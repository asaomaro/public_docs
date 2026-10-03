#!/usr/bin/env python3
"""作った動画（台本の JSON と HTML）を確かめる。数えられるものだけを見て、<台本名>.check.md に書く。画面の見た目は review.md で別の目に見てもらう。

  python3 check.py spec.json                  # 台本・読み・声・HTML を確かめる（HTML は spec と同じ名前の .html）
  python3 check.py spec.json --shots          # 各場面の終わり近く（項目が出そろった所）を撮り、一覧の画像を作る（Chrome が要る）
  python3 check.py spec.json --length 3-5     # 目安の長さ（分）と比べる（order.json があれば、その答えの長さを使う）
  python3 check.py spec.json --html out.html

見るもの:
  構成   章の数・最初と最後の場面・同じ部品が 3 つ続く・1 場面の文の数・長さ
  字幕   項目を順に出す部品で、項目と字幕の数がそろっているか（そろわないと、説明と出る時刻がずれる）・画面の文字とナレーションが同じ
  読み   VOICEVOX が読み違えやすい書き方（英字のまま・「開け」…）。かなまで見るなら build.py --readings
  声     VOICEVOX の声が HTML に入っているか（入っていないと、ブラウザの声＝別の声になる）・速さ
  音     長い動画で曲が 1 つだけ
終了コード: 0 直す所なし / 1 直す所あり
"""
import argparse, contextlib, io, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402

SEQ_FIELDS = ("items", "steps", "stages", "events")   # 項目を順に出す部品の、項目の並び（説明の文に合わせて出る）
NO_SYNC = {"table", "code", "terminal", "chat", "window", "phone", "dashboard", "notifs", "form", "flow", "tour", "scrollshot", "states", "custom", "dom", "talk", "layout"}
LENGTHS = {"short": (0.5, 0.75), "standard": (1, 2), "long": (3, 5), "longer": (5, 60)}


class Report:
    def __init__(self):
        self.rows, self.stats = [], []

    def add(self, level, area, msg, where=""):
        self.rows.append((level, area, msg, where))

    def stat(self, area, what, value, aim=""):
        self.stats.append((area, what, value, aim))


def norm(t):
    return re.sub(r"[\s、。，．！？!?「」『』（）()・…*]", "", str(t or ""))


def texts_of(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [v.get(k) for k in ("text", "title", "label") if isinstance(v.get(k), str)]
    return []


def check_spec(spec, R, target):
    au = spec.get("audio") or {}
    lang, pron = spec.get("lang", "ja"), au.get("pronounce") or {}
    chs = spec["chapters"]
    scenes = [(ci, si, s) for ci, ch in enumerate(chs) for si, s in enumerate(ch["scenes"])]
    total = sum(s.get("_dur", 0) for _, _, s in scenes) / 1000.0
    R.stat("構成", "長さ", "%d:%02d" % (total // 60, total % 60), "%g〜%g 分" % target if target else "")
    R.stat("構成", "章・場面", "%d 章・%d 場面" % (len(chs), len(scenes)), "4〜7 章・1 章に 1〜3 場面")
    if target and not (target[0] * 60 * .9 <= total <= target[1] * 60 * 1.1):
        R.add("warn", "構成", "長さ %d:%02d が目安（%g〜%g 分）から外れています" % (total // 60, total % 60, target[0], target[1]))
    if not 3 <= len(chs) <= 8:
        R.add("info", "構成", "章が %d 個です（目安 4〜7）" % len(chs))
    if scenes and scenes[0][2].get("type") not in ("title", "logo", "custom", "dom"):
        R.add("info", "構成", "最初の場面が %s です（title か logo で始めると、何の動画かが伝わる）" % scenes[0][2].get("type"))
    if scenes and scenes[-1][2].get("type") not in ("end", "custom", "dom"):
        R.add("info", "構成", "最後の場面が %s です（end で締めると、始め方・連絡先が残る）" % scenes[-1][2].get("type"))
    run = 1
    for (a, b) in zip(scenes, scenes[1:]):
        run = run + 1 if a[2].get("type") == b[2].get("type") else 1
        if run == 3:
            R.add("warn", "構成", "%s が 3 場面続きます（画面が同じに見える。別の部品をまぜる）" % b[2]["type"], where(b))
    for sc in scenes:
        s = sc[2]
        if build.is_dialogue(s):
            continue
        text = build.narration_text(s)
        groups = build.split_sentences(text, lang)
        cues = [c for g in groups for c in g]
        if len(groups) > 4:
            R.add("info", "構成", "1 場面に %d 文あります（2〜3 文が目安。場面を分けると、画面が話に付いてくる）" % len(groups), where(sc))
        # 項目を順に出す部品: 項目の数と字幕の数がそろっていないと、項目が文に合わず均等に出る
        sync = s.get("sync", spec.get("sync", "auto"))
        items = next((s[k] for k in SEQ_FIELDS if isinstance(s.get(k), list)), None)
        if items and s.get("type") not in NO_SYNC and sync == "auto" and len(cues) > 1 and len(items) > 1 and len(items) != len(cues):
            split = len(cues) - len(groups)
            R.add("warn", "字幕", "%s の項目 %d 個に、字幕が %d 個あります%s。項目が説明の文に合わず、場面の長さに均等に出ます"
                  "（文の数を項目にそろえるか、sync: true / false を書く）" % (s["type"], len(items), len(cues),
                                                                            "（長い文が読点で %d か所分かれた）" % split if split else ""), where(sc))
        # 画面の文字とナレーションが同じ
        shown = [t for k in ("heading", "title") for t in texts_of(s.get(k))] + [t for it in (items or []) for t in texts_of(it)]
        sents = {norm(c) for g in groups for c in ["".join(g)]}
        same = [t for t in shown if len(norm(t)) >= 12 and norm(t) in sents]   # 題名・製品名だけの一言（「Sodashitsu。」）は数えない
        if same:
            R.add("warn", "字幕", "画面の文字とナレーションが同じです（「%s」）。画面は要点の語、ナレーションは説明の文に" % same[0], where(sc))
        # 読み違えやすい書き方
        for g in groups:
            sp = build.spoken("".join(g), pron)
            for rx, why in build.ODD_READINGS:
                hit = rx.findall(sp)
                if hit:
                    R.add("warn", "読み", "「%s」 %s: %s" % ("".join(g)[:40], "・".join(dict.fromkeys(hit)), why), where(sc))
    # 音
    musics = {json.dumps(ch.get("music", au.get("music")), ensure_ascii=False) for ch in chs} | {json.dumps(s.get("music"), ensure_ascii=False) for _, _, s in scenes if "music" in s}
    musics.discard("null")
    R.stat("音", "曲", "%d 曲" % len(musics), "3 分を超えたら章で替える")
    if total > 180 and len(musics) <= 1 and au.get("music") not in (None, False, "none"):
        R.add("info", "音", "3 分を超えて、曲が 1 つだけです（章の music で、山場と締めの曲を替えると単調さが減る）")
    v = au.get("voice") or {}
    if v.get("engine") == "voicevox":
        sp = float(v.get("speed", au.get("speed", build.NARRATION_SPEED)))
        R.stat("声", "VOICEVOX", "%s（%s）・速さ %.2f" % (v.get("speaker", "四国めたん"), v.get("style", "ノーマル"), sp), "1.1〜1.2")
        if sp < 1.05:
            R.add("info", "声", "ナレーションの速さが %.2f です（説明の動画は 1.1〜1.2 が聞きやすい。audio.voice.speed）" % sp)
    return total


def where(sc):
    ci, si, s = sc
    return "第 %d 章 場面 %d（%s）" % (ci + 1, si + 1, s.get("type"))


def check_html(spec, html, R):
    au = spec.get("audio") or {}
    if not os.path.isfile(html):
        R.add("warn", "HTML", "%s がありません（build.py で作る）" % os.path.basename(html))
        return
    src = open(html, encoding="utf-8", errors="ignore").read()
    if (au.get("voice") or {}).get("engine") == "voicevox" and au.get("narration") is not False:
        want = sum(len(build.split_sentences(build.narration_text(s), spec.get("lang", "ja"))) for ch in spec["chapters"] for s in ch["scenes"] if not build.is_dialogue(s))
        got = len(re.findall(r"data:audio/(?:x-)?wav", src))
        R.stat("声", "HTML の中の声", "%d 個" % got, "%d 文" % want)
        if got < want * .9:
            R.add("warn", "声", "%s に声が %d 個しか入っていません（ナレーションは %d 文）。ブラウザの読み上げ（別の声）になります。"
                  "VOICEVOX を起動して build.py で作り直す" % (os.path.basename(html), got, want))
    R.stat("HTML", "大きさ", "%.1fMB" % (os.path.getsize(html) / 1e6), "アーティファクトは 16MB まで")


def shots(spec, html, outdir):
    """各場面の 85% の時刻を撮り、一覧（sheet.jpg、PIL が無ければ PNG だけ）を作る。"""
    chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
    if not chrome or not os.path.isfile(html):
        print("warn: Chrome か HTML が無いので、画面を撮れません", file=sys.stderr)
        return None
    os.makedirs(outdir, exist_ok=True)
    src, t, pngs = open(html, encoding="utf-8").read(), 0, []
    for ci, ch in enumerate(spec["chapters"]):
        for si, s in enumerate(ch["scenes"]):
            at = t + s["_dur"] * .85
            t += s["_dur"]
            png = os.path.join(outdir, "%02d-%02d.png" % (ci + 1, si + 1))
            hook = ('<style>.mv-stage{position:fixed!important;inset:0!important;z-index:99999!important;max-width:none!important;width:100vw!important;height:100vh!important}</style>'
                    '<script>window.addEventListener("load",function(){[700,2600].forEach(function(w){setTimeout(function(){try{__MV__.seek(%d)}catch(e){}},w)})})</script>' % at)
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8", dir=os.path.dirname(os.path.abspath(html))) as f:
                f.write(src + hook)
            try:
                for budget in (6000, 9000):
                    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1280,720", "--virtual-time-budget=%d" % budget,
                                    "--screenshot=" + png, "file://" + f.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
                    if os.path.isfile(png) and os.path.getsize(png) > 20000:
                        break
                pngs.append(png)
            finally:
                os.remove(f.name)
    try:
        from PIL import Image
    except ImportError:
        return outdir
    cols, w, h = 3, 640, 360
    sheet = Image.new("RGB", (cols * w, -(-len(pngs) // cols) * h), "white")
    for i, p in enumerate(pngs):
        sheet.paste(Image.open(p).convert("RGB").resize((w, h)), ((i % cols) * w, (i // cols) * h))
    out = os.path.join(outdir, "sheet.jpg")
    sheet.save(out, quality=85)
    return out


def main():
    ap = argparse.ArgumentParser(description="作った動画（台本と HTML）を確かめる")
    ap.add_argument("spec")
    ap.add_argument("--html", help="確かめる HTML（既定: 台本と同じ名前の .html）")
    ap.add_argument("--length", help="目安の長さ（分）。3-5 のように。order.json があれば、その答えから")
    ap.add_argument("--shots", action="store_true", help="各場面を撮って一覧を作る（<台本名>_check/）")
    a = ap.parse_args()
    stem = os.path.splitext(os.path.abspath(a.spec))[0]
    html = a.html or stem + ".html"
    log = io.StringIO()
    with contextlib.redirect_stderr(log):   # 声は作り済みを使い回すので、build と同じ時間割になる
        spec = build.load(a.spec)
    target = None
    if a.length:
        lo, _, hi = a.length.partition("-")
        target = (float(lo), float(hi or lo))
    else:
        op = os.path.join(os.path.dirname(os.path.abspath(a.spec)), "order.json")
        if os.path.isfile(op):
            target = LENGTHS.get((json.load(open(op, encoding="utf-8")).get("answers") or {}).get("length"))
    R = Report()
    for line in log.getvalue().splitlines():
        if line.startswith("warn:"):
            R.add("warn", "build", line[5:].strip())
    check_spec(spec, R, target)
    check_html(spec, html, R)
    sheet = shots(spec, html, stem + "_check") if a.shots else None
    warns = [r for r in R.rows if r[0] == "warn"]
    out = ["# 動画の確認: %s" % os.path.basename(a.spec), "", "## 測った値", "", "| 何を | 値 | 目安 |", "|---|---|---|"]
    out += ["| %s: %s | %s | %s |" % s for s in R.stats]
    fmt = lambda r: "- [%s] %s%s" % (r[1], r[2], "（%s）" % r[3] if r[3] else "")
    out += ["", "## 直す所（%d）" % len(warns), ""] + ([fmt(r) for r in warns] or ["- なし"])
    out += ["", "## 参考", ""] + ([fmt(r) for r in R.rows if r[0] == "info"] or ["- なし"])
    out += ["", "## 画面", "", "- 一覧: %s" % (sheet or "（撮っていない。--shots）"), "- 見た目は review.md の観点で、別のエージェントに見てもらう", ""]
    open(stem + ".check.md", "w", encoding="utf-8").write("\n".join(out))
    for s in R.stats:
        print("  %s: %s = %s%s" % (s[0], s[1], s[2], "（目安 %s）" % s[3] if s[3] else ""))
    for r in R.rows:
        print("%s: [%s] %s%s" % (r[0], r[1], r[2], "（%s）" % r[3] if r[3] else ""))
    print("%s : 直す所 %d 件。結果は %s%s" % ("OK" if not warns else "NG", len(warns), stem + ".check.md", "、画面の一覧は " + sheet if sheet else ""))
    sys.exit(1 if warns else 0)


if __name__ == "__main__":
    main()
