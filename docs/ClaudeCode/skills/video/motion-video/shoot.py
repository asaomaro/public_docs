#!/usr/bin/env python3
"""作った HTML を画面なしの Chrome で開き、その時刻の映像を PNG に撮る（check.py --shots・yukkuri-kaisetsu の kaisetsu.py --shots・yukkuri-qa の見本）。

  python3 shoot.py 動画.html 6.5,0:42 -o 出力フォルダ

撮り方: Chrome を 1 回だけ起動し（DevTools Protocol のパイプ）、HTML を 1 回だけ読み、時刻ごとに「動かす → 絵と書体が読み終わるのを待つ → 描き終わるのを待つ → 撮る」。
前は 1 枚ごとに Chrome を起動して、決めた時間（--virtual-time-budget）が過ぎたら撮っていたので、大きい HTML（100MB）や混んだ機械では、
ページを描く前に撮って真っ白になった（2026-10-03: 48 枚中 4〜6 枚）。撮った PNG は中身（色）を見て、一色なら撮り直す。標準ライブラリだけで動く。
"""
import base64, json, os, shutil, struct, subprocess, sys, tempfile, time, zlib

CHROMES = ("google-chrome", "chromium", "chromium-browser", "chrome")
STAGE_CSS = ".mv-stage{position:fixed!important;inset:0!important;z-index:99999!important;max-width:none!important;width:100vw!important;height:100vh!important}"
SMALL = 20000     # 1280×720 の PNG がこれより小さければ、中身を見るまでもなく、ほぼ一色
DECODE = 300000   # これより大きい PNG は一色ではありえない（一色の画面は数 KB に縮む）ので、中身を開かない（開くのは 1 枚 1〜2 秒かかる）


def find_chrome():
    return next((c for c in CHROMES if shutil.which(c)), None)


def png_pixels(data, step=4, rows=None):
    """PNG（8 ビットの RGB・RGBA・グレー、インターレースなし）を開いて、step おきの画素の色を返す。読めない形なら None。PIL に頼らない。
    rows を渡すと、上からその行数だけを開く（大きい画像を全部開くと遅い）。"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, head = 8, [], None
    while pos + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
        pos += 12 + n
    if not head or head[2] != 8 or head[3] not in (0, 2, 4, 6) or head[6]:
        return None
    w, h, bpp = head[0], head[1], {0: 1, 2: 3, 4: 2, 6: 4}[head[3]]
    if rows:
        h = min(h, rows)
    try:
        raw = zlib.decompressobj().decompress(b"".join(idat), (w * bpp + 1) * h)
    except zlib.error:
        return None
    line, prev, out = w * bpp, bytearray(w * bpp), []
    if len(raw) < (line + 1) * h:
        return None
    for y in range(h):
        f, cur = raw[y * (line + 1)], bytearray(raw[y * (line + 1) + 1:(y + 1) * (line + 1)])
        if f == 1:
            for i in range(bpp, line):
                cur[i] = (cur[i] + cur[i - bpp]) & 255
        elif f == 2:
            cur = bytearray((a + b) & 255 for a, b in zip(cur, prev))
        elif f == 3:
            for i in range(line):
                cur[i] = (cur[i] + ((cur[i - bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(line):
                a, b, c = (cur[i - bpp] if i >= bpp else 0), prev[i], (prev[i - bpp] if i >= bpp else 0)
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif f != 0:
            return None
        if y % step == 0:
            out += [bytes(cur[x * bpp:(x + 1) * bpp]) for x in range(0, w, step)]
        prev = cur
    return out


def is_blank(png):
    """撮った PNG が、描く前の画面（真っ白など、ほぼ一色）か。大きさではなく中身（色）で見分ける。"""
    if isinstance(png, str):
        if not os.path.isfile(png):
            return True
        if os.path.getsize(png) > DECODE:
            return False
        png = open(png, "rb").read()
    elif len(png) > DECODE:
        return False
    px = png_pixels(png)
    if px is None:   # 開けない形の PNG は、前と同じく大きさで見る
        return len(png) < SMALL
    if not px:
        return True
    count = {}
    for p in px:
        count[p] = count.get(p, 0) + 1
    return max(count.values()) >= len(px) * 0.995


class Browser:
    """画面なしの Chrome を DevTools Protocol（パイプ）で動かす。本当の時間で待つ（仮想時間は使わない）。"""

    def __init__(self, chrome, size, extra=()):   # extra: Chrome に足す引数（録画は、操作なしで音を鳴らす引数が要る）
        r3, self.w3 = os.pipe()
        self.r4, w4 = os.pipe()
        self.dir = tempfile.mkdtemp(prefix="mv-shoot-")

        def fds():   # Chrome は fd 3 から読み、fd 4 へ書く
            for src, dst in ((r3, 3), (w4, 4)):
                if src != dst:
                    os.dup2(src, dst)
                os.set_inheritable(dst, True)
        self.p = subprocess.Popen([chrome, "--headless=new", "--no-sandbox", "--hide-scrollbars", "--remote-debugging-pipe", "--user-data-dir=" + self.dir,
                                   "--window-size=%d,%d" % size] + list(extra) + ["about:blank"], preexec_fn=fds, close_fds=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(r3)
        os.close(w4)
        self.buf, self.n = b"", 0
        tid = next(t["targetId"] for t in self.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.call("Target.attachToTarget", targetId=tid, flatten=True)["sessionId"]
        self.call("Emulation.setDeviceMetricsOverride", self.sid, width=size[0], height=size[1], deviceScaleFactor=1, mobile=False)

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
                    raise RuntimeError("Chrome が終わりました")
                self.buf += chunk
            raw, self.buf = self.buf.split(b"\0", 1)
            m = json.loads(raw)
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]

    def eval(self, js):
        r = self.call("Runtime.evaluate", self.sid, expression=js, awaitPromise=True, returnByValue=True, timeout=180000)
        if r.get("exceptionDetails"):
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"])
        return r["result"].get("value")

    def open(self, html):
        """HTML を読み、プレイヤー（__MV__）ができて、絵と書体が読み終わるまで待つ。映像は画面いっぱいに広げる。"""
        self.call("Page.enable", self.sid)
        self.call("Page.addScriptToEvaluateOnNewDocument", self.sid, source=
                  'document.addEventListener("DOMContentLoaded",function(){var s=document.createElement("style");s.textContent=%s;document.head.appendChild(s)})' % json.dumps(STAGE_CSS))
        self.call("Page.navigate", self.sid, url="file://" + os.path.abspath(html))
        ok = self.eval("new Promise(function(ok){var n=0;(function w(){window.__MV__?ok(true):n++>3000?ok(false):setTimeout(w,100)})()})")   # 大きい HTML は読むのに時間がかかる（5 分まで待つ）
        if not ok:
            raise RuntimeError("プレイヤー（__MV__）が見つかりません")
        self.eval("(document.fonts&&document.fonts.ready?document.fonts.ready:Promise.resolve()).then(function(){window.dispatchEvent(new Event('resize'));return 1})")
        # 前の engine.js で作った HTML は、読み終わりを聞けない（__MV__.loading が無い）。その分だけ待つ
        self.eval("new Promise(function(ok){setTimeout(ok,__MV__.loading===undefined?3000:300)})")

    def shot(self, ms):
        """その時刻へ動かし、絵が読み終わり、2 回描かれるのを待ってから撮る。PNG のバイト列。
        コマを待つ上限は 5 秒（前は 400ms で、遅い機械では描かれる前に撮ることがあった）。"""
        self.eval("""new Promise(function(ok){
  try{__MV__.seek(%d)}catch(e){}
  var n=0,frame=function(f){var done=false,g=function(){if(!done){done=true;f()}};requestAnimationFrame(g);setTimeout(g,5000)};
  (function w(){if(__MV__.loading&&n++<150){setTimeout(w,100);return}
    try{__MV__.seek(%d)}catch(e){}
    frame(function(){frame(function(){setTimeout(ok,60)})})})()})""" % (ms, ms))
        return base64.b64decode(self.call("Page.captureScreenshot", self.sid, format="png")["data"])

    def close(self):
        try:
            try:
                self.call("Browser.close")   # Chrome に自分で終わらせる（子のプロセスも終わる）。kill だけだと子が残って、プロファイルのフォルダを書き戻すことがあった
                self.p.wait(timeout=5)
            except Exception:
                pass
            self.p.kill()
            self.p.wait()
        finally:
            for _ in range(3):   # 子のプロセスが書いている間は消し切れないことがある
                shutil.rmtree(self.dir, ignore_errors=True)
                if not os.path.exists(self.dir):
                    break
                time.sleep(.3)


def take(browser, ms, tries=3, wait=0.6):
    """1 枚撮る。一色（描く前の白い画面）なら、少し待って撮り直す。(PNG, 一色のままか)"""
    png = b""
    for i in range(tries):
        png = browser.shot(ms)
        if not is_blank(png):
            return png, False
        time.sleep(wait * (i + 1))
    return png, True


def shoot_cli(chrome, html, shots, size):
    """パイプで動かせない環境（Windows など）の撮り方: 1 枚ごとに Chrome を起動する。一色なら、待つ時間を延ばして撮り直す。"""
    src, blank = open(html, encoding="utf-8").read(), []
    for ms, png in shots:
        hook = ('<style>%s</style><script>window.addEventListener("load",function(){[700,2600].forEach(function(w){setTimeout(function(){try{__MV__.seek(%d)}catch(e){}},w)})})</script>' % (STAGE_CSS, ms))
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8", dir=os.path.dirname(os.path.abspath(html))) as f:
            f.write(src + hook)
        try:
            for budget in (6000, 12000, 24000, 48000):
                subprocess.run([chrome, "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=%d,%d" % size, "--virtual-time-budget=%d" % budget,
                                "--screenshot=" + png, "file://" + f.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
                if not is_blank(png):
                    break
            else:
                blank.append(png)
        finally:
            os.remove(f.name)
    return blank


def shoot(html, shots, size=None, browser=None):
    """shots: [(ミリ秒, PNG のパス)]。撮れた PNG のパスの一覧を返す。一色のまま残った画面は warn で知らせる（黙って白い画面を渡さない）。"""
    chrome = find_chrome()
    if not chrome and browser is None:
        print("warn: Chrome が見つからないので、画面を撮れません（HTML をブラウザで開いて見る）", file=sys.stderr)
        return []
    if size is None:
        head = open(html, encoding="utf-8", errors="ignore").read()
        size = (720, 1280) if '"format": "short"' in head or '"format":"short"' in head else (1280, 720)   # 縦の画面（ショート）は縦に撮る
    done, blank, b = [], [], browser
    try:
        if b is None:
            b = Browser(chrome, size)
        b.open(html)
    except Exception as e:
        if browser is not None:
            raise
        if b is not None:
            b.close()
        print("warn: Chrome をパイプで動かせないので、1 枚ずつ起動して撮ります（%s）" % e, file=sys.stderr)
        blank = shoot_cli(chrome, html, shots, size)
        done = [p for _, p in shots if os.path.isfile(p)]
        b = None
    if b is not None:
        try:
            for ms, png in shots:
                try:
                    data, bad = take(b, ms)
                except Exception as e:
                    print("warn: %.1f 秒の画面を撮れませんでした（%s）" % (ms / 1000.0, e), file=sys.stderr)
                    continue
                os.makedirs(os.path.dirname(os.path.abspath(png)), exist_ok=True)
                open(png, "wb").write(data)
                done.append(png)
                if bad:
                    blank.append(png)
        finally:
            if browser is None:
                b.close()
    for png in blank:
        print("warn: %s は、撮り直しても一色の画面でした（暗転の途中でなければ、撮れていません。時刻を少しずらして撮り直す）" % png, file=sys.stderr)
    return done


def seconds(t):
    """「6.5」「0:42」「1:02:03」→ 秒。"""
    return sum(float(x) * 60 ** i for i, x in enumerate(reversed(str(t).strip().split(":"))))


def main():
    import argparse
    ap = argparse.ArgumentParser(description="作った HTML の、その時刻の画面を PNG に撮る")
    ap.add_argument("html")
    ap.add_argument("times", help="時刻（秒。6.5,12 のように並べる。0:42 の形でもよい）")
    ap.add_argument("-o", "--out", default=None, help="出力フォルダ（既定は <HTML 名>_shots）")
    a = ap.parse_args()
    out = a.out or os.path.splitext(a.html)[0] + "_shots"
    for p in shoot(a.html, [(round(seconds(t) * 1000), os.path.join(out, "%07.2f.png" % seconds(t))) for t in a.times.split(",") if t.strip()]):
        print("撮った絵: %s" % p)


if __name__ == "__main__":
    main()
