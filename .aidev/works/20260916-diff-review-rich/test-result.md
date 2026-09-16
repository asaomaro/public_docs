# テスト結果: rich diff・ハイライト・文脈展開・レビュー語彙

## ラウンド 1

### 実行したもの

- `python3 -m unittest discover -s tests`（生成側） — **50 passed / 0 failed / 0 skipped**
- `aidev smoke` — **pass（exit 0、3 本）**
- `node accept2.mjs`（headless Chromium・画面の受け入れ確認） — **25 passed / 2 failed**

### 失敗の証跡

```
$ node accept2.mjs
pass	AC5	alert 記法が専用表示
FAIL	AC6	mermaid は図に、未対応図種はコード＋理由
pass	AC11	行数 16 → 22 → 42
pass	AC12	すべて展開で 122 行・展開ボタン 0
pass	AC13	記録された位置: big.py:5 (RIGHT)
FAIL	AC-I3	e で 16 → 22、Shift+E で 22
pass	AC-I5a	ボタンの Enter が横取りされない（rich→source に切り替わる）
pass	AC-I5b	入力欄では e / t がショートカットとして動かない
RESULT: 25 passed / 2 failed
```

**AC6 は受け入れスクリプト側の誤り**（製品の欠陥ではない）。フィクスチャの `doc.md` に置いたのは
```` ```gantt ```` という**コードブロック**で、````` ```mermaid ````` の中に `gantt` を書いたものではない。
未対応図種のフォールバックは「mermaid ブロックの中身が未対応の図種だったとき」に出るので、
この入力では出なくて正しい。フィクスチャを直す。

**AC-I3 は実装の欠陥**。`e` で展開したあと `Shift`+`E` が効かない。
展開すると `redrawFile` が `.file-body` の中身を作り直すため、**`currentRow` が切り離されたノードのまま残り**、
`currentRow.closest(".file")` が `null` を返してキー操作が何もしなくなる。
「キーを足した時点では気づけず、他の操作と組み合わせて初めて壊れる」——前 work の must（Enter の横取り）と
同じ型の欠陥で、tasks.md のリスク欄に書いていたとおりの場所で出た。

→ `aidev event test sent_back` を記録して coding へ差し戻す。


---

## ラウンド 2（差し戻しの修正後・2026-09-16T04:25:48Z）

### 実行したもの

- `python3 -m unittest discover -s tests` — **51 passed / 0 failed / 0 skipped**（1 件追加）
- `node accept2.mjs`（画面の受け入れ確認・T22） — **27 passed / 0 failed**
- `aidev smoke` — **pass（exit 0、3 本）**
- **自己適用**: このリポジトリ自身の差分から HTML を生成し、ブラウザで開いてエラー 0 を確認
  （7 ファイル・1,553 行・トークン 1,261 件・load 約 0.7 秒）

### 直したもの

| 事象 | 原因 | 修正 |
|---|---|---|
| `e` で展開したあと `Shift`+`E` が効かない（AC-I3） | 再描画で行のノードが作り直され、`currentRow` が**切り離されたノード**のまま残っていた。`closest(".file")` が `null` を返し、キー操作が黙って無効化されていた | 再描画時に**同じ行を指し直す**。さらにキー操作は「現在行が失われていたらフォーカス位置からファイルを引く」形にした |
| 大文字 `E` が `shiftKey` 無しで届く環境で「すべて展開」が効かない | `event.shiftKey` だけを合図にしていた | **キーが大文字であることも合図**に加えた |
| AC6 が落ちる | **受け入れスクリプト側のフィクスチャ誤り**（```gantt というコードブロックを置いていた。未対応図種のフォールバックは ```mermaid の**中身**が未対応のときに出る） | フィクスチャを ```mermaid + gantt に直した |

### 併せて直した容量の無駄（`decisions.md` D14）

受け入れ確認の途中で生成物を測ったところ、**差分行の `tokens` と展開データの `tokens` が
同じ配列を 2 回運んでいた**。重複を外し、画面は「行が持っていなければ展開データから引く」規則にした。

```
$ ls -l self.html self2.html
self.html    2486.8 KB   （重複あり）
self2.html   1860.1 KB   （重複を外したあと。−25%）
```

### 受け入れ基準ごとの判定

| AC | 判定 | 確かめ方 |
|---|---|---|
| AC1 / AC2 | pass | `big.py` に数値トークン、`data.csv`（未対応拡張子）にはトークン無し |
| AC3 | pass | 画面の外部リクエスト **0 件**（ハイライトも rich も生成時に完結） |
| AC4 | pass | CSV の変更セルに印（`td.changed`） |
| AC5 | pass | `> [!WARNING]` が `alert-warning` として描画 |
| AC6 | pass | mermaid が `img`（data URI の SVG）、`gantt` はコード＋理由 |
| AC7 | pass | `iframe sandbox=""`。差分に仕込んだ `<script>alert(1)</script>` はダイアログを出さない |
| AC8 | pass | PDF のページ数・サイズ＋テキスト差分（`.pdf-line`） |
| AC9 | pass | rich 対象なしの生成物に `rich.js` が**入らない**。rich 機構の増分は **+13.4%**（<15%） |
| AC10 | pass | rich ↔ source の切り替え（`aria-pressed` が追従） |
| AC11 | pass | 段階展開で行数 16 → 22 → 42、端まで開くとボタンが消える |
| AC12 | pass | 「すべて展開」で 122 行・展開ボタン 0 |
| AC13 | pass | 展開した行にコメントでき、記録された位置が `big.py:5 (RIGHT)` |
| AC14 | pass | 折りたたみ（`data-collapsed`）は維持 |
| AC15 / AC16 | pass | 重大度がバッジと JSON に出る。`list --severity` / `--notes` で絞れる |
| AC17 | pass | 返信への返信が**その返信**を `in_reply_to` に持つ（3 件の連鎖を実測） |
| AC18 | pass | 「レビューを開始」→ 提出（`CHANGES_REQUESTED`） |
| AC19 / AC20 | pass | 説明コメントは `kind: note`・重大度なし・解決ボタンなし・**提出の対象に入らない** |
| AC21 | pass | `/1` の記録を読み込み、`kind` / `severity` が既定値で補われる |
| AC22 | pass | 書き出し → 読み込み → 再書き出しがバイト一致（`/2`）。決定論・XSS 非解釈・標準ライブラリのみも維持 |
| AC-I1〜I5 | pass | Esc で本文と重大度が残る／取り消しで消える／`e`・`Shift+E`・`t` がキーで通る／フォーカスが戻る／入力欄とボタンの標準操作を奪わない |

### 起動確認（smoke）

```
$ aidev smoke
smoke: pass (exit 0, 3 本)
```

### 未検証の穴（skip / 環境不足）

- **Firefox / Safari と Windows は実機未検証**（前 work から継続）。
- **mermaid の描画は自前の近似**で、mermaid 公式とは絵が違う。複雑な図（subgraph の入れ子・
  スタイル指定・長いラベル）は崩れうる。実測したのは `flowchart` / `sequenceDiagram` の単純な形だけ。
- **PDF は ToUnicode を持つものだけ**テキストが出る（持たない PDF は理由を表示）。実測は Chromium 生成の PDF。
- **容量**: 既定（`--expand-max-lines 2000`）では展開データが生成物の大半を占める
  （このリポジトリ自身の差分で 1.86MB のうち約 1.1MB）。`--expand-max-lines 0` で 1.10MB まで落ちる。
  これは `decisions.md` D3 の意図どおりだが、**既定値の妥当性は使ってみないと分からない**。
- CI 未搭載（前 work から継続）。


---

## ラウンド 3（review ラウンド 1 の should 修正後・2026-09-16T04:27:44Z）

### 実行したもの

- `python3 -m unittest discover -s tests` — **51 passed / 0 failed / 0 skipped**
- `node accept2.mjs` — **28 passed / 0 failed**（AC-I4 の検査を 1 件追加して 27 → 28）
- `aidev smoke` — **pass（exit 0、3 本）**

### 直したもの（review ラウンド 1 の指摘）

| 指摘 | 修正 | 確認 |
|---|---|---|
| [should]「すべて展開」でフォーカスが `BODY` に落ちる（AC-I4 違反） | 展開後に**元いた行を指し直し**、見つからなければ押したボタンへ戻す | `AC-I4` を受け入れ確認に追加し、`document.activeElement` が `BODY` でないことを実測 |

### 失敗の証跡

このラウンドでは失敗が発生していない（修正 → 再実行で 28/28・51/51 とも一度で緑）。
差し戻しの根拠となったラウンド 1 の実測（`すべて展開のあとのフォーカス: BODY.`）は review.md に記録済み。

### 起動確認（smoke）

```
$ aidev smoke
smoke: pass (exit 0, 3 本)
```

### 未検証の穴（skip / 環境不足）

ラウンド 2 と同じ（Firefox / Safari・Windows・mermaid の複雑な図・ToUnicode 無し PDF・
既定の容量・CI 未搭載）。新たな穴は無い。
