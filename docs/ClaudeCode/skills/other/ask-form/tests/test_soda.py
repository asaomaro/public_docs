"""ask-form: Sodashitsu の pane の中で、sodactl ask --features で確かめて画面内に出す分岐（ask.ask_via_soda）を、
偽の sodactl（PATH の先頭に置く小さなスクリプト）で確かめる。実物の sodactl・soda サーバは使わない。"""
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

AF = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AF)
import ask  # noqa: E402

# 偽の sodactl。呼ばれた引数と標準入力を $FAKE_LOG に 1 行の JSON で足す。
# --features は $FAKE_FEATURES_EXIT（既定 0）で終わり、$FAKE_FEATURES を出す。ask は $FAKE_ASK_EXIT で終わり、$FAKE_ASK_OUT・$FAKE_ASK_ERR を出す。
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
stdin = "" if "--features" in args else sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"args": args, "stdin": stdin}) + "\n")
if "--features" in args:
    code = int(os.environ.get("FAKE_FEATURES_EXIT", "0"))
    if code == 0:
        print(os.environ["FAKE_FEATURES"])
    else:
        sys.stderr.write("usage error\n")
    sys.exit(code)
print(os.environ.get("FAKE_ASK_OUT", ""))
sys.stderr.write(os.environ.get("FAKE_ASK_ERR", ""))
sys.exit(int(os.environ.get("FAKE_ASK_EXIT", "0")))
'''
ALL = ["media", "view", "types:edit", "types:rank", "types:table", "remote-image"]
LIMITS = {"fileBytes": 100, "textBytes": 50, "totalBytes": 150, "files": 3, "serverBytes": 10 ** 9, "views": 2}
ANSWERED = json.dumps({"status": "answered", "answers": {"q": "a"}})


def features(server_features=ALL, server=True, sodactl=ALL, limits=LIMITS):
    return json.dumps({"sodactl": sodactl, "limits": limits, "server": {"features": server_features, "limits": {}} if server else None})


PLAIN = {"questions": [{"id": "q", "label": "Q", "options": ["a", "b"]}]}


def spec(**extra):
    s = json.loads(json.dumps(PLAIN))
    s.update(extra)
    return s


class SodaFeatures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = os.path.realpath(self.tmp.name)
        bindir = os.path.join(self.dir, "bin")
        os.mkdir(bindir)
        fake = os.path.join(bindir, "sodactl")
        open(fake, "w").write(FAKE)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.dir, "log.jsonl")
        env = {"PATH": bindir + os.pathsep + os.environ["PATH"], "SODA_PANE_ID": "p1", "FAKE_LOG": self.log,
               "FAKE_FEATURES": features(), "FAKE_ASK_OUT": ANSWERED}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("ASK_FORM_SODA", None)
        self.work = os.path.join(self.dir, "work")
        os.mkdir(self.work)

    def calls(self):
        return [json.loads(l) for l in open(self.log)] if os.path.exists(self.log) else []

    def write(self, name, size=1):
        path = os.path.join(self.work, name)
        open(path, "wb").write(b"x" * size)
        return path

    def run_soda(self, raw, timeout=60):
        """main と同じ手順（書かれたままの定義を normalize の前に写す）で ask_via_soda を呼ぶ。"""
        copy = json.loads(json.dumps(raw))
        normalized = ask.normalize(copy, self.work)
        normalized.pop("_files"), normalized.pop("_views")
        return ask.ask_via_soda(normalized, timeout, raw, self.work)

    def test_plain_definition_skips_features(self):
        """single・multi・text だけの定義は、確かめずに今までどおり渡す。"""
        self.assertEqual(self.run_soda(spec())["status"], "answered")
        self.assertEqual([c["args"][:2] for c in self.calls()], [["ask", "--timeout"]])

    def test_features_ok_passes_to_sodactl(self):
        img = self.write("a.png")
        raw = spec(view={"file": self.write("o.html")})
        raw["questions"][0]["options"] = [{"value": "a", "image": img}, {"value": "b", "image": "https://example.com/b.png"}]
        raw["questions"].append({"id": "r", "label": "R", "type": "rank", "options": ["x", "y"]})
        self.assertEqual(self.run_soda(raw)["status"], "answered")
        calls = self.calls()
        self.assertEqual(calls[0]["args"], ["ask", "--features"])
        self.assertEqual(calls[1]["args"][0], "ask")
        sent = json.loads(calls[1]["stdin"])
        self.assertEqual(sent["questions"][0]["options"][0]["image"], img)
        self.assertEqual(sent["questions"][0]["options"][1]["image"], "https://example.com/b.png")   # URL はそのまま

    def test_missing_feature_falls_to_window(self):
        for need, missing in (("view", "view"), ("remote", "remote-image"), ("rank", "types:rank")):
            os.environ["FAKE_FEATURES"] = features(server_features=[f for f in ALL if f != missing])
            raw = spec()
            if need == "view":
                raw["view"] = {"text": "hi"}
            elif need == "remote":
                raw["questions"][0]["options"] = [{"value": "a", "image": "https://example.com/a.png"}, "b"]
            else:
                raw["questions"][0]["type"] = "rank"
            if os.path.exists(self.log):
                os.remove(self.log)
            self.assertIsNone(self.run_soda(raw), need)
            self.assertEqual([c["args"] for c in self.calls()], [["ask", "--features"]], need)   # ask は呼ばない

    def test_sodactl_side_missing_feature_falls_to_window(self):
        os.environ["FAKE_FEATURES"] = features(sodactl=["media"])
        self.assertIsNone(self.run_soda(spec(view={"text": "hi"})))

    def test_old_sodactl_features_exit_2(self):
        os.environ["FAKE_FEATURES_EXIT"] = "2"
        self.assertIsNone(self.run_soda(spec(view={"text": "hi"})))
        self.assertEqual([c["args"] for c in self.calls()], [["ask", "--features"]])

    def test_no_server(self):
        os.environ["FAKE_FEATURES"] = features(server=False)
        self.assertIsNone(self.run_soda(spec(view={"text": "hi"})))
        self.assertEqual(len(self.calls()), 1)

    def test_relative_paths_become_absolute_from_base_dir(self):
        self.write("a.png"), self.write("s.mp3"), self.write("o.md")
        raw = spec(view="o.md")
        raw["questions"][0]["options"] = [{"value": "a", "image": "a.png", "audio": "./s.mp3"}, "b"]
        # 偽の sodactl の cwd は定義の場所ではない（sodactl は自分の cwd から解くので、ここで直さないとずれる）
        self.assertEqual(self.run_soda(raw)["status"], "answered")
        sent = json.loads(self.calls()[1]["stdin"])
        opt = sent["questions"][0]["options"][0]
        self.assertEqual(opt["image"], os.path.join(self.work, "a.png"))
        self.assertEqual(opt["audio"], os.path.join(self.work, "s.mp3"))
        self.assertEqual(sent["view"]["file"], os.path.join(self.work, "o.md"))

    def test_review_spec_view_files_are_absolute(self):
        self.write("o.html"), self.write("n.md")
        self.assertEqual(self.run_soda(ask.review_spec(["o.html", "n.md"]))["status"], "answered")
        sent = json.loads(self.calls()[1]["stdin"])
        self.assertEqual([v["file"] for v in sent["view"]], [os.path.join(self.work, "o.html"), os.path.join(self.work, "n.md")])

    def test_limit_exceeded_refuses_without_window(self):
        for name, raw_fn, n in (
            ("file", lambda: spec(view={"file": self.write("big.html", 101)}), 1),
            ("text", lambda: spec(view={"file": self.write("big.md", 51)}), 1),
            ("total", lambda: spec(view=[{"file": self.write("a.html", 80)}, {"file": self.write("b.html", 80)}]), 1),
            ("views", lambda: spec(view=[{"text": "1"}, {"text": "2"}, {"text": "3"}]), 1),
        ):
            if os.path.exists(self.log):
                os.remove(self.log)
            with self.assertRaises(ask.SodaRefused, msg=name):
                self.run_soda(raw_fn())
            self.assertEqual(len(self.calls()), n, name)   # ask は呼ばない

    def test_too_many_files(self):
        raw = spec()
        raw["questions"][0]["options"] = [{"value": str(i), "image": self.write("%d.png" % i)} for i in range(4)]
        with self.assertRaises(ask.SodaRefused):
            self.run_soda(raw)

    def test_same_file_counts_once(self):
        img = self.write("a.png", 90)
        raw = spec()
        raw["questions"][0]["options"] = [{"value": "a", "image": img}, {"value": "b", "image": img}]   # 合計 180 ではなく 90
        self.assertEqual(self.run_soda(raw)["status"], "answered")

    def test_sodactl_exit_2_is_refused_not_window(self):
        os.environ.update(FAKE_ASK_EXIT="2", FAKE_ASK_OUT="", FAKE_ASK_ERR="invalid ask spec: bad")
        with self.assertRaises(ask.SodaRefused) as cm:
            self.run_soda(spec())
        self.assertIn("invalid ask spec: bad", str(cm.exception))

    def test_sodactl_exit_1_and_unavailable_fall_to_window(self):
        os.environ.update(FAKE_ASK_EXIT="1", FAKE_ASK_OUT="")
        self.assertIsNone(self.run_soda(spec()))
        os.environ.update(FAKE_ASK_EXIT="0", FAKE_ASK_OUT=json.dumps({"status": "unavailable", "reason": "x"}))
        self.assertIsNone(self.run_soda(spec()))

    def test_env_off_and_outside_pane(self):
        with mock.patch.dict(os.environ, {"ASK_FORM_SODA": "off"}):
            self.assertIsNone(self.run_soda(spec()))
        with mock.patch.dict(os.environ):
            os.environ.pop("SODA_PANE_ID")
            self.assertIsNone(self.run_soda(spec()))
        self.assertEqual(self.calls(), [])

    def test_features_call_has_short_timeout(self):
        self.assertLessEqual(ask.SODA_FEATURES_TIMEOUT, 5)


if __name__ == "__main__":
    unittest.main()
