#!/usr/bin/env python3
"""背景（backgrounds.json）・BGM（bgm.json）・フォント（fonts.json）を、配布元から bg/・bgm/・fonts/ に取り直す。

  python3 fetch_assets.py            # 無いものだけ取る
  python3 fetch_assets.py --only bg  # 背景だけ（bgm で BGM だけ、fonts でフォントだけ）

素材はリポジトリに入れない（配布元の規約が「素材としての再配布」を禁じているため）。間を空けて 1 つずつ取る。
背景は 1920×1080 の JPEG に直して置く（Pillow が要る）。規約とクレジットは assets.md。
"""
import argparse, io, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))


def get(url, referer=None):
    h = {"User-Agent": "Mozilla/5.0"}
    if referer:
        h["Referer"] = referer
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120).read()


def main():
    ap = argparse.ArgumentParser(description="背景・BGM・フォントを配布元から取り直す")
    ap.add_argument("--only", choices=["bg", "bgm", "fonts"])
    a = ap.parse_args()
    n = 0
    for kind, cat in (("bg", "backgrounds.json"), ("bgm", "bgm.json"), ("fonts", "fonts.json")):
        if a.only and a.only != kind:
            continue
        os.makedirs(os.path.join(HERE, kind), exist_ok=True)
        for key, e in json.load(open(os.path.join(HERE, cat), encoding="utf-8")).items():
            if key.startswith("_"):
                continue
            path = os.path.join(HERE, kind, e["file"])
            if os.path.isfile(path):
                continue
            if "url" not in e:   # 自動では取れない曲（配布元の規約）。ブラウザで取って置く
                print("手で取る: %s → %s/%s" % (e["page"], kind, e["file"]))
                continue
            try:
                data = get(e["url"], e.get("referer") or e.get("page"))
                if kind == "bg":
                    from PIL import Image
                    im = Image.open(io.BytesIO(data)).convert("RGB")
                    if im.size != (1920, 1080):
                        im = im.resize((1920, 1080), Image.LANCZOS)
                    im.save(path, quality=84, optimize=True)
                else:
                    open(path, "wb").write(data)
                n += 1
                print("OK : %s/%s" % (kind, e["file"]))
            except Exception as ex:
                print("error: %s/%s を取れませんでした（%s）: %s" % (kind, e["file"], ex, e["url"]), file=sys.stderr)
            time.sleep(2)
    print("OK : %d 個を取りました" % n)


if __name__ == "__main__":
    main()
