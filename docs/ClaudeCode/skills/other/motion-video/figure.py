"""motion-video の部品を、プレイヤー無しの「動く図」として ほかの HTML（md-to-doc の文書）に置く。

    import figure
    html = figure.build_figure({"type": "bars", ...}, "daylight", "midnight", {"caption": "…", "loop": False}, base)
    page = ... + figure.runtime(has_engine=False)   # 1 ページに 1 度だけ（描画部・図の制御・CSS）

場面の台本は build.py の部品と同じ（--list の type。custom も書ける）。図は 16:9 の Canvas で、
画面に入ると最初から動き、最後のコマ（完成した図）で止まる。音・字幕・操作部は無い。
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import build as mv  # noqa: E402

LIGHT_THEMES = {"daylight", "paper", "mono"}

FIG_CSS = """
.mvfig{position:relative;margin:22px 0;max-width:100%}
.mvfig .mv-player{margin:0;border-radius:12px;border:1px solid var(--line,#d7dde6);box-shadow:none}
.mvfig .mv-controls,.mvfig .mv-big,.mvfig .mv-resume,.mvfig .mv-cap,.mvfig .mv-side,.mvfig .mv-note,.mvfig .mv-recbadge,.mvfig .mv-credit{display:none!important}
.mvfig .mv-stage{cursor:pointer}
.mvfig-replay{position:absolute;right:10px;top:10px;z-index:3;appearance:none;border:1px solid var(--line,#d7dde6);border-radius:999px;
  background:color-mix(in srgb,var(--surface,var(--bg,#fff)) 88%,transparent);color:var(--text,var(--ink,#1b2430));font:inherit;font-size:12.5px;
  padding:4px 12px;cursor:pointer;opacity:0;transition:opacity .2s}
.mvfig:hover .mvfig-replay,.mvfig.mvfig-done .mvfig-replay,.mvfig-replay:focus-visible{opacity:1}
.mvfig-replay:focus-visible{outline:2px solid var(--accent,#2f6fde);outline-offset:2px}
.mvfig figcaption{color:var(--muted,#5d6878);font-size:13px;margin-top:6px;text-align:center}
@media (prefers-reduced-motion:reduce){.mvfig-replay{display:none}}
@media print{.mvfig-replay{display:none}.mvfig{break-inside:avoid}}
"""


def theme_pair(key):
    """文書の配色に合う、明るい地と暗い地の映像の配色（キー）。"""
    key = key if key in mv.THEMES else "daylight"
    if key in LIGHT_THEMES:
        return key, ("navy-brass" if key == "paper" else "midnight")
    return "daylight", key


def _theme_js(key):
    th = mv.THEMES[key]
    return {"canvas": th["canvas"], "fonts": th["fonts"], "pattern": th["pattern"]}


def figure_spec(scene, opts=None):
    """1 場面だけの台本（音・字幕・章の見出しなし）。"""
    opts = opts or {}
    sc = dict(scene)
    if opts.get("duration") and "duration" not in sc:
        sc["duration"] = float(opts["duration"])
    sp = {"title": opts.get("caption") or sc.get("heading") or sc.get("title") or "図", "figure": True, "chrome": False,
          "audio": {"narration": False, "music": "none", "sfx": False}, "chapters": [{"title": "図", "scenes": [sc]}]}
    for k in ("motion", "ease", "order"):
        if opts.get(k):
            sp[k] = opts[k]
    return sp


def build_figure(scene, light_key, dark_key, opts=None, base="."):
    """動く図の HTML 断片。誤りがあれば (None, [エラー]) を返す。"""
    opts = opts or {}
    spec = figure_spec(scene, opts)
    errs = mv.validate(spec, base)
    if errs:
        return None, errs
    mv.plan(spec)
    spec["audio"]["_sfx"] = {}   # 図は音を鳴らさないので、効果音の定義（約 40 KB）を入れない
    frag = mv.build_fragment(spec, light_key, "minimal")
    # 図はプレイヤーとして操作させない（キー操作・フォーカスを受けない）。起動は figure.js が受け持つ
    # data-mv-ready: engine.js の自動起動の対象から外す（figure.js が起動する）
    frag = frag.replace(' tabindex="0"', " data-mv-ready", 1)
    themes = json.dumps({"light": _theme_js(light_key), "dark": _theme_js(dark_key)}, ensure_ascii=False).replace("</", "<\\/")
    cap = opts.get("caption") or ""
    width = opts.get("width") or ""
    style = ' style="max-width:%s;margin-left:auto;margin-right:auto"' % html.escape(width) if re.match(r"^\d+(\.\d+)?(%|px|em|rem)$", width) else ""
    label = cap or spec["title"]
    return ('<figure class="mvfig" data-loop="%s"%s role="group" aria-label="%s">'
            '<script type="application/json" data-mvfig-themes>%s</script>%s'
            '<button type="button" class="mvfig-replay" aria-label="図の動きをもう一度再生">↻ もう一度</button>%s</figure>'
            % ("1" if opts.get("loop") else "0", style, html.escape(label, quote=True), themes, frag,
               "<figcaption>%s</figcaption>" % html.escape(cap) if cap else "")), []


def runtime(has_engine=False):
    """ページに 1 度だけ置く: プレイヤーの CSS（図の分も）・描画部（has_engine なら省く）・図の制御。"""
    js = open(os.path.join(HERE, "figure.js"), encoding="utf-8").read()
    return ("<style>%s%s</style>%s<script>%s</script>"
            % ("" if has_engine else mv.player_css(), FIG_CSS,
               "" if has_engine else "<script>%s</script>" % mv.engine_js().replace("</script", "<\\/script"), js))
