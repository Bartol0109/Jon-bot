"""Slanje poruka: CallMeBot (WhatsApp), Twilio (WhatsApp) ili Telegram. Odabir preko SENDER env varijable."""
import html
import logging
import time

import requests

from . import config

log = logging.getLogger(__name__)


class Sender:
    name = "base"
    max_len = 1000
    delay = 3.0

    def bold(self, s):
        return f"*{s}*"

    def esc(self, s):
        return s

    def check(self):
        raise NotImplementedError

    def send_one(self, text):
        raise NotImplementedError

    def send_all(self, messages):
        for i, m in enumerate(messages):
            if i:
                time.sleep(self.delay)
            self.send_one(m)
            log.info("[%s] poslana poruka %d/%d (%d znakova)", self.name, i + 1, len(messages), len(m))


class CallMeBot(Sender):
    name = "callmebot"
    max_len = 900      # GET URL – hrvatski znakovi se URL-enkodiraju, pa držimo poruke kratkima
    delay = 6.0

    def check(self):
        if not (config.CALLMEBOT_PHONE and config.CALLMEBOT_APIKEY):
            raise SystemExit("Nedostaje CALLMEBOT_PHONE ili CALLMEBOT_APIKEY")

    def send_one(self, text):
        r = requests.get("https://api.callmebot.com/whatsapp.php", timeout=60,
                         params={"phone": config.CALLMEBOT_PHONE, "text": text, "apikey": config.CALLMEBOT_APIKEY})
        body = r.text.lower()
        ok = "queued" in body or "sent" in body
        if r.status_code != 200 or ("error" in body and not ok):
            raise RuntimeError(f"CallMeBot greška {r.status_code}: {r.text[:300]}")


class Twilio(Sender):
    name = "twilio"
    max_len = 1500     # Twilio limit za WhatsApp body je 1600
    delay = 4.0        # sandbox: max 1 poruka / 3 s

    def check(self):
        if not (config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN and config.TWILIO_WHATSAPP_TO):
            raise SystemExit("Nedostaje TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN ili TWILIO_WHATSAPP_TO")

    @staticmethod
    def _wa(n):
        return n if n.startswith("whatsapp:") else f"whatsapp:{n}"

    def send_one(self, text):
        url = f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json"
        r = requests.post(url, timeout=60, auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
                          data={"From": self._wa(config.TWILIO_WHATSAPP_FROM), "To": self._wa(config.TWILIO_WHATSAPP_TO),
                                "Body": text})
        if r.status_code >= 300:
            raise RuntimeError(f"Twilio greška {r.status_code}: {r.text[:300]}")


class Telegram(Sender):
    name = "telegram"
    max_len = 3800     # Telegram limit 4096
    delay = 1.0

    def bold(self, s):
        return f"<b>{s}</b>"

    def esc(self, s):
        return html.escape(s, quote=False)

    def check(self):
        if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
            raise SystemExit("Nedostaje TELEGRAM_BOT_TOKEN ili TELEGRAM_CHAT_ID")

    def send_one(self, text):
        r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage", timeout=60,
                          json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML",
                                "link_preview_options": {"is_disabled": True}})
        if r.status_code >= 300 or not r.json().get("ok"):
            raise RuntimeError(f"Telegram greška {r.status_code}: {r.text[:300]}")


SENDERS = {"callmebot": CallMeBot, "twilio": Twilio, "telegram": Telegram}


def get_sender(name=None):
    name = (name or config.SENDER).lower()
    if name not in SENDERS:
        raise SystemExit(f"Nepoznat SENDER '{name}'. Opcije: {', '.join(SENDERS)}")
    return SENDERS[name]()
