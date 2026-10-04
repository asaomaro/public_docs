"""作業役（別のセッション）が 10 選の動画を作る中で見つけた不具合（2026-10-04）。"""
import importlib.util
import json
import os
import sys
import unittest
from unittest import mock

import fakes
import build
import kaisetsu

sys.path.insert(0, os.path.join(fakes.VIDEO, "yukkuri-publish"))
import publish  # noqa: E402
import fetch_images  # noqa: E402

HEAD = "---\ntitle: テスト\ncast: metan, zundamon\nroles: metan=解説, zundamon=聞き手\n---\n"


def check(body, files=None):
    sp = importlib.util.spec_from_file_location("ycheck_w", os.path.join(fakes.YK, "script_check.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    d = fakes.tmpdir()
    path = os.path.join(d, "s.txt")
    open(path, "w", encoding="utf-8").write(HEAD + body)
    for name, text in (files or {}).items():
        open(os.path.join(d, name), "w", encoding="utf-8").write(text)
    with fakes.quiet():
        R, stats = m.run(path)
    return [x[2] for x in R.items], stats


class Script(unittest.TestCase):
    def test_trailing_note_is_not_spoken(self):
        # せりふの行末の「// 事3」が、字幕と声に入った
        _, chapters, _ = kaisetsu.parse(HEAD + "# 本題\nmetan: 深さは 200 メートルよ。 // 事3\nzundamon: 出典は https://example.com//a なのだ。\n")
        texts = [l["text"] for c in chapters for s in c["scenes"] for l in s["lines"]]
        self.assertEqual(texts[0], "深さは 200 メートルよ。")
        self.assertIn("https://example.com//a", texts[1])   # URL の // は残る

    def test_fact_ids_other_than_F(self):
        msgs, stats = check("# 本題\nmetan: 高さは 120 メートルよ。\nzundamon: 高いのだ。\n",
                            {"s.facts.md": "- [A1] 高さは 120 メートル — 出典: https://example.com\n- [事2] 幅は 30 メートル — 出典: https://example.com\n"})
        self.assertEqual(stats["事実"], "2 件")   # 前は [F数字] だけを数えて「0 件」

    def test_factcheck_done_items_are_not_counted(self):
        fc = "## 主張 1\n- 主張: a\n- 判定: 言いすぎ\n- 反映: 「最大級」に弱めた\n\n## 主張 2\n- 主張: b\n- 判定: 食い違う\n\n## 主張 3\n- 主張: c\n- 判定: 確認できた\n"
        msgs, stats = check("# 本題\nmetan: はじめるわ。\nzundamon: はいなのだ。\n", {"s.factcheck.md": fc, "s.facts.md": "- [F1] x — 出典: https://example.com\n"})
        self.assertEqual(stats["ファクトチェック"], "3 件（直す所 1・判定なし 0）")   # 前は、直しても 2 のまま
        self.assertTrue(any("直す所が 1 件" in m for m in msgs), msgs)

    def test_readings_that_voicevox_gets_wrong(self):
        hits = lambda s: [why for rx, why in build.ODD_READINGS if rx.search(s)]
        self.assertTrue(any("みずうみ" in w for w in hits("ナトロン湖は赤いわ。")))
        self.assertFalse(any("みずうみ" in w for w in hits("琵琶湖は広いわ。")))
        self.assertTrue(any("しがらみ" in w for w in hits("柵の向こうよ。")))


class Font(unittest.TestCase):
    def test_whole_font_is_embedded_without_fonttools(self):
        # fontTools の無い環境で、字幕が OS の書体になった（5 人のうち 4 人）
        d = fakes.tmpdir()
        os.makedirs(os.path.join(d, "fonts"))
        fakes.write_json(os.path.join(d, "fonts.json"), {"rounded": {"file": "r.ttf"}})
        open(os.path.join(d, "fonts", "r.ttf"), "wb").write(b"\x00\x01\x00\x00fake-font")
        with mock.patch.object(kaisetsu, "HERE", d), mock.patch.dict(sys.modules, {"fontTools": None}), fakes.quiet() as (err, _):
            f = kaisetsu.embed_font("rounded", "あいう")
        self.assertTrue(f and f["src"].startswith("data:font/ttf;base64,"), f)
        self.assertIn("まるごと", err.getvalue())


class Publish(unittest.TestCase):
    def test_url_with_parentheses_is_kept(self):
        d = fakes.tmpdir()
        open(os.path.join(d, "s.facts.md"), "w", encoding="utf-8").write(
            "- [F1] 建物（出典: https://nl.wikipedia.org/wiki/Kubuswoningen_(Rotterdam)）\n- [F2] 別の話 — 出典: https://example.com/a。\n")
        self.assertEqual(publish.sources(d, {}, os.path.join(d, "s"))[0], ["https://nl.wikipedia.org/wiki/Kubuswoningen_(Rotterdam)", "https://example.com/a"])

    FACTS = ("## 使う事実\n- [F1] 土合駅の下りホームへは 486 段の階段を下りる。 — 原文: 「486段」 — 出典: https://example.com/doai\n"
             "- [F2] 小幌駅は三方を崖に囲まれている。 — 原文: 「崖」 — 出典: https://example.com/koboro\n"
             "## 出典 題・見た日\n- 土合駅 — https://example.com/doai\n- 小幌駅 — https://example.com/koboro\n- 参考にした本（URL なし）\n"
             "## 追加\n- [F3] 駅舎は山小屋ふう。 — 出典: https://example.com/doai2\n## 出典\n- 土合駅の駅舎 — https://example.com/doai2\n")

    def srcs(self, script, **meta):
        d = fakes.tmpdir()
        open(os.path.join(d, "s.facts.md"), "w", encoding="utf-8").write(self.FACTS)
        return publish.sources(d, meta, os.path.join(d, "s"), script)

    def test_sources_of_unused_facts_are_dropped(self):
        # 調べたが使わなかった項目の出典まで、概要欄に並んでいた。「## 出典」が何か所かに分かれていると、最初の 1 つしか読まなかった
        keep, drop = self.srcs("metan: 土合駅は、階段を 486 段も下りるのよ。\ntsumugi: 駅舎は山小屋みたいっス。\n")
        self.assertEqual(keep, ["土合駅 — https://example.com/doai", "参考にした本（URL なし）", "土合駅の駅舎 — https://example.com/doai2"])
        self.assertEqual(drop, ["小幌駅 — https://example.com/koboro"])

    def test_sources_can_be_kept_or_named(self):
        script = "metan: 土合駅は、階段を 486 段も下りるのよ。\n"
        self.assertEqual(self.srcs(script, sources="all")[1], [])
        self.assertEqual(self.srcs(script, sources="駅舎")[0], ["土合駅の駅舎 — https://example.com/doai2"])
        self.assertEqual(self.srcs(None)[1], [])   # 台本を渡さなければ、外さない


class Acting(unittest.TestCase):
    def test_bubble_can_wait_for_a_later_line(self):
        it = kaisetsu.parse_show('daibutsu "牛久大仏" > "高さ/120m" left @2 frame')["items"][0]
        self.assertEqual((it["say"], it["sayAt"], it["sayLine"], it["frame"]), ("高さ/120m", "left", 2, True))
        self.assertNotIn("sayLine", kaisetsu.parse_show('daibutsu "牛久大仏" > "高さ"')["items"][0])

    def test_qa_shots_include_big_acting(self):
        sys.path.insert(0, os.path.join(fakes.VIDEO, "yukkuri-qa"))
        import qa
        views = [{"t": i * 10.0, "sec": 10.0, "kind": "photo", "key": False} for i in range(30)]
        times = qa.pick_times(views, 300, 12, acts=[33.3, 77.7, 150.1, 222.2])
        self.assertLessEqual(len(times), 12)
        self.assertEqual(len([t for t in times if t in (33.3, 77.7, 150.1, 222.2)]), 3)   # 12 枚のうち 1/4 まで


class Pages(unittest.TestCase):
    def test_refused_page_says_what_to_do_and_does_not_stop_verify(self):
        claims = fakes.skill("fact-check")
        if not claims:
            self.skipTest("fact-check が無い")
        import claims as C
        import urllib.error

        def refuse(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        with mock.patch.object(C.urllib.request, "urlopen", refuse):
            with self.assertRaises(C.PageError) as e:
                C.fetch_text("https://example.com/x")
        self.assertIn("機械からの取得を断っています", str(e.exception))
        self.assertTrue(issubclass(C.PageError, Exception) and not issubclass(C.PageError, SystemExit))   # verify は Exception を受けて次の引用へ進む


class Icons(unittest.TestCase):
    def test_used_in_ignores_embedded_data(self):
        import icons
        name = next(iter(icons.ICONS))
        other = [n for n in icons.ICONS if n != name][0]
        big = '{"icon": "%s", "src": "data:audio/x-wav;base64,%s", "x": "%s"}' % (name, "A" * (1 << 20), "'%s'" % other)
        self.assertEqual(sorted(icons.used_in(big)), sorted([name, other]))


class Images(unittest.TestCase):
    def test_author_is_a_name_not_boilerplate(self):
        for raw, want in (("No machine-readable author provided. N yotarou assumed (based on copyright claims).", "N yotarou"),
                          ("Citron You must credit this photo as follows", "Citron"),
                          ('<a href="x">Hans Müller</a> [user: Hans, mail: a@b.c]', "Hans Müller"),
                          ("Dr. Karl-Heinz Hochhaus", "Dr. Karl-Heinz Hochhaus"),
                          ("Raita Futo from Tokyo, Japan", "Raita Futo from Tokyo, Japan"),
                          ("秋空から蛇が降ってきた", "秋空から蛇が降ってきた"), ("", "")):
            self.assertEqual(fetch_images.author(raw), want, raw)
        self.assertLessEqual(len(fetch_images.author("A " * 80)), 61)

    def test_category_listing_and_default_width(self):
        asked = []

        def get(url, binary=False):
            asked.append(url)
            return {"query": {"pages": {"1": {"title": "File:A.jpg", "imageinfo": [{"width": 3000, "height": 2000, "thumburl": "u", "descriptionurl": "p",
                    "extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"}, "Artist": {"value": "Someone You must credit"}}}]}}}}
        with mock.patch.object(fetch_images, "get", get):
            out = fetch_images.commons("Lake Hillier", 3, 1920, category=True)
        self.assertIn("generator=categorymembers", asked[0])
        self.assertIn("gcmtitle=Category%3ALake+Hillier", asked[0])
        self.assertIn("iiurlwidth=1920", asked[0])
        self.assertEqual(out[0]["author"], "Someone")


if __name__ == "__main__":
    unittest.main()
