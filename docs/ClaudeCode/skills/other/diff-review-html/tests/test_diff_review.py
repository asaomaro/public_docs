"""diff_review.py のテスト（標準ライブラリのみ）。

    cd <skill>/tests && python3 -m unittest -v
    もしくは  python3 -m unittest discover -s <skill>/tests

画面（HTML）側の受け入れ確認はここでは行わない——ブラウザが要るため、別途 headless ブラウザで行う。
ここが見るのは script の責務: 差分のパース、決定論、エスケープ、検証、一覧、符号化と改行。
"""

import email.message
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
# 隣の補助モジュールも、**どの起動の仕方でも**読めるようにする
# （`discover -s tests` は自動で通すが、`python3 -m unittest tests.…` は通さない）。
sys.path.insert(0, str(TESTS_DIR))

import diff_review as dr  # noqa: E402  （パスを通してから読み込む）
import richdiff      # noqa: E402
import fixture_repo  # noqa: E402  （画面の受け入れ確認に使う固定入力を作る）

SCRIPT = SKILL_DIR / "diff_review.py"


def run_git(repo, *args):
    subprocess.run(["git", "-C", str(repo)] + list(args), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_repo(tmp):
    """テスト用のリポジトリ。日本語・空白入りのパスと、あとで足すバイナリを含む。"""
    repo = Path(tmp)
    run_git(repo, "init", "-q", ".")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "test")
    (repo / "plain.txt").write_text("a\nb\nc\n", encoding="utf-8")
    (repo / "日本 語.txt").write_text("x\n", encoding="utf-8")
    (repo / "bin.dat").write_bytes(b"\x00\x01\x02")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-qm", "init")
    # 未ステージの変更を作る
    (repo / "plain.txt").write_text('a\nB<script>alert(1)</script>\nc\nd\n', encoding="utf-8")
    (repo / "日本 語.txt").write_text("x\ny\n", encoding="utf-8")
    (repo / "bin.dat").write_bytes(b"\x00\x09")
    return repo


def make_rich_repo(tmp):
    """rich diff とハイライトと展開を見るためのリポジトリ。"""
    repo = Path(tmp)
    run_git(repo, "init", "-q", ".")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "test")
    (repo / "data.csv").write_text("id,name,qty\n1,りんご,3\n2,みかん,5\n", encoding="utf-8")
    (repo / "doc.md").write_text(
        "# タイトル\n\n> [!NOTE]\n> 注記です\n\n```mermaid\nflowchart LR\n  A[入力] --> B[出力]\n```\n",
        encoding="utf-8")
    (repo / "page.html").write_text("<h1>見出し</h1>\n", encoding="utf-8")
    (repo / "code.py").write_text(
        'def f():\n    """doc\n    string"""\n    return 1\n', encoding="utf-8")
    (repo / "big.py").write_text("\n".join("line_%d = %d" % (i, i) for i in range(1, 121)) + "\n",
                                 encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-qm", "init")

    (repo / "data.csv").write_text("id,name,qty\n1,ぶどう,3\n2,みかん,7\n3,もも,1\n", encoding="utf-8")
    (repo / "doc.md").write_text(
        "# タイトル（変更）\n\n> [!WARNING]\n> 変わった注記\n\n```mermaid\nflowchart LR\n"
        "  A[入力] --> B[出力]\n  B --> C[追加]\n```\n\n```gantt\nx\n```\n", encoding="utf-8")
    (repo / "page.html").write_text('<h1>見出し2</h1><script>alert(1)</script>\n', encoding="utf-8")
    (repo / "code.py").write_text(
        'def f():\n    """doc\n    string 2"""\n    return 2\n', encoding="utf-8")
    lines = (repo / "big.py").read_text(encoding="utf-8").split("\n")
    lines[9] = "line_10 = 999"
    lines[99] = "line_100 = 12345"
    (repo / "big.py").write_text("\n".join(lines), encoding="utf-8")
    return repo


def cli(repo, *args):
    """サブプロセスで CLI を叩き、(終了コード, 標準出力, 標準エラー) を返す。"""
    proc = subprocess.run([sys.executable, str(SCRIPT)] + list(args),
                          cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


class DiffParsingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_files_and_line_numbers(self):
        target, files = dr.collect_diff(self.repo, "unstaged", None, 3)
        by_path = {f["path"]: f for f in files}
        self.assertIn("plain.txt", by_path)
        self.assertIn("日本 語.txt", by_path, "空白と日本語を含むパスが落ちてはいけない")

        plain = by_path["plain.txt"]
        kinds = [(line["kind"], line["old"], line["new"]) for line in plain["hunks"][0]["lines"]]
        self.assertEqual(kinds[0], ("ctx", 1, 1))
        self.assertEqual(kinds[1], ("del", 2, None))
        self.assertEqual(kinds[2], ("add", None, 2))
        self.assertEqual(plain["additions"], 2)
        self.assertEqual(plain["deletions"], 1)

    def test_binary_has_no_body(self):
        _target, files = dr.collect_diff(self.repo, "unstaged", None, 3)
        binary = [f for f in files if f["path"] == "bin.dat"][0]
        self.assertTrue(binary["binary"])
        self.assertEqual(binary["hunks"], [], "バイナリの本文を持ってはいけない")

    def test_target_identity(self):
        target, _files = dr.collect_diff(self.repo, "unstaged", None, 3)
        self.assertEqual(len(target["base_commit"]), 40)
        self.assertEqual(len(target["diff_digest"]), 40)
        self.assertEqual(target["source"], "unstaged")
        self.assertIsNone(target["range"])
        self.assertTrue(any(f["path"] == "plain.txt" for f in target["files"]))

    def test_identity_changes_with_content(self):
        before, _ = dr.collect_diff(self.repo, "unstaged", None, 3)
        (self.repo / "plain.txt").write_text("a\nまったく別\n", encoding="utf-8")
        after, _ = dr.collect_diff(self.repo, "unstaged", None, 3)
        self.assertNotEqual(before["diff_digest"], after["diff_digest"])


class OutputContractTest(unittest.TestCase):
    def test_canonical_json_is_sorted_and_readable(self):
        text = dr.dumps_canonical({"b": 1, "a": "日本語"})
        self.assertEqual(text, '{\n  "a": "日本語",\n  "b": 1\n}\n')

    def test_script_block_escapes_angle_bracket(self):
        text = dr.json_for_script_block({"body": "</script>"})
        self.assertNotIn("<", text, "埋め込む JSON に生の < が残ると script ブロックが切れる")
        self.assertIn("\\u003c", text)
        self.assertEqual(json.loads(text)["body"], "</script>")

    def test_write_out_uses_lf_and_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.txt")
            dr.write_out("一行目\n二行目\n", path)
            with open(path, "rb") as f:
                raw = f.read()
            self.assertNotIn(b"\r\n", raw, "OS に関わらず改行は LF で固定する")
            self.assertEqual(raw.decode("utf-8"), "一行目\n二行目\n")


class HtmlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_deterministic(self):
        code1, first, _ = cli(self.repo, "html", "--repo", ".")
        code2, second, _ = cli(self.repo, "html", "--repo", ".")
        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)
        self.assertEqual(first, second, "同じ入力からは同じ HTML が出ること")

    def test_no_raw_script_from_diff(self):
        _code, html, _err = cli(self.repo, "html", "--repo", ".")
        self.assertNotIn("<script>alert(1)", html,
                         "差分に含まれる script タグが生のまま HTML に出てはいけない")
        self.assertIn("\\u003cscript>alert(1)", html)  # 退避が要るのは < だけ

    # SVG/XML の名前空間 URI（例: http://www.w3.org/2000/svg。app.js が
    # document.createElementNS() に渡す固定の識別子）は、ブラウザが読みに行く
    # ネットワーク参照ではないので許可する。それ以外の w3.org URL 風の文字列や、
    # 他のホストへの参照は許可しない（w3.org 直下だけに絞った狭い例外）。
    W3C_NAMESPACE_URI = re.compile(r"https?://www\.w3\.org/[\w./-]*")

    def test_contains_no_external_reference(self):
        _code, html, _err = cli(self.repo, "html", "--repo", ".")
        scrubbed = self.W3C_NAMESPACE_URI.sub("", html)
        for marker in ("http://", "https://", "//cdn."):
            self.assertNotIn(marker, scrubbed, "オフラインで開けるよう外部参照を持たない")

    def test_placeholder_text_in_diff_does_not_corrupt_embedding(self):
        """差分がテンプレートのプレースホルダ文字列を含んでも、埋め込み JSON が壊れないこと。

        自分自身（templates/page.html）の差分をレビューすると必ず踏む。順に str.replace すると、
        先に差し込んだ差分 JSON の中を次の置換が書き換えて JSON が壊れる。
        """
        # 追跡済みファイルに書く（未追跡のままだと `git diff` に出ず、検査が素通りする）
        (self.repo / "plain.txt").write_text(
            "a\n__DIFF_DATA__\n__REVIEW_DATA__\n__STYLE__\n__APP_JS__\n__TITLE__\n", encoding="utf-8")
        _code, html, _err = cli(self.repo, "html", "--repo", ".")
        for block_id in ("diff-data", "review-data"):
            start = html.index('id="%s">' % block_id) + len('id="%s">' % block_id)
            end = html.index("</script>", start)
            payload = html[start:end]
            json.loads(payload)  # 壊れていれば JSONDecodeError で落ちる
        self.assertIn("__REVIEW_DATA__", html, "差分の中身としてはそのまま出ること")

    def test_import_rejects_broken_record(self):
        code, _out, _err = cli(self.repo, "template", "--repo", ".")
        self.assertEqual(code, 0)
        broken = self.repo / "broken.json"
        broken.write_text('{"schema": "diff-review/1"}', encoding="utf-8")
        code, _out, err = cli(self.repo, "html", "--repo", ".", "--import", "broken.json",
                              "--out", "x.html")
        self.assertEqual(code, dr.EXIT_INVALID)
        self.assertFalse((self.repo / "x.html").exists(), "不正な記録から HTML を作ってはいけない")
        self.assertIn("reviews", err)


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)
        target, _files = dr.collect_diff(self.repo, "unstaged", None, 3)
        self.record = dr.empty_review(target)
        self.record["reviews"].append(
            {"id": "r1", "author": "human", "state": "COMMENTED", "body": "まとめ"})
        self.record["threads"].append({
            "id": "t1", "path": "plain.txt", "line": 2, "side": "RIGHT",
            "start_line": None, "start_side": None, "resolved": False,
            "comments": [
                {"id": "c1", "review_id": "r1", "author": "human", "body": "指摘", "in_reply_to": None},
                {"id": "c2", "review_id": None, "author": "ai", "body": "返信", "in_reply_to": "c1"},
            ],
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_record_has_no_problems(self):
        self.assertEqual(dr.validate(self.record), [])

    def test_template_output_is_valid(self):
        target, _files = dr.collect_diff(self.repo, "unstaged", None, 3)
        self.assertEqual(dr.validate(dr.empty_review(target)), [])

    def test_unknown_schema(self):
        self.record["schema"] = "diff-review/9"
        self.assertTrue(any("schema" in p for p in dr.validate(self.record)))

    def test_bad_review_state(self):
        self.record["reviews"][0]["state"] = "LGTM"
        self.assertTrue(any("state" in p for p in dr.validate(self.record)))

    def test_reply_must_stay_in_thread(self):
        self.record["threads"][0]["comments"][1]["in_reply_to"] = "c99"
        self.assertTrue(any("in_reply_to" in p for p in dr.validate(self.record)))

    def test_duplicate_comment_id(self):
        self.record["threads"][0]["comments"][1]["id"] = "c1"
        self.assertTrue(any("重複" in p for p in dr.validate(self.record)))

    def test_line_requires_path_and_side(self):
        self.record["threads"][0]["path"] = None
        self.record["threads"][0]["side"] = None
        problems = dr.validate(self.record)
        self.assertTrue(any(".path" in p for p in problems))
        self.assertTrue(any(".side" in p for p in problems))

    def test_file_level_thread_has_no_side(self):
        self.record["threads"][0]["line"] = None
        self.record["threads"][0]["side"] = "RIGHT"
        self.assertTrue(any(".side" in p for p in dr.validate(self.record)))

    def test_empty_body_is_rejected(self):
        self.record["threads"][0]["comments"][0]["body"] = "   "
        self.assertTrue(any(".body" in p for p in dr.validate(self.record)))

    def test_review_id_must_exist(self):
        self.record["threads"][0]["comments"][0]["review_id"] = "r9"
        self.assertTrue(any("review_id" in p for p in dr.validate(self.record)))

    def test_identity_mismatch_is_detected(self):
        target, _files = dr.collect_diff(self.repo, "unstaged", None, 3)
        self.record["target"]["diff_digest"] = "0" * 40
        self.assertTrue(dr.identity_mismatch(self.record, target))

    def test_check_cli_exit_codes(self):
        good = self.repo / "good.json"
        good.write_text(dr.dumps_canonical(self.record), encoding="utf-8")
        code, out, _err = cli(self.repo, "check", "good.json")
        self.assertEqual(code, 0)
        self.assertIn("OK", out)

        self.record["reviews"][0]["state"] = "LGTM"
        bad = self.repo / "bad.json"
        bad.write_text(dr.dumps_canonical(self.record), encoding="utf-8")
        code, _out, err = cli(self.repo, "check", "bad.json")
        self.assertEqual(code, dr.EXIT_INVALID)
        self.assertIn("state", err)

    def test_broken_json_is_not_silently_accepted(self):
        path = self.repo / "notjson.json"
        path.write_text("{ この行は JSON ではない", encoding="utf-8")
        code, _out, err = cli(self.repo, "check", "notjson.json")
        self.assertEqual(code, dr.EXIT_INVALID)
        self.assertIn("JSON", err)


class ListTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)
        target, _files = dr.collect_diff(self.repo, "unstaged", None, 3)
        record = dr.empty_review(target)
        record["threads"] = [
            {"id": "t1", "path": "plain.txt", "line": 2, "side": "RIGHT",
             "start_line": None, "start_side": None, "resolved": False,
             "comments": [{"id": "c1", "review_id": None, "author": "ai",
                           "body": "未解決の指摘", "in_reply_to": None}]},
            {"id": "t2", "path": "日本 語.txt", "line": None, "side": None,
             "start_line": None, "start_side": None, "resolved": True,
             "comments": [{"id": "c1", "review_id": None, "author": "ai",
                           "body": "解決済みの指摘", "in_reply_to": None}]},
        ]
        self.path = self.repo / "review.json"
        self.path.write_text(dr.dumps_canonical(record), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_shows_only_unresolved(self):
        code, out, _err = cli(self.repo, "list", "review.json")
        self.assertEqual(code, 0)
        self.assertIn("plain.txt:2", out)
        self.assertNotIn("解決済みの指摘", out)

    def test_all_includes_resolved(self):
        _code, out, _err = cli(self.repo, "list", "review.json", "--all")
        self.assertIn("解決済みの指摘", out)

    def test_tsv_is_one_line_per_thread(self):
        _code, out, _err = cli(self.repo, "list", "review.json", "--format", "tsv")
        lines = [line for line in out.split("\n") if line]
        self.assertEqual(len(lines), 1)
        location, severity, state, kind, body = lines[0].split("\t")
        self.assertEqual(location, "plain.txt:2")
        self.assertEqual(severity, "-")
        self.assertEqual(state, "unresolved")
        self.assertEqual(kind, "review")
        self.assertEqual(body, "未解決の指摘")

    def test_japanese_survives_round_trip(self):
        raw = self.path.read_text(encoding="utf-8")
        again = dr.dumps_canonical(json.loads(raw))
        self.assertEqual(raw, again, "正規形は読み書きを往復してもバイト一致する")
        self.assertIn("日本 語.txt", again)


if __name__ == "__main__":
    unittest.main()


class HighlightTest(unittest.TestCase):
    """ハイライトは全文に対して行う（行ごとに当てると docstring の途中で壊れる）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_rich_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_language_detection(self):
        _target, files = dr.collect_diff(self.repo, "unstaged", None, 3)
        langs = {f["path"]: f["language"] for f in files}
        self.assertEqual(langs["code.py"], "python")
        self.assertEqual(langs["doc.md"], "markdown")
        self.assertIsNone(langs["data.csv"], "未対応の拡張子に言語を付けない")

    @staticmethod
    def tokens_for(file, line):
        """画面と同じ規則でトークンを引く。

        行が自分で持っていればそれ、無ければ展開データ側から行番号で引く
        （同じ配列を 2 回運ばないための取り決め）。
        """
        if line.get("tokens"):
            return line["tokens"]
        expand = file.get("expand") or {}
        if not expand.get("tokens"):
            return None
        side = "old" if line["kind"] == "del" else "new"
        if expand.get("side") != side:
            return None
        number = line["old"] if side == "old" else line["new"]
        if not number:
            return None
        return expand["tokens"][number - 1]

    def test_multiline_string_keeps_class_across_lines(self):
        _target, files = dr.collect_diff(self.repo, "unstaged", None, 3)
        code = [f for f in files if f["path"] == "code.py"][0]
        targets = [l for h in code["hunks"] for l in h["lines"] if "string" in (l["text"] or "")]
        self.assertTrue(targets, "docstring の途中行が差分に含まれること")
        for line in targets:
            classes = [t[0] for t in self.tokens_for(code, line) or []]
            self.assertIn("str", classes, "docstring の途中行が文字列として色付くこと")

    def test_tokens_are_not_duplicated(self):
        """展開データが持つ側の行には、行側のトークンを重ねて持たせない（容量）。"""
        _target, files = dr.collect_diff(self.repo, "unstaged", None, 3)
        code = [f for f in files if f["path"] == "code.py"][0]
        self.assertEqual(code["expand"]["side"], "new")
        new_lines = [l for h in code["hunks"] for l in h["lines"] if l["kind"] != "del"]
        self.assertTrue(new_lines)
        for line in new_lines:
            self.assertNotIn("tokens", line, "新側の行は展開データから引くので持たない")
            self.assertIsNotNone(self.tokens_for(code, line), "それでも引ける")

    def test_tokens_are_lossless(self):
        _target, files = dr.collect_diff(self.repo, "unstaged", None, 3)
        for f in files:
            for hunk in f["hunks"]:
                for line in hunk["lines"]:
                    tokens = self.tokens_for(f, line)
                    if tokens:
                        joined = "".join(t[1] for t in tokens)
                        self.assertEqual(joined, line["text"], "トークンを連結すると元の行に戻ること")


class ExpandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_rich_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_expand_data_is_embedded(self):
        _target, files = dr.collect_diff(self.repo, "unstaged", None, 3)
        big = [f for f in files if f["path"] == "big.py"][0]
        self.assertFalse(big["expand"]["truncated"])
        self.assertEqual(big["expand"]["count"], 120)
        self.assertEqual(big["expand"]["side"], "new")
        self.assertEqual(len(big["expand"]["tokens"]), 120, "全文ぶんの行を持つこと")

    def test_limit_drops_content_but_keeps_reason(self):
        _target, files = dr.collect_diff(self.repo, "unstaged", None, 3, expand_max_lines=10)
        big = [f for f in files if f["path"] == "big.py"][0]
        self.assertTrue(big["expand"]["truncated"])
        self.assertNotIn("tokens", big["expand"])
        self.assertEqual(big["expand"]["count"], 120, "何行あるかは伝える")

    def test_zero_disables_expand_and_highlight(self):
        _target, files = dr.collect_diff(self.repo, "unstaged", None, 3, expand_max_lines=0)
        big = [f for f in files if f["path"] == "big.py"][0]
        self.assertIsNone(big["expand"])


class RichTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_rich_repo(self.tmp.name)
        _target, self.files = dr.collect_diff(self.repo, "unstaged", None, 3)
        self.by_path = {f["path"]: f for f in self.files}

    def tearDown(self):
        self.tmp.cleanup()

    def test_csv_marks_changed_cells(self):
        rich = self.by_path["data.csv"]["rich"]
        self.assertEqual(rich["kind"], "table")
        rows = rich["payload"]["rows"]
        changed = [[c["changed"] for c in row["cells"]] for row in rows]
        self.assertIn([False, True, False], changed, "name 列だけが変わった行があること")
        self.assertTrue(any(row["kind"] == "add" for row in rows), "追加行が分かること")

    def test_markdown_alert_and_mermaid(self):
        rich = self.by_path["doc.md"]["rich"]
        self.assertEqual(rich["kind"], "doc")
        after = rich["payload"]["after"]
        classes = [n[1].get("class") for n in after if isinstance(n, list) and isinstance(n[1], dict)]
        self.assertIn("alert alert-warning", classes, "GitHub alert 記法が専用表示になること")
        figures = [n for n in after if isinstance(n, list) and n[0] == "figure"]
        self.assertTrue(figures, "mermaid ブロックが figure になること")
        img = figures[0][2][0]
        self.assertEqual(img[0], "img")
        self.assertTrue(img[1]["src"].startswith("data:image/svg+xml;base64,"))

    def test_unsupported_mermaid_kind_falls_back_with_reason(self):
        svg, reason = richdiff.mermaid_svg("gantt\n  title x\n")
        self.assertIsNone(svg)
        self.assertIn("描画対象外", reason)

    def test_html_payload_is_raw_and_marked(self):
        rich = self.by_path["page.html"]["rich"]
        self.assertEqual(rich["kind"], "html")
        self.assertIn("<script>alert(1)</script>", rich["payload"]["after"],
                      "中身はそのまま持つ（実行させないのは iframe sandbox 側の責務）")
        self.assertIn("sandbox", rich["note"])

    def test_dangerous_link_is_not_an_anchor(self):
        nodes = richdiff.markdown_nodes("[x](javascript:alert(1))\n")
        flat = json.dumps(nodes, ensure_ascii=False)
        self.assertNotIn('"a"', flat, "javascript: のリンクはアンカーにしない")


class RichBundlingTest(unittest.TestCase):
    """rich の対象が無ければ、描画コードを埋め込まない（AC9）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rich_repo = make_rich_repo(self.tmp.name)
        self.plain_tmp = tempfile.TemporaryDirectory()
        self.plain_repo = make_repo(self.plain_tmp.name)

    def tearDown(self):
        self.tmp.cleanup()
        self.plain_tmp.cleanup()

    def test_rich_code_only_when_needed(self):
        _code, with_rich, _err = cli(self.rich_repo, "html", "--repo", ".")
        _code2, without_rich, _err2 = cli(self.plain_repo, "html", "--repo", ".")
        marker = "window.DiffReviewRich = (function"
        self.assertIn(marker, with_rich, "rich 対象があるときは描画コードを積む")
        self.assertNotIn(marker, without_rich, "rich 対象が無ければ積まない")
        self.assertIn('"rich_enabled": true', with_rich)
        self.assertIn('"rich_enabled": false', without_rich)

    def test_rich_output_is_deterministic(self):
        """mermaid の SVG も base64 も、同じ入力なら同じバイト列になること。"""
        _c1, first, _e1 = cli(self.rich_repo, "html", "--repo", ".")
        _c2, second, _e2 = cli(self.rich_repo, "html", "--repo", ".")
        self.assertEqual(first, second)

    def test_rich_off_drops_everything(self):
        _code, off, _err = cli(self.rich_repo, "html", "--repo", ".", "--rich", "off")
        self.assertNotIn("window.DiffReviewRich = (function", off)
        self.assertIn('"rich_enabled": false', off)

    def test_rich_machinery_cost_is_bounded(self):
        """rich 機構の増分（描画コード＋データ）が生成物の 15% 以内であること。"""
        _c1, with_rich, _e1 = cli(self.rich_repo, "html", "--repo", ".")
        _c2, off, _e2 = cli(self.rich_repo, "html", "--repo", ".", "--rich", "off")
        grew = len(with_rich.encode()) - len(off.encode())
        self.assertLess(grew, len(off.encode()) * 0.15,
                        "rich の機構が重くなりすぎていないこと（%d / %d バイト）"
                        % (grew, len(off.encode())))


class SchemaV2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)
        target, _files = dr.collect_diff(self.repo, "unstaged", None, 3, expand_max_lines=0, rich=False)
        self.record = dr.empty_review(target)
        self.record["reviews"].append(
            {"id": "r1", "author": "human", "state": "COMMENTED", "body": "まとめ"})
        self.record["threads"].append({
            "id": "t1", "kind": "review", "path": "plain.txt", "line": 2, "side": "RIGHT",
            "start_line": None, "start_side": None, "resolved": False,
            "comments": [
                {"id": "c1", "review_id": "r1", "author": "ai", "body": "直して",
                 "severity": "must", "in_reply_to": None},
                {"id": "c2", "review_id": None, "author": "human", "body": "直した",
                 "severity": None, "in_reply_to": "c1"},
            ],
        })
        self.record["threads"].append({
            "id": "t2", "kind": "note", "path": "plain.txt", "line": None, "side": None,
            "start_line": None, "start_side": None, "resolved": False,
            "comments": [{"id": "c1", "review_id": None, "author": "human",
                          "body": "ここは意図的にこうしています", "severity": None, "in_reply_to": None}],
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_v2(self):
        self.assertEqual(dr.validate(self.record), [])

    def test_bad_severity(self):
        self.record["threads"][0]["comments"][0]["severity"] = "blocker"
        self.assertTrue(any("severity" in p for p in dr.validate(self.record)))

    def test_bad_kind(self):
        self.record["threads"][0]["kind"] = "question"
        self.assertTrue(any("kind" in p for p in dr.validate(self.record)))

    def test_note_cannot_be_submitted_or_scored(self):
        self.record["threads"][1]["comments"][0]["review_id"] = "r1"
        self.record["threads"][1]["comments"][0]["severity"] = "nit"
        problems = dr.validate(self.record)
        self.assertTrue(any("review_id" in p for p in problems))
        self.assertTrue(any("severity" in p for p in problems))

    def test_v1_is_migrated_on_load(self):
        legacy = json.loads(json.dumps(self.record))
        legacy["schema"] = dr.SCHEMA_LEGACY
        for thread in legacy["threads"]:
            thread.pop("kind", None)
            for comment in thread["comments"]:
                comment.pop("severity", None)
        path = self.repo / "legacy.json"
        path.write_text(dr.dumps_canonical(legacy), encoding="utf-8")
        loaded = dr.load_json(str(path))
        self.assertEqual(loaded["schema"], dr.SCHEMA)
        self.assertEqual(loaded["threads"][0]["kind"], "review")
        self.assertIsNone(loaded["threads"][0]["comments"][0]["severity"])
        self.assertEqual(dr.validate(loaded), [])
        code, out, _err = cli(self.repo, "check", "legacy.json")
        self.assertEqual(code, 0, out)

    def test_list_filters_by_severity_and_notes(self):
        path = self.repo / "review.json"
        path.write_text(dr.dumps_canonical(self.record), encoding="utf-8")
        _code, out, _err = cli(self.repo, "list", "review.json")
        self.assertIn("must", out)
        self.assertNotIn("意図的に", out, "説明コメントは既定では出さない")

        _code, out_notes, _err = cli(self.repo, "list", "review.json", "--notes")
        self.assertIn("意図的に", out_notes)

        _code, only_nit, _err = cli(self.repo, "list", "review.json", "--severity", "nit")
        self.assertNotIn("直して", only_nit, "must の指摘は nit の絞り込みに出ない")


# --------------------------------------------------------------------------
# 3 ペイン・split・ツリー・テーマ（20260916-diff-review-layout）
# --------------------------------------------------------------------------

class LayoutBundlingTest(unittest.TestCase):
    """画面の形を担う ui.js が**常に**積まれること。

    rich.js は「対象があるときだけ」だが、ui.js はペイン・テーマ・設定の記憶を持つので
    差分の中身に依らず要る。落ちると 3 ペインが一切動かない。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ui_js_is_always_embedded(self):
        for extra in ([], ["--rich", "off"], ["--expand-max-lines", "0", "--rich", "off"]):
            _code, html, _err = cli(self.repo, "html", "--repo", ".", *extra)
            self.assertNotIn("__UI_JS__", html, "差し込み口が残っている: %r" % extra)
            self.assertIn("window.DiffReviewUI", html, "ui.js が積まれていない: %r" % extra)

    def test_three_panes_exist_in_page(self):
        _code, html, _err = cli(self.repo, "html", "--repo", ".")
        for needle in ('id="pane-left"', 'id="pane-center"', 'id="pane-right"',
                       'id="sep-left"', 'id="sep-right"', 'role="separator"',
                       'id="btn-split"', 'id="btn-tree"', 'id="btn-theme"',
                       'id="btn-pane-left"', 'id="btn-pane-right"', 'id="commentlist"'):
            self.assertIn(needle, html, needle)

    def test_theme_is_restored_before_body_renders(self):
        # 復元が本文より後だと一瞬明るく光る。head の中にあることを位置で確かめる。
        _code, html, _err = cli(self.repo, "html", "--repo", ".")
        self.assertLess(html.index(theme_storage_key()), html.index("<body>"))

    def test_head_script_and_ui_js_agree_on_the_key(self):
        # 復元は page.html の中に**直書き**してある（ui.js より先に走る必要があるため）。
        # ui.js 側の接頭辞を変えたときに、片方だけ直して黙ってすれ違うのを防ぐ。
        page = (SKILL_DIR / "templates" / "page.html").read_text(encoding="utf-8")
        self.assertIn('"%s"' % theme_storage_key(), page)


    def test_ui_prefs_never_reach_the_record(self):
        # 画面の設定はレビュー記録に混ざらない（AC15）。生成側が書き出す JSON で確かめる。
        _code, out, _err = cli(self.repo, "template", "--repo", ".")
        record = json.loads(out)
        text = dr.dumps_canonical(record)
        for key in dr_ui_pref_names():
            self.assertNotIn('"%s"' % key, text, key)
        self.assertEqual(dr.validate(record), [])


def theme_storage_key():
    """テーマの保存キー。`ui.js` の接頭辞から組み立てる（page.html との突き合わせ用）。"""
    source = (SKILL_DIR / "templates" / "ui.js").read_text(encoding="utf-8")
    prefix = source.split('var PREFIX = "', 1)[1].split('"', 1)[0]
    return prefix + "theme"


def dr_ui_pref_names():
    """ui.js が localStorage へ書く設定名。テンプレートから読み取る（二重管理を避ける）。"""
    source = (SKILL_DIR / "templates" / "ui.js").read_text(encoding="utf-8")
    block = source.split("var DEFAULTS = {", 1)[1].split("};", 1)[0]
    names = []
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        key = line.split(":", 1)[0].strip().strip('"')
        if key:
            names.append(key)
    assert names, "DEFAULTS を読み取れていない"
    return names


class ThemeCssTest(unittest.TestCase):
    """暗い配色の「割り当て」が 2 か所にある（decisions.md D3）。ずれを機械的に潰す。

    片方にだけ色を足すと、OS 追従では暗いのに手動ダークでは明るいまま、という
    目で追いにくい食い違いになる。ここで固定しておく。
    """

    def blocks(self):
        css = (SKILL_DIR / "templates" / "style.css").read_text(encoding="utf-8")
        parts = css.split("/* dark-assign:begin */")[1:]
        return [part.split("/* dark-assign:end */")[0] for part in parts]

    def normalized(self, block):
        return tuple(line.strip() for line in block.splitlines() if line.strip())

    def test_two_dark_blocks_are_identical(self):
        blocks = self.blocks()
        self.assertEqual(len(blocks), 2, "暗い配色の割り当てブロックは 2 つのはず")
        self.assertEqual(self.normalized(blocks[0]), self.normalized(blocks[1]),
                         "OS 追従用と手動ダーク用の宣言がずれている")

    def test_every_dark_value_is_assigned(self):
        css = (SKILL_DIR / "templates" / "style.css").read_text(encoding="utf-8")
        root = css.split(":root {", 1)[1].split("}", 1)[0]
        defined = set()
        for line in root.splitlines():
            for chunk in line.split(";"):
                chunk = chunk.strip()
                if chunk.startswith("--d-"):
                    defined.add(chunk.split(":", 1)[0].strip())
        self.assertTrue(defined, "--d-* が見つからない")
        assigned = set()
        for line in self.blocks()[0].splitlines():
            if "var(--d-" in line:
                assigned.add("--d-" + line.split("var(--d-", 1)[1].split(")", 1)[0])
        self.assertEqual(defined, assigned,
                         "定義した暗い色が割り当てられていない（または逆）: %s"
                         % sorted(defined ^ assigned))


class MarkdownProgressTest(unittest.TestCase):
    """フェンス記号を**行の途中に**含む行で markdown_nodes が止まらないこと。

    ```` ```gantt ```` のような行はフェンスの正規表現（行全体がフェンス）には当たらないが
    「ブロックの始まり」には見えるため、段落の取り込みが 0 行になって位置が進まず、
    **生成が永久に終わらなかった**（この work で実測して修正）。
    """

    def test_inline_fence_marker_does_not_hang(self):
        text = "前の段落\n\n```` ```gantt ```` は ````` ```mermaid ````` の中の話\n\n次の段落\n"
        nodes = richdiff.markdown_nodes(text)
        self.assertEqual(len(nodes), 3)
        joined = json.dumps(nodes, ensure_ascii=False)
        self.assertIn("gantt", joined, "取りこぼさず段落として残ること")

    def test_bare_fence_marker_line_does_not_hang(self):
        for line in ("``` これは終わらないフェンスに見える行", "   ```x y z", "```"):
            nodes = richdiff.markdown_nodes("段落\n\n%s\n" % line)
            self.assertIsInstance(nodes, list)


# --------------------------------------------------------------------------
# バンドルとビューアの分離（20260916-diff-review-bundle）
# --------------------------------------------------------------------------

def node_available():
    """`node` が使えるか。無い環境で全体を落とさないため、該当テストだけ skip する。"""
    try:
        subprocess.run(["node", "--version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


class BundleFormatTest(unittest.TestCase):
    """バンドルは「JS としても JSON としても」読めること（research.md F2 の形を固定する）。"""

    def payload(self):
        return {
            "target": {"source": "unstaged", "range": None, "base_commit": None,
                       "diff_digest": "d" * 40, "files": []},
            "files": [{"path": "a.txt", "text": "行区切り と 段落区切り</script>"}],
        }

    def test_round_trip(self):
        p = self.payload()
        text = dr.bundle_text(p["target"], p["files"], False, None)
        back = dr.parse_bundle(text)
        self.assertEqual(back, dr.bundle_object(p["target"], p["files"], False, None))
        self.assertEqual(back["files"][0]["text"], p["files"][0]["text"],
                         "退避した文字が元に戻ること")

    def test_js_line_terminators_are_escaped(self):
        # U+2028 / U+2029 は JS では行終端文字。生で置くと古いエンジンで構文エラーになる。
        text = dr.bundle_text({}, [{"t": "a b c"}], False, None)
        self.assertNotIn(" ", text)
        self.assertNotIn(" ", text)
        self.assertIn("\\u2028", text)

    def test_fixed_prefix_and_suffix(self):
        text = dr.bundle_text({}, [], False, None)
        self.assertTrue(text.startswith(dr.BUNDLE_PREFIX))
        self.assertTrue(text.endswith(dr.BUNDLE_SUFFIX))
        self.assertTrue(dr.looks_like_bundle(text))
        self.assertFalse(dr.looks_like_bundle('{"schema": "diff-review/2"}'))

    def test_rejects_things_that_are_not_bundles(self):
        for bad in ('{"schema": "diff-review/2"}', "", "window.OTHER = {};\n",
                    dr.BUNDLE_PREFIX + "{}"):          # 末尾の ; が無い
            with self.assertRaises(ValueError, msg=repr(bad)):
                dr.parse_bundle(bad)

    def test_tolerates_trailing_whitespace(self):
        # エディタが末尾に改行を足すことがある。**画面側と同じ寛容さ**にしておかないと、
        # ビューアでは開けるのに check が落ちる（利用者には理由が分からない）。
        text = dr.bundle_text({}, [], False, None)
        self.assertEqual(dr.parse_bundle(text + "\n\n  "), dr.parse_bundle(text))

    def test_render_html_has_no_load_hook(self):
        # 焼き込みの口ごと落としたことを固定する（引数が復活したら落ちる）。
        import inspect
        self.assertNotIn("load_src", inspect.signature(dr.render_html).parameters)

    def test_deterministic(self):
        p = self.payload()
        a = dr.bundle_text(p["target"], p["files"], True, None)
        b = dr.bundle_text(p["target"], p["files"], True, None)
        self.assertEqual(a, b)

    @unittest.skipUnless(node_available(), "node が無い環境では確かめられない")
    def test_node_reads_it_without_executing(self):
        # VSCode 拡張と同じ実行系（Node）から、**JS を実行せずに**読めること。
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / ("bundle" + dr.BUNDLE_EXT)
        p = self.payload()
        path.write_text(dr.bundle_text(p["target"], p["files"], False, None),
                        encoding="utf-8", newline="\n")
        script = (
            "const fs=require('fs');"
            "const PRE=%r;const SUF=';\\n';"
            "const raw=fs.readFileSync(process.argv[1],'utf8');"
            "if(!raw.startsWith(PRE)||!raw.endsWith(SUF))throw new Error('shape');"
            "const o=JSON.parse(raw.slice(PRE.length,-SUF.length));"
            "process.stdout.write(o.files[0].text);"
        ) % dr.BUNDLE_PREFIX
        out = subprocess.run(["node", "-e", script, str(path)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(out.returncode, 0, out.stderr.decode("utf-8", "replace"))
        self.assertEqual(out.stdout.decode("utf-8"), p["files"][0]["text"])


class BundleCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bundle_holds_diff_and_review(self):
        _code, tmpl, _err = cli(self.repo, "template", "--repo", ".")
        record = json.loads(tmpl)
        record["threads"] = [{
            "id": "t1", "kind": "review", "path": "big.py", "line": 1, "side": "RIGHT",
            "start_line": None, "start_side": None, "resolved": False,
            "comments": [{"id": "c1", "review_id": None, "author": "ai",
                          "body": "指摘", "severity": "must", "in_reply_to": None}],
        }]
        (self.repo / "r.json").write_text(dr.dumps_canonical(record), encoding="utf-8")
        code, out, err = cli(self.repo, "bundle", "--repo", ".", "--import", "r.json")
        self.assertEqual(code, 0, err)
        bundle = dr.parse_bundle(out)
        self.assertEqual(bundle["schema"], dr.BUNDLE_SCHEMA)
        self.assertTrue(bundle["files"], "差分が入っていること")
        self.assertEqual(bundle["review"]["threads"][0]["comments"][0]["severity"], "must")
        self.assertEqual(dr.validate_bundle(bundle), [])

    def test_check_and_list_accept_a_bundle(self):
        _code, out, _err = cli(self.repo, "bundle", "--repo", ".")
        (self.repo / ("b" + dr.BUNDLE_EXT)).write_text(out, encoding="utf-8", newline="\n")
        code, text, err = cli(self.repo, "check", "b" + dr.BUNDLE_EXT)
        self.assertEqual(code, 0, err)
        self.assertIn("バンドル", text)
        code, text, err = cli(self.repo, "list", "b" + dr.BUNDLE_EXT)
        self.assertEqual(code, 0, err)

    def test_check_rejects_a_broken_bundle(self):
        (self.repo / "bad.dreview").write_text(
            dr.BUNDLE_PREFIX + '{"schema": "other/1"}' + dr.BUNDLE_SUFFIX,
            encoding="utf-8", newline="\n")
        code, _out, err = cli(self.repo, "check", "bad.dreview")
        self.assertEqual(code, 3)
        self.assertIn("schema", err)

    def test_name_does_not_decide_the_format(self):
        # 中身で判別する。拡張子を変えられても動く。
        _code, out, _err = cli(self.repo, "bundle", "--repo", ".")
        (self.repo / "weird.txt").write_text(out, encoding="utf-8", newline="\n")
        code, text, err = cli(self.repo, "check", "weird.txt")
        self.assertEqual(code, 0, err)
        self.assertIn("バンドル", text)


class ViewCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_viewer_has_no_diff_but_has_rich(self):
        code, html, err = cli(self.repo, "view")
        self.assertEqual(code, 0, err)
        self.assertIn('id="open-prompt"', html)
        # ビューアは何を開くか事前に分からないので rich を**常に**積む（research.md F5）
        self.assertIn("window.DiffReviewRich", html)
        self.assertIn('"files": []', html)

    def test_host_embed_slot_is_present_and_empty(self):
        """ホストが HTML を組み立てて渡すための口（decisions.md D10）。

        **常に空**で出す。生成側が中身を入れることは無いので、決定論も壊れない。
        """
        for args in (["view"], ["view", "--readonly"], ["html", "--repo", "."]):
            _code, html, _err = cli(self.repo, *args)
            self.assertIn('<script type="application/json" id="bundle-data"></script>', html,
                          repr(args))

    def test_intake_is_limited_to_the_three_agreed_paths(self):
        """取り込み口は 3 つだけ（D10 / D11）——手動・埋め込み・ホストの postMessage。

        持たないのは **外部ファイルを読む口**（`<script src>`）と、
        **生成物がグローバル変数を読む経路**。前者は「どのバンドルを読むのか」が
        ファイル名任せになり、実行も伴う。
        """
        _code, html, _err = cli(self.repo, "view")
        skeleton = html.split('<script type="application/json" id="bundle-data">')[0]
        app = (SKILL_DIR / "templates" / "app.js").read_text(encoding="utf-8")
        self.assertIn('addEventListener("message"', app, "ホストからの差し替えは受ける")
        # グローバル変数は **読まない**。app.js に残ってよいのは、手で開いた .dreview の
        # 前置きを剥がすための文字列定数 1 か所だけ。
        lines = [ln for ln in app.splitlines() if "__DIFF_REVIEW_BUNDLE__" in ln]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("var BUNDLE_PREFIX =", lines[0])
        self.assertNotIn("<script src=", skeleton)

    def test_never_loads_an_external_file(self):
        """生成物は**どのファイルも自動では読まない**（decisions.md D9）。

        ビューアが特定のバンドルをファイル名で指すと、配ったあと
        「このビューアはどれを見ているのか」がファイル名任せになり決定的でなくなる。
        `<script src>` は実行も伴うので、口ごと持たない。
        """
        for args in (["view"], ["view", "--readonly"],
                     ["html", "--repo", "."], ["html", "--repo", ".", "--readonly"]):
            _code, html, _err = cli(self.repo, *args)
            skeleton = html.split('<script type="application/json" id="diff-data">')[0]
            self.assertNotIn("<script src=", skeleton, repr(args))
            self.assertNotIn("__BUNDLE_SRC__", html, repr(args))

    def test_load_option_is_gone(self):
        code, _out, err = cli(self.repo, "view", "--load", "x.dreview")
        self.assertEqual(code, 2, "argparse が知らない引数として弾くこと")
        self.assertIn("--load", err)


class ReadonlyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    WRITE_UI = ('id="btn-export-open"', 'id="btn-start-review"', 'id="review-list"',
                'id="submit-panel"', 'id="export-panel"', 'class="comment-open"',
                'id="btn-reset-draft"', 'id="submit-backdrop"', 'id="btn-submit-close-x"',
                'id="export-backdrop"', 'id="btn-export-close-x"')

    def skeleton(self, html):
        """埋め込んだ差分の中身と、ページの骨格を分ける（差分に何が入っていても影響されない）。"""
        return html.split('<script type="application/json" id="diff-data">')[0]

    def test_write_ui_is_not_shipped(self):
        _code, html, _err = cli(self.repo, "html", "--repo", ".", "--readonly")
        skeleton = self.skeleton(html)
        for needle in self.WRITE_UI:
            self.assertNotIn(needle, skeleton, needle)
        self.assertIn('"readonly": true', html)

    def test_normal_output_still_has_it(self):
        _code, html, _err = cli(self.repo, "html", "--repo", ".")
        skeleton = self.skeleton(html)
        for needle in self.WRITE_UI:
            self.assertIn(needle, skeleton, needle)
        self.assertIn('"readonly": false', html)

    def test_build_markers_never_reach_the_output(self):
        for extra in ([], ["--readonly"]):
            _code, html, _err = cli(self.repo, "html", "--repo", ".", *extra)
            self.assertNotIn("rw:begin", self.skeleton(html), repr(extra))
            self.assertNotIn("rw:end", self.skeleton(html), repr(extra))

    def test_reading_features_survive(self):
        _code, html, _err = cli(self.repo, "html", "--repo", ".", "--readonly")
        skeleton = self.skeleton(html)
        for needle in ('id="btn-split"', 'id="btn-tree"', 'id="btn-theme"',
                       'id="commentlist"', 'id="pane-left"', 'id="pane-right"'):
            self.assertIn(needle, skeleton, needle)


class SourceSelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_from_matches_the_old_flags(self):
        pairs = [(["--from", "unstaged"], []),
                 (["--from", "staged"], ["--staged"]),
                 (["--from", "range", "--rev", "HEAD~1..HEAD"], ["--range", "HEAD~1..HEAD"]),
                 (["--from", "commit", "--rev", "HEAD"], ["--commit", "HEAD"])]
        for new, old in pairs:
            _c1, a, e1 = cli(self.repo, "template", "--repo", ".", *new)
            _c2, b, e2 = cli(self.repo, "template", "--repo", ".", *old)
            self.assertEqual(a, b, "%r と %r が同じ差分を指すこと（%s %s）" % (new, old, e1, e2))

    def test_mixing_old_and_new_is_rejected(self):
        code, _out, err = cli(self.repo, "template", "--repo", ".", "--from", "staged", "--staged")
        self.assertEqual(code, 1)
        self.assertIn("同時に指定できません", err)

    def test_rev_is_required_and_restricted(self):
        code, _out, err = cli(self.repo, "template", "--repo", ".", "--from", "range")
        self.assertEqual(code, 1)
        self.assertIn("--rev", err)
        code, _out, err = cli(self.repo, "template", "--repo", ".", "--from", "staged", "--rev", "x")
        self.assertEqual(code, 1)
        self.assertIn("--rev", err)

    def test_github_pr_requires_github_pr_flag(self):
        code, out, err = cli(self.repo, "html", "--repo", ".", "--from", "github-pr")
        self.assertEqual(code, 1, "黙って別の差分を出してはいけない")
        self.assertEqual(out, "")
        self.assertIn("--github-pr", err)

    def test_github_compare_requires_github_repo_and_rev(self):
        code, _out, err = cli(self.repo, "html", "--from", "github-compare")
        self.assertEqual(code, 1)
        self.assertIn("--github-repo", err)
        code, _out, err = cli(self.repo, "html", "--from", "github-compare",
                              "--github-repo", "o/r")
        self.assertEqual(code, 1)
        self.assertIn("--rev", err)

    def test_github_compare_rejects_two_dot_rev(self):
        code, _out, err = cli(self.repo, "html", "--from", "github-compare",
                              "--github-repo", "o/r", "--rev", "main..feature")
        self.assertEqual(code, 1, "書式の誤りは使い方エラー。ネットワークを叩く前に検査で落ちる")
        self.assertIn("3 ドット", err)

    def test_github_sources_do_not_require_a_local_repo(self):
        # --repo を省いても（既定値 "." のまま）使い方エラーにならない（要件 AC3）。
        # ネットワークは実際には叩かれない——引数不足で先に落ちるケースで確認する。
        code, _out, err = cli(self.tmp.name, "html", "--from", "github-pr")
        self.assertEqual(code, 1)
        self.assertIn("--github-pr", err)


# --------------------------------------------------------------------------
# GitHub REST API 経由の差分取得（decisions.md D2）。
# **実際の外部ネットワークは叩かない**——`urllib.request.urlopen` をモックする
# （design テスト方針・tasks.md T7）。
# --------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, body_bytes, headers):
        self._body = body_bytes
        self.headers = email.message.Message()
        for k, v in (headers or {}).items():
            self.headers[k] = v

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def fake_urlopen_sequence(pages):
    """`pages`: [(status, JSON でエンコードする値, headers) , ...] を呼び出し順に返す偽 urlopen。

    呼ばれた `Request` は `calls` に積む（Authorization ヘッダ・URL の検査に使う）。
    """
    calls = []
    it = iter(pages)

    def _fake(req, timeout=None):
        calls.append(req)
        status, payload, headers = next(it)
        body = json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload
        if status >= 400:
            hdrs = email.message.Message()
            for k, v in (headers or {}).items():
                hdrs[k] = v
            raise urllib.error.HTTPError(req.full_url, status, "error", hdrs, io.BytesIO(body))
        return _FakeResponse(body, headers)

    _fake.calls = calls
    return _fake


PR_PATCH_A = "@@ -1,3 +1,4 @@\n a\n-b\n+B\n+c\n c"
PR_PATCH_B = "@@ -0,0 +1,2 @@\n+x\n+y"


class GithubSourceTest(unittest.TestCase):
    def test_pr_fetch_builds_target_and_files_and_follows_pagination(self):
        pr = {"number": 7, "head": {"sha": "headsha0123456"}, "base": {"sha": "basesha"}}
        page1 = [{"filename": "a.py", "status": "modified", "additions": 2, "deletions": 1,
                  "previous_filename": None, "sha": "shaa", "patch": PR_PATCH_A}]
        page2 = [{"filename": "b.py", "status": "added", "additions": 2, "deletions": 0,
                  "previous_filename": None, "sha": "shab", "patch": PR_PATCH_B}]
        next_url = "https://api.github.com/repositories/1/pulls/7/files?per_page=100&page=2"
        fake = fake_urlopen_sequence([
            (200, pr, {}),
            (200, page1, {"Link": '<%s>; rel="next", <%s>; rel="last"' % (next_url, next_url)}),
            (200, page2, {}),
        ])
        with mock.patch("diff_review.urllib.request.urlopen", fake):
            opts = dr.GithubOpts(dr.DEFAULT_GITHUB_API_BASE, None)
            target, files = dr.collect_diff_github_pr(opts, "o", "r", "7", 2000)
        self.assertEqual(target["source"], "github-pr")
        self.assertEqual(target["range"], "o/r#7")
        self.assertEqual(target["base_commit"], "headsha0123456")
        self.assertTrue(target["diff_digest"].startswith("gh1:"))
        self.assertEqual([f["path"] for f in files], ["a.py", "b.py"])
        self.assertEqual(files[0]["status"], "M")
        self.assertEqual(files[1]["status"], "A")
        self.assertEqual(files[0]["additions"], 2)
        self.assertEqual(files[0]["deletions"], 1)
        self.assertEqual(len(files[0]["hunks"]), 1)
        self.assertEqual(fake.calls[2].full_url, next_url, "Link ヘッダの rel=\"next\" を追従すること")

    def test_compare_fetch_uses_three_dot_and_resolves_head_commit(self):
        compare = {
            "base_commit": {"sha": "basesha"},
            "commits": [{"sha": "midsha"}, {"sha": "headsha999"}],
            "files": [{"filename": "c.py", "status": "renamed", "additions": 1, "deletions": 1,
                       "previous_filename": "old_c.py", "sha": "shac", "patch": PR_PATCH_A}],
        }
        fake = fake_urlopen_sequence([(200, compare, {})])
        with mock.patch("diff_review.urllib.request.urlopen", fake):
            opts = dr.GithubOpts(dr.DEFAULT_GITHUB_API_BASE, None)
            target, files = dr.collect_diff_github_compare(opts, "o", "r", "main...feature", 2000)
        self.assertEqual(target["source"], "github-compare")
        self.assertEqual(target["range"], "o/r@main...feature")
        self.assertEqual(target["base_commit"], "headsha999", "commits の最後＝head 側")
        self.assertEqual(files[0]["old_path"], "old_c.py")
        self.assertEqual(files[0]["status"], "R")
        self.assertIn("main...feature", fake.calls[0].full_url)

    def test_authorization_header_present_only_when_token_given(self):
        fake = fake_urlopen_sequence([(200, {"head": {"sha": "s"}, "base": {"sha": "b"}}, {}),
                                      (200, [], {})])
        with mock.patch("diff_review.urllib.request.urlopen", fake):
            opts = dr.GithubOpts(dr.DEFAULT_GITHUB_API_BASE, None)
            dr.collect_diff_github_pr(opts, "o", "r", "1", 2000)
        self.assertNotIn("Authorization", fake.calls[0].headers)

        fake2 = fake_urlopen_sequence([(200, {"head": {"sha": "s"}, "base": {"sha": "b"}}, {}),
                                       (200, [], {})])
        with mock.patch("diff_review.urllib.request.urlopen", fake2):
            opts = dr.GithubOpts(dr.DEFAULT_GITHUB_API_BASE, "tok123")
            dr.collect_diff_github_pr(opts, "o", "r", "1", 2000)
        self.assertEqual(fake2.calls[0].headers.get("Authorization"), "Bearer tok123")

    def test_api_base_override_changes_the_request_url(self):
        fake = fake_urlopen_sequence([(200, {"head": {"sha": "s"}, "base": {"sha": "b"}}, {}),
                                      (200, [], {})])
        with mock.patch("diff_review.urllib.request.urlopen", fake):
            opts = dr.GithubOpts("https://ghe.example.com/api/v3", None)
            dr.collect_diff_github_pr(opts, "o", "r", "1", 2000)
        self.assertTrue(fake.calls[0].full_url.startswith("https://ghe.example.com/api/v3/"))

    def test_http_error_reports_status_and_message_and_dies_with_exit_network(self):
        fake = fake_urlopen_sequence([(404, {"message": "Not Found"}, {})])
        with mock.patch("diff_review.urllib.request.urlopen", fake):
            opts = dr.GithubOpts(dr.DEFAULT_GITHUB_API_BASE, None)
            with self.assertRaises(SystemExit) as ctx:
                dr.collect_diff_github_pr(opts, "o", "r", "999999", 2000)
        self.assertEqual(ctx.exception.code, dr.EXIT_NETWORK)

    def test_rate_limit_hint_is_included_when_remaining_is_zero(self):
        fake = fake_urlopen_sequence([
            (403, {"message": "API rate limit exceeded"},
             {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "2000000000"}),
        ])
        with mock.patch("diff_review.urllib.request.urlopen", fake):
            opts = dr.GithubOpts(dr.DEFAULT_GITHUB_API_BASE, None)
            try:
                dr.collect_diff_github_pr(opts, "o", "r", "1", 2000)
                self.fail("SystemExit が要る")
            except SystemExit:
                pass

    def test_github_pr_spec_accepts_url_and_slug(self):
        self.assertEqual(dr.parse_github_pr_spec("o/r#123"), ("o", "r", "123"))
        self.assertEqual(dr.parse_github_pr_spec("https://github.com/o/r/pull/123"),
                         ("o", "r", "123"))
        self.assertEqual(dr.parse_github_pr_spec("https://github.com/o/r/pull/123/files"),
                         ("o", "r", "123"))
        with self.assertRaises(SystemExit):
            dr.parse_github_pr_spec("not-a-valid-spec")

    def test_github_digest_is_order_independent_and_deterministic(self):
        files_a = [{"filename": "a.py", "sha": "1", "status": "modified", "patch": "x"},
                  {"filename": "b.py", "sha": "2", "status": "added", "patch": "y"}]
        files_b = list(reversed(files_a))
        self.assertEqual(dr.github_digest(files_a), dr.github_digest(files_b))
        self.assertTrue(dr.github_digest(files_a).startswith("gh1:"))

    def test_resolve_github_token_priority(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "from-env", "GH_TOKEN": "from-gh"}):
            self.assertEqual(dr.resolve_github_token("from-cli"), "from-cli")
            self.assertEqual(dr.resolve_github_token(None), "from-env")
        with mock.patch.dict(os.environ, {"GH_TOKEN": "from-gh"}, clear=True):
            self.assertEqual(dr.resolve_github_token(None), "from-gh")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(dr.resolve_github_token(None))

    def test_expand_is_none_when_expand_max_lines_is_zero(self):
        entry = {"path": "a.py", "old_path": None, "status": "M"}
        f = {"additions": 2, "deletions": 1, "patch": PR_PATCH_A}
        built = dr.build_file_from_github(f, entry, 0)
        self.assertIsNone(built["expand"])

    def test_expand_reuses_the_truncated_display_when_files_have_a_gap(self):
        entry = {"path": "a.py", "old_path": None, "status": "M"}
        f = {"additions": 2, "deletions": 1, "patch": PR_PATCH_A}
        built = dr.build_file_from_github(f, entry, 2000)
        self.assertEqual(built["expand"], {"truncated": True, "count": 4})
        self.assertIsNone(built["rich"], "rich diff は今回スコープ外（decisions.md D5）")


# --------------------------------------------------------------------------
# 画面の受け入れ確認に使う固定入力（tests/fixture_repo.py）が、
# **検査の前提を実際に含んでいる**こと。
#
# 作業ツリーの差分を入力にしていたら、リポジトリの状態で検査が通ったり落ちたりした
# （スレッドが 150 件作れない / 展開ボタンが無い / ツリーのディレクトリが無い）。
# 前提は入力側で作り、その入力が前提を満たしていることをここで固定する。
# --------------------------------------------------------------------------

class FixtureRepoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.tmp.name) / "fixture"
        fixture_repo.build(str(cls.repo))
        _target, cls.files = dr.collect_diff(str(cls.repo), "staged", None, 3)
        cls.by_path = {f["path"]: f for f in cls.files}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_has_the_awkward_shapes(self):
        paths = set(self.by_path)
        self.assertGreaterEqual(len(paths), 6, paths)
        statuses = {f["status"] for f in self.files}
        self.assertIn("A", statuses, "新規ファイルが要る")
        self.assertIn("D", statuses, "削除ファイルが要る")
        self.assertIn("M", statuses, "変更ファイルが要る")
        depths = {p.split("/")[0] for p in paths}
        self.assertGreaterEqual(len(depths), 2, "ツリー表示の検査には 2 つ以上の親が要る: %s" % depths)

    def test_first_hunk_at_line_one_with_a_later_gap(self):
        """**ここが壊れていた**——先頭行から始まるハンクを持ち、後ろにも隙間があるファイル。

        `gapsOf` が「隙間なし」を null で返す位置で、`expandAll` が例外を投げて
        **ファイルの展開が丸ごと起きなかった**。入力にこの形が無いと、検査が素通りする。
        """
        entry = self.by_path["src/core/engine.py"]
        self.assertFalse(entry["expand"]["truncated"], "展開データが要る")
        first = entry["hunks"][0]
        starts_at_one = any(l["new"] == 1 for l in first["lines"])
        self.assertTrue(starts_at_one, "最初のハンクが 1 行目から始まること: %s" % first["header"])
        last_new = max(l["new"] for h in entry["hunks"] for l in h["lines"] if l["new"])
        self.assertLess(last_new, entry["expand"]["count"],
                        "最後のハンクより後ろにも行が残っていること（＝後ろにも隙間）")

    def test_deleted_file_expands_on_the_old_side(self):
        entry = self.by_path["src/api/legacy.py"]
        self.assertEqual(entry["status"], "D")
        self.assertEqual(entry["expand"]["side"], "old",
                         "削除ファイルの展開データは旧側。画面もこの側に従う")

    def test_has_replacements_for_split_pairing(self):
        entry = self.by_path["src/core/util.py"]
        kinds = [l["kind"] for h in entry["hunks"] for l in h["lines"]]
        self.assertIn("add", kinds)
        self.assertIn("del", kinds)

    def test_has_rich_targets(self):
        rich = {p for p, f in self.by_path.items() if f.get("rich")}
        self.assertTrue(any(p.endswith(".md") for p in rich), rich)
        self.assertTrue(any(p.endswith(".csv") for p in rich), rich)

    def test_fixture_is_deterministic(self):
        """同じ手順で作ったリポジトリからは、同じ差分が出る（検査が揺れない）。"""
        other = Path(self.tmp.name) / "fixture2"
        fixture_repo.build(str(other))
        _t, files = dr.collect_diff(str(other), "staged", None, 3)
        self.assertEqual(dr.dumps_canonical(files), dr.dumps_canonical(self.files))


# --------------------------------------------------------------------------
# 指摘を「書く」側（20260916-diff-review-authoring）
# --------------------------------------------------------------------------

class AnchorRuleTest(unittest.TestCase):
    """指摘できる位置の規則。**画面 app.js の anchorOf と同じでなければならない**。

    画面との一致そのものはブラウザが要るので test 工程で測る（research F3 の 307/307）。
    ここで固定するのは規則の中身——どの行がどちら側の位置を持つか。
    """

    def test_anchor_of_each_kind(self):
        self.assertEqual(dr.anchor_of({"kind": "del", "old": 5, "new": None}), ("LEFT", 5))
        self.assertEqual(dr.anchor_of({"kind": "add", "old": None, "new": 7}), ("RIGHT", 7))
        self.assertEqual(dr.anchor_of({"kind": "ctx", "old": 5, "new": 7}), ("RIGHT", 7))
        # 旧側しか番号が無い文脈行（削除されたファイルの展開）
        self.assertEqual(dr.anchor_of({"kind": "ctx", "old": 9, "new": None}), ("LEFT", 9))
        self.assertIsNone(dr.anchor_of({"kind": "ctx", "old": None, "new": None}))

    def test_expand_side_decides_where_expanded_lines_land(self):
        entry = {"hunks": [], "expand": {"count": 3, "side": "old", "truncated": False}}
        self.assertEqual(dr.valid_anchors(entry), {("LEFT", 1), ("LEFT", 2), ("LEFT", 3)})
        entry["expand"]["side"] = "new"
        self.assertEqual(dr.valid_anchors(entry), {("RIGHT", 1), ("RIGHT", 2), ("RIGHT", 3)})

    def test_truncated_expand_offers_nothing_extra(self):
        entry = {"hunks": [], "expand": {"count": 9999, "side": "new", "truncated": True}}
        self.assertEqual(dr.valid_anchors(entry), set())

    def test_side_defaults_to_right_when_both_exist(self):
        # 置き換えられた行では両側が有効になる（実測 10/297）。既定は RIGHT——**規約**。
        anchors = {("LEFT", 12), ("RIGHT", 12), ("LEFT", 20)}
        self.assertEqual(dr.resolve_side(anchors, 12, None), "RIGHT")
        self.assertEqual(dr.resolve_side(anchors, 20, None), "LEFT")
        self.assertEqual(dr.resolve_side(anchors, 12, "LEFT"), "LEFT", "明示が優先される")

    def test_ranges_are_folded_for_reading(self):
        self.assertEqual(dr.format_ranges([1, 2, 3, 5, 9, 10, 11, 20]), "1-3, 5, 9-11, 20")
        self.assertEqual(dr.format_ranges([]), "なし")


class AuthoringTest(unittest.TestCase):
    """`comment` / `resolve` / `submit`。入力は固定のリポジトリ（tests/fixture_repo.py）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.src = Path(cls.tmp.name) / "fixture"
        fixture_repo.build(str(cls.src))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.dir = Path(self.work.name)
        code, out, err = cli(self.src, "bundle", "--repo", ".", "--from", "staged")
        self.assertEqual(code, 0, err)
        self.bundle = self.dir / ("b" + dr.BUNDLE_EXT)
        self.bundle.write_text(out, encoding="utf-8", newline="\n")

    def run_cli(self, *args):
        return cli(self.dir, *args)

    def record(self):
        return dr.parse_bundle(self.bundle.read_text(encoding="utf-8"))["review"]

    # ---------------------------------------------------------------- 足す

    def test_adds_a_review_comment(self):
        code, _out, err = self.run_cli("comment", self.bundle.name,
                                       "--path", "src/core/util.py", "--line", "12",
                                       "--severity", "must", "--body", "空文字で落ちます")
        self.assertEqual(code, 0, err)
        thread = self.record()["threads"][0]
        self.assertEqual((thread["kind"], thread["path"], thread["line"], thread["side"]),
                         ("review", "src/core/util.py", 12, "RIGHT"))
        self.assertEqual(thread["comments"][0]["severity"], "must")
        self.assertIsNone(thread["comments"][0]["review_id"], "提出するまでは未提出")

    def test_adds_a_note(self):
        code, _out, err = self.run_cli("comment", self.bundle.name,
                                       "--path", "src/api/router.py", "--note",
                                       "--body", "意図的にこの形にしています")
        self.assertEqual(code, 0, err)
        thread = self.record()["threads"][0]
        self.assertEqual(thread["kind"], "note")
        self.assertIsNone(thread["comments"][0]["severity"])
        self.assertIsNone(thread["comments"][0]["review_id"])

    def test_replies_and_replies_to_replies(self):
        self.run_cli("comment", self.bundle.name, "--path", "src/core/util.py",
                     "--line", "12", "--body", "元の指摘")
        self.run_cli("comment", self.bundle.name, "--reply-to", "t1",
                     "--body", "直しました", "--author", "human")
        code, _out, err = self.run_cli("comment", self.bundle.name, "--reply-to", "t1",
                                       "--body", "確認しました")
        self.assertEqual(code, 0, err)
        comments = self.record()["threads"][0]["comments"]
        self.assertEqual([(c["id"], c["in_reply_to"]) for c in comments],
                         [("c1", None), ("c2", "c1"), ("c3", "c2")],
                         "返信の既定は**その時点の最後のコメント**")

    def test_reply_to_a_specific_comment(self):
        self.run_cli("comment", self.bundle.name, "--path", "src/core/util.py",
                     "--line", "12", "--body", "元")
        self.run_cli("comment", self.bundle.name, "--reply-to", "t1", "--body", "返信1")
        self.run_cli("comment", self.bundle.name, "--reply-to", "t1:c1", "--body", "c1 への返信")
        comments = self.record()["threads"][0]["comments"]
        self.assertEqual(comments[2]["in_reply_to"], "c1")

    def test_ids_continue_from_what_is_there(self):
        for line in (12, 13, 14):
            self.run_cli("comment", self.bundle.name, "--path", "src/core/util.py",
                         "--line", str(line), "--body", "x")
        self.assertEqual([t["id"] for t in self.record()["threads"]], ["t1", "t2", "t3"])

    def test_file_and_overall_scopes(self):
        self.run_cli("comment", self.bundle.name, "--path", "src/core/util.py", "--body", "ファイル")
        self.run_cli("comment", self.bundle.name, "--body", "全体")
        threads = self.record()["threads"]
        scopes = {(t["path"], t["line"], t["side"]) for t in threads}
        self.assertIn(("src/core/util.py", None, None), scopes)
        self.assertIn((None, None, None), scopes)

    # ------------------------------------------------------------ 位置の検証

    def test_rejects_a_line_that_is_not_in_the_diff(self):
        before = self.bundle.read_bytes()
        code, out, err = self.run_cli("comment", self.bundle.name,
                                      "--path", "src/core/util.py", "--line", "999",
                                      "--body", "x")
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("存在しません", err)
        self.assertIn("指摘できる位置", err, "手がかりを出すこと（「駄目」だけでは直せない）")
        self.assertEqual(self.bundle.read_bytes(), before, "**1 バイトも変えない**")

    def test_rejects_a_file_that_is_not_in_the_diff(self):
        code, _out, err = self.run_cli("comment", self.bundle.name,
                                       "--path", "nope.py", "--line", "1", "--body", "x")
        self.assertEqual(code, 3)
        self.assertIn("差分にあるファイル", err, "打ち間違いに気づけるよう候補を出す")

    def test_rejects_a_missing_file_even_without_a_line(self):
        """**ファイル単位のコメントでもパスの実在を見る。**

        見ないと、差分に無いファイルへのコメントが素通りして画面で「位置不明」に落ちる
        ——行の指定が無いだけで、穴としては行の場合と同じ。
        """
        before = self.bundle.read_bytes()
        code, _out, err = self.run_cli("comment", self.bundle.name,
                                       "--path", "totally/made/up.py", "--body", "x")
        self.assertEqual(code, 3)
        self.assertIn("差分に含まれていません", err)
        self.assertEqual(self.bundle.read_bytes(), before)

    def test_hints_the_other_side_when_that_is_where_the_line_lives(self):
        # 削除ファイルの行は LEFT にしかない。RIGHT を明示したら「反対側にある」と伝える。
        code, _out, err = self.run_cli("comment", self.bundle.name,
                                       "--path", "src/api/legacy.py", "--line", "3",
                                       "--side", "RIGHT", "--body", "x")
        self.assertEqual(code, 3)
        self.assertIn("反対の側", err)

    def test_side_is_resolved_when_omitted(self):
        # 削除ファイルには LEFT しか無いので、省略しても LEFT に決まる
        code, _out, err = self.run_cli("comment", self.bundle.name,
                                       "--path", "src/api/legacy.py", "--line", "3",
                                       "--body", "消してよいか")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.record()["threads"][0]["side"], "LEFT")

    def test_record_json_needs_a_repo_to_check_anchors(self):
        code, out, _err = cli(self.src, "template", "--repo", ".", "--from", "staged")
        path = self.dir / "r.json"
        path.write_text(out, encoding="utf-8", newline="\n")
        code, _out, err = self.run_cli("comment", "r.json",
                                       "--path", "src/core/util.py", "--line", "12", "--body", "x")
        self.assertEqual(code, 1)
        self.assertIn("--repo", err)

    # ------------------------------------------------------- 排他な指定を弾く

    def test_rejects_contradictory_options(self):
        cases = [
            (["--note", "--severity", "must", "--path", "src/core/util.py",
              "--line", "12", "--body", "x"], "重大度は付けられません"),
            (["--reply-to", "t1", "--path", "src/core/util.py", "--body", "x"], "位置は指定できません"),
            (["--path", "src/core/util.py", "--line", "12", "--body", "   "], "本文が空"),
            (["--reply-to", "t9", "--body", "x"], "がありません"),
        ]
        for args, needle in cases:
            code, _out, err = self.run_cli("comment", self.bundle.name, *args)
            self.assertEqual(code, 3, args)
            self.assertIn(needle, err, args)

    def test_line_without_path_is_rejected(self):
        code, _out, err = self.run_cli("comment", self.bundle.name, "--line", "12", "--body", "x")
        self.assertEqual(code, 3)
        self.assertIn("--path", err)

    # ------------------------------------------------------------- 本文の受け口

    def test_body_from_file_and_stdin(self):
        body = "複数行の本文。\n2 行目に `</script>` が入る。\n"
        (self.dir / "body.txt").write_text(body, encoding="utf-8", newline="\n")
        self.run_cli("comment", self.bundle.name, "--path", "src/core/util.py",
                     "--line", "12", "--body-file", "body.txt")
        self.assertEqual(self.record()["threads"][0]["comments"][0]["body"], body)

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "comment", self.bundle.name,
             "--path", "src/core/util.py", "--line", "13", "--body-file", "-"],
            cwd=str(self.dir), input=body.encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(self.record()["threads"][1]["comments"][0]["body"], body)

    def test_body_and_body_file_together_are_rejected(self):
        code, _out, err = self.run_cli("comment", self.bundle.name, "--path", "src/core/util.py",
                                       "--line", "12", "--body", "a", "--body-file", "b.txt")
        self.assertEqual(code, 1)
        self.assertIn("同時に使えません", err)

    # ------------------------------------------------------- resolve / submit

    def test_resolve_and_undo(self):
        self.run_cli("comment", self.bundle.name, "--path", "src/core/util.py",
                     "--line", "12", "--body", "x")
        self.run_cli("resolve", self.bundle.name, "--thread", "t1")
        self.assertTrue(self.record()["threads"][0]["resolved"])
        self.run_cli("resolve", self.bundle.name, "--thread", "t1", "--undo")
        self.assertFalse(self.record()["threads"][0]["resolved"])

    def test_resolve_refuses_a_note(self):
        self.run_cli("comment", self.bundle.name, "--path", "src/api/router.py",
                     "--note", "--body", "説明")
        code, _out, err = self.run_cli("resolve", self.bundle.name, "--thread", "t1")
        self.assertEqual(code, 1)
        self.assertIn("解決の対象ではありません", err)

    def test_submit_attaches_pending_review_comments_only(self):
        self.run_cli("comment", self.bundle.name, "--path", "src/core/util.py",
                     "--line", "12", "--severity", "must", "--body", "指摘")
        self.run_cli("comment", self.bundle.name, "--reply-to", "t1", "--body", "返信")
        self.run_cli("comment", self.bundle.name, "--path", "src/api/router.py",
                     "--note", "--body", "説明")
        code, _out, err = self.run_cli("submit", self.bundle.name,
                                       "--state", "CHANGES_REQUESTED", "--body", "まとめ")
        self.assertEqual(code, 0, err)
        record = self.record()
        self.assertEqual(record["reviews"][0]["state"], "CHANGES_REQUESTED")
        review_thread = [t for t in record["threads"] if t["kind"] == "review"][0]
        note_thread = [t for t in record["threads"] if t["kind"] == "note"][0]
        self.assertTrue(all(c["review_id"] == "r1" for c in review_thread["comments"]))
        self.assertIsNone(note_thread["comments"][0]["review_id"],
                          "説明は提出の対象ではない")
        self.assertEqual(dr.validate(record), [])


class BatchAuthoringTest(unittest.TestCase):
    """まとめて足す。**1 件でも駄目なら 1 件も書かない**が要。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.src = Path(cls.tmp.name) / "fixture"
        fixture_repo.build(str(cls.src))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.dir = Path(self.work.name)
        _code, out, _err = cli(self.src, "bundle", "--repo", ".", "--from", "staged")
        self.bundle = self.dir / ("b" + dr.BUNDLE_EXT)
        self.bundle.write_text(out, encoding="utf-8", newline="\n")

    def batch(self, specs):
        path = self.dir / "batch.json"
        path.write_text(json.dumps(specs, ensure_ascii=False), encoding="utf-8", newline="\n")
        return cli(self.dir, "comment", self.bundle.name, "--batch", "batch.json")

    def record(self):
        return dr.parse_bundle(self.bundle.read_text(encoding="utf-8"))["review"]

    def test_all_or_nothing(self):
        before = self.bundle.read_bytes()
        code, _out, err = self.batch([
            {"path": "src/core/util.py", "line": 5, "body": "これは通る"},
            {"path": "src/core/util.py", "line": 999, "body": "行が無い"},
            {"path": "nope.py", "line": 1, "body": "ファイルが無い"},
            {"body": "綴り違い", "typo": 1},
        ])
        self.assertEqual(code, 3)
        self.assertEqual(self.bundle.read_bytes(), before, "**1 件も書かない**")
        # 1 件目で止めず、**全件ぶん**報告する（AI が 1 往復で直せるように）
        self.assertIn("[2]", err)
        self.assertIn("[3]", err)
        self.assertIn("[4]", err)
        self.assertIn("知らないキー", err)

    def test_writes_everything_when_all_are_good(self):
        code, _out, err = self.batch([
            {"path": "src/core/util.py", "line": 5, "severity": "nit", "body": "命名"},
            {"path": "src/api/legacy.py", "line": 3, "side": "LEFT", "body": "消した理由"},
            {"note": True, "path": "src/api/router.py", "body": "新規です"},
            {"body": "全体へ"},
        ])
        self.assertEqual(code, 0, err)
        record = self.record()
        self.assertEqual(len(record["threads"]), 4)
        self.assertEqual(dr.validate(record), [])

    def test_batch_can_reply_to_a_thread_added_earlier_in_the_same_run(self):
        # 同じ実行の中で作ったスレッドには**返信できない**（検証は書く前に全件やるため）。
        # 黙って落とさず、理由が出ること。
        code, _out, err = self.batch([
            {"path": "src/core/util.py", "line": 5, "body": "元"},
            {"reply_to": "t1", "body": "同じ実行の中での返信"},
        ])
        self.assertEqual(code, 3)
        self.assertIn("t1 がありません", err)

    def test_batch_must_be_a_list(self):
        path = self.dir / "batch.json"
        path.write_text('{"path": "a"}', encoding="utf-8", newline="\n")
        code, _out, err = cli(self.dir, "comment", self.bundle.name, "--batch", "batch.json")
        self.assertEqual(code, 1)
        self.assertIn("配列", err)


class AuthoringOutputTest(unittest.TestCase):
    """入力の種類を保つこと・決定論・書いたあと check が通ること。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.src = Path(cls.tmp.name) / "fixture"
        fixture_repo.build(str(cls.src))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.dir = Path(self.work.name)

    def make_bundle(self, name="b" + dr.BUNDLE_EXT):
        _code, out, _err = cli(self.src, "bundle", "--repo", ".", "--from", "staged")
        path = self.dir / name
        path.write_text(out, encoding="utf-8", newline="\n")
        return path

    def test_a_bundle_stays_a_bundle(self):
        path = self.make_bundle()
        cli(self.dir, "comment", path.name, "--path", "src/core/util.py",
            "--line", "12", "--body", "x")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(dr.looks_like_bundle(text), "バンドルを渡したらバンドルで返す")
        bundle = dr.parse_bundle(text)
        self.assertEqual(len(bundle["files"]), 7, "差分は残っている")
        self.assertEqual(len(bundle["review"]["threads"]), 1)

    def test_a_record_stays_a_record(self):
        _code, out, _err = cli(self.src, "template", "--repo", ".", "--from", "staged")
        path = self.dir / "r.json"
        path.write_text(out, encoding="utf-8", newline="\n")
        cli(self.dir, "comment", "r.json", "--repo", str(self.src), "--from", "staged",
            "--path", "src/core/util.py", "--line", "12", "--body", "x")
        text = path.read_text(encoding="utf-8")
        self.assertFalse(dr.looks_like_bundle(text))
        self.assertEqual(json.loads(text)["schema"], dr.SCHEMA)

    def test_out_to_another_file_and_stdout(self):
        path = self.make_bundle()
        before = path.read_bytes()
        code, _out, err = cli(self.dir, "comment", path.name, "--path", "src/core/util.py",
                              "--line", "12", "--body", "x", "--out", "other" + dr.BUNDLE_EXT)
        self.assertEqual(code, 0, err)
        self.assertEqual(path.read_bytes(), before, "--out を指定したら入力は変えない")
        self.assertTrue((self.dir / ("other" + dr.BUNDLE_EXT)).exists())

        code, out, err = cli(self.dir, "comment", path.name, "--path", "src/core/util.py",
                             "--line", "12", "--body", "x", "--out", "-")
        self.assertEqual(code, 0, err)
        self.assertTrue(dr.looks_like_bundle(out))
        self.assertEqual(path.read_bytes(), before)

    def test_deterministic(self):
        first, second = self.make_bundle("a" + dr.BUNDLE_EXT), self.make_bundle("b" + dr.BUNDLE_EXT)
        for path in (first, second):
            cli(self.dir, "comment", path.name, "--path", "src/core/util.py",
                "--line", "12", "--severity", "must", "--body", "同じ本文")
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_check_passes_after_writing(self):
        path = self.make_bundle()
        cli(self.dir, "comment", path.name, "--path", "src/core/util.py",
            "--line", "12", "--severity", "must", "--body", "x")
        cli(self.dir, "comment", path.name, "--reply-to", "t1", "--body", "返信")
        cli(self.dir, "submit", path.name, "--state", "APPROVED", "--body", "よいです")
        code, out, err = cli(self.dir, "check", path.name, "--anchors")
        self.assertEqual(code, 0, err + out)

    def test_check_anchors_catches_a_file_level_comment_on_a_missing_file(self):
        path = self.make_bundle()
        bundle = dr.parse_bundle(path.read_text(encoding="utf-8"))
        bundle["review"] = dr.empty_review(bundle["target"])
        bundle["review"]["threads"] = [{
            "id": "t1", "kind": "review", "path": "gone/away.py", "line": None,
            "side": None, "start_line": None, "start_side": None, "resolved": False,
            "comments": [{"id": "c1", "review_id": None, "author": "ai",
                          "body": "差分に無いファイルへのファイル単位コメント",
                          "severity": None, "in_reply_to": None}],
        }]
        path.write_text(dr.bundle_text(bundle["target"], bundle["files"],
                                       bundle["rich_enabled"], bundle["review"]),
                        encoding="utf-8", newline="\n")
        code, _out, err = cli(self.dir, "check", path.name, "--anchors")
        self.assertEqual(code, 3)
        self.assertIn("差分に含まれていません", err)

    def test_check_anchors_catches_a_bad_line(self):
        path = self.make_bundle()
        bundle = dr.parse_bundle(path.read_text(encoding="utf-8"))
        bundle["review"] = dr.empty_review(bundle["target"])
        bundle["review"]["threads"] = [{
            "id": "t1", "kind": "review", "path": "src/core/util.py", "line": 9999,
            "side": "RIGHT", "start_line": None, "start_side": None, "resolved": False,
            "comments": [{"id": "c1", "review_id": None, "author": "ai",
                          "body": "手で書いた（行が無い）", "severity": None, "in_reply_to": None}],
        }]
        path.write_text(dr.bundle_text(bundle["target"], bundle["files"],
                                       bundle["rich_enabled"], bundle["review"]),
                        encoding="utf-8", newline="\n")
        code, _out, _err = cli(self.dir, "check", path.name)
        self.assertEqual(code, 0, "既定では位置を見ない（既存の意味を変えない）")
        code, _out, err = cli(self.dir, "check", path.name, "--anchors")
        self.assertEqual(code, 3, "--anchors なら捕まえる")
        self.assertIn("存在しません", err)
