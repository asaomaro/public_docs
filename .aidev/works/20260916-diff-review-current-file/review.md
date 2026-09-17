# レビュー記録

## ラウンド 1

- [should][conv:-] **ハイライトの背景が実際には見えていなかった**。`style.css` に足した
  `#filelist a[data-current="true"], .tree-item[data-current="true"] { background: var(--surface); ... }`
  の `var(--surface)` は、一覧が乗っている `.pane-left` 自体の既定の背景と**同じ色**
  （実測: `getComputedStyle` で両方とも `rgb(246, 248, 250)`）。結果として、ハイライトは
  左端の細い accent バー（`box-shadow`）だけで、背景の変化は無かった。コード中のコメントは
  「背景と文字の装飾を重ねる」と書いていたが、実装は背景側が効いていなかった。
  / 対応: 修正済（既存の `:hover`/`:focus-visible` と同じ `var(--bg)` に変更。一覧の既定背景
  `var(--surface)` とは別の色なので、実測でも背景色が変わることを確認した）

以下は確認して**指摘なし**と判断した:

- **判定ロジック**（`currentFileSection`）: `.file` は文書順に並ぶという前提が保たれていること
  （`renderFiles()` は `diffData.files` を順番に描画するだけで並び替えない）をコードで確認。
- **`applyCurrentFileHighlight` の呼び出し漏れが無いこと**: `renderFileList()`（描き直しのたび）・
  `renderAll()`（初期表示・`renderFiles()` の後）・`gotoFile()`（クリック直後）・
  `#pane-center` の `scroll`（`requestAnimationFrame` で間引き）の 4 箇所で網羅されている。
  検索・ツリー切り替え・確認済みチェックの再描画では `renderFileList()` を経由するので、
  個別に呼び直す必要がない（`syncFileListViewed` のような部分更新だけの箇所はハイライトの
  対象そのものを変えないので、呼ばなくてよい）。
- **記録に影響しないこと**（要件の暗黙の前提）: `data-current` は `viewedFiles` と同じく
  画面だけの状態で、`persist()`/`exportText()` のどちらにも触れていない。
- **新しいキー操作を追加していないこと**（AC9）: `addEventListener("keydown", ...)` の新規呼び出しは無い。
  `scroll` イベントへの購読のみ。
- **参照専用での動作**（AC5）: `applyCurrentFileHighlight` 系のコードは `readonly` を一切参照しない
  （既存の検索・確認済み・パスコピーと同じ「読む機能は隠さない」方針のまま）。

## ラウンド 2

**指摘なし**（must / should / nit いずれも 0 件）。ラウンド 1 の修正後、`uitest-current.js`
（通常・参照専用の両方）・前 work の回帰一式（`uitest.js`/`uitest-readonly.js`/`uitest-keys.js`）・
`python3 -m unittest tests.test_diff_review` を再実行し、全通過を確認した。
