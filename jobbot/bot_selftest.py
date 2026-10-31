"""Lokalna provjera naredbi i webhooka, bez Telegrama i bez pretrage."""
import os
import sys

os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
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
    s = Settings()
    reply, updated, action = handle_command("/dodaj data analyst", s, roles, cities, excluded)
    check(updated is s and "data analyst" in s.role_keywords, reply)
    check(action is None, "dodaj ne smije pokrenuti pretragu")
    reply, updated, _ = handle_command("/dodaj data analyst", s, roles, cities, excluded)
    check(updated is None and "već" in reply, reply)
    reply, updated, _ = handle_command("/makni QA", s, roles, cities, excluded)
    check(updated is s and not any(x.casefold() == "qa" for x in s.role_keywords), reply)
    reply, updated, _ = handle_command("/grad Šibenik", s, roles, cities, excluded)
    check("Šibenik" in s.onsite_cities, reply)
    reply, updated, _ = handle_command("/maknigrad Zagreb", s, roles, cities, excluded)
    check("Zagreb" not in s.onsite_cities and "Zadar" in s.onsite_cities, reply)
    reply, updated, _ = handle_command("/iskljuci pcb", s, roles, cities, excluded)
    check(updated is s and "pcb" in s.exclude_keywords and "hardware" in s.exclude_keywords, reply)
    reply, updated, _ = handle_command("/ukljuci hardware", s, roles, cities, excluded)
    check(updated is s and not any(x.casefold() == "hardware" for x in s.exclude_keywords), reply)
    reply, _, action = handle_command("/poslovi", s, roles, cities, excluded)
    check(action == "search" and "Tražim" in reply, reply)
    reply, _, action = handle_command("/mjesec", s, roles, cities, excluded)
    check(action == "search_month" and "30" in reply, reply)
    reply, updated, _ = handle_command("/remote", s, roles, cities, excluded)
    check(updated is None and "uključen" in reply, reply)
    reply, updated, _ = handle_command("/remote off", s, roles, cities, excluded)
    check(updated is s and s.allow_remote is False and "isključeni" in reply, reply)
    reply, updated, _ = handle_command("/bezremote", s, roles, cities, excluded)
    check(s.allow_remote is False, reply)
    reply, updated, _ = handle_command("/remote on", s, roles, cities, excluded)
    check(s.allow_remote is True and "uključeni" in reply, reply)
    reply, updated, _ = handle_command("/reset", s, roles, cities, excluded)
    check(s.role_keywords is None and s.onsite_cities is None and s.exclude_keywords is None, reply)
    check(s.allow_remote is None, "reset remote")
    text = format_settings_message(
        Settings(role_keywords=["qa"], onsite_cities=["Zadar"], exclude_keywords=["fpga"]),
        roles, cities, excluded,
    )
    parsed = parse_settings_text(text)
    check(parsed.role_keywords == ["qa"] and parsed.onsite_cities == ["Zadar"], text)
    check(parsed.exclude_keywords == ["fpga"], text)
    off_text = format_settings_message(Settings(allow_remote=False), roles, cities, excluded)
    check(parse_settings_text(off_text).allow_remote is False, off_text)
    old_pin = 'JOBBOT_SETTINGS={"v":1,"role_keywords":null,"onsite_cities":null}'
    check(parse_settings_text(old_pin).allow_remote is None, "stari pin")
    check("Isključeno" in text, text)
    check(parse_settings_text("običan tekst") is None, "bez markera")
    reply, updated, _ = handle_command("/start", Settings(), roles, cities, excluded)
    check(updated is not None and "Bok" in reply, "start prikvači postavke")
    reply, _, _ = handle_command("/nepostoji", s, roles, cities, excluded)
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
    test_webhook()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_github_env(os.path.join(tmp, "env"))
    print("bot selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
