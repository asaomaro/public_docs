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
// md-to-doc の corporate テーマを移植。Gmail は var() 非対応なので hex を焼き込み、
// ダークモードは template.html の @media によるクラス上書きで対応する。

const esc = (s) => String(s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const FONT = "'Hiragino Kaku Gothic ProN','Yu Gothic',system-ui,sans-serif";
const MONO = "'SFMono-Regular',Menlo,Consolas,monospace";

// corporate の循環アクセント（ライト値）。ダーク値は template.html 側の .aNt/.aNb。
const ACCENTS = ['#1a56db', '#0ea5e9', '#6366f1', '#0d9488'];
const INK = '#1f2937', MUTED = '#6b7280', LINE = '#e5e7eb', SOFT = '#eff4ff';

function formatDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const wd = '日月火水木金土'[new Date(y, m - 1, d).getDay()];
  return `${y}年${m}月${d}日（${wd}）`;
}

const total = sections.reduce((n, s) => n + s.items.length, 0);

// --- .stat-row 相当 ---
const stat = (num, cap) => `<td style="padding-right:30px;">
          <div class="statnum" style="font-family:${FONT}; font-size:27px; font-weight:700; line-height:1.1; color:${ACCENTS[0]};">${esc(num)}</div>
          <div class="muted" style="font-family:${FONT}; font-size:10.5px; font-weight:600; letter-spacing:0.07em; color:${MUTED}; padding-top:4px;">${esc(cap)}</div>
        </td>`;

const stats = stat(String(total), '件') + stat(String(sections.length), '分野');

// --- .chips 相当 ---
const chips = sections.map((sec) =>
  `<span class="chip line" style="display:inline-block; background-color:${SOFT}; color:${INK}; border:1px solid ${LINE}; border-radius:999px; padding:4px 12px; margin:0 6px 7px 0; font-family:${FONT}; font-size:11.5px; font-weight:600;">${esc(sec.title)}</span>`
).join('\n        ');

// --- 本体 ---
const body = sections.map((sec, si) => {
  const ac = ACCENTS[si % ACCENTS.length];
  const t = `a${si % ACCENTS.length}t`;
  const b = `a${si % ACCENTS.length}b`;

  const head = `      <tr><td class="pad" style="padding:30px 32px 0 32px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
          <td class="${t}" style="font-family:${FONT}; font-size:11.5px; font-weight:700; letter-spacing:0.09em; color:${ac}; white-space:nowrap; padding-right:12px;">${esc(sec.title)}</td>
          <td class="line" style="border-top:1px solid ${LINE}; font-size:0; line-height:0;">&nbsp;</td>
        </tr></table>
      </td></tr>`;

  const items = sec.items.map((it) => {
    const meta = [esc(it.source), it.published ? esc(it.published) : null]
      .filter(Boolean).join(' &nbsp;·&nbsp; ');

    // .callout 相当
    const why = isStr(it.why) ? `
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:12px;">
          <tr><td class="soft ${b}" style="background-color:${SOFT}; border-left:3px solid ${ac}; border-radius:0 8px 8px 0; padding:11px 14px;">
            <div class="${t}" style="font-family:${FONT}; font-size:10px; font-weight:700; letter-spacing:0.09em; color:${ac}; padding-bottom:4px;">なぜ重要か</div>
            <div class="text" style="font-family:${FONT}; font-size:13px; line-height:1.7; color:${INK};">${esc(it.why)}</div>
          </td></tr>
          </table>` : '';

    // .doc-card 相当（左アクセント罫）
    return `      <tr><td class="pad" style="padding:18px 32px 0 32px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr><td class="${b}" style="border-left:3px solid ${ac}; padding-left:15px;">
          <a class="link" href="${esc(it.url)}" style="font-family:${FONT}; font-size:16.5px; font-weight:700; line-height:1.5; color:${ACCENTS[0]}; text-decoration:none;">${esc(it.title)}</a>
          <div class="muted" style="font-family:${FONT}; font-size:11.5px; color:${MUTED}; padding-top:6px;">${meta}</div>
          <div class="text" style="font-family:${FONT}; font-size:14px; line-height:1.8; color:${INK}; padding-top:9px;">${esc(it.summary)}</div>${why}
        </td></tr>
        </table>
      </td></tr>`;
  }).join('\n');

  return `${head}\n${items}`;
}).join('\n');

const preheader = `${formatDate(data.date)} — ${total} 件 / ${String(data.summary).slice(0, 80)}`;

const html = template
  .replace(/\{\{DATE\}\}/g, esc(formatDate(data.date)))
  .replace(/\{\{SUMMARY\}\}/g, esc(data.summary))
  .replace(/\{\{STATS\}\}/g, stats)
  .replace(/\{\{CHIPS\}\}/g, chips)
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
