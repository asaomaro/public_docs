"""engine.js をブラウザ（画面なしの Chrome）で動かして確かめる。Chrome が無ければ飛ばす。

  - 1 文の声が字幕 2 つにまたがるとき、2 つ目の字幕は前の声の続き（新しく鳴らさない）
  - 字幕は、カタカナ語・英単語の途中で折らない（2026-10:「フレームワー／ク」）
  - 書き出し（OfflineAudioContext）に、ファイルの BGM が入る（2026-10: fetch を使っていて、書き出しで BGM が無音だった）
  - 場面の music で、その場面から曲が替わる
"""
import json
import os
import re
import shutil
import subprocess
import unittest

import fakes
import build

CHROME = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)


class Chrome:
    """画面なしの Chrome を DevTools Protocol（パイプ）で動かす。仮想時間（--virtual-time-budget）を使わず、本当の時間で Promise を待つ
    （仮想時間の下では、長い音の書き出し〔OfflineAudioContext〕が終わる前に打ち切られるため）。"""

    def __init__(self):
        r3, self.w3 = os.pipe()      # Chrome が読む（fd 3）
        self.r4, w4 = os.pipe()      # Chrome が書く（fd 4）
        self.dir = fakes.tmpdir()

        def fds():   # Chrome は fd 3 から読み、fd 4 へ書く。pipe の fd は exec で閉じる印が付くので、継承できるようにする
            for src, dst in ((r3, 3), (w4, 4)):
                if src != dst:
                    os.dup2(src, dst)
                os.set_inheritable(dst, True)
        self.p = subprocess.Popen([CHROME, "--headless=new", "--no-sandbox", "--remote-debugging-pipe", "--user-data-dir=" + self.dir,
                                   "--autoplay-policy=no-user-gesture-required", "about:blank"],
                                  preexec_fn=fds, close_fds=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(r3)
        os.close(w4)
        self.buf, self.n = b"", 0
        tid = next(t["targetId"] for t in self.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.call("Target.attachToTarget", targetId=tid, flatten=True)["sessionId"]

    def call(self, method, session=None, **params):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params}
        if session:
            msg["sessionId"] = session
        os.write(self.w3, json.dumps(msg).encode() + b"\0")
        while True:
            while b"\0" not in self.buf:
                chunk = os.read(self.r4, 1 << 20)
                if not chunk:
                    raise AssertionError("Chrome が終わった")
                self.buf += chunk
            raw, self.buf = self.buf.split(b"\0", 1)
            m = json.loads(raw)
            if m.get("id") == self.n:
                if "error" in m:
                    raise AssertionError(m["error"])
                return m["result"]

    def open(self, html):
        path = os.path.join(self.dir, "t%d.html" % self.n)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self.call("Page.enable", self.sid)
        self.call("Page.navigate", self.sid, url="file://" + path)
        return self.eval("new Promise(function(ok){function w(){window.__MV__?setTimeout(ok,300):setTimeout(w,100)};w()})")

    def eval(self, js):
        r = self.call("Runtime.evaluate", self.sid, expression=js, awaitPromise=True, returnByValue=True, timeout=120000)
        if r.get("exceptionDetails"):
            raise AssertionError(r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"])
        return r["result"].get("value")

    def close(self):
        self.p.kill()
        self.p.wait()


def build_html(spec, voicevox=True):
    d = fakes.tmpdir()
    path = fakes.write_json(os.path.join(d, "e.json"), spec)
    if isinstance(spec.get("audio", {}).get("music"), dict) and spec["audio"]["music"].get("file"):
        fakes.write_wav(os.path.join(d, spec["audio"]["music"]["file"]), [(2.0, True)])
    with fakes.fake_voicevox(alive=voicevox), fakes.quiet():
        s = build.load(path)
        return build.build_html(s, "midnight", "studio", True)


@unittest.skipUnless(CHROME or os.environ.get("REQUIRE_CHROME"), "Chrome が無い")
class Engine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHROME:   # CI（REQUIRE_CHROME=1）では、飛ばさずに落とす
            raise AssertionError("Chrome が無いので engine.js を確かめられません")
        cls.chrome = Chrome()

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    def run_js(self, html, js):
        self.chrome.open(html)
        return self.chrome.eval(js)
    def test_sentence_voice_spans_cues(self):
        sp = {"title": "t", "lang": "ja", "audio": {"narration": True, "music": None, "sfx": False, "voice": {"engine": "voicevox", "speaker": "四国めたん"}},
              "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t",
                                                       "narration": ["ブラウザでも、引数なしのソーダで開く端末版でも、同じ画面をそのまま操作できます。", "短い文です。"]}]}]}
        cues = self.run_js(build_html(sp), """(function(){var C=__MV__.CUES;return C.map(function(c){return {
            voice:!!(c.line&&c.line.voice), cont:!!c.par, sameKey: c.par? c.key===c.par.key : null, joins: c.par? Math.abs(c.a-c.par.b)<=5 : null}})})()""")
        self.assertEqual([c["cont"] for c in cues], [False, True, False])
        self.assertTrue(cues[1]["sameKey"] and cues[1]["joins"])

    def test_caption_wrap_keeps_words(self):
        sp = {"title": "t", "lang": "ja", "audio": {"narration": False}, "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t"}]}]}
        cases = ["「React は MVC フレームワークではない」って。", "新しいアーキテクチャのパフォーマンスとセキュリティを検証した",
                 "TypeScript で書かれた JavaScript のライブラリを使う"]
        # 幅は字幕でいちばん狭い 1080（白い箱）。それより狭いと、長いカタカナ語 2 つは 2 行に収まらない
        # 2 行の長さをそろえる所（字幕の幅の 0.58 倍で折り直す。2026-10 の「フレームワー／ク」はここで起きた）も、上限 1180 で同じく見る
        arr = ",".join(json.dumps(c, ensure_ascii=False) for c in cases)
        got = self.run_js(build_html(sp, voicevox=False), "[%s].map(function(t){return __MV__.capWrap(t, 1080, 56)}).concat([%s].map(function(t){"
                          "return __MV__.capWrap(t, Math.max(540, t.length * 56 * .58), 56, 1180)}))" % (arr, arr))
        for text, lines in zip(cases + cases, got):
            with self.subTest(text):
                self.assertEqual("".join(lines).replace(" ", ""), text.replace(" ", ""))
                for a, b in zip(lines, lines[1:]):
                    self.assertFalse(re.search(r"[ァ-ヶー]$", a) and re.match(r"[ァ-ヶー]", b), lines)   # カタカナ語の途中
                    self.assertFalse(re.search(r"[A-Za-z]$", a) and re.match(r"[A-Za-z]", b), lines)   # 英単語の途中
                    self.assertFalse(re.match(r"[、。」）]", b), lines)                                  # 行頭の句読点・閉じかっこ

    def test_export_has_file_music(self):
        sp = {"title": "t", "lang": "ja", "audio": {"narration": False, "music": {"file": "bgm.wav", "loop": True}, "sfx": False},
              "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t", "duration": 4}]}]}
        # fetch を使えない所でも（埋め込みの data: を自前で読む）
        rms = self.run_js(build_html(sp, voicevox=False), "(window.fetch=function(){return Promise.reject('fetch は使えない')}, __MV__.renderMusic())")
        self.assertGreater(max(rms[5:30]), 0.01, rms[:40])

    def test_scene_music_segments(self):
        sp = {"title": "t", "lang": "ja", "audio": {"narration": False, "music": "calm", "sfx": False},
              "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "t", "duration": 3},
                                                     {"type": "statement", "lines": ["b"], "music": "hope", "duration": 3}]},
                           {"title": "b", "music": "tech", "scenes": [{"type": "end", "title": "e", "duration": 3}]}]}
        segs = self.run_js(build_html(sp, voicevox=False), "__MV__.segments()")
        self.assertEqual([s["key"] for s in segs], ["calm", "hope", "tech"], segs)


if __name__ == "__main__":
    unittest.main()
