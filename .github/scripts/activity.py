"""Generate assets/activity.svg from public GitHub data (no third-party services)."""
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import date
from html import escape

USER = os.environ.get("GH_USER", "PaimEdu-DEV")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/activity.svg"

BG, WHITE, GRAY, LINE = "#0D1117", "#FFFFFF", "#8B949E", "#21262D"
LEVELS = ["#161B22", "#2D333B", "#545D68", "#8B949E", "#FFFFFF"]
FONT = "Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def get(url, api=False):
    headers = {"User-Agent": "profile-activity-svg"}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return r.read().decode("utf-8")


def contributions():
    html = get(f"https://github.com/users/{USER}/contributions")
    cells = {}
    for td in re.finditer(r"<td[^>]*ContributionCalendar-day[^>]*>", html):
        tag = td.group(0)
        d = re.search(r'data-date="([\d-]+)"', tag)
        lvl = re.search(r'data-level="(\d)"', tag)
        cid = re.search(r'id="([^"]+)"', tag)
        if d and lvl and cid:
            cells[cid.group(1)] = [date.fromisoformat(d.group(1)), int(lvl.group(1)), 0]
    for tip in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', html):
        if tip.group(1) in cells:
            m = re.match(r"([\d,]+) contribution", tip.group(2))
            cells[tip.group(1)][2] = int(m.group(1).replace(",", "")) if m else 0
    days = sorted(cells.values())
    if len(days) < 300:
        raise SystemExit("contribution calendar not parsed; keeping previous SVG")
    return days


def languages():
    repos = json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner", api=True))
    total = Counter()
    for r in repos:
        if r["fork"] or r["name"] == USER:
            continue
        total.update(json.loads(get(r["languages_url"], api=True)))
    # markup, scripts and Linguist misdetections (e.g. Smalltalk) are not "languages used"
    for noise in ("HTML", "CSS", "Batchfile", "Dockerfile", "Shell", "PowerShell", "Smalltalk"):
        total.pop(noise, None)
    return len([r for r in repos if not r["fork"]]), total.most_common(5)


def streaks(days):
    longest = run = 0
    for _, _, n in days:
        run = run + 1 if n else 0
        longest = max(longest, run)
    current = 0
    for i, (_, _, n) in enumerate(reversed(days)):
        if n:
            current += 1
        elif i > 0:  # today may still be empty
            break
    return current, longest


def build(days, repo_count, langs):
    W, PAD = 840, 40
    total = sum(n for *_, n in days)
    active = sum(1 for *_, n in days if n)
    current, longest = streaks(days)
    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="360" viewBox="0 0 {W} 360" '
             f'role="img" aria-label="GitHub activity for {USER}: {total} contributions in the last year">')
    o.append(f'<style>text{{font-family:{FONT}}}.k{{fill:{GRAY};font-size:11px;letter-spacing:1.6px}}'
             f'.v{{fill:{WHITE};font-size:30px;font-weight:600;letter-spacing:-0.5px}}'
             f'.l{{fill:{GRAY};font-size:12px}}</style>')
    o.append(f'<rect width="{W}" height="360" rx="10" fill="{BG}"/>')
    o.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="359" rx="10" fill="none" stroke="{LINE}"/>')
    o.append(f'<text x="{PAD}" y="48" class="k">ACTIVITY · LAST 12 MONTHS</text>')
    o.append(f'<text x="{W-PAD}" y="48" class="k" text-anchor="end">UPDATED {date.today():%d.%m.%Y}</text>')

    metrics = [(f"{total:,}", "contributions"), (str(active), "active days"),
               (str(longest), "longest streak, days"), (str(repo_count), "public repositories")]
    col = (W - 2 * PAD) / 4
    for i, (v, label) in enumerate(metrics):
        x = PAD + i * col
        o.append(f'<text x="{x}" y="100" class="v">{escape(v)}</text>')
        o.append(f'<text x="{x}" y="122" class="l">{escape(label)}</text>')

    # heatmap: weeks as columns, Sunday on top
    cell, gap, top = 11, 3, 152
    first = days[0][0]
    offset = (first.weekday() + 1) % 7
    weeks = (len(days) + offset + 6) // 7
    left = PAD + ((W - 2 * PAD) - (weeks * (cell + gap) - gap)) / 2
    for idx, (d, lvl, n) in enumerate(days):
        k = idx + offset
        x, y = left + (k // 7) * (cell + gap), top + (k % 7) * (cell + gap)
        o.append(f'<rect x="{x:.1f}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{LEVELS[lvl]}">'
                 f'<title>{n} on {d.isoformat()}</title></rect>')

    # languages: thin stacked bar + legend
    y = 278
    o.append(f'<text x="{PAD}" y="{y}" class="k">MOST USED LANGUAGES · PUBLIC REPOSITORIES</text>')
    shades = ["#FFFFFF", "#C9D1D9", "#8B949E", "#545D68", "#30363D"]
    s = sum(b for _, b in langs) or 1
    x, bw = PAD, W - 2 * PAD
    for i, (name, b) in enumerate(langs):
        w = bw * b / s
        o.append(f'<rect x="{x:.1f}" y="{y+14}" width="{max(w-2,1):.1f}" height="4" fill="{shades[i]}"/>')
        x += w
    lx = PAD
    for i, (name, b) in enumerate(langs):
        label = f"{name} {100*b/s:.0f}%"
        o.append(f'<rect x="{lx}" y="{y+36}" width="8" height="8" rx="2" fill="{shades[i]}"/>')
        o.append(f'<text x="{lx+14}" y="{y+44}" class="l">{escape(label)}</text>')
        lx += 14 + len(label) * 7 + 24
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    days = contributions()
    count, langs = languages()
    svg = build(days, count, langs)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg + "\n")
    print(f"wrote {OUT}")
