#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""figkit — md-to-doc の説明図を、短い JSON の仕様から作る部品集。

Claude が SVG を手で描く代わりに、図の種類と中身（ノード・矢印・値など）だけを JSON に書く。
figkit がテーマ配色（CSS 変数）と動きの注釈（data-step / data-effect / data-travel …）入りの
<figure> を作り、md-to-doc の出力 HTML に差し込む。同じ仕様からは同じ図になる（決定論的）。

使い方:
  python3 figkit.py --list                       # 図の種類と仕様の書き方
  python3 figkit.py spec.json                    # <figure> を標準出力へ
  python3 figkit.py spec.json --insert out.html  # 仕様の slot / replace / placeholder に差し込む

仕様（JSON）: 図 1 つのオブジェクト、図の配列、または {"figures": [...]}。
  共通: type（必須）/ id / caption / aria / motion（true=段の順に動く, "auto", "none", 省略=文書の既定）/
        tempo（slow|normal|fast）/ trigger（view|click|loop|scroll）/
        style（動きの性格 gentle|dynamic|playful|cinematic|tech|retro|elegant|news）/ intro（図全体の入り方 punch|zoom-out|drop|tilt|glitch|iris|crt|wipe|unfold）/
        dir（現れる順 x|y|radial|in|diagonal|spiral|random）/ 項目の detail（触れると説明のカード）/
        差し込み先: slot（auto-fig-slot の data-section）/ replace（置き換える figure の id）/
                    placeholder（本文の <!--FIGKIT:名前--> を置き換える）
"""
import sys, json, html, math, re, argparse

ACCENTS = 4  # 全テーマが --a0..--a3 以上を持つ
FONT = 15
SUB = 12


# ──────────────────────────────────────────────────────────────────────────
# 文字幅の見積もり（CJK は 1em、それ以外は 0.58em）
# ──────────────────────────────────────────────────────────────────────────
def tw(s, size=FONT):
    w = 0.0
    for ch in str(s):
        o = ord(ch)
        w += 1.0 if (o >= 0x2E80 or 0xFF00 <= o <= 0xFFEF) else (0.32 if ch in " .,:;|!il'" else 0.6)
    return w * size


def esc(s):
    return html.escape(str(s), quote=True)


def acc(i):
    return "var(--a%d)" % (i % ACCENTS)


def ann(o, **extra):
    """仕様の項目から共通の注釈（注記・変更点・関連の強調・ズーム）を属性にする。"""
    a = ""
    if o.get("note"):
        a += ' data-note="%s"' % esc(o["note"])
        if o.get("note_pos"):
            a += ' data-note-pos="%s"' % esc(o["note_pos"])
    if o.get("changed"):
        a += " data-changed"
    if o.get("detail"):     # 触れる・押すと説明のカードが出る（md-to-doc の LAYOUT_JS）
        a += ' data-detail="%s"' % esc(o["detail"])
    for k, v in extra.items():
        if v is None or v is False:
            continue
        a += ' data-%s' % k.replace("_", "-") if v is True else ' data-%s="%s"' % (k.replace("_", "-"), esc(v))
    return a


class Canvas:
    """SVG の断片を集めて、最後に viewBox を決める。"""

    def __init__(self, fid):
        self.fid = fid
        self.parts = []
        self.fig = {}      # figure に付ける属性（data-paths / data-hover など）

    def add(self, s):
        self.parts.append(s)

    def marker(self):
        return "mk-%s" % self.fid

    def defs(self):
        m = self.marker()
        return ('<defs><marker id="%s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                'markerHeight="7" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" '
                'fill="var(--accent-2)"/></marker></defs>' % m)


def text(x, y, s, size=FONT, weight=None, fill="var(--ink)", anchor="middle", extra=""):
    w = ' font-weight="%s"' % weight if weight else ""
    return ('<text x="%.1f" y="%.1f" font-size="%s"%s fill="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, size, w, fill, anchor, extra, esc(s)))


def box(x, y, w, h, label, sub=None, kind="normal", ci=None, attrs=""):
    """ノード 1 つ（<g> に図形と文字をまとめる）。"""
    stroke = acc(ci) if ci is not None else "var(--accent)"
    cx, cy = x + w / 2, y + h / 2
    if kind == "decision":
        shape = ('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="var(--accent-soft)" '
                 'stroke="%s" stroke-width="1.6"/>' % (cx, y, x + w, cy, cx, y + h, x, cy, stroke))
    else:
        rx = h / 2 if kind in ("start", "end") else 10
        fill = "var(--accent)" if kind == "start" else "var(--accent-soft)"
        shape = ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" stroke="%s" '
                 'stroke-width="1.6"/>' % (x, y, w, h, rx, fill, stroke))
    ink = "var(--on-accent)" if kind == "start" else "var(--ink)"
    if sub:
        t = text(cx, cy - 2, label, weight="700", fill=ink) + text(cx, cy + 16, sub, SUB, fill="var(--muted)" if kind != "start" else ink)
    else:
        t = text(cx, cy + 5, label, weight="700", fill=ink)
    return '<g%s>%s%s</g>' % (attrs, shape, t)


def node_size(label, sub=None, kind="normal", minw=110):
    w = max(minw, tw(label, FONT) + 36, tw(sub or "", SUB) + 30)
    h = 62 if sub else 48
    if kind == "decision":
        w, h = w * 1.35, h * 1.45
    return min(w, 280), h


def edge_label(x, y, s):
    w = tw(s, SUB) + 14
    return ('<g><rect x="%.1f" y="%.1f" width="%.1f" height="18" rx="5" fill="var(--card)" '
            'stroke="var(--line)"/>%s</g>' % (x - w / 2, y - 12, w, text(x, y + 1, s, SUB, fill="var(--muted)")))


def attr_travel(e):
    t = e.get("travel")
    if t is True:
        return ' data-travel=""'
    if t:
        return ' data-travel="%s"' % esc(t)
    return ""


# ──────────────────────────────────────────────────────────────────────────
# 図の種類
# ──────────────────────────────────────────────────────────────────────────
def fig_flow(spec, cv):
    nodes = spec["nodes"]
    edges = spec.get("edges", [])
    horiz = spec.get("dir", "LR").upper() != "TB"
    ids = [n["id"] for n in nodes]
    byid = {n["id"]: n for n in nodes}
    # 段（rank）: 閉路は DFS で見つけた戻りの辺を除いて最長路
    adj = {i: [] for i in ids}
    for e in edges:
        if e["from"] in adj and e["to"] in adj:
            adj[e["from"]].append(e["to"])
    back, state = set(), {}

    def dfs(u):
        state[u] = 1
        for v in adj[u]:
            if state.get(v) == 1:
                back.add((u, v))
            elif not state.get(v):
                dfs(v)
        state[u] = 2
    for i in ids:
        if not state.get(i):
            dfs(i)
    rank = {i: 0 for i in ids}
    for _ in range(len(ids)):
        for e in edges:
            if (e["from"], e["to"]) in back or e["from"] not in rank or e["to"] not in rank:
                continue
            rank[e["to"]] = max(rank[e["to"]], rank[e["from"]] + 1)
    layers = {}
    for i in ids:
        layers.setdefault(rank[i], []).append(i)
    size = {i: node_size(byid[i]["label"], byid[i].get("sub"), byid[i].get("kind", "normal")) for i in ids}
    GAP_R, GAP_I, PAD = 86, 30, 24
    pos = {}
    nr = max(layers) + 1
    if horiz:
        colw = [max(size[i][0] for i in layers[r]) for r in range(nr)]
        colh = [sum(size[i][1] for i in layers[r]) + GAP_I * (len(layers[r]) - 1) for r in range(nr)]
        H = max(colh) + PAD * 2
        x = PAD
        for r in range(nr):
            y = (H - colh[r]) / 2
            for i in layers[r]:
                w, h = size[i]
                pos[i] = (x + (colw[r] - w) / 2, y, w, h)
                y += h + GAP_I
            x += colw[r] + GAP_R
        W = x - GAP_R + PAD
    else:
        rowh = [max(size[i][1] for i in layers[r]) for r in range(nr)]
        roww = [sum(size[i][0] for i in layers[r]) + GAP_I * (len(layers[r]) - 1) for r in range(nr)]
        W = max(roww) + PAD * 2
        y = PAD
        for r in range(nr):
            x = (W - roww[r]) / 2
            for i in layers[r]:
                w, h = size[i]
                pos[i] = (x, y + (rowh[r] - h) / 2, w, h)
                x += w + GAP_I
            y += rowh[r] + GAP_R * 0.75
        H = y - GAP_R * 0.75 + PAD
    focus = {f: k for k, f in enumerate(spec.get("focus", []))}
    zoom = {f: k for k, f in enumerate(spec.get("zoom", []))}
    # 経路（シナリオ）: 辺の paths から、通るノードを求める
    scen = list(spec.get("scenarios", []))
    onpath = {i: [] for i in ids}
    for e in edges:
        for pth in e.get("paths", []):
            if pth not in scen:
                scen.append(pth)
            for end in (e["from"], e["to"]):
                if end in onpath and pth not in onpath[end]:
                    onpath[end].append(pth)
    if scen:
        cv.fig["paths"] = "|".join(scen)
    if spec.get("hover", len(nodes) >= 4):
        cv.fig["hover"] = True
    mk = cv.marker()
    extra_h = 0
    for e in edges:
        if e["from"] not in pos or e["to"] not in pos:
            continue
        x1, y1, w1, h1 = pos[e["from"]]
        x2, y2, w2, h2 = pos[e["to"]]
        isback = (e["from"], e["to"]) in back or rank[e["to"]] <= rank[e["from"]]
        if horiz:
            if not isback:
                sx, sy, tx, ty = x1 + w1, y1 + h1 / 2, x2 - 2, y2 + h2 / 2
                mx = (sx + tx) / 2
                d = "M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (sx, sy, mx, sy, mx, ty, tx, ty)
                lx, ly = mx, (sy + ty) / 2 - 10
            else:
                sx, sy, tx, ty = x1 + w1 / 2, y1 + h1, x2 + w2 / 2, y2 + h2 + 2
                by = max(sy, ty) + 46
                extra_h = max(extra_h, by + 14 - H)
                d = "M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (sx, sy, sx, by, tx, by, tx, ty)
                lx, ly = (sx + tx) / 2, by - 6
        else:
            if not isback:
                sx, sy, tx, ty = x1 + w1 / 2, y1 + h1, x2 + w2 / 2, y2 - 2
                my = (sy + ty) / 2
                d = "M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (sx, sy, sx, my, tx, my, tx, ty)
                lx, ly = (sx + tx) / 2 + 4, my + 4
            else:
                sx, sy, tx, ty = x1 + w1, y1 + h1 / 2, x2 + w2 + 2, y2 + h2 / 2
                bx = max(sx, tx) + 50
                W = max(W, bx + 20)
                d = "M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (sx, sy, bx, sy, bx, ty, tx, ty)
                lx, ly = bx - 10, (sy + ty) / 2
        dash = ' stroke-dasharray="6 5"' if e.get("dashed") else ""
        flow = " data-flow" if e.get("flow") else ""
        step = 2 * rank[e["from"]] + 1
        lab = edge_label(lx, ly, e["label"]) if e.get("label") else ""
        pa = ann(e, path="|".join(e.get("paths", [])) or None, link="%s %s" % (e["from"], e["to"]))
        cv.add('<g data-step="%d" data-effect="draw"%s%s><path d="%s" fill="none" stroke="var(--accent-2)" stroke-width="2"%s%s '
               'marker-end="url(#%s)"/>%s</g>' % (step, attr_travel(e), pa, d, dash, flow, mk, lab))
    for k, i in enumerate(ids):
        x, y, w, h = pos[i]
        n = byid[i]
        a = ' data-step="%d" data-effect="pop"' % (2 * rank[i])
        if i in focus:
            a += ' data-focus="%d"' % focus[i]
        if n.get("pulse"):
            a += " data-pulse"
        a += ann(n, node=i, path="|".join(onpath[i]) or None,
                 zoom_step=zoom.get(i) if i in zoom else None)
        cv.add(box(x, y, w, h, n["label"], n.get("sub"), n.get("kind", "normal"), attrs=a))
    return W, H + extra_h


def fig_steps(spec, cv):
    items = spec["items"]
    n = len(items)
    horiz = spec.get("dir", "LR" if n <= 5 else "TB").upper() != "TB"
    R = 17
    walk = spec.get("walkthrough")
    if horiz:
        colw = max(150, max(max(tw(it["label"]), tw(it.get("sub", ""), SUB)) for it in items) + 24)
        W, H = colw * n + 20, 150
        for i, it in enumerate(items):
            cx = 10 + colw * i + colw / 2
            if i < n - 1:
                cv.add('<line data-step="%d" x1="%.1f" y1="44" x2="%.1f" y2="44" stroke="var(--line)" '
                       'stroke-width="3"/>' % (2 * i + 1, cx + R + 4, cx + colw - R - 4))
            f = (' data-focus="%d"' % i if walk else "") + ann(it)
            cv.add('<g data-step="%d"%s><circle cx="%.1f" cy="44" r="%d" fill="%s" data-effect="pop"/>%s%s%s</g>'
                   % (2 * i, f, cx, R, acc(i), text(cx, 50, str(i + 1), 15, "700", "var(--on-accent)"),
                      text(cx, 92, it["label"], weight="700"),
                      text(cx, 114, it.get("sub", ""), SUB, fill="var(--muted)") if it.get("sub") else ""))
    else:
        roww = max(max(tw(it["label"]), tw(it.get("sub", ""), SUB)) for it in items) + 90
        W, H = max(360, roww + 20), 70 * n + 20
        for i, it in enumerate(items):
            cy = 36 + 70 * i
            if i < n - 1:
                cv.add('<line data-step="%d" x1="40" y1="%.1f" x2="40" y2="%.1f" stroke="var(--line)" '
                       'stroke-width="3"/>' % (2 * i + 1, cy + R + 4, cy + 70 - R - 4))
            f = (' data-focus="%d"' % i if walk else "") + ann(it)
            sub = text(72, cy + 20, it.get("sub", ""), SUB, fill="var(--muted)", anchor="start") if it.get("sub") else ""
            cv.add('<g data-step="%d"%s><circle cx="40" cy="%.1f" r="%d" fill="%s"/>%s%s%s</g>'
                   % (2 * i, f, cy, R, acc(i), text(40, cy + 6, str(i + 1), 15, "700", "var(--on-accent)"),
                      text(72, cy + (0 if sub else 5), it["label"], weight="700", anchor="start"), sub))
    return W, H


def fig_cycle(spec, cv):
    items = spec["items"]
    n = len(items)
    sizes = [node_size(it["label"], it.get("sub"), minw=96) for it in items]
    R = max(120, max(s[0] for s in sizes) * 0.95, n * 34)
    cx = cy = R + max(s[0] for s in sizes) / 2 + 20
    W = H = cx * 2
    mk = cv.marker()
    cv.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="var(--line)" stroke-width="1.5" '
           'stroke-dasharray="3 7" data-spin="%s" data-effect="fade"/>' % (cx, cy, R * 0.55, "cw"))
    if spec.get("center"):
        cv.add('<g data-effect="pop">%s</g>' % text(cx, cy + 6, spec["center"], 17, "700", "var(--accent)"))
    pts = [(cx + R * math.sin(2 * math.pi * i / n), cy - R * math.cos(2 * math.pi * i / n)) for i in range(n)]
    for i in range(n):
        a0 = 2 * math.pi * i / n + 0.22 + sizes[i][0] / (2 * R) * 0.6
        a1 = 2 * math.pi * (i + 1) / n - 0.22 - sizes[(i + 1) % n][0] / (2 * R) * 0.6
        if a1 <= a0:
            a0, a1 = 2 * math.pi * i / n + 0.3, 2 * math.pi * (i + 1) / n - 0.3
        p0 = (cx + R * math.sin(a0), cy - R * math.cos(a0))
        p1 = (cx + R * math.sin(a1), cy - R * math.cos(a1))
        cv.add('<path data-step="%d" d="M%.1f,%.1f A%.1f,%.1f 0 0 1 %.1f,%.1f" fill="none" stroke="var(--accent-2)" '
               'stroke-width="2" marker-end="url(#%s)"/>' % (2 * i + 1, p0[0], p0[1], R, R, p1[0], p1[1], mk))
    for i, it in enumerate(items):
        w, h = sizes[i]
        x, y = pts[i]
        cv.add(box(x - w / 2, y - h / 2, w, h, it["label"], it.get("sub"), ci=i,
                   attrs=' data-step="%d" data-effect="pop"' % (2 * i) + ann(it)))
    return W, H


def fig_bars(spec, cv):
    items = spec["items"]
    unit = spec.get("unit", "")
    vmax = spec.get("max") or max(float(it["value"]) for it in items) or 1
    hl = spec.get("highlight")
    vert = spec.get("orient", "h") == "v"

    def disp(it):
        return it.get("display") or ("{:,}".format(it["value"]) if isinstance(it["value"], int) else str(it["value"])) + unit
    if not vert:
        lw = max(tw(it["label"]) for it in items) + 20
        BW, BH, G = 380, 26, 16
        W, H = lw + BW + 110, len(items) * (BH + G) + 16
        for i, it in enumerate(items):
            y = 12 + i * (BH + G)
            w = max(2, BW * float(it["value"]) / vmax)
            p = " data-pulse" if hl == i else ""
            cv.add('<g data-step="%d"%s>%s<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="5" fill="%s" '
                   'data-effect="grow" data-grow="right"%s/>%s</g>'
                   % (i, ann(it), text(lw - 12, y + BH / 2 + 5, it["label"], anchor="end"), lw, y, w, BH, acc(i), p,
                      text(lw + w + 10, y + BH / 2 + 5, disp(it), 14, "700", anchor="start", extra=' data-count="0" data-effect="fade"')))
    else:
        colw = max(64, max(tw(it["label"], 13) for it in items) + 16)
        BH, BW = 220, min(46, colw - 18)
        W, H = colw * len(items) + 20, BH + 70
        for i, it in enumerate(items):
            cx = 10 + colw * i + colw / 2
            h = max(2, BH * float(it["value"]) / vmax)
            p = " data-pulse" if hl == i else ""
            cv.add('<g data-step="%d"%s><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="5" fill="%s" '
                   'data-effect="grow" data-grow="up"%s/>%s%s</g>'
                   % (i, ann(it), cx - BW / 2, 30 + BH - h, BW, h, acc(i), p,
                      text(cx, 30 + BH - h - 8, disp(it), 13, "700", extra=' data-count="0" data-effect="fade"'),
                      text(cx, 30 + BH + 22, it["label"], 13)))
        cv.add('<line x1="4" y1="%d" x2="%.1f" y2="%d" stroke="var(--line)" stroke-width="1.5"/>' % (30 + BH, W - 4, 30 + BH))
    return W, H


def fig_metrics(spec, cv):
    items = spec["items"]
    TW = max(170, max(max(tw(str(it["value"]) + it.get("unit", ""), 34), tw(it.get("label", ""), 13)) for it in items) + 40)
    W, H = TW * len(items) + 16 * (len(items) - 1), 128
    for i, it in enumerate(items):
        x = i * (TW + 16)
        cv.add('<g data-step="%d" data-effect="pop"><rect x="%.1f" y="4" width="%.1f" height="118" rx="14" '
               'fill="var(--card)" stroke="var(--line)"/><rect x="%.1f" y="4" width="%.1f" height="5" rx="2" fill="%s"/>'
               '%s%s%s</g>'
               % (i, x, TW, x, TW, acc(i),
                  text(x + TW / 2, 68, "%s%s" % (it["value"], it.get("unit", "")), 34, "800", acc(i),
                       extra=' data-count="%s"' % esc(it.get("from", 0))),
                  text(x + TW / 2, 94, it.get("label", ""), 13, fill="var(--muted)"),
                  text(x + TW / 2, 112, it.get("delta", ""), 12, "700", "var(--accent)") if it.get("delta") else ""))
    return W, H


def fig_compare(spec, cv):
    cols = spec["columns"]
    n = len(cols)
    CW = max(220, max(max(tw(c["title"], 17), max([tw(p, 14) for p in c.get("points", [])] or [0]) + 30) for c in cols) + 30)
    rows = max(len(c.get("points", [])) for c in cols)
    GAP = 56 if spec.get("vs") else 22
    W, H = CW * n + GAP * (n - 1), 70 + rows * 30 + 20
    for i, c in enumerate(cols):
        x = i * (CW + GAP)
        pts = "".join('<g>%s%s</g>' % ('<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>' % (x + 22, 84 + k * 30, acc(i)),
                                         text(x + 34, 89 + k * 30, p, 14, anchor="start"))
                      for k, p in enumerate(c.get("points", [])))
        cv.add('<g data-step="%d"><rect x="%.1f" y="2" width="%.1f" height="%.1f" rx="12" fill="var(--card)" '
               'stroke="%s" stroke-width="1.6"/><rect x="%.1f" y="2" width="%.1f" height="46" rx="12" fill="%s" opacity=".16"/>'
               '%s</g><g data-step="%d" data-stagger="110">%s</g>'
               % (2 * i, x, CW, H - 4, acc(i), x, CW, acc(i), text(x + CW / 2, 32, c["title"], 17, "700", acc(i)),
                  2 * i + 1, pts))
        if spec.get("vs") and i < n - 1:
            cv.add('<g data-step="%d" data-effect="pop">%s</g>' % (2 * i + 1, text(x + CW + GAP / 2, H / 2 + 6, spec["vs"], 16, "800", "var(--muted)")))
    return W, H


def fig_hub(spec, cv):
    c = spec["center"]
    items = spec["items"]
    n = len(items)
    sizes = [node_size(it["label"], it.get("sub"), minw=96) for it in items]
    cw, ch = node_size(c["label"], c.get("sub"), minw=130)
    R = max(150, n * 30, max(s[0] for s in sizes) * 0.9 + cw * 0.5)
    ox = R + max(s[0] for s in sizes) / 2 + 16
    oy = R + max(s[1] for s in sizes) / 2 + 16
    W, H = ox * 2, oy * 2
    mk = cv.marker()
    inward = spec.get("inward")
    zoom = spec.get("zoom", [])
    if spec.get("hover", n >= 4):
        cv.fig["hover"] = True
    for i, it in enumerate(items):
        ang = 2 * math.pi * i / n - math.pi / 2
        x, y = ox + R * math.cos(ang), oy + R * math.sin(ang)
        # 中心の箱の縁と、周りの箱の縁の間を結ぶ
        sx, sy = ox + (cw / 2 + 6) * math.cos(ang), oy + (ch / 2 + 6) * math.sin(ang)
        tx, ty = x - (sizes[i][0] / 2 + 6) * math.cos(ang), y - (sizes[i][1] / 2 + 6) * math.sin(ang)
        if inward:
            sx, sy, tx, ty = tx, ty, sx, sy
        e = it if isinstance(it, dict) else {}
        cv.add('<line data-step="1"%s data-link="c n%d" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--accent-2)" stroke-width="2" '
               'marker-end="url(#%s)"%s/>' % (attr_travel(e), i, sx, sy, tx, ty, mk, " data-flow" if e.get("flow") else ""))
        zs = zoom.index(it["label"]) if it["label"] in zoom else None
        cv.add(box(x - sizes[i][0] / 2, y - sizes[i][1] / 2, sizes[i][0], sizes[i][1], it["label"], it.get("sub"), ci=i,
                   attrs=' data-step="2" data-effect="pop"' + ann(it, node="n%d" % i, zoom_step=zs)))
    cv.add(box(ox - cw / 2, oy - ch / 2, cw, ch, c["label"], c.get("sub"), kind="start",
               attrs=' data-step="0" data-effect="pop"%s' % (" data-pulse" if c.get("pulse") else "") + ann(c, node="c")))
    return W, H


def fig_layers(spec, cv):
    items = spec["items"]
    n = len(items)
    LW = max(360, max(tw(it["label"]) + tw(it.get("sub", ""), SUB) + 80 for it in items))
    LH, G = 50, 10
    W, H = LW + 20, n * (LH + G) + 10
    for i, it in enumerate(items):
        y = 6 + i * (LH + G)
        sub = text(LW - 8, y + LH / 2 + 5, it.get("sub", ""), SUB, fill="var(--muted)", anchor="end") if it.get("sub") else ""
        cv.add('<g data-step="%d" data-effect="rise"%s><rect x="10" y="%.1f" width="%.1f" height="%d" rx="10" fill="var(--accent-soft)" '
               'stroke="%s" stroke-width="1.6"/><rect x="10" y="%.1f" width="8" height="%d" rx="4" fill="%s"/>%s%s</g>'
               % (n - 1 - i, ann(it), y, LW, LH, acc(i), y, LH, acc(i),
                  text(34, y + LH / 2 + 5, it["label"], weight="700", anchor="start"), sub))
    return W, H


def fig_sequence(spec, cv):
    actors = spec["actors"]
    msgs = spec["messages"]
    labels = [a if isinstance(a, str) else a["label"] for a in actors]
    keys = [a if isinstance(a, str) else a.get("id", a["label"]) for a in actors]
    colw = max(150, max(tw(l) for l in labels) + 50, max([tw(m.get("label", ""), 13) + 30 for m in msgs] or [0]))
    W = colw * len(actors)
    top, row = 58, 50
    H = top + 30 + row * len(msgs) + 24
    xs = {k: colw * i + colw / 2 for i, k in enumerate(keys)}
    mk = cv.marker()
    for i, (k, l) in enumerate(zip(keys, labels)):
        w = tw(l) + 36
        cv.add('<g data-step="0"><line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="var(--line)" stroke-width="1.5" '
               'stroke-dasharray="4 5" data-effect="fade"/>%s</g>'
               % (xs[k], top, xs[k], H - 8, box(xs[k] - w / 2, 8, w, 44, l, ci=i, attrs=' data-effect="pop"')))
    for j, m in enumerate(msgs):
        y = top + 36 + row * j
        x1, x2 = xs[m["from"]], xs[m["to"]]
        if x1 == x2:
            d = "M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (x1, y - 8, x1 + 60, y - 8, x1 + 60, y + 14, x1 + 4, y + 14)
            lx = x1 + 70
            anchor = "start"
        else:
            off = 4 if x2 > x1 else -4
            d = "M%.1f,%.1f L%.1f,%.1f" % (x1 + off, y, x2 - off, y)
            lx = (x1 + x2) / 2
            anchor = "middle"
        dash = ' stroke-dasharray="6 5"' if m.get("reply") else ""
        tr = attr_travel(m) if "travel" in m else ' data-travel=""'
        cv.add('<g data-step="%d" data-effect="draw"%s%s><path d="%s" fill="none" stroke="var(--accent-2)" stroke-width="2"%s marker-end="url(#%s)"/>%s</g>'
               % (j + 1, tr, ann(m), d, dash, mk, text(lx, y - 8, m.get("label", ""), 13, fill="var(--ink)", anchor=anchor)))
    return W, H


def _nice(v):
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * e:
            return m * e
    return 10 * e


def _fmtnum(v):
    return "{:,}".format(int(v)) if float(v).is_integer() else ("%g" % v)


def fig_line(spec, cv):
    labels = spec["labels"]
    series = spec["series"]
    unit = spec.get("unit", "")
    vals = [v for s_ in series for v in s_["values"]]
    lo = spec.get("min", 0)
    hi = _nice(max(vals) - lo) + lo
    L, R, Tp, B = 56, 70, 18, 40
    W, H = max(560, len(labels) * 64 + L + R), 300
    pw, ph = W - L - R, H - Tp - B
    X = lambda i: L + (pw * i / max(1, len(labels) - 1))
    Y = lambda v: Tp + ph * (1 - (v - lo) / (hi - lo or 1))
    grid = "".join('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="var(--line)" stroke-width="1"/>%s'
                   % (L, Y(lo + (hi - lo) * k / 4), W - R, Y(lo + (hi - lo) * k / 4),
                      text(L - 8, Y(lo + (hi - lo) * k / 4) + 4, _fmtnum(lo + (hi - lo) * k / 4), 11, fill="var(--muted)", anchor="end"))
                   for k in range(5))
    xl = "".join(text(X(i), H - 14, l, 12, fill="var(--muted)") for i, l in enumerate(labels))
    cv.add('<g data-step="0" data-effect="fade">%s%s</g>' % (grid, xl))
    for si, s_ in enumerate(series):
        pts = [(X(i), Y(v)) for i, v in enumerate(s_["values"])]
        d = "M" + " L".join("%.1f,%.1f" % p for p in pts)
        col = acc(si)
        if spec.get("area") and len(series) == 1:
            cv.add('<path data-step="1" data-effect="wipe" d="%s L%.1f,%.1f L%.1f,%.1f Z" fill="%s" opacity=".14"/>'
                   % (d, pts[-1][0], Y(lo), pts[0][0], Y(lo), col))
        cv.add('<path data-step="%d"%s d="%s" fill="none" stroke="%s" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
               % (1 + si, ann(s_), d, col))
        dots = "".join('<circle cx="%.1f" cy="%.1f" r="4.5" fill="var(--card)" stroke="%s" stroke-width="2.5"/>' % (x, y, col) for x, y in pts)
        cv.add('<g data-step="%d" data-stagger="70" data-effect="pop">%s</g>' % (2 + si, dots))
        last = s_["values"][-1]
        cv.add('<g data-step="%d">%s</g>' % (2 + si, text(pts[-1][0] + 10, pts[-1][1] + 5, _fmtnum(last) + unit, 13, "700", col, "start",
                                                  ' data-count="%s"' % esc(s_["values"][0]))))
    if len(series) > 1:
        lg = "".join('<g><rect x="%d" y="%d" width="12" height="4" rx="2" fill="%s"/>%s</g>'
                     % (L + k * 110, 2, acc(k), text(L + k * 110 + 18, 8, s_["name"], 12, fill="var(--muted)", anchor="start"))
                     for k, s_ in enumerate(series))
        cv.add('<g data-step="0" data-effect="fade">%s</g>' % lg)
    return W, H


def fig_donut(spec, cv):
    items = spec["items"]
    total = float(sum(float(it["value"]) for it in items)) or 1
    R, SW, cx, cy = 92, 32, 130, 125
    a = -math.pi / 2
    for i, it in enumerate(items):
        frac = float(it["value"]) / total
        a1 = a + 2 * math.pi * frac
        g0, g1 = a + 0.015, a1 - 0.015
        large = 1 if (g1 - g0) > math.pi else 0
        p0 = (cx + R * math.cos(g0), cy + R * math.sin(g0))
        p1 = (cx + R * math.cos(g1), cy + R * math.sin(g1))
        cv.add('<path data-step="%d" data-effect="draw"%s d="M%.2f,%.2f A%d,%d 0 %d 1 %.2f,%.2f" fill="none" stroke="%s" stroke-width="%d"/>'
               % (i, ann(it), p0[0], p0[1], R, R, large, p1[0], p1[1], acc(i), SW))
        a = a1
    c = spec.get("center") or {"value": _fmtnum(total) + spec.get("unit", ""), "label": "合計"}
    cv.add('<g data-step="%d">%s%s</g>' % (len(items), text(cx, cy + 6, c["value"], 26, "800", "var(--ink)", extra=' data-count="0"'),
                                          text(cx, cy + 28, c.get("label", ""), 12, fill="var(--muted)")))
    lx, W = 270, 270 + max(tw(it["label"], 14) + 90 for it in items)
    rows = "".join('<g><rect x="%d" y="%d" width="12" height="12" rx="3" fill="%s"/>%s%s</g>'
                   % (lx, 40 + k * 30, acc(k), text(lx + 20, 51 + k * 30, it["label"], 14, anchor="start"),
                      text(W - 6, 51 + k * 30, "%d%%" % round(100 * float(it["value"]) / total), 14, "700", acc(k), "end"))
                   for k, it in enumerate(items))
    cv.add('<g data-step="%d" data-stagger="90">%s</g>' % (len(items), rows))
    return W, max(250, 60 + len(items) * 30)


def _day(v):
    if isinstance(v, (int, float)):
        return float(v)
    import datetime
    return float(datetime.date.fromisoformat(str(v)).toordinal())


def fig_gantt(spec, cv):
    tasks = spec["tasks"]
    isdate = any(isinstance(t["start"], str) for t in tasks)
    t0 = min(_day(t["start"]) for t in tasks)
    t1 = max(_day(t["end"]) for t in tasks)
    if spec.get("today") is not None:
        t0, t1 = min(t0, _day(spec["today"])), max(t1, _day(spec["today"]))
    span = (t1 - t0) or 1
    lw = max(tw(t["label"], 14) for t in tasks) + 24
    PW, BH, G, TOP = 460, 22, 12, 50
    W, H = lw + PW + 20, TOP + len(tasks) * (BH + G) + 10
    X = lambda d: lw + PW * (d - t0) / span
    import datetime
    ticks = []
    for k in range(5):
        d = t0 + span * k / 4
        lab = "%d/%d" % (datetime.date.fromordinal(int(round(d))).month, datetime.date.fromordinal(int(round(d))).day) if isdate else _fmtnum(round(d, 1))
        ticks.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--line)"/>%s'
                     % (X(d), TOP - 6, X(d), H - 4, text(X(d), 16, lab, 11, fill="var(--muted)")))
    cv.add('<g data-step="0" data-effect="fade">%s</g>' % "".join(ticks))
    for i, t in enumerate(tasks):
        y = TOP + i * (BH + G)
        s0, s1 = _day(t["start"]), _day(t["end"])
        lab = text(lw - 10, y + BH / 2 + 5, t["label"], 14, anchor="end")
        if s1 <= s0:
            cx = X(s0)
            shape = ('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" data-effect="pop"/>'
                     % (cx, y, cx + 11, y + BH / 2, cx, y + BH, cx - 11, y + BH / 2, acc(i)))
        else:
            shape = ('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="6" fill="%s" data-effect="grow" data-grow="right"/>'
                     % (X(s0), y, max(4, X(s1) - X(s0)), BH, acc(i)))
        cv.add('<g data-step="%d"%s>%s%s</g>' % (1 + i, ann(t), lab, shape))
    if spec.get("today") is not None:
        x = X(_day(spec["today"]))
        cv.add('<g data-step="%d" data-effect="draw"><line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--accent)" stroke-width="2"/>%s</g>'
               % (len(tasks) + 1, x, TOP - 8, x, H - 2, text(x, TOP - 12, spec.get("today_label", "今日"), 11, "700", "var(--accent)")))
    return W, H


def fig_terminal(spec, cv):
    prompt = spec.get("prompt", "$")
    rows = []
    for ln in spec["lines"]:
        if "cmd" in ln:
            rows.append(("cmd", ln["cmd"]))
        else:
            for part in str(ln.get("out", "")).split("\n"):
                rows.append(("out", part))
    CH = 8.6
    maxc = max([len(r[1]) + (len(prompt) + 1 if r[0] == "cmd" else 0) for r in rows] + [30])
    W = min(820, math.ceil(maxc * CH) + 44)
    per = max(20, min(maxc, int((W - 44) / CH + 1e-6)))  # 切り捨てで最長の行の末尾が折り返されないように
    wrapped = []
    for kind, s_ in rows:
        first = True
        while True:
            room = per - (len(prompt) + 1 if kind == "cmd" and first else 0)
            wrapped.append((kind, s_[:room], first))
            s_ = s_[room:]
            first = False
            if not s_:
                break
    LH, TOP = 22, 44
    H = TOP + len(wrapped) * LH + 16
    cv.add('<g><rect x="0" y="0" width="%d" height="%d" rx="10" fill="var(--code-bg)"/>'
           '<circle cx="18" cy="16" r="5" fill="var(--a3)" opacity=".8"/><circle cx="36" cy="16" r="5" fill="var(--a2)" opacity=".8"/>'
           '<circle cx="54" cy="16" r="5" fill="var(--a1)" opacity=".8"/>%s</g>'
           % (W, H, text(W / 2, 20, spec.get("title", ""), 12, fill="var(--code-fg)", extra=' opacity=".6"')))
    step = 0
    for i, (kind, s_, first) in enumerate(wrapped):
        y = TOP + i * LH + 14
        if kind == "cmd":
            if first:
                step += 1
            pre = ('<text x="22" y="%.1f" font-size="14" fill="var(--a1)" font-family="var(--mono)">%s</text>' % (y, esc(prompt))) if first else ""
            x0 = 22 + (len(prompt) + 1) * CH if first else 22
            cv.add('<g data-step="%d">%s<text x="%.1f" y="%.1f" font-size="14" fill="var(--code-fg)" font-family="var(--mono)" '
                   'data-effect="type" xml:space="preserve">%s</text></g>' % (step * 2, pre, x0, y, esc(s_)))
        else:
            cv.add('<text data-step="%d" data-effect="fade" x="22" y="%.1f" font-size="14" fill="var(--code-fg)" opacity=".72" '
                   'font-family="var(--mono)" xml:space="preserve">%s</text>' % (step * 2 + 1, y, esc(s_)))
    return W, H


def wrap(s, width, size=FONT):
    """見積もりの文字幅で折り返す（英字は空白で切る。句読点・閉じ括弧は行頭に置かない）。"""
    lines = []
    for para in str(s).split("\n"):
        cur = ""
        for ch in para:
            if cur and tw(cur + ch, size) > width and ch not in "、。，．）」』】！？!?,.)":
                k = cur.rfind(" ")
                if ch != " " and ord(ch) < 0x2E80 and k > 0 and ord(cur[-1]) < 0x2E80:
                    lines.append(cur[:k])
                    cur = cur[k + 1:] + ch
                else:
                    lines.append(cur.rstrip())
                    cur = "" if ch == " " else ch
            else:
                cur += ch
        lines.append(cur)
    return lines


def _disp(it, unit=""):
    v = it["value"]
    return it.get("display") or ("{:,}".format(v) if isinstance(v, int) else str(v)) + unit


def fig_chat(spec, cv):
    msgs = spec["messages"]
    FS, LH, PX, PY, AV, M, MAXT = 14, 21, 14, 10, 30, 10, 340
    names = {"user": "ユーザー", "ai": "AI"}
    speakers = []
    rows = []
    for m in msgs:
        f = str(m.get("from", ""))
        side = m.get("side") or ("right" if f.lower() in ("user", "me", "ユーザー", "あなた", "自分") else "left")
        if f not in speakers:
            speakers.append(f)
        lines = wrap(m.get("text", ""), MAXT, FS)
        bw = max(tw(l, FS) for l in lines) + 2 * PX
        rows.append((m, f, side, lines, max(bw, 44)))
    # 注記は吹き出しの空いている側（左の吹き出しは右、右は左）に出し、その分だけ幅を取る
    anyn = any(m.get("note") for m in msgs)
    W = max(460, max(r[4] for r in rows) + 2 * (M + AV + 12) + (250 if anyn else 90))
    y = 6
    prev = None
    for i, (m, f, side, lines, bw) in enumerate(rows):
        same = prev == (f, side)
        disp = names.get(f.lower(), f)
        bh = 2 * PY + LH * (len(lines) - 1) + 16
        head = 0 if same else 18
        by = y + head
        if side == "right":
            bx = W - M - AV - 12 - bw
            ax = W - M - AV / 2
            fill, ink = "var(--accent)", "var(--on-accent)"
            tail = "%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (bx + bw - 1, by + 9, bx + bw + 7, by + 13, bx + bw - 1, by + 20)
            nx, nanchor = bx + bw, "end"
        else:
            bx = M + AV + 12
            ax = M + AV / 2
            fill, ink = "var(--accent-soft)", "var(--ink)"
            tail = "%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (bx + 1, by + 9, bx - 7, by + 13, bx + 1, by + 20)
            nx, nanchor = bx, "start"
        k = speakers.index(f)
        av = m.get("avatar") or (disp[:2] if disp.isascii() else disp[:1])
        top = ""
        if not same:
            top = (text(nx, y + 12, disp, SUB, "700", "var(--muted)", nanchor)
                   + '<circle cx="%.1f" cy="%.1f" r="%d" fill="%s"/>' % (ax, by + AV / 2, AV / 2, acc(k))
                   + text(ax, by + AV / 2 + 4.5, av, 12 if len(av) > 1 else 13, "700", "var(--on-accent)"))
        body = "".join(text(bx + PX, by + PY + 13 + j * LH, l, FS, fill=ink, anchor="start") for j, l in enumerate(lines))
        cv.add('<g data-step="%d" data-effect="rise"%s>%s<polygon points="%s" fill="%s"/><rect x="%.1f" y="%.1f" width="%.1f" '
               'height="%.1f" rx="14" fill="%s"/>%s</g>'
               % (i, ann(dict(m, note_pos=m.get("note_pos") or ("left" if side == "right" else "right"))),
                  top, tail, fill, bx, by, bw, bh, fill, body))
        y = by + max(bh, AV if not same else 0) + (8 if i + 1 < len(rows) and rows[i + 1][1:3] == (f, side) else 14)
        prev = (f, side)
    return W, y


def fig_funnel(spec, cv):
    items = spec["items"]
    unit = spec.get("unit", "")
    n = len(items)
    vals = [float(it["value"]) for it in items]
    vmax = max(vals) or 1
    FW, SH, G = 380, 46, 6
    MINW = max(110, max(tw(_disp(it, unit), FONT) for it in items) + 30)
    widths = [max(MINW, FW * v / vmax) for v in vals]
    lw = max(tw(it["label"], 14) for it in items) + 20
    cx = lw + 10 + FW / 2
    show_ratio = spec.get("ratio", True)
    RW = 110 if show_ratio else 10
    W, H = lw + 10 + FW + RW, n * (SH + G) + 6
    for i, it in enumerate(items):
        y = 4 + i * (SH + G)
        w0 = widths[i]
        w1 = min(w0, widths[i + 1]) if i + 1 < n else max(MINW * 0.9, w0 * 0.86)
        poly = ('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" data-effect="rise"%s/>'
                % (cx - w0 / 2, y, cx + w0 / 2, y, cx + w1 / 2, y + SH, cx - w1 / 2, y + SH, acc(i),
                   " data-pulse" if spec.get("highlight") == i else ""))
        lab = text(lw, y + SH / 2 + 5, it["label"], 14, anchor="end")
        val = text(cx, y + SH / 2 + 5.5, _disp(it, unit), FONT, "700", "var(--on-accent)", extra=' data-count="0" data-effect="fade"')
        rat = ""
        if show_ratio and i > 0 and vals[i - 1]:
            p = 100 * vals[i] / vals[i - 1]
            rat = text(lw + 10 + FW + 14, y + SH / 2 + 4.5, "前段の %s%%" % ("%.1f" % p if p < 10 else "%.0f" % p), SUB,
                       fill="var(--muted)", anchor="start", extra=' data-effect="fade"')
        cv.add('<g data-step="%d"%s>%s%s%s%s</g>' % (i, ann(it), lab, poly, val, rat))
    return W, H


def _venn_fit(c, R, others, bw, bh, m=5):
    """円 c の中で、他の円に掛からずに bw×bh の箱が入る中心を探す（入らなければ最も近いもの）。"""
    best, bs = None, -1e9
    step = max(3.0, R / 30)
    k = int(2 * R / step) + 1
    for a in range(k):
        for b in range(k):
            px, py = c[0] - R + a * step, c[1] - R + b * step
            score = 1e9
            for dx in (-bw / 2, 0, bw / 2):
                for dy in (-bh / 2, 0, bh / 2):
                    qx, qy = px + dx, py + dy
                    score = min(score, R - m - math.hypot(qx - c[0], qy - c[1]))
                    for o in others:
                        score = min(score, math.hypot(qx - o[0], qy - o[1]) - R - m)
            if score > bs:
                best, bs = (px, py), score
    return best, bs >= 0


def fig_venn(spec, cv):
    sets = spec["sets"][:3]
    n = len(sets)
    if n < 2:
        raise SystemExit("figkit: venn の sets は 2〜3 個です")
    WR = 150 if n == 2 else 118
    blocks = []
    for s in sets:
        lines = [l for it in s.get("items", []) for l in wrap(it, WR, 13)]
        bw = max([tw(s["label"], FONT)] + [tw(l, 13) for l in lines]) + 4
        blocks.append((lines, bw, 22 + 18 * len(lines)))
    ratio = 1.0 if n == 2 else 1.08
    PAD = 14
    R = 110.0
    while True:
        d = ratio * R
        if n == 2:
            cs = [(PAD + R, PAD + R), (PAD + R + d, PAD + R)]
        else:
            cs = [(PAD + R, PAD + R), (PAD + R + d, PAD + R), (PAD + R + d / 2, PAD + R + d * 0.866)]
        spots = [_venn_fit(cs[i], R, cs[:i] + cs[i + 1:], blocks[i][1], blocks[i][2]) for i in range(n)]
        if all(ok for _, ok in spots) or R >= 260:
            break
        R += 8
    W = cs[1][0] + R + PAD
    H = (cs[2][1] if n == 3 else cs[0][1]) + R + PAD
    for i, s in enumerate(sets):
        cv.add('<g data-step="%d" data-effect="pop"%s><circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity=".16" '
               'stroke="%s" stroke-width="2"/></g>' % (i, ann(s), cs[i][0], cs[i][1], R, acc(i), acc(i)))
    for i, s in enumerate(sets):
        (px, py), _ = spots[i]
        lines, bw, bh = blocks[i]
        y0 = py - bh / 2 + 15
        t = text(px, y0, s["label"], FONT, "700", acc(i))
        t += "".join(text(px, y0 + 21 + j * 18, l, 13) for j, l in enumerate(lines))
        cv.add('<g data-step="%d" data-effect="fade">%s</g>' % (i, t))
    ov = spec.get("overlap")
    if ov:
        o = ov if isinstance(ov, dict) else {"label": ov}
        if n == 2:
            ox, oy, ow = (cs[0][0] + cs[1][0]) / 2, cs[0][1], max(60, min(2 * R - d - 16, 150))
        else:
            ox, oy, ow = sum(c[0] for c in cs) / 3, sum(c[1] for c in cs) / 3, 110
        lines = wrap(o["label"], ow, 13)
        pw = max(tw(l, 13) for l in lines) + 18
        ph = 18 * len(lines) + 10
        t = "".join(text(ox, oy - ph / 2 + 18 + j * 18, l, 13, "700") for j, l in enumerate(lines))
        cv.add('<g data-step="%d" data-effect="pop"%s><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="8" fill="var(--card)" '
               'stroke="var(--line)"/>%s</g>' % (n, ann(o), ox - pw / 2, oy - ph / 2, pw, ph, t))
    return W, H


def fig_matrix(spec, cv):
    xl = spec.get("x") or ["低", "高"]
    yl = spec.get("y") or ["低", "高"]
    PW, PH = 440, 340
    L = max(tw(yl[0], SUB), tw(yl[1], SUB)) + 24
    T, B, RM = 34, 52, 22
    W, H = L + PW + RM, T + PH + B
    X = lambda v: L + max(0.0, min(1.0, float(v))) * PW
    Y = lambda v: T + (1 - max(0.0, min(1.0, float(v)))) * PH
    mk = cv.marker()
    cv.add('<g data-step="0" data-effect="draw">'
           '<path d="M%.1f,%.1f H%.1f" fill="none" stroke="var(--muted)" stroke-width="1.8" marker-end="url(#%s)"/>'
           '<path d="M%.1f,%.1f V%.1f" fill="none" stroke="var(--muted)" stroke-width="1.8" marker-end="url(#%s)"/>'
           '<path d="M%.1f,%.1f V%.1f M%.1f,%.1f H%.1f" fill="none" stroke="var(--line)" stroke-width="1.2" stroke-dasharray="5 5"/></g>'
           % (L, T + PH, L + PW + 10, mk, L, T + PH, T - 12, mk, L + PW / 2, T, T + PH, L, T + PH / 2, L + PW))
    ticks = (text(X(.25), T + PH + 20, xl[0], SUB, fill="var(--muted)") + text(X(.75), T + PH + 20, xl[1], SUB, fill="var(--muted)")
             + text(L - 10, Y(.25) + 4, yl[0], SUB, fill="var(--muted)", anchor="end")
             + text(L - 10, Y(.75) + 4, yl[1], SUB, fill="var(--muted)", anchor="end"))
    if spec.get("xlabel"):
        ticks += text(L + PW + 10, T + PH + 42, spec["xlabel"] + " →", 13, "700", "var(--muted)", "end")
    if spec.get("ylabel"):
        ticks += text(L + 12, T - 10, "↑ " + spec["ylabel"], 13, "700", "var(--muted)", "start")
    cv.add('<g data-step="0" data-effect="fade">%s</g>' % ticks)
    taken = []
    quads = spec.get("quadrants") or []
    qs = []
    for q, name in enumerate(quads[:4]):
        qx, qy = L + (q % 2) * PW / 2, T + (q // 2) * PH / 2
        lines = wrap(name, PW / 2 - 28, 14)
        taken.append((qx + 8, qy + 6, max(tw(l, 14) for l in lines) + 10, 20 * len(lines) + 4))
        qs.append('<g><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" fill-opacity=".07"/>%s</g>'
                  % (qx + 1, qy + 1, PW / 2 - 2, PH / 2 - 2, acc(q),
                     "".join(text(qx + 12, qy + 22 + j * 20, l, 14, "700", acc(q), "start") for j, l in enumerate(lines))))
    if qs:
        cv.add('<g data-step="1" data-stagger="120" data-effect="fade">%s</g>' % "".join(qs))
    for k, it in enumerate(spec.get("items", [])):
        px, py = X(it["x"]), Y(it["y"])
        lw, lh = tw(it["label"], 13) + 6, 18
        cands = []
        for dy in (0, 14, -14, 26, -26):
            cands += [(px + 11, py - lh / 2 + dy), (px - 11 - lw, py - lh / 2 + dy)]
        cands += [(px - lw / 2, py - 12 - lh), (px - lw / 2, py + 12), (px - lw / 2, py - 30 - lh), (px - lw / 2, py + 30)]

        def cost(c):
            x, y = c
            if x < L + 2 or x + lw > L + PW - 2 or y < T + 2 or y + lh > T + PH - 2:
                return 1e9
            return sum(max(0, min(x + lw, a + w) - max(x, a)) * max(0, min(y + lh, b + h) - max(y, b)) for a, b, w, h in taken)
        pick = min(cands, key=cost)   # 重ならない候補（同点なら先の候補）、無ければ重なりが最も小さいもの
        taken.append((pick[0], pick[1], lw, lh))
        taken.append((px - 8, py - 8, 16, 16))
        cv.add('<g data-step="%d"%s><circle cx="%.1f" cy="%.1f" r="7" fill="%s" stroke="var(--card)" stroke-width="2" data-effect="pop"%s/>%s</g>'
               % (2 + k, ann(it), px, py, acc(k), " data-pulse" if it.get("pulse") else "",
                  text(pick[0] + 3, pick[1] + 13.5, it["label"], 13, "700", anchor="start", extra=' data-effect="fade"')))
    return W, H


def fig_timeline(spec, cv):
    items = spec["items"]
    n = len(items)
    BW = 170
    blocks = []
    for it in items:
        lab = wrap(it.get("label", ""), BW, 14)
        sub = wrap(it["sub"], BW, SUB) if it.get("sub") else []
        w = max([tw(it.get("date", ""), 14)] + [tw(l, 14) for l in lab] + [tw(l, SUB) for l in sub]) + 12
        blocks.append((lab, sub, w, 18 + 19 * len(lab) + 16 * len(sub)))
    # 同じ側の 2 つ隣と重ならない間隔
    gap = max([(blocks[i][2] + blocks[i + 2][2]) / 4 + 8 for i in range(n - 2)] + [blocks[i][2] / 2 + 6 for i in range(n)] + [70])
    STEM, PAD = 26, 12
    up = max([blocks[i][3] for i in range(0, n, 2)] + [0])
    dn = max([blocks[i][3] for i in range(1, n, 2)] + [0])
    AY = PAD + up + STEM + 6
    x0 = PAD + max(blocks[0][2] / 2, 24)
    xs = [x0 + gap * i for i in range(n)]
    W = xs[-1] + max(blocks[-1][2] / 2, 24) + PAD + 12
    H = AY + (dn + STEM + 6 if n > 1 else 10) + PAD
    cv.add('<path data-step="0" data-effect="draw" d="M%.1f,%.1f H%.1f" fill="none" stroke="var(--muted)" stroke-width="2.5" '
           'stroke-opacity=".6" stroke-linecap="round" marker-end="url(#%s)"/>' % (6, AY, W - 6, cv.marker()))
    for i, it in enumerate(items):
        lab, sub, w, h = blocks[i]
        x = xs[i]
        top = i % 2 == 0
        hl = bool(it.get("highlight"))
        col = "var(--accent)" if hl else acc(i)
        sy = AY - 8 - STEM if top else AY + 8 + STEM
        y0 = sy - h + 13 if top else sy + 15
        t = text(x, y0, it.get("date", ""), 14, "800", col)
        t += "".join(text(x, y0 + 19 * (j + 1), l, 14, "700") for j, l in enumerate(lab))
        t += "".join(text(x, y0 + 19 * len(lab) + 16 * (j + 1), l, SUB, fill="var(--muted)") for j, l in enumerate(sub))
        ring = ('<circle cx="%.1f" cy="%.1f" r="13" fill="none" stroke="var(--accent)" stroke-width="2" data-effect="pop" data-pulse/>'
                % (x, AY)) if hl else ""
        cv.add('<g data-step="%d"%s><line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.6" stroke-dasharray="3 3"/>'
               '<circle cx="%.1f" cy="%.1f" r="%d" fill="%s" stroke="var(--card)" stroke-width="2.5" data-effect="pop"/>%s'
               '<g data-effect="fade">%s</g></g>'
               % (1 + i, ann(it), x, AY + (-8 if top else 8), x, sy, col, x, AY, 9 if hl else 7, col, ring, t))
    return W, H


def fig_org(spec, cv):
    root = spec["root"]
    VG = 58
    MAXW = spec.get("max_width", 900)
    nodes = []   # (node, depth, parent index, branch)

    def walk(nd, d, p, br):
        k = len(nodes)
        nodes.append((nd, d, p, br))
        for j, c in enumerate(nd.get("children", [])):
            walk(c, d + 1, k, j if d == 0 else br)
    walk(root, 0, None, 0)
    kids = {k: [j for j, t in enumerate(nodes) if t[2] == k] for k in range(len(nodes))}
    # 葉だけを子に持つ親は、幅が足りないとき子を縦に積む（左の縦線から枝を出す）
    leafpar = [k for k in kids if len(kids[k]) >= 2 and all(not kids[c] for c in kids[k])]
    IND = 26

    def layout(gap, minw, pad, stacked):
        size = []
        for nd, d, p, br in nodes:
            w = max(minw, tw(nd["label"], FONT) + pad, tw(nd.get("sub", ""), SUB) + pad)
            size.append((min(w, 240), 62 if nd.get("sub") else 46))
        span = {}

        def width(k):
            cs = kids[k]
            if k in stacked:
                span[k] = max(size[k][0], IND + max(size[c][0] for c in cs))
                for c in cs:
                    span[c] = size[c][0]
            elif cs:
                span[k] = max(size[k][0], sum(width(c) for c in cs) + gap * (len(cs) - 1))
            else:
                span[k] = size[k][0]
            return span[k]
        return size, span, width(0)

    tries = [(26, 110, 36, False), (14, 84, 26, False), (14, 84, 26, True), (8, 60, 18, True), (4, 0, 12, True)]
    for gap, minw, pad, allow in tries:
        stacked = set()
        size, span, total = layout(gap, minw, pad, stacked)
        while allow and total + 24 > MAXW and len(stacked) < len(leafpar):
            stacked.add(max((k for k in leafpar if k not in stacked), key=lambda k: span.get(k, 0)))
            size, span, total = layout(gap, minw, pad, stacked)
        if total + 24 <= MAXW:
            break
    depth = max(t[1] for t in nodes)
    rowh = [max(size[k][1] for k in range(len(nodes)) if nodes[k][1] == d) for d in range(depth + 1)]
    rowy = [12 + sum(rowh[:d]) + VG * d for d in range(depth + 1)]
    pos = {}
    spine = {}

    def place(k, left):
        cx = left + span[k] / 2
        cs = kids[k]
        d = nodes[k][1]
        if k in stacked:
            y = rowy[d + 1]
            spine[k] = left + 10
            for c in cs:
                pos[c] = (left + IND, y, size[c][0], size[c][1])
                y += size[c][1] + 10
        elif cs:
            inner = sum(span[c] for c in cs) + gap * (len(cs) - 1)
            x = cx - inner / 2
            for c in cs:
                place(c, x)
                x += span[c] + gap
        w, h = size[k]
        pos[k] = (cx - w / 2, rowy[d] + (rowh[d] - h) / 2, w, h)
    place(0, 12)
    W, H = total + 24, max(y + h for x, y, w, h in pos.values()) + 12
    if spec.get("hover", len(nodes) >= 8):
        cv.fig["hover"] = True
    for k, (nd, d, p, br) in enumerate(nodes):
        if p is None:
            continue
        px, py, pw, ph = pos[p]
        cx_, cy_, cw, ch = pos[k]
        my = rowy[d] - VG / 2
        if p in stacked:
            dd = "M%.1f,%.1f V%.1f H%.1f V%.1f H%.1f" % (px + pw / 2, py + ph, my, spine[p], cy_ + ch / 2, cx_ - 1)
        else:
            dd = "M%.1f,%.1f V%.1f H%.1f V%.1f" % (px + pw / 2, py + ph, my, cx_ + cw / 2, cy_)
        cv.add('<path data-step="%d" data-effect="draw" data-link="o%d o%d" d="%s" fill="none" '
               'stroke="var(--accent-2)" stroke-width="1.8"/>' % (2 * d - 1, p, k, dd))
    for k, (nd, d, p, br) in enumerate(nodes):
        x, y, w, h = pos[k]
        a = ' data-step="%d" data-effect="pop"%s' % (2 * d, " data-pulse" if nd.get("pulse") else "")
        cv.add(box(x, y, w, h, nd["label"], nd.get("sub"), "start" if d == 0 else "normal",
                   ci=None if d == 0 else br, attrs=a + ann(nd, node="o%d" % k)))
    return W, H


# ──────────────────────────────────────────────────────────────────────────
# 追加の図（waffle・bullet・slope・dumbbell・sparks・radial・sankey・heatmap）
# ──────────────────────────────────────────────────────────────────────────
def _vfmt(v):
    """値の表示（小数 1 桁まで・3 桁区切り）。軸の切りのよい値は _nice（名前が重なって line・bars が壊れていた）"""
    return _fmtnum(round(float(v), 1))


def fig_waffle(spec, cv):
    items = spec["items"]
    n = int(spec.get("cells", 100))
    cols = int(spec.get("cols", 10))
    total = float(sum(float(it["value"]) for it in items)) or 1
    counts = [int(round(n * float(it["value"]) / total)) for it in items]
    counts[-1] = max(0, n - sum(counts[:-1]))
    S, G = 22, 4
    rows = math.ceil(n / cols)
    gw = cols * (S + G)
    k = 0
    for i, c in enumerate(counts):
        cells = []
        for _ in range(c):
            r, q = divmod(k, cols)
            cells.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s"/>' % (q * (S + G), r * (S + G), S, S, acc(i)))
            k += 1
        cv.add('<g data-step="%d" data-stagger="18" data-effect="pop"%s>%s</g>' % (i, ann(items[i]), "".join(cells)))
    while k < n:
        r, q = divmod(k, cols)
        cv.add('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="var(--line)" data-step="0" data-effect="fade"/>' % (q * (S + G), r * (S + G), S, S))
        k += 1
    lx = gw + 24
    lw = max(tw(it["label"], 14) for it in items) + 110
    for i, it in enumerate(items):
        y = 14 + i * 34
        cv.add('<g data-step="%d"><rect x="%d" y="%d" width="14" height="14" rx="3" fill="%s"/>%s%s</g>'
               % (i, lx, y, acc(i), text(lx + 22, y + 12, it["label"], 14, anchor="start"),
                  text(lx + lw, y + 12, "%d%%" % round(100 * counts[i] / n) if spec.get("percent", True) else _vfmt(it["value"]) + spec.get("unit", ""),
                       15, "800", acc(i), "end", extra=' data-count="0"')))
    return lx + lw + 6, max(rows * (S + G), 14 + len(items) * 34)


def fig_bullet(spec, cv):
    items = spec["items"]
    unit = spec.get("unit", "")
    lw = max(tw(it["label"]) for it in items) + 20
    BW, BH, G = 420, 30, 26
    W, H = lw + BW + 90, len(items) * (BH + G) + 10
    for i, it in enumerate(items):
        mx = float(it.get("max") or max([float(it["value"]), float(it.get("target", 0))] + [float(b) for b in it.get("ranges", [])]) * 1.1 or 1)
        X = lambda v: lw + BW * float(v) / mx
        y = 8 + i * (BH + G)
        bands = sorted(float(b) for b in it.get("ranges", [mx * .5, mx * .8, mx]))
        bg = "".join('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="var(--ink)" opacity="%.2f"/>'
                     % (lw, y, X(b) - lw, BH, .05 + .05 * (len(bands) - j)) for j, b in enumerate(reversed(bands)))
        cv.add('<g data-step="%d" data-effect="fade">%s%s</g>' % (i * 3, text(lw - 12, y + BH / 2 + 5, it["label"], anchor="end"), bg))
        cv.add('<rect data-step="%d" data-effect="grow" data-grow="right"%s x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s"/>'
               % (i * 3 + 1, ann(it), lw, y + BH * .3, max(2, X(it["value"]) - lw), BH * .4, acc(i)))
        if it.get("target") is not None:
            tx = X(it["target"])
            cv.add('<line data-step="%d" data-effect="drop" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--ink)" stroke-width="3"/>'
                   % (i * 3 + 2, tx, y + 3, tx, y + BH - 3))
        cv.add(text(lw + BW + 10, y + BH / 2 + 5, it.get("display") or _vfmt(it["value"]) + unit, 14, "800", acc(i), "start",
                    extra=' data-step="%d" data-count="0" data-effect="fade"' % (i * 3 + 1)))
    return W, H


def fig_slope(spec, cv):
    labels = spec.get("labels", ["前", "後"])
    items = spec["items"]
    unit = spec.get("unit", "")
    vals = [float(v) for it in items for v in (it["from"], it["to"])]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    lw = max(tw(it["label"], 13) + tw(_vfmt(it["from"]) + unit, 13) for it in items) + 30
    rw = max(tw(it["label"], 13) + tw(_vfmt(it["to"]) + unit, 13) for it in items) + 30
    PW, TOP, PH = 300, 44, max(200, len(items) * 34)
    Y = lambda v: TOP + PH - PH * (float(v) - lo) / (hi - lo)
    x0, x1 = lw, lw + PW
    W, H = lw + PW + rw, TOP + PH + 20
    hl = spec.get("highlight")
    cv.add('<g data-step="0" data-effect="fade"><line x1="%d" y1="%d" x2="%d" y2="%d" stroke="var(--line)" stroke-width="2"/>'
           '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="var(--line)" stroke-width="2"/>%s%s</g>'
           % (x0, TOP - 10, x0, TOP + PH + 8, x1, TOP - 10, x1, TOP + PH + 8, text(x0, 20, labels[0], 13, "800", "var(--muted)"), text(x1, 20, labels[1], 13, "800", "var(--muted)")))
    for i, it in enumerate(items):
        y0, y1 = Y(it["from"]), Y(it["to"])
        dim = hl is not None and hl != i
        col = acc(i)
        op = ' opacity=".35"' if dim else ""
        cv.add('<g data-step="%d"%s%s><path data-effect="draw" d="M%.1f,%.1f L%.1f,%.1f" fill="none" stroke="%s" stroke-width="%s"/>'
               '<circle cx="%.1f" cy="%.1f" r="6" fill="%s" data-effect="pop"/><circle cx="%.1f" cy="%.1f" r="6" fill="%s" data-effect="pop"/>'
               '%s%s</g>'
               % (1 + i, ann(it), op, x0, y0, x1, y1, col, "4" if hl == i else "2.5", x0, y0, col, x1, y1, col,
                  text(x0 - 12, y0 + 5, "%s  %s" % (it["label"], _vfmt(it["from"]) + unit), 13, anchor="end"),
                  text(x1 + 12, y1 + 5, "%s  %s" % (_vfmt(it["to"]) + unit, it["label"]), 13, "700", col, "start")))
    return W, H


def fig_dumbbell(spec, cv):
    items = spec["items"]
    unit = spec.get("unit", "")
    labels = spec.get("labels", ["前", "後"])
    vals = [float(v) for it in items for v in (it["from"], it["to"])]
    lo = min(0.0, min(vals)) if spec.get("zero", True) else min(vals)
    hi = max(vals) * 1.05 or 1
    lw = max(tw(it["label"]) for it in items) + 20
    BW, RH, TOP = 440, 38, 38
    X = lambda v: lw + BW * (float(v) - lo) / (hi - lo)
    W, H = lw + BW + 70, TOP + len(items) * RH + 6
    cv.add('<g data-step="0" data-effect="fade"><circle cx="%d" cy="16" r="6" fill="var(--muted)"/>%s<circle cx="%d" cy="16" r="6" fill="var(--accent)"/>%s</g>'
           % (lw, text(lw + 12, 21, labels[0], 13, anchor="start"), lw + 30 + tw(labels[0], 13), text(lw + 42 + tw(labels[0], 13), 21, labels[1], 13, anchor="start")))
    for i, it in enumerate(items):
        y = TOP + i * RH + RH / 2
        a, b = X(it["from"]), X(it["to"])
        up = float(it["to"]) >= float(it["from"])
        cv.add('<g data-step="%d"%s>%s<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--line)" stroke-width="1" stroke-dasharray="2 4"/>'
               '<circle cx="%.1f" cy="%.1f" r="7" fill="var(--muted)" data-effect="pop"/></g>'
               % (1 + i, ann(it), text(lw - 12, y + 5, it["label"], anchor="end"), lw, y, lw + BW, y, a, y))
        cv.add('<g data-step="%d"><path data-effect="draw" d="M%.1f,%.1f L%.1f,%.1f" stroke="%s" stroke-width="5" stroke-linecap="round" fill="none" opacity=".55"/>'
               '<circle cx="%.1f" cy="%.1f" r="8" fill="var(--accent)" data-effect="pop"/>%s</g>'
               % (1 + len(items) + i, a, y, b, y, "var(--ok,#16a34a)" if up else "var(--ng,#dc2626)", b, y,
                  text(max(a, b) + 14, y + 5, ("+" if up else "") + _vfmt(float(it["to"]) - float(it["from"])) + unit, 13, "800",
                       "var(--ok,#16a34a)" if up else "var(--ng,#dc2626)", "start")))
    return W, H


def fig_sparks(spec, cv):
    items = spec["items"]
    unit = spec.get("unit", "")
    cols = int(spec.get("cols", min(3, len(items))))
    CW, CH, G = 230, 118, 14
    for i, it in enumerate(items):
        r, q = divmod(i, cols)
        x, y = q * (CW + G), r * (CH + G)
        vs = [float(v) for v in it["values"]]
        lo, hi = min(vs), max(vs)
        if hi == lo:
            hi = lo + 1
        pts = [(x + 14 + (CW - 28) * k / max(1, len(vs) - 1), y + CH - 16 - (CH - 70) * (v - lo) / (hi - lo)) for k, v in enumerate(vs)]
        d = "M" + " L".join("%.1f,%.1f" % p for p in pts)
        area = d + " L%.1f,%.1f L%.1f,%.1f Z" % (pts[-1][0], y + CH - 10, pts[0][0], y + CH - 10)
        delta = vs[-1] - vs[0]
        up = delta >= 0
        good = up if not it.get("lower_is_better") else not up
        dc = "var(--ok,#16a34a)" if good else "var(--ng,#dc2626)"
        cv.add('<g data-step="%d"%s><rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="var(--card)" stroke="var(--line)" data-effect="fade"/>%s%s%s'
               '<path d="%s" fill="%s" opacity=".12" data-effect="fade"/><path d="%s" fill="none" stroke="%s" stroke-width="2.4" stroke-linejoin="round" data-effect="draw"/>'
               '<circle cx="%.1f" cy="%.1f" r="4.5" fill="%s" data-effect="pop"/></g>'
               % (i, ann(it), x, y, CW, CH, text(x + 14, y + 24, it["label"], 13, "700", "var(--muted)", "start"),
                  text(x + 14, y + 50, it.get("display") or _vfmt(vs[-1]) + unit, 22, "900", "var(--ink)", "start", extra=' data-count="0"'),
                  text(x + CW - 14, y + 24, ("▲ " if up else "▼ ") + _vfmt(abs(delta)) + unit, 12, "800", dc, "end"),
                  area, acc(i), d, acc(i), pts[-1][0], pts[-1][1], acc(i)))
    rows = math.ceil(len(items) / cols)
    return cols * (CW + G) - G, rows * (CH + G) - G


def fig_radial(spec, cv):
    items = spec["items"]
    unit = spec.get("unit", "%")
    mx = float(spec.get("max", 100))
    cx, cy, R0, SW, G = 150, 150, 132, 16, 6
    for i, it in enumerate(items):
        r = R0 - i * (SW + G)
        if r < 30:
            break
        f = max(0.0, min(0.999, float(it["value"]) / mx))
        a0, a1 = -math.pi / 2, -math.pi / 2 + 2 * math.pi * f
        large = 1 if f > .5 else 0
        cv.add('<circle cx="%d" cy="%d" r="%d" fill="none" stroke="var(--line)" stroke-width="%d" opacity=".6" data-step="0" data-effect="fade"/>' % (cx, cy, r, SW))
        cv.add('<path data-step="%d" data-effect="draw"%s d="M%.2f,%.2f A%d,%d 0 %d 1 %.2f,%.2f" fill="none" stroke="%s" stroke-width="%d" stroke-linecap="round"/>'
               % (1 + i, ann(it), cx + r * math.cos(a0), cy + r * math.sin(a0), r, r, large, cx + r * math.cos(a1), cy + r * math.sin(a1), acc(i), SW))
    lx = 320
    lw = max(tw(it["label"], 14) for it in items) + 100
    for i, it in enumerate(items):
        y = 60 + i * 34
        cv.add('<g data-step="%d"><rect x="%d" y="%d" width="14" height="14" rx="7" fill="%s"/>%s%s</g>'
               % (1 + i, lx, y, acc(i), text(lx + 22, y + 12, it["label"], 14, anchor="start"),
                  text(lx + lw, y + 12, it.get("display") or _vfmt(it["value"]) + unit, 15, "800", acc(i), "end", extra=' data-count="0"')))
    if spec.get("center"):
        cv.add(text(cx, cy + 6, spec["center"], 16, "800", extra=' data-step="%d" data-effect="pop"' % (len(items) + 1)))
    return lx + lw + 6, 300


def fig_sankey(spec, cv):
    """2 段（左→右）の流れ。links の from/to は左・右の名前。帯の太さは値に比例。"""
    links = spec["links"]
    unit = spec.get("unit", "")
    L, Rn = [], []
    for l in links:
        if l["from"] not in L:
            L.append(l["from"])
        if l["to"] not in Rn:
            Rn.append(l["to"])
    tot = float(sum(float(l["value"]) for l in links)) or 1
    GAP, NW, HH = 14, 16, 300
    k = (HH - GAP * (max(len(L), len(Rn)) - 1)) / tot
    lw = max(tw(n, 14) for n in L) + 14
    rw = max(tw(n, 14) + tw(_vfmt(tot) + unit, 12) for n in Rn) + 30
    x0, x1 = lw, lw + 360
    def stack(names, side):
        pos, y = {}, 10
        for n in names:
            v = sum(float(l["value"]) for l in links if l[side] == n)
            pos[n] = [y, v * k, v]
            y += v * k + GAP
        return pos
    pl, pr = stack(L, "from"), stack(Rn, "to")
    offl = {n: pl[n][0] for n in L}
    offr = {n: pr[n][0] for n in Rn}
    for i, n in enumerate(L):
        y, h, v = pl[n]
        cv.add('<g data-step="0"><rect x="%d" y="%.1f" width="%d" height="%.1f" rx="3" fill="%s" data-effect="grow" data-grow="up"/>%s</g>'
               % (x0 - NW, y, NW, h, acc(i), text(x0 - NW - 8, y + h / 2 + 5, n, 14, "700", anchor="end")))
    for j, l in enumerate(links):
        i = L.index(l["from"])
        h = float(l["value"]) * k
        ya, yb = offl[l["from"]], offr[l["to"]]
        offl[l["from"]] += h
        offr[l["to"]] += h
        m = (x0 + x1) / 2
        d = ("M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f L%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f Z"
             % (x0, ya, m, ya, m, yb, x1, yb, x1, yb + h, m, yb + h, m, ya + h, x0, ya + h))
        cv.add('<path data-step="%d" data-effect="wipe"%s d="%s" fill="%s" opacity=".38"/>' % (1 + i, ann(l), d, acc(i)))
    for q, n in enumerate(Rn):
        y, h, v = pr[n]
        cv.add('<g data-step="%d"><rect x="%d" y="%.1f" width="%d" height="%.1f" rx="3" fill="var(--accent-2)" data-effect="grow" data-grow="up"/>%s%s</g>'
               % (1 + len(L), x1, y, NW, h, text(x1 + NW + 8, y + h / 2 + 1, n, 14, "700", anchor="start"),
                  text(x1 + NW + 8, y + h / 2 + 17, _vfmt(v) + unit, 12, fill="var(--muted)", anchor="start", extra=' data-count="0"')))
    H = max(pl[L[-1]][0] + pl[L[-1]][1], pr[Rn[-1]][0] + pr[Rn[-1]][1]) + 14
    return x1 + NW + rw, max(H, 60)


def fig_heatmap(spec, cv):
    rows, cols = spec["rows"], spec["cols"]
    vals = spec["values"]
    flat = [float(v) for r in vals for v in r]
    lo, hi = min(flat), max(flat)
    if hi == lo:
        hi = lo + 1
    CW, CH = max(44, max(tw(c, 12) for c in cols) + 12), 34
    lw = max(tw(r, 13) for r in rows) + 16
    TOP = 28
    show = spec.get("show_values", True)
    for j, c in enumerate(cols):
        cv.add(text(lw + j * CW + CW / 2, 18, c, 12, "700", "var(--muted)", extra=' data-step="0" data-effect="fade"'))
    for i, r in enumerate(rows):
        cells = []
        for j, v in enumerate(vals[i]):
            f = (float(v) - lo) / (hi - lo)
            x, y = lw + j * CW, TOP + i * CH
            cells.append('<rect x="%d" y="%d" width="%d" height="%d" rx="5" fill="var(--accent)" opacity="%.2f"/>%s'
                         % (x + 2, y + 2, CW - 4, CH - 4, .08 + .85 * f,
                            text(x + CW / 2, y + CH / 2 + 5, _vfmt(v), 12, "700", "var(--on-accent)" if f > .55 else "var(--ink)") if show else ""))
        cv.add('<g data-step="%d">%s<g data-stagger="45" data-effect="pop">%s</g></g>'
               % (1 + i, text(lw - 10, TOP + i * CH + CH / 2 + 5, r, 13, anchor="end"),
                  "".join('<g>%s</g>' % c for c in cells)))
    return lw + len(cols) * CW + 6, TOP + len(rows) * CH + 6


# ──────────────────────────────────────────────────────────────────────────
# 追加の図（レーダー・ツリーマップ・マインドマップ・散布図・積み上げ棒・ピラミッド）
#   色の付いた面の上の文字は、テーマの差し色によっては読めないので、面は淡く塗り、文字は --ink にする
# ──────────────────────────────────────────────────────────────────────────
def fig_radar(spec, cv):
    axes = spec["axes"]
    series = spec["series"]
    n = len(axes)
    if n < 3:
        raise SystemExit("figkit: radar の axes は 3 個以上です")
    mx = float(spec.get("max") or max(float(v) for s_ in series for v in s_["values"]) or 1)
    R = 150
    lw = max(tw(a, 13) for a in axes) + 14
    cx, cy = R + lw + 10, R + 40
    P = lambda k, v: (cx + R * v * math.sin(2 * math.pi * k / n), cy - R * v * math.cos(2 * math.pi * k / n))
    grid = ""
    for g in (.25, .5, .75, 1):
        grid += '<polygon points="%s" fill="none" stroke="var(--line)" stroke-width="1"/>' % " ".join("%.1f,%.1f" % P(k, g) for k in range(n))
    for k, a in enumerate(axes):
        x, y = P(k, 1)
        grid += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--line)"/>' % (cx, cy, x, y)
        lx, ly = P(k, 1.13)
        anchor = "middle" if abs(lx - cx) < 8 else ("start" if lx > cx else "end")
        grid += text(lx, ly + 5, a, 13, "700", "var(--muted)", anchor)
    cv.add('<g data-step="0" data-effect="fade">%s</g>' % grid)
    for si, s_ in enumerate(series):
        pts = [P(k, max(0.0, min(1.0, float(v) / mx))) for k, v in enumerate(s_["values"])]
        col = acc(si)
        poly = '<polygon points="%s" fill="%s" fill-opacity=".18" stroke="%s" stroke-width="2.5" stroke-linejoin="round"/>' % (
            " ".join("%.1f,%.1f" % p for p in pts), col, col)
        dots = "".join('<circle cx="%.1f" cy="%.1f" r="4" fill="var(--card)" stroke="%s" stroke-width="2"%s/>'
                       % (x, y, col, ' data-detail="%s"' % esc("%s・%s: %s" % (s_.get("name", ""), axes[k], _fmtnum(s_["values"][k]))))
                       for k, (x, y) in enumerate(pts))
        cv.add('<g data-step="%d" data-effect="zoom"%s>%s%s</g>' % (1 + si, ann(s_), poly, dots))
    W, H = cx + R + lw + 10, cy + R + 34
    if len(series) > 1 or series[0].get("name"):
        lg = "".join('<g><rect x="%.1f" y="%d" width="12" height="12" rx="3" fill="%s" fill-opacity=".5" stroke="%s"/>%s</g>'
                     % (12 + k * 120, H - 6, acc(k), acc(k), text(12 + k * 120 + 18, H + 5, s_.get("name", ""), 12, fill="var(--muted)", anchor="start"))
                     for k, s_ in enumerate(series))
        cv.add('<g data-step="0" data-effect="fade">%s</g>' % lg)
        H += 20
    return W, H


def _squarify(vals, x, y, w, h):
    """値に比例した長方形に分ける（squarified treemap）。vals は大きい順。"""
    out = []
    vals = list(vals)
    total = sum(v for _, v in vals) or 1
    scale = w * h / total
    items = [(i, v * scale) for i, v in vals]

    def worst(row, side):
        s = sum(a for _, a in row)
        if not s or not side:
            return float("inf")
        return max(max(side * side * a / (s * s), (s * s) / (side * side * a)) for _, a in row if a > 0)

    while items:
        side = min(w, h)
        row = [items.pop(0)]
        while items and worst(row + [items[0]], side) <= worst(row, side):
            row.append(items.pop(0))
        s = sum(a for _, a in row)
        if w >= h:
            cw = s / h if h else 0
            yy = y
            for i, a in row:
                ch = a / cw if cw else 0
                out.append((i, x, yy, cw, ch))
                yy += ch
            x += cw
            w -= cw
        else:
            rh = s / w if w else 0
            xx = x
            for i, a in row:
                rw = a / rh if rh else 0
                out.append((i, xx, y, rw, rh))
                xx += rw
            y += rh
            h -= rh
    return out


def fig_treemap(spec, cv):
    items = spec["items"]
    unit = spec.get("unit", "")
    W, H = float(spec.get("width", 640)), float(spec.get("height", 360))
    order = sorted(range(len(items)), key=lambda i: -float(items[i]["value"]))
    rects = _squarify([(i, float(items[i]["value"])) for i in order], 0, 0, W, H)
    total = sum(float(it["value"]) for it in items) or 1
    for rank, (i, x, y, w, h) in enumerate(sorted(rects, key=lambda r: order.index(r[0]))):
        it = items[i]
        g = 3
        body = ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="8" fill="%s" fill-opacity=".22" stroke="%s" stroke-width="1.6"/>'
                % (x + g, y + g, max(0, w - 2 * g), max(0, h - 2 * g), acc(i), acc(i)))
        lab = ""
        if w > 70 and h > 40:
            fs = 15 if w > 140 and h > 70 else 12
            lines = wrap(it["label"], w - 20, fs)[:2]
            lab = "".join(text(x + 12, y + 22 + j * (fs + 4), l, fs, "800", anchor="start") for j, l in enumerate(lines))
            if h > 40 + len(lines) * (fs + 4):
                pct = 100 * float(it["value"]) / total
                lab += text(x + 12, y + 22 + len(lines) * (fs + 4) + 2, it.get("display") or "%s%s（%.0f%%）" % (_fmtnum(it["value"]), unit, pct),
                            12, fill="var(--muted)", anchor="start")
        det = it.get("detail") or "%s: %s%s" % (it["label"], _fmtnum(it["value"]), unit)
        cv.add('<g data-step="%d" data-effect="pop"%s%s>%s%s</g>'
               % (rank, ann(it), "" if it.get("detail") else ' data-detail="%s"' % esc(det), body, lab))
    return W, H


def fig_mindmap(spec, cv):
    center = spec["center"]
    br = spec["branches"]
    right = br[: (len(br) + 1) // 2]
    left = br[(len(br) + 1) // 2:]
    BW, CW = 210, 220
    def hgt(b):
        return max(1, len(b.get("children") or [])) * 30 + 14
    side_h = lambda bs: sum(hgt(b) for b in bs) + 16 * max(0, len(bs) - 1)
    H = max(side_h(right), side_h(left), 120) + 20
    cl = center if isinstance(center, str) else center.get("label", "")
    cw = max(120, tw(cl, 17) + 40)
    lw_max = max([tw(c if isinstance(c, str) else c.get("label", ""), 13) for b in br for c in (b.get("children") or [])] + [60]) + 24
    X0 = lw_max + BW + 30
    cx, cy = X0 + cw / 2, H / 2
    W = X0 + cw + 30 + BW + lw_max
    cv.add('<g data-step="0" data-effect="pop"%s><rect x="%.1f" y="%.1f" width="%.1f" height="52" rx="26" fill="var(--accent)"/>%s</g>'
           % (ann(center) if isinstance(center, dict) else "", cx - cw / 2, cy - 26, cw, text(cx, cy + 6, cl, 17, "800", "var(--on-accent)")))
    k = 0
    for side, bs in ((1, right), (-1, left)):
        y = (H - side_h(bs)) / 2
        for b in bs:
            h = hgt(b)
            by = y + h / 2
            bx = cx + side * (cw / 2 + 60)
            lab = b.get("label", "")
            bw = tw(lab, 14) + 26
            nx = bx if side > 0 else bx - bw
            sx = cx + side * cw / 2
            path = ('<path d="M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" data-effect="draw"/>'
                    % (sx, cy, sx + side * 40, cy, bx - side * 30, by, bx, by, acc(k)))
            node = ('<g data-effect="pop"><rect x="%.1f" y="%.1f" width="%.1f" height="32" rx="16" fill="%s" fill-opacity=".18" stroke="%s" stroke-width="1.8"/>%s</g>'
                    % (nx, by - 16, bw, acc(k), acc(k), text(nx + bw / 2, by + 5, lab, 14, "800")))
            kids = ""
            ch = b.get("children") or []
            ex = (nx + bw) if side > 0 else nx
            for j, c in enumerate(ch):
                cl_ = c if isinstance(c, str) else c.get("label", "")
                yy = y + 7 + 15 + j * 30
                tx = ex + side * 46
                kids += ('<g%s><path d="M%.1f,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-opacity=".6" stroke-width="1.6" data-effect="draw"/>'
                         '<circle cx="%.1f" cy="%.1f" r="3.5" fill="%s"/>%s</g>'
                         % (ann(c) if isinstance(c, dict) else "", ex, by, ex + side * 22, by, tx - side * 22, yy, tx - side * 6, yy, acc(k),
                            tx - side * 6, yy, acc(k), text(tx, yy + 4.5, cl_, 13, anchor="start" if side > 0 else "end")))
            cv.add('<g data-step="%d"%s>%s%s<g data-stagger="70" data-effect="fade">%s</g></g>' % (1 + k, ann(b), path, node, kids))
            y += h + 16
            k += 1
    return W, H


def fig_scatter(spec, cv):
    items = spec["items"]
    xs = [float(it["x"]) for it in items]
    ys = [float(it["y"]) for it in items]
    x0, x1 = spec.get("xmin", min(0, min(xs))), spec.get("xmax", _nice(max(xs)))
    y0, y1 = spec.get("ymin", min(0, min(ys))), spec.get("ymax", _nice(max(ys)))
    L, B, T, Rm = 62, 48, 16, 30
    PW, PH = 480, 300
    X = lambda v: L + PW * (float(v) - x0) / ((x1 - x0) or 1)
    Y = lambda v: T + PH - PH * (float(v) - y0) / ((y1 - y0) or 1)
    g = ""
    for k in range(5):
        vy = y0 + (y1 - y0) * k / 4
        vx = x0 + (x1 - x0) * k / 4
        g += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="var(--line)"/>' % (L, Y(vy), L + PW, Y(vy))
        g += text(L - 8, Y(vy) + 4, _fmtnum(round(vy, 2)), 11, fill="var(--muted)", anchor="end")
        g += text(X(vx), T + PH + 18, _fmtnum(round(vx, 2)), 11, fill="var(--muted)")
    g += text(L + PW / 2, T + PH + 40, spec.get("xlabel", ""), 13, "700", "var(--muted)")
    g += text(14, T + PH / 2, spec.get("ylabel", ""), 13, "700", "var(--muted)", extra=' transform="rotate(-90 14 %.1f)"' % (T + PH / 2))
    cv.add('<g data-step="0" data-effect="fade">%s</g>' % g)
    smax = max([float(it.get("size", 1)) for it in items] or [1])
    hl = spec.get("highlight")
    dots = ""
    for i, it in enumerate(items):
        r = 6 + 12 * math.sqrt(float(it.get("size", 1)) / smax) if any("size" in t for t in items) else 7
        col = acc(it.get("group", 0) if isinstance(it.get("group", 0), int) else 0)
        det = it.get("detail") or "%s（%s, %s）" % (it.get("label", ""), _fmtnum(it["x"]), _fmtnum(it["y"]))
        dots += ('<g%s%s><circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity=".35" stroke="%s" stroke-width="2"%s/>%s</g>'
                 % (ann(it), "" if it.get("detail") else ' data-detail="%s"' % esc(det), X(it["x"]), Y(it["y"]), r, col, col,
                    " data-pulse" if hl == i else "",
                    text(X(it["x"]) + r + 4, Y(it["y"]) + 4, it.get("label", ""), 12, anchor="start") if it.get("label") else ""))
    cv.add('<g data-step="1" data-stagger="60" data-effect="pop">%s</g>' % dots)
    if spec.get("trend") and len(items) > 1:
        n = len(xs)
        mx_, my_ = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx_) ** 2 for x in xs) or 1
        b = sum((x - mx_) * (y - my_) for x, y in zip(xs, ys)) / sxx
        a = my_ - b * mx_
        cv.add('<line data-step="2" data-effect="draw" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--accent-2)" stroke-width="2" stroke-dasharray="6 5"/>'
               % (X(x0), Y(a + b * x0), X(x1), Y(a + b * x1)))
    return L + PW + Rm, T + PH + 52


def fig_stacked(spec, cv):
    labels = spec["labels"]
    series = spec["series"]
    unit = spec.get("unit", "")
    pct = spec.get("percent", False)
    totals = [sum(float(s_["values"][j]) for s_ in series) for j in range(len(labels))]
    hi = 100.0 if pct else _nice(max(totals) or 1)
    L, T, B = 56, 30, 40
    BW, G = 54, 30
    PH = 280
    PW = len(labels) * (BW + G) + G
    Y = lambda v: T + PH - PH * v / hi
    g = ""
    for k in range(5):
        v = hi * k / 4
        g += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="var(--line)"/>%s' % (
            L, Y(v), L + PW, Y(v), text(L - 8, Y(v) + 4, _fmtnum(v) + ("%" if pct else ""), 11, fill="var(--muted)", anchor="end"))
    g += "".join(text(L + G + j * (BW + G) + BW / 2, T + PH + 20, l, 12, fill="var(--muted)") for j, l in enumerate(labels))
    lg = "".join('<g><rect x="%d" y="4" width="12" height="12" rx="3" fill="%s" fill-opacity=".75"/>%s</g>'
                 % (L + k * 110, acc(k), text(L + k * 110 + 18, 14, s_["name"], 12, fill="var(--muted)", anchor="start"))
                 for k, s_ in enumerate(series))
    cv.add('<g data-step="0" data-effect="fade">%s%s</g>' % (g, lg))
    base = [0.0] * len(labels)
    for si, s_ in enumerate(series):
        bars = ""
        for j, v in enumerate(s_["values"]):
            v = float(v)
            vv = 100 * v / (totals[j] or 1) if pct else v
            x = L + G + j * (BW + G)
            y_top, y_bot = Y(base[j] + vv), Y(base[j])
            det = "%s・%s: %s%s" % (labels[j], s_["name"], _fmtnum(v), unit) + ("（%.0f%%）" % vv if pct else "")
            bars += ('<rect x="%.1f" y="%.1f" width="%d" height="%.1f" fill="%s" fill-opacity=".75" stroke="var(--card)" stroke-width="1.5" data-detail="%s"/>'
                     % (x, y_top, BW, max(0, y_bot - y_top), acc(si), esc(det)))
            base[j] += vv
        cv.add('<g data-step="%d" data-effect="grow" data-grow="up"%s>%s</g>' % (1 + si, ann(s_), bars))
    if not pct:
        tt = "".join(text(L + G + j * (BW + G) + BW / 2, Y(base[j]) - 8, _fmtnum(totals[j]) + unit, 12, "800", extra=' data-count="0"')
                     for j in range(len(labels)))
        cv.add('<g data-step="%d" data-effect="fade">%s</g>' % (1 + len(series), tt))
    return L + PW + 10, T + PH + 34


def fig_pyramid(spec, cv):
    items = spec["items"]
    n = len(items)
    TW, SH, G = 520, 54, 6
    H = n * (SH + G)
    cx = TW / 2 + 10
    for i, it in enumerate(items):
        y = i * (SH + G)
        wt, wb = TW * (i + .35) / (n + .35), TW * (i + 1.35) / (n + .35)
        poly = ('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" fill-opacity=".2" stroke="%s" stroke-width="1.8"/>'
                % (cx - wt / 2, y, cx + wt / 2, y, cx + wb / 2, y + SH, cx - wb / 2, y + SH, acc(i), acc(i)))
        lab = it if isinstance(it, str) else it.get("label", "")
        sub = None if isinstance(it, str) else it.get("sub")
        t = text(cx, y + SH / 2 + (0 if sub else 5), lab, 15, "800") + (text(cx, y + SH / 2 + 17, sub, 12, fill="var(--muted)") if sub else "")
        cv.add('<g data-step="%d" data-effect="rise"%s>%s%s</g>' % (n - 1 - i, ann(it) if isinstance(it, dict) else "", poly, t))
    return TW + 20, H


# ──────────────────────────────────────────────────────────────────────────
# 触れる図（タブ・つまみ・順に見る・画像の注目点）。JS 無し・印刷では全部の状態を並べて見せる
#   動きの実行部の「登場」はかけない（data-motion="none"）。操作は md-to-doc の LAYOUT_JS が受け持つ
# ──────────────────────────────────────────────────────────────────────────
def _merge(base, over):
    out = dict(base)
    for k, v in over.items():
        if k in ("label", "text"):
            continue
        out[k] = v
    return out


# 段 0 が軸・枠・中心（いつも見せる土台）の図。スクロール連動・1 段ずつ見るとき、土台は最初から見せ、段に数えない
BASE_TYPES = {"line", "gantt", "matrix", "sequence", "timeline", "dumbbell", "sankey", "heatmap", "slope",
              "radar", "scatter", "stacked", "hub", "mindmap"}


def render_interactive(spec, fid):
    t = spec["type"]
    if t == "tabs":
        labels = spec.get("labels") or []
        panels = []
        for k, sub in enumerate(spec["states"]):
            svg, _ = render_svg(sub, "%s-t%d" % (fid, k))
            lab = labels[k] if k < len(labels) else "表示 %d" % (k + 1)
            panels.append('<div class="fk-panel" data-label="%s"><div class="fk-panel-label">%s</div>%s</div>' % (esc(lab), esc(lab), svg))
        return '<div class="fk-tabs" data-fk-tabs>%s</div>' % "".join(panels)
    if t == "slider":
        base = spec.get("base") or {}
        frames = spec["frames"]
        panels = []
        for k, fr in enumerate(frames):
            sub = _merge(base, fr)
            svg, _ = render_svg(sub, "%s-f%d" % (fid, k))
            lab = fr.get("label", str(k + 1))
            panels.append('<div class="fk-frame" data-label="%s"><div class="fk-panel-label">%s</div>%s%s</div>'
                          % (esc(lab), esc(lab), svg, '<p class="fk-frame-text">%s</p>' % esc(fr["text"]) if fr.get("text") else ""))
        return ('<div class="fk-slider" data-fk-slider data-name="%s"%s>%s</div>'
                % (esc(spec.get("label", "")), ' data-play' if spec.get("play") else "", "".join(panels)))
    if t == "walk":
        svg, _ = render_svg(spec["figure"], "%s-w" % fid)
        steps = spec.get("steps") or []
        lis = "".join('<li data-show="%s"%s>%s</li>' % (esc(st.get("show", "")), ' data-only' if st.get("only") else "", esc(st.get("text", "")))
                      for st in steps)
        base = ' data-stage-base="0"' if spec["figure"].get("type") in BASE_TYPES else ""
        return '<div class="fk-walk" data-fk-walk><div class="fk-walk-fig"%s>%s</div><ol class="fk-walk-steps">%s</ol></div>' % (base, svg, lis)
    if t == "hotspots":
        spots = spec.get("spots") or []
        pins = "".join('<button type="button" class="fk-pin" style="left:%.2f%%;top:%.2f%%" data-i="%d" aria-label="%s">%s</button>'
                       % (100 * float(sp["x"]), 100 * float(sp["y"]), i, esc(sp.get("title") or sp.get("label") or str(i + 1)),
                          esc(sp.get("label") or str(i + 1))) for i, sp in enumerate(spots))
        lis = "".join('<li data-i="%d"><b>%s</b>%s</li>' % (i, esc(sp.get("title", "")), (" — " if sp.get("title") else "") + esc(sp.get("detail", "")))
                      for i, sp in enumerate(spots))
        return ('<div class="fk-hs" data-fk-hs><div class="fk-hs-stage"><img src="%s" alt="%s" class="fk-hs-img" loading="lazy">%s</div>'
                '<ol class="fk-hs-list">%s</ol></div>' % (esc(spec["src"]), esc(spec.get("alt", "")), pins, lis))
    raise SystemExit("figkit: 不明な type: %r" % t)


INTERACTIVE_EX = {
    "tabs": '{"type":"tabs","labels":["月別","内訳"],"states":[{"type":"bars","items":[{"label":"4月","value":320}]},{"type":"donut","items":[{"label":"完了","value":820}]}]}',
    "slider": '{"type":"slider","label":"年","base":{"type":"bars","unit":"件"},"frames":[{"label":"2024","items":[{"label":"A","value":120},{"label":"B","value":80}]},{"label":"2025","items":[{"label":"A","value":180},{"label":"B","value":150}],"text":"B が伸びた"}],"play":true}',
    "walk": '{"type":"walk","figure":{"type":"flow","nodes":[{"id":"a","label":"受付"},{"id":"b","label":"審査"}],"edges":[{"from":"a","to":"b"}]},"steps":[{"text":"まず受付","show":1},{"text":"次に審査","show":2,"only":true}]}',
    "hotspots": '{"type":"hotspots","src":"screen.png","alt":"設定画面","spots":[{"x":0.18,"y":0.3,"title":"検索","detail":"名前で絞り込める"},{"x":0.8,"y":0.12,"title":"保存"}]}',
}


INTERACTIVE = {
    "tabs": "タブで図を切り替える（左右キー。印刷・JS 無しでは全部を並べる）",
    "slider": "つまみで値の組（frames）を切り替え、図が形を保ったまま変わる（base に共通、frames に差分。play で自動再生ボタン）",
    "walk": "図を 1 段ずつ見る（前へ・次へと説明の文。steps[].show で見せる段・only でその段だけ）",
    "hotspots": "画像の上の番号を押す・触れると説明が出る（画面の解説に。x・y は 0〜1）",
}


TYPES = {
    "flow": (fig_flow, "ノードと矢印の流れ（処理・データ・依頼の流れ、分岐、差し戻し）",
             '{"type":"flow","dir":"LR|TB","nodes":[{"id":"a","label":"実装","sub":"impl","kind":"start|end|decision|normal","pulse":false}],'
             '"edges":[{"from":"a","to":"b","label":"差分","travel":"{output}","flow":false,"dashed":false}],"focus":["a","b"]}'),
    "steps": (fig_steps, "番号付きの手順・工程（横並び。6 件以上は縦）",
              '{"type":"steps","dir":"LR|TB","items":[{"label":"準備","sub":"5 分"}],"walkthrough":false}'),
    "cycle": (fig_cycle, "循環する工程（PDCA、レビューの往復など）",
              '{"type":"cycle","center":"改善","items":[{"label":"計画"},{"label":"実行"}]}'),
    "bars": (fig_bars, "数量の比較（棒が伸び、値が数え上がる）",
             '{"type":"bars","orient":"h|v","unit":"件","max":null,"highlight":0,'
             '"items":[{"label":"A 案","value":120,"display":"120 件"}]}'),
    "metrics": (fig_metrics, "指標の強調（数値が数え上がるタイル）",
                '{"type":"metrics","items":[{"value":"98.5","unit":"%","label":"稼働率","delta":"+1.2pt","from":0}]}'),
    "compare": (fig_compare, "2〜3 案の対比（要点が 1 つずつ現れる）",
                '{"type":"compare","vs":"VS","columns":[{"title":"現行","points":["手作業","週 1 回"]}]}'),
    "hub": (fig_hub, "中心と周り（中核の仕組みと関係者・連携先）",
            '{"type":"hub","inward":false,"center":{"label":"API","sub":"v2","pulse":false},'
            '"items":[{"label":"Web","travel":"要求","flow":false}]}'),
    "layers": (fig_layers, "層の構成（上から順に書き、下から積み上がる）",
               '{"type":"layers","items":[{"label":"画面","sub":"Vue"},{"label":"API"},{"label":"DB"}]}'),
    "line": (fig_line, "数値の推移（線が描かれ、点が弾み、最後の値が数え上がる）",
             '{"type":"line","unit":"件","area":false,"labels":["4月","5月","6月"],'
             '"series":[{"name":"発火","values":[120,340,610]}]}'),
    "donut": (fig_donut, "割合（ドーナツが時計回りに埋まり、合計が数え上がる）",
              '{"type":"donut","unit":"件","center":{"value":"1,240","label":"合計"},'
              '"items":[{"label":"完了","value":820},{"label":"見送り","value":300},{"label":"失敗","value":120}]}'),
    "gantt": (fig_gantt, "予定・工程表（バーが伸び、今日の線が引かれる。start==end はマイルストーン）",
              '{"type":"gantt","today":"2026-10-06","tasks":[{"label":"設計","start":"2026-10-01","end":"2026-10-08"},'
              '{"label":"リリース","start":"2026-10-20","end":"2026-10-20"}]}'),
    "terminal": (fig_terminal, "コマンドの実行（コマンドが 1 文字ずつ打たれ、出力が続く）",
                 '{"type":"terminal","title":"bash","prompt":"$","lines":[{"cmd":"soda serve"},{"out":"listening on 127.0.0.1:7780"}]}'),
    "toggle": (None, "変更前／変更後（ボタンで切り替え、変わった所が光る。印刷・JS 無しでは並べて表示）",
               '{"type":"toggle","labels":["変更前","変更後"],"auto":false,'
               '"states":[{"type":"flow","nodes":[...],"edges":[...]},{"type":"flow","nodes":[{"id":"x","label":"新","changed":true}],"edges":[]}]}'),
    "sequence": (fig_sequence, "やりとりの順序（登場者の間のメッセージ。矢印の上を印が移動）",
                 '{"type":"sequence","actors":["利用者","サーバ"],'
                 '"messages":[{"from":"利用者","to":"サーバ","label":"ログイン"},{"from":"サーバ","to":"利用者","label":"トークン","reply":true}]}'),
    "chat": (fig_chat, "会話の吹き出し（順に現れる。side 省略時は from が user なら右、他は左。長い文は折り返す）",
             '{"type":"chat","messages":[{"from":"user","text":"この PR を要約して"},'
             '{"from":"ai","text":"変更は 3 点です。…","side":"left"}]}'),
    "funnel": (fig_funnel, "漏斗（段が上から順に現れ値が数え上がる。幅は値に比例・最小幅あり、右に前段からの割合）",
               '{"type":"funnel","unit":"件","ratio":true,"highlight":null,'
               '"items":[{"label":"訪問","value":12000},{"label":"登録","value":3400},{"label":"購入","value":820}]}'),
    "venn": (fig_venn, "2〜3 円のベン図（円が順に弾んで現れ、重なりのラベルは最後）",
             '{"type":"venn","sets":[{"label":"Web","items":["画面","ルーティング"]},{"label":"CLI","items":["引数","終了コード"]}],'
             '"overlap":"共通の設定ファイル"}'),
    "matrix": (fig_matrix, "2×2 マトリクス（軸が描かれ、象限の名前、点が順に弾む。quadrants は 左上・右上・左下・右下 の順、x/y は 0〜1）",
               '{"type":"matrix","x":["低","高"],"y":["低","高"],"xlabel":"効果","ylabel":"工数",'
               '"quadrants":["後回し","大きな賭け","保留","すぐやる"],"items":[{"label":"案A","x":0.8,"y":0.3,"pulse":false}]}'),
    "timeline": (fig_timeline, "年表・マイルストーン（横。軸が伸び、点と文字が上下交互に順に現れる。highlight は明滅）",
                 '{"type":"timeline","items":[{"date":"2024","label":"試作","sub":"社内のみ"},'
                 '{"date":"2025","label":"公開","highlight":true}]}'),
    "org": (fig_org, "組織図・階層（上から下の木。段ごとに現れ、親子の線が描かれる。葉が多いと間隔を詰め、それでも収まらなければ葉を縦に積む。max_width で幅の上限）",
            '{"type":"org","max_width":900,"root":{"label":"CTO","sub":"技術","children":['
            '{"label":"基盤","children":[{"label":"SRE"}]},{"label":"製品","pulse":false}]}}'),
    "waffle": (fig_waffle, "割合を 100 マスで（色の塊ごとにマスが順に弾む。percent=false で値を表示）",
               '{"type":"waffle","cells":100,"cols":10,"items":[{"label":"自動","value":62},{"label":"手動","value":38}]}'),
    "bullet": (fig_bullet, "目標に対する実績（背景の帯が良し悪しの区切り、棒が伸び、目標の線が落ちる）",
               '{"type":"bullet","unit":"件","items":[{"label":"月間の件数","value":820,"target":1000,"ranges":[500,800,1200]}]}'),
    "slope": (fig_slope, "2 時点の変化（左右の軸の間を線が描かれる。highlight で 1 本を強調）",
              '{"type":"slope","labels":["2025","2026"],"unit":"%","highlight":0,"items":[{"label":"A","from":32,"to":58}]}'),
    "dumbbell": (fig_dumbbell, "前後の差（前の点→後の点へ線が伸び、差が付く。増えれば緑・減れば赤）",
                 '{"type":"dumbbell","labels":["導入前","導入後"],"unit":"分","items":[{"label":"レビュー","from":45,"to":12}]}'),
    "sparks": (fig_sparks, "小さな推移のタイル（各指標の線が描かれ、最新の値が数え上がる。lower_is_better で色を反転）",
               '{"type":"sparks","cols":3,"items":[{"label":"応答","values":[320,280,240,190],"unit":"ms","lower_is_better":true}]}'),
    "radial": (fig_radial, "同心円の進み具合（輪が外から順に描かれる。max 既定 100）",
               '{"type":"radial","unit":"%","center":"達成率","items":[{"label":"設計","value":90},{"label":"実装","value":65}]}'),
    "sankey": (fig_sankey, "流れの配分（左の項目から右の項目へ、値に比例した帯が拭われるように現れる。2 段まで）",
               '{"type":"sankey","unit":"件","links":[{"from":"Web","to":"登録","value":320},{"from":"Web","to":"離脱","value":180}]}'),
    "heatmap": (fig_heatmap, "表の濃淡（行ごとに升目が弾む。値が大きいほど濃い）",
                '{"type":"heatmap","rows":["月","火"],"cols":["9時","12時","15時"],"values":[[3,8,5],[2,9,4]]}'),
    "radar": (fig_radar, "レーダー（網が張られ、系列の多角形が中心から広がる。点に触れると値）",
              '{"type":"radar","axes":["速さ","安さ","安全","使いやすさ","拡張"],"max":10,"series":[{"name":"新","values":[9,7,8,9,8]},{"name":"旧","values":[5,6,7,4,5]}]}'),
    "treemap": (fig_treemap, "ツリーマップ（値に比例した面が大きい順に弾む。触れると値）",
                '{"type":"treemap","unit":"件","items":[{"label":"Web","value":420},{"label":"アプリ","value":260},{"label":"店舗","value":120}]}'),
    "mindmap": (fig_mindmap, "マインドマップ（中心から枝が左右に描かれ、子が順に現れる）",
                '{"type":"mindmap","center":"新サービス","branches":[{"label":"対象","children":["学生","社会人"]},{"label":"価格","children":["月額","年額"]}]}'),
    "scatter": (fig_scatter, "散布図（点が弾み、trend で傾向の線。size で点の大きさ、group で色。触れると値）",
                '{"type":"scatter","xlabel":"工数","ylabel":"効果","trend":true,"items":[{"label":"A","x":2,"y":8},{"label":"B","x":6,"y":5,"size":3}]}'),
    "stacked": (fig_stacked, "積み上げ棒（系列ごとに下から伸び、合計が数え上がる。percent で 100% 積み上げ）",
                '{"type":"stacked","unit":"億","labels":["Q1","Q2","Q3"],"series":[{"name":"国内","values":[30,40,55]},{"name":"海外","values":[10,18,30]}]}'),
    "pyramid": (fig_pyramid, "ピラミッド（上から書き、下の段から積み上がる。基盤→頂点）",
                '{"type":"pyramid","items":[{"label":"ビジョン"},{"label":"戦略","sub":"3 年"},{"label":"施策"},{"label":"日々の運用"}]}'),
}


def render_svg(spec, fid):
    t = spec.get("type")
    if t not in TYPES or TYPES[t][0] is None:
        raise SystemExit("figkit: 不明な type: %r（--list で一覧）" % t)
    cv = Canvas(fid)
    W, H = TYPES[t][0](spec, cv)
    W, H = math.ceil(W), math.ceil(H)
    aria = spec.get("aria") or spec.get("caption") or TYPES[t][1]
    svg = ('<svg viewBox="0 0 %d %d" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg" '
           'style="max-width:%dpx;width:100%%;height:auto;font-family:var(--font)">%s%s</svg>'
           % (W, H, esc(aria), W, cv.defs(), "".join(cv.parts)))
    return svg, cv.fig


def render(spec, n=0):
    t = spec.get("type")
    fid = re.sub(r"[^\w-]", "-", spec.get("id") or spec.get("replace") or "figkit-%d" % n)
    figattr = {}
    if t in INTERACTIVE:
        body = render_interactive(spec, fid)
        figattr = {"motion": "none", "interactive": t}
    elif t == "toggle":
        labels = spec.get("labels") or ["変更前", "変更後"]
        parts = []
        for k, sub in enumerate(spec["states"]):
            svg, fa = render_svg(sub, "%s-s%d" % (fid, k))
            figattr.update(fa)
            lab = labels[k] if k < len(labels) else "状態 %d" % (k + 1)
            parts.append('<div class="mo-state" data-state="%s"><div class="mo-state-label">%s</div>%s</div>'
                         % (esc(lab), esc(lab), svg))
        body = '<div class="mo-states">%s</div>' % "".join(parts)
        figattr["toggle"] = True
        if spec.get("auto"):
            figattr["toggle-auto"] = True
    else:
        if t not in TYPES:
            raise SystemExit("figkit: 不明な type: %r（--list で一覧）" % t)
        body, figattr = render_svg(spec, fid)
        if t in BASE_TYPES:
            figattr["stage-base"] = "0"
    m = spec.get("motion")
    if t in INTERACTIVE:
        m = None     # 触れる図は登場の動きをかけない（data-motion="none" を figattr で付ける）
    attrs = ""
    if m is True or m == "steps":
        attrs += ' data-motion="steps"'
    elif m in ("auto", "none"):
        attrs += ' data-motion="%s"' % m
    for k, a in (("tempo", "tempo"), ("trigger", "trigger"), ("intro", "intro"), ("style", "motion-style"), ("dir", "motion-dir")):
        if spec.get(k):
            attrs += ' data-%s="%s"' % (a, esc(spec[k]))
    for k, v in figattr.items():
        attrs += (' data-%s' % k) if v is True else ' data-%s="%s"' % (k, esc(v))
    cap = ('<figcaption style="color:var(--muted);font-size:13px;margin-top:10px">%s</figcaption>'
           % esc(spec["caption"])) if spec.get("caption") else ""
    return '<figure class="mermaid-fig figkit figkit-%s" id="%s"%s>%s%s</figure>' % (t, fid, attrs, body, cap)


# ──────────────────────────────────────────────────────────────────────────
# HTML への差し込み
# ──────────────────────────────────────────────────────────────────────────
def _element_span(doc, start, tagname):
    """doc[start] が <tagname ...> の開始タグのとき、対応する閉じタグの終わりまでの範囲を返す。"""
    pat = re.compile(r"<(/?)%s\b[^>]*>" % tagname)
    depth = 0
    for m in pat.finditer(doc, start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start, m.end()
    raise SystemExit("figkit: <%s> の閉じタグが見つかりません" % tagname)


def insert(doc, spec, fig):
    if spec.get("replace"):
        m = re.search(r'<figure\b[^>]*\bid="%s"' % re.escape(spec["replace"]), doc)
        if not m:
            raise SystemExit("figkit: id=%s の figure が見つかりません" % spec["replace"])
        a, b = _element_span(doc, m.start(), "figure")
        return doc[:a] + fig + doc[b:]
    if spec.get("slot"):
        m = re.search(r'<div class="auto-fig-slot" data-section="%s">' % re.escape(spec["slot"]), doc)
        if not m:
            raise SystemExit("figkit: data-section=%s のスロットが見つかりません" % spec["slot"])
        a, b = _element_span(doc, m.start(), "div")
        close = b - len("</div>")
        return doc[:close] + fig + doc[close:]
    if spec.get("placeholder"):
        ph = "<!--FIGKIT:%s-->" % spec["placeholder"]
        if ph not in doc:
            raise SystemExit("figkit: %s が見つかりません" % ph)
        return doc.replace(ph, fig, 1)
    raise SystemExit("figkit: --insert には各図の slot / replace / placeholder のどれかが要ります")


def load_specs(path):
    data = json.load(open(path, encoding="utf-8")) if path != "-" else json.load(sys.stdin)
    if isinstance(data, dict) and "figures" in data:
        data = data["figures"]
    return data if isinstance(data, list) else [data]


def main():
    ap = argparse.ArgumentParser(description="md-to-doc の説明図を JSON の仕様から作る")
    ap.add_argument("spec", nargs="?", help="仕様の JSON（- で標準入力）")
    ap.add_argument("--insert", metavar="OUT.html", help="出力 HTML に差し込む（各図の slot / replace / placeholder）")
    ap.add_argument("--list", action="store_true", help="図の種類と仕様の書き方を表示")
    args = ap.parse_args()
    if args.list or not args.spec:
        print("figkit の図の種類（共通: id / caption / aria / motion / tempo / trigger / style / intro / dir / slot|replace|placeholder）")
        print("項目の共通注釈: note（注記の吹き出し）/ note_pos / changed（toggle で変わった所）")
        print("flow: edges[].paths（経路の名前の配列）でシナリオの切り替え、zoom（寄るノード id の順）、hover（既定: 4 ノード以上）")
        print("hub: zoom（寄る項目の label の順）、hover（既定: 4 項目以上）")
        for k, (_, desc, ex) in TYPES.items():
            print("\n[%s] %s\n  %s" % (k, desc, ex))
        print("\n# 触れる図（md-to-doc の文書の中で操作できる。印刷・JS 無しでは全部の状態を並べる）")
        for k, desc in INTERACTIVE.items():
            print("\n[%s] %s\n  %s" % (k, desc, INTERACTIVE_EX[k]))
        print("\n# 図の項目の共通: detail（触れる・押すと説明のカード。radar・treemap・scatter・stacked は値を自動で出す）")
        return
    specs = load_specs(args.spec)
    figs = [render(s, i) for i, s in enumerate(specs)]
    if not args.insert:
        print("\n".join(figs))
        return
    doc = open(args.insert, encoding="utf-8").read()
    for s, f in zip(specs, figs):
        doc = insert(doc, s, f)
    open(args.insert, "w", encoding="utf-8").write(doc)
    for s in specs:
        print("OK : %s -> %s" % (s.get("type"), s.get("replace") or s.get("slot") or s.get("placeholder")))


if __name__ == "__main__":
    main()
