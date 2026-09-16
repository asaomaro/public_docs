# レビュー記録

## ラウンド 1

- [should][conv:-] **アイコンボタンの「選択中」配色が意図せず広がっていた**。`style.css` に足した
  `.icon-btn[aria-pressed="true"], .icon-btn[aria-expanded="true"] { border-color: var(--accent); ... }`
  は `btn-tree`（アイコン化した切り替えボタン）を狙ったものだったが、**クラスセレクタなので
  同じ `icon-btn` を持つ `.file-toggle`（ファイルの折りたたみ）や `#btn-pane-left/right`（ペイン開閉）
  にも当たってしまう**。これらは `aria-expanded="true"` が**既定の状態**（畳んでいない・開いている）
  を指すので、実測（headless Chromium・`getComputedStyle`）では**ほとんどのファイルの折りたたみ
  アイコンが常時アクセントカラーになる**——「選ばれている」の意味を失い、ただの見た目のノイズになる。
  design.md の F5 表には配色の指定はなく、この装飾は実装時に独自に足したもの（要求されていない）。
  / 対応: 修正済（**最小の対象へ絞った**。既定で true になるボタン（`.file-toggle` / ペイン開閉）には
  付けず、既定が false で「いま開いている／いま切り替えた」ことが意味を持つ `#btn-tree`（`aria-pressed`）・
  `#btn-help-open`（`aria-expanded`）だけに限定。前者は既存の `.view-toggle[aria-pressed="true"]` と
  同じ「モード切り替えボタン」の扱いに揃えた）

以下は確認して**指摘なし**と判断した:

- 被覆: `aidev coverage` は design/tasks 承認時に 100%（AC1〜AC16・AC-I1〜AC-I4 の 20/20）。
  coding 中に `AC:` の無いタスクは増えていない。
- **`viewedFiles` が書き出す JSON に混ざらないこと**（AC12）: `persist()` は `viewed` を
  `localStorage` に同居させるが、`exportText()`/`canonicalRecord()` は `state`/`drafts` しか読まない
  経路を実装レビューで確認。ブラウザで書き出した JSON を実測しても `viewed` は出ない
  （test-result.md ラウンド 1）。
- **F10 の根本原因の再発防止**: `redrawFile` の優先順位（押した隙間のボタン → 現在行 → 最初の
  展開ボタン → 折りたたみボタン）どおりに実装されていること、`focusInPlace` が `preventScroll` と
  可視判定の両方を持つことをコードで確認。実測（`uitest.js` の F10 検査）でも、押した隙間と別の
  ボタンに焦点が飛ぶ再発は無い。
- **検索でツリーの祖先を強制的に開く**実装は `treeOpen` 自体を書き換えない（`forceOpen` は描画時の
  一時フラグ）ので、検索を消すと元の開閉に戻ることをコードとブラウザ実測の両方で確認。
- **参照専用**でも検索・ツリー・確認済みチェックボックス・パスコピーがすべて動くこと（新機能は
  「書く」導線ではないので `!readonly` で隠していない）を実測で確認。コメント関連の導線が
  参照専用に出ないことも変わらず確認。
- **キー割り当ての不変**（AC-I3・AC-I4）: `e` / `Shift+E` / `f` / `t` が同じ対象に効くことを実測。
  新しい要素（検索欄・確認済みチェックボックス・パスコピー・畳むボタン）はいずれも通常のボタン /
  入力欄で、専用キーを割り当てていない（`Tab` で届く）。
- `compileQuery` の 3 分岐（正規表現 `/…/フラグ` ・ワイルドカード `*`/`?` ・部分一致）を、
  research で実測済みの 12 ケースの規則どおりに実装していることをコードで確認。壊れた正規表現は
  例外を投げずに `{error}` を返し、呼び出し側がバナーではなく欄の下のヒントに出すことも確認
  （画面全体を止めない）。
- `.file-toggle` のクラス名を変えていない（`f` キー・`redrawFile` の `.file-toggle` セレクタが
  そのまま効く）ことをコードで確認。

## ラウンド 2

**指摘なし**（must / should / nit いずれも 0 件）。ラウンド 1 の修正後、`uitest.js` / `uitest-readonly.js` /
`uitest-keys.js`（headless Chromium・計 35 件）と `python3 -m unittest tests.test_diff_review`
（126 件）を再実行し、全通過を確認した。
