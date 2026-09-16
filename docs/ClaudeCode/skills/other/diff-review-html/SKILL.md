---
name: diff-review-html
description: ローカルの git 差分（未ステージ / ステージ済み / コミット間）を、GitHub の PR 画面のように読める単一HTMLにして出力する。画面では行・ファイル・全体の3階層にコメントし、返信・解決・提出（Approve / Request changes / Comment）まで行え、その記録をJSONで書き出し／読み込みできる。AIが書いた指摘のJSONを埋め込んだHTMLを作ることも、人間が書いた指摘のJSONをAIが読んで修正することもできる。「差分をHTMLで見たい」「差分レビューの画面を作って」「レビュー用のHTMLを生成して」「レビュー結果をJSONで受け渡したい」「レビュー記録のJSONを読み込んで」と言われたときに使用する。GitHubのPRそのものへの投稿や取得は行わない。
allowed-tools: [Bash, Read]
---

# diff-review-html — 差分レビュー画面（単一HTML）と、指摘のJSON往復

`git` の差分を **自己完結した単一 HTML**（外部 CDN なし・`file://` で開ける）にし、
レビューの指摘を **JSON** で人間と AI のあいだで往復させる。

- **人間 → AI**: 画面で書いた指摘を JSON で書き出す → AI がその JSON を読んで直す。
- **AI → 人間**: AI が JSON に指摘を書く → その JSON を埋め込んだ HTML を人間が開いて確認・返信する。

実行には **Python3（標準ライブラリのみ）** が要る。pip パッケージ・Node・jq は不要。
sh 版 / PowerShell 版は持たない（1 実装で Windows / macOS / Linux を賄う）。

```
python3 diff_review.py <サブコマンド> ...     # macOS / Linux
py -3 diff_review.py <サブコマンド> ...       # Windows（python でも可）
```

以下、この skill のディレクトリを `<skill>` と書く（`<skill>/diff_review.py`）。

## 3 つの機能

| したいこと | サブコマンド |
|---|---|
| **HTML を出す**（差分を読む画面を作る） | `html` |
| **JSON を作る**（AI が指摘を書くための雛形） | `template` |
| **JSON を読む**（検証する / 未解決の指摘を一覧にする） | `check` / `list` |

### 1. HTML を出す

```sh
# 未コミットの変更（既定）
python3 <skill>/diff_review.py html --repo . --out review.html

# ステージ済み / コミット間 / 特定のコミット
python3 <skill>/diff_review.py html --repo . --staged            --out review.html
python3 <skill>/diff_review.py html --repo . --range main..HEAD  --out review.html
python3 <skill>/diff_review.py html --repo . --commit 3d6624e    --out review.html

# AI が書いた指摘を埋め込んで渡す
python3 <skill>/diff_review.py html --repo . --import review.json --out review.html
```

`--out` を省くと標準出力へ出る。`--context N` で前後の文脈行数、`--title` で見出しを変えられる。
できた HTML はブラウザで開くだけでよい（サーバは要らない）。

### 2. JSON を作る（AI がレビューする場合）

**`template` で雛形を作り、`threads` に指摘を足す。`target` は書き換えない**
（どの差分への指摘かを機械が照合できなくなる）。

```sh
python3 <skill>/diff_review.py template --repo . --out review.json
# → threads に指摘を足す（形は <skill>/schema.md）
python3 <skill>/diff_review.py check review.json          # 壊れていたら理由を出して exit 3
python3 <skill>/diff_review.py html --repo . --import review.json --out review.html
```

指摘 1 件の最小形（`schema.md` が正典）:

```json
{
  "id": "t1",
  "path": "src/parse.py",
  "line": 120,
  "side": "RIGHT",
  "start_line": null,
  "start_side": null,
  "resolved": false,
  "comments": [
    { "id": "c1", "review_id": null, "author": "ai", "body": "空文字のとき例外になります", "in_reply_to": null }
  ]
}
```

- 行コメントは `path` ＋ `line` ＋ `side`（`RIGHT`＝追加・文脈行 / `LEFT`＝削除行）。
- ファイル単位は `line: null`、差分全体は `path: null` と `line: null`。
- 判定を添えるなら `reviews` に 1 件足し、そのコメントの `review_id` にその `id` を書く。

### 3. JSON を読む（AI が修正する場合）

```sh
python3 <skill>/diff_review.py check review.json           # 構造・参照・値域を検証
python3 <skill>/diff_review.py list  review.json           # 未解決の指摘だけを一覧に
python3 <skill>/diff_review.py list  review.json --format tsv   # path<TAB>state<TAB>本文
python3 <skill>/diff_review.py list  review.json --all      # 解決済みも出す
```

`list` の出力（`path:line` と本文）をそのまま修正の作業リストにできる。
**直したら `resolved` を立てるのではなく、人間に返す**——解決の判断はレビューした側が行う。

## 画面でできること

- 変更ファイル一覧（追加 / 削除行数つき）、ファイル単位の折りたたみ、追加 / 削除の色分け
- **行 / ファイル / 全体**の 3 階層のコメント、返信（スレッド）、解決 / 未解決の切り替え
- **未提出（pending）→ 提出**：Approve / Request changes / Comment ＋ サマリ本文
- JSON の書き出し（ダウンロード or コピー用テキストエリア）と読み込み（ファイル選択 / ドラッグ＆ドロップ）
- 書きかけのコメントの自動保存と復元

### キー操作

| キー | 動作 |
|---|---|
| `j` / `k`（`↓` / `↑`） | 差分の行を移動 |
| `c` / `Enter` | その行にコメントを書く |
| `Esc` | コメント欄を閉じる（**書きかけは残る**） |
| `Ctrl` / `⌘` + `Enter` | コメントを確定（未提出として溜まる） |
| `f` | そのファイルの折りたたみを切り替え |
| `r` | 提出パネルを開く |
| `?` | キー操作の一覧 |

## 制限（知っておくこと）

- **GitHub の PR には触らない**。PR からの差分・コメント取得も、PR への投稿も行わない。
- **下書きの自動保存はブラウザ依存**。`file://` の localStorage を塞ぐブラウザ（Firefox 等）では
  保存されない。その場合は画面にその旨が出る。**提出済みの記録は JSON に書き出して保存すること**
  （書き出しだけが確実な永続化）。
- **隣に置いた JSON を自動では読めない**。`file://` ではページから他のファイルを読めないため、
  読み込みは「ファイル選択 / ドラッグ＆ドロップ」か、生成時の `--import` に限る。
- 構文ハイライトと side-by-side 表示は持たない（unified 表示・差分の色分けのみ）。
- 大きいファイル（2,000 行超の差分）は既定で折りたたみ、開いたときに描画する。

## 出力の性質

- **決定論的**: 同じ差分からは同じ HTML / JSON が出る（時刻・乱数を入れない）。
  `diff_review.py html … > a.html` を 2 回流して `cmp` すれば確かめられる。
- **UTF-8・LF 固定**（OS を問わない）。Windows でも出力は変わらない。
- **差分やコメントが HTML として解釈されない**。画面は `textContent` だけで描画し、
  埋め込む JSON では `<` を `<` に退避してある。

## ファイル

| パス | 役割 |
|---|---|
| `<skill>/diff_review.py` | 生成・検証の script（サブコマンド `html` / `template` / `check` / `list`） |
| `<skill>/schema.md` | **レビュー記録 JSON の正典**（AI が書く前に読む） |
| `<skill>/templates/` | 画面の素材（`page.html` / `style.css` / `app.js`） |
| `<skill>/tests/test_diff_review.py` | `python3 -m unittest` で回るテスト |

## 終了コード

| コード | 意味 |
|---|---|
| 0 | 正常 |
| 1 | 使い方の誤り |
| 2 | `git` の失敗（リポジトリ外・不正なリビジョン等） |
| 3 | レビュー記録 JSON が不正 |
