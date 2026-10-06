#!/usr/bin/env python3
"""作った HTML の、字の置かれ方を機械で確かめる（絵を目で見なくても分かること）。

  python3 layout.py 動画.html [--json] [--every 秒]

せりふ 1 つごとに、その時刻の 1 コマを描かせ、画面に描かれた字（canvas の fillText）の場所を集めて、次を見る。
  重なり   : 別々の字どうしが重なっている（名札と札・吹き出しと字幕・出どころの字どうし）
  見切れ   : 字が画面の外にはみ出している
  行数     : 字幕・吹き出しのせりふが 3 行以上になっている（2 行まで）
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
  return 1; })()"""

DRAW = r"""(function(ms){ var L = window.__LAY; L.log.length = 0; L.cv = __MV__.drawAt(ms); L.on = true; __MV__.drawAt(ms); L.on = false;
  return { w: L.cv.width, h: L.cv.height, items: L.log.slice() }; })(%d)"""

CUES = r"""__MV__.CUES.map(function(c){ return { a: c.a, b: c.b, text: c.text || "", who: c.who || "" }; })"""

PUNCT_HEAD = re.compile(r"^[、。，．！？!?」』）)…ー〜・ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ]")
plain = lambda s: re.sub(r"[\s　]|\*\*", "", s or "")


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
        if rows and abs(rows[-1][0]["y"] - b["y"]) < (b["Y"] - b["y"]) * .6:
            rows[-1].append(b)
        else:
            rows.append([b])
    lines = ["".join(plain(b["s"]) for b in sorted(r, key=lambda b: b["x"])) for r in rows]
    # せりふの全文になる、続いた行の組を探す（同じ言葉が名札などにもあるとき、余分な行が混ざる）
    for i in range(len(lines)):
        acc = ""
        for j in range(i, len(lines)):
            acc += lines[j]
            if acc == target:
                return lines[i:j + 1], [b for r in rows[i:j + 1] for b in r]
            if not target.startswith(acc):
                break
    return None


def wrap_faults(lines):
    out = []
    for a, b in zip(lines, lines[1:]):
        if re.search(r"[0-9０-９]$", a) and not re.match(r"[、。！？!?「『（(…\s]", b):
            out.append("数字の後ろで折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[0-9０-９][かヶケカ]$", a) and re.match(r"[一-龠々]", b):
            out.append("数字と単位の間で折れている（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[ァ-ヶー]$", a) and re.match(r"[ァ-ヶー]", b):
            out.append("カタカナの語の途中で折れている（%s／%s）" % (a[-5:], b[:5]))
        elif re.search(r"[A-Za-z]$", a) and re.match(r"[A-Za-z]", b):
            out.append("英字の語の途中で折れている（%s／%s）" % (a[-5:], b[:5]))
        elif PUNCT_HEAD.match(b):
            out.append("行の頭に、句読点・小さいかな・のばす音がある（%s／%s）" % (a[-4:], b[:4]))
        elif re.search(r"[「『（(]$", a):
            out.append("行の終わりが、開くかっこ（%s／%s）" % (a[-4:], b[:4]))
    if len(lines) >= 2 and len(re.sub(r"[、。！？!?…」』）)]", "", lines[-1])) <= 2:
        out.append("最後の行が 1〜2 字だけ（／%s）" % lines[-1])
    return out


def overlaps(bs, own):
    """別々の字どうしの重なり。own: 同じせりふの行（行どうしは見ない）。"""
    out, seen = [], set()
    ids = {id(b) for b in own}
    for i, p in enumerate(bs):
        for q in bs[i + 1:]:
            if p["s"] == q["s"] or (id(p) in ids and id(q) in ids):
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
        for ms, cue in times:
            r = br.eval(DRAW % ms)
            W, H = r["w"], r["h"]
            bs = boxes(r["items"], W, H)
            mine = []
            if cue and cue["text"]:
                n_cue += 1
                got = rows_of(bs, cue["text"])
                if got:
                    seen_cue += 1
                    lines, mine = got
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
        for k in ("重なり", "見切れ", "行数", "折り返し"):
            rows = [f for f in found if f["kind"] == k]
            print("%s: %d 件" % (k, len(rows)))
            for f in rows:
                print("  %s  %s" % (fmt(f["at"]), f["what"]))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
