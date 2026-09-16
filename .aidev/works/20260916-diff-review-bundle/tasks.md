# タスク: バンドルとビューアの分離

## 実装方針

**形式 → 生成側 → 画面 → 参照専用**の順に積む。逆にすると、画面が読む形が決まる前に
画面を書くことになり、取り込み口を後から作り直すことになる。

1. バンドルの形（T1）と検証（T2）——**ここが決まらないと誰も何も読めない**。
2. 生成側の出口（T3 `bundle` / T4 `view`）と入口（T5 `check`/`list` の拡張）。
3. CLI の整理（T6 `--from`）——既存フラグを壊さないことが要。
4. 画面（T7 差し替え可能化 → T8 取り込み口 → T9 失敗の見せ方）。
5. 参照専用（T10 HTML / T11 JS）。
6. 文書（T12）とテスト（T13・T14）、画面の受け入れ確認は test 工程で（T15）。

**各タスクの終わりに既存の性質を確認する**（決定論・`textContent` 描画・UTF-8/LF・依存ゼロ・
**既存 60 件のテストが通ったままであること**）。

## 作業順序と依存関係

下の `依存:` に従う。それでは表せない順序の理由だけをここに書く。

- **T7（`diffData` を差し替え可能にする）を T8 より前に**。いま `diffData` はモジュール先頭で
  1 回だけ確定している。差し替えられないまま取り込み口だけ足すと、
  「読み込んだのに前の差分が出ている」という直しにくい状態になる。
- **T6（CLI）を T3・T4 の後に**。新しいサブコマンドが出そろう前に引数を整理すると、
  取得元の軸を 2 回設計し直すことになる。
- **T10（HTML を積まない）と T11（JS が作らない）は対**。片方だけだと
  「ボタンは無いがキーで開ける」「ボタンはあるが押しても何も起きない」のどちらかになる。
- **T13 と T14 を分けているのは、依存先が違うから**。T13 は形式と新サブコマンド（T1〜T5）に、
  T14 は CLI の整理と参照専用（T6・T10）に依存する。1 本にすると、
  前半が書けているのに後半の依存待ちで着手できない、という止まり方をする。

## リスク / 留意点

- **R1（research R1・この work の中心）**: `<script src>` はバンドルを**実行する**。
  焼き込みは `--load` を明示したときだけ。**既定で読む形は作らない**（T4 の検査点）。
- **R2（research R2）**: `postMessage` の送り主は `file://` では検査できない。
  **受け取ったものは必ず検証**してから使う（T8）。
- **R3（research R4）**: 形式が 2 つ（記録とバンドル）になる。
  バンドルは記録を**内側にそのまま持つ**ので、検証は既存 `validate()` へ委譲する（T2）。
- **R4**: `diffData` の差し替えは、`target` / `storageKey` / `viewModes` / `expandState` /
  `collapsed` の初期化に波及する。**取りこぼすと前の差分の状態が残る**（T7 の検査点）。
- **R5**: `U+2028` / `U+2029` の退避を忘れると、古いエンジンで**バンドルが構文エラーになる**（T1）。
- **R6**: `node` が無い環境がある。T13 の Node 検査は**見つからなければ skip**（全体を落とさない）。
- **R7**: 参照専用は**容量をほとんど減らさない**（`app.js` は残る）。
  「軽くなる」と書かないこと（T12）。

## テスト方針

- **生成側（T13・T14・stdlib `unittest`）**: バンドルの往復（生成 → `parse_bundle` → 一致）、
  **Node で実行せずに読める**（`subprocess` で `node -e`。無ければ skip）、
  `U+2028`/`U+2029` の退避、`check`/`list` がバンドルを受ける、`--from` の全値と矛盾検出、
  `--from github-pr` の終了コード、`--readonly` で導線が HTML に無い、`view` の中身
  （`files` が空・`rich.js` が入る・`--load` でだけ `<script src>` が入る）、
  **既存 60 件が通ったまま**、2 回生成のバイト一致。
  （`html` の出力そのものは、テンプレートに口が増える分**バイト単位では変わる**。
  約束するのは意味の不変であって、バイト単位の不変ではない。）
- **画面（T15・test 工程・headless Chromium・`file://`）**: 4 つの取り込み口、
  壊れたバンドル・別形式の扱い、読み込み後のフォーカス、下書きがバンドルごとに分かれること、
  参照専用で読む機能が動き書く機能が**DOM に無い**こと、既存 75 件の回帰、外部リクエスト 0。

## タスク

- [x] T1: バンドルの形（`bundle_text` / `parse_bundle`。前後固定・正規形・`U+2028`/`U+2029` 退避）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: design §1, research F2
      依存: なし
      AC: AC1, AC2, AC14
- [x] T2: バンドルの検証（`validate_bundle`。外側の形 ＋ 内側は既存 `validate()` へ委譲）
      対象: 同上 / 根拠: design §1, research R4
      依存: T1
      AC: AC3
- [x] T3: `bundle` サブコマンド（差分を取り、`--import` で記録を同梱して 1 ファイルに）
      対象: 同上 / 根拠: design §4
      依存: T1
      AC: AC1, AC2
- [x] T4: `view` サブコマンド（差分を持たないビューア・`rich.js` を常に積む・
      `--load` を指定したときだけ `<script src>` を焼き込み、**CLI が警告を出す**）
      対象: 同上 ＋ `templates/page.html` / 根拠: design §3, research F5, R1
      依存: T1
      AC: AC4, AC15
- [x] T5: `check` / `list` がバンドルも受ける（**拡張子ではなく中身で判別**）
      対象: 同上 / 根拠: design §4
      依存: T2
      AC: AC3
- [x] T6: 取得元を `--from` ＋ `--rev` に整理（既存フラグは別名として残し、**同時指定は矛盾として落とす**。
      `--from github-pr` は「未対応」＋終了コード 1）
      対象: 同上 / 根拠: design §4
      依存: T3, T4
      AC: AC8, AC9, AC12
- [x] T7: 画面: `diffData` を**差し替え可能**にする（`boot()` で確定させ、
      `target` / `storageKey` / `viewModes` / `expandState` / `collapsed` を組み直す）
      対象: `templates/app.js` / 根拠: design §2「既存コードへの影響」, リスク R4
      依存: なし
      AC: AC2, AC-I2
- [x] T8: 画面: 取り込み口 4 つ（`window.__DIFF_REVIEW_BUNDLE__` / 埋め込み / `postMessage` /
      ファイル選択・D&D）と `adoptBundle`（**必ず検証 → 差し替え → 再描画 → フォーカス**）
      対象: `templates/app.js` ＋ `templates/page.html` / 根拠: design §2, research F1, F3, R2
      依存: T7
      AC: AC5, AC6, AC-I1, AC-I3, AC-I4
- [x] T9: 画面: 取り込みに失敗したときの見せ方（理由を出す・**いまの表示を壊さない**・
      バンドルが無いときの案内）
      対象: `templates/app.js` / 根拠: design §2, 要件 F6b
      依存: T8
      AC: AC7
- [x] T10: 参照専用（HTML を積まない）: `page.html` に `<!-- rw:begin/end -->` を置き、
      `--readonly` のとき**置換より前に**切り落とす
      対象: `templates/page.html` ＋ `diff_review.py` / 根拠: design §5(a)
      依存: T4
      AC: AC10
- [x] T11: 参照専用（JS が作らない）: `readonly` のとき `+` ボタン・返信・解決・取り消しを作らず、
      `c` / `Enter` / `r` を受け付けない。**読む機能は分岐に入れない**
      対象: `templates/app.js` / 根拠: design §5(b)
      依存: T10
      AC: AC10, AC11, AC-I5
- [x] T12: `SKILL.md` / `schema.md` を更新（バンドルの形・拡張子・4 つの取り込み口・`--from`・
      `view` / `bundle`・参照専用の**目的は容量ではない**こと・
      **VSCode 拡張との契約**と「未検証」の明示）
      対象: `SKILL.md`, `schema.md` / 根拠: design §6, リスク R7
      依存: T5, T6, T9, T11
      AC: AC15
- [x] T13: 生成側のテスト（バンドルの往復・**Node で実行せずに読める**（無ければ skip）・
      退避・`check`/`list`・`view` の中身・`--load` の有無）
      対象: `tests/test_diff_review.py` / 根拠: design「テスト方針」, リスク R6
      依存: T1, T2, T3, T4, T5, T12
      AC: AC1, AC2, AC3, AC4, AC14, AC15
- [x] T14: 生成側のテスト（`--from` の全値・矛盾検出・`github-pr` の終了コード・
      `--readonly` の HTML・**既存 60 件が通ったまま**・2 回生成のバイト一致）
      対象: 同上 / 根拠: design「テスト方針」
      依存: T6, T10, T13
      AC: AC8, AC9, AC10, AC12, AC13
- [x] T15: **画面の受け入れ確認（消化は test 工程）**。headless Chromium で
      4 つの取り込み口・失敗の扱い・フォーカス・下書きの分離・参照専用・既存 75 件の回帰・
      外部リクエスト 0 を実測する
      対象: 未特定（test 工程で実施。検証スクリプトは test 工程内で書き捨てる）
      根拠: design「テスト方針」, research F1, F3
      依存: T8, T9, T11
      AC: AC5, AC6, AC7, AC11, AC13, AC-I1, AC-I2, AC-I3, AC-I4, AC-I5
