"""The profile's daily data: draws assets/stats.svg, writes its alt text into README.md and restyles the 3D images.

    GITHUB_TOKEN=... USERNAME=wth-lg python3 scripts/daily.py profile-3d-contrib/*.svg

It reads the contribution calendar every visitor sees under the README (signed out, so UTC days; its daily totals count
private work; GraphQL is the fallback), and then:
  - assets/stats.svg: the year's contributions, the typical (median) active day, the active days since the first one and
    the streak, in Space Grotesk numerals that roll into place; the weekly totals as bars, the peak and the latest week
    labelled; the median active day by weekday. Medians, because one 1,721-contribution day would otherwise decide the
    mean and the busiest weekday. Drawn from assets/kit.json (assets/build.py makes it), so no font tools here;
  - README.md: the stats image's alt text, between its <!-- stats --> markers, so a screen reader hears today's values;
  - each 3D image (github-profile-3d-contrib): only its calendar stays, cropped to the bars. Its radar and language donut
    see only public work (GitHub reports private organisation work as daily totals, never by type), its headline and
    counters sit outside the crop, and the total leads stats.svg instead. Its SMIL growth goes (it ignored reduced
    motion) for one CSS entrance, and its colours become wentao.gg's.
"""
import json
import math
import os
import re
import statistics
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
ROOT = Path(__file__).resolve().parent.parent
KIT = json.loads((ROOT / "assets" / "kit.json").read_text())
DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


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
    """Medians are the lower median, a real day's count, so every figure is a whole number."""
    counts = [c for _, _, c in days]
    run = longest = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current, i = 0, len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1  # today may not have started yet
    while i >= 0 and counts[i]:
        current, i = current + 1, i - 1
    start = next((k for k, c in enumerate(counts) if c), len(counts) - 1)
    since = days[start:]
    by_day = [[] for _ in range(7)]  # Mon .. Sun; GitHub's weekday 0 is Sunday
    for _, wd, c in since:
        by_day[(wd + 6) % 7].append(c)
    weeks = {}  # the calendar's own columns, Sunday to Saturday
    for k, (d, _, c) in enumerate(days):
        w = weeks.setdefault((k + days[0][1]) // 7, [d, d, 0])
        w[1], w[2] = d, w[2] + c
    active = [c for c in counts if c]
    return {"total": sum(counts), "current": current, "longest": longest, "first": days[0][0], "last": days[-1][0],
            "start": days[start][0], "since": len(since), "active": len(active),
            "typical": statistics.median_low(active) if active else 0,
            "by_day": [statistics.median_low([c for c in v if c]) if any(v) else 0 for v in by_day],
            "share": [sum(1 for c in v if c) / max(len(v), 1) for v in by_day],
            "weeks": [tuple(weeks[k]) for k in sorted(weeks)]}


# ---------------------------------------------------------------------------------------------------- assets/stats.svg
def num(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def mono_width(text):
    m = KIT["mono"]
    return (m["advance"] + m["tracking"] * m["size"]) * len(text) - m["tracking"] * m["size"]


def mono(text, x, y, cls, anchor="start"):
    m = KIT["mono"]
    step = m["advance"] + m["tracking"] * m["size"]
    x0 = x - mono_width(text) if anchor == "end" else x
    uses = "".join(f'<use href="#m{ord(ch)}" x="{num(x0 + i * step)}" y="{num(y)}"/>' for i, ch in enumerate(text) if ch != " ")
    return f'<g class="{cls}">{uses}</g>', {ch for ch in text if ch != " "}


def label(parts, x, y, anchor="start"):
    """One line of mono runs, [(text, class)], set end to end."""
    text = "".join(t for t, _ in parts)
    m = KIT["mono"]
    step = m["advance"] + m["tracking"] * m["size"]
    cx = x - mono_width(text) if anchor == "end" else x
    out, chars = [], set()
    for t, cls in parts:
        g, c = mono(t, cx, y, cls)
        out.append(g)
        chars |= c
        cx += step * len(t)
    return "".join(out), chars


ROLL = 5  # cells every digit travels: equal travel, so equal speed


def odometer(value, t0):
    """Each digit rolls down five cells into place, like wentao.gg's split-flap; drawn at the origin, baseline 0.

    The column's resting place is its own position, so the final frame (and reduced motion) is the number."""
    step, cell = KIT["size"] * 1.25, KIT["cell"]
    parts, cx = [], 0.0
    for i, ch in enumerate(f"{value:,}"):
        if ch == ",":
            parts.append(f'<use href="#dcomma" x="{num(cx)}" class="fg"/>')
            cx += KIT["digits"][","]["w"]
            continue
        d = int(ch)
        col = "".join(f'<use href="#d{(d - ROLL + j) % 10}" x="{num(cx)}" y="{num((ROLL - j) * step)}"/>' for j in range(ROLL + 1))
        parts.append(f'<g clip-path="url(#cl)"><g class="fg" style="animation:roll 1.2s cubic-bezier(.2,.8,.2,1) '
                     f'{num(t0 + 0.1 * i)}s both">{col}</g></g>')
        cx += cell
    return "".join(parts)


def short_day(iso):
    return f"{date.fromisoformat(iso):%b %-d}".upper()


def span(a, b):
    """OCT 4–10, SEP 28–OCT 4, or one day."""
    da, db = date.fromisoformat(a), date.fromisoformat(b)
    if da == db:
        return short_day(a)
    return f"{short_day(a)}–{db.day}" if da.month == db.month else f"{short_day(a)}–{short_day(b)}"


def window(s):
    day = lambda iso: f"{date.fromisoformat(iso):%b %-d %Y}".upper()
    return f"{day(s['first'])} – {day(s['last'])} · UTC"


def alt_text(s):
    weeks = s["weeks"]
    peak, latest = max(weeks, key=lambda w: (w[2], w[0])), weeks[-1]
    title = lambda iso: f"{date.fromisoformat(iso):%b %-d %Y}"
    streak = (f"A {s['current']}-day streak, the longest {s['longest']}." if s["current"]
              else f"No current streak; the longest {s['longest']} days.")
    return (f"{s['total']:,} contributions from {title(s['first'])} to {title(s['last'])} (UTC). "
            f"A typical active day has {s['typical']:,} (the median). "
            f"Active on {s['active']} of the {s['since']} days since {title(s['start'])}. {streak} "
            f"Weekly totals peak at {peak[2]:,} ({span(peak[0], peak[1]).title()}); "
            f"the latest week has {latest[2]:,} ({span(latest[0], latest[1]).title()}). Median active day by weekday: "
            + ", ".join(f"{d.title()} {v:,}" for d, v in zip(DAYS, s["by_day"])) + ".")


def stats_svg(s, narrow=False):
    """One row of cells over the weeks and the weekdays side by side; narrow (README.md's phone image, 480 wide, about
    0.75x) sets the cells two by two and the weekdays under the weeks, so a label is 9 px or more on a 343 px column."""
    W, H = (480, 714) if narrow else (860, 352)
    dw, dd = (146, 362) if narrow else (0, 0)  # how far the weeks and the weekdays move down
    size = KIT["size"]
    base, lead = 66, 1.25  # the total's digits are 1.25x the others
    body, chars = [], set()

    # the row: the total leads, at 1.25x; the rest are its context
    cells = [
        (s["total"], "CONTRIBUTIONS", "LAST 12 MONTHS"),
        (s["typical"], "TYPICAL DAY", "MEDIAN ACTIVE DAY"),
        (s["active"], "ACTIVE DAYS", f"OF {s['since']} SINCE {short_day(s['start'])}"),
        (s["current"], "DAY STREAK", "LONGEST YET" if s["current"] and s["current"] == s["longest"] else f"LONGEST {s['longest']}"),
    ]
    for k, (value, name, detail) in enumerate(cells):
        if narrow:
            xd, y = 252, 146 * (k // 2)  # a rule left of the right column
            x = 270 if k % 2 else 0
        else:
            xd, y = 270 + (k - 1) * 196, 0
            x = 0 if k == 0 else xd + 18
        t0 = 0.1 * (k + 1)
        body.append(f'<g transform="translate({num(x)} {base + y}){" scale(%s)" % num(lead) if k == 0 else ""}">{odometer(value, t0)}</g>')
        g1, c1 = mono(name, x, 98 + y, "fg")
        g2, c2 = mono(detail, x, 120 + y, "mu")
        body.append(f'<g style="animation:wait {num(t0)}s step-end">{g1}{g2}</g>')
        chars |= c1 | c2
        if k % 2 if narrow else k:
            body.append(f'<line class="shl" x1="{xd}" y1="{14 + y}" x2="{xd}" y2="{126 + y}" stroke-width="1" pathLength="1" '
                        f'stroke-dasharray="1" style="animation:draw .8s cubic-bezier(.65,0,.35,1) {num(0.1 * k)}s both"/>')
    body.append(f'<line class="shl" x1="0" y1="{150.5 + dw}" x2="{W}" y2="{150.5 + dw}" stroke-width="1" pathLength="1" '
                'stroke-dasharray="1" style="animation:draw 1s cubic-bezier(.65,0,.35,1) .1s both"/>')
    split = f'x1="0" y1="{150.5 + dd}" x2="{W}" y2="{150.5 + dd}"' if narrow else 'x1="540" y1="166" x2="540" y2="340"'
    body.append(f'<line class="shl" {split} stroke-width="1" pathLength="1" stroke-dasharray="1" '
                'style="animation:draw .8s cubic-bezier(.65,0,.35,1) .4s both"/>')

    # the weeks: one bar per calendar column, the peak and the latest week in blue and labelled
    x0, x1, top, bottom = 0, W if narrow else 520, 268 + dw, 340 + dw
    weeks = s["weeks"]
    peak_k = max(range(len(weeks)), key=lambda k: (weeks[k][2], k))
    last_k = len(weeks) - 1
    pitch = (x1 - x0) / len(weeks)
    bw = pitch * 0.7
    hi = max(weeks[peak_k][2], 1)
    bar_top = lambda k: bottom - max(1, (bottom - top) * weeks[k][2] / hi) if weeks[k][2] else bottom
    bars = []
    for k, (_, _, n) in enumerate(weeks):
        if n:
            y = bar_top(k)
            paint = 'class="bl"' if k in (peak_k, last_k) else 'class="mu" fill-opacity=".45"'
            bars.append(f'<rect {paint} x="{num(x0 + k * pitch)}" y="{num(y)}" width="{num(bw)}" height="{num(bottom - y)}"/>')
    body.append(f'<g style="transform-origin:0 {bottom}px;animation:gy .8s cubic-bezier(.2,.8,.2,1) .5s both">{"".join(bars)}</g>')
    body.append(f'<line class="shl" x1="{x0}" y1="{bottom + 0.5}" x2="{x1}" y2="{bottom + 0.5}" stroke-width="1"/>')
    g1, c1 = mono("WEEKLY TOTALS", 0, 184 + dw, "fg")
    g2, c2 = mono(window(s), 0, 206 + dw, "mu")
    body.append(f'<g style="animation:wait .5s step-end">{g1}{g2}</g>')
    chars |= c1 | c2
    # the latest week's tag sits above the peak's: its leader passes right of the peak's tag, which ends at its own bar
    marks = ([(peak_k, "PEAK, LATEST", 258 + dw)] if peak_k == last_k
             else [(last_k, "LATEST", 236 + dw), (peak_k, "PEAK", 258 + dw)])
    tags = []
    for k, word, y in marks:
        a, b, n = weeks[k]
        parts = [(f"{n:,}", "fg"), (f" {word} · {span(a, b)}", "mu")]
        w = mono_width("".join(t for t, _ in parts))
        right = x0 + k * pitch + bw
        g, c = label(parts, right, y, "end") if right - w >= 0 else label(parts, x0 + k * pitch, y, "start")
        chars |= c
        cx = x0 + k * pitch + bw / 2
        tags.append(g)
        if bar_top(k) - 3 - (y + 5) > 4:  # a tag right on its bar needs no leader
            tags.append(f'<line class="smu" x1="{num(cx)}" y1="{y + 5}" x2="{num(cx)}" y2="{num(bar_top(k) - 3)}" stroke-width="1"/>')
    body.append(f'<g style="animation:wait 1.3s step-end">{"".join(tags)}</g>')

    # the weekdays: the median active day, Monday to Sunday, one blue
    lx = 0 if narrow else 558
    bx = lx + 34
    reach = W - bx - 8 - mono_width("0,000")  # room for the value after the longest bar
    g1, c1 = mono("BY WEEKDAY", lx, 184 + dd, "fg")
    g2, c2 = mono("MEDIAN ACTIVE DAY", lx, 206 + dd, "mu")
    body.append(f'<g style="animation:wait .5s step-end">{g1}{g2}</g>')
    chars |= c1 | c2
    most = max(max(s["by_day"]), 1)
    for k, (day, v) in enumerate(zip(DAYS, s["by_day"])):
        y = 232 + dd + 18 * k
        t = 0.5 + 0.1 * k
        g, c = mono(day, lx, y, "mu")
        w = max(1, reach * v / most) if v else 0
        gv, cv = mono(f"{v:,}", bx + w + 8, y, "fg")
        chars |= c | cv
        body.append(f'{g}<rect class="bl" x="{bx}" y="{y - 9}" width="{num(w)}" height="9" '
                    f'style="transform-origin:{bx}px 0;animation:gx .8s cubic-bezier(.2,.8,.2,1) {num(t)}s both"/>'
                    f'<g style="animation:wait {num(t + 0.8)}s step-end">{gv}</g>')

    defs = ["".join(f'<path id="d{k}" d="{KIT["digits"][str(k)]["d"]}"/>' for k in range(10)),
            f'<path id="dcomma" d="{KIT["digits"][","]["d"]}"/>',
            "".join(f'<path id="m{ord(ch)}" d="{KIT["mono"]["glyphs"][ch]}"/>' for ch in sorted(chars)),
            f'<clipPath id="cl"><rect x="0" y="{num(-size * 0.82)}" width="{W}" height="{num(size * 1.0)}"/></clipPath>']
    motion = (f"@keyframes roll{{from{{transform:translateY({num(-ROLL * size * 1.25)}px)}}}}"
              "@keyframes gy{from{transform:scaleY(0)}}@keyframes gx{from{transform:scaleX(0)}}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-labelledby="t"><title id="t">{escape(alt_text(s))}</title><!-- Drawn daily by scripts/daily.py. -->\n'
            f'<style>{KIT["css"]}{motion}</style>\n<defs>{"".join(defs)}</defs>{"".join(body)}\n</svg>\n')


NARROW = "https://raw.githubusercontent.com/wth-lg/wth-lg/main/assets/stats-narrow.svg"  # absolute, like the 3D sources


def readme(path, s):
    """The stats image's alt text, rewritten between its markers with the phone's source; the rest of README.md is left as
    it is."""
    text = path.read_text()
    tag = (f'<picture>\n  <source media="(max-width: 600px)" srcset="{NARROW}" />\n'
           f'  <img src="./assets/stats.svg" width="100%" alt="{escape(alt_text(s), {chr(34): "&quot;"})}" />\n</picture>')
    out, n = re.subn(r"(<!-- stats -->\n).*?(\n<!-- /stats -->)", lambda m: m.group(1) + tag + m.group(2), text, flags=re.S)
    if n != 1:
        raise ValueError(f"{path}: {n} <!-- stats --> ... <!-- /stats --> blocks, not 1")
    path.write_text(out)


# ---------------------------------------------------------------------------------------------------- the 3D images
def el(tag, attrs, text=None, parent=None):
    a = {k: str(v) for k, v in attrs.items()}
    e = ET.Element(f"{{{NS}}}{tag}", a) if parent is None else ET.SubElement(parent, f"{{{NS}}}{tag}", a)
    if text is not None:
        e.text = text
    return e


def compose(m, t):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = t
    return a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f


def matrix(transform):
    """An SVG transform list as (a b c d e f); a function the tool never wrote raises."""
    m = (1, 0, 0, 1, 0, 0)
    for op, args in re.findall(r"(\w+)\s*\(([^)]*)\)", transform or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip())]
        m = compose(m, {"translate": lambda x, y=0: (1, 0, 0, 1, x, y),
                        "scale": lambda x, y=None: (x, 0, 0, x if y is None else y, 0, 0),
                        "skewX": lambda a: (1, 0, math.tan(math.radians(a)), 1, 0, 0),
                        "skewY": lambda a: (1, math.tan(math.radians(a)), 0, 1, 0, 0),
                        "matrix": lambda *k: k}[op](*v))
    return m


def bbox(group):
    """The bars' extent: every face's corners through its transforms (the tool draws faces as skewed rects)."""
    xs, ys = [], []
    for bar in group:
        mb = compose(matrix(group.get("transform")), matrix(bar.get("transform")))
        for r in bar.iter(f"{{{NS}}}rect"):
            a, b, c, d, e, f = compose(mb, matrix(r.get("transform")))
            x, y, w, h = (float(r.get(k)) for k in ("x", "y", "width", "height"))
            for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
                xs.append(a * px + c * py + e)
                ys.append(b * px + d * py + f)
    return min(xs), min(ys), max(xs), max(ys)


RAMPS = {  # contribution levels 0-4 as (top, left, right) faces: wentao.gg's blue; light levels 1-2 stay grey, so blue is real work
    "dark": [("#1b2029", "#151a22", "#10141a"), ("#13284f", "#10203f", "#0c1931"), ("#1e3a8a", "#182f70", "#132558"),
             ("#2563eb", "#1e50bf", "#183f96"), ("#60a5fa", "#4d86cc", "#3c69a0")],
    "light": [("#ebedf0", "#dfe2e6", "#d3d7dc"), ("#e3e7ee", "#d6dae2", "#c9ced6"), ("#c9d3e3", "#bac4d6", "#abb5c8"),
              ("#3b82f6", "#2f6fdc", "#255cc0"), ("#1d4ed8", "#183fb0", "#12318c")],
}
PAD = 12  # air around the bars in the cropped viewBox


def theme_css(theme):
    css = ["@keyframes in{from{opacity:0;transform:translateY(24px)}}"
           ".cal{animation:in 1s cubic-bezier(.2,.8,.2,1) .2s both}"
           "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"]
    for lvl, (top, left, right) in enumerate(RAMPS[theme]):
        css.append(f".cont-top-{lvl}{{fill:{top}}}.cont-left-{lvl}{{fill:{left}}}.cont-right-{lvl}{{fill:{right}}}")
    return "".join(css)


def rewrite(path, s):
    """The tool's image down to its calendar. Anything not laid out as v0.9.3 lays it out raises: no silent skips."""
    tree = ET.parse(path)
    root = tree.getroot()
    g = f"{{{NS}}}g"
    cal = [c for c in root if c.tag == g and not c.get("transform") and c.find(f"{g}/{{{NS}}}rect") is not None]
    radar = [c for c in root if c.find(f".//{{{NS}}}polygon[@class='radar']") is not None]
    heads = [c for c in root if c.tag == g and any(t.get("class") == "fill-strong" and "32px" in (t.get("style") or "")
                                                   for t in c.iter(f"{{{NS}}}text"))]
    if (len(cal), len(radar), len(heads)) != (1, 1, 1):
        raise ValueError(f"{path}: {len(cal)} calendars, {len(radar)} radars, {len(heads)} headlines, not one each "
                         "(not the tool's own output, or the tool's layout changed)")
    smil = 0
    for e in root.iter():
        for k in list(e):
            if k.tag in (f"{{{NS}}}animate", f"{{{NS}}}animateTransform"):
                e.remove(k)
                smil += 1
    x0, y0, x1, y1 = bbox(cal[0])
    for c in list(root):  # the radar, the donut, the headline row and the background: everything but the bars
        if c is not cal[0] and c.tag not in (f"{{{NS}}}style", f"{{{NS}}}defs"):
            root.remove(c)
    cal[0].set("class", "cal")
    vx, vy = math.floor(x0 - PAD), math.floor(y0 - PAD)
    vw, vh = math.ceil(x1 + PAD) - vx, math.ceil(y1 + PAD) - vy
    root.set("viewBox", f"{vx} {vy} {vw} {vh}")
    root.set("width", str(vw))
    root.set("height", str(vh))
    theme = "dark" if "night" in Path(path).name else "light"
    el("style", {}, theme_css(theme), parent=root)
    tree.write(path, encoding="unicode")
    print(f"{path}: {theme}, {smil} SMIL animations removed, cropped to {vx} {vy} {vw} {vh}")


if __name__ == "__main__":
    days, source = calendar(os.environ["USERNAME"], os.environ.get("GITHUB_TOKEN", ""))
    s = stats(days)
    print(f"read {len(days)} days from {source}")
    (ROOT / "assets" / "stats.svg").write_text(stats_svg(s))
    (ROOT / "assets" / "stats-narrow.svg").write_text(stats_svg(s, narrow=True))
    readme(ROOT / "README.md", s)
    print("assets/stats.svg:", {k: s[k] for k in ("total", "typical", "active", "since", "start", "current", "longest", "first", "last")})
    print("by weekday, median active day:", dict(zip(DAYS, s["by_day"])))
    print("by weekday, share of days active:", {d: round(v, 2) for d, v in zip(DAYS, s["share"])})
    for path in sys.argv[1:]:
        rewrite(path, s)
