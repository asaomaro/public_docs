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


# ================= 2026-10-07 に足した背景（和柄と地 11・地の景色 5・場所 24） =================


def vig(d, c="#000000", o=.3, start=.55):
    """周りを暗くする（まん中は そのまま）。"""
    i = d.id()
    d.defs.append(rgrad(i, [(0, c, 0), (start, c, 0), (1, c, o)], 960, 540, 1150))
    d.fill("url(#%s)" % i)


def band(d, y, h, stops):
    """横いっぱいの帯（上から下への色の移り）。"""
    d.add('<rect y="%s" width="%d" height="%s" fill="%s"/>' % (n(y), W, n(h), d.grad(stops)))


def wash(d, c, o, rad=780, cy=560):
    """まん中に、地の色の淡いにじみを重ねて、絵のコントラストを抑える（字を載せる所）。"""
    d.glow(960, cy, rad, c, o)


def tree(x, y, s, leaf="#6fb565", leaf2="#58a056", trunk="#8a6238"):
    return (rect(x - 9 * s, y - 120 * s, 18 * s, 120 * s, trunk, rx=4 * s) + circ(x, y - 190 * s, 90 * s, leaf2) + circ(x - 60 * s, y - 150 * s, 62 * s, leaf2) + circ(x + 62 * s, y - 150 * s, 60 * s, leaf2)
            + circ(x - 16 * s, y - 206 * s, 70 * s, leaf) + circ(x + 40 * s, y - 170 * s, 50 * s, leaf))


def desk(x, y, s):
    return (rect(x + 14 * s, y, 8 * s, 150 * s, "#98a3ae") + rect(x + 218 * s, y, 8 * s, 150 * s, "#98a3ae") + rect(x + 14 * s, y + 60 * s, 212 * s, 8 * s, "#98a3ae")
            + rect(x, y - 6 * s, 240 * s, 22 * s, "#dcb780", rx=4 * s) + rect(x, y + 10 * s, 240 * s, 6 * s, "#b98f58"))


def palm(x, y, h, lean):
    tx, ty, L = x + lean, y - h, h * .52
    out = path("M%s %sQ%s %s %s %s" % (n(x), n(y), n(x + lean * .1), n(y - h * .6), n(tx), n(ty)), stroke="#a8763f", w=h * .06, extra=' stroke-linecap="round"')
    for i, a in enumerate((-172, -140, -100, -62, -28, 8, 176)):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        ex, ey = tx + ca * L, ty + sa * L + L * .38
        out += path("M%s %sQ%s %s %s %sQ%s %s %s %sZ" % (n(tx), n(ty), n(tx + ca * L * .55), n(ty + sa * L * .55 - L * .28), n(ex), n(ey), n(tx + ca * L * .5), n(ty + sa * L * .5 + L * .04), n(tx), n(ty)),
                    "#3f9a5c" if i % 2 else "#58b06e")
    return out + circ(tx - 10, ty + 12, h * .026, "#7a5533") + circ(tx + 12, ty + 14, h * .026, "#7a5533")


def books(d, r, x0, x1, y0, h, cols, sc=1.0):
    """棚の 1 段に、本を並べる。"""
    x = x0
    while x < x1 - 12 * sc:
        w, bh = r.randint(14, 34) * sc, h * r.uniform(.6, .94)
        if x + w > x1:
            break
        if r.random() < .08:
            x += w
            continue
        d.add(rect(x, y0 + h - bh, w, bh, r.choice(cols), rx=1.5))
        x += w + 1.5


# ---------- 和柄・地（配色に合わせる） ----------


@themed("yagasuri", "矢絣", "矢羽根を縦に並べた和の模様。和風・卒業・大正ふうの話に")
def _(d, r):
    def feather(x0, y0):
        return poly([(x0 + 6, y0), (x0 + 80, y0 + 40), (x0 + 80, y0 + 100), (x0 + 6, y0 + 60)], "a2") + poly([(x0 + 80, y0 + 40), (x0 + 154, y0), (x0 + 154, y0 + 60), (x0 + 80, y0 + 100)], "a2", .6)
    c = feather(0, 0) + feather(160, 60) + feather(160, -60) + line(80, 0, 80, 120, "bg0", 3) + line(240, 0, 240, 120, "bg0", 3)
    p = d.pattern(320, 120, c)
    d.fill(p, .05).fill(p, .17, d.mask("edges"))


@themed("kagome", "籠目", "竹かごの編み目の和の模様。和風・魔よけ・手仕事の話に")
def _(d, r):
    a = 64
    q = a * math.sqrt(3)
    seg = "M0 0H%s M0 %sH%s M0 %sH%s M%s 0L%s %s M0 %sL%s %s M%s 0L0 %s M%s %sL%s %s" % (
        n(2 * a), n(q), n(2 * a), n(2 * q), n(2 * a), n(a / 2), n(2 * a), n(1.5 * q), n(1.5 * q), n(a / 2), n(2 * q), n(1.5 * a), n(1.5 * q), n(2 * a), n(1.5 * q), n(1.5 * a), n(2 * q))
    p = d.pattern(2 * a, 2 * q, path(seg, stroke="a1", w=3))
    d.fill(p, .07).fill(p, .3, d.mask("corners"))


@themed("tatewaku", "立涌", "向かい合う波の線が、ふくらみを作る和の模様。和風・上品・縁起のよい話に")
def _(d, r):
    g = ""
    for k in range(-1, 18):
        x0, s = k * 120, (1 if k % 2 else -1)
        g += path(smooth([(x0 + s * 30 * math.sin(y / 110 * math.pi), y) for y in range(-55, H + 111, 55)]), stroke="a2", w=3)
        for j in range(-1, 6):
            g += circ(x0 + 60, (55 if k % 2 == 0 else 165) + j * 220, 9, "a1")
    d.add('<g opacity=".07">%s</g>' % g, '<g opacity=".3"%s>%s</g>' % (d.mask("edges"), g))


@themed("kanoko", "鹿の子", "絞り染めの小さな粒が並ぶ和の模様。和風・かわいらしい・祝いの話に")
def _(d, r):
    p = d.pattern(56, 56, path("M28 6L50 28L28 50L6 28Z", stroke="a1", w=4, extra=' stroke-linejoin="round"') + circ(28, 28, 5, "a1"))
    d.fill(p, .06).fill(p, .3, d.mask("corners"))


@themed("hishi", "菱", "菱形を重ねた和の模様。和風・格式・ひな祭りの話に")
def _(d, r):
    p = d.pattern(140, 80, path("M70 0L140 40L70 80L0 40Z M70 18L108 40L70 62L32 40Z", stroke="a2", w=2.5))
    d.fill(p, .08).fill(p, .32, d.mask("edges"))


@themed("linen", "布の織り目", "麻布のような、縦糸と横糸の細かい織り目。手づくり・暮らし・落ち着いた語りに")
def _(d, r):
    d.glow(1400, 200, 1000, "a1", .1)
    d.fill(d.pattern(10, 10, rect(0, 0, 10, 4, "ink", .5) + rect(0, 0, 4, 10, "ink", .5)), .1)
    for _k in range(150):
        x, y, ln, hz = r.uniform(0, W), r.uniform(0, H), r.uniform(60, 420), r.random() < .5
        d.add(line(x, y, x + (ln if hz else 0), y + (0 if hz else ln), "ink", r.choice((1.5, 2.5, 3.5)), round(r.uniform(.03, .08), 3)))


@themed("woodgrain", "木目", "板の木目と節。配色の色になじむ木の地。手づくり・喫茶・あたたかい語りに")
def _(d, r):
    d.glow(960, 540, 1300, "a1", .12)
    for i in range(5):
        y = i * 216
        d.add(rect(0, y, W, 216, "a1", .03 + .03 * (i % 2)), line(0, y, W, y, "ink", 3, .16))
        knots = [(r.uniform(150, W - 150), y + r.uniform(60, 156)) for _ in range(r.randint(0, 2))]
        for k in range(8):
            yy = y + 14 + k * 26 + r.uniform(-5, 5)
            pts = [(x, yy + r.uniform(-4, 4) + sum(34 * math.copysign(1, yy - ky) * math.exp(-((x - kx) / 150) ** 2) * math.exp(-abs(yy - ky) / 60) for kx, ky in knots)) for x in range(-100, W + 201, 100)]
            d.add(path(smooth(pts), stroke="ink", w=r.uniform(1, 2.4), o=round(r.uniform(.07, .16), 3)))
        for kx, ky in knots:
            d.add(ell(kx, ky, 34, 14, "ink", .1), ell(kx, ky, 18, 7, "ink", .12))


@themed("marble", "大理石", "やわらかな色むらと、細い筋。上品・高級・美術の話に")
def _(d, r):
    for x, y, rad, c, o in ((400, 250, 800, "a3", .12), (1500, 800, 900, "a2", .1), (1300, 150, 600, "ink", .05)):
        d.glow(x, y, rad, c, o)
    for k in range(11):
        x, y, a = r.uniform(-100, W + 100), -40, r.uniform(.6, 2.5)
        pts = [(x, y)]
        while -80 < x < W + 80 and y < H + 80:
            a = max(.3, min(2.84, a + r.uniform(-.4, .4)))
            x, y = x + math.cos(a) * 70, y + math.sin(a) * 70
            pts.append((x, y))
        if len(pts) > 3:
            d.add(path(smooth(pts), stroke="ink", w=r.uniform(1, 3.2), o=round(r.uniform(.06, .14), 3)))
            b = pts[len(pts) // 2:len(pts) // 2 + 5]
            d.add(path(smooth([(px + i * i * 9, py + i * 14) for i, (px, py) in enumerate(b)] + [(b[-1][0] + 300, b[-1][1] + 120)]), stroke="ink", w=1.2, o=.07))


@themed("gingham", "ギンガム", "2 色が重なる格子じま。ポップ・料理・ピクニック・親しみやすい話に")
def _(d, r):
    p = d.pattern(120, 120, rect(0, 0, 60, 120, "a2", .5) + rect(0, 0, 120, 60, "a2", .5))
    d.fill(p, .07).fill(p, .2, d.mask("edges"))


@themed("mizutama", "水玉", "2 色の水玉が互い違いに並ぶ。ポップ・子ども向け・楽しい話に")
def _(d, r):
    p = d.pattern(140, 140, circ(35, 35, 22, "a2") + circ(105, 105, 22, "a1"))
    d.fill(p, .07).fill(p, .24, d.mask("edges"))


@themed("pinstripe", "細い縦じま", "細い縦の線が等間隔に並ぶ、背広の生地のような地。ビジネス・きちんとした話に")
def _(d, r):
    d.glow(960, 300, 1100, "a2", .1)
    d.fill(d.pattern(44, 44, line(22, 0, 22, 44, "ink", 1.5)), .13)
    vig(d, o=.2)


# ---------- 地の景色（色は決まっている） ----------


@scenery("blueprint-blue", "青焼きの図面", "青い紙に白い線の図面。歯車と寸法線。設計・ものづくり・計画の話に", "dark")
def _(d, r):
    d.__init__(("#17508f", "#123f75"))
    d.fill(d.pattern(40, 40, path("M40 0H0V40", stroke="#ffffff", w=1)), .12)
    d.fill(d.pattern(200, 200, path("M200 0H0V200", stroke="#ffffff", w=1.6)), .2)
    wl = ' fill="none" stroke="#ffffff" stroke-opacity=".5" stroke-width="2.5"'
    dash = ' fill="none" stroke="#ffffff" stroke-opacity=".4" stroke-width="1.5" stroke-dasharray="18 8 4 8"'
    cx, cy, R, teeth = 300, 820, 190, 16
    pts = [(cx + math.cos(k / (teeth * 4) * math.tau) * (R if k % 4 in (0, 1) else R - 34), cy + math.sin(k / (teeth * 4) * math.tau) * (R if k % 4 in (0, 1) else R - 34)) for k in range(teeth * 4)]
    d.add('<polygon points="%s"%s/>' % (" ".join("%s,%s" % (n(x), n(y)) for x, y in pts), wl), '<circle cx="300" cy="820" r="56"%s/>' % wl, '<circle cx="300" cy="820" r="118"%s/>' % dash,
          '<path d="M60 820H540M300 580V1060"%s/>' % dash)
    d.add('<rect x="1360" y="130" width="420" height="250" rx="34"%s/>' % wl, "".join('<circle cx="%d" cy="%d" r="22"%s/>' % (x, y, wl) for x in (1420, 1720) for y in (190, 320)),
          '<circle cx="1570" cy="255" r="70"%s/>' % wl, '<path d="M1300 255H1840M1570 90V420"%s/>' % dash)
    for x0, y0, x1, y1 in ((1360, 440, 1780, 440), (1840, 130, 1840, 380), (110, 560, 490, 560)):   # 寸法線
        hz = y0 == y1
        d.add(line(x0, y0, x1, y1, "#ffffff", 1.5, .55), line(x0 - (0 if hz else 12), y0 - (12 if hz else 0), x0 + (0 if hz else 12), y0 + (12 if hz else 0), "#ffffff", 1.5, .55),
              line(x1 - (0 if hz else 12), y1 - (12 if hz else 0), x1 + (0 if hz else 12), y1 + (12 if hz else 0), "#ffffff", 1.5, .55))
    d.add('<rect x="1400" y="900" width="460" height="130"%s/>' % wl, '<path d="M1400 945H1860M1400 990H1860M1620 900V1030M1740 945V1030"%s/>' % wl)
    d.add(rect(30, 30, W - 60, H - 60, "none", extra=' stroke="#ffffff" stroke-opacity=".35" stroke-width="3"'))
    vig(d, "#061a36", .5, .5)


@scenery("stone-wall", "石垣", "大きさの違う石を積んだ、灰色の石垣。城・歴史・どっしりした話に", "dark")
def _(d, r):
    d.__init__("#22262a")
    y = -20
    while y < H:
        h, x = r.randint(96, 150), -r.randint(0, 140)
        while x < W:
            w, c = r.randint(130, 300), r.choice(("#4f565d", "#5a6067", "#484e55", "#62676c", "#525453"))
            pts = [(x + 12 + r.uniform(0, 14), y + 12 + r.uniform(0, 12)), (x + w - 12 - r.uniform(0, 14), y + 12 + r.uniform(0, 12)), (x + w - 12 - r.uniform(0, 10), y + h - 12 - r.uniform(0, 12)), (x + 12 + r.uniform(0, 10), y + h - 12 - r.uniform(0, 12))]
            d.add(poly(pts, c, extra=' stroke="%s" stroke-width="14" stroke-linejoin="round"' % c), line(pts[0][0] + 6, pts[0][1] - 2, pts[1][0] - 6, pts[1][1] - 2, "#ffffff", 3, .07),
                  line(pts[3][0] + 6, pts[3][1] + 3, pts[2][0] - 6, pts[2][1] + 3, "#000000", 4, .18))
            x += w
        y += h
    d.add("".join(circ(r.uniform(0, W), r.uniform(0, H), r.uniform(4, 12), "#5d7a4a", round(r.uniform(.15, .4), 2)) for _ in range(60)))
    vig(d, "#000000", .6, .3)


@scenery("tile-wall", "白いタイル", "目地のある白いタイルの壁。台所・浴室・清潔・料理や暮らしの話に", "light")
def _(d, r):
    d.__init__("#cdd7dc")
    d.fill(d.pattern(120, 120, '<rect x="3" y="3" width="114" height="114" rx="6" fill="%s"/>' % d.grad([(0, "#ffffff"), (1, "#eef3f5")], 0, 0, 1, 1)))
    d.add("".join(rect(r.randint(0, 15) * 120 + 3, r.randint(0, 8) * 120 + 3, 114, 114, r.choice(("#dcecf2", "#e6f1ee", "#f3efe4")), .8, 6) for _ in range(26)))
    d.glow(500, 200, 900, "#ffffff", .5)
    vig(d, "#4f7386", .22, .5)


@scenery("tatami", "畳", "上から見た畳の間。い草の目と、畳のへり。和風・茶の間・落ち着いた語りに", "light")
def _(d, r):
    d.__init__("#dedab0")
    wv = d.pattern(7, 7, line(0, 0, 0, 7, "#b9b57e", 2, .5))
    wh = d.pattern(7, 7, line(0, 0, 7, 0, "#b9b57e", 2, .5))
    for x, y, w, h in ((0, 0, 960, 480), (960, 0, 480, 960), (1440, 0, 480, 960), (0, 480, 480, 960), (480, 480, 480, 960), (960, 960, 960, 480)):
        hz = w > h
        d.add(rect(x, y, w, h, r.choice(("#e0dcb2", "#dad6a8", "#e5e1ba"))), '<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (x, y, w, h, wv if hz else wh))
        for k in (0, 1):   # へり（長い辺）
            d.add(rect(x, y + k * (h - 22), w, 22, "#5f6b4c") if hz else rect(x + k * (w - 22), y, 22, h, "#5f6b4c"))
        d.add(rect(x, y, w, h, "none", extra=' stroke="#8f8b55" stroke-width="2"'))
    d.glow(700, 300, 900, "#fffbe0", .3)
    vig(d, "#3a3515", .25, .5)
    wash(d, "#f4f1d6", .35)


@scenery("denim", "デニム", "藍色のあや織りの布と、橙の縫い目。カジュアル・若者・ファッションの話に", "dark")
def _(d, r):
    d.__init__(("#2f4f80", "#243e69"))
    d.fill(d.pattern(8, 8, line(-2, 10, 10, -2, "#9db7dd", 1.6) + line(-2, 2, 2, -2, "#9db7dd", 1.6) + line(6, 10, 10, 6, "#9db7dd", 1.6)), .22)
    d.add("".join(line(x, y, x, y + r.uniform(30, 160), "#ffffff", 1.5, round(r.uniform(.03, .1), 3)) for x, y in ((r.uniform(0, W), r.uniform(-50, H)) for _ in range(240))))
    st = ' fill="none" stroke="#e39a3c" stroke-width="5" stroke-dasharray="22 12" stroke-linecap="round" stroke-opacity=".9"'
    d.add(rect(0, 0, 170, H, "#1f3559", .35), '<path d="M118 0V1080M150 0V1080"%s/>' % st)
    d.add('<path d="M1380 1080V760Q1380 720 1420 716L1920 660"%s/>' % st, '<path d="M1412 1080V772Q1412 750 1436 748L1920 692"%s/>' % st)
    d.add(circ(1398, 738, 17, "#b8763a"), circ(1398, 738, 8, "#8a5220"))
    vig(d, "#0a1428", .5, .45)


# ---------- 場所（色は決まっている） ----------


@scenery("classroom", "教室", "窓から光の入る教室と、机の列。学校・授業・思い出の話に", "light")
def _(d, r):
    d.__init__(("#f6efdf", "#efe5cf"))
    for i in range(4):
        x = 330 + i * 400
        d.add(rect(x, 150, 360, 430, "#ffffff", rx=4), '<rect x="%d" y="166" width="328" height="398" fill="%s"/>' % (x + 16, d.grad([(0, "#a9d8f7"), (1, "#eaf6fd")])), rect(x + 172, 166, 16, 398, "#ffffff"), rect(x + 16, 330, 328, 12, "#ffffff"))
    d.add(cloud(620, 250, .3), cloud(1380, 290, .35), cloud(1010, 230, .22), rect(300, 580, 1640, 22, "#d9c9a8"))
    d.add(poly([(0, 110), (230, 170), (230, 600), (0, 680)], "#7a5230"), poly([(0, 132), (214, 186), (214, 584), (0, 654)], "#2f5a45"), poly([(0, 654), (214, 584), (230, 600), (0, 690)], "#a06b3c"))
    band(d, 740, 340, [(0, "#d6ad7c"), (1, "#bd8f5c")])
    d.add(rect(0, 728, W, 14, "#c9b48c"), "".join(line(x, 740, 960 + (x - 960) * 1.6, H, "#a37646", 2, .5) for x in range(0, W + 1, 160)))
    d.add(poly([(620, 742), (1700, 742), (1920, 1080), (420, 1080)], "#ffffff", .14))
    d.add("".join(desk(210 + k * 385, 810, .8) for k in range(4)), "".join(desk(90 + k * 520, 940, 1.15) for k in range(4)))
    wash(d, "#fffaf0", .30)


@scenery("lab", "研究室", "実験台とフラスコ、薬びんの棚。科学・実験・研究の話に", "light")
def _(d, r):
    d.__init__(("#eff5f8", "#e3edf1"))
    by = 860   # 実験台の上の面
    for x0 in (70, 1330):   # 壁の棚と薬びん
        for y0 in (190, 400):
            d.add(rect(x0, y0, 520, 14, "#b9c6ce", rx=4))
            x = x0 + 20
            while x < x0 + 480:
                w, h, c = r.randint(34, 60), r.randint(70, 130), r.choice(("#8fc7e8", "#f2c46d", "#b8dfa8", "#e8a2a2", "#c7b8ea", "#a8693c"))
                d.add(rect(x, y0 - h, w, h, c, .85, 6), rect(x + w * .25, y0 - h - 12, w * .5, 14, "#6b7a86", rx=3), rect(x + 5, y0 - h * .6, w - 10, h * .28, "#ffffff", .75, 2))
                x += w + r.randint(10, 26)
    d.add(rect(760, 120, 400, 300, "#ffffff", rx=6), '<rect x="778" y="138" width="364" height="264" fill="%s"/>' % d.grad([(0, "#b3dcf6"), (1, "#eef8fd")]), rect(952, 138, 16, 264, "#ffffff"))
    band(d, by + 40, H - by - 40, [(0, "#f7f9fa"), (1, "#dfe7ec")])
    d.add(rect(0, by, W, 44, "#5a6a79"), rect(0, by, W, 10, "#738494"), "".join(line(x, by + 56, x, H, "#c3ced6", 3) + rect(x + 30, by + 84, 90, 12, "#aab6c0", rx=6) for x in range(0, W, 320)))
    gl = ' stroke="#8fb3c6" stroke-width="4" stroke-linejoin="round"'
    for x, sc, c in ((300, 1.2, "#5fc0d8"), (520, .9, "#f0a95a"), (1560, 1.1, "#8fd08a")):   # 三角フラスコ
        d.add('<g transform="translate(%d %d) scale(%s)">%s%s</g>' % (x, by, n(sc), '<path d="M-14 -150H14V-96L62 -8Q66 0 56 0H-56Q-66 0 -62 -8L-14 -96Z" fill="#eaf6fb" fill-opacity=".8"%s/>' % gl,
                                                                    '<path d="M-36 -52H36L60 -8Q62 -3 56 -3H-56Q-62 -3 -60 -8Z" fill="%s" fill-opacity=".85"/>' % c))
    d.add(rect(700, by - 40, 220, 22, "#a9bcc8", rx=4), "".join(rect(718 + k * 50, by - 130, 26, 104, "#eaf6fb", .85, 12, gl) + rect(721 + k * 50, by - 80 - (k % 3) * 10, 20, 50 + (k % 3) * 10, ("#e88f8f", "#8fb8e8", "#f2d06b", "#a9dba0")[k], .85, 10) for k in range(4)))
    d.add(rect(1180, by - 20, 200, 22, "#5a6a79", rx=6), rect(1290, by - 220, 34, 204, "#5a6a79", rx=8), '<path d="M1300 %dL1218 %d" stroke="#5a6a79" stroke-width="40" stroke-linecap="round"/>' % (by - 200, by - 130),
          rect(1194, by - 130, 44, 60, "#3f4d5a", rx=6), rect(1190, by - 50, 120, 12, "#7b8a98", rx=4))
    wash(d, "#f6fafc", .4)


@scenery("library", "図書館", "高い本棚にはさまれた通路と、奥の大きな窓。読書・調べもの・学びの話に", "light")
def _(d, r):
    d.__init__(("#f3ead8", "#eadfc8"))
    d.add(path("M700 660V330A260 260 0 0 1 1220 330V660Z", "#ffffff"), '<path d="M724 660V332A236 236 0 0 1 1196 332V660Z" fill="%s"/>' % d.grad([(0, "#bfe2f8"), (1, "#f2fafe")]))
    d.add(rect(952, 98, 16, 562, "#ffffff"), rect(724, 400, 472, 14, "#ffffff"), rect(724, 540, 472, 12, "#ffffff"))
    d.glow(960, 420, 700, "#ffffff", .55)
    band(d, 660, 420, [(0, "#cfab80"), (1, "#b08a5c")])
    d.add(poly([(830, 660), (1090, 660), (1400, H), (520, H)], "#9a4444", .3), poly([(858, 660), (1062, 660), (1330, H), (590, H)], "#b45a55", .3))
    cols = ("#a55252", "#57789f", "#6a9470", "#c2a05a", "#84679a", "#b8744e", "#4f8a8e", "#c9bfa9", "#c56b7a", "#526a8d")
    for x0, x1, top, bot, rows in ((345, 530, 160, 890, 6), (-20, 310, -40, 1120, 7)):
        for side in (0, 1):
            xa, xb = (x0, x1) if side == 0 else (W - x1, W - x0)
            sc, rh = (x1 - x0) / 330, (bot - top) / rows
            d.add(rect(xa, top, xb - xa, bot - top, "#8f6840"), rect(xa, top, xb - xa, bot - top, "none", extra=' stroke="#6f4e2c" stroke-width="%s"' % n(8 * sc)))
            for j in range(rows):
                y = top + j * rh + rh * .12
                d.add(rect(xa + 10 * sc, y, xb - xa - 20 * sc, rh * .8, "#5a3f22"))
                books(d, r, xa + 12 * sc, xb - 12 * sc, y, rh * .8, cols, max(.45, sc))
    d.add(rect(700, 960, 520, 26, "#7a5230", rx=6), rect(730, 986, 20, 100, "#5f3f22"), rect(1170, 986, 20, 100, "#5f3f22"))
    for x in (800, 1120):
        d.add(rect(x - 5, 900, 10, 60, "#3d4a40"), poly([(x - 46, 900), (x + 46, 900), (x + 28, 866), (x - 28, 866)], "#3f8a62"))
        d.glow(x, 930, 120, "#fff2c0", .5)
    wash(d, "#fbf3e2", .55)


@scenery("meeting-room", "会議室", "長い机といす、奥に白いスクリーン。会議・打ち合わせ・仕事の説明に", "light")
def _(d, r):
    d.__init__(("#eef1f4", "#e3e8ed"))
    d.add("".join(rect(260 + i * 380, 0, 260, 20, "#ffffff", rx=6) for i in range(4)))
    d.add(rect(520, 110, 880, 500, "#c3cbd4", rx=8), rect(536, 126, 848, 468, "#fbfcfd", rx=4))
    d.add(rect(60, 150, 330, 460, "#ffffff", rx=4), '<rect x="76" y="166" width="298" height="428" fill="%s"/>' % d.grad([(0, "#bfe0f6"), (1, "#eef8fd")]), "".join(rect(76, 166 + k * 36, 298, 10, "#ffffff", .85) for k in range(12)))
    d.add("".join('<ellipse cx="1695" cy="470" rx="34" ry="120" fill="%s" transform="rotate(%d 1695 590)"/>' % (c, a) for a, c in ((-44, "#4f9a5c"), (-20, "#5fae6c"), (4, "#4f9a5c"), (26, "#5fae6c"), (48, "#4f9a5c"))), rect(1640, 570, 110, 140, "#b9c0ca", rx=10))
    band(d, 700, 380, [(0, "#b3bfcc"), (1, "#97a4b4")])
    d.add(rect(0, 690, W, 12, "#ffffff"))
    d.add("".join(rect(400 + i * 250, 660, 130, 150, "#9aa7b8", rx=22) for i in range(5)))
    d.add(poly([(300, 800), (1620, 800), (1840, 1010), (80, 1010)], "#cda06c"), poly([(80, 1010), (1840, 1010), (1840, 1050), (80, 1050)], "#a57a48"), poly([(300, 800), (1620, 800), (1634, 814), (286, 814)], "#e0ba88"))
    d.add("".join(rect(250 + i * 400, 965, 220, 160, "#414f64", rx=30) for i in range(4)))
    wash(d, "#f4f6f8", .30)


@scenery("server-room", "サーバールーム", "両側に機械の棚が並ぶ、青い光の通路。IT・クラウド・データの話に", "dark")
def _(d, r):
    d.__init__(("#050b18", "#0a1730", "#071022"))
    vx, vy = 960, 500

    def P(sx, sy, z):
        s = 1 / (1 + z)
        return (vx + sx * s, vy + sy * s)
    d.add(poly([P(-700, 620, -.3), P(700, 620, -.3), P(700, 620, 5), P(-700, 620, 5)], "#0c1c36"), poly([P(-700, -560, -.3), P(700, -560, -.3), P(700, -560, 5), P(-700, -560, 5)], "#081327"))
    for z in (0, .35, .8, 1.4, 2.2, 3.3, 5):
        a, b = P(-700, 620, z), P(700, 620, z)
        d.add(line(a[0], a[1], b[0], b[1], "#2a5aa0", 2, .5))
    for sx in range(-700, 701, 280):
        a, b = P(sx, 620, -.3), P(sx, 620, 5)
        d.add(line(a[0], a[1], b[0], b[1], "#2a5aa0", 2, .4))
    d.add(poly([P(-80, -560, -.3), P(80, -560, -.3), P(80, -560, 5), P(-80, -560, 5)], "#bfe2ff", .3))
    a, b = P(-700, -560, 5), P(700, 620, 5)
    d.add(rect(a[0], a[1], b[0] - a[0], b[1] - a[1], "#10305c"), rect(a[0] + 70, a[1] + 40, b[0] - a[0] - 140, b[1] - a[1] - 40, "#3f8fe6", .7))
    d.glow(vx, vy, 520, "#2f7bff", .4)
    zs = (-.3, 0, .35, .8, 1.4, 2.2, 3.3, 5)
    for k in range(len(zs) - 2, -1, -1):
        z0, z1 = zs[k], zs[k + 1]
        for side in (-1, 1):
            sx = side * 700
            d.add(poly([P(sx, -560, z0), P(sx, -560, z1), P(sx, 620, z1), P(sx, 620, z0)], "#0d1a30", extra=' stroke="#234a80" stroke-width="2"'))
            for j in range(11):
                sy = -480 + j * 104
                a, b = P(sx, sy, z0 + (z1 - z0) * .16), P(sx, sy, z0 + (z1 - z0) * .84)
                d.add(line(a[0], a[1], b[0], b[1], "#1b3358", 10 / (1 + z0), .9))
                for t in (.2, .3, .42, .7):
                    if r.random() < .7:
                        q = P(sx, sy, z0 + (z1 - z0) * t)
                        d.add(circ(q[0], q[1], 4.5 / (1 + z0), r.choice(("#4de3a8", "#4de3a8", "#5bc0ff", "#ffc24d")), .95))
    vig(d, "#000000", .5, .5)


@scenery("station", "駅のホーム", "屋根と柱のあるホームと、線路の向こうの街。旅・通勤・出会いと別れの話に", "light")
def _(d, r):
    d.__init__(("#8cc6f0", "#d3ebfa", "#f1f9fe"))
    d.add(cloud(520, 330, .7, "#ffffff", .85), cloud(1350, 380, .55, "#ffffff", .8))
    d.add(path(under(hills(r, 640, 70, 120, .8)), "#b7d3c8"))
    for x, y, w, h in skyline(r, 700, 40, 130, 60, 130):
        d.add(rect(x, y, w, h, "#c6d6e2"))
    d.add(rect(0, 690, W, 26, "#aeb8c2"), rect(0, 716, W, 90, "#8a7765"), '<rect y="730" width="%d" height="52" fill="%s"/>' % (W, d.pattern(46, 52, rect(16, 0, 14, 52, "#5f4e40"))), rect(0, 740, W, 7, "#c9ced4"), rect(0, 766, W, 7, "#c9ced4"))
    band(d, 800, 280, [(0, "#dcdfe2"), (1, "#bfc4ca")])
    d.add(rect(0, 800, W, 14, "#f5f6f7"), rect(0, 836, W, 30, "#f2c230"), '<rect y="836" width="%d" height="30" fill="%s"/>' % (W, d.pattern(20, 30, circ(10, 9, 3, "#d9a514") + circ(10, 21, 3, "#d9a514"))))
    d.add(rect(0, 0, W, 70, "#4c647e"), rect(0, 70, W, 16, "#384c63"), "".join(rect(x, 86, 34, 730, "#5f7994") + rect(x - 14, 86, 62, 30, "#4c647e") + rect(x - 10, 786, 54, 30, "#4c647e") for x in (210, 1676)))
    d.add(rect(356, 86, 8, 54, "#384c63"), rect(656, 86, 8, 54, "#384c63"), rect(300, 138, 420, 96, "#1f5fa8", rx=6), rect(316, 154, 388, 30, "#ffffff", .92, 4), rect(316, 196, 250, 22, "#ffffff", .5, 4))
    d.add(rect(1446, 86, 8, 60, "#384c63"), circ(1450, 196, 56, "#384c63"), circ(1450, 196, 46, "#fbfcfd"), line(1450, 196, 1450, 164, "#2a3442", 5), line(1450, 196, 1474, 208, "#2a3442", 5))
    d.add(rect(1180, 930, 330, 22, "#3f7fb5", rx=6), rect(1180, 880, 330, 16, "#3f7fb5", rx=6), rect(1180, 905, 330, 12, "#3f7fb5", rx=6), rect(1200, 880, 14, 110, "#5b6672"), rect(1476, 880, 14, 110, "#5b6672"))
    wash(d, "#eef7fd", .50)


@scenery("shopping-street", "商店街", "日よけと店先が並ぶ通りと、三角の旗。買いもの・町・にぎわいの話に", "light")
def _(d, r):
    d.__init__(("#9fd3f5", "#e3f3fc", "#fbf3e0"))
    d.add(cloud(960, 250, .5, "#ffffff", .8))
    for x, y, w, h in skyline(r, 700, 60, 190, 70, 140):
        if 600 < x < 1200:
            d.add(rect(x, y, w, h, "#e6d9c4"))
    d.add(poly([(700, 700), (1220, 700), (W, H), (0, H)], "#dbcfba"), poly([(930, 700), (990, 700), (1110, H), (810, H)], "#efe6d4", .8))
    walls, awn = ("#f3e3c6", "#f1cfc6", "#cfe5d6"), ("#d8533f", "#3f8f6a", "#3f73b5")
    for k, (x0, x1, top, bot) in enumerate(((620, 735, 400, 790), (420, 620, 250, 900), (0, 420, 40, H))):
        for side in (0, 1):
            xa, xb = (x0, x1) if side == 0 else (W - x1, W - x0)
            w, h, ci = xb - xa, bot - top, (k + side) % 3
            d.add(rect(xa, top, w, h, walls[ci]), rect(xa, top, w, h * .04, "#c9b08a"))
            d.add(rect(xa + w * .18, top + h * .1, w * .64, h * .18, "#ffffff", rx=4), rect(xa + w * .21, top + h * .115, w * .58, h * .15, "#bfe0f2"), rect(xa + w * .49, top + h * .1, w * .02, h * .18, "#ffffff"))
            d.add(rect(xa + w * .1, top + h * .33, w * .8, h * .08, "#fbf6ea", rx=4), rect(xa + w * .16, top + h * .355, w * .5, h * .03, awn[ci], .7, 3))
            d.add(rect(xa + w * .06, top + h * .56, w * .88, h * .44, "#6f5140"), rect(xa + w * .1, top + h * .82, w * .8, h * .1, "#c79a66"))
            d.add("".join(circ(xa + w * (.16 + .1 * j), top + h * .81, w * .04, ("#e8743b", "#e2c23f", "#d8473f", "#7fb857")[(j + k) % 4]) for j in range(8)))
            nst = 8
            d.add("".join(rect(xa + w * j / nst, top + h * .46, w / nst + .5, h * .1, awn[ci] if j % 2 else "#fbf6ea") for j in range(nst)),
                  "".join(circ(xa + w * (j + .5) / nst, top + h * .56, w / nst / 2, awn[ci] if j % 2 else "#fbf6ea") for j in range(nst)))
    for y0, sag in ((40, 150), (150, 110)):   # 三角の旗
        d.add(path("M0 %dQ960 %d 1920 %d" % (y0, y0 + sag * 2, y0), stroke="#8a7a66", w=3))
        for j in range(25):
            t = (j + .5) / 25
            x, y = t * W, y0 + sag * 2 * 2 * t * (1 - t)
            d.add(poly([(x - 24, y), (x + 24, y), (x, y + 50)], ("#e8743b", "#3f8f6a", "#e2c23f", "#3f73b5", "#d8473f")[j % 5], .9))
    wash(d, "#fdf6e8", .50)


@scenery("kitchen", "台所", "タイルの壁と調理台、なべと棚。料理・暮らし・家の話に", "light")
def _(d, r):
    d.__init__("#f5efe2")
    cy = 850   # 調理台の上の面
    d.add(rect(0, 430, W, cy - 430, "#d6e0dd"), '<rect y="430" width="%d" height="%d" fill="%s"/>' % (W, cy - 430, d.pattern(96, 70, rect(2, 2, 92, 66, "#fbfdfc", rx=4))))
    d.add(rect(690, 90, 540, 320, "#ffffff", rx=6), '<rect x="708" y="108" width="504" height="284" fill="%s"/>' % d.grad([(0, "#a9d8f7"), (1, "#eaf6fd")]), rect(952, 108, 16, 284, "#ffffff"), rect(670, 404, 580, 20, "#e2d3b6", rx=4),
          cloud(840, 220, .3), rect(1100, 356, 50, 48, "#d8734d", rx=6), circ(1125, 336, 30, "#5fae6c"), circ(1104, 346, 20, "#4f9a5c"), circ(1148, 348, 18, "#4f9a5c"))
    for x in (50, 1370):
        d.add(rect(x, 50, 500, 320, "#ead9bb", rx=6), rect(x + 248, 50, 4, 320, "#c9b48c"), rect(x + 212, 300, 12, 46, "#a7b0b8", rx=6), rect(x + 276, 300, 12, 46, "#a7b0b8", rx=6), rect(x, 362, 500, 10, "#c9b48c"))
    for x0 in (90, 1390):   # 壁の棒と、つるした道具
        d.add(rect(x0, 476, 440, 8, "#a7b0b8", rx=4))
        for k, kind in enumerate((0, 1, 2, 0)):
            x = x0 + 70 + k * 100
            d.add(rect(x - 3, 484, 6, 110, "#8a949d", rx=3), (ell(x, 612, 26, 22, "#8a949d") if kind == 0 else rect(x - 20, 590, 40, 56, "#8a949d", rx=8) if kind == 1 else ell(x, 616, 16, 30, "#8a949d", extra=' fill-opacity=".6"')))
    band(d, cy + 36, H - cy - 36, [(0, "#f6efe0"), (1, "#e6dcc6")])
    d.add(rect(0, cy, W, 38, "#cfa878"), rect(0, cy, W, 8, "#e0be92"), "".join(line(x, cy + 50, x, H, "#cdbf9f", 3) + rect(x + 130, cy + 76, 60, 12, "#a7b0b8", rx=6) for x in range(0, W, 320)))
    d.add(rect(220, cy - 22, 400, 24, "#3d444c", rx=4), rect(300, cy - 110, 200, 90, "#d8734d", rx=14), rect(288, cy - 124, 224, 22, "#c2603c", rx=10), circ(400, cy - 132, 13, "#3d444c"), rect(268, cy - 86, 34, 14, "#3d444c", rx=6), rect(498, cy - 86, 34, 14, "#3d444c", rx=6))
    d.add("".join(path("M%d %dq-16 -22 0 -44q16 -22 0 -44" % (x, cy - 150), stroke="#ffffff", w=7, o=.8, extra=' stroke-linecap="round"') for x in (360, 400, 440)))
    d.add(path("M1090 %dV%da34 34 0 0 1 68 0v16" % (cy, cy - 60), stroke="#a7b0b8", w=14, extra=' stroke-linecap="round"'), rect(1000, cy - 6, 240, 10, "#b9c2c9", rx=4))
    d.add(rect(1330, cy - 44, 230, 46, "#dcb780", rx=8), circ(1400, cy - 50, 22, "#d8473f"), circ(1452, cy - 46, 18, "#e2c23f"), rect(1500, cy - 60, 90, 10, "#c9ced4", rx=3))
    for k, c in enumerate(("#e8c98a", "#b8d8a0", "#e8a98a")):
        d.add(rect(1640 + k * 86, cy - 100, 66, 100, "#f3f7f8", .9, 8, ' stroke="#b9c6cc" stroke-width="3"'), rect(1646 + k * 86, cy - 60, 54, 54, c, rx=6), rect(1636 + k * 86, cy - 114, 74, 18, "#8a6238", rx=5))
    wash(d, "#fbf7ee", .3)


@scenery("hospital", "病院", "淡い緑の病室。窓とカーテン、白いベッド。医療・健康・体の話に", "light")
def _(d, r):
    d.__init__(("#eef7f4", "#e2f0ec"))
    d.add(rect(560, 140, 620, 440, "#ffffff", rx=6), '<rect x="580" y="160" width="580" height="400" fill="%s"/>' % d.grad([(0, "#a9d8f7"), (1, "#eef8fd")]), rect(862, 160, 16, 400, "#ffffff"), cloud(740, 300, .35), cloud(1030, 420, .28))
    d.add(rect(40, 80, 1300, 10, "#b9c4c2", rx=5), "".join(rect(70 + k * 46, 90, 44, 640, "#bfe0dc" if k % 2 else "#a9d3ce", rx=18) for k in range(6)))
    d.add(rect(0, 660, W, 16, "#dcbd90", rx=0))
    band(d, 780, 300, [(0, "#d3e5e0"), (1, "#bcd4ce")])
    d.add(rect(0, 772, W, 12, "#ffffff"))
    d.add(rect(1560, 180, 150, 150, "#ffffff", rx=22), rect(1617, 205, 36, 100, "#3aa67a", rx=6), rect(1585, 237, 100, 36, "#3aa67a", rx=6))
    d.add(rect(1284, 300, 10, 620, "#aab4b8"), rect(1236, 300, 106, 10, "#aab4b8", rx=5), rect(1248, 316, 50, 90, "#dff1f7", rx=12, extra=' stroke="#9cc3d2" stroke-width="3"'), rect(1254, 360, 38, 40, "#9fd6ea", .8, 8),
          path("M1273 406V470Q1273 520 1330 560L1420 800", stroke="#9cc3d2", w=3), rect(1234, 916, 110, 12, "#aab4b8", rx=6))
    d.add(rect(1800, 610, 30, 330, "#b9c4c2", rx=8), rect(1226, 720, 26, 220, "#b9c4c2", rx=8), rect(1240, 868, 580, 24, "#b9c4c2", rx=6), rect(1250, 800, 566, 72, "#ffffff", rx=16), rect(1660, 762, 136, 52, "#ffffff", rx=24, extra=' stroke="#d5e2df" stroke-width="3"'),
          rect(1250, 776, 400, 96, "#9fcbe6", rx=20), rect(1250, 776, 400, 26, "#c3e0f1", rx=13), circ(1262, 950, 16, "#6b7a80"), circ(1806, 950, 16, "#6b7a80"))
    d.add(rect(330, 790, 200, 200, "#f7f3ea", rx=8, extra=' stroke="#d9cfb8" stroke-width="4"'), rect(346, 850, 168, 4, "#d9cfb8"), rect(406, 814, 48, 10, "#b9c4c2", rx=5), rect(406, 880, 48, 10, "#b9c4c2", rx=5),
          rect(402, 720, 56, 72, "#9fd6ea", .8, 10), circ(416, 690, 22, "#f2a0b4"), circ(446, 680, 22, "#f6c453"), circ(432, 708, 18, "#f2a0b4"), rect(428, 700, 5, 40, "#5fae6c"))
    wash(d, "#f2f9f7", .30)


@scenery("factory", "工場", "夕暮れの空に、のこぎり屋根と煙突の影。ものづくり・産業・働く話に", "dark")
def _(d, r):
    d.__init__(("#161c38", "#3a3256", "#8f5566", "#dc9562"))
    d.add(stars(r, 50, ymax=360))
    d.glow(960, 1000, 900, "#ffc27a", .3)
    for cx, cy in ((398, 250), (538, 170), (1560, 340)):
        d.add("".join(circ(cx + k * 40 + r.uniform(-10, 10), cy - k * 44, 40 + k * 18, "#cbb6c6", round(.24 - k * .035, 3)) for k in range(6)))
    far = "#3a3350"
    d.add(rect(1050, 620, 160, 260, far, rx=24), rect(1230, 660, 130, 220, far, rx=24), rect(700, 700, 320, 180, far), poly([(40, 880), (40, 720), (200, 660), (200, 880)], far))
    c = "#16162a"
    d.add(rect(370, 300, 56, 600, c), rect(362, 290, 72, 20, c), rect(510, 220, 56, 680, c), rect(502, 210, 72, 20, c), rect(370, 380, 56, 26, "#7a4a55"), rect(510, 300, 56, 26, "#7a4a55"), rect(1536, 380, 48, 520, c), rect(1528, 370, 64, 18, c))
    d.add("".join(poly([(620 + k * 190, 800), (620 + k * 190, 690), (810 + k * 190, 800)], c) for k in range(4)), rect(620, 800, 760, 120, c), rect(240, 760, 380, 160, c))
    d.add(rect(1420, 620, 190, 300, c, rx=30), rect(1640, 680, 150, 240, c, rx=30), path("M1420 700H1300V920M1610 760H1640M1790 800H1900V920", stroke=c, w=18))
    d.add("".join(rect(270 + k * 56, 800, 30, 36, "#ffd879", .9) for k in range(6)), "".join(rect(650 + k * 60, 830, 34, 24, "#ffd879", .85) for k in range(12)), "".join(rect(668 + k * 190, 730, 60, 40, "#ffe9a8", .5) for k in range(4)))
    d.add(rect(0, 900, W, 180, "#0f1020"), "".join(rect(x, 870, 6, 40, c) for x in range(0, W, 60)), rect(0, 880, W, 5, c))


@scenery("harbor", "港", "青い海と、クレーン、積まれたコンテナ、沖の船。貿易・物流・旅立ちの話に", "light")
def _(d, r):
    d.__init__(("#7cc0ee", "#cfe9f9", "#eef8fe"))
    d.add(cloud(400, 220, .9), cloud(1150, 300, .6, "#ffffff", .85))
    band(d, 640, 440, [(0, "#4a9bd6"), (1, "#2f76b5")])
    d.add("".join(rect(r.uniform(0, W), r.uniform(660, 870), r.uniform(30, 110), 4, "#ffffff", round(r.uniform(.25, .6), 2), 2) for _ in range(70)))
    cc = ("#d8533f", "#3f8f6a", "#e2a83f", "#3f73b5", "#8a6fb0")
    d.add(poly([(640, 612), (1130, 612), (1104, 656), (670, 656)], "#34506e"), rect(640, 606, 490, 8, "#d8533f"), rect(1040, 548, 70, 60, "#f4f6f8"), rect(1050, 558, 50, 12, "#5b7fa3"), rect(1062, 520, 22, 30, "#d8533f"),
          "".join(rect(670 + (k % 6) * 60, 584 - (k // 6) * 24, 56, 22, cc[(k * 3 + k // 6) % 5]) for k in range(11)))
    d.add(rect(0, 880, W, 200, "#b9bfc6"), rect(0, 880, W, 16, "#dfe3e7"), "".join(rect(x, 852, 44, 34, "#3d4854", rx=8) for x in (760, 1040)))
    for row in range(3):
        for k in range(4 - row):
            x, y = 50 + k * 196 + row * 70, 880 - (row + 1) * 86
            d.add(rect(x, y, 186, 82, cc[(k + row * 2) % 5], rx=3), "".join(line(x + 14 + j * 16, y + 8, x + 14 + j * 16, y + 74, "#000000", 2, .14) for j in range(11)))
    kr = "#e2683c"
    for x in (1420, 1700):   # 門の形のクレーン
        d.add(path("M%d 880V420M%d 880V420M%d 640H%d M%d 520L%d 640M%d 520L%d 640" % (x, x + 150, x, x + 150, x, x + 150, x + 150, x), stroke=kr, w=14), rect(x - 330, 404, 560, 26, kr), rect(x + 40, 350, 70, 56, kr),
              path("M%d 350L%d 404M%d 350L%d 404" % (x + 75, x - 320, x + 75, x + 220), stroke=kr, w=6), rect(x - 250, 430, 60, 34, "#3d4854"), line(x - 220, 464, x - 220, 560, "#3d4854", 3), rect(x - 258, 560, 76, 30, cc[(x // 100) % 5]))
    d.add("".join(path("M%d %dq12 -14 24 0q12 -14 24 0" % (x, y), stroke="#5b6f85", w=4) for x, y in ((620, 380), (700, 430), (1000, 200))))
    wash(d, "#e6f3fb", .55)


@scenery("space-station", "宇宙ステーション", "青い星のふちと、太陽電池の羽を広げた基地。宇宙開発・未来・国際協力の話に", "dark")
def _(d, r):
    d.__init__("#04060f")
    d.add(stars(r, 240, big=2.2))
    d.glow(300, 200, 600, "#3a4fd1", .22)
    d.add(circ(960, 2900, 2050, "#7fd3ff", .16), circ(960, 2900, 2030, "#7fd3ff", .3), '<circle cx="960" cy="2900" r="2010" fill="%s"/>' % d.grad([(0, "#2f86dc"), (.12, "#0e3f86")]))
    d.defs.append('<clipPath id="earth"><circle cx="960" cy="2900" r="2010"/></clipPath>')
    d.add('<g clip-path="url(#earth)">%s%s</g>' % ("".join(path(blob(x, y, 150, r, 9, .35), "#3f9a6a", o=.75) for x, y in ((520, 1040), (1500, 1010))),
                                                  "".join(ell(r.uniform(0, W), r.uniform(930, 1080), r.uniform(80, 240), r.uniform(10, 26), "#ffffff", round(r.uniform(.3, .65), 2)) for _ in range(16))))
    pan = d.pattern(26, 36, rect(0, 0, 26, 36, "#1f4f9e") + path("M26 0H0V36", stroke="#7fb0ee", w=1.5))
    body = (rect(-430, -7, 860, 14, "#aeb6c2") + "".join('<rect x="%d" y="%d" width="78" height="150" fill="%s" stroke="#9fb6d6" stroke-width="3"/>' % (sx, sy, pan) for sx in (-420, -320, 242, 342) for sy in (-172, 22))
            + rect(-34, -170, 68, 330, "#c3cad4", rx=26) + rect(-120, -48, 240, 96, "#dde2ea", rx=42) + rect(-150, -30, 34, 60, "#9aa3b0", rx=8) + rect(116, -30, 34, 60, "#9aa3b0", rx=8)
            + "".join(circ(-60 + k * 40, 0, 9, "#2a3a58") for k in range(4)) + rect(-200, 60, 90, 60, "#f4f6f8", rx=4) + rect(110, -120, 90, 60, "#f4f6f8", rx=4) + line(0, -170, 0, -230, "#c3cad4", 5) + circ(0, -236, 12, "#e8ecf2"))
    d.add('<g transform="translate(1530 290) rotate(-14) scale(.66)">%s</g>' % body)


@scenery("park", "公園", "木立と芝生、小道とベンチ、街灯。休日・散歩・身近な自然の話に", "light")
def _(d, r):
    d.__init__(("#8fd0f5", "#d8f0fb", "#f3fbfe"))
    d.add(cloud(480, 240, .8), cloud(1300, 180, .6, "#ffffff", .85))
    d.add("".join(circ(x, 650 + r.uniform(-24, 24), r.uniform(80, 124), "#a5d6a1") for x in range(-40, W + 100, 140)))
    d.add(path(under(hills(r, 720, 40, 120, .5)), "#93d072"), path(under(hills(r, 830, 40, 120, .5)), "#80c260"))
    d.add(path("M820 1080C880 940 1240 900 1130 800C1080 756 1000 740 960 726L1000 726C1060 740 1150 756 1210 800C1340 900 1140 940 1200 1080Z", "#efe0bc"))
    d.add(tree(1470, 760, .7), tree(520, 760, .6), tree(220, 860, 1.5), tree(1720, 840, 1.35))
    d.add(rect(1384, 590, 12, 370, "#3d4854"), rect(1372, 950, 36, 14, "#3d4854", rx=4), rect(1364, 560, 52, 12, "#3d4854", rx=4), circ(1390, 590, 24, "#fff6cf"))
    d.add(rect(400, 930, 320, 18, "#b0743f", rx=4), rect(400, 880, 320, 14, "#b0743f", rx=4), rect(400, 902, 320, 14, "#b0743f", rx=4), rect(420, 880, 14, 110, "#3d4854"), rect(686, 880, 14, 110, "#3d4854"))
    d.add("".join(circ(x, y, 9, c) + circ(x, y, 3.5, "#fff3b0") for x, y, c in ((r.choice((r.uniform(40, 360), r.uniform(1500, 1880))), r.uniform(960, 1060), r.choice(("#f28aa5", "#ffffff", "#f6c453", "#c79be8"))) for _ in range(36))))
    wash(d, "#eef9f0", .35)


@scenery("countryside", "田園", "山のふもとに広がる田んぼと、かやぶきの家。ふるさと・農業・昔の暮らしの話に", "light")
def _(d, r):
    d.__init__(("#9fd4f3", "#dcf0fa", "#f6fbf2"))
    d.add(cloud(420, 200, .8), cloud(1420, 260, .6, "#ffffff", .85))
    d.add(path(under(hills(r, 620, 200, 120, .6)), "#a9c9c8"), path(under(hills(r, 680, 130, 120, .9)), "#86b59a"))
    d.add(rect(0, 690, W, 390, "#a8d07a"))
    ys = [690 + 390 * (k / 6) ** 1.5 for k in range(7)]
    for k in range(6):
        d.add(rect(0, ys[k], W, ys[k + 1] - ys[k], "#9fcb72" if k % 2 else "#b6d98a"), '<rect y="%s" width="%d" height="%s" fill="%s" opacity=".5"/>' % (n(ys[k]), W, n(ys[k + 1] - ys[k]), d.pattern(14 + k * 8, 10 + k * 6, rect(0, 0, 4 + k * 2, 6 + k * 3, "#6fae52"))))
        d.add(rect(0, ys[k] - 3, W, 6 + k, "#7fa85a"))
    d.add("".join(poly([(960 + x * .12 - 5, 690), (960 + x * .12 + 5, 690), (960 + x + 14, H), (960 + x - 14, H)], "#7fa85a") for x in (-1500, -820, -260, 300, 880, 1560)))
    d.add(tree(150, 720, .9, "#5fa35a", "#4b8a4a"), rect(230, 590, 300, 110, "#f3ead6"), poly([(190, 600), (570, 600), (500, 480), (260, 480)], "#8a6a44"), poly([(250, 480), (510, 480), (490, 462), (270, 462)], "#6f5334"),
          rect(350, 630, 60, 70, "#6f5334"), rect(260, 626, 60, 44, "#8a6a44"), rect(440, 626, 60, 44, "#8a6a44"))
    d.add(line(1560, 500, 1560, 700, "#6f5a44", 9), line(1520, 530, 1600, 530, "#6f5a44", 7), path("M1600 530Q1760 580 1920 540", stroke="#6f5a44", w=2), path("M1520 530Q1000 620 560 520", stroke="#6f5a44", w=2, o=.5))
    wash(d, "#f1f9ee", .35)


@scenery("office", "オフィス", "大きな窓の向こうにビル街、手前に机と画面。会社・働き方・ビジネスの話に", "light")
def _(d, r):
    d.__init__(("#f7f8fa", "#e6eaef"))
    band(d, 120, 500, [(0, "#a9d6f5"), (1, "#e8f5fc")])
    d.add(cloud(520, 230, .5, "#ffffff", .8), cloud(1380, 200, .4, "#ffffff", .8))
    for x, y, w, h in skyline(r, 620, 150, 400, 70, 150):
        d.add(rect(x, y, w, h, "#cfe0ee"))
    for x, y, w, h in skyline(r, 620, 60, 240, 80, 160):
        d.add(rect(x, y, w, h, "#b4cde2"))
    d.add("".join(rect(x - 7, 120, 14, 500, "#ffffff") for x in range(0, W + 1, 384)), rect(0, 108, W, 16, "#ffffff"), rect(0, 612, W, 22, "#ffffff"), rect(0, 634, W, 130, "#dfe4ea"),
          "".join(rect(200 + i * 400, 30, 240, 16, "#ffffff", rx=6) for i in range(4)))
    band(d, 764, 316, [(0, "#c9d0d9"), (1, "#aeb7c3")])
    d.add("".join('<ellipse cx="80" cy="640" rx="30" ry="110" fill="%s" transform="rotate(%d 80 760)"/>' % (c, a) for a, c in ((-36, "#4f9a5c"), (-12, "#5fae6c"), (14, "#4f9a5c"), (38, "#5fae6c"))), rect(34, 750, 92, 120, "#f4f6f8", rx=10))
    for x in (190, 760, 1330):
        y = 820   # 画面の上の端
        d.add(rect(x + 150, y, 180, 116, "#3f4b5c", rx=8), rect(x + 160, y + 10, 160, 96, "#8fb0d8"), rect(x + 172, y + 24, 90, 8, "#ffffff", .7, 3), rect(x + 172, y + 42, 120, 8, "#ffffff", .45, 3), rect(x + 172, y + 60, 70, 8, "#ffffff", .45, 3),
              rect(x + 228, y + 116, 24, 30, "#5b6672"), rect(x + 190, y + 142, 100, 8, "#5b6672", rx=4), rect(x, y + 150, 480, 22, "#ead5b2", rx=4), rect(x + 16, y + 172, 14, 100, "#aab3be"), rect(x + 450, y + 172, 14, 100, "#aab3be"),
              rect(x + 320, y + 172, 130, 100, "#f4f6f8", rx=4, extra=' stroke="#c3cad4" stroke-width="3"'), rect(x + 60, y + 126, 50, 24, "#f4f6f8", rx=4), rect(x + 110, y + 220, 150, 60, "#4d5b72", rx=26))
    wash(d, "#f3f6f9", .35)


@scenery("cafe", "喫茶店", "あたたかい灯りのカウンターと、棚のカップ。休憩・雑談・コーヒーの話に", "dark")
def _(d, r):
    d.__init__(("#2a1b13", "#3a261a"))
    d.add('<rect width="%d" height="780" fill="%s" opacity=".5"/>' % (W, d.pattern(120, 780, line(0, 0, 0, 780, "#1c110a", 3))))
    for x0 in (90, 1330):
        for y0 in (330, 520):
            d.add(rect(x0, y0, 500, 16, "#7a4f2a", rx=3), rect(x0 + 30, y0 + 16, 10, 30, "#5a3a20"), rect(x0 + 460, y0 + 16, 10, 30, "#5a3a20"))
            x = x0 + 24
            while x < x0 + 440:
                k = r.randint(0, 2)
                if k == 0:
                    d.add(rect(x, y0 - 44, 46, 44, "#efe6d2", rx=8), '<circle cx="%d" cy="%d" r="13" fill="none" stroke="#efe6d2" stroke-width="6"/>' % (x + 50, y0 - 24))
                    x += 84
                elif k == 1:
                    d.add(rect(x, y0 - 86, 48, 86, r.choice(("#8a5a33", "#b08a3c", "#6f8a5a")), rx=8), rect(x + 6, y0 - 100, 36, 16, "#3a2414", rx=4))
                    x += 70
                else:
                    d.add(rect(x, y0 - 34, 54, 34, "#b0633f", rx=6), circ(x + 27, y0 - 58, 30, "#4f8a55"), circ(x + 8, y0 - 46, 18, "#3f7a48"))
                    x += 84
    for x in (420, 960, 1500):
        d.glow(x, 250, 430, "#ffcf87", .3)
        d.add(line(x, 0, x, 150, "#120a06", 5), poly([(x - 66, 216), (x + 66, 216), (x + 30, 148), (x - 30, 148)], "#c98a3c"), ell(x, 216, 66, 10, "#ffe9b8"))
    d.add(rect(0, 850, W, 34, "#9a6638"), rect(0, 850, W, 8, "#b87f49"))
    band(d, 884, 196, [(0, "#4e3220"), (1, "#27170e")])
    d.add("".join(line(x, 890, x, H, "#1c110a", 4, .6) for x in range(60, W, 240)))
    for x in (330, 1530):
        d.add(ell(x + 30, 852, 60, 9, "#e2d6bd"), rect(x, 806, 60, 44, "#f3ead6", rx=10), '<circle cx="%d" cy="826" r="12" fill="none" stroke="#f3ead6" stroke-width="6"/>' % (x + 66),
              "".join(path("M%d 792q-10 -16 0 -30q10 -14 0 -30" % (x + 16 + k * 16), stroke="#ffffff", w=5, o=.3, extra=' stroke-linecap="round"') for k in range(3)))
    d.add("".join(ell(x, 1010, 74, 18, "#8f3a2c") + rect(x - 8, 1024, 16, 70, "#1c110a") for x in (300, 780, 1140, 1620)))
    vig(d, "#000000", .5, .5)


@scenery("shrine", "神社", "朱色の鳥居と石畳の参道、両わきの木立。初詣・伝統・祈りの話に", "light")
def _(d, r):
    d.__init__(("#bfe3f6", "#eaf6fc", "#f7f5ea"))
    d.add(cloud(960, 420, .6, "#ffffff", .8))
    for x in range(-40, W + 60, 90):
        d.add(pine(x, 720, r.uniform(260, 380), "#9cc9ac"))
    for x in list(range(-30, 560, 110)) + list(range(1400, W + 60, 110)):
        d.add(pine(x, 760, r.uniform(420, 560), "#5f9a78"))
    band(d, 700, 380, [(0, "#ddd3b8"), (1, "#c9be9f")])
    d.add(poly([(830, 700), (1090, 700), (1430, H), (490, H)], "#c6c8c4"), "".join(line(960 - (130 + 340 * t), 700 + 380 * t, 960 + (130 + 340 * t), 700 + 380 * t, "#a9aba7", 3) for t in (.08, .2, .36, .56, .8)),
          line(960, 700, 960, H, "#a9aba7", 3))
    red, blk = "#d8452b", "#2b2622"
    d.add(poly([(296, H), (374, H), (362, 250), (316, 250)], red), poly([(1546, H), (1624, H), (1604, 250), (1558, 250)], red), rect(288, 1010, 94, 70, blk), rect(1538, 1010, 94, 70, blk))
    d.add(rect(240, 340, 1440, 46, red), rect(932, 268, 56, 74, red), path("M196 218Q960 262 1724 218L1716 266Q960 300 204 266Z", red), path("M150 150Q960 205 1770 150L1794 208Q960 256 126 208Z", blk))
    for x in (600, 1320):   # 石どうろう
        d.add(rect(x - 16, 900, 32, 110, "#a9aba7"), rect(x - 40, 1000, 80, 22, "#9a9c98"), rect(x - 36, 850, 72, 56, "#b9bbb7"), rect(x - 14, 864, 28, 30, "#ffe9a8"), poly([(x - 56, 852), (x + 56, 852), (x, 800)], "#9a9c98"))
    wash(d, "#f4f8f2", .45)


@scenery("bamboo", "竹林", "まっすぐ伸びる竹と、上から差す光。和風・静けさ・ひと息つく話に", "dark")
def _(d, r):
    d.__init__(("#17382a", "#1f4a35", "#12281e"))
    d.glow(960, 60, 950, "#d8f2b0", .32)
    for _k in range(30):
        x, w = r.uniform(0, W), r.uniform(8, 18)
        d.add(rect(x, 0, w, H, "#2f6a48", .55))
    xs = [x for x in (r.uniform(0, W) for _ in range(60)) if abs(x - 960) > 340][:24]
    for x in sorted(xs, key=lambda v: -abs(v - 960))[::-1]:
        w, c = r.uniform(30, 58), r.choice(("#3f8a55", "#4c9a5f", "#357a4c"))
        d.add(rect(x, 0, w, H, c), rect(x + w * .12, 0, w * .16, H, "#a6dc9a", .28), rect(x + w * .8, 0, w * .2, H, "#0e2a1c", .3))
        y = r.uniform(40, 200)
        while y < H:
            d.add(rect(x - 2, y, w + 4, 7, "#1c4a30"), rect(x - 2, y + 7, w + 4, 3, "#a6dc9a", .4))
            y += r.uniform(170, 240)
    for _k in range(46):
        x, y, a = r.choice((r.uniform(0, 600), r.uniform(1320, W))), r.uniform(0, 330), r.uniform(20, 160)
        d.add('<ellipse cx="%s" cy="%s" rx="54" ry="9" fill="%s" fill-opacity=".8" transform="rotate(%d %s %s)"/>' % (n(x), n(y), r.choice(("#5fae6c", "#3f8a55", "#7cc47c")), a, n(x), n(y)))
    band(d, 780, 300, [(0, "#bfe3c8", 0), (1, "#bfe3c8", .16)])
    vig(d, "#000000", .45, .5)


@scenery("lake", "湖", "山と空を映す静かな湖と、岸の木立。静けさ・ふり返り・自然の話に", "light")
def _(d, r):
    d.__init__(("#9bd0f2", "#dff1fb", "#f4fafd"))
    d.add(cloud(380, 200, .8), cloud(1380, 260, .6, "#ffffff", .85))
    p1, p2 = peaks(r, 600, 300), hills(r, 600, 150, 120, .9)
    d.add(path(jag(p1, 600), "#9dbbd6"), path(under(p2, 600), "#78a5b8"))
    band(d, 600, 480, [(0, "#b4dcf0"), (1, "#74b3d8")])
    d.add(path(jag([(x, 1200 - y) for x, y in p1], 600), "#9dbbd6", o=.4), path(under([(x, 1200 - y) for x, y in p2], 600), "#78a5b8", o=.4))
    d.add("".join(rect(r.uniform(0, W), r.uniform(620, 900), r.uniform(60, 220), 3, "#ffffff", round(r.uniform(.25, .6), 2), 2) for _ in range(60)), rect(0, 598, W, 5, "#eaf6fb", .8))
    d.add(path("M1180 770q60 34 150 0l-14 26h-120z", "#7a5533"), rect(1240, 730, 5, 44, "#7a5533"), path("M1196 800h120l-14 16h-92z", "#7a5533", o=.3))
    d.add(path(under(hills(r, 990, 60, 120, .7)), "#6aa568"))
    for x in list(range(20, 470, 90)) + list(range(1500, W + 40, 90)):
        d.add(pine(x, 1010 + r.uniform(-20, 30), r.uniform(240, 380), "#2f6a4c"))
    wash(d, "#eef7fb", .35)


@scenery("aurora-sky", "オーロラの夜", "星空にゆれる緑と紫の光の幕と、雪の丘。北国・神秘・冬の夜の話に", "dark")
def _(d, r):
    d.__init__(("#050a1c", "#0b1b3a", "#12304a"))
    d.add(stars(r, 200, ymax=820))
    for i, (c, y0, amp) in enumerate((("#7a6bff", 170, 70), ("#3dffb0", 250, 90), ("#3dd6ff", 350, 60))):
        top = wave(y0, amp, 380 + i * 90, i * 1.7, 60)
        dd = "M" + "L".join("%s %s" % (n(x), n(y)) for x, y in top) + "L" + "L".join("%s %s" % (n(x), n(y + 430)) for x, y in reversed(top)) + "Z"
        d.add('<path d="%s" fill="%s"/>' % (dd, d.grad([(0, c, 0), (.22, c, .26), (1, c, 0)])), "".join(line(x, y + 30, x, y + r.uniform(200, 380), c, 5, round(r.uniform(.04, .1), 3)) for x, y in top))
    d.add(path(under(hills(r, 850, 90, 120, .6)), "#1f3a58"), path(under(hills(r, 960, 60, 120, .5)), "#335a7d"))
    for x in list(range(30, 520, 80)) + list(range(1480, W + 40, 80)):
        d.add(pine(x, 930 + r.uniform(-30, 40), r.uniform(150, 290), "#08182a"))
    d.glow(1290, 880, 150, "#ffd879", .4)
    d.add(rect(1230, 850, 120, 70, "#0d2036"), poly([(1214, 854), (1366, 854), (1290, 800)], "#e8f1f8"), rect(1272, 870, 34, 30, "#ffd879"), rect(1330, 812, 14, 34, "#0d2036"))


@scenery("island", "南の島", "エメラルドの海と白い砂浜、やしの木。夏休み・旅行・のんびりした話に", "light")
def _(d, r):
    d.__init__(("#6ec6f2", "#c9ecfb", "#f3fbfd"))
    d.glow(1420, 220, 420, "#fffbe0", .9)
    d.add(circ(1420, 220, 70, "#fffdf0"), cloud(420, 260, .8), cloud(1000, 340, .5, "#ffffff", .85))
    d.add(path("M360 602Q470 520 600 560Q680 540 760 602Z", "#7fbf95"))
    band(d, 600, 480, [(0, "#2fb5c6"), (.5, "#6fdcd0"), (1, "#c9f3e2")])
    d.add("".join(path(smooth(wave(y, 6, 90, k, 60)), stroke="#ffffff", w=3, o=.4) for k, y in enumerate((650, 710, 780))), rect(0, 598, W, 5, "#eafaf8", .8))
    beach = [(x, 900 - 70 * math.sin(x / W * math.pi) + 16 * math.sin(x / 170)) for x in range(-80, W + 161, 80)]
    d.add(path(under([(x, y - 16) for x, y in beach]), "#ffffff", o=.85), path(under(beach), "#f6e6b8"), path(under([(x, y + 90) for x, y in beach]), "#efd9a0", o=.6))
    d.add(palm(230, 1000, 560, 130), palm(90, 1040, 420, 60), palm(1730, 990, 520, -120))
    d.add(poly([(1330, 960), (1345, 992), (1380, 994), (1352, 1014), (1362, 1048), (1330, 1028), (1298, 1048), (1308, 1014), (1280, 994), (1315, 992)], "#f28a6a"), ell(700, 1010, 26, 16, "#f6c9b8"), ell(700, 1010, 12, 7, "#e8a48c"))
    wash(d, "#eefafa", .30)


@scenery("airport", "空港", "管制塔とターミナル、とまっている飛行機と、飛び立つ飛行機。旅・出張・世界へ出る話に", "light")
def _(d, r):
    d.__init__(("#7ebff0", "#d2eafa", "#f2f9fe"))
    d.add(cloud(720, 300, .8), cloud(1500, 420, .55, "#ffffff", .85))
    d.add(path(under(hills(r, 690, 60, 120, .6)), "#b7d3c8"))
    d.add(path("M520 700V640Q1060 580 1600 640V700Z", "#e9eef3"), rect(540, 648, 1040, 34, "#9cc7e6"), "".join(rect(x, 648, 6, 34, "#e9eef3") for x in range(600, 1560, 80)))
    d.add(rect(246, 340, 44, 360, "#d6dde5"), poly([(196, 340), (340, 340), (362, 270), (174, 270)], "#5b7fa3"), poly([(186, 270), (350, 270), (336, 250), (200, 250)], "#e9eef3"), rect(190, 338, 156, 12, "#e9eef3"), rect(264, 190, 6, 62, "#8a97a6"), circ(267, 186, 8, "#d8533f"))
    band(d, 700, 380, [(0, "#b3bbc5"), (1, "#959eaa")])
    d.add(path("M0 900Q700 800 1920 860", stroke="#f2c230", w=6), "".join(rect(x, 1000, 110, 10, "#ffffff", .85) for x in range(40, W, 220)))
    plane = (path("M-340 0Q-340 -40 -260 -44L250 -44Q340 -40 372 -6Q340 30 250 30L-260 30Q-340 30 -340 0Z", "#fbfcfd") + poly([(-290, -40), (-350, -150), (-282, -150), (-196, -44)], "#3f73b5") + poly([(-320, -6), (-390, -40), (-340, -40), (-270, -6)], "#dfe5ec")
             + path("M-336 6H366", stroke="#3f73b5", w=8) + poly([(-60, 6), (90, 6), (-10, 110), (-80, 110)], "#cfd7e0") + rect(-30, 44, 110, 44, "#9aa6b4", rx=20)
             + "".join(circ(-200 + k * 38, -18, 7, "#5b7fa3") for k in range(12)) + path("M296 -30L340 -12H286Z", "#5b7fa3"))
    d.add('<g transform="translate(1440 870)">%s%s</g>' % (plane, rect(-10, 30, 10, 60, "#5b6672") + circ(-5, 96, 16, "#2f3a45") + rect(250, 30, 8, 60, "#5b6672") + circ(254, 96, 13, "#2f3a45")))
    d.add(path("M120 560L1010 250", stroke="#ffffff", w=10, o=.6, extra=' stroke-linecap="round"'), '<g transform="translate(1060 232) rotate(-19) scale(.32)">%s</g>' % plane)
    wash(d, "#eef5fa", .35)


@scenery("control-room", "管制室", "壁いっぱいの画面と、操作卓の列。監視・運用・宇宙や交通の指令の話に", "dark")
def _(d, r):
    d.__init__(("#060b16", "#0b1424", "#070c17"))
    d.glow(960, 330, 950, "#2f7bff", .2)
    for j in range(2):
        for i in range(5):
            x, y, k = 70 + i * 360, 90 + j * 240, (i + j * 2) % 4
            d.add(rect(x, y, 330, 210, "#0d1f38", rx=6, extra=' stroke="#1f4573" stroke-width="3"'))
            if k == 0:
                pts = [(x + 20 + t * 29, y + 150 - r.uniform(10, 110)) for t in range(11)]
                d.add(path("M" + "L".join("%s %s" % (n(px), n(py)) for px, py in pts), stroke="#4dd0ff", w=3, o=.6), "".join(line(x + 20, y + 40 + q * 40, x + 310, y + 40 + q * 40, "#2a5aa0", 1, .5) for q in range(4)))
            elif k == 1:
                d.add("".join(rect(x + 26 + t * 30, y + 180 - h, 18, h, "#4de3a8", .5) for t, h in ((t, r.uniform(30, 140)) for t in range(10))))
            elif k == 2:
                d.add("".join(ring(x + 165, y + 105, q, "#4dd0ff", 2, .4) for q in (30, 60, 88)), line(x + 77, y + 105, x + 253, y + 105, "#4dd0ff", 1.5, .4), line(x + 165, y + 17, x + 165, y + 193, "#4dd0ff", 1.5, .4),
                      "".join(circ(x + 165 + r.uniform(-70, 70), y + 105 + r.uniform(-70, 70), 5, "#ffc24d", .8) for _ in range(4)))
            else:
                d.add("".join(rect(x + 24, y + 26 + q * 26, r.uniform(120, 280), 10, "#8fb8ff", .35, 4) + circ(x + 300, y + 31 + q * 26, 5, r.choice(("#4de3a8", "#4de3a8", "#ffc24d")), .8) for q in range(7)))
    band(d, 700, 380, [(0, "#0a1322"), (1, "#04070e")])
    for y, s, xs in ((790, .8, (150, 620, 1090, 1560)), (930, 1.15, (-60, 540, 1140, 1740))):
        for x in xs:
            w = 400 * s
            d.add(rect(x + w * .36, y - 96 * s, w * .28, 110 * s, "#060b14", rx=24 * s), rect(x, y, w, 30 * s, "#1a2c4a", rx=6), rect(x, y, w, 5 * s, "#3a6aa8"), rect(x + 10 * s, y + 30 * s, w - 20 * s, 240 * s, "#0c1626"),
                  rect(x + w * .08, y - 70 * s, w * .24, 62 * s, "#12315a", rx=4, extra=' stroke="#2a5aa0" stroke-width="2"'), rect(x + w * .68, y - 70 * s, w * .24, 62 * s, "#12315a", rx=4, extra=' stroke="#2a5aa0" stroke-width="2"'),
                  rect(x + w * .1, y - 60 * s, w * .14, 5 * s, "#4dd0ff", .7), rect(x + w * .7, y - 60 * s, w * .1, 5 * s, "#4de3a8", .7))
    vig(d, "#000000", .5, .5)


@scenery("moon", "月面", "まっ暗な空に浮かぶ青い星と、クレーターのある灰色の大地。宇宙探査・挑戦・遠くから見る話に", "dark")
def _(d, r):
    d.__init__("#03040a")
    d.add(stars(r, 260, ymax=780, big=2))
    d.glow(1480, 260, 330, "#4f9be8", .3)
    d.defs.append('<clipPath id="blue"><circle cx="1480" cy="260" r="130"/></clipPath>')
    d.add('<circle cx="1480" cy="260" r="130" fill="%s"/>' % d.grad([(0, "#5fb0f0"), (1, "#16458f")], 0, 0, 1, 1),
          '<g clip-path="url(#blue)">%s%s%s</g>' % (path(blob(1440, 230, 60, r, 9, .4), "#58a877") + path(blob(1540, 320, 44, r, 8, .4), "#58a877"),
                                                   "".join(ell(1480 + r.uniform(-110, 110), 260 + r.uniform(-110, 110), r.uniform(30, 70), r.uniform(6, 12), "#ffffff", .7) for _ in range(7)), circ(1560, 320, 150, "#02030a", .55)))
    d.add(path(under(hills(r, 800, 70, 120, .6)), "#3f434c"), path(under(hills(r, 880, 50, 120, .5)), "#565a63"), path(under(hills(r, 990, 36, 120, .5)), "#6c7079"))
    for _k in range(16):
        x, y = r.uniform(0, W), r.uniform(850, 1070)
        s = (y - 780) / 300 * r.uniform(.6, 1.3)
        d.add(ell(x, y, 80 * s, 20 * s, "#2f333b", .8), path("M%s %sA%s %s 0 0 0 %s %s" % (n(x - 80 * s), n(y), n(80 * s), n(20 * s), n(x + 80 * s), n(y)), stroke="#9a9ea6", w=3 * s, o=.6))
    d.add("".join(path(blob(r.uniform(0, W), r.uniform(900, 1070), r.uniform(8, 22), r, 7, .3), "#2f333b") for _ in range(14)))
    vig(d, "#000000", .4, .55)


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
