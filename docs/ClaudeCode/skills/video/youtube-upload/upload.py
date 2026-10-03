#!/usr/bin/env python3
"""動画ファイルを、YouTube に限定公開（unlisted）でアップロードする。標準ライブラリだけで動く。

  python3 upload.py check                              # 準備（OAuth クライアント・認可）ができているか
  python3 upload.py auth                               # ブラウザで認可する（最初の 1 回。使う人が自分で同意する）
  python3 upload.py upload 動画.webm --script 台本.txt   # 何を送るかを出す（まだ送らない）
  python3 upload.py upload 動画.webm --script 台本.txt --yes   # 送る。URL が出る
  python3 upload.py logout                             # 認可を取り消して、手元のトークンを消す

決まり（YouTube Data API v3 の公式の説明に合わせてある。SKILL.md の「決まり」）:
- 公開範囲は unlisted（限定公開）か private（非公開）だけ。公開（public）にはしない（公開は YouTube Studio で人がする）
- OAuth クライアントのファイルとトークンは ~/.config/youtube-upload/ に置き、画面にもログにも出さない
- 送るのは --yes を付けたときだけ。付けなければ、送る中身を出して終わる
"""
import argparse
import base64
import glob
import hashlib
import http.server
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HOME = os.environ.get("YOUTUBE_UPLOAD_HOME") or os.path.join(os.path.expanduser("~"), ".config", "youtube-upload")
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com"
SCOPE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"        # 動画とサムネイルを上げるだけ
SCOPE_CAPTIONS = "https://www.googleapis.com/auth/youtube.force-ssl"   # 字幕を上げるのに要る（アカウントの管理まで含む広い権限）
PRIVACY = {"unlisted": "限定公開", "private": "非公開"}
VIDEO_EXT = {".webm": "video/webm", ".mp4": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo"}
CHUNK = 8 * 1024 * 1024   # 256KB の倍数（最後の 1 個を除く）
RETRY, WAIT = 6, 2.0      # 途切れたときにやり直す回数と、最初の待ち（秒。倍々に延ばす）
EXIT_SETUP = 2            # 準備が要る（クライアントのファイルが無い・認可していない・認可が切れた）


class Fail(Exception):
    def __init__(self, msg, code=1):
        super().__init__(msg)
        self.code = code


def warn(msg):
    print("warn: " + msg)


# ---- HTTP ----
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):   # 308（続きを送れ）を転送として追わない
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(method, url, headers=None, body=None, timeout=120):
    """(状態, ヘッダー, 本文)。つながらないときは OSError。"""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


REASONS = {
    "quotaExceeded": "今日の API の割り当てを使い切りました（太平洋時間の 0 時に戻ります）",
    "uploadLimitExceeded": "このチャンネルが 1 日に上げられる本数を超えました",
    "youtubeSignupRequired": "この Google アカウントに YouTube のチャンネルがありません（YouTube でチャンネルを作ってから）",
    "insufficientPermissions": "認可した権限が足りません（auth をやり直す）",
    "accessNotConfigured": "Google Cloud のプロジェクトで YouTube Data API v3 が有効になっていません",
    "forbidden": "この操作は許されていません",
}


def api_error(what, status, body):
    reason = msg = ""
    try:
        e = json.loads(body.decode("utf-8", "replace")).get("error", {})
        if isinstance(e, dict):
            msg = e.get("message", "")
            reason = (e.get("errors") or [{}])[0].get("reason", "") or e.get("status", "")
        else:
            reason = str(e)
    except ValueError:
        msg = body.decode("utf-8", "replace")[:200]
    hint = REASONS.get(reason, "")
    return Fail("%sに失敗しました（HTTP %d %s）%s%s" % (what, status, reason, "。" + hint if hint else "", "\n       " + msg if msg else ""),
                EXIT_SETUP if status == 401 else 1)


# ---- 認可（OAuth 2.0。手元のアプリ用: ループバックと PKCE） ----
def _path(name):
    return os.path.join(HOME, name)


def load_client():
    p = _path("client_secret.json")
    if not os.path.exists(p):
        raise Fail("OAuth クライアントのファイルがありません: %s\n       Google Cloud で「デスクトップ アプリ」の OAuth クライアントを作り、JSON をこの名前で置きます（SKILL.md の「準備」）" % p, EXIT_SETUP)
    try:
        d = json.load(open(p, encoding="utf-8"))
    except ValueError:
        raise Fail("%s が JSON として読めません" % p, EXIT_SETUP)
    c = d.get("installed")
    if not c or not c.get("client_id"):
        raise Fail("%s は「デスクトップ アプリ」の OAuth クライアントではありません（「ウェブ アプリケーション」では、手元の認可ができません）" % p, EXIT_SETUP)
    return c


def _save_private(name, data):
    os.makedirs(HOME, exist_ok=True)
    try:
        os.chmod(HOME, 0o700)
    except OSError:
        pass
    p = _path(name)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.chmod(p, 0o600)


def load_token():
    try:
        return json.load(open(_path("token.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _token_request(form):
    try:
        st, _, body = fetch("POST", TOKEN_URI, {"Content-Type": "application/x-www-form-urlencoded"}, urllib.parse.urlencode(form).encode())
    except OSError as e:
        raise Fail("認可のサーバーにつながりません（%s）" % e)
    try:
        d = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        d = {}
    return st, d


def _keep(tok, d):
    """トークンの応答を、手元のファイルに残す形にする。"""
    tok = dict(tok or {})
    tok["access_token"] = d["access_token"]
    tok["expiry"] = time.time() + float(d.get("expires_in", 3600))
    if d.get("refresh_token"):
        tok["refresh_token"] = d["refresh_token"]
    if d.get("scope"):
        tok["scope"] = d["scope"]
    return tok


def access_token():
    """使えるアクセストークン。切れそうなら更新する。値は返すだけで、どこにも出さない。"""
    tok = load_token()
    if not tok or not tok.get("refresh_token"):
        raise Fail("まだ認可していません。`upload.py auth` を、画面の前にいる人が実行します", EXIT_SETUP)
    if tok.get("access_token") and tok.get("expiry", 0) - 60 > time.time():
        return tok["access_token"]
    c = load_client()
    st, d = _token_request({"client_id": c["client_id"], "client_secret": c.get("client_secret", ""), "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
    if st != 200 or not d.get("access_token"):
        if d.get("error") == "invalid_grant":
            raise Fail("認可が切れています。`upload.py auth` をやり直します\n       （OAuth の同意画面が「テスト中」のプロジェクトは、7 日で切れます）", EXIT_SETUP)
        raise Fail("トークンの更新に失敗しました（HTTP %d %s）" % (st, d.get("error", "")), EXIT_SETUP)
    tok = _keep(tok, d)
    _save_private("token.json", tok)
    return tok["access_token"]


def scopes():
    return set(((load_token() or {}).get("scope") or "").split())


def open_browser(url):
    """ブラウザを開く。WSL なら Windows 側のブラウザで。開けなくても、URL は画面に出してある。"""
    try:
        if "microsoft" in open("/proc/version").read().lower():
            if shutil.which("wslview"):
                return subprocess.call(["wslview", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
            if shutil.which("powershell.exe"):
                return subprocess.call(["powershell.exe", "-NoProfile", "-Command", "Start-Process '%s'" % url.replace("'", "%27")],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except OSError:
        pass
    try:
        import webbrowser
        return webbrowser.open(url)
    except Exception:
        return False


DONE_PAGE = """<!doctype html><meta charset="utf-8"><title>youtube-upload</title>
<body style="font-family:sans-serif;text-align:center;padding-top:20vh"><h2>%s</h2><p>この画面は閉じてかまいません。</p></body>"""


def cmd_auth(a):
    c = load_client()
    want = [SCOPE_UPLOAD] + ([SCOPE_CAPTIONS] if a.captions else [])
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "state" in q or "error" in q:
                got.update({k: v[0] for k, v in q.items()})
            ok = q.get("state", [""])[0] == state and "code" in q
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write((DONE_PAGE % ("認可が済みました" if ok else "認可できませんでした")).encode())

        def log_message(self, *x):   # 認可コードの入った URL をログに出さない
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = "http://127.0.0.1:%d" % srv.server_address[1]
    url = AUTH_URI + "?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": " ".join(want),
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state, "access_type": "offline", "prompt": "consent"})
    print("ブラウザで、動画を上げるチャンネルの Google アカウントを選び、同意します:\n\n  %s\n" % url)
    print("求める権限: " + "・".join(["動画のアップロード"] + (["字幕の管理（アカウントの管理を含む広い権限）"] if a.captions else [])))
    sys.stdout.flush()
    if a.paste:
        srv.server_close()
        print("同意の後、ブラウザは「接続できません」になります。そのアドレス欄の URL（http://127.0.0.1:… で始まる）を貼って Enter:")
        q = urllib.parse.parse_qs(urllib.parse.urlparse(sys.stdin.readline().strip()).query)
        got.update({k: v[0] for k, v in q.items()})
    else:
        if not a.no_browser:
            open_browser(url)
        srv.timeout = 1
        end = time.time() + a.timeout
        while not got and time.time() < end:
            srv.handle_request()
        srv.server_close()
    if got.get("error"):
        raise Fail("認可されませんでした（%s）" % got["error"])
    if not got.get("code"):
        raise Fail("時間内（%d 秒）に同意が届きませんでした。同意したのにブラウザが「接続できません」になったなら、`upload.py auth --paste` を使います" % a.timeout)
    if got.get("state") != state:
        raise Fail("認可の応答が、この実行のものではありません（state が違う）。やり直します")
    st, d = _token_request({"client_id": c["client_id"], "client_secret": c.get("client_secret", ""), "code": got["code"], "code_verifier": verifier,
                            "grant_type": "authorization_code", "redirect_uri": redirect})
    if st != 200 or not d.get("access_token"):
        raise Fail("トークンを受け取れませんでした（HTTP %d %s）" % (st, d.get("error", "")))
    if not d.get("refresh_token"):
        raise Fail("更新用のトークンが返りませんでした。Google アカウントの「サードパーティのアプリとサービス」でこのアプリの接続を外してから、やり直します")
    if not d.get("scope"):
        d["scope"] = " ".join(want)
    _save_private("token.json", _keep({}, d))
    print("OK : 認可しました（%s に保存。中身は画面に出しません）" % _path("token.json"))
    if a.captions and SCOPE_CAPTIONS not in scopes():
        warn("字幕の権限は認められませんでした（字幕は YouTube Studio から上げます）")
    return 0


def cmd_check(a):
    ok = True
    try:
        load_client()
        print("OK : OAuth クライアントのファイル（%s）" % _path("client_secret.json"))
    except Fail as e:
        ok = False
        print("NG : " + str(e))
    tok = load_token()
    if tok and tok.get("refresh_token"):
        s = scopes()
        print("OK : 認可ずみ（動画のアップロード%s）" % ("・字幕" if SCOPE_CAPTIONS in s else "。字幕の権限は無し"))
        if SCOPE_UPLOAD not in s and SCOPE_CAPTIONS not in s:
            ok = False
            print("NG : アップロードの権限がありません。`upload.py auth` をやり直します")
    else:
        ok = False
        print("NG : まだ認可していません。`upload.py auth` を、画面の前にいる人が実行します")
    return 0 if ok else EXIT_SETUP


def cmd_logout(a):
    tok = load_token()
    if not tok:
        print("OK : 手元にトークンはありません")
        return 0
    t = tok.get("refresh_token") or tok.get("access_token")
    try:
        st, _, _ = fetch("POST", REVOKE_URI, {"Content-Type": "application/x-www-form-urlencoded"}, urllib.parse.urlencode({"token": t}).encode())
        print("OK : 認可を取り消しました" if st == 200 else "warn: 取り消しの応答が HTTP %d でした（Google アカウントの設定からも外せます）" % st)
    except OSError as e:
        warn("取り消しのサーバーにつながりません（%s）。手元のトークンだけ消します" % e)
    os.remove(_path("token.json"))
    print("OK : 手元のトークンを消しました")
    return 0


# ---- 何を送るか ----
def header(script):
    """台本の先頭の設定。yukkuri-kaisetsu の .txt は --- の間の「名前: 値」、motion-video の .json は一番上の値。"""
    if script.endswith(".json"):
        try:
            d = json.load(open(script, encoding="utf-8"))
        except ValueError:
            raise Fail("%s が JSON として読めません" % script)
        return {k: (", ".join(v) if isinstance(v, list) else str(v)) for k, v in d.items() if k in ("title", "tags", "summary") and v}
    out, inside = {}, False
    for line in open(script, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.strip() == "---":
            if inside:
                break
            inside = True
            continue
        if inside:
            m = re.match(r"\s*([\w.]+)\s*:\s*(.*)$", re.sub(r"\s#\s.*$", "", line))
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def tag_length(tags):
    """YouTube の数え方: 項目の間のカンマも数え、空白を含むタグは引用符 2 字ぶん多く数える。"""
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)


def gather(a):
    video = os.path.abspath(a.video)
    if not os.path.isfile(video):
        raise Fail("動画のファイルがありません: %s" % a.video)
    ext = os.path.splitext(video)[1].lower()
    if ext in (".html", ".htm"):
        raise Fail("HTML は上げられません。プレイヤーの「WebM で保存」か record.py で、動画のファイルにしてから渡します")
    if ext not in VIDEO_EXT:
        raise Fail("動画のファイルではありません（%s）。使えるのは %s" % (ext or "拡張子なし", "・".join(sorted(VIDEO_EXT))))
    size = os.path.getsize(video)
    if size == 0:
        raise Fail("動画のファイルが空です: %s" % a.video)
    head, stem = {}, None
    if a.script:
        if not os.path.isfile(a.script):
            raise Fail("台本がありません: %s" % a.script)
        head, stem = header(a.script), os.path.splitext(os.path.abspath(a.script))[0]

    def near(explicit, *cands):
        if explicit:
            if not os.path.isfile(explicit):
                raise Fail("ファイルがありません: %s" % explicit)
            return os.path.abspath(explicit)
        for c in cands:
            hit = sorted(glob.glob(c)) if stem else []
            if hit:
                return hit[0]
        return None

    e = glob.escape(stem) if stem else ""
    desc_file = near(a.description, e + ".description.txt", os.path.join(e + "_export", "youtube_description.txt"))
    plan = {
        "video": video, "size": size, "mime": VIDEO_EXT[ext],
        "title": (a.title or head.get("title") or "").strip(),
        "description": open(desc_file, encoding="utf-8").read().strip() if desc_file else head.get("summary", ""),
        "description_file": desc_file,
        "tags": [t.strip() for t in re.split(r"[,、]", a.tags if a.tags is not None else head.get("tags", "")) if t.strip()],
        "thumbnail": near(a.thumbnail, e + ".thumbnail.png", e + ".thumbnail.jpg"),
        "captions": None if a.no_captions else near(a.captions, os.path.join(e + "_export", "*.%s.srt" % a.lang), os.path.join(e + "_export", "*.%s.vtt" % a.lang)),
        "privacy": a.privacy, "category": a.category, "lang": a.lang, "kids": a.made_for_kids, "synthetic": a.synthetic, "notify": a.notify,
    }
    if a.no_thumbnail:
        plan["thumbnail"] = None
    if not plan["title"]:
        raise Fail("題がありません。--title で渡すか、--script の台本に title: を書きます")
    if len(plan["title"]) > 100:
        raise Fail("題が長すぎます（%d 字。YouTube は 100 字まで）" % len(plan["title"]))
    for name, text in (("題", plan["title"]), ("概要欄", plan["description"])):
        if "<" in text or ">" in text:
            raise Fail("%sに < か > が入っています（YouTube は受け付けません）。全角の ＜ ＞ に替えるか、外します" % name)
    n = len(plan["description"].encode("utf-8"))
    if n > 5000:
        raise Fail("概要欄が長すぎます（%d バイト。YouTube は 5000 バイトまで＝かなで約 1,600 字）。出典・クレジットを短くします" % n)
    if not plan["description"]:
        warn("概要欄が空です（yukkuri-publish の publish.py で <台本名>.description.txt を作ると、目次・出典・クレジットが入ります）")
    while tag_length(plan["tags"]) > 500:
        warn("タグが 500 字を超えるので、後ろの「%s」を外します" % plan["tags"].pop())
    if plan["thumbnail"] and os.path.getsize(plan["thumbnail"]) > 2 * 1024 * 1024:
        warn("サムネイルが 2MB を超えています（YouTube Studio の目安は 2MB まで）")
    return plan


def mb(n):
    return "%.1fMB" % (n / 1048576) if n < 1 << 30 else "%.2fGB" % (n / (1 << 30))


def show(plan):
    d = plan["description"]
    rows = [
        ("動画", "%s（%s）" % (plan["video"], mb(plan["size"]))),
        ("公開範囲", "%s（%s）" % (PRIVACY[plan["privacy"]], plan["privacy"])),
        ("題", plan["title"]),
        ("概要欄", "%s（%d 行・%d バイト）" % (plan["description_file"] or "台本の summary", d.count("\n") + 1, len(d.encode("utf-8"))) if d else "なし"),
        ("タグ", "、".join(plan["tags"]) or "なし"),
        ("サムネイル", plan["thumbnail"] or "なし（YouTube が動画から選ぶ）"),
        ("字幕", plan["captions"] or "なし"),
        ("子ども向け", "子ども向けである" if plan["kids"] else "子ども向けではない"),
        ("登録者への通知", "する" if plan["notify"] else "しない"),
    ]
    if plan["category"]:
        rows.append(("カテゴリ", plan["category"]))
    if plan["synthetic"]:
        rows.append(("合成コンテンツの開示", "する"))
    for k, v in rows:
        print("  %s: %s" % (k, v))


def body_of(plan):
    snippet = {"title": plan["title"], "description": plan["description"], "defaultLanguage": plan["lang"], "defaultAudioLanguage": plan["lang"]}
    if plan["tags"]:
        snippet["tags"] = plan["tags"]
    if plan["category"]:
        snippet["categoryId"] = str(plan["category"])
    status = {"privacyStatus": plan["privacy"], "selfDeclaredMadeForKids": bool(plan["kids"])}
    if plan["synthetic"]:
        status["containsSyntheticMedia"] = True
    return {"snippet": snippet, "status": status}


# ---- 送る ----
def start_session(plan):
    """続きから送れるアップロード（resumable）を始め、送り先の URL を返す。"""
    url = API + "/upload/youtube/v3/videos?" + urllib.parse.urlencode({"uploadType": "resumable", "part": "snippet,status", "notifySubscribers": "true" if plan["notify"] else "false"})
    st, h, body = fetch("POST", url, {"Authorization": "Bearer " + access_token(), "Content-Type": "application/json; charset=UTF-8",
                                     "X-Upload-Content-Length": str(plan["size"]), "X-Upload-Content-Type": plan["mime"]}, json.dumps(body_of(plan)).encode("utf-8"))
    if st != 200 or not h.get("Location"):
        raise api_error("アップロードの開始", st, body)
    return h["Location"]


def _next(h):
    m = re.search(r"-(\d+)$", h.get("Range") or "")
    return int(m.group(1)) + 1 if m else 0


def send(session, plan, progress=None, sleep=time.sleep):
    """動画を CHUNK ずつ送る。途切れたら、届いている所を聞いて続きから送る。返すのは動画のリソース。"""
    size, offset, tries = plan["size"], 0, 0
    with open(plan["video"], "rb") as f:
        while True:
            f.seek(offset)
            data = f.read(CHUNK)
            st = None
            try:
                st, h, body = fetch("PUT", session, {"Authorization": "Bearer " + access_token(), "Content-Type": plan["mime"],
                                                    "Content-Range": "bytes %d-%d/%d" % (offset, offset + len(data) - 1, size)}, data, timeout=600)
            except OSError:
                pass
            while st is None or st in (500, 502, 503, 504):   # 途切れた: 待ってから、どこまで届いたかを聞く
                tries += 1
                if tries > RETRY:
                    raise Fail("アップロードが %d 回続けて途切れました。回線を確かめて、もう一度実行します" % RETRY)
                sleep(WAIT * 2 ** (tries - 1))
                try:
                    st, h, body = fetch("PUT", session, {"Authorization": "Bearer " + access_token(), "Content-Range": "bytes */%d" % size}, b"")
                except OSError:
                    st = None
            if st in (200, 201):
                return json.loads(body.decode("utf-8"))
            if st == 308:
                new = _next(h)
                if new > offset:
                    tries = 0
                offset = new
                if progress:
                    progress(offset, size)
                continue
            if st == 404:
                raise Fail("アップロードの受け付けが切れました。もう一度実行します（最初から送り直します）")
            raise api_error("アップロード", st, body)


def set_thumbnail(vid, path):
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    st, _, body = fetch("POST", API + "/upload/youtube/v3/thumbnails/set?" + urllib.parse.urlencode({"videoId": vid, "uploadType": "media"}),
                       {"Authorization": "Bearer " + access_token(), "Content-Type": mime}, open(path, "rb").read())
    if st != 200:
        raise api_error("サムネイルの設定", st, body)


def add_captions(vid, path, lang):
    bound = "mv" + secrets.token_hex(12)
    meta = json.dumps({"snippet": {"videoId": vid, "language": lang, "name": ""}}).encode("utf-8")
    body = b"".join([b"--" + bound.encode() + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n", meta,
                     b"\r\n--" + bound.encode() + b"\r\nContent-Type: application/octet-stream\r\n\r\n", open(path, "rb").read(),
                     b"\r\n--" + bound.encode() + b"--\r\n"])
    st, _, out = fetch("POST", API + "/upload/youtube/v3/captions?" + urllib.parse.urlencode({"uploadType": "multipart", "part": "snippet"}),
                      {"Authorization": "Bearer " + access_token(), "Content-Type": "multipart/related; boundary=" + bound}, body)
    if st != 200:
        raise api_error("字幕のアップロード", st, out)


def record_path(video):
    return os.path.splitext(video)[0] + ".youtube.json"


def cmd_upload(a):
    plan = gather(a)
    print("YouTube に上げる中身:")
    show(plan)
    rec = record_path(plan["video"])
    if os.path.exists(rec) and not a.again:
        try:
            old = json.load(open(rec, encoding="utf-8"))
        except ValueError:
            old = {}
        if old.get("size") == plan["size"] and old.get("mtime") == int(os.path.getmtime(plan["video"])):
            raise Fail("このファイルは、もう上げてあります: %s\n       もう 1 本上げるなら --again（前の動画は消えません。YouTube Studio で消します）" % old.get("url", rec))
    if plan["captions"] and SCOPE_CAPTIONS not in scopes():
        print("  （字幕は上げません: 字幕の権限で認可していない。上げるなら `upload.py auth --captions`。YouTube Studio からも上げられます）")
        plan["captions"] = None
    if not a.yes:
        print("\nまだ送っていません。この中身でよければ --yes を付けて実行します。")
        return 0
    access_token()   # 送る前に、認可が生きているかを確かめる
    print("\n送っています…")
    sys.stdout.flush()
    session = start_session(plan)

    def progress(done, size):
        print("  %3d%%（%s / %s）" % (done * 100 // size, mb(done), mb(size)))
        sys.stdout.flush()
    res = send(session, plan, progress)
    vid = res.get("id")
    if not vid:
        raise Fail("アップロードの応答に、動画の ID がありません")
    got = (res.get("status") or {}).get("privacyStatus", "")
    out = {"videoId": vid, "url": "https://youtu.be/" + vid, "studio": "https://studio.youtube.com/video/%s/edit" % vid, "privacy": got or plan["privacy"],
           "title": plan["title"], "file": plan["video"], "size": plan["size"], "mtime": int(os.path.getmtime(plan["video"])),
           "uploadedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "thumbnail": None, "captions": None}
    for key, label, fn in (("thumbnail", "サムネイル", lambda p: set_thumbnail(vid, p)), ("captions", "字幕", lambda p: add_captions(vid, p, plan["lang"]))):
        if plan[key]:
            try:
                fn(plan[key])
                out[key] = "ok"
                print("OK : %sを付けました" % label)
            except (Fail, OSError) as e:   # 動画はもう上がっている。付けられなかった分だけ知らせる
                out[key] = "failed"
                warn("%sは付けられませんでした（動画は上がっています。YouTube Studio から付けます）\n       %s" % (label, e))
    with open(rec, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("OK : %s（%s）" % (out["url"], PRIVACY.get(out["privacy"], out["privacy"])))
    print("     YouTube Studio: " + out["studio"])
    print("     記録: " + rec)
    if got and got != plan["privacy"]:
        warn("頼んだ公開範囲（%s）と違う「%s」になっています。YouTube Studio で確かめます" % (plan["privacy"], got))
    print("note: 審査（API の監査）を受けていない Google Cloud のプロジェクトから上げた動画は、YouTube が非公開（private）に固定します。\n"
          "      限定公開になっているかを、YouTube Studio で 1 回確かめてください。処理（HD 化）が終わるまで数分かかります。")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="動画を YouTube に限定公開でアップロードする")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="準備ができているか").set_defaults(fn=cmd_check)
    p = sub.add_parser("auth", help="ブラウザで認可する（最初の 1 回）")
    p.add_argument("--captions", action="store_true", help="字幕も上げられる権限で認可する（アカウントの管理を含む広い権限）")
    p.add_argument("--no-browser", action="store_true", help="ブラウザを自動で開かない（出た URL を自分で開く）")
    p.add_argument("--paste", action="store_true", help="同意の後の URL を貼って渡す（ブラウザから 127.0.0.1 に届かないとき）")
    p.add_argument("--timeout", type=int, default=300, help="同意を待つ秒数（既定 300）")
    p.set_defaults(fn=cmd_auth)
    sub.add_parser("logout", help="認可を取り消して、手元のトークンを消す").set_defaults(fn=cmd_logout)
    p = sub.add_parser("upload", help="動画を上げる（--yes を付けたときだけ送る）")
    p.add_argument("video", help="動画のファイル（.webm・.mp4 など）")
    p.add_argument("--script", help="台本（yukkuri-kaisetsu の .txt・motion-video の .json）。題・タグと、隣の概要欄・サムネイル・字幕を拾う")
    p.add_argument("--title")
    p.add_argument("--description", help="概要欄のファイル")
    p.add_argument("--tags", help="タグ（カンマ区切り）")
    p.add_argument("--thumbnail", help="サムネイル（PNG・JPEG）")
    p.add_argument("--captions", help="字幕（SRT・WebVTT）")
    p.add_argument("--no-thumbnail", action="store_true")
    p.add_argument("--no-captions", action="store_true")
    p.add_argument("--privacy", choices=sorted(PRIVACY), default="unlisted", help="unlisted（限定公開。既定）・private（非公開）。公開にはしない")
    p.add_argument("--lang", default="ja", help="題・音声・字幕の言語（既定 ja）")
    p.add_argument("--category", help="カテゴリの ID（書かなければ YouTube の既定）")
    p.add_argument("--made-for-kids", action="store_true", help="子ども向けの動画として申告する（既定は「子ども向けではない」）")
    p.add_argument("--synthetic", action="store_true", help="「改変または合成されたコンテンツ」として開示する")
    p.add_argument("--notify", action="store_true", help="チャンネル登録者に通知する（既定はしない）")
    p.add_argument("--again", action="store_true", help="同じファイルを、もう 1 本上げる")
    p.add_argument("--yes", action="store_true", help="送る（付けなければ、送る中身を出すだけ）")
    p.set_defaults(fn=cmd_upload)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except Fail as e:
        print("error: %s" % e, file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        print("error: 中断しました", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
