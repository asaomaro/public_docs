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
                     "data-ask-next", "data-ask-prev", "data-ask-page", "ask-submit", "ask-cancel", "ask-unsupported",
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
      else if (i.value === '__other__') {
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


if __name__ == "__main__":
    unittest.main()
