"""シンタックスハイライト（生成時に行う・標準ライブラリのみ）。

方針:
  - **ファイルの全文を 1 回だけトークナイズし、結果を行に切る**。差分行に個別に正規表現を
    当てると、複数行文字列（docstring）やブロックコメントの途中行が壊れる。
  - 目的は「構文の切れ目が見えること」であって、構文解析器の正確さではない。
    クラスは com（コメント）/ str（文字列）/ kw（キーワード）/ num（数値）/ plain の 5 つだけ。
  - ブラウザにトークナイザを積まないための工程なので、ここで完結させる。
"""

import re

# 拡張子 → 言語。ここに無い拡張子は色を付けない（素のまま表示する）。
EXT_LANG = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".json": "json",
    ".yml": "yaml", ".yaml": "yaml",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".css": "css",
    ".html": "html", ".htm": "html",
    ".md": "markdown", ".markdown": "markdown",
    ".sql": "sql",
}

_PY_KW = (
    "False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|"
    "finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield"
)
_JS_KW = (
    "await|async|break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|"
    "finally|for|function|if|import|in|instanceof|let|new|of|return|super|switch|this|throw|try|typeof|"
    "var|void|while|with|yield|null|true|false|undefined"
)
_TS_KW = _JS_KW + "|interface|type|enum|implements|declare|namespace|readonly|public|private|protected|as|any|never|unknown"
_SH_KW = (
    "if|then|elif|else|fi|for|while|until|do|done|case|esac|function|return|exit|local|export|"
    "readonly|shift|set|unset|trap|source|break|continue|in"
)
_SQL_KW = (
    "SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|ALTER|DROP|INDEX|VIEW|JOIN|"
    "LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|AND|OR|NOT|NULL|AS|DISTINCT|"
    "UNION|ALL|CASE|WHEN|THEN|ELSE|END|PRIMARY|KEY|FOREIGN|REFERENCES|DEFAULT|WITH"
)

# 言語ごとの規則。値は「クラス名 → 正規表現」。上から順に試される（辞書の並び順が優先順位）。
SPECS = {
    "python": {
        "com": r"\#[^\n]*",
        "str": r"(?:[rbuBRUF]{0,2})(?:'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\")",
        "kw": r"\b(?:%s)\b" % _PY_KW,
        "num": r"\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b",
    },
    "javascript": {
        "com": r"//[^\n]*|/\*[\s\S]*?\*/",
        "str": r"`(?:\\.|[^`\\])*`|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"",
        "kw": r"\b(?:%s)\b" % _JS_KW,
        "num": r"\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b",
    },
    "typescript": {
        "com": r"//[^\n]*|/\*[\s\S]*?\*/",
        "str": r"`(?:\\.|[^`\\])*`|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"",
        "kw": r"\b(?:%s)\b" % _TS_KW,
        "num": r"\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b",
    },
    "json": {
        "str": r"\"(?:\\.|[^\"\\])*\"",
        "kw": r"\b(?:true|false|null)\b",
        "num": r"-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b",
    },
    "yaml": {
        "com": r"\#[^\n]*",
        "str": r"'(?:''|[^'])*'|\"(?:\\.|[^\"\\])*\"",
        "kw": r"^\s*-?\s*[\w.-]+(?=\s*:)|\b(?:true|false|null|yes|no)\b",
        "num": r"\b\d+(?:\.\d+)?\b",
    },
    "shell": {
        "com": r"\#[^\n]*",
        "str": r"'[^']*'|\"(?:\\.|[^\"\\])*\"",
        "kw": r"\b(?:%s)\b" % _SH_KW,
        "num": r"\b\d+\b",
    },
    "css": {
        "com": r"/\*[\s\S]*?\*/",
        "str": r"'[^'\n]*'|\"[^\"\n]*\"",
        "kw": r"@[\w-]+|[.#][\w-]+(?=[^{}]*\{)|\b[a-z-]+(?=\s*:)",
        "num": r"-?\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms)?\b|\#[0-9a-fA-F]{3,8}\b",
    },
    "html": {
        "com": r"<!--[\s\S]*?-->",
        "str": r"\"[^\"]*\"|'[^']*'",
        "kw": r"</?[A-Za-z][\w:-]*|/?>",
        "num": r"&[a-zA-Z#0-9]+;",
    },
    "markdown": {
        "com": r"^>[^\n]*",
        "str": r"`{1,3}[^`\n]*`{1,3}",
        "kw": r"^\#{1,6}[^\n]*|^\s*(?:[-*+]|\d+\.)\s",
        "num": r"^\s*\|.*\|\s*$",
    },
    "sql": {
        "com": r"--[^\n]*|/\*[\s\S]*?\*/",
        "str": r"'(?:''|[^'])*'",
        "kw": r"\b(?:%s)\b" % _SQL_KW,
        "num": r"\b\d+(?:\.\d+)?\b",
    },
}

_COMPILED = {}


def language_for(path):
    """パスから言語を決める。未対応なら None。"""
    lowered = path.lower()
    for ext, lang in EXT_LANG.items():
        if lowered.endswith(ext):
            return lang
    return None


def _pattern(lang):
    if lang not in _COMPILED:
        spec = SPECS[lang]
        parts = ["(?P<%s>%s)" % (cls, rx) for cls, rx in spec.items()]
        flags = re.MULTILINE
        if lang in ("sql",):
            flags |= re.IGNORECASE
        _COMPILED[lang] = re.compile("|".join(parts), flags)
    return _COMPILED[lang]


def tokenize_lines(text, lang):
    """全文をトークナイズし、**行ごとのトークン列**を返す。

    返り値は行数ぶんのリストで、各要素は [[クラス, 文字列], …]。
    クラスが plain のトークンも含めて、連結すると元の行に戻る（描画側が全文を復元できる）。
    """
    if lang not in SPECS:
        return None
    pattern = _pattern(lang)
    spans = []
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            spans.append(("plain", text[pos:m.start()]))
        spans.append((m.lastgroup, m.group(0)))
        pos = m.end()
    if pos < len(text):
        spans.append(("plain", text[pos:]))

    # 行に切り分ける。複数行にまたがるトークン（docstring・ブロックコメント）は
    # 行ごとの断片に割って、同じクラスのまま各行に置く。
    lines = [[]]
    for cls, chunk in spans:
        parts = chunk.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append([cls, part])
    return lines
