#!/usr/bin/env python3
"""
================================================================================
Attendance Post-Processor
================================================================================
Matches a downloaded attendance CSV against the Canvas gradebook export.
Produces two output files:
  - Attendance record CSV  (human-readable, keep for your files)
  - Canvas upload CSV      (import directly into Canvas Gradebook)

BEFORE RUNNING — make sure:
  1. You clicked Save or End Session in the attendance app to download the
     attendance CSV to your Downloads folder.
  2. You created a "No Submission" assignment in Canvas (e.g. "Lecture 3 Attendance"),
     PUBLISHED it, then exported the gradebook:
     Canvas Grades -> Export -> Export Entire Gradebook
  3. The Canvas export CSV is saved somewhere accessible (e.g. Downloads).

RUN:
  cd C:/Users/aknoesen/Documents/Knoesen/AttendanceApp
  python process_attendance.py

The script will ask you for everything — no editing required.

Canvas reference guides:
  Export: https://community.instructure.com/en/kb/articles/660866-how-do-i-export-grades-in-the-gradebook
  Import: https://community.instructure.com/en/kb/articles/660862-how-do-i-import-grades-in-the-gradebook
================================================================================
"""

import csv, os, glob, sys, re
from datetime import datetime
from pathlib import Path

DOWNLOADS = Path.home() / "Downloads"

# Aggregate/read-only columns Canvas always appends — must be preserved in upload file
READONLY_COLS = {
    "Assignments Current Score", "Assignments Unposted Current Score",
    "Assignments Final Score", "Assignments Unposted Final Score",
    "Imported Assignments Current Score", "Imported Assignments Unposted Current Score",
    "Imported Assignments Final Score", "Imported Assignments Unposted Final Score",
    "Current Score", "Unposted Current Score", "Final Score", "Unposted Final Score",
    "Current Grade", "Unposted Current Grade", "Final Grade", "Unposted Final Grade",
    "Override Score", "Override Grade", "Override Status",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def edit_distance(a, b):
    """Standard Levenshtein edit distance."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            prev, dp[j] = dp[j], prev if a[i-1] == b[j-1] else 1 + min(prev, dp[j], dp[j-1])
    return dp[n]


def closest_match(submitted, roster_logins, max_dist=2):
    """Return (best_login, distance) if within max_dist, else None."""
    # First try stripping spaces — catches 'j 2 d q p e' -> 'j2dqpe'
    nospace = submitted.replace(" ", "")
    if nospace in roster_logins:
        return nospace, 0
    best, best_d = None, max_dist + 1
    for login in roster_logins:
        d = edit_distance(submitted, login)
        if d < best_d:
            best, best_d = login, d
    return (best, best_d) if best_d <= max_dist else None

def ask(prompt, default=None):
    """Prompt the user; return stripped input or default if blank."""
    if default:
        answer = input(f"{prompt} [{default}]: ").strip().strip('"')
        return answer if answer else default
    return input(f"{prompt}: ").strip().strip('"')


def find_csvs_in_downloads(prefix=None):
    """Return CSVs in Downloads, most recent first. Filter by prefix if given."""
    files = glob.glob(str(DOWNLOADS / "*.csv"))
    if prefix:
        files = [f for f in files if os.path.basename(f).startswith(prefix)]
    files.sort(key=os.path.getmtime, reverse=True)
    return files


def pick_file(label, candidates, allow_manual=True):
    """Show a numbered list of candidate files and let the user pick one."""
    if candidates:
        print(f"\n{label} — recent files found:")
        for i, f in enumerate(candidates[:5]):
            mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
            print(f"  [{i+1}] {os.path.basename(f)}  ({mtime})")
        if allow_manual:
            print( "  [0] Enter a different path manually")
        choice = input("\nEnter number [1]: ").strip()
        if choice == "0" or (not choice and not candidates):
            path = input("  Paste full path: ").strip().strip('"')
        else:
            idx = (int(choice) - 1) if choice.isdigit() and int(choice) >= 1 else 0
            path = candidates[min(idx, len(candidates) - 1)]
    else:
        print(f"\n{label} — no files found automatically.")
        path = input("  Paste full path: ").strip().strip('"')

    if not os.path.isfile(path):
        sys.exit(f"\nERROR: File not found:\n  {path}")
    return path


# ── Core processing (from process_lecture.py) ─────────────────────────────────

def load_canvas_export(canvas_path, assignment_label):
    """
    Reads the Canvas gradebook export.
    Returns roster dict, raw rows, headers, column indices, and target column info.
    """
    with open(canvas_path, newline="", encoding="utf-8-sig") as f:
        all_rows = list(csv.reader(f))

    headers = all_rows[0]

    try:
        col = {
            "Student":      headers.index("Student"),
            "ID":           headers.index("ID"),
            "SIS User ID":  headers.index("SIS User ID"),
            "SIS Login ID": headers.index("SIS Login ID"),
            "Section":      headers.index("Section"),
        }
    except ValueError as e:
        sys.exit(f"ERROR: Required column missing from Canvas export: {e}\n"
                 f"Make sure you exported the full gradebook (not just one section).")

    # Find the target assignment column
    target_col, target_name = None, None
    for i, h in enumerate(headers):
        if h.startswith(assignment_label):
            target_col, target_name = i, h
            break
    if target_col is None:
        sys.exit(
            f"\nERROR: Column '{assignment_label}' not found in Canvas export.\n"
            f"Make sure the assignment is CREATED and PUBLISHED in Canvas before exporting,\n"
            f"and that the name matches exactly what you entered above."
        )

    # Find where student rows start — skip any row where Student is blank or
    # contains only whitespace / "Points Possible" metadata.
    student_start = 1
    for i, row in enumerate(all_rows[1:], start=1):
        val = row[col["Student"]].strip() if row and len(row) > col["Student"] else ""
        if val and not val.startswith("Points Possible") and not val.startswith(" "):
            student_start = i
            break

    roster    = {}   # login -> (name, nine_digit)
    nine_map  = {}   # 9-digit SIS User ID -> login  (fallback for students who submitted wrong ID)
    for row in all_rows[student_start:]:
        if not row or not row[col["Student"]].strip():
            continue
        login = row[col["SIS Login ID"]].strip().lower() if len(row) > col["SIS Login ID"] else ""
        name  = row[col["Student"]].strip()
        nine  = row[col["SIS User ID"]].strip() if len(row) > col["SIS User ID"] else ""
        if not login or len(login) > 20:   # skip test-student rows (long hash IDs)
            continue
        roster[login] = (name, nine)
        if nine:
            nine_map[nine] = login

    return roster, all_rows, headers, col, target_col, target_name, student_start, nine_map


def load_attendance(attendance_path, instructor_code):
    """Returns set of normalized login IDs, excluding the instructor code."""
    present = set()
    with open(attendance_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            login = row.get("Login ID", "").strip().lower()
            if login and login != instructor_code.lower():
                present.add(login)
    return present


def write_attendance_report(path, roster, present, assignment_label, session_date):
    """Saves a human-readable CSV of who attended (Yes/No per student)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "SIS Login ID", "SIS User ID (9-digit)",
                         f"Attended {assignment_label} ({session_date})"])
        for login, (name, nine) in sorted(roster.items(), key=lambda x: x[1][0]):
            writer.writerow([name, login, nine, "Yes" if login in present else "No"])


def write_canvas_upload(path, all_rows, headers, col, target_col, target_name, roster, present, student_start):
    """
    Saves a Canvas-ready import CSV:
      - Required identifier columns (Student, ID, SIS User ID, SIS Login ID, Section)
      - The target assignment column filled with 1 (present) or 0 (absent)
      - Read-only aggregate columns Canvas requires
    """
    required = {"Student", "ID", "SIS User ID", "SIS Login ID", "Section"}
    keep = [i for i, h in enumerate(headers)
            if h in required or i == target_col or h in READONLY_COLS]

    def filter_row(row):
        padded = row + [""] * max(0, len(headers) - len(row))
        return [padded[i] for i in keep]

    out_headers = filter_row(headers)
    target_out  = out_headers.index(target_name)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(out_headers)
        for row in all_rows[1:student_start]:      # write any metadata rows between header and students
            writer.writerow(filter_row(row))
        for row in all_rows[student_start:]:
            if not row or not row[col["Student"]].strip():
                continue
            login = row[col["SIS Login ID"]].strip().lower() if len(row) > col["SIS Login ID"] else ""
            if not login or len(login) > 20:
                continue
            out_row = filter_row(row)
            if login in roster:
                out_row[target_out] = "1" if login in present else "0"
            writer.writerow(out_row)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n=== Attendance Post-Processor ===\n")

    # ── 1. Attendance CSV ─────────────────────────────────────────────────────
    candidates = find_csvs_in_downloads(prefix=("ENG6_", "EEC1_"))
    # find_csvs_in_downloads with a tuple prefix — redo with manual filter
    candidates = [f for f in find_csvs_in_downloads()
                  if os.path.basename(f).startswith(("ENG6_", "EEC1_"))]
    attendance_path = pick_file("Attendance CSV (from the app)", candidates)
    print(f"  Selected: {os.path.basename(attendance_path)}")

    # ── 2. Canvas gradebook export ────────────────────────────────────────────
    canvas_candidates = [f for f in find_csvs_in_downloads()
                         if "Grades" in os.path.basename(f) or "grades" in os.path.basename(f)]
    canvas_path = pick_file("Canvas gradebook export", canvas_candidates)
    print(f"  Selected: {os.path.basename(canvas_path)}")

    # ── 3. Session details ────────────────────────────────────────────────────
    print()
    session_type   = ask("Session type — enter L for Lecture or B for Lab", default="L").upper()
    session_prefix = "Lab" if session_type == "B" else "Lecture"
    session_number = ask(f"{session_prefix} number (integer, e.g. 3)")
    session_date   = ask("Session date (e.g. April 7, 2026)",
                         default=datetime.now().strftime("%B %-d, %Y") if os.name != "nt"
                                 else datetime.now().strftime("%B %d, %Y").replace(" 0", " "))

    assignment_label = f"{session_prefix} {session_number} Attendance"
    print(f"\n  Assignment column to update: \"{assignment_label}\"")
    confirm = input("  Press Enter to confirm, or type the exact Canvas assignment name: ").strip()
    if confirm:
        assignment_label = confirm

    # ── 4. Instructor code ────────────────────────────────────────────────────
    print()
    if session_prefix == "Lecture":
        instructor_code = ask(
            "Instructor check-in code to exclude (6-char code shown in the app, e.g. syqedj)\n"
            "  Leave blank if not applicable", default=""
        )
    else:
        instructor_code = ""   # lab app CSV has no instructor entry

    # ── 5. Output directory ───────────────────────────────────────────────────
    default_out = str(DOWNLOADS)
    output_dir  = Path(ask("\nOutput directory for saved files", default=default_out).strip('"'))
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load & match ──────────────────────────────────────────────────────────
    print(f"\nLoading Canvas roster from:  {os.path.basename(canvas_path)}")
    roster, all_rows, headers, col, target_col, target_name, student_start, nine_map = \
        load_canvas_export(canvas_path, assignment_label)
    print(f"  {len(roster)} students")

    print(f"Loading attendance from:     {os.path.basename(attendance_path)}")
    present = load_attendance(attendance_path, instructor_code)
    print(f"  {len(present)} check-in(s)" +
          (f"  (instructor code '{instructor_code}' excluded)" if instructor_code else ""))

    # Remap any 9-digit SIS User IDs to the correct login ID
    remapped = {}
    for submitted in list(present):
        if re.fullmatch(r'\d{9}', submitted) and submitted in nine_map:
            correct = nine_map[submitted]
            present.discard(submitted)
            present.add(correct)
            remapped[submitted] = correct

    if remapped:
        print(f"\n  9-digit ID(s) automatically remapped to login ID:")
        for nine, login in sorted(remapped.items()):
            print(f"    {nine} -> {login}")

    confirmed = {login for login in present if login in roster}
    unmatched = {login for login in present if login not in roster}
    absent    = {login for login in roster  if login not in present}

    print(f"\nResults:")
    print(f"  Present : {len(confirmed)}")
    print(f"  Absent  : {len(absent)}")
    if unmatched:
        print(f"\n  Check-ins NOT matched on roster ({len(unmatched)}):")
        roster_logins = set(roster.keys())
        for u in sorted(unmatched):
            match = closest_match(u, roster_logins)
            if match:
                suggestion, dist = match
                if dist == 0:
                    print(f"    '{u}'  -> spaces stripped -> '{suggestion}'  (likely match — verify)")
                else:
                    print(f"    '{u}'  -> possible typo for '{suggestion}'  (edit distance {dist})")
            else:
                print(f"    '{u}'  (no close match found)")

    # ── Write output files ────────────────────────────────────────────────────
    label_safe = assignment_label.replace(" ", "_")
    date_safe  = session_date.replace(",", "").replace(" ", "_")

    report_path = output_dir / f"Attendance_{label_safe}_{date_safe}.csv"
    upload_path = output_dir / f"Canvas_Upload_{label_safe}_{date_safe}.csv"

    write_attendance_report(report_path, roster, confirmed, assignment_label, session_date)
    write_canvas_upload(upload_path, all_rows, headers, col, target_col, target_name,
                        roster, confirmed, student_start)

    pct = round(100 * len(confirmed) / len(roster)) if roster else 0
    print(f"\nAttendance record : {report_path}")
    print(f"Canvas upload file: {upload_path}")
    print(f"\nNext step: Canvas Gradebook -> Import -> upload the Canvas_Upload file above.")
    print(f"\nDone — {len(confirmed)}/{len(roster)} attended ({pct}%)")
    input("\nPress Enter to exit.")


if __name__ == "__main__":
    main()
