"""The profile's daily data: draws assets/stats.svg and restyles the 3D contribution images.

    GITHUB_TOKEN=... USERNAME=wth-lg python3 scripts/daily.py profile-3d-contrib/*.svg

It reads the contribution calendar every visitor sees under the README (signed out, so UTC days; its daily totals count
private work; GraphQL is the fallback), and then:
  - assets/stats.svg: the last year's contributions, the current and longest streak and the active days, in Space
    Grotesk numerals that roll into place, drawn from assets/kit.json (assets/build.py makes it), so no font tools here;
  - each 3D image (github-profile-3d-contrib): its Commit / Issue / PullReq / Review / Repo radar becomes contributions
    by weekday, because GitHub reports private organisation work only as daily totals, never by type, so the five axes
    showed Commit 6 beside 7,789 contributions; the seven numbers add up to the headline, rewritten from the same
    calendar. Its language donut (only "other", for the same reason) goes, and its colours and type become wentao.gg's.
"""
import json
import math
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
ROOT = Path(__file__).resolve().parent.parent
KIT = json.loads((ROOT / "assets" / "kit.json").read_text())
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # clockwise from the top
R_OUT, R_LABEL = 156, 194  # the tool's outer ring; the labels sit just outside it


def public_calendar(user):
    """The calendar every visitor sees under the README: github.com/users/<user>/contributions, read signed out.

    The GraphQL calendar counts fewer contributions (7,798 against the page's 8,075 on 2026-10-02: it drops some private
    organisation work) and splits days by the viewer, so this is the source; the per-day tooltips must add up to the
    page's own "N contributions in the last year", or it falls back to GraphQL."""
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions", headers={"User-Agent": "wth-lg-profile"})
    page = urllib.request.urlopen(req).read().decode()
    cells = {}
    for tag in re.findall(r"<td\b[^>]*\bdata-date=[^>]*>", page):
        d, i = re.search(r'data-date="([0-9-]{10})"', tag), re.search(r'\bid="([^"]+)"', tag)
        if d and i:
            cells[i.group(1)] = d.group(1)
    counts = {}
    for cid, text in re.findall(r'<tool-tip\b[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        if cid in cells:
            m = re.match(r"\s*([0-9,]+) contributions? on", text)
            counts[cells[cid]] = int(m.group(1).replace(",", "")) if m else 0
    headline = re.search(r"([0-9,]+)\s+contributions?\s+in the last year", page)
    total = int(headline.group(1).replace(",", "")) if headline else -1
    if not counts or len(counts) != len(cells) or sum(counts.values()) != total:
        raise ValueError(f"the page's calendar did not add up ({len(counts)} of {len(cells)} days, "
                         f"{sum(counts.values())} against {total})")
    return sorted((d, (date.fromisoformat(d).weekday() + 1) % 7, c) for d, c in counts.items())  # GitHub's weekday: 0 is Sunday


def graphql_calendar(user, token):
    query = ("query($u: String!) { user(login: $u) { contributionsCollection { contributionCalendar {"
             " totalContributions weeks { contributionDays { date weekday contributionCount } } } } } }")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"u": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    cal = json.load(urllib.request.urlopen(req))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = sorted((d["date"], d["weekday"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"])
    assert sum(c for _, _, c in days) == cal["totalContributions"]
    return days


def calendar(user, token):
    try:
        return public_calendar(user), "the public calendar"
    except Exception as e:  # GitHub changed the page: the API's count is close, and better than none
        print(f"falling back to GraphQL: {e}")
        return graphql_calendar(user, token), "GraphQL"


def stats(days):
    counts = [c for _, _, c in days]
    by_day = [0] * 7  # Mon .. Sun; GitHub's weekday 0 is Sunday
    for _, wd, c in days:
        by_day[(wd + 6) % 7] += c
    run = longest = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current, i = 0, len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1  # today may not have started yet
    while i >= 0 and counts[i]:
        current, i = current + 1, i - 1
    best = max(days, key=lambda d: (d[2], d[0]))
    return {"total": sum(counts), "by_day": by_day, "current": current, "longest": longest,
            "active": sum(1 for c in counts if c), "span": len(counts), "first": days[0][0], "last": days[-1][0],
            "best": best[2], "best_date": best[0]}


# ---------------------------------------------------------------------------------------------------- assets/stats.svg
def num(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def mono(text, x, y, cls, anchor="start"):
    m = KIT["mono"]
    step = m["advance"] + m["tracking"] * m["size"]
    w = step * len(text) - m["tracking"] * m["size"]
    x0 = x - w if anchor == "end" else x
    uses = "".join(f'<use href="#m{ord(ch)}" x="{num(x0 + i * step)}" y="{num(y)}"/>' for i, ch in enumerate(text) if ch != " ")
    return f'<g class="{cls}">{uses}</g>', {ch for ch in text if ch != " "}


def odometer(value, x, base, t0):
    """Each digit rolls down a 0-9 column into place, like wentao.gg's split-flap; the final frame is the number."""
    size, cell = KIT["size"], KIT["cell"]
    step = size * 1.25
    text = f"{value:,}"
    parts, cx = [], x
    for i, ch in enumerate(text):
        if ch == ",":
            parts.append(f'<use href="#dcomma" x="{num(cx)}" y="{num(base)}" class="fg"/>')
            cx += KIT["digits"][","]["w"]
            continue
        d = int(ch)
        col = "".join(f'<use href="#d{k}" x="{num(cx)}" y="{num(base + k * step)}"/>' for k in range(10))
        dur, delay = 1.2 + 0.1 * (len(text) - i), t0 + 0.06 * i
        parts.append(f'<g clip-path="url(#cl)"><g class="fg" transform="translate(0 {num(-d * step)})" '
                     f'style="animation:r{d} {num(dur)}s cubic-bezier(.2,.8,.2,1) {num(delay)}s both">{col}</g></g>')
        cx += cell
    return "".join(parts)


def stats_svg(s):
    W, H = 860, 140
    size, step = KIT["size"], KIT["size"] * 1.25
    base = 66
    day = lambda iso: f"{date.fromisoformat(iso):%b %-d, %Y}".upper()
    cells = [
        (s["total"], "CONTRIBUTIONS", f"SINCE {day(s['first'])}"),
        (s["current"], "DAY STREAK", "LONGEST YET" if s["current"] and s["current"] == s["longest"] else f"LONGEST {s['longest']}"),
        (s["best"], "BEST DAY", day(s["best_date"])),
        (s["active"], "ACTIVE DAYS", f"OF {s['span']}"),
    ]
    body, chars = [], set()
    for k, (value, label, detail) in enumerate(cells):
        x = k * 215 + (0 if k == 0 else 22)
        body.append(odometer(value, x, base, 0.15 + 0.1 * k))
        g1, c1 = mono(label, x, 96, "fg")
        g2, c2 = mono(detail, x, 116, "mu")
        body += [f'<g style="animation:wait {num(0.5 + 0.1 * k)}s step-end">{g1}</g>', f'<g style="animation:wait {num(0.6 + 0.1 * k)}s step-end">{g2}</g>']
        chars |= c1 | c2
        if k:
            body.append(f'<line class="shl" x1="{k * 215}" y1="14" x2="{k * 215}" y2="124" stroke-width="1" pathLength="1" '
                        f'stroke-dasharray="1" style="animation:draw .8s cubic-bezier(.65,0,.35,1) {num(0.1 * k)}s both"/>')
    body.append('<line class="shl" x1="0" y1="138.5" x2="860" y2="138.5" stroke-width="1" pathLength="1" stroke-dasharray="1" '
                'style="animation:draw 1s cubic-bezier(.65,0,.35,1) .1s both"/>')
    defs = ["".join(f'<path id="d{k}" d="{KIT["digits"][str(k)]["d"]}"/>' for k in range(10)),
            f'<path id="dcomma" d="{KIT["digits"][","]["d"]}"/>',
            "".join(f'<path id="m{ord(ch)}" d="{KIT["mono"]["glyphs"][ch]}"/>' for ch in sorted(chars)),
            f'<clipPath id="cl"><rect x="0" y="{num(base - size * 0.82)}" width="{W}" height="{num(size * 1.0)}"/></clipPath>']
    rolls = "".join(f"@keyframes r{d}{{from{{transform:translateY(0)}}to{{transform:translateY({num(-d * step)}px)}}}}" for d in range(10))
    alt = (f"{s['total']:,} contributions in the last {s['span']} days; a {s['current']}-day streak (the longest "
           f"{s['longest']}); the best day {s['best']} on {s['best_date']}; {s['active']} active days of {s['span']}.")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-labelledby="t"><title id="t">{alt}</title><!-- Drawn daily by scripts/daily.py. -->\n'
            f'<style>{KIT["css"]}{rolls}</style>\n<defs>{"".join(defs)}</defs>{"".join(body)}\n</svg>\n')


# ---------------------------------------------------------------------------------------------------- the 3D images
def nice_step(raw):
    mag = 10 ** math.floor(math.log10(max(raw, 1)))
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)


def short(n):
    return f"{n / 1000:g}K" if n >= 1000 else f"{n:g}"


def el(tag, attrs, text=None, parent=None):
    a = {k: str(v) for k, v in attrs.items()}
    e = ET.Element(f"{{{NS}}}{tag}", a) if parent is None else ET.SubElement(parent, f"{{{NS}}}{tag}", a)
    if text is not None:
        e.text = text
    return e


def point(k, r):
    a = -math.pi / 2 + k * 2 * math.pi / 7
    return r * math.cos(a), r * math.sin(a)


def radar(by_day, transform):
    step = nice_step(max(by_day) / 4)
    top = step * math.ceil(max(by_day) / step)
    dash = "stroke-dasharray: 4 4; stroke-width: 1px;"
    g = el("g", {"transform": transform})
    ring = step
    while ring <= top + 1e-9:  # dashed heptagons, labelled up the Mon axis like the tool's scale
        r = R_OUT * ring / top
        el("polygon", {"points": " ".join("%.2f,%.2f" % point(k, r) for k in range(7)), "fill": "none",
                       "class": "stroke-weak", "style": dash}, parent=g)
        el("text", {"style": "font-size: 14px;", "x": 6, "y": "%.2f" % (-r), "dominant-baseline": "middle",
                    "class": "fill-weak"}, short(ring), parent=g)
        ring += step
    for k, (day, n) in enumerate(zip(DAYS, by_day)):
        x, y = point(k, R_OUT)
        el("line", {"x1": 0, "y1": 0, "x2": "%.2f" % x, "y2": "%.2f" % y, "class": "stroke-weak", "style": dash}, parent=g)
        lx, ly = point(k, R_LABEL)
        label = el("text", {"style": "font-size: 20.8px;", "text-anchor": "middle", "dominant-baseline": "middle",
                            "x": "%.2f" % lx, "y": "%.2f" % (ly - 11), "class": "fill-fg"}, day, parent=g)
        el("title", {}, f"{day}: {n:,} contributions", parent=label)
        el("text", {"style": "font-size: 18px; font-weight: bold;", "text-anchor": "middle", "dominant-baseline": "middle",
                    "x": "%.2f" % lx, "y": "%.2f" % (ly + 11), "class": "fill-strong"}, f"{n:,}", parent=g)
    pts = " ".join("%.2f,%.2f" % point(k, R_OUT * n / top) for k, n in enumerate(by_day))
    poly = el("polygon", {"class": "radar", "points": pts}, parent=g)
    el("animate", {"attributeName": "points", "values": " ".join(["0,0"] * 7) + ";" + pts, "dur": "3s", "repeatCount": "1"}, parent=poly)
    return g


RAMPS = {  # contribution levels 0-4 as (top, left, right) faces: wentao.gg's blue
    "dark": [("#1b2029", "#151a22", "#10141a"), ("#13284f", "#10203f", "#0c1931"), ("#1e3a8a", "#182f70", "#132558"),
             ("#2563eb", "#1e50bf", "#183f96"), ("#60a5fa", "#4d86cc", "#3c69a0")],
    "light": [("#ebedf0", "#dfe2e6", "#d3d7dc"), ("#c7d7fe", "#b0c4f0", "#9bb1e0"), ("#93b4f8", "#7d9ee6", "#6888d0"),
              ("#3b82f6", "#2f6fdc", "#255cc0"), ("#1d4ed8", "#183fb0", "#12318c")],
}
INKS = {"dark": ("#e8e8e2", "#8b8b94", "#30363d", "#60a5fa", ".3"), "light": ("#0b0d12", "#626c7a", "#d0d7de", "#2563eb", ".18")}


def theme_css(theme):
    fg, mu, hl, strong, op = INKS[theme]
    fonts = KIT["fonts"]
    css = [f'@font-face{{font-family:WGM;src:url(data:font/woff2;base64,{fonts["mono"]}) format("woff2")}}',
           f'@font-face{{font-family:WGD;font-weight:700;src:url(data:font/woff2;base64,{fonts["display"]}) format("woff2")}}',
           "text{font-family:WGM,ui-monospace,monospace}",
           'text[style*="32px"],text[style*="24px"]{font-family:WGD,sans-serif;font-weight:700}',
           f".fill-bg{{fill:none}}.fill-fg{{fill:{fg}}}.fill-weak{{fill:{mu}}}.stroke-weak{{stroke:{hl}}}"
           f".stroke-fg{{stroke:{fg}}}.fill-strong{{fill:{strong}}}"
           f".radar{{stroke:#2563eb;fill:#2563eb;fill-opacity:{op};stroke-width:3px}}"]
    for lvl, (top, left, right) in enumerate(RAMPS[theme]):
        css.append(f".cont-top-{lvl}{{fill:{top}}}.cont-left-{lvl}{{fill:{left}}}.cont-right-{lvl}{{fill:{right}}}")
    return "".join(css)


def rewrite(path, s):
    tree = ET.parse(path)
    root = tree.getroot()
    kids = list(root)
    old = next((c for c in kids if c.find(f".//{{{NS}}}polygon[@class='radar']") is not None), None)
    if old is None:
        print(f"{path}: no radar, left alone")
        return
    for t in root.iter(f"{{{NS}}}text"):  # the headline, the tool's one number in fill-strong; before the radar adds more
        if t.get("class") == "fill-strong" and (t.text or "").strip().isdigit():
            t.text = f"{s['total']:,}"
    root.insert(kids.index(old), radar(s["by_day"], old.get("transform", "")))
    root.remove(old)
    for c in list(root):  # the language donut: the tool's group at translate(40, 520)
        if (c.get("transform") or "").replace(" ", "") == "translate(40,520)":
            root.remove(c)
    theme = "dark" if "night" in Path(path).name else "light"
    el("style", {}, theme_css(theme), parent=root)
    tree.write(path, encoding="unicode")
    print(f"{path}: {theme}, weekday radar {dict(zip(DAYS, s['by_day']))}, total {s['total']}")


if __name__ == "__main__":
    days, source = calendar(os.environ["USERNAME"], os.environ.get("GITHUB_TOKEN", ""))
    s = stats(days)
    print(f"read {len(days)} days from {source}")
    (ROOT / "assets" / "stats.svg").write_text(stats_svg(s))
    print("assets/stats.svg:", {k: s[k] for k in ("total", "current", "longest", "best", "best_date", "active", "span", "first", "last")})
    for path in sys.argv[1:]:
        rewrite(path, s)
