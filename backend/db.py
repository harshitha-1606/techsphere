import sqlite3

from . import config


def connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    for d in (config.CERT_DIR, config.PREVIEW_DIR):
        d.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript((config.BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
        e = config.EVENT
        c.execute(
            "INSERT OR IGNORE INTO events (slug,name,event_date,college) VALUES (?,?,?,?)",
            (e["slug"], e["name"], e["event_date"], e["college"]),
        )
        c.execute("DELETE FROM staged_imports WHERE created_at < datetime('now','-1 day')")


def event_id(conn):
    return conn.execute("SELECT id FROM events WHERE slug=?", (config.EVENT["slug"],)).fetchone()["id"]
