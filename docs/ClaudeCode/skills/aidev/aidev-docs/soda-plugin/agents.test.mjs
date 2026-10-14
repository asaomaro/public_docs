import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lstat, mkdir, readFile, readdir, symlink, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import * as ag from './agents.mjs';
import { tempDir } from './testkit.mjs';

const NOW = new Date('2026-10-15T00:00:00.000Z');
const uuids = () => { let n = 0; return () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`; };
const sodaErr = (code, message) => new ag.SodaError(code, message);

/** sodactl の代役。呼び出しを記録し、コマンドごとに返す値を決める。 */
function fakeSoda({ onCall } = {}) {
  const calls = [];
  const agentsByPane = new Map(); // paneId -> { name, tabId }
  let tabs = 0;
  let instances = 0;
  const soda = async (args, opts) => {
    calls.push({ args, opts });
    if (onCall) { const r = await onCall(args, opts); if (r !== undefined) return r; }
    const key = args.slice(0, 2).join(' ');
    switch (key) {
      case 'snapshot': return { panes: [{ id: 'term-1', tabId: 'tab-app', virtual: false, status: 'running', agent: null }, { id: 'anchor', tabId: 'tab-app', virtual: true }] };
      case 'pane split': return { pane: { id: 'term-split', tabId: 'tab-app', virtual: false } };
      case 'tab create': { tabs++; return { tab: { id: `tab-w${tabs}`, workspaceId: 'ws1' }, pane: { id: `pane-w${tabs}`, tabId: `tab-w${tabs}`, virtual: false } }; }
      case 'agent start': {
        const paneId = args[args.indexOf('--pane') + 1];
        const tabId = paneId.startsWith('pane-w') ? 'tab-w' + paneId.slice(6) : 'tab-app';
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
      case 'graph link': return { link: { id: 'link' } };
      default: throw new Error(`想定外: ${args.join(' ')}`);
    }
  };
  return { soda, calls, of: (a, b) => calls.filter((c) => c.args[0] === a && (b === undefined || c.args[1] === b)) };
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
  assert.deepEqual(Object.keys(l.workers), ['ok-1']);
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
    assert.deepEqual(await ag.loadSettings(root), { supervisorModel: '', workerModel: '', permissionMode: '', autoStartSupervisor: true, supervisorKind: 'claude', workerKind: 'claude', codexPermission: '' });
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
    assert.match(r.message, /作業画面で答えてください/);
    const led = await ag.readLedger(root);
    assert.equal(led.supervisor.status, 'blocked');
    assert.equal(led.supervisor.sessionId, '00000000-0000-4000-8000-000000000001', '台帳は残す');
    assert.match(led.supervisor.error, /信頼/);
  } finally { await cleanup(); }
});

test('監督の起動: 失敗は台帳に残し、以前のセッション ID は消さない', async () => {
  let fail = false;
  const { root, cleanup, agents, ctx, panes } = await setup({
    onCall: (args) => { if (fail && args[0] === 'agent' && args[1] === 'start') throw sodaErr('agent_pane_busy', '前面が別のコマンド'); },
  });
  try {
    await agents.startSupervisor(root, ctx, {});
    const first = (await ag.readLedger(root)).supervisor.sessionId;
    fail = true; // サーバが落ちて会話は止まっている（pane にエージェントは居ない）
    await assert.rejects(agents.startSupervisor(root, ctx, {}), /前面が別のコマンド/);
    const led = await ag.readLedger(root);
    assert.equal(led.supervisor.sessionId, first);
    assert.match(led.supervisor.error, /前面/);
    assert.equal(led.log.at(-1).kind, 'error');
    assert.ok(panes);
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
    assert.match(note, /再開しました。.aidev と担当の状況を確かめてから、指示を待ってください/);
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

test('担当の起動: 監督が必要 → tab create → agent start --session-id → 役割 → 線 3 本 → 台帳', async () => {
  const s = await setup();
  try {
    await assert.rejects(s.agents.startWorker(s.root, s.ctx, { slug: '20261015-feature', instruction: '' }), /監督が動いていません/);
    await s.agents.startSupervisor(s.root, s.ctx, {});
    aliveAgent(s.panes, 'term-1');
    const before = s.fake.calls.length;
    const r = await s.agents.startWorker(s.root, s.ctx, { slug: '20261015-feature', instruction: '要件から始めて' });
    assert.equal(r.status, 'started');
    const calls = s.fake.calls.slice(before).map((c) => c.args);
    assert.deepEqual(calls[0], ['tab', 'create', '--workspace', 'ws1', '--label', 'aidev:20261015-feature']);
    const name = ag.workerName(s.root, '20261015-feature');
    assert.match(name, /^aidev-w-[0-9a-f]{4}-[a-z0-9-]+-[0-9a-f]{4}$/);
    assert.ok(name.length <= 32);
    assert.deepEqual(calls[1].slice(0, 8), ['agent', 'start', name, '--kind', 'claude', '--pane', 'pane-w1', '--timeout']);
    assert.deepEqual(calls[1].slice(calls[1].indexOf('--')), ['--', '--session-id', '00000000-0000-4000-8000-000000000002']);
    assert.equal(calls[2][0] + calls[2][1], 'agentprompt');
    const file = /"(.+worker-20261015-feature-[^"]+\.md)"/.exec(calls[2][3])[1];
    const body = await readFile(file, 'utf8');
    assert.match(body, /aidev-00-start/);
    assert.match(body, /要件から始めて/);
    assert.match(body, /worker-report --tab tab-app/);
    assert.match(body, new RegExp(ag.supervisorName(s.root)));
    const links = calls.filter((c) => c[0] === 'graph');
    assert.equal(links.length, 3);
    for (const l of links) assert.deepEqual(l.slice(0, 5), ['graph', 'link', 'add', 'pane-w1', 'term-1']);
    assert.ok(links[0].includes('supervise'));
    assert.ok(links[1].includes('approval') && links[1].includes('notify'));
    const trigger = links[2];
    assert.ok(trigger.includes('trigger') && trigger.includes('done'));
    assert.equal(trigger[trigger.indexOf('--output') + 1], '60');
    assert.equal(trigger[trigger.indexOf('--when-busy') + 1], 'wait');
    const promptArg = trigger.find((a) => a.startsWith('--prompt='));
    assert.match(promptArg, /aidev の担当 20261015-feature が一区切りつきました。結果を確かめ、次を判断してください。\n\{output\}/);
    assert.ok(trigger.includes('--json'), 'graph は --json で JSON を受ける');
    const led = await ag.readLedger(s.root);
    const w = led.workers['20261015-feature'];
    assert.equal(w.sessionId, '00000000-0000-4000-8000-000000000002');
    assert.equal(w.tabId, 'tab-w1');
    assert.equal(w.paneId, 'pane-w1');
    assert.equal(w.status, 'running');
  } finally { await s.cleanup(); }
});

test('担当の起動: 同じ slug が生きていれば断る・止まっていれば再開を案内・不正な slug は断る', async () => {
  const s = await withSupervisor();
  try {
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    aliveAgent(s.panes, 'pane-w1');
    await assert.rejects(s.agents.startWorker(s.root, s.ctx, { slug: 'w1' }), /すでに動いています/);
    s.panes.find((p) => p.id === 'pane-w1').agent = null;
    await assert.rejects(s.agents.startWorker(s.root, s.ctx, { slug: 'w1' }), /再開（worker-resume）を使ってください/);
    await assert.rejects(s.agents.resumeWorker(s.root, s.ctx, { slug: 'nope' }), /記録がありません/);
  } finally { await s.cleanup(); }
});

test('担当の再開: 新しい端末タブで --resume・線を結び直し・再開の知らせ', async () => {
  const s = await withSupervisor();
  try {
    await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    const id = (await ag.readLedger(s.root)).workers.w1.sessionId;
    const before = s.fake.calls.length;
    const r = await s.agents.resumeWorker(s.root, s.ctx, { slug: 'w1' });
    assert.equal(r.status, 'resumed');
    const calls = s.fake.calls.slice(before).map((c) => c.args);
    assert.deepEqual(calls[0].slice(0, 2), ['tab', 'create']);
    const start = calls.find((c) => c[0] === 'agent' && c[1] === 'start');
    assert.deepEqual(start.slice(start.indexOf('--')), ['--', '--resume', id]);
    assert.equal(calls.filter((c) => c[0] === 'graph').length, 3);
    const note = calls.find((c) => c[0] === 'agent' && c[1] === 'prompt')[3];
    assert.match(note, /再開しました/);
    const w = (await ag.readLedger(s.root)).workers.w1;
    assert.equal(w.sessionId, id);
    assert.equal(w.paneId, 'pane-w2');
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
    aliveAgent(s.panes, 'pane-w1');
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
    s.panes.find((p) => p.id === 'pane-w1');
    const again = await s.agents.startWorker(s.root, s.ctx, { slug: 'w1' });
    assert.equal(again.status, 'started');
  } finally { await s.cleanup(); }
});

test('設定: エージェントの種類と Codex の権限は固定の選択肢だけ', () => {
  assert.equal(ag.normalizeSettings({ workerKind: 'codex' }).workerKind, 'codex');
  for (const bad of [{ workerKind: 'gemini' }, { supervisorKind: '' }, { codexPermission: 'danger-full-access' }, { codexPermission: 5 }]) assert.throws(() => ag.normalizeSettings(bad), Error, JSON.stringify(bad));
  assert.equal(ag.normalizeSettings({ codexPermission: 'read-only' }).codexPermission, 'read-only');
});
