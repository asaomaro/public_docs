#!/usr/bin/env python3
"""BGM の曲ごとの大きさを測って、bgm_levels.json（曲の名前 → 実効値）を書く。

集めた曲は、配布元も作り方もばらばらで、同じ音量で流すと 10 dB 近く差が出る（静かなピアノと、音を詰めたチップチューン）。
kaisetsu.py はこの表を読み、どの曲も同じ大きさに聞こえるよう、曲ごとに音量へ倍率を掛ける（台本の music_level: off で止める）。

測り方: 0.4 秒ごとの実効値を取り、無音（-50 dB より下）と、平均より 10 dB 以上小さい所（曲の頭と終わりのフェード・間）を除いて平均する
（放送の音量の測り方＝ラウドネスの、周波数の重みを省いた形）。Chrome で音を復号するので、ffmpeg は要らない。

    python3 bgm_levels.py            # bgm/ にある曲を測って bgm_levels.json を書く（測ってある曲は飛ばす。--all で全部）
    python3 bgm_levels.py --show     # 今の表と、そろえた後の倍率を出す
"""
import argparse
import base64
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
OUT = os.path.join(HERE, "bgm_levels.json")
LIMIT = (0.35, 2.5)     # 倍率の幅（-9 dB 〜 +8 dB）

MEASURE = """(async function(){
  var bin = Uint8Array.from(atob(window.B64), function(c){ return c.charCodeAt(0); });
  var oc = new OfflineAudioContext(1, 44100, 44100), buf = await oc.decodeAudioData(bin.buffer);
  var n = buf.length, sr = buf.sampleRate, nc = buf.numberOfChannels, win = Math.round(sr * .4), ch = [], blocks = [], pk = 0;
  for (var c = 0; c < nc; c++) ch.push(buf.getChannelData(c));
  for (var i = 0; i + win <= n; i += win) { var e = 0;
    for (var c2 = 0; c2 < nc; c2++) { var d = ch[c2]; for (var j = i; j < i + win; j++) { var v = d[j]; e += v * v; if (v > pk) pk = v; else if (-v > pk) pk = -v; } }
    blocks.push(e / (win * nc)); }
  var a = blocks.filter(function(b){ return b > 1e-5; }), m = a.reduce(function(s, b){ return s + b; }, 0) / Math.max(1, a.length);
  var g = a.filter(function(b){ return b > m * .1; }), mg = g.reduce(function(s, b){ return s + b; }, 0) / Math.max(1, g.length);
  return { rms: Math.sqrt(mg), peak: pk, sec: n / sr };
})()"""


def load():
    try:
        return json.load(open(OUT, encoding="utf-8"))["rms"]
    except (OSError, ValueError, KeyError):
        return {}


def gains(levels=None):
    """曲の名前 → 音量に掛ける倍率。まん中（中央値）の大きさにそろえる。"""
    levels = load() if levels is None else levels
    vals = [v for v in levels.values() if v > 0]
    if not vals:
        return {}
    target = statistics.median(vals)
    return {k: round(min(LIMIT[1], max(LIMIT[0], target / v)), 3) for k, v in levels.items() if v > 0}


def measure(names, bgms):
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tests"))
    import test_engine
    out = {}
    c = test_engine.Chrome()
    try:
        for k in names:
            path = os.path.join(HERE, "bgm", bgms[k]["file"])
            b64 = base64.b64encode(open(path, "rb").read()).decode()
            c.open("<!doctype html><meta charset=utf-8><script>window.B64=%s;window.__MV__={};</script>" % json.dumps(b64))
            r = c.eval(MEASURE)
            out[k] = round(r["rms"], 5)
            print("%-22s %6.1f dB（山 %.2f・%d 秒）" % (k, 20 * math.log10(max(r["rms"], 1e-6)), r["peak"], r["sec"]), flush=True)
    finally:
        c.close()
    return out


def main():
    ap = argparse.ArgumentParser(description="BGM の曲ごとの大きさを測る")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--all", action="store_true", help="測ってある曲も測り直す")
    a = ap.parse_args()
    bgms = {k: v for k, v in json.load(open(os.path.join(HERE, "bgm.json"), encoding="utf-8")).items() if not k.startswith("_")}
    rms = load()
    if not a.show:
        todo = [k for k, v in bgms.items() if os.path.isfile(os.path.join(HERE, "bgm", v.get("file", ""))) and (a.all or k not in rms)]
        if todo:
            rms.update(measure(todo, bgms))
            json.dump({"note": "bgm_levels.py が書く。曲の名前 → 実効値（無音と小さい所を除いた平均）", "rms": rms},
                      open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
        print("OK : %s（%d 曲。今回測ったのは %d 曲）" % (OUT, len(rms), len(todo)))
    g = gains(rms)
    for k in sorted(rms, key=lambda k: -rms[k]):
        print("%-22s %6.1f dB  ×%.2f" % (k, 20 * math.log10(max(rms[k], 1e-6)), g.get(k, 1)))


if __name__ == "__main__":
    main()
