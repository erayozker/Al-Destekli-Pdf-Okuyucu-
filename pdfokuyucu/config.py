from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "pdfokuyucu_app_v2.sqlite"))
STORAGE_DIR = Path(os.getenv("PDF_STORAGE_DIR", BASE_DIR / "uploaded_pdfs"))

APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}
SECRET_KEY = os.getenv("SECRET_KEY", "")
if IS_PRODUCTION and not SECRET_KEY:
    raise RuntimeError("Production ortamında SECRET_KEY zorunludur.")
if not SECRET_KEY:
    SECRET_KEY = "dev-only-change-me"

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "").lower() in {"1", "true", "yes", "on"} or bool(
    ADMIN_PASSWORD or ADMIN_PASSWORD_HASH
)
if IS_PRODUCTION and not AUTH_REQUIRED:
    raise RuntimeError("Production ortamında AUTH_REQUIRED ve admin parola yapılandırması zorunludur.")

MAX_CONTENT_LENGTH = 50 * 1024 * 1024
MAX_PDF_BYTES = int(os.getenv("MAX_PDF_BYTES", str(MAX_CONTENT_LENGTH)))
PDF_MAGIC = b"%PDF-"
AI_SYNC_MAX_PAGES = int(os.getenv("AI_SYNC_MAX_PAGES", "80"))
AI_SYNC_MAX_CHARS = int(os.getenv("AI_SYNC_MAX_CHARS", "120000"))
ENABLE_OCR = os.getenv("ENABLE_OCR", "").lower() in {"1", "true", "yes", "on"}
VIRUS_SCAN_ENABLED = os.getenv("VIRUS_SCAN_ENABLED", "").lower() in {"1", "true", "yes", "on"}
SQLITE_JOURNAL_MODE = os.getenv("SQLITE_JOURNAL_MODE", "WAL" if IS_PRODUCTION else "MEMORY").upper()

SUMMARY_LENGTHS = {"short": 3, "medium": 5, "detailed": 8}
SUMMARY_LABELS = {"short": "Kısa", "medium": "Orta", "detailed": "Detaylı"}
THEMES = {"light", "dark"}
SEARCH_MODES = {"exact", "any", "all"}

STOP_WORDS = {
    "acaba", "ama", "ancak", "artık", "bazı", "belki", "bile", "bir", "biri",
    "birkaç", "biz", "bu", "buna", "bunda", "bundan", "bunu", "çok", "da",
    "daha", "de", "defa", "diye", "en", "gibi", "hem", "hep", "her", "hiç",
    "ile", "ise", "için", "kadar", "ki", "mi", "mı", "mu", "mü", "nasıl",
    "ne", "neden", "nerede", "nereye", "niye", "olan", "olarak", "oldu",
    "olmak", "olur", "ve", "veya", "yani",
}
