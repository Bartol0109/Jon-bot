"""Webhook za Telegram. Ulazna poruka budi Renderov besplatni servis.

Odgovor 200 ide odmah. Pretraga (/poslovi) radi u pozadini jer Telegram ne čeka dugo.
"""
import asyncio
import logging
import re
import secrets
import threading

from fastapi import FastAPI, HTTPException, Request

from jobbot import config
from jobbot.bot_commands import handle_command
from jobbot.runtime import ENV_CITIES, ENV_EXCLUDE, ENV_NARROW, ENV_ROLES, apply
from jobbot.set_webhook import set_webhook
from jobbot.settings_store import TelegramSettingsStore

log = logging.getLogger("job-bot-web")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI()
_store = TelegramSettingsStore()
_seen_updates = set()
_tasks = set()
_digest_lock = threading.Lock()
_CRON_TOKEN = re.compile(r"^[A-Za-z0-9]{8,128}$")


def _secret_ok(got: str) -> bool:
    expected = config.WEBHOOK_SECRET
    if not expected or not got:
        return False
    return secrets.compare_digest(got, expected)


def _send_plain(text: str):
    import requests
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        raise RuntimeError("Nedostaje TELEGRAM_BOT_TOKEN ili TELEGRAM_CHAT_ID")
    r = requests.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text[:4000],
            "link_preview_options": {"is_disabled": True},
        },
        timeout=30,
    )
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(str(data.get("description") or data)[:200])


def process_message(text: str):
    settings = _store.load()
    apply(settings)
    reply, updated, action = handle_command(text, settings, ENV_ROLES, ENV_CITIES, ENV_EXCLUDE, ENV_NARROW)
    if updated is not None:
        _store.save(updated, ENV_ROLES, ENV_CITIES, ENV_EXCLUDE, ENV_NARROW)
        apply(updated)
    if reply:
        _send_plain(reply)
    if action == "search":
        from main import run_once
        run_once(sender_name="telegram", mark=False)
    elif action == "search_month":
        from main import run_once
        run_once(
            sender_name="telegram",
            mark=False,
            skip_seen=True,
            max_age_hours=24 * 30,
            empty_line="U zadnjih 30 dana nema oglasa koji prolaze filtre. Neki izvori objavljuju samo svježe oglase.",
        )


def _process_safe(text: str):
    try:
        process_message(text)
    except Exception as exc:  # noqa: BLE001
        log.exception("Obrada poruke nije uspjela")
        try:
            _send_plain(f"Nešto je puklo: {exc}"[:500])
        except Exception:  # noqa: BLE001
            log.exception("Ni poruka o grešci nije poslana")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/telegram/setup")
def setup(request: Request):
    if not _secret_ok(request.headers.get("x-setup-token", "")):
        raise HTTPException(status_code=401, detail="Krivi X-Setup-Token")
    url = set_webhook()
    return {"ok": True, "url": url}


@app.post("/telegram/webhook")
async def webhook(request: Request):
    if not _secret_ok(request.headers.get("x-telegram-bot-api-secret-token", "")):
        raise HTTPException(status_code=401, detail="Krivi secret token")
    update = await request.json()
    uid = update.get("update_id")
    if uid in _seen_updates:
        return {"ok": True}
    if uid is not None:
        _seen_updates.add(uid)
        if len(_seen_updates) > 500:
            _seen_updates.clear()
            _seen_updates.add(uid)
    message = update.get("message") or update.get("edited_message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    if not config.TELEGRAM_CHAT_ID or str(chat_id) != str(config.TELEGRAM_CHAT_ID):
        log.info("Zanemarujem chat %s", chat_id)
        return {"ok": True}
    text = message.get("text") or ""
    if not text.startswith("/"):
        return {"ok": True}
    _schedule(text)
    return {"ok": True}


def _schedule(text: str):
    task = asyncio.create_task(asyncio.to_thread(_process_safe, text))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def cron_token_ok(got: str) -> bool:
    expected = config.CRON_SECRET or ""
    if not _CRON_TOKEN.fullmatch(expected):
        log.error("CRON_SECRET mora imati 8–128 znakova i samo slova i znamenke")
        return False
    if not got or not _CRON_TOKEN.fullmatch(got):
        return False
    return secrets.compare_digest(got, expected)


def run_daily_digest():
    if not _digest_lock.acquire(blocking=False):
        log.info("Dnevni pregled već radi — preskačem")
        return
    try:
        from jobbot.runtime import ENV_CITIES, ENV_EXCLUDE, ENV_NARROW, ENV_ROLES
        from jobbot.seen_state import TelegramSeen, zagreb_today
        settings = _store.load()
        apply(settings)
        seen = TelegramSeen(_store, (ENV_ROLES, ENV_CITIES, ENV_EXCLUDE, ENV_NARROW))
        if seen.already_today():
            log.info("Dnevni pregled za %s je već poslan", zagreb_today())
            return
        from main import run_once
        run_once(sender_name="telegram", mark=True, store=seen)
    except Exception as exc:  # noqa: BLE001
        log.exception("Dnevni pregled nije uspio")
        try:
            _send_plain(f"Dnevni pregled nije uspio: {exc}"[:500])
        except Exception:  # noqa: BLE001
            log.exception("Ni poruka o grešci nije poslana")
    finally:
        _digest_lock.release()


def _schedule_daily():
    task = asyncio.create_task(asyncio.to_thread(run_daily_digest))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


@app.api_route("/cron/daily", methods=["GET", "POST"])
async def cron_daily(request: Request, token: str = ""):
    got = request.headers.get("x-cron-token") or token or ""
    if not cron_token_ok(got):
        raise HTTPException(status_code=401, detail="Krivi ili nedopušten CRON token")
    _schedule_daily()
    return {"ok": True}
