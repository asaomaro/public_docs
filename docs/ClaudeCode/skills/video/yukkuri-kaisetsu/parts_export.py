#!/usr/bin/env python3
"""パーツ画像のフォルダ（キャラ素材・YMM4 の「動く立ち絵」の形式）から、表情・口・目の差分を chars/<名前>/ の PNG に書き出す。

  python3 parts_export.py 素材/YMM4用 --list                  # パーツと、preset.ini の表情
  python3 parts_export.py 素材/YMM4用 --out chars/himari      # preset.ini の表情から自動で書き出す
  python3 parts_export.py 素材/れいむ --recipe recipes/reimu.json --out chars/reimu

フォルダの形: 後・体・顔・顔色・髪・口・目・眉・他 のフォルダ（この順に重ねる）に、同じ大きさの PNG が入っている。
  口パク.png（閉じた口）と 口パク.0.png・口パク.1.png…（開いていくコマ。最後がいちばん開いた口）
  目パチ.png（開いた目）と 目パチ.0.png…（閉じていくコマ。最後が閉じた目）
preset.ini があれば、その表情（立ち絵用・会話用＿喜び など）を normal・smile・angry・sad に当てる。
レシピ（JSON）: {"base": {"体": "直立", "目": "目パチ"}, "faces": {"smile": {"目": "笑い", "口": "口パク笑い"}}, "poses": {"point": {"体": "人差し指"}}}（.png は省く）
  poses はポーズ（体・腕の差分）。
書き出すのは、体の絵と、その上に重ねる表情・まばたき・口のパーツ（sprite.json と sprite/。仕組みは sprite.py）。
--png を付けると、組み合わせごとに 1 枚の PNG（<表情>[@<ポーズ>][_open|_half|_blink].png と manifest.json）で書き出す。
  コマの無いパーツは "口_open"・"口_half"・"目_blink" で、開いた口・半開きの口・閉じた目を名指しする。
"""
import argparse, json, os, re, sys

try:
    from PIL import Image, ImageChops, ImageFilter
except ImportError:
    sys.exit("error: Pillow が要ります（pip install pillow）")
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import sprite

ORDER = ["後", "体", "顔", "顔色", "髪", "口", "目", "眉", "他"]
FACE_WORDS = [("smile", "喜|笑|よろこび|ヨシ"), ("angry", "怒|不機嫌"), ("sad", "悲|泣|かなし"), ("surprised", "驚|意外"),
              ("troubled", "困|焦"), ("normal", "普通|通常")]
EXTRA = {"surprised": {"目": ["驚き", "びっくり", "見開き"]}, "troubled": {"眉": ["困り"], "口": ["口パク歪み", "への字"]}}


def read_preset(d):
    """preset.ini → [(名前, {パーツ: ファイル名})]"""
    path = os.path.join(d, "preset.ini")
    if not os.path.isfile(path):
        return []
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp932"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    secs = []
    for ln in text.splitlines():
        ln = ln.strip()
        m = re.match(r"^\[(.+)\]$", ln)
        if m:
            secs.append((m.group(1), {}))
        elif "=" in ln and secs:
            k, v = ln.split("=", 1)
            k, v = k.strip(), re.sub(r"\.png$", "", v.strip(), flags=re.I)
            if re.match(r"^.+\d$", k):   # 他1・他2 は「他」に重ねる
                secs[-1][1].setdefault(k.rstrip("0123456789"), []).append(v)
            else:
                secs[-1][1][k] = v
    return secs


def frames(d, part, stem):
    """<stem>.0.png・<stem>.1.png…（YMM4）か <stem>a.png・<stem>b.png…（キャラ素材）のコマ（順に）。"""
    fs = []
    for f in os.listdir(os.path.join(d, part)) if stem and os.path.isdir(os.path.join(d, part)) else []:
        m = re.match(r"^" + re.escape(stem) + r"(?:\.(\d+)|([a-z]))\.png$", f, re.I)
        if m:
            fs.append((int(m.group(1)) if m.group(1) else ord(m.group(2).lower()), f[:-4]))
    return [s for _, s in sorted(fs)]


def has(d, part, stem):
    return bool(stem) and os.path.isfile(os.path.join(d, part, stem + ".png"))


def auto_recipe(d):
    secs = read_preset(d)
    if not secs:
        sys.exit("error: preset.ini がありません。--recipe でレシピを渡してください")
    base = next((v for n, v in secs if re.match(r"立ち絵|通常時", n)), secs[0][1])
    faces = {}
    for name, parts in secs:
        if re.match("立ち絵", name):
            continue
        for face, words in FACE_WORDS:
            if re.search(words, name) and face not in faces:
                faces[face] = parts
                break
    faces.setdefault("normal", {})
    for face, cand in EXTRA.items():   # preset.ini に無い表情は、よくある名前のパーツがあれば足す
        if face in faces:
            continue
        got = {p: next((s for s in ss if has(d, p, s)), None) for p, ss in cand.items()}
        if any(got.values()):
            faces[face] = dict(faces["normal"], **{p: s for p, s in got.items() if s})
    return {"base": base, "faces": dict(sorted(faces.items(), key=lambda kv: kv[0] != "normal"))}


def write_manifest(out, names, rc):
    """書き出した絵の一覧（表情・ポーズ・口と目のコマ）を manifest.json に書く。"""
    faces, poses = {}, []
    for n in names:
        m = re.match(r"^(.+?)(?:@(.+?))?(?:_(open|half|blink))?$", n)
        face, pose, part = m.group(1), m.group(2), m.group(3) or "closed"
        if pose:
            if pose not in poses:
                poses.append(pose)
        else:
            faces.setdefault(face, []).append(part)
    json.dump({"source": rc.get("_comment", ""), "faces": faces, "poses": poses}, open(os.path.join(out, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def export(d, rc, out, height, png=False, rig_psd=None):
    cache, scale = {}, []

    def load(part, stem):
        key = (part, stem)
        if key not in cache:
            cache[key] = Image.open(os.path.join(d, part, stem + ".png")).convert("RGBA")
        return cache[key]

    def draw(parts):
        im = None
        for part in ORDER + [p for p in parts if p not in ORDER]:
            for stem in (parts.get(part) if isinstance(parts.get(part), list) else [parts.get(part)]):
                if not has(d, part, stem):
                    continue
                layer = load(part, stem)
                if im is None:
                    im = Image.new("RGBA", layer.size, (0, 0, 0, 0))
                if layer.size != im.size:   # 大きさの違うパーツは、中心を合わせて重ねる（YMM4 と同じ。きつねゆっくりの眉は、ほかより縦に長い）
                    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
                    canvas.paste(layer, ((im.width - layer.width) // 2, (im.height - layer.height) // 2))
                    layer = canvas
                im.alpha_composite(layer)
        if im is None:
            sys.exit("error: パーツが 1 つも見つかりません（%s）" % parts)
        if not scale:   # 最初の絵（いつもの姿の normal）の高さを height に合わせ、全部を同じ倍率にする
            b = im.getbbox()
            scale.append(height / float(b[3] - b[1]))
        return im.resize((round(im.width * scale[0]), round(im.height * scale[0])), Image.LANCZOS)

    def parts_for(pose, face, state):
        """その絵に使うパーツ {フォルダ: 名前}。作れない状態（コマが無い）は None。"""
        f, pp = rc["faces"][face], rc.get("poses", {}).get(pose, {}) if pose else {}
        if "体" in pp:   # ポーズが体を替えるときは、表情ごとの体と手（他・後）は使わない
            f = {k: v for k, v in f.items() if k not in ("体", "他", "後")}
        parts = dict(dict(rc.get("base", {}), **f), **pp)
        extra = {k: parts.pop(k) for k in ("口_open", "口_half", "目_blink") if k in parts}   # コマが無いパーツは、開いた口・閉じた目を名指しできる
        if state == "closed":
            return parts
        if state == "blink":
            eyes = frames(d, "目", parts.get("目", "")) if isinstance(parts.get("目"), str) else []
            blink = extra.get("目_blink") or (eyes[-1] if eyes else None)
            return dict(parts, 目=blink) if blink else None
        mouth = frames(d, "口", parts.get("口", "")) if isinstance(parts.get("口"), str) else []
        if state == "open":
            opened = extra.get("口_open") or (mouth[-1] if mouth else None)
            return dict(parts, 口=opened) if opened else None
        half = extra.get("口_half") or (mouth[(len(mouth) - 1) // 2] if len(mouth) >= 2 and "口_open" not in extra else None)
        return dict(parts, 口=half) if half else None

    def render(pose, face, state):
        parts = parts_for(pose, face, state)
        return draw(parts) if parts else None

    def flat(parts, body):
        """元の大きさのまま重ねた絵。body が真なら 後・体 だけ、偽ならそれより上（顔・髪・口・目・眉・他…）だけ。"""
        im = None
        for part in ORDER + [p for p in parts if p not in ORDER]:
            if (part in ("後", "体")) != body:
                continue
            for stem in (parts.get(part) if isinstance(parts.get(part), list) else [parts.get(part)]):
                if not has(d, part, stem):
                    continue
                layer = load(part, stem)
                if im is None:
                    im = Image.new("RGBA", layer.size, (0, 0, 0, 0))
                if layer.size != im.size:
                    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
                    canvas.paste(layer, ((im.width - layer.width) // 2, (im.height - layer.height) // 2))
                    layer = canvas
                im.alpha_composite(layer)
        return im

    faces, poses = list(rc["faces"]), [""] + list(rc.get("poses", {}))
    os.makedirs(out, exist_ok=True)

    def desc(parts):   # 使うパーツの名前を並べた説明（レシピの desc があればそちら）
        items = []
        for k in ORDER:
            v = parts.get(k)
            if not v:
                continue
            v = "＋".join(v) if isinstance(v, list) else v
            if k == "口" and parts.get("口_open"):
                v += "／" + parts["口_open"]
            if k == "目" and parts.get("目_blink"):
                v += "（閉じ " + parts["目_blink"] + "）"
            items.append("%s %s" % (k, v))
        return "・".join(items)

    given, lv = rc.get("desc", {}), rc.get("levels", {})
    info = {"faces": {f: {"lv": lv.get(f, 2), "desc": given.get(f) or desc(rc["faces"][f]) or "いつもの顔"} for f in faces},
            "poses": {p: {"desc": given.get(p) or desc(rc["poses"][p])} for p in poses if p}}
    what = "表情 %d・ポーズ %d" % (len(faces), len(poses) - 1)
    if png:   # 組み合わせごとに 1 枚の PNG
        images = {f + ("@" + p if p else "") + ("" if k == "closed" else "_" + k): im
                  for p in poses for f in faces for k in ("closed", "open", "half", "blink") for im in [render(p, f, k)] if im is not None}
        box = sprite._union([im.getbbox() for im in images.values()])
        for name, im in images.items():
            im.crop(box).save(os.path.join(out, name + ".png"), optimize=True)
        write_manifest(out, list(images), rc)
        print("OK : %d 枚（%s）を %s に書き出しました" % (len(images), what, os.path.abspath(out)))
    else:     # 体の絵と、重ねるパーツ（sprite.json）
        sp, size, n, drawn = sprite.build_sprite(out, render, faces, poses, rc.get("_comment", ""), info)
        print("OK : %s をパーツ %d 個（%.1fMB。描いた絵 %d 枚）にして %s に書き出しました" % (what, n, size / 1e6, drawn, os.path.abspath(out)))
        if rig_psd:
            rig(rc, out, sp, scale[0], rig_psd, parts_for, flat)


ARM_RE, HAIR_RE = r"腕|袖|手(?!前)", r"後髪|後ろ髪|髪（胴体より後）|奥のツインテ|おさげ"


def rig(rc, out, sp, k, psd_path, parts_for, flat):
    """動くパーツ（腕・後ろ髪）を足す。このフォルダの形では、腕は体の絵に描き込まれているので、同じ素材の PSD から「体の絵に使われているレイヤー」を割り出して
    （sprite.match_layers）、腕と後ろ髪のレイヤーを別のパーツにする。顔（体より上のフォルダ）は、今までどおりこのフォルダの絵を使う。
    軸（肩・頭の中心）と回す上限は、絵とレイヤーの名前から決める（sprite.rig_layers の auto・LIMITS）。レシピの rig: {"arm": 正規表現, "hair": 正規表現, "skip": [ポーズ]} で変えられる。"""
    try:
        from psd_tools import PSDImage
    except ImportError:
        sys.exit("error: --rig には psd-tools が要ります（pip install psd-tools）")
    spec = rc.get("rig") or {}
    arm_re, hair_re = spec.get("arm", ARM_RE), spec.get("hair", HAIR_RE)
    psd, wr = PSDImage.open(psd_path), sprite.Writer(out, keep=True)
    leaves = []   # [(パス, 絵を返す関数)] 下から順

    def walk(g, pre):
        for l in g:
            if l.is_group():
                walk(l, pre + l.name + "/")
            elif l.bbox[2] > l.bbox[0]:
                leaves.append((pre + l.name, l))
    walk(psd, "")

    def raster(l):
        im = l.topil()
        if im is None:
            return None
        im, c = im.convert("RGBA"), Image.new("RGBA", psd.size, (0, 0, 0, 0))
        if l.opacity < 255:
            im.putalpha(im.getchannel("A").point(lambda a: a * l.opacity // 255))
        c.alpha_composite(im, (max(0, l.bbox[0]), max(0, l.bbox[1])), (max(0, -l.bbox[0]), max(0, -l.bbox[1])))
        return c

    def owner(path):   # 腕は「腕」と付くいちばん外側の組ごと（組が無ければそのレイヤー）に 1 つのパーツ。後ろ髪はレイヤーごと
        bits = path.split("/")
        for n, b in enumerate(bits):
            if re.search(arm_re, b):
                return {"layer": "/".join(bits[:n + 1]), "kind": "arm"}
        if re.search(hair_re, path):
            return {"layer": path, "kind": "hair", "max": 1.5}
        return None

    W, H = round(psd.width * k), round(psd.height * k)
    ox, oy = sp["origin"]
    fit = lambda im: im.resize((W, H), Image.LANCZOS).crop((ox, oy, ox + sp["w"], oy + sp["h"]))
    pt = lambda x, y: (x * k - ox, y * k - oy)
    seen, done, dropped = {}, 0, []
    for pose in sp["poses"]:
        if pose in spec.get("skip", []):
            continue
        p0 = parts_for(pose, "normal", "closed")
        body, face0 = flat(p0, True), flat(p0, False)
        if body is None or face0 is None or body.size != psd.size:
            dropped.append("%s（体の絵と PSD の大きさが違う）" % (pose or "いつもの姿"))
            continue
        used = sprite.match_layers(body, [(q, (lambda l=l: raster(l))) for q, l in leaves])
        total = body.getchannel("A").point(lambda v: 255 if v > 250 else 0).histogram()[255]
        bad = sprite._bad_pixels(sprite._over([im for _, im in used], psd.size), body, 24) if used else total
        parts = []
        for q, _ in used:
            o = owner(q)
            if o and o not in parts:
                parts.append(o)
        runs = sprite.rig_runs(used, parts)
        if all(o is None for o, _ in runs):
            dropped.append("%s（腕・後ろ髪のレイヤーが無い）" % (pose or "いつもの姿"))
            continue
        if bad > total * .004:   # 割り出したレイヤーを重ねても、体の絵と少し違う（半透明の影・小さな飾りなど、割り出せないレイヤーがある）
            # 違う所を、体の絵から切り出した「補正」の層にして、動かないパーツとして上に重ねる。違う所が動くパーツ（腕・髪）にかかっているなら、動かすと崩れるのでやめる
            recon = sprite._over([im for _, im in used], psd.size)
            d = ImageChops.difference(recon.convert("RGBa"), body.convert("RGBa"))
            m = None
            for band in d.split():
                m = band if m is None else ImageChops.lighter(m, band)
            m = m.point(lambda v: 255 if v > 24 else 0).filter(ImageFilter.MaxFilter(5))
            moving = None
            for o, ls in runs:
                if o is not None:
                    al = sprite._over([im for _, im in ls], psd.size).getchannel("A").point(lambda v: 255 if v > 8 else 0)
                    moving = al if moving is None else ImageChops.lighter(moving, al)
            hit = ImageChops.multiply(m, moving).histogram()[255]
            see = ImageChops.multiply(m, ImageChops.invert(body.getchannel("A").point(lambda v: 255 if v > 250 else 0))).histogram()[255]   # 体の絵が透けている所の違いは、上に重ねても直せない
            if hit > 150 or see > m.histogram()[255] * .5 + 300:
                dropped.append("%s（体の絵を PSD のレイヤーに分けられない: %d 画素。うち動くパーツの上 %d）" % (pose or "いつもの姿", bad, hit))
                continue
            patch = body.copy()
            patch.putalpha(ImageChops.multiply(body.getchannel("A"), m))
            runs.append([None, [("補正", patch)]])
        runs.append([None, [("顔", face0)]])
        mouth = flat({"口": p0.get("口")}, False)
        mb, fig = (mouth.getbbox() if mouth else None) or face0.getbbox(), sprite._over([body, face0], psd.size).getbbox()
        fh, mx, my = fig[3] - fig[1], (mb[0] + mb[2]) / 2, (mb[1] + mb[3]) / 2
        P = sp["poses"][pose]
        P["rig"] = sprite.rig_layers(wr, runs, parts, fit, pt, len(runs) - 1, {"neck": [mx, my + fh * .06], "head": [mx, my - fh * .06], "h": fh})
        facep = lambda f, st: {kk: v for kk, v in (parts_for(pose, f, st) or {}).items() if kk not in ("後", "体")}
        bodyp = lambda f: {kk: v for kk, v in (parts_for(pose, f, "closed") or {}).items() if kk in ("後", "体")}
        ok = [f for f in P["faces"] if bodyp(f) == bodyp("normal")]   # 体の絵ごと替わる表情（手を顔に当てる など）は、rig に入れない（その表情を使う台本では、体の絵 1 枚で描く。kaisetsu.py）
        sig = json.dumps({f: facep(f, "closed") for f in ok}, ensure_ascii=False, sort_keys=True)
        if sig not in seen:   # 顔のパーツが同じポーズは、表情のパーツを使い回す
            base, rf = fit(face0), {}
            for f in ok:
                st = {st: fit(flat(pp, False)) for st in ("closed", "open", "half", "blink") for pp in [parts_for(pose, f, st)] if pp}
                rf[f] = sprite._face_entry(wr, base, st)
            seen[sig] = rf
        P["rf"] = seen[sig]
        worst = max(sprite._bad_pixels(sprite.compose_rig(sp, out, pose, f, m), sprite.compose(sp, out, pose, f, m), 24) for f in ok[:4] for m in (None, "open"))
        if worst > max(400, sp["w"] * sp["h"] * .0025):   # 輪郭の半端な画素の差（レイヤーを別々に縮めるので出る）は許す
            dropped.append("%s（重ね直した絵が違う: %d 画素）" % (pose or "いつもの姿", worst))
            for key in ("rig", "rf"):
                P.pop(key, None)
            continue
        done += 1
    json.dump(sp, open(os.path.join(out, "sprite.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK : rig を足しました（ポーズ %d のうち %d）%s" % (len(sp["poses"]), done, "。rig にしなかったポーズ: " + "、".join(dropped) if dropped else ""))


def main():
    ap = argparse.ArgumentParser(description="パーツ画像のフォルダから表情・口・目の差分を PNG に書き出す")
    ap.add_argument("dir", help="パーツのフォルダ（体・口・目 などが並ぶ場所）")
    ap.add_argument("--list", action="store_true", help="パーツと preset.ini の表情を出す")
    ap.add_argument("--recipe", help="レシピ（JSON）。無ければ preset.ini から作る")
    ap.add_argument("-o", "--out", help="書き出すフォルダ")
    ap.add_argument("--height", type=int, default=720, help="立ち絵の高さ（px。既定 720）")
    ap.add_argument("--png", action="store_true", help="パーツ（sprite.json）にせず、組み合わせごとに 1 枚の PNG で書き出す")
    ap.add_argument("--rig", metavar="PSD", help="同じ素材の PSD。腕・後ろ髪を、体の絵とは別の動くパーツにする（psd-tools が要る。仕組みは sprite.py の rig）")
    ap.add_argument("--svg", action="store_true", help="PNG のパーツに加えて、SVG（ベクトル）のパーツを <out>/svg に作る（vtracer が要る。大きく書き出してからなぞる）")
    ap.add_argument("--svg-scale", type=float, default=2, help="SVG にするときに、--height の何倍で書き出してからなぞるか（既定 2）")
    ap.add_argument("--detail", default="fine", help="SVG の細かさ（fine 平らな塗り・既定／soft ぼかしのある絵／mid 小さく）")
    a = ap.parse_args()
    if a.list:
        for part in sorted(x for x in os.listdir(a.dir) if os.path.isdir(os.path.join(a.dir, x))):
            print("[%s] %s" % (part, " ".join(sorted(f[:-4] for f in os.listdir(os.path.join(a.dir, part)) if f.lower().endswith(".png")))))
        for name, parts in read_preset(a.dir):
            print("preset %s: %s" % (name, parts))
        return
    rc = json.load(open(a.recipe, encoding="utf-8")) if a.recipe else auto_recipe(a.dir)
    export(a.dir, rc, a.out or "chars/out", a.height, a.png, a.rig)
    if a.svg:
        import sprite
        sprite.svg_from(lambda tmp: export(a.dir, rc, tmp, round(a.height * a.svg_scale)), a.out or "chars/out", a.detail)


if __name__ == "__main__":
    main()
