#!/usr/bin/env python3
"""ask-form — 質問をまとめて 1 つの単発ウィンドウに出し、回答を JSON で受け取る。

  python3 ask.py spec.json        # 質問の定義（JSON）をファイルで渡す
  python3 ask.py - < spec.json    # 標準入力で渡す
  python3 ask.py --selftest       # 人の操作なしで、開く→答える→閉じる を確かめる（定義も渡せる）

標準出力に 1 行の JSON を出して終わる。終了コード:
  0 answered     回答あり           {"status":"answered","answers":{...}}
  1 error        定義の誤りなど     （標準エラーに理由）
  2 cancelled    回答せずに閉じた   {"status":"cancelled"}
  3 unavailable  ウィンドウを出せない環境 → 呼び出し側は AskUserQuestion に切り替える
  4 timeout      時間切れ           {"status":"timeout"}

Python3 の標準ライブラリだけで動く。ウィンドウは Chromium 系ブラウザ（Edge / Chrome など）の
--app モードで開く（タブ・アドレスバーの無い単独のウィンドウ）。

環境変数:
  ASK_FORM=off            ウィンドウを出さず、必ず unavailable を返す（画面の前に人がいない
                          マシンで動かすとき。例: 外からつなぐブラウザ版ターミナルのサーバー側）
  ASK_FORM_BROWSER=パス   使うブラウザを指定する
"""
import argparse
import glob
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
EXIT = {"answered": 0, "error": 1, "cancelled": 2, "unavailable": 3, "timeout": 4}
TYPES = ("single", "multi", "text")
OPEN_WAIT = 20      # ウィンドウがつながるまで待つ秒数（超えたら unavailable）
CLOSE_GRACE = 2.5   # 接続が切れてから「閉じられた」とみなすまでの秒数（再読み込みを許す）

SELFTEST_SPEC = {
    "title": "ask-form の動作確認",
    "intro": "このウィンドウは自動で回答して閉じます。",
    "questions": [
        {"id": "color", "label": "色", "type": "single", "default": "blue",
         "options": [{"value": "blue", "label": "青"}, {"value": "red", "label": "赤"}]},
        {"id": "extras", "label": "追加", "type": "multi", "default": ["a"],
         "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]},
    ],
}


# ── 質問の定義を検査して、既定を埋める ─────────────────────────────────────
def normalize(spec):
    if not isinstance(spec, dict) or not isinstance(spec.get("questions"), list) or not spec["questions"]:
        raise ValueError('"questions" に質問を 1 つ以上入れてください')
    seen = set()
    for i, q in enumerate(spec["questions"]):
        where = "questions[%d]" % i
        if not isinstance(q, dict) or not q.get("id") or not q.get("label"):
            raise ValueError("%s: id と label が必要です" % where)
        if q["id"] in seen:
            raise ValueError("%s: id「%s」が重複しています" % (where, q["id"]))
        seen.add(q["id"])
        q.setdefault("type", "single")
        if q["type"] not in TYPES:
            raise ValueError("%s: type は %s のいずれか" % (where, " / ".join(TYPES)))
        if q["type"] == "text":
            continue
        opts = q.get("options")
        if not isinstance(opts, list) or not opts:
            raise ValueError("%s: options に選択肢を 1 つ以上入れてください" % where)
        for j, o in enumerate(opts):
            if isinstance(o, str):
                o = opts[j] = {"value": o, "label": o}
            if not isinstance(o, dict) or "value" not in o:
                raise ValueError("%s.options[%d]: value が必要です" % (where, j))
            o["value"] = str(o["value"])
            o.setdefault("label", o["value"])
        values = [o["value"] for o in opts]
        if len(set(values)) != len(values):
            raise ValueError("%s: 選択肢の value が重複しています" % where)
        if q["type"] == "multi" and isinstance(q.get("default"), str):
            q["default"] = [q["default"]]
    for i, q in enumerate(spec["questions"]):
        for dep in (q.get("showIf") or {}):
            if dep not in seen:
                raise ValueError("questions[%d].showIf: 「%s」という id の質問がありません" % (i, dep))
    return spec


# ── 単発ウィンドウを開けるブラウザを探す ──────────────────────────────────
def is_wsl():
    try:
        return "microsoft" in open("/proc/version").read().lower()
    except OSError:
        return False


def find_browser():
    """Chromium 系ブラウザの実行ファイルを返す。見つからなければ (None, 理由)。"""
    if os.environ.get("ASK_FORM", "").lower() in ("off", "0", "no"):
        return None, "ASK_FORM=off が設定されています"
    override = os.environ.get("ASK_FORM_BROWSER")
    if override:
        path = override if os.path.exists(override) else shutil.which(override)
        return (path, None) if path else (None, "ASK_FORM_BROWSER=%s が見つかりません" % override)

    win_tails = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                 r"BraveSoftware\Brave-Browser\Application\brave.exe"]
    cands = []
    if sys.platform == "win32":
        for base in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            if os.environ.get(base):
                cands += [os.path.join(os.environ[base], t) for t in win_tails]
    elif is_wsl():
        for base in ("/mnt/c/Program Files (x86)", "/mnt/c/Program Files"):
            cands += [os.path.join(base, t.replace("\\", "/")) for t in win_tails]
        cands += glob.glob("/mnt/c/Users/*/AppData/Local/Google/Chrome/Application/chrome.exe")
    elif sys.platform == "darwin":
        if os.environ.get("SSH_CONNECTION"):
            return None, "SSH 越しのため、画面にウィンドウを出せません"
        cands = ["/Applications/%s.app/Contents/MacOS/%s" % (n, n) for n in
                 ("Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium")]
    else:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return None, "画面（DISPLAY）が無い環境です"
        cands = [p for p in (shutil.which(n) for n in (
            "google-chrome", "google-chrome-stable", "microsoft-edge", "microsoft-edge-stable",
            "chromium", "chromium-browser", "brave-browser")) if p]
    for c in cands:
        if os.path.exists(c):
            return c, None
    return None, "Chromium 系ブラウザ（Edge / Chrome など）が見つかりません"


# ── ウィンドウとやり取りする小さなサーバー ────────────────────────────────
class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.result = None          # {"status": ..., ...} が入ったら終わり
        self.conns = 0              # つながっているウィンドウの数
        self.connected_ever = False
        self.last_drop = 0.0

    def finish(self, result):
        with self.lock:
            if self.result is None:
                self.result = result


def make_handler(state, token, page):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _ok(self):
            return self.path.split("?")[0].startswith("/%s/" % token)

        def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._ok():
                return self._send(404)
            name = self.path.split("?")[0].rsplit("/", 1)[1]
            if name == "":
                return self._send(200, page, "text/html; charset=utf-8")
            if name == "ping":
                return self._send(200, b"ok")
            if name == "events":
                return self._events()
            self._send(404)

        def _events(self):
            # ウィンドウが開いている間つなぎっぱなしにする。切れたら「閉じられた」と分かる。
            # ページ側のタイマーは裏に回ると止められるので、ページからの定期連絡には頼らない。
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            with state.lock:
                state.conns += 1
                state.connected_ever = True
            try:
                while state.result is None:
                    self.wfile.write(b": keep\n\n")
                    self.wfile.flush()
                    time.sleep(0.5)
            except OSError:
                pass
            finally:
                with state.lock:
                    state.conns -= 1
                    state.last_drop = time.time()
                self.close_connection = True

        def do_POST(self):
            if not self._ok():
                return self._send(404)
            name = self.path.rsplit("/", 1)[1]
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if name == "answer":
                try:
                    data = json.loads(body.decode("utf-8"))
                except ValueError:
                    return self._send(400)
                self._send(204)
                state.finish(dict({"status": "answered"}, **data))
            elif name == "cancel":
                self._send(204)
                state.finish({"status": "cancelled"})
            else:
                self._send(404)

    return Handler


def done(result):
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(EXIT[result["status"]])


def main():
    ap = argparse.ArgumentParser(description="質問をまとめて単発ウィンドウに出し、回答を JSON で受け取る")
    ap.add_argument("spec", nargs="?", help="質問の定義（JSON ファイル。- で標準入力）")
    ap.add_argument("--timeout", type=int, default=540, help="回答を待つ秒数（既定 540）")
    ap.add_argument("--width", type=int, default=780, help="ウィンドウの幅")
    ap.add_argument("--height", type=int, default=820, help="ウィンドウの高さの上限（中身に合わせて縮む）")
    ap.add_argument("--check", action="store_true", help="定義の検査だけして終わる（ウィンドウは開かない）")
    ap.add_argument("--selftest", action="store_true", help="開く→既定の回答で自動的に答える→閉じる を確かめる（定義を渡せばその定義で）")
    args = ap.parse_args()

    try:
        if args.selftest and not args.spec:
            spec = json.loads(json.dumps(SELFTEST_SPEC))
        elif not args.spec:
            ap.error("質問の定義（JSON）を指定してください")
        else:
            raw = sys.stdin.read() if args.spec == "-" else open(args.spec, encoding="utf-8").read()
            spec = json.loads(raw)
        spec = normalize(spec)
    except (OSError, ValueError) as e:
        print("ask-form: 質問の定義を読めません: %s" % e, file=sys.stderr)
        sys.exit(EXIT["error"])
    if args.check:
        print("OK: 質問 %d 件" % len(spec["questions"]))
        return

    browser, why = find_browser()
    if not browser:
        done({"status": "unavailable", "reason": why})

    spec["_auto"] = bool(args.selftest)
    spec["_width"] = args.width
    spec["_maxHeight"] = args.height
    template = open(os.path.join(HERE, "form.html"), encoding="utf-8").read()
    page = template.replace("__SPEC__", json.dumps(spec, ensure_ascii=False).replace("</", "<\\/"))

    state = State()
    token = secrets.token_urlsafe(12)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state, token, page.encode("utf-8")))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://localhost:%d/%s/" % (server.server_address[1], token)

    try:
        subprocess.Popen([browser, "--app=" + url, "--window-size=%d,%d" % (args.width, args.height)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        done({"status": "unavailable", "reason": "ブラウザを起動できません: %s" % e})

    start = time.time()
    while state.result is None:
        time.sleep(0.1)
        now = time.time()
        with state.lock:
            closed = state.connected_ever and state.conns == 0 and now - state.last_drop > CLOSE_GRACE
            never = not state.connected_ever and now - start > OPEN_WAIT
        if closed:
            state.finish({"status": "cancelled"})
        elif never:
            state.finish({"status": "unavailable", "reason": "ウィンドウがつながりません（%d 秒待ちました）" % OPEN_WAIT})
        elif now - start > args.timeout:
            state.finish({"status": "timeout"})
    time.sleep(0.3)  # 最後の応答をウィンドウへ返し切る
    done(state.result)


if __name__ == "__main__":
    main()
