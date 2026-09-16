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
import richdiff      # noqa: E402

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

    def test_contains_no_external_reference(self):
        _code, html, _err = cli(self.repo, "html", "--repo", ".")
        for marker in ("http://", "https://", "//cdn."):
            self.assertNotIn(marker, html, "オフラインで開けるよう外部参照を持たない")

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
