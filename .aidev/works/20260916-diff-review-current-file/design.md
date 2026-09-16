# 設計: 現在表示中のファイルを一覧でハイライト

## 設計方針

**中央ペイン（`#pane-center`）のスクロール位置から「いま画面上部にあるファイル」を求め、
左の一覧（`#filelist`）の対応する項目に `data-current="true"` を付ける。** 外部ライブラリは使わない
（`IntersectionObserver` ではなく、既存の `focusInPlace` と同じ `getBoundingClientRect()` ベースの
幾何計算に寄せる——このファイルは既にその流儀で書かれている）。

判定は「各 `.file` セクションの上端が、ペインの上端（読んでいる位置の目印）以上に来ている最後の
セクション」（一般的な scrollspy の手法）。スクロールのたびに毎回計算すると重いので、
`requestAnimationFrame` で 1 フレームに 1 回へまとめる。

ハイライトの対象は、前 work（20260916-diff-review-ux-polish）で `#filelist` のフラット `<a>` /
ツリー `.tree-item.tree-file` の両方に**既に `data-path` 属性が付いている**ので、
それをそのままセレクタに使う。新しい属性は増やさない。

## 対象範囲

- `templates/app.js`: スクロール監視・現在ファイルの判定・ハイライトの付け外し。
  `renderFileList()`（描き直しのたびに再適用）・`gotoFile()`（クリック直後に即座反映）・
  `wire()`（スクロールの listener）・`renderAll()`（初期表示）に手を入れる。
- `templates/style.css`: `data-current="true"` の見た目（`data-viewed="true"` の打ち消し線と共存する
  色付け）。

対象外: `page.html`（新しい要素は増やさない）・生成側（Python）・レビュー記録の JSON
（画面だけの状態で、記録には入らない——`viewedFiles` と同じ扱い）。

## 依拠する既存の事実

- `#pane-center` が実際のスクロールコンテナ（`.pane { overflow: auto }`）。
- `#filelist a` と `.tree-item.tree-file` の両方に `data-path` が既に付いている
  （20260916-diff-review-ux-polish の `syncFileListViewed` と同じ前提）。
- `.row[data-current="true"]` が既に「いまの行」を示す属性名として使われている
  （`outline` で示す）。同じ `data-current` という名前を、意味の近い「いまの対象」として
  ファイル一覧側にも使う（属性名の一貫性）。
- `focusInPlace` が同じ `getBoundingClientRect()` ベースの可視判定を既に持っている
  （車輪の再発明をしない）。

## AC ごとの実現方法

- AC1: `currentFileSection()` の幾何計算＋ `applyCurrentFileHighlight()` が `data-current="true"` を付ける。
- AC2: `applyCurrentFileHighlight()` は呼ばれるたびに既存の `[data-current="true"]` を全部外してから
  1 件だけ付け直すので、常に高々 1 件になる。
- AC3: ハイライトの対象は `#filelist` 内の `[data-path]` セレクタで、フラット `<a>` / ツリー
  `.tree-item.tree-file` のどちらにも同じコードが対応する。
- AC4: `nav.querySelector('[data-path="..."]')` が見つからなければ何もしない（例外を投げない）。
- AC5: `applyCurrentFileHighlight` 系のコードは `readonly` を参照しない（既存の検索/確認済みと同じ方針）。
- AC6: `renderAll()` が `renderFiles()`（`.file` を作る）のあとにもう一度 `applyCurrentFileHighlight()`
  を呼ぶ。
- AC7: `gotoFile()` が `scrollIntoView`/`focus()` の直後に同期的に呼ぶ（scroll イベントを待たない）。
- AC8: `data-current` と `data-viewed` は別々の CSS ルールで、互いを上書きしない。
- AC9: 新規の `addEventListener` は `scroll`（既存要素向け）だけで、`keydown` は増やさない。
