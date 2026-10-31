"""Naredbe Telegram bota. Bez mreže — lako se testira."""
HELP = """\
Bok. Šaljem početne tech oglase.

/pomoc — ove naredbe
/poslovi — odmah potraži oglase i pošalji ih
/postavke — pokaži filtre
/dodaj riječ — dodaj ulogu, npr. /dodaj data analyst
/makni riječ — makni ulogu
/grad grad — dodaj grad za on-site/hybrid, npr. /grad Zagreb
/maknigrad grad — makni grad
/reset — vrati ugrađene filtre

On-site i hybrid samo u gradovima s popisa. Remote: otvoren za EU ili svijet, i dovoljan je engleski (hrvatski je u redu).
Postavke su u prikvačenoj poruci. Ne briši je. Dnevni pregled u 12:00 čita iste postavke.
Ručna pretraga ne dijeli popis već poslanih oglasa s dnevnim pregledom, pa se neki oglas može pojaviti i ujutro.
"""


def split_command(text):
    text = (text or "").strip()
    if not text.startswith("/"):
        return None, ""
    first, _, rest = text.partition(" ")
    return first.split("@", 1)[0].lower(), rest.strip()


def _effective(custom, baseline):
    return list(custom) if custom is not None else list(baseline)


def _has(items, phrase):
    key = phrase.casefold()
    return any(x.casefold() == key for x in items)


def _without(items, phrase):
    key = phrase.casefold()
    return [x for x in items if x.casefold() != key]


def handle_command(text, settings, roles_baseline, cities_baseline):
    """Vrati (odgovor, nove postavke ili None ako se nisu mijenjale, akcija).

    akcija je "search" ili None.
    """
    cmd, arg = split_command(text)
    if cmd is None:
        return "Pošalji naredbu. /pomoc", None, None
    if cmd == "/start":
        # Spremi (i prikvači) poruku s postavkama čak i kad su još zadane.
        return HELP, settings, None
    if cmd in ("/pomoc", "/help"):
        return HELP, None, None
    if cmd == "/postavke":
        from .settings_store import _preview
        lines = [
            "Trenutni filtri:",
            _preview(settings.role_keywords, roles_baseline, "Uloge"),
            _preview(settings.onsite_cities, cities_baseline, "Gradovi (on-site/hybrid)"),
            "Remote: EU / Europe / worldwide, engleski dovoljan. Hrvatski je u redu.",
        ]
        return "\n".join(lines), None, None
    if cmd == "/poslovi":
        return "Tražim oglase. Može potrajati minutu.", None, "search"
    if cmd == "/reset":
        settings.role_keywords = None
        settings.onsite_cities = None
        return "Vraćeno na ugrađene filtre.", settings, None
    if cmd == "/dodaj":
        return _add(settings, roles_baseline, arg, "role")
    if cmd == "/makni":
        return _remove(settings, roles_baseline, arg, "role")
    if cmd == "/grad":
        return _add(settings, cities_baseline, arg, "city")
    if cmd == "/maknigrad":
        return _remove(settings, cities_baseline, arg, "city")
    return "Nepoznata naredba. Pošalji /pomoc", None, None


def _add(settings, baseline, arg, kind):
    if not arg:
        hint = "/dodaj data analyst" if kind == "role" else "/grad Zagreb"
        return f"Napiši što dodaješ, npr. {hint}", None, None
    if "," in arg:
        return "Jedna stavka po naredbi, bez zareza.", None, None
    if kind == "role":
        current = _effective(settings.role_keywords, baseline)
        if _has(current, arg):
            return f"«{arg}» je već među ulogama.", None, None
        current.append(arg)
        settings.role_keywords = current
        return f"Dodana uloga: {arg}", settings, None
    current = _effective(settings.onsite_cities, baseline)
    if _has(current, arg):
        return f"«{arg}» je već među gradovima.", None, None
    current.append(arg)
    settings.onsite_cities = current
    return f"Dodan grad: {arg}. On-site/hybrid samo u: {', '.join(current)}", settings, None


def _remove(settings, baseline, arg, kind):
    if not arg:
        hint = "/makni data analyst" if kind == "role" else "/maknigrad Split"
        return f"Napiši što mičeš, npr. {hint}", None, None
    if kind == "role":
        current = _effective(settings.role_keywords, baseline)
        if not _has(current, arg):
            return f"Nema uloge «{arg}».", None, None
        new = _without(current, arg)
        if not new:
            return "Mora ostati barem jedna uloga.", None, None
        settings.role_keywords = new
        return f"Maknuta uloga: {arg}", settings, None
    current = _effective(settings.onsite_cities, baseline)
    if not _has(current, arg):
        return f"Nema grada «{arg}».", None, None
    new = _without(current, arg)
    if not new:
        return "Mora ostati barem jedan grad. On-site izvan popisa se ne šalje.", None, None
    settings.onsite_cities = new
    return f"Maknut grad: {arg}. Ostaju: {', '.join(new)}", settings, None
