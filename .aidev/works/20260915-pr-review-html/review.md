# レビュー記録

## タスク点検ログ（coding 工程内・「3.3」(b)）

`cross`（タスクをまたぐ不変条件の点検・same_session・ラウンド 1）で見つけ、その場で直したもの。

- [should][conv:-] `templates/app.js:validateRecord` 画面側の検証が `diff_review.py:validate` より緩く、
  **CLI が exit 3 で落とす記録（`state: "LGTM"`）を画面が黙って受け入れて、そのまま書き出していた**
  （headless Chromium で再現: バナー 0 件・スレッド 3 件・再書き出しに `"LGTM"` が残存）。
  同じ規則を支える判定が 2 箇所に散っていて片方だけ緩いという、タスク単位では見えない欠陥。
  / 対応: 修正済（判定を Python 側と対にし、値域・参照・重複・空本文まで見るようにした。
  再実測でバナー 1 件・スレッド 0 件・`"LGTM"` 残存なしを確認）
- [nit][conv:-] `diff_review.py` 定義だけで一度も呼ばれていない `sha_of()` と、そのための
  `hashlib` の import が残っていた（identity は `git hash-object` に一本化したため不要）
  / 対応: 修正済（関数と import を削除。28 件のテストは緑のまま）

## ラウンド 1（2026-09-16T02:14:11Z）

- [must][conv:-] `templates/app.js` の `onKeyDown` が **Enter をページ全体で横取り**している。
  入力欄以外にフォーカスがあると `event.preventDefault()` してから「現在行のコメント欄を開く」ため、
  **ボタンを Enter で押せない**。実測（headless Chromium）: 「解決にする」にフォーカスして Enter →
  `resolved=0` のまま行のコメント欄が開く（`composer_opened_instead: 1`）。
  「レビューを提出」も Enter で開かない（`submit_panel_hidden_after_enter: true`）。
  requirements の AC-I3「提出（submit）まで同様に到達できる」と AC-I5「既存の操作を妨げない」に反する
  （T20 の受け入れ確認はショートカット `r` で提出パネルを開いていたため、この経路を踏んでいなかった）。
  / 対応: 差し戻し（coding）
- [nit][conv:-] `diff_review.py` の `git_text()` が定義だけで未使用（`git_bytes` に一本化済み）。
  cross 点検で消した `sha_of` と同じ取り残し。 / 対応: 差し戻しのラウンドで併せて修正
- [nit][conv:-] `templates/app.js` の `adoptRecord` が `seq = threads.length + 1000` で採番を始めるため、
  読み込んだ記録が `t1001` / `c1001` のような id を持つと**セッション中の新規 id と衝突**しうる
  （衝突すると同一スレッド内の `in_reply_to` の対応付けが狂う）。既存 id の最大値から採番すべき。
  / 対応: 差し戻しのラウンドで併せて修正
- [nit][conv:-] `diff_review.py` の `parse_hunk_header()` が解析に失敗したとき `(0, 0)` を黙って返す。
  壊れた `@@` 行に当たると**行番号が静かに 0 始まりになる**（コメントの位置がずれる）。
  / 対応: 差し戻しのラウンドで併せて修正（読めない場合は明示的に落とす）

被覆: `aidev coverage --strict` は tasks 承認時と同じ（ac=21 / tasks=21 / gaps=0）。
価値適合: 「AI の差分を人間が読んで指摘を JSON で返す」経路は T20 で実測済み。must はその経路の
**キーボード操作**にあり、目的（マウス無しで完結する読み書き）に直接効くので nit に落とさない。
規約適合: このリポジトリに AGENTS.md / CLAUDE.md / `.aidev/conventions` は無いため、全て `[conv:-]`。

## ラウンド 2（2026-09-16T02:18:02Z）

ラウンド 1 の must（Enter の横取り）と nit 3 件は修正済み。実測で確認した:
`resolved_after_enter: 1` / `composer_opened_instead: 0` / 提出パネルも Enter で開く。
**この指摘が前ラウンドの修正に由来しないか**も見た——同じ不変条件（「ページ側のキー処理が
ブラウザ標準の操作を奪わない」）を支える項は `Enter` / `c` / `j` / `k` / `f` / `r` / `?` の 7 つで、
入力欄の早期 return（AC-I5）と合わせて全て確認した。Enter 以外はブラウザの標準操作と衝突しない。

- [should][conv:-] `templates/app.js` の描画が、**差分が 0 件のときに何も言わない**。
  実測（`--staged` で空の差分）: `#filelist` も `#files` も空文字で、画面上の手掛かりは
  ヘッダの「0 ファイル」だけ。`design.md`「エラー処理 / 異常系」は
  「差分が空 → HTML は生成するが**「差分なし」を明示**（レビュー記録の読み込みはできる）」と
  定めており、実装がそこに届いていない（design と実装の乖離）。 / 対応: 差し戻し（coding）

以下は確認して**指摘なし**と判断した:

- 異常系の終了コードは design のとおり（git 外 = 2 / 不正リビジョン = 2 / 引数なし = 1 / 正常 = 0）。
- 生成物にテンプレートの置換漏れ（`__…__`）は 0 件。`console.log` / `TODO` / `FIXME` の残骸も無い。
- 被覆は tasks 承認時と同じ（ac=21 / tasks=21 / gaps=0）。coding 中に `AC:` の無いタスクは増えていない。
- 価値適合: 「AI の指摘を人間が画面で読んで返す」「人間の指摘を AI が JSON で受け取る」の両方向を
  T20 で実測済み（`from-ai.html` と `list --format tsv`）。

## ラウンド 3（2026-09-16T02:19:47Z）

**指摘なし**（must / should / nit いずれも 0 件）。

- ラウンド 2 の should（空差分で画面が無言）は解消。実測: `#files` に「差分がありません…」、
  `#filelist` に「変更ファイルなし」が出る（受け入れ確認 `AC2b` として恒久化した）。
- **前ラウンドの修正に由来する再発が無いか**を確認した: 空差分の早期 return を足した 2 箇所
  （`renderFileList` / `renderFiles`）は、`renderThreads` が参照する `[data-threads]` の置き場を
  消さない（全体コメントの置き場は `#overall` 側にあり、ファイル側の置き場が無いときは
  `slotFor` が「位置不明」へ落とす）。空差分に記録を読み込んでも例外が出ないことを実測した。
- 決定論・被覆・終了コードを再確認: 2 回生成が `cmp` で一致、`coverage --strict` が
  tasks 承認時と同じ（ac=21 / tasks=21 / gaps=0）、終了コードは 0/1/2/3 とも design どおり。
- レビュー補助（`walkthrough.md`）は**書いた**——新規 8 ファイル・約 2,560 行で
  「差分が大きい」に当たる（`aidev-60-review`「レビュー補助」条件1）。

通算: must 1 / should 1 / nit 3（すべて解消済み）。
