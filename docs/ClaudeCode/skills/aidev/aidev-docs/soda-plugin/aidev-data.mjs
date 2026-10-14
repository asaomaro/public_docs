// `.aidev/` の読み取り専用の層。ここから先（台帳・画面）はこの形だけを見る。
// 書き込みはしない（aidev の state は CLI と工程スキルだけが書く）。読むパスは `.aidev/` の中だけ。
import { open, readdir, lstat, realpath } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { homedir } from 'node:os';
import { join, sep } from 'node:path';
import { createHash } from 'node:crypto';
import { promisify } from 'node:util';

const execute = promisify(execFile);

/** 読み取りで受け付ける作業名（既存のフォルダ名）。エージェントの slug は operations.mjs 側でもっと狭く縛る。 */
export const READ_SLUG = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
export const LIMITS = { works: 1000, doc: 512 * 1024, small: 1024 * 1024, events: 30, tasks: 300, backlogItems: 50, backlogFiles: 100, text: 200 };
export const PHASES = ['requirements', 'research', 'design', 'architecture', 'tasks', 'coding', 'test', 'review', 'deliver', 'retro'];
export const OPTIONAL_PHASES = ['research', 'architecture', 'retro'];
const PHASE_DOCS = { requirements: 'requirements.md', research: 'research.md', design: 'design.md', architecture: 'architecture.md', tasks: 'tasks.md', test: 'test-result.md', review: 'review.md', retro: 'retro.md' };

const clip = (s, n = LIMITS.text) => { const t = String(s ?? ''); return t.length > n ? t.slice(0, n - 1) + '…' : t; };
const within = (base, target) => target === base || target.startsWith(base.endsWith(sep) ? base : base + sep);
const fail = (message) => Object.assign(new Error(message), { expected: true });

/** 通常のファイル（シンボリックリンクは不可）を上限つきで読む。 */
export async function readCapped(file, max) {
  const st = await lstat(file);
  if (!st.isFile()) throw fail('通常のファイルではありません');
  const handle = await open(file, 'r');
  try {
    const length = Math.min(st.size, max);
    const buffer = Buffer.alloc(length);
    const { bytesRead } = await handle.read(buffer, 0, length, 0);
    return { text: buffer.subarray(0, bytesRead).toString('utf8'), truncated: st.size > max, size: st.size, mtimeMs: st.mtimeMs };
  } finally { await handle.close(); }
}
const readOptional = async (file, max = LIMITS.small) => { try { return await readCapped(file, max); } catch { return null; } };

/** `.aidev` の実体のパス（PJ の中にあるものだけ）。無い・外へ出る → null。 */
export async function resolveAidev(root) {
  try {
    const [real, realRoot] = await Promise.all([realpath(join(root, '.aidev')), realpath(root)]);
    return real !== realRoot && within(realRoot, real) ? real : null;
  } catch { return null; }
}
async function resolveWorksDir(aidev) {
  try {
    const real = await realpath(join(aidev, 'works'));
    return within(aidev, real) ? real : null;
  } catch { return null; }
}

// ---- 簡易パーサ ----------------------------------------------------------------------------------

const unquote = (v) => (/^(["']).*\1$/.test(v) ? v.slice(1, -1) : v);
function parseValue(raw) {
  let v = raw.trim();
  if (!/^["']/.test(v)) v = v.replace(/\s+#.*$/, '').trim();
  if (v === '~' || v === 'null') return '';
  const list = /^\[(.*)\]$/.exec(v);
  if (list) return list[1].split(',').map((x) => unquote(x.trim())).filter(Boolean).map((x) => clip(x, 120)).slice(0, 64);
  return clip(unquote(v), 300);
}
/** 行単位の `key: value` と `[a, b]` だけを読む（入れ子・複数行は読まない）。壊れた行は飛ばす。 */
export function parseState(text) {
  const out = {};
  let count = 0;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    if (!line || /^\s/.test(line) || line.startsWith('#')) continue;
    const m = /^([A-Za-z_][A-Za-z0-9_-]{0,63}):\s*(.*)$/.exec(line);
    if (!m || Object.hasOwn(out, m[1]) || count >= 64) continue;
    out[m[1]] = parseValue(m[2]);
    count++;
  }
  return out;
}
export function parseTasks(text) {
  const items = [];
  let done = 0, total = 0;
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const m = /^- \[( |x|X)\]\s*(.*)$/.exec(line);
    if (!m) continue;
    total++;
    const checked = m[1] !== ' ';
    if (checked) done++;
    if (items.length < LIMITS.tasks) items.push({ done: checked, text: clip(m[2]) });
  }
  return { done, total, items };
}
/** `events:` の行（`- { ts: …, phase: …, event: …, metrics: {…} }`）から時刻・工程・種類と、一言の補足を読む。 */
export function parseEvents(text) {
  const events = [];
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const m = /^\s*-\s*\{\s*ts:\s*([^,}]+?)\s*,\s*phase:\s*([^,}]+?)\s*,\s*event:\s*([^,}]+?)\s*(?:,|\})/.exec(line);
    if (!m) continue;
    const note = ['stage', 'result', 'task'].map((k) => new RegExp(`[{,]\\s*${k}:\\s*([^,}\\s]+)`).exec(line)?.[1]).filter(Boolean).join(' ');
    events.push({ ts: clip(m[1], 40), phase: clip(m[2], 40), event: clip(m[3], 40), note: clip(note, 80) });
  }
  return events;
}
export function parseBacklog(text) {
  let todo = 0, done = 0;
  const items = [];
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const m = /^\s*-\s\[( |x|X)\]\s*(.*)$/.exec(line);
    if (!m) continue;
    if (m[1] === ' ') { todo++; if (items.length < LIMITS.backlogItems) items.push(clip(m[2])); } else done++;
  }
  return { todo, done, items };
}
/** `aidev status --format tsv` の `work` 行（8 列: work slug ticket mode current next state deps）。 */
export function parseStatusTsv(text) {
  const rows = new Map();
  for (const line of String(text ?? '').split(/\r?\n/)) {
    const c = line.split('\t');
    if (c[0] !== 'work' || c.length < 8 || !READ_SLUG.test(c[1])) continue;
    const dash = (v) => (v === '-' ? '' : clip(v, 120));
    rows.set(c[1], { ticket: dash(c[2]), mode: dash(c[3]), current: dash(c[4]), next: dash(c[5]), state: dash(c[6]), deps: clip(c[7], 200) });
  }
  return rows;
}

// ---- aidev CLI ----------------------------------------------------------------------------------

/** `<PJ>/.claude/skills/aidev-docs/bin/aidev`（無ければ `.agents/skills`）、無ければ `$HOME` の同じ場所。 */
export async function findCli(root, home = homedir()) {
  // Claude Code は `.claude/skills`、Codex 用の写しは `.agents/skills`
  for (const base of [root, home]) {
    if (!base) continue;
    for (const dir of ['.claude', '.agents']) {
      const file = join(base, dir, 'skills', 'aidev-docs', 'bin', 'aidev');
      try { if ((await lstat(file)).isFile()) return file; } catch { /* 次の候補 */ }
    }
  }
  return null;
}
/** シェルを介さない。cwd は PJ、15 秒で打ち切る。使えなければ null（自前の読み取りだけになる）。 */
export async function runStatus(root, { run = execute, home } = {}) {
  const cli = await findCli(root, home);
  if (!cli) return null;
  try {
    const { stdout } = await run('sh', [cli, 'status', '--all', '--format', 'tsv'], { cwd: root, timeout: 15000, maxBuffer: 8 * 1024 * 1024, windowsHide: true });
    return String(stdout);
  } catch { return null; }
}

// CLI は作業が多いと遅い（実測で 150 件ほどの PJ で 12〜13 秒）。画面の更新を止めないよう、結果は背景で取って
// 前回の値を使う。変化（署名）があったときに、前回の開始から minIntervalMs 以上空いていれば取り直す。
const statusCache = new Map();
export function resetStatusCache() { statusCache.clear(); }
/**
 * `wait`: false = 前回の値を返して背景で取り直す／'if-empty' = まだ一度も読めていなければ終わるのを待つ／true = 常に待つ。
 * 読めなかった（CLI なし・失敗・時間切れ）間は null（自前の読み取りだけになる）。
 */
async function statusText(root, { run, home, sig = '', wait = false, onUpdate, minIntervalMs = 30000, now = Date.now } = {}) {
  let rec = statusCache.get(root);
  if (!rec) { rec = { text: null, sig: null, lastStart: -Infinity, running: null }; statusCache.set(root, rec); }
  const due = rec.sig === null || (rec.sig !== sig && now() - rec.lastStart >= minIntervalMs);
  if (!rec.running && due) {
    rec.lastStart = now();
    rec.sig = sig;
    rec.running = runStatus(root, { run, home })
      .then((text) => { if (text !== null) rec.text = text; })
      .catch(() => {})
      .finally(() => { rec.running = null; })
      .then(() => onUpdate?.())
      .catch(() => {});
  }
  if (rec.running && (wait === true || (wait === 'if-empty' && rec.text === null))) await rec.running;
  return rec.text;
}

// ---- 作業・backlog --------------------------------------------------------------------------------

function deriveState(state, hasState) {
  if (!hasState) return 'broken';
  if (state.status === 'abandoned') return 'abandoned';
  const approved = Array.isArray(state.approved) ? state.approved : [];
  return approved.includes('deliver') ? 'done' : 'active';
}
const asList = (v) => (Array.isArray(v) ? v : v ? [v] : []);

async function listWorkSlugs(aidev) {
  const dir = await resolveWorksDir(aidev);
  if (!dir) return { dir: null, slugs: [], truncated: false };
  let entries;
  try { entries = await readdir(dir, { withFileTypes: true }); } catch { return { dir: null, slugs: [], truncated: false }; }
  const all = entries.filter((e) => e.isDirectory() && READ_SLUG.test(e.name)).map((e) => e.name).sort();
  const truncated = all.length > LIMITS.works;
  return { dir, slugs: truncated ? all.slice(all.length - LIMITS.works) : all, truncated };
}

async function readWorkSummary(dir, slug, cliRow, current) {
  const [stateFile, tasksFile] = await Promise.all([readOptional(join(dir, slug, 'state.yml'), 64 * 1024), readOptional(join(dir, slug, 'tasks.md'))]);
  const state = stateFile ? parseState(stateFile.text) : {};
  const tasks = parseTasks(tasksFile?.text);
  const derived = deriveState(state, !!stateFile);
  const cliState = cliRow?.state === '着地済' ? 'done' : '';
  return {
    slug,
    state: derived === 'broken' && cliState ? cliState : derived,
    current: clip(state.current ?? cliRow?.current ?? '', 40),
    next: cliRow?.next ?? '',
    mode: clip(state.mode ?? cliRow?.mode ?? '', 40),
    profile: clip(state.profile ?? '', 40),
    ticket: cliRow?.ticket ?? '',
    approved: asList(state.approved).slice(0, 16),
    dependsOn: asList(state.dependsOn).slice(0, 16),
    deps: cliRow?.deps ?? '',
    tasks: { done: tasks.done, total: tasks.total },
    isCurrent: current === slug,
    broken: !stateFile,
  };
}

export async function readCurrent(aidev) {
  const file = await readOptional(join(aidev, 'current'), 1024);
  const line = file?.text.split(/\r?\n/)[0]?.trim() ?? '';
  return READ_SLUG.test(line) ? line : null;
}

export async function readBacklog(aidev) {
  const dir = join(aidev, 'backlog');
  let entries;
  try { entries = await readdir(dir, { withFileTypes: true }); } catch { return []; }
  const files = entries.filter((e) => e.isFile() && /^[^/\\]+\.md$/.test(e.name)).map((e) => e.name).sort().slice(0, LIMITS.backlogFiles);
  const out = [];
  for (const file of files) {
    const read = await readOptional(join(dir, file));
    if (read) out.push({ file: clip(file, 120), ...parseBacklog(read.text) });
  }
  return out;
}

/** 作業の一覧・current・backlog をまとめて読む。 */
export async function loadOverview(root, deps = {}) {
  const aidev = await resolveAidev(root);
  if (!aidev) return { available: false, works: [], total: 0, truncated: false, current: null, backlog: [], cli: false };
  const sig = deps.sig ?? await dataSignature(root);
  const [listing, text, current, backlog] = await Promise.all([listWorkSlugs(aidev), statusText(root, { ...deps, sig }), readCurrent(aidev), readBacklog(aidev)]);
  const rows = text === null ? new Map() : parseStatusTsv(text);
  const works = [];
  for (let i = 0; i < listing.slugs.length; i += 16) {
    works.push(...await Promise.all(listing.slugs.slice(i, i + 16).map((slug) => readWorkSummary(listing.dir, slug, rows.get(slug), current))));
  }
  return { available: true, works, total: works.length, truncated: listing.truncated, current, backlog, cli: text !== null };
}

/** 詳細: state の値・工程の並び・tasks のチェックリスト・文書の一覧・events（新しい順 30 件）。 */
export async function loadWorkDetail(root, slug, deps = {}) {
  if (typeof slug !== 'string' || !READ_SLUG.test(slug)) throw fail('作業名の書式が不正です');
  const aidev = await resolveAidev(root);
  if (!aidev) throw fail('.aidev が見つかりません');
  const { dir, slugs } = await listWorkSlugs(aidev);
  if (!dir || !slugs.includes(slug)) throw fail('作業が見つかりません');
  const [text, current] = await Promise.all([statusText(root, { ...deps, sig: deps.sig ?? await dataSignature(root) }), readCurrent(aidev)]);
  const row = text === null ? undefined : parseStatusTsv(text).get(slug);
  const summary = await readWorkSummary(dir, slug, row, current);
  const base = join(dir, slug);
  const [stateFile, tasksFile, metricsFile, docs] = await Promise.all([
    readOptional(join(base, 'state.yml'), 64 * 1024), readOptional(join(base, 'tasks.md')), readOptional(join(base, 'metrics.yml')), listDocs(base),
  ]);
  const values = stateFile ? parseState(stateFile.text) : {};
  const docNames = new Set(docs.map((d) => d.name));
  const phases = PHASES.map((phase) => {
    const approved = summary.approved.includes(phase);
    const isCurrent = summary.state === 'active' && summary.current === phase;
    const hasDoc = !!PHASE_DOCS[phase] && docNames.has(PHASE_DOCS[phase]);
    return { phase, status: approved ? 'approved' : isCurrent ? 'current' : 'pending', hasDoc, dim: OPTIONAL_PHASES.includes(phase) && !approved && !isCurrent && !hasDoc };
  });
  const events = parseEvents(metricsFile?.text).slice(-LIMITS.events).reverse();
  return { ...summary, values, phases, tasksList: parseTasks(tasksFile?.text).items, docs, events };
}

async function listDocs(base) {
  let entries;
  try { entries = await readdir(base, { withFileTypes: true }); } catch { return []; }
  const out = [];
  for (const e of entries) {
    if (!e.isFile() || !/^[^/\\\0]{1,120}\.md$/.test(e.name)) continue;
    try { const st = await lstat(join(base, e.name)); if (st.isFile()) out.push({ name: e.name, size: st.size }); } catch { /* 消えた */ }
  }
  return out.sort((a, b) => a.name.localeCompare(b.name)).slice(0, 64);
}

/** 文書の本文。名前は作業フォルダ直下の `*.md` の一覧にあるものだけ（パスの成分は拒否）。512 KiB で切る。 */
export async function loadDoc(root, slug, name) {
  if (typeof slug !== 'string' || !READ_SLUG.test(slug)) throw fail('作業名の書式が不正です');
  if (typeof name !== 'string' || !/^[^/\\\0]{1,120}\.md$/.test(name) || name === '.' || name.includes('..')) throw fail('文書名が不正です');
  const aidev = await resolveAidev(root);
  if (!aidev) throw fail('.aidev が見つかりません');
  const { dir, slugs } = await listWorkSlugs(aidev);
  if (!dir || !slugs.includes(slug)) throw fail('作業が見つかりません');
  const base = join(dir, slug);
  if (!(await listDocs(base)).some((d) => d.name === name)) throw fail('その文書は一覧にありません');
  const file = join(base, name);
  if (!within(base, await realpath(file))) throw fail('作業フォルダの外は読めません');
  const read = await readCapped(file, LIMITS.doc);
  return { slug, name, text: read.text, truncated: read.truncated, size: read.size };
}

/** 変化の検知用の署名。関係するファイルの mtime・大きさだけを見る（中身は読まない）。 */
export async function dataSignature(root) {
  const aidev = await resolveAidev(root);
  if (!aidev) return 'none';
  const stamp = async (file) => {
    try { const st = await lstat(file); return `${file}|${st.mtimeMs}|${st.size}`; } catch { return `${file}|-`; }
  };
  const { dir, slugs } = await listWorkSlugs(aidev);
  const files = [join(aidev, 'current'), join(aidev, 'backlog')];
  try {
    for (const e of await readdir(join(aidev, 'backlog'), { withFileTypes: true })) if (e.isFile()) files.push(join(aidev, 'backlog', e.name));
  } catch { /* backlog 無し */ }
  if (dir) {
    files.push(dir);
    for (const s of slugs) files.push(join(dir, s), join(dir, s, 'state.yml'), join(dir, s, 'tasks.md'), join(dir, s, 'metrics.yml'));
  }
  const stamps = [];
  for (let i = 0; i < files.length; i += 64) stamps.push(...await Promise.all(files.slice(i, i + 64).map(stamp)));
  return createHash('sha1').update(stamps.join('\n')).digest('hex');
}
