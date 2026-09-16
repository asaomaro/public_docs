"""rich diff の生成（標準ライブラリのみ・生成時に完結）。

**解析はここ（Python）で全部やり、ブラウザには「描けるだけの構造」だけを渡す**——
これが「第三者ライブラリを同梱しない」と「rich 対象が無ければ容量を払わない」を同時に満たす形。

扱うもの:
  - CSV / TSV  → セル単位の差分を持つ表（`kind: "table"`）
  - Markdown   → ノード木（`kind: "doc"`）。GitHub alert 記法と mermaid（4 図種）を含む
  - HTML       → 生の文字列（`kind: "html"`。描画は iframe sandbox 側の責務）
  - PDF        → ページ数・バイト数と、取れればテキスト差分（`kind: "pdf"`）

ノード木の形: ["tag", {attrs}, [children...]]、文字列はそのままテキストノード。
属性は白名簿（class / href / src / alt / colspan）に限る。
"""

import base64
import csv
import difflib
import io
import re
import zlib

TABLE_EXT = (".csv", ".tsv")
DOC_EXT = (".md", ".markdown")
HTML_EXT = (".html", ".htm")
PDF_EXT = (".pdf",)

ALERT_TYPES = ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION")

SAFE_HREF = re.compile(r"^(?:https?:|mailto:|#|[^:]*$)")


def rich_kind(path):
    """このパスが rich diff の対象なら種別を返す。対象外なら None。"""
    lowered = path.lower()
    if lowered.endswith(TABLE_EXT):
        return "table"
    if lowered.endswith(DOC_EXT):
        return "doc"
    if lowered.endswith(HTML_EXT):
        return "html"
    if lowered.endswith(PDF_EXT):
        return "pdf"
    return None


# --------------------------------------------------------------------------
# CSV / TSV
# --------------------------------------------------------------------------

def table_payload(old_text, new_text, path):
    """行を対応付け、`replace` の組はセル単位で比較する。"""
    delim = "\t" if path.lower().endswith(".tsv") else ","
    old_rows = _read_rows(old_text, delim)
    new_rows = _read_rows(new_text, delim)
    header = new_rows[0] if new_rows else (old_rows[0] if old_rows else [])
    body_old = old_rows[1:] if old_rows else []
    body_new = new_rows[1:] if new_rows else []

    matcher = difflib.SequenceMatcher(None, [tuple(r) for r in body_old], [tuple(r) for r in body_new])
    rows = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                rows.append(_row("equal", body_new[j1 + k], None))
        elif tag == "replace":
            span = max(i2 - i1, j2 - j1)
            for k in range(span):
                before = body_old[i1 + k] if i1 + k < i2 else None
                after = body_new[j1 + k] if j1 + k < j2 else None
                if before is not None and after is not None:
                    rows.append(_row("change", after, before))
                elif after is not None:
                    rows.append(_row("add", after, None))
                else:
                    rows.append(_row("del", before, None))
        elif tag == "delete":
            for k in range(i1, i2):
                rows.append(_row("del", body_old[k], None))
        elif tag == "insert":
            for k in range(j1, j2):
                rows.append(_row("add", body_new[k], None))
    return {"header": header, "rows": rows}


def _read_rows(text, delim):
    if text is None:
        return []
    return [row for row in csv.reader(io.StringIO(text), delimiter=delim)]


def _row(kind, cells, before):
    """1 行分。`change` のときだけセルごとに変化したかを持つ。"""
    cells = list(cells or [])
    if before is None:
        return {"kind": kind, "cells": [{"text": c, "changed": kind in ("add", "del")} for c in cells]}
    width = max(len(cells), len(before))
    out = []
    for i in range(width):
        after_cell = cells[i] if i < len(cells) else ""
        before_cell = before[i] if i < len(before) else ""
        out.append({"text": after_cell, "changed": after_cell != before_cell, "before": before_cell})
    return {"kind": kind, "cells": out}


# --------------------------------------------------------------------------
# Markdown → ノード木
# --------------------------------------------------------------------------

def markdown_nodes(text):
    """Markdown をノード木にする。未対応の記法は段落として落とす（壊さない）。"""
    if text is None:
        return None
    lines = text.split("\n")
    nodes = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        fence = re.match(r"^\s*```+\s*([\w-]*)\s*$", line)
        if fence:
            lang = fence.group(1).lower()
            body = []
            i += 1
            while i < len(lines) and not re.match(r"^\s*```+\s*$", lines[i]):
                body.append(lines[i])
                i += 1
            i += 1
            nodes.append(_code_block("\n".join(body), lang))
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            nodes.append(["h%d" % min(level + 1, 6), {}, _inline(heading.group(2))])
            i += 1
            continue
        if re.match(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", line):
            nodes.append(["hr", {}, []])
            i += 1
            continue
        if line.lstrip().startswith(">"):
            block, i = _take_while(lines, i, lambda s: s.lstrip().startswith(">") or s.strip())
            nodes.append(_blockquote(block))
            continue
        if _is_table_start(lines, i):
            table, i = _table(lines, i)
            nodes.append(table)
            continue
        if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", line):
            lst, i = _list(lines, i)
            nodes.append(lst)
            continue
        block, i = _take_while(lines, i, lambda s: bool(s.strip()) and not _starts_block(s))
        nodes.append(["p", {}, _inline(" ".join(s.strip() for s in block))])
    return nodes


def _starts_block(s):
    return bool(
        re.match(r"^\s*```", s)
        or re.match(r"^#{1,6}\s", s)
        or s.lstrip().startswith(">")
        or re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", s)
        or re.match(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", s)
    )


def _take_while(lines, i, pred):
    out = []
    while i < len(lines) and pred(lines[i]):
        out.append(lines[i])
        i += 1
    return out, i


def _code_block(code, lang):
    """コードブロック。mermaid は図にする（描けない図種はコードのまま＋理由）。"""
    if lang == "mermaid":
        svg, reason = mermaid_svg(code)
        if svg:
            data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
            return ["figure", {"class": "mermaid"}, [
                ["img", {"src": "data:image/svg+xml;base64," + data, "alt": "mermaid の図"}, []],
            ]]
        return ["figure", {"class": "mermaid-fallback"}, [
            ["pre", {"class": "code"}, [code]],
            ["p", {"class": "note"}, [reason]],
        ]]
    return ["pre", {"class": "code"}, [code]]


def _blockquote(block):
    """引用。先頭が GitHub alert 記法なら専用の見た目にする。"""
    stripped = [re.sub(r"^\s*>\s?", "", s) for s in block if s.strip()]
    if not stripped:
        return ["blockquote", {}, []]
    alert = re.match(r"^\[!(%s)\]\s*$" % "|".join(ALERT_TYPES), stripped[0].strip())
    if alert:
        kind = alert.group(1)
        body = [s for s in stripped[1:]]
        return ["div", {"class": "alert alert-%s" % kind.lower()}, [
            ["p", {"class": "alert-title"}, [kind]],
            ["p", {}, _inline(" ".join(body))],
        ]]
    return ["blockquote", {}, [["p", {}, _inline(" ".join(stripped))]]]


def _is_table_start(lines, i):
    if i + 1 >= len(lines):
        return False
    return "|" in lines[i] and bool(re.match(r"^\s*\|?[\s:\-|]+\|[\s:\-|]*$", lines[i + 1]))


def _table(lines, i):
    header = _cells(lines[i])
    i += 2
    rows = []
    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        rows.append(_cells(lines[i]))
        i += 1
    thead = ["thead", {}, [["tr", {}, [["th", {}, _inline(c)] for c in header]]]]
    tbody = ["tbody", {}, [["tr", {}, [["td", {}, _inline(c)] for c in row]] for row in rows]]
    return ["table", {}, [thead, tbody]], i


def _cells(line):
    parts = line.strip().strip("|").split("|")
    return [p.strip() for p in parts]


def _list(lines, i):
    """リスト。インデント 2 つで 1 段のネストとして扱う。"""
    ordered = bool(re.match(r"^\s*\d+[.)]\s+", lines[i]))
    items = []
    stack = [(0, items)]
    while i < len(lines):
        m = re.match(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$", lines[i])
        if not m:
            if lines[i].strip() and not _starts_block(lines[i]) and items:
                # 継続行は直前の項目に足す
                items[-1][2].append(" " + lines[i].strip())
                i += 1
                continue
            break
        depth = len(m.group(1)) // 2
        node = ["li", {}, _inline(m.group(2))]
        while stack and stack[-1][0] > depth:
            stack.pop()
        if stack[-1][0] < depth:
            child = []
            tag = "ol" if ordered else "ul"
            if stack[-1][1]:
                stack[-1][1][-1][2].append([tag, {}, child])
            else:
                stack[-1][1].append([tag, {}, child])
            stack.append((depth, child))
        stack[-1][1].append(node)
        i += 1
    return ["ol" if ordered else "ul", {}, items], i


_INLINE_RE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<image>!\[([^\]]*)\]\(([^)\s]+)[^)]*\))"
    r"|(?P<link>\[([^\]]+)\]\(([^)\s]+)[^)]*\))"
    r"|(?P<strong>\*\*[^*]+\*\*)"
    r"|(?P<em>(?<![\w*])[*_][^*_\n]+[*_](?![\w*]))"
)


def _inline(text):
    """行内記法。画像は外部取得を避けるためテキストに落とす（オフライン維持）。"""
    out = []
    pos = 0
    for m in _INLINE_RE.finditer(text or ""):
        if m.start() > pos:
            out.append(text[pos:m.start()])
        kind = m.lastgroup
        if kind == "code":
            out.append(["code", {}, [m.group(0)[1:-1]]])
        elif kind == "image":
            out.append("［画像: %s］" % (m.group(3) or m.group(4)))
        elif kind == "link":
            href = m.group(7)
            label = m.group(6)
            if SAFE_HREF.match(href):
                out.append(["a", {"href": href}, [label]])
            else:
                out.append("%s（%s）" % (label, href))
        elif kind == "strong":
            out.append(["strong", {}, [m.group(0)[2:-2]]])
        elif kind == "em":
            out.append(["em", {}, [m.group(0)[1:-1]]])
        pos = m.end()
    if pos < len(text or ""):
        out.append(text[pos:])
    return out


# --------------------------------------------------------------------------
# mermaid（4 図種だけを自前で描く。忠実再現は狙わない）
# --------------------------------------------------------------------------

def mermaid_svg(code):
    """mermaid のコードから SVG を作る。描けない図種は (None, 理由) を返す。"""
    body = [l for l in code.split("\n") if l.strip() and not l.strip().startswith("%%")]
    if not body:
        return None, "空の mermaid ブロックです"
    head = body[0].strip().lower()
    kind = head.split()[0] if head.split() else ""
    if kind.startswith("sequencediagram"):
        return _sequence_svg(body[1:]), None
    if kind.startswith(("flowchart", "graph", "statediagram")):
        direction = "LR" if " lr" in head or head.endswith("lr") else "TD"
        return _graph_svg(body[1:], direction), None
    return None, "この図種（%s）は描画対象外です。コードのまま表示しています" % (kind or "不明")


_NODE_RE = re.compile(r"([A-Za-z0-9_.\-]+)\s*(?:\[([^\]]*)\]|\(([^)]*)\)|\{([^}]*)\})?")
_EDGE_RE = re.compile(
    r"^\s*(.+?)\s*(-->|---|-\.->|==>)\s*(?:\|([^|]*)\|\s*)?(.+?)\s*(?::\s*(.*))?$")


def _graph_svg(lines, direction):
    nodes, order, edges = {}, [], []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("subgraph", "end", "class ", "click ", "style ")):
            # subgraph はグループ化だけなので、中身のノードは拾って枠は描かない
            continue
        m = _EDGE_RE.match(line)
        if m:
            src_id, src_label = _node(m.group(1))
            dst_id, dst_label = _node(m.group(4))
            for nid, label in ((src_id, src_label), (dst_id, dst_label)):
                if nid not in nodes:
                    nodes[nid] = label
                    order.append(nid)
                elif label and nodes[nid] == nid:
                    nodes[nid] = label
            edges.append((src_id, dst_id, (m.group(3) or m.group(5) or "").strip()))
            continue
        nid, label = _node(line)
        if nid and nid not in nodes:
            nodes[nid] = label
            order.append(nid)

    if not nodes:
        return None

    # 層を決める（入次数 0 から順に。循環していたら出現順で置く）
    layer = {n: 0 for n in order}
    for _ in range(len(order)):
        changed = False
        for src, dst, _label in edges:
            if layer.get(dst, 0) < layer.get(src, 0) + 1:
                layer[dst] = layer[src] + 1
                changed = True
        if not changed:
            break
    layers = {}
    for n in order:
        layers.setdefault(min(layer.get(n, 0), len(order)), []).append(n)

    box_h, gap_x, gap_y, pad = 36, 40, 70, 16
    placed = {}
    widths = {n: max(90, len(nodes[n]) * 9 + 24) for n in order}
    if direction == "LR":
        x = pad
        for depth in sorted(layers):
            col = layers[depth]
            width = max(widths[n] for n in col)
            y = pad
            for n in col:
                placed[n] = (x, y, widths[n], box_h)
                y += box_h + gap_x
            x += width + gap_y
        total_w = x
        total_h = max((p[1] + p[3] for p in placed.values()), default=0) + pad
    else:
        y = pad
        for depth in sorted(layers):
            row = layers[depth]
            x = pad
            for n in row:
                placed[n] = (x, y, widths[n], box_h)
                x += widths[n] + gap_x
            y += box_h + gap_y
        total_h = y
        total_w = max((p[0] + p[2] for p in placed.values()), default=0) + pad

    parts = [_svg_head(total_w, total_h)]
    for src, dst, label in edges:
        if src not in placed or dst not in placed:
            continue
        x1, y1, w1, h1 = placed[src]
        x2, y2, w2, h2 = placed[dst]
        if direction == "LR":
            start, end = (x1 + w1, y1 + h1 / 2), (x2, y2 + h2 / 2)
        else:
            start, end = (x1 + w1 / 2, y1 + h1), (x2 + w2 / 2, y2)
        parts.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="edge" marker-end="url(#arrow)"/>'
            % (start[0], start[1], end[0], end[1]))
        if label:
            parts.append('<text x="%.1f" y="%.1f" class="edge-label">%s</text>'
                         % ((start[0] + end[0]) / 2 + 4, (start[1] + end[1]) / 2 - 4, _esc(label)))
    for n in order:
        x, y, w, h = placed[n]
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" class="node"/>' % (x, y, w, h))
        parts.append('<text x="%.1f" y="%.1f" class="node-label">%s</text>'
                     % (x + w / 2, y + h / 2 + 5, _esc(nodes[n])))
    parts.append("</svg>")
    return "".join(parts)


def _node(token):
    token = token.strip()
    if token.startswith("[*]"):
        return "__start__", "●"
    m = _NODE_RE.match(token)
    if not m:
        return token, token
    nid = m.group(1)
    label = m.group(2) or m.group(3) or m.group(4) or nid
    return nid, label.strip().strip('"')


_SEQ_MSG_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*(->>|-->>|->|-->)\s*([A-Za-z0-9_.\-]+)\s*:\s*(.*)$")
_SEQ_PART_RE = re.compile(r"^\s*participant\s+([A-Za-z0-9_.\-]+)(?:\s+as\s+(.*))?$", re.IGNORECASE)


def _sequence_svg(lines):
    participants, labels, messages = [], {}, []
    for raw in lines:
        line = raw.strip()
        if not line or line.lower().startswith(("note ", "loop", "end", "alt", "else", "opt", "activate", "deactivate")):
            continue
        p = _SEQ_PART_RE.match(line)
        if p:
            pid = p.group(1)
            if pid not in participants:
                participants.append(pid)
            labels[pid] = (p.group(2) or pid).strip().strip('"')
            continue
        m = _SEQ_MSG_RE.match(line)
        if m:
            src, dst, text = m.group(1), m.group(3), m.group(4)
            for pid in (src, dst):
                if pid not in participants:
                    participants.append(pid)
                    labels.setdefault(pid, pid)
            messages.append((src, dst, text.strip(), m.group(2).startswith("--")))
    if not participants:
        return None

    col_w, top, row_h, pad = 190, 56, 44, 16
    width = pad * 2 + col_w * max(len(participants) - 1, 1) + 160
    height = top + row_h * (len(messages) + 1) + pad
    xs = {pid: pad + 80 + i * col_w for i, pid in enumerate(participants)}

    parts = [_svg_head(width, height)]
    for pid in participants:
        x = xs[pid]
        parts.append('<rect x="%.1f" y="%.1f" width="150" height="32" rx="6" class="node"/>' % (x - 75, 12))
        parts.append('<text x="%.1f" y="%.1f" class="node-label">%s</text>' % (x, 33, _esc(labels[pid])))
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="lifeline"/>' % (x, 46, x, height - pad))
    for i, (src, dst, text, dashed) in enumerate(messages):
        y = top + row_h * (i + 1)
        x1, x2 = xs[src], xs[dst]
        cls = "edge dashed" if dashed else "edge"
        if x1 == x2:
            parts.append('<path d="M%.1f %.1f q 50 10 0 22" class="%s" fill="none" marker-end="url(#arrow)"/>'
                         % (x1, y, cls))
        else:
            parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="%s" marker-end="url(#arrow)"/>'
                         % (x1, y, x2, y, cls))
        parts.append('<text x="%.1f" y="%.1f" class="edge-label">%s</text>'
                     % ((x1 + x2) / 2, y - 6, _esc(text)))
    parts.append("</svg>")
    return "".join(parts)


def _svg_head(width, height):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        '<style>'
        '.node{fill:#f6f8fa;stroke:#8c959f;stroke-width:1}'
        '.node-label{font:12px system-ui,sans-serif;fill:#1f2328;text-anchor:middle}'
        '.edge{stroke:#6e7781;stroke-width:1.2}'
        '.edge.dashed{stroke-dasharray:4 3}'
        '.edge-label{font:11px system-ui,sans-serif;fill:#59636e;text-anchor:middle}'
        '.lifeline{stroke:#d1d9e0;stroke-width:1;stroke-dasharray:4 4}'
        '</style>'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#6e7781"/></marker></defs>'
        % (int(width), int(height), int(width), int(height))
    )


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


# --------------------------------------------------------------------------
# PDF（zlib ＋ ToUnicode CMap。取れないことが普通にあるので二段構え）
# --------------------------------------------------------------------------

def pdf_payload(old_bytes, new_bytes):
    before = _pdf_info(old_bytes)
    after = _pdf_info(new_bytes)
    notes = []
    text_diff = None
    if before["text"] or after["text"]:
        text_diff = _text_diff(before["text"], after["text"])
    else:
        notes.append("この PDF からはテキストを抽出できませんでした"
                     "（ToUnicode を持たない・画像だけの PDF の可能性があります）")
    return {
        "pages": {"before": before["pages"], "after": after["pages"]},
        "bytes": {"before": before["bytes"], "after": after["bytes"]},
        "text": text_diff,
    }, (" / ".join(notes) or None)


def _pdf_info(data):
    if not data:
        return {"pages": 0, "bytes": 0, "text": []}
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    return {"pages": pages, "bytes": len(data), "text": _pdf_text(data)}


def _pdf_streams(data):
    out = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        body = data[start:end].rstrip(b"\r\n")
        try:
            out.append(zlib.decompress(body))
        except zlib.error:
            out.append(body)
    return out


def _pdf_text(data):
    """ToUnicode CMap を読んでテキストを復元する。取れなければ空リスト。"""
    streams = _pdf_streams(data)
    cmap = {}
    for s in streams:
        if b"beginbfchar" in s or b"beginbfrange" in s:
            cmap.update(_bfmap(s))
    if not cmap:
        return []
    out = []
    for stream in streams:
        if b"Tj" not in stream and b"TJ" not in stream:
            continue
        # **位置決めの演算子（Td / TD / T* / Tm / ET）で行に区切る**。
        # これをしないと、カーニングのたびに分かれた断片がそのまま 1 行ずつ並び、
        # 差分が「1 文字だけの行」だらけになって読めない。
        buf = []
        for m in re.finditer(rb"\[(.*?)\]\s*TJ|<([0-9A-Fa-f]+)>\s*Tj|\b(Td|TD|T\*|Tm|ET)\b", stream, re.S):
            if m.group(3):
                text = "".join(buf).strip()
                if text:
                    out.append(text)
                buf = []
                continue
            if m.group(1) is not None:
                buf.append("".join(_decode_hex(h, cmap)
                                   for h in re.findall(rb"<([0-9A-Fa-f]+)>", m.group(1))))
            elif m.group(2) is not None:
                buf.append(_decode_hex(m.group(2), cmap))
        text = "".join(buf).strip()
        if text:
            out.append(text)
    return out


def _decode_hex(hexbytes, cmap):
    h = hexbytes.decode("ascii", "ignore")
    return "".join(cmap.get(int(h[i:i + 4], 16), "") for i in range(0, len(h) - 3, 4))


def _bfmap(stream):
    text = stream.decode("latin-1", "replace")
    out = {}
    for blk in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            out[int(src, 16)] = "".join(chr(int(dst[i:i + 4], 16)) for i in range(0, len(dst) - 3, 4))
    for blk in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        for lo, hi, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            lo_i, hi_i, base = int(lo, 16), int(hi, 16), int(dst, 16)
            for k in range(lo_i, min(hi_i, lo_i + 4096) + 1):
                out[k] = chr(base + (k - lo_i))
    return out


def _text_diff(before, after):
    rows = []
    for line in difflib.unified_diff(before, after, lineterm="", n=2):
        if line.startswith(("---", "+++", "@@")):
            continue
        kind = "add" if line.startswith("+") else ("del" if line.startswith("-") else "ctx")
        rows.append({"kind": kind, "text": line[1:] if line[:1] in "+- " else line})
    return rows


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def build(path, old_text, new_text, old_bytes, new_bytes):
    """rich diff の payload を作る。対象外・作れない場合は None。"""
    kind = rich_kind(path)
    if kind is None:
        return None
    if kind == "table":
        if old_text is None and new_text is None:
            return None
        return {"kind": "table", "note": None, "payload": table_payload(old_text, new_text, path)}
    if kind == "doc":
        if old_text is None and new_text is None:
            return None
        return {"kind": "doc", "note": None,
                "payload": {"before": markdown_nodes(old_text), "after": markdown_nodes(new_text)}}
    if kind == "html":
        if old_text is None and new_text is None:
            return None
        return {"kind": "html", "note": "スクリプトを実行しない枠（sandbox）で描画しています",
                "payload": {"before": old_text, "after": new_text}}
    if kind == "pdf":
        payload, note = pdf_payload(old_bytes, new_bytes)
        return {"kind": "pdf", "note": note, "payload": payload}
    return None
