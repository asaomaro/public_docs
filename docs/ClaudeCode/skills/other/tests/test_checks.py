"""確かめる道具が、実際に起きた失敗を見つけるか（motion-video の check.py・yukkuri-qa の qa.py・yukkuri-kaisetsu の script_check.py・fact-check）。"""
import os
import unittest

import fakes
import build


def mv_check(spec, html_voices=None):
    """motion-video の check.py を、台本と（あれば）声の数を変えた HTML で走らせ、(直す所, 参考) の文を返す。"""
    import check as mvc
    d = fakes.tmpdir()
    path = fakes.write_json(os.path.join(d, "c.json"), spec)
    with fakes.fake_voicevox(alive=True), fakes.quiet():
        s = build.load(path)
        html = os.path.join(d, "c.html")
        with open(html, "w", encoding="utf-8") as f:
            f.write(build.build_html(s, "midnight", "studio", True) if html_voices is None else "<html>%s</html>" % ("data:audio/x-wav;base64,AA" * html_voices))
    R = mvc.Report()
    mvc.check_spec(s, R, None)
    mvc.check_html(s, html, R)
    return [r[2] for r in R.rows if r[0] == "warn"], [r[2] for r in R.rows if r[0] == "info"]


def base(**scene):
    sc = {"type": "bullets", "heading": "できること", "items": ["速い", "安全", "簡単"], "narration": ["速く作れます。", "安全に使えます。", "簡単に始められます。"]}
    sc.update(scene)
    return {"title": "t", "lang": "ja", "audio": {"narration": True, "music": None, "sfx": False, "voice": {"engine": "voicevox", "speaker": "四国めたん"}},
            "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t", "narration": "はじめに。"}]},
                         {"title": "b", "scenes": [sc]}, {"title": "c", "scenes": [{"type": "end", "title": "終", "narration": "おわり。"}]}]}


class MotionCheck(unittest.TestCase):
    def test_clean(self):
        warns, _ = mv_check(base())
        self.assertEqual(warns, [])

    def test_items_vs_cues(self):
        """2026-10: 長い文が読点で分かれて字幕が増え、項目が説明に合わずに均等に出た。"""
        warns, _ = mv_check(base(narration=["速く作れます。", "安全に使えます。", "簡単に始められて、設定もほとんど要らないので、すぐに使い始めることができます。"]))
        self.assertTrue(any("項目 3 個に、字幕が 4 個" in w for w in warns), warns)

    def test_odd_reading(self):
        warns, _ = mv_check(base(narration=["速く作れます。", "ブラウザを開けない所でも。", "Ctrl で始められます。"]))
        self.assertTrue(any("開け" in w for w in warns))
        self.assertTrue(any("Ctrl" in w for w in warns))

    def test_screen_text_same_as_narration(self):
        warns, _ = mv_check(base(items=["どこでも速く作れる仕組みです", "安全", "簡単"], narration=["どこでも速く作れる仕組みです。", "安全です。", "簡単です。"]))
        self.assertTrue(any("画面の文字とナレーションが同じ" in w for w in warns))

    def test_html_without_voices(self):
        """2026-10: 声の無い HTML（ブラウザの声＝別人の声）を配った。"""
        warns, _ = mv_check(base(), html_voices=0)
        self.assertTrue(any("声が 0 個しか入っていません" in w for w in warns), warns)

    def test_three_same_parts(self):
        sp = base()
        sp["chapters"][1]["scenes"] = [dict(sp["chapters"][1]["scenes"][0]) for _ in range(3)]
        warns, _ = mv_check(sp)
        self.assertTrue(any("3 場面続きます" in w for w in warns))


class ScriptCheck(unittest.TestCase):
    """yukkuri-kaisetsu の script_check.py（台本の検査）。"""

    def run_check(self, body):
        import importlib.util
        p = os.path.join(fakes.YK, "script_check.py")
        sp = importlib.util.spec_from_file_location("ycheck_t", p)
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        d = fakes.tmpdir()
        path = os.path.join(d, "s.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\ntitle: テスト\ncast: metan, zundamon\nroles: metan=解説, zundamon=聞き手\n---\n" + body)
        with fakes.quiet():
            R, _ = m.run(path)
        return [x[2] for x in R.items]

    def test_picture_reuse_and_layout_run(self):
        lines = ["# 本題"]
        for i in range(4):
            lines += ['@show: 積み木 "部品 %d" | → | 工具箱 "道具"' % i, "metan: 説明その%dよ。" % i, "zundamon: そうなのだ。"]
        lines += ["# まとめ", "metan: おわりよ。"]
        msgs = self.run_check("\n".join(lines) + "\n")
        self.assertTrue(any("積み木」を本編で 4 回" in m for m in msgs), msgs)
        self.assertTrue(any("2 つを並べた画面が 4 枚続きます" in m for m in msgs), msgs)

    def test_odd_reading(self):
        msgs = self.run_check("# 本題\nmetan: ブラウザを開けない所でも使えるわ。\nzundamon: すごいのだ。\n")
        self.assertTrue(any("開け" in m for m in msgs), msgs)


class FactCheck(unittest.TestCase):
    def test_url_with_parentheses(self):
        """2026-10: かっこを含む URL（Wikipedia の React_(software)）の閉じかっこを切り、照合できなかった。"""
        import claims
        self.assertEqual(claims.clean_url("https://en.wikipedia.org/wiki/React_(software)）"), "https://en.wikipedia.org/wiki/React_(software)")
        self.assertEqual(claims.clean_url("https://example.com/a)"), "https://example.com/a")   # 文の「（https://…）」の閉じだけ落とす
        self.assertEqual(claims.clean_url("https://en.wikipedia.org/wiki/React_(software)。"), "https://en.wikipedia.org/wiki/React_(software)")


if __name__ == "__main__":
    unittest.main()
