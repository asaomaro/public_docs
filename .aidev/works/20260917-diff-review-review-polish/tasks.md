# タスク: レビュー操作性の改善（ツリー見た目・レビュー提出フロー・固定ヘッダー・コメント折りたたみ・通知ベル）

## 実装方針

design.md の F1〜F6 を、他の機能に依存しない単位から並行できるように分解する。
分割 work（subtask）にはしない——3 ファイル（`page.html`/`app.js`/`style.css`。`ui.js` は
design.md のとおり無改造）への変更はいずれも独立して検証可能な小さな差分で、1 PR に
収まる規模（`aidev-docs/DESIGN.md`「5.」の3層決定木で「不可分・小規模」）。

- SVG アイコン基盤（T1）は、ツリーアイコン（T2）・検索アイコン（T3）・通知ベル（T9）の
  前提になるので最初に作る。
- レビュー提出フロー（T4〜T6）は互いに直列（ボタン統合 → 一覧UI → 破棄ボタン撤去の順で、
  前の変更が後の前提になる）。
- sticky ヘッダー（T7）・コメント折りたたみ（T8）は T1〜T6 とも独立に着手できる。
  通知ベル基盤（T9）は T1（SVG 基盤）にのみ依存し、T2〜T6 とは独立。
- 通知の実配線（T10: `banner()` → `notify()`）は通知ベル基盤（T9）の後。
- 仕上げ（T11: `Escape` の配線・`threadCollapsed` のリセット・既存キー操作の回帰確認）は
  対象の機能（T5/T8/T9）がすべて揃ってから行う。

## 作業順序と依存関係

下の各タスクの `依存:` に従う。この節では依存では表せない理由だけを補足する。

- T2/T3/T9 はいずれも T1（SVG スプライトと `icon()` ヘルパー）が無いとアイコンを出せない。
- T5（一覧・編集・削除 UI）は T4（ボタン統合後の `#submit-panel` の開閉経路）を前提にする。
- T6（破棄ボタン撤去）は T5 で「編集・削除で代替できる」状態になってから行う
  （requirements.md の理由づけそのもの。先に消すと「未提出コメントを一括で消す手段」が
  一時的に無くなる）。
- T11 は T5/T8/T9 の新規ボタン・パネルがすべて揃ってからでないと、`Escape` の配線先や
  回帰確認の対象が定まらない。

## リスク / 留意点

- T7（sticky ヘッダー）は `.file` の `overflow: hidden` を外す変更を伴う。角丸の見た目
  （`.file-head`/`.file-body` への `border-radius` の付け替え）を同じタスク内で必ずセットで
  行う（design.md「実装時の注意」）。抜けると角の四隅が欠けて見える退行になる。
- T5 で `discardPending()`／`#btn-submit-discard` をこの時点ではまだ消さない
  （T6 で消す）。T5 の時点で消してしまうと、T5 単体でのコミット/検証時に
  「未提出コメントを一括で消す手段」が無い状態と「編集・削除で代替できる」状態が
  同時に成立しているかを確認しづらい。
- T9（通知ベル基盤）の時点では `banner()` の呼び出し側はまだ何も変えない
  （`notify()` を定義するだけ）。T10 で初めて呼び出し側を差し替える。順序を逆にすると
  「`notify()` が無いのに呼ばれる」状態を経由してしまう。
- T4（`page.html:31-35` の `#btn-submit-open` 削除）と T9（`page.html:28-40` の `.actions`
  へベルボタンを追加）は、`依存:` 上は独立で並行に着手できるが、`page.html` の同じ
  `.actions` ブロック内の近接した行を編集する。**着手前に `page.html` の現在の内容を
  読み直してから編集する**（他方が先に着手済みで行番号がずれている可能性があるため。
  ファイル単位の衝突であって、機能上の依存関係ではないので `依存:` には加えない）。

## テスト方針

- 既存の `tests/test_diff_review.py`（`python3 -m unittest` 等）を通す。特に
  `ThemeCssTest` は新規色トークンを追加していないことを前提にしているので、
  `style.css` の `:root`/dark-assign ブロックに触れていないことを確認する。
- `.aidev/config.yml` の `smokeCommands`（`diff_review.py --help` / `template --repo .`）を
  test 工程の起動確認として実行する。
- 目視確認（ブラウザで `diff_review.py` の出力 HTML を開く）で、AC1〜AC16・
  AC-I1〜AC-I5 を一通りなぞる。自動テストが無い UI の見た目・操作感はここで確認する
  （テストコードでの機械検証は無い項目が多いため、起動確認と目視が主な検証手段になる）。

## タスク

- [x] T1: SVG スプライト（フォルダ/ファイル/検索/ベル）と `icon()` ヘルパーを追加する
      対象: `templates/page.html`（`<body>` 直後、`.skip` の前に `<symbol>` を追加）／
      `templates/app.js:136-151`（`el()` の隣に `icon()` を追加）／
      `templates/style.css:592-611`（`.icon-btn` の隣に共通の `.icon` サイズ指定を追加）／
      根拠: design.md「インターフェース/データ構造」節「SVG アイコン」
      依存: なし
      AC: なし
- [x] T2: ツリーのフォルダ/ファイル行にアイコンを追加する
      対象: `templates/app.js:703-739`（`appendTreeChildren()`）／根拠: design.md 同節、
      research.md A1
      依存: T1
      AC: AC1, AC3
- [x] T3: ファイル検索欄に検索アイコンを追加し、角丸を統一する
      対象: `templates/page.html:113-118`（`.filelist-tools`）／
      `templates/style.css:613-628`（`#file-search`）／根拠: design.md 同節、research.md A2
      依存: T1
      AC: AC2
- [x] T4: レビュー操作ボタンを1個（「レビューを開始」→「レビュー結果を入力」）に統合する
      対象: `templates/page.html:31-35`（`#btn-submit-open` 削除）／
      `templates/app.js:1849-1861`（`updatePendingCount()` のラベル文言）／
      `templates/app.js:2152-2171`（`wire()` の `submitOpen` 結線削除）／根拠: design.md
      「レビュー提出フローの単一ボタン化（F2）」、research.md A3, A5
      依存: なし
      AC: AC4, AC5
- [x] T5: 提出済みレビュー結果の一覧・編集・削除 UI を追加する
      対象: `templates/page.html:71-88`（`#submit-panel` に `#review-list` を追加）／
      `templates/app.js`（`renderReviewList`/`reviewEntry`/`editReview`/`cancelEditReview`/
      `deleteReview` の新設、`submitReview()` の編集分岐）／根拠: design.md
      「提出済みレビュー結果の一覧・編集・削除（F3）」、research.md A4, A11
      依存: T4
      AC: AC6, AC7, AC8, AC-I2, AC-I3
- [x] T6: 「未提出のコメントを破棄」ボタンと `discardPending()` を削除する
      対象: `templates/page.html:85`／`templates/app.js:1890-1898`（`discardPending()`）／
      `templates/app.js:2160`（結線）／根拠: design.md 同節
      依存: T5
      AC: AC9
- [x] T7: ファイルヘッダーを画面上部に固定表示（sticky）する
      対象: `templates/style.css:317-330`（`.file`/`.file-head`/`.file-body`）／根拠:
      design.md「ファイルヘッダーの固定（F4）」、research.md F1〜F3, A6
      依存: なし
      AC: AC10
- [x] T8: コメントスレッドに折りたたみ/展開ボタンを追加する
      対象: `templates/app.js:1493-1529`（`renderThread()`）／`templates/style.css`
      （`.thread[data-collapsed]` の新規ルール）／根拠: design.md
      「コメントスレッドの折りたたみ（F5）」、research.md A7, A10
      依存: なし
      AC: AC11, AC12, AC-I1, AC-I3, AC-I4
- [x] T9: 通知ベル（ポップオーバー・未読バッジ・`notify()`/`renderNotifList()`）を追加する
      対象: `templates/page.html:28-40`（`.actions` にベルボタン＋`#notif-panel`）／
      `templates/app.js`（`notify`/`renderNotifList`/`updateNotifBadge`/`toggleNotifPanel`
      の新設）／根拠: design.md「通知ベル（F6）」、research.md A8, A9
      依存: T1
      AC: AC13, AC16, AC-I1, AC-I3, AC-I4
- [x] T10: 「対応不要のお知らせ」2箇所を `banner()` から `notify()` へ差し替える
      対象: `templates/app.js:110`（バンドル読み込み成功）／`templates/app.js:1887`
      （レビュー提出成功）／根拠: design.md 同節、research.md F7 の表
      依存: T9
      AC: AC14, AC15
- [x] T11: `Escape` の配線・折りたたみ状態のリセット・既存キー操作の回帰確認を行う
      対象: `templates/app.js:2037-2131`（`onKeyDown()` の `Escape` 分岐に `#notif-panel`/
      編集キャンセルを追記。他のキー分岐は変更しない）／`templates/app.js:56-74`
      （`applyDiffData()` に `threadCollapsed = {}` のリセットを追加）／根拠: design.md
      「振る舞いの詳細」「ドメイン固有の考慮」
      依存: T5, T8, T9
      AC: AC-I1, AC-I5
