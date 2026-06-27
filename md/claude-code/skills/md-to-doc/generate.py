#!/usr/bin/env python3
"""md-to-doc: Markdown を視覚的に分かりやすい単一HTMLドキュメントに変換する。

- 5テーマ（CSS変数で切替）/ 出力モード single|print|site
- 見出しからメニュー・目次を自動生成、固定ヘッダー＋スクロール連動ハイライト
- コールアウト( > [!NOTE] )、コードコピー、印刷/PDF対応
- mermaid は生成時に「選んだテーマの配色」でSVG化して埋め込む（mmdc があれば）。
  mmdc が無い場合はコードブロックにフォールバック。

stdlib のみで動作。Markdown はメモ用途に十分なサブセットを自前パース。
"""
import sys, os, re, html, json, argparse, subprocess, tempfile, shutil, datetime, base64

# ──────────────────────────────────────────────────────────────────────────
# テーマ定義: :root の CSS 変数 + mermaid の themeVariables
# ──────────────────────────────────────────────────────────────────────────
THEMES = {
    "corporate": {
        "label": "モダンコーポレート",
        "accents": ["#1a56db", "#0ea5e9", "#6366f1", "#0d9488"],
        "vars": {
            "--bg": "#f7f9fc", "--card": "#ffffff", "--ink": "#1f2937",
            "--muted": "#6b7280", "--line": "#e5e7eb",
            "--accent": "#1a56db", "--accent-2": "#1e40af", "--accent-soft": "#eff4ff",
            "--code-bg": "#0f172a", "--code-fg": "#e2e8f0",
            "--radius": "14px", "--shadow": "0 1px 3px rgba(16,24,40,.06)",
            "--font": '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--font-head": '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "linear-gradient(135deg,#1a56db,#1e40af)",
            "--header-fg": "#ffffff",
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
    },
    "darktech": {
        "label": "ダークテック",
        "accents": ["#22d3ee", "#a78bfa", "#34d399", "#f472b6"],
        "dark": True,
        "vars": {
            "--bg": "#0b0f17", "--card": "#121826", "--ink": "#e5e9f0",
            "--muted": "#8b97a8", "--line": "#1f2937",
            "--accent": "#22d3ee", "--accent-2": "#a78bfa", "--accent-soft": "#0e1420",
            "--code-bg": "#0e1420", "--code-fg": "#e5e9f0",
            "--radius": "12px", "--shadow": "0 1px 0 rgba(255,255,255,.02)",
            "--font": '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--font-head": '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "#0b0f17",
            "--header-fg": "#e5e9f0",
        },
        "mermaid": {
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
        "accents": ["#ff5d73", "#ffb13d", "#2ec4b6", "#5a7dff", "#a056ff"],
        "vars": {
            "--bg": "#fff7f2", "--card": "#ffffff", "--ink": "#23243a",
            "--muted": "#6c6f8a", "--line": "#f0e6de",
            "--accent": "#ff5d73", "--accent-2": "#5a7dff", "--accent-soft": "#fff0e8",
            "--code-bg": "#23243a", "--code-fg": "#f3f1ff",
            "--radius": "22px", "--shadow": "0 10px 28px rgba(40,30,60,.08)",
            "--font": '"Hiragino Maru Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--font-head": '"Hiragino Maru Gothic ProN","Yu Gothic",system-ui,sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "linear-gradient(135deg,#ff5d73,#ffb13d)",
            "--header-fg": "#ffffff",
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
    },
    "editorial": {
        "label": "エディトリアル",
        "accents": ["#8b1e3f", "#a8814e", "#3f6b5e", "#5b4b8a"],
        "vars": {
            "--bg": "#fbfaf7", "--card": "#ffffff", "--ink": "#1a1a1a",
            "--muted": "#555555", "--line": "#dddddd",
            "--accent": "#8b1e3f", "--accent-2": "#8b1e3f", "--accent-soft": "#f6eef1",
            "--code-bg": "#1a1a1a", "--code-fg": "#f5f5f5",
            "--radius": "4px", "--shadow": "none",
            "--font": '"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif',
            "--font-head": '"Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "#fbfaf7",
            "--header-fg": "#1a1a1a",
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
    },
    "pastel": {
        "label": "やわらかパステル",
        "accents": ["#ff9eb5", "#ffd6a5", "#b8e6d0", "#a7d8f0", "#d4c5f9"],
        "vars": {
            "--bg": "#fef6fb", "--card": "#ffffff", "--ink": "#4a4458",
            "--muted": "#8a8499", "--line": "#f1e7f3",
            "--accent": "#ff9eb5", "--accent-2": "#a7d8f0", "--accent-soft": "#fff0f6",
            "--code-bg": "#4a4458", "--code-fg": "#fdf2f8",
            "--radius": "26px", "--shadow": "0 12px 30px rgba(150,120,180,.10)",
            "--font": '"Hiragino Maru Gothic ProN","Yu Gothic Medium",system-ui,sans-serif',
            "--font-head": '"Hiragino Maru Gothic ProN","Yu Gothic Medium",system-ui,sans-serif',
            "--mono": '"SFMono-Regular",Menlo,Consolas,monospace',
            "--header-bg": "linear-gradient(135deg,#ff9eb5,#d4c5f9)",
            "--header-fg": "#ffffff",
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
    },
}

CALLOUT_LABELS = {
    "NOTE": ("ノート", "ℹ️"), "TIP": ("ヒント", "💡"),
    "IMPORTANT": ("重要", "❗"), "WARNING": ("注意", "⚠️"),
    "CAUTION": ("警告", "🚫"),
}

# ──────────────────────────────────────────────────────────────────────────
# インライン記法
# ──────────────────────────────────────────────────────────────────────────
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

    def indent_of(s):
        m = re.match(r"[ \t]*", s)
        return len(m.group(0).replace("\t", "    "))

    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # 見出し
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1)); txt = m.group(2).strip()
            inner = inline(txt)
            if level in (2, 3):
                slug = slugify(txt, used_slugs)
                headings.append({"level": level, "text": txt, "slug": slug})
                out.append('<h%d id="%s" class="hl">%s<a class="anchor" href="#%s">#</a></h%d>'
                           % (level, slug, inner, slug, level))
            else:
                out.append("<h%d>%s</h%d>" % (level, inner, level))
            i += 1
            continue

        # コードフェンス / mermaid
        m = re.match(r"^(`{3,}|~{3,})\s*([\w-]*)\s*$", line)
        if m:
            fence = m.group(1)[0]; lang = m.group(2).lower()
            j = i + 1; buf = []
            while j < n and not re.match(r"^%s{3,}\s*$" % re.escape(fence), lines[j]):
                buf.append(lines[j]); j += 1
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
                                      top_level=False, layout=layout)
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
            th = "".join("<th>%s</th>" % inline(c) for c in header)
            trs = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in rows)
            out.append('<div class="tablewrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                       % (th, trs))
            continue

        # リスト
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            items = []
            while i < n and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                lm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i])
                items.append({"indent": indent_of(lines[i]),
                              "ordered": bool(re.match(r"\d+\.", lm.group(2))),
                              "text": lm.group(3)})
                i += 1
            if top_level and layout != "plain":
                out.append(render_list(items, layout))
            else:
                out.append(build_list(items))
            continue

        # 段落（空行まで結合）
        para = [line]; i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|>|\s*([-*+]|\d+\.)\s|`{3,}|~{3,}|\s*([-*_])(\s*\3){2,}\s*$)", lines[i]):
            para.append(lines[i]); i += 1
        out.append("<p>%s</p>" % inline(" ".join(s.strip() for s in para)))

    return "\n".join(out)


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


# 描画中テーマの配色サイクル（convert_file でセット）
_ACCENTS = ["#1a56db"]

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


def render_list(items, layout):
    """トップレベルのリストを、選択レイアウト（cards/timeline/accordion）で描画。
    先頭絵文字→アイコン、末尾{タグ}→pill、カード色はテーマ配色を循環。"""
    if layout == "plain":
        return build_list(items)
    groups = split_top_items(items)

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
def render_mermaid(sources, theme):
    if not sources:
        return {}, True
    mmdc = shutil.which("mmdc")
    if not mmdc:
        return {}, False
    result = {}
    tmp = tempfile.mkdtemp(prefix="md2doc_")
    try:
        cfg = os.path.join(tmp, "cfg.json")
        with open(cfg, "w") as f:
            json.dump(theme["mermaid"], f)
        pup = os.path.join(tmp, "pup.json")
        with open(pup, "w") as f:
            json.dump({"args": ["--no-sandbox", "--disable-setuid-sandbox"]}, f)
        for idx, src in enumerate(sources):
            inp = os.path.join(tmp, "d%d.mmd" % idx)
            outp = os.path.join(tmp, "d%d.svg" % idx)
            with open(inp, "w") as f:
                f.write(src)
            try:
                subprocess.run([mmdc, "-i", inp, "-o", outp, "-c", cfg, "-p", pup, "-b", "transparent"],
                               check=True, capture_output=True, timeout=90)
                with open(outp) as f:
                    svg = f.read()
                svg = re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
                result[idx] = '<figure class="mermaid-fig">%s</figure>' % svg
            except Exception:
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
                "--accent", "--accent-2", "--accent-soft", "--font"]


def theme_palette(theme_key):
    v = THEMES[theme_key]["vars"]
    pal = {k.lstrip("-"): v[k] for k in PALETTE_KEYS if k in v}
    pal["dark"] = bool(THEMES[theme_key].get("dark"))
    return pal


# ──────────────────────────────────────────────────────────────────────────
# テンプレート
# ──────────────────────────────────────────────────────────────────────────
STATIC_CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:var(--font);color:var(--ink);background:var(--bg);line-height:1.85;
  -webkit-font-smoothing:antialiased}
.progress{position:fixed;top:0;left:0;height:3px;width:0;background:var(--accent);z-index:200;transition:width .1s}
.topbar{position:fixed;top:0;left:0;right:0;height:var(--nav-h);z-index:100;
  background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line)}
.topbar-inner{max-width:var(--maxw);margin:0 auto;height:100%;padding:0 24px;
  display:flex;align-items:center;gap:20px}
.brand{font-family:var(--font-head);font-weight:800;font-size:15px;color:var(--accent);
  white-space:nowrap;text-decoration:none;display:flex;align-items:center;gap:8px}
.nav-menu{display:flex;gap:3px;margin-left:auto;flex-wrap:wrap;overflow-x:auto}
.nav-menu a{font-family:var(--font-head);font-size:13px;font-weight:700;color:var(--muted);
  text-decoration:none;padding:7px 13px;border-radius:8px;transition:.18s;white-space:nowrap}
.nav-menu a:hover{color:var(--accent);background:var(--accent-soft)}
.nav-menu a.active{color:#fff;background:var(--accent)}
.hamburger{display:none;margin-left:auto;background:none;border:1px solid var(--line);
  border-radius:8px;padding:6px 10px;color:var(--ink);font-size:18px;cursor:pointer}
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
.toc{position:sticky;top:calc(var(--nav-h) + 24px);font-size:13.5px;padding-top:32px}
.toc .toc-ttl{font-family:var(--font-head);font-weight:800;font-size:12px;letter-spacing:.1em;
  color:var(--muted);margin-bottom:12px}
.toc a{display:block;color:var(--muted);text-decoration:none;padding:4px 10px;border-left:2px solid var(--line);
  transition:.15s}
.toc a.lv3{padding-left:22px;font-size:12.5px}
.toc a:hover{color:var(--accent)}
.toc a.active{color:var(--accent);border-left-color:var(--accent);font-weight:700}
.content{min-width:0;padding-top:32px}
.content h2.hl{font-family:var(--font-head);font-size:23px;font-weight:800;margin:48px 0 18px;
  padding-left:14px;border-left:5px solid var(--accent);color:var(--accent-2)}
.content h2.hl:first-child{margin-top:0}
.content h3.hl{font-family:var(--font-head);font-size:18px;font-weight:700;margin:30px 0 10px}
.content h4{font-family:var(--font-head);font-size:15.5px;margin:22px 0 8px}
.anchor{opacity:0;margin-left:8px;color:var(--accent);text-decoration:none;font-weight:400}
.hl:hover .anchor{opacity:.5}
.content p{margin:12px 0}
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
.copy-btn.done{background:var(--accent);border-color:var(--accent)}
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
.tl-dot{width:44px;height:44px;border-radius:50%;background:var(--ca,var(--accent));color:#fff;
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
  color:#fff;background:var(--ca,var(--accent))}
.split{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:18px 0}
@media(max-width:680px){.split{grid-template-columns:1fr}}
/* 目次の表示モード */
.toc-menu .toc,.toc-none .toc{display:none}
.toc-menu .layout,.toc-none .layout{grid-template-columns:1fr}
.toc-sidebar .nav-menu{display:none}
.toc-none .nav-menu,.toc-none .hamburger{display:none!important}
hr{border:none;border-top:1px solid var(--line);margin:28px 0}
.backtop{position:fixed;bottom:26px;right:26px;width:44px;height:44px;border-radius:50%;
  background:var(--accent);color:#fff;border:none;font-size:18px;cursor:pointer;opacity:0;
  pointer-events:none;transition:.25s;box-shadow:0 6px 18px rgba(0,0,0,.2);z-index:90}
.backtop.show{opacity:1;pointer-events:auto}
footer{max-width:var(--maxw);margin:40px auto 0;padding:24px;text-align:center;
  color:var(--muted);font-size:12px;border-top:1px solid var(--line)}
@media(max-width:860px){
  .layout{grid-template-columns:1fr}.toc{display:none}
  .nav-menu{position:fixed;top:var(--nav-h);left:0;right:0;background:var(--bg);
    border-bottom:1px solid var(--line);flex-direction:column;padding:8px;display:none}
  .nav-menu.open{display:flex}.hamburger{display:block}
}
@media print{
  .topbar,.progress,.backtop,.copy-btn,.hamburger,.anchor{display:none!important}
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

PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
:root{
__ROOTVARS__
  --nav-h:60px; --maxw:1080px;
}
__STATIC_CSS__
</style>
</head>
<body id="top" class="__BODYCLASS__">
<div class="progress"></div>
<nav class="topbar"><div class="topbar-inner">
  <a href="#top" class="brand">__BRAND__</a>
  <button class="hamburger" type="button" aria-label="メニュー">☰</button>
  <div class="nav-menu">__NAV__</div>
</div></nav>
<header class="hero"><div class="hero-inner">
  __EYEBROW____H1____DATE____TAGS__
</div></header>
<div class="layout">
  <aside class="toc"><div class="toc-ttl">目次</div>__TOC__</aside>
  <main class="content">__CONTENT__</main>
</div>
<button class="backtop" type="button" aria-label="トップへ">↑</button>
<footer>__FOOTER__</footer>
<script>
(function(){
  var navH=parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-h'))||60;
  var links=[].slice.call(document.querySelectorAll('.nav-menu a, .toc a'));
  // 見出し要素を文書順で取得（スクロールスパイの対象）
  var targets=[].slice.call(document.querySelectorAll('.content .hl'));
  function setActive(id){
    links.forEach(function(a){a.classList.toggle('active', a.getAttribute('href').slice(1)===id);});
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
</body>
</html>
"""


def build_html(meta, content_html, headings, theme_key, title, brand, footer, toc_mode="sidebar"):
    theme = THEMES[theme_key]
    rootvars = "\n".join("  %s:%s;" % (k, v) for k, v in theme["vars"].items())
    nav = "".join('<a href="#%s">%s</a>' % (h["slug"], html.escape(h["text"]))
                  for h in headings if h["level"] == 2)
    toc = "".join('<a class="lv%d" href="#%s">%s</a>' % (h["level"], h["slug"], html.escape(h["text"]))
                  for h in headings) or '<span style="color:var(--muted);font-size:12px">―</span>'
    eyebrow = '<span class="eyebrow">%s</span>' % html.escape(meta["eyebrow"]) if meta.get("eyebrow") else ""
    h1 = "<h1>%s</h1>" % html.escape(title)
    date = '<div class="date">%s</div>' % html.escape(meta["date"]) if meta.get("date") else ""
    tags = ""
    if meta.get("tags"):
        tg = [t.strip() for t in re.split(r"[,，、]", meta["tags"]) if t.strip()]
        tags = '<div class="tags">%s</div>' % "".join("<span>%s</span>" % html.escape(t) for t in tg)
    repl = {
        "__TITLE__": html.escape(title), "__ROOTVARS__": rootvars,
        "__STATIC_CSS__": STATIC_CSS, "__BRAND__": html.escape(brand),
        "__NAV__": nav, "__TOC__": toc, "__EYEBROW__": eyebrow, "__H1__": h1,
        "__DATE__": date, "__TAGS__": tags, "__CONTENT__": content_html,
        "__FOOTER__": html.escape(footer), "__BODYCLASS__": "toc-" + toc_mode,
    }
    page = PAGE
    for k, v in repl.items():
        page = page.replace(k, v)
    return page


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
                 layout="plain", design="deterministic"):
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
    _ACCENTS = THEMES[theme_key].get("accents") or [THEMES[theme_key]["vars"]["--accent"]]

    # AI設計（freeform もしくは design=ai）: 本文は Claude が後段で著述する。
    # ガワだけ生成し中身はプレースホルダにする。
    if layout == "freeform" or design == "ai":
        headings = extract_headings(lines)
        content = "<!--MD2DOC_CONTENT-->"
        brand = meta.get("brand", title if len(title) <= 16 else title[:15] + "…")
        footer = "%s — Generated from Markdown by md-to-doc" % (meta.get("date") or
                 datetime.date.today().isoformat())
        out_html = build_html(meta, content, headings, theme_key, title, brand, footer, toc_mode)
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

    brand = meta.get("brand", title if len(title) <= 16 else title[:15] + "…")
    footer = "%s — Generated from Markdown by md-to-doc" % (meta.get("date") or
             datetime.date.today().isoformat())
    out_html = build_html(meta, content, headings, theme_key, title, brand, footer, toc_mode)
    return out_html, title, headings, ok, pending


def main():
    ap = argparse.ArgumentParser(description="Markdown を視覚的なHTMLドキュメントに変換")
    ap.add_argument("inputs", nargs="+", help="入力 .md（複数可）")
    ap.add_argument("--theme", required=True, choices=list(THEMES.keys()))
    ap.add_argument("--mode", default="single", choices=["single", "print", "site"])
    ap.add_argument("--outdir", default=None, help="出力先（既定: 入力と同じ場所）")
    ap.add_argument("--eyebrow", default=None, help="ヘッダー上部の小見出し")
    ap.add_argument("--auto-figure", default="off", choices=["off", "light", "rich"],
                    help="mermaid 以外の内容も、図解すべき箇所をClaudeが図にする（off/控えめ/積極的）")
    ap.add_argument("--toc", default="sidebar", choices=["sidebar", "menu", "both", "none"],
                    help="目次の出し方（左サイドのみ/ヘッダーメニューのみ/両方/なし）")
    ap.add_argument("--layout", default="plain",
                    choices=["plain", "cards", "timeline", "accordion", "freeform"],
                    help="本文の見せ方/テイスト（箇条書き/カード/タイムライン/アコーディオン/完全フリーフォーム）")
    ap.add_argument("--design", default="deterministic", choices=["deterministic", "ai"],
                    help="deterministic=スクリプトが型変換／ai=選んだ形式のテイストでClaudeが作り込む")
    args = ap.parse_args()

    produced = []
    todo = []  # 手描きが必要な図 [{out, id, source}]
    for path in args.inputs:
        if not os.path.isfile(path):
            print("skip (not found):", path, file=sys.stderr); continue
        out_html, title, headings, ok, pending = convert_file(
            path, args.theme, args.eyebrow, args.auto_figure, args.toc, args.layout, args.design)
        outdir = args.outdir or os.path.dirname(os.path.abspath(path))
        os.makedirs(outdir, exist_ok=True)
        outname = os.path.splitext(os.path.basename(path))[0] + ".html"
        outpath = os.path.join(outdir, outname)
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(out_html)
        entry = {"src": path, "out": outpath, "title": title,
                 "h2": [h["slug"] for h in headings if h["level"] == 2]}
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

    if args.mode == "site" and produced:
        outdir = args.outdir or os.path.dirname(os.path.abspath(produced[0]["src"]))
        cards = "".join(
            '<a class="idx-card" href="%s"><div class="idx-ttl">%s</div>'
            '<div class="idx-sub">%s</div></a>'
            % (html.escape(os.path.basename(p["out"]), quote=True),
               html.escape(p["title"]), html.escape(os.path.basename(p["src"])))
            for p in produced)
        theme = THEMES[args.theme]
        rootvars = "\n".join("  %s:%s;" % (k, v) for k, v in theme["vars"].items())
        index = INDEX_PAGE.replace("__ROOTVARS__", rootvars)\
                          .replace("__STATIC_CSS__", STATIC_CSS).replace("__CARDS__", cards)\
                          .replace("__COUNT__", str(len(produced)))
        ipath = os.path.join(outdir, "index.html")
        with open(ipath, "w", encoding="utf-8") as f:
            f.write(index)
        print("OK :", ipath, "(index)")

    # AI設計（freeform もしくは design=ai）: Claude が本文を著述するための情報を出力
    if (args.layout == "freeform" or args.design == "ai") and produced:
        theme = THEMES[args.theme]
        pal = theme_palette(args.theme)
        pal["accents"] = theme.get("accents", [])
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
        print("[基調テイスト=%s] %s" % (args.layout, taste))
        print("決定論的な型変換ではなく、上記テイストを保ちつつ手作りサンプル相当の作り込みを行う。")
        print("\n[配色] " + json.dumps(pal, ensure_ascii=False))
        print("[使える部品クラス] hero外の本文で利用可:")
        print("  見出し: <h2 id=SLUG class=\"hl\">..</h2> / <h3 id=SLUG class=\"hl\">..</h3>（下記SLUG必須）")
        print("  リード文:.lead / カード:.card-grid>.doc-card(.doc-card-top>.doc-card-ic+.doc-card-h,.doc-card-tags>span,.doc-card-b)")
        print("  特徴グリッド:.feature-grid / 数値:.stat-row>.stat(.big,.cap) / チップ:.chips>.chip / バッジ:.badge")
        print("  タイムライン:.timeline>.tl-item(.tl-dot,.tl-body>.tl-h) / 折りたたみ:.accordion>.acc-item>summary")
        print("  コールアウト:.callout.callout-note(.callout-head,.callout-body) / 表:.tablewrap>table / 2分割:.split")
        print("  ※各要素に style=\"--ca:COLOR\" を付けると、その部品の配色を accents から個別指定できる。")
        print("  ※図は自己完結の <figure class=\"mermaid-fig\"><svg ...></figure> で（外部依存なし・viewBox必須）。")
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
        if args.auto_figure == "light":
            print("level=light: 各ドキュメントで最も効果的な1〜2個に絞る。")
        else:
            print("level=rich: 図解できる箇所は積極的に図にする。")
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
        print("配色パレット: " + json.dumps(theme_palette(args.theme), ensure_ascii=False))
        print("TODO一覧(JSON): " + sidecar)
        for t in todo:
            print("\n--- figure id=%s  in  %s ---" % (t["id"], t["out"]))
            print(t["source"])
        print("===== /MERMAID_MANUAL_RENDER_REQUIRED =====")


INDEX_PAGE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ドキュメント一覧</title><style>
:root{
__ROOTVARS__
  --nav-h:60px; --maxw:1080px;
}
__STATIC_CSS__
.idx-wrap{max-width:var(--maxw);margin:0 auto;padding:calc(var(--nav-h) + 40px) 24px 80px}
.idx-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:18px;margin-top:24px}
.idx-card{display:block;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:22px;text-decoration:none;color:var(--ink);box-shadow:var(--shadow);transition:.18s}
.idx-card:hover{transform:translateY(-3px);border-color:var(--accent)}
.idx-ttl{font-family:var(--font-head);font-weight:800;font-size:17px;color:var(--accent-2)}
.idx-sub{color:var(--muted);font-size:12px;margin-top:8px}
</style></head><body id="top">
<nav class="topbar"><div class="topbar-inner"><a href="#top" class="brand">📚 ドキュメント一覧</a></div></nav>
<div class="idx-wrap"><h1 style="font-family:var(--font-head);font-size:30px">ドキュメント一覧</h1>
<p style="color:var(--muted)">__COUNT__ 件のドキュメント</p>
<div class="idx-grid">__CARDS__</div></div></body></html>
"""


if __name__ == "__main__":
    main()
