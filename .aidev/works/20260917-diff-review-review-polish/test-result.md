# テスト結果: レビュー操作性の改善（ツリー見た目・レビュー提出フロー・固定ヘッダー・コメント折りたたみ・通知ベル）

> **ラウンド7・最終**（PR #28 マージ後、「高さの修正が元に戻っている」というユーザー報告を
> 受け、`min-height` が実ブラウザで効いていなかった原因を突き止めて修正した後の再検証。
> decisions.md D13）。ラウンド1〜6の内容は本ファイル末尾に残す。

## 実行したもの（ラウンド7・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- **実ブラウザでの高さ実測（新規の検証手段）**: `playwright-core` ＋ 既存インストール済みの
  Chromium バイナリ（`~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`）を使い、
  `page.locator(...).boundingBox()` で実際にレンダリングされた高さを測定した。
  jsdom（headless DOM 検証）は CSS の**指定値**（`getComputedStyle().minHeight` が
  `"28px"` を返す等）しか確認できず、レイアウト計算後の**使用値**（実際に描画される
  高さ）は検証できていなかった——今回の不具合（`min-height` が下限であるがゆえに
  content 側の自然な高さがそれを超えていると無効化される）は、まさにこの「指定値と
  使用値の違い」によって jsdom では検出できず、実ブラウザでしか見つけられなかった。
  - トップバー7個（split表示/テーマ/レビュー開始/JSON書き出し/ファイルを開く/通知ベル/
    ヘルプ）: すべて 28.00px（修正前は通知ベル以外すべて 32.39px）
  - ファイル操作列（file-toggle/copy-path）: 28.00px
  - composer（コメントする/閉じる/severity select）: 28.00px
  - submit-panel（提出する/閉じる）: 28.00px
  - 例外3箇所（差分行の +・expand-all〔比較用に icon-btn も確認〕・
    row .comment-open）: `row .comment-open` は 18.80px（意図どおりコンパクトなまま）、
    `expand-all`（`.icon-btn`）は 28.00px
  - 「ファイルにコメント」ボタン（`.file-actions .comment-open`）は、この work が
    自分自身の差分をレビューする際、`docs/ClaudeCode/skills/other/diff-review-html/
    templates/style.css` という長いパスと組み合わさって `.file-head` の横幅が窮屈になり、
    ボタン自身が2行に折り返って 43.59px になるケースを確認した。**これはバグではなく
    D12/D13 で意図した「固定 `height` ではなく `min-height` にして、収まらない場合は
    欠けずに伸びる」という安全策が働いている状態**（通常の短いパスでは発生しない）。

## 実行したもの（ラウンド6）

## 実行したもの（ラウンド6・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による headless DOM 検証 — **64 件、すべて pass**（`height: 28px` を
  `min-height: 28px` に変更したことを `getComputedStyle().minHeight` で確認。3つの
  例外セレクタは `min-height: 0` も明示したことを確認。今回の実行では差分が複数
  ファイルだったため、環境依存スキップは発生しなかった）

> **ラウンド5**（PR #27 マージ後、ボタンの高さ不揃いがトップバー以外にも残っていると
> いう指摘——decisions.md D12——を coding で修正した後の再検証）。ラウンド1〜4の内容は
> 本ファイル末尾に残す。

## 実行したもの（ラウンド5）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による headless DOM 検証 — **62 件のアサーション pass・1件は環境依存で
  スキップ**（D12 の確認——ファイル操作列/コメント入力欄/スレッド見出し/提出パネル/
  レビュー結果一覧の編集・削除ボタンが軒並み `height: 28px`、かつ差分行の「+」・
  隙間展開ボタン・コメント一覧カードは意図どおり `auto` のまま——を `getComputedStyle()`
  で追加。スキップは「差分が1ファイルのみだとツリーのフォルダ行自体が出ない」という
  ツリー表示側の既存仕様に起因するもので、今回の変更とは無関係）

## 実行したもの（ラウンド4）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による headless DOM 検証 — **60 件のアサーション、すべて pass**
  （D11 の2件——`#pane-center` の `padding-top`/`#overall` の `margin-top`・トップバー
  7個のボタンの `height`——の確認を `getComputedStyle()` で追加）

> **ラウンド3**（review ラウンド2で見つかった重大度バッジの二重表示——decisions.md D10
> ——を coding で修正した後の再検証）。ラウンド2は D9 の2件（AC12 の重大度消失・編集中
> インジケータ欠如）の修正検証、ラウンド1は初回実装の検証。いずれの内容も本ファイル
> 末尾に残す。

## 実行したもの（ラウンド3・最終）

- `python3 -m unittest discover -s docs/ClaudeCode/skills/other/diff-review-html/tests -p "test_*.py"`
  — 126 passed / 0 failed / 0 skipped
- `aidev smoke`（`.aidev/config.yml` の `smokeCommands` 3本）— pass (exit 0)
- Node.js + jsdom による headless DOM 検証 — **51 件のアサーション、すべて pass**
  （ラウンドを追うごとに、見つかった指摘の確認を検証スクリプトへ追加していった。
  以下「追加の headless DOM 検証」節に各ラウンドの追加分を記載）

## 受け入れ基準ごとの判定

すべて headless DOM 検証（jsdom で実際に生成 HTML を実行し、クリック/入力を dispatch して
確認）または既存の自動テストで確認した。design.md の「受け入れ基準との対応」に対応する
実装箇所を、実際にブラウザ相当の環境で動かして検証している（コードを読むだけの確認ではない）。

- AC1: pass — ツリー表示でフォルダ/ファイル行に `.icon-folder`/`.icon-file` が実在することを確認。
- AC2: pass — 検索欄に `.icon-search` が実在することを確認。
- AC3: pass — ツリー表示のファイル行に `+N` 形式の追加行数表示が残っていることを確認。
- AC4: pass — `#btn-submit-open` が存在せず、`#btn-start-review` のみが存在することを確認。
- AC5: pass — クリックでパネルが開き、ラベルが「レビュー結果を入力」に変わることを確認。
- AC6: pass — 提出後、`#review-list` にエントリ（判定バッジ＋サマリ）が表示されることを確認。
- AC7: pass — 編集ボタンでフォームに既存値が読み込まれ、保存すると新規追加ではなく
  同じエントリが更新されることを確認（提出前後でエントリ数が1件のまま）。
- AC8: pass — 削除ボタンでエントリが一覧から消え、空状態メッセージに戻ることを確認。
- AC9: pass — `#btn-submit-discard` が存在しないことを確認。
- AC10: pass — 生成 CSS に `.file-head { ... position: sticky ... }` が含まれることを確認
  （jsdom はレイアウトエンジンを持たないため、実際の描画・スクロール追従の見た目は
  未検証。「未検証の穴」参照）。
- AC11: pass — スレッドに `.thread-fold` ボタンが実在し、クリックで
  `data-collapsed="true"` に切り替わることを確認。
- AC12: pass — 折りたたんでも `.thread-head` は残り、`.comment` 要素（CSS で隠す対象）は
  DOM 上に残っていることを確認。
- AC13: pass — 提出直後に `#notif-badge` が非表示解除され `"1"` を表示することを確認。
- AC14: pass — 提出成功メッセージが `#banners` のインラインバナーには現れず、
  `#notif-list` にだけ現れることを確認。
- AC15: pass — 不正な正規表現を検索欄に入力すると、`#file-search-hint` にエラーが
  表示されることを確認（画面上部側に留まる。対応不要のお知らせと違いベルへは流さない）。
- AC16: pass — ベルをクリックすると `#notif-badge` が再び非表示になることを確認。
- AC-I1: pass — `Escape` で提出パネルが閉じることを確認（`closeSubmitPanel()` 経由）。
  スレッド折りたたみ・通知ベルの開閉はクリックで確認済み（AC11/AC13/AC16 のとおり）。
- AC-I2: pass — 編集中に値を変更したあと `Escape` で閉じても、一覧のエントリ内容が
  変更前のまま（キャンセル前に保存した内容）であることを確認。
- AC-I3: pass（部分検証） — 新規ボタン（編集・削除・折りたたみ・ベル）はいずれも
  `<button type="button">` として実装されており、`click()` イベントで操作できることを
  確認した。**Tab キーでの実際の到達順序（フォーカストラップの有無等）は jsdom では
  検証していない**（「未検証の穴」参照）。
- AC-I4: pass — スレッド折りたたみのフォーカス復元ロジック（`focusInPlace` 呼び出し）が
  例外なく動くことを確認。ベルは開いてもフォーカス移動処理を呼んでいないため、
  ボタン自身に残ることを設計上確認（jsdom の `document.activeElement` の厳密な追跡は
  行っていない）。
- AC-I5: pass — 新機能追加後も既存のキー操作（`j` による行移動）が例外なく動作することを
  確認。
- **AC12（ラウンド2で再確認）**: pass — review 指摘（decisions.md D9）を受けて
  `.thread-head` に重大度バッジを追加。折りたたむ前後どちらも
  `.thread-head .badge.sev-must` が存在することを headless DOM 検証で確認（ラウンド1では
  この観点を見落としていた）。
- **US3（ラウンド2で追加）**: pass — `#review-list` が複数件のとき、編集中のエントリにだけ
  `data-editing="true"` と「編集中」表示が付き、保存/キャンセルどちらでも印が消えることを
  headless DOM 検証で確認。

## 失敗の証跡

ラウンド1〜3のいずれも、テスト実行そのものの失敗は発生していない
（`python3 -m unittest` 126件・jsdom 検証（ラウンドを追うごとに指摘の確認を追加し
最終51件）・smoke 3件、いずれも green）。
**ただし review 工程（要件適合/価値適合の独立点検）が2度、指摘を検出して coding へ
差し戻している**:
- ラウンド1の実装に対して must 1件・should 1件（decisions.md D9・review.md「ラウンド1」）。
- D9 の修正自体に対して should 1件——`.thread-head` に足した重大度バッジが展開時に
  既存の `.comment > .who` 側と二重表示になっていた（decisions.md D10・review.md
  「ラウンド2」）。
いずれも自動テストの失敗としては現れず（DOM 的には「意図通り表示された/消えた」ように
見え、要件の意図と突き合わせて初めて分かる性質の欠陥だった）、review 工程の独立点検で
拾われた。

## 起動確認（smoke）

```
$ sh docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev help
（…aidev CLI のヘルプ出力…）
$ python3 docs/ClaudeCode/skills/other/diff-review-html/diff_review.py --help
usage: diff_review.py [-h]
                      {html,bundle,view,template,check,comment,resolve,submit,list}
                      ...
git の差分をレビュー用の単一 HTML にし、レビュー記録 JSON を往復させる
$ python3 docs/ClaudeCode/skills/other/diff-review-html/diff_review.py template --repo .
{
  "reviews": [],
  "schema": "diff-review/2",
  "target": { … },
  "threads": []
}
smoke: pass (exit 0, 3 本)
```

今回の work は新しい CLI サブコマンド/オプションを追加していない（画面側の変更のみ）ため、
`smokeCommands` への追記は不要と判断した。

### 追加の headless DOM 検証（jsdom）

このプロジェクトは「画面（HTML）側の受け入れ確認は headless ブラウザで行う」方針
（`tests/test_diff_review.py` 冒頭のコメント）だが、そのための仕組みは無かったため、
この work の検証用に Node.js + jsdom を使い、実際に生成された HTML をロードして
クリック・入力イベントを dispatch する検証スクリプトをその場で書いて実行した
（成果物には含めない。work フォルダにも置かず `/tmp` のスクラッチで実行し、
検証後は残さない。**リポジトリに恒常的な headless テストとして追加するかは
この work のスコープ外**——別途 backlog 化する価値はある）。

```
$ node run.js
PASS: ツリー切替ボタンが存在する
PASS: AC1: フォルダ行にフォルダアイコンがある
PASS: AC1: ファイル行にファイルアイコンがある
PASS: AC3: 追加/削除行数表示（+N）が残っている
PASS: AC2: 検索欄にアイコンがある
PASS: AC4: #btn-submit-open が存在しない
PASS: AC4: #btn-start-review が唯一のボタンとして存在する
PASS: AC5: 初期ラベルは「レビューを開始」
PASS: AC5: クリックでパネルが開く
PASS: AC5: ラベルが「レビュー結果を入力」に変わる
PASS: AC9: #btn-submit-discard が存在しない
PASS: AC6: #review-list が存在する
PASS: AC6: 初期状態は空メッセージ
PASS: AC-I2: 確定ボタンの初期表示は「提出する」
PASS: AC6: 提出後、一覧にエントリが1件表示される
PASS: AC6: エントリにサマリが表示される
PASS: AC6: エントリに判定バッジが表示される
PASS: AC13: 通知ベルにバッジが表示される
PASS: AC14: 画面上部のバナーに提出成功メッセージが無い（ベルへ振り替え済み）
PASS: AC7: 編集ボタンが存在する
PASS: AC7: 編集モードで確定ボタンが「保存する」になる
PASS: AC7: フォームに既存のサマリが読み込まれる
PASS: AC7: 編集後もエントリは1件のまま（新規追加されない）
PASS: AC7: エントリの内容が更新される
PASS: AC7: 保存後は確定ボタンが「提出する」に戻る
PASS: AC-I2: Escape でパネルが閉じる
PASS: AC-I2: キャンセルしてもエントリの内容は変わらない
PASS: AC8: 削除ボタンが存在する
PASS: AC8: 削除後は一覧が空になる
PASS: AC10: .file-head に position: sticky が指定されている
PASS: AC11: スレッドに折りたたみボタンがある
PASS: AC11: 初期状態は展開（aria-expanded=true）
PASS: AC11/AC12: クリックで data-collapsed=true になる
PASS: AC12: 折りたたんでも thread-head は残っている
PASS: AC12: 折りたたむとコメント本文の要素が data-collapsed 配下にある（CSSで隠す対象）
PASS: AC16: ベルを開くと未読バッジが消える
PASS: AC-I4: ベルを開いてもフォーカスはベル自身に残る（明示的な移動なし）
PASS: AC13/AC14: 通知一覧に提出成功のメッセージがある
PASS: AC15: 不正な正規表現のエラーはベルではなく画面上部のバナーに出る
PASS: AC-I5: j キーで行移動しても例外が出ない

ALL PASS
```

readonly ビルド（`--readonly`）でも同様に headless で確認し、書き込み系の新規要素
（`#btn-start-review`/`#btn-submit-discard`/`#review-list`）が出力されないこと、
表示専用の新規要素（ツリーアイコン・`#btn-notif`）は出力されること、ツリーのアイコン
切り替えやスレッド折りたたみが例外なく動くことを確認した。

**ラウンド2**（review 指摘2件の修正後、検証スクリプトに4件のアサーションを追加して
再実行）:

```
$ node run.js
（…ラウンド1の全アサーション…）
PASS: レビュー観点(should#2): 編集中の1件目には data-editing=true と「編集中」表示がある
PASS: レビュー観点(should#2): 編集していない2件目には編集中の印が無い
PASS: レビュー観点(should#2): 保存すると編集中の印が消える
PASS: レビュー観点(should#2): Escape キャンセルでも編集中の印が消える
PASS: レビュー観点(must#1): 折りたたむ前は .thread-head に重大度バッジがある
PASS: レビュー観点(must#1): 折りたたんでも重大度バッジが thread-head に残っている（消えない）

（この時点で計45件 pass）
```

**ラウンド3**（D10 の二重表示解消後、さらにアサーションを追加して再実行。最終版）:

```
$ node run.js
（…ラウンド2までの45件…）
PASS: レビュー観点(must#1・ラウンド2): 展開時、先頭コメント側には重大度バッジが重複表示されない
PASS: レビュー観点(must#1・ラウンド2): 返信自身が持つ重大度は自分の .who に表示される
PASS: レビュー観点(must#1・ラウンド2): 先頭コメントの .who には重大度バッジが無い（重複抑制）

ALL PASS（51件）
```

## 未検証の穴（skip / 環境不足）

- **実際の描画・レイアウト**: jsdom はレイアウトエンジンを持たないため、
  `position: sticky` によるファイルヘッダーの追従、通知ポップオーバーの表示位置、
  検索アイコンとテキストの重なり具合など、**見た目・スクロール挙動そのものは
  当初実ブラウザで未確認だった**。CSS ルールの存在と、taskcheck（T7/T9）でのレビュー時の
  仕様確認（CSS Positioned Layout の仕様に照らした静的検証）で代替していた。
  - **この穴が2度顕在化した**: (1) PR #26 マージ後、sticky ヘッダーとトップバーの間の
    隙間・トップバーのボタンの高さ不揃い（decisions.md D11）。(2) PR #28 マージ後、
    `min-height: 28px` が実ブラウザでは全く効いていなかった（`min-height` は下限であり、
    content 由来の高さが既にそれを超えていると無効化される。decisions.md D13）。
    (2) は特に、jsdom の `getComputedStyle()` が「指定値」しか読めず「使用値」（実際の
    描画結果）を読めないことに起因し、jsdom による検証だけでは原理的に検出不可能だった。
  - **この work では playwright-core ＋ 既存 Chromium バイナリによる実ブラウザ実測
    （`boundingBox()`）を用意し、ボタンの高さについてはこの穴を解消した**（D13）。
    ただし sticky の実際のスクロール追従・通知ポップオーバーの表示位置など、
    ボタンの高さ以外の見た目はまだ実ブラウザで網羅的には確認していない。
    **今後 diff-review-html を触る work では、jsdom だけでなく実ブラウザでの
    `boundingBox()`/スクリーンショット確認も検証手段に含めることを推奨する**
    （この work で有効性が実証された）。
- **Tab キーでの到達順序**: AC-I3 は新規ボタンが `<button>` として click 操作できる
  ことは確認したが、実際に Tab キーで辿ったときの順序・フォーカスの見え方
  （`:focus-visible` のスタイル等）は未確認。
- **色のコントラスト実測**: 通知バッジの配色修正（review.md 参照）はトークンの
  組み合わせから妥当と判断したが、実際のレンダリングでのコントラスト比計測ツール
  （axe 等）による確認は行っていない。
- **クロスブラウザ確認**: Chromium/Firefox/Safari 等での実機確認は行っていない
  （このプロジェクトの既存の検証範囲を超えるため、他の work でも同様に未検証）。
