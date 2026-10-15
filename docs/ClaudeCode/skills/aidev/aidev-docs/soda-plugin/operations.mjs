// UI と `sodactl plugin call` が共通に呼ぶ操作。入力の意味の検証（型・長さ・書式・enum）はここで行う。
import { basename } from 'node:path';
import * as aidevData from './aidev-data.mjs';
import { AGENT_KINDS, LOG_LEVELS, PANE_ID_RE, WORKER_SLUG, WORKER_STATUSES, MODEL_RE } from './agents.mjs';

export const TEXT_MAX_BYTES = 16 * 1024;
const fail = (message) => Object.assign(new Error(message), { expected: true });

const SLUG_SCHEMA = { type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$', description: '作業の名前（aidev の work の slug。日付の付いたフォルダ名も可）' };
const FRESH_SCHEMA = { type: 'boolean', description: '再開できる会話があっても、新しい会話で始める（前の会話の ID は previousSessions に残す）' };
const TEXT_SCHEMA = { type: 'string', minLength: 1, maxLength: 16384 };
const KIND_SCHEMA = { enum: ['', ...AGENT_KINDS], description: '種類（空なら設定の既定）' };
const PANE_SCHEMA = { type: 'string', pattern: '^[0-9a-f][0-9a-f-]{3,63}$', description: 'pane の ID（UUID または先頭 4 文字以上）' };
const object = (properties = {}, required = []) => ({ type: 'object', properties, ...(required.length ? { required } : {}), additionalProperties: false });

export const OPERATIONS = [
  { name: 'works-list', description: '作業の一覧（slug・current・next・mode・profile・state・tasks の進み・担当の状態）。all を省くと進行中だけ', inputSchema: object({ all: { type: 'boolean' } }) },
  { name: 'work-get', description: '作業の詳細（state・工程・tasks・文書の一覧・events・担当）', inputSchema: object({ slug: { type: 'string', minLength: 1, maxLength: 128 } }, ['slug']) },
  { name: 'work-doc', description: '作業の文書の本文（作業フォルダ直下の *.md。512 KiB で切る）', inputSchema: object({ slug: { type: 'string', minLength: 1, maxLength: 128 }, name: { type: 'string', minLength: 1, maxLength: 120 } }, ['slug', 'name']) },
  { name: 'backlog-list', description: 'backlog のファイルごとの未着手の数と項目（先頭 50 件）', inputSchema: object() },
  { name: 'agents-list', description: '監督・担当のエージェント（セッション ID・状態・pane・設定）', inputSchema: object() },
  { name: 'supervisor-start', description: '監督エージェントを起動する（動いていれば何もしない）。種類（claude|codex）とモデルは省けば設定の既定', inputSchema: object({ kind: KIND_SCHEMA, model: { type: 'string', maxLength: 64 }, fresh: FRESH_SCHEMA }) },
  { name: 'supervisor-resume', description: '監督エージェントを、記録したセッション ID で同じ会話のまま再開する', inputSchema: object() },
  { name: 'supervisor-prompt', description: '監督エージェントへ指示を送る', inputSchema: object({ text: TEXT_SCHEMA }, ['text']) },
  { name: 'worker-start', description: '作業の担当エージェントを新しい端末タブで起動し、監督へ線（監督・承認の代理・完了のトリガ）を結ぶ', inputSchema: object({ slug: SLUG_SCHEMA, instruction: { type: 'string', maxLength: 16384 }, kind: KIND_SCHEMA, model: { type: 'string', maxLength: 64 }, fresh: FRESH_SCHEMA }, ['slug']) },
  { name: 'worker-resume', description: '止まっている担当エージェントを、記録したセッション ID で再開する', inputSchema: object({ slug: SLUG_SCHEMA }, ['slug']) },
  { name: 'worker-prompt', description: '担当エージェントへ指示を送る', inputSchema: object({ slug: SLUG_SCHEMA, text: TEXT_SCHEMA }, ['slug', 'text']) },
  { name: 'worker-report', description: '担当から監督・利用者への報告（progress|done|question|blocked|failed）。担当が呼ぶ', inputSchema: object({ slug: SLUG_SCHEMA, status: { enum: WORKER_STATUSES }, message: TEXT_SCHEMA }, ['slug', 'status', 'message']) },
  { name: 'report', description: '監督から利用者への知らせ。アプリのログに出す（level: info|warn|question）', inputSchema: object({ message: TEXT_SCHEMA, level: { enum: LOG_LEVELS } }, ['message']) },
  { name: 'work-agents', description: '作業の担当と、担当が起こした関連するエージェント（グラフの線で連なるもの＋登録分）', inputSchema: object({ slug: SLUG_SCHEMA }, ['slug']) },
  { name: 'work-agent-register', description: '担当が、自分で起こした別のエージェントの pane を、作業の関連として登録する（線が自動で引かれないときの保険）', inputSchema: object({ slug: SLUG_SCHEMA, paneId: PANE_SCHEMA }, ['slug', 'paneId']) },
  { name: 'work-agent-prompt', description: '作業の担当または関連するエージェントへ指示を送る', inputSchema: object({ slug: SLUG_SCHEMA, paneId: PANE_SCHEMA, text: TEXT_SCHEMA }, ['slug', 'paneId', 'text']) },
  { name: 'work-agent-read', description: '作業の担当または関連するエージェントの画面の末尾を読む', inputSchema: object({ slug: SLUG_SCHEMA, paneId: PANE_SCHEMA, lines: { type: 'integer', minimum: 1, maximum: 200 } }, ['slug', 'paneId']) },
  { name: 'log-list', description: 'アプリのログ（新しい順）', inputSchema: object({ limit: { type: 'integer', minimum: 1, maximum: 300 } }) },
  { name: 'refresh', description: '.aidev と台帳を読み直して画面を更新する', inputSchema: object() },
];

// ---- 入力の検証 -----------------------------------------------------------------------------------

function only(params, allowed) {
  if (params === undefined || params === null) return {};
  if (typeof params !== 'object' || Array.isArray(params)) throw fail('パラメータは JSON オブジェクトで指定してください');
  for (const key of Object.keys(params)) if (!allowed.includes(key)) throw fail(`知らないパラメータです: ${String(key).slice(0, 40)}`);
  return params;
}
function text(value, label, { required = true } = {}) {
  if (value === undefined && !required) return '';
  if (typeof value !== 'string') throw fail(`${label}は文字列で指定してください`);
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)) throw fail(`${label}に制御文字は使えません`);
  if (Buffer.byteLength(value) > TEXT_MAX_BYTES) throw fail(`${label}は 16 KiB までです`);
  const trimmed = value.trim();
  if (required && !trimmed) throw fail(`${label}が空です`);
  return trimmed;
}
function workerSlug(value) {
  if (typeof value !== 'string' || !WORKER_SLUG.test(value)) throw fail('slug は英数字と . _ - の 1〜128 文字です（先頭は英数字）');
  return value;
}
function readSlug(value) {
  if (typeof value !== 'string' || !aidevData.READ_SLUG.test(value)) throw fail('作業名の書式が不正です');
  return value;
}
function bool(value, label) {
  if (value === undefined) return false;
  if (typeof value !== 'boolean') throw fail(`${label} は true か false です`);
  return value;
}
function kind(value) {
  if (value === undefined || value === '') return '';
  if (!AGENT_KINDS.includes(value)) throw fail(`種類は ${AGENT_KINDS.join(' か ')} です`);
  return value;
}
function paneId(value) {
  if (typeof value !== 'string' || !PANE_ID_RE.test(value)) throw fail('pane の ID の書式が不正です');
  return value;
}
function model(value) {
  if (value === undefined || value === '') return '';
  if (typeof value !== 'string' || !MODEL_RE.test(value)) throw fail('モデル名は英数字と . _ - [ ] の 1〜64 文字です');
  return value;
}

const VALIDATORS = {
  'works-list': (p) => { const o = only(p, ['all']); if (o.all !== undefined && typeof o.all !== 'boolean') throw fail('all は true か false です'); return { all: o.all === true }; },
  'work-get': (p) => ({ slug: readSlug(only(p, ['slug']).slug) }),
  'work-doc': (p) => { const o = only(p, ['slug', 'name']); return { slug: readSlug(o.slug), name: docName(o.name) }; },
  'backlog-list': (p) => { only(p, []); return {}; },
  'agents-list': (p) => { only(p, []); return {}; },
  'supervisor-start': (p) => { const o = only(p, ['kind', 'model', 'fresh']); return { kind: kind(o.kind), model: model(o.model), fresh: bool(o.fresh, 'fresh') }; },
  'supervisor-resume': (p) => { only(p, []); return {}; },
  'supervisor-prompt': (p) => ({ text: text(only(p, ['text']).text, '指示') }),
  'worker-start': (p) => { const o = only(p, ['slug', 'instruction', 'kind', 'model', 'fresh']); return { slug: workerSlug(o.slug), instruction: text(o.instruction, '指示', { required: false }), kind: kind(o.kind), model: model(o.model), fresh: bool(o.fresh, 'fresh') }; },
  'work-agents': (p) => ({ slug: workerSlug(only(p, ['slug']).slug) }),
  'work-agent-register': (p) => { const o = only(p, ['slug', 'paneId']); return { slug: workerSlug(o.slug), paneId: paneId(o.paneId) }; },
  'work-agent-prompt': (p) => { const o = only(p, ['slug', 'paneId', 'text']); return { slug: workerSlug(o.slug), paneId: paneId(o.paneId), text: text(o.text, '指示') }; },
  'work-agent-read': (p) => {
    const o = only(p, ['slug', 'paneId', 'lines']);
    if (o.lines !== undefined && (!Number.isInteger(o.lines) || o.lines < 1 || o.lines > 200)) throw fail('lines は 1〜200 の整数です');
    return { slug: workerSlug(o.slug), paneId: paneId(o.paneId), lines: o.lines ?? 60 };
  },
  'worker-resume': (p) => ({ slug: workerSlug(only(p, ['slug']).slug) }),
  'worker-prompt': (p) => { const o = only(p, ['slug', 'text']); return { slug: workerSlug(o.slug), text: text(o.text, '指示') }; },
  'worker-report': (p) => {
    const o = only(p, ['slug', 'status', 'message']);
    if (!WORKER_STATUSES.includes(o.status)) throw fail(`status は ${WORKER_STATUSES.join('・')} のどれかです`);
    return { slug: workerSlug(o.slug), status: o.status, message: text(o.message, '報告') };
  },
  report: (p) => {
    const o = only(p, ['message', 'level']);
    if (o.level !== undefined && !LOG_LEVELS.includes(o.level)) throw fail(`level は ${LOG_LEVELS.join('・')} のどれかです`);
    return { message: text(o.message, '知らせ'), level: o.level ?? 'info' };
  },
  'log-list': (p) => {
    const o = only(p, ['limit']);
    if (o.limit !== undefined && (!Number.isInteger(o.limit) || o.limit < 1 || o.limit > 300)) throw fail('limit は 1〜300 の整数です');
    return { limit: o.limit ?? 50 };
  },
  refresh: (p) => { only(p, []); return {}; },
};
function docName(value) {
  if (typeof value !== 'string' || !/^[^/\\\0]{1,120}\.md$/.test(value) || value.includes('..')) throw fail('文書名が不正です（作業フォルダ直下の *.md だけ）');
  return value;
}
/**
 * 画面（`soda.action`）の値は文字列だけなので、真偽の項目（`fresh`）を `'true'`/`'false'` から boolean に直す。
 * 直せない値はそのまま渡す（検証が断る）。CLI（JSON）の経路では使わない。
 */
export function fromUi(data) {
  const out = { ...data };
  for (const key of ['fresh']) {
    if (out[key] === 'true') out[key] = true;
    else if (out[key] === 'false' || out[key] === '') out[key] = false;
  }
  return out;
}
export function validateParams(name, params) {
  const validate = VALIDATORS[name];
  if (!validate) throw fail('未対応の操作です');
  return validate(params);
}

// ---- 画面用のまとまり ------------------------------------------------------------------------------

/** 画面・端末版・帯が共通に読む 1 つのまとまり（`.aidev` の読み取り＋台帳）。 */
export async function buildModel(root, panes, { data = aidevData, agents, overview: loaded, overviewDeps }) {
  const [overview, agentState, relatedBySlug] = await Promise.all([
    loaded ?? data.loadOverview(root, overviewDeps), agents.overview(root, panes), agents.related ? agents.related(root, panes) : {},
  ]);
  const workerBySlug = new Map(agentState.workers.map((w) => [w.slug, w]));
  const works = overview.works.map((w) => ({ ...w, worker: workerBySlug.get(w.slug) ?? null }));
  return {
    project: basename(root) || root, root,
    available: overview.available, cli: overview.cli, truncated: overview.truncated, total: overview.total, current: overview.current,
    works, backlog: overview.backlog,
    supervisor: agentState.supervisor, workers: agentState.workers, settings: agentState.settings, log: agentState.log,
    related: Object.values(relatedBySlug).flat(),
  };
}
/** 帯・端末版の 1〜数行の要約に使う数。 */
export function summarize(model) {
  const active = model.works.filter((w) => w.state === 'active');
  const cur = model.works.find((w) => w.isCurrent) ?? null;
  const workers = model.workers.filter((w) => w.alive);
  return {
    supervisor: model.supervisor?.status ?? 'none',
    active: active.length,
    current: cur ? { slug: cur.slug, phase: cur.current } : null,
    working: workers.filter((w) => w.status === 'working').length,
    blocked: workers.filter((w) => w.status === 'blocked').length,
    questions: model.log.filter((e) => e.level === 'question').length,
  };
}

// ---- 操作の本体 -----------------------------------------------------------------------------------

/**
 * `ctx` は呼び出し側（拡張）が `ext.panes` と照合して作る: `{ root, tabId, workspaceId, paneId, panes }`。
 * `source` は 'ui'（画面の操作）か 'cli'（`sodactl plugin call`）。
 */
// ---- 結果の大きさ -----------------------------------------------------------------------------------
// `app.result` は 256 KiB を超えると、サーバが受理せず、呼び出しが 30 秒の時間切れになる。余裕を見て 200 KiB で切る。
export const RESULT_MAX_BYTES = 200 * 1024;
const jsonBytes = (v) => Buffer.byteLength(JSON.stringify(v));
function cutBytes(text, max) {
  const buf = Buffer.from(String(text));
  return buf.length <= max ? String(text) : buf.subarray(0, max).toString('utf8').replace(/\uFFFD+$/, '');
}
/** 配列を、収まるまで減らす（先頭から残す）。減らしたら `truncated: true`。 */
function fitArray(result, key) {
  let arr = result[key];
  while (jsonBytes({ ...result, [key]: arr }) > RESULT_MAX_BYTES && arr.length > 1) arr = arr.slice(0, Math.max(1, Math.floor(arr.length * 0.7)));
  return { ...result, [key]: arr, truncated: true, ...(key === 'works' ? { shown: arr.length } : {}) };
}
export function fitResult(name, result, max = RESULT_MAX_BYTES) {
  if (jsonBytes(result) <= max) return result;
  let out = result;
  if (name === 'work-doc' && typeof out.text === 'string') {
    const room = Math.max(1024, max - jsonBytes({ ...out, text: '' }) - 1024);
    out = { ...out, text: cutBytes(out.text, room), truncated: true };
  } else if (name === 'log-list') out = fitArray(out, 'log');
  else if (name === 'works-list') out = fitArray(out, 'works');
  else if (name === 'backlog-list') out = fitArray(out, 'backlog');
  if (jsonBytes(out) > max) throw fail(`結果が大きすぎます（${Math.round(jsonBytes(result) / 1024)} KiB）。範囲を絞ってください`);
  return out;
}

// CLI から呼ばれたときは、`next` を空にしないために、まだ一度も読めていなければ aidev CLI の結果を待つ（以後は前回の値）
const CLI_DEPS = { wait: 'if-empty' };
export function createOperations({ data = aidevData, agents }) {
  const handlers = {
    async 'works-list'(ctx, { all }) {
      const model = await buildModel(ctx.root, ctx.panes, { data, agents, overviewDeps: CLI_DEPS });
      const works = all ? model.works : model.works.filter((w) => w.state === 'active');
      return { available: model.available, total: model.total, shown: works.length, truncated: model.truncated, current: model.current, cli: model.cli, works };
    },
    async 'work-get'(ctx, { slug }) {
      const [detail, state] = await Promise.all([data.loadWorkDetail(ctx.root, slug, CLI_DEPS), agents.overview(ctx.root, ctx.panes)]);
      return { ...detail, worker: state.workers.find((w) => w.slug === slug) ?? null };
    },
    'work-doc': (ctx, { slug, name }) => data.loadDoc(ctx.root, slug, name),
    async 'backlog-list'(ctx) {
      const model = await buildModel(ctx.root, ctx.panes, { data, agents });
      return { backlog: model.backlog, todo: model.backlog.reduce((n, b) => n + b.todo, 0) };
    },
    async 'agents-list'(ctx) {
      const { supervisor, workers, settings } = await agents.overview(ctx.root, ctx.panes);
      return { supervisor, workers, settings };
    },
    'supervisor-start': (ctx, p) => agents.startSupervisor(ctx.root, ctx, p),
    'supervisor-resume': (ctx) => agents.resumeSupervisor(ctx.root, ctx),
    'supervisor-prompt': (ctx, p, source) => agents.promptSupervisor(ctx.root, ctx, { ...p, source }),
    'worker-start': (ctx, p) => agents.startWorker(ctx.root, ctx, p),
    async 'work-agents'(ctx, { slug }) {
      const [state, rel] = await Promise.all([agents.overview(ctx.root, ctx.panes), agents.related(ctx.root, ctx.panes, { force: true })]);
      return { slug, worker: state.workers.find((w) => w.slug === slug) ?? null, agents: rel[slug] ?? [] };
    },
    'work-agent-register': (ctx, p) => agents.registerRelated(ctx.root, ctx, p),
    'work-agent-prompt': (ctx, p, source) => agents.promptRelated(ctx.root, ctx, { ...p, source }),
    'work-agent-read': (ctx, p) => agents.readRelated(ctx.root, ctx, p),
    'worker-resume': (ctx, p) => agents.resumeWorker(ctx.root, ctx, p),
    'worker-prompt': (ctx, p, source) => agents.promptWorker(ctx.root, ctx, { ...p, source }),
    'worker-report': (ctx, p) => agents.reportWorker(ctx.root, ctx, p),
    report: (ctx, p) => agents.report(ctx.root, p),
    'log-list': (ctx, { limit }) => agents.logList(ctx.root, limit),
    refresh: async () => ({ updated: true }),
  };
  /** 検証してから実行する。未知の操作・不正な入力は期待された誤り（expected）で返る。 */
  async function call(name, params, ctx, source = 'cli') {
    const clean = validateParams(name, params);
    return fitResult(name, await handlers[name](ctx, clean, source));
  }
  return { call, delegate: (ctx, slug) => agents.delegate(ctx.root, ctx, workerSlug(slug)) };
}
