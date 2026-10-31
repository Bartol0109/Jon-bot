"""Filtriranje: keyword heuristika + (opcionalno) LLM rangiranje preko OpenAI-kompatibilnog API-ja."""
import json
import logging
import re

import requests

from . import config
from .models import Job

log = logging.getLogger(__name__)

DEV = r"develop|programer|programmer|software|engineer|inženjer|frontend|front-end|backend|back-end|full[- ]?stack|" \
      r"python|java|javascript|typescript|react|node|\.net|c#|c\+\+|php|golang|rust|kotlin|swift|android|ios|" \
      r"web|data|devops|cloud|qa\b|tester|testing|it support|machine learning|\bml\b|\bai\b|mobile|coding|razvoj"
ENTRY = r"junior|\bjr\b|intern|internship|trainee|student|graduate|entry[- ]level|entry|apprentice|werkstudent|" \
        r"praksa|pripravnik|stručno osposobljavanje|studentski|početni|bez iskustva|no experience|early career|new grad"
SENIOR = r"senior|\bsr\b|lead|principal|staff|head of|director|architect|manager|\bmid\b|medior|expert|" \
         r"\b[5-9]\+? ?years|\b1[0-9]\+? ?years|vp\b"
NOT_DEV = r"sales|prodaj|customer service|support representative|recruit|marketing|account(ant|ing)|hr\b|" \
          r"speaking customer|call cent|business developer|nurse|driver"
EXPERIENCE = r"\b([2-9]|1[0-9])\+?\s*(-\s*\d+\s*)?(years|yrs|godin[ae])|minimum of [2-9]|at least [2-9]|najmanje [2-9]"
OPEN_LOC = r"anywhere|worldwide|global|europe|\beu\b|emea|croatia|hrvatska|cet|remote$|^remote|^$"

DEV_RE, ENTRY_RE, SENIOR_RE, NOT_DEV_RE, EXP_RE, OPEN_LOC_RE = (
    re.compile(p, re.I) for p in (DEV, ENTRY, SENIOR, NOT_DEV, EXPERIENCE, OPEN_LOC))


def location_ok(job: Job) -> bool:
    if job.scope == "hr":
        return True
    loc = (job.location or "").strip()
    return bool(OPEN_LOC_RE.search(loc))


def prefilter(jobs):
    """Grubi filter: programerski, nije senior, lokacija dostupna iz HR."""
    out = []
    for j in jobs:
        text = f"{j.title} {' '.join(map(str, j.tags))}"
        if not DEV_RE.search(text) or SENIOR_RE.search(j.title) or NOT_DEV_RE.search(j.title):
            continue
        if not location_ok(j):
            continue
        out.append(j)
    return out


def keyword_rank(jobs, limit):
    """Bez LLM-a: prvo oglasi s jasnim junior/student signalom, a ako ih je malo,
    dopuni ne-senior oglasima koji u opisu ne traže više godina iskustva."""
    entry, neutral = [], []
    for j in jobs:
        title_tags = f"{j.title} {' '.join(map(str, j.tags))}"
        bonus = (2 if j.scope == "hr" else 0) + (1 if re.search(r"anywhere|worldwide|europe|croatia|hrvatska",
                                                                 j.location or "", re.I) else 0)
        if ENTRY_RE.search(j.title):
            j.score, j.reason = 5 + bonus, "Oglas je eksplicitno za juniore/studente/praksu."
            entry.append(j)
        elif ENTRY_RE.search(title_tags):
            j.score, j.reason = 4 + bonus, "Oznake oglasa upućuju na početnu razinu."
            entry.append(j)
        elif DEV_RE.search(j.title) and not EXP_RE.search(j.description):
            j.score = 1 + bonus + (1 if ENTRY_RE.search(j.description) else 0)
            j.reason = "Nije označen kao senior i ne traži godine iskustva – provjeri uvjete."
            neutral.append(j)
        if j.scope == "hr" and j.reason:
            j.reason += " Posao u Hrvatskoj."
    key = lambda x: (x.score, x.posted.timestamp() if x.posted else 0)  # noqa: E731
    entry.sort(key=key, reverse=True)
    neutral.sort(key=key, reverse=True)
    picked = entry if len(entry) >= 3 else entry + neutral[: max(0, min(5, limit) - len(entry))]
    return balance(picked, limit)


def balance(jobs, limit):
    """Pobrini se da i hrvatski oglasi dođu na red (ako ih ima)."""
    take_hr = [j for j in jobs if j.scope == "hr"][: max(2, limit // 3)]
    rest = [j for j in jobs if j not in take_hr][: limit - len(take_hr)]
    return sorted(take_hr + rest, key=lambda x: x.score, reverse=True)


PROMPT = """Ti si asistent koji odabire oglase za posao.
Kriteriji korisnika: {criteria}

Ispod je JSON lista oglasa (id, naslov, tvrtka, lokacija, izvor, oznake, opis).
Ocijeni svaki oglas 0-10 prema kriterijima. Kandidat je student BEZ iskustva: oglasi koji traže
više godina iskustva ili senior razinu dobivaju nisku ocjenu. Remote oglasi moraju biti dostupni
nekome iz Hrvatske (EU). Vrati najviše {limit} najboljih s ocjenom >= 6.

Odgovori ISKLJUČIVO JSON-om oblika:
{{"picks": [{{"id": <int>, "score": <0-10>, "reason": "<jedna kratka rečenica na hrvatskom>"}}]}}

Oglasi:
{jobs}"""


def llm_rank(jobs, limit):
    items = [{"id": i, "title": j.title, "company": j.company, "location": j.location or ("Remote" if j.remote else ""),
              "source": j.source, "tags": [str(t) for t in j.tags][:8], "desc": j.description[:350]}
             for i, j in enumerate(jobs)]
    body = {
        "model": config.LLM_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "Odgovaraš samo valjanim JSON-om."},
            {"role": "user", "content": PROMPT.format(criteria=config.JOB_CRITERIA, limit=limit,
                                                      jobs=json.dumps(items, ensure_ascii=False))},
        ],
        "response_format": {"type": "json_object"},
    }
    r = requests.post(f"{config.LLM_BASE_URL}/chat/completions", json=body, timeout=120,
                      headers={"Authorization": f"Bearer {config.LLM_API_KEY}"})
    if r.status_code == 400 and "response_format" in r.text:   # neki provideri to ne podržavaju
        body.pop("response_format")
        r = requests.post(f"{config.LLM_BASE_URL}/chat/completions", json=body, timeout=120,
                          headers={"Authorization": f"Bearer {config.LLM_API_KEY}"})
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    picks = json.loads(m.group(0) if m else content).get("picks", [])
    out = []
    for p in picks:
        try:
            j = jobs[int(p["id"])]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        j.score = float(p.get("score", 0))
        j.reason = str(p.get("reason", "")).strip()
        if j.score >= 6 and j not in out:
            out.append(j)
    out.sort(key=lambda x: x.score, reverse=True)
    return out[:limit]


def rank(jobs, limit):
    cands = prefilter(jobs)
    log.info("Nakon predfiltera: %d kandidata", len(cands))
    if config.LLM_API_KEY and cands:
        # Kandidati s junior signalom idu prvi, max 80 da prompt ostane malen/jeftin
        cands.sort(key=lambda j: (bool(ENTRY_RE.search(f"{j.title} {' '.join(map(str, j.tags))}")), j.scope == "hr"),
                   reverse=True)
        try:
            return llm_rank(cands[:80], limit), "llm"
        except Exception as e:  # noqa: BLE001
            log.warning("LLM rangiranje nije uspjelo (%s) – koristim keyword filter", e)
    return keyword_rank(cands, limit), "keywords"
