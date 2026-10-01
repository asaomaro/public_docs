#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""motion-video — 台本（JSON）から、動画のように再生できるモーショングラフィックスの単一 HTML を作る。

  python3 build.py --list                      # プレイヤー・配色・場面の部品と、台本の書き方
  python3 build.py spec.json --timeline        # 場面の長さ・字幕の時刻（HTML は作らない）
  python3 build.py spec.json -o out.html [--player studio] [--theme navy-brass]

描画は台本と時刻だけで決まる（同じ台本 → 同じ動画。シークしても同じ画）。
外部への依存は無い（書体は OS のもの。画像は data URI で埋め込む）。
"""
import sys, os, re, json, html, base64, argparse, mimetypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sound  # noqa: E402  曲・効果音の定義（同じ場所の sound.py）
import icons  # noqa: E402  線で描くアイコン集（同じ場所の icons.py。md-to-doc と共有）
import voice  # noqa: E402  声を前もって作る（VOICEVOX）・用意した WAV を当てる

# ──────────────────────────────────────────────────────────────────────────
# 映像の配色テーマ（canvas は映像の中、chrome はプレイヤーの操作部）
# ──────────────────────────────────────────────────────────────────────────
SANS = '"Hiragino Kaku Gothic ProN","Yu Gothic","Noto Sans JP",system-ui,sans-serif'
MARU = '"Hiragino Maru Gothic ProN","Zen Maru Gothic","Yu Gothic",system-ui,sans-serif'
MINCHO = '"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif'
MONO = '"SFMono-Regular",Menlo,Consolas,"Hiragino Kaku Gothic ProN",monospace'


def _dark(bg0, bg1, grid, ink, muted, faint, accent, accent2, warn, ok, panel, panel2, edge, accents, on_accent="#08141b"):
    return {"bg0": bg0, "bg1": bg1, "grid": grid, "ink": ink, "muted": muted, "faint": faint, "accent": accent,
            "accent2": accent2, "warn": warn, "ok": ok, "panel": panel, "panel2": panel2, "edge": edge,
            "shadow": "rgba(0,0,0,.45)", "code": "#04090c", "codeBar": "#0c171d", "codeInk": "#e4eff1",
            "codeMuted": "#8ea9b2", "onAccent": on_accent, "accents": accents}


THEMES = {
    "navy-brass": {
        "label": "紺と真鍮", "desc": "紺の地に真鍮とターコイズ。落ち着いた製品紹介", "pattern": "grid",
        "fonts": {"display": SANS, "sans": SANS, "mono": MONO},
        "canvas": _dark("#07131a", "#0d202b", "rgba(43,209,184,0.06)", "#e4eff1", "#8ea9b2", "#56707b",
                        "#c8923a", "#2bd1b8", "#f0a93b", "#7fe0a0", "#0f222d", "#1d5d6e", "#1f3b48",
                        ["#2bd1b8", "#c8923a", "#8fb8ff", "#e07a9b"]),
        "chrome": {"bg": "#08141b", "bg2": "#0e1f29", "line": "#1e3a47", "ink": "#e2eef0", "muted": "#8ea9b2", "accent": "#2bd1b8"},
    },
    "midnight": {
        "label": "真夜中", "desc": "黒に近い地にシアンと紫。技術・開発者向け", "pattern": "dots",
        "fonts": {"display": SANS, "sans": SANS, "mono": MONO},
        "canvas": _dark("#05070d", "#0b1020", "rgba(120,160,255,0.10)", "#e8ecf6", "#8b95ad", "#4c5670",
                        "#22d3ee", "#a78bfa", "#fbbf24", "#34d399", "#10172a", "#1c2340", "#232c47",
                        ["#22d3ee", "#a78bfa", "#34d399", "#f472b6"], "#04121a"),
        "chrome": {"bg": "#05070d", "bg2": "#0d1224", "line": "#232c47", "ink": "#e8ecf6", "muted": "#8b95ad", "accent": "#22d3ee"},
    },
    "daylight": {
        "label": "日中", "desc": "白い地に青。社内説明・研修・明るい紹介", "pattern": "dots",
        "fonts": {"display": SANS, "sans": SANS, "mono": MONO},
        "canvas": {"bg0": "#eef3f9", "bg1": "#ffffff", "grid": "rgba(26,86,219,0.10)", "ink": "#16202e", "muted": "#5b6778",
                   "faint": "#a9b3c1", "accent": "#1a56db", "accent2": "#0ea5e9", "warn": "#d97706", "ok": "#16a34a",
                   "panel": "#ffffff", "panel2": "#e8eefb", "edge": "#d3dbe8", "shadow": "rgba(16,24,40,.14)",
                   "code": "#0f172a", "codeBar": "#1e293b", "codeInk": "#e2e8f0", "codeMuted": "#94a3b8", "onAccent": "#ffffff",
                   "accents": ["#1a56db", "#0ea5e9", "#7c3aed", "#0d9488"]},
        "chrome": {"bg": "#ffffff", "bg2": "#f1f5fb", "line": "#d3dbe8", "ink": "#16202e", "muted": "#5b6778", "accent": "#1a56db"},
    },
    "paper": {
        "label": "紙", "desc": "生成りの地に焦げ茶と明朝の見出し。語り・解説・物語", "pattern": "none",
        "fonts": {"display": MINCHO, "sans": SANS, "mono": MONO},
        "canvas": {"bg0": "#efe7d8", "bg1": "#f8f3ea", "grid": "rgba(122,74,30,0.08)", "ink": "#3b2f24", "muted": "#7a6a58",
                   "faint": "#b9a98f", "accent": "#7a4a1e", "accent2": "#5f6f3a", "warn": "#a3471f", "ok": "#4f7a3a",
                   "panel": "#fbf8f1", "panel2": "#efe4d2", "edge": "#dccfb9", "shadow": "rgba(60,40,20,.14)",
                   "code": "#2f261d", "codeBar": "#3b2f24", "codeInk": "#f3eadb", "codeMuted": "#b9a98f", "onAccent": "#fbf8f1",
                   "accents": ["#7a4a1e", "#5f6f3a", "#8a3b3b", "#3f5f73"]},
        "chrome": {"bg": "#f8f3ea", "bg2": "#efe4d2", "line": "#dccfb9", "ink": "#3b2f24", "muted": "#7a6a58", "accent": "#7a4a1e"},
    },
    "mono": {
        "label": "モノクロ", "desc": "白黒に赤ひとつ。強い主張・発表・キーノート", "pattern": "none",
        "fonts": {"display": SANS, "sans": SANS, "mono": MONO},
        "canvas": _dark("#0a0a0a", "#141414", "rgba(255,255,255,0.05)", "#f5f5f5", "#9a9a9a", "#555555",
                        "#ff3b30", "#f5f5f5", "#ff9f0a", "#30d158", "#1b1b1b", "#262626", "#2e2e2e",
                        ["#ff3b30", "#f5f5f5", "#9a9a9a", "#ff9f0a"], "#0a0a0a"),
        "chrome": {"bg": "#0a0a0a", "bg2": "#141414", "line": "#2e2e2e", "ink": "#f5f5f5", "muted": "#9a9a9a", "accent": "#ff3b30"},
    },
    "vivid": {
        "label": "鮮やか", "desc": "深い紫の地に明るい差し色と丸ゴシック。広報・イベント・若い読み手", "pattern": "glow",
        "fonts": {"display": MARU, "sans": MARU, "mono": MONO},
        "canvas": _dark("#140a2e", "#231048", "rgba(255,120,220,0.18)", "#fbf7ff", "#c7b8e8", "#7f6aa8",
                        "#ffcc33", "#ff5fa2", "#ff9a3c", "#5ef0a8", "#2a1656", "#3a1f73", "#4a2c8a",
                        ["#ffcc33", "#ff5fa2", "#5ef0a8", "#6ecbff"], "#1a0b33"),
        "chrome": {"bg": "#140a2e", "bg2": "#231048", "line": "#4a2c8a", "ink": "#fbf7ff", "muted": "#c7b8e8", "accent": "#ffcc33"},
    },
}

# ──────────────────────────────────────────────────────────────────────────
# プレイヤーのテンプレート（どれも全操作を持つ。並べ方と見せ方が違う）
# ──────────────────────────────────────────────────────────────────────────
PLAYERS = {
    "cinema": ("シネマ", "操作部は映像の上に重なり、再生中は隠れる。紹介動画・ティザー"),
    "studio": ("スタジオ", "操作部は映像の下、チャプターの一覧を下に並べる。製品紹介・説明"),
    "presenter": ("プレゼンター", "横にチャプターの目次と説明。研修・講義・長めの解説"),
    "minimal": ("ミニマル", "細いシークバーと最小限のボタン。他は「⋯」にまとめる。埋め込み・短い動画"),
    "kiosk": ("キオスク", "自動再生・繰り返し・音なしで始まる。操作部は触れたときだけ。展示・受付"),
    "theater": ("シアター", "暗い地に大きな映像、横に文字起こし（クリックでその位置へ・検索）。講演・録画の公開"),
    "slides": ("スライド", "章の終わりで止まり、「次へ」で進む。発表の場で話しながら送る"),
}

# ──────────────────────────────────────────────────────────────────────────
# 場面の部品（type ごとの必須項目・最低の長さ・書き方）
# ──────────────────────────────────────────────────────────────────────────
SCENE_TYPES = {
    "title": (["title"], "表題（紋章・題名・副題・一文。紋章の中の 1 文字は markText、既定は題名の頭）", '{"type":"title","title":"Sodashitsu","subtitle":"操舵室","tagline":"**複数のエージェント**を一つの画面で","mark":"ring|wheel|none","markText":"S"}'),
    "statement": ([], "大きな一文（**強調** に下線が伸びる）", '{"type":"statement","lines":["作業の受け渡しを、","**自動**にする。"],"note":"小さな補足"}'),
    "bullets": (["items"], "箇条書きが順に現れ、今の項目を強調", '{"type":"bullets","heading":"できること","items":[{"text":"pane を分けて並べる","icon":"🧭"},"状態が一目で分かる"]}'),
    "flow": (["nodes"], "ノードと矢印の流れ。travel で線の上を印が移動", '{"type":"flow","heading":"受け渡し","nodes":[{"id":"a","label":"実装","sub":"impl","kind":"start"},{"id":"b","label":"レビュー"}],"edges":[{"from":"a","to":"b","travel":"{output}","label":"完了"}]}'),
    "steps": (["items"], "番号付きの手順（進み具合の線が伸びる）", '{"type":"steps","heading":"はじめかた","items":[{"label":"起動","sub":"soda serve"},{"label":"開く"}]}'),
    "terminal": (["lines"], "コマンドを 1 文字ずつ打ち、出力が続く", '{"type":"terminal","title":"bash","prompt":"$","lines":[{"cmd":"soda serve"},{"out":"listening on 127.0.0.1:7780"}]}'),
    "stats": (["items"], "数値のタイルが数え上がる（書式は元の文字を保つ）", '{"type":"stats","heading":"実績","items":[{"value":"98.5%","label":"稼働率"},{"value":"1,240件","label":"月間"}]}'),
    "bars": (["items"], "棒が伸び、値が数え上がる", '{"type":"bars","heading":"月ごとの件数","unit":"件","highlight":2,"items":[{"label":"4月","value":320},{"label":"5月","value":480}]}'),
    "compare": (["left", "right"], "左右の対比（tone: good / bad で印と色）", '{"type":"compare","heading":"手作業との違い","left":{"title":"手作業","tone":"bad","points":["夜は止まる"]},"right":{"title":"連携","tone":"good","points":["サーバで常時"]}}'),
    "code": (["code"], "コードを見せ、行の範囲を順に強調して注記", '{"type":"code","heading":"設定","code":"const a = 1;\\nexport default a;","highlight":[{"lines":[1],"note":"値を決める"},{"lines":[2,2]}]}'),
    "window": (["panes"], "アプリの画面の模型（pane の状態・通知が変わる）", '{"type":"window","title":"Sodashitsu — api","sidebar":[{"label":"impl","state":"working","active":true}],"panes":[{"title":"impl","tag":"claude","state":"working","states":[{"at":0.4,"state":"done"}],"lines":["› 実装して","  ✓ 24 passed"]}],"toasts":[{"at":0.45,"title":"impl が完了しました","sub":"api · p1","kind":"done"}]}'),
    "image": (["src"], "画像（ゆっくり寄る。src は台本からの相対パス・URL・data URI）", '{"type":"image","src":"shot.png","caption":"画面の例","kenburns":true}'),
    "end": ([], "締め（紋章・コマンドや連絡先の行・題名・一文。紋章の文字は markText）", '{"type":"end","title":"Sodashitsu","lines":[{"text":"$ soda serve","note":"ブラウザで開く"}],"tagline":"舵を一つの場所で"}'),
    "cards": (["items"], "カードの格子が弾んで現れる（2〜6 枚）", '{"type":"cards","heading":"主な機能","items":[{"title":"MCP","text":"AI から操作","icon":"🤖"},{"title":"Web","text":"ブラウザで"}]}'),
    "timeline": (["items"], "年表・マイルストーン（線が伸び、点と文字が上下交互に）", '{"type":"timeline","heading":"歩み","items":[{"date":"2024","label":"公開"},{"date":"2026","label":"v1.0","highlight":true}]}'),
    "chat": (["messages"], "会話の吹き出し（入力中の点のあとに現れる）", '{"type":"chat","messages":[{"from":"user","text":"受注を照会して"},{"from":"AI","text":"**128 件**あります"}]}'),
    "line": (["labels", "series"], "折れ線（線が伸び、最後の値が数え上がる）", '{"type":"line","heading":"推移","unit":"件","labels":["4月","5月","6月"],"series":[{"name":"件数","values":[120,340,610]}]}'),
    "donut": (["items"], "ドーナツ（時計回りに埋まり、割合の凡例）", '{"type":"donut","heading":"内訳","unit":"件","items":[{"label":"完了","value":820},{"label":"見送り","value":300}]}'),
    "table": (["columns", "rows"], "表（行が順に現れ、highlight の行を順に強調。数値の列は右寄せ）", '{"type":"table","heading":"比較","columns":["項目","A","B"],"rows":[["速度","12ms","40ms"],["費用","0円","3万円"]],"highlight":[0,1]}'),
    "quote": (["text"], "引用・声（大きな引用符、発言者）", '{"type":"quote","text":"画面を**覚えさせる**だけで済んだ","by":"山田さん","role":"情報システム部"}'),
    "kinetic": (["text"], "キネティック文字（語が 1 つずつ弾んで組み上がる。**強調** は色と下線）", '{"type":"kinetic","text":"AI も 人も **同じ画面** を 見る"}'),
    "split": (["left", "right"], "左に文章・右に部品（右は type 付きの部品を縮小して置く）", '{"type":"split","heading":"…","left":{"title":"見出し","text":"説明","points":["要点"]},"right":{"type":"stats","items":[{"value":"48","label":"ツール"}]}}'),
    "beforeafter": (["before", "after"], "前後比較（境目が左から右へ動き、後の姿が現れる）", '{"type":"beforeafter","heading":"導入の前と後","before":{"label":"Before","title":"手作業","points":["毎朝 30 分"],"value":"30 分"},"after":{"label":"After","title":"自動","points":["ボタン 1 つ"],"value":"1 分"}}'),
    "dom": ([], "HTML・SVG・CSS で自由に描く（html / css / update。src・cssSrc・updateSrc でファイルから）。時刻は CSS 変数 --lt（ms）と --p（0..1）", '{"type":"dom","src":"scenes/intro.html","cssSrc":"scenes/intro.css","updateSrc":"scenes/intro.js","duration":8}'),
    "area": (["labels", "series"], "面グラフ（左から塗られる。stacked で積み上げ）", '{"type":"area","heading":"利用者の推移","labels":["1月","2月","3月","4月"],"series":[{"name":"新規","values":[120,180,260,340]}],"unit":"人"}'),
    "stack": (["labels", "series"], "積み上げ棒（段ごとに伸び、合計が数え上がる）", '{"type":"stack","labels":["Q1","Q2","Q3"],"series":[{"name":"国内","values":[30,40,55]},{"name":"海外","values":[10,18,30]}],"unit":"億"}'),
    "scatter": (["points"], "散布図（点が弾み、highlight で 1 点を強調、trend で傾向の線）", '{"type":"scatter","xLabel":"工数","yLabel":"効果","points":[{"x":2,"y":8,"label":"A"},{"x":6,"y":5,"label":"B"}],"highlight":0,"trend":true}'),
    "heatmap": (["rows", "cols", "values"], "ヒートマップ（斜めの波で塗られ、最大のマスを強調）", '{"type":"heatmap","rows":["月","火","水"],"cols":["9時","12時","18時"],"values":[[3,8,5],[2,9,6],[4,7,9]]}'),
    "gauge": (["value"], "メーター（針が振れて止まる。zones で色の帯）", '{"type":"gauge","value":82,"max":100,"unit":"点","label":"満足度","zones":[{"from":0,"to":60,"tone":"bad"},{"from":80,"to":100,"tone":"good"}]}'),
    "rings": (["items"], "進捗の輪（並べて塗られ、数え上がる）", '{"type":"rings","items":[{"label":"設計","value":100},{"label":"実装","value":70},{"label":"試験","value":35}]}'),
    "treemap": (["items"], "ツリーマップ（大きい順に面が現れる）", '{"type":"treemap","items":[{"label":"国内","value":52},{"label":"北米","value":28},{"label":"欧州","value":14}],"unit":"%"}'),
    "radar": (["axes", "series"], "レーダー（網が張られ、多角形が中心から広がる）", '{"type":"radar","axes":["速さ","安さ","安全","使いやすさ","拡張"],"series":[{"name":"新","values":[9,7,8,9,8]},{"name":"旧","values":[5,6,7,4,5]}],"max":10}'),
    "phone": ([], "スマホの画面（項目が現れ、screens で画面が横に送られる。notify・tap・points）", '{"type":"phone","screens":[{"title":"今日","items":[{"title":"会議","sub":"10:00","icon":"calendar"},{"title":"レビュー","badge":"3"}]}],"notify":{"at":0.6,"title":"承認待ち","text":"impl が待っています"},"points":["通知で気づける","その場で承認"]}'),
    "dashboard": ([], "ダッシュボードが組み上がる（kpis・bars・rows）", '{"type":"dashboard","title":"運用","kpis":[{"label":"処理件数","value":"1,240","delta":"+12%"},{"label":"平均時間","value":"3 分"}],"bars":[3,5,4,7,8,11],"rows":["impl 完了",{"text":"review 待ち","state":"blocked"}]}'),
    "form": (["fields"], "フォームに順に入力して送信する（カーソル・打鍵・選択・チェック・完了）", '{"type":"form","title":"申し込み","fields":[{"label":"名前","value":"山田 太郎"},{"label":"プラン","type":"select","value":"Pro","options":["Free","Pro"]},{"label":"規約","type":"check","value":"同意する"}],"submit":"送信","done":"受け付けました"}'),
    "notifs": (["items"], "通知が上から積み重なる（text で左に一言）", '{"type":"notifs","text":"AI からの連絡を 1 か所に","items":[{"app":"Claude","title":"impl が完了","icon":"check"},{"app":"Codex","title":"承認待ち","icon":"bell"}]}'),
    "scroll": (["sections"], "ページが節ごとにスクロールする（focus の節を強調）", '{"type":"scroll","url":"docs.example.com","sections":[{"heading":"はじめに","text":"…"},{"heading":"設定","text":"…","image":"画面"}],"focus":1}'),
    "drag": (["columns"], "カンバンのカードをドラッグで移す（moves: [{card, to}]）", '{"type":"drag","columns":[{"title":"未着手","cards":["設計"]},{"title":"作業中","cards":[]},{"title":"完了","cards":[]}],"moves":[{"card":"設計","to":"作業中"}]}'),
    "network": (["nodes", "edges"], "網の目のつながり（自動で配置し、線の上を印が流れる）", '{"type":"network","nodes":[{"id":"a","label":"操舵室"},{"id":"b","label":"Claude"},{"id":"c","label":"Codex"}],"edges":[["a","b"],["a","c"]]}'),
    "tree": (["root"], "木（上の段から枝が伸びる）", '{"type":"tree","root":{"label":"製品","children":[{"label":"Web","children":["画面","API"]},{"label":"CLI"}]}}'),
    "states": (["states"], "状態の遷移（丸と矢印。path の順に印が移り、今の状態が光る）", '{"type":"states","states":[{"id":"idle","label":"待機"},{"id":"work","label":"作業"},{"id":"done","label":"完了"}],"transitions":[{"from":"idle","to":"work","label":"依頼"},{"from":"work","to":"done"}],"path":["idle","work","done"]}'),
    "map": (["pins"], "地図とピン（街の地図にピンが落ち、routes で経路）。x・y は 0..1", '{"type":"map","pins":[{"x":0.2,"y":0.6,"label":"東京"},{"x":0.75,"y":0.35,"label":"大阪"}],"routes":[[0,1]]}'),
    "layers": (["items"], "層の構成（下から積み上がり、途中で分かれて見せる）", '{"type":"layers","items":[{"label":"インフラ","sub":"クラウド"},{"label":"サーバ"},{"label":"画面"}]}'),
    "pipeline": (["stages"], "流れ作業（段を印が流れ続け、段ごとの数が増える）", '{"type":"pipeline","stages":[{"label":"受付","icon":"mail"},"設計","実装",{"label":"完了","icon":"check"}],"label":"依頼が次々に流れる"}'),
    "layout": (["slots"], "場面の割り付けの型（template: trio 3 つ並び・inset 大見出し＋小窓・collage 傾いた写真・fullbleed 全面の写真＋文字・focus 1 つを大きく・split2 左右の比較）。slots は部品の台本の配列（caption で下に一言）",
               '{"type":"layout","template":"trio","title":"3 つの画面","slots":[{"type":"gauge","value":82,"caption":"満足度"},{"type":"rings","items":[{"label":"達成","value":70}],"caption":"進み"},{"type":"stack","labels":["A","B"],"series":[{"name":"x","values":[3,5]}],"caption":"内訳"}]}'),
    "wordcloud": (["words"], "語の雲（重い語ほど大きく中央に。順に弾んで現れ、ゆっくり漂う）", '{"type":"wordcloud","words":[{"text":"並行","weight":5},{"text":"承認","weight":4},"通知","SSH","Windows"]}'),
    "bigtype": (["big"], "画面いっぱいの文字が背景で流れ、前に言葉が出る（text・sub）", '{"type":"bigtype","big":"PARALLEL","text":"並べて、任せる。","sub":"Sodashitsu"}'),
    "talk": ([], "掛け合い（ゆっくり解説など）。lines: [{who, text, face, emote, voice, shake, pause}] と、中央の黒板 board（部品の台本・{type:image,src}・文字列）、背景 bg。登場人物は台本の cast",
             '{"type":"talk","board":{"type":"bullets","heading":"3 つの特徴","items":["速い","安い","うまい"]},"lines":[{"who":"a","text":"今日は〇〇を解説するよ。"},{"who":"b","text":"よろしくなのだ！","face":"smile","emote":"!"}]}'),
    "funnel": (["items"], "漏斗（段が上から落ちて重なり、段の間に歩留まりの %）", '{"type":"funnel","heading":"申し込みまで","items":[{"label":"訪問","value":12000},{"label":"試用","value":3200},{"label":"申し込み","value":860}],"unit":"人"}'),
    "pyramid": (["items"], "ピラミッド（下の段から積み上がる。items は上から順。text で右に説明）", '{"type":"pyramid","heading":"支える仕組み","items":[{"label":"体験","text":"画面"},{"label":"機能","text":"API"},{"label":"基盤","text":"サーバ"}]}'),
    "venn": (["sets"], "ベン図（2〜3 の円が外から寄って重なり、center の言葉が弾む）", '{"type":"venn","sets":[{"label":"速さ","text":"すぐ返る"},{"label":"安さ"},{"label":"安全"}],"center":"ここ"}'),
    "cycle": (["items"], "循環（項目が輪に並び、矢印が順につながり、印が回り続ける。center で中心の言葉）", '{"type":"cycle","center":"改善","items":[{"label":"計画","icon":"pencil"},{"label":"実行","icon":"rocket"},{"label":"評価","icon":"chart-line"},{"label":"改善","icon":"refresh"}]}'),
    "matrix": (["items"], "四象限（軸が伸び、象限の名前、点が置かれる。x・y は 0..1、quadrants は 左上・右上・左下・右下、highlight で象限を光らせる）", '{"type":"matrix","xLabel":"効果","yLabel":"手軽さ","quadrants":["すぐやる","計画","保留","見送り"],"highlight":1,"items":[{"label":"自動化","x":0.8,"y":0.7},{"label":"刷新","x":0.85,"y":0.2}]}'),
    "calendar": ([], "ひと月の暦（マスが斜めの波で並び、events の日に印。start は 1 日の曜日 0=日、side で右に一覧）", '{"type":"calendar","month":"2026年10月","days":31,"start":4,"events":[{"day":1,"label":"公開"},{"day":15,"label":"説明会"}],"highlight":1,"side":true}'),
    "checklist": (["items"], "チェックリスト（印が描かれ、進み具合が伸びる。done:false は未完了、note で右に一言）", '{"type":"checklist","heading":"公開の前に","items":["テスト",{"text":"文書","note":"済"},{"text":"告知","done":false,"note":"来週"}]}'),
    "versus": (["left", "right"], "対決（左右が斜めの境目で滑り込み、VS が叩きつけられる。winner: left|right で勝者が光る）", '{"type":"versus","left":{"label":"手作業","value":"30 分","points":["毎朝の確認"]},"right":{"label":"自動","value":"1 分","icon":"bolt"},"winner":"right"}'),
    "ranking": (["items"], "順位（下の順位から棒が伸び、1 位が最後に光る。sort:false で並べ替えない）", '{"type":"ranking","heading":"よく使う機能","unit":"回","items":[{"label":"承認","value":1240},{"label":"通知","value":860},{"label":"検索","value":520}]}'),
    "keys": ([], "キー操作（キーの頭が落ちてきて押し込まれる。keys と label、または combos: [{keys, label}]）", '{"type":"keys","combos":[{"keys":["Ctrl","K"],"label":"コマンドを開く"},{"keys":["Ctrl","Shift","P"],"label":"すべての操作"}]}'),
    "icons": (["items"], "アイコンの格子（線で描かれ、現れた後も動く）。items: {icon, label, text}", '{"type":"icons","heading":"できること","items":[{"icon":"rocket","label":"速い","text":"3 分で"},{"icon":"shield","label":"安全"},{"icon":"users","label":"みんなで"}]}'),
    "impact": (["text"], "強い一語を叩きつける（集中線・破片・画面の揺れ）。sub で下に一行", '{"type":"impact","text":"10 倍速い","sub":"同じ作業が 3 分で"}'),
    "countdown": ([], "3・2・1 の数え下ろしと、最後に label を叩きつける（from で始まりの数）", '{"type":"countdown","from":3,"label":"公開！","sub":"10 月 1 日"}'),
    "orbit": (["items"], "中心の周りを項目が回る（関係・生態系）。center は中心の名前", '{"type":"orbit","heading":"つながる道具","center":{"label":"Sodashitsu","sub":"操舵室"},"items":[{"label":"Claude","icon":"🤖"},"Codex","Gemini","herdr"]}'),
    "logo": (["title"], "破片が集まってロゴになり、題名に光が走る（公開・発表の頭と締め。紋章の文字は markText）", '{"type":"logo","title":"Sodashitsu","subtitle":"AI エージェントの操舵室","mark":"wheel"}'),
    "marquee": (["rows"], "大きな文字の帯が左右に流れる（キーワードの洪水）。caption で中央に札", '{"type":"marquee","rows":[["並行","承認","通知"],["SSH","Windows","TLS"]],"caption":"ぜんぶ、1 つの画面で"}'),
    "custom": ([], "JS で自由に描く（本体: (ctx, lt, d, H, s)。道具は --api。code は文字列か行の配列、または src に .js のパス）", '{"type":"custom","src":"scenes/intro.js","duration":8,"narration":"…"}'),
}
# 立体・奥行きと文字の演出（parts-depth.js）
SCENE_TYPES.update({
    "cube": (["faces"], "箱が回って面ごとに見せる（2〜4 面。faces: {title, text, icon} か文字列）", '{"type":"cube","heading":"3 つの顔","faces":[{"title":"速い","text":"3 分で始められる","icon":"rocket"},{"title":"安全","icon":"shield"},{"title":"みんなで","icon":"users"}]}'),
    "carousel": (["items"], "カードの輪が奥行きの中で回り、今の 1 枚が手前に来る（caption で下に一言）", '{"type":"carousel","heading":"使える道具","items":[{"title":"Claude","icon":"bolt"},{"title":"Codex","icon":"code"},{"title":"Gemini","icon":"star"},{"title":"herdr","icon":"terminal"}]}'),
    "explode": (["layers"], "層の構成を斜め上から見た板で積み、間が開いて分かれる（下から。text で横に注記）", '{"type":"explode","heading":"仕組みの層","layers":[{"title":"インフラ","text":"クラウド"},{"title":"サーバ","icon":"server"},{"title":"画面","text":"ブラウザ・端末"}]}'),
    "tunnel": (["items"], "奥に並んだ枠の中を進み、1 つずつ通り抜ける（手順・章立て）", '{"type":"tunnel","items":[{"title":"計画","icon":"pencil"},{"title":"実装","text":"並べて進める"},{"title":"公開","icon":"rocket"}]}'),
    "parallax": ([], "奥行きのある風景（scene: hills|city|space）を横に移り、手前ほど速く動く。中央に title・text", '{"type":"parallax","scene":"city","title":"どこからでも","text":"別のマシンの作業も 1 画面で"}'),
    "swarm": (["words"], "粒が集まって言葉になり、次の言葉へ形を変える（2〜4 語。短い語ほどきれい）", '{"type":"swarm","words":["並べる","知らせる","任せる"],"text":"3 つの動き"}'),
    "morph": (["items"], "形（circle square triangle diamond hexagon star arrow plus heart）が次の形へ変わり、横の名前が入れ替わる", '{"type":"morph","heading":"育つ流れ","items":[{"shape":"circle","label":"種","text":"思いつき"},{"shape":"triangle","label":"芽"},{"shape":"star","label":"花"}]}'),
    "barrage": (["phrases"], "短い言葉を大きく連打する（言葉ごとに組み方が変わる: stack punch slide spread。**強調** は差し色）", '{"type":"barrage","phrases":["待たない。","**並べる**。","気づく、すぐに。","任せて、**進む**。"]}'),
    "rotator": (["words"], "前後の言葉は止まったまま、間の語だけが入れ替わる（before・after・text）", '{"type":"rotator","before":"AI と","words":["速く","安全に","楽しく"],"after":"作る","text":"Sodashitsu で"}'),
    "textpath": (["text"], "文字が線（path: circle wave arc spiral）に沿って並び、流れる。中央に center・icon・sub", '{"type":"textpath","path":"circle","text":"SODASHITSU · AGENT COCKPIT","center":"操舵室","sub":"AI の作業を 1 画面で"}'),
    "emphasis": (["text"], "文章は静かに置き、**強調** の語だけが順に光って動く（強調の数とナレーションの文の数をそろえると、話す順に光る）", '{"type":"emphasis","text":"作業を**並べて見る**。待ちは**通知で知る**。あとは**任せる**だけ。"}'),
})
COMMON = ("共通: narration（ナレーション＝字幕。文字列か配列）・duration（秒。省略時は自動）・heading・transition（切り替え。下の一覧）"
          "・overlays（重ねの層）・camera（カメラ。型の名前か keyframe）・anim（文字の出方。title・statement・quote・end・kinetic・impact・logo）"
          "・fx（演出の層の配列。false で性格の既定も止める）・shake（[{at, amp, dur}] 画面の揺れ）・sfx（効果音）")

OVERLAY_KINDS = {
    "note": (["text"], '注記の吹き出し。target で引き出し線', '{"kind":"note","text":"ここが**新しい**","x":1300,"y":200,"target":[900,420],"at":0.3,"until":0.9}'),
    "arrow": (["from", "to"], "描かれる矢印（curve で曲げる）", '{"kind":"arrow","from":[400,700],"to":[900,450],"curve":0.2,"label":"完了","at":0.4}'),
    "highlight": (["rect"], "枠で強調。spotlight で周りを暗く", '{"kind":"highlight","rect":[700,300,500,200],"spotlight":true,"label":"ここ","at":0.5,"until":0.8}'),
    "badge": (["text"], "弾んで出る札", '{"kind":"badge","text":"NEW","x":1500,"y":260,"at":0.2}'),
    "cursor": (["path"], "マウスの矢印が点を順にたどる。click はクリックする点の番号", '{"kind":"cursor","path":[[500,800],[900,420],[1200,420]],"click":[1],"at":0.2,"until":0.8}'),
    "notify": (["text"], "OS 風の通知（右上。pos:br で右下寄り）", '{"kind":"notify","app":"Sodashitsu","text":"impl が完了しました","at":0.3,"until":0.7}'),
    "icon": (["name"], "アイコンを線で描き、動かす（x, y, size, color, anim）", '{"kind":"icon","name":"bell","x":1500,"y":300,"size":120,"at":0.3}'),
    "burst": ([], "破片が弾ける（x, y。n で数・r で広がり）", '{"kind":"burst","x":1300,"y":420,"at":0.4}'),
    "ripple": ([], "波紋がくり返し広がる（x, y, r）", '{"kind":"ripple","x":900,"y":500,"r":180,"at":0.3,"until":0.8}'),
    "confetti": ([], "紙吹雪が降る（祝い・達成）", '{"kind":"confetti","at":0.5}'),
    "stamp": (["text"], "判子が叩きつけられる（x, y, rot 度, color: warn|accent|ok）。画面が揺れる", '{"kind":"stamp","text":"承認","x":1450,"y":320,"at":0.6,"color":"ok"}'),
    "circle": (["rect"], "手書きの丸で囲む（label で添え書き）", '{"kind":"circle","rect":[700,380,420,120],"label":"ここ","at":0.4}'),
    "marker": (["rect"], "蛍光ペンで塗る（文字の上に重なる半透明）", '{"kind":"marker","rect":[620,470,560,60],"at":0.5}'),
}
TRANSITIONS = {
    "fade": "重ねて入れ替える（既定）", "slide": "少し横にずれながら", "zoom": "少し寄りながら", "cut": "すぐ切り替える",
    "wipe": "境目が左から右へ", "push": "前の場面を横に押し出す", "slide-up": "上に押し出す", "slide-down": "下に押し出す",
    "iris": "中央から円が広がる", "blinds": "横の帯が開く", "split": "前の場面が上下に割れる", "whip": "高速で横に流れる（ぶれと線）",
    "spin": "回って縮み、回って現れる", "flash": "白く光って切り替わる", "glitch": "映像が乱れて切り替わる", "pixel": "モザイクになって切り替わる",
    "squeeze": "箱が回るように", "zoom-through": "前の場面に突っ込んで抜ける",
    "diagonal": "斜めの境目が流れる", "diamond": "菱形が広がる", "spot": "一点（origin）から円が広がる", "cube": "縦に箱が回る",
    "page": "ページをめくる", "liquid": "波打つ境目が流れる", "dive": "前の場面の一点（focus）へ飛び込む", "tiles": "タイルが斜めの順に開く",
    "stripes": "縦の縞が上下から開く", "clock": "時計回りに開く",
    "doors": "前の場面が左右の扉のように開く", "shatter": "前の場面がガラスのように割れて落ちる", "fan": "扇が 6 枚開く", "spin-zoom": "回りながら突っ込み、回りながら定まる",
    "bars": "色の帯が横に走って覆い、抜ける", "cover": "色の幕が上から下りて上がる（ブランド名が出る）", "ink": "墨が滲むように広がる", "flip": "カードのように裏返る",
    "rings": "同心円の輪が開く", "stack": "次の場面が横から重なり、前の場面が沈む", "shrink": "前の場面が縮んで左上へ飛ぶ", "flood": "波打つ水面が下から満ちる",
    "focus": "ぼけて入れ替わる", "dissolve": "細かい四角がばらばらに入れ替わる", "columns": "縦の帯が開く",
}
TRANSITIONS.update({"depth": "前の場面が奥へ沈み、次が手前から定まる（立体）", "swing": "前の場面が左端を軸に扉のように奥へ開く（立体）"})
TEXT_ANIMS = {
    "rise": "下から浮かぶ（既定）", "reveal": "左から現れ、カーソルが走る（題名の既定）", "pop": "弾んで出る", "slam": "大きく叩きつけ、画面が揺れる",
    "stretch": "横に伸びた形から縮む（映画の題名）", "blur": "ぼけから合う", "glitch": "色ずれしながら定まる", "neon": "ネオンが点く",
    "type": "1 文字ずつ打つ", "scramble": "でたらめな文字から定まる", "wave": "1 文字ずつ波打って出る", "letters": "1 文字ずつ落ちてくる", "split": "散らばった文字が集まる",
    "mask": "下から覗くように現れる", "marker": "蛍光ペンが走ってから文字", "drop": "上から落ちて弾む", "zoom": "大きな所から縮んで定まる",
    "outline": "輪郭だけの文字から塗られる", "roll": "1 文字ずつ下から回り込む", "spin": "1 文字ずつ回って現れる", "shadow": "長い影が伸びる",
    "flip": "1 文字ずつ上下に裏返る", "rotate": "左端を軸に起き上がる", "bounce": "1 文字ずつ落ちて跳ねる", "box": "色の箱が走り、抜けた後に文字",
    "flicker": "1 文字ずつ瞬いて点く（古い看板）", "words": "語ごとに下から覗く", "halves": "上半分と下半分が左右から合わさる", "swing": "1 文字ずつ上を軸に振れて止まる",
    "elastic": "ゴムのように伸び縮みして定まる", "tracking": "広い字間から詰まる（上品）", "skew": "斜めに傾いて滑り込む（ニュース）",
}
TEXT_ANIMS.update({"depth": "1 文字ずつ奥から迫って定まる（立体）", "unfold": "下を軸に、寝た状態から起き上がる（立体）", "swirl": "渦を巻いて集まる"})
EASES = {"smooth": "なめらか（既定）", "spring": "ばねのように行き過ぎて戻る", "snappy": "素早く決まる", "bouncy": "跳ねて止まる",
         "elastic": "ゴムのように震えて止まる", "calm": "ゆっくり出てゆっくり止まる"}
ORDERS = {"normal": "前から（既定）", "reverse": "後ろから", "center": "中央から外へ", "edges": "両端から中央へ", "random": "ばらばら（毎回同じ順）",
          "alternate": "1 つおき（奇数の後に偶数）", "zigzag": "前と後ろを交互に"}
FX = {
    "particles": "漂う粒", "stars": "瞬く星", "bokeh": "ぼけた光の玉", "rays": "差し込む光の筋", "speedlines": "中心へ向かう集中線", "grid": "奥へ流れる格子の床",
    "waves": "下で揺れる波線", "gradient": "動くグラデーション", "aurora": "流れるオーロラ", "plexus": "点と線の網", "contour": "等高線",
    "shapes": "漂う図形", "blobs": "ゆらぐ柔らかな塊", "scanlines": "走査線（上）", "confetti": "紙吹雪（上）", "vignette": "周りを暗く（上）", "sweep": "斜めの光が通る（上）", "noise": "フィルムの粒（上）",
    "embers": "舞い上がる火の粉", "halftone": "網点の模様（x, y が濃い所）", "warp": "奥から迫る星（ワープ）", "pulse": "レーダーの輪と走査",
    "bubbles": "昇る泡", "matrix": "流れ落ちる文字", "rain": "雨（上）", "snow": "雪（上）", "film": "古いフィルムの傷とちらつき（上）",
    "leaks": "光漏れ（上）", "spotlight": "動くスポットライト（上）", "sparkles": "きらめき（上）",
}
FX.update({"cubes": "奥行きの中を回りながら漂う針金の箱"})
CAMERA_PRESETS = {
    "push-in": "ゆっくり寄る", "pull-out": "寄った所から引く", "pan-left": "左へ流す", "pan-right": "右へ流す", "rise": "上へ上がる",
    "punch": "言い切りで素早く寄る", "tilt": "傾きを戻しながら", "drift": "ゆらゆら漂う", "dolly": "大きく寄った所から回りながら引く",
    "crash-zoom": "寄った所から一瞬で引く", "orbit": "回り込むように横へ", "pan-reveal": "左上に寄った所から全体へ", "rack-focus": "ぼけからピントが合う",
    "breathe": "呼吸するように寄り引き", "sink": "下へ沈む", "handheld": "手持ちの揺れ",
}
MOTION_STYLES = {
    "gentle": "穏やか（既定）。fade・浮かぶ文字・題名はカーソルで現れる",
    "dynamic": "ダイナミック。whip・push・突っ込む切り替え、文字は弾む・題名は叩きつける、集中線、言い切りで寄る",
    "playful": "楽しい。回る・箱・円の切り替え、文字は波打つ・題名は落ちてくる、紙吹雪",
    "cinematic": "映画的。fade と突っ込む切り替え・章は白く光る、文字はぼけから・題名は伸びから、光の玉・光の筋・周りを暗く、ゆっくり漂うカメラ",
    "tech": "技術。乱れ・モザイク・帯の切り替え、文字はでたらめから定まる、走査線・格子の床",
    "retro": "レトロ。モザイク・ばらばら・縞の切り替え、文字は瞬いて点く・題名は落ちて跳ねる、古いフィルム・網点、手持ちのカメラ",
    "elegant": "上品。ぼけ・色の幕の切り替え、字間が詰まる文字、光漏れ・きらめき、呼吸するカメラ・ピントが合う題名",
    "news": "報道。色の帯・押し出し・重なる切り替え、箱が走る文字・斜めの題名、レーダーの輪、言い切りで一瞬で引く",
}
CAMERA_DOC = ('camera: [{"at":0,"x":960,"y":540,"zoom":1,"rot":0},{"at":0.6,"x":1300,"y":480,"zoom":1.6}] — 場面の進み（0..1）で補間し、'
              '(x,y) を中央に zoom 倍・rot 度で映す。部品にも custom にも効く。重ねの層もいっしょに動く。'
              '型の名前でもよい: ' + " ".join(CAMERA_PRESETS))
EXPRESSIONS = {
    "components": "部品だけで組む。速く安く、毎回ぶれにくい（custom は使わない）",
    "mixed": "基本は部品で、見せ場だけ custom（既定）",
    "free": "場面ごとに custom（Canvas）か dom（HTML・SVG・CSS）で描く。部品は H.sub で道具として使う。プレイヤー・時間割・字幕・音声だけを使う",
}

API_DOC = """custom の本体は (ctx, lt, d, H, s)。座標は 1920×1080、lt は場面の中の経過 ms、d は場面の長さ ms、s は台本の場面。
描き方は時刻だけで決める（Math.random・Date.now・前のコマの状態は使わない。乱数は H.rand(種)）。

配色と書体
  H.C.bg0 bg1 ink muted faint accent accent2 warn ok panel panel2 edge code codeInk codeMuted onAccent accents[]
  H.F.display sans mono      H.accentAt(i) 循環色
時間
  H.P(lt, a, b[, 緩急]) a..b ms の進み 0..1（既定 eo）。緩急は H.eo H.eio H.back H.linear（等速）
  H.lin(lt, a, b) a..b ms の等速の進み 0..1（H.P(lt, a, b, H.linear) と同じ。緩急としては渡さない）   H.clamp H.mix
  H.slots(n, d, 先頭ms, 末尾ms) n 個の区切りの時刻の配列（項目と字幕の文の数が同じなら、i 番目の文が始まる時。違えば場面の長さに均等）
  H.cue(i) / H.cueEnd(i) この場面の i 番目（0 から）の字幕の文が始まる・終わる時（場面の中の ms。声の長さ・速さの直しの後）  H.cues() 始まりの配列
文字
  H.txt(s, x, y, {size, weight, color, align, font, alpha, spacing})   H.tw(s, 同)=幅
  H.rich(行, x, y, {…}, 下線の進み) **強調** を色と下線で   H.wrap(s, 最大幅, {size, weight}) 折り返した行の配列
  H.typed(s, k) 入力中の文字（先頭から k の割合）   H.count("1,240件", k) 数え上げ中の表記
図形
  H.rr(x,y,w,h,r) 角丸の経路   H.panel(x,y,w,h,{fill,stroke,lw,r,shadow})   H.icon(名前,x,y,size,{color,anim,k,lt})  線のアイコン（--list-icons。k は線が描かれる進み 0..1、lt は現れた後の動きの時刻 ms）
  H.iconAny(絵文字か名前,x,y,size)  絵文字も描ける（名前ならアイコン）
  H.node(x,y,w,h,label,sub,{hot,state,t,fill,stroke,ink})   H.stateMark(x,y,"working|done|blocked|idle",lt)
  H.appWindow(x,y,w,h,title) → 中の矩形 {x,y,w,h}   H.toast(x,y,w,title,sub,"done|blocked",k,lt)
  H.emblem("ring|wheel",cx,cy,r,回転,alpha,文字)   H.cursor(x,y,押下,lt)
線と移動
  H.qpt(p0,c,p1,u) 二次曲線の点   H.arrow(p0,c,p1,k,{color,width,dashed,glow,head})   H.packet(p0,c,p1,u,ラベル,{color})
演出
  H.particles({seed,n,x,y,w,h,color,size,speed,alpha}, lt) 種で決まる粒子   H.heading(s, lt) 左上の見出し
  H.camAt(keys, 進み) / H.applyCam(cam) カメラを自分で掛ける
部品を道具に
  H.sub(type, spec, lt, d, {x, y, scale, alpha, clip}) 部品を縮小して置く（spec は s の中に置くと計算が使い回される）
立体（parts-depth.js。透視の焦点 1400、中心が原点・z は奥が正）
  H.p3(x, y, z[, cx, cy]) 3D の点を画面へ → {x, y, s（縮尺）}   H.rot3([x,y,z], 傾き ax, 回転 ay) 縦軸で回してから横軸で傾ける
  H.plane(左上, 右上, 左下, w, h, function (ctx) {…w×h の絵…}, {cx, cy, both}) 3D の面に 2D の絵を貼る（裏向きは描かない。both で両面）
  H.textPoints(文字, n, {size, weight, font, y}) 文字の形の点 n 個   H.shapePoints(形, n) circle square triangle diamond hexagon star arrow plus heart
  H.morph(点の並び A, B, 進み) 形の変身   H.mixColor(色, 色, 進み)
動きを強く
  H.text(行, x, y, {size, weight, font, align, color}, 出方, lt, 始まり ms, 長さ ms) 文字の出方（--list の一覧）で 1 行を出す
  H.burst(x, y, 弾けてからの ms, {n, seed, r, color}) 破片が弾ける   H.fx(["speedlines", …], lt, d, "under"|"over") 演出の層を描く
  H.shake(ms, 強さ, 長さ ms) その時刻に画面を揺らす（効果音と同じく条件の外で呼ぶ）   H.cams カメラの型の表
音
  H.sfx(ms, "名前か出来事", {v, pitch}) その時刻に効果音（条件の外で呼ぶ）
手本は recipes.md。"""


MIN_SEC = {"funnel": 4, "pyramid": 4, "venn": 5.5, "cycle": 5, "matrix": 5, "calendar": 5, "checklist": 3, "versus": 6, "ranking": 4, "keys": 3, "talk": 2, "layout": 7, "wordcloud": 5, "bigtype": 4.5, "area": 6, "stack": 6, "scatter": 6, "heatmap": 6, "gauge": 5, "rings": 5, "treemap": 6, "radar": 6, "phone": 6, "dashboard": 7,
           "form": 6, "notifs": 4, "scroll": 6, "drag": 5, "network": 6, "tree": 5, "states": 6, "map": 6, "layers": 6, "pipeline": 7, "icons": 3, "impact": 3.5, "countdown": 4, "orbit": 7, "logo": 6.5, "marquee": 5, "title": 8, "statement": 4.5, "bullets": 2.5, "flow": 3, "steps": 2, "terminal": 2.5, "stats": 4.5, "bars": 3.5,
           "compare": 3, "code": 2.5, "window": 7, "image": 5, "end": 4, "custom": 5,
           "cards": 3, "timeline": 3, "chat": 2, "line": 6, "donut": 6, "table": 3, "quote": 6, "kinetic": 3, "split": 6,
           "beforeafter": 7, "dom": 5}
MIN_SEC.update({"cube": 5, "carousel": 5, "explode": 5, "tunnel": 6, "parallax": 4, "swarm": 5, "morph": 5, "barrage": 4, "rotator": 4, "textpath": 4.5, "emphasis": 4})


def wav_info(path, step_ms=50):
    """WAV の長さ（ms）と、step_ms ごとの音量（0..1。口パクに使う）。PCM 8/16/32bit のみ。"""
    import wave, array
    with wave.open(path, "rb") as w:
        n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    dur = n * 1000.0 / sr
    if sw == 2:
        a = array.array("h", raw); full = 32768.0
    elif sw == 4:
        a = array.array("i", raw); full = 2147483648.0
    else:
        a = array.array("B", raw); a = array.array("h", [(x - 128) * 256 for x in a]); full = 32768.0
    if sys.byteorder == "big" and sw > 1:
        a.byteswap()
    per = max(1, int(sr * step_ms / 1000)) * ch
    env = []
    for i in range(0, len(a), per):
        seg = a[i:i + per]
        if not seg:
            break
        rms = (sum(x * x for x in seg[::4]) / max(1, len(seg[::4]))) ** .5 / full
        env.append(rms)
    mx = max(env) if env else 1
    return dur, [round(v / mx, 2) if mx else 0 for v in env]


def _embed(path, base, default="image/png"):
    if not path or re.match(r"^(data:|https?:)", path):
        return path, None
    p = os.path.join(base, path)
    if not os.path.isfile(p):
        return None, p
    mime = mimetypes.guess_type(p)[0] or default
    return "data:%s;base64,%s" % (mime, base64.b64encode(open(p, "rb").read()).decode("ascii")), None


def is_dialogue(s):
    """掛け合いの場面か（lines に話し手 who 付きのせりふがある。end・statement の lines とは別）。"""
    return isinstance(s.get("lines"), list) and any(isinstance(ln, dict) and ln.get("who") for ln in s["lines"])


def narration_text(s):
    n = s.get("narration") or ""
    return "\n".join(n) if isinstance(n, list) else str(n)


def spoken(text, pronounce):
    """読み上げる文（**強調** を外し、audio.pronounce の読みに置き換えた後）。長さの見積もりもこれで数える。"""
    s = re.sub(r"\*\*", "", text)
    for k in sorted(pronounce or {}, key=len, reverse=True):   # 長い語から（engine.js と同じ順）
        s = s.replace(k, pronounce[k])
    return s.strip()


def speech_seconds(text, lang, pronounce=None):
    """読み上げにかかる秒数（速さ 1.0 のとき）。ブラウザの日本語の声は 1 秒に 6 文字前後なので、少し遅めに見積もる。"""
    plain = spoken(text, pronounce)
    if not plain:
        return 0.0
    if lang.startswith("ja") or lang.startswith("zh"):
        chars = len(re.sub(r"[\s、。，．・「」（）()]", "", plain)) + 0.35 * len(re.findall(r"[、。，．]", plain))
        return chars / 6.2
    return len(plain.split()) / 2.5


def min_seconds(s):
    t = s.get("type")
    base = MIN_SEC.get(t, 5)
    if t == "bullets":
        base += 1.6 * len(s.get("items", []))
    elif t == "flow":
        base += 0.9 * len(s.get("nodes", [])) + 1.2 * sum(1 for e in s.get("edges", []) if e.get("travel") not in (None, False))
    elif t == "steps":
        base += 1.5 * len(s.get("items", []))
    elif t == "terminal":
        base += sum(len(l.get("cmd", "")) for l in s.get("lines", [])) * 0.045 + 0.4 * sum(1 for l in s.get("lines", []) if "out" in l)
    elif t == "bars":
        base += 0.5 * len(s.get("items", []))
    elif t == "compare":
        base += 1.0 * (len(s.get("left", {}).get("points", [])) + len(s.get("right", {}).get("points", [])))
    elif t == "code":
        base += 2.2 * len(s.get("highlight", []))
    elif t == "end":
        base += 0.8 * len(s.get("lines", [])) + 2.5
    elif t in ("cards", "timeline"):
        base += 1.0 * len(s.get("items", []))
    elif t == "chat":
        base += sum(1.2 + len(m.get("text", "")) * .03 for m in s.get("messages", []))
    elif t == "table":
        base += 0.3 * len(s.get("rows", [])) + 1.8 * len(s.get("highlight", []))
    elif t == "kinetic":
        base += 0.35 * len(re.findall(r"\*\*[^*]+\*\*|[^\s*]+", s.get("text", "")))
    elif t == "form":
        base += 1.8 * len(s.get("fields", []))
    elif t == "drag":
        base += 2.2 * len(s.get("moves", [s.get("move")] if s.get("move") else []))
    elif t in ("notifs", "rings", "treemap", "scatter"):
        base += 0.6 * len(s.get("items", s.get("points", [])))
    elif t == "states":
        base += 0.5 * len(s.get("states", [])) + 1.3 * len(s.get("path", []))
    elif t == "phone":
        base += 2.5 * (len(s.get("screens", [])) or 1)
    elif t == "scroll":
        base += 1.4 * len(s.get("sections", []))
    elif t == "icons":
        base += 0.7 * len(s.get("items", []))
    elif t == "countdown":
        base += 1.0 * s.get("from", 3) + (1.5 if s.get("label") else 0)
    elif t == "orbit":
        base += 0.9 * len(s.get("items", []))
    elif t in ("funnel", "pyramid", "cycle", "matrix", "ranking", "checklist"):
        base += 0.8 * len(s.get("items", []))
    elif t == "calendar":
        base += 0.8 * len(s.get("events", []))
    elif t == "keys":
        base += 1.6 * len(s.get("combos", [1]))
    elif t == "versus":
        base += 0.4 * (len(s.get("left", {}).get("points", [])) + len(s.get("right", {}).get("points", [])))
    elif t == "statement":
        base += 0.6 * len(s.get("lines", [s.get("text", "")]))
    return base


SENT = re.compile(r"[^。！？!?\n]+[。！？!?]*")


# 字幕 1 行に収まる文字数の目安（字の大きさは映像の幅に比例するので、映像の大きさによらない）。これを超える文は読点で分ける
CUE_LIMIT = {"ja": 34, "zh": 34, "ko": 34}


def split_cues(text, lang):
    """ナレーションを字幕の単位に切る（文ごと。長い文は読点で分ける）。"""
    out = []
    for sent in SENT.findall(text):
        sent = sent.strip()
        if not sent:
            continue
        limit = CUE_LIMIT[lang[:2]] if lang[:2] in CUE_LIMIT else 70
        while len(re.sub(r"\*\*", "", sent)) > limit:
            # 読点のうち、文の中央に最も近い所で切る（末尾に短い切れ端を残さない）
            n = len(sent)
            cands = [m.start() for m in re.finditer(r"[、，]|, ", sent) if n // 4 <= m.start() <= n - n // 4]
            if not cands:
                break
            cut = min(cands, key=lambda c: abs(c - n / 2))
            out.append(sent[:cut + 1].strip())
            sent = sent[cut + 1:].strip()
        out.append(sent)
    return out


VOICE_GAP = 250   # 前もって作った声の、字幕と字幕の間（ms）


def prepare_voices(spec, base, mode, url=voice.DEFAULT_URL, vdir=None, outdir=None):
    """ナレーション（と掛け合いのせりふ）の声を前もって用意し、WAV を埋め込む。mode: voicevox / files。
    ナレーションは字幕の単位（split_cues）ごとに 1 つの WAV。返り値は (エラーの一覧, クレジット)。"""
    lang = spec.get("lang", "ja")
    au = spec.setdefault("audio", {})
    pron = au.get("pronounce") or {}
    vcfg = au.get("voice") or {}
    errs, vv = [], None
    if mode == "voicevox":
        vv = voice.Voicevox(url)
        outdir = outdir or os.path.join(base, "voices")
    files = sorted(os.path.join(vdir, f) for f in os.listdir(vdir) if f.lower().endswith(".wav")) if mode == "files" else []
    fi = 0
    cast = spec.get("cast") or {}
    for ch in spec["chapters"]:
        for s in ch["scenes"]:
            if is_dialogue(s):
                for ln in s["lines"]:
                    if ln.get("voice"):
                        continue
                    if mode == "voicevox":
                        cv = (cast.get(ln.get("who")) or {}).get("voice") or {}
                        if cv.get("engine") == "voicevox":
                            ln["voice"] = vv.synth(spoken(ln.get("text", ""), pron), cv, outdir)
                    elif fi < len(files):
                        ln["voice"] = files[fi]; fi += 1
                continue
            cues = split_cues(narration_text(s), lang)
            if not cues:
                continue
            paths = []
            for c in cues:
                if mode == "voicevox":
                    paths.append(vv.synth(spoken(c, pron), vcfg, outdir))
                elif fi < len(files):
                    paths.append(files[fi]); fi += 1
            if len(paths) < len(cues):   # WAV が足りない場面はブラウザの声のまま
                continue
            vs, ds = [], []
            for p in paths:
                try:
                    dur, env = wav_info(p)
                except Exception as e:
                    errs.append("音声は WAV（PCM）にしてください: %s（%s）" % (p, e))
                    break
                uri, _ = _embed(p, base, "audio/wav")
                vs.append({"voice": uri, "_env": env}); ds.append(int(dur))
            else:
                s["_voices"], s["_vdurs"], s["_vtexts"] = vs, ds, cues
    if mode == "files" and fi < len(files):
        errs.append("WAV が %d 個余りました（ナレーションの字幕とせりふは合わせて %d 個）。--timeline で字幕の数を確かめる" % (len(files) - fi, fi))
    credits = vv.credits() if vv else ([au["voice_credit"]] if au.get("voice_credit") else [])
    return errs, credits


def plan(spec):
    """場面ごとの長さ（ms）と字幕の時刻を決め、_dur・_cues を書き込む。警告の一覧を返す。"""
    lang = spec.get("lang", "ja")
    rate = float((spec.get("audio") or {}).get("rate", 1.1))
    pron = (spec.get("audio") or {}).get("pronounce") or {}
    warns = []
    cast = spec.get("cast") or {}
    for ci, ch in enumerate(spec["chapters"]):
        for si, s in enumerate(ch["scenes"]):
            if is_dialogue(s):
                # 掛け合い: せりふごとに、音声ファイルの長さか読み上げの見積もりで時間を割り付ける
                t, cl, pl = 400.0, [], []
                for li, ln in enumerate(s["lines"]):
                    if ln.get("_vdur"):
                        dur, est = ln["_vdur"], 0
                    else:
                        vr = float(((cast.get(ln.get("who")) or {}).get("voice") or {}).get("rate", rate))
                        est = speech_seconds(ln.get("text", ""), lang, pron) / vr * 1000
                        dur = max(900.0, est + 250)
                    pause = float(ln.get("pause", .3)) * 1000
                    cl.append([int(t), int(t + dur), ln.get("text", ""), ln.get("who"), li])
                    pl.append([int(est), int(ln.get("_vdur") or 0), int(pause)])
                    t += dur + pause
                ms = int(max(t + 500, min_seconds(s) * 1000, float(s.get("duration", 0)) * 1000))
                s["_dur"] = ms
                s["_cues"] = cl
                if any(e for e, _, _ in pl):   # ブラウザの声のせりふがある: 再生しながら実際の速さで直す（engine.js の retime）
                    s["_plan"] = {"min": int(min_seconds(s) * 1000), "floor": int(float(s.get("duration", 0)) * 1000), "L": pl}
                continue
            if s.get("_vdurs"):
                # 前もって作った声（VOICEVOX・用意した WAV）: 字幕は声の長さどおりに並べ、場面の長さも声で決まる
                t, cl = 500.0, []
                for i, (c, dur) in enumerate(zip(s["_vtexts"], s["_vdurs"])):
                    cl.append([int(t), int(t + dur), c, "", i])
                    t += dur + VOICE_GAP
                need = max(min_seconds(s) * 1000, t - VOICE_GAP + 700)
                if s.get("duration") and float(s["duration"]) * 1000 < t - VOICE_GAP + 300:
                    warns.append("第 %d 章「%s」の場面 %d（%s）: duration %.1f 秒では声（%.1f 秒）が収まらないので、声の長さに合わせます"
                                 % (ci + 1, ch.get("title", ""), si + 1, s.get("type"), float(s["duration"]), (t - VOICE_GAP) / 1000))
                s["_dur"] = int(max(need, float(s.get("duration", 0)) * 1000) // 100 * 100 + 100)
                s["_cues"] = cl
                continue
            text = narration_text(s)
            speech = speech_seconds(text, lang, pron) / rate
            need = max(min_seconds(s), speech + 1.2)
            if s.get("duration"):
                d = float(s["duration"])
                if d < speech + 0.8:
                    warns.append("第 %d 章「%s」の場面 %d（%s）: duration %.1f 秒ではナレーション（約 %.1f 秒）が収まりません"
                                 % (ci + 1, ch.get("title", ""), si + 1, s.get("type"), d, speech))
            else:
                d = round(need * 2) / 2
            ms = int(d * 1000)
            s["_dur"] = ms
            cues = split_cues(text, lang)
            lim = CUE_LIMIT.get(lang[:2], 70)
            for c in cues:
                if len(re.sub(r"\*\*", "", c)) > lim:
                    warns.append("第 %d 章「%s」の場面 %d（%s）: 字幕「%s」は %d 字で 1 行（約 %d 字）に収まりません（2 行に折り返す）。文の中ほどに読点か句点を入れると分かれます"
                                 % (ci + 1, ch.get("title", ""), si + 1, s.get("type"), c, len(re.sub(r"\*\*", "", c)), lim))
            a0, b0 = 500, max(900, ms - 400)
            # 字幕の時間は、読み上げる長さ（読みの置き換え後）に比例させる
            weight = [max(1.0, speech_seconds(c, lang, pron)) for c in cues]
            total = sum(weight) or 1
            acc, cl = a0, []
            for c, wgt in zip(cues, weight):
                span = (b0 - a0) * wgt / total
                cl.append([int(acc), int(acc + span), c])
                acc += span
            s["_cues"] = cl
            if cues and (spec.get("audio") or {}).get("narration", True) is not False:
                # ブラウザの声は環境で速さが違う。再生しながら実際の速さを測り、まだ来ていない場面の長さを直す（engine.js の retime）
                s["_plan"] = {"min": int(min_seconds(s) * 1000), "fix": ms if s.get("duration") else 0,
                              "sp": int(speech * 1000), "w": [round(x, 2) for x in weight],
                              "e": [int(speech_seconds(c, lang, pron) / rate * 1000) for c in cues]}
    return warns


def validate(spec, base):
    errs = []
    if not isinstance(spec.get("chapters"), list) or not spec["chapters"]:
        errs.append("chapters（章の配列）が必要です")
        return errs
    for ci, ch in enumerate(spec["chapters"]):
        if not ch.get("title"):
            errs.append("第 %d 章に title がありません" % (ci + 1))
        if not ch.get("scenes"):
            errs.append("第 %d 章「%s」に scenes がありません" % (ci + 1, ch.get("title", "")))
            continue
        for si, s in enumerate(ch["scenes"]):
            t = s.get("type")
            where = "第 %d 章「%s」の場面 %d" % (ci + 1, ch.get("title", ""), si + 1)
            if t not in SCENE_TYPES:
                errs.append("%s: 不明な type %r（--list で一覧）" % (where, t))
                continue
            for k in SCENE_TYPES[t][0]:
                if k not in s:
                    errs.append("%s（%s）: %s が必要です" % (where, t, k))
            if t == "custom":
                if s.get("src"):
                    p = os.path.join(base, s["src"])
                    if not os.path.isfile(p):
                        errs.append("%s: custom の src が見つかりません: %s" % (where, p))
                    else:
                        s["code"] = open(p, encoding="utf-8").read()
                if not s.get("code"):
                    errs.append("%s（custom）: code か src が必要です" % where)
                elif isinstance(s["code"], list):
                    s["code"] = "\n".join(s["code"])
            if t == "dom":
                for key, fk in (("html", "src"), ("css", "cssSrc"), ("update", "updateSrc")):
                    if s.get(fk):
                        p = os.path.join(base, s[fk])
                        if not os.path.isfile(p):
                            errs.append("%s: dom の %s が見つかりません: %s" % (where, fk, p))
                        else:
                            s[key] = open(p, encoding="utf-8").read()
                if not s.get("html") and not s.get("update"):
                    errs.append("%s（dom）: html（src）か update（updateSrc）が必要です" % where)
            if "sync" in s and s["sync"] not in (True, False, "auto"):
                errs.append("%s: sync は true（文に合わせる）・false（場面の長さに均等）・\"auto\"（項目と文の数が同じとき合わせる。既定）のいずれか" % where)
            for key, table, name in (("transition", TRANSITIONS, "切り替え"), ("anim", TEXT_ANIMS, "文字の出方"),
                                     ("ease", EASES, "緩急"), ("order", ORDERS, "現れる順")):
                if s.get(key) and not (isinstance(s[key], str) and s[key] in table):
                    errs.append("%s: %s は%sの設定で、%s のいずれか（%r は使えない）。%s"
                                % (where, key, name, "/".join(table), s[key],
                                   "" if isinstance(s[key], str) else
                                   "独自のデータなら別の名前にする（例: items・data。場面の共通の項目の名前は SKILL.md）"))
            if t == "layout":
                for li, sp in enumerate(s.get("slots") or []):
                    if not isinstance(sp, dict) or sp.get("type") not in SCENE_TYPES or sp.get("type") in ("layout", "dom", "custom"):
                        errs.append("%s: slots[%d] の type は部品の名前（layout・dom・custom 以外）" % (where, li))
                if s.get("template", "trio") not in ("trio", "inset", "collage", "fullbleed", "focus", "split2"):
                    errs.append("%s: template は trio / inset / collage / fullbleed / focus / split2 のいずれか" % where)
            if isinstance(s.get("camera"), str) and s["camera"] not in CAMERA_PRESETS:
                errs.append("%s: カメラの型 %r は %s のいずれか" % (where, s["camera"], "/".join(CAMERA_PRESETS)))
            for f in (s.get("fx") or []) if isinstance(s.get("fx"), list) else []:
                fk = f if isinstance(f, str) else (f or {}).get("kind")
                if fk not in FX:
                    errs.append("%s: fx %r は %s のいずれか" % (where, fk, "/".join(FX)))
            for oi, o in enumerate(s.get("overlays", [])):
                k = o.get("kind", "note")
                if k not in OVERLAY_KINDS:
                    errs.append("%s: overlays[%d] の kind %r は使えません（%s）" % (where, oi, k, "/".join(OVERLAY_KINDS)))
                    continue
                for r in OVERLAY_KINDS[k][0]:
                    if r not in o:
                        errs.append("%s: overlays[%d]（%s）に %s が必要です" % (where, oi, k, r))
            for ki, key in enumerate(s.get("camera", []) if isinstance(s.get("camera"), list) else []):
                if not isinstance(key, dict) or not any(x in key for x in ("x", "y", "zoom")):
                    errs.append("%s: camera[%d] は {at, x, y, zoom} の形にしてください" % (where, ki))
            if t in ("image", "layout") and s.get("src") and not re.match(r"^(data:|https?:)", s["src"]):
                p = os.path.join(base, s["src"])
                if not os.path.isfile(p):
                    errs.append("%s: 画像が見つかりません: %s" % (where, p))
                else:
                    mime = mimetypes.guess_type(p)[0] or "image/png"
                    s["src"] = "data:%s;base64,%s" % (mime, base64.b64encode(open(p, "rb").read()).decode("ascii"))
    def walk_icons(o, where):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("icon", "name") and isinstance(v, str) and re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+$|^[a-z]{3,}$", v) and (k == "icon" or o.get("kind") == "icon"):
                    if v not in icons.ICONS and not (k == "name" and o.get("kind") != "icon"):
                        errs.append("%s: アイコン %r は無い（--list-icons。絵文字も使える）" % (where, v))
                walk_icons(v, where)
        elif isinstance(o, list):
            for v in o:
                walk_icons(v, where)
    for ci, ch in enumerate(spec.get("chapters") or []):
        for si, s in enumerate(ch.get("scenes") or []):
            walk_icons(s, "第 %d 章の場面 %d" % (ci + 1, si + 1))
    if spec.get("transition") and not (isinstance(spec["transition"], str) and spec["transition"] in TRANSITIONS):
        errs.append("transition %r は %s のいずれか" % (spec["transition"], "/".join(TRANSITIONS)))
    for key, table, name in (("ease", EASES, "緩急"), ("order", ORDERS, "現れる順")):
        if spec.get(key) and not (isinstance(spec[key], str) and spec[key] in table):
            errs.append("%s %r は %s のいずれか" % (name, spec[key], "/".join(table)))
    if spec.get("motion") and spec["motion"] not in MOTION_STYLES:
        errs.append("motion %r は %s のいずれか" % (spec["motion"], "/".join(MOTION_STYLES)))
    for f in spec.get("fx") or []:
        fk = f if isinstance(f, str) else (f or {}).get("kind")
        if fk not in FX:
            errs.append("fx %r は %s のいずれか" % (fk, "/".join(FX)))
    # 登場人物（cast）: 立ち絵の画像を埋め込む。images は {表情: 画像} か {表情: {closed, open, half, blink}}
    for cid, c in (spec.get("cast") or {}).items():
        for face, v in list((c.get("images") or {}).items()):
            vals = v if isinstance(v, dict) else {"_": v}
            for key, path in list(vals.items()):
                uri, miss = _embed(path, base)
                if miss:
                    errs.append("cast.%s.images.%s: 画像が見つかりません: %s" % (cid, face, miss))
                elif isinstance(v, dict):
                    v[key] = uri
                else:
                    c["images"][face] = uri
    for ci, ch in enumerate(spec.get("chapters") or []):
        for si, s in enumerate(ch.get("scenes") or []):
            where = "第 %d 章の場面 %d" % (ci + 1, si + 1)
            for key in ("bg",):
                if s.get(key):
                    uri, miss = _embed(s[key], base)
                    if miss:
                        errs.append("%s: %s の画像が見つかりません: %s" % (where, key, miss))
                    else:
                        s[key] = uri
            if isinstance(s.get("board"), dict) and s["board"].get("type") == "image" and s["board"].get("src"):
                uri, miss = _embed(s["board"]["src"], base)
                if miss:
                    errs.append("%s: board の画像が見つかりません: %s" % (where, miss))
                else:
                    s["board"]["src"] = uri
            for li, ln in enumerate(s.get("lines") if is_dialogue(s) else []):
                if ln.get("who") and spec.get("cast") and ln["who"] not in spec["cast"]:
                    errs.append("%s: lines[%d] の who %r は cast に無い" % (where, li, ln["who"]))
                if ln.get("voice") and not str(ln["voice"]).startswith("data:"):
                    p = os.path.join(base, ln["voice"])
                    if not os.path.isfile(p):
                        errs.append("%s: lines[%d] の音声ファイルが見つかりません: %s" % (where, li, p))
                        continue
                    try:
                        dur, env = wav_info(p)
                        ln["_vdur"], ln["_env"] = int(dur), env
                    except Exception as e:  # WAV 以外（mp3 など）: 長さは読み上げの見積もり、口は文字の拍
                        errs.append("%s: lines[%d] の音声は WAV（PCM）にしてください（%s）" % (where, li, e))
                        continue
                    ln["voice"], _ = _embed(p, base, "audio/wav")
    errs += sound.prepare(spec, base)
    return errs


# ──────────────────────────────────────────────────────────────────────────
# HTML
# ──────────────────────────────────────────────────────────────────────────
ICON = {
    "play": '<svg class="i-play" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5l12 7-12 7z"/></svg>'
            '<svg class="i-pause" viewBox="0 0 24 24" fill="currentColor" hidden><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>',
    "stop": '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1.5"/></svg>',
    "prev": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h2.4v14H6zM19 5v14L9.5 12z"/></svg>',
    "next": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.6 5H18v14h-2.4zM5 5l9.5 7L5 19z"/></svg>',
    "audio": '<svg class="on" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/><path d="M16.5 8.5a5 5 0 010 7M19 6a8.5 8.5 0 010 12"/></svg>'
             '<svg class="off" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/><path d="M17 9.5l5 5M22 9.5l-5 5"/></svg>',
    "cc": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5.5" width="18" height="13" rx="2.5"/><path d="M10.5 10.2a2.4 2.4 0 100 3.6M17 10.2a2.4 2.4 0 100 3.6" stroke-linecap="round"/></svg>',
    "chapters": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h10M4 18h13"/></svg>',
    "pip": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><rect x="12" y="12" width="7" height="5" rx="1" fill="currentColor" stroke="none"/></svg>',
    "fs": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
    "more": '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>',
    "big": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 4l14 8-14 8z"/></svg>',
    "gear": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/></svg>',
}

PAGE_CSS = r"""
:root{--bg:#eef1f4;--ink:#131a22;--muted:#56616e;--line:#d3d9e0;--card:#ffffff;--focus:#1a56db}
@media (prefers-color-scheme:dark){:root{--bg:#0a0d12;--ink:#e6ebf1;--muted:#98a3b0;--line:#222a35;--card:#11161d;--focus:#6ea0ff;color-scheme:dark}}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--ink);font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif;font-size:15px;line-height:1.7;padding:24px 16px 48px}
.mv-page{max-width:1120px;margin:0 auto;display:flex;flex-direction:column;gap:18px}
.mv-head h1{font-size:clamp(22px,3.4vw,32px);line-height:1.25;margin:0;text-wrap:balance}
.mv-head p{margin:6px 0 0;color:var(--muted);max-width:44em}
"""

PLAYER_CSS = r"""
.mv-player,.mv-player *{box-sizing:border-box}
.mv-player [hidden]{display:none!important}
.mv-player{font-family:var(--mv-uifont,"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif);font-size:15px;line-height:1.7;margin:18px 0;
  position:relative;background:var(--c-bg);color:var(--c-ink);border:1px solid var(--c-line);border-radius:14px;overflow:hidden}
.mv-player:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
.mv-main{position:relative;min-width:0;container-type:inline-size}
.mv-stage{position:relative;aspect-ratio:16/9;max-width:100%;cursor:pointer;user-select:none;background:var(--c-bg);container-type:inline-size}
.mv-stage canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.mv-cap{position:absolute;left:50%;bottom:5%;transform:translateX(-50%);width:min(88%,1100px);text-align:center;pointer-events:none;transition:bottom .2s;text-wrap:balance;line-break:strict}
.mv-cap span{background:rgba(4,8,12,.8);color:#f5f8f9;font-weight:700;font-size:clamp(12px,2.4cqw,28px);line-height:1.75;padding:.18em .6em;border-radius:6px;
  box-decoration-break:clone;-webkit-box-decoration-break:clone}
.mv-big{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:clamp(56px,9vw,92px);height:clamp(56px,9vw,92px);border-radius:50%;
  border:2px solid var(--c-accent);background:color-mix(in srgb,var(--c-bg) 75%,transparent);color:var(--c-accent);display:grid;place-items:center;cursor:pointer;transition:transform .15s}
.mv-big:hover{transform:translate(-50%,-50%) scale(1.06)}
.mv-big:focus-visible{outline:3px solid var(--c-accent);outline-offset:4px}
.mv-big svg{width:42%;height:42%;margin-left:8%}
.mv-controls{display:flex;flex-direction:column;gap:6px;padding:10px 14px 12px;background:var(--c-bg2);border-top:1px solid var(--c-line)}
.mv-seek{position:relative;height:22px;display:flex;align-items:center;cursor:pointer;touch-action:none}
.mv-seek:focus-visible{outline:2px solid var(--c-accent);outline-offset:2px;border-radius:4px}
.mv-track{position:relative;width:100%;height:6px;display:flex;gap:3px}
.mv-seg{position:relative;height:100%;background:color-mix(in srgb,var(--c-ink) 18%,transparent);border-radius:2px;overflow:hidden}
.mv-seg i{position:absolute;inset:0;width:0;background:var(--c-accent);border-radius:2px}
.mv-seek:hover .mv-track,.mv-seek.drag .mv-track{height:8px}
.mv-knob{position:absolute;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;background:var(--c-ink);border:3px solid var(--c-accent);pointer-events:none}
.mv-tip{position:absolute;bottom:26px;transform:translateX(-50%);background:var(--c-bg);color:var(--c-ink);font-size:12px;line-height:1.4;padding:4px 8px;
  border-radius:6px;white-space:nowrap;pointer-events:none;border:1px solid var(--c-line)}
.mv-tip b{font-family:ui-monospace,Menlo,monospace;color:var(--c-accent);margin-right:6px}
/* 操作の行は 1 行に保つ。狭いときはチャプター名から縮め（… で省略）、さらに狭いと順に隠す（幅はプレイヤーの映像の側で見る） */
.mv-row{display:flex;align-items:center;gap:4px;flex-wrap:nowrap;min-width:0}
.mv-row>*{flex-shrink:0}
.mv-spacer{flex:1 1 0;min-width:0}
.mv-btn{appearance:none;border:0;background:transparent;color:var(--c-ink);height:36px;min-width:36px;padding:0 8px;border-radius:8px;
  display:inline-flex;align-items:center;justify-content:center;gap:6px;cursor:pointer;font:inherit;font-size:13px}
.mv-btn:hover{background:color-mix(in srgb,var(--c-ink) 10%,transparent)}
.mv-btn:focus-visible{outline:2px solid var(--c-accent);outline-offset:1px}
.mv-btn svg{width:20px;height:20px;flex:none}
.mv-btn[aria-pressed="false"] .on,.mv-btn[aria-pressed="true"] .off{display:none}
#mv-cc[aria-pressed="true"]{color:var(--c-accent)}
.mv-time{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--c-muted);font-variant-numeric:tabular-nums;padding:0 6px;white-space:nowrap}
.mv-time b{color:var(--c-ink);font-weight:600}
.mv-row>.mv-chapname{flex:0 1 auto;min-width:0}
.mv-chapname{font-size:13px;color:var(--c-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:24em;padding-left:4px}
/* 狭いときに隠す順（キー操作・ほかの場所で代わりがあるものから）: チャプター名 → 音量のつまみ（スピーカーで入切） → 停止（S）
   → 前・次のチャプター（[ ]・チャプターの一覧） → 小窓 → 速度（< >） → チャプターのメニュー（シークバーの区切り・一覧） */
@container (max-width:780px){.mv-chapname{display:none}}
@container (max-width:730px){.mv-vol{display:none}}
@container (max-width:650px){#mv-stop{display:none}}
@container (max-width:600px){#mv-prev,#mv-next{display:none}}
@container (max-width:520px){#mv-pip{display:none}}
@container (max-width:470px){.mv-speed{display:none}}
@container (max-width:400px){.mv-controls{padding-left:6px;padding-right:6px}.mv-row{gap:0}.mv-time{padding:0 2px}}
@container (max-width:330px){.mv-menuwrap:has(#mv-chapbtn){display:none}}
.mv-sec{display:flex;align-items:center;gap:4px}
.mv-morewrap{position:relative;display:flex;align-items:center;gap:4px}
#mv-more{display:none}
.mv-volwrap{display:inline-flex;align-items:center}
.mv-vol{width:76px;margin:0 6px 0 0;accent-color:var(--c-accent);cursor:pointer;height:20px}
.mv-vol:focus-visible{outline:2px solid var(--c-accent);outline-offset:2px;border-radius:4px}
@media(max-width:640px){.mv-vol{width:56px}}
.mv-speed{position:relative}
.mv-speed select{appearance:none;background:color-mix(in srgb,var(--c-ink) 8%,transparent);color:var(--c-ink);border:1px solid var(--c-line);border-radius:8px;
  height:32px;padding:0 26px 0 10px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px;cursor:pointer}
.mv-speed select option{background:var(--c-bg);color:var(--c-ink)}
.mv-speed select:focus-visible{outline:2px solid var(--c-accent);outline-offset:1px}
.mv-speed::after{content:"";position:absolute;right:10px;top:13px;border:4px solid transparent;border-top-color:var(--c-muted);pointer-events:none}
.mv-menuwrap{position:relative}
.mv-menu{position:absolute;right:0;bottom:44px;z-index:5;min-width:260px;background:var(--c-bg);border:1px solid var(--c-line);border-radius:10px;padding:6px;
  box-shadow:0 12px 30px rgba(0,0,0,.35);display:flex;flex-direction:column;
  /* 映像の高さ（幅の 9/16）に収め、中だけスクロールする。チャプターが多くても上が切れない */
  max-height:min(70vh,max(160px,calc(56.25cqw - 24px)));overflow-y:auto;overscroll-behavior:contain}
.mv-menu>*{flex-shrink:0}
[data-player="cinema"] .mv-menu,[data-player="minimal"] .mv-menu,[data-player="kiosk"] .mv-menu{max-height:min(70vh,max(160px,calc(56.25cqw - 110px)))}
.mv-menu button{appearance:none;border:0;background:transparent;color:var(--c-ink);text-align:left;font:inherit;font-size:13.5px;padding:8px 10px;border-radius:6px;
  display:grid;grid-template-columns:3em 1fr auto;gap:8px;cursor:pointer}
.mv-menu button:hover,.mv-menu button:focus-visible{background:color-mix(in srgb,var(--c-ink) 10%,transparent);outline:none}
.mv-menu button[aria-current="true"]{color:var(--c-accent)}
.mv-menu .n,.mv-menu .t{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--c-muted);align-self:center}
.mv-note{font-size:12px;color:var(--c-muted);padding:0 4px}
.mv-side{display:none}
.mv-side h2,.mv-below h2{font-size:12.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--c-accent);margin:0 0 8px;font-weight:700}
.mv-chaplist{list-style:none;margin:0;padding:0}
.mv-chaplist button{appearance:none;width:100%;border:0;border-top:1px solid var(--c-line);background:transparent;color:var(--c-ink);font:inherit;text-align:left;
  padding:10px 4px;display:grid;grid-template-columns:2.8em 1fr auto;gap:10px;cursor:pointer;align-items:baseline}
.mv-chaplist li:first-child button{border-top:0}
.mv-chaplist button:hover{color:var(--c-accent)}
.mv-chaplist button:focus-visible{outline:2px solid var(--c-accent);outline-offset:-2px;border-radius:6px}
.mv-chaplist button[aria-current="true"]{color:var(--c-accent);font-weight:700}
.mv-chaplist .n,.mv-chaplist .t{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--c-muted)}
.mv-chaplist .d{display:block;font-size:12.5px;color:var(--c-muted);font-weight:400;line-height:1.5;margin-top:2px}
.mv-keys{font-size:12.5px;color:var(--muted)}
.mv-keys kbd{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:0 5px;background:var(--card);color:var(--ink)}

/* studio: 操作部は下、チャプターの一覧を下に */
[data-player="studio"] .mv-chapters{display:block;padding:14px 18px;border-top:1px solid var(--c-line);background:var(--c-bg)}
[data-player="studio"] .mv-chaplist{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));column-gap:24px}
[data-player="studio"] .mv-chaplist li:nth-child(-n+3) button{border-top:0}
/* presenter: 横に目次 */
[data-player="presenter"]{display:grid;grid-template-columns:minmax(0,1fr) 300px}
/* 一覧は映像と同じ高さにし、中だけスクロールする（contain:size で行の高さを押し広げない） */
[data-player="presenter"] .mv-chapters{display:block;border-left:1px solid var(--c-line);padding:14px 16px;background:var(--c-bg2);overflow:auto;contain:size;min-height:0}
@media(max-width:860px){[data-player="presenter"]{grid-template-columns:1fr}[data-player="presenter"] .mv-chapters{border-left:0;border-top:1px solid var(--c-line);contain:none;max-height:320px}}
/* 重ねる操作部（cinema・minimal・kiosk） */
[data-player="cinema"] .mv-controls,[data-player="minimal"] .mv-controls,[data-player="kiosk"] .mv-controls{position:absolute;left:0;right:0;bottom:0;border-top:0;
  background:linear-gradient(to top,color-mix(in srgb,var(--c-bg) 92%,transparent),transparent);padding-top:40px;transition:opacity .25s}
.mv-playing:not(.mv-awake)[data-player="cinema"] .mv-controls,.mv-playing:not(.mv-awake)[data-player="minimal"] .mv-controls,
.mv-playing:not(.mv-awake)[data-player="kiosk"] .mv-controls{opacity:0;pointer-events:none}
.mv-playing:not(.mv-awake)[data-player="cinema"] .mv-stage,.mv-playing:not(.mv-awake)[data-player="kiosk"] .mv-stage{cursor:none}
[data-player="cinema"].mv-awake .mv-cap,[data-player="minimal"].mv-awake .mv-cap,[data-player="kiosk"].mv-awake .mv-cap,
.mv-player:not(.mv-playing)[data-player="cinema"] .mv-cap,.mv-player:not(.mv-playing)[data-player="minimal"] .mv-cap{bottom:24%}
/* minimal: 主な操作だけ見せ、残りは「⋯」 */
[data-player="minimal"] .mv-track{height:3px}
[data-player="minimal"] #mv-prev,[data-player="minimal"] #mv-next,[data-player="minimal"] .mv-chapname{display:none}
[data-player="minimal"] #mv-more{display:inline-flex}
[data-player="minimal"] .mv-sec{position:absolute;right:0;bottom:44px;z-index:6;flex-wrap:wrap;width:max-content;max-width:320px;padding:8px;background:var(--c-bg);
  border:1px solid var(--c-line);border-radius:10px;box-shadow:0 12px 30px rgba(0,0,0,.35)}
[data-player="minimal"] .mv-sec[hidden]{display:none}
[data-player="minimal"] .mv-menu{right:auto;left:0}
/* kiosk: 大きな字幕 */
[data-player="kiosk"] .mv-cap span{font-size:clamp(14px,3cqw,34px)}
.mv-player:fullscreen{border-radius:0;display:flex;flex-direction:column;justify-content:center;background:#000}
.mv-player:fullscreen .mv-side{display:none}
.mv-player:fullscreen .mv-stage{max-height:100vh;margin:0 auto;width:min(100vw,177.78vh)}
@media(max-width:640px){.mv-chapname{display:none}.mv-controls{padding:8px 10px}}
@media(prefers-reduced-motion:reduce){.mv-controls,.mv-cap{transition:none}}

/* シークバーのプレビュー（その時刻の画） */
.mv-tip{display:flex;flex-direction:column;align-items:center;gap:4px;padding:4px}
.mv-thumb{width:160px;height:90px;border-radius:4px;display:block;background:var(--c-bg)}
@media(max-width:640px){.mv-thumb{display:none}}
/* 設定 */
.mv-set{min-width:300px;width:max-content;max-width:min(360px,calc(100cqw - 16px));padding:10px;gap:6px}
.mv-setrow{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:13px;color:var(--c-muted);padding:4px 6px}
.mv-setrow>span:first-child,.mv-setrow>label:first-child{white-space:nowrap;flex-shrink:0}
.mv-fontsel{appearance:none;background:color-mix(in srgb,var(--c-ink) 8%,transparent);color:var(--c-ink);border:1px solid var(--c-line);border-radius:999px;
  font:inherit;font-size:12.5px;padding:4px 26px 4px 12px;cursor:pointer;max-width:200px;
  background-image:linear-gradient(45deg,transparent 50%,var(--c-muted) 50%),linear-gradient(135deg,var(--c-muted) 50%,transparent 50%);
  background-position:calc(100% - 14px) 52%,calc(100% - 10px) 52%;background-size:4px 4px;background-repeat:no-repeat}
.mv-fontsel option{background:var(--c-bg);color:var(--c-ink)}
.mv-fontsel:focus-visible{outline:2px solid var(--c-accent);outline-offset:2px}
.mv-cap span{font-family:var(--mv-capfont,inherit)}
.mv-seg3{display:inline-flex;gap:2px;padding:2px;border:1px solid var(--c-line);border-radius:999px}
/* .mv-menu button（チャプターの行の格子）を打ち消す */
.mv-set .mv-seg3 button{display:inline-block;grid-template-columns:none;gap:0;appearance:none;border:0;background:none;color:var(--c-muted);font:inherit;font-size:12.5px;
  padding:3px 12px;border-radius:999px;cursor:pointer;white-space:nowrap}
.mv-set .mv-seg3 button[aria-pressed="true"]{background:var(--c-accent);color:var(--c-bg)}
.mv-set button.mv-setitem{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;margin-top:4px;padding:8px 12px;white-space:nowrap;
  border:1px solid var(--c-line);background:color-mix(in srgb,var(--c-ink) 6%,transparent);border-radius:8px;font-weight:600;text-align:center}
.mv-set button.mv-setitem[hidden]{display:none}
.mv-set button.mv-setitem:hover,.mv-set button.mv-setitem:focus-visible{background:color-mix(in srgb,var(--c-accent) 14%,transparent);border-color:var(--c-accent)}
.mv-setnote{margin:2px 6px 4px;font-size:11.5px;color:var(--c-muted);line-height:1.5}
/* 字幕の大きさ */
.mv-player[data-cap="s"] .mv-cap span{font-size:clamp(11px,1.9cqw,22px)}
.mv-player[data-cap="l"] .mv-cap span{font-size:clamp(14px,3.1cqw,34px)}
/* 続きから・録画中 */
.mv-resume{position:absolute;left:16px;top:16px;z-index:3;appearance:none;border:1px solid var(--c-line);background:color-mix(in srgb,var(--c-bg) 85%,transparent);
  color:var(--c-ink);font:inherit;font-size:13px;padding:6px 12px;border-radius:999px;cursor:pointer}
.mv-resume:hover{border-color:var(--c-accent);color:var(--c-accent)}
.mv-resume:focus-visible{outline:2px solid var(--c-accent);outline-offset:2px}
.mv-recbadge{position:absolute;right:16px;top:16px;z-index:3;background:#d7263d;color:#fff;font-size:13px;font-weight:700;padding:4px 10px;border-radius:999px}
/* HTML・SVG で描く場面（dom）の層。1920×1080 の箱を舞台の大きさに縮める */
.mv-dom{position:absolute;inset:0;overflow:hidden;pointer-events:none}
.mv-dom>.mv-domscene{position:absolute;left:0;top:0;width:1920px;height:1080px;transform-origin:0 0}
/* 文字起こし */
.mv-transcript{display:none}
.mv-tsearch{width:100%;font:inherit;font-size:13px;padding:6px 10px;border-radius:8px;border:1px solid var(--c-line);background:color-mix(in srgb,var(--c-ink) 6%,transparent);color:var(--c-ink);margin-bottom:8px}
.mv-tlist{list-style:none;margin:0;padding:0}
.mv-tlist button{appearance:none;width:100%;border:0;background:transparent;color:var(--c-muted);font:inherit;font-size:13.5px;line-height:1.6;text-align:left;
  padding:6px 6px;border-radius:6px;display:grid;grid-template-columns:3.2em 1fr;gap:6px;cursor:pointer}
.mv-tlist button:hover{background:color-mix(in srgb,var(--c-ink) 8%,transparent)}
.mv-tlist button:focus-visible{outline:2px solid var(--c-accent);outline-offset:-2px}
.mv-tlist button[aria-current="true"]{color:var(--c-ink);background:color-mix(in srgb,var(--c-accent) 16%,transparent)}
.mv-tlist .t{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--c-accent);padding-top:2px}
/* theater: 横に文字起こし */
[data-player="theater"]{display:grid;grid-template-columns:minmax(0,1fr) 320px;background:#05070b}
.mv-player[data-uimode="light"][data-player="theater"]{background:var(--c-bg2)}
[data-player="theater"] .mv-transcript{display:block;border-left:1px solid var(--c-line);padding:14px 14px;background:var(--c-bg2);overflow:auto;contain:size;min-height:0}
@media(max-width:860px){[data-player="theater"]{grid-template-columns:1fr}[data-player="theater"] .mv-transcript{border-left:0;border-top:1px solid var(--c-line);contain:none;max-height:320px}}
/* slides: 章の終わりで止まる。「次へ」を目立たせる */
[data-player="slides"] .mv-big{width:auto;height:auto;border-radius:999px;padding:12px 22px;font-size:16px;font-weight:700;gap:8px;display:flex;align-items:center}
[data-player="slides"] .mv-big svg{width:20px;height:20px;margin:0}
[data-player="slides"] .mv-big .mv-biglabel{display:inline}
.mv-biglabel{display:none}
"""


_UID = [0]


def build_fragment(spec, theme_key, player, uid=None):
    """プレイヤー 1 つ分の HTML（1 ページに何個でも置ける。台本と配色はプレイヤーの中の JSON に入る）。"""
    th = THEMES[theme_key]
    ch = th["chrome"]
    _UID[0] += 1
    if not uid:
        # 台本の中身から決める（別々に作った断片を 1 ページに並べても id が重ならない。同じ台本なら同じ id）
        import hashlib
        uid = "mv" + hashlib.sha1((json.dumps(spec, ensure_ascii=False, sort_keys=True) + player + str(_UID[0])).encode("utf-8")).hexdigest()[:8]
    theme_js = {"canvas": th["canvas"], "fonts": th["fonts"], "pattern": th["pattern"]}
    title = spec.get("title") or "動画"
    minimal = player == "minimal"
    btn = lambda id_, label, icon, extra="": ('<button class="mv-btn" id="%s" type="button" aria-label="%s" title="%s"%s>%s</button>'
                                              % (id_, label, label, extra, icon))
    controls = (
        '<div class="mv-controls">'
        '<div class="mv-seek" id="mv-seek" role="slider" tabindex="0" aria-label="再生位置" aria-valuemin="0" aria-valuemax="0" aria-valuenow="0">'
        '<div class="mv-track" id="mv-track"></div><div class="mv-knob" id="mv-knob"></div>'
        '<div class="mv-tip" id="mv-tip" hidden><canvas class="mv-thumb" id="mv-thumb" width="256" height="144" aria-hidden="true"></canvas>'
        '<span id="mv-tiplabel"></span></div></div>'
        '<div class="mv-row">'
        + btn("mv-play", "再生", ICON["play"]) + btn("mv-stop", "停止して最初に戻る", ICON["stop"])
        + btn("mv-prev", "前のチャプター", ICON["prev"]) + btn("mv-next", "次のチャプター", ICON["next"])
        + '<span class="mv-time" id="mv-time"><b>0:00</b> / 0:00</span><span class="mv-chapname" id="mv-chapname"></span>'
        '<span class="mv-spacer"></span>'
        '<div class="mv-morewrap">'
        + btn("mv-more", "そのほかの操作（音声・字幕・速度・チャプター・設定）", ICON["more"], ' aria-haspopup="true" aria-expanded="false" aria-controls="mv-morepanel"')
        + '<div class="mv-sec" id="mv-morepanel"%s>' % (" hidden" if minimal else "")
        + '<span class="mv-volwrap">' + btn("mv-audio", "音声", ICON["audio"], ' aria-pressed="true"')
        + '<input type="range" class="mv-vol" id="mv-vol" min="0" max="100" step="5" value="100" aria-label="音量" title="音量（↑ ↓）"></span>'
        + btn("mv-cc", "字幕", ICON["cc"], ' aria-pressed="true"')
        + '<label class="mv-speed" title="再生速度"><select id="mv-speed" aria-label="再生速度">'
        + "".join('<option value="%s"%s>%s×</option>' % (v, " selected" if v == "1" else "", v) for v in ["0.5", "0.75", "1", "1.25", "1.5", "2"])
        + '</select></label>'
        '<div class="mv-menuwrap">'
        + btn("mv-chapbtn", "チャプター", ICON["chapters"], ' aria-haspopup="true" aria-expanded="false" aria-controls="mv-chapmenu"')
        + '<div class="mv-menu" id="mv-chapmenu" hidden></div></div>'
        '<div class="mv-menuwrap">'
        + btn("mv-setbtn", "設定（字幕の大きさ・音楽・効果音・保存）", ICON["gear"], ' aria-haspopup="true" aria-expanded="false" aria-controls="mv-setpanel"')
        + '<div class="mv-menu mv-set" id="mv-setpanel" hidden>'
        '<div class="mv-setrow"><span>字幕の大きさ</span><span class="mv-seg3" role="group" aria-label="字幕の大きさ">'
        '<button type="button" data-cap="s">小</button><button type="button" data-cap="m">標準</button><button type="button" data-cap="l">大</button></span></div>'
        '<div class="mv-setrow"><span>表示</span><span class="mv-seg3" role="group" aria-label="プレイヤーの表示（ライト・ダーク）">'
        '<button type="button" data-ui="">テーマ</button><button type="button" data-ui="light">ライト</button>'
        '<button type="button" data-ui="dark">ダーク</button><button type="button" data-ui="system">システム</button></span></div>'
        '<div class="mv-setrow"><label for="mv-font">書体</label><select class="mv-fontsel" id="mv-font" aria-label="書体（映像の文字・字幕・プレイヤーの文字）"></select></div>'
        '<div class="mv-setrow"><span>音楽</span><span class="mv-seg3" role="group" aria-label="音楽">'
        '<button type="button" data-mus="1">入</button><button type="button" data-mus="0">切</button></span></div>'
        '<div class="mv-setrow"><span>効果音</span><span class="mv-seg3" role="group" aria-label="効果音">'
        '<button type="button" data-sfx="1">入</button><button type="button" data-sfx="0">切</button></span></div>'
        '<button type="button" class="mv-setitem" id="mv-rec">動画ファイル（WebM）で保存</button>'
        + '<p class="mv-setnote">保存は最初から 1 倍速で再生して録画します（字幕は映像に焼き込み。%s）。</p>' % (
            "前もって作った声も入ります" if any(s_.get("_voices") for c_ in spec["chapters"] for s_ in c_["scenes"]) else "読み上げの声は入りません")
        + ''
        '</div></div>'
        '</div></div>'
        + btn("mv-pip", "小窓で再生（ピクチャー・イン・ピクチャー）", ICON["pip"], ' aria-pressed="false"')
        + btn("mv-fs", "全画面", ICON["fs"])
        + '</div><div class="mv-note" id="mv-voicenote" hidden>この端末には読み上げの声が無いため、音声は効果音と音楽だけになります。</div>'
        + ('<div class="mv-note mv-credit">音声: %s</div>' % html.escape("・".join(spec["_credits"])) if spec.get("_credits") else "")
        + ''
        '</div>')
    style = ("--c-bg:%s;--c-bg2:%s;--c-line:%s;--c-ink:%s;--c-muted:%s;--c-accent:%s"
             % (ch["bg"], ch["bg2"], ch["line"], ch["ink"], ch["muted"], ch["accent"]))
    data = json.dumps(spec, ensure_ascii=False).replace("</", "<\\/")
    frag = (
        '<section class="mv-player" id="mv-player" data-player="%s" tabindex="0" aria-label="%s" style="%s">'
        '<script type="application/json" data-mv-spec>%s</script><script type="application/json" data-mv-theme>%s</script>'
        '<script type="application/json" data-mv-icons>%s</script>'
        '<div class="mv-main"><div class="mv-stage" id="mv-stage"><canvas id="mv-canvas" aria-hidden="true"></canvas>'
        '<div class="mv-dom" id="mv-dom"></div>'
        '<div class="mv-cap"><span id="mv-captext" hidden></span></div>'
        '<button class="mv-big" id="mv-big" type="button" aria-label="再生">%s</button>'
        '<button class="mv-resume" id="mv-resume" type="button" hidden></button>'
        '<span class="mv-recbadge" id="mv-recbadge" hidden>● 録画中</span></div>%s</div>'
        '<aside class="mv-side mv-chapters" aria-label="チャプター"><h2>チャプター</h2><ol class="mv-chaplist" id="mv-chaplist"></ol></aside>'
        '<aside class="mv-side mv-transcript" aria-label="文字起こし"><h2>文字起こし</h2>'
        '<input type="search" class="mv-tsearch" id="mv-tsearch" placeholder="文字起こしを検索" aria-label="文字起こしを検索">'
        '<ol class="mv-tlist" id="mv-tlist"></ol></aside>'
        '</section>' % (player, html.escape(title, quote=True), style, data, json.dumps(theme_js, ensure_ascii=False),
                        json.dumps(icons.pick(icons.used_in(data)), ensure_ascii=False), ICON["big"] + '<span class="mv-biglabel"></span>', controls))
    # id はプレイヤーごとの名前にし、エンジンは data-mv で探す
    frag = re.sub(r'\bid="mv-([\w-]+)"', lambda m: 'data-mv="%s" id="%s-%s"' % (m.group(1), uid, m.group(1)), frag)
    frag = re.sub(r'aria-controls="mv-([\w-]+)"', lambda m: 'aria-controls="%s-%s"' % (uid, m.group(1)), frag)
    return frag


def player_css():
    """プレイヤーだけに効く CSS（ページの見た目には触れない。#mv-x は data-mv に読み替える）。"""
    return re.sub(r"#mv-([\w-]+)", r'[data-mv="\1"]', PLAYER_CSS)


def engine_js():
    """音の合成（audio.js）・部品（parts-*.js）・描画とプレイヤー（engine.js）。1 ページで 1 度だけ効く。"""
    parts = sorted(f for f in os.listdir(HERE) if f.startswith("parts-") and f.endswith(".js"))
    return "\n".join(open(os.path.join(HERE, f), encoding="utf-8").read() for f in ["audio.js"] + parts + ["engine.js"])


def build_embed(spec, theme_key, player):
    """ほかの HTML（md-to-doc の文書など）に差し込む断片。CSS と実行部は一度だけ効く。"""
    return ('<div class="mv-embed">%s<style>%s</style><script>%s</script></div>'
            % (build_fragment(spec, theme_key, player), player_css(), engine_js()))


def build_html(spec, theme_key, player):
    title = spec.get("title") or "動画"
    desc = spec.get("description") or ""
    head = '<header class="mv-head"><h1>%s</h1>%s</header>' % (html.escape(title), "<p>%s</p>" % html.escape(desc) if desc else "")
    keys = ('<p class="mv-keys"><kbd>Space</kbd> 再生・一時停止　<kbd>S</kbd> 停止　<kbd>←</kbd><kbd>→</kbd> 5 秒　<kbd>J</kbd><kbd>L</kbd> 10 秒　'
            '<kbd>0</kbd>〜<kbd>9</kbd> 0〜90%　<kbd>[</kbd><kbd>]</kbd> チャプター　<kbd>&lt;</kbd><kbd>&gt;</kbd> 速度　<kbd>C</kbd> 字幕　'
            '<kbd>M</kbd> 音声　<kbd>↑</kbd><kbd>↓</kbd> 音量　<kbd>F</kbd> 全画面</p>')
    return ("<!doctype html>\n<html lang=\"%s\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>%s</title>"
            "<style>%s%s</style></head><body><main class=\"mv-page\">%s%s%s</main><script>%s</script></body></html>\n"
            % (html.escape(spec.get("lang", "ja")), html.escape(title), PAGE_CSS, player_css(), head,
               build_fragment(spec, theme_key, player, "mv"), keys if player != "kiosk" else "", engine_js()))


def sound_board():
    """曲と効果音を聞き比べる 1 枚の HTML（audio.js だけを使う。映像は無い）。"""
    music = {k: v for k, v in sound.MUSIC.items()}
    kits = {}
    for k, (n, desc, m) in sound.KITS.items():
        merged = {}
        for ev in sound.EVENTS:
            v = m.get(ev) if ev in m else (None if "**" in m else sound.KITS["standard"][2].get(ev))
            if v:
                merged[ev] = v
        kits[k] = {"name": n, "desc": desc, "map": merged}
    data = json.dumps({"music": music, "sfx": sound.SFX, "kits": kits, "events": sound.EVENTS,
                       "mcats": sound.MUSIC_CATS, "scats": sound.SFX_CATS}, ensure_ascii=False).replace("</", "<\\/")
    audio = open(os.path.join(HERE, "audio.js"), encoding="utf-8").read()
    return """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>motion-video の音</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2430;--muted:#5d6878;--line:#dde2ea;--accent:#2f6fde;--on:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#12161c;--card:#1a2029;--ink:#e6ebf2;--muted:#9aa6b6;--line:#2c3542;--accent:#6ea2ff;--on:#0b1220}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,"Hiragino Sans","Noto Sans JP",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 80px}h1{font-size:24px;margin:0 0 4px}h2{font-size:19px;margin:34px 0 8px;border-bottom:2px solid var(--line);padding-bottom:6px}
h3{font-size:14px;color:var(--muted);margin:18px 0 6px}p.lead{color:var(--muted);margin:0 0 14px}
.bar{position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;gap:12px;align-items:center;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line)}
.bar label{display:flex;gap:6px;align-items:center;font-size:13px;color:var(--muted)}select,button{font:inherit}
.bar button{padding:6px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.now{font-size:13px;color:var(--accent);font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:8px}
.m{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;align-items:center;text-align:left;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);cursor:pointer}
.m:hover,.s:hover{border-color:var(--accent)}.m[aria-pressed="true"]{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent) inset}
.m .i{grid-row:span 2;width:30px;height:30px;border-radius:50%;background:var(--accent);color:var(--on);display:grid;place-items:center;font-size:13px}
.m b{font-size:15px}.m small{color:var(--muted);font-size:12px}.m code,.s code{font-size:11.5px;color:var(--muted)}
.sg{display:flex;flex-wrap:wrap;gap:6px}.s{padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);cursor:pointer}
table{border-collapse:collapse;width:100%;font-size:13px;background:var(--card)}th,td{border:1px solid var(--line);padding:4px 8px;text-align:left}th{background:var(--bg)}
td button{border:0;background:none;color:var(--accent);cursor:pointer;padding:0}
@media (max-width:600px){.grid{grid-template-columns:1fr}}
</style></head><body><main>
<h1>motion-video の音</h1>
<p class="lead">曲（__NM__ 曲）と効果音（__NS__ 種）を試し聞きする。どれも Web Audio で合成した音で、同じ台本からは同じ音が鳴る。名前（<code>code</code>）を台本の <code>audio.music</code>・<code>sfx</code> に書く。</p>
<div class="bar"><label>盛り上がり <select id="en"><option value="1">1（静か）</option><option value="2" selected>2（標準）</option><option value="3">3（山場）</option></select></label>
<label>章 <select id="ci"><option value="0">1 章目の進行</option><option value="1">2 章目</option><option value="2">3 章目</option></select></label>
<button type="button" id="stop">■ 止める</button><span class="now" id="now"></span></div>
<h2>曲</h2><div id="music"></div>
<h2>効果音</h2><div id="sfx"></div>
<h2>効果音の組（出来事 → 効果音）</h2><p class="lead">組の名前をクリックすると、主な出来事の音を順に鳴らす。</p><div id="kits"></div>
</main>
<script>__AUDIO__</script>
<script>
var D = __DATA__, MA = window.MotionAudio, ac = null, cur = null;
function ensure() { if (!ac) ac = new (window.AudioContext || window.webkitAudioContext)(); if (ac.state === "suspended") ac.resume(); }
function el(t, a, h) { var e = document.createElement(t); if (a) Object.keys(a).forEach(function (k) { e.setAttribute(k, a[k]); }); if (h !== undefined) e.innerHTML = h; return e; }
function stop() { if (!cur) return; clearInterval(cur.timer); var g = cur.bus; g.gain.setTargetAtTime(0, ac.currentTime, .08); setTimeout(function () { g.disconnect(); }, 800);
  if (cur.btn) cur.btn.setAttribute("aria-pressed", "false"); cur = null; document.getElementById("now").textContent = ""; }
function playMusic(id, btn) {
  var same = cur && cur.id === id; stop(); if (same) return; ensure();
  var def = JSON.parse(JSON.stringify(D.music[id])), bus = ac.createGain(); bus.gain.value = def.g || 1; bus.connect(ac.destination);
  var t0 = ac.currentTime + .12, upTo = 0, info = { ci: +document.getElementById("ci").value, energy: +document.getElementById("en").value, len: 1e12 };
  var tick = function () { var now = (ac.currentTime - t0) * 1000, to = now + 500; if (to <= upTo) return;
    MA.notes(def, info, upTo, to).forEach(function (n) { MA.note(ac, bus, n, t0 + n.t / 1000, Math.max(.05, (n.d || 0) / 1000), 1); }); upTo = to; };
  tick(); cur = { id: id, bus: bus, btn: btn, timer: setInterval(tick, 100) }; btn.setAttribute("aria-pressed", "true");
  document.getElementById("now").textContent = "♪ " + def.name + "（" + id + "）";
}
var fx = null;
function playSfx(id, v, pitch) { ensure(); if (!fx) { fx = ac.createGain(); fx.connect(ac.destination); } MA.play(ac, fx, D.sfx[id], ac.currentTime + .02, { v: v || 1, pitch: pitch || 0, seed: 1 }); }
D.mcats.forEach(function (cat) {
  var box = document.getElementById("music"); box.appendChild(el("h3", null, cat)); var g = el("div", { class: "grid" }); box.appendChild(g);
  Object.keys(D.music).forEach(function (k) { var m = D.music[k]; if (m.cat !== cat) return;
    var b = el("button", { type: "button", class: "m", "aria-pressed": "false" }, '<span class="i">▶</span><b>' + m.name + ' <code>' + k + '</code></b><small>' + m.bpm + ' BPM・' + m.key + ' ' + m.scale + '・' + m.desc + '</small>');
    b.addEventListener("click", function () { playMusic(k, b); }); g.appendChild(b); });
});
D.scats.forEach(function (cat) {
  var box = document.getElementById("sfx"); box.appendChild(el("h3", null, cat)); var g = el("div", { class: "sg" }); box.appendChild(g);
  Object.keys(D.sfx).forEach(function (k) { var s = D.sfx[k]; if (s.cat !== cat) return;
    var b = el("button", { type: "button", class: "s", title: s.desc }, s.name + ' <code>' + k + '</code>'); b.addEventListener("click", function () { playSfx(k); }); g.appendChild(b); });
});
(function () {
  var evs = Object.keys(D.events), t = el("table"), hr = el("tr"); hr.appendChild(el("th", null, "出来事"));
  Object.keys(D.kits).forEach(function (k) { var th = el("th"), b = el("button", { type: "button", title: D.kits[k].desc }, "▶ " + D.kits[k].name + "<br><code>" + k + "</code>");
    b.addEventListener("click", function () { var i = 0; ["title", "chapter", "tr.slide", "appear", "appear", "appear", "step", "connect", "countEnd", "notify", "done", "click", "outro"].forEach(function (ev, j) {
      var m = D.kits[k].map[ev]; if (!m) return; setTimeout(function () { playSfx(m[0], m[1], (ev === "appear" ? j - 3 : 0) * (m[2] || 0)); }, (i++) * 650); }); });
    th.appendChild(b); hr.appendChild(th); });
  t.appendChild(hr);
  evs.forEach(function (ev) { var tr = el("tr"); tr.appendChild(el("td", null, "<code>" + ev + "</code><br>" + D.events[ev][0]));
    Object.keys(D.kits).forEach(function (k) { var m = D.kits[k].map[ev], td = el("td");
      if (m) { var b = el("button", { type: "button" }, m[0]); b.addEventListener("click", function () { playSfx(m[0], m[1]); }); td.appendChild(b); } else td.textContent = "—";
      tr.appendChild(td); }); t.appendChild(tr); });
  var wrap = el("div", { style: "overflow-x:auto" }); wrap.appendChild(t); document.getElementById("kits").appendChild(wrap);
})();
document.getElementById("stop").addEventListener("click", stop);
["en", "ci"].forEach(function (id) { document.getElementById(id).addEventListener("change", function () { if (cur) { var c = cur; stop(); playMusic(c.id, c.btn); } }); });
</script></body></html>
""".replace("__AUDIO__", audio).replace("__DATA__", data).replace("__NM__", str(len(sound.MUSIC))).replace("__NS__", str(len(sound.SFX)))


def print_list():
    print("# プレイヤー（--player / 台本の player）")
    for k, (n, d) in PLAYERS.items():
        print("  %-10s %s — %s" % (k, n, d))
    print("\n# 配色テーマ（--theme / 台本の theme）")
    for k, t in THEMES.items():
        print("  %-11s %s — %s" % (k, t["label"], t["desc"]))
    print("\n# 場面の部品（chapters[].scenes[].type）")
    print("  " + COMMON)
    for k, (req, desc, ex) in SCENE_TYPES.items():
        print("\n  [%s] %s（必須: %s）\n    %s" % (k, desc, ", ".join(req) or "なし", ex))
    print("\n# 重ねの層（場面の overlays: [...]。座標は 1920×1080、at / until は場面の進み 0..1。atCue / untilCue は n 番目（1 から）の字幕の文が始まる・終わる時）")
    for k, (req, desc, ex) in OVERLAY_KINDS.items():
        print("  [%s] %s（必須: %s）\n    %s" % (k, desc, ", ".join(req), ex))
    print("\n# カメラ\n  " + CAMERA_DOC)
    print("\n# 動きの性格（台本の motion。切り替え・文字の出方・演出・カメラの既定をまとめて決める。場面の指定が優先）")
    for k, d in MOTION_STYLES.items():
        print("  %-10s %s" % (k, d))
    print("\n# 場面の切り替え（transition。台本全体か場面ごと。省くと motion の既定）")
    print("  " + "　".join("%s（%s）" % kv for kv in TRANSITIONS.items()))
    print("\n# 文字の出方（場面の anim）")
    print("  " + "　".join("%s（%s）" % kv for kv in TEXT_ANIMS.items()))
    print("\n# 動き方（場面の ease・order。台本全体にも書ける）")
    print("  ease: " + "　".join("%s（%s）" % kv for kv in EASES.items()))
    print("  order: " + "　".join("%s（%s）" % kv for kv in ORDERS.items()) + "　※ 項目を順に出す部品（bullets・cards・steps など）に効く")
    print("\n# 演出の層（場面の fx・台本の fx。文字列か {kind, color, alpha, n, seed}）")
    print("  " + "　".join("%s（%s）" % kv for kv in FX.items()))
    print("\n# 表現のモード（台本の expression）")
    for k, d in EXPRESSIONS.items():
        print("  %-10s %s" % (k, d))
    print("\n# 台本の骨組み")
    print('  {"title":"…","description":"…","lang":"ja","player":"studio","theme":"navy-brass",'
          '"brand":{"name":"…"},"motion":"dynamic","poster":4300,'
          '"audio":{"narration":true,"music":"corporate","sfx":{"kit":"standard","density":"normal"},"rate":1.1,"wait":true,"pronounce":{"Sodashitsu":"ソダシツ"}},'
          '"expression":"mixed","chapters":[{"title":"章の名前","desc":"一覧に出す説明","scenes":[{…場面…}]}]}')
    print("\n# アイコン（部品の icon・重ねの層の icon・H.icon）\n  %d 種。一覧は --list-icons。icon には絵文字も書ける" % len(icons.ICONS))
    print("\n# 音（曲 %d・効果音 %d・効果音の組 %d）\n  一覧と書き方は --list-sounds、聞き比べるページは --sounds -o sounds.html"
          % (len(sound.MUSIC), len(sound.SFX), len(sound.KITS)))
    print("\ncustom の道具は --api、手本は recipes.md")


def main():
    ap = argparse.ArgumentParser(description="台本（JSON）から動画のように再生できる単一 HTML を作る")
    ap.add_argument("spec", nargs="?", help="台本の JSON")
    ap.add_argument("-o", "--out", help="出力 HTML（既定: 台本と同じ場所・同じ名前の .html）")
    ap.add_argument("--player", choices=list(PLAYERS), help="プレイヤー（台本の player を上書き）")
    ap.add_argument("--theme", choices=list(THEMES), help="配色テーマ（台本の theme を上書き）")
    ap.add_argument("--list", action="store_true", help="プレイヤー・配色・場面の部品と台本の書き方を出す")
    ap.add_argument("--timeline", action="store_true", help="HTML を作らず、場面の長さと字幕の時刻を出す")
    ap.add_argument("--api", action="store_true", help="custom の場面で使える描画の道具（H.*）の一覧を出す")
    ap.add_argument("--embed", action="store_true", help="ページではなく、ほかの HTML に差し込む断片を出す（md-to-doc の文書など）")
    ap.add_argument("--list-sounds", action="store_true", help="曲・効果音・効果音の組・出来事と、audio の書き方を出す")
    ap.add_argument("--list-icons", action="store_true", help="線で描くアイコンの一覧を出す")
    ap.add_argument("--sounds", action="store_true", help="曲と効果音を聞き比べる HTML を作る（-o で出力先。既定 sounds.html）")
    ap.add_argument("--voicevox", action="store_true", help="VOICEVOX でナレーションの声を前もって作り、埋め込む（話者は audio.voice）")
    ap.add_argument("--voicevox-url", default=voice.DEFAULT_URL, help="VOICEVOX の場所（既定 %(default)s）")
    ap.add_argument("--voices-dir", help="用意した WAV を名前順に、ナレーションの字幕（とせりふ）へ順に当てて埋め込む")
    ap.add_argument("--voices-out", help="VOICEVOX で作った WAV の置き場所（既定: 台本と同じ場所の <台本名>_voices/）")
    args = ap.parse_args()
    if args.api:
        print(API_DOC)
        return
    if args.list_sounds:
        sound.print_sounds()
        return
    if args.list_icons:
        icons.print_icons()
        return
    if args.sounds:
        out = args.out or os.path.abspath("sounds.html")
        open(out, "w", encoding="utf-8").write(sound_board())
        print("OK : %s（曲 %d・効果音 %d）" % (out, len(sound.MUSIC), len(sound.SFX)))
        return
    if args.list or not args.spec:
        print_list()
        return
    spec = json.load(open(args.spec, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(args.spec))
    if (args.voicevox or args.voices_dir) and isinstance(spec.get("chapters"), list):
        out_v = args.voices_out or os.path.splitext(os.path.abspath(args.spec))[0] + "_voices"
        verrs, spec["_credits"] = prepare_voices(spec, base, "voicevox" if args.voicevox else "files", args.voicevox_url, args.voices_dir, out_v)
        for e in verrs:
            print("error:", e, file=sys.stderr)
        if verrs:
            sys.exit(1)
        n = sum(len(s_.get("_vdurs") or []) for c_ in spec["chapters"] for s_ in c_["scenes"])
        print("声: ナレーションの字幕 %d 個に前もって作った声を当てました（作り済みの WAV は使い回し）" % n, file=sys.stderr)
    elif ((spec.get("audio") or {}).get("voice") or {}).get("engine") == "voicevox":
        print("warn: audio.voice は VOICEVOX ですが --voicevox が無いので、ブラウザの読み上げで再生します（時間は見積もり）", file=sys.stderr)
    errs = validate(spec, base)
    if errs:
        for e in errs:
            print("error:", e, file=sys.stderr)
        sys.exit(1)
    player = args.player or spec.get("player", "studio")
    theme = args.theme or spec.get("theme", "navy-brass")
    if player not in PLAYERS:
        sys.exit("error: 不明な player %r（%s）" % (player, "/".join(PLAYERS)))
    if theme not in THEMES:
        sys.exit("error: 不明な theme %r（%s）" % (theme, "/".join(THEMES)))
    warns = plan(spec)
    expr = spec.get("expression", "mixed")
    if expr not in EXPRESSIONS:
        warns.append("expression %r は %s のいずれか（mixed として扱います）" % (expr, "/".join(EXPRESSIONS)))
        expr = "mixed"
    kinds = [s["type"] for ch in spec["chapters"] for s in ch["scenes"]]
    if expr == "components" and "custom" in kinds:
        warns.append("expression=components なのに custom の場面が %d 個あります" % kinds.count("custom"))
    au = spec.get("audio") or {}
    own = [k for k in ("music",) if isinstance(au.get(k), dict) and (au[k].get("code") or au[k].get("layers"))] + (["sfxDefs"] if au.get("sfxDefs") else []) + (["instruments"] if au.get("instruments") else [])
    if expr == "components" and own:
        warns.append("expression=components なのに自作の音（%s）があります（部品だけのときは用意された曲・効果音を使う）" % ", ".join(own))
    if expr == "free" and "custom" not in kinds:
        warns.append("expression=free なのに custom の場面がありません（見せ場は custom で描く）")
    for w in warns:
        print("warn:", w, file=sys.stderr)
    total = sum(s["_dur"] for ch in spec["chapters"] for s in ch["scenes"])
    if args.timeline:
        t = 0
        for ci, ch in enumerate(spec["chapters"]):
            mk = ch.get("_music", spec["audio"].get("_musicKey"))
            print("%s  第 %d 章 %s　♪ %s" % (fmt(t), ci + 1, ch["title"], sound.music_label(ch["music"]) if "music" in ch else sound.music_label(spec["audio"].get("music")) if mk else "なし"))
            for s in ch["scenes"]:
                print("  %s  %-9s %5.1f 秒  %s" % (fmt(t), s["type"], s["_dur"] / 1000, (s.get("heading") or s.get("title") or "")[:30]))
                for cu in s["_cues"]:
                    who = (spec.get("cast") or {}).get(cu[3], {}).get("name", cu[3]) + "：" if len(cu) > 3 and cu[3] else ""
                    print("        %s–%s  %s%s" % (fmt(t + cu[0]), fmt(t + cu[1]), who, cu[2]))
                t += s["_dur"]
        print("合計 %s（%d 章・%d 場面）" % (fmt(total), len(spec["chapters"]), sum(len(c["scenes"]) for c in spec["chapters"])))
        return
    out = args.out or os.path.splitext(os.path.abspath(args.spec))[0] + (".embed.html" if args.embed else ".html")
    open(out, "w", encoding="utf-8").write(build_embed(spec, theme, player) if args.embed else build_html(spec, theme, player))
    print("OK : %s（%s・%s・%s）" % (out, player, theme, fmt(total)))


def fmt(ms):
    s = int(ms // 1000)
    return "%d:%02d" % (s // 60, s % 60)


if __name__ == "__main__":
    main()
