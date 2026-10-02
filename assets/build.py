"""Builds the profile README's static images (assets/*.svg) and the kit the daily workflow draws with (assets/kit.json).

    uv run --with fonttools --with brotli --with uharfbuzz python assets/build.py

The design system, wentao.gg's identity set the way the Awwwards Sites of the Year set theirs:
  type    Space Grotesk for words and numbers, JetBrains Mono for labels, indexes and commands: wentao.gg's own pair.
          HarfBuzz shapes every line (kerning, tabular figures) and fontTools draws it as outlines, because an SVG shown
          as an <img> cannot load web fonts.
  colour  ink #0b0d12, paper #e8e8e2, muted #8b8b94 (#626c7a on light) and one blue, #2563eb (#60a5fa as text on dark).
          Grounds are transparent and each image follows prefers-color-scheme by itself; the banner is a terminal, dark in both.
  motion  one beat is 100 ms, wentao.gg's ESCAPEMENT. decode: a word resolves out of code glyphs; type: a command types
          and a block cursor blinks; draw: a hairline draws left to right; rise: rows slide up out of a mask; drift: the
          stack marquee. All of it is CSS animation over a final frame: an intro plays once and rests there, and the final
          frame is what prefers-reduced-motion and renderers that do not animate show. Only cursors, the marquee and the
          banner's loop keep moving.
"""
import base64
import io
import json
import math
import random
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent
# the latin subsets Google Fonts serves (variable: JetBrains Mono wght 400-800, Space Grotesk wght 300-700)
JBM_URL = "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbv2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8yKwBNntkaToggR7BYRbKPxDcwgknk-4.woff2"
SG_URL = "https://fonts.gstatic.com/s/spacegrotesk/v22/V8mDoQDjQSkFtoMM3T6r8E7mPbF4C_k3HqU.woff2"
BEAT = 0.1

# ---------------------------------------------------------------------------------------------------- type
_raw = {"jb": urllib.request.urlopen(JBM_URL).read(), "sg": urllib.request.urlopen(SG_URL).read()}
KIT = {}
for key, fam, wght in [("sg400", "sg", 400), ("sg500", "sg", 500), ("sg700", "sg", 700),
                       ("jb400", "jb", 400), ("jb500", "jb", 500), ("jb700", "jb", 700)]:
    tt = instancer.instantiateVariableFont(TTFont(io.BytesIO(_raw[fam])), {"wght": wght})
    tt.flavor = None
    buf = io.BytesIO()
    tt.save(buf)
    KIT[key] = dict(tt=tt, gs=tt.getGlyphSet(), upm=tt["head"].unitsPerEm, order=tt.getGlyphOrder(),
                    hb=hb.Font(hb.Face(buf.getvalue())), raw=buf.getvalue())


def num(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def shape(key, text, size, tracking=0.0, features=None):
    """[(glyph, x, char)], width: HarfBuzz-shaped, kerned, tracking in em."""
    k = KIT[key]
    sc = size / k["upm"]
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(k["hb"], buf, features or {})
    out, x = [], 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        out.append((k["order"][info.codepoint], x + pos.x_offset * sc, text[info.cluster]))
        x += pos.x_advance * sc + tracking * size
    return out, (x - tracking * size) if text else 0.0


def outline(key, glyph, x, baseline, size):
    k = KIT[key]
    sc = size / k["upm"]
    pen = SVGPathPen(k["gs"], ntos=num)
    k["gs"][glyph].draw(TransformPen(pen, (sc, 0, 0, -sc, x, baseline)))
    return pen.getCommands()


def line(key, text, x, baseline, size, anchor="start", tracking=0.0, features=None):
    """[(char, d, x)] plus the line's left edge and width."""
    glyphs, w = shape(key, text, size, tracking, features)
    x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
    return [(ch, outline(key, g, x0 + gx, baseline, size), x0 + gx) for g, gx, ch in glyphs], x0, w


def path_group(glyphs, cls, extra=""):
    return f'<g class="{cls}"{extra}>' + "".join(f'<path d="{d}"/>' for _, d, _ in glyphs if d) + "</g>"


# wentao.gg's mark, app/icon.svg: the heptadecagon (17 sides, corners softened), drawn in a 100 x 100 box
HEPTA = ("M47.54 9.46Q50 9 52.46 9.46L62.35 11.31Q64.81 11.77 66.94 13.08L75.5 18.38Q77.62 19.7 79.13 21.7L85.2 29.73"
         "Q86.7 31.72 87.39 34.13L90.14 43.81Q90.83 46.22 90.59 48.71L89.67 58.73Q89.43 61.22 88.32 63.46L83.83 72.47"
         "Q82.72 74.71 80.87 76.39L73.43 83.17Q71.58 84.86 69.25 85.76L59.86 89.4Q57.53 90.3 55.03 90.3L44.97 90.3"
         "Q42.47 90.3 40.14 89.4L30.75 85.76Q28.42 84.86 26.57 83.17L19.13 76.39Q17.28 74.71 16.17 72.47L11.68 63.46"
         "Q10.57 61.22 10.33 58.73L9.41 48.71Q9.17 46.22 9.86 43.81L12.61 34.13Q13.3 31.72 14.8 29.73L20.87 21.7"
         "Q22.38 19.7 24.5 18.38L33.06 13.08Q35.19 11.77 37.65 11.31Z")


def hepta(cx, cy, d, cls, extra=""):
    s = d / 81.3  # the mark spans 81.3 of its 100 units
    return f'<path class="{cls}" transform="translate({num(cx - 50 * s)} {num(cy - 50 * s)}) scale({num(s)})" d="{HEPTA}"{extra}/>'


def arrow(x, y, s, cls):
    """A drawn north-east arrow in an s x s box at (x, y): the latin subsets carry no arrows."""
    return (f'<path class="{cls}" fill="none" stroke-width="{num(s * 0.13)}" stroke-linecap="square" '
            f'd="M{num(x + s * 0.12)} {num(y + s * 0.88)}L{num(x + s * 0.86)} {num(y + s * 0.14)}'
            f'M{num(x + s * 0.3)} {num(y + s * 0.12)}H{num(x + s * 0.88)}V{num(y + s * 0.7)}"/>')


# ---------------------------------------------------------------------------------------------------- colour + motion
THEME = """
.fg{fill:#e8e8e2}.mu{fill:#8b8b94}.ac{fill:#60a5fa}.bl{fill:#2563eb}
.sfg{stroke:#e8e8e2}.smu{stroke:#8b8b94}.shl{stroke:#30363d}.sac{stroke:#60a5fa}.sbl{stroke:#2563eb}
@media (prefers-color-scheme: light){.fg{fill:#0b0d12}.mu{fill:#626c7a}.ac{fill:#2563eb}
.sfg{stroke:#0b0d12}.smu{stroke:#626c7a}.shl{stroke:#d0d7de}.sac{stroke:#2563eb}}
"""
MOTION = """
@keyframes wait{0%,100%{opacity:0}}
@keyframes flash{0%,100%{opacity:1}}
@keyframes draw{from{stroke-dashoffset:1}}
@keyframes blink{0%,49.9%{opacity:1}50%,100%{opacity:0}}
@keyframes rise{from{transform:translateY(40px)}}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{transform-box:fill-box;transform-origin:center;animation:spin 60s linear infinite}
@media (prefers-reduced-motion: reduce){*{animation:none!important}}
"""


def svg(w, h, title, desc, body, css="", dark_card=False):
    style = (css if dark_card else THEME + css) + MOTION
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-labelledby="t d"><title id="t">{escape(title)}</title><desc id="d">{escape(desc)}</desc>'
            f'<!-- Generated by assets/build.py. -->\n<style>{style}</style>\n{body}\n</svg>\n')


# ---------------------------------------------------------------------------------------------------- documents
def num1(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


class Doc:
    """One image's glyphs, each drawn once in <defs> and placed with <use>: a letter that repeats costs a few bytes."""

    def __init__(self):
        self.ids, self.defs = {}, []

    def glyph(self, key, g, size):
        k = (key, g, round(size, 3))
        if k not in self.ids:
            kk = KIT[key]
            sc = size / kk["upm"]
            pen = SVGPathPen(kk["gs"], ntos=num1)
            kk["gs"][g].draw(TransformPen(pen, (sc, 0, 0, -sc, 0, 0)))
            d = pen.getCommands()
            self.ids[k] = None
            if d:
                self.ids[k] = f"g{len(self.defs)}"
                self.defs.append(f'<path id="{self.ids[k]}" d="{d}"/>')
        return self.ids[k]

    def use(self, key, g, size, x, y, attrs=""):
        gid = self.glyph(key, g, size)
        return f'<use href="#{gid}" x="{num1(x)}" y="{num1(y)}"{attrs}/>' if gid else ""

    def text(self, key, s, x, y, size, cls=None, anchor="start", tracking=0.0, features=None, attrs=""):
        glyphs, w = shape(key, s, size, tracking, features)
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        inner = "".join(self.use(key, g, size, x0 + gx, y) for g, gx, _ in glyphs)
        return (f'<g class="{cls}"{attrs}>{inner}</g>' if cls else inner), x0, w

    def render(self, extra=""):
        return "<defs>" + "".join(self.defs) + extra + "</defs>"


def wait(t):  # hidden until t, then the element's own state
    return f"animation:wait {num(t)}s step-end"


def flash(t):  # shown for one beat at t
    return f"animation:flash {num(BEAT)}s step-end {num(t)}s"


def draw(t, dur=0.8):
    return f"animation:draw {num(dur)}s cubic-bezier(.65,0,.35,1) {num(t)}s both"


CODE = "01<>/{}[]#*+=_%$&;:?!"


def decode(doc, key, text, x, baseline, size, t0, rnd, cls="fg", code_cls="ac", frames=4):
    """The word resolves out of code glyphs, letter by letter, one beat apart (Igloo Inc's scramble)."""
    glyphs, w = shape(key, text, size)
    parts = []
    for i, (g, gx, ch) in enumerate(glyphs):
        if ch == " ":
            continue
        settle = t0 + (i + frames) * BEAT
        nxt = glyphs[i + 1][1] if i + 1 < len(glyphs) else w
        cx = x + (gx + nxt) / 2
        for j in range(frames):
            (cg, _, _), = shape("jb700", rnd.choice(CODE), size * 0.92)[0]
            cw = shape("jb700", "0", size * 0.92)[1]
            parts.append(doc.use("jb700", cg, size * 0.92, cx - cw / 2, baseline,
                                 f' class="{code_cls}" opacity="0" style="{flash(t0 + (i + j) * BEAT)}"'))
        parts.append(doc.use(key, g, size, x + gx, baseline, f' class="{cls}" style="{wait(settle)}"'))
    return "".join(parts), w, t0 + (len(glyphs) + frames) * BEAT


def typed(doc, key, text, x, baseline, size, t0, step, cls, tracking=0.0):
    glyphs, w = shape(key, text, size, tracking)
    parts, t = [], t0
    for g, gx, ch in glyphs:
        parts.append(doc.use(key, g, size, x + gx, baseline, f' class="{cls}" style="{wait(t)}"'))
        t += step
    return "".join(parts), w, t


def cursor(x, y, w, h, t_on, cls="bl"):
    return (f'<rect class="{cls}" x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" rx="1" '
            f'style="animation:wait {num(t_on)}s step-end,blink 1.1s step-end {num(t_on)}s infinite"/>')


def hairline(x1, y, x2, t, dur=0.8, cls="shl"):
    return (f'<line class="{cls}" x1="{num(x1)}" y1="{num(y)}" x2="{num(x2)}" y2="{num(y)}" stroke-width="1" '
            f'pathLength="1" stroke-dasharray="1" style="{draw(t, dur)}"/>')


def hepta_at(cx, cy, d, cls):
    s = d / 81.3
    return f'<g transform="translate({num(cx - 50 * s)} {num(cy - 50 * s)}) scale({num(s)})"><path class="{cls}" d="{HEPTA}"/></g>'


# ---------------------------------------------------------------------------------------------------- components
W = 860


def header(index, title, command, seed):
    """(01) + a decoded title + a typed shell command with a blinking cursor + a drawn hairline; 24 px of air above."""
    rnd, doc = random.Random(seed), Doc()
    top, H = 24, 128
    idx, _, _ = doc.text("jb500", index, 0, top + 16, 13, "ac", tracking=0.08, attrs=f' style="{wait(0)}"')
    word, _, _ = decode(doc, "sg700", title, -2, top + 74, 54, 0.15, rnd)
    cw = shape("jb400", command, 15)[1]
    cx0 = W - 14 - cw
    dollar, _, _ = doc.text("jb400", "$ ", cx0, top + 72, 15, "ac", anchor="end", attrs=f' style="{wait(0.45)}"')
    cmd, _, t_cmd = typed(doc, "jb400", command, cx0, top + 72, 15, 0.5, 0.045, "mu")
    body = (idx + word + dollar + cmd + cursor(W - 10, top + 59, 8, 16, t_cmd) + hairline(0, H - 1.5, W, 0.1, 1.0))
    return svg(W, H, f"{index} {title}: {command}",
               f"Section {index}, {title}. The title resolves out of code glyphs; the command {command} types beside it.",
               doc.render() + body)


ROWS = [  # (group, name, role, years, place): wentao.gg's app/lib/content/experience.ts and education.ts
    ("NOW", "Mercor", "Engineering Lead, Applied AI", "2026–NOW", "San Francisco"),
    ("BEFORE", "Meta", "Data Engineer", "2024–26", "New York"),
    ("", "Cherre", "Software Engineer", "2022–24", "New York"),
    ("", "Mashey", "Software Engineer", "2021–22", "Remote"),
    ("", "Jefferson Street Technologies", "Machine Learning Engineer", "2020–21", "Remote"),
    ("STUDIED", "University of Pennsylvania", "MS Robotics (AI)", "", "Philadelphia"),
    ("", "Carnegie Mellon University", "MS, BS Mechanical Engineering", "", "Pittsburgh"),
    ("OFF-HOURS", "Powerlifting, photography", "", "", ""),
]


def about():
    doc = Doc()
    rh, top = 44, 6
    H = top + rh * len(ROWS) + 8
    body, clips = [], []
    for i, (grp, name, role, years, place) in enumerate(ROWS):
        y0 = top + i * rh
        base = y0 + 28
        t = 0.2 + i * BEAT
        clips.append(f'<clipPath id="r{i}"><rect x="0" y="{y0}" width="{W}" height="{rh}"/></clipPath>')
        row = []
        if grp:
            row.append(doc.text("jb500", grp, 0, base - 1, 11.5, "ac" if grp == "NOW" else "mu", tracking=0.1)[0])
        row.append(doc.text("sg500", name, 128, base, 19, "fg")[0])
        if role:
            row.append(doc.text("sg400", role, 420, base, 15.5, "mu")[0])
        meta = "  ·  ".join(v for v in (years, place.upper()) if v)
        if meta:
            row.append(doc.text("jb400", meta, W, base - 1, 11.5, "mu", anchor="end", tracking=0.06)[0])
        body.append(f'<g clip-path="url(#r{i})"><g style="animation:rise .7s cubic-bezier(.2,.8,.2,1) {num(t)}s both">'
                    + "".join(row) + "</g></g>")
        if i < len(ROWS) - 1 and ROWS[i + 1][0]:
            body.append(hairline(0, y0 + rh, W, t + 0.15, 0.9))
    body.append(hairline(0, H - 1.5, W, 0.2 + len(ROWS) * BEAT, 0.9))
    alt = "; ".join(", ".join(v for v in (f"{g}: {n}" if g else n, r, y, p) if v) for g, n, r, y, p in ROWS)
    return svg(W, H, "About Wentao He", alt, doc.render("".join(clips)) + "".join(body))


STACK = [["Python", "TypeScript", "Go", "Java", "React", "Next.js", "three.js", "Tailwind", "Node.js"],
         ["Postgres", "GCP", "AWS", "Docker", "Kubernetes", "PyTorch", "TensorFlow", "Vercel", "Supabase"]]


def stack():
    doc = Doc()
    H, size, gap = 128, 40, 34
    rows, css, seqs = [], [], []
    for r, names in enumerate(STACK):
        base = 46 + r * 62
        x, seq = 0.0, []
        for n in names:
            g_, _, w = doc.text("sg700", n, x, base, size)
            seq.append(g_)
            x += w + gap / 2
            seq.append(hepta_at(x, base - size * 0.34, 9, "bl"))
            x += gap / 2
        period = x
        cls = "fg" if r == 0 else "smu"
        seqs.append(f'<g id="row{r}" class="{cls}"{"" if r == 0 else " fill=" + chr(34) + "none" + chr(34) + " stroke-width=" + chr(34) + "1.1" + chr(34)}>{"".join(seq)}</g>')
        copies = math.ceil(W / period) + 1
        uses = "".join(f'<use href="#row{r}" x="{num(k * period)}"/>' for k in range(copies))
        dur = period / 26  # about 26 px a second
        if r == 0:
            css.append(f"@keyframes drift0{{to{{transform:translateX(-{num(period)}px)}}}}")
        else:
            css.append(f"@keyframes drift1{{from{{transform:translateX(-{num(period)}px)}}to{{transform:translateX(0)}}}}")
        rows.append(f'<g mask="url(#fade)"><g style="animation:drift{r} {num(dur)}s linear infinite">{uses}</g></g>')
    fade = ('<linearGradient id="fd" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset=".09" stop-color="#fff"/><stop offset=".91" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
            f'</linearGradient><mask id="fade" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
            f'<rect width="{W}" height="{H}" fill="url(#fd)"/></mask>')
    alt = ", ".join(STACK[0] + STACK[1])
    return svg(W, H, "Stack: " + alt, "Two rows of names drift past in opposite directions in Space Grotesk, the second "
               "outlined, wentao.gg's heptadecagon between them.", doc.render(fade + "".join(seqs)) + "".join(rows), "".join(css))


def link(label, icon=False, delay=0.0):
    doc = Doc()
    size, track = 12.5, 0.12
    w = shape("jb500", label, size, track)[1]
    pad, ic, ar = 20, (22 if icon else 0), 12
    Wb, Hb = pad + ic + w + 12 + ar + pad, 44
    x = pad + ic
    body = [f'<rect class="shl" x=".75" y=".75" width="{num(Wb - 1.5)}" height="{Hb - 1.5}" rx="{(Hb - 1.5) / 2}" fill="none" stroke-width="1.5"/>']
    if icon:
        body.append(hepta_at(pad + 7, Hb / 2, 13, "bl"))
    body.append(doc.text("jb500", label, x, Hb / 2 + 4.5, size, "fg", tracking=track)[0])
    ax, ay = x + w + 12, Hb / 2 - ar / 2
    css = ("@keyframes nudge{0%,84%{transform:translate(0,0);opacity:1}88%{transform:translate(7px,-7px);opacity:0}"
           "88.1%{transform:translate(-7px,7px);opacity:0}93%,100%{transform:translate(0,0);opacity:1}}")
    body.append(f'<clipPath id="ac"><rect x="{num(ax - 2)}" y="{num(ay - 2)}" width="{ar + 4}" height="{ar + 4}"/></clipPath>'
                f'<g clip-path="url(#ac)"><g style="animation:nudge 6s ease-in-out {num(delay)}s infinite">{arrow(ax, ay, ar, "sfg")}</g></g>')
    return svg(math.ceil(Wb), Hb, label, f"{label}, a link", doc.render() + "".join(body), css)


def footer():
    doc = Doc()
    H = 96
    body = [hairline(0, 1, W, 0.1, 1.0), hepta_at(9, 45, 16, "bl spin")]
    prompt, px0, pw = doc.text("jb400", "wentao@sf ~ $ ", 30, 50, 14, "mu")
    ex, _, t_ex = typed(doc, "jb400", "exit", px0 + pw, 50, 14, 0.9, 0.12, "fg")
    done = doc.text("jb400", "[Process completed]", 30, 74, 14, "mu", attrs=f' style="{wait(t_ex + 0.5)}"')[0]
    right1 = doc.text("jb500", "© 2026 WENTAO HE", W, 50, 11.5, "fg", anchor="end", tracking=0.1)[0]
    right2 = doc.text("jb400", "SAN FRANCISCO  ·  37.77° N, 122.42° W", W, 74, 11.5, "mu", anchor="end", tracking=0.06)[0]
    body += [prompt, ex, done, right1, right2]
    return svg(W, H, "wentao@sf ~ $ exit", "The session ends: exit types, then [Process completed]. © 2026 Wentao He, San Francisco.",
               doc.render() + "".join(body))


# ---------------------------------------------------------------------------------------------------- the banner
BW, BH = 1200, 320
WX, WY, WW, WH = 170, 44, 860, 236  # the terminal window
LX = WX + 34


def banner(seed=17):
    """A terminal types whoami, the name, a role line it deletes and retypes as the roles; JetBrains Mono, 12 s loop."""
    rnd = random.Random(seed)
    T, OFF = 12.0, 11.4
    pct = lambda t: num(100 * t / T) + "%"
    p_user, x1, w1 = line("jb400", "wentao@sf", LX, 122, 22)
    p_path, x2, w2 = line("jb400", " ~ ", x1 + w1, 122, 22)
    p_dollar, x3, w3 = line("jb400", "$ ", x2 + w2, 122, 22)
    x_cmd = x3 + w3
    p_cmd, _, _ = line("jb400", "whoami", x_cmd, 122, 22)
    p_name, _, _ = line("jb700", "Wentao He", LX - 3, 204, 78)
    p_pre, xp0, wp = line("jb400", "// ", LX, 250, 19)
    p_a, _, _ = line("jb400", "Engineering Lead @ Mercor · San Francisco", xp0 + wp, 250, 19)
    p_b, _, _ = line("jb400", "engineer · developer · photographer · powerlifter", xp0 + wp, 250, 19)
    p_title, _, _ = line("jb400", "wentao@sf: ~ — zsh", WX + WW / 2, WY + 22, 13, anchor="middle")
    adv = lambda size: 0.6 * size

    def times(glyphs, t0, lo, hi, space=None):
        out, t = [], t0
        for ch, _, _ in glyphs:
            out.append(t)
            t += space if (space and ch == " ") else rnd.uniform(lo, hi)
        return out
    t_cmd = times(p_cmd, 0.75, 0.08, 0.16)
    enter2 = t_cmd[-1] + 0.45
    t_name = times(p_name, enter2 + 0.2, 0.08, 0.14, space=0.17)
    enter3 = t_name[-1] + 0.3
    t_pre = times(p_pre, enter3 + 0.2, 0.03, 0.05)
    t_a = times(p_a, t_pre[-1] + 0.05, 0.018, 0.032)
    del0 = t_a[-1] + 2.2
    t_del = [del0 + 0.016 * k for k in range(len(p_a))]
    t_b = times(p_b, t_del[-1] + 0.3, 0.018, 0.032)
    css, n_kf = [], [0]

    def glyph(d, on, off, cls, shown=True):
        n_kf[0] += 1
        k = f"k{n_kf[0]}"
        css.append(f"@keyframes {k}{{0%{{opacity:0}}{pct(on)}{{opacity:1}}{pct(off)},100%{{opacity:0}}}}")
        hidden = "" if shown else ' opacity="0"'
        return f'<path class="{cls}"{hidden} style="animation:{k} {num(T)}s step-end infinite" d="{d}"/>'
    g_cmd = "".join(glyph(d, t, OFF, "tx") for (_, d, _), t in zip(p_cmd, t_cmd) if d)
    g_name = "".join(glyph(d, t, OFF, "nm") for (_, d, _), t in zip(p_name, t_name) if d)
    n = len(p_a)
    g_cmt = ("".join(glyph(d, t, OFF, "cm") for (_, d, _), t in zip(p_pre, t_pre) if d)
             + "".join(glyph(d, t_a[i], t_del[n - 1 - i], "cm") for i, (_, d, _) in enumerate(p_a) if d)
             + "".join(glyph(d, t, OFF, "cm", shown=False) for (_, d, _), t in zip(p_b, t_b) if d))

    def box(row, x):
        return {1: (x, 104, adv(22), 23.3), 2: (x, 144, adv(78), 72), 3: (x, 234.4, adv(19), 20.1)}[row]
    bp = [(0.0,) + box(1, x_cmd)]
    bp += [(t,) + box(1, gx + adv(22)) for (_, _, gx), t in zip(p_cmd, t_cmd)]
    bp.append((enter2,) + box(2, p_name[0][2]))
    bp += [(t,) + box(2, gx + adv(78)) for (_, _, gx), t in zip(p_name, t_name)]
    bp.append((enter3,) + box(3, LX))
    bp += [(t,) + box(3, gx + adv(19)) for (_, _, gx), t in zip(p_pre, t_pre)]
    bp += [(t,) + box(3, gx + adv(19)) for (_, _, gx), t in zip(p_a, t_a)]
    bp += [(t_del[n - 1 - i],) + box(3, gx) for i, (_, _, gx) in enumerate(p_a)]
    bp += [(t,) + box(3, gx + adv(19)) for (_, _, gx), t in zip(p_b, t_b)]
    bp.append((OFF,) + box(1, x_cmd))
    seen = {}
    for b in sorted(bp, key=lambda b: b[0]):
        seen[pct(b[0])] = b
    tf = lambda b: f"translate({num(b[1])}px,{num(b[2])}px) scale({num(b[3])},{num(b[4])})"
    css.append("@keyframes cur{" + "".join(f"{k}{{transform:{tf(b)}}}" for k, b in seen.items()) + "}")
    busy = [(t_cmd[0], t_cmd[-1] + 0.12), (t_name[0], t_name[-1] + 0.12), (t_pre[0], t_a[-1] + 0.12),
            (t_del[0], t_del[-1] + 0.05), (t_b[0], t_b[-1] + 0.12)]
    ob, s = [], 0.0
    for a, b in busy + [(T, T)]:
        on = 1
        while s < a - 1e-9:
            ob.append((s, on))
            s = min(s + 0.5, a)
            on = 1 - on
        if a < T:
            ob.append((a, 1))
            s = b
    css.append("@keyframes curb{" + "".join(f"{pct(t)}{{opacity:{v}}}" for t, v in ob) + "}")
    rest = box(3, p_a[-1][2] + adv(19))  # the final frame: the role line typed, the cursor after it
    cursor_el = (f'<g style="animation:curb {num(T)}s step-end infinite"><rect class="cu" width="1" height="1" '
                 f'transform="translate({num(rest[0])} {num(rest[1])}) scale({num(rest[2])} {num(rest[3])})" '
                 f'style="animation:cur {num(T)}s step-end infinite"/></g>')
    rain = []
    for x in range(22, BW, 46):
        tsp = "".join(f'<tspan x="{x}" dy="{34 if j else 0}">{escape(rnd.choice("{}[]();<>/=+*01"))}</tspan>' for j in range(9))
        dur, off, op = rnd.uniform(7, 13), rnd.uniform(0, 13), rnd.uniform(0.16, 0.34)
        rain.append(f'<text y="-20" font-size="17" opacity="{num(op)}" style="animation:fall {num(dur)}s linear -{num(off)}s infinite">{tsp}</text>')
    css.append("@keyframes fall{from{transform:translateY(-330px)}to{transform:translateY(360px)}}")
    style = (".tx{fill:#e8e8e2}.cm{fill:#8b8b94}.nm{fill:url(#ink)}.cu{fill:#2563eb;fill-opacity:.92}" + "".join(css))
    sp = lambda gl, fill: f'<g fill="{fill}">' + "".join(f'<path d="{d}"/>' for _, d, _ in gl if d) + "</g>"
    body = f"""<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b0d12"/><stop offset="1" stop-color="#0d1526"/></linearGradient>
<linearGradient id="ink" gradientUnits="userSpaceOnUse" x1="{LX}" y1="0" x2="{LX + 430}" y2="0"><stop offset="0" stop-color="#e8e8e2"/><stop offset=".55" stop-color="#e8e8e2"/><stop offset="1" stop-color="#93c5fd"/></linearGradient>
<radialGradient id="vign" cx=".5" cy=".5" r=".8"><stop offset=".6" stop-color="#0b0d12" stop-opacity="0"/><stop offset="1" stop-color="#0b0d12" stop-opacity=".6"/></radialGradient>
<filter id="glow" x="-10%" y="-40%" width="120%" height="180%"><feGaussianBlur in="SourceGraphic" stdDeviation="7" result="b"/><feColorMatrix in="b" type="matrix" values="0 0 0 0 .145 0 0 0 0 .388 0 0 0 0 .922 0 0 0 .7 0" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="shadow" x="-10%" y="-20%" width="120%" height="150%"><feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#2563eb" flood-opacity=".22"/></filter>
<clipPath id="card"><rect width="{BW}" height="{BH}" rx="18"/></clipPath>
<clipPath id="win"><rect x="{WX}" y="{WY}" width="{WW}" height="{WH}" rx="14"/></clipPath>
</defs>
<g clip-path="url(#card)">
<rect width="{BW}" height="{BH}" fill="url(#bg)"/>
<g fill="#2563eb" font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-weight="600">{"".join(rain)}</g>
<rect width="{BW}" height="{BH}" fill="url(#vign)"/>
<g filter="url(#shadow)"><rect x="{WX}" y="{WY}" width="{WW}" height="{WH}" rx="14" fill="#0d1117" fill-opacity=".96" stroke="#1f2a44" stroke-width="1.5"/></g>
<g clip-path="url(#win)"><rect x="{WX}" y="{WY}" width="{WW}" height="34" fill="#111827"/><line x1="{WX}" y1="{WY + 34}" x2="{WX + WW}" y2="{WY + 34}" stroke="#1f2a44"/></g>
<circle cx="{WX + 22}" cy="{WY + 17}" r="6" fill="#ff5f57"/><circle cx="{WX + 42}" cy="{WY + 17}" r="6" fill="#febc2e"/><circle cx="{WX + 62}" cy="{WY + 17}" r="6" fill="#28c840"/>
{sp(p_title, "#8b8b94")}{sp(p_user, "#60a5fa")}{sp(p_path, "#8b8b94")}{sp(p_dollar, "#e8e8e2")}
{g_cmd}<g filter="url(#glow)">{g_name}</g>{g_cmt}{cursor_el}
</g>"""
    return svg(BW, BH, "Wentao He", "A terminal types whoami, then Wentao He, then // Engineering Lead @ Mercor · San Francisco, "
               "which it deletes and retypes as // engineer · developer · photographer · powerlifter; JetBrains Mono, a "
               "blinking cursor, falling code symbols behind.", body, style, dark_card=True)


# ---------------------------------------------------------------------------------------------------- the daily kit
STAT_SIZE = 54
MONO_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,.–—·/+%:"


def kit():
    """What scripts/daily.py draws the stats with, and the fonts it gives the 3D image's own text."""
    doc = Doc()
    digits, cell = {}, 0.0
    for ch in "0123456789,":
        (g, _, _), = shape("sg700", ch, STAT_SIZE, features={"tnum": True})[0]
        w = shape("sg700", ch, STAT_SIZE, features={"tnum": True})[1]
        kk = KIT["sg700"]
        pen = SVGPathPen(kk["gs"], ntos=num1)
        kk["gs"][g].draw(TransformPen(pen, (STAT_SIZE / kk["upm"], 0, 0, -STAT_SIZE / kk["upm"], 0, 0)))
        digits[ch] = {"d": pen.getCommands(), "w": round(w, 2)}
        if ch != ",":
            cell = max(cell, w)
    mono = {}
    for ch in MONO_CHARS:
        (g, _, _), = shape("jb500", ch, 11.5)[0]
        kk = KIT["jb500"]
        pen = SVGPathPen(kk["gs"], ntos=num1)
        kk["gs"][g].draw(TransformPen(pen, (11.5 / kk["upm"], 0, 0, -11.5 / kk["upm"], 0, 0)))
        mono[ch] = pen.getCommands()

    def subset(key, text):
        f = TTFont(io.BytesIO(KIT[key]["raw"]))
        opts = Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "tnum"]
        sub = Subsetter(opts)
        sub.populate(text=text)
        sub.subset(f)
        buf = io.BytesIO()
        f.flavor = "woff2"
        f.save(buf)
        return base64.b64encode(buf.getvalue()).decode()
    ascii_ = "".join(chr(c) for c in range(32, 127)) + "·—–°"
    return {"size": STAT_SIZE, "cell": round(cell, 2), "digits": digits,
            "mono": {"size": 11.5, "tracking": 0.1, "advance": round(0.6 * 11.5, 3), "glyphs": mono},
            "css": THEME + MOTION, "fonts": {"mono": subset("jb400", ascii_), "display": subset("sg700", ascii_)}}


if __name__ == "__main__":
    files = {
        "banner.svg": banner(),
        "h-about.svg": header("01", "About", "whoami --verbose", 1),
        "h-stack.svg": header("02", "Stack", "ls ~/stack", 2),
        "h-activity.svg": header("03", "Activity", "git log --since=1y", 3),
        "about.svg": about(),
        "stack.svg": stack(),
        "link-site.svg": link("WENTAO.GG", icon=True, delay=0.0),
        "link-linkedin.svg": link("LINKEDIN", delay=0.4),
        "link-email.svg": link("ME@WENTAO.GG", delay=0.8),
        "footer.svg": footer(),
    }
    for name, content in files.items():
        (OUT / name).write_text(content)
    (OUT / "kit.json").write_text(json.dumps(kit(), separators=(",", ":")))
    for name in list(files) + ["kit.json"]:
        print(f"{name:20s} {(OUT / name).stat().st_size:>7,d} bytes")
