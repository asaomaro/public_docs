#!/usr/bin/env python3
"""立ち絵をパーツに分けて持つ（sprite.json と sprite/ の画像）。再生のときに、体の絵の上に表情・まばたき・口のパーツを重ねる。

  python3 sprite.py chars/zundamon_png --out chars/zundamon     # 表情ごとの PNG（<表情>[@<ポーズ>][_open|_half|_blink].png）からパーツを作る
  python3 sprite.py chars/zundamon --check                      # パーツを重ね直して、元の絵と同じになるか確かめる（--from 元の PNG のフォルダ）

psd_export.py・parts_export.py は、この形で書き出す（build_sprite）。表情とポーズは `smile#2`・`raise#2` のように番号を付けて、同じ名前の別の形を持てる。

仕組み: ポーズごとに「体の絵」（normal の顔・口を閉じた絵）を 1 枚持つ。表情は体の絵と違う所を囲む四角、まばたきと口はその表情の絵と違う所を
囲む四角を切り出した小さなパーツにする。同じパーツは 1 つにまとめる（ポーズが違っても顔が同じなら共有）。パーツは、その四角の中を
置き換えて描く（半透明の画素も元の絵と同じになる）。

sprite.json: {"w", "h", "poses": {"": {"base": 画像, "faces": {"smile": {"e": [画像, x, y], "open": […], "half": […], "blink": […]}}}}, "source"}
  画像は sprite/<名前>.png。描く順は 体 → e（表情）→ blink（まばたき）→ open か half（口）。
  "info": {"faces": {"smile#2": {"lv": 3, "desc": "目 ^^・口 むふ／あは"}}, "poses": {"raise": {"desc": "右腕 手を挙げる"}}} は、形ごとの説明と度合い（1 控えめ・2 ふつう・3 強め）。
"""
import argparse, glob, hashlib, io, json, os, re, sys

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
    a = ap.parse_args()
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
