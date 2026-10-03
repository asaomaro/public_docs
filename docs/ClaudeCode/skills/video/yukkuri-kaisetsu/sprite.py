#!/usr/bin/env python3
"""立ち絵をパーツに分けて持つ（sprite.json と sprite/ の画像）。再生のときに、体の絵の上に表情・まばたき・口のパーツを重ねる。

  python3 sprite.py chars/zundamon_png --out chars/zundamon     # 表情ごとの PNG（<表情>[@<ポーズ>][_open|_half|_blink].png）からパーツを作る
  python3 sprite.py chars/zundamon --check                      # パーツを重ね直して、元の絵と同じになるか確かめる（--from 元の PNG のフォルダ）
  python3 sprite.py <大きく書き出した sprite のフォルダ> --svg --out chars/zundamon/svg     # パーツを SVG（ベクトル）にする。vtracer が要る
  python3 sprite.py chars/zundamon --compare                    # PNG と SVG を並べた見本（svg/compare.html と、Chrome があれば compare.png）

psd_export.py・parts_export.py は、この形で書き出す（build_sprite）。表情とポーズは `smile#2`・`raise#2` のように番号を付けて、同じ名前の別の形を持てる。

仕組み: ポーズごとに「体の絵」（normal の顔・口を閉じた絵）を 1 枚持つ。表情は体の絵と違う所を囲む四角、まばたきと口はその表情の絵と違う所を
囲む四角を切り出した小さなパーツにする。同じパーツは 1 つにまとめる（ポーズが違っても顔が同じなら共有）。パーツは、その四角の中を
置き換えて描く（半透明の画素も元の絵と同じになる）。

sprite.json: {"w", "h", "poses": {"": {"base": 画像, "faces": {"smile": {"e": [画像, x, y], "open": […], "half": […], "blink": […]}}}}, "source"}
  画像は sprite/<名前>.png。描く順は 体 → e（表情）→ blink（まばたき）→ open か half（口）。
  "info": {"faces": {"smile#2": {"lv": 3, "desc": "目 ^^・口 むふ／あは"}}, "poses": {"raise": {"desc": "右腕 手を挙げる"}}} は、形ごとの説明と度合い（1 控えめ・2 ふつう・3 強め）。
"""
import argparse, glob, hashlib, io, json, os, re, shutil, subprocess, sys

try:
    from PIL import Image, ImageChops, ImageFilter
except ImportError:
    sys.exit("error: Pillow が要ります（pip install pillow）")

NAME_RE = re.compile(r"^(.+?)(?:@(.+?))?(?:_(open|half|blink))?$")
STATES = ("open", "half", "blink")


def _mask(a, b):
    """a と b で違う画素（少し太らせる）。違いが無ければ None。"""
    d = ImageChops.difference(a.convert("RGBa"), b.convert("RGBa"))
    m = None
    for band in d.split():
        m = band if m is None else ImageChops.lighter(m, band)
    m = m.point(lambda v: 255 if v else 0)
    if not m.getbbox():
        return None
    return m.filter(ImageFilter.MaxFilter(5))


def _bad_pixels(a, b, tol=10):
    d = ImageChops.difference(a.convert("RGBa"), b.convert("RGBa"))
    m = None
    for band in d.split():
        m = band if m is None else ImageChops.lighter(m, band)
    return sum(m.histogram()[tol + 1:])


class Writer:
    def __init__(self, out):
        self.dir = os.path.join(out, "sprite")
        os.makedirs(self.dir, exist_ok=True)
        for f in glob.glob(os.path.join(self.dir, "*.png")):
            os.remove(f)
        self.saved = {}

    def save(self, im):
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
        key = hashlib.sha1(data).hexdigest()[:12]
        if key not in self.saved:
            open(os.path.join(self.dir, key + ".png"), "wb").write(data)
            self.saved[key] = len(data)
        return key

    def part(self, a, b):
        """a の一部を置き換えると b になるパーツ [画像, x, y]（違う所を囲む四角を b から切り出す）。同じなら None。"""
        m = _mask(a, b)
        if m is None:
            return None
        box = m.getbbox()
        return [self.save(b.crop(box)), box[0], box[1]]

    def apply(self, a, p):
        """a にパーツ p を置いた絵（再生のときと同じ結果）。"""
        if not p:
            return a
        im = a.copy()
        im.paste(Image.open(os.path.join(self.dir, p[0] + ".png")).convert("RGBA"), (p[1], p[2]))
        return im


def write_sprite(out, images, source=""):
    """images: {"smile@raise_open": 画像（どれも同じ大きさの RGBA）}。sprite.json と sprite/ を書き、作った sprite（dict）を返す。"""
    tree = {}
    for name, im in images.items():
        m = NAME_RE.match(name)
        tree.setdefault(m.group(2) or "", {}).setdefault(m.group(1), {})[m.group(3) or "closed"] = im.convert("RGBA")
    if "normal" not in tree.get("", {}) or "closed" not in tree[""]["normal"]:
        sys.exit("error: normal.png（いつもの姿・口を閉じた絵）が要ります")
    wr = Writer(out)
    size = tree[""]["normal"]["closed"].size
    sp = {"w": size[0], "h": size[1], "source": source, "poses": {}}
    for pose, faces in tree.items():
        if "normal" not in faces or "closed" not in faces["normal"]:
            continue
        base = faces["normal"]["closed"]
        entry = {"base": wr.save(base), "faces": {}}
        for face, st in faces.items():
            if "closed" not in st:
                continue
            f = {}
            e = wr.part(base, st["closed"])
            if e:
                f["e"] = e
            shown = wr.apply(base, e)   # 実際に重ねた結果を元にして、まばたきと口のパーツを作る（ずれを持ち越さない）
            for k in STATES:
                if k in st:
                    p = wr.part(shown, st[k])
                    if p:
                        f[k] = p
            entry["faces"][face] = f
        sp["poses"][pose] = entry
    json.dump(sp, open(os.path.join(out, "sprite.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tree[""]["normal"]["closed"].save(os.path.join(out, "normal.png"), optimize=True)   # 見本（sprite.json があればそちらが使われる）
    return sp, sum(wr.saved.values()), len(wr.saved)


def _union(boxes):
    boxes = [b for b in boxes if b]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def build_sprite(out, render, faces, poses, source="", info=None):
    """絵を描く関数から sprite を作る。render(ポーズ, 表情, 状態) は、同じ大きさの RGBA の絵か None を返す（状態は closed・open・half・blink）。
    faces は表情の名前（normal を含む）、poses はポーズの名前（いつもの姿は ""）。
    ほかのポーズでは体の絵だけを描き、顔のパーツが置かれる四角の中がいつもの姿と同じなら、いつもの姿の顔のパーツをそのまま使う
    （手が顔にかかるポーズだけ、その表情を描き直す）。描いた絵の数も返す。"""
    states = ("closed",) + STATES
    faces = ["normal"] + [f for f in faces if f != "normal"]
    full = {f: {k: im for k in states for im in [render("", f, k)] if im is not None} for f in faces}
    n = sum(len(v) for v in full.values())
    bases = {"": full["normal"]["closed"]}
    for p in poses:
        if p:
            bases[p] = render(p, "normal", "closed")
            n += 1
    box = _union([im.getbbox() for v in full.values() for im in v.values()] + [im.getbbox() for im in bases.values()])
    crop = lambda im: im.convert("RGBA").crop(box)
    wr = Writer(out)
    sp = {"w": box[2] - box[0], "h": box[3] - box[1], "source": source, "info": info or {}, "poses": {}}   # info: 表情・体ごとの説明（desc）と度合い（lv）

    def face_entry(base, st):
        f = {}
        e = wr.part(base, st["closed"])
        if e:
            f["e"] = e
        shown = wr.apply(base, e)
        for k in STATES:
            if k in st:
                p = wr.part(shown, st[k])
                if p:
                    f[k] = p
        return f

    base0 = crop(bases[""])
    first = {"base": wr.save(base0), "faces": {f: face_entry(base0, {k: crop(im) for k, im in full[f].items()}) for f in faces}}
    sp["poses"][""] = first
    sizes = {}

    def rect(p):
        if p[0] not in sizes:
            sizes[p[0]] = Image.open(os.path.join(wr.dir, p[0] + ".png")).size
        return (p[1], p[2], p[1] + sizes[p[0]][0], p[2] + sizes[p[0]][1])

    for p in poses:
        if not p:
            continue
        base = crop(bases[p])
        entry = {"base": wr.save(base), "faces": {}}
        for f in faces:
            parts = first["faces"][f]
            if all(base.crop(rect(v)).tobytes() == base0.crop(rect(v)).tobytes() for v in parts.values()):
                entry["faces"][f] = parts   # 顔のまわりが同じ → いつもの姿のパーツを使う
            else:
                st = {k: crop(im) for k in states for im in [render(p, f, k)] if im is not None}
                n += len(st)
                entry["faces"][f] = face_entry(base, st)
        sp["poses"][p] = entry
    json.dump(sp, open(os.path.join(out, "sprite.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    base0.save(os.path.join(out, "normal.png"), optimize=True)   # 見本
    return sp, sum(wr.saved.values()), len(wr.saved), n


def compose(sp, d, pose="", face="normal", mouth=None, blink=False):
    """パーツを重ねて 1 枚の絵にする（再生のときにエンジンがするのと同じ順）。"""
    P = sp["poses"].get(pose) or sp["poses"][""]
    F = P["faces"].get(face) or P["faces"].get("normal") or {}
    load = lambda k: Image.open(os.path.join(d, "sprite", k + ".png")).convert("RGBA")
    im = load(P["base"])
    layers = [F.get("e"), F.get("blink") if blink else None, F.get(mouth) if mouth else None]
    for p in layers:
        if p:
            im.paste(load(p[0]), (p[1], p[2]))
    return im


# ──────────────────────────────────────────────────────────────────────────
# SVG（ベクトル）にする: パーツを 1 つずつ、色の塊ごとに輪郭をなぞる（vtracer）。大きく映しても輪郭が荒れない。
# エンジンは SVG を Canvas に描くので、録画（WebM）にも映る。ぼかし・グラデーションは平らな色の段になるので、元の絵と見比べてから使う。
# ──────────────────────────────────────────────────────────────────────────
# step: なぞる前に、色を 1 段がこの幅の段に分ける（ぼかし・グラデーションが、色の段として残る。分けないと、ぼかしの全体が 1 色にまとまってしまう）
DETAIL = {"fine": dict(step=12, filter_speckle=4, color_precision=8, layer_difference=0),    # 既定
          "soft": dict(step=8, filter_speckle=4, color_precision=8, layer_difference=0),     # ぼかしの段を細かく（大きくなる）
          "mid": dict(step=16, filter_speckle=8, color_precision=8, layer_difference=0)}     # 小さくしたいとき（段が粗くなる）


def _vtracer():
    try:
        import vtracer
    except ImportError:
        sys.exit("error: SVG にするには vtracer が要ります（python3 -m pip install --user vtracer）")
    return vtracer


def _trace(im, **kw):
    b = io.BytesIO()
    im.save(b, "PNG")
    o = dict(colormode="color", hierarchical="stacked", mode="spline", corner_threshold=60, max_iterations=10, splice_threshold=45,
             length_threshold=2.0, path_precision=0)   # length_threshold を大きくすると、細い輪郭線が外へはみ出して太る
    o.update(kw)
    svg = _vtracer().convert_raw_image_to_svg(b.getvalue(), img_format="png", **o)
    return re.findall(r'<path d="([^"]*)" fill="(#[0-9A-Fa-f]{6})" transform="translate\(([-\d.]+),([-\d.]+)\)"', svg)


def _paths(found, fill=True):
    out = []
    for d, color, x, y in found:
        tr = "" if float(x) == 0 and float(y) == 0 else ' transform="translate(%s,%s)"' % (x, y)
        out.append('<path d="%s"%s%s/>' % (re.sub(r"\s+", " ", d).strip(), ' fill="%s"' % color if fill else "", tr))
    return "".join(out)


def _palette(images, top=64):
    """絵に多く出てくる色（平らな塗りの色）。なぞった色をこれに寄せると、体の絵とパーツで同じ色になり、継ぎ目が出ない。"""
    count = {}
    for im in images:
        for n, c in im.convert("RGBA").getcolors(maxcolors=1 << 24) or []:
            if c[3] == 255:
                count[c[:3]] = count.get(c[:3], 0) + n
    total = sum(count.values()) or 1
    return [c for c, n in sorted(count.items(), key=lambda kv: -kv[1])[:top] if n >= total * 0.0005]


def _snap(color, pal, tol=8, step=0):
    """なぞった色を、決まった色に寄せる: まず色の段（step）の値に戻し、次に、絵に多く出てくる色（pal）が近くにあればその色にする。
    なぞる道具は、小さな塊をとなりの塊にまぜて色を平均するので、同じ所でも、なぞる範囲によって色が少しずれる。寄せておくと、体の絵とパーツで同じ色になる。"""
    c = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    if step:
        c = tuple(min(255, (v // step) * step + step // 2) for v in c)
    best = min(pal, key=lambda p: max(abs(p[0] - c[0]), abs(p[1] - c[1]), abs(p[2] - c[2]))) if pal else c
    if max(abs(best[0] - c[0]), abs(best[1] - c[1]), abs(best[2] - c[2])) <= tol:
        c = best
    return "#%02X%02X%02X" % c


def _bbox(d, x, y):
    n = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
    xs, ys = n[0::2], n[1::2]
    return min(xs) + x, min(ys) + y, max(xs) + x, max(ys) + y


def trace_svg(im, pal=(), detail="fine", rect=None, margin=48):
    """RGBA の絵 → SVG の文字列。rect（x, y, w, h）があれば、その四角の中だけを映す SVG にする（width・height は四角の大きさ）。
    四角のときは、まわり（margin）ごとなぞって、四角にかかる形だけを残す。体の絵と同じ流れで色の段ができるので、重ねたときに境目が揃う。
    半透明の縁は、不透明か透明かに分ける。透明な所は vtracer が抜く（上に透明な 1 行を足して、必ず抜かせる）。"""
    im = im.convert("RGBA")
    x0, y0, w, h = rect or (0, 0) + im.size
    cx, cy = max(0, x0 - margin), max(0, y0 - margin)
    if rect:
        im = im.crop((cx, cy, min(im.width, x0 + w + margin), min(im.height, y0 + h + margin)))
    alpha = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    head = '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="%d %d %d %d">' % (w, h, x0 - cx, y0 - cy, w, h)
    if not alpha.getbbox():
        return head + "</svg>"
    pad = 1 if alpha.getextrema()[0] == 0 else 0
    src = Image.new("RGBA", (im.width, im.height + pad), (0, 0, 0, 0))
    opt = dict(DETAIL[detail])
    step = opt.pop("step", 0)
    flat = im.convert("RGB")
    if step:   # 段に分けた後、3×3 の中央値でならす（輪郭のにじみが細い筋の形にならず、小さくなる）
        flat = flat.point(lambda v: min(255, (v // step) * step + step // 2)).filter(ImageFilter.MedianFilter(3))
    flat = flat.convert("RGBA")
    flat.putalpha(alpha)
    src.paste(flat, (0, pad))
    found = []
    for d, c, x, y in _trace(src, **opt):
        y = "%g" % (float(y) - pad)
        if rect:
            b = _bbox(d, float(x), float(y)) if re.search(r"\d", d) else None
            if not b or b[2] <= x0 - cx or b[0] >= x0 - cx + w or b[3] <= y0 - cy or b[1] >= y0 - cy + h:
                continue
        found.append((d, _snap(c, pal, step=step), x, y))
    return head + _paths(found) + "</svg>"


def vectorize(src, out, detail="fine"):
    """sprite（sprite.json と sprite/*.png）のパーツを SVG にして、out に同じ形の sprite（"svg": true）を書く。
    元の sprite は、映す大きさの 2 倍ほどで書き出したものを使う（小さい絵をなぞると、目もとなどの細かい形が崩れる）。
    表情・口・まばたきのパーツは、体の絵に重ねた絵（再生のときと同じ順）を、パーツの四角のまわりごとなぞる。"""
    sp = json.load(open(os.path.join(src, "sprite.json"), encoding="utf-8"))
    cache = {}

    def load(k):
        if k not in cache:
            cache[k] = Image.open(os.path.join(src, "sprite", k + ".png")).convert("RGBA")
        return cache[k]

    pal = _palette([load(P["base"]) for P in sp["poses"].values()])
    d = os.path.join(out, "sprite")
    os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(d, "*.svg")):
        os.remove(f)
    done, stat = {}, {"size": 0, "soft": 0}

    def write(k, svg):
        open(os.path.join(d, k + ".svg"), "w", encoding="utf-8").write(svg)
        done[k] = set(re.findall(r'fill="(#\w+)"', svg))
        stat["size"] += len(svg.encode("utf-8"))
        hist = load(k).getchannel("A").histogram()
        if sum(hist[64:192]) > 0.02 * sum(hist[1:]):
            stat["soft"] += 1

    def patch(frame, p, colors):
        im = load(p[0])
        frame = frame.copy()
        frame.paste(im, (p[1], p[2]))
        if p[0] not in done:
            write(p[0], trace_svg(frame, colors, detail, (p[1], p[2]) + im.size))
        return frame

    for P in sp["poses"].values():
        base = load(P["base"])
        if P["base"] not in done:
            write(P["base"], trace_svg(base, pal, detail))
        colors = pal
        for F in P["faces"].values():
            shown = patch(base, F["e"], colors) if F.get("e") else base
            for k in STATES:
                if F.get(k):
                    patch(shown, F[k], colors)
    sp["svg"] = True
    json.dump(sp, open(os.path.join(out, "sprite.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if stat["soft"]:
        print("warn: 半透明の所が多いパーツが %d 個あります（SVG では不透明か透明かになる。--compare で見比べる）" % stat["soft"], file=sys.stderr)
    return sp, stat["size"], len(done)


COMPARE = """<!doctype html><meta charset="utf-8"><title>PNG と SVG の見比べ</title>
<body style="margin:0;background:#8ab;font:14px sans-serif"><script>
var A = %(png)s, B = %(svg)s, SHOTS = %(shots)s, H = %(h)d;
function load(src) { return new Promise(function (ok) { var i = new Image(); i.onload = function () { ok(i); }; i.onerror = function () { ok(null); }; i.src = src; }); }
function frame(sp, dir, ext, pose, face, st, box) {
  var P = sp.poses[pose] || sp.poses[""], F = P.faces[face] || P.faces.normal || {};
  var parts = [[P.base, 0, 0], F.e, st === "blink" ? F.blink : null, st !== "blink" && st ? F[st] : null].filter(Boolean);
  return Promise.all(parts.map(function (p) { return load(dir + p[0] + ext); })).then(function (ims) {
    var full = document.createElement("canvas"); full.width = sp.w; full.height = sp.h; var g = full.getContext("2d");   /* エンジンと同じ: 絵の大きさの Canvas に、四角の中を置き換えて重ねる */
    parts.forEach(function (p, j) { if (!ims[j]) return; if (j) g.clearRect(p[1], p[2], ims[j].naturalWidth, ims[j].naturalHeight); g.drawImage(ims[j], p[1], p[2]); });
    var x = box[0] * sp.w, y = box[1] * sp.h, w = (box[2] - box[0]) * sp.w, h = (box[3] - box[1]) * sp.h;
    var c = document.createElement("canvas"); c.width = Math.round(w * H * 2 / h); c.height = H * 2; var g2 = c.getContext("2d"); g2.imageSmoothingQuality = "high";
    g2.drawImage(full, x, y, w, h, 0, 0, c.width, c.height);
    c.style.cssText = "height:" + H + "px;display:block"; return c; });
}
[["PNG", A, "../sprite/", ".png"], ["SVG", B, "sprite/", ".svg"]].reduce(function (pr, r) { return pr.then(function () {
  var row = document.createElement("div"); row.style.cssText = "display:flex;gap:2px;position:relative;margin-bottom:2px"; document.body.appendChild(row);
  var l = document.createElement("b"); l.textContent = r[0]; l.style.cssText = "position:absolute;left:4px;top:4px;background:#fff;padding:0 4px"; row.appendChild(l);
  return SHOTS.reduce(function (p2, s) { return p2.then(function () { return frame(r[1], r[2], r[3], s[0], s[1], s[2], s[3]).then(function (c) { row.appendChild(c); }); }); }, Promise.resolve()); }); }, Promise.resolve());
</script>
"""


def compare(d, shot=True, height=430):
    """chars/<id>/sprite（PNG）と chars/<id>/svg（SVG）を、同じ表情で上下に並べる。全身 1 つと、顔を大きくしたもの 4 つ。"""
    a = json.load(open(os.path.join(d, "sprite.json"), encoding="utf-8"))
    sv = os.path.join(d, "svg")
    if not os.path.isfile(os.path.join(sv, "sprite.json")):
        sys.exit("error: %s がありません（先に --svg で作る）" % os.path.join(sv, "sprite.json"))
    b = json.load(open(os.path.join(sv, "sprite.json"), encoding="utf-8"))
    P = b["poses"][""]
    sizes = lambda p: re.search(r'width="(\d+)" height="(\d+)"', open(os.path.join(sv, "sprite", p[0] + ".svg"), encoding="utf-8").read(400)).groups()
    rects = [(p[1], p[2], p[1] + int(sizes(p)[0]), p[2] + int(sizes(p)[1])) for f in P["faces"].values() for p in f.values()]
    if rects:   # 顔 = 表情・口・目のパーツが置かれる範囲に、まわりを足したもの
        x0, y0, x1, y1 = _union(rects)
        m = 0.35 * max(x1 - x0, y1 - y0)
        face = [max(0, (x0 - m) / b["w"]), max(0, (y0 - m) / b["h"]), min(1, (x1 + m) / b["w"]), min(1, (y1 + m) / b["h"])]
    else:
        face = [0, 0, 1, 1]
    names = [f for f in P["faces"] if f in a["poses"][""]["faces"]]
    pick = [n for n in ("normal", "smile", "surprised", "angry", "sad", "troubled") if n in names][:4] or names[:4]
    states = ["open", "blink", "half", "", "open", ""]
    shots = [["", "normal", "", [0, 0, 1, 1]]] + [["", f, states[i] if states[i] in P["faces"][f] or states[i] == "" else "", face] for i, f in enumerate(pick)]
    strip = lambda sp: {"w": sp["w"], "h": sp["h"], "poses": {"": sp["poses"][""]}}
    page = os.path.join(sv, "compare.html")
    open(page, "w", encoding="utf-8").write(COMPARE % {"png": json.dumps(strip(a)), "svg": json.dumps(strip(b)), "shots": json.dumps(shots), "h": height})
    print("見比べる: %s（上が PNG、下が SVG）" % page)
    chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
    if shot and chrome:
        png = os.path.join(sv, "compare.png")
        try:
            width = sum(int(height * (s[3][2] - s[3][0]) * b["w"] / ((s[3][3] - s[3][1]) * b["h"])) + 2 for s in shots)
            subprocess.run([chrome, "--headless=new", "--no-sandbox", "--allow-file-access-from-files", "--hide-scrollbars", "--window-size=%d,%d" % (width, height * 2 + 4),
                            "--virtual-time-budget=6000", "--screenshot=" + os.path.abspath(png), "file://" + os.path.abspath(page)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            print("撮った絵: %s（Read で開いて、顔の印象・継ぎ目・縁を見る）" % png)
        except Exception as e:
            print("warn: Chrome で撮れませんでした（%s）。compare.html をブラウザで開いて見る" % e, file=sys.stderr)


def svg_from(render_to, out, detail="fine"):
    """書き出し側（psd_export・parts_export）から呼ぶ: render_to(一時フォルダ) が大きい PNG の sprite を書き、それを SVG にして out/svg に置く。"""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="sprite_svg_")
    try:
        render_to(tmp)
        sp, size, n = vectorize(tmp, os.path.join(out, "svg"), detail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK : SVG のパーツ %d 個（%.1fMB。%d×%d）を %s に書き出しました。python3 sprite.py %s --compare で PNG と見比べる" % (n, size / 1e6, sp["w"], sp["h"], os.path.join(out, "svg"), out))
    return sp


def faces_poses(sp):
    return list(sp["poses"][""]["faces"]), [p for p in sp["poses"] if p]


def load_pngs(d):
    return {os.path.basename(f)[:-4]: Image.open(f).convert("RGBA") for f in sorted(glob.glob(os.path.join(d, "*.png")))}


def check(d, src):
    """sprite を重ね直して、元の PNG と比べる。違いの大きい絵の数を返す。"""
    sp = json.load(open(os.path.join(d, "sprite.json"), encoding="utf-8"))
    bad = n = 0
    for name, im in load_pngs(src).items():
        m = NAME_RE.match(name)
        face, pose, st = m.group(1), m.group(2) or "", m.group(3)
        if pose not in sp["poses"] or face not in sp["poses"][pose]["faces"]:
            continue
        got = compose(sp, d, pose, face, st if st in ("open", "half") else None, st == "blink")
        n += 1
        if _bad_pixels(got, im) > 30:
            bad += 1
            print("  違う: %s" % name)
    return n, bad


def main():
    ap = argparse.ArgumentParser(description="表情ごとの PNG から、重ねて使うパーツ（sprite.json）を作る")
    ap.add_argument("dir", help="PNG のフォルダ（--check のときは sprite.json のあるフォルダ）")
    ap.add_argument("-o", "--out", help="書き出すフォルダ")
    ap.add_argument("--check", action="store_true", help="パーツを重ね直して元の PNG と比べる")
    ap.add_argument("--from", dest="src", help="--check で比べる元の PNG のフォルダ")
    ap.add_argument("--svg", action="store_true", help="dir の sprite（sprite.json と sprite/*.png）を SVG にして --out に書く（既定は dir/svg）")
    ap.add_argument("--detail", choices=sorted(DETAIL), default="fine", help="SVG の細かさ（fine 平らな塗り・既定／soft ぼかしのある絵／mid 小さく）")
    ap.add_argument("--compare", action="store_true", help="dir の PNG の sprite と dir/svg の SVG を並べた見本を作る")
    a = ap.parse_args()
    if a.svg:
        sp, size, n = vectorize(a.dir, a.out or os.path.join(a.dir, "svg"), a.detail)
        print("OK : SVG のパーツ %d 個（%.1fMB。%d×%d）を %s に書き出しました" % (n, size / 1e6, sp["w"], sp["h"], a.out or os.path.join(a.dir, "svg")))
        return
    if a.compare:
        compare(a.dir)
        return
    if a.check:
        n, bad = check(a.dir, a.src or a.dir)
        print("OK : %d 枚を重ね直し、%d 枚が元と違いました" % (n, bad))
        sys.exit(1 if bad else 0)
    images = load_pngs(a.dir)
    src = ""
    if os.path.isfile(os.path.join(a.dir, "manifest.json")):
        src = json.load(open(os.path.join(a.dir, "manifest.json"), encoding="utf-8")).get("source", "")
    sp, size, n = write_sprite(a.out or a.dir, images, src)
    faces, poses = faces_poses(sp)
    print("OK : %d 枚の絵 → パーツ %d 個（%.1fMB）。表情 %s%s" % (len(images), n, size / 1e6, "・".join(faces), " / ポーズ " + "・".join(poses) if poses else ""))


if __name__ == "__main__":
    main()
