"""youtube-upload（YouTube に限定公開で上げる）を、偽の Google のサーバーで確かめる。ネット・本物の認可は使わない。"""
import base64
import hashlib
import http.server
import json
import os
import stat
import sys
import threading
import unittest
import urllib.parse
import urllib.request
from unittest import mock

import fakes

sys.path.insert(0, os.path.join(fakes.VIDEO, "youtube-upload"))
import upload as yt  # noqa: E402

SECRETS = ("ACCESS-", "REFRESH-SECRET", "CLIENT-SECRET", "AUTH-CODE")


class FakeGoogle:
    """認可のサーバーと YouTube Data API のうち、upload.py が使う所だけ。受けたものを覚えておく。"""

    def __init__(self):
        g = self
        self.calls, self.tokens, self.meta, self.query, self.got = [], [], None, None, b""
        self.break_at, self.token_error, self.thumb_status, self.privacy = None, None, 200, None
        self.thumb, self.caption, self.challenge, self.puts = None, None, None, 0

        class H(http.server.BaseHTTPRequestHandler):
            def reply(self, status, body=b"", **headers):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body).encode()
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def body(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_POST(self):
                u = urllib.parse.urlparse(self.path)
                q = dict(urllib.parse.parse_qsl(u.query))
                data = self.body()
                g.calls.append("POST " + u.path)
                if u.path == "/token":
                    form = dict(urllib.parse.parse_qsl(data.decode()))
                    g.tokens.append(form)
                    if g.token_error:
                        return self.reply(400, {"error": g.token_error})
                    if form["grant_type"] == "authorization_code":
                        ok = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest()).rstrip(b"=").decode() == g.challenge
                        if not ok or form["code"] != "AUTH-CODE":
                            return self.reply(400, {"error": "invalid_grant"})
                        return self.reply(200, {"access_token": "ACCESS-1", "refresh_token": "REFRESH-SECRET", "expires_in": 3600, "scope": form.get("_scope", "")})
                    return self.reply(200, {"access_token": "ACCESS-%d" % (len(g.tokens) + 1), "expires_in": 3600})
                if self.headers.get("Authorization", "").split("-")[0] != "Bearer ACCESS":
                    return self.reply(401, {"error": {"message": "no token", "errors": [{"reason": "authError"}]}})
                if u.path == "/upload/youtube/v3/videos":
                    g.meta, g.query, g.size = json.loads(data.decode("utf-8")), q, int(self.headers["X-Upload-Content-Length"])
                    return self.reply(200, Location="http://127.0.0.1:%d/session/1" % g.port)
                if u.path == "/upload/youtube/v3/thumbnails/set":
                    g.thumb = (q, self.headers["Content-Type"], data)
                    return self.reply(g.thumb_status, {"error": {"message": "no", "errors": [{"reason": "forbidden"}]}} if g.thumb_status != 200 else {})
                if u.path == "/upload/youtube/v3/captions":
                    g.caption = (q, self.headers["Content-Type"], data)
                    return self.reply(200, {})
                self.reply(404)

            def do_PUT(self):
                data = self.body()
                g.calls.append("PUT")
                rng = self.headers["Content-Range"]
                if not rng.startswith("bytes */"):
                    g.puts += 1
                    first = int(rng.split(" ")[1].split("-")[0])
                    assert first == len(g.got), (first, len(g.got))
                    if g.break_at == g.puts:   # 半分だけ受け取って、途切れる
                        g.got += data[:len(data) // 2]
                        return self.reply(503)
                    g.got += data
                if len(g.got) >= g.size:
                    return self.reply(200, {"id": "VID123", "status": {"privacyStatus": g.privacy or g.meta["status"]["privacyStatus"], "uploadStatus": "uploaded"}})
                self.reply(308, **({"Range": "bytes=0-%d" % (len(g.got) - 1)} if g.got else {}))

            def log_message(self, *a):
                pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        self.base = "http://127.0.0.1:%d" % self.port
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


class Case(unittest.TestCase):
    def setUp(self):
        self.g = FakeGoogle()
        self.home = os.path.join(fakes.tmpdir(), "cfg")
        self.dir = fakes.tmpdir()
        os.makedirs(self.home)
        fakes.write_json(os.path.join(self.home, "client_secret.json"), {"installed": {"client_id": "CLIENT-ID", "client_secret": "CLIENT-SECRET"}})
        ps = [mock.patch.object(yt, "HOME", self.home), mock.patch.object(yt, "API", self.g.base), mock.patch.object(yt, "TOKEN_URI", self.g.base + "/token"),
              mock.patch.object(yt, "REVOKE_URI", self.g.base + "/revoke"), mock.patch.object(yt, "CHUNK", 1024), mock.patch.object(yt, "WAIT", 0)]
        for p in ps:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.g.close)
        self.video = os.path.join(self.dir, "v.webm")
        self.bytes = bytes(range(256)) * 10 + b"end"   # 2563 バイト = 1024 の 3 個め が端数
        with open(self.video, "wb") as f:
            f.write(self.bytes)

    def token(self, scope=yt.SCOPE_UPLOAD, expiry=None):
        import time
        fakes.write_json(os.path.join(self.home, "token.json"), {"access_token": "ACCESS-0", "refresh_token": "REFRESH-SECRET", "expiry": time.time() + 3000 if expiry is None else expiry, "scope": scope})

    def run_cli(self, *argv):
        with fakes.quiet() as (err, out):
            code = yt.main(list(argv))
        text = out.getvalue() + err.getvalue()
        for s in SECRETS:   # トークン・クライアントの秘密・認可コードは、どこにも出さない
            self.assertNotIn(s, text)
        return code, text


class Upload(Case):
    def test_without_yes_nothing_is_sent(self):
        self.token()
        code, text = self.run_cli("upload", self.video, "--title", "題")
        self.assertEqual(code, 0)
        self.assertIn("限定公開", text)
        self.assertIn("まだ送っていません", text)
        self.assertEqual(self.g.calls, [])

    def test_public_is_refused(self):
        self.token()
        with self.assertRaises(SystemExit), fakes.quiet():
            yt.main(["upload", self.video, "--title", "題", "--privacy", "public", "--yes"])
        self.assertEqual(self.g.calls, [])

    def test_unlisted_upload(self):
        self.token()
        code, text = self.run_cli("upload", self.video, "--title", "関西の秘境 10 選", "--tags", "解説, 旅", "--yes")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.g.got, self.bytes)
        self.assertEqual(self.g.meta["status"], {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False})
        self.assertEqual(self.g.meta["snippet"]["title"], "関西の秘境 10 選")
        self.assertEqual(self.g.meta["snippet"]["tags"], ["解説", "旅"])
        self.assertEqual(self.g.query["notifySubscribers"], "false")
        self.assertEqual(self.g.puts, 3)
        self.assertIn("https://youtu.be/VID123", text)
        rec = json.load(open(os.path.join(self.dir, "v.youtube.json"), encoding="utf-8"))
        self.assertEqual((rec["videoId"], rec["privacy"]), ("VID123", "unlisted"))
        self.assertNotIn("ACCESS", json.dumps(rec))

    def test_resumes_after_a_break(self):
        self.token()
        self.g.break_at = 2
        code, text = self.run_cli("upload", self.video, "--title", "題", "--yes")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.g.got, self.bytes)   # 半分だけ届いた所から続ける（重ねて送らない・飛ばさない）

    def test_gives_up_when_it_keeps_breaking(self):
        self.token()
        with mock.patch.object(yt, "fetch", side_effect=[(200, {"Location": "http://x/s"}, b"")] + [OSError("down")] * 20):
            code, text = self.run_cli("upload", self.video, "--title", "題", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("途切れ", text)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "v.youtube.json")))

    def test_same_file_is_not_uploaded_twice(self):
        self.token()
        self.run_cli("upload", self.video, "--title", "題", "--yes")
        n = len(self.g.calls)
        code, text = self.run_cli("upload", self.video, "--title", "題", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("もう上げてあります", text)
        self.assertEqual(len(self.g.calls), n)

    def test_warns_when_youtube_locks_it_private(self):
        self.token()
        self.g.privacy = "private"
        code, text = self.run_cli("upload", self.video, "--title", "題", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("頼んだ公開範囲", text)

    def test_thumbnail_failure_keeps_the_video(self):
        self.token()
        thumb = os.path.join(self.dir, "t.png")
        open(thumb, "wb").write(b"\x89PNG....")
        self.g.thumb_status = 403
        code, text = self.run_cli("upload", self.video, "--title", "題", "--thumbnail", thumb, "--yes")
        self.assertEqual(code, 0, text)
        self.assertIn("サムネイルは付けられませんでした", text)
        self.assertEqual(json.load(open(os.path.join(self.dir, "v.youtube.json"), encoding="utf-8"))["thumbnail"], "failed")

    def test_refuses_what_youtube_would_refuse(self):
        self.token()
        html = os.path.join(self.dir, "v.html")
        open(html, "w").write("<html>")
        desc = os.path.join(self.dir, "d.txt")
        open(desc, "w", encoding="utf-8").write("出典 <https://example.com>")
        for argv, word in ((["upload", html, "--title", "題"], "HTML は上げられません"),
                           (["upload", self.video], "題がありません"),
                           (["upload", self.video, "--title", "あ" * 101], "100 字まで"),
                           (["upload", self.video, "--title", "題", "--description", desc], "< か >")):
            code, text = self.run_cli(*argv, "--yes")
            self.assertEqual(code, 1, argv)
            self.assertIn(word, text)
        self.assertEqual(self.g.calls, [])

    def test_tag_length_counts_like_youtube(self):
        self.assertEqual(yt.tag_length(["Foo-Baz", "foo bar"]), 7 + 1 + 9)   # 公式の例の数え方: カンマと、空白を含むタグの引用符


class FromScript(Case):
    def setUp(self):
        super().setUp()
        self.script = os.path.join(self.dir, "hikyo.txt")
        open(self.script, "w", encoding="utf-8").write("---\ntitle: 関西の秘境 10 選【ずんだもん解説】   # 題\ntags: 秘境, 関西\nsummary: 概要の 1 文\n---\n# 章\nmetan: こんにちは。\n")
        open(os.path.join(self.dir, "hikyo.description.txt"), "w", encoding="utf-8").write("概要欄の本文\n0:00 はじめに\n")
        open(os.path.join(self.dir, "hikyo.thumbnail.png"), "wb").write(b"\x89PNGthumb")
        os.makedirs(os.path.join(self.dir, "hikyo_export"))
        open(os.path.join(self.dir, "hikyo_export", "題.ja.srt"), "w", encoding="utf-8").write("1\n00:00:00,000 --> 00:00:01,000\nこんにちは\n")

    def test_picks_up_title_description_thumbnail(self):
        self.token()
        code, text = self.run_cli("upload", self.video, "--script", self.script, "--yes")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.g.meta["snippet"]["title"], "関西の秘境 10 選【ずんだもん解説】")
        self.assertEqual(self.g.meta["snippet"]["description"], "概要欄の本文\n0:00 はじめに")
        self.assertEqual(self.g.meta["snippet"]["tags"], ["秘境", "関西"])
        self.assertEqual(self.g.thumb[0]["videoId"], "VID123")
        self.assertEqual(self.g.thumb[1:], ("image/png", b"\x89PNGthumb"))
        self.assertIsNone(self.g.caption)   # 字幕の権限で認可していなければ、字幕は送らない
        self.assertIn("字幕は上げません", text)

    def test_captions_with_the_wider_scope(self):
        self.token(scope=yt.SCOPE_UPLOAD + " " + yt.SCOPE_CAPTIONS)
        code, text = self.run_cli("upload", self.video, "--script", self.script, "--yes")
        self.assertEqual(code, 0, text)
        q, ctype, body = self.g.caption
        self.assertTrue(ctype.startswith("multipart/related; boundary="))
        self.assertIn(b'"videoId": "VID123"', body)
        self.assertIn("こんにちは".encode("utf-8"), body)

    def test_motion_video_json(self):
        self.token()
        spec = fakes.write_json(os.path.join(self.dir, "mv.json"), {"title": "相談室", "chapters": []})
        code, text = self.run_cli("upload", self.video, "--script", spec)
        self.assertEqual(code, 0, text)
        self.assertIn("題: 相談室", text)


class Auth(Case):
    def test_expired_token_is_refreshed_and_kept_private(self):
        self.token(expiry=0)
        code, text = self.run_cli("upload", self.video, "--title", "題", "--yes")
        self.assertEqual(code, 0, text)
        self.assertEqual(self.g.tokens[0]["grant_type"], "refresh_token")
        tok = os.path.join(self.home, "token.json")
        self.assertEqual(stat.S_IMODE(os.stat(tok).st_mode), 0o600)
        self.assertEqual(json.load(open(tok))["refresh_token"], "REFRESH-SECRET")   # 更新しても、更新用のトークンは残る

    def test_revoked_grant_asks_to_auth_again(self):
        self.token(expiry=0)
        self.g.token_error = "invalid_grant"
        code, text = self.run_cli("upload", self.video, "--title", "題", "--yes")
        self.assertEqual(code, yt.EXIT_SETUP)
        self.assertIn("auth", text)
        self.assertNotIn("POST /upload/youtube/v3/videos", self.g.calls)

    def test_not_ready(self):
        code, text = self.run_cli("check")
        self.assertEqual(code, yt.EXIT_SETUP)
        os.remove(os.path.join(self.home, "client_secret.json"))
        code, text = self.run_cli("upload", self.video, "--title", "題", "--yes")
        self.assertEqual(code, yt.EXIT_SETUP)
        fakes.write_json(os.path.join(self.home, "client_secret.json"), {"web": {"client_id": "x"}})
        code, text = self.run_cli("auth", "--no-browser", "--timeout", "1")
        self.assertEqual(code, yt.EXIT_SETUP)
        self.assertIn("デスクトップ アプリ", text)

    def test_auth_with_loopback_and_pkce(self):
        def browser(url):   # 使う人がブラウザで同意したことにする
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
            self.g.challenge, self.asked = q["code_challenge"], q

            def back():
                urllib.request.urlopen(q["redirect_uri"] + "/?" + urllib.parse.urlencode({"state": q["state"], "code": "AUTH-CODE"})).read()
            threading.Thread(target=back, daemon=True).start()
        with mock.patch.object(yt, "open_browser", browser):
            code, text = self.run_cli("auth", "--timeout", "10")
        self.assertEqual(code, 0, text)
        self.assertEqual((self.asked["scope"], self.asked["code_challenge_method"]), (yt.SCOPE_UPLOAD, "S256"))   # 既定は、上げるだけの狭い権限
        self.assertTrue(self.asked["redirect_uri"].startswith("http://127.0.0.1:"))
        tok = os.path.join(self.home, "token.json")
        self.assertEqual(stat.S_IMODE(os.stat(tok).st_mode), 0o600)
        self.assertEqual(json.load(open(tok))["refresh_token"], "REFRESH-SECRET")
        self.assertEqual(self.run_cli("check")[0], 0)

    def test_auth_rejects_a_reply_with_another_state(self):
        def browser(url):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))

            def back():
                try:
                    urllib.request.urlopen(q["redirect_uri"] + "/?state=other&code=AUTH-CODE").read()
                except OSError:
                    pass
            threading.Thread(target=back, daemon=True).start()
        with mock.patch.object(yt, "open_browser", browser):
            code, text = self.run_cli("auth", "--timeout", "10")
        self.assertEqual(code, 1)
        self.assertEqual(self.g.tokens, [])
        self.assertFalse(os.path.exists(os.path.join(self.home, "token.json")))


if __name__ == "__main__":
    unittest.main()


class Record(unittest.TestCase):
    """record.py: 画面なしの Chrome で、プレイヤーの「WebM で保存」を押して録る。Chrome が無ければ飛ばす。"""

    def test_records_a_1080p_webm_with_sound(self):
        import shutil
        import build
        import record
        import shoot
        chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
        if not chrome:
            self.skipTest("Chrome が無い")
        d = fakes.tmpdir()
        path = fakes.write_json(os.path.join(d, "r.json"), {"title": "録画の試し", "lang": "ja", "audio": {"narration": False, "music": "calm", "sfx": True},
                                                          "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "録画の試し", "duration": 3}]}]})
        html, out = os.path.join(d, "r.html"), os.path.join(d, "r.webm")
        with fakes.quiet():
            open(html, "w", encoding="utf-8").write(build.build_html(build.load(path), "midnight", "studio", True))
        b = shoot.Browser(chrome, (1280, 720), record.FLAGS)
        real = b.call

        def call(method, session=None, **params):   # Chrome が、保存先に自分のファイルを落としたことにする（CI で、部品の CRX を録画と取り違えた）
            if method == "Browser.setDownloadBehavior":
                open(os.path.join(params["downloadPath"], "downloads.html"), "wb").write(b"Cr24....")
            return real(method, session, **params)
        b.call = call
        try:
            sel = lambda: b.eval("[].map.call(document.querySelectorAll('select[data-mv^=rec]'),function(e){return e.getAttribute('data-mv')+'='+e.value}).join(' ')")
            b.open(html)
            self.assertEqual(sel(), "recsize=1080 recbps=0 recfps=30 recabps=192 recfmt=webm")   # ⚙ の既定: 1920×1080・自動・30 コマ・192kbps・WebM
            off = os.path.join(d, "o.webm")
            oi = record.record_offline(b, html, off, {"size": "1080", "fps": "30"}, log=lambda *a: None)   # 1 コマずつの書き出し（既定の方式）
            og = record.probe(b, off, os.path.join(d, "o.png"), .5)
            o60 = record.record_offline(b, html, os.path.join(d, "o60.webm"), {"size": "720", "fps": "60"}, log=lambda *a: None)
            info = record.record(b, html, out, None, log=lambda *a: None)   # 前の方式: 何も付けずにボタンを押す = プレイヤーの既定で録る
            got = record.probe(b, out, os.path.join(d, "r.png"), .5)
            small = os.path.join(d, "s.webm")
            record.record(b, html, small, {"size": "720", "bps": 1, "fps": "30", "abps": 128, "fmt": "vp8"}, log=lambda *a: None)
            got2 = record.probe(b, small, os.path.join(d, "s.png"), .5)
        finally:
            b.close()
        # 1 コマずつの書き出し: コマが 1 つも抜けない（前は再生しながら録っていて、機械が遅いとコマが抜けた）・長さが台本どおり・音が入る・好きな所へ飛べる
        self.assertEqual((oi["frames"], oi["want"]), (90, 90))
        self.assertEqual((og["w"], og["h"]), (1920, 1080))
        self.assertEqual((o60["frames"], o60["size"]), (180, (1280, 720)))   # コマ数も選べる（60 コマ/秒）
        self.assertLess(abs(og["dur"] - 3.0), .1)
        self.assertEqual(sorted(record.tracks(off)), ["A_OPUS", "V_VP9"])
        self.assertFalse(shoot.is_blank(open(os.path.join(d, "o.png"), "rb").read()))
        self.assertEqual((got["w"], got["h"]), (1920, 1080))   # 既定は 1920×1080（前は 1280×720 に決め打ちだった）
        self.assertEqual((got2["w"], got2["h"]), (1280, 720))   # 解像度・画質・形式を選べる
        self.assertIn("V_VP8", record.tracks(small))
        self.assertLess(os.path.getsize(small), os.path.getsize(out))
        self.assertLess(abs(got["dur"] - info["dur"]), 2)
        self.assertTrue(info["audio"])
        tr = record.tracks(out)
        self.assertTrue(any(t.startswith("V_") for t in tr) and any(t.startswith("A_") for t in tr), tr)
        self.assertFalse(shoot.is_blank(open(os.path.join(d, "r.png"), "rb").read()))

    def test_parallel_export_joins_every_frame(self):
        """動画を区間に分け、Chrome を 2 つ動かして同時に書き出す。つないだ後も、コマが 1 つも抜けず、時刻が順に並ぶ。"""
        import shutil
        import build
        import record
        import shoot
        import webm
        chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
        if not chrome:
            self.skipTest("Chrome が無い")
        d = fakes.tmpdir()
        path = fakes.write_json(os.path.join(d, "p.json"), {"title": "並べて書き出す", "lang": "ja", "audio": {"narration": False, "music": "calm", "sfx": True},
                                                          "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "並べて書き出す", "duration": 9}, {"type": "statement", "lines": ["後半"], "duration": 9}]}]})
        html, out = os.path.join(d, "p.html"), os.path.join(d, "p.webm")
        with fakes.quiet():
            open(html, "w", encoding="utf-8").write(build.build_html(build.load(path), "midnight", "studio", True))
        seen = []
        real = webm.Writer.add_video

        def add_video(self2, ms, data, key=False):
            seen.append((ms, key))
            return real(self2, ms, data, key)
        b = shoot.Browser(chrome, (1280, 720), record.FLAGS)
        try:
            with mock.patch.object(webm.Writer, "add_video", add_video):
                info = record.record_offline(b, html, out, {"size": "720", "fps": "30"}, log=lambda *a: None, jobs=2, browser=lambda: shoot.Browser(chrome, (1280, 720), record.FLAGS))
            got = record.probe(b, out, os.path.join(d, "p.png"), .75)   # 2 つめの区間の中
        finally:
            b.close()
        self.assertEqual(info["jobs"], 2)
        self.assertEqual((info["frames"], len(seen)), (info["want"], info["want"]))
        self.assertEqual([m for m, _ in seen], sorted(set(m for m, _ in seen)))   # 時刻が順で、重なりも抜けも無い
        self.assertTrue(all(k for m, k in seen if m % 2000 == 0))   # 2 秒ごとのキーフレーム（区間の頭もここにそろう）
        self.assertLess(abs(got["dur"] - info["dur"]), .1)
        self.assertFalse(shoot.is_blank(open(os.path.join(d, "p.png"), "rb").read()))
        self.assertEqual([f for f in os.listdir(d) if f.startswith("mv-parts-")], [])   # 区間の一時ファイルを残さない


class WebM(unittest.TestCase):
    """webm.py: 映像と音のかたまりを 1 つの WebM にまとめる。"""

    def test_layout(self):
        import struct
        import webm
        d = fakes.tmpdir()
        path = os.path.join(d, "t.webm")
        w = webm.Writer(path, 1920, 1080, 30, "V_VP9", {"rate": 48000, "channels": 2})
        for i in range(50):
            w.add_audio(i * 20, b"A" * 10)
        for i in range(30):
            w.add_video(round(i * 1000 / 30), b"V" * 100, key=i % 10 == 0)
        res = w.close(1000)
        data = open(path, "rb").read()
        self.assertEqual((res["frames"], res["audio"]), (30, 50))
        self.assertEqual(data[:4], bytes.fromhex("1a45dfa3"))
        seg = data.index(bytes.fromhex("18538067"))
        size = int.from_bytes(data[seg + 5:seg + 12], "big")
        self.assertEqual(seg + 12 + size, len(data))   # 全体の大きさが書いてある（途中で切れたファイルと見分けられる）
        body = seg + 12
        cues = data.index(bytes.fromhex("1c53bb6b"))
        pos = [int.from_bytes(data[m + 2:m + 10], "big") for m in range(cues, len(data)) if data[m:m + 2] == b"\xf1\x88"][:3]
        self.assertEqual(len(pos), 3)   # キーフレームごとに 1 つ（0・10・20 コマめ）
        for p in pos:   # 索引は、かたまりの頭を指す
            self.assertEqual(data[body + p:body + p + 4], bytes.fromhex("1f43b675"))
        self.assertEqual(struct.unpack(">d", data[data.index(bytes.fromhex("4489")) + 3:][:8])[0], 1000.0)
        self.assertEqual(data.count(b"V" * 100), 30)
        self.assertEqual(data.count(b"A" * 10 ) >= 50, True)
        self.assertEqual([f for f in os.listdir(d) if f != "t.webm"], [])   # 一時ファイルを残さない

    def test_first_frame_must_be_key(self):
        import webm
        w = webm.Writer(os.path.join(fakes.tmpdir(), "t.webm"), 16, 16, 30)
        with self.assertRaises(ValueError):
            w.add_video(0, b"x", key=False)
        w.abort()
