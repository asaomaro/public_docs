# 研究: ナビゲーションまわりの改善 6 件

## F1: 隙間の一括展開ボタンが無い

`templates/app.js` の `expander(file, index, gap, shown, remaining)`（1115 行）は、
`up`（`.expand-up`・20 行ずつ下方向に開く）と `down`（`.expand-down`・20 行ずつ上方向に開く）の
2 個のボタンしか作らない。ファイル単位の「すべて展開」（`.expand-all`）はヘッダー（`.file-actions`）に
あるが、**その隙間そのものを一度に開く**ボタンは無い。

`expandAll(section, file)`（972 行）が使っている手法がそのまま流用できる:

```js
state[i] = { top: gap.end - gap.start + 1, bottom: 0 };
```

`shown.top` を隙間の全長に設定すれば、`renderGap` の `remaining = bottomStart - topEnd - 1` が
0 以下になり、その隙間の展開表示自体が消える（`shown.bottom` は使わなくてよい。片方の counter だけで
足りる——`expandAll` も同じ前提で書かれている）。

## F2: ツリーの名前が折り返すだけで省略されない

`.tree-name { flex: 1 1 auto; word-break: break-all; }`（style.css 519 行）。
`.tree-item` は `display: flex`（508 行）で、`.tree-name` に `min-width: 0` が無いので、
`flex: 1 1 auto` だけでは**縮まずに折り返す**（`word-break: break-all` は「あふれたら折り返す」意味で、
1 行に収める効果は無い）。`title` 属性も `appendTreeChildren`（app.js 685 行）のどちらの
`.tree-name` 生成（697 行=ディレクトリ・715 行=ファイル）にも付いていない。

`text-overflow: ellipsis` を効かせるには `overflow: hidden` ＋ `white-space: nowrap` ＋
**縮められる `min-width: 0`** の 3 点が要る（1 点でも欠けると効かない、よくある落とし穴）。

## F3: パネルの開閉ボタンがトップバーにある

`page.html` の `#btn-pane-left`/`#btn-pane-right`（26-29 行）は `.topbar .actions` の中にある。
`ui.js` の `setPane(which, open, save)`（122 行）は同じボタン 1 個の `aria-expanded`/`title`/
`aria-label` を開閉に応じて書き換えるだけで、**ボタンの DOM 上の位置には関与しない**。
つまり、ボタンを `.pane-head` の中へ**移設するだけ**なら `ui.js` のロジックは無改造で済む
（`document.getElementById("btn-pane-" + which)` で参照するだけなので、どこにあっても動く）。

閉じたときの見た目は `.shell[data-left="collapsed"] .pane-left { visibility: hidden; }`
（style.css 188 行）——**パネル全体を隠す**。ここへ「閉じたパネル自身に再度開くボタンを出す」を
乗せるには、`visibility: hidden` を外し、代わりに幅を細いストリップ（提案: 40px。
`.icon-btn` の `min-width: 30px` が border-box で収まる余白を確保）にして、
ボタン以外の子要素だけを非表示にする必要がある。

## F4: 一覧側がハイライトに追従しない

`applyCurrentFileHighlight()`（app.js 508 行）は `data-current` を付け外すだけで、
一覧側（`#filelist`。その親は `.pane` = `overflow: auto` の `#pane-left`）のスクロールには
一切触れていない。`entry.scrollIntoView({ block: "nearest" })` を追加すれば、
**すでに見えていれば何もしない・見えていなければ最小限だけ動かす**という要件（AC6）を
そのまま満たす（`focusInPlace` が `focus()` のための特別扱いをしているのとは違い、
ここは `.focus()` を呼ばないので、素の `scrollIntoView({block:"nearest"})` で十分——
ブラウザの既定のスクロール追従を心配する理由が無い）。

## F5: 検索欄・絞り込み欄がヘッダー扱いではない

`.pane-head`（style.css 191 行）は `position: sticky; top: 0;` を持つが、
`.filelist-tools`（587 行）・`.cl-filters`（530 行）には無い。両者は `.pane-head` の**直後の
兄弄**（page.html: `#pane-left` は `.pane-head` → `.filelist-tools` → `#filelist`、
`#pane-right` は `.pane-head` → `.cl-filters` → `#commentlist`）なので、`.pane-head` の高さが
変わっても両方が一緒に動く形にしたい。個別に `top` をピクセルで計算するより、
**両方を 1 つのラッパーに包んで、そのラッパー自体を sticky にする**方が、
高さの実測（`--topbar-h` のような JS 計測）を増やさずに済む。

## F6: 進捗バーが無い（`md-to-doc` との比較）

`docs/ClaudeCode/skills/other/md-to-doc/generate.py` に既存の実装がある（1010-1472 行）:

```css
.progress-track{position:fixed;top:0;left:0;right:0;height:7px;z-index:200;cursor:pointer;background:transparent}
.progress-track:hover{background:color-mix(in srgb,var(--accent) 14%,transparent)}
.progress{position:absolute;top:0;left:0;height:3px;width:0;background:var(--accent);transition:width .1s;pointer-events:none}
```

```js
function onScroll(){
  var h=document.documentElement,sc=h.scrollTop||document.body.scrollTop,mx=h.scrollHeight-h.clientHeight;
  if(bar)bar.style.width=(mx>0?sc/mx*100:0)+'%';
  ...
}
if(ptrack)ptrack.addEventListener('click',function(e){
  var r=ptrack.getBoundingClientRect(), ratio=(e.clientX-r.left)/r.width;
  ratio=Math.max(0,Math.min(1,ratio));
  window.scrollTo({top:(document.documentElement.scrollHeight-document.documentElement.clientHeight)*ratio,behavior:'smooth'});
});
```

`md-to-doc` はページ自体（`document.documentElement`）がスクロールする 1 ペイン構成なので、
そこを見ている。`diff-review-html` は**ページ自体は固定高さで、`#pane-center` だけが
スクロールする**（`.shell { height: calc(100vh - var(--topbar-h)); }` ・ `.pane { overflow: auto; }`）。
「画面全体のスクロール位置」を実際に体現しているのは `#pane-center`（差分を読む領域）なので、
そこを見る形に置き換える。`document.documentElement` を見ても、それ自体はスクロールしないので
常に 0% になる（実測するまでもなく、既存の `height: calc(100vh - ...)` の指定から自明）。

`#pane-center` のスクロールはすでに `wire()` 内で 1 箇所だけ監視している
（`currentFileTicking` による `requestAnimationFrame` 間引き。前 work
20260916-diff-review-current-file の実装）。**同じリスナーに進捗バーの更新を相乗りさせる**のが、
2 本目の scroll リスナーを増やさない自然な形。

## リスク

- **R1**: パネルの開閉ボタンを `.pane-head` の中へ移すと、`.pane-head` の子要素が増える
  （左は 4 個目、右は 2 個目）。`.pane-head { justify-content: space-between; }` のままだと
  閉じたときに 1 個だけ残る子要素の位置がずれる可能性がある——**閉じたときは
  `.pane-head` 自体のレイアウトも中央寄せへ切り替える**（`.shell[data-left="collapsed"] ...`
  の中でだけ上書き）。
- **R2**: `.pane-sticky`（F5 の新設ラッパー）の `z-index` が、`.tree-item:focus-visible` の
  `outline` や、行内の `.row[data-current="true"]` の `outline` と重ならないか——
  重なる要素はいずれもラッパーの**外**（`#filelist`/`#commentlist` の中）にあるので影響しない。
- **R3**: 進捗バー（`position: fixed; top: 0;`）が、`.topbar`（`position: sticky; top: 0; z-index: 5;`）
  の上に重なる。高さ 6-7px 程度なので、トップバーの文字を隠すほどではない
  （`md-to-doc` も同じ重なり方を採用している＝実運用で問題になっていない前例）。
- **R4**: パネルを閉じたときの幅（提案 40px）が、`.icon-btn` の `min-width: 30px`
  （`box-sizing: border-box` で padding 込み）に対して十分な余白を持つか——
  40px なら片側 5px の余白が残る。境界線（`.sep`）の 6px と合わせても圧迫感は無い。

## 結論（design への申し送り）

- F1: `expander()` に 3 番目のボタン（`.expand-gap-all`。テキスト「すべて表示」）を追加。
  クリック時は `shown.top = gap.end - gap.start + 1` を設定して `redrawFile(file, {gap:index, dir:"all"})`
  相当を呼ぶ（`redrawFile` の焦点探索は `.expand-` + dir のセレクタなので、`dir: "all"` は
  `.expand-all` という無関係のクラス（ファイル単位の「すべて展開」）と衝突しないよう、
  別のクラス名（例: `.expand-gap-all`）を使い、`focusHint.dir` には `"gap-all"` のような
  重複しない文字列を使う）。
- F2: `.tree-name` に `min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;`。
  `dir.name`/`entry.name` を `title` 属性にも渡す。
- F3: ボタンを `page.html` の `.pane-head` 内へ移設（`ui.js` は無改造）。CSS で
  「閉じたら幅を細くし、ボタン以外を隠す」を追加。
- F4: `applyCurrentFileHighlight()` の末尾で `entry.scrollIntoView({block:"nearest"})`。
- F5: `.pane-head` + `.filelist-tools`（左）／`.pane-head` + `.cl-filters`（右）を
  それぞれ 1 個のラッパー `div.pane-sticky` に包み、そのラッパーへ `position: sticky; top: 0;` を移す。
- F6: `page.html` に `.progress-track`/`.progress` を追加。既存の `#pane-center` scroll リスナー
  （前 work で追加済み）に幅の更新を相乗りさせ、クリックのハンドラを 1 つ追加する。
