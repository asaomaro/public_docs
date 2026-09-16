#!/usr/bin/env python3
"""diff-review-html: ローカルの git 差分を GitHub PR 風の単一 HTML にし、
レビュー記録（JSON）を人間と AI のあいだで往復させる。

サブコマンド:
  html      差分から自己完結した単一 HTML を作る（--import で既存のレビュー記録を埋め込む）
  template  その差分に対する「空のレビュー記録」を出す（AI が指摘を埋める雛形）
  check     レビュー記録 JSON を検証する（壊れていれば理由を示して exit 3）
  list      未解決の指摘を一覧にする（AI が修正に使う）

方針:
  - 標準ライブラリのみ（pip パッケージ・Node・jq を使わない）。sh 版 / pwsh 版は持たない。
  - 出力は OS を問わず UTF-8・LF 固定。時刻・乱数を混ぜないので、同じ入力からは同じ出力が出る。
  - 差分もコメントも HTML として解釈させない（画面は textContent のみで描画し、
    埋め込む JSON は "<" を \\u003c に退避する）。
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import highlight
import richdiff

SCHEMA = "diff-review/2"
SCHEMA_LEGACY = "diff-review/1"
SCHEMAS = (SCHEMA, SCHEMA_LEGACY)

# バンドル（差分 ＋ 記録を 1 ファイルに）。
# 前後を固定しているのは、**JS を実行せずに JSON として読める**ようにするため
# （research.md F2 で Python / Node / ブラウザの 3 者から実測）。
BUNDLE_SCHEMA = "diff-review-bundle/1"
BUNDLE_GLOBAL = "window.__DIFF_REVIEW_BUNDLE__"
BUNDLE_PREFIX = BUNDLE_GLOBAL + " = "
BUNDLE_SUFFIX = ";\n"
BUNDLE_EXT = ".dreview"

# テンプレートの差し込み口。`render_html` はこの 5 つを 1 回の走査で置き換える。
PLACEHOLDER_RE = re.compile(r"__(?:TITLE|STYLE|UI_JS|APP_JS|RICH_JS|DIFF_DATA|REVIEW_DATA)__")
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# git が「空のツリー」に与えている固定のハッシュ。最初のコミットの差分を取るときに親の代わりに使う。
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_GIT = 2
EXIT_INVALID = 3

REVIEW_STATES = ("APPROVED", "CHANGES_REQUESTED", "COMMENTED")
SIDES = ("LEFT", "RIGHT")
THREAD_KINDS = ("review", "note")          # note = 作者の説明（提出されない・未解決に数えない）
SEVERITIES = ("must", "should", "nit")     # None は「重大度なし」
DEFAULT_EXPAND_MAX_LINES = 2000


# --------------------------------------------------------------------------
# 出力の規約（T3）
#   ここを 1 箇所に閉じ込める。書き出し口が増えてから規約を足すと、どこか 1 つが漏れて
#   「同じ入力なのに出力が違う」が残る。
# --------------------------------------------------------------------------

def dumps_canonical(obj):
    """正規形の JSON。キー昇順・インデント 2・非 ASCII をそのまま・末尾に改行。

    キー順と整形を固定するのは、(1) 同じ内容なら常に同じバイト列になること、
    (2) 人間と AI が diff で読めること、の 2 つのため。
    """
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def json_for_script_block(obj):
    """<script type="application/json"> に埋めるための JSON。

    素のまま埋めると本文中の "</script>" でブロックが切れる（実測で SyntaxError）。
    JSON の文字列中では "<" を \\u003c と書けるので、すべての "<" を退避する。
    """
    return dumps_canonical(obj).replace("<", "\\u003c")


def js_safe(text):
    """JS のソースに置いても壊れない形へ。

    U+2028 / U+2029 は **JS では行終端文字**で、ES2019 より前のエンジンでは文字列リテラルの
    中に生で置けない。JSON としては `\\u2028` と書いても同じ文字なので、退避しても意味は変わらない。
    """
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def bundle_object(target, files, rich_enabled, review):
    """バンドルの中身（辞書）。`review` は `diff-review/2` の記録**そのもの**を入れる。

    記録を内側にそのまま持つのは、**検証を 1 本で済ませる**ため（design §1）。
    バンドル用の検証と記録用の検証が分かれると、片方だけ直す事故が起きる。
    """
    return {
        "schema": BUNDLE_SCHEMA,
        "target": target,
        "files": files,
        "rich_enabled": bool(rich_enabled),
        "review": review,
    }


def bundle_text(target, files, rich_enabled, review):
    """バンドル 1 ファイルの中身（文字列）。JS としても JSON としても読める。"""
    body = dumps_canonical(bundle_object(target, files, rich_enabled, review)).rstrip("\n")
    return BUNDLE_PREFIX + js_safe(body) + BUNDLE_SUFFIX


def parse_bundle(text):
    """バンドルの文字列から中身を取り出す。**JS は実行しない**。

    前後が合わなければその場で弾く。合わなければ JSON としても読めないので、
    「実行しないと読めない形」が紛れ込む余地が無い。
    """
    # 末尾の空白は許す（エディタが改行を足すことがある）。画面側 parseBundleText と同じ寛容さ。
    trimmed = text.rstrip()
    if not trimmed.startswith(BUNDLE_PREFIX) or not trimmed.endswith(";"):
        raise ValueError("バンドルの形ではありません（%s… で始まり ; で終わる必要があります）"
                         % BUNDLE_PREFIX.strip())
    return json.loads(trimmed[len(BUNDLE_PREFIX):-1])


def validate_bundle(bundle):
    """バンドルの構造を検査する。内側の記録は既存の `validate()` へ委譲する。"""
    problems = []
    if not isinstance(bundle, dict):
        return ["$: オブジェクトではありません"]
    if bundle.get("schema") != BUNDLE_SCHEMA:
        problems.append("$.schema: 既知のバンドルではありません（期待: %s、実際: %r）"
                        % (BUNDLE_SCHEMA, bundle.get("schema")))
    if not isinstance(bundle.get("target"), dict):
        problems.append("$.target: オブジェクトが必要です")
    if not isinstance(bundle.get("files"), list):
        problems.append("$.files: 配列が必要です")
    review = bundle.get("review")
    if review is not None:
        problems.extend("$.review%s" % p[1:] for p in validate(migrate(review)))
    return problems


def load_bundle(path):
    """バンドルを読む（実行しない）。内側の記録は `migrate` を通す。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            bundle = parse_bundle(f.read())
    except OSError as exc:
        die("読み込めません: %s" % exc, EXIT_USAGE)
    except (ValueError, json.JSONDecodeError) as exc:
        die("バンドルとして読めません（%s）: %s" % (path, exc), EXIT_INVALID)
    if bundle.get("review") is not None:
        bundle["review"] = migrate(bundle["review"])
    return bundle


def looks_like_bundle(text):
    """中身で判別する（拡張子に頼らない——名前を変えられても動く）。"""
    return text.lstrip().startswith(BUNDLE_PREFIX)


def write_out(text, out_path=None):
    """LF 固定・UTF-8 固定で書く。Windows の text mode 既定（CRLF）に任せない。"""
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


def die(message, code):
    sys.stderr.write(message.rstrip("\n") + "\n")
    raise SystemExit(code)


# --------------------------------------------------------------------------
# git の呼び出しと差分の構造化（T1）
# --------------------------------------------------------------------------

def git_bytes(repo, args, stdin=None):
    """git を呼んで stdout を bytes で返す。

    出力をバイト列で受けて自前で UTF-8 デコードするのは、コンソールのコードページ
    （Windows の cp932 等）に結果を左右されないため。
    """
    cmd = ["git", "-C", str(repo), "-c", "core.quotepath=false"] + list(args)
    try:
        proc = subprocess.run(cmd, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        die("git が見つかりません（PATH を確認してください）", EXIT_GIT)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").rstrip()
        die("git %s に失敗しました:\n%s" % (" ".join(args), detail), EXIT_GIT)
    return proc.stdout


def diff_args(source, rev):
    """差分の指定を git の引数に落とす。"""
    if source == "staged":
        return ["diff", "--cached"]
    if source == "range":
        return ["diff", rev]
    if source == "commit":
        return ["diff", rev + "~1", rev]
    return ["diff"]


def resolve_commit_args(repo, source, rev):
    """--commit が最初のコミットを指しているときは、親の代わりに空ツリーを使う。"""
    if source != "commit":
        return diff_args(source, rev)
    cmd = ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", rev + "~1"]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode != 0:
        return ["diff", EMPTY_TREE, rev]
    return diff_args(source, rev)


def parse_raw_z(data):
    """`git diff --raw -z` を読む。返り値は出力順のリスト。

    1 件は「:<oldmode> <newmode> <oldsha> <newsha> <status>」＋ NUL ＋ パス（R/C は 2 本）。
    パスをここから取るのは、本文の "diff --git a/… b/…" 行が空白を含むパスで
    曖昧になるため（-z なら区切りが NUL なので曖昧さが無い）。
    """
    fields = data.decode("utf-8", "replace").split("\0")
    entries = []
    i = 0
    while i < len(fields):
        head = fields[i]
        if not head.startswith(":"):
            i += 1
            continue
        parts = head[1:].split(" ")
        if len(parts) < 5:
            i += 1
            continue
        status = parts[4]
        old_blob, new_blob = parts[2], parts[3]
        if status and status[0] in ("R", "C"):
            old_path = fields[i + 1] if i + 1 < len(fields) else ""
            path = fields[i + 2] if i + 2 < len(fields) else ""
            i += 3
        else:
            old_path = None
            path = fields[i + 1] if i + 1 < len(fields) else ""
            i += 2
        entries.append({
            "path": path,
            "old_path": old_path,
            "status": status,
            "old_blob": old_blob,
            "new_blob": new_blob,
        })
    return entries


def parse_numstat_z(data):
    """`git diff --numstat -z` を読み、パス → (追加, 削除) を返す。

    リネームは「追加 TAB 削除 NUL 旧パス NUL 新パス」の形で出る。
    バイナリは追加・削除が "-" になるので None を入れる。
    """
    fields = data.decode("utf-8", "replace").split("\0")
    stats = {}
    i = 0
    while i < len(fields):
        head = fields[i]
        if not head or "\t" not in head:
            i += 1
            continue
        add, dele, rest = head.split("\t", 2)
        if rest == "":
            # リネーム / コピー: 次の 2 フィールドが旧パスと新パス
            path = fields[i + 2] if i + 2 < len(fields) else ""
            i += 3
        else:
            path = rest
            i += 1
        stats[path] = (
            None if add == "-" else int(add),
            None if dele == "-" else int(dele),
        )
    return stats


def split_body(body):
    """差分本文を「diff --git」の行でファイル単位のブロックに割る。

    ブロックの順序は --raw -z の順序と一致するので、パスは raw 側の値を使う
    （本文のヘッダ行からパスを推測しない）。
    """
    blocks = []
    current = None
    for line in body.split("\n"):
        if line.startswith("diff --git "):
            if current is not None:
                blocks.append(current)
            current = []
        if current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return blocks


def parse_hunks(lines):
    """1 ファイル分のブロックからハンクを取り出す。

    - "---" / "+++" のファイルヘッダ行は行分類に混ぜない（行頭 1 文字で分けると取り違える）。
    - "\\ No newline at end of file" は直前の行の属性として持つ（独立した行として出さない）。
    - 行末の CR（core.autocrlf 環境）は削らない。削ると差分の事実が変わる。
    """
    hunks = []
    binary = False
    current = None
    old_no = new_no = 0
    for line in lines:
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            binary = True
            continue
        if line.startswith("@@"):
            header = line
            old_no, new_no = parse_hunk_header(header)
            current = {"header": header, "old_start": old_no, "new_start": new_no, "lines": []}
            hunks.append(current)
            continue
        if current is None:
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if line.startswith("\\"):
            if current["lines"]:
                current["lines"][-1]["no_newline"] = True
            continue
        if line.startswith("+"):
            current["lines"].append({"kind": "add", "old": None, "new": new_no, "text": line[1:]})
            new_no += 1
        elif line.startswith("-"):
            current["lines"].append({"kind": "del", "old": old_no, "new": None, "text": line[1:]})
            old_no += 1
        elif line.startswith(" ") or line == "":
            # 文脈行。末尾の空行（本文末の改行由来）は行として数えない。
            if line == "":
                continue
            current["lines"].append({"kind": "ctx", "old": old_no, "new": new_no, "text": line[1:]})
            old_no += 1
            new_no += 1
    return hunks, binary


def parse_hunk_header(header):
    """@@ -12,7 +12,9 @@ …  から開始行番号を取る。"""
    try:
        body = header.split("@@")[1].strip()
        old_part, new_part = body.split(" ")[0], body.split(" ")[1]
        old_start = int(old_part[1:].split(",")[0])
        new_start = int(new_part[1:].split(",")[0])
        return old_start, new_start
    except (IndexError, ValueError):
        # 黙って (0, 0) を返すと行番号が静かに 0 始まりになり、コメントの位置がずれる。
        # 読めないハンクヘッダは git 側の異常なので、原因を見せて止める。
        die("ハンクヘッダを解釈できません: %s" % header, EXIT_GIT)


def git_try(repo, args):
    """失敗を許す git 呼び出し（ファイルが片側に無い場合など）。無ければ None。"""
    cmd = ["git", "-C", str(repo), "-c", "core.quotepath=false"] + list(args)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if proc.returncode != 0:
        return None
    return proc.stdout


def side_bytes(repo, source, rev, entry, side):
    """その側のファイル全文をバイト列で取る（T1）。無ければ None。

    どの版を見るかは差分の指定で変わる:
      unstaged … 旧=HEAD / 新=作業ツリー、staged … 旧=HEAD / 新=index、
      range・commit … 旧=A / 新=B。リネームは旧側のパスが違う。
    """
    path = entry["old_path"] if (side == "old" and entry.get("old_path")) else entry["path"]
    status = (entry.get("status") or "")[:1]
    if side == "old" and status == "A":
        return None
    if side == "new" and status == "D":
        return None

    if source == "range" and rev:
        base, _, head = rev.partition("..")
        base = base or "HEAD"
        head = head or "HEAD"
        return git_try(repo, ["show", "%s:%s" % (base if side == "old" else head, path)])
    if source == "commit" and rev:
        spec = ("%s~1" % rev) if side == "old" else rev
        out = git_try(repo, ["show", "%s:%s" % (spec, path)])
        if out is None and side == "old":
            return None
        return out
    if side == "old":
        return git_try(repo, ["show", "HEAD:%s" % path])
    if source == "staged":
        return git_try(repo, ["show", ":%s" % path])
    try:
        with open(Path(repo) / path, "rb") as f:
            return f.read()
    except OSError:
        return None


def as_text(data):
    """バイト列をテキストに。NUL を含むならバイナリとみなして None を返す。"""
    if data is None or b"\x00" in data:
        return None
    return data.decode("utf-8", "replace")


def split_lines(text):
    """行に切る（末尾の改行で空行を増やさない）。"""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def build_expand(text, lang, max_lines):
    """展開データ（T3）。上限を超えるファイルは中身を持たず truncated にする。"""
    if text is None or max_lines <= 0:
        return None
    lines = split_lines(text)
    if len(lines) > max_lines:
        return {"truncated": True, "count": len(lines)}
    tokens = highlight.tokenize_lines(text, lang) if lang else None
    if tokens is not None:
        tokens = tokens[:len(lines)]
        return {"truncated": False, "count": len(lines), "tokens": tokens}
    return {"truncated": False, "count": len(lines), "lines": lines}


def attach_tokens(hunks, tok_old, tok_new, covered_side=None):
    """差分行にトークンを付ける（T2）。

    **展開データが同じ側の全文トークンを持っているなら、その側の行には付けない**——
    画面が行番号で引けるので、付けると同じ配列を 2 回運ぶことになる（生成物がその分重くなる）。
    """
    for hunk in hunks:
        for line in hunk["lines"]:
            side = "old" if line["kind"] == "del" else "new"
            if side == covered_side:
                continue
            source_tokens = tok_old if side == "old" else tok_new
            number = line["old"] if side == "old" else line["new"]
            if not source_tokens or not number or number > len(source_tokens):
                continue
            line["tokens"] = source_tokens[number - 1]


def collect_diff(repo, source, rev, context, expand_max_lines=DEFAULT_EXPAND_MAX_LINES, rich=True):
    """差分を取り、構造化したファイル一覧と identity を返す（T1 / T2）。"""
    args = resolve_commit_args(repo, source, rev)
    body_bytes = git_bytes(repo, args[:1] + ["--no-color", "--no-ext-diff", "-U%d" % context] + args[1:])
    raw = parse_raw_z(git_bytes(repo, args[:1] + ["--no-color", "--no-ext-diff", "--raw", "-z"] + args[1:]))
    stats = parse_numstat_z(git_bytes(repo, args[:1] + ["--numstat", "-z"] + args[1:]))

    body = body_bytes.decode("utf-8", "replace")
    blocks = split_body(body)

    files = []
    for index, entry in enumerate(raw):
        lines = blocks[index] if index < len(blocks) else []
        hunks, binary = parse_hunks(lines)
        add, dele = stats.get(entry["path"], (0, 0))
        if add is None or dele is None:
            binary = True
            add, dele = 0, 0

        # バイナリでも rich の対象（PDF）なら中身が要る。それ以外のバイナリは触らない。
        wants_bytes = (not binary) or (richdiff.rich_kind(entry["path"]) is not None)
        old_bytes = side_bytes(repo, source, rev, entry, "old") if wants_bytes else None
        new_bytes = side_bytes(repo, source, rev, entry, "new") if wants_bytes else None
        old_text = as_text(old_bytes)
        new_text = as_text(new_bytes)
        if not binary and old_bytes is not None and old_text is None:
            binary = True
        if not binary and new_bytes is not None and new_text is None:
            binary = True

        language = None if binary else highlight.language_for(entry["path"])
        expand_side = "new" if new_text is not None else ("old" if old_text is not None else None)
        expand_text = new_text if expand_side == "new" else old_text
        expand = None
        if not binary and expand_side:
            expand = build_expand(expand_text, language, expand_max_lines)
            if expand:
                expand["side"] = expand_side

        if not binary and language:
            tok_old = highlight.tokenize_lines(old_text, language) if old_text is not None else None
            tok_new = highlight.tokenize_lines(new_text, language) if new_text is not None else None
            covered = expand_side if (expand and expand.get("tokens")) else None
            attach_tokens(hunks, tok_old, tok_new, covered)

        rich_payload = None
        if rich:
            rich_payload = richdiff.build(entry["path"], old_text, new_text, old_bytes, new_bytes)

        files.append({
            "path": entry["path"],
            "old_path": entry["old_path"],
            "status": entry["status"],
            "additions": add,
            "deletions": dele,
            "binary": binary,
            "language": language,
            "hunks": [] if binary else hunks,
            "expand": expand,
            "rich": rich_payload,
        })

    target = {
        "source": source,
        "range": rev if source in ("range", "commit") else None,
        "base_commit": head_commit(repo),
        "diff_digest": digest(repo, body_bytes),
        "files": [
            {
                "path": e["path"],
                "status": e["status"],
                "old_blob": e["old_blob"],
                "new_blob": e["new_blob"],
            }
            for e in raw
        ],
    }
    return target, files


def head_commit(repo):
    """HEAD の完全なコミット ID。まだコミットが無いリポジトリでは None。"""
    cmd = ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "HEAD"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip()


def digest(repo, body_bytes):
    """差分本文の同一性。git の hash-object を使うので、外部依存が増えない。

    git が使えない事態はそもそも差分が取れない事態なので、フォールバックは要らない。
    """
    out = git_bytes(repo, ["hash-object", "--stdin"], stdin=body_bytes)
    return out.decode("ascii", "replace").strip()



# --------------------------------------------------------------------------
# レビュー記録（JSON）
# --------------------------------------------------------------------------

def empty_review(target):
    return {"schema": SCHEMA, "target": target, "reviews": [], "threads": []}


# --------------------------------------------------------------------------
# 指摘できる位置（T1）
#
#   **画面 `templates/app.js` の `anchorOf` と同じ規則**。片方だけ直すと、
#   script が「書ける」と言った位置に画面が入れ物を用意しない——指摘が黙って
#   「位置不明」欄へ落ちる、という気づきにくい壊れ方をする。
#   test 工程で、ここが出す位置と画面が実際に出す位置の一致を検査している（research F3）。
# --------------------------------------------------------------------------

def anchor_of(line):
    """差分の 1 行が持つ位置 `(side, 行番号)`。持たない行は None。

    削除行            → LEFT ＋ 旧側の行番号
    追加行・文脈行    → RIGHT ＋ 新側の行番号
    旧側しか番号が無い文脈行（削除されたファイルの展開） → LEFT ＋ 旧側の行番号
    """
    if line.get("kind") == "del":
        old = line.get("old")
        return ("LEFT", old) if old is not None else None
    new = line.get("new")
    if new is not None:
        return ("RIGHT", new)
    old = line.get("old")
    if old is not None:
        return ("LEFT", old)
    return None


def valid_anchors(entry):
    """そのファイルで指摘できる `(side, 行番号)` の集合。

    ハンクに出ている行 ＋ **展開して出せる行**（展開データがあるとき）。
    展開行は文脈行なので、展開データと同じ側に番号が乗る。
    """
    out = set()
    for hunk in entry.get("hunks") or []:
        for line in hunk.get("lines") or []:
            anchor = anchor_of(line)
            if anchor:
                out.add(anchor)
    expand = entry.get("expand") or {}
    count = expand.get("count")
    if count and not expand.get("truncated"):
        side = "LEFT" if expand.get("side") == "old" else "RIGHT"
        for no in range(1, count + 1):
            out.add((side, no))
    return out


def resolve_side(anchors, line, side):
    """`--side` を省いたときにどちら側へ付けるか。

    片側しか無ければそれに決まる。**両側あるときは RIGHT**——置き換えられた行では
    両側が有効になり（実測 10/297）、そこで落とすと「書き換えた行に指摘できない」という
    いちばん困る形になる。推測ではなく**規約**として決める（GitHub の REST も既定は RIGHT）。
    """
    if side:
        return side
    if ("RIGHT", line) in anchors:
        return "RIGHT"
    if ("LEFT", line) in anchors:
        return "LEFT"
    return "RIGHT"          # どちらも無いときは既定のまま進め、呼び出し側が「無い」と報告する


def format_ranges(numbers):
    """行番号の集合を `1-40, 55, 60-62` の形に畳む。

    40 行のファイルで 40 個並べても読めない。手がかりは**読める形**でなければ意味がない。
    """
    numbers = sorted(numbers)
    if not numbers:
        return "なし"
    parts = []
    start = prev = numbers[0]
    for no in numbers[1:]:
        if no == prev + 1:
            prev = no
            continue
        parts.append("%d" % start if start == prev else "%d-%d" % (start, prev))
        start = prev = no
    parts.append("%d" % start if start == prev else "%d-%d" % (start, prev))
    return ", ".join(parts)


def path_problem(files, path):
    """そのファイルが差分に無ければ理由を返す。問題なければ None。

    打ち間違いが多いので、**差分にあるファイル名**を必ず添える。
    """
    known = sorted(entry["path"] for entry in files)
    if path in known:
        return None
    return ("%s はこの差分に含まれていません\n    差分にあるファイル: %s"
            % (path, ", ".join(known) if known else "なし"))


def anchor_problem(files, path, line, side):
    """位置が差分に無ければ、**手がかりつきの理由**を返す。問題なければ None。

    「駄目」だけでは直しようがないので、そのファイルで指摘できる位置を必ず添える。
    """
    trouble = path_problem(files, path)
    if trouble:
        return trouble
    by_path = {entry["path"]: entry for entry in files}
    entry = by_path[path]
    anchors = valid_anchors(entry)
    if (side, line) in anchors:
        return None
    rights = format_ranges(n for s, n in anchors if s == "RIGHT")
    lefts = format_ranges(n for s, n in anchors if s == "LEFT")
    detail = "%s:%d (%s) はこの差分に存在しません" % (path, line, side)
    if entry.get("binary"):
        return detail + "\n    このファイルはバイナリです（行ではなくファイル単位でコメントできます）"
    if (("RIGHT" if side == "LEFT" else "LEFT"), line) in anchors:
        detail += "\n    （%d 行目は反対の側にならあります。--side を付けてください）" % line
    return detail + "\n    このファイルで指摘できる位置: RIGHT %s / LEFT %s" % (rights, lefts)


def migrate(review):
    """`diff-review/1` を `/2` として扱えるようにする（読むだけ。書き出しは常に /2）。

    欠けている項目の既定値は `decisions.md` D8: kind は review、severity は None。
    """
    if not isinstance(review, dict):
        return review
    if review.get("schema") == SCHEMA_LEGACY:
        review = dict(review, schema=SCHEMA)
    for thread in review.get("threads") or []:
        if isinstance(thread, dict):
            thread.setdefault("kind", "review")
            for comment in thread.get("comments") or []:
                if isinstance(comment, dict):
                    comment.setdefault("severity", None)
    return review


def load_json(path):
    """読み込みは常に `migrate` を通す（`/1` も `/2` として扱えるようにする）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return migrate(json.load(f))
    except OSError as exc:
        die("読み込めません: %s" % exc, EXIT_USAGE)
    except json.JSONDecodeError as exc:
        die("JSON として読めません（%s 行 %d 列）: %s" % (path, exc.lineno, exc.colno), EXIT_INVALID)


def validate(review):
    """レビュー記録の構造を検査し、問題を「場所: 理由」の一覧で返す。

    黙って通すのが最悪なので、AI が書き損ねやすい点（値域・参照・重複）まで見る。
    """
    problems = []

    def bad(where, why):
        problems.append("%s: %s" % (where, why))

    if not isinstance(review, dict):
        return ["$: オブジェクトではありません"]
    if review.get("schema") not in SCHEMAS:
        bad("$.schema", "既知のスキーマではありません（期待: %s、実際: %r）"
            % ("/".join(SCHEMAS), review.get("schema")))

    target = review.get("target")
    if not isinstance(target, dict):
        bad("$.target", "オブジェクトが必要です")
    else:
        for key in ("source", "base_commit", "diff_digest", "files"):
            if key not in target:
                bad("$.target.%s" % key, "必須です")
        if "files" in target and not isinstance(target["files"], list):
            bad("$.target.files", "配列が必要です")

    review_ids = set()
    reviews = review.get("reviews")
    if not isinstance(reviews, list):
        bad("$.reviews", "配列が必要です")
        reviews = []
    for i, item in enumerate(reviews):
        where = "$.reviews[%d]" % i
        if not isinstance(item, dict):
            bad(where, "オブジェクトが必要です")
            continue
        rid = item.get("id")
        if not isinstance(rid, str) or not rid:
            bad(where + ".id", "空でない文字列が必要です")
        elif rid in review_ids:
            bad(where + ".id", "ID が重複しています（%s）" % rid)
        else:
            review_ids.add(rid)
        if item.get("state") not in REVIEW_STATES:
            bad(where + ".state", "%s のいずれかが必要です（実際: %r）" % ("/".join(REVIEW_STATES), item.get("state")))
        if not isinstance(item.get("body", ""), str):
            bad(where + ".body", "文字列が必要です")

    thread_ids = set()
    threads = review.get("threads")
    if not isinstance(threads, list):
        bad("$.threads", "配列が必要です")
        threads = []
    for i, thread in enumerate(threads):
        where = "$.threads[%d]" % i
        if not isinstance(thread, dict):
            bad(where, "オブジェクトが必要です")
            continue
        tid = thread.get("id")
        if not isinstance(tid, str) or not tid:
            bad(where + ".id", "空でない文字列が必要です")
        elif tid in thread_ids:
            bad(where + ".id", "ID が重複しています（%s）" % tid)
        else:
            thread_ids.add(tid)

        kind = thread.get("kind", "review")
        if kind not in THREAD_KINDS:
            bad(where + ".kind", "%s のいずれかが必要です（実際: %r）" % ("/".join(THREAD_KINDS), kind))

        path, line, side = thread.get("path"), thread.get("line"), thread.get("side")
        if path is not None and not isinstance(path, str):
            bad(where + ".path", "文字列か null が必要です")
        if line is not None and not isinstance(line, int):
            bad(where + ".line", "整数か null が必要です")
        if line is None and side is not None:
            bad(where + ".side", "line が null のときは side も null です")
        if line is not None:
            if path is None:
                bad(where + ".path", "line があるならファイルのパスが必要です")
            if side not in SIDES:
                bad(where + ".side", "%s のいずれかが必要です（実際: %r）" % ("/".join(SIDES), side))
        if not isinstance(thread.get("resolved", False), bool):
            bad(where + ".resolved", "真偽値が必要です")

        comments = thread.get("comments")
        if not isinstance(comments, list) or not comments:
            bad(where + ".comments", "1 件以上の配列が必要です")
            continue
        local_ids = set()
        for j, comment in enumerate(comments):
            cwhere = "%s.comments[%d]" % (where, j)
            if not isinstance(comment, dict):
                bad(cwhere, "オブジェクトが必要です")
                continue
            cid = comment.get("id")
            if not isinstance(cid, str) or not cid:
                bad(cwhere + ".id", "空でない文字列が必要です")
            elif cid in local_ids:
                bad(cwhere + ".id", "ID が重複しています（%s）" % cid)
            else:
                local_ids.add(cid)
            if not isinstance(comment.get("body"), str) or not comment.get("body").strip():
                bad(cwhere + ".body", "空でない本文が必要です")
            rid = comment.get("review_id")
            if rid is not None and rid not in review_ids:
                bad(cwhere + ".review_id", "存在しないレビューを指しています（%s）" % rid)
            if kind == "note" and rid is not None:
                bad(cwhere + ".review_id", "説明コメント（kind: note）は提出されないので review_id を持ちません")
            severity = comment.get("severity", None)
            if severity is not None and severity not in SEVERITIES:
                bad(cwhere + ".severity", "%s または null が必要です（実際: %r）"
                    % ("/".join(SEVERITIES), severity))
            if kind == "note" and severity is not None:
                bad(cwhere + ".severity", "説明コメント（kind: note）に重大度は付けません")
        for j, comment in enumerate(comments):
            if not isinstance(comment, dict):
                continue
            parent = comment.get("in_reply_to")
            if parent is not None and parent not in local_ids:
                bad("%s.comments[%d].in_reply_to" % (where, j),
                    "同じスレッドに無いコメントを指しています（%s）" % parent)
    return problems


def identity_mismatch(review, target):
    """記録が別の差分に対するものでないかを見る。ここでは判定するだけで、扱いは呼び出し側。"""
    recorded = review.get("target") or {}
    notes = []
    if recorded.get("base_commit") != target.get("base_commit"):
        notes.append("base_commit が違います（記録: %s / 現在: %s）"
                     % (recorded.get("base_commit"), target.get("base_commit")))
    if recorded.get("diff_digest") != target.get("diff_digest"):
        notes.append("差分の内容が変わっています（diff_digest が一致しません）")
    return notes


def iter_threads(review, unresolved_only=True, include_notes=False):
    """既定では「未解決の指摘」だけを返す。説明コメント（note）は明示しない限り出さない。"""
    for thread in review.get("threads") or []:
        if not include_notes and thread.get("kind", "review") == "note":
            continue
        if unresolved_only and thread.get("resolved"):
            continue
        yield thread


def thread_severity(thread):
    """スレッドの重大度は、含まれるコメントの中で最も重いもの（無ければ None）。"""
    order = {"must": 3, "should": 2, "nit": 1}
    best = None
    for comment in thread.get("comments") or []:
        sev = comment.get("severity")
        if sev in order and (best is None or order[sev] > order[best]):
            best = sev
    return best


def location_of(thread):
    path = thread.get("path")
    line = thread.get("line")
    if path is None:
        return "(全体)"
    if line is None:
        return path
    return "%s:%d" % (path, line)


# --------------------------------------------------------------------------
# サブコマンド
# --------------------------------------------------------------------------

def read_template(name):
    path = TEMPLATE_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        die("テンプレートが読めません: %s" % exc, EXIT_USAGE)


RW_BLOCK_RE = re.compile(r"[ \t]*<!-- rw:begin -->.*?<!-- rw:end -->[ \t]*\n?", re.S)
RW_MARK_RE = re.compile(r"[ \t]*<!-- rw:(?:begin|end) -->[ \t]*\n?")


def strip_write_ui(page, readonly):
    """`rw:` の印を処理する。

    - 参照専用: 印で囲まれた**中身ごと**落とす。隠すだけだと開発者ツールで戻せてしまうので、
      配布物として「読むだけ」を名乗るなら出力に入れない。
    - 通常: **印そのものだけ**落とす。生成物に組み立て用の印を残さない。
    """
    return (RW_BLOCK_RE if readonly else RW_MARK_RE).sub("", page)


def render_html(target, files, review, title, readonly=False, force_rich=False):
    # **プレースホルダ置換より前に**印を処理する。素のテンプレートに対して印を探すので、
    # 差分の中に "<!-- rw:begin -->" という文字列があっても影響しない。
    page = read_template("page.html")
    page = strip_write_ui(page, readonly)
    style = read_template("style.css")
    app = read_template("app.js")
    # ui.js は rich.js と違って**常に**積む。ペイン・テーマ・設定の記憶は差分の中身に依らない。
    ui = read_template("ui.js")
    # rich の描画コードは**対象があるときだけ**積む（decisions.md D4）。
    # 解析は生成時に済ませてあるので、画面側に積むのは「構造を描く」数十行だけ。
    # ビューア（`view`）は何を開くか事前に分からないので、rich を**常に**積む（research.md F5）。
    has_rich = force_rich or any(f.get("rich") for f in files)
    rich_js = read_template("rich.js") if has_rich else ""
    for name, text in (("style.css", style), ("ui.js", ui), ("app.js", app), ("rich.js", rich_js)):
        if "</script" in text:
            die("テンプレート %s に '</script' が含まれています（埋め込むと壊れます）" % name, EXIT_USAGE)
    diff_data = {"target": target, "files": files, "rich_enabled": bool(has_rich),
                 "readonly": bool(readonly), "embedded": bool(files)}
    replacements = {
        "__TITLE__": title,
        "__STYLE__": style,
        "__UI_JS__": ui,
        "__APP_JS__": app,
        "__RICH_JS__": rich_js,
        "__DIFF_DATA__": json_for_script_block(diff_data),
        "__REVIEW_DATA__": json_for_script_block(review) if review is not None else "null",
    }
    # **1 回の走査ですべて置き換える**。`str.replace` を順に掛けると、先に差し込んだ中身を
    # 次の置換が書き換えてしまう——差分に `__REVIEW_DATA__` のような文字列が含まれていると
    # （このテンプレート自身の差分をレビューすると必ず起きる）、埋め込んだ JSON の途中に
    # 別の JSON が挿し込まれて壊れる。置換後の文字列は再走査しない。
    return PLACEHOLDER_RE.sub(lambda m: replacements[m.group(0)], page)


def cmd_html(args):
    target, files = collect_diff(args.repo, args.source, args.rev, args.context,
                                 expand_max_lines=args.expand_max_lines, rich=(args.rich != "off"))
    review = load_review_for_embedding(args.import_path, target) if args.import_path else None
    title = args.title or default_title(target)
    write_out(render_html(target, files, review, title, readonly=args.readonly), args.out)
    return EXIT_OK


def load_review_for_embedding(path, target):
    """`--import` で渡された記録を読み、検証し、対象のずれを警告する（html / bundle で共用）。"""
    review = load_json(path)
    problems = validate(review)
    if problems:
        die("レビュー記録が不正です（埋め込みません）:\n"
            + "\n".join("  " + p for p in problems), EXIT_INVALID)
    for note in identity_mismatch(review, target):
        sys.stderr.write("警告: %s\n" % note)
    return review


def cmd_bundle(args):
    """差分と記録を 1 ファイルに（T3）。ビューアはこれを開く。"""
    target, files = collect_diff(args.repo, args.source, args.rev, args.context,
                                 expand_max_lines=args.expand_max_lines, rich=(args.rich != "off"))
    review = load_review_for_embedding(args.import_path, target) if args.import_path else None
    rich_enabled = any(f.get("rich") for f in files)
    write_out(bundle_text(target, files, rich_enabled, review), args.out)
    return EXIT_OK


def cmd_view(args):
    """差分を持たないビューアだけを出す（T4）。

    **どのバンドルも自動では読まない**（decisions.md D9）。ビューアがファイル名で特定の
    バンドルを指すと、配ったあと「このビューアはどれを見ているのか」がファイル名任せになり、
    決定的でなくなる。中身は開いたときに人が選ぶか、ホストが渡す。

    `rich.js` は**常に積む**——ビューアは何を開くか事前に分からないため
    （`html` の「対象が無ければ積まない」とは前提が違う。research.md F5）。
    """
    empty_target = {"source": "none", "range": None, "base_commit": None,
                    "diff_digest": None, "files": []}
    title = args.title or "差分レビュー（ビューア）"
    write_out(render_html(empty_target, [], None, title,
                          readonly=args.readonly, force_rich=True), args.out)
    return EXIT_OK


def default_title(target):
    source = target.get("source")
    if source == "staged":
        return "staged の差分"
    if source in ("range", "commit"):
        return "%s の差分" % target.get("range")
    return "未コミットの差分"


def cmd_template(args):
    target, _files = collect_diff(args.repo, args.source, args.rev, args.context,
                                  expand_max_lines=0, rich=False)
    write_out(dumps_canonical(empty_review(target)), args.out)
    return EXIT_OK


def read_record(path):
    """記録 JSON でもバンドルでも、**中の記録**を返す（拡張子ではなく中身で判別する）。

    返り値は (記録, ラベル)。バンドルに記録が入っていなければ空の記録を作って返す。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        die("読み込めません: %s" % exc, EXIT_USAGE)
    if not looks_like_bundle(text):
        return load_json(path), "レビュー記録"
    bundle = load_bundle(path)
    problems = validate_bundle(bundle)
    if problems:
        sys.stderr.write("NG %s（バンドル %d 件）\n" % (path, len(problems)))
        for problem in problems:
            sys.stderr.write("  %s\n" % problem)
        raise SystemExit(EXIT_INVALID)
    review = bundle.get("review")
    if review is None:
        review = empty_review(bundle.get("target") or {})
    return review, "バンドル"


def anchor_problems(review, files):
    """記録の中の全スレッドについて、位置が差分に実在するかを見る（T9）。"""
    problems = []
    for thread in review.get("threads") or []:
        path, line = thread.get("path"), thread.get("line")
        if path is None:
            continue                      # 差分全体へのコメントは位置を持たない
        if line is None:
            trouble = path_problem(files, path)      # ファイル単位でもパスは実在すべき
        else:
            trouble = anchor_problem(files, path, line, thread.get("side") or "RIGHT")
        if trouble:
            problems.append("threads[%s]: %s" % (thread.get("id"), trouble))
    return problems


def cmd_check(args):
    record = load_record(args.path)
    review, label = record.review, ("バンドル" if record.is_bundle else "レビュー記録")
    problems = validate(review)
    if args.repo_given:
        target, _files = collect_diff(args.repo, args.source, args.rev, args.context,
                                      expand_max_lines=0, rich=False)
        for note in identity_mismatch(review, target):
            sys.stderr.write("警告: %s\n" % note)
    if args.anchors:
        # 位置の実在まで見る。**既定では見ない**——既存の呼び出しの意味を変えないため。
        problems = problems + anchor_problems(review, diff_files_for(record, args))
    if problems:
        sys.stderr.write("NG %s（%d 件）\n" % (args.path, len(problems)))
        for problem in problems:
            sys.stderr.write("  %s\n" % problem)
        return EXIT_INVALID
    threads = review.get("threads") or []
    unresolved = sum(1 for t in threads if not t.get("resolved"))
    sys.stdout.write("OK %s［%s］（レビュー %d 件 / スレッド %d 件 / 未解決 %d 件）\n"
                     % (args.path, label, len(review.get("reviews") or []), len(threads), unresolved))
    return EXIT_OK


def cmd_list(args):
    review, _label = read_record(args.path)
    problems = validate(review)
    if problems:
        sys.stderr.write("NG %s（%d 件）: check サブコマンドで詳細を見てください\n" % (args.path, len(problems)))
        return EXIT_INVALID
    wanted = None
    if args.severity:
        wanted = set(x.strip() for x in args.severity.split(",") if x.strip())
    rows = []
    for thread in iter_threads(review, unresolved_only=not args.all, include_notes=args.notes):
        severity = thread_severity(thread)
        if wanted is not None:
            key = severity or "none"
            if key not in wanted:
                continue
        first = (thread.get("comments") or [{}])[0]
        rows.append({
            "location": location_of(thread),
            "state": "resolved" if thread.get("resolved") else "unresolved",
            "kind": thread.get("kind", "review"),
            "severity": severity or "-",
            "body": (first.get("body") or "").strip(),
            "replies": max(0, len(thread.get("comments") or []) - 1),
        })
    if args.format == "tsv":
        for row in rows:
            body = row["body"].replace("\t", " ").replace("\n", " ")
            write_out("%s\t%s\t%s\t%s\t%s\n"
                      % (row["location"], row["severity"], row["state"], row["kind"], body), None)
        return EXIT_OK
    if not rows:
        write_out("該当する指摘はありません\n", None)
        return EXIT_OK
    for row in rows:
        label = "[%s]" % row["severity"] if row["severity"] != "-" else "[重大度なし]"
        note = " ＜説明＞" if row["kind"] == "note" else ""
        write_out("- %s %s %s%s\n" % (row["location"], label, row["state"], note), None)
        for line in row["body"].split("\n"):
            write_out("    %s\n" % line, None)
        if row["replies"]:
            write_out("    （返信 %d 件）\n" % row["replies"], None)
    return EXIT_OK


# --------------------------------------------------------------------------
# 記録に書き足す（T3 / T4）
# --------------------------------------------------------------------------

def next_id(prefix, existing):
    """`t1` `t2` … の続きを採る。**入力が同じなら同じ id** になる（決定論）。"""
    biggest = 0
    for value in existing:
        text = str(value or "")
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            biggest = max(biggest, int(text[len(prefix):]))
    return "%s%d" % (prefix, biggest + 1)


def new_comment(review, thread, author, body, severity, in_reply_to):
    return {
        "id": next_id("c", [c.get("id") for c in thread.get("comments") or []]),
        "review_id": None,
        "author": author,
        "body": body,
        "severity": severity,
        "in_reply_to": in_reply_to,
    }


def new_thread(review, kind, path, line, side, author, body, severity):
    thread = {
        "id": next_id("t", [t.get("id") for t in review.get("threads") or []]),
        "kind": kind,
        "path": path,
        "line": line,
        "side": side,
        "start_line": None,
        "start_side": None,
        "resolved": False,
        "comments": [],
    }
    thread["comments"].append(new_comment(review, thread, author, body, severity, None))
    return thread


def find_thread(review, thread_id):
    for thread in review.get("threads") or []:
        if thread.get("id") == thread_id:
            return thread
    return None


class Record(object):
    """記録 JSON でもバンドルでも同じように触れるようにする入れ物（T4）。

    **入力が何だったかを覚えていて、同じ種類で書き戻す**。バンドルを渡したのに
    記録 JSON が返ると、後続の処理（ビューアへ渡す等）が繋がらない。
    """

    def __init__(self, path, review, bundle=None):
        self.path = path
        self.review = review
        self.bundle = bundle          # バンドルなら中身。記録 JSON なら None

    @property
    def is_bundle(self):
        return self.bundle is not None

    def files(self):
        """アンカー検証に使う差分。バンドルなら**自分の中にある**（git が要らない）。"""
        return self.bundle.get("files") if self.is_bundle else None

    def text(self):
        if self.is_bundle:
            merged = dict(self.bundle, review=self.review)
            return bundle_text(merged["target"], merged["files"],
                               merged.get("rich_enabled"), merged["review"])
        return dumps_canonical(self.review)


def load_record(path):
    """記録 JSON / バンドルのどちらでも読む。**中身で判別**する（拡張子に頼らない）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        die("読み込めません: %s" % exc, EXIT_USAGE)
    if looks_like_bundle(text):
        bundle = load_bundle(path)
        problems = validate_bundle(bundle)
        if problems:
            die("バンドルが不正です:\n" + "\n".join("  " + p for p in problems), EXIT_INVALID)
        review = bundle.get("review") or empty_review(bundle.get("target") or {})
        return Record(path, migrate(review), bundle)
    return Record(path, load_json(path), None)


def save_record(record, out):
    """**全部通ってから 1 回だけ**書く。書く前に必ず既存 validate() を通す。"""
    problems = validate(record.review)
    if problems:
        die("書き込みません（組み立てた記録が不正です）:\n"
            + "\n".join("  " + p for p in problems), EXIT_INVALID)
    if out == "-":
        write_out(record.text(), None)
    else:
        write_out(record.text(), out or record.path)


def diff_files_for(record, args):
    """アンカー検証に使う差分を用意する。

    バンドルなら中身をそのまま（research F6 で git と一致することを実測）。
    記録 JSON のときだけ git から取る。
    """
    files = record.files()
    if files is not None:
        return files
    if not getattr(args, "repo_given", False) and not getattr(args, "from_source", None):
        die("この記録には差分が入っていないので、位置を確かめられません。\n"
            "  --repo <リポジトリ> を付けるか、バンドル（%s）を渡してください" % BUNDLE_EXT,
            EXIT_USAGE)
    _target, files = collect_diff(args.repo, args.source, args.rev, args.context,
                                  expand_max_lines=args.expand_max_lines,
                                  rich=False)
    return files


# --------------------------------------------------------------------------
# comment / resolve / submit（T5〜T8）
# --------------------------------------------------------------------------

BATCH_KEYS = ("path", "line", "side", "body", "severity", "note", "reply_to", "author")


def read_body(text, path):
    """本文は引数・ファイル・標準入力のどれからでも受ける（長い本文を引数に押し込まない）。"""
    if text is not None and path is not None:
        die("--body と --body-file は同時に使えません", EXIT_USAGE)
    if path is not None:
        if path == "-":
            return sys.stdin.read()
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as exc:
            die("本文を読めません: %s" % exc, EXIT_USAGE)
    return text


def spec_problems(spec, record, files, index=None):
    """1 件ぶんの指定を検証し、問題の一覧を返す（**書く前に**全部見る）。"""
    where = "" if index is None else "[%d] " % (index + 1)
    problems = []

    unknown = sorted(set(spec) - set(BATCH_KEYS))
    if unknown:
        problems.append("%s知らないキー: %s（使えるのは %s）"
                        % (where, ", ".join(unknown), ", ".join(BATCH_KEYS)))

    body = spec.get("body")
    if not body or not str(body).strip():
        problems.append("%s本文が空です" % where)

    is_note = bool(spec.get("note"))
    severity = spec.get("severity")
    reply_to = spec.get("reply_to")

    if is_note and severity:
        problems.append("%s説明コメント（note）に重大度は付けられません" % where)
    if severity and severity not in SEVERITIES:
        problems.append("%s重大度は %s のいずれかです（実際: %r）"
                        % (where, " / ".join(SEVERITIES), severity))
    if reply_to and (spec.get("path") or spec.get("line") or spec.get("side")):
        problems.append("%s返信に位置は指定できません（位置はスレッドが持っています）" % where)

    if reply_to:
        thread_id = str(reply_to).split(":")[0]
        thread = find_thread(record.review, thread_id)
        if thread is None:
            known = [t.get("id") for t in record.review.get("threads") or []]
            problems.append("%sスレッド %s がありません（あるのは: %s）"
                            % (where, thread_id, ", ".join(known) if known else "なし"))
        elif ":" in str(reply_to):
            comment_id = str(reply_to).split(":", 1)[1]
            if not any(c.get("id") == comment_id for c in thread.get("comments") or []):
                problems.append("%sスレッド %s に %s というコメントはありません"
                                % (where, thread_id, comment_id))
        return problems

    line = spec.get("line")
    path = spec.get("path")
    if line is not None and not path:
        problems.append("%s--line を使うなら --path も要ります" % where)
    if path:
        # **行を指定しないファイル単位のコメントでも、そのファイルが差分にあるかは見る。**
        # 見ないと、差分に無いファイルへのコメントが素通りして画面で「位置不明」に落ちる
        # ——行の指定が無いだけで、穴としては同じ。
        if files is None:
            problems.append("%s位置を確かめる差分がありません" % where)
        elif line is None:
            trouble = path_problem(files, path)
            if trouble:
                problems.append("%s%s" % (where, trouble))
        else:
            anchors = valid_anchors(next((e for e in files if e["path"] == path), {}))
            side = resolve_side(anchors, line, spec.get("side"))
            trouble = anchor_problem(files, path, line, side)
            if trouble:
                problems.append("%s%s" % (where, trouble))
    return problems


def apply_spec(record, spec, files, default_author):
    """検証済みの 1 件を記録へ足す。**ここでは検証しない**（済んでいる前提）。"""
    author = spec.get("author") or default_author
    body = str(spec["body"])
    reply_to = spec.get("reply_to")
    if reply_to:
        thread_id = str(reply_to).split(":")[0]
        thread = find_thread(record.review, thread_id)
        comments = thread.get("comments") or []
        if ":" in str(reply_to):
            parent = str(reply_to).split(":", 1)[1]
        else:
            parent = comments[-1].get("id") if comments else None
        severity = None if thread.get("kind") == "note" else spec.get("severity")
        thread.setdefault("comments", []).append(
            new_comment(record.review, thread, author, body, severity, parent))
        return thread["id"]

    path = spec.get("path")
    line = spec.get("line")
    side = None
    if line is not None:
        anchors = valid_anchors(next((e for e in files if e["path"] == path), {}))
        side = resolve_side(anchors, line, spec.get("side"))
    kind = "note" if spec.get("note") else "review"
    severity = None if kind == "note" else spec.get("severity")
    thread = new_thread(record.review, kind, path, line, side, author, body, severity)
    record.review.setdefault("threads", []).append(thread)
    return thread["id"]


def load_batch(path):
    text = sys.stdin.read() if path == "-" else None
    if text is None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            die("--batch を読めません: %s" % exc, EXIT_USAGE)
    try:
        specs = json.loads(text)
    except json.JSONDecodeError as exc:
        die("--batch が JSON として読めません: %s" % exc, EXIT_INVALID)
    if not isinstance(specs, list):
        die("--batch は JSON の配列です（実際: %s）" % type(specs).__name__, EXIT_USAGE)
    return specs


def cmd_comment(args):
    record = load_record(args.path)
    if args.batch:
        specs = load_batch(args.batch)
        if not specs:
            die("--batch が空です", EXIT_USAGE)
    else:
        body = read_body(args.body, args.body_file)
        spec = {"body": body}
        for key, value in (("path", args.target_path), ("line", args.line), ("side", args.side),
                           ("severity", args.severity), ("reply_to", args.reply_to),
                           ("author", args.author)):
            if value is not None:
                spec[key] = value
        if args.note:
            spec["note"] = True
        specs = [spec]

    # 行だけでなく**パスの指定があるなら**差分が要る（ファイル単位も実在を見るため）
    needs_diff = any(s.get("path") for s in specs if isinstance(s, dict))
    files = diff_files_for(record, args) if needs_diff else (record.files() or [])

    # **全件を先に見る**。1 件でも駄目なら 1 件も書かない（research R2 / R5）。
    problems = []
    for index, spec in enumerate(specs):
        if not isinstance(spec, dict):
            problems.append("[%d] オブジェクトではありません" % (index + 1))
            continue
        problems.extend(spec_problems(spec, record, files,
                                      index if len(specs) > 1 else None))
    if problems:
        sys.stderr.write("NG（%d 件。何も書き込んでいません）\n" % len(problems))
        for problem in problems:
            sys.stderr.write("  %s\n" % problem)
        return EXIT_INVALID

    added = [apply_spec(record, spec, files, args.author or "ai") for spec in specs]
    save_record(record, args.out)
    sys.stderr.write("追加しました: %s\n" % ", ".join(added))
    return EXIT_OK


def cmd_resolve(args):
    record = load_record(args.path)
    thread = find_thread(record.review, args.thread)
    if thread is None:
        known = [t.get("id") for t in record.review.get("threads") or []]
        die("スレッド %s がありません（あるのは: %s）"
            % (args.thread, ", ".join(known) if known else "なし"), EXIT_INVALID)
    if thread.get("kind") == "note":
        die("説明コメント（note）は解決の対象ではありません: %s" % args.thread, EXIT_USAGE)
    thread["resolved"] = not args.undo
    save_record(record, args.out)
    sys.stderr.write("%s を%sにしました\n" % (args.thread, "未解決" if args.undo else "解決"))
    return EXIT_OK


def cmd_submit(args):
    record = load_record(args.path)
    review = record.review
    body = read_body(args.body, args.body_file) or ""
    review_id = next_id("r", [r.get("id") for r in review.get("reviews") or []])
    review.setdefault("reviews", []).append(
        {"id": review_id, "author": args.author or "ai", "state": args.state, "body": body})
    # 未提出の**指摘**だけを紐づける。説明（note）は提出の対象ではない（記録の規則）。
    attached = 0
    for thread in review.get("threads") or []:
        if thread.get("kind") == "note":
            continue
        for comment in thread.get("comments") or []:
            if comment.get("review_id") is None:
                comment["review_id"] = review_id
                attached += 1
    save_record(record, args.out)
    sys.stderr.write("%s として提出しました（%s / コメント %d 件）\n"
                     % (review_id, args.state, attached))
    return EXIT_OK


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

SOURCES = ("unstaged", "staged", "range", "commit", "github-pr")
SOURCES_NOT_YET = {"github-pr": "GitHub の PR からの取得はまだ実装していません"}


def add_source_options(parser, required_repo_flag=False):
    # 取得元は **--from ひとつの軸**。機能が増えてもフラグが増えない形にする。
    parser.add_argument("--from", dest="from_source", choices=SOURCES, metavar="<元>",
                        help="差分の取得元: %s（既定: unstaged）" % " | ".join(SOURCES))
    parser.add_argument("--rev", metavar="<SPEC>",
                        help="--from range / commit のときの指定（例 main..HEAD / 3d6624e）")
    # 以下は従来からのフラグ。**同じことを 2 通りで書けるので、併用は矛盾として弾く**。
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--unstaged", action="store_true", help="（別名）--from unstaged")
    group.add_argument("--staged", action="store_true", help="（別名）--from staged")
    group.add_argument("--range", dest="range_spec", metavar="<A>..<B>", help="（別名）--from range --rev <A>..<B>")
    group.add_argument("--commit", metavar="<C>", help="（別名）--from commit --rev <C>")
    parser.add_argument("--repo", default=".", help="対象リポジトリ（既定: カレント）")
    parser.add_argument("--context", type=int, default=3, help="前後に出す文脈行数（既定: 3）")
    parser.add_argument("--expand-max-lines", type=int, default=DEFAULT_EXPAND_MAX_LINES,
                        dest="expand_max_lines",
                        help="画面で前後を展開するために全文を埋める上限行数（既定: %d。0 で埋めない）"
                             % DEFAULT_EXPAND_MAX_LINES)
    parser.add_argument("--rich", choices=("auto", "off"), default="auto",
                        help="CSV/Markdown/HTML/PDF の rich diff（既定: auto。対象が無ければ自動で積まない）")


def normalize_source(args):
    """`--from` と従来フラグを 1 つの `(source, rev)` にまとめる。

    **両方が指定されたら落とす**——どちらかを黙って優先すると、
    「指定したはずの差分と違うものが出た」という気づきにくい事故になる。
    """
    legacy = None
    if getattr(args, "staged", False):
        legacy = ("staged", None)
    elif getattr(args, "range_spec", None):
        legacy = ("range", args.range_spec)
    elif getattr(args, "commit", None):
        legacy = ("commit", args.commit)
    elif getattr(args, "unstaged", False):
        legacy = ("unstaged", None)

    chosen = getattr(args, "from_source", None)
    rev = getattr(args, "rev", None)
    if chosen and legacy:
        die("--from と従来のフラグ（--unstaged / --staged / --range / --commit）は"
            "同時に指定できません。どちらか一方にしてください", EXIT_USAGE)
    if chosen:
        if chosen in SOURCES_NOT_YET:
            die("%s（--from %s）" % (SOURCES_NOT_YET[chosen], chosen), EXIT_USAGE)
        if chosen in ("range", "commit") and not rev:
            die("--from %s には --rev <SPEC> が要ります" % chosen, EXIT_USAGE)
        if chosen not in ("range", "commit") and rev:
            die("--rev は --from range / commit のときだけ使えます", EXIT_USAGE)
        args.source, args.rev = chosen, rev
        return args
    if rev and not legacy:
        die("--rev は --from range / commit と一緒に使ってください", EXIT_USAGE)
    args.source, args.rev = legacy or ("unstaged", None)
    return args


def build_parser():
    parser = argparse.ArgumentParser(
        prog="diff_review.py",
        description="git の差分をレビュー用の単一 HTML にし、レビュー記録 JSON を往復させる")
    sub = parser.add_subparsers(dest="command")

    p_html = sub.add_parser("html", help="差分から単一 HTML を作る")
    add_source_options(p_html)
    p_html.add_argument("--title", help="画面の見出し")
    p_html.add_argument("--import", dest="import_path", metavar="<review.json>",
                        help="既存のレビュー記録を埋め込む")
    p_html.add_argument("--readonly", action="store_true",
                        help="参照専用（コメント入力・提出・JSON 入出力の導線を積まない）")
    p_html.add_argument("--out", metavar="<FILE>", help="出力先（既定: 標準出力）")
    p_html.set_defaults(func=cmd_html)

    p_bundle = sub.add_parser("bundle", help="差分と指摘を 1 ファイル（%s）にまとめる" % BUNDLE_EXT)
    add_source_options(p_bundle)
    p_bundle.add_argument("--import", dest="import_path", metavar="<review.json>",
                          help="既存のレビュー記録を同梱する")
    p_bundle.add_argument("--out", metavar="<FILE>", help="出力先（既定: 標準出力）")
    p_bundle.set_defaults(func=cmd_bundle)

    p_view = sub.add_parser("view", help="差分を持たないビューアだけを出す")
    p_view.add_argument("--readonly", action="store_true",
                        help="参照専用（コメント入力・提出・JSON 入出力の導線を積まない）")
    p_view.add_argument("--title", help="画面の見出し")
    p_view.add_argument("--out", metavar="<FILE>", help="出力先（既定: 標準出力）")
    p_view.set_defaults(func=cmd_view)

    p_tmpl = sub.add_parser("template", help="空のレビュー記録（雛形）を出す")
    add_source_options(p_tmpl)
    p_tmpl.add_argument("--out", metavar="<FILE>", help="出力先（既定: 標準出力）")
    p_tmpl.set_defaults(func=cmd_template)

    p_check = sub.add_parser("check", help="レビュー記録 JSON / バンドルを検証する")
    p_check.add_argument("path", metavar="<review.json | bundle%s>" % BUNDLE_EXT)
    p_check.add_argument("--anchors", action="store_true",
                         help="指摘の位置が差分に実在するかも見る"
                              "（バンドルなら中の差分で。記録 JSON なら --repo が要る）")
    add_source_options(p_check)
    p_check.set_defaults(func=cmd_check)

    p_comment = sub.add_parser("comment", help="指摘 / 説明 / 返信を記録に足す")
    p_comment.add_argument("path", metavar="<review.json | bundle%s>" % BUNDLE_EXT)
    p_comment.add_argument("--path", dest="target_path", metavar="<FILE>",
                           help="指摘するファイル（省くと差分全体へのコメント）")
    p_comment.add_argument("--line", type=int, metavar="<N>",
                           help="指摘する行（省くとファイル単位のコメント）")
    p_comment.add_argument("--side", choices=SIDES,
                           help="LEFT=削除行 / RIGHT=追加・文脈行（省くと RIGHT を優先）")
    p_comment.add_argument("--body", metavar="<TEXT>", help="本文")
    p_comment.add_argument("--body-file", dest="body_file", metavar="<FILE|->",
                           help="本文をファイル（- で標準入力）から読む")
    p_comment.add_argument("--severity", choices=SEVERITIES, help="重大度（指摘のときだけ）")
    p_comment.add_argument("--note", action="store_true",
                           help="説明コメントにする（提出されず、未解決にも数えない）")
    p_comment.add_argument("--reply-to", dest="reply_to", metavar="<t1[:c1]>",
                           help="返信先。コメントを省くとそのスレッドの最後のコメントへ")
    p_comment.add_argument("--author", metavar="<NAME>", help="書き手（既定: ai）")
    p_comment.add_argument("--batch", metavar="<FILE|->",
                           help="まとめて足す（JSON の配列。1 件でも駄目なら 1 件も書かない）")
    p_comment.add_argument("--out", metavar="<FILE|->",
                           help="出力先（既定: 入力を上書き。- で標準出力）")
    add_source_options(p_comment)
    p_comment.set_defaults(func=cmd_comment)

    p_resolve = sub.add_parser("resolve", help="スレッドを解決 / 未解決にする")
    p_resolve.add_argument("path", metavar="<review.json | bundle%s>" % BUNDLE_EXT)
    p_resolve.add_argument("--thread", required=True, metavar="<t1>")
    p_resolve.add_argument("--undo", action="store_true", help="未解決に戻す")
    p_resolve.add_argument("--out", metavar="<FILE|->", help="出力先（既定: 入力を上書き）")
    p_resolve.set_defaults(func=cmd_resolve)

    p_submit = sub.add_parser("submit", help="判定とサマリを足し、未提出の指摘を紐づける")
    p_submit.add_argument("path", metavar="<review.json | bundle%s>" % BUNDLE_EXT)
    p_submit.add_argument("--state", required=True, choices=REVIEW_STATES)
    p_submit.add_argument("--body", metavar="<TEXT>", help="サマリ")
    p_submit.add_argument("--body-file", dest="body_file", metavar="<FILE|->",
                          help="サマリをファイル（- で標準入力）から読む")
    p_submit.add_argument("--author", metavar="<NAME>", help="書き手（既定: ai）")
    p_submit.add_argument("--out", metavar="<FILE|->", help="出力先（既定: 入力を上書き）")
    p_submit.set_defaults(func=cmd_submit)

    p_list = sub.add_parser("list", help="未解決の指摘を一覧にする（記録でもバンドルでも）")
    p_list.add_argument("path", metavar="<review.json | bundle%s>" % BUNDLE_EXT)
    p_list.add_argument("--all", action="store_true", help="解決済みも出す")
    p_list.add_argument("--severity", metavar="must,should,nit,none",
                        help="重大度で絞る（カンマ区切り。none は重大度なし）")
    p_list.add_argument("--notes", action="store_true", help="説明コメント（kind: note）も出す")
    p_list.add_argument("--format", choices=("text", "tsv"), default="text")
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv=None):
    # 標準出力も LF・UTF-8 に固定する（Windows の既定に任せると出力が OS で変わる）。
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - 3.7 未満
        pass

    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_USAGE
    if hasattr(args, "unstaged"):
        normalize_source(args)
    # check は --repo を明示したときだけ identity を突き合わせる
    args.repo_given = any(a == "--repo" or a.startswith("--repo=") for a in argv)
    try:
        return args.func(args)
    except SystemExit as exc:  # die() からの離脱をそのまま終了コードにする
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
