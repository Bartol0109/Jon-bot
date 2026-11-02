"""Već poslani oglasi i datum zadnjeg dnevnog slanja.

Na Renderu nema diska. Stanje stoji u istoj prikvačenoj Telegram poruci kao
postavke. Svaki oglas pamti se po kratkom hashu kanonskog linka i po hashu
normaliziranog naslova s tvrtkom, pa isti oglas s drugog izvora ili s
parametrima za praćenje ne ide opet. Zapisi stariji od 90 dana otpadaju.
Ako poruka ne može stati u Telegramov limit, otpadaju najstariji zapisi.
"""
import hashlib
import re
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit
from zoneinfo import ZoneInfo

from . import config

RETENTION_DAYS = 90
HASH_LEN = 8
LEGACY_LEN = 12
# Gornja granica zapisa prije nego što se gleda preostali prostor u poruci.
MAX_BLOB = 3600
EPOCH = date(2024, 1, 1)
_ALPH = "0123456789abcdefghijklmnopqrstuvwxyz"

_TRACKING = {
    "fbclid", "gclid", "gbraid", "wbraid", "dclid", "msclkid", "twclid", "yclid", "ttclid",
    "mc_cid", "mc_eid", "mkt_tok", "_hsenc", "_hsmi", "igshid", "igsh",
    "gad_source", "gad_campaignid", "_ga", "_gl", "li_fat_id", "oly_enc_id", "oly_anon_id",
}
_LEGAL = {
    "ltd", "limited", "inc", "llc", "gmbh", "ag", "sa", "bv", "corp", "plc",
    "doo", "sro", "oy", "kft", "zrt", "srl", "sarl", "lp", "llp",
}
_DIACRITICS = str.maketrans("čćđšž", "ccdsz")
_GENDER = re.compile(
    r"\((?:m\s*/\s*w\s*/\s*d|m\s*/\s*f\s*/\s*d|f\s*/\s*m\s*/\s*d|m\s*/\s*w\s*/\s*x|d\s*/\s*m\s*/\s*w)\)",
    re.IGNORECASE,
)


def zagreb_today(now=None) -> str:
    tz = ZoneInfo(config.TZ or "Europe/Zagreb")
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz)
    return current.astimezone(tz).date().isoformat()


def _as_date(day) -> date:
    if isinstance(day, datetime):
        return day.date()
    if isinstance(day, date):
        return day
    return date.fromisoformat(str(day)[:10])


def _day_index(day) -> int:
    return (_as_date(day) - EPOCH).days


def _encode_day(index: int) -> str:
    n = max(0, int(index))
    chars = []
    for _ in range(3):
        n, rem = divmod(n, 36)
        chars.append(_ALPH[rem])
    return "".join(reversed(chars))


def _decode_day(text: str) -> int:
    n = 0
    for ch in text:
        n = n * 36 + _ALPH.index(ch)
    return n


def _hash(text: str, length: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _is_tracking(key: str) -> bool:
    k = (key or "").lower()
    return k.startswith("utm_") or k in _TRACKING


def canonical_url(url: str) -> str:
    """Link bez www, fragmenta i parametara za praćenje. http i https su isto."""
    raw = (url or "").strip()
    if not raw or raw.lower().startswith("mailto:"):
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return ""
    path = re.sub(r"/+", "/", parts.path or "")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    path = path.lower()
    pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if _is_tracking(key):
            continue
        pairs.append((key.lower(), value))
    pairs.sort()
    query = urlencode(pairs)
    base = "https://" + host + path
    return base + ("?" + query if query else "")


def norm_phrase(text: str) -> str:
    s = (text or "").casefold().translate(_DIACRITICS)
    s = _GENDER.sub(" ", s)
    s = s.replace(".", "")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return " ".join(tok for tok in s.split() if tok not in _LEGAL)


def title_company_key(title: str, company: str) -> str:
    title_n = norm_phrase(title)
    if not title_n:
        return ""
    return title_n + "|" + norm_phrase(company)


def fingerprints(job) -> list:
    out = []
    url = canonical_url(getattr(job, "url", "") or "")
    if url:
        out.append(_hash("u:" + url, HASH_LEN))
    tc = title_company_key(getattr(job, "title", "") or "", getattr(job, "company", "") or "")
    if tc:
        out.append(_hash("t:" + tc, HASH_LEN))
    return out


def legacy_hash(key: str) -> str:
    """Stari 12-znamenkasti hash sirovog ključa, da postojeći pin i dalje vrijedi."""
    return _hash(key or "", LEGACY_LEN)


def dedupe_jobs(jobs):
    """Isti oglas iz više izvora ostaje samo jednom, po linku ili naslovu+tvrtki."""
    kept = []
    seen = set()
    for job in jobs:
        fps = fingerprints(job)
        if not fps:
            fps = ["k:" + (getattr(job, "key", "") or str(id(job)))]
        if any(fp in seen for fp in fps):
            continue
        seen.update(fps)
        kept.append(job)
    return kept


class SeenState:
    def __init__(self, date=None):
        self.date = date or None
        self.items = []    # (day_index, 8-hex) najstariji prvi
        self.legacy = []   # (day_index, 12-hex) stari pin

    def already_sent_on(self, day: str) -> bool:
        return bool(self.date) and self.date == day

    def seen_job(self, job) -> bool:
        fps = set(fingerprints(job))
        if fps and any(h in fps for _, h in self.items):
            return True
        if not self.legacy:
            return False
        old = legacy_hash(getattr(job, "key", "") or "")
        return any(h == old for _, h in self.legacy)

    def mark_jobs(self, jobs, day, claim_day=True, max_chars=MAX_BLOB):
        stamp = _day_index(day)
        have = {h for _, h in self.items}
        for job in jobs:
            for fp in fingerprints(job):
                if fp not in have:
                    self.items.append((stamp, fp))
                    have.add(fp)
        if claim_day:
            self.date = _as_date(day).isoformat()
        self.prune(_as_date(day), max_chars)

    def prune(self, today, max_chars):
        today_i = _day_index(today)
        self.items = [(d, h) for d, h in self.items if today_i - d <= RETENTION_DAYS]
        self.legacy = [(d, h) for d, h in self.legacy if today_i - d <= RETENTION_DAYS]
        self.items.sort(key=lambda row: row[0])
        self.legacy.sort(key=lambda row: row[0])
        while (self.items or self.legacy) and len(self.pack()) > max_chars:
            item_day = self.items[0][0] if self.items else None
            legacy_day = self.legacy[0][0] if self.legacy else None
            if item_day is None or (legacy_day is not None and legacy_day < item_day):
                self.legacy.pop(0)
            else:
                self.items.pop(0)
        if len(self.pack()) > max_chars:
            self.items.clear()
            self.legacy.clear()

    def pack(self) -> str:
        if not self.items and not self.legacy:
            return ""
        groups = _pack_groups(self.items, HASH_LEN, prefix="")
        legacy = _pack_groups(self.legacy, LEGACY_LEN, prefix="L")
        return "2|" + ".".join(groups) + "|" + ".".join(legacy)

    @classmethod
    def unpack(cls, blob, date_value=None):
        state = cls(date_value)
        if not blob or not isinstance(blob, str) or not blob.startswith("2|"):
            return state
        body = blob[2:]
        groups, _, legacy = body.partition("|")
        state.items = _unpack_groups(groups, HASH_LEN, prefixed=False)
        state.legacy = _unpack_groups(legacy, LEGACY_LEN, prefixed=True)
        return state


def _pack_groups(rows, width, prefix):
    groups = []
    current = None
    buf = []
    for day, token in rows:
        if day != current:
            if current is not None:
                groups.append(prefix + _encode_day(current) + "".join(buf))
            current = day
            buf = [token]
        else:
            buf.append(token)
    if current is not None:
        groups.append(prefix + _encode_day(current) + "".join(buf))
    return groups


def _unpack_groups(text, width, prefixed):
    rows = []
    if not text:
        return rows
    for part in text.split("."):
        if prefixed:
            if not part.startswith("L") or len(part) < 4:
                continue
            part = part[1:]
        if len(part) < 3:
            continue
        try:
            day = _decode_day(part[:3])
        except ValueError:
            continue
        hexes = part[3:]
        hexes = hexes[: len(hexes) // width * width]
        if not re.fullmatch(r"[0-9a-f]*", hexes):
            continue
        for i in range(0, len(hexes), width):
            rows.append((day, hexes[i:i + width]))
    return rows


def legacy_blob(hashes, day) -> str:
    state = SeenState()
    stamp = _day_index(day)
    for raw in hashes or []:
        token = str(raw).strip().lower()
        if re.fullmatch(r"[0-9a-f]{12}", token):
            state.legacy.append((stamp, token))
    return state.pack()


def fit_seen_blob(blob: str, max_chars: int, today=None) -> str:
    if max_chars <= 0:
        return ""
    state = SeenState.unpack(blob or "")
    state.prune(today or date.today(), max_chars)
    packed = state.pack()
    return packed if len(packed) <= max_chars else ""


class TelegramSeen:
    """Store sučelje (covers/mark) koje piše u prikvačenu poruku.

    claim_day=True samo za dnevni pregled: drugi poziv isti zagrebački dan
    ne šalje opet. Ručni /poslovi i /mjesec pamte oglase, ali ne gase podne.
    """

    def __init__(self, store, baselines, claim_day=True):
        self.store = store
        self.baselines = baselines
        self.claim_day = claim_day
        loaded = store.load()
        self.state = SeenState.unpack(getattr(loaded, "seen_blob", "") or "", loaded.seen_date)
        self.state.date = loaded.seen_date

    def covers(self, job):
        return self.state.seen_job(job)

    def is_seen(self, key):
        return self.covers(_KeyJob(key))

    def already_today(self):
        return self.state.already_sent_on(zagreb_today())

    def mark(self, jobs):
        before = (self.state.date, self.state.pack())
        self.state.mark_jobs(jobs, zagreb_today(), claim_day=self.claim_day)
        if (self.state.date, self.state.pack()) == before:
            return
        self.store.save_seen(self.state.date, self.state.pack(), *self.baselines)


class _KeyJob:
    """Stari poziv is_seen(url) i dalje prepoznaje kanonski link i stari hash."""

    def __init__(self, key):
        self.url = key or ""
        self.title = ""
        self.company = ""
        self.key = key or ""
