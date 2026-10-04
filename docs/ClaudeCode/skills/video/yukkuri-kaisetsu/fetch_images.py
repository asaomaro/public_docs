#!/usr/bin/env python3
"""本編に映す画像を、自由に使えるものから探して取る（Wikimedia Commons・Openverse）。作者・ライセンスを credits.json に残し、動画の締めに自動で出す。

  python3 fetch_images.py search "レイリー散乱"                 # 候補を見る（題・大きさ・ライセンス・作者・説明）
  python3 fetch_images.py search "sunset sky" --source openverse
  python3 fetch_images.py get "File:Rayleigh sunlight scattering.png" --as scatter    # images/scatter.png に保存し、images/credits.json に書く
  python3 fetch_images.py get 3 --as sunset                     # 直前の search の 3 番目

台本では `@board image: images/scatter.png | 説明`。取った画像は必ず 1 回開いて、中身が話に合っているかを見る。

使えるライセンスだけを出す: パブリックドメイン・CC0・CC BY（--sa を付けると CC BY-SA も）。
CC BY-SA の画像を入れた動画は、同じ条件で共有することを求められる。分からなければ使わない。
人物の写真・ロゴ・商標には、著作権のほかの決まり（肖像・商標）がある。候補に「注意」と出たものは使わない。
"""
import argparse, html, json, os, re, sys, urllib.error, urllib.parse, urllib.request

UA = "yukkuri-kaisetsu-skill/1.0 (https://github.com/asaomaro/public_docs; Python urllib)"   # Wikimedia は、連絡先の入った User-Agent を求めている
COMMONS = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
LAST = os.path.join(os.path.expanduser("~"), ".cache", "yukkuri-kaisetsu-images.json")


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        data = urllib.request.urlopen(req, timeout=60).read()
    except urllib.error.HTTPError as e:   # 候補に出ても、もう削除されている画像がある（Commons・Flickr）。トレースバックで止めない
        sys.exit("error: 取れませんでした（HTTP %d）: %s\n  %s" % (e.code, url, "この画像は削除されたか、場所が変わっています。search の別の候補を使う" if e.code in (404, 410) else "少し待ってやり直すか、別の候補を使う"))
    except urllib.error.URLError as e:
        sys.exit("error: つながりません（%s）: %s" % (e.reason, url))
    return data if binary else json.loads(data.decode("utf-8"))


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def author(raw):
    """Commons の作者欄から、名前だけを取り出す。作者欄には定型文や連絡先がそのまま入っていることがあり、
    クレジットに「No machine-readable author provided. …」「You must credit this…」「…[user: …, mail: …」と出ていた。"""
    s = text(raw)
    m = re.search(r"No machine-readable author provided\.\s*(.+?)\s+assumed", s)
    if m:
        s = m.group(1)
    s = re.split(r"\s*(?:\[|\(talk\b|\(User talk|\bYou (?:must|may|can)\b|\bPlease\b|\bThis (?:file|image|photo)\b|\bI, the\b|https?://|\bmail\b|\bE-?mail\b)", s)[0]
    s = re.sub(r"^(?:Photo(?:graph)?(?: taken)? by|Photographer|Author|Creator|Original uploader was|撮影者?|作者)\s*[:：]?\s*", "", s, flags=re.I)
    s = re.sub(r"\s+(?:at|from)\s+(?:English|German|French|Japanese|Dutch|\w+)\s+Wikipedia$", "", s)
    s = s.strip(" ,.;:-—–()（）「」\"'")
    if len(s) > 60:   # 長い名前は、語の切れ目で切る
        s = re.sub(r"\s+\S*$", "", s[:61]).rstrip(" ,") + "…"
    return s


def kind(short):
    """ライセンスの短い名前 → pd・cc0・by・by-sa・その他"""
    s = (short or "").lower()
    if "cc0" in s or "zero" in s:
        return "cc0"
    if "public domain" in s or s.startswith("pd") or "pdm" in s or "no restrictions" in s:
        return "pd"
    if re.search(r"by[- ]sa", s):
        return "by-sa"
    if re.search(r"cc[- ]by|^by\b", s) and "nc" not in s and "nd" not in s:
        return "by"
    return "other"


def commons(q, n, width, category=False):
    """Commons を探す。category=True は、その名前のカテゴリに入っているファイルの一覧（固有名詞は、全文検索より当たる）。"""
    gen = ({"generator": "categorymembers", "gcmtitle": q if q.startswith("Category:") else "Category:" + q, "gcmtype": "file", "gcmlimit": min(50, n * 4)} if category else
           {"generator": "search", "gsrsearch": q + " filetype:bitmap|drawing", "gsrnamespace": 6, "gsrlimit": min(50, n * 4)})
    p = dict({"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": width, "maxlag": 5}, **gen)
    pages = (get(COMMONS + "?" + urllib.parse.urlencode(p)).get("query") or {}).get("pages", {})
    out = []
    for pg in sorted(pages.values(), key=lambda x: (x.get("index", 0), x.get("title", ""))):
        ii = (pg.get("imageinfo") or [{}])[0]
        md = {k: v.get("value", "") for k, v in (ii.get("extmetadata") or {}).items()}
        out.append({"id": pg["title"], "title": text(md.get("ObjectName")) or re.sub(r"^File:|\.\w+$", "", pg["title"]), "w": ii.get("width"), "h": ii.get("height"),
                    "license": text(md.get("LicenseShortName")), "license_url": md.get("LicenseUrl", ""), "author": author(md.get("Artist")) or author(md.get("Credit")),
                    "desc": text(md.get("ImageDescription"))[:120], "url": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl", ""),
                    "note": text(md.get("Restrictions")), "from": "Wikimedia Commons"})
    return out


def openverse(q, n, width):
    p = {"q": q, "page_size": min(20, n * 3), "license_type": "commercial,modification", "mature": "false"}
    out = []
    for r in get(OPENVERSE + "?" + urllib.parse.urlencode(p)).get("results", []):
        lic = ("CC0" if r["license"] == "cc0" else "Public domain" if r["license"] == "pdm" else "CC " + r["license"].upper() + " " + (r.get("license_version") or "")).strip()
        out.append({"id": r["url"], "title": r.get("title") or "", "w": r.get("width"), "h": r.get("height"), "license": lic, "license_url": r.get("license_url", ""),
                    "author": r.get("creator") or "", "desc": "", "url": r["url"], "page": r.get("foreign_landing_url", ""), "note": "", "from": r.get("source", "Openverse")})
    return out


def usable(e, sa):
    return kind(e["license"]) in ("pd", "cc0", "by") + (("by-sa",) if sa else ())


def credit(e):
    """クレジット。short は締めの画面に出す短い形、full は概要欄に書く形。"""
    k = kind(e["license"])
    who = e["author"] or "作者不明"
    if e["author"] and not re.search(r"[^\W_]", e["author"]):   # 記号だけの作者名（Flickr の「*_*」など）は、名前に見えない。どこの利用者かを添える
        who = "%s の %s" % (e["from"], who)
    short = "%s（%s）" % (who, e["license"]) if k in ("by", "by-sa") else "%s（%s）" % (e["from"], "パブリックドメイン" if k == "pd" else "CC0")
    full = "「%s」%s／%s%s／%s" % (e["title"], who, e["license"], "（" + e["license_url"] + "）" if e["license_url"] else "", e["page"])
    return {"title": e["title"], "author": e["author"], "license": e["license"], "license_url": e["license_url"], "page": e["page"], "from": e["from"],
            "short": short, "full": full}


def listing(i, e):
    """search の候補 1 件の表示。題は必ず出す（Openverse は id が URL なので、題が無いと何の写真か分からない）。"""
    title = e.get("title") or "（題なし）"
    head = e["id"] if title in e["id"] else "%s\n   %s" % (title, e["id"])
    return "%d. %s\n   %s×%s  %s  作者: %s%s\n   %s\n   %s" % (i, head, e["w"], e["h"], e["license"], e["author"][:50] or "（不明）",
                                                         "  注意: " + e["note"] if e["note"] else "", e["desc"], e["page"])


def main():
    ap = argparse.ArgumentParser(description="自由に使える画像を探して取り、クレジットを残す")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="候補を見る")
    s.add_argument("query")
    s.add_argument("--source", choices=["commons", "openverse"], default="commons")
    s.add_argument("-n", type=int, default=8)
    s.add_argument("--sa", action="store_true", help="CC BY-SA も出す")
    s.add_argument("--category", action="store_true", help="query を Commons のカテゴリ名とみて、その中のファイルを出す（固有名詞の写真は、検索よりこちらが当たる）")
    g = sub.add_parser("get", help="取る")
    g.add_argument("id", help="search の番号か、File:… の名前")
    g.add_argument("--as", dest="name", required=True, help="保存する名前（拡張子なし）")
    g.add_argument("--out", default="images", help="保存するフォルダ（既定: images）")
    g.add_argument("--sa", action="store_true")
    ap.add_argument("--width", type=int, default=1920, help="取る幅（既定 1920。元がこれより小さければ元のまま。前は 1280 で、1920×1080 の動画では写真がぼやけた）")
    a = ap.parse_args()
    if a.cmd == "search":
        found = commons(a.query, a.n, a.width, a.category) if a.source == "commons" else openverse(a.query, a.n, a.width)
        ok = [e for e in found if usable(e, a.sa) and (e["w"] or 0) >= 400][:a.n]
        os.makedirs(os.path.dirname(LAST), exist_ok=True)
        json.dump(ok, open(LAST, "w", encoding="utf-8"), ensure_ascii=False)
        for i, e in enumerate(ok, 1):
            print(listing(i, e))
        print("%d 件（見つかった %d 件のうち、使えるライセンスのもの）" % (len(ok), len(found)))
        if a.category and not found:
            print("note: カテゴリ「%s」が Commons にありません。英語の名前で（例: \"Lake Hillier\"）。Commons のそのページの下にある「Category:…」の名前を使います" % a.query)
        return
    if a.id.isdigit():
        last = json.load(open(LAST, encoding="utf-8")) if os.path.isfile(LAST) else []
        if not 1 <= int(a.id) <= len(last):
            sys.exit("error: 直前の search に %s 番はありません" % a.id)
        e = last[int(a.id) - 1]
    else:
        title = a.id if a.id.startswith("File:") else "File:" + a.id
        p = {"action": "query", "format": "json", "titles": title, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": a.width}
        pg = list((get(COMMONS + "?" + urllib.parse.urlencode(p)).get("query") or {}).get("pages", {}).values())
        if not pg or "imageinfo" not in pg[0]:
            sys.exit("error: %s が見つかりません" % title)
        ii = pg[0]["imageinfo"][0]
        md = {k: v.get("value", "") for k, v in (ii.get("extmetadata") or {}).items()}
        e = {"id": title, "title": text(md.get("ObjectName")) or re.sub(r"^File:|\.\w+$", "", title), "w": ii.get("width"), "h": ii.get("height"),
             "license": text(md.get("LicenseShortName")), "license_url": md.get("LicenseUrl", ""), "author": author(md.get("Artist")) or author(md.get("Credit")),
             "url": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl", ""), "note": text(md.get("Restrictions")), "from": "Wikimedia Commons"}
    if not usable(e, a.sa):
        sys.exit("error: この画像のライセンス（%s）は使えません（パブリックドメイン・CC0・CC BY だけ。CC BY-SA は --sa）" % (e["license"] or "不明"))
    if e.get("note"):
        print("warn: この画像には著作権のほかの注意があります（%s）。使わないほうがよい" % e["note"], file=sys.stderr)
    data = get(e["url"], binary=True)
    ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".gif" if data[:3] == b"GIF" else ".webp" if data[8:12] == b"WEBP" else ".jpg"
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, a.name + ext)
    open(path, "wb").write(data)
    cj = os.path.join(a.out, "credits.json")
    cr = json.load(open(cj, encoding="utf-8")) if os.path.isfile(cj) else {}
    cr[os.path.basename(path)] = credit(e)
    json.dump(cr, open(cj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK : %s（%.0fKB）\nクレジット: %s" % (path, len(data) / 1024, cr[os.path.basename(path)]["full"]))


if __name__ == "__main__":
    main()
