#!/usr/bin/env python3
"""md-to-doc: Markdown を視覚的に分かりやすい単一HTMLドキュメントに変換する。

- 5テーマ（CSS変数で切替）/ 出力モード single|print|site
- 各テーマにライト/ダーク両パレット。ヘッダーの切替ボタンで ライト/ダーク/システム設定 を選択
  （選択は localStorage に保存。既定はシステム設定に追従）
- 見出しからメニュー・目次を自動生成、固定ヘッダー＋スクロール連動ハイライト
- コールアウト( > [!NOTE] )、コードコピー、印刷/PDF対応
- mermaid は生成時に「選んだテーマの配色」でSVG化して埋め込む（mmdc があれば）。
  ライト用/ダーク用の2枚を描き、表示モードに応じてCSSで出し分ける。
  mmdc が無い場合はコードブロックにフォールバック。

stdlib のみで動作。Markdown はメモ用途に十分なサブセットを自前パース。
"""
import sys, os, re, html, json, math, argparse, subprocess, tempfile, shutil, datetime, base64

# ──────────────────────────────────────────────────────────────────────────
# テーマ定義
#   vars        : ライト時の CSS 変数（全キーを定義）
#   vars_dark   : ダーク時の上書き（vars のサブセットでよい）
#   accents     : カード等の循環配色。--a0..--aN として CSS 変数化される
#   accents_dark: ダーク時の循環配色（省略時は accents を流用。要素数は揃える）
#   mermaid /
#   mermaid_dark: mmdc の themeVariables（ライト/ダークで2枚描く）
#   default_mode: 初回表示（localStorage 未設定時）の既定 system|light|dark
# ──────────────────────────────────────────────────────────────────────────
THEMES = {
    "corporate": {
        "label": "モダンコーポレート",
        "default_mode": "system",
        "accents": ["#1a56db", "#0ea5e9", "#6366f1", "#0d9488"],
        "accents_dark": ["#5b9bff", "#38bdf8", "#8b8cf7", "#2dd4bf"],
        "vars": {
            "--bg": "#f7f9fc", "--card": "#ffffff", "--ink": "#1f2937",
            "--muted": "#6b7280", "--line": "#e5e7eb",
            "--accent": "#1a56db", "--accent-2": "#1e40af", "--accent-soft": "#eff4ff",
            "--on-accent": "#ffffff",
            "--code-bg": "#0f172a", "--code-fg": "#e2e8f0",
            "--radius": "14px", "--shadow": "0 1px 3px rgba(16,24,40,.06)",
            "--font": '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--font-head": '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "linear-gradient(135deg,#1a56db,#1e40af)",
            "--header-fg": "#ffffff",
        },
        "vars_dark": {
            "--bg": "#0e1420", "--card": "#161d2b", "--ink": "#e6ecf5",
            "--muted": "#9aa6b8", "--line": "#26303f",
            "--accent": "#5b9bff", "--accent-2": "#8fbcff", "--accent-soft": "#16213a",
            "--on-accent": "#0b1220",
            "--code-bg": "#080d16", "--code-fg": "#e2e8f0",
            "--shadow": "0 1px 3px rgba(0,0,0,.5)",
            "--header-bg": "linear-gradient(135deg,#16305e,#0f1c38)",
            "--header-fg": "#eaf1ff",
        },
        "mermaid": {
            "theme": "base",
            "themeVariables": {
                "primaryColor": "#eff4ff", "primaryBorderColor": "#1a56db",
                "primaryTextColor": "#1f2937", "lineColor": "#6b7280",
                "secondaryColor": "#dbeafe", "tertiaryColor": "#f7f9fc",
                "fontFamily": "Hiragino Kaku Gothic ProN, Yu Gothic, sans-serif",
            },
        },
        "mermaid_dark": {
            "theme": "dark",
            "themeVariables": {
                "primaryColor": "#16213a", "primaryBorderColor": "#5b9bff",
                "primaryTextColor": "#e6ecf5", "lineColor": "#9aa6b8",
                "secondaryColor": "#26303f", "tertiaryColor": "#0e1420",
                "background": "#0e1420",
                "fontFamily": "Hiragino Kaku Gothic ProN, Yu Gothic, sans-serif",
            },
        },
    },
    "darktech": {
        "label": "ダークテック",
        "default_mode": "dark",
        "accents": ["#0e7490", "#7c3aed", "#059669", "#db2777"],
        "accents_dark": ["#22d3ee", "#a78bfa", "#34d399", "#f472b6"],
        "vars": {
            "--bg": "#f5f8fb", "--card": "#ffffff", "--ink": "#101827",
            "--muted": "#5a6676", "--line": "#e3e9f0",
            "--accent": "#0e7490", "--accent-2": "#6d28d9", "--accent-soft": "#e6f7fb",
            "--on-accent": "#ffffff",
            "--code-bg": "#0e1420", "--code-fg": "#e5e9f0",
            "--radius": "12px", "--shadow": "0 1px 2px rgba(16,24,40,.06)",
            "--font": '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--font-head": '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "#ffffff",
            "--header-fg": "#101827",
        },
        "vars_dark": {
            "--bg": "#0b0f17", "--card": "#121826", "--ink": "#e5e9f0",
            "--muted": "#8b97a8", "--line": "#1f2937",
            "--accent": "#22d3ee", "--accent-2": "#a78bfa", "--accent-soft": "#0e1420",
            "--on-accent": "#06212a",
            "--code-bg": "#0e1420", "--code-fg": "#e5e9f0",
            "--shadow": "0 1px 0 rgba(255,255,255,.02)",
            "--header-bg": "#0b0f17",
            "--header-fg": "#e5e9f0",
        },
        "mermaid": {
            "theme": "base",
            "themeVariables": {
                "primaryColor": "#e6f7fb", "primaryBorderColor": "#0e7490",
                "primaryTextColor": "#101827", "lineColor": "#5a6676",
                "secondaryColor": "#e3e9f0", "tertiaryColor": "#f5f8fb",
                "fontFamily": "SFMono-Regular, Menlo, monospace",
            },
        },
        "mermaid_dark": {
            "theme": "dark",
            "themeVariables": {
                "primaryColor": "#121826", "primaryBorderColor": "#22d3ee",
                "primaryTextColor": "#e5e9f0", "lineColor": "#8b97a8",
                "secondaryColor": "#1f2937", "tertiaryColor": "#0e1420",
                "background": "#0b0f17",
                "fontFamily": "SFMono-Regular, Menlo, monospace",
            },
        },
    },
    "infographic": {
        "label": "インフォグラフィック",
        "default_mode": "system",
        "accents": ["#ff5d73", "#ffb13d", "#2ec4b6", "#5a7dff", "#a056ff"],
        "accents_dark": ["#ff7b8c", "#ffc46b", "#4fd6c7", "#7f9bff", "#b985ff"],
        "vars": {
            "--bg": "#fff7f2", "--card": "#ffffff", "--ink": "#23243a",
            "--muted": "#6c6f8a", "--line": "#f0e6de",
            "--accent": "#ff5d73", "--accent-2": "#5a7dff", "--accent-soft": "#fff0e8",
            "--on-accent": "#ffffff",
            "--code-bg": "#23243a", "--code-fg": "#f3f1ff",
            "--radius": "22px", "--shadow": "0 10px 28px rgba(40,30,60,.08)",
            "--font": '"Hiragino Maru Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--font-head": '"Hiragino Maru Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "linear-gradient(135deg,#ff5d73,#ffb13d)",
            "--header-fg": "#ffffff",
        },
        "vars_dark": {
            "--bg": "#181425", "--card": "#221d33", "--ink": "#f2eef8",
            "--muted": "#a79fbd", "--line": "#332b47",
            "--accent": "#ff7b8c", "--accent-2": "#7f9bff", "--accent-soft": "#2a2138",
            "--on-accent": "#2a121a",
            "--code-bg": "#120f1c", "--code-fg": "#f3f1ff",
            "--shadow": "0 10px 28px rgba(0,0,0,.45)",
            "--header-bg": "linear-gradient(135deg,#c9394f,#c47a1f)",
            "--header-fg": "#fff5ee",
        },
        "mermaid": {
            "theme": "base",
            "themeVariables": {
                "primaryColor": "#ffe3ea", "primaryBorderColor": "#ff5d73",
                "primaryTextColor": "#23243a", "lineColor": "#5a7dff",
                "secondaryColor": "#dcf4e9", "tertiaryColor": "#fff7f2",
                "fontFamily": "Hiragino Maru Gothic ProN, sans-serif",
            },
        },
        "mermaid_dark": {
            "theme": "dark",
            "themeVariables": {
                "primaryColor": "#2a2138", "primaryBorderColor": "#ff7b8c",
                "primaryTextColor": "#f2eef8", "lineColor": "#7f9bff",
                "secondaryColor": "#332b47", "tertiaryColor": "#181425",
                "background": "#181425",
                "fontFamily": "Hiragino Maru Gothic ProN, sans-serif",
            },
        },
    },
    "editorial": {
        "label": "エディトリアル",
        "default_mode": "system",
        "accents": ["#8b1e3f", "#a8814e", "#3f6b5e", "#5b4b8a"],
        "accents_dark": ["#e3849f", "#d3b483", "#7fb3a1", "#a294d8"],
        "vars": {
            "--bg": "#fbfaf7", "--card": "#ffffff", "--ink": "#1a1a1a",
            "--muted": "#555555", "--line": "#dddddd",
            "--accent": "#8b1e3f", "--accent-2": "#8b1e3f", "--accent-soft": "#f6eef1",
            "--on-accent": "#ffffff",
            "--code-bg": "#1a1a1a", "--code-fg": "#f5f5f5",
            "--radius": "4px", "--shadow": "none",
            "--font": '"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif',
            "--font-head": '"Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "#fbfaf7",
            "--header-fg": "#1a1a1a",
        },
        "vars_dark": {
            "--bg": "#14120f", "--card": "#1c1a17", "--ink": "#efece6",
            "--muted": "#a9a49b", "--line": "#332f2a",
            "--accent": "#e3849f", "--accent-2": "#e9a2b6", "--accent-soft": "#2a2124",
            "--on-accent": "#241419",
            "--code-bg": "#0e0d0b", "--code-fg": "#f5f5f5",
            "--shadow": "none",
            "--header-bg": "#14120f",
            "--header-fg": "#efece6",
        },
        "mermaid": {
            "theme": "neutral",
            "themeVariables": {
                "primaryColor": "#f6eef1", "primaryBorderColor": "#8b1e3f",
                "primaryTextColor": "#1a1a1a", "lineColor": "#555555",
                "secondaryColor": "#eeeeee", "tertiaryColor": "#fbfaf7",
                "fontFamily": "Hiragino Mincho ProN, serif",
            },
        },
        "mermaid_dark": {
            "theme": "dark",
            "themeVariables": {
                "primaryColor": "#2a2124", "primaryBorderColor": "#e3849f",
                "primaryTextColor": "#efece6", "lineColor": "#a9a49b",
                "secondaryColor": "#332f2a", "tertiaryColor": "#14120f",
                "background": "#14120f",
                "fontFamily": "Hiragino Mincho ProN, serif",
            },
        },
    },
    "pastel": {
        "label": "やわらかパステル",
        "default_mode": "system",
        "accents": ["#ff9eb5", "#ffd6a5", "#b8e6d0", "#a7d8f0", "#d4c5f9"],
        "accents_dark": ["#f2a9bd", "#e9c08a", "#8fd6bb", "#8fc7e8", "#bda9ef"],
        "vars": {
            "--bg": "#fef6fb", "--card": "#ffffff", "--ink": "#4a4458",
            "--muted": "#8a8499", "--line": "#f1e7f3",
            "--accent": "#ff9eb5", "--accent-2": "#a7d8f0", "--accent-soft": "#fff0f6",
            "--on-accent": "#ffffff",
            "--code-bg": "#4a4458", "--code-fg": "#fdf2f8",
            "--radius": "26px", "--shadow": "0 12px 30px rgba(150,120,180,.10)",
            "--font": '"Hiragino Maru Gothic ProN","Yu Gothic Medium",system-ui,sans-serif',
            "--font-head": '"Hiragino Maru Gothic ProN","Yu Gothic Medium",system-ui,sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "linear-gradient(135deg,#ff9eb5,#d4c5f9)",
            "--header-fg": "#ffffff",
        },
        "vars_dark": {
            "--bg": "#1c1826", "--card": "#262133", "--ink": "#f0e9f5",
            "--muted": "#a99fb8", "--line": "#352e44",
            "--accent": "#f2a9bd", "--accent-2": "#8fc7e8", "--accent-soft": "#2e2739",
            "--on-accent": "#26131c",
            "--code-bg": "#15111e", "--code-fg": "#fdf2f8",
            "--shadow": "0 12px 30px rgba(0,0,0,.40)",
            "--header-bg": "linear-gradient(135deg,#a9556c,#6a5a99)",
            "--header-fg": "#fdf1f7",
        },
        "mermaid": {
            "theme": "base",
            "themeVariables": {
                "primaryColor": "#ffe3ea", "primaryBorderColor": "#ff9eb5",
                "primaryTextColor": "#4a4458", "lineColor": "#a7d8f0",
                "secondaryColor": "#dcf4e9", "tertiaryColor": "#fef6fb",
                "fontFamily": "Hiragino Maru Gothic ProN, sans-serif",
            },
        },
        "mermaid_dark": {
            "theme": "dark",
            "themeVariables": {
                "primaryColor": "#2e2739", "primaryBorderColor": "#f2a9bd",
                "primaryTextColor": "#f0e9f5", "lineColor": "#8fc7e8",
                "secondaryColor": "#352e44", "tertiaryColor": "#1c1826",
                "background": "#1c1826",
                "fontFamily": "Hiragino Maru Gothic ProN, sans-serif",
            },
        },
    },
}

# ──────────────────────────────────────────────────────────────────────────
# 追加のテーマ（色だけでなく、見出し・罫線・密度・地の模様まで変える）
#   extra_css は共通の CSS の後に出す（テーマの個性が共通の見た目より優先される）。
#   mermaid の配色はテーマの色から導く。
# ──────────────────────────────────────────────────────────────────────────
_GOTHIC = '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif'
_MINCHO = '"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif'
_MONO = '"SFMono-Regular",Menlo,Consolas,monospace'
_UD = '"BIZ UDPGothic","Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif'


def _mermaid_from(v, dark):
    return {
        "theme": "dark" if dark else "base",
        "themeVariables": dict({
            "primaryColor": v["--accent-soft"], "primaryBorderColor": v["--accent"],
            "primaryTextColor": v["--ink"], "lineColor": v["--muted"],
            "secondaryColor": v["--line"], "tertiaryColor": v["--bg"],
            "fontFamily": v["--font"].replace('"', ""),
        }, **({"background": v["--bg"]} if dark else {})),
    }


def _theme(label, default_mode, accents, accents_dark, light, dark, extra=""):
    dark_full = dict(light)
    dark_full.update(dark)
    return {"label": label, "default_mode": default_mode, "accents": accents, "accents_dark": accents_dark,
            "vars": light, "vars_dark": dark, "extra_css": extra,
            "mermaid": _mermaid_from(light, False), "mermaid_dark": _mermaid_from(dark_full, True)}


# 見出しの番号付け（formal: 1. / 1.1、manual: 札の 1 / 1-1）
_NUMBERED = """
.content{counter-reset:h2}
.content h2.hl{counter-increment:h2;counter-reset:h3}
.content h3.hl{counter-increment:h3}
"""

THEMES.update({
    "formal": _theme(
        "フォーマル", "system",
        ["#1f3a68", "#5b6b7f", "#8a6d3b", "#3f5f4f"], ["#9fb6de", "#aab4c2", "#d4b37a", "#8fbfa6"],
        {"--bg": "#ffffff", "--card": "#ffffff", "--ink": "#111111", "--muted": "#555555", "--line": "#cfcfcf",
         "--accent": "#1f3a68", "--accent-2": "#1f3a68", "--accent-soft": "#eef1f6", "--on-accent": "#ffffff",
         "--code-bg": "#1b1f27", "--code-fg": "#e6e6e6", "--radius": "0px", "--shadow": "none",
         "--font": _GOTHIC, "--font-head": _MINCHO, "--mono": _MONO,
         "--header-bg": "#ffffff", "--header-fg": "#111111"},
        {"--bg": "#121416", "--card": "#181b1f", "--ink": "#e8e8e8", "--muted": "#a0a4aa", "--line": "#2e3238",
         "--accent": "#9fb6de", "--accent-2": "#b9cbe9", "--accent-soft": "#1c2230", "--on-accent": "#0f1420",
         "--code-bg": "#0c0e11", "--code-fg": "#e6e6e6", "--header-bg": "#121416", "--header-fg": "#e8e8e8"},
        _NUMBERED + """
.content h2.hl{border-left:0;padding-left:0;padding-bottom:8px;border-bottom:3px double var(--ink);color:var(--ink);font-size:22px}
.content h2.hl::before{content:counter(h2) ".";margin-right:.6em;color:var(--accent)}
.content h3.hl::before{content:counter(h2) "." counter(h3);margin-right:.6em;color:var(--accent)}
.hero{border-bottom:3px double var(--ink)}
.hero h1{font-weight:700;letter-spacing:.04em}
table{box-shadow:none;border-radius:0}
th,td{border:1px solid var(--line)}
th{color:var(--ink)}
.doc-card,.stat,.tabs,.checklist,.defs,.tree,.pc-col,.accordion,.callout,.mermaid-fig{box-shadow:none}
.doc-card{border-top-width:2px}
.tl-dot{border-radius:0}
"""),
    "manual": _theme(
        "マニュアル", "system",
        ["#d9480f", "#2563eb", "#0f766e", "#7c3aed"], ["#ff8a4c", "#6ea1ff", "#2dd4bf", "#b196ff"],
        {"--bg": "#f3f4f6", "--card": "#ffffff", "--ink": "#1c1f24", "--muted": "#5b616b", "--line": "#d7dbe0",
         "--accent": "#d9480f", "--accent-2": "#b03a0b", "--accent-soft": "#fff1e8", "--on-accent": "#ffffff",
         "--code-bg": "#1e2227", "--code-fg": "#e6e8eb", "--radius": "6px", "--shadow": "0 1px 2px rgba(0,0,0,.06)",
         "--font": _GOTHIC, "--font-head": _GOTHIC, "--mono": _MONO,
         "--header-bg": "#2b2f36", "--header-fg": "#ffffff"},
        {"--bg": "#15171a", "--card": "#1d2024", "--ink": "#e7e9ec", "--muted": "#9aa1ab", "--line": "#30343a",
         "--accent": "#ff8a4c", "--accent-2": "#ffb088", "--accent-soft": "#2a1d15", "--on-accent": "#1a0f08",
         "--code-bg": "#101214", "--code-fg": "#e6e8eb", "--header-bg": "#0f1113", "--header-fg": "#e7e9ec",
         "--shadow": "none"},
        _NUMBERED + """
body{line-height:1.7}
.content{font-size:15px}
.content h2.hl{border:1px solid var(--line);border-top:4px solid var(--accent);background:var(--card);padding:8px 14px;
  color:var(--ink);font-size:21px;margin-top:36px}
.content h2.hl::before{content:counter(h2);display:inline-block;min-width:1.7em;margin-right:.6em;padding:0 .4em;border-radius:4px;
  background:var(--accent);color:var(--on-accent);text-align:center;font-size:.85em}
.content h3.hl::before{content:counter(h2) "-" counter(h3);color:var(--accent);margin-right:.5em}
.content p{margin:8px 0}
.callout{border-left-width:6px}
.callout-head{font-size:15px}
.tl-dot{border-radius:8px}
"""),
    "contrast": _theme(
        "高コントラスト", "system",
        ["#0033aa", "#8a0000", "#005a1e", "#5a1a8a"], ["#ffd400", "#7fd4ff", "#9dff7a", "#ff9ecb"],
        {"--bg": "#ffffff", "--card": "#ffffff", "--ink": "#000000", "--muted": "#333333", "--line": "#6b6b6b",
         "--accent": "#0033aa", "--accent-2": "#002277", "--accent-soft": "#e8eeff", "--on-accent": "#ffffff",
         "--code-bg": "#000000", "--code-fg": "#ffffff", "--radius": "8px", "--shadow": "none",
         "--font": _UD, "--font-head": _UD, "--mono": '"BIZ UDGothic",Consolas,Menlo,monospace',
         "--header-bg": "#000000", "--header-fg": "#ffffff"},
        {"--bg": "#000000", "--card": "#0a0a0a", "--ink": "#ffffff", "--muted": "#d6d6d6", "--line": "#9a9a9a",
         "--accent": "#ffd400", "--accent-2": "#ffe766", "--accent-soft": "#1f1a00", "--on-accent": "#000000",
         "--code-bg": "#111111", "--code-fg": "#ffffff", "--header-bg": "#000000", "--header-fg": "#ffffff"},
        """
body{font-size:17px;line-height:1.9}
.content a{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px;border-bottom:0}
:focus-visible{outline:3px solid var(--accent)!important;outline-offset:3px}
.content h2.hl{color:var(--ink);border-left-width:8px}
th{color:var(--ink)}
.doc-card-tags span,.chip{color:var(--ink)!important}
table,.doc-card,.stat,.tabs,.checklist,.defs,.tree,.pc-col,.accordion,.callout,.mermaid-fig{border-width:2px}
"""),
    "blueprint": _theme(
        "ブループリント", "system",
        ["#1d4e89", "#0f7c8c", "#b45309", "#6d28d9"], ["#7fb2ff", "#4fd1e0", "#f5b454", "#b69cff"],
        {"--bg": "#f4f7fb", "--card": "#ffffff", "--ink": "#0f2540", "--muted": "#4b6584", "--line": "#c5d3e6",
         "--accent": "#1d4e89", "--accent-2": "#163a66", "--accent-soft": "#e7eef8", "--on-accent": "#ffffff",
         "--code-bg": "#0f2540", "--code-fg": "#dbe7f6", "--radius": "2px", "--shadow": "none",
         "--font": _GOTHIC, "--font-head": _MONO.replace("monospace", '"Hiragino Kaku Gothic ProN",monospace'), "--mono": _MONO,
         "--header-bg": "repeating-linear-gradient(0deg,rgba(255,255,255,.09) 0 1px,transparent 1px 24px),"
                        "repeating-linear-gradient(90deg,rgba(255,255,255,.09) 0 1px,transparent 1px 24px),#163a66",
         "--header-fg": "#ffffff"},
        {"--bg": "#0b1a2e", "--card": "#0f2238", "--ink": "#dbe7f6", "--muted": "#8fa7c4", "--line": "#23405f",
         "--accent": "#7fb2ff", "--accent-2": "#a9ccff", "--accent-soft": "#12294a", "--on-accent": "#07162a",
         "--code-bg": "#07121f", "--code-fg": "#dbe7f6",
         "--header-bg": "repeating-linear-gradient(0deg,rgba(127,178,255,.08) 0 1px,transparent 1px 24px),"
                        "repeating-linear-gradient(90deg,rgba(127,178,255,.08) 0 1px,transparent 1px 24px),#0f2238",
         "--header-fg": "#dbe7f6"},
        """
body{background-image:linear-gradient(color-mix(in srgb,var(--accent) 7%,transparent) 1px,transparent 1px),
  linear-gradient(90deg,color-mix(in srgb,var(--accent) 7%,transparent) 1px,transparent 1px);background-size:24px 24px}
.content h2.hl{border-left:0;padding-left:0;padding-bottom:6px;border-bottom:1px dashed var(--accent);letter-spacing:.02em}
.content h2.hl::before{content:"// ";color:var(--muted)}
.mermaid-fig{border:1px solid var(--accent);box-shadow:none;background-color:var(--card);
  background-image:linear-gradient(color-mix(in srgb,var(--accent) 6%,transparent) 1px,transparent 1px),
  linear-gradient(90deg,color-mix(in srgb,var(--accent) 6%,transparent) 1px,transparent 1px);background-size:16px 16px}
.doc-card,.stat,.tabs,.checklist,.defs,.tree,.pc-col,.accordion{box-shadow:none}
@media print{body,.mermaid-fig{background-image:none}}
"""),
    "minimal": _theme(
        "ミニマル", "system",
        ["#2f6feb", "#6e6e73", "#0f766e", "#b45309"], ["#6ea0ff", "#a1a1a6", "#2dd4bf", "#f5b454"],
        {"--bg": "#ffffff", "--card": "#ffffff", "--ink": "#1d1d1f", "--muted": "#6e6e73", "--line": "#e6e6e6",
         "--accent": "#2f6feb", "--accent-2": "#1d1d1f", "--accent-soft": "#f4f4f2", "--on-accent": "#ffffff",
         "--code-bg": "#f6f6f4", "--code-fg": "#37352f", "--radius": "6px", "--shadow": "none",
         "--font": _GOTHIC, "--font-head": _GOTHIC, "--mono": _MONO,
         "--header-bg": "#ffffff", "--header-fg": "#1d1d1f"},
        {"--bg": "#191919", "--card": "#202020", "--ink": "#e9e9e7", "--muted": "#9b9a97", "--line": "#2f2f2f",
         "--accent": "#6ea0ff", "--accent-2": "#e9e9e7", "--accent-soft": "#252525", "--on-accent": "#0d0d0d",
         "--code-bg": "#252525", "--code-fg": "#e9e9e7", "--header-bg": "#191919", "--header-fg": "#e9e9e7"},
        """
.content h2.hl{border-left:0;padding-left:0;padding-bottom:6px;border-bottom:1px solid var(--line);color:var(--ink);font-size:22px;font-weight:700}
.content h3.hl{font-weight:700}
.hero{border-bottom:1px solid var(--line);padding-bottom:36px}
.hero h1{font-weight:700}
.doc-card{border-top-width:1px}
.copy-btn{background:var(--card);color:var(--muted);border-color:var(--line)}
.copy-btn:hover{background:var(--accent-soft)}
.codeblock pre{border:1px solid var(--line)}
th{color:var(--ink);background:var(--accent-soft)}
"""),
    "paper": _theme(
        "紙（セピア）", "system",
        ["#7a4a1e", "#5f6f3a", "#8a3b3b", "#3f5f73"], ["#d9a066", "#b5c47a", "#e39a8f", "#9dbbd0"],
        {"--bg": "#f6f1e7", "--card": "#fbf8f1", "--ink": "#3b2f24", "--muted": "#7a6a58", "--line": "#e2d7c5",
         "--accent": "#7a4a1e", "--accent-2": "#5c3714", "--accent-soft": "#efe4d2", "--on-accent": "#fbf8f1",
         "--code-bg": "#3b2f24", "--code-fg": "#f3eadb", "--radius": "10px", "--shadow": "none",
         "--font": _GOTHIC, "--font-head": _MINCHO, "--mono": _MONO,
         "--header-bg": "#efe4d2", "--header-fg": "#3b2f24"},
        {"--bg": "#1e1a15", "--card": "#25201a", "--ink": "#e9dfcf", "--muted": "#b3a58f", "--line": "#3a3128",
         "--accent": "#d9a066", "--accent-2": "#e8bd8d", "--accent-soft": "#2e261d", "--on-accent": "#1e1a15",
         "--code-bg": "#16130f", "--code-fg": "#e9dfcf", "--header-bg": "#25201a", "--header-fg": "#e9dfcf"},
        """
:root{--maxw:940px}
body{line-height:2;font-size:16.5px}
.content p{margin:16px 0}
.content h2.hl{border-left:0;padding-left:0;font-size:24px;font-weight:700}
.content h2.hl::after{content:"";display:block;width:48px;height:2px;background:var(--accent);margin-top:10px}
.hero h1{font-weight:700}
"""),
})

# さらに追加のテーマ（発表・紹介向けの「オーロラ」と、落ち着いた社内資料の「ノルディック」）
THEMES.update({
    "aurora": _theme(
        "オーロラ", "dark",
        ["#6d28d9", "#0e7490", "#be185d", "#047857"], ["#a78bfa", "#22d3ee", "#f472b6", "#34d399"],
        {"--bg": "#f6f5ff", "--card": "rgba(255,255,255,.9)", "--ink": "#1e1b3a", "--muted": "#5f5b7d", "--line": "#e1def5",
         "--accent": "#6d28d9", "--accent-2": "#4c1d95", "--accent-soft": "#efe9ff", "--on-accent": "#ffffff",
         "--code-bg": "#17142e", "--code-fg": "#e9e5ff", "--radius": "18px", "--shadow": "0 10px 30px rgba(76,29,149,.10)",
         "--font": _GOTHIC, "--font-head": _GOTHIC, "--mono": _MONO,
         "--header-bg": "radial-gradient(120% 140% at 10% 0%,#22d3ee 0%,transparent 45%),radial-gradient(120% 140% at 90% 10%,#f472b6 0%,transparent 50%),linear-gradient(135deg,#4c1d95,#1e1b4b)",
         "--header-fg": "#ffffff"},
        {"--bg": "#0b0a1a", "--card": "rgba(26,23,52,.92)", "--ink": "#ece9ff", "--muted": "#a7a2c9", "--line": "#2c2752",
         "--accent": "#a78bfa", "--accent-2": "#c4b5fd", "--accent-soft": "#1f1a44", "--on-accent": "#140f2e",
         "--code-bg": "#07061a", "--code-fg": "#e9e5ff", "--shadow": "0 10px 30px rgba(0,0,0,.45)",
         "--header-bg": "radial-gradient(120% 140% at 10% 0%,rgba(34,211,238,.55) 0%,transparent 45%),radial-gradient(120% 140% at 90% 10%,rgba(244,114,182,.5) 0%,transparent 50%),linear-gradient(135deg,#2e1065,#0b0a1a)",
         "--header-fg": "#f5f3ff"},
        """
.doc-card,.stat,.tabs,.checklist,.defs,.tree,.pc-col,.accordion,.mermaid-fig,.sy-sticky,.sy-card,.callout,.fk-tip{backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
.content h2.hl{border-left:0;padding-left:0;background:linear-gradient(90deg,var(--a0),var(--a1),var(--a2));-webkit-background-clip:text;background-clip:text;color:transparent;font-weight:800}
.content h2.hl .anchor{-webkit-text-fill-color:var(--muted)}
@media print{.content h2.hl{color:var(--accent);background:none}}
"""),
    "nordic": _theme(
        "ノルディック", "system",
        ["#3b6e8f", "#a0673c", "#5f8a5a", "#8a6fa8"], ["#8cc0e0", "#e0a676", "#9cc795", "#c4aee0"],
        {"--bg": "#f3f4f1", "--card": "#ffffff", "--ink": "#2b3036", "--muted": "#6b737b", "--line": "#dfe2dc",
         "--accent": "#3b6e8f", "--accent-2": "#2c5470", "--accent-soft": "#e8f0f4", "--on-accent": "#ffffff",
         "--code-bg": "#2b3036", "--code-fg": "#eef1ec", "--radius": "10px", "--shadow": "0 1px 2px rgba(43,48,54,.06)",
         "--font": _GOTHIC, "--font-head": _GOTHIC, "--mono": _MONO,
         "--header-bg": "linear-gradient(180deg,#e7ebe5,#dfe5df)",
         "--header-fg": "#2b3036"},
        {"--bg": "#1c2024", "--card": "#242a2f", "--ink": "#e7eae6", "--muted": "#a2aab0", "--line": "#353d44",
         "--accent": "#8cc0e0", "--accent-2": "#b5d7ec", "--accent-soft": "#24323c", "--on-accent": "#13212b",
         "--code-bg": "#15181b", "--code-fg": "#e7eae6", "--shadow": "0 1px 2px rgba(0,0,0,.4)",
         "--header-bg": "linear-gradient(180deg,#262c31,#20252a)",
         "--header-fg": "#e7eae6"},
        """
body{line-height:1.95}
.content h2.hl{border-left:0;padding-left:0;font-weight:700;letter-spacing:.04em}
.content h2.hl::after{content:"";display:block;width:28px;height:3px;border-radius:2px;background:var(--a1);margin-top:8px}
.doc-card,.stat,.mermaid-fig,.sy-sticky,.sy-card{border-color:var(--line);box-shadow:none}
"""),
})

# テーマの一覧（選ばせるときの材料。label は THEMES 側）
THEME_INFO = {
    "corporate": ("青基調・カード・万人向け", "資料・報告・社内共有の既定"),
    "darktech": ("暗背景＋シアン/パープル", "エンジニア向けの技術資料"),
    "infographic": ("カラフル・丸ゴシック", "インパクト重視の紹介・広報"),
    "editorial": ("明朝・余白・読み物風", "コラム・解説・読み物"),
    "pastel": ("丸み・淡色", "社内の親しみやすい共有"),
    "formal": ("白と墨＋紺・罫線・見出しに 1. / 1.1 の番号", "報告書・稟議・規程・提案書（印刷が最も整う）"),
    "manual": ("灰色の地＋オレンジ・詰めた組み・見出しに番号の札", "手順書・運用手順・トラブル対応"),
    "contrast": ("大きな文字・高コントラスト・太い下線のリンク", "社外公開・全社向け・読みやすさ最優先"),
    "blueprint": ("方眼の地に紺・等幅の見出し・製図風の図枠", "設計書・仕様書・アーキテクチャ説明"),
    "minimal": ("黒い文字と余白・細い罫線・影なし", "社内メモ・議事録・ナレッジ"),
    "paper": ("生成りの紙色・焦げ茶・広い行間", "長文の読み物・解説・研修資料"),
    "aurora": ("深い紫の地にオーロラの光・すりガラスのカード・グラデーションの見出し", "発表・製品紹介・イベント（画面で見せる）"),
    "nordic": ("灰みの地に青と木の色・静かな見出し・広い行間", "落ち着いた社内資料・方針・ナレッジ"),
}


def theme_extra_css(theme_key):
    return THEMES[theme_key].get("extra_css", "")


COLOR_MODES = ["system", "light", "dark"]
MODE_STORAGE_KEY = "md2doc-color-mode"


def _vars_block(vars_map, accents, scheme, indent="  "):
    out = ["%scolor-scheme:%s;" % (indent, scheme)]
    out += ["%s%s:%s;" % (indent, k, v) for k, v in vars_map.items()]
    out += ["%s--a%d:%s;" % (indent, i, c) for i, c in enumerate(accents)]
    return "\n".join(out)


def theme_css(theme_key):
    """:root（ライト）＋ ダーク上書き（OS設定 / 明示指定）を生成。

    セレクタ順が効く: prefers-color-scheme のダークは data-theme="light" を除外し、
    末尾の [data-theme="light"] が全変数を再定義してライトへ確実に戻す。
    """
    t = THEMES[theme_key]
    light, dark = t["vars"], t["vars_dark"]
    la = t["accents"]
    da = t.get("accents_dark") or la
    lb = _vars_block(light, la, "light")
    db = _vars_block(dark, da, "dark")
    return "\n".join([
        ":root{\n%s\n  --nav-h:60px; --maxw:1080px;\n}" % lb,
        '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){\n%s\n}}' % db,
        ':root[data-theme="dark"]{\n%s\n}' % db,
        ':root[data-theme="light"]{\n%s\n}' % lb,
        # 印刷はモードを問わずライト配色（紙に暗背景を刷らない）
        '@media print{:root,:root[data-theme="dark"],:root[data-theme="light"]{\n%s\n}}' % lb,
    ])


def accent_vars(theme_key):
    """カード等の循環配色を CSS 変数参照で返す（hex 直書きだとモード切替で追従しないため）。"""
    return ["var(--a%d)" % i for i in range(len(THEMES[theme_key]["accents"]))]


def default_mode_of(theme_key, override=None):
    return override or THEMES[theme_key].get("default_mode", "system")

CALLOUT_LABELS = {
    "NOTE": ("ノート", "ℹ️"), "TIP": ("ヒント", "💡"),
    "IMPORTANT": ("重要", "❗"), "WARNING": ("注意", "⚠️"),
    "CAUTION": ("警告", "🚫"),
}

# ──────────────────────────────────────────────────────────────────────────
# インライン記法
# ──────────────────────────────────────────────────────────────────────────
# 画像の扱い。convert_file が処理対象 md のディレクトリ・出力先・モードを設定する。
#   _IMG_MODE = "embed" … ローカル画像を data URI で埋め込む（単一HTMLで自己完結）
#   _IMG_MODE = "link"  … ローカル画像は外部フォルダ参照のまま（出力HTMLからの相対パス）
_IMG_BASE = None     # 処理対象 md のディレクトリ（相対パス解決の基準）
_IMG_OUTDIR = None   # 出力HTMLのディレクトリ（link 時の相対パス起点）
_IMG_MODE = "embed"
_IMG_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
             "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp",
             "bmp": "image/bmp", "ico": "image/x-icon", "avif": "image/avif"}


def _rel_src(fp):
    """出力HTMLのディレクトリから画像ファイルへの参照用パスを作る（link モード用）。
    可能なら相対パス、無理（別ドライブ等）なら絶対パス。区切りは / に統一し URL エンコードする。"""
    import urllib.parse
    base = _IMG_OUTDIR or os.path.dirname(fp)
    try:
        rel = os.path.relpath(fp, base)
    except ValueError:
        rel = os.path.abspath(fp)
    rel = rel.replace(os.sep, "/")
    # 各パスセグメントを個別に URL エンコード（"/" は残す）
    return "/".join(urllib.parse.quote(seg) for seg in rel.split("/"))


def image_tag(alt_escaped, src_escaped):
    """![alt](src) を <img> に変換。ローカル画像は _IMG_MODE に従い
    data URI 埋め込み（embed）または外部フォルダ参照（link）にする。
    引数は inline() 内で html.escape 済みの文字列。src はファイル探索のため一旦復元する。"""
    import urllib.parse
    alt_attr = alt_escaped.replace('"', "&quot;")
    src = html.unescape(src_escaped).strip()
    # 末尾のタイトル指定 ![alt](src "title") を除去
    m = re.match(r'^(.*?)\s+["\'].*["\']$', src)
    if m:
        src = m.group(1).strip()
    # 外部URL / 既に data URI はそのまま
    if re.match(r"^(?:[a-zA-Z][\w+.-]*:)?//", src) or src.startswith("data:"):
        return '<img class="md-img" src="%s" alt="%s" loading="lazy">' % (
            html.escape(src, quote=True), alt_attr)
    # ローカル相対パス → md のディレクトリ基準で解決
    if _IMG_BASE:
        p = urllib.parse.unquote(src)
        fp = os.path.normpath(os.path.join(_IMG_BASE, p))
        if os.path.isfile(fp):
            if _IMG_MODE == "link":
                # 外部フォルダ参照: 出力HTMLからの相対パスで参照（埋め込まない）
                return '<img class="md-img" src="%s" alt="%s" loading="lazy">' % (
                    html.escape(_rel_src(fp), quote=True), alt_attr)
            # embed: base64 の data URI で埋め込み
            ext = os.path.splitext(fp)[1].lower().lstrip(".")
            mime = _IMG_MIME.get(ext, "application/octet-stream")
            try:
                with open(fp, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                return '<img class="md-img" src="data:%s;base64,%s" alt="%s" loading="lazy">' % (
                    mime, b64, alt_attr)
            except OSError:
                pass
    # 見つからない場合は相対 src のまま（少なくともリンク切れとして把握できる）
    return '<img class="md-img" src="%s" alt="%s" loading="lazy">' % (
        html.escape(src, quote=True), alt_attr)


def inline(text):
    out = []
    i = 0
    # コードスパンを先に退避
    parts = re.split(r"(`[^`]+`)", text)
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            out.append("<code>%s</code>" % html.escape(part[1:-1]))
            continue
        s = html.escape(part)
        # 画像 ![alt](src) はリンクより先に処理（先頭の ! を取りこぼさないため）
        s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                   lambda m: image_tag(m.group(1), m.group(2)), s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                   lambda m: '<a href="%s">%s</a>' % (html.escape(m.group(2), quote=True), m.group(1)), s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", s)
        out.append(s)
    return "".join(out)


def slugify(text, used):
    base = re.sub(r"<[^>]+>", "", text)
    base = re.sub(r"[\s　]+", "-", base.strip())
    base = re.sub(r"[^\w\-ぁ-んァ-ヶ一-龠ー]", "", base) or "sec"
    slug = base
    n = 2
    while slug in used:
        slug = "%s-%d" % (base, n); n += 1
    used.add(slug)
    return slug


def extract_headings(lines):
    """コードフェンス外の h2/h3 を slug 付きで抽出（freeform 用：本文はClaudeが書く）。"""
    headings, used = [], set()
    in_fence = False
    for ln in lines:
        if re.match(r"^(`{3,}|~{3,})", ln):
            in_fence = not in_fence; continue
        if in_fence:
            continue
        hm = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if hm:
            txt = hm.group(2).strip()
            headings.append({"level": len(hm.group(1)), "text": txt, "slug": slugify(txt, used)})
    return headings


# ──────────────────────────────────────────────────────────────────────────
# ブロックパーサ
# ──────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────
# 本文の中の figkit（```figkit の JSON から、その場に図を置く）とスクロール連動
# ──────────────────────────────────────────────────────────────────────────
_FK = [None]


def _figkit():
    if _FK[0] is None:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import figkit
        _FK[0] = figkit
    return _FK[0]


def render_figkit_fence(code):
    """```figkit のフェンス: 図 1 つ・図の配列・{"figures": [...]} の JSON をその場で <figure> にする。
    hotspots の画像は本文の画像と同じく埋め込む（--image-mode に従う）。"""
    try:
        data = json.loads(code)
    except ValueError as e:
        print("[figkit] JSON を読めません: %s" % e, file=sys.stderr)
        return ('<div class="callout callout-warning"><div class="callout-head"><span class="callout-ico">⚠️</span>figkit の JSON を読めません</div>'
                '<div class="callout-body"><pre><code>%s</code></pre></div></div>' % html.escape(code))
    specs = data["figures"] if isinstance(data, dict) and "figures" in data else (data if isinstance(data, list) else [data])
    fk = _figkit()
    outs = []
    for spec in specs:
        if spec.get("type") == "hotspots" and spec.get("src"):
            m = re.search(r'src="([^"]*)"', image_tag(html.escape(spec.get("alt", "")), html.escape(spec["src"])))
            if m:
                spec = dict(spec, src=html.unescape(m.group(1)))
        try:
            outs.append(fk.render(spec if spec.get("id") else dict(spec, id=_uid("fk-"))))
        except (SystemExit, KeyError, ValueError, TypeError, IndexError, ZeroDivisionError) as e:
            print("[figkit] 図を作れません（%s）: %s" % (spec.get("type"), e), file=sys.stderr)
            outs.append('<div class="callout callout-warning"><div class="callout-head"><span class="callout-ico">⚠️</span>figkit の図（%s）を作れません</div>'
                        '<div class="callout-body"><p>%s</p></div></div>' % (html.escape(str(spec.get("type"))), html.escape(str(e))))
    return "\n".join(outs)


SCROLLY_RE = re.compile(r"^\s*<!--\s*scrolly(?:\s*[:=]\s*([^>]*?))?\s*-->\s*$", re.I)
SCROLLY_END_RE = re.compile(r"^\s*<!--\s*/\s*scrolly\s*-->\s*$", re.I)
STEP_RE = re.compile(r"^\s*<!--\s*step(?:\s*[:=]\s*([^>]*?))?\s*-->\s*$", re.I)


def render_scrolly(lines, opts, headings, used_slugs, mermaid_store, layout):
    """図を画面に留め、本文の段（<!-- step -->）が画面の中ほどに来るたびに図の段を進める。
    図が 1 つなら図の段（data-step）を順に見せ、図・画像が複数なら 1 つずつ入れ替える。
    JS 無し・印刷・動きを減らす設定では、図は完成形のまま本文と並ぶ。"""
    fig_lines, steps, cur = [], [], None
    for ln in lines:
        m = STEP_RE.match(ln)
        if m:
            cur = {"opt": (m.group(1) or "").strip(), "lines": []}
            steps.append(cur)
        elif cur is None:
            fig_lines.append(ln)
        else:
            cur["lines"].append(ln)
    fig = parse_blocks(fig_lines, headings, used_slugs, mermaid_store, top_level=False, layout=layout)
    side = "left" if re.search(r"\bleft\b|左", opts) else "right"
    parts = []
    for k, st in enumerate(steps):
        o = st["opt"].lower()
        show = re.search(r"\d+", o)
        attrs = ' data-sy-show="%s"' % show.group(0) if show else ""
        if re.search(r"\bonly\b|だけ", o):
            attrs += " data-sy-only"
        if re.search(r"\ball\b|全部", o):
            attrs += ' data-sy-show="all"'
        body = parse_blocks(st["lines"], headings, used_slugs, mermaid_store, top_level=False, layout=layout)
        parts.append('<div class="sy-step"%s><div class="sy-card">%s</div></div>' % (attrs, body))
    return ('<section class="sy sy-%s" data-sy><div class="sy-fig"><div class="sy-sticky">%s'
            '<div class="sy-prog" aria-hidden="true"></div></div></div><div class="sy-steps">%s</div></section>'
            % (side, fig, "".join(parts)))


def parse_blocks(lines, headings, used_slugs, mermaid_store, top_level=True, layout="plain"):
    out = []
    i = 0
    n = len(lines)
    # このブロック内で現在有効なレイアウト。見出しごとに --layout-map / 既定値で再解決し、
    # `<!-- layout: .. -->` ディレクティブが現れたらそこから上書きする。
    cur_layout = layout
    lays, head_lay = [], {}      # 出力ブロックごとの節レイアウト（節単位の組み替え用）
    table_mode = "auto"

    def indent_of(s):
        m = re.match(r"[ \t]*", s)
        return len(m.group(0).replace("\t", "    "))

    while i < n:
        while len(lays) < len(out):
            lays.append(cur_layout)
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # 見出し
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1)); txt = m.group(2).strip(); slug = ""
            inner = inline(txt)
            if level in (2, 3):
                slug = slugify(txt, used_slugs)
                headings.append({"level": level, "text": txt, "slug": slug})
                out.append('<h%d id="%s" class="hl">%s<a class="anchor" href="#%s">#</a></h%d>'
                           % (level, slug, inner, slug, level))
            else:
                out.append("<h%d>%s</h%d>" % (level, inner, level))
            # 節が変わったのでレイアウトを再解決（前節のディレクティブを引きずらない）
            if top_level:
                cur_layout = layout_for_section(txt, slug, layout)
                head_lay[len(out) - 1] = (level, cur_layout)
            i += 1
            continue

        # スクロール連動（<!-- scrolly --> … <!-- step --> … <!-- /scrolly -->）
        sm = SCROLLY_RE.match(line)
        if sm:
            j = i + 1
            while j < n and not SCROLLY_END_RE.match(lines[j]):
                j += 1
            out.append(render_scrolly(lines[i + 1:j], sm.group(1) or "", headings, used_slugs, mermaid_store, cur_layout))
            i = j + 1
            continue

        # セクション別レイアウトのディレクティブ。出力には出さず、以降の節内リストに効く
        directive = read_layout_directive(line)
        if directive is not None:
            if top_level and directive:
                cur_layout = directive
                for k in sorted(head_lay, reverse=True):      # 見出し直後のディレクティブは節の見せ方にも効く
                    head_lay[k] = (head_lay[k][0], directive)
                    break
            i += 1
            continue
        fm = MOTION_COMMENT_RE.match(line.strip())
        if fm:
            out.append(motion_figure(fm.group(1), _IMG_BASE, _DOC_THEME[0]))
            i += 1
            continue
        vm = VIDEO_RE.match(line.strip())
        if vm:
            out.append(video_fragment(video_attrs(vm.group(1)), _IMG_BASE, _DOC_THEME[0]))
            i += 1
            continue
        tm = TABLE_DIRECTIVE_RE.match(line)
        if tm:
            table_mode = tm.group(1).lower()
            i += 1
            continue

        # コードフェンス / mermaid（先頭 0〜3 スペースを許容：リスト内のフェンス対応）
        m = re.match(r"^(\s{0,3})(`{3,}|~{3,})\s*([\w-]*)\s*$", line)
        if m:
            lead = len(m.group(1)); fence = m.group(2)[0]; lang = m.group(3).lower()
            j = i + 1; buf = []
            while j < n and not re.match(r"^\s{0,3}%s{3,}\s*$" % re.escape(fence), lines[j]):
                ln = lines[j]
                k = 0
                while k < lead and k < len(ln) and ln[k] == " ":
                    k += 1
                buf.append(ln[k:]); j += 1
            code = "\n".join(buf)
            if lang == "figkit":
                out.append(render_figkit_fence(code))
            elif lang == "motion":
                out.append(motion_figure(code, _IMG_BASE, _DOC_THEME[0]))
            elif lang == "mermaid":
                key = "@@MERMAID_%d@@" % len(mermaid_store)
                mermaid_store.append(code)
                out.append(key)
            elif lang == "diff":
                def dline(ln):
                    cls = "dl-add" if ln.startswith("+") and not ln.startswith("+++") else "dl-del" if ln.startswith("-") and not ln.startswith("---") else "dl-hunk" if ln.startswith("@@") else "dl-ctx"
                    return '<span class="dl %s">%s\n</span>' % (cls, html.escape(ln))
                out.append('<figure class="codeblock diff"><button class="copy-btn" type="button">コピー</button>'
                           '<pre><code class="lang-diff">%s</code></pre></figure>' % "".join(dline(ln) for ln in code.split("\n")))
            else:
                out.append(
                    '<figure class="codeblock"><button class="copy-btn" type="button">コピー</button>'
                    '<pre><code class="lang-%s">%s</code></pre></figure>'
                    % (html.escape(lang), html.escape(code)))
            i = j + 1
            continue

        # コールアウト / 引用
        if line.lstrip().startswith(">"):
            j = i; quoted = []
            while j < n and lines[j].lstrip().startswith(">"):
                quoted.append(re.sub(r"^\s*>\s?", "", lines[j])); j += 1
            ctype = None
            mm = re.match(r"^\[!(\w+)\]\s*(.*)$", quoted[0]) if quoted else None
            if mm:
                ctype = mm.group(1).upper()
                first = mm.group(2).strip()
                quoted = ([first] if first else []) + quoted[1:]
            inner_html = parse_blocks(quoted, headings, used_slugs, mermaid_store,
                                      top_level=False, layout=cur_layout)
            if ctype:
                label, icon = CALLOUT_LABELS.get(ctype, (ctype.title(), "💬"))
                out.append('<div class="callout callout-%s"><div class="callout-head">'
                           '<span class="callout-ico">%s</span>%s</div><div class="callout-body">%s</div></div>'
                           % (ctype.lower(), icon, html.escape(label), inner_html))
            else:
                out.append('<blockquote>%s</blockquote>' % inner_html)
            i = j
            continue

        # 水平線
        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", line):
            out.append("<hr>"); i += 1; continue

        # テーブル
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]) and "-" in lines[i + 1]:
            def cells(row):
                row = row.strip()
                if row.startswith("|"): row = row[1:]
                if row.endswith("|"): row = row[:-1]
                return [c.strip() for c in row.split("|")]
            header = cells(line); i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i])); i += 1
            out.append(render_table(header, rows, table_mode))
            table_mode = "auto"
            continue

        # リスト
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            # カード/タイムライン（トップレベルの単純箇条書き）は従来のフラット収集
            if top_level and cur_layout in RICH_LAYOUTS:
                items, i = collect_top_items(lines, i)
                out.append(render_rich(items, cur_layout, headings, used_slugs, mermaid_store))
                continue
            if top_level and cur_layout in FLAT_LAYOUTS:
                items = []
                while i < n and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                    lm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i])
                    items.append({"indent": indent_of(lines[i]),
                                  "ordered": bool(re.match(r"\d+\.", lm.group(2))),
                                  "text": lm.group(3)})
                    i += 1
                out.append(render_list(items, cur_layout))
                continue
            # それ以外は項目内のネストしたブロック（コード/画像/段落/サブリスト）を保持
            html_list, i = parse_rich_list(lines, i, headings, used_slugs, mermaid_store, cur_layout)
            out.append(html_list)
            continue

        # 段落（空行まで結合）
        para = [line]; i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|>|\s*([-*+]|\d+\.)\s|\s{0,3}(`{3,}|~{3,})|\s*([-*_])(\s*\4){2,}\s*$)", lines[i]):
            para.append(lines[i]); i += 1
        # 行末2スペース or 末尾 \ はハードブレイク（<br>）として維持
        toks = []
        for idx, s in enumerate(para):
            hard = bool(re.search(r"(  +|\\)\s*$", s))
            core = re.sub(r"\s+$", "", s)
            core = re.sub(r"\\$", "", core).strip()
            toks.append(core)
            if hard and idx < len(para) - 1:
                toks.append("\x00BR\x00")
        raw = " ".join(t for t in toks if t)
        out.append("<p>%s</p>" % inline(raw).replace("\x00BR\x00", "<br>"))

    while len(lays) < len(out):
        lays.append(cur_layout)
    if top_level:
        out = regroup_sections(out, lays, head_lay)
    return "\n".join(out)


def _indent_of(s):
    m = re.match(r"[ \t]*", s)
    return len(m.group(0).replace("\t", "    "))


def parse_rich_list(lines, i, headings, used_slugs, mermaid_store, layout):
    """リスト項目ごとに、その項目に属する後続行（本文継続・空行・より深いインデント）を集め、
    項目インデント分だけデデントして再帰パースする。項目内のコードブロック・画像・段落・
    サブリストを正しく保持する（インデントされたコードフェンスもこれで列0扱いになる）。"""
    n = len(lines)
    base = _indent_of(lines[i])
    ordered = bool(re.match(r"^\s*\d+\.", lines[i]))
    tag = "ol" if ordered else "ul"
    out = ["<%s>" % tag]
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        if _indent_of(lines[i]) != base:
            break
        mk = re.match(r"^(\s*)([-*+]|\d+\.)(\s+)(.*)$", lines[i])
        if not mk:
            break
        content_indent = len(mk.group(1)) + len(mk.group(2)) + len(mk.group(3))
        body = [mk.group(4)]
        i += 1
        while i < n:
            if not lines[i].strip():
                body.append("")
                i += 1
                continue
            if _indent_of(lines[i]) >= content_indent:
                ln = lines[i]
                body.append(ln[content_indent:] if len(ln) >= content_indent else ln.lstrip())
                i += 1
            else:
                break
        while body and not body[-1].strip():
            body.pop()
        out.append("<li>%s</li>" % render_item_body(body, headings, used_slugs, mermaid_store, layout))
    out.append("</%s>" % tag)
    return "".join(out), i


def render_item_body(body, headings, used_slugs, mermaid_store, layout):
    """リスト項目本文を描画。ブロック要素が無ければ inline（tight）、あれば再帰パース。"""
    block_re = r"^(#{1,6}\s|>|\s*([-*+]|\d+\.)\s|\s{0,3}(`{3,}|~{3,})|\s*([-*_])(\s*\4){2,}\s*$)"
    has_block = any((not ln.strip()) or re.match(block_re, ln) for ln in body)
    if not has_block:
        for k in range(len(body) - 1):
            if "|" in body[k] and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", body[k + 1]) and "-" in body[k + 1]:
                has_block = True
                break
    if not has_block:
        text = " ".join(s.strip() for s in body if s.strip())
        cm = re.match(r"^\[([ xX])\]\s+(.*)$", text)
        cb = ""
        if cm:
            checked = "checked" if cm.group(1).lower() == "x" else ""
            cb = '<input type="checkbox" disabled %s> ' % checked
            text = cm.group(2)
        return cb + inline(text)
    return parse_blocks(body, headings, used_slugs, mermaid_store, top_level=False, layout=layout)


def build_list(items):
    pos = [0]

    def parse(level):
        tag = "ol" if items[pos[0]]["ordered"] else "ul"
        html_out = ["<%s>" % tag]
        while pos[0] < len(items):
            it = items[pos[0]]
            if it["indent"] < level:
                break
            if it["indent"] == level:
                # チェックボックス
                text = it["text"]
                cb = ""
                cm = re.match(r"^\[([ xX])\]\s+(.*)$", text)
                if cm:
                    checked = "checked" if cm.group(1).lower() == "x" else ""
                    cb = '<input type="checkbox" disabled %s> ' % checked
                    text = cm.group(2)
                pos[0] += 1
                if pos[0] < len(items) and items[pos[0]]["indent"] > level:
                    child = parse(items[pos[0]]["indent"])
                    html_out.append("<li>%s%s%s</li>" % (cb, inline(text), child))
                else:
                    html_out.append("<li>%s%s</li>" % (cb, inline(text)))
            else:
                html_out.append(parse(it["indent"]))
        html_out.append("</%s>" % tag)
        return "".join(html_out)

    return parse(items[0]["indent"])


# ──────────────────────────────────────────────────────────────────────────
# 追加のレイアウト（tabs / checklist / defs / stats / proscons / chips / tree）と
# 節の見せ方（walkthrough / summary）、表の強化
# ──────────────────────────────────────────────────────────────────────────
_UID = [0]
_DOC_THEME = ["corporate"]


def _uid(prefix):
    _UID[0] += 1
    return "%s%d" % (prefix, _UID[0])


def collect_top_items(lines, i):
    """トップレベルの項目ごとに {text, body} を集める（body は項目の中の後続行。コード・段落を含む）。"""
    n = len(lines)
    base = _indent_of(lines[i])
    items = []
    while i < n:
        if not lines[i].strip():
            j = i
            while j < n and not lines[j].strip():
                j += 1
            if j < n and _indent_of(lines[j]) == base and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[j]):
                i = j
                continue
            break
        if _indent_of(lines[i]) != base:
            break
        mk = re.match(r"^(\s*)([-*+]|\d+\.)(\s+)(.*)$", lines[i])
        if not mk:
            break
        ci = len(mk.group(1)) + len(mk.group(2)) + len(mk.group(3))
        body = []
        i += 1
        while i < n:
            if not lines[i].strip():
                body.append("")
                i += 1
                continue
            if _indent_of(lines[i]) >= ci:
                ln = lines[i]
                body.append(ln[ci:] if len(ln) >= ci else ln.lstrip())
                i += 1
            else:
                break
        while body and not body[-1].strip():
            body.pop()
        items.append({"text": mk.group(4), "body": body, "ordered": bool(re.match(r"\d+\.", mk.group(2)))})
    return items, i


_PROS = re.compile(r"(メリット|良い|良かった|利点|長所|強み|pros?\b|good|できること|うれしい)", re.I)
_CONS = re.compile(r"(デメリット|懸念|欠点|短所|弱み|リスク|課題|cons?\b|bad|注意|できないこと|困る)", re.I)
_STAT = re.compile(r"^\s*(?:\*\*)?([+\-−±]?[¥$€]?\d[\d,]*(?:\.\d+)?\s*(?:%|％|倍|件|人|名|社|円|万円|億円|万|億|時間|分|秒|ms|s|x|pt|点|日|週間|週|か月|ヶ月|年|GB|MB|TB|KB|K|M|B|回|本|個|行)?)(?:\*\*)?(?:\s+|$)(.*)$")


def _term_desc(text):
    m = re.match(r"^\*\*(.+?)\*\*\s*[:：—–]?\s*(.*)$", text)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^`([^`]+)`\s*[:：—–]\s*(.*)$", text)
    if m:
        return "`%s`" % m.group(1), m.group(2)
    m = re.match(r"^([^:：]{1,40}?)\s*[:：]\s*(.+)$", text)
    if m and "http" not in m.group(1) and "/" not in m.group(1):
        return m.group(1), m.group(2)
    return text, ""


def render_rich(items, layout, headings, used_slugs, mermaid_store):
    def body_html(it):
        if not it["body"]:
            return ""
        return render_item_body(it["body"], headings, used_slugs, mermaid_store, "plain")

    if layout == "tabs":
        tid = _uid("tabs")
        btns, panels = [], []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            lab = (icon_html(icon, 18) + " " if icon else "") + inline(text)
            btns.append('<button type="button" role="tab" id="%s-t%d" aria-controls="%s-p%d" aria-selected="%s" '
                        'tabindex="%d" style="--ca:%s">%s</button>'
                        % (tid, k, tid, k, "true" if k == 0 else "false", 0 if k == 0 else -1, _ca(k), lab))
            panels.append('<section class="tab-panel" role="tabpanel" id="%s-p%d" aria-labelledby="%s-t%d" tabindex="0">'
                          '<div class="tab-print-h">%s</div>%s</section>' % (tid, k, tid, k, lab, body_html(it)))
        return ('<div class="tabs" data-tabs><div class="tab-list" role="tablist">%s</div>%s</div>'
                % ("".join(btns), "".join(panels)))

    if layout == "checklist":
        key = _uid("ck")
        rows, done = [], 0
        for it in items:
            m = re.match(r"^\[([ xX])\]\s+(.*)$", it["text"])
            checked = bool(m and m.group(1).lower() == "x")
            text = m.group(2) if m else it["text"]
            done += checked
            b = body_html(it)
            rows.append('<li><label><input type="checkbox"%s><span class="ck-text">%s</span></label>%s</li>'
                        % (" checked" if checked else "", inline(text), '<div class="ck-body">%s</div>' % b if b else ""))
        total = len(items) or 1
        return ('<div class="checklist" data-checklist="%s"><div class="ck-head"><div class="ck-bar"><i style="width:%d%%"></i></div>'
                '<span class="ck-count">%d / %d</span><button type="button" class="ck-reset">元に戻す</button></div>'
                '<ul class="ck-list">%s</ul></div>' % (key, round(100 * done / total), done, len(items), "".join(rows)))

    if layout == "defs":
        rows = []
        for it in items:
            term, desc = _term_desc(it["text"])
            b = body_html(it)
            rows.append('<div class="def"><dt>%s</dt><dd>%s%s</dd></div>' % (inline(term), inline(desc) if desc else "", b))
        filt = ('<input type="search" class="defs-filter" placeholder="用語を絞り込む" aria-label="用語を絞り込む">'
                if len(items) >= 10 else "")
        return '<div class="defs-wrap">%s<dl class="defs">%s</dl></div>' % (filt, "".join(rows))

    if layout == "stats":
        tiles = []
        for k, it in enumerate(items):
            m = _STAT.match(it["text"])
            val, lab = (m.group(1).strip(), m.group(2)) if m else (it["text"], "")
            b = body_html(it)
            tiles.append('<div class="stat" style="--ca:%s"><div class="big">%s</div><div class="cap">%s</div>%s</div>'
                         % (_ca(k), inline(val), inline(lab), '<div class="stat-note">%s</div>' % b if b else ""))
        return '<div class="stat-row">%s</div>' % "".join(tiles)

    if layout == "proscons":
        cols = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            # 「デメリット」は「メリット」を含むので、懸念を先に判定する
            tone = "con" if _CONS.search(text) else "pro" if _PROS.search(text) else "neutral"
            ca = ' style="--ca:%s"' % _ca(k) if tone == "neutral" else ""
            cols.append('<div class="pc-col pc-%s"%s><div class="pc-h">%s%s</div><div class="pc-b">%s</div></div>'
                        % (tone, ca, (icon_html(icon) + " ") if icon else "", inline(text), body_html(it)))
        return '<div class="pc-grid" style="--cols:%d">%s</div>' % (min(len(items), 3), "".join(cols))
    return render_more(items, layout, body_html)


# ──────────────────────────────────────────────────────────────────────────
# 追加の見せ方（hero・quote・pricing・stepper・kanban・faq・beforeafter・gallery・roadmap・persona・
#   chevron・counters・rating・dodont・voices・decision・icongrid）。動きは MOTION_JS の部品の登場で付く
# ──────────────────────────────────────────────────────────────────────────
def _split_dash(text):
    """「A — B」「A - B」「A：B」を (A, B) に。"""
    m = re.split(r"\s+(?:—|–|-{1,2})\s+|：", text, 1)
    return (m[0].strip(), m[1].strip()) if len(m) > 1 else (text.strip(), "")


def _tree_nodes(lines):
    """インデントした箇条書きの行から [{text, kids}] の木を作る。"""
    rows = []
    for ln in lines:
        m = re.match(r"^(\s*)(?:[-*+]|\d+\.)\s+(.*)$", ln)
        if m:
            rows.append((len(m.group(1).replace("\t", "    ")), m.group(2).strip()))
    root, stack = [], [(-1, {"kids": None})]
    stack[0][1]["kids"] = root
    for ind, text in rows:
        node = {"text": text, "kids": []}
        while stack and stack[-1][0] >= ind:
            stack.pop()
        stack[-1][1]["kids"].append(node)
        stack.append((ind, node))
    return root


def _sub(body):
    """項目の中の、いちばん浅い箇条書きの文（カードの中身・機能の一覧など）。"""
    return [n["text"] for n in _tree_nodes(body)]


def _ico(name, size=18, fallback=""):
    h = icon_html(":%s:" % name, size)
    return h if h.startswith("<svg") else fallback


_REC = re.compile(r"おすすめ|推奨|人気|recommended|popular|best", re.I)
_DO = re.compile(r"^\s*(?:[✓✔○◯◎]|do\b|やる|すべき|良い|good|ok\b)\s*[:：]?\s*", re.I)
_DONT = re.compile(r"^\s*(?:[✗✕×☓]|don'?t\b|やらない|避ける|しない|悪い|bad|ng\b)\s*[:：]?\s*", re.I)


def render_more(items, layout, body_html):
    if not items:
        return ""
    if layout == "hero":
        icon, tags, text = extract_decorations(items[0]["text"])
        chips = "".join('<span class="hero-chip">%s</span>' % html.escape(t) for t in tags)
        return ('<div class="blk-hero"><span class="hero-glow" aria-hidden="true"></span>%s<div class="hero-h">%s</div>%s%s%s</div>'
                % ('<div class="hero-ic">%s</div>' % icon_html(icon, 44) if icon else "", inline(text),
                   "".join('<p class="hero-sub">%s</p>' % inline(it["text"]) for it in items[1:]),
                   '<div class="hero-chips">%s</div>' % chips if chips else "", body_html(items[0])))
    if layout == "quote":
        out = []
        for it in items:
            q, by = _split_dash(it["text"])
            segs = [q] if re.search(r"\*\*|`|\[", q) else (re.findall(r"[^、。，．！？,.!?\s]+[、。，．！？,.!?]*\s*", q) or [q])
            out.append('<figure class="pq"><span class="pq-mark" aria-hidden="true">“</span><blockquote>%s</blockquote>%s%s</figure>'
                       % ("".join('<span class="w">%s</span>' % inline(sg) for sg in segs),
                          '<figcaption>— %s</figcaption>' % inline(by) if by else "", body_html(it)))
        return "".join(out)
    if layout == "pricing":
        cards = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            name, price = _split_dash(text)
            rec = any(_REC.search(t) for t in tags)
            m = re.match(r"^(.*?\d[\d,]*(?:\.\d+)?)(.*)$", price)
            amt = '%s<span class="price-unit">%s</span>' % (inline(m.group(1)), inline(m.group(2))) if m else inline(price)
            feats = "".join('<li>%s<span>%s</span></li>' % (_ico("check", 16, "✓"), inline(f)) for f in _sub(it["body"]))
            cards.append('<div class="price%s" style="--ca:%s">%s%s<div class="price-name">%s</div><div class="price-amt">%s</div><ul class="price-feats">%s</ul></div>'
                         % (" is-rec" if rec else "", _ca(k), '<span class="price-badge">%s</span>' % html.escape(tags[0]) if rec else "",
                            '<div class="price-ic">%s</div>' % icon_html(icon, 26) if icon else "", inline(name), amt, feats))
        return '<div class="price-grid" style="--cols:%d">%s</div>' % (min(len(items), 4), "".join(cards))
    if layout == "stepper":
        steps = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            a, b = _split_dash(text)
            steps.append('<li class="st" style="--ca:%s"><span class="st-dot">%s</span><div class="st-t">%s</div>%s</li>'
                         % (_ca(k), icon_html(icon, 18) if icon else k + 1, inline(a), '<div class="st-d">%s</div>' % inline(b) if b else ""))
        return '<div class="stepper" style="--n:%d"><div class="st-line" aria-hidden="true"><i></i></div><ol>%s</ol></div>' % (len(items), "".join(steps))
    if layout == "kanban":
        cols = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            cards = []
            for c in _sub(it["body"]):
                ci, ct, cx = extract_decorations(c)
                cards.append('<div class="kb-card">%s<span>%s</span>%s</div>' % (icon_html(ci, 16) + " " if ci else "", inline(cx),
                             "".join('<em class="kb-tag">%s</em>' % html.escape(t) for t in ct)))
            cols.append('<div class="kb-col" style="--ca:%s"><div class="kb-h">%s%s<span class="kb-n">%d</span></div>%s</div>'
                        % (_ca(k), icon_html(icon, 16) + " " if icon else "", inline(text), len(cards), "".join(cards)))
        return '<div class="kanban" style="--cols:%d">%s</div>' % (len(items), "".join(cols))
    if layout == "faq":
        return '<div class="faq">%s</div>' % "".join(
            '<details class="faq-item"%s><summary><span class="faq-q">Q</span><span>%s</span></summary><div class="faq-a"><span class="faq-al">A</span><div>%s</div></div></details>'
            % (" open" if k == 0 else "", inline(it["text"]), body_html(it)) for k, it in enumerate(items))
    if layout == "beforeafter":
        if len(items) < 2:
            return render_more(items, "quote", body_html)
        panes = []
        for k, it in enumerate(items[:2]):
            lab, rest = _split_dash(it["text"])
            panes.append('<div class="ba-pane ba-%s"><div class="ba-label">%s</div><div class="ba-body">%s%s</div></div>'
                         % ("before" if k == 0 else "after", inline(lab), '<p>%s</p>' % inline(rest) if rest else "", body_html(it)))
        return ('<div class="ba" data-ba><div class="ba-stage">%s<div class="ba-handle" aria-hidden="true"><span>⇆</span></div></div>'
                '<input class="ba-range" type="range" min="0" max="100" value="50" aria-label="前と後の境目"></div>' % "".join(panes))
    if layout == "gallery":
        figs = []
        for it in items:
            h = inline(it["text"])
            imgs = re.findall(r"<img[^>]*>", h)
            cap = re.sub(r"<img[^>]*>", "", h).strip()
            figs.append('<figure class="gal-item">%s<figcaption>%s</figcaption></figure>'
                        % ('<button type="button" class="gal-btn" aria-label="拡大">%s</button>' % imgs[0] if imgs else '<div class="gal-ph">%s</div>' % cap, cap if imgs else ""))
        return '<div class="gal">%s</div>' % "".join(figs)
    if layout == "roadmap":
        lanes = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            lis = "".join('<li>%s</li>' % inline(x) for x in _sub(it["body"]))
            lanes.append('<div class="rm-lane%s" style="--ca:%s"><div class="rm-h">%s%s%s</div><ul>%s</ul></div>'
                         % (" is-now" if k == 0 else "", _ca(k), icon_html(icon, 18) + " " if icon else "", inline(text),
                            '<span class="rm-now">いまここ</span>' if k == 0 else "", lis))
        return '<div class="rm" style="--cols:%d">%s</div>' % (len(items), "".join(lanes))
    if layout == "persona":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            name, role = _split_dash(text)
            av = icon_html(icon, 34) if icon else html.escape(re.sub(r"[*`\[\]]", "", name)[:1])
            out.append('<div class="pers" style="--ca:%s"><div class="pers-av">%s</div><div class="pers-name">%s</div>%s%s<div class="pers-b">%s</div></div>'
                       % (_ca(k), av, inline(name), '<div class="pers-role">%s</div>' % inline(role) if role else "",
                          '<div class="pers-tags">%s</div>' % "".join('<span>%s</span>' % html.escape(t) for t in tags) if tags else "", body_html(it)))
        return '<div class="pers-grid">%s</div>' % "".join(out)
    if layout == "chevron":
        return '<ol class="chev-row" style="--n:%d">%s</ol>' % (len(items), "".join(
            '<li class="chev" style="--ca:%s"><span class="chev-t">%s</span>%s</li>'
            % (_ca(k), inline(_split_dash(it["text"])[0]), '<span class="chev-d">%s</span>' % inline(_split_dash(it["text"])[1]) if _split_dash(it["text"])[1] else "")
            for k, it in enumerate(items)))
    if layout == "counters":
        tiles = []
        for k, it in enumerate(items):
            m = _STAT.match(it["text"])
            val, lab = (m.group(1).strip(), m.group(2)) if m else (it["text"], "")
            lab = re.sub(r"^\s*(?:—|–|-)\s*", "", lab)
            digits = "".join('<span class="od" style="--d:%s"><span class="od-s">%s</span></span>' % (ch, "".join("<span>%d</span>" % i for i in range(10)))
                             if ch.isdigit() else '<span class="od-c">%s</span>' % html.escape(ch) for ch in val)
            tiles.append('<div class="ctr" style="--ca:%s"><div class="ctr-v" aria-label="%s"><span aria-hidden="true">%s</span></div><div class="ctr-l">%s</div></div>'
                         % (_ca(k), html.escape(val, quote=True), digits, inline(lab)))
        return '<div class="ctr-row">%s</div>' % "".join(tiles)
    if layout == "rating":
        rows = []
        for k, it in enumerate(items):
            lab, val = _split_dash(it["text"])
            m = re.match(r"^([\d.]+)\s*(?:/\s*([\d.]+))?\s*(%|％)?", val)
            v = float(m.group(1)) if m else 0.0
            mx = float(m.group(2)) if m and m.group(2) else (100.0 if m and m.group(3) else 5.0)
            f = max(0.0, min(1.0, v / mx if mx else 0))
            meter = ('<span class="rt-stars" aria-hidden="true"><span class="rt-base">★★★★★</span><span class="rt-fill" style="width:%.1f%%">★★★★★</span></span>' % (f * 100)
                     if mx == 5 else '<span class="rt-bar" aria-hidden="true"><i style="width:%.1f%%"></i></span>' % (f * 100))
            rows.append('<div class="rt" style="--ca:%s"><span class="rt-l">%s</span>%s<span class="rt-v">%s</span></div>' % (_ca(k), inline(lab), meter, html.escape(val)))
        return '<div class="rt-list">%s</div>' % "".join(rows)
    if layout == "dodont":
        do, dont = [], []
        for it in items:
            t = it["text"]
            if _DONT.match(t):
                dont.append(_DONT.sub("", t, 1))
            else:
                do.append(_DO.sub("", t, 1))
        col = lambda cls, head, ico, fb, rows: ('<div class="dd-col dd-%s"><div class="dd-h">%s%s</div><ul>%s</ul></div>'
                                                % (cls, _ico(ico, 20, fb) + " ", head, "".join('<li>%s<span>%s</span></li>' % (_ico(ico, 16, fb), inline(r)) for r in rows)))
        return '<div class="dd">%s%s</div>' % (col("do", "やること", "check", "✓", do), col("dont", "やらないこと", "x", "✗", dont))
    if layout == "voices":
        out = []
        for k, it in enumerate(items):
            q, by = _split_dash(it["text"])
            out.append('<figure class="voice" style="--ca:%s;--r:%s"><blockquote>%s</blockquote>%s</figure>'
                       % (_ca(k), ["-3deg", "2deg", "-1.5deg", "3deg"][k % 4], inline(q),
                          '<figcaption><span class="voice-av">%s</span>%s</figcaption>' % (html.escape(re.sub(r"[*`]", "", by)[:1]), inline(by)) if by else ""))
        return '<div class="voices">%s</div>' % "".join(out)
    if layout == "decision":
        def node(n, depth):
            t = n["text"]
            b = re.split(r"\s*(?:→|->|⇒)\s*", t, 1)
            head = ('<span class="dt-b">%s</span>%s' % (inline(b[0]), inline(b[1])) if len(b) > 1 else inline(t))
            cls = "dt-q" if n["kids"] else "dt-leaf"
            kids = '<ul>%s</ul>' % "".join(node(c, depth + 1) for c in n["kids"]) if n["kids"] else ""
            return '<li><div class="dt-n %s" data-depth="%d">%s</div>%s</li>' % (cls, depth, head, kids)
        return "".join('<div class="dt-wrap"><ul class="dt">%s</ul></div>' % node({"text": it["text"], "kids": _tree_nodes(it["body"])}, 0) for it in items)
    if layout == "icongrid":
        return '<div class="ig-grid">%s</div>' % "".join(
            '<div class="ig" style="--ca:%s"><div class="ig-ic">%s</div><div class="ig-t">%s</div>%s</div>'
            % (_ca(k), icon_html(extract_decorations(it["text"])[0], 30) or "•", inline(_split_dash(extract_decorations(it["text"])[2])[0]),
               '<div class="ig-d">%s</div>' % inline(_split_dash(extract_decorations(it["text"])[2])[1]) if _split_dash(extract_decorations(it["text"])[2])[1] else "")
            for k, it in enumerate(items))
    return render_more2(items, layout, body_html)


# ──────────────────────────────────────────────────────────────────────────
# さらに追加の見せ方（pyramid・cycle・quad・chat・calendar・versus・banner・swimlane・zigzag・rings・
#   ticker・bignum・sticky・flip・agenda・marker）。部品の class は他と重ならない接頭辞（lx-）で始める
# ──────────────────────────────────────────────────────────────────────────
_CENTER = re.compile(r"^(?:center|中心|中央)$", re.I)
_PCT = re.compile(r"([\d.]+)\s*(?:/\s*([\d.]+))?\s*(%|％)?")
_WEEK = "日月火水木金土"


def _date_of(s, year):
    """「2026-10-06」「10/6」「10月6日」を date に。読めなければ None。"""
    import datetime
    m = re.match(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s) or None
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.match(r"^\s*(\d{1,2})\s*[/月]\s*(\d{1,2})\s*日?", s)
        if not m:
            return None, s
        y, mo, d = year, int(m.group(1)), int(m.group(2))
    try:
        return datetime.date(y, mo, d), s[m.end():]
    except ValueError:
        return None, s


def render_more2(items, layout, body_html):
    if layout == "pyramid":
        n = len(items)
        rows = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            a, b = _split_dash(text)
            w = 46 + (54 * k / (n - 1) if n > 1 else 54)
            rows.append('<div class="lx-pyr-row" style="--ca:%s;--w:%.1f%%;--k:%d"><div class="lx-pyr-band"><span>%s%s</span></div>'
                        '<div class="lx-pyr-d">%s</div></div>'
                        % (_ca(k), w, k, icon_html(icon, 18) + " " if icon else "", inline(a), (inline(b) if b else "") + body_html(it)))
        return '<div class="lx-pyr" style="--n:%d">%s</div>' % (n, "".join(rows))
    if layout == "cycle":
        center, ring = None, []
        for it in items:
            icon, tags, text = extract_decorations(it["text"])
            if center is None and any(_CENTER.match(t) for t in tags):
                center = (icon, text)
            else:
                ring.append((icon, text))
        n = max(1, len(ring))
        nodes = []
        for k, (icon, text) in enumerate(ring):
            an = -math.pi / 2 + 2 * math.pi * k / n
            a, b = _split_dash(text)
            nodes.append('<li class="lx-cyc-n" style="--ca:%s;--x:%.2f%%;--y:%.2f%%;--k:%d"><span class="lx-cyc-no">%s</span><span class="lx-cyc-t">%s</span>%s</li>'
                         % (_ca(k), 50 + 38 * math.cos(an), 50 + 38 * math.sin(an), k, icon_html(icon, 16) if icon else k + 1, inline(a),
                            '<span class="lx-cyc-d">%s</span>' % inline(b) if b else ""))
        ring_svg = ('<svg class="lx-cyc-ring" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="38" pathLength="100"/>%s</svg>'
                    % "".join('<path class="lx-cyc-ar" d="M0,-2.2 L3,0 L0,2.2z" transform="translate(%.2f %.2f) rotate(%.1f)"/>'
                              % (50 + 38 * math.cos(-math.pi / 2 + 2 * math.pi * (k + .5) / n), 50 + 38 * math.sin(-math.pi / 2 + 2 * math.pi * (k + .5) / n),
                                 math.degrees(-math.pi / 2 + 2 * math.pi * (k + .5) / n) + 90) for k in range(n)))
        mid = ('<div class="lx-cyc-c">%s%s</div>' % (icon_html(center[0], 26) if center[0] else "", inline(center[1]))) if center else ""
        return '<div class="lx-cyc" style="--n:%d">%s%s<ol>%s</ol></div>' % (n, ring_svg, mid, "".join(nodes))
    if layout == "quad":
        axes = {}
        cells = []
        for k, it in enumerate(items[:4]):
            icon, tags, text = extract_decorations(it["text"])
            rest = []
            for t in tags:
                m = re.match(r"^([xy])\s*[:：]\s*(.+)$", t, re.I)
                if m:
                    axes[m.group(1).lower()] = m.group(2)
                else:
                    rest.append(t)
            a, b = _split_dash(text)
            rec = any(_REC.search(t) for t in rest)
            lis = "".join('<li>%s</li>' % inline(x) for x in _sub(it["body"]))
            cells.append('<div class="lx-quad-c%s" style="--ca:%s;--qx:%d;--qy:%d">%s<div class="lx-quad-h">%s%s</div>%s%s</div>'
                         % (" is-rec" if rec else "", _ca(k), -1 if k % 2 == 0 else 1, -1 if k < 2 else 1,
                            '<span class="lx-quad-badge">%s</span>' % html.escape(next(t for t in rest if _REC.search(t))) if rec else "",
                            icon_html(icon, 18) + " " if icon else "", inline(a),
                            '<p>%s</p>' % inline(b) if b else "", '<ul>%s</ul>' % lis if lis else ""))
        ax = ""
        if axes.get("y"):
            ax += '<div class="lx-quad-y"><i></i><span>%s</span></div>' % inline(axes["y"])
        if axes.get("x"):
            ax += '<div class="lx-quad-x"><i></i><span>%s</span></div>' % inline(axes["x"])
        return '<div class="lx-quad%s%s">%s<div class="lx-quad-g">%s</div></div>' % (
            " has-y" if axes.get("y") else "", " has-x" if axes.get("x") else "", ax, "".join(cells))
    if layout == "chat":
        who, rows = [], []
        for it in items:
            icon, tags, text = extract_decorations(it["text"])
            m = re.match(r"^\s*(?:\*\*)?([^:：*]{1,20}?)(?:\*\*)?\s*[:：]\s*(.+)$", text)
            name, say = (m.group(1).strip(), m.group(2)) if m else ("", text)
            if name not in who:
                who.append(name)
            k = who.index(name)
            av = icon_html(icon, 20) if icon else html.escape(re.sub(r"[*`\[\]]", "", name)[:1] or "•")
            rows.append('<div class="lx-cht-m %s" style="--ca:%s"><span class="lx-cht-av" aria-hidden="true">%s</span><div class="lx-cht-w">%s'
                        '<div class="lx-cht-b"><span class="lx-cht-dots" aria-hidden="true"><i></i><i></i><i></i></span><div class="lx-cht-x">%s%s</div></div></div></div>'
                        % ("is-r" if k % 2 else "is-l", _ca(k), av, '<span class="lx-cht-n">%s</span>' % inline(name) if name else "",
                           inline(say), body_html(it)))
        return '<div class="lx-cht">%s</div>' % "".join(rows)
    if layout == "calendar":
        import datetime, calendar as _cal
        yr = datetime.date.today().year
        for it in items:
            m = re.match(r"^\s*(\d{4})[-/.]", it["text"])
            if m:
                yr = int(m.group(1))
                break
        evs = []
        for k, it in enumerate(items):
            d, rest = _date_of(it["text"], yr)
            icon, tags, text = extract_decorations(rest.lstrip(" —–-:：") if d else rest)
            evs.append((d, icon, tags, text, it))
        months = sorted({(d.year, d.month) for d, *_ in evs if d})[:3]
        out = []
        for (y, mo) in months:
            first = datetime.date(y, mo, 1)
            days = _cal.monthrange(y, mo)[1]
            lead = (first.weekday() + 1) % 7              # 日曜はじまり
            cells = ['<div class="lx-cal-w">%s</div>' % w for w in _WEEK]
            cells += ['<div class="lx-cal-d is-empty" style="--i:%d"></div>' % i for i in range(lead)]
            for day in range(1, days + 1):
                dt = datetime.date(y, mo, day)
                hits = [(k, e) for k, e in enumerate(evs) if e[0] == dt]
                wd = (dt.weekday() + 1) % 7
                chips = "".join('<span class="lx-cal-ev" style="--ca:%s">%s</span>' % (_ca(k), inline(_split_dash(e[3])[0])) for k, e in hits)
                cells.append('<div class="lx-cal-d%s%s" style="--i:%d"><span class="lx-cal-no">%d</span>%s</div>'
                             % (" has-ev" if hits else "", " is-sun" if wd == 0 else " is-sat" if wd == 6 else "", lead + day - 1, day, chips))
            lst = "".join('<li style="--ca:%s"><time>%d/%d（%s）</time><span>%s%s</span>%s</li>'
                          % (_ca(k), e[0].month, e[0].day, _WEEK[(e[0].weekday() + 1) % 7], icon_html(e[1], 16) + " " if e[1] else "",
                             inline(e[3]), "".join('<em>%s</em>' % html.escape(t) for t in e[2]))
                          for k, e in enumerate(evs) if e[0] and (e[0].year, e[0].month) == (y, mo))
            out.append('<div class="lx-cal"><div class="lx-cal-h">%d年 %d月</div><div class="lx-cal-g">%s</div><ul class="lx-cal-l">%s</ul></div>'
                       % (y, mo, "".join(cells), lst))
        loose = [e for e in evs if not e[0]]
        if loose:
            out.append('<ul class="lx-cal-l">%s</ul>' % "".join('<li><span>%s</span></li>' % inline(e[3]) for e in loose))
        return '<div class="lx-cal-wrap">%s</div>' % "".join(out)
    if layout == "versus":
        if len(items) < 2:
            return render_more(items, "hero", body_html)
        sides = []
        for k, it in enumerate(items[:2]):
            icon, tags, text = extract_decorations(it["text"])
            a, b = _split_dash(text)
            rec = any(_REC.search(t) for t in tags)
            lis = "".join('<li>%s</li>' % inline(x) for x in _sub(it["body"]))
            rest = [ln for ln in it["body"] if not re.match(r"^\s*(?:[-*+]|\d+\.)\s+", ln) and ln.strip() and not ln.startswith(" ")]
            sides.append('<div class="lx-vs-s lx-vs-%s%s" style="--ca:%s">%s<div class="lx-vs-ic">%s</div><div class="lx-vs-n">%s</div>%s%s</div>'
                         % ("l" if k == 0 else "r", " is-rec" if rec else "", _ca(k),
                            '<span class="lx-vs-badge">%s</span>' % html.escape(tags[0]) if rec else "",
                            icon_html(icon, 34) if icon else html.escape(re.sub(r"[*`\[\]]", "", a)[:1]), inline(a),
                            '<p class="lx-vs-d">%s</p>' % inline(b) if b else "", '<ul>%s</ul>' % lis if lis else ""))
        return '<div class="lx-vs">%s<div class="lx-vs-mid" aria-hidden="true"><span>VS</span></div>%s</div>' % (sides[0], sides[1])
    if layout == "banner":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            out.append('<div class="lx-bnr" style="--ca:%s">%s<div class="lx-bnr-t">%s%s</div>%s</div>'
                       % (_ca(k), '<span class="lx-bnr-tag">%s</span>' % html.escape(tags[0]) if tags else "",
                          '<span class="lx-bnr-ic">%s</span>' % icon_html(icon, 22) if icon else "", inline(text),
                          '<div class="lx-bnr-b">%s</div>' % body_html(it) if it["body"] else ""))
        return '<div class="lx-bnr-list">%s</div>' % "".join(out)
    if layout == "swimlane":
        lanes, maxc = [], 1
        seq = 0
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            steps, col = [], 0
            for s in _sub(it["body"]):
                m = re.match(r"^\s*(\d+)\s*[.:：)）]\s*(.+)$", s)
                if m:
                    col = int(m.group(1)); s = m.group(2)
                else:
                    col += 1
                steps.append((col, s))
                maxc = max(maxc, col)
            lanes.append((k, icon, text, steps))
        rows = []
        for k, icon, text, steps in lanes:
            cells = "".join('<div class="lx-swl-s" style="grid-column:%d;--c:%d"><span class="lx-swl-no">%d</span>%s</div>' % (c + 1, c, c, inline(s)) for c, s in steps)
            rows.append('<div class="lx-swl-lane" style="--ca:%s"><div class="lx-swl-h">%s%s</div>%s</div>'
                        % (_ca(k), icon_html(icon, 18) + " " if icon else "", inline(text), cells))
        return '<div class="lx-swl" style="--cols:%d">%s</div>' % (maxc, "".join(rows))
    if layout == "zigzag":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            a, b = _split_dash(text)
            h = inline(a)
            imgs = re.findall(r"<img[^>]*>", h)
            h = re.sub(r"<img[^>]*>", "", h).strip()
            vis = imgs[0] if imgs else (icon_html(icon, 64) if icon else '<span class="lx-zz-no">%02d</span>' % (k + 1))
            out.append('<div class="lx-zz-row%s" style="--ca:%s"><div class="lx-zz-v%s">%s</div><div class="lx-zz-t"><div class="lx-zz-h">%s</div>%s%s%s</div></div>'
                       % (" is-rev" if k % 2 else "", _ca(k), " has-img" if imgs else "", vis, h,
                          '<div class="lx-zz-tags">%s</div>' % "".join('<span>%s</span>' % html.escape(t) for t in tags) if tags else "",
                          '<p>%s</p>' % inline(b) if b else "", body_html(it)))
        return '<div class="lx-zz">%s</div>' % "".join(out)
    if layout == "rings":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            lab, val = _split_dash(text)
            m = _PCT.search(val) if val else None
            if not m and val == "":
                m2 = _STAT.match(text)
                if m2:
                    val, lab = m2.group(1).strip(), m2.group(2)
                    m = _PCT.search(val)
            v = float(m.group(1)) if m else 0.0
            mx = float(m.group(2)) if m and m.group(2) else 100.0
            f = max(0.0, min(1.0, v / mx if mx else 0))
            out.append('<div class="lx-rng" style="--ca:%s;--f:%.3f"><div class="lx-rng-o"><svg viewBox="0 0 120 120" aria-hidden="true">'
                       '<circle class="lx-rng-bg" cx="60" cy="60" r="50"/><circle class="lx-rng-fg" cx="60" cy="60" r="50" pathLength="100" '
                       'style="stroke-dashoffset:%.1f"/></svg><span class="lx-rng-v">%s</span></div><div class="lx-rng-l">%s%s</div>%s</div>'
                       % (_ca(k), f, 100 - 100 * f, html.escape(val), icon_html(icon, 16) + " " if icon else "", inline(lab),
                          '<div class="lx-rng-b">%s</div>' % body_html(it) if it["body"] else ""))
        return '<div class="lx-rng-row">%s</div>' % "".join(out)
    if layout == "ticker":
        chips = "".join('<li style="--ca:%s">%s%s%s</li>'
                        % (_ca(k), '<b>%s</b>' % html.escape(extract_decorations(it["text"])[1][0]) if extract_decorations(it["text"])[1] else "",
                           icon_html(extract_decorations(it["text"])[0], 16) + " " if extract_decorations(it["text"])[0] else "",
                           inline(extract_decorations(it["text"])[2])) for k, it in enumerate(items))
        return ('<div class="lx-tkr" style="--n:%d"><div class="lx-tkr-track"><ul>%s</ul><ul aria-hidden="true">%s</ul></div></div>'
                % (len(items), chips, chips))
    if layout == "bignum":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            a, b = _split_dash(text)
            out.append('<li class="lx-bn-i" style="--ca:%s"><span class="lx-bn-no" aria-hidden="true"><span>%02d</span></span><div class="lx-bn-t">'
                       '<div class="lx-bn-h">%s%s</div><i class="lx-bn-rule"></i>%s%s</div></li>'
                       % (_ca(k), k + 1, icon_html(icon, 20) + " " if icon else "", inline(a), '<p>%s</p>' % inline(b) if b else "", body_html(it)))
        return '<ol class="lx-bn">%s</ol>' % "".join(out)
    if layout == "sticky":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            a, b = _split_dash(text)
            out.append('<div class="lx-stk" style="--ca:%s;--r:%s"><i class="lx-stk-pin" aria-hidden="true"></i><div class="lx-stk-h">%s%s</div>%s%s%s</div>'
                       % (_ca(k), ["-2.5deg", "1.8deg", "-1deg", "2.6deg", "-1.8deg", "1deg"][k % 6], icon_html(icon, 18) + " " if icon else "", inline(a),
                          '<p>%s</p>' % inline(b) if b else "", body_html(it),
                          '<div class="lx-stk-tags">%s</div>' % "".join('<span>%s</span>' % html.escape(t) for t in tags) if tags else ""))
        return '<div class="lx-stk-wall">%s</div>' % "".join(out)
    if layout == "flip":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            a, b = _split_dash(text)
            back = ('<p>%s</p>' % inline(b) if b else "") + body_html(it)
            out.append('<div class="lx-flp" style="--ca:%s" tabindex="0"><div class="lx-flp-in"><div class="lx-flp-f">%s<div class="lx-flp-h">%s</div>'
                       '<span class="lx-flp-hint" aria-hidden="true">↻</span></div><div class="lx-flp-b"><div class="lx-flp-bh">%s</div>%s</div></div></div>'
                       % (_ca(k), '<div class="lx-flp-ic">%s</div>' % icon_html(icon, 36) if icon else "", inline(a), inline(a), back))
        return '<div class="lx-flp-grid">%s</div>' % "".join(out)
    if layout == "agenda":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            tm, rest = _split_dash(text)
            if not rest:
                m = re.match(r"^\s*(\d{1,2}[:：]\d{2}(?:\s*[〜~\-–]\s*\d{1,2}[:：]\d{2})?)\s*(.*)$", text)
                tm, rest = (m.group(1), m.group(2)) if m else ("", text)
            ti, de = _split_dash(rest)
            brk = any(re.search(r"休憩|break|昼食|lunch", t, re.I) for t in tags) or bool(re.search(r"^(?:休憩|昼食|break|lunch)", ti, re.I))
            out.append('<li class="lx-agd-i%s" style="--ca:%s"><time class="lx-agd-tm">%s</time><span class="lx-agd-dot" aria-hidden="true"></span>'
                       '<div class="lx-agd-c"><div class="lx-agd-h">%s%s%s</div>%s%s</div></li>'
                       % (" is-break" if brk else "", _ca(k), html.escape(tm), icon_html(icon, 16) + " " if icon else "", inline(ti),
                          "".join('<em>%s</em>' % html.escape(t) for t in tags), '<p>%s</p>' % inline(de) if de else "", body_html(it)))
        return '<ol class="lx-agd"><i class="lx-agd-line" aria-hidden="true"></i>%s</ol>' % "".join(out)
    if layout == "marker":
        out = []
        for k, it in enumerate(items):
            icon, tags, text = extract_decorations(it["text"])
            h = inline(text)
            if "<strong>" not in h:
                h = "<strong>%s</strong>" % h
            out.append('<li style="--ca:%s"><span class="lx-mk-ic" aria-hidden="true">%s</span><div><div class="lx-mk-t">%s</div>%s</div></li>'
                       % (_ca(k), icon_html(icon, 18) if icon else _ico("check", 18, "✓"), h, body_html(it)))
        return '<ul class="lx-mk">%s</ul>' % "".join(out)
    return ""


def render_tree(items):
    pos = [0]

    def node_html(text, children_html):
        parts = re.split(r"\s+(?:—|–|#|→)\s+", text, 1)
        name = inline(parts[0].strip())
        note = '<span class="tree-note">%s</span>' % inline(parts[1]) if len(parts) > 1 else ""
        is_dir = bool(children_html) or parts[0].strip().rstrip("`").endswith("/")
        cls = "tree-dir" if is_dir else "tree-file"
        head = '<span class="tree-name">%s</span>%s' % (name, note)
        if children_html:
            return '<li class="%s"><details open><summary>%s</summary>%s</details></li>' % (cls, head, children_html)
        return '<li class="%s"><span class="tree-row">%s</span></li>' % (cls, head)

    def parse(level):
        out = []
        while pos[0] < len(items) and items[pos[0]]["indent"] >= level:
            it = items[pos[0]]
            if it["indent"] > level:
                out.append(parse(it["indent"]))
                continue
            pos[0] += 1
            child = ""
            if pos[0] < len(items) and items[pos[0]]["indent"] > level:
                child = parse(items[pos[0]]["indent"])
            out.append(node_html(it["text"], child))
        return "<ul>%s</ul>" % "".join(out)
    inner = parse(items[0]["indent"])
    return '<div class="tree">%s</div>' % inner


_NUM_CELL = re.compile(r"^[+\-−]?[¥$€]?\d[\d,]*(?:\.\d+)?\s*[%％a-zA-Zぁ-んァ-ヶ一-龠]{0,4}$")


def _num_value(c):
    m = re.search(r"[+\-−]?\d[\d,]*(?:\.\d+)?", c)
    return float(m.group(0).replace(",", "").replace("−", "-")) if m else None


_MX_YES = re.compile(r"^(?:[✓✔◯○◎]|yes|y|あり|有|対応|可)$", re.I)
_MX_NO = re.compile(r"^(?:[✗✕×☓-]|no|n|なし|無|非対応|不可)$", re.I)


def render_matrix(header, rows):
    """機能の比較表: ✓・✗ を記号で描く。見出しの末尾に * を付けた列を強調する。"""
    hl = [c.strip().endswith("*") for c in header]
    th = "".join('<th%s>%s</th>' % (' class="mx-hl"' if hl[c] else "", inline(h.strip().rstrip("*").strip())) for c, h in enumerate(header))
    trs = []
    for r in rows:
        tds = []
        for c in range(len(header)):
            v = (r[c] if c < len(r) else "").strip()
            if c == 0:
                cell = inline(v)
            elif _MX_YES.match(v):
                cell = '<span class="mx-y">%s</span>' % _ico("check", 20, "✓")
            elif _MX_NO.match(v):
                cell = '<span class="mx-n">%s</span>' % _ico("x", 18, "✗")
            elif v in ("△", "▲", "一部"):
                cell = '<span class="mx-p">△</span>'
            else:
                cell = inline(v)
            tds.append('<td%s>%s</td>' % (' class="mx-hl"' if hl[c] else "", cell))
        trs.append("<tr>%s</tr>" % "".join(tds))
    return '<div class="table-wrap"><table class="mx"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (th, "".join(trs))


def render_raci(header, rows):
    """役割表（RACI）: R・A・C・I を色の札にする。"""
    th = "".join("<th>%s</th>" % inline(h) for h in header)
    trs = []
    for r in rows:
        tds = ["<td>%s</td>" % inline(r[0] if r else "")]
        for c in range(1, len(header)):
            v = (r[c] if c < len(r) else "").strip().upper()
            tds.append("<td>%s</td>" % "".join('<span class="raci raci-%s">%s</span>' % (ch.lower(), ch) for ch in re.findall(r"[RACI]", v)))
        trs.append("<tr>%s</tr>" % "".join(tds))
    legend = ('<div class="raci-legend"><span class="raci raci-r">R</span>実行 <span class="raci raci-a">A</span>説明責任 '
              '<span class="raci raci-c">C</span>相談 <span class="raci raci-i">I</span>報告</div>')
    return '<div class="table-wrap"><table class="raci-t"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>%s' % (th, "".join(trs), legend)


def render_table(header, rows, mode="auto"):
    if mode == "matrix":
        return render_matrix(header, rows)
    if mode == "raci":
        return render_raci(header, rows)
    ncol = len(header)
    tools = mode == "tools" or (mode == "auto" and len(rows) >= TABLE_TOOLS_ROWS)
    numeric = []
    for c in range(ncol):
        vals = [r[c].strip() for r in rows if c < len(r) and r[c].strip()]
        # 1 列目は行の見出し（「1月」「v2」など）なので数値の列にしない
        numeric.append(c > 0 and len(vals) >= 2 and all(_NUM_CELL.match(v.replace("**", "")) for v in vals))
    maxv = {}
    for c in range(ncol):
        if numeric[c]:
            vs = [_num_value(r[c]) for r in rows if c < len(r) and r[c].strip()]
            vs = [v for v in vs if v is not None]
            maxv[c] = max(vs) if vs and max(vs) > 0 and min(vs) >= 0 else None
    th = "".join('<th%s>%s</th>' % (' class="num"' if numeric[c] else "", inline(h)) for c, h in enumerate(header))
    trs = []
    for r in rows:
        tds = []
        for c in range(ncol):
            cell = r[c] if c < len(r) else ""
            if numeric[c] and cell.strip():
                v = _num_value(cell)
                bar = ""
                if tools and maxv.get(c) and v is not None:
                    bar = '<span class="nbar" style="--w:%.1f"></span>' % (100.0 * v / maxv[c])   # 単位なしの割合（CSS の calc で使う）
                tds.append('<td class="num" data-v="%s">%s<span class="nv">%s</span></td>' % (v, bar, inline(cell)))
            else:
                tds.append("<td>%s</td>" % inline(cell))
        trs.append("<tr>%s</tr>" % "".join(tds))
    return ('<div class="tablewrap%s" data-md2doc-table%s><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
            % (" tools" if tools else "", " data-table-tools" if tools else "", th, "".join(trs)))


def regroup_sections(out, lays, head_lay):
    """節単位の見せ方を組み立てる。
    walkthrough: 段落とコードが交互に続く所（2 組以上）を「左に説明・右にコード」に並べる。
    summary: 見出しから次の同じか上の見出しまでを要点の箱で包む。"""
    def kind(h):
        if h.startswith('<figure class="codeblock"'):
            return "code"
        if re.match(r"<h[1-6]\b", h):
            return "h"
        return "text"

    # walkthrough
    res, i = [], 0
    while i < len(out):
        if lays[i] != "walkthrough" or kind(out[i]) == "h":
            res.append(out[i]); i += 1
            continue
        j = i
        while j < len(out) and lays[j] == "walkthrough" and kind(out[j]) != "h":
            j += 1
        seg, rows, cur_t, cur_c = out[i:j], [], [], []
        for h in seg:
            if kind(h) == "code":
                cur_c.append(h)
            else:
                if cur_c:
                    rows.append((cur_t, cur_c)); cur_t, cur_c = [], []
                cur_t.append(h)
        if cur_t or cur_c:
            rows.append((cur_t, cur_c))
        pairs = [r for r in rows if r[0] and r[1]]
        if len(pairs) >= 2:
            html_rows = []
            for t, c in rows:
                if t and c:
                    html_rows.append('<div class="walk-row"><div class="walk-text">%s</div><div class="walk-code">%s</div></div>'
                                     % ("\n".join(t), "\n".join(c)))
                else:
                    html_rows.append('<div class="walk-solo">%s</div>' % "\n".join(t + c))
            res.append('<div class="walk">%s</div>' % "".join(html_rows))
        else:
            res.extend(seg)
        i = j
    # summary（見出しの位置は walkthrough で変わらない：見出しは組み替えない）
    final, i = [], 0
    heads = {}
    for n_, h in enumerate(out):
        if n_ in head_lay:
            heads[h] = head_lay[n_]
    while i < len(res):
        h = res[i]
        hl = heads.get(h)
        if hl and hl[1] == "summary":
            level = hl[0]
            j = i + 1
            while j < len(res):
                m = re.match(r"<h([1-6])\b", res[j])
                if m and int(m.group(1)) <= level:
                    break
                j += 1
            final.append('<section class="tldr">%s</section>' % "\n".join(res[i:j]))
            i = j
            continue
        final.append(h); i += 1
    return final


def suggest_layouts(lines):
    """節ごとのレイアウトの割り当て案（3f で提示する材料）。[(節名, レイアウト, 理由)]"""
    secs, cur, in_fence = [], None, False
    for ln in lines:
        if re.match(r"^\s{0,3}(`{3,}|~{3,})", ln):
            in_fence = not in_fence
            if cur is not None:
                cur["lines"].append(ln)
            continue
        hm = None if in_fence else re.match(r"^(#{2,3})\s+(.*)$", ln)
        if hm:
            cur = {"name": hm.group(2).strip(), "level": len(hm.group(1)), "lines": []}
            secs.append(cur)
            continue
        if cur is not None:
            cur["lines"].append(ln)
    out = []
    for si, sec in enumerate(secs):
        L = sec["lines"]
        items, i = [], 0
        while i < len(L):
            if re.match(r"^([-*+]|\d+\.)\s+", L[i]):
                its, i = collect_top_items(L, i)
                items += its
            else:
                i += 1
        name = sec["name"]
        texts = [it["text"] for it in items]
        n = len(items)
        paras_code, prev, fence = 0, None, False
        for ln in L:
            if re.match(r"^(`{3,}|~{3,})", ln):
                if not fence and prev == "p":
                    paras_code += 1          # 段落の直後に始まるコード
                fence = not fence
                prev = "code"
            elif not fence and ln.strip() and not re.match(r"^\s*([-*+]|\d+\.|#|>|\|)", ln):
                prev = "p"
        frac = lambda f: n and sum(1 for t in texts if f(t)) / n
        pick = None
        if re.search(r"^(概要|まとめ|要点|要約|サマリー?|summary|tl;?dr|結論)$", name, re.I) and si <= 1:
            pick = ("summary", "冒頭の要約の節")
        elif paras_code >= 2 and n <= 2:
            pick = ("walkthrough", "説明とコードが %d 組交互に続く" % paras_code)
        elif n >= 2 and frac(lambda t: re.match(r"^\[[ xX]\]\s", t)) >= .6:
            pick = ("checklist", "チェックボックスの項目が %d 件" % n)
        elif n >= 3 and frac(lambda t: bool(_STAT.match(t)) and _STAT.match(t).group(2)) >= .8 and n <= 6:
            pick = ("stats", "先頭が数値の項目が %d 件" % n)
        elif n >= 3 and frac(lambda t: bool(re.match(r"^(\*\*.+?\*\*|`[^`]+`|[^:：]{1,30})\s*[:：—–]\s*\S", t))) >= .7:
            pick = ("defs", "「用語: 説明」の形が %d 件" % n)
        elif n >= 2 and frac(lambda t: bool(re.search(r"(/|\.[a-z]{1,5}\b)", re.split(r"\s+(?:—|–|#|→)\s+", t)[0]))) >= .6 \
                and any(it["body"] for it in items):
            pick = ("tree", "パスの形の入れ子")
        elif 2 <= n <= 3 and all(it["body"] for it in items) and \
                (sum(1 for t in texts if _PROS.search(t) or _CONS.search(t)) >= 2 or
                 re.search(r"(比較|対比|違い|vs)", name, re.I)):
            pick = ("proscons", "%d 列の対比（小項目あり）" % n)
        elif 2 <= n <= 6 and all(len(it["body"]) >= 3 or any(re.match(r"^\s*(`{3,}|~{3,})", b) for b in it["body"]) for it in items) \
                and all(len(re.sub(r"[`*]", "", t)) <= 24 for t in texts):
            pick = ("tabs", "並列の %d 項目それぞれに長い中身・コード" % n)
        elif n >= 5 and all(not it["body"] for it in items) and all(len(re.sub(r"[`*]", "", t)) <= 14 for t in texts):
            pick = ("chips", "短い語が %d 件" % n)
        elif n >= 3 and all(it["ordered"] for it in items):
            pick = ("timeline", "番号付きの %d 工程" % n)
        elif n >= 8 and (sum(1 for it in items if it["body"]) >= n * .6 or
                         sum(1 for t in texts if re.search(r"[?？]$|^Q[.:：]", t)) >= 3):
            pick = ("accordion", "項目が %d 件で詳細を畳みたい" % n)
        elif n >= 3 and sum(1 for it in items if it["body"]) >= n * .6:
            pick = ("cards", "並列の %d 項目に小項目" % n)
        if pick:
            out.append((name, pick[0], pick[1]))
    return out


# 描画中テーマの配色サイクル（convert_file でセット）。
# hex ではなく var(--aN) を入れる — ライト/ダークで別配色に切り替わるため。
_ACCENTS = ["var(--a0)"]

# 先頭の絵文字（カードアイコン用）
_EMOJI = re.compile(r"^\s*([\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿️⃣]+)\s+")


_ICONS = [None]


def _icons():
    """隣の motion-video スキルの icons.py（線で描くアイコン集）を読み込む（無ければ None）。"""
    if _ICONS[0] is None:
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "motion-video", "icons.py")
        if not os.path.isfile(path):
            _ICONS[0] = False
        else:
            spec = importlib.util.spec_from_file_location("motion_video_icons", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _ICONS[0] = mod
    return _ICONS[0] or None


_ICON_TOKEN = re.compile(r"^:([a-z][a-z0-9-]*):\s*")


def icon_html(icon, size=22):
    """項目の icon（絵文字か :名前:）を HTML に。:名前: はアイコン集の SVG（無い名前はそのまま文字で）。"""
    if not icon:
        return ""
    m = _ICON_TOKEN.match(icon)
    ic = _icons()
    if m and ic and m.group(1) in ic.ICONS:
        return ic.svg(m.group(1), size)
    return html.escape(icon)


def extract_decorations(text):
    """項目テキストから 先頭絵文字 か :アイコン名:（icon）と 末尾 {タグ} 群 を取り出す。"""
    icon = ""
    m = _EMOJI.match(text) or _ICON_TOKEN.match(text)
    if m:
        icon = m.group(0).strip() if m.re is _ICON_TOKEN else m.group(1); text = text[m.end():]
    tags = []
    tm = re.search(r"((?:\s*\{[^{}]+\})+)\s*$", text)
    if tm:
        for tok in re.findall(r"\{([^{}]+)\}", tm.group(1)):
            tags += [t.strip() for t in re.split(r"[,，、]", tok) if t.strip()]
        text = text[:tm.start()]
    return icon, tags, text.strip()


def split_top_items(items):
    """トップレベル項目ごとに {label, icon, tags, children, ordered} へ分割。"""
    base = items[0]["indent"]
    groups, i = [], 0
    while i < len(items):
        it = items[i]
        text, cb = it["text"], ""
        cm = re.match(r"^\[([ xX])\]\s+(.*)$", text)
        if cm:
            cb = '<input type="checkbox" disabled %s> ' % ("checked" if cm.group(1).lower() == "x" else "")
            text = cm.group(2)
        icon, tags, text = extract_decorations(text)
        label = cb + inline(text)
        j = i + 1
        child = []
        while j < len(items) and items[j]["indent"] > base:
            child.append(items[j]); j += 1
        groups.append({"label": label, "icon": icon, "tags": tags,
                       "children": build_list(child) if child else "", "ordered": it["ordered"]})
        i = j
    return groups


def _ca(idx):
    return _ACCENTS[idx % len(_ACCENTS)]


# ──────────────────────────────────────────────────────────────────────────
# セクション別レイアウト
#   1つのドキュメント内でも「ここは手順だからタイムライン、ここは並列な機能だからカード、
#   ここは散文的な補足だから素の箇条書き」と使い分けたい。レイアウトは文書全体で画一に
#   決まるものではないので、--layout は **既定値（フォールバック）** とし、
#   セクション単位の指定を次の優先順で解決する。
#     1. md 内ディレクティブ `<!-- layout: cards -->`（見出し直後に置く。次の見出しまで有効）
#     2. `--layout-map "節名=cards,節名2=timeline"`（元 md を触らずに指定）
#     3. `--layout`（既定値）
#   freeform は文書全体を Claude が著述するモードなので、セクション単位には指定できない。
# ──────────────────────────────────────────────────────────────────────────
# リストの見せ方（節の中のトップレベル箇条書きに効く）と、節そのものの見せ方
MORE_LAYOUTS = ("hero", "quote", "pricing", "stepper", "kanban", "faq", "beforeafter", "gallery", "roadmap", "persona",
                "chevron", "counters", "rating", "dodont", "voices", "decision", "icongrid",
                "pyramid", "cycle", "quad", "chat", "calendar", "versus", "banner", "swimlane", "zigzag", "rings",
                "ticker", "bignum", "sticky", "flip", "agenda", "marker")
LIST_LAYOUTS = ("plain", "cards", "timeline", "accordion",
                "tabs", "checklist", "defs", "stats", "chips", "tree", "proscons") + MORE_LAYOUTS
SECTION_LAYOUTS = ("walkthrough", "summary")
DET_LAYOUTS = LIST_LAYOUTS + SECTION_LAYOUTS
FLAT_LAYOUTS = ("cards", "timeline", "accordion", "chips", "tree")     # 箇条書きの行だけで組む
RICH_LAYOUTS = ("tabs", "checklist", "defs", "stats", "proscons") + MORE_LAYOUTS     # 項目の中のコード・段落も使う
TABLE_DIRECTIVE_RE = re.compile(r"^\s*<!--\s*table\s*[:=]\s*(plain|tools|auto|matrix|raci)\s*-->\s*$", re.I)
TABLE_TOOLS_ROWS = 8
LAYOUT_DIRECTIVE_RE = re.compile(r"^\s*<!--\s*layout\s*[:=]\s*([\w-]+)\s*-->\s*$", re.I)
_LAYOUT_MAP = {}         # 正規化した節名/slug -> レイアウト
_LAYOUT_MAP_HIT = set()  # 実際に当たったキー（未使用キーの警告用）


def _norm_key(s):
    """節名の突き合わせ用キー。タグ・空白・記号を落として大小同一視する。"""
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"[\s　]+", "", s)
    return re.sub(r"[^\w\-ぁ-んァ-ヶ一-龠ー]", "", s).lower()


def parse_layout_map(spec):
    """--layout-map "導入手順=timeline,主な機能=cards" を dict にする。"""
    out = {}
    if not spec:
        return out
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            print("warn: --layout-map の項目に = がありません: %r（無視）" % chunk, file=sys.stderr)
            continue
        name, val = chunk.split("=", 1)
        key, val = _norm_key(name), val.strip().lower()
        if not key:
            print("warn: --layout-map の節名が空です: %r（無視）" % chunk, file=sys.stderr)
            continue
        if val not in DET_LAYOUTS:
            print("warn: --layout-map の値 %r は指定できません（%s のいずれか）。無視します。"
                  % (val, "/".join(DET_LAYOUTS)), file=sys.stderr)
            continue
        out[key] = val
    return out


def layout_for_section(text, slug, default):
    """節名または slug で --layout-map を引く。当たらなければ default（=--layout）。"""
    for key in (_norm_key(text), _norm_key(slug)):
        if key and key in _LAYOUT_MAP:
            _LAYOUT_MAP_HIT.add(key)
            return _LAYOUT_MAP[key]
    return default


def read_layout_directive(line):
    """`<!-- layout: cards -->` を読む。
    ディレクティブでなければ None、ディレクティブだが値が不正なら "" を返す
    （"" は「行は消費するがレイアウトは変えない」の意）。"""
    m = LAYOUT_DIRECTIVE_RE.match(line)
    if not m:
        return None
    val = m.group(1).lower()
    if val not in DET_LAYOUTS:
        hint = "（文書全体のモードなので節単位には指定できません）" if val == "freeform" else ""
        print("warn: <!-- layout: %s --> は指定できません%s。%s のいずれかにしてください。無視します。"
              % (val, hint, "/".join(DET_LAYOUTS)), file=sys.stderr)
        return ""
    return val


def extract_layout_directives(lines):
    """AI設計モード用。どの節に何が指定されていたかを [(節名, レイアウト)] で拾う。
    値が不正なものは警告して落とす（決定論モードの read_layout_directive と同じ基準）。"""
    found, cur, in_fence = [], "(冒頭)", False
    for ln in lines:
        if re.match(r"^\s{0,3}(`{3,}|~{3,})", ln):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        hm = re.match(r"^#{1,6}\s+(.*)$", ln)
        if hm:
            cur = hm.group(1).strip()
            continue
        m = LAYOUT_DIRECTIVE_RE.match(ln)
        if not m:
            continue
        val = m.group(1).lower()
        if val not in DET_LAYOUTS:
            hint = "（文書全体のモードなので節単位には指定できません）" if val == "freeform" else ""
            print("warn: 「%s」の <!-- layout: %s --> は指定できません%s。%s のいずれかに"
                  "してください。無視します。" % (cur, val, hint, "/".join(DET_LAYOUTS)),
                  file=sys.stderr)
            continue
        found.append((cur, val))
    return found


def render_list(items, layout):
    """トップレベルのリストを、選択レイアウト（cards/timeline/accordion）で描画。
    先頭絵文字→アイコン、末尾{タグ}→pill、カード色はテーマ配色を循環。"""
    if layout == "plain":
        return build_list(items)
    if layout == "tree":
        return render_tree(items)
    groups = split_top_items(items)
    if layout == "chips":
        chips = []
        for idx, g in enumerate(groups):
            tip = re.sub(r"<[^>]+>", " ", g["children"]).strip()
            chips.append('<span class="chip" style="--ca:%s"%s>%s%s</span>'
                         % (_ca(idx), ' title="%s"' % html.escape(re.sub(r"\s+", " ", tip), quote=True) if tip else "",
                            (icon_html(g["icon"], 16) + " ") if g["icon"] else "", g["label"]))
        return '<div class="chips chips-lg">%s</div>' % "".join(chips)

    def tags_html(g):
        if not g["tags"]:
            return ""
        return '<div class="doc-card-tags">%s</div>' % "".join(
            "<span>%s</span>" % html.escape(t) for t in g["tags"])

    if layout == "cards":
        cards = []
        for idx, g in enumerate(groups):
            ic = '<span class="doc-card-ic">%s</span>' % icon_html(g["icon"], 26) if g["icon"] else ""
            body = '<div class="doc-card-b">%s</div>' % g["children"] if g["children"] else ""
            cards.append(
                '<div class="doc-card" style="--ca:%s">'
                '<div class="doc-card-top">%s<div class="doc-card-h">%s</div></div>%s%s</div>'
                % (_ca(idx), ic, g["label"], tags_html(g), body))
        return '<div class="card-grid">%s</div>' % "".join(cards)

    if layout == "timeline":
        nodes = []
        for idx, g in enumerate(groups):
            badge = icon_html(g["icon"], 18) if g["icon"] else str(idx + 1)
            nodes.append(
                '<div class="tl-item" style="--ca:%s"><div class="tl-dot">%s</div>'
                '<div class="tl-body"><div class="tl-h">%s</div>%s%s</div></div>'
                % (_ca(idx), badge, g["label"], tags_html(g), g["children"]))
        return '<div class="timeline">%s</div>' % "".join(nodes)

    if layout == "accordion":
        rows = []
        for idx, g in enumerate(groups):
            ic = (icon_html(g["icon"], 18) + " ") if g["icon"] else ""
            body = '<div class="acc-body">%s</div>' % g["children"] if g["children"] else ""
            rows.append(
                '<details class="acc-item" style="--ca:%s"%s><summary>%s%s%s</summary>%s</details>'
                % (_ca(idx), " open" if idx == 0 else "", ic, g["label"], tags_html(g), body))
        return '<div class="accordion">%s</div>' % "".join(rows)
    return build_list(items)


# ──────────────────────────────────────────────────────────────────────────
# frontmatter
# ──────────────────────────────────────────────────────────────────────────
def split_frontmatter(text):
    meta = {}
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        if m:
            for ln in m.group(1).splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"').strip("'")
            text = text[m.end():]
    return meta, text


# ──────────────────────────────────────────────────────────────────────────
# mermaid → SVG
# ──────────────────────────────────────────────────────────────────────────
def _uniquify_svg_ids(svg, suffix):
    """SVG 内の id と、それを指す参照(url(#x) / href="#x" / style内 #x)に接尾辞を付ける。
    同一ページにライト用・ダーク用の2枚を同時に埋め込むと id が衝突し、
    marker（矢印）や内部 <style> が誤ったほうを参照するため。"""
    ids = sorted(set(re.findall(r'\bid="([^"]+)"', svg)), key=len, reverse=True)
    for i in ids:
        esc = re.escape(i)
        new = i + suffix
        svg = re.sub(r'\bid="%s"' % esc, lambda m, n=new: 'id="%s"' % n, svg)
        # 参照側: 直後が識別子文字なら別 id なので置換しない
        svg = re.sub(r"#%s(?![\w:.-])" % esc, lambda m, n=new: "#" + n, svg)
    return svg


def _read_svg(path):
    with open(path) as f:
        return re.sub(r"<\?xml[^>]*\?>", "", f.read()).strip()


def render_mermaid(sources, theme):
    """各図を「ライト用」「ダーク用」の2枚 SVG にして返す。
    表示モードに応じて CSS(.mm-light/.mm-dark) が出し分ける。"""
    if not sources:
        return {}, True
    mmdc = shutil.which("mmdc")
    if not mmdc:
        return {}, False
    result = {}
    tmp = tempfile.mkdtemp(prefix="md2doc_")
    try:
        pup = os.path.join(tmp, "pup.json")
        with open(pup, "w") as f:
            json.dump({"args": ["--no-sandbox", "--disable-setuid-sandbox"]}, f)
        cfgs = {}
        for mode, key in (("light", "mermaid"), ("dark", "mermaid_dark")):
            p = os.path.join(tmp, "cfg_%s.json" % mode)
            with open(p, "w") as f:
                json.dump(theme[key], f)
            cfgs[mode] = p

        for idx, src in enumerate(sources):
            inp = os.path.join(tmp, "d%d.mmd" % idx)
            with open(inp, "w") as f:
                f.write(src)
            svgs = {}
            for mode in ("light", "dark"):
                outp = os.path.join(tmp, "d%d_%s.svg" % (idx, mode))
                try:
                    subprocess.run([mmdc, "-i", inp, "-o", outp, "-c", cfgs[mode], "-p", pup,
                                    "-b", "transparent"],
                                   check=True, capture_output=True, timeout=90)
                    svgs[mode] = _read_svg(outp)
                except Exception:
                    svgs[mode] = None
            if svgs["light"] and svgs["dark"]:
                result[idx] = ('<figure class="mermaid-fig" id="md2doc-mm-%d">'
                               '<div class="mm-light">%s</div>'
                               '<div class="mm-dark">%s</div></figure>'
                               % (idx, svgs["light"], _uniquify_svg_ids(svgs["dark"], "-mmdark")))
            elif svgs["light"] or svgs["dark"]:
                # 片方だけ描けたなら両モードでそれを使う（無いよりまし）
                result[idx] = '<figure class="mermaid-fig" id="md2doc-mm-%d">%s</figure>' % (
                    idx, svgs["light"] or svgs["dark"])
            else:
                result[idx] = None
        return result, True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def manual_mermaid_figure(eid, src):
    """mmdc が無い時のフォールバック。Claude が後段でこの figure 全体を
    テーマ配色の <svg> 図に差し替える前提のマーカー付き枠。差し替えられなくても
    定義がそのまま読めるよう、コードブロックを残しておく。"""
    b64 = base64.b64encode(src.encode("utf-8")).decode("ascii")
    return ('<figure class="mermaid-fig manual-render" id="%s" data-mermaid-b64="%s">\n'
            '<!-- MD2DOC_RENDER id=%s : この figure 全体を、テーマ配色の <svg> 図に置き換えてください。'
            ' mermaid定義は data-mermaid-b64 属性 / 下の code 要素にあります -->\n'
            '<div class="mermaid-note">⚠ mermaid 未レンダリング（定義のみ表示）</div>\n'
            '<pre><code class="lang-mermaid">%s</code></pre>\n'
            '</figure>' % (eid, b64, eid, html.escape(src)))


# 図示フォールバック時に Claude へ渡すテーマ配色（描画用パレット）
PALETTE_KEYS = ["--bg", "--card", "--ink", "--muted", "--line",
                "--accent", "--accent-2", "--accent-soft", "--on-accent", "--font"]


def theme_palette(theme_key):
    """SVG 等で使う配色。ライト/ダーク両対応にするため、**必ず CSS 変数参照**を使う。
    hex は「どんな色か」を把握するための参考値。"""
    t = THEMES[theme_key]
    light, dark = t["vars"], t["vars_dark"]
    keys = [k for k in PALETTE_KEYS if k in light]
    return {
        "use": {k.lstrip("-"): "var(%s)" % k for k in keys},
        "accents": accent_vars(theme_key),
        "ref_light": {k.lstrip("-"): light[k] for k in keys},
        "ref_dark": {k.lstrip("-"): dark.get(k, light[k]) for k in keys},
        "note": "色は必ず var(--accent) 等の CSS 変数で指定する。hex 直書きはダークモードで破綻する。",
    }


# ──────────────────────────────────────────────────────────────────────────
# テンプレート
# ──────────────────────────────────────────────────────────────────────────
STATIC_CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:var(--font);color:var(--ink);background:var(--bg);line-height:1.85;
  -webkit-font-smoothing:antialiased}
.progress-track{position:fixed;top:0;left:0;right:0;height:7px;z-index:200;cursor:pointer;background:transparent}
.progress-track:hover{background:color-mix(in srgb,var(--accent) 14%,transparent)}
.progress{position:absolute;top:0;left:0;height:3px;width:0;background:var(--accent);transition:width .1s;pointer-events:none}
.topbar{position:fixed;top:0;left:0;right:0;height:var(--nav-h);z-index:100;
  background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line)}
.topbar-inner{max-width:var(--maxw);margin:0 auto;height:100%;padding:0 24px;
  display:flex;align-items:center;gap:20px}
.brand{font-family:var(--font-head);font-weight:800;font-size:15px;color:var(--accent);
  white-space:nowrap;text-decoration:none;display:block;
  /* 余白がある限り全文を出し、本当に入り切らない時だけ CSS で省略する */
  flex:0 1 auto;min-width:0;max-width:52%;overflow:hidden;text-overflow:ellipsis}
.nav-menu{display:flex;gap:3px;margin-left:auto;min-width:0;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:thin;scrollbar-color:var(--line) transparent}
.nav-menu::-webkit-scrollbar{height:6px}
.nav-menu::-webkit-scrollbar-thumb{background:var(--line);border-radius:6px}
.nav-menu::-webkit-scrollbar-thumb:hover{background:var(--muted)}
.nav-menu::-webkit-scrollbar-track{background:transparent}
.nav-menu a{font-family:var(--font-head);font-size:13px;font-weight:700;color:var(--muted);
  text-decoration:none;padding:7px 13px;border-radius:8px;transition:.18s;white-space:nowrap;flex:0 0 auto}
.nav-menu a:hover{color:var(--accent);background:var(--accent-soft)}
.nav-menu a.active{color:var(--on-accent);background:var(--accent)}
.topbar-tools{display:flex;align-items:center;gap:10px;flex:0 0 auto}
.hamburger{display:none;background:none;border:1px solid var(--line);
  border-radius:8px;padding:6px 10px;color:var(--ink);font-size:18px;cursor:pointer}
/* サイドメニューの展開/非表示トグル（サイド目次があるときだけ出す） */
.toc-toggle{display:none;align-items:center;justify-content:center;flex:0 0 auto;
  width:32px;height:30px;padding:0;background:none;border:1px solid var(--line);
  border-radius:8px;color:var(--muted);cursor:pointer;transition:.15s}
.toc-toggle:hover{color:var(--accent);background:var(--accent-soft);border-color:var(--accent)}
.toc-toggle:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* 表示モード切替（ライト / ダーク / システム設定） */
.mode-switch{display:inline-flex;gap:2px;padding:3px;border:1px solid var(--line);
  border-radius:999px;background:color-mix(in srgb,var(--card) 65%,transparent)}
.mode-switch button{width:30px;height:26px;display:flex;align-items:center;justify-content:center;
  border:none;border-radius:999px;background:none;color:var(--muted);font-size:13px;line-height:1;
  cursor:pointer;transition:.15s}
.mode-switch button:hover{color:var(--accent);background:var(--accent-soft)}
.mode-switch button[aria-pressed="true"]{background:var(--accent);color:var(--on-accent)}
.mode-switch button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* 文字の設定（書体・大きさ）。テーマの変数より後に置いて上書きする */
.type-switch{position:relative;display:inline-flex}
.type-btn{height:32px;min-width:40px;padding:0 10px;margin-left:6px;border:1px solid var(--line);border-radius:999px;
  background:color-mix(in srgb,var(--card) 65%,transparent);color:var(--muted);font:700 13px/1 var(--font-head);cursor:pointer;transition:.15s}
.type-btn:hover,.type-btn[aria-expanded="true"]{color:var(--accent);border-color:var(--accent);background:var(--accent-soft)}
.type-btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.type-panel{position:absolute;right:6px;top:calc(100% + 8px);z-index:300;display:flex;flex-direction:column;gap:10px;
  min-width:286px;padding:12px 14px;background:var(--card);color:var(--ink);border:1px solid var(--line);
  border-radius:12px;box-shadow:0 10px 28px rgba(0,0,0,.2)}
.type-panel[hidden]{display:none}
.type-row{display:flex;align-items:center;gap:10px}
.type-lab{font-size:12px;font-weight:700;color:var(--muted);min-width:3.6em}
.type-seg{display:flex;gap:2px;padding:3px;border:1px solid var(--line);border-radius:999px}
.type-seg button{border:0;background:none;color:var(--muted);font-size:12.5px;line-height:1.2;padding:5px 10px;
  border-radius:999px;cursor:pointer;white-space:nowrap}
.type-seg button:hover{color:var(--accent);background:var(--accent-soft)}
.type-seg button[aria-pressed="true"]{background:var(--accent);color:var(--on-accent)}
.type-seg button:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.type-seg [data-ff="gothic"]{font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif}
.type-seg [data-ff="mincho"]{font-family:"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif}
.type-seg [data-ff="ud"]{font-family:"BIZ UDPGothic","Hiragino Kaku Gothic ProN",sans-serif}
:root[data-ff="gothic"]{--font:"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif;
  --font-head:"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif}
:root[data-ff="mincho"]{--font:"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif;
  --font-head:"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif}
:root[data-ff="ud"]{--font:"BIZ UDPGothic","Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif;
  --font-head:"BIZ UDPGothic","Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif}
:root[data-fs="s"] .content{zoom:.9}
:root[data-fs="l"] .content{zoom:1.15}
:root[data-fs="xl"] .content{zoom:1.3}
@media(max-width:560px){.type-panel{right:-40px}}
[id]{scroll-margin-top:calc(var(--nav-h) + 16px)}
.hero{background:var(--header-bg);color:var(--header-fg);
  padding:calc(var(--nav-h) + 52px) 24px 52px;margin-bottom:8px}
.hero-inner{max-width:var(--maxw);margin:0 auto}
.hero .eyebrow{display:inline-block;font-size:13px;letter-spacing:.12em;font-weight:700;
  background:color-mix(in srgb,var(--header-fg) 18%,transparent);padding:6px 14px;border-radius:999px;margin-bottom:18px}
.hero h1{font-family:var(--font-head);font-size:36px;line-height:1.35;font-weight:800}
.hero .date{margin-top:14px;opacity:.85;font-size:14px}
.hero .tags{margin-top:16px;display:flex;gap:8px;flex-wrap:wrap}
.hero .tags span{font-size:12px;font-weight:700;background:color-mix(in srgb,var(--header-fg) 16%,transparent);
  padding:4px 12px;border-radius:999px}
.layout{max-width:var(--maxw);margin:0 auto;padding:0 24px 90px;display:grid;
  grid-template-columns:220px 1fr;gap:40px;align-items:start}
.toc{position:sticky;top:calc(var(--nav-h) + 24px);max-height:calc(100vh - var(--nav-h) - 48px);overflow-y:auto;overscroll-behavior:contain;font-size:13.5px;padding-right:8px;scrollbar-width:thin;scrollbar-color:var(--line) transparent}
.toc::-webkit-scrollbar{width:8px}
.toc::-webkit-scrollbar-thumb{background:var(--line);border-radius:8px}
.toc::-webkit-scrollbar-thumb:hover{background:var(--muted)}
.toc::-webkit-scrollbar-track{background:transparent}
/* 見出し＋検索欄は目次内スクロールでも常に見えるよう上端に固定 */
.toc-head{position:sticky;top:0;z-index:1;background:var(--bg);padding:32px 0 10px}
.toc .toc-ttl{font-family:var(--font-head);font-weight:800;font-size:12px;letter-spacing:.1em;
  color:var(--muted);margin-bottom:10px}
.toc a{display:block;color:var(--muted);text-decoration:none;padding:4px 10px;border-left:2px solid var(--line);
  transition:.15s}
.toc a.lv3{padding-left:22px;font-size:12.5px}
.toc a:hover{color:var(--accent)}
.toc a.active{color:var(--accent);border-left-color:var(--accent);font-weight:700}
/* 目次の検索欄 */
.toc-search{display:block;width:100%;box-sizing:border-box;padding:6px 10px;
  -webkit-appearance:none;appearance:none;
  font-family:var(--font);font-size:12.5px;color:var(--ink);
  background:var(--card);border:1px solid var(--line);border-radius:8px}
.toc-search::placeholder{color:var(--muted);opacity:.9}
.toc-search:focus{outline:none;border-color:var(--accent);
  box-shadow:0 0 0 2px var(--accent-soft)}
.toc-empty{display:none;color:var(--muted);font-size:12px;padding:6px 10px}
/* 章（h2）単位のアコーディオン */
.toc-sec{margin-bottom:2px}
.toc-row{display:flex;align-items:stretch;gap:2px}
.toc-row>a{flex:1 1 auto;min-width:0}
.toc-acc{flex:0 0 auto;width:22px;padding:0;background:none;border:none;border-radius:6px;
  color:var(--muted);font-size:10px;line-height:1;cursor:pointer;transition:.15s}
.toc-acc:hover{color:var(--accent);background:var(--accent-soft)}
.toc-acc:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.toc-caret{display:inline-block;transition:transform .18s}
.toc-acc[aria-expanded="false"] .toc-caret{transform:rotate(-90deg)}
.toc-sec.collapsed .toc-sub{display:none}
.toc-sec.no-sub .toc-acc{visibility:hidden}
/* 検索中は章の開閉状態に関わらず、ヒットした項目をすべて見せる */
.toc.toc-searching .toc-sec .toc-sub{display:block}
.toc.toc-searching .toc-acc{visibility:hidden}
.toc .toc-hide{display:none}
.content{min-width:0;padding-top:32px}
.content h2.hl{font-family:var(--font-head);font-size:23px;font-weight:800;margin:48px 0 18px;
  padding-left:14px;border-left:5px solid var(--accent);color:var(--accent-2)}
.content h2.hl:first-child{margin-top:0}
.content h3.hl{font-family:var(--font-head);font-size:18px;font-weight:700;margin:30px 0 10px}
.content h4{font-family:var(--font-head);font-size:15.5px;margin:22px 0 8px}
.anchor{opacity:0;margin-left:8px;color:var(--accent);text-decoration:none;font-weight:400}
.hl:hover .anchor{opacity:.5}
.content p{margin:12px 0}
.md-img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px;
  box-shadow:0 1px 4px rgba(0,0,0,.06);margin:4px 0;vertical-align:top}
.content a{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--accent) 40%,transparent)}
.content ul,.content ol{margin:12px 0 12px 4px;padding-left:22px}
.content li{margin:6px 0}
.content ul ul,.content ol ol,.content ul ol,.content ol ul{margin:6px 0}
.content ul{list-style:none}
.content ul>li{position:relative;padding-left:18px}
.content ul>li::before{content:"";position:absolute;left:2px;top:12px;width:6px;height:6px;
  border-radius:50%;background:var(--accent)}
.content ol{list-style:decimal;color:var(--ink)}
.content li input[type=checkbox]{margin-right:6px}
.content strong{font-weight:800}
code{font-family:var(--mono);font-size:.88em;background:var(--accent-soft);
  padding:2px 6px;border-radius:5px;color:var(--accent-2)}
.codeblock{position:relative;margin:18px 0}
.codeblock pre{background:var(--code-bg);color:var(--code-fg);border-radius:var(--radius);
  padding:18px 20px;overflow:auto}
.codeblock pre code{background:none;color:inherit;padding:0;font-size:13px;line-height:1.7}
.copy-btn{position:absolute;top:10px;right:10px;font-family:var(--font-head);font-size:11px;font-weight:700;
  background:rgba(255,255,255,.12);color:#fff;border:1px solid rgba(255,255,255,.25);
  border-radius:6px;padding:4px 10px;cursor:pointer;transition:.15s}
.copy-btn:hover{background:rgba(255,255,255,.25)}
.copy-btn.done{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.tablewrap{overflow-x:auto;margin:18px 0}
table{border-collapse:collapse;width:100%;font-size:14px;background:var(--card);
  border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow)}
th,td{padding:10px 14px;text-align:left;border-bottom:1px solid var(--line)}
th{background:var(--accent-soft);font-family:var(--font-head);font-weight:800;color:var(--accent-2)}
tbody tr:hover{background:color-mix(in srgb,var(--accent-soft) 50%,transparent)}
blockquote{margin:16px 0;padding:8px 18px;border-left:3px solid var(--line);color:var(--muted)}
.callout{margin:18px 0;border-radius:var(--radius);overflow:hidden;border:1px solid var(--line);
  background:var(--card);box-shadow:var(--shadow)}
.callout-head{font-family:var(--font-head);font-weight:800;font-size:14px;padding:10px 16px;
  display:flex;align-items:center;gap:8px}
.callout-body{padding:4px 16px 14px}
.callout-body p:first-child{margin-top:4px}
.callout-note{--c:#3b82f6}.callout-tip{--c:#10b981}.callout-important{--c:#8b5cf6}
.callout-warning{--c:#f59e0b}.callout-caution{--c:#ef4444}
.callout{border-left:4px solid var(--c,var(--accent))}
.callout-head{background:color-mix(in srgb,var(--c,var(--accent)) 12%,var(--card));color:var(--c,var(--accent))}
.mermaid-fig{margin:22px 0;text-align:center;background:var(--card);border:1px solid var(--line);
  border-radius:var(--radius);padding:18px;box-shadow:var(--shadow)}
.mermaid-fig svg{max-width:100%;height:auto}
.mermaid-note{font-size:12px;color:var(--muted);padding:8px 16px}
/* mermaid はライト用/ダーク用の2枚を埋め込み、表示モードで出し分ける */
.mm-dark{display:none}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]) .mm-light{display:none}
  :root:not([data-theme="light"]) .mm-dark{display:block}
}
:root[data-theme="dark"] .mm-light{display:none}
:root[data-theme="dark"] .mm-dark{display:block}
:root[data-theme="light"] .mm-light{display:block}
:root[data-theme="light"] .mm-dark{display:none}
.auto-fig-slot{margin:18px 0}
.auto-fig-slot:empty{display:none;margin:0}
/* セクション直下リストのレイアウト */
.card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;margin:18px 0}
.doc-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px 22px;box-shadow:var(--shadow);border-top:4px solid var(--ca,var(--accent))}
.doc-card-top{display:flex;align-items:center;gap:12px;margin-bottom:8px}
.ico{display:inline-block;vertical-align:-.2em;flex:none;overflow:visible}
.doc-card-ic .ico{color:var(--ca,var(--accent))}
.doc-card-ic{flex:0 0 auto;width:42px;height:42px;border-radius:12px;display:flex;align-items:center;
  justify-content:center;font-size:22px;background:color-mix(in srgb,var(--ca,var(--accent)) 15%,var(--card))}
.doc-card-h{font-family:var(--font-head);font-weight:800;font-size:16px;color:var(--ca,var(--accent-2));line-height:1.4}
.doc-card-tags{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}
.doc-card-tags span,.tl-body .doc-card-tags span,.acc-item .doc-card-tags span{font-size:11.5px;font-weight:700;
  color:var(--ca,var(--accent));background:color-mix(in srgb,var(--ca,var(--accent)) 12%,var(--card));
  padding:2px 9px;border-radius:999px}
.doc-card-b{font-size:14px}
.doc-card-b ul,.doc-card-b ol{margin:6px 0 0}
.doc-card ul>li::before{background:var(--ca,var(--accent))}
.timeline{margin:18px 0;padding-left:4px}
.tl-item{position:relative;display:grid;grid-template-columns:44px 1fr;gap:16px}
.tl-item:not(:last-child)::before{content:"";position:absolute;left:21px;top:44px;bottom:-6px;width:2px;background:var(--line)}
.tl-dot{width:44px;height:44px;border-radius:50%;background:var(--ca,var(--accent));color:var(--on-accent);
  font-family:var(--font-head);font-weight:800;font-size:17px;display:flex;align-items:center;justify-content:center;z-index:1}
.tl-body{padding-bottom:22px;min-width:0}
.tl-h{font-family:var(--font-head);font-weight:800;font-size:16px;margin-top:8px}
.tl-body .doc-card-tags{margin-top:6px}
.acc-item>summary .doc-card-tags{display:inline-flex;margin:0 0 0 4px}
.accordion{margin:18px 0;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:var(--card)}
.acc-item{border-bottom:1px solid var(--line)}
.acc-item:last-child{border-bottom:none}
.acc-item>summary{cursor:pointer;list-style:none;padding:14px 18px;font-family:var(--font-head);
  font-weight:700;display:flex;align-items:center;gap:10px}
.acc-item>summary::-webkit-details-marker{display:none}
.acc-item>summary::before{content:"▶";color:var(--ca,var(--accent));font-size:11px;transition:.2s;flex:0 0 auto}
.acc-item[open]>summary::before{transform:rotate(90deg)}
.acc-item>summary:hover{background:var(--accent-soft)}
.acc-body{padding:2px 18px 16px 40px}
@media(max-width:560px){.tl-item{grid-template-columns:36px 1fr;gap:12px}
  .tl-dot{width:36px;height:36px}.tl-item:not(:last-child)::before{left:17px;top:36px}}
/* 汎用コンポーネント（freeform=AI設計 で使える部品） */
.lead{font-size:18px;line-height:1.85;margin:14px 0 6px;border-left:3px solid var(--accent);padding-left:18px}
.feature-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin:18px 0}
.stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin:18px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:22px 18px;text-align:center;box-shadow:var(--shadow)}
.stat .big{font-family:var(--font-head);font-size:40px;font-weight:800;line-height:1;color:var(--ca,var(--accent))}
.stat .cap{margin-top:8px;font-size:13px;font-weight:700;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.chip{font-family:var(--mono);font-size:12px;font-weight:700;color:var(--accent-2);
  background:var(--accent-soft);border:1px solid color-mix(in srgb,var(--accent) 25%,transparent);
  padding:3px 10px;border-radius:8px}
.badge{display:inline-block;font-size:11.5px;font-weight:800;padding:3px 10px;border-radius:999px;
  color:var(--on-accent);background:var(--ca,var(--accent))}
.split{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:18px 0}
@media(max-width:680px){.split{grid-template-columns:1fr}}
/* 追加のレイアウト */
.tabs{margin:18px 0;border:1px solid var(--line);border-radius:var(--radius);background:var(--card);overflow:hidden}
.tab-list{display:flex;flex-wrap:wrap;gap:2px;border-bottom:1px solid var(--line);background:var(--accent-soft);padding:6px 6px 0}
.tab-list [role=tab]{font:inherit;font-family:var(--font-head);font-weight:700;font-size:14px;border:0;background:none;
  color:var(--muted);padding:9px 16px;border-radius:10px 10px 0 0;cursor:pointer;border-bottom:3px solid transparent}
.tab-list [role=tab][aria-selected=true]{background:var(--card);color:var(--ca,var(--accent-2));border-bottom-color:var(--ca,var(--accent))}
.tab-list [role=tab]:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.tab-panel{padding:6px 20px 14px}
.tab-panel:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.tab-print-h{font-family:var(--font-head);font-weight:800;margin:12px 0 4px;color:var(--accent-2)}
.tabs-js .tab-print-h{display:none}
.tabs-js .tab-panel[hidden]{display:none}
.tabs:not(.tabs-js) .tab-list{display:none}
.tabs:not(.tabs-js) .tab-panel+.tab-panel{border-top:1px solid var(--line)}
.checklist{margin:18px 0;border:1px solid var(--line);border-radius:var(--radius);background:var(--card);padding:14px 18px}
.ck-head{display:flex;align-items:center;gap:12px;margin-bottom:6px}
.ck-bar{flex:1;height:8px;border-radius:99px;background:var(--accent-soft);overflow:hidden}
.ck-bar i{display:block;height:100%;background:var(--accent);border-radius:99px;transition:width .3s}
.ck-count{font-family:var(--mono);font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.ck-reset{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--card);color:var(--muted);border-radius:8px;padding:3px 10px;cursor:pointer}
.content .ck-list{list-style:none;padding:0;margin:0}
.content .ck-list>li{padding:8px 0 8px 0;border-top:1px solid var(--line);margin:0}
.content .ck-list>li:first-child{border-top:0}
.content .ck-list>li::before{display:none}
.ck-list label{display:flex;gap:10px;align-items:flex-start;cursor:pointer}
.ck-list input{width:18px;height:18px;margin:3px 0 0;accent-color:var(--accent);flex:0 0 auto}
.ck-list input:checked+.ck-text{color:var(--muted);text-decoration:line-through}
.ck-body{padding-left:28px;font-size:14px;color:var(--muted)}
.defs-wrap{margin:18px 0}
.defs-filter{font:inherit;font-size:14px;width:100%;max-width:320px;padding:7px 12px;border:1px solid var(--line);
  border-radius:8px;background:var(--card);color:var(--ink);margin-bottom:10px}
.defs{margin:0;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:var(--card)}
.def{display:grid;grid-template-columns:minmax(120px,30%) 1fr;border-top:1px solid var(--line)}
.def:first-child{border-top:0}
.def dt{font-family:var(--font-head);font-weight:800;color:var(--accent-2);padding:11px 16px;background:var(--accent-soft)}
.def dd{margin:0;padding:11px 16px;min-width:0}
.def dd>:first-child{margin-top:0}.def dd>:last-child{margin-bottom:0}
@media(max-width:560px){.def{grid-template-columns:1fr}.def dt{padding-bottom:4px}}
.stat-note{margin-top:8px;font-size:12.5px;color:var(--muted);text-align:left}
.chips-lg{gap:10px;margin:14px 0}
.chips-lg .chip{font-family:var(--font);font-size:13.5px;color:var(--ca,var(--accent-2));
  background:color-mix(in srgb,var(--ca,var(--accent)) 12%,var(--card));
  border-color:color-mix(in srgb,var(--ca,var(--accent)) 35%,transparent);padding:5px 14px;border-radius:999px}
.tree{margin:18px 0;padding:14px 18px;border:1px solid var(--line);border-radius:var(--radius);background:var(--card);
  font-family:var(--mono);font-size:13.5px;overflow-x:auto}
.content .tree ul{list-style:none;margin:0;padding:0}
.content .tree ul ul{margin-left:8px;padding-left:16px;border-left:1px dashed var(--line)}
.content .tree li{margin:0;padding:0}
.content .tree li::before{display:none}
.tree summary{cursor:pointer;list-style:none;display:flex;gap:10px;align-items:baseline;padding:3px 0}
.tree summary::-webkit-details-marker{display:none}
.tree-row{display:flex;gap:10px;align-items:baseline;padding:3px 0}
.tree-name::before{content:"";display:inline-block;width:10px;height:12px;margin-right:8px;border:1.5px solid var(--muted);
  border-radius:2px;vertical-align:-1px}
.tree-dir>details>summary>.tree-name::before,.tree-dir>.tree-row>.tree-name::before{width:14px;height:10px;border:0;
  border-radius:2px 2px 3px 3px;background:var(--accent);opacity:.85}
.tree-dir>details:not([open])>summary>.tree-name::before{opacity:.45}
.tree-dir>details>summary>.tree-name,.tree-dir>.tree-row>.tree-name{font-weight:700;color:var(--accent-2)}
.tree-note{font-family:var(--font);font-size:12.5px;color:var(--muted)}
.tree code{background:none;padding:0;color:inherit}
.pc-grid{display:grid;grid-template-columns:repeat(var(--cols,2),minmax(0,1fr));gap:16px;margin:18px 0}
@media(max-width:680px){.pc-grid{grid-template-columns:1fr}}
.pc-col{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);overflow:hidden;
  border-top:4px solid var(--ca,var(--accent))}
.pc-pro{--ca:#16a34a}.pc-con{--ca:#dc2626}
.pc-h{font-family:var(--font-head);font-weight:800;padding:12px 16px 4px;color:var(--ca,var(--accent-2))}
.pc-b{padding:0 16px 12px;font-size:14px}
.pc-pro .pc-b ul>li::before{content:"✓";background:none;width:auto;height:auto;top:0;left:0;color:var(--ca);font-weight:800}
.pc-con .pc-b ul>li::before{content:"!";background:none;width:auto;height:auto;top:0;left:3px;color:var(--ca);font-weight:800}
.walk{margin:18px 0;display:flex;flex-direction:column;gap:14px}
.walk-row{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:22px;align-items:start}
.walk-row .codeblock{margin:0}
.walk-text>:first-child{margin-top:0}
@media(max-width:820px){.walk-row{grid-template-columns:1fr;gap:6px}}
.tldr{margin:10px 0 28px;padding:4px 24px 16px;border-radius:var(--radius);background:var(--accent-soft);
  border:1px solid color-mix(in srgb,var(--accent) 30%,transparent);border-left:5px solid var(--accent)}
.tldr>h2.hl,.tldr>h3.hl{margin-top:14px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
td.num{position:relative}
td.num .nv{position:relative}
.nbar{position:absolute;left:6px;top:7px;bottom:7px;width:calc((100% - 12px) * var(--w) / 100);
  background:color-mix(in srgb,var(--accent) 16%,transparent);border-radius:3px}
.tablewrap.tools{max-height:560px;overflow:auto;border-radius:var(--radius)}
.tablewrap.tools thead th{position:sticky;top:0;z-index:1}
.tablewrap.tools th[aria-sort]{cursor:pointer;user-select:none;white-space:nowrap}
.tablewrap.tools th[aria-sort]::after{content:"↕";margin-left:6px;font-size:11px;opacity:.45}
.tablewrap.tools th[aria-sort=ascending]::after{content:"▲";opacity:.9}
.tablewrap.tools th[aria-sort=descending]::after{content:"▼";opacity:.9}
.tbl-tools{display:flex;gap:10px;align-items:center;margin:18px 0 -10px}
.tbl-filter{font:inherit;font-size:13.5px;max-width:280px;width:100%;padding:6px 12px;border:1px solid var(--line);
  border-radius:8px;background:var(--card);color:var(--ink)}
.tbl-count{font-size:12.5px;color:var(--muted)}
@media print{
  .tabs .tab-list,.ck-reset,.defs-filter,.tbl-tools{display:none!important}
  .tabs .tab-panel{display:block!important}.tabs .tab-print-h{display:block!important}
  .tablewrap.tools{max-height:none;overflow:visible}.tablewrap.tools thead th{position:static}
  .walk-row{grid-template-columns:1fr}
}
/* 目次の表示モード */
.toc-menu .toc,.toc-none .toc{display:none}
.toc-menu .layout,.toc-none .layout{grid-template-columns:1fr}
.toc-sidebar .toc-toggle,.toc-both .toc-toggle{display:inline-flex}
/* トグルで畳んだ状態（初期は展開。localStorage に保存される） */
.toc-collapsed .toc{display:none}
.toc-collapsed .layout{grid-template-columns:1fr}
.toc-sidebar .nav-menu{display:none}
.toc-none .nav-menu,.toc-none .hamburger{display:none!important}
/* nav-menu が消えるレイアウトでは、ツール群を右端へ寄せる */
.toc-sidebar .topbar-tools,.toc-none .topbar-tools{margin-left:auto}
hr{border:none;border-top:1px solid var(--line);margin:28px 0}
.backtop{position:fixed;bottom:26px;right:26px;width:44px;height:44px;border-radius:50%;
  background:var(--accent);color:var(--on-accent);border:none;font-size:18px;cursor:pointer;opacity:0;
  pointer-events:none;transition:.25s;box-shadow:0 6px 18px rgba(0,0,0,.2);z-index:90}
.backtop.show{opacity:1;pointer-events:auto}
footer{max-width:var(--maxw);margin:40px auto 0;padding:24px;text-align:center;
  color:var(--muted);font-size:12px;border-top:1px solid var(--line)}
@media(max-width:860px){
  .layout{grid-template-columns:1fr}.toc{display:none}
  .nav-menu{position:fixed;top:var(--nav-h);left:0;right:0;background:var(--bg);
    border-bottom:1px solid var(--line);flex-direction:column;padding:8px;display:none}
  .nav-menu.open{display:flex}.hamburger{display:block}
  .topbar-tools{margin-left:auto}
  /* 狭い画面はサイド目次自体を出さないので、トグルも隠す */
  .toc-toggle{display:none!important}
}
@media print{
  /* 紙は常にライト配色の図を使う */
  .mm-dark{display:none!important}.mm-light{display:block!important}
  .topbar,.progress,.backtop,.copy-btn,.hamburger,.mode-switch,.type-switch,.anchor{display:none!important}
  :root[data-fs] .content{zoom:1}
  .toc{display:none}.layout{grid-template-columns:1fr;display:block}
  [id]{scroll-margin-top:0}body{background:#fff}
  .hero{padding:0 0 18px;background:none!important;color:#000!important;border-bottom:2px solid #000}
  .hero .eyebrow,.hero .tags span{background:#eee!important;color:#333!important}
  .content,.layout{padding:0}.content h2.hl{margin-top:24px}
  .callout,.mermaid-fig,.codeblock,table,figure,h2,h3,li{break-inside:avoid}
  a{color:#000;border:none}.codeblock pre{background:#f4f4f4;color:#111;border:1px solid #ccc}
  .copy-btn{display:none}
}
/* ---------- 追加の見せ方 ---------- */
.content .price-feats,.content .dd ul,.content .stepper ol,.content .chev-row,.content .dt,.content .dt ul{padding-left:0;margin-left:0}
.content .price-feats>li,.content .dd ul>li,.content .stepper ol>li,.content .chev-row>li{padding-left:0}
.content .price-feats>li::before,.content .dd ul>li::before,.content .stepper ol>li::before,.content .chev-row>li::before{display:none}
.content .dt li{margin:0;padding-left:8px}
.content .dt li::before,.content .dt li::after{left:auto;width:50%;height:22px;background:none;border-radius:0;top:0}
.content .dt li::before{right:50%}
.content .dt li::after{left:50%}
.ba.ba-js .ba-before .ba-body,.ba.ba-js .ba-before .ba-label{padding-right:52%}
.ba.ba-js .ba-after .ba-body,.ba.ba-js .ba-after .ba-label{padding-left:52%;text-align:right}
@media print{.ba.ba-js .ba-body,.ba.ba-js .ba-label{padding:0!important;text-align:left!important}}
.blk-hero{position:relative;overflow:hidden;margin:22px 0;padding:44px 40px;border-radius:calc(var(--radius) + 6px);
  background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 16%,var(--card)),var(--card));border:1px solid var(--line)}
.hero-glow{position:absolute;inset:-40% -20%;background:radial-gradient(closest-side,color-mix(in srgb,var(--accent) 22%,transparent),transparent);
  transform:translateX(-30%);pointer-events:none}
.blk-hero>*:not(.hero-glow){position:relative}
.hero-ic{color:var(--accent);margin-bottom:10px}
.hero-h{font-family:var(--font-head);font-weight:900;font-size:clamp(26px,4.2vw,40px);line-height:1.3;color:var(--ink)}
.hero-sub{margin-top:12px;font-size:17px;color:var(--muted)}
.hero-chips{margin-top:18px;display:flex;flex-wrap:wrap;gap:8px}
.hero-chip{padding:6px 14px;border-radius:999px;background:var(--accent);color:var(--on-accent);font-weight:700;font-size:13px}
.pq{position:relative;margin:26px 0;padding:18px 24px 18px 70px}
.pq-mark{position:absolute;left:8px;top:-18px;font-family:Georgia,serif;font-size:96px;line-height:1;color:var(--accent);opacity:.8}
.pq blockquote{border:0;margin:0;padding:0;font-family:var(--font-head);font-size:clamp(20px,2.6vw,26px);font-weight:700;line-height:1.6;color:var(--ink)}
.pq .w{display:inline}
.pq figcaption{margin-top:12px;color:var(--muted);font-weight:700}
.price-grid{display:grid;grid-template-columns:repeat(var(--cols,3),minmax(0,1fr));gap:18px;margin:22px 0;align-items:stretch}
@media(max-width:760px){.price-grid{grid-template-columns:1fr}}
.price{position:relative;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:24px 22px;box-shadow:var(--shadow)}
.price.is-rec{border:2px solid var(--ca,var(--accent));transform:translateY(-6px)}
.price-badge{position:absolute;top:-12px;left:50%;transform:translateX(-50%);padding:3px 14px;border-radius:999px;background:var(--ca,var(--accent));color:var(--on-accent);font-size:12px;font-weight:800;white-space:nowrap}
.price-ic{color:var(--ca,var(--accent))}
.price-name{font-family:var(--font-head);font-weight:800;font-size:18px;color:var(--ca,var(--accent-2))}
.price-amt{font-family:var(--font-head);font-weight:900;font-size:34px;margin:6px 0 12px}
.price-unit{font-size:14px;font-weight:600;color:var(--muted);margin-left:4px}
.price-feats{list-style:none;padding:0;margin:0}
.price-feats li{display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-top:1px dashed var(--line);font-size:14px}
.price-feats li .ico{color:var(--ca,var(--accent));margin-top:3px}
.stepper{position:relative;margin:26px 0}
.st-line{position:absolute;left:calc(50% / var(--n));right:calc(50% / var(--n));top:21px;height:4px;background:var(--line);border-radius:2px}
.st-line i{display:block;height:100%;background:var(--accent);border-radius:2px;transform-origin:0 50%}
.stepper ol{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:10px}
.st{text-align:center;position:relative}
.st-dot{display:inline-flex;align-items:center;justify-content:center;width:46px;height:46px;border-radius:50%;background:var(--ca,var(--accent));color:var(--on-accent);font-weight:800;box-shadow:0 0 0 5px var(--bg)}
.st-t{margin-top:10px;font-weight:800}
.st-d{font-size:13px;color:var(--muted)}
@media(max-width:680px){.stepper ol{grid-template-columns:1fr;text-align:left}.st{display:grid;grid-template-columns:46px 1fr;gap:4px 12px;text-align:left}.st-d{grid-column:2}.st-line{display:none}}
.kanban{display:grid;grid-template-columns:repeat(var(--cols,3),minmax(0,1fr));gap:14px;margin:22px 0}
@media(max-width:760px){.kanban{grid-template-columns:1fr}}
.kb-col{background:color-mix(in srgb,var(--ca,var(--accent)) 7%,var(--bg));border:1px solid var(--line);border-radius:var(--radius);padding:12px}
.kb-h{display:flex;align-items:center;gap:6px;font-weight:800;margin:2px 4px 10px;color:var(--ca,var(--accent-2))}
.kb-n{margin-left:auto;font-size:12px;color:var(--muted);background:var(--card);border-radius:999px;padding:1px 9px}
.kb-card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--ca,var(--accent));border-radius:10px;padding:9px 12px;margin-top:8px;font-size:14px;box-shadow:var(--shadow)}
.kb-tag{display:inline-block;margin-left:6px;font-style:normal;font-size:11px;padding:1px 8px;border-radius:999px;background:var(--accent-soft);color:var(--accent)}
.faq{margin:18px 0}
.faq-item{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);margin:10px 0;overflow:hidden}
.faq-item summary{list-style:none;cursor:pointer;display:flex;gap:12px;align-items:flex-start;padding:14px 18px;font-weight:700}
.faq-item summary::-webkit-details-marker{display:none}
.faq-q,.faq-al{flex:none;width:28px;height:28px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-weight:900;font-size:14px}
.faq-q{background:var(--accent);color:var(--on-accent)}
.faq-a{display:flex;gap:12px;padding:0 18px 14px}
.faq-al{background:var(--accent-soft);color:var(--accent)}
.faq-item[open] .faq-a{animation:faq-in .3s ease-out}
@keyframes faq-in{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.faq-item[open] .faq-a{animation:none}}
.ba{margin:22px 0}
.ba-stage{display:flex;gap:14px}
.ba-pane{flex:1;border:1px solid var(--line);border-radius:var(--radius);background:var(--card);padding:20px}
.ba-after{background:color-mix(in srgb,var(--accent) 8%,var(--card))}
.ba-label{font-weight:900;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
.ba-after .ba-label{color:var(--accent)}
.ba-handle,.ba-range{display:none}
.ba.ba-js .ba-stage{display:grid;position:relative;gap:0}
.ba.ba-js .ba-pane{grid-area:1/1}
.ba.ba-js .ba-after{clip-path:inset(0 0 0 var(--p,50%))}
.ba.ba-js .ba-handle{display:block;position:absolute;top:0;bottom:0;left:var(--p,50%);width:3px;margin-left:-1.5px;background:var(--accent);pointer-events:none}
.ba.ba-js .ba-handle span{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:36px;height:36px;border-radius:50%;background:var(--accent);color:var(--on-accent);display:flex;align-items:center;justify-content:center;font-weight:900}
.ba.ba-js .ba-range{display:block;width:100%;margin-top:10px;accent-color:var(--accent)}
@media print{.ba.ba-js .ba-stage{display:flex;gap:14px}.ba.ba-js .ba-after{clip-path:none}.ba.ba-js .ba-handle,.ba.ba-js .ba-range{display:none}}
.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin:22px 0}
.gal-item{margin:0}
.gal-btn{display:block;width:100%;padding:0;border:0;background:none;cursor:zoom-in;border-radius:12px;overflow:hidden}
.gal-btn img{display:block;width:100%;aspect-ratio:4/3;object-fit:cover;transition:transform .3s}
.gal-btn:hover img{transform:scale(1.04)}
.gal-item figcaption{font-size:13px;color:var(--muted);margin-top:6px}
.gal-ph{aspect-ratio:4/3;border-radius:12px;background:var(--accent-soft);display:flex;align-items:center;justify-content:center;color:var(--accent);font-weight:700;padding:10px;text-align:center}
.gal-box{position:fixed;inset:0;z-index:300;background:rgba(0,0,0,.82);display:flex;align-items:center;justify-content:center;padding:4vw;cursor:zoom-out}
.gal-box img{max-width:100%;max-height:100%;border-radius:10px;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.rm{display:grid;grid-template-columns:repeat(var(--cols,3),minmax(0,1fr));gap:14px;margin:22px 0}
@media(max-width:760px){.rm{grid-template-columns:1fr}}
.rm-lane{border-top:5px solid var(--ca,var(--accent));background:var(--card);border-radius:0 0 var(--radius) var(--radius);border-left:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:14px 16px}
.rm-lane.is-now{background:color-mix(in srgb,var(--ca,var(--accent)) 9%,var(--card))}
.rm-h{display:flex;align-items:center;gap:6px;font-family:var(--font-head);font-weight:800;color:var(--ca,var(--accent-2))}
.rm-now{margin-left:auto;font-size:11px;font-weight:800;color:var(--on-accent);background:var(--ca,var(--accent));padding:2px 10px;border-radius:999px}
.rm-lane ul{margin:10px 0 0;padding-left:1.1em}
.pers-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:22px 0}
.pers{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px 20px;text-align:center;box-shadow:var(--shadow)}
.pers-av{width:74px;height:74px;margin:0 auto 10px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:color-mix(in srgb,var(--ca,var(--accent)) 18%,var(--card));color:var(--ca,var(--accent));font-size:30px;font-weight:900;border:3px solid var(--ca,var(--accent))}
.pers-name{font-family:var(--font-head);font-weight:800;font-size:17px}
.pers-role{font-size:13px;color:var(--muted)}
.pers-tags{margin-top:8px;display:flex;flex-wrap:wrap;justify-content:center;gap:6px}
.pers-tags span{font-size:11px;padding:1px 8px;border-radius:999px;background:var(--accent-soft);color:var(--accent)}
.pers-b{text-align:left;font-size:14px;margin-top:10px}
.chev-row{list-style:none;padding:0;margin:22px 0;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:4px}
.chev{position:relative;background:var(--ca,var(--accent));color:var(--on-accent);padding:14px 26px 14px 30px;min-height:64px;display:flex;flex-direction:column;justify-content:center;
  clip-path:polygon(0 0,calc(100% - 18px) 0,100% 50%,calc(100% - 18px) 100%,0 100%,18px 50%)}
.chev:first-child{clip-path:polygon(0 0,calc(100% - 18px) 0,100% 50%,calc(100% - 18px) 100%,0 100%);padding-left:18px;border-radius:10px 0 0 10px}
.chev-t{font-weight:800}
.chev-d{font-size:12px;opacity:.9}
@media(max-width:680px){.chev-row{grid-template-columns:1fr}.chev,.chev:first-child{clip-path:none;border-radius:10px}}
.ctr-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px;margin:22px 0}
.ctr{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px;text-align:center;border-top:4px solid var(--ca,var(--accent))}
.ctr-v{font-family:var(--font-head);font-weight:900;font-size:40px;line-height:1;color:var(--ca,var(--accent));display:flex;justify-content:center;align-items:flex-end}
.od{display:inline-block;height:1em;overflow:hidden;line-height:1}
.od-s{display:flex;flex-direction:column;transform:translateY(calc(var(--d) * -1em))}
.od-s span{height:1em;display:block}
.od-c{display:inline-block;line-height:1}
.ctr-l{margin-top:10px;font-size:13px;color:var(--muted);font-weight:700}
.rt-list{margin:18px 0}
.rt{display:grid;grid-template-columns:minmax(120px,30%) 1fr auto;gap:14px;align-items:center;padding:9px 0;border-bottom:1px dashed var(--line)}
.rt-l{font-weight:700}
.rt-v{font-weight:800;color:var(--ca,var(--accent));font-variant-numeric:tabular-nums}
.rt-bar{height:10px;border-radius:5px;background:var(--line);overflow:hidden}
.rt-bar i{display:block;height:100%;border-radius:5px;background:var(--ca,var(--accent));transform-origin:0 50%}
.rt-stars{position:relative;display:inline-block;font-size:22px;letter-spacing:2px;line-height:1}
.rt-base{color:var(--line)}
.rt-fill{position:absolute;left:0;top:0;overflow:hidden;white-space:nowrap;color:var(--ca,var(--accent))}
.dd{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:22px 0}
@media(max-width:680px){.dd{grid-template-columns:1fr}}
.dd-col{border-radius:var(--radius);padding:16px 18px;border:1px solid var(--line)}
.dd-do{background:color-mix(in srgb,var(--ok,#16a34a) 8%,var(--card));border-top:4px solid var(--ok,#16a34a)}
.dd-dont{background:color-mix(in srgb,var(--ng,#dc2626) 7%,var(--card));border-top:4px solid var(--ng,#dc2626)}
.dd-h{display:flex;align-items:center;font-weight:900;margin-bottom:8px}
.dd-do .dd-h,.dd-do li .ico{color:var(--ok,#16a34a)}
.dd-dont .dd-h,.dd-dont li .ico{color:var(--ng,#dc2626)}
.dd ul{list-style:none;padding:0;margin:0}
.dd li{display:flex;gap:8px;padding:5px 0;align-items:flex-start}
.dd li .ico{margin-top:4px}
.voices{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin:26px 0}
.voice{margin:0;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow);border-left:5px solid var(--ca,var(--accent))}
.voice blockquote{border:0;margin:0;padding:0;font-size:15px}
.voice figcaption{display:flex;align-items:center;gap:10px;margin-top:12px;font-size:13px;font-weight:700;color:var(--muted)}
.voice-av{width:32px;height:32px;border-radius:50%;background:var(--ca,var(--accent));color:var(--on-accent);display:inline-flex;align-items:center;justify-content:center;font-weight:900}
.dt-wrap{overflow-x:auto;margin:22px 0;padding-bottom:6px}
.dt,.dt ul{list-style:none;margin:0;padding:0;display:flex;justify-content:center}
.dt ul{padding-top:22px;position:relative}
.dt li{position:relative;padding:22px 8px 0;text-align:center}
.dt li::before,.dt li::after{content:"";position:absolute;top:0;right:50%;width:50%;height:22px;border-top:2px solid var(--line)}
.dt li::after{right:auto;left:50%;border-left:2px solid var(--line)}
.dt li:only-child::before,.dt li:only-child::after{display:none}
.dt li:only-child{padding-top:0}
.dt li:first-child::before,.dt li:last-child::after{border:0}
.dt li:last-child::before{border-right:2px solid var(--line);border-radius:0 8px 0 0}
.dt li:first-child::after{border-radius:8px 0 0 0}
.dt ul::before{content:"";position:absolute;top:0;left:50%;height:22px;border-left:2px solid var(--line)}
.dt>li{padding-top:0}.dt>li::before,.dt>li::after{display:none}
.dt-n{display:inline-block;padding:9px 14px;border-radius:12px;border:2px solid var(--accent);background:var(--card);font-weight:700;font-size:14px;max-width:220px}
.dt-q{background:var(--accent);color:var(--on-accent)}
.dt-leaf{border-style:dashed}
.dt-b{display:block;font-size:11px;font-weight:900;color:var(--accent);margin-bottom:2px}
.dt-q .dt-b{color:var(--on-accent);opacity:.85}
.ig-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px;margin:22px 0}
.ig{text-align:center;padding:18px 12px;border-radius:var(--radius);background:var(--card);border:1px solid var(--line)}
.ig-ic{width:64px;height:64px;margin:0 auto 10px;border-radius:18px;display:flex;align-items:center;justify-content:center;color:var(--ca,var(--accent));
  background:color-mix(in srgb,var(--ca,var(--accent)) 14%,var(--card))}
.ig-t{font-weight:800}
.ig-d{font-size:13px;color:var(--muted)}
.lx-pyr{margin:24px 0;display:grid;gap:6px}
.lx-pyr-row{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:18px;align-items:center}
.lx-pyr-band{width:var(--w);margin:0 auto;min-height:54px;display:flex;align-items:center;justify-content:center;text-align:center;padding:8px 11%;
  background:color-mix(in srgb,var(--ca,var(--accent)) 42%,var(--card));color:var(--ink);font-weight:800;clip-path:polygon(9% 0,91% 0,100% 100%,0 100%);line-height:1.3}
.lx-pyr-row:first-child .lx-pyr-band{clip-path:polygon(50% 0,50% 0,100% 100%,0 100%);padding:26px 8px 4px;min-height:70px;font-size:14px}
.lx-pyr-band span{display:inline-flex;align-items:center;gap:4px}
.lx-pyr-d{font-size:14px;border-left:3px solid var(--ca,var(--accent));padding:4px 0 4px 12px;color:var(--ink)}
.lx-pyr-d>*:first-child{margin-top:0}.lx-pyr-d>*:last-child{margin-bottom:0}
@media(max-width:680px){.lx-pyr-row{grid-template-columns:1fr;gap:4px}.lx-pyr-d{margin-bottom:8px}}
.lx-cyc{position:relative;width:min(100%,560px);aspect-ratio:1;margin:26px auto}
.lx-cyc-ring{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
.lx-cyc-ring circle{fill:none;stroke:var(--line);stroke-width:1.4;stroke-dasharray:2.2 1.4}
.lx-cyc-ar{fill:var(--accent)}
.lx-cyc ol{list-style:none;margin:0;padding:0}
.lx-cyc-n{position:absolute;left:var(--x);top:var(--y);transform:translate(-50%,-50%);width:clamp(110px,27%,160px);text-align:center;background:var(--card);
  border:2px solid var(--ca,var(--accent));border-radius:14px;padding:10px 10px 9px;box-shadow:var(--shadow)}
.lx-cyc-no{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card));color:var(--ink);font-weight:900;font-size:13px;margin-top:-24px;box-shadow:0 0 0 4px var(--bg)}
.lx-cyc-t{display:block;font-weight:800;font-size:14px;margin-top:4px}
.lx-cyc-d{display:block;font-size:12px;color:var(--muted)}
.lx-cyc-c{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:30%;aspect-ratio:1;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
  background:var(--accent-soft);color:var(--accent);font-family:var(--font-head);font-weight:900;text-align:center;padding:10px;font-size:15px}
@media(max-width:600px){.lx-cyc{aspect-ratio:auto;width:100%}.lx-cyc-ring{display:none}.lx-cyc-c{position:static;transform:none;width:auto;aspect-ratio:auto;border-radius:12px;margin-bottom:10px}
  .lx-cyc-n{position:static;transform:none;width:auto;display:grid;grid-template-columns:28px 1fr;gap:2px 10px;text-align:left;margin:14px 0 0}.lx-cyc-no{margin:0;grid-row:span 2}
  .lx-cyc-n:last-child::after{content:"↻ 最初へ";grid-column:2;font-size:11px;color:var(--muted)}}
.lx-quad{position:relative;margin:24px 0}
.lx-quad.has-y{padding-left:34px}.lx-quad.has-x{padding-bottom:34px}
.lx-quad-g{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.lx-quad-c{position:relative;background:color-mix(in srgb,var(--ca,var(--accent)) 9%,var(--card));border:1px solid var(--line);border-top:4px solid var(--ca,var(--accent));border-radius:var(--radius);padding:16px 18px;min-height:120px}
.lx-quad-c.is-rec{border:2px solid var(--ca,var(--accent));border-top-width:4px;box-shadow:0 8px 26px color-mix(in srgb,var(--ca,var(--accent)) 30%,transparent)}
.lx-quad-h{font-family:var(--font-head);font-weight:800;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));display:flex;align-items:center;gap:4px}
.lx-quad-c p{margin:6px 0 0;font-size:14px}.lx-quad-c ul{margin:8px 0 0;padding-left:1.1em;font-size:14px}
.lx-quad-badge{position:absolute;top:-12px;right:12px;font-size:11px;font-weight:800;padding:2px 10px;border-radius:999px;background:color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card));color:var(--ink)}
.lx-quad-y{position:absolute;left:0;top:0;bottom:0;width:24px}
.lx-quad.has-x .lx-quad-y{bottom:34px}
.lx-quad-y i{position:absolute;left:11px;top:4px;bottom:0;width:2px;background:var(--muted);transform-origin:50% 100%}
.lx-quad-y i::before{content:"";position:absolute;top:-4px;left:-4px;border:5px solid transparent;border-bottom:7px solid var(--muted);border-top:0}
.lx-quad-y span{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%) rotate(-90deg);white-space:nowrap;font-size:12px;font-weight:800;color:var(--muted);background:var(--bg);padding:0 6px}
.lx-quad-x{position:absolute;left:34px;right:0;bottom:0;height:24px}
.lx-quad:not(.has-y) .lx-quad-x{left:0}
.lx-quad-x i{position:absolute;left:0;right:4px;top:11px;height:2px;background:var(--muted);transform-origin:0 50%}
.lx-quad-x i::after{content:"";position:absolute;right:-6px;top:-4px;border:5px solid transparent;border-left:7px solid var(--muted);border-right:0}
.lx-quad-x span{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-size:12px;font-weight:800;color:var(--muted);background:var(--bg);padding:0 6px;white-space:nowrap}
@media(max-width:560px){.lx-quad-g{grid-template-columns:1fr}}
.lx-cht{margin:22px 0;display:flex;flex-direction:column;gap:12px;max-width:760px}
.lx-cht-m{display:flex;gap:10px;align-items:flex-end}
.lx-cht-m.is-r{flex-direction:row-reverse}
.lx-cht-av{flex:none;width:36px;height:36px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card));color:var(--ink);font-weight:900}
.lx-cht-w{max-width:min(78%,560px);display:flex;flex-direction:column}
.lx-cht-m.is-r .lx-cht-w{align-items:flex-end}
.lx-cht-n{font-size:12px;font-weight:700;color:var(--muted);margin:0 6px 3px}
.lx-cht-b{position:relative;padding:10px 15px;border-radius:18px;background:var(--card);border:1px solid var(--line);box-shadow:var(--shadow);font-size:15px}
.lx-cht-m.is-l .lx-cht-b{border-bottom-left-radius:5px}
.lx-cht-m.is-r .lx-cht-b{border-bottom-right-radius:5px;background:color-mix(in srgb,var(--ca,var(--accent)) 16%,var(--card));border-color:color-mix(in srgb,var(--ca,var(--accent)) 35%,var(--line))}
.lx-cht-x>*:first-child{margin-top:0}.lx-cht-x>*:last-child{margin-bottom:0}
.lx-cht-dots{position:absolute;left:14px;top:50%;transform:translateY(-50%);display:flex;gap:4px;opacity:0;pointer-events:none}
.lx-cht-m.is-r .lx-cht-dots{left:auto;right:14px}
.lx-cht-dots i{width:7px;height:7px;border-radius:50%;background:var(--muted)}
.lx-cal-wrap{margin:22px 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:22px}
.lx-cal{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow)}
.lx-cal-h{font-family:var(--font-head);font-weight:900;font-size:18px;margin-bottom:10px;color:var(--accent-2)}
.lx-cal-g{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px}
.lx-cal-w{text-align:center;font-size:11px;font-weight:800;color:var(--muted);padding:2px 0}
.lx-cal-w:first-child{color:var(--ng,#dc2626)}.lx-cal-w:last-child{color:var(--accent)}
.lx-cal-d{min-height:58px;border-radius:8px;background:color-mix(in srgb,var(--ink) 3%,transparent);padding:3px 4px;overflow:hidden;display:flex;flex-direction:column;gap:2px}
.lx-cal-d.is-empty{background:none}
.lx-cal-no{font-size:12px;font-weight:700;color:var(--muted)}
.lx-cal-d.is-sun .lx-cal-no{color:var(--ng,#dc2626)}.lx-cal-d.is-sat .lx-cal-no{color:var(--accent)}
.lx-cal-d.has-ev{background:color-mix(in srgb,var(--accent) 10%,transparent)}
.lx-cal-ev{display:block;font-size:10.5px;line-height:1.35;font-weight:700;padding:1px 4px;border-radius:4px;border-left:3px solid var(--ca,var(--accent));background:color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card));color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lx-cal-l{list-style:none;padding:0;margin:12px 0 0;font-size:14px}
.lx-cal-l li{display:flex;gap:10px;align-items:baseline;padding:5px 0;border-top:1px dashed var(--line)}
.lx-cal-l time{flex:none;font-weight:800;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));font-variant-numeric:tabular-nums;min-width:6.5em}
.lx-cal-l em{font-style:normal;font-size:11px;margin-left:6px;padding:1px 8px;border-radius:999px;background:var(--accent-soft);color:var(--accent)}
@media(max-width:520px){.lx-cal-ev{font-size:0;height:6px;padding:0}.lx-cal-d{min-height:40px}}
.lx-vs{position:relative;display:grid;grid-template-columns:1fr auto 1fr;gap:14px;align-items:stretch;margin:26px 0}
.lx-vs-s{position:relative;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px 20px;box-shadow:var(--shadow);border-top:5px solid var(--ca,var(--accent))}
.lx-vs-s.is-rec{border:2px solid var(--ca,var(--accent));border-top-width:5px}
.lx-vs-r{text-align:right}
.lx-vs-r ul{padding-left:0;padding-right:4px}.content .lx-vs-r ul>li{padding-left:0;padding-right:18px}.content .lx-vs-r ul>li::before{left:auto;right:2px}
.lx-vs-ic{width:60px;height:60px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--ca,var(--accent)) 16%,var(--card));color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));font-size:26px;font-weight:900}
.lx-vs-n{font-family:var(--font-head);font-weight:900;font-size:21px;margin-top:8px;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink))}
.lx-vs-d{margin:4px 0 0;color:var(--muted);font-size:14px}
.lx-vs-s ul{margin:10px 0 0;padding-left:1.1em;font-size:14px}
.lx-vs-badge{position:absolute;top:-13px;left:18px;font-size:11px;font-weight:800;padding:2px 10px;border-radius:999px;background:color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card));color:var(--ink)}
.lx-vs-r .lx-vs-badge{left:auto;right:18px}
.lx-vs-mid{display:flex;align-items:center;justify-content:center}
.lx-vs-mid span{width:62px;height:62px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--ink);color:var(--bg);font-family:var(--font-head);font-weight:900;font-size:20px;font-style:italic;box-shadow:0 0 0 6px var(--bg),0 8px 22px rgba(0,0,0,.25)}
@media(max-width:680px){.lx-vs{grid-template-columns:1fr}.lx-vs-r{text-align:left}.lx-vs-r ul{padding:0 0 0 4px}.content .lx-vs-r ul>li{padding:0 0 0 18px}.content .lx-vs-r ul>li::before{left:2px;right:auto}.lx-vs-mid span{width:48px;height:48px;font-size:16px}}
.lx-bnr-list{margin:22px 0;display:flex;flex-direction:column;gap:14px}
.lx-bnr{position:relative;overflow:hidden;display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:14px 22px;border-radius:12px;
  background:linear-gradient(100deg,color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card)),color-mix(in srgb,var(--ca,var(--accent)) 10%,var(--card)));color:var(--ink);box-shadow:var(--shadow);border-left:6px solid var(--ca,var(--accent))}
.lx-bnr::after{content:"";position:absolute;top:0;bottom:0;left:-40%;width:30%;background:linear-gradient(100deg,transparent,rgba(255,255,255,.35),transparent);transform:skewX(-20deg);opacity:0;pointer-events:none}
.mo-live .lx-bnr::after{animation:lx-shine 4.5s ease-in-out infinite}
@keyframes lx-shine{0%{left:-40%;opacity:1}40%{left:120%;opacity:1}100%{left:120%;opacity:0}}
.lx-bnr-tag{font-size:11px;font-weight:900;letter-spacing:.06em;padding:3px 10px;border-radius:999px;background:var(--card);color:var(--ink);border:1.5px solid var(--ca,var(--accent))}
.lx-bnr-t{flex:1;min-width:12em;font-weight:800;font-size:16px;display:flex;align-items:center;gap:8px}
.lx-bnr-ic{display:inline-flex}
.lx-bnr-b{flex-basis:100%;font-size:14px;opacity:.95}
.lx-bnr-b>*:first-child{margin-top:0}.lx-bnr-b>*:last-child{margin-bottom:0}
.lx-swl{margin:22px 0;border:1px solid var(--line);border-radius:var(--radius);overflow-x:auto;background:var(--card)}
.lx-swl-lane{display:grid;grid-template-columns:112px repeat(var(--cols),minmax(104px,1fr));gap:10px;align-items:center;padding:12px 12px 12px 0;min-width:calc(134px + var(--cols) * 114px);
  border-top:1px solid var(--line);background:color-mix(in srgb,var(--ca,var(--accent)) 5%,transparent)}
.lx-swl-lane:first-child{border-top:0}
.lx-swl-h{grid-column:1;align-self:stretch;display:flex;align-items:center;gap:6px;padding:0 14px;font-weight:800;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));border-right:4px solid var(--ca,var(--accent))}
.lx-swl-s{position:relative;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--ca,var(--accent));border-radius:10px;padding:8px 10px 8px 34px;font-size:13.5px;box-shadow:var(--shadow);grid-row:1}
.lx-swl-no{position:absolute;left:8px;top:8px;width:20px;height:20px;border-radius:50%;background:color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card));color:var(--ink);font-size:11px;font-weight:900;display:flex;align-items:center;justify-content:center}
.lx-zz{margin:26px 0;display:flex;flex-direction:column;gap:30px}
.lx-zz-row{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:28px;align-items:center}
.lx-zz-row.is-rev{grid-template-columns:minmax(0,1.2fr) minmax(0,.8fr)}
.lx-zz-row.is-rev .lx-zz-v{order:2}
.lx-zz-v{aspect-ratio:4/3;border-radius:var(--radius);display:flex;align-items:center;justify-content:center;overflow:hidden;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));
  background:radial-gradient(circle at 30% 25%,color-mix(in srgb,var(--ca,var(--accent)) 28%,var(--card)),color-mix(in srgb,var(--ca,var(--accent)) 8%,var(--card)))}
.lx-zz-v img{width:100%;height:100%;object-fit:cover;display:block}
.lx-zz-no{font-family:var(--font-head);font-weight:900;font-size:64px;opacity:.85}
.lx-zz-h{font-family:var(--font-head);font-weight:900;font-size:22px;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink))}
.lx-zz-t p{margin:8px 0}
.lx-zz-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.lx-zz-tags span{font-size:11px;padding:1px 9px;border-radius:999px;background:var(--accent-soft);color:var(--accent);font-weight:700}
@media(max-width:680px){.lx-zz-row,.lx-zz-row.is-rev{grid-template-columns:1fr;gap:12px}.lx-zz-row.is-rev .lx-zz-v{order:0}.lx-zz-v{aspect-ratio:16/7}}
.lx-rng-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:18px;margin:22px 0}
.lx-rng{text-align:center}
.lx-rng-o{position:relative;width:128px;height:128px;margin:0 auto}
.lx-rng svg{width:100%;height:100%;transform:rotate(-90deg)}
.lx-rng circle{fill:none;stroke-width:11}
.lx-rng-bg{stroke:var(--line)}
.lx-rng-fg{stroke:var(--ca,var(--accent));stroke-linecap:round;stroke-dasharray:100 100}
.lx-rng-v{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:var(--font-head);font-weight:900;font-size:24px;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));font-variant-numeric:tabular-nums}
.lx-rng-l{margin-top:8px;font-weight:800;display:flex;align-items:center;justify-content:center;gap:4px}
.lx-rng-b{font-size:13px;color:var(--muted)}
.lx-tkr{margin:20px 0;overflow:hidden;border-radius:999px;border:1px solid var(--line);background:var(--card);
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent);mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent)}
.lx-tkr-track{display:flex;width:max-content;animation:lx-tkr calc(var(--n) * 4.5s) linear infinite}
.lx-tkr:hover .lx-tkr-track,.lx-tkr:focus-within .lx-tkr-track{animation-play-state:paused}
.lx-tkr ul{list-style:none;margin:0;padding:0;display:flex}
.lx-tkr li{display:flex;align-items:center;gap:8px;padding:11px 26px;white-space:nowrap;font-weight:700;font-size:14px;border-right:1px dashed var(--line)}
.lx-tkr li b{font-size:11px;padding:2px 9px;border-radius:999px;background:color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card));color:var(--ink)}
@keyframes lx-tkr{to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.lx-tkr{border-radius:var(--radius);-webkit-mask-image:none;mask-image:none}.lx-tkr-track{animation:none;width:auto}.lx-tkr ul{flex-wrap:wrap}.lx-tkr ul[aria-hidden]{display:none}.lx-tkr li{white-space:normal}}
.lx-bn{list-style:none;padding:0;margin:24px 0;counter-reset:none}
.lx-bn-i{display:grid;grid-template-columns:auto 1fr;gap:4px 22px;align-items:start;padding:14px 0}
.lx-bn-no{display:block;overflow:hidden;font-family:var(--font-head);font-weight:900;font-size:64px;line-height:1;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.lx-bn-no span{display:block}
.lx-bn-h{font-family:var(--font-head);font-weight:900;font-size:20px;display:flex;align-items:center;gap:6px;margin-top:6px}
.lx-bn-rule{display:block;height:3px;width:64px;border-radius:2px;background:var(--ca,var(--accent));margin:10px 0 8px;transform-origin:0 50%}
.lx-bn-t p{margin:0 0 6px}
@media(max-width:560px){.lx-bn-no{font-size:44px}}
.lx-stk-wall{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:22px 18px;margin:28px 0;padding:6px}
.lx-stk{position:relative;background:color-mix(in srgb,var(--ca,var(--accent)) 20%,var(--card));padding:22px 18px 18px;min-height:150px;transform:rotate(var(--r));
  box-shadow:0 10px 18px -8px rgba(0,0,0,.28),0 2px 3px rgba(0,0,0,.08);border-radius:3px 3px 18px 3px;color:var(--ink)}
.lx-stk-pin{position:absolute;top:-8px;left:50%;width:18px;height:18px;margin-left:-9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#fff8,transparent 45%),var(--ca,var(--accent));box-shadow:0 3px 4px rgba(0,0,0,.3)}
.lx-stk-h{font-weight:900;font-size:16px;display:flex;align-items:center;gap:5px}
.lx-stk p{margin:8px 0 0;font-size:14px}
.lx-stk-tags{margin-top:10px;display:flex;flex-wrap:wrap;gap:4px}
.lx-stk-tags span{font-size:11px;padding:1px 8px;border-radius:999px;background:rgba(0,0,0,.08)}
.lx-flp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px;margin:22px 0}
.lx-flp{perspective:900px;min-height:170px;outline:none;cursor:pointer}
.lx-flp-in{position:relative;height:100%;min-height:170px;transform-style:preserve-3d;transition:transform .6s cubic-bezier(.3,.8,.3,1)}
.lx-flp:hover .lx-flp-in,.lx-flp:focus .lx-flp-in,.lx-flp:focus-within .lx-flp-in{transform:rotateY(180deg)}
.lx-flp:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:var(--radius)}
.lx-flp-f,.lx-flp-b{position:absolute;inset:0;backface-visibility:hidden;-webkit-backface-visibility:hidden;border-radius:var(--radius);padding:18px;display:flex;flex-direction:column;justify-content:center;overflow:auto}
.lx-flp-f{align-items:center;text-align:center;background:var(--card);border:1px solid var(--line);border-bottom:5px solid var(--ca,var(--accent));box-shadow:var(--shadow)}
.lx-flp-b{transform:rotateY(180deg);background:color-mix(in srgb,var(--ca,var(--accent)) 20%,var(--card));color:var(--ink);border:2px solid var(--ca,var(--accent));font-size:14px}
.lx-flp-ic{color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));margin-bottom:8px}
.lx-flp-h{font-family:var(--font-head);font-weight:900;font-size:18px}
.lx-flp-bh{font-weight:900;margin-bottom:6px}
.lx-flp-b p{margin:0 0 6px}
.lx-flp-hint{position:absolute;right:10px;bottom:8px;font-size:14px;color:var(--muted)}
@media (prefers-reduced-motion:reduce){.lx-flp-in{transition:none}}
.lx-agd{list-style:none;position:relative;margin:24px 0;padding:0}
.lx-agd-line{position:absolute;left:calc(5.5em + 11px);top:10px;bottom:10px;width:3px;margin-left:-1.5px;background:var(--line);border-radius:2px;transform-origin:50% 0}
.lx-agd-i{position:relative;display:grid;grid-template-columns:5.5em 22px 1fr;gap:0 14px;align-items:start;padding:6px 0}
.lx-agd-tm{text-align:right;font-weight:900;font-variant-numeric:tabular-nums;color:color-mix(in srgb,var(--ca,var(--accent)) 68%,var(--ink));padding-top:9px;font-size:14px;white-space:nowrap}
.lx-agd-dot{width:16px;height:16px;margin:12px auto 0;border-radius:50%;background:var(--card);border:4px solid var(--ca,var(--accent));box-sizing:border-box;position:relative;z-index:1}
.lx-agd-c{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:9px 14px;box-shadow:var(--shadow)}
.lx-agd-h{font-weight:800;display:flex;align-items:center;flex-wrap:wrap;gap:6px}
.lx-agd-h em{font-style:normal;font-size:11px;font-weight:700;padding:1px 8px;border-radius:999px;background:var(--accent-soft);color:var(--accent)}
.lx-agd-c p{margin:4px 0 0;font-size:14px;color:var(--muted)}
.lx-agd-i.is-break .lx-agd-c{background:repeating-linear-gradient(135deg,transparent 0 8px,color-mix(in srgb,var(--ink) 4%,transparent) 8px 16px);box-shadow:none;border-style:dashed}
.lx-agd-i.is-break .lx-agd-dot{border-color:var(--muted)}
.lx-agd-i.is-break .lx-agd-tm{color:var(--muted)}
@media(max-width:520px){.lx-agd-i{grid-template-columns:4.2em 18px 1fr;gap:0 8px}.lx-agd-line{left:calc(4.2em + 17px)}}
.lx-mk{list-style:none;padding:0;margin:22px 0}
.content .lx-agd,.content .lx-bn,.content .lx-mk,.content .lx-cal-l,.content .lx-tkr ul,.content .lx-cyc ol{list-style:none;padding:0;margin:0}
.content .lx-agd,.content .lx-bn{margin:24px 0}.content .lx-mk{margin:22px 0}.content .lx-cal-l{margin:12px 0 0}
.content .lx-tkr li,.content .lx-cyc-n{margin:0}
@media(max-width:600px){.content .lx-cyc-n{margin:14px 0 0}}
.content .lx-mk>li,.content .lx-cal-l>li{padding-left:0}.content .lx-mk>li::before,.content .lx-cal-l>li::before,.content .lx-tkr li::before{display:none}.content .lx-tkr li{padding-left:26px}
.lx-mk li{display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px dashed var(--line)}
.lx-mk-ic{flex:none;width:30px;height:30px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--ca,var(--accent)) 30%,var(--card));color:var(--ink);margin-top:1px}
.lx-mk-t{font-size:17px;line-height:1.75}
.lx-mk-t strong{background-image:linear-gradient(transparent 58%,color-mix(in srgb,var(--ca,var(--accent)) 38%,transparent) 58%);background-repeat:no-repeat;background-size:100% 100%;padding:0 2px;
  -webkit-box-decoration-break:clone;box-decoration-break:clone}
@media print{.lx-tkr{border-radius:var(--radius);-webkit-mask-image:none;mask-image:none}.lx-tkr-track{animation:none!important;width:auto}.lx-tkr ul{flex-wrap:wrap}.lx-tkr ul[aria-hidden]{display:none}.lx-tkr li{white-space:normal}
  .lx-flp{perspective:none;min-height:0}.lx-flp-in{transform:none!important;min-height:0}.lx-flp-f,.lx-flp-b{position:static;transform:none;backface-visibility:visible}.lx-flp-f{border-radius:var(--radius) var(--radius) 0 0}.lx-flp-b{border-radius:0 0 var(--radius) var(--radius);-webkit-print-color-adjust:exact;print-color-adjust:exact}.lx-flp-hint{display:none}
  .lx-stk{transform:none;break-inside:avoid}.lx-bnr,.lx-pyr-band,.lx-cal-ev{-webkit-print-color-adjust:exact;print-color-adjust:exact}.lx-bnr::after{display:none}
  .lx-cyc-n,.lx-vs-s,.lx-zz-row,.lx-bn-i,.lx-agd-i,.lx-cal,.lx-swl-lane{break-inside:avoid}}
table.mx td,table.mx th{text-align:center}
table.mx td:first-child,table.mx th:first-child{text-align:left}
.mx-hl{background:color-mix(in srgb,var(--accent) 9%,transparent)}
th.mx-hl{color:var(--accent)}
.mx-y{color:var(--ok,#16a34a)}.mx-n{color:var(--muted);opacity:.7}.mx-p{color:var(--accent-2);font-weight:900}
.raci{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:7px;font-weight:900;font-size:13px;margin:1px;color:#fff}
.raci-r{background:var(--accent)}.raci-a{background:var(--ng,#dc2626)}.raci-c{background:var(--accent-2)}.raci-i{background:var(--muted)}
.raci-legend{font-size:12px;color:var(--muted);margin:-8px 0 18px;display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center}
.raci-legend .raci{width:20px;height:20px;font-size:11px}
.diff .dl{display:block}
.diff .dl-add{background:color-mix(in srgb,var(--ok,#16a34a) 18%,transparent)}
.diff .dl-del{background:color-mix(in srgb,var(--ng,#dc2626) 16%,transparent);text-decoration:line-through;text-decoration-color:color-mix(in srgb,var(--ng,#dc2626) 50%,transparent)}
.diff .dl-hunk{color:var(--accent);opacity:.8}

"""

# 表示モード切替のUIと、そのブート/操作スクリプト（INDEX_PAGE と共用）
MODE_SWITCH_HTML = (
    '<div class="mode-switch" role="group" aria-label="表示モード">'
    '<button type="button" data-mode="light" title="ライトモード" aria-label="ライトモード">☀</button>'
    '<button type="button" data-mode="dark" title="ダークモード" aria-label="ダークモード">☾</button>'
    '<button type="button" data-mode="system" title="システム設定に合わせる"'
    ' aria-label="システム設定に合わせる">◐</button>'
    '</div>'
) + (
    # 読み手が書体と文字の大きさを選ぶ（テーマの選択とは別。このブラウザに保存）
    '<div class="type-switch">'
    '<button type="button" class="type-btn" aria-haspopup="true" aria-expanded="false" aria-controls="md2doc-type"'
    ' title="文字の設定（書体・大きさ）" aria-label="文字の設定（書体・大きさ）"><span aria-hidden="true">Aa</span></button>'
    '<div class="type-panel" id="md2doc-type" hidden>'
    '<div class="type-row"><span class="type-lab" id="md2doc-type-ff">書体</span>'
    '<div class="type-seg" role="group" aria-labelledby="md2doc-type-ff">'
    '<button type="button" data-ff="theme">既定</button><button type="button" data-ff="gothic">ゴシック</button>'
    '<button type="button" data-ff="mincho">明朝</button><button type="button" data-ff="ud" title="読みやすさを重視した書体">UD</button>'
    '</div></div>'
    '<div class="type-row"><span class="type-lab" id="md2doc-type-fs">大きさ</span>'
    '<div class="type-seg" role="group" aria-labelledby="md2doc-type-fs">'
    '<button type="button" data-fs="s">小</button><button type="button" data-fs="m">標準</button>'
    '<button type="button" data-fs="l">大</button><button type="button" data-fs="xl">特大</button>'
    '</div></div>'
    '</div></div>'
)

# <head> 内で先に data-theme を確定させ、ダーク指定時の白フラッシュを防ぐ
MODE_BOOT_JS = """(function(){try{
var m=localStorage.getItem('__MODE_KEY__')||'__DEFAULT_MODE__';
if(m==='light'||m==='dark')document.documentElement.setAttribute('data-theme',m);
var ff=localStorage.getItem('md2doc-font'),fs=localStorage.getItem('md2doc-size');
if(ff==='gothic'||ff==='mincho'||ff==='ud')document.documentElement.setAttribute('data-ff',ff);
if(fs==='s'||fs==='l'||fs==='xl')document.documentElement.setAttribute('data-fs',fs);
}catch(e){}})();"""

# サイドメニューの開閉状態を、レイアウトが描かれる前に確定させる（初期表示は展開）
TOC_STORAGE_KEY = "md2doc-toc-open"

TOC_BOOT_JS = """(function(){try{
if(localStorage.getItem('__TOC_KEY__')==='0')document.documentElement.classList.add('toc-collapsed');
}catch(e){}})();"""

# サイドメニュー: 展開/非表示トグル・章アコーディオン・メニュー検索
TOC_SCRIPT_JS = """(function(){
  var KEY='__TOC_KEY__',root=document.documentElement;
  var toc=document.querySelector('.toc'),tgl=document.querySelector('.toc-toggle');
  function setOpen(open){
    root.classList.toggle('toc-collapsed',!open);
    if(tgl){
      tgl.setAttribute('aria-expanded',open?'true':'false');
      var lab=open?'サイドメニューを隠す':'サイドメニューを表示';
      tgl.title=lab;tgl.setAttribute('aria-label',lab);
    }
    try{localStorage.setItem(KEY,open?'1':'0');}catch(e){}
  }
  setOpen(!root.classList.contains('toc-collapsed'));
  if(tgl)tgl.addEventListener('click',function(){
    setOpen(root.classList.contains('toc-collapsed'));
  });
  if(!toc) return;
  // 章（h2）ごとのアコーディオン。初期状態は全て展開。
  toc.querySelectorAll('.toc-sec').forEach(function(sec){
    var btn=sec.querySelector('.toc-acc'),sub=sec.querySelector('.toc-sub');
    if(!btn) return;
    if(!sub||!sub.children.length){
      sec.classList.add('no-sub');btn.tabIndex=-1;btn.setAttribute('aria-hidden','true');return;
    }
    btn.addEventListener('click',function(){
      var c=sec.classList.toggle('collapsed');
      btn.setAttribute('aria-expanded',c?'false':'true');
    });
  });
  // メニュー検索。章名がヒットしたらその小見出しも全部残す。
  var q=toc.querySelector('.toc-search'),empty=toc.querySelector('.toc-empty');
  if(!q) return;
  function norm(s){return s.toLowerCase().replace(/\\s+/g,'');}
  function filter(){
    var v=norm(q.value),hit=0;
    toc.classList.toggle('toc-searching',!!v);
    toc.querySelectorAll('.toc-sec').forEach(function(sec){
      var top=sec.querySelector('a.lv2'),sm=0;
      var tm=!v||!!(top&&norm(top.textContent).indexOf(v)>=0);
      sec.querySelectorAll('a.lv3').forEach(function(a){
        var on=tm||norm(a.textContent).indexOf(v)>=0;
        a.classList.toggle('toc-hide',!on);
        if(on)sm++;
      });
      var show=tm||sm>0;
      sec.classList.toggle('toc-hide',!show);
      if(show)hit++;
    });
    if(empty)empty.style.display=(v&&!hit)?'block':'none';
  }
  q.addEventListener('input',filter);
  q.addEventListener('keydown',function(e){
    if(e.key==='Escape'||e.key==='Esc'){q.value='';filter();q.blur();}
  });
})();"""

MODE_SCRIPT_JS = """(function(){
  var KEY='__MODE_KEY__',DEF='__DEFAULT_MODE__',root=document.documentElement;
  var btns=[].slice.call(document.querySelectorAll('.mode-switch button'));
  function read(){try{var v=localStorage.getItem(KEY);
    return (v==='light'||v==='dark'||v==='system')?v:DEF;}catch(e){return DEF;}}
  function apply(m){
    // system は属性を外し、prefers-color-scheme に委ねる
    if(m==='light'||m==='dark')root.setAttribute('data-theme',m);else root.removeAttribute('data-theme');
    btns.forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-mode')===m?'true':'false');});
  }
  btns.forEach(function(b){b.addEventListener('click',function(){
    var m=b.getAttribute('data-mode');
    try{localStorage.setItem(KEY,m);}catch(e){}
    apply(m);
  });});
  apply(read());
})();
(function(){
  /* 文字の設定（書体・大きさ）: 「Aa」のパネル。選んだ値はこのブラウザに保存 */
  var root=document.documentElement,btn=document.querySelector('.type-btn'),panel=document.getElementById('md2doc-type');
  if(!btn||!panel) return;
  function get(k,d){try{return localStorage.getItem(k)||d;}catch(e){return d;}}
  function put(k,v){try{localStorage.setItem(k,v);}catch(e){}}
  function apply(){
    var ff=get('md2doc-font','theme'),fs=get('md2doc-size','m');
    if(ff==='theme')root.removeAttribute('data-ff');else root.setAttribute('data-ff',ff);
    if(fs==='m')root.removeAttribute('data-fs');else root.setAttribute('data-fs',fs);
    [].forEach.call(panel.querySelectorAll('[data-ff]'),function(b){b.setAttribute('aria-pressed',String(b.getAttribute('data-ff')===ff));});
    [].forEach.call(panel.querySelectorAll('[data-fs]'),function(b){b.setAttribute('aria-pressed',String(b.getAttribute('data-fs')===fs));});
  }
  function open(on,focus){
    panel.hidden=!on; btn.setAttribute('aria-expanded',String(on));
    if(on&&focus){var p=panel.querySelector('[aria-pressed="true"]');if(p)p.focus();}
    if(!on&&focus)btn.focus();
  }
  btn.addEventListener('click',function(){open(panel.hidden,true);});
  [].forEach.call(panel.querySelectorAll('button'),function(b){b.addEventListener('click',function(){
    if(b.hasAttribute('data-ff'))put('md2doc-font',b.getAttribute('data-ff'));
    if(b.hasAttribute('data-fs'))put('md2doc-size',b.getAttribute('data-fs'));
    apply();
  });});
  panel.addEventListener('keydown',function(e){if(e.key==='Escape'){e.preventDefault();open(false,true);}});
  document.addEventListener('pointerdown',function(e){if(!panel.hidden&&!e.target.closest('.type-switch'))open(false,false);});
  apply();
})();"""

LAYOUT_JS = r"""(function(){
  function each(l,f){[].forEach.call(l,f);}
  /* タブ: JS 無し・印刷では全部を見出し付きで並べる */
  each(document.querySelectorAll('.tabs[data-tabs]'),function(t){
    var tabs=[].slice.call(t.querySelectorAll('[role=tab]')), panels=[].slice.call(t.querySelectorAll('.tab-panel'));
    t.classList.add('tabs-js');
    function sel(i,focus){ tabs.forEach(function(b,k){ b.setAttribute('aria-selected',String(k===i)); b.tabIndex=k===i?0:-1; panels[k].hidden=k!==i; });
      if(focus) tabs[i].focus(); }
    tabs.forEach(function(b,i){
      b.addEventListener('click',function(){ sel(i); });
      b.addEventListener('keydown',function(e){
        var k={ArrowRight:1,ArrowLeft:-1,Home:'h',End:'e'}[e.key]; if(k===undefined) return;
        e.preventDefault(); sel(k==='h'?0:k==='e'?tabs.length-1:(i+k+tabs.length)%tabs.length,true); });
    });
    sel(0);
    window.addEventListener('beforeprint',function(){ panels.forEach(function(p){p.hidden=false;}); });
    window.addEventListener('afterprint',function(){ sel(tabs.findIndex(function(b){return b.getAttribute('aria-selected')==='true';})); });
  });
  /* チェックリスト: 進み具合と、チェックの保存（このブラウザだけ） */
  each(document.querySelectorAll('[data-checklist]'),function(c){
    var key='md2doc-ck:'+location.pathname+':'+c.getAttribute('data-checklist');
    var boxes=[].slice.call(c.querySelectorAll('input[type=checkbox]')), init=boxes.map(function(b){return b.checked;});
    var bar=c.querySelector('.ck-bar i'), cnt=c.querySelector('.ck-count');
    try{ var saved=JSON.parse(localStorage.getItem(key)||'null'); if(saved&&saved.length===boxes.length) boxes.forEach(function(b,i){b.checked=!!saved[i];}); }catch(e){}
    function upd(save){ var d=boxes.filter(function(b){return b.checked;}).length;
      bar.style.width=(boxes.length?100*d/boxes.length:0)+'%'; cnt.textContent=d+' / '+boxes.length;
      if(save){ try{ localStorage.setItem(key,JSON.stringify(boxes.map(function(b){return b.checked;}))); }catch(e){} } }
    boxes.forEach(function(b){ b.addEventListener('change',function(){ upd(true); }); });
    c.querySelector('.ck-reset').addEventListener('click',function(){ boxes.forEach(function(b,i){b.checked=init[i];}); try{localStorage.removeItem(key);}catch(e){} upd(false); });
    upd(false);
  });
  /* 用語の絞り込み */
  each(document.querySelectorAll('.defs-filter'),function(inp){
    var rows=[].slice.call(inp.parentNode.querySelectorAll('.def'));
    inp.addEventListener('input',function(){ var q=inp.value.trim().toLowerCase();
      rows.forEach(function(r){ r.hidden=!!q&&r.textContent.toLowerCase().indexOf(q)<0; }); });
  });
  /* 手で書かれた表（AI 構築）も、スクリプトが組む表と同じ規則で整える:
     数値の列（1 列目を除く）は右寄せと data-v、8 行以上なら並べ替え・絞り込み・棒。
     table か .tablewrap に data-table="plain" で止め、"tools" で行数に関係なく付ける */
  var NUM=/^[+\-−]?[¥$€]?\d[\d,]*(?:\.\d+)?\s*[%％a-zA-Zぁ-んァ-ヶ一-龠]{0,4}$/;
  function numOf(t){ var m=t.match(/[+\-−]?\d[\d,]*(?:\.\d+)?/); return m?parseFloat(m[0].replace(/,/g,'').replace('−','-')):NaN; }
  each(document.querySelectorAll('.content table'),function(tbl){
    var w=tbl.closest('.tablewrap');
    if(w&&w.hasAttribute('data-md2doc-table')) return;
    var mode=tbl.getAttribute('data-table')||(w&&w.getAttribute('data-table'))||'auto';
    if(mode==='plain'||!tbl.tBodies[0]) return;
    if(!w){ w=document.createElement('div'); w.className='tablewrap'; tbl.parentNode.insertBefore(w,tbl); w.appendChild(tbl); }
    var rows=[].slice.call(tbl.tBodies[0].rows), head=tbl.tHead?tbl.tHead.rows[0]:null;
    var tools=mode==='tools'||rows.length>=8, ncol=head?head.cells.length:(rows[0]?rows[0].cells.length:0);
    for(var c=1;c<ncol;c++){
      var cells=rows.map(function(r){return r.cells[c];}).filter(function(x){return x&&x.textContent.trim();});
      if(cells.length<2||!cells.every(function(x){return NUM.test(x.textContent.trim().replace(/\*\*/g,''));})) continue;
      var vals=cells.map(function(x){return numOf(x.textContent);}), max=Math.max.apply(null,vals), min=Math.min.apply(null,vals);
      if(head&&head.cells[c]) head.cells[c].classList.add('num');
      cells.forEach(function(x,k){
        x.classList.add('num'); x.setAttribute('data-v',vals[k]);
        if(tools&&max>0&&min>=0&&!x.querySelector('.nbar')){
          var v=document.createElement('span'); v.className='nv'; while(x.firstChild) v.appendChild(x.firstChild);
          var b=document.createElement('span'); b.className='nbar'; b.style.setProperty('--w',(100*vals[k]/max).toFixed(1));
          x.appendChild(b); x.appendChild(v);
        }
      });
    }
    if(tools){ w.classList.add('tools'); w.setAttribute('data-table-tools',''); }
    w.setAttribute('data-md2doc-table','');
  });
  /* 表: 並べ替え・絞り込み（見出しの固定は CSS） */
  each(document.querySelectorAll('[data-table-tools]'),function(w){
    var tb=w.querySelector('tbody'), rows=[].slice.call(tb.rows), ths=[].slice.call(w.querySelectorAll('thead th'));
    var bar=document.createElement('div'); bar.className='tbl-tools';
    bar.innerHTML='<input type="search" class="tbl-filter" placeholder="表を絞り込む" aria-label="表を絞り込む"><span class="tbl-count"></span>';
    w.parentNode.insertBefore(bar,w);
    var inp=bar.querySelector('input'), cnt=bar.querySelector('.tbl-count');
    function count(){ var v=rows.filter(function(r){return !r.hidden;}).length; cnt.textContent=v===rows.length?rows.length+' 行':v+' / '+rows.length+' 行'; }
    inp.addEventListener('input',function(){ var q=inp.value.trim().toLowerCase();
      rows.forEach(function(r){ r.hidden=!!q&&r.textContent.toLowerCase().indexOf(q)<0; }); count(); });
    ths.forEach(function(th,c){
      th.setAttribute('aria-sort','none'); th.tabIndex=0;
      function go(){
        var dir=th.getAttribute('aria-sort')==='ascending'?'descending':'ascending';
        ths.forEach(function(x){x.setAttribute('aria-sort','none');}); th.setAttribute('aria-sort',dir);
        var num=th.classList.contains('num'), s=dir==='ascending'?1:-1;
        rows.slice().sort(function(a,b){
          var x=a.cells[c], y=b.cells[c]; if(!x||!y) return 0;
          if(num){ var p=parseFloat(x.getAttribute('data-v')), q=parseFloat(y.getAttribute('data-v'));
            return ((isNaN(p)?-Infinity:p)-(isNaN(q)?-Infinity:q))*s; }
          return x.textContent.trim().localeCompare(y.textContent.trim(),'ja',{numeric:true})*s;
        }).forEach(function(r){ tb.appendChild(r); });
      }
      th.addEventListener('click',go);
      th.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); go(); } });
    });
    count();
  });
  /* 前と後（つまみで境目を動かす）。JS 無し・印刷では左右に並べる */
  each(document.querySelectorAll('.ba[data-ba]'),function(b){
    var r=b.querySelector('.ba-range'); if(!r) return; b.classList.add('ba-js');
    var set=function(v){ b.style.setProperty('--p',v+'%'); }; set(r.value);
    r.addEventListener('input',function(){ set(r.value); });
    b.__baSet=function(v){ r.value=v; set(v); };
  });
  /* ギャラリー: 押すと大きく表示（Esc・クリックで閉じる） */
  each(document.querySelectorAll('.gal-btn'),function(btn){
    btn.addEventListener('click',function(){
      var img=btn.querySelector('img'); if(!img) return;
      var box=document.createElement('div'); box.className='gal-box'; box.setAttribute('role','dialog'); box.setAttribute('aria-label',img.alt||'画像');
      var big=img.cloneNode(); box.appendChild(big); document.body.appendChild(box);
      var close=function(){ box.remove(); document.removeEventListener('keydown',key); btn.focus(); }, key=function(e){ if(e.key==='Escape') close(); };
      box.addEventListener('click',close); document.addEventListener('keydown',key);
      if(big.animate&&!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)) big.animate([{transform:'scale(.85)',opacity:0},{transform:'none',opacity:1}],{duration:220,easing:'ease-out'});
    });
  });
})();"""


# ──────────────────────────────────────────────────────────────────────────
# スクロール連動（.sy）と触れる図（figkit の tabs・slider・walk・hotspots と data-detail）
#   動きの設定（--motion）と無関係に働く。JS 無し・印刷では、全部の段・状態を並べた完成形のまま。
#   動きを減らす設定では、スクロール連動は完成図のまま並べ、切り替えは即座にする。
#   部品の class は sy-・fk- で始める（ヘッダーなどページの class と重ならないように）
# ──────────────────────────────────────────────────────────────────────────
INTERACT_CSS = r"""
/* ===== スクロール連動 ===== */
.sy{margin:28px 0;display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.25fr);gap:24px;align-items:start}
.sy-left{grid-template-columns:minmax(0,1.25fr) minmax(0,.8fr)}
.sy-right .sy-fig{order:2}
.sy-sticky{position:relative}
.sy-sticky>figure,.sy-sticky>p{margin:0}
.sy-sticky>p>img{display:block;border-radius:var(--radius);border:1px solid var(--line)}
.sy-sticky img{max-width:100%;height:auto}
.sy-prog{display:none}
.sy-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 18px;margin:0 0 14px}
.sy-card>:first-child{margin-top:0}.sy-card>:last-child{margin-bottom:0}
.sy-js .sy-fig{position:sticky;top:calc(var(--nav-h) + 20px);align-self:start}
.sy-js .sy-steps{padding:14vh 0 34vh}
.sy-js .sy-step{min-height:58vh;display:flex;align-items:center}
.sy-js .sy-card{width:100%;margin:0;opacity:.45;transition:opacity .35s,border-color .35s,box-shadow .35s}
.sy-js .sy-step.sy-on .sy-card{opacity:1;border-color:var(--accent);box-shadow:inset 4px 0 0 var(--accent),var(--shadow)}
.sy-js .sy-prog{display:flex;gap:5px;position:absolute;right:12px;top:-14px;z-index:2}
.sy-prog i{width:7px;height:7px;border-radius:50%;background:var(--line);transition:background .3s}
.sy-prog i.on{background:var(--accent)}
.sy-left .sy-prog{right:auto;left:12px}
.sy-js svg [data-step],.fk-js svg [data-step]{transition:opacity .45s ease}
svg .sy-off{opacity:.07}
svg .sy-dim{opacity:.2}
svg .sy-new{animation:sy-glow 1s ease-out}
@keyframes sy-glow{0%{filter:drop-shadow(0 0 0 transparent)}35%{filter:drop-shadow(0 0 7px var(--accent))}100%{filter:drop-shadow(0 0 0 transparent)}}
.sy-js .sy-swap{display:grid}
.sy-js .sy-swap>.sy-item{grid-area:1/1;opacity:0;visibility:hidden;transition:opacity .45s,visibility .45s}
.sy-js .sy-swap>.sy-item.sy-cur{opacity:1;visibility:visible}
@media (max-width:900px){
  .sy{grid-template-columns:1fr;gap:0}
  .sy-right .sy-fig{order:0}
  .sy-js .sy-fig{top:var(--nav-h);z-index:5;background:var(--bg);padding-top:6px}
  .sy-js .sy-sticky{background:var(--bg);padding:6px 0;box-shadow:0 10px 14px -10px rgba(0,0,0,.25)}
  .sy-js .sy-sticky>figure{padding:10px}
  .sy-js .sy-sticky svg,.sy-js .sy-sticky img{max-height:38vh;width:100%}
  .sy-js .sy-steps{padding:6vh 0 30vh}
  .sy-js .sy-step{min-height:60vh;align-items:flex-end}
}
/* ===== 触れる図 ===== */
.fk-panel-label{font-size:13px;font-weight:700;color:var(--muted);margin:10px 0 6px}
.fk-panel+.fk-panel,.fk-frame+.fk-frame{margin-top:14px}
.fk-js>.fk-panel,.fk-js>.fk-frame{display:none;margin:0}
.fk-js>.fk-panel.fk-on,.fk-js>.fk-frame.fk-on{display:block}
.fk-js .fk-panel-label{display:none}
.fk-tablist{display:flex;gap:2px;border-bottom:1px solid var(--line);margin:0 0 14px;flex-wrap:wrap}
.fk-tab{appearance:none;background:none;border:0;border-bottom:2px solid transparent;margin-bottom:-1px;padding:8px 14px;font:inherit;font-size:14px;color:var(--muted);cursor:pointer}
.fk-tab:hover{color:var(--ink)}
.fk-tab[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent);font-weight:700}
.fk-tab:focus-visible,.fk-btn:focus-visible,.fk-pin:focus-visible,.fk-ctrl input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.fk-ctrl{display:flex;align-items:center;gap:12px;margin:0 0 6px;flex-wrap:wrap}
.fk-ctrl input[type=range]{flex:1 1 180px;accent-color:var(--accent);cursor:pointer}
.fk-name{font-size:13px;color:var(--muted);font-weight:700}
.fk-val{font-weight:800;color:var(--accent);min-width:3.5em;font-variant-numeric:tabular-nums}
.fk-slider.fk-has-ticks .fk-val{display:none}
.fk-ticks{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin:0 0 12px;gap:6px}
.fk-ticks button{appearance:none;background:none;border:0;padding:0;font:inherit;color:inherit;cursor:pointer}
.fk-ticks button[aria-current="true"]{color:var(--accent);font-weight:700}
.fk-btn{appearance:none;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:5px 14px;font:inherit;font-size:13px;cursor:pointer;line-height:1.4}
.fk-btn:hover:not(:disabled){border-color:var(--accent);color:var(--accent)}
.fk-btn:disabled{opacity:.4;cursor:default}
.fk-frame-text{margin:8px 0 0;color:var(--muted);font-size:14px}
.fk-cap{min-height:1.6em;margin:10px 0 0;color:var(--ink);font-size:14px}
.fk-walk-steps,.fk-hs-list{text-align:left}
.fk-walk-steps{margin:12px 0 0;padding-left:1.4em}
.fk-walk-steps li{margin:4px 0}
.fk-js .fk-walk-steps{display:none}
.fk-walk-nav{display:flex;align-items:center;gap:10px;margin:10px 0 0;flex-wrap:wrap}
.fk-walk-count{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums;min-width:3.5em;text-align:center}
.fk-walk-cap{margin:10px 0 0;padding:10px 14px;border-left:4px solid var(--accent);background:var(--accent-soft);border-radius:8px;min-height:3.2em;color:var(--ink)}
.fk-hs-stage{position:relative}
.fk-hs-img{display:block;width:100%;height:auto;border-radius:10px;border:1px solid var(--line)}
.fk-pin{position:absolute;transform:translate(-50%,-50%);width:30px;height:30px;border-radius:50%;border:2px solid var(--card);background:var(--accent);color:var(--on-accent);
  font:inherit;font-weight:800;font-size:13px;line-height:1;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.3);padding:0}
.fk-pin[aria-expanded="true"]{background:var(--ink);color:var(--card)}
.fk-js .fk-pin:not([aria-expanded="true"])::after{content:"";position:absolute;inset:-6px;border-radius:50%;border:2px solid var(--accent);opacity:0;animation:fk-ring 2.4s ease-out infinite}
@keyframes fk-ring{0%{transform:scale(.6);opacity:.8}80%,100%{transform:scale(1.35);opacity:0}}
.fk-hs-list{margin:12px 0 0;padding-left:1.6em;font-size:14px}
.fk-hs-list li{margin:3px 0;cursor:pointer}
.fk-hs-list li.fk-cur{color:var(--accent)}
.content svg [data-detail]{cursor:help}
.content svg [data-detail]:focus{outline:none}
.content svg [data-detail]:focus-visible{filter:drop-shadow(0 0 3px var(--accent))}
.fk-tip{position:fixed;z-index:400;max-width:300px;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:8px 12px;
  font-size:13px;line-height:1.6;box-shadow:0 10px 26px rgba(0,0,0,.2);pointer-events:none}
.fk-tip b{display:block;color:var(--accent)}
@media (prefers-reduced-motion:reduce){svg .sy-new{animation:none}.fk-js .fk-pin::after{animation:none;display:none}.sy-js .sy-card,.sy-js svg [data-step]{transition:none}}
@media print{
  .sy *,.sy-item{transition:none!important;animation:none!important}
  .sy{display:block}.sy-fig{position:static!important}.sy-steps{padding:0!important}.sy-step{min-height:0!important;display:block!important}
  .sy-card{opacity:1!important;margin:0 0 10px!important;box-shadow:none!important;border-color:var(--line)!important}.sy-prog{display:none!important}
  svg .sy-off,svg .sy-dim{opacity:1!important}
  .sy-swap>.sy-item{opacity:1!important;visibility:visible!important;grid-area:auto!important}.sy-swap{display:block!important}
  .fk-js>.fk-panel,.fk-js>.fk-frame{display:block!important;margin-top:12px!important}.fk-js .fk-panel-label{display:block!important}
  .fk-tablist,.fk-ctrl,.fk-ticks,.fk-walk-nav,.fk-walk-cap,.fk-cap,.fk-tip{display:none!important}
  .fk-js .fk-walk-steps{display:block!important}.fk-pin::after{display:none!important}
}
"""

INTERACT_JS = r"""(function(){
  var REDUCE=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches, SEQ=0;
  function each(l,f){[].forEach.call(l,f);}
  function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
  /* ---- 説明のカード（data-detail・画像の注目点）。1 つを使い回す ---- */
  var tip=null;
  function showTip(el,title,body){
    if(!tip){ tip=document.createElement('div'); tip.className='fk-tip'; tip.setAttribute('role','tooltip'); tip.id='fk-tip'; document.body.appendChild(tip); }
    tip.textContent=''; if(title){ var b=document.createElement('b'); b.textContent=title; tip.appendChild(b); }
    tip.appendChild(document.createTextNode(body||'')); tip.hidden=false;
    var r=el.getBoundingClientRect(), w=tip.offsetWidth, h=tip.offsetHeight, vw=window.innerWidth;
    var top=r.top-h-10; if(top<70) top=r.bottom+10;
    tip.style.left=clamp(r.left+r.width/2-w/2,8,vw-w-8)+'px'; tip.style.top=top+'px';
  }
  function hideTip(){ if(tip) tip.hidden=true; }
  document.addEventListener('keydown',function(e){ if(e.key==='Escape') hideTip(); });
  window.addEventListener('scroll',hideTip,{passive:true});
  each(document.querySelectorAll('.content svg [data-detail]'),function(x){
    var d=x.getAttribute('data-detail');
    x.setAttribute('tabindex','0'); x.setAttribute('role','button'); x.setAttribute('aria-label',d);
    x.addEventListener('pointerenter',function(){ showTip(x,'',d); });
    x.addEventListener('pointerleave',hideTip);
    x.addEventListener('focus',function(){ showTip(x,'',d); });
    x.addEventListener('blur',hideTip);
    x.addEventListener('click',function(){ showTip(x,'',d); });
  });
  /* ---- 図の段（data-step）を見せる・隠す: val まで見せる（only: val だけ濃く）。val=null は全部 ---- */
  /* 段の一覧: ノード・文字を含む段だけを数える（線だけの段は、その次の段と一緒に見せる）。
     data-stage-base の段（軸・枠・中心）はいつも見せ、数えない */
  function stagesOf(root){
    var all={}, txt={}, nod={}, bEl=root.matches&&root.matches('[data-stage-base]')?root:root.querySelector('[data-stage-base]'), base=bEl?+bEl.getAttribute('data-stage-base'):null;
    each(root.querySelectorAll('svg [data-step]'),function(x){ var v=+x.getAttribute('data-step')||0; if(v===base) return; all[v]=1;
      if(x.hasAttribute('data-node')||x.querySelector('[data-node]')) nod[v]=1;
      if(!x.hasAttribute('data-link')&&(x.tagName.toLowerCase()==='text'||x.querySelector('text'))) txt[v]=1; });
    /* ノードのある図はノードの段、無ければ文字を含む段（矢印の名札は数えない）、それも無ければ全部の段 */
    var T=Object.keys(nod).length?nod:Object.keys(txt).length?txt:all;
    var V=Object.keys(T).map(Number).sort(function(a,b){return a-b;}); V.base=base; return V;
  }
  function setStage(root,val,only,base){
    each(root.querySelectorAll('svg [data-step]'),function(x){
      var s=+x.getAttribute('data-step')||0, keep=base!==null&&base!==undefined&&s===base;
      var off=val!==null&&!only&&!keep&&s>val, dim=val!==null&&!!only&&!keep&&s!==val, was=x.classList.contains('sy-off');
      x.classList.toggle('sy-off',off); x.classList.toggle('sy-dim',dim);
      x.classList.remove('sy-new');
      if(!REDUCE&&was&&!off){ void x.getBoundingClientRect(); x.classList.add('sy-new'); }
    });
  }
  function pick(V,show,k,n){
    if(!V.length||show==='all') return null;
    var i=show?clamp((+show)-1,0,V.length-1):(n>1?Math.round(k*(V.length-1)/(n-1)):V.length-1);
    return V[i];
  }
  /* ---- スクロール連動 ---- */
  each(document.querySelectorAll('[data-sy]'),function(sec){
    var sticky=sec.querySelector('.sy-sticky'), prog=sticky.querySelector('.sy-prog');
    var steps=[].slice.call(sec.querySelectorAll('.sy-steps > .sy-step'));
    each(sticky.querySelectorAll('figure'),function(f){ f.setAttribute('data-motion','none'); f.removeAttribute('data-trigger'); });  /* 登場の動きは段の見せ方に任せる */
    if(REDUCE||!steps.length) return;   /* 動きを減らす: 完成図のまま本文と並べる */
    var items=[].filter.call(sticky.children,function(c){ return c!==prog; }), swap=items.length>1;
    if(swap){ sticky.classList.add('sy-swap'); items.forEach(function(c){ c.classList.add('sy-item'); }); }
    var V=swap?[]:stagesOf(sticky), cur=-1;
    sec.classList.add('sy-js');
    prog.innerHTML=steps.map(function(){ return '<i></i>'; }).join('');
    function go(k){
      if(k===cur) return; cur=k;
      steps.forEach(function(s,i){ s.classList.toggle('sy-on',i===k); });
      each(prog.children,function(d,i){ d.classList.toggle('on',i<=k); });
      var st=steps[k], sh=st.getAttribute('data-sy-show');
      if(swap){ var it=clamp(sh&&sh!=='all'?(+sh)-1:k,0,items.length-1); items.forEach(function(c,i){ c.classList.toggle('sy-cur',i===it); }); }
      else setStage(sticky,pick(V,sh,k,steps.length),st.hasAttribute('data-sy-only'),V.base);
      sec.setAttribute('data-sy-cur',String(k));
    }
    function upd(){
      var line=window.innerHeight*(window.innerWidth<=900?.74:.56), k=0;
      steps.forEach(function(s,i){ var c=s.querySelector('.sy-card')||s; if(c.getBoundingClientRect().top<line) k=i; });
      go(k);
    }
    var q=false;
    window.addEventListener('scroll',function(){ if(!q){ q=true; requestAnimationFrame(function(){ q=false; upd(); }); } },{passive:true});
    window.addEventListener('resize',upd); upd();
    window.addEventListener('beforeprint',function(){ setStage(sticky,null); });
    window.addEventListener('afterprint',function(){ var k=cur; cur=-1; go(k); });
  });
  /* ---- タブで図を切り替える ---- */
  each(document.querySelectorAll('[data-fk-tabs]'),function(t){
    var panels=[].slice.call(t.querySelectorAll(':scope > .fk-panel')); if(panels.length<2) return;
    var n=++SEQ, list=document.createElement('div'); list.className='fk-tablist'; list.setAttribute('role','tablist');
    var tabs=panels.map(function(p,i){
      var b=document.createElement('button'); b.type='button'; b.className='fk-tab'; b.setAttribute('role','tab');
      b.id='fk-tab-'+n+'-'+i; p.id='fk-pan-'+n+'-'+i; b.setAttribute('aria-controls',p.id);
      p.setAttribute('role','tabpanel'); p.setAttribute('aria-labelledby',b.id); p.tabIndex=0;
      b.textContent=p.getAttribute('data-label'); list.appendChild(b);
      b.addEventListener('click',function(){ sel(i); });
      b.addEventListener('keydown',function(e){ var k={ArrowRight:1,ArrowLeft:-1,Home:'h',End:'e'}[e.key]; if(k===undefined) return;
        e.preventDefault(); sel(k==='h'?0:k==='e'?tabs.length-1:(i+k+tabs.length)%tabs.length,true); });
      return b;
    });
    t.insertBefore(list,t.firstChild); t.classList.add('fk-js');
    var cur=-1;
    function sel(i,focus){
      tabs.forEach(function(b,k){ b.setAttribute('aria-selected',String(k===i)); b.tabIndex=k===i?0:-1; panels[k].classList.toggle('fk-on',k===i); });
      if(focus) tabs[i].focus();
      if(cur>=0&&cur!==i&&!REDUCE&&panels[i].animate) panels[i].animate([{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'none'}],{duration:260,easing:'ease-out'});
      cur=i; t.setAttribute('data-fk-cur',String(i));
    }
    sel(0);
  });
  /* ---- つまみで値の組を切り替え、図の形を保ったまま数値を移す（形が違えば入れ替える） ---- */
  var NUM=/-?\d+(?:\.\d+)?/g;
  function sk(s){ return String(s).replace(NUM,'#'); }
  function nums(s){ return (String(s).match(NUM)||[]).map(Number); }
  function put(skel,arr){ var i=0; return skel.replace(/#/g,function(){ var v=arr[i++]; return String(Math.round(v*100)/100); }); }
  var TNUM=/-?\d[\d,]*(?:\.\d+)?/;
  function fmtLike(v,ref){ var dec=(ref.split('.')[1]||'').length, s=v.toFixed(dec); if(ref.indexOf(',')>=0||Math.abs(v)>=1000&&/\d{1,3}(,\d{3})+/.test(ref)){ var p=s.split('.'); p[0]=p[0].replace(/\B(?=(\d{3})+(?!\d))/g,','); s=p.join('.'); } return s; }
  function nodesOf(svg){ return [svg].concat([].slice.call(svg.querySelectorAll('*'))); }
  function morph(live,target,dur,gen,box){
    var A=nodesOf(live), B=nodesOf(target), same=A.length===B.length&&A.every(function(a,i){ return a.tagName===B[i].tagName; });
    function swapAll(){
      live.setAttribute('viewBox',target.getAttribute('viewBox')||'');
      live.innerHTML=target.innerHTML.replace(/(\bid="|url\(#|href="#)([^")]+)/g,'$1$2-lv');
    }
    if(!same){
      if(REDUCE||!dur){ swapAll(); return; }
      var a=live.animate([{opacity:1},{opacity:0}],{duration:dur*.35,fill:'forwards'});
      a.onfinish=function(){ if(box.gen!==gen) return; swapAll(); live.animate([{opacity:0},{opacity:1}],{duration:dur*.5}); a.cancel(); };
      return;
    }
    var jobs=[], texts=[];
    A.forEach(function(a,i){
      var b=B[i];
      each(b.attributes,function(at){
        if(at.name==='id'||/url\(#/.test(at.value)) return;
        var v0=a.getAttribute(at.name), v1=at.value;
        if(v0===v1) return;
        if(v0!==null&&sk(v0)===sk(v1)&&nums(v1).length) jobs.push({el:a,name:at.name,skel:sk(v1),from:nums(v0),to:nums(v1),end:v1});
        else jobs.push({el:a,name:at.name,end:v1,late:true});
      });
      if(!a.children.length&&!b.children.length&&a.textContent!==b.textContent){
        var m0=a.textContent.match(TNUM), m1=b.textContent.match(TNUM);
        var rest0=m0?a.textContent.replace(m0[0],'#'):null, rest1=m1?b.textContent.replace(m1[0],'#'):null;
        if(m0&&m1&&rest0===rest1) texts.push({el:a,from:parseFloat(m0[0].replace(/,/g,'')),to:parseFloat(m1[0].replace(/,/g,'')),ref:m1[0],rest:rest1,end:b.textContent});
        else texts.push({el:a,end:b.textContent,late:true});
      }
    });
    function finish(){ jobs.forEach(function(j){ j.el.setAttribute(j.name,j.end); }); texts.forEach(function(t){ t.el.textContent=t.end; }); }
    if(REDUCE||!dur){ finish(); return; }
    var t0=performance.now();
    (function step(now){
      if(box.gen!==gen) return;
      var k=Math.min(1,(now-t0)/dur), e=k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;
      jobs.forEach(function(j){ if(j.late){ if(k>=.5) j.el.setAttribute(j.name,j.end); return; }
        j.el.setAttribute(j.name,put(j.skel,j.to.map(function(v,i){ return j.from[i]+(v-j.from[i])*e; }))); });
      texts.forEach(function(t){ if(t.late){ if(k>=.5) t.el.textContent=t.end; return; }
        t.el.textContent=t.rest.replace('#',fmtLike(t.from+(t.to-t.from)*e,t.ref)); });
      if(k<1) requestAnimationFrame(step); else finish();
    })(t0);
  }
  each(document.querySelectorAll('[data-fk-slider]'),function(s){
    var frames=[].slice.call(s.querySelectorAll(':scope > .fk-frame')); if(frames.length<2) return;
    var live=frames[0].querySelector('svg'); if(!live) return;
    var src=frames.map(function(f,i){ return i?f.querySelector('svg'):live.cloneNode(true); });
    var labels=frames.map(function(f){ return f.getAttribute('data-label'); }), notes=frames.map(function(f){ var p=f.querySelector('.fk-frame-text'); return p?p.textContent:''; });
    each(s.querySelectorAll('.fk-frame-text'),function(p){ p.remove(); });
    s.classList.add('fk-js'); frames[0].classList.add('fk-on');
    var name=s.getAttribute('data-name')||'表示する値', box={gen:0}, cur=0, timer=0;
    var ctrl=document.createElement('div'); ctrl.className='fk-ctrl';
    ctrl.innerHTML='<span class="fk-name"></span><input type="range" min="0" step="1"><span class="fk-val" aria-hidden="true"></span>';
    ctrl.querySelector('.fk-name').textContent=name;
    var rg=ctrl.querySelector('input'); rg.max=String(frames.length-1); rg.value='0'; rg.setAttribute('aria-label',name);
    var play=null;
    if(s.hasAttribute('data-play')){ play=document.createElement('button'); play.type='button'; play.className='fk-btn'; play.textContent='▶ 再生'; play.setAttribute('aria-pressed','false'); ctrl.insertBefore(play,ctrl.firstChild); }
    var ticks=document.createElement('div'); ticks.className='fk-ticks';
    if(frames.length<=8) s.classList.add('fk-has-ticks'); else ticks.hidden=true;   /* 多いときは目盛りを出さず、今の値だけ */
    labels.forEach(function(l,i){ var b=document.createElement('button'); b.type='button'; b.textContent=l; b.tabIndex=-1; b.addEventListener('click',function(){ stop(); go(i); }); ticks.appendChild(b); });
    var cap=document.createElement('p'); cap.className='fk-cap'; cap.setAttribute('aria-live','polite');
    s.insertBefore(ctrl,s.firstChild); s.insertBefore(ticks,ctrl.nextSibling); s.appendChild(cap);
    function go(i){
      i=clamp(i,0,frames.length-1); rg.value=String(i);
      rg.setAttribute('aria-valuetext',labels[i]); ctrl.querySelector('.fk-val').textContent=labels[i];
      each(ticks.children,function(b,k){ b.setAttribute('aria-current',String(k===i)); });
      cap.textContent=notes[i]||'';
      if(i!==cur){ box.gen++; morph(live,src[i],650,box.gen,box); }
      cur=i; s.setAttribute('data-fk-cur',String(i));
    }
    function stop(){ if(timer){ clearInterval(timer); timer=0; if(play){ play.textContent='▶ 再生'; play.setAttribute('aria-pressed','false'); } } }
    rg.addEventListener('input',function(){ stop(); go(+rg.value); });
    if(play) play.addEventListener('click',function(){ if(timer){ stop(); return; }
      play.textContent='❚❚ 止める'; play.setAttribute('aria-pressed','true');
      if(cur>=frames.length-1) go(0);
      timer=setInterval(function(){ if(cur>=frames.length-1){ stop(); return; } go(cur+1); },1700); });
    go(0);
    window.addEventListener('beforeprint',function(){ stop(); box.gen++; morph(live,src[0],0,box.gen,box); });
    window.addEventListener('afterprint',function(){ var i=cur; cur=0; go(i); });
  });
  /* ---- 図を 1 段ずつ見る（前へ・次へ） ---- */
  each(document.querySelectorAll('[data-fk-walk]'),function(w){
    var fig=w.querySelector('.fk-walk-fig'), lis=[].slice.call(w.querySelectorAll('.fk-walk-steps > li')); if(!fig||!lis.length) return;
    var V=stagesOf(fig), n=lis.length, cur=-1;
    w.classList.add('fk-js');
    var nav=document.createElement('div'); nav.className='fk-walk-nav';
    nav.innerHTML='<button type="button" class="fk-btn" data-d="-1">◀ 前へ</button><span class="fk-walk-count"></span><button type="button" class="fk-btn" data-d="1">次へ ▶</button>';
    var cap=document.createElement('div'); cap.className='fk-walk-cap'; cap.setAttribute('aria-live','polite');
    w.appendChild(nav); w.appendChild(cap);
    var prev=nav.children[0], next=nav.children[2], cnt=nav.children[1];
    function go(k){ k=clamp(k,0,n-1); if(k===cur) return; cur=k; var li=lis[k];
      setStage(fig,pick(V,li.getAttribute('data-show'),k,n),li.hasAttribute('data-only'),V.base);
      cap.textContent=li.textContent; cnt.textContent=(k+1)+' / '+n; prev.disabled=k===0; next.disabled=k===n-1;
      w.setAttribute('data-fk-cur',String(k)); }
    prev.addEventListener('click',function(){ go(cur-1); }); next.addEventListener('click',function(){ go(cur+1); });
    w.addEventListener('keydown',function(e){ if(e.key==='ArrowRight'){ go(cur+1); e.preventDefault(); } else if(e.key==='ArrowLeft'){ go(cur-1); e.preventDefault(); } });
    go(0);
    window.addEventListener('beforeprint',function(){ setStage(fig,null); });
    window.addEventListener('afterprint',function(){ var k=cur; cur=-1; go(k); });
  });
  /* ---- 画像の注目点 ---- */
  each(document.querySelectorAll('[data-fk-hs]'),function(h){
    var pins=[].slice.call(h.querySelectorAll('.fk-pin')), lis=[].slice.call(h.querySelectorAll('.fk-hs-list > li'));
    h.classList.add('fk-js');
    function open(i,focus){
      pins.forEach(function(p,k){ p.setAttribute('aria-expanded',String(k===i)); });
      lis.forEach(function(l,k){ l.classList.toggle('fk-cur',k===i); });
      var li=lis[i], b=li&&li.querySelector('b'), title=b?b.textContent:'', body=li?li.textContent.slice(title.length).replace(/^\s*—\s*/,''):'';
      showTip(pins[i],title,body); if(focus) pins[i].focus();
      h.setAttribute('data-fk-cur',String(i));
    }
    function close(){ pins.forEach(function(p){ p.setAttribute('aria-expanded','false'); }); hideTip(); }
    pins.forEach(function(p,i){
      p.setAttribute('aria-expanded','false'); p.setAttribute('aria-describedby','fk-tip');
      p.addEventListener('click',function(){ open(i); });
      p.addEventListener('pointerenter',function(){ open(i); });
      p.addEventListener('focus',function(){ open(i); });
      p.addEventListener('pointerleave',close); p.addEventListener('blur',close);
    });
    lis.forEach(function(l,i){ l.addEventListener('click',function(){ open(i,true); }); });
  });
})();"""

STATIC_CSS += INTERACT_CSS
LAYOUT_JS = LAYOUT_JS + "\n" + INTERACT_JS

PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
__THEMECSS__
__STATIC_CSS__
</style>
<script>__MODE_BOOT_JS__</script>
<script>__TOC_BOOT_JS__</script>
</head>
<body id="top" class="__BODYCLASS__">
<div class="progress-track" title="クリックした位置へ移動"><div class="progress"></div></div>
<nav class="topbar"><div class="topbar-inner">
  <button class="toc-toggle" type="button" aria-expanded="true" aria-controls="doc-toc"
    title="サイドメニューを隠す" aria-label="サイドメニューを隠す"><svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><rect x="1.2" y="2.4" width="13.6" height="11.2" rx="2.2" fill="none" stroke="currentColor" stroke-width="1.4"/><line x1="6.2" y1="2.4" x2="6.2" y2="13.6" stroke="currentColor" stroke-width="1.4"/></svg></button>
  <a href="#top" class="brand">__BRAND__</a>
  <div class="nav-menu">__NAV__</div>
  <div class="topbar-tools">
    <button class="hamburger" type="button" aria-label="メニュー">☰</button>
    __MODE_SWITCH__
  </div>
</div></nav>
<header class="hero"><div class="hero-inner">
  __EYEBROW____H1____DATE____TAGS__
</div></header>
<div class="layout">
  <aside class="toc" id="doc-toc">
    <div class="toc-head">
      <div class="toc-ttl">目次</div>
      <input class="toc-search" type="search" placeholder="メニューを検索" aria-label="メニューを検索" autocomplete="off">
    </div>
    <div class="toc-body">__TOC__<div class="toc-empty">該当する見出しがありません</div></div>
  </aside>
  <main class="content">__CONTENT__</main>
</div>
<button class="backtop" type="button" aria-label="トップへ">↑</button>
<footer>__FOOTER__</footer>
<script>
__MODE_SCRIPT_JS__
__TOC_SCRIPT_JS__
__LAYOUT_JS__
(function(){
  var navH=parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-h'))||60;
  var links=[].slice.call(document.querySelectorAll('.nav-menu a, .toc a'));
  // 見出し要素を文書順で取得（スクロールスパイの対象）
  var targets=[].slice.call(document.querySelectorAll('.content .hl'));
  var curId=null;
  // アクティブな目次項目が、スクロール可能な目次(.toc=縦 / .nav-menu=横)の
  // 表示範囲外にある場合、その項目が見えるように目次側をスクロールする
  function keepInView(a){
    // 畳まれた章の中／非表示のサイドメニューにある項目は追わない
    if(!a.offsetParent) return;
    var box=a.closest('.toc')||a.closest('.nav-menu');
    if(!box) return;
    var lr=a.getBoundingClientRect(), br=box.getBoundingClientRect(), m=16;
    if(box.scrollHeight>box.clientHeight+1){
      if(lr.top<br.top+m) box.scrollBy({top:lr.top-br.top-m,behavior:'smooth'});
      else if(lr.bottom>br.bottom-m) box.scrollBy({top:lr.bottom-br.bottom+m,behavior:'smooth'});
    }
    if(box.scrollWidth>box.clientWidth+1){
      if(lr.left<br.left+m) box.scrollBy({left:lr.left-br.left-m,behavior:'smooth'});
      else if(lr.right>br.right-m) box.scrollBy({left:lr.right-br.right+m,behavior:'smooth'});
    }
  }
  function setActive(id){
    if(id===curId) return;
    curId=id;
    links.forEach(function(a){
      var on=a.getAttribute('href').slice(1)===id;
      a.classList.toggle('active', on);
      if(on) keepInView(a);
    });
  }
  function spy(){
    if(!targets.length) return;
    var th=navH+40, cur=targets[0].id;
    for(var i=0;i<targets.length;i++){
      if(targets[i].getBoundingClientRect().top - th <= 0) cur=targets[i].id; else break;
    }
    // ページ最下部まで来たら、最後の見出しを必ず選択（短い末尾セクション対策）
    var h=document.documentElement, sc=h.scrollTop||document.body.scrollTop;
    if(window.innerHeight + sc >= h.scrollHeight - 2) cur=targets[targets.length-1].id;
    setActive(cur);
  }
  document.querySelectorAll('.copy-btn').forEach(function(b){b.addEventListener('click',function(){
    var code=b.parentElement.querySelector('code');navigator.clipboard.writeText(code.innerText).then(function(){
      var t=b.textContent;b.textContent='コピー済';b.classList.add('done');
      setTimeout(function(){b.textContent=t;b.classList.remove('done');},1400);});});});
  var ham=document.querySelector('.hamburger'),menu=document.querySelector('.nav-menu');
  if(ham&&menu)ham.addEventListener('click',function(){menu.classList.toggle('open');});
  if(menu)menu.querySelectorAll('a').forEach(function(a){a.addEventListener('click',function(){menu.classList.remove('open');});});
  var bar=document.querySelector('.progress'),bt=document.querySelector('.backtop');
  // 進捗バー（トラック）をクリックすると、その横位置に相当する位置へスクロール
  var ptrack=document.querySelector('.progress-track');
  if(ptrack)ptrack.addEventListener('click',function(e){
    var r=ptrack.getBoundingClientRect(), ratio=(e.clientX-r.left)/r.width;
    ratio=Math.max(0,Math.min(1,ratio));
    var h=document.documentElement;
    window.scrollTo({top:(h.scrollHeight-h.clientHeight)*ratio,behavior:'smooth'});
  });
  function onScroll(){
    var h=document.documentElement,sc=h.scrollTop||document.body.scrollTop,mx=h.scrollHeight-h.clientHeight;
    if(bar)bar.style.width=(mx>0?sc/mx*100:0)+'%';
    if(bt)bt.classList.toggle('show',sc>500);
    spy();
  }
  window.addEventListener('scroll',onScroll,{passive:true});
  window.addEventListener('resize',spy);
  if(bt)bt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
  onScroll();
})();
</script>
__MOTION__
</body>
</html>
"""


def build_toc_html(headings):
    """サイド目次を「章(h2) = アコーディオン、配下に h3」の形で組み立てる。
    初期状態は全章とも展開（collapsed クラスを付けない）。"""
    if not headings:
        return '<span style="color:var(--muted);font-size:12px">―</span>'
    # h2 を境に章へ束ねる（先頭が h3 の場合は見出しなしの章として扱う）
    groups = []
    for h in headings:
        if h["level"] == 2 or not groups:
            groups.append([h if h["level"] == 2 else None,
                           [] if h["level"] == 2 else [h]])
        else:
            groups[-1][1].append(h)

    out = []
    for top, subs in groups:
        out.append('<div class="toc-sec">')
        if top is not None:
            txt = html.escape(top["text"])
            out.append('<div class="toc-row">'
                       '<a class="lv2" href="#%s">%s</a>'
                       '<button class="toc-acc" type="button" aria-expanded="true"'
                       ' title="この章の小見出しを開閉" aria-label="%s の小見出しを開閉">'
                       '<span class="toc-caret">▾</span></button>'
                       '</div>' % (top["slug"], txt, txt))
        out.append('<div class="toc-sub">')
        out.extend('<a class="lv3" href="#%s">%s</a>' % (s["slug"], html.escape(s["text"]))
                   for s in subs)
        out.append("</div></div>")
    return "".join(out)


def build_html(meta, content_html, headings, theme_key, title, brand, footer,
               toc_mode="sidebar", default_mode="system", motion="off",
               motion_tempo="normal"):
    nav = "".join('<a href="#%s">%s</a>' % (h["slug"], html.escape(h["text"]))
                  for h in headings if h["level"] == 2)
    toc = build_toc_html(headings)
    eyebrow = '<span class="eyebrow">%s</span>' % html.escape(meta["eyebrow"]) if meta.get("eyebrow") else ""
    h1 = "<h1>%s</h1>" % html.escape(title)
    date = '<div class="date">%s</div>' % html.escape(meta["date"]) if meta.get("date") else ""
    tags = ""
    if meta.get("tags"):
        tg = [t.strip() for t in re.split(r"[,，、]", meta["tags"]) if t.strip()]
        tags = '<div class="tags">%s</div>' % "".join("<span>%s</span>" % html.escape(t) for t in tg)
    repl = {
        "__TITLE__": html.escape(title), "__THEMECSS__": theme_css(theme_key),
        "__STATIC_CSS__": STATIC_CSS + theme_extra_css(theme_key), "__BRAND__": html.escape(brand),
        "__MODE_SWITCH__": MODE_SWITCH_HTML,
        "__MODE_BOOT_JS__": MODE_BOOT_JS, "__MODE_SCRIPT_JS__": MODE_SCRIPT_JS,
        "__TOC_BOOT_JS__": TOC_BOOT_JS, "__TOC_SCRIPT_JS__": TOC_SCRIPT_JS, "__LAYOUT_JS__": LAYOUT_JS,
        "__NAV__": nav, "__TOC__": toc, "__EYEBROW__": eyebrow, "__H1__": h1,
        "__DATE__": date, "__TAGS__": tags, "__CONTENT__": content_html,
        "__FOOTER__": html.escape(footer), "__BODYCLASS__": "toc-" + toc_mode,
        "__MOTION__": motion_html(motion, motion_tempo),
    }
    page = PAGE
    for k, v in repl.items():
        page = page.replace(k, v)
    # スクリプト中のプレースホルダは、JS を差し込んだ後にまとめて解決する
    page = (page.replace("__MODE_KEY__", MODE_STORAGE_KEY)
                .replace("__DEFAULT_MODE__", default_mode)
                .replace("__TOC_KEY__", TOC_STORAGE_KEY))
    return page


# ──────────────────────────────────────────────────────────────────────────
# モーション（説明図の要所を動かす）
#   決定論的な実行部。Claude は図に data-* の注釈を付けるだけで、動かし方はここで決まる。
#   - 図が画面に入ったら 1 回再生。図の右上の「↻ 再生」でもう一度。
#   - prefers-reduced-motion / 印刷 / JS 無し では何もしない（静止した完成図のまま）。
#   - 図の単位（コンテナ）: <figure data-motion="auto|steps|none">。level=rich は全図が対象。
#   - 要素の注釈: data-step="N" / data-effect="draw|rise|fade|slide" / data-flow / data-pulse
# ──────────────────────────────────────────────────────────────────────────
MOTION_LEVELS = ["off", "key", "rich"]

MOTION_CSS = """
.mo-fig{position:relative}
.mo-replay{position:absolute;top:8px;right:8px;z-index:2;font:inherit;font-size:12px;line-height:1;
  padding:6px 10px;border-radius:999px;border:1px solid var(--line);background:var(--card);
  color:var(--muted);cursor:pointer;opacity:.0;transition:opacity .2s,color .2s,border-color .2s}
.mo-fig.mo-played .mo-replay,.mo-replay.mo-click{opacity:.75}
.mo-fig:hover .mo-replay,.mo-replay:focus-visible{opacity:1;color:var(--accent);border-color:var(--accent)}
.mo-replay:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* 操作（経路・状態の切り替え）と、関連の強調 */
.mo-bar{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin:0 0 12px}
.mo-chip{font:inherit;font-size:12.5px;line-height:1.2;padding:5px 12px;border-radius:999px;border:1px solid var(--line);
  background:var(--card);color:var(--muted);cursor:pointer}
.mo-chip:hover{color:var(--accent);border-color:var(--accent)}
.mo-chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.mo-chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
[data-path],[data-node],[data-link]{transition:opacity .25s}
.mo-dim{opacity:.15}
[data-node]:focus{outline:none}
[data-node]:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
/* 変更前／変更後: JS 無し・印刷では並べて表示し、JS があれば 1 つずつ切り替える */
.mo-states{display:flex;flex-wrap:wrap;gap:18px;justify-content:center;align-items:flex-start}
.mo-state{flex:1 1 280px;min-width:0}
.mo-state-label{font-size:13px;font-weight:700;color:var(--muted);margin-bottom:6px}
.mo-states.mo-js{display:block}
.mo-states.mo-js .mo-state{display:none}
.mo-states.mo-js .mo-state.mo-on{display:block}
.mo-states.mo-js .mo-state-label{display:none}
@media print{.mo-replay,.mo-bar{display:none!important}.mo-dim{opacity:1!important}}
/* アイコンの繰り返しの動き（部品が現れた後に .ico-live を付ける） */
@keyframes ico-spin{to{transform:rotate(360deg)}}
@keyframes ico-swing{0%,100%{transform:rotate(-12deg)}50%{transform:rotate(12deg)}}
@keyframes ico-beat{0%,45%,100%{transform:scale(1)}15%{transform:scale(1.16)}30%{transform:scale(1.04)}}
@keyframes ico-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-9%)}}
@keyframes ico-blink{0%,100%{opacity:1}50%{opacity:.4}}
@keyframes ico-glow{0%,100%{filter:none}50%{filter:drop-shadow(0 0 4px currentColor)}}
@keyframes ico-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.1)}}
@keyframes ico-shake{0%,78%,100%{transform:rotate(0)}82%{transform:rotate(-12deg)}86%{transform:rotate(12deg)}90%{transform:rotate(-7deg)}94%{transform:rotate(4deg)}}
@keyframes ico-bounce{0%,100%{transform:translateY(0)}40%{transform:translateY(-14%)}60%{transform:translateY(0)}}
@keyframes ico-flip{0%,40%,100%{transform:scaleX(1)}70%{transform:scaleX(-1)}}
@keyframes ico-twinkle{0%,100%{transform:scale(1) rotate(0)}50%{transform:scale(1.18) rotate(10deg)}}
.ico.ico-live{transform-origin:50% 50%;transform-box:fill-box}
.ico.ico-live[data-ico-anim="spin"]{animation:ico-spin 8s linear infinite}
.ico.ico-live[data-ico-anim="swing"]{transform-origin:50% 8%;animation:ico-swing 2.4s ease-in-out infinite}
.ico.ico-live[data-ico-anim="beat"]{animation:ico-beat 1.6s ease-in-out infinite}
.ico.ico-live[data-ico-anim="float"]{animation:ico-float 3.2s ease-in-out infinite}
.ico.ico-live[data-ico-anim="blink"]{animation:ico-blink 2.2s ease-in-out infinite}
.ico.ico-live[data-ico-anim="glow"]{animation:ico-glow 2.6s ease-in-out infinite}
.ico.ico-live[data-ico-anim="pulse"]{animation:ico-pulse 2s ease-in-out infinite}
.ico.ico-live[data-ico-anim="shake"]{animation:ico-shake 3.2s ease-in-out infinite}
.ico.ico-live[data-ico-anim="bounce"]{animation:ico-bounce 2s ease-in-out infinite}
.ico.ico-live[data-ico-anim="flip"]{animation:ico-flip 3.6s ease-in-out infinite}
.ico.ico-live[data-ico-anim="twinkle"]{animation:ico-twinkle 2.2s ease-in-out infinite}
.mo-live .rm-now{animation:rm-pulse 1.8s ease-in-out infinite}
@keyframes rm-pulse{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 60%,transparent)}50%{box-shadow:0 0 0 7px transparent}}
.mo-live .hero-glow{animation:hero-drift 9s ease-in-out infinite alternate}
.mo-live .lx-agd-i:last-child .lx-agd-dot{animation:rm-pulse 1.8s ease-in-out infinite}
@keyframes hero-drift{from{transform:translateX(-30%)}to{transform:translateX(10%)}}
@media (prefers-reduced-motion:reduce){.ico.ico-live,.mo-live .rm-now,.mo-live .hero-glow,.mo-live .lx-bnr::after,.mo-live .lx-agd-dot{animation:none!important}}
@media print{.ico.ico-live{animation:none!important}}
"""

MOTION_JS = r"""(function(){
  var LEVEL='__MOTION_LEVEL__', TEMPO_DEF='__MOTION_TEMPO__', STYLE_DEF='__MOTION_STYLE__', BLOCKS='__MOTION_BLOCKS__';
  var mq=window.matchMedia?matchMedia('(prefers-reduced-motion: reduce)'):null;
  var REDUCE=!!(mq&&mq.matches), CAN=!!Element.prototype.animate&&('IntersectionObserver' in window);
  var NS='http://www.w3.org/2000/svg';
  var GEOM={rect:1,circle:1,ellipse:1,polygon:1,polyline:1,line:1,path:1,text:1,image:1,use:1,foreignObject:1};
  var SKIP={defs:1,marker:1,clipPath:1,mask:1,pattern:1,symbol:1,linearGradient:1,radialGradient:1,filter:1,style:1,title:1,desc:1,metadata:1};
  var ATOMIC=['data-effect','data-stagger','data-travel','data-count','data-focus','data-spin','data-pulse','data-flow','data-attn','data-burst',
              'data-float','data-sway','data-blink','data-heartbeat','data-wave','data-march','data-glow','data-orbit','data-ripple','data-stream',
              'data-breathe','data-shine','data-jiggle','data-hop','data-tick','data-redraw','data-hue'];
  var TEMPOS={slow:1.45,normal:1,fast:.7};
  var BASE={draw:760,rise:520,travel:1400,count:1100,type:30,stagger:130,gapSteps:450,gapAuto:380,autoTotal:2600,hold:1500,
            flow:900,pulse:1800,spin:24000,loopRest:2200,zoomMove:900,zoomHold:1500,toggle:3400,token:900,
            attn:760,burst:900,float:3200,sway:3000,blink:1600,heartbeat:1300,wave:1600,march:1200,glow:2200,orbit:6000,ripple:2000,stream:2400,intro:720,
            breathe:3600,shine:2600,jiggle:3000,hop:1400,tick:8000,redraw:2800,hue:6000};
  /* 動きの性格: 注釈の無い要素の現れ方・図全体の入り方・段の間隔を決める（data-motion-style か --motion-style） */
  var STYLES={gentle:{gap:1},
    dynamic:{shape:'pop',text:'slide-up',big:'zoom',intro:'punch',gap:.75},
    playful:{shape:'elastic',text:'bounce',big:'drop',intro:'drop',gap:.9},
    cinematic:{shape:'blur',text:'blur',big:'blur',intro:'zoom-out',gap:1.35},
    tech:{shape:'wipe',text:'scramble',big:'wipe',intro:'glitch',gap:.85},
    retro:{shape:'pixel',text:'type',big:'blinds',intro:'crt',gap:.9},
    elegant:{shape:'float-in',text:'letters',big:'blur',intro:'unfold',gap:1.25},
    news:{shape:'swoosh',text:'slide-right',big:'wipe',intro:'wipe',gap:.7}};
  var INTROS={punch:[{scale:'.86',opacity:0},{scale:'1.03',opacity:1,offset:.6},{scale:'1',opacity:1}],
    'zoom-out':[{scale:'1.18',filter:'blur(6px)',opacity:0},{scale:'1',filter:'blur(0px)',opacity:1}],
    drop:[{translate:'0 -40px',opacity:0},{translate:'0 6px',opacity:1,offset:.6},{translate:'0 0',opacity:1}],
    tilt:[{rotate:'-4deg',scale:'.94',opacity:0},{rotate:'0deg',scale:'1',opacity:1}],
    glitch:[{translate:'-14px 0',opacity:0},{translate:'10px 0',opacity:1,offset:.2},{translate:'-6px 2px',opacity:.4,offset:.4},{translate:'4px 0',opacity:1,offset:.6},{translate:'0 0',opacity:1}],
    iris:[{clipPath:'circle(0% at 50% 50%)'},{clipPath:'circle(75% at 50% 50%)'}],
    fade:[{opacity:0},{opacity:1}], rise:[{translate:'0 24px',opacity:0},{translate:'0 0',opacity:1}],
    crt:[{scale:'1 .02',filter:'brightness(3)',opacity:0},{scale:'1 .02',filter:'brightness(3)',opacity:1,offset:.3},{scale:'1 1',filter:'brightness(1)',opacity:1}],
    wipe:[{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0% 0 0)'}],
    unfold:[{scale:'1 0',opacity:0},{scale:'1 1.02',opacity:1,offset:.7},{scale:'1 1',opacity:1}]};
  function styleOf(c){ return STYLES[c&&c.getAttribute('data-motion-style')]||STYLES[STYLE_DEF]||STYLES.gentle; }
  function cssv(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#3b82f6'; }
  function hrand(i){ var x=Math.sin(i*12.9898+78.233)*43758.5453; return x-Math.floor(x); }
  var EASE='cubic-bezier(.2,.7,.2,1)';
  function tag(el){return el.localName||el.tagName;}
  function num(v,d){v=parseFloat(v);return isFinite(v)?v:d;}
  function each(list,fn){[].forEach.call(list,fn);}
  function tempoOf(c){return TEMPOS[c.getAttribute('data-tempo')]||TEMPOS[TEMPO_DEF]||1;}
  function strokeOnly(el){
    var t=tag(el); if(t!=='path'&&t!=='line'&&t!=='polyline') return false;
    var cs=getComputedStyle(el);
    var noFill=t==='line'||cs.fill==='none'||parseFloat(cs.fillOpacity)===0;   // line には塗りが無い
    return noFill&&cs.stroke!=='none'&&parseFloat(cs.strokeWidth)>0;
  }
  function isAtomic(el){ for(var i=0;i<ATOMIC.length;i++) if(el.hasAttribute(ATOMIC[i])) return true; return false; }
  function shown(el){ return el.getClientRects().length>0; }
  function outerSvgs(root){ return [].filter.call(root.querySelectorAll('svg'),function(s){ return !s.parentElement.closest('svg'); }); }
  function el(name,attrs){ var e=document.createElementNS(NS,name); for(var k in attrs) e.setAttribute(k,attrs[k]); return e; }
  /* 画面上の矩形を svg の座標へ */
  function toUser(svg,r){
    var m=svg.getScreenCTM(); if(!m) return null; m=m.inverse();
    var p=svg.createSVGPoint(); p.x=r.left; p.y=r.top; var a=p.matrixTransform(m);
    p.x=r.right; p.y=r.bottom; var b=p.matrixTransform(m);
    return {x:a.x,y:a.y,w:b.x-a.x,h:b.y-a.y};
  }
  function vbox(svg){ var v=svg.viewBox&&svg.viewBox.baseVal; return v&&v.width?{x:v.x,y:v.y,w:v.width,h:v.height}:null; }

  /* ================= 注記の吹き出し（data-note） ================= */
  function notes(svg){
    if(svg.__moNotes||!shown(svg)) return svg.__moNotes||[];
    var vb=vbox(svg), out=[];
    each(svg.querySelectorAll('[data-note]'),function(t){
      var bb=toUser(svg,t.getBoundingClientRect()); if(!bb||!vb) return;
      var txt=t.getAttribute('data-note'), lines=[], cur='';
      for(var i=0;i<txt.length;i++){ cur+=txt[i]; if(cur.length>=18&&i<txt.length-1){ lines.push(cur); cur=''; } }
      if(cur) lines.push(cur);
      var g=el('g',{'class':'mo-note','pointer-events':'none'});
      var box=el('rect',{rx:6,fill:'var(--card)',stroke:'var(--accent)','stroke-width':1.2});
      var line=el('line',{stroke:'var(--accent)','stroke-width':1.2,'stroke-dasharray':'3 3'});
      g.appendChild(line); g.appendChild(box);
      var tx=[]; lines.forEach(function(s){ var x=el('text',{'font-size':12,fill:'var(--ink)','text-anchor':'middle'}); x.textContent=s; g.appendChild(x); tx.push(x); });
      svg.appendChild(g);
      var w=0; tx.forEach(function(x){ var l=0; try{l=x.getComputedTextLength();}catch(e){} w=Math.max(w,l||x.textContent.length*12); });
      w+=16; var h=lines.length*16+10;
      var pos=t.getAttribute('data-note-pos'), room={top:bb.y-vb.y,bottom:vb.y+vb.h-(bb.y+bb.h),left:bb.x-vb.x,right:vb.x+vb.w-(bb.x+bb.w)};
      if(!pos){ pos=room.top>=h+14?'top':room.bottom>=h+14?'bottom':room.right>=w+14?'right':room.left>=w+14?'left':'top'; }
      var cx=bb.x+bb.w/2, cy=bb.y+bb.h/2, ax=cx, ay=cy, lx, ly;
      if(pos==='top'){ ay=bb.y; lx=cx; ly=bb.y-14-h/2; } else if(pos==='bottom'){ ay=bb.y+bb.h; lx=cx; ly=bb.y+bb.h+14+h/2; }
      else if(pos==='left'){ ax=bb.x; lx=bb.x-14-w/2; ly=cy; } else { ax=bb.x+bb.w; lx=bb.x+bb.w+14+w/2; ly=cy; }
      lx=Math.max(vb.x+w/2+2,Math.min(vb.x+vb.w-w/2-2,lx)); ly=Math.max(vb.y+h/2+2,Math.min(vb.y+vb.h-h/2-2,ly));
      box.setAttribute('x',lx-w/2); box.setAttribute('y',ly-h/2); box.setAttribute('width',w); box.setAttribute('height',h);
      tx.forEach(function(x,i){ x.setAttribute('x',lx); x.setAttribute('y',ly-h/2+17+i*16); });
      var ex=pos==='left'?lx+w/2:pos==='right'?lx-w/2:lx, ey=pos==='top'?ly+h/2:pos==='bottom'?ly-h/2:ly;
      line.setAttribute('x1',ax); line.setAttribute('y1',ay); line.setAttribute('x2',ex); line.setAttribute('y2',ey);
      t.__moNote=g; out.push(g);
    });
    svg.__moNotes=out; return out;
  }
  function allNotes(root){ outerSvgs(root).forEach(notes); }

  /* ================= 変更前／変更後（data-toggle） ================= */
  function setupToggle(f){
    var wrap=f.querySelector('.mo-states'); if(!wrap) return;
    var states=[].slice.call(wrap.querySelectorAll(':scope > .mo-state')); if(states.length<2) return;
    wrap.classList.add('mo-js');
    var bar=document.createElement('div'); bar.className='mo-bar'; bar.setAttribute('role','group');
    bar.setAttribute('aria-label','表示する状態');
    var cur=0, timer=0, user=false, T=tempoOf(f);
    function show(i,auto){
      states.forEach(function(s,k){ s.classList.toggle('mo-on',k===i); });
      each(bar.children,function(b,k){ b.setAttribute('aria-pressed',String(k===i)); });
      var s=states[i]; outerSvgs(s).forEach(notes);
      if(!REDUCE&&CAN&&i!==cur){
        s.animate([{opacity:0},{opacity:1}],{duration:380,easing:'ease-out'});
        each(s.querySelectorAll('[data-changed]'),function(x,k){
          x.animate([{opacity:.25},{opacity:1,offset:.35},{opacity:.55,offset:.6},{opacity:1}],{duration:1300*T,delay:200+k*90,easing:'ease-in-out'});
        });
      }
      cur=i;
    }
    states.forEach(function(s,i){
      var b=document.createElement('button'); b.type='button'; b.className='mo-chip'; b.textContent=s.getAttribute('data-state');
      b.addEventListener('click',function(){ user=true; clearInterval(timer); show(i); });
      bar.appendChild(b);
    });
    wrap.parentNode.insertBefore(bar,wrap);
    show(0);
    if(f.hasAttribute('data-toggle-auto')&&!REDUCE&&CAN){
      var io=new IntersectionObserver(function(en){
        clearInterval(timer);
        if(en[0].isIntersecting&&!user) timer=setInterval(function(){ show((cur+1)%states.length,true); },BASE.toggle*T);
      },{threshold:.4});
      io.observe(f);
    }
    f.__moToggle={wrap:wrap,show:show};
  }

  /* ================= シナリオの切り替え（data-paths / data-path） ================= */
  function runTokens(svg,paths,T,gen,f){
    if(REDUCE||!CAN||!paths.length) return;
    var i=0;
    (function next(){
      if(f.__moGen!==gen||i>=paths.length) return;
      var p=paths[i++], geo=tag(p)==='g'?p.querySelector('path,line,polyline'):p;
      var L=0; try{L=geo.getTotalLength();}catch(e){}
      if(!L){ next(); return; }
      var g=el('g',{'class':'mo-token','pointer-events':'none'}); g.appendChild(el('circle',{r:6,fill:'var(--accent)',stroke:'var(--card)','stroke-width':2}));
      geo.parentNode.insertBefore(g,geo.nextSibling);
      var D=BASE.token*T, t0=performance.now();
      (function step(now){
        if(f.__moGen!==gen){ g.remove(); return; }
        var k=Math.min(1,(now-t0)/D), e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2, pt=geo.getPointAtLength(L*e);
        g.setAttribute('transform','translate('+pt.x+','+pt.y+')');
        if(k<1) requestAnimationFrame(step); else { g.remove(); next(); }
      })(t0);
    })();
  }
  function setupPaths(f){
    var names=(f.getAttribute('data-paths')||'').split('|').filter(Boolean); if(!names.length) return;
    var bar=document.createElement('div'); bar.className='mo-bar'; bar.setAttribute('role','group'); bar.setAttribute('aria-label','経路');
    var T=tempoOf(f);
    function select(name){
      f.__moGen=(f.__moGen||0)+1;
      each(bar.children,function(b){ b.setAttribute('aria-pressed',String(b.__name===name)); });
      each(f.querySelectorAll('[data-path]'),function(x){
        var on=!name||x.getAttribute('data-path').split('|').indexOf(name)>=0;
        x.classList.toggle('mo-dim',!on);
      });
      if(!name) return;
      outerSvgs(f).forEach(function(svg){
        var list=[].filter.call(svg.querySelectorAll('[data-path]'),function(x){
          return x.getAttribute('data-path').split('|').indexOf(name)>=0&&(tag(x)==='path'||tag(x)==='line'||tag(x)==='polyline'||(tag(x)==='g'&&x.querySelector('path,line,polyline')&&!x.hasAttribute('data-node')));
        });
        list.sort(function(a,b){ return num(a.getAttribute('data-step'),0)-num(b.getAttribute('data-step'),0); });
        runTokens(svg,list,T,f.__moGen,f);
      });
    }
    ['すべて'].concat(names).forEach(function(n,i){
      var b=document.createElement('button'); b.type='button'; b.className='mo-chip'; b.textContent=n; b.__name=i?n:'';
      b.addEventListener('click',function(){ select(b.__name); });
      bar.appendChild(b);
    });
    var anchor=f.querySelector('.mo-states')||outerSvgs(f)[0];
    if(anchor) anchor.parentNode.insertBefore(bar,anchor);
    select('');
    f.__moPaths=select;
  }

  /* ================= 触れると関連が光る（data-hover） ================= */
  function setupHover(f){
    each(outerSvgs(f),function(svg){
      var nodes=[].slice.call(svg.querySelectorAll('[data-node]')), links=[].slice.call(svg.querySelectorAll('[data-link]'));
      if(!nodes.length) return;
      function on(id){
        var near={}; near[id]=1;
        links.forEach(function(l){ var e=l.getAttribute('data-link').split(' '); if(e.indexOf(id)>=0){ near[e[0]]=1; near[e[1]]=1; } });
        nodes.forEach(function(n){ n.classList.toggle('mo-dim',!near[n.getAttribute('data-node')]); });
        links.forEach(function(l){ l.classList.toggle('mo-dim',l.getAttribute('data-link').split(' ').indexOf(id)<0); });
      }
      function off(){ nodes.concat(links).forEach(function(x){ x.classList.remove('mo-dim'); }); }
      nodes.forEach(function(n){
        n.setAttribute('tabindex','0'); n.setAttribute('focusable','true');
        var id=n.getAttribute('data-node');
        n.addEventListener('pointerenter',function(){ on(id); }); n.addEventListener('pointerleave',off);
        n.addEventListener('focus',function(){ on(id); }); n.addEventListener('blur',off);
      });
    });
  }

  /* 操作（切り替え・経路・強調）と注記は、動きの設定に関係なく働く */
  each(document.querySelectorAll('.content figure[data-toggle]'),setupToggle);
  each(document.querySelectorAll('.content figure[data-paths]'),setupPaths);
  each(document.querySelectorAll('.content figure[data-hover]'),setupHover);
  window.addEventListener('beforeprint',function(){
    each(document.querySelectorAll('.mo-states.mo-js'),function(w){ w.classList.remove('mo-js'); w.classList.add('mo-was-js'); });
    each(document.querySelectorAll('.mo-dim'),function(x){ x.classList.remove('mo-dim'); });
    allNotes(document.querySelector('.content')||document);
  });
  window.addEventListener('afterprint',function(){
    each(document.querySelectorAll('.mo-was-js'),function(w){ w.classList.add('mo-js'); w.classList.remove('mo-was-js'); });
  });
  var content=document.querySelector('.content')||document.body;

  /* ================= 奥行き（data-depth）: スクロールに合わせて要素がずれる ================= */
  var depthEls=REDUCE?[]:[].slice.call(content.querySelectorAll('[data-depth]'));
  if(depthEls.length){
    var dq=false, par=function(){ dq=false; var vh=window.innerHeight||1;
      depthEls.forEach(function(x){ var r=(x.closest('figure')||x).getBoundingClientRect(), p=(r.top+r.height/2)/vh-.5; x.style.translate='0 '+(p*-num(x.getAttribute('data-depth'),1)*40).toFixed(1)+'px'; }); };
    window.addEventListener('scroll',function(){ if(!dq){ dq=true; requestAnimationFrame(par); } },{passive:true}); par();
    window.addEventListener('beforeprint',function(){ depthEls.forEach(function(x){ x.style.translate=''; }); });
  }

  /* ================= 部品の登場（カード・数字・年表・チェックリスト・表…）。--motion-blocks ================= */
  (function(){
    if(BLOCKS!=='on'||REDUCE||!CAN) return;
    var S=STYLE_DEF, T=TEMPOS[TEMPO_DEF]||1;
    var FR={gentle:function(){return [{opacity:0,translate:'0 14px'},{opacity:1,translate:'0 0'}];},
      dynamic:function(){return [{opacity:0,scale:'.85',translate:'0 26px'},{opacity:1,scale:'1.03',translate:'0 0',offset:.7},{opacity:1,scale:'1',translate:'0 0'}];},
      playful:function(i){return [{opacity:0,translate:'0 -30px',rotate:(i%2?'3deg':'-3deg')},{opacity:1,translate:'0 6px',rotate:'0deg',offset:.6},{opacity:1,translate:'0 0',rotate:'0deg'}];},
      cinematic:function(){return [{opacity:0,filter:'blur(6px)',translate:'0 10px'},{opacity:1,filter:'blur(0px)',translate:'0 0'}];},
      tech:function(){return [{opacity:0,clipPath:'inset(0 100% 0 0)'},{opacity:1,clipPath:'inset(0 0% 0 0)'}];},
      retro:function(){return [{opacity:0,clipPath:'inset(0 0 100% 0)',easing:'steps(5,end)'},{opacity:1,clipPath:'inset(0 0 0% 0)'}];},
      elegant:function(){return [{opacity:0,translate:'0 22px',filter:'blur(3px)'},{opacity:1,translate:'0 0',filter:'blur(0px)'}];},
      news:function(){return [{opacity:0,translate:'-40px 0',clipPath:'inset(0 100% 0 0)'},{opacity:1,translate:'0 0',clipPath:'inset(0 0% 0 0)'}];}};
    var fr=FR[S]||FR.gentle, GAP={dynamic:70,cinematic:140,playful:90,elegant:150,news:60,retro:110}[S]||90, DUR=({cinematic:800,dynamic:560,elegant:900,news:450,retro:600}[S]||520)*T;
    var GROUPS=[['.card-grid','.doc-card'],['.stat-row','.stat'],['.timeline','.tl-item'],['.chips','.chip'],['.ck-list','li'],['.pc-grid','.pc-col'],
                ['dl.defs','.def'],['.accordion','.acc-item'],['.tabs','.tab-list'],['table','tbody > tr'],['.callout',null],['.tree','ul > li'],
                ['.blk-hero',null],['.pq',null],['.price-grid','.price'],['.stepper',':scope > ol > .st'],['.kanban','.kb-col'],['.faq','.faq-item'],['.ba',null],
                ['.gal','.gal-item'],['.rm','.rm-lane'],['.pers-grid','.pers'],['.chev-row','.chev'],['.ctr-row','.ctr'],['.rt-list','.rt'],['.dd','.dd-col'],
                ['.voices','.voice'],['.dt-wrap',null],['.ig-grid','.ig'],['figure.diff',null],
                ['.lx-pyr',null],['.lx-cyc',null],['.lx-quad',null],['.lx-cht',null],['.lx-cal-wrap',null],['.lx-vs',null],['.lx-bnr-list','.lx-bnr'],
                ['.lx-swl',null],['.lx-zz','.lx-zz-row'],['.lx-rng-row','.lx-rng'],['.lx-tkr',null],['.lx-bn','.lx-bn-i'],['.lx-stk-wall',null],['.lx-flp-grid',null],
                ['.lx-agd',null],['.lx-mk','li']];
    var OVER='cubic-bezier(.34,1.56,.64,1)', ACC=cssv('--accent');
    var CLIPS={tech:1,retro:1,news:1};
    function add(st,x,frames,dur,delay,ease){ var a=x.animate(frames,{duration:dur*T,delay:delay*T,easing:ease||'cubic-bezier(.2,.7,.2,1)',fill:'backwards'}); a.pause(); st.anims.push(a); return a; }
    /* 部品ごとの動き（共通の「項目が順に現れる」に重ねる） */
    var SPECIAL={
      '.blk-hero':function(c,st){ var h=c.querySelector('.hero-h'), gl=c.querySelector('.hero-glow');
        if(h) add(st,h,[{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0% 0 0)'}],900,200,'cubic-bezier(.6,0,.2,1)');
        each(c.querySelectorAll('.hero-ic,.hero-sub,.hero-chips'),function(x,i){ add(st,x,[{opacity:0,translate:'0 14px'},{opacity:1,translate:'0 0'}],600,700+i*160); });
        if(gl) add(st,gl,[{transform:'translateX(-70%)',opacity:0},{transform:'translateX(-30%)',opacity:1}],1800,0,'ease-out'); },
      '.pq':function(c,st){ var m=c.querySelector('.pq-mark'), ws=c.querySelectorAll('.w'); if(m) add(st,m,[{opacity:0,transform:'translateY(-40px) rotate(-25deg)'},{opacity:.8,transform:'none'}],650,0,OVER);
        each(ws,function(w,i){ add(st,w,[{opacity:0,filter:'blur(4px)'},{opacity:1,filter:'blur(0px)'}],450,300+i*150); });
        var f=c.querySelector('figcaption'); if(f) add(st,f,[{opacity:0,translate:'16px 0'},{opacity:1,translate:'0 0'}],500,450+ws.length*150); },
      '.price-grid':function(c,st){ each(c.querySelectorAll('.price.is-rec'),function(p){ add(st,p,[{boxShadow:'0 0 0 0 transparent'},{boxShadow:'0 16px 44px '+ACC,offset:.5},{boxShadow:'0 6px 18px transparent'}],1600,900);
        var bd=p.querySelector('.price-badge'); if(bd) add(st,bd,[{transform:'translateX(-50%) scale(0)'},{transform:'translateX(-50%) scale(1)'}],500,800,OVER); }); },
      '.stepper':function(c,st){ var n=c.querySelectorAll('.st').length, L=c.querySelector('.st-line i'); if(L) add(st,L,[{transform:'scaleX(0)'},{transform:'scaleX(1)'}],n*380,200,'linear');
        each(c.querySelectorAll('.st-dot'),function(d,i){ add(st,d,[{transform:'scale(0)'},{transform:'scale(1.22)',offset:.7},{transform:'scale(1)'}],450,200+i*380); }); },
      '.kanban':function(c,st){ each(c.querySelectorAll('.kb-col'),function(col,i){ each(col.querySelectorAll('.kb-card'),function(cd,j){ add(st,cd,[{opacity:0,transform:'translateY(-26px) rotate(-3deg)'},{opacity:1,transform:'none'}],480,350+i*160+j*150,OVER); }); }); },
      '.ba':function(c,st){ st.after.push(function(){ if(!c.__baSet) return; var t0=performance.now(), D=2200*T;
        (function step(now){ var k=Math.min(1,(now-t0)/D), v=k<.45?100*(k/.45):k<.8?100-70*((k-.45)/.35):30+20*((k-.8)/.2); c.__baSet(Math.round(v)); if(k<1) requestAnimationFrame(step); })(t0); }); },
      '.gal':function(c,st){ each(c.querySelectorAll('.gal-btn img,.gal-ph'),function(im,i){ add(st,im,[{transform:'scale(1.3)',filter:'blur(8px)'},{transform:'scale(1)',filter:'blur(0px)'}],800,i*GAP); }); },
      '.pers-grid':function(c,st){ each(c.querySelectorAll('.pers-av'),function(av,i){ add(st,av,[{transform:'scale(0) rotate(-30deg)'},{transform:'scale(1.15) rotate(6deg)',offset:.6},{transform:'none'}],650,120+i*GAP,'ease-out'); }); },
      '.ctr-row':function(c,st){ each(c.querySelectorAll('.od-s'),function(s,i){ var d=parseInt(s.parentElement.style.getPropertyValue('--d'),10)||0;
        add(st,s,[{transform:'translateY(0)'},{transform:'translateY(-'+d+'em)'}],1100+i*120,150,'cubic-bezier(.15,.7,.25,1)'); }); },
      '.rt-list':function(c,st){ each(c.querySelectorAll('.rt-bar i'),function(b,i){ add(st,b,[{transform:'scaleX(0)'},{transform:'scaleX(1)'}],900,200+i*GAP); });
        each(c.querySelectorAll('.rt-fill'),function(f,i){ add(st,f,[{width:'0%'},{width:f.style.width}],1000,200+i*GAP,'steps(10,end)'); }); },
      '.dd':function(c,st){ each(c.querySelectorAll('.dd-col'),function(col,i){ add(st,col,[{translate:(i?'40px':'-40px')+' 0'},{translate:'0 0'}],600,0);
        each(col.querySelectorAll('li'),function(li,j){ add(st,li,[{opacity:0,translate:'0 8px'},{opacity:1,translate:'0 0'}],400,300+j*120+i*80); }); }); },
      '.voices':function(c,st){ var vs=[].slice.call(c.querySelectorAll('.voice')), r0=vs.length?vs[0].getBoundingClientRect():null;
        vs.forEach(function(v,i){ var r=v.getBoundingClientRect(), dx=r0?r0.left-r.left:0, dy=r0?r0.top-r.top:0, rot=getComputedStyle(v).getPropertyValue('--r')||'0deg';
          add(st,v,[{transform:'translate('+dx+'px,'+(dy+10)+'px) rotate('+rot+')'},{transform:'translate('+dx+'px,'+dy+'px) rotate('+rot+')',offset:.35},{transform:'none'}],1100,200+i*60,'cubic-bezier(.3,.8,.3,1)'); }); },
      '.dt-wrap':function(c,st){ each(c.querySelectorAll('.dt-n'),function(nd,i){ var dep=+nd.getAttribute('data-depth')||0; add(st,nd,[{opacity:0,transform:'translateY(-12px) scale(.9)'},{opacity:1,transform:'none'}],450,200+dep*380+(i%4)*60,OVER); }); },
      '.ig-grid':function(c,st){ each(c.querySelectorAll('.ig-ic'),function(ic,i){ add(st,ic,[{transform:'scale(0) rotate(-20deg)',borderRadius:'50%'},{transform:'scale(1.12)',offset:.6},{transform:'none',borderRadius:'18px'}],650,i*GAP,'ease-out'); }); },
      'figure.diff':function(c,st){ each(c.querySelectorAll('.dl-add,.dl-del'),function(l,i){ var bg=getComputedStyle(l).backgroundColor;
        add(st,l,[{backgroundColor:'transparent',translate:'-8px 0'},{backgroundColor:bg,translate:'0 0'}],420,300+i*110); }); },
      'table':function(c,st){ each(c.querySelectorAll('.raci'),function(r,i){ add(st,r,[{transform:'scale(0)'},{transform:'scale(1)'}],380,300+i*45,OVER); }); },
      /* ---- 追加の見せ方（lx-） ---- */
      '.lx-pyr':function(c,st){ var rows=[].slice.call(c.querySelectorAll('.lx-pyr-row')), n=rows.length;
        rows.forEach(function(r,i){ var d=(n-1-i)*230, b=r.querySelector('.lx-pyr-band'), t=r.querySelector('.lx-pyr-d');
          if(b) add(st,b,[{opacity:0,transform:'translateY(34px) scaleX(.55)'},{opacity:1,transform:'translateY(-3px) scaleX(1.02)',offset:.7},{opacity:1,transform:'none'}],560,d,'ease-out');
          if(t) add(st,t,[{opacity:0,translate:'24px 0'},{opacity:1,translate:'0 0'}],480,d+260); }); },
      '.lx-cyc':function(c,st){ var ring=c.querySelector('.lx-cyc-ring'), mid=c.querySelector('.lx-cyc-c');
        if(ring) add(st,ring,[{opacity:0,rotate:'-120deg',scale:'.7'},{opacity:1,rotate:'0deg',scale:'1'}],1000,0,'cubic-bezier(.2,.8,.2,1)');
        if(mid) add(st,mid,[{opacity:0,scale:'.3'},{opacity:1,scale:'1.1',offset:.7},{opacity:1,scale:'1'}],600,250);
        each(c.querySelectorAll('.lx-cyc-n'),function(nd,i){ add(st,nd,[{opacity:0,scale:'.3'},{opacity:1,scale:'1.12',offset:.7},{opacity:1,scale:'1'}],520,450+i*260); }); },
      '.lx-quad':function(c,st){ each(c.querySelectorAll('.lx-quad-y i'),function(x){ add(st,x,[{transform:'scaleY(0)'},{transform:'scaleY(1)'}],700,0); });
        each(c.querySelectorAll('.lx-quad-x i'),function(x){ add(st,x,[{transform:'scaleX(0)'},{transform:'scaleX(1)'}],700,0); });
        each(c.querySelectorAll('.lx-quad-x span,.lx-quad-y span'),function(x){ add(st,x,[{opacity:0},{opacity:1}],400,650); });
        each(c.querySelectorAll('.lx-quad-c'),function(q,i){ var qx=parseFloat(q.style.getPropertyValue('--qx'))||0, qy=parseFloat(q.style.getPropertyValue('--qy'))||0;
          add(st,q,[{opacity:0,translate:(-qx*50)+'px '+(-qy*40)+'px',scale:'.8'},{opacity:1,translate:'0 0',scale:'1'}],620,250+i*150,OVER);
          if(q.classList.contains('is-rec')){ add(st,q,[{boxShadow:'0 0 0 0 transparent'},{boxShadow:'0 0 0 10px '+ACC,offset:.4},{boxShadow:'0 0 0 0 transparent'}],1100,1100);
            var bd=q.querySelector('.lx-quad-badge'); if(bd) add(st,bd,[{transform:'scale(0) rotate(-20deg)'},{transform:'scale(1)'}],450,1000,OVER); } }); },
      '.lx-cht':function(c,st){ var t=150;
        each(c.querySelectorAll('.lx-cht-m'),function(m,i){ var r=m.classList.contains('is-r'), av=m.querySelector('.lx-cht-av'), b=m.querySelector('.lx-cht-b'),
            dots=m.querySelector('.lx-cht-dots'), x=m.querySelector('.lx-cht-x'), nm=m.querySelector('.lx-cht-n'), len=(x&&x.textContent.length)||10, typ=Math.min(900,280+len*9);
          if(av) add(st,av,[{opacity:0,scale:'0'},{opacity:1,scale:'1'}],320,t,OVER);
          if(nm) add(st,nm,[{opacity:0},{opacity:1}],300,t);
          if(b){ b.style.transformOrigin=r?'100% 100%':'0% 100%'; add(st,b,[{opacity:0,scale:'.4'},{opacity:1,scale:'1'}],320,t+80,OVER); }
          if(dots){ add(st,dots,[{opacity:0},{opacity:1,offset:.15},{opacity:1,offset:.85},{opacity:0}],typ,t+160);
            each(dots.children,function(d,j){ add(st,d,[{translate:'0 0'},{translate:'0 -4px',offset:.5},{translate:'0 0'}],360,t+160+j*110); }); }
          if(x) add(st,x,[{opacity:0},{opacity:1}],260,t+160+typ);
          t+=typ+420; }); },
      '.lx-cal-wrap':function(c,st){ each(c.querySelectorAll('.lx-cal'),function(cal,ci){ var base=ci*300;
        each(cal.querySelectorAll('.lx-cal-d'),function(d){ var i=parseInt(d.style.getPropertyValue('--i'),10)||0; add(st,d,[{opacity:0,scale:'.5'},{opacity:1,scale:'1'}],360,base+(Math.floor(i/7)+i%7)*45); });
        each(cal.querySelectorAll('.lx-cal-ev'),function(e,j){ add(st,e,[{opacity:0,translate:'-14px 0',scale:'.8'},{opacity:1,translate:'0 0',scale:'1'}],420,base+650+j*140,OVER); });
        each(cal.querySelectorAll('.lx-cal-l li'),function(li,j){ add(st,li,[{opacity:0,translate:'0 8px'},{opacity:1,translate:'0 0'}],380,base+700+j*120); }); }); },
      '.lx-vs':function(c,st){ var l=c.querySelector('.lx-vs-l'), r=c.querySelector('.lx-vs-r'), m=c.querySelector('.lx-vs-mid span');
        if(l) add(st,l,[{opacity:0,translate:'-110px 0'},{opacity:1,translate:'10px 0',offset:.75},{opacity:1,translate:'0 0'}],620,0,'ease-out');
        if(r) add(st,r,[{opacity:0,translate:'110px 0'},{opacity:1,translate:'-10px 0',offset:.75},{opacity:1,translate:'0 0'}],620,0,'ease-out');
        if(m) add(st,m,[{opacity:0,scale:'3',rotate:'-25deg'},{opacity:1,scale:'.88',rotate:'0deg',offset:.6},{opacity:1,scale:'1',rotate:'0deg'}],520,560,'ease-out');
        [l,r].forEach(function(x){ if(x) add(st,x,[{rotate:'0deg'},{rotate:'-1.2deg',offset:.25},{rotate:'1.2deg',offset:.5},{rotate:'-.5deg',offset:.75},{rotate:'0deg'}],420,900); });
        each(c.querySelectorAll('.lx-vs-s li'),function(li,i){ add(st,li,[{opacity:0},{opacity:1}],320,1100+i*90); });
        each(c.querySelectorAll('.lx-vs-badge'),function(b){ add(st,b,[{opacity:0,scale:'0'},{opacity:1,scale:'1'}],420,1350,OVER); }); },
      '.lx-bnr-list':function(c,st){ each(c.querySelectorAll('.lx-bnr'),function(b,i){ add(st,b,[{clipPath:'inset(0 100% 0 0 round 12px)'},{clipPath:'inset(0 0% 0 0 round 12px)'}],700,i*160,'cubic-bezier(.6,0,.2,1)');
        var tg=b.querySelector('.lx-bnr-tag'); if(tg) add(st,tg,[{opacity:0,scale:'0',rotate:'-15deg'},{opacity:1,scale:'1',rotate:'0deg'}],420,i*160+520,OVER);
        var tx=b.querySelector('.lx-bnr-t'); if(tx) add(st,tx,[{opacity:0,translate:'-16px 0'},{opacity:1,translate:'0 0'}],460,i*160+380); }); },
      '.lx-swl':function(c,st){ each(c.querySelectorAll('.lx-swl-lane'),function(l,i){ add(st,l,[{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0% 0 0)'}],650,i*120,'cubic-bezier(.6,0,.2,1)'); });
        each(c.querySelectorAll('.lx-swl-s'),function(s){ var k=parseInt(s.style.getPropertyValue('--c'),10)||1; add(st,s,[{opacity:0,translate:'-26px 0',scale:'.9'},{opacity:1,translate:'0 0',scale:'1'}],480,420+k*280,OVER); }); },
      '.lx-zz':function(c,st){ each(c.querySelectorAll('.lx-zz-row'),function(r,i){ var rev=r.classList.contains('is-rev'), v=r.querySelector('.lx-zz-v'), t=r.querySelector('.lx-zz-t'), no=r.querySelector('.lx-zz-no');
        if(v) add(st,v,[{opacity:0,transform:'translateX('+(rev?70:-70)+'px) rotate('+(rev?5:-5)+'deg) scale(.9)'},{opacity:1,transform:'none'}],800,i*GAP+100,'cubic-bezier(.2,.8,.2,1)');
        if(t) add(st,t,[{opacity:0,transform:'translateX('+(rev?-30:30)+'px)'},{opacity:1,transform:'none'}],700,i*GAP+300);
        if(no) add(st,no,[{opacity:0,scale:'2.2'},{opacity:.85,scale:'1'}],600,i*GAP+450,OVER); }); },
      '.lx-rng-row':function(c,st){ each(c.querySelectorAll('.lx-rng'),function(r,i){ var fg=r.querySelector('.lx-rng-fg'), v=r.querySelector('.lx-rng-v'), to=fg?parseFloat(fg.style.strokeDashoffset):0;
        if(fg) add(st,fg,[{strokeDashoffset:'100'},{strokeDashoffset:String(to)}],1300,150+i*GAP,'cubic-bezier(.2,.7,.2,1)');
        if(v) cnt(st,v,150+i*GAP); }); },
      '.lx-bn':function(c,st){ each(c.querySelectorAll('.lx-bn-i'),function(it,i){ var no=it.querySelector('.lx-bn-no span'), ru=it.querySelector('.lx-bn-rule');
        if(no) add(st,no,[{transform:'translateY(105%)'},{transform:'none'}],700,i*GAP+60,'cubic-bezier(.2,.9,.2,1)');
        if(ru) add(st,ru,[{transform:'scaleX(0)'},{transform:'scaleX(1)'}],600,i*GAP+380); }); },
      '.lx-stk-wall':function(c,st){ each(c.querySelectorAll('.lx-stk'),function(n,i){ var r=parseFloat(n.style.getPropertyValue('--r'))||0, pin=n.querySelector('.lx-stk-pin'), d=i*150+(hrand(i+5)*80|0);
        add(st,n,[{opacity:0,transform:'translateY(-80px) rotate('+(r*-4)+'deg) scale(1.2)'},{opacity:1,transform:'translateY(5px) rotate('+r+'deg) scale(.97)',offset:.72},{opacity:1,transform:'rotate('+r+'deg)'}],620,d,'cubic-bezier(.3,.7,.3,1)');
        if(pin) add(st,pin,[{opacity:0,transform:'translateY(-14px) scale(1.6)'},{opacity:1,transform:'none'}],300,d+480,OVER); }); },
      '.lx-flp-grid':function(c,st){ each(c.querySelectorAll('.lx-flp-in'),function(x,i){ add(st,x,[{transform:'rotateY(180deg)'},{transform:'rotateY(180deg)',offset:.25},{transform:'rotateY(-14deg)',offset:.8},{transform:'rotateY(0deg)'}],1100,i*170,'ease-in-out'); }); },
      '.lx-agd':function(c,st){ var its=c.querySelectorAll('.lx-agd-i'), ln=c.querySelector('.lx-agd-line'), P=320;
        if(ln) add(st,ln,[{transform:'scaleY(0)'},{transform:'scaleY(1)'}],its.length*P,100,'linear');
        each(its,function(it,i){ var d=100+i*P, dot=it.querySelector('.lx-agd-dot'), card=it.querySelector('.lx-agd-c'), tm=it.querySelector('.lx-agd-tm');
          if(dot) add(st,dot,[{transform:'scale(0)'},{transform:'scale(1.35)',offset:.6},{transform:'scale(1)'}],420,d,'ease-out');
          if(tm) add(st,tm,[{opacity:0,translate:'10px 0'},{opacity:1,translate:'0 0'}],380,d+60);
          if(card) add(st,card,[{opacity:0,translate:'30px 0'},{opacity:1,translate:'0 0'}],480,d+100,OVER); }); },
      '.lx-mk':function(c,st){ each(c.querySelectorAll(':scope > li'),function(li,i){ var ic=li.querySelector('.lx-mk-ic');
        if(ic) add(st,ic,[{scale:'0',rotate:'-90deg'},{scale:'1',rotate:'0deg'}],450,i*260+100,OVER);
        each(li.querySelectorAll('.lx-mk-t strong'),function(sg,j){ add(st,sg,[{backgroundSize:'0% 100%'},{backgroundSize:'100% 100%'}],650,i*260+350+j*200,'cubic-bezier(.6,0,.3,1)'); }); }); }
    };
    function cnt(st,b,delay){ var orig=b.textContent, m=orig.match(/-?[\d,]*\.?\d+/); if(!m) return;
      var to=parseFloat(m[0].replace(/,/g,'')), dec=(m[0].split('.')[1]||'').length, pre=orig.slice(0,m.index), post=orig.slice(m.index+m[0].length);
      st.drv.push({el:b,orig:orig,delay:delay*T,dur:1300,fmt:function(k){ return pre+(to*k).toFixed(dec)+post; }}); }
    var all=[];
    GROUPS.forEach(function(g){ each(content.querySelectorAll(g[0]),function(c){
      var par=c.parentElement; if(c.closest('.mo-block')||(par&&par.closest('figure'))||(g[0]!=='figure.diff'&&c.tagName==='FIGURE'&&g[0]!=='.pq')) return;
      var items=g[1]?[].slice.call(c.querySelectorAll(g[1])).filter(function(x){ return g[0]==='.tree'||g[1].indexOf(':scope')===0||x.parentElement===c||g[0]==='table'; }):[c];
      if(g[0]==='.tree') items=items.slice(0,40);
      if(g[0]==='table'&&items.length>30) return;
      if(!items.length) return;
      c.classList.add('mo-block');
      var st={c:c,anims:[],drv:[],after:[]};
      /* 部品そのものを動かすときは切り抜きを使わない（切り抜くと IntersectionObserver が見えないと判断して再生が始まらない） */
      items.forEach(function(x,i){ var a=x.animate(x===c&&CLIPS[S]?[{opacity:0,translate:'0 12px'},{opacity:1,translate:'0 0'}]:fr(i),{duration:DUR,delay:i*GAP*T,easing:'cubic-bezier(.2,.7,.2,1)',fill:'backwards'}); a.pause(); st.anims.push(a);
        /* 中のアイコンは線が描かれ、終わったら繰り返しの動き */
        each(x.querySelectorAll('svg.ico path'),function(pa,j){ var L=0; try{L=pa.getTotalLength();}catch(e){} if(!L) return; var dd=L+' '+L;
          var b=pa.animate([{strokeDasharray:dd,strokeDashoffset:L},{strokeDasharray:dd,strokeDashoffset:0}],{duration:650*T,delay:i*GAP*T+160+j*90*T,easing:'ease-in-out',fill:'backwards'}); b.pause(); st.anims.push(b); }); });
      /* 数字は数え上げ、チェックリストの棒・表の棒は伸びる */
      each(c.querySelectorAll('.stat .big'),function(b,i){ var orig=b.textContent, m=orig.match(/-?[\d,]*\.?\d+/); if(!m||b.children.length) return;
        var to=parseFloat(m[0].replace(/,/g,'')), dec=(m[0].split('.')[1]||'').length, comma=m[0].indexOf(',')>=0, pre=orig.slice(0,m.index), post=orig.slice(m.index+m[0].length);
        st.drv.push({el:b,orig:orig,delay:i*GAP*T+150,fmt:function(k){ var s=(to*k).toFixed(dec); if(comma){ var p=s.split('.'); p[0]=p[0].replace(/\B(?=(\d{3})+(?!\d))/g,','); s=p.join('.'); } return pre+s+post; }}); });
      each(c.querySelectorAll('.ck-bar i, .nbar'),function(b,i){ var a=b.animate([{scale:'0 1'},{scale:'1 1'}],{duration:900*T,delay:250+i*40*T,easing:'cubic-bezier(.2,.7,.2,1)',fill:'backwards'});
        b.style.transformOrigin='0 50%'; a.pause(); st.anims.push(a); });
      if(SPECIAL[g[0]]) try{ SPECIAL[g[0]](c,st); }catch(e){}
      all.push(st);
    }); });
    function run(st){ st.anims.forEach(function(a){ a.play(); }); st.after.forEach(function(f){ f(); });
      Promise.all(st.anims.map(function(a){ return a.finished; })).then(function(){ each(st.c.querySelectorAll('svg.ico'),function(s){ s.classList.add('ico-live'); }); st.c.classList.add('mo-live'); },function(){});
      st.drv.forEach(function(d){ var t0=performance.now()+d.delay, D=(d.dur||1100)*T; d.el.textContent=d.fmt(0);
        (function step(now){ var k=Math.max(0,Math.min(1,(now-t0)/D)); d.el.textContent=k>=1?d.orig:d.fmt(1-Math.pow(1-k,3)); if(k<1) requestAnimationFrame(step); })(performance.now()); }); }
    var bio=new IntersectionObserver(function(en){ en.forEach(function(e){ if(!e.isIntersecting) return; var st=e.target.__moB; if(st&&!st.done){ st.done=true; run(st); } bio.unobserve(e.target); }); },{threshold:.15});
    all.forEach(function(st){ st.c.__moB=st; bio.observe(st.c); });
    window.addEventListener('beforeprint',function(){ all.forEach(function(st){ st.anims.forEach(function(a){ try{a.finish();}catch(e){} }); st.drv.forEach(function(d){ d.el.textContent=d.orig; }); }); });
  })();

  if(REDUCE||!CAN||LEVEL==='off'&&!document.querySelector('.content [data-motion]:not([data-motion="none"]),.content figure[data-trigger]')){
    allNotes(content); return;          // 動かさない: 注記は最初から出しておく
  }

  /* ================= 登場の動き ================= */
  function containers(){
    var out=[];
    function add(c){ if(c&&out.indexOf(c)<0&&c.getAttribute('data-motion')!=='none'&&!c.classList.contains('manual-render')&&c.querySelector('svg')) out.push(c); }
    each(content.querySelectorAll('[data-motion],figure[data-trigger]'),function(x){ if(!x.closest('svg')) add(x); });   // trigger の指定も動かす意図とみなす
    if(LEVEL==='rich'){
      each(content.querySelectorAll('figure'),function(f){ if(!f.parentElement.closest('figure')) add(f); });
      each(content.querySelectorAll('.auto-fig-slot'),function(s){ if(!s.querySelector('figure')) add(s); });
    }
    return out;
  }
  function plan(st,svg){
    var T=st.T, explicit=[].slice.call(svg.querySelectorAll('[data-step]'));
    if(explicit.length){
      explicit=explicit.filter(function(x){ return !x.parentElement.closest('[data-step]'); });
      var nums=explicit.map(function(x){return num(x.getAttribute('data-step'),0);});
      var uniq=nums.slice().sort(function(a,b){return a-b;}).filter(function(v,i,a){return i===0||v!==a[i-1];});
      return {units:explicit.map(function(x,i){return {el:x,step:uniq.indexOf(nums[i])};}),gap:BASE.gapSteps*T};
    }
    var sr=svg.getBoundingClientRect(), area=sr.width*sr.height, leaves=[];
    (function walk(node){
      for(var c=node.firstElementChild;c;c=c.nextElementSibling){
        var t=tag(c);
        if(SKIP[t]||(c.classList&&(c.classList.contains('mo-token')||c.classList.contains('mo-note')))) continue;
        var group=(t==='g'||t==='a'||t==='switch'||(t==='svg'&&c!==svg));
        if(group&&!isAtomic(c)){ walk(c); continue; }
        if(!group&&!GEOM[t]) continue;
        var r=c.getBoundingClientRect();
        if(r.width===0&&r.height===0) continue;
        if(r.width*r.height>area*0.8&&!isAtomic(c)) continue;   // 背景の面は動かさない
        leaves.push({el:c,r:r});
      }
    })(svg);
    if(!leaves.length) return {units:[],gap:0};
    var dir=st.c.getAttribute('data-motion-dir')||'auto';
    if(dir==='auto') dir=sr.width>=sr.height*1.15?'x':'y';
    var cx=sr.left+sr.width/2, cy=sr.top+sr.height/2;
    leaves.forEach(function(l,i){
      var x=l.r.left+l.r.width/2, y=l.r.top+l.r.height/2;
      l.k= dir==='x'?x : dir==='reverse-x'?-x : dir==='reverse-y'?-y : dir==='radial'||dir==='center-out'?Math.hypot(x-cx,y-cy) : dir==='in'?-Math.hypot(x-cx,y-cy)
         : dir==='diagonal'?x+y : dir==='spiral'?Math.atan2(y-cy,x-cx) : dir==='random'?hrand(i) : y;
    });
    var lo=Infinity,hi=-Infinity; leaves.forEach(function(l){lo=Math.min(lo,l.k);hi=Math.max(hi,l.k);});
    var n=Math.max(3,Math.min(10,Math.round(leaves.length/3))), band=Math.max(1,(hi-lo)/n);
    return {units:leaves.map(function(l){return {el:l.el,step:Math.min(n-1,Math.floor((l.k-lo)/band))};}),
            gap:Math.min(BASE.gapAuto,BASE.autoTotal/n)*T};
  }
  function effectOf(x,st){
    var e=x.getAttribute('data-effect'); if(e) return e;
    var auto=tag(x)==='g'?(x.querySelector('path,line,polyline')&&[].every.call(x.querySelectorAll('*'),function(y){return !GEOM[tag(y)]||strokeOnly(y);})?'draw':'rise')
                        :(strokeOnly(x)?'draw':'rise');
    var S=st&&st.S; if(!S||!S.shape||auto==='draw') return auto;
    var t=tag(x); if(t==='text'||(t==='g'&&x.querySelector('text')&&!x.querySelector('rect,circle,ellipse,polygon,path'))) return S.text;
    var r=x.getBoundingClientRect(), sr=st.sr; return sr&&r.width*r.height>sr.width*sr.height*0.12?S.big:S.shape;
  }
  function track(st,a,end){ a.pause(); st.anims.push(a); st.end=Math.max(st.end,end); return a; }
  function withBox(st,x,origin){
    var pb=x.style.transformBox, po=x.style.transformOrigin;
    x.style.transformBox='fill-box'; x.style.transformOrigin=origin;
    var back=function(){ x.style.transformBox=pb; x.style.transformOrigin=po; };
    st.restores.push(back); return back;
  }
  /* 進み具合で中身を書き換える部品（数え上げ・入力・移動する印・ズーム）: 見えない代理アニメの進み具合で駆動する */
  function driven(st,x,dur,delay,fn){
    var a=x.animate([{},{}],{duration:dur,delay:delay});
    track(st,a,delay+dur);
    var d={a:a,fn:fn}; st.drivers.push(d);
    a.finished.then(function(){ fn(1); },function(){});
    return a;
  }
  function build(st,x,effect,delay){
    var T=st.T, t0=tag(x);
    /* 中に注釈のある要素を持つグループは、子ごとに組み立てる（棒の伸び・数え上げを内側で効かせる） */
    if((t0==='g'||t0==='a')&&!x.hasAttribute('data-effect')&&!x.hasAttribute('data-stagger')&&!x.hasAttribute('data-travel')
       &&x.querySelector('[data-effect],[data-count],[data-travel],[data-stagger]')){
      each(x.children,function(k){ var tk=tag(k); if(GEOM[tk]||tk==='g'||tk==='a') build(st,k,effectOf(k,st),delay); });
      return;
    }
    if(x.hasAttribute('data-stagger')){
      var kids=[].filter.call(x.children,function(k){return GEOM[tag(k)]||tag(k)==='g';});
      var gap=num(x.getAttribute('data-stagger'),BASE.stagger)*T, eff=x.getAttribute('data-effect')||'rise';
      kids.forEach(function(k,i){ build(st,k,k.getAttribute('data-effect')||eff,delay+i*gap); });
      return;
    }
    if(x.hasAttribute('data-count')) count(st,x,delay);
    if(x.hasAttribute('data-travel')) travel(st,x,delay);
    var o=getComputedStyle(x).opacity||'1', k0={opacity:0}, k1={opacity:o}, dur=BASE.rise*T, back, frames=null, OVER='cubic-bezier(.34,1.56,.64,1)';
    switch(effect){
      case 'none': return;
      case 'type': type(st,x,delay); return;
      case 'letters': letters(st,x,delay); return;
      case 'scramble': scramble(st,x,delay); return;
      case 'outline':
        var L2=0; try{L2=x.getTotalLength();}catch(e){}
        if(!L2||t0==='text'||t0==='g'){ k0.translate='0 10px'; k1.translate='0 0'; break; }
        var fo=getComputedStyle(x).fillOpacity||'1', dd=L2+' '+L2, D2=BASE.draw*T*1.5;
        track(st,x.animate([{strokeDasharray:dd,strokeDashoffset:L2,fillOpacity:0},{strokeDasharray:dd,strokeDashoffset:0,fillOpacity:0,offset:.65},{strokeDasharray:dd,strokeDashoffset:0,fillOpacity:fo}],
          {duration:D2,delay:delay,easing:'ease-in-out',fill:'backwards'}),delay+D2); return;
      case 'zoom': back=withBox(st,x,'center'); k0.scale='1.4'; k1.scale='1'; break;
      case 'flip': back=withBox(st,x,'center'); k0.scale='0 1'; k1.scale='1 1'; k0.easing=OVER; break;
      case 'flip-y': back=withBox(st,x,'center'); k0.scale='1 0'; k1.scale='1 1'; k0.easing=OVER; break;
      case 'spin': back=withBox(st,x,'center'); k0.rotate='-200deg'; k0.scale='.3'; k1.rotate='0deg'; k1.scale='1'; dur*=1.3; break;
      case 'roll': back=withBox(st,x,'center'); k0.translate='-60px 0'; k0.rotate='-120deg'; k1.translate='0 0'; k1.rotate='0deg'; dur*=1.2; break;
      case 'swing': back=withBox(st,x,'50% 0%'); k0.rotate='-28deg'; k1.rotate='0deg'; k0.easing=OVER; dur*=1.3; break;
      case 'drop': k0.translate='0 -70px'; k1.translate='0 0'; k0.easing=OVER; dur*=1.2; break;
      case 'slide-left': k0.translate='40px 0'; k1.translate='0 0'; break;
      case 'slide-right': k0.translate='-40px 0'; k1.translate='0 0'; break;
      case 'slide-up': k0.translate='0 30px'; k1.translate='0 0'; break;
      case 'slide-down': k0.translate='0 -30px'; k1.translate='0 0'; break;
      case 'blur': k0.filter='blur(8px)'; k1.filter='blur(0px)'; dur*=1.3; break;
      case 'iris': k0={opacity:o,clipPath:'circle(0% at 50% 50%)'}; k1={opacity:o,clipPath:'circle(75% at 50% 50%)'}; dur=BASE.draw*T; break;
      case 'blinds': k0={opacity:o,clipPath:'inset(50% 0 50% 0)'}; k1={opacity:o,clipPath:'inset(0% 0 0% 0)'}; dur=BASE.draw*T; break;
      case 'bounce': frames=[{opacity:0,translate:'0 -60px'},{opacity:o,translate:'0 0',offset:.45},{translate:'0 -18px',offset:.65},{translate:'0 0',offset:.8},{translate:'0 -5px',offset:.9},{opacity:o,translate:'0 0'}];
        dur*=1.9; break;
      case 'elastic': back=withBox(st,x,'center'); frames=[{opacity:0,scale:'0'},{opacity:o,scale:'1.25',offset:.35},{scale:'.88',offset:.55},{scale:'1.06',offset:.72},{scale:'.97',offset:.86},{opacity:o,scale:'1'}];
        dur*=1.8; break;
      case 'jelly': back=withBox(st,x,'center'); frames=[{opacity:0,scale:'1.3 .7'},{opacity:o,scale:'.85 1.15',offset:.4},{scale:'1.06 .94',offset:.7},{opacity:o,scale:'1 1'}]; dur*=1.6; break;
      case 'glitch': frames=[{opacity:0,translate:'-12px 0'},{opacity:o,translate:'8px 0',offset:.2},{translate:'-6px 2px',offset:.35},{opacity:.3,offset:.45},{opacity:o,translate:'3px -1px',offset:.6},{opacity:o,translate:'0 0'}];
        dur*=1.2; break;
      case 'flicker': frames=[{opacity:0},{opacity:o,offset:.15},{opacity:.1,offset:.25},{opacity:o,offset:.4},{opacity:.3,offset:.5},{opacity:o,offset:.65},{opacity:o}]; dur*=1.6; break;
      case 'mask': k0={opacity:o,clipPath:'inset(0 50% 0 50%)'}; k1={opacity:o,clipPath:'inset(0 0% 0 0%)'}; dur=BASE.draw*T; break;
      case 'wipe-up': k0={opacity:o,clipPath:'inset(100% 0 0 0)'}; k1={opacity:o,clipPath:'inset(0% 0 0 0)'}; dur=BASE.draw*T; break;
      case 'wipe-down': k0={opacity:o,clipPath:'inset(0 0 100% 0)'}; k1={opacity:o,clipPath:'inset(0 0 0% 0)'}; dur=BASE.draw*T; break;
      case 'wipe-left': k0={opacity:o,clipPath:'inset(0 0 0 100%)'}; k1={opacity:o,clipPath:'inset(0 0 0 0%)'}; dur=BASE.draw*T; break;
      case 'spring': back=withBox(st,x,'center'); frames=[{opacity:0,scale:'0'},{opacity:o,scale:'1.3',offset:.3},{scale:'.85',offset:.5},{scale:'1.08',offset:.68},{scale:'.97',offset:.84},{opacity:o,scale:'1'}]; dur*=2; break;
      case 'stamp': back=withBox(st,x,'center'); frames=[{opacity:0,scale:'2.2',rotate:'-8deg'},{opacity:o,scale:'.94',rotate:'0deg',offset:.55},{opacity:o,scale:'1',rotate:'0deg'}]; dur*=.9; break;
      case 'unfold': back=withBox(st,x,'50% 0%'); frames=[{opacity:o,scale:'1 0'},{opacity:o,scale:'1 1.08',offset:.7},{opacity:o,scale:'1 1'}]; dur*=1.3; break;
      case 'twist': back=withBox(st,x,'center'); k0.rotate='90deg'; k0.scale='.4'; k1.rotate='0deg'; k1.scale='1'; k0.easing=OVER; dur*=1.3; break;
      case 'skew': k0.translate='-40px 0'; k0.transform='skewX(-20deg)'; k1.translate='0 0'; k1.transform='skewX(0deg)'; break;
      case 'pop-up': back=withBox(st,x,'50% 100%'); k0.translate='0 40px'; k0.scale='.7'; k1.translate='0 0'; k1.scale='1'; k0.easing=OVER; dur*=1.2; break;
      case 'zoom-blur': back=withBox(st,x,'center'); k0.scale='1.6'; k0.filter='blur(10px)'; k1.scale='1'; k1.filter='blur(0px)'; dur*=1.3; break;
      case 'rise-rotate': back=withBox(st,x,'center'); k0.translate='0 30px'; k0.rotate='-8deg'; k1.translate='0 0'; k1.rotate='0deg'; break;
      case 'tilt-in': back=withBox(st,x,'0% 100%'); k0.rotate='-12deg'; k1.rotate='0deg'; k0.easing=OVER; dur*=1.2; break;
      case 'float-in': k0.translate='-30px 20px'; k0.filter='blur(3px)'; k1.translate='0 0'; k1.filter='blur(0px)'; dur*=1.5; break;
      case 'diamond': k0={opacity:o,clipPath:'polygon(50% 50%,50% 50%,50% 50%,50% 50%)'}; k1={opacity:o,clipPath:'polygon(50% -50%,150% 50%,50% 150%,-50% 50%)'}; dur=BASE.draw*T; break;
      case 'corner': k0={opacity:o,clipPath:'circle(0% at 0% 0%)'}; k1={opacity:o,clipPath:'circle(150% at 0% 0%)'}; dur=BASE.draw*T; break;
      case 'rubber': back=withBox(st,x,'center'); frames=[{opacity:0,scale:'1 1'},{opacity:o,scale:'1.25 .75',offset:.3},{scale:'.75 1.25',offset:.4},{scale:'1.15 .85',offset:.5},{scale:'.95 1.05',offset:.65},{scale:'1.05 .95',offset:.75},{opacity:o,scale:'1 1'}]; dur*=1.8; break;
      case 'slide-bounce': frames=[{opacity:0,translate:'-80px 0'},{opacity:o,translate:'12px 0',offset:.6},{translate:'-5px 0',offset:.8},{opacity:o,translate:'0 0'}]; dur*=1.5; break;
      case 'swirl': back=withBox(st,x,'center'); k0.rotate='-540deg'; k0.scale='0'; k0.filter='blur(4px)'; k1.rotate='0deg'; k1.scale='1'; k1.filter='blur(0px)'; dur*=1.6; break;
      case 'shake-in': frames=[{opacity:0,translate:'0 0'},{opacity:o,translate:'-10px 0',offset:.2},{translate:'9px 0',offset:.35},{translate:'-6px 0',offset:.5},{translate:'4px 0',offset:.65},{translate:'-2px 0',offset:.8},{opacity:o,translate:'0 0'}]; dur*=1.4; break;
      case 'pixel': k0={opacity:o,clipPath:'inset(0 100% 0 0)',easing:'steps(6,end)'}; k1={opacity:o,clipPath:'inset(0 0% 0 0)'}; dur=BASE.draw*T; break;
      case 'hinge': back=withBox(st,x,'0% 0%'); frames=[{opacity:0,rotate:'80deg'},{opacity:o,rotate:'-12deg',offset:.55},{rotate:'6deg',offset:.75},{rotate:'-2deg',offset:.9},{opacity:o,rotate:'0deg'}]; dur*=1.8; break;
      case 'swoosh': k0.translate='-160px 0'; k0.filter='blur(6px)'; k1.translate='0 0'; k1.filter='blur(0px)'; k0.easing='cubic-bezier(.1,.9,.2,1)'; dur*=1.1; break;
      case 'wobble': back=withBox(st,x,'50% 100%'); frames=[{opacity:0,translate:'0 20px',rotate:'0deg'},{opacity:o,translate:'0 0',rotate:'-7deg',offset:.3},{rotate:'5deg',offset:.5},{rotate:'-3deg',offset:.7},{rotate:'1deg',offset:.85},{opacity:o,translate:'0 0',rotate:'0deg'}]; dur*=1.8; break;
      case 'lift': frames=[{opacity:0,translate:'0 16px',filter:'drop-shadow(0 0 0 rgba(0,0,0,0))'},{opacity:o,translate:'0 -6px',filter:'drop-shadow(0 10px 8px rgba(0,0,0,.25))',offset:.6},{opacity:o,translate:'0 0',filter:'drop-shadow(0 0 0 rgba(0,0,0,0))'}]; dur*=1.5; break;
      case 'pendulum': back=withBox(st,x,'50% 0%'); frames=[{opacity:0,rotate:'40deg'},{opacity:o,rotate:'-25deg',offset:.3},{rotate:'14deg',offset:.5},{rotate:'-7deg',offset:.7},{rotate:'3deg',offset:.85},{opacity:o,rotate:'0deg'}]; dur*=2.2; break;
      case 'cascade':
        var ks=[].filter.call(x.children,function(k){return GEOM[tag(k)]||tag(k)==='g';});
        if(ks.length){ ks.forEach(function(k,i){ build(st,k,'drop',delay+i*90*T); }); return; }
        k0.translate='0 -40px'; k1.translate='0 0'; k0.easing=OVER; break;
      case 'draw':
        var paths=t0==='g'?[].slice.call(x.querySelectorAll('path,line,polyline')):[x];
        if(t0==='g') each(x.querySelectorAll('*'),function(y){ if(GEOM[tag(y)]&&!strokeOnly(y)&&!y.closest('.mo-token')) build(st,y,'fade',delay+BASE.draw*T*0.55); });
        paths.forEach(function(p){
          if(!strokeOnly(p)||p.closest('.mo-token')) return;
          var L=0; try{L=p.getTotalLength();}catch(e){}
          if(!L){ build(st,p,'fade',delay); return; }
          var ms=p.getAttribute('marker-start'), me=p.getAttribute('marker-end'), mb=null;
          if(ms||me){
            p.removeAttribute('marker-start'); p.removeAttribute('marker-end');
            mb=function(){ if(ms) p.setAttribute('marker-start',ms); if(me) p.setAttribute('marker-end',me); };
            st.restores.push(mb);
          }
          var d=L+' '+L, a=p.animate([{strokeDasharray:d,strokeDashoffset:L},{strokeDasharray:d,strokeDashoffset:0}],
                                   {duration:BASE.draw*T,delay:delay,easing:'ease-in-out',fill:'backwards'});
          track(st,a,delay+BASE.draw*T);
          if(mb) a.finished.then(mb,function(){});
        });
        return;
      case 'fade': break;
      case 'slide': k0.translate='-18px 0'; k1.translate='0 0'; break;
      case 'pop':
        back=withBox(st,x,'center'); k0.scale='.6'; k1.scale='1';
        k0.easing='cubic-bezier(.34,1.56,.64,1)'; dur=BASE.rise*T*1.1; break;
      case 'grow':
        var g=x.getAttribute('data-grow')||'up';
        back=withBox(st,x,{up:'50% 100%',down:'50% 0%',right:'0% 50%',left:'100% 50%'}[g]||'50% 100%');
        k0={opacity:o,scale:(g==='left'||g==='right')?'0 1':'1 0'}; k1={opacity:o,scale:'1 1'};
        dur=BASE.draw*T*1.15; break;
      case 'wipe':
        k0={opacity:o,clipPath:'inset(0 100% 0 0)'}; k1={opacity:o,clipPath:'inset(0 0% 0 0)'};
        dur=BASE.draw*T; break;
      default: k0.translate='0 10px'; k1.translate='0 0';   // rise
    }
    var a=x.animate(frames||[k0,k1],{duration:dur,delay:delay,easing:frames?'linear':EASE,fill:'backwards'});
    track(st,a,delay+dur);
    if(back) a.finished.then(back,function(){});
  }
  /* 1 文字ずつ現れる（text を文字ごとの tspan に分け、終わったら元に戻す） */
  function letters(st,x,delay){
    var targets=tag(x)==='text'?[x]:[].slice.call(x.querySelectorAll('text')), at=delay;
    targets.forEach(function(t){
      if(t.children.length){ build(st,t,'fade',at); return; }
      var orig=t.textContent, chars=Array.from(orig), n=chars.length, D=Math.max(320,n*55*st.T);
      t.textContent=''; var spans=chars.map(function(ch){ var s=document.createElementNS(NS,'tspan'); s.textContent=ch; s.setAttribute('fill-opacity','0'); t.appendChild(s); return s; });
      st.restores.push(function(){ t.textContent=orig; });
      driven(st,t,D,at,function(k){ spans.forEach(function(s,i){ var q=Math.max(0,Math.min(1,(k*(n+3)-i)/3)); s.setAttribute('fill-opacity',k>=1?'1':q.toFixed(2)); }); });
      at+=D*.6;
    });
  }
  /* でたらめな文字から定まる */
  var GLY='ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#$%&*+=?';
  function scramble(st,x,delay){
    var targets=tag(x)==='text'?[x]:[].slice.call(x.querySelectorAll('text'));
    targets.forEach(function(t){
      if(t.children.length){ build(st,t,'fade',delay); return; }
      var orig=t.textContent, chars=Array.from(orig), n=chars.length, D=Math.max(420,n*45*st.T);
      var a=t.animate([{opacity:0},{opacity:1}],{duration:1,delay:delay,fill:'backwards'}); track(st,a,delay+1);
      st.restores.push(function(){ t.textContent=orig; });
      driven(st,t,D,delay,function(k){ if(k>=1){ t.textContent=orig; return; } var f=Math.floor(k*30), out='';
        chars.forEach(function(ch,i){ out+=(i/n<k*1.15-.15||/\s/.test(ch))?ch:GLY[Math.floor(hrand(i*31+f)*GLY.length)]; }); t.textContent=out; });
    });
  }
  /* 破片が弾ける（data-burst）: 要素の中心から粒が散る */
  function burst(st,svg,x,delay){
    var bb=toUser(svg,x.getBoundingClientRect()); if(!bb) return;
    var g=el('g',{'class':'mo-token','pointer-events':'none'}), cx=bb.x+bb.w/2, cy=bb.y+bb.h/2, n=num(x.getAttribute('data-burst'),14)||14, R=Math.max(bb.w,bb.h)*.6+30;
    svg.appendChild(g); st.restores.push(function(){ if(g.parentNode) g.parentNode.removeChild(g); });
    for(var i=0;i<n;i++){
      var an=i/n*Math.PI*2+hrand(i)*.5, rr=R*(.6+hrand(i+9)*.6), c=el('circle',{cx:cx,cy:cy,r:3+hrand(i+3)*3,fill:'var(--a'+(i%4)+', var(--accent))',opacity:0});
      g.appendChild(c);
      track(st,c.animate([{translate:'0 0',opacity:1},{translate:(Math.cos(an)*rr).toFixed(1)+'px '+(Math.sin(an)*rr).toFixed(1)+'px',opacity:0}],
        {duration:BASE.burst*st.T,delay:delay,easing:'cubic-bezier(.1,.8,.3,1)'}),delay+BASE.burst*st.T);   /* 前後は属性の opacity:0 で隠れる */
    }
  }
  /* 波紋（強調の ring・data-ripple）: 要素を囲む円が広がって消える */
  function ringEl(svg,x){
    var bb=toUser(svg,x.getBoundingClientRect()); if(!bb) return null;
    return el('circle',{cx:bb.x+bb.w/2,cy:bb.y+bb.h/2,r:Math.max(bb.w,bb.h)/2+6,fill:'none',stroke:'var(--accent)','stroke-width':2.5,'pointer-events':'none','class':'mo-token',opacity:0,
                        style:'transform-box:fill-box;transform-origin:center'});
  }
  /* 現れた後の強調（data-attn）: 登場がすべて終わってから、段の順に 1 回 */
  function attn(st,svg){
    var els=[].slice.call(svg.querySelectorAll('[data-attn]')); if(!els.length) return;
    els.sort(function(a,b){ return num(a.getAttribute('data-step'),0)-num(b.getAttribute('data-step'),0); });
    var base=st.end+150, end=st.end, acc=cssv('--accent');
    els.forEach(function(x,i){
      var kind=x.getAttribute('data-attn')||'pulse', d=base+i*320, D=BASE.attn*st.T, fr, org='center';
      if(kind==='ring'){ for(var j=0;j<2;j++){ var c=ringEl(svg,x); if(!c) return; svg.appendChild(c); st.restores.push((function(c){ return function(){ if(c.parentNode) c.parentNode.removeChild(c); }; })(c));
          track(st,c.animate([{scale:'1',opacity:.9},{scale:'2.2',opacity:0}],{duration:D*1.2,delay:d+j*220,easing:'ease-out'}),d+j*220+D*1.2); }
        end=Math.max(end,d+D*1.6); return; }
      switch(kind){
        case 'shake': fr=[{translate:'0 0'},{translate:'-8px 0',offset:.15},{translate:'8px 0',offset:.3},{translate:'-6px 0',offset:.45},{translate:'6px 0',offset:.6},{translate:'-3px 0',offset:.75},{translate:'0 0'}]; break;
        case 'wiggle': fr=[{rotate:'0deg'},{rotate:'-8deg',offset:.2},{rotate:'8deg',offset:.4},{rotate:'-5deg',offset:.6},{rotate:'3deg',offset:.8},{rotate:'0deg'}]; break;
        case 'jump': fr=[{translate:'0 0'},{translate:'0 -18px',offset:.3},{translate:'0 0',offset:.55},{translate:'0 -6px',offset:.75},{translate:'0 0'}]; break;
        case 'pop': fr=[{scale:'1'},{scale:'1.2',offset:.4},{scale:'.95',offset:.7},{scale:'1'}]; break;
        case 'tada': fr=[{scale:'1',rotate:'0deg'},{scale:'.9',rotate:'-3deg',offset:.15},{scale:'1.12',rotate:'3deg',offset:.35},{scale:'1.12',rotate:'-3deg',offset:.55},{scale:'1.12',rotate:'3deg',offset:.75},{scale:'1',rotate:'0deg'}]; D*=1.4; break;
        case 'heartbeat': fr=[{scale:'1'},{scale:'1.15',offset:.15},{scale:'1',offset:.3},{scale:'1.12',offset:.45},{scale:'1'}]; D*=1.3; break;
        case 'flash': fr=[{opacity:1},{opacity:.15,offset:.25},{opacity:1,offset:.5},{opacity:.15,offset:.75},{opacity:1}]; break;
        case 'glow': fr=[{filter:'drop-shadow(0 0 0 '+acc+')'},{filter:'drop-shadow(0 0 12px '+acc+')',offset:.5},{filter:'drop-shadow(0 0 0 '+acc+')'}]; D*=1.6; break;
        default: fr=[{scale:'1'},{scale:'1.08',offset:.25},{scale:'1',offset:.5},{scale:'1.08',offset:.75},{scale:'1'}];
      }
      withBox(st,x,org); track(st,x.animate(fr,{duration:D,delay:d,easing:'ease-in-out'}),d+D); end=Math.max(end,d+D);
    });
    st.end=end;
  }
  /* 図全体の入り方（data-intro・動きの性格）。中の要素はその途中から現れる */
  function intro(st,svg){
    var name=st.c.getAttribute('data-intro')||st.S.intro; if(!name||name==='none'||!INTROS[name]) return 0;
    var D=BASE.intro*st.T; track(st,svg.animate(INTROS[name],{duration:D,easing:'cubic-bezier(.2,.8,.2,1)',fill:'backwards'}),D);
    return D*.45;
  }
  function type(st,x,delay){
    var targets=tag(x)==='text'?[x]:[].slice.call(x.querySelectorAll('text'));
    var at=delay;
    targets.forEach(function(t){
      var orig=t.textContent, n=orig.length, D=Math.max(260,n*BASE.type*st.T);
      var a=t.animate([{opacity:0},{opacity:1}],{duration:1,delay:at,fill:'backwards'}); track(st,a,at+1);
      t.__moOrig=orig; st.restores.push(function(){ t.textContent=orig; });
      driven(st,t,D,at,function(k){ t.textContent=k>=1?orig:orig.slice(0,Math.round(n*k)); });
      at+=D+60;
    });
  }
  function count(st,x,delay){
    var t=tag(x)==='text'?x:x.querySelector('text')||x;
    var orig=t.textContent, m=orig.match(/-?[\d,]*\.?\d+/);
    if(!m) return;
    var to=parseFloat(m[0].replace(/,/g,'')), spec=x.getAttribute('data-count')||'', f=spec.split(/→|->/);
    var from=num(f.length>1?f[0]:spec,0), dec=(m[0].split('.')[1]||'').length, comma=m[0].indexOf(',')>=0;
    var pre=orig.slice(0,m.index), post=orig.slice(m.index+m[0].length);
    function fmt(v){ var s=v.toFixed(dec); if(comma){ var p=s.split('.'); p[0]=p[0].replace(/\B(?=(\d{3})+(?!\d))/g,','); s=p.join('.'); } return pre+s+post; }
    t.textContent=fmt(from);
    st.restores.push(function(){ t.textContent=orig; });
    driven(st,x,BASE.count*st.T,delay,function(k){ t.textContent=k>=1?orig:fmt(from+(to-from)*(1-Math.pow(1-k,3))); });
  }
  function travel(st,x,delay){
    var p=tag(x)==='g'?x.querySelector('path,line,polyline'):x;
    if(!p||!p.getTotalLength) return;
    var L=0; try{L=p.getTotalLength();}catch(e){} if(!L) return;
    var g=el('g',{'class':'mo-token','pointer-events':'none',opacity:0});
    g.appendChild(el('circle',{r:6,fill:'var(--accent)',stroke:'var(--card)','stroke-width':2}));
    var label=x.getAttribute('data-travel'), bg, tx;
    if(label){
      bg=el('rect',{fill:'var(--accent)',rx:6}); tx=el('text',{'font-size':12,fill:'var(--on-accent)','text-anchor':'middle',y:-13,'font-family':'var(--mono)'});
      tx.textContent=label; g.appendChild(bg); g.appendChild(tx);
    }
    p.parentNode.insertBefore(g,p.nextSibling);
    if(label){ var w=0; try{w=tx.getComputedTextLength();}catch(e){} w=(w||label.length*7)+14;
      bg.setAttribute('x',-w/2); bg.setAttribute('y',-26); bg.setAttribute('width',w); bg.setAttribute('height',18); }
    st.restores.push(function(){ if(g.parentNode) g.parentNode.removeChild(g); });
    var start=delay+(effectOf(x,st)==='draw'?BASE.draw*st.T*0.9:0);
    driven(st,g,BASE.travel*st.T,start,function(k){
      if(k>=1||k<=0){ g.setAttribute('opacity','0'); return; }
      var e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2, pt=p.getPointAtLength(L*e);
      g.setAttribute('transform','translate('+pt.x+','+pt.y+')');
      g.setAttribute('opacity', k<.08?String(k/.08):k>.92?String((1-k)/.08):'1');
    });
  }
  function noteAnims(st,svg,units,gap,off){
    notes(svg).forEach(function(g){
      var target=null; each(svg.querySelectorAll('[data-note]'),function(t){ if(t.__moNote===g) target=t; });
      if(!target) return;
      var u=null; units.forEach(function(v){ if(v.el===target||v.el.contains(target)) u=v; });
      if(!u) return;                                      // 動かない要素の注記は最初から表示
      var d=(off||0)+u.step*gap+BASE.rise*st.T*0.8;
      track(st,g.animate([{opacity:0,translate:'0 6px'},{opacity:1,translate:'0 0'}],{duration:BASE.rise*st.T,delay:d,easing:EASE,fill:'backwards'}),d+BASE.rise*st.T);
    });
  }
  function focus(st,svg){
    var els=[].slice.call(svg.querySelectorAll('[data-focus]'));
    if(!els.length) return;
    var ranks=els.map(function(e){return num(e.getAttribute('data-focus'),0);});
    var uniq=ranks.slice().sort(function(a,b){return a-b;}).filter(function(v,i,a){return i===0||v!==a[i-1];});
    var n=uniq.length, hold=BASE.hold*st.T, fadeIn=260, D=n*hold+500, delay=st.end+300;
    els.forEach(function(e,i){
      var r=uniq.indexOf(ranks[i]), o=num(getComputedStyle(e).opacity,1), kf=[{offset:0,opacity:o}];
      for(var s=0;s<n;s++){ var v=s===r?o:o*.25;
        kf.push({offset:(s*hold+fadeIn)/D,opacity:v}); kf.push({offset:((s+1)*hold)/D,opacity:v}); }
      kf.push({offset:1,opacity:o});
      track(st,e.animate(kf,{duration:D,delay:delay,easing:'ease-in-out'}),delay+D);
    });
  }
  function zoom(st,svg){
    var targets=[].slice.call(svg.querySelectorAll('[data-zoom-step]')); if(!targets.length) return;
    var vb=vbox(svg); if(!vb) return;
    targets.sort(function(a,b){ return num(a.getAttribute('data-zoom-step'),0)-num(b.getAttribute('data-zoom-step'),0); });
    var boxes=targets.map(function(t){
      var b=toUser(svg,t.getBoundingClientRect()); if(!b) return vb;
      var pad=Math.max(b.w,b.h)*0.45+30, w=b.w+pad*2, h=b.h+pad*2, ar=vb.w/vb.h;
      if(w/h<ar) w=h*ar; else h=w/ar;
      w=Math.min(w,vb.w); h=Math.min(h,vb.h);
      var x=Math.max(vb.x,Math.min(vb.x+vb.w-w,b.x+b.w/2-w/2)), y=Math.max(vb.y,Math.min(vb.y+vb.h-h,b.y+b.h/2-h/2));
      return {x:x,y:y,w:w,h:h};
    });
    var seq=[vb]; boxes.forEach(function(b){ seq.push(b); seq.push(b); }); seq.push(vb);
    var mv=BASE.zoomMove*st.T, hd=BASE.zoomHold*st.T, segs=[];
    for(var i=0;i<seq.length-1;i++) segs.push({a:seq[i],b:seq[i+1],d:(i%2===0)?mv:hd});
    var D=segs.reduce(function(s,g){return s+g.d;},0), orig=svg.getAttribute('viewBox'), delay=st.end+400;
    st.restores.push(function(){ svg.setAttribute('viewBox',orig); });
    driven(st,svg,D,delay,function(k){
      if(k>=1){ svg.setAttribute('viewBox',orig); return; }
      var t=k*D;
      for(var j=0;j<segs.length;j++){ if(t<=segs[j].d||j===segs.length-1){
        var q=Math.min(1,t/segs[j].d); q=q<.5?4*q*q*q:1-Math.pow(-2*q+2,3)/2;
        var A=segs[j].a, B=segs[j].b;
        svg.setAttribute('viewBox',[A.x+(B.x-A.x)*q,A.y+(B.y-A.y)*q,A.w+(B.w-A.w)*q,A.h+(B.h-A.h)*q].join(' ')); return; }
        t-=segs[j].d; }
    });
  }
  function loops(st,svg){
    each(svg.querySelectorAll('[data-flow]'),function(p){
      (tag(p)==='g'?[].slice.call(p.querySelectorAll('path,line,polyline')):[p]).forEach(function(x){
        st.loops.push(x.animate([{strokeDasharray:'10 8',strokeDashoffset:18},{strokeDasharray:'10 8',strokeDashoffset:0}],{duration:BASE.flow*st.T,iterations:Infinity})); });
    });
    each(svg.querySelectorAll('[data-pulse]'),function(x){
      st.loops.push(x.animate([{opacity:1},{opacity:.45},{opacity:1}],{duration:BASE.pulse*st.T,iterations:Infinity,easing:'ease-in-out'}));
    });
    each(svg.querySelectorAll('[data-spin]'),function(x){
      withBox(st,x,'center'); var rev=x.getAttribute('data-spin')==='ccw';
      st.loops.push(x.animate([{rotate:'0deg'},{rotate:(rev?'-':'')+'360deg'}],{duration:BASE.spin*st.T,iterations:Infinity}));
    });
    var acc=cssv('--accent'), L=function(x,fr,D,o){ var a=x.animate(fr,Object.assign({duration:D*st.T,iterations:Infinity,easing:'ease-in-out'},o||{})); st.loops.push(a); return a; };
    each(svg.querySelectorAll('[data-float]'),function(x){ var h=num(x.getAttribute('data-float'),6)||6; L(x,[{translate:'0 0'},{translate:'0 -'+h+'px'},{translate:'0 0'}],BASE.float); });
    each(svg.querySelectorAll('[data-sway]'),function(x){ withBox(st,x,'50% 0%'); var dg=num(x.getAttribute('data-sway'),4)||4; L(x,[{rotate:'-'+dg+'deg'},{rotate:dg+'deg'},{rotate:'-'+dg+'deg'}],BASE.sway); });
    each(svg.querySelectorAll('[data-blink]'),function(x){ L(x,[{opacity:1},{opacity:1,offset:.6},{opacity:.15,offset:.75},{opacity:1}],BASE.blink); });
    each(svg.querySelectorAll('[data-heartbeat]'),function(x){ withBox(st,x,'center'); L(x,[{scale:'1'},{scale:'1.12',offset:.12},{scale:'1',offset:.25},{scale:'1.09',offset:.38},{scale:'1',offset:.55},{scale:'1'}],BASE.heartbeat); });
    each(svg.querySelectorAll('[data-glow]'),function(x){ L(x,[{filter:'drop-shadow(0 0 0 '+acc+')'},{filter:'drop-shadow(0 0 10px '+acc+')'},{filter:'drop-shadow(0 0 0 '+acc+')'}],BASE.glow); });
    each(svg.querySelectorAll('[data-march]'),function(x){ (tag(x)==='g'?[].slice.call(x.querySelectorAll('rect,circle,ellipse,polygon,path,line,polyline')):[x]).forEach(function(y){
      L(y,[{strokeDasharray:'8 6',strokeDashoffset:14},{strokeDasharray:'8 6',strokeDashoffset:0}],BASE.march,{easing:'linear'}); }); });
    each(svg.querySelectorAll('[data-wave]'),function(x){ [].filter.call(x.children,function(k){return GEOM[tag(k)]||tag(k)==='g';}).forEach(function(k,i){
      L(k,[{translate:'0 0'},{translate:'0 -8px',offset:.25},{translate:'0 0',offset:.5},{translate:'0 0'}],BASE.wave,{delay:-i*140*st.T}); }); });
    each(svg.querySelectorAll('[data-orbit]'),function(x){ var r=num(x.getAttribute('data-orbit'),10)||10, fr=[];
      for(var i=0;i<=12;i++){ var an=i/12*Math.PI*2; fr.push({translate:(Math.cos(an)*r).toFixed(1)+'px '+(Math.sin(an)*r).toFixed(1)+'px'}); }
      L(x,fr,BASE.orbit,{easing:'linear'}); });
    each(svg.querySelectorAll('[data-ripple]'),function(x){ for(var j=0;j<2;j++){ var c=ringEl(svg,x); if(!c) return; svg.appendChild(c); st.loopEls.push(c);
      L(c,[{scale:'1',opacity:.7},{scale:'2.4',opacity:0}],BASE.ripple,{easing:'ease-out',delay:-j*BASE.ripple*st.T/2}); } });
    each(svg.querySelectorAll('[data-stream]'),function(x){ var p=tag(x)==='g'?x.querySelector('path,line,polyline'):x, Ln=0; try{Ln=p.getTotalLength();}catch(e){} if(!Ln) return;
      var n=num(x.getAttribute('data-stream'),3)||3; for(var j=0;j<n;j++){ var g=el('g',{'class':'mo-token','pointer-events':'none'}); g.appendChild(el('circle',{r:4.5,fill:'var(--accent)'}));
        p.parentNode.insertBefore(g,p.nextSibling); st.loopEls.push(g); st.streams.push({g:g,p:p,L:Ln,ph:j/n}); } });
    each(svg.querySelectorAll('[data-breathe]'),function(x){ withBox(st,x,'center'); L(x,[{scale:'1',opacity:1},{scale:'1.045',opacity:.82},{scale:'1',opacity:1}],BASE.breathe); });
    each(svg.querySelectorAll('[data-shine]'),function(x){ L(x,[{filter:'brightness(1)'},{filter:'brightness(1)',offset:.6},{filter:'brightness(1.45)',offset:.75},{filter:'brightness(1)',offset:.9},{filter:'brightness(1)'}],BASE.shine); });
    each(svg.querySelectorAll('[data-jiggle]'),function(x){ withBox(st,x,'center'); L(x,[{rotate:'0deg'},{rotate:'0deg',offset:.7},{rotate:'-6deg',offset:.76},{rotate:'6deg',offset:.82},{rotate:'-4deg',offset:.88},{rotate:'2deg',offset:.94},{rotate:'0deg'}],BASE.jiggle); });
    each(svg.querySelectorAll('[data-hop]'),function(x){ withBox(st,x,'50% 100%'); var h=num(x.getAttribute('data-hop'),14)||14;
      L(x,[{translate:'0 0',scale:'1 1'},{translate:'0 0',scale:'1.1 .9',offset:.15},{translate:'0 -'+h+'px',scale:'.95 1.05',offset:.4},{translate:'0 0',scale:'1.06 .94',offset:.62},{translate:'0 0',scale:'1 1',offset:.78},{translate:'0 0',scale:'1 1'}],BASE.hop,{easing:'linear'}); });
    each(svg.querySelectorAll('[data-tick]'),function(x){ withBox(st,x,x.getAttribute('data-tick-origin')||'center'); var n=Math.max(2,Math.round(num(x.getAttribute('data-tick'),12)||12));
      L(x,[{rotate:'0deg'},{rotate:'360deg'}],BASE.tick,{easing:'steps('+n+',end)'}); });
    each(svg.querySelectorAll('[data-redraw]'),function(x){ (tag(x)==='g'?[].slice.call(x.querySelectorAll('path,line,polyline')):[x]).forEach(function(p){ var Ln=0; try{Ln=p.getTotalLength();}catch(e){} if(!Ln) return; var d=Ln+' '+Ln;
      L(p,[{strokeDasharray:d,strokeDashoffset:0},{strokeDasharray:d,strokeDashoffset:0,offset:.4},{strokeDasharray:d,strokeDashoffset:-Ln,offset:.6},{strokeDasharray:d,strokeDashoffset:Ln,offset:.6001},{strokeDasharray:d,strokeDashoffset:0}],BASE.redraw); }); });
    each(svg.querySelectorAll('[data-hue]'),function(x){ L(x,[{filter:'hue-rotate(0deg)'},{filter:'hue-rotate(360deg)'}],BASE.hue,{easing:'linear'}); });
    if(st.streams.length) streamKick();
    if(!st.inView) st.loops.forEach(function(a){a.pause();});
  }
  /* 線の上を印が流れ続ける（data-stream）: 見えている図だけ動かす */
  var streaming=false;
  function streamKick(){ if(streaming) return; streaming=true; requestAnimationFrame(streamTick); }
  function streamTick(now){
    var any=false;
    states.forEach(function(st){ if(!st.inView||!st.streams.length) return; any=true;
      st.streams.forEach(function(s){ var k=((now/(BASE.stream*st.T))+s.ph)%1, pt=s.p.getPointAtLength(s.L*k); s.g.setAttribute('transform','translate('+pt.x+','+pt.y+')');
        s.g.setAttribute('opacity',k<.08?String(k/.08):k>.92?String((1-k)/.08):'1'); }); });
    if(any) requestAnimationFrame(streamTick); else streaming=false;
  }

  /* ---- 再生の制御 ---- */
  var driving=false, states=[];
  function drive(){
    var any=false;
    states.forEach(function(st){ st.drivers.forEach(function(d){
      if(d.a.playState!=='running') return; any=true;
      var k=d.a.effect.getComputedTiming().progress; if(k!==null) d.fn(k); }); });
    if(any) requestAnimationFrame(drive); else driving=false;
  }
  function reset(st){
    clearTimeout(st.timer);
    st.anims.forEach(function(a){try{a.cancel();}catch(e){}});
    st.loops.forEach(function(a){try{a.cancel();}catch(e){}});
    for(var i=st.restores.length-1;i>=0;i--) st.restores[i]();
    (st.loopEls||[]).forEach(function(e){ if(e.parentNode) e.parentNode.removeChild(e); });
    st.anims=[]; st.loops=[]; st.restores=[]; st.drivers=[]; st.svgs=[]; st.end=0; st.loopEls=[]; st.streams=[];
  }
  function arm(st){
    reset(st);
    st.T=tempoOf(st.c); st.S=styleOf(st.c);
    try{
      outerSvgs(st.c).filter(shown).forEach(function(svg){
        notes(svg);
        st.sr=svg.getBoundingClientRect();
        var pl=plan(st,svg), off=intro(st,svg), gap=pl.gap*(st.S.gap||1);
        pl.units.forEach(function(u){ build(st,u.el,effectOf(u.el,st),off+u.step*gap);
          (u.el.hasAttribute('data-burst')?[u.el]:[].slice.call(u.el.querySelectorAll('[data-burst]'))).forEach(function(b){ burst(st,svg,b,off+u.step*gap+BASE.rise*st.T*.6); }); });
        noteAnims(st,svg,pl.units,gap,off);
        st.svgs.push(svg);
      });
      st.svgs.forEach(function(svg){ attn(st,svg); });
      st.svgs.forEach(function(svg){ focus(st,svg); });
      var base=st.end; st.svgs.forEach(function(svg){ st.end=base; zoom(st,svg); });
    }catch(e){ reset(st); }
  }
  function play(st){
    arm(st);
    var runs=st.anims.slice(), svgs=st.svgs.slice(), gen=++st.gen;
    runs.forEach(function(a){ a.currentTime=0; a.play(); });
    if(!driving&&st.drivers.length){ driving=true; requestAnimationFrame(drive); }
    st.c.classList.add('mo-played');
    Promise.all(runs.map(function(a){return a.finished;})).then(function(){
      if(gen!==st.gen) return;
      for(var i=st.restores.length-1;i>=0;i--) st.restores[i]();
      st.restores=[];
      svgs.forEach(function(svg){ loops(st,svg); });
      if(st.trigger==='loop') st.timer=setTimeout(function(){ if(st.inView) play(st); else st.pending=true; },BASE.loopRest*st.T);
    },function(){});
  }
  /* スクロール連動: 図が画面を通る位置で進み具合を決める */
  function scrub(st){
    var r=st.c.getBoundingClientRect(), vh=window.innerHeight||1;
    var p=Math.max(0,Math.min(1,(vh-r.top)/(vh*0.55+r.height*0.35)));
    if(p===st.p) return; st.p=p;
    var t=p*st.end;
    st.anims.forEach(function(a){ a.currentTime=t; });
    st.drivers.forEach(function(d){
      var ct=d.a.effect.getComputedTiming(), k=ct.progress;
      if(k===null) k=t>=(ct.endTime||0)?1:0;
      d.fn(k);
    });
    if(p>=1&&!st.looped){ st.looped=true; st.svgs.forEach(function(svg){ loops(st,svg); }); }
  }
  var scrubbing=[];
  if(!REDUCE) window.addEventListener('scroll',function(){ scrubbing.forEach(function(st){ if(!st.q){ st.q=true; requestAnimationFrame(function(){ st.q=false; scrub(st); }); } }); },{passive:true});
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(en){
      var st=en.target.__mo; if(!st) return;
      st.inView=en.isIntersecting;
      if(st.trigger==='scroll'){ scrub(st); return; }
      if(en.isIntersecting&&((!st.played&&st.trigger!=='click')||st.pending)){ st.played=true; st.pending=false; play(st); }
      st.loops.forEach(function(a){ en.isIntersecting?a.play():a.pause(); });
      if(en.isIntersecting&&st.streams.length) streamKick();
    });
  },{threshold:0.3});
  containers().forEach(function(c){
    var st={c:c,anims:[],loops:[],restores:[],drivers:[],svgs:[],end:0,T:1,gen:0,played:false,inView:false,pending:false,loopEls:[],streams:[],S:STYLES.gentle,
            trigger:c.getAttribute('data-trigger')||'view',p:-1};
    c.__mo=st; states.push(st);
    c.classList.add('mo-fig');
    if(st.trigger!=='scroll'){
      var b=document.createElement('button');
      b.type='button'; b.className='mo-replay'+(st.trigger==='click'?' mo-click':'');
      b.textContent=st.trigger==='click'?'▶ 動きを再生':'↻ 再生';
      b.setAttribute('aria-label',st.trigger==='click'?'図の動きを再生':'図の動きをもう一度再生');
      b.addEventListener('click',function(){ st.played=true; st.pending=false; play(st); });
      c.appendChild(b);
    }
    if(st.trigger==='click') outerSvgs(c).forEach(notes);   // click は完成図のまま待つ
    else arm(st);                                           // 見えるまでは最初のコマで待機
    if(st.trigger==='scroll'){ scrubbing.push(st); st.p=-1; scrub(st); }
    io.observe(c);
  });
  /* 印刷: 動きを終わりのコマに揃える（注記は残す） */
  window.addEventListener('beforeprint',function(){ states.forEach(function(st){
    st.anims.forEach(function(a){try{a.finish();}catch(e){}});
    st.drivers.forEach(function(d){ d.fn(1); });
    st.loops.forEach(function(a){try{a.cancel();}catch(e){}});
    for(var i=st.restores.length-1;i>=0;i--) st.restores[i]();
    st.restores=[];
  }); });
  if(mq&&mq.addEventListener) mq.addEventListener('change',function(e){ if(e.matches) states.forEach(reset); });
})();"""


MOTION_TEMPOS = ["slow", "normal", "fast"]
MOTION_STYLES = ["gentle", "dynamic", "playful", "cinematic", "tech", "retro", "elegant", "news"]
# 動きの性格と部品の登場（main で CLI の値に書き換える。convert_file の引数を増やさないため）
MOTION_OPTS = {"style": "gentle", "blocks": "auto"}


def motion_html(level, tempo="normal"):
    # off でも埋め込む: 切り替え・経路・関連の強調・注記は動きの設定と無関係に働く。
    # off のときは、data-motion を明示した図以外は登場の動きをしない。
    blocks = MOTION_OPTS["blocks"]
    if blocks == "auto":
        blocks = "on" if level == "rich" else "off"
    return "<style>%s</style>\n<script>%s</script>" % (
        MOTION_CSS, MOTION_JS.replace("__MOTION_LEVEL__", level).replace("__MOTION_TEMPO__", tempo)
                              .replace("__MOTION_STYLE__", MOTION_OPTS["style"]).replace("__MOTION_BLOCKS__", blocks))



# ──────────────────────────────────────────────────────────────────────────
def inject_figure_slots(content, headings):
    """auto-figure 有効時、各 H2 セクションの末尾に差し込み用スロットを置く。
    Claude が内容を解釈し、図解すべき箇所に <svg> を入れる。空のままなら非表示。"""
    h2s = [h for h in headings if h["level"] == 2]
    if not h2s:
        return content
    for k in range(1, len(h2s)):
        slot = '<div class="auto-fig-slot" data-section="%s"></div>\n' % h2s[k - 1]["slug"]
        target = '<h2 id="%s"' % h2s[k]["slug"]
        content = content.replace(target, slot + target, 1)
    content += '\n<div class="auto-fig-slot" data-section="%s"></div>' % h2s[-1]["slug"]
    return content


def convert_file(path, theme_key, eyebrow=None, auto_figure="off", toc_mode="sidebar",
                 layout="plain", design="deterministic", default_mode="system",
                 image_mode="embed", outdir=None, layout_map=None, motion="off",
                 motion_tempo="normal"):
    global _IMG_BASE, _IMG_OUTDIR, _IMG_MODE, _LAYOUT_MAP
    if layout_map is not None:
        _LAYOUT_MAP = layout_map
    _IMG_BASE = os.path.dirname(os.path.abspath(path))
    _IMG_OUTDIR = os.path.abspath(outdir) if outdir else _IMG_BASE
    _IMG_MODE = image_mode
    raw = open(path, encoding="utf-8").read()
    meta, body = split_frontmatter(raw)
    lines = body.replace("\r\n", "\n").split("\n")

    # 先頭の H1 をタイトルに昇格（hero に出すため本文からは除外）
    title = meta.get("title")
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if not title and idx < len(lines):
        m = re.match(r"^#\s+(.*)$", lines[idx])
        if m:
            title = m.group(1).strip()
            lines = lines[:idx] + lines[idx + 1:]
    if not title:
        title = os.path.splitext(os.path.basename(path))[0]

    if eyebrow and "eyebrow" not in meta:
        meta["eyebrow"] = eyebrow
    if "date" not in meta:
        fm = re.match(r"(\d{2,4}[-_/]\d{1,2}([-_/]\d{1,2})?)", os.path.basename(path))
        if fm:
            meta["date"] = fm.group(1).replace("_", "-").replace("/", "-")

    global _ACCENTS
    _ACCENTS = accent_vars(theme_key)
    _DOC_THEME[0] = theme_key

    # AI設計（freeform もしくは design=ai）: 本文は Claude が後段で著述する。
    # ガワだけ生成し中身はプレースホルダにする。
    if layout == "freeform" or design == "ai":
        headings = extract_headings(lines)
        content = "<!--MD2DOC_CONTENT-->"
        brand = meta.get("brand", title)
        footer = "%s — Generated from Markdown by md-to-doc" % (meta.get("date") or
                 datetime.date.today().isoformat())
        out_html = build_html(meta, content, headings, theme_key, title, brand, footer,
                              toc_mode, default_mode, motion, motion_tempo)
        return out_html, title, headings, True, []

    headings, used, mermaid_store = [], set(), []
    content = parse_blocks(lines, headings, used, mermaid_store, top_level=True, layout=layout)

    rendered, ok = render_mermaid(mermaid_store, THEMES[theme_key])
    pending = []  # mmdc 無し時に Claude が手描きする図
    for i, src in enumerate(mermaid_store):
        svg = rendered.get(i)
        if svg:
            content = content.replace("@@MERMAID_%d@@" % i, svg)
        else:
            eid = "md2doc-mm-%d" % i
            content = content.replace("@@MERMAID_%d@@" % i, manual_mermaid_figure(eid, src))
            pending.append({"id": eid, "source": src})

    if auto_figure != "off":
        content = inject_figure_slots(content, headings)

    brand = meta.get("brand", title)
    footer = "%s — Generated from Markdown by md-to-doc" % (meta.get("date") or
             datetime.date.today().isoformat())
    out_html = build_html(meta, content, headings, theme_key, title, brand, footer,
                          toc_mode, default_mode, motion, motion_tempo)
    out_html = add_motion_runtime(out_html)
    return out_html, title, headings, ok, pending



# ──────────────────────────────────────────────────────────────────────────
# AI 構築の仕上げ（--finalize）
#   Claude が書いた本文の中の <!--MD2DOC-PART layout=…--> … <!--/MD2DOC-PART--> を、
#   決定論的な部品（リストのレイアウト・表・コード・mermaid）に置き換える。
# ──────────────────────────────────────────────────────────────────────────
PART_RE = re.compile(r"<!--\s*MD2DOC-PART(?:\s+layout\s*=\s*([\w-]+))?\s*-->(.*?)<!--\s*/MD2DOC-PART\s*-->", re.S)


def finalize_html(path, theme_key, src=None):
    global _IMG_BASE, _IMG_OUTDIR, _IMG_MODE, _ACCENTS
    doc = open(path, encoding="utf-8").read()
    _IMG_BASE = os.path.dirname(os.path.abspath(src)) if src else os.path.dirname(os.path.abspath(path))
    _IMG_OUTDIR = os.path.dirname(os.path.abspath(path))
    _ACCENTS = accent_vars(theme_key)
    store, count, bad = [], [0], []

    def one(m):
        lay = (m.group(1) or "plain").lower()
        if lay not in DET_LAYOUTS:
            bad.append(lay)
            lay = "plain"
        md = m.group(2)
        lines = md.replace("\r\n", "\n").split("\n")
        # 断片の共通の字下げを外す（HTML の中に字下げして書かれていてもよい）
        ind = min([len(l) - len(l.lstrip(" ")) for l in lines if l.strip()] or [0])
        lines = [l[ind:] if len(l) >= ind else l for l in lines]
        base = len(store)
        local = []
        part = parse_blocks(lines, [], set(), local, top_level=True, layout=lay)
        for k in range(len(local)):
            part = part.replace("@@MERMAID_%d@@" % k, "@@MERMAID_%d@@" % (base + k))
        store.extend(local)
        count[0] += 1
        return part

    doc = PART_RE.sub(one, doc)
    _DOC_THEME[0] = theme_key
    doc = add_motion_runtime(replace_videos(doc, _IMG_BASE, theme_key))
    rendered, ok = render_mermaid(store, THEMES[theme_key])
    pending = []
    for i, src_ in enumerate(store):
        svg = rendered.get(i)
        if svg:
            doc = doc.replace("@@MERMAID_%d@@" % i, svg)
        else:
            eid = "md2doc-mm-%d" % i
            doc = doc.replace("@@MERMAID_%d@@" % i, manual_mermaid_figure(eid, src_))
            pending.append({"out": path, "id": eid, "source": src_})
    open(path, "w", encoding="utf-8").write(doc)
    return count[0], pending, bad, "<!--MD2DOC_CONTENT-->" in doc

# ──────────────────────────────────────────────────────────────────────────
# 動画の埋め込み（motion-video のプレイヤーを文書の中に置く）
#   <!--MD2DOC-VIDEO src="intro.json" player="minimal" theme="midnight"-->
#   台本は motion-video の形式（部品・混在・自由のどれでも）。プレイヤー・時間割・字幕・音声は motion-video が受け持つ。
# ──────────────────────────────────────────────────────────────────────────
VIDEO_RE = re.compile(r'<!--\s*MD2DOC-VIDEO\s+([^>]*?)\s*-->')
VIDEO_THEME = {"corporate": "daylight", "darktech": "midnight", "infographic": "vivid", "editorial": "paper", "pastel": "daylight",
               "formal": "daylight", "manual": "daylight", "contrast": "mono", "blueprint": "navy-brass", "minimal": "daylight",
               "paper": "paper", "aurora": "vivid", "nordic": "daylight"}
_MV = [None]


def _motion_video():
    """隣の motion-video スキルの build.py を読み込む（無ければ None）。"""
    if _MV[0] is None:
        import importlib.util
        here = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(here, "..", "motion-video", "build.py")
        if not os.path.isfile(path):
            _MV[0] = False
        else:
            spec = importlib.util.spec_from_file_location("motion_video_build", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _MV[0] = mod
    return _MV[0] or None


def video_attrs(text):
    return dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', text))


def video_fragment(attrs, base, doc_theme):
    mv = _motion_video()
    if not mv:
        return '<div class="callout callout-warning"><div class="callout-body">motion-video スキルが見つからないため、動画を埋め込めませんでした。</div></div>'
    src = attrs.get("src", "")
    path = src if os.path.isabs(src) else os.path.join(base or ".", src)
    if not os.path.isfile(path):
        print("warn: MD2DOC-VIDEO の台本が見つかりません: %s" % path, file=sys.stderr)
        return '<div class="callout callout-warning"><div class="callout-body">動画の台本が見つかりません: %s</div></div>' % html.escape(src)
    spec = json.load(open(path, encoding="utf-8"))
    errs = mv.validate(spec, os.path.dirname(os.path.abspath(path)))
    if errs:
        for e in errs:
            print("warn: 動画 %s: %s" % (src, e), file=sys.stderr)
        return '<div class="callout callout-warning"><div class="callout-body">動画の台本に誤りがあります（%s）。</div></div>' % html.escape(src)
    for w in mv.plan(spec):
        print("warn: 動画 %s: %s" % (src, w), file=sys.stderr)
    player = attrs.get("player") or spec.get("player") or "minimal"
    theme = attrs.get("theme") or spec.get("theme") or VIDEO_THEME.get(doc_theme, "daylight")
    if player not in mv.PLAYERS:
        player = "minimal"
    if theme not in mv.THEMES:
        theme = VIDEO_THEME.get(doc_theme, "daylight")
    cap = attrs.get("caption") or ""
    frag = mv.build_embed(spec, theme, player)
    return '<figure class="md2doc-video">%s%s</figure>' % (
        frag, '<figcaption style="color:var(--muted);font-size:13px;margin-top:6px">%s</figcaption>' % html.escape(cap) if cap else "")


def replace_videos(doc, base, doc_theme):
    doc = VIDEO_RE.sub(lambda m: video_fragment(video_attrs(m.group(1)), base, doc_theme), doc)
    return MOTION_COMMENT_RE.sub(lambda m: motion_figure(m.group(1), base, doc_theme), doc)


# ──────────────────────────────────────────────────────────────────────────
# 動く図（motion-video の部品を、プレイヤー無しで文書の図として置く）
#   ```motion
#   {"type": "bars", "items": [...], "figure": {"caption": "…", "loop": false, "width": "80%"}}
#   ```
#   または 1 行で <!-- motion: {"type": "flow", ...} -->。画面に入ると動き、完成した図で止まる。
#   描画部は文書に 1 度だけ入れる（add_motion_runtime）。
# ──────────────────────────────────────────────────────────────────────────
MOTION_COMMENT_RE = re.compile(r'<!--\s*motion:\s*(\{.*?\})\s*-->', re.S)
_MF = [None]


def _motion_figure_mod():
    if _MF[0] is None:
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "motion-video", "figure.py")
        if not os.path.isfile(path):
            _MF[0] = False
        else:
            spec = importlib.util.spec_from_file_location("motion_video_figure", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _MF[0] = mod
    return _MF[0] or None


def motion_figure(src, base, doc_theme):
    def warn(msg):
        print("warn: 動く図: %s" % msg, file=sys.stderr)
        return '<div class="callout callout-warning"><div class="callout-body">動く図を作れませんでした（%s）。</div></div>' % html.escape(msg)
    mf = _motion_figure_mod()
    if not mf:
        return warn("motion-video スキルが見つかりません")
    try:
        scene = json.loads(src)
    except ValueError as e:
        return warn("JSON の誤り: %s" % e)
    if not isinstance(scene, dict) or not scene.get("type"):
        return warn("type（motion-video の部品の名前）が必要です")
    opts = scene.pop("figure", None) or {}
    light, dark = mf.theme_pair(opts.get("theme") or VIDEO_THEME.get(doc_theme, "daylight"))
    frag, errs = mf.build_figure(scene, light, dark, opts, base or ".")
    if errs:
        return warn("; ".join(errs))
    return frag


def add_motion_runtime(doc):
    """動く図があれば、描画部と制御を </body> の前に 1 度だけ入れる（動画の埋め込みで描画部が入っていれば使い回す）。"""
    if 'class="mvfig"' not in doc or "window.MotionFigure" in doc:
        return doc
    mf = _motion_figure_mod()
    if not mf:
        return doc
    rt = mf.runtime(has_engine="window.MotionVideo = window.MotionVideo ||" in doc)
    i = doc.rfind("</body>")
    return doc[:i] + rt + doc[i:] if i >= 0 else doc + rt


# ── 生成前の質問（テーマ・出力モードなど）を ask-form の 1 画面にまとめる ──
# 質問の id は generate.py の引数名と同じ（theme → --theme、auto-figure → --auto-figure）。
LOCAL_IMG_RE = re.compile(r"!\[[^\]]*\]\(\s*(?!https?://|data:|//)[^)\s]+")


def ask_spec(inputs, recommend):
    """ask-form に渡す質問の定義を作る。recommend は md の内容に合うテーマのキー（先頭が既定）。"""
    def opts(*rows):
        return [{"value": v, "label": l, "desc": d} for v, l, d in rows]

    order = recommend + [k for k in THEMES if k not in recommend]
    themes = []
    for k in order:
        ch, fit = THEME_INFO.get(k, ("", ""))
        themes.append({"value": k, "label": THEMES[k]["label"], "desc": "%s。向く文書: %s" % (ch, fit),
                       "colors": [THEMES[k]["vars"]["--accent"]] + THEMES[k]["accents"][1:4],
                       "recommended": k in recommend})
    has_image = False
    for path in inputs:
        try:
            has_image = has_image or bool(LOCAL_IMG_RE.search(open(path, encoding="utf-8").read()))
        except OSError:
            pass
    many = len(inputs) > 1
    qs = [
        {"id": "theme", "label": "テーマ", "options": themes, "default": order[0],
         "help": "ライト/ダークは全テーマが両方持ち、読み手がヘッダーで切り替えられます。"},
        {"id": "mode", "label": "出力モード", "default": "site" if many else "single", "options": opts(
            ("single", "単一HTML", "1 ファイル完結。メール添付・USB 配布に最適。"),
            ("print", "印刷/PDF重視", "紙・PDF 配布を主目的に、改ページ・余白を最適化。"),
            ("site", "複数md→サイト化", "複数ファイルを束ね、一覧 index.html を作って相互リンク。"))},
        {"id": "toc", "label": "目次", "default": "sidebar", "options": opts(
            ("sidebar", "左サイドに目次", "本文の左に目次（開閉・検索・章ごとの折りたたみ）。"),
            ("menu", "ヘッダーメニュー", "上部の固定メニューのみ。本文は全幅。"),
            ("both", "両方", "ヘッダーメニュー＋左サイド目次。"),
            ("none", "目次なし", "どちらも出さない。"))},
        {"id": "layout", "label": "リストの見せ方（既定値）", "default": "plain",
         "help": "節ごとの指定が無い箇条書きに使う既定値です。節ごとの割り当ては、このあと案を出します。",
         "options": opts(
            ("plain", "箇条書き", "通常のリスト。"),
            ("cards", "カード", "項目をカードのグリッドに。一覧性・見栄え重視。"),
            ("timeline", "タイムライン", "番号付きの縦タイムライン。手順・工程・時系列向き。"),
            ("accordion", "アコーディオン", "折りたたみ。項目が多く詳細を隠したいとき。"),
            ("freeform", "完全フリーフォーム", "形式に縛られず、Claude が内容ごとに自由にデザイン（文書全体）。"))},
        {"id": "design", "label": "構築方法", "default": "deterministic",
         "showIf": {"layout": ["plain", "cards", "timeline", "accordion"]}, "options": opts(
            ("deterministic", "決定論的", "スクリプトが型どおりに変換。同じ入力なら同じ出力。"),
            ("ai", "AIがこのテイストで構築", "Claude が節ごとに内容を読んで部品を選び、作り込む。"))},
        {"id": "auto-figure", "label": "図解の自動補完", "default": "off", "options": opts(
            ("off", "しない", "本文そのまま。図は mermaid ブロックのみ。"),
            ("light", "控えめに補う", "最も効果的な 1〜2 個だけ図解。"),
            ("rich", "積極的に図解", "図にできる箇所は積極的に図解。"))},
    ]
    if has_image:
        qs.append({"id": "image-mode", "label": "画像の扱い", "default": "embed", "options": opts(
            ("embed", "埋め込み", "画像を HTML に埋め込み、1 ファイルで自己完結。"),
            ("link", "外部フォルダ参照", "HTML は軽いが、配布時は画像フォルダも一緒に運ぶ。"))})
    qs.append({"id": "motion", "label": "説明図の動き", "default": "off",
               "showIf": {"mode": ["single", "site"]}, "options": opts(
        ("off", "動かさない", "静止した図のみ。"),
        ("key", "要所だけ動かす", "流れ・手順など、動きで理解が進む図を 1〜2 個選んで動かす。"),
        ("rich", "図をすべて動かす", "すべての図が流れの向きに沿って順に現れる。"))})
    names = "・".join(os.path.basename(p) for p in inputs[:3]) + (" ほか" if len(inputs) > 3 else "")
    return {"title": "md-to-doc の設定", "intro": names, "submit": "この内容で生成", "questions": qs}


def run_ask(spec):
    """隣の ask-form スキルで質問の画面を出し、その結果（JSON 1 行）と終了コードをそのまま返す。"""
    here = os.path.abspath(__file__)
    for base in (os.path.dirname(here), os.path.dirname(os.path.realpath(here))):
        ask = os.path.join(base, os.pardir, "ask-form", "ask.py")
        if os.path.exists(ask):
            r = subprocess.run([sys.executable, ask, "-", "--width", "1080", "--height", "1000"], input=json.dumps(spec, ensure_ascii=False).encode("utf-8"))
            return r.returncode
    print(json.dumps({"status": "unavailable", "reason": "ask-form スキルが見つかりません"}, ensure_ascii=False))
    return 3


def main():
    ap = argparse.ArgumentParser(description="Markdown を視覚的なHTMLドキュメントに変換")
    ap.add_argument("inputs", nargs="*", help="入力 .md（複数可）")
    ap.add_argument("--finalize", metavar="OUT.html", default=None,
                    help="AI 構築の仕上げ: 本文の <!--MD2DOC-PART layout=…--> を部品に置き換え、mermaid を描く（--theme が要る）")
    ap.add_argument("--src", default=None, help="--finalize で、断片の中の画像の相対パスの基準にする元の .md")
    ap.add_argument("--theme", choices=list(THEMES.keys()), help="テーマ（一覧は --list-themes）")
    ap.add_argument("--list-themes", action="store_true", help="テーマの一覧（キー・名前・性格・向く文書）を出す")
    ap.add_argument("--ask", action="store_true",
                    help="生成前の質問を ask-form の 1 画面で聞き、回答の JSON を出す（HTML は作らない）")
    ap.add_argument("--ask-spec", action="store_true", help="--ask で出す質問の定義（JSON）だけを出す")
    ap.add_argument("--recommend", default="", metavar="キー,...",
                    help="--ask で先頭に並べる、md の内容に合うテーマ（先頭が既定。例: manual,formal,minimal）")
    ap.add_argument("--mode", default="single", choices=["single", "print", "site"])
    ap.add_argument("--outdir", default=None, help="出力先（既定: 入力と同じ場所）")
    ap.add_argument("--eyebrow", default=None, help="ヘッダー上部の小見出し")
    ap.add_argument("--auto-figure", default="off", choices=["off", "light", "rich"],
                    help="mermaid 以外の内容も、図解すべき箇所をClaudeが図にする（off/控えめ/積極的）")
    ap.add_argument("--toc", default="sidebar", choices=["sidebar", "menu", "both", "none"],
                    help="目次の出し方（左サイドのみ/ヘッダーメニューのみ/両方/なし）")
    ap.add_argument("--layout", default="plain",
                    choices=list(LIST_LAYOUTS) + ["freeform"],
                    help="本文の見せ方の【既定値】（箇条書き/カード/タイムライン/アコーディオン/完全フリーフォーム）。"
                         "セクション単位の指定が無い節にだけ適用される")
    ap.add_argument("--layout-map", default=None, metavar="節名=レイアウト,...",
                    help='セクション別レイアウト。例: --layout-map "導入手順=timeline,主な機能=cards"。'
                         "節名は見出しテキストか slug（空白・記号・大小は無視して突き合わせ）。"
                         "値は plain/cards/timeline/accordion。"
                         "優先順は md 内 <!-- layout: .. --> > --layout-map > --layout")
    ap.add_argument("--suggest-layouts", action="store_true",
                    help="HTML を作らず、節ごとのレイアウトの割り当て案（3f の材料）と --layout-map の文字列を出す")
    ap.add_argument("--design", default="deterministic", choices=["deterministic", "ai"],
                    help="deterministic=スクリプトが型変換／ai=選んだ形式のテイストでClaudeが作り込む")
    ap.add_argument("--default-mode", default=None, choices=COLOR_MODES,
                    help="初回表示の既定モード（未指定ならテーマの既定。darktech=dark, 他=system）")
    ap.add_argument("--motion", default="off", choices=MOTION_LEVELS,
                    help="説明図の動き（off=動かさない／key=Claude が選んだ要所の図だけ／rich=すべての図）。"
                         "スクロールで見えたとき 1 回再生。reduced-motion・印刷では静止")
    ap.add_argument("--motion-tempo", default="normal", choices=MOTION_TEMPOS,
                    help="動きの速さ（slow / normal / fast）。図ごとには data-tempo で上書きできる")
    ap.add_argument("--motion-style", default="gentle", choices=MOTION_STYLES,
                    help="動きの性格（gentle=穏やか／dynamic=弾む・寄る／playful=跳ねる・落ちる／cinematic=ぼけから・ゆっくり／tech=拭き取り・でたらめな文字から／"
                         "retro=コマ送り・打字・走査線／elegant=漂う・1 文字ずつ・ゆったり／news=勢いよく滑る・拭き取り・速い）。"
                         "図ごとには data-motion-style で上書き")
    ap.add_argument("--motion-blocks", default="auto", choices=["auto", "on", "off"],
                    help="カード・数字・年表・チェックリスト・表などの部品も、見えたときに現れる（auto=--motion rich のときだけ）")
    ap.add_argument("--image-mode", default="embed", choices=["embed", "link"],
                    help="mdのローカル画像リンクの扱い（embed=data URIで埋め込み／link=外部フォルダ参照のまま）")
    args = ap.parse_args()
    MOTION_OPTS["style"] = args.motion_style
    MOTION_OPTS["blocks"] = args.motion_blocks

    if args.list_themes:
        print("| キー | 名前 | 性格 | 向く文書 |")
        print("|---|---|---|---|")
        for k, t in THEMES.items():
            ch, fit = THEME_INFO.get(k, ("", ""))
            print("| `%s` | %s | %s | %s |" % (k, t["label"], ch, fit))
        return
    if args.ask or args.ask_spec:
        rec = [k.strip() for k in args.recommend.split(",") if k.strip()] or ["corporate"]
        bad = [k for k in rec if k not in THEMES]
        if bad:
            ap.error("--recommend の %s はテーマにありません（一覧は --list-themes）" % "/".join(bad))
        spec = ask_spec(args.inputs, rec)
        if args.ask_spec:
            print(json.dumps(spec, ensure_ascii=False, indent=1))
            return
        sys.exit(run_ask(spec))
    if not args.theme:
        ap.error("--theme を指定してください（一覧は --list-themes）")
    default_mode = default_mode_of(args.theme, args.default_mode)
    layout_map = parse_layout_map(args.layout_map)
    if args.finalize:
        n, pending, bad, left = finalize_html(args.finalize, args.theme, args.src)
        print("OK : %s（部品 %d 個を置き換え）" % (args.finalize, n))
        for b in bad:
            print("warn: MD2DOC-PART の layout=%s は使えません（plain で描きました）。%s のいずれか。"
                  % (b, "/".join(DET_LAYOUTS)), file=sys.stderr)
        if left:
            print("warn: <!--MD2DOC_CONTENT--> がまだ残っています。本文を書いてから仕上げてください。", file=sys.stderr)
        if pending:
            print("\n===== MERMAID_MANUAL_RENDER_REQUIRED =====")
            print("mmdc が無いため %d 個の図が未レンダリングです。figkit の flow / sequence に写して" % len(pending))
            print('"replace": "<id>" で差し込むか、テーマ配色の <svg> を手描きして figure ごと置き換えてください。')
            print("配色パレット: " + json.dumps(theme_palette(args.theme), ensure_ascii=False))
            for t in pending:
                print("\n--- figure id=%s  in  %s ---" % (t["id"], t["out"]))
                print(t["source"])
            print("===== /MERMAID_MANUAL_RENDER_REQUIRED =====")
        return
    if not args.inputs:
        ap.error("入力 .md を指定してください（--finalize のときは不要）")
    if args.suggest_layouts:
        for path in args.inputs:
            raw = open(path, encoding="utf-8").read()
            _, body = split_frontmatter(raw)
            sug = suggest_layouts(body.replace("\r\n", "\n").split("\n"))
            print("--- %s" % path)
            if not sug:
                print("  （割り当ての候補なし。既定値のまま）")
                continue
            print("  | セクション | 割り当て | 理由 |")
            print("  |---|---|---|")
            for name, lay, why in sug:
                print("  | %s | `%s` | %s |" % (name, lay, why))
            print('  --layout-map "%s"' % ",".join("%s=%s" % (nm, ly) for nm, ly, _ in sug))
        return
    if args.motion != "off" and args.mode == "print":
        print("warn: --mode print では図を動かしません（--motion %s を off として扱います）" % args.motion,
              file=sys.stderr)
        args.motion = "off"

    produced = []
    todo = []  # 手描きが必要な図 [{out, id, source}]
    for path in args.inputs:
        if not os.path.isfile(path):
            print("skip (not found):", path, file=sys.stderr); continue
        outdir = args.outdir or os.path.dirname(os.path.abspath(path))
        out_html, title, headings, ok, pending = convert_file(
            path, args.theme, args.eyebrow, args.auto_figure, args.toc, args.layout, args.design,
            default_mode, args.image_mode, outdir, layout_map, args.motion,
            args.motion_tempo)
        os.makedirs(outdir, exist_ok=True)
        outname = os.path.splitext(os.path.basename(path))[0] + ".html"
        outpath = os.path.join(outdir, outname)
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(out_html)
        entry = {"src": path, "out": outpath, "title": title,
                 "h2": [h["slug"] for h in headings if h["level"] == 2],
                 "figs": re.findall(r'<figure class="mermaid-fig[^"]*" id="([^"]+)"', out_html)}
        if args.layout == "freeform" or args.design == "ai":
            entry["hlist"] = headings
            try:
                entry["md"] = open(path, encoding="utf-8").read()
            except Exception:
                entry["md"] = ""
        produced.append(entry)
        for p in pending:
            todo.append({"out": outpath, "id": p["id"], "source": p["source"]})
        print("OK :", outpath)

    unused = sorted(set(layout_map) - _LAYOUT_MAP_HIT)
    if unused:
        print("warn: --layout-map の節名が見つかりませんでした（無視）: %s" % ", ".join(unused),
              file=sys.stderr)
        print("      見出しテキストか slug と一致させてください（空白・記号・大小は無視されます）。",
              file=sys.stderr)

    if args.mode == "site" and produced:
        outdir = args.outdir or os.path.dirname(os.path.abspath(produced[0]["src"]))
        cards = "".join(
            '<a class="idx-card" href="%s"><div class="idx-ttl">%s</div>'
            '<div class="idx-sub">%s</div></a>'
            % (html.escape(os.path.basename(p["out"]), quote=True),
               html.escape(p["title"]), html.escape(os.path.basename(p["src"])))
            for p in produced)
        index = INDEX_PAGE.replace("__THEMECSS__", theme_css(args.theme))\
                          .replace("__STATIC_CSS__", STATIC_CSS + theme_extra_css(args.theme))\
                          .replace("__MODE_SWITCH__", MODE_SWITCH_HTML)\
                          .replace("__MODE_BOOT_JS__", MODE_BOOT_JS)\
                          .replace("__MODE_SCRIPT_JS__", MODE_SCRIPT_JS)\
                          .replace("__CARDS__", cards)\
                          .replace("__COUNT__", str(len(produced)))\
                          .replace("__MODE_KEY__", MODE_STORAGE_KEY)\
                          .replace("__DEFAULT_MODE__", default_mode)
        ipath = os.path.join(outdir, "index.html")
        with open(ipath, "w", encoding="utf-8") as f:
            f.write(index)
        print("OK :", ipath, "(index)")

    # AI設計（freeform もしくは design=ai）: Claude が本文を著述するための情報を出力
    if (args.layout == "freeform" or args.design == "ai") and produced:
        pal = theme_palette(args.theme)
        TASTE = {
            "cards": "カード（.card-grid>.doc-card）を主モチーフに、アイコン・タグ・色循環で内容を作り込む",
            "timeline": "タイムライン（.timeline>.tl-item）を主モチーフに、番号/アイコンとチップで工程・時系列を表現する",
            "accordion": "アコーディオン（.accordion>.acc-item）を主モチーフに、要点を見せ詳細を畳む",
            "plain": "落ち着いた箇条書きを主体に、要所だけカードやコールアウトで強調する",
            "freeform": "形式に縛られず、内容に最適な部品を自由に組み合わせる（カード/数値/タイムライン/比較/図の混在可）",
        }
        taste = TASTE.get(args.layout, TASTE["freeform"])
        print("\n===== AI_DESIGN_REQUIRED =====")
        print("各出力HTMLの <main class=\"content\"> 内にある <!--MD2DOC_CONTENT--> を、")
        print("元Markdownを解釈して『内容に最適化したデザインのHTML』に Edit で置き換えてください。")
        print("決定論的な型変換ではなく、手作りサンプル相当の作り込みを行う。")
        print("\n[レイアウトは節単位で決める] レイアウトは文書全体で画一に決まるものではない。")
        print("  **セクション（h2/h3）ごとに中身を読んで部品を選ぶ**。目安:")
        print("    番号付き手順・工程・時系列        -> .timeline>.tl-item")
        print("    並列に比較できる機能・選択肢・種別 -> .card-grid>.doc-card")
        print("    項目が多い / 詳細を畳みたい / Q&A -> .accordion>.acc-item")
        print("    散文的な補足・注意・前提          -> 素の箇条書き＋段落、要所だけ .callout")
        print("    件数・割合・所要時間などの指標    -> .stat-row>.stat")
        print("    2項の対比・Before/After           -> .split、比較軸が3つ以上なら .tablewrap>table")
        print("  同じ部品が3節以上続いたら、内容を見直して別の部品に振り分ける（単調さを避ける）。")
        print("  1つの節の中でも、前半は説明の箇条書き＋後半だけカード、のような混在は可。")
        print("[基調テイスト=%s] %s" % (args.layout, taste))
        print("  ※これは『迷ったときの寄せ先』であって、全節に適用する指定ではない。")
        for ent in produced:
            dirs = extract_layout_directives((ent.get("md") or "").replace("\r\n", "\n").split("\n"))
            if dirs:
                print("[節指定あり: %s] %s" % (os.path.basename(ent["src"]),
                      ", ".join("%s=%s" % (sec, lay) for sec, lay in dirs)))
                print("  ↑ md 側で明示されている節は、この指定を優先すること。")
        print("\n[定型の部品はスクリプトに任せる] 本文の中に、Markdown の断片とレイアウトを書く目印を置ける:")
        print("  <!--MD2DOC-PART layout=tabs-->")
        print("  - macOS")
        print("    ```bash … ```")
        print("  <!--/MD2DOC-PART-->")
        print("  書き終えたら次を 1 回実行すると、断片が決定論的な部品（リストのレイアウト・表の強化・コード・mermaid）に置き換わる:")
        print("  python3 %s --finalize <out.html> --theme %s [--src <input.md>]"
              % (os.path.abspath(__file__), args.theme))
        print("  layout は %s。見出し（h2/h3）は断片に入れず、Claude が書く。" % " / ".join(DET_LAYOUTS))
        print("  定型の形（タブ・チェックリスト・用語・数値タイル・タグ・ツリー・対比・説明とコード・表・mermaid）は")
        print("  手で書かずにこの目印を使い、手作りは構成・強調・独自の部品だけにする（生成コストと書き漏れを減らす）。")
        print("  手で書いた <table> も、8 行以上ならページ側で並べ替え・絞り込み・数値の棒が付く（止めるなら data-table=\"plain\"）。")
        for ent in produced:
            sug = suggest_layouts((ent.get("md") or "").replace("\r\n", "\n").split("\n"))
            if sug:
                print("[割り当て案: %s]（参考。崩してよいが、定型に当たる節は MD2DOC-PART を使う）" % os.path.basename(ent["src"]))
                for name, lay, why in sug:
                    print("  %s → %s（%s）" % (name, lay, why))
        print("\n[配色] " + json.dumps(pal, ensure_ascii=False))
        print("[使える部品クラス] hero外の本文で利用可:")
        print("  見出し: <h2 id=SLUG class=\"hl\">..</h2> / <h3 id=SLUG class=\"hl\">..</h3>（下記SLUG必須）")
        print("  リード文:.lead / カード:.card-grid>.doc-card(.doc-card-top>.doc-card-ic+.doc-card-h,.doc-card-tags>span,.doc-card-b)")
        print("  特徴グリッド:.feature-grid / 数値:.stat-row>.stat(.big,.cap) / チップ:.chips>.chip / バッジ:.badge")
        print("  タイムライン:.timeline>.tl-item(.tl-dot,.tl-body>.tl-h) / 折りたたみ:.accordion>.acc-item>summary")
        print("  コールアウト:.callout.callout-note(.callout-head,.callout-body) / 表:.tablewrap>table / 2分割:.split")
        print("  タブ:.tabs[data-tabs]>.tab-list[role=tablist]>button[role=tab]#ID-tN + section.tab-panel#ID-pN>.tab-print-h")
        print("  チェックリスト:.checklist[data-checklist=KEY]>.ck-head(.ck-bar>i,.ck-count,button.ck-reset)+ul.ck-list>li>label>input[type=checkbox]+span.ck-text")
        print("  用語:.defs-wrap>dl.defs>.def>dt+dd（10 件以上なら先頭に input.defs-filter）/ 対比:.pc-grid[style=--cols:2]>.pc-col.pc-pro|.pc-con|.pc-neutral>.pc-h+.pc-b")
        print("  ツリー:.tree>ul>li.tree-dir>details[open]>summary>.tree-name+.tree-note / li.tree-file>.tree-row>.tree-name")
        print("  説明とコード:.walk>.walk-row>.walk-text+.walk-code / 要点の箱:section.tldr / 大きめのタグ:.chips.chips-lg>.chip")
        print("  強化した表:.tablewrap.tools[data-table-tools]（数値の列は th.num / td.num[data-v]>.nbar[style=--w:NN（0〜100 の数）]+.nv）")
        print("  ※各要素に style=\"--ca:var(--a0)\" のように付けると、その部品の配色を accents から個別指定できる。")
        print("  ※図は自己完結の <figure class=\"mermaid-fig\"><svg ...></figure> で（外部依存なし・viewBox必須）。")
        print("  ※【重要】色は必ず CSS 変数（var(--accent) / var(--a1) 等）で指定する。SVG の fill/stroke も同様。")
        print("     hex を直書きするとヘッダーの ライト/ダーク 切替に追従せず、ダークで判読不能になる。")
        print("     アクセント色の上に載る文字は var(--on-accent) を使う。")
        if args.image_mode == "link":
            print("  ※【画像=外部フォルダ参照(link)】md内のローカル画像 ![](path) は data URI に埋め込まず、")
            print("     出力HTMLからの相対パスで <img class=\"md-img\" src=\"...\"> として参照すること。")
        else:
            print("  ※【画像=埋め込み(embed)】md内のローカル画像 ![](path) は data URI で埋め込み、自己完結にすること。")
        for p in produced:
            print("\n--- 著述対象: %s" % p["out"])
            print("  必須見出し（この slug を id に使う / nav・目次と一致させる）:")
            for h in p.get("hlist", []):
                print("    h%d  id=%s  «%s»" % (h["level"], h["slug"], h["text"]))
            print("  元Markdown:")
            print(p.get("md", ""))
        print("===== /AI_DESIGN_REQUIRED =====")

    # auto-figure 有効: Claude が図解を補うための情報を出力
    if args.auto_figure != "off" and produced:
        print("\n===== AUTO_FIGURE_ENABLED (level=%s) =====" % args.auto_figure)
        print("各セクション末尾に空の差し込みスロット")
        print('  <div class="auto-fig-slot" data-section="SLUG"></div>')
        print("を置きました。元のMarkdownを読み、図解した方が分かりやすい内容")
        print("（番号付き手順→フロー図 / 比較→対比図・棒 / 階層→ツリー / 循環→サイクル 等）が")
        print("あるセクションについて、対応スロットの中身をテーマ配色の自己完結 <svg> 図に Edit で置き換えてください。")
        print("不要なセクションのスロットは空のまま（自動で非表示）でよい。")
        print("【重要】svg の色は必ず CSS 変数（fill=\"var(--accent-soft)\" 等）で指定する。")
        print("        hex 直書きはヘッダーの ライト/ダーク 切替に追従しない。")
        if args.auto_figure == "light":
            print("level=light: 各ドキュメントで最も効果的な1〜2個に絞る。")
        else:
            print("level=rich: 図解できる箇所は積極的に図にする。")
        print("【推奨】図の多くは figkit で作れる（SVG を手で描かない。JSON の仕様→テーマ配色の図、slot に直接差し込む）:")
        print("  python3 %s --list  /  python3 %s spec.json --insert <out.html>"
              % ((os.path.join(os.path.dirname(os.path.abspath(__file__)), "figkit.py"),) * 2))
        print("  figkit に無い形の図だけ、下の配色で手描きする。")
        print("配色パレット: " + json.dumps(theme_palette(args.theme), ensure_ascii=False))
        for p in produced:
            print("--- %s : sections=%s" % (p["out"], ",".join(p["h2"]) or "(なし)"))
        print("===== /AUTO_FIGURE_ENABLED =====")

    # mmdc で描けなかった図がある場合: Claude が手描きするための情報を出力
    if todo:
        sidecar = os.path.join(args.outdir or os.path.dirname(os.path.abspath(produced[0]["src"])),
                               ".md2doc-mermaid-todo.json")
        payload = {"theme": args.theme, "palette": theme_palette(args.theme), "diagrams": todo}
        with open(sidecar, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("\n===== MERMAID_MANUAL_RENDER_REQUIRED =====")
        print("mmdc が無いため %d 個の図が未レンダリングです。" % len(todo))
        print("Claude は以下の各図を『テーマ配色の <svg>』として描き、出力HTML内の")
        print("対応する <figure id=...> 全体を Edit で置き換えてください。")
        print("【重要】色は必ず CSS 変数で指定する（fill=\"var(--accent-soft)\" stroke=\"var(--accent)\"")
        print("        text の fill=\"var(--ink)\"）。1枚の svg がライト/ダーク両方に自動追従する。")
        print("配色パレット: " + json.dumps(theme_palette(args.theme), ensure_ascii=False))
        print("TODO一覧(JSON): " + sidecar)
        for t in todo:
            print("\n--- figure id=%s  in  %s ---" % (t["id"], t["out"]))
            print(t["source"])
        print("===== /MERMAID_MANUAL_RENDER_REQUIRED =====")

    # motion 有効: Claude が図に動きの注釈を付けるための情報を出力
    if args.motion != "off" and produced:
        ai = args.layout == "freeform" or args.design == "ai"
        kit = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figkit.py")
        print("\n===== MOTION_ENABLED (level=%s, tempo=%s) =====" % (args.motion, args.motion_tempo))
        print("説明図を動かす実行部を埋め込みました。動かし方は実行部が決める（決定論的）。")
        print("Claude が決めるのは『どの図を動かすか』と『(任意の)注釈』だけ。色・座標・style は変えない。")
        print("再生: 図が画面に入ったとき 1 回（data-trigger で変更可）。reduced-motion・印刷・JS 無しでは静止した完成図。")
        if args.motion == "key":
            print("[level=key] 動くのは data-motion を付けた図だけ。各文書で動きが理解を足す図を 1〜2 個選ぶ（0 個でもよい）。")
            print("  向く: 流れ・手順・状態遷移・段階的に組み上がる構成・数量の変化。向かない: 静的な一覧・単純な階層。")
        else:
            print("[level=rich] すべての図が動く（注釈なしの図は位置順に自動で現れる）。邪魔な図は data-motion=\"none\"。")
        print("[図を作るなら figkit を使う] SVG を手で描かず、JSON の仕様から注釈入りの図を作れる（生成コストが低く、同じ仕様→同じ図）:")
        print("  python3 %s --list                       # 図の種類と仕様" % kit)
        print("  python3 %s spec.json --insert <out.html>  # slot / replace / placeholder に差し込む" % kit)
        print("  種類: flow / steps / cycle / bars / metrics / compare / hub / layers / sequence / line / donut / gantt / terminal / toggle /")
        print("        chat / funnel / venn / matrix / timeline / org / waffle / bullet / slope / dumbbell / sparks / radial / sankey / heatmap。")
        print("  figkit の図は段・現れ方が組み込み済み。key で動かす図は仕様に \"motion\": true を足すだけ。")
        print("[動きの性格] --motion-style=%s（図ごとに data-motion-style で変える: gentle|dynamic|playful|cinematic|tech|retro|elegant|news）。" % MOTION_OPTS["style"]
              + " 注釈の無い要素の現れ方・図全体の入り方・段の間隔が性格で決まる")
        print("[部品の登場] --motion-blocks=%s（カード・数字の数え上げ・年表・チェックリスト・表の行と棒）" % MOTION_OPTS["blocks"])
        print("[図の単位] <figure data-motion=\"auto|steps|none\" data-tempo=\"slow|normal|fast\" data-trigger=\"view|click|loop|scroll\"")
        print("           data-motion-dir=\"auto|x|y|reverse-x|reverse-y|radial|in|diagonal|spiral|random\" data-motion-style=\"…\"")
        print("           data-intro=\"punch|zoom-out|drop|tilt|glitch|iris|crt|wipe|unfold|fade|rise|none\"（図全体の入り方）>")
        print("[要素の注釈]（svg 内の要素か <g>。すべて任意）")
        print("  data-step=\"N\"  現れる順番（同じ N は同時）")
        print("  data-effect=  現れ方: draw rise fade slide pop grow wipe / zoom flip flip-y spin roll swing drop bounce elastic jelly")
        print("                slide-left slide-right slide-up slide-down blur iris blinds glitch flicker outline（輪郭を描いてから塗る）")
        print("                mask wipe-up wipe-down wipe-left spring stamp unfold twist skew pop-up zoom-blur rise-rotate tilt-in float-in cascade（<g> の子が順に落ちる）")
        print("                diamond corner rubber slide-bounce swirl shake-in pixel hinge swoosh wobble lift pendulum")
        print("                type letters scramble（文字） none")
        print("  data-attn=\"shake|wiggle|jump|pop|tada|heartbeat|flash|glow|ring|pulse\"  現れた後に 1 回強調（登場がすべて終わってから段の順）")
        print("  data-burst[=\"粒の数\"]  現れるときに粒が弾ける（達成・結果の強調に 1 図 1 か所）")
        print("  繰り返し: data-float[=px] 漂う  data-sway[=度] 揺れる  data-blink 瞬く  data-heartbeat 鼓動  data-glow 光る  data-march 輪郭の点線が回る")
        print("           data-wave（<g> の子が波打つ）  data-orbit=\"半径\" 小さく回る  data-ripple 波紋  data-stream=\"数\" 線の上を印が流れ続ける")
        print("           data-breathe 息づく  data-shine ときどき光る  data-jiggle ときどき震える  data-hop[=px] 弾む  data-tick[=刻み] 時計の針のように刻んで回る（data-tick-origin）")
        print("           data-redraw 線が消えては描かれる  data-hue 色相が巡る")
        print("  data-depth=\"-2〜2\"  スクロールで奥行きのようにずれる（背景の飾りに）")
        print("  data-grow=\"up|down|left|right\"  grow の向き   data-stagger[=\"ms\"]  <g> の子を 1 つずつ")
        print("  data-travel=\"ラベル\"  線の上を印が移動（受け渡し）   data-count=\"0\"  文字の数値を 0 から数え上げ")
        print("  data-flow  線に沿って破線が流れ続ける   data-pulse  ゆっくり明滅   data-spin[=\"ccw\"]  回り続ける（飾りの輪に）")
        print("  data-focus=\"N\"  現れた後、N の順に 1 つずつ強調し、他の data-focus 要素を薄くする（手順の解説）")
        print("  ※ mermaid（mmdc 出力）の svg は内部を書き換えず、figure に data-motion 等を足すだけにする。")
        for p in produced:
            figs = p.get("figs") or []
            print("--- %s" % p["out"])
            print("  mermaid の図: %s" % (", ".join(figs) if figs else "(なし)"))
            if args.auto_figure != "off":
                print("  auto-figure のスロット: %s（figkit の slot に指定できる）" % (",".join(p["h2"]) or "-"))
            if ai:
                print("  AI 構築: 本文に <!--FIGKIT:名前--> を置き、figkit の placeholder で差し込める")
            if not figs and args.auto_figure == "off" and not ai:
                print("  ※ この文書には図がありません（動く対象なし）。")
        print("===== /MOTION_ENABLED =====")


INDEX_PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ドキュメント一覧</title><style>
__THEMECSS__
__STATIC_CSS__
.idx-wrap{max-width:var(--maxw);margin:0 auto;padding:calc(var(--nav-h) + 40px) 24px 80px}
.idx-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px;margin-top:24px}
.idx-card{display:block;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:22px;text-decoration:none;color:var(--ink);box-shadow:var(--shadow);transition:.18s}
.idx-card:hover{transform:translateY(-3px);border-color:var(--accent)}
.idx-ttl{font-family:var(--font-head);font-weight:800;font-size:17px;color:var(--accent-2)}
.idx-sub{color:var(--muted);font-size:12px;margin-top:8px}
</style><script>__MODE_BOOT_JS__</script></head><body id="top" class="toc-none">
<nav class="topbar"><div class="topbar-inner"><a href="#top" class="brand">📚 ドキュメント一覧</a>
<div class="topbar-tools">__MODE_SWITCH__</div></div></nav>
<div class="idx-wrap"><h1 style="font-family:var(--font-head);font-size:30px">ドキュメント一覧</h1>
<p style="color:var(--muted)">__COUNT__ 件のドキュメント</p>
<div class="idx-grid">__CARDS__</div></div>
<script>__MODE_SCRIPT_JS__</script></body></html>
"""


if __name__ == "__main__":
    main()
