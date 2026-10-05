#!/usr/bin/env python3
"""ask-form — 質問をまとめて 1 つの単発ウィンドウに出し、回答を JSON で受け取る。

  python3 ask.py spec.json        # 質問の定義（JSON）をファイルで渡す
  python3 ask.py - < spec.json    # 標準入力で渡す
  python3 ask.py --review out.html notes.md   # 成果物を見せて、承認・修正の依頼・中止を聞く（定義は要らない）
  python3 ask.py --selftest       # 人の操作なしで、開く→答える→閉じる を確かめる（定義も渡せる）

標準出力に 1 行の JSON を出して終わる。終了コード:
  0 answered     回答あり           {"status":"answered","answers":{...}}
  1 error        定義の誤りなど     （標準エラーに理由）
  2 cancelled    回答せずに閉じた   {"status":"cancelled"}
  3 unavailable  ウィンドウを出せない・画面の前に人がいない → 呼び出し側は AskUserQuestion に切り替える
  4 timeout      時間切れ           {"status":"timeout"}

Python3 の標準ライブラリだけで動く。ウィンドウは Chromium 系ブラウザ（Edge / Chrome など）の
--app モードで開く（タブ・アドレスバーの無い単独のウィンドウ）。

環境変数:
  ASK_FORM=off              ウィンドウを出さず、必ず unavailable を返す（画面の前に人がいない
                            マシンで動かすとき。例: 外からつなぐブラウザ版ターミナルのサーバー側）
  ASK_FORM_BROWSER=パス     使うブラウザを指定する
  ASK_FORM_SODA=off         Sodashitsu の pane の中でも、sodactl ask を使わずにウィンドウを開く

窓では、定義の image の外部 URL（https://…）を、ブラウザではなくこの ask.py が取って（remote_image.py。SSRF 対策つき）受け口から配る（利用者の IP が取得先に見えない）。
取れなかった画像は画像なしで出し、窓の固定の行と標準エラーに知らせる。成果物（HTML）の枠は sandbox="allow-scripts" のみ（popup・download なし）。Markdown の枠だけ、リンクを新しいタブで開ける（http(s) のみ）。

Sodashitsu（soda）の pane の中で動いているとき（SODA_PANE_ID があり sodactl が PATH にある）は、
ウィンドウを開く前に sodactl ask へ渡し、その pane を見ているブラウザの画面にフォームを出す
（ブラウザが別のマシンでも届く。ASK_FORM=off でも行う）。画像・音・コード・成果物（view）・edit・rank・table を
使う定義は、sodactl ask --features で、sodactl とサーバがそれを出せると確かめてから渡す。出せないとき——
つながっているブラウザが無い・古い sodactl／soda・機能が足りない——は、今までどおりこのマシンのウィンドウへ進む。
上限（ファイルの大きさ・個数）の超過と、sodactl が定義の誤りとした（終了コード 2）ときは、窓へ落とさず終了コード 1 で理由を出す。
  ASK_FORM_AWAY_SECONDS=秒  --away-after の既定（300）
  ASK_FORM_REACT_SECONDS=秒 --react-within の既定（90）
"""
import argparse
import atexit
import base64
import glob
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remote_image  # noqa: E402  外部 URL の画像を ask.py が取る（取得と SSRF 対策。標準ライブラリだけ）
EXIT = {"answered": 0, "error": 1, "cancelled": 2, "unavailable": 3, "timeout": 4}
TYPES = ("single", "multi", "text", "edit", "rank", "table")
CHOICE_TYPES = ("single", "multi", "rank", "table")   # options を持つ型
PREVIEWS = ("side", "inline")
SCALAR = (str, int, float, bool)
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".avif": "image/avif", ".svg": "image/svg+xml"}
AUDIO_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".oga": "audio/ogg",
               ".opus": "audio/ogg", ".m4a": "audio/mp4", ".aac": "audio/aac", ".flac": "audio/flac"}
# 見せる成果物（定義の view）。HTML は隔離した枠に、画像はそのまま、ほかは文字として出す
VIEW_HTML = {".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8"}
VIEW_MARKDOWN = (".md", ".markdown")   # 整形して見せる（viewer.html が、同梱の marked・mermaid で描く）
VIEW_LIBS = {"marked.umd.js": "text/javascript; charset=utf-8", "mermaid.min.js": "text/javascript; charset=utf-8"}   # 配ってよい同梱のライブラリ（vendor/）
VIEW_TEXT_MAX = 2 * 1024 * 1024   # 文字として出すファイルの大きさの上限
# 枠の中に許すこと（同じ origin としては扱わない）。HTML・text・image の成果物は、スクリプトだけ。
# allow-popups は付けない（スクリプトが動く枠で popup を許すと、URL に本文を載せて外へ出せる）・allow-downloads も付けない。form.html の iframe の属性と同じ値にする
VIEW_SANDBOX = "allow-scripts"
# Markdown の整形ページの枠だけ、リンクを新しいタブで開けるよう popup を許す（Markdown の枠はスクリプトが動かない〔marked の出力から script を除く〕ので、
# popup の URL に本文を載せて外へ出す害が成り立たない。リンクは viewer.html が http(s) のものだけ残し、noopener noreferrer を付ける）。
# 開いた先は隔離を引き継がない（allow-popups-to-escape-sandbox）。allow-same-origin・allow-top-navigation 系は付けない。form.html の Markdown の iframe の属性と同じ値にする
VIEW_SANDBOX_MD = "allow-scripts allow-popups allow-popups-to-escape-sandbox"
MEDIA_FILE_MAX = remote_image.MAX_BYTES   # 画像・音 1 ファイルの上限（8 MiB。data: も外部 URL の取得も同じ）
MEDIA_TOTAL_MAX = 24 * 1024 * 1024        # 外部 URL から取る画像の合計の上限（Sodashitsu の 1 つの質問の合計と同じ）
MEDIA_REMOTE_MAX = 32                     # 取りに行く外部 URL の数の上限（超えた分は取らず、画像なしで出す）
TIMEOUT = 540                     # 回答を待つ秒数の既定
TIMEOUT_VIEW = 3540               # 成果物を見せるときの既定（読む時間が要る）
OPEN_WAIT = 20      # ウィンドウがつながるまで待つ秒数（超えたら unavailable）
CLOSE_GRACE = 2.5   # 接続が切れてから「閉じられた」とみなすまでの秒数（再読み込みを許す）

SELFTEST_SPEC = {
    "title": "ask-form の動作確認",
    "intro": "このウィンドウは自動で回答して閉じます。",
    "questions": [
        {"id": "color", "label": "色", "type": "single", "default": "blue",
         "options": [{"value": "blue", "label": "青"}, {"value": "red", "label": "赤"}]},
        {"id": "extras", "label": "追加", "type": "multi", "default": ["a"],
         "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]},
    ],
}


# ── 質問の定義を検査して、既定を埋める ─────────────────────────────────────
def data_uri_size(ref):
    """data: URI の本文の大きさ（復号した後のバイト数）。"""
    head, _, payload = ref.partition(",")
    if head.rstrip().endswith(";base64"):
        payload = payload.strip()
        return len(payload) * 3 // 4 - payload.count("=", max(len(payload) - 2, 0))
    return len(urllib.parse.unquote_to_bytes(payload))


class SpecError(ValueError):
    """定義の誤り。reason は誤りの分類（fixtures/normalize.json と、同じ検査をする Sodashitsu とで共通の名前）。"""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def normalize(spec, base_dir=".", view_text_max=VIEW_TEXT_MAX):
    """定義を検査して既定を埋める。選択肢の image・audio がローカルのファイルなら、受け口から配る番号付きの
    アドレス（file/N）に書き換え、(パス, 種類) の一覧を spec["_files"] に入れる。"""
    files = []

    def local_file(o, key, types, where):
        ref = o.get(key)
        if not ref or re.match(r"^(https?://|data:)", ref):
            if isinstance(ref, str) and ref.startswith("data:") and data_uri_size(ref) > MEDIA_FILE_MAX:
                raise SpecError("too_large", "%s: data: が大きすぎます（%d MiB まで）" % (where, MEDIA_FILE_MAX // 1024 // 1024))
            return
        path = os.path.join(base_dir, os.path.expanduser(ref))
        ctype = types.get(os.path.splitext(path)[1].lower())
        if not ctype:
            raise SpecError("media_type", "%s: %s は %s のいずれか（%s）" % (where, key, " / ".join(sorted(types)), ref))
        if not os.path.isfile(path):
            raise SpecError("media_missing", "%s: %s のファイルがありません（%s）" % (where, key, path))
        files.append((os.path.abspath(path), ctype))
        o[key] = "file/%d" % (len(files) - 1)

    def items(q, key, where):
        lst = q.get(key)
        if not isinstance(lst, list) or not lst:
            raise SpecError("options_empty", "%s: %s に 1 つ以上入れてください" % (where, key))
        for j, o in enumerate(lst):
            if isinstance(o, str):
                o = lst[j] = {"value": o, "label": o}
            if not isinstance(o, dict) or "value" not in o:
                raise SpecError("option_value_required", "%s.%s[%d]: value が必要です" % (where, key, j))
            o["value"] = str(o["value"])
            if not isinstance(o.get("label"), str):
                o["label"] = o["value"]
            if o.get("recommended") is True:
                o["recommended"] = True
            else:
                o.pop("recommended", None)
            colors = [c for c in o["colors"] if isinstance(c, str) and COLOR_RE.match(c)][:16] if isinstance(o.get("colors"), list) else []
            if colors:
                o["colors"] = colors
            else:
                o.pop("colors", None)
        values = [o["value"] for o in lst]
        if len(set(values)) != len(values):
            raise SpecError("option_value_duplicate", "%s: %s の value が重複しています" % (where, key))
        return lst

    if not isinstance(spec, dict) or not isinstance(spec.get("questions"), list) or not spec["questions"]:
        raise SpecError("questions_empty", '"questions" に質問を 1 つ以上入れてください')
    paging = spec.get("paging")
    if not (paging in (None, "auto") or isinstance(paging, bool) or (isinstance(paging, int) and paging >= 1)):
        raise SpecError("paging_invalid", '"paging" は "auto"（高さに収まらないときだけ目次を出す）/ true（必ず出す）/ false（出さない）')
    seen = set()
    for i, q in enumerate(spec["questions"]):
        where = "questions[%d]" % i
        if not isinstance(q, dict) or not q.get("id") or not q.get("label"):
            raise SpecError("id_label_required", "%s: id と label が必要です" % where)
        if q["id"] in seen:
            raise SpecError("id_duplicate", "%s: id「%s」が重複しています" % (where, q["id"]))
        seen.add(q["id"])
        if q.get("page") is not None and not isinstance(q["page"], str):
            raise SpecError("page_invalid", "%s: page はまとまりの題（文字列）で渡してください" % where)
        q.setdefault("type", "single")
        if q["type"] not in TYPES:
            raise SpecError("unknown_type", "%s: type は %s のいずれか" % (where, " / ".join(TYPES)))
        # 部品（ask-form.js）が受ける形に揃える（fixtures/normalize.json の「正規化後」。Sodashitsu の normalizeAskSpec と同じ形）
        q["allowOther"] = q.get("allowOther") is True
        q["required"] = (q.get("required") is not False) if q["type"] == "edit" else (q.get("required") is True)
        q["multiline"] = q.get("multiline") is True
        mw = q.get("minWidth")
        if not (isinstance(mw, int) and not isinstance(mw, bool) and 60 <= mw <= 600):
            q.pop("minWidth", None)
        if q["type"] == "text" and not isinstance(q.get("default"), str):
            q.pop("default", None)
        sif = q.get("showIf")
        if not sif:
            q.pop("showIf", None)
        elif not isinstance(sif, dict):
            raise SpecError("showif_invalid", "%s: showIf は {質問の id: 値} で渡してください" % where)
        else:
            q["showIf"] = {str(k): [str(x) for x in (v if isinstance(v, list) else [v]) if isinstance(x, SCALAR)] for k, v in sif.items()}
        if q["type"] == "single" and isinstance(q.get("default"), list):
            q["default"] = q["default"][0] if q["default"] else None
        if q["type"] == "single" and q.get("default") is not None:
            q["default"] = str(q["default"])
        if q["type"] == "multi" and isinstance(q.get("default"), list):
            q["default"] = [str(x) for x in q["default"] if isinstance(x, SCALAR)]
        if q.get("default") is None:
            q.pop("default", None)
        if q["type"] not in CHOICE_TYPES:
            q["options"] = []
            continue
        for j, o in enumerate(items(q, "options", where)):
            ow = "%s.options[%d]" % (where, j)
            if "code" in o and not isinstance(o["code"], str):
                raise SpecError("code_invalid", "%s: code は文字列で渡してください" % ow)
            local_file(o, "image", IMAGE_TYPES, ow)
            local_file(o, "audio", AUDIO_TYPES, ow)
        if q["type"] == "table":
            values = {o["value"] for o in q["options"]}
            for j, r in enumerate(items(q, "rows", where)):
                if r.get("default") is not None and str(r["default"]) not in values:
                    raise SpecError("row_default_unknown", "%s.rows[%d]: default「%s」が options にありません" % (where, j, r["default"]))
        if q.get("preview") not in (None,) + PREVIEWS:
            raise SpecError("preview_invalid", "%s: preview は %s のいずれか" % (where, " / ".join(PREVIEWS)))
        if q["type"] == "multi" and isinstance(q.get("default"), str):
            q["default"] = [q["default"]]
    if not isinstance(spec.get("title"), str):
        spec["title"] = "質問"
    if not isinstance(spec.get("submit"), str):
        spec["submit"] = "決定"
    if isinstance(spec.get("note"), str):       # 補足の欄の入力例
        spec["notePlaceholder"] = spec["note"]
    spec["note"] = spec.get("note") is not False
    if spec.get("comments") is not False:       # 質問ごとの自由記述（既定で付く）。付けないときだけ false を残す
        spec.pop("comments", None)
    for q in spec["questions"]:
        if q.get("comment") is not False:
            q.pop("comment", None)
    views = normalize_view(spec, base_dir, view_text_max)
    for i, q in enumerate(spec["questions"]):
        for dep in (q.get("showIf") or {}):
            if dep not in seen:
                raise SpecError("showif_unknown_id", "questions[%d].showIf: 「%s」という id の質問がありません" % (i, dep))
    spec["_files"] = files
    spec["_views"] = views
    return spec


def normalize_view(spec, base_dir, view_text_max=VIEW_TEXT_MAX):
    """定義の view（質問の横に見せる成果物）を検査する。1 つ（辞書かパス）か、いくつか（配列。タブで切り替える）。
    項目は file（ファイル）か text（その場の文字）と、任意の title。HTML・画像・Markdown は受け口から配る番号付きのアドレス（view/N）に書き換え、
    (パス, 種類) の一覧を返す（Markdown の種類は "markdown"。配るときに、整形して見せるページにする）。
    ほかのファイル（テキスト・コード）と、"raw": true を付けた Markdown は、中身を文字として定義に入れる。"""
    raw = spec.get("view")
    if raw is None:
        spec.pop("view", None)
        return []
    items = raw if isinstance(raw, list) else [raw]
    if not items:
        raise SpecError("view_invalid", '"view" に、見せるものを 1 つ以上入れてください')
    out, served = [], []
    for i, v in enumerate(items):
        where = "view[%d]" % i if isinstance(raw, list) else "view"
        if isinstance(v, str):
            v = {"file": v}
        if not isinstance(v, dict) or (("file" in v) == ("text" in v)):
            raise SpecError("view_invalid", "%s: file（ファイル）か text（文字）のどちらか 1 つを書いてください" % where)
        if "text" in v:
            if not isinstance(v["text"], str):
                raise SpecError("view_invalid", "%s: text は文字列で渡してください" % where)
            out.append({"title": str(v.get("title") or "テキスト"), "kind": "text", "text": v["text"]})
            continue
        if not isinstance(v["file"], str) or not v["file"]:
            raise SpecError("view_invalid", "%s: file はファイルのパスで渡してください" % where)
        path = os.path.abspath(os.path.join(base_dir, os.path.expanduser(v["file"])))
        if not os.path.isfile(path):
            raise SpecError("view_missing", "%s: ファイルがありません（%s）" % (where, path))
        ext = os.path.splitext(path)[1].lower()
        item = {"title": str(v.get("title") or os.path.basename(path)), "path": path}
        if ext in VIEW_HTML or ext in IMAGE_TYPES:
            served.append((path, VIEW_HTML.get(ext) or IMAGE_TYPES[ext]))
            item.update(kind="html" if ext in VIEW_HTML else "image", src="view/%d" % (len(served) - 1))
        elif ext in VIEW_MARKDOWN and v.get("raw") is not True:
            if os.path.getsize(path) > view_text_max:
                raise SpecError("view_invalid", "%s: Markdown が大きすぎます（%d MB まで）" % (where, VIEW_TEXT_MAX // 1024 // 1024))
            served.append((path, "markdown"))
            item.update(kind="markdown", src="view/%d" % (len(served) - 1))
        else:
            if os.path.getsize(path) > view_text_max:
                raise SpecError("view_invalid", "%s: 文字として出すには大きすぎます（%d MB まで。HTML にして渡してください）" % (where, VIEW_TEXT_MAX // 1024 // 1024))
            try:
                item.update(kind="text", text=open(path, encoding="utf-8").read())
            except UnicodeDecodeError:
                raise SpecError("view_invalid", "%s: 文字として読めません（HTML・画像・UTF-8 のテキストを渡してください）" % where)
        out.append(item)
    spec["view"] = out
    spec.setdefault("paging", False)   # 質問の欄は幅が狭いので、目次は出さない（書いてあればそれに従う）
    return served


def localize_remote_media(spec, files, tmpdir, fetch=None, workers=4):
    """定義の image の外部 URL（https://…）を、ask.py が取って一時ファイルに保存し、ローカルのファイルと同じ配り方（file/N）に書き換える。
    取れなかった画像は、画像なしにする（image を外す）。外部 URL の音（audio）は、Sodashitsu の画面内と同じく出さない（外す）。
    同じ URL は 1 回だけ取る。取りに行く数・合計の大きさには上限がある（超えた分は取らず、画像なしにする）。
    → (取れなかった画像の件数〔URL の重複をまとめた数〕, 外した外部 URL の音の件数)。理由は定義の中身を含めず標準エラーに出す。"""
    fetch = fetch or remote_image.fetch_image
    slots, audio_skipped = {}, 0
    for q in spec.get("questions", []):
        for o in q.get("options", []):
            ref = o.get("audio")
            if isinstance(ref, str) and re.match(r"^https?://", ref, re.I):
                del o["audio"]
                audio_skipped += 1
            ref = o.get("image")
            if isinstance(ref, str) and re.match(r"^https?://", ref, re.I):
                slots.setdefault(ref, None)
    if not slots:
        return 0, audio_skipped
    urls = list(slots)
    total, lock = [0], threading.Lock()

    def count(n):
        with lock:
            total[0] += n
            if total[0] > MEDIA_TOTAL_MAX:     # 合計が上限を超えたら、そこで取るのを止める（全部取り終えてから判定しない）
                raise remote_image.FetchError("total too large")

    def one(i):
        if i >= MEDIA_REMOTE_MAX:
            return None, "too many images"
        try:
            body, ctype = fetch(urls[i], on_bytes=count)
        except remote_image.FetchError as e:
            return None, str(e)
        except Exception:
            return None, "error"
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp", "image/avif": ".avif", "image/svg+xml": ".svg"}[ctype]
        path = os.path.join(tmpdir, "remote%d%s" % (i, ext))
        with open(path, "wb") as f:
            f.write(body)
        return (path, ctype), None
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, range(len(urls))))
    failed = 0
    for url, (got, why) in zip(urls, results):
        if got:
            files.append(got)
            slots[url] = "file/%d" % (len(files) - 1)
        else:
            failed += 1
            print("ask-form: 外部の画像を取得できませんでした（%s）" % why, file=sys.stderr)   # 宛先は書かない（定義の中身）
    for q in spec.get("questions", []):
        for o in q.get("options", []):
            ref = o.get("image")
            if isinstance(ref, str) and ref in slots:
                if slots[ref]:
                    o["image"] = slots[ref]
                else:
                    del o["image"]
    if audio_skipped:
        print("ask-form: 外部 URL の音は出せません（%d 件。絶対パスか data: で渡してください）" % audio_skipped, file=sys.stderr)
    return failed, audio_skipped


def markdown_page(text, title, lib="../lib/"):
    """Markdown を整形して見せるページ（viewer.html）。lib は、同梱のライブラリを読むアドレス。"""
    js = lambda v: json.dumps(v, ensure_ascii=False).replace("</", "<\\/")
    template = open(os.path.join(HERE, "viewer.html"), encoding="utf-8").read()
    return (template.replace("__TITLE__", title.replace("&", "&amp;").replace("<", "&lt;"))
            .replace("__LIB__", js(lib)).replace("__SOURCE__", js(text)))


def review_spec(files, title=None):
    """成果物を見せて、承認か修正の依頼かを聞く定義（--review）。答えは decision（approve / revise / stop）と comment・remark。"""
    return {
        "title": title or "成果物の確認",
        "submit": "この内容で返す",
        "note": False,
        "view": [{"file": f} for f in files],
        "questions": [
            {"id": "decision", "label": "どうしますか", "default": "approve", "minWidth": 120, "showValue": False, "options": [
                {"value": "approve", "label": "承認", "desc": "このまま進める。", "recommended": True},
                {"value": "revise", "label": "修正を依頼", "desc": "直してほしい所を書く。"},
                {"value": "stop", "label": "中止", "desc": "この作業をやめる。"}]},
            {"id": "comment", "label": "直してほしい所", "type": "text", "multiline": True, "required": True, "showIf": {"decision": "revise"},
             "placeholder": "どこを、どう直すか"},
            {"id": "remark", "label": "一言（任意）", "type": "text", "multiline": True, "showIf": {"decision": ["approve", "stop"]}},
        ],
    }


# ── 前回の回答を既定にする（定義の "remember": "名前"） ───────────────────
def remember_path(key):
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "ask-form", "remember", re.sub(r"[^\w.-]", "_", str(key)) + ".json")


def apply_remembered(spec):
    """前回の回答のうち、今回の定義でもそのまま選べるものだけを既定にする。
    自由記述（text・edit）と、選択肢に無い値（自由入力）は持ち越さない。"""
    try:
        last = json.load(open(remember_path(spec["remember"]), encoding="utf-8"))
    except (OSError, ValueError):
        return
    for q in spec["questions"]:
        v = last.get(q["id"])
        if v is None or q.get("remember") is False or q["type"] not in CHOICE_TYPES:
            continue
        values = [o["value"] for o in q["options"]]
        if q["type"] == "single":
            new = v if v in values else None
        elif q["type"] == "multi":
            new = [x for x in v if x in values] if isinstance(v, list) else None
        elif q["type"] == "rank":
            new = v if isinstance(v, list) and sorted(v) == sorted(values) else None
        else:  # table: 行ごとに持ち越す
            hit = False
            for r in q["rows"]:
                if isinstance(v, dict) and v.get(r["value"]) in values and v[r["value"]] != r.get("default", q.get("default")):
                    r["_default0"] = r.get("default", q.get("default"))
                    r["default"] = v[r["value"]]
                    hit = True
            if hit:
                q["_remembered"] = True
            continue
        if new is not None and new != q.get("default"):
            q["_default0"] = q.get("default")
            q["default"] = new
            q["_remembered"] = True


def save_remembered(spec, answers):
    keep = {q["id"]: answers[q["id"]] for q in spec["questions"]
            if q["id"] in answers and q["type"] in CHOICE_TYPES and q.get("remember") is not False}
    path = remember_path(spec["remember"])
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            keep = dict(json.load(open(path, encoding="utf-8")), **keep)  # 今回聞かなかった質問の分は残す
        except (OSError, ValueError):
            pass
        json.dump(keep, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    except OSError:
        pass


# ── 単発ウィンドウを開けるブラウザを探す ──────────────────────────────────
def is_wsl():
    try:
        return "microsoft" in open("/proc/version").read().lower()
    except OSError:
        return False


def find_browser():
    """Chromium 系ブラウザの実行ファイルを返す。見つからなければ (None, 理由)。"""
    if os.environ.get("ASK_FORM", "").lower() in ("off", "0", "no"):
        return None, "ASK_FORM=off が設定されています"
    override = os.environ.get("ASK_FORM_BROWSER")
    if override:
        path = override if os.path.exists(override) else shutil.which(override)
        return (path, None) if path else (None, "ASK_FORM_BROWSER=%s が見つかりません" % override)

    win_tails = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                 r"BraveSoftware\Brave-Browser\Application\brave.exe"]
    cands = []
    if sys.platform == "win32":
        for base in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            if os.environ.get(base):
                cands += [os.path.join(os.environ[base], t) for t in win_tails]
    elif is_wsl():
        for base in ("/mnt/c/Program Files (x86)", "/mnt/c/Program Files"):
            cands += [os.path.join(base, t.replace("\\", "/")) for t in win_tails]
        cands += glob.glob("/mnt/c/Users/*/AppData/Local/Google/Chrome/Application/chrome.exe")
    elif sys.platform == "darwin":
        if os.environ.get("SSH_CONNECTION"):
            return None, "SSH 越しのため、画面にウィンドウを出せません"
        cands = ["/Applications/%s.app/Contents/MacOS/%s" % (n, n) for n in
                 ("Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium")]
    else:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return None, "画面（DISPLAY）が無い環境です"
        cands = [p for p in (shutil.which(n) for n in (
            "google-chrome", "google-chrome-stable", "microsoft-edge", "microsoft-edge-stable",
            "chromium", "chromium-browser", "brave-browser")) if p]
    for c in cands:
        if os.path.exists(c):
            return c, None
    return None, "Chromium 系ブラウザ（Edge / Chrome など）が見つかりません"


# ── 画面の前に人がいるか（最後にキーボード・マウスを触ってからの秒数） ────
_IDLE_PS = r'''
Add-Type @"
using System;using System.Runtime.InteropServices;
public static class AskIdle{[StructLayout(LayoutKind.Sequential)]struct LII{public uint cb;public uint t;}
[DllImport("user32.dll")]static extern bool GetLastInputInfo(ref LII p);
public static uint Sec(){LII i=new LII();i.cb=8;GetLastInputInfo(ref i);return ((uint)Environment.TickCount-i.t)/1000;}}
"@
[AskIdle]::Sec()
'''


def idle_seconds():
    """このマシンで最後に操作があってからの秒数。分からなければ None（そのときは判定しない）。
    スマホなど別の端末から指示しているとき、誰も見ていない画面にウィンドウを出して待ち続けないために使う。"""
    try:
        if sys.platform == "win32":
            import ctypes

            class LII(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_uint), ("t", ctypes.c_uint)]
            info = LII(8, 0)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
            return ((ctypes.windll.kernel32.GetTickCount() - info.t) & 0xFFFFFFFF) / 1000.0
        if is_wsl():
            ps = shutil.which("powershell.exe") or "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
            enc = base64.b64encode(_IDLE_PS.encode("utf-16-le")).decode("ascii")
            out = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                                 capture_output=True, timeout=10, stdin=subprocess.DEVNULL).stdout
            return float(out.decode("ascii", "ignore").strip().splitlines()[-1])
        if sys.platform == "darwin":
            out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, timeout=5).stdout.decode()
            return int(re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out).group(1)) / 1e9
        if shutil.which("xprintidle"):
            return int(subprocess.run(["xprintidle"], capture_output=True, timeout=5).stdout) / 1000.0
    except Exception:
        pass
    return None


# ── ウィンドウとやり取りする小さなサーバー ────────────────────────────────
class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.result = None          # {"status": ..., ...} が入ったら終わり
        self.conns = 0              # つながっているウィンドウの数
        self.connected_at = None    # 最初につながった時刻
        self.last_drop = 0.0
        self.seen = False           # ウィンドウの中で人の操作（マウス・キー）があった

    def finish(self, result):
        with self.lock:
            if self.result is None:
                self.result = result


def make_handler(state, token, page, files=(), views=(), vtoken=None):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _ok(self):
            return self.path.split("?")[0].startswith("/%s/" % token)

        def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")   # 枠の中へ、このページのアドレス（合言葉）を渡さない
            self.end_headers()
            self.wfile.write(body)

        def _view(self):
            """見せる成果物。回答の受け口とは別の合言葉の下で配る（枠の中のスクリプトが、自分のアドレスから回答の受け口を作れないように）。
            枠の外で開かれても隔離されるよう、応答にも sandbox を付ける。"""
            rel = self.path.split("?")[0]
            lib = re.match(r"^/%s/lib/([\w.\-]+)$" % re.escape(vtoken), rel) if vtoken else None
            if lib and lib.group(1) in VIEW_LIBS:   # 同梱のライブラリ（Markdown を見せるページが読む）。名前の一覧にあるものだけ
                path, ctype = os.path.join(HERE, "vendor", lib.group(1)), VIEW_LIBS[lib.group(1)]
            else:
                m = re.match(r"^/%s/view/(\d+)$" % re.escape(vtoken), rel) if vtoken else None
                if not m or int(m.group(1)) >= len(views):
                    return False
                path, ctype = views[int(m.group(1))]
            sandbox = VIEW_SANDBOX
            try:
                body = open(path, "rb").read()
                if ctype == "markdown":
                    sandbox = VIEW_SANDBOX_MD
                    body = markdown_page(body.decode("utf-8", "replace"), os.path.basename(path)).encode("utf-8")
                    ctype = "text/html; charset=utf-8"
            except OSError:
                self._send(404)
                return True
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "sandbox " + sandbox)
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)
            return True

        def do_GET(self):
            if self._view():
                return
            if not self._ok():
                return self._send(404)
            rel = self.path.split("?")[0][len(token) + 2:]
            m = re.match(r"^file/(\d+)$", rel)
            if m and int(m.group(1)) < len(files):  # 定義に書かれた画像・音だけを、番号で配る
                path, ctype = files[int(m.group(1))]
                try:
                    return self._send(200, open(path, "rb").read(), ctype)
                except OSError:
                    return self._send(404)
            if rel == "":
                return self._send(200, page, "text/html; charset=utf-8")
            if rel == "ping":
                return self._send(200, b"ok")
            if rel == "events":
                return self._events()
            self._send(404)

        def _events(self):
            # ウィンドウが開いている間つなぎっぱなしにする。切れたら「閉じられた」と分かる。
            # ページ側のタイマーは裏に回ると止められるので、ページからの定期連絡には頼らない。
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            with state.lock:
                state.conns += 1
                state.connected_at = state.connected_at or time.time()
            try:
                while state.result is None:
                    self.wfile.write(b": keep\n\n")
                    self.wfile.flush()
                    time.sleep(0.5)
            except OSError:
                pass
            finally:
                with state.lock:
                    state.conns -= 1
                    state.last_drop = time.time()
                self.close_connection = True

        def do_POST(self):
            if not self._ok():
                return self._send(404)
            name = self.path.rsplit("/", 1)[1]
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if name == "answer":
                try:
                    data = json.loads(body.decode("utf-8"))
                except ValueError:
                    return self._send(400)
                self._send(204)
                state.finish(dict({"status": "answered"}, **data))
            elif name == "cancel":
                self._send(204)
                state.finish({"status": "cancelled"})
            elif name == "seen":
                self._send(204)
                state.seen = True
            else:
                self._send(404)

    return Handler


# ── Sodashitsu の pane の中なら、その pane を見ているブラウザの画面に出す ─────
SODA_FEATURES_TIMEOUT = 5   # sodactl ask --features を待つ秒数（ここで待たせすぎない）


class SodaRefused(Exception):
    """sodactl ask に渡せない定義（上限超過・sodactl が定義の誤りとした）。窓へ落とさず、終了コード 1 で理由を出す。"""


def soda_features(sodactl):
    """sodactl ask --features の結果（辞書）。古い sodactl（終了コード 2）・サーバが無い（server が null）・読めないときは None。"""
    try:
        p = subprocess.run([sodactl, "ask", "--features"], capture_output=True, text=True, encoding="utf-8",
                           timeout=SODA_FEATURES_TIMEOUT, stdin=subprocess.DEVNULL)
        info = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else None
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None
    if not isinstance(info, dict) or not isinstance(info.get("server"), dict):
        return None
    return info


def soda_required(raw):
    """書かれたままの定義が使う、sodactl・サーバの機能（types:*・media・remote-image・view）。"""
    need = set()
    if raw.get("view") is not None:
        need.add("view")
    for q in raw.get("questions") or []:
        if not isinstance(q, dict):
            continue
        if q.get("type") in ("edit", "rank", "table"):
            need.add("types:%s" % q["type"])
        if q.get("preview") is not None or q.get("thumb") is not None:
            need.add("media")
        for o in q.get("options") or []:
            if not isinstance(o, dict):
                continue
            if any(o.get(k) is not None for k in ("image", "audio", "code", "lang", "group")):
                need.add("media")
            if isinstance(o.get("image"), str) and o["image"].lower().startswith("https://"):
                need.add("remote-image")
    return need


def soda_absolutize(raw, base_dir):
    """image・audio・view.file の相対パス・~/ を base_dir から解いた絶対パスにした写しと、ローカルのファイルの一覧
    [(パス, 文字の成果物か)] を返す（sodactl は自分の cwd から解くので、定義の場所とずれないよう、ここで直す）。"""
    spec = json.loads(json.dumps(raw))
    paths = []

    def absolute(ref):
        return os.path.abspath(os.path.join(base_dir, os.path.expanduser(ref)))

    for q in spec.get("questions") or []:
        for o in (q.get("options") or []) if isinstance(q, dict) else []:
            if not isinstance(o, dict):
                continue
            for key in ("image", "audio"):
                ref = o.get(key)
                if isinstance(ref, str) and ref and not re.match(r"^(https?://|data:)", ref, re.I):
                    o[key] = absolute(ref)
                    paths.append((o[key], False))
    view = spec.get("view")
    items = view if isinstance(view, list) else [view] if view is not None else []
    for i, v in enumerate(items):
        if isinstance(v, str):
            v = {"file": v}
            items[i] = v
        if isinstance(v, dict) and isinstance(v.get("file"), str) and v["file"]:
            v["file"] = absolute(v["file"])
            ext = os.path.splitext(v["file"])[1].lower()
            paths.append((v["file"], ext not in VIEW_HTML and ext not in IMAGE_TYPES))
    if view is not None:
        spec["view"] = items if isinstance(view, list) else items[0]
    return spec, paths, len(items)


def soda_unlimited(info):
    """--features の結果が「ローカル起動で大きさの上限が無い」（limits.unlimited）か。sodactl の limits か、サーバの limits のどちらかが真なら真。
    古い sodactl・サーバは unlimited を持たない（偽）で、数の上限がそのまま効く。"""
    if not isinstance(info, dict):
        return False
    server = info.get("server")
    for limits in (info.get("limits"), server.get("limits") if isinstance(server, dict) else None):
        if isinstance(limits, dict) and limits.get("unlimited") is True:
            return True
    return False


def soda_effective_limits(info):
    """事前確認に使う上限。unlimited なら、大きさの上限は安全弁（limits.safety。無ければ確認しない）に替える。個数（files・views）は変わらない。"""
    info = info if isinstance(info, dict) else {}
    limits = info.get("limits") if isinstance(info.get("limits"), dict) else {}
    if not soda_unlimited(info):
        return limits
    server = info.get("server") if isinstance(info.get("server"), dict) else {}
    safety = limits.get("safety") or (server.get("limits") or {}).get("safety")
    safety = safety if isinstance(safety, dict) else {}
    out = {"files": limits.get("files"), "views": limits.get("views")}
    out["fileBytes"] = out["textBytes"] = safety.get("fileBytes")
    out["totalBytes"] = safety.get("totalBytes")
    return out


def soda_text_unlimited(raw, base_dir, sodactl_path=None):
    """文字として出す成果物（Markdown・テキスト）が窓の上限（VIEW_TEXT_MAX）を超えるとき、Sodashitsu がローカル起動で上限を外しているか。
    normalize はこの上限で定義の誤りにするので、外れているときだけ上限を緩めて通すために使う。超える成果物が無ければ、聞かずに偽（余分な呼び出しをしない）。"""
    if os.environ.get("ASK_FORM_SODA", "").lower() in ("off", "0", "no") or not os.environ.get("SODA_PANE_ID"):
        return False
    view = raw.get("view") if isinstance(raw, dict) else None
    big = False
    for v in view if isinstance(view, list) else [view] if view is not None else []:
        f = v if isinstance(v, str) else v.get("file") if isinstance(v, dict) else None
        if isinstance(f, str) and f:
            path = os.path.abspath(os.path.join(base_dir, os.path.expanduser(f)))
            ext = os.path.splitext(path)[1].lower()
            try:
                if ext not in VIEW_HTML and ext not in IMAGE_TYPES and os.path.getsize(path) > VIEW_TEXT_MAX:
                    big = True
            except OSError:
                pass
    sodactl = sodactl_path or shutil.which("sodactl")
    if not big or not sodactl:
        return False
    return soda_unlimited(soda_features(sodactl))


def soda_check_limits(paths, views, limits):
    """ローカルのファイルの大きさ・個数・合計を、sodactl の上限（--features の limits。soda_effective_limits の結果）で事前に確かめる。超えたら理由（文字列）。
    ローカル起動（unlimited）のときは、大きさは安全弁だけを見る。"""
    def lim(k):
        v = limits.get(k) if isinstance(limits, dict) else None
        return v if isinstance(v, int) and v > 0 else None
    seen, total = {}, 0
    for path, as_text in paths:
        if path in seen:
            continue   # 同じファイルは 1 つに数える
        try:
            size = seen[path] = os.path.getsize(path)
        except OSError:
            continue
        total += size
        cap = lim("textBytes") if as_text else lim("fileBytes")
        if cap and size > cap:
            return "%s が大きすぎます（%d バイト。1 つ %d バイトまで）" % (path, size, cap)
    if lim("files") and len(seen) > lim("files"):
        return "ファイルが多すぎます（%d 個。%d 個まで）" % (len(seen), lim("files"))
    if lim("totalBytes") and total > lim("totalBytes"):
        return "ファイルの合計が大きすぎます（%d バイト。%d バイトまで）" % (total, lim("totalBytes"))
    if lim("views") and views > lim("views"):
        return "view が多すぎます（%d 件。%d 件まで）" % (views, lim("views"))
    return None


def ask_via_soda(spec, timeout, raw=None, base_dir="."):
    """sodactl ask で聞く。結果（answered / cancelled / timeout）を返す。出せない・使わないときは None
    （呼び出し側はウィンドウへ進む）。上限超過・sodactl が定義の誤りとしたときは SodaRefused（窓へ落とさない）。

    画像・音・成果物・edit/rank/table を使う定義は、sodactl ask --features で、sodactl とサーバがそれを出せると
    確かめてから渡す（古い sodactl・サーバが無い・足りないときは None）。使わない定義（single・multi・text だけ）は、
    今までどおり確かめずに渡す。"""
    if os.environ.get("ASK_FORM_SODA", "").lower() in ("off", "0", "no"):
        return None
    sodactl = shutil.which("sodactl")
    if not sodactl or not os.environ.get("SODA_PANE_ID"):
        return None
    raw = raw if raw is not None else spec
    need = soda_required(raw)
    send, paths, views = soda_absolutize(raw, base_dir)
    if need:
        info = soda_features(sodactl)
        if not info:
            return None   # 古い sodactl・サーバが無い（繋げない・古い・pane の外）
        have = set(info.get("sodactl") or []) & set(info["server"].get("features") or [])
        if not need <= have:
            return None   # 足りない機能がある
        why = soda_check_limits(paths, views, soda_effective_limits(info))
        if why:
            raise SodaRefused(why)
    try:
        p = subprocess.run([sodactl, "ask", "--timeout", str(max(1, timeout) * 1000)],
                           input=json.dumps(send, ensure_ascii=False), capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout + 30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode == 2:   # invalid ask spec: …（定義の誤り・上限・種類の不一致）。窓でも同じなので、落とさずに知らせる
        raise SodaRefused((p.stderr or "").strip() or "sodactl ask が定義を受け付けませんでした")
    try:
        result = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else None
    except (ValueError, IndexError):
        return None
    if not isinstance(result, dict) or result.get("status") not in ("answered", "cancelled", "timeout"):
        return None   # unavailable（つながっているブラウザが無い等）・サーバのエラー（終了コード 1）
    return result


def build_page(spec, vtoken=None):
    """殻（form.html）に、部品（ask-form.js）と定義を埋め込む。"""
    spec = dict(spec, _viewBase="/%s/" % vtoken if vtoken else None)
    template = open(os.path.join(HERE, "form.html"), encoding="utf-8").read()
    component = open(os.path.join(HERE, "ask-form.js"), encoding="utf-8").read()   # 画面の部品（<ask-form>）。殻に埋め込んで配る
    return (template.replace("__COMPONENT__", component.replace("</script", "<\\/script"))
            .replace("__SPEC__", json.dumps(spec, ensure_ascii=False).replace("</", "<\\/")))


def done(result):
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(EXIT[result["status"]])


def env_int(name, default):
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def main():
    ap = argparse.ArgumentParser(description="質問をまとめて単発ウィンドウに出し、回答を JSON で受け取る")
    ap.add_argument("spec", nargs="?", help="質問の定義（JSON ファイル。- で標準入力）")
    ap.add_argument("--timeout", type=int, default=None, help="回答を待つ秒数（既定 %d。成果物を見せるときは %d）" % (TIMEOUT, TIMEOUT_VIEW))
    ap.add_argument("--review", nargs="+", metavar="FILE",
                    help="成果物（HTML・画像・テキスト）を見せて、承認・修正の依頼・中止を聞く（定義は要らない。答えは decision と comment）")
    ap.add_argument("--title", help="--review のウィンドウの題")
    ap.add_argument("--width", type=int, default=None,
                    help="ウィンドウの幅（既定 780。横にプレビューを出す質問・表があれば 1080）")
    ap.add_argument("--height", type=int, default=None, help="ウィンドウの高さの上限（中身に合わせて縮む。既定 820。成果物を見せるときは 1000 で、縮めない）")
    ap.add_argument("--away-after", type=int, default=env_int("ASK_FORM_AWAY_SECONDS", 300), metavar="秒",
                    help="このマシンの操作がこの秒数以上無ければ、画面の前に人がいないとみて unavailable を返す（既定 300。0 で判定しない）")
    ap.add_argument("--react-within", type=int, default=env_int("ASK_FORM_REACT_SECONDS", 90), metavar="秒",
                    help="開いたウィンドウにこの秒数のあいだ操作が無ければ、閉じて unavailable を返す（既定 90。0 で判定しない）")
    ap.add_argument("--check", action="store_true", help="定義の検査だけして終わる（ウィンドウは開かない）")
    ap.add_argument("--selftest", action="store_true", help="開く→既定の回答で自動的に答える→閉じる を確かめる（定義を渡せばその定義で）")
    args = ap.parse_args()

    try:
        if args.review:
            if args.spec:
                ap.error("--review のときは、定義を渡しません")
            spec = review_spec(args.review, args.title)
        elif args.selftest and not args.spec:
            spec = json.loads(json.dumps(SELFTEST_SPEC))
        elif not args.spec:
            ap.error("質問の定義（JSON）を指定してください")
        else:
            raw = sys.stdin.read() if args.spec == "-" else open(args.spec, encoding="utf-8").read()
            spec = json.loads(raw)
        # image・audio の相対パスは、定義のファイルの場所（標準入力なら今の場所）から解く
        base_dir = "." if args.spec in (None, "-") else os.path.dirname(os.path.abspath(args.spec))
        raw_spec = json.loads(json.dumps(spec))   # sodactl ask へは、書かれたままの定義を渡す
        # Sodashitsu がローカル起動で大きさの上限を外しているときだけ、文字の成果物（Markdown・テキスト）の窓の上限（2 MiB）を緩めて通す。窓へ落ちるときは下で厳密に直す
        relaxed = not args.selftest and not args.review and soda_text_unlimited(raw_spec, base_dir)
        spec = normalize(spec, base_dir, view_text_max=1 << 60 if relaxed else VIEW_TEXT_MAX)
    except (OSError, ValueError) as e:
        print("ask-form: 質問の定義を読めません: %s" % e, file=sys.stderr)
        sys.exit(EXIT["error"])
    if args.check:
        print("OK: 質問 %d 件" % len(spec["questions"]))
        return

    files, views = spec.pop("_files"), spec.pop("_views")
    if args.timeout is None:
        args.timeout = TIMEOUT_VIEW if spec.get("view") else TIMEOUT
    if args.height is None:
        args.height = 1000 if spec.get("view") else 820
    if spec.get("remember") and not args.selftest:
        apply_remembered(spec)
    if not args.selftest:
        try:
            result = ask_via_soda(spec, args.timeout, raw_spec, base_dir)
        except SodaRefused as e:
            print("ask-form: Sodashitsu の画面には出せません: %s" % e, file=sys.stderr)
            sys.exit(EXIT["error"])
        if result:
            if result["status"] == "answered" and spec.get("remember"):
                save_remembered(spec, result.get("answers") or {})
            done(result)
        if relaxed:   # Sodashitsu の画面へ出せなかった: 窓では従来の上限（窓は Markdown・テキストを 2 MiB まで）
            try:
                normalize(json.loads(json.dumps(raw_spec)), base_dir)
            except (OSError, ValueError) as e:
                print("ask-form: 質問の定義を読めません: %s" % e, file=sys.stderr)
                sys.exit(EXIT["error"])

    browser, why = find_browser()
    if not browser:
        done({"status": "unavailable", "reason": why})
    if args.selftest:  # 自動回答なので、人がいるかは見ない
        args.away_after = args.react_within = 0
    if args.away_after > 0:
        idle = idle_seconds()
        if idle is not None and idle >= args.away_after:
            done({"status": "unavailable",
                  "reason": "このマシンの操作が %d 秒ありません（画面の前に人がいないとみて、ウィンドウを出しませんでした）" % idle})

    if args.width is None:
        wide = any(q["type"] == "table" or q.get("preview") == "side"
                   or (q.get("preview") is None and any("code" in o for o in q.get("options", [])))
                   for q in spec["questions"])
        args.width = 1400 if spec.get("view") else 1080 if wide else 780
    spec["_auto"] = bool(args.selftest)
    spec["_width"] = args.width
    spec["_maxHeight"] = args.height
    # 外部 URL の画像は、ブラウザではなくここ（ask.py）が取る。利用者の IP が取得先に見えない。取れなかった画像は、画像なしで出す
    tmpdir = tempfile.mkdtemp(prefix="ask-form-")
    atexit.register(shutil.rmtree, tmpdir, True)
    failed, audio_skipped = localize_remote_media(spec, files, tmpdir)
    spec["_mediaFailed"], spec["_audioSkipped"] = failed, audio_skipped
    state = State()
    token, vtoken = secrets.token_urlsafe(12), secrets.token_urlsafe(12)
    page = build_page(spec, vtoken)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state, token, page.encode("utf-8"), files, views, vtoken))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://localhost:%d/%s/" % (server.server_address[1], token)

    try:
        subprocess.Popen([browser, "--app=" + url, "--window-size=%d,%d" % (args.width, args.height)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        done({"status": "unavailable", "reason": "ブラウザを起動できません: %s" % e})

    start = time.time()
    while state.result is None:
        time.sleep(0.1)
        now = time.time()
        with state.lock:
            opened = state.connected_at
            closed = opened and state.conns == 0 and now - state.last_drop > CLOSE_GRACE
            never = not opened and now - start > OPEN_WAIT
            unseen = opened and not state.seen and args.react_within > 0 and now - opened > args.react_within
        if closed:
            state.finish({"status": "cancelled"})
        elif never:
            state.finish({"status": "unavailable", "reason": "ウィンドウがつながりません（%d 秒待ちました）" % OPEN_WAIT})
        elif unseen:  # 受け口が終わると、ウィンドウは自分で閉じる
            state.finish({"status": "unavailable",
                          "reason": "開いたウィンドウに %d 秒のあいだ操作がありません（画面の前に人がいないとみて閉じました）" % args.react_within})
        elif now - start > args.timeout:
            state.finish({"status": "timeout"})
    time.sleep(0.3)  # 最後の応答をウィンドウへ返し切る
    if state.result["status"] == "answered" and spec.get("remember") and not args.selftest:
        save_remembered(spec, state.result.get("answers") or {})
    done(state.result)


if __name__ == "__main__":
    main()
