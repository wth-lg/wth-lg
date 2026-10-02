"""Generates assets/banner.svg, the profile README's terminal banner.

    uv run --with fonttools --with brotli python assets/banner.py > assets/banner.svg

The type is JetBrains Mono (wentao.gg's code font): regular for the terminal, bold for the name. It is
drawn as outlines because an SVG shown as an <img> cannot load web fonts. SMIL drives the typing,
because GitHub shows README images as plain images, where scripts never run. Palette: wentao.gg's
ink #0b0d12, paper #e8e8e2, blue #2563eb, muted #8b8b94. Edit the lines in build_banner() and rerun.
"""
import io
import random
import urllib.request

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

# JetBrains Mono's variable font, latin subset, as Google Fonts serves it (wght 400-800)
FONT_URL = "https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbv2o-flEEny0FZhsfKu5WU4zr3E_BX0PnT8RD8yKwBNntkaToggR7BYRbKPxDcwgknk-4.woff2"
_raw = urllib.request.urlopen(FONT_URL).read()
FONTS = {w: instancer.instantiateVariableFont(TTFont(io.BytesIO(_raw)), {"wght": w}) for w in (400, 700)}

W, H = 1200, 320
WX, WY, WW, WH = 170, 44, 860, 236  # the terminal window
LX = WX + 34                         # the text's left edge

def glyph_paths(text, x, baseline, size, weight=400):
    f = FONTS[weight]; gs = f.getGlyphSet(); cmap = f.getBestCmap(); upm = f['head'].unitsPerEm
    sc = size / upm; out = []; cx = x
    for ch in text:
        g = cmap.get(ord(ch))
        adv = f['hmtx'][g][0] * sc if g else 0.6 * size
        d = ''
        if g and ch != ' ':
            pen = SVGPathPen(gs, ntos=lambda v: ('%.1f' % v).rstrip('0').rstrip('.'))
            gs[g].draw(TransformPen(pen, (sc, 0, 0, -sc, cx, baseline)))
            d = pen.getCommands()
        out.append((ch, d, cx, adv)); cx += adv
    return out, cx


def build_banner(seed=17):
    rnd = random.Random(seed)
    T = 12.0; OFF = 11.4
    kt = lambda t: '%.4f' % (t / T)
    def glyph_anim(d, on, off):
        return (f'<path d="{d}" opacity="0"><animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
                f'calcMode="discrete" values="0;1;0" keyTimes="0;{kt(on)};{kt(off)}"/></path>')
    # ---- glyphs
    p_user, x1 = glyph_paths('wentao@sf', LX, 122, 22)
    p_path, x2 = glyph_paths(' ~ ', x1, 122, 22)
    p_dollar, x3 = glyph_paths('$ ', x2, 122, 22)
    p_cmd, _ = glyph_paths('whoami', x3, 122, 22)
    p_name, _ = glyph_paths('Wentao He', LX - 3, 204, 78, 700)
    p_pre, xp = glyph_paths('// ', LX, 250, 19)
    p_a, _ = glyph_paths('Engineering Lead @ Mercor · San Francisco', xp, 250, 19)
    p_b, _ = glyph_paths('engineer · developer · photographer · powerlifter', xp, 250, 19)
    title_w = 0.6 * 13 * len('wentao@sf: ~ — zsh')
    p_title, _ = glyph_paths('wentao@sf: ~ — zsh', WX + WW / 2 - title_w / 2, WY + 22, 13)
    # ---- the timeline
    def typed(glyphs, t0, lo, hi, space=None):
        ts, t = [], t0
        for ch, *_ in glyphs:
            ts.append(t); t += (space if (space and ch == ' ') else rnd.uniform(lo, hi))
        return ts
    t_cmd = typed(p_cmd, 0.75, 0.08, 0.16)
    enter2 = t_cmd[-1] + 0.45
    t_name = typed(p_name, enter2 + 0.2, 0.08, 0.14, space=0.17)
    enter3 = t_name[-1] + 0.3
    t_pre = typed(p_pre, enter3 + 0.2, 0.03, 0.05)
    t_a = typed(p_a, t_pre[-1] + 0.05, 0.018, 0.032)
    del0 = t_a[-1] + 2.2
    t_del = [del0 + 0.016 * k for k in range(len(p_a))]          # backspace held: right to left
    t_b = typed(p_b, t_del[-1] + 0.3, 0.018, 0.032)
    assert t_b[-1] < OFF - 1.5, t_b[-1]
    # ---- typed groups
    def grp(fill, items, extra=''):
        return f'<g fill="{fill}"{extra}>' + ''.join(items) + '</g>'
    g_cmd = grp('#e8e8e2', [glyph_anim(d, t, OFF) for (ch, d, *_), t in zip(p_cmd, t_cmd) if d])
    g_name = grp('url(#nameInk)', [glyph_anim(d, t, OFF) for (ch, d, *_), t in zip(p_name, t_name) if d], ' filter="url(#glow)"')
    n = len(p_a)
    a_items = [glyph_anim(d, t_a[i], t_del[n - 1 - i]) for i, (ch, d, *_) in enumerate(p_a) if d]
    g_cmt = grp('#8b8b94', [glyph_anim(d, t, OFF) for (ch, d, *_), t in zip(p_pre, t_pre) if d] + a_items
                + [glyph_anim(d, t, OFF) for (ch, d, *_), t in zip(p_b, t_b) if d])
    # ---- the cursor
    def box(line, x):
        if line == 1: return (x, 122 - 18, 13.2, 23.3)
        if line == 2: return (x, 204 - 60, 46.8, 72)
        return (x, 250 - 15.6, 11.4, 20.1)
    bp = [(0.0,) + box(1, x3)]
    bp += [(t,) + box(1, cx + adv) for (ch, d, cx, adv), t in zip(p_cmd, t_cmd)]
    bp.append((enter2,) + box(2, p_name[0][2]))
    bp += [(t,) + box(2, cx + adv) for (ch, d, cx, adv), t in zip(p_name, t_name)]
    bp.append((enter3,) + box(3, LX))
    bp += [(t,) + box(3, cx + adv) for (ch, d, cx, adv), t in zip(p_pre, t_pre)]
    bp += [(t,) + box(3, cx + adv) for (ch, d, cx, adv), t in zip(p_a, t_a)]
    bp += [(t_del[n - 1 - i],) + box(3, cx) for i, (ch, d, cx, adv) in enumerate(p_a)]
    bp += [(t,) + box(3, cx + adv) for (ch, d, cx, adv), t in zip(p_b, t_b)]
    bp.append((OFF,) + box(1, x3))
    ded = {}
    for b in sorted(bp, key=lambda b: b[0]): ded[kt(b[0])] = b
    bp = [ded[k] for k in sorted(ded, key=float)]
    def anim(attr, idx):
        return (f'<animate attributeName="{attr}" dur="{T}s" repeatCount="indefinite" calcMode="discrete" '
                f'values="{";".join("%.1f" % b[idx] for b in bp)}" keyTimes="{";".join(kt(b[0]) for b in bp)}"/>')
    busy = [(t_cmd[0], t_cmd[-1] + 0.12), (t_name[0], t_name[-1] + 0.12), (t_pre[0], t_a[-1] + 0.12),
            (t_del[0], t_del[-1] + 0.05), (t_b[0], t_b[-1] + 0.12)]
    ob, s = [], 0.0
    for a, b in busy + [(T, T)]:
        on = 1
        while s < a - 1e-9:
            ob.append((s, on)); s = min(s + 0.5, a); on = 1 - on
        if a < T: ob.append((a, 1)); s = b
    obd = {}
    for t, v in ob: obd[kt(t)] = v
    obk = sorted(obd, key=float)
    cursor = (f'<rect x="{bp[0][1]:.1f}" y="{bp[0][2]:.1f}" width="{bp[0][3]:.1f}" height="{bp[0][4]:.1f}" rx="2" fill="#2563eb" fill-opacity="0.92">'
              + anim('x', 1) + anim('y', 2) + anim('width', 3) + anim('height', 4)
              + f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" calcMode="discrete" values="{";".join(str(obd[k]) for k in obk)}" keyTimes="{";".join(obk)}"/></rect>')
    # ---- the rain: falling code symbols
    CH = '{}[]();<>/=+*01'
    rain = []
    for x in range(22, W, 46):
        tsp = ''.join(f'<tspan x="{x}" dy="{34 if j else 0}">{rnd.choice(CH).replace("<", "&lt;").replace(">", "&gt;")}</tspan>' for j in range(9))
        dur = rnd.uniform(7, 13); off = rnd.uniform(0, dur); op = rnd.uniform(0.16, 0.34)
        rain.append(f'<g opacity="{op:.2f}"><text y="-20" font-size="17">{tsp}</text><animateTransform attributeName="transform" type="translate" from="0 -330" to="0 360" dur="{dur:.1f}s" begin="-{off:.1f}s" repeatCount="indefinite"/></g>')
    static = lambda gl, fill: f'<g fill="{fill}">' + ''.join(f'<path d="{d}"/>' for ch, d, *_ in gl if d) + '</g>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">Wentao He</title>
<desc id="d">A terminal types whoami, then Wentao He, then // Engineering Lead @ Mercor · San Francisco, which it deletes and retypes as // engineer · developer · photographer · powerlifter. JetBrains Mono, a blinking cursor, falling code symbols behind.</desc>
<!-- Generated: the type is JetBrains Mono (400; the name at 700) drawn as outlines, because an SVG shown as an image cannot load web fonts. SMIL animates it, because GitHub shows README images as plain images. -->
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b0d12"/><stop offset="1" stop-color="#0d1526"/></linearGradient>
  <linearGradient id="nameInk" gradientUnits="userSpaceOnUse" x1="{LX}" y1="0" x2="{LX + 430}" y2="0"><stop offset="0" stop-color="#e8e8e2"/><stop offset="0.55" stop-color="#e8e8e2"/><stop offset="1" stop-color="#93c5fd"/></linearGradient>
  <radialGradient id="vign" cx="0.5" cy="0.5" r="0.8"><stop offset="0.6" stop-color="#0b0d12" stop-opacity="0"/><stop offset="1" stop-color="#0b0d12" stop-opacity="0.6"/></radialGradient>
  <filter id="glow" x="-10%" y="-40%" width="120%" height="180%"><feGaussianBlur in="SourceGraphic" stdDeviation="7" result="b"/><feColorMatrix in="b" type="matrix" values="0 0 0 0 0.145  0 0 0 0 0.388  0 0 0 0 0.922  0 0 0 0.7 0" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="shadow" x="-10%" y="-20%" width="120%" height="150%"><feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#2563eb" flood-opacity="0.22"/></filter>
  <clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>
  <clipPath id="win"><rect x="{WX}" y="{WY}" width="{WW}" height="{WH}" rx="14"/></clipPath>
</defs>
<g clip-path="url(#card)">
  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <g fill="#2563eb" font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-weight="600">{''.join(rain)}</g>
  <rect width="{W}" height="{H}" fill="url(#vign)"/>
  <g filter="url(#shadow)"><rect x="{WX}" y="{WY}" width="{WW}" height="{WH}" rx="14" fill="#0d1117" fill-opacity="0.96" stroke="#1f2a44" stroke-width="1.5"/></g>
  <g clip-path="url(#win)"><rect x="{WX}" y="{WY}" width="{WW}" height="34" fill="#111827"/><line x1="{WX}" y1="{WY + 34}" x2="{WX + WW}" y2="{WY + 34}" stroke="#1f2a44"/></g>
  <circle cx="{WX + 22}" cy="{WY + 17}" r="6" fill="#ff5f57"/><circle cx="{WX + 42}" cy="{WY + 17}" r="6" fill="#febc2e"/><circle cx="{WX + 62}" cy="{WY + 17}" r="6" fill="#28c840"/>
  {static(p_title, '#8b8b94')}
  {static(p_user, '#60a5fa')}{static(p_path, '#8b8b94')}{static(p_dollar, '#e8e8e2')}
  {g_cmd}
  {g_name}
  {g_cmt}
  {cursor}
</g>
</svg>
''', dict(T=T, OFF=OFF, cmd=(t_cmd[0], t_cmd[-1]), name=(t_name[0], t_name[-1]), a=(t_pre[0], t_a[-1]), dele=(t_del[0], t_del[-1]), b=(t_b[0], t_b[-1]))


if __name__ == "__main__":
    print(build_banner()[0], end="")
