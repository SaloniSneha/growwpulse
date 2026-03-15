"""
Central configuration — reads from .env / environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
REVIEWS_DIR = DATA_DIR / "reviews"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"

for _d in (REVIEWS_DIR, REPORTS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── App ────────────────────────────────────────────────────────────────────
APP_ID = os.getenv("APP_ID", "com.nextbillion.groww")
APP_NAME = os.getenv("APP_NAME", "Groww")

# ── Groq ───────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Gemini ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── Email ──────────────────────────────────────────────────────────────────
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", EMAIL_SENDER)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# ── Scheduler ──────────────────────────────────────────────────────────────
SCHEDULER_RECIPIENT = os.getenv("GROWW_SCHEDULER_RECIPIENT", EMAIL_RECIPIENT)
SCHEDULER_TZ = os.getenv("GROWW_SCHEDULER_TZ", "Asia/Kolkata")
SCHEDULER_INTERVAL_MINUTES = int(os.getenv("GROWW_SCHEDULER_INTERVAL_MINUTES", "5"))
SCHEDULER_WEEKS = int(os.getenv("GROWW_SCHEDULER_WEEKS", "8"))
SCHEDULER_MAX_REVIEWS = int(os.getenv("GROWW_SCHEDULER_MAX_REVIEWS", "1000"))

# ── Scraper defaults ───────────────────────────────────────────────────────
DEFAULT_WEEKS = 10
DEFAULT_MAX_REVIEWS = 5000
MIN_REVIEW_WORDS = 5
