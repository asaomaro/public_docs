# レビューガイド: 画面まわりの不備 7 件

> `templates/`（`page.html` / `style.css` / `ui.js` / `app.js`）だけの変更。生成側（`diff_review.py` 等）は
> 触っていない。差分は `app.js` が中心でまとまった量になるので用意した。

## 変更概要 / 目的

ユーザーから挙がった画面側の不備 7 件をすべて直した。

1. **ツリー表示が字下げされていない**（実は見た目だけの不具合）→ CSS だけで解決
2. **ファイル一覧に検索が無い** → 部分一致・ワイルドカード（`*`/`?`）・正規表現（`/…/フラグ`）の 3 通り
3. **展開の逆（畳む）ボタンが無い** → アイコンのみの「畳む」を「すべて展開」の隣に常設
4. **無駄なボタンテキストを削る** → `btn-tree`/`btn-pane-left/right`/`btn-theme`/`btn-help-open`/
   ファイルの折りたたみをアイコン化。`title`/`aria-label` は個別に残す
5. **確認済みチェックボックスと件数が無い** → ファイルごとにチェックボックス、
   一覧の見出しに「N / M 確認済み」
6. **ファイル名クリックでの展開が展開ボタンと機能が被る** → クリックでの展開を廃止し、
   代わりにパスをコピーするアイコンボタンを追加
7. **展開すると表示位置が動く** → `focusInPlace`（`focus({preventScroll:true})` ＋ 必要なときだけ
   `scrollIntoView({block:"nearest"})`）を新設し、押した隙間のボタン自身に焦点を戻す

## 重要ポイント（非自明な判断）

1. **7 番の根本原因**: `redrawFile` が再描画のたびに `.expander button` を**DOM 順で最初の 1 つ**へ
   `focus()` していた。押したのが 3 番目の隙間でも 1 番目のボタンに焦点が飛び、ブラウザの既定の
   スクロール追従で画面が無関係な位置へ動いていた（`research.md` F10 で実測: scrollTop が
   -470px 動く）。直し方は「正しい場所を指す」＋「動かさない」の 2 段: `expander()` の `up`/`down`
   クリックが**自分の隙間の番号**を `redrawFile` に渡し（`{gap, dir}`）、`focusInPlace` が
   `preventScroll` で既定のスクロールを止める。
2. **確認済みは記録に入れない**（D3）。`viewedFiles` は `persist()` で `state`/`drafts` と同じ
   localStorage エントリに同居するが、書き出す JSON（`exportText`/`canonicalRecord`）はそこを
   読まない経路なので混ざらない。
3. **検索はパスだけ**（ファイルの中身は対象外）。3 分岐の判別（`compileQuery`）は
   「`/…/フラグ` ならそのまま正規表現」「`*`/`?` を含むならワイルドカードとして変換」
   「それ以外は部分一致」。壊れた正規表現は例外を投げずに `{error}` を返し、画面を止めずに
   検索欄の下にエラーを出す。
4. **ツリー表示中の検索は祖先を強制的に開く**が、`treeOpen`（開閉の記憶）自体は書き換えない。
   検索を消すと元の開閉状態に戻る。
5. **クリップボードは `execCommand` が実質の本経路**。`navigator.clipboard.writeText()` は
   `file://` で明示的な許可なしに失敗する（`isSecureContext` が true でも、実測で確認）ので、
   非表示の `<textarea>` 経由の `execCommand("copy")` に自動でフォールバックする。
6. **アイコンの配色は、既定で true になるボタンには付けない**（D4・review.md ラウンド 1 の指摘）。
   `.file-toggle`（既定で展開＝ true）や `#btn-pane-left/right`（既定で開いている＝ true）に
   「選択中」の色を付けると常時点灯してノイズになるため、`#btn-tree`（`aria-pressed`）・
   `#btn-help-open`（`aria-expanded`）だけに絞った。

## 動作確認

- `python3 -m unittest tests.test_diff_review` — 126 件、生成側の既存回帰（無変更のため全通過）
- headless Chromium（`file://`）での画面検証 35 件（通常モード 23・参照専用 7・キー割り当て 5）——
  詳細は `test-result.md`
- 自己適用: このリポジトリ自身の差分から HTML を生成し、ブラウザで開いて JS エラー 0 件を確認

## 見なくてよいところ

- `templates/style.css` の見た目の微調整（`.file-viewed-label` の余白など）
- `SKILL.md` の説明文の言い回し
