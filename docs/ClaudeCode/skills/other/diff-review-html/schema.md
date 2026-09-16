# レビュー記録 JSON スキーマ（`diff-review/1`）

`diff-review-html` が読み書きする唯一の外部形式。**人間（画面）と AI（テキスト）の契約点**であり、
画面・`diff_review.py`・AI エージェントの 3 者はすべてこの形だけをやり取りする。

> AI がこの JSON を**書く**ときは、`diff_review.py template` が出す雛形から始めること。
> `target` を手で書くと、どの差分に対する指摘なのかが合わなくなる。

## 全体の形

```json
{
  "schema": "diff-review/1",
  "target": { "...": "対象の差分（雛形が埋める。手で書かない）" },
  "reviews": [ { "...": "提出されたレビュー（判定とサマリ）" } ],
  "threads": [ { "...": "コメントのスレッド" } ]
}
```

| キー | 型 | 説明 |
|---|---|---|
| `schema` | string | 固定で `"diff-review/1"`。違う値は読み込みも検証も拒否される |
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
  "path": "docs/x.md",
  "line": 120,
  "side": "RIGHT",
  "start_line": null,
  "start_side": null,
  "resolved": false,
  "comments": [
    { "id": "c1", "review_id": "r1", "author": "ai", "body": "この分岐は null を踏みます", "in_reply_to": null },
    { "id": "c2", "review_id": null, "author": "human", "body": "直しました", "in_reply_to": "c1" }
  ]
}
```

| キー | 型 | 説明 |
|---|---|---|
| `id` | string | 記録内で一意 |
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
| `review_id` | string \| null | 属する提出レビューの `id`。**`null` は「未提出（pending）」** |
| `author` | string | `human` / `ai` / 任意の名前 |
| `body` | string | 本文（空は不可） |
| `in_reply_to` | string \| null | **同じスレッド内の**コメント `id`。起点は `null` |

## 正規形（書き出しの形）

- UTF-8・LF・末尾に改行 1 つ。
- **キーは昇順**、インデントはスペース 2、非 ASCII はエスケープしない。
- Python では `json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"`。
- 画面（JavaScript）も同じ形で書き出すので、**書き出し → 読み込み → 再書き出しでバイト一致する**。
- **時刻を持たない**。持たせると同じ内容でも出力が変わり、差分として読めなくなる。

## 検証（何を弾くか）

`python3 diff_review.py check <review.json>` が見るもの。1 件でも該当すれば終了コード 3。

- `schema` が `diff-review/1` でない
- `target` / `reviews` / `threads` の欠落や型違い
- `reviews[].state` が 3 値のいずれでもない
- `threads[].line` があるのに `path` が無い / `side` が `LEFT` `RIGHT` でない
- `threads[].line` が `null` なのに `side` がある
- `comments` が空、`body` が空
- `id` の重複（レビュー・スレッド・スレッド内コメント）
- `review_id` が存在しないレビューを指している
- `in_reply_to` が同じスレッドに無いコメントを指している

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

**互換を保証するものではない**（GitHub への書き戻しはこの skill のスコープ外）。名前を揃えてあるだけ。
