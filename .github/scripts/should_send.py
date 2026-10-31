"""Jednom dnevno, u podne po Europe/Zagreb — i kad GitHub odgodi cron.

GitHubov `schedule` je u UTC-u i run zna kasniti satima. Provjera „je li točno 12 h“
(ONLY_AT_LOCAL_HOUR) tada preskoči cijeli dan. Ova skripta umjesto toga:

- šalje ako za današnji zagrebački datum još nije poslano i lokalno je 12:00 ili kasnije
  (odgođeni popodnevni run i dalje pošalje, drugi run isti dan ne);
- ako je cijeli prethodni dan propušten, a run stigne prije podneva, pošalje nadoknadu
  i zabilježi jučerašnji datum — današnje podne i dalje ide;
- inače prije 12:00 ne šalje.

Izlaz je uvijek 0. Za `schedule` upisuje `send` i `record_date` u `$GITHUB_OUTPUT`.
`--stamp` nakon uspješnog slanja zapiše taj datum u `data/last_sent_local_date.txt`.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Zagreb")
NOON_HOUR = 12


def state_path() -> Path:
    return Path(os.environ.get("DATA_DIR", "data")) / "last_sent_local_date.txt"


def load_last(path: Path):
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        print(f"Neispravan datum u {path}: {text!r} — tretiram kao da nije poslano.")
        return None


def decide(now: datetime, last):
    """Vrati (slati, datum za zapis ili None, poruka za log)."""
    if now.tzinfo is None:
        raise ValueError("now mora imati vremensku zonu")
    today = now.date()
    yesterday = today - timedelta(days=1)
    if last == today:
        return False, None, f"Već poslano za {today} (lokalno {now:%H:%M}). Preskačem."
    if now.hour < NOON_HOUR:
        if last is not None and last < yesterday:
            return True, yesterday.isoformat(), (
                f"Nadoknada: zadnje slanje {last}, a lokalno je {now:%Y-%m-%d %H:%M} (prije 12:00). "
                f"Šaljem propušteni dan {yesterday.isoformat()} da današnje podne i dalje ode."
            )
        return False, None, (
            f"Lokalno je {now:%Y-%m-%d %H:%M}, još nije 12:00, a propuštenog dana nema "
            f"(zadnje: {last or 'nikad'}). Preskačem."
        )
    return True, today.isoformat(), (
        f"Šaljem dnevne oglase za {today} (lokalno {now:%H:%M}, zadnje: {last or 'nikad'})."
    )


def write_output(send: bool, record_date: str | None) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with open(output, "a", encoding="utf-8") as fh:
        fh.write(f"send={'true' if send else 'false'}\n")
        fh.write(f"record_date={record_date or ''}\n")


def stamp() -> str:
    raw = os.environ.get("RECORD_DATE", "").strip()
    if raw:
        datetime.strptime(raw, "%Y-%m-%d")
        day = raw
    else:
        day = datetime.now(TZ).date().isoformat()
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(day + "\n", encoding="utf-8")
    print(f"Zabilježen lokalni dan {day} u {path}")
    return day


def evaluate():
    now = datetime.now(TZ)
    last = load_last(state_path())
    return decide(now, last)


def self_test() -> int:
    def at(y, m, d, hh, mm):
        return datetime(y, m, d, hh, mm, tzinfo=TZ)

    cases = []

    def check(now, last, send, record, label):
        got_send, got_record, message = decide(now, last)
        if got_send != send or got_record != record:
            cases.append(f"FAIL {label}: send={got_send} record={got_record} ({message})")
        else:
            cases.append(f"ok   {label}")

    # Zima (CET, UTC+1): 12:00 Zagreb = 11:00 UTC. 10:05 UTC je još 11:05.
    winter_before = at(2026, 1, 15, 11, 5)
    winter_noon = at(2026, 1, 15, 12, 5)
    assert winter_before.utcoffset() == timedelta(hours=1)
    assert winter_noon.utcoffset() == timedelta(hours=1)
    check(at(2026, 1, 15, 11, 59), None, False, None, "11:59 ne šalje")
    check(at(2026, 1, 15, 12, 0), None, True, "2026-01-15", "točno 12:00 šalje")
    check(winter_before, None, False, None, "zima prije podne, nikad poslano")
    check(winter_before, winter_before.date() - timedelta(days=1), False, None, "zima prije podne, jučer poslano")
    check(winter_noon, winter_noon.date() - timedelta(days=1), True, "2026-01-15", "zima u podne")
    check(at(2026, 1, 15, 17, 0), winter_noon.date() - timedelta(days=1), True, "2026-01-15", "zima odgoda do 17 h")
    check(at(2026, 1, 15, 17, 0), winter_noon.date(), False, None, "zima drugi run isti dan")

    # Ljeto (CEST, UTC+2): 12:00 Zagreb = 10:00 UTC. 11:00 UTC je već 13:00 — i dalje šalje ako nije.
    summer_noon = at(2026, 7, 15, 12, 5)
    assert summer_noon.utcoffset() == timedelta(hours=2)
    check(summer_noon, summer_noon.date() - timedelta(days=1), True, "2026-07-15", "ljeto u podne")
    check(at(2026, 7, 15, 13, 30), summer_noon.date() - timedelta(days=1), True, "2026-07-15", "ljeto odgoda, sat nije 12")
    check(at(2026, 7, 15, 13, 30), summer_noon.date(), False, None, "ljeto drugi UTC sat isti dan")
    check(at(2026, 7, 15, 11, 5), None, False, None, "ljeto prije podne")

    # Prijelazi (2026.): 29.3. ljetno računanje, 25.10. zimsko. Podne postoji točno jednom.
    spring = at(2026, 3, 29, 12, 0)
    autumn = at(2026, 10, 25, 12, 0)
    assert spring.utcoffset() == timedelta(hours=2), spring.utcoffset()
    assert autumn.utcoffset() == timedelta(hours=1), autumn.utcoffset()
    check(spring, spring.date() - timedelta(days=1), True, "2026-03-29", "prelazak na ljetno")
    check(autumn, autumn.date() - timedelta(days=1), True, "2026-10-25", "prelazak na zimsko")

    # Cijeli dan propušten: jutarnji run nadoknadi jučer, ne današnji datum.
    missed = at(2026, 1, 16, 11, 5)
    check(missed, missed.date() - timedelta(days=2), True, "2026-01-15", "nadoknada prije podne")
    check(at(2026, 1, 16, 12, 5), missed.date() - timedelta(days=1), True, "2026-01-16", "podne nakon nadoknade")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "last_sent_local_date.txt"
        if load_last(path) is not None:
            cases.append("FAIL load_last missing")
        else:
            cases.append("ok   load_last missing")
        path.write_text("nope\n", encoding="utf-8")
        if load_last(path) is not None:
            cases.append("FAIL load_last corrupt")
        else:
            cases.append("ok   load_last corrupt")
        path.write_text("2026-01-15\n", encoding="utf-8")
        loaded = load_last(path)
        if loaded is None or loaded.isoformat() != "2026-01-15":
            cases.append("FAIL load_last date")
        else:
            cases.append("ok   load_last date")

        old = {k: os.environ.get(k) for k in ("DATA_DIR", "RECORD_DATE", "GITHUB_OUTPUT")}
        try:
            os.environ["DATA_DIR"] = tmp
            os.environ["RECORD_DATE"] = "2026-04-01"
            out = Path(tmp) / "outputs.txt"
            os.environ["GITHUB_OUTPUT"] = str(out)
            if stamp() != "2026-04-01" or path.read_text(encoding="utf-8").strip() != "2026-04-01":
                cases.append("FAIL stamp")
            else:
                cases.append("ok   stamp")
            write_output(True, "2026-04-01")
            text = out.read_text(encoding="utf-8")
            if "send=true\n" not in text or "record_date=2026-04-01\n" not in text:
                cases.append(f"FAIL output {text!r}")
            else:
                cases.append("ok   output")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    failed = [line for line in cases if line.startswith("FAIL")]
    print("\n".join(cases))
    if failed:
        print(f"{len(failed)} provjera palo")
        return 1
    print(f"{len(cases)} provjera prošlo")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if "--stamp" in argv:
        stamp()
        return 0
    send, record_date, message = evaluate()
    print(message)
    write_output(send, record_date)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
