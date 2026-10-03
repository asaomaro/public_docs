"""yukkuri-kaisetsu の台本 → 動画（偽の VOICEVOX で）と、yukkuri-qa の出来上がりの検査。"""
import os
import unittest

import fakes
import build

SCRIPT = """---
title: テスト
cast: metan, zundamon
roles: metan=解説, zundamon=聞き手
speed: 1.15
music: calm
---
# はじめに
metan(smile): React は 13 年続いたの。
zundamon(surprised): 10 回も作り直したのだ！
@music: hope
metan: ここから曲が替わるわ。
zundamon: 替わったのだ。
# おわり
metan: おわりよ。
"""


def make(alive=True, voicevox=False, script=SCRIPT):
    import kaisetsu
    d = fakes.tmpdir()
    path = os.path.join(d, "y.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    with fakes.fake_voicevox(alive) as vv, fakes.quiet() as (err, out):
        spec, mv, cast, credits = kaisetsu.make_spec(path, voicevox)
    lines = [ln for ch in spec["chapters"] for sc in ch["scenes"] for ln in (sc.get("lines") or []) if isinstance(ln, dict) and ln.get("who")]
    return spec, mv, lines, vv, err.getvalue() + out.getvalue(), path


class Voices(unittest.TestCase):
    def test_auto_voicevox(self):
        """2026-10: --voicevox を付け忘れて、声の無い HTML（別人の声）で上書きした。動いていれば付けなくても入れる。"""
        spec, _, lines, vv, err, _ = make(alive=True)
        self.assertIn("声を入れます", err)
        self.assertTrue(all(ln.get("voice") for ln in lines))

    def test_warn_when_down(self):
        spec, _, lines, _, err, _ = make(alive=False)
        self.assertIn("別人の声", err)
        self.assertFalse(any(ln.get("voice") for ln in lines))

    def test_no_spaces_next_to_japanese(self):
        """2026-10: 英字・数字の前後の空白で一呼吸おいていた。声に渡す文には、日本語の隣の空白が無い。"""
        _, _, _, vv, _, _ = make(voicevox=True)
        texts = vv[0].texts
        self.assertIn("リアクトは13年続いたの。", [t for t in texts if "13" in t][0].replace("React", "リアクト"))
        for t in texts:
            self.assertNotRegex(t, r"[^\x00-\x7f] | [^\x00-\x7f]", t)

    def test_speed(self):
        spec, _, _, _, _, _ = make(voicevox=True)
        self.assertGreater(spec["cast"]["metan"]["voice"]["speed"], 1.1)    # speed: 1.15 を掛ける


class Music(unittest.TestCase):
    def test_scene_music(self):
        """2026-10: 場面の @music が効かなかった（@show が無いと場面が分かれなかった）。"""
        spec, _, _, _, _, _ = make()
        ch = spec["chapters"][0]
        self.assertGreaterEqual(len(ch["scenes"]), 2)
        changed = [sc for sc in ch["scenes"] if "music" in sc]
        self.assertTrue(changed, [list(sc) for sc in ch["scenes"]])
        self.assertEqual(changed[0]["lines"][0]["text"], "ここから曲が替わるわ。")


class Html(unittest.TestCase):
    def test_qa_counts_voices_in_html(self):
        """yukkuri-qa は、組み直した台本ではなく HTML そのものの声を数える（2026-10: 0 個の HTML を見逃した）。"""
        import kaisetsu
        import qa
        spec, mv, lines, _, _, path = make(voicevox=True)
        stem = os.path.splitext(path)[0]
        meta = kaisetsu.parse(open(path, encoding="utf-8").read())[0]
        meta["_stem"] = stem

        def warns(html_text):
            with open(stem + ".html", "w", encoding="utf-8") as f:
                f.write(html_text)
            R = qa.Report()
            with fakes.quiet():
                qa.measure(spec, meta, {}, R)
            return [r[2] for r in R.rows if r[0] == "warn" and "声" in r[2]]

        self.assertTrue(warns("<html>声なし</html>"))
        with fakes.quiet():
            full = mv.build_html(spec, spec["theme"], spec["player"], True)
        self.assertEqual(fakes.voices_in_html_text(full), len(lines))
        self.assertFalse(warns(full))


class DrawPlate(unittest.TestCase):
    def test_board_plate(self):
        """@draw: 名前 board（黒板の板）が台本から engine へ渡る。"""
        import kaisetsu
        shot = kaisetsu.parse_show("draw:zu board | note: 図")
        self.assertEqual(shot["items"][0], {"draw_ref": "zu", "plate": "board"})
        src = open(os.path.join(fakes.MV, "engine.js"), encoding="utf-8").read()
        self.assertIn('it.plate === "board"', src)


class PhotoFull(unittest.TestCase):
    def test_header_option(self):
        """photo: full で、写真 1 枚の画面を画面いっぱいに出す設定が engine へ渡る（どの型でも）。"""
        head = "---\ntitle: t\ncast: metan, zundamon\n%s---\n# 本題\nmetan: 話すわ。\n"
        self.assertEqual(make(script=head % "photo: full\n")[0]["talk"].get("stage", {}).get("photo"), "full")
        self.assertNotEqual(make(script=head % "")[0]["talk"].get("stage", {}).get("photo"), "full")


class AutomationTells(unittest.TestCase):
    """2026-10-03: 手本と伏せて比べ、自動で作った動画の手がかり（字だけの画面・写真が無い・その場面の作りが無い）を qa.py で数える。"""

    def warns(self, body):
        import kaisetsu
        import qa
        spec, _, _, _, _, path = make(script="---\ntitle: t\ncast: metan, zundamon\n---\n" + body)
        meta = kaisetsu.parse(open(path, encoding="utf-8").read())[0]
        meta["_stem"] = os.path.splitext(path)[0]
        R = qa.Report()
        with fakes.quiet():
            qa.measure(spec, meta, {}, R)
        return [r[2] for r in R.rows if r[0] == "warn"]

    def test_words_only_screens(self):
        body = "# 本題\n" + "".join('@show: "語%d" | → | "語%d"\nmetan: 説明%dよ。\nzundamon: そうなのだ。\n' % (i, i + 1, i) for i in range(4))
        w = self.warns(body)
        self.assertTrue(any("字だけの画面" in x for x in w), w)
        self.assertTrue(any("写真・資料が 1 枚も" in x for x in w), w)
        self.assertTrue(any("その場面のためだけの作り" in x for x in w), w)


class OrderFormWithoutAssets(unittest.TestCase):
    """指示のフォーム（script_order.py）が、立ち絵・曲を集めていない環境でも出せる。
    （登場人物と曲の選択肢が 0 件になり、ask-form が定義の誤りで止まった。クローンしたばかりの環境・コンテナで起きる）"""

    def order(self, chars=()):
        """立ち絵は chars の人だけ・曲は 1 つも集めていない状態の script_order を返す。"""
        import importlib.util
        sp = importlib.util.spec_from_file_location("yorder_t", os.path.join(fakes.YK, "script_order.py"))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        d = fakes.tmpdir()
        m.CHARS, m.BGM = os.path.join(d, "chars"), os.path.join(d, "bgm")
        for cid in chars:
            os.makedirs(os.path.join(m.CHARS, cid))
        os.makedirs(m.BGM, exist_ok=True)
        return m

    def check(self, spec):
        import json
        import subprocess
        import sys
        ask = os.path.join(fakes.OTHER, "ask-form", "ask.py")
        if not os.path.isfile(ask):
            self.skipTest("ask-form が無い")
        r = subprocess.run([sys.executable, ask, "-", "--check"], input=json.dumps(spec, ensure_ascii=False), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_no_assets(self):
        m = self.order()
        spec = m.build_spec("テスト")
        Q = {q["id"]: q for q in spec["questions"]}
        self.check(spec)
        self.assertGreaterEqual(len(Q["explainer"]["options"]), 40, "立ち絵が 1 人も無ければ、プリセットの全員を並べる")
        self.assertFalse(any("image" in o for o in Q["explainer"]["options"]))
        self.assertNotIn("track", Q, "曲が無ければ、曲を選ぶ質問は出さない")
        self.assertEqual([o["value"] for o in Q["music"]["options"]], ["builtin", "none"], "bgm/ の曲が要る選び方は出さない")
        self.assertEqual(Q["music"]["default"], "builtin")
        self.assertEqual((Q["explainer"]["default"], Q["listener"]["default"]), ("metan", "zundamon"))

    def test_some_art_only(self):
        m = self.order(chars=("tsumugi", "zunko"))
        spec = m.build_spec("テスト")
        Q = {q["id"]: q for q in spec["questions"]}
        self.check(spec)
        values = [o["value"] for o in Q["explainer"]["options"]]
        self.assertEqual(sorted(values), ["tsumugi", "zunko"], "集めた人がいれば、その人だけを並べる")
        for qid in ("explainer", "listener", "third", "cameo", "narrator"):
            self.assertIn(Q[qid]["default"], values, "%s の既定が選択肢に無い" % qid)
        self.assertNotEqual(Q["explainer"]["default"], Q["listener"]["default"])

    def test_warns_when_drawn_as_placeholder(self):
        m = self.order(chars=("metan",))
        a = {"explainer": "metan", "listener": "zundamon", "ensemble": "pair", "length": "5", "music": "builtin"}
        w = [x for x in m.warnings(a) if "仮のキャラクター" in x]
        self.assertEqual(len(w), 1)
        self.assertIn("zundamon", w[0])
        self.assertNotIn("metan", w[0])
        self.assertNotIn("music", m.header(a), "作曲（builtin）は、台本の先頭に music を書かない")


if __name__ == "__main__":
    unittest.main()
