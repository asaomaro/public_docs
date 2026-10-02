#!/usr/bin/env python3
"""説明用の挿絵（イラスト）を、日本語の言葉で探して取る。もの・食べ物・動物・乗り物・建物・天気・記号・職業の人 など約 1,500 点。

  python3 illust.py search りんご 太陽 先生        # 言葉ごとに候補（名前と、ほかの呼び名）を出す
  python3 illust.py get りんご 太陽 地球          # images/りんご.svg … に保存し、images/credits.json にクレジットを書く
  python3 illust.py get "red apple" --as apple   # 英語の名前で名指し、保存する名前を決める
  python3 illust.py get 科学者 --style 3d         # 立体の絵（PNG）。既定は平らな色の絵（SVG。小さくて、拡大しても荒れない）

台本では `@show: りんご "りんご" | → | 太陽`（images/ の名前を、拡張子なしで書ける）。

絵は Microsoft の Fluent Emoji（MIT License。商用・加工・再配布とも可、著作権表示が要る）。日本語の呼び名は Unicode CLDR の注釈（Unicode License）。
クレジットは締めの画面と概要欄に自動で出る。索引は最初の 1 回だけ作る（illust_index.json。配布元から 3 つのファイルを読む）。
"""
import argparse, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
INDEX = os.path.join(HERE, "illust_index.json")
UA = "yukkuri-kaisetsu-skill/1.0 (https://github.com/asaomaro/public_docs; Python urllib)"
REPO = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/"
TREE = "https://api.github.com/repos/microsoft/fluentui-emoji/git/trees/main?recursive=1"
CLDR = "https://raw.githubusercontent.com/unicode-org/cldr/main/common/annotations/%s.xml"
CREDIT = {"title": "Fluent Emoji", "author": "Microsoft", "license": "MIT License", "license_url": "https://github.com/microsoft/fluentui-emoji/blob/main/LICENSE",
          "page": "https://github.com/microsoft/fluentui-emoji", "from": "Fluent Emoji", "short": "Fluent Emoji（Microsoft、MIT）",
          "full": "挿絵: Fluent Emoji（Copyright (c) Microsoft Corporation、MIT License）https://github.com/microsoft/fluentui-emoji"}


def get(url, binary=False):
    data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90).read()
    return data if binary else data.decode("utf-8")


def build_index():
    """絵の一覧（配布元のファイルの並び）に、日本語の呼び名（CLDR）を英語の名前でつなぐ。"""
    print("索引を作っています（最初の 1 回だけ）…", file=sys.stderr)
    paths = [x["path"] for x in json.loads(get(TREE))["tree"]]
    note = lambda lang: re.findall(r'<annotation cp="([^"]+)"( type="tts")?>([^<]+)</annotation>', get(CLDR % lang))
    en = {text.strip().lower(): cp for cp, tts, text in note("en") if tts}
    ja = {}
    for cp, tts, text in note("ja"):
        e = ja.setdefault(cp, {"name": "", "keys": []})
        if tts:
            e["name"] = text.strip()
        else:
            e["keys"] = [k.strip() for k in text.split("|")]
    items = {}
    for p in paths:
        m = re.match(r"^assets/([^/]+)/(?:Default/)?(Color|3D)/([^/]+\.(?:svg|png))$", p)
        if m:
            items.setdefault(m.group(1), {})[m.group(2).lower()] = p
    out = []
    for name, files in sorted(items.items()):
        cp = en.get(name.lower()) or en.get(name.lower().replace("-", " "))
        j = ja.get(cp, {"name": "", "keys": []}) if cp else {"name": "", "keys": []}
        out.append({"en": name, "ja": j["name"], "keys": j["keys"], "glyph": cp or "", "color": files.get("color", ""), "3d": files.get("3d", "")})
    json.dump(out, open(INDEX, "w", encoding="utf-8"), ensure_ascii=False)
    print("OK : %d 点（日本語の呼び名つき %d 点）" % (len(out), sum(1 for e in out if e["ja"])), file=sys.stderr)
    return out


def load():
    return json.load(open(INDEX, encoding="utf-8")) if os.path.isfile(INDEX) else build_index()


def kana(s):
    """ひらがなとカタカナを同じに見る。"""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s).lower()


def find(idx, q):
    """言葉に合う絵を、合い方の強い順に。名前が同じ → 呼び名が同じ → 名前に含む → 呼び名に含む。"""
    k, hits = kana(q), []
    for e in idx:
        names = [kana(e["ja"]), e["en"].lower()]
        keys = [kana(x) for x in e["keys"]]
        rank = 0 if k in names else 1 if k in keys else 2 if any(k in n for n in names if n) else 3 if any(k in x for x in keys) else None
        if rank is not None:
            hits.append((rank, len(e["ja"] or e["en"]), e))
    return [e for _, _, e in sorted(hits, key=lambda x: x[:2])]


def main():
    ap = argparse.ArgumentParser(description="説明用の挿絵を、日本語の言葉で探して取る")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="候補を見る")
    s.add_argument("words", nargs="+")
    s.add_argument("-n", type=int, default=8)
    g = sub.add_parser("get", help="取る（言葉ごとに、いちばん合う絵）")
    g.add_argument("words", nargs="+")
    g.add_argument("--as", dest="name", help="保存する名前（言葉が 1 つのとき。既定は言葉そのまま）")
    g.add_argument("--out", default="images")
    g.add_argument("--style", choices=["color", "3d"], default="color")
    sub.add_parser("index", help="索引を作り直す")
    a = ap.parse_args()
    if a.cmd == "index":
        build_index()
        return
    idx = load()
    if a.cmd == "search":
        for w in a.words:
            hits = find(idx, w)
            print("# %s（%d 点）" % (w, len(hits)))
            for e in hits[:a.n]:
                print("  %s %-10s %-28s %s" % (e["glyph"], e["ja"] or "-", e["en"], "・".join(e["keys"][:6])))
        return
    os.makedirs(a.out, exist_ok=True)
    cj = os.path.join(a.out, "credits.json")
    cr = json.load(open(cj, encoding="utf-8")) if os.path.isfile(cj) else {}
    for w in a.words:
        hits = find(idx, w)
        if not hits:
            print("warn: 「%s」に合う絵がありません（search で別の言い方を探す。無ければ写真か、言葉だけで見せる）" % w, file=sys.stderr)
            continue
        e = hits[0]
        p = e[a.style] or e["color"] or e["3d"]
        data = get(REPO + urllib.parse.quote(p), binary=True)
        ext = os.path.splitext(p)[1]
        if ext == ".svg":   # 大きく描いても荒れないように、絵の元の大きさを 512 にしておく
            data = re.sub(rb'<svg width="\d+" height="\d+"', b'<svg width="512" height="512"', data, count=1)
        path = os.path.join(a.out, (a.name if a.name and len(a.words) == 1 else w) + ext)
        open(path, "wb").write(data)
        cr[os.path.basename(path)] = dict(CREDIT, title=e["ja"] or e["en"])
        print("OK : %s ← %s %s（%s）%s" % (path, e["glyph"], e["ja"] or e["en"], e["en"], "" if len(hits) == 1 else "  ほかの候補: " + "、".join(x["ja"] or x["en"] for x in hits[1:5])))
    json.dump(cr, open(cj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
