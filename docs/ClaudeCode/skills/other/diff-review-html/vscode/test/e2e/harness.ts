// 実機の VSCode を操作する e2e の道具。利用者の VSCode には触れない: @vscode/test-electron で取得した版を、
// 使い捨ての場所だけを使うポータブル状態（VSCODE_PORTABLE）で起動する（ホームの ~/.vscode/argv.json 等にも
// 書かせない）。WebView は別プロセスの iframe なので、--remote-debugging-port を付けて CDP で繋ぐ
// （research.md「実装時の注意」）。
import { ChildProcess, spawn, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { join } from "node:path";
import { Browser, Frame, Page, chromium } from "playwright-core";
import { downloadAndUnzipVSCode } from "@vscode/test-electron";

export const EXT_ROOT = join(__dirname, "..", "..", "..");
export const SKILL_DIR = join(EXT_ROOT, "..");
// Python の呼び名の決め方は scripts/python.cjs に 1 つだけ置く（ビルドと共通。名前を
// 決め打ちにすると、Windows の Microsoft Store のスタブを掴んで黙って失敗する）。
// コンパイル後の位置（out/test/e2e）から相対で書けないので、EXT_ROOT から引く。
// eslint-disable-next-line @typescript-eslint/no-var-requires
const pythonUtil = require(join(EXT_ROOT, "scripts", "python.cjs")) as {
  resolvePython(): string[] | null;
  pythonNotFoundMessage(): string;
};
const resolved = pythonUtil.resolvePython();
if (!resolved) { throw new Error(pythonUtil.pythonNotFoundMessage()); }
export const [PYTHON, ...PYTHON_ARGS] = resolved;
const VSCODE_VERSION = process.env.VSCODE_VERSION || "1.138.0";
const QUICK_INPUT = ".quick-input-widget:not([style*='display: none']) input";

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export async function waitFor<T>(what: string, probe: () => Promise<T | null | undefined | false>, timeoutMs = 15000): Promise<T> {
  const until = Date.now() + timeoutMs;
  let last: unknown = null;
  while (Date.now() < until) {
    try {
      const value = await probe();
      if (value) { return value as T; }
    } catch (err) {
      last = err;
    }
    await sleep(100);
  }
  throw new Error(`待ちきれませんでした: ${what}${last ? `（${String(last)}）` : ""}`);
}

export function python(args: string[], cwd?: string, input?: string): { status: number; stdout: string; stderr: string } {
  const result = spawnSync(PYTHON, [...PYTHON_ARGS, ...args], { cwd, input, encoding: "utf8" });
  return { status: result.status ?? -1, stdout: result.stdout, stderr: result.stderr };
}

export function diffReview(args: string[], cwd?: string) {
  return python([join(SKILL_DIR, "diff_review.py"), ...args], cwd);
}

// 保存されたファイルが、Python の正規形（bundle_text）とバイト一致するか。
export function isCanonicalBundle(file: string): boolean {
  const script = [
    "import sys",
    `sys.path.insert(0, ${JSON.stringify(SKILL_DIR)})`,
    "import diff_review as dr",
    "text = open(sys.argv[1], encoding='utf-8', newline='').read()",
    "b = dr.parse_bundle(text)",
    "sys.exit(0 if dr.bundle_text(b['target'], b['files'], b['rich_enabled'], b['review']) == text else 1)",
  ].join("\n");
  return python(["-c", script, file]).status === 0;
}

// 保存したファイルが元の中身を保っているか: files・target・記録の target・元のスレッドがそのままで、新しいスレッドは
// 末尾に足されただけか（整形の正規性は isCanonicalBundle が見る。こちらは中身が勝手に変わっていないかを見る）。
export function preservedAndAppended(original: string, saved: string): string | null {
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(SKILL_DIR)})`,
    "import diff_review as dr",
    "a = dr.parse_bundle(open(sys.argv[1], encoding='utf-8').read())",
    "b = dr.parse_bundle(open(sys.argv[2], encoding='utf-8').read())",
    "problems = [k for k in ('schema', 'target', 'files', 'rich_enabled') if a[k] != b[k]]",
    "ra, rb = a['review'] or {}, b['review'] or {}",
    "if ra.get('target') is not None and ra.get('target') != rb.get('target'): problems.append('review.target')",
    "ta, tb = ra.get('threads') or [], rb.get('threads') or []",
    "if tb[:len(ta)] != ta: problems.append('threads')",
    "print(json.dumps(problems))",
  ].join("\n");
  const result = python(["-c", script, original, saved]);
  if (result.status !== 0) { return result.stderr; }
  const problems = JSON.parse(result.stdout) as string[];
  return problems.length ? problems.join(", ") : null;
}

// Python の resolve を元のファイルの写しに当てた結果（画面で解決したときに一致すべきバイト列）。
export function pythonResolve(file: string, scratchCopy: string, threadId: string): Buffer {
  writeFileSync(scratchCopy, readFileSync(file));
  const r = diffReview(["resolve", scratchCopy, "--thread", threadId]);
  if (r.status !== 0) { throw new Error(r.stderr); }
  return readFileSync(scratchCopy);
}

// バンドルの中身（ファイル数・スレッド数・コメントの本文）を Python で読む。画面の表示と突き合わせる基準。
export function bundleSummary(file: string): { files: number; threads: number; bodies: string[] } {
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(SKILL_DIR)})`,
    "import diff_review as dr",
    "b = dr.load_bundle(sys.argv[1])",
    "threads = (b.get('review') or {}).get('threads') or []",
    "print(json.dumps({'files': len(b['files']), 'threads': len(threads),",
    "  'bodies': [c['body'] for t in threads for c in t['comments']]}))",
  ].join("\n");
  const result = python(["-c", script, file]);
  if (result.status !== 0) { throw new Error(result.stderr); }
  return JSON.parse(result.stdout);
}

export interface Session {
  browser: Browser;
  page: Page;
  proc: ChildProcess;
  userDir: string;
  // ビューアの CSP（nonce を使う）への違反のコンソール出力と、WebView からの外部への通信。
  webviewCspErrors: string[];
  webviewRequests: string[];
  close(): Promise<void>;
}

export function writeSettings(userDir: string, settings: Record<string, unknown>): void {
  mkdirSync(join(userDir, "User"), { recursive: true });
  writeFileSync(join(userDir, "User", "settings.json"), JSON.stringify(settings, null, 2));
}

export const BASE_SETTINGS = {
  "window.dialogStyle": "custom",
  "workbench.colorTheme": "Default Dark Modern",
  "workbench.startupEditor": "none",
  "window.restoreWindows": "none",
  "security.workspace.trust.enabled": false,
  "files.autoSave": "off",
  "update.mode": "none",
  "telemetry.telemetryLevel": "off",
  "extensions.autoCheckUpdates": false,
};

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolve(port));
    });
  });
}

// trust: ワークスペースの信頼を有効にして起動する（信頼されていない＝制限モードで開くことを確かめるため）。
export async function launch(workspace: string, scratch: string, options: { trust?: boolean } = {}): Promise<Session> {
  const executable = await downloadAndUnzipVSCode({ version: VSCODE_VERSION, cachePath: join(EXT_ROOT, ".vscode-test") });
  // ポータブル状態では設定・拡張・argv.json をこの下に置く（--user-data-dir も同じ場所を指す）。
  const portable = join(scratch, "portable");
  const userDir = join(portable, "user-data");
  mkdirSync(portable, { recursive: true });
  writeSettings(userDir, options.trust
    ? { ...BASE_SETTINGS, "security.workspace.trust.enabled": true, "security.workspace.trust.startupPrompt": "never" }
    : BASE_SETTINGS);
  const port = await freePort();
  const proc = spawn(executable, [
    workspace,
    `--remote-debugging-port=${port}`,
    `--extensionDevelopmentPath=${EXT_ROOT}`,
    `--user-data-dir=${userDir}`,
    `--extensions-dir=${join(portable, "extensions")}`,
    "--disable-extensions",
    ...(options.trust ? [] : ["--disable-workspace-trust"]),
    "--skip-welcome",
    "--skip-release-notes",
    "--disable-telemetry",
  ], { stdio: "ignore", env: { ...process.env, VSCODE_PORTABLE: portable } });

  let browser: Browser | null = null;
  try {
    browser = await waitFor("CDP への接続", async () => chromium.connectOverCDP(`http://127.0.0.1:${port}`), 60000);
    const connected = browser;
    const page = await waitFor("ワークベンチ", async () => {
      const pages = connected.contexts().flatMap((c) => c.pages()).filter((p) => p.url().includes("workbench.html"));
      return pages[0] || null;
    }, 60000);
    await page.waitForSelector(".monaco-workbench", { timeout: 60000 });
    await sleep(2500);

    const webviewCspErrors: string[] = [];
    page.on("console", (message) => {
      if (process.env.DIFF_REVIEW_E2E_DEBUG) { console.log("[console]", JSON.stringify(message.location()), message.text().slice(0, 160)); }
      // WebView の違反はコンソールの出どころ（location）が空で届く。ビューアの CSP だけが script-src に
      // nonce を使う（拡張が付ける。src/viewerHtml.ts）ので、その指令を含む違反をビューアのものとして数える。
      if (/Content Security Policy/i.test(message.text()) && /'nonce-/.test(message.text())) {
        webviewCspErrors.push(message.text());
      }
    });
    const webviewRequests: string[] = [];
    page.on("request", (request) => {
      const frameUrl = request.frame() ? request.frame().url() : "";
      if (frameUrl.startsWith("vscode-webview:") && /^(https?|wss?):/.test(request.url())) {
        webviewRequests.push(request.url());
      }
    });

    return {
      browser: connected, page, proc, userDir, webviewCspErrors, webviewRequests,
      async close() {
        await connected.close().catch(() => undefined);
        await stop(proc);
      },
    };
  } catch (err) {
    // 起動の途中で失敗しても、立ち上げた VSCode を残さない。
    if (browser) { await browser.close().catch(() => undefined); }
    await stop(proc);
    throw err;
  }
}

// 止めて、終わるまで待つ（終わる前に一時ディレクトリを消すと、終了時の書き込みで作り直される）。
async function stop(proc: ChildProcess): Promise<void> {
  if (proc.exitCode !== null || proc.signalCode !== null) { return; }
  const exited = new Promise<void>((resolve) => proc.once("exit", () => resolve()));
  proc.kill();
  await Promise.race([exited, sleep(10000)]);
  if (proc.exitCode === null && proc.signalCode === null) { proc.kill("SIGKILL"); }
}

async function openQuickInput(page: Page, key: string): Promise<void> {
  await page.keyboard.press(key);
  await page.waitForSelector(QUICK_INPUT, { timeout: 5000 });
}

// 候補の中から、ラベルが一致する行が出るのを待って選ぶ（先頭が「最近使った似たもの」のことがある）。
async function pickRow(page: Page, what: string, matches: (label: string) => boolean): Promise<void> {
  const row = await waitFor(what, async () => {
    const rows = page.locator(".quick-input-list .monaco-list-row");
    const count = await rows.count();
    for (let i = 0; i < count; i += 1) {
      const label = ((await rows.nth(i).locator(".label-name").first().textContent()) || "").trim();
      if (matches(label)) { return rows.nth(i); }
    }
    return null;
  }, 10000);
  await row.click();
  await sleep(500);
}

// VSCode のコマンドパレットからコマンドを実行する。
export async function runCommand(page: Page, label: string): Promise<void> {
  await openQuickInput(page, "F1");
  await page.keyboard.type(label);
  await pickRow(page, `コマンド「${label}」`, (text) => text === label);
}

// クイックオープンで開く。候補にそのファイルが出るのを待ってから選び、タブが開いたことを確かめる。
export async function openFile(page: Page, name: string): Promise<void> {
  await openQuickInput(page, "Control+p");
  await page.keyboard.type(name);
  await pickRow(page, `クイックオープンの「${name}」`, (text) => text === name);
  await waitFor(`「${name}」のタブ`, async () => page.evaluate((label) => {
    const tab = document.querySelector(".tabs-container .tab.active");
    return !!tab && (tab.getAttribute("aria-label") || "").startsWith(label);
  }, name), 10000);
}

async function saveDialog(page: Page, timeoutMs: number): Promise<boolean> {
  return waitFor("保存確認", async () => (await page.$(".monaco-dialog-box")) !== null, timeoutMs).catch(() => false);
}

// すべて閉じる。expectDirty でないのに保存確認が出たら失敗にする（未保存が紛れ込んでいたら見逃さない）。
export async function closeAllEditors(page: Page, expectDirty = false): Promise<void> {
  await runCommand(page, "View: Close All Editors");
  const asked = await saveDialog(page, 2000);
  if (asked) {
    await page.locator(".monaco-dialog-box .dialog-buttons a, .monaco-dialog-box .dialog-buttons button",
      { hasText: /Don't Save|保存しない/ }).first().click();
    await sleep(500);
    if (!expectDirty) { throw new Error("閉じるときに保存確認が出た（未保存が残っていた）"); }
  }
}

export async function expectSaveDialog(page: Page): Promise<void> {
  if (!(await saveDialog(page, 5000))) { throw new Error("保存確認が出ない"); }
}

// いま表示されているビューアの iframe（WebView の中身）。隠れた WebView は破棄される設定なので
// （retainContextWhenHidden: false）、ビューアの要素を持つ vscode-webview の frame が表示中のものになる。
export async function viewerFrame(page: Page): Promise<Frame> {
  return waitFor("ビューアの WebView", async () => {
    for (const frame of page.frames()) {
      if (!frame.url().startsWith("vscode-webview:") || frame.isDetached()) { continue; }
      const ok = await frame.evaluate(() => !!document.getElementById("files") && !!document.getElementById("banners"))
        .catch(() => false);
      if (ok) { return frame; }
    }
    return null;
  }, 30000);
}

export async function activeTabDirty(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const tab = document.querySelector(".tabs-container .tab.active");
    return !!tab && tab.classList.contains("dirty");
  });
}

// 画面の中でフォーカスが行にあるか（WebView がキーボードの行き先になっているか）。
export async function focusedRow(frame: Frame): Promise<string | null> {
  return frame.evaluate(() => (document.activeElement ? document.activeElement.getAttribute("data-key") : null));
}

export interface ViewState {
  files: number;
  rows: number;
  firstRow: string | null;
  threads: number;
  bodies: string[];
  active: string | null;
  pageScroll: number;
  paneScroll: number;
  banners: string[];
  dataTheme: string | null;
}

export async function viewState(frame: Frame): Promise<ViewState> {
  return frame.evaluate(() => {
    const pane = document.getElementById("pane-center");
    const active = document.activeElement as HTMLElement | null;
    const first = document.querySelector("#files .row[data-key]");
    return {
      files: document.querySelectorAll("#files .file").length,
      rows: document.querySelectorAll("#files .row[data-key]").length,
      firstRow: first ? first.getAttribute("data-key") : null,
      threads: document.querySelectorAll(".thread").length,
      bodies: Array.from(document.querySelectorAll(".thread .comment .body")).map((n) => (n.textContent || "").trim()),
      active: active ? active.getAttribute("data-key") : null,
      pageScroll: document.scrollingElement ? document.scrollingElement.scrollTop : 0,
      paneScroll: pane ? pane.scrollTop : 0,
      banners: Array.from(document.querySelectorAll("#banners .banner")).map((n) => (n.textContent || "").trim()),
      dataTheme: document.documentElement.getAttribute("data-theme"),
    };
  });
}
