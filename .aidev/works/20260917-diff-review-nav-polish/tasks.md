# タスク: ナビゲーションまわりの改善 6 件

## 実装方針

6 件のうち F1（隙間の一括展開）・F2（ツリー名の省略）・F4（一覧のスクロール追従）は
互いに独立したコードを触るので並行に進められる。F3（ボタン移設）と F5（検索欄・絞り込み欄の
固定）は**どちらも `page.html` の `.pane-head` 周りを触る**ので、F3 を先に済ませてから
F5 を重ねる（design の F5 の HTML 例も「既存 + F3 のボタン」を前提に書いている）。
F6（進捗バー）は F4 と同じ scroll リスナーに相乗りするが、触る関数は別なので独立で進めてよい。

## 作業順序と依存関係

- **T4（F5・sticky ラッパー）を T3（F3・ボタン移設）のあとに**。両方とも `page.html` の
  `#pane-left`/`#pane-right` 内側（`.pane-head` 周り）を書き換えるため、先に F3 でボタンを
  `.pane-head` に足してから、F5 でその `.pane-head` ごとラッパーに包む方が、
  同じ場所を 2 回に分けて触らずに済む。
- 他のタスクに順序の制約は無い（`依存` 欄のとおり）。

## リスク / 留意点

- **R3（research R3）**: 進捗バー（`position: fixed; top: 0;`）が `.topbar`（`position: sticky; top: 0;`）
  と重なる。高さ 6px 程度なので実害は無い前提——T6 で実測して確認する。
- **R4（research R4）**: 閉じたパネルの幅 40px が `.icon-btn`（`min-width: 30px`）に対して
  窮屈でないか——T3 で実測して確認する。
- **モバイル退行の見落とし防止**（design F3）: ボタンをパネルの中へ移すと、既存の
  「900px 以下では閉じたパネルを `display:none` で丸ごと隠す」CSS と衝突し、モバイルで
  閉じたパネルを二度と開けなくなる。T3 はこの CSS の書き換えも含む（design 参照）。
- **各タスクの終わりに既存の性質を確認する**（決定論・`f`/`e`/`t`/`[`/`]`/`{`/`}` キーが
  同じ対象に効くこと・参照専用でも動くこと）。

## テスト方針

design.md「テスト方針」のとおり。要約:

- headless Chromium（`file://`・固定入力 `tests/fixture_repo.py`）で AC1〜AC12 をそれぞれ検査
  （通常モード・`--readonly` モードの両方）。
- `python3 -m unittest tests.test_diff_review` の既存回帰（無関係のはずだが確認）。
- 前 work（20260916-diff-review-ux-polish・20260916-diff-review-current-file）で作った
  書き捨ての回帰スクリプト一式を再実行し、影響が無いことを確認する
  （ツリー・検索・確認済み・パスコピー・畳む・展開位置維持・現在ファイルのハイライト）。

## タスク

- [x] T1: 隙間の一括展開ボタン（`expander()` に `.expand-gap-all` を追加し、up/down と並べる）
      対象: `templates/app.js` / 根拠: design§F1
      依存: なし
      AC: AC1
- [x] T2: ツリー名の省略とツールチップ（`.tree-name` の CSS・`appendTreeChildren` の `title` 属性）
      対象: `templates/app.js`, `templates/style.css` / 根拠: design§F2
      依存: なし
      AC: AC2, AC3
- [x] T3: パネル開閉ボタンの移設（トップバーから各 `.pane-head` へ。閉じたときの見た目・
      モバイル幅での退行防止を含む）
      対象: `templates/page.html`, `templates/style.css` / 根拠: design§F3
      依存: なし
      AC: AC4, AC5
- [x] T4: 検索欄・絞り込み欄の固定（`.pane-head` + 道具欄を `.pane-sticky` ラッパーに包む）
      対象: `templates/page.html`, `templates/style.css` / 根拠: design§F5
      依存: T3
      AC: AC7, AC8
- [x] T5: ファイル一覧のスクロール追従（`applyCurrentFileHighlight()` に `scrollIntoView` を追加）
      対象: `templates/app.js` / 根拠: design§F4
      依存: なし
      AC: AC6
- [x] T6: 進捗バー（HTML・CSS の新設、`updateProgressBar()`・クリックでの移動・初期表示への反映）
      対象: `templates/page.html`, `templates/style.css`, `templates/app.js` / 根拠: design§F6
      依存: なし
      AC: AC9, AC10
- [x] T7: 画面側の検証コード整備・実行（scratch のブラウザ検証スクリプト。通常モード・
      `--readonly` の両方で AC1〜AC10 を検査）
      対象: 未特定（test 工程で作成・書き捨て） / 根拠: design「テスト方針」
      依存: T1, T2, T3, T4, T5, T6
      AC: AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9, AC10, AC11
- [x] T8: **画面の受け入れ確認・回帰（消化は test 工程）**。T7 に加え、既存キー操作の不変
      （AC12）・前 work までの回帰一式・`python3 -m unittest tests.test_diff_review` の再実行
      対象: 未特定（test 工程で実施） / 根拠: design「既存への影響と回帰」
      依存: T7
      AC: AC12
