"""Izvori oglasa. Svaki izvor je izoliran: greška u jednom ne ruši ostale."""
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from .models import Job

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (compatible; job-bot/1.0; personal use)",
      "Accept": "application/json, text/html, application/rss+xml;q=0.9, */*;q=0.8"}
TIMEOUT = 25

DEV_QUERIES_REMOTE = ["junior developer", "intern software", "entry level developer"]
# Hrvatski portali objavljuju i poslove u inozemstvu – njih preskačemo (osim ako su remote)
FOREIGN_RE = re.compile(r"inozem|njemačk|austrij|turska|irsk|sloven|švicarsk|nizozem|belgij|franc|ital|"
                        r"švedsk|norvešk|dansk|češk|slovačk|mađarsk|poljsk|bosn|bih|srbij|crna gora|"
                        r"makedonij|ujedinjen|uk\b|usa|sad\b|kanad|dubai|uae|katar|malta|cipar", re.I)
HR_QUERIES = ["developer", "programer", "software", "junior", "praksa", "student", "frontend", "backend"]


def _get(url, **kw):
    r = requests.get(url, headers=UA, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


def _clean(text, limit=600):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _dt_iso(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _dt_epoch(v):
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


# ---------------- Remote izvori ----------------

def remotive():
    data = _get("https://remotive.com/api/remote-jobs", params={"category": "software-dev"}).json()
    for j in data.get("jobs", []):
        yield Job("Remotive", j["title"], j.get("company_name", ""), j["url"],
                  location=j.get("candidate_required_location", ""), remote=True,
                  posted=_dt_iso(j.get("publication_date")), tags=j.get("tags", []) + [j.get("job_type", "")],
                  description=_clean(j.get("description")))


def remoteok():
    data = _get("https://remoteok.com/api").json()
    for j in data[1:]:  # prvi element je pravna napomena
        if not j.get("position"):
            continue
        yield Job("RemoteOK", j["position"], j.get("company", ""), j.get("url") or j.get("apply_url", ""),
                  location=j.get("location", ""), remote=True, posted=_dt_iso(j.get("date")),
                  tags=j.get("tags", []), description=_clean(j.get("description")))


def arbeitnow():
    for page in (1, 2, 3):
        data = _get("https://www.arbeitnow.com/api/job-board-api", params={"page": page}).json()
        for j in data.get("data", []):
            loc = j.get("location", "")
            is_hr = "croatia" in loc.lower() or "hrvatska" in loc.lower()
            if not (j.get("remote") or is_hr):
                continue  # većinom Njemačka on-site -> preskoči
            yield Job("Arbeitnow", j["title"], j.get("company_name", ""), j["url"], location=loc,
                      remote=bool(j.get("remote")), posted=_dt_epoch(j.get("created_at")),
                      tags=j.get("tags", []) + j.get("job_types", []), description=_clean(j.get("description")),
                      scope="hr" if is_hr else "remote")


def jobicy():
    for tag in ("developer", "junior", "intern"):
        data = _get("https://jobicy.com/api/v2/remote-jobs", params={"count": 50, "tag": tag}).json()
        for j in data.get("jobs", []):
            yield Job("Jobicy", _clean(j["jobTitle"], 200), j.get("companyName", ""), j["url"],
                      location=j.get("jobGeo", ""), remote=True, posted=_dt_iso(j.get("pubDate")),
                      tags=[str(j.get("jobLevel", ""))] + list(j.get("jobIndustry") or []) + list(j.get("jobType") or []),
                      description=_clean(j.get("jobExcerpt") or j.get("jobDescription")))


def himalayas():
    for q in ("developer", "software engineer", "intern"):
        data = _get("https://himalayas.app/jobs/api/search",
                    params={"q": q, "seniority": "Entry-level", "sort": "recent"}).json()
        for j in data.get("jobs", []):
            restr = j.get("locationRestrictions") or []
            yield Job("Himalayas", j["title"], j.get("companyName", ""), j.get("applicationLink") or j.get("guid", ""),
                      location=", ".join(restr) or "Anywhere", remote=True, posted=_dt_epoch(j.get("pubDate")),
                      tags=list(j.get("seniority") or []) + list(j.get("categories") or [])[:5],
                      description=_clean(j.get("excerpt") or j.get("description")))


def weworkremotely():
    r = _get("https://weworkremotely.com/categories/remote-programming-jobs.rss")
    root = ET.fromstring(r.content)
    for it in root.iter("item"):
        title = it.findtext("title", "")
        company, _, pos = title.partition(":")
        posted = None
        try:
            posted = parsedate_to_datetime(it.findtext("pubDate", ""))
        except (TypeError, ValueError):
            pass
        yield Job("WeWorkRemotely", (pos or title).strip(), company.strip() if pos else "",
                  it.findtext("link", ""), location=it.findtext("region", "") or "Remote", remote=True,
                  posted=posted, description=_clean(it.findtext("description", "")))


# ---------------- Hrvatski izvori ----------------

def posao_hr():
    """Posao.hr službeni RSS za djelatnost 'Informatika i telekomunikacije'."""
    r = _get("https://www.posao.hr/rss/djelatnost/informatika-i-telekomunikacije/")
    root = ET.fromstring(r.content)
    for it in root.iter("item"):
        desc = it.findtext("description", "")
        company = re.search(r"Poslodavac:\s*([^<]+)", desc)
        place = re.search(r"Mjesto rada:\s*([^<]+)", desc)
        loc = place.group(1).strip() if place else "Hrvatska"
        if FOREIGN_RE.search(loc) and "remote" not in loc.lower():
            continue
        try:
            posted = parsedate_to_datetime(it.findtext("pubDate", ""))
        except (TypeError, ValueError):
            posted = None
        yield Job("Posao.hr", it.findtext("title", "").strip(), company.group(1).strip() if company else "",
                  it.findtext("link", ""), location=loc, remote="remote" in loc.lower(), posted=posted,
                  description=_clean(desc), scope="hr")


def mojposao_hr():
    """MojPosao.hr – javni (nedokumentirani) JSON endpoint koji koristi njihova web stranica.
    Može se promijeniti bez najave; tada se izvor samo preskoči."""
    seen = set()
    for q in HR_QUERIES:
        data = _get("https://mojposao.hr/api/proxy/jobs/search", params={"query": q}).json()
        for group in data.get("items", []):
            org = group.get("organization")
            company = org.get("name", "") if isinstance(org, dict) else "Anonimni poslodavac"
            for j in group.get("jobs", []):
                if j["id"] in seen:
                    continue
                seen.add(j["id"])
                url = j.get("externalDetailsUrl") or f"https://www.mojposao.hr/posao/{j['id']}/{j.get('slug', '')}"
                loc = j.get("location") or "Hrvatska"
                if FOREIGN_RE.search(loc) and "remote" not in loc.lower():
                    continue
                yield Job("MojPosao.hr", j["title"], company, url, location=loc,
                          remote="remote" in loc.lower() or "rad od kuće" in loc.lower(),
                          posted=_dt_iso(j.get("publishedAt")), description=_clean(j.get("description")),
                          scope="hr")


SOURCES = {
    "remotive": remotive,
    "remoteok": remoteok,
    "arbeitnow": arbeitnow,
    "jobicy": jobicy,
    "himalayas": himalayas,
    "weworkremotely": weworkremotely,
    "posao_hr": posao_hr,
    "mojposao_hr": mojposao_hr,
}


def collect(disabled=()):
    jobs, report = [], {}
    for name, fn in SOURCES.items():
        if name in disabled:
            continue
        try:
            found = [j for j in fn() if j.title and j.url]
            jobs.extend(found)
            report[name] = len(found)
            log.info("Izvor %-15s %4d oglasa", name, len(found))
        except Exception as e:  # noqa: BLE001 – namjerno: izvor ne smije srušiti cijeli run
            report[name] = f"GREŠKA: {type(e).__name__}: {e}"[:200]
            log.warning("Izvor %s nije uspio: %s", name, e)
    return jobs, report
