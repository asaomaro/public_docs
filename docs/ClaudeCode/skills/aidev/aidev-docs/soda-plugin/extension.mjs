#!/usr/bin/env node
// aidev プラグインの拡張本体。Sodashitsu と NDJSON（標準入出力）でやり取りする。
// 画面の組み立ては ui.mjs、操作は operations.mjs、エージェントは agents.mjs、`.aidev` の読み取りは aidev-data.mjs。
import { createInterface } from 'node:readline';
import { createHash } from 'node:crypto';
import * as aidevData from './aidev-data.mjs';
import { createAgents, saveSettings } from './agents.mjs';
import { OPERATIONS, buildModel, createOperations } from './operations.mjs';
import { appHtml, bandHtml, chunkItems, chunkText, staticHtml, stripControl, terminalMarkdown, uiModel } from './ui.mjs';

const NAME = 'aidev';
const VIEW_ID = 'progress';
const POLL_MS = 3000;
const SEND_GAP_MS = 60;
const CAPTURE_MS = 8000;
const CALL_DEADLINE_MS = 25000; // `sodactl plugin call` の応答待ちは 30 秒。起動系はそれより前に「続けています」と返す
const AUTO_START_AFTER_MS = 8000;
const RESTORE_WAIT_MS = 40000;
const LAUNCH_OPS = new Set(['supervisor-start', 'supervisor-resume', 'worker-start', 'worker-resume']);

const agents = createAgents();
const operations = createOperations({ agents });

let key = 'user:aidev';
let scriptEnabled = false;
let panes = [];
let seq = 0;
let closing = false;
let queue = Promise.resolve();
let queued = false, queuedForce = false;
let lastFeatures = 0;
const pending = new Map();
const roots = new Map();     // root -> { sig, overview, firstSeen, autoTried, detailSig }
const shown = new Map();     // `${paneId}|${name}` -> 表示の署名（同じなら display.set しない）
const active = new Map();    // `${paneId}|${name}` -> { paneId, name }（出している面。消えたら閉じる）
const ready = new Set();     // スクリプトの画面が起動した pane
const dismissed = new Set(); // 利用者が閉じた面
const sent = new Map();      // paneId -> 最後に送った JSON（変わったときだけ送る）
const selected = new Map();  // paneId -> 選んでいる作業
const reported = new Set();

const log = (e) => process.stderr.write(String(e?.message ?? e).slice(0, 1000) + '\n');
const logOnce = (e) => { const m = String(e?.message ?? e); if (!reported.has(m)) { reported.add(m); if (reported.size > 100) reported.clear(); log(m); } };

function call(method, params) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('Sodashitsu の応答がありません')); }, 15000);
    pending.set(id, { resolve, reject, timer });
    process.stdout.write(JSON.stringify({ id, method, params }) + '\n');
  });
}

// ---- pane と対象 ----------------------------------------------------------------------------------

const isAnchor = (p) => p.plugin?.extensionKey === key && p.plugin.display === NAME && !!p.projectDir;
const ownViews = (p) => (p.views ?? []).filter((v) => v.extensionKey === key && v.viewId === VIEW_ID);
const isOurs = (p) => !!p.projectDir && (isAnchor(p) || ownViews(p).length > 0);

/** 操作の対象（`app.call` の `target`・画面の操作の paneId）を `ext.panes` と照合して、その PJ を使う。 */
function contextFor(target) {
  const pane = panes.find((p) => p.id === target?.paneId && (target.tabId === undefined || p.tabId === target.tabId) && (target.workspaceId === undefined || p.workspaceId === target.workspaceId));
  if (!pane || !isOurs(pane)) throw Object.assign(new Error('対象の aidev アプリ（またはビュー）が見つかりません'), { expected: true });
  return { root: pane.projectDir, tabId: pane.tabId, workspaceId: pane.workspaceId, paneId: pane.id, panes };
}
const publicError = (e) => String(e?.message ?? '操作に失敗しました').slice(0, 500);

// ---- 表示 ---------------------------------------------------------------------------------------

async function setDisplay(paneId, name, params, signature) {
  const id = `${paneId}|${name}`;
  active.set(id, { paneId, name });
  if (dismissed.has(id) || shown.get(id) === signature) return false;
  try {
    await call('display.set', { paneId, name, ...params });
    shown.set(id, signature);
    return true;
  } catch (e) { logOnce(e); return false; }
}
const sha = (s) => createHash('sha1').update(s).digest('hex');

// `display.send` は pane ごとに毎秒 20（バースト 20）まで。大きな文書の小分けで超えないよう、60 ms 以上あけて送る。
const lastSend = new Map();
async function send(paneId, data) {
  const slot = Math.max(Date.now(), (lastSend.get(paneId) ?? 0) + SEND_GAP_MS);
  lastSend.set(paneId, slot);
  if (slot > Date.now()) await new Promise((r) => setTimeout(r, slot - Date.now()));
  try { await call('display.send', { paneId, name: NAME, data }); return true; } catch (e) { logOnce(e); ready.delete(paneId); return false; }
}
async function sendList(paneId, name, listKey, items) {
  const parts = chunkItems(items);
  const gen = ++seq;
  for (let i = 0; i < parts.length; i++) if (!await send(paneId, { type: 'list', name, key: listKey, gen, part: i, parts: parts.length, items: parts[i] })) return false;
  return true;
}
async function sendDetail(pane, slug) {
  const detail = await aidevData.loadWorkDetail(pane.projectDir, slug);
  const { tasksList, events, ...core } = detail;
  const small = Buffer.byteLength(JSON.stringify(core)) > 55000 ? { ...core, values: {} } : core;
  await send(pane.id, { type: 'detail', detail: small });
  await sendList(pane.id, 'tasks', slug, tasksList);
  await sendList(pane.id, 'events', slug, events);
}
async function sendDoc(pane, slug, name) {
  const doc = await aidevData.loadDoc(pane.projectDir, slug, name);
  const parts = chunkText(stripControl(doc.text));
  const gen = ++seq;
  for (let i = 0; i < parts.length; i++) await send(pane.id, { type: 'doc', slug, name, gen, part: i, parts: parts.length, text: parts[i], truncated: doc.truncated });
}
async function notify(paneId, level, text) {
  if (ready.has(paneId)) await send(paneId, { type: 'notice', level, text });
}

async function pushData(pane, model, rec, force) {
  const ui = uiModel(model);
  let stateJson = JSON.stringify(ui.state);
  let state = ui.state;
  if (Buffer.byteLength(stateJson) > 58000) { state = { ...state, log: state.log.slice(0, 8) }; stateJson = JSON.stringify(state); }
  const memo = force ? {} : sent.get(pane.id) ?? {};
  if (memo.state !== stateJson) { if (!await send(pane.id, { type: 'state', state })) return; memo.state = stateJson; }
  for (const [name, items] of Object.entries(ui.lists)) {
    const json = JSON.stringify(items);
    if (memo[name] !== json) { if (!await sendList(pane.id, name, '', items)) return; memo[name] = json; }
  }
  const slug = selected.get(pane.id);
  if (slug) {
    const sig = `${rec.sig}|${slug}`;
    if (memo.detail !== sig) {
      memo.detail = sig;
      try { await sendDetail(pane, slug); } catch (e) { await send(pane.id, { type: 'notice', level: 'warn', text: publicError(e) }); }
    }
  }
  sent.set(pane.id, memo);
}

function viewPlacement(v) {
  const placement = String(v.placement ?? 'right');
  return placement.startsWith('band-') ? { kind: 'band', edge: placement.slice(5) } : { kind: 'panel', dock: placement, size: 360, collapsed: false };
}

async function refreshRoot(root, force) {
  let rec = roots.get(root);
  if (!rec) { rec = { firstSeen: Date.now(), autoTried: false }; roots.set(root, rec); }
  const sig = await aidevData.dataSignature(root);
  if (force || rec.sig !== sig || !rec.overview) { rec.overview = await aidevData.loadOverview(root, { sig, onUpdate: () => schedule(true) }); rec.sig = sig; }
  rec.model = await buildModel(root, panes, { agents, overview: rec.overview });
  return rec;
}

async function maybeAutoStart(root, rec, anchor) {
  if (rec.autoTried || closing || !process.env.SODA_SERVER_URL) return;
  const elapsed = Date.now() - rec.firstSeen;
  if (elapsed < AUTO_START_AFTER_MS) return;
  const sup = rec.model.supervisor;
  // サーバの再起動で会話が復元されている途中かもしれない（pane は在るがエージェントがまだ検出されない）間は待つ
  if (sup && !sup.alive && panes.some((p) => p.id === sup.paneId) && elapsed < RESTORE_WAIT_MS) return;
  rec.autoTried = true;
  if (sup?.alive || rec.model.settings.autoStartSupervisor === false) return;
  try {
    const result = await agents.autoStart(root, contextFor({ paneId: anchor.id }));
    if (result?.warning || result?.status === 'blocked') await notify(anchor.id, 'warn', result.warning ?? result.message);
  } catch (e) {
    logOnce(e);
    await agents.note(root, { from: 'app', kind: 'error', message: `監督の自動起動に失敗しました: ${publicError(e)}` }).catch(() => {});
  }
  schedule(true);
}

async function reconcile(force) {
  const wanted = new Set();
  const keep = (paneId, name) => wanted.add(`${paneId}|${name}`);
  const byRoot = new Map();
  for (const p of panes) if (isOurs(p)) { if (!byRoot.has(p.projectDir)) byRoot.set(p.projectDir, []); byRoot.get(p.projectDir).push(p); }
  for (const root of [...roots.keys()]) if (!byRoot.has(root)) roots.delete(root);

  for (const [root, group] of byRoot) {
    let rec;
    try { rec = await refreshRoot(root, force); } catch (e) {
      logOnce(e);
      // 読めなかった間は、出している面を閉じない
      for (const [id, face] of active) if (group.some((p) => p.id === face.paneId)) wanted.add(id);
      continue;
    }
    const model = rec.model;
    // 会話 ID を先に決められない種類（Codex）は、起動後に払い出された ID を取り込む
    if (Date.now() - (rec.lastCapture ?? 0) > CAPTURE_MS && [model.supervisor, ...model.workers].some((a) => a?.sessionPending && a.recordedStatus !== 'failed')) {
      rec.lastCapture = Date.now();
      try { if (await agents.captureSessions(root)) schedule(true); } catch (e) { logOnce(e); }
    }
    for (const pane of group) {
      try {
        if (isAnchor(pane)) {
          const useScript = scriptEnabled;
          keep(pane.id, NAME);
          const content = useScript ? appHtml() : staticHtml(model, '設定「スクリプトが動く表示」が無効なため、読むだけの画面です。操作は sodactl plugin call で行えます。');
          const sig = useScript ? 'script' : `html|${sha(content)}`;
          const changed = await setDisplay(pane.id, NAME, { title: 'aidev', kind: 'panel', format: useScript ? 'script-html' : 'html', content, dock: 'right', size: 360 }, sig);
          if (changed) { ready.delete(pane.id); sent.delete(pane.id); }
          if (useScript && ready.has(pane.id)) await pushData(pane, model, rec, force);
          if (pane.plugin.terminalDisplay) {
            keep(pane.id, pane.plugin.terminalDisplay);
            const md = terminalMarkdown(model);
            await setDisplay(pane.id, pane.plugin.terminalDisplay, { title: 'aidev', kind: 'panel', format: 'markdown', content: md, dock: 'right', size: 360 }, sha(md));
          }
          void maybeAutoStart(root, rec, pane).catch(logOnce);
        }
        for (const v of ownViews(pane)) {
          const paneId = v.paneId ?? pane.id;
          const place = viewPlacement(v);
          if (v.display) {
            keep(paneId, v.display);
            const html = bandHtml(model);
            await setDisplay(paneId, v.display, { title: 'aidev の進捗', format: 'html', content: html, ...place }, `${sha(html)}|${v.placement}`);
          }
          if (v.terminalDisplay) {
            keep(paneId, v.terminalDisplay);
            const md = terminalMarkdown(model);
            await setDisplay(paneId, v.terminalDisplay, { title: 'aidev の進捗', format: 'markdown', content: md, ...place }, `${sha(md)}|${v.placement}`);
          }
        }
      } catch (e) {
        logOnce(e);
        for (const [id, face] of active) if (face.paneId === pane.id) wanted.add(id);
      }
    }
  }
  for (const [id, face] of [...active]) {
    if (wanted.has(id)) continue;
    active.delete(id); shown.delete(id); dismissed.delete(id);
    if (face.name === NAME) { ready.delete(face.paneId); sent.delete(face.paneId); selected.delete(face.paneId); lastSend.delete(face.paneId); }
    await call('display.close', { paneId: face.paneId, name: face.name }).catch(() => {});
  }
}

function schedule(force = false) {
  if (force) queuedForce = true;
  if (queued) return;
  queued = true;
  queue = queue.then(async () => {
    queued = false;
    const f = queuedForce; queuedForce = false;
    if (Date.now() - lastFeatures > 15000) {
      lastFeatures = Date.now();
      try { const r = await call('ext.features', {}); if (typeof r?.display?.scriptEnabled === 'boolean') scriptEnabled = r.display.scriptEnabled; } catch (e) { logOnce(e); }
    }
    await reconcile(f);
  }).catch(logOnce);
}

// ---- 画面の操作 / CLI の操作 ----------------------------------------------------------------------

const DONE_TEXT = { started: '起動しました', resumed: '再開しました', sent: '送りました', recorded: '記録しました' };
function resultText(r) {
  if (!r || typeof r !== 'object') return '完了しました';
  const extra = [r.warning, ...(r.warnings ?? [])].filter(Boolean).join(' / ');
  return `${r.message ?? DONE_TEXT[r.status] ?? '完了しました'}${extra ? `（注意: ${extra}）` : ''}`;
}

async function onAction(msg) {
  const pane = panes.find((p) => p.id === msg.paneId && isAnchor(p));
  if (!pane || msg.name !== NAME) return;
  const data = msg.data ?? {};
  const ctx = contextFor({ paneId: pane.id });
  const run = (name, params) => operations.call(name, params, ctx, 'ui');
  try {
    switch (msg.action) {
      case 'ready': ready.add(pane.id); sent.delete(pane.id); schedule(true); return;
      case 'refresh': schedule(true); await notify(pane.id, 'info', '読み直しました'); return;
      case 'select': { await aidevData.loadWorkDetail(pane.projectDir, String(data.slug ?? '')); selected.set(pane.id, String(data.slug)); sent.set(pane.id, { ...(sent.get(pane.id) ?? {}), detail: undefined }); schedule(); return; }
      case 'doc': await sendDoc(pane, String(data.slug ?? ''), String(data.name ?? '')); return;
      case 'settings-save': {
        await saveSettings(pane.projectDir, {
          supervisorModel: String(data.supervisorModel ?? ''), workerModel: String(data.workerModel ?? ''),
          permissionMode: String(data.permissionMode ?? ''), autoStartSupervisor: data.autoStartSupervisor === 'true',
          supervisorKind: String(data.supervisorKind ?? 'claude'), workerKind: String(data.workerKind ?? 'claude'),
          codexPermission: String(data.codexPermission ?? ''),
        });
        schedule(true); await notify(pane.id, 'info', '設定を保存しました'); return;
      }
      case 'delegate': { const r = await operations.delegate(ctx, String(data.slug ?? '')); await notify(pane.id, 'info', resultText(r)); schedule(true); return; }
      case 'supervisor-start': case 'supervisor-resume': case 'supervisor-prompt':
      case 'worker-start': case 'worker-resume': case 'worker-prompt': {
        const params = { ...data };
        if (msg.action === 'supervisor-start' || msg.action === 'supervisor-resume') delete params.model;
        const r = await run(msg.action, msg.action === 'supervisor-resume' ? {} : params);
        await notify(pane.id, r?.status === 'blocked' ? 'warn' : 'info', resultText(r));
        schedule(true);
        return;
      }
      default: return;
    }
  } catch (e) {
    if (!e?.expected) logOnce(e);
    await agents.note(pane.projectDir, { from: 'app', kind: 'error', message: `${msg.action}: ${publicError(e)}` }).catch(() => {});
    await notify(pane.id, 'error', publicError(e));
    schedule(true);
  }
}

/** 期限までに終わらなければ「続けています」を返す（処理は止めない。後で失敗したら onLate に渡す）。 */
function withDeadline(promise, ms, onLate) {
  let late = false, timer;
  const deadline = new Promise((resolve) => {
    timer = setTimeout(() => { late = true; resolve({ status: 'pending', message: '処理を続けています。結果は agents-list か log-list で確かめてください（自動では再試行しません）' }); }, ms);
  });
  promise.then(() => clearTimeout(timer), (e) => { clearTimeout(timer); if (late) onLate(e); });
  return Promise.race([promise, deadline]);
}

async function onCall(msg) {
  const reply = (body) => call('app.result', { callId: msg.callId, ...body }).catch(() => undefined);
  let ctx;
  try {
    ctx = contextFor(msg.target);
    const run = operations.call(msg.operation, msg.params ?? {}, ctx, 'cli');
    const result = LAUNCH_OPS.has(msg.operation)
      ? await withDeadline(run, CALL_DEADLINE_MS, (e) => agents.note(ctx.root, { from: 'app', kind: 'error', message: `${msg.operation}: ${publicError(e)}` }).catch(() => {}))
      : await run;
    schedule(true);
    await reply({ ok: true, result });
  } catch (e) {
    if (!e?.expected) logOnce(e);
    await reply({ ok: false, error: publicError(e) });
    schedule(true);
  }
}

// ---- 入力 ---------------------------------------------------------------------------------------

const input = createInterface({ input: process.stdin });
input.on('line', (line) => {
  let msg;
  try { msg = JSON.parse(line); } catch { return; }
  switch (msg.type) {
    case 'ext.result': {
      const p = pending.get(msg.id);
      if (p) { pending.delete(msg.id); clearTimeout(p.timer); msg.ok ? p.resolve(msg.result) : p.reject(new Error(msg.error?.message ?? '表示を更新できません')); }
      return;
    }
    case 'ext.hello':
      scriptEnabled = msg.display?.scriptEnabled === true;
      key = msg.extension?.scope === 'project' ? `project:${createHash('sha256').update(String(msg.extension.root ?? '')).digest('hex')}:${msg.extension.id}` : `user:${msg.extension?.id ?? 'aidev'}`;
      void call('app.register', { operations: OPERATIONS }).catch(logOnce);
      return;
    case 'ext.panes': panes = Array.isArray(msg.panes) ? msg.panes : []; schedule(); return;
    case 'app.call': void onCall(msg); return;
    case 'display.action': void onAction(msg); return;
    case 'display.closed': {
      const id = `${msg.paneId}|${msg.name}`;
      shown.delete(id);
      if (msg.name === NAME) { ready.delete(msg.paneId); sent.delete(msg.paneId); }
      if (msg.reason === 'dismissed') dismissed.add(id);
      if (msg.reason === 'script_disabled') scriptEnabled = false;
      schedule();
      return;
    }
    default:
  }
});
const poll = setInterval(() => schedule(), POLL_MS);
function stop() {
  if (closing) return;
  closing = true;
  clearInterval(poll);
  for (const p of pending.values()) clearTimeout(p.timer);
  input.close();
  process.exit(0);
}
input.on('close', stop);
process.on('SIGTERM', stop);
process.on('SIGINT', stop);
