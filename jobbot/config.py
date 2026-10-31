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

# Uloge za keyword filter. Prazan ROLE_KEYWORDS = ovaj popis. Vlastita vrijednost
# (zarezom odvojene fraze) ga zamjenjuje. Kratke oznake (qa, bi, ai) dobiju granicu riječi.
DEFAULT_ROLE_KEYWORDS = [
    "developer", "develop", "programer", "programmer", "programiranje", "software",
    "engineer", "inženjer", "inzenjer", "frontend", "front-end", "backend", "back-end",
    "fullstack", "full-stack", "full stack",
    "python", "java", "javascript", "typescript", "react", "node", ".net", "c#", "c++",
    "php", "golang", "rust", "kotlin", "swift", "android", "ios", "coding", "razvoj",
    "informatika", "informatičar", "informaticar", "machine learning", "ml", "ai",
    "data analyst", "data engineer", "data science", "data scientist", "analytics",
    "analitičar", "analiticar", "poslovni analitičar", "poslovni analiticar",
    "business analyst", "bi analyst", "bi", "business intelligence",
    "qa", "tester", "testing", "quality assurance", "test engineer", "software tester",
    "osiguranje kvalitete", "ispitivač", "ispitivac",
    "it support", "technical support", "tech support", "tehnička podrška", "tehnicka podrska",
    "podrška", "podrska", "helpdesk", "help desk", "help-desk", "service desk",
    "support engineer", "application support", "app support", "podrška aplikacijama",
    "desktop support", "korisnička podrška", "korisnicka podrska",
    "customer success engineer", "technical success",
    "devops", "sysadmin", "sys admin", "system administrator", "systems administrator",
    "sistemski administrator", "administrator sustava", "sistem administrator",
]
_role_raw = env("ROLE_KEYWORDS", "")
ROLE_KEYWORDS = [p.strip() for p in _role_raw.split(",") if p.strip()] or list(DEFAULT_ROLE_KEYWORDS)

def _csv(name, default):
    raw = env(name, "")
    items = [p.strip() for p in raw.split(",") if p.strip()]
    return items or list(default)


# On-site i hybrid samo u ovim gradovima. Prazno = Zagreb, Zadar.
DEFAULT_ONSITE_CITIES = ["Zagreb", "Zadar"]
ONSITE_CITIES = _csv("ONSITE_CITIES", DEFAULT_ONSITE_CITIES)
# Remote mora biti otvoren kandidatima bilo gdje u EU, ili Europe/worldwide koje uključuje EU.
# Jedna država (npr. samo Njemačka) nije dovoljna. Prazno = ovaj popis.
REMOTE_REGIONS = _csv("REMOTE_REGIONS", [
    "EU", "EEA", "European Union", "Europe", "European", "Schengen", "EMEA",
    "CET", "CEST",
    "worldwide", "anywhere", "global", "world",
    "Croatia", "Hrvatska",
])
# Fraze koje znače da remote oglas traži drugi jezik. Engleski smije biti dovoljan; hrvatski je u redu.
# Prazno = ugrađeni popis. Vlastita vrijednost ga zamjenjuje.
EXCLUDED_LANGUAGES = _csv("EXCLUDED_LANGUAGES", [
    "fluent german", "german required", "german fluency", "native german", "german speaker",
    "german speaking", "german-speaking", "must speak german", "knowledge of german",
    "proficiency in german", "command of german", "german language",
    "deutschkenntnisse", "fließend deutsch", "fliessend deutsch", "deutsch erforderlich",
    "verhandlungssicher deutsch", "muttersprache deutsch", "gute deutschkenntnisse",
    "fluent french", "french required", "native french", "french speaker", "french speaking",
    "french-speaking", "must speak french", "français courant", "francais courant",
    "fluent dutch", "native dutch", "dutch required", "dutch speaker", "dutch speaking",
    "dutch-speaking", "must speak dutch", "vloeiend nederlands",
    "fluent italian", "native italian", "italian required", "italian speaker", "italian speaking",
    "italian-speaking", "must speak italian",
    "fluent spanish", "native spanish", "spanish required", "spanish speaker", "spanish speaking",
    "spanish-speaking", "must speak spanish",
    "fluent portuguese", "portuguese required", "native portuguese", "portuguese speaker",
    "fluent polish", "native polish", "polish required", "polish speaker", "polish speaking",
    "polish-speaking",
    "fluent swedish", "fluent danish", "fluent norwegian", "fluent finnish",
    "swedish required", "danish required", "norwegian required", "finnish required",
    "swedish speaking", "danish speaking", "norwegian speaking",
    "fluent czech", "fluent hungarian", "fluent greek", "fluent romanian",
])

JOB_CRITERIA = env(
    "JOB_CRITERIA",
    "Student bez iskustva. Početne uloge: programiranje, data/business/BI analitičar, QA i testiranje, "
    "IT i tehnička podrška, helpdesk, application support, technical ili customer success engineer, "
    "junior DevOps ili sysadmin. On-site ili hybrid samo Zagreb ili Zadar. Remote samo ako je otvoren "
    "kandidatima bilo gdje u EU (ili Europe/worldwide) i ako je dovoljan engleski. Hrvatski je u redu. "
    "Bez senior/lead/manager razine i bez obveznog njemačkog, francuskog ili drugog jezika.",
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
# Tajna u zaglavlju X-Telegram-Bot-Api-Secret-Token. Prazno = webhook odbija sve.
WEBHOOK_SECRET = env("WEBHOOK_SECRET")

# Izvori koje želiš isključiti, npr. "himalayas,arbeitnow"
DISABLED_SOURCES = {s.strip().lower() for s in env("DISABLED_SOURCES").split(",") if s.strip()}
