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

## D21: レビュー結果の入力画面（#submit-panel）も #help と同じフローティング表示にした

- **背景**: ユーザーから「レビュー結果の入力画面はヘルプ画面同様にポップアップにして
  ください」。D19 で `#help` をフローティング化した際と同じ問題——`#submit-panel` も
  `.panel`（文書の流れに乗る）のままで、開くと他の表示に影響していた——を
  `#submit-panel` にも適用する。
- **決定**: D19 で確立した `.modal`/`.modal-backdrop`/`.modal-head` の CSS をそのまま
  再利用し、`#submit-panel` に `.modal` クラスを追加、新設 `#submit-backdrop` を
  背後に敷いた。見出し行を `.modal-head` に変え、新設の ×ボタン
  （`#btn-submit-close-x`）を追加した（既存の下部「閉じる」ボタンは提出/取消の
  アクション行としてそのまま残す——モーダル右上の×とボタン行の「閉じる」は
  役割が違うので両方持たせて問題ない）。開閉を実際に書き換える3箇所
  （`startReview()`/`editReview()`/`"r"`キー分岐の開く側）をすべて新設
  `setSubmitOpen(open)` 経由にし、閉じる経路（ボタン・×・backdrop・Escape・`"r"`
  キーの閉じる側）は既存の `closeSubmitPanel()`（編集中のキャンセル処理を持つ）が
  内部で `setSubmitOpen(false)` を呼ぶ形に一本化した。`ui.js` の
  `syncTopbarHeight()` の対象 id からも `"submit-panel"` を外した。
  - **副次的に見つけて直した不具合**: `#help` と違い `#submit-panel` は開いた直後に
    `#review-body`（textarea）へ自動でフォーカスする。グローバルの Escape ハンドラは
    `isTyping()`（`<textarea>`/`<input>`/`contenteditable` を「入力中」とみなす）が
    真だと何もせずに戻るため、開いた直後は Esc がまったく効かなかった
    （「ヘルプ画面同様に」と約束する以上、これは新機能の一部として塞ぐ必要がある）。
    `#submit-panel` 自身に Escape 専用の `keydown` listener を追加して塞いだ。
- **理由・代替案**: `isTyping()` 自体を「Escape だけは常に通す」ように緩める案も
  検討したが、影響範囲がアプリ全体のキーボード処理（`c`/`f`/`e`/`s` 等、他の
  入力欄でも横断的に効く）に及び、この work のスコープを超える。`#submit-panel`
  というこの1箇所にだけ listener を足す方が影響範囲が閉じている。
  「`"r"` キーでの閉じるトグルも直すべきか」を検証中に検討したが、`isTyping()` は
  `<input>` を型を問わず（ラジオボタン含む）「入力中」とみなすため、開いた直後の
  ほぼ全ての操作可能要素（textarea・ラジオ）でこの経路が塞がれており、キー操作表の
  約束も「開く」としかしていない（「閉じる」トグルは謳っていない）。これは
  この work と無関係な既存の性質と判断し、手を入れなかった。
- **検証**: playwright-core で20アサーション。フローティング化・`.shell` の高さ不変・
  ×/backdrop/Escape/既存の下部「閉じる」ボタン・`"r"`キーそれぞれでの開閉・
  実際にレビューを提出して一覧に載ること・提出後も開いたままなこと（既存仕様、
  変更していないことの確認）・編集モードでも同じ挙動になること、を確認した。
  `"r"` キーについては、フォーカスが textarea にある間は文字として "r" が入力される
  のが正しい挙動であること（`isTyping()` ガードが機能していること）も明示的に
  確認し、閉じるトグルの確認はボタンへフォーカスを移した状態で行った。
  `python3 -m unittest`（140件）も green のまま。
- **影響**: `templates/page.html`（`#submit-backdrop`・`.modal-head`・
  `#btn-submit-close-x`）、`templates/style.css`（既存の `.modal` 系クラスを再利用、
  追加ルール無し）、`templates/app.js`（新設 `setSubmitOpen()`、`startReview()`/
  `editReview()`/`"r"`キー分岐/`closeSubmitPanel()`/`wire()` の更新、`#submit-panel`
  への Escape listener 追加）、`templates/ui.js`（`syncTopbarHeight()` の対象 id）、
  `tests/test_diff_review.py`（`WRITE_UI` タプル）。

## D22: 「レビューを開始」ボタンのラベル固定化、JSON書き出し画面のフローティング化、
  submit-panel/export-panel の拡幅

- **背景**: ユーザーから3件の要望（後半2件は同じ会話の中で連続して届いた）。
  (1) 「レビューを開始ボタンを一度クリックすると、それ以降レビュー結果を入力ボタンに
  変わりますが、特に開始した状態自体を記録している訳でもなく、記録する必要も
  あまりないので、レビュー結果を入力で表現を固定して構いません」。
  (2) 「JSONを書き出すも、ヘルプ表示同様にポップアップにしてください」（D19/D21 と
  同じ形を `#export-panel` にも適用してほしい）。
  (3) 実装中に届いた追加要望: 「レビュー結果入力のポップアップ画面のサイズが
  小さかったので大きくしてください。同じサイズでjson書き出しも表示して」。
- **決定**:
  (1) `reviewStarted` 変数を完全に削除した（`updatePendingCount()`/`startReview()`/
  `submitReview()` から参照・代入を全て除去）。`pending-count` の
  「（レビュー中）」サフィックスも道連れで削除（`reviewStarted` 専用の表示だった
  ため、その概念自体を無くす以上残す理由が無い）。`#btn-start-review` の表示は
  `page.html` に静的に「レビュー結果を入力」と書き、JS 側の textContent 切り替えを
  削除した。ボタンは実質「`#submit-panel` の開閉トリガー」という disclosure
  ボタンでしかなくなったので、意味の合わない `aria-pressed`（「レビュー中」を
  表していた）を `aria-expanded`（`#btn-help-open` と同じ型）に差し替え、
  `setSubmitOpen()` がその同期も担うようにした。
  (2) D19/D21 で確立した `.modal`/`.modal-backdrop`/`.modal-head` をそのまま
  `#export-panel` に適用。新設 `#export-backdrop`、`.modal-head` ＋新設 ×ボタン
  （`#btn-export-close-x`）、新設 `setExportOpen(open)`（`#btn-export-open` の
  `aria-expanded` も同期）。`openExport()` は開いた直後に readonly な
  `#export-text` （textarea）へフォーカス＋選択するため、`#submit-panel` と同じ
  理由（`isTyping()` ガード）で Escape が効かなかった——`#export-panel` 専用の
  Escape listener で塞いだ。グローバルの Escape ハンドラの該当行
  （`showPanel("export-panel", false)`）も `setExportOpen(false)` に差し替え、
  backdrop の状態が経路によらず必ず揃うようにした。`ui.js` の
  `syncTopbarHeight()` の対象からも `"export-panel"` を外した（`#banners` のみ残る）。
  (3) `.panel.modal` に `.modal-lg`（`max-width: 800px`）という追加のモディファイア
  クラスを新設し、`#submit-panel`/`#export-panel` にだけ付けた。`#help`
  （表組み中心で幅を必要としない。ユーザーからの言及も無い）は既定の560pxのまま
  据え置いた。
- **理由・代替案**: (1) は「ラベルだけ固定文字列にする」だけの対症療法も検討したが、
  `reviewStarted` 変数自体がその表示以外に一切使われておらず（`submitReview()` の
  可否判定にも関わらない、純粋な表示専用フラグ）、変数を残したまま参照だけ削れば
  「更新されるが読まれない」デッドコードになる。変数ごと削除する方が素直。
  `aria-pressed`→`aria-expanded` の切り替えは、テキストラベルは固定でも「押されて
  いる/いない」という意味論自体が既に無くなっている（ボタンはトグル開閉であって
  「オン/オフの状態を持つトグルスイッチ」ではない）ため、放置すると視覚的には
  何も変わらないのに支援技術には無意味な状態変化が伝わる不整合が残る（D17 の
  `aria-valuenow` の教訓と同種）。
  (2) は D19/D21 の設計をそのまま踏襲するのが最も一貫性が高い。
  (3) は `.panel.modal` 自体の既定値を上げる案（3画面とも一律で広げる）も検討したが、
  ユーザーの要望は明確に「レビュー結果入力」「JSON書き出す」の2つを指しており、
  `#help` を広げる根拠が無い。モディファイアクラスで対象を絞る方が要望に忠実。
- **検証**: playwright-core で27アサーション。ラベルが起動直後から一貫して
  「レビュー結果を入力」であること（開閉・コメント追加のいずれでも変わらない）、
  「（レビュー中）」表示が消えたこと、`aria-expanded` が開閉に追従すること、
  `#export-panel` のフローティング化（`.shell` の高さ不変・×/backdrop/Escape/
  既存の下部「閉じる」ボタンでの close・書き出し内容の非回帰）、`#submit-panel`/
  `#export-panel` が800pxで揃い `#help` は560pxのまま変わらないこと、を確認した。
  **テスト作成中に見つけた誤り（実装ではなくテスト側）**: 一度モーダルを開くと
  `.modal-backdrop`（z-index:30）が `.topbar`（z-index:5、別のスタッキング
  コンテキスト）ごと覆うため、同じトリガーボタンをマウスで再クリックして閉じる
  ことは元々できない——これは backdrop 付きモーダルとして正しい・意図した挙動
  （閉じる手段は ×/backdrop クリック/Esc/下部の「閉じる」）であり、実装の不具合
  ではない。テスト側でトリガーボタンの再クリックに依存していた箇所を実際の
  close 経路（×ボタン等）に修正した。`python3 -m unittest`（140件）も green。
- **影響**: `templates/page.html`（`#btn-start-review` の静的ラベル・
  `aria-expanded`、`#export-backdrop`・`.modal-head`・`#btn-export-close-x`、
  `#submit-panel`/`#export-panel` への `.modal-lg`）、`templates/style.css`
  （`.modal-lg` 新設）、`templates/app.js`（`reviewStarted` 削除、
  `updatePendingCount()`/`startReview()`/`submitReview()`/`setSubmitOpen()` の
  更新、新設 `setExportOpen()`、`openExport()`/`wire()`/グローバル Escape
  ハンドラの更新）、`templates/ui.js`（`syncTopbarHeight()` の対象 id）、
  `tests/test_diff_review.py`（`WRITE_UI` タプル）、`SKILL.md`（説明文の更新）。

## D23: ヘルプ画面も800pxに拡幅、投稿済みコメントの編集機能を追加

- **背景**: ユーザーから3件届いた。(1)「ヘルプ画面も広げて」——D22で
  `#submit-panel`/`#export-panel` だけ800pxに広げたが、`#help` にも同じ要望が来た。
  (2)「一度投稿したコメントは取り消しか返信しか選択できませんが、編集出来るように
  してください」。(3)「コメント入力後、未提出と表示されますが、いつ表示が
  消えるのですか？」——これは変更要望ではなく質問。仕組みを調べて回答した
  （下記「理由・代替案」）。コード変更はしていない。
- **決定**: (1) `#help` にも `.modal-lg` を付けた結果、`.modal` を使う3画面
  （`#help`/`#submit-panel`/`#export-panel`）が**すべて**800pxになったため、
  個別に広さを変える理由が無くなった。`.modal-lg` モディファイアクラスを廃止し、
  `.panel.modal` の `max-width` 自体を800pxへ変更、3画面から `.modal-lg` クラスを
  外した（D22 で「`#help` だけ据え置く」ために導入した区別自体が、この要望で
  意味を失ったため）。
  (2) `renderComment()` の行アクションに「編集」ボタンを追加した（提出済み
  （`review_id` 付き）でも表示する——取り消しだけ提出済みでは出さない既存仕様は
  そのまま）。押すと `toggleEditComposer()`/`openEditComposer()`（新設。
  `openComposer()` とは別経路）が、そのコメント専用の入力欄（既存の本文・重大度で
  事前入力）を開く。「保存する」で `comment.body`/`comment.severity` を直接
  書き換える（`review_id`・`in_reply_to`・`author` は触らない——編集しても
  提出状態は変わらず「未提出」バッジも付かない）。「閉じる」（またはEsc）は
  `closeComposer()` をそのまま再利用し、保存せずに破棄する。
- **理由・代替案**: (1) は `.modal-lg` を残したまま3箇所に付ける案もあったが、
  「一部だけ広い」という前提が崩れた以上、モディファイアクラスを保つ理由が無く、
  基底クラスへ統合する方が素直（死んだ区別を残さない）。
  (2) は「取り消してから新しく書き直す」を代替案として検討したが、提出済み
  コメントは `review_id` があるため取り消しボタン自体が現状出ない（提出後は
  一切直せない）——ユーザーの要望はまさにこの「提出後に直せない」点を指しており、
  代替にならない。`openComposer()` を条件分岐で拡張して編集モードを持たせる案も
  検討したが、下書き（drafts）の扱い・「説明として残す」チェックボックスの要否・
  ボタン文言（コメントする/返信する→保存する）が編集では意味を持たず、条件分岐が
  増えてかえって読みにくくなるため、既存の小さな専用関数を並べる流儀
  （`closeSubmitPanel`/`cancelEditReview` 等）に倣い別関数にした。
  「編集しても未提出扱いに戻す」案（提出済みコメントを直したら再提出が必要、
  という設計）も検討したが、要望は「文言を直したい」であって「再度レビュー
  ワークフローに乗せたい」ではないと判断し、`review_id` は変更しないことにした。
  (3) の仕組み: 「未提出」は `comment.review_id === null` の間だけ表示される。
  これが埋まるのは `submitReview()`（「レビュー結果を入力」→ 提出する）が
  そのとき溜まっている未提出コメント全部に新しいレビューの `review_id` を
  一括で割り当てたときだけ。つまり「未提出」表示は、個々のコメントごとに
  自動で消えるものではなく、**「レビュー結果を入力」から明示的に提出する**まで
  消えない設計（GitHub の PR レビューと同じ、下書きコメント→まとめて1つの
  レビューとして提出、というモデル）。ユーザーへはこの説明を回答するに留め、
  UI 側の変更（例: バッジへの説明テキスト追加）は要望されていないため行っていない。
- **検証**: playwright-core で12アサーション。`#help` が800pxになったこと、未提出
  コメントに「編集」ボタンが出て本文・重大度が事前入力された状態で開くこと、
  保存すると本文・重大度（`.thread-head` 側の表示も含め）が反映されること、
  提出済みコメントでも「取り消し」は出ないが「編集」は引き続き使え、編集しても
  「未提出」バッジが付かないこと、「閉じる」で保存せず閉じると変更が破棄される
  こと、を確認した。readonly ビルドでは「編集」ボタンが1件も無いことも確認した。
  `python3 -m unittest`（140件）も green のまま。
- **影響**: `templates/page.html`（3画面から `.modal-lg` を除去）、
  `templates/style.css`（`.modal-lg` 廃止、`.panel.modal` の `max-width` を
  800pxへ）、`templates/app.js`（`renderComment()` に編集ボタン・専用
  composer-slot、新設 `toggleEditComposer()`/`openEditComposer()`）。

## D24: 折りたたんだコメント同士の縦の余白が二重に効いていた不具合を修正した

- **背景**: ユーザーからスクリーンショット付きで報告。「全体コメント、ファイル
  コメント、行コメントは複数入力できますが、コメント間の余白が大きすぎて
  スペースを無駄にしている」。実測すると、折りたたんだ `.thread` 同士の間隔が
  24px あった。原因は `.threads { display: grid; gap: 8px; }`（親のグリッドが
  既に縦の間隔を8px確保している）に加えて `.thread { margin: 8px 12px; }`
  （各スレッド自身も上下8pxのマージンを持つ）が**二重に**効いていたこと——
  グリッドの子要素どうしのマージンは gap と相殺されない（通常のブロック要素の
  隣接マージンのような「マージンの相殺」が、グリッドコンテナの直接の子には
  起きない）ため、8（前の要素の margin-bottom）+ 8（grid gap）+ 8（次の要素の
  margin-top）= 24px になっていた。
- **決定**: `.threads > .thread { margin-top: 0; margin-bottom: 0; }` を追加し、
  `.threads` グリッドの直接の子である `.thread` の上下マージンだけを打ち消した
  （左右のマージンは維持——横方向はグリッドの gap ではなく `.thread` 自身の
  マージンで確保しているため）。`.thread` 自体の `margin: 8px 12px` は変更して
  いない——`renderOrphans()` が作る `.orphans`（グリッドではない素の入れ物）の
  中の `.thread` はこの対象外（`.orphans > .thread` は `.threads > .thread` に
  マッチしない）で、引き続き自分のマージンだけで間隔を作る必要があるため。
- **理由・代替案**: `.thread` 自体の `margin` を丸ごと消す案も検討したが、
  `.orphans` 内の `.thread` の間隔がそれ1つに依存しており、消すとそちらが
  壊れる。グリッドの `gap` を無くして `.thread` のマージンだけに頼る案も
  検討したが、`.threads` は他の場所（split 表示の `.slots` 内側など）でも
  使われており、影響範囲を `.thread` 側だけに絞れる今回の直し方の方が安全。
- **検証**: playwright-core で5アサーション。全体・ファイル・行のそれぞれで
  2件コメントを実際に投稿し、折りたたんだ `.thread` 同士の間隔が実測8px
  （グリッドの gap のみ）になったことを確認した（修正前は24pxだった）。
  `.orphans`（位置不明の指摘）内の `.thread` は今回の対象外であることも、
  `--import` で位置不明な指摘を埋め込んだ別ビルドで実測し、独自の間隔
  （35px前後。段落ラベルとマージンによるもので今回の変更と無関係）が
  変わっていないことを確認した。`python3 -m unittest`（140件）も green のまま。
- **review 工程の独立点検で1件の should 指摘**: 最初の実装
  （`.threads > .thread { margin-top: 0; margin-bottom: 0; }` と一律に打ち消す形）
  は、`.threads` の前後（`#overall` の見出し行と最初のスレッドの間など。
  `.threads` 自身は padding を持たない）の余白まで消してしまう副作用があった
  （指摘時点では未検証だった箇所）。実測すると、`#overall` の見出し行と最初の
  スレッドの間隔が0pxになっていた（修正前は8px）。`:not(:first-child)`/
  `:not(:last-child)` を使い、**隣接する2要素の間だけ**を打ち消す形に直した
  （最初の要素は自身の margin-top を、最後の要素は自身の margin-bottom を
  保つ）。修正後、見出し行と最初のスレッドの間隔が8pxに戻ったことを実測で
  確認した（このアサーションを含め計5件）。
- **影響**: `templates/style.css` のみ（`.threads > .thread` 関連ルール）。

## D25: 展開コントロールの帯とハンク見出し（@@ ... @@）を GitHub と同じく1本の帯に統合した

- **背景**: ユーザーから「ソース差分の展開ボタンクリック後も差分量表示の行が残ったままに
  なっています」と報告（スクリーンショット付き）。この報告を受け、playwright-core で
  実ブラウザ上の展開ボタンを網羅的に（単独クリック・混在方向クリック・実際の生成物
  37箇所すべての隙間を「すべて表示」で開き切る・ファイルの折りたたみ/展開・split⇔
  unified 切り替え・rich⇔source 切り替えを挟む、等）繰り返し試したが、`.expander`
  （展開コントロールの帯）が消えずに残る事象そのものは一度も再現できなかった
  （すべて正しく DOM から除去されることを実測で確認済み）。
  ユーザーへ「具体的にどの部分が残るか」を尋ねたところ、「『…N行』の帯自体が消えずに
  残る」との回答を得たが、それでも再現には至らなかった。続けてユーザーから
  「GitHubのように展開ボタンのある帯に@@表示を付けると帯が残る事象が根本的に
  発生しなくなるので対応して」と、原因追及ではなく**構造そのものを変える**提案が
  届いた（GitHub のスクリーンショット付き: 展開アイコンと `@@ ... @@` 見出しが
  1本の帯にまとまっている）。
- **決定**: `fillFileBody()` のハンク描画ループを変更し、各ハンクの**直前の隙間**
  （`gaps[index]`）とそのハンクの見出し（`hunk.header`）を`renderGap(body, file, gap,
  index, headerText)` 1回の呼び出しにまとめた。`renderGap` は、隙間が残っている
  （`remaining > 0`）ときは `expander(..., headerText)` へ見出しテキストを渡し、
  `expander()` が展開コントロール（残り行数・↑/↓/すべて表示ボタン）の**同じ行の
  末尾**に見出しテキスト（新設 `.expander-hunk-head`）を追加で差し込む。隙間を
  使い切った（`remaining <= 0`）とき・そもそも隙間が無いときは、従来どおり独立した
  `.hunk-head` を出す。末尾（最後のハンクより後ろ）の隙間には合流できる次の見出しが
  無いため、`headerText: null` を渡し、従来どおり独立した帯のままにした。
- **理由・代替案**: 「なぜ残るのか」を突き止める（要求されたデバッグ）方向は、
  再現できない以上これ以上のログ追加や当て推量での修正は誤った箇所を直しかねないため
  断念した。ユーザー提案の「1本の帯にする」構造変更は、**そもそも2本の別要素が
  存在しなくなる**ため、仮に何らかの経路で「展開コントロール側だけ描画され見出しが
  出ない」ような取りこぼしが起きていたとしても、この変更後は「展開コントロール＋
  見出しがセットの1個の要素」か「見出しだけの1個の要素」のどちらか一方しか存在し
  得ず、"展開コントロールだけが単独で残る" という見た目のクラス自体が構造的に
  作れなくなる。GitHub という広く使われている確立されたパターンに合わせる副次効果
  もある。
- **検証**: playwright-core で5アサーション。実際の生成物で、隙間の残っている
  ハンクの帯が`.expander-hunk-head`（ハンク見出し）を内包した1本の帯になっている
  こと（34箇所で確認）、統合された帯の直後に独立した `.hunk-head` が重複して
  続かないこと、対象の帯を「すべて表示」で開き切ると帯自体が消え、同じ見出し
  テキストを持つ**通常の** `.hunk-head` が正確に1個だけ残ること、を確認した。
  ライト/ダークどちらのテーマでも見た目を目視確認した（スクリーンショット）。
  `python3 -m unittest`（140件）も green のまま。
- **影響**: `templates/app.js`（`fillFileBody()`/`renderGap()`/`expander()`）、
  `templates/style.css`（新設 `.expander-hunk-head`）。

## D26: 隙間を展開しきった後、ボタンの無い @@ 見出しだけが残っていたのを、
  見出しごと消すように直した（D25 のすぐ後の追加報告）

- **背景**: D25（展開コントロールと @@ 見出しの帯を1本化）のマージ直後、ユーザーから
  「展開後、展開ボタンのない@@の行だけ残りました」と報告。スクリーンショットを
  確認すると、D25 の意図どおり——隙間を使い切ると統合されていた帯が「ボタンの無い
  通常の `.hunk-head`」に**正しく**切り替わっていた（D25 のテストが検証していた
  とおりの状態）。ただし、それはユーザーが望む最終形ではなかった: 「ボタンが無い
  @@ 行」自体が、GitHub の実際の挙動と食い違っていた——GitHub では、2つのハンクの
  間の隙間を全部展開すると、その2つは実質1つの連続したコードとして見え、境目の
  `@@ ... @@` 自体が表示から消える（ハンクが事実上1つに繋がったことを反映する）。
- **決定**: `renderGap()` から、隙間を使い切った（`remaining <= 0`）ときに
  `.hunk-head` を単独で出していた分岐を削除した。隙間（`gap` が非 null）を
  ユーザーが展開しきった場合は、見出しを**一切出さない**——該当ハンクの行
  （追加・削除・文脈）はそのまま続けて表示され、コード自体は途切れない。
  一方 `!gap`（そもそも隙間の無い、元の差分の時点で隣接しているハンク。
  ユーザーが埋めたものではない）は対象外とし、これまでどおり常に見出しを出す。
- **理由・代替案**: `@@ -a,b +c,d @@` は本来「ここで行番号が飛ぶ（隙間がある）」
  ことを示すための印であり、ユーザーが隙間を全部埋めた時点で、示すべき飛びが
  無くなる。見出しを「ボタンだけ無い版」として残す案（D25 で実装した状態）は、
  意味を失った印をそのまま残す点で不完全だった。`!gap` のケースまで一律に
  消してしまう案も検討したが、そちらはユーザーが起こした変化ではなく元の差分
  構造そのものなので対象外とした（区別を保つ）。
- **検証**: playwright-core で6アサーション。展開前は独立した `.hunk-head` が
  存在しないこと（統合帯に含まれているだけ）、「すべて表示」で展開しきると
  統合帯が消えること、**展開後にボタンの無い `.hunk-head` が1件も残らないこと**
  （ユーザー報告の核心）、見出しテキスト自体がページのどこにも要素として
  存在しないこと、ハンク自身の行（216行）は引き続き正しく表示されること、
  `!gap`（未展開・隣接ハンク）の通常の見出し（29件）は影響を受けず変わらず
  表示されること、を確認した。実ブラウザのスクリーンショットで、展開前は
  `… 15 行 ↑20行 すべて表示 @@ -16,10 +16,15 @@` の統合帯、展開後はその
  見出しテキストがページ上に一切残らないことを確認した。
  `python3 -m unittest`（140件）も green のまま。
- **影響**: `templates/app.js`（`renderGap()`）のみ。

## D27: 残り行数が EXPAND_STEP（20行）以下のとき、「すべて表示」以外のボタンを
  出さないようにした

- **背景**: ユーザーから「展開する行が残り20行以下の場合、すべて展開以外の
  ボタンは表示しないようにして」との要望。`EXPAND_STEP`（1回のクリックで広がる
  行数）が20なので、残りが20行以下のときは「↑20行」を押しても「↓20行」を
  押しても「すべて表示」を押しても、結果は完全に同じ（1回で残り全部が開く）。
  選択肢が3つあるように見えて実質1つしか無いのは紛らわしい。
- **決定**: `expander()` に `var onlyAll = remaining <= EXPAND_STEP;` を追加し、
  `onlyAll` が真のときは「↑」「↓」ボタンをどちらも出さず、「すべて表示」だけを
  出すようにした（残り行数のラベル「…N行」はそのまま残す）。ハンク境界の有無
  （`index < hunks.length`/`index > 0`）による既存の出し分けは、`onlyAll` が
  偽のときの条件として維持した。
- **理由・代替案**: 「すべて表示」のラベルを状況に応じて「↑」「↓」どちらかの
  文言に変える案も検討したが、`onlyAll` のときは方向を問わず同じ結果になる
  （そもそも「どちらの方向に展開するか」という選択自体が意味を持たない）ため、
  「すべて表示」という中立な文言のまま1つに絞る方が実態と合っている。
- **検証**: playwright-core で、実際の生成物にある全38箇所の展開帯を走査し、
  残り20行以下（17箇所）ではすべて「↑」「↓」ボタンが1つも無いこと、残り21行
  以上（21箇所）では引き続き「↑」「↓」の少なくとも一方があることを確認した。
  さらに、残り23行の隙間を実際に1回クリックして残り3行まで縮めた直後、その場で
  「↑」「↓」ボタンが消え「すべて表示」だけになる遷移も実測した。ライトテーマの
  スクリーンショットで、小さい隙間（15行）は「すべて表示」のみ、大きい隙間
  （104行）は「↑20行」「すべて表示」が並ぶ、という見た目の違いも確認した。
  `python3 -m unittest`（140件）も green のまま。
- **影響**: `templates/app.js`（`expander()`）のみ。
