"""diff_review.py のテスト（標準ライブラリのみ）。

    cd <skill>/tests && python3 -m unittest -v
    もしくは  python3 -m unittest discover -s <skill>/tests

画面（HTML）側の受け入れ確認はここでは行わない——ブラウザが要るため、別途 headless ブラウザで行う。
ここが見るのは script の責務: 差分のパース、決定論、エスケープ、検証、一覧、符号化と改行。
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))

import diff_review as dr  # noqa: E402  （パスを通してから読み込む）

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

    def test_contains_no_external_reference(self):
        _code, html, _err = cli(self.repo, "html", "--repo", ".")
        for marker in ("http://", "https://", "//cdn."):
            self.assertNotIn(marker, html, "オフラインで開けるよう外部参照を持たない")

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
        location, state, body = lines[0].split("\t")
        self.assertEqual(location, "plain.txt:2")
        self.assertEqual(state, "unresolved")
        self.assertEqual(body, "未解決の指摘")

    def test_japanese_survives_round_trip(self):
        raw = self.path.read_text(encoding="utf-8")
        again = dr.dumps_canonical(json.loads(raw))
        self.assertEqual(raw, again, "正規形は読み書きを往復してもバイト一致する")
        self.assertIn("日本 語.txt", again)


if __name__ == "__main__":
    unittest.main()
