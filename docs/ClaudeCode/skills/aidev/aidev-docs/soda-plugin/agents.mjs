// 台帳（セッション ID の記憶）と、sodactl を使った監督・担当エージェントの起動・再開・指示・グラフの線。
// 台帳は `<PJ>/.soda/aidev/`（リポジトリに入らない）。`.aidev/` には書かない。
import { createHash, randomUUID } from 'node:crypto';
import { execFile } from 'node:child_process';
import { lstat, mkdir, readFile, realpath, rename, rm, writeFile } from 'node:fs/promises';
import { join, sep } from 'node:path';
import { promisify } from 'node:util';
import { delegateInstruction, readFileInstruction, supervisorPrompt, SUPERVISOR_RESUME_NOTE, triggerPrompt, workerPrompt, workerResumeNote } from './prompts.mjs';

const execute = promisify(execFile);

export const WORKER_SLUG = /^[a-z0-9][a-z0-9-]{0,63}$/;
export const MODEL_RE = /^[A-Za-z0-9._\-[\]]{1,64}$/;
export const PERMISSION_MODES = ['', 'default', 'acceptEdits', 'auto', 'plan'];
export const AGENT_KINDS = ['claude', 'codex'];
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
const AGENT_STATUSES = ['running', 'blocked', 'stopped', 'failed'];
const STARTING_GRACE_MS = 20_000;
const RELAYED = ['question', 'failed', 'blocked'];
export const PANE_ID_RE = /^[0-9a-f][0-9a-f-]{3,63}$/i;
const RELATED_DEPTH = 3;
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

function cleanAgent(a, slug) {
  if (!a || typeof a !== 'object') return null;
  const out = {
    ...(slug ? { slug } : {}),
    name: str(a.name, 32), kind: AGENT_KINDS.includes(a.kind) ? a.kind : 'claude',
    sessionId: UUID_RE.test(a.sessionId ?? '') ? a.sessionId : '',
    paneId: str(a.paneId, 64), tabId: str(a.tabId, 64), workspaceId: str(a.workspaceId, 64),
    model: MODEL_RE.test(a.model ?? '') ? a.model : '',
    startedAt: str(a.startedAt, 40), resumedAt: a.resumedAt ? str(a.resumedAt, 40) : null,
    status: AGENT_STATUSES.includes(a.status) ? a.status : 'stopped',
    error: a.error ? str(a.error, 1000) : null,
  };
  if (slug) {
    const r = a.lastReport;
    out.lastReport = r && typeof r === 'object' ? { status: WORKER_STATUSES.includes(r.status) ? r.status : 'progress', message: str(r.message, LEDGER_LIMITS.message), at: str(r.at, 40) } : null;
    out.linkErrors = Array.isArray(a.linkErrors) ? a.linkErrors.slice(0, 5).map((x) => str(x, 300)) : [];
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

export async function readLedger(root) {
  const dir = await ensureStateDir(root, false);
  if (!dir) return emptyLedger();
  const file = join(dir, 'agents.json');
  let text;
  try { text = await readFile(file, 'utf8'); } catch (e) { if (e.code === 'ENOENT') return emptyLedger(); throw e; }
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
    await atomicWrite(join(await ensureStateDir(root), 'agents.json'), JSON.stringify(ledger, null, 2) + '\n');
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

export const DEFAULT_SETTINGS = Object.freeze({ supervisorModel: '', workerModel: '', permissionMode: '', autoStartSupervisor: true, supervisorKind: 'claude', workerKind: 'claude', codexPermission: '' });
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
      if (!AGENT_KINDS.includes(src[key])) throw fail('エージェントの種類は claude か codex です');
      s[key] = src[key];
    }
  }
  if ('codexPermission' in src) {
    if (typeof src.codexPermission !== 'string' || !Object.hasOwn(CODEX_PERMISSIONS, src.codexPermission)) throw fail('Codex の権限は read-only・workspace-write・workspace-write-never のどれかです');
    s.codexPermission = src.codexPermission;
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
    return normalizeSettings(JSON.parse(await readFile(join(dir, 'settings.json'), 'utf8')));
  } catch { return { ...DEFAULT_SETTINGS }; }
}
export async function saveSettings(root, input) {
  const next = normalizeSettings(input, await loadSettings(root));
  await atomicWrite(join(await ensureStateDir(root), 'settings.json'), JSON.stringify(next, null, 2) + '\n');
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
    model: entry.model, status, recordedStatus: entry.status, agentState, alive, resumable: !alive && !!entry.sessionId, sessionPending: !entry.sessionId && entry.kind !== 'claude',
    startedAt: entry.startedAt, resumedAt: entry.resumedAt, error: entry.error,
    ...(entry.slug ? { lastReport: entry.lastReport ?? null, linkErrors: entry.linkErrors ?? [] } : {}),
  };
}
const shortHash = (s, n) => createHash('sha256').update(s).digest('hex').slice(0, n);
/** `agent rename` の書式 `[a-z][a-z0-9_-]{0,31}`。PJ の根の短いハッシュで他の PJ と衝突させない。 */
export const supervisorName = (root) => `aidev-sup-${shortHash(root, 6)}`;
export function workerName(root, slug) {
  const part = slug.replace(/^\d{8}-/, '').replace(/-+/g, '-').slice(0, 14).replace(/-$/, '') || 'work';
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

  async function choosePane(soda, tabId) {
    const snap = await soda(['snapshot']);
    const panes = (snap.panes ?? []).filter((p) => p.tabId === tabId && !p.virtual);
    const free = panes.find((p) => !p.agent && !p.busy && (p.status === undefined || p.status === 'running'));
    if (free) return free.id;
    if (!panes.length) throw fail('アプリのタブに作業ターミナルがありません');
    const made = await soda(['pane', 'split', panes[0].id, '--direction', 'right']);
    if (!made.pane?.id || made.pane.tabId !== tabId || made.pane.virtual) throw fail('新しい作業ターミナルを確認できません');
    return made.pane.id;
  }
  async function newTerminalTab(soda, workspaceId, slug) {
    const made = await soda(['tab', 'create', '--workspace', workspaceId, '--label', `aidev:${slug}`.slice(0, 30)]);
    if (!made.tab?.id || !made.pane?.id || made.pane.tabId !== made.tab.id || made.pane.virtual) throw fail('新しい端末タブを確認できません');
    return { tabId: made.tab.id, paneId: made.pane.id };
  }
  /** Claude は先に決めた ID で `--session-id` / `--resume`。Codex は ID を先に決められないので、初回は指定せず起動し、後で取り込む。 */
  const launchArgs = (settings, kind, sessionId, resume, model, root) => {
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
    const dir = join(await ensureStateDir(root), 'prompts');
    await mkdir(dir, { recursive: true, mode: 0o700 });
    const file = join(dir, `${kind}-${stamp(now())}.md`);
    await writeFile(file, content, { flag: 'wx', mode: 0o600 });
    return file;
  }
  function recordAfterFailure(root, role, slug, entry, error, resume) {
    const blocked = error.code === 'agent_not_ready';
    return updateLedger(root, (l) => {
      const prev = slug ? l.workers[slug] : l.supervisor;
      const message = clip(error.message, 1000);
      // 承認待ちはエージェントが居るので新しい記録にする。それ以外で以前の記録があれば、セッション ID を残す（再開できるように）
      const next = blocked ? { ...entry, status: 'blocked', error: message } : prev?.sessionId ? { ...prev, error: message } : { ...entry, status: 'failed', error: message };
      if (slug) l.workers[slug] = next; else l.supervisor = next;
      pushLog(l, now(), { from: 'app', slug: slug ?? null, kind: 'error', message: `${role}の${resume ? '再開' : '起動'}: ${error.message}` });
    });
  }

  function supervisorEntry(base) {
    return cleanAgent({ ...base }, null);
  }

  /** 監督の起動・再開の共通の流れ。 */
  async function launchSupervisor(root, ctx, { resume, model, kind: wantKind }) {
    const soda = makeSoda(root);
    const settings = await loadSettings(root);
    const ledger = await readLedger(root);
    const prev = ledger.supervisor;
    const kind = resume ? prev.kind : wantKind || settings.supervisorKind;
    const sessionId = resume ? prev.sessionId : kind === 'claude' ? uuid() : '';
    const name = supervisorName(root);
    const tabId = resume && prev.tabId && ctx.panes.some((p) => p.tabId === prev.tabId && !p.virtual) ? prev.tabId : ctx.tabId;
    const useModel = model || settings.supervisorModel;
    const base = { name, kind, sessionId, tabId, workspaceId: ctx.workspaceId, model: useModel, startedAt: resume && prev.startedAt ? prev.startedAt : iso(now()), resumedAt: resume ? iso(now()) : null };
    let paneId, agent;
    try {
      paneId = await choosePane(soda, tabId);
      agent = await startAgent(soda, { name, kind, paneId, args: launchArgs(settings, kind, sessionId, resume, useModel, root) });
    } catch (e) {
      const entry = supervisorEntry({ ...base, paneId: paneId ?? '' });
      await recordAfterFailure(root, '監督', null, entry, e, resume).catch(() => {});
      if (e.code === 'agent_not_ready') return { status: 'blocked', message: 'エージェントが確認（信頼・承認など）を待っています。作業画面で答えてください。', supervisor: agentView({ ...entry, status: 'blocked' }, ctx.panes, now()) };
      throw e;
    }
    const entry = supervisorEntry({ ...base, paneId, status: 'running', error: null });
    await updateLedger(root, (l) => {
      l.supervisor = entry;
      pushLog(l, now(), { from: 'app', kind: 'event', message: resume ? `監督を再開しました（${name}）` : `監督を起動しました（${name}）` });
    });
    let warning = null;
    try {
      if (resume) await sendPrompt(soda, root, entry, SUPERVISOR_RESUME_NOTE, agent);
      else {
        const file = await writePromptFile(root, 'supervisor', supervisorPrompt({ root, tabId: ctx.tabId }));
        await sendPrompt(soda, root, entry, readFileInstruction(file, '監督'), agent);
      }
    } catch (e) {
      warning = `起動はしましたが、役割の送信に失敗しました: ${e.message}`;
      await logEvent(root, { from: 'app', kind: 'error', message: warning });
    }
    if (!sessionId) await captureSessions(root).catch(() => {});
    const fresh = (await readLedger(root)).supervisor ?? entry;
    return { status: resume ? 'resumed' : 'started', supervisor: agentView(fresh, [...ctx.panes, { id: paneId, agent: kind, agentState: 'idle' }], now()), ...(warning ? { warning } : {}) };
  }

  async function startSupervisor(root, ctx, { model, kind } = {}) {
    return withLaunchLock(root, async () => {
      const prev = (await readLedger(root)).supervisor;
      if (prev && agentView(prev, ctx.panes, now()).alive) return { status: 'already', message: '監督はすでに動いています', supervisor: agentView(prev, ctx.panes, now()) };
      return launchSupervisor(root, ctx, { resume: false, model, kind });
    });
  }
  async function resumeSupervisor(root, ctx) {
    return withLaunchLock(root, async () => {
      const prev = (await readLedger(root)).supervisor;
      if (!prev?.sessionId) throw fail(prev ? '会話 ID をまだ取得できていないため再開できません。「監督を起動」を使ってください' : '再開できる監督の記録がありません。「監督を起動」を使ってください');
      if (agentView(prev, ctx.panes, now()).alive) return { status: 'already', message: '監督はすでに動いています', supervisor: agentView(prev, ctx.panes, now()) };
      return launchSupervisor(root, ctx, { resume: true });
    });
  }

  async function aliveSupervisor(root, ctx) {
    const sup = (await readLedger(root)).supervisor;
    const view = agentView(sup, ctx.panes, now());
    if (!view?.alive) throw fail('監督が動いていません。先に監督を起動（または再開）してください');
    return { entry: sup, view };
  }

  async function promptSupervisor(root, ctx, { text }) {
    const { entry } = await aliveSupervisor(root, ctx);
    const soda = makeSoda(root);
    await sendPrompt(soda, root, entry, text);
    await logEvent(root, { from: 'user', kind: 'instruction', message: text });
    return { status: 'sent' };
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

  async function launchWorker(root, ctx, { slug, resume, instruction, model, kind: wantKind }) {
    const { entry: sup } = await aliveSupervisor(root, ctx);
    const soda = makeSoda(root);
    const settings = await loadSettings(root);
    const ledger = await readLedger(root);
    const prev = ledger.workers[slug];
    const kind = resume ? prev.kind : wantKind || settings.workerKind;
    const sessionId = resume ? prev.sessionId : kind === 'claude' ? uuid() : '';
    const name = workerName(root, slug);
    const useModel = model || settings.workerModel;
    const base = { slug, name, kind, sessionId, workspaceId: ctx.workspaceId, model: useModel, startedAt: resume && prev.startedAt ? prev.startedAt : iso(now()), resumedAt: resume ? iso(now()) : null, lastReport: resume ? prev.lastReport : null, linkErrors: [] };
    let tab, agent;
    try {
      tab = await newTerminalTab(soda, ctx.workspaceId, slug);
      agent = await startAgent(soda, { name, kind, paneId: tab.paneId, args: launchArgs(settings, kind, sessionId, resume, useModel, root) });
    } catch (e) {
      const entry = cleanAgent({ ...base, tabId: tab?.tabId ?? '', paneId: tab?.paneId ?? '' }, slug);
      await recordAfterFailure(root, `担当 ${slug}`, slug, entry, e, resume).catch(() => {});
      if (e.code === 'agent_not_ready') return { status: 'blocked', slug, message: 'エージェントが確認（信頼・承認など）を待っています。担当の端末で答えてください。', worker: agentView({ ...entry, status: 'blocked' }, ctx.panes, now()) };
      throw e;
    }
    const entry = cleanAgent({ ...base, tabId: tab.tabId, paneId: tab.paneId, status: 'running', error: null }, slug);
    await updateLedger(root, (l) => {
      l.workers[slug] = entry;
      pushLog(l, now(), { from: 'app', slug, kind: 'event', message: resume ? `担当 ${slug} を再開しました（${name}）` : `担当 ${slug} を起動しました（${name}）` });
    });
    const warnings = [];
    try {
      if (resume) await sendPrompt(soda, root, entry, workerResumeNote(slug), agent);
      else {
        const file = await writePromptFile(root, `worker-${slug}`, workerPrompt({ root, tabId: ctx.tabId, slug, supervisorName: sup.name, instruction }));
        await sendPrompt(soda, root, entry, readFileInstruction(file, `作業 ${slug} の担当`), agent);
      }
    } catch (e) { warnings.push(`役割の送信に失敗しました: ${e.message}`); }
    if (!sessionId) await captureSessions(root).catch(() => {});
    const linkErrors = await linkWorker(soda, tab.paneId, sup.paneId, slug);
    warnings.push(...linkErrors);
    if (warnings.length) {
      entry.linkErrors = linkErrors.slice(0, 5);
      await updateLedger(root, (l) => {
        if (l.workers[slug]?.paneId === entry.paneId) l.workers[slug].linkErrors = entry.linkErrors;
        for (const w of warnings) pushLog(l, now(), { from: 'app', slug, kind: 'error', message: w });
      });
    }
    return { status: resume ? 'resumed' : 'started', slug, worker: agentView((await readLedger(root)).workers[slug] ?? entry, [...ctx.panes, { id: tab.paneId, agent: kind, agentState: 'idle' }], now()), ...(warnings.length ? { warnings } : {}) };
  }

  async function startWorker(root, ctx, { slug, instruction, model, kind }) {
    return withLaunchLock(root, async () => {
      const prev = (await readLedger(root)).workers[slug];
      if (prev) {
        const view = agentView(prev, ctx.panes, now());
        if (view.alive) throw fail(`作業 ${slug} の担当はすでに動いています`);
        if (prev.status !== 'failed' && prev.sessionId) throw fail(`作業 ${slug} の担当は止まっています。再開（worker-resume）を使ってください`);
      }
      return launchWorker(root, ctx, { slug, resume: false, instruction, model, kind });
    });
  }
  async function resumeWorker(root, ctx, { slug }) {
    return withLaunchLock(root, async () => {
      const prev = (await readLedger(root)).workers[slug];
      if (!prev?.sessionId) throw fail(prev ? `作業 ${slug} の会話 ID をまだ取得できていないため再開できません。起動（worker-start）を使ってください` : `作業 ${slug} の担当の記録がありません。起動（worker-start）を使ってください`);
      if (agentView(prev, ctx.panes, now()).alive) return { status: 'already', slug, message: '担当はすでに動いています', worker: agentView(prev, ctx.panes, now()) };
      return launchWorker(root, ctx, { slug, resume: true });
    });
  }

  async function promptWorker(root, ctx, { slug, text, source = 'ui' }) {
    const ledger = await readLedger(root);
    const w = ledger.workers[slug];
    if (!w) throw fail(`作業 ${slug} の担当の記録がありません`);
    if (!agentView(w, ctx.panes, now()).alive) throw fail(`作業 ${slug} の担当は動いていません。再開（worker-resume）を使ってください`);
    await sendPrompt(makeSoda(root), root, w, text);
    await logEvent(root, { from: source === 'ui' ? 'user' : 'supervisor', slug, kind: 'instruction', message: text });
    return { status: 'sent', slug };
  }

  /** 担当からの報告。`question`・`failed`・`blocked` は監督へも中継する（失敗はログに残すだけで再試行しない）。 */
  async function reportWorker(root, ctx, { slug, status, message }) {
    const found = await updateLedger(root, (l) => {
      const w = l.workers[slug];
      if (!w) return false;
      w.lastReport = { status, message: clip(message, LEDGER_LIMITS.message), at: iso(now()) };
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
    const [ledger, settings] = await Promise.all([readLedger(root), loadSettings(root)]);
    return {
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
    await relatedTarget(root, ctx, slug, paneId);
    const soda = makeSoda(root);
    const agent = (await soda(['agent', 'get', paneId])).agent;
    if (!agent || agent.paneId !== paneId) throw fail('エージェントが見つかりません（入れ替わった可能性があります）');
    const args = ['agent', 'prompt', paneId, guardDash(text)];
    if (agent.name && agent.instanceId && agent.tabId) args.push('--expect', JSON.stringify({ paneId, instanceId: agent.instanceId, tabId: agent.tabId, projectDir: root, name: agent.name }));
    await soda(args, { timeout: 60000 });
    await logEvent(root, { from: source === 'ui' ? 'user' : 'supervisor', slug, kind: 'instruction', message: `[関連 ${paneId.slice(0, 8)}] ${text}` });
    return { status: 'sent', slug, paneId };
  }
  async function readRelated(root, ctx, { slug, paneId, lines = 60 }) {
    await relatedTarget(root, ctx, slug, paneId);
    const res = await makeSoda(root)(['agent', 'read', paneId, '--lines', String(lines)], { timeout: 20000, rawMax: 40000 });
    return { slug, paneId, text: String(res.raw ?? res.text ?? '') };
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
      if (pane?.agent?.kind === e.kind && pane.agent.name === e.name && ref?.kind === e.kind && UUID_RE.test(ref.sessionId ?? '')) found.push({ slug, paneId: e.paneId, name: e.name, id: ref.sessionId });
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
    return prev?.sessionId && prev.status !== 'failed' ? resumeSupervisor(root, ctx) : startSupervisor(root, ctx);
  }

  return {
    startSupervisor, resumeSupervisor, promptSupervisor, startWorker, resumeWorker, promptWorker, reportWorker,
    report, overview, logList, autoStart, captureSessions, needsCapture, note: logEvent, related, registerRelated, promptRelated, readRelated, delegate: (root, ctx, slug) => promptSupervisor(root, ctx, { text: delegateInstruction(slug) }),
  };
}
