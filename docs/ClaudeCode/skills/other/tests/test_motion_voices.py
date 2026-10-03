"""motion-video のナレーションの声（偽の VOICEVOX で）: 1 文ずつの声・文の中の字幕・声の付け忘れ・書き出し。"""
import os
import unittest

import fakes
import build


def spec(extra_audio=None):
    au = {"narration": True, "music": None, "sfx": False, "voice": {"engine": "voicevox", "speaker": "東北きりたん", "style": "ノーマル"}}
    au.update(extra_audio or {})
    return {"title": "テスト", "lang": "ja", "theme": "midnight", "player": "studio", "audio": au, "chapters": [
        {"title": "一", "scenes": [{"type": "title", "title": "テスト",
                                     # 1 文目は 34 字を超えるので、字幕 2 つに分かれる
                                     "narration": ["ブラウザでも、引数なしのソーダで開く端末版でも、同じ画面をそのまま操作できます。", "短い文です。"]}]},
        {"title": "二", "scenes": [{"type": "bullets", "heading": "できること", "items": ["一つ目", "二つ目"],
                                     "narration": ["一つ目の説明です。", "二つ目の説明です。"]}]}]}


class SentenceVoices(unittest.TestCase):
    def setUp(self):
        self.dir = fakes.tmpdir()
        self.path = fakes.write_json(os.path.join(self.dir, "v.json"), spec())

    def load(self, alive=True, **kw):
        with fakes.fake_voicevox(alive) as vv, fakes.quiet() as (err, _):
            s = build.load(self.path, **kw)
        return s, vv, err.getvalue()

    def test_one_wav_per_sentence(self):
        s, vv, _ = self.load(voicevox=True)
        sc = s["chapters"][0]["scenes"][0]
        self.assertEqual(len(sc["_vtexts"]), 3)                              # 字幕は 3 つ
        self.assertEqual([("cont" in v) for v in sc["_voices"]], [False, True, False])   # 声は 2 つ（2 つ目の字幕は続き）
        self.assertEqual(sc["_voices"][1]["cont"], 0)
        self.assertEqual(sc["_vgaps"], [0, build.VOICE_GAP, build.VOICE_GAP])   # 文の中は間を置かない
        self.assertIsNone(sc["_vpaths"][1])                                  # 書き出しでは 2 つ目に声を置かない
        self.assertEqual(len(vv[0].texts), 4)                               # 声を作ったのは 4 文（字幕の数ではない）

    def test_cues_continue_inside_sentence(self):
        s, _, _ = self.load(voicevox=True)
        sc = s["chapters"][0]["scenes"][0]
        c = sc["_cues"]
        self.assertEqual(c[0][1], c[1][0])                                   # 1 つ目の字幕の終わり＝2 つ目の始まり
        self.assertEqual(c[2][0] - c[1][1], build.VOICE_GAP)                 # 文と文の間
        whole = fakes.wav_ms(sc["_vpaths"][0])
        self.assertAlmostEqual(sum(sc["_vdurs"][:2]), whole, delta=2)        # 2 つの字幕で 1 つの声の長さ
        # 切り替えは「ブラウザでも、引数なしのソーダで開く端末版でも、」を読み終えた間の後
        first = build.spoken(sc["_vtexts"][0], {})
        n = sum(k for k, _ in fakes.tokens(first))
        pauses = sum(1 for _, p in fakes.tokens(first + "x") if p)
        sp = build.NARRATION_SPEED
        self.assertAlmostEqual(sc["_vdurs"][0], (fakes.EDGE + n * fakes.MORA + pauses * fakes.PAUSE) / sp * 1000, delta=3)

    def test_default_speed(self):
        _, vv, _ = self.load(voicevox=True)
        p = [x for x in os.listdir(os.path.join(self.dir, "v_voices")) if x.endswith(".wav")]
        self.assertTrue(p)
        self.assertEqual(build.NARRATION_SPEED, 1.1)

    def test_auto_voicevox_when_alive(self):
        """2026-10 の不具合: --voicevox を付け忘れて、声の無い HTML（ブラウザの声＝別人の声）で上書きした。"""
        s, _, err = self.load(alive=True)
        self.assertIn("声を入れます", err)
        self.assertTrue(s["chapters"][0]["scenes"][0].get("_voices"))

    def test_warn_when_voicevox_down(self):
        s, _, err = self.load(alive=False)
        self.assertIn("ブラウザの読み上げ", err)
        self.assertFalse(s["chapters"][0]["scenes"][0].get("_voices"))

    def test_html_embeds_one_voice_per_sentence(self):
        s, _, _ = self.load(voicevox=True)
        out = os.path.join(self.dir, "v.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(build.build_html(s, s["theme"], s["player"], True))
        self.assertEqual(fakes.voices_in_html(out), 4)
        self.assertNotIn(self.dir, open(out, encoding="utf-8").read())      # ローカルのパス（_vpaths）を HTML に入れない

    def test_video_export_timeline(self):
        import importlib.util
        p = os.path.join(fakes.OTHER, "video-export", "export.py")
        sp_ = importlib.util.spec_from_file_location("export_t", p)
        ex = importlib.util.module_from_spec(sp_)
        sp_.loader.exec_module(ex)
        s, _, _ = self.load(voicevox=True)
        tl = ex.timeline(s)
        voiced = [c for c in tl["cues"] if c["vpath"]]
        self.assertEqual(len(tl["cues"]), 5)
        self.assertEqual(len(voiced), 4)                                     # 続きの字幕には声を置かない


class FilesMode(unittest.TestCase):
    def test_prepared_wavs_one_per_cue(self):
        d = fakes.tmpdir()
        vd = os.path.join(d, "wavs")
        os.makedirs(vd)
        for i in range(5):
            fakes.write_wav(os.path.join(vd, "%02d.wav" % i), [(0.5, True)])
        sp = spec()
        sp["audio"].pop("voice")
        path = fakes.write_json(os.path.join(d, "f.json"), sp)
        with fakes.quiet():
            s = build.load(path, voices_dir=vd)
        sc = s["chapters"][0]["scenes"][0]
        self.assertEqual(len(sc["_voices"]), 3)
        self.assertFalse(any("cont" in v for v in sc["_voices"]))           # 用意した WAV は字幕ごと


if __name__ == "__main__":
    unittest.main()
