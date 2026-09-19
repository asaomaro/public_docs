import { randomBytes } from "node:crypto";

// 画面は通信もファイル読み込みもしない。nonce の無いスクリプトは動かさない。
// img-src data: は rich diff の SVG 画像、frame-src 'self' は rich diff の <iframe sandbox srcdoc> のため
// （research.md F4-F6）。
export function cspFor(nonce: string): string {
  return [
    "default-src 'none'",
    "img-src data:",
    "style-src 'unsafe-inline'",
    `script-src 'nonce-${nonce}'`,
    "frame-src 'self'",
  ].join("; ") + ";";
}

export function makeNonce(): string {
  return randomBytes(18).toString("base64");
}

const CHARSET = '<meta charset="utf-8">';

// 本物の <script> タグはすべて行頭にある。行頭に限るのは、埋め込まれた JS のコメントや文字列に
// 現れる "<script" を書き換えないため。
export function withCsp(template: string, nonce: string): string {
  if (!template.includes(CHARSET)) {
    throw new Error(`viewer.html に ${CHARSET} がありません（diff_review.py view の出力ではない）`);
  }
  const meta = `<meta http-equiv="Content-Security-Policy" content="${cspFor(nonce)}">`;
  return template
    .replace(CHARSET, `${CHARSET}\n${meta}`)
    .replace(/^<script/gm, `<script nonce="${nonce}"`);
}
