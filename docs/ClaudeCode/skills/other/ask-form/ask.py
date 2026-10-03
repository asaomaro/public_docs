#!/usr/bin/env python3
"""ask-form — 質問をまとめて 1 つの単発ウィンドウに出し、回答を JSON で受け取る。

  python3 ask.py spec.json        # 質問の定義（JSON）をファイルで渡す
  python3 ask.py - < spec.json    # 標準入力で渡す
  python3 ask.py --selftest       # 人の操作なしで、開く→答える→閉じる を確かめる（定義も渡せる）

標準出力に 1 行の JSON を出して終わる。終了コード:
  0 answered     回答あり           {"status":"answered","answers":{...}}
  1 error        定義の誤りなど     （標準エラーに理由）
  2 cancelled    回答せずに閉じた   {"status":"cancelled"}
  3 unavailable  ウィンドウを出せない・画面の前に人がいない → 呼び出し側は AskUserQuestion に切り替える
  4 timeout      時間切れ           {"status":"timeout"}

Python3 の標準ライブラリだけで動く。ウィンドウは Chromium 系ブラウザ（Edge / Chrome など）の
--app モードで開く（タブ・アドレスバーの無い単独のウィンドウ）。

環境変数:
  ASK_FORM=off              ウィンドウを出さず、必ず unavailable を返す（画面の前に人がいない
                            マシンで動かすとき。例: 外からつなぐブラウザ版ターミナルのサーバー側）
  ASK_FORM_BROWSER=パス     使うブラウザを指定する
  ASK_FORM_SODA=off         Sodashitsu の pane の中でも、sodactl ask を使わずにウィンドウを開く

Sodashitsu（soda）の pane の中で動いているとき（SODA_PANE_ID があり sodactl が PATH にある）は、
ウィンドウを開く前に sodactl ask へ渡し、その pane を見ているブラウザの画面にフォームを出す
（ブラウザが別のマシンでも届く。ASK_FORM=off でも行う）。出せないとき——つながっているブラウザが無い・
sodactl ask が対応していない型（edit・rank・table）や画像・音・コードのプレビューがある——は、
今までどおりこのマシンのウィンドウへ進む。
  ASK_FORM_AWAY_SECONDS=秒  --away-after の既定（300）
  ASK_FORM_REACT_SECONDS=秒 --react-within の既定（90）
"""
import argparse
import base64
import glob
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
EXIT = {"answered": 0, "error": 1, "cancelled": 2, "unavailable": 3, "timeout": 4}
TYPES = ("single", "multi", "text", "edit", "rank", "table")
CHOICE_TYPES = ("single", "multi", "rank", "table")   # options を持つ型
PREVIEWS = ("side", "inline")
SCALAR = (str, int, float, bool)
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".avif": "image/avif", ".svg": "image/svg+xml"}
AUDIO_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".oga": "audio/ogg",
               ".opus": "audio/ogg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".flac": "audio/flac"}
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
class SpecError(ValueError):
    """定義の誤り。reason は誤りの分類（fixtures/normalize.json と、同じ検査をする Sodashitsu とで共通の名前）。"""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def normalize(spec, base_dir="."):
    """定義を検査して既定を埋める。選択肢の image・audio がローカルのファイルなら、受け口から配る番号付きの
    アドレス（file/N）に書き換え、(パス, 種類) の一覧を spec["_files"] に入れる。"""
    files = []

    def local_file(o, key, types, where):
        ref = o.get(key)
        if not ref or re.match(r"^(https?://|data:)", ref):
            return
        path = os.path.join(base_dir, os.path.expanduser(ref))
        ctype = types.get(os.path.splitext(path)[1].lower())
        if not ctype:
            raise SpecError("media_type", "%s: %s は %s のいずれか（%s）" % (where, key, " / ".join(sorted(types)), ref))
        if not os.path.isfile(path):
            raise SpecError("media_missing", "%s: %s のファイルがありません（%s）" % (where, key, path))
        files.append((os.path.abspath(path), ctype))
        o[key] = "file/%d" % (len(files) - 1)

    def items(q, key, where):
        lst = q.get(key)
        if not isinstance(lst, list) or not lst:
            raise SpecError("options_empty", "%s: %s に 1 つ以上入れてください" % (where, key))
        for j, o in enumerate(lst):
            if isinstance(o, str):
                o = lst[j] = {"value": o, "label": o}
            if not isinstance(o, dict) or "value" not in o:
                raise SpecError("option_value_required", "%s.%s[%d]: value が必要です" % (where, key, j))
            o["value"] = str(o["value"])
            if not isinstance(o.get("label"), str):
                o["label"] = o["value"]
            if o.get("recommended") is True:
                o["recommended"] = True
            else:
                o.pop("recommended", None)
            colors = [c for c in o["colors"] if isinstance(c, str) and COLOR_RE.match(c)][:16] if isinstance(o.get("colors"), list) else []
            if colors:
                o["colors"] = colors
            else:
                o.pop("colors", None)
        values = [o["value"] for o in lst]
        if len(set(values)) != len(values):
            raise SpecError("option_value_duplicate", "%s: %s の value が重複しています" % (where, key))
        return lst

    if not isinstance(spec, dict) or not isinstance(spec.get("questions"), list) or not spec["questions"]:
        raise SpecError("questions_empty", '"questions" に質問を 1 つ以上入れてください')
    paging = spec.get("paging")
    if not (paging in (None, "auto") or isinstance(paging, bool) or (isinstance(paging, int) and paging >= 1)):
        raise SpecError("paging_invalid", '"paging" は "auto"（高さに収まらないときだけ目次を出す）/ true（必ず出す）/ false（出さない）')
    seen = set()
    for i, q in enumerate(spec["questions"]):
        where = "questions[%d]" % i
        if not isinstance(q, dict) or not q.get("id") or not q.get("label"):
            raise SpecError("id_label_required", "%s: id と label が必要です" % where)
        if q["id"] in seen:
            raise SpecError("id_duplicate", "%s: id「%s」が重複しています" % (where, q["id"]))
        seen.add(q["id"])
        if q.get("page") is not None and not isinstance(q["page"], str):
            raise SpecError("page_invalid", "%s: page はまとまりの題（文字列）で渡してください" % where)
        q.setdefault("type", "single")
        if q["type"] not in TYPES:
            raise SpecError("unknown_type", "%s: type は %s のいずれか" % (where, " / ".join(TYPES)))
        # 部品（ask-form.js）が受ける形に揃える（fixtures/normalize.json の「正規化後」。Sodashitsu の normalizeAskSpec と同じ形）
        q["allowOther"] = q.get("allowOther") is True
        q["required"] = (q.get("required") is not False) if q["type"] == "edit" else (q.get("required") is True)
        q["multiline"] = q.get("multiline") is True
        mw = q.get("minWidth")
        if not (isinstance(mw, int) and not isinstance(mw, bool) and 60 <= mw <= 600):
            q.pop("minWidth", None)
        if q["type"] == "text" and not isinstance(q.get("default"), str):
            q.pop("default", None)
        sif = q.get("showIf")
        if not sif:
            q.pop("showIf", None)
        elif not isinstance(sif, dict):
            raise SpecError("showif_invalid", "%s: showIf は {質問の id: 値} で渡してください" % where)
        else:
            q["showIf"] = {str(k): [str(x) for x in (v if isinstance(v, list) else [v]) if isinstance(x, SCALAR)] for k, v in sif.items()}
        if q["type"] == "single" and isinstance(q.get("default"), list):
            q["default"] = q["default"][0] if q["default"] else None
        if q["type"] == "single" and q.get("default") is not None:
            q["default"] = str(q["default"])
        if q["type"] == "multi" and isinstance(q.get("default"), list):
            q["default"] = [str(x) for x in q["default"] if isinstance(x, SCALAR)]
        if q.get("default") is None:
            q.pop("default", None)
        if q["type"] not in CHOICE_TYPES:
            q["options"] = []
            continue
        for j, o in enumerate(items(q, "options", where)):
            ow = "%s.options[%d]" % (where, j)
            if "code" in o and not isinstance(o["code"], str):
                raise SpecError("code_invalid", "%s: code は文字列で渡してください" % ow)
            local_file(o, "image", IMAGE_TYPES, ow)
            local_file(o, "audio", AUDIO_TYPES, ow)
        if q["type"] == "table":
            values = {o["value"] for o in q["options"]}
            for j, r in enumerate(items(q, "rows", where)):
                if r.get("default") is not None and str(r["default"]) not in values:
                    raise SpecError("row_default_unknown", "%s.rows[%d]: default「%s」が options にありません" % (where, j, r["default"]))
        if q.get("preview") not in (None,) + PREVIEWS:
            raise SpecError("preview_invalid", "%s: preview は %s のいずれか" % (where, " / ".join(PREVIEWS)))
        if q["type"] == "multi" and isinstance(q.get("default"), str):
            q["default"] = [q["default"]]
    if not isinstance(spec.get("title"), str):
        spec["title"] = "質問"
    if not isinstance(spec.get("submit"), str):
        spec["submit"] = "決定"
    if isinstance(spec.get("note"), str):       # 補足の欄の入力例
        spec["notePlaceholder"] = spec["note"]
    spec["note"] = spec.get("note") is not False
    for i, q in enumerate(spec["questions"]):
        for dep in (q.get("showIf") or {}):
            if dep not in seen:
                raise SpecError("showif_unknown_id", "questions[%d].showIf: 「%s」という id の質問がありません" % (i, dep))
    spec["_files"] = files
    return spec


# ── 前回の回答を既定にする（定義の "remember": "名前"） ───────────────────
def remember_path(key):
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "ask-form", "remember", re.sub(r"[^\w.-]", "_", str(key)) + ".json")


def apply_remembered(spec):
    """前回の回答のうち、今回の定義でもそのまま選べるものだけを既定にする。
    自由記述（text・edit）と、選択肢に無い値（自由入力）は持ち越さない。"""
    try:
        last = json.load(open(remember_path(spec["remember"]), encoding="utf-8"))
    except (OSError, ValueError):
        return
    for q in spec["questions"]:
        v = last.get(q["id"])
        if v is None or q.get("remember") is False or q["type"] not in CHOICE_TYPES:
            continue
        values = [o["value"] for o in q["options"]]
        if q["type"] == "single":
            new = v if v in values else None
        elif q["type"] == "multi":
            new = [x for x in v if x in values] if isinstance(v, list) else None
        elif q["type"] == "rank":
            new = v if isinstance(v, list) and sorted(v) == sorted(values) else None
        else:  # table: 行ごとに持ち越す
            hit = False
            for r in q["rows"]:
                if isinstance(v, dict) and v.get(r["value"]) in values and v[r["value"]] != r.get("default", q.get("default")):
                    r["_default0"] = r.get("default", q.get("default"))
                    r["default"] = v[r["value"]]
                    hit = True
            if hit:
                q["_remembered"] = True
            continue
        if new is not None and new != q.get("default"):
            q["_default0"] = q.get("default")
            q["default"] = new
            q["_remembered"] = True


def save_remembered(spec, answers):
    keep = {q["id"]: answers[q["id"]] for q in spec["questions"]
            if q["id"] in answers and q["type"] in CHOICE_TYPES and q.get("remember") is not False}
    path = remember_path(spec["remember"])
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            keep = dict(json.load(open(path, encoding="utf-8")), **keep)  # 今回聞かなかった質問の分は残す
        except (OSError, ValueError):
            pass
        json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    except OSError:
        pass


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


# ── 画面の前に人がいるか（最後にキーボード・マウスを触ってからの秒数） ────
_IDLE_PS = r'''
Add-Type @"
using System;using System.Runtime.InteropServices;
public static class AskIdle{[StructLayout(LayoutKind.Sequential)]struct LII{public uint cb;public uint t;}
[DllImport("user32.dll")]static extern bool GetLastInputInfo(ref LII p);
public static uint Sec(){LII i=new LII();i.cb=8;GetLastInputInfo(ref i);return ((uint)Environment.TickCount-i.t)/1000;}}
"@
[AskIdle]::Sec()
'''


def idle_seconds():
    """このマシンで最後に操作があってからの秒数。分からなければ None（そのときは判定しない）。
    スマホなど別の端末から指示しているとき、誰も見ていない画面にウィンドウを出して待ち続けないために使う。"""
    try:
        if sys.platform == "win32":
            import ctypes

            class LII(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_uint), ("t", ctypes.c_uint)]
            info = LII(8, 0)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
            return ((ctypes.windll.kernel32.GetTickCount() - info.t) & 0xFFFFFFFF) / 1000.0
        if is_wsl():
            ps = shutil.which("powershell.exe") or "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
            enc = base64.b64encode(_IDLE_PS.encode("utf-16-le")).decode("ascii")
            out = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                                 capture_output=True, timeout=10, stdin=subprocess.DEVNULL).stdout
            return float(out.decode("ascii", "ignore").strip().splitlines()[-1])
        if sys.platform == "darwin":
            out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, timeout=5).stdout.decode()
            return int(re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out).group(1)) / 1e9
        if shutil.which("xprintidle"):
            return int(subprocess.run(["xprintidle"], capture_output=True, timeout=5).stdout) / 1000.0
    except Exception:
        pass
    return None


# ── ウィンドウとやり取りする小さなサーバー ────────────────────────────────
class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.result = None          # {"status": ..., ...} が入ったら終わり
        self.conns = 0              # つながっているウィンドウの数
        self.connected_at = None    # 最初につながった時刻
        self.last_drop = 0.0
        self.seen = False           # ウィンドウの中で人の操作（マウス・キー）があった

    def finish(self, result):
        with self.lock:
            if self.result is None:
                self.result = result


def make_handler(state, token, page, files=()):
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
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._ok():
                return self._send(404)
            rel = self.path.split("?")[0][len(token) + 2:]
            m = re.match(r"^file/(\d+)$", rel)
            if m and int(m.group(1)) < len(files):  # 定義に書かれた画像・音だけを、番号で配る
                path, ctype = files[int(m.group(1))]
                try:
                    return self._send(200, open(path, "rb").read(), ctype)
                except OSError:
                    return self._send(404)
            if rel == "":
                return self._send(200, page, "text/html; charset=utf-8")
            if rel == "ping":
                return self._send(200, b"ok")
            if rel == "events":
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
                state.connected_at = state.connected_at or time.time()
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
            elif name == "seen":
                self._send(204)
                state.seen = True
            else:
                self._send(404)

    return Handler


# ── Sodashitsu の pane の中なら、その pane を見ているブラウザの画面に出す ─────
SODA_TYPES = ("single", "multi", "text")   # sodactl ask が対応する型


def ask_via_soda(spec, timeout, raw=None):
    """sodactl ask で聞く。結果（answered / cancelled / timeout）を返す。出せない・使わないときは None
    （呼び出し側はウィンドウへ進む）。"""
    if os.environ.get("ASK_FORM_SODA", "").lower() in ("off", "0", "no"):
        return None
    sodactl = shutil.which("sodactl")
    if not sodactl or not os.environ.get("SODA_PANE_ID"):
        return None
    for q in spec["questions"]:
        if q["type"] not in SODA_TYPES:
            return None
        # プレビューは sodactl ask では出ない。見比べて選ぶ質問なので、ウィンドウで聞く
        if any(k in o for o in q.get("options", []) for k in ("image", "audio", "code")):
            return None
    try:
        p = subprocess.run([sodactl, "ask", "--timeout", str(max(1, timeout) * 1000)],
                           input=json.dumps(raw if raw is not None else spec, ensure_ascii=False), capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout + 30)
        result = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else None
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None
    if not isinstance(result, dict) or result.get("status") not in ("answered", "cancelled", "timeout"):
        return None   # unavailable（つながっているブラウザが無い等）・古い sodactl・サーバのエラー
    return result


def done(result):
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(EXIT[result["status"]])


def env_int(name, default):
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def main():
    ap = argparse.ArgumentParser(description="質問をまとめて単発ウィンドウに出し、回答を JSON で受け取る")
    ap.add_argument("spec", nargs="?", help="質問の定義（JSON ファイル。- で標準入力）")
    ap.add_argument("--timeout", type=int, default=540, help="回答を待つ秒数（既定 540）")
    ap.add_argument("--width", type=int, default=None,
                    help="ウィンドウの幅（既定 780。横にプレビューを出す質問・表があれば 1080）")
    ap.add_argument("--height", type=int, default=820, help="ウィンドウの高さの上限（中身に合わせて縮む）")
    ap.add_argument("--away-after", type=int, default=env_int("ASK_FORM_AWAY_SECONDS", 300), metavar="秒",
                    help="このマシンの操作がこの秒数以上無ければ、画面の前に人がいないとみて unavailable を返す（既定 300。0 で判定しない）")
    ap.add_argument("--react-within", type=int, default=env_int("ASK_FORM_REACT_SECONDS", 90), metavar="秒",
                    help="開いたウィンドウにこの秒数のあいだ操作が無ければ、閉じて unavailable を返す（既定 90。0 で判定しない）")
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
        # image・audio の相対パスは、定義のファイルの場所（標準入力なら今の場所）から解く
        base_dir = "." if args.spec in (None, "-") else os.path.dirname(os.path.abspath(args.spec))
        raw_spec = json.loads(json.dumps(spec))   # sodactl ask へは、書かれたままの定義を渡す
        spec = normalize(spec, base_dir)
    except (OSError, ValueError) as e:
        print("ask-form: 質問の定義を読めません: %s" % e, file=sys.stderr)
        sys.exit(EXIT["error"])
    if args.check:
        print("OK: 質問 %d 件" % len(spec["questions"]))
        return

    files = spec.pop("_files")
    if spec.get("remember") and not args.selftest:
        apply_remembered(spec)
    if not args.selftest:
        result = ask_via_soda(spec, args.timeout, raw_spec)
        if result:
            if result["status"] == "answered" and spec.get("remember"):
                save_remembered(spec, result.get("answers") or {})
            done(result)

    browser, why = find_browser()
    if not browser:
        done({"status": "unavailable", "reason": why})
    if args.selftest:  # 自動回答なので、人がいるかは見ない
        args.away_after = args.react_within = 0
    if args.away_after > 0:
        idle = idle_seconds()
        if idle is not None and idle >= args.away_after:
            done({"status": "unavailable",
                  "reason": "このマシンの操作が %d 秒ありません（画面の前に人がいないとみて、ウィンドウを出しませんでした）" % idle})

    if args.width is None:
        wide = any(q["type"] == "table" or q.get("preview") == "side"
                   or (q.get("preview") is None and any("code" in o for o in q.get("options", [])))
                   for q in spec["questions"])
        args.width = 1080 if wide else 780
    spec["_auto"] = bool(args.selftest)
    spec["_width"] = args.width
    spec["_maxHeight"] = args.height
    template = open(os.path.join(HERE, "form.html"), encoding="utf-8").read()
    component = open(os.path.join(HERE, "ask-form.js"), encoding="utf-8").read()   # 画面の部品（<ask-form>）。殻に埋め込んで配る
    page = (template.replace("__COMPONENT__", component.replace("</script", "<\\/script"))
            .replace("__SPEC__", json.dumps(spec, ensure_ascii=False).replace("</", "<\\/")))

    state = State()
    token = secrets.token_urlsafe(12)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state, token, page.encode("utf-8"), files))
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
            opened = state.connected_at
            closed = opened and state.conns == 0 and now - state.last_drop > CLOSE_GRACE
            never = not opened and now - start > OPEN_WAIT
            unseen = opened and not state.seen and args.react_within > 0 and now - opened > args.react_within
        if closed:
            state.finish({"status": "cancelled"})
        elif never:
            state.finish({"status": "unavailable", "reason": "ウィンドウがつながりません（%d 秒待ちました）" % OPEN_WAIT})
        elif unseen:  # 受け口が終わると、ウィンドウは自分で閉じる
            state.finish({"status": "unavailable",
                          "reason": "開いたウィンドウに %d 秒のあいだ操作がありません（画面の前に人がいないとみて閉じました）" % args.react_within})
        elif now - start > args.timeout:
            state.finish({"status": "timeout"})
    time.sleep(0.3)  # 最後の応答をウィンドウへ返し切る
    if state.result["status"] == "answered" and spec.get("remember") and not args.selftest:
        save_remembered(spec, state.result.get("answers") or {})
    done(state.result)


if __name__ == "__main__":
    main()
