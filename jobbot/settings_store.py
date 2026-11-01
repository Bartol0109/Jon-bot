"""Postavke u prikvačenoj Telegram poruci.

Renderov besplatni plan nema disk koji preživi restart. Prikvačena poruka u
privatnom chatu ostaje, ne košta ništa i istu je može pročitati dnevni
GitHub Actions (isti bot token i chat id).
"""
import json
import logging
import threading

import requests

from . import config

log = logging.getLogger(__name__)

MARKER = "JOBBOT_SETTINGS="
_write_lock = threading.Lock()


class Settings:
    def __init__(self, role_keywords=None, onsite_cities=None, exclude_keywords=None,
                 allow_remote=None, narrow_mode=None, narrow_keywords=None):
        # None = ugrađeno / env zadano. Lista = točno te vrijednosti (i prazna).
        # allow_remote None = uključeno. narrow_mode None = isključeno (široki filtri).
        self.role_keywords = role_keywords
        self.onsite_cities = onsite_cities
        self.exclude_keywords = exclude_keywords
        self.allow_remote = allow_remote
        self.narrow_mode = narrow_mode
        self.narrow_keywords = narrow_keywords
        self.seen_date = None
        self.seen_keys = []

    def to_dict(self):
        return {
            "v": 1,
            "role_keywords": self.role_keywords,
            "onsite_cities": self.onsite_cities,
            "exclude_keywords": self.exclude_keywords,
            "allow_remote": self.allow_remote,
            "narrow_mode": self.narrow_mode,
            "narrow_keywords": self.narrow_keywords,
            "seen_date": self.seen_date,
            "seen": list(self.seen_keys or [])[-80:],
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))


def parse_settings_text(text):
    if not text or MARKER not in text:
        return None
    raw = text.split(MARKER, 1)[1].strip().splitlines()[0].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Prikvačena poruka ima oštećen JOBBOT_SETTINGS")
        return None
    roles = data.get("role_keywords")
    cities = data.get("onsite_cities")
    excluded = data.get("exclude_keywords")
    allow_remote = data.get("allow_remote") if "allow_remote" in data else None
    if not isinstance(allow_remote, bool):
        allow_remote = None
    narrow_mode = data.get("narrow_mode") if "narrow_mode" in data else None
    if not isinstance(narrow_mode, bool):
        narrow_mode = None
    narrow = data.get("narrow_keywords")
    settings = Settings(
        role_keywords=list(roles) if isinstance(roles, list) else None,
        onsite_cities=list(cities) if isinstance(cities, list) else None,
        exclude_keywords=list(excluded) if isinstance(excluded, list) else None,
        allow_remote=allow_remote,
        narrow_mode=narrow_mode,
        narrow_keywords=list(narrow) if isinstance(narrow, list) else None,
    )
    seen = data.get("seen")
    settings.seen_keys = [str(k) for k in seen][-80:] if isinstance(seen, list) else []
    date = data.get("seen_date")
    settings.seen_date = date if isinstance(date, str) and date else None
    return settings


def _preview(items, baseline, label):
    if items is None:
        shown = ", ".join(baseline)
        suffix = " (zadano)"
    else:
        shown = ", ".join(items) if items else "—"
        suffix = ""
    if len(shown) > 700:
        shown = shown[:700] + "…"
    return f"{label}: {shown}{suffix}"


def _remote_line(settings):
    if settings.allow_remote is False:
        return "Remote: isključen (samo on-site/hybrid u gradovima)"
    if settings.allow_remote is True:
        return "Remote: uključen"
    return "Remote: uključen (zadano)"


def _narrow_line(settings):
    if settings.narrow_mode is True:
        return "Uski način: uključen (naslov mora pogoditi uži popis)"
    if settings.narrow_mode is False:
        return "Uski način: isključen (programiranje, analitika, podrška)"
    return "Uski način: isključen (zadano)"


def format_settings_message(settings, roles_baseline, cities_baseline, exclude_baseline, narrow_baseline):
    body = "\n".join([
        "⚙️ Postavke job bota",
        "Ova poruka je prikvačena. Ne briši je — dnevni pregled u 12:00 čita iste postavke.",
        "",
        _preview(settings.role_keywords, roles_baseline, "Uloge"),
        _preview(settings.onsite_cities, cities_baseline, "Gradovi (on-site/hybrid)"),
        _preview(settings.exclude_keywords, exclude_baseline, "Isključeno iz naslova"),
        _remote_line(settings),
        _narrow_line(settings),
        _preview(settings.narrow_keywords, narrow_baseline, "Uski popis (naslov)"),
        "",
        "Kad je remote uključen: EU / Europe / worldwide, samo engleski ili hrvatski.",
    ])
    json_line = MARKER + settings.to_json()
    if len(body) + 1 + len(json_line) > 4000:
        body = body[: 4000 - len(json_line) - 1]
    return body + "\n" + json_line


def _api(method, payload):
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Nedostaje TELEGRAM_BOT_TOKEN")
    r = requests.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}",
        json=payload, timeout=30,
    )
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError(f"Telegram {method} nije vratio JSON ({r.status_code})")
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method}: {str(data.get('description') or data)[:200]}")
    return data.get("result")


def _message_text(msg):
    if not msg:
        return ""
    return msg.get("text") or msg.get("caption") or ""


class TelegramSettingsStore:
    def load(self):
        if not config.TELEGRAM_CHAT_ID:
            return Settings()
        chat = _api("getChat", {"chat_id": config.TELEGRAM_CHAT_ID}) or {}
        parsed = parse_settings_text(_message_text(chat.get("pinned_message")))
        return parsed if parsed is not None else Settings()

    def _write(self, settings, roles_baseline, cities_baseline, exclude_baseline, narrow_baseline):
        text = format_settings_message(settings, roles_baseline, cities_baseline, exclude_baseline, narrow_baseline)
        chat = _api("getChat", {"chat_id": config.TELEGRAM_CHAT_ID}) or {}
        pinned = chat.get("pinned_message") or {}
        pinned_text = _message_text(pinned)
        if pinned.get("message_id") and MARKER in pinned_text:
            try:
                _api("editMessageText", {
                    "chat_id": config.TELEGRAM_CHAT_ID,
                    "message_id": pinned["message_id"],
                    "text": text,
                    "link_preview_options": {"is_disabled": True},
                })
            except RuntimeError as exc:
                if "not modified" not in str(exc).lower():
                    raise
            return
        sent = _api("sendMessage", {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
            "link_preview_options": {"is_disabled": True},
        })
        _api("pinChatMessage", {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "message_id": sent["message_id"],
            "disable_notification": True,
        })

    def save(self, settings, roles_baseline, cities_baseline, exclude_baseline, narrow_baseline):
        if not config.TELEGRAM_CHAT_ID:
            raise RuntimeError("Nedostaje TELEGRAM_CHAT_ID")
        with _write_lock:
            latest = self.load()
            settings.seen_date = latest.seen_date
            settings.seen_keys = list(latest.seen_keys or [])
            self._write(settings, roles_baseline, cities_baseline, exclude_baseline, narrow_baseline)

    def save_seen(self, date, keys, roles_baseline, cities_baseline, exclude_baseline, narrow_baseline):
        if not config.TELEGRAM_CHAT_ID:
            raise RuntimeError("Nedostaje TELEGRAM_CHAT_ID")
        with _write_lock:
            latest = self.load()
            latest.seen_date = date
            latest.seen_keys = list(keys)[-80:]
            self._write(latest, roles_baseline, cities_baseline, exclude_baseline, narrow_baseline)
