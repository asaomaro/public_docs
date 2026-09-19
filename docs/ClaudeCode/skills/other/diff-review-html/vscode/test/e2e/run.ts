// 実機の VSCode での e2e（tasks.md T10）。`npm run test:e2e` で動かす。画面（WSLg 等）とネットワーク（初回の
// VSCode 取得）が要る。場面ごとに合否を出し、1 つでも落ちたら終了コード 1。使った一時ディレクトリは最後に消す
// （DIFF_REVIEW_E2E_KEEP=1 で残す）。
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { Frame, Page } from "playwright-core";
import {
  BASE_SETTINGS, PYTHON, SKILL_DIR, Session, activeTabDirty, bundleSummary, closeAllEditors, diffReview,
  expectSaveDialog, focusedRow, isCanonicalBundle, launch, openFile, preservedAndAppended, python, pythonResolve,
  runCommand, sleep, viewState, viewerFrame, waitFor, writeSettings,
} from "./harness";

const results: Array<{ name: string; ok: boolean; detail: string }> = [];
const notes: string[] = [];

function check(condition: unknown, message: string): void {
  if (!condition) { throw new Error(message); }
}

function git(repo: string, args: string[]): void {
  const r = spawnSync("git", ["-C", repo, "-c", "user.name=e2e", "-c", "user.email=e2e@example.invalid", ...args], { encoding: "utf8" });
  if (r.status !== 0) { throw new Error(`git ${args.join(" ")}: ${r.stderr}`); }
}

function prepare(scratch: string) {
  const ws = join(scratch, "ws");
  const repo = join(scratch, "repo");
  mkdirSync(ws, { recursive: true });
  check(python([join(SKILL_DIR, "tests", "fixture_repo.py"), repo]).status === 0, "fixture_repo.py");
  const sample = join(ws, "sample.dreview");
  const made = diffReview(["bundle", "--repo", repo, "--from", "commit", "--rev", "HEAD", "--out", sample]);
  check(made.status === 0, `bundle: ${made.stderr}`);
  check(diffReview(["comment", sample, "--body", "e2e: 全体への指摘"]).status === 0, "comment overall");
  check(diffReview(["comment", sample, "--path", "src/api/handler.py", "--line", "2", "--body", "e2e: 行への指摘", "--severity", "should"]).status === 0, "comment line");

  const text = readFileSync(sample, "utf8");
  writeFileSync(join(scratch, "sample.original.dreview"), text);
  writeFileSync(join(ws, "viewonly.dreview"), text);
  // 記録の target が差分の target と違う（別の差分への記録を --import で持ち込んだ形）。
  const foreign = python(["-c", [
    "import sys",
    `sys.path.insert(0, ${JSON.stringify(SKILL_DIR)})`,
    "import diff_review as dr",
    "b = dr.parse_bundle(sys.stdin.read())",
    "b['review']['target'] = dict(b['review']['target'], diff_digest='0' * 40)",
    "sys.stdout.write(dr.bundle_text(b['target'], b['files'], b['rich_enabled'], b['review']))",
  ].join("\n")], undefined, text);
  check(foreign.status === 0, foreign.stderr);
  writeFileSync(join(ws, "foreign.dreview"), foreign.stdout);
  writeFileSync(join(ws, "crlf.dreview"), text.replace(/\n/g, "\r\n"));
  writeFileSync(join(ws, "broken.dreview"), "これはバンドルではありません\n");

  // 2MB を超えるバンドル: 25,000 行のファイルを全行書き換えた差分。
  const bigRepo = join(scratch, "big");
  mkdirSync(bigRepo, { recursive: true });
  git(bigRepo, ["init", "-q"]);
  const lines = (tag: string) => Array.from({ length: 25000 }, (_, i) => `${tag} line ${i} ${"x".repeat(30)}`).join("\n") + "\n";
  writeFileSync(join(bigRepo, "big.txt"), lines("old"));
  git(bigRepo, ["add", "."]);
  git(bigRepo, ["commit", "-q", "-m", "old"]);
  writeFileSync(join(bigRepo, "big.txt"), lines("new"));
  git(bigRepo, ["commit", "-q", "-am", "new"]);
  const big = join(ws, "big.dreview");
  check(diffReview(["bundle", "--repo", bigRepo, "--from", "commit", "--rev", "HEAD", "--out", big]).status === 0, "big bundle");
  return { ws, sample, big, scratch };
}

async function scenario(name: string, body: () => Promise<void>): Promise<void> {
  try {
    await body();
    results.push({ name, ok: true, detail: "" });
    console.log(`PASS ${name}`);
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    results.push({ name, ok: false, detail });
    console.log(`FAIL ${name}: ${detail}`);
  }
}

async function focusFirstRow(frame: Frame): Promise<void> {
  await frame.evaluate(() => { (document.querySelector("#files .row[data-key]") as HTMLElement).focus(); });
}

async function openComposer(page: Page, frame: Frame): Promise<void> {
  await page.keyboard.press("c");
  await waitFor("入力欄", async () => frame.evaluate(() => !!document.activeElement && document.activeElement.tagName === "TEXTAREA"));
}

async function run(session: Session, fx: ReturnType<typeof prepare>): Promise<void> {
  const { page } = session;
  const expected = bundleSummary(fx.sample);

  await scenario("AC1/AC2/AC-I1/AC-I4: .dreview が既定で開き、バンドルと同じ差分とコメントが出て、先頭行にフォーカス", async () => {
    await openFile(page, "sample.dreview");
    const frame = await viewerFrame(page);
    const state = await waitFor("描画", async () => {
      const s = await viewState(frame);
      return s.files === expected.files && s.threads === expected.threads ? s : null;
    });
    expected.bodies.forEach((body) => check(state.bodies.includes(body), `本文が出ていない: ${body}`));
    check(state.active !== null && state.active === state.firstRow, `フォーカスが先頭行でない: ${state.active} / ${state.firstRow}`);
    const textEditor = await page.evaluate(() => !!document.querySelector(".editor-group-container.active .monaco-editor"));
    check(!textEditor, "テキストエディタで開いた");
    check(!(await activeTabDirty(page)), "開いただけで未保存になった");
  });

  await scenario("AC-I3: マウス無しで行を移動できる（j / k）", async () => {
    const frame = await viewerFrame(page);
    const start = await focusedRow(frame);
    check(start, "WebView の中の行にフォーカスが無い");
    await page.keyboard.press("j");
    const down = await waitFor("j で移動", async () => { const k = await focusedRow(frame); return k !== start ? k : null; });
    await page.keyboard.press("k");
    await waitFor("k で戻る", async () => (await focusedRow(frame)) === start);
    check(down, "移動しない");
  });

  await scenario("AC-I2: 書きかけを Esc で閉じても文書は変わらない", async () => {
    const frame = await viewerFrame(page);
    await openComposer(page, frame);
    await page.keyboard.type("e2e: キーボードで追加");
    await page.keyboard.press("Escape");
    await sleep(300);
    check(!(await activeTabDirty(page)), "Esc で閉じただけで未保存になった");
    check((await viewState(frame)).threads === expected.threads, "スレッドが増えた");
  });

  await scenario("AC3/AC-I2: コメントを確定すると未保存になる（書きかけは下書きから戻る）", async () => {
    const frame = await viewerFrame(page);
    await openComposer(page, frame);
    const draft = await frame.evaluate(() => (document.activeElement as HTMLTextAreaElement).value);
    check(draft === "e2e: キーボードで追加", `下書きが戻らない: ${draft}`);
    await page.keyboard.press("Control+Enter");
    await waitFor("スレッドが増える", async () => (await viewState(frame)).threads === expected.threads + 1);
    await waitFor("未保存", async () => activeTabDirty(page));
  });

  await scenario("AC4/AC-I3: Ctrl+S で保存され、check を通り、Python の正規形とバイト一致する", async () => {
    await page.keyboard.press("Control+s");
    await waitFor("保存", async () => !(await activeTabDirty(page)));
    const text = readFileSync(fx.sample, "utf8");
    check(text.includes("e2e: キーボードで追加"), "保存した中身に新しいコメントが無い");
    check(diffReview(["check", fx.sample]).status === 0, "check に通らない");
    check(isCanonicalBundle(fx.sample), "Python の bundle_text とバイト一致しない");
    const changed = preservedAndAppended(join(fx.scratch, "sample.original.dreview"), fx.sample);
    check(changed === null, `元の中身が変わった: ${changed}`);
    check(!text.includes("\r"), "CR が混ざった");
  });

  await scenario("AC-I5: 入力欄の Ctrl+Z は入力欄の取り消しで、文書の元に戻すにならない", async () => {
    // 文書には元に戻せる編集がある（直前の確定と保存）。入力欄の Ctrl+Z が文書へ漏れたら、スレッドが減り未保存になる。
    const frame = await viewerFrame(page);
    await focusFirstRow(frame);
    await openComposer(page, frame);
    await page.keyboard.type("undo-me");
    await page.keyboard.press("Control+z");
    await sleep(500);
    const value = await frame.evaluate(() => (document.activeElement as HTMLTextAreaElement).value);
    check(value === "", `入力欄が取り消されない: ${JSON.stringify(value)}`);
    check(!(await activeTabDirty(page)), "入力欄の Ctrl+Z が文書に届いた（未保存になった）");
    check((await viewState(frame)).threads === expected.threads + 1, "入力欄の Ctrl+Z でスレッドが消えた");
    await page.keyboard.press("Escape");
  });

  await scenario("AC6: VSCode の元に戻す・やり直しが画面に反映される", async () => {
    const frame = await viewerFrame(page);
    await focusFirstRow(frame);
    await page.keyboard.press("Control+z");
    await waitFor("元に戻す", async () => (await viewState(frame)).threads === expected.threads);
    check(await activeTabDirty(page), "元に戻したのに未保存でない");
    await page.keyboard.press("Control+Shift+z");
    await waitFor("やり直し", async () => (await viewState(frame)).threads === expected.threads + 1);
    await waitFor("保存時点に戻る", async () => !(await activeTabDirty(page)));
  });

  await scenario("AC8/AC-I4: 外部での追記に、スクロール位置と現在行を保ったまま追従する", async () => {
    const frame = await viewerFrame(page);
    await focusFirstRow(frame);
    for (let i = 0; i < 40; i += 1) { await page.keyboard.press("j"); }
    await sleep(300);
    const before = await viewState(frame);
    check(before.active, "前提: 現在行がある");
    check(before.pageScroll + before.paneScroll > 0, "前提: スクロールしている");
    const rectBefore = await frame.evaluate(() => (document.activeElement as HTMLElement).getBoundingClientRect().top);
    const last = await frame.evaluate(() => {
      const rows = document.querySelectorAll("#files .row[data-key]");
      return (rows[rows.length - 1] as HTMLElement).getAttribute("data-key");
    });
    const m = /^line:(.+):(LEFT|RIGHT):(\d+)$/.exec(last || "");
    check(m, `最後の行の鍵が読めない: ${last}`);
    const r = diffReview(["comment", fx.sample, "--path", m![1], "--side", m![2], "--line", m![3], "--body", "e2e: 外部からの追記"]);
    check(r.status === 0, r.stderr);
    const after = await waitFor("外部変更の反映", async () => {
      const s = await viewState(frame);
      return s.threads === expected.threads + 2 ? s : null;
    }, 20000);
    const rectAfter = await frame.evaluate(() => (document.activeElement as HTMLElement).getBoundingClientRect().top);
    check(after.active === before.active, `現在行が変わった: ${before.active} → ${after.active}`);
    check(Math.abs(after.pageScroll - before.pageScroll) <= 1 && Math.abs(after.paneScroll - before.paneScroll) <= 1,
      `スクロールが動いた: ${JSON.stringify([before.pageScroll, before.paneScroll])} → ${JSON.stringify([after.pageScroll, after.paneScroll])}`);
    check(Math.abs(rectAfter - rectBefore) <= 2, `現在行の画面上の位置が動いた: ${rectBefore} → ${rectAfter}`);
    check(!(await activeTabDirty(page)), "外部変更で未保存になった");
  });

  await scenario("AC-I5: WebView の中から VSCode のキー（Ctrl+P）が効く", async () => {
    const frame = await viewerFrame(page);
    check(await focusedRow(frame), "前提: WebView の中の行にフォーカスがある");
    await page.keyboard.press("Control+p");
    await page.waitForSelector(".quick-input-widget:not([style*='display: none']) input", { timeout: 5000 });
    await page.keyboard.press("Escape");
  });

  await scenario("AC15: VSCode の配色に合わせ、切り替えにその場で追従する", async () => {
    const frame = await viewerFrame(page);
    try {
      await waitFor("ダーク", async () => (await viewState(frame)).dataTheme === "dark");
      writeSettings(session.userDir, { ...BASE_SETTINGS, "workbench.colorTheme": "Default Light Modern" });
      await waitFor("ライトへ追従", async () => (await viewState(frame)).dataTheme === "light", 20000);
    } finally {
      writeSettings(session.userDir, BASE_SETTINGS);
    }
    await waitFor("ダークへ追従", async () => (await viewState(frame)).dataTheme === "dark", 20000);
  });

  await scenario("AC-I1: 「エディターを開き直す」でテキストエディタを選べる", async () => {
    await runCommand(page, "View: Reopen Editor With...");
    const items = await waitFor("選択肢", async () => {
      const labels = await page.$$eval(".quick-input-list .monaco-list-row", (rows) => rows.map((r) => r.textContent || ""));
      return labels.some((t) => /Text Editor|テキスト エディター/.test(t)) && labels.some((t) => t.includes("Diff Review")) ? labels : null;
    });
    check(items.length >= 2, `選択肢: ${items}`);
    await page.keyboard.press("Escape");
  });

  await scenario("AC7: 未保存のまま閉じると VSCode 標準の保存確認が出る", async () => {
    const frame = await viewerFrame(page);
    await focusFirstRow(frame);
    await openComposer(page, frame);
    await page.keyboard.type("e2e: 閉じる前の変更");
    await page.keyboard.press("Control+Enter");
    await waitFor("未保存", async () => activeTabDirty(page));
    const saved = readFileSync(fx.sample);
    await runCommand(page, "View: Close Editor");
    await expectSaveDialog(page);
    await page.locator(".monaco-dialog-box .dialog-buttons a, .monaco-dialog-box .dialog-buttons button", { hasText: /Don't Save|保存しない/ }).first().click();
    await sleep(500);
    check(Buffer.compare(saved, readFileSync(fx.sample)) === 0, "保存しないを選んだのにファイルが変わった");
  });

  await scenario("AC5: 見るだけ・変更せずに保存・変更して元に戻してから保存、のどれでもバイト列が変わらない", async () => {
    const file = join(fx.ws, "viewonly.dreview");
    const original = readFileSync(file);
    await openFile(page, "viewonly.dreview");
    const frame = await viewerFrame(page);
    await waitFor("描画", async () => (await viewState(frame)).files === expected.files);
    const toggled = await frame.evaluate(() => {
      const box = document.querySelector(".file-head input[type=checkbox]") as HTMLInputElement | null;
      if (!box) { return false; }
      box.click();
      return true;
    });
    check(toggled, "確認済みのチェックが見つからない");
    await focusFirstRow(frame);
    await page.keyboard.press("j");
    await sleep(800);
    check(!(await activeTabDirty(page)), "見るだけで未保存になった");
    await page.keyboard.press("Control+s");
    await sleep(800);
    check(Buffer.compare(original, readFileSync(file)) === 0, "変更せずに保存したらバイト列が変わった");

    await openComposer(page, frame);
    await page.keyboard.type("e2e: 元に戻す前提");
    await page.keyboard.press("Control+Enter");
    await waitFor("未保存", async () => activeTabDirty(page));
    await focusFirstRow(frame);
    await page.keyboard.press("Control+z");
    await waitFor("元に戻す", async () => !(await activeTabDirty(page)));
    await page.keyboard.press("Control+s");
    await sleep(800);
    check(Buffer.compare(original, readFileSync(file)) === 0, "変更して元に戻してから保存したらバイト列が変わった");
    await closeAllEditors(page);
  });

  await scenario("AC4/AC5: 画面での解決は Python の resolve と同じバイト列になり、未解決に戻すと元に戻る（記録の target も保つ）", async () => {
    const file = join(fx.ws, "foreign.dreview");
    const original = readFileSync(file);
    const expectedResolved = pythonResolve(file, join(fx.scratch, "resolved.dreview"), "t1");
    await openFile(page, "foreign.dreview");
    const frame = await viewerFrame(page);
    await waitFor("描画", async () => (await viewState(frame)).threads === expected.threads);
    const press = async (label: string) => frame.evaluate((l) => {
      const button = Array.from(document.querySelectorAll('.thread[data-thread="t1"] button'))
        .find((b) => (b.textContent || "").includes(l)) as HTMLButtonElement | undefined;
      if (!button) { return false; }
      button.click();
      return true;
    }, label);
    check(await press("解決にする"), "解決のボタンが無い");
    await waitFor("未保存", async () => activeTabDirty(page));
    await focusFirstRow(frame);
    await page.keyboard.press("Control+s");
    await waitFor("保存", async () => !(await activeTabDirty(page)));
    check(Buffer.compare(readFileSync(file), expectedResolved) === 0, "Python の resolve --thread t1 とバイト一致しない");
    check(await press("未解決に戻す"), "未解決に戻すのボタンが無い");
    await waitFor("未保存", async () => activeTabDirty(page));
    await focusFirstRow(frame);
    await page.keyboard.press("Control+s");
    await waitFor("保存", async () => !(await activeTabDirty(page)));
    check(Buffer.compare(readFileSync(file), original) === 0, "未解決に戻して保存しても元のバイト列に戻らない");
    await closeAllEditors(page);
  });

  await scenario("AC5/D2: CRLF の .dreview は開いただけでは書き換えず、最初の編集で正規形（LF）になる", async () => {
    const file = join(fx.ws, "crlf.dreview");
    const original = readFileSync(file);
    await openFile(page, "crlf.dreview");
    const frame = await viewerFrame(page);
    await waitFor("描画", async () => (await viewState(frame)).threads === expected.threads);
    await sleep(800);
    check(!(await activeTabDirty(page)), "開いただけで未保存になった");
    await focusFirstRow(frame);
    await openComposer(page, frame);
    await page.keyboard.type("e2e: CRLF への追記");
    await page.keyboard.press("Control+Enter");
    await waitFor("未保存", async () => activeTabDirty(page));
    await page.keyboard.press("Control+s");
    await waitFor("保存", async () => !(await activeTabDirty(page)));
    const text = readFileSync(file, "utf8");
    check(original.includes(Buffer.from("\r\n")), "前提: 元は CRLF");
    check(!text.includes("\r"), "CRLF のまま");
    check(isCanonicalBundle(file), "正規形でない");
    await closeAllEditors(page);
  });

  await scenario("AC9: 壊れた .dreview は理由を出し、直ると表示する", async () => {
    await openFile(page, "broken.dreview");
    const frame = await viewerFrame(page);
    const broken = await waitFor("理由", async () => {
      const s = await viewState(frame);
      return s.banners.some((b) => b.includes("表示できません")) ? s : null;
    });
    check(broken.rows === 0, "壊れているのに行が出ている");
    copyFileSync(join(fx.ws, "viewonly.dreview"), join(fx.ws, "broken.dreview"));
    const fixed = await waitFor("直った", async () => { const s = await viewState(frame); return s.rows > 0 ? s : null; }, 20000);
    check(!fixed.banners.some((b) => b.includes("表示できません")), `理由が残った: ${fixed.banners}`);
    await closeAllEditors(page);
  });

  await scenario("AC14: 2MB を超えるバンドルで、コメントの確定から画面への反映が 1 秒以内", async () => {
    const size = statSync(fx.big).size;
    check(size > 2 * 1024 * 1024, `バンドルが小さい: ${size}`);
    await openFile(page, "big.dreview");
    const frame = await viewerFrame(page);
    // 2,000 行を超える差分のファイルは既定で畳まれて行が描かれないので、全体へのコメントで測る。
    await waitFor("描画", async () => (await viewState(frame)).files === 1, 30000);
    await frame.evaluate(() => { (document.querySelector("#overall .comment-open") as HTMLElement).click(); });
    await waitFor("入力欄", async () => frame.evaluate(() => !!document.activeElement && document.activeElement.tagName === "TEXTAREA"));
    await page.keyboard.type("e2e: 大きなバンドル");
    await frame.evaluate(() => {
      const w = window as unknown as { __shown: number; __start: number };
      w.__shown = 0;
      const observer = new MutationObserver(() => {
        if (document.querySelectorAll(".thread").length > 0) {
          observer.disconnect();
          // 描画のあとの最初のフレームまで待って「画面に出た」とする。
          requestAnimationFrame(() => { w.__shown = performance.now(); });
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
      w.__start = performance.now();
    });
    const t0 = Date.now();
    await page.keyboard.press("Control+Enter");
    await waitFor("未保存", async () => activeTabDirty(page), 10000);
    const dirtyMs = Date.now() - t0;
    const shownMs = await waitFor("画面反映の計測", async () => frame.evaluate(() => {
      const w = window as unknown as { __shown: number; __start: number };
      return w.__shown ? w.__shown - w.__start : null;
    }), 5000);
    notes.push(`AC14: バンドル ${size} バイト / 確定→画面反映 ${Math.round(shownMs)}ms / 確定→文書が未保存 ${dirtyMs}ms`);
    check(shownMs < 1000, `画面反映 ${shownMs}ms`);
    await frame.evaluate(() => { (document.querySelector("#overall .comment-open") as HTMLElement).focus(); });
    const u0 = Date.now();
    await page.keyboard.press("Control+z");
    await waitFor("元に戻す", async () => (await viewState(frame)).threads === 0, 10000);
    notes.push(`AC14: 元に戻す→画面反映 ${Date.now() - u0}ms（その場の差し替え）`);
    await closeAllEditors(page);
  });

  await scenario("AC10: CSP 違反と WebView からの外部通信が 0 件で、nonce の無いスクリプトと eval は動かない", async () => {
    check(session.webviewCspErrors.length === 0, `CSP: ${session.webviewCspErrors.join(" | ")}`);
    check(session.webviewRequests.length === 0, `通信: ${session.webviewRequests.join(" | ")}`);
    // 陽性対照: CSP が本当に効いていること、上の違反の検出が空振りでないことを確かめる。
    await openFile(page, "viewonly.dreview");
    const frame = await viewerFrame(page);
    await waitFor("描画", async () => (await viewState(frame)).files === expected.files);
    const inlineRan = await frame.evaluate(() => {
      const script = document.createElement("script");
      script.textContent = "window.__cspProbe = 1";
      document.head.appendChild(script);
      // CDP から評価したコードは CSP の対象外で、その最中は文字列の評価も一時的に許される。eval は正しい nonce 付きの
      // ページのスクリプトから、評価が終わったあとのタイマーで試す。
      const nonce = (document.querySelector("script[nonce]") as HTMLScriptElement | null)?.nonce || "";
      const trusted = document.createElement("script");
      trusted.nonce = nonce;
      trusted.textContent = "setTimeout(function () { try { eval('1'); window.__evalProbe = 'ran'; } catch (e) { window.__evalProbe = 'blocked'; } }, 0);";
      document.head.appendChild(trusted);
      return (window as unknown as { __cspProbe?: number }).__cspProbe === 1;
    });
    const evalProbe = await waitFor("eval の試行", async () => frame.evaluate(() => (window as unknown as { __evalProbe?: string }).__evalProbe || null), 5000);
    check(!inlineRan, "nonce の無いスクリプトが動いた");
    check(evalProbe === "blocked", `eval: ${evalProbe}`);
    await waitFor("違反がコンソールで検出される（検出の経路が生きている）", async () => session.webviewCspErrors.length > 0, 5000);
    notes.push(`AC10: 陽性対照の違反を検出（${session.webviewCspErrors.length} 件）`);
    await closeAllEditors(page);
  });
}

async function main(): Promise<void> {
  const scratch = mkdtempSync(join(tmpdir(), "diff-review-e2e-"));
  let session: Session | null = null;
  try {
    const fx = prepare(scratch);
    console.log(`fixtures: ${fx.ws}（python: ${PYTHON}）`);
    session = await launch(fx.ws, scratch);
    await run(session, fx);
    await session.close();
    session = null;
    // 信頼されていないワークスペース（制限モード）でも開ける（AC10）。別の VSCode として、信頼を有効にして起動する。
    session = await launch(fx.ws, join(scratch, "trust"), { trust: true });
    const trusted = session;
    await scenario("AC10: 信頼されていないワークスペース（制限モード）でも開いて表示できる", async () => {
      const restricted = await waitFor("制限モード", async () => trusted.page.evaluate(() =>
        Array.from(document.querySelectorAll(".statusbar-item, .window-title, .titlebar"))
          .some((n) => /Restricted Mode|制限モード/.test(n.textContent || ""))), 15000);
      check(restricted, "制限モードになっていない（前提）");
      await openFile(trusted.page, "viewonly.dreview");
      const frame = await viewerFrame(trusted.page);
      await waitFor("描画", async () => (await viewState(frame)).files > 0);
    });
  } finally {
    if (session) { await session.close(); }
    if (!process.env.DIFF_REVIEW_E2E_KEEP) {
      await sleep(1000);
      rmSync(scratch, { recursive: true, force: true });
    }
  }

  console.log("");
  notes.forEach((n) => console.log(`NOTE ${n}`));
  const failed = results.filter((r) => !r.ok);
  console.log(`RESULT: ${results.length - failed.length} passed / ${failed.length} failed`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
