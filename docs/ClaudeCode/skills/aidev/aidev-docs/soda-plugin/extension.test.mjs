import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFile, spawn } from 'node:child_process';
import { readFile, stat } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { promisify } from 'node:util';
import { sampleProject, tempDir } from './testkit.mjs';

const execute = promisify(execFile);
const HERE = dirname(fileURLToPath(import.meta.url));
const EXTENSION = join(HERE, 'extension.mjs');

/** 偽のホスト: 拡張を子プロセスで動かし、NDJSON の要求を記録して、ext.result を返す。 */
async function startHost({ scriptEnabled = true, reply = {} } = {}) {
  const home = await tempDir('aidev-home-');
  const child = spawn(process.execPath, [EXTENSION], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, SODA_SERVER_URL: '', HOME: home.dir },
  });
  const requests = [];
  let errors = '';
  child.stderr.on('data', (c) => { errors += c; });
  const lines = createInterface({ input: child.stdout });
  const send = (m) => child.stdin.write(JSON.stringify(m) + '\n');
  lines.on('line', (line) => {
    const r = JSON.parse(line);
    requests.push(r);
    if (r.id !== undefined) send({ type: 'ext.result', id: r.id, ok: true, result: reply[r.method] ?? {} });
  });
  send({ type: 'ext.hello', v: 1, extension: { scope: 'user', id: 'aidev' }, display: { scriptEnabled } });
  const waitFor = async (pred, what, ms = 8000) => {
    const until = Date.now() + ms;
    while (Date.now() < until) { const hit = pred(); if (hit) return hit; await new Promise((r) => setTimeout(r, 15)); }
    throw new Error(`時間切れ: ${what}\nrequests=${JSON.stringify(requests.map((r) => r.method + ':' + (r.params?.name ?? '')))}\nstderr=${errors}`);
  };
  const find = (method, name) => requests.find((r) => r.method === method && (name === undefined || r.params?.name === name));
  const stop = async () => {
    child.stdin.end();
    await new Promise((r) => child.once('exit', r));
    await home.cleanup();
  };
  return { send, requests, waitFor, find, stop, child, errors: () => errors };
}
const anchor = (dir, extra = {}) => ({ id: 'anchor-1', tabId: 'tab-1', workspaceId: 'ws-1', workspaceLabel: 'ws', projectDir: dir, virtual: true, agent: null, plugin: { extensionKey: 'user:aidev', display: 'aidev', terminalDisplay: 'aidev-terminal' }, ...extra });
const terminal = (dir, extra = {}) => ({ id: 'term-1', tabId: 'tab-1', workspaceId: 'ws-1', projectDir: dir, agent: null, ...extra });
const sends = (h) => h.requests.filter((r) => r.method === 'display.send').map((r) => r.params.data);

test('ext.hello → app.register（公開操作）・ext.panes → アプリ画面と端末版が出る', async () => {
  const { dir, cleanup } = await tempDir();
  const h = await startHost();
  try {
    await sampleProject(dir);
    const reg = await h.waitFor(() => h.find('app.register'), 'app.register');
    assert.equal(reg.params.operations.length, 15);
    assert.ok(reg.params.operations.some((o) => o.name === 'worker-start'));
    h.send({ type: 'ext.panes', panes: [anchor(dir), terminal(dir)] });
    const main = await h.waitFor(() => h.find('display.set', 'aidev'), 'display.set aidev');
    assert.equal(main.params.paneId, 'anchor-1');
    assert.equal(main.params.format, 'script-html');
    assert.match(main.params.content, /監督を起動/);
    assert.ok(!main.params.content.includes('20261001-active-a'), 'データは HTML に埋め込まない（display.send で送る）');
    const term = await h.waitFor(() => h.find('display.set', 'aidev-terminal'), 'display.set aidev-terminal');
    assert.equal(term.params.format, 'markdown');
    assert.match(term.params.content, /20261001-active-a/);
    assert.equal(h.errors(), '');
  } finally { await h.stop(); await cleanup(); }
});

test('画面が ready を返すと、状態と一覧が display.send で届く・選ぶと詳細と文書が届く', async () => {
  const { dir, cleanup } = await tempDir();
  const h = await startHost();
  try {
    await sampleProject(dir);
    h.send({ type: 'ext.panes', panes: [anchor(dir)] });
    await h.waitFor(() => h.find('display.set', 'aidev'), 'display.set');
    assert.equal(sends(h).length, 0, 'ready の前には送らない');
    h.send({ type: 'display.action', paneId: 'anchor-1', name: 'aidev', action: 'ready', data: {}, source: 'script' });
    const state = await h.waitFor(() => sends(h).find((d) => d.type === 'state'), 'state');
    assert.equal(state.state.available, true);
    assert.equal(state.state.summary.active, 2, 'active-a と、読める行だけで active になる weird-e');
    assert.equal(state.state.current, '20261001-active-a');
    const works = await h.waitFor(() => sends(h).find((d) => d.type === 'list' && d.name === 'works'), 'works');
    assert.equal(works.items.length, 5);
    assert.equal(works.parts, 1);
    await h.waitFor(() => sends(h).find((d) => d.type === 'list' && d.name === 'workers'), 'workers');
    await h.waitFor(() => sends(h).find((d) => d.type === 'list' && d.name === 'backlog'), 'backlog');

    h.send({ type: 'display.action', paneId: 'anchor-1', name: 'aidev', action: 'select', data: { slug: '20261001-active-a' }, source: 'script' });
    const detail = await h.waitFor(() => sends(h).find((d) => d.type === 'detail'), 'detail');
    assert.equal(detail.detail.slug, '20261001-active-a');
    assert.equal(detail.detail.phases.find((p) => p.phase === 'coding').status, 'current');
    const tasks = await h.waitFor(() => sends(h).find((d) => d.type === 'list' && d.name === 'tasks'), 'tasks');
    assert.equal(tasks.key, '20261001-active-a');
    assert.equal(tasks.items.length, 3);
    const events = await h.waitFor(() => sends(h).find((d) => d.type === 'list' && d.name === 'events'), 'events');
    assert.equal(events.items.length, 30);

    h.send({ type: 'display.action', paneId: 'anchor-1', name: 'aidev', action: 'doc', data: { slug: '20261001-active-a', name: 'requirements.md' }, source: 'script' });
    const doc = await h.waitFor(() => sends(h).find((d) => d.type === 'doc'), 'doc');
    assert.match(doc.text, /# 要件/);
    h.send({ type: 'display.action', paneId: 'anchor-1', name: 'aidev', action: 'doc', data: { slug: '20261001-active-a', name: '../state.yml' }, source: 'script' });
    const notice = await h.waitFor(() => sends(h).find((d) => d.type === 'notice'), 'notice');
    assert.equal(notice.level, 'error');
    assert.equal(h.errors(), '');
  } finally { await h.stop(); await cleanup(); }
});

test('app.call: works-list・report が動き、対象や入力が不正なら ok:false で返す', async () => {
  const { dir, cleanup } = await tempDir();
  const h = await startHost();
  try {
    await sampleProject(dir);
    h.send({ type: 'ext.panes', panes: [anchor(dir), terminal(dir)] });
    await h.waitFor(() => h.find('display.set', 'aidev'), 'display.set');
    const target = { paneId: 'anchor-1', tabId: 'tab-1', workspaceId: 'ws-1' };
    const result = (callId) => h.waitFor(() => h.requests.find((r) => r.method === 'app.result' && r.params.callId === callId), `app.result ${callId}`);

    h.send({ type: 'app.call', callId: 'c1', operation: 'works-list', params: {}, target });
    const r1 = (await result('c1')).params;
    assert.equal(r1.ok, true);
    assert.deepEqual(r1.result.works.map((w) => w.slug).sort(), ['20260601-weird-e', '20261001-active-a']);

    h.send({ type: 'app.call', callId: 'c2', operation: 'works-list', params: { all: true }, target });
    assert.equal((await result('c2')).params.result.works.length, 5);

    h.send({ type: 'app.call', callId: 'c3', operation: 'worker-start', params: { slug: '../etc' }, target });
    const r3 = (await result('c3')).params;
    assert.equal(r3.ok, false);
    assert.match(r3.error, /slug/);

    h.send({ type: 'app.call', callId: 'c4', operation: 'works-list', params: {}, target: { paneId: 'nope', tabId: 'tab-1', workspaceId: 'ws-1' } });
    assert.equal((await result('c4')).params.ok, false);

    h.send({ type: 'app.call', callId: 'c5', operation: 'works-list', params: {}, target: { ...target, tabId: 'other-tab' } });
    assert.equal((await result('c5')).params.ok, false, 'タブが食い違う対象は受けない');

    h.send({ type: 'app.call', callId: 'c6', operation: 'delete-everything', params: {}, target });
    assert.match((await result('c6')).params.error, /未対応/);

    h.send({ type: 'app.call', callId: 'c7', operation: 'supervisor-prompt', params: { text: '状況をまとめて' }, target });
    const r7 = (await result('c7')).params;
    assert.equal(r7.ok, false);
    assert.match(r7.error, /監督が動いていません/);

    h.send({ type: 'app.call', callId: 'c8', operation: 'report', params: { message: '承認をください', level: 'question' }, target });
    assert.equal((await result('c8')).params.ok, true);
    h.send({ type: 'app.call', callId: 'c9', operation: 'log-list', params: {}, target });
    const log = (await result('c9')).params.result.log;
    assert.equal(log[0].level, 'question');
    assert.equal(log[0].from, 'supervisor');
    assert.equal(h.errors(), '');
  } finally { await h.stop(); await cleanup(); }
});

test('CLI から変更した結果が画面にすぐ反映される（ready 済みの画面へ state が届く）', async () => {
  const { dir, cleanup } = await tempDir();
  const h = await startHost();
  try {
    await sampleProject(dir);
    h.send({ type: 'ext.panes', panes: [anchor(dir)] });
    await h.waitFor(() => h.find('display.set', 'aidev'), 'display.set');
    h.send({ type: 'display.action', paneId: 'anchor-1', name: 'aidev', action: 'ready', data: {}, source: 'script' });
    await h.waitFor(() => sends(h).find((d) => d.type === 'state'), 'state');
    h.send({ type: 'app.call', callId: 'r1', operation: 'report', params: { message: '画面に出るはず' }, target: { paneId: 'anchor-1', tabId: 'tab-1', workspaceId: 'ws-1' } });
    await h.waitFor(() => sends(h).filter((d) => d.type === 'state').some((d) => d.state.log.some((e) => e.message === '画面に出るはず')), '反映された state');
  } finally { await h.stop(); await cleanup(); }
});

test('スクリプトが無効なら、読むだけの静的な画面にする（display.send は使わない）', async () => {
  const { dir, cleanup } = await tempDir();
  const h = await startHost({ scriptEnabled: false });
  try {
    await sampleProject(dir);
    h.send({ type: 'ext.panes', panes: [anchor(dir)] });
    const main = await h.waitFor(() => h.find('display.set', 'aidev'), 'display.set');
    assert.equal(main.params.format, 'html');
    assert.match(main.params.content, /20261001-active-a/);
    assert.match(main.params.content, /スクリプトが動く表示/);
    assert.equal(sends(h).length, 0);
  } finally { await h.stop(); await cleanup(); }
});

test('帯・パネルのビュー（views.progress）と端末版のビュー、消えたら閉じる', async () => {
  const { dir, cleanup } = await tempDir();
  const h = await startHost();
  try {
    await sampleProject(dir);
    const view = { id: 'v1', extensionKey: 'user:aidev', viewId: 'progress', display: 'aidev-view-1', terminalDisplay: 'aidev-view-t-1', placement: 'band-bottom', paneId: 'term-1' };
    h.send({ type: 'ext.panes', panes: [terminal(dir, { views: [view] })] });
    const band = await h.waitFor(() => h.find('display.set', 'aidev-view-1'), 'band');
    assert.equal(band.params.paneId, 'term-1');
    assert.equal(band.params.kind, 'band');
    assert.equal(band.params.edge, 'bottom');
    assert.equal(band.params.format, 'html');
    assert.match(band.params.content, /進行中 2 件/);
    const tview = await h.waitFor(() => h.find('display.set', 'aidev-view-t-1'), 'terminal view');
    assert.equal(tview.params.format, 'markdown');
    assert.equal(h.find('display.set', 'aidev'), undefined, 'アンカーが無ければアプリ画面は出さない');

    h.send({ type: 'ext.panes', panes: [terminal(dir, { views: [{ ...view, placement: 'right' }] })] });
    await h.waitFor(() => h.requests.find((r) => r.method === 'display.set' && r.params.name === 'aidev-view-1' && r.params.kind === 'panel' && r.params.dock === 'right'), 'panel');

    h.send({ type: 'ext.panes', panes: [terminal(dir)] }); // インスタンスの削除
    await h.waitFor(() => h.requests.some((r) => r.method === 'display.close' && r.params.name === 'aidev-view-1'), 'close band');
    await h.waitFor(() => h.requests.some((r) => r.method === 'display.close' && r.params.name === 'aidev-view-t-1'), 'close terminal view');
  } finally { await h.stop(); await cleanup(); }
});

test('他の拡張の pane・PJ の無い pane は扱わない', async () => {
  const { dir, cleanup } = await tempDir();
  const h = await startHost();
  try {
    await sampleProject(dir);
    h.send({ type: 'ext.panes', panes: [
      anchor(dir, { id: 'other', plugin: { extensionKey: 'user:other', display: 'aidev' } }),
      anchor(dir, { id: 'nodir', projectDir: undefined }),
      anchor(dir, { id: 'wrongdisplay', plugin: { extensionKey: 'user:aidev', display: 'x' } }),
    ] });
    await new Promise((r) => setTimeout(r, 300));
    assert.equal(h.requests.filter((r) => r.method === 'display.set').length, 0);
  } finally { await h.stop(); await cleanup(); }
});

test('標準入力が閉じたら終了コード 0 で終わる（SIGTERM でも）', async () => {
  const h = await startHost();
  await h.waitFor(() => h.find('app.register'), 'app.register');
  const code = await new Promise((resolve) => { h.child.once('exit', resolve); h.child.stdin.end(); });
  assert.equal(code, 0);
  const again = await startHost();
  await again.waitFor(() => again.find('app.register'), 'app.register');
  const sig = await new Promise((resolve) => { again.child.once('exit', (c) => resolve(c)); again.child.kill('SIGTERM'); });
  assert.equal(sig, 0);
});

// ---- パッケージ ---------------------------------------------------------------------------------

test('soda-plugin.json: 設計どおりの宣言で、files が実在する', async () => {
  const m = JSON.parse(await readFile(join(HERE, 'soda-plugin.json'), 'utf8'));
  assert.equal(m.schemaVersion, 1);
  assert.equal(m.id, 'aidev');
  assert.equal(m.name, 'aidev');
  assert.equal(m.version, '0.1.0');
  assert.equal(m.entry, 'extension.mjs');
  assert.deepEqual(m.allow, ['script-html']);
  assert.deepEqual(m.tabView, { title: 'aidev', display: 'aidev', terminalDisplay: 'aidev-terminal' });
  assert.deepEqual(m.views, [{ id: 'progress', title: 'aidev の進捗', targets: ['tab'], placements: ['band-bottom', 'band-top', 'right', 'left', 'float'], terminal: { format: 'markdown' } }]);
  assert.ok(m.files.includes(m.entry));
  assert.ok(m.files.length <= 128);
  assert.equal(new Set(m.files).size, m.files.length);
  for (const f of m.files) {
    assert.ok(!f.startsWith('/') && !f.split('/').includes('..'), f);
    assert.ok((await stat(join(HERE, f))).isFile(), f);
    assert.ok(!/\.test\.mjs$/.test(f) && f !== 'testkit.mjs', 'テストは配布物に入れない');
  }
  // 配布物の .mjs が import する先がすべて files にある（依存なし）
  for (const f of m.files.filter((x) => x.endsWith('.mjs'))) {
    const src = await readFile(join(HERE, f), 'utf8');
    for (const [, spec] of src.matchAll(/from '([^']+)'/g)) {
      if (spec.startsWith('node:')) continue;
      assert.ok(spec.startsWith('./'), `${f}: Node 標準ライブラリだけ（${spec}）`);
      assert.ok(m.files.includes(spec.slice(2)), `${f} が ${spec} を import しているが files に無い`);
    }
  }
});

test('sodactl plugin pack <根> --out <tmp> が通る', async (t) => {
  try { await execute('sodactl', ['--help']); } catch (e) { if (e.code === 'ENOENT') return t.skip('sodactl が PATH に無い'); }
  const { dir, cleanup } = await tempDir();
  try {
    const out = join(dir, 'aidev.sodaplugin');
    const { stdout } = await execute('sodactl', ['plugin', 'pack', HERE, '--out', out]);
    assert.equal(JSON.parse(stdout).id, 'aidev');
    const pkg = JSON.parse(await readFile(out, 'utf8'));
    assert.equal(pkg.format, 'sodashitsu-plugin');
    assert.equal(pkg.manifest.id, 'aidev');
    assert.deepEqual(pkg.files.map((f) => f.path).sort(), [...pkg.manifest.files].sort());
  } finally { await cleanup(); }
});
