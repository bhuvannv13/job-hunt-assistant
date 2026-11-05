"""Offline HTML dashboard of your applications (python -m jobhunt report).

One self-contained file: headline numbers, the funnel from applied to offer, applications per week,
breakdowns by channel and sector, follow-ups that are due, and a filterable table. No external
scripts, fonts or images, so it opens from disk and stays private.
"""
from __future__ import annotations

import html
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from . import applications as appsmod

INK, MUTED, GRID, ACCENT, ACCENT2 = "#1d2733", "#5b6b78", "#e3e8ec", "#0b6e75", "#7fb8bd"
STATUS_LABEL = {"considering": "Considering", "applied": "Applied", "assessment": "Assessment", "interview_1": "1st interview",
                "interview_2": "2nd interview", "final_interview": "Final interview", "offer": "Offer", "hired": "Hired",
                "offer_declined": "Offer declined", "rejected": "Rejected", "withdrawn": "Withdrawn", "no_response": "No response"}


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def hbars(items: list[tuple[str, int]], width: int = 460) -> str:
    """Horizontal bar chart as inline SVG, with direct value labels."""
    if not items:
        return '<p class="muted">No data yet.</p>'
    top = max(v for _, v in items) or 1
    row, label_w = 26, 130
    h = row * len(items) + 6
    parts = [f'<svg viewBox="0 0 {width} {h}" width="100%" role="img" aria-label="bar chart">']
    for i, (label, value) in enumerate(items):
        y = i * row + 4
        w = max(2, (width - label_w - 40) * value / top)
        parts.append(f'<text x="{label_w - 8}" y="{y + 14}" text-anchor="end" class="lbl">{esc(label)}</text>'
                     f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="18" rx="3" fill="{ACCENT}"/>'
                     f'<text x="{label_w + w + 6:.1f}" y="{y + 14}" class="val">{value}</text>')
    parts.append("</svg>")
    return "".join(parts)


def weekly(apps: list[appsmod.Application], weeks: int = 12, today: date | None = None) -> str:
    today = today or date.today()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    counts = Counter()
    for a in apps:
        d = a.date_applied or ""
        if not d:
            continue
        day = date.fromisoformat(d)
        if day >= start:
            counts[(day - start).days // 7] += 1
    width, height, pad = 460, 150, 24
    top = max(counts.values() or [1])
    bw = (width - pad) / weeks
    parts = [f'<svg viewBox="0 0 {width} {height + 20}" width="100%" role="img" aria-label="applications per week">',
             f'<line x1="{pad}" y1="{height}" x2="{width}" y2="{height}" stroke="{GRID}"/>']
    for i in range(weeks):
        v = counts.get(i, 0)
        h = (height - 20) * v / top
        x = pad + i * bw + 3
        parts.append(f'<rect x="{x:.1f}" y="{height - h:.1f}" width="{bw - 6:.1f}" height="{h:.1f}" rx="2" fill="{ACCENT}"><title>{v}</title></rect>')
        if v:
            parts.append(f'<text x="{x + (bw - 6) / 2:.1f}" y="{height - h - 4:.1f}" text-anchor="middle" class="val">{v}</text>')
        if i % 2 == 0:
            label = (start + timedelta(weeks=i)).strftime("%d %b")
            parts.append(f'<text x="{x + (bw - 6) / 2:.1f}" y="{height + 14}" text-anchor="middle" class="lbl">{label}</text>')
    parts.append("</svg>")
    return "".join(parts)


def build(apps: list[appsmod.Application], archive: str | Path = appsmod.ARCHIVE, quiet_days: int = 10,
          today: date | None = None) -> str:
    today = today or date.today()
    s = appsmod.summary(apps, archive)
    rate = lambda a, b: f"{100 * a / b:.0f}%" if b else "–"  # noqa: E731
    cards = [("Applications sent", s["applied"]), ("Reached interview", f'{s["interviews"]} <small>({rate(s["interviews"], s["applied"])})</small>'),
             ("Offers", s["offers"]), ("Open now", sum(1 for a in apps if a.status in appsmod.OPEN))]
    funnel_order = ["applied", "assessment", "interview_1", "interview_2", "final_interview", "offer", "hired"]
    reached = Counter()
    rank = {st: i for i, st in enumerate(funnel_order)}
    for a in apps:
        if a.status == "considering":
            continue
        best = rank.get(a.status, 0)
        if a.status in ("rejected", "withdrawn", "no_response", "offer_declined"):
            best = 2 if appsmod.reached_interview(a, archive) else 0
            if a.status == "offer_declined":
                best = rank["offer"]
        for st in funnel_order[: best + 1]:
            reached[st] += 1
    funnel = [(STATUS_LABEL[st], reached[st]) for st in funnel_order if reached[st] or st in ("applied", "interview_1", "offer")]
    status_items = [(STATUS_LABEL[k], v) for k, v in s["by_status"].items() if v]
    channel = Counter(a.channel or "Not recorded" for a in apps if a.status != "considering").most_common(8)
    sector = Counter(a.sector or "Not recorded" for a in apps if a.status != "considering").most_common(8)
    due = appsmod.followups_due(apps, quiet_days, today)
    def role_cell(a):
        if a.url.startswith("http"):
            return f'<a href="{esc(a.url)}" rel="noopener noreferrer">{esc(a.role)}</a>'
        return esc(a.role)

    rows = "".join(
        f'<tr data-status="{esc(a.status)}"><td>{esc(a.date_applied or a.status_date)}</td><td>{esc(a.company)}</td>'
        f'<td>{role_cell(a)}</td>'
        f'<td><span class="pill s-{esc(a.status)}">{esc(STATUS_LABEL.get(a.status, a.status))}</span></td>'
        f'<td>{esc(a.score)}</td><td>{esc(a.channel)}</td><td>{esc(a.next_step)}</td></tr>'
        for a in sorted(apps, key=lambda a: a.date_applied or a.status_date, reverse=True))
    due_html = "".join(f"<li><b>{esc(a.company)}</b> – {esc(a.role)}: {days} days quiet "
                       f"(follow-ups sent: {esc(a.followups_sent)})</li>" for a, days in due) or "<li>Nothing due.</li>"
    options = "".join(f'<option value="{k}">{v}</option>' for k, v in STATUS_LABEL.items() if s["by_status"].get(k))
    card_html = "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in cards)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Job search dashboard</title>
<style>
:root{{--ink:{INK};--muted:{MUTED};--grid:{GRID};--accent:{ACCENT};--bg:#f7f9fa;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--ink:#e7edf1;--muted:#9fb0bc;--grid:#2c3a44;--bg:#11181d;--card:#182229}}}}
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg);margin:0;padding:16px}}
main{{max-width:1080px;margin:auto}} h1{{font-size:22px;margin:4px 0}} h2{{font-size:15px;margin:0 0 8px}}
.muted,.sub{{color:var(--muted)}} .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:16px 0}}
.card,.panel{{background:var(--card);border:1px solid var(--grid);border-radius:10px;padding:14px}}
.k{{color:var(--muted);font-size:13px}} .v{{font-size:26px;font-weight:650;margin-top:4px}} .v small{{font-size:14px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-bottom:12px}}
svg text{{fill:var(--ink);font-size:12px}} svg .lbl{{fill:var(--muted)}} svg .val{{font-weight:600}}
table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{text-align:left;padding:7px 6px;border-bottom:1px solid var(--grid)}}
.wrap{{overflow-x:auto}} a{{color:var(--accent)}} select{{margin:0 0 8px;padding:4px}}
.pill{{padding:2px 8px;border-radius:999px;background:var(--grid);font-size:12px;white-space:nowrap}}
.s-offer,.s-hired{{background:#cfe9d6;color:#14532d}} .s-rejected,.s-no_response{{background:#f3d6d6;color:#7f1d1d}}
.s-interview_1,.s-interview_2,.s-final_interview,.s-assessment{{background:#d6e8f3;color:#0c4a6e}}
</style></head><body><main>
<h1>Job search dashboard</h1><p class="sub">Generated {today.isoformat()} from private/applications.csv · {s["total"]} tracked</p>
<div class="cards">{card_html}</div>
<div class="grid"><div class="panel"><h2>Funnel</h2>{hbars(funnel)}</div>
<div class="panel"><h2>Applications per week</h2>{weekly(apps, today=today)}</div></div>
<div class="grid"><div class="panel"><h2>Current status</h2>{hbars(status_items)}</div>
<div class="panel"><h2>Channel</h2>{hbars(channel)}</div>
<div class="panel"><h2>Sector</h2>{hbars(sector)}</div>
<div class="panel"><h2>Follow-ups due ({quiet_days}+ days quiet)</h2><ul>{due_html}</ul></div></div>
<div class="panel"><h2>Applications</h2><select id="f"><option value="">All statuses</option>{options}</select>
<div class="wrap"><table><thead><tr><th>Date</th><th>Company</th><th>Role</th><th>Status</th><th>Score</th><th>Channel</th><th>Next step</th></tr></thead>
<tbody id="rows">{rows}</tbody></table></div></div>
</main><script>
document.getElementById('f').addEventListener('change',e=>{{for(const r of document.querySelectorAll('#rows tr'))r.style.display=!e.target.value||r.dataset.status===e.target.value?'':'none'}});
</script></body></html>"""


def write(out: str | Path, csv_path: str | Path = appsmod.CSV_PATH, archive: str | Path = appsmod.ARCHIVE, quiet_days: int = 10) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(appsmod.load(csv_path), archive, quiet_days), encoding="utf-8")
    return out
