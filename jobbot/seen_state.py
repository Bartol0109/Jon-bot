"""Već poslani oglasi i datum zadnjeg dnevnog slanja.

Na Renderu nema diska. Stanje stoji u istoj prikvačenoj Telegram poruci kao
postavke (polja seen_date i seen). Ključevi su kratki hash URL-a, najviše 80,
da poruka ostane ispod Telegramovog limita.
"""
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config

MAX_SEEN = 80


def hash_job_key(key: str) -> str:
    return hashlib.sha256((key or "").encode("utf-8")).hexdigest()[:12]


def zagreb_today(now=None) -> str:
    tz = ZoneInfo(config.TZ or "Europe/Zagreb")
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz)
    return current.astimezone(tz).date().isoformat()


class SeenState:
    def __init__(self, date=None, keys=None):
        self.date = date or None
        self.keys = list(keys or [])

    def is_seen(self, key: str) -> bool:
        return hash_job_key(key) in self.keys

    def already_sent_on(self, day: str) -> bool:
        return bool(self.date) and self.date == day

    def mark(self, job_keys, day: str):
        for key in job_keys:
            digest = hash_job_key(key)
            if digest not in self.keys:
                self.keys.append(digest)
        if len(self.keys) > MAX_SEEN:
            self.keys = self.keys[-MAX_SEEN:]
        self.date = day


class TelegramSeen:
    """Store sučelje (is_seen/mark) koje piše u prikvačenu poruku."""

    def __init__(self, store, baselines):
        self.store = store
        self.baselines = baselines
        loaded = store.load()
        self.state = SeenState(loaded.seen_date, loaded.seen_keys)

    def is_seen(self, key):
        return self.state.is_seen(key)

    def already_today(self):
        return self.state.already_sent_on(zagreb_today())

    def mark(self, jobs):
        self.state.mark([getattr(j, "key", j) for j in jobs], zagreb_today())
        self.store.save_seen(self.state.date, self.state.keys, *self.baselines)
