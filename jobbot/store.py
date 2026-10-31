"""Pamćenje već poslanih oglasa (SQLite)."""
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from . import config

log = logging.getLogger(__name__)


class Store:
    def __init__(self, path=config.DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, title TEXT, sent_at TEXT)")
        # čišćenje starih zapisa (>120 dana)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        self.db.execute("DELETE FROM seen WHERE sent_at < ?", (cutoff,))
        self.db.commit()

    def is_seen(self, key):
        return self.db.execute("SELECT 1 FROM seen WHERE key=?", (key,)).fetchone() is not None

    def mark(self, jobs):
        now = datetime.now(timezone.utc).isoformat()
        self.db.executemany("INSERT OR IGNORE INTO seen VALUES (?,?,?)", [(j.key, j.title, now) for j in jobs])
        self.db.commit()
