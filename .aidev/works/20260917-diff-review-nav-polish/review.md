# レビュー記録

## ラウンド 1

**指摘なし**（must / should / nit いずれも 0 件）。以下は確認して**指摘なし**と判断した:

- **F1（隙間の一括展開）**: `.expand-gap-all` のクリックハンドラが `shown.top` だけを隙間の全長に
  設定し、`shown.bottom` に触れていないこと（`expandAll` と同じ前提を踏襲）をコードで確認。
  実測（`uitest-nav.js`）でも、隙間の先頭（`index === 0`・`down` ボタンが無い側）・末尾
  （`index === hunks.length`・`up` ボタンが無い側）のどちらでも「すべて表示」ボタン自体は
  常に出ることを確認した。
- **F2（ツリー名の省略）**: `min-width: 0` を欠くと `flex: 1 1 auto` だけでは `ellipsis` が
  効かない、という研究段階で見つけた落とし穴が、実装した CSS に実際に含まれていることを
  コードで確認。`title` 属性の文字列が表示テキストと完全に一致すること（`dir.name`/`entry.name`
  をどちらにも同じ値で渡している）を実測で確認した。
- **F3（パネル開閉ボタンの移設）とモバイル幅への影響**: `ui.js` を実際に無改造で済ませたこと
  （`grep` で確認: `ui.js` の diff は 0 行）。design の段階で見込んだモバイル退行
  （開閉ボタンをパネルの中へ移したことで、900px 以下の「閉じたら `display:none`」と衝突し、
  二度と開けなくなる）が、実装した該当 CSS の書き換えによって実際に防がれていることを
  480px 幅の headless Chromium で実測した（`uitest-mobile.js`）。
- **F4（一覧のスクロール追従）**: `scrollIntoView({block:"nearest"})` が「すでに見えていれば
  何もしない」という要件（AC6 後段）をブラウザの標準動作としてそのまま満たすこと
  （`focusInPlace` のような可視判定の自前実装が要らない）を、実測（一覧を先頭へ戻した状態で
  すでに見えている項目に対して呼び、`scrollTop` が変わらないこと）で確認した。
- **F5（sticky ラッパー）**: `.pane-head` から外した `position`/`top`/`z-index` の 3 プロパティが
  `.pane-sticky` 側に正しく移っていること、`background`/`padding`/`border-bottom` は
  重複したまま残っていて実害が無いことをコードと実測（スクロールしても top が変わらない）の
  両方で確認した。
- **F6（進捗バー）**: 新しい scroll リスナーを増やさず、前 work で追加済みの
  `#pane-center` scroll リスナー（`requestAnimationFrame` 間引き）に相乗りしていることを
  コードで確認（`centerPane.addEventListener("scroll", ...)` の呼び出しが 1 か所のまま）。
  `.progress-track`（`z-index: 200`）が `.skip:focus`（`top: 8px`・`z-index: 10`）と
  垂直方向に重ならないこと（バーの高さ 6px ＜ skip リンクの `top: 8px`）を計算で確認した。
- **参照専用での動作**（AC11）: F1〜F6 のどのコードにも `readonly` の分岐が無いこと
  （新しい導線はいずれも「読む」機能であり、書き込みの導線ではないため）をコードで確認し、
  `--readonly` で生成した画面で AC1〜AC10 の全項目を実測でも確認した（test-result.md）。
- **既存キー操作の不変**（AC12）: `focusPane`（`[`/`]`）・`wireSeparator`（`{`/`}`・矢印キー）の
  コードが今回無改造であること、`#btn-tree`・`#file-search` 等の ID・イベント配線を変えていない
  ことをコードで確認。実測（`uitest-pane-keys.js`）でも、移設後のボタンを直接クリックしたときの
  `aria-expanded` の反転を含めて確認した。
- 被覆: `aidev coverage --strict` は design/tasks 承認時に 100%（AC1〜AC12 の 12/12）。
  coding 中に `AC:` の無いタスクは増えていない。

## ラウンド 2

再確認のみ（新しい変更は無い）。`uitest-nav.js`（通常・`--readonly`）・`uitest-pane-keys.js`・
`uitest-mobile.js`・前 work までの回帰一式（計 70 件超）・`python3 -m unittest tests.test_diff_review`
（126 件）を再実行し、全通過を確認した。**指摘なし**。
