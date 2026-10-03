#!/usr/bin/env python3
"""動画の HTML（motion-video・yukkuri-kaisetsu）を、画面なしの Chrome で再生して、字幕・音入りの WebM に録る。

  python3 record.py 動画.html                            # 動画.webm（1920×1080・8Mbps・30 コマ。ショートは 1080×1920）
  python3 record.py 動画.html --size 720                 # 1280×720 で
  python3 record.py 動画.html --size 1440 --bitrate 20 --fps 60 --format mp4

プレイヤーの ⚙「動画ファイル（WebM）で保存」を、人の代わりに押す。最初から 1 倍速で再生しながら録るので、**動画の長さだけ時間がかかる**。
録り終わったら、長さ・大きさ・音のトラックを確かめ、まん中の 1 コマを <出力名>.check.png に撮る（Read で開いて見る）。
"""
import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
import time


def find_motion_video():
    here = os.path.dirname(os.path.abspath(__file__))
    for d in [os.path.join(os.path.dirname(here), "motion-video")] + sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(here)), "*", "motion-video"))):
        if os.path.isfile(os.path.join(d, "shoot.py")):
            return d
    return None


MV = find_motion_video()
if MV and MV not in sys.path:
    sys.path.insert(0, MV)

FLAGS = ["--autoplay-policy=no-user-gesture-required", "--allow-file-access-from-files",
         "--disable-component-update", "--disable-background-networking"]   # 録っている間に、Chrome が自分の部品を取りに行かないように
PROBE = """<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#000;height:100%%;overflow:hidden}video{width:100vw;height:100vh;object-fit:contain}</style>
<video id="v" src="%s" preload="auto"></video>"""


def fail(msg):
    print("error: " + msg, file=sys.stderr)
    return 1


def tracks(path):
    """WebM の先頭にある、映像と音のコーデックの名前。"""
    with open(path, "rb") as f:
        head = f.read(1 << 16)
        if path.lower().endswith(".mp4"):   # MP4 は、コーデックの名前が終わりの方（moov）にあることがある
            f.seek(max(0, os.path.getsize(path) - (1 << 20)))
            head += f.read()
            return [n for c, n in ((b"avc1", "V_H264"), (b"avc3", "V_H264"), (b"vp09", "V_VP9"), (b"mp4a", "A_AAC"), (b"Opus", "A_OPUS")) if c in head]
    return [c for c in ("V_VP9", "V_VP8", "V_AV1", "A_OPUS", "A_VORBIS") if c.encode() in head]


def say(msg):
    print(msg, flush=True)   # 進み具合を、ファイルやパイプへもすぐ出す


def record(b, html, out, opt=None, log=say):
    """録って out に置く。opt は {size, bps, fps, abps, fmt}（保存のボタンに付けて、プレイヤーの設定に勝たせる。None は付けない）。
    返すのは {dur（秒）, fps, size（録った大きさ）, audio（音が動いていたか）, file（録れたファイルの名前）}。"""
    tmp = tempfile.mkdtemp(prefix="mv-rec-")
    try:
        b.call("Browser.setDownloadBehavior", behavior="allow", downloadPath=tmp)
        b.open(html)
        dur = b.eval("__MV__.DUR") / 1000.0
        if not b.eval("!!document.getElementById('mv-rec') && !document.getElementById('mv-rec').hidden"):
            raise RuntimeError("この HTML には「WebM で保存」がありません（配布用の --dist で作った HTML は録れません。--dist を付けずに作り直します）")
        log("録り始めます（%d:%02d。同じだけ時間がかかります）" % (dur // 60, dur % 60))
        b.eval("window.__f=0;(function c(){window.__f++;requestAnimationFrame(c)})();var r=document.getElementById('mv-rec');%sr.click();1" % "".join("r.setAttribute('data-%s',%s);" % (k, json.dumps(str(v))) for k, v in (opt or {}).items() if v is not None))
        t0, last, f0, info = time.time(), -1, None, {"dur": dur, "audio": False}
        while True:
            time.sleep(1)
            # 動画のファイルだけを見る（Chrome が自分の部品を同じ場所へ落とすことがあり、それを録画と取り違えた: CI で 33MB の CRX を拾った）
            done = [f for f in glob.glob(os.path.join(tmp, "*")) if os.path.splitext(f)[1].lower() in (".webm", ".mp4")]
            if done:
                break
            st = b.eval("({t:__MV__.t,f:window.__f,w:document.querySelector('.mv-player canvas').width,h:document.querySelector('.mv-player canvas').height,"
                        "a:!!(__MV__.audio.ctx&&__MV__.audio.ctx.state==='running')})")
            info["size"], info["audio"] = (st["w"], st["h"]), info["audio"] or st["a"]
            if f0 is None and st["t"] > 500:
                f0 = (time.time(), st["f"])
            elif f0 and st["t"] < dur * 1000 - 500:
                info["fps"] = (st["f"] - f0[1]) / max(.001, time.time() - f0[0])
            pct = int(st["t"] / 10.0 / dur) // 10 * 10
            if pct > last:
                last = pct
                log("  %3d%%" % min(pct, 100))
            if time.time() - t0 > dur * 1.5 + 120:
                raise RuntimeError("録画が終わりません（%d 秒待ちました）" % (time.time() - t0))
        info["file"] = os.path.basename(done[0])
        shutil.move(done[0], out)
        return info
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def probe(b, out, png, at):
    """録ったファイルを開いて、長さ・大きさ・音の大きさを測り、at（0〜1）の所の 1 コマを撮る。"""
    d = tempfile.mkdtemp(prefix="mv-probe-")
    try:
        page = os.path.join(d, "probe.html")
        open(page, "w", encoding="utf-8").write(PROBE % ("file://" + urllib_quote(os.path.abspath(out))))
        b.call("Page.navigate", b.sid, url="file://" + page)
        # 前のページ（プレイヤー）が残っている間は聞かない。ファイルを読み終わるのは、遅い機械では時間がかかる（60 秒まで待つ。前は 20 秒で、CI で開けないことがあった）
        b.eval("new Promise(function(ok){var n=0;(function w(){document.getElementById('v')&&location.href.indexOf('probe.html')>0||n++>300?ok(1):setTimeout(w,100)})()})")
        r = b.eval("""new Promise(function(ok){var n=0;(function w(){var v=document.getElementById('v');
  if(v&&v.readyState>=1){var fin=function(){ok({w:v.videoWidth,h:v.videoHeight,dur:v.duration})};
    if(isFinite(v.duration))fin();else{v.addEventListener('durationchange',function(){if(isFinite(v.duration))fin()});v.currentTime=1e9;setTimeout(fin,15000)}}
  else if((v&&v.error)||n++>600)ok({error:v&&v.error?v.error.code+' '+v.error.message:'timeout rs='+(v?v.readyState+' ns='+v.networkState:'no video')});else setTimeout(w,100)})()})""")
        if not r or r.get("error"):
            print("warn: 録ったファイルを開けません（%s・%d バイト）" % ((r or {}).get("error", "応答なし"), os.path.getsize(out)), file=sys.stderr)
            return None
        r["rms"] = b.eval("""new Promise(function(ok){var v=document.getElementById('v'),t0=%f*v.duration;
  try{var ac=new AudioContext(),src=ac.createMediaElementSource(v),an=ac.createAnalyser();an.fftSize=2048;src.connect(an);var g=ac.createGain();g.gain.value=0;an.connect(g);g.connect(ac.destination);
    var buf=new Float32Array(an.fftSize),best=0,end=0;
    v.addEventListener('seeked',function(){v.play();var iv=setInterval(function(){an.getFloatTimeDomainData(buf);var s=0;for(var i=0;i<buf.length;i++)s+=buf[i]*buf[i];best=Math.max(best,Math.sqrt(s/buf.length));
      if(++end>40){clearInterval(iv);v.pause();v.currentTime=t0;setTimeout(function(){ok(best)},600)}},100)},{once:true});
    v.currentTime=t0}catch(e){ok(-1)}})""" % at)
        import base64
        open(png, "wb").write(base64.b64decode(b.call("Page.captureScreenshot", b.sid, format="png")["data"]))
        return r
    finally:
        shutil.rmtree(d, ignore_errors=True)


def urllib_quote(p):
    import urllib.parse
    return urllib.parse.quote(p)


def main(argv=None):
    ap = argparse.ArgumentParser(description="動画の HTML を、字幕・音入りの WebM に録る")
    ap.add_argument("html")
    ap.add_argument("-o", "--out", help="出力（既定は <HTML 名>.webm）")
    ap.add_argument("--size", choices=["720", "1080", "1440", "2160"], default="1080", help="解像度（縦の画素数。既定 1080 = 1920×1080。ショートは縦横が入れ替わる）")
    ap.add_argument("--sd", action="store_true", help="--size 720 と同じ")
    ap.add_argument("--bitrate", type=float, help="映像のビットレート（Mbps。既定は自動: 720 は 5、1080 は 8、1440 は 16、2160 は 35。60 コマは 1.5 倍）")
    ap.add_argument("--fps", choices=["30", "60"], default="30", help="1 秒あたりのコマ数（既定 30）")
    ap.add_argument("--audio-bitrate", type=int, default=192, help="音のビットレート（kbps。既定 192）")
    ap.add_argument("--format", choices=["webm", "vp8", "av1", "mp4"], default="webm", help="webm（VP9。既定）・vp8・av1・mp4（H.264。Chrome が録れるときだけ）")
    ap.add_argument("--at", type=float, default=.5, help="確かめの 1 コマを撮る所（0〜1。既定 0.5）")
    a = ap.parse_args(argv)
    if not MV:
        return fail("motion-video スキル（shoot.py）が見つかりません。このスキルと同じ場所に置きます")
    import shoot
    if not os.path.isfile(a.html):
        return fail("HTML がありません: %s" % a.html)
    if os.path.splitext(a.html)[1].lower() not in (".html", ".htm"):
        return fail("HTML ではありません: %s（録るのは motion-video・yukkuri-kaisetsu で作った動画の HTML）" % a.html)
    chrome = shoot.find_chrome()
    if not chrome:
        return fail("Chrome が見つかりません（画面なしの Chrome で録ります）。無ければ、HTML を開いて ⚙「動画ファイル（WebM）で保存」を使います")
    size = "720" if a.sd else a.size
    out = a.out or os.path.splitext(a.html)[0] + (".mp4" if a.format == "mp4" else ".webm")
    text = open(a.html, encoding="utf-8", errors="replace").read()
    if "data:audio/" not in text:
        print("warn: この HTML には声が入っていません（ブラウザの読み上げの声は録れません）。--voicevox で作り直してから録ります")
    del text
    b = shoot.Browser(chrome, (1280, 720), FLAGS)
    try:
        try:
            info = record(b, a.html, out, {"size": size, "bps": a.bitrate or 0, "fps": a.fps, "abps": a.audio_bitrate, "fmt": a.format})
        except RuntimeError as e:
            return fail(str(e))
        got = probe(b, out, os.path.splitext(out)[0] + ".check.png", a.at)
    finally:
        b.close()
    tr = tracks(out)
    print("OK : %s（%.1fMB・%s）" % (out, os.path.getsize(out) / 1048576, "・".join(tr) or "コーデック不明"))
    bad = 0
    if got:
        print("     %d×%d・%d:%02d（台本は %d:%02d）・音の大きさ %s・確かめの 1 コマ: %s" % (got["w"], got["h"], got["dur"] // 60, got["dur"] % 60, info["dur"] // 60, info["dur"] % 60,
              "%.3f" % got["rms"] if got.get("rms", -1) >= 0 else "測れず", os.path.splitext(out)[0] + ".check.png"))
        if abs(got["dur"] - info["dur"]) > 3:
            bad += 1
            print("warn: 録った長さが、台本の長さと %.1f 秒違います" % (got["dur"] - info["dur"]))
        if min(got["w"], got["h"]) != int(size):
            print("warn: 頼んだ解像度（%s）で録れていません（前の engine.js で作った HTML は 1280×720 で録れます）。HTML を作り直します" % size)
        if os.path.splitext(info["file"])[1].lower() != os.path.splitext(out)[1].lower():
            bad += 1
            print("warn: 頼んだ形式で録れていません（録れたのは %s）。この Chrome では、その形式を録れません" % os.path.splitext(info["file"])[1])
        if 0 <= got.get("rms", -1) < .002:
            bad += 1
            print("warn: 測った所（%d%%）の音が、ほぼ無音です。別の所でも確かめます（--at）" % (a.at * 100))
    else:
        bad += 1
        print("warn: 録ったファイルを開けませんでした")
    if not any(t.startswith("A_") for t in tr) or not info.get("audio"):
        bad += 1
        print("warn: 音のトラックが入っていません")
    if info.get("fps") and info["fps"] < 24:
        print("warn: 録っている間のコマ数が少ない（毎秒 %.0f コマ）。動きがかくつくことがあります。ほかの重い作業を止めて録り直すか、--size 720 で録ります" % info["fps"])
    elif info.get("fps"):
        print("     録っている間のコマ数: 毎秒 %.0f コマ" % info["fps"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
