# TECH SPHERE Poster Presentation 2026 – Certificate Portal
Audisankara College of Engineering and Technology, Gudur · Event date: 13 October 2026

Coordinator uploads an Excel list → validates → imports → generates one PDF per participant on the **official
certificate template** → participants log in and view/download **only their own** certificate.

## Stack (and why it differs from the brief)
Flask (Python) API + SQLite + plain JavaScript frontend (no build step), served by the same server.
The build environment had no Maven/npm package access, so Spring Boot/React could not be compiled or tested there.
This stack was built **and tested end-to-end**. PostgreSQL is **not** implemented yet (SQLite in WAL mode on a
persistent disk is used; fine for one event / one server).

```
backend/   app.py (API) · excel_import.py · certificates.py · config.py · db.py · schema.sql · assets/ (template, font)
frontend/  index.html · styles.css · app.js · config.js · assets/ (logo, fonts, sample template)
sample/    participants_template.xlsx      tests/  test_workflow.py      run.py
```

## Run locally (VS Code terminal)
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
python run.py                                          # http://localhost:8000
```
Demo coordinator login: username `techshere`, password `coordinator@123` (works only while `DEMO_MODE=true`;
never shown in the UI). Participants: registered Email ID as username **and** password (demo mode only).

Tests: `python -m unittest discover -s tests -v`

## Configuration (.env)
| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Signs session cookies. **Required** when `DEMO_MODE=false`. |
| `DEMO_MODE` | `true` = email-as-password for participants + default coordinator password. Set `false` for production (participant login is then disabled until a secure method is added). |
| `COORDINATOR_USERNAME` / `COORDINATOR_PASSWORD_HASH` | Generate hash: `python -c "from werkzeug.security import generate_password_hash as g; print(g('NewPassword'))"` |
| `DATA_DIR` | Database + generated PDFs/previews. **Must be on persistent storage.** |
| `COOKIE_SECURE` | `true` behind HTTPS. |
| `CORS_ORIGINS` | Only if the frontend is hosted on a different origin; also set `window.TS_API_BASE` in `frontend/config.js`, and use HTTPS + `COOKIE_SECURE=true`. |

## Excel format
Header names are matched, not positions (see `sample/participants_template.xlsx`). Required: **Student Name,
Department, Email ID**. Optional: Team / Batch, Roll No., Mobile Number, Theme / Topic. The header row may be
anywhere in the first 25 rows; merged Department cells are applied to all rows they cover. Invalid rows are shown
with row numbers and never imported silently.

## Certificates
The template is used as the background; only name and department are drawn on its blank lines (auto-shrinks to
fit; ellipsis only at the minimum size). Certificate IDs look like `TS26-1A2B3C4D`, stay stable if a participant's
details are corrected, and re-running "Generate" never duplicates up-to-date certificates. The background is the
supplied template resampled to A4 @ 300 dpi to keep each PDF about 0.5 MB.

## Deploy
1. Pick a host with a **persistent disk** (VM, or Render/Railway with a volume). Set the env vars above, with `DATA_DIR` on the volume.
2. `pip install -r requirements.txt && python run.py` (uses waitress). Put it behind HTTPS (nginx/Caddy/platform TLS).
3. Set `DEMO_MODE=false`, a strong `SECRET_KEY`, and `COORDINATOR_PASSWORD_HASH`.
4. Test: open the site, coordinator login, upload sample, import, generate, ZIP, participant login, restart the app
   and confirm certificates are still downloadable.

## Known limits
- Participant auth in demo mode is weak by design (email = password). Production needs OTP/hashed passwords.
- `.xls` reading depends on `xlrd` and was not tested; `.xlsx` is tested.
- The browser UI was not opened in a real browser during development (none was available); API and static serving were tested.
