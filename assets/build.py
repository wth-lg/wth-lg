"""Builds the profile README's static images (assets/*.svg) and the kit the daily workflow draws with (assets/kit.json).

    uv run --with fonttools --with brotli --with uharfbuzz python assets/build.py

The design system, wentao.gg's identity set the way the Awwwards Sites of the Year set theirs:
  type    Space Grotesk for words and numbers, JetBrains Mono for labels, indexes and commands: wentao.gg's own pair.
          HarfBuzz shapes every line (kerning, tabular figures) and fontTools draws it as outlines, because an SVG shown
          as an <img> cannot load web fonts.
  colour  ink #0b0d12, paper #e8e8e2, muted #8b8b94 (#626c7a on light) and one blue, #2563eb (#60a5fa as text on dark).
          Grounds are transparent and each image follows prefers-color-scheme by itself; the banner is a terminal, dark in both.
  motion  one beat is 100 ms, wentao.gg's ESCAPEMENT. decode: a word resolves out of code glyphs; type: a command types
          on half beats and a block cursor blinks once a second; draw: a hairline scales in from its left end; drift: the
          stack marquee. All of it is CSS animation over a final frame: an intro plays once and rests there, and the final
          frame is what prefers-reduced-motion and renderers that do not animate show. Every intro ends by 2 s, its delays
          on the beat; entrances ease (.2,.8,.2,1), draws (.65,0,.35,1), and only loops run linear. Only the banner's cursor
          and role line and the marquee keep moving; the other cursors blink four times and rest lit, the link arrows nudge
          twice.
  width   860 for the desktop column; under 600 px README.md shows each image's -narrow twin, 480 wide, drawn about 0.75x,
          so no label falls under 9 px on a 343 px column. The pills are drawn 1:1 and their narrow ones fit on one line.
"""
import io
import json
import math
import random
import re
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
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
    tt = instancer.instantiateVariableFont(TTFont(io.BytesIO(_raw[fam]), recalcTimestamp=False), {"wght": wght})
    tt.flavor = None
    tt.recalcTimestamp = False  # no build time in the fonts: the same inputs give the same bytes
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


# wentao.gg's mark, app/icon.svg: the heptadecagon (17 sides, corners softened), drawn in a 100 x 100 box
HEPTA = ("M47.54 9.46Q50 9 52.46 9.46L62.35 11.31Q64.81 11.77 66.94 13.08L75.5 18.38Q77.62 19.7 79.13 21.7L85.2 29.73"
         "Q86.7 31.72 87.39 34.13L90.14 43.81Q90.83 46.22 90.59 48.71L89.67 58.73Q89.43 61.22 88.32 63.46L83.83 72.47"
         "Q82.72 74.71 80.87 76.39L73.43 83.17Q71.58 84.86 69.25 85.76L59.86 89.4Q57.53 90.3 55.03 90.3L44.97 90.3"
         "Q42.47 90.3 40.14 89.4L30.75 85.76Q28.42 84.86 26.57 83.17L19.13 76.39Q17.28 74.71 16.17 72.47L11.68 63.46"
         "Q10.57 61.22 10.33 58.73L9.41 48.71Q9.17 46.22 9.86 43.81L12.61 34.13Q13.3 31.72 14.8 29.73L20.87 21.7"
         "Q22.38 19.7 24.5 18.38L33.06 13.08Q35.19 11.77 37.65 11.31Z")


def arrow(x, y, s, cls):
    """A drawn north-east arrow in an s x s box at (x, y): the latin subsets carry no arrows."""
    return (f'<path class="{cls}" fill="none" stroke-width="{num(s * 0.13)}" stroke-linecap="square" '
            f'd="M{num(x + s * 0.12)} {num(y + s * 0.88)}L{num(x + s * 0.86)} {num(y + s * 0.14)}'
            f'M{num(x + s * 0.3)} {num(y + s * 0.12)}H{num(x + s * 0.88)}V{num(y + s * 0.7)}"/>')


# ---------------------------------------------------------------------------------------------------- colour + motion
THEME = """
.fg{fill:#e8e8e2}.mu{fill:#8b8b94}.ac{fill:#60a5fa}.bl{fill:#2563eb}
.sfg{stroke:#e8e8e2}.smu{stroke:#8b8b94}.shl{stroke:#30363d}.spl{stroke:#6e7681}
@media (prefers-color-scheme: light){.fg{fill:#0b0d12}.mu{fill:#626c7a}.ac{fill:#2563eb}
.sfg{stroke:#0b0d12}.smu{stroke:#626c7a}.shl{stroke:#d0d7de}.spl{stroke:#8c959f}}
"""
# drawx scales a rule in, so a renderer that does not animate draws it whole
MOTION = """
@keyframes wait{0%,100%{opacity:0}}
@keyframes flash{0%,100%{opacity:1}}
@keyframes drawx{from{transform:scaleX(0)}}
@keyframes blink{0%,49.9%{opacity:1}50%,100%{opacity:0}}
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


ENTER, DRAW = "cubic-bezier(.2,.8,.2,1)", "cubic-bezier(.65,0,.35,1)"


def draw(t, dur=0.8):
    return f"animation:drawx {num(dur)}s {DRAW} {num(t)}s both"


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


def cursor(x, y, w, h, t_on, blinks=4, cls="bl"):
    """A block cursor: shown at t_on, then blinks once a second, `blinks` times, and rests lit."""
    return (f'<rect class="{cls}" x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" rx="1" '
            f'style="animation:wait {num(t_on)}s step-end,blink 1s step-end {num(t_on)}s {blinks}"/>')


def hairline(x1, y, x2, t, dur=0.8, cls="shl"):
    return (f'<line class="{cls}" x1="{num(x1)}" y1="{num(y)}" x2="{num(x2)}" y2="{num(y)}" stroke-width="1" '
            f'style="transform-origin:{num(x1)}px 0;{draw(t, dur)}"/>')


def hepta_at(cx, cy, d, cls):
    s = d / 81.3  # the mark spans 81.3 of its 100 units
    return f'<g transform="translate({num(cx - 50 * s)} {num(cy - 50 * s)}) scale({num(s)})"><path class="{cls}" d="{HEPTA}"/></g>'


# ---------------------------------------------------------------------------------------------------- components
W, NARROW = 860, 480  # the README column's two widths: desktop, and phones (shown under 600 px, about 0.75x)


def header(index, title, command, seed, w=W):
    """(01) + a decoded title + a typed shell command with a cursor + a drawn hairline; 34 px of air above, 15 below.

    The title is 36 px, cap height 0.6 of the banner's name, so the name leads."""
    rnd, doc = random.Random(seed), Doc()
    base, H = 82, 112  # the title's baseline; the image's height
    idx, _, _ = doc.text("jb500", index, 0, base - 38, 13, "ac", tracking=0.08)
    word, _, _ = decode(doc, "sg700", title, -1, base, 36, 0.1, rnd)
    cw = shape("jb400", command, 15)[1]
    cx0 = w - 14 - cw
    dollar, _, _ = doc.text("jb400", "$ ", cx0, base - 2, 15, "ac", anchor="end", attrs=f' style="{wait(0.4)}"')
    cmd, _, t_cmd = typed(doc, "jb400", command, cx0, base - 2, 15, 0.5, 0.05, "mu")
    body = (idx + word + dollar + cmd + cursor(w - 10, base - 15, 8, 16, t_cmd) + hairline(0, base + 14.5, w, 0.1, 1.0))
    return svg(w, H, f"{index} {title}: {command}",
               f"Section {index}, {title}. The title resolves out of code glyphs; the command {command} types beside it.",
               doc.render() + body)


REPL = [  # (prompt, code, result, comment): the About, short, pointing at wentao.gg for the long version
    (">>> ", "wentao.multimodal", "['text', 'code', 'docs', 'tables', 'images', 'audio', 'video']", ""),
    (">>> ", "wentao.everything_else", "'https://wentao.gg'", "  # experience, projects, lifting tools"),
]


def about(w=W):
    """A Python session: what Multimodal means, then where everything else lives. Each command types to two letters past
    the dot and Tab completes it, as python3 -i does; results land two beats later, the last prompt by 1.9 s. A result too
    long for the box wraps as pprint's compact form does, and its comment drops to the next line."""
    doc = Doc()
    size, lh, x0, top = 15, 30, 26, 46
    fits = lambda s: shape("jb400", s, size)[1] <= w - 2 * x0

    def wrap(result, comment):  # [(result, comment)], one per line
        if fits(result + comment):
            return [(result, comment)]
        rows, cur = [], ""
        for item in re.split(r"(?<=,) ", result):
            if cur and not fits(cur + " " + item):
                rows.append(cur)
                cur = " " + item
            else:
                cur = f"{cur} {item}" if cur else item
        return [(r, "") for r in rows + [cur]] + ([("", comment.strip())] if comment else [])
    wraps = [wrap(result, comment) for _, _, result, comment in REPL]
    H = top + lh * (len(REPL) + sum(map(len, wraps)) + 1) - 2
    body = [f'<rect class="shl" x=".75" y=".75" width="{w - 1.5}" height="{H - 1.5}" rx="12" fill="none" stroke-width="1.5"/>',
            doc.text("jb400", "python3", w - 22, 28, 11.5 if w == W else 12.5, "mu", anchor="end", tracking=0.06)[0]]
    t, y = 0.1, top

    def tokens(s):  # strings blue, punctuation muted, the rest paper
        for m in re.finditer(r"'[^']*'|[\[\](),.]|[^'\[\](),.]+", s):
            tok = m.group(0)
            yield tok, ("st" if tok.startswith("'") else "mu" if tok in "[](),." else "fg")
    for (prompt, code, _, _), rows in zip(REPL, wraps):
        body.append(doc.text("jb400", prompt, x0, y, size, "ac", attrs=f' style="{wait(t)}"')[0])
        pw = shape("jb400", prompt, size)[1]
        cut = code.index(".") + 3
        typed_code, cw, t = typed(doc, "jb400", code[:cut], x0 + pw, y, size, t + BEAT, 0.05, "fg")
        done, _, _ = typed(doc, "jb400", code[cut:], x0 + pw + cw, y, size, t + BEAT / 2, 0, "fg")
        body.append(typed_code + done)
        t += BEAT / 2 + 2 * BEAT
        parts = []
        for result, comment in rows:
            y += lh
            x = x0
            for tok, cls in tokens(result):
                g_, _, w_ = doc.text("jb400", tok, x, y, size, cls)
                parts.append(g_)
                x += w_
            if comment:
                parts.append(doc.text("jb400", comment, x, y, size, "mu")[0])
        body.append(f'<g style="{wait(t)}">' + "".join(parts) + "</g>")
        t += BEAT
        y += lh
    body.append(doc.text("jb400", ">>> ", x0, y, size, "ac", attrs=f' style="{wait(t)}"')[0])
    body.append(cursor(x0 + shape("jb400", ">>> ", size)[1], y - 12.5, 9, 16, t))
    alt = " ".join(f"{p}{c} → {r}{cm}" for p, c, r, cm in REPL)
    css = ".st{fill:#93c5fd}@media (prefers-color-scheme: light){.st{fill:#1d4ed8}}"
    return svg(w, H, "About: a Python session", alt, doc.render() + "".join(body), css)


# Simple Icons (CC0) and, where a brand left it (AWS), Devicon (MIT); pinned, fetched at build time, drawn in the theme's ink
SIMPLE_ICONS = "https://cdn.jsdelivr.net/npm/simple-icons@16.33.0/icons/{}.svg"
DEVICON = "https://cdn.jsdelivr.net/gh/devicons/devicon@2.17.0/icons/{}.svg"
STACK = [  # (name, icon): a Simple Icons slug, "devicon:<path>", or "custom:agent". Rows alternate direction.
    # Evidence: his 1,428 merged PRs in Mercor-io (Go 645 PRs, Python 444, Rust 268), the manifests of his repos (PyTorch,
    # Hugging Face, scikit-learn, ONNX, the Anthropic and Gemini SDKs, the Claude Agent SDK, MCP, LangGraph, Harbor, Modal),
    # pwrlft (Swift, SwiftUI), wentao.gg (Next.js, React, three.js, Tailwind, Vercel, Supabase) and the roles on wentao.gg
    # (Java, PHP, SQL, Spark, Airflow, BigQuery, TensorFlow, PyTorch).
    [("Python", "python"), ("Go", "go"), ("Rust", "rust"), ("TypeScript", "typescript"), ("Swift", "swift"),
     ("Java", "devicon:java/java-plain"), ("Bash", "gnubash"), ("PHP", "php"), ("Next.js", "nextdotjs"), ("React", "react"),
     ("three.js", "threedotjs"), ("Tailwind CSS", "tailwindcss")],
    [("PyTorch", "pytorch"), ("TensorFlow", "tensorflow"), ("Hugging Face", "huggingface"), ("scikit-learn", "scikitlearn"),
     ("XGBoost", "custom:xgboost"), ("ONNX", "onnx"), ("Claude", "claude"), ("Gemini", "googlegemini"),
     ("OpenAI", "si13:openai"), ("LiteLLM", "custom:litellm"), ("MCP", "modelcontextprotocol"), ("LangGraph", "langgraph"),
     ("Agent harnesses", "custom:agent"), ("Modal", "modal"), ("NumPy", "numpy"), ("Polars", "polars"), ("Pydantic", "pydantic")],
    [("Temporal", "temporal"), ("Spark", "apachespark"), ("Airflow", "apacheairflow"), ("dbt", "si13:dbt"), ("BigQuery", "googlebigquery"),
     ("Parquet", "apacheparquet"), ("Arrow", "apachearrow"), ("DuckDB", "duckdb"), ("PostgreSQL", "postgresql"),
     ("Redis", "redis"), ("AWS", "devicon:amazonwebservices/amazonwebservices-plain-wordmark"), ("Google Cloud", "googlecloud"),
     ("Kubernetes", "kubernetes"), ("Docker", "docker"), ("Terraform", "terraform"), ("Helm", "helm"), ("Argo CD", "argo"),
     ("GitHub Actions", "githubactions"), ("Datadog", "datadog"), ("OpenTelemetry", "opentelemetry"), ("Vercel", "vercel"),
     ("Supabase", "supabase")],
]
# Brands the current Simple Icons dropped (OpenAI, dbt): its 13.21.0 release, CC0 then, pinned
SIMPLE_ICONS_13 = "https://cdn.jsdelivr.net/npm/simple-icons@13.21.0/icons/{}.svg"
# XGBoost: the first tree of the project's own logo (xgboost.ai/images/logo/xgboost-logo.svg; XGBoost is Apache-2.0), its
# five rings and four links redrawn as fills in a 24 box (the rings' holes wound against them, the links with them)
XGBOOST_ICON = "M5.42 4.12A3.12 3.12 0 1 1 11.65 4.12A3.12 3.12 0 1 1 5.42 4.12ZM7.73 4.12A0.81 0.81 0 1 0 9.35 4.12A0.81 0.81 0 1 0 7.73 4.12ZM1.06 12.13A3.12 3.12 0 1 1 7.29 12.13A3.12 3.12 0 1 1 1.06 12.13ZM3.37 12.13A0.81 0.81 0 1 0 4.98 12.13A0.81 0.81 0 1 0 3.37 12.13ZM9.77 12.06A3.12 3.12 0 1 1 16.01 12.06A3.12 3.12 0 1 1 9.77 12.06ZM12.08 12.06A0.81 0.81 0 1 0 13.7 12.06A0.81 0.81 0 1 0 12.08 12.06ZM10.45 19.88A3.12 3.12 0 1 1 16.69 19.88A3.12 3.12 0 1 1 10.45 19.88ZM12.76 19.88A0.81 0.81 0 1 0 14.38 19.88A0.81 0.81 0 1 0 12.76 19.88ZM16.71 16.33A3.12 3.12 0 1 1 22.94 16.33A3.12 3.12 0 1 1 16.71 16.33ZM19.02 16.33A0.81 0.81 0 1 0 20.63 16.33A0.81 0.81 0 1 0 19.02 16.33ZM8.32 6.23L5.86 10.73L3.83 9.62L6.3 5.12ZM10.78 5.44L13.14 9.72L11.12 10.84L8.76 6.55ZM14.13 14.53L13.49 18.71L11.2 18.35L11.85 14.18ZM15.22 11.71L19.5 13.86L18.47 15.92L14.19 13.78Z"
# LiteLLM: its monogram, traced from the project's own (BerriAI/litellm, litellm/proxy/logo_monogram.png; MIT) into a 24
# box, the rounded tile with the bullet train cut out of it (even-odd)
LITELLM_ICON = "M1.65 23.85C1.35 23.75 1.05 23.56 0.75 23.26C0.13 22.63 -0 22.17 -0 20.51L0 19.22L9.7 19.22C20.09 19.22 20.75 19.19 22.13 18.74C22.87 18.5 23.19 18.34 23.65 17.98L24 17.7L24 19.76C24 22.05 23.93 22.44 23.44 23.05C23.27 23.27 22.92 23.54 22.61 23.69L22.08 23.95L12.09 23.97C3.44 23.99 2.05 23.97 1.65 23.85ZM21.47 16.04C21.47 14.44 21.44 13.88 21.35 13.81C21.16 13.66 19.34 12.88 18.23 12.47C15.08 11.3 9.76 10.01 6.09 9.51C5.39 9.42 3.94 9.34 2.46 9.31L0 9.26L0 9.03L0 8.81L1.99 8.81C5.08 8.81 7.03 9.04 10.42 9.8C16.55 11.17 21.77 13.14 23.45 14.72L24 15.24L24 16.09C24 16.89 23.99 16.95 23.74 17.17C23.6 17.3 23.34 17.5 23.16 17.6C22.84 17.79 21.76 18.19 21.57 18.19C21.5 18.19 21.47 17.45 21.47 16.04ZM0.07 17.01C0.03 16.97 -0 16.82 -0 16.67L0 16.41L2.19 16.41C3.39 16.41 5.7 16.38 7.33 16.34L10.28 16.28L10.49 16.58C10.61 16.75 10.69 16.9 10.67 16.92C10.6 16.98 0.14 17.07 0.07 17.01ZM14.27 16.29C14.21 16.23 14.16 16.09 14.16 15.98C14.16 15.58 14.26 15.56 16.85 15.56L19.32 15.56L19.42 15.79C19.49 15.95 19.49 16.06 19.41 16.21C19.31 16.4 19.26 16.41 16.84 16.41C15.05 16.41 14.35 16.38 14.27 16.29ZM0.04 15.82C0.02 15.75 0.01 14.73 0.02 13.54L0.05 11.39L3.34 11.37C6.37 11.34 6.65 11.35 6.83 11.51C6.94 11.6 7.7 12.6 8.52 13.73L10.01 15.8L7.65 15.85C3.14 15.96 0.09 15.95 0.04 15.82ZM23.48 14.15C22.82 13.47 21.11 12.2 18.66 10.57C13.28 6.99 10.34 5.67 6.23 5.01C5.11 4.82 2.06 4.77 0.72 4.9L-0.02 4.98L0.02 3.36C0.05 1.5 0.13 1.24 0.86 0.62C1.61 -0.03 1.12 -0 12.04 0C18.54 0 22.01 0.03 22.24 0.1C22.77 0.25 23.36 0.75 23.67 1.32L23.95 1.83L23.98 6.98C23.99 9.82 23.99 12.7 23.98 13.39L23.95 14.63L23.48 14.15ZM14.3 9.88C11.18 8.93 9.14 8.43 6.74 8.02C4.89 7.71 3.44 7.58 1.58 7.56L0 7.55L0 6.55C0 5.59 0.01 5.54 0.21 5.48C0.63 5.34 4.32 5.41 5.58 5.57C8.68 5.97 11.74 6.96 14.37 8.41C15.41 8.99 16.88 9.94 16.88 10.04C16.88 10.09 16.46 10.12 15.96 10.12C15.27 10.12 14.87 10.06 14.3 9.88Z"
CUSTOM = {"custom:xgboost": (XGBOOST_ICON, "nonzero"), "custom:litellm": (LITELLM_ICON, "evenodd")}
# A terminal for the agent harnesses (no brand owns the idea): a rounded frame, a chevron and a cursor, in a 24 box
AGENT_ICON = ("M5 3H19A4 4 0 0 1 23 7V17A4 4 0 0 1 19 21H5A4 4 0 0 1 1 17V7A4 4 0 0 1 5 3Z"
              "M5.5 5A2.5 2.5 0 0 0 3 7.5V16.5A2.5 2.5 0 0 0 5.5 19H18.5A2.5 2.5 0 0 0 21 16.5V7.5A2.5 2.5 0 0 0 18.5 5Z"
              "M6 8.6L7.4 7.2L12.2 12L7.4 16.8L6 15.4L9.4 12Z"
              "M12.5 14.8H18.5V16.8H12.5Z")


NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def tidy(d):
    """Path data with every number through num(). Parsed, not matched: an arc's flags may run into its next number."""
    out, i, cmd, k = [], 0, "", 0
    while i < len(d):
        c = d[i]
        if c in " ,\n\t":
            i += 1
        elif c.isalpha():
            cmd, k = c, 0
            out.append(c)
            i += 1
        else:
            if cmd.lower() == "a" and k % 7 in (3, 4):  # a flag is one digit
                tok, i = d[i], i + 1
            else:
                tok = NUMBER.match(d, i).group(0)
                i += len(tok)
                tok = re.sub(r"^(-?)0\.", r"\1.", num(float(tok)))
            prev = out[-1] if out else "a"
            if not prev.isalpha() and not tok.startswith("-") and not (tok.startswith(".") and "." in prev):
                out.append(" ")
            out.append(tok)
            k += 1
    return "".join(out)


def icon(src):
    """(path data, box size) of a brand icon."""
    if src == "custom:agent":
        return AGENT_ICON, 24.0
    if src in CUSTOM:
        return CUSTOM[src][0], 24.0
    if src.startswith("si13:"):
        svg_ = urllib.request.urlopen(SIMPLE_ICONS_13.format(src[5:])).read().decode()
        return tidy(" ".join(re.findall(r'<path[^>]*\sd="([^"]+)"', svg_))), 24.0
    url = DEVICON.format(src.split(":", 1)[1]) if src.startswith("devicon:") else SIMPLE_ICONS.format(src)
    svg_ = urllib.request.urlopen(url).read().decode()
    box = float(re.search(r'viewBox="0 0 ([0-9.]+)', svg_).group(1))
    return tidy(" ".join(re.findall(r'<path[^>]*\sd="([^"]+)"', svg_))), box


def stack(w=W):
    """Rows of brand icons and names rolling past, alternating direction: languages, then ML, LLMs and agents, then data and
    infrastructure. One mask fades all three at the edges; at rest each row starts clear of the fade."""
    doc = Doc()
    pitch, size, ic, gap = 60, 22, 28, 46
    clear = math.ceil(0.08 * w) + 3  # where a row starts at rest: just past the fade's 8%
    H = 14 + pitch * len(STACK)
    rows, css, defs = [], [], []
    seen = {}
    for r, items in enumerate(STACK):
        base = 46 + r * pitch
        x, seq = 0.0, []
        for name, src in items:
            if src not in seen:
                d, box = icon(src)
                seen[src] = (f"i{len(seen)}", box)
                rule = ' fill-rule="evenodd"' if src == "custom:agent" or CUSTOM.get(src, ("", ""))[1] == "evenodd" else ""
                defs.append(f'<path id="{seen[src][0]}" d="{d}"{rule}/>')
            iid, box = seen[src]
            seq.append(f'<use href="#{iid}" transform="translate({num(x)} {num(base - ic + 4)}) scale({num(ic / box)})"/>')
            g_, _, nw = doc.text("sg500", name, x + ic + 11, base, size)
            seq.append(g_)
            x += ic + 11 + nw + gap
        period = x
        defs.append(f'<g id="row{r}">{"".join(seq)}</g>')
        copies = math.ceil(w / period) + 1
        uses = "".join(f'<use href="#row{r}" x="{num(k * period + clear)}"/>' for k in range(-1, copies))
        dur = period / 50  # about 50 px a second (the owner, 2026-10-02: "can scroll a bit faster")
        if r % 2 == 0:
            css.append(f"@keyframes drift{r}{{to{{transform:translateX(-{num(period)}px)}}}}")
        else:
            css.append(f"@keyframes drift{r}{{from{{transform:translateX(-{num(period)}px)}}to{{transform:translateX(0)}}}}")
        rows.append(f'<g style="animation:drift{r} {num(dur)}s linear infinite">{uses}</g>')
    fade = ('<linearGradient id="fd" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset=".08" stop-color="#fff"/><stop offset=".92" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
            f'</linearGradient><mask id="fade" maskUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{H}">'
            f'<rect width="{w}" height="{H}" fill="url(#fd)"/></mask>')
    names = [n for row in STACK for n, _ in row]
    return svg(w, H, "Stack: " + ", ".join(names), "Rows of brand icons and names roll past in alternating directions.",
               doc.render(fade + "".join(defs)) + '<g class="fg" mask="url(#fade)">' + "".join(rows) + "</g>", "".join(css))


def link(label, icon=False, delay=0.0, narrow=False):
    """A pill, drawn at its own size (1:1 on the page); the narrow one keeps all three on one line in a 343 px column."""
    doc = Doc()
    size, track, pad, ar, gap, Hb = (10.5, 0.06, 10, 8, 7, 32) if narrow else (12.5, 0.12, 20, 12, 12, 44)
    w = shape("jb500", label, size, track)[1]
    ic, mark = (16, 10) if narrow else (22, 13)  # the mark's slot and size
    ic = ic if icon else 0
    Wb = pad + ic + w + gap + ar + pad
    x = pad + ic
    body = [f'<rect class="spl" x=".75" y=".75" width="{num(Wb - 1.5)}" height="{Hb - 1.5}" rx="{(Hb - 1.5) / 2}" fill="none" stroke-width="1.5"/>']
    if icon:
        body.append(hepta_at(pad + mark / 2 + 0.5, Hb / 2, mark, "bl"))
    body.append(doc.text("jb500", label, x, Hb / 2 + 0.36 * size, size, "fg", tracking=track)[0])
    ax, ay, nd = x + w + gap, Hb / 2 - ar / 2, num(ar * 7 / 12)
    css = (f"@keyframes nudge{{0%,84%{{transform:translate(0,0);opacity:1}}88%{{transform:translate({nd}px,-{nd}px);opacity:0}}"
           f"88.1%{{transform:translate(-{nd}px,{nd}px);opacity:0}}93%,100%{{transform:translate(0,0);opacity:1}}}}")
    body.append(f'<clipPath id="ac"><rect x="{num(ax - 2)}" y="{num(ay - 2)}" width="{ar + 4}" height="{ar + 4}"/></clipPath>'
                f'<g clip-path="url(#ac)"><g style="animation:nudge 6s {ENTER} {num(delay)}s 2">{arrow(ax, ay, ar, "sfg")}</g></g>')
    return svg(math.ceil(Wb), Hb, label, f"{label}, a link", doc.render() + "".join(body), css)


def footer(w=W):
    """The session ends on the left, the colophon on the right; on a phone the colophon sits under the session."""
    doc = Doc()
    H = 96 if w == W else 154
    body = [hairline(0, 1, w, 0.1, 1.0), hepta_at(9, 45, 16, "bl")]
    prompt, px0, pw = doc.text("jb400", "wentao@sf ~ $ ", 30, 50, 14, "mu")
    ex, _, t_ex = typed(doc, "jb400", "exit", px0 + pw, 50, 14, 0.9, BEAT, "fg")
    done = doc.text("jb400", "[Process completed]", 30, 74, 14, "mu", attrs=f' style="{wait(t_ex + 0.5)}"')[0]
    x, y, size, anchor = (W, 50, 11.5, "end") if w == W else (30, 108, 12.5, "start")
    right1 = doc.text("jb500", "© 2026 WENTAO HE", x, y, size, "fg", anchor=anchor, tracking=0.1)[0]
    right2 = doc.text("jb400", "SAN FRANCISCO  ·  37.77° N, 122.42° W", x, y + 24, size, "mu", anchor=anchor, tracking=0.06)[0]
    body += [prompt, ex, done, right1, right2]
    return svg(w, H, "wentao@sf ~ $ exit", "The session ends: exit types, then [Process completed]. © 2026 Wentao He, San Francisco.",
               doc.render() + "".join(body))


# ---------------------------------------------------------------------------------------------------- the banner
# (card, the terminal window in it, the text's left inset), each row as (size, baseline), the cursor's (top, height) on each
# row, the ink gradient's reach and the glow. The narrow card's window fills it, so the type is about 0.75x on a phone.
WIDE = dict(card=(1200, 320), win=(170, 44, 860, 236), inset=34, title=13, prompt=(22, 122), name=(78, 204), role=(19, 250),
            nudge=3, cur=((104, 23.3), (144, 72), (234.4, 20.1)), ink=430, glow=7)
SLIM = dict(card=(NARROW, 268), win=(14, 36, 452, 196), inset=22, title=12, prompt=(16, 104), name=(60, 170), role=(13, 206),
            nudge=2.3, cur=((90.9, 16.9), (123.8, 55.4), (195.3, 13.8)), ink=331, glow=5.4)


def banner(seed=17, lay=WIDE):
    """A terminal types whoami and the name once, then loops the role line: a role types, holds, deletes back to the // and
    the other role types. JetBrains Mono; the cursor blinks for good."""
    rnd, doc = random.Random(seed), Doc()
    adv = lambda size: 0.6 * size
    (BW, BH), (WX, WY, WW, WH) = lay["card"], lay["win"]
    LX = WX + lay["inset"]
    (ps, py), (ns, ny), (rs, ry), ts = lay["prompt"], lay["name"], lay["role"], lay["title"]

    def row(key, text, x, baseline, size, anchor="start"):  # line() as [(char, glyph, x)], for the Doc
        glyphs, w = shape(key, text, size)
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        return [(ch, g, x0 + gx) for g, gx, ch in glyphs], x0, w
    p_user, x1, w1 = row("jb400", "wentao@sf", LX, py, ps)
    p_path, x2, w2 = row("jb400", " ~ ", x1 + w1, py, ps)
    p_dollar, x3, w3 = row("jb400", "$ ", x2 + w2, py, ps)
    x_cmd = x3 + w3
    p_cmd, _, _ = row("jb400", "whoami", x_cmd, py, ps)
    p_name, _, _ = line("jb700", "Wentao He", LX - lay["nudge"], ny, ns)  # paths in place: a <use> would shift the ink gradient
    p_pre, xp0, wp = row("jb400", "// ", LX, ry, rs)
    p_a, _, _ = row("jb400", "Engineering Lead, Multimodal @ Mercor", xp0 + wp, ry, rs)
    p_b, _, _ = row("jb400", "engineer · developer · photographer · powerlifter", xp0 + wp, ry, rs)
    p_title, _, _ = row("jb400", "wentao@sf: ~ — zsh", WX + WW / 2, WY + 22, ts, anchor="middle")

    def times(glyphs, t0, lo, hi, space=None):
        out, t = [], t0
        for ch, _, _ in glyphs:
            out.append(t)
            t += space if (space and ch == " ") else rnd.uniform(lo, hi)
        return out
    t_cmd = times(p_cmd, 0.2, 0.04, 0.07)
    enter2 = t_cmd[-1] + 0.1
    t_name = times(p_name, enter2 + 0.1, 0.03, 0.05, space=0.06)  # the name lands by about 1 s
    enter3 = t_name[-1] + 0.15
    t_pre = times(p_pre, enter3 + 0.1, 0.03, 0.05)
    t0 = t_pre[-1] + 0.05  # the role loop starts; its times below run from here
    t_a = times(p_a, 0.05, 0.018, 0.032)
    t_da = [t_a[-1] + 3.0 + 0.016 * k for k in range(len(p_a))]  # deleted from the end, like a held backspace
    t_b = times(p_b, t_da[-1] + 0.3, 0.018, 0.032)
    t_db = [t_b[-1] + 3.0 + 0.016 * k for k in range(len(p_b))]
    L = t_db[-1] + 0.3
    css, n_kf = [], [0]

    def keyframes(stops, dur, prop):  # step stops [(t, value)] as a keyframe rule; the last stop at a time wins
        n_kf[0] += 1
        k = f"k{n_kf[0]}"
        seen = {}
        for t, v in sorted(stops, key=lambda s: s[0]):
            seen[num(100 * t / dur) + "%"] = v
        css.append(f"@keyframes {k}{{" + "".join(f"{p}{{{prop}:{v}}}" for p, v in seen.items()) + "}")
        return k

    def typed_once(glyphs, ts, key, size, y, cls):
        return "".join(doc.use(key, g, size, x, y, f' class="{cls}" style="{wait(t)}"') for (_, g, x), t in zip(glyphs, ts))

    def looped(glyphs, ts, td, cls, shown):
        n, out = len(glyphs), []
        for i, ((_, g, x), t) in enumerate(zip(glyphs, ts)):
            if doc.glyph("jb400", g, rs):
                k = keyframes([(0, 0), (t, 1), (td[n - 1 - i], 0)], L, "opacity")
                out.append(doc.use("jb400", g, rs, x, ry, ("" if shown else ' opacity="0"')
                                   + f' class="cm" style="animation:{k} {num(L)}s step-end {num(t0)}s infinite both"'))
        return "".join(out)
    g_cmd = typed_once(p_cmd, t_cmd, "jb400", ps, py, "tx")
    g_name = "".join(f'<path class="nm" style="{wait(t)}" d="{d}"/>' for (_, d, _), t in zip(p_name, t_name) if d)
    g_pre = typed_once(p_pre, t_pre, "jb400", rs, ry, "cm")
    g_role = looped(p_a, t_a, t_da, "cm", True) + looped(p_b, t_b, t_db, "cm", False)

    def box(row_, x):
        top, h = lay["cur"][row_ - 1]
        return x, top, adv((ps, ns, rs)[row_ - 1]), h
    tf = lambda b: f"translate({num(b[0])}px,{num(b[1])}px) scale({num(b[2])},{num(b[3])})"
    home = box(3, xp0 + wp)  # after the //, where the loop starts and ends
    bp0 = [(0.0, box(1, x_cmd))]
    bp0 += [(t, box(1, gx + adv(ps))) for (_, _, gx), t in zip(p_cmd, t_cmd)]
    bp0.append((enter2, box(2, p_name[0][2])))
    bp0 += [(t, box(2, gx + adv(ns))) for (_, _, gx), t in zip(p_name, t_name)]
    bp0.append((enter3, box(3, LX)))
    bp0 += [(t, box(3, gx + adv(rs))) for (_, _, gx), t in zip(p_pre, t_pre)]
    bp0.append((t0, home))
    n, nb = len(p_a), len(p_b)
    bp1 = [(0.0, home)]
    bp1 += [(t, box(3, gx + adv(rs))) for (_, _, gx), t in zip(p_a, t_a)]
    bp1 += [(t_da[n - 1 - i], box(3, gx)) for i, (_, _, gx) in enumerate(p_a)]
    bp1 += [(t, box(3, gx + adv(rs))) for (_, _, gx), t in zip(p_b, t_b)]
    bp1 += [(t_db[nb - 1 - i], box(3, gx)) for i, (_, _, gx) in enumerate(p_b)]
    bp1.append((L, home))
    cur0 = keyframes([(t, tf(b)) for t, b in bp0], t0, "transform")
    cur1 = keyframes([(t, tf(b)) for t, b in bp1], L, "transform")

    def blinks(busy, end):  # lit while typing, a 1 s blink between; no toggle within .25 s of typing, so no flicker
        ob, s = [], 0.0
        for a, b in busy + [(end, end)]:
            on = 1
            while s < a - 1e-9:
                ob.append((s, on))
                if a - s - 0.5 < 0.25:
                    break
                s, on = s + 0.5, 1 - on
            if a < end:
                ob.append((a, 1))
                s = b
        return ob
    curb0 = keyframes(blinks([(t_cmd[0], t_cmd[-1] + 0.12), (t_name[0], t_name[-1] + 0.12), (t_pre[0], t_pre[-1] + 0.12)], t0),
                      t0, "opacity")
    curb1 = keyframes(blinks([(t_a[0], t_a[-1] + 0.12), (t_da[0], t_da[-1] + 0.05), (t_b[0], t_b[-1] + 0.12),
                              (t_db[0], t_db[-1] + 0.05)], L), L, "opacity")
    rest = box(3, p_a[-1][2] + adv(rs))  # the final frame: the role line typed, the cursor after it
    cursor_el = (f'<g style="animation:{curb0} {num(t0)}s step-end,{curb1} {num(L)}s step-end {num(t0)}s infinite">'
                 f'<rect class="cu" width="1" height="1" transform="translate({num(rest[0])} {num(rest[1])}) '
                 f'scale({num(rest[2])} {num(rest[3])})" style="animation:{cur0} {num(t0)}s step-end,'
                 f'{cur1} {num(L)}s step-end {num(t0)}s infinite"/></g>')
    rain = []
    for x in range(22, BW, 46):
        tsp = "".join(f'<tspan x="{x}" dy="{34 if j else 0}">{escape(rnd.choice("{}[]();<>/=+*01"))}</tspan>' for j in range(9))
        dur, off, op = rnd.uniform(7, 13), rnd.uniform(0, 13), rnd.uniform(0.16, 0.34)
        rain.append(f'<text y="-20" font-size="17" fill-opacity="{num(op)}" style="animation:fall {num(dur)}s linear -{num(off)}s infinite">{tsp}</text>')
    css.append(f"@keyframes fall{{from{{transform:translateY(-{BH + 10}px)}}to{{transform:translateY({BH + 40}px)}}}}")
    style = (".tx{fill:#e8e8e2}.cm{fill:#8b8b94}.nm{fill:url(#ink)}.cu{fill:#2563eb;fill-opacity:.92}" + "".join(css))
    sp = lambda gl, key, size, y, fill: f'<g fill="{fill}">' + "".join(doc.use(key, g, size, x, y) for _, g, x in gl) + "</g>"
    static = (sp(p_title, "jb400", ts, WY + 22, "#8b8b94") + sp(p_user, "jb400", ps, py, "#60a5fa")
              + sp(p_path, "jb400", ps, py, "#8b8b94") + sp(p_dollar, "jb400", ps, py, "#e8e8e2"))
    hx, hy, hrx, hry = WX + WW / 2, WY + WH / 2 + 14, WW / 2 + 90, WH / 2 + 70  # the halo: a still light under the window
    defs = f"""
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b0d12"/><stop offset="1" stop-color="#0d1526"/></linearGradient>
<linearGradient id="ink" gradientUnits="userSpaceOnUse" x1="{LX}" y1="0" x2="{LX + lay["ink"]}" y2="0"><stop offset="0" stop-color="#e8e8e2"/><stop offset=".55" stop-color="#e8e8e2"/><stop offset="1" stop-color="#93c5fd"/></linearGradient>
<radialGradient id="vign" cx=".5" cy=".5" r=".8"><stop offset=".6" stop-color="#0b0d12" stop-opacity="0"/><stop offset="1" stop-color="#0b0d12" stop-opacity=".6"/></radialGradient>
<radialGradient id="halo"><stop offset=".6" stop-color="#2563eb" stop-opacity=".22"/><stop offset="1" stop-color="#2563eb" stop-opacity="0"/></radialGradient>
<filter id="glow" x="-10%" y="-40%" width="120%" height="180%"><feGaussianBlur in="SourceGraphic" stdDeviation="{lay["glow"]}" result="b"/><feColorMatrix in="b" type="matrix" values="0 0 0 0 .145 0 0 0 0 .388 0 0 0 0 .922 0 0 0 .7 0" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="card"><rect width="{BW}" height="{BH}" rx="18"/></clipPath>
<clipPath id="win"><rect x="{WX}" y="{WY}" width="{WW}" height="{WH}" rx="14"/></clipPath>
"""
    body = f"""{doc.render(defs)}
<g clip-path="url(#card)">
<rect width="{BW}" height="{BH}" fill="url(#bg)"/>
<g fill="#2563eb" font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-weight="600">{"".join(rain)}</g>
<rect width="{BW}" height="{BH}" fill="url(#vign)"/>
<rect x="{num(hx - hrx)}" y="{num(hy - hry)}" width="{num(2 * hrx)}" height="{num(2 * hry)}" fill="url(#halo)"/>
<rect x="{WX}" y="{WY}" width="{WW}" height="{WH}" rx="14" fill="#0d1117" fill-opacity=".96" stroke="#1f2a44" stroke-width="1.5"/>
<g clip-path="url(#win)"><rect x="{WX}" y="{WY}" width="{WW}" height="34" fill="#111827"/><line x1="{WX}" y1="{WY + 34}" x2="{WX + WW}" y2="{WY + 34}" stroke="#1f2a44"/></g>
<circle cx="{WX + 22}" cy="{WY + 17}" r="6" fill="#ff5f57"/><circle cx="{WX + 42}" cy="{WY + 17}" r="6" fill="#febc2e"/><circle cx="{WX + 62}" cy="{WY + 17}" r="6" fill="#28c840"/>
{static}
{g_cmd}<g filter="url(#glow)">{g_name}</g>{g_pre}{g_role}{cursor_el}
</g>"""
    return svg(BW, BH, "Wentao He", "A terminal types whoami, then Wentao He, then // Engineering Lead, Multimodal @ Mercor, "
               "which it deletes and retypes as // engineer · developer · photographer · powerlifter, and back; JetBrains "
               "Mono, a blinking cursor, falling code symbols behind.", body, style, dark_card=True)


# ---------------------------------------------------------------------------------------------------- the daily kit
STAT_SIZE = 54
MONO_SIZE = 13
MONO_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,.–—·/+%:"


def kit():
    """What scripts/daily.py draws the stats with: tabular Space Grotesk digits and JetBrains Mono capitals, as outlines."""
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
        (g, _, _), = shape("jb500", ch, MONO_SIZE)[0]
        kk = KIT["jb500"]
        pen = SVGPathPen(kk["gs"], ntos=num1)
        kk["gs"][g].draw(TransformPen(pen, (MONO_SIZE / kk["upm"], 0, 0, -MONO_SIZE / kk["upm"], 0, 0)))
        mono[ch] = pen.getCommands()
    return {"size": STAT_SIZE, "cell": round(cell, 2), "digits": digits,
            "mono": {"size": MONO_SIZE, "tracking": 0.1, "advance": round(0.6 * MONO_SIZE, 3), "glyphs": mono},
            "css": THEME + MOTION}


if __name__ == "__main__":
    files = {}
    for sfx, narrow in (("", False), ("-narrow", True)):  # README.md shows the -narrow ones under 600 px
        w = NARROW if narrow else W
        files.update({
            f"banner{sfx}.svg": banner(lay=SLIM if narrow else WIDE),
            f"h-about{sfx}.svg": header("01", "About", "python3 -i wentao.py", 1, w),
            f"h-stack{sfx}.svg": header("02", "Stack", "ls ~/stack", 2, w),
            f"h-activity{sfx}.svg": header("03", "Activity", "git log --since=1y", 3, w),
            f"about{sfx}.svg": about(w),
            f"stack{sfx}.svg": stack(w),
            f"link-site{sfx}.svg": link("WENTAO.GG", icon=True, delay=0.0, narrow=narrow),
            f"link-linkedin{sfx}.svg": link("LINKEDIN", delay=0.4, narrow=narrow),
            f"link-email{sfx}.svg": link("ME@WENTAO.GG", delay=0.8, narrow=narrow),
            f"footer{sfx}.svg": footer(w),
        })
    for name, content in files.items():
        (OUT / name).write_text(content)
    (OUT / "kit.json").write_text(json.dumps(kit(), separators=(",", ":")))
    for name in list(files) + ["kit.json"]:
        print(f"{name:24s} {(OUT / name).stat().st_size:>7,d} bytes")
