import { beforeEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { symlink, utimes, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import * as data from './aidev-data.mjs';
import { put, sampleProject, tempDir, TSV } from './testkit.mjs';

const bySlug = (works) => Object.fromEntries(works.map((w) => [w.slug, w]));
const NOHOME = { home: '/nonexistent-aidev-home' };
beforeEach(() => data.resetStatusCache());

test('作業一覧: 進行中・完了・廃止・state なし・壊れた state を区別する', async () => {
  const { dir, cleanup } = await tempDir();
  try {
    await sampleProject(dir);
    const o = await data.loadOverview(dir, NOHOME);
    assert.equal(o.available, true);
    assert.equal(o.total, 5);
    assert.equal(o.current, '20261001-active-a');
    const w = bySlug(o.works);
    assert.equal(w['20261001-active-a'].state, 'active');
    assert.equal(w['20261001-active-a'].current, 'coding');
    assert.deepEqual(w['20261001-active-a'].approved, ['requirements', 'design', 'tasks']);
    assert.deepEqual(w['20261001-active-a'].dependsOn, ['20260901-done-b']);
    assert.deepEqual(w['20261001-active-a'].tasks, { done: 1, total: 3 }, '入れ子の項目は数えない');
    assert.equal(w['20261001-active-a'].isCurrent, true);
    assert.equal(w['20260901-done-b'].state, 'done');
    assert.equal(w['20260801-abandoned-c'].state, 'abandoned');
    assert.equal(w['20260701-broken-d'].state, 'broken');
    assert.equal(w['20260701-broken-d'].broken, true);
    assert.equal(w['20260601-weird-e'].state, 'active', '壊れた行は飛ばして読めるところだけ使う');
    assert.equal(w['20260601-weird-e'].current, 'tasks', '行末のコメントは落とす');
    assert.equal(o.cli, false);
  } finally { await cleanup(); }
});

test('aidev CLI があれば status の next・deps を合わせる（sh で execFile・cwd は PJ・15 秒）', async () => {
  const { dir, cleanup } = await tempDir();
  try {
    await sampleProject(dir);
    await put(dir, '.claude/skills/aidev-docs/bin/aidev', '#!/bin/sh\n');
    const calls = [];
    const run = async (cmd, args, opts) => { calls.push({ cmd, args, opts }); return { stdout: TSV }; };
    const first = await data.loadOverview(dir, { run, ...NOHOME });
    assert.equal(first.cli, false, '初回は CLI を待たずに自前の読み取りだけで返す（背景で取りに行く）');
    const o = await data.loadOverview(dir, { run, ...NOHOME, wait: true });
    assert.equal(calls.length, 1, '同じ署名では取り直さない');
    assert.equal(calls[0].cmd, 'sh');
    assert.deepEqual(calls[0].args, [join(dir, '.claude/skills/aidev-docs/bin/aidev'), 'status', '--all', '--format', 'tsv']);
    assert.equal(calls[0].opts.cwd, dir);
    assert.equal(calls[0].opts.timeout, 15000);
    const a = bySlug(o.works)['20261001-active-a'];
    assert.equal(a.next, 'test');
    assert.match(a.deps, /未deliver/);
    assert.equal(o.cli, true);
    data.resetStatusCache();
    const failing = await data.loadOverview(dir, { run: async () => { throw new Error('boom'); }, ...NOHOME, wait: true });
    assert.equal(failing.cli, false, 'CLI が失敗しても自前の読み取りだけで返す');
    assert.equal(failing.total, 5);
  } finally { await cleanup(); }
});

test('CLI の探し場所は PJ → HOME の順', async () => {
  const { dir, cleanup } = await tempDir();
  try {
    const home = join(dir, 'home');
    const proj = join(dir, 'proj');
    await put(home, '.claude/skills/aidev-docs/bin/aidev', '');
    assert.equal(await data.findCli(proj, home), join(home, '.claude/skills/aidev-docs/bin/aidev'));
    await put(proj, '.claude/skills/aidev-docs/bin/aidev', '');
    assert.equal(await data.findCli(proj, home), join(proj, '.claude/skills/aidev-docs/bin/aidev'));
    assert.equal(await data.findCli(join(dir, 'x'), join(dir, 'y')), null);
    // Codex 用の写し（.agents/skills）も探す。PJ の .claude が先
    await put(proj, '.agents/skills/aidev-docs/bin/aidev', '');
    assert.equal(await data.findCli(proj, home), join(proj, '.claude/skills/aidev-docs/bin/aidev'));
    const only = join(dir, 'only');
    await put(only, '.agents/skills/aidev-docs/bin/aidev', '');
    assert.equal(await data.findCli(only, join(dir, 'y')), join(only, '.agents/skills/aidev-docs/bin/aidev'));
  } finally { await cleanup(); }
});

test('詳細: 工程の並び・文書の一覧・events は新しい順に 30 件・tasks のチェックリスト', async () => {
  const { dir, cleanup } = await tempDir();
  try {
    await sampleProject(dir);
    const d = await data.loadWorkDetail(dir, '20261001-active-a', NOHOME);
    const phase = Object.fromEntries(d.phases.map((p) => [p.phase, p]));
    assert.equal(phase.requirements.status, 'approved');
    assert.equal(phase.coding.status, 'current');
    assert.equal(phase.test.status, 'pending');
    assert.equal(phase.research.dim, true, '任意工程で文書も承認も無いものは薄く');
    assert.equal(phase.design.dim, false);
    assert.equal(phase.requirements.hasDoc, true);
    assert.deepEqual(d.docs.map((x) => x.name), ['design.md', 'requirements.md', 'tasks.md']);
    assert.equal(d.events.length, 30);
    assert.equal(d.events[0].task, undefined);
    assert.match(d.events[0].note, /T39/, '新しい順');
    assert.deepEqual(d.tasksList.map((t) => t.done), [true, false, false]);
    assert.equal(d.values.mode, 'autonomous');
  } finally { await cleanup(); }
});

test('文書: 一覧にある名前だけ・パスの成分は拒否・512 KiB で切る', async () => {
  const { dir, cleanup } = await tempDir();
  try {
    await sampleProject(dir);
    const slug = '20261001-active-a';
    const ok = await data.loadDoc(dir, slug, 'requirements.md');
    assert.match(ok.text, /要件/);
    for (const bad of ['../state.yml', 'a/b.md', '..\\state.yml', 'state.yml', '.md', 'nope.md', '..md', 'x\0.md']) {
      await assert.rejects(data.loadDoc(dir, slug, bad), Error, bad);
    }
    await assert.rejects(data.loadDoc(dir, '../etc', 'requirements.md'));
    await assert.rejects(data.loadDoc(dir, 'no-such-work', 'requirements.md'));
    await put(dir, '.aidev/works/20261001-active-a/big.md', 'あ'.repeat(300000));
    const big = await data.loadDoc(dir, slug, 'big.md');
    assert.equal(big.truncated, true);
    assert.ok(Buffer.byteLength(big.text) <= 512 * 1024 + 4);
  } finally { await cleanup(); }
});

test('シンボリックリンクで外へ出ない（文書・作業フォルダ・.aidev）', async () => {
  const { dir, cleanup } = await tempDir();
  const outside = await tempDir('aidev-outside-');
  try {
    await sampleProject(dir);
    await put(outside.dir, 'secret.md', 'SECRET');
    await symlink(join(outside.dir, 'secret.md'), join(dir, '.aidev/works/20261001-active-a/link.md'));
    const d = await data.loadWorkDetail(dir, '20261001-active-a', NOHOME);
    assert.ok(!d.docs.some((x) => x.name === 'link.md'), 'リンクの文書は一覧に出ない');
    await assert.rejects(data.loadDoc(dir, '20261001-active-a', 'link.md'));
    await put(outside.dir, 'work/state.yml', 'current: coding\n');
    await symlink(join(outside.dir, 'work'), join(dir, '.aidev/works/20260501-linked'));
    const o = await data.loadOverview(dir, NOHOME);
    assert.ok(!o.works.some((w) => w.slug === '20260501-linked'), 'リンクの作業フォルダは読まない');

    const other = await tempDir();
    try {
      await put(outside.dir, 'aidev/works/x/state.yml', 'current: coding\n');
      await symlink(join(outside.dir, 'aidev'), join(other.dir, '.aidev'));
      const e = await data.loadOverview(other.dir, NOHOME);
      assert.equal(e.available, false, 'PJ の外を指す .aidev は読まない');
    } finally { await other.cleanup(); }
  } finally { await cleanup(); await outside.cleanup(); }
});

test('backlog: 未着手の数と先頭 50 件', async () => {
  const { dir, cleanup } = await tempDir();
  try {
    await sampleProject(dir);
    const many = Array.from({ length: 80 }, (_, i) => `- [ ] 項目 ${i}`).join('\n');
    await put(dir, '.aidev/backlog/many.md', many + '\n- [x] 済み\n');
    const o = await data.loadOverview(dir, NOHOME);
    const roadmap = o.backlog.find((b) => b.file === 'roadmap.md');
    assert.equal(roadmap.todo, 2);
    assert.equal(roadmap.done, 1);
    const m = o.backlog.find((b) => b.file === 'many.md');
    assert.equal(m.todo, 80);
    assert.equal(m.items.length, 50);
  } finally { await cleanup(); }
});

test('作業は 1000 件まで（新しいものを残す）', async () => {
  const { dir, cleanup } = await tempDir();
  try {
    for (let i = 0; i < 1005; i++) await put(dir, `.aidev/works/w${String(i).padStart(5, '0')}/state.yml`, 'current: coding\n');
    const o = await data.loadOverview(dir, NOHOME);
    assert.equal(o.total, 1000);
    assert.equal(o.truncated, true);
    assert.ok(o.works.some((w) => w.slug === 'w01004'));
    assert.ok(!o.works.some((w) => w.slug === 'w00000'));
  } finally { await cleanup(); }
});

test('署名: ファイルが変わったときだけ変わる', async () => {
  const { dir, cleanup } = await tempDir();
  try {
    await sampleProject(dir);
    const a = await data.dataSignature(dir);
    assert.equal(await data.dataSignature(dir), a);
    const file = join(dir, '.aidev/works/20261001-active-a/tasks.md');
    await writeFile(file, '- [x] T1\n');
    await utimes(file, new Date(), new Date(Date.now() + 5000));
    assert.notEqual(await data.dataSignature(dir), a);
    assert.equal(await data.dataSignature(join(dir, 'none')), 'none');
  } finally { await cleanup(); }
});

test('簡易パーサ: 配列・引用符・コメント・重複キー', () => {
  const s = data.parseState('a: [x, "y z", \'w\']\nb: "quoted # not comment"\nc: v # comment\nc: second\n  nested: 1\n# c2: skip\n');
  assert.deepEqual(s.a, ['x', 'y z', 'w']);
  assert.equal(s.b, 'quoted # not comment');
  assert.equal(s.c, 'v');
  assert.equal(s.nested, undefined);
  assert.deepEqual(data.parseTasks('- [X] a\n- [ ] b\n  - [ ] c\n'), { done: 1, total: 2, items: [{ done: true, text: 'a' }, { done: false, text: 'b' }] });
});
