"""yukkuri-kaisetsu の台本 → 動画（偽の VOICEVOX で）と、yukkuri-qa の出来上がりの検査。"""
import os
import unittest
from unittest import mock

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

    def test_big_label(self):
        """@show: 写真 "題" big（画面いっぱいの写真に、題を大きく出す）が台本から engine へ渡る。"""
        import kaisetsu
        it = kaisetsu.parse_show('tani "関西の秘境10選" big')["items"][0]
        self.assertEqual((it["label"], it.get("big")), ("関西の秘境10選", True))
        self.assertNotIn("big", kaisetsu.parse_show('tani "名札" > "吹き出し" frame')["items"][0])
        self.assertIn("solo[0].big", open(os.path.join(fakes.MV, "engine.js"), encoding="utf-8").read())

    def test_caption_width_with_two_on_one_side(self):
        """3 人（左に 2 人・右に 1 人）のとき、帯の字幕は側ごとに立ち絵を避け、まん中を空いている右へ寄せる
        （1 行の長い字幕の頭が、左の 2 人目の立ち絵にかかった）。2 人のときは、まん中のまま。"""
        src = open(os.path.join(fakes.YK, "kaisetsu.py"), encoding="utf-8").read()
        self.assertIn('talk["capX"]', src)
        self.assertIn("TALK.capX", open(os.path.join(fakes.MV, "engine.js"), encoding="utf-8").read())
        wide, n = 272, {"left": 2, "right": 1}
        edge = {sd: wide * (.95 + .75 * (n[sd] - 1)) + 40 for sd in n}
        left_figures = 40 + wide * (1 + .75) * .93          # 左の 2 人が占める幅（絵の余白を除く）
        self.assertGreaterEqual(edge["left"], left_figures - 5)
        self.assertGreater(edge["left"] + (1920 - edge["left"] - edge["right"]) / 2, 960, "まん中が右へ寄っていない")


class Ending(unittest.TestCase):
    def test_ending_matches_the_talk(self):
        """2026-10-03: 締めの画面だけ、白い地に輪の印（題の頭の 1 字「ご」）と箱の列で、本編と作りが違いすぎた。行が多いとはみ出した。
        掛け合いの動画の締めは、本編の背景と立ち絵のまま、クレジットを全部・小さな字で出す。"""
        spec, _, _, _, _, _ = make()
        end = spec["chapters"][-1]["scenes"][-1]
        self.assertEqual((end["type"], end.get("variant")), ("end", "credits"))
        self.assertTrue(any("VOICEVOX" in x for x in end["lines"]))
        src = open(os.path.join(fakes.MV, "engine.js"), encoding="utf-8").read()
        self.assertIn('s.variant === "credits"', src)

    def test_music_runs_through_the_credits(self):
        """クレジットの画面に入った瞬間に BGM が止まっていた。締めの章の曲をそのまま流し、最後は映像と一緒に消す（endFade）。"""
        spec, _, _, _, _, _ = make(script="---\ntitle: t\ncast: metan, zundamon\nmusic: calm\n---\n# 本題\nmetan: 話すわ。\n# おわり\n@music: hope\nmetan: おわりよ。\n")
        self.assertTrue(spec["chapters"][-2].get("music"), "章の頭の @music が章の曲になっていない")
        self.assertEqual(spec["chapters"][-1].get("music"), spec["chapters"][-2].get("music"))
        plain = make()[0]   # 章の曲が無ければ、全体の曲のまま流れる（締めの章に曲を書かない）
        self.assertEqual(plain["chapters"][-1].get("music"), plain["chapters"][-2].get("music"))
        self.assertEqual(spec.get("endFade"), 2000)
        self.assertIn("SPEC.endFade", open(os.path.join(fakes.MV, "engine.js"), encoding="utf-8").read())

    def test_ending_is_short(self):
        """締めの画面が 20 秒近くあった（行の数だけ延びていた）。全部を一度に出すので 6 秒。end_seconds で変えられる。"""
        self.assertEqual(build.min_seconds({"type": "end", "variant": "credits", "lines": ["a"] * 20}), 6.0)
        self.assertEqual(build.min_seconds({"type": "end", "lines": ["a"] * 20}), 6.0, "motion-video の締めも、行の数では延ばさない")
        head = "---\ntitle: t\ncast: metan, zundamon\n%s---\n# 本題\nmetan: 話すわ。\n"
        self.assertEqual(make(script=head % "end_seconds: 12\n")[0]["chapters"][-1]["scenes"][-1].get("duration"), 12.0)


class Levels(unittest.TestCase):
    """2026-10-03: 効果音・BGM・声の大きさが、音色・曲・話者ごとにばらばらだった（BGM は曲で 17 dB、声は話者で 3 dB）。測ってそろえる。"""

    def test_voices_levelled_per_speaker(self):
        import kaisetsu
        d = fakes.tmpdir()
        def wav(name, amp):
            import math, struct, wave
            p = os.path.join(d, name)
            with wave.open(p, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(b"".join(struct.pack("<h", int(amp * 32767 * math.sin(i * .2))) for i in range(24000)))
            return p
        spec = {"cast": {"a": {"name": "A"}, "b": {"name": "B"}},
                "chapters": [{"scenes": [{"type": "talk", "lines": [{"who": "a", "text": "x", "voice": wav("a.wav", .05)}, {"who": "b", "text": "y", "voice": wav("b.wav", .2)},
                                                                    {"who": "a", "text": "z", "voice": wav("a2.wav", .05)}]}]}]}
        lv = kaisetsu.level_voices(spec)
        L = spec["chapters"][0]["scenes"][0]["lines"]
        self.assertGreater(L[0]["volume"], 1.5)
        self.assertLess(L[1]["volume"], .7)
        self.assertEqual(L[0]["volume"], L[2]["volume"], "同じ話者には同じ倍率")
        rms = lambda amp, g: amp / 2 ** .5 * g
        self.assertAlmostEqual(rms(.05, L[0]["volume"]), rms(.2, L[1]["volume"]), delta=.01)
        self.assertEqual(set(lv), {"a", "b"})

    def test_voice_gain_never_clips(self):
        import kaisetsu
        import struct, wave
        d = fakes.tmpdir(); p = os.path.join(d, "q.wav")
        with wave.open(p, "wb") as w:   # 小さな声に、1 つだけ大きな山
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(b"".join(struct.pack("<h", 30000 if i == 500 else int(600 * ((i % 40) - 20))) for i in range(24000)))
        spec = {"cast": {"a": {}}, "chapters": [{"scenes": [{"type": "talk", "lines": [{"who": "a", "text": "x", "voice": p}]}]}]}
        kaisetsu.level_voices(spec)
        self.assertLessEqual(spec["chapters"][0]["scenes"][0]["lines"][0].get("volume", 1) * 30000 / 32768, kaisetsu.VOICE_PEAK + .01)

    def test_bgm_gain_table(self):
        import bgm_levels
        g = bgm_levels.gains({"loud": .4, "mid": .2, "quiet": .1})
        self.assertEqual(g["mid"], 1)
        self.assertLess(g["loud"], 1)
        self.assertGreater(g["quiet"], 1)
        self.assertAlmostEqual(.4 * g["loud"], .1 * g["quiet"], places=3)
        import json
        names = {k for k in json.load(open(os.path.join(fakes.YK, "bgm.json"), encoding="utf-8")) if not k.startswith("_")}
        self.assertFalse(set(bgm_levels.load()) - names, "bgm_levels.json に、bgm.json に無い曲がある")


class Backgrounds(unittest.TestCase):
    def test_bg_carries_and_bare_is_ng(self):
        """@bg は次に書くまで続く（前は 1 場面だけで、次から白い地になった）。背景の無い画面は、作るときに warn、qa.py で NG。"""
        import kaisetsu
        import qa
        head = "---\ntitle: t\ncast: metan, zundamon\n---\n"
        meta, chapters, _ = kaisetsu.parse(head + '# 一\n@bg: sky\n@show: "語"\nmetan: 一よ。\n# 二\n@show: "語 2"\nmetan: 二よ。\n')   # 背景の素材が無い環境でも回るよう、台本の段で見る
        kaisetsu.carry_bg(meta, chapters)
        bgs = [sc.get("bg") for ch in chapters for sc in ch["scenes"]]
        self.assertTrue(all(bgs) and len(set(bgs)) == 1, bgs)
        self.assertFalse(kaisetsu.bare_scenes(meta, chapters))
        spec, _, _, _, out, path = make(script=head + '# 一\n@show: "語"\nmetan: 一よ。\n')
        self.assertIn("背景の無い画面が 1 枚", out)
        meta = kaisetsu.parse(open(path, encoding="utf-8").read())[0]
        meta["_stem"], meta["_bare"] = os.path.splitext(path)[0], [("一", "一よ。")]
        R = qa.Report()
        with fakes.quiet():
            qa.measure(spec, meta, {}, R)
        self.assertTrue([r for r in R.rows if r[0] == "warn" and "背景の無い画面" in r[2]])

    def test_full_photo_counts_as_background(self):
        import kaisetsu
        ch = [{"title": "a", "scenes": [{"lines": [{"who": "m", "text": "x"}], "board": {"type": "stage", "shots": [{"line": 0, "items": [{"ref": "p", "frame": True}]}]}}]}]
        self.assertFalse(kaisetsu.bare_scenes({"style": "list"}, ch))
        self.assertTrue(kaisetsu.bare_scenes({"style": "talk"}, ch))
        self.assertFalse(kaisetsu.bare_scenes({"style": "talk", "photo": "full"}, ch))
        two = [{"title": "a", "scenes": [{"lines": [{"who": "m", "text": "x"}], "board": {"type": "stage", "shots": [{"line": 0, "items": [{"ref": "p", "frame": True}, {"text": "語"}]}]}}]}]
        self.assertTrue(kaisetsu.bare_scenes({"style": "list"}, two), "写真 1 枚だけでない画面は、画面いっぱいにならない")
        self.assertFalse(kaisetsu.bare_scenes({"style": "zukai"}, two), "図解の型は紙の色の画面")


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


class LengthFit(unittest.TestCase):
    """2026-10-03: 「関西の秘境10選」を 5 分で受けて、1 か所 25 秒の薄い動画を最後まで作った。題の数と長さが合わなければ、作る前に知らせる。"""

    def setUp(self):
        self.m = OrderFormWithoutAssets.order(self)

    def test_count_from_title(self):
        for theme, n in (("関西の秘境10選", 10), ("危険な生き物ベスト20", 20), ("世界三大がっかり名所", 3), ("知らないと損する 7 つの制度", 7),
                         ("空はなぜ青いのか", 0), ("1954年の事件", 0), ("十二支の由来", 0)):
            self.assertEqual(self.m.item_count(theme), n, theme)

    def test_warns_before_making(self):
        a = {"theme": "関西の秘境10選", "length": "5", "intro": "chaban", "explainer": "metan", "listener": "zunko", "ensemble": "pair", "music": "builtin"}
        w = self.m.warnings(a)
        self.assertTrue(w and w[0].startswith("長さが足りない"), w)
        self.assertIn("10 分にする", w[0])
        self.assertIn("5 個に減らす", w[0])
        for ok in (dict(a, length="10"), dict(a, length="15"), dict(a, theme="世界三大がっかり名所", length="3", intro=""), dict(a, theme="空はなぜ青いのか")):
            self.assertFalse([x for x in self.m.warnings(ok) if "長さが足りない" in x], ok)

    def test_auto_length(self):
        """長さ「おまかせ」は、題の項目の数から決める（10 選 → 12 分）。数が無ければ、物語・寸劇は 10 分、ほかは 5 分。"""
        a = {"theme": "関西の秘境10選", "length": "auto", "intro": "chaban", "explainer": "metan", "listener": "zunko", "ensemble": "pair", "music": "builtin"}
        self.assertEqual(self.m.header(a)["length"], "12")
        self.assertFalse([x for x in self.m.warnings(a) if "長さが足りない" in x])
        self.assertEqual(self.m.header(dict(a, theme="空はなぜ青いのか"))["length"], "5")
        self.assertEqual(self.m.header(dict(a, theme="ある村の怪談", style="story"))["length"], "10")
        self.assertEqual(self.m.header(dict(a, length="5"))["length"], "5", "選んだ長さはそのまま")
        Q = {q["id"]: q for q in self.m.build_spec("")["questions"]}
        self.assertEqual(Q["length"]["default"], "auto")
        self.assertEqual(Q["length"]["options"][0]["value"], "auto")

    def test_help_on_the_form(self):
        Q = {q["id"]: q for q in self.m.build_spec("")["questions"]}
        self.assertIn("10 選なら", Q["length"]["help"])


class ShortFormat(unittest.TestCase):
    """ショート（縦の画面）: format: short が engine へ渡り、HTML の舞台が 9:16 になる。フォームの「ショート」は format: short を書く。"""

    def test_script_to_spec_and_html(self):
        head = "---\ntitle: t\ncast: metan, zundamon\n%s---\n# 本題\nmetan: 話すわ。\n"
        spec, mv, _, _, _, _ = make(script=head % "format: short\nlength: 1\n")
        self.assertEqual(spec["talk"].get("format"), "short")
        self.assertEqual(spec["talk"]["stage"]["photo"], "full")
        with fakes.quiet():
            page = mv.build_html(spec, spec["theme"], spec["player"], True)
        self.assertIn("aspect-ratio:9/16", page)
        wide = make(script=head % "")
        self.assertNotIn("format", wide[0]["talk"])
        with fakes.quiet():
            self.assertNotIn("aspect-ratio:9/16", wide[1].build_html(wide[0], wide[0]["theme"], wide[0]["player"], True))

    def test_no_credit_screen(self):
        """ショートには締めの画面（クレジット）を出さない。クレジットは info.json・概要欄へ。end: yes で出せる。"""
        head = "---\ntitle: t\ncast: metan, zundamon\nformat: short\n%s---\n# 本題\nmetan: 話すわ。\n"
        spec, _, _, _, _, _ = make(script=head % "")
        self.assertFalse([s for ch in spec["chapters"] for s in ch["scenes"] if s.get("type") == "end"])
        self.assertEqual(spec.get("endFade"), 600)
        import kaisetsu
        with fakes.fake_voicevox(True), fakes.quiet():
            credits = kaisetsu.make_spec(make(script=head % "")[5], True)[3]
        self.assertTrue(any("VOICEVOX" in c for c in credits), "画面に出さなくても、クレジットの一覧（info.json・概要欄用）は作る")
        self.assertTrue([s for ch in make(script=head % "end: yes\n")[0]["chapters"] for s in ch["scenes"] if s.get("type") == "end"])

    def test_form_header(self):
        m = OrderFormWithoutAssets.order(self)
        a = {"theme": "沖島", "length": "1", "intro": "chaban", "explainer": "metan", "listener": "zundamon", "ensemble": "pair", "music": "builtin"}
        h = m.header(a)
        self.assertEqual((h["length"], h.get("format")), ("1", "short"))
        self.assertNotIn("intro", h, "ショートには茶番を入れない")
        self.assertTrue([w for w in m.warnings(a) if "茶番を入れない" in w])
        self.assertNotIn("format", m.header(dict(a, length="5")))


LIST = """---
title: テスト 3 選
cast: metan, zundamon
roles: metan=解説, zundamon=聞き手
style: list
intro: chaban
---
# 茶番
metan: 茶番よ。
zundamon: 茶番なのだ。
# オープニング
metan: 今日は 3 つ紹介するわ。
# カブトエビ
metan: 1 つめよ。
zundamon: 田んぼにいるのだ。
# イチョウ
@corner: 街路樹の木
metan: 2 つめよ。
# シーラカンス
@corner:
metan: 3 つめよ。
zundamon: 札は出さないのだ。
# まとめ
metan: まとめよ。
# エンディング
metan: おわりよ。
"""


class Corner(unittest.TestCase):
    def test_numbers_only_item_chapters(self):
        """2026-10-03: 列挙の型で茶番とオープニングの章があると、右上の札の番号がずれた（オープニングが「1.」、項目が「2. カブトエビ」…）。
        番号は項目の章だけに振る。@corner: を書いた章はそれを使い、空なら出さない（前は消えなかった）。"""
        spec = make(script=LIST)[0]
        got = {ch["title"]: [sc.get("corner") for sc in ch["scenes"] if sc.get("type") == "talk"] for ch in spec["chapters"]}
        self.assertEqual(got["カブトエビ"], ["1. カブトエビ"])
        self.assertEqual(got["イチョウ"], ["街路樹の木"])
        self.assertEqual(got["オープニング"], ["オープニング"])     # 項目でない章は、番号なしの題
        self.assertEqual(got["まとめ"], ["まとめ"])
        self.assertEqual(got["エンディング"], ["エンディング"])
        self.assertFalse(any(got["シーラカンス"]), got["シーラカンス"])
        self.assertFalse(any(sc.get("corner") for sc in spec["chapters"][0]["scenes"]))


class Show(unittest.TestCase):
    def test_bubble_position(self):
        """2026-10-03: 画面いっぱいの写真の吹き出しは、いつも上の中央に出て、像や人の顔に重なった。台本から left・right・bottom を選べる。"""
        import kaisetsu
        it = kaisetsu.parse_show('daibutsu "牛久大仏" > "高さ 120m" left frame')["items"][0]
        self.assertEqual((it["label"], it["say"], it["sayAt"], it["frame"]), ("牛久大仏", "高さ 120m", "left", True))
        self.assertEqual(kaisetsu.parse_show('daibutsu > "下に出す" bottom')["items"][0]["sayAt"], "bottom")
        self.assertNotIn("sayAt", kaisetsu.parse_show('daibutsu "牛久大仏" > "高さ 120m"')["items"][0])
        self.assertEqual(kaisetsu.parse_show('daibutsu "牛久大仏" frame big')["items"][0], {"ref": "daibutsu", "label": "牛久大仏", "frame": True, "big": True})

    def test_png_photo_goes_full(self):
        """2026-10-03: PNG の写真は、1 枚だけでも画面いっぱいにならなかった（写真かどうかを拡張子の .jpg で決めていた）。
        色の多い、透明な所の無い PNG は写真とみる。地図・図・挿絵の PNG は、そのまま。frame・noframe を書けば、そちらに従う。"""
        import kaisetsu
        body = '# 本題\n@show: photo "写真"\nmetan: 写真よ。\n@show: map "地図"\nzundamon: 地図なのだ。\n@show: map "地図" frame\nmetan: 縁つきよ。\n@show: photo "写真" noframe\nzundamon: 縁なしなのだ。\n'
        d = fakes.tmpdir()
        os.makedirs(os.path.join(d, "images"))
        fakes.write_png(os.path.join(d, "images", "photo.png"), 240, 160, fakes.noise)
        fakes.write_png(os.path.join(d, "images", "map.png"), 240, 160, lambda x, y: (160, 200, 240) if (x // 24 + y // 24) % 5 else (250, 240, 180))
        path = os.path.join(d, "y.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(SCRIPT.split("# はじめに")[0].replace("---\n# ", "---\n") + body)
        with fakes.fake_voicevox(False), fakes.quiet():
            spec = kaisetsu.make_spec(path, False)[0]
        frames = [it["frame"] for ch in spec["chapters"] for sc in ch["scenes"] if isinstance(sc.get("board"), dict) for sh in sc["board"].get("shots", []) for it in sh["items"]]
        self.assertEqual(frames, [True, False, True, False])

    def test_board_bullets_fit(self):
        """2026-10-03: @board bullets の字がとても小さかった（黒板は部品を縮めて置く）。箇条書きは、板に収まる範囲で字を大きくする。"""
        import kaisetsu
        self.assertEqual(kaisetsu.parse_board("bullets: まとめ | 一つめ | 二つめ")["zoom"], "fit")
        self.assertEqual(kaisetsu.parse_board('{"type": "bullets", "items": ["a"]}')["zoom"], "fit")
        self.assertEqual(kaisetsu.parse_board('{"type": "bullets", "items": ["a"], "zoom": 1}')["zoom"], 1)


class QaNotes(unittest.TestCase):
    def test_rerun_keeps_scores(self):
        """2026-10-03: qa.py を回し直すと、<名前>.qa.md の「目で見る」の下に書き足してあった採点が消えた。測った値だけを書き換える。"""
        import qa
        path = make(script=SCRIPT)[5]
        out = os.path.splitext(path)[0] + ".qa.md"

        def run():
            with mock.patch("sys.argv", ["qa.py", path, "--no-shots"]), fakes.fake_voicevox(False), fakes.quiet():
                try:
                    qa.main()
                except SystemExit:
                    pass
            return open(out, encoding="utf-8").read()

        first = run()
        self.assertEqual(first.count("## 目で見る"), 1)
        note = "\n### 見た結果（1 回目・写っている画面 24 枚）\n- A 絵の中身: 3\n- 直す所: 5 枚目の名札\n\n## 2 回目の採点\n- A 絵の中身: 4\n"
        with open(out, "a", encoding="utf-8") as f:
            f.write(note)
        again = run()
        self.assertIn(note.strip(), again)
        self.assertEqual(again.count("## 測った値"), 1)
        self.assertEqual(again.count("- 別のエージェントに rubric.md"), 1)
        self.assertLess(again.index("## 測った値"), again.index("### 見た結果"))
        self.assertEqual(run(), again, "3 回目でも、書き足した分が増えも減りもしない")


class FetchImages(unittest.TestCase):
    def setUp(self):
        import importlib.util
        sp = importlib.util.spec_from_file_location("fetch_images_t", os.path.join(fakes.YK, "fetch_images.py"))
        self.F = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(self.F)

    def test_deleted_image_is_not_a_traceback(self):
        """2026-10-03: Commons で削除済みの画像を取ろうとすると、404 のトレースバックで落ちた。何が起きたかを 1 行で言って止まる。"""
        import urllib.error

        def gone(req, *a, **k):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", None, None)
        with mock.patch("urllib.request.urlopen", gone):
            with self.assertRaises(SystemExit) as e:
                self.F.get("https://upload.wikimedia.org/x.jpg", binary=True)
        self.assertIn("削除された", str(e.exception.code))
        self.assertIn("404", str(e.exception.code))

    def test_openverse_listing_and_symbol_author(self):
        """2026-10-03: --source openverse の候補に題が出なかった（URL だけ）。Flickr の作者名「*_*」が、そのままクレジットに入った。"""
        e = {"id": "https://live.staticflickr.com/1/2_b.jpg", "title": "Ushiku Daibutsu", "w": 1024, "h": 768, "license": "CC BY 2.0", "license_url": "", "author": "*_*",
             "desc": "", "url": "https://live.staticflickr.com/1/2_b.jpg", "page": "https://www.flickr.com/photos/o_0/2", "note": "", "from": "flickr"}
        self.assertIn("Ushiku Daibutsu", self.F.listing(1, e))
        self.assertIn("（題なし）", self.F.listing(1, dict(e, title="")))
        self.assertEqual(self.F.credit(e)["short"], "flickr の *_*（CC BY 2.0）")
        self.assertEqual(self.F.credit(dict(e, author="Ikusuki"))["short"], "Ikusuki（CC BY 2.0）")


if __name__ == "__main__":
    unittest.main()


class Inserts(unittest.TestCase):
    """2026-10-03: オープニング・チャンネル登録のお願いなど、用意した部品（別の台本）を差し込む（opening:・@insert:）。"""
    HEAD = "---\ntitle: 空の話\ncast: zundamon, metan\nroles: metan=解説, zundamon=聞き手\nbg: a.png\nmusic: calm\n%s---\n"
    BODY = "# つかみ\nzundamon: つかみなのだ。\n# 本題\n@bg: b.png\nmetan: 前よ。\n@insert: cm\nmetan: 後ろよ。\n# まとめ\nmetan: まとめよ。\n"

    def load(self, head="", body=BODY, parts=None):
        import kaisetsu
        d = fakes.tmpdir()
        os.mkdir(os.path.join(d, "parts"))
        for name, text in (parts or {"op": "@show: \"{title}\" | \"{channel|ここ}\"\n聞き手: はじまるのだ。\n> 解説(smile)\n",
                                     "cm": "---\nbg: c.png\nmusic: hope\nseconds: 3\n---\n# 見出しは章にしない\n@show: \"登録\"\n2: 登録してね。\n"}).items():
            with open(os.path.join(d, "parts", name + ".txt"), "w", encoding="utf-8") as f:
                f.write(text)
        meta, chapters, errs = kaisetsu.parse(self.HEAD % head + body)
        self.assertFalse(errs)
        with fakes.quiet():
            kaisetsu.insert_parts(meta, chapters, d, kaisetsu.build_cast(meta, d))
        return meta, chapters

    def test_opening_joins_the_first_chapter(self):
        meta, chapters = self.load("opening: op\n")
        self.assertEqual([c["title"] for c in chapters], ["つかみ", "本題", "まとめ"], "数秒の部品で章（YouTube のチャプター）を増やさない")
        first = chapters[0]["scenes"][0]
        self.assertEqual((first["_part"], first["lines"][0]["who"], first["lines"][0]["react_raw"][0]["who"]), ("op", "zundamon", "metan"))
        self.assertEqual([it.get("text") for it in first["board"]["shots"][0]["items"]], ["空の話", "ここ"], "{title} と、設定に無いときの既定")
        self.assertEqual(first.get("bg"), "a.png")

    def test_insert_in_the_middle_and_back(self):
        meta, chapters = self.load()
        sc = chapters[1]["scenes"]
        self.assertEqual([s.get("_part") for s in sc], [None, "cm", None])
        self.assertEqual((sc[1]["bg"], sc[1]["music"], sc[1]["duration"], sc[1]["lines"][0]["who"]), ("c.png", "hope", 3.0, "metan"))
        self.assertEqual((sc[2]["bg"], chapters[2]["scenes"][0]["bg"]), ("b.png", "b.png"), "部品が背景を替えても、続きは元の背景")
        self.assertEqual(sc[2]["lines"][0]["text"], "後ろよ。")

    def test_music_comes_back(self):
        import kaisetsu
        meta, chapters = self.load()
        for ch in chapters:
            for sc in ch["scenes"]:
                sc.pop("bg", None)
        with fakes.quiet():
            got = kaisetsu.to_spec(meta, chapters, kaisetsu.build_cast(meta, "."), ".")[0]
        self.assertEqual([sc.get("music") for sc in got["chapters"][1]["scenes"]], [None, "hope", "calm"], "部品の後は、その章で流れていた曲に戻る")

    def test_missing_part_stops(self):
        with self.assertRaises(SystemExit) as e:
            self.load(body="# 一\n@insert: nai\nmetan: あ。\n")
        self.assertIn("nai", str(e.exception))

    def test_bundled_parts_build(self):
        spec, _, lines, _, err, _ = make(script=self.HEAD.replace("bg: a.png\n", "") % "opening: opening\n" + self.BODY.replace("@bg: b.png\n", "").replace("@insert: cm", "@insert: subscribe"))
        self.assertIn("差し込んだ部品: opening", err)
        self.assertEqual([sc.get("_part") for ch in spec["chapters"][:2] for sc in ch["scenes"]], ["opening", None, None, "subscribe", None])
