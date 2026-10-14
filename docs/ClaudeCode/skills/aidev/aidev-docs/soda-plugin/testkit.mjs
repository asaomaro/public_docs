// テスト用の見本作り（配布物には入れない）。
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

export async function tempDir(prefix = 'aidev-plugin-') {
  const dir = await mkdtemp(join(tmpdir(), prefix));
  return { dir, cleanup: () => rm(dir, { recursive: true, force: true }) };
}
export async function put(root, rel, content) {
  const file = join(root, rel);
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, content);
  return file;
}

const events = (n) => Array.from({ length: n }, (_, i) => `  - { ts: 2026-10-0${(i % 9) + 1}T00:00:${String(i % 60).padStart(2, '0')}Z, phase: coding, event: taskcheck, metrics: { stage: start, task: T${i} } }`).join('\n');

/** 進行中・完了・廃止・壊れた state・state なしの作業と backlog を持つ小さな PJ。 */
export async function sampleProject(root) {
  await put(root, '.aidev/current', '20261001-active-a\n');
  await put(root, '.aidev/works/20261001-active-a/state.yml',
    '---\nschema: 11\nslug: active-a\ncurrent: coding\napproved: [requirements, design, tasks]\nmode: autonomous\nprofile: full\ndependsOn: [20260901-done-b]\nharnessRev: unknown\n---\n');
  await put(root, '.aidev/works/20261001-active-a/tasks.md', '# タスク\n\n- [x] T1: 型を作る\n- [ ] T2: 画面を作る\n      - [ ] 入れ子は数えない\n- [ ] T3: テストを書く\n');
  await put(root, '.aidev/works/20261001-active-a/metrics.yml', `events:\n${events(40)}\n`);
  await put(root, '.aidev/works/20261001-active-a/requirements.md', '# 要件\n\n- 目的\n\n```sh\necho hi\n```\n');
  await put(root, '.aidev/works/20261001-active-a/design.md', '# 設計\n');
  await put(root, '.aidev/works/20260901-done-b/state.yml', 'current: deliver\napproved: [requirements, design, tasks, coding, test, review, deliver]\nmode: interactive\nprofile: light\n');
  await put(root, '.aidev/works/20260801-abandoned-c/state.yml', 'current: design\napproved: [requirements]\nstatus: abandoned\n');
  await put(root, '.aidev/works/20260701-broken-d/notes.md', '# state.yml が無い作業\n');
  await put(root, '.aidev/works/20260601-weird-e/state.yml', 'これは行ではない\ncurrent coding\n: x\ncurrent: tasks # コメント\napproved: [requirements,\n');
  await put(root, '.aidev/backlog/roadmap.md', '# roadmap\n- [ ] 一つ目\n- [x] 終わったもの\n- [ ] 二つ目 <script>alert(1)</script>\n');
}

export const TSV = [
  'work\t20261001-active-a\t-\tautonomous\tcoding\ttest\tactive\t20260901-done-b(未deliver)',
  'work\t20260901-done-b\t-\tinteractive\tdeliver\t-\tdone\tok',
  'backlog\troadmap.md\t3\t2\t0',
  '',
].join('\n');
