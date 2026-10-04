"""ask-form: 定義の検査（ask.py の normalize）と、部品 <ask-form>（ask-form.js）の回答の集め方を、共通の試験データで確かめる。

共通の試験データ（ask-form/fixtures/*.json）は、同じ部品を取り込む Sodashitsu（sodactl ask の画面）も読む。
ここで通る形を変えるときは、試験データを直し、Sodashitsu 側にも知らせる（片方だけ変えると、もう片方のテストが落ちる）。
部品は、画面なしの Chrome で動かす。Chrome が無ければ飛ばす。
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unittest

import chrome as helpers

AF = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AF)
import ask  # noqa: E402

CHROME = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)


def fixture(name):
    return json.load(open(os.path.join(AF, "fixtures", name), encoding="utf-8"))


def public(o):
    """実装が足す内部の項目（_ で始まる）を除く。"""
    if isinstance(o, dict):
        return {k: public(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [public(v) for v in o]
    return o


class Normalize(unittest.TestCase):
    """定義の検査と正規化（fixtures/normalize.json）。"""

    def test_cases(self):
        doc = fixture("normalize.json")
        for c in doc["cases"]:
            with self.subTest(c["name"]):
                want = (c.get("ask-form") or {}).get("expect") or c["expect"]
                try:
                    got = {"ok": True, "spec": public(ask.normalize(copy.deepcopy(c["spec"])))}
                except ask.SpecError as e:
                    got = {"ok": False, "reason": e.reason}
                self.assertEqual(got, want)
                if not want["ok"]:
                    self.assertIn(want["reason"], doc["reasons"])

    def test_every_error_has_a_listed_reason(self):
        """ask.py が出す誤りの分類は、すべて試験データの一覧（reasons）にある。"""
        src = open(os.path.join(AF, "ask.py"), encoding="utf-8").read()
        used = set(re.findall(r'SpecError\("([a-z_]+)"', src))
        self.assertTrue(used)
        self.assertEqual(used - set(fixture("normalize.json")["reasons"]), set())


class Component(unittest.TestCase):
    """部品のファイルの決まり（置いた側の安全のため。Sodashitsu の CSP と、定義を信用しない前提）。"""

    @classmethod
    def setUpClass(cls):
        cls.src = open(os.path.join(AF, "ask-form.js"), encoding="utf-8").read()
        code = re.sub(r"/\*.*?\*/", "", cls.src, flags=re.S)
        cls.code = re.sub(r"(?m)^\s*//.*$|\s//\s.*$", "", code)

    def test_no_page_wide_or_network_access(self):
        for word in ("innerHTML", "insertAdjacentHTML", "outerHTML", "document.write", "fetch(", "EventSource", "XMLHttpRequest", "WebSocket",
                     "sendBeacon", "window.close", "document.title", "resizeTo", "localStorage", "sessionStorage", "history.", "location.",
                     "eval(", "new Function", "cssText", "document.addEventListener", "window.addEventListener", "</script"):
            with self.subTest(word):
                self.assertNotIn(word, self.code)

    def test_markers_for_hosts(self):
        """置いた側のテストが使う印と、受け渡しの名前。"""
        for word in ("data-ask-title", "data-ask-question", "data-ask-note", "data-ask-status", "data-ask-submit", "data-ask-cancel",
                     "data-ask-index", "data-ask-comment", "ask-submit", "ask-cancel", "ask-unsupported",
                     "--ask-bg", "--ask-fg", "--ask-border", "--ask-accent", "--ask-accent-fg", "--ask-error", "--ask-warn",
                     "static version", "static supports", "customElements.define('ask-form'"):
            with self.subTest(word):
                self.assertIn(word, self.src)

    def test_shell_embeds_the_component(self):
        shell = open(os.path.join(AF, "form.html"), encoding="utf-8").read()
        self.assertEqual(shell.count("__COMPONENT__"), 1)
        self.assertEqual(shell.count("__SPEC__"), 1)
        self.assertIn("<ask-form", shell)


PAGE = """<!doctype html><meta charset="utf-8"><body>
<script type="module">
%(component)s
</script>
<script type="module">
const CASES = %(cases)s, out = [];
for (const c of CASES) {
  const f = document.createElement('ask-form');
  f.style.height = '600px';
  document.body.append(f);
  let sent = null;
  f.addEventListener('ask-submit', (e) => { sent = e.detail; });
  f.spec = c.spec;
  const R = f.shadowRoot, st = c.state;
  for (const q of c.spec.questions) {
    const esc = CSS.escape(q.id);
    for (const i of R.querySelectorAll(`input[name="${esc}"]`)) {
      if (i.type === 'text') i.value = (st.text || {})[q.id] || '';
      else if (i.dataset.other != null) {
        i.checked = !!(st.otherPicked || {})[q.id];
        i.closest('label').querySelector('input[type=text]').value = (st.otherText || {})[q.id] || '';
      } else i.checked = ((st.picked || {})[q.id] || []).includes(i.value);
    }
    const ta = R.querySelector(`textarea[name="${esc}"]`);
    if (ta) ta.value = (st.text || {})[q.id] || '';
  }
  for (const [id, text] of Object.entries(st.comments || {})) {   // 質問ごとの自由記述（閉じたままでも、書いてあれば入る）
    const cm = R.querySelector(`textarea[data-ask-comment="${CSS.escape(id)}"]`);
    if (cm) cm.value = text;
  }
  const note = R.querySelector('[data-ask-note] textarea');
  if (note) note.value = st.note || '';
  const value = f.value;
  f.submit();
  out.push({ value, sent, pages: f.pageCount, missing: [...R.querySelectorAll('fieldset.missing')].map(x => x.dataset.askQuestion) });
  f.remove();
}
document.body.append(Object.assign(document.createElement('pre'), { id: 'out', textContent: JSON.stringify(out) }));
</script>
"""


@unittest.skipUnless(CHROME or os.environ.get("REQUIRE_CHROME"), "Chrome が無い")
class Collect(unittest.TestCase):
    """回答の集め方（fixtures/collect.json）を、部品を画面なしの Chrome で動かして確かめる。"""

    @classmethod
    def setUpClass(cls):
        if not CHROME:
            raise AssertionError("Chrome が無いので ask-form.js を確かめられません")
        cls.cases = fixture("collect.json")["cases"]
        runs = []
        for c in cls.cases:
            spec = public(ask.normalize(copy.deepcopy(c["spec"])))
            runs.append({"spec": spec, "state": c["state"]})
        d = helpers.tmpdir()
        page = os.path.join(d, "collect.html")
        html = PAGE % {"component": open(os.path.join(AF, "ask-form.js"), encoding="utf-8").read(), "cases": json.dumps(runs, ensure_ascii=False).replace("</", "<\\/")}
        open(page, "w", encoding="utf-8").write(html)
        r = subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=5000", "--dump-dom", "file://" + page],
                           capture_output=True, text=True, timeout=120)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout, flags=re.S)
        if not m:
            raise AssertionError("部品が結果を出しませんでした: " + r.stdout[-400:] + r.stderr[-400:])
        import html as htmllib
        cls.results = json.loads(htmllib.unescape(m.group(1)))

    def test_cases(self):
        self.assertEqual(len(self.results), len(self.cases))
        for c, got in zip(self.cases, self.results):
            with self.subTest(c["name"]):
                want = (c.get("ask-form") or {}).get("expect") or c["expect"]
                self.assertEqual(got["value"], want)
                body = {k: v for k, v in want.items() if k != "lacking"}
                if want["lacking"]:   # 未回答があれば知らせず、その質問を示す
                    self.assertIsNone(got["sent"])
                    self.assertEqual(got["missing"], want["lacking"])
                else:
                    self.assertEqual(got["sent"], body)


@unittest.skipUnless(CHROME or os.environ.get("REQUIRE_CHROME"), "Chrome が無い")
class Index(unittest.TestCase):
    """質問の目次（横の一覧）: 質問が高さに収まらないときに出て、スクロールに合わせて今の質問に印が付き、押すとその質問へ移る。
    ページには分けない（2026-10: ページ分けをやめ、1 枚に並べて目次で移る形にした）。"""

    @classmethod
    def setUpClass(cls):
        if not CHROME:
            raise AssertionError("Chrome が無いので ask-form.js を確かめられません")
        from chrome import Chrome
        cls.chrome = Chrome()
        cls.component = open(os.path.join(AF, "ask-form.js"), encoding="utf-8").read()

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    def open(self, questions, **top):
        spec = public(ask.normalize(dict({"title": "t", "questions": questions}, **top)))
        c = self.chrome
        c.call("Emulation.setDeviceMetricsOverride", c.sid, width=1000, height=400, deviceScaleFactor=1, mobile=False)
        c.call("Emulation.setFocusEmulationEnabled", c.sid, enabled=True)   # 画面なしでも、フォーカスの出来事（focusin）が起きるように
        path = os.path.join(c.dir, "index%d.html" % c.n)
        open(path, "w", encoding="utf-8").write(INSTANT_PAGE % {"component": self.component, "spec": json.dumps(spec, ensure_ascii=False)})
        c.call("Page.enable", c.sid)
        c.call("Page.navigate", c.sid, url="file://" + path)
        c.eval("new Promise(function(ok){function w(){window.READY&&FORM.shadowRoot.querySelector('input')?setTimeout(ok,150):setTimeout(w,50)};w()})")

    def state(self, before=""):
        return self.chrome.eval("""new Promise(function(ok){%s;setTimeout(function(){var R=FORM.shadowRoot,ix=R.querySelector('.index'),cur=R.querySelector('.index .cur');
          ok({shown:!ix.hidden&&ix.offsetWidth>0, width:FORM.indexWidth, pages:FORM.pageCount,
              items:[].slice.call(R.querySelectorAll('.index button')).filter(function(b){return !b.hidden}).map(function(b){return b.dataset.askIndex}),
              secs:[].slice.call(R.querySelectorAll('.index .sec')).filter(function(b){return !b.hidden}).map(function(b){return b.textContent}),
              cur:cur?cur.dataset.askIndex:null, lack:[].slice.call(R.querySelectorAll('.index .lack')).map(function(b){return b.dataset.askIndex}),
              off:R.querySelectorAll('fieldset.off').length, focus:(R.activeElement||{}).name||null, top:R.querySelector('.body').scrollTop})},200)})""" % before)

    MANY = [{"id": "q%d" % i, "label": "質問 %d" % i, "default": "a", "options": ["a", "b", "c"]} for i in range(1, 9)]

    def test_short_form_has_no_index(self):
        self.open(self.MANY[:1], note=False)
        st = self.state()
        self.assertFalse(st["shown"])
        self.assertEqual(st["width"], 0)

    def test_long_form_shows_every_question(self):
        self.open(self.MANY)
        st = self.state()
        self.assertTrue(st["shown"])
        self.assertGreater(st["width"], 100)
        self.assertEqual(st["items"], ["q%d" % i for i in range(1, 9)] + [""])   # 補足も並ぶ
        self.assertEqual((st["cur"], st["off"], st["pages"]), ("q1", 0, 1))      # 1 枚に並ぶ（隠すページは無い）

    def test_paging_false_hides_and_true_forces(self):
        self.open(self.MANY, paging=False)
        self.assertFalse(self.state()["shown"])
        self.open(self.MANY[:2], paging=True, note=False)
        self.assertTrue(self.state()["shown"])

    def test_scroll_moves_the_mark_and_click_moves_the_view(self):
        self.open(self.MANY)
        st = self.state("var b=FORM.shadowRoot.querySelector('.body'),f=FORM.shadowRoot.querySelector('[data-ask-question=q4]');"
                        "b.scrollTop=f.getBoundingClientRect().top-b.getBoundingClientRect().top+b.scrollTop")
        self.assertEqual(st["cur"], "q4")
        st = self.state("FORM.shadowRoot.querySelector('[data-ask-index=q7]').click()")
        self.assertEqual((st["cur"], st["focus"]), ("q7", "q7"))
        self.assertGreater(st["top"], 300)
        st = self.state("FORM.step(-1)")       # 置いた側のキー（前の質問へ）
        self.assertEqual(st["cur"], "q6")

    def test_bottom_marks_the_last_and_short_items_in_turn(self):
        """いちばん下まで下げると、最後の項目に印が付く。最後の画面に並んで収まる短い質問にも、下げる途中で順に印が移る
        （上の端を過ぎた質問だけを見ていると、下の端の短い質問には印が来ない）。"""
        self.open(self.MANY)
        st = self.state("var b=FORM.shadowRoot.querySelector('.body');b.scrollTop=b.scrollHeight")
        self.assertEqual(st["cur"], "")          # 補足（最後の項目）
        seen = []
        for k in range(0, 21):
            cur = self.state("var b=FORM.shadowRoot.querySelector('.body');b.scrollTop=(b.scrollHeight-b.clientHeight)*%s" % (k / 20))["cur"]
            if not seen or seen[-1] != cur:
                seen.append(cur)
        self.assertEqual(seen, ["q%d" % i for i in range(1, 9)] + [""], "下げていく途中で、どの質問にも順に印が付く")

    def test_mark_when_everything_fits(self):
        """目次が出ていて、全部が収まっている（スクロールしない）ときは、最初の質問に印が付く。フォーカスを移すと、印もその質問へ移る
        （前は、スクロールできないと「いちばん下」とみなして、開いた直後から最後の質問に印が付いた）。"""
        self.open(self.MANY[:2], paging=True, note=False)
        st = self.state()
        self.assertTrue(st["shown"])
        self.assertEqual((st["cur"], st["top"]), ("q1", 0))
        st = self.state("FORM.shadowRoot.querySelector('[data-ask-question=q2] input').focus()")
        self.assertEqual(st["cur"], "q2")

    def test_submit_with_unanswered_moves_the_mark(self):
        """未回答のまま決定すると、最初の未回答の質問へ移り、目次の印もその質問に付く
        （前は、フォーカスと表示は移るのに、印が元のままだった）。"""
        qs = [dict(q) for q in self.MANY]
        del qs[1]["default"]
        self.open(qs)
        st = self.state("var b=FORM.shadowRoot.querySelector('.body');b.scrollTop=b.scrollHeight")
        self.assertEqual(st["cur"], "")
        st = self.state("FORM.submit()")
        self.assertEqual((st["cur"], st["focus"], st["lack"]), ("q2", "q2", ["q2"]))
        time.sleep(0.6)                      # なめらかに移り終えた後も、印はそのまま
        self.assertEqual(self.state()["cur"], "q2")

    def test_paging_false_wins_over_page(self):
        """paging: false は、page を書いていても目次を出さない。"""
        qs = [dict(q, page="まとまり %d" % (i // 3)) for i, q in enumerate(self.MANY)]
        self.open(qs, paging=False)
        self.assertFalse(self.state()["shown"])
        self.open(qs[:2], note=False)        # paging を書かなければ、page があれば収まっていても出す
        self.assertTrue(self.state()["shown"])

    def test_long_index_scrolls_and_follows_the_mark(self):
        """質問が多いと、目次にも縦のスクロールバーが出る。印が移ると、目次もその項目が見える所へ動く。"""
        self.open([{"id": "q%d" % i, "label": "質問 %d" % i, "default": "a", "options": ["a", "b"]} for i in range(1, 41)])
        js = """(function(){var R=FORM.shadowRoot,ix=R.querySelector('.index'),c=R.querySelector('.index .cur').getBoundingClientRect(),x=ix.getBoundingClientRect(),
          f=FORM.getBoundingClientRect(),ft=R.querySelector('footer').getBoundingClientRect();
          return {scrolls:ix.scrollHeight>ix.clientHeight+20, bar:getComputedStyle(ix).overflowY, top:ix.scrollTop, fits:x.top>=f.top-1&&x.bottom<=ft.top+1,
                  curIn:c.top>=x.top&&c.bottom<=x.bottom}})()"""
        a = self.chrome.eval(js)
        self.assertTrue(a["scrolls"] and a["bar"] == "auto" and a["fits"], a)   # 目次は画面の中に収まり、中がスクロールする
        self.assertEqual(a["top"], 0)
        st = self.state("var b=FORM.shadowRoot.querySelector('.body');b.scrollTop=b.scrollHeight")
        self.assertEqual(st["cur"], "")
        z = self.chrome.eval(js)
        self.assertGreater(z["top"], 100)
        self.assertTrue(z["curIn"], z)
        st = self.state("var b=FORM.shadowRoot.querySelector('.body'),f=FORM.shadowRoot.querySelector('[data-ask-question=q20]');"
                        "b.scrollTop=f.getBoundingClientRect().top-b.getBoundingClientRect().top+b.scrollTop")
        self.assertEqual(st["cur"], "q20")
        self.assertTrue(self.chrome.eval(js)["curIn"])

    def test_question_comment_opens_on_click(self):
        """質問ごとの自由記述: ボタンを押すと欄が開き、書いた内容が comments に入る。閉じても消えず、ボタンに「入力あり」と出る。
        書く質問（text）と、付けない指定（comment: false）の質問には出ない。"""
        self.open([{"id": "a", "label": "A", "default": "x", "options": ["x", "y"]}, {"id": "t", "label": "T", "type": "text"},
                   {"id": "n", "label": "N", "default": "x", "comment": False, "options": ["x"]}], paging=False)
        js = """(function(){var R=FORM.shadowRoot,b=R.querySelector('[data-ask-comment-toggle=a]'),ta=R.querySelector('textarea[data-ask-comment=a]');
          return {toggles:[].slice.call(R.querySelectorAll('[data-ask-comment-toggle]')).map(function(x){return x.dataset.askCommentToggle}),
                  open:!ta.hidden, label:b.textContent, expanded:b.getAttribute('aria-expanded'), focus:R.activeElement===ta, comments:FORM.value.comments||null}})()"""
        st = self.chrome.eval(js)
        self.assertEqual(st["toggles"], ["a"])
        self.assertEqual((st["open"], st["expanded"], st["comments"]), (False, "false", None))
        self.chrome.eval("FORM.shadowRoot.querySelector('[data-ask-comment-toggle=a]').click()")
        st = self.chrome.eval(js)
        self.assertEqual((st["open"], st["expanded"], st["focus"]), (True, "true", True))
        self.chrome.eval("(function(){var R=FORM.shadowRoot,ta=R.querySelector('textarea[data-ask-comment=a]');ta.value='夜だけ';"
                         "ta.dispatchEvent(new Event('input',{bubbles:true}));R.querySelector('[data-ask-comment-toggle=a]').click()})()")
        st = self.chrome.eval(js)
        self.assertFalse(st["open"])
        self.assertIn("入力あり", st["label"])
        self.assertEqual(st["comments"], {"a": "夜だけ"})

    def test_no_comment_when_disabled_or_instant(self):
        self.open(self.MANY[:2], comments=False)
        self.assertEqual(self.chrome.eval("FORM.shadowRoot.querySelectorAll('[data-ask-comment-toggle]').length"), 0)
        self.open(self.MANY[:1], note=False)   # 選んだ時点で決定するフォームには付けない
        self.assertEqual(self.chrome.eval("FORM.shadowRoot.querySelectorAll('[data-ask-comment-toggle]').length"), 0)

    def test_sections_hidden_questions_and_unanswered(self):
        qs = [dict(q) for q in self.MANY]
        qs[0]["page"], qs[4]["page"] = "基本", "音"
        qs[5]["showIf"] = {"q1": "b"}           # 出ていない質問は、目次にも出ない
        del qs[2]["default"]                    # 未回答
        self.open(qs)
        st = self.state()
        self.assertTrue(st["shown"])
        self.assertEqual(st["secs"], ["基本", "音"])
        self.assertNotIn("q6", st["items"])
        self.assertEqual(st["lack"], ["q3"])
        st = self.state("var i=FORM.shadowRoot.querySelector('input[name=q1][value=b]');i.checked=true;i.dispatchEvent(new Event('change',{bubbles:true}))")
        self.assertIn("q6", st["items"])


KEYS = {" ": ("Space", 32, " "), "Enter": ("Enter", 13, "\r"), "ArrowDown": ("ArrowDown", 40, None), "Tab": ("Tab", 9, None)}
INSTANT_PAGE = """<!doctype html><meta charset="utf-8"><body style="margin:0">
<script type="module">
%(component)s
</script>
<script type="module">
window.SENT = [];
const f = document.createElement('ask-form');
f.style.height = '400px';
f.addEventListener('ask-submit', (e) => { window.SENT.push(e.detail); });
document.body.append(f);
f.spec = %(spec)s;
window.FORM = f;
window.READY = true;
</script>
"""


@unittest.skipUnless(CHROME or os.environ.get("REQUIRE_CHROME"), "Chrome が無い")
class InstantConfirm(unittest.TestCase):
    """質問が 1 つだけ（単一選択・補足なし）のときの即確定を、**実際のキー入力とクリック**（DevTools Protocol の入力）で確かめる。

    プログラムから起こした click では見えない違いがある: Chromium は、既に選ばれているラジオで Space を押しても click を出さない
    （Sodashitsu の E2E で見つかった。click 頼みだと、既定で選ばれている選択肢を Space で決定できなかった）。"""

    @classmethod
    def setUpClass(cls):
        if not CHROME:
            raise AssertionError("Chrome が無いので ask-form.js を確かめられません")
        from chrome import Chrome
        cls.chrome = Chrome()
        cls.component = open(os.path.join(AF, "ask-form.js"), encoding="utf-8").read()

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    def open(self, default="a", allow_other=False):
        q = {"id": "q", "label": "Q", "options": ["a", "b", "c"], "allowOther": allow_other}
        if default:
            q["default"] = default
        spec = public(ask.normalize({"title": "t", "note": False, "questions": [q]}))
        c = self.chrome
        path = os.path.join(c.dir, "instant%d.html" % c.n)
        open(path, "w", encoding="utf-8").write(INSTANT_PAGE % {"component": self.component, "spec": json.dumps(spec, ensure_ascii=False)})
        c.call("Page.enable", c.sid)
        c.call("Page.navigate", c.sid, url="file://" + path)
        c.eval("new Promise(function(ok){function w(){window.READY&&FORM.shadowRoot.querySelector('input')?setTimeout(ok,100):setTimeout(w,50)};w()})")

    def focus(self, value):
        self.chrome.eval("FORM.shadowRoot.querySelector('input[value=%s]').focus()" % json.dumps(value))

    def key(self, key):
        code, vk, text = KEYS[key]
        c = self.chrome
        down = {"type": "keyDown" if text else "rawKeyDown", "key": key, "code": code, "windowsVirtualKeyCode": vk}
        if text:
            down["text"] = text
        c.call("Input.dispatchKeyEvent", c.sid, **down)
        c.call("Input.dispatchKeyEvent", c.sid, type="keyUp", key=key, code=code, windowsVirtualKeyCode=vk)

    def click(self, selector):
        c = self.chrome
        x, y = c.eval("(function(){var r=FORM.shadowRoot.querySelector(%s).getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})()" % json.dumps(selector))
        for t in ("mousePressed", "mouseReleased"):
            c.call("Input.dispatchMouseEvent", c.sid, type=t, x=x, y=y, button="left", clickCount=1)

    def sent(self):
        return self.chrome.eval("new Promise(function(ok){setTimeout(function(){ok(SENT.map(function(d){return d.answers.q}))},150)})")

    def test_space_on_the_already_checked_option(self):
        self.open(default="a")
        self.focus("a")
        self.key(" ")
        self.assertEqual(self.sent(), ["a"])

    def test_space_on_an_unchecked_option_confirms_once(self):
        self.open(default=None)
        self.focus("b")
        self.key(" ")
        self.assertEqual(self.sent(), ["b"])

    def test_arrow_does_not_confirm_then_space_does(self):
        self.open(default="a")
        self.focus("a")
        self.key("ArrowDown")
        self.assertEqual(self.sent(), [])
        self.key(" ")
        self.assertEqual(self.sent(), ["b"])

    def test_enter_on_the_already_checked_option(self):
        self.open(default="a")
        self.focus("a")
        self.key("Enter")
        self.assertEqual(self.sent(), ["a"])

    def test_click_on_the_already_checked_card(self):
        self.open(default="a")
        self.click("label.opt")
        self.assertEqual(self.sent(), ["a"])

    def test_click_on_another_card_confirms_once(self):
        self.open(default="a")
        self.click("label.opt:nth-of-type(2)")
        self.assertEqual(self.sent(), ["b"])

    def test_other_does_not_confirm(self):
        """「その他」は、選んだだけでは決定しない（入力してから決定する）。"""
        self.open(default="a", allow_other=True)
        self.chrome.eval("FORM.shadowRoot.querySelector('input[data-other]').focus()")
        self.key(" ")
        self.assertEqual(self.sent(), [])


@unittest.skipUnless(CHROME or os.environ.get("REQUIRE_CHROME"), "Chrome が無い")
class View(unittest.TestCase):
    """質問の横に成果物を見せる枠（定義の view）。HTML は隔離した枠に、回答の受け口とは別の合言葉のアドレスから読む。
    文字のファイルは文字として出す。部品（<ask-form>）には成果物を入れない。"""

    EVIL = ("<!doctype html><meta charset='utf-8'><title>成果物</title><h1 id='h'>成果物の本文</h1><script>"
            "window.RAN=true;"
            "fetch('../answer',{method:'POST',body:JSON.stringify({answers:{decision:'approve'},forged:true})}).catch(function(){});"   # 自分のアドレスから回答の受け口を作ってみる
            "fetch('../cancel',{method:'POST'}).catch(function(){});"
            "try{window.parent.document.title='HACKED'}catch(e){}"
            "</script>")

    @classmethod
    def setUpClass(cls):
        if not CHROME:
            raise AssertionError("Chrome が無いので、成果物の枠を確かめられません")
        from chrome import Chrome
        cls.chrome = Chrome()

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    STUB = ("<script>window.EventSource=function(){};window.SENT=[];window.close=function(){};"
            "window.fetch=function(u,o){SENT.push([String(u).split('/').pop(),o&&o.body||'']);return Promise.resolve({})};</script>")

    def serve(self, spec):
        """受け口を立てる（成果物は別の合言葉 tok-view の下）。→ (状態, アドレス, ページの HTML)"""
        import threading
        from http.server import ThreadingHTTPServer
        spec = ask.normalize(spec)
        files, views = spec.pop("_files"), spec.pop("_views")
        spec.update(_auto=False, _width=1400, _maxHeight=1000)
        state, page = ask.State(), ask.build_page(spec, "tok-view")
        server = ThreadingHTTPServer(("127.0.0.1", 0), ask.make_handler(state, "tok-answer", page.encode("utf-8"), files, views, "tok-view"))
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return state, "http://127.0.0.1:%d" % server.server_address[1], page

    def open(self, spec):
        """殻のページを、画面なしの Chrome で開く（通信は偽物に差し替える。送ったものは window.SENT に残る）。"""
        spec = ask.normalize(spec)
        spec.pop("_files"), spec.pop("_views")
        spec.update(_auto=False, _width=1400, _maxHeight=1000)
        page = ask.build_page(spec, "tok-view").replace('<div id="app">', self.STUB + '<div id="app">', 1)
        c = self.chrome
        path = os.path.join(c.dir, "view%d.html" % c.n)
        open(path, "w", encoding="utf-8").write(page)
        c.call("Emulation.setDeviceMetricsOverride", c.sid, width=1400, height=800, deviceScaleFactor=1, mobile=False)
        c.call("Page.enable", c.sid)
        c.call("Page.navigate", c.sid, url="file://" + path)
        c.eval("new Promise(function(ok){function w(){var f=document.getElementById('form');f&&f.shadowRoot&&f.shadowRoot.querySelector('[data-ask-submit]')?setTimeout(ok,300):setTimeout(w,50)};w()})")

    def files(self):
        d = helpers.tmpdir()
        html, md = os.path.join(d, "doc.html"), os.path.join(d, "notes.txt")
        open(html, "w", encoding="utf-8").write(self.EVIL)
        open(md, "w", encoding="utf-8").write("# 見出し\n\n<script>window.HACKED=1</script>\n<b>太字</b>\n")
        return html, md

    def test_definition(self):
        html, md = self.files()
        real_md = os.path.join(os.path.dirname(html), "design.md")
        open(real_md, "w", encoding="utf-8").write("# 設計\n")
        spec = ask.normalize({"view": [html, {"file": md, "title": "メモ"}, {"text": "その場の文字"}, real_md, {"file": real_md, "raw": True}],
                              "questions": [{"id": "a", "label": "A", "options": ["x"]}]})
        self.assertEqual([(v["kind"], v["title"]) for v in spec["view"]],
                         [("html", "doc.html"), ("text", "メモ"), ("text", "テキスト"), ("markdown", "design.md"), ("text", "design.md")])
        self.assertEqual((spec["view"][3]["src"], spec["view"][4]["text"]), ("view/1", "# 設計\n"))   # Markdown は整形して見せる。raw なら文字のまま
        self.assertEqual(spec["view"][0]["src"], "view/0")
        self.assertIn("<script>", spec["view"][1]["text"])            # 文字のファイルは、中身を文字として持つ
        self.assertEqual(spec["_views"], [(html, "text/html; charset=utf-8"), (real_md, "markdown")])
        self.assertIs(spec["paging"], False)                          # 質問の欄は狭いので、目次は出さない
        for bad, reason in (({"file": "nai.html"}, "view_missing"), ({"file": html, "text": "x"}, "view_invalid"), ({}, "view_invalid"), ([], "view_invalid"), (3, "view_invalid")):
            with self.subTest(bad=bad):
                with self.assertRaises(ask.SpecError) as e:
                    ask.normalize({"view": bad, "questions": [{"id": "a", "label": "A", "options": ["x"]}]})
                self.assertEqual(e.exception.reason, reason)
        self.assertNotIn("view", ask.normalize({"questions": [{"id": "a", "label": "A", "options": ["x"]}]}))   # 書かなければ、今までどおり

    def test_html_goes_into_an_isolated_frame(self):
        html, md = self.files()
        self.open(ask.review_spec([html, md]))
        got = self.chrome.eval("""(function(){var f=document.querySelector('#stage iframe'),R=document.getElementById('form').shadowRoot;
          return {sandbox:f.getAttribute('sandbox'),src:f.getAttribute('src'),ref:f.referrerPolicy,title:document.title,hasView:document.body.classList.contains('has-view'),
                  tabs:[].slice.call(document.querySelectorAll('#tabs button')).map(function(b){return b.textContent}),
                  formW:document.getElementById('form').getBoundingClientRect().width,viewW:document.getElementById('viewer').getBoundingClientRect().width,
                  index:R.querySelector('.index')?!R.querySelector('.index').hidden:false,inForm:R.querySelectorAll('iframe').length,
                  questions:[].slice.call(R.querySelectorAll('[data-ask-question]')).filter(function(x){return !x.hidden}).map(function(x){return x.dataset.askQuestion})}})()""")
        self.assertNotIn("allow-same-origin", got["sandbox"])         # 同じ origin として扱わない（回答の受け口・親の画面に触れない）
        self.assertIn("allow-scripts", got["sandbox"])
        self.assertEqual((got["src"], got["ref"]), ("/tok-view/view/0", "no-referrer"))   # 回答の受け口とは別の合言葉。親のアドレスも渡さない
        self.assertEqual((got["title"], got["hasView"], got["tabs"], got["inForm"], got["index"]), ("成果物の確認", True, ["doc.html", "notes.txt"], 0, False))
        self.assertEqual(got["questions"], ["decision", "remark"])
        self.assertGreater(got["viewW"], 800)
        self.assertLess(got["formW"], 500)

    def test_server_keeps_artifacts_apart_from_the_answer_endpoint(self):
        """成果物は、別の合言葉の下でだけ配る。そこから回答・取り消しは送れない。応答にも sandbox が付く（Chrome は使わない）。"""
        import urllib.error
        import urllib.request
        html, md = self.files()
        state, base, page = self.serve(ask.review_spec([html, md]))
        self.assertNotIn("tok-answer", page)                          # ページの中に、回答の受け口の合言葉を書かない（アドレスからだけ分かる）
        r = urllib.request.urlopen(base + "/tok-view/view/0")
        self.assertIn("sandbox", r.headers["Content-Security-Policy"])
        self.assertNotIn("allow-same-origin", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["Referrer-Policy"], "no-referrer")
        self.assertIn("成果物の本文", r.read().decode("utf-8"))
        self.assertEqual(urllib.request.urlopen(base + "/tok-answer/").headers["Referrer-Policy"], "no-referrer")
        for path, method in (("/tok-answer/view/0", "GET"), ("/tok-view/", "GET"), ("/tok-view/view/9", "GET"), ("/tok-view/view/1", "GET"),
                             ("/tok-view/answer", "POST"), ("/tok-view/cancel", "POST"), ("/tok-view/view/answer", "POST")):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(urllib.request.Request(base + path, data=b"{}" if method == "POST" else None, method=method))
                self.assertEqual(e.exception.code, 404)
        self.assertIsNone(state.result)

    def test_text_is_shown_as_text_and_tabs_switch(self):
        html, md = self.files()
        self.open(ask.review_spec([html, md]))
        got = self.chrome.eval("""new Promise(function(ok){document.querySelectorAll('#tabs button')[1].click();setTimeout(function(){
          var pre=document.querySelector('#stage pre'),fr=document.querySelector('#stage iframe');
          ok({text:pre.textContent,kids:pre.children.length,preShown:!pre.hidden,frameShown:!fr.hidden,hacked:window.HACKED||null,
              selected:[].slice.call(document.querySelectorAll('#tabs button')).map(function(b){return b.getAttribute('aria-selected')})})},100)})""")
        self.assertEqual(got["text"], "# 見出し\n\n<script>window.HACKED=1</script>\n<b>太字</b>\n")
        self.assertEqual((got["kids"], got["hacked"]), (0, None))     # HTML として解釈しない
        self.assertEqual((got["preShown"], got["frameShown"], got["selected"]), (True, False, ["false", "true"]))

    MD = ("# 設計\n\n本文 **太字**\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```mermaid\ngraph LR\n  A --> B\n```\n\n```mermaid\nこれは図ではない\n```\n\n"
          "<script>window.HACKED=1</script>\n")

    def test_markdown_is_rendered_with_the_bundled_libraries(self):
        """Markdown は、同梱の marked・mermaid で整形して見せる。描けない図はコードのまま残す。ライブラリが読めなければ、文字のまま出す。"""
        c = self.chrome
        ready = "new Promise(function(ok){var n=0;function w(){(document.documentElement.dataset.ready||!document.getElementById('source').hidden||++n>150)?setTimeout(ok,100):setTimeout(w,100)};w()})"
        path = os.path.join(c.dir, "md%d.html" % c.n)
        open(path, "w", encoding="utf-8").write(ask.markdown_page(self.MD, "design.md", "file://" + os.path.join(AF, "vendor") + "/"))
        c.call("Page.enable", c.sid)
        c.call("Page.navigate", c.sid, url="file://" + path)
        c.eval(ready)
        got = c.eval("""(function(){var d=document.getElementById('doc');return {h1:d.querySelector('h1').textContent,strong:d.querySelector('strong').textContent,
          cells:d.querySelectorAll('td').length,figs:d.querySelectorAll('.mermaid svg').length,left:d.querySelectorAll('pre code.language-mermaid').length,
          errors:d.querySelectorAll('.mermaid-error').length,hacked:window.HACKED||null,toggle:!document.getElementById('toggle').hidden,
          source:document.getElementById('source').textContent}})()""")
        self.assertEqual((got["h1"], got["strong"], got["cells"]), ("設計", "太字", 2))
        self.assertEqual((got["figs"], got["left"], got["errors"]), (1, 1, 1))     # 1 つは図に、描けない 1 つはコードのまま＋理由
        self.assertEqual((got["hacked"], got["toggle"], got["source"]), (None, True, self.MD))
        c.eval("document.getElementById('toggle').click()")                        # ソースを見る
        self.assertEqual(c.eval("[document.getElementById('doc').hidden, document.getElementById('source').hidden]"), [True, False])
        # ライブラリが読めないとき
        open(path, "w", encoding="utf-8").write(ask.markdown_page(self.MD, "design.md", "file:///nai/"))
        c.call("Page.navigate", c.sid, url="file://" + path)
        c.eval(ready)
        self.assertEqual(c.eval("[document.getElementById('doc').hidden, document.getElementById('source').hidden, document.getElementById('source').textContent]"),
                         [True, False, self.MD])

    def test_server_serves_markdown_page_and_only_listed_libraries(self):
        import urllib.error
        import urllib.request
        d = helpers.tmpdir()
        md = os.path.join(d, "design.md")
        open(md, "w", encoding="utf-8").write(self.MD)
        state, base, page = self.serve(ask.review_spec([md]))
        r = urllib.request.urlopen(base + "/tok-view/view/0")
        body = r.read().decode("utf-8")
        self.assertEqual(r.headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("sandbox", r.headers["Content-Security-Policy"])
        self.assertIn('const LIB = "../lib/"', body)
        self.assertNotIn("</script>\n<script>window.HACKED", body)                 # 元の文字は、スクリプトの中の文字列として入る
        self.assertIn("<\\/script>", body)
        for name in ("marked.umd.js", "mermaid.min.js"):
            r = urllib.request.urlopen(base + "/tok-view/lib/" + name)
            self.assertTrue(r.headers["Content-Type"].startswith("text/javascript"))
            self.assertGreater(len(r.read()), 10000)
        for path in ("/tok-view/lib/SOURCE.json", "/tok-view/lib/..%2Fask.py", "/tok-view/lib/../ask.py", "/tok-answer/lib/marked.umd.js", "/tok-view/lib/"):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(base + path)
                self.assertEqual(e.exception.code, 404)

    def test_bundled_libraries_are_unmodified(self):
        """同梱のライブラリは、配布元のファイルそのまま（vendor/SOURCE.json の sha256 と一致）。ライセンスの文も置いてある。"""
        import hashlib
        src = json.load(open(os.path.join(AF, "vendor", "SOURCE.json"), encoding="utf-8"))
        self.assertEqual(sorted(src["files"]), sorted(ask.VIEW_LIBS))
        for name, info in src["files"].items():
            with self.subTest(name):
                self.assertEqual(hashlib.sha256(open(os.path.join(AF, "vendor", name), "rb").read()).hexdigest(), info["sha256"])
                self.assertTrue(os.path.getsize(os.path.join(AF, "vendor", info["license_file"])) > 500)

    def test_review_answer(self):
        html, md = self.files()
        self.open(ask.review_spec([html]))
        sent = lambda: [json.loads(b) for name, b in self.chrome.eval("SENT") if name == "answer"]
        self.assertEqual(self.chrome.eval("getComputedStyle(document.getElementById('tabs')).display"), "none")   # 1 つだけなら、タブは出さない
        self.chrome.eval("""new Promise(function(ok){var R=document.getElementById('form').shadowRoot;
          R.querySelector('input[value=revise]').click();
          setTimeout(function(){document.getElementById('form').submit();setTimeout(ok,200)},100)})""")
        self.assertEqual(sent(), [])                                  # 修正の依頼は、直してほしい所を書くまで決定できない
        self.chrome.eval("""new Promise(function(ok){var R=document.getElementById('form').shadowRoot,t=R.querySelector('textarea[name=comment]');
          t.value='2 章の表を直す';t.dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('form').submit();setTimeout(ok,300)})""")
        self.assertEqual([a["answers"] for a in sent()], [{"decision": "revise", "comment": "2 章の表を直す"}])


if __name__ == "__main__":
    unittest.main()
