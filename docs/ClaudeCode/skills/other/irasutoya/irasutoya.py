#!/usr/bin/env python3
"""いらすとや（https://www.irasutoya.com/）のイラストを、言葉で探して、選んだものだけ取る。前もって全部は落とさない。

  python3 irasutoya.py search "ひらめいた|ひらめき|閃いた" "アイデア|アイディア" --sheet   # 言い換えをまとめて探し、見本の一覧画像を作る
  python3 irasutoya.py search 会議 --label ビジネス -n 20          # カテゴリーで絞る
  python3 irasutoya.py show 3 --sheet                              # 3 番目の記事に入っている絵（セットの中身）を見る
  python3 irasutoya.py get 1 3:2 --dir images                      # 1 番目と、3 番目の記事の 2 枚目を images/ に保存
  python3 irasutoya.py get https://www.irasutoya.com/2024/06/blog-post_21.html --as wet_cat
  python3 irasutoya.py canvas images/idea.png -o scenes/idea.js --split --preview   # SVG にして、Canvas に描いて動かす JS にする（motion-video の custom の場面）
  python3 irasutoya.py trace images/idea.png                       # SVG のファイルにする（images/idea.svg）
  python3 irasutoya.py labels                                      # カテゴリーの一覧
  python3 irasutoya.py check                                       # Pillow・vtracer が入っているか（無ければ入れ方を出す）
  python3 irasutoya.py count --dir images                          # 取った点数（商用は 1 つの制作物に 20 点まで）

探す言葉の書き方（サイトの検索と同じ。説明文・題・カテゴリーに、その字が書いてあるものだけが当たる）:
  空白 = どちらも含む ／ | = どれかを含む（空白より先に組になる。「会社員 困っている|焦る」=「会社員」かつ「困っている か 焦る」）／ 空白と -言葉 = 含まない。
  引数を分けると、別々に探して 1 つの一覧にまとめる。

サイトの Blogger のフィード（JSON）を読む。探す・取るのは標準ライブラリだけで動く。見本の一覧画像（--sheet）と canvas には Pillow、SVG にするのには vtracer が要る（python3 irasutoya.py check で確かめる）。
検索の結果は 1 日だけ手元に覚え、サイトへの問い合わせは 1 秒あける。
"""
import argparse, base64, hashlib, html, io, json, os, re, sys, time, urllib.parse, urllib.request

UA = "irasutoya-skill/1.0 (https://github.com/asaomaro/public_docs; Python urllib)"
SITE = "https://www.irasutoya.com"
FEED = SITE + "/feeds/posts/default"
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "irasutoya-skill")
LAST = os.path.join(CACHE, "last.json")
TTL = 24 * 3600
LIMIT = 20          # 商用で、1 つの制作物に無料で使える点数
CREDIT = {"author": "みふねたかし", "license": "いらすとや ご利用規定", "license_url": SITE + "/p/terms.html", "from": "いらすとや",
          "short": "いらすとや", "full": "イラスト: いらすとや https://www.irasutoya.com/"}
_last_hit = [0.0]


def die(msg):
    print("エラー: " + msg, file=sys.stderr)
    sys.exit(1)


def pil():
    """Pillow（画像を並べる・切り分ける・縮めるのに使う）。無ければ、入れ方を示して止まる。"""
    try:
        import PIL
        from PIL import Image
        return PIL
    except ImportError:
        die("Pillow が要ります。次で入れてください:\n  python3 -m pip install --user pillow\n"
            "  （externally-managed-environment と出たら、--break-system-packages を足すか、sudo apt install python3-pil）")


def tracer():
    """vtracer（PNG の輪郭をなぞって SVG にする）。無ければ、入れ方を示して止まる。"""
    try:
        import vtracer
        return vtracer
    except ImportError:
        die("vtracer が要ります。次で入れてください:\n  python3 -m pip install --user vtracer\n"
            "  （externally-managed-environment と出たら、--break-system-packages を足す）\n"
            "PNG のまま Canvas に入れるなら、canvas に --raster を付ければ vtracer は要りません")


def fetch(url, wait=1.0):
    """サイトへは間をあけて問い合わせる（wait 秒）。"""
    gap = wait - (time.time() - _last_hit[0])
    if gap > 0:
        time.sleep(gap)
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
    except Exception as e:
        die("読めませんでした: %s（%s）" % (url, e))
    _last_hit[0] = time.time()
    return data


def feed(url, fresh=False):
    """フィードを読む。同じ問い合わせは 1 日だけ手元から返す。"""
    path = os.path.join(CACHE, "feed", hashlib.sha1(url.encode()).hexdigest() + ".json")
    if not fresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < TTL:
        return json.load(open(path, encoding="utf-8"))
    d = json.loads(fetch(url).decode("utf-8"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return d


def sized(url, size):
    """画像の URL の大きさの指定を差し替える。s0 = 元の大きさ、s200 = 長い辺 200px。"""
    return re.sub(r"/(?:s\d+|w\d+-h\d+)(?:-[a-z0-9-]+)?/(?=[^/]+$)", "/%s/" % size, url)


def fname(url):
    n = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    return re.sub(r"(\.(?:png|jpe?g|gif))\1$", r"\1", n, flags=re.I)     # まれに name.png.png がある


def entry(e):
    """フィードの 1 件 → 題・カテゴリー・説明・入っている絵。"""
    body = (e.get("content") or e.get("summary") or {}).get("$t", "")
    imgs = []
    for href, inner in re.findall(r'<a[^>]+href="(https?://[^"]+?\.(?:png|jpe?g|gif))"[^>]*>(.*?)</a>', body, flags=re.S | re.I):
        alt = re.search(r'alt="([^"]*)"', inner)
        imgs.append({"url": href, "alt": html.unescape(alt.group(1)) if alt else "", "file": fname(href)})
    if not imgs:    # リンクの無い古い記事は、本文の絵そのもの（一覧用の見本は除く）
        for tag in re.findall(r"<img[^>]+>", body):
            src = re.search(r'src="([^"]+)"', tag)
            if src and "postthumb" not in tag:
                alt = re.search(r'alt="([^"]*)"', tag)
                imgs.append({"url": src.group(1), "alt": html.unescape(alt.group(1)) if alt else "", "file": fname(src.group(1))})
    desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
    thumb = (e.get("media$thumbnail") or {}).get("url") or (imgs[0]["url"] if imgs else "")
    return {"id": e["id"]["$t"].rsplit("-", 1)[-1], "title": e["title"]["$t"], "labels": [c["term"] for c in e.get("category", [])], "desc": desc,
            "page": next((l["href"] for l in e["link"] if l["rel"] == "alternate"), ""), "date": e["published"]["$t"][:10], "thumb": thumb, "images": imgs}


def search_one(q, labels, n, fresh):
    p = {"alt": "json", "max-results": n}
    base = FEED
    if q:       # 言葉と一緒のときは label: で絞る（カテゴリーのフィードは q を付けると絞り込みが外れる）
        p["q"] = " ".join(["label:" + l for l in labels] + [q])
    elif labels:
        base += "/-/" + "/".join(urllib.parse.quote(l, safe="") for l in labels)
    return [entry(e) for e in feed(base + "?" + urllib.parse.urlencode(p), fresh)["feed"].get("entry", [])]


def words(q):
    return [w for w in re.split(r"[\s|]+", q) if w and not w.startswith("-") and w.upper() != "OR"]


def rank(found, queries):
    """題に出る言葉を重く、次にカテゴリー、説明の順に数える。いくつもの問い合わせに当たったものを上に。"""
    ws = {w for q in queries for w in words(q)}
    for it in found.values():
        it["score"] = sum(3 * (w in it["title"]) + 2 * (w in it["labels"]) + (w in it["desc"]) for w in ws) + 2 * (len(it["hit"]) - 1)
    return sorted(sorted(found.values(), key=lambda it: it["date"], reverse=True), key=lambda it: -it["score"])     # 同じ点なら新しい順


def save_last(kind, items):
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"kind": kind, "items": items}, open(LAST, "w", encoding="utf-8"), ensure_ascii=False)


def load_last():
    if not os.path.exists(LAST):
        die("先に search をしてください（番号は直前の search の結果を指す）")
    return json.load(open(LAST, encoding="utf-8"))["items"]


def by_page(url):
    path = urllib.parse.urlparse(url).path
    es = feed(FEED + "?" + urllib.parse.urlencode({"alt": "json", "path": path}))["feed"].get("entry", [])
    if not es:
        die("記事が見つかりません: " + url)
    return entry(es[0])


def resolve(ref):
    """「3」「3:2」「3:1,4」「3:all」「記事の URL」「URL:2」 → （記事, 取る絵の番号の並び か None）"""
    m = re.match(r"^(.*?)(?::(all|\d+(?:,\d+)*))?$", ref)
    head, pick = m.group(1), m.group(2)
    if head.isdigit():
        items = load_last()
        if not 1 <= int(head) <= len(items):
            die("%s 番はありません（直前の search は %d 件）" % (head, len(items)))
        it = items[int(head) - 1]
    elif head.startswith("http"):
        it = by_page(head)
    else:
        die("番号か記事の URL を書いてください: " + ref)
    n = len(it["images"])
    if pick is None:
        return it, None
    ks = list(range(1, n + 1)) if pick == "all" else [int(k) for k in pick.split(",")]
    if any(not 1 <= k <= n for k in ks):
        die("「%s」の絵は %d 枚です: %s" % (it["title"], n, ref))
    return it, ks


def compose(tiles, out, cell=200, cols=None):
    """番号つきの絵を 1 枚に並べる。tiles = [(番号の文字, PIL の画像 か None)]"""
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cols = cols or min(len(tiles), 6 if len(tiles) > 12 else 4) or 1
    rows = -(-len(tiles) // cols)
    pad, bar = 8, 26
    im = Image.new("RGB", (cols * (cell + pad) + pad, rows * (cell + bar + pad) + pad), "#ffffff")
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.load_default(size=20)
    except TypeError:
        font = ImageFont.load_default()
    for i, (tag, t) in enumerate(tiles):
        x, y = pad + (i % cols) * (cell + pad), pad + (i // cols) * (cell + bar + pad)
        dr.rectangle([x, y, x + cell, y + bar], fill="#1f2937")
        dr.text((x + 8, y + 2), tag, fill="#ffffff", font=font)
        dr.rectangle([x, y + bar, x + cell, y + bar + cell], fill="#f1f5f9")
        if t is None:
            dr.text((x + 8, y + bar + 8), "?", fill="#dc2626", font=font)
            continue
        t = t.convert("RGBA")
        t.thumbnail((cell, cell))
        im.paste(t, (x + (cell - t.width) // 2, y + bar + (cell - t.height) // 2), t)
    im.save(out)


def sheet(cells, out, cell=200, cols=None):
    """番号つきの見本を 1 枚に並べる。cells = [(番号の文字, 画像の URL)]"""
    pil()
    from PIL import Image
    tiles = []
    for tag, u in cells:
        if not u:
            continue
        try:
            tiles.append((tag, Image.open(io.BytesIO(fetch(sized(u, "s%d" % cell), wait=0.1)))))
        except Exception:
            tiles.append((tag, None))
    compose(tiles, out, cell, cols)
    print("見本の一覧: %s（%d 枚。Read で開いて番号で選ぶ）" % (out, len(tiles)))


def cmd_search(a):
    queries = a.words or [""]
    if not a.words and not a.label:
        die("探す言葉か --label を書いてください")
    found = {}
    for q in queries:
        for it in search_one(q, a.label, a.max, a.fresh):
            found.setdefault(it["id"], dict(it, hit=[]))["hit"].append(q)
    items = rank(found, queries)[:a.n]
    save_last("search", items)
    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
        return
    for q in queries:
        print("「%s」%s: %d 件" % (q, "（カテゴリー " + "+".join(a.label) + "）" if a.label else "", sum(q in it["hit"] for it in found.values())))
    if not items:
        print("見つかりません。表記（ひらがな・カタカナ・漢字）や言い回し（「歩く」→「歩いている」）を変えるか、似た見た目の別の言葉で探す。")
        return
    print("―― %d 件のうち上から %d 件 ――" % (len(found), len(items)))
    for i, it in enumerate(items, 1):
        n = len(it["images"])
        print("[%d] %s%s  〔%s〕 %s" % (i, it["title"], "  ★%d 枚セット" % n if n > 1 else "", "・".join(it["labels"]), it["date"]))
        if n > 1:
            print("     中身: " + " / ".join("%d:%s" % (k, im["alt"] or im["file"]) for k, im in enumerate(it["images"], 1))[:300])
        print("     %s  %s" % (it["desc"][:90], it["page"]))
    if a.sheet:
        sheet([(str(i), it["thumb"]) for i, it in enumerate(items, 1)], a.sheet, a.cell)


def cmd_show(a):
    it, _ = resolve(a.ref)
    print("%s  〔%s〕 %s\n%s\n%s" % (it["title"], "・".join(it["labels"]), it["date"], it["desc"], it["page"]))
    for k, im in enumerate(it["images"], 1):
        print("  %s:%d  %s  %s" % (a.ref, k, im["alt"] or "（説明なし）", im["file"]))
    if a.sheet:
        sheet([(str(k), im["url"]) for k, im in enumerate(it["images"], 1)], a.sheet, a.cell)


def cmd_get(a):
    jobs = []
    for ref in a.refs:
        it, ks = resolve(ref)
        if not it["images"]:
            die("絵が見つかりません: " + it["page"])
        if ks is None:
            if len(it["images"]) > 1:
                die("「%s」は %d 枚セットです。どれを取るか書いてください（例 %s:1、全部なら %s:all）。中身は show %s --sheet で見られます。\n  %s"
                    % (it["title"], len(it["images"]), ref, ref, ref, " / ".join("%d:%s" % (k, im["alt"] or im["file"]) for k, im in enumerate(it["images"], 1))))
            ks = [1]
        jobs += [(it, it["images"][k - 1]) for k in ks]
    if a.name and len(jobs) != 1:
        die("--as は 1 枚だけ取るときに使えます")
    os.makedirs(a.dir, exist_ok=True)
    cj = os.path.join(a.dir, "credits.json")
    credits = json.load(open(cj, encoding="utf-8")) if os.path.exists(cj) else {}
    for it, im in jobs:
        ext = os.path.splitext(im["file"])[1].lower() or ".png"
        name = (a.name + ext) if a.name else im["file"]
        path = os.path.join(a.dir, name)
        data = fetch(sized(im["url"], "s%d" % a.size), wait=0.3)
        open(path, "wb").write(data)
        credits[name] = dict(CREDIT, title=im["alt"] or it["title"], page=it["page"], source=sized(im["url"], "s0"))
        print("保存: %s（%s、%d KB）  %s" % (path, im["alt"] or it["title"], len(data) // 1024, it["page"]))
    json.dump(credits, open(cj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    report(a.dir, credits)


def mine(credits):
    return {k: v for k, v in credits.items() if v.get("from") == "いらすとや"}


def report(d, credits):
    n = len({v.get("source") or k for k, v in mine(credits).items()})
    print("%s のいらすとやの絵: %d 点（商用は 1 つの制作物に %d 点まで。同じ絵は何度使っても 1 点）" % (d, n, LIMIT))
    if n > LIMIT:
        print("★ %d 点を超えています。商用の制作物なら、点数を減らすか、いらすとやに有償の利用を問い合わせる。" % LIMIT)


def cmd_count(a):
    cj = os.path.join(a.dir, "credits.json")
    credits = json.load(open(cj, encoding="utf-8")) if os.path.exists(cj) else {}
    for k, v in mine(credits).items():
        print("  %s  %s  %s" % (k, v.get("title", ""), v.get("page", "")))
    report(a.dir, credits)


HERE = os.path.dirname(os.path.realpath(__file__))
MARK = "/* ---- ここから描き方"
PREVIEW = """<!doctype html>
<meta charset="utf-8"><title>%(title)s</title>
<style>html,body{margin:0;height:100%%;background:#dfe4ea;display:flex;align-items:center;justify-content:center}
canvas{width:min(100vw,177.78vh);aspect-ratio:16/9;background:#fbfaf7;box-shadow:0 8px 40px rgba(0,0,0,.18)}</style>
<canvas id="c" width="1920" height="1080"></canvas>
<script>
/* 動きを見るための画面（%(dur)d ms を繰り返す）。?t=1200 で、その時刻で止める。motion-video の道具 H は空なので、H.txt などは映らない */
var CODE = %(code)s;
var fn = new Function("ctx", "lt", "d", "H", "s", CODE), s = {}, ctx = document.getElementById("c").getContext("2d"), D = %(dur)d;
var fixed = new URLSearchParams(location.search).get("t"), H = new Proxy({}, { get: function () { return function () { return 0; }; } });
function frame(now) { var lt = fixed != null ? +fixed : now %% D;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, 1920, 1080); ctx.save(); try { fn(ctx, lt, D, H, s); } catch (e) { console.error(e); } ctx.restore();
  requestAnimationFrame(frame); }
requestAnimationFrame(frame);
</script>
"""


def split_parts(im, gap, min_pct, max_parts):
    """背景が透明な絵を、つながっている塊ごとに分ける。→ [(その塊だけを残した絵, 左, 上)]（大きい順）
    gap px までのすき間はつながっているとみなし、小さすぎる塊は近くの塊に入れる。"""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = im.size
    alpha = im.getchannel("A").point(lambda v: 255 if v > 24 else 0)
    grown = alpha.filter(ImageFilter.MaxFilter(2 * gap + 1)) if gap > 0 else alpha
    data = grown.tobytes()
    parent, runs, prev = [], [], []          # runs = [(y, x0, x1, 札)]

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for y in range(h):
        cur = []
        for m in re.finditer(b"\xff+", data[y * w:(y + 1) * w]):
            x0, x1 = m.span()
            lab = None
            for px0, px1, pl in prev:        # 上の行と、斜めも含めて触れていれば同じ塊
                if px0 <= x1 and px1 >= x0:
                    r = find(pl)
                    if lab is None:
                        lab = r
                    elif r != lab:
                        parent[r] = lab
            if lab is None:
                lab = len(parent)
                parent.append(lab)
            cur.append((x0, x1, lab))
            runs.append((y, x0, x1, lab))
        prev = cur
    comps = {}
    for y, x0, x1, lab in runs:
        c = comps.setdefault(find(lab), {"area": 0, "box": [x0, y, x1, y + 1], "runs": []})
        c["area"] += x1 - x0
        c["runs"].append((y, x0, x1))
        b = c["box"]
        c["box"] = [min(b[0], x0), min(b[1], y), max(b[2], x1), y + 1]
    order = sorted(comps.values(), key=lambda c: -c["area"])
    total = sum(c["area"] for c in order) or 1
    keep = [c for i, c in enumerate(order) if i == 0 or (i < max_parts and c["area"] * 100.0 / total >= min_pct)]

    def dist(a, b):                          # 外枠どうしのすき間
        dx = max(a[0] - b[2], b[0] - a[2], 0)
        dy = max(a[1] - b[3], b[1] - a[3], 0)
        return dx * dx + dy * dy

    for c in order:
        if not any(c is k for k in keep):
            min(keep, key=lambda k: dist(k["box"], c["box"]))["runs"] += c["runs"]
    out = []
    clear = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for c in keep:
        mask = Image.new("L", (w, h), 0)
        dr = ImageDraw.Draw(mask)
        for y, x0, x1 in c["runs"]:
            dr.line([(x0, y), (x1 - 1, y)], fill=255)
        part = Image.composite(im, clear, mask)
        box = part.getchannel("A").getbbox()
        if box:
            out.append((part.crop(box), box[0], box[1]))
    return sorted(out, key=lambda p: -sum(1 for v in p[0].getchannel("A").tobytes() if v > 24))


# なぞる細かさ。fine は元の絵に近く（色の段が細かい）、mid は半分ほどの大きさで模様が減る
DETAIL = {"fine": dict(filter_speckle=4, color_precision=6, layer_difference=16, length_threshold=4.0, path_precision=2),
          "mid": dict(filter_speckle=8, color_precision=5, layer_difference=32, length_threshold=4.0, path_precision=1)}


def trace_svg(im, detail):
    """PIL の絵（背景が透明）→ SVG の文字列。色の塊ごとに輪郭をなぞる（塗りの質感・ぼかしは平らな色になる）。"""
    b = io.BytesIO()
    im.save(b, "PNG")
    svg = tracer().convert_raw_image_to_svg(b.getvalue(), img_format="png", colormode="color", hierarchical="stacked", mode="spline",
                                            corner_threshold=60, max_iterations=10, splice_threshold=45, **DETAIL[detail])
    svg = re.sub(r"^.*?(?=<svg)", "", svg, flags=re.S)       # XML の宣言と注釈を落とす
    return svg.replace("<svg ", '<svg viewBox="0 0 %d %d" ' % im.size, 1) if "viewBox" not in svg[:300] else svg


def svg_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii"), len(svg.encode("utf-8"))


def png_uri(im):
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode("ascii"), len(b.getvalue())


def bundle(out, data_json, draw_path):
    rt = open(os.path.join(HERE, "sprite.js"), encoding="utf-8").read()
    rt = rt.replace("__DRAW__", os.path.basename(draw_path)).replace("__DATA__", data_json)
    open(out, "w", encoding="utf-8").write(rt + open(draw_path, encoding="utf-8").read())


def write_preview(js, path, dur):
    code = json.dumps(open(js, encoding="utf-8").read(), ensure_ascii=False).replace("</", "<\\/")
    open(path, "w", encoding="utf-8").write(PREVIEW % {"title": os.path.basename(js), "dur": dur, "code": code})
    print("動きを見る: %s（ブラウザで開く。?t=1200 でその時刻に止まる）" % path)


def cmd_canvas(a):
    stem = os.path.splitext(a.update or a.out or "")[0]
    if not stem:
        die("-o で作るファイル（scenes/名前.js）を書いてください")
    out, draw = stem + ".js", stem + ".draw.js"
    if a.update:        # 描き方（*.draw.js）だけを入れ直す。絵はそのまま
        if a.images:
            die("--update のときは、画像は書きません（絵を替えるなら -o で作り直す）")
        if not os.path.exists(out) or not os.path.exists(draw):
            die("%s と %s が要ります" % (out, draw))
        src = open(out, encoding="utf-8").read()
        k = src.find(MARK)
        if k < 0:
            die("irasutoya.py canvas で作ったファイルではありません: " + out)
        head = src[:src.index("\n", k) + 1]
        open(out, "w", encoding="utf-8").write(head + open(draw, encoding="utf-8").read())
        print("作り直しました: %s（描き方: %s）" % (out, draw))
    else:
        if not a.images:
            die("Canvas にする画像を書いてください")
        pil()
        from PIL import Image
        if not a.raster:
            tracer()
        size_max = (800 if a.raster else 0) if a.size is None else a.size     # SVG は元の大きさからなぞる（細部が残る）
        data, tiles = {}, []
        for path in a.images:
            if not os.path.isfile(path):
                die("画像がありません: " + path)
            name = os.path.splitext(os.path.basename(path))[0]
            cj = os.path.join(os.path.dirname(path) or ".", "credits.json")
            cr = (json.load(open(cj, encoding="utf-8")) if os.path.exists(cj) else {}).get(os.path.basename(path), {})
            im = Image.open(path).convert("RGBA")
            if not a.no_trim:
                im = im.crop(im.getchannel("A").getbbox() or (0, 0) + im.size)      # まわりの透明な余白を落とす
            if size_max and max(im.size) > size_max:
                k = size_max / float(max(im.size))
                im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
            w, h = im.size
            pieces = split_parts(im, a.gap, a.min_part, a.max_parts) if a.split else [(im, 0, 0)]
            parts, size = [], 0
            for i, (pim, px, py) in enumerate(pieces, 1):
                uri, n = png_uri(pim) if a.raster else svg_uri(trace_svg(pim, a.detail))
                size += n
                parts.append({"src": uri, "x": px, "y": py, "w": pim.width, "h": pim.height})
                tiles.append(("%s %d" % (name[:10], i) if len(a.images) > 1 else str(i), pim))
            data[name] = {"w": w, "h": h, "title": cr.get("title", ""), "page": cr.get("page", ""), "parts": parts}
            print("%s: %s %d×%d、%d KB%s%s" % (name, "PNG" if a.raster else "SVG", w, h, size // 1024, "、" + cr["title"] if cr.get("title") else "", "、部品 %d 個" % len(parts) if a.split else ""))
            if a.split:
                for i, p in enumerate(parts, 1):
                    print("   部品 %d: 左上 (%d, %d)・%d×%d" % (i, p["x"], p["y"], p["w"], p["h"]))
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        if not os.path.exists(draw):         # 描き方のひな形。横に並べて、ふわふわ動かす
            n = len(data)
            hh = 560 if n == 1 else max(240, min(480, int(1500 / n)))
            lines = ["// 描き方。ここを直して、python3 irasutoya.py canvas --update %s で作り直す。" % out,
                     "// 座標は 1920×1080（下の 880 から先は字幕）。lt = 場面の中の経過 ms、d = 場面の長さ ms。draw() は描いた枠 {x, y, w, h} を返す。"]
            for i, name in enumerate(data):
                x = int(1920 * (i + 1) / (n + 1))
                extra = ', stagger: 220, partIdle: "float"' if a.split and len(data[name]["parts"]) > 1 else ', enter: "pop", idle: "float"'
                lines.append("draw(%s, { x: %d, y: 500, h: %d, at: %d%s, shadow: true });" % (json.dumps(name, ensure_ascii=False), x, hh, 200 + i * 300, extra))
            open(draw, "w", encoding="utf-8").write("\n".join(lines) + "\n")
            print("描き方のひな形: %s（ここを直す）" % draw)
        else:
            print("描き方はそのまま使います: %s" % draw)
        bundle(out, json.dumps(data, ensure_ascii=False, separators=(",", ":")), draw)
        print("作りました: %s（%d KB。絵のデータが長いので開かない。motion-video では {\"type\": \"custom\", \"src\": \"%s\"}）" % (out, os.path.getsize(out) // 1024, out))
        if a.split and tiles:
            sp = a.sheet or os.path.join(CACHE, "parts.png")
            compose(tiles, sp, a.cell)
            print("部品の一覧: %s（Read で開いて、どの番号が何かを見る）" % sp)
    if a.preview:
        write_preview(out, stem + ".preview.html" if a.preview is True else a.preview, a.duration)


def cmd_trace(a):
    """PNG を SVG のファイルにする（Canvas 以外で使うとき。credits.json の出どころも引き継ぐ）"""
    pil()
    from PIL import Image
    if a.out and len(a.images) != 1:
        die("-o は 1 枚だけのときに使えます")
    for path in a.images:
        if not os.path.isfile(path):
            die("画像がありません: " + path)
        out = a.out or os.path.splitext(path)[0] + ".svg"
        svg = trace_svg(Image.open(path).convert("RGBA"), a.detail)
        open(out, "w", encoding="utf-8").write(svg)
        cj = os.path.join(os.path.dirname(path) or ".", "credits.json")
        if os.path.exists(cj) and os.path.dirname(os.path.abspath(out)) == os.path.dirname(os.path.abspath(path)):
            credits = json.load(open(cj, encoding="utf-8"))
            if os.path.basename(path) in credits:        # 同じ絵（source が同じ）なので、点数は増えない
                credits[os.path.basename(out)] = credits[os.path.basename(path)]
                json.dump(credits, open(cj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("SVG: %s（%d KB・経路 %d 本。元の PNG は %d KB）" % (out, len(svg.encode("utf-8")) // 1024, svg.count("<path"), os.path.getsize(path) // 1024))


def cmd_check(a):
    print("Pillow %s が入っています（見本の一覧画像・canvas が使えます）" % pil().__version__)
    tracer()
    print("vtracer が入っています（canvas・trace で、絵を SVG にできます）")


def cmd_labels(a):
    cats = feed(SITE + "/feeds/posts/summary?alt=json&max-results=0")["feed"].get("category", [])
    print("カテゴリー %d 個（search の --label に書ける。2 つ書くと両方に入るもの）:" % len(cats))
    print("　".join(c["term"] for c in cats))


def main():
    ap = argparse.ArgumentParser(description="いらすとやのイラストを探して取る")
    sub = ap.add_subparsers(dest="cmd", required=True)
    tmp = os.path.join(CACHE, "sheet.png")
    s = sub.add_parser("search", help="言葉で探す")
    s.add_argument("words", nargs="*", help="探す言葉。引数ごとに別々に探してまとめる")
    s.add_argument("--label", action="append", default=[], help="カテゴリーで絞る（何度でも）")
    s.add_argument("-n", type=int, default=12, help="出す件数（既定 12）")
    s.add_argument("--max", type=int, default=60, help="1 つの言葉でサイトから取る件数（既定 60）")
    s.add_argument("--sheet", nargs="?", const=tmp, help="番号つきの見本の一覧画像を作る（場所を省くと ~/.cache/irasutoya-skill/sheet.png）")
    s.add_argument("--cell", type=int, default=200, help="見本 1 枚の大きさ（既定 200）")
    s.add_argument("--fresh", action="store_true", help="手元に覚えた結果を使わず、サイトに問い合わせ直す")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_search)
    s = sub.add_parser("show", help="記事に入っている絵（セットの中身）を見る")
    s.add_argument("ref", help="直前の search の番号か、記事の URL")
    s.add_argument("--sheet", nargs="?", const=tmp)
    s.add_argument("--cell", type=int, default=200)
    s.set_defaults(fn=cmd_show)
    s = sub.add_parser("get", help="選んだ絵を保存する")
    s.add_argument("refs", nargs="+", help="番号・番号:枚目（3:2、3:1,4、3:all）・記事の URL")
    s.add_argument("--dir", default="images", help="保存する場所（既定 images/）")
    s.add_argument("--as", dest="name", help="保存する名前（拡張子なし。1 枚のとき）")
    s.add_argument("--size", type=int, default=0, help="長い辺の大きさ。既定 0 = 元の大きさ（だいたい 400〜1000px）")
    s.set_defaults(fn=cmd_get)
    s = sub.add_parser("canvas", help="取った絵を、Canvas に描いて動かす JS にする（motion-video の custom の場面）")
    s.add_argument("images", nargs="*", help="画像（名前は拡張子を除いたファイル名）")
    s.add_argument("-o", dest="out", help="作るファイル（例 scenes/idea.js。隣に描き方の idea.draw.js ができる）")
    s.add_argument("--update", metavar="JS", help="描き方（*.draw.js）を直したあと、絵はそのままで作り直す")
    s.add_argument("--split", action="store_true", help="つながっていない塊ごとに部品に分け、別々に動かせるようにする")
    s.add_argument("--gap", type=int, default=3, help="この px までのすき間は同じ部品とみなす（既定 3）")
    s.add_argument("--min-part", type=float, default=1.5, help="絵全体のこの %% より小さい塊は、近くの部品に入れる（既定 1.5）")
    s.add_argument("--max-parts", type=int, default=8, help="部品の数の上限（既定 8）")
    s.add_argument("--raster", action="store_true", help="SVG にせず、PNG のまま入れる（塗りの質感・ぼかしを残す。拡大には弱く、重い）")
    s.add_argument("--detail", choices=sorted(DETAIL), default="fine", help="SVG にするときの細かさ（既定 fine）")
    s.add_argument("--size", type=int, help="長い辺をこの px までに縮める（既定は SVG なら縮めない・--raster なら 800。0 で縮めない）")
    s.add_argument("--no-trim", action="store_true", help="まわりの透明な余白を落とさない")
    s.add_argument("--sheet", help="部品の一覧画像の場所（既定 ~/.cache/irasutoya-skill/parts.png）")
    s.add_argument("--cell", type=int, default=200)
    s.add_argument("--preview", nargs="?", const=True, help="動きを見る HTML を作る（場所を省くと <名前>.preview.html）")
    s.add_argument("--duration", type=int, default=6000, help="動きを見る HTML で繰り返す長さ ms（既定 6000）")
    s.set_defaults(fn=cmd_canvas)
    s = sub.add_parser("trace", help="PNG を SVG のファイルにする")
    s.add_argument("images", nargs="+")
    s.add_argument("-o", dest="out", help="作る SVG（省くと、同じ場所に同じ名前の .svg）")
    s.add_argument("--detail", choices=sorted(DETAIL), default="fine")
    s.set_defaults(fn=cmd_trace)
    s = sub.add_parser("check", help="Pillow・vtracer が入っているかを確かめる")
    s.set_defaults(fn=cmd_check)
    s = sub.add_parser("labels", help="カテゴリーの一覧")
    s.set_defaults(fn=cmd_labels)
    s = sub.add_parser("count", help="取った点数を数える")
    s.add_argument("--dir", default="images")
    s.set_defaults(fn=cmd_count)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
