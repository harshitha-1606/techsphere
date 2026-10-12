"""TECH SPHERE certificate portal - Flask API (also serves the frontend)."""
import hmac
import io
import json
import secrets
import tempfile
import threading
import time
import zipfile
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory, session
from werkzeug.security import check_password_hash

from . import certificates as certs
from . import config, db
from .excel_import import ImportFileError, parse_workbook

app = Flask(__name__, static_folder=None)
app.config.update(
    SECRET_KEY=config.secret_key(),
    MAX_CONTENT_LENGTH=config.MAX_UPLOAD_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="None" if config.CORS_ORIGINS and config.COOKIE_SECURE else "Lax",
    SESSION_COOKIE_SECURE=config.COOKIE_SECURE,
    PERMANENT_SESSION_LIFETIME=8 * 3600,
)
db.init_db()
COORD_HASH = config.coordinator_password_hash()
_gen_lock = threading.Lock()
_job = {"state": "idle", "total": 0, "done": 0, "success": 0, "failed": 0, "skipped": 0}
_fails = {}  # rate limiting: (ip, username) -> [timestamps]


# ---------- helpers ----------
def err(msg, code=400, **extra):
    return jsonify({"error": msg, **extra}), code


def norm_email(v):
    return str(v or "").strip().lower()


def rate_limited(key):
    now = time.time()
    _fails[key] = [t for t in _fails.get(key, []) if now - t < 600]
    return len(_fails[key]) >= 5


def note_fail(key):
    _fails.setdefault(key, []).append(time.time())


def coordinator_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if session.get("role") != "coordinator":
            return err("Coordinator login required.", 401)
        return fn(*a, **k)
    return w


def participant_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if session.get("role") != "participant" or not session.get("pid"):
            return err("Participant login required.", 401)
        return fn(*a, **k)
    return w


def cert_path(row):
    return config.CERT_DIR / row["file_name"] if row["file_name"] else None


def cert_ready(row):
    p = cert_path(row)
    return bool(row["status"] == "generated" and p and p.exists())


def preview_path(certificate_id):
    return config.PREVIEW_DIR / f"{certificate_id}.jpg"


def participant_rows(conn, pid=None):
    sql = """SELECT p.id pid, p.name, p.department, p.email, p.team, p.roll_no, p.mobile, p.topic, p.data_hash phash,
                    c.certificate_id, c.status, c.file_name, c.error, c.data_hash chash, c.generated_at
             FROM participants p LEFT JOIN certificates c ON c.participant_id = p.id
             WHERE p.event_id = ?"""
    args = [db.event_id(conn)]
    if pid is not None:
        sql += " AND p.id = ?"
        args.append(pid)
    return conn.execute(sql + " ORDER BY p.department, p.name", args).fetchall()


def serialize(r):
    state = r["status"] or "pending"
    if state == "generated" and (r["chash"] != r["phash"] or not cert_ready(r)):
        state = "pending"
    return {"id": r["pid"], "name": r["name"], "department": r["department"], "email": r["email"],
            "certificate_id": r["certificate_id"], "status": state, "error": r["error"],
            "team": r["team"], "roll_no": r["roll_no"], "topic": r["topic"]}


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
        "object-src 'self'; frame-src 'self' blob:; connect-src 'self'")
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    origin = request.headers.get("Origin")
    if origin and origin in config.CORS_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
        resp.headers["Vary"] = "Origin"
    return resp


@app.errorhandler(413)
def too_big(_):
    return err(f"File too large (limit {config.MAX_UPLOAD_BYTES // 1024 // 1024} MB).", 413)


@app.errorhandler(404)
def nf(_):
    return err("Not found.", 404) if request.path.startswith("/api/") else (send_from_directory(config.FRONTEND_DIR, "index.html"))


@app.errorhandler(500)
def ise(_):
    return err("Unexpected server error.", 500)


@app.before_request
def json_guard():
    # Cross-site form posts cannot set a JSON content type, which is our CSRF guard for JSON endpoints.
    if request.method == "POST" and request.path.startswith("/api/") and not request.path.endswith("/upload"):
        if request.content_length and not request.is_json:
            return err("Content-Type must be application/json.", 415)


@app.route("/api/<path:_p>", methods=["OPTIONS"])
def preflight(_p):
    return ("", 204)


# ---------- public ----------
@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/event")
def event_info():
    return jsonify(config.EVENT)


# ---------- coordinator auth ----------
@app.post("/api/coordinator/login")
def coordinator_login():
    d = request.get_json(silent=True) or {}
    u, p = str(d.get("username", "")).strip(), str(d.get("password", ""))
    key = (request.remote_addr, "coord:" + u.lower())
    if rate_limited(key):
        return err("Too many failed attempts. Please wait a few minutes.", 429)
    ok = hmac.compare_digest(u, config.COORDINATOR_USERNAME) and check_password_hash(COORD_HASH, p)
    if not ok:
        note_fail(key)
        return err("Invalid username or password.", 401)
    session.clear()
    session.permanent = True
    session["role"] = "coordinator"
    return jsonify({"ok": True})


@app.post("/api/coordinator/logout")
def coordinator_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/coordinator/me")
@coordinator_required
def coordinator_me():
    return jsonify({"role": "coordinator", "username": config.COORDINATOR_USERNAME})


# ---------- upload / import ----------
@app.post("/api/coordinator/upload")
@coordinator_required
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return err("Please choose an Excel file (.xlsx or .xls).")
    content = f.read()
    if not content:
        return err("The uploaded file is empty.")
    try:
        result = parse_workbook(content, f.filename)
    except ImportFileError as e:
        return err(str(e), 422)
    except Exception:
        app.logger.exception("Excel parse failure")
        return err("The spreadsheet could not be processed.", 422)
    if result["total"] == 0:
        return err("No participant rows were found below the header row.", 422)
    token = secrets.token_urlsafe(16)
    with db.connect() as c:
        c.execute("INSERT INTO staged_imports (token,payload) VALUES (?,?)",
                  (token, json.dumps({"filename": f.filename, "result": result})))
    return jsonify({"token": token, "filename": f.filename, **result})


@app.post("/api/coordinator/import")
@coordinator_required
def do_import():
    token = (request.get_json(silent=True) or {}).get("token", "")
    with db.connect() as c:
        row = c.execute("SELECT payload FROM staged_imports WHERE token=?", (token,)).fetchone()
        if not row:
            return err("This upload has expired or was already imported. Please upload the file again.", 404)
        payload = json.loads(row["payload"])
        res = payload["result"]
        valid = [r for r in res["rows"] if r["valid"]]
        if not valid:
            return err("There are no valid rows to import.", 422)
        eid = db.event_id(c)
        inserted = updated = unchanged = 0
        for r in valid:
            d = r["data"]
            h = certs.data_hash(d["name"], d["department"])
            ex = c.execute("SELECT * FROM participants WHERE event_id=? AND email=?", (eid, d["email"])).fetchone()
            if ex is None:
                cur = c.execute(
                    "INSERT INTO participants (event_id,email,name,department,team,roll_no,mobile,topic,data_hash) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (eid, d["email"], d["name"], d["department"], d["team"], d["roll_no"], d["mobile"], d["topic"], h))
                c.execute("INSERT INTO certificates (participant_id,certificate_id,status) VALUES (?,?, 'pending')",
                          (cur.lastrowid, certs.new_certificate_id()))
                inserted += 1
            else:
                same = (ex["name"], ex["department"], ex["team"], ex["roll_no"], ex["mobile"], ex["topic"]) == \
                       (d["name"], d["department"], d["team"], d["roll_no"], d["mobile"], d["topic"])
                if same:
                    unchanged += 1
                    continue
                c.execute("UPDATE participants SET name=?,department=?,team=?,roll_no=?,mobile=?,topic=?,data_hash=?,"
                          "updated_at=datetime('now') WHERE id=?",
                          (d["name"], d["department"], d["team"], d["roll_no"], d["mobile"], d["topic"], h, ex["id"]))
                if not c.execute("SELECT 1 FROM certificates WHERE participant_id=?", (ex["id"],)).fetchone():
                    c.execute("INSERT INTO certificates (participant_id,certificate_id,status) VALUES (?,?, 'pending')",
                              (ex["id"], certs.new_certificate_id()))
                updated += 1
        c.execute("INSERT INTO import_runs (filename,total,valid,invalid,inserted,updated,unchanged) VALUES (?,?,?,?,?,?,?)",
                  (payload["filename"], res["total"], res["valid"], res["invalid"], inserted, updated, unchanged))
        c.execute("DELETE FROM staged_imports WHERE token=?", (token,))
    return jsonify({"ok": True, "inserted": inserted, "updated": updated, "unchanged": unchanged,
                    "invalid_skipped": res["invalid"]})


@app.delete("/api/coordinator/staging/<token>")
@coordinator_required
def cancel_import(token):
    with db.connect() as c:
        c.execute("DELETE FROM staged_imports WHERE token=?", (token,))
    return jsonify({"ok": True})


# ---------- data ----------
@app.get("/api/coordinator/summary")
@coordinator_required
def summary():
    with db.connect() as c:
        rows = [serialize(r) for r in participant_rows(c)]
        last = c.execute("SELECT * FROM import_runs ORDER BY id DESC LIMIT 1").fetchone()
    return jsonify({
        "total_participants": len(rows),
        "generated": sum(r["status"] == "generated" for r in rows),
        "available": sum(r["status"] == "generated" for r in rows),
        "failed": sum(r["status"] == "failed" for r in rows),
        "pending": sum(r["status"] == "pending" for r in rows),
        "invalid_rows": last["invalid"] if last else 0,
        "last_import": dict(last) if last else None,
    })


@app.get("/api/coordinator/participants")
@coordinator_required
def participants():
    with db.connect() as c:
        return jsonify([serialize(r) for r in participant_rows(c)])


# ---------- generation ----------
def _generate_one(conn, r):
    """Idempotent: skips when an up-to-date certificate file already exists. Returns 'ok'|'skipped'."""
    if r["status"] == "generated" and r["chash"] == r["phash"] and cert_ready(r):
        return "skipped"
    fname = certs.safe_filename(r["name"], "")
    clash = conn.execute("SELECT 1 FROM certificates WHERE file_name=? AND participant_id<>?", (fname, r["pid"])).fetchone()
    if clash:
        fname = certs.safe_filename(r["name"], "_" + r["certificate_id"][-6:])
    certs.render_pdf(config.CERT_DIR / fname, r["name"], r["department"], r["certificate_id"])
    certs.render_preview(preview_path(r["certificate_id"]), r["name"], r["department"])
    conn.execute("UPDATE certificates SET status='generated', data_hash=?, file_name=?, error=NULL, "
                 "generated_at=datetime('now') WHERE participant_id=?", (r["phash"], fname, r["pid"]))
    return "ok"


def _run_generation(only_failed):
    try:
        with db.connect() as c:
            rows = participant_rows(c)
            if only_failed:
                rows = [r for r in rows if r["status"] == "failed"]
            _job.update(total=len(rows), done=0, success=0, failed=0, skipped=0)
            for r in rows:
                try:
                    res = _generate_one(c, r)
                    _job["skipped" if res == "skipped" else "success"] += 1
                except Exception as e:  # keep going; the row can be retried
                    app.logger.exception("Certificate generation failed for participant %s", r["pid"])
                    c.execute("UPDATE certificates SET status='failed', error=? WHERE participant_id=?",
                              (str(e)[:300] or e.__class__.__name__, r["pid"]))
                    _job["failed"] += 1
                c.commit()
                _job["done"] += 1
    finally:
        _job["state"] = "done"
        _gen_lock.release()


@app.post("/api/coordinator/generate")
@coordinator_required
def generate():
    only_failed = bool((request.get_json(silent=True) or {}).get("only_failed"))
    with db.connect() as c:
        if not participant_rows(c):
            return err("No participants imported yet. Upload and import an Excel file first.", 409)
    if not _gen_lock.acquire(blocking=False):
        return err("Generation is already running.", 409)
    _job.update(state="running", total=0, done=0, success=0, failed=0, skipped=0)
    threading.Thread(target=_run_generation, args=(only_failed,), daemon=True).start()
    return jsonify({"ok": True})


@app.get("/api/coordinator/generate/status")
@coordinator_required
def generate_status():
    return jsonify(_job)


def _send_cert(row, inline):
    if not row or not cert_ready(row) or row["chash"] != row["phash"]:
        return err("Certificate is not available yet.", 404)
    p = cert_path(row)
    return send_file(p, mimetype="application/pdf", as_attachment=not inline, download_name=p.name)


@app.get("/api/coordinator/certificates/<cid>/pdf")
@coordinator_required
def coord_pdf(cid):
    with db.connect() as c:
        row = next((r for r in participant_rows(c) if r["certificate_id"] == cid), None)
    if not row:
        return err("Certificate not found.", 404)
    return _send_cert(row, request.args.get("inline") == "1")


@app.get("/api/coordinator/certificates/<cid>/preview.jpg")
@coordinator_required
def coord_preview(cid):
    with db.connect() as c:
        row = next((r for r in participant_rows(c) if r["certificate_id"] == cid), None)
    if not row or not cert_ready(row) or not preview_path(cid).exists():
        return err("Preview not available.", 404)
    return send_file(preview_path(cid), mimetype="image/jpeg")


@app.get("/api/coordinator/certificates.zip")
@coordinator_required
def zip_all():
    with db.connect() as c:
        rows = [r for r in participant_rows(c) if cert_ready(r) and r["chash"] == r["phash"]]
    if not rows:
        return err("No generated certificates to download yet.", 409)
    tmp = tempfile.NamedTemporaryFile(prefix="techsphere_", suffix=".zip", delete=False)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for r in rows:
                z.write(cert_path(r), arcname=cert_path(r).name)
        tmp.close()
        data = Path(tmp.name).read_bytes()
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    return send_file(io.BytesIO(data), mimetype="application/zip", as_attachment=True,
                     download_name="TechSphere_Certificates.zip")


# ---------- participant ----------
@app.post("/api/participant/login")
def participant_login():
    if not config.DEMO_MODE:
        return err("Participant login is disabled until a secure sign-in method is configured.", 503)
    d = request.get_json(silent=True) or {}
    u, p = norm_email(d.get("username")), norm_email(d.get("password"))
    key = (request.remote_addr, "part:" + u)
    if rate_limited(key):
        return err("Too many failed attempts. Please wait a few minutes.", 429)
    row = None
    if u and hmac.compare_digest(u.encode(), p.encode()):  # demo mode: email is both username and password
        with db.connect() as c:
            row = c.execute("SELECT id FROM participants WHERE event_id=? AND email=?", (db.event_id(c), u)).fetchone()
    if not row:
        note_fail(key)
        return err("Invalid credentials. Use your registered Email ID as both username and password.", 401)
    session.clear()
    session.permanent = True
    session["role"], session["pid"] = "participant", row["id"]
    return jsonify({"ok": True})


@app.post("/api/participant/logout")
def participant_logout():
    session.clear()
    return jsonify({"ok": True})


def _me():
    with db.connect() as c:
        rows = participant_rows(c, session["pid"])
    return rows[0] if rows else None


@app.get("/api/participant/me")
@participant_required
def participant_me():
    r = _me()
    if not r:
        session.clear()
        return err("Account not found.", 401)
    s = serialize(r)
    return jsonify({"name": r["name"], "department": r["department"], "email": r["email"],
                    "certificate_id": r["certificate_id"], "ready": s["status"] == "generated",
                    "event": config.EVENT})


@app.get("/api/participant/certificate.pdf")
@participant_required
def participant_pdf():
    r = _me()
    return _send_cert(r, request.args.get("inline") == "1") if r else err("Not found.", 404)


@app.get("/api/participant/certificate/preview.jpg")
@participant_required
def participant_preview():
    r = _me()
    if not r or not cert_ready(r) or r["chash"] != r["phash"] or not preview_path(r["certificate_id"]).exists():
        return err("Certificate is not available yet.", 404)
    return send_file(preview_path(r["certificate_id"]), mimetype="image/jpeg")


# ---------- frontend ----------
@app.get("/")
def index():
    return send_from_directory(config.FRONTEND_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path):
    if path.startswith("api/"):
        return err("Not found.", 404)
    f = config.FRONTEND_DIR / path
    if f.is_file() and config.FRONTEND_DIR in f.resolve().parents:
        return send_from_directory(config.FRONTEND_DIR, path)
    return send_from_directory(config.FRONTEND_DIR, "index.html")
