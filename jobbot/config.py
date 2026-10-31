"""Konfiguracija iz environment varijabli."""
import os
from pathlib import Path

try:  # .env lokalno (na Railwayu se varijable postavljaju u dashboardu)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def env(name, default=""):
    v = os.getenv(name)
    return v.strip() if v and v.strip() else default


TZ = env("TZ_NAME", "Europe/Zagreb")
RUN_MODE = env("RUN_MODE", "cron").lower()            # cron | scheduler
RUN_AT = env("RUN_AT", "12:00")                        # za scheduler mod (lokalno vrijeme)
ONLY_AT_LOCAL_HOUR = env("ONLY_AT_LOCAL_HOUR", "")     # npr. "12" -> DST-safe cron "0 10,11 * * *"

# Pohrana: Railway volume (RAILWAY_VOLUME_MOUNT_PATH se postavlja automatski) ili DATA_DIR
_data_dir = env("DATA_DIR") or env("RAILWAY_VOLUME_MOUNT_PATH")
PERSISTENT = bool(_data_dir) or env("ASSUME_PERSISTENT", "") == "1"
DATA_DIR = Path(_data_dir or "./data")
DB_PATH = DATA_DIR / "seen_jobs.sqlite3"

# Ako nema trajne pohrane, gledamo samo oglase iz zadnjih ~26 h (fallback dedupe po datumu)
MAX_AGE_HOURS = int(env("MAX_AGE_HOURS", "48" if PERSISTENT else "26"))
MAX_RESULTS = int(env("MAX_RESULTS", "8"))

JOB_CRITERIA = env(
    "JOB_CRITERIA",
    "Student bez iskustva, programerski poslovi (junior, praksa, studentski posao), remote ili u Hrvatskoj",
)

LLM_API_KEY = env("LLM_API_KEY")
LLM_BASE_URL = env("LLM_BASE_URL", "https://api.x.ai/v1").rstrip("/")
LLM_MODEL = env("LLM_MODEL", "grok-4.20-non-reasoning")

SENDER = env("SENDER", "callmebot").lower()            # callmebot | twilio | telegram
CALLMEBOT_PHONE = env("CALLMEBOT_PHONE")
CALLMEBOT_APIKEY = env("CALLMEBOT_APIKEY")
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = env("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TWILIO_WHATSAPP_TO = env("TWILIO_WHATSAPP_TO")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")

# Izvori koje želiš isključiti, npr. "himalayas,arbeitnow"
DISABLED_SOURCES = {s.strip().lower() for s in env("DISABLED_SOURCES").split(",") if s.strip()}
