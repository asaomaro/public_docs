#!/usr/bin/env python3
"""ファクトチェックの道具。文章から確かめる主張の候補を拾い、引用が出どころに本当にあるかを確かめ、判定の表を点検する。

  python3 claims.py extract 文章.md -o 文章.factcheck.md   # 主張の候補を拾って、判定の表のひな形を書く（台本・Markdown・テキスト）
  python3 claims.py page <URL>                            # ページの本文をそのまま出す（要約を通さずに原文を読む）
  python3 claims.py quote <URL> "引用した文"               # その文が、ページに本当に書いてあるか（ページを直に読んで照らす）
  python3 claims.py verify 文章.factcheck.md               # 表の中の引用（「…」）を、同じ主張の出典のページとまとめて照らす（事実の一覧 facts.md にも使える）
  python3 claims.py lint 文章.factcheck.md                 # 判定の表の抜け（判定・根拠・出典）を点検し、数をまとめる

読んだページは ~/.cache/fact-check/ に 1 日だけ覚えておく（同じページを何度も取りに行かない）。

手順は SKILL.md。標準ライブラリだけで動く。
"""
import argparse, hashlib, html, os, re, sys, time, unicodedata, urllib.parse, urllib.request

UA = "fact-check-skill/1.0 (https://github.com/asaomaro/public_docs; Python urllib)"
VERDICTS = ["確認できた", "食い違う", "言いすぎ", "確かめられない", "対象外"]
UNIT = r"(?:%|％|倍|年|月|日|世紀|時間|分|秒|万|億|兆|円|ドル|人|件|個|本|回|種|位|歳|才|度|km|m|cm|mm|nm|kg|g|t|トン|キロ|メートル|グラム|パーセント|か国|カ国|社|台|頭|匹)"
KINDS = [   # (種類, 見つけ方, 危なさ 3 が高い)
    ("数字", re.compile(r"\d[\d,\.]*\s*" + UNIT + r"|\d{2,}"), 3),
    ("年・日付", re.compile(r"\d{3,4}\s*年|\d{1,2}\s*世紀|\d{1,2}\s*月\s*\d{1,2}\s*日|昭和|平成|令和|明治|大正"), 3),
    ("言い切り", re.compile(r"初めて|はじめて|最初|最大|最小|最古|最新|最高|最も|もっとも|唯一|世界一|日本一|必ず|絶対|すべて|全て|全部|誰も|どこにも|一度も|常に|100\s*[%％]"), 3),
    ("比べる", re.compile(r"より(多|少|大き|小さ|高|低|速|遅|強|弱|長|短)|の\s*\d[\d\.]*\s*倍|上回|下回|に次ぐ"), 2),
    ("原因・仕組み", re.compile(r"ため(に|、|だ|です|な)|によって|が原因|おかげで|せいで|その結果|だから|ので、|からよ|からだ|からなの"), 2),
    ("人・組織がした", re.compile(r"(発見|発明|提唱|証明|開発|設立|創業|発表|命名|解明|計算|制定|導入)(し|した|され|の)"), 2),
    ("引用・伝聞", re.compile(r"と(言った|述べた|書いた|語った|発表した)|によると|によれば|「[^」]{8,}」と"), 2),
    ("今の状態", re.compile(r"現在|今は|今では|今も|最近|近年|いまだに|時点"), 2),
    ("固有名詞", re.compile(r"[ァ-ヶー]{4,}|[A-Z][A-Za-z0-9\-]{2,}"), 1),
]
STATEMENT = re.compile(r"(だ|である|です|ます|なの|のよ|わ|よ|んだ|だぜ|なのだ|のだ|ている|ていた|した|れる|いる|ある)[。．！!]*$")   # 言い切りの形で終わる、説明の文
HEDGE = re.compile(r"と言われ|とされ|らしい|かもしれ|と考えられ|という説|諸説|可能性")
LINE_RE = re.compile(r"^([\w\-]+)(?:[（(][^)）]*[)）])?\s*[:：]\s*(.*?)\s*(?:\[[^\]]+\])?\s*$")


def clean_url(u):
    """文の中から拾った URL の末尾の句読点・閉じかっこを落とす。ただし URL の中で開いたかっこ（React_(software) など）の閉じは残す。"""
    u = u.rstrip("、。，．")
    while u.endswith(")") and u.count(")") > u.count("("):
        u = u[:-1]
    return u.rstrip("、。）")


def norm(s):
    return re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", s)).lower()


def units(path):
    """文章を、確かめる単位（文・せりふ・画面の言葉）に分ける。[(行番号, だれ／どこ, 文)]"""
    text = open(path, encoding="utf-8").read()
    out, script = [], bool(re.match(r"^---\s*\n.*?\n---\s*\n", text, re.S)) and bool(re.search(r"^[\w\-]+(\(.*?\))?\s*[:：]", text, re.M))
    head_end = text.find("\n---", 4) if text.startswith("---") else -1
    skip_until = text[:head_end].count("\n") + 2 if head_end > 0 else 0
    chapter = ""
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if script and no <= skip_until:   # 台本の設定のうち、人の目に触れる文（題・概要・サムネイルの文字）
            m = re.match(r"^(title|summary|thumb|end_title)\s*:\s*(.+)$", line)
            if m:
                out.append((no, "設定の " + m.group(1), m.group(2).replace("|", " ")))
            continue
        if no <= skip_until or not line:
            continue
        if script:
            if line.startswith("# "):
                chapter = line[2:].strip()
                continue
            if line.startswith(("//", ">", "＞")) or re.match(r"^[（(]\s*(間|pause)", line):
                continue
            if line.startswith("@"):
                m = re.match(r"^@(show|board|tag|corner)\s*[:：]?\s*(.*)$", line)
                if m and m.group(1) == "show":   # 絵の並び: 絵の名前と名札の組（絵が中身と合っているかも確かめる）、短い言葉、note・title
                    for cell in [c.strip() for c in m.group(2).split("|")]:
                        mm = re.match(r"^(note|title)\s*[:：]\s*(.+)$", cell)
                        pic = re.match(r'^([^\s"]+)\s+"([^"]+)"(?:\s*>\s*"([^"]+)")?', cell)
                        if mm:
                            out.append((no, "画面の" + ("一言" if mm.group(1) == "note" else "見出し"), mm.group(2)))
                        elif pic:
                            out.append((no, "画面の絵「%s」の名札" % pic.group(1), pic.group(2) + ("（吹き出し: %s）" % pic.group(3) if pic.group(3) else "")))
                        elif cell.startswith('"'):
                            out.append((no, "画面の言葉", re.sub(r'"\s*\w*$', "", cell.strip('"')).replace("/", " ").replace("**", "")))
                elif m:
                    out.append((no, "画面" + ("・" + chapter if chapter else ""), m.group(2).replace("**", "")))
                continue
            m = LINE_RE.match(line)
            if m:
                out.append((no, m.group(1) + ("・" + chapter if chapter else ""), m.group(2).replace("|", "")))
            continue
        if line.startswith(("```", "|--", "|:-")):
            continue
        line = re.sub(r"^#+\s*|^[-*]\s+|^\d+\.\s+|\*\*|`", "", line)
        for s in re.split(r"(?<=[。！？!?])\s*", line):
            if len(s.strip()) >= 6:
                out.append((no, "", s.strip()))
    return out, script


def kinds_of(s):
    t = unicodedata.normalize("NFKC", s)
    ks = [(k, r) for k, pat, r in KINDS if pat.search(t)]
    if len(t) >= 12 and STATEMENT.search(t) and not re.search(r"[?？]", t) and not any(k != "固有名詞" for k, _ in ks):
        ks.append(("説明の文", 1))
    return [k for k, _ in ks], max([r for _, r in ks] or [0])


def extract(path, out, every=False):
    us, script = units(path)
    rows = []
    for i, (no, who, s) in enumerate(us):
        ks, risk = kinds_of(s)
        if who.startswith(("設定", "画面の")):   # 題・サムネイル・画面の文字は、短くても必ず確かめる（目立つ所の誤りほど響く）
            ks, risk = ks or ["画面・題の文字"], max(risk, 2 if who.startswith("設定") else 1)
        if not ks or (ks == ["固有名詞"] and not every):
            continue
        note = []
        if HEDGE.search(s):
            note.append("言い方がぼかしてある")
        if script and who and not who.startswith("画面") and "茶番" in who:
            note.append("茶番の章（おふざけ。事実として言っているものだけ確かめる）")
        speaker = who.split("・")[0]
        nxt = next((x[2] for x in us[i + 1:i + 3] if x[1] and not x[1].startswith(("画面", "設定")) and x[1].split("・")[0] != speaker), "")
        if script and not who.startswith(("画面", "設定")) and re.search(r"勘違い|間違|誤解|そんなわけ|違うわよ|違うぜ|ちがうわよ|じゃないわよ|じゃないぜ|ないわよ[。！]|ないぜ[。！]", nxt):
            note.append("直後に訂正されている（ボケなら対象外。訂正のほうを確かめる）")
        rows.append((risk, no, who, s, ks, note))
    merged = {}   # 同じ文（画面に何度も出る名札など）は 1 つにまとめ、場所を並べる
    for risk, no, who, s, ks, note in rows:
        m = merged.setdefault(norm(s), [risk, no, who, s, ks, note, []])
        m[0] = max(m[0], risk)
        if no != m[1]:
            m[6].append(no)
    rows = [tuple(m[:6]) + (m[6],) for m in merged.values()]
    rows.sort(key=lambda r: (-r[0], r[1]))
    lines = ["# ファクトチェック: %s" % path, "", "確かめた日: （日付）　確かめた人: （書いた本人とは別の目で）", "",
             "判定は %s のどれか。確認できた・食い違う・言いすぎ には、根拠（出どころの原文の引用）と出典（URL）を書く。" % "・".join(VERDICTS), ""]
    for n, (risk, no, who, s, ks, note, more) in enumerate(rows, 1):
        lines += ["### C%d %s" % (n, s), "- 場所: %d 行目%s%s" % (no, "（%s）" % who if who else "", "。ほかに %s 行目" % "・".join(map(str, more)) if more else ""), "- 種類: %s%s" % ("・".join(ks), "　※" + "。".join(note) if note else ""),
                  "- 判定: ", "- 根拠: ", "- 出典: ", "- 直し方: ", ""]
    lines[4:4] = ["同じ主張が別の場所（画面とせりふ、本文とまとめ）にもあるときは、2 つ目からは「- 同じ: C6」とだけ書けば、判定・根拠・出典は要らない（直し方は書く）。",
                  "1 つの文に主張が 2 つあるとき（年と人）は、### C6a・### C6b のように分ける。", ""]
    lines += ["## 拾い切れていない主張（読んで足す）", "", "数字の無い事実（〜は〜である、〜が〜した）は、上の一覧に出ないことがある。文章を頭から読んで、ここに C の続きの番号で足す。", ""]
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    print("OK : %s（候補 %d 件。危なさの高い順。%d 件の文・せりふから）" % (out, len(rows), len(us)))


CACHE = os.path.join(os.path.expanduser("~"), ".cache", "fact-check")


def page_text(url):
    """ページの本文（タグを除いた文字）。日本語の入った URL はそのまま渡してよい。1 日は覚えておく。"""
    url = urllib.parse.quote(url.strip(), safe=":/?&=#%+@,;~()!*'$-._")
    cf = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".txt")
    if os.path.isfile(cf) and time.time() - os.path.getmtime(cf) < 86400:
        return open(cf, encoding="utf-8").read()
    text = fetch_text(url)
    os.makedirs(CACHE, exist_ok=True)
    open(cf, "w", encoding="utf-8").write(text)
    return text


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en"})
    data = urllib.request.urlopen(req, timeout=60)
    ctype = data.headers.get("Content-Type", "")
    raw = data.read()
    if "pdf" in ctype or raw[:4] == b"%PDF":
        try:
            import io
            from pypdf import PdfReader
            return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
        except ImportError:
            sys.exit("error: PDF を読むには pypdf が要ります（pip install pypdf）。または、ページを自分で開いて確かめる")
    m = re.search(rb"charset=[\"']?([\w\-]+)", raw[:3000])
    t = raw.decode(m.group(1).decode() if m else "utf-8", "replace")
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
    return html.unescape(re.sub(r"(?s)<[^>]+>", " ", t))


def found(url, text):
    """引用がページにあるか（空白と全角・半角の違いは無視）。表のセルをまたぐ引用は、セルの間を空白にして書く。"""
    Q = norm(text)
    return bool(Q) and Q in norm(page_text(url))


URL_RE = re.compile(r"https?://[^\s　、）]+")
QUOTE_RE = re.compile(r"「([^」]+)」")
SHORT = 10   # 判定の表の根拠では、これより短い「」は語（引用でない）とみて照らさない。照らさなかった数は必ず出す


def quotes_of(text):
    """照らす引用を、書かれた場所ごとに集める。[(名前, [引用], [URL], [(照らさなかった引用, 理由)])]

    事実の一覧は「原文:」のある行ごと（小見出し ### があってもなくても、全部の行）。判定の表は ### のかたまりごとの「- 根拠:」。"""
    out, n = [], 0
    for no, line in enumerate(text.splitlines(), 1):   # 事実の一覧: 1 行に 事実 — 原文: 「…」 — 出典: URL
        if not re.search(r"原文[:：]", line) or re.match(r"\s*- 根拠[:：]", line):
            continue
        n += 1
        m = re.search(r"\[(F\w+)\]", line)
        cid = m.group(1) if m else "%d 行目" % no
        qs = [q for seg in re.findall(r"原文[:：](.*?)(?=—\s*出典|出典[:：]|$)", line) for q in QUOTE_RE.findall(seg)]
        urls = [clean_url(u) for u in URL_RE.findall(line)]
        skip = []
        if not qs:
            skip.append(("（原文: の後に「…」がありません）", "引用が無い"))
        elif not urls:
            skip, qs = [(q, "同じ行に出典の URL が無い") for q in qs], []
        out.append((cid, qs, urls, skip))
    for b in re.split(r"(?m)^### ", text)[1:]:   # 判定の表
        m2 = re.search(r"(?m)^- 根拠[:：](.*)$", b)
        if not m2:
            continue
        cid, head = (b.split() or ["?"])[0], b.splitlines()[0]
        urls = [clean_url(u) for u in URL_RE.findall(b)]
        qs, skip = [], []
        for q in QUOTE_RE.findall(m2.group(1)):
            if norm(q) in norm(head):   # 見出し（確かめている文）と同じ言葉は、出どころの引用ではない
                skip.append((q, "確かめている文そのもの（出どころの引用ではない）"))
            elif len(q) < SHORT:
                skip.append((q, "%d 字より短い（語とみなした。引用なら quote で 1 つずつ照らす）" % SHORT))
            elif not urls:
                skip.append((q, "出典の URL が無い"))
            else:
                qs.append(q)
        out.append((cid, qs, urls, skip))
    return out


def verify(path):
    """判定の表（### ごとの「- 根拠:」）と事実の一覧（「原文:」のある行すべて）の引用「…」を、同じ所にある URL のページと照らす。

    照らさなかった引用があれば、数と理由を必ず出す（黙って OK にしない）。"""
    text = open(path, encoding="utf-8").read()
    ok = ng = 0
    skipped = []
    for cid, quotes, urls, skip in quotes_of(text):
        skipped += [(cid, q, why) for q, why in skip]
        for q in quotes:
            hit = False
            for u in urls:
                try:
                    if found(u, q):
                        hit = True
                        break
                except Exception as e:
                    print("  %s: ページを読めません（%s）: %s" % (cid, type(e).__name__, u), file=sys.stderr)
            ok, ng = ok + hit, ng + (not hit)
            if not hit:
                print("NG : %s の引用が、出典のどのページにも見つかりません: 「%s」" % (cid, q[:70] + ("…" if len(q) > 70 else "")))
    if skipped:
        why = {}
        for cid, q, w in skipped:
            why.setdefault(w, []).append("%s「%s」" % (cid, q[:40] + ("…" if len(q) > 40 else "")) if not q.startswith("（") else "%s %s" % (cid, q))
        print("照らさなかった引用: %d 個" % len(skipped))
        for w, xs in why.items():
            print("  %s: %d 個 — %s" % (w, len(xs), "、".join(xs)))
    hard = [s for s in skipped if "短い" not in s[2] and "確かめている文" not in s[2]]   # 引用も URL も無い行は、照らせていない（直す）
    if not ok + ng and not skipped:
        print("結果: 照らす引用が 1 つも見つかりません（事実の一覧は「原文: 「…」 — 出典: URL」、判定の表は「- 根拠: 「…」」と書く）")
        return 1
    print("%s : 引用 %d 個のうち、ページにあったもの %d・見つからないもの %d・照らさなかったもの %d" % ("OK" if not ng and not skipped else "結果", ok + ng + len(skipped), ok, ng, len(skipped)))
    return 1 if ng or hard else 0


def quote(url, text):
    """引用が、ページの本文に本当にあるか。空白と全角・半角の違いは無視する。無ければ、いちばん近い所を出す。"""
    page = page_text(url)
    P, Q = norm(page), norm(text)
    if Q and Q in P:
        i = P.index(Q)
        print("OK : 引用はページにあります")
        print("  前後: …%s【%s】%s…" % (P[max(0, i - 60):i], P[i:i + len(Q)], P[i + len(Q):i + len(Q) + 60]))
        return 0
    n = 8 if len(Q) >= 24 else 4
    grams = [Q[i:i + n] for i in range(0, max(1, len(Q) - n + 1), max(1, n // 2))]
    hit = [g for g in grams if g in P]
    print("NG : 引用どおりの文は、ページに見つかりません（%d 字ずつに切った %d 片のうち %d 片は見つかった）" % (n, len(grams), len(hit)))
    if hit:
        i = P.index(hit[0])
        print("  近い所: …%s…" % P[max(0, i - 80):i + 200])
    print("  要約の道具が言い換えた・作った文かもしれません。ページを開き直して、原文をそのまま写す")
    return 1


def lint(path):
    text = open(path, encoding="utf-8").read()
    blocks = re.split(r"(?m)^### ", text)[1:]
    counts, bad, todo, dup, verdict_of, weak = {v: 0 for v in VERDICTS}, [], [], [], {}, []
    for b in blocks:
        head = b.splitlines()[0].strip()
        cid = head.split()[0]
        f = {k: (re.search(r"(?m)^- %s:[ \t]*(.*)$" % k, b) or [None, ""])[1].strip() for k in ("場所", "種類", "判定", "根拠", "出典", "直し方")}
        same = re.search(r"(?m)^- 同じ:[ \t]*(C\w+)", b)
        if same:   # 別の場所にある同じ主張（判定は元の主張に従う。数には入れない）
            dup.append((cid, same.group(1), head[len(cid):].strip(), f["直し方"]))
            continue
        v = next((x for x in VERDICTS if f["判定"].startswith(x)), None)
        if not v:
            bad.append("%s: 判定がありません（%s のどれか）" % (cid, "・".join(VERDICTS)))
            continue
        counts[v] += 1
        verdict_of[cid] = v
        if v == "確認できた" and re.search(r"別の出どころでは未確認|出どころは 1 つだけ", f["根拠"]):
            weak.append("%s %s" % (cid, head[len(cid):].strip()[:44]))
        if v == "確認できた" and "「" not in f["根拠"] and "計算" not in f["根拠"]:
            bad.append("%s: 「確認できた」の根拠に、原文の引用（「…」）も計算もありません" % cid)
        if v in ("確認できた", "食い違う", "言いすぎ"):
            if "http" not in f["出典"]:
                bad.append("%s: 判定が「%s」なのに、出典の URL がありません" % (cid, v))
            if len(f["根拠"]) < 6:
                bad.append("%s: 判定が「%s」なのに、根拠（原文の引用か計算）がありません" % (cid, v))
        if v in ("食い違う", "言いすぎ", "確かめられない"):
            if f["直し方"] in ("", "—", "-", "なし"):
                bad.append("%s: 判定が「%s」なのに、直し方がありません（言い換える・ぼかす・外す）" % (cid, v))
            todo.append("%s（%s）%s → %s" % (cid, v, head[len(cid):].strip()[:36], f["直し方"][:60]))
        if v == "対象外" and len(f["根拠"]) < 2:
            bad.append("%s: 対象外にした理由（意見・たとえ・ボケ など）を根拠に書く" % cid)
    for cid, ref, head, fix in dup:
        v = verdict_of.get(ref)
        if not v:
            bad.append("%s: 「同じ: %s」の元の主張が見つかりません" % (cid, ref))
        elif v in ("食い違う", "言いすぎ", "確かめられない"):
            todo.append("%s（%s と同じ・%s）%s → %s" % (cid, ref, v, head[:30], (fix or "元の主張と同じに直す")[:60]))
    print("# 判定の数（%d 件。ほかに、同じ主張の別の場所 %d 件）" % (len(blocks) - len(dup), len(dup)))
    for v in VERDICTS:
        print("  %s: %d" % (v, counts[v]))
    if todo:
        print("# 文章を直す所（%d）" % len(todo))
        for t in todo:
            print("  " + t)
    if weak:
        print("# 確認できたが、支えが弱い所（%d。出どころが 1 つだけ。大事な主張なら、ぼかすか別の出どころを探す）" % len(weak))
        for t in weak:
            print("  " + t)
    if bad:
        print("# 判定の表の抜け（%d）" % len(bad))
        for x in bad:
            print("  " + x)
    print("OK : 判定の表に抜けはありません" if not bad else "結果: 抜け %d" % len(bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="ファクトチェックの道具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="主張の候補を拾って、判定の表のひな形を書く")
    e.add_argument("file")
    e.add_argument("-o", "--out")
    e.add_argument("--all", action="store_true", help="固有名詞だけの文も拾う")
    pg = sub.add_parser("page", help="ページの本文をそのまま出す")
    pg.add_argument("url")
    vf = sub.add_parser("verify", help="表の中の引用を、出典のページとまとめて照らす")
    vf.add_argument("file")
    q = sub.add_parser("quote", help="引用が、ページに本当にあるかを確かめる")
    q.add_argument("url")
    q.add_argument("text")
    l = sub.add_parser("lint", help="判定の表の抜けを点検する")
    l.add_argument("file")
    a = ap.parse_args()
    if a.cmd == "extract":
        extract(a.file, a.out or re.sub(r"\.\w+$", "", a.file) + ".factcheck.md", a.all)
    elif a.cmd == "quote":
        sys.exit(quote(a.url, a.text))
    elif a.cmd == "page":
        print(re.sub(r"[ \t]*\n\s*", "\n", re.sub(r"[ \t]+", " ", page_text(a.url))).strip())
    elif a.cmd == "verify":
        sys.exit(verify(a.file))
    else:
        sys.exit(lint(a.file))


if __name__ == "__main__":
    main()
