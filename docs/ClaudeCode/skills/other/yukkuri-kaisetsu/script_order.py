#!/usr/bin/env python3
"""動画を作る前の指示を、ask-form の 1 つのウィンドウで聞く（テーマ・長さ・型・登場人物・音楽・絵・使い道・確かめ方）。

  python3 script_order.py                          # 聞いて、結果を ./order.json に書く（台本の先頭に書く設定 header も入る）
  python3 script_order.py --theme "空はなぜ青い"    # テーマを入れた状態で出す
  python3 script_order.py --out sky-blue/order.json
  python3 script_order.py --spec                   # 出す質問の定義（JSON）だけを見る

選択肢は、手元にあるものから作る: 登場人物は立ち絵を集めた人（chars/。顔の見本つき）、
音楽は bgm/ にある曲（試聴つき。OpenTracks の曲は「WebM でだけ配れる」と出る）、型は styles.json。
素材が無い環境（クローンしたばかり・コンテナ）でも出せる: 立ち絵が 1 人も無ければ、プリセット（casts.json）の全員を
顔の見本なしで並べ（仮のキャラクターで作る）、bgm/ に曲が無ければ、曲を選ぶ質問と「おまかせ」「曲を選ぶ」を出さない。
前回の回答は次回の既定になる（テーマと自由記述は持ち越さない）。
終了コード: 0 回答あり / 2 キャンセル / 3 ウィンドウを出せない（AskUserQuestion で聞き直す。--spec の質問を分けて使う） / 4 時間切れ
"""
import argparse
import re, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHARS = os.path.join(HERE, "chars")   # 集めた立ち絵（リポジトリには入らない）
BGM = os.path.join(HERE, "bgm")       # 集めた曲（同上）
ASK = os.path.join(os.path.dirname(HERE), "ask-form", "ask.py")
load = lambda p: json.load(open(p, encoding="utf-8"))

POPULAR = ["zundamon", "metan", "reimu", "marisa", "tsumugi", "zunko", "kiritan", "itako"]


def has_art(cid):
    return os.path.isdir(os.path.join(CHARS, cid))


def cast_options():
    """登場人物の選択肢。立ち絵を集めた人だけを並べる。1 人も集めていなければ、プリセットの全員を顔の見本なしで並べる
    （立ち絵が無くても、仮のキャラクターで最後まで作れるので、フォームも出せるようにする）。"""
    casts, chars = load(os.path.join(HERE, "casts.json")), load(os.path.join(HERE, "characters.json"))
    ids = [cid for cid, c in casts.items() if not cid.startswith("_") and isinstance(c, dict) and len(cid) >= 2]
    collected = [cid for cid in ids if has_art(cid)]
    rows = []
    for cid in collected or ids:
        c, d = casts[cid], os.path.join(CHARS, cid)
        if collected:
            src = ""
            if os.path.isfile(os.path.join(d, "sprite.json")):
                src = load(os.path.join(d, "sprite.json")).get("source", "")
            group = ("よく出る" if cid in POPULAR else "ゆっくり" if cid in ("reimu", "marisa") else "坂本アヒルさんの立ち絵" if "坂本アヒル" in src
                     else "moiky さんの立ち絵" if "moiky" in src else "公式の立ち絵")
        else:
            engine = (c.get("voice") or {}).get("engine")
            group = "よく出る" if cid in POPULAR else "ゆっくり" if engine == "aquestalk" else "VOICEVOX の話者"
        P = chars.get(cid, {})
        desc = "・".join(x for x in (P.get("role", "")[:30], P.get("persona", "")[:40]) if x)
        o = {"value": cid, "label": c.get("name", cid), "group": group, "desc": desc}
        img = os.path.join(d, "normal.png")
        if os.path.isfile(img):
            o["image"] = img
        rows.append(o)
    order = ["よく出る", "坂本アヒルさんの立ち絵", "moiky さんの立ち絵", "公式の立ち絵", "VOICEVOX の話者", "ゆっくり"]
    rows.sort(key=lambda o: (order.index(o["group"]), POPULAR.index(o["value"]) if o["value"] in POPULAR else 99))
    return rows


def pick(want, options, avoid=()):
    """既定にする値。want が選択肢にあればそれ、無ければ avoid に無い最初の選択肢（集めた立ち絵が一部だけのとき）。"""
    values = [o["value"] for o in options]
    return want if want in values else next((v for v in values if v not in avoid), values[0])


def bgm_options():
    J, moods = load(os.path.join(HERE, "bgm.json")), {}
    moods = J.get("_moods", {})
    rows = []
    for k, v in J.items():
        if k.startswith("_") or not isinstance(v, dict) or "file" not in v:
            continue
        p = os.path.join(BGM, v["file"])
        if not os.path.isfile(p):
            continue
        webm = v.get("embed") is False
        o = {"value": k, "label": "%s（%s）" % (v["title"], v["author"]), "group": moods.get(v.get("mood"), "そのほか"),
             "desc": ("WebM でだけ配れる。" if webm else "HTML にも入れられる。") + v.get("desc", "").replace("（見当。聴いて確かめていない）", "（雰囲気は見当）"), "audio": p}
        rows.append(o)
    order = list(moods.values()) + ["そのほか"]
    rows.sort(key=lambda o: order.index(o["group"]) if o["group"] in order else 99)
    return rows


def build_spec(theme=""):
    styles = load(os.path.join(HERE, "styles.json"))
    style_opts = [{"value": "auto", "label": "おまかせ（題材から選ぶ）", "recommended": True, "desc": "しくみ→掛け合いか図解、〇選→列挙、事件・怪談→物語か寸劇、商品→比べる"}]
    style_opts += [{"value": k, "label": "%s（%s）" % (v["name"], k), "desc": v["desc"][:70] + "。向くもの: " + v["fit"][:40]} for k, v in styles.items() if not k.startswith("_")]
    casts = cast_options()
    bgm = bgm_options()
    art = any(has_art(o["value"]) for o in casts)
    cast_q = {"options": casts, "minWidth": 118} if not art else {"options": casts, "preview": "inline", "thumb": 84, "minWidth": 118}
    explainer = pick("metan", casts)
    listener = pick("zundamon", casts, avoid=(explainer,))
    music_opts = [
        {"value": "auto", "label": "おまかせ（雰囲気に合う曲を選ぶ）", "recommended": True, "desc": "章ごとに雰囲気を当てて選び、茶番・本編・締めで替える（music: auto）。使い道がアーティファクトなら、HTML に入れられる曲から"},
        {"value": "pick", "label": "曲を選ぶ（下で試聴して選ぶ）"},
        {"value": "builtin", "label": "motion-video の作曲（素材を使わない）", "desc": "Web Audio で鳴らす。配布の心配が無い"},
        {"value": "none", "label": "なし"}]
    if not bgm:   # 曲を集めていない: おまかせ・曲を選ぶは選べない（music: auto は bgm/ の曲から選ぶので、BGM なしになる）
        music_opts = [dict(o, recommended=True) if o["value"] == "builtin" else o for o in music_opts if o["value"] in ("builtin", "none")]
    Q = [
        {"id": "theme", "label": "テーマ", "type": "text", "required": True, "default": theme, "placeholder": "例: 空はなぜ青いのか", "remember": False,
         "help": "1 本で答えられる問いか、題材の名前。広すぎるとき（「歴史について」）は、切り口を 3 つ出して選んでもらう"},
        {"id": "angle", "label": "切り口・入れてほしいこと（任意）", "type": "text", "multiline": True, "remember": False,
         "help": "見る人・言いたい結論・入れたい話・避けたい話など。空なら調べて決める"},
        {"id": "length", "label": "長さ", "default": "auto",
         "help": "〇選・ランキングは、項目 1 つに 40 秒〜2 分半かかる（5 選なら 5〜10 分、10 選なら 10〜15 分以上）。物語・事件は 1 章に 4〜5 分。合わないときは、作る前に確かめる",
         "options": [
            {"value": "auto", "label": "おまかせ", "desc": "題から決める。〇選・ランキングは項目 1 つ 1 分で（10 選なら 12 分）、物語・寸劇は 10 分、ほかは 5 分", "recommended": True},
            {"value": "1", "label": "ショート（縦の画面・1 分）", "desc": "縦 9:16 で作る（YouTube ショート・TikTok 向け）。問い 1 つに答えるだけ。茶番は入れない"},
            {"value": "3", "label": "3 分", "desc": "1 つの問いに答える"},
            {"value": "5", "label": "5 分", "desc": "答え＋理由＋広がり"},
            {"value": "10", "label": "10 分", "desc": "手本の動画の多くはこのくらいから（途中の広告は 8 分から）"},
            {"value": "15", "label": "15 分以上", "desc": "列挙 5〜7 個・物語 4〜6 章"}]},
        {"id": "style", "label": "動画の型（画面の作り）", "default": "auto", "options": style_opts},
        {"id": "tone", "label": "雰囲気", "default": "normal", "options": [
            {"value": "serious", "label": "まじめ", "desc": "ボケは少なく、解説が中心"},
            {"value": "normal", "label": "ふつう", "desc": "掛け合いのボケ・ツッコミを 1 分に 1 つ", "recommended": True},
            {"value": "funny", "label": "ネタ多め", "desc": "勘違いと寸劇を多く。説明は短く"}]},
        {"id": "audience", "label": "見る人", "default": "general", "options": [
            {"value": "general", "label": "その話題を知らない大人", "recommended": True},
            {"value": "kids", "label": "中学生くらい", "desc": "言葉をやさしく、たとえ話を多く"},
            {"value": "fans", "label": "くわしい人", "desc": "前提は省き、深い話を入れる"}]},
        {"id": "ensemble", "label": "登場人物の組み方", "default": "pair", "options": [
            {"value": "pair", "label": "2 人（解説＋聞き手）", "desc": "いちばん多い形", "recommended": True},
            {"value": "trio", "label": "3 人", "desc": "3 人目にも役（ボケ・ツッコミ・進行・専門家）を持たせる"},
            {"value": "cameo", "label": "2 人＋一瞬だけのゲスト", "desc": "ゲストは出番の場面だけ出る"},
            {"value": "narrator", "label": "語り手（声だけ）＋登場人物", "desc": "寸劇・物語の型で多い"}]},
        dict(cast_q, id="explainer", label="解説役", default=explainer,
             help=("立ち絵を集めてある人だけが並ぶ。顔の見本を押すと大きく見られる" if art else
                   "立ち絵をまだ集めていないので、プリセットの全員を並べている。仮のキャラクター（色つきの丸顔）で作る。立ち絵の集め方は assets.md")),
        dict(cast_q, id="listener", label="聞き手", default=listener),
        dict(cast_q, id="third", label="3 人目", showIf={"ensemble": "trio"}, default=pick("tsumugi", casts, avoid=(explainer, listener))),
        dict(cast_q, id="cameo", label="一瞬だけ出るゲスト", showIf={"ensemble": "cameo"}, default=pick("kiritan", casts, avoid=(explainer, listener))),
        dict(cast_q, id="narrator", label="語り手（声だけ）", showIf={"ensemble": "narrator"}, default=pick("reimu", casts, avoid=(explainer, listener))),
        {"id": "intro", "label": "冒頭", "default": "hook", "options": [
            {"value": "hook", "label": "すぐ本題（つかみ 15 秒）", "recommended": True},
            {"value": "chaban", "label": "冒頭に茶番（おふざけの寸劇 15〜40 秒）"},
            {"value": "opening", "label": "オープニング（あいさつと今日の中身 30〜60 秒）", "desc": "長い動画・列挙・物語の手本に多い"}]},
        {"id": "ending", "label": "締め", "default": "summary", "options": [
            {"value": "summary", "label": "まとめ＋ひとこと", "recommended": True},
            {"value": "chaban", "label": "締めに茶番（40 秒ほど）"},
            {"value": "opinion", "label": "独自の考察", "desc": "物語・事件の手本に多い"},
            {"value": "next", "label": "次回予告"}]},
        {"id": "use", "label": "使い道", "default": "local", "options": [
            {"value": "local", "label": "手元で見る", "desc": "集めた素材をそのまま使える", "recommended": True},
            {"value": "artifact", "label": "アーティファクトで見る（16MB まで）", "desc": "声と絵を小さくする。ダウンロードした曲（OpenTracks）は入れられない"},
            {"value": "youtube", "label": "YouTube に上げる（WebM に書き出す）", "desc": "題・概要欄・サムネイルも作る"},
            {"value": "monetize", "label": "YouTube で収益化する", "desc": "素材ごとに収益化の可否を確かめる。いらすとやは 20 点まで、ゆっくりボイスは使用ライセンスが要る"}]},
        dict({"id": "music", "label": "音楽", "default": "auto" if bgm else "builtin", "options": music_opts},
             **({} if bgm else {"help": "bgm/ に曲を集めていないので、おまかせ・曲を選ぶは出していない（集め方は assets.md。fetch_assets.py）"})),
        {"id": "track", "label": "曲", "showIf": {"music": "pick"}, "default": (bgm[0]["value"] if bgm else ""), "options": bgm,
         "help": "手元の bgm/ にある曲。▶ で試聴できる（曲の頭から鳴る）。「WebM でだけ配れる」曲は、HTML を配らない"},
        {"id": "pictures", "label": "絵の集め方（使ってよいもの）", "type": "multi", "default": ["photo", "irasutoya", "draw", "emoji"], "options": [
            {"value": "photo", "label": "写真（Wikimedia Commons。パブリックドメイン・CC0・CC BY）"},
            {"value": "irasutoya", "label": "いらすとや（人・しぐさ・場面。収益化なら 20 点まで）"},
            {"value": "draw", "label": "描き下ろしの図解（しくみを動きで見せる。山場に）"},
            {"value": "emoji", "label": "絵文字の絵（Fluent Emoji。もの・記号）"},
            {"value": "parts", "label": "グラフ・図の部品（棒・円・年表など）"}]},
        {"id": "speed", "label": "話す速さ", "default": "1.15", "options": [
            {"value": "1.0", "label": "ゆっくり（1.0）"}, {"value": "1.15", "label": "ふつう（1.15）", "recommended": True},
            {"value": "1.25", "label": "速め（1.25。解説動画の定番の上の方）"}]},
        {"id": "checks", "label": "確かめ方（別のエージェントにさせる）", "type": "multi", "default": ["factcheck", "review", "qa"], "options": [
            {"value": "factcheck", "label": "ファクトチェック（fact-check）", "desc": "1 回 3〜5 分"},
            {"value": "review", "label": "台本の見直し（構成・キャラクター・解説動画らしさ）", "desc": "2 回まで"},
            {"value": "qa", "label": "出来上がりの検査（yukkuri-qa。画面の採点）", "desc": "2 回まで"},
            {"value": "publish", "label": "題・概要欄・サムネイルを作る（yukkuri-publish）"}]},
    ]
    if not bgm:
        Q = [q for q in Q if q["id"] != "track"]
    return {"title": "解説動画の指示", "intro": "決めたことから台本と動画を作ります。既定のままでよい所は触らずに「この内容で作る」を押してください。",
            "submit": "この内容で作る", "remember": "yukkuri-order", "note": "ほかに伝えたいこと（任意）", "questions": Q}


def header(a):
    """回答 → 台本の先頭に書く設定（yukkuri-kaisetsu の書き方）。"""
    cast = [a["explainer"], a["listener"]]
    h = {}
    e = a.get("ensemble", "pair")
    if e == "trio" and a.get("third"):
        cast.append(a["third"])
    if e == "cameo" and a.get("cameo"):
        cast.append(a["cameo"]); h["cameo"] = a["cameo"]
    if e == "narrator" and a.get("narrator"):
        cast.append(a["narrator"]); h["narrator"] = a["narrator"]
    h["cast"] = ", ".join(dict.fromkeys(c for c in cast if c))
    h["roles"] = "%s=解説, %s=聞き手" % (a["explainer"], a["listener"])
    h["length"] = str(resolve_length(a))
    if h["length"] == "1":
        h["format"] = "short"                # 縦の画面（1080×1920）
    if a.get("style") and a["style"] != "auto":
        h["style"] = a["style"]
    if a.get("intro") == "chaban" and h["length"] != "1":
        h["intro"] = "chaban"
    h["speed"] = a.get("speed", "1.15")
    if a.get("music") == "pick" and a.get("track"):
        h["music"] = a["track"]
    elif a.get("music") == "auto":
        h["music"] = "auto"
        if a.get("use") == "artifact":
            h["music_pool"] = "embed"
    elif a.get("music") == "none":
        h["music"] = "none"
    if a.get("use") == "artifact":
        h["art"] = "png"
    return h


KANSUJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
COUNT_RE = re.compile(r"(?:ベスト|トップ|TOP|Top|top|ワースト)\s*(\d{1,3})|(\d{1,3}|[一二三四五六七八九十]{1,3})\s*(?:選|大|位|傑|か所|ヶ所|カ所|箇所|つの|個の|本の|人の|種の|か条|ヶ条)")
LENGTHS = (1, 3, 5, 10, 15)                 # フォームで選べる長さ（分）
ITEM_SEC = (40, 150)                        # 項目 1 つの長さ（秒）。下は 3 分の台本の「本題 1 つ 40 秒」（patterns.md の 1）、上は手本の中央値（yukkuri-qa の norms.json の list）
FRAME_SEC = 60                              # 冒頭（茶番・オープニング）と締めの分


def item_count(theme):
    """題から、並べる項目の数を読む（「関西の秘境10選」→ 10、「三大がっかり名所」→ 3）。読めなければ 0。"""
    m = COUNT_RE.search(theme or "")
    if not m:
        return 0
    s = m.group(1) or m.group(2)
    if s.isdigit():
        return int(s)
    n = 0
    for ch in s:                            # 十二 → 12、二十 → 20
        n = (n or 1) * 10 if ch == "十" else n + KANSUJI[ch]
    return n


AUTO_ITEM_SEC = 60                          # おまかせのときの、項目 1 つの長さ（秒）


def auto_length(theme, style="", intro=""):
    """長さ「おまかせ」→ 分。題に項目の数があれば 1 つ 1 分で（10 選 → 12 分）、物語・寸劇は 10 分、ほかは 5 分。"""
    n = item_count(theme)
    if n >= 2:
        frame = FRAME_SEC + (30 if intro == "chaban" else 0)
        return max(3, min(-(-(n * AUTO_ITEM_SEC + frame) // 60), 30))
    return 10 if style in ("story", "geki") else 5


def resolve_length(a):
    """回答の長さ（分）。「おまかせ」は auto_length で決める。"""
    v = a.get("length") or "auto"
    return auto_length(a.get("theme"), a.get("style"), a.get("intro")) if v == "auto" else v


def length_fit(theme, length, intro=""):
    """題の項目の数と長さが合っているか。合わなければ、どう直すかまで言う 1 文を返す（合っていれば ""）。"""
    n = item_count(theme)
    try:
        minutes = float(length)
    except (TypeError, ValueError):
        return ""
    if n < 2 or not minutes:
        return ""
    frame = FRAME_SEC + (30 if intro == "chaban" else 0)
    per = (minutes * 60 - frame) / n
    if per >= ITEM_SEC[0]:
        return ""
    need = next((m for m in LENGTHS if (m * 60 - frame) / n >= ITEM_SEC[0]), 0)
    fits = max(int((minutes * 60 - frame) // ITEM_SEC[0]), 1)
    grow = "直すなら、%d 分にする" % need if need else "直すなら、15 分より長くする（%d 個なら約 %d 分）" % (n, -(-(n * ITEM_SEC[0] + frame) // 60))
    return ("長さが足りない: %d 個を %s 分に収めると、1 つ約 %d 秒（写真 2〜3 枚と事実 2〜3 個で次へ進む。目安は 1 つ %d 秒〜%d 分半）。"
            "%s。または、項目を %d 個に減らす。作り始める前に、どちらにするかを確かめる"
            % (n, length, max(per, 0), ITEM_SEC[0], ITEM_SEC[1] // 60, grow, fits))


def warnings(a):
    """答えどうしの食い違い（作る前に、使う人に伝える）。"""
    w = []
    fit = length_fit(a.get("theme"), resolve_length(a), a.get("intro"))
    if fit:
        w.append(fit)
    J = load(os.path.join(HERE, "bgm.json"))
    t = J.get(a.get("track") or "", {})
    if a.get("music") == "pick" and t.get("embed") is False and a.get("use") == "artifact":
        w.append("選んだ曲「%s」は HTML に入れて配れない（OpenTracks）ので、アーティファクトには入れられない。HTML に入れられる曲に替えるか、使い道を手元か YouTube（WebM）にする" % t.get("title"))
    if a.get("use") == "monetize":
        w.append("収益化する動画: いらすとやは 1 本 20 点まで。ゆっくりボイス（AquesTalk）は使用ライセンスが要る。立ち絵・BGM・背景の規約を確かめる（assets.md の確認表）")
        if "reimu" in (a.get("explainer"), a.get("listener"), a.get("third"), a.get("cameo"), a.get("narrator")) or "marisa" in (a.get("explainer"), a.get("listener")):
            w.append("霊夢・魔理沙（きつねゆっくり）は、商用は事前の許諾と有償ライセンスが要る（個人の広告収益は無償の範囲）")
    if str(a.get("length")) == "1" and a.get("intro") == "chaban":
        w.append("ショート（1 分）には茶番を入れない（patterns.md の 2.5）。すぐ本題に入る")
    if a.get("explainer") == a.get("listener"):
        w.append("解説役と聞き手が同じ人になっている")
    e = a.get("ensemble", "pair")
    people = [a.get("explainer"), a.get("listener")] + [a.get(k) for k, on in (("third", "trio"), ("cameo", "cameo")) if e == on]
    bare = list(dict.fromkeys(p for p in people if p and not has_art(p)))
    if bare:
        w.append("立ち絵が無い人（%s）は、仮のキャラクター（色つきの丸顔）で描く。立ち絵の集め方は assets.md" % "・".join(bare))
    return w


def main():
    ap = argparse.ArgumentParser(description="解説動画の指示を ask-form で聞く")
    ap.add_argument("--theme", default="")
    ap.add_argument("--out", default="order.json")
    ap.add_argument("--spec", action="store_true", help="質問の定義を出すだけ")
    ap.add_argument("--fit", metavar="分", help="フォームを出さずに、--theme の項目の数と長さ（分）が合うかだけを確かめる（合わなければ終了コード 1）")
    a = ap.parse_args()
    if a.fit:
        msg = length_fit(a.theme, a.fit)
        print(msg or "OK : 長さは足りる（題に項目の数が無いときも OK）")
        sys.exit(1 if msg else 0)
    spec = build_spec(a.theme)
    if a.spec:
        print(json.dumps(spec, ensure_ascii=False, indent=1))
        return
    if not os.path.isfile(ASK):
        sys.exit("error: ask-form スキルが見つかりません（%s）。--spec の質問を AskUserQuestion で聞く" % ASK)
    r = subprocess.run([sys.executable, ASK, "-"], input=json.dumps(spec, ensure_ascii=False), capture_output=True, text=True)
    sys.stderr.write(r.stderr)
    try:
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.exit(r.returncode or 1)
    if res.get("status") != "answered":
        print(json.dumps(res, ensure_ascii=False))
        sys.exit(r.returncode)
    ans = res["answers"]
    out = {"answers": ans, "note": res.get("note", ""), "custom": res.get("custom", []), "header": header(ans), "warnings": warnings(ans)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))
    for w in out["warnings"]:
        print("warn: " + w, file=sys.stderr)
    print("OK : %s に書きました。header を台本の先頭（--- の間）に書き、answers に従って作る" % a.out, file=sys.stderr)


if __name__ == "__main__":
    main()
