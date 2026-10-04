"""ask-form: 外部 URL（https://…）の画像を、ブラウザではなく ask.py が取って配るための取得部分。標準ライブラリだけで書く。

Sodashitsu の画面内のダイアログ（packages/server/src/ask/RemoteImageFetcher.ts・mediaSniff.ts）と同じ規則にする:
  - https のみ・ポート 443 のみ・URL に資格情報（user:pass@）があれば拒否
  - 名前解決で得た**全部**のアドレスが公開アドレスであること（ループバック・プライベート・リンクローカル・メタデータ・CGNAT・予約・
    マルチキャスト・IPv4 射影の IPv6 など、接続してはいけないものが 1 つでもあれば拒否。解釈できないものも拒否）
  - 接続は検査したアドレスに固定する（接続の直前にもう一度名前解決しない＝DNS リバインディング対策）。証明書の検証と SNI は元のホスト名
  - リダイレクトは 3 回まで。毎回、上の検査をやり直す
  - 全体で 10 秒・1 ファイル 8 MiB まで
  - プロキシの環境変数（HTTPS_PROXY など）は使わない・Cookie・Authorization・Referer は付けない
  - Content-Type が画像（png・jpeg・gif・webp・avif・svg）で、先頭バイトから決めた種類がそれと一致すること

これにより、利用者のマシン（IP）は画像の取得先に見えない（取りに行くのは ask.py を動かしているマシン）。
テストが差し替えられるよう、名前解決（lookup）と 1 回の要求（request）は引数で渡せる。
"""
import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
import unicodedata
import urllib.parse

MAX_BYTES = 8 * 1024 * 1024      # 1 ファイルの上限（Sodashitsu の ASK_MEDIA_FILE_MAX と同じ）
MAX_REDIRECTS = 3
TIMEOUT = 10.0                    # 秒。名前解決・接続・本文の読み取りを合わせた全体
REDIRECT_STATUS = (301, 302, 303, 307, 308)
ALLOWED_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp", "image/avif", "image/svg+xml")
ACCEPT = ", ".join(ALLOWED_TYPES)


class FetchError(Exception):
    """取得できない（理由は、定義の中身を含めない短い文）。"""


# ── アドレスの検査 ────────────────────────────────────────────────────────────

def _blocked_v4(p):
    a, b, c = p[0], p[1], p[2]
    return (a == 0 or a == 10 or (a == 100 and 64 <= b <= 127) or a == 127 or (a == 169 and b == 254)
            or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 0 and c in (0, 2)) or (a == 192 and b == 88 and c == 99)
            or (a == 192 and b == 168) or (a == 198 and b in (18, 19)) or (a == 198 and b == 51 and c == 100)
            or (a == 203 and b == 0 and c == 113) or a >= 224)


def is_blocked_address(addr):
    """接続してはいけないアドレスか。IPv6 は公開の単一宛先（2000::/3）から文書用・Teredo を除いたものだけ許し、
    IPv4 射影（::ffff:a.b.c.d）・6to4（2002::/16）は埋め込んだ IPv4 で判定する。解釈できないものは拒否。"""
    if not isinstance(addr, str) or "%" in addr:
        return True
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True
    b = ip.packed
    if ip.version == 4:
        return _blocked_v4(b)
    if b[:10] == bytes(10) and b[10:12] == b"\xff\xff":
        return _blocked_v4(b[12:])
    if (b[0] & 0xE0) != 0x20:      # 2000::/3 の外（::・::1・fc00::/7・fe80::/10・ff00::/8・64:ff9b::/96・IPv4 互換 など）
        return True
    if b[:4] == b"\x20\x01\x0d\xb8" or b[:4] == b"\x20\x01\x00\x00":   # 2001:db8::/32（文書用）・2001::/32（Teredo）
        return True
    if b[0] == 0x20 and b[1] == 0x02:   # 6to4
        return _blocked_v4(b[2:6])
    return False


def _number(part):
    """URL の標準（WHATWG）の IPv4 の 1 要素: 0x…（16 進）・先頭 0（8 進）・10 進。数でなければ None。"""
    if re.fullmatch(r"0[xX][0-9a-fA-F]*", part):
        return int(part[2:] or "0", 16)
    if re.fullmatch(r"0[0-7]+", part):
        return int(part, 8)
    if re.fullmatch(r"[0-9]+", part):
        return int(part, 10)
    return None


def _numeric_host(host):
    """ホスト名が「数で終わる」なら IPv4 の表記として解釈して点区切りにする（2130706433・0x7f000001・0177.0.0.1・127.1 など。
    ブラウザや OS の名前解決はこれらを 127.0.0.1 にするので、名前としては扱わない）。数で終わらなければ None（名前）。
    数で終わるのに IPv4 として解釈できないものは FetchError。"""
    parts = host.split(".")
    if parts and parts[-1] == "" and len(parts) > 1:
        parts = parts[:-1]
    if not parts or _number(parts[-1]) is None:
        return None
    if len(parts) > 4:
        raise FetchError("blocked host")
    nums = [_number(p) for p in parts]
    if any(n is None for n in nums):
        raise FetchError("blocked host")
    if any(n > 255 for n in nums[:-1]) or nums[-1] >= 256 ** (5 - len(nums)):
        raise FetchError("blocked host")
    value = nums[-1] + sum(n << (8 * (3 - i)) for i, n in enumerate(nums[:-1]))
    return str(ipaddress.IPv4Address(value))


def _clean_host(url):
    """URL のホストを検査し、(正規化したホスト名か IP, 要求に使う IP リテラルか None) を返す。"""
    if url.scheme != "https":
        raise FetchError("only https is allowed")
    if url.username is not None or url.password is not None or "@" in url.netloc:
        raise FetchError("credentials in the URL are not allowed")
    try:
        port = url.port
    except ValueError:
        raise FetchError("bad port")
    if port is not None and port != 443:
        raise FetchError("only port 443 is allowed")
    host = url.hostname or ""
    host = unicodedata.normalize("NFKC", host).replace("。", ".").lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(".localhost"):
        raise FetchError("blocked host")
    if ":" in host:      # IPv6 リテラル
        if is_blocked_address(host):
            raise FetchError("blocked address")
        return host, host
    if not host.isascii():
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise FetchError("bad host")
    if re.search(r"[\s/\\?#@%]", host):
        raise FetchError("bad host")
    dotted = _numeric_host(host)
    if dotted is not None:
        if is_blocked_address(dotted):
            raise FetchError("blocked address")
        return dotted, dotted
    return host, None


def default_lookup(host, timeout):
    """名前解決（全アドレス）。中止できない処理なので、別スレッドで待って時間の上限を効かせる。"""
    box = {}

    def work():
        try:
            box["r"] = [(i[4][0], 6 if i[0] == socket.AF_INET6 else 4)
                        for i in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
        except OSError as e:
            box["e"] = e
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(max(timeout, 0.01))
    if t.is_alive():
        raise FetchError("timeout")
    if "e" in box:
        raise FetchError("host not found")
    return box["r"]


# ── 実物の 1 回の要求 ────────────────────────────────────────────────────────

class _Pinned(http.client.HTTPSConnection):
    """接続先を `address`（検査済み）に固定する。SNI・証明書の検証は元のホスト名（`host`）。"""

    def __init__(self, host, address, timeout, context):
        super().__init__(host, 443, timeout=timeout, context=context)
        self._address = address

    def connect(self):
        sock = socket.create_connection((self._address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


class Response:
    def __init__(self, status, headers, reader, close):
        self.status, self.headers, self.read, self.close = status, headers, reader, close


def real_request(host, path, address, headers, timeout, context=None):
    """https の GET を 1 回。`address` へ接続する（`host` の名前解決はしない）。プロキシの環境変数は見ない。"""
    conn = _Pinned(host, address, timeout, context or ssl.create_default_context())
    try:
        conn.request("GET", path, headers=headers)
        r = conn.getresponse()
    except Exception:
        conn.close()
        raise
    return Response(r.status, {k.lower(): v for k, v in r.getheaders()}, r.read, conn.close)


# ── 先頭バイトからの種類（Sodashitsu の mediaSniff.ts の画像の分）──────────────────

def _ftyp_brands(b):
    if len(b) < 12 or b[4:8] != b"ftyp":
        return None
    size = int.from_bytes(b[0:4], "big")
    end = min(len(b), size if 16 <= size <= 4096 else 64)
    brands = [b[8:12].decode("latin-1")]
    for at in range(16, end - 3, 4):
        brands.append(b[at:at + 4].decode("latin-1"))
    return brands


def _is_svg(b):
    t = b[:8192].decode("utf-8", "replace").lstrip("﻿")
    for _ in range(32):
        t = t.lstrip()
        if t.startswith("<?"):
            end = t.find("?>")
            if end < 0:
                return False
            t = t[end + 2:]
        elif t.startswith("<!--"):
            end = t.find("-->")
            if end < 0:
                return False
            t = t[end + 3:]
        elif t[:9].upper() == "<!DOCTYPE":
            op, cl = t.find("["), t.find(">")
            if cl < 0:
                return False
            if 0 <= op < cl:
                end = t.find("]>")
                if end < 0:
                    return False
                t = t[end + 2:]
            else:
                t = t[cl + 1:]
        else:
            break
    return re.match(r"<svg[\s>/]", t) is not None


def sniff_image(b):
    """先頭バイトから画像の MIME を決める。画像でなければ None（音など、ほかの種類も None）。"""
    if len(b) < 4:
        return None
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    brands = _ftyp_brands(b)
    if brands is not None:
        return "image/avif" if (brands[0] in ("avif", "avis") or ("avif" in brands and brands[0] != "M4A ")) else None
    if _is_svg(b):
        return "image/svg+xml"
    return None


# ── 取得 ──────────────────────────────────────────────────────────────────────

def fetch_image(url_text, lookup=None, request=None, max_redirects=MAX_REDIRECTS, timeout=TIMEOUT, max_bytes=MAX_BYTES,
                clock=time.monotonic, on_bytes=None):
    """外部 URL の画像を取る。→ (本文のバイト列, MIME)。取れなければ FetchError。
    lookup(host, timeout) -> [(アドレス, 4 か 6), ...]、request(host, path, address, headers, timeout) -> Response は差し替えられる。
    on_bytes(n) は本文を受け取るたびに呼ぶ（呼び出し側の合計の上限を超えたら例外を投げて止める）。"""
    lookup = lookup or default_lookup
    request = request or real_request
    deadline = clock() + timeout
    remaining = lambda: deadline - clock()
    try:
        url = urllib.parse.urlsplit(url_text)
    except ValueError:
        raise FetchError("bad url")
    for hop in range(max_redirects + 1):
        host, literal = _clean_host(url)
        if remaining() <= 0:
            raise FetchError("timeout")
        addrs = [(literal, 6 if ":" in literal else 4)] if literal else lookup(host, remaining())
        if not addrs:
            raise FetchError("host not found")
        if any(is_blocked_address(a) for a, _ in addrs):    # 1 つでも接続してはいけないアドレスがあれば、全体を拒否する
            raise FetchError("blocked address")
        path = urllib.parse.urlunsplit(("", "", url.path or "/", url.query, "")) or "/"
        # 付けるのはこれだけ（Cookie・Authorization・Referer・Origin は付けない）
        headers = {"Accept": ACCEPT, "User-Agent": "ask-form", "Accept-Encoding": "identity",
                   "Host": "[%s]" % host if ":" in host else host}
        res, last = None, None
        for address, _family in addrs:       # 検査を通ったアドレスを順に試す。接続できなかったときだけ次へ
            if remaining() <= 0:
                raise FetchError("timeout")
            try:
                res = request(host, path, address, headers, max(remaining(), 0.01))
                break
            except FetchError:
                raise
            except (OSError, ssl.SSLError, http.client.HTTPException) as e:
                last = e
        if res is None:
            raise FetchError("connection failed" if last is not None else "no address")
        try:
            if res.status in REDIRECT_STATUS:
                if hop >= max_redirects:
                    raise FetchError("too many redirects")
                loc = res.headers.get("location")
                if not loc:
                    raise FetchError("redirect without location")
                try:
                    url = urllib.parse.urlsplit(urllib.parse.urljoin(urllib.parse.urlunsplit(url), loc))
                except ValueError:
                    raise FetchError("bad redirect")
                continue                      # 次の周で https・ポート・アドレスを検査し直す
            if res.status != 200:
                raise FetchError("unexpected status %d" % res.status)
            ctype = (res.headers.get("content-type") or "").split(";")[0].strip().lower()
            if ctype not in ALLOWED_TYPES:
                raise FetchError("unsupported content type")
            declared = res.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > max_bytes:
                raise FetchError("too large")
            chunks, size = [], 0
            while True:
                if remaining() <= 0:
                    raise FetchError("timeout")
                try:
                    chunk = res.read(65536)
                except (OSError, ssl.SSLError, http.client.HTTPException):
                    raise FetchError("read failed")
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError("too large")
                if on_bytes:
                    on_bytes(len(chunk))
                chunks.append(chunk)
            body = b"".join(chunks)
            if sniff_image(body) != ctype:
                raise FetchError("content does not match the content type")
            return body, ctype
        finally:
            res.close()
    raise FetchError("too many redirects")
