#!/usr/bin/env python3
"""効果音の大きさを測って、sfx_levels.json（名前 → いちばん大きい 0.3 秒の実効値）を書く。

効果音は波形の山（peak）はそろえてあるが、聞こえる大きさ（実効値）は音色で 10 dB ほど違う（きらきらした長い音は大きく、短い「ポン」は小さい）。
sound.py はこの表を読み、どの音も同じ大きさに聞こえるよう、音ごとの倍率（lv）を台本に書き込む（engine.js の sfxPlay が掛ける）。

効果音を足した・作り直したら回す（Chrome が要る。画面なしで、音だけを書き出して測る）:
    python3 sfx_levels.py            # 測って sfx_levels.json を書く
    python3 sfx_levels.py --show     # 今の表と、そろえた後の倍率を出す
"""
import argparse
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
OUT = os.path.join(HERE, "sfx_levels.json")
LIMIT = (0.45, 2.0)     # 倍率の幅（-7 dB 〜 +6 dB）
POWER = 0.75            # どこまで寄せるか（1 で完全に同じ実効値。短い「カチ」は実効値より大きく聞こえるので、寄せきらない）


def gains(levels):
    """名前 → 倍率。まん中（中央値）の大きさにそろえる。"""
    vals = [v for v in levels.values() if v > 0]
    if not vals:
        return {}
    target = statistics.median(vals)
    return {k: round(min(LIMIT[1], max(LIMIT[0], (target / v) ** POWER)), 3) for k, v in levels.items() if v > 0}


def load():
    try:
        return json.load(open(OUT, encoding="utf-8"))["rms"]
    except (OSError, ValueError, KeyError):
        return {}


def measure():
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tests"))
    sys.path.insert(0, HERE)
    import build
    import test_engine
    spec = {"title": "sfx", "lang": "ja", "audio": {"narration": False, "music": None, "sfx": {"kit": "standard"}},
            "chapters": [{"title": "a", "scenes": [{"type": "title", "title": "sfx"}]}]}
    d = test_engine.fakes.tmpdir()
    path = os.path.join(d, "s.json")
    json.dump(spec, open(path, "w", encoding="utf-8"))
    with test_engine.fakes.quiet():
        page = build.build_html(build.load(path), "midnight", "studio", True)
    c = test_engine.Chrome()
    try:
        c.open(page)
        names = c.eval("__MV__.sfxNames()")
        return {n: round(c.eval("__MV__.sfxLevel(%s)" % json.dumps(n))["rms"], 5) for n in names}
    finally:
        c.close()


def main():
    ap = argparse.ArgumentParser(description="効果音の大きさを測る")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if not a.show:
        rms = measure()
        json.dump({"note": "sfx_levels.py が書く。名前 → いちばん大きい 0.3 秒の実効値（倍率 1 で鳴らしたとき）", "rms": rms},
                  open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
        print("OK : %s（%d 個）" % (OUT, len(rms)))
    rms, g = load(), gains(load())
    db = lambda x: 20 * math.log10(max(x, 1e-6))
    for k in sorted(rms, key=lambda k: -rms[k]):
        print("%-18s %6.1f dB  ×%.2f" % (k, db(rms[k]), g.get(k, 1)))


if __name__ == "__main__":
    main()
