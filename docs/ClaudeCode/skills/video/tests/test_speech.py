"""声に渡す文・読みの指摘・文の中の字幕の切り替え時刻（motion-video の build.py と yukkuri-kaisetsu の kaisetsu.py）。"""
import unittest

import fakes  # noqa: F401  パスを通す
import build
import kaisetsu

PRON = {"pane": "ペイン", "React": "リアクト", "sodactl": "ソーダコントロール", "soda": "ソーダ"}


class Spacing(unittest.TestCase):
    """2026-10 の不具合: 英字・数字の前後の空白で VOICEVOX が一呼吸おき、「10 回」が「じゅう、かい」と読まれた。"""

    CASES = [
        ("ワークスペースを開き、pane を分けて動かします。", "ワークスペースを開き、ペインを分けて動かします。"),
        ("既定は 10 回で止まります。", "既定は10回で止まります。"),
        ("React は 13 年生き延びた。", "リアクトは13年生き延びた。"),
        ("Claude Code も Codex も並べる。", "Claude CodeもCodexも並べる。"),   # 英字どうしの間は残す
        ("This is English.", "This is English."),
        ("全角　の空白 も詰める", "全角の空白も詰める"),
    ]

    def test_motion_video(self):
        for src, want in self.CASES:
            self.assertEqual(build.spoken(src, PRON), want, src)

    def test_yukkuri(self):
        for src, want in self.CASES:
            self.assertEqual(kaisetsu.speakable(src, PRON), want, src)

    def test_longest_word_first(self):
        # sodactl を soda より先に置き換える（「ソーダctl」にしない）
        self.assertEqual(build.spoken("sodactl と soda", PRON), "ソーダコントロールとソーダ")
        self.assertEqual(kaisetsu.speakable("sodactl と soda", PRON), "ソーダコントロールとソーダ")

    def test_strip_emphasis(self):
        self.assertEqual(build.spoken("**大事** な所", {}), "大事な所")


class OddReadings(unittest.TestCase):
    def hits(self, text, pron=None):
        sp = build.spoken(text, pron or {})
        return [why for rx, why in build.ODD_READINGS if rx.findall(sp)]

    def test_flags(self):
        self.assertTrue(self.hits("ブラウザを開けない環境"))       # あけない／ひらけない
        self.assertTrue(self.hits("Ctrl を押す"))                  # 英字のまま
        self.assertFalse(self.hits("Ctrl を押す", {"Ctrl": "コントロール"}))

    def test_counters_are_fine_without_spaces(self):
        # 空白を詰めれば正しく読まれるので、数と助数詞は指摘しない（「1 つ」の規則は空白の症状だった）
        for t in ("キー 1 つで", "3 日かかる", "10 回で止まる", "13 年"):
            self.assertFalse(self.hits(t), t)


class Sentences(unittest.TestCase):
    def test_long_sentence_splits_at_comma(self):
        g = build.split_sentences("ブラウザでも、引数なしの soda で開く端末版でも、同じ画面を操作できます。短い文。", "ja")
        self.assertEqual(len(g), 2)
        self.assertEqual(len(g[0]), 2)                        # 1 文が字幕 2 つに
        self.assertTrue(g[0][0].endswith("、"))
        self.assertEqual(g[1], ["短い文。"])
        self.assertEqual(build.split_cues("A。B。", "ja"), ["A。", "B。"])


class VoiceSplits(unittest.TestCase):
    """2026-10 の不具合: 字幕ごとに声を作り、文の途中で語尾が下がって切れていた。1 文の声の中で、読点の間の終わりで字幕を切り替える。"""

    def test_cut_at_end_of_pause(self):
        parts = ["あいう、", "えおかき。"]
        text = "".join(parts)
        q = fakes.fake_query(text)
        total = (fakes.EDGE * 2 + 7 * fakes.MORA + fakes.PAUSE) * 1000
        cuts = build.voice_splits(q, [3, 4], total)
        self.assertEqual(len(cuts), 1)
        self.assertAlmostEqual(cuts[0], (fakes.EDGE + 3 * fakes.MORA + fakes.PAUSE) * 1000, delta=2)

    def test_speed_and_wav_length_scale(self):
        q = fakes.fake_query("あいう、えおかき。", speed=2.0)
        total = (fakes.EDGE * 2 + 7 * fakes.MORA + fakes.PAUSE) * 1000 / 2
        self.assertAlmostEqual(build.voice_splits(q, [3, 4], total)[0], (fakes.EDGE + 0.3 + fakes.PAUSE) * 1000 / 2, delta=2)

    def test_fallback_when_mora_count_differs(self):
        q = fakes.fake_query("あいう、えおかき。")
        cuts = build.voice_splits(q, [5, 5], 1000)              # 拍の数が合わない → 割合
        self.assertEqual(cuts, [500])

    def test_single_part(self):
        self.assertEqual(build.voice_splits(fakes.fake_query("あいう。"), [3], 500), [])


if __name__ == "__main__":
    unittest.main()
