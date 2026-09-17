# 仕様: レビュー操作性の改善（ツリー見た目・レビュー提出フロー・固定ヘッダー・コメント折りたたみ・通知ベル）

## 概要

`templates/page.html` / `templates/style.css` / `templates/app.js` / `templates/ui.js` に対し、
requirements.md の F1〜F6 を実装する。方針は一貫して「PJ 内に既に確立されている部品・語彙
（Disclosure トグル・composer フォーム・icon-btn）を再利用し、新しい UI 語彙を増やさない」。
新しい実装機構は 2 点に絞る: フォルダ/ファイル/検索/ベルのアイコン用インライン SVG
（research.md F6・「design への申し送り」）と、通知ベル用の浮動ポップオーバー（下記 F6）。

## 設計方針

- **F1（ツリー見た目）**: 追加/削除行数の表示・ロジックは変更しない（decisions.md D2）。
  新規に「SVG スプライト」（`page.html` に一度だけ `<symbol>` を定義し、各行では
  `<svg><use></use></svg>` で参照する）を導入し、フォルダ/ファイル/検索アイコンを表示する。
  検索欄の角丸は既存の `.file`/button 系で使っている `8px` に揃える（参考画像のピル型
  そのままではなく、この画面の既存の角丸の強さに合わせる。過度に浮いた見た目を避ける）。
- **F2/F3（レビュー提出フローの統合）**: ボタンを新設せず、既存の `#btn-start-review` の
  トグル挙動（`templates/app.js` の `updatePendingCount`/`wire()`）をそのまま使い、
  重複していた `#btn-submit-open` を削除する。提出済みレビュー結果の一覧・編集・削除は、
  既存の composer 型フォーム（`#submit-panel` の判定ラジオ＋サマリ textarea＋確定ボタン）を
  「新規作成モード」と「編集モード」で使い回す（新しいフォーム部品を増やさない）。
- **F4（sticky ファイルヘッダー）**: research.md F1〜F3 の結論のとおり、`.file` の
  `overflow: hidden` を外し、角丸クリップの責務を `.file-head`（上 2 角）と `.file-body`
  （`overflow-y: hidden` ＋下 2 角）に移す。`.file-head` に `position: sticky; top: 0;` を足す。
- **F5（コメント折りたたみ）**: 既存の `toggleFile()`（ファイル折りたたみ）と同じ
  Disclosure パターンを `renderThread()` に適用する。スコープ（全体/ファイル/行）による
  分岐は不要——3 スコープとも同じ `renderThread()` を通るため、1 箇所の変更で全スコープに効く。
- **F6（通知ベル）**: research.md の「design への申し送り」のとおり、固定パネル方式
  （`#help`/`#submit-panel` と同じ、トップバー直下に押し出す方式）ではなく、ベルボタンの
  真下に重ねて出す**浮動ポップオーバー**にする。`UI.syncTopbarHeight()` の対象に含めず、
  レイアウトを動かさない。`banner()` 呼び出しのうち、research.md F7 の表で「対応不要」と
  分類した 2 箇所（`templates/app.js:110,1887`）だけを新関数 `notify()` に差し替える。

## 対象範囲

- `templates/page.html`: SVG スプライト定義、トップバーのボタン構成、`#submit-panel` の中身、
  ベルボタン＋通知ポップオーバーの器。
- `templates/style.css`: `.file`/`.file-head`/`.file-body`、`.tree-item` 系、`#file-search`、
  新規: `.icon`、`.thread` の折りたたみ、`.notif-*`、`.review-entry` 系。
- `templates/app.js`: ツリー描画、レビュー提出まわり、`renderThread()`、`banner()`/`notify()`、
  `applyDiffData()`（`threadCollapsed` のリセット対象に追加）、`onKeyDown()`（通知パネル/
  編集キャンセルの `Escape` 分岐への追記）。
- `templates/ui.js`: 変更なし（F6 を浮動ポップオーバーにしたため `syncTopbarHeight()` の
  対象リストに触れずに済む。research.md「design への申し送り」で確認済み）。

## 依拠する既存の事実

- `.file` の `overflow: hidden` が sticky を無効化する（research.md F1、
  `templates/style.css:317` で確認）。
- `.file-body` の `overflow-x: auto` は longhand なので `overflow-y: hidden` を追加併記しても
  横スクロールは壊れない（research.md F3。CSS 仕様上の一般的な性質で、このリポジトリ固有の
  確認箇所は無い＝該当なし）。
- Disclosure パターン（トグルボタン＋`aria-expanded`＋隣接領域の表示切替）は
  `toggleFile()`（`templates/app.js:953-965`）、`setPane()`（`templates/ui.js:122-138`）、
  `#btn-help-open`（`templates/app.js:2180-2184`）の 3 箇所で確立済み（research.md F4）。
- composer フォーム（textarea＋select＋確定/閉じるボタン、`Escape`/`Ctrl+Enter` 対応）は
  `openComposer()`（`templates/app.js:1712-1781`）で確立済み（research.md F5）。
- `banner()` 呼び出し 16 箇所の分類は research.md F7 の表のとおり（`templates/app.js` 内、
  行番号つきで全件確認済み）。
- `ThemeCssTest`（`tests/test_diff_review.py:699-737`）は `:root` の `--d-*` トークンが
  2 つの dark-assign ブロックに同一に割り当てられていることを検査する（research.md F8）。
  今回の設計では新規色トークンを追加しない（下記「ドメイン固有の考慮」）ため、この
  テストへの影響は無い見込み。

## インターフェース / データ構造

### SVG アイコン（`page.html` + `app.js`）

`page.html` の `<body>` 直後（`.skip` リンクの前）に、非表示の SVG スプライトを 1 つ置く。

```html
<svg aria-hidden="true" style="position:absolute;width:0;height:0;overflow:hidden">
  <symbol id="icon-folder" viewBox="0 0 20 20">…</symbol>
  <symbol id="icon-file" viewBox="0 0 20 20">…</symbol>
  <symbol id="icon-search" viewBox="0 0 20 20">…</symbol>
  <symbol id="icon-bell" viewBox="0 0 20 20">…</symbol>
</svg>
```

各 `<symbol>` の中身は `stroke="currentColor" fill="none" stroke-width="1.4"
stroke-linecap="round" stroke-linejoin="round"` を基調にした単色の線画（塗りつぶしなし）。
具体的な path 座標は coding 時に微調整してよい（見た目の微修正は設計の逸脱ではない）。

`app.js` の `el()`（`templates/app.js:136-151`）の隣に、SVG 版のヘルパーを追加する
（**`innerHTML` は使わない**——`createElementNS` と `setAttribute` だけで組み立てる）:

```js
var SVG_NS = "http://www.w3.org/2000/svg";
function icon(name, cls) {
  var svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "icon icon-" + name + (cls ? " " + cls : ""));
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  var use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", "#icon-" + name);
  svg.appendChild(use);
  return svg;
}
```

ツリー描画（`appendTreeChildren()`、`templates/app.js:703-739`）で、フォルダ行には
`icon("folder")` を、ファイル行には `icon("file")` を `.tree-twisty` の直後・`.tree-name`
の直前に挿入する。検索欄のアイコンは動的に変わらないので `page.html` に静的な
`<svg class="icon icon-search" aria-hidden="true" focusable="false"><use href="#icon-search"></use></svg>`
を直接書く（`.filelist-tools` の中、`#file-search` の手前。CSS で入力欄に重ねて絶対配置する）。
静的に書く SVG も `icon()` ヘルパーと同じく `aria-hidden="true" focusable="false"` を必ず
両方付ける（装飾アイコンであることを一貫させる）。

### レビュー提出フローの単一ボタン化（F2）

- `page.html` の `rw:begin`/`rw:end` ブロック（`templates/page.html:31-35`）から
  `#btn-submit-open` を削除する。`#btn-start-review` と `#btn-export-open` は残す。
- `wire()`（`templates/app.js:2148-2314`）から `submitOpen`（`#btn-submit-open`）の結線
  （`templates/app.js:2152-2164` のうち `submitOpen` 部分）を削除する。ただし
  `#btn-submit-do`/`#btn-submit-close` の結線はそのまま残す（`startButton`
  （`templates/app.js:2165-2171`）が**パネルを開く唯一の経路**になる。閉じる経路は
  従来どおり `#btn-submit-close`・`Escape`・`startButton` 自身の再クリックの複数がある）。
- `updatePendingCount()`（`templates/app.js:1849-1861`）のラベル文言を
  `"レビュー中（提出する）"` → `"レビュー結果を入力"` に変える。ボタンの活性条件
  （`reviewStarted || pendingComments().length > 0`）は変えない。

### 提出済みレビュー結果の一覧・編集・削除（F3）

`#submit-panel`（`templates/page.html:71-88`）に、既存の `<fieldset>`（判定）と
`<textarea id="review-body">`（サマリ）の**前**に一覧領域を追加する:

```html
<div id="review-list" class="review-list" aria-label="提出済みのレビュー結果"></div>
```

`app.js` に状態と関数を追加する:

```js
var editingReviewId = null;   // null = 新規作成モード。id なら編集中のエントリ

function renderReviewList() {
  var host = document.getElementById("review-list");
  if (!host) { return; }
  clear(host);
  if (!state.reviews.length) {
    host.appendChild(el("p", { class: "empty", text: "提出したレビュー結果はまだありません" }));
    return;
  }
  state.reviews.forEach(function (review) { host.appendChild(reviewEntry(review)); });
}

function reviewEntry(review) {
  // 判定バッジ＋サマリの要約＋「編集」「削除」ボタン。renderComment()
  // （`templates/app.js:1531-1563`）の「返信」「取り消し」と同じ並び（row-actions）に揃える。
}

function editReview(review) {
  editingReviewId = review.id;
  document.querySelector('input[name="review-state"][value="' + review.state + '"]').checked = true;
  document.getElementById("review-body").value = review.body;
  document.getElementById("btn-submit-do").textContent = "保存する";
  // 専用の「キャンセル」ボタンは新設しない（設計方針: 新しいフォーム部品を増やさない）。
  // 編集の取り消しは、下記「振る舞いの詳細」のとおりパネルを閉じる操作
  // （#btn-submit-close / Escape）を cancelEditReview() の呼び出し先とすることで賄う。
}

function cancelEditReview() {
  editingReviewId = null;
  document.getElementById("review-body").value = "";
  document.querySelector('input[name="review-state"][value="COMMENTED"]').checked = true;
  document.getElementById("btn-submit-do").textContent = "提出する";
}

function deleteReview(review) {
  state.reviews = state.reviews.filter(function (r) { return r !== review; });
  state.threads.forEach(function (thread) {
    thread.comments.forEach(function (comment) {
      if (comment.review_id === review.id) { comment.review_id = null; }
    });
  });
  if (editingReviewId === review.id) { cancelEditReview(); }
  persist();
  renderThreads();   // 「未提出」バッジの再計算＋末尾で renderReviewList() も呼ぶ（下記）
}
```

`submitReview()`（`templates/app.js:1871-1888`）を分岐させる:
- `editingReviewId` が null → 従来どおり新規の `review` を `state.reviews` に push。
- `editingReviewId` が非 null → 該当エントリの `state`/`body` を書き換え、
  `editingReviewId` を null に戻す（編集完了後は新規作成モードへ）。
  **紐づくコメントの `review_id` はそのまま**（判定・サマリだけを差し替える。
  どのコメントがこのレビューに属するかは変えない）。

`#btn-submit-discard`（`templates/page.html:85`）と `discardPending()`
（`templates/app.js:1890-1898`）、およびその結線（`templates/app.js:2160`）を削除する。

`renderThreads()`（`templates/app.js:1445-1456`）の末尾で `renderReviewList()` も呼ぶ
（`state.reviews` が変わる操作は persist → renderThreads の流れに乗っているため）。

### ファイルヘッダーの固定（F4）

```css
.file { border: 1px solid var(--line); border-radius: 8px; margin-bottom: 16px; }
.file-head {
  position: sticky;
  top: 0;
  z-index: 2;
  border-radius: 8px 8px 0 0;
  /* 既存の display/padding/背景/border-bottom はそのまま */
}
.file-body { overflow-x: auto; overflow-y: hidden; border-radius: 0 0 8px 8px; }
```

`.file` から `overflow: hidden` を削除する。`z-index: 2` は `.pane-sticky`
（`templates/style.css:209`）と同じ値に揃える（左右ペインとは別の描画コンテキストなので
競合しない）。

### コメントスレッドの折りたたみ（F5）

`app.js` に画面状態を追加する（保存しない。`collapsed`/`expandState` 等と同じ扱い）:

```js
var threadCollapsed = {};   // thread.id -> true なら畳んでいる
```

`renderThread()`（`templates/app.js:1493-1529`）の `actions` に、`toggleFile()` と同じ
語彙のボタンを追加する:

```js
var foldButton = el("button", {
  type: "button", class: "thread-fold icon-btn",
  "aria-expanded": threadCollapsed[thread.id] ? "false" : "true",
  title: threadCollapsed[thread.id] ? "展開する" : "折りたたむ",
  "aria-label": (threadCollapsed[thread.id] ? "展開する: " : "折りたたむ: ") + locationLabel(thread),
  text: threadCollapsed[thread.id] ? "▸" : "▾"
});
foldButton.addEventListener("click", function () {
  threadCollapsed[thread.id] = !threadCollapsed[thread.id];
  renderThreads();
  // renderThreads() は DOM を作り直すので、押したボタン自身を id で指し直してフォーカスを
  // 戻す（AC-I4）。`redrawFile()`（`templates/app.js:1165-1189`）が現在行を指し直すのと
  // 同じ考え方: 描き直し前に対象の thread.id を覚えておき、描き直し後に同じ id の
  // `.thread-fold` を検索して `focusInPlace()`（`templates/app.js:1194-1203`）に渡す。
  var again = document.querySelector(
    '.thread[data-thread="' + cssEscape(thread.id) + '"] .thread-fold');
  focusInPlace(again || foldButton);
});
actions.appendChild(foldButton);
```

`node`（スレッドのルート `div`）に `"data-collapsed": threadCollapsed[thread.id] ? "true" : "false"`
を追加する。CSS:

```css
.thread[data-collapsed="true"] > .comment,
.thread[data-collapsed="true"] > .composer-slot { display: none; }
```

（`.thread-head` はこのセレクタの対象外なので常に見える。位置・解決状態・重大度は
`.thread-head` の中に既にある。）

### 通知ベル（F6）

`page.html` の `.actions`（`templates/page.html:28-40`）に、`#btn-help-open` の手前へ追加:

```html
<div class="notif-wrap">
  <button type="button" id="btn-notif" class="icon-btn" aria-expanded="false"
          aria-controls="notif-panel" title="通知" aria-label="通知">
    <svg class="icon icon-bell" aria-hidden="true" focusable="false"><use href="#icon-bell"></use></svg>
    <span id="notif-badge" class="notif-badge" hidden>0</span>
  </button>
  <section id="notif-panel" class="notif-panel" hidden aria-label="通知一覧">
    <div id="notif-list"></div>
  </section>
</div>
```

`app.js` に状態と関数を追加する:

```js
var notifications = [];   // { id, message, ts } の配列。新しい順に unshift
var notifUnread = 0;
var NOTIF_LIMIT = 50;     // 際限なく増やさない（research.md「実装時の注意」の考え方に合わせる）

function notify(message) {
  // banner() と違い key による置き換えは持たない（対象は research.md F7 の「対応不要」
  // 2 箇所のみで、いずれも同じ内容が短時間に連続する想定が薄いため。件数は NOTIF_LIMIT で頭打ちにする）。
  notifications.unshift({ id: nextId("n"), message: message, ts: Date.now() });
  if (notifications.length > NOTIF_LIMIT) { notifications.length = NOTIF_LIMIT; }
  notifUnread += 1;
  renderNotifList();
  updateNotifBadge();
}

function renderNotifList() {
  var host = document.getElementById("notif-list");
  if (!host) { return; }
  clear(host);
  if (!notifications.length) {
    host.appendChild(el("p", { class: "empty", text: "通知はまだありません" }));
    return;
  }
  notifications.forEach(function (n) {
    host.appendChild(el("p", { class: "notif-item", text: n.message }));
  });
}

function updateNotifBadge() {
  var badge = document.getElementById("notif-badge");
  if (!badge) { return; }
  badge.hidden = notifUnread === 0;
  badge.textContent = String(notifUnread);
}

function toggleNotifPanel() {
  var panel = document.getElementById("notif-panel");
  var button = document.getElementById("btn-notif");
  var open = panel.hidden;
  panel.hidden = !open;
  button.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) { notifUnread = 0; updateNotifBadge(); }
}
```

`banner()` 呼び出しの差し替え対象は research.md F7 の表のとおり 2 箇所のみ:
- `templates/app.js:110`: `banner("読み込みました…", [], "load")` →
  `notify("読み込みました（" + (source || "不明") + "）: " + (bundle.files || []).length + " ファイル")`
- `templates/app.js:1887`: `banner("レビューを提出しました…", [])` →
  `notify("レビューを提出しました（" + stateValue + "）。JSON を書き出して渡してください。")`

他の 14 箇所は変更しない。

## 振る舞いの詳細

- 通知ポップオーバーは `position: absolute` でベルボタンの真下・右揃えに出す
  （`.notif-wrap { position: relative; }`）。`UI.syncTopbarHeight()` の対象リストには
  加えない（レイアウトを動かさない浮動要素のため。ui.js は無改造）。
- ポップオーバーを開いた時点で `notifUnread` を 0 にする（AC16）。通知の**一覧内容**は
  既読後も残る（消す操作は今回のスコープ外。requirements「対象外」参照）。
- レビュー結果の編集中（`editingReviewId` が非 null）にパネルを閉じる（`Escape` /
  `#btn-submit-close`）と、編集は暗黙にキャンセルされる（`cancelEditReview()` を呼ぶ）。
  保存されていない入力は失われるが、`state.reviews` 側のエントリ自体は変更されない
  （AC-I2 の「キャンセルすると変更前の内容のまま残る」を満たす）。
- 編集中のエントリを一覧から「削除」した場合も、`cancelEditReview()` を呼んでフォームを
  新規作成モードへ戻す（存在しない id を指したまま「保存する」を押せる状態を防ぐ）。
- スレッドの折りたたみ状態（`threadCollapsed`）は `applyDiffData()`
  （`templates/app.js:56-74`）でリセットする対象に加える（差分を読み替えたときに
  前の差分の折りたたみが残らないようにする。`viewModes`/`expandState`/`collapsed` と同じ扱い）。
- ツリーのフォルダ/ファイルアイコンは、検索による絞り込み・パスの省略表示（`title` 属性での
  全体表示）と共存する（`appendTreeChildren()` の既存のロジックは変えず、アイコンを
  追加するだけ）。

## ドメイン固有の考慮

- **`innerHTML` を使わない**という既存の約束（`templates/app.js:4-5`）は、SVG アイコンを
  `createElementNS` + `setAttribute` で組み立てることで守る。
- **新規の色トークンを追加しない**（`ThemeCssTest` の 2 ブロック同時更新を避ける。
  research.md F8）。アイコンは `stroke="currentColor"` で親要素の `color`
  （既存の `--fg`/`--muted` 等）にそのまま追従させる。通知バッジの背景色は既存の
  `--danger` を再利用する。
- **新規のグローバルキーボードショートカットを追加しない**（requirements 非機能要件）。
  折りたたみ・ベル・編集/削除ボタンはすべて通常の `<button>` として実装し、既存の
  `onKeyDown()`（`templates/app.js:2037-2131`）には新しいキー分岐を足さない。
  ただし `Escape` での通知パネル/編集キャンセルは、既存の `Escape` 分岐
  （`templates/app.js:2126-2130`、`showPanel("submit-panel", false)` 等）に**追加の行として**
  合流させる（新しいキーの割り当てではなく、既存の `Escape` の効き先を増やすだけ）。
- **オフライン単一 HTML** の制約上、SVG アイコンの `<symbol>` 定義も `page.html` に
  インラインで埋め込む（外部ファイル参照をしない）。

## エラー処理 / 異常系

- `state.reviews` が空の状態で `#review-list` を描画する場合、「提出したレビュー結果は
  まだありません」という空状態メッセージを出す（`renderCommentList()` 等、既存の空状態表示
  と同じ語彙）。
- レビュー結果の編集で、判定（ラジオ）やサマリが未入力のまま「保存する」を押した場合、
  既存の `submitReview()` と同じ検証（`pendingComments` が無く `body` も空なら
  `banner("提出するコメントもサマリもありません。", [])` を出して確定しない）を編集モードにも
  適用する。
- 通知の配列は `NOTIF_LIMIT`（50件）を超えたら古いものから捨てる（無制限に増やして
  `localStorage`/メモリを圧迫しないため。通知は永続化しないので、セッションが終われば
  どのみち消える）。

## 受け入れ基準との対応

- AC1: `appendTreeChildren()` にフォルダ/ファイルアイコンを追加（「インターフェース/データ構造」
  節「SVG アイコン（`page.html` + `app.js`）」のツリー描画部分）。絵文字ではなく
  `stroke="currentColor"` の SVG（`.icon-btn` と同じ方針）。
- AC2: `#file-search` に検索アイコンを静的 SVG で追加し、角丸を `8px` に統一（同上）。
- AC3: 追加/削除行数の表示・ロジック（`statsSpan()`、`templates/app.js:540-546`）は
  今回変更しない（decisions.md D2）。
- AC4: `#btn-submit-open` を削除し、`#btn-start-review` の 1 個だけが残る（F2 節）。
- AC5: `#btn-start-review` の既存トグル挙動＋ラベル変更（`updatePendingCount()`）。
- AC6: `#review-list` に `state.reviews` を一覧表示（`renderReviewList()`）。
- AC7: `editReview()` → フォームへ反映 → `submitReview()` の編集分岐で保存（F3 節）。
- AC8: `deleteReview()` がエントリを削除し、紐づくコメントの `review_id` を null に戻す。
- AC9: `#btn-submit-discard`/`discardPending()` を削除する。
- AC10: `.file-head` の `position: sticky` ＋ `.file` の `overflow: hidden` 除去（F4 節）。
- AC11: `renderThread()` に折りたたみボタンを追加（全スコープ共通の関数のため一括で効く）。
- AC12: CSS セレクタが `.thread-head` を対象外にする（F5 節）。
- AC13: `#btn-notif` ＋ `#notif-badge`（F6 節）。
- AC14: `templates/app.js:1887` の `banner()` を `notify()` に差し替え、レビューを複数回
  提出しても画面上部に積み上がらない。同じ原理で `:110`（バンドル読み込み成功）も
  `notify()` に差し替える（requirements.md 機能要件 F6 が挙げる例そのもの。「対応不要の
  お知らせ」全般をベルへ、という同じ AC14 の趣旨に含める）。
- AC15: research.md F7 の表で「対応不要」以外に分類した 14 箇所は `banner()` のまま。
- AC16: `toggleNotifPanel()` が開くタイミングで `notifUnread = 0` にする。

## 相互作用の受け入れ基準（design での対応）

- AC-I1: `#submit-panel` は `#btn-start-review` のクリック＋`Escape`（既存の分岐）で開閉。
  `.thread-fold` はクリックでトグル。`#notif-panel` は `#btn-notif` のクリック＋`Escape`で開閉
  （`toggleNotifPanel()` ＋ 既存 `Escape` 分岐への追記）。
- AC-I2: 編集は `editReview()`（読み込み）→ `submitReview()`（保存）/ `cancelEditReview()`
  （キャンセル）。キャンセルは `state.reviews` を書き換えないので元の内容のまま残る。
  削除は `deleteReview()` が確認ダイアログなしで即時反映（既存の `cancelComment()` と同じ操作感）。
- AC-I3: 折りたたみボタン・ベル・編集/削除ボタンはすべて `<button type="button">` で実装し、
  既存の `.icon-btn`/`row-actions` の `button` と同じく Tab 到達＋Enter/Space で操作できる
  （ブラウザ標準の button 挙動に乗るだけで、新しいキー処理を書く必要がない）。
- AC-I4: `.thread-fold` はクリック後もフォーカスは自分自身に残る（F5 節のコード例のとおり、
  `renderThreads()` の再描画後に同じ `thread.id` でボタンを探し直し `focusInPlace()` へ渡す）。
  `#btn-notif` はポップオーバーを開いてもフォーカスはボタン自身に残る
  （`#btn-help-open` と同じ挙動）。
- AC-I5: 新規のボタン・パネルは `j`/`k`/`[`/`]`/`{`/`}` 等の既存キー処理
  （`templates/app.js:2037-2131`）を奪わない。`isTyping()` によるテキスト入力中のガードも
  そのまま効く（新しいテキスト入力欄を増やさないため影響なし）。
