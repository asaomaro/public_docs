"""motion-video の背景のプリセット（SVG の背景 bg/・動く背景 parts-backdrops.js）。

  - 一覧（bg/index.json・build.BACKDROPS）と実物（SVG のファイル・engine の描画部）がずれていない。名前が重ならない
  - bg_make.py を回し直しても、同じファイルになる（手で直した SVG が、作り直しで消えない）
  - 台本・章・場面の bg が HTML に入る（同じ SVG は 1 回だけ）。無い名前は作る前に止まる。明るさの合わない景色は知らせる
  - 動く背景は、周期の終わりと始まりがつながる（ループする）。SVG の背景は配色の色に置き換わって描かれる
"""
import json
import os
import re
import unittest
import xml.etree.ElementTree as ET

import fakes
import build
import bg_make
import test_engine

BG = os.path.join(fakes.MV, "bg")


def spec(scenes, **top):
    return dict({"title": "t", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": False},
                 "chapters": [{"title": "a", "scenes": scenes}]}, **top)


def load(sp, d):
    p = os.path.join(d, "s.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(sp, f, ensure_ascii=False)
    return build.load(p)


class Catalog(unittest.TestCase):
    def test_names_and_files(self):
        svgs = build.bg_svgs()
        self.assertGreaterEqual(len(svgs), 60)
        self.assertGreaterEqual(len(build.BACKDROPS), 30)
        self.assertFalse(set(svgs) & set(build.BACKDROPS), "SVG の背景と動く背景で、同じ名前を使わない（動く背景が先に当たる）")
        for name, e in svgs.items():
            with self.subTest(name):
                text = open(os.path.join(BG, e["file"]), encoding="utf-8").read()
                root = ET.fromstring(text)
                self.assertEqual((root.get("width"), root.get("height")), ("1920", "1080"))   # 大きさが無いと、画像として読めない
                self.assertLess(len(text), 60000)
                self.assertEqual(":root{" in text, e["kind"] == "themed")                    # 配色に合わせるものだけ、色の変数を持つ
                self.assertEqual(e["kind"] == "scenery", e.get("tone") in ("dark", "light"))
                self.assertTrue(e["label"] and e["desc"])

    def test_motion_names_match_engine(self):
        js = open(os.path.join(fakes.MV, "parts-backdrops.js"), encoding="utf-8").read()
        self.assertEqual(set(re.findall(r'^  def\("([\w-]+)"', js, re.M)), set(build.BACKDROPS))

    def test_generator_is_reproducible(self):
        d, out = fakes.tmpdir(), bg_make.OUT
        bg_make.OUT = d
        try:
            idx = bg_make.make()
        finally:
            bg_make.OUT = out
        self.assertEqual(idx, build.bg_svgs())
        for e in idx.values():
            with self.subTest(e["file"]):
                self.assertEqual(open(os.path.join(d, e["file"]), encoding="utf-8").read(), open(os.path.join(BG, e["file"]), encoding="utf-8").read(),
                                 "bg_make.py を回すと変わる（SVG を手で直さず、bg_make.py を直して回す）")


class Build(unittest.TestCase):
    def test_bg_levels(self):
        sp = spec([{"type": "title", "title": "t"}, {"type": "statement", "lines": ["a"], "bg": {"src": "aurora", "dim": .3, "speed": 2}},
                   {"type": "statement", "lines": ["b"], "bg": False}], bg="topo")
        sp["chapters"].append({"title": "b", "bg": "topo", "scenes": [{"type": "statement", "lines": ["c"]}, {"type": "statement", "lines": ["d"], "bg": "waves"}]})
        with fakes.quiet():
            s = load(sp, fakes.tmpdir())
            html = build.build_html(s, "midnight", "studio", True)
        sc = [x for ch in s["chapters"] for x in ch["scenes"]]
        self.assertEqual([x.get("bg") for x in sc], [None, {"src": "aurora", "dim": .3, "speed": 2}, False, "topo", "waves"])   # 章の背景は、書いていない場面へ
        self.assertEqual(list(s["bgs"]), ["topo"])
        self.assertEqual(html.count("<svg xmlns=\\\"http://www.w3.org/2000/svg\\\" width=\\\"1920\\\""), 1, "同じ SVG の背景は 1 回だけ入る")

    def test_unknown_and_bad_values_stop(self):
        for bg in ("no-such-bg", {"src": "aurora", "dim": 3}, {"dim": .2}):
            with self.subTest(bg=bg), fakes.quiet(), self.assertRaises(SystemExit):
                load(spec([{"type": "title", "title": "t", "bg": bg}]), fakes.tmpdir())

    def test_tone_warning(self):
        day = spec([{"type": "title", "title": "t", "bg": "sky-day"}], theme="navy-brass")
        self.assertTrue(build.bg_warnings(day))
        self.assertFalse(build.bg_warnings(dict(day, theme="daylight")))
        day["chapters"][0]["scenes"][0]["bg"] = {"src": "sky-day", "dim": .5}   # 抑えてあれば知らせない
        self.assertFalse(build.bg_warnings(day))

    def test_demo_lists_everything(self):
        names = [s["bg"] for ch in build.backgrounds_demo()["chapters"] for s in ch["scenes"]]
        self.assertEqual(set(names), set(build.BACKDROPS) | set(build.bg_svgs()))


@unittest.skipUnless(test_engine.CHROME or os.environ.get("REQUIRE_CHROME"), "Chrome が無い")
class Engine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not test_engine.CHROME:
            raise AssertionError("Chrome が無いので engine.js を確かめられません")
        cls.chrome = test_engine.Chrome()

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    # 画面を 96×54 に縮めた画素の列（比べる用）
    PIX = "function pix(cv){var c=document.createElement('canvas');c.width=96;c.height=54;var x=c.getContext('2d');x.drawImage(cv,0,0,96,54);return x.getImageData(0,0,96,54).data}" \
          "function diff(a,b){var s=0;for(var i=0;i<a.length;i++)s+=Math.abs(a[i]-b[i]);return s/a.length}"

    def test_motion_backdrops_loop(self):
        """動く背景は、どれも何かを描き、動き、周期の終わり（u→1）が始まり（u=0）につながる。"""
        with fakes.quiet():
            s = load(spec([{"type": "title", "title": "t"}]), fakes.tmpdir())
            html = build.build_html(s, "midnight", "studio", True)
        self.chrome.open(html)
        got = self.chrome.eval("(function(){%s var cv=__MV__.drawAt(0),B=__MV__.backdrops,out={};"
                               "function at(n,u){var x=cv.getContext('2d');x.save();B[n].draw(u,{});x.restore();return pix(cv)}"
                               "Object.keys(B).forEach(function(n){var a=at(n,0),m=at(n,.37),z=at(n,1-1e-7),again=at(n,0);"
                               "out[n]={seam:diff(a,z),move:diff(a,m),same:diff(a,again),period:B[n].period}});return out})()" % self.PIX)
        self.assertEqual(set(got), set(build.BACKDROPS))
        for n, r in got.items():
            with self.subTest(n):
                self.assertLess(r["seam"], .01, "周期の終わりと始まりがつながっていない（u に掛ける回数が整数でない）")
                self.assertGreater(r["move"], .01, "動いていない")
                self.assertEqual(r["same"], 0, "同じ時刻で画が変わる（乱数を毎回引いている）")
                self.assertGreaterEqual(r["period"], 2000)

    def test_backgrounds_are_painted(self):
        """台本の bg・場面の bg・false が画に出る。SVG の背景は、配色の色に置き換わる（既定の紺の色のままにならない）。"""
        sc = [{"type": "statement", "lines": [" "], "duration": 3, "fx": False, "transition": "cut", "bg": b} for b in ("grid-fade", "sky-day", "aurora", False)]
        sc.insert(0, {"type": "statement", "lines": [" "], "duration": 3, "fx": False})
        with fakes.quiet():
            s = load(spec(sc, bg="mesh", chrome=False, theme="daylight"), fakes.tmpdir())
            html = build.build_html(s, "daylight", "studio", True)
        self.chrome.open(html)
        self.chrome.eval("new Promise(function(ok){setTimeout(ok,1200)})")   # SVG の画像を読み終えるまで
        got = self.chrome.eval("(function(){%s var f=[0,1,2,3,4].map(function(i){return pix(__MV__.drawAt(i*3000+1500))});"
                               "var lum=function(a){var s=0;for(var i=0;i<a.length;i+=4)s+=a[i]+a[i+1]+a[i+2];return s/(a.length/4*3)};"
                               "return {d:[1,2,3,4].map(function(i){return diff(f[0],f[i])}),lum:f.map(lum)}})()" % self.PIX)
        for i, name in enumerate(("grid-fade", "sky-day", "aurora", "false")):
            self.assertGreater(got["d"][i], .5, "場面の bg（%s）が、台本の bg と違う画になっていない" % name)
        self.assertGreater(got["lum"][0], 200, "配色（日中）の色に置き換わっていない（紺の色のまま）")
        self.assertGreater(got["lum"][1], 200)


if __name__ == "__main__":
    unittest.main()
