#!/usr/bin/env python3
"""作った HTML の、字の置かれ方を機械で確かめる（絵を目で見なくても分かること）。

  python3 layout.py 動画.html [--json] [--every 秒]

せりふ 1 つごとに、その時刻の 1 コマを描かせ、画面に描かれた字（canvas の fillText）の場所を集めて、次を見る。
  重なり   : 別々の字どうしが重なっている（名札と札・吹き出しと字幕・出どころの字どうし）
  見切れ   : 字が画面の外にはみ出している
  切れ     : せりふが途中までしか描かれていない（行が足りずに切れた）・画面に見つからない
  行数     : 字幕・吹き出しのせりふが 3 行以上になっている（2 行まで）
  隠れ     : 字（吹き出し・札）が、後から描かれた大きな塗り（せりふの箱・板）の下になっている
  折り返し : せりふが、数字と単位の間・カタカナや英字の語の途中で折れている／行の頭に句読点・助詞・小さいかながある／最後の行が 1〜2 字だけ

分からないこと: 絵と字の重なり（写真の上の字が読めるか）・吹き出しのしっぽが指す先・色の見やすさ・動いている途中の見え方。これらは目で見る。
場面の中に別の画面（offscreen の canvas）で描かれる字（図解の中の字 など）は、置かれる場所が分からないので見ない。
終了コード: 0 = 指摘なし、1 = 指摘あり、2 = 動かせなかった。"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoot as S

HOOK = r"""(function(){
  if (window.__LAY) return 1;
  var P = CanvasRenderingContext2D.prototype, f0 = P.fillText, log = [];
  window.__LAY = { log: log, on: false, cv: null, cvs: [], vert: /"format"\s*:\s*"short"/.test((document.querySelector("script[data-mv-spec]") || {}).textContent || "") };
  P.fillText = function (s, x, y) {
    try { var L = window.__LAY;
      var tall = L.vert, k = 0;   /* 縦の画面（ショート）は、字幕・絵を別の canvas に描いてから貼る。行数と折り返しを見るために、そちらの字も集める */
      if (L.on && tall && this.canvas !== L.cv) { k = L.cvs.indexOf(this.canvas); if (k < 0) { L.cvs.push(this.canvas); k = L.cvs.length - 1; } k += 1; }
      if (L.on && (this.canvas === L.cv || tall) && String(s).replace(/[\s　]/g, "").length) {
        var m = this.measureText(s), T = this.getTransform(), al = this.textAlign, w = m.width,
            x0 = x - (m.actualBoundingBoxLeft !== undefined ? m.actualBoundingBoxLeft : (al === "center" ? w / 2 : al === "right" || al === "end" ? w : 0)),
            x1 = x + (m.actualBoundingBoxRight !== undefined ? m.actualBoundingBoxRight : w),
            y0 = y - (m.fontBoundingBoxAscent || m.actualBoundingBoxAscent || 0) * .78, y1 = y + (m.actualBoundingBoxDescent || 0),
            pts = [[x0, y0], [x1, y0], [x0, y1], [x1, y1]].map(function (p) { return [T.a * p[0] + T.c * p[1] + T.e, T.b * p[0] + T.d * p[1] + T.f]; }),
            xs = pts.map(function (p) { return p[0]; }), ys = pts.map(function (p) { return p[1]; });
        log.push({ s: String(s), x: Math.min.apply(null, xs), y: Math.min.apply(null, ys), X: Math.max.apply(null, xs), Y: Math.max.apply(null, ys),
                   a: this.globalAlpha, c: String(this.fillStyle), k: k });
      } } catch (e) {}
    return f0.apply(this, arguments);
  };
  /* 字の上に、後から描かれる大きな塗り（せりふの箱・板）を集める: 道（path）の点を覚えておき、fill のときに、その範囲を記録する。字が「後から描かれた箱の下」になっていないかを見るため */
  var pt = function (c, x, y) { var T = c.getTransform(), X = T.a * x + T.c * y + T.e, Y = T.b * x + T.d * y + T.f, b = c.__pb;
    if (!b) c.__pb = [X, Y, X, Y]; else { if (X < b[0]) b[0] = X; if (Y < b[1]) b[1] = Y; if (X > b[2]) b[2] = X; if (Y > b[3]) b[3] = Y; } };
  var wrapP = function (name, fn) { var g0 = P[name]; if (!g0) return; P[name] = function () { try { fn(this, arguments); } catch (e) {} return g0.apply(this, arguments); }; };
  wrapP("beginPath", function (c) { c.__pb = null; });
  wrapP("moveTo", function (c, a) { pt(c, a[0], a[1]); });
  wrapP("lineTo", function (c, a) { pt(c, a[0], a[1]); });
  wrapP("arcTo", function (c, a) { pt(c, a[0], a[1]); pt(c, a[2], a[3]); });
  wrapP("quadraticCurveTo", function (c, a) { pt(c, a[2], a[3]); });
  wrapP("bezierCurveTo", function (c, a) { pt(c, a[4], a[5]); });
  wrapP("rect", function (c, a) { pt(c, a[0], a[1]); pt(c, a[0] + a[2], a[1] + a[3]); });
  wrapP("roundRect", function (c, a) { pt(c, a[0], a[1]); pt(c, a[0] + a[2], a[1] + a[3]); });
  wrapP("arc", function (c, a) { pt(c, a[0] - a[2], a[1] - a[2]); pt(c, a[0] + a[2], a[1] + a[2]); });
  var alphaOf = function (st) { if (typeof st !== "string") return 1; var m = /rgba?\(([^)]+)\)/.exec(st); if (m) { var q = m[1].split(","); return q.length > 3 ? parseFloat(q[3]) : 1; }
    return /^#[0-9a-f]{8}$/i.test(st) ? parseInt(st.slice(7), 16) / 255 : 1; };
  /* 塗りが、前に描いた字を隠すか: 字の左・まん中・右の 3 点のうち 2 点以上が、塗りの形の中にあるか（道の形そのもので見る。四角い範囲で見ると、吹き出しのしっぽの分だけ広く取って、となりの字を「隠れた」と数えた） */
  var cover = function (c, inside, x, y, X, Y) { var L = window.__LAY; if (!L.on || c.canvas !== L.cv) return; var a = c.globalAlpha * alphaOf(c.fillStyle);
    if (a < .5 || (X - x) * (Y - y) < 9000 || c.globalCompositeOperation !== "source-over") return;
    var big = (X - x) * (Y - y) > c.canvas.width * c.canvas.height * .6;
    for (var i = 0; i < log.length; i++) { var t = log[i]; if (t.cover || t.k || t.mark || t.a < .5) continue;
      if (t.X < x || t.x > X || t.Y < y || t.y > Y) continue;
      var cy = (t.y + t.Y) / 2, w = t.X - t.x, n = [[t.x + w * .15, cy], [t.x + w * .5, cy], [t.X - w * .15, cy]].filter(function (q) { return inside(q[0], q[1]); }).length;
      if (n >= 2) log.push({ cover: 1, of: i, big: big, x: x, y: y, X: X, Y: Y, a: a }); } };
  wrapP("fill", function (c) { var b = c.__pb; if (b) cover(c, function (px, py) { return c.isPointInPath(px, py); }, b[0], b[1], b[2], b[3]); });
  wrapP("fillRect", function (c, a) { var T = c.getTransform(), p = [[a[0], a[1]], [a[0] + a[2], a[1] + a[3]]].map(function (q) { return [T.a * q[0] + T.c * q[1] + T.e, T.b * q[0] + T.d * q[1] + T.f]; });
    var x = Math.min(p[0][0], p[1][0]), y = Math.min(p[0][1], p[1][1]), X = Math.max(p[0][0], p[1][0]), Y = Math.max(p[0][1], p[1][1]);
    cover(c, function (px, py) { return px >= x && px <= X && py >= y && py <= Y; }, x, y, X, Y); });
  return 1; })()"""

DRAW = r"""(function(ms){ var L = window.__LAY; L.log.length = 0; L.cv = __MV__.drawAt(ms); L.on = true; __MV__.drawAt(ms); L.on = false;
  return { w: L.cv.width, h: L.cv.height, items: L.log.slice() }; })(%d)"""

CUES = r"""__MV__.CUES.map(function(c){ return { a: c.a, b: c.b, text: c.text || "", who: c.who || "" }; })"""

CUT = "\x00切れ:"   # rows_of が、描かれなかった残りを最後の行として返すときの印
PUNCT_HEAD = re.compile(r"^[、。，．！？!?」』）)…ー〜・ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ]")
plain = lambda s: re.sub(r"[\s　\u200b]|\*\*", "", s or "")   # U+200B: 台本で決めた折る所（<br>）


def fmt(ms):
    return "%d:%04.1f" % (ms // 60000, ms % 60000 / 1000)


def boxes(items, W, H):
    """描かれた字を、見える物だけ・同じ物を 1 つにまとめて返す（縁取り・影で、同じ字が少しずれて何度も描かれる）。"""
    out = []
    for it in items:
        if it["a"] < .5 or it["X"] - it["x"] < 2:
            continue
        if it.get("k"):   # 別の canvas の字（縦の画面）: 場所は貼る前のものなので、ほかの canvas の字と混ざらないよう、上下に大きく離す
            it = dict(it, y=it["y"] + it["k"] * 100000, Y=it["Y"] + it["k"] * 100000)
        for o in out:
            if o["s"] == it["s"] and abs(o["x"] - it["x"]) < 14 and abs(o["y"] - it["y"]) < 14:
                o["x"], o["y"], o["X"], o["Y"] = min(o["x"], it["x"]), min(o["y"], it["y"]), max(o["X"], it["X"]), max(o["Y"], it["Y"])
                break
        else:
            out.append(dict(it))
    return out


def rows_of(bs, text):
    """字幕・吹き出しに描かれた、このせりふの行（上から）。見つからなければ None（1 字ずつ描く演出・縦書き など）。"""
    target = plain(text)
    if len(target) < 2:
        return None
    cand = [b for b in bs if len(plain(b["s"])) >= 1 and plain(b["s"]) in target]
    cand.sort(key=lambda b: (round(b["y"] / 12), b["x"]))
    rows = []
    for b in cand:
        h = b["Y"] - b["y"]
        if rows and abs(rows[-1][0]["y"] - b["y"]) < h * .6 and -h < b["x"] - rows[-1][-1]["X"] < h * 2:   # 同じ高さでも、横に離れた字は別の行（字幕の 2 行目と、同じ言葉の吹き出しが横に並ぶ）
            rows[-1].append(b)
        else:
            rows.append([b])
    lines = ["".join(plain(b["s"]) for b in sorted(r, key=lambda b: b["x"])) for r in rows]
    span = lambda r: (min(b["x"] for b in r), max(b["X"] for b in r), sum(b["Y"] - b["y"] for b in r) / len(r))
    # せりふの全文になる行の組を探す。同じ言葉が名札・吹き出しにもあるので、頭の行と字の大きさが同じで、横の位置が重なる行だけをつなぐ（ほかの行は飛ばす）
    best = None
    for i in range(len(lines)):
        x0, x1, h0 = span(rows[i])
        acc, used = "", []
        for j in range(i, len(lines)):
            xa, xb, hj = span(rows[j])
            if j > i and (abs(hj - h0) > h0 * .15 or xb < x0 - h0 * 3 or xa > x1 + h0 * 3):
                continue
            if not target.startswith(acc + lines[j]):
                if j == i:
                    break
                continue
            acc += lines[j]
            used.append(j)
            if acc == target:
                return [lines[n] for n in used], [b for n in used for b in rows[n]]
            if len(acc) >= max(6, len(target) * .5) and (best is None or len(acc) > len(best[2])):
                best = ([lines[n] for n in used], [b for n in used for b in rows[n]], acc)
    if best:   # せりふの頭から途中までしか描かれていない（行が足りずに切れた）
        return best[0] + [CUT + target[len(best[2]):]], best[1]
    return None


AUX = r"(み(る|た|て|よ|ま|れ)|しま|い(る|た|て|ま|く|っ|き)|お(く|い|き|こ)|く(る|れ)|き(た|て|ま)|ほし|あげ|もら)"   # 「〜て」に続く動詞（見て｜みたい、割れて｜しまう）


def wrap_faults(lines):
    out = []
    for a, b in zip(lines, lines[1:]):
        if re.search(r"[0-9０-９][〜～~－-]$", a) and re.match(r"[0-9０-９]", b):
            out.append("数の範囲の途中で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[0-9０-９]$", a) and not re.match(r"[、。！？!?「『（(…\s]", b):
            out.append("数字の後ろで折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[0-9０-９][かヶケカ]$", a) and re.match(r"[一-龠々]", b):
            out.append("数字と単位の間で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[ァ-ヶー]$", a) and re.match(r"[ァ-ヶー]", b):
            out.append("カタカナの語の途中で折れている（%s／%s）" % (a[-5:], b[:5]))
        elif re.search(r"[A-Za-z]$", a) and re.match(r"[A-Za-z]", b):
            out.append("英字の語の途中で折れている（%s／%s）" % (a[-5:], b[:5]))
        elif re.search(r"[一-龠々]$", a) and re.match(r"[一-龠々]", b):
            out.append("漢字の語の途中で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[ァ-ヶー]$", a) and re.match(r"[一-龠々]{1,2}(?![一-龠々])", b):
            out.append("カタカナ＋漢字の語の途中で折れている（%s／%s）" % (a[-5:], b[:4]))
        elif re.search(r"[一-龠々]$", a) and re.match(r"[ぁ-ん]", b) and not re.match(r"(は|が|を|に|で|と|も|の|へ|や|か|な|だ|じゃ|って|から|まで|より|みたい|ほど|くらい|ぐらい|など|しか|さえ|こそ|です|でしょ|らしい|っス|ね|よ)", b):   # 助詞・だ／です・みたい などで始まる行は、語の切れ目
            out.append("送りがなの前で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[一-龠々]{2}$", a) and re.match(r"[ァ-ヶー]{2,6}(?![ァ-ヶー])", b):
            out.append("漢字＋カタカナの語の途中で折れている（%s／%s）" % (a[-4:], b[:6]))
        elif re.match(r"[てで]" + AUX, b) and re.search(r"[ぁ-ん一-龠]$", a):
            out.append("「〜て＋動詞」が、行の頭に割れている（%s／%s）" % (a[-4:], b[:5]))
        elif re.match(r"[（(]", b):
            out.append("行の頭が、読みがなのかっこ（%s／%s）" % (a[-4:], b[:6]))
        elif re.search(r"(^|[、。！？!?…\s「『（(])[おご]$", a) and re.match(r"[一-龠々]", b):
            out.append("「お」「ご」と、続く語の間で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"(で|なん)$", a) and re.match(r"(で)?しょ", b):
            out.append("「〜でしょう」の途中で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[てで]$", a) and re.match(AUX, b):
            out.append("「〜て」と、続く動詞の間で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"(^|[、。！？!?…\s])(もう|あと|まだ|その|この|あの|どの|ある)$", a):
            out.append("短い語が、行の終わりに残っている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[ぁ-ん]$", a) and re.match(r"(られ|れ[るたて]|させ|せ[るたて])", b):
            out.append("語尾の前で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif PUNCT_HEAD.match(b):
            out.append("行の頭に、句読点・小さいかな・のばす音がある（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[「『（(]$", a):
            out.append("行の終わりが、開くかっこ（%s／%s）" % (a[-4:], b[:4]))
    if len(lines) >= 2 and len(re.sub(r"[、。！？!?…「『（(]", "", lines[0])) <= 1:
        out.append("最初の行が 1 字だけ（%s／%s）" % (lines[0], lines[1][:4]))
    if len(lines) >= 2 and len(re.sub(r"[、。！？!?…」』）)]", "", lines[-1])) <= 2:
        out.append("最後の行が 1〜2 字だけ（／%s）" % lines[-1])
    return out


def hidden(items, W, H):
    """後から描かれた大きな塗り（せりふの箱・板）の下になった字。items: 描いた順（字と、「どの字を隠したか」の印 cover・of）。→ [(字, 塗りの範囲)]"""
    out, seen = [], set()
    for j, c in enumerate(items):
        if not c.get("cover") or c.get("big") or c.get("of") in seen:   # big: 画面いっぱいの塗り（場面の切り替え・暗転）は、隠すためのもの
            continue
        b = items[c["of"]]
        if len(plain(b["s"])) < 2:
            continue
        again = any(not d.get("cover") and d["s"] == b["s"] and abs(d["x"] - b["x"]) < 4 and abs(d["y"] - b["y"]) < 4 for d in items[j + 1:])   # 塗りの後に、同じ字をもう一度描いている（ふちどり・重ね描き）
        if not again:
            seen.add(c["of"])
            out.append((b["s"], c))
    return out


def overlaps(bs, own):
    """別々の字どうしの重なり。own: 同じせりふの行（行どうしは見ない）。"""
    out, seen = [], set()
    ids = {id(b) for b in own}
    for i, p in enumerate(bs):
        for q in bs[i + 1:]:
            if p["s"] == q["s"] or (id(p) in ids and id(q) in ids):
                continue
            if (p.get("mark") or q.get("mark")) and re.fullmatch(r"[!?！？♪…・\s]+", (q if p.get("mark") else p)["s"]):   # 印が自分で描く字（！？）
                continue
            if min(p.get("a", 1), q.get("a", 1)) < .9:   # 写真が入れ替わる途中（前の名札が消えかけ・次の名札が出かけ）は、重なりに数えない
                continue
            if min(len(plain(p["s"])), len(plain(q["s"]))) < 2:   # 1 字ずつ描く字（動く題・強調）は、となりと触れる
                continue
            hp, hq = (p["Y"] - p["y"]) * .12, (q["Y"] - q["y"]) * .12   # 行の上下のあきは、重なりに数えない
            w = min(p["X"], q["X"]) - max(p["x"], q["x"])
            h = min(p["Y"] - hp, q["Y"] - hq) - max(p["y"] + hp, q["y"] + hq)
            if w <= 3 or h <= 3:
                continue
            small = min((p["X"] - p["x"]) * (p["Y"] - p["y"]), (q["X"] - q["x"]) * (q["Y"] - q["y"]))
            if w * h < small * .12:
                continue
            key = tuple(sorted((p["s"], q["s"])))
            if key not in seen:
                seen.add(key)
                out.append("「%s」と「%s」" % (p["s"][:18], q["s"][:18]))
    return out


def check(html, every=0, browser=None):
    """[{at, kind, what}] を返す。kind: 重なり・見切れ・行数・折り返し。"""
    own = browser is None
    chrome = S.find_chrome()
    if not chrome and own:
        raise RuntimeError("Chrome がありません")
    br = browser or S.Browser(chrome, (1280, 720))
    try:
        if own:
            br.open(html)
        br.eval(HOOK)
        cues = br.eval(CUES)
        times = []
        for c in cues:
            d = c["b"] - c["a"]
            times.append((int(c["a"] + min(1400, d * .7)), c))
        if every:
            end = max(c["b"] for c in cues) if cues else 0
            times += [(int(t * 1000), None) for t in range(0, int(end / 1000), int(every))]
        times.sort(key=lambda x: x[0])
        found, last, seen_cue, n_cue = [], {}, 0, 0
        prev_out, prev_ms = {}, -1e9
        unread = []
        prev_hid, told_hid = set(), set()
        for ms, cue in times:
            r = br.eval(DRAW % ms)
            W, H = r["w"], r["h"]
            now_hid = {t for t, _ in hidden(r["items"], W, H)}
            for t in sorted(now_hid & prev_hid - told_hid):   # 続けて 2 回見えたものだけ（動いている途中の一瞬は数えない）
                told_hid.add(t)
                found.append({"at": ms, "kind": "隠れ", "what": "「%s」が、後から描かれた箱（せりふの箱・板）の下になっている" % t[:20]})
            prev_hid = now_hid
            bs = boxes([x for x in r["items"] if not x.get("cover")], W, H)
            mine = []
            if cue and cue["text"]:
                n_cue += 1
                got = rows_of(bs, cue["text"])
                if not got:
                    unread.append((ms, cue["text"]))
                if got:
                    seen_cue += 1
                    lines, mine = got
                    if lines and lines[-1].startswith(CUT):
                        found.append({"at": ms, "kind": "切れ", "what": "せりふが途中で切れている（「%s」まで。「%s」が出ない）" % ("".join(lines[:-1])[-12:], lines[-1][len(CUT):][:16])})
                        lines = lines[:-1]
                    if len(lines) >= 3:
                        found.append({"at": ms, "kind": "行数", "what": "%d 行: %s" % (len(lines), "／".join(lines))})
                    for w in wrap_faults(lines):
                        found.append({"at": ms, "kind": "折り返し", "what": w})
            now_out = {}
            for b in bs:
                if not b.get("k") and (b["x"] < -4 or b["y"] < -4 or b["X"] > W + 4 or b["Y"] > H + 4):
                    now_out[b["s"]] = b
            for txt_, b in now_out.items():   # 続けて 2 回、外にあるものだけ（札が横から入ってくる途中の 1 コマは、見切れではない）
                k = ("見切れ", txt_)
                if txt_ in prev_out and ms - prev_ms >= 700 and ms - last.get(k, -1e9) > 8000:
                    found.append({"at": ms, "kind": "見切れ", "what": "「%s」が画面の外へ（左 %d・上 %d・右 %d・下 %d／画面 %d×%d）" % (txt_[:24], b["x"], b["y"], b["X"], b["Y"], W, H)})
                    last[k] = ms
            if not now_out or ms - prev_ms >= 700:
                prev_out, prev_ms = now_out, ms
            for o in overlaps(bs, mine):
                k = ("重なり", o)
                if ms - last.get(k, -1e9) > 4000:
                    found.append({"at": ms, "kind": "重なり", "what": o})
                last[k] = ms
        if n_cue and seen_cue >= n_cue * .8:   # ほとんど読めているのに読めなかったせりふ: 描かれていないか、形が崩れている。問題なしと数えない（2026-10-06: 切れたせりふを見逃した）
            for ms, tx in unread:
                found.append({"at": ms, "kind": "切れ", "what": "せりふが画面に見つからない（描かれていない・切れている・字が欠けている）: %s" % tx[:24]})
        check.stats = {"cues": n_cue, "read": seen_cue, "frames": len(times)}   # せりふのうち、描かれた行を読み取れた数（少なければ、行数・折り返しは見られていない）
        return found
    finally:
        if own:
            br.close()


def main():
    ap = argparse.ArgumentParser(description="作った HTML の字の重なり・見切れ・行数・折り返しを、機械で確かめる")
    ap.add_argument("html")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--every", type=float, default=0, help="せりふの時刻のほかに、この秒数おきにも見る")
    a = ap.parse_args()
    try:
        found = check(a.html, a.every)
    except Exception as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(found, ensure_ascii=False, indent=1))
    else:
        st = getattr(check, "stats", {})
        print("見た画面: %d／せりふ %d のうち、描かれた行を読み取れたもの %d" % (st.get("frames", 0), st.get("cues", 0), st.get("read", 0)))
        for k in ("重なり", "見切れ", "隠れ", "切れ", "行数", "折り返し"):
            rows = [f for f in found if f["kind"] == k]
            print("%s: %d 件" % (k, len(rows)))
            for f in rows:
                print("  %s  %s" % (fmt(f["at"]), f["what"]))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
