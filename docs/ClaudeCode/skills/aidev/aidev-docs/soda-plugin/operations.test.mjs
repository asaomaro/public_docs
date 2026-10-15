import { test } from 'node:test';
import assert from 'node:assert/strict';
import { OPERATIONS, TEXT_MAX_BYTES, buildModel, createOperations, fromUi, summarize, validateParams } from './operations.mjs';
import { chunkItems, chunkText, terminalMarkdown, uiModel, bandHtml, staticHtml, appHtml, esc } from './ui.mjs';

const bad = (name, params, pattern) => assert.throws(() => validateParams(name, params), pattern ?? Error, `${name} ${JSON.stringify(params).slice(0, 80)}`);

test('すべての公開操作に検証がある（入力スキーマが閉じている）', () => {
  assert.equal(OPERATIONS.length, 19);
  assert.deepEqual(OPERATIONS.map((o) => o.name).sort(), [
    'agents-list', 'backlog-list', 'log-list', 'refresh', 'report', 'supervisor-prompt', 'supervisor-resume', 'supervisor-start',
    'work-agent-prompt', 'work-agent-read', 'work-agent-register', 'work-agents', 'work-doc', 'work-get',
    'worker-prompt', 'worker-report', 'worker-resume', 'worker-start', 'works-list',
  ]);
  for (const op of OPERATIONS) {
    assert.equal(op.inputSchema.type, 'object', op.name);
    assert.equal(op.inputSchema.additionalProperties, false, op.name);
    assert.ok(op.description.length > 5 && op.description.length <= 500, op.name);
    assert.ok(JSON.stringify(op.inputSchema).length < 16 * 1024);
  }
  assert.equal(OPERATIONS.length <= 32, true);
});

test('slug: 英数字と . _ - の 1〜128 文字（読み取り側と同じ書式。日付つきも可）', () => {
  assert.equal(validateParams('worker-start', { slug: '20261015-aidev-plugin' }).slug, '20261015-aidev-plugin');
  for (const slug of ['a', 'A', 'a_b', 'a.b', 'Feature-1', 'a'.repeat(128)]) assert.equal(validateParams('worker-resume', { slug }).slug, slug);
  for (const slug of ['', '-a', '.a', '_a', 'a b', 'a/b', '../x', 'a\\b', 'a'.repeat(129), 5, null, undefined, 'あ', 'a;rm']) bad('worker-resume', { slug });
  bad('worker-prompt', { slug: 'x;rm', text: 'a' });
});

test('指示・報告: 16 KiB まで・空・制御文字・型を断る', () => {
  assert.equal(TEXT_MAX_BYTES, 16384);
  assert.equal(validateParams('supervisor-prompt', { text: ' 状況をまとめて \n' }).text, '状況をまとめて');
  assert.equal(validateParams('supervisor-prompt', { text: 'a'.repeat(16384) }).text.length, 16384);
  bad('supervisor-prompt', { text: 'a'.repeat(16385) }, /16 KiB/);
  bad('supervisor-prompt', { text: 'あ'.repeat(5462) }, /16 KiB/); // 3 バイト文字は 16 KiB を超える
  bad('supervisor-prompt', { text: '   ' }, /空/);
  bad('supervisor-prompt', { text: 'a\u0000b' }, /制御文字/);
  bad('supervisor-prompt', { text: 'a\u001b[31m' }, /制御文字/);
  bad('supervisor-prompt', { text: 5 }, /文字列/);
  bad('supervisor-prompt', {}, /文字列/);
  assert.equal(validateParams('supervisor-prompt', { text: '改行\nと\tタブは可' }).text.includes('\n'), true);
  bad('worker-start', { slug: 'ok', instruction: 'a'.repeat(16385) }, /16 KiB/);
  assert.equal(validateParams('worker-start', { slug: 'ok' }).instruction, '');
});

test('enum・範囲・未知のキー・オブジェクトでない入力', () => {
  assert.equal(validateParams('worker-report', { slug: 'a', status: 'question', message: 'm' }).status, 'question');
  for (const status of ['', 'ok', 'DONE', 'progress ', 5, undefined]) bad('worker-report', { slug: 'a', status, message: 'm' }, /status/);
  assert.equal(validateParams('report', { message: 'm' }).level, 'info');
  bad('report', { message: 'm', level: 'fatal' }, /level/);
  assert.equal(validateParams('log-list', {}).limit, 50);
  for (const limit of [0, -1, 301, 1.5, '5']) bad('log-list', { limit }, /limit/);
  bad('works-list', { all: 'yes' }, /all/);
  bad('works-list', { extra: 1 }, /知らないパラメータ/);
  bad('refresh', { x: 1 });
  bad('agents-list', [1]);
  bad('agents-list', 'str');
  bad('no-such-op', {}, /未対応/);
  assert.deepEqual(validateParams('refresh', undefined), {});
  assert.equal(validateParams('supervisor-start', { model: 'claude-opus-4-1' }).model, 'claude-opus-4-1');
  bad('supervisor-start', { model: 'a b' }, /モデル名/);
  bad('supervisor-start', { model: '--dangerously' + '-x y' }, /モデル名/);
  bad('worker-start', { slug: 'a', model: 'm'.repeat(65) }, /モデル名/);
});

test('文書名・作業名: パスの成分を拒否する', () => {
  assert.deepEqual(validateParams('work-doc', { slug: '20261001-active-a', name: 'design.md' }), { slug: '20261001-active-a', name: 'design.md' });
  for (const name of ['../a.md', 'a/b.md', 'a\\b.md', 'design.txt', '', '.md.', 'a..md', 'x\0.md', 5]) bad('work-doc', { slug: 'a', name }, /文書名|知らない/);
  for (const slug of ['../x', 'a/b', '', '.hidden', 'a'.repeat(129)]) bad('work-get', { slug }, /作業名/);
});

// ---- 操作の本体（偽のデータ・偽のエージェント） -----------------------------------------------------

function fakes() {
  const log = [];
  const overview = { available: true, works: [
    { slug: 'a', state: 'active', current: 'coding', next: 'test', mode: 'autonomous', profile: 'full', tasks: { done: 1, total: 2 }, isCurrent: true, approved: [], dependsOn: [], deps: 'ok', broken: false },
    { slug: 'b', state: 'done', current: 'deliver', next: '', mode: '', profile: '', tasks: { done: 2, total: 2 }, isCurrent: false, approved: [], dependsOn: [], deps: 'ok', broken: false },
  ], total: 2, truncated: false, current: 'a', backlog: [{ file: 'r.md', todo: 3, done: 1, items: ['x'] }], cli: true };
  const data = {
    loadOverview: async (root, deps) => { log.push(['overview', root, deps]); return overview; },
    loadWorkDetail: async (root, slug) => ({ slug, state: 'active', tasksList: [], events: [], docs: [] }),
    loadDoc: async (root, slug, name) => ({ slug, name, text: 'hi', truncated: false, size: 2 }),
  };
  const agents = {
    overview: async () => ({ supervisor: { status: 'idle', alive: true, name: 's', sessionId: 'x' }, workers: [{ slug: 'a', status: 'working', alive: true }], settings: {}, log: [{ level: 'question', message: '?' }] }),
    startSupervisor: async (root, ctx, p) => (log.push(['startSupervisor', p]), { status: 'started' }),
    resumeSupervisor: async () => ({ status: 'resumed' }),
    promptSupervisor: async (root, ctx, p) => (log.push(['promptSupervisor', p]), { status: 'sent' }),
    startWorker: async (root, ctx, p) => (log.push(['startWorker', p]), { status: 'started' }),
    resumeWorker: async () => ({ status: 'resumed' }),
    promptWorker: async (root, ctx, p) => (log.push(['promptWorker', p]), { status: 'sent' }),
    reportWorker: async (root, ctx, p) => (log.push(['reportWorker', p]), { status: 'recorded' }),
    report: async (root, p) => (log.push(['report', p]), { status: 'recorded' }),
    logList: async (root, limit) => ({ log: [], limit }),
    delegate: async (root, ctx, slug) => ({ status: 'sent', slug }),
  };
  return { data, agents, log, ops: createOperations({ data, agents }) };
}
const ctx = { root: '/proj', tabId: 't', workspaceId: 'w', paneId: 'p', panes: [] };

test('works-list: all を省くと進行中だけ・担当の状態を付ける', async () => {
  const { ops } = fakes();
  const active = await ops.call('works-list', {}, ctx);
  assert.deepEqual(active.works.map((w) => w.slug), ['a']);
  assert.equal(active.works[0].worker.status, 'working');
  assert.equal(active.total, 2);
  const all = await ops.call('works-list', { all: true }, ctx);
  assert.equal(all.works.length, 2);
});

test('検証済みの値だけが下の層へ渡る・不正な入力は下の層に届かない', async () => {
  const { ops, log } = fakes();
  await ops.call('worker-start', { slug: 'x1', instruction: ' 始めて ' }, ctx);
  assert.deepEqual(log.find((l) => l[0] === 'startWorker')[1], { slug: 'x1', instruction: '始めて', kind: '', model: '', fresh: false });
  await assert.rejects(ops.call('worker-start', { slug: '../x' }, ctx));
  await assert.rejects(ops.call('worker-prompt', { slug: 'x1', text: '' }, ctx));
  await assert.rejects(ops.call('report', { message: 'm', level: 'x' }, ctx));
  assert.equal(log.filter((l) => l[0] === 'startWorker').length, 1);
  const prompted = await ops.call('worker-prompt', { slug: 'x1', text: 'go' }, ctx, 'ui');
  assert.equal(prompted.status, 'sent');
  assert.equal(log.find((l) => l[0] === 'promptWorker')[1].source, 'ui');
});

test('CLI から呼ぶ一覧は、aidev CLI の結果が未取得なら待つ（next を空にしない）', async () => {
  const { ops, log } = fakes();
  await ops.call('works-list', {}, ctx);
  assert.deepEqual(log.find((l) => l[0] === 'overview')[2], { wait: 'if-empty' });
});

test('summarize・uiModel・端末版: 数・切り詰め・エスケープ', async () => {
  const { data, agents } = fakes();
  const model = await buildModel('/proj/sample', [], { data, agents });
  const s = summarize(model);
  assert.deepEqual([s.supervisor, s.active, s.working, s.blocked, s.questions], ['idle', 1, 1, 0, 1]);
  assert.deepEqual(s.current, { slug: 'a', phase: 'coding' });
  model.log = [{ at: '2026-10-15T00:00:00Z', from: 'worker', slug: 'a', kind: 'report', message: '<img src=x onerror=alert(1)>|表\n改行' }];
  const md = terminalMarkdown(model);
  assert.match(md, /^# aidev — sample/);
  assert.ok(!md.includes('\n改行'), '改行は 1 行にする');
  assert.match(md, /\| ● a \|/);
  assert.ok(!md.includes('<img'), 'Markdown にも生の < を入れない');
  const band = bandHtml(model);
  assert.match(band, /監督: 待機/);
  const html = staticHtml(model);
  assert.ok(!html.includes('<img src=x'), 'HTML はエスケープする');
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.equal(esc('<a href="x">\'&'), '&lt;a href=&quot;x&quot;&gt;&#39;&amp;');
  const ui = uiModel(model);
  assert.equal(ui.lists.works[0].ws, 'working');
  assert.equal('worker' in ui.lists.works[0], false);
});

test('端末版・帯: .aidev が無いときも壊れない', () => {
  const empty = { project: 'p', root: '/p', available: false, works: [], backlog: [], workers: [], log: [], supervisor: null, settings: {} };
  assert.match(terminalMarkdown(empty), /\.aidev が見つかりません/);
  assert.match(bandHtml(empty), /\.aidev が見つかりません/);
});

test('小分け: JSON の大きさを守る・文字列は元に戻る', () => {
  const items = Array.from({ length: 500 }, (_, i) => ({ slug: `work-${i}`, text: 'あ'.repeat(100) }));
  const parts = chunkItems(items, 8000);
  assert.ok(parts.length > 1);
  for (const p of parts) assert.ok(Buffer.byteLength(JSON.stringify(p)) <= 8000);
  assert.equal(parts.flat().length, 500);
  assert.deepEqual(chunkItems([], 100), [[]]);
  const text = '日本語"引用"\n\\' .repeat(5000);
  const pieces = chunkText(text, 4000);
  assert.ok(pieces.length > 1);
  for (const p of pieces) assert.ok(Buffer.byteLength(JSON.stringify(p)) <= 4000 + 2);
  assert.equal(pieces.join(''), text);
});

test('アプリ画面: データを埋め込まず、textContent で描く（innerHTML を使わない）', () => {
  const html = appHtml();
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(/.test(html));
  assert.match(html, /typeof soda\.mount !== 'function'/);
  assert.match(html, /soda\.onMessage/);
  assert.match(html, /監督を起動/);
  assert.match(html, /監督に任せる/);
  const script = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));
  assert.doesNotThrow(() => new Function(script));
});

test('種類（claude|codex）とモデルは起動ごとに指定できる・不正な値は断る', () => {
  assert.deepEqual(validateParams('worker-start', { slug: 'a', kind: 'codex', model: 'gpt-5' }), { slug: 'a', instruction: '', kind: 'codex', model: 'gpt-5', fresh: false });
  assert.deepEqual(validateParams('supervisor-start', { kind: 'claude', model: 'sonnet' }), { kind: 'claude', model: 'sonnet', fresh: false });
  assert.equal(validateParams('supervisor-start', { fresh: true }).fresh, true);
  assert.equal(validateParams('worker-start', { slug: 'a', fresh: true }).fresh, true);
  bad('supervisor-start', { fresh: 'yes' }, /fresh/);
  for (const kind of ['gemini', 'CLAUDE', 5, null]) { bad('worker-start', { slug: 'a', kind }, /種類/); bad('supervisor-start', { kind }, /種類/); }
});

test('関連するエージェントの操作: slug・pane の ID・lines を検証する', () => {
  const id = 'aaaa1111-0000-4000-8000-000000000001';
  assert.deepEqual(validateParams('work-agent-prompt', { slug: 'a', paneId: id, text: ' 調べて ' }), { slug: 'a', paneId: id, text: '調べて' });
  assert.equal(validateParams('work-agent-read', { slug: 'a', paneId: id }).lines, 60);
  assert.equal(validateParams('work-agent-register', { slug: 'a', paneId: 'abcd' }).paneId, 'abcd');
  for (const paneId of ['', 'x y', '../x', 'abc', 'ZZZZ', 5, 'a'.repeat(65)]) bad('work-agent-prompt', { slug: 'a', paneId, text: 't' }, /pane/);
  bad('work-agent-read', { slug: 'a', paneId: id, lines: 201 }, /lines/);
  bad('work-agent-read', { slug: '-A', paneId: id }, /slug/);
  bad('work-agents', { slug: 'a', extra: 1 }, /知らない/);
});

// ---- 結果の大きさ（app.result は 256 KiB まで） -------------------------------------------------------

import { fitResult, RESULT_MAX_BYTES } from './operations.mjs';
const size = (v) => Buffer.byteLength(JSON.stringify(v));

test('結果の大きさ: work-doc は本文を切って truncated を返す', () => {
  const text = 'あ'.repeat(200000); // 600 KB
  const out = fitResult('work-doc', { slug: 'a', name: 'design.md', text, truncated: false, size: 600000 });
  assert.ok(size(out) <= RESULT_MAX_BYTES);
  assert.equal(out.truncated, true);
  assert.ok(out.text.length > 1000 && !out.text.includes('\uFFFD'));
  assert.equal(out.size, 600000);
  const small = { slug: 'a', name: 'x.md', text: 'hi', truncated: false };
  assert.equal(fitResult('work-doc', small), small, '小さければそのまま');
});

test('結果の大きさ: log-list・works-list は件数を減らして truncated を返す・切れないものは明示的に断る', () => {
  const log = Array.from({ length: 300 }, (_, i) => ({ at: 't', from: 'app', kind: 'event', message: 'x'.repeat(8000) + i }));
  const l = fitResult('log-list', { log });
  assert.ok(size(l) <= RESULT_MAX_BYTES);
  assert.equal(l.truncated, true);
  assert.ok(l.log.length >= 1 && l.log[0].message.endsWith('0'), '新しい順の先頭から残す');
  const works = Array.from({ length: 1000 }, (_, i) => ({ slug: `w-${i}`, pad: 'y'.repeat(600) }));
  const w = fitResult('works-list', { total: 1000, shown: 1000, works });
  assert.ok(size(w) <= RESULT_MAX_BYTES);
  assert.deepEqual([w.truncated, w.shown === w.works.length], [true, true]);
  assert.throws(() => fitResult('agents-list', { blob: 'z'.repeat(300000) }), /結果が大きすぎます/);
});

test('結果の大きさ: call の出口に共通のガードがある', async () => {
  const data = { loadDoc: async () => ({ slug: 'a', name: 'd.md', text: 'あ'.repeat(200000), truncated: false, size: 600000 }) };
  const ops = createOperations({ data, agents: {} });
  const r = await ops.call('work-doc', { slug: 'a', name: 'd.md' }, { root: '/p', panes: [] });
  assert.ok(size(r) <= RESULT_MAX_BYTES);
  assert.equal(r.truncated, true);
});

test('N3: 端末版の Markdown では、リンク・画像の記法を生きたまま出さない', () => {
  const model = { project: 'p', root: '/p', available: true, works: [], backlog: [], workers: [], supervisor: null, settings: {}, related: [],
    log: [{ at: 't', from: 'worker', slug: null, kind: 'report', message: '![x](https://evil.example/a.png) [click](https://evil.example)' }] };
  const md = terminalMarkdown(model);
  assert.ok(!/\]\(https?:/.test(md), md);
  assert.ok(!/(^|[^\\])!\[/.test(md));
});

test('画面の値（すべて文字列）の真偽を boolean に直してから検証に渡す（新しい会話で始める）', () => {
  assert.deepEqual(validateParams('supervisor-start', fromUi({ kind: '', model: '', fresh: 'true' })), { kind: '', model: '', fresh: true });
  assert.deepEqual(validateParams('worker-start', fromUi({ slug: 'a', instruction: '', kind: 'codex', model: '', fresh: 'true' })), { slug: 'a', instruction: '', kind: 'codex', model: '', fresh: true });
  assert.equal(validateParams('supervisor-start', fromUi({ fresh: 'false' })).fresh, false);
  assert.equal(validateParams('supervisor-start', fromUi({ fresh: '' })).fresh, false);
  bad('supervisor-start', fromUi({ fresh: 'yes' }), /fresh/);
  assert.deepEqual(fromUi({ text: 'true' }), { text: 'true' }, '他の項目には触れない');
  bad('supervisor-start', { fresh: 'true' }, /fresh/); // CLI（JSON）の経路は、文字列を受けない
});
