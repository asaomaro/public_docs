#!/usr/bin/env python3
"""動画を作る前の指示を、ask-form の 1 つのウィンドウで聞く（何の動画か・見る人・使い道・長さ・表現・プレイヤー・配色・背景・動き・音）。

  python3 order.py                           # 聞いて、結果を ./order.json に書く（台本の骨組み spec と、作るときの引数 build も入る）
  python3 order.py --subject "Sodashitsu の紹介"   # 何の動画かを入れた状態で出す
  python3 order.py --out intro/order.json
  python3 order.py --spec                    # 出す質問の定義（JSON）だけを見る
  python3 order.py --no-previews             # プレイヤーと動く背景の見本の画面を撮らない（Chrome が無いときも撮らない）

選択肢は build.py・sound.py の表から作る: プレイヤーと動く背景は実物の画面の見本つき（初回に Chrome で撮り ~/.cache/motion-video/order/ に置く）、
SVG の背景はファイルそのものが見本、配色は色の帯、曲は分類ごと（聞き比べは build.py --sounds）、話者は動いている VOICEVOX から引く。
前回の回答は次回の既定になる（何の動画か・資料・自由記述は持ち越さない）。
終了コード: 0 回答あり / 2 キャンセル / 3 ウィンドウを出せない（AskUserQuestion で聞き直す。--spec の質問を分けて使う） / 4 時間切れ
"""
import argparse, base64, json, os, re, shutil, subprocess, sys, tempfile, urllib.request
import html as html_mod

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build, sound   # noqa: E402


def find_skill(name):
    """ほかのスキルのフォルダを探す: 隣 → 1 つ上の階層の別のまとまり（other/・video/ など）→ ~/.claude/skills。無ければ None。"""
    import glob
    up = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    cands = [os.path.join(up, name)] + sorted(glob.glob(os.path.join(os.path.dirname(up), "*", name))) + [os.path.join(os.path.expanduser("~"), ".claude", "skills", name)]
    return next((c for c in cands if os.path.isdir(c)), None)


ASK = os.path.join(find_skill("ask-form") or os.path.join(os.path.dirname(HERE), "ask-form"), "ask.py")   # ask-form は別のまとまり（other/）にある。無ければ、端末の質問に切り替える
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "motion-video", "order")
VOICEVOX = "http://127.0.0.1:50021"

# 使い道 → プレイヤー・配布の既定（「おまかせ」のとき）
USE_PLAYER = {"local": "studio", "artifact": "studio", "embed": "minimal", "youtube": "cinema", "kiosk": "kiosk", "present": "slides", "lecture": "theater"}
LENGTH = {"short": "30〜45 秒（4 章・場面 5 前後）", "standard": "1〜2 分（6 章・場面 8〜10）", "long": "3〜5 分（7 章・場面 15〜25）", "longer": "5 分以上（章 7 以上。章ごとに音楽を替える）"}


def player_previews(make=True):
    """プレイヤーごとの見本の画面（PNG）。無ければ、小さな台本から作って Chrome で撮る。撮れなければ空。"""
    out = {p: os.path.join(CACHE, "player-%s.png" % p) for p in build.PLAYERS}
    if all(os.path.isfile(f) for f in out.values()):
        return out
    chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
    if not make or not chrome:
        return {p: f for p, f in out.items() if os.path.isfile(f)}
    os.makedirs(CACHE, exist_ok=True)
    spec = {"title": "見本の動画", "description": "プレイヤーの見た目の見本", "lang": "ja", "theme": "navy-brass", "audio": {"narration": False, "music": None, "sfx": False},
            "chapters": [{"title": "はじめに", "desc": "何ができるか", "scenes": [{"type": "title", "title": "見本の動画", "subtitle": "プレイヤーの見本", "narration": "これはプレイヤーの見本です。"}]},
                         {"title": "できること", "desc": "3 つの特徴", "scenes": [{"type": "bullets", "title": "できること", "items": ["速く作れる", "どこでも再生", "字幕と音声"], "narration": "できることは 3 つあります。"}]},
                         {"title": "数字で見る", "desc": "効果", "scenes": [{"type": "stats", "title": "効果", "items": [{"value": "3倍", "label": "速さ"}, {"value": "98%", "label": "満足"}], "narration": "効果を数字で見ます。"}]},
                         {"title": "おわりに", "desc": "始め方", "scenes": [{"type": "end", "title": "はじめよう", "narration": "ご覧いただきありがとうございました。"}]}]}
    for p, png in out.items():
        if os.path.isfile(png):
            continue
        try:
            s = json.loads(json.dumps(spec))
            errs = build.validate(s, HERE)
            if errs:
                raise ValueError("; ".join(errs[:3]))
            build.plan(s)
            html = build.build_html(s, "navy-brass", p, True)
        except Exception as e:   # 作れなければ見本なしで聞く
            print("warn: プレイヤー %s の見本を作れません（%s）" % (p, e), file=sys.stderr)
            continue
        hook = '<script>window.addEventListener("load",function(){setTimeout(function(){try{__MV__.seek(4200)}catch(e){}},600)})</script>'
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html + hook)
        try:
            subprocess.run([chrome, "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1100,960", "--virtual-time-budget=5000",
                            "--screenshot=" + png, "file://" + f.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        except Exception as e:
            print("warn: プレイヤー %s の見本を撮れません（%s）" % (p, e), file=sys.stderr)
        finally:
            os.remove(f.name)
    return {p: f for p, f in out.items() if os.path.isfile(f) and os.path.getsize(f) > 8000}


def backdrop_previews(make=True):
    """動く背景ごとの見本の画像（JPEG）。無ければ、Chrome を 1 回だけ動かして全部を描き、~/.cache に置く。撮れなければ空。"""
    out = {k: os.path.join(CACHE, "bg-%s.jpg" % k) for k in build.BACKDROPS}
    have = lambda: {k: f for k, f in out.items() if os.path.isfile(f) and os.path.getsize(f) > 1500}
    chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
    if len(have()) == len(out) or not make or not chrome:
        return have()
    os.makedirs(CACHE, exist_ok=True)
    spec = {"title": "背景の見本", "lang": "ja", "theme": "navy-brass", "chrome": False, "audio": {"narration": False, "music": None, "sfx": False},
            "chapters": [{"title": "a", "scenes": [{"type": "statement", "lines": [" "], "fx": False}]}]}
    try:
        errs = build.validate(spec, HERE)
        if errs:
            raise ValueError("; ".join(errs[:3]))
        build.plan(spec)
        html = build.build_html(spec, "navy-brass", "studio", True)
    except Exception as e:   # 作れなければ見本なしで聞く
        print("warn: 動く背景の見本を作れません（%s）" % e, file=sys.stderr)
        return have()
    # 1 枚ずつ 480×270 に描き、data URL を <pre> に書く（--dump-dom で受け取る）
    hook = ('<script>window.addEventListener("load",function(){setTimeout(function(){try{var cv=__MV__.drawAt(0),x=cv.getContext("2d"),B=__MV__.backdrops,o={},'
            'c=document.createElement("canvas");c.width=480;c.height=270;Object.keys(B).forEach(function(n){x.save();B[n].draw(.3,{});x.restore();'
            'c.getContext("2d").drawImage(cv,0,0,480,270);o[n]=c.toDataURL("image/jpeg",.8)});var p=document.createElement("pre");p.id="mv-bg-shots";'
            'p.textContent=JSON.stringify(o);document.body.appendChild(p)}catch(e){}},600)})</script>')
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html + hook)
    try:
        r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--window-size=1100,960", "--virtual-time-budget=6000", "--dump-dom", "file://" + f.name],
                           capture_output=True, text=True, timeout=90)
        m = re.search(r'<pre id="mv-bg-shots">(.*?)</pre>', r.stdout, re.S)
        for k, uri in (json.loads(html_mod.unescape(m.group(1))) if m else {}).items():
            if k in out and uri.startswith("data:image/jpeg;base64,"):
                with open(out[k], "wb") as g:
                    g.write(base64.b64decode(uri.split(",", 1)[1]))
    except Exception as e:
        print("warn: 動く背景の見本を撮れません（%s）" % e, file=sys.stderr)
    finally:
        os.remove(f.name)
    return have()


def background_options(previews=True):
    """背景の選択肢（動く背景・SVG の背景）。分類ごとに並べ、見本の画像を付ける（SVG はファイルそのもの。配色に合わせるものは紺と真鍮の色で見える）。"""
    shots, sv, opts = backdrop_previews(previews), build.bg_svgs(), []
    for k, d in build.BACKDROPS.items():
        o = {"value": k, "label": k, "desc": d, "group": "動く背景（ループする。色は配色に合う）"}
        if k in shots:
            o["image"] = shots[k]
        opts.append(o)
    groups = (("themed", None, "SVG の背景・配色に合わせる"), ("scenery", "dark", "SVG の背景・景色と場所（暗い絵。暗い配色で）"), ("scenery", "light", "SVG の背景・景色と場所（明るい絵。明るい配色で）"))
    for kind, tone, group in groups:
        for k, e in sv.items():
            if e["kind"] == kind and e.get("tone") == tone:
                opts.append({"value": k, "label": "%s（%s）" % (e["label"], k), "desc": e["desc"], "group": group, "image": os.path.join(build.BG_DIR, e["file"])})
    return opts


def voicevox_speakers(url=VOICEVOX):
    """動いている VOICEVOX の話者（名前・スタイル）。つながらなければ None。"""
    try:
        sp = json.loads(urllib.request.urlopen(url + "/speakers", timeout=3).read())
    except Exception:
        return None
    return [(s["name"], [t["name"] for t in s.get("styles", [])]) for s in sp]


def build_spec(subject="", previews=True):
    shots = player_previews(previews)
    players = [{"value": "auto", "label": "おまかせ（使い道から選ぶ）", "recommended": True,
                "desc": "手元・アーティファクト→スタジオ、埋め込み→ミニマル、YouTube→シネマ、展示→キオスク、発表→スライド、講演→シアター"}]
    for k, v in build.PLAYERS.items():
        o = {"value": k, "label": "%s（%s）" % (v[0], k), "desc": v[1]}
        if k in shots:
            o["image"] = shots[k]
        players.append(o)
    palettes = [{"value": "auto", "label": "おまかせ（内容とブランドの色から選ぶ）", "recommended": True}]
    for k, t in build.THEMES.items():
        c = t["canvas"]
        palettes.append({"value": k, "label": "%s（%s）" % (t["label"], k), "desc": t["desc"], "colors": [c["bg0"], c["panel"], c["accent"], c["accent2"], c["ink"]]})
    backgrounds = background_options(previews)
    motions = [{"value": "auto", "label": "おまかせ（内容と見る人から選ぶ）", "recommended": True}]
    motions += [{"value": k, "label": k, "desc": v} for k, v in build.MOTION_STYLES.items()]
    tracks = [{"value": k, "label": "%s（%s）" % (v["name"], k), "group": v["cat"], "desc": v["desc"]} for k, v in sound.MUSIC.items()]
    order = list(sound.MUSIC_CATS)
    tracks.sort(key=lambda o: order.index(o["group"]) if o["group"] in order else 99)
    kits = [{"value": "auto", "label": "おまかせ（曲の雰囲気にそろえる）", "recommended": True}]
    kits += [{"value": k, "label": "%s（%s）" % (v[0], k), "desc": v[1]} for k, v in sound.KITS.items()]
    vv = voicevox_speakers()
    if vv:
        names = [n for n, _ in vv]
        first = "四国めたん" if "四国めたん" in names else names[0]
        speakers = [{"value": n, "label": n, "desc": "スタイル: " + "・".join(st[:6]), "recommended": n == first} for n, st in vv]
        vv_note = "動いている VOICEVOX（%d 人）から選べる" % len(vv)
    else:
        first = "四国めたん"
        speakers = [{"value": n, "label": n} for n in ("四国めたん", "ずんだもん", "春日部つむぎ", "雨晴はう", "冥鳴ひまり", "青山龍星", "WhiteCUL", "No.7")]
        vv_note = "VOICEVOX が動いていない（作る前に起動する）。名前は代表的な人だけ"
    narr = ["full", "composed", "narration"]
    Q = [
        {"id": "subject", "label": "何の動画か", "type": "text", "required": True, "default": subject, "remember": False,
         "placeholder": "例: Sodashitsu（社内の開発環境）の紹介", "help": "紹介・説明するもの。製品・サービス・手順・仕組み・報告など"},
        {"id": "materials", "label": "元になる資料（任意）", "type": "text", "multiline": True, "remember": False,
         "placeholder": "README.md、docs/、https://…、画面の画像 screenshots/*.png など", "help": "ファイルのパス・URL・メモ。空なら会話とリポジトリから集める"},
        {"id": "message", "label": "見た人に残したいこと（任意）", "type": "text", "remember": False, "placeholder": "例: 5 分で使い始められる",
         "help": "締めの一言と、構成の軸にする"},
        {"id": "audience", "label": "見る人", "default": "general", "options": [
            {"value": "internal", "label": "社内の人", "desc": "前提を共有している。手順・効果を具体的に"},
            {"value": "customer", "label": "顧客・見込み客", "desc": "困りごと → 解決 → 効果の順に"},
            {"value": "developer", "label": "開発者", "desc": "コード・コマンド・構成の図を多めに"},
            {"value": "general", "label": "一般の人", "desc": "専門の言葉を言い換える", "recommended": True},
            {"value": "kids", "label": "子ども", "desc": "言葉をやさしく、動きを楽しく"}]},
        {"id": "use", "label": "使い道", "default": "local", "options": [
            {"value": "local", "label": "手元で見る・社内で配る（HTML）", "recommended": True},
            {"value": "artifact", "label": "アーティファクトで見せる（16MB まで）", "desc": "声と画像を小さくする。3 分くらいまで"},
            {"value": "embed", "label": "文書・ページに埋め込む", "desc": "md-to-doc の文書や、ほかの HTML の中に並べる（--embed）"},
            {"value": "youtube", "label": "YouTube・SNS に上げる（WebM に書き出す）", "desc": "声は VOICEVOX で前もって作る。字幕・チャプターは video-export"},
            {"value": "present", "label": "発表の場で、話しながら送る", "desc": "章の終わりで止まる"},
            {"value": "lecture", "label": "講演・録画の公開（文字起こしつき）"},
            {"value": "kiosk", "label": "展示・受付の画面で流す", "desc": "自動再生・繰り返し・音なしで始まる"}]},
        {"id": "length", "label": "長さ", "default": "standard", "options": [
            {"value": k, "label": v, "recommended": k == "standard"} for k, v in LENGTH.items()]},
        {"id": "expression", "label": "表現", "default": "mixed", "options": [
            {"value": "mixed", "label": "混在（部品で組み、見せ場だけ描き下ろす）", "desc": build.EXPRESSIONS["mixed"], "recommended": True},
            {"value": "components", "label": "部品だけ（速く、ぶれにくい）", "desc": build.EXPRESSIONS["components"]},
            {"value": "free", "label": "自由（場面ごとに描き下ろす。作り込む）", "desc": build.EXPRESSIONS["free"]}]},
        {"id": "player", "label": "プレイヤー（再生する画面の作り）", "default": "auto", "options": players, "preview": "inline", "thumb": 120,
         "help": "見本は、同じ動画を各プレイヤーで開いた画面。押すと大きく見られる"},
        {"id": "palette", "label": "配色", "default": "auto", "options": palettes, "help": "帯の色は、地・板・差し色 2 つ・文字"},
        {"id": "brand", "label": "ブランド名・ブランドの色（任意）", "type": "text", "remember": False, "placeholder": "例: Sodashitsu、#1f6feb",
         "help": "名前は右上に出す。色はいちばん近い配色を選ぶ（配色の上書きはしない）"},
        {"id": "bg", "label": "背景", "default": "auto", "options": [
            {"value": "auto", "label": "おまかせ（内容から選ぶ）", "desc": "静かな地を 1 つ決め、題・言い切り・締めなどの見せ場だけ替える", "recommended": True},
            {"value": "pick", "label": "全場面の地を選ぶ（動く背景 %d 種・SVG の背景 %d 枚から）" % (len(build.BACKDROPS), len(build.bg_svgs())), "desc": "見せ場の場面だけ替えるかは、内容から決める"},
            {"value": "theme", "label": "配色の地のまま（背景を足さない）", "desc": "配色の色と模様だけ。情報の多い動画・落ち着いた説明に"}]},
        {"id": "bg_name", "label": "全場面の地", "showIf": {"bg": "pick"}, "default": "soft", "options": backgrounds, "preview": "inline", "thumb": 96,
         "help": "「配色に合わせる」の見本は紺と真鍮の色。選んだ配色の色に置き換わる。全部を動かして見るページは python3 build.py --backgrounds -o backgrounds.html"},
        {"id": "motion", "label": "動きの性格", "default": "auto", "options": motions,
         "help": "切り替え・文字の出方・演出・カメラの既定がまとめて決まる"},
        {"id": "audio", "label": "音", "default": "full", "options": [
            {"value": "full", "label": "読み上げ＋音楽＋効果音", "recommended": True},
            {"value": "composed", "label": "読み上げ＋作曲した音楽と自作の効果音", "desc": "表現が自由のとき向け。曲・音色を作り込む"},
            {"value": "narration", "label": "読み上げだけ"},
            {"value": "music", "label": "音楽と効果音だけ（字幕で読む）"},
            {"value": "silent", "label": "無音"}]},
        {"id": "voice", "label": "読み上げの声", "showIf": {"audio": narr}, "default": "voicevox" if vv else "browser", "options": [
            {"value": "voicevox", "label": "VOICEVOX で前もって作る", "desc": "どの環境でも同じ声と時間。WebM にも声が入る。声 1 分で約 4MB。" + vv_note, "recommended": bool(vv)},
            {"value": "browser", "label": "見る人のブラウザの声", "desc": "HTML が小さい。声と速さは OS しだい（声の無い環境では字幕だけ）", "recommended": not vv},
            {"value": "files", "label": "用意した WAV を当てる", "desc": "録音したナレーション。字幕の数と順にそろえる"}]},
        {"id": "speaker", "label": "VOICEVOX の話者", "showIf": {"voice": "voicevox"}, "default": first, "options": speakers},
        {"id": "speed", "label": "話す速さ（VOICEVOX）", "showIf": {"voice": "voicevox"}, "default": "1.1", "options": [
            {"value": "1.0", "label": "ゆっくり（1.0）", "desc": "研修・子ども・お年寄り向け"},
            {"value": "1.1", "label": "ふつう（1.1）", "desc": "説明の動画の既定", "recommended": True},
            {"value": "1.2", "label": "速め（1.2）", "desc": "解説動画の定番の速さ。開発者向け・情報の多い動画"},
            {"value": "1.3", "label": "かなり速め（1.3）"}]},
        {"id": "music", "label": "音楽", "showIf": {"audio": ["full", "music"]}, "default": "auto", "options": [
            {"value": "auto", "label": "おまかせ（内容と雰囲気から選ぶ。長い動画は章で替える）", "recommended": True},
            {"value": "pick", "label": "曲を選ぶ（140 曲から）"},
            {"value": "file", "label": "音声ファイル（mp3・wav）を使う", "desc": "埋め込むので HTML が大きくなる。権利に注意"},
            {"value": "none", "label": "なし"}]},
        {"id": "track", "label": "曲", "showIf": {"music": "pick"}, "default": "calm", "options": tracks,
         "help": "聞き比べるページは python3 build.py --sounds -o sounds.html"},
        {"id": "music_file", "label": "音楽のファイル", "showIf": {"music": "file"}, "type": "text", "remember": False, "placeholder": "bgm/opening.mp3"},
        {"id": "kit", "label": "効果音の組", "showIf": {"audio": ["full", "music"]}, "default": "auto", "options": kits},
        {"id": "density", "label": "効果音の量", "showIf": {"audio": ["full", "composed", "music"]}, "default": "normal", "options": [
            {"value": "low", "label": "少なめ（章・通知・クリックだけ）", "desc": "読み上げのある 2 分以上の動画で、うるさく感じるとき"},
            {"value": "normal", "label": "ふつう（項目が出る・線がつながる等も）", "recommended": True},
            {"value": "high", "label": "多め（表の行まで）"}]},
        {"id": "outputs", "label": "作るもの", "type": "multi", "default": ["html"], "options": [
            {"value": "html", "label": "HTML（再生・書き出しつき）"},
            {"value": "dist", "label": "配布用の HTML（書き出しを省く --dist）"},
            {"value": "embed", "label": "埋め込み用の断片（--embed）"},
            {"value": "export", "label": "字幕・チャプター・YMM4/AviUtl 用の書き出し（video-export スキル）"}]},
        {"id": "checks", "label": "確かめ方", "type": "multi", "default": ["readings", "check", "shots"], "options": [
            {"value": "readings", "label": "声を作る前に読みを確かめる（build.py --readings）", "desc": "英字・「開け」など、読み違えやすい所を出す"},
            {"value": "check", "label": "台本と出来上がりを数えて確かめる（check.py）", "desc": "構成・項目と字幕の数・画面とナレーションの重なり・HTML の中の声・長さ"},
            {"value": "shots", "label": "全場面を撮って見る（check.py --shots）", "desc": "文字のはみ出し・重なり"},
            {"value": "review", "label": "別のエージェントに見てもらう（review.md）", "desc": "構成・わかりやすさ・画面。作った本人の思い込みを外す"}]},
    ]
    return {"title": "モーション動画の指示", "intro": "決めたことから台本（JSON）と HTML を作ります。既定のままでよい所は触らずに「この内容で作る」を押してください。",
            "submit": "この内容で作る", "remember": "motion-video-order", "note": "ほかに伝えたいこと（任意）", "questions": Q}


def skeleton(a):
    """回答 → 台本（JSON）の先頭の骨組みと、作るときの引数。おまかせ（auto）の項目は書かず、Claude が内容から決める。"""
    s = {"title": a.get("subject", ""), "lang": "ja", "expression": a.get("expression", "mixed")}
    p = a.get("player", "auto")
    s["player"] = USE_PLAYER.get(a.get("use"), "studio") if p == "auto" else p
    if a.get("palette", "auto") != "auto":
        s["theme"] = a["palette"]
    if a.get("motion", "auto") != "auto":
        s["motion"] = a["motion"]
    if a.get("bg") == "pick" and a.get("bg_name"):   # 全場面の地。おまかせ・配色の地のままは書かない（answers.bg を見て、台本を書くときに決める）
        s["bg"] = a["bg_name"]
    au, mode = {}, a.get("audio", "full")
    au["narration"] = mode in ("full", "composed", "narration")
    if mode in ("narration", "silent"):
        au["music"] = None
    elif a.get("music") == "pick" and a.get("track"):
        au["music"] = a["track"]
    elif a.get("music") == "file" and a.get("music_file"):
        au["music"] = {"file": a["music_file"]}
    elif a.get("music") == "none":
        au["music"] = None
    if mode == "silent" or mode == "narration":
        au["sfx"] = False
    else:
        sfx = {"density": a.get("density", "normal")}
        if a.get("kit", "auto") != "auto":
            sfx["kit"] = a["kit"]
        au["sfx"] = sfx
    if a.get("voice") == "voicevox":
        au["voice"] = {"engine": "voicevox", "speaker": a.get("speaker", "四国めたん"), "style": "ノーマル", "speed": float(a.get("speed", "1.1"))}
    s["audio"] = au
    if a.get("brand"):
        s["brand"] = {"name": a["brand"].split("、")[0].split(",")[0].strip()}
    args = []
    if a.get("voice") == "voicevox":
        args.append("--voicevox")
    if a.get("voice") == "files":
        args += ["--voices-dir", "voices/"]
    outs = a.get("outputs", ["html"])
    if "dist" in outs:
        args.append("--dist")
    return s, {"args": args, "embed": "embed" in outs or a.get("use") == "embed", "export": "export" in outs or a.get("use") == "youtube",
               "length": LENGTH.get(a.get("length", "standard"))}


def warnings(a):
    """答えどうしの食い違い（作る前に、使う人に伝える）。"""
    w = []
    if a.get("use") == "artifact":
        if a.get("voice") == "voicevox" and a.get("length") in ("long", "longer"):
            w.append("アーティファクトは 16MB まで。VOICEVOX の声は 1 分で約 4MB なので、3 分を超えると入らない。短くするか、ブラウザの声にする")
        if a.get("music") == "file":
            w.append("音楽のファイルを埋め込むと 3〜9MB 増える。アーティファクトの 16MB に収まるか確かめる")
    if a.get("use") == "youtube" and a.get("voice") == "browser":
        w.append("ブラウザの声は「WebM で保存」した動画に入らない。YouTube に上げるなら VOICEVOX か用意した WAV にする")
    if a.get("use") == "kiosk" and a.get("audio") in ("full", "composed", "narration"):
        w.append("キオスクは音なしで始まる。読み上げの内容は字幕で伝わるように書く")
    if a.get("audio") == "composed" and a.get("expression") != "free":
        w.append("作曲・自作の効果音は、表現が「自由」のとき向け（部品の表現でも使えるが、手間に見合うか）")
    if a.get("voice") == "voicevox" and not voicevox_speakers():
        w.append("VOICEVOX が動いていない。作る前に起動する（%s）" % VOICEVOX)
    e = build.bg_svgs().get(a.get("bg_name")) if a.get("bg") == "pick" else None
    if e and e.get("tone"):   # 景色の背景は色が決まっている
        pal, word = a.get("palette", "auto"), {"dark": "暗い", "light": "明るい"}[e["tone"]]
        if pal == "auto":
            w.append("背景「%s」は%s絵。配色は、%s地のものから選ぶ" % (e["label"], word, word))
        elif pal in build.THEMES and build.bg_warnings({"theme": pal, "bg": a["bg_name"]}):
            w.append("背景「%s」は%s絵で、配色「%s」と明るさが合わない（字が読みにくい）。配色を替えるか、bg を {\"src\": \"%s\", \"dim\": 0.5} にして抑える"
                     % (e["label"], word, build.THEMES[pal]["label"], a["bg_name"]))
    if a.get("use") == "embed" and a.get("player") not in ("auto", "minimal"):
        w.append("埋め込みには、操作部の小さいミニマルが向く")
    return w


def main():
    ap = argparse.ArgumentParser(description="モーション動画の指示を ask-form で聞く")
    ap.add_argument("--subject", default="")
    ap.add_argument("--out", default="order.json")
    ap.add_argument("--spec", action="store_true", help="質問の定義を出すだけ")
    ap.add_argument("--no-previews", action="store_true", help="プレイヤーと動く背景の見本の画面を撮らない")
    a = ap.parse_args()
    spec = build_spec(a.subject, not a.no_previews)
    if a.spec:
        print(json.dumps(spec, ensure_ascii=False, indent=1))
        return
    if not os.path.isfile(ASK):
        # ask-form が無い: ウィンドウを出せないときと同じ形（unavailable・終了コード 3）で返す。呼び出し側は、端末の質問（AskUserQuestion）に切り替える
        print(json.dumps({"status": "unavailable", "reason": "ask-form スキルが見つかりません（%s）" % ASK}, ensure_ascii=False))
        sys.exit(3)
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
    sk, bd = skeleton(ans)
    out = {"answers": ans, "note": res.get("note", ""), "custom": res.get("custom", []), "comments": res.get("comments", {}), "spec": sk, "build": bd, "warnings": warnings(ans)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))
    for w in out["warnings"]:
        print("warn: " + w, file=sys.stderr)
    print("OK : %s に書きました。spec を台本の先頭に使い、answers に従って章と場面を組む（おまかせの項目は内容から決める）" % a.out, file=sys.stderr)


if __name__ == "__main__":
    main()
