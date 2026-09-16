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

SCHEMA = "diff-review/1"

# テンプレートの差し込み口。`render_html` はこの 5 つを 1 回の走査で置き換える。
PLACEHOLDER_RE = re.compile(r"__(?:TITLE|STYLE|APP_JS|DIFF_DATA|REVIEW_DATA)__")
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# git が「空のツリー」に与えている固定のハッシュ。最初のコミットの差分を取るときに親の代わりに使う。
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_GIT = 2
EXIT_INVALID = 3

REVIEW_STATES = ("APPROVED", "CHANGES_REQUESTED", "COMMENTED")
SIDES = ("LEFT", "RIGHT")


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


def collect_diff(repo, source, rev, context):
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
        files.append({
            "path": entry["path"],
            "old_path": entry["old_path"],
            "status": entry["status"],
            "additions": add,
            "deletions": dele,
            "binary": binary,
            "hunks": [] if binary else hunks,
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


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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
    if review.get("schema") != SCHEMA:
        bad("$.schema", "既知のスキーマではありません（期待: %r、実際: %r）" % (SCHEMA, review.get("schema")))

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


def iter_threads(review, unresolved_only=True):
    threads = review.get("threads") or []
    for thread in threads:
        if unresolved_only and thread.get("resolved"):
            continue
        yield thread


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
    for name, text in (("style.css", style), ("app.js", app)):
        if "</script" in text:
            die("テンプレート %s に '</script' が含まれています（埋め込むと壊れます）" % name, EXIT_USAGE)
    diff_data = {"target": target, "files": files}
    replacements = {
        "__TITLE__": title,
        "__STYLE__": style,
        "__APP_JS__": app,
        "__DIFF_DATA__": json_for_script_block(diff_data),
        "__REVIEW_DATA__": json_for_script_block(review) if review is not None else "null",
    }
    # **1 回の走査ですべて置き換える**。`str.replace` を順に掛けると、先に差し込んだ中身を
    # 次の置換が書き換えてしまう——差分に `__REVIEW_DATA__` のような文字列が含まれていると
    # （このテンプレート自身の差分をレビューすると必ず起きる）、埋め込んだ JSON の途中に
    # 別の JSON が挿し込まれて壊れる。置換後の文字列は再走査しない。
    return PLACEHOLDER_RE.sub(lambda m: replacements[m.group(0)], page)


def cmd_html(args):
    target, files = collect_diff(args.repo, args.source, args.rev, args.context)
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
    target, _files = collect_diff(args.repo, args.source, args.rev, args.context)
    write_out(dumps_canonical(empty_review(target)), args.out)
    return EXIT_OK


def cmd_check(args):
    review = load_json(args.path)
    problems = validate(review)
    if args.repo_given:
        target, _files = collect_diff(args.repo, args.source, args.rev, args.context)
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
    rows = []
    for thread in iter_threads(review, unresolved_only=not args.all):
        first = (thread.get("comments") or [{}])[0]
        rows.append({
            "location": location_of(thread),
            "state": "resolved" if thread.get("resolved") else "unresolved",
            "body": (first.get("body") or "").strip(),
            "replies": max(0, len(thread.get("comments") or []) - 1),
        })
    if args.format == "tsv":
        for row in rows:
            body = row["body"].replace("\t", " ").replace("\n", " ")
            write_out("%s\t%s\t%s\n" % (row["location"], row["state"], body), None)
        return EXIT_OK
    if not rows:
        write_out("未解決の指摘はありません\n", None)
        return EXIT_OK
    for row in rows:
        write_out("- %s [%s]\n" % (row["location"], row["state"]), None)
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
