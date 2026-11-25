import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BACKEND_DIR / "instance"

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 5
TOKEN_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
# The Vite dev server moves to 5174, 5175... when 5173 is busy, so accept any local port.
ALLOWED_ORIGINS = [r"^http://(localhost|127\.0\.0\.1):\d+$"]


def default_database_url():
    return os.environ.get(
        "DATABASE_URL", f"sqlite:///{(INSTANCE_DIR / 'docverify.db').as_posix()}"
    )


def secret_key():
    """Use SECRET_KEY from the environment, or a random key kept in instance/."""
    configured = os.environ.get("SECRET_KEY")
    if configured:
        return configured

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32), encoding="utf8")
    return key_file.read_text(encoding="utf8").strip()
