# 調査: レビュー操作性の改善（ツリー見た目・レビュー提出フロー・固定ヘッダー・コメント折りたたみ・通知ベル）

## 調査の問い

- Q1: ファイルヘッダー（`.file-head`）を画面上部に固定表示（sticky）するとき、`.file` の
  既存の `overflow: hidden` はその挙動を壊さないか。
- Q2: 通知ベルのポップオーバー、提出済みレビュー結果の一覧＋編集/削除、コメントスレッドの
  折りたたみ——それぞれに「確立したパターン」はあるか。PJ 内に既存の確立パターンがあれば
  それを優先する（`protocol.md`「2.5」）。
- Q3: 新規アイコン（フォルダ/ファイル/検索/ベル）は、既存の `.icon-btn` の方針
  （絵文字ではなく記号文字）をどう実現すればよいか。
- Q4: 現行の `banner()` 呼び出し（16 箇所）のうち、どれが「対応不要のお知らせ」（decisions.md
  D3）に当たるか。機械的な基準（例: `buttons` 引数の有無）だけで仕分けられるか。
- Q5: 新規の色（通知バッジ等）を足すとき、`tests/test_diff_review.py` の `ThemeCssTest` を
  壊さずに済む方法はあるか。

## 判明した事実

- F1（Q1）: `.file` は `border-radius: 8px;` と `overflow: hidden;` を持つ
  （`templates/style.css:317`）。CSS Overflow の仕様上、`overflow` が `visible` 以外の値
  （`hidden` を含む）を持つ要素は**それ自体が「スクロールコンテナ」を確立し**、
  その子孫の `position: sticky` の基準（sticky containing block）になる。
  `.file` は高さが子要素に合わせて自動決定され実際にはスクロールしない箱だが、
  仕様上はスクロールコンテナとして扱われるため、`.file-head` に `position: sticky; top: 0;`
  を付けても、その「固定される基準」は `#pane-center`（実際にスクロールする祖先。
  `.pane { overflow: auto; }` `templates/style.css:177`）ではなく `.file` 自身になる。
  `.file` 自身の描画位置は `#pane-center` のスクロールに応じて普通に動くだけなので、
  この状態では `.file-head` は見かけ上ほとんど動かない（= 期待する「画面上部に居座る」
  効果が出ない）。**`.file` の `overflow: hidden` を外さない限り、sticky は機能しない。**
- F2（Q1 続き）: `.file` の `overflow: hidden` は、`.file-head`（`templates/style.css:318-327`）の
  上端 2 角と `.file-body` 内の最後の行の下端 2 角を、`.file` 自身の `border-radius: 8px` に
  沿って切り欠くためだけに使われている（角丸クリップ）。`.file-head`/`.file-body` 自体には
  `border-radius` は付いていない。
- F3（Q1 続き）: `.file-body` は既に `overflow-x: auto;`（横スクロール。`templates/style.css:329`）
  を持つ。`overflow` の longhand（`overflow-x`/`overflow-y`）は独立して指定できるため、
  `.file-body` に `overflow-y: hidden;` を追加しても横スクロールは壊れない。かつ
  `.file-body` は `.file-head` の**兄弟**（子ではない）なので、`.file-body` 側で
  スクロールコンテナを確立しても `.file-head` の sticky 基準には影響しない。
- F4（Q2）: PJ 内に、開閉トグルボタン＋ `aria-expanded` ＋隣接領域の表示切替、という
  「確立したパターン」が既に複数箇所で使われている（WAI-ARIA の Disclosure パターン相当）:
  - ファイルの折りたたみ: `toggleFile()`（`templates/app.js:953-965`）。
    ボタンに `aria-expanded`、テキストを ▾/▸ で切替、対象は
    `.file[data-collapsed="true"] .file-body { display: none; }`（`templates/style.css:330`）。
  - ヘルプ一覧: `#btn-help-open` ⇄ `#help`（`templates/page.html:38-39,45`、
    `templates/app.js:2180-2184`）。
  - ペイン開閉: `#btn-pane-left`/`#btn-pane-right`（`templates/ui.js:122-138` の `setPane`）。
  - ツリーのフォルダ開閉: `toggleTreeDir()`（`templates/app.js:743-748`）。
  いずれも新しいライブラリや ARIA パターンを持ち込まず、同じ語彙（ボタン＋
  `aria-expanded`＋隣接要素の `display` 切替）で作れている。
- F5（Q2 続き）: 「入力して確定する/閉じる」フォームも、PJ 内に確立パターンがある:
  コメントの composer（`openComposer()` `templates/app.js:1712-1781`）は、
  textarea・select・「確定」ボタン・「閉じる」ボタンという組み合わせで、
  `Escape` で閉じる／`Ctrl(⌘)+Enter` で確定、というキー操作も揃っている
  （`templates/app.js:1751-1759`）。提出済みレビュー結果の編集フォームは、
  現行の `#submit-panel`（`templates/page.html:72-88`。判定ラジオ＋サマリ
  textarea＋確定ボタン）と全く同じ部品構成を再利用でき、新しいフォーム語彙を
  増やさずに済む。
- F6（Q3）: 既存の `.icon-btn`（`templates/style.css:592-611`）は絵文字ではなく
  幾何学的な記号文字（`⊞` `◐` `◧` `⧉` `⏷` `⏶` `▾` `▸`）を使っている
  （`templates/ui.js:24` のコメント「太陽・月・半月の組は他の多くのアプリで確立した
  idiom」が根拠）。一方、Unicode には「フォルダ」「ファイル」「ベル」を単色・
  幾何学的な記号として明確に表す定番の非絵文字グリフが無い（絵文字版 📁📄🔔 は
  カラーで環境依存のため既存方針から除外される）。
  `templates/rich.js` は SVG を**信頼できない差分コンテンツの表示**にだけ使っており
  （`SAFE_SRC` によるサニタイズ、`templates/rich.js:9,22`）、UI クロム自体には
  SVG を使った前例が無い。ただし `app.js` の `el()`（`templates/app.js:136-151`）は
  `document.createElement` ベースで、`innerHTML` を使わない、という制約は
  `document.createElementNS("http://www.w3.org/2000/svg", tag)` を使ったインライン SVG
  構築（属性を `setAttribute` で1つずつ付ける形）でも守れる——`el()` と同じ思想の
  SVG 版ヘルパーを足せば、既存の「HTML として解釈されない」という約束を崩さない。
- F7（Q4）: `banner()` の呼び出しは `templates/app.js` に 16 箇所ある。分類は下表。
  「対応不要」は成功の確認だけで、押せるボタンも無く、内容を読んだあとに何かする
  必要が無いもの。「対応/注意」はエラー・警告・選択肢（ボタン）を伴うもの。

  | 行 | 内容（要約） | 分類 | 理由 |
  |---|---|---|---|
  | 97 | バンドルを開けなかった（`key: load`） | 対応/注意 | エラー |
  | 110 | バンドルを読み込んだ（`key: load`） | **対応不要** | 成功確認のみ |
  | 258 | 下書きを保存できない（ブラウザ制限） | 対応/注意 | 機能制限の警告 |
  | 347 | `adoptRecord` の `note`（現状どの呼び出しも `null` で未使用） | — | 呼び出しなし |
  | 447 | 記録を読み込めなかった（`key: load`） | 対応/注意 | エラー |
  | 451 | 記録の対象差分が違う（識別不一致） | 対応/注意 | データ整合性の注意喚起 |
  | 865 | パスをコピーできない（手動コピーを促す） | 対応/注意 | 次の行動を要求 |
  | 1877 | 提出するものが無い（提出操作の直後） | 対応/注意 | 直前の操作に対する即時フィードバック |
  | 1887 | **レビューを提出した（screenshot 2 の蓄積元）** | **対応不要** | 成功確認のみ |
  | 1947 | バンドルとして読めない（`key: load`） | 対応/注意 | エラー |
  | 1957 | JSON/バンドルどちらとしても読めない（`key: load`） | 対応/注意 | エラー |
  | 1962 | ファイルを読めなかった（`key: load`） | 対応/注意 | エラー |
  | 2351 | 起動時: 埋め込みバンドルが壊れている | 対応/注意 | エラー |
  | 2369 | 起動時: このブラウザは下書きを保存できない | 対応/注意 | 機能制限の警告（セッション開始時に把握させる） |
  | 2376 | 起動時: 保存されていた下書きを復元した（**ボタン付き**: 「破棄してやり直す」） | 対応/注意 | 選択肢（ボタン）を伴う |
  | 2389 | 起動時: 復元した記録の対象差分が違う | 対応/注意 | データ整合性の注意喚起 |

  **`buttons` 引数が空配列かどうかだけでは機械的に仕分けられない**——258・451・865・1877・
  1962・2351・2369・2389 はいずれも `buttons` が空配列だが「対応不要」ではない
  （エラー・警告・注意喚起のため）。ベルへ振り替えるべきは 110・1887 の 2 箇所だけで、
  残り 14 箇所は画面上部の `banner()` のまま。呼び出し側で明示的に区別する必要がある
  （例: ベル行き専用の別関数 `notify(message, key)` を新設し、対象 2 箇所だけをそれに
  差し替える）。
- F8（Q5）: `ThemeCssTest`（`tests/test_diff_review.py:699-737`）は、`:root` に定義された
  すべての `--d-*` トークンが、2 つの `/* dark-assign:begin */`〜`/* dark-assign:end */`
  ブロック（OS 追従用・手動ダーク用）の両方に**一字一句同じ形で**割り当てられていることを
  機械検査する。**新しい色トークン（例: 通知バッジの色）を追加すると、この 2 ブロックを
  両方とも編集しないとテストが落ちる。** 一方、既存トークン（例: `--danger`/`--accent`）を
  再利用すればこのテストには触れずに済む。

## 影響範囲

- `templates/page.html`: トップバーのボタン構成（F2/F6）、`#submit-panel` の中身（F3）。
- `templates/style.css`: `.file`/`.file-head`/`.file-body` の角丸・overflow（F4）、
  `.tree-item` まわり（F1）、`#file-search`（F1）、新規のベル・バッジ・折りたたみボタンの
  スタイル。**`ThemeCssTest` の対象範囲（`:root` の色トークン）に触れる場合は
  2 ブロック同時更新が必須**（F8）。
- `templates/app.js`: `renderFileTree`/`appendTreeChildren`（F1）、`banner()` 呼び出しの
  一部を新関数へ差し替え（F6）、`updatePendingCount`/`startReview`/`submitReview`/
  `discardPending`/`wire()` のボタン結線（F2/F3）、`renderThread`（F5）。
- `templates/ui.js`: 直接の変更は無い見込み（F4/F6 のポップオーバーを固定パネルではなく
  ボタン起点の浮動要素にすれば `syncTopbarHeight()` に手を入れずに済む。下記「design への
  申し送り」参照）。
- `tests/test_diff_review.py`: 既存テストに `.file` の `overflow`・`banner()` の呼び出し・
  ツリーのアイコン・折りたたみに対する直接のアサーションは無い（grep で未検出）。
  既存テストを壊さずに実装できる見込みが高い。

## 実現性 / リスク

- sticky なファイルヘッダー（F4）は、`.file` の `overflow: hidden` を外し、角丸クリップを
  `.file-head`（上 2 角）と `.file-body`（`overflow-y: hidden` ＋下 2 角の `border-radius`）に
  移すことで、既存の見た目を保ったまま実現できる（F1〜F3 で確認済み。技術的リスクは低い）。
- ポップオーバー系 UI（通知ベルの一覧、レビュー結果の編集フォーム、コメントの折りたたみ）は、
  いずれも PJ 内の既存パターン（Disclosure ボタン＋`aria-expanded`、composer 型フォーム）を
  そのまま転用できるため、新しい UI 語彙やライブラリを持ち込むリスクは低い。
- フォルダ/ファイル/検索/ベルのアイコンは、Unicode の記号文字では参考画像に近い見た目を
  再現できない（定番の非絵文字グリフが無い）。インライン SVG（`createElementNS` ベース、
  `innerHTML` 不使用）を新設する必要があり、これは PJ にとって新しい実装パターンになる
  （ただし「HTML として解釈されない」という既存の約束は保てる）。
- `banner()` の振り分け（F7）は、呼び出し側の意図（対応不要か否か）を機械的に判定できない
  ため、**呼び出し箇所ごとに手で仕分ける**必要がある（上表がその仕分け結果）。

## 実装アンカー

- A1: ツリーのフォルダ/ファイル行描画 — `templates/app.js:703-739`
  `appendTreeChildren()`。フォルダアイコン・ファイルアイコンをここで各 `tree-item` に追加する。
- A2: ファイル検索欄 — `templates/page.html:113-118`（`#file-search` を含む
  `.filelist-tools`）。検索アイコンをここに追加する。
- A3: レビュー操作ボタン（現行3個） — `templates/page.html:31-35`
  （`#btn-start-review` / `#btn-submit-open` / `#btn-export-open`）。1 個に統合する対象。
- A4: 提出パネルの中身 — `templates/page.html:71-88`（`#submit-panel`）。
  提出済みレビュー結果の一覧＋編集/削除 UI をここに追加する。
- A5: レビュー提出ロジック — `templates/app.js:1835-1898`
  （`pendingComments` / `updatePendingCount` / `startReview` / `submitReview` /
  `discardPending`）。`discardPending` と対応するボタンの結線（`templates/app.js:2160`）を
  削除し、`state.reviews` の編集・削除関数を新設する対象。
- A6: `.file`/`.file-head`/`.file-body` の角丸・overflow — `templates/style.css:317-330`。
- A7: コメントスレッドの描画 — `templates/app.js:1493-1529`（`renderThread()`）。
  折りたたみボタンをここ（`thread-head` の `actions`）に追加する。
- A8: 通知（`banner()`）本体 — `templates/app.js:279-300`。ベル行き専用の関数を新設する
  起点（呼び出し側の差し替え対象は上表 F7 の 110・1887 行目）。
- A9: トップバーのボタン列（ベルアイコンの追加先） — `templates/page.html:28-40`（`.actions`）。
- A10: 既存の Disclosure パターン（設計の参考） — `toggleFile()`
  `templates/app.js:953-965`、`setPane()` `templates/ui.js:122-138`。
- A11: 既存の composer パターン（レビュー結果編集フォームの参考） —
  `openComposer()` `templates/app.js:1712-1781`。
- A12: `ThemeCssTest` — `tests/test_diff_review.py:699-737`（新規色トークンを足す場合に
  必ず通す対象。**未特定**: 通知バッジに新規トークンが要るか、既存トークン
  （`--danger`/`--accent` 等）の再利用で足りるかは design で決める）。

## 実装時の注意

- `.file` から `overflow: hidden` を外す変更は、**角丸の見た目を保つための代替**
  （`.file-head` に `border-radius: 8px 8px 0 0`、`.file-body` に
  `overflow-y: hidden; border-radius: 0 0 8px 8px;` を足す）とセットでないと、
  角の四隅がわずかに欠けた見た目になる（F2）。
- 通知ベルの一覧・レビュー結果の編集フォームを、既存の `#help`/`#submit-panel` と同じ
  「トップバー直下に押し出す固定パネル」にすると、`UI.syncTopbarHeight()`
  （`templates/ui.js:197-209`）の対象 id リスト（`banners`/`help`/`submit-panel`/
  `export-panel`）にも新しい id を足す必要が生じ、レイアウトのがたつき（他パネルの
  開閉で `.shell` の高さが変わる）の対象も増える。**ボタン起点の浮動ポップオーバー**
  （`position: absolute`、ボタンの下に重ねて表示）にすれば、この対象リストに触れず
  レイアウトも動かないため、変更範囲を小さくできる（design で採否を決める）。
- `discardPending()`（`templates/app.js:1890-1898`）を削除する際、対応するボタンの
  結線（`templates/app.js:2160`: `document.getElementById("btn-submit-discard")...`）
  も一緒に外さないと、存在しない要素への参照で起動時に例外が出る
  （`wire()` は他のボタンも `if (submitOpen) {...}` のように存在チェックしてから
  結線しているので、同じ流儀に揃える）。
- `state.reviews` のエントリを削除したときに `review_id` を null に戻す処理
  （F3・要件 AC8）は、`cancelComment()`（`templates/app.js:1565-1572`）とは別の新規関数に
  なる（`cancelComment` は「未提出のコメント」だけを対象にしており、
  「提出済みのコメントを未提出へ戻す」ケースは扱っていない）。

## design への申し送り

- ベル通知・提出済みレビュー結果編集の UI は、固定パネル方式ではなく浮動ポップオーバー
  方式を推奨する（上記「実装時の注意」）。design で最終的な採否と、開閉のキーボード
  操作（Tab 到達・Escape で閉じる等、AC-I1/AC-I3 を満たす具体的な実装）を確定する。
- フォルダ/ファイル/検索/ベルのアイコンはインライン SVG（`createElementNS` ベース）で
  実装する方針を推奨する。具体的な形状（viewBox・path データ）は design で決める。
- `banner()` の呼び出しのうち、ベルへ振り替えるのは `templates/app.js:110` と `:1887` の
  2 箇所のみ（F7 の表）。それ以外の 14 箇所は現状どおり画面上部に残す。実装方法
  （新関数 `notify()` を新設するか、`banner()` に第4引数で振り分けフラグを足すか）は
  design で決める。
- 通知バッジの色は、新規トークンを増やさず既存の `--danger` または `--accent` を
  再利用することを推奨する（`ThemeCssTest` を触らずに済む。A12）。新規トークンが
  本当に必要と design で判断した場合のみ、2 つの dark-assign ブロックを揃えて更新する。
