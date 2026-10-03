#!/usr/bin/env python3
"""動画を作る前の指示を、ask-form の 1 つのウィンドウで聞く（テーマ・長さ・型・登場人物・音楽・絵・使い道・確かめ方）。

  python3 order.py                          # 聞いて、結果を ./order.json に書く（台本の先頭に書く設定 header も入る）
  python3 order.py --theme "空はなぜ青い"    # テーマを入れた状態で出す
  python3 order.py --out sky-blue/order.json
  python3 order.py --spec                   # 出す質問の定義（JSON）だけを見る

選択肢は、手元にあるものから作る: 登場人物は立ち絵を集めた人（yukkuri-kaisetsu の chars/。顔の見本つき）、
音楽は bgm/ にある曲（試聴つき。OpenTracks の曲は「WebM でだけ配れる」と出る）、型は styles.json。
前回の回答は次回の既定になる（テーマと自由記述は持ち越さない）。
終了コード: 0 回答あり / 2 キャンセル / 3 ウィンドウを出せない（AskUserQuestion で聞き直す。--spec の質問を分けて使う） / 4 時間切れ
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.join(os.path.dirname(HERE), "yukkuri-kaisetsu")
ASK = os.path.join(os.path.dirname(HERE), "ask-form", "ask.py")
load = lambda p: json.load(open(p, encoding="utf-8"))

POPULAR = ["zundamon", "metan", "reimu", "marisa", "tsumugi", "zunko", "kiritan", "itako"]


def cast_options(with_none=False):
    casts, chars = load(os.path.join(KDIR, "casts.json")), load(os.path.join(HERE, "characters.json"))
    opts = [{"value": "", "label": "なし", "group": "なし"}] if with_none else []
    rows = []
    for cid, c in casts.items():
        if cid.startswith("_") or not isinstance(c, dict) or len(cid) < 2:
            continue
        d = os.path.join(KDIR, "chars", cid)
        if not os.path.isdir(d):
            continue
        src = ""
        if os.path.isfile(os.path.join(d, "sprite.json")):
            src = load(os.path.join(d, "sprite.json")).get("source", "")
        group = ("よく出る" if cid in POPULAR else "ゆっくり" if cid in ("reimu", "marisa") else "坂本アヒルさんの立ち絵" if "坂本アヒル" in src
                 else "moiky さんの立ち絵" if "moiky" in src else "公式の立ち絵")
        P = chars.get(cid, {})
        desc = "・".join(x for x in (P.get("role", "")[:30], P.get("persona", "")[:40]) if x)
        o = {"value": cid, "label": c.get("name", cid), "group": group, "desc": desc}
        img = os.path.join(d, "normal.png")
        if os.path.isfile(img):
            o["image"] = img
        rows.append(o)
    order = ["よく出る", "坂本アヒルさんの立ち絵", "moiky さんの立ち絵", "公式の立ち絵", "ゆっくり"]
    rows.sort(key=lambda o: (order.index(o["group"]), POPULAR.index(o["value"]) if o["value"] in POPULAR else 99))
    return opts + rows


def bgm_options():
    J, moods = load(os.path.join(KDIR, "bgm.json")), {}
    moods = J.get("_moods", {})
    rows = []
    for k, v in J.items():
        if k.startswith("_") or not isinstance(v, dict) or "file" not in v:
            continue
        p = os.path.join(KDIR, "bgm", v["file"])
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
    styles = load(os.path.join(KDIR, "styles.json"))
    style_opts = [{"value": "auto", "label": "おまかせ（題材から選ぶ）", "recommended": True, "desc": "しくみ→掛け合いか図解、〇選→列挙、事件・怪談→物語か寸劇、商品→比べる"}]
    style_opts += [{"value": k, "label": "%s（%s）" % (v["name"], k), "desc": v["desc"][:70] + "。向くもの: " + v["fit"][:40]} for k, v in styles.items() if not k.startswith("_")]
    casts = cast_options()
    bgm = bgm_options()
    Q = [
        {"id": "theme", "label": "テーマ", "type": "text", "required": True, "default": theme, "placeholder": "例: 空はなぜ青いのか", "remember": False,
         "help": "1 本で答えられる問いか、題材の名前。広すぎるとき（「歴史について」）は、切り口を 3 つ出して選んでもらう"},
        {"id": "angle", "label": "切り口・入れてほしいこと（任意）", "type": "text", "multiline": True, "remember": False,
         "help": "見る人・言いたい結論・入れたい話・避けたい話など。空なら調べて決める"},
        {"id": "length", "label": "長さ", "default": "5", "options": [
            {"value": "1", "label": "ショート（1 分）", "desc": "縦の画面はまだ作れない（横で 1 分）"},
            {"value": "3", "label": "3 分", "desc": "1 つの問いに答える"},
            {"value": "5", "label": "5 分", "desc": "既定。答え＋理由＋広がり", "recommended": True},
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
        {"id": "explainer", "label": "解説役", "default": "metan", "options": casts, "preview": "inline", "thumb": 84, "minWidth": 118,
         "help": "立ち絵を集めてある人だけが並ぶ。顔の見本を押すと大きく見られる"},
        {"id": "listener", "label": "聞き手", "default": "zundamon", "options": casts, "preview": "inline", "thumb": 84, "minWidth": 118},
        {"id": "third", "label": "3 人目", "showIf": {"ensemble": "trio"}, "default": "tsumugi", "options": casts, "preview": "inline", "thumb": 84, "minWidth": 118},
        {"id": "cameo", "label": "一瞬だけ出るゲスト", "showIf": {"ensemble": "cameo"}, "default": "kiritan", "options": casts, "preview": "inline", "thumb": 84, "minWidth": 118},
        {"id": "narrator", "label": "語り手（声だけ）", "showIf": {"ensemble": "narrator"}, "default": "reimu", "options": casts, "preview": "inline", "thumb": 84, "minWidth": 118},
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
        {"id": "music", "label": "音楽", "default": "auto", "options": [
            {"value": "auto", "label": "おまかせ（雰囲気に合う曲を選ぶ）", "recommended": True, "desc": "章ごとに雰囲気を当てて選び、茶番・本編・締めで替える（music: auto）。使い道がアーティファクトなら、HTML に入れられる曲から"},
            {"value": "pick", "label": "曲を選ぶ（下で試聴して選ぶ）"},
            {"value": "builtin", "label": "motion-video の作曲（素材を使わない）", "desc": "Web Audio で鳴らす。配布の心配が無い"},
            {"value": "none", "label": "なし"}]},
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
    h["length"] = {"15": "15"}.get(a["length"], a["length"])
    if a.get("style") and a["style"] != "auto":
        h["style"] = a["style"]
    if a.get("intro") == "chaban":
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


def warnings(a):
    """答えどうしの食い違い（作る前に、使う人に伝える）。"""
    w = []
    J = load(os.path.join(KDIR, "bgm.json"))
    t = J.get(a.get("track") or "", {})
    if a.get("music") == "pick" and t.get("embed") is False and a.get("use") == "artifact":
        w.append("選んだ曲「%s」は HTML に入れて配れない（OpenTracks）ので、アーティファクトには入れられない。HTML に入れられる曲に替えるか、使い道を手元か YouTube（WebM）にする" % t.get("title"))
    if a.get("use") == "monetize":
        w.append("収益化する動画: いらすとやは 1 本 20 点まで。ゆっくりボイス（AquesTalk）は使用ライセンスが要る。立ち絵・BGM・背景の規約を確かめる（assets.md の確認表）")
        if "reimu" in (a.get("explainer"), a.get("listener"), a.get("third"), a.get("cameo"), a.get("narrator")) or "marisa" in (a.get("explainer"), a.get("listener")):
            w.append("霊夢・魔理沙（きつねゆっくり）は、商用は事前の許諾と有償ライセンスが要る（個人の広告収益は無償の範囲）")
    if a.get("length") == "1":
        w.append("ショート（縦の画面）はまだ作れない。横の 1 分で作る")
    if a.get("explainer") == a.get("listener"):
        w.append("解説役と聞き手が同じ人になっている")
    return w


def main():
    ap = argparse.ArgumentParser(description="解説動画の指示を ask-form で聞く")
    ap.add_argument("--theme", default="")
    ap.add_argument("--out", default="order.json")
    ap.add_argument("--spec", action="store_true", help="質問の定義を出すだけ")
    a = ap.parse_args()
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
