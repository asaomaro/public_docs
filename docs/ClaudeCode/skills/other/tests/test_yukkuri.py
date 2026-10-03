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

    def test_big_label(self):
        """@show: 写真 "題" big（画面いっぱいの写真に、題を大きく出す）が台本から engine へ渡る。"""
        import kaisetsu
        it = kaisetsu.parse_show('tani "関西の秘境10選" big')["items"][0]
        self.assertEqual((it["label"], it.get("big")), ("関西の秘境10選", True))
        self.assertNotIn("big", kaisetsu.parse_show('tani "名札" > "吹き出し" frame')["items"][0])
        self.assertIn("solo[0].big", open(os.path.join(fakes.MV, "engine.js"), encoding="utf-8").read())

    def test_caption_width_with_two_on_one_side(self):
        """3 人（左に 2 人）のとき、帯の字幕は 2 人ぶんの立ち絵を避けて折り返す（1 行の長い字幕が立ち絵にかかった）。"""
        import kaisetsu
        seen = {}
        for n, cast in ((2, "metan, zundamon"), (3, "metan, zundamon, tsumugi")):
            talk = {"caption": "bar"}
            c = {k: {"height": 600, "sprite": {"w": 400, "h": 800}, "side": s} for k, s in zip(cast.split(", "), ("left", "right", "left"))}
            wide = 600 * 400 / 800
            per = max(sum(1 for v in c.values() if v["side"] == sd) for sd in ("left", "right"))
            seen[n] = int(1920 - 2 * (wide * (.8 + .75 * (per - 1)) + 40))
        self.assertLess(seen[3], seen[2])
        src = open(os.path.join(fakes.YK, "kaisetsu.py"), encoding="utf-8").read()
        self.assertIn(".75 * (per - 1)", src)


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
        self.assertGreater(build.min_seconds({"type": "end", "lines": ["a"] * 20}), 15)
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
        spec, _, _, _, out, path = make(script=head + '# 一\n@bg: sky\n@show: "語"\nmetan: 一よ。\n# 二\n@show: "語 2"\nmetan: 二よ。\n')
        bgs = [sc.get("bg") for ch in spec["chapters"] for sc in ch["scenes"] if sc.get("type") != "end"]
        self.assertTrue(all(bgs) and len(set(bgs)) == 1, bgs)
        self.assertNotIn("背景の無い画面", out)
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


if __name__ == "__main__":
    unittest.main()
