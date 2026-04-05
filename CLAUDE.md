# Attendance App — Project Notes

## What this is
A local Node.js web app for recording lecture attendance via QR code.
- Teacher runs the server on their laptop, projects the QR code at end of lecture
- Students scan QR (or type the 6-char code) on their phone → enter UC Davis login ID → checked in
- Validates against full class roster CSVs (loaded fresh at each startup)
- Saves attendance to CSV in `attendance/` folder

## How to run — every lecture

```
cd C:\Users\aknoesen\Documents\Knoesen\AttendanceApp
python start.py
```

The launcher automatically:
1. Kills any old server on port 3000
2. Starts the Node.js server
3. Starts ngrok with the permanent static domain
4. Opens the browser with the ngrok URL pre-filled

Then in the browser:
1. Select course (ENG 006 or EEC 001)
2. Enter lecture topic (optional)
3. Click **Start Session** — ngrok URL is already filled in
4. Test with login ID `testprofk` before showing QR to students
5. Project the QR code
6. Click **Save Attendance CSV** or **End Session** when done

**At home (no ngrok needed):** Clear the ngrok URL field before clicking Start Session.

## ngrok static domain (permanent)
```
https://spinous-tripedal-sandra.ngrok-free.dev
```
This URL never changes. It is hardcoded in `start.py` and pre-filled in the dashboard automatically.
ngrok.exe is located at: `C:\Users\aknoesen\Desktop\ngrok.exe`

## Test account
Login ID: `testprofk` — works for both ENG 006 and EEC 001. Use this to verify the app is working before each lecture.

## Student roster CSVs
Rosters are loaded fresh every time `start.py` is run. Update the CSV in Box before launching.

- **ENG 006** (191 students): `C:\Users\aknoesen\Box\Andre Knoesen\Coursework Folder\ENG6Admin2026\2026-03-29T0616_Grades-ENG_006_A01-A11_SQ_2026.csv`
- **EEC 001** (194 students): `C:\Users\aknoesen\Box\Andre Knoesen\Coursework Folder\EEC1Admin2026\2026-03-29T0250_Grades-ECE_Emerge_SQ_2026.csv`

CSV format: Canvas gradebook export. Row 1 = headers, Row 2 = "Points Possible" (skipped). Key columns: Student (Last, First), ID, SIS User ID, SIS Login ID (Kerberos), Section.

## Attendance records
Saved to `C:\Users\aknoesen\Documents\Knoesen\AttendanceApp\attendance\`
Format: `ENG6_2026-03-30_XXXXXX.csv` and matching `.json`
**Must click Save or End Session before closing** — there is no auto-save.

## Files
```
AttendanceApp/
├── start.py           — Launcher: starts server + ngrok, opens browser
├── server.js          — Express backend, CSV loading, all API routes
├── package.json
├── public/
│   ├── teacher.html   — Instructor dashboard (start session, QR, live list, save)
│   └── student.html   — Student check-in page (mobile-optimized)
└── attendance/        — Saved CSV + JSON records per session
```

## API routes
- `GET  /`                        → teacher dashboard
- `GET  /attend/:code`            → student check-in page
- `GET  /api/status`              → student counts per course
- `POST /api/session/start`       → start session, returns code + QR data URL
- `GET  /api/session/:code`       → live session state + attendance list
- `POST /api/session/:code/save`  → save CSV (session stays active)
- `POST /api/session/:code/end`   → save CSV + mark session inactive
- `POST /api/attend/:code`        → student submits login ID

## Windows Firewall — port 3000 (already done)
Completed 2026-03-30. No action needed.
```
netsh advfirewall firewall add rule name="Attendance App" dir=in action=allow protocol=TCP localport=3000
```

## Notes
- Students can enter UC Davis login ID (e.g. `hwabbott`) OR their numeric student ID
- Duplicate check-ins are detected and acknowledged, not double-counted
- Server must be restarted (re-run start.py) after switching networks
- Students who cannot connect: write name on paper, sign it, hand to Professor Knoesen
