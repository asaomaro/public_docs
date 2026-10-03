#!/usr/bin/env python3
"""掛け合いの解説動画の、公開まわりを作る: 概要欄（目次・出典・クレジット）とサムネイル。

  python3 publish.py 台本.txt                 # <台本名>.description.txt と <台本名>.thumbnail.png
  python3 publish.py 台本.txt --no-thumb      # 概要欄だけ
  python3 publish.py 台本.txt --check         # 題の長さ・クレジットの抜けなどを見るだけ

先に yukkuri-kaisetsu で動画を作っておく（<台本名>.info.json に、章の時刻とクレジットが入る）。
台本の先頭に書ける項目: summary（概要欄の最初の 1〜2 文）・tags（, 区切り）・thumb（サムネイルの文字。| で改行、最大 3 行）・
thumb_faces（zundamon=surprised+, metan=smug）・thumb_bg（背景の名前か画像）・thumb_font（fonts.json の名前。既定 dela）
"""
import argparse, importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.realpath(__file__))
KDIR = os.path.join(HERE, "..", "yukkuri-kaisetsu")
W, H = 1280, 720
COLORS = [(255, 230, 0), (255, 255, 255), (255, 80, 70)]   # 行ごとの文字の色（黄・白・赤）。縁は黒、外に白


def load(name, file):
    path = os.path.join(KDIR, file)
    if not os.path.isfile(path):
        sys.exit("error: yukkuri-kaisetsu スキルが見つかりません（%s）" % path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sources(base, meta, stem):
    """事実の一覧（facts.md）の「## 出典」の行。無ければ、事実の行にある URL。"""
    fp = os.path.join(base, meta["facts"]) if meta.get("facts") else stem + ".facts.md"
    if not os.path.isfile(fp):
        return []
    text = open(fp, encoding="utf-8").read()
    m = re.search(r"^##\s*出典\s*\n(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    if m:
        return [re.sub(r"^\s*[-*]\s*", "", x).strip() for x in m.group(1).splitlines() if x.strip()]
    return list(dict.fromkeys(re.findall(r"https?://[^\s）)、]+", text)))


DESC_LIMIT = 5000   # YouTube の概要欄は 5000 バイトまで（かなで約 1,600 字）


def description(meta, info, src, limit=DESC_LIMIT):
    """概要欄と、収まらずに外へ出した画像のクレジットの全文（外へ出さなければ None）。
    写真が多い動画は、画像のクレジット（題・作者・ライセンス・URL）だけで上限を超える。超えたら順に縮める:
    1) ライセンスの URL を外す  2) 作者とライセンスだけにまとめ、題と URL つきの全文は別のファイルに出す。"""
    imgs = info.get("images") or []

    def build(lines):
        out = []
        if meta.get("summary"):
            out += [meta["summary"], ""]
        out += ["▼目次"] + ["%s %s" % (c["at"], c["title"]) for c in info["chapters"]] + [""]
        if src:
            out += ["▼出典・参考"] + ["・" + s for s in src] + [""]
        out += ["▼クレジット"] + [c for c in info["credits"] if not c.startswith("画像:")]
        if lines:
            out += ["画像:"] + lines
        out.append("")
        if meta.get("tags"):
            out.append(" ".join("#" + t.strip().lstrip("#") for t in re.split(r"[,、]", meta["tags"]) if t.strip()))
        return "\n".join(out).rstrip() + "\n"

    full = ["・" + i["full"] for i in imgs]
    text = build(full)
    if len(text.encode("utf-8")) <= limit:
        return text, None
    mid = ["・" + ("「%s」%s／%s／%s" % (i["title"], i["author"], i["license"], i["page"]) if i.get("page") and i.get("license") and i.get("from") != "いらすとや" else i["full"]) for i in imgs]
    text = build(mid)
    if len(text.encode("utf-8")) <= limit:
        return text, None
    by = {}   # ライセンスごとに作者をまとめる
    for i in imgs:
        if i.get("from") == "いらすとや":
            by.setdefault("イラスト", []).append("いらすとや https://www.irasutoya.com/")
        else:
            by.setdefault("%s（%s）" % (i.get("license") or "ライセンス不明", i.get("from") or "出どころ不明"), []).append(re.sub(r"（[^（）]*）$", "", i.get("short") or "") or i.get("author") or "作者不明")   # short は「作者（ライセンス）」。Commons の長い但し書きを除いた名前
    short = ["・%s: %s" % (k, "、".join(dict.fromkeys(v))) for k, v in by.items()] + ["・写真の題と出どころの URL は、コメント欄の一覧に"]
    return build(short), "この動画で使った画像（題・作者・ライセンス・出どころ）\n" + "\n".join(full) + "\n"


def checks(meta, info, src, K):
    warns, title = [], meta.get("title", "")
    if len(title) > 40:
        warns.append("題が %d 字です（検索結果では 28 字前後までが見える。大事な言葉を前に）" % len(title))
    if len(info["chapters"]) < 3:
        warns.append("章が %d 個です（目次が YouTube のチャプターになるのは 3 個以上・各 10 秒以上・0:00 から）" % len(info["chapters"]))
    if not meta.get("summary"):
        warns.append("summary（概要欄の最初の 1〜2 文）がありません。何がわかる動画かを書く")
    if not src:
        warns.append("出典がありません（事実の一覧 facts.md の「## 出典」）")
    vv = [c["name"] for c in info["cast"] if (K.PRESETS.get(c["id"], {}).get("voice") or {}).get("engine") == "voicevox"]
    for n in vv:
        if not any(("VOICEVOX:" + n) in c for c in info["credits"]):
            warns.append("クレジットに「VOICEVOX:%s」がありません（--voicevox で作ったか、voice_credit: を書いたか）" % n)
    if info.get("irasutoya", 0) > 20:
        warns.append("いらすとやの絵が %d 点あります。収益化した動画は 1 本 20 点まで（サムネイルを含む）" % info["irasutoya"])
    if info.get("webm_only"):
        warns.append("HTML のままでは配れない素材を使っています（%s）。WebM に書き出した動画だけを公開する" % "、".join(info["webm_only"]))
    if not meta.get("thumb"):
        warns.append("thumb（サムネイルの文字）がありません。題をそのまま使います。12 字前後の強い一言を 2〜3 行で書く")
    return warns


def font_path(K, name):
    cat = json.load(open(os.path.join(KDIR, "fonts.json"), encoding="utf-8"))
    p = os.path.join(KDIR, "fonts", cat.get(name, {}).get("file", ""))
    if os.path.isfile(p):
        return p, 0
    for q in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf"):
        if os.path.isfile(q):
            print("warn: フォント %s がありません（fetch_assets.py --only fonts）。Noto Sans CJK で代わります" % name, file=sys.stderr)
            return q, 0
    sys.exit("error: 日本語のフォントがありません。python3 %s --only fonts で取ってください" % os.path.join(KDIR, "fetch_assets.py"))


def thumbnail(meta, base, K, out):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    sprite = load("sprite", "sprite.py")
    # 背景
    bg = meta.get("thumb_bg") or meta.get("bg") or ""
    e = K.BGS.get(bg)
    path = os.path.join(KDIR, "bg", e["file"]) if e else os.path.join(base, bg) if bg else ""
    if path and os.path.isfile(path):
        im = Image.open(path).convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((round(im.width * r) + 1, round(im.height * r) + 1), Image.LANCZOS)
        im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
        im = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(3))).enhance(.62)
    else:
        im = Image.new("RGB", (W, H), (24, 28, 60))
        d = ImageDraw.Draw(im)
        for y in range(H):
            d.line([(0, y), (W, y)], fill=(24 + y // 12, 28 + y // 9, 60 + y // 5))
    im = im.convert("RGBA")
    # 立ち絵（右に寄せて大きく。表情は thumb_faces か、聞き手は驚き・解説役は得意げ）
    cast = K.build_cast(dict({k: v for k, v in meta.items() if not k.endswith(".art")}, art="png"), base)   # サムネイルは PNG のパーツから描く（SVG の立ち絵があっても）
    want = dict(p.split("=", 1) for p in re.split(r"[,、]\s*", meta.get("thumb_faces", "")) if "=" in p)
    ids = list(cast)
    explainer = next((p.split("=")[0].strip() for p in re.split(r"[,、]", meta.get("roles", "")) if "解説" in p.split("=")[-1]), ids[0])
    order = [i for i in ids if i != explainer][:1] + [i for i in ids if i == explainer]   # 聞き手を右端に大きく、解説役をその左に
    x_right, min_x, figs = W + 30, W, []
    for n, cid in enumerate(order[:2]):
        sp = cast[cid].get("sprite")
        if not sp:
            continue
        lab = want.get(cid, "smug" if cid == explainer else "surprised+").strip()
        m = K.OPT_RE.match(lab)
        faces = [f for f in sp["poses"][""]["faces"] if f.split("#")[0] == m.group(1)] or ["normal"]
        lv = lambda f: (sp.get("info", {}).get("faces", {}).get(f) or {}).get("lv", 2)
        face = lab if lab in faces else sorted(faces, key=lambda f: abs(lv(f) - (3 if m.group(3) == "+" else 1 if m.group(3) == "-" else 2)))[0]
        d = os.path.dirname(os.path.join(base, sp["_dir"]))
        fig = sprite.compose(sp, d, "", face, "open")
        fig = fig.crop(fig.getbbox())
        head = fig.height / fig.width < 1.3   # 頭だけの立ち絵（ゆっくり）
        hh = H * (.5 if head else 1.3) * (1 if n == 0 else .88)
        fig = fig.resize((round(fig.width * hh / fig.height), round(hh)), Image.LANCZOS)
        x = x_right - fig.width
        y = H - fig.height if head else round(H * (.05 if n == 0 else .16))
        edge = Image.new("RGBA", fig.size, (255, 255, 255, 0))
        edge.putalpha(fig.split()[3].filter(ImageFilter.MaxFilter(9)))
        figs.append((edge, fig, x, y))
        min_x, x_right = min(min_x, x), x + round(fig.width * .5)
    for edge, fig, x, y in reversed(figs):   # 奥（左）から描く
        im.paste(edge, (x, y), edge)   # 白いふち
        im.paste(fig, (x, y), fig)
    # 文字（左から。太い黒い縁と、外に白い縁）
    lines = [x.strip() for x in (meta.get("thumb") or meta.get("title", "")).split("|") if x.strip()][:3]
    fp, idx = font_path(K, meta.get("thumb_font", "dela"))
    box_w, top = max(round(W * .5), min_x + 70), 30   # 文字は左から、立ち絵の顔にかからない幅まで
    line_h = (H - 60) / max(len(lines), 2)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, t in enumerate(lines):
        size = int(line_h * .86)
        while size > 40:
            f = ImageFont.truetype(fp, size, index=idx)
            if d.textlength(t, font=f) <= box_w - 40:
                break
            size -= 6
        y = top + i * line_h + (line_h - size) / 2 - size * .12
        for sw, col in ((max(14, size // 6), (255, 255, 255)), (max(8, size // 10), (20, 20, 24))):
            d.text((36, y), t, font=f, fill=col, stroke_width=sw, stroke_fill=col)
        d.text((36, y), t, font=f, fill=COLORS[i % 3])
    im.alpha_composite(layer)
    im.convert("RGB").save(out, quality=92)
    return lines


def main():
    ap = argparse.ArgumentParser(description="概要欄とサムネイルを作る")
    ap.add_argument("script")
    ap.add_argument("--no-thumb", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    K = load("kaisetsu", "kaisetsu.py")
    base, stem = os.path.dirname(os.path.abspath(a.script)), os.path.splitext(os.path.abspath(a.script))[0]
    meta, chapters, errs = K.parse(open(a.script, encoding="utf-8").read())
    if not os.path.isfile(stem + ".info.json"):
        sys.exit("error: %s がありません。先に yukkuri-kaisetsu で動画を作ってください（kaisetsu.py 台本.txt --voicevox）" % os.path.basename(stem + ".info.json"))
    info = json.load(open(stem + ".info.json", encoding="utf-8"))
    src = sources(base, meta, stem)
    for w in checks(meta, info, src, K):
        print("warn:", w, file=sys.stderr)
    if a.check:
        return
    text, credits = description(meta, info, src)
    open(stem + ".description.txt", "w", encoding="utf-8").write(text)
    print("OK : %s（%d バイト）" % (stem + ".description.txt", len(text.encode("utf-8"))))
    if credits:
        open(stem + ".credits.txt", "w", encoding="utf-8").write(credits)
        print("warn: 画像のクレジットが概要欄（%d バイトまで）に収まらないので、作者とライセンスだけにまとめました。題と URL つきの全文は %s（動画のコメント欄に貼って固定する）"
              % (DESC_LIMIT, stem + ".credits.txt"))
    elif os.path.exists(stem + ".credits.txt"):
        os.remove(stem + ".credits.txt")
    if len(text.encode("utf-8")) > DESC_LIMIT:
        print("warn: 概要欄が %d バイトあります（YouTube は %d バイトまで）。出典を減らします" % (len(text.encode("utf-8")), DESC_LIMIT))
    if not a.no_thumb:
        lines = thumbnail(meta, base, K, stem + ".thumbnail.png")
        print("OK : %s（%s）" % (stem + ".thumbnail.png", " / ".join(lines)))


if __name__ == "__main__":
    main()
