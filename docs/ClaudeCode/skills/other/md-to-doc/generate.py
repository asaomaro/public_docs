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
import sys, os, re, html, json, argparse, subprocess, tempfile, shutil, datetime, base64

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
            if lang == "mermaid":
                key = "@@MERMAID_%d@@" % len(mermaid_store)
                mermaid_store.append(code)
                out.append(key)
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
            lab = (html.escape(icon) + " " if icon else "") + inline(text)
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
                        % (tone, ca, (html.escape(icon) + " ") if icon else "", inline(text), body_html(it)))
        return '<div class="pc-grid" style="--cols:%d">%s</div>' % (min(len(items), 3), "".join(cols))
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


def render_table(header, rows, mode="auto"):
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


def extract_decorations(text):
    """項目テキストから 先頭絵文字(icon) と 末尾 {タグ} 群 を取り出す。"""
    icon = ""
    m = _EMOJI.match(text)
    if m:
        icon = m.group(1); text = text[m.end():]
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
LIST_LAYOUTS = ("plain", "cards", "timeline", "accordion",
                "tabs", "checklist", "defs", "stats", "chips", "tree", "proscons")
SECTION_LAYOUTS = ("walkthrough", "summary")
DET_LAYOUTS = LIST_LAYOUTS + SECTION_LAYOUTS
FLAT_LAYOUTS = ("cards", "timeline", "accordion", "chips", "tree")     # 箇条書きの行だけで組む
RICH_LAYOUTS = ("tabs", "checklist", "defs", "stats", "proscons")     # 項目の中のコード・段落も使う
TABLE_DIRECTIVE_RE = re.compile(r"^\s*<!--\s*table\s*[:=]\s*(plain|tools|auto)\s*-->\s*$", re.I)
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
                            (html.escape(g["icon"]) + " ") if g["icon"] else "", g["label"]))
        return '<div class="chips chips-lg">%s</div>' % "".join(chips)

    def tags_html(g):
        if not g["tags"]:
            return ""
        return '<div class="doc-card-tags">%s</div>' % "".join(
            "<span>%s</span>" % html.escape(t) for t in g["tags"])

    if layout == "cards":
        cards = []
        for idx, g in enumerate(groups):
            ic = '<span class="doc-card-ic">%s</span>' % html.escape(g["icon"]) if g["icon"] else ""
            body = '<div class="doc-card-b">%s</div>' % g["children"] if g["children"] else ""
            cards.append(
                '<div class="doc-card" style="--ca:%s">'
                '<div class="doc-card-top">%s<div class="doc-card-h">%s</div></div>%s%s</div>'
                % (_ca(idx), ic, g["label"], tags_html(g), body))
        return '<div class="card-grid">%s</div>' % "".join(cards)

    if layout == "timeline":
        nodes = []
        for idx, g in enumerate(groups):
            badge = html.escape(g["icon"]) if g["icon"] else str(idx + 1)
            nodes.append(
                '<div class="tl-item" style="--ca:%s"><div class="tl-dot">%s</div>'
                '<div class="tl-body"><div class="tl-h">%s</div>%s%s</div></div>'
                % (_ca(idx), badge, g["label"], tags_html(g), g["children"]))
        return '<div class="timeline">%s</div>' % "".join(nodes)

    if layout == "accordion":
        rows = []
        for idx, g in enumerate(groups):
            ic = (html.escape(g["icon"]) + " ") if g["icon"] else ""
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
  .topbar,.progress,.backtop,.copy-btn,.hamburger,.mode-switch,.anchor{display:none!important}
  .toc{display:none}.layout{grid-template-columns:1fr;display:block}
  [id]{scroll-margin-top:0}body{background:#fff}
  .hero{padding:0 0 18px;background:none!important;color:#000!important;border-bottom:2px solid #000}
  .hero .eyebrow,.hero .tags span{background:#eee!important;color:#333!important}
  .content,.layout{padding:0}.content h2.hl{margin-top:24px}
  .callout,.mermaid-fig,.codeblock,table,figure,h2,h3,li{break-inside:avoid}
  a{color:#000;border:none}.codeblock pre{background:#f4f4f4;color:#111;border:1px solid #ccc}
  .copy-btn{display:none}
}
"""

# 表示モード切替のUIと、そのブート/操作スクリプト（INDEX_PAGE と共用）
MODE_SWITCH_HTML = (
    '<div class="mode-switch" role="group" aria-label="表示モード">'
    '<button type="button" data-mode="light" title="ライトモード" aria-label="ライトモード">☀</button>'
    '<button type="button" data-mode="dark" title="ダークモード" aria-label="ダークモード">☾</button>'
    '<button type="button" data-mode="system" title="システム設定に合わせる"'
    ' aria-label="システム設定に合わせる">◐</button>'
    '</div>'
)

# <head> 内で先に data-theme を確定させ、ダーク指定時の白フラッシュを防ぐ
MODE_BOOT_JS = """(function(){try{
var m=localStorage.getItem('__MODE_KEY__')||'__DEFAULT_MODE__';
if(m==='light'||m==='dark')document.documentElement.setAttribute('data-theme',m);
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
})();"""

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
        "__STATIC_CSS__": STATIC_CSS, "__BRAND__": html.escape(brand),
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
"""

MOTION_JS = r"""(function(){
  var LEVEL='__MOTION_LEVEL__', TEMPO_DEF='__MOTION_TEMPO__';
  var mq=window.matchMedia?matchMedia('(prefers-reduced-motion: reduce)'):null;
  var REDUCE=!!(mq&&mq.matches), CAN=!!Element.prototype.animate&&('IntersectionObserver' in window);
  var NS='http://www.w3.org/2000/svg';
  var GEOM={rect:1,circle:1,ellipse:1,polygon:1,polyline:1,line:1,path:1,text:1,image:1,use:1,foreignObject:1};
  var SKIP={defs:1,marker:1,clipPath:1,mask:1,pattern:1,symbol:1,linearGradient:1,radialGradient:1,filter:1,style:1,title:1,desc:1,metadata:1};
  var ATOMIC=['data-effect','data-stagger','data-travel','data-count','data-focus','data-spin','data-pulse','data-flow'];
  var TEMPOS={slow:1.45,normal:1,fast:.7};
  var BASE={draw:760,rise:520,travel:1400,count:1100,type:30,stagger:130,gapSteps:450,gapAuto:380,autoTotal:2600,hold:1500,
            flow:900,pulse:1800,spin:24000,loopRest:2200,zoomMove:900,zoomHold:1500,toggle:3400,token:900};
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
    leaves.forEach(function(l){
      var x=l.r.left+l.r.width/2, y=l.r.top+l.r.height/2;
      l.k= dir==='x'?x : dir==='reverse-x'?-x : dir==='reverse-y'?-y : dir==='radial'?Math.hypot(x-cx,y-cy) : y;
    });
    var lo=Infinity,hi=-Infinity; leaves.forEach(function(l){lo=Math.min(lo,l.k);hi=Math.max(hi,l.k);});
    var n=Math.max(3,Math.min(10,Math.round(leaves.length/3))), band=Math.max(1,(hi-lo)/n);
    return {units:leaves.map(function(l){return {el:l.el,step:Math.min(n-1,Math.floor((l.k-lo)/band))};}),
            gap:Math.min(BASE.gapAuto,BASE.autoTotal/n)*T};
  }
  function effectOf(x){
    var e=x.getAttribute('data-effect'); if(e) return e;
    if(tag(x)==='g') return x.querySelector('path,line,polyline')&&[].every.call(x.querySelectorAll('*'),function(y){return !GEOM[tag(y)]||strokeOnly(y);})?'draw':'rise';
    return strokeOnly(x)?'draw':'rise';
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
      each(x.children,function(k){ var tk=tag(k); if(GEOM[tk]||tk==='g'||tk==='a') build(st,k,effectOf(k),delay); });
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
    var o=getComputedStyle(x).opacity||'1', k0={opacity:0}, k1={opacity:o}, dur=BASE.rise*T, back;
    switch(effect){
      case 'none': return;
      case 'type': type(st,x,delay); return;
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
    var a=x.animate([k0,k1],{duration:dur,delay:delay,easing:EASE,fill:'backwards'});
    track(st,a,delay+dur);
    if(back) a.finished.then(back,function(){});
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
    var start=delay+(effectOf(x)==='draw'?BASE.draw*st.T*0.9:0);
    driven(st,g,BASE.travel*st.T,start,function(k){
      if(k>=1||k<=0){ g.setAttribute('opacity','0'); return; }
      var e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2, pt=p.getPointAtLength(L*e);
      g.setAttribute('transform','translate('+pt.x+','+pt.y+')');
      g.setAttribute('opacity', k<.08?String(k/.08):k>.92?String((1-k)/.08):'1');
    });
  }
  function noteAnims(st,svg,units,gap){
    notes(svg).forEach(function(g){
      var target=null; each(svg.querySelectorAll('[data-note]'),function(t){ if(t.__moNote===g) target=t; });
      if(!target) return;
      var u=null; units.forEach(function(v){ if(v.el===target||v.el.contains(target)) u=v; });
      if(!u) return;                                      // 動かない要素の注記は最初から表示
      var d=u.step*gap+BASE.rise*st.T*0.8;
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
    if(!st.inView) st.loops.forEach(function(a){a.pause();});
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
    st.anims=[]; st.loops=[]; st.restores=[]; st.drivers=[]; st.svgs=[]; st.end=0;
  }
  function arm(st){
    reset(st);
    st.T=tempoOf(st.c);
    try{
      outerSvgs(st.c).filter(shown).forEach(function(svg){
        notes(svg);
        var pl=plan(st,svg);
        pl.units.forEach(function(u){ build(st,u.el,effectOf(u.el),u.step*pl.gap); });
        noteAnims(st,svg,pl.units,pl.gap);
        st.svgs.push(svg);
      });
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
    });
  },{threshold:0.3});
  containers().forEach(function(c){
    var st={c:c,anims:[],loops:[],restores:[],drivers:[],svgs:[],end:0,T:1,gen:0,played:false,inView:false,pending:false,
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


def motion_html(level, tempo="normal"):
    # off でも埋め込む: 切り替え・経路・関連の強調・注記は動きの設定と無関係に働く。
    # off のときは、data-motion を明示した図以外は登場の動きをしない。
    return "<style>%s</style>\n<script>%s</script>" % (
        MOTION_CSS, MOTION_JS.replace("__MOTION_LEVEL__", level).replace("__MOTION_TEMPO__", tempo))



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

def main():
    ap = argparse.ArgumentParser(description="Markdown を視覚的なHTMLドキュメントに変換")
    ap.add_argument("inputs", nargs="*", help="入力 .md（複数可）")
    ap.add_argument("--finalize", metavar="OUT.html", default=None,
                    help="AI 構築の仕上げ: 本文の <!--MD2DOC-PART layout=…--> を部品に置き換え、mermaid を描く（--theme が要る）")
    ap.add_argument("--src", default=None, help="--finalize で、断片の中の画像の相対パスの基準にする元の .md")
    ap.add_argument("--theme", required=True, choices=list(THEMES.keys()))
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
    ap.add_argument("--image-mode", default="embed", choices=["embed", "link"],
                    help="mdのローカル画像リンクの扱い（embed=data URIで埋め込み／link=外部フォルダ参照のまま）")
    args = ap.parse_args()

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
                          .replace("__STATIC_CSS__", STATIC_CSS)\
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
        print("  種類: flow / steps / cycle / bars / metrics / compare / hub / layers / sequence。")
        print("  figkit の図は段・現れ方が組み込み済み。key で動かす図は仕様に \"motion\": true を足すだけ。")
        print("[図の単位] <figure data-motion=\"auto|steps|none\" data-tempo=\"slow|normal|fast\" data-trigger=\"view|click|loop\" data-motion-dir=\"auto|x|y|reverse-x|reverse-y|radial\">")
        print("[要素の注釈]（svg 内の要素か <g>。すべて任意）")
        print("  data-step=\"N\"  現れる順番（同じ N は同時）   data-effect=\"draw|rise|fade|slide|pop|grow|wipe|none\"  現れ方")
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
