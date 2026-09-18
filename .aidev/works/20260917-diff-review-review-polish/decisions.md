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
