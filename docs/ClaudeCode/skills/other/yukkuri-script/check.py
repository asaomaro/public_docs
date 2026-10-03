#!/usr/bin/env python3
"""掛け合いの台本（yukkuri-kaisetsu の書き方）を検査する。長さ・冒頭・掛け合いの型・口調・演技・画面の変化・読み・出典を見て、直す所を出す。

  python3 check.py 台本.txt                     # 検査（error があれば終了コード 1）
  python3 check.py 台本.txt --facts 事実.md     # 出典の一覧と突き合わせる（既定: 台本の facts: か、<台本名>.facts.md）
  python3 check.py 台本.txt --stats             # 数字だけ見る
  python3 check.py 台本.txt --strict            # warn でも終了コード 1

台本の先頭に書ける項目（どれも省ける）: length: 3（分）・roles: metan=解説, zundamon=聞き手・facts: 事実.md
基準の出どころは yukkuri-kaisetsu/research.md。口調の決まりは characters.json。
"""
import argparse, copy, importlib.util, json, os, re, statistics, sys, unicodedata

HERE = os.path.dirname(os.path.realpath(__file__))
_CJ = json.load(open(os.path.join(HERE, "characters.json"), encoding="utf-8"))
CHARS = {k: v for k, v in _CJ.items() if not k.startswith("_")}
RELATIONS = {k: v for k, v in _CJ.get("_relations", {}).items() if not k.startswith("_")}   # よく一緒に出る組み合わせ（"metan+zundamon" の形。名前の順）
PUNCT = re.compile(r"[\s　、。，．！？!?…‥「」『』（）()・♪〜ー―\-*]")
CPS = 4.8           # VOICEVOX の話速 1.0 で 1 秒に読む字数（記号を除く。句読点の間を含む。3 分の台本で実測）
LINE_GAP, SCENE_GAP, END_SEC = 0.3, 2.5, 6.0
MAX_LINE, HARD_LINE = 40, 60
AIZUCHI = {"へぇ": r"^(へぇ|へえ|へー|ほぉ|ほう|ふーん|ふむ)", "なるほど": r"^なるほど", "そうなんだ": r"^(そうなん|そうだったん|そうなの(?!？|\?))", "えっ": r"^(えっ|ええっ|えぇ|え、|えー)",
           "すごい": r"^(すご|すげ)", "たしかに": r"^(たしかに|確かに)", "まさか": r"^(まさか|うそ|ウソ|マジ|まじ)"}
AGREE = re.compile(r"^(そう(よ|だ|なの|ね|いうこと|です)?[、。！!]|その通り|そのとおり|正解|そういうこと|いい質問|よく気づ|よくわかった)")
QUESTION = re.compile(r"[？?]\s*$|どういうこと|なんで|なぜ|って(何|なに|なん)")
HOOK = re.compile(r"[？?]|実は|じつは|なぜ|なんと|知って|って知|本当は|意外|驚|まさか|秘密|\d")
BORING_OPEN = re.compile(r"(今日|今回|本日|この動画)(は|では).{0,30}(について|を).{0,12}(解説|紹介|説明|お話|話|見てい)")
STRONG_FACES = {"angry", "doubt", "smug", "troubled", "dizzy", "shy", "sad", "surprised", "love"}
STRONG_EMOTES = {"!?", "💢", "💦"}
NUM_UNIT = r"(?:%|％|倍|年|月|日|時間|分|秒|万|億|兆|円|ドル|人|件|個|本|回|種|位|歳|才|度|km|m|cm|mm|nm|kg|g|t|トン|キロ|メートル|グラム|パーセント|選)"


def load_kaisetsu():
    path = os.path.join(HERE, "..", "yukkuri-kaisetsu", "kaisetsu.py")
    if not os.path.isfile(path):
        sys.exit("error: yukkuri-kaisetsu スキルが見つかりません（%s）。同じ場所に置いてください" % path)
    spec = importlib.util.spec_from_file_location("kaisetsu", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def nchars(text):
    return len(PUNCT.sub("", text.replace("**", "")))


def norm(s):
    return unicodedata.normalize("NFKC", s).replace(",", "").replace(" ", "")


def numbers(text):
    """出典と突き合わせる数字（2 桁以上か、単位つき）。「3 つ」のような数え方は除く。"""
    t, out = norm(text), []
    for m in re.finditer(r"(\d+(?:\.\d+)?)(%s)?" % NUM_UNIT, t):
        num, unit = m.group(1), m.group(2) or ""
        if t[m.end():m.end() + 1] in ("つ", "点") and not unit:
            continue
        if unit in ("分", "秒", "回", "個", "本", "位", "選", "件", "種") and len(num) < 2:   # 「3 選」「1 位」は構成の数字
            continue
        if len(num.replace(".", "")) >= 2 or unit:
            out.append(num)
    return out


def board_text(b):
    if isinstance(b, str):
        return b
    out = []

    def walk(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in ("type", "src", "ref", "img", "line", "frame", "color", "op", "icon", "draw", "draw_ref"):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(b)
    return " ".join(out)


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, group, msg, no=None):
        self.items.append((level, group, ("%d 行目: " % no if no else "") + msg))

    def count(self, level):
        return sum(1 for i in self.items if i[0] == level)


def run(path, facts_path=None):
    K = load_kaisetsu()
    text = open(path, encoding="utf-8").read()
    meta, chapters, errs = K.parse(text)
    R = Report()
    for e in errs:
        R.add("error", "書き方", e)
    base = os.path.dirname(os.path.abspath(path))
    # せりふを 1 列に（元の行番号つき）
    head = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    off = text[:head.end()].count("\n") if head else 0
    nos = [off + i for i, raw in enumerate(text[head.end() if head else 0:].splitlines(), 1)
           if raw.strip() and not raw.strip().startswith(("//", "# ", "@", ">", "＞")) and not K.PAUSE_RE.match(raw.strip()) and K.LINE_RE.match(raw.strip())]
    L, scenes = [], []
    for ci, ch in enumerate(chapters):
        for sc in ch["scenes"]:
            S = {"ch": ci, "title": ch["title"], "board": sc.get("board"), "tag": sc.get("tag"), "lines": []}
            scenes.append(S)
            for ln in sc["lines"]:
                d = {"who": ln["who"], "text": ln["text"], "n": nchars(ln["text"]), "opts": ln.get("opts", []), "emote": ln.get("emote", ""),
                     "pause": ln.get("pause", 0), "ch": ci, "no": nos[len(L)] if len(L) < len(nos) else None}
                L.append(d)
                S["lines"].append(d)
    if not L:
        R.add("error", "書き方", "せりふがありません")
        return R, {}
    cast = K.build_cast(meta, base)
    for who in sorted({l["who"] for l in L} - set(cast)):
        R.add("error", "書き方", "cast に無い話し手: %s" % who)
    mult = float(meta.get("speed", getattr(K, "DEFAULT_SPEED", 1.0)))
    speed = {cid: float((c.get("voice") or {}).get("speed", 1.0)) * mult for cid, c in cast.items()}
    t = 0.0
    for S in scenes:
        S["t0"] = t
        for l in S["lines"]:
            l["t"] = t
            l["sec"] = l["n"] / (CPS * speed.get(l["who"], 1.0))
            t += l["sec"] + LINE_GAP + l["pause"]
        t += SCENE_GAP
        S["sec"] = t - S["t0"]
    total = t + END_SEC
    chars = sum(l["n"] for l in L)
    by = {}
    for l in L:
        by.setdefault(l["who"], []).append(l)
    roles = {}
    for part in re.split(r"[,、]", meta.get("roles", "")):
        if "=" in part:
            a, b = part.split("=", 1)
            roles[a.strip()] = b.strip()
    explainer = next((k for k, v in roles.items() if "解説" in v), None) or max(by, key=lambda k: sum(l["n"] for l in by[k]))
    listeners = [k for k in by if k != explainer]
    stats = {"せりふ": len(L), "字数": chars, "見積もりの長さ": "%d:%02d" % (total // 60, total % 60), "1 分あたりの字数": round(chars / total * 60),
             "解説役": cast.get(explainer, {}).get("name", explainer), "聞き手のせりふの割合": "%d%%" % round(100 * sum(len(by[k]) for k in listeners) / len(L)),
             "せりふの長さ（平均・ばらつき）": "%.0f 字・%.1f" % (statistics.mean(l["n"] for l in L), statistics.pstdev(l["n"] for l in L)),
             "場面（黒板）": len(scenes), "場面の長さ（平均）": "%.0f 秒" % statistics.mean(S["sec"] for S in scenes)}
    

    # 1. 長さ
    for l in L:
        if l["n"] > HARD_LINE:
            R.add("error", "長さ", "せりふが %d 字（%d 字まで。2 つに分ける）: %s…" % (l["n"], HARD_LINE, l["text"][:18]), l["no"])
        elif l["n"] > MAX_LINE:
            R.add("warn", "長さ", "せりふが %d 字（字幕 2 行は %d 字まで）: %s…" % (l["n"], MAX_LINE, l["text"][:18]), l["no"])
    if meta.get("length"):
        goal = float(re.sub(r"[^\d.]", "", meta["length"]) or 0) * 60
        if goal and abs(total - goal) / goal > .2:
            R.add("warn", "長さ", "見積もり %s は、目標の %s 分から 2 割より離れています（%d 字。目標に合わせるなら約 %d 字）"
                  % (stats["見積もりの長さ"], meta["length"], chars, round(chars * goal / total / 10) * 10))
    if statistics.pstdev(l["n"] for l in L) < 6 and len(L) >= 10:
        R.add("warn", "掛け合い", "せりふの長さがそろいすぎています（ばらつき %.1f）。短い相づち（12 字以下）と長めの説明をまぜる" % statistics.pstdev(l["n"] for l in L))
    if len(L) >= 10 and sum(1 for l in L if l["n"] <= 12) / len(L) < .1:
        R.add("warn", "掛け合い", "12 字以下の短いせりふが 1 割より少ない（短い反応・ツッコミを入れる）")

    # 2. 冒頭（すぐ本題に入る型か、茶番から入る型）
    chaban = meta.get("intro", "").lower() in ("chaban", "茶番") or "茶番" in chapters[0]["title"]
    if chaban:
        C = [l for l in L if l["ch"] == 0]
        sec = sum(l["sec"] + LINE_GAP for l in C)
        stats["冒頭の茶番"] = "%d せりふ・約 %d 秒" % (len(C), sec)
        if "茶番" not in chapters[0]["title"]:
            R.add("warn", "冒頭", "intro: chaban なのに、最初の章の名前に「茶番」がありません（# 茶番 にする。検査とファクトチェックが茶番として扱う）")
        if sec > 45 or sec > max(20, total * .12):
            R.add("warn", "冒頭", "茶番が約 %d 秒あります（15〜40 秒・全体の 1 割まで）" % sec, C[0]["no"])
        elif sec < 15:
            R.add("warn", "冒頭", "茶番が約 %d 秒しかありません（15〜40 秒が目安。短いなら、茶番にせずつかみにする）" % sec, C[0]["no"])
        if total < 100:
            R.add("warn", "冒頭", "1 分台の動画に茶番は入れない（すぐ本題に入る）")
        nxt = [l for l in L if l["ch"] == 1][:2]
        if not any(re.search(r"というわけで|ということで|そんなわけで|はさておき|それはさておき|今回は|今日は|本題", l["text"]) for l in C[-2:] + nxt):
            R.add("warn", "冒頭", "茶番から本題へのつなぎ（「というわけで今回は」など）が見当たりません", (C[-1] if C else L[0])["no"])
        nums = [x for l in C for x in numbers(l["text"])]
        if nums:
            R.add("info", "冒頭", "茶番の中に数字があります（%s）。事実として言うなら本編で。茶番の中の事実も、ファクトチェックの対象になる" % "・".join(dict.fromkeys(nums)))
        if not any(l["emote"] in STRONG_EMOTES or any(K.OPT_RE.match(o).group(1) in STRONG_FACES for o in l["opts"]) for l in C):
            R.add("warn", "冒頭", "茶番に、感情の動くせりふ（驚き・ツッコミ・困る）がありません")
    else:
        first = [l for l in L if l["t"] < 15] or L[:3]
        for l in L[:2]:
            if BORING_OPEN.search(l["text"]):
                R.add("warn", "冒頭", "「今日は〜について解説」で始まっています。先に問い・意外な事実・結論のチラ見せを置く: %s" % l["text"][:24], l["no"])
        if not any(HOOK.search(l["text"]) for l in first):
            R.add("warn", "冒頭", "最初の 15 秒につかみ（問い・意外な事実・数字）が見当たりません")
        greet = [l for l in L[:4] if re.search(r"(です|よ|だぜ|なのだ|だよ)[。！!★]*$", l["text"]) and cast.get(l["who"], {}).get("name", "")[-2:] in l["text"]]
        if len(greet) >= 2 and L.index(greet[-1]) <= 1:
            R.add("info", "冒頭", "あいさつ（名乗り）から始まっています。つかみを先にして、名乗りは 1 人ぶん・短くするか省く")

    # 3. 掛け合い
    run_who, run_n = None, 0
    for l in L + [{"who": None}]:
        if l["who"] == run_who:
            run_n += 1
        else:
            if run_n > 5:
                R.add("warn", "掛け合い", "%s が %d せりふ続けて話しています（3〜5 せりふごとに相手を入れる）" % (cast.get(run_who, {}).get("name", run_who), run_n), start)
            run_who, run_n, start = l["who"], 1, l.get("no")
    share = sum(len(by[k]) for k in listeners) / len(L)
    if listeners and share < .25:
        R.add("warn", "掛け合い", "聞き手のせりふが %d%% しかありません（3 割前後に）" % round(share * 100))
    lis = [l for l in L if l["who"] in listeners]
    for name, pat in AIZUCHI.items():
        hit = [l for l in lis if re.search(pat, l["text"])]
        if len(hit) > max(3, len(lis) * .15):
            R.add("warn", "掛け合い", "相づち「%s」で始まるせりふが %d 回あります（%s 行目）。言い方を変える" % (name, len(hit), "・".join(str(l["no"]) for l in hit[:8])))
    prev = None
    for l in lis:
        op = next((n for n, p in AIZUCHI.items() if re.search(p, l["text"])), None)
        if op and op == prev:
            R.add("warn", "掛け合い", "相づち「%s」が 2 回続いています" % op, l["no"])
        prev = op
    agree = [l for l in by.get(explainer, []) if AGREE.search(l["text"])]
    if len(agree) > max(3, len(by.get(explainer, [])) * .12):
        R.add("warn", "掛け合い", "解説役が「そう」「その通り」「正解」で受けるせりふが %d 回あります（%s 行目）。「説明→確認の質問→肯定」の型が続いていないか"
              % (len(agree), "・".join(str(l["no"]) for l in agree[:8])))
    kind = lambda l: "Q" if QUESTION.search(l["text"]) else "R" if (l["n"] <= 12 or any(re.search(p, l["text"]) for p in AIZUCHI.values())) else "E"
    seq = "".join(kind(l) for l in L)
    for size in (2, 3, 4):
        m = re.search(r"((?:[QRE]){%d})\1{3,}" % size, seq)
        if m and len(set(m.group(1))) > 1:
            names = {"Q": "質問", "R": "短い反応", "E": "説明"}
            R.add("warn", "掛け合い", "「%s」の同じ流れが %d 回続いています。たとえ話・ツッコミ・クイズ・勘違いで崩す"
                  % ("→".join(names[c] for c in m.group(1)), len(m.group(0)) // size), L[m.start()]["no"])
            break
    spice = [l for l in L if l["emote"] in STRONG_EMOTES or any(K.OPT_RE.match(o).group(1) in STRONG_FACES for o in l["opts"])]
    if total > 60 and len(spice) < total / 45:
        R.add("warn", "掛け合い", "感情の動くせりふ（驚き・ツッコミ・困る・得意げ など）が %d 回だけです。45 秒に 1 回は入れる" % len(spice))

    # 4. 口調
    for who, lines in by.items():
        P = CHARS.get(who)
        if not P:
            continue
        name, others = P["name"], [k for k in cast if k != who]
        for l in lines:
            for bad in P.get("avoid_first", []):
                if re.search(r"(?<![一-龥ぁ-んァ-ヶ])%s(?![立設鉄語])(は|が|も|の|に|を|って|、|たち|なら|だって)" % re.escape(bad), l["text"]):
                    R.add("error", "口調", "%s の一人称は「%s」です（「%s」になっている）: %s" % (name, P["first"][0], bad, l["text"][:22]), l["no"])
            for pat, why in P.get("ng", []):
                if re.search(pat, l["text"]):
                    last = l["ch"] == len(chapters) - 1 and re.search(r"ありがとう|お願い", l["text"])
                    R.add("info" if last else "error", "口調", "%s: %s → %s" % (name, why, l["text"][:26]), l["no"])
            for o in others:
                want = P.get("calls", {}).get(o)
                if not want:
                    continue
                stem = re.sub(r"(さん|ちゃん|くん|先輩|さま|様|殿)$", "", want)
                for m in re.finditer(re.escape(stem) + r"(さん|ちゃん|くん|先輩|さま|様|殿)?", l["text"]):
                    if m.group(0) != want and not l["text"][:m.start()].endswith(("四国", "春日部")):
                        R.add("warn", "口調", "%s は相手を「%s」と呼びます（「%s」になっている）" % (name, want, m.group(0)), l["no"])
        for rule in P.get("must", []):
            if len(lines) >= 6:
                r = sum(1 for l in lines if re.search(rule["re"], l["text"])) / len(lines)
                if r < rule["min"]:
                    R.add("warn", "口調", "%s: %sが %d%% しかありません（%d%% 以上に）" % (name, rule["what"], round(r * 100), round(rule["min"] * 100)))
                elif r > rule["max"]:
                    R.add("warn", "口調", "%s: %sが %d%% あります（%d%% まで。相づち・体言止めをまぜる）" % (name, rule["what"], round(r * 100), round(rule["max"] * 100)))

    # 4.5 性格・関係・登場の仕方（3 人以上・一瞬だけ出る人・語り手）
    ids = lambda key: [x.strip() for x in re.split(r"[,、\s]+", meta.get(key, "")) if x.strip()]
    cameo, narr = set(ids("cameo")), set(ids("narrator"))
    main = [k for k in by if k not in cameo and k not in narr]
    nm = lambda k: cast.get(k, {}).get("name") or CHARS.get(k, {}).get("name", k)
    called = lambda k: {nm(k), re.sub(r"^(四国|春日部|東北|ゆっくり)", "", nm(k))} | {P2.get("calls", {}).get(k) for P2 in CHARS.values()} - {None, ""}
    if total >= 150:   # 性格の見せ場（公式の設定・定番の持ちネタ）が一度も無い
        for who in main:
            sig = CHARS.get(who, {}).get("signature")
            if sig and len(by[who]) >= 8 and not any(re.search(p, l["text"]) for p in sig["patterns"] for l in L):
                R.add("info", "性格", "%s の持ち味（%s）が台本に一度も出てきません。1 か所入れると、その人らしくなる" % (nm(who), sig["desc"]))
    for k in [x for x in listeners if x in main]:   # 聞き手が解説している（教える側・教わる側の入れ替わり）
        ex = [l for l in by[k] if l["n"] >= 32 and not re.search(r"[？?！!…]$|ってこと|なの？|のだ？", l["text"])]
        if len(by[k]) >= 6 and len(ex) / len(by[k]) > .3:
            R.add("warn", "関係", "聞き手の %s が、長い説明を %d 回しています（せりふの %d%%）。教える側と教わる側が入れ替わって見える。説明は %s に回し、%s は問い・驚き・言い直しにする"
                  % (nm(k), len(ex), round(100 * len(ex) / len(by[k])), nm(explainer), nm(k)), ex[0]["no"])
    pair = "+".join(sorted([explainer] + [x for x in listeners if x in main][:1]))
    rel = RELATIONS.get(pair) or next((v for kk, v in RELATIONS.items() if set(kk.split("+")) == set(main)), None)
    if rel and rel.get("roles") and rel["roles"].get("explainer") not in (None, explainer) and len(main) == 2:
        R.add("info", "関係", "%s が解説役です。定番は逆（%s）。わざとなら、冒頭で役を入れ替える理由を一言入れる" % (nm(explainer), rel["convention"][:40]))
    if len(main) >= 3:   # 3 人以上: 全員に役を。少なすぎる人は、一瞬だけ出る人（cameo）にする
        for k in main:
            share = len(by[k]) / len(L)
            if k != explainer and share < .12:
                R.add("warn", "関係", "%s のせりふが %d%% だけです（3 人目は 15〜35%%）。役（ボケ・ツッコミ・進行・専門家）を持たせて増やすか、台本の先頭の cameo: に書いて、出番の場面だけに出す"
                      % (nm(k), round(share * 100)))
    for k in cameo | ({k for k in by if len(main) >= 3 and len(by[k]) / len(L) < .05} - narr):   # 一瞬だけ出る人: 出てきたときに、誰か分かるように
        if k not in by:
            continue
        i0 = next(i for i, l in enumerate(L) if l["who"] == k)
        near = L[max(0, i0 - 2):i0 + 3]
        if not any(n2 and n2 in l["text"] for l in near for n2 in called(k)):
            R.add("warn", "関係", "%s が初めて出る所で、だれも名前を呼ばず、本人も名乗っていません（見る人に誰か分かるように、前後のせりふで名前を出す）" % nm(k), L[i0]["no"])
        chs = sorted({l["ch"] for l in by[k]})
        if k in cameo and len(chs) >= 3:
            R.add("info", "関係", "%s（cameo）が %d つの章に出ています。一瞬だけ出る人なら 1〜2 章に絞り、通して出るなら cameo: から外す" % (nm(k), len(chs)))
    for k in narr:
        if k in by and any(re.search(r"(のだ|だぜ|わよ)[。！!]?$", l["text"]) for l in by[k]):
            R.add("info", "関係", "語り手（%s）のせりふに、キャラクターの口調が出ています。語りは、です・ます か言い切りで" % nm(k))
    if rel:
        stats["関係（定番）"] = rel.get("convention", "")[:60]

    # 5. 演技（表情・体・動きのラベル）
    try:
        for w in K.resolve_faces(copy.deepcopy(chapters), copy.deepcopy(cast)):
            R.add("warn", "演技", w)
    except Exception as e:   # 立ち絵が無いなど
        R.add("info", "演技", "ラベルを立ち絵に当てられませんでした（%s）" % e)
    for who, lines in by.items():
        name = cast.get(who, {}).get("name", who)
        faces = []
        for l in lines:
            labs = [K.OPT_RE.match(o).group(1) for o in l["opts"]]
            f = next((x for x in labs if x in K.FACES), None)
            l["face"], l["body"], l["motion"] = f, [x for x in labs if x in K.POSES or x in K.ITEMS], [x for x in labs if x in K.MOTIONS]
            faces.append(f or "normal")
        runs, prev, n = [], None, 0
        for i, f in enumerate(faces + [None]):
            if f == prev:
                n += 1
            else:
                if n >= 4:
                    runs.append((prev, n, lines[i - n]["no"]))
                prev, n = f, 1
        for f, n, no in runs:
            R.add("warn", "演技", "%s の表情が %d せりふ続けて %s のままです" % (name, n, f), no)
        if len(lines) >= 8 and len(set(faces)) < 3:
            R.add("warn", "演技", "%s の表情が %d 種類しかありません（%s）" % (name, len(set(faces)), "・".join(sorted(set(faces)))))
        if len(lines) >= 8 and sum(1 for l in lines if l["body"]) / len(lines) < .2:
            R.add("warn", "演技", "%s に体のラベル（point・raise・chin など）が 2 割より少ない" % name)
        nolab = sum(1 for l in lines if not l["opts"])
        if nolab:
            R.add("info", "演技", "%s: ラベルの無いせりふが %d 個（せりふの中身から自動で付く）" % (name, nolab))

    # 6. 画面の変化（絵で見せているか）
    views = []   # 画面が変わる単位: 絵の並び（@show の 1 つ）か、黒板 1 枚
    for S in scenes:
        b = S["board"]
        if isinstance(b, dict) and b.get("type") == "stage":
            shots = b["shots"]
            for i, sh in enumerate(shots):
                ls = S["lines"][sh["line"]:shots[i + 1]["line"] if i + 1 < len(shots) else None]
                pics = sum(1 for it in sh["items"] if it.get("ref") or it.get("img") or it.get("icon") or it.get("part") or it.get("draw_ref") or it.get("draw"))
                views.append({"kind": "絵" if pics else "言葉", "lines": ls, "sec": sum(l["sec"] + LINE_GAP for l in ls), "t0": ls[0]["t"] if ls else S["t0"], "text": board_text(sh),
                              "refs": [it.get("ref") for it in sh["items"] if it.get("ref")], "ops": [it.get("op") for it in sh["items"] if it.get("op")],
                              "cells": len([it for it in sh["items"] if not it.get("op")]), "title": bool(sh.get("title")), "no": ls[0]["no"] if ls else None,
                              "ch": ls[0]["ch"] if ls else None})
        else:
            k = b.get("type") if isinstance(b, dict) else "言葉" if b else "なし"
            views.append({"kind": "絵" if k == "image" else k, "lines": S["lines"], "sec": S["sec"], "t0": S["t0"], "text": board_text(b) if b else ""})
    stats["画面"] = "%d 枚（絵 %d・言葉だけ %d・黒板 %d・なし %d）" % (len(views), sum(v["kind"] == "絵" for v in views), sum(v["kind"] == "言葉" for v in views),
                                                              sum(v["kind"] not in ("絵", "言葉", "なし") for v in views), sum(v["kind"] == "なし" for v in views))
    stats.pop("場面（黒板）", None); stats.pop("場面の長さ（平均）", None)
    for v in views:
        lim = 15 if v["t0"] < 60 else 25
        if v["sec"] > lim and v["lines"]:
            R.add("warn", "画面", "同じ画面が約 %d 秒続きます（%s は %d 秒まで）。@show で絵を替える" % (v["sec"], "最初の 1 分" if lim == 15 else "本編", lim), v["lines"][0]["no"])
        if v["text"] and v["lines"]:
            said = norm(" ".join(l["text"] for l in v["lines"]))
            miss = [x for x in dict.fromkeys(numbers(v["text"])) if x not in said]
            if miss:
                R.add("info", "画面", "画面の数字 %s を言うせりふが、その画面の間にありません" % "・".join(miss), v["lines"][0]["no"])
    if views:
        pic = sum(v["kind"] == "絵" for v in views) / len(views)
        if pic < .6:
            R.add("warn", "画面", "絵のある画面が %d%% です（6 割以上に。解説動画は、ほとんどの画面に挿絵・写真・図がある）。illust.py・fetch_images.py・irasutoya スキルで絵を取り、@show で出す" % round(pic * 100))
        lists = [v for v in views if v["kind"] in ("bullets", "steps", "cards", "statement")]
        if len(lists) > max(1, len(views) * .15):
            R.add("warn", "画面", "箇条書き・手順・カードの黒板が %d 枚あります（全体の 15%% まで。まとめ以外は絵で見せる）" % len(lists))
        none = [v for v in views if v["kind"] == "なし" and v["lines"]]
        if none:
            R.add("warn", "画面", "絵も黒板も無い画面が %d 枚あります" % len(none), none[0]["lines"][0]["no"])
        per = len(L) / len(views)
        if per > 3.2:
            R.add("warn", "画面", "1 つの画面でせりふが平均 %.1f 個続きます（1〜3 個ごとに絵を替える）" % per)

    # 6.5 絵の選び方（画面の採点で多かった指摘を、台本の段階で数える）
    img_dir = os.path.join(base, meta.get("images", "images"))
    cj = os.path.join(img_dir, "credits.json")
    credits = json.load(open(cj, encoding="utf-8")) if os.path.isfile(cj) else {}
    files = {os.path.splitext(f)[0]: f for f in os.listdir(img_dir)} if os.path.isdir(img_dir) else {}
    src_of = lambda r: (credits.get(files.get(r, ""), {}) or {}).get("from") or ("描き下ろし" if files.get(r, "").endswith(".svg") and r not in credits else None)
    STYLE = {"いらすとや": "いらすとや", "Fluent Emoji": "絵文字"}
    uses = {}
    for v in views:   # 茶番と最後の章（まとめ・オチ）は数えない。茶番の小道具をオチで出し直すのはよい
        if v.get("ch") in (0 if chaban else -1, len(chapters) - 1):
            continue
        for r in v.get("refs", []):
            uses.setdefault(r, []).append(v)
    for r, vs in uses.items():   # 同じ絵の使い回し（本編で 3 回以上）
        if len(vs) >= 3:
            R.add("warn", "絵", "絵「%s」を本編で %d 回使っています（画面が同じに見える。3 回目からは別の絵か図にする）" % (r, len(vs)), vs[2].get("no"))
    for v in views:   # 1 つの画面に、絵柄の違う絵（いらすとやと 3D の絵文字）を並べない
        st = {STYLE.get(src_of(r)) for r in v.get("refs", [])} - {None}
        if len(st) >= 2:
            R.add("warn", "絵", "1 つの画面に、いらすとやの絵と絵文字の絵がまざっています（%s）。どちらかにそろえる" % "・".join(v["refs"]), v.get("no"))
    allst = {}
    for r in uses:
        k = STYLE.get(src_of(r))
        if k:
            allst[k] = allst.get(k, 0) + 1
    if len(allst) >= 2 and min(allst.values()) >= 3:
        R.add("info", "絵", "いらすとや %d 点と絵文字 %d 点を使っています。1 本の中では、人・物の絵の絵柄をどちらかにそろえると、手本に近づく" % (allst.get("いらすとや", 0), allst.get("絵文字", 0)))
    run, start = 0, None   # 「A → B」の 2 つを並べる構図が続く
    for v in views + [{}]:
        pair = v.get("cells") == 2 and v.get("ops") and not v.get("title")
        if pair:
            run, start = run + 1, start or v
        else:
            if run >= 3:
                R.add("warn", "絵", "「A → B」の 2 つを並べた画面が %d 枚続きます。年表・図解（@draw）・1 枚の大きな絵・題の画面などをまぜる" % run, start.get("no"))
            run, start = 0, None

    # 7. 読み
    try:
        pron = json.loads(meta["pronounce"]) if meta.get("pronounce", "").startswith("{") else {}
    except ValueError:
        pron = {}
        R.add("error", "読み", "pronounce の JSON が読めません")
    words = {}
    for l in L:
        for w in re.findall(r"[A-Za-z][A-Za-z0-9\-\.]+", unicodedata.normalize("NFKC", l["text"])):
            if not any(k in w or w in k for k in pron) and w.lower() not in ("nm", "km", "cm", "mm", "kg"):
                words.setdefault(w, l["no"])
    if words:
        R.add("warn", "読み", "英字の語に読みがありません。先頭の pronounce に足す（字幕はそのまま）: %s" % "、".join("%s（%s 行目）" % kv for kv in list(words.items())[:12]))

    # 8. 出典
    fp = facts_path or (os.path.join(base, meta["facts"]) if meta.get("facts") else os.path.splitext(os.path.abspath(path))[0] + ".facts.md")
    if not os.path.isfile(fp):
        R.add("warn", "出典", "事実の一覧（%s）がありません。調べた事実と出典を先にまとめる" % os.path.basename(fp))
    else:
        ftext = open(fp, encoding="utf-8").read()
        fnorm = norm(ftext)
        facts = [x for x in ftext.splitlines() if re.match(r"^\s*-\s*\[F\d+\]", x)]
        for x in facts:
            if "http" not in x:
                R.add("warn", "出典", "出典の URL が無い事実: %s" % x.strip()[:40])
        stats["事実"] = "%d 件" % len(facts)
        miss = {}
        for l in L:
            for x in numbers(l["text"]):
                if x not in fnorm:
                    miss.setdefault(x, l["no"])
        for S in scenes:
            for x in numbers(board_text(S["board"]) if S["board"] else ""):
                if x not in fnorm:
                    miss.setdefault(x, (S["lines"] or [{}])[0].get("no"))
            for x in numbers(S.get("tag", "") or ""):
                if x not in fnorm:
                    miss.setdefault(x, (S["lines"] or [{}])[0].get("no"))
        if miss:
            R.add("warn", "出典", "事実の一覧に無い数字: %s。出典を足すか、台本から外す" % "、".join("%s（%s 行目）" % kv for kv in miss.items()))
    # 9. 仕上げ（別の目でのファクトチェックと見直しが済んでいるか）
    stem = os.path.splitext(os.path.abspath(path))[0]
    fc = stem + ".factcheck.md"
    if not os.path.isfile(fc):
        R.add("info", "仕上げ", "ファクトチェックがまだです（fact-check スキル。別のエージェントに渡す）")
    else:
        t = open(fc, encoding="utf-8").read()
        vs = re.findall(r"(?m)^- 判定:[ \t]*(\S*)", t)
        left = [v for v in vs if v.startswith(("食い違う", "言いすぎ", "確かめられない"))]
        stats["ファクトチェック"] = "%d 件（直す所 %d・判定なし %d）" % (len(vs), len(left), sum(1 for v in vs if not v))
        if any(not v for v in vs):
            R.add("warn", "仕上げ", "ファクトチェックに、判定の無い主張が %d 件あります" % sum(1 for v in vs if not v))
        if left:   # 直したかどうかは、ここからは分からない（結果のファイルは直す前の台本を見たもの）
            R.add("info", "仕上げ", "ファクトチェックで直す所が %d 件出ています（食い違う・言いすぎ・確かめられない）。台本に反映したかを確かめる" % len(left))
    rv = stem + ".review.md"
    if not os.path.isfile(rv):
        R.add("info", "仕上げ", "見直しがまだです（review.md の観点。別のエージェントに渡す）")
    else:
        t = open(rv, encoding="utf-8").read()
        sc = [int(x) for x in re.findall(r"(?m)^- [A-E] [^:：]*[:：]\s*([1-5])", t)]
        verdict = (re.search(r"(?m)^- 総合[:：]\s*(\S+)", t) or [None, ""])[1]
        stats["見直し"] = "%s（%s）" % (verdict or "判定なし", "・".join(map(str, sc)) or "点数なし")
        if len(sc) < 5:
            R.add("warn", "仕上げ", "見直しの点数が 5 つそろっていません（A 構成・B わかりやすさ・C キャラクター・D 掛け合い・E 画面と演技）")
        elif min(sc) < 4:
            R.add("info", "仕上げ", "見直しに 3 点以下の観点があります。指摘を台本に反映したかを確かめる（見直しは 2 回まで）")
    return R, stats


def main():
    ap = argparse.ArgumentParser(description="掛け合いの台本を検査する")
    ap.add_argument("script")
    ap.add_argument("--facts", help="事実の一覧（Markdown。「- [F1] 事実 — 出典: URL」の行）")
    ap.add_argument("--stats", action="store_true", help="数字だけ出す")
    ap.add_argument("--strict", action="store_true", help="warn でも終了コード 1")
    a = ap.parse_args()
    R, stats = run(a.script, a.facts)
    print("# 台本の数字")
    for k, v in stats.items():
        print("  %s: %s" % (k, v))
    if a.stats:
        return
    for level, label in (("error", "直す"), ("warn", "見直す"), ("info", "参考")):
        items = [i for i in R.items if i[0] == level]
        if items:
            print("# %s（%d）" % (label, len(items)))
            for _, group, msg in items:
                print("  [%s] %s" % (group, msg))
    e, w = R.count("error"), R.count("warn")
    print("OK : 直す所はありません" if not e and not w else "結果: 直す %d・見直す %d" % (e, w))
    sys.exit(1 if e or (a.strict and w) else 0)


if __name__ == "__main__":
    main()
