"""ask-form のテストの道具: 画面なしの Chrome を動かす口と、終わると消える一時フォルダ。
Chrome の口は、動画のスキルのテスト（video/tests/test_engine.py）と同じもの（ask-form を単独で確かめられるよう、ここにも置く）。"""
import atexit
import json
import os
import shutil
import subprocess
import tempfile

CHROME = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
_TMP = []


def tmpdir():
    d = tempfile.mkdtemp(prefix="askformtest-")
    _TMP.append(d)
    return d


@atexit.register
def _cleanup():
    for d in _TMP:
        shutil.rmtree(d, ignore_errors=True)


class Chrome:
    """画面なしの Chrome を DevTools Protocol（パイプ）で動かす。仮想時間（--virtual-time-budget）を使わず、本当の時間で Promise を待つ
    （仮想時間の下では、長い音の書き出し〔OfflineAudioContext〕が終わる前に打ち切られるため）。"""

    def __init__(self):
        r3, self.w3 = os.pipe()      # Chrome が読む（fd 3）
        self.r4, w4 = os.pipe()      # Chrome が書く（fd 4）
        self.dir = tmpdir()

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
