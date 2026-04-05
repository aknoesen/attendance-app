"""
Attendance App Launcher
-----------------------
Run this script before each lecture.
It starts the Node.js server AND ngrok, then opens your browser.

Usage:
    python start.py

Requirements:
    - Node.js installed
    - ngrok.exe downloaded (script searches common locations)
"""

import subprocess
import sys
import time
import webbrowser
import os

try:
    from urllib.request import urlopen
    from urllib.error import URLError
except ImportError:
    print("ERROR: Python 3 required.")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────

APP_DIR = r"C:\Users\aknoesen\Documents\Knoesen\AttendanceApp"

# Static ngrok domain (permanent — never changes)
NGROK_STATIC_DOMAIN = "spinous-tripedal-sandra.ngrok-free.dev"
NGROK_URL = f"https://{NGROK_STATIC_DOMAIN}"

# Places to look for ngrok.exe (add more paths here if needed)
NGROK_SEARCH_PATHS = [
    r"C:\Users\aknoesen\Desktop\ngrok.exe",
    r"C:\Users\aknoesen\Downloads\ngrok.exe",
    r"C:\ngrok\ngrok.exe",
    r"C:\tools\ngrok.exe",
    r"ngrok.exe",  # if it's in PATH
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def find_ngrok():
    for path in NGROK_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    # Try PATH
    result = subprocess.run(["where", "ngrok"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip().splitlines()[0]
    return None


def kill_port_3000():
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if ":3000" in line and "LISTENING" in line:
            parts = line.split()
            pid = parts[-1]
            try:
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                               capture_output=True)
                print(f"  Stopped old server (PID {pid})")
            except Exception:
                pass


def wait_for_server(timeout=15):
    for _ in range(timeout * 2):
        try:
            urlopen("http://localhost:3000/api/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False



# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  ATTENDANCE APP LAUNCHER")
    print("=" * 60)

    # 1. Kill any existing server
    print("\n[1/4] Checking for old server on port 3000...")
    kill_port_3000()

    # 2. Find ngrok
    print("[2/4] Looking for ngrok...")
    ngrok_path = find_ngrok()
    if not ngrok_path:
        print("\n  ERROR: ngrok.exe not found.")
        print("  Download from https://ngrok.com and place ngrok.exe on your Desktop.")
        print("  Then run this script again.")
        input("\nPress Enter to exit.")
        sys.exit(1)
    print(f"  Found ngrok at: {ngrok_path}")

    # 3. Start Node.js server
    print("[3/4] Starting Node.js server...")
    server_proc = subprocess.Popen(
        ["npm.cmd", "start"],
        cwd=APP_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    )

    if not wait_for_server():
        print("\n  ERROR: Server did not start in time.")
        print("  Check the server terminal for errors.")
        input("\nPress Enter to exit.")
        sys.exit(1)
    print("  Server is running.")

    # 4. Start ngrok with static domain
    print("[4/4] Starting ngrok tunnel...")
    ngrok_proc = subprocess.Popen(
        [ngrok_path, "http", f"--domain={NGROK_STATIC_DOMAIN}", "3000"],
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    )
    time.sleep(2)  # give ngrok a moment to connect

    # 5. Open browser with ngrok URL pre-filled in the dashboard
    print("\nOpening teacher dashboard in browser...")
    webbrowser.open(f"http://localhost:3000?ngrok={NGROK_URL}")

    # 6. Print summary
    print("\n" + "=" * 60)
    print("  READY FOR CLASS")
    print("=" * 60)
    print(f"\n  ngrok URL (already pre-filled in dashboard):")
    print(f"  {NGROK_URL}")
    print(f"\n  Teacher dashboard: http://localhost:3000")
    print(f"\n  Test login ID: testprofk")
    print("\n  Both the server and ngrok are running in separate windows.")
    print("  Close those windows (or press Ctrl+C in each) to shut down.")
    print("\n" + "=" * 60)
    input("\nPress Enter to exit this launcher (server keeps running).")


if __name__ == "__main__":
    main()
