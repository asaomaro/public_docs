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
        tempo（slow|normal|fast）/ trigger（view|click|loop）/
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


class Canvas:
    """SVG の断片を集めて、最後に viewBox を決める。"""

    def __init__(self, fid):
        self.fid = fid
        self.parts = []

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
        cv.add('<g data-step="%d" data-effect="draw"%s><path d="%s" fill="none" stroke="var(--accent-2)" stroke-width="2"%s%s '
               'marker-end="url(#%s)"/>%s</g>' % (step, attr_travel(e), d, dash, flow, mk, lab))
    for k, i in enumerate(ids):
        x, y, w, h = pos[i]
        n = byid[i]
        a = ' data-step="%d" data-effect="pop"' % (2 * rank[i])
        if i in focus:
            a += ' data-focus="%d"' % focus[i]
        if n.get("pulse"):
            a += " data-pulse"
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
            f = ' data-focus="%d"' % i if walk else ""
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
            f = ' data-focus="%d"' % i if walk else ""
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
                   attrs=' data-step="%d" data-effect="pop"' % (2 * i)))
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
            cv.add('<g data-step="%d">%s<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="5" fill="%s" '
                   'data-effect="grow" data-grow="right"%s/>%s</g>'
                   % (i, text(lw - 12, y + BH / 2 + 5, it["label"], anchor="end"), lw, y, w, BH, acc(i), p,
                      text(lw + w + 10, y + BH / 2 + 5, disp(it), 14, "700", anchor="start", extra=' data-count="0" data-effect="fade"')))
    else:
        colw = max(64, max(tw(it["label"], 13) for it in items) + 16)
        BH, BW = 220, min(46, colw - 18)
        W, H = colw * len(items) + 20, BH + 70
        for i, it in enumerate(items):
            cx = 10 + colw * i + colw / 2
            h = max(2, BH * float(it["value"]) / vmax)
            p = " data-pulse" if hl == i else ""
            cv.add('<g data-step="%d"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="5" fill="%s" '
                   'data-effect="grow" data-grow="up"%s/>%s%s</g>'
                   % (i, cx - BW / 2, 30 + BH - h, BW, h, acc(i), p,
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
    for i, it in enumerate(items):
        ang = 2 * math.pi * i / n - math.pi / 2
        x, y = ox + R * math.cos(ang), oy + R * math.sin(ang)
        # 中心の箱の縁と、周りの箱の縁の間を結ぶ
        sx, sy = ox + (cw / 2 + 6) * math.cos(ang), oy + (ch / 2 + 6) * math.sin(ang)
        tx, ty = x - (sizes[i][0] / 2 + 6) * math.cos(ang), y - (sizes[i][1] / 2 + 6) * math.sin(ang)
        if inward:
            sx, sy, tx, ty = tx, ty, sx, sy
        e = it if isinstance(it, dict) else {}
        cv.add('<line data-step="1"%s x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--accent-2)" stroke-width="2" '
               'marker-end="url(#%s)"%s/>' % (attr_travel(e), sx, sy, tx, ty, mk, " data-flow" if e.get("flow") else ""))
        cv.add(box(x - sizes[i][0] / 2, y - sizes[i][1] / 2, sizes[i][0], sizes[i][1], it["label"], it.get("sub"), ci=i,
                   attrs=' data-step="2" data-effect="pop"'))
    cv.add(box(ox - cw / 2, oy - ch / 2, cw, ch, c["label"], c.get("sub"), kind="start",
               attrs=' data-step="0" data-effect="pop"%s' % (" data-pulse" if c.get("pulse") else "")))
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
        cv.add('<g data-step="%d" data-effect="rise"><rect x="10" y="%.1f" width="%.1f" height="%d" rx="10" fill="var(--accent-soft)" '
               'stroke="%s" stroke-width="1.6"/><rect x="10" y="%.1f" width="8" height="%d" rx="4" fill="%s"/>%s%s</g>'
               % (n - 1 - i, y, LW, LH, acc(i), y, LH, acc(i),
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
        cv.add('<g data-step="%d" data-effect="draw"%s><path d="%s" fill="none" stroke="var(--accent-2)" stroke-width="2"%s marker-end="url(#%s)"/>%s</g>'
               % (j + 1, tr, d, dash, mk, text(lx, y - 8, m.get("label", ""), 13, fill="var(--ink)", anchor=anchor)))
    return W, H


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
    "sequence": (fig_sequence, "やりとりの順序（登場者の間のメッセージ。矢印の上を印が移動）",
                 '{"type":"sequence","actors":["利用者","サーバ"],'
                 '"messages":[{"from":"利用者","to":"サーバ","label":"ログイン"},{"from":"サーバ","to":"利用者","label":"トークン","reply":true}]}'),
}


def render(spec, n=0):
    t = spec.get("type")
    if t not in TYPES:
        raise SystemExit("figkit: 不明な type: %r（--list で一覧）" % t)
    fid = re.sub(r"[^\w-]", "-", spec.get("id") or spec.get("replace") or "figkit-%d" % n)
    cv = Canvas(fid)
    W, H = TYPES[t][0](spec, cv)
    W, H = math.ceil(W), math.ceil(H)
    aria = spec.get("aria") or spec.get("caption") or TYPES[t][1]
    m = spec.get("motion")
    attrs = ""
    if m is True or m == "steps":
        attrs += ' data-motion="steps"'
    elif m in ("auto", "none"):
        attrs += ' data-motion="%s"' % m
    for k in ("tempo", "trigger"):
        if spec.get(k):
            attrs += ' data-%s="%s"' % (k, esc(spec[k]))
    cap = ('<figcaption style="color:var(--muted);font-size:13px;margin-top:10px">%s</figcaption>'
           % esc(spec["caption"])) if spec.get("caption") else ""
    svg = ('<svg viewBox="0 0 %d %d" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg" '
           'style="max-width:%dpx;width:100%%;height:auto;font-family:var(--font)">%s%s</svg>'
           % (W, H, esc(aria), W, cv.defs(), "".join(cv.parts)))
    return '<figure class="mermaid-fig figkit figkit-%s" id="%s"%s>%s%s</figure>' % (t, fid, attrs, svg, cap)


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
        print("figkit の図の種類（共通: id / caption / aria / motion / tempo / trigger / slot|replace|placeholder）")
        for k, (_, desc, ex) in TYPES.items():
            print("\n[%s] %s\n  %s" % (k, desc, ex))
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
