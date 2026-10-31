"""Job bot: jednom dnevno skupi svježe početne tehnološke oglase (programiranje, analitika, QA, IT podrška, DevOps…) i pošalje ih na WhatsApp/Telegram.

  python main.py                 # jedan run (Railway Cron) – ili scheduler ako je RUN_MODE=scheduler
  python main.py --dry-run       # samo ispiše poruke, ništa ne šalje i ne pamti
  python main.py --test-whatsapp # pošalje testnu poruku preko odabranog SENDER-a
"""
import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jobbot import config
from jobbot.formatter import build_messages
from jobbot.ranking import rank
from jobbot.senders import get_sender
from jobbot.sources import collect
from jobbot.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
log = logging.getLogger("job-bot")


def run_once(dry_run=False, sender_name=None, mark=True):
    sender = get_sender(sender_name)
    if not dry_run:
        sender.check()
    jobs, report = collect(config.DISABLED_SOURCES)

    # 1) svježina (fallback dedupe po datumu)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.MAX_AGE_HOURS)
    fresh = [j for j in jobs if j.posted is None or j.posted >= cutoff]
    # 2) dedupe unutar runa
    uniq, seen_tc = {}, set()
    for j in fresh:
        tc = (j.title.lower().strip(), j.company.lower().strip())
        if j.key not in uniq and tc not in seen_tc:
            uniq[j.key] = j
            seen_tc.add(tc)
    fresh = list(uniq.values())
    # 3) dedupe naspram već poslanih
    store = Store()
    fresh = [j for j in fresh if not store.is_seen(j.key)]
    log.info("Ukupno %d oglasa, svježih i neposlanih: %d (prozor %dh, trajna pohrana: %s)",
             len(jobs), len(fresh), config.MAX_AGE_HOURS, config.PERSISTENT)

    picked, mode = rank(fresh, config.MAX_RESULTS)
    messages = build_messages(picked, sender, mode)

    if dry_run:
        print("\n===== DRY RUN – izvori =====")
        for k, v in report.items():
            print(f"  {k:15} {v}")
        print(f"===== DRY RUN – {len(messages)} poruka(e) za '{sender.name}' (način: {mode}) =====")
        for m in messages:
            print(m)
            print("-" * 60)
        return
    sender.send_all(messages)
    if mark:
        store.mark(picked)
    log.info("Gotovo: poslano %d oglasa u %d poruka.", len(picked), len(messages))


def scheduler(dry_run=False, sender_name=None):
    tz = ZoneInfo(config.TZ)
    hh, mm = map(int, config.RUN_AT.split(":"))
    log.info("Scheduler mod: svaki dan u %02d:%02d (%s)", hh, mm, config.TZ)
    while True:
        now = datetime.now(tz)
        nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        log.info("Sljedeći run: %s", nxt.isoformat())
        while datetime.now(tz) < nxt:  # spavaj u komadima (otporno na DST i suspend)
            time.sleep(min(300, max(1, (nxt - datetime.now(tz)).total_seconds())))
        try:
            run_once(dry_run, sender_name)
        except Exception:  # noqa: BLE001
            log.exception("Run nije uspio – pokušavam opet sutra")


def main():
    ap = argparse.ArgumentParser(description="Dnevni job bot")
    ap.add_argument("--dry-run", action="store_true", help="ispiši poruke umjesto slanja")
    ap.add_argument("--test-whatsapp", action="store_true", help="pošalji testnu poruku (preko SENDER-a)")
    ap.add_argument("--sender", choices=["callmebot", "twilio", "telegram"], help="nadjačaj SENDER env varijablu")
    ap.add_argument("--mode", choices=["cron", "scheduler"], help="nadjačaj RUN_MODE")
    ap.add_argument("--telegram-chat-id", action="store_true", help="ispiši chat ID-eve iz zadnjih poruka botu")
    a = ap.parse_args()

    if a.telegram_chat_id:
        import requests
        if not config.TELEGRAM_BOT_TOKEN:
            raise SystemExit("Postavi TELEGRAM_BOT_TOKEN pa pošalji botu bilo koju poruku.")
        upd = requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates", timeout=30).json()
        chats = {(u.get("message") or u.get("channel_post") or {}).get("chat", {}).get("id"): u for u in upd.get("result", [])}
        for cid, u in chats.items():
            if cid:
                c = (u.get("message") or u.get("channel_post"))["chat"]
                print(f"TELEGRAM_CHAT_ID={cid}  ({c.get('first_name') or c.get('title', '')})")
        if not any(chats):
            print("Nema poruka – otvori svog bota u Telegramu, pošalji mu 'bok' i pokreni ponovno.")
        return

    if a.test_whatsapp:
        s = get_sender(a.sender)
        s.check()
        s.send_one(f"✅ Job bot test ({s.name}) – {datetime.now(ZoneInfo(config.TZ)):%d.%m.%Y. %H:%M}. Ako ovo vidiš, slanje radi!")
        log.info("Testna poruka poslana preko %s", s.name)
        return

    if (a.mode or config.RUN_MODE) == "scheduler":
        return scheduler(a.dry_run, a.sender)

    if config.ONLY_AT_LOCAL_HOUR and not a.dry_run:
        h = datetime.now(ZoneInfo(config.TZ)).hour
        if h != int(config.ONLY_AT_LOCAL_HOUR):
            log.info("Sada je %d h po %s, a ONLY_AT_LOCAL_HOUR=%s – preskačem (DST zaštita).",
                     h, config.TZ, config.ONLY_AT_LOCAL_HOUR)
            return
    run_once(a.dry_run, a.sender)


if __name__ == "__main__":
    main()
