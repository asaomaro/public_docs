"""yukkuri-publish: 概要欄が YouTube の上限（5000 バイト）に収まるか。"""
import os
import sys
import unittest

import fakes

sys.path.insert(0, os.path.join(fakes.VIDEO, "yukkuri-publish"))
import publish  # noqa: E402


def info(n):
    imgs = [{"title": "Photo of a very remote place number %d" % i, "author": "No machine-readable author provided. Author%d assumed." % (i % 7), "short": "Author%d（CC BY-SA 4.0）" % (i % 7),
             "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0", "from": "Wikimedia Commons", "page": "https://commons.wikimedia.org/wiki/File:Remote_place_%d.jpg" % i} for i in range(n)]
    for i in imgs:
        i["full"] = "「%s」%s／%s（%s）／%s" % (i["title"], i["author"], i["license"], i["license_url"], i["page"])
    return {"chapters": [{"at": "0:00", "title": "はじめに"}], "credits": ["VOICEVOX:四国めたん", "画像: Author0（CC BY-SA 4.0）"], "images": imgs}


class Description(unittest.TestCase):
    META = {"summary": "概要の 1 文。", "tags": "解説, 秘境"}

    def test_few_images_keep_the_full_credits(self):
        text, extra = publish.description(self.META, info(3), ["https://example.com — 出典"])
        self.assertIsNone(extra)
        self.assertIn("https://creativecommons.org/licenses/by-sa/4.0", text)
        self.assertIn("File:Remote_place_2.jpg", text)

    def test_many_images_fit_the_limit(self):
        # 写真 47 枚の動画で、概要欄が 12,063 バイトになり、YouTube に送れなかった
        text, extra = publish.description(self.META, info(47), ["https://example.com — 出典"])
        self.assertLessEqual(len(text.encode("utf-8")), publish.DESC_LIMIT)
        for must in ("VOICEVOX:四国めたん", "CC BY-SA 4.0（Wikimedia Commons）", "Author6", "▼目次", "#解説"):   # 作者とライセンスは概要欄に残る
            self.assertIn(must, text)
        self.assertNotIn("No machine-readable", text)
        self.assertEqual(extra.count("File:Remote_place_"), 47)   # 題と URL つきの全文は、別に出す

    def test_middle_size_drops_only_the_license_url(self):
        text, extra = publish.description(self.META, info(24), [])
        self.assertIsNone(extra)
        self.assertNotIn("creativecommons.org", text)
        self.assertIn("File:Remote_place_23.jpg", text)
        self.assertLessEqual(len(text.encode("utf-8")), publish.DESC_LIMIT)


if __name__ == "__main__":
    unittest.main()
