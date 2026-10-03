#!/usr/bin/env python3
"""motion-video の背景（SVG）のプリセットを作る。bg/<名前>.svg と、一覧 bg/index.json を書く。

  python3 bg_make.py            # 全部を作り直す（同じ入力からは同じファイルになる）

2 種類ある:
  - 配色に合わせる背景（themed）: 色を :root の変数（--bg0・--a1 など）で書く。動画にするとき、engine.js がいまの配色の色に置き換える。
    ファイルを直に開くと、既定の配色（紺と真鍮）の色で見える。
  - 景色・場所の背景（scenery）: 色は決まっている。tone（dark / light）が配色の明るさと合わないと、字が読みにくくなる。

足すときは、@themed か @scenery を付けた関数を 1 つ書き、このスクリプトを回す。
"""
import json
import math
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "bg")
W, H = 1920, 1080
KEYS = ("bg0", "bg1", "ink", "muted", "faint", "panel", "panel2", "edge", "a1", "a2", "a3", "a4")
ROOT = (":root{--bg0:#07131a;--bg1:#0d202b;--ink:#e4eff1;--muted:#8ea9b2;--faint:#56707b;--panel:#0f222d;--panel2:#1d5d6e;--edge:#1f3b48;"
        "--a1:#c8923a;--a2:#2bd1b8;--a3:#8fb8ff;--a4:#e07a9b}")
ACC = ("a2", "a1", "a3", "a4")
PRESETS = []   # (名前, 種類, 見出し, 説明, tone, 関数)


def themed(name, label, desc):
    return lambda fn: PRESETS.append((name, "themed", label, desc, None, fn)) or fn


def scenery(name, label, desc, tone):
    return lambda fn: PRESETS.append((name, "scenery", label, desc, tone, fn)) or fn


# ---------- SVG の部品 ----------


def n(x):
    s = ("%.1f" % x).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def f(x):
    """透明度（小数 3 桁まで）。"""
    return ("%.3f" % x).rstrip("0").rstrip(".") or "0"


def paint(prop, c, o=None):
    """色の指定。配色の名前（a1 など）は変数で、ほかはそのまま書く。"""
    if c in KEYS:
        return ' style="%s:var(--%s)%s"' % (prop, c, "" if o is None else ";%s-opacity:%s" % (prop, f(o)))
    return ' %s="%s"%s' % (prop, c, "" if o is None else ' %s-opacity="%s"' % (prop, f(o)))


def rect(x, y, w, h, c, o=None, rx=0, extra=""):
    return '<rect x="%s" y="%s" width="%s" height="%s"%s%s%s/>' % (n(x), n(y), n(w), n(h), ' rx="%s"' % n(rx) if rx else "", paint("fill", c, o), extra)


def circ(cx, cy, r, c, o=None, extra=""):
    return '<circle cx="%s" cy="%s" r="%s"%s%s/>' % (n(cx), n(cy), n(r), paint("fill", c, o), extra)


def ring(cx, cy, r, c, w=2, o=None, extra=""):
    return '<circle cx="%s" cy="%s" r="%s" fill="none" stroke-width="%s"%s%s/>' % (n(cx), n(cy), n(r), n(w), paint("stroke", c, o), extra)


def ell(cx, cy, rx, ry, c, o=None, extra=""):
    return '<ellipse cx="%s" cy="%s" rx="%s" ry="%s"%s%s/>' % (n(cx), n(cy), n(rx), n(ry), paint("fill", c, o), extra)


def path(d, fill=None, stroke=None, w=2, o=None, extra=""):
    a = paint("fill", fill, o) if fill else ' fill="none"'
    b = (paint("stroke", stroke, o if not fill else None) + ' stroke-width="%s"' % n(w)) if stroke else ""
    return '<path d="%s"%s%s%s/>' % (d, a, b, extra)


def line(x0, y0, x1, y1, c, w=2, o=None, extra=""):
    return '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke-width="%s"%s%s/>' % (n(x0), n(y0), n(x1), n(y1), n(w), paint("stroke", c, o), extra)


def poly(pts, c, o=None, extra=""):
    return '<polygon points="%s"%s%s/>' % (" ".join("%s,%s" % (n(x), n(y)) for x, y in pts), paint("fill", c, o), extra)


def stop(off, c, o=1):
    if c in KEYS:
        return '<stop offset="%s" style="stop-color:var(--%s);stop-opacity:%s"/>' % (n(off), c, f(o))
    return '<stop offset="%s" stop-color="%s"%s/>' % (n(off), c, "" if o == 1 else ' stop-opacity="%s"' % f(o))


def lgrad(i, stops, x1=0, y1=0, x2=0, y2=1, user=False):
    return '<linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s"%s>%s</linearGradient>' % (
        i, n(x1), n(y1), n(x2), n(y2), ' gradientUnits="userSpaceOnUse"' if user else "", "".join(stop(*s) for s in stops))


def rgrad(i, stops, cx, cy, r):
    return '<radialGradient id="%s" cx="%s" cy="%s" r="%s" gradientUnits="userSpaceOnUse">%s</radialGradient>' % (i, n(cx), n(cy), n(r), "".join(stop(*s) for s in stops))


class Doc:
    """1 枚の SVG。defs と本体を足していく。"""
    def __init__(self, base=None):
        self.defs, self.body, self.k = [], [], 0
        if base is None:   # 配色の地（上が bg1、下が bg0）
            self.defs.append(lgrad("bg", [(0, "bg1"), (1, "bg0")]))
            self.body.append('<rect width="%d" height="%d" fill="url(#bg)"/>' % (W, H))
        elif isinstance(base, (list, tuple)):   # 景色の地（上から下への色の列）
            self.defs.append(lgrad("bg", [(i / (len(base) - 1), c) for i, c in enumerate(base)]))
            self.body.append('<rect width="%d" height="%d" fill="url(#bg)"/>' % (W, H))
        else:
            self.body.append('<rect width="%d" height="%d" fill="%s"/>' % (W, H, base))
    def id(self):
        self.k += 1
        return "g%d" % self.k
    def add(self, *xs):
        self.body.extend(xs)
        return self
    def glow(self, cx, cy, r, c, o):
        i = self.id()
        self.defs.append(rgrad(i, [(0, c, o), (1, c, 0)], cx, cy, r))
        self.body.append('<rect x="%s" y="%s" width="%s" height="%s" fill="url(#%s)"/>' % (n(max(0, cx - r)), n(max(0, cy - r)), n(min(W, cx + r) - max(0, cx - r)), n(min(H, cy + r) - max(0, cy - r)), i))
        return self
    def grad(self, stops, x1=0, y1=0, x2=0, y2=1, user=False):
        i = self.id()
        self.defs.append(lgrad(i, stops, x1, y1, x2, y2, user))
        return "url(#%s)" % i
    def pattern(self, w, h, content, transform=""):
        i = self.id()
        self.defs.append('<pattern id="%s" width="%s" height="%s" patternUnits="userSpaceOnUse"%s>%s</pattern>' % (i, n(w), n(h), ' patternTransform="%s"' % transform if transform else "", content))
        return "url(#%s)" % i
    def mask(self, kind):
        """模様を薄くする所を決める。center: 中央だけ見せる / edges: 周りだけ見せる / corners: 右上と左下 / bottom: 下ほど濃く / top: 上ほど濃く"""
        i, m = self.id(), self.id()
        if kind == "center":
            self.defs.append(rgrad(i, [(0, "#fff"), (.55, "#fff", .5), (1, "#fff", 0)], 960, 540, 1050))
        elif kind == "edges":
            self.defs.append(rgrad(i, [(0, "#fff", 0), (.4, "#fff", .08), (1, "#fff")], 960, 540, 1100))
        elif kind == "corners":
            self.defs.append(lgrad(i, [(0, "#fff"), (.38, "#fff", 0), (.62, "#fff", 0), (1, "#fff")], 0, 1, 1, 0))
        elif kind == "bottom":
            self.defs.append(lgrad(i, [(0, "#fff", 0), (.35, "#fff", .1), (1, "#fff")]))
        else:
            self.defs.append(lgrad(i, [(0, "#fff"), (.65, "#fff", .1), (1, "#fff", 0)]))
        self.defs.append('<mask id="%s" maskUnits="userSpaceOnUse" x="0" y="0" width="%d" height="%d"><rect width="%d" height="%d" fill="url(#%s)"/></mask>' % (m, W, H, W, H, i))
        return ' mask="url(#%s)"' % m
    def fill(self, paint_url, o=None, mask=""):
        self.body.append('<rect width="%d" height="%d" fill="%s"%s%s/>' % (W, H, paint_url, "" if o is None else ' opacity="%s"' % f(o), mask))
        return self
    def svg(self, is_themed):
        return re.sub(r"<[^<>]+>", _one_style, self._svg(is_themed))
    def _svg(self, is_themed):
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">%s<defs>%s</defs>%s</svg>\n'
                % (W, H, W, H, "<style>%s</style>" % ROOT if is_themed else "", "".join(self.defs), "".join(self.body)))


def _one_style(m):
    """1 つの要素に style が 2 つ付いたら（塗りと線の両方が配色の色）、1 つにまとめる。"""
    tag = m.group(0)
    st = re.findall(r' style="([^"]*)"', tag)
    if len(st) < 2:
        return tag
    tag = re.sub(r' style="[^"]*"', "", tag)
    end = "/>" if tag.endswith("/>") else ">"
    return tag[:-len(end)] + ' style="%s"' % ";".join(st) + end


def smooth(pts, closed=False):
    """点の列を、なめらかな線にする（中点をつなぐ 2 次の曲線）。"""
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if closed:
        m = mid(pts[-1], pts[0])
        d = "M%s %s" % (n(m[0]), n(m[1]))
        for i, p in enumerate(pts):
            q = mid(p, pts[(i + 1) % len(pts)])
            d += "Q%s %s %s %s" % (n(p[0]), n(p[1]), n(q[0]), n(q[1]))
        return d + "Z"
    d = "M%s %s" % (n(pts[0][0]), n(pts[0][1]))
    for i in range(1, len(pts) - 1):
        q = mid(pts[i], pts[i + 1])
        d += "Q%s %s %s %s" % (n(pts[i][0]), n(pts[i][1]), n(q[0]), n(q[1]))
    return d + "L%s %s" % (n(pts[-1][0]), n(pts[-1][1]))


def wave(y0, amp, wl, ph=0, step=80, amp2=0, wl2=97):
    return [(x, y0 + amp * math.sin(x / wl + ph) + amp2 * math.sin(x / wl2 + ph * 2)) for x in range(-step, W + step * 2, step)]


def under(pts, bottom=H):
    """線の下を塗る形。"""
    return smooth(pts) + "L%s %s L%s %s Z" % (n(pts[-1][0]), n(bottom), n(pts[0][0]), n(bottom))


def blob(cx, cy, r, rnd, k=10, rough=.22):
    return smooth([(cx + math.cos(i / k * math.tau) * r * (1 + (rnd.random() - .5) * 2 * rough), cy + math.sin(i / k * math.tau) * r * (1 + (rnd.random() - .5) * 2 * rough)) for i in range(k)], True)


def hills(rnd, base, amp, step=120, rough=1.0):
    """丘の稜線（なめらか）。"""
    ph = [rnd.random() * math.tau for _ in range(3)]
    return [(x, base - amp * (.5 + .5 * math.sin(x / 330 * rough + ph[0])) - amp * .35 * math.sin(x / 140 * rough + ph[1]) - amp * .15 * math.sin(x / 61 + ph[2])) for x in range(-step, W + step * 2, step)]


def peaks(rnd, base, amp, step=110):
    """山の稜線（とがった）。"""
    return [(x + rnd.uniform(-30, 30), base - amp * rnd.uniform(.15, 1) * (1 if i % 2 else .45)) for i, x in enumerate(range(-step, W + step * 2, step))]


def jag(pts, bottom=H):
    return "M" + "L".join("%s %s" % (n(x), n(y)) for x, y in pts) + "L%s %s L%s %s Z" % (n(pts[-1][0]), n(bottom), n(pts[0][0]), n(bottom))


def stars(rnd, cnt, c="#ffffff", ymax=H, big=2.2):
    return "".join(circ(rnd.uniform(0, W), rnd.uniform(0, ymax), rnd.uniform(.7, big), c, round(rnd.uniform(.25, .95), 2)) for _ in range(cnt))


def cloud(cx, cy, s, c="#ffffff", o=.9):
    parts = [(-150, 10, 60), (-80, -30, 80), (10, -50, 95), (100, -20, 75), (165, 14, 55)]
    return '<g%s>%s%s</g>' % ("" if o == 1 else ' opacity="%s"' % f(o), "".join(circ(cx + x * s, cy + y * s, r * s, c) for x, y, r in parts),
                              rect(cx - 200 * s, cy + 6 * s, 410 * s, 62 * s, c, rx=31 * s))


def pine(x, y, h, c):
    w = h * .42
    return poly([(x, y - h), (x + w * .5, y - h * .55), (x + w * .28, y - h * .55), (x + w * .75, y - h * .2), (x + w * .12, y - h * .2), (x + w * .12, y),
                 (x - w * .12, y), (x - w * .12, y - h * .2), (x - w * .75, y - h * .2), (x - w * .28, y - h * .55), (x - w * .5, y - h * .55)], c)


def skyline(rnd, base, hmin, hmax, wmin=60, wmax=150):
    """建物の列。[(x, y, w, h), …]"""
    x, out = -20, []
    while x < W + 20:
        w, h = rnd.randint(wmin, wmax), rnd.randint(hmin, hmax)
        out.append((x, base - h, w, h))
        x += w + rnd.choice((0, 0, 6, 14))
    return out


# ================= 配色に合わせる背景 =================


@themed("soft", "やわらかな光", "右上と左下に、淡い光がにじむ。どの内容にも合う無難な地")
def _(d, r):
    d.glow(1500, 150, 950, "a2", .24).glow(300, 1000, 850, "a1", .17)


@themed("mesh", "色のにじみ", "4 色の光が四隅から混ざり合う。明るく今っぽい紹介に")
def _(d, r):
    for x, y, rad, c, o in ((300, 200, 720, "a2", .26), (1650, 250, 680, "a3", .24), (1420, 960, 760, "a1", .2), (350, 960, 620, "a4", .2), (960, 540, 520, "a2", .07)):
        d.glow(x, y, rad, c, o)


@themed("vignette", "周りを暗く", "中央がほのかに明るく、周りが暗い。言葉を真ん中に置く場面に")
def _(d, r):
    d.glow(960, 500, 900, "a2", .12)
    i = d.id()
    d.defs.append(rgrad(i, [(0, "#000", 0), (.55, "#000", 0), (1, "#000", .24)], 960, 540, 1150))
    d.fill("url(#%s)" % i)


@themed("horizon", "床と壁", "奥に地平の光があり、手前に床が広がる。スタジオのような落ち着いた地")
def _(d, r):
    d.add('<rect y="760" width="%d" height="320" fill="%s"/>' % (W, d.grad([(0, "panel2", .34), (1, "panel2", 0)])))
    i = d.id()
    d.defs.append('<radialGradient id="%s" cx=".5" cy=".5" r=".5">%s</radialGradient>' % (i, stop(0, "a2", .34) + stop(1, "a2", 0)))
    d.add('<ellipse cx="960" cy="760" rx="1150" ry="90" fill="url(#%s)"/>' % i, line(0, 760, W, 760, "a2", 2, .3))


@themed("wave-bottom", "下の波", "下に、重なる波。上が広く空くので、見出しや箇条書きを置きやすい")
def _(d, r):
    for i in range(4):
        d.add(path(under(wave(700 + i * 90, 42 - i * 5, 300 + i * 70, i * 1.9, amp2=12)), ACC[i % 2], o=.08 + i * .04))


@themed("wave-top", "上下の波", "上と下に、波の帯。中央の横長の所に内容を置く")
def _(d, r):
    g = "".join(path(under(wave(840 + i * 80, 34, 280 + i * 60, i * 2.3 + 1, amp2=10)), ACC[(i + 1) % 2], o=.09 + i * .04) for i in range(3))
    d.add(g, '<g transform="rotate(180 960 540)">%s</g>' % g)


@themed("curves", "流れる線", "何本もの細い線が、束になってゆるく流れる。上品・技術のどちらにも")
def _(d, r):
    for i in range(15):
        pts = [(x, 580 + (i - 7) * 20 * (1 + .6 * math.sin(x / 420)) + 150 * math.sin(x / 520 + i * .09) + 60 * math.sin(x / 230 + i * .05)) for x in range(-80, W + 161, 80)]
        d.add(path(smooth(pts), stroke=ACC[i % 2], w=2, o=.1 + .2 * i / 15))


@themed("topo", "等高線", "地図の等高線のような輪が広がる。調査・計画・探索の話に")
def _(d, r):
    for cx, cy, c in ((420, 280, 2.1), (1480, 780, .4), (1720, 130, 4.0)):
        for k in range(1, 10):
            R = k * 68
            pts = [(cx + math.cos(t) * R * (1 + .18 * math.sin(2 * t + c) + .1 * math.sin(3 * t + 2 * c) + .05 * math.sin(5 * t + k * .3)),
                    cy + math.sin(t) * R * (1 + .18 * math.sin(2 * t + c) + .1 * math.sin(3 * t + 2 * c) + .05 * math.sin(5 * t + k * .3))) for t in (j / 30 * math.tau for j in range(30))]
            d.add(path(smooth(pts, True), stroke="a2", w=2.5 if k % 3 == 0 else 1.5, o=.26 if k % 3 == 0 else .15))


@themed("grid-fade", "消えていく格子", "中央に格子があり、周りへ消えていく。設計・仕組みの説明に")
def _(d, r):
    p = d.pattern(80, 80, path("M80 0H0V80", stroke="a2", w=1.5))
    d.fill(p, .5, d.mask("center"))


@themed("dots-fade", "隅の点", "右上と左下に、点の並びが浮かぶ。中央は空く")
def _(d, r):
    p = d.pattern(40, 40, circ(20, 20, 3.2, "a2"))
    d.fill(p, .7, d.mask("corners"))


@themed("iso", "斜めの格子", "三角の格子（立体図の方眼）。構造・建築・立体の話に")
def _(d, r):
    h = 80 * math.sqrt(3)
    p = d.pattern(80, h, path("M0 0L80 %s M80 0L0 %s M0 %s H80 M0 0H80" % (n(h), n(h), n(h / 2)), stroke="a2", w=1.2))
    d.fill(p, .45, d.mask("edges"))


@themed("hex", "蜂の巣", "六角形の並びが、右上と左下に浮かぶ。技術・化学・つながりの話に")
def _(d, r):
    p = d.pattern(120, 69.28, path("M0 34.64L20 0H60L80 34.64L60 69.28H20Z M80 34.64H120", stroke="a2", w=2))
    d.fill(p, .5, d.mask("corners"))


@themed("lowpoly", "三角の面", "三角の面を敷きつめた地。色の濃さが面ごとに少しずつ違う")
def _(d, r):
    cols, rows = 12, 7
    g = [[(x * W / cols + (r.uniform(-50, 50) if 0 < x < cols else 0), y * H / rows + (r.uniform(-45, 45) if 0 < y < rows else 0)) for x in range(cols + 1)] for y in range(rows + 1)]
    for y in range(rows):
        for x in range(cols):
            a, b, c, e = g[y][x], g[y][x + 1], g[y + 1][x + 1], g[y + 1][x]
            for tri in ((a, b, c), (a, c, e)) if (x + y) % 2 else ((a, b, e), (b, c, e)):
                d.add(poly(tri, r.choice(("a2", "a2", "a1", "panel2")), round(r.uniform(.02, .13), 3)))


@themed("pcb", "基板", "基板の配線と端子。ハードウェア・IT・仕組みの話に")
def _(d, r):
    for _i in range(34):
        x, y, hz = r.randint(1, 46) * 40, r.randint(1, 25) * 40, r.random() < .5
        pts = [(x, y)]
        for _k in range(r.randint(2, 4)):
            step = r.randint(2, 8) * 40 * r.choice((-1, 1))
            x, y = (max(40, min(W - 40, x + step)), y) if hz else (x, max(40, min(H - 40, y + step)))
            hz = not hz
            pts.append((x, y))
        d.add(path("M" + "L".join("%d %d" % p for p in pts), stroke="a2", w=2.5, o=.2), ring(pts[0][0], pts[0][1], 7, "a2", 2.5, .34), circ(pts[-1][0], pts[-1][1], 6, "a1", .4))
    for x, y in ((360, 240), (1440, 760), (1560, 200)):
        d.add(rect(x, y, 120, 120, "panel", .8, 10, paint("stroke", "a2", .4) + ' stroke-width="2.5"'), rect(x + 30, y + 30, 60, 60, "a2", .14, 6))


@themed("blueprint", "設計図", "方眼と、寸法線・円・十字の印。設計・計画・製図の話に")
def _(d, r):
    d.fill(d.pattern(40, 40, path("M40 0H0V40", stroke="ink", w=1)), .09)
    d.fill(d.pattern(200, 200, path("M200 0H0V200", stroke="ink", w=1.6)), .16)
    d.add(ring(1500, 320, 170, "a2", 2, .35), ring(1500, 320, 240, "a2", 1.5, .2, ' stroke-dasharray="10 10"'), line(1230, 320, 1770, 320, "a2", 1.5, .3), line(1500, 50, 1500, 590, "a2", 1.5, .3))
    d.add(line(160, 960, 900, 960, "a1", 2, .5), "".join(line(160 + i * 74, 948, 160 + i * 74, 972, "a1", 2, .5) for i in range(11)))
    for x, y, sx, sy in ((60, 60, 1, 1), (W - 60, 60, -1, 1), (60, H - 60, 1, -1), (W - 60, H - 60, -1, -1)):
        d.add(path("M%d %dV%dH%d" % (x, y + 70 * sy, y, x + 70 * sx), stroke="ink", w=3, o=.4))


@themed("rings", "同心円", "右下と左上の隅から、輪が広がる。広がり・波及・中心の話に")
def _(d, r):
    for i in range(11):
        d.add(ring(1760, 960, 90 + i * 80, "a2", 2, .26 - i * .02))
    for i in range(5):
        d.add(ring(140, 110, 60 + i * 60, "a1", 2, .24 - i * .04))


@themed("arcs", "隅の弧", "左上と右下の隅に、太い弧が重なる。親しみやすい紹介・イベントに")
def _(d, r):
    for i, c in enumerate(("a1", "a2", "a3")):
        d.add(ring(0, 0, 190 + i * 110, c, 46, .2 - i * .04), ring(W, H, 230 + i * 120, ACC[(i + 2) % 4], 52, .2 - i * .04))


@themed("diagonal", "斜めの縞", "細い斜めの縞が全面に入る。控えめで、どの部品とも合う")
def _(d, r):
    d.fill(d.pattern(64, 64, rect(0, 0, 30, 64, "a2"), "rotate(45)"), .06)
    d.glow(1600, 200, 800, "a2", .12)


@themed("burst", "放射の光", "下の中央から、光の筋が放射に広がる。発表・お祝い・強調に")
def _(d, r):
    cx, cy, k = 960, 1180, 30
    for i in range(0, k, 2):
        a0, a1 = math.pi + i * math.pi / k, math.pi + (i + 1) * math.pi / k
        d.add(poly([(cx, cy), (cx + math.cos(a0) * 1900, cy + math.sin(a0) * 1900), (cx + math.cos(a1) * 1900, cy + math.sin(a1) * 1900)], "a1", .08))
    d.glow(cx, 1080, 700, "a1", .26)


@themed("dots-corner", "網点", "右下と左上の隅へ、点が大きくなっていく。漫画・ポップな紹介に")
def _(d, r):
    for gx in range(22, W, 44):
        for gy in range(22, H, 44):
            k = (gx / W + gy / H) - 1.12
            if k > .04:
                d.add(circ(gx, gy, min(19, k * 30), "a2", .3))
            k2 = .62 - (gx / W + gy / H)
            if k2 > .04:
                d.add(circ(gx, gy, min(14, k2 * 26), "a1", .26))


@themed("soft-shapes", "まるい形", "四隅に、ゆるい丸みの形。やさしい・親しみやすい内容に")
def _(d, r):
    for (x, y, rad), c in zip(((180, 140, 330), (1760, 200, 280), (1680, 980, 360), (200, 1000, 300)), ACC):
        d.add(path(blob(x, y, rad, r), c, o=.16))
    d.add(path(blob(1500, 380, 70, r), "a1", o=.2), path(blob(420, 760, 50, r), "a2", o=.2))


@themed("memphis", "散らした図形", "丸・三角・十字・波線を周りに散らす。楽しい・にぎやかな紹介に")
def _(d, r):
    k = 0
    while k < 46:
        x, y = r.uniform(40, W - 40), r.uniform(40, H - 40)
        if 330 < x < 1590 and 230 < y < 850:
            continue
        c, s, rot, kind = ACC[k % 4], r.uniform(16, 34), r.randint(0, 359), k % 6
        if kind == 0:
            e = ring(0, 0, s, c, 5)
        elif kind == 1:
            e = poly([(0, -s), (s * .9, s * .7), (-s * .9, s * .7)], c)
        elif kind == 2:
            e = path("M%s 0H%s M0 %sV%s" % (n(-s), n(s), n(-s), n(s)), stroke=c, w=6)
        elif kind == 3:
            e = path("M%s 0l%s %sl%s %sl%s %sl%s %s" % (n(-s * 1.6), n(s * .8), n(-s * .6), n(s * .8), n(s * .6), n(s * .8), n(-s * .6), n(s * .8), n(s * .6)), stroke=c, w=5, extra=' stroke-linejoin="round"')
        elif kind == 4:
            e = circ(0, 0, s * .5, c)
        else:
            e = rect(-s * .7, -s * .7, s * 1.4, s * 1.4, c, rx=4)
        d.add('<g transform="translate(%s %s) rotate(%d)" opacity=".5">%s</g>' % (n(x), n(y), rot, e))
        k += 1


@themed("plus", "十字の並び", "小さな十字が周りに並ぶ。医療・計算・足し算の話や、控えめな地に")
def _(d, r):
    d.fill(d.pattern(72, 72, path("M36 26V46M26 36H46", stroke="a2", w=3, extra=' stroke-linecap="round"')), .55, d.mask("edges"))


@themed("lights", "光の玉", "大小の淡い光の玉が浮かぶ。祝い・夜・やわらかい雰囲気に")
def _(d, r):
    for i in range(26):
        x, y, rad, c = r.uniform(0, W), r.uniform(0, H), r.uniform(40, 170), ACC[i % 4]
        d.add(circ(x, y, rad, c, round(r.uniform(.04, .13), 3)))
        if i % 3 == 0:
            d.add(ring(x, y, rad, c, 2, .18))


@themed("spotlight", "照明", "上から 2 本の光が差し、床に光の輪ができる。発表・表彰・主役の紹介に")
def _(d, r):
    for ox in (420, 1500):
        g = d.grad([(0, "a2", .3), (1, "a2", 0)], ox, -60, 960, 980, True)
        d.add('<polygon points="%d,-60 %d,1000 %d,1000" fill="%s"/>' % (ox, 560, 1360, g))
    i = d.id()
    d.defs.append('<radialGradient id="%s" cx=".5" cy=".5" r=".5">%s</radialGradient>' % (i, stop(0, "ink", .22) + stop(1, "ink", 0)))
    d.add('<ellipse cx="960" cy="985" rx="620" ry="90" fill="url(#%s)"/>' % i)


@themed("frame", "飾り枠", "二重の枠と、四隅の飾り。式典・招待・表彰・古風な内容に")
def _(d, r):
    d.add(rect(44, 44, W - 88, H - 88, "none", extra=paint("stroke", "a1", .7) + ' stroke-width="3"'), rect(62, 62, W - 124, H - 124, "none", extra=paint("stroke", "a1", .35) + ' stroke-width="1.5"'))
    for x, y, sx, sy in ((44, 44, 1, 1), (W - 44, 44, -1, 1), (44, H - 44, 1, -1), (W - 44, H - 44, -1, -1)):
        d.add('<g transform="translate(%d %d) scale(%d %d)">%s%s%s</g>' % (
            x, y, sx, sy, path("M0 120A120 120 0 0 0 120 0", stroke="a1", w=3, o=.7), path("M0 80A80 80 0 0 0 80 0", stroke="a1", w=1.5, o=.5),
            poly([(34, 20), (48, 34), (34, 48), (20, 34)], "a1", .8)))
    d.glow(960, 540, 900, "a1", .07)


@themed("bands", "斜めの帯", "右上と左下の隅を、色の帯が斜めに横切る。勢いのある告知・発表に")
def _(d, r):
    g = ""
    for i, (c, o) in enumerate((("a2", .16), ("a1", .14), ("a3", .1))):
        a, w = 1240 + i * 150, 110
        g += poly([(a, 0), (a + w, 0), (W, W - a - w), (W, W - a)], c, o)
    d.add(g, '<g transform="rotate(180 960 540)">%s</g>' % g)


@themed("bars", "棒の列", "下に、高さの違う棒が並ぶ。数字・音・成長の話に")
def _(d, r):
    g = d.grad([(0, "a1", .32), (1, "a2", .08)])
    for i in range(48):
        h = 40 + 300 * (.35 + .65 * math.sin(math.pi * (i + .5) / 48)) * r.uniform(.35, 1)
        d.add('<rect x="%d" y="%s" width="24" height="%s" rx="4" fill="%s"/>' % (10 + i * 40, n(H - h), n(h), g))


@themed("network", "つながり", "点と線の網が広がる。ネットワーク・関係・連携の話に")
def _(d, r):
    pts = [(r.uniform(40, W - 40), r.uniform(40, H - 40)) for _ in range(46)]
    for i, p in enumerate(pts):
        for q in sorted(pts, key=lambda q: math.hypot(q[0] - p[0], q[1] - p[1]))[1:3]:
            d.add(line(p[0], p[1], q[0], q[1], "a2", 1.5, .22))
    for i, p in enumerate(pts):
        d.add(circ(p[0], p[1], 7 if i % 5 == 0 else 4, "a1" if i % 5 == 0 else "a2", .6))


@themed("split", "斜めの 2 色", "画面を斜めに 2 色に分ける。比べる・表と裏・切り替わりの場面に")
def _(d, r):
    d.add(poly([(1180, 0), (W, 0), (W, H), (820, H)], "panel2", .32), line(1180, 0, 820, H, "a1", 5, .7))
    d.glow(1650, 250, 700, "a2", .12)


@themed("chevrons", "山形の並び", "山形の線が並ぶ。進む・流れ・上向きの話に")
def _(d, r):
    d.fill(d.pattern(96, 48, path("M0 36L48 12L96 36", stroke="a2", w=3)), .36, d.mask("bottom"))


@themed("speckle", "ざらつき", "細かい粒のざらつきと、周りの暗がり。フィルム・紙のような手ざわりに")
def _(d, r):
    d.add("".join(circ(r.uniform(0, W), r.uniform(0, H), r.uniform(.8, 2.6), "ink", round(r.uniform(.1, .4), 2)) for _ in range(380)))
    i = d.id()
    d.defs.append(rgrad(i, [(0, "#000", 0), (.6, "#000", 0), (1, "#000", .2)], 960, 540, 1150))
    d.fill("url(#%s)" % i)


@themed("orbit", "軌道", "右上の光のまわりを、楕円の軌道と星が回る。宇宙・循環・製品の周辺の話に")
def _(d, r):
    d.glow(1480, 300, 420, "a1", .3)
    for i in range(5):
        rx = 200 + i * 190
        d.add('<ellipse cx="1480" cy="300" rx="%d" ry="%d" fill="none" stroke-width="2" transform="rotate(-18 1480 300)"%s/>' % (rx, rx * .36, paint("stroke", "a2", .26 - i * .03)))
        a = r.uniform(0, math.tau)
        x, y = math.cos(a) * rx, math.sin(a) * rx * .36
        c, s = math.cos(math.radians(-18)), math.sin(math.radians(-18))
        d.add(circ(1480 + x * c - y * s, 300 + x * s + y * c, 7 + i % 3 * 4, ACC[i % 4], .8))
    d.add("".join(circ(r.uniform(0, W), r.uniform(0, H), r.uniform(.8, 2), "ink", round(r.uniform(.15, .5), 2)) for _ in range(90)))


@themed("ridge", "山並み", "下に、重なる山の影。道のり・目標・挑戦の話に")
def _(d, r):
    d.glow(1400, 420, 520, "a1", .16)
    for i in range(4):
        d.add(path(jag(peaks(r, 760 + i * 90, 300 - i * 50)), "a2", o=.07 + i * .045))


@themed("city", "街の影", "下に、建物の影が並ぶ。社会・都市・ビジネスの話に")
def _(d, r):
    d.glow(960, 900, 900, "a2", .14)
    for x, y, w, h in skyline(r, H, 160, 420):
        d.add(rect(x, y, w, h, "panel2", .24))
    for x, y, w, h in skyline(r, H, 80, 260):
        d.add(rect(x, y, w, h, "edge", .95))
        for _k in range(r.randint(0, 4)):
            d.add(rect(x + r.randint(8, max(9, w - 22)), y + r.randint(12, max(13, h - 30)), 12, 16, "a1", .5))


@themed("checker", "市松", "淡い市松の模様。和風・ゲーム・遊びの話に")
def _(d, r):
    d.fill(d.pattern(160, 160, rect(0, 0, 80, 80, "ink") + rect(80, 80, 80, 80, "ink")), .04)
    d.glow(960, 540, 900, "a2", .08)


@themed("seigaiha", "青海波", "波を重ねた和の模様。和風・伝統・めでたい話に")
def _(d, r):
    c = ""
    for k in range(-2, 5):
        for cx in ((0, 120) if k % 2 == 0 else (-60, 60, 180)):
            c += circ(cx, k * 30, 60, "bg0", extra=paint("stroke", "a2") + ' stroke-width="3"') + ring(cx, k * 30, 42, "a2", 3) + ring(cx, k * 30, 24, "a2", 3)
    d.fill(d.pattern(120, 60, c), .45, d.mask("bottom"))


@themed("asanoha", "麻の葉", "麻の葉の和の模様。和風・伝統・成長の話に")
def _(d, r):
    s, h = 96, 96 * math.sqrt(3)
    segs = ["M0 0H%s M0 %sH%s M0 %sH%s" % (n(s), n(h / 2), n(s), n(h), n(s)), "M0 0L%s %s M%s 0L0 %s" % (n(s), n(h), n(s), n(h))]
    for ty in (0, h / 2, h):   # 三角の重心と頂点を結ぶ
        ox = s / 2 if ty == h / 2 else 0
        for tx in (-s, 0, s):
            a = (tx + ox, ty)
            for up in (1, -1):
                b, c = (a[0] + s, a[1]), (a[0] + s / 2, a[1] + up * h / 2)
                g = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3)
                segs.append("".join("M%s %sL%s %s" % (n(g[0]), n(g[1]), n(p[0]), n(p[1])) for p in (a, b, c)))
    d.fill(d.pattern(s, h, path(" ".join(segs), stroke="a1", w=1.6)), .5, d.mask("corners"))


@themed("shippo", "七宝", "輪をつないだ和の模様。和風・縁・つながりの話に")
def _(d, r):
    s, rad = 96, 96 / math.sqrt(2)
    c = "".join(ring(x, y, rad, "a1", 2) for x, y in ((0, 0), (s, 0), (0, s), (s, s), (s / 2, s / 2)))
    d.fill(d.pattern(s, s, c), .45, d.mask("edges"))


@themed("uroko", "鱗", "三角を並べた和の模様。和風・厄除け・きりっとした内容に")
def _(d, r):
    c = poly([(0, 70), (40, 0), (80, 70)], "ink") + poly([(-40, 140), (0, 70), (40, 140)], "ink") + poly([(40, 140), (80, 70), (120, 140)], "ink")
    d.fill(d.pattern(80, 140, c), .07, d.mask("bottom"))


@themed("papercut", "切り紙の重なり", "左下と右上から、紙を重ねたような形がせり出す。物語・絵本・やさしい説明に")
def _(d, r):
    for i, (c, o) in enumerate((("panel2", .3), ("a2", .14), ("panel2", .5), ("a1", .16))):
        y = 620 + i * 110
        pts = [(x, y + 260 * max(0, x / W) ** 1.5 + 40 * math.sin(x / 210 + i * 2)) for x in range(-80, W + 161, 80)]
        d.add(path(under([(x, yy + 10) for x, yy in pts]), "#000000", o=.16), path(under(pts), c, o=o))
    for i, (c, o) in enumerate((("panel2", .3), ("a2", .12))):
        pts = [(x, 200 - i * 90 - 220 * max(0, 1 - x / W) ** 1.5 + 30 * math.sin(x / 190 + i)) for x in range(-80, W + 161, 80)]
        d.add(path(smooth(pts) + "L%d -10L-80 -10Z" % (W + 80), c, o=o))


@themed("stairs", "段々", "右下に、階段のように積み上がる段。成長・段階・積み上げの話に")
def _(d, r):
    for i in range(8):
        h = 80 + i * 86
        d.add(rect(960 + i * 120, H - h, 120, h, "a2", .06 + i * .022), rect(960 + i * 120, H - h, 120, 6, "a1", .5))


@themed("window", "窓の光", "窓から差す光が、壁に斜めに落ちる。朝・静けさ・暮らしの話に")
def _(d, r):
    panes = "".join(rect(x * 250, y * 250, 230, 230, "ink", .07) for x in range(3) for y in range(3))
    d.add('<g transform="translate(980 60) skewX(-22) skewY(8)">%s</g>' % panes)
    d.glow(1500, 300, 900, "a1", .1)


# ================= 景色・場所の背景（色は決まっている） =================


@scenery("sky-day", "青空", "青い空に、白い雲。明るい紹介・あいさつ・外の話に", "light")
def _(d, r):
    d.__init__(("#3f9be6", "#8cc9f5", "#d6eefc"))
    for x, y, s, o in ((300, 250, 1.2, .95), (1250, 170, .9, .9), (1650, 420, 1.3, .92), (800, 520, .7, .8), (150, 760, 1.0, .85), (1100, 860, 1.5, .95), (1800, 900, .9, .9)):
        d.add(cloud(x, y, s, "#ffffff", o))


@scenery("sky-sunset", "夕焼け", "紫から橙へ移る夕焼けの空と、沈む日。締め・ふり返り・物語に", "dark")
def _(d, r):
    d.__init__(("#241d4a", "#6b3466", "#c84f62", "#f39a4d", "#fbd27a"))
    d.glow(960, 980, 520, "#fff3c4", .9)
    d.add(circ(960, 980, 120, "#fff1b8"))
    for y, w, o in ((300, 900, .35), (420, 1300, .3), (560, 1000, .3), (700, 1500, .25), (820, 800, .3)):
        x = r.uniform(-200, W - w + 200)
        d.add(ell(x + w / 2, y, w / 2, 16 + r.uniform(0, 12), "#3a2456", o))


@scenery("sky-night", "夜空", "星と三日月の夜空。夜・静けさ・夢・宇宙の入口に", "dark")
def _(d, r):
    d.__init__(("#040818", "#0c1a3c", "#1b2f5e"))
    d.glow(500, 600, 900, "#3a5db0", .22)
    d.add(stars(r, 230))
    d.glow(1500, 250, 260, "#fff6d0", .3)
    d.add('<path d="M1540 160a100 100 0 1 0 60 170a82 82 0 1 1 -60 -170z" fill="#fff3c2"/>')


@scenery("sky-dawn", "朝焼け", "桃色と淡い黄の朝の空。はじまり・希望・新しい話に", "light")
def _(d, r):
    d.__init__(("#b9d9f2", "#f6dfd3", "#fbd3b4", "#fdeccb"))
    d.glow(960, 1100, 800, "#fff7d6", .9)
    for x, y, s, c in ((350, 300, 1.2, "#fff4ee"), (1400, 220, 1.0, "#ffe9e4"), (1700, 560, 1.2, "#fff4ee"), (700, 700, .8, "#ffe9e4"), (200, 880, 1.3, "#ffffff")):
        d.add(cloud(x, y, s, c, .85))


@scenery("mountains", "山なみ", "澄んだ空の下、遠くまで重なる青い山。旅・目標・自然の話に", "light")
def _(d, r):
    d.__init__(("#bfe1f6", "#e6f3fb", "#fbf3e2"))
    d.glow(1450, 300, 420, "#fff6cf", .95)
    d.add(circ(1450, 300, 70, "#fffbe6"))
    for i, c in enumerate(("#b9cfe6", "#93b3d6", "#6c93c0", "#4a72a3", "#2f5182")):
        d.add(path(jag(peaks(r, 620 + i * 100, 330 - i * 40)), c))
    d.add(cloud(400, 240, 1.0, "#ffffff", .9), cloud(1050, 380, .7, "#ffffff", .8))


@scenery("mountains-night", "夜の山", "星空の下の、暗い山の影と月。夜・静けさ・挑戦の前に", "dark")
def _(d, r):
    d.__init__(("#050a1c", "#12224a", "#2c4478"))
    d.add(stars(r, 170, ymax=760))
    d.glow(420, 260, 300, "#f8f1d0", .35)
    d.add(circ(420, 260, 64, "#f6efcf"))
    for i, c in enumerate(("#22386a", "#182b55", "#0f1e40", "#08122b")):
        d.add(path(jag(peaks(r, 680 + i * 100, 320 - i * 40)), c))


@scenery("sea", "海", "青い空と水平線、きらめく海。夏・旅・ひらけた話に", "light")
def _(d, r):
    d.__init__(("#58b4ee", "#bfe6fb", "#eaf7fd"))
    d.glow(1380, 250, 380, "#ffffff", .9)
    d.add(circ(1380, 250, 62, "#ffffff"), cloud(380, 300, 1.1, "#ffffff", .95), cloud(1000, 190, .7, "#ffffff", .85))
    d.add('<rect y="600" width="%d" height="480" fill="%s"/>' % (W, d.grad([(0, "#2f8fd6"), (1, "#0e4f96")])))
    for i in range(26):
        z = (i + 1) / 26
        y, w = 600 + 480 * z ** 1.7, 60 + 380 * z
        for _k in range(5):
            x = r.uniform(0, W)
            d.add(line(x, y, x + w * r.uniform(.4, 1), y, "#ffffff", 2 + 3 * z, round(.15 + .3 * r.random(), 2), ' stroke-linecap="round"'))


@scenery("sea-sunset", "夕暮れの海", "夕日が沈む海と、水面の光の道。締め・余韻・思い出に", "dark")
def _(d, r):
    d.__init__(("#2a1f4d", "#a5466b", "#f08a4b", "#fbc56b"))
    d.glow(960, 640, 520, "#fff2c0", .85)
    d.add(circ(960, 640, 110, "#fff0b0"))
    d.add('<rect y="640" width="%d" height="440" fill="%s"/>' % (W, d.grad([(0, "#7a3562"), (1, "#1c1438")])))
    for i in range(24):
        z = (i + .5) / 24
        y, w = 640 + 440 * z ** 1.6, (90 + 420 * z) * r.uniform(.5, 1)
        d.add(rect(960 - w / 2 + r.uniform(-30, 30), y, w, 4 + 6 * z, "#ffd98a", round(.75 - z * .4, 2), 3))


@scenery("city-night", "夜の街", "明かりのともる夜のビル街。都会・仕事・ニュースの話に", "dark")
def _(d, r):
    d.__init__(("#070b1f", "#16214a", "#3a2f63"))
    d.add(stars(r, 90, ymax=520))
    d.glow(960, 1000, 1000, "#ff9d5c", .22)
    for x, y, w, h in skyline(r, H, 300, 620, 70, 150):
        d.add(rect(x, y, w, h, "#1a2550"))
    win = d.pattern(26, 34, rect(6, 8, 12, 16, "#ffd879", .85))
    win2 = d.pattern(52, 68, rect(6, 8, 12, 16, "#ffe9a8", .9) + rect(32, 42, 12, 16, "#8fd0ff", .7))
    for i, (x, y, w, h) in enumerate(skyline(r, H, 160, 460, 80, 170)):
        d.add(rect(x, y, w, h, "#0b1230"), '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (n(x + 8), n(y + 10), n(w - 16), n(h - 10), win if i % 3 else win2))


@scenery("city-day", "昼の街", "青空の下のビル街。会社・社会・暮らしの話に", "light")
def _(d, r):
    d.__init__(("#6db8f0", "#c9e8fb", "#eef8fe"))
    d.add(cloud(350, 220, 1.1), cloud(1350, 160, .8, "#ffffff", .85), cloud(1700, 360, .6, "#ffffff", .8))
    for x, y, w, h in skyline(r, H, 300, 600, 70, 150):
        d.add(rect(x, y, w, h, "#a9c6e0"))
    win = d.pattern(28, 36, rect(6, 8, 14, 18, "#dff1ff", .9))
    for i, (x, y, w, h) in enumerate(skyline(r, H, 160, 460, 80, 170)):
        d.add(rect(x, y, w, h, ("#5f86ad", "#6f97bd", "#547aa2")[i % 3]), '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (n(x + 8), n(y + 10), n(w - 16), n(h - 10), win))


@scenery("space", "宇宙", "星雲と星、輪のある惑星。宇宙・未来・大きな構想の話に", "dark")
def _(d, r):
    d.__init__("#060918")
    for x, y, rad, c, o in ((400, 300, 700, "#5b3fd1", .4), (1500, 760, 800, "#1f6fd6", .35), (1100, 200, 500, "#d04a9c", .25), (300, 950, 500, "#18a3a8", .2)):
        d.glow(x, y, rad, c, o)
    d.add(stars(r, 260, big=2.6))
    d.add('<ellipse cx="1500" cy="800" rx="330" ry="70" fill="none" stroke="#e9c79a" stroke-width="16" stroke-opacity=".7" transform="rotate(-16 1500 800)"/>')
    d.add('<circle cx="1500" cy="800" r="170" fill="%s"/>' % d.grad([(0, "#f2b46b"), (1, "#8a3f2e")], 0, 0, 1, 1))
    d.add('<path d="M1183 891A330 70 -16 0 0 1817 709" fill="none" stroke="#f4d9b3" stroke-width="16" stroke-opacity=".9"/>', circ(520, 240, 44, "#b9c4e8"), circ(506, 228, 9, "#98a5d0"), circ(536, 252, 6, "#98a5d0"))


@scenery("forest", "森", "霧のかかった、深い緑の針葉樹の森。自然・静けさ・探検の話に", "dark")
def _(d, r):
    d.__init__(("#1d3b3a", "#2f5d52", "#7fa58d"))
    d.glow(1300, 250, 700, "#e9f5c8", .4)
    for i, c in enumerate(("#5c8a78", "#3f6f5f", "#285345", "#163a30", "#0b241e")):
        base, hh = 640 + i * 110, 200 + i * 60
        x = r.uniform(-60, 0)
        while x < W + 60:
            d.add(pine(x, base + r.uniform(-20, 20), hh * r.uniform(.7, 1.15), c))
            x += hh * r.uniform(.28, .5)
        d.add(rect(0, base - 10, W, H - base + 10, c))
        if i < 4:
            d.add('<rect y="%d" width="%d" height="160" fill="%s"/>' % (base - 150, W, d.grad([(0, "#dfeee0", 0), (1, "#dfeee0", .2)])))


@scenery("desert", "砂漠", "大きな日と、なだらかな砂丘。旅・乾いた地・遠い道のりの話に", "light")
def _(d, r):
    d.__init__(("#f6c97c", "#fbe0a6", "#fdf0cf"))
    d.glow(1350, 330, 460, "#fff8dc", .95)
    d.add(circ(1350, 330, 96, "#fffbe8"))
    for i, c in enumerate(("#eeb974", "#e4a45c", "#d68f48", "#c27a38")):
        d.add(path(under(hills(r, 700 + i * 105, 150 - i * 15, 120, .7)), c))
    for x, y, s in ((300, 900, 1), (1600, 980, 1.3)):
        d.add('<g transform="translate(%d %d) scale(%s)" fill="#3f7a4a">%s%s%s</g>' % (x, y, n(s), rect(-12, -120, 24, 120, "#3f7a4a", rx=12), path("M-12 -60h-26a10 10 0 0 1 -10 -10v-26", stroke="#3f7a4a", w=18, extra=' stroke-linecap="round"'),
                                                                                    path("M12 -40h24a10 10 0 0 0 10 -10v-34", stroke="#3f7a4a", w=18, extra=' stroke-linecap="round"')))


@scenery("snowfield", "雪原", "雪の丘と針葉樹、舞う雪。冬・静けさ・年末年始の話に", "light")
def _(d, r):
    d.__init__(("#b9d3ea", "#dfebf6", "#f6fafd"))
    for i, c in enumerate(("#e3edf6", "#eef4fa", "#ffffff")):
        base = 680 + i * 120
        d.add(path(under(hills(r, base, 110 - i * 20, 120, .8)), c))
        for _k in range(6 - i):
            d.add(pine(r.uniform(40, W - 40), base + 30 + r.uniform(0, 40), 120 + i * 70 + r.uniform(0, 40), ("#7fa0b5", "#4f7890", "#2f566e")[i]))
    d.add("".join(circ(r.uniform(0, W), r.uniform(0, H), r.uniform(2, 6), "#ffffff", round(r.uniform(.6, 1), 2)) for _ in range(120)))


@scenery("field", "草原", "青空と、なだらかな緑の丘。のびのびした話・子ども向け・春夏に", "light")
def _(d, r):
    d.__init__(("#56b0ee", "#bfe6fb", "#f2fbff"))
    d.glow(300, 240, 380, "#fffbe0", .9)
    d.add(circ(300, 240, 70, "#fff7c9"), cloud(1000, 230, 1.1), cloud(1600, 380, .8, "#ffffff", .9))
    for i, c in enumerate(("#a5d87f", "#7cc463", "#55ae4c", "#3a943f")):
        d.add(path(under(hills(r, 700 + i * 100, 130 - i * 15, 120, .8)), c))
    d.add("".join(circ(r.uniform(0, W), r.uniform(960, H - 10), r.uniform(4, 7), r.choice(("#ffffff", "#ffe36b", "#ff9fc0"))) for _ in range(60)))


@scenery("sakura", "桜", "淡い桃色の空に、桜の枝と花びら。春・入学・門出・和の話に", "light")
def _(d, r):
    d.__init__(("#fbd9e6", "#fdeaf1", "#fff8fb"))
    d.glow(1500, 300, 800, "#ffffff", .7)
    d.add(path("M-20 120C300 140 520 60 760 190M360 118C440 220 520 250 640 330M560 108C640 40 760 30 860 10", stroke="#6b4636", w=16, extra=' stroke-linecap="round"'))
    flower = lambda x, y, s: '<g transform="translate(%s %s) rotate(%d)">%s%s</g>' % (n(x), n(y), r.randint(0, 71), "".join(
        '<ellipse cx="0" cy="%s" rx="%s" ry="%s" fill="#f9a8c4" transform="rotate(%d)"/>' % (n(-s * .62), n(s * .42), n(s * .62), k * 72) for k in range(5)), circ(0, 0, s * .22, "#e8648f"))
    for x, y in ((120, 130), (260, 100), (400, 150), (520, 90), (640, 170), (760, 190), (430, 240), (560, 290), (640, 330), (660, 60), (800, 30), (300, 180), (720, 110)):
        d.add(flower(x + r.uniform(-14, 14), y + r.uniform(-14, 14), r.uniform(26, 40)))
    for _k in range(46):
        x, y = r.uniform(0, W), r.uniform(200, H)
        d.add('<ellipse cx="%s" cy="%s" rx="13" ry="7" fill="#f7a3c1" fill-opacity="%s" transform="rotate(%d %s %s)"/>' % (n(x), n(y), f(r.uniform(.45, .9)), r.randint(0, 179), n(x), n(y)))


@scenery("autumn", "紅葉", "あたたかい色の空に、舞う落ち葉。秋・実り・ふり返りの話に", "light")
def _(d, r):
    d.__init__(("#fbe6c2", "#fbd3a0", "#f6b57a"))
    d.glow(400, 250, 700, "#fff6dc", .8)
    leaf = "M0 -22C14 -14 16 6 0 24C-16 6 -14 -14 0 -22ZM0 -22V30"
    for _k in range(70):
        x, y, s, c = r.uniform(0, W), r.uniform(0, H), r.uniform(.8, 2), r.choice(("#d9452b", "#e9782a", "#f0a92d", "#b7342a", "#c98a2b"))
        d.add('<path d="%s" fill="%s" stroke="#7a3b1e" stroke-width="1.5" fill-opacity="%s" transform="translate(%s %s) rotate(%d) scale(%s)"/>' % (leaf, c, f(r.uniform(.6, .95)), n(x), n(y), r.randint(0, 359), n(s)))
    d.add(path(under(hills(r, 1040, 50, 120, 1.4)), "#c8642e"))


@scenery("underwater", "海の中", "上から光が差す青い海の中と、泡。海・深さ・もぐる話に", "dark")
def _(d, r):
    d.__init__(("#3fb3d9", "#1773ae", "#0a3f7a", "#06224d"))
    for i in range(7):
        x = 150 + i * 270 + r.uniform(-60, 60)
        d.add('<polygon points="%s,-20 %s,-20 %s,1080 %s,1080" fill="%s"/>' % (n(x), n(x + 90), n(x - 160), n(x - 420), d.grad([(0, "#ffffff", .2), (1, "#ffffff", 0)])))
    for _k in range(46):
        x, y, s = r.uniform(0, W), r.uniform(100, H), r.uniform(5, 22)
        d.add(ring(x, y, s, "#ffffff", 2, .5), circ(x - s * .3, y - s * .3, s * .2, "#ffffff", .6))
    d.add(path(under(hills(r, 980, 90, 120, .9)), "#0a2a4e"), path(under(hills(r, 1040, 60, 120, 1.2)), "#061a36"))
    for x in (200, 330, 1500, 1640, 1760):
        d.add(path("M%d 1080C%d 980 %d 940 %d 860C%d 800 %d 780 %d 720" % (x, x - 40, x + 40, x, x - 30, x + 20, x - 6), stroke="#1f8f6e", w=14, extra=' stroke-linecap="round"'))


@scenery("fireworks", "花火", "夜空に上がる花火と、街の影。祭り・お祝い・夏の夜に", "dark")
def _(d, r):
    d.__init__(("#050818", "#101a40", "#2a2452"))
    d.add(stars(r, 80, ymax=600))
    for cx, cy, rad, c in ((420, 320, 230, "#ff6b8b"), (1050, 240, 280, "#ffd35c"), (1560, 400, 220, "#6be0ff"), (760, 560, 150, "#b98cff"), (1320, 660, 130, "#7dff9a")):
        d.glow(cx, cy, rad * 1.3, c, .22)
        for k in range(28):
            a, r0, r1 = k / 28 * math.tau, rad * .22, rad * (1 if k % 2 else .78)
            d.add(line(cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * r1, cy + math.sin(a) * r1 + r1 * .06, c, 3, .85, ' stroke-linecap="round"'), circ(cx + math.cos(a) * r1, cy + math.sin(a) * r1 + r1 * .06, 5, "#ffffff", .9))
    for x, y, w, h in skyline(r, H, 60, 200, 60, 140):
        d.add(rect(x, y, w, h, "#04060f"))


@scenery("rainbow", "虹", "やわらかな色の虹と雲。子ども向け・多様さ・楽しい話に", "light")
def _(d, r):
    d.__init__(("#dff1fb", "#f6fbff", "#fffaf0"))
    for i, c in enumerate(("#ff9aa2", "#ffbe8a", "#ffe58a", "#b5e6a2", "#9ad4f5", "#c3b1f0")):
        d.add(ring(960, 1250, 1000 - i * 60, c, 60, .75))
    d.add(cloud(330, 900, 1.6), cloud(1600, 920, 1.7), cloud(960, 1040, 1.4, "#ffffff", .95), cloud(260, 210, .8, "#ffffff", .9), cloud(1650, 180, .7, "#ffffff", .9))


@scenery("blackboard", "黒板", "木の枠の、深緑の黒板。授業・解説・勉強の話に", "dark")
def _(d, r):
    d.__init__("#8a5a33")
    d.add('<rect x="40" y="40" width="1840" height="950" rx="6" fill="%s"/>' % d.grad([(0, "#2f5a45"), (1, "#234636")]), rect(40, 40, 1840, 950, "none", rx=6, extra=' stroke="#5e3a1e" stroke-width="10"'))
    for _k in range(26):
        d.add('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#ffffff" fill-opacity="%s" transform="rotate(%d %d %d)"/>' % (n(r.uniform(150, 1770)), n(r.uniform(120, 900)), n(r.uniform(120, 380)), n(r.uniform(14, 44)), f(r.uniform(.015, .04)), r.randint(-12, 12), 960, 540))
    d.add(rect(0, 990, W, 90, "#74481f"), rect(0, 990, W, 14, "#a06b3c"), rect(520, 1004, 80, 16, "#ffffff", rx=6), rect(620, 1006, 64, 14, "#ffd6de", rx=6), rect(700, 1005, 70, 15, "#fff2a8", rx=6),
          rect(1240, 996, 170, 40, "#3c4a6b", rx=6), rect(1240, 1026, 170, 14, "#d9d2c0", rx=4))


@scenery("whiteboard", "ホワイトボード", "銀の枠の白い板と、ペン。会議・打ち合わせ・仕事の説明に", "light")
def _(d, r):
    d.__init__("#d9dee5")
    d.add(rect(50, 46, 1820, 930, "#fbfcfd", rx=10, extra=' stroke="#aab2bd" stroke-width="12"'), '<rect x="70" y="66" width="1780" height="300" fill="%s"/>' % d.grad([(0, "#ffffff", .9), (1, "#ffffff", 0)]))
    d.add(rect(360, 986, 1200, 34, "#b9c0ca", rx=8), rect(360, 986, 1200, 8, "#d6dbe2", rx=4))
    for i, c in enumerate(("#222a35", "#d0342c", "#1f6fd6", "#1e9e57")):
        d.add(rect(480 + i * 190, 962, 130, 24, c, rx=10), rect(596 + i * 190, 966, 26, 16, "#3c4350", rx=4))
    d.add(rect(1300, 950, 150, 36, "#5b6675", rx=6))


@scenery("notebook", "ノート", "罫線と赤い縦線の入ったノートの紙。勉強・メモ・手順の話に", "light")
def _(d, r):
    d.__init__("#fdfbf3")
    d.fill(d.pattern(W, 54, line(0, 53, W, 53, "#a8c8ea", 2)))
    d.add(line(230, 0, 230, H, "#ee8a8a", 3), "".join(circ(110, y, 24, "#d9d6cc") + circ(110, y + 3, 21, "#eeece4") for y in (180, 540, 900)))


@scenery("graph-paper", "方眼紙", "水色の方眼紙。図・計算・設計・理科の話に", "light")
def _(d, r):
    d.__init__("#fbfdfe")
    d.fill(d.pattern(24, 24, path("M24 0H0V24", stroke="#bfe0f1", w=1)))
    d.fill(d.pattern(120, 120, path("M120 0H0V120", stroke="#7fbfe0", w=2)))


@scenery("kraft", "クラフト紙", "茶色いクラフト紙の手ざわり。手づくり・素朴・あたたかい話に", "light")
def _(d, r):
    d.__init__(("#d3b384", "#c8a674"))
    for _k in range(360):
        x, y, a, ln = r.uniform(0, W), r.uniform(0, H), r.uniform(0, math.tau), r.uniform(6, 26)
        d.add(line(x, y, x + math.cos(a) * ln, y + math.sin(a) * ln, r.choice(("#a98654", "#e6cfa6", "#b89562")), 1.4, round(r.uniform(.25, .6), 2)))
    i = d.id()
    d.defs.append(rgrad(i, [(0, "#5a3d18", 0), (.6, "#5a3d18", 0), (1, "#5a3d18", .28)], 960, 540, 1150))
    d.fill("url(#%s)" % i)


@scenery("cork", "コルクボード", "木の枠のコルクの板。お知らせ・写真や付箋を並べる話に", "dark")
def _(d, r):
    d.__init__("#b98b57")
    d.add("".join(circ(r.uniform(0, W), r.uniform(0, H), r.uniform(2, 7), r.choice(("#9a6f3f", "#d2a873", "#8a6034", "#c79a63")), round(r.uniform(.4, .9), 2)) for _ in range(430)))
    d.add(rect(18, 18, W - 36, H - 36, "none", extra=' stroke="#6b4423" stroke-width="36"'), rect(38, 38, W - 76, H - 76, "none", extra=' stroke="#4f3118" stroke-width="5"'))


@scenery("washi", "和紙", "繊維と金の粒の入った生成りの和紙。和風・手紙・しきたりの話に", "light")
def _(d, r):
    d.__init__(("#f6f1e4", "#efe7d4"))
    for _k in range(190):
        x, y, a, ln = r.uniform(0, W), r.uniform(0, H), r.uniform(0, math.tau), r.uniform(20, 70)
        d.add(path("M%s %sq%s %s %s %s" % (n(x), n(y), n(math.cos(a) * ln / 2 + r.uniform(-12, 12)), n(math.sin(a) * ln / 2 + r.uniform(-12, 12)), n(math.cos(a) * ln), n(math.sin(a) * ln)), stroke="#c9b991", w=1.3, o=round(r.uniform(.3, .7), 2)))
    d.add("".join(rect(r.uniform(0, W), r.uniform(0, H), r.uniform(3, 8), r.uniform(3, 8), "#c9a24a", round(r.uniform(.5, .9), 2), extra=' transform="rotate(%d)"' % r.randint(-8, 8)) for _ in range(60)))


@scenery("curtain", "舞台の幕", "赤い幕と木の床の舞台。発表会・寸劇・はじまりとおしまいに", "dark")
def _(d, r):
    d.__init__("#5c0f17")
    fold = d.pattern(150, H, '<rect width="150" height="%d" fill="%s"/>' % (H, d.grad([(0, "#5a0d16"), (.35, "#b3202c"), (.6, "#8c1622"), (1, "#4a0a12")], 0, 0, 1, 0)))
    d.add('<rect width="%d" height="900" fill="%s"/>' % (W, fold), '<rect width="%d" height="900" fill="%s"/>' % (W, d.grad([(0, "#000000", .45), (.3, "#000000", 0), (.8, "#000000", 0), (1, "#000000", .5)])))
    d.add(path("M0 0H%dV110" % W + "".join("Q%d 200 %d 110" % (W - 120 - k * 240, W - 240 - k * 240) for k in range(8)) + "Z", "#7a121d"), path("M0 110" + "".join("Q%d 200 %d 110" % (120 + k * 240, 240 + k * 240) for k in range(8)), stroke="#e2b54a", w=8))
    d.add('<rect y="900" width="%d" height="180" fill="%s"/>' % (W, d.grad([(0, "#6b4322"), (1, "#3a2210")])), "".join(line(x, 900, x - (960 - x) * .25, H, "#2c190b", 3, .5) for x in range(0, W + 1, 160)))
    d.glow(960, 500, 700, "#fff2cc", .14)


@scenery("room", "部屋", "窓のある明るい部屋の壁と床。暮らし・家・身近な話に", "light")
def _(d, r):
    d.__init__(("#f4ead8", "#efe2cc"))
    d.add('<rect y="800" width="%d" height="280" fill="%s"/>' % (W, d.grad([(0, "#c89a66"), (1, "#a97c4c")])), "".join(line(0, y, W, y, "#8f6639", 2, .5) for y in (870, 950, 1030)), rect(0, 780, W, 24, "#ffffff"))
    d.add(rect(180, 150, 460, 420, "#ffffff", rx=6), '<rect x="204" y="174" width="412" height="372" fill="%s"/>' % d.grad([(0, "#8ccbf5"), (1, "#e3f4fd")]), rect(402, 174, 16, 372, "#ffffff"), rect(204, 352, 412, 16, "#ffffff"),
          cloud(330, 270, .35), cloud(520, 450, .3))
    d.add('<polygon points="640,600 1150,800 420,800 250,600" fill="#ffffff" fill-opacity=".2"/>')
    d.add(rect(1360, 190, 260, 200, "#8a5a33", rx=4), rect(1376, 206, 228, 168, "#f7f3ea"), poly([(1390, 360), (1450, 280), (1500, 330), (1540, 290), (1590, 360)], "#7fb48a"), circ(1560, 250, 18, "#f2b04c"))
    d.add(rect(1640, 640, 110, 150, "#d8734d", rx=10), "".join('<ellipse cx="1695" cy="560" rx="34" ry="110" fill="#4f9a5c" transform="rotate(%d 1695 660)"/>' % a for a in (-40, -18, 6, 28, 48)))


@scenery("washitsu", "和室", "障子と畳の和室。和風・昔の話・落ち着いた語りに", "light")
def _(d, r):
    d.__init__("#e9dcc0")
    d.add(rect(0, 0, W, 70, "#5a3d22"), rect(0, 760, W, 26, "#5a3d22"))
    for i in range(4):
        x = 60 + i * 455
        d.add(rect(x, 70, 435, 690, "#fbf7ec", extra=' stroke="#5a3d22" stroke-width="14"'), "".join(line(x + k * 108.75, 70, x + k * 108.75, 760, "#7a5a36", 5) for k in range(1, 4)),
              "".join(line(x, 70 + k * 115, x + 435, 70 + k * 115, "#7a5a36", 5) for k in range(1, 6)))
    d.add('<rect y="786" width="%d" height="294" fill="%s"/>' % (W, d.grad([(0, "#b9b775"), (1, "#a3a160")])))
    d.add('<rect y="786" width="%d" height="294" fill="%s"/>' % (W, d.pattern(8, 8, line(0, 0, 8, 0, "#8f8d50", 1.5, .35))))
    d.add(line(640, 786, 400, H, "#2f3a2a", 14), line(1280, 786, 1520, H, "#2f3a2a", 14), line(0, 792, W, 792, "#2f3a2a", 12))


@scenery("wood", "木の板", "濃い色の木の板の壁。喫茶・手づくり・あたたかい語りに", "dark")
def _(d, r):
    d.__init__("#4a2f1b")
    for i in range(6):
        y, c = i * 180, ("#5b3a22", "#523320", "#63402a", "#4e3120", "#5e3c25", "#553622")[i]
        d.add(rect(0, y, W, 176, c))
        for _k in range(9):
            yy = y + r.uniform(14, 162)
            d.add(path(smooth([(x, yy + r.uniform(-7, 7)) for x in range(-100, W + 201, 200)]), stroke="#2f1c10", w=r.uniform(1, 2.5), o=round(r.uniform(.2, .5), 2)))
        for _k in range(r.randint(0, 2)):
            x, yy = r.uniform(100, W - 100), y + r.uniform(50, 126)
            d.add(ell(x, yy, 30, 13, "#2f1c10", .5), ell(x, yy, 16, 6, "#1f120a", .6))
        d.add(line(r.uniform(300, W - 300), y, r.uniform(300, W - 300), y, "#1f120a", 3))
    i = d.id()
    d.defs.append(rgrad(i, [(0, "#000", 0), (.5, "#000", 0), (1, "#000", .5)], 960, 540, 1150))
    d.fill("url(#%s)" % i)


@scenery("brick", "れんがの壁", "赤茶のれんがの壁。街角・店・カジュアルな語りに", "dark")
def _(d, r):
    d.__init__("#3b2a25")
    b = "".join(rect(x, y, 112, 52, c, rx=3) for x, y, c in ((4, 4, "#8f3f2e"), (124, 4, "#9b4a35"), (-56, 64, "#84392a"), (64, 64, "#96432f"), (184, 64, "#8a3d2c")))
    d.fill(d.pattern(240, 120, b))
    d.add("".join(rect(r.randint(0, 16) * 120 + (4 if k % 2 else 64), r.randint(0, 8) * 120 + (4 if k % 2 else 64), 112, 52, r.choice(("#6f2f22", "#a8563d", "#7a3526")), .7, 3) for k in range(40)))
    i = d.id()
    d.defs.append(rgrad(i, [(0, "#000", 0), (.45, "#000", .1), (1, "#000", .6)], 960, 480, 1200))
    d.fill("url(#%s)" % i)


@scenery("bookshelf", "本棚", "本がぎっしり並ぶ本棚。読書・学び・調べものの話に", "dark")
def _(d, r):
    d.__init__("#2b1b10")
    cols = ("#8c3b3b", "#3f5f8a", "#4f7a55", "#b08a3c", "#6b4a7e", "#a35a34", "#2f6f73", "#7a7466", "#b54d5e", "#35486b")
    for row in range(4):
        y0, x = 40 + row * 262, 50
        d.add(rect(30, y0, W - 60, 232, "#1c110a"))
        while x < W - 90:
            w, h = r.randint(26, 62), r.randint(150, 222)
            if r.random() < .06:
                x += r.randint(30, 70)
                continue
            c = r.choice(cols)
            d.add(rect(x, y0 + 232 - h, w, h, c, rx=2), rect(x + 4, y0 + 232 - h + 18, w - 8, 6, "#f1e3bd", .7), rect(x + 4, y0 + 232 - 30, w - 8, 4, "#f1e3bd", .5))
            x += w + 2
        d.add(rect(0, y0 + 232, W, 30, "#5a3a20"), rect(0, y0 + 232, W, 6, "#7a5230"))
    d.add(rect(0, 0, 30, H, "#5a3a20"), rect(W - 30, 0, 30, H, "#5a3a20"), rect(0, 0, W, 40, "#5a3a20"))
    i = d.id()
    d.defs.append(rgrad(i, [(0, "#000", .25), (1, "#000", .55)], 960, 540, 1150))
    d.fill("url(#%s)" % i)


@scenery("studio", "ニュースのスタジオ", "青い光の帯と、つやのある床のスタジオ。ニュース・報告・番組風に", "dark")
def _(d, r):
    d.__init__(("#06122e", "#0d2a63", "#081a3f"))
    d.glow(960, 420, 900, "#2f7bff", .35)
    for i in range(9):
        x = 60 + i * 225
        d.add(rect(x, 110, 170, 560, "#0b2152", .85, 8, ' stroke="#3d86ff" stroke-opacity=".5" stroke-width="2"'), rect(x + 20, 130, 8, 520, "#6fc3ff", .8, 4), rect(x + 142, 130, 8, 520, "#6fc3ff", .35, 4))
    d.add('<rect y="740" width="%d" height="340" fill="%s"/>' % (W, d.grad([(0, "#0f2f6e"), (1, "#040b1f")])), rect(0, 734, W, 8, "#7fd0ff", .8))
    for i in range(9):
        d.add('<rect x="%d" y="742" width="170" height="240" fill="%s"/>' % (60 + i * 225, d.grad([(0, "#6fc3ff", .22), (1, "#6fc3ff", 0)])))
    d.add("".join(circ(200 + i * 304, 60, 14, "#ffffff", .9) for i in range(6)))


def make():
    os.makedirs(OUT, exist_ok=True)
    index, seen = {}, set()
    for i, (name, kind, label, desc, tone, fn) in enumerate(PRESETS):
        assert name not in seen, name
        seen.add(name)
        d = Doc()
        fn(d, random.Random(1000 + sum(ord(c) * (k + 1) for k, c in enumerate(name))))
        text = d.svg(kind == "themed")
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
            f.write(text)
        index[name] = {"file": name + ".svg", "label": label, "desc": desc, "kind": kind}
        if tone:
            index[name]["tone"] = tone
    for f in os.listdir(OUT):   # 一覧に無い SVG は消す（名前を変えたとき）
        if f.endswith(".svg") and f[:-4] not in index:
            os.remove(os.path.join(OUT, f))
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return index


if __name__ == "__main__":
    idx = make()
    size = sum(os.path.getsize(os.path.join(OUT, v["file"])) for v in idx.values())
    print("bg/: %d 枚（配色に合わせる %d・景色 %d）、合計 %d KB、最大 %d KB" % (
        len(idx), sum(v["kind"] == "themed" for v in idx.values()), sum(v["kind"] == "scenery" for v in idx.values()), size // 1024,
        max(os.path.getsize(os.path.join(OUT, v["file"])) for v in idx.values()) // 1024))
