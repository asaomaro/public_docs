# 判断の記録: 20260917-diff-review-review-polish

> 1 決定 = 1 エントリ・追記式（`protocol.md`「8.1」）。既存エントリは書き直さない。
> この work は `mode: autonomous`。承認者が工程内にいないので、方針と成果物は
> 同じ approve ゲートで一度に受ける（`protocol-autonomous.md`「方針の事前承認」）。

## D1: 実行プロファイルは full、実行モードは autonomous

- **背景**: ユーザーから 5 件の追加指摘（ツリー表示の見た目、レビュー操作ボタンの整理＋
  提出済みレビュー結果の一覧編集削除、ファイルヘッダー固定、コメントの折りたたみ、
  通知のベルアイコン化）。screenshot 2 枚（ツリー表示の参考画像、通知バナーが
  積み上がっている現状のスクリーンショット）が添付された。
- **決定**: `aidev new diff-review-review-polish --mode autonomous`（profile full）。
- **理由・代替案**: 5 件のうち複数（レビュー提出フローの再設計＝ボタン統合＋提出済み
  レビュー結果の編集/削除 UI 新設、ファイルヘッダーの sticky 化に伴う `.file` の
  `overflow: hidden` の見直し）は、既存の中核的な振る舞い・DOM 構造を変える設計判断を
  要し、「振る舞いを変えない/小規模」という light の条件を満たさない。full を選び、
  上流 4 文書の独立点検を通す。過去の同種 work（nav-polish 等）もすべて
  `mode: autonomous / profile: full` で一貫しており、その慣行にも従う。
- **影響**: `requirements`/`design`/`tasks` それぞれで `doccheck`（同一セッション内点検）を実施。

## D2: ツリー行の追加/削除行数表示は維持し、見た目（アイコン・検索欄）だけ参考画像に寄せる

- **背景**: 参考画像（VS Code 風の SCM ツリー）は、ファイル行の右端に Git ステータスの
  色付きアイコン（緑=追加・オレンジ=変更 等）を出し、行数は表示していない。一方
  diff-review-html の現行ツリーは行の右端に `+N -N`（追加/削除行数）を出しており、
  これはレビュー時に「この変更がどれだけ大きいか」を一目で把握するための既存の実用情報。
- **決定**: `AskUserQuestion` でユーザーに確認し、「行数表示は残し、見た目だけ寄せる」を
  選択（Recommended 案のまま採用）。ステータスアイコン（A/M/D 等）への置き換え・併記は
  今回のスコープに含めない。
- **理由・代替案**: 置き換え案は画像に最も忠実だが、レビュー上有用な行数情報を失う。
  併記案は情報量最大だが行が詰まる。行数を維持しつつ、フォルダ/ファイルアイコン・
  検索欄の見た目（角丸・虫眼鏡アイコン）だけを画像に近づける案が、既存機能を損なわず
  視覚的な質感の要望にも応えられる。
- **影響**: `templates/ui.js` の `statsSpan()`／ツリー描画（`appendTreeChildren` 等）は
  行数表示のロジックを変えず、アイコンの追加のみを行う設計にする（design 工程で確定）。

## D3: 通知バナーの振り分けは「対応不要のお知らせ」系のみベルへ

- **背景**: 現状の `banner()` は、ボタンを持たない通知（例: レビュー提出成功の確認、
  バンドル読み込み成功）が `key` なしで呼ばれると `#banners` に無期限に積み上がり、
  消す手段がない（screenshot 2 で実測）。一方、ボタンを伴うバナー（下書き復元の選択、
  エラーへの対応）は同一 `key` での置き換えや明示的な操作で解消できる。
- **決定**: `AskUserQuestion` でユーザーに確認し、「対応不要のお知らせ系をすべてベルへ」を
  選択（Recommended 案のまま採用）。エラー・選択を要するバナーは現状どおり画面上部に残す。
- **理由・代替案**: 「提出通知だけ」に絞る案は対象が狭く、読み込み成功などの同種の
  蓄積バナーが今後も画面上部に残り続ける。「全種類をベルへ」案はエラーの即時性を損なう
  （エラーは見逃されると原因究明が遅れる）。対応要否で線引きする案が、今回の課題
  （消せない・蓄積する）を過不足なく解消する。
- **影響**: どのバナー呼び出しが「対応不要」に該当するかの具体的な仕分け
  （ボタン引数の有無で機械的に判定できるか等）は design 工程で確定する。

## D4: requirements 承認後、design の前に research（任意工程）を挟む

- **背景**: requirements の独立点検（`doccheck`）は 2 件の should/nit（AC1/AC2 の表現漏れ）
  のみで、いずれもその場で反映済み。一方 `protocol.md`「4.5」の research 推奨条件のうち
  「利用者が操作する部品を作る（ポップオーバー・ピッカー・一覧・ダイアログ等）」に該当する
  新規部品が複数ある（通知ベルのポップオーバー、提出済みレビュー結果の編集/削除つき一覧、
  スレッドの折りたたみ）。加えて、ファイルヘッダーの sticky 化は `.file { overflow: hidden }`
  との相互作用が未検証（sticky の効き方が `.file` 単位か `#pane-center` 単位かで挙動が変わりうる）。
- **決定**: `mode: autonomous` のため「4.5」に従い**自律的に research を挟むと決定**する。
  直前の同種 work（`20260916-diff-review-ux-polish` 以降、UI 部品を伴う work はいずれも
  research を経由している）とも一貫させる。
- **理由・代替案**: research を省いて design にそのまま進む案もあったが、確立したパターンの
  調査を怠ると、通知ポップオーバーやコラプシブルなリストのフォーカス管理・aria 属性の
  既存の確立パターンから外れた実装になりやすく、review での差し戻しコストの方が高い。
- **影響**: `aidev event research start` を記録し、`aidev-15-research` の手順で
  sticky 実装方式・ポップオーバー/折りたたみの確立パターンを調査する。

## D5: design の独立点検は上限（2 ラウンド）まで実施し、以降は深追いしない

- **背景**: `aidev doccheck start design` をラウンド1・2ともに実施し、
  ラウンド1で5件（must 2・should 2・nit 1）、ラウンド2で8件（must 3・should 3・nit 2）の
  内部一貫性指摘を受けた。いずれもその場で `design.md` に反映済み（矛盾の解消・未定義関数
  `renderNotifList()` の追加・AC 対応の補完・出所の明記・文言の明確化）。
  `maxDocCheckRounds`（既定 2）に達したため、3 回目は実施しない
  （`protocol-check.md`「上限で止まったら深追いしない」）。
- **決定**: ラウンド2の指摘を反映した版で design を承認し、tasks 工程へ進む。
  反映後の再検証（3 回目相当）は行わない。
- **理由・代替案**: `aidev escalate`／`aidev limits set` で上限を上げる案もあったが、
  2 ラウンドとも「文書内の記述同士の食い違い」という同種の指摘（新機構を書いた箇所と
  それを参照する箇所がずれる）であり、性質上 review 工程（実装との突き合わせ）で
  拾える／拾うべき粒度に近づいている。上限を機械的に上げるより、残った疑問を
  coding/review に委ねる方が protocol の想定に沿う。
- **影響**: tasks/coding で `design.md` に従って実装したのち、review 工程で
  `design.md` と実装の乖離が無いかを改めて確認する。

## D6: パネルを閉じる経路を `closeSubmitPanel()` に一本化し、既存の `r` キー操作にも適用した

- **背景**: T5（提出済みレビュー結果の編集）で「編集中にパネルを閉じると暗黙にキャンセルする」
  （AC-I2）を実装する際、design.md のコード例は `#btn-submit-close` のクリックだけを
  想定していたが、実装時に確認したところ、既存のキーボードショートカット `r`
  （`templates/app.js` の `onKeyDown()`）も同じ `#submit-panel` を独自に開閉しており、
  そちらは `showPanel()` を直接呼ぶだけで `editingReviewId` を考慮していなかった。
- **決定**: `closeSubmitPanel()`（`editingReviewId` があれば `cancelEditReview()` を呼んでから
  `showPanel("submit-panel", false)`）を新設し、`#btn-submit-close`・`#btn-start-review` の
  トグル・`r` キーの3経路すべてをこれに揃えた。`Escape` での配線は tasks.md T11 の scope の
  ままそちらで行う。
- **理由・代替案**: `r` キーを直さない案もあったが、閉じる経路が1つでも `editingReviewId`
  を考慮しないままだと、そこから閉じたときだけ「編集中」の状態が残ったまま新規作成の
  ボタン操作に戻ってしまう（`updatePendingCount()` がラベルを書き換えても
  `editingReviewId` は非 null のままなので、次に「提出する」を押すと新規作成のつもりが
  実は編集の上書きになる、という分かりにくい不具合になる）。design.md には無い箇所だが、
  同じ不変条件（閉じたら編集は終わる）を守るために直した。
- **影響**: `templates/app.js` の `onKeyDown()` 内 `r` 分岐が対象。design.md のコード例からの
  差分はこの1点のみ。

## D7: `SVG_NS` は分割して書き、既存テストの `WRITE_UI` から `btn-submit-open` を外した

- **背景**: T1 実装後に `python3 -m unittest` を実行したところ、research.md が「既存テストに
  直接のアサーションは無い（grep で未検出）」とした前提に反し、2 件の既存テストが落ちた。
  (1) `HtmlTest.test_contains_no_external_reference` は生成 HTML 全体を `"http://"` 等の
  部分文字列で検査しており、`document.createElementNS()` に渡す SVG 名前空間 URI
  （`http://www.w3.org/2000/svg`。ネットワーク先ではなく XML の識別子）が誤って
  外部参照とみなされ落ちた。さらに、その回避策を説明する最初のコメート自体に
  `"http://"` という文字列を引用符付きで書いてしまい、同じ理由で二重に落ちた
  （`--repo .` が自分自身の未コミット差分をレビューするため、コメントの文言も
  埋め込み JSON に混入する）。
  (2) `ReadonlyTest.test_normal_output_still_has_it` は `WRITE_UI` の一覧に
  `id="btn-submit-open"` を含んでおり、T4 でこのボタンを削除したことと直接矛盾した
  （F2 の意図どおりの削除で、テスト側が旧仕様を前提にしていた）。
- **決定**: (1) `SVG_NS` を `"http:" + "//www.w3.org/2000/svg"` の2文字列に分割し、
  かつ説明コメントでも `"http://"` を直接引用しない書き方に直した。(2) `WRITE_UI` から
  `'id="btn-submit-open"'` を外し、代わりに `'id="review-list"'`（T5 で新設した、
  読み取り専用では出ない要素）を加えた。
- **理由・代替案**: (1) は、テスト側を「SVG 名前空間は例外」と緩める案もあったが、
  検査対象を機能ではなく文字列に保つ既存の単純さを崩したくなかったため、値側で
  回避する方を選んだ。(2) は `WRITE_UI` を単に間引く案もあったが、`#submit-panel` 内部の
  書き込み専用要素を1つはカバーし続けたいので、削除した ID を新設した ID に置き換えた。
- **影響**: `templates/app.js:156-160` 付近（`SVG_NS` とその説明コメント）、
  `tests/test_diff_review.py` の `ReadonlyTest.WRITE_UI`。`python3 -m unittest discover`
  （126 件）が green であることを確認済み。

## D8: 全11タスクの独立点検（taskcheck）を実施し、指摘は review.md に集約した

- **背景**: `mode: autonomous` のため、`protocol-check.md`「(b)」に従い T1〜T11 の全タスクを
  それぞれ独立コンテキストへ点検させた（`aidev taskcheck start <id> --mode delegated`）。
  合計 8 件の指摘（should 4・nit 4）。
- **決定**: 内容は `review.md`「タスク点検ログ」節に1件1行で記録し、修正できるものは
  その場で直した（SVG 名前空間 URI のテスト回避を本質的な対処に差し替え、readonly での
  死んだ分岐を削除、通知バッジのコントラスト、未読カウントの開閉整合、編集対象消失時の
  無言リセット）。複雑さに見合わない2件（sub-pixel の角丸誤差、`NOTIF_LIMIT` と
  `notifUnread` の非連動という稀な edge case）は許容として据え置いた。
- **理由・代替案**: いずれも許容した2件は影響が視認不能なレベル（sub-pixel）か、
  発生条件が極めて稀（51件以上の通知を一度もベルを開かず溜める）で、対応のコード量が
  効果に見合わないと判断した。
- **影響**: `templates/app.js`/`templates/style.css`/`tests/test_diff_review.py` に
  追加の修正を加えた。`python3 -m unittest discover`（126 件）で green を再確認済み。

## D9: review 工程で見つかった2件（AC12 の重大度消失・編集中インジケータ欠如）を coding へ
  差し戻して直した。design.md の F5 節の事実誤認は decisions.md に残すだけにし、
  承認済みの design.md 本文は書き換えない

- **背景**: coding 完了後の review 工程（要件適合/価値適合を重点にした独立点検）で、
  taskcheck・cross・unittest・jsdom のいずれでも拾われなかった2件が見つかった。
  (1) `.thread[data-collapsed="true"] > .comment { display: none; }` により、重大度
  バッジ（`.comment > .who` の中にしかない）が折りたたみと同時に消え、AC12「重大度などの
  ヘッダー情報は見えたまま」に反する。design.md F5 節の「位置・解決状態・重大度は
  `.thread-head` の中に既にある」という記述自体が事実と異なっていた（doccheck 2 ラウンドも
  この事実誤認は拾えなかった——「依拠する既存の事実」ではなく設計方針の説明文だったため）。
  (2) `#review-list` の一覧が複数件のとき、編集中のエントリを示す印が無く、US3 の
  「いま何を編集しているか一目で分かる」体験を一覧のスクロール時に満たせない。
- **決定**: `aidev event review sent_back` → `unapprove test` → `unapprove coding` →
  `aidev event coding start` の順で coding へ戻し、(1) `renderThread()` の `.thread-head`
  に `threadSeverity(thread)` から重大度バッジを追加、(2) `reviewEntry()` に
  `data-editing`/「編集中」表示を追加し `editReview()`/`cancelEditReview()` から一覧を
  再描画、の2点を直した。**承認済みの `design.md` 本文は書き換えない**——F5 節の事実誤認は
  この decisions.md のエントリに残すことで、他工程からも経緯が辿れる形にした。
- **理由・代替案**: `design.md` を遡って修正する案もあったが、`design.md` は承認済みの
  成果物であり、書き換えると「いつ・なぜ直したか」が本文の中に埋もれる。decisions.md に
  追記する方が、protocol.md「8.1」の「1決定=1エントリ・追記式」の趣旨（当時どう考えたかを
  残す）に沿う。
- **影響**: `templates/app.js`（`renderThread()`/`reviewEntry()`/`editReview()`/
  `cancelEditReview()`）、`templates/style.css`（`.review-entry[data-editing]`/
  `.review-entry-editing`）。headless DOM 検証（jsdom）を拡張し、両修正を実際にクリック/
  入力して確認した（`test-result.md` 参照）。`python3 -m unittest discover`（126 件）は
  green のまま。review 工程をやり直し、この2件の再発が無いことを再確認する。

## D10: review ラウンド2で見つかった重大度バッジの二重表示を修正（D9 の修正自体が原因）

- **背景**: review ラウンド2（D9 の修正を検証する独立点検）で、D9 が `.thread-head` に
  追加した重大度バッジが、展開時（折りたたんでいない通常時）に既存の `.comment > .who`
  側のバッジと二重表示になる、という新たな指摘（should）を受けた。`threadSeverity(thread)`
  は常に「先頭コメントの重大度」を返すため、`.thread-head` のバッジと先頭コメント自身の
  `.who` のバッジが同じ内容で重複していた。**この指摘は前ラウンド（D9）の修正そのものに
  由来する**ため、`protocol.md`「10.」の指示（同じ不変条件を支える項をすべて列挙して
  壊してみる）に従い、severity 表示箇所を `grep -n '"sev-'` で全数洗い出した
  （`templates/app.js:1595`=`.thread-head`（今回）、`:1644`=`.comment > .who`（既存）、
  `:1743`=`clItem()` の一覧表示（別 DOM 部分木・重複なし）の3箇所のみ）。
- **決定**: `renderComment()` 側で、先頭コメント（`comment === thread.comments[0]`）のときだけ
  `.who` の重大度バッジを省くよう修正した（返信が個別に持つ重大度は従来どおり `.who` に
  表示される。返信にも重大度を付けられる仕様は `openComposer()` の既存挙動で、D9/D10 では
  変えていない）。
- **理由・代替案**: `.thread-head` 側のバッジを撤回する案もあったが、AC12（折りたたんでも
  重大度が見える）を満たすには `.thread-head` 側の表示が必須。`.comment` 側を先頭コメントに
  限って省く方が、影響範囲が最小（返信の重大度表示は変えない）。
- **影響**: `templates/app.js:1639-1645` 付近（`renderComment()`）。headless DOM 検証を
  さらに拡張し、(a) 展開時に先頭コメント側の重複が無いこと、(b) 返信自身が持つ重大度は
  抑制されず表示されること、の両方を確認した（47件、すべて pass）。
  `python3 -m unittest discover`（126件）は green のまま。

## D11: deliver（PR #26 マージ）後、実ブラウザで確認したユーザーから2件の指摘を受け、
  work を再開して修正した

- **背景**: PR #26 マージ後、ユーザーが実際にブラウザで生成 HTML を開いて確認し、
  (1) sticky なファイルヘッダーとトップバーの間に隙間がある、(2) トップバーのボタンの
  高さが揃っていない（通知ベルが他より高く、そもそも既存のボタン同士も 28px と
  32.39px でばらついていた）、の2件を報告した。これは `test-result.md`「未検証の穴」に
  記載していたとおり、jsdom が実際のレイアウト計算をできないために検出できなかった
  種類の欠陥。
- **決定**: `aidev-70-deliver`「deliver 後に作業が続いたら」の手順に従い、`aidev use`
  でこの work を再開し、`aidev event coding start` から入り直した。
  (1) `.pane-center` の `padding-top` を `0` にし、`#overall` の `margin-top: 16px` で
  同じ視覚的余白を確保（padding は sticky の基準位置に含まれるが margin は含まれない
  ため）。
  (2) `.topbar .actions button` に `height: 28px` と flex ベースの中央揃えを追加し、
  line-height 依存の高さ計算（本文からの継承・SVG コンテンツでの baseline のずれ）を
  排除して、トップバーの全ボタンを 28px に統一した。
- **理由・代替案**: (2) は基底の `button {}` セレクタを直接 28px に固定する案もあったが、
  行コメントの「+」ボタン等、トップバー外の小さいボタンまで巻き込んで壊す
  （`.comment-open` 等は現状 `height: auto` の compact なサイズに依存している）ため、
  `.topbar .actions button` に絞ったスコープの狭い上書きを選んだ。
- **影響**: `templates/style.css` のみ。headless DOM 検証（jsdom）に9件のアサーションを
  追加し、`getComputedStyle()` で実際に確認した（計60件、すべて pass）。
  `python3 -m unittest discover`（126件）も green。新しいブランチ・PR で提出する
  （PR #26 は既にマージ・ブランチ削除済みのため再利用しない）。

## D12: PR #27 マージ後、ボタンの高さ不揃いがトップバー以外にも残っているとの指摘を受け、
  基底の `button {}` ルールに一本化した

- **背景**: D11 では `.topbar .actions button` という個別スコープで高さを揃えたが、
  ユーザーから「ファイルにコメント」「コメントする」「閉じる」等、トップバー以外の
  ボタンも高さが揃っていないと指摘された。調べたところ、**ファイル操作列
  （`.file-actions`）は `.icon-btn`（expand-all/collapse-all、約28px）と素の
  `.comment-open`（「ファイルにコメント」、約32.4px）が混在**しており、
  トップバーと全く同じ根本原因（`button` の `line-height` が `body` の `1.6` を継承する
  一方、`.icon-btn` は独自に `1.2` を持つ）がサイト全体に広がっていた。
- **決定**: 個別スコープ（`.topbar .actions button`）を削除し、**基底の `button {}` へ
  `height: 28px; display: inline-flex; align-items: center; justify-content: center;`
  を移して、サイト全体の既定にした**。`<select>`（コメントの重大度・コメント一覧の
  絞り込み）にも `height: 28px` を追加し、ボタンと同じ行での見た目を揃えた。
  一方、以下は明示的に `height: auto`（元の見た目のまま）へ戻した:
  `.row .comment-open` / `.row.split .cell .comment-open`（差分の各行の「+」。12px
  フォントの行の高さを崩さないため）・`.expander button`（隙間展開のボタン。同じく
  12px の文脈）・`.cl-item`（コメント一覧の1件。位置・タグ・本文の複数行を持つ）。
- **理由・代替案**: 個別スコープをファイル操作列・コメント入力欄・スレッド見出し・
  レビュー結果一覧…と後から1つずつ追加していく案もあったが、同じ根本原因（`button`
  の line-height 継承）が既に複数箇所で再発していたことから、**基底のルールを直す方が
  同種の再発を将来にわたって防げる**と判断した。例外にした3箇所は、いずれも「差分の
  12px フォント文脈に収める」「複数行の内容を持つ」という明確な理由がある。
- **影響**: `templates/style.css` のみ。headless DOM 検証（jsdom）でファイル操作列・
  コメント入力欄・スレッド見出し・提出パネル・レビュー結果一覧の編集/削除ボタンが
  すべて 28px、かつ3つの例外箇所は `auto` のままであることを `getComputedStyle()` で
  確認した（62件 pass・1件は差分が1ファイルのみの回でツリーのフォルダ行が出ないための
  環境依存スキップ）。`python3 -m unittest discover`（126件）も green。

## D13: PR #28 マージ後、ユーザーから「高さの修正が元に戻っている」と報告を受け、jsdom では
  検出できなかった `min-height` の実ブラウザでの誤解を修正した

- **背景**: PR #28（D12）で `height: 28px` を `min-height: 28px` に変更したが、
  ユーザーが実ブラウザで確認したところ、トップバーのボタンが軒並み**元の 32.39px に
  戻って見える**と報告された。jsdom はレイアウトエンジンを持たないため、
  `getComputedStyle().minHeight` が `"28px"`（**指定値**）を返すことしか確認できておらず、
  **実際に描画される高さ**（レイアウト計算後の**使用値**）は一度も検証できていなかった
  （test-result.md の「未検証の穴」に明記していたとおり）。この work のために
  playwright-core（既存の Chromium バイナリを流用）を使い、初めて実際のブラウザで
  `boundingBox()` を測定して検証したところ、`.icon-btn`（`line-height: 1.2` を独自に
  持つ）は正しく 28px になる一方、素の `button`（`font: inherit` で `body` の
  `line-height: 1.6` を継承＝14px×1.6=22.4px＋padding8px＋border2px=32.4px）は
  **min-height: 28px が一切効かず 32.39px のまま**であることを実測した。
  **根本原因**: `min-height` は「これより小さくしない」という下限であって、
  content 由来の自然な高さ（この場合 32.4px）が既に下限（28px）を超えていれば
  **何の効果も持たない**。`height: 28px`（強制）から `min-height: 28px`（下限）へ
  変更した時点で、line-height を詰めるという対処を欠いたまま「28px に揃う」ことを
  前提にしてしまっていた——D12 の設計判断そのものに欠陥があった。
- **決定**: 基底の `button {}` に `line-height: 1.2;` を追加した（**`font: inherit` の
  直後に書く**——`font` ショートハンドは `line-height` を含めて巻き込むため、先に書くと
  上書きされて消える。実機検証で確認済みの落とし穴）。これにより通常の1行ラベルの
  content 高さが 28px 未満（14px×1.2=16.8px＋padding8px＋border2px=26.8px）に収まり、
  `min-height: 28px` の下限が実際に効くようになる。長いラベルが2行に折り返す場合は
  従来どおり `min-height` を超えて自然に伸びる（欠けない。D12 で得た折返し安全性は
  維持）。
- **理由・代替案**: `height: 28px`（固定）に戻す案は D12 で指摘された折返し時のはみ出し
  リスクを再度持ち込むため却下。`min-height` を使いながら `line-height` を詰める
  今回の対処が、両方の要件（28px に揃う・長いラベルでも欠けない）を両立する。
- **検証方法の追加**: jsdom は「指定値」（specified value）は読めるが「使用値」
  （used value、実際にレイアウト計算された値）は読めないため、今回のような
  `min-height` が効かないバグを検出できない。この work のために
  `playwright-core` ＋ 既存インストール済みの Chromium バイナリ
  （`~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`）を使い、
  `page.locator(...).boundingBox()` で実際の描画結果を測定する検証手段を用意した
  （スクラッチ領域のみで実行し、成果物には含めない）。トップバー7個・ファイル操作列
  （file-toggle/copy-path）・composer（コメントする/閉じる/severity select）・
  submit-panel（提出する/閉じる）・例外3箇所（差分行の+/expand-all/expander button）の
  いずれも実ブラウザで 28px（または例外は意図どおりの小さい値）になることを確認した。
- **影響**: `templates/style.css` の基底 `button {}` ルールのみ（1行追加）。
  `python3 -m unittest discover`（126件）は green。今回は実ブラウザでの実測を伴う
  最終確認まで行った。**test-result.md の「未検証の穴」から「実際の描画・レイアウト」の
  項目を、この work に関しては解消済みとして更新する**（他の work では引き続き
  実ブラウザでの検証手段が無い場合がある点に留意）。

## デバッグ D1: logic / retry（review round 1・2026-09-18T01:15:39Z）
- 根本原因: review の3回の差し戻しは、同一の欠陥が直らず再発したものではなく、毎回異なる新規の観点（AC12の重大度消失→編集中インジケータ欠如→D9修正自体が生んだ重複表示→ボタン高さのトップバー限定スコープ不足→height固定による折返し時のはみ出しリスク）を独立点検が都度発見したもの。根本原因は「視覚的な完成度（CSSレイアウト）は自動テストでは検出できず、独立点検・実ブラウザでの目視・レビュー観点の深掘りでしか段階的にしか見つからない」という性質そのもの。各回の指摘はその場で修正し、修正の巻き戻し・やり直しは発生していない（同じ欠陥のループではない）。
- 確認方法: python3 -m unittest discover（126件）と headless DOM 検証（jsdom, 64件）がいずれもgreen。style.cssの最終diffを通読し、min-height化・3例外セレクタのmin-height:0明示・select要素の高さ統一が矛盾なく揃っていることを確認済み（review.md ラウンド6参照）。
- 確度: high
- 次の行動: retry

## D14: PR #29 マージ後、ユーザーの実利用から5件の追加指摘を受け、うち1件は本 work の
  コードにあった不具合（ツリーのフォルダ非表示）、4件は新規の使い勝手改善として対応した

- **背景**: ユーザーが実際にツールを使い、以下5件を報告した。
  1. ツリー表示でフォルダの行が出ない（例: `apps/sample/src` 配下に2ファイルだけの
     とき、フォルダ名の行が消えてファイルだけが並ぶ）。
  2. コメント一覧パネルを閉じても「指摘はまだありません」が見えてしまう。代わりに、
     パネルの開閉ボタンに未解決件数・未レビューのファイル数をバッジ表示してほしい
     （展開時は消す）。
  3. ファイル一覧・コメント一覧のドラッグでのリサイズが、閉じた状態より小さくできて
     しまう。
  4. ファイルの「確認済み」チェックを入れたら、そのファイルのソースを自動で畳んで
     ほしい。
  5. コメントの「解決済み」にしたら、そのスレッドも自動で畳んでほしい。
- **決定・原因**:
  1. `buildTree()`/`collapseSingles()` は、全ファイルが1つの共通フォルダに収まる場合、
     **ルート自身まで畳んでしまい**、そのフォルダ名を表示する行そのものが消えていた
     （`templates/app.js:723-741`）。ルートは畳まず、ルートの直下フォルダだけを畳むように
     修正した。**これは本 work の T2（ツリーアイコン）が触れた既存コード
     （`buildTree`/`collapseSingles`。decisions.md D10 で導入）に元からあった不具合**
     ——T2 では表示ロジックを変えておらずアイコンを挿すだけだったため見つからなかった。
  2. `#commentlist { display: grid; ... }` が**ID セレクタ**で、パネルを閉じたときの
     `.shell[data-right="collapsed"] .pane-right > *:not(.pane-sticky) { display: none; }`
     （クラスセレクタ）を **ID の方が強いため上書き**していた。ID を含む同格のセレクタで
     上書きし直した。加えて `#pane-left-badge`/`#pane-right-badge`（`.notif-badge` と
     同じ見た目を流用）を新設し、`updateFileBadge()`/`updateCommentBadge()`
     （`templates/app.js`）で「パネルが閉じているときだけ・件数が1以上のときだけ」
     表示するようにした。
  3. `templates/ui.js` の `MIN_W`（ドラッグでの最小幅）が `0` だった。閉じた状態の
     ストリップ幅（`style.css` の `.shell[data-left="collapsed"]` 等、40px）に合わせて
     `MIN_W = 40` に変更した。
  4. `viewedBox`（確認済みチェックボックス）の `change` ハンドラに、チェックを入れた
     ときだけ `toggleFile()` を呼んで折りたたむ処理を追加した（外したときは自動で
     展開し直さない）。
  5. `resolveButton`（解決にするボタン）のクリックハンドラに、`thread.resolved` を
     true にしたときだけ `threadCollapsed[thread.id] = true` を設定する処理を追加した
     （T8 で作った折りたたみの仕組みをそのまま再利用。未解決に戻したときは自動で
     展開し直さない）。
- **検証**: D13 の教訓（jsdom は「指定値」しか読めず「実際に描画される高さ/見え方」を
  検証できない）を踏まえ、**実装した5件すべてを playwright-core による実ブラウザ
  操作・スクリーンショットで確認**した（`click`/`fill` で実際にユーザー操作を再現し、
  `boundingBox()`/`isVisible()`/スクリーンショットで結果を確認。jsdom だけでは
  2番のバッジ表示・CSS 特異性起因の非表示漏れ・3番のドラッグ最小幅のいずれも
  検出できなかった可能性が高い）。既存の headless DOM 検証（jsdom, run.js）・
  `python3 -m unittest discover`（126件）もあわせて green を確認済み。readonly
  ビルドでも例外なく動作し、フォルダ表示・バッジ表示とも機能することを確認した。
- **影響**: `templates/app.js`（`buildTree`/`viewedBox` change/`resolveButton` click/
  `renderViewedCount`/`renderThreads`/新設 `updateFileBadge`/`updateCommentBadge`）、
  `templates/page.html`（バッジ用 `<span>` 2箇所）、`templates/style.css`（`#commentlist`
  の上書き・`.pane-badge`）、`templates/ui.js`（`MIN_W`）。

## D15: D14 のバッジ更新が、ボタンのクリック以外の開閉経路（キーボードショートカット・
  セパレータ操作）では効いていなかった不具合を review 工程の独立点検で見つけて直した

- **背景**: D14 で `#btn-pane-left`/`#btn-pane-right` の `click` イベントにバッジ更新を
  結線したが、review 工程の独立点検で、パネルの開閉状態が変わる経路はクリックだけでなく
  `{`/`}`（`UI.togglePane()` を直接呼ぶ）・`[`/`]`（`focusPane()` 経由の
  `UI.openPane()`）・セパレータへの Enter/Space・セパレータのドラッグ開始時の自動オープン
  など複数あり、いずれも ui.js 側で完結していて app.js のバッジ更新を経由しない、と
  指摘された。
- **決定**: 開閉状態を実際に書き換える唯一の関数 `setPane()`（`templates/ui.js`）に
  フック機構（`onPaneChange`）を追加した。ui.js は**フックの中身を一切知らない**まま
  （画面の形だけを扱うという既存の約束を保ったまま）、状態が変わったことだけを
  app.js へ伝える。app.js は `UI.onPaneChange(fn)` で
  `updateFileBadge`/`updateCommentBadge` を登録し、クリック個別の結線
  （`btn-pane-left`/`btn-pane-right` への追加リスナー）は撤去した。
- **理由・代替案**: 個々の経路（キー・セパレータ）ごとに app.js から結線し直す案もあったが、
  経路が今後増えるたびに同じ抜け漏れを繰り返す。状態を書き換える唯一の箇所にフックを
  1つ置く方が、経路の数に関わらず確実。
- **検証**: playwright-core で `}`/`]`/`{` のキーボードショートカット、セパレータへの
  `Enter` キー操作、それぞれでバッジが正しく表示/非表示に切り替わることを実測した
  （4経路すべて確認）。既存の headless DOM 検証（jsdom, run.js）・
  `python3 -m unittest discover`（126件）・D14 の12項目の実ブラウザ確認も再実行し、
  いずれも green のままであることを確認した。
- **影響**: `templates/ui.js`（`setPane`/`onPaneChange`/`DiffReviewUI` の公開面）、
  `templates/app.js`（`wire()` の結線をクリック個別から `UI.onPaneChange` 登録に変更）。

## D16: PR #30 マージ後、ユーザーからセパレータの D&D リサイズに2件の指摘を受け、
  `wireSeparator()` のドラッグ開始/移動の扱いを見直した

- **背景**: ユーザー報告2件。(1) ファイル一覧・コメント一覧が畳まれた状態でセパレータを
  D&D しようとすると、勝手に展開状態になり、展開した分だけマウス位置と罫線の位置が
  ずれる。(2) D&D でサイズを縮小したとき、開閉ボタンで畳んだ場合と異なり、
  一覧の中身が隠されずに見えたまま残る（`MIN_W`=40px まで縮まっても `data-left`/
  `data-right` は `open` のままだった）。
- **決定**: `templates/ui.js` の `wireSeparator()` `pointerdown` から
  「畳んでいたら先に `setPane(..., true, true)` で開く」処理を削除し、代わりに
  `currentWidth()`（畳んでいれば実測 40px）をそのままドラッグの起点にした。
  さらに新設した `applyWidth(which, rawWidth, save)` を `pointermove` から呼び、
  `clampWidth()` した幅が `MIN_W` 以下なら `setPane(which, false, save)` で畳んだ表示
  （中身を隠す）へ倒し、`MIN_W` を上回れば `setPane(which, true, save)` で開いたうえで
  `setWidth()` を適用する。ドラッグ中は `save=false` のまま（従来どおり離した時点でのみ
  `pref()` へ書く）。`pointerup` 側もその時点の開閉状態を見て
  `pane-left`/`pane-right` の pref を確定させるよう変更した（幅の pref は開いている
  ときだけ `setWidth(..., true)` で書く。畳んだままなら幅の pref は変更しない——
  再度開いたときに畳む直前の幅へ戻るようにするため）。
- **理由・代替案**: 「ドラッグ開始時に自動で開く」処理自体をなくせば (1) は解消する。
  開始時点では幅を変えていないので、そのままではドラッグしても畳んだ表示
  （固定40pxのグリッド列）のまま見た目が変わらないが、これは実際に MIN_W を
  超えて動かした瞬間に `applyWidth` が開閉を切り替えるため、連続的にドラッグ量へ
  追従する形で解決される（ジャンプではなく「40pxから伸びていく」自然な動き）。
  (2) は MIN_W がそのまま「畳んだときのストリップ幅」と同じ値であることを利用し、
  ドラッグでその床に到達した時点を「畳んだ」と同一視して倒すことにした。閾値を
  別に持たず既存の `MIN_W` を再利用することで、`clampWidth` の下限とパネルの
  折りたたみ判定の基準がずれない。
- **検証**: playwright-core（`out.html` を `git range 8b22f0c..056ffc8` から生成）で
  実ブラウザ操作を実測。(a) 畳んだ状態からの2pxドラッグでセパレータの位置が2px程度しか
  動かない（ジャンプしない）、(b) 一切動かさずに押して離した場合は畳んだまま、
  (c) 畳んだ状態から大きく広げるドラッグで開いて中身（`#filelist`）が見える、
  (d) 開いた状態から大きく縮めるドラッグで畳んだ表示になり中身（`#filelist`/
  `#commentlist`）が隠れ、ストリップ幅が正確に40pxになる、(e) 畳んだ状態はリロード後も
  `localStorage` 経由で保持される、(f) 左右両ペインで同様、(g) ドラッグで畳んだ後に
  開閉ボタンで開き直すと畳む直前の実際の幅（40pxではない）に戻る——の19アサーション
  すべて green。既存の `python3 -m unittest`（tests/test_diff_review.py, 140件）も
  green のまま（Python 側は無変更のため影響なし）。
- **影響**: `templates/ui.js` のみ（`wireSeparator`/新設 `applyWidth`）。CSS・app.js・
  HTML 構造の変更なし。

## D17: D16 の review 工程で2件の should 指摘を受け、不変条件をドラッグ以外の経路（キーボード・
  読み込み時）にも広げ、`aria-valuenow` の陳腐化を直した

- **背景**: review 工程の独立点検（別コンテキストの subagent）から2件。
  (1) `applyWidth` は `wireSeparator` の pointerdown/move/up からしか呼ばれておらず、
  セパレータへの `Home` キー操作は従来どおり `setWidth(which, MIN_W, true)` を直接
  呼んで「開いたまま幅だけ40pxにする」状態を作れた。この状態を保存したままページを
  再読み込みすると、`init()` は保存された `pane-left: open` をそのまま復元するので、
  D16 で塞いだはずの「開いたまま40pxに潰れて中身が見える」状態がキーボード経路＋
  リロードで再現できる。(2) `applyWidth` の畳む分岐は `setWidth` を呼ばない（呼ぶと
  再度開いたときに戻る幅を上書きしてしまうため意図的に避けた）が、そのぶん
  `aria-valuenow` が畳む直前の値のまま更新されず、視覚的には畳んでいるのに
  支援技術には畳む前の幅が残ったまま見える。
- **決定**: (1) `wireSeparator` の `keydown` ハンドラの4つの `setWidth` 呼び出しを
  すべて `applyWidth` に置き換え、末尾の「畳んだ状態からの矢印キーは強制的に開く」
  トリックを削除した（`applyWidth` が自分で開閉を判断するため不要かつ、削除しないと
  `Home` で畳んだ直後に再び開いてしまう）。これにより `Home` は「最小幅にする」ではなく
  「畳む」を意味するようになる（D16 で確立した「MIN_W 以下は畳む」という不変条件と
  一致させた、意図した仕様変更）。`init()` も `pref()` から読んだ幅と開閉状態を
  そのまま復元するのではなく、`幅 <= MIN_W なら開閉状態によらず畳む` という同じ
  不変条件で正規化してから復元するよう変更した。
  (2) `applyWidth` の畳む分岐で、`--left`/`--right` の CSS 変数（＝ 再度開いたときに
  戻る幅）はそのままに、`aria-valuenow` だけを直接 `MIN_W` へ更新するようにした。
- **理由・代替案**: (1) は「保存状態の読み込み」という別の入口を都度つぶすのではなく、
  幅を実際に書き換える経路（ドラッグの `move`・キーボードの4キー・読み込みの
  `init()`）すべてで同じ判断（`width <= MIN_W` なら畳む）を通すことで、今後この種の
  入口が増えても同じ穴を作らないようにした。(2) は `setWidth` をそのまま呼ぶ案も
  検討したが、`--left`/`--right` まで上書きすると D16 で確認した「畳んだあと開き直すと
  元の幅に戻る」が壊れるため、`aria-valuenow` だけを直接更新する方を選んだ。
- **検証**: playwright-core で追加7アサーション。`End`→`Home` キー操作で `Home` が
  畳んだ表示（`#filelist` 非表示）になること、`localStorage` に意図的に
  `pane-left=open` かつ `left-width=40` という壊れた組み合わせを書き込んでからリロード
  しても畳んだ表示に正規化されること、ドラッグで畳んだ直後の `#sep-left` の
  `aria-valuenow` が実測 `"40"` になっていること、を確認。既存の D16 の19アサーション
  （`#sep-left`へのフォーカスをクリックではなく `locator.focus()` に修正——pointerdown
  ハンドラの `preventDefault()` によりクリックではフォーカスが乗らないため、テスト側の
  不備であり実装側の問題ではない）を含む計25アサーション、すべて green。
  `python3 -m unittest`（140件）も green のまま。
- **影響**: `templates/ui.js` のみ（`applyWidth`/`wireSeparator` の `keydown`/`init`）。

## D18: 下書き自動復元時の確認バナーを撤去し、代わりに常設の「下書きを初期化」ボタンを新設した
  （D3 が「選択を要するバナーは残す」とした対象の1つを、この work で明示的に覆す）

- **背景**: ユーザーから「セッションストレージへの保存機能は不要なので削除して」と要望。
  コードを確認すると実際には `sessionStorage` は使っておらず、`localStorage` ベースの
  保存機能が2種類ある：(a) app.js の下書き自動保存（コメント本文。`diff_digest` を
  含むキーで差分ごとに区別済み）、(b) ui.js の画面の見た目の記憶（テーマ・ペイン幅・
  開閉・フィルタ。意図的に差分ごとの区別をしない——D5）。`AskUserQuestion` で
  対象を確認したところ、ユーザーは削除ではなく「html を開き直した際に**復元するかを
  聞かれる**が、自動的に復元して確認を求めないでほしい」「初期化したい場合は明示的に
  初期化するので、初期化ボタンを配置してほしい」と回答——実際に「聞かれる」ように
  見えていたのは (a) の下書き復元時に `boot()` が毎回自動表示していたバナー
  「このブラウザに保存されていた下書きを復元しました。[下書きを破棄してやり直す]」
  だった（D3 は「ボタンを伴うバナー（下書き復元の選択）は選択を要するので画面上部に
  残す」と決めていたが、ユーザー視点では復元はすでに自動で行われており、バナーは
  「確認を求められている」ように感じられ不要だった）。(b) にはそもそも復元確認の
  ようなものは無い（起動時に無言で適用されるだけ）ため、今回の対象は (a) のみと判断した。
- **決定**: `boot()` 内の自動表示バナー（`banner("...復元しました。", [...])`）を削除した。
  下書きの自動保存・自動復元そのもの（`persist()`/`restore()`）は変えていない——
  復元は従来どおり毎回**無言で**行われる。代わりに、rw ブロック内（トップバー）へ
  常設の「下書きを初期化」ボタン（`#btn-reset-draft`）を新設し、押すと
  `resetDraft()`（旧バナーの「下書きを破棄してやり直す」と同じ処理: `dropSaved()` →
  `drafts={}` → 埋め込みレビューがあればそれへ、無ければ空へ戻す）を確認ダイアログ
  無しで即座に実行する。`viewedFiles`（確認済み）は下書きと独立という既存の扱いを
  そのまま引き継ぎ、初期化の対象に含めていない。
- **理由・代替案**: バナーの表示条件だけを絞る（例: 前回と内容が変わっていなければ
  出さない）案も検討したが、「何かが自動で起きたことを毎回通知する」設計そのものが
  ユーザーの望む体験（無言で復元・要るときだけ自分で消す）と合わない。ボタンを
  常設にすることで、下書きが実際に復元されたかどうかに関わらずいつでも初期化操作が
  可能になり、「バナーが出たときしか消せない」という制約も無くなる。確認ダイアログ
  （`confirm()`）を挟む案もあったが、このアプリは `confirm()`/`alert()` を一切使わない
  既存の一貫した設計（`deleteReview()` 等、既存の破壊的操作もすべて確認なしの即時実行）
  に倣い、揃えた。
- **検証**: playwright-core で11アサーション。ボタンが常設で見えること・全体コメントに
  下書きを書くと `persist()` により `localStorage` に1件だけ書かれること・リロードしても
  「復元」系のテキストが `#banners` に一切出ないこと・下書きの中身自体は自動で復元されて
  いること・初期化ボタンを押すと確認ダイアログ無しで即座に `localStorage` のキーが
  消えテキストエリアが空になること・再度リロードしても空のままであること、を確認
  （`page.on('dialog', ...)` でダイアログが一切出ないことも監視した）。readonly ビルドでは
  `#btn-reset-draft` が DOM に1件も存在しないことも実ブラウザで確認した（rw ブロックに
  入れたための既存の仕組みで自動的に除外される）。`python3 -m unittest`（140件、
  `WRITE_UI` タプルに `id="btn-reset-draft"` を追加）も green。
- **影響**: `templates/app.js`（`boot()`/`wire()`、新設 `resetDraft()`、`embeddedReview` を
  モジュール先頭の変数へ昇格）、`templates/page.html`（`#btn-reset-draft` を rw ブロックへ
  追加）、`tests/test_diff_review.py`（`WRITE_UI` タプル）、`SKILL.md`（下書き自動保存の
  説明を更新）。`templates/ui.js`（画面の見た目の記憶）は対象外・無変更。
- **review 工程の独立点検**: must/should 指摘は無し。nit 1件——`#btn-reset-draft` の
  `title`/`aria-label` が可視テキストと重複しており、隣接する `#btn-start-review`/
  `#btn-export-open`（どちらも `title`/`aria-label` を持たない）と流儀が揃っていない、
  という指摘。`aria-label`（可視テキストと完全に重複）は削除し、`title`（可視テキストに
  無い説明——「初期化」が具体的に何をするかのヒント）は残した。修正後、
  `python3 -m unittest`（140件）を再実行し green を確認。

## D19: キー操作説明（#help）をフローティング表示にし、通知ベルの空状態が細長い帯に
  見えていた不具合を修正した

- **背景**: ユーザーから2件の要望。(1) キー操作説明（`#help`）をフローティング表示に
  し、表示時に他の表示へ影響を与えないようにしてほしい。×アイコン・backdrop クリック・
  Esc キーで閉じられるようにしてほしい。(2) 通知ベルをクリックして通知が無いとき、
  細長いバーのようなメッセージ領域が表示されるので、ある程度のサイズで表示させ、
  「メッセージなし」のテキストを載せてほしい。
  - (1) を調べると、`#help` は他の `.panel`（`#submit-panel`/`#export-panel`）と同じく
    文書の流れに乗ったブロックで、開くと `ui.js` の `syncTopbarHeight()` がその高さを
    `--topbar-h` に足し込み、`.shell` の高さ（他のペイン全体）まで変わっていた。
    Esc キーでの close は実はすでに実装済みだった（`onKeyDown()` の `Escape` 分岐が
    `showPanel("help", false)` を呼んでいた）が、backdrop・×ボタンは無かった。
  - (2) を実ブラウザで再現すると、`#notif-panel` の高さが実測 10px しかなく、
    `#notif-list .empty`（「通知はまだありません」）の要素が**そもそも DOM に存在しない**
    ことが分かった。`renderNotifList()` は `notify()` の中からしか呼ばれておらず、
    起動直後（1件も通知が飛んでいない状態）にベルを開いても、空状態の描画が
    一度も行われていなかった（要望文の「メッセージなしのテキストを載せてください」は
    比喩ではなく文字どおり——本当に何も描画されていなかった）。
- **決定**: (1) `#help` に `.modal` クラスを追加し `position: fixed` で画面中央固定に、
  背後に `#help-backdrop`（`position: fixed; inset: 0;`）を敷いた。開閉が変わる経路
  （ボタン・`?`・Escape・backdrop クリック・新設の `#btn-help-close`）を、パネル・
  backdrop・トリガーボタンの `aria-expanded` を必ず揃えて書き換える `setHelpOpen(open)`
  1箇所に統一した（review 工程で確立した「状態を書き換える唯一の関数にフックを置く」
  という設計方針——D15/D17と同じ考え方——をここでも踏襲）。`ui.js` の
  `syncTopbarHeight()` の対象 id リストから `"help"` を外し、フローティング化した
  ぶん `.shell` の高さ計算に含めないようにした。
  (2) `renderNotifList()` を `renderAll()`（起動時に必ず通る経路）からも呼ぶようにし、
  1件も通知が無い状態でも「通知はまだありません」が最初から描画されているようにした。
  あわせて `.notif-panel` に `min-height: 72px` を追加し、空状態でも意図した大きさの
  領域として見えるようにした（`.notif-panel .empty` の余白も広げ、テキストを中央に）。
- **理由・代替案**: (1) は `<dialog>` 要素（`showModal()`）の採用も検討したが、この
  アプリは通知ポップオーバー等、既存のフローティング UI をすべて自前の
  `position: fixed/absolute` + `hidden` 属性の切り替えで実装しており（ネイティブ
  `<dialog>` は使っていない）、1箇所だけ別の仕組みを持ち込むと閉じる経路の扱いが
  ばらつく。既存のパターン（backdrop 用の div を敷き、クリックで閉じる）に揃えた。
  (2) は「起動時に呼び忘れている」という単純な抜けだったので、`renderAll()` に足すだけ
  で直接解消する。`min-height` は無くても機能的には直っていたが、要望の「ある程度の
  サイズで表示」に文字どおり応えるため追加した。
- **検証**: playwright-core で18アサーション。フローティング化後も `.shell` の高さが
  開閉前後で変わらないこと（652px→652px）、×ボタン・backdrop クリック
  （`#progress-track` の z-index:200 な6px帯を避けた座標で）・Esc キーそれぞれで
  閉じられること、`aria-expanded` が正しく追従すること、`?` キーでの開閉に回帰が
  無いこと、通知パネルが空でも72px以上の高さを持ち「通知はまだありません」が
  最初から表示されていること、を確認。readonly ビルドでも `#help`/`#btn-help-close`
  が機能することを別途確認。`python3 -m unittest`（140件）も green のまま。
- **影響**: `templates/page.html`（`#help-backdrop`・`.modal-head`・`#btn-help-close`）、
  `templates/style.css`（`.modal-backdrop`/`.panel.modal`/`.modal-head`、
  `.notif-panel` の `min-height`・`.empty` の余白）、`templates/app.js`（新設
  `setHelpOpen()`、`"?"`/`Escape`/`btn-help-open` の3箇所を統一、`renderAll()` から
  `renderNotifList()` を呼ぶ）、`templates/ui.js`（`syncTopbarHeight()` の対象 id）。

## D20: split 表示で削除＋追加の対になる行が、コメントの有無に関わらず常に
  「変更前」「変更後」の見出しで2行分を消費していた不具合を修正した

- **背景**: ユーザーからスクリーンショット付きで報告。split 表示で1行の変更
  （削除＋追加の対）ごとに、コメントが1件も無くても「変更前」「変更後」という
  見出しの行が常に表示され、2行分を消費して見た目が間延びしていた。
  「通常、変更後変更前の行を差分表示で表示しないのでは？」という指摘どおり。
  - 原因を追うと、`splitSlots()` が組み立てる `.slots`（`.slot-side` 見出し＋
    `.threads` ＋ `.composer-slot` の入れ物）は、`.threads`/`.composer-slot` が
    他の関数（`renderThreads()`/`openComposer()`）が鍵で探して差し込むための
    入れ物として**中身が無くても常に DOM に存在**しており、`.slots` 自身が
    リテラルに空（子要素ゼロ）になることが無いため、既存の CSS
    `.row.split .slots:empty { display: none; }` は**一度も発火していなかった**
    （`.slots` は常に最低2つの子要素——`.threads` と `.composer-slot`——を持つ）。
    左右両方に位置を持つ行（削除＋追加の対）では `.slot-side` 見出しも常に
    追加されるため、コメントの有無に関わらずラベルだけが常に見えていた。
- **決定**: `.slots` の可視性を CSS の `:empty` に頼らず、JS で明示的に管理する
  `syncSlotsVisibility(slotsEl)` を新設した。`.threads`/`.composer-slot` の**実際の
  中身の有無**（`firstChild` の有無）を見て `.slots` ごと `hidden` 属性で隠す/見せる。
  呼び出し箇所は3つ: (1) `renderThreads()`（clear→repopulate の後に全 `.slots` を
  スキャン——フル再描画のたびに整合させる）、(2) `openComposer()`（入力欄を開いた
  直後）、(3) `closeComposer()`（入力欄を閉じた直後）。CSS の `.row.split .slots:empty`
  は一度も効いていなかった死んだルールなので削除した。
- **理由・代替案**: CSS の `:has()` で「中身のある `.threads`/`.composer-slot` を
  持たない `.slots` を隠す」というセレクタも検討したが、この work で確立してきた
  「状態を書き換える箇所にフックを置く」という設計方針（D15/D17/D19 と同じ考え方）
  に揃え、可視性の判定と切り替えを1箇所（`syncSlotsVisibility`）に集約する方を
  選んだ。`.slot-side` 見出し自体を `openComposer()`/`renderThread()` の中へ
  移して「コンテンツに紐づけて生成する」案も検討したが、レビュー中に会話が既存の
  スレッドと新規コンポーザーの両方に及ぶ場合（両方が同時に存在しうる）に見出しを
  二重生成しない設計が煩雑になるため、既存の「見出しは常に1つ、表示だけ切り替える」
  構造を保つ方が単純だった。
- **検証**: playwright-core で11アサーション。split 表示でコメントが1件も無い
  状態では `.slots`（`.slot-side` を含む）が全1195個中0個も可視でないこと、片側の
  「+」で入力欄を開くとそのときだけ「変更前」ラベルと入力欄が見えること、
  「閉じる」で確定せずに閉じると再び不可視に戻ること、コメントを確定すると
  スレッドが残るぶん閉じても表示され続けること（かつ他の無関係な行は不可視の
  ままであること）を確認した。`python3 -m unittest`（140件）も green のまま。
- **影響**: `templates/app.js`（`renderThreads()`/新設 `syncSlotsVisibility()`/
  `openComposer()`/`closeComposer()`）、`templates/style.css`（死んでいた
  `.row.split .slots:empty` ルールの削除）。
