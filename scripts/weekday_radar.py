"""Plots contributions by weekday in place of the 3D contribution image's radar, and drops its language donut.

github-profile-3d-contrib draws a Commit / Issue / PullReq / Review / Repo radar and a language donut. GitHub reports
private organisation work only as a daily total, never by type or language, so for this account they showed Commit 6
and "other" beside 7,789 contributions. The calendar's daily totals do count private work, so the radar plots those by
weekday instead, and the headline is rewritten from the same calendar: the seven numbers always add up to it.

    GITHUB_TOKEN=... USERNAME=wth-lg python3 scripts/weekday_radar.py profile-3d-contrib/*.svg
"""
import json
import math
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # clockwise from the top
R_OUT, R_LABEL = 156, 194  # the tool's outer ring; the labels sit just outside it


def calendar(user, token):
    query = ("query($u: String!) { user(login: $u) { contributionsCollection { contributionCalendar {"
             " totalContributions weeks { contributionDays { weekday contributionCount } } } } } }")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"u": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    cal = json.load(urllib.request.urlopen(req))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    by_day = [0] * 7  # Mon .. Sun; GitHub's weekday 0 is Sunday
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            by_day[(day["weekday"] + 6) % 7] += day["contributionCount"]
    assert sum(by_day) == cal["totalContributions"], (sum(by_day), cal["totalContributions"])
    return cal["totalContributions"], by_day


def nice_step(raw):
    mag = 10 ** math.floor(math.log10(max(raw, 1)))
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)


def short(n):
    return f"{n / 1000:g}K" if n >= 1000 else f"{n:g}"


def el(tag, attrs, text=None, parent=None):
    e = ET.Element(f"{{{NS}}}{tag}", {k: str(v) for k, v in attrs.items()}) if parent is None else \
        ET.SubElement(parent, f"{{{NS}}}{tag}", {k: str(v) for k, v in attrs.items()})
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


def rewrite(path, total, by_day):
    tree = ET.parse(path)
    root = tree.getroot()
    kids = list(root)
    old = next((c for c in kids if c.find(f".//{{{NS}}}polygon[@class='radar']") is not None), None)
    if old is None:
        print(f"{path}: no radar, left alone")
        return
    for t in root.iter(f"{{{NS}}}text"):  # the headline, the tool's one number in fill-strong; before the radar adds more
        if t.get("class") == "fill-strong" and (t.text or "").strip().isdigit():
            t.text = str(total)
    root.insert(kids.index(old), radar(by_day, old.get("transform", "")))
    root.remove(old)
    for c in list(root):  # the language donut: the tool's group at translate(40, 520)
        if (c.get("transform") or "").replace(" ", "") == "translate(40,520)":
            root.remove(c)
    tree.write(path, encoding="unicode")
    print(f"{path}: weekday radar {dict(zip(DAYS, by_day))}, total {total}")


if __name__ == "__main__":
    total, by_day = calendar(os.environ["USERNAME"], os.environ["GITHUB_TOKEN"])
    for path in sys.argv[1:]:
        rewrite(path, total, by_day)
