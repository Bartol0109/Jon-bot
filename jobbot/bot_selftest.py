"""Lokalna provjera naredbi i webhooka, bez Telegrama i bez pretrage."""
import os
import sys

os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("CRON_SECRET", "cronSecret123")
os.environ.setdefault("TELEGRAM_CHAT_ID", "42")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:test")

from fastapi.testclient import TestClient  # noqa: E402

from jobbot.bot_commands import handle_command  # noqa: E402
from jobbot.settings_store import Settings, format_settings_message, parse_settings_text  # noqa: E402
import webapp  # noqa: E402


def check(cond, msg):
    if not cond:
        raise SystemExit(f"FAIL {msg}")


def test_commands():
    roles = ["developer", "qa"]
    cities = ["Zagreb", "Zadar"]
    excluded = ["hardware", "firmware"]
    narrow = ["react", "unity"]
    s = Settings()
    reply, updated, action = handle_command("/dodaj data analyst", s, roles, cities, excluded, narrow)
    check(updated is s and "data analyst" in s.role_keywords, reply)
    check(action is None, "dodaj ne smije pokrenuti pretragu")
    reply, updated, _ = handle_command("/dodaj data analyst", s, roles, cities, excluded, narrow)
    check(updated is None and "već" in reply, reply)
    reply, updated, _ = handle_command("/makni QA", s, roles, cities, excluded, narrow)
    check(updated is s and not any(x.casefold() == "qa" for x in s.role_keywords), reply)
    reply, updated, _ = handle_command("/grad Šibenik", s, roles, cities, excluded, narrow)
    check("Šibenik" in s.onsite_cities, reply)
    reply, updated, _ = handle_command("/maknigrad Zagreb", s, roles, cities, excluded, narrow)
    check("Zagreb" not in s.onsite_cities and "Zadar" in s.onsite_cities, reply)
    reply, updated, _ = handle_command("/iskljuci pcb", s, roles, cities, excluded, narrow)
    check(updated is s and "pcb" in s.exclude_keywords and "hardware" in s.exclude_keywords, reply)
    reply, updated, _ = handle_command("/ukljuci hardware", s, roles, cities, excluded, narrow)
    check(updated is s and not any(x.casefold() == "hardware" for x in s.exclude_keywords), reply)
    reply, _, action = handle_command("/poslovi", s, roles, cities, excluded, narrow)
    check(action == "search" and "Tražim" in reply, reply)
    reply, _, action = handle_command("/mjesec", s, roles, cities, excluded, narrow)
    check(action == "search_month" and "30" in reply and "nisi dobio" in reply, reply)
    reply, updated, _ = handle_command("/remote", s, roles, cities, excluded, narrow)
    check(updated is None and "uključen" in reply, reply)
    reply, updated, _ = handle_command("/remote off", s, roles, cities, excluded, narrow)
    check(updated is s and s.allow_remote is False and "isključeni" in reply, reply)
    reply, updated, _ = handle_command("/bezremote", s, roles, cities, excluded, narrow)
    check(s.allow_remote is False, reply)
    reply, updated, _ = handle_command("/remote on", s, roles, cities, excluded, narrow)
    check(s.allow_remote is True and "uključeni" in reply, reply)
    reply, updated, _ = handle_command("/reset", s, roles, cities, excluded, narrow)
    check(s.role_keywords is None and s.onsite_cities is None and s.exclude_keywords is None, reply)
    check(s.allow_remote is None and s.narrow_mode is None and s.narrow_keywords is None, "reset remote")
    reply, updated, _ = handle_command("/usko", s, roles, cities, excluded, narrow)
    check(updated is None and "isključen" in reply, reply)
    reply, updated, _ = handle_command("/usko on", s, roles, cities, excluded, narrow)
    check(updated is s and s.narrow_mode is True, reply)
    reply, updated, _ = handle_command("/usko dodaj motion designer", s, roles, cities, excluded, narrow)
    check("motion designer" in s.narrow_keywords and "react" in s.narrow_keywords, reply)
    reply, updated, _ = handle_command("/usko makni unity", s, roles, cities, excluded, narrow)
    check(not any(x.casefold() == "unity" for x in s.narrow_keywords), reply)
    reply, updated, _ = handle_command("/usko off", s, roles, cities, excluded, narrow)
    check(s.narrow_mode is False and "širi" in reply, reply)
    text = format_settings_message(
        Settings(role_keywords=["qa"], onsite_cities=["Zadar"], exclude_keywords=["fpga"]),
        roles, cities, excluded, narrow,
    )
    parsed = parse_settings_text(text)
    check(parsed.role_keywords == ["qa"] and parsed.onsite_cities == ["Zadar"], text)
    check(parsed.exclude_keywords == ["fpga"], text)
    off_text = format_settings_message(Settings(allow_remote=False), roles, cities, excluded, narrow)
    check(parse_settings_text(off_text).allow_remote is False, off_text)
    old_pin = 'JOBBOT_SETTINGS={"v":1,"role_keywords":null,"onsite_cities":null}'
    check(parse_settings_text(old_pin).allow_remote is None, "stari pin")
    check("Isključeno" in text, text)
    check(parse_settings_text("običan tekst") is None, "bez markera")
    reply, updated, _ = handle_command("/start", Settings(), roles, cities, excluded, narrow)
    check(updated is not None and "Bok" in reply, "start prikvači postavke")
    reply, _, _ = handle_command("/nepostoji", s, roles, cities, excluded, narrow)
    check("pomoc" in reply, reply)


def test_language_and_exclude():
    from jobbot.models import Job
    from jobbot.ranking import english_sufficient, location_ok, prefilter

    en = (
        "We are looking for a junior developer to join our team. You will work with modern technologies "
        "and support the engineering group. We offer flexible hours and a fair salary. You should know "
        "programming basics. Apply by the end of the month and learn from experienced colleagues every day."
    )
    hr = (
        "Tražimo mlađeg inženjera koji će raditi u Zagrebu. Nudimo rad na zanimljivim projektima i mentorstvo. "
        "Kandidat treba poznavati osnove programiranja. Prijave primamo do kraja mjeseca. Radno vrijeme je puno. "
        "Pridruži se našem timu i uči svaki dan uz iskusne kolege na ovoj poziciji."
    )
    de = (
        "Wir suchen einen Mitarbeiter für den Kundenservice. Du beantwortest Fragen von Kunden und arbeitest "
        "im Team. Wir bieten eine Festanstellung und gute Konditionen. Bewirb dich jetzt und werde Teil unseres "
        "Unternehmens. Du arbeitest mit den Kollegen und unterstützt die Kunden jeden Tag im Büro."
    )
    nl = (
        "Wij zoeken een medewerker voor onze klantenservice. Je werkt met klanten en beantwoordt vragen. "
        "Wij bieden een leuk team en goede voorwaarden. Het werk is voor onze klanten en je bent het "
        "aanspreekpunt. Solliciteer vandaag nog op deze vacature bij ons team."
    )

    def job(title, desc, loc="Europe", remote=True, scope="remote"):
        return Job("t", title, "Co", "http://x/" + title, location=loc, remote=remote, scope=scope, description=desc)

    german_title = job("Mitarbeiter Kundenservice (m/w/d)", de)
    check(not english_sufficient(german_title), "njemački naslov")
    check(not english_sufficient(job("Customer Support (m/w/d)", en)), "(m/w/d)")
    check(not english_sufficient(job("Werkstudent Kundenbetreuer", "Join our support team today.")), "Werkstudent")
    check(not english_sufficient(job("Junior Support", en + " Fluent German is required.")), "fluent German")
    check(not english_sufficient(job("Klantenservice Medewerker", nl)), "nizozemski")
    check(english_sufficient(job("Junior Customer Support Engineer", en)), "engleski")
    check(english_sufficient(job("We serve the German market", en)), "German market nije uvjet")
    cro = job("Mlađi inženjer za podršku", hr, loc="Zagreb", remote=False, scope="hr")
    check(english_sufficient(cro) and location_ok(cro), "hrvatski Zagreb")

    kept = prefilter([
        job("Hardware Development Engineer", en, loc="Zagreb", remote=False, scope="hr"),
        job("Junior Software Engineer", en, loc="Zagreb", remote=False, scope="hr"),
        job("Elektrotehničar", hr, loc="Zadar", remote=False, scope="hr"),
        job("Firmware Engineer", en, loc="Remote"),
        cro,
    ])
    titles = [j.title for j in kept]
    check(titles == ["Junior Software Engineer", "Mlađi inženjer za podršku"], titles)

    from jobbot import config
    remote_job = job("Junior Developer", en, loc="Europe", remote=True)
    zagreb = job("Junior Software Engineer", en, loc="Zagreb", remote=False, scope="hr")
    hybrid = job("Hybrid Developer", en, loc="Zadar", remote=False, scope="hr")
    old = config.ALLOW_REMOTE
    try:
        config.ALLOW_REMOTE = False
        check(not location_ok(remote_job), "remote off")
        check(location_ok(zagreb) and location_ok(hybrid), "gradovi ostaju")
        config.ALLOW_REMOTE = True
        check(location_ok(remote_job), "remote on")
    finally:
        config.ALLOW_REMOTE = old

    old_mode = config.NARROW_MODE
    try:
        config.NARROW_MODE = True
        narrow_kept = [j.title for j in prefilter([
            job("Junior React Developer", en, loc="Zagreb", remote=False, scope="hr"),
            job("Junior Data Analyst", en, loc="Zagreb", remote=False, scope="hr"),
            job("Senior React Developer", en, loc="Zagreb", remote=False, scope="hr"),
            job("React Developer", en, loc="Split", remote=False, scope="hr"),
            job("Hardware React Engineer", en, loc="Zagreb", remote=False, scope="hr"),
        ])]
        check(narrow_kept == ["Junior React Developer"], narrow_kept)
        config.NARROW_MODE = False
        broad = [j.title for j in prefilter([
            job("Junior Data Analyst", en, loc="Zagreb", remote=False, scope="hr"),
        ])]
        check(broad == ["Junior Data Analyst"], broad)
    finally:
        config.NARROW_MODE = old_mode


def test_seen_and_cron():
    from datetime import date, timedelta

    from jobbot.formatter import EMPTY_DIGEST, build_messages
    from jobbot.models import Job
    from jobbot.seen_state import (
        MAX_BLOB,
        SeenState,
        canonical_url,
        dedupe_jobs,
        legacy_blob,
        legacy_hash,
        zagreb_today,
    )

    a = Job("remoteok", "Junior React Developer", "Acme Ltd",
            "https://www.Example.com/jobs/1/?utm_source=x&utm_medium=email#apply")
    b = Job("mojposao", "Junior React Developer (m/w/d)", "Acme d.o.o.", "https://example.com/jobs/1/")
    c = Job("posao", "Junior React Developer", "Acme", "https://other.example/jobs/999?id=3")
    d = Job("posao", "Senior React Developer", "Acme", "https://other.example/jobs/1000?id=4")
    e = Job("board", "QA Analyst", "Beta", "https://board.example/job?id=1&utm_medium=email")
    f = Job("board", "Support Analyst", "Beta", "https://board.example/job?id=2")
    check(canonical_url(a.url) == canonical_url(b.url) == "https://example.com/jobs/1", canonical_url(a.url))
    check(canonical_url(e.url) != canonical_url(f.url), "id u linku ostaje")
    kept = dedupe_jobs([a, b, c, d, e, f])
    check([j.title for j in kept] == [
        "Junior React Developer", "Senior React Developer", "QA Analyst", "Support Analyst",
    ], [j.title for j in kept])

    state = SeenState()
    state.mark_jobs([a], "2026-11-01", claim_day=True)
    check(state.already_sent_on("2026-11-01"), "dan")
    check(not state.already_sent_on("2026-11-02"), "sutra")
    check(state.seen_job(b) and state.seen_job(c), "isti oglas, drugi link ili izvor")
    check(not state.seen_job(d) and not state.seen_job(e), "drugi oglas")
    again = SeenState.unpack(state.pack())
    again.date = state.date
    check(again.seen_job(b) and again.already_sent_on("2026-11-01"), "pack")
    state.mark_jobs([d], "2026-11-02", claim_day=False)
    check(state.already_sent_on("2026-11-01") and state.seen_job(d), "ručni ne gasi dan")

    today = date(2026, 11, 1)
    aged = SeenState()
    aged.mark_jobs([a], (today - timedelta(days=91)).isoformat(), claim_day=False, max_chars=10000)
    aged.prune(today, 10000)
    check(not aged.seen_job(a), "91 dan")
    aged.mark_jobs([b], (today - timedelta(days=90)).isoformat(), claim_day=False, max_chars=10000)
    aged.prune(today, 10000)
    check(aged.seen_job(b), "90 dana")

    many = [Job("s", f"Role {i}", f"Co {i}", f"https://jobs.example/p/{i}") for i in range(400)]
    capped = SeenState()
    capped.mark_jobs(many, "2026-11-01", claim_day=False, max_chars=2800)
    check(len(capped.pack()) <= 2800, len(capped.pack()))
    check(capped.seen_job(many[-1]) and not capped.seen_job(many[0]), "granica")
    wide = SeenState()
    wide.mark_jobs(many, zagreb_today(), claim_day=True, max_chars=MAX_BLOB)
    check(len(wide.pack()) <= MAX_BLOB, len(wide.pack()))

    old = legacy_blob([legacy_hash(a.key)], "2026-11-01")
    legacy = SeenState.unpack(old)
    check(legacy.seen_job(a), "stari pin")
    raw = 'JOBBOT_SETTINGS={"v":1,"seen":["%s"],"seen_date":"2026-11-01"}' % legacy_hash(a.key)
    parsed_old = parse_settings_text(raw)
    check(parsed_old.seen_date == "2026-11-01", parsed_old.seen_date)
    check(SeenState.unpack(parsed_old.seen_blob).seen_job(a), "stari json")

    pinned = Settings(role_keywords=["qa"] * 30)
    pinned.seen_date = zagreb_today()
    pinned.seen_blob = wide.pack()
    text = format_settings_message(pinned, ["developer"], ["Zagreb"], ["hardware"], ["react"])
    check(len(text) <= 4000, len(text))
    check(text.splitlines()[-1].startswith("JOBBOT_SETTINGS="), text[-80:])
    parsed = parse_settings_text(text)
    check(parsed.role_keywords == ["qa"] * 30 and parsed.seen_date == zagreb_today(), "postavke")
    restored = SeenState.unpack(parsed.seen_blob)
    check(restored.seen_job(many[-1]) and not restored.seen_job(many[0]), "poruka čuva najnovije")

    class _Sender:
        max_len = 1000

        @staticmethod
        def bold(s):
            return s

        @staticmethod
        def esc(s):
            return s

    check(EMPTY_DIGEST in build_messages([], _Sender())[0], "prazan pregled")
    check(EMPTY_DIGEST == "Danas nema novih oglasa koji odgovaraju tvojim kriterijima.", EMPTY_DIGEST)

    import tempfile
    from pathlib import Path
    from jobbot.store import Store
    with tempfile.TemporaryDirectory() as tmp:
        db = Store(Path(tmp) / "seen.sqlite3")
        db.mark([a])
        check(db.covers(b) and db.covers(c) and not db.covers(d), "sqlite")

    calls = []
    webapp._schedule_daily = lambda: calls.append("daily")
    with TestClient(webapp.app) as client:
        r = client.get("/cron/daily")
        check(r.status_code == 401, r.text)
        r = client.get("/cron/daily?token=not-the-secret")
        check(r.status_code == 401, "krivi token")
        r = client.get("/cron/daily?token=cronSecret123")
        check(r.status_code == 200 and calls == ["daily"], r.text)
        r = client.post("/cron/daily", headers={"x-cron-token": "cronSecret123"})
        check(r.status_code == 200 and calls == ["daily", "daily"], calls)
        old = webapp.config.CRON_SECRET
        webapp.config.CRON_SECRET = "has-dash"
        r = client.get("/cron/daily?token=has-dash")
        check(r.status_code == 401, "crtica u tajni")
        webapp.config.CRON_SECRET = old


def test_webhook():
    calls = []
    webapp._schedule = calls.append
    webapp._seen_updates.clear()
    with TestClient(webapp.app) as client:
        r = client.post("/telegram/webhook", json={"update_id": 1, "message": {"text": "/pomoc", "chat": {"id": 42}}})
        check(r.status_code == 401, r.text)
        ok = {"x-telegram-bot-api-secret-token": "test-secret"}
        r = client.post("/telegram/webhook", headers=ok, json={
            "update_id": 2, "message": {"text": "/pomoc", "chat": {"id": 99}},
        })
        check(r.status_code == 200 and calls == [], "tuđi chat")
        r = client.post("/telegram/webhook", headers=ok, json={
            "update_id": 3, "message": {"text": "/postavke", "chat": {"id": "42"}},
        })
        check(r.status_code == 200 and calls == ["/postavke"], calls)
        r = client.post("/telegram/webhook", headers=ok, json={
            "update_id": 3, "message": {"text": "/poslovi", "chat": {"id": 42}},
        })
        check(calls == ["/postavke"], "dupli update_id")
        r = client.get("/health")
        check(r.status_code == 200 and r.json().get("ok") is True, r.text)
        r = client.post("/telegram/setup", headers={"x-setup-token": "nope"})
        check(r.status_code == 401, "setup")


def test_github_env(path):
    from jobbot.sync_settings import write_github_env
    write_github_env(Settings(role_keywords=["qa"], onsite_cities=["Zadar"]), path)
    text = open(path, encoding="utf-8").read()
    check("ROLE_KEYWORDS<<JOBBOT_EOF" in text and "\nqa\n" in text, text)
    check("ONSITE_CITIES<<JOBBOT_EOF" in text and "Zadar" in text, text)
    check(write_github_env(Settings(), path + ".empty") is False, "prazan pin")
    off = os.path.join(os.path.dirname(path), "off")
    write_github_env(Settings(allow_remote=False), off)
    check("ALLOW_REMOTE<<JOBBOT_EOF\n0\n" in open(off, encoding="utf-8").read(), "remote off")


def main():
    test_commands()
    test_language_and_exclude()
    test_seen_and_cron()
    test_webhook()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_github_env(os.path.join(tmp, "env"))
    print("bot selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
