"""layout.py（字の重なり・見切れ・行数・折り返しを機械で確かめる）。判定の部分は、描かれた字の箱を手で作って確かめる。"""
import unittest

import fakes  # noqa: F401（motion-video を読めるようにする）
import layout as L

box = lambda s, x, y, w, h=40, a=1: {"s": s, "x": x, "y": y, "X": x + w, "Y": y + h, "a": a, "c": "#fff"}


class Layout(unittest.TestCase):
    def test_rows_and_line_count(self):
        bs = L.boxes([box("9:00 稲荷駅", 20, 20, 200, 30), box("東山のいちばん南の", 300, 600, 400), box("伏見稲荷から、清水寺、", 300, 650, 420), box("八坂神社へと北に進むの。", 300, 700, 440)], 1280, 720)
        lines, mine = L.rows_of(bs, "東山のいちばん南の伏見稲荷から、清水寺、八坂神社へと北に進むの。")
        self.assertEqual(len(lines), 3)
        self.assertEqual(len(mine), 3)
        self.assertIsNone(L.rows_of(bs, "画面に無いせりふ"))

    def test_same_text_drawn_twice_is_one(self):
        """縁取り・影で、同じ字が少しずれて描かれても 1 つ。うすい字（消えかけ）は数えない。"""
        bs = L.boxes([box("長谷寺", 100, 100, 120), box("長谷寺", 103, 103, 120), box("消えかけ", 100, 300, 120, a=.2)], 1280, 720)
        self.assertEqual([b["s"] for b in bs], ["長谷寺"])

    def test_wrap_faults(self):
        bad = [["全部で7か", "所よ。"], ["駅を出て10", "歩…。"], ["これはフレームワー", "クではない"], ["いただくのは", "、あとで"], ["そうなん", "スか！？"]]
        for lines in bad:
            with self.subTest(lines):
                self.assertTrue(L.wrap_faults(lines), lines)
        for lines in [["柿の葉で包んだ", "押し寿司よ。"], ["高さは24メートルも", "あるのよ。"]]:
            with self.subTest(lines):
                self.assertEqual(L.wrap_faults(lines), [])

    def test_overlaps(self):
        a, b, c = box("11:30 長谷寺", 20, 20, 200, 30), box("画像: だれか（CC BY 4.0）", 150, 28, 300, 20), box("4か所目", 1100, 20, 100, 30)
        got = L.overlaps([a, b, c], [])
        self.assertEqual(len(got), 1)
        self.assertIn("長谷寺", got[0])
        # 同じせりふの行どうし・上下に並んだ行は、重なりではない
        l1, l2 = box("一行目の字", 300, 600, 300, 44), box("二行目の字", 300, 640, 300, 44)
        self.assertEqual(L.overlaps([l1, l2], [l1, l2]), [])
        self.assertEqual(L.overlaps([l1, box("別の字", 300, 641, 300, 44)], []), [])


if __name__ == "__main__":
    unittest.main()
