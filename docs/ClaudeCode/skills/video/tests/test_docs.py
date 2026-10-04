"""motion-video の説明書（SKILL.md と reference/）が、手順と資料に分かれたまま、互いを正しく指しているか。

SKILL.md は呼ぶたびに読み込まれるので、手順と毎回守ることだけに保つ（以前は 480 行・53KB あった）。
仕様の詳しい説明・一覧は reference/ に置き、SKILL.md から「いつ読むか」と一緒に指す。
"""
import glob
import os
import re
import unittest

import fakes

SKILL = os.path.join(fakes.MV, "SKILL.md")
REF = os.path.join(fakes.MV, "reference")
FILE = re.compile(r"`((?:\.\./|reference/|examples/)?[\w./-]+\.(?:md|json|js|py))`")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class SkillDoc(unittest.TestCase):
    def test_skill_md_stays_short(self):
        text = read(SKILL)
        self.assertLessEqual(len(text.splitlines()), 150, "SKILL.md は手順だけに。詳しい説明は reference/ へ")
        self.assertLessEqual(len(text.encode("utf-8")), 18000)

    def test_reference_files_linked_both_ways(self):
        text = read(SKILL)
        refs = {os.path.basename(p) for p in glob.glob(os.path.join(REF, "*.md"))}
        self.assertGreaterEqual(len(refs), 8)
        for name in refs:
            self.assertIn(name, text, "reference/%s が SKILL.md から指されていない（読むときが分からない）" % name)
        for name in set(re.findall(r"reference/([\w-]+\.md)", text)):
            self.assertIn(name, refs, "SKILL.md が指す reference/%s が無い" % name)

    def test_each_reference_says_when_to_read(self):
        for p in glob.glob(os.path.join(REF, "*.md")):
            lines = read(p).splitlines()
            with self.subTest(os.path.basename(p)):
                self.assertTrue(lines[0].startswith("# "))
                self.assertRegex(lines[2], r"読む", "2 行目に、いつ読むかを書く")

    def test_mentioned_files_exist(self):
        """説明書に書いたファイル名（`recipes.md`・`examples/…json`・`../tests/README.md` など）が実在する。"""
        roots = [fakes.MV, REF, os.path.join(fakes.MV, "examples")]
        elsewhere = ("kaisetsu.py", "sprite.py", "rig.json")   # yukkuri-kaisetsu のファイル（別のリポジトリ yukkuri-work にある）。ここでは確かめない
        for p in [SKILL] + glob.glob(os.path.join(REF, "*.md")):
            for name in set(FILE.findall(read(p))):
                if "*" in name or name.startswith(("spec.", "out.", "intro.", "bgm.", "music.", "work/", "order.")) or name in ("SKILL.md",) + elsewhere:
                    continue
                with self.subTest(file=os.path.basename(p), name=name):
                    base = [os.path.dirname(p)] + roots
                    self.assertTrue(any(os.path.exists(os.path.normpath(os.path.join(b, name))) for b in base), name)

    def test_steps_present(self):
        text = read(SKILL)
        for h in ("### 0.", "### 1.", "### 2.", "### 3.", "### 4."):
            self.assertIn(h, text)
        for cmd in ("order.py", "--readings", "--timeline", "check.py", "review.md"):
            self.assertIn(cmd, text)


if __name__ == "__main__":
    unittest.main()
