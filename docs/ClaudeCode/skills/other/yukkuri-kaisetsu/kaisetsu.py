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
sys.path.insert(0, HERE)
PRESETS = {k: v for k, v in json.load(open(os.path.join(HERE, "casts.json"), encoding="utf-8")).items() if not k.startswith("_")}
LABELS = json.load(open(os.path.join(HERE, "labels.json"), encoding="utf-8"))   # 表情・体（ポーズと持ち物）・動きのラベルと説明
FACES, POSES, ITEMS, MOTIONS = list(LABELS["faces"]), list(LABELS["poses"]), list(LABELS["items"]), list(LABELS["motions"])
FALLBACK = {"smile": ["normal"], "surprised": ["normal"], "angry": ["doubt", "troubled", "normal"], "sad": ["troubled", "normal"],
            "troubled": ["sad", "normal"], "think": ["doubt", "troubled", "normal"], "shy": ["smile", "normal"], "smug": ["smile", "normal"],
            "doubt": ["think", "troubled", "normal"], "dizzy": ["troubled", "surprised", "normal"], "love": ["shy", "smile", "normal"]}   # 無い表情の代わり（近い順）
STYLES = json.load(open(os.path.join(HERE, "styles.json"), encoding="utf-8"))   # 動画の型（style:）
BGS = json.load(open(os.path.join(HERE, "backgrounds.json"), encoding="utf-8"))   # 背景のカタログ（bg/）
BGMS = json.load(open(os.path.join(HERE, "bgm.json"), encoding="utf-8"))          # BGM のカタログ（bgm/）
WEBM_ONLY = []   # 台本で使った、HTML に埋め込んで配れない曲（embed: false）
OPT_RE = re.compile(r"^(.+?)(#\d+)?([+-])?$")   # smile・smile+・smile-・smile#2
EMOTES = {"!", "?", "!?", "♪", "💦", "💢", "…"}
IMG_EXT = (".png", ".webp", ".jpg", ".jpeg", ".gif")
DEFAULT_SPEED = 1.1   # 話速の倍率（台本の speed:）。プリセットの速さに掛ける。解説動画の定番は 1.15〜1.25 倍
# ラベルの無いせりふに付ける演技（上から順に、最初に合ったもの）: (せりふ・印に合う形, 表情, 体, 動き, 誰に: L 聞き手・E 解説役・空 どちらも)
ACTING = [
    (r"！？|!\?|？！|^(えっ|ええっ|えぇ|なんと|まさか|うそ|ウソ|マジ)", "surprised", "", "", ""),
    (r"💢|ひどい|ゆるせ|ふざけ|納得いか", "angry", "", "", ""),
    (r"そんな.*(わけ|話じゃ|単純)|聞いてた|言いすぎ|誰が.*(のよ|んだ)|じゃないわよ|じゃないぜ|おいおい", "doubt", "fold", "", ""),
    (r"💦|困|やばい|ヤバい|まずい|しまった|どうしよう|むずかし|難し|大変", "troubled", "", "", ""),
    (r"悲し|残念|つらい|しょんぼり|…[。]?$", "sad", "", "", ""),
    (r"えへへ|照れ|ほめ.*(た|て)", "shy", "", "", ""),
    (r"♪|やった|すごい|すげ|うれしい|最高|わーい|ありがとう", "smile+", "raise", "", ""),
    (r"実は|じつは|ここだけ|秘密|ふっ|ふふ|結論から", "smug", "point", "", "E"),
    (r"^(なるほど|へぇ|へえ|へー|そうなん|そうだったん|わかった|たしかに|確かに)", "smile-", "", "nod", "L"),
    (r"うーん|ううん|かな[？?]|だろう[？?]|なんで|なぜ|どうして|どういうこと|[？?]\s*$", "think", "chin", "", "L"),
    (r"[？?]\s*$", "smile-", "point", "", "E"),
    (r"つまり|要するに|ポイント|大事|結論|まず|次に|最後に|理由は|答えは|簡単に言うと|\d", "normal", "point", "", "E"),
]


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
        if kind == "bullets":
            return {"type": kind, "heading": parts[0], "items": [p for p in parts[1:] if p]}
        if kind == "steps":
            return {"type": kind, "heading": parts[0], "items": [{"label": p.split("—")[0].strip(), "sub": p.split("—")[1].strip() if "—" in p else ""} for p in parts[1:] if p]}
        if kind == "cards":
            return {"type": "cards", "heading": parts[0], "items": [{"title": p.split("—")[0].strip(), "text": p.split("—")[1].strip() if "—" in p else ""} for p in parts[1:]]}
        if kind == "stats":
            return {"type": "stats", "heading": parts[0], "items": [{"value": p.split()[0], "label": " ".join(p.split()[1:])} for p in parts[1:]]}
        if kind == "title":
            return {"type": "title", "title": parts[0], "subtitle": parts[1] if len(parts) > 1 else ""}
        return {"type": "statement", "lines": parts}
    return rest


OPS = {"→", "->", "⇒", "←", "<-", "↔", "＋", "+", "×", "＝", "=", "≠", "vs", "VS", "？", "…"}
TEXT_COLORS = {"red": "#ff5a5f", "yellow": "#ffe45c", "blue": "#7cc4ff", "green": "#7be08a", "white": "#ffffff"}
REACT_RE = re.compile(r"^[>＞]\s*([\w\-]+)\s*(?:[（(]([^)）]*)[)）])?\s*(?:\[([^\]]+)\])?\s*(?:@\s*([\d.]+))?\s*$")


def split_cells(rest):
    """@show の中身を | で区切る（{…} の中と "…" の中の | は区切らない）。"""
    cells, cur, depth, quote = [], "", 0, False
    for ch in rest:
        if ch == '"':
            quote = not quote
        elif not quote and ch in "{[":
            depth += 1
        elif not quote and ch in "}]":
            depth -= 1
        if ch == "|" and not quote and depth <= 0:
            cells.append(cur)
            cur = ""
        else:
            cur += ch
    return [c.strip() for c in cells + [cur]]


LABEL_RE = r'(?:\s+"([^"]*)")?(?:\s*>\s*"([^"]*)")?'


def parse_show(rest):
    """@show の中身 → 1 つの絵の並び（shot）。| で区切る: 絵の名前 "名札" > "吹き出し"・"短い言葉"・→ などの記号・title: / note: / credit: …
    絵の代わりに、icon:名前（線で描いて動くアイコン）・part:{部品の JSON}（グラフ・図）・draw:名前（描き下ろしの JS）も置ける。"""
    shot = {"items": []}
    for cell in split_cells(rest):
        if not cell:
            continue
        m = re.match(r"^draw:(\S+)(?:\s+(dark|light|none))?$", cell)
        if m:   # 描き下ろし（中身は、台本を組むときにファイルから読む。stage_images）。後ろは下に敷く板（dark 既定・light・none）
            shot["items"].append(dict({"draw_ref": m.group(1)}, **({"plate": m.group(2)} if m.group(2) else {})))
            continue
        if cell.startswith("part:"):   # 部品（motion-video の部品の台本）を、絵と同じ場所に置く
            try:
                spec, end = json.JSONDecoder().raw_decode(cell[5:].lstrip())
            except ValueError as e:
                raise ValueError('part: の後ろは部品の JSON（例 part:{"type":"bars","items":[…]}）: %s' % e)
            m = re.match("^" + LABEL_RE + "$", cell[5:].lstrip()[end:])
            if not isinstance(spec, dict) or not m:
                raise ValueError('「%s」（part:{部品の JSON} "名札" > "吹き出し"）' % cell[:40])
            it = {"part": spec}
            for k, v in (("label", m.group(1)), ("say", m.group(2))):
                if v:
                    it[k] = v
            shot["items"].append(it)
            continue
        m = re.match(r"^(note|title|credit)\s*[:：]\s*(.+)$", cell)
        if m:
            shot[m.group(1)] = m.group(2).strip()
            continue
        if cell in OPS:
            shot["items"].append({"op": cell})
            continue
        m = re.match(r'^"(.*)"(?:\s+(#[0-9a-fA-F]{3,8}|red|yellow|blue|green|white))?$', cell)
        if m:
            it = {"text": m.group(1)}
            if m.group(2):
                it["color"] = TEXT_COLORS.get(m.group(2), m.group(2))
            shot["items"].append(it)
            continue
        m = re.match(r'^(\S+)(?:\s+"([^"]*)")?(?:\s*>\s*"([^"]*)")?(?:\s+(frame|noframe))?$', cell)
        if not m:
            raise ValueError('「%s」（絵の名前 "名札" > "吹き出し"、"短い言葉"、→ などの記号 のどれかを | で区切る）' % cell)
        it = {"ref": m.group(1)}
        if it["ref"].startswith("icon:"):
            it = {"icon": it["ref"][5:]}
        for k, v in (("label", m.group(2)), ("say", m.group(3))):
            if v:
                it[k] = v
        if m.group(4):
            it["frame"] = m.group(4) == "frame"
        shot["items"].append(it)
    if not shot["items"]:
        raise ValueError("絵も言葉もありません")
    return shot


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

    sticky = {}   # 章の中で出し続ける札（@tag・@corner）

    def new_scene(**kw):
        nonlocal sc
        if ch is None:
            new_chapter("はじめに")
        sc = {"type": "talk", "lines": []}
        sc.update({k: v for k, v in sticky.items() if v})
        sc.update(kw)
        ch["scenes"].append(sc)

    def new_chapter(title):
        nonlocal ch, sc
        ch = {"title": title, "scenes": []}
        chapters.append(ch)
        sc = None
        sticky.clear()

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
            elif key in ("show", "draw"):   # @draw: 名前 は @show: draw:名前 と同じ
                try:
                    shot = parse_show(rest if key == "show" else "draw:" + rest)
                except ValueError as e:
                    errs.append("%d 行目: @show の書き方が違います: %s" % (no, e)); continue
                staged = sc is not None and isinstance(sc.get("board"), dict) and sc["board"].get("type") == "stage"
                if sc is not None and "board" not in sc and not pending:   # 黒板の無い場面: そこから絵を出す
                    shot["line"] = len(sc["lines"])
                    sc["board"] = {"type": "stage", "shots": [shot]}
                elif staged and not pending:   # 同じ場面のまま、次のせりふから絵を替える
                    shot["line"] = len(sc["lines"])
                    if sc["board"]["shots"][-1]["line"] == shot["line"]:
                        sc["board"]["shots"][-1] = shot
                    else:
                        sc["board"]["shots"].append(shot)
                else:
                    shot["line"] = 0
                    new_scene(board={"type": "stage", "shots": [shot]}, **pending); pending = {}
            elif key in ("tag", "corner"):
                sticky[key] = rest
                if sc is not None and not sc["lines"]:
                    sc[key] = rest
                    if not rest:
                        sc.pop(key, None)
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
        rm = REACT_RE.match(line)
        if rm:   # 「> 聞き手(表情, 動き) [印] @0.6」: 前のせりふの間の、相手の反応
            if not (sc and sc["lines"]):
                errs.append("%d 行目: 反応（> …）の前に、せりふがありません" % no); continue
            r = {"who": rm.group(1), "opts": [o for o in re.split(r"[,、\s]+", rm.group(2) or "") if o], "at": float(rm.group(4) or .5)}
            if rm.group(3):
                r["emote"] = rm.group(3).strip()
            sc["lines"][-1].setdefault("react_raw", []).append(r)
            continue
        lm = LINE_RE.match(line)
        if not lm:
            errs.append("%d 行目: 「話し手: せりふ」の形になっていません: %s" % (no, raw)); continue
        who, opts, text_, emote = lm.group(1), lm.group(2), lm.group(3), lm.group(4)
        if sc is None:
            new_scene(**pending); pending = {}
        groups = (opts or "").split("|")   # 「(think, chin | smug, point)」: せりふの途中（文の中の | の位置）で演技を変える
        segs = text_.split("|") if len(groups) > 1 else [text_]
        ln = {"who": who, "text": "".join(segs)}
        for gi, grp in enumerate(groups):
            toks = []
            for o in re.split(r"[,、\s]+", grp):
                if not o:
                    continue
                if o == "shake":
                    ln["shake"] = True
                elif o == "big":
                    ln["big"] = True
                elif o.startswith("se:"):
                    ln["se"] = o[3:]
                elif o.startswith("voice:"):
                    ln["style"] = o[6:]
                elif re.match(r"^[\d.]+$", o):
                    ln["pause"] = float(o)
                else:
                    toks.append(o)   # 表情・体・動きのラベル。立ち絵が分かってから当てる（resolve_faces）
            if gi == 0:
                if toks:
                    ln["opts"] = toks
            else:
                at = sum(len(x) for x in segs[:gi]) / max(1, len(ln["text"])) if len(segs) > gi else gi / len(groups)
                ln.setdefault("acts_raw", []).append({"at": round(at, 3), "opts": toks})
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


def find_sprite(cid, base, chars_dir, art="svg"):
    """chars/<id>/sprite.json（体の絵にパーツを重ねる形。sprite.py）があれば読む。画像は sprite/<名前>.png。
    chars/<id>/svg/（SVG にしたパーツ。sprite.py --svg）があれば、そちらを使う（art が "png" のときは使わない）。"""
    d = os.path.join(base, chars_dir, cid)
    if art != "png" and os.path.isfile(os.path.join(d, "svg", "sprite.json")):
        d = os.path.join(d, "svg")
    if not os.path.isfile(os.path.join(d, "sprite.json")):
        return None
    sp = json.load(open(os.path.join(d, "sprite.json"), encoding="utf-8"))
    sp.pop("source", None)
    sp["_dir"] = os.path.relpath(os.path.join(d, "sprite"), base)
    return sp


def build_cast(meta, base):
    ids = [x.strip() for x in re.split(r"[,、\s]+", meta.get("cast", "zundamon, metan")) if x.strip()]
    chars_dir = meta.get("chars", "chars")
    cast = {}
    for i, cid in enumerate(ids):
        c = json.loads(json.dumps(PRESETS.get(cid, {"name": cid, "voice": {"engine": "browser"}})))
        if cid not in PRESETS:
            c["color"] = ["#3b82c4", "#d9772b", "#5fae45", "#d6538f"][i % 4]
        for k in ("name", "color", "side"):
            if meta.get("%s.%s" % (cid, k)):
                c[k] = meta["%s.%s" % (cid, k)]
        for d in (chars_dir, os.path.join(HERE, "chars")):   # 台本の隣に無ければ、スキルに集めた立ち絵。パーツの形（sprite.json）があればそちら
            sp, imgs = find_sprite(cid, base, d, meta.get("%s.art" % cid, meta.get("art", "svg"))), find_images(cid, base, d)
            if sp:
                c["sprite"] = sp
            elif imgs:
                c["images"] = imgs
            if sp or imgs:
                break
        if meta.get("%s.credit" % cid):
            c["image_credit"] = meta["%s.credit" % cid]
        # 立ち絵の大きさ: 型（style:）ごとの既定。頭だけの絵（ゆっくり）と全身の絵で別。変えるなら cast_height:・cast_offset:
        st = STYLES.get(meta.get("style", "talk"), STYLES["talk"])["cast"]
        sp0 = c.get("sprite")
        head = bool(sp0 and sp0["h"] / sp0["w"] < 1.3) or "height" in c
        hh, oy = st["head" if head else "stand"]
        if meta.get("style", "talk") == "talk" and "height" in c:
            hh, oy = c["height"], c.get("offsetY", 0)
        c["height"], c["offsetY"] = int(meta.get("cast_height", hh)), int(meta.get("cast_offset", oy))
        if cid in [x.strip() for x in re.split(r"[,、\s]+", meta.get("narrator", "")) if x.strip()]:
            c["hidden"] = True   # 語り手: 声だけで、立ち絵を出さない
        v = c.get("voice") or {}
        mult = float(meta.get("%s.speed" % cid) or meta.get("speed") or DEFAULT_SPEED)   # 話速（全体は speed:、1 人だけは <名前>.speed:）
        if v.get("engine") == "aquestalk":   # ゆっくりボイス。ライブラリを置いていなければ、ブラウザの読み上げで代わる
            import aquestalk
            v["yukkuri"] = True
            if aquestalk.backend(v.get("voice", "f1")):
                v["aq_speed"] = int(float(v.get("aq_speed", 100)) * mult / DEFAULT_SPEED)
            else:
                v["engine"] = "browser"
        if v.get("engine") == "voicevox":
            v["speed"] = round(float(v.get("speed", 1.0)) * mult, 3)
        elif v:
            v["rate"] = round(float(v.get("rate", 1.0)) * mult / DEFAULT_SPEED, 3)
        cast[cid] = c
    for cid, c in cast.items():   # 位置の決まっていない人は、空いている側へ
        if not c.get("side"):
            sides = [x.get("side") for x in cast.values()]
            c["side"] = "left" if sides.count("left") <= sides.count("right") else "right"
    if len(cast) > 1 and len({c["side"] for c in cast.values()}) == 1:   # 全員が同じ側なら、台本で位置を決めていない最後の人を反対へ
        for cid in reversed(list(cast)):
            if not meta.get("%s.side" % cid):
                cast[cid]["side"] = "right" if cast[cid]["side"] == "left" else "left"
                break
    for cid, c in cast.items():   # 横を向いた立ち絵（facing: left / right）は、画面の内側を向くように左右を返す
        f = meta.get("%s.facing" % cid) or c.get("facing")
        if f in ("left", "right") and "flip" not in c:
            c["flip"] = f == c["side"]
    return cast


def faces_of(c):
    """その立ち絵にある表情と、ポーズごとの表情。（表情の並び, {ポーズ: 表情の集まり}）。表情・ポーズの名前は smile#2・raise#2 の形も含む。"""
    if c.get("sprite"):
        poses = c["sprite"]["poses"]
        keys, by_pose = set(poses[""]["faces"]), {p: set(v["faces"]) for p, v in poses.items() if p}
    else:
        im = c.get("images") or {}
        keys, by_pose = {k for k in im if "@" not in k}, {}
        for k in im:
            if "@" in k:
                by_pose.setdefault(k.split("@", 1)[1], set()).add(k.split("@", 1)[0])
    order = lambda k: (FACES.index(k.split("#")[0]) if k.split("#")[0] in FACES else 99, k)
    return sorted(keys, key=order), by_pose


def label_counts(names):
    """["smile", "smile#2", "raise"] → "smile×2 raise" """
    seen = {}
    for n in names:
        seen[n.split("#")[0]] = seen.get(n.split("#")[0], 0) + 1
    return " ".join(k + ("×%d" % n if n > 1 else "") for k, n in seen.items())


class Chooser:
    """同じラベルの形の中から、使うたびに順に選ぶ（同じ形が続かないように）。"""
    def __init__(self):
        self.n = {}

    def pick(self, who, label, items):
        i = self.n.get((who, label), 0)
        self.n[(who, label)] = i + 1
        return items[i % len(items)]


def roles_of(meta, chapters):
    """解説役（台本の roles: か、いちばん多く話す人）と、聞き手。"""
    n = {}
    for ch in chapters:
        for sc in ch["scenes"]:
            for ln in sc.get("lines", []):
                n[ln["who"]] = n.get(ln["who"], 0) + len(ln["text"])
    ex = next((p.split("=")[0].strip() for p in re.split(r"[,、]", meta.get("roles", "")) if "解説" in p.split("=")[-1]), None)
    return ex if ex in n else (max(n, key=n.get) if n else None)


def auto_act(chapters, cast, explainer):
    """表情・体・動きのラベルが無いせりふに、せりふの中身から演技を付ける（控えめ。山場は台本で名指しする）。その立ち絵にあるラベルだけを使う。"""
    have, turn = {}, {}
    for cid, c in cast.items():
        faces, by_pose = faces_of(c) if (c.get("sprite") or c.get("images")) else (FACES, {})
        have[cid] = ({f.split("#")[0] for f in faces}, set().union(*[set(p.split("#")[0].split("+")) for p in by_pose]) if by_pose else set())
    for ch in chapters:
        for sc in ch["scenes"]:
            for ln in sc.get("lines", []):
                if ln.get("opts") or ln.get("face"):
                    continue
                who = ln["who"]
                role, key = ("E" if who == explainer else "L"), ln["text"] + (ln.get("emote") or "")
                i = turn[who] = turn.get(who, 0) + 1
                face, body, motion = next(((f, b, m) for pat, f, b, m, r in ACTING if r in ("", role) and re.search(pat, key)),
                                          (["normal", "smile-", "normal"][i % 3], "point" if role == "E" and i % 3 == 0 else "", ""))
                opts = [face] if OPT_RE.match(face).group(1) in have[who][0] else []
                if body in have[who][1] and i % 2:   # 体は 2 回に 1 回（同じ姿が続かないように）
                    opts.append(body)
                if motion:
                    opts.append(motion)
                if opts:
                    ln["opts"] = opts


def auto_react(chapters, cast, explainer):
    """相手の反応が書かれていないせりふに、聞いている側の小さな反応を足す（うなずく・驚く・考える・あきれる）。同じ反応を続けない。"""
    ids, n, last = list(cast), 0, None
    if len(ids) < 2:
        return
    have = {cid: ({f.split("#")[0] for f in faces_of(c)[0]} if (c.get("sprite") or c.get("images")) else set(FACES)) for cid, c in cast.items()}

    def fit(cid, opts):   # 無い表情は近いものに（自動で付ける分は、知らせずに代える）
        out = []
        for o in opts:
            m = OPT_RE.match(o)
            if m.group(1) in FACES and m.group(1) not in have[cid]:
                o = next((f for f in FALLBACK.get(m.group(1), []) if f in have[cid]), None)
            if o:
                out.append(o)
        return out
    for ch in chapters:
        for sc in ch["scenes"]:
            L = sc.get("lines", [])
            for i, ln in enumerate(L):
                if ln.get("react_raw") or len(ln["text"]) < 12:
                    continue
                who = ln["who"]
                other = next((x["who"] for x in reversed(L[:i]) if x["who"] != who), None) or next(c for c in ids if c != who)
                key, opts = ln["text"] + (ln.get("emote") or ""), []
                smug = any(OPT_RE.match(o).group(1) == "smug" for o in ln.get("opts", []))
                if who == explainer:
                    if re.search(r"\d\s*(倍|%|％|万|億|年|人|個)|実は|じつは|なんと|！？", key):
                        opts, at = ["surprised-"], .6
                    elif re.search(r"[？?]\s*$", key):
                        opts, at = ["think"], .7
                    elif n % 2 == 0:
                        opts, at = ["nod"], .82
                elif smug or re.search(r"全部わかった|平気|余裕|かんたん|簡単|完璧|ばっちり", key):
                    opts, at = ["doubt"], .6
                elif re.search(r"[？?]\s*$", key) and n % 3 == 0:
                    opts, at = ["smile-", "nod"], .75
                n += 1
                if not opts or opts == last:
                    last = None if opts == last else last
                    continue
                last = opts
                nxt = L[i + 1] if i + 1 < len(L) else None
                if nxt and nxt["who"] == other and opts[0].startswith("surprised") and re.search(r"^(えっ|ええ|まさか|うそ)|！？", nxt["text"] + (nxt.get("emote") or "")):
                    continue   # すぐ後に自分で驚くせりふがある
                ln["react_raw"] = [{"who": other, "opts": fit(other, opts), "at": at}]


def resolve_faces(chapters, cast):
    """せりふのラベル（表情・体・動き）を、その立ち絵にある形に当てる。せりふの途中の演技（acts）と相手の反応（react）も同じに。
    無いものは近いもので代わり、その旨を返す。使わない絵は埋め込まない。"""
    warns, used, choose = [], {}, Chooser()

    def warn(w):
        if w not in warns:
            warns.append(w)

    def resolve(who, opts, legacy_pose=None):
        c, out = cast[who], {}
        name, has_art = c.get("name", who), bool(c.get("sprite") or c.get("images"))
        faces, by_pose = faces_of(c) if has_art else ([], {})
        info = (c.get("sprite") or {}).get("info", {})
        tags_of = lambda p: set(p.split("#")[0].split("+"))
        body_tags = set().union(*[tags_of(p) for p in by_pose]) if by_pose else set()
        face_labels = {f.split("#")[0] for f in faces}
        want_face, want_tags = None, []
        for o in list(opts) + ([legacy_pose] if legacy_pose else []):
            m = OPT_RE.match(o)
            lab, num, lv = m.group(1), m.group(2), m.group(3)
            if lab in MOTIONS:
                out["motion"] = lab
                if lv:
                    out["mlv"] = 3 if lv == "+" else 1
            elif lab in POSES or lab in ITEMS or lab in body_tags:
                want_tags.append(lab + (num or ""))
            elif lab in FACES or lab in face_labels or want_face is None:
                want_face = (lab, num, lv)
            else:
                warn("%s の（%s）は、表情・体・動きのどれでもありません（--list-casts で確かめる）" % (name, o))
        lab, num, lv = want_face or ("normal", None, None)
        if not has_art:   # 仮のキャラクター
            out["face"] = lab
            return out
        # 表情: ラベル → その立ち絵にある形
        if lab not in face_labels:
            alt = next((f for f in FALLBACK.get(lab, []) if f in face_labels), "normal")
            warn("%s に表情 %s がありません → %s で代わります（ある表情: %s）" % (name, lab, alt, label_counts(faces)))
            lab, num = alt, None
        forms = [f for f in faces if f.split("#")[0] == lab]
        if num and lab + num in forms:
            face = lab + num
        elif num and num == "#1":
            face = lab
        else:
            if num:
                warn("%s の %s%s はありません → %s の中から選びます（%d 通り）" % (name, lab, num, lab, len(forms)))
            if lv:
                goal = 3 if lv == "+" else 1
                level = lambda f: (info.get("faces", {}).get(f) or {}).get("lv", 2)
                best = min(abs(level(f) - goal) for f in forms)
                forms = [f for f in forms if abs(level(f) - goal) == best]
            face = choose.pick(who, lab + (lv or ""), forms)
        lvl = (info.get("faces", {}).get(face) or {}).get("lv", 2)
        if lvl != 2:
            out["lv"] = lvl
        # 体: ポーズと持ち物のラベル → その両方を持つ体（無ければ、多く当てはまる体）
        pose = None
        if want_tags:
            T = {t.split("#")[0] for t in want_tags}
            named = [t for t in want_tags if "#" in t and t in by_pose]
            exact = [p for p in by_pose if tags_of(p) == T]
            more = [p for p in by_pose if tags_of(p) > T]
            part = sorted((p for p in by_pose if tags_of(p) & T), key=lambda p: -len(tags_of(p) & T))
            part = [p for p in part if len(tags_of(p) & T) == len(tags_of(part[0]) & T)] if part else []
            if named:
                pose = named[0]
            else:
                cands = exact or more or part
                if cands:
                    pose = choose.pick(who, "+".join(sorted(T)), cands)
                miss = T - (tags_of(pose) if pose else set())
                if miss:
                    warn("%s に体のラベル %s がありません → %s（ある体: %s）" % (name, "・".join(sorted(miss)), "%s にします" % pose if pose else "いつもの姿にします",
                                                                         label_counts(sorted(by_pose)) or "なし"))
            if pose and face not in by_pose[pose]:
                pose = None
        if c.get("sprite"):
            out["face"], out["pose"] = face, pose or ""
        else:
            out["face"] = face + ("@" + pose if pose else "")
        used.setdefault(who, {("", "normal")}).add((pose or "", face))
        return out

    for ch in chapters:
        for sc in ch["scenes"]:
            for ln in sc.get("lines", []):
                who = ln["who"]
                first = [ln.pop("face")] if ln.get("face") else []   # JSON を直接書いた台本など
                r = resolve(who, first + ln.pop("opts", []), ln.pop("pose", None))
                if not r.get("pose"):
                    r.pop("pose", None)
                ln.update(r)
                for a in ln.pop("acts_raw", []):
                    ln.setdefault("acts", []).append(dict(resolve(who, a["opts"]), at=a["at"]))
                for a in ln.pop("react_raw", []):
                    if a["who"] not in cast or a["who"] == who:
                        warn("反応（> %s）の相手が cast にいないか、話し手と同じです" % a["who"])
                        continue
                    d = dict(resolve(a["who"], a["opts"]), who=a["who"], at=a["at"])
                    if a.get("emote"):
                        d["emote"] = a["emote"]
                    ln.setdefault("react", []).append(d)
    for cid, c in cast.items():   # 台本で使う絵だけを埋め込む（HTML が大きくなるのを防ぐ）
        use = used.get(cid, {("", "normal")})
        if c.get("sprite"):
            sp, poses = c["sprite"], {}
            for pose, face in sorted(use):
                P = poses.setdefault(pose, {"base": sp["poses"][pose]["base"], "faces": {}})
                P["faces"][face] = sp["poses"][pose]["faces"][face]
                P["faces"].setdefault("normal", sp["poses"][pose]["faces"].get("normal", {}))
            keys = {P["base"] for P in poses.values()} | {p[0] for P in poses.values() for f in P["faces"].values() for p in f.values()}
            c["sprite"] = {"w": sp["w"], "h": sp["h"], "poses": poses, "images": {k: os.path.join(sp["_dir"], k + (".svg" if sp.get("svg") else ".png")) for k in sorted(keys)}}
        elif c.get("images"):
            names = {f + ("@" + p if p else "") for p, f in use}
            c["images"] = {f: v for f, v in c["images"].items() if f in names}
    return warns


def list_casts(only=None):
    """登場人物のプリセットと、立ち絵にある表情・体。名前を付けると、形ごとの説明と度合いまで出す。"""
    if only:
        if only not in PRESETS:
            sys.exit("error: プリセットに %s はありません（--list-casts で一覧）" % only)
        v, sp = PRESETS[only], find_sprite(only, HERE, "chars")
        print("# %s（%s）" % (only, v["name"]))
        if not sp:
            imgs = find_images(only, HERE, "chars")
            print("  表情: %s" % (label_counts(faces_of({"images": imgs})[0]) or "立ち絵がありません（仮のキャラクターで描く）"))
            return
        info, lvname = sp.get("info", {}), {1: "控えめ", 2: "ふつう", 3: "強め"}
        print("## 表情（ラベル: 説明。その下は形ごとの 名前・度合い・中身）")
        faces = list(sp["poses"][""]["faces"])
        for lab in dict.fromkeys(f.split("#")[0] for f in faces):
            print("  %-10s %s" % (lab, LABELS["faces"].get(lab, "")))
            for f in [f for f in faces if f.split("#")[0] == lab]:
                m = info.get("faces", {}).get(f, {})
                print("      %-13s %-4s %s" % (f, lvname[m.get("lv", 2)], m.get("desc", "")))
        poses = [p for p in sp["poses"] if p]
        print("## 体（ポーズ・持ち物）")
        for p in poses:
            tags = p.split("#")[0].split("+")
            print("  %-13s %s ｜ %s" % (p, " ＋ ".join(LABELS["poses"].get(t) or LABELS["items"].get(t) or t for t in tags), info.get("poses", {}).get(p, {}).get("desc", "")))
        if not poses:
            print("  （いつもの姿だけ）")
        return
    print("# ラベル（台本の 話し手(…) に、表情・体・動きから 1 つずつ並べる。例: zundamon(smile+, raise, jump)）")
    for title, key in (("表情", "faces"), ("度合い", "levels"), ("体: ポーズ", "poses"), ("体: 持ち物（ある立ち絵だけ）", "items"), ("動き", "motions")):
        print("## %s" % title)
        for k, d in LABELS[key].items():
            print("  %-10s %s" % (k or "（なし）", d))
    print("# 登場人物のプリセット（台本の cast: に並べる。形ごとの説明は --list-casts <名前>）")
    for k, v in PRESETS.items():
        print("  %-9s %-8s 声: %-9s %s" % (k, v["name"], (v.get("voice") or {}).get("engine", "-"), v.get("note", v.get("credit", ""))))
        sp, imgs = find_sprite(k, HERE, "chars"), find_images(k, HERE, "chars")
        faces, by_pose = faces_of({"sprite": sp} if sp else {"images": imgs})
        if faces:   # スキルに集めた立ち絵にある表情と体（×数字は、そのラベルの形の数）
            print("            表情: %s%s" % (label_counts(faces), "   体: " + label_counts(sorted(by_pose)) if by_pose else ""))


# ──────────────────────────────────────────────────────────────────────────
# 声（VOICEVOX・用意した WAV）
# ──────────────────────────────────────────────────────────────────────────
def speakable(text, pronounce):
    """読み上げに渡す文。読みを置き換え、数字と前後の文字の間の空白を詰める（「1859 年」を「…きゅう、とし」と読ませない）。字幕は元のまま。"""
    text = text.replace("**", "")
    for k in sorted(pronounce, key=len, reverse=True):
        text = text.replace(k, pronounce[k])
    text = re.sub(r"(?<=\d)[ \u3000]+(?=[^\s\dA-Za-z])", "", text)
    return re.sub(r"(?<=[^\x00-\x7f])[ \u3000]+(?=\d)", "", text)


# 表情 → 声のスタイル（その話者に、左から順に最初にあったもの）。台本の先頭の voice_style: off で止める
VOICE_STYLES = {"angry": ["ツンツン", "おこ", "怒り"], "sad": ["なみだめ", "かなしみ", "悲しみ", "かなしい"], "sad+": ["なみだめ", "ヘロヘロ"], "shy": ["あまあま", "照れ"],
                "love": ["あまあま"], "dizzy": ["ヘロヘロ"], "troubled+": ["ヘロヘロ", "なみだめ"], "smile+": ["よろこび", "喜び", "たのしい", "楽しい"], "surprised+": ["びっくり", "驚き"]}


def voicevox_lines(spec, url, outdir, pronounce, styles=True):
    """VOICEVOX でせりふの WAV を作る（同じ話者・同じ文は作り直さない）。作った数を返す。VOICEVOX との通信は motion-video の voice.py。"""
    sys.path.insert(0, os.path.join(HERE, "..", "motion-video"))
    import voice, aquestalk
    vv, aq = voice.Voicevox(url), aquestalk.AquesTalk(url)
    for ch in spec["chapters"]:
        for sc in ch["scenes"]:
            for ln in talk_lines(sc):
                v = (spec["cast"].get(ln["who"], {}).get("voice") or {})
                if v.get("engine") == "aquestalk" and not ln.get("voice"):   # ゆっくりボイス（読みは VOICEVOX に聞く）
                    ln["voice"] = aq.synth(speakable(ln["text"], pronounce), v, outdir)
                    vv.made += aq.made
                    aq.made = 0
                    continue
                if v.get("engine") != "voicevox" or ln.get("voice"):
                    continue
                text = speakable(ln["text"], pronounce)
                style = ln.get("style")   # 声のスタイル: 名指し（voice:ささやき）か、表情に合うもの（その話者にあるときだけ）
                if not style and styles:
                    lab = OPT_RE.match(str(ln.get("face", "normal")).split("@")[0].split("#")[0]).group(1)
                    key = lab + ("+" if ln.get("lv") == 3 else "")
                    style = next((x for x in VOICE_STYLES.get(key, []) + VOICE_STYLES.get(lab, []) if (v.get("speaker"), x) in vv.ids), None)
                if style and (v.get("speaker"), style) not in vv.ids:
                    print("warn: %s に声のスタイル「%s」はありません（speakers.md）" % (v.get("speaker"), style), file=sys.stderr)
                    style = None
                v2 = dict(v, style=style) if style else v
                if ln.get("big") or ln.get("lv") == 3:
                    v2 = dict(v2, intonation=round(float(v.get("intonation", 1.0)) * 1.25, 2))   # 山場は抑揚を大きく
                ln["voice"] = vv.synth(text, v2, outdir)
    return vv.made


def readings(spec, url, pronounce):
    """VOICEVOX がせりふをどう読むか（かな。' はアクセントの位置、/ と 、 は区切り）を出す。声を作る前に、読み間違いを見つけるため。"""
    import urllib.parse, urllib.request
    try:
        speakers = json.loads(urllib.request.urlopen(url + "/speakers", timeout=10).read())
    except OSError as e:
        sys.exit("error: VOICEVOX につながりません（%s）: %s" % (url, e))
    ids = {(sp["name"], st["name"]): st["id"] for sp in speakers for st in sp["styles"]}
    for ch in spec["chapters"]:
        for sc in ch["scenes"]:
            for ln in talk_lines(sc):
                c = spec["cast"].get(ln["who"], {})
                v = c.get("voice") or {}
                sid = ids.get((v.get("speaker"), v.get("style", "ノーマル")))
                if v.get("engine") != "voicevox" or sid is None:
                    continue
                text = speakable(ln["text"], pronounce)
                req = urllib.request.Request(url + "/audio_query?" + urllib.parse.urlencode({"text": text, "speaker": sid}), data=b"", method="POST")
                kana = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("kana", "")
                print("%s: %s\n    → %s" % (c.get("name", ln["who"]), ln["text"], kana))


def yukkuri_bat(spec, stem, pronounce):
    """ゆっくりボイスのせりふを、Windows の AquesTalkPlayer（個人・非営利は無償）で WAV にするバッチファイルを書く。
    実行すると <台本名>_yukkuri/ に、せりふの順に 001_reimu.wav … ができる。それを --voices-dir で渡す。"""
    name = os.path.basename(stem)
    rows = []
    for ch in spec["chapters"]:
        for sc in ch["scenes"]:
            for ln in talk_lines(sc):
                v = spec["cast"].get(ln["who"], {}).get("voice") or {}
                if v.get("yukkuri") and not ln.get("voice"):
                    text = speakable(ln["text"], pronounce).replace('"', "").replace("%", "パーセント").replace("〜", "ー").replace("～", "ー")
                    text = text.encode("cp932", "ignore").decode("cp932").strip()
                    rows.append((ln["who"], v.get("preset", ""), text))
    if not rows:
        return None, 0
    out = ["@echo off", "rem ゆっくりボイスの WAV を作る（AquesTalkPlayer を使う。個人・非営利は無償。https://www.a-quest.com/products/aquestalkplayer.html）",
           "rem 1. 下の PLAYER を、AquesTalkPlayer.exe を置いた場所に直す  2. このファイルをダブルクリックする  3. できた %s_yukkuri フォルダを --voices-dir で渡す" % name,
           'set "PLAYER=C:\\AquesTalkPlayer\\AquesTalkPlayer.exe"', 'set "OUT=%%~dp0%s_yukkuri"' % name,
           'if not exist "%PLAYER%" ( echo AquesTalkPlayer.exe が見つかりません: %PLAYER% & echo このファイルの PLAYER= の行を直してください & pause & exit /b 1 )',
           'if not exist "%OUT%" mkdir "%OUT%"']
    for i, (who, preset, text) in enumerate(rows, 1):
        out.append('echo %d / %d' % (i, len(rows)))
        out.append('start "" /wait "%%PLAYER%%" /T "%s"%s /W "%%OUT%%\\%03d_%s.wav"' % (text, ' /P "%s"' % preset if preset else "", i, who))
    out += ["echo 終わりました。%d 個の WAV ができています: %%OUT%%" % len(rows), "pause"]
    path = stem + "_yukkuri.bat"
    open(path, "w", encoding="cp932", newline="\r\n").write("\n".join(out) + "\n")
    return path, len(rows)


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


def _lowpass_taps(r0, rate, n=95):
    """新しい周波数の半分より上を落とす係数（窓をかけた sinc）。落とさずに間引くと、高い音が折り返して雑音になる（サ行の多い声で目立つ）。"""
    import math
    fc, mid = 0.46 * rate / r0, (n - 1) / 2
    h = [(2 * fc if i == mid else math.sin(2 * math.pi * fc * (i - mid)) / (math.pi * (i - mid)))
         * (0.42 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) + 0.08 * math.cos(4 * math.pi * i / (n - 1))) for i in range(n)]
    g = sum(h)
    return [v / g for v in h]


def resample_wav(src, dst, rate):
    """WAV（16 ビット）を低いサンプリング周波数に直す（HTML を小さくするため）。先に高い音を落としてから間引く。"""
    import array, wave
    w = wave.open(src)
    ch, sw, r0, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    data = w.readframes(n)
    w.close()
    if sw != 2 or r0 <= rate:
        return src
    a = array.array("h", data)[::ch]   # 1 つ目のチャンネルだけを使う（声は 1 チャンネル）
    taps = _lowpass_taps(r0, rate)
    half, m = len(taps) // 2, int(len(a) * rate / r0)
    try:
        import numpy as np
        x = np.convolve(np.asarray(a, dtype=np.float64), np.asarray(taps), mode="same")
        y = np.interp(np.arange(m) * (r0 / rate), np.arange(len(x)), x)
        out = array.array("h", np.clip(np.rint(y), -32768, 32767).astype(np.int16).tolist())
    except ImportError:   # numpy の無い環境: 要る位置だけを計算する（遅いが、結果は同じ）
        pad = [0] * half + list(a) + [0] * (half + 2)
        step, out = r0 / rate, array.array("h")
        whole = abs(step - round(step)) < 1e-9
        for i in range(m):
            pos = i * step
            j = int(pos)
            v = sum(t * q for t, q in zip(taps, pad[j:j + len(taps)]))
            if not whole and pos > j:   # 間の位置は、となりの値との間を線で補う
                v += (sum(t * q for t, q in zip(taps, pad[j + 1:j + 1 + len(taps)])) - v) * (pos - j)
            out.append(max(-32768, min(32767, int(round(v)))))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    w = wave.open(dst, "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(out.tobytes())
    w.close()
    return dst


def compact(spec, base, stem, rate=16000, width=1280):
    """HTML を小さくする: 声を 16kHz に、背景と黒板の写真を幅 1280 の JPEG に直した写しを <台本名>_compact/ に作り、そちらを使う。"""
    out, done = stem + "_compact", {}

    def image(path):
        if not path or not re.search(r"\.(jpe?g|png|webp)$", path, re.I) or not os.path.isfile(os.path.join(base, path)):
            return path
        if path not in done:
            from PIL import Image
            im = Image.open(os.path.join(base, path))
            if im.mode in ("RGBA", "LA", "P") and "transparency" in im.info or im.mode in ("RGBA", "LA"):
                done[path] = path   # 透明のある絵はそのまま
            else:
                im = im.convert("RGB")
                if im.width > width:
                    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
                os.makedirs(out, exist_ok=True)
                dst = os.path.join(out, re.sub(r"[^\w.-]", "_", os.path.splitext(path)[0])[-60:] + ".jpg")
                im.save(dst, quality=74, optimize=True)
                done[path] = os.path.relpath(dst, base) if os.path.getsize(dst) < os.path.getsize(os.path.join(base, path)) else path
        return done[path]

    for k, pth in list(spec.get("_image_paths", {}).items()):
        if pth.lower().endswith((".jpg", ".jpeg")):
            spec["_image_paths"][k] = os.path.join(base, image(os.path.relpath(pth, base)))
    for ch in spec["chapters"]:
        for sc in ch["scenes"]:
            if isinstance(sc.get("bg"), str):
                sc["bg"] = image(sc["bg"])
            b = sc.get("board")
            if isinstance(b, dict) and b.get("type") == "image":
                b["src"] = image(b.get("src"))
            for ln in talk_lines(sc):
                v = ln.get("voice")
                if v and v.lower().endswith(".wav"):
                    src = v if os.path.isabs(v) else os.path.join(base, v)
                    ln["voice"] = resample_wav(src, os.path.join(out, "voices", os.path.basename(v)), rate)


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
    credits += ["BGM: " + c if not re.match(r"^(BGM|音楽)", c) else c for c in meta.get("_music_credits", [])]   # カタログの BGM・背景（自動）
    if meta.get("_bg_credits"):
        credits.append("背景: " + "／".join(meta["_bg_credits"]))
    img = meta.get("_img_credits", [])   # fetch_images.py で取った画像（images/credits.json）。締めの画面には短い形を、数行にまとめて出す
    line = ""
    for c in {x["short"]: x for x in img}.values():
        if line and len(line) + len(c["short"]) > 46:
            credits.append("画像: " + line)
            line = ""
        line += ("／" if line else "") + c["short"]
    if line:
        credits.append("画像: " + line)
    for k in ("bg_credit", "credit"):
        if meta.get(k):
            credits.append(meta[k])
    return credits


def asset(name, catalog, sub, base, credits):
    """カタログの名前（classroom_evening・monkeys など）なら、スキルの bg/・bgm/ のファイルに当て、クレジットを覚える。そのほかはそのまま返す。"""
    e = catalog.get(name) if not name.startswith("_") else None
    if not e:
        return name
    path = os.path.join(HERE, sub, e["file"])
    if not os.path.isfile(path) and e.get("embed") is False:
        sys.exit("error: %s/%s がありません。この曲は自動では取れません（配布元の規約）。ブラウザで %s から取り、%s という名前で置いてください"
                 % (sub, e["file"], e["page"], path))
    if not os.path.isfile(path):
        sys.exit("error: %s/%s がありません。python3 %s で取り直してください" % (sub, e["file"], os.path.join(HERE, "fetch_assets.py")))
    if e["credit"] and e["credit"] not in credits:
        credits.append(e["credit"])
    if e.get("embed") is False and name not in WEBM_ONLY:
        WEBM_ONLY.append(name)
    return os.path.relpath(path, base)


IMG_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}


def stage_images(meta, chapters, base):
    """@show の絵の名前を、ファイルに当てる（台本の隣か images/。拡張子は省ける）。{名前: パス} と、見つからなかった名前を返す。
    写真（JPEG）は白い縁を付け、取ってきた絵のクレジット（credits.json）を覚える。"""
    table, missing, dirs = {}, [], ["", meta.get("images", "images")]
    for ch in chapters:
        for sc in ch["scenes"]:
            b = sc.get("board")
            if not (isinstance(b, dict) and b.get("type") == "stage"):
                continue
            for shot in b["shots"]:
                for it in shot["items"]:
                    dref = it.pop("draw_ref", None)
                    if dref:   # 描き下ろし: 台本の隣か scenes/ の <名前>.js（custom と同じ (ctx, lt, d, H, s) の本体）
                        cands = [os.path.join(base, d, dref + e) for d in ("", "scenes") for e in ("", ".js")]
                        path = next((c for c in cands if os.path.isfile(c)), None)
                        if not path:
                            sys.exit("error: @show の draw:%s の JS が見つかりません（%s か scenes/%s.js に置く）" % (dref, dref + ".js", dref))
                        it["draw"] = open(path, encoding="utf-8").read()
                        continue
                    ref = it.pop("ref", None)
                    if ref is None:
                        continue
                    cands = [os.path.join(base, d, ref + e) for d in dirs for e in [""] + list(IMG_MIME)]
                    path = next((c for c in cands if os.path.isfile(c) and os.path.splitext(c)[1].lower() in IMG_MIME), None)
                    if not path:
                        missing.append(ref)
                        it["text"] = it.pop("label", ref)
                        continue
                    key = re.sub(r"[^\w\-]", "_", os.path.splitext(os.path.relpath(path, base))[0])
                    table[key] = path
                    it["img"] = key
                    ext = os.path.splitext(path)[1].lower()
                    it.setdefault("frame", ext in (".jpg", ".jpeg"))
                    cj = os.path.join(os.path.dirname(path), "credits.json")
                    e = json.load(open(cj, encoding="utf-8")).get(os.path.basename(path)) if os.path.isfile(cj) else None
                    if e and e.get("from") == "いらすとや":   # 商用は 1 つの制作物に 20 点まで・素材としての再配布は不可（irasutoya スキル）
                        meta.setdefault("_irasutoya", set()).add(e.get("source") or path)
                    if e:
                        if not any(x["full"] == e["full"] for x in meta.setdefault("_img_credits", [])):
                            meta["_img_credits"].append(e)
                        if it["frame"]:   # 写真は、出どころを絵の右下にも出す
                            it["credit"] = shot.pop("credit", None) or "画像: " + e["short"]
    return table, missing


def embed_font(name, text):
    """字幕の書体（fonts.json の名前）を、使う字だけにして埋め込む形にする。fontTools が無ければ None（OS の書体で描く）。"""
    cat = json.load(open(os.path.join(HERE, "fonts.json"), encoding="utf-8"))
    path = os.path.join(HERE, "fonts", cat.get(name, {}).get("file", "-"))
    if not os.path.isfile(path):
        print("warn: 書体 %s がありません（python3 %s --only fonts）。OS の書体で描きます" % (name, os.path.join(HERE, "fetch_assets.py")), file=sys.stderr)
        return None
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
    except ImportError:
        print("warn: fontTools がありません（pip install fonttools）。字幕は OS の書体で描きます", file=sys.stderr)
        return None
    import base64, io
    font = TTFont(path)
    opt = subset.Options()
    opt.layout_features = []
    opt.name_IDs = [1, 2]
    opt.notdef_outline = True
    sub = subset.Subsetter(opt)
    sub.populate(text="".join(sorted(set(text))) + " 0123456789!?！？…♪zZ")
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff"
    font.save(buf)
    return {"family": "MVCast", "src": "data:font/woff;base64," + base64.b64encode(buf.getvalue()).decode("ascii"), "weight": 800}


def all_text(spec):
    """画面に出る文字ぜんぶ（書体を、使う字だけにするため）。"""
    out = [spec.get("title", "")] + [c.get("name", "") for c in spec["cast"].values()]

    def walk(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in ("voice", "src", "img", "bg", "_env", "face", "pose", "motion", "who", "se"):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(spec["chapters"])
    return "".join(out)


def to_spec(meta, chapters, cast, base):
    bg_credits, music_credits = meta.setdefault("_bg_credits", []), meta.setdefault("_music_credits", [])
    vol = float(meta.get("music_volume", .3))

    def music_of(name):
        name = asset(name, BGMS, "bgm", base, music_credits)
        return {"file": name, "volume": vol} if re.search(r"\.(mp3|m4a|ogg|wav)$", name, re.I) else name

    music = music_of(meta.get("music", "none"))
    for ch in chapters:
        if ch.get("music"):
            ch["music"] = music_of(ch["music"])
    spec = {"title": meta.get("title", "解説"), "description": meta.get("description", ""), "lang": "ja",
            "player": meta.get("player", "studio"), "theme": meta.get("theme", "daylight"), "castAlways": True,
            "transition": meta.get("transition", "slide"),
            "audio": {"narration": True, "music": music, "duck": .35, "sfx": {"kit": meta.get("kit", "playful"), "density": meta.get("density", "low")},
                      "pronounce": json.loads(meta["pronounce"]) if meta.get("pronounce", "").startswith("{") else {}},
            "cast": cast, "chapters": chapters}
    if meta.get("motion"):
        spec["motion"] = meta["motion"]
    if meta.get("cast_motion", "yes").lower() in ("no", "off", "false"):   # 立ち絵の動き（呼吸・弾み・身ぶり）を止める
        spec["castMotion"] = False
    off = lambda k: meta.get(k, "").lower() in ("off", "no", "false")
    talk = {"caption": meta.get("subtitle", "outline")}   # 字幕: outline（箱なし。白い字にキャラ色の太い縁）か box（白い箱）
    if meta.get("subtitle_name"):
        talk["name"] = not off("subtitle_name")
    if meta.get("subtitle_size"):
        talk["size"] = int(meta["subtitle_size"])
    if off("relax"):
        talk["relax"] = False
    if off("se"):
        talk["sfx"] = False
    talk.update(json.loads(json.dumps(STYLES[meta.get("style", "talk")]["talk"])))
    if talk["caption"] in ("bar", "band", "strip"):   # 置きっぱなしの字幕: 全身の立ち絵にかからない幅で折り返す
        wide = max([0] + [c["height"] * c["sprite"]["w"] / c["sprite"]["h"] for c in cast.values() if c.get("sprite") and not c.get("hidden") and c["sprite"]["h"] / c["sprite"]["w"] >= 1.3])
        if wide:
            talk["capWidth"] = int(1920 - 2 * (wide * .8 + 40))
    spec["talk"] = talk
    spec["chrome"] = False   # 章の表示は、左上の札（tag）で出す
    if not off("tags"):
        for ci, ch in enumerate(chapters):
            for sc in ch["scenes"]:
                if "tag" not in sc and ci > 0 and sc.get("type") == "talk":
                    sc["tag"] = ch["title"]
    # 一瞬だけ出る人（cameo:）は、自分が話すか反応する場面だけ画面に出す
    cameos = [x.strip() for x in re.split(r"[,、\s]+", meta.get("cameo", "")) if x.strip() in cast]
    if cameos:
        regular = [k for k in cast if k not in cameos]
        for k in cameos:
            cast[k]["cameo"] = True
        for ch in chapters:
            for sc in ch["scenes"]:
                if sc.get("type") != "talk":
                    continue
                inn = {ln.get("who") for ln in sc.get("lines", []) if isinstance(ln, dict)} | {r.get("who") for ln in sc.get("lines", []) if isinstance(ln, dict) for r in ln.get("react") or []}
                sc["cast"] = regular + [k for k in cameos if k in inn]
    if "name" not in talk and len([c for c in cast.values() if not c.get("hidden")]) >= 3:   # 3 人以上: 字幕に名前を出す（誰のせりふか分かるように）
        talk["name"] = True
    if meta.get("chapter_tag") == "corner":   # 列挙・物語の型: 章の題を、右上の札に出す（1 章目は導入なので出さない）
        for ci, ch in enumerate(chapters):
            for sc in ch["scenes"]:
                if sc.get("type") == "talk" and ci > 0:
                    if sc.get("tag") == ch["title"]:
                        sc.pop("tag")
                    sc.setdefault("corner", "%d. %s" % (ci, ch["title"]) if meta.get("style") == "list" and ci < len(chapters) - 1 and not re.match(r"^[\d①-⑳第]", ch["title"]) else ch["title"])
    spec["_image_paths"], missing = stage_images(meta, chapters, base)
    for ref in dict.fromkeys(missing):
        print("warn: @show の絵「%s」が見つかりません（illust.py get か fetch_images.py get で取る）。名前だけを文字で出します" % ref, file=sys.stderr)
    for ch in chapters:
        for sc in ch["scenes"]:
            if meta.get("bg") and not sc.get("bg"):
                sc["bg"] = meta["bg"]
            if sc.get("bg"):
                sc["bg"] = asset(sc["bg"], BGS, "bg", base, bg_credits)
            b = sc.get("board")
            if isinstance(b, dict) and b.get("type") == "image" and b.get("src"):   # 取ってきた画像なら、クレジットを覚える
                cj = os.path.join(os.path.dirname(os.path.join(base, b["src"])), "credits.json")
                e = json.load(open(cj, encoding="utf-8")).get(os.path.basename(b["src"])) if os.path.isfile(cj) else None
                if e and e not in meta.setdefault("_img_credits", []):
                    meta["_img_credits"].append(e)
                if e and not b.get("caption"):
                    b["caption"] = e.get("title", "")
    credits = make_credits(meta, cast, False)
    if meta.get("end", "yes") != "no":
        chapters.append({"title": "おわりに", "scenes": [{"type": "end", "title": meta.get("end_title", "ご視聴ありがとうございました"),
                                                           "lines": credits[:9], "narration": ""}]})
    return spec, credits


def load_spec(script):
    """台本（テキスト）を読み、登場人物と演技を決めて、motion-video の台本にする（声はまだ当てない）。誤りがあれば止める。
    返り値は (設定, 台本, 登場人物, クレジット, 台本のあるフォルダ)。"""
    base = os.path.dirname(os.path.abspath(script))
    meta, chapters, errs = parse(open(script, encoding="utf-8").read())
    for e in errs:
        print("error:", e, file=sys.stderr)
    if errs:
        sys.exit(1)
    if meta.get("style", "talk") not in STYLES or meta.get("style", "talk").startswith("_"):
        sys.exit("error: style: %s はありません（%s）" % (meta["style"], "・".join(k for k in STYLES if not k.startswith("_"))))
    for k, v in STYLES[meta.get("style", "talk")]["meta"].items():   # 型の既定（台本に書いた設定が勝つ）
        meta.setdefault(k, v)
    cast = build_cast(meta, base)
    unknown = sorted({ln["who"] for ch in chapters for sc in ch["scenes"] for ln in sc.get("lines", [])} - set(cast))
    if unknown:
        sys.exit("error: cast に無い話し手: %s（台本の先頭の cast: に足してください）" % "、".join(unknown))
    if meta.get("acting", "auto").lower() not in ("off", "no", "false"):
        auto_act(chapters, cast, roles_of(meta, chapters))
    if meta.get("react", "auto").lower() not in ("off", "no", "false"):
        auto_react(chapters, cast, roles_of(meta, chapters))
    for w in resolve_faces(chapters, cast):
        print("warn:", w, file=sys.stderr)
    spec, credits = to_spec(meta, chapters, cast, base)
    return meta, spec, cast, credits, base


def make_spec(script, voicevox=False, voicevox_url="http://127.0.0.1:50021", voices_dir=None, compact_html=False, voice_rate=16000):
    """台本（テキスト）から motion-video の台本を作り、声を当て、確かめ、時間割を決める。誤りがあれば止める。
    返り値は (台本, motion-video の build, 登場人物, クレジット)。video-export スキル（書き出し）もこれで読む。
    途中の台本は <台本名>.json、章の時刻とクレジットは <台本名>.info.json に書く。"""
    meta, spec, cast, credits, base = load_spec(script)
    stem = os.path.splitext(os.path.abspath(script))[0]
    if voicevox:
        n = voicevox_lines(spec, voicevox_url, stem + "_voices", spec["audio"]["pronounce"], meta.get("voice_style", "auto").lower() not in ("off", "no", "false"))
        print("VOICEVOX: %d 個のせりふの声を作りました（作り済みは使い回し）" % n)
    credits = make_credits(meta, cast, voicevox)
    sc_ = sample_credit(spec)
    if sc_:
        credits.append(sc_)
    last = spec["chapters"][-1]["scenes"][-1]
    if last.get("type") == "end":
        last["lines"] = credits[:9]
    if voices_dir:
        used, have = assign_voice_files(spec, os.path.join(base, voices_dir) if not os.path.isabs(voices_dir) else voices_dir)
        print("WAV: %d 個をせりふに当てました（フォルダに %d 個）" % (used, have))
    if compact_html:
        compact(spec, base, stem, voice_rate)
    import base64   # @show の絵は、名前の表（images）に 1 回ずつ埋め込む
    spec["images"] = {k: "data:%s;base64,%s" % (IMG_MIME[os.path.splitext(p)[1].lower()], base64.b64encode(open(p, "rb").read()).decode("ascii"))
                      for k, p in spec.pop("_image_paths").items()}
    fname = meta.get("font", "rounded")
    if fname.lower() not in ("off", "no", "none", "os"):
        f = embed_font(fname, all_text(spec) + "".join(credits))
        if f:
            spec["fonts"], spec["talk"]["font"] = [f], f["family"]
            if meta.get("text_font", "").lower() in ("same", "yes", "on"):
                spec["textFont"] = f["family"]
    for ch in spec["chapters"]:
        for sc in ch["scenes"]:
            for ln in talk_lines(sc):
                if ln.get("voice") and os.path.isabs(ln["voice"]):
                    ln["voice"] = os.path.relpath(ln["voice"], base)
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
    total = sum(s["_dur"] for ch in spec["chapters"] for s in ch["scenes"])
    t, marks = 0, []
    for ch in spec["chapters"]:
        marks.append({"at": mv.fmt(t), "title": ch["title"]})
        t += sum(s["_dur"] for s in ch["scenes"])
    ira = len(meta.get("_irasutoya", ()))
    if ira:
        print("warn: いらすとやの絵を %d 点使っています。素材としての再配布は不可なので、この HTML は手元だけで使い、「WebM で保存」した動画を配ってください%s"
              % (ira, "。商用（収益化した動画）は 1 本 20 点まで（サムネイルを含む）。点数を減らすか、有償の利用を問い合わせる" if ira > 20 else "（収益化するなら、サムネイルと合わせて 20 点まで）"), file=sys.stderr)
    info = {"title": spec["title"], "length": mv.fmt(total), "chapters": marks, "credits": credits, "images": list({x["full"]: x for x in meta.get("_img_credits", [])}.values()),
            "cast": [{"id": k, "name": c.get("name", k)} for k, c in cast.items()], "facts": meta.get("facts", ""), "webm_only": WEBM_ONLY + (["いらすとやの絵"] if meta.get("_irasutoya") else []),
            "irasutoya": len(meta.get("_irasutoya", ())),
            "lines": sum(len(talk_lines(s)) for ch in spec["chapters"] for s in ch["scenes"])}
    json.dump(info, open(stem + ".info.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)   # 公開まわり（yukkuri-publish）が読む
    return spec, mv, cast, credits


def facing_sheet(out):
    """立ち絵ごとに、左に置いた姿と右に置いた姿を並べる（facing: left・right があれば、画面の内側を向くように返した後の姿）。"""
    from PIL import Image, ImageDraw
    ids = sorted(d for d in os.listdir(os.path.join(HERE, "chars")) if os.path.isfile(os.path.join(HERE, "chars", d, "normal.png")))
    W, H, cols = 300, 300, 6
    sheet = Image.new("RGB", (W * cols, (H + 24) * ((len(ids) + cols - 1) // cols)), "#8aa6b8")
    d = ImageDraw.Draw(sheet)
    for i, cid in enumerate(ids):
        im = Image.open(os.path.join(HERE, "chars", cid, "normal.png")).convert("RGBA")
        im = im.crop(im.getbbox())
        im = im.crop((0, 0, im.width, min(im.height, int(im.width * 1.2))))
        f = PRESETS.get(cid, {}).get("facing")
        x, y = (i % cols) * W, (i // cols) * (H + 24)
        for j, side in enumerate(("left", "right")):
            t = im.transpose(Image.FLIP_LEFT_RIGHT) if f in ("left", "right") and f == side else im
            t.thumbnail((W // 2 - 6, H))
            sheet.paste(t, (x + j * (W // 2) + (W // 2 - t.width) // 2, y + 24 + H - t.height), t)
        d.text((x + 4, y + 5), "%s  facing: %s" % (cid, f or "-"), fill="#000000")
        d.text((x + 4, y + 24 + 4), "L (screen left)        R (screen right)", fill="#203040")
    sheet.save(out)
    print("OK : %s（左の列は画面の左に、右の列は画面の右に置いたときの姿。両方とも内側＝画面の中央を向いていればよい）" % out)


def take_shots(html, times, outdir):
    """作った HTML を Chrome（画面なし）で開き、その時刻へ動かして、映像だけを 1280×720 の PNG に撮る。"""
    import shutil, subprocess, tempfile
    chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
    if not chrome:
        print("warn: Chrome が見つからないので、画面を撮れません（HTML をブラウザで開いて見る）", file=sys.stderr)
        return
    os.makedirs(outdir, exist_ok=True)
    src = open(html, encoding="utf-8").read()
    for t in times:
        sec = sum(float(x) * 60 ** i for i, x in enumerate(reversed(t.strip().split(":"))))
        hook = ('<style>.mv-stage{position:fixed!important;inset:0!important;z-index:99999!important;max-width:none!important;width:100vw!important;height:100vh!important}</style>'
                '<script>window.addEventListener("load",function(){setTimeout(function(){try{__MV__.seek(%d)}catch(e){}},700)})</script>' % round(sec * 1000))
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8", dir=os.path.dirname(html)) as f:
            f.write(src + hook)
        png = os.path.join(outdir, "%07.2f.png" % sec)
        try:
            subprocess.run([chrome, "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1280,720", "--virtual-time-budget=4000",
                            "--screenshot=" + png, "file://" + f.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            print("撮った絵: %s" % png)
        except Exception as e:
            print("warn: %s 秒の画面を撮れませんでした（%s）" % (t, e), file=sys.stderr)
        finally:
            os.remove(f.name)


def main():
    ap = argparse.ArgumentParser(description="ゆっくり解説・ずんだもん解説の台本から、掛け合いの動画（単一 HTML）を作る")
    ap.add_argument("script", nargs="?", help="台本（テキスト）。--list-casts のときは、詳しく見る登場人物の名前")
    ap.add_argument("-o", "--out", help="出力 HTML（既定: 台本と同じ場所・同じ名前）")
    ap.add_argument("--voicevox", action="store_true", help="VOICEVOX でせりふの声を作る（engine: voicevox の登場人物。ゆっくりボイスもここで作る）")
    ap.add_argument("--voicevox-url", default="http://127.0.0.1:50021")
    ap.add_argument("--voices-dir", help="用意した WAV のフォルダ（名前順に、声の無いせりふへ順に当てる）")
    ap.add_argument("--timeline", action="store_true", help="HTML を作らず時間割りを出す")
    ap.add_argument("--shots", help="作った HTML の、その時刻（秒。6.5,12 のように並べる。0:42 の形でもよい）の画面を PNG に撮る（<台本名>_shots/。Chrome が要る）。絵・図・立ち絵の見え方を確かめるため")
    ap.add_argument("--readings", action="store_true", help="VOICEVOX がせりふをどう読むか（かな）を出す。読み間違いを pronounce: で直すため")
    ap.add_argument("--yukkuri-bat", action="store_true", help="ゆっくりボイスのせりふを、Windows の AquesTalkPlayer で WAV にするバッチファイル（<台本名>_yukkuri.bat）を書く")
    ap.add_argument("--compact", action="store_true", help="HTML を小さくする（声を 16kHz に、背景と写真を幅 1280 の JPEG に。3 分で 5MB ほど減る）")
    ap.add_argument("--voice-rate", type=int, default=16000, help="--compact のときの声のサンプリング周波数（既定 16000。12000 にすると、もう 2 割ほど小さくなるが、声が少しこもる）")
    ap.add_argument("--dist", action="store_true", help="配布用: 設定の書き出し（WebM で保存・編集用の映像・音のトラック）と、その実行部を除いて HTML を小さくする")
    ap.add_argument("--list-assets", action="store_true", help="背景と BGM のカタログ（名前と説明）を出す")
    ap.add_argument("--facing-sheet", metavar="PNG", help="集めた立ち絵を、画面の左に置いたときと右に置いたときの向き（facing で返した後）で並べた見本を作る。向きが内側を向いているかを確かめる")
    ap.add_argument("--list-styles", action="store_true", help="動画の型（style:）の一覧を出す")
    ap.add_argument("--list-casts", action="store_true", help="登場人物のプリセットと、立ち絵にある表情・ポーズを出す")
    a = ap.parse_args()
    if a.facing_sheet:
        facing_sheet(a.facing_sheet)
        return
    if a.list_styles:
        for k, v in STYLES.items():
            if not k.startswith("_"):
                print("%-7s %s\n        %s\n        向くもの: %s" % (k, v["name"], v["desc"], v["fit"]))
        return
    if a.list_assets:
        print("# 背景（台本の bg: か @bg: に名前を書く。時間帯は _evening・_night）")
        for k, e in BGS.items():
            if not k.startswith("_"):
                print("  %-22s %-14s %s%s" % (k, e["name"], e["desc"], "" if os.path.isfile(os.path.join(HERE, "bg", e["file"])) else "  ※ファイルなし（fetch_assets.py）"))
        print("# BGM（台本の music: か @music: に名前を書く。ほかに motion-video の曲の名前も使える）")
        for mood, label in BGMS["_moods"].items():
            print("## %s" % label)
            for k, e in BGMS.items():
                if not k.startswith("_") and e["mood"] == mood:
                    have = os.path.isfile(os.path.join(HERE, "bgm", e["file"]))
                    note = ("  ※WebM 専用（HTML は配れない）" + ("" if have else "・手で取る: " + e["page"])) if e.get("embed") is False else "" if have else "  ※ファイルなし（fetch_assets.py）"
                    print("  %-14s %s ／ %s（%s%s）%s" % (k, e["desc"], e["title"], e["author"], "・%.1fMB" % e["mb"] if e.get("mb") else "", note))
        return
    if a.list_casts or not a.script:   # --list-casts [名前]
        list_casts(a.script)
        return
    name = os.path.splitext(os.path.basename(a.script))[0]
    if a.readings or a.yukkuri_bat:
        meta, spec, cast, credits, base = load_spec(a.script)
        if a.readings:
            readings(spec, a.voicevox_url, spec["audio"]["pronounce"])
            return
        path, n = yukkuri_bat(spec, os.path.splitext(os.path.abspath(a.script))[0], spec["audio"]["pronounce"])
        if not path:
            sys.exit("error: ゆっくりボイスの登場人物（reimu・marisa など）のせりふがありません")
        print("OK : %s（%d 個のせりふ）" % (path, n))
        print("  1. Windows で AquesTalkPlayer を入手して展開する（https://www.a-quest.com/products/aquestalkplayer.html）")
        print("  2. %s をメモ帳で開き、PLAYER= の行を AquesTalkPlayer.exe の場所に直す" % os.path.basename(path))
        print("  3. ダブルクリックで実行する（%s_yukkuri フォルダに WAV ができる）" % name)
        print("  4. python3 %s %s --voices-dir %s_yukkuri" % (os.path.basename(__file__), a.script, name))
        return
    spec, mv, cast, credits = make_spec(a.script, a.voicevox, a.voicevox_url, a.voices_dir, a.compact, a.voice_rate)
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
    open(out, "w", encoding="utf-8").write(mv.build_html(spec, spec["theme"], spec["player"], not a.dist))
    print("OK : %s（%s・%.1fMB%s）" % (out, mv.fmt(total), os.path.getsize(out) / 1e6, "・配布用" if a.dist else ""))
    for k in WEBM_ONLY:
        e = BGMS[k]
        print("warn: BGM「%s」（%s）は、音源を取り出せる形では配れません（%s）。この HTML は手元だけで使い、プレイヤーの「WebM で保存」で動画にして配ってください"
              % (e["title"], e["author"], e["license"].split("。")[0]), file=sys.stderr)
    if credits:
        print("クレジット: " + " / ".join(credits))
    if a.shots:
        take_shots(out, [t for t in a.shots.split(",") if t.strip()], stem + "_shots")


if __name__ == "__main__":
    main()
