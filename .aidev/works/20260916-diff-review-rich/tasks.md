# タスク: rich diff・ハイライト・文脈展開・レビュー語彙の追加

## 実装方針

**生成側（Python）を先に固め、その出力を画面が描く**という依存の向きどおりに積む。
画面の仕事は「渡された構造を描く」だけなので、生成側が出す形が決まらないと画面は書けない。

1. 全文の取得（T1）——ハイライトも展開も rich も、ここが無いと何も始まらない。
2. 生成側の 3 機能（T2 ハイライト / T3 展開データ / T4〜T7 rich）と条件付き同梱（T8）。
3. スキーマ `/2` と検証・`list`（T9・T10）——画面より先に、記録の形を確定させる。
4. 画面（T11〜T19）。
5. 文書（T20）とテスト（T21）、画面の受け入れ確認は test 工程で（T22）。

**既存の性質を壊さないことを各タスクの終わりに確認する**（決定論・XSS 非解釈・LF/UTF-8・依存ゼロ）。
前 work の deliver 後に踏んだ「自分自身を入力にすると壊れる」欠陥があるので、
**この skill 自身の差分**をテストの入力に含める（`design.md`「申し送り」）。

## 作業順序と依存関係

下の `依存:` に従う。それでは表せない順序の理由だけをここに書く。

- **T9（スキーマ）を画面より前に置く**。`kind` / `severity` の形が決まる前に画面を書くと、
  画面側の内部状態と JSON の対応を後から作り直すことになる（前 work で往復を避けられた理由がこれ）。
- **T8（条件付き同梱）は rich の 4 形式が出そろってから**。先に作ると「対象があるか」の判定条件が
  形式ごとに増えて、分岐が二重になる。
- **T19（キー割り当て）は画面が出そろってから**。前 work の must（Enter の横取り）は
  「キーを足した時点では気づけず、他の操作と組み合わせて初めて壊れる」類なので、最後にまとめて実測する。

## リスク / 留意点

- **容量**（`research.md` R1）: 展開データは全テキストファイルが対象。`--expand-max-lines` の既定 2,000 行を
  超えるファイルを持つリポジトリで、生成物がどれだけ育つかを T21 で測る。
- **ハイライトの行またぎ**（R3）: 全文を 1 回トークナイズしてから行に切る。差分行に個別に当てない。
- **PDF は取れないことがある**（R2）: 取れなかった経路を必ずテストする（理由が出ること）。
- **iframe の `sandbox=""` を外さない**（F3）: `allow-scripts` を足した瞬間に XSS の経路になる。
- **rich データも `<` の退避を通す**: 埋め込み口が 2 つ増えるので、退避を通す関数を 1 箇所に保つ。
- **キー割り当ての衝突**（R5）: `e` / `Shift+e` / `t` が入力欄・ボタンの標準操作を奪わないこと。

## テスト方針

- **生成側（T21・stdlib `unittest`）**: 一時 git リポジトリに CSV / Markdown（mermaid ＋ alert）/ HTML /
  PDF / コード（python・js）を置き、①全文取得と片側 null、②ハイライトの行またぎ（docstring）、
  ③展開データの上限と `truncated`、④rich 各形式の payload、⑤条件付き同梱（対象なしで `rich.js` が
  埋まらない）、⑥`/2` の検証と `/1` 互換、⑦`list --severity` / `--notes`、⑧決定論（2 回生成でバイト一致）、
  ⑨容量（rich あり/なしの差、`--expand-max-lines 0` で前 work 相当）。PDF は Chromium で生成する。
- **画面側（T22・test 工程）**: headless Chromium で、展開（段階・全展開・端で消える）、rich↔source、
  重大度、コメント単位の返信、レビュー開始と提出、説明コメント、`/1` の読み込み、
  キー割り当てが標準操作を奪わないこと、往復のバイト一致を実測する。
- **入力にこの skill 自身の差分を含める**（自己適用で壊れないこと）。

## タスク

- [x] T1: 両側の全文を取得する層を書く（`git show <rev>:<path>` / index / 作業ツリー、バイト列で受けて
      NUL でバイナリ判定、片側が無い場合は `null`）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: research F6
      依存: なし
      AC: AC2, AC13
- [x] T2: シンタックスハイライト（拡張子 → 言語、全文を 1 回トークナイズして行に切り、`tokens` を付ける。
      python / javascript / typescript / json / yaml / shell / css / html / markdown / sql）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: research F5, R3
      依存: T1
      AC: AC1, AC2, AC3
- [x] T3: 展開データ（`--expand-max-lines`、上限超過は `truncated: true` で空、展開側の決定）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: research F6, decisions D3
      依存: T1
      AC: AC11, AC12, AC13
- [x] T4: rich（CSV / TSV）: 行を対応付けてセル単位の変更を出す
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: research F4
      依存: T1
      AC: AC4
- [x] T5: rich（Markdown）: 見出し・段落・リスト・表・コード・引用・リンク・**alert 記法**をノード木に。
      属性は白名簿、`href` のスキームを検査する
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` （新規モジュール可）
      依存: T1
      AC: AC5
- [x] T6: rich（mermaid）: `flowchart` / `graph` / `stateDiagram` / `sequenceDiagram` を SVG に描き
      `data:image/svg+xml;base64,` で貼る。対象外の図種はコード＋注記
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: research F7, decisions D6
      依存: T5
      AC: AC6
- [x] T7: rich（HTML / PDF）: HTML は生文字列を payload に、PDF は `zlib` ＋ ToUnicode CMap でテキスト復元し
      差分を出す（取れなければ理由）。ページ数とバイト数は常に出す
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: research F2, F3, decisions D5
      依存: T1
      AC: AC7, AC8
- [x] T8: 条件付き同梱（`__RICH_JS__` / `__RICH_DATA__`、`--rich auto|off`、対象が無ければ空にする）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: decisions D4
      依存: T4, T5, T6, T7
      AC: AC9
- [x] T9: スキーマ `diff-review/2`（`threads[].kind` / `comments[].severity`）と検証・`/1` 互換（生成側）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: decisions D8, D9
      依存: なし
      AC: AC15, AC19, AC21
- [x] T10: `list` に重大度を出し、`--severity` と `--notes` を足す
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py`
      依存: T9
      AC: AC16
- [x] T11: 画面: `tokens` を `span.tok-*` で描き、追加/削除の背景色と両立させる（配色は CSS 変数）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` ＋ `templates/style.css`
      依存: T2
      AC: AC1, AC2
- [x] T12: 画面: 文脈の段階展開（1 回 20 行・端で消える・「すべて展開」・`truncated` の理由表示・
      既存の折りたたみ（`LAZY_LINE_LIMIT`）との統合）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js`
      依存: T3
      AC: AC11, AC12, AC13, AC14
- [x] T13: 画面: rich の描画（ノード木 → DOM / 表 / `iframe sandbox=""` / `img`）と rich↔source 切り替え
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/rich.js` （新規作成）
      依存: T8
      AC: AC4, AC5, AC6, AC7, AC8, AC10
- [x] T14: 画面: 重大度の選択（`<select>`）・バッジ表示・記録への反映
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js`
      依存: T9
      AC: AC15, AC-I2
- [x] T15: 画面: コメント単位の返信（返信への返信を含む）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js`
      依存: T9
      AC: AC17
- [x] T16: 画面: 「レビューを開始」と提出バー（Approve / Request changes / Comment は既存を流用）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` ＋ `templates/page.html`
      依存: T14
      AC: AC18
- [x] T17: 画面: 説明コメント（`kind: "note"`・提出対象外・解決ボタンを出さない・バッジ）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js`
      依存: T14
      AC: AC19, AC20
- [x] T18: 画面: `/1` の読み込み互換と、画面側検証を生成側 `validate` と対にする
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js`
      依存: T9, T14, T17
      AC: AC21, AC22
- [x] T19: 画面: キー割り当て（`e` / `Shift+e` / `t`）と、既定操作を奪っていないことの実測
      対象: `docs/ClaudeCode/skills/other/diff-review-html/templates/app.js` / 根拠: 前 work review ラウンド1 の must
      依存: T12, T13
      AC: AC-I1, AC-I3, AC-I4, AC-I5
- [x] T20: `schema.md` と `SKILL.md` を更新（`/2`・新フラグ・rich の対応範囲と限界・キー操作）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/schema.md` ＋ `SKILL.md`
      依存: T10, T13, T17
      AC: AC5, AC6, AC8, AC16, AC21
- [x] T21: 生成側のテストを足す（全文 / ハイライトの行またぎ / 展開の上限 / rich 各形式 / 条件付き同梱 /
      `/2` 検証と `/1` 互換 / `list` の絞り込み / 決定論 / 容量。**この skill 自身の差分も入力にする**）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/tests/test_diff_review.py`
      依存: T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T20
      AC: AC1, AC3, AC4, AC5, AC6, AC7, AC8, AC9, AC16, AC21, AC22
- [x] T22: **画面の受け入れ確認（消化は test 工程）**。headless Chromium で展開・rich↔source・重大度・
      返信・レビュー開始・説明コメント・`/1` 読み込み・キー割り当て・往復の一致を実測する
      対象: 未特定（test 工程で実施。検証スクリプトは test 工程内で書き捨てる）
      依存: T11, T12, T13, T14, T15, T16, T17, T18, T19
      AC: AC10, AC11, AC12, AC13, AC14, AC15, AC17, AC18, AC19, AC20, AC-I1, AC-I2, AC-I3, AC-I4, AC-I5
