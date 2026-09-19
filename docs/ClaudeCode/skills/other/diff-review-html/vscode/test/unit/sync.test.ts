import { test } from "node:test";
import assert from "node:assert/strict";
import { MessageType, SyncHost, SyncSession } from "../../src/sync";

// VSCode の TextDocument の代わり。版は変更のたびに 1 増える（保存では増えない。design.md「依拠する既存の事実」）。
class FakeDoc implements SyncHost {
  text: string;
  version = 1;
  posted: Array<Record<string, unknown>> = [];
  warnings: string[] = [];
  session!: SyncSession;
  applyResult: "ok" | "fail" | "throw" | "hijack" = "ok";
  applyDelay = 0;
  applied: string[] = [];

  constructor(text: string) { this.text = text; }

  getText(): string { return this.text; }
  getVersion(): number { return this.version; }
  post(message: object): void { this.posted.push(message as Record<string, unknown>); }
  warn(message: string): void { this.warnings.push(message); }

  async applyText(next: string): Promise<boolean> {
    this.applied.push(next);
    if (this.applyDelay) { await sleep(this.applyDelay); }
    if (this.applyResult === "fail") { return false; }
    if (this.applyResult === "throw") { throw new Error("boom"); }
    this.change(next);
    if (this.applyResult === "hijack") { this.change("HIJACKED"); }
    return true;
  }

  // 外部変更・元に戻す・自分の書き込みのどれでも、VSCode は onDidChangeTextDocument を飛ばす。
  change(next: string): void {
    this.text = next;
    this.version += 1;
    this.session.onDocumentChanged();
  }

  bumpVersionOnly(): void {
    this.version += 1;
    this.session.onDocumentChanged();
  }

  take(): Array<Record<string, unknown>> {
    const out = this.posted;
    this.posted = [];
    return out;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setup(text = "T0") {
  const doc = new FakeDoc(text);
  const session = new SyncSession(doc, 5);
  doc.session = session;
  return { doc, session };
}

// 間引きのタイマーが切れて、列が空になるまで待つ。
async function settle(session: SyncSession): Promise<void> {
  await sleep(20);
  await session.idle();
  await sleep(20);
  await session.idle();
}

function edit(id: string, text: string, baseVersion: number) {
  return { type: MessageType.edit, id, text, baseVersion };
}

async function readied(text = "T0") {
  const s = setup(text);
  s.session.onWebviewMessage({ type: MessageType.ready });
  await settle(s.session);
  s.doc.take();
  return s;
}

test("ready を受けたら今の文書と版を送る", async () => {
  const { doc, session } = setup("T0");
  session.onWebviewMessage({ type: MessageType.ready });
  await settle(session);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "T0", version: 1 }]);
});

test("ready の前の文書の変更は送らない", async () => {
  const { doc, session } = setup("T0");
  doc.change("T1");
  await settle(session);
  assert.deepEqual(doc.take(), []);
});

test("編集を書いたら ack だけを返し、自分の書き込みの通知は送り返さない", async () => {
  const { doc, session } = await readied();
  session.onWebviewMessage(edit("p:1", "T1", 1));
  await settle(session);
  assert.equal(doc.text, "T1");
  assert.deepEqual(doc.take(), [{ type: MessageType.ack, id: "p:1", version: 2 }]);
});

test("全文が文書と同じなら書かずに ack", async () => {
  const { doc, session } = await readied();
  session.onWebviewMessage(edit("p:1", "T0", 1));
  await settle(session);
  assert.deepEqual(doc.applied, []);
  assert.deepEqual(doc.take(), [{ type: MessageType.ack, id: "p:1", version: 1 }]);
});

test("元に戻す → やり直しの往復は、どちらも画面へ送る", async () => {
  const { doc, session } = await readied();
  session.onWebviewMessage(edit("p:1", "T1", 1));
  await settle(session);
  doc.take();
  doc.change("T0");                     // 元に戻す
  await settle(session);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "T0", version: 3 }]);
  doc.change("T1");                     // やり直し
  await settle(session);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "T1", version: 4 }]);
});

test("中身が同じで版だけ進んだときも送る（画面の版を揃える）", async () => {
  const { doc, session } = await readied();
  doc.bumpVersionOnly();
  await settle(session);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "T0", version: 2 }]);
});

test("間引きの間の変更はまとめて 1 回だけ送る", async () => {
  const { doc, session } = await readied();
  doc.change("A");
  doc.change("B");
  doc.change("C");
  await settle(session);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "C", version: 4 }]);
});

test("すれ違い: 外部変更のあとに古い版を基にした編集が来たら書かずに conflict で答え、二重に送らない", async () => {
  const { doc, session } = await readied();
  doc.change("X");                      // 外部変更（まだ間引き中）
  session.onWebviewMessage(edit("p:1", "T1", 1));
  await settle(session);
  assert.equal(doc.text, "X");
  assert.deepEqual(doc.applied, []);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "X", version: 2, id: "p:1", conflict: true }]);
});

test("編集は 1 本ずつ処理され、同じ版を基にした 2 本目は退けられる", async () => {
  const { doc, session } = await readied();
  doc.applyDelay = 10;
  session.onWebviewMessage(edit("p:1", "T1", 1));
  session.onWebviewMessage(edit("p:2", "T2", 1));
  await settle(session);
  assert.equal(doc.text, "T1");
  assert.deepEqual(doc.take(), [
    { type: MessageType.ack, id: "p:1", version: 2 },
    { type: MessageType.text, text: "T1", version: 2, id: "p:2", conflict: true },
  ]);
});

test("ack のあとの版を基にした次の編集は書ける", async () => {
  const { doc, session } = await readied();
  session.onWebviewMessage(edit("p:1", "T1", 1));
  await settle(session);
  session.onWebviewMessage(edit("p:2", "T2", 2));
  await settle(session);
  assert.equal(doc.text, "T2");
  assert.deepEqual(doc.take(), [
    { type: MessageType.ack, id: "p:1", version: 2 },
    { type: MessageType.ack, id: "p:2", version: 3 },
  ]);
});

test("書けなかったら知らせて、今の文書を conflict で送る", async () => {
  const { doc, session } = await readied();
  doc.applyResult = "fail";
  session.onWebviewMessage(edit("p:1", "T1", 1));
  await settle(session);
  assert.equal(doc.warnings.length, 1);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "T0", version: 1, id: "p:1", conflict: true }]);
});

test("書き込みが例外でも返事は必ず返る（画面を待たせたままにしない）", async () => {
  const { doc, session } = await readied();
  doc.applyResult = "throw";
  session.onWebviewMessage(edit("p:1", "T1", 1));
  await settle(session);
  assert.equal(doc.warnings.length, 1, "警告は 1 つにまとめる");
  assert.match(doc.warnings[0], /boom/);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "T0", version: 1, id: "p:1", conflict: true }]);
});

test("書いている間に別の変更が入ったら、ack ではなく今の文書を conflict で送る", async () => {
  const { doc, session } = await readied();
  doc.applyResult = "hijack";
  session.onWebviewMessage(edit("p:1", "T1", 1));
  await settle(session);
  assert.deepEqual(doc.take(), [{ type: MessageType.text, text: "HIJACKED", version: 3, id: "p:1", conflict: true }]);
});

test("作り直し: 書いている途中に ready が来たら、書いたあとの文書を送る", async () => {
  const { doc, session } = await readied();
  doc.applyDelay = 10;
  session.onWebviewMessage(edit("p:1", "T1", 1));
  session.onWebviewMessage({ type: MessageType.ready });   // タブを隠して戻した新しい画面
  await settle(session);
  assert.deepEqual(doc.take(), [
    { type: MessageType.ack, id: "p:1", version: 2 },
    { type: MessageType.text, text: "T1", version: 2 },
  ]);
});

test("関係の無いメッセージ・形の崩れた編集は無視する", async () => {
  const { doc, session } = await readied();
  session.onWebviewMessage(null);
  session.onWebviewMessage("hello");
  session.onWebviewMessage({ type: "other" });
  session.onWebviewMessage({ type: MessageType.edit, id: "p:1", text: 42, baseVersion: 1 });
  session.onWebviewMessage({ type: MessageType.edit, text: "T1", baseVersion: 1 });
  await settle(session);
  assert.equal(doc.text, "T0");
  assert.deepEqual(doc.take(), []);
});

test("書いている途中に破棄されたら、返事も警告も出さない", async () => {
  for (const result of ["ok", "fail"] as const) {
    const { doc, session } = await readied();
    doc.applyDelay = 10;
    doc.applyResult = result;
    session.onWebviewMessage(edit("p:1", "T1", 1));
    await sleep(2);
    session.dispose();
    await settle(session);
    assert.deepEqual(doc.take(), [], result);
    assert.deepEqual(doc.warnings, [], result);
  }
});

test("破棄したあとは何も送らない", async () => {
  const { doc, session } = await readied();
  session.dispose();
  doc.change("T1");
  session.onWebviewMessage(edit("p:1", "T2", 2));
  await settle(session);
  assert.deepEqual(doc.take(), []);
  assert.equal(doc.text, "T1");
});
