# レビュー記録

## タスク点検ログ（coding 工程内・「3.3」(b)）

- [nit][conv:-] `vscode/package.json:45` `test:unit` の `node --test "out/test/unit/*.test.js"` はグロブを Node 自身が
  展開するため Node 21 以上が要る（design.md の `node --test out/test/unit/` はディレクトリ指定で、Node 24 では
  失敗する）/ 対応: 修正済（T1）——開発に要る Node の版（22 以上）を README（T11）に書く。`engines.node` は
  拡張の実行環境（VSCode 同梱の Node）と紛らわしいので足さない。design との違いは decisions.md D13 に残す。
- [should][conv:-] `vscode/test/unit/minimalEdit.test.ts` 後ろ側（end）の境目の調整（`minimalEdit.ts:32-35`）を確かめる
  テストが無く、その while を消しても全件通った（点検が変異で実証。`"x\r\n"→"x\n"` で end が旧文の CRLF の間に来る）/
  対応: 修正済（T3）——`roundTrip` で旧文の start/end・新文の境目が割れていないことを毎回確かめ、`"x\r\n"→"x\n"`・
  `"a\u{1F600}"→"a\u{1F200}"` を足し、長さ 3 までの全組み合わせを回す。end の調整を消すと 3 件、新文側の確認を消すと
  2 件が落ちることを確認した。
- [nit][conv:-] 新文側の境目の確認（`minimalEdit.ts:24, 33` の `unsafeCut(newText, …)`）を確かめるテストが無い
  （`"a\rb"→"a\r\nb"`）/ 対応: 修正済（T3）——上と同じ。
- [nit][conv:-] `vscode/test/unit/viewerHtml.test.ts:36-37`「JS の中の "<script" は書き換えない」は件数の比較だけで、
  行頭でない `<script` が 0 件でも通ってしまう（今は `app.js` のコメント 1 件に頼っている）/ 対応: 修正済（T2）——
  `inner >= 1` を確かめ、手書きの小さな入力（CRLF・コード中の `"<script"`・行頭でないタグ）のテストを足した。
- [should][conv:-] `vscode/src/sync.ts` 書いている途中（`await applyText`）に `dispose()` されると、破棄のあとに ack／conflict を
  送り、警告も出していた（`disposed` をジョブの開始時にしか見ていない。点検が手順を実行して再現）/ 対応: 修正済（T4）——
  `await` から戻った直後と `showCurrent` で `disposed` を見る。途中で破棄する unit テスト（書けた／書けなかった）を足した。
- [nit][conv:-] `vscode/src/sync.ts` 書き込みが例外のとき警告が 2 回出る（例外の文言と「書き込めませんでした」）/
  対応: 修正済（T4）——1 つにまとめ、テストは `=== 1` で縛った。
- [nit][conv:-] `templates/ui.js` 「自動」のとき VSCode の配色を当てるのは `UI.init()`（DOMContentLoaded 後の `boot`）なので、
  WebView の `prefers-color-scheme` と VSCode の配色が違うと、起動直後に一瞬だけ OS 側の配色が見えうる / 対応: 許容（T8）
  ——HTML 版にも同じ種類の一瞬（`templates/page.html:8` のコメントの「app.js の起動を待つと一瞬明るく光る」）があり、
  直すには `page.html` に `<body>` 直後のスクリプトを足すことになる（design で `page.html` は変えないと決めた）。
  実害は起動の一瞬の配色だけ。e2e で配色の追従そのもの（切り替えでその場で変わる）は確かめる。
- [nit][conv:-] `templates/page.html:142` の書き出し画面の案内「ダウンロードするか、下の内容をコピーして…」が、VSCode では
  外した「ダウンロード」を指したまま / 対応: 修正済（T7）——`wireHost()` で案内をコピーだけの文言（保存は `.dreview` 自体・
  `Ctrl+S`）に差し替える。
- [must][conv:-] `templates/app.js` `bundleText` の正規表現リテラルに U+2028 / U+2029 が生の文字で入り（書き込みに使った道具が
  `\u2028` をその文字に変えていた）、JS では行終端文字なので `app.js` 全体が構文エラーになり、HTML 版も VSCode 版も動かなく
  なっていた。`/^\uFEFF/` にも生の BOM が入っていた。Python の unittest 143 件はこれを検出できなかった（点検が `node --check`
  と実ブラウザで再現）/ 対応: 修正済（T6）——エスケープで書き直し、再発防止に Python の unittest へ「テンプレートに生の
  U+2028/U+2029/U+FEFF が無い」（node 不要）と「`node --check` で構文が通る」（node があるときだけ）を足した。
- [should][conv:-] `templates/app.js` `onHostText` 自分の編集への返事の本文が送った全文と同じだと採用せずに戻るので、返事待ちの間に
  重ねた記録の変更が送られないまま残る（点検が手順で再現）/ 対応: 修正済（T6）——`onHostText` の最後で必ず `sendHostEdit()` を
  呼ぶ（記録が表示中の文書と違うときだけ送られる）。
- [should][conv:-] `templates/app.js` 送る記録は `canonicalRecord` が id を r1.. / t1.. / c1.. に振り直すので、文書を採用し直すと
  画面が id で覚えているもの（編集中のレビュー・畳んだスレッド・返信や編集の下書きの鍵）が別のものを指し、「保存する」で
  別のレビューを上書きしうる（点検が手順で再現）/ 対応: 修正済（T6）——`canonicalRecord(keepIds)` を足し、文書へ書くときは
  id を振り直さない（decisions.md D14）。HTML 版の書き出しは今どおり振り直す。
- [should][conv:-] `templates/app.js` `validateBundle` は浅い検査なので、通っても描画で例外になるバンドルがあり、その例外で
  `hostRecord = null` のまま知らせも無く止まる（点検が再現）/ 対応: 修正済（T6）——採用を `adoptHostBundle` に切り出して
  `try` で包み、例外は「壊れている」と同じ扱い（差分を空にして理由を出す）にした。
- [should][conv:-] `tests/test_diff_review.py` `test_host_messages_are_accepted_only_with_a_host` の `assertIn("if (!host) { return; }")` は
  通知の描画にある同じ形の行でも満たされ、`sendHostEdit` の防御を消しても通っていた（点検が変異で実証）/ 対応: 修正済（T9）——
  `sendHostEdit` の最初の文そのものを確かめる。変異（防御を消す）で落ちることを確認した。
- [should][conv:-] 同テストの `finditer` のループは、書き方が変わって一致が 0 件だと空回りして通る / 対応: 修正済（T9）——
  `"diff-review/text"` / `"diff-review/ack"` がそれぞれ 1 か所だけであることを先に確かめる。
- [should][conv:-] `test_theme_follows_vscode_only_when_its_classes_exist` の `assertIn("return null;")` は先頭の早期 return でも満たされ、
  最後の `return null` を `return "dark"` に変えても通っていた（HTML 版まで暗くなる変異）/ 対応: 修正済（T9）——関数の最後の文が
  `return null;` であることを確かめる。変異で落ちることを確認した。
- [nit][conv:-] `acquireVsCodeApi` の呼び出し数の数え方 `ln.split("//")[0]` は文字列中の `https://` で切れ、同じ行の 2 回目の呼び出しを
  見落とす / 対応: 修正済（T9）——空白の後ろの `//` からだけ落とす。
- [nit][conv:-] 生の U+2028 等の検査は `assertNotIn` がテンプレート全体を失敗メッセージに出す（約 148KB）/ 対応: 修正済（T9）——
  位置だけを出す。
- [should][conv:-] e2e（`vscode/test/e2e/run.ts`）入力欄の Ctrl+Z の検査が、文書に元に戻せる編集がまだ無い時点で行われ、漏れても
  失敗し得なかった / 対応: 修正済（T10）——保存の後（元に戻せる編集がある時点）へ移し、値が `""`・未保存にならない・スレッド数が
  変わらない、を確かめる。
- [should][conv:-] e2e AC8 はスクロールしていない・現在行が無いときに素通りしうる / 対応: 修正済（T10）——前提（現在行がある・
  スクロール量 > 0）を確かめてから比べる。
- [should][conv:-] e2e AC10 は違反の検出が空振りでも 0 件で通り、陽性対照は NOTE を書くだけだった / 対応: 修正済（T10）——陽性対照で
  違反を検出できなければ失敗にする。コンソールの出どころ（location）が空で届くと分かったので、ビューアの CSP だけが使う `'nonce-` の
  指令を含む違反を数える。eval の陽性対照は CDP の評価の外（正しい nonce のページスクリプトのタイマー）で試す（CDP の評価の最中は
  文字列の評価が許されることを実測）。
- [should][conv:-] e2e AC5 のバイト比較は保存が一度も起きないので失敗し得ず、「変更せずに保存」「変更して元に戻してから保存」を
  試していなかった / 対応: 修正済（T10）——その 2 つを実際に行ってバイト一致を確かめる。
- [should][conv:-] e2e 起動の途中で失敗すると VSCode が残る / 対応: 修正済（T10）——`launch` の失敗時と終了時に止めて終わるまで待つ。
- [should][conv:-] e2e のデバッグ用ポートが固定で、別の VSCode に繋がりうる / 対応: 修正済（T10）——空いているポートを取る。
- [should][conv:-] e2e のテスト用 VSCode がホームの `~/.vscode/argv.json` を書き換えていた（利用者の既存ファイル）/ 対応: 修正済（T10）
  ——`VSCODE_PORTABLE` で一時ディレクトリの中だけを使う（修正後の実行で `argv.json` の更新時刻が変わらないことを確認）。調査中の
  最初の試作が作った `~/.vscode/extensions/`（空の一覧だけ）は削除した。`argv.json` は以前からあったもので、中身は VSCode の既定の
  2 項目（書き換え前の内容は分からない）。
- [should][conv:-] e2e `openFile` は候補を確かめずに固定の待ち時間で Enter を押していた / 対応: 修正済（T10）——候補に同名の行が出るのを
  待って選び、タブが開いたことを確かめる。
- [should][conv:-] e2e `closeAllEditors` は保存確認を 1 回しか見ず、自動で「保存しない」を押して未保存を隠していた / 対応: 修正済（T10）
  ——確認を 2 秒待ち、未保存を想定していないのに確認が出たら失敗にする。
- [nit][conv:-] e2e CRLF の場面のバイト比較は必ず成り立つ / 対応: 修正済（T10）——「元は CRLF」を前提として確かめ、中身の検査
  （CR が無い・正規形）で判定する。
- [nit][conv:-] e2e AC1 の WebView かどうかの式の前半は一致しえない / 対応: 修正済（T10）——テキストエディタが無いこと＋ビューアの
  iframe が見つかること、で判定する。
- [nit][conv:-] e2e AC2 は固定値と比べていた / 対応: 修正済（T10）——Python でバンドルを読んだ件数・本文と比べる。
- [nit][conv:-] e2e AC-I4 は先頭行と比べておらず、k を確かめていない / 対応: 修正済（T10）。
- [nit][conv:-] e2e Ctrl+P の場面は WebView にフォーカスがあることを確かめていない / 対応: 修正済（T10）。
- [nit][conv:-] e2e AC14 は描画前の時刻を取っている / 対応: 修正済（T10）——変化のあとの最初の `requestAnimationFrame` の時刻にした。
  文書が未保存になるまでの時間（往復）は NOTE に残す（要件は「画面への反映」）。
- [nit][conv:-] e2e `viewerFrame` の可視性の判定は WebView を区別できない / 対応: 修正済（T10）——判定を外し、隠れた WebView は
  破棄される設定（`retainContextWhenHidden: false`）に依ることをコメントで明記。切り離された frame は除く。
- [nit][conv:-] e2e の一時ディレクトリが消えない / 対応: 修正済（T10）——VSCode の終了を待ってから消す（`DIFF_REVIEW_E2E_KEEP=1` で残す）。
- [nit][conv:-] e2e AC-I1 は古い候補を拾いうる / 対応: 修正済（T10）——「テキストエディタ」と「Diff Review」が揃うまで待つ。
- [should][conv:-] `vscode/README.md` の「同じ `.dreview` を 2 つのタブで開けない」は誤り。`CustomTextEditorProvider` では
  `supportsMultipleEditorsPerDocument` が効かず（`@types/vscode` の説明どおり）、VSCode は常に複数開ける。`extension.ts` の `false` も
  効果が無い / 対応: 修正済（T11）——記述を「分割して 2 つ開いたときの振る舞いは確かめていない」に直し、効かない指定を外した。
- [should][conv:-] README / SKILL.md の「外部変更に追従する」に「未保存の変更がある間は追従しない」前提が抜けていた / 対応: 修正済（T11）。
- [should][conv:-] README の「スクロール位置と現在行はそのまま」「入力欄はそのまま残る」は差分が同じときだけ / 対応: 修正済（T11）——
  条件と、差分が変わったら先頭から表示し直すことを書いた。
- [should][conv:-] SKILL.md の「読むだけのホスト（従来の口）」は、VSCode の WebView の中（`acquireVsCodeApi` がある）では画面が
  `text` / `ack` 以外を受けないので使えない / 対応: 修正済（T11）——WebView 以外のホスト向けと明記し、1b 節の表も直した。
- [nit][conv:-] SKILL.md のファイル表で `vscode/` の行が tests の 2 行の間に入っていた / 対応: 修正済（T11）。
- [should][conv:-] `templates/app.js` `canonicalRecord(true)`（文書へ書く記録）がスレッドを path / line で並べ替えるが、Python の
  `bundle_text` と `comment` は配列の順のまま（新しいスレッドは末尾）。CLI が書いたファイルは Python では正規形なのに、画面での
  最初の編集ですべてのスレッドの順が動き、「解決 → 未解決に戻す」のような打ち消し合う操作でもバイト列が元に戻らない（点検が
  手順で再現）/ 対応: 修正済（cross）——`keepIds` のときは並べ替えない（decisions.md D15）。
- [should][conv:-] `tests/test_diff_review.py` の `EditorHostBridgeTest` が、`boot` の分岐・`persist` の localStorage の形・D&D の門を
  押さえておらず、それらを逆にする変異でも 145 件が通った / 対応: 修正済（cross）——`test_host_only_paths_are_gated` を足し、
  3 つの変異がそれぞれ落ちることを確認した。
- [nit][conv:-] `templates/app.js` 編集の入力欄の鍵 `"edit:" + comment.id` は、Python がコメントの id をスレッドごとに振る（各スレッドの
  最初が c1）ので重なり、別のスレッドの下で編集欄が開く（既存の不具合。VSCode 版で id を振り直さなくなったため主経路になった）/
  対応: 修正済（cross）——返信の鍵と同じくスレッドの id を含める。

## ラウンド 1（独立レビュー）

- [should][conv:-] `templates/app.js:276, 2421` VSCode での最初の編集で、記録の `target` がバンドルの `target` に置き換わる
  （`canonicalRecord` が常に画面の差分の `target` を書く）。Python の `comment` / `resolve` は記録の `target` を保つので、別の差分に
  対する記録（`--import` で持ち込んだもの）を持つ `.dreview` では Python の書き方とバイト一致せず、「別の差分への記録」という情報も
  消えて `check --repo` の食い違いの警告が出なくなる（レビューが手順で再現。解決 → 未解決でも元に戻らない）/ 対応: 差し戻し（coding）
- [should][conv:-] `vscode/test/e2e/harness.ts:45-55` AC4 の検査（保存したファイルを読んで `bundle_text` で作り直して比べる）は整形の
  正規性しか見ず、files・target・触っていないスレッドが保たれたかを見ない（上の不具合も通る）/ 対応: 差し戻し（coding）
- [should][conv:-] `templates/app.js` 同期の画面側（`sendHostEdit` / `onHostAck` / `onHostText` / `applyHostText`）の、すれ違い・返事のあとの
  送り直し・返事待ち・版だけ進む・壊れている間の書き込み、を確かめる自動テストがリポジトリに無い（D11 の「画面側は e2e で」が
  果たされていない。スクラッチの検証だけ）/ 対応: 差し戻し（coding）
- [nit][conv:-] `templates/app.js:2282, 2297` 提出・更新のあとの通知が VSCode でも「JSON を書き出して渡してください」のまま / 対応: 差し戻しで直す
- [nit][conv:-] `templates/app.js:2469` 「同時に変更された」のバナーがあとで書けても消えず、今の問題のように残る / 対応: 差し戻しで直す
- [nit][conv:-] `SKILL.md:479` `ack` の説明が「書けたとき」だけで、全文が既に同じときも `ack` を返すこと（`sync.ts`）が書かれていない /
  対応: 差し戻しで直す
- [nit][conv:-] `tests/test_diff_review.py` `EditorHostBridgeTest` の一部は字下げを含む複数行の文字列一致で、整形し直すだけで落ちる /
  対応: 許容——門の式を 1 文字でも変えたら落ちることが目的（タスク点検の変異で確かめた）。整形したらテストも直す。
- [nit][conv:-] test-result.md の AC10「信頼されていないワークスペースでも開ける」は `package.json` の宣言だけが根拠で、e2e は信頼を
  切って起動している / 対応: 差し戻しで直す（信頼を有効にした起動で確かめる）

判定: must 0 / should 3 / nit 5 → coding へ差し戻す。

### ラウンド 1 の指摘への対応（coding 差し戻し後）

- 記録の target（should）: 修正済——`adoptRecord` で記録そのものの `target` を覚え（`recordTarget`）、`canonicalRecord(true)` はそれを書く
  （無ければ差分の target）。`test:protocol` の「別の差分に対する記録」と e2e の「画面での解決は Python の resolve と同じバイト列」で、
  Python の `resolve` とのバイト一致・未解決に戻したときの元のバイト列への復帰を確かめる。修正を戻した画面で `test:protocol` が落ちる
  ことも確認した。
- AC4 の検査（should）: 修正済——e2e の AC4 に `preservedAndAppended`（schema・target・files・rich_enabled・記録の target・元のスレッドが
  変わらず、新しいスレッドは末尾だけ）を足し、上の Python の `resolve` とのバイト一致の場面を足した。
- 画面側の同期の自動テスト（should）: 修正済——`vscode/test/viewer/protocol.ts`（`npm run test:protocol`）。同梱の画面と本物の
  `SyncSession` を偽の文書でつなぎ、見るだけ・解決と戻す・別の差分の記録・すれ違い（知らせと消えること）・返事待ちの間の重ね書き・
  版だけ進む・元に戻す相当・壊れた文書、の 8 場面。
- 提出後の通知（nit）: 修正済——VSCode では「Ctrl+S で .dreview に保存されます」。
- 「同時に変更された」の知らせ（nit）: 修正済——次の編集が書けたら（`ack`）消す。
- SKILL.md の `ack`（nit）: 修正済——全文が既に同じだったときも返すと書いた。
- 信頼されていないワークスペース（nit）: 修正済——e2e の最後に、信頼を有効にした別の VSCode（制限モード）で開いて表示できることを確かめる。

## ラウンド 2（独立レビュー）

ラウンド 1 の修正（記録の target・AC4 の検査・`test:protocol`・nit 群）はすべて正しく、退行も無いと確認された（`recordTarget` を
target の無い記録・HTML 版の書き出し・`resetDraft`・/1 の記録・記録の無いバンドルへの最初のコメント・元に戻す・壊れた文書で点検。
`test:protocol` の各場面が本当にその順序を作っていることを、`sync.ts` / `app.js` の変異で確かめた）。

- [nit][conv:-] `templates/app.js:244-281, 415-447` 最初の編集で、触っていないスレッドもスキーマに無い項目が落ち、書き手の無いコメントは
  `unknown` になる（Python の `comment` / `resolve` は保つ。HTML 版の書き出しと同じ振る舞いで、この skill の書き手はそうした項目を作らない）/
  対応: 修正済——`vscode/README.md` の既知の制約に書いた（振る舞いは変えない）。
- [nit][conv:-] `vscode/test/viewer/protocol.ts` `onHostText` の最後の `sendHostEdit()`（返事の本文が送った全文と同じときに、重ねた変更を送る）を
  確かめる場面が無く、送り直しの場面は自分の前提（返事待ちの間に重ねたこと）を確かめていない / 対応: 修正済——場面を足し
  （その呼び出しを消した画面で落ちることを確認）、送り直しの場面に前提の検査を足した。`test:protocol` は 9 passed。
- [nit][conv:-] `schema.md:208-218`・`templates/app.js` のコメントが、`#bundle-data` / `postMessage(bundle)` を「エディタ拡張など」の口と
  書いたまま（VSCode の WebView の中では使わない）/ 対応: 修正済——iframe で載せる親ページ等の口と書き直した（コメントだけ。振る舞いは不変）。
- [nit][conv:-] `vscode/README.md:35` git は e2e だけでなく `test:protocol` にも要る（`tests/fixture_repo.py` が使う）/ 対応: 修正済。

判定: must 0 / should 0 / nit 4 → 通過（nit はすべてその場で直した）。

件数（ラウンドの通算。タスク点検ログは含めない）: must 0 / should 3 / nit 9。
