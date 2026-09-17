# タスク: 現在表示中のファイルを一覧でハイライト

## 作業順序と依存関係

1. T1（判定関数）を先に作り、T2（scroll 監視・適用箇所への配線）で使う。
   1 タスクに分けているのは、判定ロジック単体と配線側の懸念（いつ呼ぶか）を分けたいため
   （`design.md` の「設計方針」が判定・「対象範囲」が配線箇所を分けているのに対応）。

## テスト方針

- headless Chromium（`file://`・固定入力 `tests/fixture_repo.py`）:
  - 初期表示でいちばん上のファイルにハイライトが付いていること（AC6）。
  - `#pane-center` をスクロールし、別のファイルが上部に来たらハイライトが移ること・
    同時に 2 件以上ハイライトされないこと（AC1・AC2）。
  - フラット・ツリー双方で同じ結果になること（AC3）。
  - 検索で現在ファイルが絞り込まれて消えたとき、例外にならず静かにハイライトが消えること（AC4）。
  - `--readonly` でも同じに動くこと（AC5）。
  - 一覧の項目をクリックしてファイルへ移動した直後にハイライトが即座に移ること（AC7）。
  - 確認済み（打ち消し線）とハイライトが同じ項目で共存できること（AC8）。
- `python3 -m unittest tests.test_diff_review` の既存回帰を再実行（無関係のはずだが確認）。
- キー操作を増やしていないこと（AC9）はコードレビューで確認（新しい `addEventListener("keydown", ...)` を
  足していないことを見る）。

## タスク

- [x] T1: 現在ファイルの判定関数（`getBoundingClientRect()` で `.file` の上端とペイン上端を比較し、
      最後に上端を超えたセクションを返す）
      対象: `templates/app.js` / 根拠: design「設計方針」
      依存: なし
      AC: AC1, AC6
- [x] T2: ハイライトの適用と配線（`data-current` の付け外し・`renderFileList()` での再適用・
      `#pane-center` の scroll listener（`requestAnimationFrame` で間引く）・`gotoFile()` での
      即時反映・`renderAll()` での初期適用）、`style.css` に `data-current="true"` の見た目
      対象: `templates/app.js`, `templates/style.css` / 根拠: design「対象範囲」
      依存: T1
      AC: AC2, AC3, AC4, AC5, AC7, AC8, AC9
