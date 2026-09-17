# テスト結果: 現在表示中のファイルを一覧でハイライト

## ラウンド 1

### 実行したもの

- `python3 -m unittest tests.test_diff_review`（生成側の既存回帰） — **126 passed / 0 failed / 0 skipped**
- `aidev smoke` — **pass（exit 0、3 本）**
- headless Chromium（`file://`・固定入力 `tests/fixture_repo.py --staged`）:
  - `uitest-current.js`（この機能の新規検査・11 件）— **11 passed**（通常モード・参照専用モードの
    両方で実行。計 22 件）
    - 初期表示でいちばん上のファイルだけがハイライトされる（AC6）
    - 最後のファイルへスクロール → ハイライトがそこへ移り、同時に 2 件以上つかない（AC1・AC2）
    - 上へスクロールし直すと先頭のファイルへ戻る（AC1・AC2）
    - ツリー表示でも同じ結果になる（AC3）
    - 一覧の項目をクリックした直後（スクロールの完了を待たず）にハイライトが移る（AC7）
    - 検索で現在ファイルが絞り込まれて消えても例外にならず、ハイライトが単に付かない（AC4）
    - 確認済み（打ち消し線）とハイライトが同じ項目で共存する（AC8）
  - 既存の回帰一式（前 work・20260916-diff-review-ux-polish で作った書き捨てスクリプト）も
    再実行し、影響が無いことを確認 — `uitest.js`（23 件）・`uitest-readonly.js`（7 件）・
    `uitest-keys.js`（5 件）すべて **pass**

### 結果

全項目 **合格**。差し戻しなし。

## 受け入れ基準（AC）との対応

| AC | 検査 | 結果 |
|---|---|---|
| AC1（スクロールでハイライトがつく） | `uitest-current.js` scroll → highlight | pass |
| AC2（同時に 1 件だけ・移動する） | 同上 | pass |
| AC3（フラット・ツリー双方） | `uitest-current.js` tree mode | pass |
| AC4（絞り込みで消えても例外にならない） | `uitest-current.js` search filters out | pass |
| AC5（参照専用でも動く） | `uitest-current.js` を `--readonly` の生成物で再実行 | pass |
| AC6（初期表示でも先頭がハイライト） | `uitest-current.js` initial load | pass |
| AC7（クリック直後に即座反映） | `uitest-current.js` click → immediate highlight | pass |
| AC8（確認済みと共存） | `uitest-current.js` viewed + current | pass |
| AC9（新しいキー操作を増やさない） | 実装レビュー（`addEventListener("keydown", ...)` を追加していないことを確認） | pass |

## 既存への影響

- `python3 -m unittest tests.test_diff_review` は変更前と同じ 126 件が全通過（生成側は無変更）。
- 前 work（ツリー表示・検索・確認済み・パスコピー・畳む・展開位置維持）の回帰スクリプトを
  再実行し、影響が無いことを確認済み。
