"""Formatiranje poruke na hrvatskom i dijeljenje na više poruka."""
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config
from .ranking import place_tag


def _where(job):
    if job.scope == "hr":
        return f"{job.location or 'Hrvatska'}" + (" (remote)" if job.remote else "")
    loc = (job.location or "").strip()
    return "Remote" if not loc or loc.lower().startswith("remote") else f"Remote – {loc}"


def build_messages(jobs, sender, mode="keywords"):
    today = datetime.now(ZoneInfo(config.TZ)).strftime("%d.%m.%Y.")
    b, e = sender.bold, sender.esc
    if not jobs:
        return [f"💼 {b('Oglasi ' + today)}\nDanas nema novih oglasa koji odgovaraju kriterijima."]
    header = f"💼 {b(f'Novi oglasi za posao – {today}')}\nPronađeno: {len(jobs)} ({'AI odabir' if mode == 'llm' else 'filter po ključnim riječima'})"
    blocks = []
    for i, j in enumerate(jobs, 1):
        lines = [f"{i}. {place_tag(j)} {b(e(j.title))}",
                 f"🏢 {e(j.company or 'n/a')} | 📍 {e(_where(j))}"]
        if j.reason:
            lines.append(f"💡 {e(j.reason)}")
        lines.append(f"🔗 {j.url}")
        blocks.append("\n".join(lines))
    return split([header] + blocks, sender.max_len - 12)


def split(blocks, max_len):
    msgs, cur = [], ""
    for blk in blocks:
        blk = blk[:max_len]
        if cur and len(cur) + 2 + len(blk) > max_len:
            msgs.append(cur)
            cur = blk
        else:
            cur = f"{cur}\n\n{blk}" if cur else blk
    if cur:
        msgs.append(cur)
    if len(msgs) > 1:
        msgs = [f"{m}\n\n({i}/{len(msgs)})" for i, m in enumerate(msgs, 1)]
    return msgs
