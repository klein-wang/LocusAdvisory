import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
PORT = int(os.environ.get("PORT", "5001"))

TURSO_URL = os.environ.get("TURSO_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
DB_PATH_OVERRIDE = os.environ.get("DB_PATH")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL") or SMTP_USER or "no-reply@locusadvisory.com"
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() != "false"

DEV_EMAIL_MODE = not SMTP_HOST or not SMTP_USER

FEEDBACK_TO_EMAIL = os.environ.get("FEEDBACK_TO_EMAIL") or SMTP_USER


def resolve_db_path():
    if DB_PATH_OVERRIDE:
        return DB_PATH_OVERRIDE
    db_dir = PROJECT_ROOT / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "locus.db")