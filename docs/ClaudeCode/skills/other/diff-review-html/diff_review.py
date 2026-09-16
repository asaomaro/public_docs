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


def render_html(target, files, review, title):
    page = read_template("page.html")
    style = read_template("style.css")
    app = read_template("app.js")
    # ui.js は rich.js と違って**常に**積む。ペイン・テーマ・設定の記憶は差分の中身に依らない。
    ui = read_template("ui.js")
    # rich の描画コードは**対象があるときだけ**積む（decisions.md D4）。
    # 解析は生成時に済ませてあるので、画面側に積むのは「構造を描く」数十行だけ。
    has_rich = any(f.get("rich") for f in files)
    rich_js = read_template("rich.js") if has_rich else ""
    for name, text in (("style.css", style), ("ui.js", ui), ("app.js", app), ("rich.js", rich_js)):
        if "</script" in text:
            die("テンプレート %s に '</script' が含まれています（埋め込むと壊れます）" % name, EXIT_USAGE)
    diff_data = {"target": target, "files": files, "rich_enabled": bool(has_rich)}
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
    review = None
    if args.import_path:
        review = load_json(args.import_path)
        problems = validate(review)
        if problems:
            die("レビュー記録が不正です（埋め込みません）:\n" + "\n".join("  " + p for p in problems), EXIT_INVALID)
        for note in identity_mismatch(review, target):
            sys.stderr.write("警告: %s\n" % note)
    title = args.title or default_title(target)
    write_out(render_html(target, files, review, title), args.out)
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


def cmd_check(args):
    review = load_json(args.path)
    problems = validate(review)
    if args.repo_given:
        target, _files = collect_diff(args.repo, args.source, args.rev, args.context,
                                      expand_max_lines=0, rich=False)
        for note in identity_mismatch(review, target):
            sys.stderr.write("警告: %s\n" % note)
    if problems:
        sys.stderr.write("NG %s（%d 件）\n" % (args.path, len(problems)))
        for problem in problems:
            sys.stderr.write("  %s\n" % problem)
        return EXIT_INVALID
    threads = review.get("threads") or []
    unresolved = sum(1 for t in threads if not t.get("resolved"))
    sys.stdout.write("OK %s（レビュー %d 件 / スレッド %d 件 / 未解決 %d 件）\n"
                     % (args.path, len(review.get("reviews") or []), len(threads), unresolved))
    return EXIT_OK


def cmd_list(args):
    review = load_json(args.path)
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
# 入口
# --------------------------------------------------------------------------

def add_source_options(parser, required_repo_flag=False):
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--unstaged", action="store_true", help="未ステージの変更（既定）")
    group.add_argument("--staged", action="store_true", help="ステージ済みの変更")
    group.add_argument("--range", dest="range_spec", metavar="<A>..<B>", help="コミット間の差分")
    group.add_argument("--commit", metavar="<C>", help="そのコミットが入れた差分")
    parser.add_argument("--repo", default=".", help="対象リポジトリ（既定: カレント）")
    parser.add_argument("--context", type=int, default=3, help="前後に出す文脈行数（既定: 3）")
    parser.add_argument("--expand-max-lines", type=int, default=DEFAULT_EXPAND_MAX_LINES,
                        dest="expand_max_lines",
                        help="画面で前後を展開するために全文を埋める上限行数（既定: %d。0 で埋めない）"
                             % DEFAULT_EXPAND_MAX_LINES)
    parser.add_argument("--rich", choices=("auto", "off"), default="auto",
                        help="CSV/Markdown/HTML/PDF の rich diff（既定: auto。対象が無ければ自動で積まない）")


def normalize_source(args):
    if args.staged:
        args.source, args.rev = "staged", None
    elif args.range_spec:
        args.source, args.rev = "range", args.range_spec
    elif args.commit:
        args.source, args.rev = "commit", args.commit
    else:
        args.source, args.rev = "unstaged", None
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
    p_html.add_argument("--out", metavar="<FILE>", help="出力先（既定: 標準出力）")
    p_html.set_defaults(func=cmd_html)

    p_tmpl = sub.add_parser("template", help="空のレビュー記録（雛形）を出す")
    add_source_options(p_tmpl)
    p_tmpl.add_argument("--out", metavar="<FILE>", help="出力先（既定: 標準出力）")
    p_tmpl.set_defaults(func=cmd_template)

    p_check = sub.add_parser("check", help="レビュー記録 JSON を検証する")
    p_check.add_argument("path", metavar="<review.json>")
    add_source_options(p_check)
    p_check.set_defaults(func=cmd_check)

    p_list = sub.add_parser("list", help="未解決の指摘を一覧にする")
    p_list.add_argument("path", metavar="<review.json>")
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
