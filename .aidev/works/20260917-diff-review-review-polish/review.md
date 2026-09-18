# レビュー記録

## タスク点検ログ（coding 工程内・「3.3」(b)）

- [should][conv:-] `templates/app.js`（`SVG_NS`） SVG 名前空間 URI を2文字列に分割して
  `test_contains_no_external_reference` の部分文字列検査を回避していたのは、ソース側の
  難読化であって本質的な対応ではない / 対応: 修正済（T1・ラウンド1）。`SVG_NS` を通常の
  1リテラルへ戻し、`tests/test_diff_review.py` 側に w3.org 名前空間 URI を許可する狭い
  例外（正規表現でスクラブしてから検査）を追加した。
- [should][conv:-] `templates/page.html`／`templates/app.js`（T4） 提示された diff の範囲
  だけでは `#btn-submit-do`/`#btn-submit-close` が通常モードの page.html に実在するか
  確認できない、という指摘 / 対応: 確認済（修正不要）。`grep` で実ファイルを直読し、
  両ボタンが T6 実施後も変わらず存在することを確認した（T6 で消したのは
  `#btn-submit-discard` のみ）。
- [should][conv:-] `templates/page.html`/`templates/app.js`（T5） `#review-list` が
  `#submit-panel`（rw ブロック）の中にしかなく、readonly では `renderReviewList()` が
  host 不在で早期リターンするため、`reviewEntry()` に足した
  `if (readonly) { return node; }` が実行されない死んだ分岐になっていた / 対応: 修正済
  （T5・ラウンド1）。死んだ分岐を削除し、理由をコメントで残した（readonly での提出済み
  レビュー結果の閲覧対応は、今回の要件の対象外として scope 外のまま——将来必要なら
  別途 backlog 化する）。
- [nit][conv:-] `templates/app.js`（T5） `submitReview()` の編集分岐で編集対象が
  削除済み等により見つからない場合、無言でフォームがリセットされていた / 対応: 修正済
  （T5・ラウンド1）。`banner()` で一言伝えるようにした。
- [nit][conv:-] `templates/style.css`（T7） `.file-head`/`.file-body` の入れ子
  `border-radius` が `.file` の `border-width`（1px）を厳密には差し引いていない（理論上
  1px 未満の誤差） / 対応: 許容。border=1px・radius=8px のスケールでは視認できないレベル
  のため、複雑さに見合わないと判断し据え置いた。
- [should][conv:-] `templates/style.css`（T9） `.notif-badge` が `color: #fff` 固定で、
  ダークテーマで `--danger` が明るいサーモンピンクに切り替わるとコントラストが崩れる
  / 対応: 修正済（T9・ラウンド1）。`color: var(--bg)`（明暗どちらのテーマでも `--danger`
  と輝度が逆になるよう設計済みの既存トークン）に差し替えた。
- [nit][conv:-] `templates/app.js`（T9） `notifUnread` が `NOTIF_LIMIT`（保持上限50件）と
  連動しておらず、パネルを一度も開かないまま51件以上通知が発生すると、バッジの数字と
  実際に一覧へ残る件数がずれる / 対応: 許容。極めて稀な状況であり、対応の複雑さに
  見合わないと判断し据え置いた。
- [nit][conv:-] `templates/app.js`（T9） `notify()` が `#notif-panel` の開閉状態を見ずに
  常に `notifUnread` を加算しており、パネルを開いたまま新着があると一覧には見えているのに
  バッジの数字だけ増えたままになりうる / 対応: 修正済（T9・ラウンド1）。パネルが開いている
  間に届いた通知は未読に数えないよう分岐を追加した。

（T2・T3・T6・T8・T10・T11 は `CHECK: ok` / `FINDINGS: 0`。指摘なし。）

## タスクをまたぐ不変条件の点検（`cross`・「3.3」(b)）

- [nit][conv:-] `templates/style.css` の `.tree-item[data-viewed="true"] .tree-name`
  ルールが、単独の宣言（旧585行目）と「フラット・ツリー共通」ルール（`#filelist
  a[data-viewed="true"] .path-text, .tree-item[data-viewed="true"] .tree-name`）の
  2箇所に全く同一の内容で重複定義されていた / 対応: 修正済（cross・ラウンド1）。
  `git diff` で確認したところ**この重複は本 work の変更に起因せず、過去の work から
  持ち越された既存の重複**だったが、修正が1行削除で完結し既存テストにも影響しないため、
  触れたついでに直した。単独ルールを削除し、共通ルール1本に統合した。

（他の観点——`#submit-panel` を閉じる経路の一貫性・`readonly` ガードの使い分け・
新規アイコンの属性・`ReadonlyTest.WRITE_UI` との整合・新規色トークンの不在——はいずれも
整合していることを確認済み。）

## ラウンド 1（review 工程・要件適合/価値適合の独立点検）

- [must][conv:-] スレッドを折りたたむと重大度（severity）バッジが一緒に消え、AC12
  「位置・解決状態・重大度などのヘッダー情報は見えたままである」を満たさない。
  `.thread[data-collapsed="true"] > .comment { display: none; }`（style.css）は `.thread`
  の直接の子である `.comment` 全体を隠すが、重大度バッジは `.thread-head` ではなく
  `renderComment()` が作る `.comment > .who` の中にしかない。design.md F5 節の「位置・
  解決状態・重大度は `.thread-head` の中に既にある」という記述は事実誤認だった。
  既存の `threadSeverity(thread)`（コメント一覧のフィルタで使用中）をそのまま
  `.thread-head` 側の表示に転用できる。 / 対応: 修正済（coding 再開・ラウンド1）。
  `renderThread()` の `.thread-head` に `threadSeverity(thread)` から重大度バッジを
  追加した。折りたたんでもバッジは `.thread-head` 側に残るため消えない。headless DOM
  検証で「折りたたむ前後どちらも `.thread-head .badge.sev-must` が存在する」ことを確認。
- [should][conv:-] 提出済みレビュー結果の編集中（`editingReviewId` が非 null）に、
  `#review-list` の一覧側にはどのエントリを編集中か分かる視覚的な印が無い。一覧が複数件
  あり、スクロールで編集対象のエントリが見えなくなると、US3 が意図する「いま自分が
  何を編集しているか一目で分かる」体験を取りこぼす。 / 対応: 修正済（coding 再開・
  ラウンド1）。`reviewEntry()` に `data-editing`/「編集中」表示を追加し、
  `editReview()`/`cancelEditReview()` で一覧を再描画して同期させた。headless DOM 検証で
  一覧2件のうち編集中の1件だけに印が付き、保存/キャンセルどちらでも印が消えることを確認。

（他の観点——ツリーアイコン・単一ボタン化・sticky ヘッダー・通知ベルの対象範囲選定——は
requirements.md / design.md の記述と実装が整合していることを確認済み。）

## ラウンド 2（review 工程・ラウンド1の修正の検証）

- [should][conv:-] ラウンド1の must 対応（`.thread-head` への重大度バッジ追加）が、
  展開時（折りたたんでいない通常時）に `.comment > .who` 側の既存バッジと二重表示に
  なっていた。`threadSeverity(thread)` は常に「先頭コメントの重大度」を返すため、
  `.thread-head` に出すバッジと、先頭コメント自身の `.who` に出るバッジが同じ内容で
  重複していた。 / 対応: 修正済（coding 再開・ラウンド2）。`renderComment()` 側で、
  先頭コメント（`comment === thread.comments[0]`）のときだけ `.who` の重大度バッジを
  省くようにした（返信が個別に持つ重大度は従来どおり `.who` に表示される）。headless
  DOM 検証で、展開時に先頭コメント側の重複が無いこと、かつ返信自身の重大度は
  抑制されず表示されることの両方を確認した。
- ラウンド1の2件（AC12 の重大度消失・編集中インジケータ欠如）は解消を再確認。
  新たな回帰は見当たらない（`ReadonlyTest.WRITE_UI` との整合も含め確認済み）。

（他の観点の広い再点検は、ラウンド1で確認済みの範囲に留め、今回の修正が触れていない
箇所——ツリーアイコン・sticky・通知ベル等——は対象外とした。）

## ラウンド 3（review 工程・D10 の修正の最終確認）

指摘なし。D10 の修正（`renderComment()` で先頭コメントの重大度バッジを抑制）が
`.thread[data-collapsed]`/`.thread-head`/`renderCommentList()`/`clItem()` 等、重大度を
扱う他の箇所（`grep -n '"sev-'`で全数確認: `templates/app.js` の3箇所——`.thread-head`・
`.comment > .who`・コメント一覧の `clItem()`——のうち影響があるのは前2者のみで、
`clItem()` は別 DOM 部分木のため無関係）と矛盾しないことを diff の通読で確認した。
`closeSubmitPanel()`/`editReview()`/`cancelEditReview()`/`deleteReview()` のフォーカス・
再描画の流れ（`editReview()` が `renderReviewList()` を呼ぶ前に `review-body` へ
フォーカスしているため、一覧の再構築でフォーカスが失われない等）も合わせて確認した。
`aidev coverage --strict` は gaps=0 のまま（tasks 承認時から被覆の乖離なし）。

**この work のレビュー指摘は最終的に must 1件・should 2件・nit 0件**
（ラウンド1: must 1・should 1／ラウンド2: should 1／ラウンド3: 指摘なし。いずれも
coding で修正し、修正後の再検証まで完了している）。

## PR レビュー（人間）（deliver 後・PR #26 マージ後）

- [should][conv:-] `templates/style.css`（`.pane-center`） sticky なファイルヘッダーと
  トップバーの間に隙間が見える / 対応: 修正済。`.pane-center` の `padding-top` を
  `0` にし、その分の余白を `#overall` の `margin-top: 16px` で確保するようにした
  （padding は sticky の基準位置に含まれるが margin は含まれないため、固定時に隙間が
  出なくなる）。 / src: チャットでの指摘（GitHub の PR コメントではない。PR #26 は
  マージ・ブランチ削除済みのため、この修正は新しい PR で提出する）。
- [should][conv:-] `templates/style.css`（`button`/`.icon-btn`） 通知ベルボタンが他の
  トップバーのボタンより高く、既存のボタン同士（アイコンボタン ≒28px・通常ボタン
  ≒32.39px）も揃っていなかった / 対応: 修正済。`.topbar .actions button` に
  `height: 28px; display: inline-flex; align-items: center; justify-content: center;`
  を追加し、line-height ベースの高さ計算（本文の line-height: 1.6 の継承や、SVG を
  含むボタンでの baseline 計算のずれ）に頼らず、トップバーのボタン全てを一律 28px に
  揃えた。トップバー外の小さいボタン（行コメントの「+」等）は対象外のまま。
  / src: チャットでの指摘（同上）。

いずれも headless DOM 検証（jsdom）に確認項目を追加し、`getComputedStyle()` で
`#pane-center` の `padding-top: 0px`／`#overall` の `margin-top: 16px`／トップバー7個の
ボタンがすべて `height: 28px` になっていることを確認した（計9件追加、60件すべて pass）。

## PR レビュー（人間）（PR #27 マージ後、追加の指摘）

- [should][conv:-] `templates/style.css`（`button`） トップバー以外にも、ファイルの
  操作列（「ファイルにコメント」等）やコメント入力欄（「コメントする」「閉じる」等）で
  ボタンの高さが揃っていない箇所が残っていた / 対応: 修正済。前回はトップバーだけに
  絞った `.topbar .actions button` という個別ルールで対処していたが、根本原因（素の
  `button` が `body` の `line-height: 1.6` を継承しておよそ32px、`.icon-btn` は独自の
  `line-height: 1.2` でおよそ28px、という不一致）はサイト全体の `button` に共通していた
  ため、**基底の `button {}` に `height: 28px` と flex 中央揃えを移し、サイト全体の
  既定にした**。個別の `.topbar .actions button` ルールは削除（冗長になったため）。
  `<select>`（コメントの重大度選択・コメント一覧の絞り込み）も同じ 28px に揃えた
  （ボタンと同じ行に並ぶため）。
  一方で、以下の3箇所は意図的にこの既定から外した（`height: auto` を明示）:
  - `.row .comment-open` / `.row.split .cell .comment-open`（差分の各行に出る「+」。
    12px フォントの行に収める必要がある）
  - `.expander button`（隙間展開の ↑/↓/すべて表示。同じ 12px の文脈）
  - `.cl-item`（コメント一覧の1件。位置・タグ・本文を複数行で持つカード）
  / src: チャットでの指摘（PR #27 マージ後）。

headless DOM 検証（jsdom）で、ファイル操作列・コメント入力欄・スレッド見出し
（解決にする/折りたたみ）・提出パネル・提出済みレビュー結果の編集/削除ボタンが
すべて 28px に揃っていること、かつ上記3箇所は従来どおり `auto`（コンパクト）のままで
あることを `getComputedStyle()` で確認した（62件 pass・1件は環境依存でスキップ:
このスクリプトが読む差分が1ファイルのみのときはツリーのフォルダ行自体が出ないため）。

### この対応自体の独立点検（review 工程内）

- [should][conv:-] `height: 28px` を固定していたため、アプリ内で最も長いラベルの
  ボタン（バナーの「下書きを破棄してやり直す」12文字。他のボタンは長くても数文字）が
  狭い幅で2行に折り返した場合、文字がボタンの枠からはみ出す懸念があった
  / 対応: 修正済。基底の `button {}` を `height: 28px` から **`min-height: 28px`** に
  変更した（短いラベルは従来どおり 28px に揃い、万一2行になっても高さが追従して
  欠けなくなる）。3つの例外セレクタ（`.row .comment-open` 等）は `height: auto` だけ
  では基底の `min-height: 28px` を打ち消せないため、`min-height: 0` も明示的に追加した。
- [nit][conv:-] `.thread-head` の解決ボタン（「解決にする」/「未解決に戻す」）は、
  同じ 12px フォントの密な文脈にある `.row .comment-open`/`.expander button` と違い
  例外に含めていない / 対応: 許容（コード変更なし）。`.thread-fold`（`.icon-btn`）が
  既に約28px相当の高さを持ち、`.thread-head` の行の高さは元々そこで決まっていたため、
  解決ボタンを28pxに揃えても行全体の高さは増えない（実害なし）。意図的な据え置きとして
  ここに記録する。

上記の修正を反映した最終版で headless DOM 検証を再実行し、64件すべて pass（環境依存の
スキップも今回は該当差分が複数ファイルだったため発生せず）。

## PR レビュー（人間）（PR #28 マージ後、追加の指摘）

- [must][conv:-] `templates/style.css`（`button`） PR #28 で `height: 28px` を
  `min-height: 28px` に変えたが、実ブラウザではトップバーのボタンが軒並み元の
  32.39px に戻って見える / 対応: 修正済（decisions.md D13）。原因は `min-height` が
  「下限」であって、素の `button` の content 由来の自然な高さ（`line-height: 1.6` 継承で
  32.4px）が既にその下限を超えていたため、`min-height: 28px` が全く効いていなかった。
  基底の `button {}` に `line-height: 1.2;`（`font: inherit` の直後）を追加し、
  content の自然な高さを 28px 未満に収めることで `min-height` の下限が実際に効くように
  した。jsdom は「指定値」しか読めず「実際に描画される高さ」を検証できないため、
  この指摘は jsdom では検出できず、**playwright-core を使った実ブラウザでの
  `boundingBox()` 実測で初めて発見・確認した**（decisions.md D13 参照）。

トップバー7個・ファイル操作列・composer・submit-panel・3つの例外箇所すべてで、実際の
Chromium レンダリングにより高さを実測して確認した（jsdom による指定値の確認だけでなく、
使用値レベルでの検証を初めて行った）。

## PR レビュー（人間）（PR #29 マージ後、5件の追加指摘）

- [must][conv:-] ツリー表示でフォルダの行が出ない（全ファイルが1つの共通フォルダに
  収まる場合に顕著） / 対応: 修正済（decisions.md D14）。`buildTree()` がルート自身まで
  畳んでいたのが原因。本 work の T2 が触れた既存コード（D10 由来）に元々あった不具合。
- [should][conv:-] コメント一覧パネルを閉じても「指摘はまだありません」が見える /
  対応: 修正済（decisions.md D14）。`#commentlist` の ID セレクタが、閉じたときの
  `display: none`（クラスセレクタ）を ID の強さで上書きしていた。
- [should][conv:-] 代わりにパネルの開閉ボタンへ未解決件数・未レビューのファイル数を
  バッジ表示してほしい（展開時は消す） / 対応: 実装済（decisions.md D14）。
- [should][conv:-] ドラッグでのリサイズが、閉じた状態（40px）より小さくできてしまう /
  対応: 修正済（decisions.md D14）。`ui.js` の `MIN_W` を `0` → `40` に変更。
- [should][conv:-] 確認済みチェック・解決済みチェックで、それぞれファイル本文/
  コメントスレッドを自動的に折りたたんでほしい / 対応: 実装済（decisions.md D14）。
  既存の折りたたみの仕組み（`toggleFile()`/`threadCollapsed`）を再利用。

D13 の教訓（jsdom は使用値を検証できない）を踏まえ、5件すべてを playwright-core による
実ブラウザ操作（click/fill）とスクリーンショットで確認した（decisions.md D14 参照）。
既存の headless DOM 検証（jsdom, run.js）・`python3 -m unittest discover`（126件）も
green。readonly ビルドでも動作を確認済み。

## ラウンド（review 工程・独立点検）

- [should][conv:-] D14 のバッジ更新が `#btn-pane-left`/`#btn-pane-right` の `click`
  イベントにしか結線されておらず、キーボードショートカット（`{`/`}`/`[`/`]`）・
  セパレータへの Enter/Space・ドラッグ開始時の自動オープンではバッジが更新されない
  / 対応: 修正済（decisions.md D15）。開閉状態を実際に書き換える `setPane()`
  （`ui.js`）にフック機構を追加し、経路によらず確実に更新されるようにした。
  playwright-core で4経路（`}`/`]`/`{`/セパレータ Enter）すべてを実測して確認した。

## PR レビュー（人間）（PR #30 マージ後、2件の追加指摘）

- [should][conv:-] ファイル一覧・コメント一覧が畳まれた状態でセパレータを D&D すると
  勝手に展開状態になり、その分だけマウス位置と罫線の位置がずれる / 対応: 修正済
  （decisions.md D16）。`wireSeparator()` の `pointerdown` から「畳んでいたら先に開く」
  処理を削除し、畳んだ実測幅（40px）をそのままドラッグの起点にした。
- [should][conv:-] D&D でサイズを縮小しても、開閉ボタンで畳んだ場合と違って一覧の
  中身が隠されずに見えたままになる。一定位置より縮めたら非展開状態にしてほしい /
  対応: 修正済（decisions.md D16）。新設 `applyWidth()` が、クランプ後の幅が
  `MIN_W`（＝畳んだときのストリップ幅と同じ 40px）以下になった時点で
  `setPane(..., false, ...)` を呼び、開閉ボタンでの折りたたみと同じ表示（中身を隠す）
  に倒す。

playwright-core による実ブラウザでのドラッグ操作（`page.mouse.move/down/up` で実際に
セパレータを動かす）で19アサーションすべて確認した（decisions.md D16 参照）。
既存の `python3 -m unittest`（140件）・`aidev smoke` も green。

## ラウンド（review 工程・独立点検、D16 に対して）

- [should][conv:-] `applyWidth` はドラッグ（`wireSeparator` の pointerdown/move/up）
  からしか呼ばれておらず、セパレータへの `Home` キー操作は従来どおり
  `setWidth(which, MIN_W, true)` を直接呼んで「開いたまま幅だけ40pxにする」壊れた
  状態を保存できた。この状態を保存したままリロードすると、`init()` が保存された
  `pane-left: open` をそのまま復元するため、D16 で塞いだはずの「開いたまま40pxに
  潰れて中身が見える」状態がキーボード操作＋リロード経由で再現できる / 対応: 修正済
  （decisions.md D17）。`keydown` ハンドラの4キーすべてを `applyWidth` 経由に統一し、
  `init()` も「幅が MIN_W 以下なら開閉状態によらず畳む」という同じ不変条件で
  正規化してから復元するよう変更した。
- [should][conv:-] `applyWidth` の畳む分岐は意図的に `setWidth` を呼ばない
  （呼ぶと再度開いたときに戻る幅を上書きしてしまうため）ため、`aria-valuenow` が
  畳む直前の値のまま更新されず、支援技術には畳む前の幅が残ったまま見える / 対応:
  修正済（decisions.md D17）。CSS 変数はそのままに `aria-valuenow` だけを直接
  `MIN_W` へ更新するようにした。

playwright-core で追加7アサーション（`Home` キーでの畳み・壊れた保存状態からの
リロード正規化・`aria-valuenow` の実測）を含む計25アサーション、すべて green。
`python3 -m unittest`（140件）も green のまま。

## ユーザー要望（下書き自動復元の確認バナー撤去・初期化ボタン新設）

- [nit][conv:-] `#btn-reset-draft`（`templates/page.html`） `title`/`aria-label` が
  可視テキスト「下書きを初期化」と重複しており、隣接する `#btn-start-review`/
  `#btn-export-open`（どちらも `title`/`aria-label` 無し）と流儀が揃っていない /
  対応: 修正済（decisions.md D18）。可視テキストと完全に重複する `aria-label` は削除し、
  可視テキストに無い説明を持つ `title` は残した。

独立点検（別コンテキストの subagent）で must/should の指摘は無し。`embeddedReview` の
モジュール変数への昇格・`resetDraft()` の `dropSaved`/`drafts`/`state` の扱い・
readonly ビルドからの除外・`viewedFiles` の独立性が保たれていること、他のバナー
（保存不可・バンドル破損・checkIdentity）に影響していないことを確認済み
（decisions.md D18 参照）。`python3 -m unittest`（140件）も green のまま。

## ユーザー要望（キー操作説明のフローティング化・通知ベルの空状態修正）

独立点検（別コンテキストの subagent）で must/should/nit いずれの指摘も無し。
`setHelpOpen()` が5つの開閉経路（ボタン・`?`・Escape・×・backdrop）を正しく一本化して
いること、`#help-backdrop`/`#help` が兄弟要素で backdrop クリックが `#help` 自身の
クリックに誤って反応しないこと、`#progress-track`（z-index:200）が `#help` 本体には
重ならず backdrop の最上部6px帯にのみ影響すること（この回のテスト中に自分たちで
見つけて座標側を直した問題であり実装の不具合ではないことの再確認）、readonly
ビルドで `#help-backdrop`/`#btn-help-close` が rw ブロック外にあり無条件に機能する
こと、`renderNotifList()` を `renderAll()` に足したことが `notifUnread`/バッジや
ドラッグ＆ドロップ読み込み時の再描画と衝突しないこと、を確認済み（decisions.md D19
参照）。`python3 -m unittest`（140件）も green のまま。

## ユーザー要望（split表示の変更前/変更後見出しが常に2行分を消費する不具合）

独立点検（別コンテキストの subagent）で must/should/nit いずれの指摘も無し。
`.slots` が `.threads`/`.composer-slot` を常に両方持つため「両方とも無い」ケースは
到達不能であること、`labelled=false`（見出し無し）の行でも同じ可視性判定が正しく
働くこと、split 以外（unified・ファイル単位・overall・スレッド内の返信）の
composer-slot では `slot.closest(".slots")` が `null` を返し安全に早期returnすること、
`renderFiles()`（`.slots` を生成）が全ての呼び出し経路で必ず `renderThreads()`
（可視性を同期）より先に実行されること、削除された `:empty` ルールに依存する他の
セレクタが無いこと、解決済み（未削除）のスレッドは中身として残るので `.slots` が
可視のままなのは意図どおりであること、を確認済み（decisions.md D20 参照）。
`python3 -m unittest`（140件）も green のまま。

## ユーザー要望（レビュー結果の入力画面のフローティング化）

独立点検（別コンテキストの subagent）で must/should/nit いずれの指摘も無し。新設した
`#submit-panel` 専用の Escape listener が `event.preventDefault()` を呼ぶことで、
既存の `onKeyDown()` 冒頭の `defaultPrevented` ガード（別の目的で既に存在していた
仕組み）により、グローバルの Escape ハンドラ側の `closeSubmitPanel()` 呼び出しと
二重発火しないこと（`stopPropagation()` を使わなかったのは意図的に正しい選択で
あったこと）、`editReview()` から開いた場合でも新しい全ての閉じる経路
（×・backdrop・下部「閉じる」・Escape・`"r"`）が `closeSubmitPanel()` を経由して
`cancelEditReview()` を正しく呼ぶこと、`#btn-submit-close-x`/`#submit-backdrop` が
`#btn-start-review` とは別の rw ブロックに属するが常に一緒に着脱される（同じ
`readonly` フラグで一律に処理されるため）ので無条件の `getElementById` が安全なこと、
`ui.js` から `"submit-panel"` を外したことに他の依存が無いこと、を確認済み
（decisions.md D21 参照）。×ボタンと下部「閉じる」ボタンの両方を残した設計判断は
妥当な UX 判断であり欠陥ではない、との言及もあった。`python3 -m unittest`
（140件）も green のまま。

## ユーザー要望（ボタンラベル固定化・JSON書き出しのフローティング化・拡幅）

独立点検（別コンテキストの subagent）で must/should/nit いずれの指摘も無し。
`reviewStarted` が app.js のどこにも参照が残っていないこと（`node --check` でも
確認）、`pendingComments()` は他で引き続き使われておりデッドコードになっていない
こと、`#btn-start-review` の `aria-expanded` が `setSubmitOpen()` という単一の
経由点を通じて全ての開閉経路（`startReview`/`editReview`/`"r"`キー/
`closeSubmitPanel` とその全呼び出し元）で正しく同期すること、`#export-panel` も
同様に `setExportOpen()` が全ての旧 `showPanel("export-panel", ...)` 呼び出し箇所
（`openExport`・グローバル Escape 分岐・新設の×/backdrop/閉じる）を置き換えている
こと、新設の `#export-panel` 専用 Escape listener が `#submit-panel` と同じ
`preventDefault`+`defaultPrevented` ガードの仕組みで安全に二重発火しないこと、
`.modal-lg`（800px）が既存の `width: calc(100vw - 32px)` により狭い画面でも
はみ出さないこと、`WRITE_UI` タプルの更新が新設要素を正しくカバーしていること、
を確認済み（decisions.md D22 参照）。`python3 -m unittest`（140件）も green の
まま。
