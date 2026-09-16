# タスク: diff-review-html の実装

## 実装方針

`design.md` の順に「**下から上へ**」組む——(1) git から差分を取って構造化する層、(2) 出力の規約
（UTF-8 / LF / 正規形 JSON / エスケープ）、(3) テンプレートと `html` サブコマンド、(4) 画面の挙動、
(5) 検証と一覧（`check` / `list` / `template`）、(6) 文書とテスト。

**不確実性の高い順ではなく、依存の浅い順に積む**——`research.md` で `file://` の制約・決定論・性能を
実測済みなので、この work に残っている不確実性は「実装の手間」だけで、見立てが外れて分解をやり直す
リスクは低い。唯一の例外は画面側のキーボードとフォーカス（T10）で、ここだけは実機（headless Chromium）で
確かめるまで確定しないため、**test 工程で消化するタスク（T20）を明示的に立てる**。

すべて新規ファイルなので、既存コードとの衝突は無い。`対象` は「新規作成」でも**具体的なパス**を書く
（探索の省略にはならないが、どのファイルに手を入れる回かが機械的に分かる）。

## 作業順序と依存関係

下の `依存:` に従う。それでは表せない順序の理由だけをここに書く。

- **T3（出力規約）を早い段階に置く**のは、決定論（AC9）とエスケープ（AC10）が**後から足せない性質**だから。
  書き出し口が増えてから規約を入れると、どこか 1 箇所が漏れて「同じ入力なのに出力が違う」が残る。
- **T4（page.html）と T5（style.css）は T6（html サブコマンド）より前**。テンプレートが無いと
  差し込み先が無く、`html` の出力を目視で確かめられない。
- **T19（テスト）は script 側が揃ってから**。先に書くと、確定していない CLI の形に合わせて
  書き直すことになる。画面側は T20（test 工程）が受け持つ。

## リスク / 留意点

- **差分パースの取りこぼし**（リネーム・モード変更・バイナリ・新規/削除）。`git diff --raw -z` の
  status 文字を正典にし、本文のヘッダ行からは推測しない（`research.md` F9）。
- **`</script>` の混入**（`research.md` F6 の実測）。埋め込みは `<`→`<` の退避を通すこと。
  T3 で 1 箇所に閉じ込め、T6 / T14 はそれを呼ぶだけにする。
- **Windows での改行**（`decisions.md` D13）。`open()` / `sys.stdout` の `newline` を明示しないと
  CRLF になり AC9 が OS で壊れる。T3 で固定する。
- **localStorage の共有**（`research.md` F1）。キーに `diff_digest` を含め忘れると、別レビューの
  下書きが混ざる。T13 の最重要点。
- **キーボードのショートカット漏れ**（AC-I5）。入力欄にフォーカスがある間の早期 return を忘れると、
  コメント本文に `c` や `f` を打った瞬間に画面が動く。T10 で必ずテストする。

## テスト方針

- **script 側（T19、stdlib `unittest`）**: 一時 git リポジトリを作って差分を生成し、
  ①パース結果の構造、②同一入力の 2 回生成が**バイト一致**（AC9）、③`<script>` を含む差分の
  エスケープ（AC10）、④`check` が壊れた JSON を終了コード 3 で落とすこと（AC11）、
  ⑤`list` の text / tsv 出力（AC12）、⑥日本語パス・本文の往復（AC15）、
  ⑦出力が LF・UTF-8 固定であること（バイト列で検査）。
- **画面側（T20、test 工程）**: この環境に同梱の headless Chromium で `file://` の生成物を開き、
  コメント 3 階層・返信・解決（AC3 / AC4）、pending → submit（AC5）、
  書き出し → 読み込み → 再書き出しのバイト一致（AC7）、下書きの復元と破棄（AC16）、
  キーボード経路とフォーカス復帰（AC-I1〜I5）を確かめる。
  **skill 自体は Chromium を要求しない**（テスト側の都合）。
- 受け入れ基準と検証手段の対応は `requirements.md` の ID で辿る（`aidev coverage`）。

## タスク

- [x] T1: `git` から差分を取得し、ファイル / ハンク / 行に構造化する層を書く（`--raw -z` の status・blob と
      `--numstat -z` の行数を突き合わせ、バイナリ・リネーム・新規・削除・モード変更を保持する）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` （新規作成） / 根拠: research F9
      依存: なし
      AC: AC1, AC2, AC15
- [x] T2: 差分の identity（`base_commit` / `diff_digest` / ファイルごとの blob）を算出して `target` を組み立てる
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` （新規作成） / 根拠: research F10
      依存: T1
      AC: AC6
- [x] T3: 出力規約の共通基盤を書く（UTF-8・LF 固定の書き出し、正規形 JSON ダンプ、HTML エスケープ、
      埋め込み用の `<`→`<` 退避）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` （新規作成） / 根拠: research F6, F8
      依存: なし
      AC: AC9, AC10, AC15
- [x] T4: `templates/page.html` を書く（プレースホルダ、ヘッダ・ファイル一覧・差分本体・提出パネルの骨格）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/page.html` （新規作成）
      依存: なし
      AC: AC1, AC2
- [x] T5: `templates/style.css` を書く（追加/削除の色分け、折りたたみ、ライト/ダーク両対応）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/style.css` （新規作成）
      依存: T4
      AC: AC2
- [x] T6: `html` サブコマンドを実装する（テンプレート差し込み、`--out` / 標準出力、`--title` / `--context`、
      CSS/JS の埋め込み）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` （新規作成）
      依存: T1, T2, T3, T4, T5
      AC: AC1, AC2, AC9
- [x] T7: `templates/app.js` に差分描画を書く（`textContent` のみで描画、ファイル折りたたみ、
      大きいファイルの遅延展開）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` （新規作成）
      依存: T4, T6
      AC: AC2, AC10
- [x] T8: コメントの 3 階層（行 / ファイル / 全体）・返信・解決を実装する（内部状態は JSON と 1:1）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` （新規作成）
      依存: T7
      AC: AC3, AC4
- [x] T9: pending → submit のフローを実装する（Approve / Request changes / Comment ＋ サマリ、
      コメントの取り消し、レビューの破棄）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` （新規作成） / 根拠: research F11
      依存: T8
      AC: AC5, AC-I2
- [x] T10: キーボード操作とフォーカス管理を実装する（`j`/`k`・`c`・`Esc`・修飾キー＋`Enter`・`f`・`r`・`?`、
      `aria-expanded`、入力欄での早期 return、閉じたらトリガへフォーカス復帰）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` （新規作成） / 根拠: research F13, F15
      依存: T8, T9
      AC: AC-I1, AC-I2, AC-I3, AC-I4, AC-I5
- [x] T11: JSON の書き出しを実装する（正規形での直列化、Blob ダウンロード、コピー用テキストエリア、
      時刻を含まないファイル名）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` （新規作成） / 根拠: research F4
      依存: T8, T9
      AC: AC6, AC7, AC9, AC15
- [x] T12: JSON の読み込みを実装する（ファイル選択とドラッグ＆ドロップ、画面側の検証、
      identity 不一致の警告帯と「位置不明」欄。`fetch` は使わない）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` （新規作成） / 根拠: research F3
      依存: T11
      AC: AC7, AC8, AC11
- [x] T13: 下書きの保存・復元・破棄を実装する（キーに `diff_digest` を含める、try/catch、
      使えないブラウザでの明示、未書き出し時の `beforeunload` 警告）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` （新規作成） / 根拠: research F1, F2
      依存: T8
      AC: AC16
- [x] T14: `template` サブコマンドと `html --import` を実装する（雛形の出力、埋め込み前の検証、
      不合格なら生成せず終了コード 3）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` （新規作成）
      依存: T6, T15
      AC: AC8, AC11
- [x] T15: `check` サブコマンドを実装する（構造・値域・参照整合・ID 重複、JSON パス付きの診断、
      終了コード 3、`--repo` 指定時の identity 突き合わせは警告のみ）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` （新規作成）
      依存: T2, T3
      AC: AC11
- [x] T16: `list` サブコマンドを実装する（既定は未解決のみ、`--all`、`text` / `tsv` 出力）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` （新規作成）
      依存: T3, T15
      AC: AC12
- [x] T17: `schema.md` を書く（レビュー記録 JSON の正典。フィールド・値域・正規形・GitHub 語彙との対応）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/schema.md` （新規作成）
      依存: T11, T15
      AC: AC6, AC13
- [x] T18: `SKILL.md` を書く（frontmatter とトリガ語、3 機能の使用例、`python3` / `py -3` の併記、
      Windows での注意、`schema.md` への導線）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/SKILL.md` （新規作成） / 根拠: research F18, F19
      依存: T16, T17
      AC: AC13, AC14
- [x] T19: script のテストを書く（`unittest`。一時 git リポジトリでの差分パース、2 回生成のバイト一致、
      エスケープ、`check` の不合格系、`list` の出力、日本語の往復、LF・UTF-8 の固定）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/tests/test_diff_review.py` （新規作成）
      依存: T6, T15, T16
      AC: AC9, AC10, AC11, AC12, AC14, AC15
- [x] T20: **画面の受け入れ確認（消化は test 工程）**。headless Chromium で `file://` の生成物を開き、
      3 階層コメント・返信・解決、pending → submit、書き出し→読み込み→再書き出しの一致、
      下書きの復元と破棄、キーボード経路とフォーカス復帰を確かめる（`decisions.md` D14）
      対象: 未特定（test 工程で実施。検証スクリプトは test 工程内で書き捨てる）
      依存: T10, T12, T13
      AC: AC3, AC4, AC5, AC7, AC16, AC-I1, AC-I2, AC-I3, AC-I4, AC-I5
