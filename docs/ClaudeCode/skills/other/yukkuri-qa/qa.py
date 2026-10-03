#!/usr/bin/env python3
"""出来上がった解説動画（yukkuri-kaisetsu の台本）を、手本の動画から取った目安と照らす。数えられるものを測り、目で見るための見本の一覧画像を作る。

  python3 qa.py 台本.txt                 # 測って、<台本名>.qa.md と <台本名>_qa/sheet.jpg（画面の見本の一覧）を作る
  python3 qa.py 台本.txt --no-shots      # 画面を撮らない（数だけ）
  python3 qa.py 台本.txt --max-shots 36  # 撮る画面の数（既定 24。画面が替わる時刻から、まんべんなく選ぶ）

測るもの: 構成（章の数と長さ・冒頭）、画面（絵のある割合・同じ画面の長さ・型に合う絵の種類）、字幕（長さ）、音（BGM・効果音の回数・声）、演技（表情の続き）、仕上げ。
台本の中身（口調・掛け合い・事実）は yukkuri-script の check.py・review.md と fact-check が見る。ここで見るのは、作った動画そのもの。
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.join(os.path.dirname(HERE), "yukkuri-kaisetsu")
if not os.path.isfile(os.path.join(KDIR, "kaisetsu.py")):
    sys.exit("error: yukkuri-kaisetsu スキルが見つかりません（%s）。同じ場所に置いてください" % KDIR)
sys.path.insert(0, KDIR)
import kaisetsu as K

NORMS = json.load(open(os.path.join(HERE, "norms.json"), encoding="utf-8"))
SFX_EMOTES = {"!", "?", "!?", "♪", "💦", "💢", "…", "💡", "✨", "♥", "gloom", "shock"}


def fmt(sec):
    return "%d:%02d" % (sec // 60, sec % 60)


class Report:
    def __init__(self):
        self.rows, self.stats = [], []

    def add(self, level, area, msg):
        self.rows.append((level, area, msg))

    def stat(self, area, name, value, norm=""):
        self.stats.append((area, name, value, norm))


def within(v, rng):
    return rng[0] <= v <= rng[1]


def measure(spec, meta, info, R):
    style = meta.get("style", "talk")
    N = dict({k: v[0] for k, v in NORMS["common"].items()}, **{k: v[0] for k, v in NORMS.get(style, NORMS["talk"]).items()})
    chapters, t = [], 0.0
    views, lines = [], []          # 画面（絵の並び 1 つ・黒板 1 枚）と、せりふ
    for ch in spec["chapters"]:
        t0 = t
        for sc in ch["scenes"]:
            dur = sc.get("_dur", 0) / (1000.0 if sc.get("_dur", 0) > 600 else 1.0)
            cues = sc.get("_cues") or []
            ls = [l for l in sc.get("lines", []) if isinstance(l, dict)]
            for i, l in enumerate(ls):
                c = next((c for c in cues if len(c) > 4 and c[4] == i), None)
                lines.append(dict(l, t=t + (c[0] / 1000.0 if c else 0), scene=sc))
            b = sc.get("board")
            if isinstance(b, dict) and b.get("type") == "stage":
                starts = []
                for sh in b["shots"]:
                    c = next((c for c in cues if len(c) > 4 and c[4] == sh.get("line", 0)), None)
                    starts.append(c[0] / 1000.0 if c and sh.get("line") else 0.0)
                for sh, a, z in zip(b["shots"], starts, starts[1:] + [dur]):
                    items = sh.get("items", [])
                    cells = [it for it in items if "op" not in it]
                    kind = ("photo" if any(it.get("frame") for it in cells) else "draw" if any("draw" in it for it in cells) else "part" if any("part" in it for it in cells)
                            else "picture" if any(it.get("img") or it.get("icon") for it in cells) else "words")
                    views.append({"t": t + a, "sec": max(0, z - a), "kind": kind, "say": any(it.get("say") for it in cells), "ops": any("op" in it for it in items),
                                  "n": len(cells), "words": any("text" in it for it in cells), "scene": sc,
                                  "key": any("**" in str(it.get("text", "")) for it in cells)})
            elif ls or b:
                kind = "none" if not b else "photo" if isinstance(b, dict) and b.get("type") == "image" else "board"
                views.append({"t": t, "sec": dur, "kind": kind, "say": False, "ops": False, "n": 1, "words": False, "scene": sc})
            t += dur
        chapters.append({"title": ch["title"], "t": t0, "sec": t - t0})
    total = t
    talk = [c for c in chapters if any(l["scene"] in spec["chapters"][i]["scenes"] for l in lines for i in [chapters.index(c)])]

    # ---- 構成 ----
    R.stat("構成", "長さ", fmt(total))
    R.stat("構成", "型", "%s（%s）" % (style, K.STYLES.get(style, {}).get("name", "?")))
    body = [c for c in talk]
    R.stat("構成", "章", "%d 個（%s）" % (len(body), "・".join("%s %s" % (c["title"][:8], fmt(c["sec"])) for c in body)), "%d〜%d 個" % tuple(N["chapters"]))
    if total >= 180 and not within(len(body), N["chapters"]):
        R.add("warn", "構成", "章が %d 個です（この型の目安は %d〜%d 個）" % ((len(body),) + tuple(N["chapters"])))
    if body:
        intro = body[0]["sec"]
        R.stat("構成", "冒頭の章", "%d 秒" % intro, "%d〜%d 秒" % tuple(N["intro_sec"]))
        if not within(intro, N["intro_sec"]) and total >= 120:
            R.add("warn", "構成", "冒頭の章が %d 秒です（目安 %d〜%d 秒。手本の中央値は 41 秒）" % ((intro,) + tuple(N["intro_sec"])))
        if total >= 300:
            for c in body[1:-1]:
                if not within(c["sec"], N["chapter_sec"]):
                    R.add("info", "構成", "章「%s」が %s です（この型の目安は %s〜%s）" % (c["title"], fmt(c["sec"]), fmt(N["chapter_sec"][0]), fmt(N["chapter_sec"][1])))
    if total < 480:
        R.add("info", "構成", "長さが 8 分未満です（手本の解説は 9〜24 分が多い。途中に広告を入れられるのは 8 分から）")

    # ---- 画面 ----
    vt = sum(v["sec"] for v in views) or 1
    share = lambda f: sum(v["sec"] for v in views if f(v)) / vt
    pic = share(lambda v: v["kind"] in ("photo", "picture", "draw", "part", "board")) + min(.15, share(lambda v: v["kind"] == "words"))   # 言葉だけの画面（題・項目の変わり目）は 15% まで数える
    R.stat("画面", "画面の数", "%d 枚（1 枚 平均 %.1f 秒）" % (len(views), vt / max(1, len(views))))
    R.stat("画面", "絵のある時間", "%d%%" % round(pic * 100), "%d%% 以上" % round(N["picture_ratio"] * 100))
    kinds = {}
    for v in views:
        kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    R.stat("画面", "内わけ", "　".join("%s %d" % ({"photo": "写真", "picture": "挿絵", "draw": "描き下ろし", "part": "部品", "board": "黒板", "words": "言葉だけ", "none": "絵なし"}[k], n) for k, n in kinds.items()))
    if pic < N["picture_ratio"]:
        R.add("warn", "画面", "絵のある時間が %d%% です（手本は、ほぼ全部の画面に絵がある）" % round(pic * 100))
    # 手本と並べて採点して分かった、自動で作った動画の手がかり（rubric.md の「自動らしさの照合表」）を、台本から数えられる分だけ数える
    words = [v for v in views if v["kind"] == "words" and not (v["scene"].get("board") or {}).get("shots", [{}])[0].get("title")]
    if views and len(words) / len(views) > N["words_ratio_max"]:
        R.add("warn", "画面", "字だけの画面が %d 枚（%d%%）あります（手本にはほとんど無い。大きな語だけ・「語 → 語」は、写真・資料・描き下ろしの図に）"
              % (len(words), round(len(words) * 100 / len(views))))
    nphoto = kinds.get("photo", 0)
    R.stat("画面", "写真・資料", "%d 枚" % nphoto, "1 枚以上（手本はどの型にもある）")
    if views and nphoto == 0:
        R.add("warn", "画面", "実物の写真・資料が 1 枚もありません（手本はどの型でも、話している人・物・場所を写真や当時の資料で見せる。fetch_images.py で取る）")
    own = sum(1 for v in views if v["kind"] == "draw" or v["say"])
    R.stat("画面", "その場面のための作り", "%d 枚（描き下ろし・絵の吹き出し）" % own, "写っている画面の 1 割以上")
    if views and own == 0:
        R.add("warn", "画面", "その場面のためだけの作り（描き下ろしの図・絵の吹き出し）がありません（手本は、見立て・描き足し・小さな寸劇で場面を作る）")
    for v in views:
        lim = N["view_sec_max_intro"] if v["t"] < 60 else N["view_sec_max"]
        if v["sec"] > lim + 3:
            R.add("warn", "画面", "%s から同じ画面が %d 秒続きます（%s は %d 秒まで）" % (fmt(v["t"]), v["sec"], "最初の 1 分" if v["t"] < 60 else "本編", lim))
    if N.get("photo_ratio") and share(lambda v: v["kind"] == "photo") < N["photo_ratio"]:
        R.add("warn", "型", "写真の画面が %d%% です（%s の型は、写真が主役。%d%% 以上に。fetch_images.py で取る）" % (round(share(lambda v: v["kind"] == "photo") * 100), style, round(N["photo_ratio"] * 100)))
    if N.get("figure_ratio") and share(lambda v: v["kind"] in ("draw", "part") or v["ops"] or (v["kind"] == "picture" and v["n"] >= 2)) < N["figure_ratio"]:
        R.add("warn", "型", "図の画面（絵と矢印・部品・描き下ろし）が少ないです（図解の型は、半分以上を図に）")
    if N.get("say_ratio"):
        if share(lambda v: v["say"]) < N["say_ratio"] and spec["talk"].get("caption") != "bubble":
            R.add("warn", "型", "吹き出しのある画面が少ないです（寸劇の型は、人の絵に名札と吹き出しを付ける）")
        if not any(c.get("hidden") for c in spec["cast"].values()):
            R.add("info", "型", "語り手がいません（寸劇の型は、narrator: で声だけの語りを置くと、場面の説明ができる）")
    first = next((v for v in views if v["kind"] != "none"), None)
    if first and first["t"] > 8:
        R.add("warn", "画面", "最初の絵が出るのが %d 秒目です（冒頭から絵か題を出す）" % first["t"])

    # ---- 字幕・演技 ----
    long = [l for l in lines if len(re.sub(r"\*\*|\s", "", l["text"])) > N["caption_chars"]]
    R.stat("字幕", "せりふ", "%d 個（平均 %.0f 字）" % (len(lines), sum(len(l["text"]) for l in lines) / max(1, len(lines))), "1 つ %d 字まで" % N["caption_chars"])
    for l in long[:8]:
        R.add("warn", "字幕", "%s のせりふが %d 字で、字幕が 2 行に収まらないおそれ: %s…" % (fmt(l["t"]), len(l["text"]), l["text"][:18]))
    cpm = sum(len(re.sub(r"\*\*|\s", "", l["text"])) for l in lines) / max(1, total / 60.0)
    R.stat("字幕", "1 分あたりの字数", "%d" % cpm, "%d〜%d" % tuple(N["chars_per_min"]))
    if not within(cpm, N["chars_per_min"]) and total > 60:
        R.add("info", "字幕", "1 分あたり %d 字です（目安 %d〜%d。少ないなら間が多い・多いなら早口）" % ((cpm,) + tuple(N["chars_per_min"])))
    run, last, worst = {}, {}, 0
    for l in lines:
        f = str(l.get("face", "")).split("#")[0]
        run[l["who"]] = run.get(l["who"], 0) + 1 if last.get(l["who"]) == f else 1
        last[l["who"]] = f
        worst = max(worst, run[l["who"]])
    R.stat("演技", "同じ表情の続き", "最長 %d せりふ" % worst, "%d まで" % N["same_face_run"])
    if worst > N["same_face_run"]:
        R.add("warn", "演技", "同じ人の同じ表情が %d せりふ続きます（表情・体・動きを変える）" % worst)
    reacts = sum(len(l.get("react") or []) for l in lines)
    R.stat("演技", "聞き手の反応", "%d 回" % reacts)

    # ---- 音 ----
    music = (spec.get("audio") or {}).get("music")
    tracks = {json.dumps(x.get("music"), sort_keys=True) for ch in spec["chapters"] for x in [ch] + ch["scenes"] if x.get("music") not in (None, "none")}
    if music and music != "none":
        tracks.add(json.dumps(music, sort_keys=True))
    else:
        music = None
    music = music or tracks
    R.stat("音", "BGM", "%d 曲" % len(tracks) if tracks else "なし", "茶番・本編・締めで替える（2〜4 曲）")
    if not music and not tracks:
        R.add("warn", "音", "BGM がありません（手本の動画は、全編に BGM がある）")
    elif total > 360 and len(tracks) <= 1:
        R.add("info", "音", "6 分を超えて、BGM が 1 曲だけです（music: auto か、章の雰囲気が変わる所の @music: で替えると、単調さが減る）")
    if meta.get("intro") == "chaban" and len(spec["chapters"]) > 1 and json.dumps(spec["chapters"][0].get("music")) == json.dumps(spec["chapters"][1].get("music")) and len(tracks) <= 1:
        R.add("info", "音", "冒頭の茶番と本編が同じ曲です（茶番はコミカルな曲にすると、本題に入った所が分かる）")
    sfx_off = spec["talk"].get("sfx") is False
    sfx = 0 if sfx_off else sum(1 for l in lines if l.get("se") or l.get("big") or l.get("shake") or l.get("emote") in SFX_EMOTES) + sum(1 for v in views if v["kind"] not in ("none",))
    per = sfx / max(1, total / 60.0)
    R.stat("音", "効果音のきっかけ", "%d 回（1 分あたり %.1f）" % (sfx, per), "1 分あたり %d〜%d" % tuple(N["sfx_per_min"]))
    if not within(per, N["sfx_per_min"]) and total > 60:
        R.add("warn" if per < N["sfx_per_min"][0] else "info", "音", "効果音が 1 分あたり %.1f 回です（目安 %d〜%d。ツッコミ・驚き・絵の出る所に）" % ((per,) + tuple(N["sfx_per_min"])))
    voiced = sum(1 for l in lines if l.get("voice"))
    R.stat("音", "声", "%d / %d せりふに声のファイル" % (voiced, len(lines)))
    if voiced < len(lines):
        R.add("warn", "音", "声のファイルが無いせりふが %d 個あります（ブラウザの読み上げになり、録画に入らない。--voicevox で作る）" % (len(lines) - voiced))
    html = meta["_stem"] + ".html"   # ここで数えたのは組み直した台本。配る HTML に声が入っているかは、HTML そのものを数える（声なしで上書きしたことがある）
    if voiced and os.path.isfile(html):
        inside = open(html, encoding="utf-8", errors="ignore").read()
        inside = len(re.findall(r"data:audio/(?:x-)?wav", inside))
        R.stat("音", "HTML の中の声", "%d 個" % inside)
        if inside < voiced * .9:
            R.add("warn", "音", "%s に声が %d 個しか入っていません（せりふは %d）。ブラウザの読み上げ（別人の声）になります。VOICEVOX を起動して kaisetsu.py で作り直す" % (os.path.basename(html), inside, voiced))

    # ---- 仕上げ ----
    stem = meta["_stem"]
    for name, what in ((".factcheck.md", "ファクトチェック（fact-check）"), (".review.md", "台本の見直し（yukkuri-script の review.md）")):
        if not os.path.isfile(stem + name):
            R.add("warn", "仕上げ", "%s の結果（%s）がありません" % (what, os.path.basename(stem + name)))
    for k in ("title", "summary", "thumb"):
        if not meta.get(k):
            R.add("info", "仕上げ", "台本の先頭に %s: がありません（yukkuri-publish）" % k)
    if info.get("irasutoya", 0) > 20:
        R.add("warn", "仕上げ", "いらすとやの絵が %d 点です（収益化する動画は 20 点まで）" % info["irasutoya"])
    return views, total


def shots(script, views, total, n, outdir):
    """画面が替わる時刻（の少し後）から、まんべんなく n 枚を撮り、番号と時刻つきの一覧画像にする。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("warn: Pillow が無いので、見本の一覧を作れません（pip install pillow）", file=sys.stderr)
        return None
    # 画面ごとに 1 枚。大事な画面（数字・大きい字幕・描き下ろし・写真）は必ず入れ、残りをまんべんなく選ぶ。撮る時刻は 1 枚おきに遅らせて、聞き手のせりふの間も写す
    cand = []
    for i, v in enumerate(v2 for v2 in views if v2["sec"] > 0.8):
        late = v["sec"] * (.5 if i % 2 == 0 else .82)
        cand.append((round(min(total - 1, v["t"] + min(v["sec"] - .3, max(1.2, late))), 1), v["kind"] in ("photo", "draw", "part") or v.get("key")))
    must = [t for t, k in cand if k][:max(0, n * 2 // 3)]
    rest = [t for t, k in cand if t not in must]
    room = max(0, n - len(must))
    if len(rest) > room:
        rest = [rest[round(i * (len(rest) - 1) / max(1, room - 1))] for i in range(room)] if room else []
    times = sorted(set(must + rest))
    html = os.path.splitext(script)[0] + ".html"
    if not os.path.isfile(html):
        print("warn: %s がありません（先に kaisetsu.py で作る）。画面は撮りません" % html, file=sys.stderr)
        return None
    K.take_shots(html, ["%.1f" % t for t in times], outdir)
    files = [os.path.join(outdir, "%07.2f.png" % t) for t in times]
    files = [(t, f) for t, f in zip(times, files) if os.path.isfile(f)]
    if not files:
        return None
    W, H, cols = 480, 270, 4
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (W * cols, (H + 26) * rows), "#1c1c22")
    d = ImageDraw.Draw(sheet)
    for i, (t, f) in enumerate(files):
        x, y = (i % cols) * W, (i // cols) * (H + 26)
        sheet.paste(Image.open(f).convert("RGB").resize((W, H)), (x, y + 26))
        d.text((x + 6, y + 6), "#%d  %s" % (i + 1, fmt(t)), fill="#ffffff")
    out = os.path.join(outdir, "sheet.jpg")
    sheet.save(out, quality=86)
    return out


def main():
    ap = argparse.ArgumentParser(description="出来上がった解説動画を、手本の動画の目安と照らす")
    ap.add_argument("script", help="台本（yukkuri-kaisetsu のテキスト）")
    ap.add_argument("--no-shots", action="store_true", help="画面を撮らない")
    ap.add_argument("--max-shots", type=int, default=24)
    a = ap.parse_args()
    stem = os.path.splitext(os.path.abspath(a.script))[0]
    try:
        spec, mv, cast, credits = K.make_spec(a.script, True)
    except SystemExit:
        spec, mv, cast, credits = K.make_spec(a.script, False)
    meta = K.parse(open(a.script, encoding="utf-8").read())[0]
    meta["_stem"] = stem
    info = json.load(open(stem + ".info.json", encoding="utf-8")) if os.path.isfile(stem + ".info.json") else {}
    R = Report()
    views, total = measure(spec, meta, info, R)
    sheet = None if a.no_shots else shots(a.script, views, total, a.max_shots, stem + "_qa")
    warns = [r for r in R.rows if r[0] == "warn"]
    out = ["# 動画の検査: %s" % os.path.basename(a.script), "", "## 測った値", "", "| 何を | 値 | 目安 |", "|---|---|---|"]
    out += ["| %s: %s | %s | %s |" % s for s in R.stats]
    out += ["", "## 直す所（%d）" % len(warns), ""] + (["- [%s] %s" % (r[1], r[2]) for r in warns] or ["- なし"])
    out += ["", "## 参考", ""] + (["- [%s] %s" % (r[1], r[2]) for r in R.rows if r[0] == "info"] or ["- なし"])
    out += ["", "## 目で見る（rubric.md）", "", "- 見本の一覧: %s（全 %d 画面のうち、撮ったもの。写っていない画面は採点に入らない）" % (sheet or "（撮っていない）", len(views)), "- 別のエージェントに rubric.md の観点で見てもらい、結果をこの下に書く", ""]
    open(stem + ".qa.md", "w", encoding="utf-8").write("\n".join(out))
    for s in R.stats:
        print("  %s: %s = %s%s" % (s[0], s[1], s[2], "（目安 %s）" % s[3] if s[3] else ""))
    for r in R.rows:
        print("%s: [%s] %s" % ("warn" if r[0] == "warn" else "参考", r[1], r[2]))
    print("%s : 直す所 %d 件。結果は %s%s" % ("OK" if not warns else "NG", len(warns), stem + ".qa.md", "、見本の一覧は %s" % sheet if sheet else ""))
    sys.exit(1 if warns else 0)


if __name__ == "__main__":
    main()
