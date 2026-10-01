"""声を前もって作る（VOICEVOX）・用意した WAV を当てる。motion-video の build.py と yukkuri-kaisetsu の kaisetsu.py が使う。

作った声は WAV で保存し、同じ話者・同じ文・同じ設定なら作り直さない（ファイル名は内容のハッシュ）。
"""
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:50021"
DEFAULT_SPEAKER = ("四国めたん", "ノーマル")


def _http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


class Voicevox:
    def __init__(self, url=DEFAULT_URL):
        self.url = url.rstrip("/")
        self.made = 0
        self.used = set()   # 使った話者の名前（クレジットに出す）
        try:
            speakers = json.loads(_http(self.url + "/speakers"))
        except Exception as e:
            sys.exit("error: VOICEVOX に接続できません（%s）: %s\n  VOICEVOX を起動してから、もう一度実行してください（--voicevox-url で場所を変えられる）" % (url, e))
        self.ids = {}
        for sp in speakers:
            for st in sp.get("styles", []):
                self.ids[(sp["name"], st["name"])] = st["id"]

    def speaker_id(self, speaker, style):
        sid = self.ids.get((speaker, style or "ノーマル"))
        if sid is None:
            sys.exit("error: VOICEVOX に話者「%s（%s）」がありません。候補: %s"
                     % (speaker, style or "ノーマル", "、".join(sorted({n for n, _ in self.ids}))[:400]))
        return sid

    def synth(self, text, v, outdir):
        """text を v（{speaker, style, speed, vv_pitch, intonation, volume}）の声で WAV にし、パスを返す。"""
        speaker = v.get("speaker") or DEFAULT_SPEAKER[0]
        style = v.get("style") or (DEFAULT_SPEAKER[1] if not v.get("speaker") else "ノーマル")
        sid = self.speaker_id(speaker, style)
        params = {"speedScale": v.get("speed", 1.0), "pitchScale": v.get("vv_pitch", 0.0),
                  "intonationScale": v.get("intonation", 1.0), "volumeScale": v.get("volume", 1.0)}
        key = hashlib.sha1(json.dumps([sid, text, params], ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "%s.wav" % key)
        if not os.path.isfile(path):
            q = json.loads(_http(self.url + "/audio_query?" + urllib.parse.urlencode({"text": text, "speaker": sid}), data=b""))
            q.update(params)
            wav = _http(self.url + "/synthesis?" + urllib.parse.urlencode({"speaker": sid}), data=json.dumps(q).encode("utf-8"),
                        headers={"Content-Type": "application/json"})
            open(path, "wb").write(wav)
            self.made += 1
        self.used.add(speaker)
        return path

    def credits(self):
        return ["VOICEVOX:%s" % n for n in sorted(self.used)]
