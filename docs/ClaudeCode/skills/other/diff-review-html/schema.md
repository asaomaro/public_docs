# レビュー記録 JSON スキーマ（`diff-review/2`）

`diff-review-html` が読み書きする唯一の外部形式。**人間（画面）と AI（テキスト）の契約点**であり、
画面・`diff_review.py`・AI エージェントの 3 者はすべてこの形だけをやり取りする。

> AI がこの JSON を**書く**ときは、`diff_review.py template` が出す雛形から始めること。
> `target` を手で書くと、どの差分に対する指摘なのかが合わなくなる。

## 全体の形

```json
{
  "schema": "diff-review/2",
  "target": { "...": "対象の差分（雛形が埋める。手で書かない）" },
  "reviews": [ { "...": "提出されたレビュー（判定とサマリ）" } ],
  "threads": [ { "...": "コメントのスレッド" } ]
}
```

| キー | 型 | 説明 |
|---|---|---|
| `schema` | string | `"diff-review/2"`。`"diff-review/1"`（旧版）も**読み込みだけ**受け付ける |
| `target` | object | 対象の差分の識別情報（下記） |
| `reviews` | array | 提出単位。0 件でもよい（提出前の記録） |
| `threads` | array | コメントのスレッド。0 件でもよい |

## `target`（対象の差分）

```json
{
  "source": "unstaged",
  "range": null,
  "base_commit": "3d6624ec0a5dbae0ab1530540379ec0a96d2ad71",
  "diff_digest": "2d4df67c17c60134de3c6ceb32244c261ef77d13",
  "files": [
    { "path": "docs/x.md", "status": "M", "old_blob": "edf5f7b", "new_blob": "69f6331" }
  ]
}
```

| キー | 型 | 説明 |
|---|---|---|
| `source` | string | `unstaged` / `staged` / `range` / `commit` |
| `range` | string \| null | `source` が `range` / `commit` のときの指定（例 `HEAD~1..HEAD`）。他は `null` |
| `base_commit` | string \| null | `git rev-parse HEAD`。コミットが 1 つも無いリポジトリでは `null` |
| `diff_digest` | string | 差分本文の `git hash-object` 値。**この記録がどの差分に対するものか**を決める |
| `files` | array | 変更ファイルと blob。`status` は git の記号（`A` 新規 / `M` 変更 / `D` 削除 / `R…` リネーム …） |

読み込み時に `diff_digest` や `base_commit` が現在の差分と食い違う場合、**拒否はせず警告する**。
少し進んだ作業ツリーに対して過去の指摘を読めなくすると、往復が止まるため。

## `reviews[]`（提出されたレビュー）

```json
{ "id": "r1", "author": "human", "state": "CHANGES_REQUESTED", "body": "まとめのコメント" }
```

| キー | 型 | 説明 |
|---|---|---|
| `id` | string | 記録内で一意（画面は `r1`, `r2`… で振り直す） |
| `author` | string | `human` / `ai` / 任意の名前 |
| `state` | string | `APPROVED` / `CHANGES_REQUESTED` / `COMMENTED` のいずれか |
| `body` | string | レビュー全体のサマリ（空文字可） |

## `threads[]`（コメントのスレッド）

```json
{
  "id": "t1",
  "kind": "review",
  "path": "docs/x.md",
  "line": 120,
  "side": "RIGHT",
  "start_line": null,
  "start_side": null,
  "resolved": false,
  "comments": [
    { "id": "c1", "review_id": "r1", "author": "ai", "body": "この分岐は null を踏みます",
      "severity": "must", "in_reply_to": null },
    { "id": "c2", "review_id": null, "author": "human", "body": "直しました",
      "severity": null, "in_reply_to": "c1" }
  ]
}
```

| キー | 型 | 説明 |
|---|---|---|
| `id` | string | 記録内で一意 |
| `kind` | string | `"review"`（指摘）または `"note"`（**作者の説明**。提出されず、未解決にも数えない） |
| `path` | string \| null | ファイルのパス。`null` は**差分全体へのコメント** |
| `line` | integer \| null | 行番号。`null` は**ファイル単位のコメント**（`path` は必須） |
| `side` | string \| null | `RIGHT`（追加・文脈行の新しい側）/ `LEFT`（削除行）。`line` が `null` なら `null` |
| `start_line` / `start_side` | null | 複数行コメント用の予約。**現在は常に `null`** |
| `resolved` | boolean | 解決済みかどうか |
| `comments` | array | **1 件以上**。最初の要素がスレッドの起点 |

### コメントの 3 階層

| 階層 | `path` | `line` |
|---|---|---|
| 行へのコメント | ファイルのパス | 行番号 |
| ファイルへのコメント | ファイルのパス | `null` |
| 全体へのコメント | `null` | `null` |

### `comments[]`

| キー | 型 | 説明 |
|---|---|---|
| `id` | string | **同じスレッド内で**一意 |
| `review_id` | string \| null | 属する提出レビューの `id`。**`null` は「未提出（pending）」**。`kind: "note"` では常に `null` |
| `author` | string | `human` / `ai` / 任意の名前 |
| `body` | string | 本文（空は不可） |
| `severity` | string \| null | `"must"` / `"should"` / `"nit"` / `null`（重大度なし）。`kind: "note"` では常に `null` |
| `in_reply_to` | string \| null | **同じスレッド内の**コメント `id`。起点は `null`。返信への返信は**その返信の id** |

## 正規形（書き出しの形）

- UTF-8・LF・末尾に改行 1 つ。
- **キーは昇順**、インデントはスペース 2、非 ASCII はエスケープしない。
- Python では `json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"`。
- 画面（JavaScript）も同じ形で書き出すので、**書き出し → 読み込み → 再書き出しでバイト一致する**。
- **時刻を持たない**。持たせると同じ内容でも出力が変わり、差分として読めなくなる。
- **画面の設定を持たない**。split か unified か、テーマ、ペインの幅と開閉、ファイル一覧の形、
  コメント一覧の絞り込み——これらは**記録に一切入らない**。
  記録は「どこに何を指摘したか」の器であって、見る人の画面の器ではない。
  同じ記録を、split で見ている人と unified で見ている人が同じバイト列として扱えることが
  往復（人 → AI → 人）の前提になる。画面の設定はブラウザの `localStorage` にだけ入る
  （キーは `diff-review-html/ui/v1/*`）。

### 指摘（review）と説明（note）

| | `kind: "review"` | `kind: "note"` |
|---|---|---|
| 目的 | レビュアーの指摘 | **差分の作者がレビュアーに残す説明** |
| 提出（Approve 等）の対象 | なる（`review_id` が付く） | ならない（`review_id` は常に `null`） |
| 重大度 | 付けられる | 付けない |
| `list` の既定の一覧 | 出る | 出ない（`--notes` で出せる） |
| 画面の解決ボタン | 出る | 出ない |

## 旧版（`diff-review/1`）からの移行

`/1` の記録はそのまま読み込める。足りない項目は既定値で補われる。

| 項目 | `/1` を読んだときの既定値 |
|---|---|
| `threads[].kind` | `"review"` |
| `comments[].severity` | `null` |

**書き出しは常に `/2`**。`check` は `/1` も通すが、読み込み時に `/2` として扱われる。

## 検証（何を弾くか）

`python3 diff_review.py check <review.json>` が見るもの。1 件でも該当すれば終了コード 3。

- `schema` が `diff-review/2` でも `diff-review/1` でもない
- `threads[].kind` が `review` / `note` のどちらでもない
- `comments[].severity` が `must` / `should` / `nit` / `null` のどれでもない
- `kind: "note"` なのに `review_id` や `severity` を持っている
- `target` / `reviews` / `threads` の欠落や型違い
- `reviews[].state` が 3 値のいずれでもない
- `threads[].line` があるのに `path` が無い / `side` が `LEFT` `RIGHT` でない
- `threads[].line` が `null` なのに `side` がある
- `comments` が空、`body` が空
- `id` の重複（レビュー・スレッド・スレッド内コメント）
- `review_id` が存在しないレビューを指している
- `in_reply_to` が同じスレッドに無いコメントを指している

## バンドル（`diff-review-bundle/1`）

差分と指摘を **1 ファイル**にまとめた形。拡張子は `.dreview`。
エディタ拡張のように「ファイルを開く」単位が要る場面のためのもの。

```js
window.__DIFF_REVIEW_BUNDLE__ = {
  "schema": "diff-review-bundle/1",
  "target": { …この記録形式の target と同じ… },
  "files":  [ …差分の本体（画面が描くための構造）… ],
  "rich_enabled": true,
  "review": { "schema": "diff-review/2", "target": …, "reviews": […], "threads": […] }
};
```

| キー | 型 | 説明 |
|---|---|---|
| `schema` | string | `"diff-review-bundle/1"` |
| `target` | object | 対象の差分（この文書の `target` と同じ形） |
| `files` | array | 差分の本体。画面が描くための構造（生成側が作る） |
| `rich_enabled` | boolean | rich diff のデータを含むか |
| `review` | object \| null | **この記録形式（`diff-review/2`）そのもの**。指摘が無ければ `null` |

### なぜ記録を「内側にそのまま」持つのか

`review` にこの形式を丸ごと入れてあるのは、**検証を 1 本で済ませる**ため。
バンドル用の検証と記録用の検証が分かれると、片方だけ直す事故が起きる。
`target` が二重に入るが、MB 単位のファイルで数百バイトの重複は問題にならない。

### 前後が固定であること

前置き `window.__DIFF_REVIEW_BUNDLE__ = ` と後置き `;\n` は**固定**。
剥がせばこの文書の正規形 JSON になるので、**JS を実行せずに読める**
（Python・Node の両方で検査している）。前後が合わなければその場で弾く。

`U+2028` / `U+2029` は **JS では行終端文字**なので `\u2028` / `\u2029` へ退避する
（JSON としての意味は変わらない）。

### ビューアへの渡し方

バンドルをビューアに渡す口は 3 つ——**人がファイルを選ぶ**、**HTML の中に埋め込む**、
**ホストが `postMessage` で渡す**。ホスト（エディタ拡張など）が HTML を組み立てるときは、
ビューアにある空の `#bundle-data` に**この形のまま**書き込む
（`<` は `\u003c` に退避する。`</script>` でブロックが切れるため）。

```html
<script type="application/json" id="bundle-data">{ …バンドルの JSON… }</script>
```

開いたあとに差し替えるときは、同じ形をそのまま `postMessage` する
（`{type: "diff-review/bundle", bundle: …}` でも可）。
**外部ファイルを読む口は持たない**——どのバンドルを読むのかがファイル名任せになり、
そのファイルを実行することにもなるため。

### 画面の設定は入らない

レイアウトの設定（split / テーマ / ペインの幅…）が記録に入らないのと同じく、
**バンドルにも入らない**。バンドルは「どの差分に何を指摘したか」の器であって、
見る人の画面の器ではない。

## GitHub REST との対応

将来 GitHub の PR へ書き戻す経路を足すときに変換層が要らないよう、語彙を寄せてある。

| この形式 | GitHub REST（pulls review comments） |
|---|---|
| `threads[].path` | `path` |
| `threads[].line` / `side` | `line` / `side` |
| `threads[].start_line` / `start_side` | `start_line` / `start_side` |
| `comments[].body` | `body` |
| `comments[].in_reply_to` | `in_reply_to_id` |
| `reviews[].state` | `event` / `state`（`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED`） |
| `comments[].severity` | （対応なし。GitHub にはこの語彙が無いので、本文の接頭辞に落とす想定） |
| `threads[].kind` | （対応なし。`note` は GitHub では普通のコメントになる） |

**互換を保証するものではない**（GitHub への書き戻しはこの skill のスコープ外）。名前を揃えてあるだけ。
