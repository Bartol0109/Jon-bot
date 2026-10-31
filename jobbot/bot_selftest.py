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
    s = Settings()
    reply, updated, action = handle_command("/dodaj data analyst", s, roles, cities)
    check(updated is s and "data analyst" in s.role_keywords, reply)
    check(action is None, "dodaj ne smije pokrenuti pretragu")
    reply, updated, _ = handle_command("/dodaj data analyst", s, roles, cities)
    check(updated is None and "već" in reply, reply)
    reply, updated, _ = handle_command("/makni QA", s, roles, cities)
    check(updated is s and not any(x.casefold() == "qa" for x in s.role_keywords), reply)
    reply, updated, _ = handle_command("/grad Šibenik", s, roles, cities)
    check("Šibenik" in s.onsite_cities, reply)
    reply, updated, _ = handle_command("/maknigrad Zagreb", s, roles, cities)
    check("Zagreb" not in s.onsite_cities and "Zadar" in s.onsite_cities, reply)
    reply, _, action = handle_command("/poslovi", s, roles, cities)
    check(action == "search" and "Tražim" in reply, reply)
    reply, updated, _ = handle_command("/reset", s, roles, cities)
    check(s.role_keywords is None and s.onsite_cities is None, reply)
    text = format_settings_message(Settings(role_keywords=["qa"], onsite_cities=["Zadar"]), roles, cities)
    parsed = parse_settings_text(text)
    check(parsed.role_keywords == ["qa"] and parsed.onsite_cities == ["Zadar"], text)
    check(parse_settings_text("običan tekst") is None, "bez markera")
    reply, updated, _ = handle_command("/start", Settings(), roles, cities)
    check(updated is not None and "Bok" in reply, "start prikvači postavke")
    reply, _, _ = handle_command("/nepostoji", s, roles, cities)
    check("pomoc" in reply, reply)


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


def main():
    test_commands()
    test_webhook()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_github_env(os.path.join(tmp, "env"))
    print("bot selftest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
