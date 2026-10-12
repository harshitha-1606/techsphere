"""Runtime configuration. Secrets come from environment variables / .env, never from the frontend."""
import os
import secrets
from pathlib import Path

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent


def _load_dotenv():
    f = ROOT_DIR / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def env(name, default=None):
    return os.environ.get(name, default)


def _path(value):
    p = Path(value)
    return p if p.is_absolute() else (ROOT_DIR / p).resolve()


DATA_DIR = _path(env("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "techsphere.db"
CERT_DIR = DATA_DIR / "certificates"
PREVIEW_DIR = DATA_DIR / "previews"
FRONTEND_DIR = ROOT_DIR / "frontend"
ASSETS_DIR = BASE_DIR / "assets"

# DEMO_MODE=true enables the event-prototype behaviours: participant email-as-password
# and the documented default coordinator credentials. Turn it off for production.
DEMO_MODE = env("DEMO_MODE", "true").lower() == "true"
COOKIE_SECURE = env("COOKIE_SECURE", "false").lower() == "true"
CORS_ORIGINS = [o.strip() for o in env("CORS_ORIGINS", "").split(",") if o.strip()]

EVENT = {
    "slug": "techsphere-2026",
    "name": "TECH SPHERE POSTER PRESENTATION",
    "event_date": "2026-10-13",
    "college": "Audisankara College of Engineering and Technology, Gudur",
}

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_NAME_LEN = 100
MAX_DEPT_LEN = 120

COORDINATOR_USERNAME = env("COORDINATOR_USERNAME", "techshere")


def coordinator_password_hash():
    h = env("COORDINATOR_PASSWORD_HASH")
    if h:
        return h
    if DEMO_MODE:  # documented demo credential for the event prototype
        return generate_password_hash("coordinator@123")
    raise RuntimeError("Set COORDINATOR_PASSWORD_HASH (DEMO_MODE is off).")


def secret_key():
    k = env("SECRET_KEY")
    if k:
        return k
    if not DEMO_MODE:
        raise RuntimeError("Set SECRET_KEY (DEMO_MODE is off).")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    f = DATA_DIR / ".secret_key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()
