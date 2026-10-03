"""motion-video の台本 → HTML（見本がそのまま作れる・BGM の表・指示のフォーム）。"""
import glob
import json
import os
import subprocess
import sys
import unittest

import fakes
import build
import sound

EXAMPLES = sorted(glob.glob(os.path.join(fakes.MV, "examples", "*.json")))


class Examples(unittest.TestCase):
    """同梱の見本は、どれも誤りなく HTML になる（engine.js・build.py の変更で見本が壊れていないか）。"""

    def test_examples_build(self):
        self.assertGreaterEqual(len(EXAMPLES), 5)
        for p in EXAMPLES:
            with self.subTest(os.path.basename(p)), fakes.fake_voicevox(alive=False), fakes.quiet():
                s = build.load(p)
                html = build.build_html(s, s.get("theme", "navy-brass"), s.get("player", "studio"), True)
                self.assertIn("window.MotionVideo", html)
                self.assertGreater(sum(sc["_dur"] for ch in s["chapters"] for sc in ch["scenes"]), 5000)

    def test_dist_drops_export(self):
        with fakes.fake_voicevox(alive=False), fakes.quiet():
            s = build.load(EXAMPLES[0])
            full = build.build_html(json.loads(json.dumps(s)), "navy-brass", "studio", True)
            dist = build.build_html(json.loads(json.dumps(s)), "navy-brass", "studio", False)
        self.assertLess(len(dist), len(full))


class Music(unittest.TestCase):
    def music_spec(self, d):
        fakes.write_wav(os.path.join(d, "bgm.wav"), [(1.0, True)])
        return {"title": "曲", "audio": {"narration": True, "music": {"file": "bgm.wav"}}, "chapters": [
            {"title": "一", "music": {"file": "bgm.wav"}, "scenes": [{"type": "title", "title": "一", "narration": "一つ目。"},
                                                                     {"type": "statement", "lines": ["二"], "music": "calm", "narration": "二つ目。"}]},
            {"title": "二", "music": {"file": "bgm.wav"}, "scenes": [{"type": "end", "title": "終", "narration": "終わり。"}]}]}

    def test_same_file_embedded_once(self):
        """同じ曲のファイルを章ごとに書いても、HTML には 1 回だけ入れる。"""
        d = fakes.tmpdir()
        s = self.music_spec(d)
        self.assertEqual(sound.prepare(s, d), [])
        files = [k for k, v in s["audio"]["_music"].items() if v.get("file")]
        self.assertEqual(len(files), 1)
        self.assertEqual(s["chapters"][0]["_music"], s["chapters"][1]["_music"])

    def test_scene_music(self):
        """場面の music は、その場面から曲を替える（2026-10 の不具合: 場面の曲が効かなかった）。"""
        d = fakes.tmpdir()
        s = self.music_spec(d)
        sound.prepare(s, d)
        self.assertEqual(s["chapters"][0]["scenes"][1]["_music"], "calm")
        self.assertIn("calm", s["audio"]["_music"])

    def test_missing_file_is_error(self):
        d = fakes.tmpdir()
        s = {"title": "x", "audio": {"music": {"file": "nai.mp3"}}, "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "a"}]}]}
        self.assertTrue(any("見つかりません" in e for e in sound.prepare(s, d)))


class OrderForm(unittest.TestCase):
    """指示のフォーム（order.py）: 定義が ask-form の検査を通り、答えから作った骨組みが build.py の検査を通る。"""

    @classmethod
    def setUpClass(cls):
        import order
        cls.order = order
        with fakes.fake_voicevox(alive=False):
            cls.spec = order.build_spec("テスト", previews=False)

    def test_form_definition(self):
        ask = os.path.join(fakes.OTHER, "ask-form", "ask.py")
        if not os.path.isfile(ask):
            self.skipTest("ask-form が無い")
        r = subprocess.run([sys.executable, ask, "-", "--check"], input=json.dumps(self.spec, ensure_ascii=False), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_skeletons_validate(self):
        answers = [
            {"subject": "a", "use": "local", "audio": "full", "voice": "voicevox", "speaker": "ずんだもん", "speed": "1.2", "music": "auto", "kit": "digital",
             "density": "normal", "palette": "auto", "motion": "tech", "player": "auto", "expression": "components"},
            {"subject": "b", "use": "kiosk", "audio": "silent", "player": "auto", "palette": "vivid", "motion": "auto", "expression": "free"},
            {"subject": "c", "use": "embed", "audio": "music", "music": "pick", "track": "tech", "kit": "auto", "density": "high", "player": "auto"},
        ]
        for a in answers:
            with self.subTest(a["subject"]):
                s, b = self.order.skeleton(a)
                s["chapters"] = [{"title": "a", "scenes": [{"type": "title", "title": "t", "narration": "こんにちは。"}]}]
                self.assertEqual(build.validate(s, fakes.MV), [])
        s, b = self.order.skeleton(answers[0])
        self.assertEqual(s["audio"]["voice"]["speed"], 1.2)
        self.assertIn("--voicevox", b["args"])
        self.assertEqual(self.order.skeleton(answers[1])[0]["player"], "kiosk")

    def test_warnings(self):
        w = self.order.warnings({"use": "youtube", "voice": "browser"})
        self.assertTrue(any("WebM" in x for x in w))


if __name__ == "__main__":
    unittest.main()
