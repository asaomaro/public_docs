"""実際の楽器を録音した音（サンプル）で曲を鳴らすための音源。

曲の作り方（旋律・和音・リズム）は audio.js のまま、楽器の音色だけを録音の音に差し替える。
音源は FluidR3_GM（Frank Wen 作。CC BY 3.0。クレジットが要る）を MIDI.js 用に変換したもの
（gleitz/midi-js-soundfonts）。版を固定して取りに行き、手元に置いて使い回す。
埋め込むのは、曲が使う楽器の、使う音域の音だけ（4 半音おき。間の音は再生の速さで高さを合わせる）。
"""
import json
import os
import re
import sys
import urllib.request

REV = "044fab8e1456bfafc5776e86dfd6bb8697149aef"
URL = "https://raw.githubusercontent.com/gleitz/midi-js-soundfonts/%s/FluidR3_GM/%%s-mp3.js" % REV
CREDIT = "楽器の音: FluidR3_GM（Frank Wen、CC BY 3.0）"
CACHE = os.environ.get("MOTION_VIDEO_SAMPLES") or os.path.join(os.path.expanduser("~"), ".cache", "motion-video", "samples", REV[:12])
STEP = 4   # 何半音おきに入れるか

# audio.js の楽器 → (FluidR3_GM の楽器, 鳴り方 d=減衰する・s=伸ばす, 音量の合わせ)。音量は合成の音と同じ大きさ（中央の C の前後 3 音の中央値。最大 6）になるよう測った値
MAP = {
    "keys": ("acoustic_grand_piano", "d", 2.9), "epiano": ("electric_piano_1", "d", 1.48), "harpsi": ("harpsichord", "d", 0.27),
    "clav": ("clavinet", "d", 0.12), "organ": ("drawbar_organ", "s", 2.75), "accordion": ("accordion", "s", 1.13),
    "bandoneon": ("tango_accordion", "s", 0.97), "harmonica": ("harmonica", "s", 1.26),
    "strings": ("string_ensemble_1", "s", 1.49), "pizz": ("pizzicato_strings", "d", 0.75), "choir": ("choir_aahs", "s", 1.32),
    "oohs": ("voice_oohs", "s", 0.96), "harp": ("orchestral_harp", "d", 1.53), "marimba": ("marimba", "d", 1.72),
    "vibes": ("vibraphone", "d", 3.35), "glock": ("glockenspiel", "d", 1.64), "musicbox": ("music_box", "d", 1.67),
    "tubular": ("tubular_bells", "d", 1.83), "kalimba": ("kalimba", "d", 6.0), "koto": ("koto", "d", 1.48),
    "shaku": ("shakuhachi", "s", 2.28), "flute": ("flute", "s", 4.01), "whistle": ("whistle", "s", 1.05),
    "brass": ("brass_section", "s", 1.44), "steel": ("steel_drums", "d", 2.13), "sitar": ("sitar", "d", 0.65),
    "shamisen": ("shamisen", "d", 1.17), "uke": ("acoustic_guitar_nylon", "d", 1.17), "banjo": ("banjo", "d", 0.33),
    "bass": ("electric_bass_finger", "d", 4.36), "upright": ("acoustic_bass", "d", 2.35), "slap": ("slap_bass_1", "d", 1.99),
    "timpani": ("timpani", "d", 6.0), "taiko": ("taiko_drum", "d", 6.0), "block": ("woodblock", "d", 4.14),
}
PC = {"C": 0, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
_PACKS = {}


def _midi(name):
    m = re.match(r"^([A-G]b?)(-?\d)$", name)
    return 12 * (int(m.group(2)) + 1) + PC[m.group(1)] if m else None


def pack(gm, warn=None):
    """FluidR3_GM の 1 楽器（音の名前 → data URI）。手元に無ければ取りに行く。取れなければ None。"""
    if gm in _PACKS:
        return _PACKS[gm]
    path = os.path.join(CACHE, gm + ".js")
    if not os.path.isfile(path):
        try:
            os.makedirs(CACHE, exist_ok=True)
            with urllib.request.urlopen(URL % gm, timeout=60) as r:
                data = r.read()
            open(path + ".part", "wb").write(data)
            os.replace(path + ".part", path)
        except Exception as e:
            if warn is not None:
                warn.append("楽器の音 %s を取れませんでした（%s）。この楽器は合成の音で鳴らします" % (gm, e))
            _PACKS[gm] = None
            return None
    txt = open(path, encoding="utf-8").read()
    notes = {}
    for name, uri in re.findall(r'"([A-G]b?-?\d)"\s*:\s*"(data:audio/[^"]+)"', txt):
        m = _midi(name)
        if m is not None:
            notes[m] = uri
    _PACKS[gm] = notes or None
    return _PACKS[gm]


def pick(notes, lo, hi):
    """lo..hi の音域を STEP 半音おきに覆う音（それぞれ一番近い録音の音）。"""
    have = sorted(notes)
    out = {}
    for m in range(lo, hi + 1, STEP):
        near = min(have, key=lambda x: (abs(x - m), x))
        out[near] = notes[near]
    return out


def build(table, custom=(), warn=None):
    """曲の表（sound.prepare の _music）から、使う楽器と音域を拾って埋め込む音を作る。
    返り値: ({楽器: {k, g, n: {midi: uri}}}, 使ったか)"""
    ranges = {}
    for d in (table or {}).values():
        for L in (d or {}).get("layers") or []:
            inst = L.get("inst")
            if inst in MAP and inst not in custom:
                o = int(L.get("oct", 4))
                lo, hi = 12 * o, 12 * (o + 3)   # その層の高さの 1 オクターブ下から 2 オクターブ上まで
                a, b = ranges.get(inst, (lo, hi))
                ranges[inst] = (min(a, lo), max(b, hi))
    out = {}
    for inst, (lo, hi) in sorted(ranges.items()):
        gm, kind, g = MAP[inst]
        notes = pack(gm, warn)
        if notes:
            out[inst] = {"k": kind, "g": g, "n": {str(m): u for m, u in pick(notes, lo, hi).items()}}
    return out


if __name__ == "__main__":
    # 手元に全部の楽器の音を取ってくる（オフラインで作る前に）
    w = []
    for inst, (gm, _, _) in sorted(MAP.items()):
        print("%-10s %-24s %s" % (inst, gm, "ok" if pack(gm, w) else "失敗"))
    for x in w:
        print("warn:", x, file=sys.stderr)
