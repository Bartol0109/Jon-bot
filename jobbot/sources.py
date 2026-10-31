"""Izvori oglasa. Svaki izvor je izoliran: greška u jednom ne ruši ostale."""
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from . import config
from .models import Job

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (compatible; job-bot/1.0; personal use)",
      "Accept": "application/json, text/html, application/rss+xml;q=0.9, */*;q=0.8"}
TIMEOUT = 25

# Besplatni Remotive feed trenutno često ignorira category i vrati mali mješoviti skup.
# Više kategorija ostaje da, kad API opet filtrira, uđu i podrška / DevOps / QA.
REMOTIVE_CATEGORIES = ("software-dev", "customer-support", "devops", "qa")
JOBICY_TAGS = ("developer", "junior", "intern", "data", "analyst", "devops", "support")
HIMALAYAS_QUERIES = (
    "developer", "software engineer", "intern",
    "data analyst", "business analyst", "qa", "it support",
    "technical support", "helpdesk", "devops",
)
WWR_FEEDS = (
    "remote-programming-jobs",
    "remote-devops-sysadmin-jobs",
    "remote-customer-support-jobs",
)
# Hrvatski portali objavljuju i poslove u inozemstvu – njih preskačemo (osim ako su remote)
FOREIGN_RE = re.compile(r"inozem|njemačk|austrij|turska|irsk|sloven|švicarsk|nizozem|belgij|franc|ital|"
                        r"švedsk|norvešk|dansk|češk|slovačk|mađarsk|poljsk|bosn|bih|srbij|crna gora|"
                        r"makedonij|ujedinjen|uk\b|usa|sad\b|kanad|dubai|uae|katar|malta|cipar", re.I)
HR_QUERIES = [
    "developer", "programer", "software", "junior", "praksa", "student", "frontend", "backend",
    "analitičar", "data analyst", "business analyst", "tester", "qa",
    "tehnička podrška", "helpdesk", "devops", "sistemski administrator",
]


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
    seen = set()
    for cat in REMOTIVE_CATEGORIES:
        try:
            data = _get("https://remotive.com/api/remote-jobs", params={"category": cat}).json()
        except Exception as e:  # noqa: BLE001
            log.warning("Remotive kategorija %s: %s", cat, e)
            continue
        for j in data.get("jobs", []):
            url = j.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            yield Job("Remotive", j["title"], j.get("company_name", ""), url,
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
    seen = set()
    for tag in JOBICY_TAGS:
        try:
            data = _get("https://jobicy.com/api/v2/remote-jobs", params={"count": 50, "tag": tag}).json()
        except Exception as e:  # noqa: BLE001 – jedan tag (npr. 400) ne gasi ostale
            log.warning("Jobicy tag %s: %s", tag, e)
            continue
        for j in data.get("jobs", []):
            url = j.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            yield Job("Jobicy", _clean(j["jobTitle"], 200), j.get("companyName", ""), url,
                      location=j.get("jobGeo", ""), remote=True, posted=_dt_iso(j.get("pubDate")),
                      tags=[str(j.get("jobLevel", ""))] + list(j.get("jobIndustry") or []) + list(j.get("jobType") or []),
                      description=_clean(j.get("jobExcerpt") or j.get("jobDescription")))


def himalayas():
    seen = set()
    for q in HIMALAYAS_QUERIES:
        try:
            data = _get("https://himalayas.app/jobs/api/search",
                        params={"q": q, "seniority": "Entry-level", "sort": "recent"}).json()
        except Exception as e:  # noqa: BLE001
            log.warning("Himalayas upit %s: %s", q, e)
            continue
        for j in data.get("jobs", []):
            url = j.get("applicationLink") or j.get("guid", "")
            if not url or url in seen:
                continue
            seen.add(url)
            restr = j.get("locationRestrictions") or []
            yield Job("Himalayas", j["title"], j.get("companyName", ""), url,
                      location=", ".join(restr) or "Anywhere", remote=True, posted=_dt_epoch(j.get("pubDate")),
                      tags=list(j.get("seniority") or []) + list(j.get("categories") or [])[:5],
                      description=_clean(j.get("excerpt") or j.get("description")))


def _wwr_feed(slug):
    r = _get(f"https://weworkremotely.com/categories/{slug}.rss")
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


def weworkremotely():
    seen = set()
    for slug in WWR_FEEDS:
        try:
            for job in _wwr_feed(slug):
                if not job.url or job.url in seen:
                    continue
                seen.add(job.url)
                yield job
        except Exception as e:  # noqa: BLE001
            log.warning("WeWorkRemotely %s: %s", slug, e)


# ---------------- Hrvatski izvori ----------------

def posao_hr():
    """Posao.hr službeni RSS za djelatnost 'Informatika i telekomunikacije'.

    URL-ovi tipa /rss/grad/zadar/ nisu filter po gradu (vraćaju opći feed).
    Zagreb i Zadar se čitaju iz mjesta rada; on-site izvan tih gradova kasnije otpada.
    """
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
    # Upit samo s imenom grada vrati oglase koje rolni upit (često prva stranica Zagreba) preskoči.
    queries = list(HR_QUERIES)
    seen_q = {q.casefold() for q in queries}
    for city in config.ONSITE_CITIES:
        if city.casefold() not in seen_q:
            queries.append(city)
            seen_q.add(city.casefold())
    for q in queries:
        try:
            data = _get("https://mojposao.hr/api/proxy/jobs/search", params={"query": q}).json()
        except Exception as e:  # noqa: BLE001
            log.warning("MojPosao upit %s: %s", q, e)
            continue
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
