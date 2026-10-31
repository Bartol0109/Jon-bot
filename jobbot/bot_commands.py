"""Naredbe Telegram bota. Bez mreže — lako se testira."""
HELP = """\
Bok. Šaljem početne tech oglase.

/pomoc — ove naredbe
/poslovi — odmah potraži svježe oglase i pošalji ih
/mjesec — oglasi iz zadnjih 30 dana (već poslani se ne preskaču)
/postavke — pokaži filtre
/dodaj riječ — dodaj ulogu, npr. /dodaj data analyst
/makni riječ — makni ulogu
/grad grad — dodaj grad za on-site/hybrid, npr. /grad Zagreb
/maknigrad grad — makni grad
/iskljuci riječ — izbaci naslove s tom riječi, npr. /iskljuci hardware
/ukljuci riječ — vrati tu riječ u naslove
/remote — jesu li remote oglasi uključeni
/remote off ili /bezremote — samo on-site/hybrid u gradovima
/remote on — opet šalji i remote
/usko — je li uski način uključen
/usko on — naslov mora pogoditi uži popis (frontend, dizajn, unity, …)
/usko off — vrati široke filtre (programiranje, analitika, podrška)
/usko dodaj riječ — dodaj u uži popis
/usko makni riječ — makni iz užeg popisa
/reset — vrati ugrađene filtre

Šaljem samo oglase na engleskom ili hrvatskom. On-site i hybrid samo u gradovima s popisa. Remote: otvoren za EU ili svijet.
Postavke su u prikvačenoj poruci. Ne briši je. Dnevni pregled u 12:00 čita iste postavke.
Ručna pretraga ne dijeli popis već poslanih oglasa s dnevnim pregledom, pa se neki oglas može pojaviti i ujutro.
"""


def split_command(text):
    text = (text or "").strip()
    if not text.startswith("/"):
        return None, ""
    first, _, rest = text.partition(" ")
    return first.split("@", 1)[0].lower(), rest.strip()


def _remote_state(settings):
    if settings.allow_remote is False:
        return "Remote: isključen (samo on-site/hybrid u gradovima)"
    if settings.allow_remote is True:
        return "Remote: uključen"
    return "Remote: uključen (zadano)"


def _remote_cmd(settings, arg):
    word = (arg or "").casefold()
    if word in ("off", "0", "ne", "iskljuci", "isključi"):
        settings.allow_remote = False
        return "Remote oglasi su isključeni. Ostaju samo on-site i hybrid u tvojim gradovima.", settings, None
    if word in ("on", "1", "da", "ukljuci", "uključi"):
        settings.allow_remote = True
        return "Remote oglasi su uključeni.", settings, None
    if not word:
        return _remote_state(settings) + ". /remote off ili /remote on.", None, None
    return "Koristi /remote, /remote on ili /remote off.", None, None


def _usko_state(settings):
    if settings.narrow_mode is True:
        return "Uski način: uključen"
    if settings.narrow_mode is False:
        return "Uski način: isključen"
    return "Uski način: isključen (zadano)"


def _usko_cmd(settings, arg, baseline):
    head, _, rest = (arg or "").partition(" ")
    word = head.casefold()
    if not word:
        return _usko_state(settings) + ". /usko on, /usko off, /usko dodaj, /usko makni.", None, None
    if word in ("on", "1", "da"):
        settings.narrow_mode = True
        return "Uski način je uključen. Naslov mora odgovarati užem popisu.", settings, None
    if word in ("off", "0", "ne"):
        settings.narrow_mode = False
        return "Uski način je isključen. Vrijede širi filtri (programiranje, analitika, podrška).", settings, None
    if word == "dodaj":
        return _narrow_add(settings, baseline, rest.strip())
    if word == "makni":
        return _narrow_remove(settings, baseline, rest.strip())
    return "Koristi /usko, /usko on, /usko off, /usko dodaj riječ ili /usko makni riječ.", None, None


def _narrow_add(settings, baseline, arg):
    if not arg:
        return "Napiši što dodaješ, npr. /usko dodaj tailwind", None, None
    if "," in arg:
        return "Jedna riječ ili izraz po naredbi, bez zareza.", None, None
    current = _effective(settings.narrow_keywords, baseline)
    if _has(current, arg):
        return f"«{arg}» je već u uskom popisu.", None, None
    current.append(arg)
    settings.narrow_keywords = current
    return f"U uži popis dodano: {arg}", settings, None


def _narrow_remove(settings, baseline, arg):
    if not arg:
        return "Napiši što mičeš, npr. /usko makni unity", None, None
    current = _effective(settings.narrow_keywords, baseline)
    if not _has(current, arg):
        return f"«{arg}» nije u uskom popisu.", None, None
    new = _without(current, arg)
    if not new:
        return "U užem popisu mora ostati barem jedna riječ.", None, None
    settings.narrow_keywords = new
    return f"Iz užeg popisa maknuto: {arg}", settings, None


def _effective(custom, baseline):
    return list(custom) if custom is not None else list(baseline)


def _has(items, phrase):
    key = phrase.casefold()
    return any(x.casefold() == key for x in items)


def _without(items, phrase):
    key = phrase.casefold()
    return [x for x in items if x.casefold() != key]


def handle_command(text, settings, roles_baseline, cities_baseline, exclude_baseline, narrow_baseline):
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
            _preview(settings.exclude_keywords, exclude_baseline, "Isključeno iz naslova"),
            _remote_state(settings),
            _usko_state(settings),
        ]
        return "\n".join(lines), None, None
    if cmd == "/poslovi":
        return "Tražim svježe oglase. Može potrajati minutu.", None, "search"
    if cmd == "/mjesec":
        return (
            "Tražim oglase iz zadnjih 30 dana. Već poslane ne preskačem. "
            "Neki izvori daju samo novije oglase, pa stariji mogu nedostajati. Može potrajati minutu.",
            None,
            "search_month",
        )
    if cmd == "/reset":
        settings.role_keywords = None
        settings.onsite_cities = None
        settings.exclude_keywords = None
        settings.allow_remote = None
        settings.narrow_mode = None
        settings.narrow_keywords = None
        return "Vraćeno na ugrađene filtre.", settings, None
    if cmd in ("/bezremote",):
        settings.allow_remote = False
        return "Remote oglasi su isključeni. Ostaju samo on-site i hybrid u tvojim gradovima.", settings, None
    if cmd == "/remote":
        return _remote_cmd(settings, arg)
    if cmd == "/usko":
        return _usko_cmd(settings, arg, narrow_baseline)
    if cmd == "/dodaj":
        return _add(settings, roles_baseline, arg, "role")
    if cmd == "/makni":
        return _remove(settings, roles_baseline, arg, "role")
    if cmd == "/grad":
        return _add(settings, cities_baseline, arg, "city")
    if cmd == "/maknigrad":
        return _remove(settings, cities_baseline, arg, "city")
    if cmd in ("/iskljuci", "/isključi"):
        return _exclude_add(settings, exclude_baseline, arg)
    if cmd in ("/ukljuci", "/uključi"):
        return _exclude_remove(settings, exclude_baseline, arg)
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


def _exclude_add(settings, baseline, arg):
    if not arg:
        return "Napiši što isključuješ iz naslova, npr. /iskljuci hardware", None, None
    if "," in arg:
        return "Jedna riječ ili izraz po naredbi, bez zareza.", None, None
    current = _effective(settings.exclude_keywords, baseline)
    if _has(current, arg):
        return f"«{arg}» je već isključena.", None, None
    current.append(arg)
    settings.exclude_keywords = current
    return f"Naslovi s «{arg}» više ne prolaze.", settings, None


def _exclude_remove(settings, baseline, arg):
    if not arg:
        return "Napiši što vraćaš, npr. /ukljuci embedded", None, None
    current = _effective(settings.exclude_keywords, baseline)
    if not _has(current, arg):
        return f"«{arg}» nije na popisu isključenih.", None, None
    settings.exclude_keywords = _without(current, arg)
    if settings.exclude_keywords:
        return f"«{arg}» više nije isključena.", settings, None
    return "Nema više isključenih riječi. Naslovi se ne filtriraju po tom popisu.", settings, None
