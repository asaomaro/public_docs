#!/usr/bin/env node
// items.json + template.html -> htmlBody.html / body.txt
//
//   node md/claude-code/routines/build.mjs /tmp/items.json --out /tmp/digest
//
// 依存パッケージなし。Node 18+ の ESM で動く。
// スキーマ違反は全部まとめて報告して exit 1。

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

// ---------- args ----------

const argv = process.argv.slice(2);
let itemsPath = null;
let outDir = null;

for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--out') outDir = argv[++i];
  else if (!itemsPath) itemsPath = argv[i];
  else die(`予期しない引数: ${argv[i]}`);
}
if (!itemsPath) die('使い方: build.mjs <items.json> [--out <dir>]');
itemsPath = resolve(itemsPath);
outDir = resolve(outDir ?? dirname(itemsPath));

function die(msg) {
  console.error(`build.mjs: ${msg}`);
  process.exit(1);
}

// ---------- load ----------

let data;
try {
  data = JSON.parse(readFileSync(itemsPath, 'utf8'));
} catch (e) {
  die(`${itemsPath} を JSON として読めない: ${e.message}`);
}

const template = readFileSync(join(HERE, 'template.html'), 'utf8');

// ---------- validate ----------

const errors = [];
const isStr = (v) => typeof v === 'string' && v.trim() !== '';

if (!isStr(data.date) || !/^\d{4}-\d{2}-\d{2}$/.test(data.date)) {
  errors.push('date が無いか YYYY-MM-DD 形式でない');
}
if (!isStr(data.summary)) errors.push('summary が無い');
if (!Array.isArray(data.sections) || data.sections.length === 0) {
  errors.push('sections が無いか空');
}

const seen = new Set();
const sections = [];

for (const [si, sec] of (data.sections ?? []).entries()) {
  const at = `sections[${si}]`;
  if (!isStr(sec?.title)) { errors.push(`${at}.title が無い`); continue; }
  if (!Array.isArray(sec.items) || sec.items.length === 0) {
    errors.push(`${at} (${sec.title}) の items が無いか空。空セクションは書かない`);
    continue;
  }

  const kept = [];
  for (const [ii, it] of sec.items.entries()) {
    const iat = `${at}.items[${ii}]`;
    const bad = [];
    if (!isStr(it?.title)) bad.push('title');
    if (!isStr(it?.summary)) bad.push('summary');
    if (!isStr(it?.source)) bad.push('source');
    if (!isStr(it?.url)) bad.push('url');
    else if (!/^https?:\/\//i.test(it.url)) bad.push('url (http/https でない)');
    if (it?.published != null && !/^\d{4}-\d{2}-\d{2}$/.test(it.published)) {
      bad.push('published (YYYY-MM-DD でない)');
    }
    if (bad.length) { errors.push(`${iat} の不備: ${bad.join(', ')}`); continue; }

    const key = normalizeUrl(it.url);
    if (seen.has(key)) continue;   // 同一 URL は最初の 1 件だけ残す
    seen.add(key);
    kept.push(it);
  }
  if (kept.length) sections.push({ title: sec.title, items: kept });
}

if (sections.length === 0) errors.push('有効な item が 1 件も無い');

if (errors.length) {
  console.error('build.mjs: items.json のスキーマ違反:');
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}

function normalizeUrl(u) {
  try {
    const url = new URL(u);
    url.hash = '';
    for (const k of [...url.searchParams.keys()]) {
      if (/^(utm_|fbclid|gclid|ref$|ref_)/i.test(k)) url.searchParams.delete(k);
    }
    return url.toString().replace(/\/$/, '').toLowerCase();
  } catch { return u.toLowerCase(); }
}

// ---------- render ----------

const esc = (s) => String(s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const SANS = "-apple-system,BlinkMacSystemFont,'Hiragino Sans','Yu Gothic',Meiryo,sans-serif";

function formatDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const wd = '日月火水木金土'[new Date(y, m - 1, d).getDay()];
  return `${y}年${m}月${d}日（${wd}）`;
}

const total = sections.reduce((n, s) => n + s.items.length, 0);

const body = sections.map((sec) => {
  const head = `      <tr><td class="pad" style="padding:28px 32px 0 32px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
          <td class="muted" style="font-family:${SANS}; font-size:11px; font-weight:700; letter-spacing:0.08em; color:#78716c; white-space:nowrap; padding-right:12px;">${esc(sec.title).toUpperCase()}</td>
          <td class="rule" style="border-top:1px solid #e7e5e4; font-size:0; line-height:0;">&nbsp;</td>
        </tr></table>
      </td></tr>`;

  const items = sec.items.map((it) => {
    const meta = [esc(it.source), it.published ? esc(it.published) : null]
      .filter(Boolean).join(' &nbsp;·&nbsp; ');
    const why = isStr(it.why)
      ? `\n        <p class="muted" style="margin:8px 0 0 0; font-family:${SANS}; font-size:13px; line-height:1.6; color:#78716c;"><span class="chip" style="display:inline-block; background-color:#f5f5f4; color:#57534e; border-radius:4px; padding:1px 6px; font-size:11px; font-weight:700; margin-right:6px;">なぜ重要か</span>${esc(it.why)}</p>`
      : '';
    return `      <tr><td class="pad" style="padding:20px 32px 0 32px;">
        <a class="link" href="${esc(it.url)}" style="font-family:${SANS}; font-size:16px; font-weight:700; line-height:1.5; color:#b45309; text-decoration:none;">${esc(it.title)}</a>
        <p class="muted" style="margin:6px 0 0 0; font-family:${SANS}; font-size:12px; color:#78716c;">${meta}</p>
        <p class="text" style="margin:8px 0 0 0; font-family:${SANS}; font-size:14px; line-height:1.75; color:#1c1917;">${esc(it.summary)}</p>${why}
      </td></tr>`;
  }).join('\n');

  return `${head}\n${items}`;
}).join('\n');

const preheader = `${formatDate(data.date)} — ${total} 件 / ${String(data.summary).slice(0, 80)}`;

const html = template
  .replace(/\{\{DATE\}\}/g, esc(formatDate(data.date)))
  .replace(/\{\{SUMMARY\}\}/g, esc(data.summary))
  .replace(/\{\{COUNT\}\}/g, String(total))
  .replace(/\{\{PREHEADER\}\}/g, esc(preheader))
  .replace(/\{\{BODY\}\}/g, body);

const leftover = html.match(/\{\{[A-Z_]+\}\}/g);
if (leftover) die(`テンプレートに未置換のプレースホルダが残った: ${[...new Set(leftover)].join(', ')}`);

// ---------- plain text ----------

const text = [
  `AI Daily Digest — ${formatDate(data.date)}`,
  '='.repeat(48),
  '',
  data.summary,
  `（${total} 件）`,
  '',
  ...sections.flatMap((sec) => [
    `## ${sec.title}`,
    '',
    ...sec.items.flatMap((it) => [
      `* ${it.title}`,
      `  ${it.source}${it.published ? ` / ${it.published}` : ''}`,
      `  ${it.url}`,
      `  ${it.summary}`,
      ...(isStr(it.why) ? [`  → ${it.why}`] : []),
      '',
    ]),
  ]),
].join('\n');

// ---------- write ----------

// ファイル名は send_message の引数名そのもの。htmlBody.html -> htmlBody,
// body.txt -> body。取り違えると生ソースが届くので、名前で対応を固定しておく。
mkdirSync(outDir, { recursive: true });
const htmlPath = join(outDir, 'htmlBody.html');
const textPath = join(outDir, 'body.txt');
writeFileSync(htmlPath, html, 'utf8');
writeFileSync(textPath, text, 'utf8');

console.log(`件名: AI Daily Digest ${formatDate(data.date)}`);
console.log('');
console.log('Gmail コネクタ send_message の引数（ファイル名 = 引数名）:');
console.log('  subject  = 上の「件名:」の値をそのまま（接尾辞を付けない）');
console.log(`  htmlBody = ${htmlPath} の中身をそのまま (${Buffer.byteLength(html)} bytes, ${total} 件)`);
console.log(`  body     = ${textPath} の中身をそのまま (${Buffer.byteLength(text)} bytes)`);
console.log('');
console.log('htmlBody.html を body に渡すとエスケープされた生ソースが届く。逆も同じ。');
console.log('送信後は get_message (messageFormat: PLAIN_TEXT) で読み直し、');
console.log('本文が "<!doctype" で始まっていないことを必ず確認する。');
