# テスト結果: レビュー操作性の改善（ツリー見た目・レビュー提出フロー・固定ヘッダー・コメント折りたたみ・通知ベル）

> **ラウンド18・最終**（D25（展開コントロールと@@見出しの帯を1本化）の直後、
> ユーザーから「展開後、展開ボタンのない@@の行だけ残りました」との追加報告を受けて
> 対応した後の検証。decisions.md D26）。ラウンド1〜17の内容は本ファイル末尾に残す。

## 実行したもの（ラウンド18・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（Python 側は無変更）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規6アサーション、すべて pass）**:
  1. 展開前は、対象の見出しテキストを持つ独立した `.hunk-head` が存在しないこと
     （統合帯の中にしか無いこと）
  2. 「すべて表示」で展開しきると、統合帯（`.expander`）自体が消えること
  3. **展開後、ボタンの無い `.hunk-head` が1件も残らないこと**（ユーザー報告の核心。
     D25 時点ではここが「ボタンだけ無い通常の見出し」として残ってしまっていた）
  4. 見出しテキスト自体（`.hunk-head`/`.expander-hunk-head` いずれの形でも）が
     ページのどこにも要素として存在しなくなること
  5. ハンク自身の行（追加・削除・文脈、216行）は引き続き正しく表示されること
     （見出しが消えてもコード自体は消えない）
  6. `!gap`（そもそも隙間が無い・元から隣接しているハンク、または未展開のハンク）の
     通常の見出し（29件）はこの変更の影響を受けず、従来どおり表示され続けること
  - 実ブラウザのスクリーンショットで、展開前は「… 15 行 ↑20行 すべて表示
    @@ -16,10 +16,15 @@」の統合帯として、展開後はその見出しテキストがページ上に
    一切残らないことを目視でも確認した。

- **再現の試行（対応前の調査。playwright-core で網羅的に実施）**:
  - 実際の生成物（37箇所の隙間）すべてを「すべて表示」で開き切り、`.expander` が
    全件正しく DOM から消えることを確認（再現せず）
  - 単一方向（↑のみ）の繰り返しクリック、混在方向（↓→↑）のクリックでの完全消費を
    それぞれ確認（再現せず）
  - 1箇所の大きな隙間（230行）を「↓20行」で12回段階的にクリックし、毎回ラベルが
    正しく減っていくこと・コンソールエラーが一切出ないことを1クリックずつ確認
    （再現せず）
  - ファイルの折りたたみ→再展開、split⇔unified切り替え、rich⇔source切り替え
    （"t"キー）を挟んでも、展開済みの隙間が再び現れないことを確認（再現せず）
  - ユーザーへ再現に必要な追加情報（ブラウザ・押したボタン・生成物そのもの）を
    尋ねたが、代わりに「GitHubのように帯を1本にまとめる」という構造変更の提案を
    受けたため、原因追及ではなくその対応へ切り替えた
- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（Python 側は無変更）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規5アサーション、すべて pass）**:
  1. 隙間が残っているハンクの帯が、展開コントロールとハンク見出し
     （`.expander-hunk-head`）を内包した1本の帯になっていること（34箇所で確認）
  2. 統合された帯の直後に、独立した `.hunk-head` が重複して続かないこと
  3. 対象の帯を「すべて表示」で開き切ると、帯自体が消え、同じ見出しテキストを
     持つ通常の `.hunk-head` が正確に1個だけ残ること
  4. ライト/ダークどちらのテーマでも見た目を目視で確認（スクリーンショット）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（Python 側は無変更）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規4アサーション、すべて pass）**:
  1. 修正前に、全体コメントを2件実際に投稿して折りたたんだ `.thread` 間の間隔を
     実測すると24pxだったことを確認（`.threads` の `gap`（8px）と `.thread`
     自身の上下マージン（8px×2）が二重に効いていたことの実証）
  2. 修正後、全体・ファイル・行それぞれで2件ずつコメントを実際に投稿し、
     折りたたんだ `.thread` 間の間隔が実測8pxになったことを確認
  3. `.orphans`（位置不明の指摘。`--import` で埋め込んで作った別ビルドで検証）
     内の `.thread` の間隔は今回の対象外であり、変わっていないことを確認
     （こちらはグリッドではない入れ物なので、`.thread` 自身のマージンに
     引き続き依存する設計）
  4. **（review 工程の指摘の修正後・追加）** `#overall` の見出し行（「全体への
     コメント」）と最初のスレッドの間隔が8pxのまま保たれていること
     （最初の実装は一律に上下マージンを0にしていたため、ここが意図せず
     0pxになっていた——`:not(:first-child)`/`:not(:last-child)` で隣接ペア
     だけを狙う形に直して解消）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（Python 側は無変更）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規12アサーション＋readonly
  ビルドでの1件の実測確認、すべて pass）**:
  1. `#help` が800pxに広がったこと（`#submit-panel`/`#export-panel` と揃ったこと）
  2. 未提出のコメントに「編集」ボタンが表示され、既存の本文・重大度が
     事前入力された状態で入力欄が開くこと
  3. 保存すると本文・重大度が反映され、重大度は `.thread-head` 側の表示
     （先頭コメントの重大度はそちらに出る既存仕様）にも反映されること
  4. 提出済みのコメントでは「取り消し」は出ないが「編集」は引き続き使えること
     （まさにユーザーが報告した制約の解消）
  5. 提出済みコメントを編集しても「未提出」バッジは付かない（`review_id` は
     変更しない設計どおり）こと
  6. 「閉じる」で保存せずに閉じると変更が破棄されること
  7. readonly ビルドでは「編集」ボタンが1件も存在しないこと

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（`ReadonlyTest.WRITE_UI` に
  `id="export-backdrop"`/`id="btn-export-close-x"` を追加）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規27アサーション、すべて pass）**:
  1. `#btn-start-review` のラベルが起動直後から一貫して「レビュー結果を入力」で
     あること（開閉・コメント追加を挟んでも変わらないこと）を確認
  2. `aria-expanded` がボタンの開閉に正しく追従すること（`aria-pressed` から
     切り替えたことの確認）
  3. `#pending-count` から「（レビュー中）」表示が消え、件数表示だけが残ること
  4. `#export-panel` が `#help`/`#submit-panel` と同じくフローティング表示
     （`position: fixed`）になり、開いても `.shell` の高さが変わらないこと
  5. `#export-panel` が ×・backdropクリック・Escapeキー・既存の下部「閉じる」
     ボタンのいずれでも閉じられること（Escape は、開いた直後に readonly な
     `#export-text` textarea へフォーカスが移る状態からでも効くことを確認——
     `#submit-panel` と同じ `isTyping()` の穴を専用 listener で塞いだ）
  6. 書き出される JSON の内容自体に変化が無いこと（回帰確認）
  7. `#submit-panel`/`#export-panel` の幅が800pxで揃い、`#help` は560pxのまま
     変わらないことを実測で確認
  - **テスト作成中に見つけた誤り（テスト側の問題であり実装の不具合ではない）**:
     一度モーダルを開くと `.modal-backdrop`（z-index:30）が `.topbar`
     （z-index:5、別のスタッキングコンテキスト）ごと覆うため、同じトリガー
     ボタンをマウスで再クリックして閉じることは元々できない。これは backdrop
     付きモーダルとして正しい挙動であり、テスト側の該当箇所を実際の close
     経路（×ボタン等）を使うよう修正した。

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（`ReadonlyTest.WRITE_UI` に
  `id="submit-backdrop"`/`id="btn-submit-close-x"` を追加）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規20アサーション、すべて pass）**:
  1. `#submit-panel` がフローティング表示（`position: fixed`）になり、開いても
     `.shell` の高さが変わらないことを確認
  2. ×ボタン・backdropクリック・Escapeキー・既存の下部「閉じる」ボタンの
     いずれでも閉じられることを確認（`#submit-backdrop` も一緒に隠れる）
  3. `"r"` キーで開くこと（回帰確認）。開いた直後は `#review-body`（textarea）へ
     フォーカスが移るため、その状態で `"r"` を押すと**文字として "r" が
     入力される**のが正しい挙動であることを明示的に確認（`isTyping()` ガードが
     引き続き機能している）。閉じるトグルは、フォーカスをボタンへ移した状態で
     `"r"` を押すことで確認した（ラジオボタンは `<input>` なので `isTyping()` に
     引っかかり、そこからは閉じない——これは今回の変更と無関係な既存の性質）
  4. 実際にレビューを1件提出すると `#review-list` に反映されること（提出後も
     パネルは開いたまま——既存仕様で変更していないことの確認）
  5. 一覧から「編集」を開いてもフローティング表示のまま同じ経路で閉じられること

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（Python 側は無変更）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規11アサーション、すべて pass）**:
  `git range 8b22f0c..HEAD` の実差分（diff-review-html 自身の変更を含む。split 表示で
  削除＋追加が対になる行が86件存在することを確認したうえで検証した）から生成した
  `out.html` を Chromium で開き、split 表示に切り替えて検証した。
  1. コメントが1件も無い状態で、`.slots`（`.slot-side` 見出しを含む）が
     全1195個中1つも可視でないことを確認（修正前は `.slot-side` を持つすべての行が
     常に可視で、86件×2行=172行分の余分な表示があった）
  2. 「+」ボタンで入力欄を開くと、そのときだけ「変更前」の見出しと入力欄が見える
  3. 「閉じる」で確定せずに閉じると、再び不可視に戻る
  4. コメントを確定すると、スレッドが残るぶん入力欄を閉じても表示され続ける
     （見出しの必要性がコメントの有無と一致することの確認）
  5. コメントを確定した行以外の無関係な行の `.slots` は、その間も不可視のままである
  - **注意**: 対象差分に diff-review-html 自身のソース（"変更前"/"変更後" という文字列を
    含むコード・コメント）が含まれるため、ページ全体のテキスト検索（`innerText()`）で
    「"変更前"が見えない」ことを確認しようとすると誤検出する（差分の中身として
    その文字列が表示されているだけで、UI のラベルとは無関係）。`.slot-side` 要素の
    可視性を直接見る形に検証方法を修正した。

## 実行したもの（ラウンド11・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（Python 側は無変更）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規18アサーション、すべて pass）**:
  `git range 8b22f0c..HEAD` の実差分から生成した `out.html` を Chromium で開いて検証した。
  1. `#btn-help-open` クリックで `#help`/`#help-backdrop` が表示され、`#help` の
     `position` が `fixed`（フローティング）になっていることを確認
  2. `#help` を開く前後で `.shell` の高さが変わらない（652px→652px。他の表示への
     影響が無くなったことの実測）
  3. ×ボタン（`#btn-help-close`）・backdrop クリック・Esc キーのそれぞれで閉じられ、
     閉じると `#help-backdrop` も一緒に隠れることを確認
  4. `btn-help-open` の `aria-expanded` が開閉に追従することを確認
  5. `?` キーでの開閉に回帰が無いことを確認
  6. 通知ベルを開くと、`#notif-panel` の高さが72px以上あり、`#notif-list .empty`
     （「通知はまだありません」）が最初の1回目から可視であることを確認（修正前は
     この要素自体が DOM に存在せず、`isVisible()` がタイムアウトしていた）
  - readonly ビルド（`--readonly`）でも `#help`/`#btn-help-close` が機能することを
    別途確認した
- **テスト作業中に見つけた副産物**: backdrop クリックのテストを画面左上隅
  （x:5, y:5）で行うと `#progress-track`（読了位置バー、`z-index: 200`）に
  クリックを奪われタイムアウトした。これはテストの座標選択の問題であり実装の不具合
  ではない（progress-track は画面最上部の高さ6pxの帯にのみ存在し、backdrop より
  前面にあるのは元々の設計どおり）。座標を (20, 100) に変更して解消した。

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 140 passed / 0 failed / 0 skipped（`ReadonlyTest.WRITE_UI` に `id="btn-reset-draft"` を
  追加し、通常ビルドで存在・readonly ビルドで不在の両方をカバー）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（新規11アサーション、すべて pass）**:
  `git range 8b22f0c..HEAD` の実差分から生成した `out.html` を Chromium で開き、
  `page.on('dialog', ...)` でネイティブの確認ダイアログが一切出ないことを監視しながら検証した。
  1. 「下書きを初期化」ボタン（`#btn-reset-draft`）がトップバーに常設で見えている
  2. 「全体へのコメント」に下書きを書くと `persist()` により `localStorage` に1件だけ
     書かれ、その間 confirm/alert 系のダイアログは一切出ない
  3. リロードしても `#banners` に「復元」「下書きを破棄」といった文言のバナーが一切
     出ない（無言で自動復元）
  4. 実際にコンポーザーを開くと、リロード前に書いた下書きの内容がそのまま復元されている
  5. 「下書きを初期化」ボタンを押すと、確認ダイアログ無しで即座に `localStorage` の
     下書きキーが消え、コンポーザーが空になる
  6. 初期化後にリロードしても下書きは空のままである（本当に消えている）
  - readonly ビルド（`--readonly`）では `#btn-reset-draft` が DOM に1件も存在しないことを
    実ブラウザで別途確認（生成物のテキスト検索では埋め込み diff データ内にこの識別子の
    文字列が偶然含まれ誤検出するため、DOM 要素数で確認した）

## 実行したもの（ラウンド9・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  （`tests/` から `python3 -m unittest -v` でも同一）— 140 passed / 0 failed / 0 skipped
  （Python 側は無変更。JS のみの変更が既存の埋め込みテストを壊していないことの確認）
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **playwright-core による実ブラウザでの操作確認（計25アサーション、すべて pass）**:
  `git range 8b22f0c..056ffc8` の実差分から生成した `out.html`（複数フォルダ・複数
  ファイルを含む）を Chromium（`~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`）
  で開き、`page.mouse.move/down/up` でセパレータを実際にドラッグして検証した。
  1. 畳んだ状態から2pxだけドラッグしても、セパレータの実測位置は2px程度しか動かない
     （以前のように以前の幅へジャンプしない）
  2. マウスを一切動かさずに押して離した場合は畳んだままである（ドラッグ開始時の
     自動オープンが無いことの確認）
  3. 畳んだ状態から大きく（+300px）ドラッグすると開いた状態になり、`#filelist` の
     中身が見える
  4. 開いた状態から大きく（-400px）ドラッグすると畳んだ表示になり、`#filelist` が
     非表示になり、ストリップ幅が正確に40pxになる
  5. 畳んだ状態はページリロード後も `localStorage` 経由で保持される
  6. 右ペイン（コメント一覧）でも同様に、畳んだ状態からの小ドラッグでジャンプしない・
     大きなドラッグで開閉が追従する・畳むと `#commentlist` が非表示になることを確認
  7. ドラッグで畳んだ後、開閉ボタンで開き直すと、畳む直前の実際の幅（40pxではない
     まともな幅）に戻ることを確認（幅の pref をドラッグ畳み時には上書きしていないこと）
  8. **（review 指摘の修正後・追加）** セパレータにフォーカスして `End`→`Home` キーを
     押すと、`Home` は「最小幅にするが開いたまま」ではなく畳んだ表示（`#filelist` 非表示）
     になることを確認（キーボード経由でも同じ不変条件が働く）
  9. **（同上）** `localStorage` に意図的に壊れた組み合わせ（`pane-left=open` かつ
     `left-width=40`）を書き込んでからリロードすると、畳んだ表示に正規化されることを
     確認（`init()` の読み込み時正規化）
  10. **（同上）** ドラッグで畳んだ直後の `#sep-left` の `aria-valuenow` が実測で
      `"40"` になっている（畳む直前の値のまま固まっていない）ことを確認
  - なお `#sep-left` へのフォーカスは `page.click()` ではなく `locator.focus()` で
    行った——`pointerdown` ハンドラの `event.preventDefault()` により、マウスクリック
    では既定のフォーカスが乗らない（これはテスト手法上の注意点であり、実装側の
    不具合ではない）。

## 実行したもの（ラウンド8・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による既存の headless DOM 検証（`run.js`）— 引き続きすべて pass
  （回帰なし）
- **playwright-core による実ブラウザでの操作確認（新規5項目・12アサーション、すべて
  pass）**:
  1. ツリー表示でフォルダ行（`.tree-dir`）が実際に表示されることを確認
     （4ファイルの差分で `.aidev/works/...` と `docs/ClaudeCode/skills/...` の
     2つのフォルダ行が正しく分かれて表示された）
  2. コメント一覧パネルを閉じると `#commentlist` が非表示になる（`isVisible()`）
  3. コメント一覧・ファイル一覧それぞれの開閉ボタンに、閉じたときだけバッジが表示され
     （件数も正しい）、開いたときは消えることを確認
  4. セパレーターの `Home` キー操作（最小幅へ）で実際の幅が40pxになることを確認
     （`getBoundingClientRect().width`）
  5. 確認済みチェックでファイル本文が自動的に `data-collapsed="true"` になることを確認
  6. 解決済みチェック（「解決にする」ボタン）でスレッドが自動的に
     `data-collapsed="true"` になることを確認
- readonly ビルド（`--readonly`）でも、ツリーのフォルダ表示・バッジ表示（クリックせず
  閉じた状態を直接生成して確認）が機能し、例外が発生しないことを確認した。
- **review 工程の独立点検で「バッジ更新がボタンのクリック以外の開閉経路（`{`/`}`/`[`/`]`
  ショートカット・セパレータの Enter/Space）では効かない」と指摘され修正**
  （decisions.md D15）。修正後、playwright-core で `}` キーでの折りたたみ→バッジ表示、
  `]` キーでの展開→バッジ非表示、`{` キーでの左ペイン折りたたみ→バッジ表示、
  セパレータへの `Enter` キーでの折りたたみ→バッジ表示、の4経路すべてを実測して
  確認した。既存の12項目の実ブラウザ確認（クリックでの開閉）・jsdom 回帰・
  `python3 -m unittest discover`（126件）も再実行し green のまま。

## 実行したもの（ラウンド7・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **実ブラウザでの高さ実測（新規の検証手段）**: `playwright-core` ＋ 既存インストール済みの
  Chromium バイナリ（`~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`）を使い、
  `page.locator(...).boundingBox()` で実際にレンダリングされた高さを測定した。
  jsdom（headless DOM 検証）は CSS の**指定値**（`getComputedStyle().minHeight` が
  `"28px"` を返す等）しか確認できず、レイアウト計算後の**使用値**（実際に描画される
  高さ）は検証できていなかった——今回の不具合（`min-height` が下限であるがゆえに
  content 側の自然な高さがそれを超えていると無効化される）は、まさにこの「指定値と
  使用値の違い」によって jsdom では検出できず、実ブラウザでしか見つけられなかった。
  - トップバー7個（split表示/テーマ/レビュー開始/JSON書き出し/ファイルを開く/通知ベル/
    ヘルプ）: すべて 28.00px（修正前は通知ベル以外すべて 32.39px）
  - ファイル操作列（file-toggle/copy-path）: 28.00px
  - composer（コメントする/閉じる/severity select）: 28.00px
  - submit-panel（提出する/閉じる）: 28.00px
  - 例外3箇所（差分行の +・expand-all〔比較用に icon-btn も確認〕・
    row .comment-open）: `row .comment-open` は 18.80px（意図どおりコンパクトなまま）、
    `expand-all`（`.icon-btn`）は 28.00px
  - 「ファイルにコメント」ボタン（`.file-actions .comment-open`）は、この work が
    自分自身の差分をレビューする際、`docs/ClaudeCode/skills/other/diff-review-html/
    templates/style.css` という長いパスと組み合わさって `.file-head` の横幅が窮屈になり、
    ボタン自身が2行に折り返って 43.59px になるケースを確認した。**これはバグではなく
    D12/D13 で意図した「固定 `height` ではなく `min-height` にして、収まらない場合は
    欠けずに伸びる」という安全策が働いている状態**（通常の短いパスでは発生しない）。

## 実行したもの（ラウンド6）

## 実行したもの（ラウンド6・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による headless DOM 検証 — **64 件、すべて pass**（`height: 28px` を
  `min-height: 28px` に変更したことを `getComputedStyle().minHeight` で確認。3つの
  例外セレクタは `min-height: 0` も明示したことを確認。今回の実行では差分が複数
  ファイルだったため、環境依存スキップは発生しなかった）

> **ラウンド5**（PR #27 マージ後、ボタンの高さ不揃いがトップバー以外にも残っていると
> いう指摘——decisions.md D12——を coding で修正した後の再検証）。ラウンド1〜4の内容は
> 本ファイル末尾に残す。

## 実行したもの（ラウンド5）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による headless DOM 検証 — **62 件のアサーション pass・1件は環境依存で
  スキップ**（D12 の確認——ファイル操作列/コメント入力欄/スレッド見出し/提出パネル/
  レビュー結果一覧の編集・削除ボタンが軒並み `height: 28px`、かつ差分行の「+」・
  隙間展開ボタン・コメント一覧カードは意図どおり `auto` のまま——を `getComputedStyle()`
  で追加。スキップは「差分が1ファイルのみだとツリーのフォルダ行自体が出ない」という
  ツリー表示側の既存仕様に起因するもので、今回の変更とは無関係）

## 実行したもの（ラウンド4）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による headless DOM 検証 — **60 件のアサーション、すべて pass**
  （D11 の2件——`#pane-center` の `padding-top`/`#overall` の `margin-top`・トップバー
  7個のボタンの `height`——の確認を `getComputedStyle()` で追加）

> **ラウンド3**（review ラウンド2で見つかった重大度バッジの二重表示——decisions.md D10
> ——を coding で修正した後の再検証）。ラウンド2は D9 の2件（AC12 の重大度消失・編集中
> インジケータ欠如）の修正検証、ラウンド1は初回実装の検証。いずれの内容も本ファイル
> 末尾に残す。

## 実行したもの（ラウンド3・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による headless DOM 検証 — **51 件のアサーション、すべて pass**
  （ラウンドを追うごとに、見つかった指摘の確認を検証スクリプトへ追加していった。
  以下「追加の headless DOM 検証」節に各ラウンドの追加分を記載）

## 受け入れ基準ごとの判定

すべて headless DOM 検証（jsdom で実際に生成 HTML を実行し、クリック/入力を dispatch して
確認）または既存の自動テストで確認した。design.md の「受け入れ基準との対応」に対応する
実装箇所を、実際にブラウザ相当の環境で動かして検証している（コードを読むだけの確認ではない）。

- AC1: pass — ツリー表示でフォルダ/ファイル行に `.icon-folder`/`.icon-file` が実在することを確認。
- AC2: pass — 検索欄に `.icon-search` が実在することを確認。
- AC3: pass — ツリー表示のファイル行に `+N` 形式の追加行数表示が残っていることを確認。
- AC4: pass — `#btn-submit-open` が存在せず、`#btn-start-review` のみが存在することを確認。
- AC5: pass — クリックでパネルが開き、ラベルが「レビュー結果を入力」に変わることを確認。
- AC6: pass — 提出後、`#review-list` にエントリ（判定バッジ＋サマリ）が表示されることを確認。
- AC7: pass — 編集ボタンでフォームに既存値が読み込まれ、保存すると新規追加ではなく
  同じエントリが更新されることを確認（提出前後でエントリ数が1件のまま）。
- AC8: pass — 削除ボタンでエントリが一覧から消え、空状態メッセージに戻ることを確認。
- AC9: pass — `#btn-submit-discard` が存在しないことを確認。
- AC10: pass — 生成 CSS に `.file-head { ... position: sticky ... }` が含まれることを確認
  （jsdom はレイアウトエンジンを持たないため、実際の描画・スクロール追従の見た目は
  未検証。「未検証の穴」参照）。
- AC11: pass — スレッドに `.thread-fold` ボタンが実在し、クリックで
  `data-collapsed="true"` に切り替わることを確認。
- AC12: pass — 折りたたんでも `.thread-head` は残り、`.comment` 要素（CSS で隠す対象）は
  DOM 上に残っていることを確認。
- AC13: pass — 提出直後に `#notif-badge` が非表示解除され `"1"` を表示することを確認。
- AC14: pass — 提出成功メッセージが `#banners` のインラインバナーには現れず、
  `#notif-list` にだけ現れることを確認。
- AC15: pass — 不正な正規表現を検索欄に入力すると、`#file-search-hint` にエラーが
  表示されることを確認（画面上部側に留まる。対応不要のお知らせと違いベルへは流さない）。
- AC16: pass — ベルをクリックすると `#notif-badge` が再び非表示になることを確認。
- AC-I1: pass — `Escape` で提出パネルが閉じることを確認（`closeSubmitPanel()` 経由）。
  スレッド折りたたみ・通知ベルの開閉はクリックで確認済み（AC11/AC13/AC16 のとおり）。
- AC-I2: pass — 編集中に値を変更したあと `Escape` で閉じても、一覧のエントリ内容が
  変更前のまま（キャンセル前に保存した内容）であることを確認。
- AC-I3: pass（部分検証） — 新規ボタン（編集・削除・折りたたみ・ベル）はいずれも
  `<button type="button">` として実装されており、`click()` イベントで操作できることを
  確認した。**Tab キーでの実際の到達順序（フォーカストラップの有無等）は jsdom では
  検証していない**（「未検証の穴」参照）。
- AC-I4: pass — スレッド折りたたみのフォーカス復元ロジック（`focusInPlace` 呼び出し）が
  例外なく動くことを確認。ベルは開いてもフォーカス移動処理を呼んでいないため、
  ボタン自身に残ることを設計上確認（jsdom の `document.activeElement` の厳密な追跡は
  行っていない）。
- AC-I5: pass — 新機能追加後も既存のキー操作（`j` による行移動）が例外なく動作することを
  確認。
- **AC12（ラウンド2で再確認）**: pass — review 指摘（decisions.md D9）を受けて
  `.thread-head` に重大度バッジを追加。折りたたむ前後どちらも
  `.thread-head .badge.sev-must` が存在することを headless DOM 検証で確認（ラウンド1では
  この観点を見落としていた）。
- **US3（ラウンド2で追加）**: pass — `#review-list` が複数件のとき、編集中のエントリにだけ
  `data-editing="true"` と「編集中」表示が付き、保存/キャンセルどちらでも印が消えることを
  headless DOM 検証で確認。

## 失敗の証跡

**ラウンド16では失敗は発生していない**（`python3 -m unittest` 140件・smoke 3件・
playwright-core 実測4件、いずれも green で coding への差し戻しは無かった）。

**ラウンド15では失敗は発生していない**（`python3 -m unittest` 140件・smoke 3件・
playwright-core 実測13件、いずれも green で coding への差し戻しは無かった）。

**ラウンド14では失敗は発生していない**（`python3 -m unittest` 140件・smoke 3件・
playwright-core 実測27件、いずれも green で coding への差し戻しは無かった。テスト
作成中にバックドロップとトリガーボタンのスタッキング関係についての想定違いが
1件あったが、これは実装の不具合ではなく正しい・意図したモーダルの挙動であり、
テスト側の該当箇所を修正して解消した）。

**ラウンド13では失敗は発生していない**（`python3 -m unittest` 140件・smoke 3件・
playwright-core 実測20件、いずれも green で coding への差し戻しは無かった。テスト
作成中に自分の想定違いが3件あった——(1) 開いた直後は `#review-body` に
フォーカスが移るため Escape がグローバルハンドラの `isTyping()` ガードで無効化
され、そのままでは Esc が効かなかった〔これは実装側の不足だったので `#submit-panel`
専用の Escape listener を追加して修正〕、(2) `"r"` キーでフォーカスが textarea に
あるまま2回目を押すと「r」が閉じるのではなく文字として入力されるのが正しい
挙動だった〔テスト側の期待を訂正〕、(3) `submitReview()` は提出後にパネルを
自動で閉じない仕様だった〔テスト側の期待を訂正〕。(1) のみ実装を直し、
(2)(3) はテストの前提を実際の・意図した挙動に合わせて修正した）。

**ラウンド12では失敗は発生していない**（`python3 -m unittest` 140件・smoke 3件・
playwright-core 実測11件、いずれも green で coding への差し戻しは無かった。テスト
作成中に自分のテストの前提が誤っていた箇所〔ページ全体のテキスト検索で "変更前" の
不在を確認しようとしたが、診断対象の差分自体にその文字列が含まれ誤検出した〕が
1件あったが、これは実装の不具合ではなくテスト側の検証方法の修正で解消した）。

**ラウンド11では失敗は発生していない**（`python3 -m unittest` 140件・smoke 3件・
playwright-core 実測18件、いずれも green で coding への差し戻しは無かった。上述の
座標選択ミスはテスト側の修正で解消し、実装への差し戻しは発生していない）。

**ラウンド10では失敗は発生していない**（`python3 -m unittest` 140件・smoke 3件・
playwright-core 実測11件、いずれも green で coding への差し戻しは無かった）。

**ラウンド9では失敗は発生していない**（`python3 -m unittest` 140件・smoke 3件・
playwright-core 実測19件、いずれも green で coding への差し戻しは無かった。検証
スクリプトを書く過程で、こちらの想定アサーションの立て方自体が誤っていた箇所が
1件あったが〔MIN_W をわずかに超える2pxドラッグ後も「畳んだまま」と期待していたが、
これは実装の不具合ではなく、その分だけ実際に開いた状態になるのが正しい挙動——
自分のテストの前提を訂正した〕、これは実装差し戻しには当たらない）。

ラウンド1〜3のいずれも、テスト実行そのものの失敗は発生していない
（`python3 -m unittest` 126件・jsdom 検証（ラウンドを追うごとに指摘の確認を追加し
最終51件）・smoke 3件、いずれも green）。
**ただし review 工程（要件適合/価値適合の独立点検）が2度、指摘を検出して coding へ
差し戻している**:
- ラウンド1の実装に対して must 1件・should 1件（decisions.md D9・review.md「ラウンド1」）。
- D9 の修正自体に対して should 1件——`.thread-head` に足した重大度バッジが展開時に
  既存の `.comment > .who` 側と二重表示になっていた（decisions.md D10・review.md
  「ラウンド2」）。
いずれも自動テストの失敗としては現れず（DOM 的には「意図通り表示された/消えた」ように
見え、要件の意図と突き合わせて初めて分かる性質の欠陥だった）、review 工程の独立点検で
拾われた。

## 起動確認（smoke）

```
$ sh docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev help
（…aidev CLI のヘルプ出力…）
$ python3 docs/ClaudeCode/skills/other/diff-review-html/diff_review.py --help
usage: diff_review.py [-h]
                      {html,bundle,view,template,check,comment,resolve,submit,list}
                      ...
git の差分をレビュー用の単一 HTML にし、レビュー記録 JSON を往復させる
$ python3 docs/ClaudeCode/skills/other/diff-review-html/diff_review.py template --repo .
{
  "reviews": [],
  "schema": "diff-review/2",
  "target": { … },
  "threads": []
}
smoke: pass (exit 0, 3 本)
```

今回の work は新しい CLI サブコマンド/オプションを追加していない（画面側の変更のみ）ため、
`smokeCommands` への追記は不要と判断した。

### 追加の headless DOM 検証（jsdom）

このプロジェクトは「画面（HTML）側の受け入れ確認は headless ブラウザで行う」方針
（`tests/test_diff_review.py` 冒頭のコメント）だが、そのための仕組みは無かったため、
この work の検証用に Node.js + jsdom を使い、実際に生成された HTML をロードして
クリック・入力イベントを dispatch する検証スクリプトをその場で書いて実行した
（成果物には含めない。work フォルダにも置かず `/tmp` のスクラッチで実行し、
検証後は残さない。**リポジトリに恒常的な headless テストとして追加するかは
この work のスコープ外**——別途 backlog 化する価値はある）。

```
$ node run.js
PASS: ツリー切替ボタンが存在する
PASS: AC1: フォルダ行にフォルダアイコンがある
PASS: AC1: ファイル行にファイルアイコンがある
PASS: AC3: 追加/削除行数表示（+N）が残っている
PASS: AC2: 検索欄にアイコンがある
PASS: AC4: #btn-submit-open が存在しない
PASS: AC4: #btn-start-review が唯一のボタンとして存在する
PASS: AC5: 初期ラベルは「レビューを開始」
PASS: AC5: クリックでパネルが開く
PASS: AC5: ラベルが「レビュー結果を入力」に変わる
PASS: AC9: #btn-submit-discard が存在しない
PASS: AC6: #review-list が存在する
PASS: AC6: 初期状態は空メッセージ
PASS: AC-I2: 確定ボタンの初期表示は「提出する」
PASS: AC6: 提出後、一覧にエントリが1件表示される
PASS: AC6: エントリにサマリが表示される
PASS: AC6: エントリに判定バッジが表示される
PASS: AC13: 通知ベルにバッジが表示される
PASS: AC14: 画面上部のバナーに提出成功メッセージが無い（ベルへ振り替え済み）
PASS: AC7: 編集ボタンが存在する
PASS: AC7: 編集モードで確定ボタンが「保存する」になる
PASS: AC7: フォームに既存のサマリが読み込まれる
PASS: AC7: 編集後もエントリは1件のまま（新規追加されない）
PASS: AC7: エントリの内容が更新される
PASS: AC7: 保存後は確定ボタンが「提出する」に戻る
PASS: AC-I2: Escape でパネルが閉じる
PASS: AC-I2: キャンセルしてもエントリの内容は変わらない
PASS: AC8: 削除ボタンが存在する
PASS: AC8: 削除後は一覧が空になる
PASS: AC10: .file-head に position: sticky が指定されている
PASS: AC11: スレッドに折りたたみボタンがある
PASS: AC11: 初期状態は展開（aria-expanded=true）
PASS: AC11/AC12: クリックで data-collapsed=true になる
PASS: AC12: 折りたたんでも thread-head は残っている
PASS: AC12: 折りたたむとコメント本文の要素が data-collapsed 配下にある（CSSで隠す対象）
PASS: AC16: ベルを開くと未読バッジが消える
PASS: AC-I4: ベルを開いてもフォーカスはベル自身に残る（明示的な移動なし）
PASS: AC13/AC14: 通知一覧に提出成功のメッセージがある
PASS: AC15: 不正な正規表現のエラーはベルではなく画面上部のバナーに出る
PASS: AC-I5: j キーで行移動しても例外が出ない

ALL PASS
```

readonly ビルド（`--readonly`）でも同様に headless で確認し、書き込み系の新規要素
（`#btn-start-review`/`#btn-submit-discard`/`#review-list`）が出力されないこと、
表示専用の新規要素（ツリーアイコン・`#btn-notif`）は出力されること、ツリーのアイコン
切り替えやスレッド折りたたみが例外なく動くことを確認した。

**ラウンド2**（review 指摘2件の修正後、検証スクリプトに4件のアサーションを追加して
再実行）:

```
$ node run.js
（…ラウンド1の全アサーション…）
PASS: レビュー観点(should#2): 編集中の1件目には data-editing=true と「編集中」表示がある
PASS: レビュー観点(should#2): 編集していない2件目には編集中の印が無い
PASS: レビュー観点(should#2): 保存すると編集中の印が消える
PASS: レビュー観点(should#2): Escape キャンセルでも編集中の印が消える
PASS: レビュー観点(must#1): 折りたたむ前は .thread-head に重大度バッジがある
PASS: レビュー観点(must#1): 折りたたんでも重大度バッジが thread-head に残っている（消えない）

（この時点で計45件 pass）
```

**ラウンド3**（D10 の二重表示解消後、さらにアサーションを追加して再実行。最終版）:

```
$ node run.js
（…ラウンド2までの45件…）
PASS: レビュー観点(must#1・ラウンド2): 展開時、先頭コメント側には重大度バッジが重複表示されない
PASS: レビュー観点(must#1・ラウンド2): 返信自身が持つ重大度は自分の .who に表示される
PASS: レビュー観点(must#1・ラウンド2): 先頭コメントの .who には重大度バッジが無い（重複抑制）

ALL PASS（51件）
```

## 未検証の穴（skip / 環境不足）

- **D25 の元の再現条件は特定できていなかったが、D26 で事実上説明がついた**:
  ユーザーが報告した「展開ボタンをクリックしても『…N行』の帯が残る」という現象
  そのものは、playwright-core での網羅的な試行（実際の生成物37箇所の隙間・単独/
  混在方向のクリック・ファイル折りたたみ・表示モード切り替え等）では一度も
  再現できなかった。D25 実装後、ユーザーから「展開後、ボタンの無い@@の行だけ
  残った」という具体的な追加報告があり、これを機に判明したのは——**D25 より前の
  コードでは、`fillFileBody()` が `.hunk-head` を隙間の状態に関わらず常に無条件で
  出しており、しかも `.hunk-head` と `.expander` はほぼ同じ見た目
  （`background`/`padding`/`border` が同一）だったため、展開で `.expander` が
  消えても、直後にある `.hunk-head` が見た目上ほぼ同じ帯として残り続け、
  「同じ帯が消えずに残っている」ように見えていた可能性が高い**、ということ。
  D26（隙間を使い切ったら見出し自体を出さない）で、この見え方の原因になっていた
  「常に残る、ほぼ同じ見た目の帯」を無くしたため、当初の報告も実質的に解消して
  いると考えられる（ただし別コンテキストからの再確認では無いため、確定はしていない）。
- **実際の描画・レイアウト**: jsdom はレイアウトエンジンを持たないため、
  `position: sticky` によるファイルヘッダーの追従、通知ポップオーバーの表示位置、
  検索アイコンとテキストの重なり具合など、**見た目・スクロール挙動そのものは
  当初実ブラウザで未確認だった**。CSS ルールの存在と、taskcheck（T7/T9）でのレビュー時の
  仕様確認（CSS Positioned Layout の仕様に照らした静的検証）で代替していた。
  - **この穴が2度顕在化した**: (1) PR #26 マージ後、sticky ヘッダーとトップバーの間の
    隙間・トップバーのボタンの高さ不揃い（decisions.md D11）。(2) PR #28 マージ後、
    `min-height: 28px` が実ブラウザでは全く効いていなかった（`min-height` は下限であり、
    content 由来の高さが既にそれを超えていると無効化される。decisions.md D13）。
    (2) は特に、jsdom の `getComputedStyle()` が「指定値」しか読めず「使用値」（実際の
    描画結果）を読めないことに起因し、jsdom による検証だけでは原理的に検出不可能だった。
  - **この work では playwright-core ＋ 既存 Chromium バイナリによる実ブラウザ実測
    （`boundingBox()`）を用意し、ボタンの高さについてはこの穴を解消した**（D13）。
    ただし sticky の実際のスクロール追従・通知ポップオーバーの表示位置など、
    ボタンの高さ以外の見た目はまだ実ブラウザで網羅的には確認していない。
    **今後 diff-review-html を触る work では、jsdom だけでなく実ブラウザでの
    `boundingBox()`/スクリーンショット確認も検証手段に含めることを推奨する**
    （この work で有効性が実証された）。
- **Tab キーでの到達順序**: AC-I3 は新規ボタンが `<button>` として click 操作できる
  ことは確認したが、実際に Tab キーで辿ったときの順序・フォーカスの見え方
  （`:focus-visible` のスタイル等）は未確認。
- **色のコントラスト実測**: 通知バッジの配色修正（review.md 参照）はトークンの
  組み合わせから妥当と判断したが、実際のレンダリングでのコントラスト比計測ツール
  （axe 等）による確認は行っていない。
- **クロスブラウザ確認**: Chromium/Firefox/Safari 等での実機確認は行っていない
  （このプロジェクトの既存の検証範囲を超えるため、他の work でも同様に未検証）。
