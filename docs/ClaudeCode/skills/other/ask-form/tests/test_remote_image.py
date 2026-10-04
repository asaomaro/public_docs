"""ask-form: 外部 URL（https://…）の画像を、ブラウザではなく ask.py が取って配る部分（remote_image.py と ask.localize_remote_media）。

Sodashitsu の packages/server/src/ask/RemoteImageFetcher.test.ts と同じ観点（接続してはいけない宛先・表記違い・リダイレクトの再検査・上限・種類の不一致・時間切れ）を、
ネットワークに出ずに確かめる（名前解決と 1 回の要求を偽物に差し替える）。接続先の固定と証明書の検証だけは、手元の自己署名の証明書の https で実物を確かめる（openssl が無ければ飛ばす）。
"""
import os
import shutil
import ssl
import subprocess
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import chrome as helpers

AF = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AF)
import ask  # noqa: E402
import remote_image as ri  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + bytes(16)
JPEG = b"\xff\xd8\xff\xe0" + bytes(16)
SVG = b'<?xml version="1.0"?><!-- c --><svg xmlns="http://www.w3.org/2000/svg"></svg>'
PUBLIC = "93.184.216.34"


class Res:
    """偽の応答。"""

    def __init__(self, status=200, headers=None, body=b"", chunk=65536):
        self.status, self.headers = status, {k.lower(): v for k, v in (headers or {}).items()}
        self._body, self.closed = body, False

    def read(self, n):
        out, self._body = self._body[:n], self._body[n:]
        return out

    def close(self):
        self.closed = True


class Fake:
    """名前解決と要求の偽物。呼ばれた内容を残す。routes: ホスト名 → 応答（か、応答を返す関数）。"""

    def __init__(self, routes, dns=None):
        self.routes, self.dns, self.calls, self.lookups = routes, dns or {}, [], []

    def lookup(self, host, timeout):
        self.lookups.append(host)
        return self.dns.get(host, [(PUBLIC, 4)])

    def request(self, host, path, address, headers, timeout):
        self.calls.append({"host": host, "path": path, "address": address, "headers": dict(headers)})
        r = self.routes[host]
        return r(path) if callable(r) else r

    def fetch(self, url, **kw):
        return ri.fetch_image(url, lookup=self.lookup, request=self.request, **kw)


def png(**h):
    return Res(200, dict({"Content-Type": "image/png"}, **h), PNG)


def fail(case, fake, url, why=None, **kw):
    with case.assertRaises(ri.FetchError) as e:
        fake.fetch(url, **kw)
    if why:
        case.assertIn(why, str(e.exception))
    return e.exception


BLOCKED = [
    "0.0.0.0", "10.1.2.3", "100.64.0.1", "100.127.255.255", "127.0.0.1", "127.255.0.1", "169.254.169.254", "172.16.0.1", "172.31.255.255",
    "192.0.0.1", "192.0.2.1", "192.168.1.1", "198.18.0.1", "198.19.1.1", "198.51.100.1", "203.0.113.1", "224.0.0.1", "239.1.1.1", "240.0.0.1",
    "255.255.255.255", "::", "::1", "fc00::1", "fd12:3456::1", "fe80::1", "ff02::1", "::ffff:127.0.0.1", "::ffff:7f00:1", "::ffff:10.0.0.1",
    "::ffff:169.254.169.254", "64:ff9b::7f00:1", "::127.0.0.1", "2001:db8::1", "2001::1", "2002:7f00:1::1", "2002:a9fe:a9fe::1", "fe80::1%eth0",
    "not-an-ip", "1.2.3", "300.1.1.1", "::g", "1::2::3", "",
]
ALLOWED = ["93.184.216.34", "8.8.8.8", "172.15.0.1", "172.32.0.1", "100.63.0.1", "2606:2800:220:1:248:1893:25c8:1946", "2001:4860:4860::8888",
           "::ffff:8.8.8.8", "2002:0808:0808::1"]


class Address(unittest.TestCase):
    def test_blocked(self):
        for a in BLOCKED:
            with self.subTest(a):
                self.assertTrue(ri.is_blocked_address(a))

    def test_allowed(self):
        for a in ALLOWED:
            with self.subTest(a):
                self.assertFalse(ri.is_blocked_address(a))


class Destination(unittest.TestCase):
    """URL の書き方（表記違い）を含め、接続してはいけない宛先には、要求を 1 回も出さない。"""

    URLS = [
        "http://example.com/a.png", "https://example.com:8443/a.png", "https://example.com:80/a.png", "ftp://example.com/a.png", "file:///etc/passwd",
        "https://user:pw@example.com/a.png", "https://user@example.com/a.png", "https://example.com@127.0.0.1/a.png",
        "https://localhost/a.png", "https://LOCALHOST./a.png", "https://app.localhost/a.png",
        "https://127.0.0.1/a.png", "https://10.0.0.1/a.png", "https://192.168.0.1/a.png", "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/a.png", "https://[::ffff:127.0.0.1]/a.png", "https://[::ffff:7f00:1]/a.png", "https://[fe80::1]/a.png", "https://[fd00::1]/a.png",
        "https://2130706433/a.png", "https://0x7f000001/a.png", "https://0x7f.0.0.1/a.png", "https://0177.0.0.1/a.png", "https://017700000001/a.png",
        "https://127.1/a.png", "https://127.0.1/a.png", "https://0/a.png", "https://0.0.0.0/a.png", "https://2852039166/a.png", "https://0xA9FEA9FE/a.png",
        "https://１２７．０．０．１/a.png", "https://127。0。0。1/a.png", "https://127.0.0.1./a.png", "https://1.2.3.4.5/a.png", "https://256.1.1.1/a.png",
        "https://foo.123/a.png", "https:///a.png", "https://",
    ]

    def test_each_is_refused_without_any_request(self):
        for url in self.URLS:
            with self.subTest(url):
                f = Fake({})
                fail(self, f, url)
                self.assertEqual(f.calls, [])
                self.assertEqual(f.lookups, [])      # 名前としては解決もしない（数の表記・拒否する形は、名前解決の前に断る）

    def test_public_literal_is_allowed(self):
        f = Fake({"8.8.8.8": png()})
        self.assertEqual(f.fetch("https://8.8.8.8/a.png"), (PNG, "image/png"))
        self.assertEqual(f.calls[0]["address"], "8.8.8.8")

    def test_every_resolved_address_is_checked(self):
        for answer in ([("10.0.0.5", 4)], [(PUBLIC, 4), ("127.0.0.1", 4)], [("::1", 6), (PUBLIC, 4)], [("::ffff:169.254.169.254", 6)], [("fe80::1%lo", 6)], [("junk", 4)]):
            with self.subTest(answer):
                f = Fake({"example.com": png()}, {"example.com": answer})
                fail(self, f, "https://example.com/a.png", "blocked address")
                self.assertEqual(f.calls, [])

    def test_no_address(self):
        fail(self, Fake({}, {"example.com": []}), "https://example.com/a.png", "host not found")

    def test_connects_to_the_checked_address_and_sends_no_credentials(self):
        """接続は検査したアドレスに固定する（要求の側へ、名前ではなく検査したアドレスを渡す＝接続の直前にもう一度名前解決しない）。"""
        f = Fake({"example.com": png()}, {"example.com": [("93.184.216.34", 4), ("2606:2800:220:1::1", 6)]})
        f.fetch("https://example.com/a/b.png?x=1")
        c = f.calls[0]
        self.assertEqual((c["host"], c["path"], c["address"]), ("example.com", "/a/b.png?x=1", "93.184.216.34"))
        self.assertEqual(f.lookups, ["example.com"])
        low = {k.lower() for k in c["headers"]}
        self.assertEqual(low, {"accept", "user-agent", "accept-encoding", "host"})   # Cookie・Authorization・Referer・Origin は付けない

    def test_next_address_when_connection_fails(self):
        f = Fake({}, {"example.com": [("2606:2800:220:1::1", 6), (PUBLIC, 4)]})
        seen = []

        def req(host, path, address, headers, timeout):
            seen.append(address)
            if ":" in address:
                raise OSError("unreachable")
            return png()
        self.assertEqual(ri.fetch_image("https://example.com/a.png", lookup=f.lookup, request=req)[1], "image/png")
        self.assertEqual(seen, ["2606:2800:220:1::1", PUBLIC])
        with self.assertRaises(ri.FetchError):
            ri.fetch_image("https://example.com/a.png", lookup=f.lookup, request=lambda *a: (_ for _ in ()).throw(OSError("x")))


class Redirects(unittest.TestCase):
    def test_follows_and_rechecks_each_hop(self):
        f = Fake({"a.example": Res(302, {"Location": "https://b.example/img.png"}), "b.example": png()})
        self.assertEqual(f.fetch("https://a.example/start"), (PNG, "image/png"))
        self.assertEqual(f.lookups, ["a.example", "b.example"])           # 次の宛先も、名前解決からやり直す
        self.assertEqual(f.calls[1]["path"], "/img.png")

    def test_relative_location(self):
        f = Fake({"a.example": lambda p: Res(301, {"Location": "/real.png"}) if p == "/start" else png()})
        self.assertEqual(f.fetch("https://a.example/start")[1], "image/png")

    def test_redirect_into_blocked_destinations(self):
        for loc in ("https://169.254.169.254/latest/meta-data/", "https://127.0.0.1/a.png", "http://b.example/a.png", "https://b.example:8443/a.png",
                    "https://[::ffff:127.0.0.1]/a.png", "https://2130706433/a.png", "https://localhost/a.png", "https://user:pw@b.example/a.png", "file:///etc/passwd",
                    "https://private.example/a.png"):
            with self.subTest(loc):
                f = Fake({"a.example": Res(302, {"Location": loc}), "b.example": png(), "private.example": png()}, {"private.example": [("10.0.0.9", 4)]})
                fail(self, f, "https://a.example/start")
                self.assertEqual([c["host"] for c in f.calls], ["a.example"])   # 2 回目の要求は出さない

    def test_at_most_three(self):
        hops = {"h%d.example" % i: Res(302, {"Location": "https://h%d.example/" % (i + 1)}) for i in range(10)}
        hops["h3.example"] = png()
        f = Fake(hops)
        self.assertEqual(f.fetch("https://h0.example/")[1], "image/png")     # 3 回までは辿る
        hops["h3.example"] = Res(302, {"Location": "https://h4.example/"})
        hops["h4.example"] = png()
        fail(self, Fake(hops), "https://h0.example/", "too many redirects")
        fail(self, Fake({"a.example": Res(302, {})}), "https://a.example/", "without location")


class Limits(unittest.TestCase):
    def test_declared_size_over(self):
        f = Fake({"a.example": Res(200, {"Content-Type": "image/png", "Content-Length": str(ri.MAX_BYTES + 1)}, PNG)})
        fail(self, f, "https://a.example/x.png", "too large")

    def test_streamed_size_over_without_content_length(self):
        big = PNG + bytes(ri.MAX_BYTES)
        res = Res(200, {"Content-Type": "image/png"}, big)
        fail(self, Fake({"a.example": res}), "https://a.example/x.png", "too large")
        self.assertTrue(res.closed)
        self.assertEqual(Fake({"a.example": Res(200, {"Content-Type": "image/png"}, PNG + bytes(ri.MAX_BYTES - len(PNG)))}).fetch("https://a.example/x.png")[1], "image/png")   # ちょうど上限は通る

    def test_caller_total_limit_stops_the_fetch(self):
        def count(n):
            raise ri.FetchError("total too large")
        fail(self, Fake({"a.example": png()}), "https://a.example/x.png", "total too large", on_bytes=count)

    def test_status(self):
        for st in (204, 301 + 100, 403, 404, 500):
            with self.subTest(st):
                fail(self, Fake({"a.example": Res(st, {"Content-Type": "image/png"}, PNG)}), "https://a.example/x.png", "status")

    def test_content_type(self):
        cases = [
            ({"Content-Type": "text/html"}, b"<html></html>"),
            ({"Content-Type": "image/png"}, b"<html>not an image</html>"),            # 宣言は画像でも、先頭バイトが違う
            ({"Content-Type": "image/png"}, JPEG),                                      # 画像どうしでも、宣言と先頭バイトが違う
            ({"Content-Type": "image/jpeg"}, PNG),
            ({"Content-Type": "application/octet-stream"}, PNG),
            ({"Content-Type": "audio/wav"}, b"RIFF\0\0\0\0WAVE" + bytes(8)),
            ({}, PNG),
            ({"Content-Type": "image/png"}, b""),
            ({"Content-Type": "image/svg+xml"}, b"<html><svg></svg></html>"),
        ]
        for h, body in cases:
            with self.subTest(h, body=body[:12]):
                fail(self, Fake({"a.example": Res(200, h, body)}), "https://a.example/x.png", "content")

    def test_content_type_with_parameters_and_svg(self):
        self.assertEqual(Fake({"a.example": Res(200, {"Content-Type": "Image/PNG; charset=binary"}, PNG)}).fetch("https://a.example/")[1], "image/png")
        self.assertEqual(Fake({"a.example": Res(200, {"Content-Type": "image/svg+xml"}, SVG)}).fetch("https://a.example/")[1], "image/svg+xml")
        self.assertEqual(Fake({"a.example": Res(200, {"Content-Type": "image/jpeg"}, JPEG)}).fetch("https://a.example/")[1], "image/jpeg")

    def test_timeout(self):
        now = [0.0]

        def slow_request(host, path, address, headers, timeout):
            now[0] += 11          # 応答が来るまでに 10 秒を超えた
            return png()
        with self.assertRaises(ri.FetchError) as e:
            ri.fetch_image("https://a.example/", lookup=lambda h, t: [(PUBLIC, 4)], request=slow_request, clock=lambda: now[0])
        self.assertIn("timeout", str(e.exception))

        class Trickle(Res):          # 本文が少しずつしか来ない
            def read(self, n):
                now[0] += 4
                return b"\x89PNG\r\n\x1a\n" + bytes(8) if now[0] < 5 else bytes(10)
        now[0] = 0.0
        with self.assertRaises(ri.FetchError) as e:
            ri.fetch_image("https://a.example/", lookup=lambda h, t: [(PUBLIC, 4)], request=lambda *a: Trickle(200, {"content-type": "image/png"}), clock=lambda: now[0])
        self.assertIn("timeout", str(e.exception))

    def test_slow_name_resolution_is_cut(self):
        gate = threading.Event()
        orig = ri.socket.getaddrinfo
        ri.socket.getaddrinfo = lambda *a, **k: (gate.wait(5), [])[1]
        self.addCleanup(lambda: (gate.set(), setattr(ri.socket, "getaddrinfo", orig)))
        with self.assertRaises(ri.FetchError) as e:
            ri.default_lookup("slow.example", 0.2)
        self.assertIn("timeout", str(e.exception))


@unittest.skipUnless(shutil.which("openssl"), "openssl が無い")
class RealRequest(unittest.TestCase):
    """実物の要求: 接続先は渡したアドレスに固定され、証明書は元のホスト名で検証される。"""

    @classmethod
    def setUpClass(cls):
        d = helpers.tmpdir()
        cls.cert, key = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", cls.cert, "-days", "2", "-subj", "/CN=img.test",
                        "-addext", "subjectAltName=DNS:img.test"], check=True, capture_output=True)

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.seen.append((self.path, self.headers.get("Host"), self.headers.get("Cookie"), self.headers.get("Referer"), self.headers.get("Accept-Encoding")))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(PNG)))
                self.end_headers()
                self.wfile.write(PNG)

            def log_message(self, *a):
                pass
        cls.server = HTTPServer(("127.0.0.1", 0), H)
        cls.server.seen = []
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cls.cert, key)
        cls.server.socket = ctx.wrap_socket(cls.server.socket, server_side=True)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def request(self, host, address, port=None, context=None):
        ctx = context or ssl.create_default_context(cafile=self.cert)
        pinned = ri._Pinned(host, address, 5, ctx)
        pinned.port = port or self.server.server_address[1]       # 本物は 443 固定。ここだけ、手元の受け口の番号にする
        pinned._address = address
        orig = ri.socket.create_connection
        ri.socket.create_connection = lambda addr, t: orig((addr[0], pinned.port), t)
        try:
            pinned.request("GET", "/a.png", headers={"Host": host, "Accept-Encoding": "identity"})
            r = pinned.getresponse()
            return r.status, r.read()
        finally:
            ri.socket.create_connection = orig
            pinned.close()

    def test_pinned_address_with_hostname_verification(self):
        self.assertEqual(self.request("img.test", "127.0.0.1"), (200, PNG))     # 名前（img.test）は解決できないが、渡したアドレスに接続し、名前で証明書を検証できる
        self.assertEqual(self.server.seen[-1][:4], ("/a.png", "img.test", None, None))
        with self.assertRaises(ssl.SSLCertVerificationError):                    # 証明書の名前と違うホストでは、通さない
            self.request("other.test", "127.0.0.1")
        with self.assertRaises(ssl.SSLCertVerificationError):                    # 信用していない証明書は通さない
            self.request("img.test", "127.0.0.1", context=ssl.create_default_context())

    def test_proxy_environment_is_not_used(self):
        """プロキシの環境変数があっても、要求は検査したアドレスへ直接つなぐ。"""
        old = {k: os.environ.get(k) for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY")}
        os.environ.update(HTTPS_PROXY="http://127.0.0.1:1", https_proxy="http://127.0.0.1:1", ALL_PROXY="http://127.0.0.1:1")
        try:
            self.assertEqual(self.request("img.test", "127.0.0.1"), (200, PNG))
        finally:
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


class Localize(unittest.TestCase):
    """定義の外部 URL を取って file/N に付け替える（ask.localize_remote_media）。取れなかった画像は画像なしにする。"""

    def spec(self, **images):
        return {"questions": [{"id": "q", "label": "Q", "options": [dict({"value": k, "label": k}, **v) for k, v in images.items()]}]}

    def run_localize(self, spec, routes, dns=None):
        f = Fake(routes, dns)
        files, d = [], helpers.tmpdir()
        got = ask.localize_remote_media(spec, files, d, fetch=f.fetch)
        return f, files, got

    def test_success_failure_and_dedupe(self):
        spec = self.spec(ok={"image": "https://ok.example/a.png"}, same={"image": "https://ok.example/a.png"},
                         bad={"image": "https://127.0.0.1/a.png"}, wrongtype={"image": "https://txt.example/a.png"},
                         local={"image": "file/0"}, plain={})
        f, files, (failed, audio) = self.run_localize(spec, {"ok.example": png(), "txt.example": Res(200, {"Content-Type": "text/html"}, b"<p>x")})
        o = {x["value"]: x for x in spec["questions"][0]["options"]}
        self.assertEqual((failed, audio), (2, 0))
        self.assertEqual((o["ok"]["image"], o["same"]["image"]), ("file/0", "file/0"))        # 同じ URL は 1 回だけ取る
        self.assertEqual([c["host"] for c in f.calls], ["ok.example", "txt.example"])
        self.assertNotIn("image", o["bad"])                                                    # 取れなかった画像は、画像なしで出す
        self.assertNotIn("image", o["wrongtype"])
        self.assertEqual(o["local"]["image"], "file/0")                                         # ローカルのものは触らない
        self.assertEqual(len(files), 1)
        path, ctype = files[0]
        self.assertEqual((open(path, "rb").read(), ctype), (PNG, "image/png"))

    def test_served_like_a_local_file(self):
        """取った画像は、ローカルのファイルと同じ配り方（/token/file/N）で窓へ渡る。"""
        import urllib.request
        spec = self.spec(a={"image": "https://ok.example/a.png"})
        f, files, _ = self.run_localize(spec, {"ok.example": png()})
        server = ask_server(files)
        body = urllib.request.urlopen("http://127.0.0.1:%d/tok/%s" % (server.server_address[1], spec["questions"][0]["options"][0]["image"])).read()
        self.assertEqual(body, PNG)

    def test_external_audio_is_dropped_and_counted(self):
        spec = self.spec(a={"audio": "https://ok.example/a.mp3", "image": "https://ok.example/a.png"}, b={"audio": "data:audio/wav;base64,AAAA"})
        f, files, (failed, audio) = self.run_localize(spec, {"ok.example": png()})
        o = spec["questions"][0]["options"]
        self.assertEqual((failed, audio), (0, 1))
        self.assertNotIn("audio", o[0])
        self.assertEqual(o[1]["audio"], "data:audio/wav;base64,AAAA")                           # data: は今までどおり
        self.assertEqual([c["host"] for c in f.calls], ["ok.example"])                          # 音は取りに行かない

    def test_unexpected_error_is_a_failure_not_a_crash(self):
        spec = self.spec(a={"image": "https://boom.example/a.png"})
        files = []
        failed, _ = ask.localize_remote_media(spec, files, helpers.tmpdir(), fetch=lambda u, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertEqual((failed, files), (1, []))
        self.assertNotIn("image", spec["questions"][0]["options"][0])

    def test_total_size_cap(self):
        orig = ask.MEDIA_TOTAL_MAX
        ask.MEDIA_TOTAL_MAX = len(PNG) + 1
        self.addCleanup(setattr, ask, "MEDIA_TOTAL_MAX", orig)
        spec = self.spec(a={"image": "https://a.example/1.png"}, b={"image": "https://b.example/2.png"})
        f, files, (failed, _) = self.run_localize(spec, {"a.example": png(), "b.example": png()})
        self.assertEqual((failed, len(files)), (1, 1))                                          # 合計が上限を超えた分は取らない

    def test_data_uri_size_limit(self):
        import base64
        big = base64.b64encode(bytes(ask.MEDIA_FILE_MAX + 10)).decode()
        for key, mime in (("image", "image/png"), ("audio", "audio/wav")):
            with self.subTest(key):
                with self.assertRaises(ask.SpecError) as e:
                    ask.normalize({"questions": [{"id": "q", "label": "Q", "options": [{"value": "a", "label": "A", key: "data:%s;base64,%s" % (mime, big)}]}]})
                self.assertEqual(e.exception.reason, "too_large")
        ok = base64.b64encode(bytes(1000)).decode()
        ask.normalize({"questions": [{"id": "q", "label": "Q", "options": [{"value": "a", "label": "A", "image": "data:image/png;base64," + ok}]}]})   # 小さい data: は今までどおり


def ask_server(files):
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer(("127.0.0.1", 0), ask.make_handler(ask.State(), "tok", b"", files, [], "v"))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    unittest.main()
