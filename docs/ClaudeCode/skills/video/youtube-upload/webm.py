"""WebM（Matroska）のファイルを書く。映像 1 本（VP9・VP8・AV1）と音 1 本（Opus）を、時刻の順に 1 つにまとめる。標準ライブラリだけ。

record.py の「1 コマずつの書き出し」が使う: ブラウザの符号化器（WebCodecs）が出したコマと音のかたまりを add_video・add_audio で受け、
close で 1 つのファイルにする。長さと、早送り用の索引（Cues）を書くので、プレイヤーで好きな所へ飛べる。

  w = Writer("out.webm", width=1920, height=1080, fps=30, codec="V_VP9", audio={"rate": 48000, "channels": 2, "preskip": 312})
  w.add_audio(ms, data); w.add_video(ms, data, key=True); …; w.close()

時刻は ms。かたまり（Cluster）は映像のキーフレームごとに区切る（1 つは 30 秒まで。中のコマの時刻は、かたまりの頭からの差を 16 ビットで書くため）。
"""
import os
import struct
import tempfile


def vint(n):
    """大きさを表す可変長の整数（EBML の data size）。"""
    for k in range(1, 9):
        if n < (1 << (7 * k)) - 1:
            return ((1 << (7 * k)) | n).to_bytes(k, "big")
    raise ValueError("大きすぎます: %d" % n)


def el(eid, data):
    return bytes.fromhex(eid) + vint(len(data)) + data


def uint(eid, n, size=None):
    size = size or max(1, (n.bit_length() + 7) // 8)
    return el(eid, n.to_bytes(size, "big"))


def text(eid, s):
    return el(eid, s.encode("utf-8"))


def opus_head(channels, rate, preskip):
    return b"OpusHead" + struct.pack("<BBHIhB", 1, channels, preskip, rate, 0, 0)


class Writer:
    def __init__(self, path, width, height, fps, codec="V_VP9", audio=None, app="youtube-upload record.py"):
        self.path, self.w, self.h, self.fps, self.codec, self.audio, self.app = path, width, height, fps, codec, audio, app
        self.tmp = tempfile.NamedTemporaryFile(prefix="webm-", suffix=".clusters", dir=os.path.dirname(os.path.abspath(path)), delete=False)
        self.clusters = []          # [(頭の時刻 ms, 一時ファイルの中の位置)]
        self.cur, self.cur_t0 = None, 0
        self.pending = []           # まだ書いていない音のかたまり [(ms, data)]。映像より先に全部届くので、映像の時刻に合わせて流す
        self.frames = self.samples = 0
        self.last = 0

    # ---- かたまり ----
    def _flush(self):
        if self.cur:
            body = uint("e7", self.cur_t0) + b"".join(self.cur)
            self.clusters.append((self.cur_t0, self.tmp.tell()))
            self.tmp.write(el("1f43b675", body))
        self.cur = None

    def _block(self, track, ms, data, key):
        if self.cur is None:
            self.cur, self.cur_t0 = [], ms
        rel = ms - self.cur_t0
        if not -32768 <= rel <= 32767:
            raise ValueError("かたまりが長すぎます（%d ms）。映像にキーフレームが 30 秒より長く無い" % rel)
        self.cur.append(el("a3", bytes([0x80 | track]) + struct.pack(">h", rel) + (b"\x80" if key else b"\x00") + data))
        self.last = max(self.last, ms)

    def add_audio(self, ms, data):
        self.pending.append((int(round(ms)), data))
        self.samples += 1

    def _drain(self, upto):
        """upto（ms）までの音を、今のかたまりに書く。"""
        n = 0
        while n < len(self.pending) and self.pending[n][0] <= upto:
            t, d = self.pending[n]
            self._block(2, max(t, self.cur_t0 if self.cur is not None else t), d, True)
            n += 1
        del self.pending[:n]

    def add_video(self, ms, data, key=False):
        ms = int(round(ms))
        if key and self.cur is not None:   # キーフレームの前までの音を前のかたまりに入れてから、新しいかたまりを始める
            self._drain(ms - 1)
            self._flush()
        if self.cur is None and not key and not self.frames:
            raise ValueError("最初のコマがキーフレームではありません")
        if self.cur is None:
            self.cur, self.cur_t0 = [], ms
        self._drain(ms)
        self._block(1, ms, data, key)
        self.frames += 1

    # ---- 仕上げ ----
    def close(self, duration_ms=None):
        if self.cur is None and self.pending:
            self.cur, self.cur_t0 = [], self.pending[0][0]
        self._drain(1 << 62)
        self._flush()
        self.tmp.close()
        dur = float(duration_ms if duration_ms is not None else self.last + 1000.0 / self.fps)
        info = el("1549a966", uint("2ad7b1", 1000000) + text("4d80", self.app) + text("5741", self.app) + el("4489", struct.pack(">d", dur)))
        video = el("ae", uint("d7", 1) + uint("73c5", 1) + uint("83", 1) + uint("9c", 0) + text("86", self.codec)
                   + uint("23e383", int(round(1e9 / self.fps))) + el("e0", uint("b0", self.w) + uint("ba", self.h)))
        tracks = video
        if self.audio:
            a = self.audio
            tracks += el("ae", uint("d7", 2) + uint("73c5", 2) + uint("83", 2) + uint("9c", 0) + text("86", "A_OPUS")
                         + uint("56aa", int(round(a.get("preskip", 312) * 1e9 / 48000))) + uint("56bb", 80000000)
                         + el("63a2", a.get("head") or opus_head(a["channels"], a["rate"], a.get("preskip", 312)))
                         + el("e1", el("b5", struct.pack(">d", float(a["rate"]))) + uint("9f", a["channels"])))
        tracks = el("1654ae6b", tracks)
        # 索引（Cues）と目次（SeekHead）は、位置を 8 バイトの決まった長さで書く（大きさが先に決まり、かたまりの位置を計算できる）
        cue = lambda t, pos: el("bb", uint("b3", t) + el("b7", uint("f7", 1) + uint("f1", pos, 8)))
        cues_len = len(el("1c53bb6b", b"".join(cue(t, 0) for t, _ in self.clusters)))
        seek = lambda eid, pos: el("4dbb", el("53ab", bytes.fromhex(eid)) + uint("53ac", pos, 8))
        seek_len = len(el("114d9b74", seek("1549a966", 0) + seek("1654ae6b", 0) + seek("1c53bb6b", 0)))
        p_info = seek_len
        p_tracks = p_info + len(info)
        p_cues = p_tracks + len(tracks)
        p_clusters = p_cues + cues_len
        seekhead = el("114d9b74", seek("1549a966", p_info) + seek("1654ae6b", p_tracks) + seek("1c53bb6b", p_cues))
        cues = el("1c53bb6b", b"".join(cue(t, p_clusters + pos) for t, pos in self.clusters))
        assert len(seekhead) == seek_len and len(cues) == cues_len
        size = p_clusters + os.path.getsize(self.tmp.name)
        head = el("1a45dfa3", uint("4286", 1) + uint("42f7", 1) + uint("42f2", 4) + uint("42f3", 8) + text("4282", "webm") + uint("4287", 4) + uint("4285", 2))
        with open(self.path, "wb") as out, open(self.tmp.name, "rb") as src:
            out.write(head + bytes.fromhex("18538067") + b"\x01" + size.to_bytes(7, "big") + seekhead + info + tracks + cues)
            while True:
                buf = src.read(1 << 22)
                if not buf:
                    break
                out.write(buf)
        os.remove(self.tmp.name)
        return {"frames": self.frames, "audio": self.samples, "ms": dur, "bytes": os.path.getsize(self.path)}

    def abort(self):
        try:
            self.tmp.close()
            os.remove(self.tmp.name)
        except OSError:
            pass
