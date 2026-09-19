// 画面側（templates/app.js）の同期の手順を、同梱の画面そのもの（media/viewer.html）と本物の SyncSession
// （src/sync.ts）をつないで確かめる。VSCode は使わず、headless Chromium と、元に戻せる偽の文書で動かす。
// e2e では起こしにくい順序（すれ違い・返事のあとの送り直し・版だけ進む・壊れている間の書き込み）をここで押さえる。
//
// Chromium: 環境変数 CHROMIUM_PATH か、playwright-core が入れたもの（`npx playwright-core install chromium`）。
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Page, chromium } from "playwright-core";
import { SyncSession } from "../../src/sync";
import { EXT_ROOT, PYTHON, SKILL_DIR, diffReview, python, sleep, waitFor } from "../e2e/harness";

const results: Array<{ name: string; ok: boolean; detail: string }> = [];

function check(condition: unknown, message: string): void {
  if (!condition) { throw new Error(message); }
}

// VSCode の TextDocument の代わり。変更のたびに版が 1 増え、変更の通知を SyncSession へ送る。
class FakeDocument {
  text: string;
  version = 1;
  session!: SyncSession;
  applyDelayMs = 0;
  beforeEdit: ((edit: { text: string }) => void) | null = null;

  constructor(text: string) { this.text = text; }

  async applyText(next: string): Promise<boolean> {
    if (this.applyDelayMs) { await sleep(this.applyDelayMs); }
    this.change(next);
    return true;
  }

  change(next: string): void {
    this.text = next;
    this.version += 1;
    this.session.onDocumentChanged();
  }

  bumpVersionOnly(): void {
    this.version += 1;
    this.session.onDocumentChanged();
  }
}

interface Rig {
  page: Page;
  doc: FakeDocument;
  edits: Array<{ id: string; text: string; baseVersion: number }>;
  warnings: string[];
}

// postDelayMs: 拡張から画面への送信を遅らせる（返事が届く前に画面で操作を重ねる順序を作るため）。
async function rig(page: Page, viewerUrl: string, text: string, postDelayMs = 0): Promise<Rig> {
  const doc = new FakeDocument(text);
  const edits: Rig["edits"] = [];
  const warnings: string[] = [];
  const session = new SyncSession({
    getText: () => doc.text,
    getVersion: () => doc.version,
    applyText: (next) => doc.applyText(next),
    post: (message) => {
      const send = () => { void page.evaluate((m) => window.postMessage(m, "*"), message).catch(() => undefined); };
      if (postDelayMs) { setTimeout(send, postDelayMs); } else { send(); }
    },
    warn: (message) => { warnings.push(message); },
  }, 20);
  doc.session = session;
  await page.exposeFunction("__toHost", (message: { type: string; id: string; text: string; baseVersion: number }) => {
    if (message && message.type === "diff-review/edit") {
      edits.push(message);
      if (doc.beforeEdit) { const hook = doc.beforeEdit; doc.beforeEdit = null; hook(message); }
    }
    session.onWebviewMessage(message);
  });
  await page.addInitScript(() => {
    const w = window as unknown as { acquireVsCodeApi: () => unknown; __toHost: (m: unknown) => void };
    w.acquireVsCodeApi = () => ({ postMessage: (m: unknown) => { void w.__toHost(m); }, getState: () => null, setState: () => undefined });
  });
  await page.goto(viewerUrl);
  return { page, doc, edits, warnings };
}

async function state(page: Page) {
  return page.evaluate(() => ({
    threads: document.querySelectorAll(".thread").length,
    rows: document.querySelectorAll("#files .row[data-key]").length,
    banners: Array.from(document.querySelectorAll("#banners .banner")).map((n) => n.textContent || ""),
    resolved: document.querySelectorAll(".thread[data-resolved='true'], .thread.resolved").length,
  }));
}

// スレッドを id で指して、解決／未解決に戻すのボタンを押す（DOM の並びは全体へのコメントが先に来る）。
async function toggleResolve(page: Page, threadId: string, label: "解決にする" | "未解決に戻す"): Promise<void> {
  await page.locator(`.thread[data-thread="${threadId}"] button`, { hasText: label }).first()
    .evaluate((b) => (b as HTMLButtonElement).click());
}

function pyResolve(original: string, scratch: string, threadId: string): string {
  const copy = join(scratch, `resolve-${threadId}.dreview`);
  writeFileSync(copy, original);
  const r = diffReview(["resolve", copy, "--thread", threadId]);
  if (r.status !== 0) { throw new Error(r.stderr); }
  return readFileSync(copy, "utf8");
}

// 記録の target を別の差分のものに書き換えた（--import で持ち込んだ記録と同じ形の）バンドル。
function foreignTarget(text: string): string {
  const script = [
    "import sys",
    `sys.path.insert(0, ${JSON.stringify(SKILL_DIR)})`,
    "import diff_review as dr",
    "b = dr.parse_bundle(sys.stdin.read())",
    "b['review']['target'] = dict(b['review']['target'], diff_digest='0' * 40, base_commit='f' * 40)",
    "sys.stdout.write(dr.bundle_text(b['target'], b['files'], b['rich_enabled'], b['review']))",
  ].join("\n");
  const r = spawnSync(PYTHON, ["-c", script], { input: text, encoding: "utf8" });
  if (r.status !== 0) { throw new Error(r.stderr); }
  return r.stdout;
}

async function main(): Promise<void> {
  const scratch = mkdtempSync(join(tmpdir(), "diff-review-protocol-"));
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, headless: true });
  try {
    const repo = join(scratch, "repo");
    check(python([join(SKILL_DIR, "tests", "fixture_repo.py"), repo]).status === 0, "fixture_repo.py");
    const base = join(scratch, "base.dreview");
    check(diffReview(["bundle", "--repo", repo, "--from", "commit", "--rev", "HEAD", "--out", base]).status === 0, "bundle");
    check(diffReview(["comment", base, "--path", "src/core/util.py", "--line", "1", "--body", "AI: util"]).status === 0, "comment");
    check(diffReview(["comment", base, "--path", "src/api/handler.py", "--line", "2", "--body", "AI: handler", "--severity", "must"]).status === 0, "comment");
    check(diffReview(["comment", base, "--body", "AI: overall"]).status === 0, "comment");
    const original = readFileSync(base, "utf8");
    const viewerUrl = "file://" + join(EXT_ROOT, "media", "viewer.html");

    const scenario = async (name: string, body: (page: Page) => Promise<void>) => {
      const context = await browser.newContext();
      const page = await context.newPage();
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      try {
        await body(page);
        check(errors.length === 0, `ページの例外: ${errors.join(" | ")}`);
        results.push({ name, ok: true, detail: "" });
        console.log(`PASS ${name}`);
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        results.push({ name, ok: false, detail });
        console.log(`FAIL ${name}: ${detail}`);
      } finally {
        await context.close();
      }
    };
    const opened = async (page: Page, text: string, postDelayMs = 0) => {
      const r = await rig(page, viewerUrl, text, postDelayMs);
      await waitFor("描画", async () => (await state(page)).threads === 3);
      return r;
    };

    await scenario("開いて見るだけ（確認済み・移動・入力・展開）では編集を送らない", async (page) => {
      const r = await opened(page, original);
      await page.locator(".file-head input[type=checkbox]").first().click();
      await page.locator("#files .row[data-key]").first().focus();
      await page.keyboard.press("j");
      await page.keyboard.press("c");
      await page.keyboard.type("typing only");
      await page.keyboard.press("Escape");
      const expand = page.locator(".expander button").first();
      if (await expand.count()) { await expand.evaluate((b) => (b as HTMLButtonElement).click()); }
      await sleep(300);
      check(r.edits.length === 0, `編集が送られた: ${r.edits.length}`);
      check(r.doc.text === original, "文書が変わった");
    });

    await scenario("解決すると Python の resolve と同じバイト列になり、未解決に戻すと元のバイト列に戻る", async (page) => {
      const r = await opened(page, original);
      await toggleResolve(page, "t1", "解決にする");
      await waitFor("書き込み", async () => r.doc.version === 2);
      check(r.doc.text === pyResolve(original, scratch, "t1"), "Python の resolve --thread t1 と一致しない");
      await toggleResolve(page, "t1", "未解決に戻す");
      await waitFor("書き込み", async () => r.doc.version === 3);
      check(r.doc.text === original, "元のバイト列に戻らない");
    });

    await scenario("別の差分に対する記録（target が違う）も、記録の target を保って書く", async (page) => {
      const foreign = foreignTarget(original);
      const r = await opened(page, foreign);
      await toggleResolve(page, "t1", "解決にする");
      await waitFor("書き込み", async () => r.doc.version === 2);
      check(r.doc.text === pyResolve(foreign, scratch, "t1"), "Python の resolve と一致しない（記録の target が変わった）");
      await toggleResolve(page, "t1", "未解決に戻す");
      await waitFor("書き込み", async () => r.doc.version === 3);
      check(r.doc.text === foreign, "元のバイト列に戻らない");
    });

    await scenario("すれ違い: 送った編集が退けられたら知らせを出して文書の内容に揃え、次の編集は書ける（知らせも消える）", async (page) => {
      const r = await opened(page, original);
      const external = pyResolve(original, scratch, "t2");   // 外で t2 が解決された
      r.doc.beforeEdit = () => r.doc.change(external);        // 画面の編集が届く直前に外で変わる
      await toggleResolve(page, "t1", "解決にする");            // 画面では t1 を解決
      await waitFor("知らせ", async () => (await state(page)).banners.some((b) => b.includes("同時に変更")));
      check(r.doc.text === external, "退けたはずの編集が書かれた");
      await waitFor("文書の内容に揃う", async () => (await page.locator(".thread[data-resolved='true']").count()) === 1
        && (await page.locator(".thread[data-thread='t2'][data-resolved='true']").count()) === 1);
      await toggleResolve(page, "t1", "解決にする");
      await waitFor("次の編集が書ける", async () => r.doc.version === 3);
      await waitFor("書けたら知らせが消える", async () => !(await state(page)).banners.some((b) => b.includes("同時に変更")), 3000);
    });

    await scenario("返事待ちの間に重ねた変更は、返事のあとに最新の全文としてまとめて送る", async (page) => {
      const r = await opened(page, original);
      r.doc.applyDelayMs = 300;
      await toggleResolve(page, "t1", "解決にする");
      await sleep(30);
      await toggleResolve(page, "t2", "解決にする");           // 1 本目の返事待ちの間に重ねる
      check(r.doc.version === 1 && r.edits.length === 1, `前提: 1 本目の返事待ちの間に重ねた（版 ${r.doc.version}・送った ${r.edits.length}）`);
      await waitFor("2 回とも書かれる", async () => r.doc.version === 3, 5000);
      check(r.edits.length === 2, `送った編集: ${r.edits.length}`);
      check(r.edits[1].baseVersion === 2, `2 本目の基の版: ${r.edits[1].baseVersion}`);
      const both = pyResolve(pyResolve(original, scratch, "t1"), scratch, "t2");
      check(r.doc.text === both, "2 つの解決が両方書かれていない");
    });

    await scenario("返事の本文が送った全文と同じでも、返事待ちの間に重ねた変更は送る", async (page) => {
      const r = await opened(page, original, 300);
      // 送った編集が届く直前に、外で文書がちょうどその全文になる → 版が古いので退けられ、返事の本文は送った全文と同じ。
      r.doc.beforeEdit = (edit) => r.doc.change(edit.text);
      await toggleResolve(page, "t1", "解決にする");
      await waitFor("1 本目が届く", async () => r.edits.length === 1);
      await toggleResolve(page, "t2", "解決にする");           // 返事（300ms 遅れる）を待つ間に重ねる
      check(r.edits.length === 1, "前提: 返事待ちの間に重ねた");
      await waitFor("重ねた変更が送られる", async () => r.edits.length === 2, 5000);
      await waitFor("書き込み", async () => r.doc.text === pyResolve(pyResolve(original, scratch, "t1"), scratch, "t2"), 5000);
    });

    await scenario("中身が同じまま版だけ進んでも、次の編集は退けられない", async (page) => {
      const r = await opened(page, original);
      r.doc.bumpVersionOnly();
      await sleep(200);
      await toggleResolve(page, "t1", "解決にする");
      await waitFor("書き込み", async () => r.doc.version === 3);
      check(!(await state(page)).banners.some((b) => b.includes("同時に変更")), "退けられた");
    });

    await scenario("元に戻す相当（文書が前のテキストに戻る）は、行を作り直さずに記録だけ差し替える", async (page) => {
      const r = await opened(page, original);
      await page.locator("#files .row[data-key]").nth(30).focus();
      const before = await page.evaluate(() => document.activeElement!.getAttribute("data-key"));
      await toggleResolve(page, "t1", "解決にする");
      await waitFor("書き込み", async () => r.doc.version === 2);
      await page.locator(`#files .row[data-key="${before}"]`).focus();
      r.doc.change(original);
      await waitFor("戻る", async () => (await page.locator(".thread[data-resolved='true']").count()) === 0);
      const after = await page.evaluate(() => document.activeElement && document.activeElement.getAttribute("data-key"));
      check(after === before, `現在行が変わった: ${before} → ${after}`);
      check(r.edits.length === 1, "元に戻したことを編集として送り返した");
    });

    await scenario("壊れた文書は理由を出して空にし、その間に書いたものは保存されないと知らせ、直ると表示する", async (page) => {
      const r = await opened(page, original);
      r.doc.change("これはバンドルではない\n");
      await waitFor("理由", async () => (await state(page)).banners.some((b) => b.includes("表示できません")));
      check((await state(page)).rows === 0, "壊れているのに行が出ている");
      await page.locator("#overall .comment-open").evaluate((b) => (b as HTMLButtonElement).click());
      await page.keyboard.type("broken write");
      await page.keyboard.press("Control+Enter");
      await waitFor("保存されない知らせ", async () => (await state(page)).banners.some((b) => b.includes("保存されません")));
      check(r.edits.length === 0, "壊れている間に編集を送った");
      r.doc.change(original);
      await waitFor("直った", async () => { const s = await state(page); return s.rows > 0 && s.threads === 3; });
      check(!(await state(page)).banners.some((b) => b.includes("表示できません") || b.includes("保存されません")), "知らせが残った");
    });
  } finally {
    await browser.close();
    rmSync(scratch, { recursive: true, force: true });
  }

  const failed = results.filter((r) => !r.ok);
  console.log(`RESULT: ${results.length - failed.length} passed / ${failed.length} failed`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
