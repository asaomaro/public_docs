import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lstat, mkdir, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import * as ag from './agents.mjs';
import { tempDir } from './testkit.mjs';

const NOW = new Date('2026-10-15T00:00:00.000Z');
const uuids = () => { let n = 0; return () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`; };
const sodaErr = (code, message) => new ag.SodaError(code, message);

/** sodactl の代役。呼び出しを記録し、コマンドごとに返す値を決める。 */
const ALL_INSTALLED = { autoResumeEnabled: true, agents: Object.fromEntries(['claude', 'codex', 'copilot', 'bob'].map((k) => [k, { cliDetected: true, installed: true }])) };
function fakeSoda({ onCall, integrations = ALL_INSTALLED } = {}) {
  const calls = [];
  const agentsByPane = new Map(); // paneId -> { name, kind, tabId, instanceId }
  const known = [{ id: 'term-1', tabId: 'tab-app' }, { id: 'anchor', tabId: 'tab-app', virtual: true }];
  let tabs = 0, splits = 0, instances = 0;
  const soda = async (args, opts) => {
    calls.push({ args, opts });
    if (onCall) { const r = await onCall(args, opts); if (r !== undefined) return r; }
    const key = args.slice(0, 2).join(' ');
    switch (key) {
      case 'snapshot': return { panes: known.map((p) => ({ ...p, virtual: !!p.virtual, status: 'running', agent: agentsByPane.has(p.id) ? { kind: agentsByPane.get(p.id).kind, name: agentsByPane.get(p.id).name } : null })) };
      case 'pane split': {
        splits++;
        const base = known.find((p) => p.id === args[2]);
        const id = splits === 1 ? 'term-split' : `term-split-${splits}`;
        known.push({ id, tabId: base?.tabId ?? 'tab-app' });
        return { pane: { id, tabId: base?.tabId ?? 'tab-app', virtual: false } };
      }
      case 'tab create': { tabs++; known.push({ id: `pane-w${tabs}`, tabId: `tab-w${tabs}` }); return { tab: { id: `tab-w${tabs}`, workspaceId: 'ws1' }, pane: { id: `pane-w${tabs}`, tabId: `tab-w${tabs}`, virtual: false } }; }
      case 'pane close': { const i = known.findIndex((p) => p.id === args[2]); if (i >= 0) known.splice(i, 1); agentsByPane.delete(args[2]); return {}; }
      case 'agent start': {
        const paneId = args[args.indexOf('--pane') + 1];
        const tabId = known.find((p) => p.id === paneId)?.tabId ?? 'tab-app';
        const kind = args[args.indexOf('--kind') + 1];
        agentsByPane.set(paneId, { name: args[2], kind, tabId, instanceId: `inst-${++instances}` });
        return { agent: { name: args[2], paneId, ...agentsByPane.get(paneId) } };
      }
      case 'agent get': {
        const a = agentsByPane.get(args[2]);
        if (!a) throw new ag.SodaError('agent_not_found', '居ません');
        return { agent: { paneId: args[2], ...a } };
      }
      case 'agent rename': { const a = agentsByPane.get(args[2]); a.name = args[3]; return { agent: { paneId: args[2], ...a } }; }
      case 'agent prompt': return { agent: {} };
      case 'agent integrations': {
        if (integrations === 'unsupported') throw new ag.SodaError('not_found', 'このサーバは agent integrations に対応していません');
        return integrations;
      }
      case 'graph link': return { link: { id: 'link' } };
      default: throw new Error(`想定外: ${args.join(' ')}`);
    }
  };
  return { soda, calls, known, of: (a, b) => calls.filter((c) => c.args[0] === a && (b === undefined || c.args[1] === b)) };
}
const basePanes = () => [
  { id: 'anchor', tabId: 'tab-app', workspaceId: 'ws1', virtual: true, projectDir: '/x', plugin: { extensionKey: 'user:aidev', display: 'aidev' }, agent: null },
  { id: 'term-1', tabId: 'tab-app', workspaceId: 'ws1', agent: null },
];
const aliveAgent = (panes, id, state = 'idle') => { const p = panes.find((x) => x.id === id); if (p) { p.agent = 'claude'; p.agentState = state; } else panes.push({ id, tabId: 't', agent: 'claude', agentState: state }); };

async function setup(options = {}) {
  const t = await tempDir();
  const fake = fakeSoda(options);
  const agents = ag.createAgents({ makeSoda: () => fake.soda, now: () => NOW, uuid: uuids() });
  const panes = basePanes();
  const ctx = { tabId: 'tab-app', workspaceId: 'ws1', paneId: 'anchor', panes };
  return { ...t, fake, agents, panes, ctx, root: t.dir };
}

test('台帳: .gitignore（*）・原子的な書き込み・ログの上限・項目の上限', async () => {
  const { root, cleanup } = await setup();
  try {
    await ag.updateLedger(root, (l) => ag.pushLog(l, NOW, { from: 'app', kind: 'event', message: 'x'.repeat(20000) }));
    const dir = join(root, '.soda/aidev');
    assert.equal(await readFile(join(dir, '.gitignore'), 'utf8'), '*\n');
    assert.deepEqual((await readdir(dir)).sort(), ['.gitignore', 'agents.json']);
    const l = await ag.readLedger(root);
    assert.equal(l.log[0].message.length, 8192);
    await ag.updateLedger(root, (led) => { for (let i = 0; i < 350; i++) ag.pushLog(led, NOW, { from: 'app', kind: 'event', message: `m${i}` }); });
    const after = await ag.readLedger(root);
    assert.equal(after.log.length, 300);
    assert.equal(after.log.at(-1).message, 'm349');
    assert.equal(after.version, 1);
    assert.deepEqual((await readdir(dir)).sort(), ['.gitignore', 'agents.json'], '一時ファイルが残らない');
    assert.equal(((await lstat(join(dir, 'agents.json'))).mode & 0o077), 0, '持ち主だけが読み書きできる');
  } finally { await cleanup(); }
});

test('台帳: 同時の更新が取りこぼされない・壊れたファイルは退避して空から始める', async () => {
  const { root, cleanup } = await setup();
  try {
    await Promise.all(Array.from({ length: 20 }, (_, i) => ag.updateLedger(root, (l) => ag.pushLog(l, NOW, { from: 'app', kind: 'event', message: `n${i}` }))));
    assert.equal((await ag.readLedger(root)).log.length, 20);
    await writeFile(join(root, '.soda/aidev/agents.json'), '{ broken');
    const l = await ag.readLedger(root);
    assert.deepEqual(l, ag.emptyLedger());
    assert.ok((await readdir(join(root, '.soda/aidev'))).includes('agents.json.corrupt'));
  } finally { await cleanup(); }
});

test('台帳: 読み込み時に形を直す（不正な slug・セッション ID・モデル名を捨てる）', () => {
  const l = ag.cleanLedger({
    supervisor: { name: 'aidev-sup-1', sessionId: 'not-a-uuid', model: 'bad model!', status: 'weird', paneId: 'p' },
    workers: { 'ok-1': { name: 'w', sessionId: '00000000-0000-4000-8000-000000000001', status: 'running' }, '../evil': { name: 'x' }, Upper: { name: 'y' } },
    log: [{ at: 'a', from: 'hacker', kind: 'report', message: 'm' }, 5],
  });
  assert.equal(l.supervisor.sessionId, '');
  assert.equal(l.supervisor.model, '');
  assert.equal(l.supervisor.status, 'stopped');
  assert.deepEqual(Object.keys(l.workers).sort(), ['Upper', 'ok-1'], '英大文字も slug として受ける。パスの成分は捨てる');
  assert.equal(l.log.length, 1);
  assert.equal(l.log[0].from, 'app');
});

test('台帳: .soda がシンボリックリンクなら使わない', async () => {
  const { root, cleanup } = await setup();
  const out = await tempDir();
  try {
    await symlink(out.dir, join(root, '.soda'));
    await assert.rejects(ag.readLedger(root), /シンボリックリンク/);
    await assert.rejects(ag.updateLedger(root, () => {}), /シンボリックリンク/);
    assert.deepEqual(await readdir(out.dir), [], '外には何も書かない');
  } finally { await cleanup(); await out.cleanup(); }
});

test('設定: モデル名の書式・権限のモードの選択肢・未知のキー', async () => {
  const { root, cleanup } = await setup();
  try {
    assert.deepEqual(await ag.loadSettings(root), { execution: 'server', supervisorModel: '', workerModel: '', permissionMode: '', autoStartSupervisor: true, supervisorKind: 'claude', workerKind: 'claude', codexPermission: '', exitOnDone: true });
    const saved = await ag.saveSettings(root, { supervisorModel: 'claude-opus-4-1', workerModel: 'sonnet[1m]', permissionMode: 'acceptEdits', autoStartSupervisor: false });
    assert.equal(saved.supervisorModel, 'claude-opus-4-1');
    assert.deepEqual(await ag.loadSettings(root), saved);
    for (const bad of [{ supervisorModel: 'a b' }, { supervisorModel: '--flag' + ' x' }, { supervisorModel: 'x'.repeat(65) }, { permissionMode: 'bypassPermissions' }, { autoStartSupervisor: 'yes' }, { extra: 1 }, { workerModel: 5 }]) {
      assert.throws(() => ag.normalizeSettings(bad), Error, JSON.stringify(bad));
    }
    assert.equal(ag.normalizeSettings({ supervisorModel: '' }).supervisorModel, '');
  } finally { await cleanup(); }
});

test('sodactl: SODA_PANE_ID・SODA_PANE_SOCKET を外し、--url は -- の手前、cwd は PJ', async () => {
  const seen = [];
  const run = async (cmd, argv, opts) => { seen.push({ cmd, argv, opts }); return { stdout: '{"ok":true}' }; };
  const soda = ag.sodaClient('/proj', { run, url: 'http://127.0.0.1:7780', env: { SODA_PANE_ID: 'p', soda_pane_socket: 's', KEEP: '1', SODACTL_URL: 'old' } });
  assert.deepEqual(await soda(['agent', 'start', 'n', '--kind', 'claude', '--', '--session-id', 'x']), { ok: true });
  assert.equal(seen[0].cmd, 'sodactl');
  assert.deepEqual(seen[0].argv, ['agent', 'start', 'n', '--kind', 'claude', '--url', 'http://127.0.0.1:7780', '--', '--session-id', 'x']);
  assert.equal(seen[0].opts.cwd, '/proj');
  assert.equal(seen[0].opts.env.SODA_PANE_ID, undefined);
  assert.equal(seen[0].opts.env.soda_pane_socket, undefined);
  assert.equal(seen[0].opts.env.KEEP, '1');
  assert.equal(seen[0].opts.env.SODACTL_URL, 'http://127.0.0.1:7780');
  await soda(['snapshot']);
  assert.deepEqual(seen[1].argv, ['snapshot', '--url', 'http://127.0.0.1:7780']);
  assert.throws(() => ag.sodaClient('/proj', { run, url: '' }), /SODA_SERVER_URL/);
});

test('sodactl: 失敗の code・message を読み、ログインが要るときは案内する', async () => {
  const fail = (stderr, extra = {}) => async () => { throw Object.assign(new Error('exit 1'), { stderr, ...extra }); };
  const mk = (run) => ag.sodaClient('/p', { run, url: 'http://x' });
  await assert.rejects(mk(fail('{"error":{"code":"agent_not_ready","message":"確認待ち"}}'))(['x']), (e) => e.code === 'agent_not_ready' && /確認待ち/.test(e.message));
  await assert.rejects(mk(fail('{"error":{"code":"unauthorized","message":"not logged in"}}'))(['x']), /sodactl login/);
  await assert.rejects(mk(fail('', { code: 'ENOENT' }))(['x']), (e) => e.code === 'sodactl_missing');
  await assert.rejects(mk(fail('', { killed: true }))(['x']), (e) => e.code === 'timeout' && /実行されたか/.test(e.message));
});

test('監督の起動: 空き pane → agent start --session-id → 役割ファイル → agent prompt --expect → 台帳', async () => {
  const { root, cleanup, fake, agents, ctx, panes } = await setup();
  try {
    await ag.saveSettings(root, { supervisorModel: 'sonnet', permissionMode: 'plan' });
    const r = await agents.startSupervisor(root, ctx, {});
    assert.equal(r.status, 'started');
    const name = ag.supervisorName(root);
    assert.match(name, /^aidev-sup-[0-9a-f]{6}$/);
    const start = fake.of('agent', 'start')[0].args;
    assert.deepEqual(start, ['agent', 'start', name, '--kind', 'claude', '--pane', 'term-1', '--timeout', '60000', '--', '--session-id', '00000000-0000-4000-8000-000000000001', '--model', 'sonnet', '--permission-mode', 'plan']);
    assert.equal(fake.of('pane', 'split').length, 0, '空いている pane があれば分けない');
    const prompt = fake.of('agent', 'prompt')[0].args;
    assert.equal(prompt[2], name);
    assert.deepEqual(JSON.parse(prompt[prompt.indexOf('--expect') + 1]), { paneId: 'term-1', instanceId: 'inst-1', tabId: 'tab-app', projectDir: root, name }, '--expect は 5 項目が必須');
    const file = /"(.+supervisor-[^"]+\.md)"/.exec(prompt[3])[1];
    assert.ok(file.startsWith(join(root, '.soda/aidev/prompts')));
    const body = await readFile(file, 'utf8');
    assert.match(body, /plugin call aidev worker-start --tab tab-app/);
    assert.match(body, /自分では実装しない/);
    assert.ok(prompt[3].length < 300, '長い文面を直接貼らない');
    const led = await ag.readLedger(root);
    assert.equal(led.supervisor.sessionId, '00000000-0000-4000-8000-000000000001');
    assert.equal(led.supervisor.paneId, 'term-1');
    assert.equal(led.supervisor.status, 'running');
    assert.equal(led.supervisor.tabId, 'tab-app');
    assert.equal(led.log.at(-1).kind, 'event');
    // 生きていれば何もしない
    aliveAgent(panes, 'term-1');
    const again = await agents.startSupervisor(root, ctx, {});
    assert.equal(again.status, 'already');
    assert.equal(fake.of('agent', 'start').length, 1);
  } finally { await cleanup(); }
});

test('監督の起動: 空き pane が無ければ作業 pane を右へ分ける', async () => {
  const { root, cleanup, fake, agents, ctx } = await setup({
    onCall: (args) => (args[0] === 'snapshot' ? { panes: [{ id: 'busy', tabId: 'tab-app', virtual: false, status: 'running', agent: { kind: 'codex' } }] } : undefined),
  });
  try {
    await agents.startSupervisor(root, ctx, {});
    assert.deepEqual(fake.of('pane', 'split')[0].args, ['pane', 'split', 'busy', '--direction', 'right']);
    assert.equal(fake.of('agent', 'start')[0].args[fake.of('agent', 'start')[0].args.indexOf('--pane') + 1], 'term-split');
  } finally { await cleanup(); }
});

test('監督の起動: 承認待ち（agent_not_ready）は blocked として台帳に残す', async () => {
  const { root, cleanup, agents, ctx } = await setup({
    onCall: (args) => { if (args[0] === 'agent' && args[1] === 'start') throw sodaErr('agent_not_ready', '信頼の確認'); },
  });
  try {
    const r = await agents.startSupervisor(root, ctx, {});
    assert.equal(r.status, 'blocked');
    assert.match(r.message, /端末で答えてください/);
    const led = await ag.readLedger(root);
    assert.equal(led.supervisor.status, 'blocked');
    assert.equal(led.supervisor.sessionId, '00000000-0000-4000-8000-000000000001', '台帳は残す');
    assert.match(led.supervisor.error, /信頼/);
    assert.deepEqual(led.supervisor.pending, ['role'], '役割は未送信として残す');
  } finally { await cleanup(); }
});

test('監督の起動: エージェントが居る可能性がある失敗（kind 不一致など）は、新しい pane・UUID を台帳に残し、前の ID は previousSessions に残す', async () => {
  let fail = false;
  const { root, cleanup, agents, ctx } = await setup({
    onCall: (args) => { if (fail && args[0] === 'agent' && args[1] === 'start') throw sodaErr('agent_kind_mismatch', '別の種類が検出された'); },
  });
  try {
    await agents.startSupervisor(root, ctx, {});
    const first = (await ag.readLedger(root)).supervisor.sessionId;
    fail = true;
    await assert.rejects(agents.startSupervisor(root, ctx, {}), /再開できる会話があります/, '再開できる会話は、黙って上書きしない');
    await assert.rejects(agents.startSupervisor(root, ctx, { fresh: true }), /別の種類が検出された/);
    const sup = (await ag.readLedger(root)).supervisor;
    assert.notEqual(sup.sessionId, first, '新しい UUID を記録する（名前を握った孤児を作らない）');
    assert.equal(sup.status, 'failed');
    assert.deepEqual(sup.previousSessions.map((x) => x.sessionId), [first], '前の会話の ID は残る');
    assert.equal(ag.agentView(sup, [], NOW).resumable, false);
  } finally { await cleanup(); }
});

test('監督の起動: 起動に至らなかった失敗（pane が埋まっている等）では、前の記録を残して error だけ付ける', async () => {
  let fail = false;
  const { root, cleanup, agents, ctx } = await setup({
    onCall: (args) => { if (fail && args[0] === 'agent' && args[1] === 'start') throw sodaErr('agent_pane_busy', '前面が別のコマンド'); },
  });
  try {
    await agents.startSupervisor(root, ctx, {});
    const before = (await ag.readLedger(root)).supervisor;
    fail = true;
    await assert.rejects(agents.startSupervisor(root, ctx, { fresh: true }), /前面が別のコマンド/);
    const sup = (await ag.readLedger(root)).supervisor;
    assert.equal(sup.sessionId, before.sessionId, '前の会話の記録のまま');
    assert.deepEqual([sup.status, sup.paneId, sup.previousSessions.length], [before.status, before.paneId, 0]);
    assert.match(sup.error, /前面/);
    assert.equal(ag.agentView(sup, [], NOW).resumable, true, '再開できるまま');
    assert.equal((await ag.readLedger(root)).log.at(-1).kind, 'error');
  } finally { await cleanup(); }
});
test('監督の再開: 台帳のセッション ID で --resume・再開の知らせを送る', async () => {
  const { root, cleanup, fake, agents, ctx } = await setup();
  try {
    await assert.rejects(agents.resumeSupervisor(root, ctx), /再開できる監督の記録がありません/);
    await agents.startSupervisor(root, ctx, {});
    const id = (await ag.readLedger(root)).supervisor.sessionId;
    const r = await agents.resumeSupervisor(root, ctx); // pane にエージェントは居ない = 停止
    assert.equal(r.status, 'resumed');
    const start = fake.of('agent', 'start').at(-1).args;
    assert.deepEqual(start.slice(start.indexOf('--')), ['--', '--resume', id]);
    const note = fake.of('agent', 'prompt').at(-1).args[3];
    assert.match(note, /いまのアプリのタブは tab-app です/);
    assert.match(note, /指示を待ってください。新しい作業は始めないでください/);
    assert.match(note, /PJ フォルダの外は変更せず/);
    const led = await ag.readLedger(root);
    assert.equal(led.supervisor.sessionId, id);
    assert.equal(led.supervisor.resumedAt, NOW.toISOString());
  } finally { await cleanup(); }
});

test('二重の起動は「実行中」で断る（PJ ごとのロック）', async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  const { root, cleanup, agents, ctx } = await setup({
    onCall: async (args) => { if (args[0] === 'agent' && args[1] === 'start') await gate; },
  });
  try {
    const first = agents.startSupervisor(root, ctx, {});
    await new Promise((r) => setTimeout(r, 30));
    await assert.rejects(agents.startSupervisor(root, ctx, {}), /実行中/);
    await assert.rejects(agents.resumeSupervisor(root, ctx), /実行中/);
    release();
    assert.equal((await first).status, 'started');
    const next = await agents.startSupervisor(root, ctx, {}).catch((e) => e);
    assert.ok(!/実行中/.test(next.message ?? ''), '終われば再び受け付ける');
  } finally { release(); await cleanup(); }
});

test('監督への指示: 生きていなければ断る・送ったらログに user として残す・先頭が - の文は守る', async () => {
  const { root, cleanup, fake, agents, ctx, panes } = await setup();
  try {
    await assert.rejects(agents.promptSupervisor(root, ctx, { text: 'やって' }), /監督が動いていません/);
    await agents.startSupervisor(root, ctx, {});
    aliveAgent(panes, 'term-1');
    await agents.promptSupervisor(root, ctx, { text: '--version を確かめて' });
    const sent = fake.of('agent', 'prompt').at(-1).args;
    assert.match(sent[3], /^指示: --version/);
    assert.ok(sent.includes('--expect'));
    const led = await ag.readLedger(root);
    assert.deepEqual([led.log.at(-1).from, led.log.at(-1).kind], ['user', 'instruction']);
  } finally { await cleanup(); }
});

async function withSupervisor(options) {
  const s = await setup(options);
  await s.agents.startSupervisor(s.root, s.ctx, {});
  aliveAgent(s.panes, 'term-1');
  return s;
}

test('担当の起動: 監督が必要 → アプリのタブの pane を分ける → agent start --session-id → 役割 → 線 3 本 → 台帳', async () => {
  const s = await setup();
  try {
    await assert.rejects(s.agents.startWorker(s.root, s.ctx, { slug: '20261015-feature', instruction: '' }), /監督が動いていません/);
    await s.agents.startSupervisor(s.root, s.ctx, {});
    aliveAgent(s.panes, 'term-1');
    const before = s.fake.calls.length;
    const r = await s.agents.startWorker(s.root, s.ctx, { slug: '20261015-feature', instruction: '要件から始めて' });
    assert.equal(r.status, 'started');
    const calls = s.fake.calls.slice(before).map((c) => c.args);
    assert.deepEqual(calls[0], ['snapshot']);
    assert.deepEqual(calls[1], ['pane', 'split', 'term-1', '--direction', 'right'], 'タブは作らず、アプリのタブの作業 pane を分ける');
    assert.equal(s.fake.of('tab', 'create').length, 0);
    const name = ag.workerName(s.root, '20261015-feature');
    assert.match(name, /^aidev-w-[0-9a-f]{4}-[a-z0-9-]+-[0-9a-f]{4}$/);
    assert.ok(name.length <= 32);
    assert.deepEqual(calls[2].slice(0, 8), ['agent', 'start', name, '--kind', 'claude', '--pane', 'term-split', '--timeout']);
    assert.deepEqual(calls[2].slice(calls[2].indexOf('--')), ['--', '--session-id', '00000000-0000-4000-8000-000000000002']);
    assert.equal(calls[3][0] + calls[3][1], 'agentprompt');
    const file = /"(.+worker-20261015-feature-[^"]+\.md)"/.exec(calls[3][3])[1];
    const body = await readFile(file, 'utf8');
    assert.match(body, /aidev-00-start/);
    assert.match(body, /要件から始めて/);
    assert.match(body, /worker-report --tab tab-app/);
    assert.match(body, /PJ フォルダの外のファイルは変更しない/);
    assert.match(body, new RegExp(ag.supervisorName(s.root)));
    const links = calls.filter((c) => c[0] === 'graph');
    assert.equal(links.length, 3);
    for (const l of links) assert.deepEqual(l.slice(0, 5), ['graph', 'link', 'add', 'term-split', 'term-1']);
    assert.ok(links[0].includes('supervise'));
    assert.ok(links[1].includes('approval') && links[1].includes('notify'));
    const trigger = links[2];
    assert.ok(trigger.includes('trigger') && trigger.includes('done'));
    assert.equal(trigger[trigger.indexOf('--output') + 1], '60');
    assert.equal(trigger[trigger.indexOf('--when-busy') + 1], 'wait');
    assert.match(trigger.find((a) => a.startsWith('--prompt=')), /aidev の担当 20261015-feature が一区切りつきました。結果を確かめ、次を判断してください。\n\{output\}/);
    assert.ok(trigger.includes('--json'), 'graph は --json で JSON を受ける');
    const w = (await ag.readLedger(s.root)).workers['20261015-feature'];
    assert.deepEqual([w.sessionId, w.tabId, w.paneId, w.status, w.pending], ['00000000-0000-4000-8000-000000000002', 'tab-app', 'term-split', 'running', []]);
  } finally { await s.cleanup(); }
});
test('担当の起動: 生きていれば「すでに動いています」・止まっていれば再開を案内・fresh なら新しい会話', async () => {
  const s = await withSupervisor();
  try {
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    const wp = (await ag.readLedger(s.root)).workers.w1.paneId;
    aliveAgent(s.panes, wp);
    const again = await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    assert.equal(again.status, 'already');
    assert.match(again.message, /すでに動いています/);
    s.panes.find((p) => p.id === wp).agent = null;
    await assert.rejects(s.agents.startWorker(s.root, s.ctx, { slug: 'w1' }), /worker-resume/);
    await assert.rejects(s.agents.resumeWorker(s.root, s.ctx, { slug: 'nope' }), /記録がありません/);
    const first = (await ag.readLedger(s.root)).workers.w1.sessionId;
    const fresh = await s.agents.startWorker(s.root, s.ctx, { slug: 'w1', fresh: true });
    assert.equal(fresh.status, 'started');
    const w = (await ag.readLedger(s.root)).workers.w1;
    assert.notEqual(w.sessionId, first);
    assert.deepEqual(w.previousSessions.map((x) => x.sessionId), [first], '前の会話の ID を previousSessions に残す');
  } finally { await s.cleanup(); }
});
test('担当の再開: 前の pane が残っていれば再利用して --resume・線を結び直し・再開の知らせ（いまのタブ ID・指示待ち）', async () => {
  const s = await withSupervisor();
  try {
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    const led0 = (await ag.readLedger(s.root)).workers.w1;
    s.panes.push({ id: led0.paneId, tabId: 'tab-app', workspaceId: 'ws1', agent: null }); // 担当だけ終了して、pane は残っている
    const before = s.fake.calls.length;
    const splits = s.fake.of('pane', 'split').length;
    const r = await s.agents.resumeWorker(s.root, s.ctx, { slug: 'w1' });
    assert.equal(r.status, 'resumed');
    const calls = s.fake.calls.slice(before).map((c) => c.args);
    assert.equal(s.fake.of('pane', 'split').length, splits, 'pane が残っていれば分けない');
    const start = calls.find((c) => c[0] === 'agent' && c[1] === 'start');
    assert.equal(start[start.indexOf('--pane') + 1], led0.paneId);
    assert.deepEqual(start.slice(start.indexOf('--')), ['--', '--resume', led0.sessionId]);
    assert.equal(calls.filter((c) => c[0] === 'graph').length, 3);
    const note = calls.find((c) => c[0] === 'agent' && c[1] === 'prompt')[3];
    assert.match(note, /いまのアプリのタブは tab-app です/);
    assert.match(note, /指示を待ってください。新しい作業は始めないでください/);
    const w = (await ag.readLedger(s.root)).workers.w1;
    assert.equal(w.sessionId, led0.sessionId);
    assert.equal(w.resumedAt, NOW.toISOString());
  } finally { await s.cleanup(); }
});
test('担当の起動: 線を結べなくても起動は成功とし、ログに残す', async () => {
  const s = await withSupervisor({ onCall: (args) => { if (args[0] === 'graph') throw sodaErr('invalid_params', 'supervisor_taken'); } });
  try {
    const r = await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    assert.equal(r.status, 'started');
    assert.equal(r.warnings.length, 3);
    const led = await ag.readLedger(s.root);
    assert.equal(led.workers.w1.status, 'running');
    assert.equal(led.workers.w1.linkErrors.length, 3);
    assert.ok(led.log.some((e) => e.kind === 'error' && /supervisor_taken/.test(e.message)));
  } finally { await s.cleanup(); }
});

test('担当の起動: 失敗は台帳に failed で残し、自動では再試行しない', async () => {
  let starts = 0;
  const s = await withSupervisor({ onCall: (args) => { if (args[0] === 'agent' && args[1] === 'start' && args[2].startsWith('aidev-w-')) { starts++; throw sodaErr('timeout', '時間切れ'); } } });
  try {
    await assert.rejects(s.agents.startWorker(s.root, s.ctx, { slug: 'w1' }), /時間切れ/);
    assert.equal(starts, 1);
    const w = (await ag.readLedger(s.root)).workers.w1;
    assert.equal(w.status, 'failed');
    assert.match(w.error, /時間切れ/);
    // failed は新しい会話として起動し直せる（再開は別に使える）
    await assert.rejects(s.agents.startWorker(s.root, s.ctx, { slug: 'w1' }), /時間切れ/);
    assert.equal(starts, 2);
  } finally { await s.cleanup(); }
});

test('担当への指示・報告: question・failed・blocked だけ監督へ中継する', async () => {
  const s = await withSupervisor();
  try {
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    aliveAgent(s.panes, (await ag.readLedger(s.root)).workers.w1.paneId);
    await s.agents.promptWorker(s.root, s.ctx, { slug: 'w1', text: '次へ' });
    let last = s.fake.of('agent', 'prompt').at(-1).args;
    assert.equal(last[2], ag.workerName(s.root, 'w1'));
    const before = s.fake.of('agent', 'prompt').length;
    assert.equal((await s.agents.reportWorker(s.root, s.ctx, { slug: 'w1', status: 'progress', message: '進んでいます' })).relayed, null);
    assert.equal((await s.agents.reportWorker(s.root, s.ctx, { slug: 'w1', status: 'done', message: '完了' })).relayed, null);
    assert.equal(s.fake.of('agent', 'prompt').length, before, 'progress・done は中継しない（done はトリガの線が知らせる）');
    const q = await s.agents.reportWorker(s.root, s.ctx, { slug: 'w1', status: 'question', message: 'どちらにしますか' });
    assert.equal(q.relayed, true);
    last = s.fake.of('agent', 'prompt').at(-1).args;
    assert.equal(last[2], ag.supervisorName(s.root));
    assert.match(last[3], /担当 w1 の報告: question.*どちらにしますか/);
    const led = await ag.readLedger(s.root);
    assert.equal(led.workers.w1.lastReport.status, 'question');
    assert.equal(led.log.at(-1).from, 'worker');
    await assert.rejects(s.agents.reportWorker(s.root, s.ctx, { slug: 'unknown', status: 'done', message: 'm' }), /記録がありません/);
  } finally { await s.cleanup(); }
});

test('中継の失敗はログに残すだけで再試行しない', async () => {
  let supPrompts = 0;
  const s = await withSupervisor({ onCall: (args) => { if (args[0] === 'agent' && args[1] === 'prompt' && args[2].startsWith('aidev-sup-') && supPrompts++ > 0) throw sodaErr('agent_blocked', '作業中'); } });
  try {
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    const before = supPrompts;
    const r = await s.agents.reportWorker(s.root, s.ctx, { slug: 'w1', status: 'failed', message: '壊れた' });
    assert.equal(r.relayed, false);
    assert.equal(supPrompts, before + 1, '再試行しない');
    assert.ok((await ag.readLedger(s.root)).log.some((e) => e.kind === 'error' && /中継に失敗/.test(e.message)));
  } finally { await s.cleanup(); }
});

test('監督から利用者への知らせ（report）と概要・ログ', async () => {
  const s = await setup();
  try {
    await s.agents.report(s.root, { message: '判断をください', level: 'question' });
    const o = await s.agents.overview(s.root, s.panes);
    assert.equal(o.log[0].level, 'question');
    assert.equal(o.log[0].from, 'supervisor');
    assert.equal((await s.agents.logList(s.root, 5)).log.length, 1);
  } finally { await s.cleanup(); }
});

test('状態の読み替え: pane とエージェントの有無から決める', () => {
  const entry = { name: 'n', kind: 'claude', sessionId: '00000000-0000-4000-8000-000000000001', paneId: 'p1', status: 'running', startedAt: '2026-10-14T00:00:00.000Z', resumedAt: null, error: null };
  const view = (panes, e = entry, now = NOW) => ag.agentView(e, panes, now);
  assert.equal(view([{ id: 'p1', agent: 'claude', agentState: 'working' }]).status, 'working');
  assert.equal(view([{ id: 'p1', agent: 'claude', agentState: 'blocked' }]).status, 'blocked');
  assert.equal(view([{ id: 'p1', agent: 'claude', agentState: 'done' }]).status, 'idle');
  assert.equal(view([{ id: 'p1', agent: null }]).status, 'stopped');
  assert.equal(view([]).status, 'stopped');
  assert.equal(view([]).resumable, true);
  assert.equal(view([{ id: 'p1', agent: 'codex', agentState: 'idle' }]).alive, false, '別の種類のエージェントは別物');
  assert.equal(view([], { ...entry, status: 'failed' }).status, 'failed');
  assert.equal(view([], { ...entry, startedAt: NOW.toISOString() }).status, 'starting');
  assert.equal(ag.agentView(null, []), null);
});

test('自動起動: 記録があれば再開・無ければ起動・生きていれば何もしない・設定で止められる', async () => {
  const s = await setup();
  try {
    assert.equal((await s.agents.autoStart(s.root, s.ctx)).status, 'started');
    aliveAgent(s.panes, 'term-1');
    assert.equal((await s.agents.autoStart(s.root, s.ctx)).status, 'already');
    s.panes.find((p) => p.id === 'term-1').agent = null;
    assert.equal((await s.agents.autoStart(s.root, s.ctx)).status, 'resumed');
    await ag.saveSettings(s.root, { autoStartSupervisor: false });
    s.panes.find((p) => p.id === 'term-1').agent = null;
    const startsBefore = s.fake.of('agent', 'start').length;
    assert.equal((await s.agents.autoStart(s.root, s.ctx)).status, 'disabled');
    assert.equal(s.fake.of('agent', 'start').length, startsBefore);
  } finally { await s.cleanup(); }
});

test('名前は agent rename の書式に収まる（長い slug・記号・大文字を含んでも）', () => {
  for (const slug of ['a', '20261015-a-very-long-work-name-that-keeps-going-and-going-and-going-on', '0-0', 'x'.repeat(64), '20261015-' + '-'.repeat(5) + 'a']) {
    const name = ag.workerName('/some/project', slug);
    assert.match(name, /^[a-z][a-z0-9_-]{0,31}$/, name);
  }
  assert.notEqual(ag.workerName('/p1', 'w'), ag.workerName('/p2', 'w'));
  assert.notEqual(ag.workerName('/p', 'long-name-aaaaaaaaaaaaaaaa-1'), ag.workerName('/p', 'long-name-aaaaaaaaaaaaaaaa-2'));
  assert.match(ag.supervisorName('/p'), /^[a-z][a-z0-9_-]{0,31}$/);
});

test('プロンプトの送信: 名前が合っていれば付け直さない・別のエージェントに入れ替わっていれば何も送らない', async () => {
  let swap = false;
  const { root, cleanup, fake, agents, ctx, panes } = await setup({
    onCall: (args) => { if (swap && args[0] === 'agent' && args[1] === 'get') return { agent: { paneId: args[2], kind: 'codex', name: null, instanceId: 'x', tabId: 'tab-app' } }; },
  });
  try {
    await agents.startSupervisor(root, ctx, {});
    aliveAgent(panes, 'term-1');
    const get = fake.of('agent', 'get');
    await agents.promptSupervisor(root, ctx, { text: '続けて' });
    assert.equal(fake.of('agent', 'get').length, get.length + 1);
    assert.equal(fake.of('agent', 'rename').length, 0, '名前が合っていれば付け直さない');
    swap = true;
    await assert.rejects(agents.promptSupervisor(root, ctx, { text: '続けて' }), /入れ替わった可能性/);
    assert.equal(fake.of('agent', 'prompt').length, 2, '起動時の役割と最初の指示だけ。入れ替わっていれば何も送らない');
  } finally { await cleanup(); }
});

test('プロンプトの送信: 名前が違えば agent rename で台帳の名前を付け直してから送る', async () => {
  const { root, cleanup, fake, agents, ctx, panes } = await setup({
    onCall: (args) => { if (args[0] === 'agent' && args[1] === 'get' && args[2] === 'term-1' && !fake.renamed) return { agent: { paneId: 'term-1', kind: 'claude', name: null, instanceId: 'inst-restored', tabId: 'tab-app' } }; },
  });
  try {
    await agents.startSupervisor(root, ctx, {});
    aliveAgent(panes, 'term-1');
    await agents.promptSupervisor(root, ctx, { text: '続けて' });
    const rename = fake.of('agent', 'rename')[0].args;
    assert.deepEqual(rename, ['agent', 'rename', 'term-1', ag.supervisorName(root)]);
    const last = fake.of('agent', 'prompt').at(-1).args;
    assert.equal(JSON.parse(last[last.indexOf('--expect') + 1]).name, ag.supervisorName(root));
  } finally { await cleanup(); }
});

// ---- Codex ---------------------------------------------------------------------------------------

const CODEX_ID = '019a0000-1111-7222-8333-444444444444';

test('Codex の監督: 初回は ID を指定せず起動し、払い出された ID を台帳に記録する', async () => {
  let started = null;
  const s = await setup({
    onCall: (args) => {
      if (args[0] === 'agent' && args[1] === 'start') started = args;
      if (args[0] === 'snapshot' && started) {
        return { panes: [{ id: 'term-1', tabId: 'tab-app', virtual: false, agent: { kind: 'codex', name: started[2], instanceId: 'inst-1' }, agentSession: { kind: 'codex', sessionId: CODEX_ID } }] };
      }
    },
  });
  try {
    await ag.saveSettings(s.root, { supervisorKind: 'codex', supervisorModel: 'gpt-5', codexPermission: 'workspace-write' });
    const r = await s.agents.startSupervisor(s.root, s.ctx, {});
    assert.equal(r.status, 'started');
    assert.deepEqual(started.slice(started.indexOf('--kind'), started.indexOf('--kind') + 2), ['--kind', 'codex']);
    assert.deepEqual(started.slice(started.indexOf('--') + 1), ['-C', s.root, '-m', 'gpt-5', '-s', 'workspace-write', '-a', 'on-request'], 'Codex には --session-id を渡さない');
    const led = await ag.readLedger(s.root);
    assert.equal(led.supervisor.kind, 'codex');
    assert.equal(led.supervisor.sessionId, CODEX_ID);
    assert.ok(led.log.some((e) => /会話 ID を記録しました/.test(e.message)));
    assert.equal(r.supervisor.sessionPending, false);
  } finally { await s.cleanup(); }
});

test('Codex: ID がまだ払い出されていなければ未取得として残し、周期の取り込みで記録する・再開はできない', async () => {
  let started = null, report = false;
  const s = await setup({
    onCall: (args) => {
      if (args[0] === 'agent' && args[1] === 'start') started = args;
      if (args[0] === 'snapshot' && started) {
        return { panes: [{ id: 'term-1', tabId: 'tab-app', virtual: false, agent: { kind: 'codex', name: started[2], instanceId: 'inst-1' }, ...(report ? { agentSession: { kind: 'codex', sessionId: CODEX_ID } } : {}) }] };
      }
    },
  });
  try {
    await ag.saveSettings(s.root, { supervisorKind: 'codex' });
    const r = await s.agents.startSupervisor(s.root, s.ctx, {});
    assert.equal(r.supervisor.sessionPending, true);
    assert.equal((await ag.readLedger(s.root)).supervisor.sessionId, '');
    await assert.rejects(s.agents.resumeSupervisor(s.root, s.ctx), /会話 ID をまだ取得できていない/);
    assert.equal(await s.agents.captureSessions(s.root), 0);
    report = true;
    assert.equal(await s.agents.captureSessions(s.root), 1);
    assert.equal((await ag.readLedger(s.root)).supervisor.sessionId, CODEX_ID);
    assert.equal(await s.agents.captureSessions(s.root), 0, '取り込み済みは触らない');
  } finally { await s.cleanup(); }
});

test('Codex: 別の種類・別の名前の pane の ID は取り込まない', async () => {
  let started = null;
  const s = await setup({
    onCall: (args) => {
      if (args[0] === 'agent' && args[1] === 'start') started = args;
      if (args[0] === 'snapshot' && started) {
        return { panes: [{ id: 'term-1', tabId: 'tab-app', virtual: false, agent: { kind: 'codex', name: 'someone-else', instanceId: 'i' }, agentSession: { kind: 'codex', sessionId: CODEX_ID } }] };
      }
    },
  });
  try {
    await ag.saveSettings(s.root, { supervisorKind: 'codex' });
    await s.agents.startSupervisor(s.root, s.ctx, {});
    assert.equal((await ag.readLedger(s.root)).supervisor.sessionId, '');
  } finally { await s.cleanup(); }
});

test('Codex の再開: codex resume <ID> -C <PJ>（記録した種類で起動する。設定が変わっていても）', async () => {
  let started = null;
  const s = await setup({
    onCall: (args) => {
      if (args[0] === 'agent' && args[1] === 'start') started = args;
      if (args[0] === 'snapshot' && started) return { panes: [{ id: 'term-1', tabId: 'tab-app', virtual: false, agent: { kind: 'codex', name: started[2], instanceId: 'inst-1' }, agentSession: { kind: 'codex', sessionId: CODEX_ID } }] };
    },
  });
  try {
    await ag.saveSettings(s.root, { supervisorKind: 'codex' });
    await s.agents.startSupervisor(s.root, s.ctx, {});
    await ag.saveSettings(s.root, { supervisorKind: 'claude' }); // 設定を変えても、記録した種類で再開する
    started = null;
    const r = await s.agents.resumeSupervisor(s.root, s.ctx);
    assert.equal(r.status, 'resumed');
    assert.deepEqual(started.slice(started.indexOf('--kind'), started.indexOf('--kind') + 2), ['--kind', 'codex']);
    assert.deepEqual(started.slice(started.indexOf('--') + 1), ['resume', CODEX_ID, '-C', s.root]);
  } finally { await s.cleanup(); }
});

test('監督は Claude・担当は Codex の混在: 担当だけ Codex で起動し、線は同じように結ぶ', async () => {
  const s = await setup();
  try {
    await ag.saveSettings(s.root, { workerKind: 'codex', codexPermission: 'workspace-write-never' });
    await s.agents.startSupervisor(s.root, s.ctx, {});
    aliveAgent(s.panes, 'term-1');
    const before = s.fake.calls.length;
    const r = await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    assert.equal(r.status, 'started');
    const calls = s.fake.calls.slice(before).map((c) => c.args);
    const start = calls.find((c) => c[0] === 'agent' && c[1] === 'start');
    assert.equal(start[start.indexOf('--kind') + 1], 'codex');
    assert.deepEqual(start.slice(start.indexOf('--') + 1), ['-C', s.root, '-s', 'workspace-write', '-a', 'never']);
    assert.equal(calls.filter((c) => c[0] === 'graph').length, 3);
    const led = await ag.readLedger(s.root);
    assert.equal(led.supervisor.kind, 'claude');
    assert.equal(led.workers.w1.kind, 'codex');
    // ID 未取得のまま止まっていれば、再開ではなく新しく起動し直せる
    s.panes.find((p) => p.id === WP);
    const again = await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    assert.equal(again.status, 'started');
  } finally { await s.cleanup(); }
});

test('設定: エージェントの種類と Codex の権限は固定の選択肢だけ', () => {
  assert.equal(ag.normalizeSettings({ workerKind: 'codex' }).workerKind, 'codex');
  for (const bad of [{ workerKind: 'gemini' }, { supervisorKind: '' }, { codexPermission: 'danger-full-access' }, { codexPermission: 5 }]) assert.throws(() => ag.normalizeSettings(bad), Error, JSON.stringify(bad));
  assert.equal(ag.normalizeSettings({ codexPermission: 'read-only' }).codexPermission, 'read-only');
});

// ---- 関連するエージェント・種類とモデルの指定 --------------------------------------------------------

const PA = 'aaaa1111-0000-4000-8000-000000000001';
const PB = 'aaaa2222-0000-4000-8000-000000000002';
const PC = 'aaaa3333-0000-4000-8000-000000000003';

async function withWorkerAndGraph(links, opts = {}) {
  const s = await setup({
    onCall: (args) => {
      if (args[0] === 'graph' && args[1] === 'show') return { graph: { links } };
      if (args[0] === 'agent' && args[1] === 'read') return { raw: '末尾の出力\n' };
      return opts.onCall?.(args);
    },
  });
  await s.agents.startSupervisor(s.root, s.ctx, {});
  aliveAgent(s.panes, 'term-1');
  await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
  s.wp = (await ag.readLedger(s.root)).workers.w1.paneId;
  aliveAgent(s.panes, s.wp);
  return s;
}
const WP = 'term-split'; // 担当は、アプリのタブの pane を分けて置かれる
const link = (from, to, kind = 'supervise') => ({ id: `l-${from}-${to}`, kind, from: `local:${from}`, to: `local:${to}` });

test('関連するエージェント: 担当の pane に線で連なるものを再帰で辿る（孫まで・生きているものだけ・監督や他の担当は除く）', async () => {
  const s = await withWorkerAndGraph([link(PA, WP), link(PB, PA), link(PC, PB), link('term-1', WP), link('x-dead', WP), link(PA, 'term-1')]);
  try {
    s.panes.push({ id: PA, agent: 'codex', agentState: 'working', label: 'helper' }, { id: PB, agent: 'claude', agentState: 'blocked' }, { id: PC, agent: 'claude', agentState: 'idle' });
    const rel = (await s.agents.related(s.root, s.panes, { force: true })).w1;
    assert.deepEqual(rel.map((a) => [a.paneId, a.kind, a.status, a.depth]), [[PA, 'codex', 'working', 1], [PB, 'claude', 'blocked', 2], [PC, 'claude', 'idle', 3]]);
    assert.equal(rel[0].label, 'helper');
    assert.ok(!rel.some((a) => a.paneId === 'term-1' || a.paneId === WP || a.paneId === 'x-dead'));
  } finally { await s.cleanup(); }
});

test('関連するエージェント: 登録は担当の pane から線で連なる pane だけ（深さ 4 以降は登録分として出る）', async () => {
  const PD = 'aaaa4444-0000-4000-8000-000000000004';
  const s = await withWorkerAndGraph([link(PA, WP), link(PB, PA), link(PC, PB), link(PD, PC)]);
  try {
    s.panes.push(...[PA, PB, PC, PD].map((id) => ({ id, agent: 'claude', agentState: 'idle', workspaceId: 'ws1' })));
    s.panes.push({ id: 'user-pane', agent: 'claude', agentState: 'idle', workspaceId: 'ws1' });
    let rel = (await s.agents.related(s.root, s.panes, { force: true })).w1;
    assert.deepEqual(rel.map((a) => [a.paneId, a.registered]), [[PA, false], [PB, false], [PC, false]], '深さ 3 まで');
    await assert.rejects(s.agents.registerRelated(s.root, s.ctx, { slug: 'w1', paneId: 'user-pane' }), /線で連なっていません/, '利用者自身の pane は登録できない');
    await assert.rejects(s.agents.registerRelated(s.root, s.ctx, { slug: 'nope', paneId: PD }), /記録がありません/);
    await assert.rejects(s.agents.registerRelated(s.root, s.ctx, { slug: 'w1', paneId: WP }), /自身/);
    await s.agents.registerRelated(s.root, s.ctx, { slug: 'w1', paneId: PD });
    rel = (await s.agents.related(s.root, s.panes, { force: true })).w1;
    assert.deepEqual(rel.map((a) => [a.paneId, a.registered]), [[PA, false], [PB, false], [PC, false], [PD, true]]);
    assert.deepEqual((await ag.readLedger(s.root)).workers.w1.related, [PD]);
  } finally { await s.cleanup(); }
});

test('関連するエージェント: グラフを読めないときは登録を断る', async () => {
  const s = await setup({ onCall: (args) => { if (args[0] === 'graph' && args[1] === 'show') throw sodaErr('unauthenticated', 'login'); } });
  try {
    await s.agents.startSupervisor(s.root, s.ctx, {});
    aliveAgent(s.panes, 'term-1');
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    s.panes.push({ id: PA, agent: 'claude', agentState: 'idle', workspaceId: 'ws1' });
    await assert.rejects(s.agents.registerRelated(s.root, s.ctx, { slug: 'w1', paneId: PA }), /グラフを読めない/);
    assert.deepEqual((await s.agents.related(s.root, s.panes, { force: true })).w1, []);
  } finally { await s.cleanup(); }
});
test('関連するエージェントへの指示・読み取り: 作業に連なる pane だけ', async () => {
  const s = await withWorkerAndGraph([link(PA, WP)], {
    onCall: (args) => { if (args[0] === 'agent' && args[1] === 'get' && args[2] === PA) return { agent: { paneId: PA, name: 'aidev-helper', kind: 'codex', instanceId: 'i-9', tabId: 'tab-x' } }; },
  });
  try {
    s.panes.push({ id: PA, agent: 'codex', agentState: 'idle' }, { id: PC, agent: 'claude', agentState: 'idle' });
    await assert.rejects(s.agents.promptRelated(s.root, s.ctx, { slug: 'w1', paneId: PC, text: 'x' }), /関連するエージェントではありません/);
    const r = await s.agents.promptRelated(s.root, s.ctx, { slug: 'w1', paneId: PA, text: '--help を調べて' });
    assert.equal(r.status, 'sent');
    const sent = s.fake.of('agent', 'prompt').at(-1).args;
    assert.deepEqual(sent.slice(0, 3), ['agent', 'prompt', PA]);
    assert.match(sent[3], /^指示: --help/);
    assert.deepEqual(JSON.parse(sent[sent.indexOf('--expect') + 1]), { paneId: PA, instanceId: 'i-9', tabId: 'tab-x', projectDir: s.root, name: 'aidev-helper' });
    assert.match((await ag.readLedger(s.root)).log.at(-1).message, /\[関連 aaaa1111\]/);
    await s.agents.promptRelated(s.root, s.ctx, { slug: 'w1', paneId: WP, text: 'go' }); // 担当自身も指せる
    const read = await s.agents.readRelated(s.root, s.ctx, { slug: 'w1', paneId: PA, lines: 30 });
    assert.equal(read.text, '末尾の出力\n');
    assert.deepEqual(s.fake.of('agent', 'read').at(-1).args, ['agent', 'read', PA, '--lines', '30']);
    await assert.rejects(s.agents.readRelated(s.root, s.ctx, { slug: 'w1', paneId: PC }), /関連するエージェントではありません/);
  } finally { await s.cleanup(); }
});

test('起動ごとの種類とモデル: 設定の既定を上書きし、記録した種類が再開に使われる', async () => {
  const s = await setup();
  try {
    await ag.saveSettings(s.root, { supervisorKind: 'claude', workerKind: 'claude', supervisorModel: 'sonnet', workerModel: 'opus' });
    await s.agents.startSupervisor(s.root, s.ctx, { kind: 'codex', model: 'gpt-5' });
    const sup = s.fake.of('agent', 'start')[0].args;
    assert.equal(sup[sup.indexOf('--kind') + 1], 'codex');
    assert.deepEqual(sup.slice(sup.indexOf('--') + 1), ['-C', s.root, '-m', 'gpt-5']);
    aliveAgent(s.panes, 'term-1');
    s.panes.find((p) => p.id === 'term-1').agent = 'codex';
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1', kind: 'claude', model: 'haiku' });
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w2' });
    const [w1, w2] = [s.fake.of('agent', 'start')[1].args, s.fake.of('agent', 'start')[2].args];
    assert.equal(w1[w1.indexOf('--kind') + 1], 'claude');
    assert.deepEqual(w1.slice(w1.indexOf('--') + 1).slice(-2), ['--model', 'haiku']);
    assert.deepEqual(w2.slice(w2.indexOf('--') + 1).slice(-2), ['--model', 'opus'], '指定が無ければ設定の既定');
    const led = await ag.readLedger(s.root);
    assert.deepEqual([led.supervisor.kind, led.supervisor.model, led.workers.w1.kind, led.workers.w1.model], ['codex', 'gpt-5', 'claude', 'haiku']);
  } finally { await s.cleanup(); }
});

// ---- fix-01: 承認待ちの仕上げ・置き場所・上書きの防止・終了 ------------------------------------------------

const idleAt = (panes, id, kind = 'claude') => { const p = panes.find((x) => x.id === id); if (p) { p.agent = kind; p.agentState = 'idle'; } else panes.push({ id, tabId: 'tab-app', agent: kind, agentState: 'idle' }); };

test('M2: 承認待ちで止まった監督は、答えた後（待機）に、役割が 1 回だけ届く／起動を押し直しても届く', async () => {
  let blocked = true;
  const s = await setup({ onCall: (args) => { if (blocked && args[0] === 'agent' && args[1] === 'start') { blocked = false; throw sodaErr('agent_not_ready', '信頼の確認'); } } });
  try {
    const r = await s.agents.startSupervisor(s.root, s.ctx, {});
    assert.equal(r.status, 'blocked');
    assert.equal(s.fake.of('agent', 'prompt').length, 0, '承認待ちの間は役割を送らない');
    // 利用者が端末で答えた: エージェントが生きて、待機になる（pane は term-1）
    s.fake.calls.length;
    idleAt(s.panes, 'term-1');
    await s.fake.soda(['agent', 'start', ag.supervisorName(s.root), '--kind', 'claude', '--pane', 'term-1', '--', '--session-id', 'x']); // 偽のサーバ側にエージェントを置く
    s.fake.calls.pop();
    assert.equal(await s.agents.finishAll(s.root, s.ctx), 1);
    const prompts = s.fake.of('agent', 'prompt');
    assert.equal(prompts.length, 1);
    assert.match((await readFile(/"(.+supervisor-[^"]+\.md)"/.exec(prompts[0].args[3])[1], 'utf8')), /あなたは aidev の監督です/);
    assert.deepEqual((await ag.readLedger(s.root)).supervisor.pending, []);
    assert.equal(await s.agents.finishAll(s.root, s.ctx), 0, '2 回目はもう無い');
  } finally { await s.cleanup(); }
});

test('M2: 承認待ちの担当は、待機になったら役割と線 3 本が届く（［担当を起動］の押し直しでも）', async () => {
  let blockedOnce = true;
  const s = await withSupervisor({ onCall: (args) => { if (blockedOnce && args[0] === 'agent' && args[1] === 'start' && args[2].startsWith('aidev-w-')) { blockedOnce = false; throw sodaErr('agent_not_ready', '信頼の確認'); } } });
  try {
    const r = await s.agents.startWorker(s.root, s.ctx, { slug: 'w1', instruction: '始めて' });
    assert.equal(r.status, 'blocked');
    assert.equal(s.fake.of('graph').length, 0);
    const w0 = (await ag.readLedger(s.root)).workers.w1;
    assert.deepEqual(w0.pending, ['role', 'links']);
    assert.equal(w0.instruction, '始めて', '指示は仕上げまで台帳に残す');
    // 答えた後: 偽のサーバにエージェントが居る・待機
    await s.fake.soda(['agent', 'start', w0.name, '--kind', 'claude', '--pane', w0.paneId, '--', '--session-id', 'x']);
    s.fake.calls.pop();
    idleAt(s.panes, w0.paneId);
    // 起動の押し直し = 仕上げだけ（新しい会話は始めない）
    const startsBefore = s.fake.of('agent', 'start').length;
    const again = await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    assert.equal(again.status, 'finished');
    assert.equal(s.fake.of('agent', 'start').length, startsBefore);
    assert.equal(s.fake.of('graph').length, 3);
    const body = await readFile(/"(.+worker-w1-[^"]+\.md)"/.exec(s.fake.of('agent', 'prompt').at(-1).args[3])[1], 'utf8');
    assert.match(body, /始めて/);
    assert.deepEqual((await ag.readLedger(s.root)).workers.w1.pending, []);
  } finally { await s.cleanup(); }
});

test('M2: 仕上げは待機になるまで待つ・失敗しても 20 秒以上あけて 3 回まで', async () => {
  let t = +NOW;
  const fake = fakeSoda({ onCall: (args) => { if (args[0] === 'agent' && args[1] === 'start') throw sodaErr('agent_not_ready', '確認'); if (args[0] === 'agent' && args[1] === 'get') return { agent: { paneId: args[2], kind: 'claude', name: ag.supervisorName(root), instanceId: 'i', tabId: 'tab-app' } }; if (args[0] === 'agent' && args[1] === 'prompt') throw sodaErr('agent_blocked', 'x'); } });
  const t0 = await tempDir();
  const root = t0.dir;
  try {
    const agents = ag.createAgents({ makeSoda: () => fake.soda, now: () => new Date(t), uuid: uuids() });
    const panes = basePanes();
    const ctx = { tabId: 'tab-app', workspaceId: 'ws1', paneId: 'anchor', panes };
    await agents.startSupervisor(root, ctx, {});
    panes.find((p) => p.id === 'term-1').agent = 'claude';
    panes.find((p) => p.id === 'term-1').agentState = 'working';
    assert.equal(await agents.finishAll(root, ctx), 0, '作業中は待つ');
    assert.equal(fake.of('agent', 'prompt').length, 0);
    panes.find((p) => p.id === 'term-1').agentState = 'idle';
    for (let i = 0; i < 6; i++) { await agents.finishAll(root, ctx); t += 25000; }
    assert.equal(fake.of('agent', 'prompt').length, 3, '3 回まで');
  } finally { await t0.cleanup(); }
});

test('S1: 担当はアプリのタブの最新の作業 pane を、右・下を交互に分ける。6 個に達したときだけ tab create', async () => {
  const s = await withSupervisor();
  try {
    const split = () => s.fake.of('pane', 'split').map((c) => [c.args[2], c.args[4]]);
    const mkPanes = () => { for (const k of s.fake.known) if (!s.panes.some((p) => p.id === k.id)) s.panes.push({ id: k.id, tabId: k.tabId, workspaceId: 'ws1', agent: null, virtual: !!k.virtual }); };
    for (const slug of ['w1', 'w2', 'w3', 'w4']) {
      await s.agents.startWorker(s.root, s.ctx, { slug });
      mkPanes();
      const wp = (await ag.readLedger(s.root)).workers[slug].paneId;
      idleAt(s.panes, wp);
    }
    assert.deepEqual(split(), [['term-1', 'right'], ['term-split', 'down'], ['term-split-2', 'right'], ['term-split-3', 'down']]);
    assert.equal(s.fake.of('tab', 'create').length, 0);
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w5' });
    assert.equal(s.fake.of('tab', 'create').length, 0, '5 個目の pane（合計 6 個）まではタブを作らない');
    mkPanes();
    idleAt(s.panes, (await ag.readLedger(s.root)).workers.w5.paneId);
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w6' });
    assert.equal(s.fake.of('tab', 'create').length, 1, '6 個に達したとき、そのときだけ新しいタブ');
    assert.equal((await ag.readLedger(s.root)).workers.w6.tabId, 'tab-w1');
  } finally { await s.cleanup(); }
});

test('S2: prompts/・agents.json・settings.json がシンボリックリンクなら使わない（外へ書かない）', async () => {
  const s = await setup();
  const out = await tempDir();
  try {
    const dir = await ag.ensureStateDir(s.root);
    await symlink(out.dir, join(dir, 'prompts'));
    const r = await s.agents.startSupervisor(s.root, s.ctx, {});
    assert.match(r.warnings.join(' '), /シンボリックリンク/, '役割は送れず、理由が出る');
    assert.deepEqual(await readdir(out.dir), [], '外には何も書かない');
    assert.deepEqual((await ag.readLedger(s.root)).supervisor.pending, ['role'], '仕上げは残る');
    await rm(join(dir, 'prompts'));
    await rm(join(dir, 'agents.json'));
    await writeFile(join(out.dir, 'real.json'), JSON.stringify({ supervisor: { name: 'x', sessionId: '00000000-0000-4000-8000-000000000009' } }));
    await symlink(join(out.dir, 'real.json'), join(dir, 'agents.json'));
    await assert.rejects(ag.readLedger(s.root), /シンボリックリンク/);
    await rm(join(dir, 'agents.json'));
    await writeFile(join(out.dir, 's.json'), JSON.stringify({ workerModel: 'evil' }));
    await symlink(join(out.dir, 's.json'), join(dir, 'settings.json'));
    assert.equal((await ag.loadSettings(s.root)).workerModel, '', 'リンクの設定は読まない');
    await assert.rejects(ag.saveSettings(s.root, { workerModel: 'ok' }), /シンボリックリンク/);
    assert.equal(await readFile(join(out.dir, 's.json'), 'utf8'), JSON.stringify({ workerModel: 'evil' }), '外のファイルは書き換えない');
  } finally { await s.cleanup(); await out.cleanup(); }
});

test('S5: 再開できる会話があれば start は断る・fresh は ID を previousSessions（最新 5 件）に残す・resumable は failed を除く', async () => {
  const s = await setup();
  try {
    await s.agents.startSupervisor(s.root, s.ctx, {});
    const ids = [(await ag.readLedger(s.root)).supervisor.sessionId];
    await assert.rejects(s.agents.startSupervisor(s.root, s.ctx, {}), /再開できる会話があります/);
    for (let i = 0; i < 6; i++) {
      await s.agents.startSupervisor(s.root, s.ctx, { fresh: true });
      ids.push((await ag.readLedger(s.root)).supervisor.sessionId);
    }
    const sup = (await ag.readLedger(s.root)).supervisor;
    assert.equal(sup.sessionId, ids.at(-1));
    assert.deepEqual(sup.previousSessions.map((x) => x.sessionId), ids.slice(0, -1).reverse().slice(0, 5), '新しい順に最新 5 件');
    // failed の記録は resumable にならない
    const view = ag.agentView({ ...sup, status: 'failed' }, [], NOW);
    assert.equal(view.resumable, false);
  } finally { await s.cleanup(); }
});

test('S5・L4: --resume が会話を見つけられず落ちたら failed にして、新しい会話を案内する', async () => {
  let failResume = false;
  const s = await setup({ onCall: (args) => { if (failResume && args[0] === 'agent' && args[1] === 'start') throw sodaErr('agent_start_failed', 'No conversation found'); } });
  try {
    await s.agents.startSupervisor(s.root, s.ctx, {});
    failResume = true;
    await assert.rejects(s.agents.resumeSupervisor(s.root, s.ctx), /No conversation found/);
    const sup = (await ag.readLedger(s.root)).supervisor;
    assert.equal(sup.status, 'failed');
    assert.match(sup.error, /新しい会話で始める/);
    await assert.rejects(s.agents.resumeSupervisor(s.root, s.ctx), /失敗しています。「新しい会話で始める」/);
    failResume = false;
    const started = await s.agents.startSupervisor(s.root, s.ctx, {}); // failed は fresh なしで、新しい会話を始められる
    assert.equal(started.status, 'started');
  } finally { await s.cleanup(); }
});

test('L4: 役割を送る前に止まったもの（pending に role）は再開せず、新しい会話で起動する', async () => {
  const s = await setup({ onCall: (args) => { if (args[0] === 'agent' && args[1] === 'start') throw sodaErr('agent_not_ready', '確認'); } });
  try {
    await s.agents.startSupervisor(s.root, s.ctx, {}); // blocked・pending: role
    const view = ag.agentView((await ag.readLedger(s.root)).supervisor, [], NOW); // 答えずに止まった（pane にエージェントは居ない）
    assert.equal(view.resumable, false);
    await assert.rejects(s.agents.resumeSupervisor(s.root, s.ctx), /役割を送る前に止まった/);
    await assert.doesNotReject(s.agents.startSupervisor(s.root, s.ctx, {}).catch((e) => { if (/再開できる会話/.test(e.message)) throw e; }), 'fresh なしで新しい会話を始められる');
  } finally { await s.cleanup(); }
});

test('N4: CLI から送った監督への指示は、利用者の指示として記録しない', async () => {
  const s = await withSupervisor();
  try {
    await s.agents.promptSupervisor(s.root, s.ctx, { text: '調べて', source: 'cli' });
    const e = (await ag.readLedger(s.root)).log.at(-1);
    assert.deepEqual([e.from, e.kind], ['app', 'instruction']);
    assert.match(e.message, /^\[CLI から\] 調べて/);
  } finally { await s.cleanup(); }
});

test('N5: 大文字・. _ を含む slug でも担当を起動でき、エージェント名は安全な形になる', async () => {
  const s = await withSupervisor();
  try {
    const r = await s.agents.startWorker(s.root, s.ctx, { slug: 'Feature_X.v2' });
    assert.equal(r.status, 'started');
    assert.match((await ag.readLedger(s.root)).workers['Feature_X.v2'].name, /^[a-z][a-z0-9_-]{0,31}$/);
  } finally { await s.cleanup(); }
});

/** 完了の終了の試験用: 担当・補助 1 件・トリガの線（履歴は runs を差し替える）を持つ環境。 */
async function doneEnv({ helperState = 'idle', registered = false } = {}) {
  const state = { t: +NOW, runs: [] };
  const links = [];
  const fake = fakeSoda({
    onCall: (args) => {
      if (args[0] === 'graph' && args[1] === 'show') return { graph: { links } };
      if (args[0] === 'graph' && args[1] === 'history') return { runs: state.runs };
    },
  });
  const t0 = await tempDir();
  const root = t0.dir;
  const agents = ag.createAgents({ makeSoda: () => fake.soda, now: () => new Date(state.t), uuid: uuids() });
  const panes = basePanes();
  const ctx = { tabId: 'tab-app', workspaceId: 'ws1', paneId: 'anchor', panes };
  await agents.startSupervisor(root, ctx, {});
  aliveAgent(panes, 'term-1');
  await agents.startWorker(root, ctx, { slug: 'w1' });
  const wp = (await ag.readLedger(root)).workers.w1.paneId;
  aliveAgent(panes, wp);
  panes.push({ id: PA, agent: 'codex', agentState: helperState, tabId: 'tab-app', workspaceId: 'ws1' });
  links.push({ id: 'trig-1', kind: 'trigger', from: `local:${wp}`, to: 'local:term-1' });
  links.push({ kind: 'supervise', from: `local:${PA}`, to: `local:${wp}` });
  if (registered) { links.length = 0; links.push({ id: 'trig-1', kind: 'trigger', from: `local:${wp}`, to: 'local:term-1' }); }
  return { state, links, fake, root, ctx, panes, wp, agents, cleanup: t0.cleanup };
}

test('完了の終了: 完了の知らせ（トリガ）が監督へ送られた後に、担当と自動の線で連なる関連するエージェントの pane を閉じる（会話 ID は残る）', async () => {
  const e = await doneEnv();
  try {
    const id = (await ag.readLedger(e.root)).workers.w1.sessionId;
    await e.agents.reportWorker(e.root, e.ctx, { slug: 'w1', status: 'done', message: '完了' });
    assert.ok((await ag.readLedger(e.root)).workers.w1.doneAt);
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0, '猶予の間は閉じない');
    e.state.t += 30000;
    e.panes.find((p) => p.id === e.wp).agentState = 'working';
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0, '作業中なら待つ');
    e.panes.find((p) => p.id === e.wp).agentState = 'idle';
    const queries = () => e.fake.of('graph', 'history').length;
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0, 'トリガがまだ送られていない（監督が作業中で待っている）間は閉じない');
    assert.equal(e.fake.of('pane', 'close').length, 0);
    assert.equal(queries(), 1);
    e.state.t += 3000;
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0);
    assert.equal(queries(), 1, 'トリガの履歴の問い合わせは 20 秒以上あける（3 秒ごとに読まない）');
    e.state.t += 21000;
    e.state.runs = [{ linkId: 'trig-1', at: +NOW - 5000, result: 'sent' }];
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0, '完了の報告より前の送信は数えない');
    assert.equal(queries(), 2);
    e.state.t += 21000;
    e.state.runs = [{ linkId: 'trig-1', at: e.state.t, result: 'sent' }];
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 1);
    assert.deepEqual(e.fake.of('pane', 'close').map((c) => c.args[2]), [PA, e.wp], '関連するエージェント → 担当の順');
    const w = (await ag.readLedger(e.root)).workers.w1;
    assert.deepEqual([w.status, w.doneAt, w.sessionId], ['stopped', '', id]);
    assert.equal(ag.agentView(w, [], new Date(e.state.t)).resumable, true, '再開できる');
  } finally { await e.cleanup(); }
});

test('完了の終了: トリガの線が無い・30 分たっても送られないときは閉じず、ログに残して以後は自動で閉じない', async () => {
  const e = await doneEnv();
  try {
    e.links.splice(0, e.links.length, { kind: 'supervise', from: `local:${PA}`, to: `local:${e.wp}` }); // トリガの線が無い
    await e.agents.reportWorker(e.root, e.ctx, { slug: 'w1', status: 'done', message: '完了' });
    e.state.t += 60000;
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0, '線が無ければ閉じない');
    e.state.t += 31 * 60000;
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0);
    const led = await ag.readLedger(e.root);
    assert.equal(led.workers.w1.noAutoClose, true);
    assert.equal(led.workers.w1.doneAt, '');
    assert.ok(led.log.some((x) => /完了の知らせが監督へ届いていないので、担当を閉じませんでした/.test(x.message)));
    assert.equal(e.fake.of('pane', 'close').length, 0);
    await e.agents.reportWorker(e.root, e.ctx, { slug: 'w1', status: 'done', message: 'もう一度' });
    assert.equal((await ag.readLedger(e.root)).workers.w1.doneAt, '', '以後その担当は自動では閉じない');
  } finally { await e.cleanup(); }
});

test('完了の終了: 自動の線で連なる関連するエージェントが作業中・承認待ちなら見送る。登録分は閉じない', async () => {
  const e = await doneEnv({ helperState: 'blocked' });
  try {
    e.state.runs = [{ linkId: 'trig-1', at: e.state.t + 1000, result: 'sent' }];
    await e.agents.reportWorker(e.root, e.ctx, { slug: 'w1', status: 'done', message: '完了' });
    e.state.t += 30000;
    e.state.runs = [{ linkId: 'trig-1', at: e.state.t, result: 'sent' }];
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0, '承認待ちの関連するエージェントがあれば見送る');
    assert.equal(e.fake.of('pane', 'close').length, 0);
    e.panes.find((p) => p.id === PA).agentState = 'idle';
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 1, '次の周期で閉じる');
  } finally { await e.cleanup(); }
});

test('完了の終了: 登録された関連するエージェントは閉じず、ログに残す', async () => {
  const e = await doneEnv();
  try {
    const PD = 'aaaa4444-0000-4000-8000-000000000004';
    e.panes.push({ id: PD, agent: 'claude', agentState: 'idle', tabId: 'tab-app', workspaceId: 'ws1' });
    // 深さ 4（自動では出ない）を、線で連なるものとして登録する
    const PB = 'aaaa2222-0000-4000-8000-000000000002', PC = 'aaaa3333-0000-4000-8000-000000000003';
    e.panes.push({ id: PB, agent: 'claude', agentState: 'idle' }, { id: PC, agent: 'claude', agentState: 'idle' });
    e.links.push({ kind: 'supervise', from: `local:${PB}`, to: `local:${PA}` }, { kind: 'supervise', from: `local:${PC}`, to: `local:${PB}` }, { kind: 'supervise', from: `local:${PD}`, to: `local:${PC}` });
    await e.agents.registerRelated(e.root, e.ctx, { slug: 'w1', paneId: PD });
    await e.agents.reportWorker(e.root, e.ctx, { slug: 'w1', status: 'done', message: '完了' });
    e.state.t += 30000;
    e.state.runs = [{ linkId: 'trig-1', at: e.state.t, result: 'sent' }];
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 1);
    assert.ok(!e.fake.of('pane', 'close').some((c) => c.args[2] === PD), '登録分は閉じない');
    assert.ok((await ag.readLedger(e.root)).log.some((x) => /登録された関連するエージェント 1 件は閉じていません/.test(x.message)));
  } finally { await e.cleanup(); }
});

test('S3: 完了の後に追加の指示を送ったら、完了後の終了は取り消す（担当宛の work-agent-prompt でも）', async () => {
  const e = await doneEnv();
  try {
    await e.agents.reportWorker(e.root, e.ctx, { slug: 'w1', status: 'done', message: '完了' });
    assert.ok((await ag.readLedger(e.root)).workers.w1.doneAt);
    await e.agents.promptWorker(e.root, e.ctx, { slug: 'w1', text: '直して' });
    assert.equal((await ag.readLedger(e.root)).workers.w1.doneAt, '');
    await e.agents.reportWorker(e.root, e.ctx, { slug: 'w1', status: 'done', message: '直した' });
    assert.ok((await ag.readLedger(e.root)).workers.w1.doneAt);
    await e.agents.promptRelated(e.root, e.ctx, { slug: 'w1', paneId: e.wp, text: 'もう一つ' });
    assert.equal((await ag.readLedger(e.root)).workers.w1.doneAt, '');
    e.state.t += 60000;
    e.state.runs = [{ linkId: 'trig-1', at: e.state.t, result: 'sent' }];
    assert.equal(await e.agents.finishDone(e.root, e.ctx), 0);
    assert.equal(e.fake.of('pane', 'close').length, 0);
  } finally { await e.cleanup(); }
});

test('S1: 起動が timeout で返っても、名前・種類が付いて動いていれば失敗にしない（pending を残して、待機で仕上げる）', async () => {
  const t0 = await tempDir();
  const root = t0.dir;
  const base = fakeSoda();
  let first = true;
  const soda = async (args, opts) => {
    if (first && args[0] === 'agent' && args[1] === 'start') {
      first = false;
      await base.soda(args, opts); // 起動は進んでいる（名前が付く）
      throw sodaErr('timeout', '時間切れ');
    }
    return base.soda(args, opts);
  };
  try {
    const agents = ag.createAgents({ makeSoda: () => soda, now: () => NOW, uuid: uuids() });
    const panes = basePanes();
    const ctx = { tabId: 'tab-app', workspaceId: 'ws1', paneId: 'anchor', panes };
    const r = await agents.startSupervisor(root, ctx, {});
    assert.equal(r.status, 'started');
    assert.match(r.warnings.join(' '), /時間がかかっています/);
    const sup = (await ag.readLedger(root)).supervisor;
    assert.deepEqual([sup.status, sup.pending], ['running', ['role']]);
    assert.equal(base.of('agent', 'prompt').length, 0, 'まだ役割は送らない');
    idleAt(panes, 'term-1');
    assert.equal(await agents.finishAll(root, ctx), 1);
    assert.equal(base.of('agent', 'prompt').length, 1);
    assert.deepEqual((await ag.readLedger(root)).supervisor.pending, []);
  } finally { await t0.cleanup(); }
});

test('S1: 再開が timeout で返っても、動いていれば failed にしない。agent_start_failed だけが「会話が無い」', async () => {
  const t0 = await tempDir();
  const root = t0.dir;
  const base = fakeSoda();
  let mode = 'ok';
  const soda = async (args, opts) => {
    if (mode !== 'ok' && args[0] === 'agent' && args[1] === 'start') {
      if (mode === 'timeout') { await base.soda(args, opts); throw sodaErr('timeout', '時間切れ'); }
      throw sodaErr('agent_start_failed', 'No conversation found');
    }
    return base.soda(args, opts);
  };
  try {
    const agents = ag.createAgents({ makeSoda: () => soda, now: () => NOW, uuid: uuids() });
    const panes = basePanes();
    const ctx = { tabId: 'tab-app', workspaceId: 'ws1', paneId: 'anchor', panes };
    await agents.startSupervisor(root, ctx, {});
    mode = 'timeout';
    const r = await agents.resumeSupervisor(root, ctx);
    assert.equal(r.status, 'resumed');
    const sup = (await ag.readLedger(root)).supervisor;
    assert.equal(sup.status, 'running');
    assert.deepEqual(sup.pending, ['note'], '再開の知らせは待機になってから届ける');
    mode = 'lost';
    await assert.rejects(agents.resumeSupervisor(root, { ...ctx, panes: basePanes() }), /No conversation found/);
    assert.equal((await ag.readLedger(root)).supervisor.status, 'failed');
  } finally { await t0.cleanup(); }
});

test('N4: 6 個を超えた後は、前に作った担当用のタブの空き pane を使い、無ければそのタブを分ける（タブ作成は最初の 1 回だけ）', async () => {
  const s = await withSupervisor();
  try {
    const mkPanes = () => { for (const k of s.fake.known) if (!s.panes.some((p) => p.id === k.id)) s.panes.push({ id: k.id, tabId: k.tabId, workspaceId: 'ws1', agent: null, virtual: !!k.virtual }); };
    const slugs = ['a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8'];
    for (const slug of slugs) {
      await s.agents.startWorker(s.root, s.ctx, { slug });
      mkPanes();
      idleAt(s.panes, (await ag.readLedger(s.root)).workers[slug].paneId);
    }
    assert.equal(s.fake.of('tab', 'create').length, 1, 'タブ作成は最初の 1 回だけ');
    const led = await ag.readLedger(s.root);
    assert.equal(led.workers.a6.tabId, 'tab-w1');
    assert.equal(led.workers.a7.tabId, 'tab-w1', '2 個目以降は同じタブを分ける');
    assert.equal(led.workers.a8.tabId, 'tab-w1');
    // 終了して空いた pane は再利用する
    const p7 = led.workers.a7.paneId;
    s.panes.find((p) => p.id === p7).agent = null;
    await s.agents.startWorker(s.root, s.ctx, { slug: 'a9' });
    assert.equal(s.fake.of('tab', 'create').length, 1);
  } finally { await s.cleanup(); }
});
test('完了の終了: 設定で止められる・done 以外の報告で取り消される・Codex で会話 ID が未取得なら見送る', async () => {
  let t = +NOW;
  const fake = fakeSoda();
  const t0 = await tempDir();
  const root = t0.dir;
  try {
    const agents = ag.createAgents({ makeSoda: () => fake.soda, now: () => new Date(t), uuid: uuids() });
    const panes = basePanes();
    const ctx = { tabId: 'tab-app', workspaceId: 'ws1', paneId: 'anchor', panes };
    await ag.saveSettings(root, { exitOnDone: false });
    await agents.startSupervisor(root, ctx, {});
    aliveAgent(panes, 'term-1');
    await agents.startWorker(root, ctx, { slug: 'w1' });
    await agents.reportWorker(root, ctx, { slug: 'w1', status: 'done', message: 'ok' });
    assert.equal((await ag.readLedger(root)).workers.w1.doneAt, '', '設定が切れていれば印を付けない');
    await ag.saveSettings(root, { exitOnDone: true, workerKind: 'codex' });
    await agents.startWorker(root, ctx, { slug: 'w2' });
    const wp2 = (await ag.readLedger(root)).workers.w2.paneId;
    aliveAgent(panes, wp2); panes.find((p) => p.id === wp2).agent = 'codex';
    await agents.reportWorker(root, ctx, { slug: 'w2', status: 'done', message: 'ok' });
    t += 30000;
    assert.equal(await agents.finishDone(root, ctx), 0);
    assert.equal(fake.of('pane', 'close').length, 0, '会話 ID が無いまま閉じると再開できなくなる');
    assert.ok((await ag.readLedger(root)).log.some((e) => /終了を見送りました/.test(e.message)));
    await agents.reportWorker(root, ctx, { slug: 'w2', status: 'question', message: '?' });
    assert.equal((await ag.readLedger(root)).workers.w2.doneAt, '');
  } finally { await t0.cleanup(); }
});

// ---- 種類の制限（導入済みだけ）・Copilot CLI・Bob Shell ------------------------------------------------

const BOB_ID = '0123456789abcdef0123456789abcdef';
const integ = (map) => ({ autoResumeEnabled: true, agents: Object.fromEntries(Object.entries(map).map(([k, v]) => [k, { cliDetected: true, ...v }])) });
const sessionPane = (kind, started, id) => ({ panes: [{ id: started[started.indexOf('--pane') + 1], tabId: 'tab-app', virtual: false, agent: { kind, name: started[0], instanceId: 'inst-1' }, agentSession: { kind, sessionId: id } }] });

test('選べる種類: integrations の installed だけ（claude・codex も含む）。needsUpdate は選べて印が付く', async () => {
  const s = await setup({ integrations: integ({ claude: { installed: true }, codex: { installed: false }, copilot: { installed: true, needsUpdate: true }, bob: { installed: false } }) });
  try {
    const k = await s.agents.availableKinds(s.root);
    assert.deepEqual(k.available, ['claude', 'copilot']);
    assert.equal(k.legacy, false);
    assert.equal(k.details.copilot.needsUpdate, true);
    assert.deepEqual((await s.agents.overview(s.root, s.panes)).kinds.available, ['claude', 'copilot']);
  } finally { await s.cleanup(); }
});

test('選べる種類: 古いサーバ（integrations を知らない = not_found）は legacy で claude・codex だけ', async () => {
  const s = await setup({ integrations: 'unsupported' });
  try {
    const k = await s.agents.availableKinds(s.root);
    assert.deepEqual(k.available, ['claude', 'codex']);
    assert.equal(k.legacy, true);
    assert.equal(k.unreadable, undefined);
    await assert.rejects(s.agents.startSupervisor(s.root, s.ctx, { kind: 'copilot' }), /導入/);
    assert.equal((await s.agents.startSupervisor(s.root, s.ctx, { kind: 'codex' })).status, 'started');
  } finally { await s.cleanup(); }
});

test('選べる種類: not_found 以外の失敗は legacy ではなく「読めなかった」（reason 付き）。copilot・bob は選べない', async () => {
  const s = await setup({ onCall: (args) => { if (args[0] === 'agent' && args[1] === 'integrations') throw new ag.SodaError('unauthorized', 'ログインが要ります'); } });
  try {
    const k = await s.agents.availableKinds(s.root);
    assert.equal(k.legacy, false);
    assert.equal(k.unreadable, true);
    assert.match(k.reason, /ログイン/);
    assert.deepEqual(k.available, ['claude', 'codex']);
    await assert.rejects(s.agents.startSupervisor(s.root, s.ctx, { kind: 'bob' }), /Bob Shell/);
    assert.equal((await s.agents.startSupervisor(s.root, s.ctx, { kind: 'claude' })).status, 'started');
  } finally { await s.cleanup(); }
});

test('設定の保存: 未導入の種類は断る。保存済みと同じ値なら通す', async () => {
  const s = await setup({ integrations: integ({ claude: { installed: true }, codex: { installed: false }, copilot: { installed: true }, bob: { installed: false } }) });
  try {
    const kinds = s.agents.availableKinds;
    await assert.rejects(ag.saveSettings(s.root, { workerKind: 'bob' }, { kinds }), /「エージェント連携」で Bob Shell を導入/);
    await assert.rejects(ag.saveSettings(s.root, { supervisorKind: 'codex' }, { kinds }), /Codex/);
    assert.equal((await ag.saveSettings(s.root, { workerKind: 'copilot' }, { kinds })).workerKind, 'copilot');
    await assert.rejects(ag.saveSettings(s.root, { workerKind: 'gemini' }, { kinds }), /のどれか/);
    // 保存済みの設定が、後で未導入になっても、同じ値の送り直しは断らない
    await ag.saveSettings(s.root, { supervisorKind: 'codex' });
    assert.equal((await ag.saveSettings(s.root, { supervisorKind: 'codex', supervisorModel: 'm' }, { kinds })).supervisorModel, 'm');
  } finally { await s.cleanup(); }
});

test('新規起動: 設定が未導入の種類を指していれば分かる誤りで断り、起動しない', async () => {
  const s = await setup({ integrations: integ({ claude: { installed: true }, codex: { installed: false }, copilot: { installed: false }, bob: { installed: false } }) });
  try {
    await ag.saveSettings(s.root, { supervisorKind: 'copilot' });
    await assert.rejects(s.agents.startSupervisor(s.root, s.ctx, {}), /「エージェント連携」で Copilot CLI を導入してください/);
    assert.equal(s.fake.of('agent', 'start').length, 0);
    await assert.rejects(s.agents.autoStart(s.root, s.ctx), /Copilot CLI/);
    await s.agents.startSupervisor(s.root, s.ctx, { kind: 'claude' });
    aliveAgent(s.panes, 'term-1');
    await assert.rejects(s.agents.startWorker(s.root, s.ctx, { slug: 'w1', kind: 'bob' }), /Bob Shell/);
    assert.equal(s.fake.of('agent', 'start').length, 1, '監督（claude）だけ');
  } finally { await s.cleanup(); }
});

test('Copilot CLI: 初回は ID なし（モデルは --model）・取り込み後の再開は --resume=<ID>。未導入になっても再開は試す', async () => {
  let started, installed = true, report = false;
  const s = await setup({
    onCall: (args) => {
      if (args[0] === 'agent' && args[1] === 'integrations') return integ({ claude: { installed: true }, copilot: { installed } });
      if (args[0] === 'agent' && args[1] === 'start') started = args.slice(2);
      if (args[0] === 'snapshot' && started && report) return sessionPane('copilot', started, CODEX_ID);
    },
  });
  try {
    await ag.saveSettings(s.root, { supervisorKind: 'copilot', supervisorModel: 'gpt-5', codexPermission: 'workspace-write', permissionMode: 'plan' });
    assert.equal((await s.agents.startSupervisor(s.root, s.ctx, {})).status, 'started');
    assert.deepEqual(started.slice(started.indexOf('--kind'), started.indexOf('--kind') + 2), ['--kind', 'copilot']);
    assert.deepEqual(started.slice(started.indexOf('--') + 1), ['--model', 'gpt-5'], '権限の指定は付けない');
    assert.equal((await ag.readLedger(s.root)).supervisor.sessionId, '', '先には決められない');
    assert.equal((await s.agents.overview(s.root, s.panes)).supervisor.sessionPending, true);
    report = true;
    assert.equal(await s.agents.captureSessions(s.root), 1);
    assert.equal((await ag.readLedger(s.root)).supervisor.sessionId, CODEX_ID);
    // 止めて、未導入になってから再開する
    s.fake.known.splice(0, s.fake.known.length, { id: 'term-1', tabId: 'tab-app' }, { id: 'anchor', tabId: 'tab-app', virtual: true });
    installed = false; started = undefined;
    const again = await s.agents.resumeSupervisor(s.root, { ...s.ctx, panes: basePanes() });
    assert.equal(again.status, 'resumed');
    assert.deepEqual(started.slice(started.indexOf('--') + 1), [`--resume=${CODEX_ID}`, '--model', 'gpt-5']);
  } finally { await s.cleanup(); }
});

test('Bob Shell: 初回は引数なし・32 桁の 16 進の ID を取り込み、再開は --resume <ID>。UUID は取り込まない', async () => {
  let started, id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';
  const s = await setup({
    onCall: (args) => {
      if (args[0] === 'agent' && args[1] === 'start') started = args.slice(2);
      if (args[0] === 'snapshot' && started) return sessionPane('bob', started, id);
    },
  });
  try {
    await ag.saveSettings(s.root, { workerKind: 'bob', workerModel: 'm1', codexPermission: 'read-only', permissionMode: 'plan' });
    await s.agents.startSupervisor(s.root, s.ctx, {});
    aliveAgent(s.panes, 'term-1');
    started = undefined;
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    assert.deepEqual(started.slice(started.indexOf('--kind'), started.indexOf('--kind') + 2), ['--kind', 'bob']);
    assert.deepEqual(started.slice(started.indexOf('--') + 1), [], 'モデル・権限は付けない');
    assert.equal(await s.agents.captureSessions(s.root), 0, 'UUID 形式は Bob の ID ではない');
    id = BOB_ID;
    assert.equal(await s.agents.captureSessions(s.root), 1);
    assert.equal((await ag.readLedger(s.root)).workers.w1.sessionId, BOB_ID);
    s.fake.known.splice(0, s.fake.known.length, { id: 'term-1', tabId: 'tab-app' }, { id: 'anchor', tabId: 'tab-app', virtual: true });
    started = undefined;
    const panes = basePanes();
    aliveAgent(panes, 'term-1');
    const r = await s.agents.resumeWorker(s.root, { ...s.ctx, panes }, { slug: 'w1' });
    assert.equal(r.status, 'resumed');
    assert.deepEqual(started.slice(started.indexOf('--') + 1), ['--resume', BOB_ID]);
  } finally { await s.cleanup(); }
});

test('会話 ID の検査: 種類ごと（Bob は 32 桁の 16 進。ほかは UUID）', () => {
  assert.equal(ag.sessionIdOk('bob', BOB_ID), true);
  assert.equal(ag.sessionIdOk('bob', BOB_ID.toUpperCase()), true);
  for (const bad of ['', BOB_ID.slice(1), `${BOB_ID}0`, 'g'.repeat(32), '../'.padEnd(32, 'a'), 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', `${BOB_ID}\n`]) assert.equal(ag.sessionIdOk('bob', bad), false, bad);
  for (const kind of ['claude', 'codex', 'copilot']) {
    assert.equal(ag.sessionIdOk(kind, CODEX_ID), true);
    assert.equal(ag.sessionIdOk(kind, BOB_ID), false);
  }
  assert.equal(ag.sessionIdOk('gemini', CODEX_ID), false);
});

test('台帳の読み込み: Bob の 32 桁 ID は残り、不正な ID は捨てる', () => {
  assert.equal(ag.cleanAgent({ name: 'n', kind: 'bob', sessionId: BOB_ID }, null).sessionId, BOB_ID);
  assert.equal(ag.cleanAgent({ name: 'n', kind: 'bob', sessionId: CODEX_ID }, null).sessionId, '');
  assert.equal(ag.cleanAgent({ name: 'n', kind: 'copilot', sessionId: BOB_ID }, null).sessionId, '');
  assert.equal(ag.cleanAgent({ name: 'n', kind: 'copilot', sessionId: CODEX_ID }, null).sessionId, CODEX_ID);
});
