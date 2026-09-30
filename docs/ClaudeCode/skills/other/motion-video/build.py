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
    "title": (["title"], "表題（紋章・題名・副題・一文）", '{"type":"title","title":"Sodashitsu","subtitle":"操舵室","tagline":"**複数のエージェント**を一つの画面で","mark":"ring|wheel|none"}'),
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
    "end": ([], "締め（紋章・コマンドや連絡先の行・題名・一文）", '{"type":"end","title":"Sodashitsu","lines":[{"text":"$ soda serve","note":"ブラウザで開く"}],"tagline":"舵を一つの場所で"}'),
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
    "custom": ([], "JS で自由に描く（本体: (ctx, lt, d, H, s)。道具は --api。code は文字列か行の配列、または src に .js のパス）", '{"type":"custom","src":"scenes/intro.js","duration":8,"narration":"…"}'),
}
COMMON = ("共通: narration（ナレーション＝字幕。文字列か配列）・duration（秒。省略時は自動）・heading・transition（fade|slide|zoom|wipe|push|cut）"
          "・overlays（重ねの層）・camera（カメラ）")

OVERLAY_KINDS = {
    "note": (["text"], '注記の吹き出し。target で引き出し線', '{"kind":"note","text":"ここが**新しい**","x":1300,"y":200,"target":[900,420],"at":0.3,"until":0.9}'),
    "arrow": (["from", "to"], "描かれる矢印（curve で曲げる）", '{"kind":"arrow","from":[400,700],"to":[900,450],"curve":0.2,"label":"完了","at":0.4}'),
    "highlight": (["rect"], "枠で強調。spotlight で周りを暗く", '{"kind":"highlight","rect":[700,300,500,200],"spotlight":true,"label":"ここ","at":0.5,"until":0.8}'),
    "badge": (["text"], "弾んで出る札", '{"kind":"badge","text":"NEW","x":1500,"y":260,"at":0.2}'),
    "cursor": (["path"], "マウスの矢印が点を順にたどる。click はクリックする点の番号", '{"kind":"cursor","path":[[500,800],[900,420],[1200,420]],"click":[1],"at":0.2,"until":0.8}'),
    "notify": (["text"], "OS 風の通知（右上。pos:br で右下寄り）", '{"kind":"notify","app":"Sodashitsu","text":"impl が完了しました","at":0.3,"until":0.7}'),
}
CAMERA_DOC = ('camera: [{"at":0,"x":960,"y":540,"zoom":1},{"at":0.6,"x":1300,"y":480,"zoom":1.6}] — 場面の進み（0..1）で補間し、'
              '(x,y) を中央に zoom 倍で映す。部品にも custom にも効く。重ねの層もいっしょに動く')
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
  H.P(lt, a, b[, 緩急]) a..b ms の進み 0..1（既定 eo）   H.lin H.eo H.eio H.back H.clamp H.mix
  H.slots(n, d, 先頭ms, 末尾ms) n 個の区切りを場面の長さに割り付けた時刻の配列
文字
  H.txt(s, x, y, {size, weight, color, align, font, alpha, spacing})   H.tw(s, 同)=幅
  H.rich(行, x, y, {…}, 下線の進み) **強調** を色と下線で   H.wrap(s, 最大幅, {size, weight}) 折り返した行の配列
  H.typed(s, k) 入力中の文字（先頭から k の割合）   H.count("1,240件", k) 数え上げ中の表記
図形
  H.rr(x,y,w,h,r) 角丸の経路   H.panel(x,y,w,h,{fill,stroke,lw,r,shadow})   H.icon(絵文字,x,y,size)
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
手本は recipes.md。"""


MIN_SEC = {"title": 8, "statement": 4.5, "bullets": 2.5, "flow": 3, "steps": 2, "terminal": 2.5, "stats": 4.5, "bars": 3.5,
           "compare": 3, "code": 2.5, "window": 7, "image": 5, "end": 4, "custom": 5,
           "cards": 3, "timeline": 3, "chat": 2, "line": 6, "donut": 6, "table": 3, "quote": 6, "kinetic": 3, "split": 6,
           "beforeafter": 7, "dom": 5}


def narration_text(s):
    n = s.get("narration") or ""
    return " ".join(n) if isinstance(n, list) else str(n)


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
    elif t == "statement":
        base += 0.6 * len(s.get("lines", [s.get("text", "")]))
    return base


SENT = re.compile(r"[^。！？!?]+[。！？!?]*")


def split_cues(text, lang):
    """ナレーションを字幕の単位に切る（文ごと。長い文は読点で分ける）。"""
    out = []
    for sent in SENT.findall(text):
        sent = sent.strip()
        if not sent:
            continue
        limit = 44 if lang.startswith("ja") else 90
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


def plan(spec):
    """場面ごとの長さ（ms）と字幕の時刻を決め、_dur・_cues を書き込む。警告の一覧を返す。"""
    lang = spec.get("lang", "ja")
    rate = float((spec.get("audio") or {}).get("rate", 1.1))
    pron = (spec.get("audio") or {}).get("pronounce") or {}
    warns = []
    for ci, ch in enumerate(spec["chapters"]):
        for si, s in enumerate(ch["scenes"]):
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
            for oi, o in enumerate(s.get("overlays", [])):
                k = o.get("kind", "note")
                if k not in OVERLAY_KINDS:
                    errs.append("%s: overlays[%d] の kind %r は使えません（%s）" % (where, oi, k, "/".join(OVERLAY_KINDS)))
                    continue
                for r in OVERLAY_KINDS[k][0]:
                    if r not in o:
                        errs.append("%s: overlays[%d]（%s）に %s が必要です" % (where, oi, k, r))
            for ki, key in enumerate(s.get("camera", [])):
                if not isinstance(key, dict) or not any(x in key for x in ("x", "y", "zoom")):
                    errs.append("%s: camera[%d] は {at, x, y, zoom} の形にしてください" % (where, ki))
            if t == "image" and s.get("src") and not re.match(r"^(data:|https?:)", s["src"]):
                p = os.path.join(base, s["src"])
                if not os.path.isfile(p):
                    errs.append("%s: 画像が見つかりません: %s" % (where, p))
                else:
                    mime = mimetypes.guess_type(p)[0] or "image/png"
                    s["src"] = "data:%s;base64,%s" % (mime, base64.b64encode(open(p, "rb").read()).decode("ascii"))
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
.mv-player{font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif;font-size:15px;line-height:1.7;margin:18px 0;
  position:relative;background:var(--c-bg);color:var(--c-ink);border:1px solid var(--c-line);border-radius:14px;overflow:hidden}
.mv-player:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
.mv-main{position:relative;min-width:0}
.mv-stage{position:relative;aspect-ratio:16/9;max-width:100%;cursor:pointer;user-select:none;background:var(--c-bg)}
.mv-stage canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.mv-cap{position:absolute;left:50%;bottom:5%;transform:translateX(-50%);width:min(88%,1100px);text-align:center;pointer-events:none;transition:bottom .2s}
.mv-cap span{background:rgba(4,8,12,.8);color:#f5f8f9;font-weight:700;font-size:clamp(12px,2vw,24px);line-height:1.75;padding:.18em .6em;border-radius:6px;
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
.mv-row{display:flex;align-items:center;gap:4px;flex-wrap:wrap}
.mv-spacer{flex:1}
.mv-btn{appearance:none;border:0;background:transparent;color:var(--c-ink);height:36px;min-width:36px;padding:0 8px;border-radius:8px;
  display:inline-flex;align-items:center;justify-content:center;gap:6px;cursor:pointer;font:inherit;font-size:13px}
.mv-btn:hover{background:color-mix(in srgb,var(--c-ink) 10%,transparent)}
.mv-btn:focus-visible{outline:2px solid var(--c-accent);outline-offset:1px}
.mv-btn svg{width:20px;height:20px;flex:none}
.mv-btn[aria-pressed="false"] .on,.mv-btn[aria-pressed="true"] .off{display:none}
#mv-cc[aria-pressed="true"]{color:var(--c-accent)}
.mv-time{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--c-muted);font-variant-numeric:tabular-nums;padding:0 6px;white-space:nowrap}
.mv-time b{color:var(--c-ink);font-weight:600}
.mv-chapname{font-size:13px;color:var(--c-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:16em;padding-left:4px}
.mv-sec{display:flex;align-items:center;gap:4px}
.mv-morewrap{position:relative;display:flex;align-items:center;gap:4px}
#mv-more{display:none}
.mv-speed{position:relative}
.mv-speed select{appearance:none;background:color-mix(in srgb,var(--c-ink) 8%,transparent);color:var(--c-ink);border:1px solid var(--c-line);border-radius:8px;
  height:32px;padding:0 26px 0 10px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px;cursor:pointer}
.mv-speed select option{background:var(--c-bg);color:var(--c-ink)}
.mv-speed select:focus-visible{outline:2px solid var(--c-accent);outline-offset:1px}
.mv-speed::after{content:"";position:absolute;right:10px;top:13px;border:4px solid transparent;border-top-color:var(--c-muted);pointer-events:none}
.mv-menuwrap{position:relative}
.mv-menu{position:absolute;right:0;bottom:44px;z-index:5;min-width:260px;background:var(--c-bg);border:1px solid var(--c-line);border-radius:10px;padding:6px;
  box-shadow:0 12px 30px rgba(0,0,0,.35);display:flex;flex-direction:column}
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
[data-player="presenter"] .mv-chapters{display:block;border-left:1px solid var(--c-line);padding:14px 16px;background:var(--c-bg2);overflow:auto;max-height:100%}
@media(max-width:860px){[data-player="presenter"]{grid-template-columns:1fr}[data-player="presenter"] .mv-chapters{border-left:0;border-top:1px solid var(--c-line);max-height:none}}
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
[data-player="kiosk"] .mv-cap span{font-size:clamp(14px,2.6vw,32px)}
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
.mv-set{min-width:300px;padding:10px;gap:6px}
.mv-setrow{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:13px;color:var(--c-muted);padding:4px 6px}
.mv-seg3{display:inline-flex;gap:2px;padding:2px;border:1px solid var(--c-line);border-radius:999px}
.mv-seg3 button{appearance:none;border:0;background:none;color:var(--c-muted);font:inherit;font-size:12.5px;padding:3px 10px;border-radius:999px;cursor:pointer}
.mv-seg3 button[aria-pressed="true"]{background:var(--c-accent);color:var(--c-bg)}
.mv-set button.mv-setitem{display:block;width:100%;text-align:left;grid-template-columns:none}
.mv-setnote{margin:2px 6px 4px;font-size:11.5px;color:var(--c-muted);line-height:1.5}
/* 字幕の大きさ */
.mv-player[data-cap="s"] .mv-cap span{font-size:clamp(11px,1.6vw,19px)}
.mv-player[data-cap="l"] .mv-cap span{font-size:clamp(14px,2.7vw,32px)}
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
[data-player="theater"] .mv-transcript{display:block;border-left:1px solid var(--c-line);padding:14px 14px;background:var(--c-bg2);overflow:auto;max-height:100%}
@media(max-width:860px){[data-player="theater"]{grid-template-columns:1fr}[data-player="theater"] .mv-transcript{border-left:0;border-top:1px solid var(--c-line);max-height:320px}}
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
        + btn("mv-audio", "音声", ICON["audio"], ' aria-pressed="true"')
        + btn("mv-cc", "字幕", ICON["cc"], ' aria-pressed="true"')
        + '<label class="mv-speed" title="再生速度"><select id="mv-speed" aria-label="再生速度">'
        + "".join('<option value="%s"%s>%s×</option>' % (v, " selected" if v == "1" else "", v) for v in ["0.5", "0.75", "1", "1.25", "1.5", "2"])
        + '</select></label>'
        '<div class="mv-menuwrap">'
        + btn("mv-chapbtn", "チャプター", ICON["chapters"], ' aria-haspopup="true" aria-expanded="false" aria-controls="mv-chapmenu"')
        + '<div class="mv-menu" id="mv-chapmenu" hidden></div></div>'
        '<div class="mv-menuwrap">'
        + btn("mv-setbtn", "設定（字幕の大きさ・小窓・保存）", ICON["gear"], ' aria-haspopup="true" aria-expanded="false" aria-controls="mv-setpanel"')
        + '<div class="mv-menu mv-set" id="mv-setpanel" hidden>'
        '<div class="mv-setrow"><span>字幕の大きさ</span><span class="mv-seg3" role="group" aria-label="字幕の大きさ">'
        '<button type="button" data-cap="s">小</button><button type="button" data-cap="m">標準</button><button type="button" data-cap="l">大</button></span></div>'
        '<div class="mv-setrow"><span>音楽</span><span class="mv-seg3" role="group" aria-label="音楽">'
        '<button type="button" data-mus="1">入</button><button type="button" data-mus="0">切</button></span></div>'
        '<div class="mv-setrow"><span>効果音</span><span class="mv-seg3" role="group" aria-label="効果音">'
        '<button type="button" data-sfx="1">入</button><button type="button" data-sfx="0">切</button></span></div>'
        '<button type="button" class="mv-setitem" id="mv-pip">小窓で再生（ピクチャー・イン・ピクチャー）</button>'
        '<button type="button" class="mv-setitem" id="mv-rec">動画ファイル（WebM）で保存</button>'
        '<p class="mv-setnote">保存は最初から 1 倍速で再生して録画します（字幕は映像に焼き込み。読み上げの声は入りません）。</p>'
        '</div></div>'
        '</div></div>'
        + btn("mv-fs", "全画面", ICON["fs"])
        + '</div><div class="mv-note" id="mv-voicenote" hidden>この端末には読み上げの声が無いため、音声は効果音と音楽だけになります。</div>'
        '</div>')
    style = ("--c-bg:%s;--c-bg2:%s;--c-line:%s;--c-ink:%s;--c-muted:%s;--c-accent:%s"
             % (ch["bg"], ch["bg2"], ch["line"], ch["ink"], ch["muted"], ch["accent"]))
    data = json.dumps(spec, ensure_ascii=False).replace("</", "<\\/")
    frag = (
        '<section class="mv-player" id="mv-player" data-player="%s" tabindex="0" aria-label="%s" style="%s">'
        '<script type="application/json" data-mv-spec>%s</script><script type="application/json" data-mv-theme>%s</script>'
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
        '</section>' % (player, html.escape(title, quote=True), style, data, json.dumps(theme_js, ensure_ascii=False), ICON["big"] + '<span class="mv-biglabel"></span>', controls))
    # id はプレイヤーごとの名前にし、エンジンは data-mv で探す
    frag = re.sub(r'\bid="mv-([\w-]+)"', lambda m: 'data-mv="%s" id="%s-%s"' % (m.group(1), uid, m.group(1)), frag)
    frag = re.sub(r'aria-controls="mv-([\w-]+)"', lambda m: 'aria-controls="%s-%s"' % (uid, m.group(1)), frag)
    return frag


def player_css():
    """プレイヤーだけに効く CSS（ページの見た目には触れない。#mv-x は data-mv に読み替える）。"""
    return re.sub(r"#mv-([\w-]+)", r'[data-mv="\1"]', PLAYER_CSS)


def engine_js():
    """音の合成（audio.js）と描画・プレイヤー（engine.js）。どちらも 1 ページで 1 度だけ効く。"""
    return (open(os.path.join(HERE, "audio.js"), encoding="utf-8").read() + "\n"
            + open(os.path.join(HERE, "engine.js"), encoding="utf-8").read())


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
            '<kbd>M</kbd> 音声　<kbd>F</kbd> 全画面</p>')
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
    print("\n# 重ねの層（場面の overlays: [...]。座標は 1920×1080、at / until は場面の進み 0..1）")
    for k, (req, desc, ex) in OVERLAY_KINDS.items():
        print("  [%s] %s（必須: %s）\n    %s" % (k, desc, ", ".join(req), ex))
    print("\n# カメラ\n  " + CAMERA_DOC)
    print("\n# 表現のモード（台本の expression）")
    for k, d in EXPRESSIONS.items():
        print("  %-10s %s" % (k, d))
    print("\n# 台本の骨組み")
    print('  {"title":"…","description":"…","lang":"ja","player":"studio","theme":"navy-brass",'
          '"brand":{"name":"…"},"transition":"fade","poster":4300,'
          '"audio":{"narration":true,"music":"corporate","sfx":{"kit":"standard","density":"normal"},"rate":1.1,"wait":true,"pronounce":{"Sodashitsu":"ソダシツ"}},'
          '"expression":"mixed","chapters":[{"title":"章の名前","desc":"一覧に出す説明","scenes":[{…場面…}]}]}')
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
    ap.add_argument("--sounds", action="store_true", help="曲と効果音を聞き比べる HTML を作る（-o で出力先。既定 sounds.html）")
    args = ap.parse_args()
    if args.api:
        print(API_DOC)
        return
    if args.list_sounds:
        sound.print_sounds()
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
                for a, b, c in s["_cues"]:
                    print("        %s–%s  %s" % (fmt(t + a), fmt(t + b), c))
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
