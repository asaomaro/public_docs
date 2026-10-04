#!/usr/bin/env python3
"""動画の HTML（motion-video・yukkuri-kaisetsu）を、画面なしの Chrome で、字幕・音入りの WebM に書き出す。

既定は「1 コマずつの書き出し」: プレイヤーに時刻を渡して 1 コマずつ描かせ、ブラウザの符号化器（WebCodecs）で映像と音にし、webm.py で 1 つにまとめる。
実際の速さで再生しないので、機械が遅くてもコマが抜けない（前は再生しながら録っていて、1920×1080 で毎秒 21〜49 コマになり、動きがかくついた）。
--realtime は前の方式（プレイヤーの ⚙「動画ファイル（WebM）で保存」を人の代わりに押し、最初から 1 倍速で再生しながら録る。MP4 はこちらだけ）。

  python3 record.py 動画.html                            # 動画.webm（1920×1080・8Mbps・30 コマ。ショートは 1080×1920）
  python3 record.py 動画.html --size 720                 # 1280×720 で
  python3 record.py 動画.html --size 1440 --bitrate 20 --fps 60 --format mp4

かかる時間は、動画の長さと同じくらい（機械と解像度による）。
録り終わったら、長さ・大きさ・音のトラックを確かめ、まん中の 1 コマを <出力名>.check.png に撮る（Read で開いて見る）。
"""
import argparse
import glob
import json
import os
import re
import shutil
import struct
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
        # 録る前に、せりふごとの画面を 1 回ずつ描いておく（絵を先に開かせる。録っている間に初めて開くと、そこでコマが止まる）
        b.eval(PREWARM)
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


CODECS = {"webm": ("V_VP9", "vp09.00.51.08"), "vp8": ("V_VP8", "vp8"), "av1": ("V_AV1", "av01.0.12M.08")}
PREWARM = """new Promise(function(ok){var ts=(__MV__.CUES||[]).map(function(c){return c.a}).filter(function(x){return x>=0}),i=0;
  (function w(){var t0=performance.now();while(i<ts.length&&performance.now()-t0<30){try{__MV__.drawAt(ts[i]+50)}catch(e){}i++}
    if(i<ts.length)setTimeout(w,0);else{try{__MV__.seek(0)}catch(e){}ok(ts.length)}})()})"""
# ページの中で動かす部分: プレイヤーに 1 コマずつ描かせ、ブラウザの符号化器（WebCodecs）で映像と音のかたまりにする。かたまりは base64 で Python へ返す
OFFLINE_JS = """window.__off=(function(){
  var Q=[],ERR=null,enc=null,info=null;
  function b64(u8){var s='',i,n=u8.length;for(i=0;i<n;i+=0x8000)s+=String.fromCharCode.apply(null,u8.subarray(i,i+0x8000));return btoa(s)}
  return {
    start:async function(codec,mode){
      if(!(window.VideoEncoder&&window.VideoFrame&&__MV__.offline))return {error:window.VideoEncoder?'old-html':'no-webcodecs'};
      info=__MV__.offline.begin();
      var c={codec:codec,width:info.w,height:info.h,bitrate:info.bps,framerate:info.fps,latencyMode:mode};
      var sup=await VideoEncoder.isConfigSupported(c);
      if(!sup.supported){__MV__.offline.end();return {error:'unsupported '+codec}}
      enc=new VideoEncoder({output:function(ch){var b=new Uint8Array(ch.byteLength);ch.copyTo(b);Q.push([ch.type==='key'?1:0,Math.round(ch.timestamp/1000),b64(b)])},error:function(e){ERR=String(e)}});
      enc.configure(c);
      return {w:info.w,h:info.h,fps:info.fps,dur:info.dur,bps:info.bps,abps:info.abps}},
    frames:async function(i0,n,gop){
      for(var i=i0;i<i0+n;i++){var ms=i*1000/info.fps,cv=__MV__.offline.frame(ms);
        var f=new VideoFrame(cv,{timestamp:Math.round(ms*1000),duration:Math.round(1e6/info.fps)});enc.encode(f,{keyFrame:i%gop===0});f.close();
        while(enc.encodeQueueSize>3)await new Promise(function(r){setTimeout(r,1)})}
      if(ERR)throw new Error(ERR);var out=Q;Q=[];return out},
    finish:async function(){await enc.flush();enc.close();var out=Q;Q=[];__MV__.offline.end();if(ERR)throw new Error(ERR);return out},
    abort:function(){try{enc&&enc.close()}catch(e){}try{__MV__.offline.end()}catch(e){}},
    audio:async function(){
      if(!window.AudioEncoder)return {error:'no-audio-encoder'};
      var buf=await __MV__.offline.mix();if(!buf)return {chunks:[]};
      var sr=buf.sampleRate,nch=buf.numberOfChannels,total=Math.min(buf.length,Math.ceil(info.dur/1000*sr)),out=[],head=null,err=null;
      var ae=new AudioEncoder({output:function(ch,meta){var b=new Uint8Array(ch.byteLength);ch.copyTo(b);out.push([ch.timestamp/1000,b64(b)]);
        if(meta&&meta.decoderConfig&&meta.decoderConfig.description&&!head)head=b64(new Uint8Array(meta.decoderConfig.description))},error:function(e){err=String(e)}});
      ae.configure({codec:'opus',sampleRate:sr,numberOfChannels:nch,bitrate:info.abps});
      var peak=0,step=sr;
      for(var p=0;p<total;p+=step){var n=Math.min(step,total-p),data=new Float32Array(n*nch);
        for(var c=0;c<nch;c++){var src=buf.getChannelData(c).subarray(p,p+n);data.set(src,c*n);if(c===0)for(var k=0;k<n;k+=97){var v=Math.abs(src[k]);if(v>peak)peak=v}}
        var ad=new AudioData({format:'f32-planar',sampleRate:sr,numberOfFrames:n,numberOfChannels:nch,timestamp:Math.round(p/sr*1e6),data:data});ae.encode(ad);ad.close();
        while(ae.encodeQueueSize>8)await new Promise(function(r){setTimeout(r,1)})}
      await ae.flush();ae.close();if(err)throw new Error(err);
      return {rate:sr,channels:nch,head:head,chunks:out,peak:peak}}
  }})();1"""


def auto_jobs(size="1080"):
    """同時に動かす Chrome の数の既定: CPU 4 スレッドにつき 1 つ、空きメモリ 2GB（4K は 3GB）につき 1 つ、多くて 6。
    4K を 4 つ同時に動かしたとき、メモリの使用が 5GB 増えて、空きが 1GB まで減った。"""
    n = max(1, (os.cpu_count() or 4) // 4)
    try:
        avail = int(re.search(r"MemAvailable:\s+(\d+)", open("/proc/meminfo").read()).group(1)) // ((3 if str(size) == "2160" else 2) * 1024 * 1024)
        n = min(n, max(1, avail))
    except (OSError, AttributeError):
        pass
    return min(n, 6)


def _setup(b, html, opt, kind, fast, span=None):
    """HTML を開き、録画の設定を渡し、絵を先に開かせて、符号化器を用意する。返すのは {w, h, fps, dur, …} か {error}。span = (ms, ms) は、絵を開かせる範囲。"""
    b.open(html)
    if not b.eval("!!document.getElementById('mv-rec') && !document.getElementById('mv-rec').hidden"):
        raise RuntimeError("この HTML には「WebM で保存」がありません（配布用の --dist で作った HTML は録れません。--dist を付けずに作り直します）")
    b.eval("var r=document.getElementById('mv-rec');%s1" % "".join("r.setAttribute('data-%s',%s);" % (k, json.dumps(str(v))) for k, v in opt.items() if v is not None))
    b.eval(PREWARM if not span else PREWARM.replace("filter(function(x){return x>=0})", "filter(function(x){return x>=%d&&x<=%d})" % (span[0] - 5000, span[1] + 1000)))
    b.eval(OFFLINE_JS)
    return b.eval("__off.start(%s,%s)" % (json.dumps(CODECS[kind][1]), json.dumps("realtime" if fast else "quality")))


def _part(b, i0, i1, gop, batch, path, tick):
    """i0〜i1 のコマを描いて符号化し、かたまりを path に書く（キーフレームか・時刻・長さ・中身 の並び）。"""
    import base64
    with open(path, "wb") as f:
        def put(rows):
            for key, ms, data in rows:
                raw = base64.b64decode(data)
                f.write(struct.pack(">BQI", key, ms, len(raw)) + raw)
        i = i0
        while i < i1:
            n = min(batch, i1 - i)
            put(b.eval("__off.frames(%d,%d,%d)" % (i, n, gop)))
            i += n
            tick(n)
        put(b.eval("__off.finish()"))


def record_offline(b, html, out, opt=None, log=say, fast=True, batch=30, jobs=1, browser=None):
    """1 コマずつ描いて符号化し、out（WebM）に書く。実際の速さで再生しないので、機械が遅くてもコマが抜けない。
    jobs > 1 は、動画を区間に分け、Chrome を jobs 個動かして同時に書き出し、最後に順につなぐ（browser() が Chrome をもう 1 つ開く）。
    区間の頭はキーフレーム（2 秒ごと）にそろえるので、つないでも絵は変わらない。
    返すのは {dur, frames, want, size, audio, fps（1 秒に書き出せたコマ数）, jobs}。使えないとき（前の engine.js の HTML・符号化器が無い）は None。"""
    import base64
    import threading
    import webm
    opt = dict(opt or {})
    kind = opt.get("fmt") or "webm"
    if kind not in CODECS:
        return None
    info = _setup(b, html, opt, kind, fast)
    if info.get("error"):
        log("note: 1 コマずつの書き出しは使えません（%s）。実際の速さで再生して録ります" % {"old-html": "前の engine.js で作った HTML", "no-webcodecs": "この Chrome に符号化器が無い"}.get(info["error"], info["error"]))
        return None
    dur, fps = info["dur"] / 1000.0, info["fps"]
    total, gop = int(-(-info["dur"] * fps // 1000)), fps * 2
    jobs = max(1, min(jobs if browser else 1, total // (gop * 4)))   # 区間 1 つは 8 秒以上
    per = -(-total // jobs // gop) * gop
    spans = [(i0, min(total, i0 + per)) for i0 in range(0, total, per)]
    log("書き出します（%d:%02d・%d×%d・%d コマ/秒・%d コマ%s）" % (dur // 60, dur % 60, info["w"], info["h"], fps, total, "・%d つに分けて同時に" % len(spans) if len(spans) > 1 else ""))
    tmp = tempfile.mkdtemp(prefix="mv-parts-", dir=os.path.dirname(os.path.abspath(out)))
    parts = [os.path.join(tmp, "%03d.bin" % k) for k in range(len(spans))]
    W, others, errors, done, lock, last = None, [], [], [0], threading.Lock(), [-1]

    def tick(n):
        with lock:
            done[0] += n
            pct = done[0] * 10 // total * 10
            if pct > last[0]:
                last[0] = pct
                log("  %3d%%" % pct)

    def work(k):
        try:
            bk = b
            if k:
                bk = browser()
                with lock:
                    others.append(bk)
                got = _setup(bk, html, opt, kind, fast, (spans[k][0] * 1000.0 / fps, spans[k][1] * 1000.0 / fps))
                if got.get("error"):
                    raise RuntimeError("区間 %d の Chrome で符号化器を用意できません（%s）" % (k, got["error"]))
            _part(bk, spans[k][0], spans[k][1], gop, batch, parts[k], tick)
        except BaseException as e:
            errors.append(e)

    try:
        t0 = time.time()
        threads = [threading.Thread(target=work, args=(k,), daemon=True) for k in range(1, len(spans))]
        for t in threads:
            t.start()
        au = b.eval("__off.audio()")   # 音は 1 回だけ（最初の Chrome で）
        if au.get("error"):
            raise RuntimeError("音を符号化できません（%s）" % au["error"])
        work(0)
        for t in threads:
            t.join()
        if errors:
            raise errors[0]
        head = base64.b64decode(au["head"]) if au.get("head") else None
        audio = {"rate": au["rate"], "channels": au["channels"], "head": head, "preskip": (head[10] | head[11] << 8) if head and len(head) > 11 else 312} if au.get("chunks") else None
        W = webm.Writer(out, info["w"], info["h"], fps, CODECS[kind][0], audio)
        for ms, data in au.get("chunks") or []:
            W.add_audio(ms, base64.b64decode(data))
        for path in parts:   # 区間の順につなぐ
            with open(path, "rb") as f:
                while True:
                    h = f.read(13)
                    if len(h) < 13:
                        break
                    key, ms, n = struct.unpack(">BQI", h)
                    W.add_video(ms, f.read(n), bool(key))
        res = W.close(info["dur"])
    except BaseException:
        if W:
            W.abort()
        try:
            b.eval("__off.abort();1")
        except Exception:
            pass
        raise
    finally:
        for b2 in others:
            try:
                b2.close()
            except Exception:
                pass
        shutil.rmtree(tmp, ignore_errors=True)
    return {"dur": dur, "frames": res["frames"], "want": total, "size": (info["w"], info["h"]), "audio": bool(audio), "peak": au.get("peak", 0),
            "fps": total / max(.001, time.time() - t0), "file": os.path.basename(out), "jobs": len(spans)}


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
    ap.add_argument("--realtime", action="store_true", help="前の方式（実際の速さで再生しながら録る。機械が遅いとコマが抜ける）")
    ap.add_argument("--jobs", type=int, default=0, help="同時に動かす Chrome の数（既定は自動: CPU と空きメモリから。1 で分けない）")
    ap.add_argument("--quality", action="store_true", help="1 コマずつの書き出しで、符号化をていねいにする（遅い。同じビットレートで少しきれい）")
    ap.add_argument("--at", type=float, default=.5, help="確かめの 1 コマを撮る所（0〜1。既定 0.5）")
    a = ap.parse_args(argv)
    import signal
    signal.signal(signal.SIGTERM, lambda *x: sys.exit(143))   # 止められたときも、開いた Chrome と一時ファイルを片づける（前は timeout で止めると Chrome が残った）
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
            opt = {"size": size, "bps": a.bitrate or 0, "fps": a.fps, "abps": a.audio_bitrate, "fmt": a.format}
            info = None
            if not a.realtime and a.format == "mp4":
                say("note: MP4 は、1 コマずつの書き出しではまだ作れません。実際の速さで再生して録ります")
            elif not a.realtime:
                info = record_offline(b, a.html, out, opt, fast=not a.quality, jobs=a.jobs or auto_jobs(size), browser=lambda: shoot.Browser(chrome, (1280, 720), FLAGS))
            offline = info is not None
            if info is None:
                info = record(b, a.html, out, opt)
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
    if offline and info["frames"] != info["want"]:
        bad += 1
        print("warn: コマの数が合いません（%d コマのはずが %d コマ）" % (info["want"], info["frames"]))
    elif offline:
        print("     全 %d コマを書き出しました（1 秒に %.0f コマの速さ%s）" % (info["frames"], info["fps"], "・Chrome %d つ" % info["jobs"] if info["jobs"] > 1 else ""))
    if not any(t.startswith("A_") for t in tr) or not info.get("audio"):
        bad += 1
        print("warn: 音のトラックが入っていません")
    if offline:
        pass
    elif info.get("fps") and info["fps"] < 24:
        print("warn: 録っている間のコマ数が少ない（毎秒 %.0f コマ）。動きがかくつくことがあります。--realtime を外して、1 コマずつの書き出しを使います" % info["fps"])
    elif info.get("fps"):
        print("     録っている間のコマ数: 毎秒 %.0f コマ" % info["fps"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
