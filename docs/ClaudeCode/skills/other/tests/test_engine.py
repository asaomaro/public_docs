"""engine.js をブラウザ（画面なしの Chrome）で動かして確かめる。Chrome が無ければ飛ばす。

  - 1 文の声が字幕 2 つにまたがるとき、2 つ目の字幕は前の声の続き（新しく鳴らさない）
  - 字幕は、カタカナ語・英単語の途中で折らない（2026-10:「フレームワー／ク」）
  - 書き出し（OfflineAudioContext）に、ファイルの BGM が入る（2026-10: fetch を使っていて、書き出しで BGM が無音だった）
  - 場面の music で、その場面から曲が替わる
"""
import json
import os
import re
import shutil
import struct
import subprocess
import unittest
from unittest import mock

import fakes
import build

CHROME = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)


class Chrome:
    """画面なしの Chrome を DevTools Protocol（パイプ）で動かす。仮想時間（--virtual-time-budget）を使わず、本当の時間で Promise を待つ
    （仮想時間の下では、長い音の書き出し〔OfflineAudioContext〕が終わる前に打ち切られるため）。"""

    def __init__(self):
        r3, self.w3 = os.pipe()      # Chrome が読む（fd 3）
        self.r4, w4 = os.pipe()      # Chrome が書く（fd 4）
        self.dir = fakes.tmpdir()

        def fds():   # Chrome は fd 3 から読み、fd 4 へ書く。pipe の fd は exec で閉じる印が付くので、継承できるようにする
            for src, dst in ((r3, 3), (w4, 4)):
                if src != dst:
                    os.dup2(src, dst)
                os.set_inheritable(dst, True)
        self.p = subprocess.Popen([CHROME, "--headless=new", "--no-sandbox", "--remote-debugging-pipe", "--user-data-dir=" + self.dir,
                                   "--autoplay-policy=no-user-gesture-required", "about:blank"],
                                  preexec_fn=fds, close_fds=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(r3)
        os.close(w4)
        self.buf, self.n = b"", 0
        tid = next(t["targetId"] for t in self.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.call("Target.attachToTarget", targetId=tid, flatten=True)["sessionId"]

    def call(self, method, session=None, **params):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params}
        if session:
            msg["sessionId"] = session
        os.write(self.w3, json.dumps(msg).encode() + b"\0")
        while True:
            while b"\0" not in self.buf:
                chunk = os.read(self.r4, 1 << 20)
                if not chunk:
                    raise AssertionError("Chrome が終わった")
                self.buf += chunk
            raw, self.buf = self.buf.split(b"\0", 1)
            m = json.loads(raw)
            if m.get("id") == self.n:
                if "error" in m:
                    raise AssertionError(m["error"])
                return m["result"]

    def open(self, html):
        path = os.path.join(self.dir, "t%d.html" % self.n)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self.call("Page.enable", self.sid)
        self.call("Page.navigate", self.sid, url="file://" + path)
        return self.eval("new Promise(function(ok){function w(){window.__MV__?setTimeout(ok,300):setTimeout(w,100)};w()})")

    def eval(self, js):
        r = self.call("Runtime.evaluate", self.sid, expression=js, awaitPromise=True, returnByValue=True, timeout=120000)
        if r.get("exceptionDetails"):
            raise AssertionError(r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"])
        return r["result"].get("value")

    def close(self):
        self.p.kill()
        self.p.wait()


def build_html(spec, voicevox=True):
    d = fakes.tmpdir()
    path = fakes.write_json(os.path.join(d, "e.json"), spec)
    if isinstance(spec.get("audio", {}).get("music"), dict) and spec["audio"]["music"].get("file"):
        fakes.write_wav(os.path.join(d, spec["audio"]["music"]["file"]), [(2.0, True)])
    with fakes.fake_voicevox(alive=voicevox), fakes.quiet():
        s = build.load(path)
        return build.build_html(s, "midnight", "studio", True)


@unittest.skipUnless(CHROME or os.environ.get("REQUIRE_CHROME"), "Chrome が無い")
class Engine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHROME:   # CI（REQUIRE_CHROME=1）では、飛ばさずに落とす
            raise AssertionError("Chrome が無いので engine.js を確かめられません")
        cls.chrome = Chrome()

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    def run_js(self, html, js):
        self.chrome.open(html)
        return self.chrome.eval(js)
    def test_sentence_voice_spans_cues(self):
        sp = {"title": "t", "lang": "ja", "audio": {"narration": True, "music": None, "sfx": False, "voice": {"engine": "voicevox", "speaker": "四国めたん"}},
              "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t",
                                                       "narration": ["ブラウザでも、引数なしのソーダで開く端末版でも、同じ画面をそのまま操作できます。", "短い文です。"]}]}]}
        cues = self.run_js(build_html(sp), """(function(){var C=__MV__.CUES;return C.map(function(c){return {
            voice:!!(c.line&&c.line.voice), cont:!!c.par, sameKey: c.par? c.key===c.par.key : null, joins: c.par? Math.abs(c.a-c.par.b)<=5 : null}})})()""")
        self.assertEqual([c["cont"] for c in cues], [False, True, False])
        self.assertTrue(cues[1]["sameKey"] and cues[1]["joins"])

    def test_caption_wrap_keeps_words(self):
        sp = {"title": "t", "lang": "ja", "audio": {"narration": False}, "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t"}]}]}
        cases = ["「React は MVC フレームワークではない」って。", "新しいアーキテクチャのパフォーマンスとセキュリティを検証した",
                 "TypeScript で書かれた JavaScript のライブラリを使う"]
        # 幅は字幕でいちばん狭い 1080（白い箱）。それより狭いと、長いカタカナ語 2 つは 2 行に収まらない
        # 2 行の長さをそろえる所（字幕の幅の 0.58 倍で折り直す。2026-10 の「フレームワー／ク」はここで起きた）も、上限 1180 で同じく見る
        arr = ",".join(json.dumps(c, ensure_ascii=False) for c in cases)
        got = self.run_js(build_html(sp, voicevox=False), "[%s].map(function(t){return __MV__.capWrap(t, 1080, 56)}).concat([%s].map(function(t){"
                          "return __MV__.capWrap(t, Math.max(540, t.length * 56 * .58), 56, 1180)}))" % (arr, arr))
        for text, lines in zip(cases + cases, got):
            with self.subTest(text):
                self.assertEqual("".join(lines).replace(" ", ""), text.replace(" ", ""))
                for a, b in zip(lines, lines[1:]):
                    self.assertFalse(re.search(r"[ァ-ヶー]$", a) and re.match(r"[ァ-ヶー]", b), lines)   # カタカナ語の途中
                    self.assertFalse(re.search(r"[A-Za-z]$", a) and re.match(r"[A-Za-z]", b), lines)   # 英単語の途中
                    self.assertFalse(re.match(r"[、。」）]", b), lines)                                  # 行頭の句読点・閉じかっこ

    def test_vertical_frame(self):
        """ショート（talk.format: "short"）: 舞台が縦になり、題の下に絵・字幕・立ち絵が描かれる（下の端まで何かが描かれている）。"""
        sp = {"title": "縦の題", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": False}, "talk": {"format": "short"},
              "cast": {"a": {"name": "A", "color": "#e0457b", "side": "left"}, "b": {"name": "B", "color": "#3aa657", "side": "right"}},
              "chapters": [{"title": "c", "scenes": [{"type": "talk", "cast": ["a", "b"], "lines": [{"who": "a", "text": "縦の画面でも話すわ。"}, {"who": "b", "text": "そうなのだ。"}]}]}]}
        js = """(function(){var cv=document.getElementById("mv-canvas"),r=cv.getBoundingClientRect();__MV__.seek(900);
          var g=cv.getContext("2d"),w=cv.width,h=cv.height,n=0,d=g.getImageData(0,Math.round(h*.8),w,Math.round(h*.18)).data,seen={};
          for(var i=0;i<d.length;i+=4){seen[(d[i]>>4)+","+(d[i+1]>>4)+","+(d[i+2]>>4)]=1}
          return {ratio:r.width/r.height, cw:w, ch:h, colors:Object.keys(seen).length}})()"""
        got = self.run_js(build_html(sp, voicevox=False), js)
        self.assertAlmostEqual(got["ratio"], 9 / 16, delta=.02)
        self.assertLess(got["cw"], got["ch"])
        self.assertGreater(got["colors"], 3, "下の帯に立ち絵が描かれていない")
        sp["talk"] = {}
        self.assertAlmostEqual(self.run_js(build_html(sp, voicevox=False), js)["ratio"], 16 / 9, delta=.05)

    def test_transition_sounds(self):
        """章・場面の切り替えの音は audio.sfx.transitionVolume で小さくでき、締めのクレジット（variant: credits）へは鳴らさずに替わる。"""
        def spec(tv):
            sfx = {"kit": "playful", "density": "low"}
            if tv is not None:
                sfx["transitionVolume"] = tv
            return {"title": "t", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": sfx},
                    "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "一"}]}, {"title": "b", "scenes": [{"type": "title", "title": "二"}]},
                                 {"title": "おわりに", "scenes": [{"type": "end", "variant": "credits", "title": "おわり", "lines": ["x"]}]}]}
        js = """(function(){var S=__MV__.segments?0:0, sc=[], q=__MV__.SFX; __MV__.seek(0);
          var ch=__MV__.CHAPTERS.map(function(c){return c.t});
          return {starts: ch, ev: q.map(function(e){return {T:e.T, v:e.v, name:e.name}})}})()"""
        full = self.run_js(build_html(spec(None), voicevox=False), js)
        half = self.run_js(build_html(spec(.5), voicevox=False), js)
        def near(got, T):
            return [e for e in got["ev"] if abs(e["T"] - T) < 200]
        b0, e0 = full["starts"][1], full["starts"][2]
        self.assertTrue(near(full, b0), "章の切り替えの音が無い: %r" % full)
        self.assertAlmostEqual(near(half, half["starts"][1])[0]["v"], near(full, b0)[0]["v"] * .5, places=3)
        self.assertFalse(near(full, e0), "クレジットへの切り替えで音が鳴る")

    def test_sfx_loudness_is_levelled(self):
        """2026-10-03: 章の切り替えの音（twinkle）だけが、ほかの効果音より 10 dB 近く大きく聞こえた（波形の山はそろっていたが、実効値がばらばらだった）。
        sfx_levels.json の倍率を掛けると、よく使う音の実効値の開きが小さくなる。"""
        import math
        import sfx_levels
        g = sfx_levels.gains(sfx_levels.load())
        self.assertGreater(len(g), 150, "sfx_levels.json が無いか、古い（python3 sfx_levels.py で測り直す）")
        sp = {"title": "t", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": {"kit": "playful"}}, "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t"}]}]}
        names = ["twinkle", "sparkle", "pop", "hyoshigi", "bling", "stab"]
        js = "Promise.all(%s.map(function(n){return Promise.all([__MV__.sfxLevel(n), __MV__.sfxLevel(n,{raw:false})])}))" % json.dumps(names)
        got = self.run_js(build_html(sp, voicevox=False), js)
        raw = [20 * math.log10(a["rms"]) for a, _ in got]
        lev = [20 * math.log10(b["rms"]) for _, b in got]
        self.assertGreater(max(raw) - min(raw), 8, raw)
        self.assertLess(max(lev) - min(lev), 4, lev)
        self.assertEqual(sorted(self.run_js(build_html(sp, voicevox=False), "__MV__.sfxNames()")), sorted(g), "効果音が増減した: python3 sfx_levels.py で測り直す")

    def test_end_scene_plain(self):
        """motion-video の締め: 題の頭の 1 字を輪に入れた紋章（「ご」）は出さない・行が多くてもはみ出さない・最後は映像と音を消す（endFade）。"""
        def spec(n, **kw):
            end = dict({"type": "end", "title": "ご視聴ありがとうございました", "lines": ["行 %d" % i for i in range(n)]}, **kw)
            return {"title": "t", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": False},
                    "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t"}]}, {"title": "z", "scenes": [end]}]}
        js = """new Promise(function(ok){var seen=[], o=CanvasRenderingContext2D.prototype.fillText; CanvasRenderingContext2D.prototype.fillText=function(s,x,y){seen.push([String(s),x,y]);return o.apply(this,arguments)};
          __MV__.seek(__MV__.DUR-2500); setTimeout(function(){ CanvasRenderingContext2D.prototype.fillText=o;
          ok({texts: seen.map(function(a){return a[0]}), maxY: Math.max.apply(null, [0].concat(seen.map(function(a){return a[2]}))), dur: __MV__.DUR, fade: __MV__.endFade}) }, 500)})"""
        for n in (3, 12):
            got = self.run_js(build_html(spec(n), voicevox=False), js)
            self.assertNotIn("ご", got["texts"], "題の頭の 1 字の紋章が出ている")
            self.assertLessEqual(got["maxY"], 1000, "行が画面の下にはみ出す（%d 行）" % n)
            self.assertTrue(any("行 %d" % (n - 1) in x for x in got["texts"]), "最後の行が出ていない")
        got = self.run_js(build_html(spec(3, markText="舵"), voicevox=False), js)
        self.assertIn("舵", got["texts"], "markText を書いたときは紋章を出す")
        self.assertEqual(got["fade"], 2000)

    def test_caption_breaks_at_punctuation(self):
        """2026-10-03: 3 人の台本（字幕の幅が狭い）で、字幕が「すれ違うた／めの場所」「行きやすいそう／よ。」と折れ、3 行目が箱の外に切れた。
        句読点の後で 2 行に分けられるなら、そこで折る（収まらなければ、字を 8 割まで小さくして探す）。"""
        sp = {"title": "t", "lang": "ja", "audio": {"narration": False}, "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t"}]}]}
        cases = ["もとは 1943 年にできた、列車がすれ違うための場所なの。駅になったのは 1987 年よ。", "車なら、国道で近くまでは行きやすいそうよ。駅への道は狭いけれど。",
                 "だから、無いって言ってるでしょう！ きっぷ代も各自よ！"]
        # 幅は文の長さの 7 割（書体の幅に頼らない。日本語の書体が無い環境でも 2 行になる）
        got = self.run_js(build_html(sp, voicevox=False), "[%s].map(function(t){return __MV__.capFit(t, __MV__.textWidth(t, 50) * .72, 50)})" % ",".join(json.dumps(c, ensure_ascii=False) for c in cases))
        for text, fit in zip(cases, got):
            lines = fit["lines"]
            with self.subTest(text):
                self.assertEqual(len(lines), 2, lines)
                self.assertGreaterEqual(fit["size"], 39, "字を小さくしすぎ")
                self.assertRegex(lines[0], r"[、。！？]$")
                self.assertEqual("".join(lines).replace(" ", ""), text.replace(" ", ""))
        self.assertEqual(self.run_js(build_html(sp, voicevox=False), '__MV__.capFit("短いわ。", 1100, 50)'), {"lines": ["短いわ。"], "size": 50})

    def test_vertical_draw_box_fits(self):
        """ショート（縦の画面）では、描き下ろしの図解の箱が、映る幅（まん中の 1080）に収まる。前は横の画面の幅 1200 のままで、右端の字が切れた。"""
        code = "window.__BOX = {x: s.box.x, w: s.box.w};"
        def spec(talk):
            return {"title": "t", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": False}, "talk": talk,
                    "cast": {"a": {"name": "A", "color": "#e0457b", "side": "left"}, "b": {"name": "B", "color": "#3aa657", "side": "right"}},
                    "chapters": [{"title": "c", "scenes": [{"type": "talk", "cast": ["a", "b"], "lines": [{"who": "a", "text": "図を見て。"}],
                                                            "board": {"type": "stage", "shots": [{"line": 0, "items": [{"draw": code, "plate": "board"}]}]}}]}]}
        js = "new Promise(function(ok){__MV__.seek(900); setTimeout(function(){ok(window.__BOX)}, 500)})"
        tall = self.run_js(build_html(spec({"format": "short"}), voicevox=False), js)
        self.assertGreaterEqual(tall["x"], 420)
        self.assertLessEqual(tall["x"] + tall["w"], 1500)
        wide = self.run_js(build_html(spec({}), voicevox=False), js)
        self.assertEqual(wide["w"], 1200)

    # ---- 2026-10-03: 作業役 3 人の報告（3 人の台本・画面いっぱいの写真） ----
    THREE = {"a": {"name": "A", "color": "#e0457b", "side": "left"}, "b": {"name": "B", "color": "#3aa657", "side": "left"}, "c": {"name": "C", "color": "#3a7be0", "side": "right"}}
    TEXTS = ("window.__T=[];(function(){var f=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(s,x,y){"
             "var m=this.getTransform(),k=this.canvas.width/1920;window.__T.push({s:String(s),x:(m.a*x+m.c*y+m.e)/k,y:(m.b*x+m.d*y+m.f)/k,px:parseFloat((this.font.match(/([0-9.]+)px/)||[0,0])[1])*Math.hypot(m.a,m.b)/k});"
             "return f.apply(this,arguments)}})();")

    def stage_spec(self, items, cast=None, talk=None):
        return {"title": "t", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": False}, "talk": dict({"caption": "bar", "stage": {"photo": "full"}}, **(talk or {})),
                "cast": cast or self.THREE, "images": {"p": self.square_photo()},
                "chapters": [{"title": "c", "scenes": [{"type": "talk", "cast": list(cast or self.THREE), "lines": [{"who": "a", "text": "写真を見て。"}],
                                                        "board": {"type": "stage", "shots": [{"line": 0, "items": items}]}}]}]}

    def square_photo(self):
        import base64
        path = fakes.write_png(os.path.join(fakes.tmpdir(), "p.png"), 64, 64, fakes.noise)
        return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()

    def texts(self, spec, at=2500):
        return self.run_js(build_html(spec, voicevox=False), self.TEXTS + "new Promise(function(ok){__MV__.seek(%d); setTimeout(function(){window.__T=[];__MV__.seek(%d);setTimeout(function(){ok(window.__T)},400)}, 600)})" % (at, at))

    def test_draw_box_clear_of_two_on_one_side(self):
        """3 人の台本（左に 2 人）では、描き下ろしの図解の箱（s.box）の左下が立ち絵に隠れた。同じ側に 2 人立つときは、箱を立ち絵にかからない幅に寄せる。"""
        code = "window.__BOX = {x: s.box.x, w: s.box.w};"
        spec = self.stage_spec([{"draw": code, "plate": "board"}], talk={"stage": {}})
        box = self.run_js(build_html(spec, voicevox=False), "new Promise(function(ok){__MV__.seek(900); setTimeout(function(){ok(window.__BOX)}, 500)})")
        self.assertGreater(box["x"], 500, box)             # 左の 2 人目（幅 322 の立ち絵は 282〜604 に立つ）の右へ
        self.assertLessEqual(box["x"] + box["w"], 1560)
        self.assertGreater(box["w"], 900, "寄せすぎ")

    def test_full_photo_label_above_cast(self):
        """縦長・正方形の写真を画面いっぱいに出すと、名札が写真の左下に出て、左の立ち絵に隠れた。立ち絵の頭より上に出す。"""
        got = self.texts(self.stage_spec([{"img": "p", "frame": True, "label": "正方形の写真"}]))
        label = [t for t in got if t["s"] == "【正方形の写真】"]
        self.assertTrue(label, [t["s"] for t in got])
        self.assertLess(label[-1]["y"], 1080 - 520, "名札が立ち絵（高さ 520）の頭より下にある: %r" % label[-1])
        self.assertGreater(label[-1]["y"], 170)

    def test_full_photo_bubble_lines_and_position(self):
        """写真 1 枚の画面の吹き出しで、/ が改行にならずそのまま出た。位置は sayAt（left・right・bottom）で選べる（前はいつも上の中央）。"""
        wide = {"p": "data:image/svg+xml," + "%3Csvg xmlns='http://www.w3.org/2000/svg' width='1600' height='900'%3E%3Crect width='1600' height='900' fill='%23486'/%3E%3C/svg%3E"}
        def bubble(at):
            sp = self.stage_spec([dict({"img": "p", "frame": True, "say": "上の行/下の行"}, **({"sayAt": at} if at else {}))])
            sp["images"] = wide
            got = self.texts(sp)
            self.assertFalse([t["s"] for t in got if "/" in t["s"] and "行" in t["s"]], "/ がそのまま出ている")
            up, down = [t for t in got if t["s"] == "上の行"], [t for t in got if t["s"] == "下の行"]
            self.assertTrue(up and down, [t["s"] for t in got])
            self.assertGreater(down[-1]["y"], up[-1]["y"] + 30)
            return up[-1]
        top, left, right, bottom = bubble(None), bubble("left"), bubble("right"), bubble("bottom")
        self.assertAlmostEqual(top["x"], 960, delta=30)
        self.assertLess(left["x"], 700)
        self.assertGreater(right["x"], 1220)
        self.assertGreater(bottom["y"], 540)
        self.assertLess(top["y"], 300)

    def test_board_bullets_zoom(self):
        """黒板（縮めて置く）の箇条書きは字がとても小さかった。zoom: "fit" で、収まる範囲で字を大きくする。多すぎる項目は、はみ出さない倍率に下がる。"""
        def size(items, zoom):
            sc = dict({"type": "bullets", "heading": "まとめ", "items": items, "duration": 6}, **({"zoom": zoom} if zoom else {}))
            sp = {"title": "t", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": False}, "chapters": [{"title": "c", "scenes": [sc]}]}
            got = self.texts(sp, 5500)
            return max(t["px"] for t in got if t["s"] in items), max(t["y"] for t in got if t["s"] in items)
        few, many = ["一つめの項目", "二つめの項目", "三つめの項目"], ["項目 %d" % i for i in range(1, 7)]
        self.assertAlmostEqual(size(few, None)[0], 40, delta=1)
        self.assertAlmostEqual(size(few, "fit")[0], 64, delta=1)
        px, bottom = size(many, "fit")
        self.assertLess(px, 64)
        self.assertGreaterEqual(px, 40)
        self.assertLess(bottom, 1040, "板の下にはみ出した")

    def test_shoot_waits_and_is_not_blank(self):
        """画面の撮影がときどき真っ白になった（決めた時間が過ぎたら撮っていた）。Chrome を 1 回だけ起動し、絵が読み終わって描かれるのを待って撮る。"""
        import shoot
        d = fakes.tmpdir()
        html = os.path.join(d, "s.html")
        with open(html, "w", encoding="utf-8") as f:
            f.write(build_html(self.stage_spec([{"img": "p", "frame": True, "label": "写真"}]), voicevox=False))
        want = [(ms, os.path.join(d, "shots", "%d.png" % ms)) for ms in (500, 1500, 2500)]
        with fakes.quiet() as (err, _):
            done = shoot.shoot(html, want)
        self.assertEqual(done, [p for _, p in want], err.getvalue())
        self.assertNotIn("一色", err.getvalue())
        for p in done:
            data = open(p, "rb").read()
            self.assertEqual(struct.unpack(">II", data[16:24]), (1280, 720))
            self.assertFalse(shoot.is_blank(data), p)
        self.chrome.open(open(html, encoding="utf-8").read())
        self.assertEqual(self.chrome.eval("new Promise(function(ok){setTimeout(function(){ok(__MV__.loading)},500)})"), 0)

    def test_export_has_file_music(self):
        sp = {"title": "t", "lang": "ja", "audio": {"narration": False, "music": {"file": "bgm.wav", "loop": True}, "sfx": False},
              "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t", "duration": 4}]}]}
        # fetch を使えない所でも（埋め込みの data: を自前で読む）
        rms = self.run_js(build_html(sp, voicevox=False), "(window.fetch=function(){return Promise.reject('fetch は使えない')}, __MV__.renderMusic())")
        self.assertGreater(max(rms[5:30]), 0.01, rms[:40])

    def test_scene_music_segments(self):
        sp = {"title": "t", "lang": "ja", "audio": {"narration": False, "music": "calm", "sfx": False},
              "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t", "duration": 3},
                                                     {"type": "statement", "lines": ["b"], "music": "hope", "duration": 3}]},
                           {"title": "b", "music": "tech", "scenes": [{"type": "end", "title": "e", "duration": 3}]}]}
        segs = self.run_js(build_html(sp, voicevox=False), "__MV__.segments()")
        self.assertEqual([s["key"] for s in segs], ["calm", "hope", "tech"], segs)


class Shoot(unittest.TestCase):
    """画面を撮る道具（motion-video の shoot.py）のうち、Chrome が無くても確かめられる所。"""

    def test_white_png_is_blank_whatever_its_size(self):
        """2026-10-03: 白い画面を PNG の大きさ（20000 バイト）で見分けていた。中身（色）で見分ける: 大きくても一色なら白い画面、小さくても絵があれば白くない。"""
        import shoot
        d = fakes.tmpdir()
        white = fakes.write_png(os.path.join(d, "white.png"), 320, 180, lambda x, y: (255, 255, 255), pad=40000)
        self.assertGreater(os.path.getsize(white), 20000)
        self.assertTrue(shoot.is_blank(white))
        self.assertTrue(shoot.is_blank(open(white, "rb").read()))
        small = fakes.write_png(os.path.join(d, "small.png"), 64, 36, lambda x, y: (x * 4, y * 7, 90))
        self.assertLess(os.path.getsize(small), 20000)
        self.assertFalse(shoot.is_blank(small))
        self.assertFalse(shoot.is_blank(fakes.write_png(os.path.join(d, "photo.png"), 320, 180, fakes.noise)))
        self.assertTrue(shoot.is_blank(os.path.join(d, "none.png")))

    def test_blank_shot_is_retaken_and_reported(self):
        """白い画面は撮り直す。撮り直しても白ければ、黙って渡さずに知らせる。"""
        import shoot
        d = fakes.tmpdir()
        white = open(fakes.write_png(os.path.join(d, "w.png"), 64, 36, lambda x, y: (255, 255, 255)), "rb").read()
        good = open(fakes.write_png(os.path.join(d, "g.png"), 64, 36, fakes.noise), "rb").read()

        class Fake:
            def __init__(self, shots):
                self.shots, self.asked = list(shots), []

            def open(self, html):
                pass

            def shot(self, ms):
                self.asked.append(ms)
                return self.shots.pop(0) if len(self.shots) > 1 else self.shots[0]

        html = os.path.join(d, "x.html")
        open(html, "w").write("<html></html>")
        b = Fake([white, white, good])
        with mock.patch("time.sleep", lambda s: None), fakes.quiet() as (err, _):
            done = shoot.shoot(html, [(1000, os.path.join(d, "o", "a.png"))], (1280, 720), browser=b)
        self.assertEqual(b.asked, [1000, 1000, 1000])
        self.assertEqual(open(done[0], "rb").read(), good)
        self.assertNotIn("一色", err.getvalue())
        with mock.patch("time.sleep", lambda s: None), fakes.quiet() as (err, _):
            shoot.shoot(html, [(1000, os.path.join(d, "o", "b.png"))], (1280, 720), browser=Fake([white]))
        self.assertIn("一色", err.getvalue())

    def test_times(self):
        import shoot
        self.assertEqual([shoot.seconds(t) for t in ("6.5", "0:42", "1:02:03")], [6.5, 42.0, 3723.0])


if __name__ == "__main__":
    unittest.main()
