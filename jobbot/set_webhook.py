"""Prijavi Telegram webhook na ovaj servis.

Na Renderu: Shell → python -m jobbot.set_webhook
Lokalno: PUBLIC_URL=https://tvoj-tunel python -m jobbot.set_webhook
"""
import os
import sys

import requests

from . import config


def webhook_base_url():
    return (os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")


def set_webhook(base_url=None):
    base = (base_url or webhook_base_url()).rstrip("/")
    if not base:
        raise SystemExit("Nema PUBLIC_URL ni RENDER_EXTERNAL_URL.")
    if not config.TELEGRAM_BOT_TOKEN or not config.WEBHOOK_SECRET:
        raise SystemExit("Treba TELEGRAM_BOT_TOKEN i WEBHOOK_SECRET.")
    url = base + "/telegram/webhook"
    r = requests.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/setWebhook",
        json={
            "url": url,
            "secret_token": config.WEBHOOK_SECRET,
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
        },
        timeout=30,
    )
    data = r.json()
    if not data.get("ok"):
        raise SystemExit(f"setWebhook nije uspio: {data.get('description', data)}")
    return url


def main():
    url = set_webhook()
    print(f"Webhook postavljen: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
