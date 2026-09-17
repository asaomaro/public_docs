# タスク: 画面まわりの不備 7 件

## 実装方針

**独立した項目から先に、共有ヘルパー（`focusInPlace`）を軸にする項目をあとに**積む。
F10（展開時の位置維持）が `focusInPlace` を新設し、F4（畳む）と `expandAll` の既存コードが
それを使い回すので、**F10 の土台を先に作ってから F4 を乗せる**。

1. 独立して直せるもの（T1 ツリー CSS / T2 アイコン化 / T3 確認済み / T4 パスコピー / T5 ファイル名整理）。
2. 検索（T6・T7）——ファイル一覧の描画（フラット・ツリー）を触るので、
   T2（アイコン化）と T5（ファイル名整理）で一覧の描画コードが変わったあとに乗せる。
3. `focusInPlace` の新設と展開系の巻き取り（T8）。
4. 畳む操作（T9）——T8 の `focusInPlace` を前提にする。
5. 文書（T10）とテスト（T11・T12）、画面の受け入れ確認は test 工程で（T13）。

**各タスクの終わりに既存の性質を確認する**（決定論・`f`/`e`/`t` キーが同じ対象に効くこと・
参照専用でも動くこと）。

## 作業順序と依存関係

下の `依存:` に従う。それでは表せない順序の理由だけをここに書く。

- **T5（ファイル名クリックの整理）を T3（確認済み）・T4（パスコピー）より先に**。
  ファイルヘッダーの組み立て順（折りたたみアイコン・パス・コピー・確認済み・タグ・操作）を
  1 回で決めないと、あとから挿し込むたびに並びが変わって読みにくくなる。
- **T6・T7（検索）を T2・T5 のあとに**。一覧の描画（`renderFileList`/`appendTreeChildren`）を
  検索対応で書き換える前に、アイコン化とヘッダー整理を済ませておかないと、同じ関数を
  2 回に分けて触ることになる。
- **T9（畳む）を T8（focusInPlace）のあとに**。design のとおり、畳むボタンの焦点処理は
  `focusInPlace` を直接使う前提で書く。

## リスク / 留意点

- **R1（research R1）**: `preventScroll` はブラウザ実装依存。対応していない環境では
  旧来の挙動に戻るだけ（悪化しない）ことを T8 で確認する。
- **R2（research R2）**: 検索でツリーを絞り込むとき、一致ファイルの祖先ディレクトリを
  強制的に開いて見せる。既存の `treeOpen`（画面内だけの状態）を検索中は上書きしない
  （検索を消したら元の開閉に戻る）。T7 の設計点。
- **R3（research R3）**: 確認済みチェックボックスは `app.js` が動的に作る要素なので、
  `page.html` の `rw:` マーカー（静的削除）の対象にならない。参照専用でも同じ DOM 構造で出ることを
  T13 で確認する。
- **R4（research R4）**: `viewedFiles` は `applyDiffData` のリセット対象に含める
  （バンドルを差し替えたら前の差分の確認済みを引きずらない）。T3 の実装点。
- **R5（research R5）**: アイコンに変える既存ボタンには必ず `title` を新設する
  （`aria-label` だけだとマウス利用者に伝わらない）。T2 で全数チェック。
- **R6**: `.file-toggle` のクラス名は残す（`f` キー・`redrawFile` 等の既存セレクタを壊さないため）。
  中身（テキスト→アイコン）だけを変える。T5・T2 共通の留意点。
- **R7**: 「畳む」ボタンのクラスは `.collapse-all`（`.expand-all` と対称）。design 誤記の是正
  （doccheck で発見・修正済み）を実装でも踏襲する。

## テスト方針

- **画面（T13・test 工程・headless Chromium・`file://`）**: 固定入力（`tests/fixture_repo.py`）で
  HTML を生成し——
  - ツリーの深さに応じたインデント（`getBoundingClientRect().x` の比較）。
  - 検索 3 種（部分一致/ワイルドカード/正規表現）× フラット/ツリー。
  - 畳む: 全展開 → 畳む → 行数が元に戻ること。
  - アイコン化した各ボタンに `aria-label`/`title` があること（全数）。
  - 確認済み: チェック → 件数表示 → 再読み込みで状態が残ること → 書き出し JSON に混ざらないこと。
  - パスコピー: `execCommand` 経路の実行とボタンの一時表示変化。
  - **F10 の回帰**: research で再現したシナリオ（4 ギャップ中 3 番目を展開）を
    そのまま検査にし、`scrollTop` の差が小さいことを確認。
  - 既存 75＋34 件相当の画面回帰（レイアウト・バンドル）を再実行。
- **キー割り当ての不変**: `f`/`e`/`Shift+E`/`t` が同じ対象に効くことを実測する。

## タスク

- [x] T1: ツリーのインデント（`.tree-group` に `padding-left`/`border-left`）
      対象: `templates/style.css` / 根拠: research F1, design §F1
      依存: なし
      AC: AC1
- [x] T2: アイコン化（`btn-tree`/`btn-pane-left`/`btn-pane-right`/`btn-theme`/`btn-help-open`。
      各要素に `title` を新設）
      対象: `templates/page.html`, `templates/ui.js`, `templates/app.js` / 根拠: research F5, design §F5
      依存: なし
      AC: AC7, AC8
- [x] T3: 確認済みチェックボックスと件数表示（`viewedFiles` の新設・`persist()`/`restore()` への
      同居・`applyDiffData` でのリセット・件数の描画）
      対象: `templates/app.js` / 根拠: research F6, F7, R4, design §F6/F7
      依存: なし
      AC: AC9, AC10, AC11, AC12
- [x] T4: パスコピー（`copyText` ヘルパー・`execCommand` フォールバック・ボタンの一時表示・
      失敗時のバナー）
      対象: `templates/app.js` / 根拠: research F8, design §F8
      依存: なし
      AC: AC13
- [x] T5: ファイル名クリックの整理（`.file-toggle` をアイコンのみへ・パスを非クリックの `<span>` へ・
      ヘッダーの並び順を確定：折りたたみ／パス／コピー／確認済み／タグ／操作）
      対象: `templates/app.js`, `templates/style.css` / 根拠: research F9, design §F9, リスク R6
      依存: なし
      AC: AC14
- [x] T6: 検索の判定（`compileQuery`: 部分一致/ワイルドカード/正規表現の判別。12 ケースを
      scratch で実測済みの規則をそのまま移す）
      対象: `templates/app.js` / 根拠: research「アイコン化の線引き」直前の検証, design「AC ごとの実現方法」
      依存: なし
      AC: AC3, AC4, AC5
- [x] T7: 検索欄の描画と一覧への適用（フラット・ツリー双方の絞り込み、ツリーでの祖先自動展開、
      検索を消したときに元の開閉状態へ戻す）
      対象: `templates/page.html`, `templates/app.js`, `templates/style.css` / 根拠: リスク R2
      依存: T2, T5, T6
      AC: AC2
- [x] T8: `focusInPlace` の新設と展開系の巻き取り（`redrawFile` にギャップの手がかりを渡す・
      `expander()` の呼び出し変更・`expandAll` を `focusInPlace` に統一）
      対象: `templates/app.js` / 根拠: research F10, design §F10, リスク R1
      依存: なし
      AC: AC15
- [x] T9: 畳む操作（`collapseAllGaps`。`.expand-all` の隣に `.collapse-all` を常設）
      対象: `templates/app.js` / 根拠: research F4, design §F4, リスク R7
      依存: T8
      AC: AC6, AC16
- [x] T10: `SKILL.md` を更新（検索の記法・確認済み・アイコンの一覧・キー操作表への追記無し
      の明記〔新キーは増やさない〕）
      対象: `SKILL.md` / 根拠: design「非機能要件」
      依存: T1, T2, T3, T4, T5, T6, T7, T9
      AC: AC7, AC8
- [x] T11: 画面側の検証コード整備（scratch のブラウザ検証スクリプトを test 工程で使えるよう、
      固定入力での生成コマンドをまとめておく）
      対象: 未特定（test 工程で作成・書き捨て） / 根拠: design「テスト方針」
      依存: T1, T2, T3, T4, T5, T6, T7, T9
      AC: AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9, AC10, AC11, AC12, AC13, AC14
- [x] T12: F10 の回帰検査（research のシナリオをそのまま固定）
      対象: 未特定（test 工程で作成・書き捨て） / 根拠: research F10, design §F10
      依存: T8
      AC: AC15, AC16
- [x] T13: **画面の受け入れ確認・回帰（消化は test 工程）**。T11・T12 に加え、
      キー割り当ての不変（`f`/`e`/`Shift+E`/`t`）・参照専用での動作・既存画面確認の再実行
      対象: 未特定（test 工程で実施） / 根拠: design「既存への影響と回帰」, リスク R3
      依存: T11, T12
      AC: AC-I1, AC-I2, AC-I3, AC-I4
