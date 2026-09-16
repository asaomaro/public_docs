# タスク: 3 ペイン・split・ツリー・テーマ

## 実装方針

**器（レイアウト）を先に、中身（split・ツリー・コメント一覧）を後に**積む。
逆にすると、split やツリーを作ったあとで親の入れ物が変わり、スクロールとフォーカスの手当てを
2 回やることになる。

1. 骨格（T1 page.html / T2 style.css の 3 ペイン）——ここが動かないと他は置き場所が無い。
2. `ui.js`（T3 設定の記憶 → T4 テーマ → T5 境界）——**レビューの状態を知らない層**を先に閉じる。
3. 中身（T6 split → T7 ツリー → T8 コメント一覧）。
4. キー割り当て（T9）は**画面が出そろってから**。前 work の must（`Enter` の横取り）は
   組み合わせて初めて壊れる類なので、最後にまとめて実測する。
5. 文書（T10）とテスト（T11・T12）、画面の受け入れ確認は test 工程で（T13）。

**各タスクの終わりに既存の性質を確認する**（決定論・`textContent` 描画・UTF-8/LF・依存ゼロ）。

## 作業順序と依存関係

下の `依存:` に従う。それでは表せない順序の理由だけをここに書く。

- **T3（設定の記憶）を T4・T5 より前に**。テーマも幅も開閉も同じ保存庫を使うので、
  先に形を決めないと 3 か所で別々の書き方になる。
- **T6（split）を T8（コメント一覧）より前に**。コメント一覧の「該当箇所へ飛ぶ」は
  split の行にも当たる必要があり、split の DOM が決まってからでないと飛び先を書けない。
- **T12（CSS の検査テスト）は T4 の直後でもよいが、T11 とまとめる**。同じテストファイルを 2 回触らない。

## リスク / 留意点

- **R1（実測済み・research F3）**: 畳む指定を CSS 変数で書くと**黙って効かない**。
  `grid-template-columns` の宣言で書く（decisions D4）。T2 と T13 の検査点。
- **R2（実測済み・research F7）**: リンクでの移動は**フォーカスを運ばない**。
  移動先に `tabindex="-1"` ＋ `focus()`（T7・T8）。
- **R3（前 work で 2 回踏んだ）**: 再描画すると `currentRow` が切り離されたノードのまま残り、
  キー操作が**黙って効かなくなる**／フォーカスが `BODY` に落ちる。
  split の切り替え（T6）とツリーからの移動（T7）でも同じ手当てを入れる。
- **R4（decisions D3）**: 暗の色の割り当てが 2 か所にある。**ずれを機械的に検出**する（T12）。
- **R5**: `.topbar` にボタンが 9 個になる。狭い画面で折り返して差分の高さを食わないこと（T2）。
- **R6**: コメント一覧は `renderThreads()` のたびに描き直す。スレッドが多いと重い——
  実測して、必要なら描き直しを絞る（T8 で測る）。
- **R7**: `--rich off` / 差分 0 件 / コメント 0 件でも 3 列が崩れないこと（T13）。

## テスト方針

- **生成側（T11・T12・stdlib `unittest`）**: `__UI_JS__` が埋まること、`ui.js` が常に同梱されること、
  `style.css` の暗の割り当て 2 ブロックの宣言列が一致すること、
  書き出した JSON に画面設定のキーが出ないこと、2 回生成のバイト一致。
- **画面（T13・test 工程・headless Chromium・`file://`）**: AC1〜AC14・AC-I1〜AC-I5 を実測。
  research の落とし穴 2 件を**回帰として固定**する——
  (a) 畳んで戻したら幅が戻る、(b) 一覧・コメント一覧から飛ぶとフォーカスが移る。
  既存 28 件の画面確認も 3 ペインのまま再実行する（AC16）。
- 外部リクエストが `file://` の本体 1 件以外 0 であることを実測（AC17）。

## タスク

- [x] T1: `page.html` を 3 ペインの骨格にする（`.shell` / 左ペイン / 境界 / 中央 / 右ペイン、
      トップバーのボタン 4 種、左ペイン見出しの `btn-tree`、`<head>` のテーマ復元スクリプト、
      ヘルプ表に 3 行）＋ `diff_review.py` に `__UI_JS__` の差し込み口を足す
      対象: `templates/page.html`, `diff_review.py` / 根拠: design「画面の骨格」
      依存: なし
      AC: AC11
- [x] T2: `style.css` に 3 ペインの Grid（畳む 4 パターン・狭い画面で 1 列・境界の見た目）と
      ペイン内スクロールを書く
      対象: `templates/style.css` / 根拠: design §2, decisions D4, research F3, F10
      依存: T1
      AC: AC11, AC12, AC14
- [x] T3: `templates/ui.js` を作り、設定の保存庫（`DiffReviewUI.pref`）を書く
      （固定キー・読めない書けない環境では既定値・バナーを出さない）
      対象: `templates/ui.js` （新規） / 根拠: decisions D5, D6, D7
      依存: T1
      AC: AC7, AC13, AC15
- [x] T4: テーマ 3 状態（CSS の二層化と `data-theme`、巡回ボタン、`<head>` スクリプトとの整合）
      対象: `templates/style.css`, `templates/ui.js` / 根拠: design §1, decisions D3, research F4
      依存: T2, T3
      AC: AC6, AC7
- [x] T5: 境界（`role="separator"`・Pointer Events のドラッグ・矢印 / Home / End / Enter・
      `aria-valuenow` の追従・離した時点で保存）とペインの開閉ボタン
      対象: `templates/ui.js` / 根拠: design §2, research F1, F2, F3
      依存: T2, T3
      AC: AC12, AC13, AC-I1, AC-I2
- [x] T6: split 表示（`pairLines`・2 セルの行・左右それぞれのコメント入れ物・
      展開した文脈行は両側に同じ本文・切り替えボタンと再描画時のフォーカス手当て）
      対象: `templates/app.js`, `templates/style.css` / 根拠: design §4, decisions D1, D2, D9, research F8
      依存: T2, T3
      AC: AC1, AC2, AC3
- [x] T7: ファイル一覧のツリー（木の構築・子 1 つのディレクトリを畳む・`role="tree"` と矢印キー・
      ローミング `tabindex`・フラット ↔ ツリーの切り替え・移動時の `focus()`）
      対象: `templates/app.js`, `templates/style.css` / 根拠: design §5, decisions D10, research F7, F9
      依存: T2, T3
      AC: AC4, AC5, AC-I4
- [x] T8: コメント一覧（全スレッドの一覧・絞り込み 3 種と記憶・件数の告知・
      該当箇所へ移動＝折りたたみを開く ＋ `scrollIntoView` ＋ `focus()` ＋ 現在行の更新）
      対象: `templates/app.js`, `templates/style.css` / 根拠: design §6, research F6, F7
      依存: T3, T6
      AC: AC8, AC9, AC10, AC-I4
- [x] T9: キー割り当て（`s` / `[` / `]`）を既存の `onKeyDown` に足し、
      既存キーと標準操作を奪っていないことを実測する
      対象: `templates/app.js` / 根拠: design §7, decisions D8, 前 work review ラウンド1 の must
      依存: T5, T6, T7, T8
      AC: AC-I1, AC-I3, AC-I5
- [x] T10: `SKILL.md` を更新（3 ペイン・split・ツリー・テーマ・コメント一覧・キー操作・
      split で展開した文脈行の行番号が片側空になる限界）、`schema.md` に
      「画面の設定は記録に入らない」を明記
      対象: `SKILL.md`, `schema.md` / 根拠: decisions D9, AC15
      依存: T6, T7, T8
      AC: AC15
- [x] T11: 生成側のテストを足す（`__UI_JS__` が埋まる・`ui.js` は常に同梱・
      書き出した JSON に画面設定のキーが出ない・2 回生成のバイト一致）
      対象: `tests/test_diff_review.py` / 根拠: design「テスト方針」, decisions D5
      依存: T1, T3, T10
      AC: AC15, AC17
- [x] T12: `style.css` の暗の割り当て 2 ブロックの宣言列が一致することを検査するテスト
      対象: `tests/test_diff_review.py` / 根拠: decisions D3 の代償
      依存: T4, T11
      AC: AC6
- [x] T13: **画面の受け入れ確認（消化は test 工程）**。headless Chromium で
      split / ツリー / テーマ / コメント一覧 / 3 ペインの開閉とドラッグ / 狭い画面 /
      キー操作 / 既存機能の回帰 / 外部リクエスト 0 件を実測する
      対象: 未特定（test 工程で実施。検証スクリプトは test 工程内で書き捨てる）
      根拠: design「テスト方針」, research F2, F3, F6, F7（落とし穴 2 件の回帰化）
      依存: T4, T5, T6, T7, T8, T9
      AC: AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC8, AC9, AC10, AC11, AC12, AC13, AC14, AC16, AC17, AC-I1, AC-I2, AC-I3, AC-I4, AC-I5
