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
import unittest

import fakes

AF = os.path.join(fakes.OTHER, "ask-form")
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
                     "data-ask-index", "ask-submit", "ask-cancel", "ask-unsupported",
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
        d = fakes.tmpdir()
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
        from test_engine import Chrome
        cls.chrome = Chrome()
        cls.component = open(os.path.join(AF, "ask-form.js"), encoding="utf-8").read()

    @classmethod
    def tearDownClass(cls):
        cls.chrome.close()

    def open(self, questions, **top):
        spec = public(ask.normalize(dict({"title": "t", "questions": questions}, **top)))
        c = self.chrome
        c.call("Emulation.setDeviceMetricsOverride", c.sid, width=1000, height=400, deviceScaleFactor=1, mobile=False)
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
        from test_engine import Chrome
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


if __name__ == "__main__":
    unittest.main()
