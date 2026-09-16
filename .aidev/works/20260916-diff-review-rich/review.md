# レビュー記録

## タスク点検ログ（coding 工程内・「3.3」(b)）

`cross`（タスクをまたぐ不変条件の点検・same_session・ラウンド 1）で見つけ、その場で直したもの。

- [should][conv:-] **文書と実装が食い違っていた**。`decisions.md` D7 と `SKILL.md` は
  「`--expand-max-lines` を超えるファイルは**展開もハイライトもされない**」と書いていたが、
  実装はハイライトを続ける（実測: `expand_max_lines=10` でも `truncated: True` のまま
  差分行に `tokens` が付き、`expand_max_lines=0` でも付く）。
  タスク単位では見えない——T2（ハイライト）と T3（展開）と T20（文書）の 3 つにまたがる。
  / 対応: 修正済（**実装を正とし、文書を直した**。ハイライトは差分行にしか乗らず容量が小さいのに対し、
  展開データは全文ぶんで重い。重い方だけを落とす現実装が妥当）
- [nit][conv:-] `richdiff.py` の `RICH_EXT` と `MERMAID_SUPPORTED` が定義だけで未使用
  （判定は `rich_kind()` と `mermaid_svg()` の中にある）。前 work の `sha_of` / `git_text` と同じ取り残し。
  / 対応: 修正済（削除）

## ラウンド 1（2026-09-16T04:27:09Z）

- [should][conv:-] `templates/app.js` の `expandAll` が**フォーカスを落とす**。
  実測（headless Chromium）: 行にフォーカスした状態で `Shift`+`E` を押すと、展開後の
  `document.activeElement` が `BODY` になる（`e` の場合は `redrawFile` が行を指し直すので
  `.row.expanded` に残る）。requirements の **AC-I4「展開後もフォーカスが失われない」**に反する。
  キーボードだけで操作している人は、ここで現在位置を見失う。 / 対応: 差し戻し（coding）

以下は確認して**指摘なし**と判断した:

- 被覆は tasks 承認時と同じ（ac=27 / tasks=27 / gaps=0）。coding 中に `AC:` の無いタスクは増えていない。
- **Markdown の引用の遅延継続**（`> 引用` の次行に空行なしで本文が続くと引用に取り込まれる）は
  CommonMark / GitHub と同じ挙動なので**正しい**。指摘にしない。
- 入れ子リスト・画像のテキスト落とし・`javascript:` リンクの非アンカー化を実測で確認。
- **削除ファイル**（`status: D`）では展開側が `old` になり、削除行のトークンが展開データから引けている
  （二重持ちの排除が片側だけの実装になっていないことの確認）。
- `list --severity none` / `--severity must` / `--notes` の絞り込みが実測どおり効く。
- 前 work のレビューで must になった **Enter の横取り**は再発していない（AC-I5a が pass）。
  今回足した `e` / `Shift+E` / `t` も、入力欄とボタンの標準操作を奪っていないことを実測済み。

## ラウンド 2（2026-09-16T04:28:57Z）

**指摘なし**（must / should / nit いずれも 0 件）。

- ラウンド 1 の should（「すべて展開」でフォーカスが落ちる）は解消。実測: `Shift`+`E` のあとも
  `document.activeElement` が `BODY` にならない。**この検査を受け入れ確認に恒久化した**（AC-I4）。
- **前ラウンドの修正に由来する再発が無いか**を確認した: 同じ不変条件（「描き直しても現在位置を失わない」）を
  支える箇所は `redrawFile` / `expandAll` / `toggleView` / `toggleFile` の 4 つ。
  前 2 つは指し直しを実装済み、後ろ 2 つは押したボタン自身にフォーカスが残る（ボタンは再描画されない）ことを確認した。
- **最小構成**（`--rich off --expand-max-lines 0`）でも画面が壊れないことを実測（84.5KB・コメントも書ける）。
- 削除ファイル（展開側が `old`）でトークンが引けることを確認——二重持ちの排除が片側だけの実装に
  なっていない。
- `console.log` / `TODO` / `FIXME` の残骸なし。被覆は tasks 承認時と同じ（ac=27 / gaps=0）。
- レビュー補助（`walkthrough.md`）は**書いた**（新規 3 ファイル＋大きな変更で「差分が大きい」に該当）。

通算: must 0 / should 1 / nit 0（すべて解消済み）。
（coding の cross 点検で潰した 2 件は「タスク点検ログ」節にあり、この件数には数えない）
