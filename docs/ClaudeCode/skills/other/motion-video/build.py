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
    "custom": (["code"], "部品に無い絵を JS で描く（本体: (ctx, lt, d, H, s)。H に描画の道具）", '{"type":"custom","code":"H.txt(\\"Hello\\", 960, 540, {size:80, align:\\"center\\", alpha:H.P(lt,0,600)});","duration":5}'),
}
COMMON = "共通: narration（ナレーション＝字幕。文字列か配列）・duration（秒。省略時は自動）・heading・transition（fade|slide|zoom|cut）"

MIN_SEC = {"title": 8, "statement": 4.5, "bullets": 2.5, "flow": 3, "steps": 2, "terminal": 2.5, "stats": 4.5, "bars": 3.5,
           "compare": 3, "code": 2.5, "window": 7, "image": 5, "end": 4, "custom": 5}


def narration_text(s):
    n = s.get("narration") or ""
    return " ".join(n) if isinstance(n, list) else str(n)


def speech_seconds(text, lang):
    plain = re.sub(r"\*\*", "", text).strip()
    if not plain:
        return 0.0
    if lang.startswith("ja") or lang.startswith("zh"):
        chars = len(re.sub(r"\s", "", plain))
        return chars / 7.2
    return len(plain.split()) / 2.6


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
    warns = []
    for ci, ch in enumerate(spec["chapters"]):
        for si, s in enumerate(ch["scenes"]):
            text = narration_text(s)
            speech = speech_seconds(text, lang) / rate * 1.1
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
            total = sum(len(c) for c in cues) or 1
            acc, cl = a0, []
            for c in cues:
                span = (b0 - a0) * len(c) / total
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
            if t == "image" and s.get("src") and not re.match(r"^(data:|https?:)", s["src"]):
                p = os.path.join(base, s["src"])
                if not os.path.isfile(p):
                    errs.append("%s: 画像が見つかりません: %s" % (where, p))
                else:
                    mime = mimetypes.guess_type(p)[0] or "image/png"
                    s["src"] = "data:%s;base64,%s" % (mime, base64.b64encode(open(p, "rb").read()).decode("ascii"))
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
}

CSS = r"""
:root{--bg:#eef1f4;--ink:#131a22;--muted:#56616e;--line:#d3d9e0;--card:#ffffff;--focus:#1a56db}
@media (prefers-color-scheme:dark){:root{--bg:#0a0d12;--ink:#e6ebf1;--muted:#98a3b0;--line:#222a35;--card:#11161d;--focus:#6ea0ff;color-scheme:dark}}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0}
body{background:var(--bg);color:var(--ink);font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif;font-size:15px;line-height:1.7;padding:24px 16px 48px}
.mv-page{max-width:1120px;margin:0 auto;display:flex;flex-direction:column;gap:18px}
.mv-head h1{font-size:clamp(22px,3.4vw,32px);line-height:1.25;margin:0;text-wrap:balance}
.mv-head p{margin:6px 0 0;color:var(--muted);max-width:44em}
.mv-player{--c-bg:__BG__;--c-bg2:__BG2__;--c-line:__LINE__;--c-ink:__INK__;--c-muted:__MUTED__;--c-accent:__ACCENT__;
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
[data-player="studio"] .mv-side{display:block;padding:14px 18px;border-top:1px solid var(--c-line);background:var(--c-bg)}
[data-player="studio"] .mv-chaplist{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));column-gap:24px}
[data-player="studio"] .mv-chaplist li:nth-child(-n+3) button{border-top:0}
/* presenter: 横に目次 */
[data-player="presenter"]{display:grid;grid-template-columns:minmax(0,1fr) 300px}
[data-player="presenter"] .mv-side{display:block;border-left:1px solid var(--c-line);padding:14px 16px;background:var(--c-bg2);overflow:auto;max-height:100%}
@media(max-width:860px){[data-player="presenter"]{grid-template-columns:1fr}[data-player="presenter"] .mv-side{border-left:0;border-top:1px solid var(--c-line);max-height:none}}
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
"""


def build_html(spec, theme_key, player):
    th = THEMES[theme_key]
    ch = th["chrome"]
    css = (CSS.replace("__BG__", ch["bg"]).replace("__BG2__", ch["bg2"]).replace("__LINE__", ch["line"])
              .replace("__INK__", ch["ink"]).replace("__MUTED__", ch["muted"]).replace("__ACCENT__", ch["accent"]))
    theme_js = {"canvas": th["canvas"], "fonts": th["fonts"], "pattern": th["pattern"]}
    title = spec.get("title") or "動画"
    desc = spec.get("description") or ""
    minimal = player == "minimal"
    btn = lambda id_, label, icon, extra="": ('<button class="mv-btn" id="%s" type="button" aria-label="%s" title="%s"%s>%s</button>'
                                              % (id_, label, label, extra, icon))
    controls = (
        '<div class="mv-controls">'
        '<div class="mv-seek" id="mv-seek" role="slider" tabindex="0" aria-label="再生位置" aria-valuemin="0" aria-valuemax="0" aria-valuenow="0">'
        '<div class="mv-track" id="mv-track"></div><div class="mv-knob" id="mv-knob"></div><div class="mv-tip" id="mv-tip" hidden></div></div>'
        '<div class="mv-row">'
        + btn("mv-play", "再生", ICON["play"]) + btn("mv-stop", "停止して最初に戻る", ICON["stop"])
        + btn("mv-prev", "前のチャプター", ICON["prev"]) + btn("mv-next", "次のチャプター", ICON["next"])
        + '<span class="mv-time" id="mv-time"><b>0:00</b> / 0:00</span><span class="mv-chapname" id="mv-chapname"></span>'
        '<span class="mv-spacer"></span>'
        '<div class="mv-morewrap">'
        + btn("mv-more", "そのほかの操作（音声・字幕・速度・チャプター）", ICON["more"], ' aria-haspopup="true" aria-expanded="false" aria-controls="mv-morepanel"')
        + '<div class="mv-sec" id="mv-morepanel"%s>' % (" hidden" if minimal else "")
        + btn("mv-audio", "音声", ICON["audio"], ' aria-pressed="true"')
        + btn("mv-cc", "字幕", ICON["cc"], ' aria-pressed="true"')
        + '<label class="mv-speed" title="再生速度"><select id="mv-speed" aria-label="再生速度">'
        + "".join('<option value="%s"%s>%s×</option>' % (v, " selected" if v == "1" else "", v) for v in ["0.5", "0.75", "1", "1.25", "1.5", "2"])
        + '</select></label>'
        '<div class="mv-menuwrap">'
        + btn("mv-chapbtn", "チャプター", ICON["chapters"], ' aria-haspopup="true" aria-expanded="false" aria-controls="mv-chapmenu"')
        + '<div class="mv-menu" id="mv-chapmenu" hidden></div></div>'
        '</div></div>'
        + btn("mv-fs", "全画面", ICON["fs"])
        + '</div><div class="mv-note" id="mv-voicenote" hidden>この端末には読み上げの声が無いため、音声は効果音と音楽だけになります。</div>'
        '</div>')
    player_html = (
        '<section class="mv-player" id="mv-player" data-player="%s" tabindex="0" aria-label="%s">'
        '<div class="mv-main"><div class="mv-stage" id="mv-stage"><canvas id="mv-canvas" aria-hidden="true"></canvas>'
        '<div class="mv-cap"><span id="mv-captext" hidden></span></div>'
        '<button class="mv-big" id="mv-big" type="button" aria-label="再生">%s</button></div>%s</div>'
        '<aside class="mv-side" aria-label="チャプター"><h2>チャプター</h2><ol class="mv-chaplist" id="mv-chaplist"></ol></aside>'
        '</section>' % (player, html.escape(title, quote=True), ICON["big"], controls))
    head = '<header class="mv-head"><h1>%s</h1>%s</header>' % (html.escape(title), "<p>%s</p>" % html.escape(desc) if desc else "")
    keys = ('<p class="mv-keys"><kbd>Space</kbd> 再生・一時停止　<kbd>S</kbd> 停止　<kbd>←</kbd><kbd>→</kbd> 5 秒　'
            '<kbd>[</kbd><kbd>]</kbd> チャプター　<kbd>&lt;</kbd><kbd>&gt;</kbd> 速度　<kbd>C</kbd> 字幕　<kbd>M</kbd> 音声　<kbd>F</kbd> 全画面</p>')
    engine = open(os.path.join(HERE, "engine.js"), encoding="utf-8").read()
    data = json.dumps(spec, ensure_ascii=False).replace("</", "<\\/")
    return ("<!doctype html>\n<html lang=\"%s\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>%s</title>"
            "<style>%s</style></head><body><main class=\"mv-page\">%s%s%s</main>"
            "<script>window.__MV_SPEC__=%s;window.__MV_THEME__=%s;</script><script>%s</script></body></html>\n"
            % (html.escape(spec.get("lang", "ja")), html.escape(title), css, head, player_html,
               keys if player != "kiosk" else "", data, json.dumps(theme_js, ensure_ascii=False), engine))


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
    print("\n# 台本の骨組み")
    print('  {"title":"…","description":"…","lang":"ja","player":"studio","theme":"navy-brass",'
          '"brand":{"name":"…"},"transition":"fade","poster":4300,'
          '"audio":{"narration":true,"music":"calm|bright|deep|none","sfx":true,"rate":1.1,"pronounce":{"Sodashitsu":"ソダシツ"}},'
          '"chapters":[{"title":"章の名前","desc":"一覧に出す説明","scenes":[{…場面…}]}]}')


def main():
    ap = argparse.ArgumentParser(description="台本（JSON）から動画のように再生できる単一 HTML を作る")
    ap.add_argument("spec", nargs="?", help="台本の JSON")
    ap.add_argument("-o", "--out", help="出力 HTML（既定: 台本と同じ場所・同じ名前の .html）")
    ap.add_argument("--player", choices=list(PLAYERS), help="プレイヤー（台本の player を上書き）")
    ap.add_argument("--theme", choices=list(THEMES), help="配色テーマ（台本の theme を上書き）")
    ap.add_argument("--list", action="store_true", help="プレイヤー・配色・場面の部品と台本の書き方を出す")
    ap.add_argument("--timeline", action="store_true", help="HTML を作らず、場面の長さと字幕の時刻を出す")
    args = ap.parse_args()
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
    for w in warns:
        print("warn:", w, file=sys.stderr)
    total = sum(s["_dur"] for ch in spec["chapters"] for s in ch["scenes"])
    if args.timeline:
        t = 0
        for ci, ch in enumerate(spec["chapters"]):
            print("%s  第 %d 章 %s" % (fmt(t), ci + 1, ch["title"]))
            for s in ch["scenes"]:
                print("  %s  %-9s %5.1f 秒  %s" % (fmt(t), s["type"], s["_dur"] / 1000, (s.get("heading") or s.get("title") or "")[:30]))
                for a, b, c in s["_cues"]:
                    print("        %s–%s  %s" % (fmt(t + a), fmt(t + b), c))
                t += s["_dur"]
        print("合計 %s（%d 章・%d 場面）" % (fmt(total), len(spec["chapters"]), sum(len(c["scenes"]) for c in spec["chapters"])))
        return
    out = args.out or os.path.splitext(os.path.abspath(args.spec))[0] + ".html"
    open(out, "w", encoding="utf-8").write(build_html(spec, theme, player))
    print("OK : %s（%s・%s・%s）" % (out, player, theme, fmt(total)))


def fmt(ms):
    s = int(ms // 1000)
    return "%d:%02d" % (s // 60, s % 60)


if __name__ == "__main__":
    main()
