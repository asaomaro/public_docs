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
        # 途中までしか描かれていないせりふは、残りに印を付けて返す（切れ）
        cut = L.boxes([box("つまり運河は、陸を掘った", 300, 600, 400), box("川じゃなくて、海のほうに", 300, 650, 420), box("作った荷物用の", 300, 700, 300)], 1280, 720)
        lines, _ = L.rows_of(cut, "つまり運河は、陸を掘った川じゃなくて、海のほうに作った荷物用の水路なの。")
        self.assertTrue(lines[-1].startswith(L.CUT))
        self.assertIn("水路なの", lines[-1])

    def test_same_text_drawn_twice_is_one(self):
        """縁取り・影で、同じ字が少しずれて描かれても 1 つ。うすい字（消えかけ）は数えない。"""
        bs = L.boxes([box("長谷寺", 100, 100, 120), box("長谷寺", 103, 103, 120), box("消えかけ", 100, 300, 120, a=.2)], 1280, 720)
        self.assertEqual([b["s"] for b in bs], ["長谷寺"])

    def test_wrap_faults(self):
        bad = [["全部で7か", "所よ。"], ["駅を出て10", "歩…。"], ["これはフレームワー", "クではない"], ["いただくのは", "、あとで"], ["そうなん", "スか！？"],
               ["朝はウニとイクラ", "丼にするっス"], ["強い風に引っぱ", "られることも"], ["運河を守", "ろうとしたのよ"], ["小樽市総合", "博物館へ行くわ"]]
        for lines in bad:
            with self.subTest(lines):
                self.assertTrue(L.wrap_faults(lines), lines)
        for lines in [["柿の葉で包んだ", "押し寿司よ。"], ["高さは24メートルも", "あるのよ。"], ["小樽の運河", "は、海に作った"], ["大きな山", "が見えるわ"], ["この橋", "なのよ"]]:
            with self.subTest(lines):
                self.assertEqual(L.wrap_faults(lines), [])

    def test_hidden_under_a_later_box(self):
        """字（吹き出し）が、後から描かれた大きな塗り（せりふの箱）の下になっていたら出す。塗りの後に同じ字を描き直しているもの・画面いっぱいの塗りは出さない。"""
        t = lambda s, x, y: {"s": s, "x": x, "y": y, "X": x + 200, "Y": y + 50, "a": 1, "k": 0}
        box = {"cover": 1, "x": 0, "y": 900, "X": 1200, "Y": 1060, "a": .9}
        self.assertEqual([h[0] for h in L.hidden([t("石炭の道", 300, 890), box], 1920, 1080)], ["石炭の道"])
        self.assertEqual(L.hidden([box, t("石炭の道", 300, 890)], 1920, 1080), [])                       # 箱の後に描いた字は、上にある
        self.assertEqual(L.hidden([t("石炭の道", 300, 700), box], 1920, 1080), [])                       # 重なっていない
        self.assertEqual(L.hidden([t("字", 300, 910), box, t("字幕の字", 300, 910)], 1920, 1080), [])     # 1 字だけの字は見ない
        self.assertEqual(L.hidden([t("ふちどり", 300, 910), box, t("ふちどり", 300, 910)], 1920, 1080), [])   # 塗りの後に描き直している
        full = {"cover": 1, "x": 0, "y": 0, "X": 1920, "Y": 1080, "a": 1}
        self.assertEqual(L.hidden([t("前の場面", 300, 500), full], 1920, 1080), [])                      # 場面の切り替えの塗り

    def test_caption_rows_skip_same_words_elsewhere(self):
        """字幕の 2 行目と同じ言葉の吹き出しが、同じ高さの横にあっても、字幕の行に混ぜない（「支柱は0本なの。」と吹き出し「支柱は」）。"""
        b = lambda s, x, y, h=40: {"s": s, "x": x, "y": y, "X": x + len(s) * h, "Y": y + h}
        bs = [b("よく気づいたわね、ずん子。", 200, 880), b("支柱は0本なの。", 300, 932), b("支柱は", 900, 925, 38), b("0本", 915, 975, 38)]
        lines, _ = L.rows_of(bs, "よく気づいたわね、ずん子。支柱は0本なの。")
        self.assertEqual(lines, ["よく気づいたわね、ずん子。", "支柱は0本なの。"])

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
