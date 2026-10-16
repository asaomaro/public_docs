// 台帳（セッション ID の記憶）と、sodactl を使った監督・担当エージェントの起動・再開・指示・グラフの線。
// 台帳は `<PJ>/.soda/aidev/`（リポジトリに入らない）。`.aidev/` には書かない。
import { createHash, randomUUID } from 'node:crypto';
import { execFile } from 'node:child_process';
import { lstat, mkdir, readFile, realpath, rename, rm, writeFile } from 'node:fs/promises';
import { join, sep } from 'node:path';
import { promisify } from 'node:util';
import { delegateInstruction, readFileInstruction, supervisorPrompt, supervisorResumeNote, triggerPrompt, workerPrompt, workerResumeNote } from './prompts.mjs';

const execute = promisify(execFile);

/** 作業の名前（`.aidev/works/<slug>`）。読み取り側（aidev-data の READ_SLUG）と同じ書式。エージェント名は slug から安全な形に作る。 */
export const WORKER_SLUG = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
export const MODEL_RE = /^[A-Za-z0-9._\-[\]]{1,64}$/;
export const PERMISSION_MODES = ['', 'default', 'acceptEdits', 'auto', 'plan'];
export const AGENT_KINDS = ['claude', 'codex', 'copilot', 'bob'];
/** `agent integrations` に答えられない古いサーバでも選べる種類（後方互換）。 */
export const LEGACY_KINDS = ['claude', 'codex'];
export const KIND_LABELS = { claude: 'Claude Code', codex: 'Codex', copilot: 'Copilot CLI', bob: 'Bob Shell' };
/** Codex の権限の組（`--sandbox` と `--ask-for-approval`）。固定の選択肢だけ。 */
export const CODEX_PERMISSIONS = {
  '': [],
  'read-only': ['-s', 'read-only', '-a', 'on-request'],
  'workspace-write': ['-s', 'workspace-write', '-a', 'on-request'],
  'workspace-write-never': ['-s', 'workspace-write', '-a', 'never'],
};
export const WORKER_STATUSES = ['progress', 'done', 'question', 'blocked', 'failed'];
export const LOG_LEVELS = ['info', 'warn', 'question'];
export const LEDGER_LIMITS = { log: 300, message: 8 * 1024 };
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** Bob Shell の会話 ID は UUID ではなく 32 桁の 16 進数。 */
const BOB_ID_RE = /^[0-9a-f]{32}$/i;
/** 会話 ID の書式は種類ごと（安全な文字だけ・長さ固定）。知らない種類は通さない。 */
export const sessionIdOk = (kind, id) => typeof id === 'string' && (kind === 'bob' ? BOB_ID_RE : AGENT_KINDS.includes(kind) ? UUID_RE : /^$/).test(id);
const INTEGRATIONS_TTL_MS = 5_000;
const AGENT_STATUSES = ['running', 'blocked', 'stopped', 'failed'];
const STARTING_GRACE_MS = 20_000;
const RELAYED = ['question', 'failed', 'blocked'];
export const PANE_ID_RE = /^[0-9a-f][0-9a-f-]{3,63}$/i;
const RELATED_DEPTH = 3;
const MAX_TAB_PANES = 6;
const PENDING_KINDS = ['role', 'note', 'links'];
// --resume が会話を見つけられず落ちたときの code。`timeout` は「まだ確かめられない」で、会話が無いとは限らない（名前が付いていれば動いている）
const RESUME_LOST = ['agent_start_failed'];
const ORPHAN_CODES = ['timeout', 'agent_kind_mismatch', 'agent_start_failed', 'agent_not_ready'];
const TRIGGER_CHECK_GAP_MS = 20_000; // 完了後の終了で、トリガの線の履歴を問い合わせる間隔
const FINISH_GAP_MS = 20_000;
const FINISH_MAX_TRIES = 3;
const EXIT_GRACE_MS = 20_000;
const EXIT_GIVE_UP_MS = 30 * 60_000; // トリガの線が先（監督）を待つ上限（busy_timeout 30 分）に合わせる
export const PREVIOUS_SESSIONS_MAX = 5;
const RELATED_TTL_MS = 5000;

const fail = (message) => Object.assign(new Error(message), { expected: true });
const clip = (s, n) => { const t = String(s ?? ''); return t.length > n ? t.slice(0, n) : t; };
const str = (v, n) => (typeof v === 'string' ? clip(v, n) : '');
const iso = (d) => d.toISOString();

// ---- 台帳 ---------------------------------------------------------------------------------------

/** `<PJ>/.soda/aidev/`。`.soda`・`aidev` がシンボリックリンクなら使わない。初回に `.gitignore`（`*`）を作る。 */
export async function ensureStateDir(root, create = true) {
  const realRoot = await realpath(root);
  const soda = join(realRoot, '.soda');
  const dir = join(soda, 'aidev');
  for (const p of [soda, dir]) {
    let st = null;
    try { st = await lstat(p); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    if (st && (st.isSymbolicLink() || !st.isDirectory())) throw fail(`${p} がフォルダではない（またはシンボリックリンク）ため使えません`);
  }
  if (create) await mkdir(dir, { recursive: true, mode: 0o700 });
  let real;
  try { real = await realpath(dir); } catch (e) { if (!create && e.code === 'ENOENT') return null; throw e; }
  if (!real.startsWith(realRoot + sep)) throw fail('台帳の置き場所が PJ の外を指しています');
  if (create) {
    try { await writeFile(join(real, '.gitignore'), '*\n', { flag: 'wx', mode: 0o644 }); } catch (e) { if (e.code !== 'EEXIST') throw e; }
  }
  return real;
}

async function atomicWrite(file, text) {
  const tmp = `${file}.${process.pid}.${randomUUID().slice(0, 8)}.tmp`;
  try {
    await writeFile(tmp, text, { flag: 'wx', mode: 0o600 });
    await rename(tmp, file);
  } catch (e) { await rm(tmp, { force: true }).catch(() => {}); throw e; }
}

export const emptyLedger = () => ({ version: 1, supervisor: null, workers: {}, log: [] });

export function cleanAgent(a, slug) {
  if (!a || typeof a !== 'object') return null;
  const out = {
    ...(slug ? { slug } : {}),
    name: str(a.name, 32), kind: AGENT_KINDS.includes(a.kind) ? a.kind : 'claude',
    sessionId: sessionIdOk(AGENT_KINDS.includes(a.kind) ? a.kind : 'claude', a.sessionId ?? '') ? a.sessionId : '',
    paneId: str(a.paneId, 64), tabId: str(a.tabId, 64), workspaceId: str(a.workspaceId, 64),
    model: MODEL_RE.test(a.model ?? '') ? a.model : '',
    startedAt: str(a.startedAt, 40), resumedAt: a.resumedAt ? str(a.resumedAt, 40) : null,
    status: AGENT_STATUSES.includes(a.status) ? a.status : 'stopped',
    error: a.error ? str(a.error, 1000) : null,
    // 役割・再開の知らせ・線のうち、まだ届いていないもの（承認待ちなどで起動の途中に止まったとき）
    pending: Array.isArray(a.pending) ? PENDING_KINDS.filter((k) => a.pending.includes(k)) : [],
    previousSessions: Array.isArray(a.previousSessions)
      ? a.previousSessions.filter((x) => x && sessionIdOk(AGENT_KINDS.includes(x.kind) ? x.kind : 'claude', x.sessionId ?? '')).slice(0, PREVIOUS_SESSIONS_MAX).map((x) => ({ sessionId: x.sessionId, kind: AGENT_KINDS.includes(x.kind) ? x.kind : 'claude', endedAt: str(x.endedAt, 40) }))
      : [],
  };
  if (slug) {
    const r = a.lastReport;
    out.lastReport = r && typeof r === 'object' ? { status: WORKER_STATUSES.includes(r.status) ? r.status : 'progress', message: str(r.message, LEDGER_LIMITS.message), at: str(r.at, 40) } : null;
    out.linkErrors = Array.isArray(a.linkErrors) ? a.linkErrors.slice(0, 5).map((x) => str(x, 300)) : [];
    out.instruction = str(a.instruction, 16 * 1024);
    out.doneAt = str(a.doneAt, 40);
    out.noAutoClose = a.noAutoClose === true; // 完了の知らせが届かなかった担当は、自動では閉じない
    out.related = Array.isArray(a.related) ? [...new Set(a.related.filter((x) => typeof x === 'string' && PANE_ID_RE.test(x)))].slice(0, 16) : [];
  }
  return out;
}
/** 読んだ JSON を台帳の形に直す（知らない項目は捨てる）。 */
export function cleanLedger(raw) {
  const out = emptyLedger();
  if (!raw || typeof raw !== 'object') return out;
  out.supervisor = cleanAgent(raw.supervisor, null);
  if (raw.workers && typeof raw.workers === 'object') {
    for (const [slug, w] of Object.entries(raw.workers)) {
      if (WORKER_SLUG.test(slug)) { const c = cleanAgent(w, slug); if (c) out.workers[slug] = c; }
    }
  }
  if (Array.isArray(raw.log)) {
    out.log = raw.log.slice(-LEDGER_LIMITS.log).filter((e) => e && typeof e === 'object').map((e) => ({
      at: str(e.at, 40), from: ['user', 'supervisor', 'worker', 'app'].includes(e.from) ? e.from : 'app',
      slug: typeof e.slug === 'string' && WORKER_SLUG.test(e.slug) ? e.slug : null,
      kind: ['instruction', 'report', 'event', 'error'].includes(e.kind) ? e.kind : 'event',
      ...(LOG_LEVELS.includes(e.level) ? { level: e.level } : {}),
      message: str(e.message, LEDGER_LIMITS.message),
    }));
  }
  return out;
}

/** 台帳・設定の読み込み。シンボリックリンクなら読まない（PJ の外を指させない）。無ければ null。 */
async function readStateFile(file) {
  let st;
  try { st = await lstat(file); } catch (e) { if (e.code === 'ENOENT') return null; throw e; }
  if (st.isSymbolicLink() || !st.isFile()) throw fail(`${file} は通常のファイルではない（またはシンボリックリンク）ため使えません`);
  return readFile(file, 'utf8');
}

export async function readLedger(root) {
  const dir = await ensureStateDir(root, false);
  if (!dir) return emptyLedger();
  const file = join(dir, 'agents.json');
  const text = await readStateFile(file);
  if (text === null) return emptyLedger();
  try { return cleanLedger(JSON.parse(text)); } catch {
    await rename(file, `${file}.corrupt`).catch(() => {});
    return emptyLedger();
  }
}

const chains = new Map();
/** 同じ PJ の台帳の読み→変更→書きを直列にする（取りこぼしを防ぐ）。 */
export function updateLedger(root, mutate) {
  const run = (chains.get(root) ?? Promise.resolve()).catch(() => {}).then(async () => {
    const ledger = await readLedger(root);
    const result = await mutate(ledger);
    ledger.log = ledger.log.slice(-LEDGER_LIMITS.log);
    const target = join(await ensureStateDir(root), 'agents.json');
    await readStateFile(target); // シンボリックリンクなら断る
    await atomicWrite(target, JSON.stringify(ledger, null, 2) + '\n');
    return result;
  });
  chains.set(root, run.catch(() => {}));
  return run;
}
export function pushLog(ledger, now, entry) {
  ledger.log.push({ at: iso(now), slug: null, ...entry, message: clip(entry.message, LEDGER_LIMITS.message) });
  if (ledger.log.length > LEDGER_LIMITS.log) ledger.log.splice(0, ledger.log.length - LEDGER_LIMITS.log);
}

// ---- 設定 ---------------------------------------------------------------------------------------

export const notInstalledMessage = (kind) => `${KIND_LABELS[kind] ?? kind} は導入されていません。Sodashitsu の設定「エージェント連携」で ${KIND_LABELS[kind] ?? kind} を導入してください`;

export const DEFAULT_SETTINGS = Object.freeze({ supervisorModel: '', workerModel: '', permissionMode: '', autoStartSupervisor: true, supervisorKind: 'claude', workerKind: 'claude', codexPermission: '', exitOnDone: true });
export function normalizeSettings(input, base = DEFAULT_SETTINGS) {
  const s = { ...base };
  const src = input && typeof input === 'object' ? input : {};
  for (const key of Object.keys(src)) {
    if (!(key in DEFAULT_SETTINGS)) throw fail(`知らない設定です: ${clip(key, 40)}`);
  }
  for (const key of ['supervisorModel', 'workerModel']) {
    if (key in src) {
      if (typeof src[key] !== 'string' || (src[key] !== '' && !MODEL_RE.test(src[key]))) throw fail('モデル名は英数字と . _ - [ ] の 1〜64 文字です（空なら指定しません）');
      s[key] = src[key];
    }
  }
  if ('permissionMode' in src) {
    if (!PERMISSION_MODES.includes(src.permissionMode)) throw fail('権限のモードは default・acceptEdits・auto・plan のどれかです');
    s.permissionMode = src.permissionMode;
  }
  for (const key of ['supervisorKind', 'workerKind']) {
    if (key in src) {
      if (!AGENT_KINDS.includes(src[key])) throw fail(`エージェントの種類は ${AGENT_KINDS.join('・')} のどれかです`);
      s[key] = src[key];
    }
  }
  if ('codexPermission' in src) {
    if (typeof src.codexPermission !== 'string' || !Object.hasOwn(CODEX_PERMISSIONS, src.codexPermission)) throw fail('Codex の権限は read-only・workspace-write・workspace-write-never のどれかです');
    s.codexPermission = src.codexPermission;
  }
  if ('exitOnDone' in src) {
    if (typeof src.exitOnDone !== 'boolean') throw fail('完了時の終了は true か false です');
    s.exitOnDone = src.exitOnDone;
  }
  if ('autoStartSupervisor' in src) {
    if (typeof src.autoStartSupervisor !== 'boolean') throw fail('自動起動は true か false です');
    s.autoStartSupervisor = src.autoStartSupervisor;
  }
  return s;
}
export async function loadSettings(root) {
  try {
    const dir = await ensureStateDir(root, false);
    if (!dir) return { ...DEFAULT_SETTINGS };
    const text = await readStateFile(join(dir, 'settings.json'));
    return text === null ? { ...DEFAULT_SETTINGS } : normalizeSettings(JSON.parse(text));
  } catch { return { ...DEFAULT_SETTINGS }; }
}
/**
 * 設定に保存できる種類は、導入済みのものだけ（`availableKinds`）。保存済みの値と同じなら通す
 * （後で未導入になった種類を、画面の保存でほかの項目と一緒に送り直しても断らない。断るのは新しく起動するとき）。
 */
export async function saveSettings(root, input, { kinds } = {}) {
  const current = await loadSettings(root);
  const next = normalizeSettings(input, current);
  if (kinds) {
    const { available } = await kinds(root);
    for (const key of ['supervisorKind', 'workerKind']) {
      if (key in (input ?? {}) && next[key] !== current[key] && !available.includes(next[key])) throw fail(notInstalledMessage(next[key]));
    }
  }
  const target = join(await ensureStateDir(root), 'settings.json');
  await readStateFile(target); // シンボリックリンクなら断る
  await atomicWrite(target, JSON.stringify(next, null, 2) + '\n');
  return next;
}

// ---- sodactl ------------------------------------------------------------------------------------

export class SodaError extends Error {
  constructor(code, message) { super(message); this.name = 'SodaError'; this.code = code; this.expected = true; }
}
const LOGIN_HINT = '（sodactl のログインが要ります。Sodashitsu のサーバと同じ OS 利用者で `sodactl login` を実行してください）';

/**
 * 拡張のプロセスから sodactl を呼ぶ。`SODA_PANE_ID`・`SODA_PANE_SOCKET` は外す（起動元の pane を親にしない）。
 * `--url` は `--` の手前に足す。cwd は PJ。失敗は SodaError。成功は JSON（JSON でなければ `{raw}`）。
 */
export function sodaClient(root, { run = execute, url = process.env.SODA_SERVER_URL, env = process.env } = {}) {
  if (!url) throw new SodaError('no_server', 'sodactl の接続先サーバ（SODA_SERVER_URL）がありません');
  const childEnv = { ...env, SODACTL_URL: url };
  for (const key of Object.keys(childEnv)) if (['SODA_PANE_ID', 'SODA_PANE_SOCKET'].includes(key.toUpperCase())) delete childEnv[key];
  return async (args, { timeout = 45000, rawMax = 2000 } = {}) => {
    const divider = args.indexOf('--');
    const argv = divider < 0 ? [...args, '--url', url] : [...args.slice(0, divider), '--url', url, ...args.slice(divider)];
    let stdout;
    try {
      ({ stdout } = await run('sodactl', argv, { cwd: root, env: childEnv, timeout, maxBuffer: 4 * 1024 * 1024, windowsHide: true }));
    } catch (e) {
      let code = e.code === 'ENOENT' ? 'sodactl_missing' : e.killed || e.code === 'ETIMEDOUT' ? 'timeout' : 'sodactl_failed';
      let message = e.code === 'ENOENT' ? 'sodactl が見つかりません（PATH を確かめてください）' : e.killed ? 'sodactl が時間内に終わりませんでした（操作が実行されたかは、状態を読んで確かめてください）' : 'sodactl が失敗しました';
      try {
        const err = JSON.parse(String(e.stderr ?? '')).error;
        if (err?.code) { code = String(err.code).slice(0, 60); message = clip(err.message || message, 400); }
      } catch { const raw = String(e.stderr ?? '').trim(); if (raw) message = clip(`${message}: ${raw}`, 400); }
      if (/login|auth|unauthor|forbidden|session/i.test(`${code} ${message}`)) message += LOGIN_HINT;
      throw new SodaError(code, message);
    }
    try { return JSON.parse(stdout); } catch { return { raw: clip(String(stdout), rawMax) }; }
  };
}

// ---- 状態の読み替え ------------------------------------------------------------------------------

/** 台帳の記録と `ext.panes` を照らして、エージェントが生きているかと表示用の状態を決める。 */
export function agentView(entry, panes, now = new Date()) {
  if (!entry) return null;
  const pane = panes.find((p) => p.id === entry.paneId);
  const alive = !!pane && pane.agent === entry.kind;
  const agentState = alive ? (pane.agentState ?? 'unknown') : null;
  let status;
  if (alive) status = agentState === 'working' ? 'working' : agentState === 'blocked' ? 'blocked' : 'idle';
  else if (entry.status === 'failed') status = 'failed';
  else if (entry.status === 'running' && now - Date.parse(entry.resumedAt || entry.startedAt) < STARTING_GRACE_MS) status = 'starting';
  else status = 'stopped';
  return {
    ...(entry.slug ? { slug: entry.slug } : {}),
    name: entry.name, kind: entry.kind, sessionId: entry.sessionId, paneId: entry.paneId, tabId: entry.tabId, workspaceId: entry.workspaceId,
    model: entry.model, status, recordedStatus: entry.status, agentState, alive, resumable: !alive && !!entry.sessionId && entry.status !== 'failed' && !entry.pending?.includes('role'), sessionPending: !entry.sessionId && entry.kind !== 'claude',
    pending: entry.pending ?? [], previousSessions: (entry.previousSessions ?? []).length, doneAt: entry.doneAt || null,
    startedAt: entry.startedAt, resumedAt: entry.resumedAt, error: entry.error,
    ...(entry.slug ? { lastReport: entry.lastReport ?? null, linkErrors: entry.linkErrors ?? [] } : {}),
  };
}
const shortHash = (s, n) => createHash('sha256').update(s).digest('hex').slice(0, n);
/** `agent rename` の書式 `[a-z][a-z0-9_-]{0,31}`。PJ の根の短いハッシュで他の PJ と衝突させない。 */
export const supervisorName = (root) => `aidev-sup-${shortHash(root, 6)}`;
export function workerName(root, slug) {
  const part = slug.toLowerCase().replace(/^\d{8}-/, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+/, '').slice(0, 14).replace(/-$/, '') || 'work';
  return `aidev-w-${shortHash(root, 4)}-${part}-${shortHash(slug, 4)}`;
}
const stamp = (d) => iso(d).replace(/[-:.]/g, '');
const guardDash = (text) => (/^\s*-/.test(text) ? `指示: ${text}` : text);

// ---- エージェントの起動・再開・指示 ----------------------------------------------------------------

export function createAgents({ makeSoda = (root) => sodaClient(root), now = () => new Date(), uuid = randomUUID } = {}) {
  const launching = new Set();
  const withLaunchLock = async (root, fn) => {
    if (launching.has(root)) throw fail('別の起動・再開の操作が実行中です。終わってからやり直してください');
    launching.add(root);
    try { return await fn(); } finally { launching.delete(root); }
  };
  const logEvent = (root, entry) => updateLedger(root, (l) => pushLog(l, now(), entry)).catch(() => {});

  /**
   * エージェントの置き場所。(1) 前の pane がまだ有り、エージェントが居なければ再利用 (2) アプリのタブの空き pane
   * (3) アプリのタブの最新の作業 pane を、右・下を交互に分ける (4) 作業 pane が 6 個に達していれば、そのときだけ新しいタブ
   * （新しいタブはアクティブになり、利用者の画面がそちらへ移る）。
   */
  async function placePane(soda, ctx, { preferPaneId, label, extraTabIds = [] }) {
    if (preferPaneId) {
      const p = ctx.panes.find((x) => x.id === preferPaneId);
      if (p && !p.virtual && !p.agent) return { paneId: p.id, tabId: p.tabId ?? ctx.tabId };
    }
    const snap = await soda(['snapshot']);
    const panes = (snap.panes ?? []).filter((p) => p.tabId === ctx.tabId && !p.virtual);
    const free = panes.find((p) => !p.agent && !p.busy && (p.status === undefined || p.status === 'running'));
    if (free) return { paneId: free.id, tabId: ctx.tabId };
    if (!panes.length) throw fail('アプリのタブに作業ターミナルがありません');
    if (panes.length >= MAX_TAB_PANES) {
      // 前にあふれて作った担当用のタブがあれば、その空き pane を使い、無ければそのタブを分ける（タブ作成は最初の 1 回だけ）
      const isFree = (p) => !p.agent && !p.busy && (p.status === undefined || p.status === 'running');
      for (const tabId of extraTabIds) {
        const tabPanes = (snap.panes ?? []).filter((p) => p.tabId === tabId && !p.virtual);
        if (!tabPanes.length) continue;
        const spare = tabPanes.find(isFree);
        if (spare) return { paneId: spare.id, tabId };
        const direction = tabPanes.length % 2 === 1 ? 'right' : 'down';
        const split = await soda(['pane', 'split', tabPanes.at(-1).id, '--direction', direction]);
        if (split.pane?.id && split.pane.tabId === tabId && !split.pane.virtual) return { paneId: split.pane.id, tabId };
      }
      const made = await soda(['tab', 'create', '--workspace', ctx.workspaceId, '--label', `aidev:${label}`.slice(0, 30)]);
      if (!made.tab?.id || !made.pane?.id || made.pane.tabId !== made.tab.id || made.pane.virtual) throw fail('新しい端末タブを確認できません');
      return { paneId: made.pane.id, tabId: made.tab.id };
    }
    const direction = panes.length % 2 === 1 ? 'right' : 'down';
    const made = await soda(['pane', 'split', panes.at(-1).id, '--direction', direction]);
    if (!made.pane?.id || made.pane.tabId !== ctx.tabId || made.pane.virtual) throw fail('新しい作業ターミナルを確認できません');
    return { paneId: made.pane.id, tabId: ctx.tabId };
  }
  /**
   * 選べる種類。`sodactl agent integrations --json` の `installed: true` だけ（claude・codex も含む。`needsUpdate` は選べるが、画面に出す）。
   * この操作を知らない古いサーバ（`not_found`）は `legacy: true`、それ以外の失敗は `unreadable: true` と `reason`。どちらも（読めないので）claude・codex だけ。短く覚える。
   */
  const kindsMemo = new Map();
  async function availableKinds(root) {
    const hit = kindsMemo.get(root);
    if (hit && now() - hit.at < INTEGRATIONS_TTL_MS) return hit.value;
    let value;
    try {
      const agentsMap = (await makeSoda(root)(['agent', 'integrations', '--json'], { timeout: 20000 })).agents;
      if (!agentsMap || typeof agentsMap !== 'object') throw new Error('agents がありません');
      const details = {};
      for (const kind of AGENT_KINDS) {
        const a = agentsMap[kind];
        details[kind] = { installed: a?.installed === true, needsUpdate: a?.needsUpdate === true, cliDetected: a?.cliDetected === true };
      }
      value = { legacy: false, available: AGENT_KINDS.filter((k) => details[k].installed), details };
    } catch (e) {
      // 古いサーバ（操作を知らない = not_found）だけが legacy。ログイン切れ・時間切れなどは「読めなかった」で、理由を添える（どちらも copilot・bob は選べない）
      const details = Object.fromEntries(AGENT_KINDS.map((k) => [k, { installed: LEGACY_KINDS.includes(k), needsUpdate: false, cliDetected: false }]));
      value = e?.code === 'not_found'
        ? { legacy: true, available: [...LEGACY_KINDS], details }
        : { legacy: false, unreadable: true, reason: clip(String(e?.message ?? e), 200), available: [...LEGACY_KINDS], details };
    }
    kindsMemo.set(root, { at: now(), value });
    return value;
  }
  /** Claude は先に決めた ID で `--session-id` / `--resume`。Codex は ID を先に決められないので、初回は指定せず起動し、後で取り込む。 */
  const launchArgs = (settings, kind, sessionId, resume, model, root) => {
    // Copilot・Bob も ID を先に決められない（初回は取り込み）。権限の指定は付けない。Bob はモデルの指定の付け方が確かでないので付けない
    if (kind === 'copilot') return [...(resume ? [`--resume=${sessionId}`] : []), ...(model ? ['--model', model] : [])];
    if (kind === 'bob') return resume ? ['--resume', sessionId] : [];
    if (kind === 'codex') {
      const common = ['-C', root, ...(model ? ['-m', model] : []), ...(CODEX_PERMISSIONS[settings.codexPermission] ?? [])];
      return resume ? ['resume', sessionId, ...common] : common;
    }
    const args = [resume ? '--resume' : '--session-id', sessionId];
    if (model) args.push('--model', model);
    if (settings.permissionMode) args.push('--permission-mode', settings.permissionMode);
    return args;
  };
  /** 起動して、そのエージェント（instanceId を含む）を確かめて返す。 */
  async function startAgent(soda, { name, kind, paneId, args }) {
    const res = await soda(['agent', 'start', name, '--kind', kind, '--pane', paneId, '--timeout', '60000', '--', ...args], { timeout: 90000 });
    const agent = res.agent?.instanceId ? res.agent : (await soda(['agent', 'get', paneId])).agent;
    if (agent?.paneId !== paneId || !agent.instanceId || !agent.tabId || (agent.kind && agent.kind !== kind)) throw fail('起動後のエージェントを確認できません');
    return agent;
  }
  /**
   * 台帳の記録とサーバの今のエージェントを照らす。別のものに入れ替わっていれば断る。サーバの再起動で会話が復元された
   * エージェントは名前を失っているので、台帳の名前を付け直す（`--expect` は name を必須とする）。
   */
  async function bindAgent(soda, entry) {
    let agent = (await soda(['agent', 'get', entry.paneId])).agent;
    if (agent?.paneId !== entry.paneId || (agent.kind && agent.kind !== entry.kind)) throw fail('エージェントが見つかりません（入れ替わった可能性があります）');
    if (agent.name !== entry.name) agent = (await soda(['agent', 'rename', entry.paneId, entry.name])).agent ?? agent;
    if (!agent.instanceId || !agent.tabId) throw fail('エージェントの識別子を確認できません');
    return agent;
  }
  /** 一致を確かめてから送る（`agent prompt --expect` は 5 項目が必須）。`known` は起動直後に確かめ済みのエージェント。 */
  async function sendPrompt(soda, root, entry, text, known) {
    const agent = known ?? await bindAgent(soda, entry);
    const expect = { paneId: entry.paneId, instanceId: agent.instanceId, tabId: agent.tabId, projectDir: root, name: entry.name };
    return soda(['agent', 'prompt', entry.name, guardDash(text), '--expect', JSON.stringify(expect)], { timeout: 60000 });
  }
  async function writePromptFile(root, kind, content) {
    const base = await ensureStateDir(root);
    const dir = join(base, 'prompts');
    let st = null;
    try { st = await lstat(dir); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    if (st && (st.isSymbolicLink() || !st.isDirectory())) throw fail(`${dir} はフォルダではない（またはシンボリックリンク）ため使えません`);
    await mkdir(dir, { recursive: true, mode: 0o700 });
    if (!(await realpath(dir)).startsWith(base + sep)) throw fail('役割の文面の置き場所が PJ の外を指しています');
    const stem = `${kind.replace(/[^A-Za-z0-9._-]/g, '_')}-${stamp(now())}`;
    for (let i = 0; ; i++) {
      const file = join(dir, `${stem}${i ? `-${i}` : ''}.md`);
      try { await writeFile(file, content, { flag: 'wx', mode: 0o600 }); return file; } catch (e) { if (e.code !== 'EEXIST' || i >= 20) throw e; }
    }
  }
  function recordAfterFailure(root, role, slug, entry, error, resume) {
    const blocked = error.code === 'agent_not_ready';
    const lost = resume && RESUME_LOST.includes(error.code);
    // エージェントが居る可能性がある失敗だけ、新しい pane・UUID を台帳に残す（名前を握った孤児を作らない）。
    // pane が埋まっている・名前が使われている等の、起動に至らなかった失敗では、前の記録を残す
    const orphan = !resume && !!entry.paneId && ORPHAN_CODES.includes(error.code);
    return updateLedger(root, (l) => {
      const prev = slug ? l.workers[slug] : l.supervisor;
      const message = clip(error.message, 1000);
      let next;
      if (blocked) next = { ...entry, status: 'blocked', error: message }; // エージェントは居る（承認待ち）。役割・線は仕上げの印で残す
      else if (lost && prev) next = { ...prev, status: 'failed', error: `会話を再開できませんでした（${message}）。「新しい会話で始める」を使ってください` };
      else if (orphan) next = { ...entry, status: 'failed', error: message }; // 前の会話の ID は entry.previousSessions に入っている
      else if (prev?.sessionId) next = { ...prev, error: message };
      else next = { ...entry, status: 'failed', error: message };
      if (slug) l.workers[slug] = next; else l.supervisor = next;
      pushLog(l, now(), { from: 'app', slug: slug ?? null, kind: 'error', message: `${role}の${resume ? '再開' : '起動'}: ${error.message}` });
    });
  }

  async function aliveSupervisor(root, ctx) {
    const sup = (await readLedger(root)).supervisor;
    const view = agentView(sup, ctx.panes, now());
    if (!view?.alive) throw fail('監督が動いていません。先に監督を起動（または再開）してください');
    return { entry: sup, view };
  }

  /** 担当 → 監督の 3 本の線（監督・承認の代理・トリガ）。結べなくても起動は成功とし、結果を返す。 */
  async function linkWorker(soda, workerPane, supervisorPane, slug) {
    const base = ['graph', 'link', 'add', workerPane, supervisorPane];
    const specs = [
      ['監督', [...base, '--kind', 'supervise', '--json']],
      ['承認の代理', [...base, '--kind', 'approval', '--mode', 'notify', '--limit', '100', '--json']],
      ['トリガ', [...base, '--kind', 'trigger', '--on', 'done', `--prompt=${triggerPrompt(slug)}`, '--output', '60', '--when-busy', 'wait', '--limit', '100', '--json']],
    ];
    const errors = [];
    for (const [label, args] of specs) {
      try { await soda(args); } catch (e) { errors.push(`${label}の線: ${e.message}`); }
    }
    return errors;
  }

  /**
   * 起動の仕上げ（役割または再開の知らせ・担当なら線）。承認待ちで起動の途中に止まったものは、台帳の `pending` に残っている。
   * `known` は起動直後に確かめ済みのエージェント。届いたものは `pending` から外す。
   */
  async function finishPending(root, ctx, slug, { known } = {}) {
    const ledger = await readLedger(root);
    const entry = slug ? ledger.workers[slug] : ledger.supervisor;
    const warnings = [];
    if (!entry || !entry.pending.length) return { warnings, remaining: [] };
    const soda = makeSoda(root);
    const left = new Set(entry.pending);
    if (left.has('role') || left.has('note')) {
      try {
        let text;
        if (left.has('role')) {
          const content = slug
            ? workerPrompt({ root, tabId: ctx.tabId, slug, supervisorName: ledger.supervisor?.name ?? '', instruction: entry.instruction })
            : supervisorPrompt({ root, tabId: ctx.tabId });
          text = readFileInstruction(await writePromptFile(root, slug ? `worker-${slug}` : 'supervisor', content), slug ? `作業 ${slug} の担当` : '監督');
        } else text = slug ? workerResumeNote({ slug, tabId: ctx.tabId }) : supervisorResumeNote({ tabId: ctx.tabId });
        await sendPrompt(soda, root, entry, text, known);
        left.delete('role'); left.delete('note');
      } catch (e) { warnings.push(`役割の送信に失敗しました: ${e.message}`); }
    }
    let linkErrors = null;
    if (left.has('links')) {
      const sup = ledger.supervisor;
      if (sup && agentView(sup, ctx.panes, now())?.alive) {
        linkErrors = await linkWorker(soda, entry.paneId, sup.paneId, slug);
        warnings.push(...linkErrors);
        left.delete('links'); // 一部が失敗しても、成功した線を重ねないため、繰り返さない（失敗はログと linkErrors に残す）
      } else warnings.push('監督が動いていないため、線は結べませんでした（監督が動けば仕上げます）');
    }
    await updateLedger(root, (l) => {
      const t = slug ? l.workers[slug] : l.supervisor;
      if (!t || t.paneId !== entry.paneId) return;
      t.pending = PENDING_KINDS.filter((k) => left.has(k));
      if (linkErrors) t.linkErrors = linkErrors.slice(0, 5);
      for (const w of warnings) pushLog(l, now(), { from: 'app', slug: slug ?? null, kind: 'error', message: w });
    });
    return { warnings, remaining: [...left] };
  }

  /** 仕上げが残っていて、エージェントが生きていて待機しているものを、1 回だけ（失敗しても 20 秒以上あけて 3 回まで）仕上げる。 */
  const finishTries = new Map();
  async function finishAll(root, ctx) {
    if (launching.has(root)) return 0;
    const ledger = await readLedger(root);
    let n = 0;
    for (const [slug, entry] of [[null, ledger.supervisor], ...Object.entries(ledger.workers)]) {
      if (!entry?.pending?.length) continue;
      const view = agentView(entry, ctx.panes, now());
      if (!view.alive || view.status !== 'idle') continue;
      const key = `${root}|${slug ?? ''}|${entry.paneId}`;
      const tries = finishTries.get(key) ?? { count: 0, at: 0 };
      if (tries.count >= FINISH_MAX_TRIES || now() - tries.at < FINISH_GAP_MS) continue;
      finishTries.set(key, { count: tries.count + 1, at: +now() });
      const r = await finishPending(root, ctx, slug);
      if (!r.remaining.length) { n++; await logEvent(root, { from: 'app', slug, kind: 'event', message: `${slug ? `担当 ${slug}` : '監督'}の起動の仕上げを行いました` }); }
    }
    return n;
  }

  /**
   * 起動・再開の共通の流れ。承認待ちで止まったときは、台帳に仕上げの印（pending）を残して返す。
   * 新しい会話は、前の会話の ID を previousSessions（最新 5 件）に残してから置き換える。
   */
  async function launch(root, ctx, { slug = null, resume, model, kind: wantKind, instruction = '' }) {
    const isWorker = slug !== null;
    const roleLabel = isWorker ? `担当 ${slug}` : '監督';
    if (isWorker) await aliveSupervisor(root, ctx);
    const soda = makeSoda(root);
    const settings = await loadSettings(root);
    const ledger = await readLedger(root);
    const prev = isWorker ? ledger.workers[slug] : ledger.supervisor;
    const kind = resume ? prev.kind : wantKind || (isWorker ? settings.workerKind : settings.supervisorKind);
    // 新しく起動するときだけ、導入済みの種類かを確かめる（既存の会話の再開は、未導入でも試す）
    if (!resume && !(await availableKinds(root)).available.includes(kind)) throw fail(notInstalledMessage(kind));
    const sessionId = resume ? prev.sessionId : kind === 'claude' ? uuid() : '';
    const name = isWorker ? workerName(root, slug) : supervisorName(root);
    const useModel = model || (isWorker ? settings.workerModel : settings.supervisorModel);
    const previousSessions = [...(prev?.previousSessions ?? [])];
    if (!resume && prev?.sessionId && !prev.pending?.includes('role')) previousSessions.unshift({ sessionId: prev.sessionId, kind: prev.kind, endedAt: iso(now()) });
    const base = {
      ...(isWorker ? { slug } : {}), name, kind, sessionId, workspaceId: ctx.workspaceId, model: useModel,
      startedAt: resume && prev.startedAt ? prev.startedAt : iso(now()), resumedAt: resume ? iso(now()) : null,
      pending: [resume ? 'note' : 'role', ...(isWorker ? ['links'] : [])],
      previousSessions: previousSessions.slice(0, PREVIOUS_SESSIONS_MAX),
      ...(isWorker ? { instruction: resume ? prev.instruction ?? '' : instruction, lastReport: resume ? prev.lastReport : null, related: resume ? prev.related ?? [] : [], linkErrors: [], doneAt: '' } : {}),
    };
    let place, agent, startedLate = false;
    try {
      const extraTabIds = [...new Set(Object.values(ledger.workers).map((w) => w.tabId).filter((t) => t && t !== ctx.tabId))].reverse();
      place = await placePane(soda, ctx, { preferPaneId: prev?.paneId, label: slug ?? 'sup', extraTabIds });
      agent = await startAgent(soda, { name, kind, paneId: place.paneId, args: launchArgs(settings, kind, sessionId, resume, useModel, root) });
    } catch (e) {
      // `timeout` は「会話が無い」ではなく「まだ確かめられない」。名前・種類が付いて動いていれば、起動したものとして扱う
      if (e.code === 'timeout' && place?.paneId) {
        try {
          const got = (await soda(['agent', 'get', place.paneId])).agent;
          if (got?.paneId === place.paneId && got.name === name && got.instanceId && got.tabId && (!got.kind || got.kind === kind)) { agent = got; startedLate = true; }
        } catch { /* 確かめられなければ、失敗として扱う */ }
      }
      if (!startedLate) {
      const entry = cleanAgent({ ...base, tabId: place?.tabId ?? '', paneId: place?.paneId ?? '' }, slug);
      await recordAfterFailure(root, roleLabel, slug, entry, e, resume).catch(() => {});
      if (e.code === 'agent_not_ready') {
        return { status: 'blocked', ...(isWorker ? { slug } : {}), message: 'エージェントが確認（信頼・承認など）を待っています。端末で答えてください（答えた後に［起動］を押し直すと、役割と線が届きます）。', [isWorker ? 'worker' : 'supervisor']: agentView({ ...entry, status: 'blocked' }, ctx.panes, now()) };
      }
      throw e;
      }
    }
    const entry = cleanAgent({ ...base, tabId: place.tabId, paneId: place.paneId, status: 'running', error: null }, slug);
    await updateLedger(root, (l) => {
      if (isWorker) l.workers[slug] = entry; else l.supervisor = entry;
      pushLog(l, now(), { from: 'app', slug, kind: 'event', message: `${roleLabel}を${resume ? '再開' : '起動'}しました（${name}）` });
    });
    // 起動に時間がかかった（timeout 後に確かめた）ものは、まだ読み込み中かもしれない。待機になってから仕上げる（finishAll）
    const finished = startedLate
      ? { warnings: ['起動に時間がかかっています。待機になったら、役割（と線）を届けます'] }
      : await finishPending(root, ctx, slug, { known: agent });
    if (!sessionId) await captureSessions(root).catch(() => {});
    const fresh = (await readLedger(root));
    const livePanes = [...ctx.panes.filter((p) => p.id !== place.paneId), { id: place.paneId, agent: kind, agentState: 'idle' }];
    const view = agentView((isWorker ? fresh.workers[slug] : fresh.supervisor) ?? entry, livePanes, now());
    return { status: resume ? 'resumed' : 'started', ...(isWorker ? { slug, worker: view } : { supervisor: view }), ...(finished.warnings.length ? { warnings: finished.warnings } : {}) };
  }

  const noResumeReason = (what, view) => {
    if (!view) return `再開できる${what}の記録がありません。起動を使ってください`;
    if (view.pending.includes('role')) return `${what}は役割を送る前に止まったため、再開できる会話がありません。起動（新しい会話）を使ってください`;
    if (view.recordedStatus === 'failed') return `${what}の前回の起動・再開に失敗しています。「新しい会話で始める」を使ってください`;
    if (!view.sessionId) return `${what}の会話 ID をまだ取得できていないため再開できません。起動し直してください`;
    return null;
  };

  /** 生きているが仕上げが残っているとき、答えた後に押し直されたら、仕上げだけを行う。 */
  async function alreadyOrFinish(root, ctx, slug, view, label) {
    if (view.pending.length && view.status === 'idle') {
      const r = await finishPending(root, ctx, slug);
      return { status: 'finished', ...(slug ? { slug } : {}), message: r.remaining.length ? `${label}の仕上げは一部残っています` : `${label}の役割（と線）を届けました`, ...(r.warnings.length ? { warnings: r.warnings } : {}) };
    }
    if (view.pending.length) return { status: 'already', ...(slug ? { slug } : {}), message: `${label}は確認待ち・作業中です。端末で答えてから、もう一度押してください（役割と線が未送信です）` };
    return { status: 'already', ...(slug ? { slug } : {}), message: `${label}はすでに動いています` };
  }

  async function startSupervisor(root, ctx, { model, kind, fresh = false } = {}) {
    return withLaunchLock(root, async () => {
      const prev = (await readLedger(root)).supervisor;
      const view = agentView(prev, ctx.panes, now());
      if (view?.alive) return { ...(await alreadyOrFinish(root, ctx, null, view, '監督')), supervisor: view };
      if (view?.resumable && !fresh) throw fail('再開できる会話があります。「監督を再開」を使うか、「新しい会話で始める」を選んでください');
      return launch(root, ctx, { resume: false, model, kind });
    });
  }
  async function resumeSupervisor(root, ctx) {
    return withLaunchLock(root, async () => {
      const prev = (await readLedger(root)).supervisor;
      const view = agentView(prev, ctx.panes, now());
      if (view?.alive) return { ...(await alreadyOrFinish(root, ctx, null, view, '監督')), supervisor: view };
      const why = noResumeReason('監督', view);
      if (why) throw fail(why);
      return launch(root, ctx, { resume: true });
    });
  }

  async function promptSupervisor(root, ctx, { text, source = 'ui' }) {
    const { entry } = await aliveSupervisor(root, ctx);
    const soda = makeSoda(root);
    await sendPrompt(soda, root, entry, text);
    await logEvent(root, source === 'ui' ? { from: 'user', kind: 'instruction', message: text } : { from: 'app', kind: 'instruction', message: `[CLI から] ${text}` });
    return { status: 'sent' };
  }

  async function startWorker(root, ctx, { slug, instruction, model, kind, fresh = false }) {
    return withLaunchLock(root, async () => {
      const prev = (await readLedger(root)).workers[slug];
      const view = agentView(prev, ctx.panes, now());
      if (view?.alive) return { ...(await alreadyOrFinish(root, ctx, slug, view, `作業 ${slug} の担当`)), worker: view };
      if (view?.resumable && !fresh) throw fail(`作業 ${slug} の担当は再開できる会話があります。再開（worker-resume）を使うか、「新しい会話で始める」（fresh:true）を選んでください`);
      return launch(root, ctx, { slug, resume: false, instruction, model, kind });
    });
  }
  async function resumeWorker(root, ctx, { slug }) {
    return withLaunchLock(root, async () => {
      const prev = (await readLedger(root)).workers[slug];
      const view = agentView(prev, ctx.panes, now());
      if (view?.alive) return { ...(await alreadyOrFinish(root, ctx, slug, view, `作業 ${slug} の担当`)), worker: view };
      const why = noResumeReason(`作業 ${slug} の担当`, view);
      if (why) throw fail(why);
      return launch(root, ctx, { slug, resume: true });
    });
  }

  async function promptWorker(root, ctx, { slug, text, source = 'ui' }) {
    const ledger = await readLedger(root);
    const w = ledger.workers[slug];
    if (!w) throw fail(`作業 ${slug} の担当の記録がありません`);
    if (!agentView(w, ctx.panes, now()).alive) throw fail(`作業 ${slug} の担当は動いていません。再開（worker-resume）を使ってください`);
    await sendPrompt(makeSoda(root), root, w, text);
    await updateLedger(root, (l) => { if (l.workers[slug]) l.workers[slug].doneAt = ''; }); // 追加の作業が始まる。完了後の終了は取り消す
    await logEvent(root, { from: source === 'ui' ? 'user' : 'supervisor', slug, kind: 'instruction', message: text });
    return { status: 'sent', slug };
  }

  /** 担当からの報告。`question`・`failed`・`blocked` は監督へも中継する（失敗はログに残すだけで再試行しない）。 */
  async function reportWorker(root, ctx, { slug, status, message }) {
    const settings = await loadSettings(root);
    const found = await updateLedger(root, (l) => {
      const w = l.workers[slug];
      if (!w) return false;
      w.lastReport = { status, message: clip(message, LEDGER_LIMITS.message), at: iso(now()) };
      if (status === 'done' && settings.exitOnDone && !w.noAutoClose) w.doneAt = iso(now()); // 待機になったら終了する（会話 ID は記録済みで、再開できる）
      else if (status !== 'done') w.doneAt = '';
      pushLog(l, now(), { from: 'worker', slug, kind: 'report', message: `[${status}] ${message}` });
      return true;
    });
    if (!found) throw fail(`作業 ${slug} の担当の記録がありません`);
    let relayed = null;
    if (RELAYED.includes(status)) {
      try {
        const { entry } = await aliveSupervisor(root, ctx);
        await sendPrompt(makeSoda(root), root, entry, `[aidev 担当 ${slug} の報告: ${status}] ${message}`);
        relayed = true;
      } catch (e) {
        relayed = false;
        await logEvent(root, { from: 'app', slug, kind: 'error', message: `監督への中継に失敗しました: ${e.message}` });
      }
    }
    return { status: 'recorded', slug, relayed };
  }

  async function report(root, { message, level = 'info' }) {
    await updateLedger(root, (l) => pushLog(l, now(), { from: 'supervisor', kind: 'report', level, message }));
    return { status: 'recorded' };
  }

  async function overview(root, panes, { logLimit = 60 } = {}) {
    const [ledger, settings, kinds] = await Promise.all([readLedger(root), loadSettings(root), availableKinds(root)]);
    return {
      kinds,
      supervisor: agentView(ledger.supervisor, panes, now()),
      workers: Object.values(ledger.workers).map((w) => agentView(w, panes, now())),
      settings,
      log: ledger.log.slice(-logLimit).reverse(),
    };
  }
  const logList = async (root, limit = 50) => ({ log: (await readLedger(root)).log.slice(-limit).reverse() });

  // ---- 関連するエージェント（担当が起こした別のエージェント） ----------------------------------------------
  const relatedCache = new Map();
  const statusOf = (pane) => (pane.agentState === 'working' ? 'working' : pane.agentState === 'blocked' ? 'blocked' : 'idle');
  /**
   * 担当の pane に「監督・承認の代理」の線で連なるエージェントを、グラフから再帰で辿る（担当が `sodactl` で起こすと
   * 自動で線が引かれる）。線が無い場合に備え、担当が明示登録した pane（台帳の related）も足す。生きているものだけ。
   * 結果は slug ごとの配列。グラフが読めなければ登録分だけ。
   */
  async function related(root, panes, { force = false } = {}) {
    const hit = relatedCache.get(root);
    if (!force && hit && now() - hit.at < RELATED_TTL_MS) return hit.map;
    const ledger = await readLedger(root);
    const workers = Object.values(ledger.workers);
    const map = {};
    if (workers.length) {
      let links = [];
      try { links = (await makeSoda(root)(['graph', 'show', '--json'], { timeout: 20000 })).graph?.links ?? []; } catch { /* 登録分だけ */ }
      const children = new Map();
      for (const l of links) {
        if (l.kind !== 'supervise' && l.kind !== 'approval') continue;
        const parent = String(l.to).replace(/^local:/, '');
        const child = String(l.from).replace(/^local:/, '');
        if (!children.has(parent)) children.set(parent, new Set());
        children.get(parent).add(child);
      }
      const reserved = new Set([ledger.supervisor?.paneId, ...workers.map((w) => w.paneId)].filter(Boolean));
      const byId = new Map(panes.map((p) => [p.id, p]));
      for (const w of workers) {
        const seen = new Set([w.paneId]);
        const out = [];
        let frontier = [w.paneId];
        for (let depth = 1; depth <= RELATED_DEPTH && frontier.length; depth++) {
          const next = [];
          for (const parent of frontier) {
            for (const child of children.get(parent) ?? []) {
              if (seen.has(child) || reserved.has(child)) continue;
              seen.add(child); next.push(child);
              const pane = byId.get(child);
              if (pane?.agent) out.push({ slug: w.slug, paneId: child, kind: pane.agent, status: statusOf(pane), label: str(pane.label, 60), depth, registered: false });
            }
          }
          frontier = next;
        }
        for (const id of w.related ?? []) {
          const pane = byId.get(id);
          if (pane?.agent && !seen.has(id) && !reserved.has(id)) { seen.add(id); out.push({ slug: w.slug, paneId: id, kind: pane.agent, status: statusOf(pane), label: str(pane.label, 60), depth: 1, registered: true }); }
        }
        map[w.slug] = out;
      }
    }
    relatedCache.set(root, { at: now(), map });
    return map;
  }
  /** 担当が、自分が起こした別のエージェントを明示登録する（線が自動で引かれなかったときの保険）。 */
  async function registerRelated(root, ctx, { slug, paneId }) {
    const known = await readLedger(root);
    if (!known.workers[slug]) throw fail(`作業 ${slug} の担当の記録がありません`);
    if (paneId === known.workers[slug].paneId || paneId === known.supervisor?.paneId) throw fail('担当・監督自身は登録できません');
    const pane = ctx.panes.find((p) => p.id === paneId);
    if (!pane?.agent) throw fail('その pane にエージェントが居ません');
    if (pane.projectDir !== root && !ctx.panes.some((p) => p.id === paneId && p.workspaceId === ctx.workspaceId)) throw fail('この PJ の pane ではありません');
    // 登録できるのは、担当の pane から線（監督・承認の代理）で連なる pane だけ（利用者自身の pane を登録・終了させない）
    let links;
    try { links = (await makeSoda(root)(['graph', 'show', '--json'], { timeout: 20000 })).graph?.links ?? []; } catch (e) { throw fail(`グラフを読めないため、登録を確かめられません（${e.message}）`); }
    const down = new Set([known.workers[slug].paneId]);
    for (let i = 0; i < 6; i++) {
      for (const l of links) if ((l.kind === 'supervise' || l.kind === 'approval') && down.has(String(l.to).replace(/^local:/, ''))) down.add(String(l.from).replace(/^local:/, ''));
    }
    if (!down.has(paneId)) throw fail('その pane は、担当の pane から線で連なっていません（担当が自分の pane から起こしたものだけ登録できます）');
    const found = await updateLedger(root, (l) => {
      const w = l.workers[slug];
      if (!w) return false;
      if (paneId === w.paneId || paneId === l.supervisor?.paneId) return 'self';
      w.related = [...new Set([...(w.related ?? []), paneId])].slice(-16);
      pushLog(l, now(), { from: 'worker', slug, kind: 'event', message: `関連するエージェントを登録しました（${paneId.slice(0, 8)}・${pane.agent}）` });
      return true;
    });
    if (found === false) throw fail(`作業 ${slug} の担当の記録がありません`);
    if (found === 'self') throw fail('担当・監督自身は登録できません');
    relatedCache.delete(root);
    return { status: 'recorded', slug, paneId };
  }
  async function relatedTarget(root, ctx, slug, paneId) {
    const w = (await readLedger(root)).workers[slug];
    if (!w) throw fail(`作業 ${slug} の担当の記録がありません`);
    if (paneId === w.paneId) return w;
    const list = (await related(root, ctx.panes, { force: true }))[slug] ?? [];
    const hit = list.find((a) => a.paneId === paneId);
    if (!hit) throw fail(`その pane は作業 ${slug} の関連するエージェントではありません`);
    return hit;
  }
  async function promptRelated(root, ctx, { slug, paneId, text, source = 'ui' }) {
    const target = await relatedTarget(root, ctx, slug, paneId);
    const soda = makeSoda(root);
    const agent = (await soda(['agent', 'get', paneId])).agent;
    if (!agent || agent.paneId !== paneId) throw fail('エージェントが見つかりません（入れ替わった可能性があります）');
    const args = ['agent', 'prompt', paneId, guardDash(text)];
    if (agent.name && agent.instanceId && agent.tabId) args.push('--expect', JSON.stringify({ paneId, instanceId: agent.instanceId, tabId: agent.tabId, projectDir: root, name: agent.name }));
    await soda(args, { timeout: 60000 });
    if (target.paneId === paneId && target.slug === slug) await updateLedger(root, (l) => { if (l.workers[slug]?.paneId === paneId) l.workers[slug].doneAt = ''; });
    await logEvent(root, { from: source === 'ui' ? 'user' : 'supervisor', slug, kind: 'instruction', message: `[関連 ${paneId.slice(0, 8)}] ${text}` });
    return { status: 'sent', slug, paneId };
  }
  async function readRelated(root, ctx, { slug, paneId, lines = 60 }) {
    await relatedTarget(root, ctx, slug, paneId);
    const res = await makeSoda(root)(['agent', 'read', paneId, '--lines', String(lines)], { timeout: 20000, rawMax: 40000 });
    return { slug, paneId, text: String(res.raw ?? res.text ?? '') };
  }

  const triggerMemo = new Map();
  /** 担当 → 監督のトリガの線が、`since`（完了の報告）より後に `sent` になったか。true / false / null（線が無い・読めない）。 */
  async function triggerSent(soda, workerPane, supervisorPane, since) {
    try {
      const links = (await soda(['graph', 'show', '--json'], { timeout: 20000 })).graph?.links ?? [];
      const link = links.find((l) => l.kind === 'trigger' && l.from === `local:${workerPane}` && l.to === `local:${supervisorPane}`);
      if (!link) return null;
      const runs = (await soda(['graph', 'history', link.id, '--json'], { timeout: 20000 })).runs ?? [];
      return runs.some((r) => r.result === 'sent' && Number(r.at) >= since);
    } catch { return null; }
  }
  /**
   * 完了（`done`）を報告した担当と、自動の線で連なる関連するエージェントを、待機になったら終了する（pane を閉じる）。
   * 閉じる条件: (1) 担当が待機 (2) 完了の知らせ（トリガの線）が監督へ `sent` になった（閉じるとノードと線が消え、
   * 監督が作業中で待っていた知らせが黙って取り消されるため） (3) 自動の線で連なる関連するエージェントが全部待機。
   * 登録分は閉じない。30 分待っても満たされなければ、理由をログに残して以後は自動で閉じない。
   * 会話 ID は台帳にあるので再開できる。Codex で会話 ID が未取得なら、再開できなくなるので見送る。
   */
  async function finishDone(root, ctx) {
    if (launching.has(root)) return 0;
    const ledger = await readLedger(root);
    const settings = await loadSettings(root);
    const clear = (slug) => updateLedger(root, (l) => { if (l.workers[slug]) l.workers[slug].doneAt = ''; });
    let n = 0;
    for (const w of Object.values(ledger.workers)) {
      if (!w.doneAt) continue;
      const age = now() - Date.parse(w.doneAt);
      const view = agentView(w, ctx.panes, now());
      if (!settings.exitOnDone || w.noAutoClose || !(age >= 0) || !view.alive) { await clear(w.slug); continue; }
      const giveUp = async (why) => updateLedger(root, (l) => {
        const t = l.workers[w.slug];
        if (!t) return;
        t.doneAt = ''; t.noAutoClose = true;
        pushLog(l, now(), { from: 'app', slug: w.slug, kind: 'error', message: `${why}、担当を閉じませんでした（以後この担当は自動では閉じません）` });
      });
      if (age < EXIT_GRACE_MS) continue;
      if (view.status !== 'idle') { if (age > EXIT_GIVE_UP_MS) await giveUp('担当が待機にならないため'); continue; }
      if (needsCapture(w)) {
        await captureSessions(root).catch(() => {});
        if (needsCapture((await readLedger(root)).workers[w.slug])) {
          await updateLedger(root, (l) => { const t = l.workers[w.slug]; if (t) { t.doneAt = ''; pushLog(l, now(), { from: 'app', slug: w.slug, kind: 'error', message: '会話 ID が未取得のため、終了を見送りました（終了すると再開できなくなります）' }); } });
          continue;
        }
      }
      const soda = makeSoda(root);
      const sup = ledger.supervisor;
      // グラフの読み取りは毎周期（3 秒）は行わない。20 秒以上あける
      const memoKey = `${root}|${w.slug}|${w.doneAt}`;
      const memo = triggerMemo.get(memoKey);
      let sent;
      if (memo && now() - memo.at < TRIGGER_CHECK_GAP_MS) sent = memo.value;
      else {
        sent = sup ? await triggerSent(soda, w.paneId, sup.paneId, Date.parse(w.doneAt)) : null;
        triggerMemo.set(memoKey, { at: +now(), value: sent });
      }
      if (sent !== true) { if (age > EXIT_GIVE_UP_MS) await giveUp('完了の知らせが監督へ届いていないので'); continue; }
      const rel = (await related(root, ctx.panes, { force: true }))[w.slug] ?? [];
      const auto = rel.filter((a) => !a.registered);
      const kept = rel.filter((a) => a.registered);
      if (auto.some((a) => a.status !== 'idle')) { if (age > EXIT_GIVE_UP_MS) await giveUp('関連するエージェントが作業中・承認待ちのため'); continue; }
      const errors = [];
      for (const paneId of [...auto.map((a) => a.paneId).reverse(), w.paneId]) {
        try { await soda(['pane', 'close', paneId]); } catch (e) { errors.push(`${paneId.slice(0, 8)}: ${e.message}`); }
      }
      await updateLedger(root, (l) => {
        const t = l.workers[w.slug];
        if (!t || t.paneId !== w.paneId) return;
        t.doneAt = ''; t.status = 'stopped'; t.pending = [];
        const tail = kept.length ? `。登録された関連するエージェント ${kept.length} 件は閉じていません` : '';
        pushLog(l, now(), { from: 'app', slug: w.slug, kind: errors.length ? 'error' : 'event', message: errors.length ? `完了後の終了に失敗した pane があります: ${errors.join(' / ')}` : `作業 ${w.slug} が完了したため、担当${auto.length ? `と関連するエージェント ${auto.length} 件` : ''}を終了しました（会話 ID は記録済み。再開できます）${tail}` });
      });
      relatedCache.delete(root);
      triggerMemo.delete(memoKey);
      n++;
    }
    return n;
  }

  const needsCapture = (e) => !!e && !e.sessionId && e.kind !== 'claude' && e.status !== 'failed';
  /**
   * 払い出された会話 ID の取り込み（Codex）。Sodashitsu が pane に記録した `agentSession` を、種類・名前が一致するものだけ採る。
   * 起動直後は未報告なので、呼び出し側が周期的に呼ぶ。取り込めた数を返す。
   */
  async function captureSessions(root) {
    const ledger = await readLedger(root);
    const pending = [[null, ledger.supervisor], ...Object.entries(ledger.workers)].filter(([, e]) => needsCapture(e));
    if (!pending.length) return 0;
    const snap = await makeSoda(root)(['snapshot']);
    const found = [];
    for (const [slug, e] of pending) {
      const pane = (snap.panes ?? []).find((p) => p.id === e.paneId && !p.virtual);
      const ref = pane?.agentSession;
      if (pane?.agent?.kind === e.kind && pane.agent.name === e.name && ref?.kind === e.kind && sessionIdOk(e.kind, ref.sessionId)) found.push({ slug, paneId: e.paneId, name: e.name, id: ref.sessionId });
    }
    if (!found.length) return 0;
    return updateLedger(root, (l) => {
      let n = 0;
      for (const f of found) {
        const t = f.slug ? l.workers[f.slug] : l.supervisor;
        if (t && t.paneId === f.paneId && t.name === f.name && !t.sessionId) {
          t.sessionId = f.id; n++;
          pushLog(l, now(), { from: 'app', slug: f.slug, kind: 'event', message: `${f.slug ? `担当 ${f.slug}` : '監督'}の会話 ID を記録しました（${f.id.slice(0, 8)}）` });
        }
      }
      return n;
    });
  }

  /** 監督が生きていなければ、1 回だけ起動（記録があれば再開）を試みる。呼び出し側が回数を数える。 */
  async function autoStart(root, ctx) {
    const settings = await loadSettings(root);
    if (!settings.autoStartSupervisor) return { status: 'disabled' };
    const prev = (await readLedger(root)).supervisor;
    if (prev && agentView(prev, ctx.panes, now()).alive) return { status: 'already' };
    return agentView(prev, ctx.panes, now())?.resumable ? resumeSupervisor(root, ctx) : startSupervisor(root, ctx);
  }

  return {
    availableKinds, startSupervisor, resumeSupervisor, promptSupervisor, startWorker, resumeWorker, promptWorker, reportWorker,
    report, overview, logList, autoStart, captureSessions, needsCapture, note: logEvent, finishAll, finishDone, related, registerRelated, promptRelated, readRelated, delegate: (root, ctx, slug) => promptSupervisor(root, ctx, { text: delegateInstruction(slug) }),
  };
}
