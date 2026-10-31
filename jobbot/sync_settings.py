"""Učitaj prikvačene postavke i, na GitHub Actions, upiši ih u GITHUB_ENV.

Poziva se prije dnevnog slanja da /dodaj i /grad utječu na poruku u 12:00.
Ako pina nema ili Telegram ne odgovori, ostaju varijable repozitorija / zadano.
"""
import logging
import os
import sys

from .settings_store import TelegramSettingsStore

log = logging.getLogger(__name__)


def export_lines(settings):
    lines = []
    if settings.role_keywords is not None:
        lines.append(("ROLE_KEYWORDS", ",".join(settings.role_keywords)))
    if settings.onsite_cities is not None:
        lines.append(("ONSITE_CITIES", ",".join(settings.onsite_cities)))
    if settings.exclude_keywords is not None:
        value = ",".join(settings.exclude_keywords) if settings.exclude_keywords else "__NONE__"
        lines.append(("EXCLUDE_KEYWORDS", value))
    return lines


def write_github_env(settings, path):
    chunks = []
    for key, value in export_lines(settings):
        chunks.append(f"{key}<<JOBBOT_EOF\n{value}\nJOBBOT_EOF\n")
    if not chunks:
        return False
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("".join(chunks))
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    try:
        settings = TelegramSettingsStore().load()
    except Exception as exc:  # noqa: BLE001
        print(f"Postavke iz Telegrame nisu pročitane ({exc}). Ostaje zadano.")
        return 0
    path = os.environ.get("GITHUB_ENV")
    if not path:
        print(settings.to_json())
        return 0
    if write_github_env(settings, path):
        print("Prikvačene postavke prenesene u okruženje dnevnog pregleda.")
    else:
        print("Pin je na zadanim filtrima. Dnevni pregled koristi varijable repozitorija.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
