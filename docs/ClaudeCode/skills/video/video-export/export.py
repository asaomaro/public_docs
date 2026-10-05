"""video-export — motion-video・yukkuri-kaisetsu の動画を、YouTube への投稿と編集ソフト向けに書き出す。

  python3 export.py 台本.json --to youtube,ymm4,exo --voicevox      # motion-video の台本
  python3 export.py 台本.txt  --to all --voicevox --win-dir "C:\\..."  # yukkuri-kaisetsu の台本

台本は隣の motion-video の build.py（.txt は yukkuri-kaisetsu の kaisetsu.py）で読み、時間割を決める（台本どおり。
前もって作った声があれば声の長さ）。同じ時間割の HTML も書き出す場所に作るので、その ⚙ の
「編集用の映像（字幕・音なし WebM）」「音のトラックを書き出す（WAV）」で書き出した映像・音と、ここで作る
字幕・プロジェクトの時刻がそろう。

- youtube: 字幕（SRT・WebVTT。訳した字幕も）・チャプターの一覧（概要欄に貼る形）
- ymm4:    ゆっくりMovieMaker4 の台本（CSV。「キャラクター名,セリフ」）と、映像・音・声・字幕を並べたプロジェクト（.ymmp）
- exo:     AviUtl（拡張編集）のオブジェクトファイル（.exo）。映像・音・声・字幕を層に並べる
"""
import argparse
import csv
import importlib.util
import io
import json
import ntpath
import os
import re
import shutil
import sys
import uuid
import wave

KINDS = ("youtube", "ymm4", "exo")
W, H, HZ = 1920, 1080, 48000
HERE = os.path.dirname(os.path.abspath(__file__))


def plain(text):
    return re.sub(r"\*\*", "", str(text)).strip()


def wav_ms(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() * 1000.0 / w.getframerate()


# ──────────────────────────────────────────────────────────────────────────
# 時間割（字幕・声・章）
# ──────────────────────────────────────────────────────────────────────────
def timeline(spec):
    """章と字幕の一覧。字幕は {a, b（ms）, text, who, name, color, vpath, vms}。"""
    cast = spec.get("cast") or {}
    au = spec.get("audio") or {}
    narrator = (au.get("voice") or {}).get("speaker") or "ナレーション"
    chapters, cues, t = [], [], 0
    for ci, ch in enumerate(spec["chapters"]):
        chapters.append({"t": t, "title": ch.get("title", "")})
        for s in ch["scenes"]:
            for c in s.get("_cues") or []:
                who = c[3] if len(c) > 3 else ""
                vpath = None
                if who:
                    ln = (s.get("lines") or [])[c[4]] if len(c) > 4 else {}
                    vpath = ln.get("_vpath")
                    sp = cast.get(who) or {}
                    name, color = sp.get("name", who), sp.get("color")
                else:
                    vp = s.get("_vpaths") or []
                    vpath = vp[c[4]] if len(c) > 4 and c[4] < len(vp) else None
                    name, color = narrator, None
                if au.get("narration") is False:
                    vpath = None
                cues.append({"a": t + c[0], "b": t + c[1], "text": plain(c[2]), "who": who, "name": name, "color": color,
                             "vpath": vpath, "vms": wav_ms(vpath) if vpath and os.path.isfile(vpath) else 0, "ci": ci})
            t += s["_dur"]
    return {"total": t, "chapters": chapters, "cues": cues}


def has_music(spec):
    au = spec.get("audio") or {}
    table = au.get("_music") or {}
    for ch in spec["chapters"]:
        k = ch["_music"] if "_music" in ch else au.get("_musicKey")
        if k and k in table:
            return True
    return False


def has_sfx(spec):
    return bool((spec.get("audio") or {}).get("_sfxcfg"))


# ──────────────────────────────────────────────────────────────────────────
# YouTube: 字幕・チャプター
# ──────────────────────────────────────────────────────────────────────────
def ts(ms, sep=","):
    ms = int(round(ms))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d%s%03d" % (h, m, s, sep, ms)


def clock(ms):
    s = int(ms // 1000)
    return "%d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else "%d:%02d" % (s // 60, s % 60)


def srt(cues, texts):
    out = []
    for i, (c, tx) in enumerate(zip(cues, texts)):
        out.append("%d\n%s --> %s\n%s\n" % (i + 1, ts(c["a"]), ts(c["b"]), tx))
    return "\n".join(out)


def vtt(cues, texts):
    out = ["WEBVTT\n"]
    for c, tx in zip(cues, texts):
        out.append("%s --> %s\n%s\n" % (ts(c["a"], "."), ts(c["b"], "."), tx))
    return "\n".join(out)


def caption_text(c, dialogue):
    """字幕の文。掛け合いの動画では話し手の名前を前に付ける（だれの言葉か分かるように）。"""
    return "%s：%s" % (c["name"], c["text"]) if dialogue and c["who"] else c["text"]


def export_youtube(spec, tl, outdir, base, lang, warns):
    cues = tl["cues"]
    dialogue = any(c["who"] for c in cues)
    files = []
    src = [caption_text(c, dialogue) for c in cues]
    for ext, fn in (("srt", srt), ("vtt", vtt)):
        p = os.path.join(outdir, "%s.%s.%s" % (base, lang, ext))
        open(p, "w", encoding="utf-8").write(fn(cues, src))
        files.append(p)
    # 訳す元（1 行に字幕 1 つ）。subs.<言語>.txt に同じ行数で訳を書けば、次の --export でその言語の字幕ができる
    open(os.path.join(outdir, "subs.%s.txt" % lang), "w", encoding="utf-8").write("\n".join(c["text"] for c in cues) + "\n")
    for fn_ in sorted(os.listdir(outdir)):
        m = re.match(r"^subs\.([A-Za-z-]+)\.txt$", fn_)
        if not m or m.group(1) == lang:
            continue
        tl_ = m.group(1)
        lines = open(os.path.join(outdir, fn_), encoding="utf-8").read().rstrip("\n").split("\n")
        if len(lines) != len(cues):
            warns.append("%s は %d 行です（字幕は %d 個。1 行に字幕 1 つ）。この言語の字幕は作りませんでした" % (fn_, len(lines), len(cues)))
            continue
        tx = [ln.strip() for ln in lines]
        for ext, fn in (("srt", srt), ("vtt", vtt)):
            p = os.path.join(outdir, "%s.%s.%s" % (base, tl_, ext))
            open(p, "w", encoding="utf-8").write(fn(cues, tx))
            files.append(p)
    # チャプター（概要欄に貼る）。YouTube の条件: 最初が 0:00・3 つ以上・どれも 10 秒以上
    chs = tl["chapters"]
    lens = [(chs[i + 1]["t"] if i + 1 < len(chs) else tl["total"]) - c["t"] for i, c in enumerate(chs)]
    if len(chs) < 3:
        warns.append("チャプターが %d 個です。YouTube のチャプターは 3 つ以上で表示されます" % len(chs))
    for c, ln in zip(chs, lens):
        if ln < 10000:
            warns.append("章「%s」は %.1f 秒です。YouTube のチャプターはどれも 10 秒以上が必要です" % (c["title"], ln / 1000))
    credits = []
    for c in list(spec.get("_credits") or []) + list(spec.get("_exportCredits") or []) + [(spec.get("audio") or {}).get("music_credit")]:
        if c and c not in credits:
            credits.append(c)
    desc = [spec.get("title", ""), ""] + ["%s %s" % (clock(c["t"]), c["title"]) for c in chs]
    if credits:
        desc += [""] + credits
    p = os.path.join(outdir, "youtube_description.txt")
    open(p, "w", encoding="utf-8").write("\n".join(desc).strip() + "\n")
    files.append(p)
    return files


# ──────────────────────────────────────────────────────────────────────────
# 素材（声の WAV を書き出す場所へ集める）と、プロジェクトに書くパス
# ──────────────────────────────────────────────────────────────────────────
def collect_voices(tl, outdir):
    vdir = os.path.join(outdir, "voices")
    n = 0
    for i, c in enumerate(tl["cues"]):
        if not c["vpath"]:
            continue
        os.makedirs(vdir, exist_ok=True)
        name = "%03d_%s.wav" % (i + 1, re.sub(r'[\\/:*?"<>|\s]', "_", c["name"])[:20])
        dst = os.path.join(vdir, name)
        if os.path.abspath(c["vpath"]) != os.path.abspath(dst):
            shutil.copyfile(c["vpath"], dst)
        c["vrel"] = "voices/" + name
        n += 1
    return n


class Paths:
    """プロジェクトに書く素材のパス。YMM4・AviUtl は Windows の絶対パスで素材を探す。"""

    def __init__(self, outdir, win_dir, warns):
        self.outdir, self.win = outdir, win_dir
        if not win_dir and os.name != "nt":
            warns.append("YMM4・AviUtl のプロジェクトは Windows のパスで素材を探します。--win-dir に、この書き出したフォルダを"
                         "置く Windows の場所（例 C:\\Users\\me\\Videos\\%s）を渡してください（今は %s のまま書きました）"
                         % (os.path.basename(outdir), outdir))

    def __call__(self, rel):
        if self.win:
            return ntpath.join(self.win, *rel.split("/"))
        p = os.path.abspath(os.path.join(self.outdir, rel))
        return p.replace("/", "\\") if os.name == "nt" else p


def layers(spec, tl):
    """層の割り当て（0 から）: 映像・音楽・効果音・声（話し手ごと）・字幕。"""
    lay, n = {"video": 0}, 1
    if has_music(spec):
        lay["music"] = n; n += 1
    if has_sfx(spec):
        lay["sfx"] = n; n += 1
    order = []
    for c in tl["cues"]:
        if c["vpath"] and c["who"] not in order:
            order.append(c["who"])
    for w in order:
        lay["voice:" + w] = n; n += 1
    lay["text"] = n
    return lay


def spans(items):
    """同じ層の項目が重ならないように、次の項目の手前で切る（frame・length は書き換える）。"""
    items.sort(key=lambda x: x["frame"])
    for a, b in zip(items, items[1:]):
        if a["frame"] + a["length"] > b["frame"]:
            a["length"] = max(1, b["frame"] - a["frame"])
    return items


def plan_items(spec, tl, fps, base):
    """プロジェクトに並べる項目（YMM4・AviUtl 共通）。frame は 0 から。"""
    f = lambda ms: int(round(ms * fps / 1000.0))
    total = max(1, f(tl["total"]))
    lay = layers(spec, tl)
    out = [{"kind": "video", "layer": lay["video"], "frame": 0, "length": total, "file": "%s_video.webm" % base}]
    if "music" in lay:
        out.append({"kind": "audio", "layer": lay["music"], "frame": 0, "length": total, "file": "%s_music.wav" % base, "remark": "音楽"})
    if "sfx" in lay:
        out.append({"kind": "audio", "layer": lay["sfx"], "frame": 0, "length": total, "file": "%s_sfx.wav" % base, "remark": "効果音"})
    by = {}
    for c in tl["cues"]:
        if c.get("vrel"):
            by.setdefault(lay["voice:" + c["who"]], []).append(
                {"kind": "audio", "layer": lay["voice:" + c["who"]], "frame": f(c["a"]), "length": max(1, f(c["a"] + c["vms"]) - f(c["a"])),
                 "file": c["vrel"], "remark": "%s：%s" % (c["name"], c["text"])})
        by.setdefault(lay["text"], []).append(
            {"kind": "text", "layer": lay["text"], "frame": f(c["a"]), "length": max(1, f(c["b"]) - f(c["a"])), "text": c["text"],
             "color": c["color"], "name": c["name"] if c["who"] else ""})
    for k in sorted(by):
        out += spans(by[k])
    return out, total, lay


def rgb(color, default):
    m = re.match(r"^#?([0-9a-fA-F]{6})$", str(color or "").strip())
    if m:
        return m.group(1).lower()
    m = re.match(r"^#?([0-9a-fA-F]{3})$", str(color or "").strip())
    return "".join(ch * 2 for ch in m.group(1)).lower() if m else default


# ──────────────────────────────────────────────────────────────────────────
# YMM4: 台本（CSV）とプロジェクト（.ymmp）
# ──────────────────────────────────────────────────────────────────────────
def anim(v):
    return {"Values": [{"Value": float(v)}], "Span": 0.0, "AnimationType": "なし"}


def _common(it):
    return {"FadeIn": 0.0, "FadeOut": 0.0, "Group": 0, "Frame": it["frame"], "Layer": it["layer"], "KeyFrames": {"Frames": [], "Count": 0},
            "Length": it["length"], "PlaybackRate": 100.0, "PlaybackRate2": anim(100), "ContentOffset": "00:00:00",
            "Remark": it.get("remark", ""), "IsLocked": False, "IsHidden": False}


def _visual():
    return {"X": anim(0), "Y": anim(0), "Z": anim(0), "Opacity": anim(100), "Zoom": anim(100), "Rotation": anim(0), "Blend": "Normal",
            "IsInverted": False, "IsClippingWithObjectAbove": False, "IsAlwaysOnTop": False, "IsZOrderEnabled": False, "VideoEffects": []}


def ymmp_item(it, path):
    if it["kind"] == "video":
        d = {"$type": "YukkuriMovieMaker.Project.Items.VideoItem, YukkuriMovieMaker", "FilePath": path(it["file"]),
             "Volume": anim(100), "Pan": anim(0), "IsLooped": False, "AudioEffects": []}
        d.update(_visual())
    elif it["kind"] == "audio":
        d = {"$type": "YukkuriMovieMaker.Project.Items.AudioItem, YukkuriMovieMaker", "FilePath": path(it["file"]),
             "Volume": anim(100), "Pan": anim(0), "IsLooped": False, "EchoIsEnabled": False, "EchoInterval": 0.1, "EchoAttenuation": 40.0,
             "AudioEffects": []}
    else:
        d = {"$type": "YukkuriMovieMaker.Project.Items.TextItem, YukkuriMovieMaker", "Text": it["text"], "Decorations": [], "Font": "Meiryo",
             "FontSize": anim(54), "LineHeight2": anim(100), "LetterSpacing2": anim(0), "WordWrap": "NoWrap", "MaxWidth": anim(W),
             "BasePoint": "CenterBottom", "FontColor": "#FFFFFFFF", "Style": "Border", "StyleColor": "#FF" + rgb(it.get("color"), "000000").upper(),
             "Bold": True, "Italic": False, "Underline": False, "Strikethrough": False, "IsTrimEndSpace": False, "IsDevidedPerCharacter": False,
             "DisplayInterval": 0.0, "DisplayDirection": "FromFirst", "HideInterval": 0.0, "HideDirection": "FromFirst"}
        d.update(_visual())
        d["Y"] = anim(H / 2 - 40)
        it = dict(it, remark=it.get("name", ""))
    d.update(_common(it))
    return d


def export_ymm4(spec, tl, outdir, base, fps, path):
    files = []
    # 台本（YMM4 の「台本ファイルを開く」で読む。A 列 キャラクター名・B 列 セリフ。名前は YMM4 のキャラクター名に合わせる）
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\r\n")
    for c in tl["cues"]:
        wr.writerow([c["name"], c["text"]])
    p = os.path.join(outdir, "%s_ymm4_script.csv" % base)
    open(p, "w", encoding="utf-8-sig", newline="").write(buf.getvalue())
    files.append(p)
    items, total, lay = plan_items(spec, tl, fps, base)
    proj = {
        "FilePath": path("%s.ymmp" % base),
        "SelectedTimelineIndex": 0,
        "Timelines": [{
            "ID": str(uuid.uuid5(uuid.NAMESPACE_URL, "motion-video:" + base)), "Name": "Main",
            "VideoInfo": {"FPS": fps, "Hz": HZ, "Width": W, "Height": H, "BackgroundColor": "#FF000000"},
            "Items": [ymmp_item(it, path) for it in items],
            "LayerSettings": {"Items": []}, "CurrentFrame": 0, "Length": total, "MaxLayer": max(it["layer"] for it in items),
        }],
        "Characters": [], "CollapsedGroups": [], "ToolStates": {},
    }
    p = os.path.join(outdir, "%s.ymmp" % base)
    open(p, "w", encoding="utf-8-sig").write(json.dumps(proj, ensure_ascii=False, indent=2))
    files.append(p)
    return files


# ──────────────────────────────────────────────────────────────────────────
# AviUtl（拡張編集）: .exo
# ──────────────────────────────────────────────────────────────────────────
def exo_text(s):
    """テキストの text=（UTF-16LE の 16 進。4096 桁まで 0 で埋める）。"""
    hx = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-16-le").hex()[:4092]
    return hx + "0" * (4096 - len(hx))


def export_exo(spec, tl, outdir, base, fps, path, warns):
    items, total, lay = plan_items(spec, tl, fps, base)
    L = ["[exedit]", "width=%d" % W, "height=%d" % H, "rate=%d" % fps, "scale=1", "length=%d" % total, "audio_rate=%d" % HZ, "audio_ch=2"]
    for i, it in enumerate(items):
        start, end = it["frame"] + 1, it["frame"] + it["length"]
        L += ["[%d]" % i, "start=%d" % start, "end=%d" % end, "layer=%d" % (it["layer"] + 1), "overlay=1"]
        if it["kind"] == "audio":
            L += ["audio=1", "[%d.0]" % i, "_name=音声ファイル", "再生位置=0.00", "再生速度=100.0", "ループ再生=0", "動画ファイルと連携=0",
                  "file=" + path(it["file"]), "[%d.1]" % i, "_name=標準再生", "音量=100.0", "左右=0.0"]
            continue
        L += ["camera=0"]
        if it["kind"] == "video":
            L += ["[%d.0]" % i, "_name=動画ファイル", "再生位置=1", "再生速度=100.0", "ループ再生=0", "アルファチャンネルを読み込む=0",
                  "file=" + path(it["file"])]
        else:
            L += ["[%d.0]" % i, "_name=テキスト", "サイズ=54", "表示速度=0.0", "文字毎に個別オブジェクト=0", "移動座標上に表示する=0",
                  "自動スクロール=0", "B=1", "I=0", "type=3", "autoadjust=0", "soft=1", "monospace=0", "align=7", "spacing_x=0", "spacing_y=0",
                  "precision=1", "color=ffffff", "color2=" + rgb(it.get("color"), "000000"), "font=メイリオ", "text=" + exo_text(it["text"])]
        L += ["[%d.1]" % i, "_name=標準描画", "X=0.0", "Y=%.1f" % (H / 2 - 40 if it["kind"] == "text" else 0), "Z=0.0", "拡大率=100.00",
              "透明度=0.0", "回転=0.00", "blend=0"]
    data = "\r\n".join(L) + "\r\n"
    try:
        raw = data.encode("cp932")
    except UnicodeEncodeError:
        raw = data.encode("cp932", errors="replace")
        warns.append("exo は Shift_JIS で書くため、素材のパスに Shift_JIS に無い文字があり「?」に置き換えました（フォルダ名を英数字にしてください）")
    p = os.path.join(outdir, "%s.exo" % base)
    open(p, "wb").write(raw)
    return [p]


# ──────────────────────────────────────────────────────────────────────────
# まとめ
# ──────────────────────────────────────────────────────────────────────────
README = """書き出したファイル（{title}）

■ プレイヤーから書き出して、このフォルダに置くもの
  このフォルダの {base}.html を開き、⚙（設定）から:
  - 「編集用の映像（字幕・音なし WebM）」 → {base}_video.webm（最初から 1 倍速で録画するので、動画の長さだけかかります）
  - 「音のトラックを書き出す（WAV）」     → {base}_voice.wav / {base}_music.wav / {base}_sfx.wav / {base}_mix.wav
  ダウンロードされたファイルを、このフォルダ（{dir}）へ移してください。
  時間割は台本どおりなので、ここにある字幕・プロジェクトと時刻がそろいます。

■ YouTube
  - {base}.<言語>.srt / .vtt … 字幕（YouTube Studio の「字幕」→ ファイルをアップロード → タイミングあり）
  - youtube_description.txt … 概要欄に貼る（チャプターの時刻・クレジット）
  - subs.<言語>.txt         … 字幕の文（1 行に 1 つ）。subs.en.txt などに同じ行数で訳を書いてもう一度 --export すると、その言語の字幕もできます
  - {base}_mix.wav          … 音の全部（動画を作り直す・ほかの言語の音声トラックの元に）。声・音楽・効果音は別々の WAV もあります
  ※ 動画の本体は ⚙ の「動画ファイル（WebM）で保存」（字幕・音入り）か、編集ソフトで作ったものを使います。

■ YMM4（ゆっくりMovieMaker4）
  - {base}_ymm4_script.csv … 台本（ファイル → 台本ファイルを開く）。A 列の名前は YMM4 のキャラクター名に合わせてください。
                             YMM4 のキャラクターの声・立ち絵で作り直すときに使います
  - {base}.ymmp            … 映像・音楽・効果音・声（voices/）・字幕を層に並べたプロジェクト（実験的。開けないときは CSV を使ってください）

■ AviUtl（拡張編集）
  - {base}.exo … タイムラインへドラッグ。WebM を読むには L-SMASH Works などの入力プラグインが要ります

素材のパス: {paths}
"""


def run(spec, spec_path, kinds, outdir=None, fps=30, win_dir=None):
    kinds = [k.strip() for k in (kinds or "").split(",") if k.strip()]
    if "all" in kinds:
        kinds = list(KINDS)
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        sys.exit("error: --export は %s（カンマで区切る。all で全部）: %s" % ("・".join(KINDS), ", ".join(bad)))
    base = spec["_exportName"]
    outdir = os.path.abspath(outdir or os.path.splitext(os.path.abspath(spec_path))[0] + "_export")
    os.makedirs(outdir, exist_ok=True)
    tl = timeline(spec)
    warns, files = [], []
    lang = (spec.get("lang") or "ja").split("-")[0]
    if "youtube" in kinds:
        files += export_youtube(spec, tl, outdir, base, lang, warns)
    if "ymm4" in kinds or "exo" in kinds:
        nv = collect_voices(tl, outdir)
        if not nv:
            warns.append("前もって作った声が無いので、プロジェクトに声は入りません（--voicevox か --voices-dir で作ると入ります）")
        path = Paths(outdir, win_dir, warns)
        if "ymm4" in kinds:
            files += export_ymm4(spec, tl, outdir, base, fps, path)
        if "exo" in kinds:
            files += export_exo(spec, tl, outdir, base, fps, path, warns)
    open(os.path.join(outdir, "README.txt"), "w", encoding="utf-8").write(README.format(
        title=spec.get("title", ""), base=base, dir=outdir, paths=win_dir or outdir))
    for w in warns:
        print("warn:", w, file=sys.stderr)
    print("書き出し: %s（%s）" % (outdir, "・".join(kinds)))
    for p in files:
        print("  " + os.path.relpath(p, outdir))
    need = ["%s_video.webm" % base] + (["%s_music.wav" % base] if has_music(spec) else []) + (["%s_sfx.wav" % base] if has_sfx(spec) else [])
    if "ymm4" in kinds or "exo" in kinds:
        print("  あとで置く（HTML の ⚙ から書き出す）: " + "・".join(need))
    return outdir


# ──────────────────────────────────────────────────────────────────────────
# 台本を読む（隣のスキル）
# ──────────────────────────────────────────────────────────────────────────
def sibling(skill, name):
    path = os.path.join(os.path.dirname(HERE), skill, name)   # 「..」は使わない（リンク越しに置かれたとき、リンク先の親をたどってしまう）
    if not os.path.isfile(path):
        sys.exit("error: %s スキルが見つかりません（%s）。同じ場所に置いてください" % (skill, path))
    sp = importlib.util.spec_from_file_location("%s_%s" % (skill.replace("-", "_"), name[:-3]), path)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description="motion-video・yukkuri-kaisetsu の動画を、YouTube と編集ソフト（YMM4・AviUtl）向けに書き出す")
    ap.add_argument("script", help="台本（motion-video の .json か、yukkuri-kaisetsu の .txt）")
    ap.add_argument("--to", default="all", help="書き出す種類（youtube・ymm4・exo をカンマで。既定 all）")
    ap.add_argument("--out-dir", help="書き出す場所（既定: 台本と同じ場所の <台本名>_export/）")
    ap.add_argument("--fps", type=int, default=30, help="YMM4・AviUtl のプロジェクトのフレームレート（既定 30）")
    ap.add_argument("--win-dir", help="YMM4・AviUtl のプロジェクトに書く素材の場所（書き出したフォルダを置く Windows のパス）")
    ap.add_argument("--voicevox", action="store_true", help="VOICEVOX で声を前もって作る（公開する動画はこれか --voices-dir）")
    ap.add_argument("--voicevox-url", default="http://127.0.0.1:50021")
    ap.add_argument("--voices-dir", help="用意した WAV を名前順に、字幕（とせりふ）へ順に当てる")
    ap.add_argument("--player", help="書き出す場所に作る HTML のプレイヤー（台本の player を上書き）")
    ap.add_argument("--theme", help="書き出す場所に作る HTML の配色（台本の theme を上書き）")
    a = ap.parse_args()
    if a.script.lower().endswith(".txt"):
        ks = sibling("yukkuri-kaisetsu", "kaisetsu.py")
        spec, mv, _, _ = ks.make_spec(a.script, a.voicevox, a.voicevox_url, a.voices_dir)
    else:
        mv = sibling("motion-video", "build.py")
        spec = mv.load(a.script, a.voicevox, a.voicevox_url, a.voices_dir)
    player = a.player or spec.get("player", "studio")
    theme = a.theme or spec.get("theme", "navy-brass")
    if player not in mv.PLAYERS or theme not in mv.THEMES:
        sys.exit("error: player は %s、theme は %s のいずれか" % ("/".join(mv.PLAYERS), "/".join(mv.THEMES)))
    outdir = run(spec, a.script, a.to, a.out_dir, a.fps, a.win_dir)
    # 同じ時間割の HTML（⚙ から映像と音を書き出す）
    html_path = os.path.join(outdir, spec["_exportName"] + ".html")
    open(html_path, "w", encoding="utf-8").write(mv.build_html(spec, theme, player))
    print("  %s … ⚙ から映像（字幕・音なし WebM）と音（WAV）を書き出して、このフォルダに置く" % os.path.basename(html_path))


if __name__ == "__main__":
    main()
