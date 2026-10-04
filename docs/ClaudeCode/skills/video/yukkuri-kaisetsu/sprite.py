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
    def __init__(self, out, keep=False):
        self.dir = os.path.join(out, "sprite")
        os.makedirs(self.dir, exist_ok=True)
        for f in glob.glob(os.path.join(self.dir, "*.png")):
            if not keep:   # keep: 書き出し済みのパーツに足す（rig）
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

    face_entry = lambda base, st: _face_entry(wr, base, st)

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
    sp["origin"] = [box[0], box[1]]   # 描いた絵のどこを切り出したか（rig のパーツを同じ位置に切り出すのに使う）
    json.dump(sp, open(os.path.join(out, "sprite.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    base0.save(os.path.join(out, "normal.png"), optimize=True)   # 見本
    return sp, sum(wr.saved.values()), len(wr.saved), n


# ──────────────────────────────────────────────────────────────────────────
# rig: 腕・髪・黒目を、体の絵とは別のパーツで持ち、再生のときに動かす（腕と髪は軸のまわりに回し、黒目は白目の中でずらす）。
# sprite.json の poses.<ポーズ> に足す（base と faces はそのまま残るので、rig を知らない道具は今までどおり使える）:
#   "rig":  [{"i": 画像, "x", "y"}, {…, "k": "arm"・"hair", "p": [軸 x, y], "m": 回す角度の上限（度）, "s": 外向きが時計回りなら 1・逆なら -1}, {…, "f": 1}, …]   下から重ねる順
#           "f": 1 は顔の層（目・口・眉・前髪など）。表情のパーツ "rf" と黒目 "iris" は、この層の中を置き換える（下の体・腕・後ろ髪には触らないので、それらが動いても崩れない）
#   "rf":   {"表情": {"e": […], "open": […], "half": […], "blink": […]}}   faces と同じ形。顔の層に当てるパーツ
#   "iris": {"表情": {"x", "y", "w", "h", "u": 黒目より下の絵, "i": 黒目, "m": 白目（この形の中にだけ黒目を描く）, "o": 黒目より上の絵, "d": ずらす量の上限（px）}}
# ──────────────────────────────────────────────────────────────────────────
def _over(images, size):
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    for im in images:
        out.alpha_composite(im)
    return out


def _piece(wr, im):
    """絵を、中身のある範囲で切り出して保存する → (画像, x, y)。空なら None。"""
    box = im.getbbox()
    if not box:
        return None
    return wr.save(im.crop(box)), box[0], box[1]


def _face_entry(wr, base, st):
    """表情のパーツ: base の一部を置き換えると st["closed"] になるパーツ e と、そこからのまばたき・口のパーツ。"""
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


def rig_runs(leaves, parts):
    """leaves: [(パス, 絵)] 下から順。parts: [{"layer": パス（組なら中の全部）, "kind", "pivot": [x, y], "max": 度, "side", "still": [この言葉を含むレイヤーは動かさない], "limit": {言葉: 度}}]。
    → [[パーツの番号か None, [(パス, 絵)]]]（同じパーツのレイヤーが続く間と、動かないレイヤーが続く間を、それぞれ 1 つに）。"""
    def owner(path):
        for i, q in enumerate(parts):
            if path == q["layer"] or path.startswith(q["layer"].rstrip("/") + "/"):
                return None if any(w in path for w in q.get("still", [])) else i
        return None

    runs = []
    for path, im in leaves:
        o = owner(path)
        if runs and runs[-1][0] == o:
            runs[-1][1].append((path, im))
        else:
            runs.append([o, [(path, im)]])
    return runs


# 回す角度の上限の既定（レシピの limit が無いとき。レイヤーの名前で決める）: 手が体・顔・物に触れている腕は小さく、上げた腕・指さす腕は中くらい
LIMITS = [(r"腰|組|口|顔|頬|ほっぺ|胸|頭|合わせ|あご|ひそ|抱|ポケ|持|スマホ|マイク|剣|弓|パッド|構|かまえ|こつん|チョップ|電話|説明|本|杖|傘", 1.5),
          (r"指差|指さ|ゆびさ|ピース|挙|上げ|あげ|万歳|かざ|差し出|横|一番|ひろげ|開", 4)]


def auto_pivot(im, anchor, radius):
    """軸の位置を絵から決める: anchor（首のあたり）にいちばん近い画素のまわり（radius の中）の、画素の重心。腕なら肩、垂れた髪なら根元になる。"""
    box = im.getbbox()
    if not box:
        return list(anchor)
    k = 4
    a = im.getchannel("A").crop(box).resize((max(1, (box[2] - box[0]) // k), max(1, (box[3] - box[1]) // k)), Image.BOX)
    w, px = a.width, a.tobytes()
    pts = [(box[0] + (i % w + .5) * k, box[1] + (i // w + .5) * k) for i, v in enumerate(px) if v > 128]
    if not pts:
        return list(anchor)
    near = min(pts, key=lambda q: (q[0] - anchor[0]) ** 2 + (q[1] - anchor[1]) ** 2)
    close = [q for q in pts if (q[0] - near[0]) ** 2 + (q[1] - near[1]) ** 2 <= radius ** 2]
    return [sum(q[0] for q in close) / len(close), sum(q[1] for q in close) / len(close)]


def rig_layers(wr, runs, parts, fit, pt, face_run, auto=None):
    """runs を rig の層の一覧にする。face_run は顔の層にする run の番号。
    auto: {"neck": [x, y], "head": [x, y], "h": 立ち絵の高さ}（元の絵の座標）を渡すと、pivot の無いパーツの軸を絵から決め（腕は首に近い端 = 肩、髪は頭の中心）、side も決める。"""
    out = []
    for n, (o, ls) in enumerate(runs):
        flat = _over([im for _, im in ls], ls[0][1].size)
        pc = _piece(wr, fit(flat))
        if not pc:
            continue
        L = {"i": pc[0], "x": pc[1], "y": pc[2]}
        if o is not None:
            q = parts[o]
            kind, pivot, side = q.get("kind", "hair"), q.get("pivot"), q.get("side")
            if auto and not pivot:
                pivot = auto_pivot(flat, auto["neck"], auto["h"] * .03) if kind == "arm" else list(auto["head"])
            if auto and not side and kind == "arm":
                side = "left" if pivot[0] < auto["neck"][0] else "right"
            x, y = pt(*pivot)
            names = " ".join(path for path, _ in ls)
            lim = [v for w, v in q.get("limit", {}).items() if w in names]   # limit: {"マイク": 2} その形のときだけ、回す上限を小さく
            if not lim and "limit" not in q and kind == "arm":
                lim = [v for rx, v in LIMITS if re.search(rx, names.split("/")[-1])][:1]
            L.update(k=kind, p=[round(x, 1), round(y, 1)], m=min(lim + [q.get("max", 7 if kind == "arm" else 2)]), s=-1 if side == "right" else 1)
        elif n == face_run:
            L["f"] = 1
        out.append(L)
    return out


def match_layers(target, leaves, tol=14, need=.9):
    """1 枚に重ねた絵 target が、どのレイヤーを重ねたものかを割り出す。leaves: [(パス, 絵)] 下から順（target と同じ大きさ）。上のレイヤーから見て、
    まだ隠れていない不透明な画素が target と同じ色なら、そのレイヤーが使われている。→ 使われているレイヤー [(パス, 絵)]（下から順）。"""
    covered = Image.new("L", target.size, 0)
    t_rgb, t_a = target.convert("RGB"), target.getchannel("A").point(lambda v: 255 if v > 250 else 0)
    used = []
    for path, im in reversed(leaves):
        im = im() if callable(im) else im   # 絵を返す関数でもよい（レイヤーが多い PSD で、全部を一度に持たない）
        if im is None:
            continue
        box = im.getbbox()
        if not box:
            continue
        opaque = im.getchannel("A").crop(box).point(lambda v: 255 if v > 250 else 0)
        free = ImageChops.subtract(opaque, covered.crop(box))
        n = free.histogram()[255]
        if n < 40:
            continue
        d = ImageChops.difference(im.convert("RGB").crop(box), t_rgb.crop(box))
        worst = None
        for band in d.split():
            worst = band if worst is None else ImageChops.lighter(worst, band)
        good = ImageChops.multiply(ImageChops.multiply(worst.point(lambda v: 255 if v <= tol else 0), t_a.crop(box)), free)
        if good.histogram()[255] >= need * n:
            used.append((path, im))
            covered.paste(ImageChops.lighter(covered.crop(box), opaque), box[:2])
    return used[::-1]


def build_iris(wr, leaves, spec, fit, k):
    """黒目のパーツ。leaves は顔の層のレイヤー。spec: {"layer": 黒目のレイヤー（組なら中の全部）, "white": [白目のレイヤー, …], "max": ずらす量の上限（元の絵の px）}。k は縮める倍率。
    黒目か白目が出ていない表情（閉じた目・＞＜ など）は None。"""
    lay = spec["layer"].rstrip("/")
    idx = [n for n, (path, _) in enumerate(leaves) if path == lay or path.startswith(lay + "/")]
    white = [im for path, im in leaves if any(path == w or path.startswith(w.rstrip("/") + "/") for w in spec.get("white", []))]
    if not idx or not white:
        return None
    size = leaves[0][1].size
    iris = fit(_over([leaves[n][1] for n in idx], size))
    box, d = iris.getbbox(), max(1, int(round(spec.get("max", 6) * k)))
    if not box:
        return None
    box = (max(0, box[0] - d - 2), max(0, box[1] - d - 2), min(iris.width, box[2] + d + 2), min(iris.height, box[3] + d + 2))
    cut = lambda ims: wr.save(fit(_over(ims, size)).crop(box))
    return {"x": box[0], "y": box[1], "w": box[2] - box[0], "h": box[3] - box[1], "d": d,
            "u": cut([im for _, im in leaves[:idx[0]]]), "i": wr.save(iris.crop(box)), "m": cut(white), "o": cut([im for _, im in leaves[idx[-1] + 1:]])}


def compose_rig(sp, d, pose="", face="normal", mouth=None, blink=False, angles=None, shift=(0, 0)):
    """rig のパーツを重ねた絵（エンジンと同じ順。確かめる用）。angles: {層の番号: 度}（時計回りが正）。shift: 黒目をずらす量。"""
    P = sp["poses"][pose]
    load = lambda k: Image.open(os.path.join(d, "sprite", k + ".png")).convert("RGBA")
    out = Image.new("RGBA", (sp["w"], sp["h"]), (0, 0, 0, 0))
    for n, L in enumerate(P["rig"]):
        c = Image.new("RGBA", out.size, (0, 0, 0, 0))
        c.paste(load(L["i"]), (L["x"], L["y"]))
        if L.get("f"):
            F = P["rf"].get(face) or P["rf"].get("normal") or {}
            if F.get("e"):
                c.paste(load(F["e"][0]), (F["e"][1], F["e"][2]))
            v = P.get("iris", {}).get(face)
            if v and not (blink and F.get("blink")):
                ir = Image.new("RGBA", (v["w"], v["h"]), (0, 0, 0, 0))
                ir.paste(load(v["i"]), (int(shift[0]), int(shift[1])))
                ir.putalpha(ImageChops.multiply(ir.getchannel("A"), load(v["m"]).getchannel("A")))
                cell = load(v["u"])
                cell.alpha_composite(ir)
                cell.alpha_composite(load(v["o"]))
                c.paste(cell, (v["x"], v["y"]))
            for q in (F.get("blink") if blink else None, F.get(mouth) if mouth else None):
                if q:
                    c.paste(load(q[0]), (q[1], q[2]))
        elif L.get("k") and (angles or {}).get(n):
            c = c.rotate(-angles[n], resample=Image.BICUBIC, center=tuple(L["p"]))
        out.alpha_composite(c)
    return out


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
