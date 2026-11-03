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

    def covers(self, job):
        from .seen_state import fingerprints
        keys = list(fingerprints(job))
        key = getattr(job, "key", None)
        if key:
            keys.append(key)
        if not keys:
            return False
        marks = ",".join("?" * len(keys))
        return self.db.execute(f"SELECT 1 FROM seen WHERE key IN ({marks}) LIMIT 1", keys).fetchone() is not None

    def mark(self, jobs):
        from .seen_state import fingerprints
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for job in jobs:
            rows.append((job.key, job.title, now))
            for fp in fingerprints(job):
                rows.append((fp, job.title, now))
        self.db.executemany("INSERT OR IGNORE INTO seen VALUES (?,?,?)", rows)
        self.db.commit()
