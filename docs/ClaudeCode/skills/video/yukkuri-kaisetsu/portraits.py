#!/usr/bin/env python3
"""VOICEVOX（起動しておく）に入っている話者の立ち絵を取り出して、chars/<名前>/normal.png に置く。

  python3 portraits.py                      # casts.json のプリセットの話者（chars/<プリセットの名前>/）
  python3 portraits.py --all                # プリセットに無い話者も（chars/<話者の名前>/）
  python3 portraits.py --out 台本の場所/chars

取り出すのは 1 人 1 枚の絵（口・目の差分は無い）。styles/ポートレート.png に置き、normal.png が無いときだけ normal.png にもする
（差分つきの立ち絵を書き出してあれば上書きしない）。スタイルごとの絵がある話者は styles/<スタイル>.png にも置く。
話者ごとの利用規約の案内は policy.txt。画像は再配布しない（リポジトリに入れない）。
"""
import argparse, base64, json, os, re, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
PRESETS = {k: v for k, v in json.load(open(os.path.join(HERE, "casts.json"), encoding="utf-8")).items() if not k.startswith("_")}


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def save_image(path, data):
    """data は base64 の PNG か、画像の URL（エンジンの設定による）。"""
    raw = urllib.request.urlopen(data, timeout=60).read() if data.startswith("http") else base64.b64decode(data)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(raw)


def main():
    ap = argparse.ArgumentParser(description="VOICEVOX の話者の立ち絵を chars/ に取り出す")
    ap.add_argument("--voicevox-url", default="http://127.0.0.1:50021")
    ap.add_argument("--out", default="chars", help="置き場所（既定: いまの場所の chars/）")
    ap.add_argument("--all", action="store_true", help="プリセットに無い話者も取り出す")
    a = ap.parse_args()
    url = a.voicevox_url.rstrip("/")
    ids = {(v.get("voice") or {}).get("speaker"): k for k, v in PRESETS.items() if (v.get("voice") or {}).get("engine") == "voicevox"}
    n = 0
    for sp in get(url + "/speakers"):
        if sp["name"] not in ids and not a.all:
            continue
        cid = ids.get(sp["name"]) or re.sub(r'[\\/:*?"<>|]', "_", sp["name"])
        info = get(url + "/speaker_info?" + urllib.parse.urlencode({"speaker_uuid": sp["speaker_uuid"]}))
        d = os.path.join(a.out, cid)
        save_image(os.path.join(d, "styles", "ポートレート.png"), info["portrait"])
        if not os.path.exists(os.path.join(d, "normal.png")):   # 差分つきの立ち絵を書き出してあれば、そちらを残す
            save_image(os.path.join(d, "normal.png"), info["portrait"])
        names = {st["id"]: st["name"] for st in sp["styles"]}
        styles = [si for si in info.get("style_infos", []) if si.get("portrait") and si["id"] in names]
        for si in styles:
            save_image(os.path.join(d, "styles", names[si["id"]] + ".png"), si["portrait"])
        open(os.path.join(d, "policy.txt"), "w", encoding="utf-8").write("%s\n\n%s\n" % (sp["name"], info.get("policy", "").strip()))
        print("  %-12s %s%s" % (cid, sp["name"], "（スタイルの絵 %d 枚）" % len(styles) if styles else ""))
        n += 1
    print("OK : %d 人の立ち絵を %s に置きました" % (n, os.path.abspath(a.out)))


if __name__ == "__main__":
    main()
