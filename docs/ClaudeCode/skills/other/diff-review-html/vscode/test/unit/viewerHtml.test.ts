import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cspFor, makeNonce, withCsp } from "../../src/viewerHtml";

const extRoot = join(__dirname, "..", "..", "..");
const viewerPath = join(extRoot, "media", "viewer.html");
const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");

test("同梱のビューアは diff_review.py view の出力そのもの", () => {
  const result = spawnSync(python, [join(extRoot, "..", "diff_review.py"), "view"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(readFileSync(viewerPath, "utf8"), result.stdout);
});

test("CSP は charset の直後に入り、通信とファイル読み込みを許さない", () => {
  const html = withCsp(readFileSync(viewerPath, "utf8"), "N0nce");
  const head = html.split("</head>")[0];
  assert.match(head, /<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="[^"]+">/);
  const csp = cspFor("N0nce");
  assert.ok(html.includes(`content="${csp}"`));
  assert.match(csp, /default-src 'none'/);
  assert.match(csp, /script-src 'nonce-N0nce'/);
  assert.doesNotMatch(csp, /connect-src|unsafe-eval|https?:/);
});

test("行頭の <script には nonce を付け、JS の中の \"<script\" は書き換えない", () => {
  const template = readFileSync(viewerPath, "utf8");
  const html = withCsp(template, "N0nce");
  const tags = template.match(/^<script/gm) || [];
  assert.ok(tags.length >= 7, "ビューアのスクリプトと JSON のブロック");
  assert.equal((html.match(/^<script nonce="N0nce"/gm) || []).length, tags.length);
  assert.equal((html.match(/^<script(?! nonce)/gm) || []).length, 0);
  const inner = (template.match(/<script/g) || []).length - tags.length;
  assert.ok(inner >= 1, "今のビューアには app.js のコメント内に \"<script src>\" がある");
  assert.equal((html.match(/<script(?! nonce="N0nce")/g) || []).length, inner, "行頭以外は元のまま");
  assert.ok(html.includes('<script nonce="N0nce" type="application/json" id="bundle-data"></script>'), "#bundle-data は空のまま");
});

test("小さな入力でも: 行頭のタグだけに nonce、コードの中の \"<script\" と CRLF の行頭は区別する", () => {
  const template = [
    "<!doctype html>",
    '<meta charset="utf-8">',
    "<script>",
    '  x("<script"); // <script src> in a comment',
    '</script><script type="application/json" id="d"></script>',
    "<script>y()</script>",
  ].join("\r\n");
  const html = withCsp(template, "Q");
  assert.equal((html.match(/<script nonce="Q"/g) || []).length, 2);
  assert.ok(html.includes('x("<script"); // <script src> in a comment'));
  assert.ok(html.includes('</script><script type="application/json" id="d">'), "行頭でないタグには付けない");
});

test("diff_review.py view の出力でないものは拒む", () => {
  assert.throws(() => withCsp("<html><head></head></html>", "x"), /charset/);
});

test("nonce は毎回違う", () => {
  assert.notEqual(makeNonce(), makeNonce());
  assert.match(makeNonce(), /^[A-Za-z0-9+/]+=*$/);
});
