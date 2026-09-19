# タスク: `.dreview` を VSCode で開いて読み書きする拡張機能

## 実装方針

design.md の 2 つの側を、互いに依存しない順に組み立てる。

- **拡張側**（`vscode/`）: 足場 → VSCode に依存しない純粋な部品（CSP 付与・最小の書き換え範囲・同期の列）を
  `node:test` で固めてから → VSCode との結線（`editorProvider` / `extension`）。
- **画面側**（`templates/`）: `app.js` の橋渡し（同期の状態と採用）→ ホストがいるときの出し分け → `ui.js` の配色 →
  Python の unittest の静的な検査。
- 両側が揃ったら、**実機の VSCode を CDP で操作する e2e** で通し、最後に文書（README・`SKILL.md`）とパッケージ。

split 判定: subtask に割らない。拡張と画面は相互に依存して初めて検証でき（高結合）、合わせても 1 PR に収まる規模。

## 作業順序と依存関係

下の `依存:` に従う。依存では表せない順序の理由:

- **`SyncSession`（T4）を最初に固める**。design の独立点検の指摘が集中した箇所で（decisions.md D11）、見立てが外れたら
  画面側（T6）の手順も変わる。順序のテストが通ってから画面側に同じ手順を写す（T6 の `依存: T4`）。
- 検証は e2e（T10）が最後。実機の起動に時間がかかるので、純粋な部品の不具合は unit テストで先に潰しておく。
  文書（T11）とパッケージ（T12）は e2e で確かめた内容（手順・既知の制約）を書くので、その後に置く。

## リスク / 留意点

- `acquireVsCodeApi` は 1 回しか呼べない（research.md F11）。呼ぶのは `app.js` の 1 か所だけ。
- `#file-import` は外さない（`wire()` が無条件に結線する。design.md「依拠する既存の事実」）。
- `tests/test_diff_review.py:955-957` の縛り: `__DIFF_REVIEW_BUNDLE__` を含む行を `app.js` に増やさない。
- e2e はユーザーデータを毎回新しくし、ファイルは起動後にクイックオープンで開く（research.md「実装時の注意」）。
- ルートの `.gitignore` は `/node_modules` しか外さない。`vscode/.gitignore` を先に置いてから `npm install` する。
- 利用者の VSCode（Windows 側の `code`）には一切触れない。実機の検査はテスト用に取得した VSCode だけで行う。

## テスト方針

- Python の unittest（既存 140 件＋追加）: HTML 版の回帰（AC12）と、橋渡しが HTML 版で眠っていることの静的な検査。
- `node:test`（`npm run test:unit`）: `withCsp`・`minimalEdit`・`SyncSession` の順序・同梱物 == `view` の出力（AC11）。
- e2e（`npm run test:e2e`）: 実機の VSCode（1.138.0 linux-x64）を `--remote-debugging-port` で起動し、playwright-core の
  `connectOverCDP` で実キー入力を送る。開く・描画の一致・コメント・保存（`check` と Python の `bundle_text` とのバイト一致）・
  元に戻す／やり直し・入力欄の `Ctrl+Z`・外部変更（スクロールと現在行の維持）・壊れた文書・CRLF の文書・配色・CSP 違反 0・
  閉じるときの確認・2MB のバンドルの所要時間。
- test 工程で、HTML 版を headless Chromium で開いて書き込みの流れが今どおりであることも確かめる（AC12 の実行時側）。
- `aidev smoke`（既存の 3 本）。拡張は CLI の入口を足さないので `smokeCommands` は増やさない（理由は test-result.md に書く）。

## タスク

- [x] T1: `vscode/` の足場を作る（`package.json`・`tsconfig.json`・`.gitignore`・`.vscodeignore`・
      `scripts/build-viewer.mjs`）。開発依存を入れ、`package.json` の `scripts` に `build:viewer`・`compile`・`build`・
      `test:unit`・`test:e2e`・`package` を置き、`npm run build:viewer` と `npm run compile` が通る状態にする。
      対象: `docs/ClaudeCode/skills/other/diff-review-html/vscode/`（新規）/ 根拠: design.md「拡張（`vscode/`）」・decisions.md D5, D6
      依存: なし
      AC: AC13, AC16
- [x] T2: `src/viewerHtml.ts`（`withCsp` / `makeNonce`）と unit テスト。行頭の `<script` にだけ nonce、`<meta charset>` の直後に
      CSP、同梱物（`media/viewer.html`）が `view` の出力と一致すること。
      対象: `vscode/src/viewerHtml.ts`・`vscode/test/unit/viewerHtml.test.ts`（新規）/ 根拠: design.md「拡張」の CSP・nonce、research.md F4-F6
      依存: T1
      AC: AC10, AC11
- [x] T3: `src/minimalEdit.ts` と unit テスト（同一・前後だけの差・全体の差・サロゲートペアと CRLF の途中で切らない）。
      対象: `vscode/src/minimalEdit.ts`・`vscode/test/unit/minimalEdit.test.ts`（新規）/ 根拠: design.md「`SyncSession`（1 本の列）」
      依存: T1
      AC: AC3, AC5
- [x] T4: `src/sync.ts`（`SyncSession`）と順序の unit テスト: ready → text／edit → ack／すれ違い（退け・`conflict`）／
      元に戻す → やり直し／続けざまの編集／版だけ進む／書けない／書いている途中の変更／作り直し中の ready／dispose。
      対象: `vscode/src/sync.ts`・`vscode/test/unit/sync.test.ts`（新規）/ 根拠: design.md「`SyncSession`（1 本の列）」・decisions.md D10, D11
      依存: T1
      AC: AC3, AC6, AC8, AC14, AC-I2
- [x] T5: `src/editorProvider.ts` と `src/extension.ts`: WebView の設定（`enableScripts`・`localResourceRoots: []`）、`withCsp` した
      HTML、`SyncSession` の生成と VSCode のイベントとの結線、`applyText`（`minimalEdit` ＋ CRLF なら `setEndOfLine(LF)`）、
      `warn`、破棄。
      対象: `vscode/src/editorProvider.ts`・`vscode/src/extension.ts`（新規）/ 根拠: research.md A15、design.md「拡張」
      依存: T2, T3, T4
      AC: AC1, AC7, AC10, AC-I1
- [x] T6: `app.js` の橋渡し: `bundleText`・同期の状態（`hostText` ほか）・`onHostText` / `onHostAck` / `applyHostText` /
      `sendHostEdit`、`persist()` と `boot()` のホストがいるときの分岐、`message` リスナーへの `text` / `ack` の追加。
      対象: `templates/app.js:57` `applyDiffData`・`:95` `adoptBundle`・`:205-261` 正規形・`:265` `persist`・`:2763` `message` リスナー・
      `:2840` `boot` / 根拠: research.md A1-A7
      依存: T4
      AC: AC2, AC3, AC4, AC5, AC6, AC8, AC9, AC-I4
- [x] T7: `app.js` の `wireHost`: HTML 版だけの操作を外す（`#file-import` は残す）、D&D を取り込まない、`beforeunload` を
      しない、開く案内を出さない、入力欄の `Ctrl/⌘+Z` / `Ctrl/⌘+Y` の `stopPropagation`、`ready` の送信。
      対象: `templates/app.js:2587` `wire`・`:2773-2819`・`:2835` `showOpenPrompt` / 根拠: research.md A8, A9
      依存: T6
      AC: AC-I3, AC-I5
- [x] T8: `ui.js` の配色: 「自動」のとき `<body>` の `vscode-*` クラスから `data-theme` を決め、`MutationObserver` で追従し、
      ボタンの説明を「テーマ: VSCode に従う」にする。
      対象: `templates/ui.js:68` `applyTheme`・`:81` `cycleTheme`・`:255` 起動時の適用 / 根拠: research.md A10
      依存: なし
      AC: AC15
- [x] T9: Python の unittest を足す: `acquireVsCodeApi` の呼び出しが `typeof … === "function"` の分岐の中の 1 か所だけ・
      `ui.js` の配色の分岐が `vscode-` クラスで閉じている・`view` の出力の縛り（既存）が保たれている。既存 140 件と合わせて通す。
      対象: `tests/test_diff_review.py:932-972` の近く / 根拠: research.md A13
      依存: T6, T7, T8
      AC: AC11, AC12
- [x] T10: e2e（`vscode/test/e2e/`）: テスト用 VSCode の取得・CDP での起動・fixture の生成（`tests/fixture_repo.py` と
      `diff_review.py bundle`）と、テスト方針に挙げた場面を通す。
      対象: `vscode/test/e2e/run.ts` ほか（新規）/ 根拠: research.md の調査手順（`keys-probe` / `run-probe` の形）、design.md「受け入れ基準との対応」
      依存: T5, T6, T7, T8
      AC: AC1, AC2, AC4, AC5, AC6, AC7, AC8, AC9, AC10, AC14, AC15, AC-I1, AC-I2, AC-I3, AC-I4, AC-I5
- [x] T11: 文書: `vscode/README.md`（ビルド・インストール・テスト・既知の制約）と `SKILL.md` の「エディタ拡張から使う」節の更新
      （書き込みを含むメッセージの契約・拡張の場所）。
      対象: `vscode/README.md`（新規）・`SKILL.md:454-468` / 根拠: research.md A14
      依存: T5, T6, T7, T10
      AC: AC13
- [x] T12: パッケージ: `npm run package` で `.vsix` を作り、`vsce ls` で中身（`node_modules`・`src`・`test` が無い）を確かめる。
      `git status` で生成物が出ないことを確かめる。
      対象: `vscode/package.json` の `package` スクリプト・`vscode/.vscodeignore` / 根拠: design.md「拡張」の `.vscodeignore`
      依存: T1, T5, T10, T11
      AC: AC13, AC16
