"""動くパーツ（rig）: 腕・髪・黒目を、体の絵とは別のパーツで持って動かす（2026-10-04）。sprite.py が作り、kaisetsu.py が埋め込み、engine.js が描く。"""
import json
import os
import unittest
from unittest import mock

import fakes
import kaisetsu
import test_engine

try:
    from PIL import Image, ImageChops, ImageDraw
    import sprite
except (ImportError, SystemExit):
    Image = None

SIZE = (120, 200)


def layer(box, color):
    im = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle(box, fill=color)
    return im


def leaves(mouth="closed", eye="open"):
    """下から: 後ろ髪・体・腕・白目・黒目・口・前髪。"""
    out = [("髪", layer((10, 20, 30, 120), (200, 80, 160, 255))), ("体", layer((35, 10, 85, 190), (240, 220, 200, 255))), ("腕/基本", layer((80, 70, 95, 150), (250, 250, 250, 255)))]
    if eye == "open":
        out += [("目/白目", layer((45, 30, 75, 45), (255, 255, 255, 255))), ("目/黒目", layer((55, 32, 65, 43), (20, 60, 200, 255)))]
    else:
        out.append(("目/閉じ", layer((45, 37, 75, 39), (60, 40, 40, 255))))
    out.append(("口/" + mouth, layer((52, 55, 68, 58 if mouth == "closed" else 66), (200, 60, 60, 255))))
    out.append(("前髪", layer((35, 5, 85, 28), (200, 80, 160, 255))))
    return out


PARTS = [{"layer": "髪", "kind": "hair", "pivot": [20, 20], "max": 4}, {"layer": "腕", "kind": "arm", "side": "right", "pivot": [85, 72], "max": 8, "limit": {"基本": 6}}]
IRIS = {"layer": "目/黒目", "white": ["目/白目"], "max": 4}


def build(out):
    """sprite.json（base ＋ 表情のパーツ）に、rig を足す（psd_export.py の rig と同じ手順）。"""
    flat = lambda ls: sprite._over([im for _, im in ls], SIZE)
    render = lambda pose, face, state: flat(leaves("open" if state == "open" else "closed", "closed" if state == "blink" else "open")) if state != "half" else None
    sp = sprite.build_sprite(out, render, ["normal"], [""])[0]
    wr, ox, oy = sprite.Writer(out, keep=True), sp["origin"][0], sp["origin"][1]
    fit = lambda im: im.crop((ox, oy, ox + sp["w"], oy + sp["h"]))
    runs = sprite.rig_runs(leaves(), PARTS)
    fr = [n for n, (o, ls) in enumerate(runs) if o is None and any(q == "口/closed" for q, _ in ls)][0]
    seg = lambda mouth, eye: fit(flat(sprite.rig_runs(leaves(mouth, eye), PARTS)[fr][1]))
    P = sp["poses"][""]
    P["rig"] = sprite.rig_layers(wr, runs, PARTS, fit, lambda x, y: (x - ox, y - oy), fr)
    P["rf"] = {"normal": sprite._face_entry(wr, seg("closed", "open"), {"closed": seg("closed", "open"), "open": seg("open", "open"), "blink": seg("closed", "closed")})}
    P["iris"] = {"normal": sprite.build_iris(wr, runs[fr][1], IRIS, fit, 1)}
    json.dump(sp, open(os.path.join(out, "sprite.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return sp


@unittest.skipUnless(Image, "Pillow が無い")
class Rig(unittest.TestCase):
    def setUp(self):
        self.d = os.path.join(fakes.tmpdir(), "chars", "metan")
        os.makedirs(self.d)
        with fakes.quiet():
            self.sp = build(self.d)

    def same(self, a, b):
        return sprite._bad_pixels(a, b, 0) == 0

    def test_layers_and_rest_pose(self):
        """層は下から 髪（動く）・体・腕（動く）・顔。動かさなければ、今までの絵（base ＋ 表情のパーツ）と同じ絵になる。"""
        rig = self.sp["poses"][""]["rig"]
        self.assertEqual([L.get("k") or ("face" if L.get("f") else "-") for L in rig], ["hair", "-", "arm", "face"])
        self.assertEqual((rig[2]["m"], rig[2]["s"], rig[0]["s"]), (6, -1, 1))   # limit で上限が小さくなる・右の腕は外向きが反時計回り
        for mouth, blink in ((None, False), ("open", False), (None, True)):
            self.assertTrue(self.same(sprite.compose_rig(self.sp, self.d, "", "normal", mouth, blink), sprite.compose(self.sp, self.d, "", "normal", mouth, blink)), (mouth, blink))

    def test_moving_parts_do_not_break_the_face(self):
        """腕と髪を回しても、顔（表情のパーツを当てる層）は変わらない。黒目は白目の中だけで動く。"""
        rest = sprite.compose_rig(self.sp, self.d)
        moved = sprite.compose_rig(self.sp, self.d, angles={0: 4, 2: -6}, mouth="open")
        ox, oy = self.sp["origin"]
        face = (45 - ox, 30 - oy, 76 - ox, 46 - oy)
        self.assertTrue(self.same(rest.crop(face), moved.crop(face)))
        self.assertFalse(self.same(rest, moved))
        gaze = sprite.compose_rig(self.sp, self.d, shift=(20, 0))   # 白目の外までずらす → 黒目は白目の外には出ない
        self.assertTrue(self.same(gaze.crop((76 - ox, 30 - oy, 100 - ox, 46 - oy)), rest.crop((76 - ox, 30 - oy, 100 - ox, 46 - oy))))
        self.assertFalse(self.same(gaze.crop(face), rest.crop(face)))

    def script(self, extra=""):
        base = os.path.dirname(os.path.dirname(self.d))
        path = os.path.join(base, "s.txt")
        open(path, "w", encoding="utf-8").write("---\ntitle: 題\ncast: metan\n%s---\n# 章\nmetan: こんにちは。\n" % extra)
        return path

    def test_kaisetsu_embeds_rig_instead_of_base(self):
        with fakes.fake_voicevox(alive=True), fakes.quiet():
            _, _, people, _, _ = kaisetsu.load_spec(self.script())
        P = people["metan"]["sprite"]["poses"][""]
        self.assertTrue(P.get("rig") and "base" not in P and P["iris"]["normal"])
        self.assertEqual(set(P["faces"]["normal"]), {"open", "blink"})
        self.assertTrue({L["i"] for L in P["rig"]} <= set(people["metan"]["sprite"]["images"]))
        with fakes.fake_voicevox(alive=True), fakes.quiet():   # rig: off → 今までどおり体の絵 1 枚
            _, _, people, _, _ = kaisetsu.load_spec(self.script("rig: off\n"))
        self.assertTrue("base" in people["metan"]["sprite"]["poses"][""] and "rig" not in people["metan"]["sprite"]["poses"][""])


    def test_saved_motion_presets(self):
        """動かし方は rig.json の名前で呼び出す（rig: calm）。standard は何も足さない。無い名前は止める。"""
        def motion(extra):
            with fakes.fake_voicevox(alive=True), fakes.quiet():
                return kaisetsu.load_spec(self.script(extra))[2]["metan"].get("rigMotion")
        saved = dict(kaisetsu.RIG["cast"])
        kaisetsu.RIG["cast"].clear()   # その人のいつもの設定（rig.json の cast）は、下で別に確かめる
        self.addCleanup(kaisetsu.RIG["cast"].update, saved)
        self.assertIsNone(motion(""))
        calm = motion("rig: calm\n")
        self.assertEqual(calm["arm"]["voice"], kaisetsu.RIG["presets"]["calm"]["arm"]["voice"])
        self.assertEqual(calm["hair"]["bend"], kaisetsu.RIG["presets"]["calm"]["hair"]["bend"])   # 度合いのセットは、全部の項目を持つ
        self.assertEqual(motion("metan.rig: lively\n")["iris"]["every"], 1900)
        with self.assertRaises((ValueError, SystemExit)):
            motion("rig: nai\n")
        with mock.patch.dict(kaisetsu.RIG["cast"], {"metan": {"preset": "calm", "hair": {"sway": 0.02}}}):   # その人のいつもの設定
            m = motion("")
            self.assertEqual((m["hair"]["sway"], m["arm"]["speed"]), (0.02, 2300))


@unittest.skipUnless(Image and (test_engine.CHROME or os.environ.get("REQUIRE_CHROME")), "Pillow か Chrome が無い")
class RigEngine(unittest.TestCase):
    """エンジンが rig の層を重ねて描く。"""
    drawn, run_js = test_engine.Engine.drawn, test_engine.Engine.run_js

    @classmethod
    def setUpClass(cls):
        cls.chrome = test_engine.Chrome()

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    def test_engine_draws_rig_layers(self):
        d = os.path.join(fakes.tmpdir(), "chars", "metan")
        os.makedirs(d)
        with fakes.quiet():
            sp = build(d)
        P = sp["poses"][""]
        keys = {L["i"] for L in P["rig"]} | {q[0] for q in P["rf"]["normal"].values()} | {P["iris"]["normal"][k] for k in "uimo"}
        cast = {"a": {"name": "A", "color": "#e0457b", "side": "left", "height": 600,
                      "sprite": {"w": sp["w"], "h": sp["h"], "images": {k: os.path.join(d, "sprite", k + ".png") for k in keys},
                                 "poses": {"": {"rig": P["rig"], "faces": P["rf"], "iris": P["iris"]}}}}}
        spec = {"title": "t", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": False}, "talk": {}, "cast": cast,
                "chapters": [{"title": "c", "scenes": [{"type": "talk", "cast": ["a"], "lines": [{"who": "a", "text": "腕と髪と目が動きます。"}]}]}]}
        # rig のキャンバス（まわりに 30% の余白が付く）に、腕と髪が細い横の帯で描かれる。帯ごとの横の位置を集める
        hook = ("window.__X=[];(function(){var d=CanvasRenderingContext2D.prototype.drawImage;CanvasRenderingContext2D.prototype.drawImage=function(im,a,b,c,e,x){"
                "if(this.canvas.width===%d&&arguments.length===9)window.__X.push(x);return d.apply(this,arguments)}})();" % (sp["w"] + 2 * -(-sp["w"] * 3 // 10)))
        xs = self.drawn(test_engine.build_html(spec, voicevox=False), 1500, "window.__X.length >= 60 && window.__X", reset="window.__X = [];", before=hook)
        hair, arm = xs[:51], xs[51:91]   # 層は 髪 → 体 → 腕 の順。髪の絵は高さ 101（2px の帯が 51 本）、腕は 81（41 本）
        for name, part in (("髪", hair), ("腕", arm)):
            self.assertGreater(max(part) - min(part), .05, "%s が動いていない: %r" % (name, part))
            self.assertLess(max(abs(a - b) for a, b in zip(part, part[1:])), 1.0, "%s: となりの帯とのずれが 1px を超える（輪郭に段が見える）: %r" % (name, part))
        self.assertEqual(len({round(v, 3) for v in arm[:10]}), 1, "腕の付け根（肩から 3 割）は動かさない: %r" % arm[:12])
