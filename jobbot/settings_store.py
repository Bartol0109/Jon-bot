"""Postavke u prikvačenoj Telegram poruci.

Renderov besplatni plan nema disk koji preživi restart. Prikvačena poruka u
privatnom chatu ostaje, ne košta ništa i istu je može pročitati dnevni
GitHub Actions (isti bot token i chat id).
"""
import json
import logging

import requests

from . import config

log = logging.getLogger(__name__)

MARKER = "JOBBOT_SETTINGS="


class Settings:
    def __init__(self, role_keywords=None, onsite_cities=None):
        # None = ugrađeno / env zadano. Lista = točno te vrijednosti.
        self.role_keywords = role_keywords
        self.onsite_cities = onsite_cities

    def to_dict(self):
        return {"v": 1, "role_keywords": self.role_keywords, "onsite_cities": self.onsite_cities}

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
    return Settings(
        role_keywords=list(roles) if isinstance(roles, list) else None,
        onsite_cities=list(cities) if isinstance(cities, list) else None,
    )


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


def format_settings_message(settings, roles_baseline, cities_baseline):
    body = "\n".join([
        "⚙️ Postavke job bota",
        "Ova poruka je prikvačena. Ne briši je — dnevni pregled u 12:00 čita iste postavke.",
        "",
        _preview(settings.role_keywords, roles_baseline, "Uloge"),
        _preview(settings.onsite_cities, cities_baseline, "Gradovi (on-site/hybrid)"),
        "",
        "Remote: EU / Europe / worldwide, engleski dovoljan. Hrvatski je u redu.",
        MARKER + settings.to_json(),
    ])
    return body[:4000]


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

    def save(self, settings, roles_baseline, cities_baseline):
        if not config.TELEGRAM_CHAT_ID:
            raise RuntimeError("Nedostaje TELEGRAM_CHAT_ID")
        text = format_settings_message(settings, roles_baseline, cities_baseline)
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
