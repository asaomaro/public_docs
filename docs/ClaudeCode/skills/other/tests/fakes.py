"""回帰テストの道具: 偽の VOICEVOX・WAV を作る・モジュールの読み込み。

素材（立ち絵・BGM・書体）・VOICEVOX・ネットにつながらない環境（CI）でも回るように、声は偽の VOICEVOX で作る。
偽の VOICEVOX は、文の字（句読点を除く）1 つを 1 拍（0.1 秒）、読点などを 1 つの間（0.2 秒）として読み、
その長さどおりの WAV（拍は音・間は無音）を書く。拍と間の長さが分かっているので、字幕の切り替えの時刻をぴったり確かめられる。
"""
import atexit
import contextlib
import hashlib
import importlib
import io
import json
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import wave
from unittest import mock

OTHER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MV = os.path.join(OTHER, "motion-video")
YK = os.path.join(OTHER, "yukkuri-kaisetsu")
for d in (MV, YK, os.path.join(OTHER, "yukkuri-qa"), os.path.join(OTHER, "fact-check")):
    if d not in sys.path:
        sys.path.insert(0, d)

import samples  # noqa: E402
samples.pack = lambda gm, warn=None: None   # 楽器の録音の音は取りに行かない（ネット・手元の保存分に頼らない。合成の音で鳴らす）

SR = 24000
MORA, PAUSE, EDGE = 0.1, 0.2, 0.1
PUNCT = re.compile(r"[、。，．！？!?…,.]+")


def write_wav(path, segments, sr=SR):
    """segments: [(秒, 音を出すか)]。音は 220Hz の正弦波、それ以外は無音。"""
    frames = bytearray()
    for sec, loud in segments:
        for i in range(int(sec * sr)):
            frames += struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / sr)) if loud else 0)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))


def tokens(text):
    """偽の読み: [(拍の数, 後ろに間があるか)]（句読点・空白で区切った塊ごと）。空白も VOICEVOX と同じく間にする。"""
    parts = list(re.finditer(r"([^、。，．！？!?…,.\s]+)([、。，．！？!?…,.\s]*)", text))
    return [(len(m.group(1)), bool(m.group(2)) and i < len(parts) - 1) for i, m in enumerate(parts)]   # 文の終わりの句点は間にしない


def fake_query(text, speed=1.0):
    aps = []
    for n, pause in tokens(text):
        ap = {"moras": [{"consonant_length": None, "vowel_length": MORA} for _ in range(n)]}
        if pause:
            ap["pause_mora"] = {"vowel_length": PAUSE}
        aps.append(ap)
    return {"accent_phrases": aps, "prePhonemeLength": EDGE, "postPhonemeLength": EDGE, "speedScale": speed,
            "kana": "/".join("ア" * n for n, _ in tokens(text))}


class FakeVoicevox:
    """motion-video の voice.Voicevox と同じ口（ids・synth・query・moras・credits）。作った文を texts に残す。"""
    instances = []

    def __init__(self, url="http://fake"):
        self.url, self.made, self.used, self.texts = url, 0, set(), []
        self.ids = {(n, s): i for i, (n, s) in enumerate([("四国めたん", "ノーマル"), ("ずんだもん", "ノーマル"), ("東北きりたん", "ノーマル"),
                                                            ("四国めたん", "あまあま"), ("ずんだもん", "なみだめ")])}
        FakeVoicevox.instances.append(self)

    def speaker_id(self, speaker, style):
        return self.ids.get((speaker, style or "ノーマル"), 0)

    def _path(self, text, v, outdir):
        key = hashlib.sha1(json.dumps([v.get("speaker"), v.get("style"), v.get("speed"), text], ensure_ascii=False).encode()).hexdigest()[:16]
        os.makedirs(outdir, exist_ok=True)
        return os.path.join(outdir, key + ".wav")

    def synth(self, text, v, outdir):
        p = self._path(text, v, outdir)
        sp = float(v.get("speed", 1.0))
        if not os.path.isfile(p):
            segs = [(EDGE / sp, False)]
            for n, pause in tokens(text):
                segs.append((n * MORA / sp, True))
                if pause:
                    segs.append((PAUSE / sp, False))
            segs.append((EDGE / sp, False))
            write_wav(p, segs)
            self.made += 1
        self.texts.append(text)
        self.used.add(v.get("speaker") or "四国めたん")
        return p

    def query(self, text, v, outdir):
        return self.synth(text, v, outdir), fake_query(text, float(v.get("speed", 1.0)))

    def moras(self, text, v, outdir):
        return sum(n for n, _ in tokens(text))

    def credits(self):
        return ["VOICEVOX:%s" % n for n in sorted(self.used)]


@contextlib.contextmanager
def fake_voicevox(alive=True):
    """voice.Voicevox を偽物に替え、VOICEVOX が動いている（alive）か止まっているかを決める。"""
    import voice
    import build
    FakeVoicevox.instances = []

    def urlopen(url, *a, **k):
        if not alive:
            raise OSError("VOICEVOX は止まっている（テスト）")
        return io.BytesIO(b'"0.0.0-test"')

    with mock.patch.object(voice, "Voicevox", FakeVoicevox), mock.patch.object(build, "voicevox_alive", lambda *a, **k: alive), \
            mock.patch("urllib.request.urlopen", urlopen):
        yield FakeVoicevox.instances


@contextlib.contextmanager
def quiet():
    """標準エラー・標準出力を捨てて、中身を返す。"""
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        yield err, out


_TMP = []


def tmpdir():
    d = tempfile.mkdtemp(prefix="skilltest-")
    _TMP.append(d)
    return d


@atexit.register
def _cleanup():
    for d in _TMP:
        shutil.rmtree(d, ignore_errors=True)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return path


def fresh(name):
    """モジュールを読み直す（ほかのテストの差し替えを持ち越さない）。"""
    if name in sys.modules:
        return importlib.reload(sys.modules[name])
    return importlib.import_module(name)


def wav_ms(path):
    with wave.open(path) as w:
        return w.getnframes() * 1000.0 / w.getframerate()


def voices_in_html(path):
    return len(re.findall(r"data:audio/(?:x-)?wav", open(path, encoding="utf-8", errors="ignore").read()))


def voices_in_html_text(text):
    return len(re.findall(r"data:audio/(?:x-)?wav", text))
