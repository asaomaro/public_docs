#!/usr/bin/env python3
"""立ち絵の PSD（PSDTool 形式）から、表情・口・目の差分を chars/<名前>/ の PNG に書き出す。

  python3 psd_export.py 立ち絵.psd --list                          # レイヤーの一覧（パス）
  python3 psd_export.py 立ち絵.psd --sheet "本体/!表情/!口" -o 口.png  # その組の選択肢を並べた見本（番号と名前は画面に出る）
  python3 psd_export.py 立ち絵.psd --recipe recipes/no7.json --out chars/no7

psd-tools が要る（pip install psd-tools）。PSD は同梱しない。配布元と規約は recipes/README.md と assets.md。

レシピ（JSON）:
  alias   {"口": "本体/!表情/!口", "目": ["…/右", "…/左"]}  組の別名（複数の組をまとめて切り替えられる）
  hide    消すレイヤー（背景など）      show   出すレイヤー
  base    どの絵にも当てる選択          closed・open・half  口（閉じ・開き・半開き）の選択      blink  目を閉じる選択
  faces   {"smile": {"set": […], "closed": […], "open": […], "blink": null}}  表情ごとの選択。口と blink は上書きできる（null で作らない）
  poses   {"point": ["!右腕/*指差し上"]}  ポーズ（腕の差分）
書き出すのは、体の絵と、その上に重ねる表情・まばたき・口のパーツ（sprite.json と sprite/。仕組みは sprite.py）。
--png を付けると、組み合わせごとに 1 枚の PNG（<表情>[@<ポーズ>][_open|_half|_blink].png と manifest.json）で書き出す。
選択は "口=*通常"（別名=レイヤー名。その組のほかのレイヤーは消える）か、レイヤーのパス（名前が * で始まるレイヤーは、同じ組の * のレイヤーと入れ替わる）。
"""
import argparse, json, os, re, sys

try:
    from psd_tools import PSDImage
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("error: psd-tools が要ります（pip install psd-tools）")
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import sprite


class Psd:
    def __init__(self, path):
        self.psd = PSDImage.open(path)
        self.layers = {}
        self._walk(self.psd, "")
        self.initial = {p: l.visible for p, l in self.layers.items()}

    def _walk(self, group, pre):
        for l in group:
            self.layers[pre + l.name] = l
            if l.is_group():
                self._walk(l, pre + l.name + "/")

    def reset(self):
        for p, l in self.layers.items():
            l.visible = self.initial[p]

    def select(self, path, only=False):
        """レイヤーを出す。* で始まるレイヤーは同じ組の * のレイヤーを消す（only なら同じ組のほかを全部消す）。親もたどって出す。"""
        if path not in self.layers:
            sys.exit("error: レイヤーが見つかりません: %s（--list で確かめる）" % path)
        l = self.layers[path]
        for s in l.parent:
            if only or (l.name.startswith("*") and s.name.startswith("*")):
                s.visible = False
        l.visible = True
        if "/" in path:
            self.select(path.rsplit("/", 1)[0])

    def state(self):
        return {p: l.visible for p, l in self.layers.items()}

    def box(self, paths, pad=4):
        """レイヤー（組なら中の全部）を囲む範囲。"""
        bs = [l.bbox for p, l in self.layers.items() if not l.is_group() and l.bbox[2] > l.bbox[0]
              and any(p == q or p.startswith(q + "/") for q in paths)]
        if not bs:
            return None
        return (max(0, min(b[0] for b in bs) - pad), max(0, min(b[1] for b in bs) - pad),
                min(self.psd.width, max(b[2] for b in bs) + pad), min(self.psd.height, max(b[3] for b in bs) + pad))

    def render(self, viewport=None):
        return self.psd.composite(viewport=viewport, force=True).convert("RGBA")


def expand(sel, alias):
    """ "口=*通常" →（別名の組ごとのパス, その組のほかを消す）。そのほかはパスのまま。"""
    if "=" in sel and sel.split("=", 1)[0] in alias:
        k, name = sel.split("=", 1)
        groups = alias[k] if isinstance(alias[k], list) else [alias[k]]
        return [(g.rstrip("/") + "/" + name, True) for g in groups]
    return [(sel, False)]


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


def export(p, rc, out, height, png=False):
    alias, first, scale = rc.get("alias", {}), {}, []

    def draw(sels):
        p.reset()
        for path in rc.get("hide", []):
            p.layers[path].visible = False
        for s in rc.get("show", []) + rc.get("base", []) + sels:
            for path, only in expand(s, alias):
                p.select(path, only)
        if not first:   # 最初の 1 枚は全体を描き、2 枚目からは変わったレイヤーの範囲だけ描いて貼る（速い）
            first.update(state=p.state(), image=p.render())
            im = first["image"]
        else:
            vp = p.box([q for q, v in p.state().items() if v != first["state"][q]])
            im = first["image"].copy()
            if vp:
                im.paste(p.render(vp), vp[:2])
        if not scale:   # 最初の絵（いつもの姿の normal）の高さを height に合わせ、全部を同じ倍率にする
            b = im.getbbox()
            scale.append(height / float(b[3] - b[1]))
        return im.resize((round(im.width * scale[0]), round(im.height * scale[0])), Image.LANCZOS)

    def render(pose, face, state):
        f = rc["faces"][face]
        part = lambda k: f[k] if k in f else rc.get(k)
        st = (rc.get("poses", {}).get(pose, []) if pose else []) + f.get("set", [])
        if part(state) is None:
            return None
        return draw(st + (part("closed") or []) + part("blink")) if state == "blink" else draw(st + part(state))

    faces, poses = list(rc["faces"]), [""] + list(rc.get("poses", {}))
    os.makedirs(out, exist_ok=True)

    def names(sels):   # 選んだレイヤーの名前（"目 にっこり" の形）
        out_ = []
        for s in sels or []:
            if "=" in s and s.split("=", 1)[0] in alias:
                out_.append("%s %s" % (s.split("=", 1)[0], s.split("=", 1)[1].lstrip("*!")))
            else:
                bits = [b.lstrip("*!") for b in s.split("/")]
                out_.append(" ".join(bits[-2:]) if len(bits) > 1 else bits[-1])
        return out_

    def face_desc(f):
        part = lambda k: f[k] if k in f else rc.get(k)
        mouth = [n.split(" ", 1)[-1] for k in ("closed", "open") for n in names(part(k))]
        return "・".join(names(f.get("set")) + (["口 " + "／".join(mouth)] if mouth else []))

    given, lv = rc.get("desc", {}), rc.get("levels", {})
    info = {"faces": {f: {"lv": lv.get(f, 2), "desc": given.get(f) or face_desc(rc["faces"][f])} for f in faces},
            "poses": {q: {"desc": given.get(q) or "・".join(names(rc["poses"][q]))} for q in poses if q}}
    what = "表情 %d・ポーズ %d" % (len(faces), len(poses) - 1)
    if png:   # 組み合わせごとに 1 枚の PNG
        images = {f + ("@" + q if q else "") + ("" if k == "closed" else "_" + k): im
                  for q in poses for f in faces for k in ("closed", "open", "half", "blink") for im in [render(q, f, k)] if im is not None}
        box = sprite._union([im.getbbox() for im in images.values()])
        for name, im in images.items():
            im.crop(box).save(os.path.join(out, name + ".png"), optimize=True)
        write_manifest(out, list(images), rc)
        print("OK : %d 枚（%s）を %s に書き出しました" % (len(images), what, os.path.abspath(out)))
    else:     # 体の絵と、重ねるパーツ（sprite.json）
        sp, size, n, drawn = sprite.build_sprite(out, render, faces, poses, rc.get("_comment", ""), info)
        print("OK : %s をパーツ %d 個（%.1fMB。描いた絵 %d 枚）にして %s に書き出しました" % (what, n, size / 1e6, drawn, os.path.abspath(out)))


def sheet(p, group, out, hide):
    """組の選択肢を 1 つずつ出した絵を並べる（顔のまわりを切り出す）。"""
    g = p.layers.get(group.rstrip("/"))
    if g is None or not g.is_group():
        sys.exit("error: 組が見つかりません: %s" % group)
    group = group.rstrip("/")
    names = [l.name for l in g]
    x0, y0, x1, y1 = p.box([group], 0)
    m = max(x1 - x0, y1 - y0)
    box = (max(0, x0 - m), max(0, y0 - m), min(p.psd.width, x1 + m), min(p.psd.height, y1 + m))
    tiles = []
    for n in names:
        p.reset()
        for path in hide:
            p.layers[path].visible = False
        p.select(group + "/" + n, True)
        tiles.append(p.render(box))
    tw = 280
    th = round(tw * (box[3] - box[1]) / (box[2] - box[0]))
    cols = min(5, len(tiles))
    img = Image.new("RGB", (tw * cols, (th + 18) * -(-len(tiles) // cols)), "white")
    d = ImageDraw.Draw(img)
    for i, t in enumerate(tiles):
        t = t.resize((tw, th), Image.LANCZOS)
        x, y = (i % cols) * tw, (i // cols) * (th + 18)
        img.paste(t, (x, y + 18), t)
        d.text((x + 4, y + 3), str(i), fill="black")
        print("  %2d  %s" % (i, names[i]))
    img.save(out)
    print("OK : %s" % out)


def main():
    ap = argparse.ArgumentParser(description="立ち絵の PSD から表情・口・目の差分を PNG に書き出す")
    ap.add_argument("psd")
    ap.add_argument("--list", action="store_true", help="レイヤーの一覧を出す")
    ap.add_argument("--sheet", help="この組の選択肢を並べた見本を作る")
    ap.add_argument("--recipe", help="レシピ（JSON）")
    ap.add_argument("-o", "--out", help="書き出す場所（--recipe: フォルダ、--sheet: PNG）")
    ap.add_argument("--height", type=int, default=720, help="立ち絵の高さ（px。既定 720）")
    ap.add_argument("--png", action="store_true", help="パーツ（sprite.json）にせず、組み合わせごとに 1 枚の PNG で書き出す")
    ap.add_argument("--svg", action="store_true", help="PNG のパーツに加えて、SVG（ベクトル）のパーツを <out>/svg に作る（vtracer が要る。大きく書き出してからなぞる）")
    ap.add_argument("--svg-scale", type=float, default=2, help="SVG にするときに、--height の何倍で書き出してからなぞるか（既定 2）")
    ap.add_argument("--detail", default="fine", help="SVG の細かさ（fine 平らな塗り・既定／soft ぼかしのある絵／mid 小さく）")
    a = ap.parse_args()
    p = Psd(a.psd)
    rc = json.load(open(a.recipe, encoding="utf-8")) if a.recipe else {}
    if a.list:
        for path, l in p.layers.items():
            print("%s%s%s" % ("  " * path.count("/"), l.name, "" if l.visible else "  （非表示）"))
    elif a.sheet:
        sheet(p, a.sheet, a.out or "sheet.png", rc.get("hide", []))
    elif a.recipe:
        export(p, rc, a.out or "chars/out", a.height, a.png)
        if a.svg:
            import sprite
            sprite.svg_from(lambda tmp: export(p, rc, tmp, round(a.height * a.svg_scale)), a.out or "chars/out", a.detail)
    else:
        ap.error("--list・--sheet・--recipe のどれかを付ける")


if __name__ == "__main__":
    main()
