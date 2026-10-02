#!/usr/bin/env python3
"""ゆっくり解説・ずんだもん解説の台本（テキスト）から、motion-video の掛け合いの動画（単一 HTML）を作る。

  python3 kaisetsu.py script.txt                         # 台本 → script.json（motion-video の台本）→ script.html
  python3 kaisetsu.py script.txt --voicevox              # VOICEVOX（http://127.0.0.1:50021）でせりふの WAV を作ってから
  python3 kaisetsu.py script.txt --voices-dir voices/    # 用意した WAV（名前順）をせりふに順に当てる
  python3 kaisetsu.py script.txt --timeline              # 時間割りだけ見る
  python3 kaisetsu.py --list-casts                       # 登場人物のプリセット

台本の書き方は SKILL.md。組み立ては隣の motion-video スキルの build.py を使う。
"""
import argparse, glob, importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.realpath(__file__))
PRESETS = {k: v for k, v in json.load(open(os.path.join(HERE, "casts.json"), encoding="utf-8")).items() if not k.startswith("_")}
FACES = ["normal", "smile", "surprised", "angry", "sad", "think", "shy", "troubled"]
EMOTES = {"!", "?", "!?", "♪", "💦", "💢", "…"}
IMG_EXT = (".png", ".webp", ".jpg", ".jpeg", ".gif")


def talk_lines(sc):
    """せりふ（話し手付きの行）だけ。締めの場面の lines（文字列）は含めない。"""
    return [ln for ln in sc.get("lines", []) if isinstance(ln, dict) and ln.get("who")]


def motion_video():
    path = os.path.join(HERE, "..", "motion-video", "build.py")
    if not os.path.isfile(path):
        sys.exit("error: motion-video スキルが見つかりません（%s）。同じ場所に置いてください" % path)
    spec = importlib.util.spec_from_file_location("motion_video_build", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ──────────────────────────────────────────────────────────────────────────
# 台本の読み取り
# ──────────────────────────────────────────────────────────────────────────
LINE_RE = re.compile(r"^([\w\-]+)(?:[（(]([^)）]*)[)）])?\s*[:：]\s*(.*?)\s*(?:\[([^\]]+)\])?\s*$")
PAUSE_RE = re.compile(r"^[（(]\s*(?:間|pause)\s*([\d.]+)?\s*[)）]$")


def parse_board(rest):
    """@board の中身: 文字列 / image: パス / {JSON} / bullets|steps|statement: 見出し | 項目 | …"""
    rest = rest.strip()
    if rest.startswith("{"):
        return json.loads(rest)
    m = re.match(r"^(\w+)\s*:\s*(.*)$", rest)
    if m and m.group(1) in ("image", "bullets", "steps", "statement", "title", "cards", "stats"):
        kind, body = m.group(1), m.group(2)
        parts = [p.strip() for p in body.split("|")]
        if kind == "image":
            return {"type": "image", "src": parts[0], "caption": parts[1] if len(parts) > 1 else ""}
        if kind in ("bullets", "steps"):
            return {"type": kind, "heading": parts[0], "items": [p for p in parts[1:] if p]}
        if kind == "cards":
            return {"type": "cards", "heading": parts[0], "items": [{"title": p.split("—")[0].strip(), "text": p.split("—")[1].strip() if "—" in p else ""} for p in parts[1:]]}
        if kind == "stats":
            return {"type": "stats", "heading": parts[0], "items": [{"value": p.split()[0], "label": " ".join(p.split()[1:])} for p in parts[1:]]}
        if kind == "title":
            return {"type": "title", "title": parts[0], "subtitle": parts[1] if len(parts) > 1 else ""}
        return {"type": "statement", "lines": parts}
    return rest


def parse(text):
    meta, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if m:
        for ln in m.group(1).splitlines():
            ln = re.sub(r"\s+#\s.*$", "", ln).strip()   # 「 # 説明」は注記（#5fae45 のような色は残す）
            if ln.startswith("//"):
                continue
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip()
        body = text[m.end():]
    chapters, errs = [], []
    ch = sc = None

    def new_scene(**kw):
        nonlocal sc
        if ch is None:
            new_chapter("はじめに")
        sc = {"type": "talk", "lines": []}
        sc.update(kw)
        ch["scenes"].append(sc)

    def new_chapter(title):
        nonlocal ch, sc
        ch = {"title": title, "scenes": []}
        chapters.append(ch)
        sc = None

    pending = {}
    for no, raw in enumerate(body.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("# "):
            new_chapter(line[2:].strip())
            continue
        if line.startswith("@"):
            m2 = re.match(r"^@(\w+)\s*(?::\s*|\s+)?(.*)$", line)
            if not m2:
                errs.append("%d 行目: @ の書き方が違います: %s" % (no, raw)); continue
            key, rest = m2.group(1), m2.group(2)
            if key == "board":
                try:
                    board = parse_board(rest)
                except ValueError as e:
                    errs.append("%d 行目: board の JSON が読めません（%s）" % (no, e)); continue
                if sc is not None and not sc["lines"] and "board" not in sc:
                    sc["board"] = board
                else:
                    new_scene(board=board, **pending); pending = {}
            elif key in ("bg", "transition", "camera", "fx"):
                if sc is None or sc["lines"]:
                    pending[key] = rest if key != "fx" else [x.strip() for x in rest.split(",")]
                else:
                    sc[key] = rest if key != "fx" else [x.strip() for x in rest.split(",")]
            elif key == "music":
                if ch is None:
                    new_chapter("はじめに")
                ch["music"] = rest
            elif key == "scene":
                new_scene(**pending); pending = {}
            else:
                errs.append("%d 行目: 知らない指定 @%s" % (no, key))
            continue
        pm = PAUSE_RE.match(line)
        if pm:
            if sc and sc["lines"]:
                sc["lines"][-1]["pause"] = float(pm.group(1) or 1)
            continue
        lm = LINE_RE.match(line)
        if not lm:
            errs.append("%d 行目: 「話し手: せりふ」の形になっていません: %s" % (no, raw)); continue
        who, opts, text_, emote = lm.group(1), lm.group(2), lm.group(3), lm.group(4)
        if sc is None:
            new_scene(**pending); pending = {}
        ln = {"who": who, "text": text_}
        for o in re.split(r"[,、\s]+", opts or ""):
            if not o:
                continue
            if o == "shake":
                ln["shake"] = True
            elif re.match(r"^[\d.]+$", o):
                ln["pause"] = float(o)
            else:
                ln["face"] = o
        if emote:
            ln["emote"] = emote.strip()
        sc["lines"].append(ln)
    return meta, chapters, errs


# ──────────────────────────────────────────────────────────────────────────
# 登場人物
# ──────────────────────────────────────────────────────────────────────────
def find_images(cid, base, chars_dir):
    """chars/<id>/ の <表情>.png・<表情>_open.png・<表情>_half.png・<表情>_blink.png を images にする。"""
    d = os.path.join(base, chars_dir, cid)
    if not os.path.isdir(d):
        return {}
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(IMG_EXT))
    faces = {}
    for f in files:
        stem = os.path.splitext(f)[0]
        m = re.match(r"^(.+?)(?:_(open|half|blink|closed))?$", stem)
        face, part = m.group(1), m.group(2) or "closed"
        faces.setdefault(face, {})[part] = os.path.relpath(os.path.join(d, f), base)
    return faces


def build_cast(meta, base):
    ids = [x.strip() for x in re.split(r"[,、\s]+", meta.get("cast", "zundamon, metan")) if x.strip()]
    chars_dir = meta.get("chars", "chars")
    cast = {}
    for i, cid in enumerate(ids):
        c = json.loads(json.dumps(PRESETS.get(cid, {"name": cid, "voice": {"engine": "browser"}})))
        if cid not in PRESETS:
            c["color"] = ["#3b82c4", "#d9772b", "#5fae45", "#d6538f"][i % 4]
        c.setdefault("side", "left" if i % 2 == 0 else "right")
        for k in ("name", "color", "side"):
            if meta.get("%s.%s" % (cid, k)):
                c[k] = meta["%s.%s" % (cid, k)]
        imgs = find_images(cid, base, chars_dir)
        if imgs:
            c["images"] = imgs
        if meta.get("%s.credit" % cid):
            c["image_credit"] = meta["%s.credit" % cid]
        cast[cid] = c
    return cast


# ──────────────────────────────────────────────────────────────────────────
# 声（VOICEVOX・用意した WAV）
# ──────────────────────────────────────────────────────────────────────────
def voicevox_lines(spec, url, outdir, pronounce):
    """VOICEVOX でせりふの WAV を作る（同じ話者・同じ文は作り直さない）。作った数を返す。VOICEVOX との通信は motion-video の voice.py。"""
    sys.path.insert(0, os.path.join(HERE, "..", "motion-video"))
    import voice
    vv = voice.Voicevox(url)
    for ch in spec["chapters"]:
        for sc in ch["scenes"]:
            for ln in talk_lines(sc):
                v = (spec["cast"].get(ln["who"], {}).get("voice") or {})
                if v.get("engine") != "voicevox" or ln.get("voice"):
                    continue
                text = ln["text"].replace("**", "")
                for k in sorted(pronounce, key=len, reverse=True):
                    text = text.replace(k, pronounce[k])
                ln["voice"] = vv.synth(text, v, outdir)
    return vv.made


def assign_voice_files(spec, vdir):
    files = sorted(glob.glob(os.path.join(vdir, "*.wav")))
    i = 0
    for ch in spec["chapters"]:
        for sc in ch["scenes"]:
            for ln in talk_lines(sc):
                if ln.get("voice"):
                    continue
                if i >= len(files):
                    return i, len(files)
                ln["voice"] = files[i]
                i += 1
    return i, len(files)


# ──────────────────────────────────────────────────────────────────────────
# 台本（motion-video の JSON）を組む
# ──────────────────────────────────────────────────────────────────────────
def sample_credit(spec):
    """motion-video の曲が録音の楽器の音（samples.py）を使うなら、そのクレジット。audio.samples: false・曲なし・音声ファイルの曲では無し。"""
    au = spec.get("audio") or {}
    if au.get("samples", True) is False:
        return None
    sys.path.insert(0, os.path.join(HERE, "..", "motion-video"))
    import sound, samples
    names = [au.get("music")] + [ch.get("music") for ch in spec.get("chapters", [])]
    for n in names:
        if isinstance(n, str) and n in sound.MUSIC and any(L.get("inst") in samples.MAP for L in sound.MUSIC[n].get("layers", [])):
            return samples.CREDIT
    return None


def make_credits(meta, cast, vv_used):
    """締めに出すクレジット。VOICEVOX の表記は、実際に VOICEVOX で声を作ったときだけ（ほかの声は voice_credit: に書く）。"""
    credits = []
    if vv_used:
        credits += [c["credit"] for c in cast.values() if c.get("credit") and (c.get("voice") or {}).get("engine") == "voicevox"]
    if meta.get("voice_credit"):
        credits.append(meta["voice_credit"])
    for cid, c in cast.items():
        if c.get("image_credit"):
            credits.append("立ち絵（%s）: %s" % (c.get("name", cid), c["image_credit"]))
    if meta.get("music_credit"):
        credits.append("BGM: " + meta["music_credit"])
    for k in ("bg_credit", "credit"):
        if meta.get(k):
            credits.append(meta[k])
    return credits


def to_spec(meta, chapters, cast):
    music = meta.get("music", "none")
    if re.search(r"\.(mp3|m4a|ogg|wav)$", music, re.I):
        music = {"file": music, "volume": float(meta.get("music_volume", .3))}
    spec = {"title": meta.get("title", "解説"), "description": meta.get("description", ""), "lang": "ja",
            "player": meta.get("player", "studio"), "theme": meta.get("theme", "daylight"), "castAlways": True,
            "transition": meta.get("transition", "slide"),
            "audio": {"narration": True, "music": music, "duck": .35, "sfx": {"kit": meta.get("kit", "playful"), "density": meta.get("density", "low")},
                      "pronounce": json.loads(meta["pronounce"]) if meta.get("pronounce", "").startswith("{") else {}},
            "cast": cast, "chapters": chapters}
    if meta.get("motion"):
        spec["motion"] = meta["motion"]
    for ch in chapters:
        for sc in ch["scenes"]:
            if meta.get("bg") and not sc.get("bg"):
                sc["bg"] = meta["bg"]
    credits = make_credits(meta, cast, False)
    if meta.get("end", "yes") != "no":
        chapters.append({"title": "おわりに", "scenes": [{"type": "end", "title": meta.get("end_title", "ご視聴ありがとうございました"),
                                                           "lines": credits[:6], "narration": ""}]})
    return spec, credits


def make_spec(script, voicevox=False, voicevox_url="http://127.0.0.1:50021", voices_dir=None):
    """台本（テキスト）から motion-video の台本を作り、声を当て、確かめ、時間割を決める。誤りがあれば止める。
    返り値は (台本, motion-video の build, 登場人物, クレジット)。video-export スキル（書き出し）もこれで読む。"""
    base = os.path.dirname(os.path.abspath(script))
    meta, chapters, errs = parse(open(script, encoding="utf-8").read())
    for e in errs:
        print("error:", e, file=sys.stderr)
    if errs:
        sys.exit(1)
    cast = build_cast(meta, base)
    unknown = sorted({ln["who"] for ch in chapters for sc in ch["scenes"] for ln in sc.get("lines", [])} - set(cast))
    if unknown:
        sys.exit("error: cast に無い話し手: %s（台本の先頭の cast: に足してください）" % "、".join(unknown))
    spec, credits = to_spec(meta, chapters, cast)
    if voicevox:
        n = voicevox_lines(spec, voicevox_url, os.path.join(base, os.path.splitext(os.path.basename(script))[0] + "_voices"), spec["audio"]["pronounce"])
        print("VOICEVOX: %d 個のせりふの声を作りました（作り済みは使い回し）" % n)
    credits = make_credits(meta, cast, voicevox)
    sc_ = sample_credit(spec)
    if sc_:
        credits.append(sc_)
    last = spec["chapters"][-1]["scenes"][-1]
    if last.get("type") == "end":
        last["lines"] = credits[:7]
    if voices_dir:
        used, have = assign_voice_files(spec, os.path.join(base, voices_dir) if not os.path.isabs(voices_dir) else voices_dir)
        print("WAV: %d 個をせりふに当てました（フォルダに %d 個）" % (used, have))
    for ch in spec["chapters"]:
        for sc in ch["scenes"]:
            for ln in talk_lines(sc):
                if ln.get("voice") and os.path.isabs(ln["voice"]):
                    ln["voice"] = os.path.relpath(ln["voice"], base)
    stem = os.path.splitext(os.path.abspath(script))[0]
    json.dump(spec, open(stem + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    mv = motion_video()
    errs = mv.validate(spec, base)
    for e in errs:
        print("error:", e, file=sys.stderr)
    if errs:
        sys.exit(1)
    for w in mv.plan(spec):
        print("warn:", w, file=sys.stderr)
    spec["_exportName"] = mv.export_name(spec, script)
    spec["_exportCredits"] = credits   # 書き出しの概要欄に載せる（HTML には入れない）
    return spec, mv, cast, credits


def main():
    ap = argparse.ArgumentParser(description="ゆっくり解説・ずんだもん解説の台本から、掛け合いの動画（単一 HTML）を作る")
    ap.add_argument("script", nargs="?", help="台本（テキスト）")
    ap.add_argument("-o", "--out", help="出力 HTML（既定: 台本と同じ場所・同じ名前）")
    ap.add_argument("--voicevox", action="store_true", help="VOICEVOX でせりふの声を作る（engine: voicevox の登場人物）")
    ap.add_argument("--voicevox-url", default="http://127.0.0.1:50021")
    ap.add_argument("--voices-dir", help="用意した WAV のフォルダ（名前順に、声の無いせりふへ順に当てる）")
    ap.add_argument("--timeline", action="store_true", help="HTML を作らず時間割りを出す")
    ap.add_argument("--list-casts", action="store_true", help="登場人物のプリセットを出す")
    a = ap.parse_args()
    if a.list_casts or not a.script:
        print("# 登場人物のプリセット（台本の cast: に並べる。chars/<名前>/ に立ち絵を置く）")
        for k, v in PRESETS.items():
            print("  %-9s %-8s 声: %-9s %s" % (k, v["name"], (v.get("voice") or {}).get("engine", "-"), v.get("note", v.get("credit", ""))))
        return
    spec, mv, cast, credits = make_spec(a.script, a.voicevox, a.voicevox_url, a.voices_dir)
    stem = os.path.splitext(os.path.abspath(a.script))[0]
    total = sum(s["_dur"] for ch in spec["chapters"] for s in ch["scenes"])
    if a.timeline:
        t = 0
        for ch in spec["chapters"]:
            print("%s  %s" % (mv.fmt(t), ch["title"]))
            for s in ch["scenes"]:
                for cu in s.get("_cues", []):
                    who = cast.get(cu[3], {}).get("name", "") if len(cu) > 3 and cu[3] else ""
                    print("   %s  %s%s" % (mv.fmt(t + cu[0]), who + "：" if who else "", cu[2]))
                t += s["_dur"]
        print("合計 %s" % mv.fmt(total))
        return
    out = a.out or stem + ".html"
    open(out, "w", encoding="utf-8").write(mv.build_html(spec, spec["theme"], spec["player"]))
    print("OK : %s（%s）" % (out, mv.fmt(total)))
    if credits:
        print("クレジット: " + " / ".join(credits))


if __name__ == "__main__":
    main()
