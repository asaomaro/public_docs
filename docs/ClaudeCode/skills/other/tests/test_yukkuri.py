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


if __name__ == "__main__":
    unittest.main()
