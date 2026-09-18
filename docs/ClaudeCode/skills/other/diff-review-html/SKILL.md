---
name: diff-review-html
description: ローカルの git 差分（未ステージ / ステージ済み / コミット間）や、GitHub の PR・任意の2リビジョン間の比較（API 経由・ローカルリポジトリ不要）を、GitHub の PR 画面のように読める単一HTMLにして出力する。差分と指摘を1ファイルにまとめたバンドル（.dreview）と、それを開くビューアHTMLに分けて出すこともでき、エディタ拡張の土台になる。配布用に書き込み機能を積まない参照専用HTMLも出せる。ファイル一覧（左・ツリー/フラット）・差分（中央・unified/split 切り替え）・コメント一覧（右）の3ペインで、左右はD&Dで幅を変えられ畳める。ライト/ダーク/OS追従のテーマ切り替え、シンタックスハイライト、CSV/TSV・Markdown（mermaid・alert記法）・HTML・PDF の rich diff、前後の行を押した分だけ広げる段階展開つき。画面では行・ファイル・全体の3階層にコメントし、must/should/nit の重大度、コメントごとの返信、解決、提出（Approve / Request changes / Comment）、レビュー対象外の説明コメントまで行え、その記録をJSONで書き出し／読み込みできる。AIが書いた指摘のJSONを埋め込んだHTMLを作ることも、人間が書いた指摘のJSONをAIが読んで修正することもできる。「差分をHTMLで見たい」「差分レビューの画面を作って」「レビュー用のHTMLを生成して」「レビュー結果をJSONで受け渡したい」「レビュー記録のJSONを読み込んで」「差分をファイルに切り出して」「レビュー用のビューアを作って」「読むだけのHTMLを配りたい」と言われたときに使用する。GitHub の PR・比較の**差分取得**（読み取り）はできるが、GitHub の PR への投稿（コメント・レビューの書き戻し）は行わない。
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

## サブコマンド

| したいこと | サブコマンド |
|---|---|
| **HTML を出す**（差分 ＋ 画面 ＋ 指摘を 1 枚に） | `html` |
| **差分ファイルを出す**（差分 ＋ 指摘を 1 ファイルに。画面は含まない） | `bundle` |
| **ビューアを出す**（画面だけ。差分は開いて読み込む） | `view` |
| **JSON を作る**（AI が指摘を書くための雛形） | `template` |
| **指摘を書く**（AI / 人が記録に足す） | `comment` / `resolve` / `submit` |
| **読む・検証する**（記録でもバンドルでも） | `check` / `list` |

### 差分の取得元（すべてのサブコマンド共通）

```sh
--from unstaged      # 未コミットの変更（既定）
--from staged        # ステージ済みの変更
--from range  --rev main..HEAD
--from commit --rev 3d6624e
--from github-pr      --github-pr <owner>/<repo>#<番号>            # ローカルリポジトリ不要
--from github-compare --github-repo <owner>/<repo> --rev A...B    # 同上（3 ドット必須）
```

従来のフラグ（`--unstaged` / `--staged` / `--range A..B` / `--commit C`）も**そのまま使える**。
ただし `--from` との**併用はできない**（同じことを 2 通りで書けるので、矛盾として落とす）。

**`github-pr` / `github-compare` は GitHub REST API（既定 `https://api.github.com`）から取る**。
`--repo`（ローカルリポジトリ）は不要——clone していなくても PR 番号や比較対象を指定するだけでよい。

```sh
# PR（owner/repo#番号 でも PR の URL でもよい）
python3 <skill>/diff_review.py html --from github-pr --github-pr octocat/hello-world#42 --out review.html
python3 <skill>/diff_review.py html --from github-pr --github-pr https://github.com/octocat/hello-world/pull/42 --out review.html

# PR に紐付かない任意の 2 リビジョン間（3 ドット。GitHub の compare URL と同じ書式）
python3 <skill>/diff_review.py html --from github-compare \
        --github-repo octocat/hello-world --rev main...feature --out review.html
```

**認証**（非公開リポジトリ・レート制限の緩和に使う。無くても公開リポジトリは取得できる）:

```sh
--github-token <TOKEN>          # 省略時は環境変数 GITHUB_TOKEN → GH_TOKEN の順に探す
--github-api-base <URL>         # GitHub Enterprise 等（既定: https://api.github.com）
```

トークンは環境変数での指定を推奨する（`--github-token` はプロセス一覧に一時的に見える）。
GitHub 側のエラー（存在しない PR・認証エラー・レート制限）は、HTTP ステータスと GitHub からの
メッセージを添えて `EXIT_NETWORK`（4）で失敗する——黙って空の差分を返さない。

### 1. HTML を出す

```sh
# 未コミットの変更（既定）
python3 <skill>/diff_review.py html --repo . --out review.html

# ステージ済み / コミット間 / 特定のコミット
python3 <skill>/diff_review.py html --repo . --from staged                  --out review.html
python3 <skill>/diff_review.py html --repo . --from range  --rev main..HEAD --out review.html
python3 <skill>/diff_review.py html --repo . --from commit --rev 3d6624e    --out review.html

# AI が書いた指摘を埋め込んで渡す
python3 <skill>/diff_review.py html --repo . --import review.json --out review.html

# 配布用（読むだけ。コメント入力・提出・JSON 入出力を積まない）
python3 <skill>/diff_review.py html --repo . --import review.json --readonly --out share.html
```

`--out` を省くと標準出力へ出る。`--context N` で前後の文脈行数、`--title` で見出しを変えられる。
できた HTML はブラウザで開くだけでよい（サーバは要らない）。

**容量と rich を調整するフラグ**:

| フラグ | 既定 | 何が変わるか |
|---|---|---|
| `--expand-max-lines N` | 2000 | 画面で前後を展開するために全文を埋める上限（行数）。**超えるファイルは展開できない**（画面に理由が出る）。`0` で展開データを一切埋めない（いちばん軽い）。**ハイライトは影響を受けない**——差分行にしか乗らないので軽い |
| `--rich auto\|off` | auto | `off` にすると CSV/Markdown/HTML/PDF の rich diff を作らない。**auto でも対象が 1 件も無ければ描画コードは埋め込まれない** |

### 1b. 差分ファイル（バンドル）とビューアに分ける

**1 枚の HTML に焼き固める代わりに、「中身」と「画面」を分けられる。**
エディタ拡張のように「ファイルを開くとビューアが立ち上がる」形の土台になる。

```sh
# 中身: 差分 ＋ 指摘を 1 ファイルに（拡張子 .dreview）
python3 <skill>/diff_review.py bundle --repo . --from range --rev main..HEAD \
        --import review.json --out rev-abc.dreview

# 画面: ビューアだけ（差分を持たない）。開いて .dreview を選ぶ
python3 <skill>/diff_review.py view --out viewer.html
```

**ビューアは、どのバンドルも自動では読まない。** 中身は開いたときに選ぶ（または埋め込み / ホストが渡す）。
ビューアが特定のファイル名を指す形にすると、配ったあと
「このビューアはどれを見ているのか」がファイル名任せになり、**決まらなくなる**ため。

**バンドルの中身**は、代入文 1 行に包んだ正規形 JSON。

```js
window.__DIFF_REVIEW_BUNDLE__ = {
  "schema": "diff-review-bundle/1",
  "target": { … }, "files": [ … ], "rich_enabled": true,
  "review": { "schema": "diff-review/2", … }   // 指摘。無ければ null
};
```

前置き `window.__DIFF_REVIEW_BUNDLE__ = ` と後置き `;\n` は**固定**なので、
**JS を実行せずに JSON としても読める**（Python・Node の両方で検査している）。

**ビューアがバンドルを受け取る口は 3 つ**（**どれもファイルを実行しない**）:

| 口 | 誰が使う | いつ |
|---|---|---|
| **手動**（ファイル選択 / ドラッグ＆ドロップ） | 人間 | 開いたあと、いつでも |
| **埋め込み**（HTML の中に書いてある） | `html` の出力 / ホストが組み立てた HTML | 起動時 |
| **`postMessage`** | ホスト（エディタ拡張・親フレーム） | いつでも |

埋め込みの口は 2 種類ある。`html` サブコマンドの出力は `#diff-data` と `#review-data` を埋める。
ホスト（エディタ拡張など）が HTML を組み立てて渡すときは、
ビューアにある**空の `#bundle-data`** にバンドルをそのまま書き込む。

```html
<!-- view の出力に最初から入っている（中身は空） -->
<script type="application/json" id="bundle-data"></script>
```

`postMessage` は、**開いたあとに中身を差し替える**ための口。
ホストはバンドルをそのまま（または `{type: "diff-review/bundle", bundle: …}` の形で）投げる。
形が合わないメッセージは黙って無視するので、ホストが自分の用事で使っている `postMessage` と
混ざっても害はない。

> [!NOTE]
> **外部ファイルを読む口（`<script src>`）は持ちません。**
> `file://` で隣のファイルを読める唯一の手段ですが、**どのバンドルを読むのかが
> ファイル名任せになって決まらなくなる**うえ、そのファイルを**実行する**ことにもなります。
> 他人から受け取ったバンドルは「ファイルを開く」から読み込んでください（実行されません）。

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
  "kind": "review",
  "path": "src/parse.py",
  "line": 120,
  "side": "RIGHT",
  "start_line": null,
  "start_side": null,
  "resolved": false,
  "comments": [
    { "id": "c1", "review_id": null, "author": "ai", "body": "空文字のとき例外になります",
      "severity": "must", "in_reply_to": null }
  ]
}
```

- 行コメントは `path` ＋ `line` ＋ `side`（`RIGHT`＝追加・文脈行 / `LEFT`＝削除行）。
- ファイル単位は `line: null`、差分全体は `path: null` と `line: null`。
- **重大度**は `severity`（`must` / `should` / `nit` / `null`）。受け取る側が着手順を機械的に決められる。
- **説明**（指摘ではない注記）は `kind: "note"`。提出されず、未解決にも数えない（`severity` は付けない）。
- 判定を添えるなら `reviews` に 1 件足し、そのコメントの `review_id` にその `id` を書く。

### 2b. 指摘を書く（AI がレビューする場合・推奨）

**`threads` を手で組み立てなくてよい。** `id` の採番も形の規則も script が面倒を見る。

```sh
# 行への指摘（重大度つき）
python3 <skill>/diff_review.py comment rev-abc.dreview \
        --path src/parse.py --line 120 --severity must --body "空文字のとき例外になります"

# 削除された行への指摘
python3 <skill>/diff_review.py comment rev-abc.dreview \
        --path src/old.py --line 8 --side LEFT --body "これを消した理由は？"

# ファイル単位 / 差分全体（--line を省く / --path も省く）
python3 <skill>/diff_review.py comment rev-abc.dreview --path src/parse.py --body "…"
python3 <skill>/diff_review.py comment rev-abc.dreview --body "全体として…"

# 説明コメント（提出されず、未解決にも数えない）
python3 <skill>/diff_review.py comment rev-abc.dreview \
        --path src/parse.py --line 30 --note --body "ここは意図的に残しています"

# 返信（返信への返信も同じ。--reply-to t1 はそのスレッドの最後のコメントへ）
python3 <skill>/diff_review.py comment rev-abc.dreview --reply-to t1 --body "直しました"
python3 <skill>/diff_review.py comment rev-abc.dreview --reply-to t1:c1 --body "c1 への返信"

# 解決 / 提出
python3 <skill>/diff_review.py resolve rev-abc.dreview --thread t1
python3 <skill>/diff_review.py submit  rev-abc.dreview --state CHANGES_REQUESTED --body "まとめ"
```

**長い本文は引数に押し込まない**——`--body-file <FILE>`、または `--body-file -` で標準入力から。

#### 存在しない行には書けない

`--line` を指定すると、**その位置が差分に実在するかを確かめてから**書く。
無ければ**何も書かずに**終了コード 3 で落ち、**そのファイルで指摘できる位置**を出す。

```
$ … comment rev-abc.dreview --path src/core/util.py --line 999 --body "…"
NG（1 件。何も書き込んでいません）
  src/core/util.py:999 (RIGHT) はこの差分に存在しません
    このファイルで指摘できる位置: RIGHT 1-40 / LEFT 10-12, 21
```

**バンドル（`.dreview`）を渡せば、リポジトリが手元になくても確かめられる**（差分を持っているため）。
記録 JSON を渡すときは `--repo`（と必要なら `--from` / `--rev`）が要る。

#### `--side` の既定は **RIGHT**（規約）

`LEFT` は削除行、`RIGHT` は追加行と文脈行。省略したときは——

- 片側にしか無ければ**その側**に決まる（削除ファイルの行なら `LEFT`）
- **両側にある場合（その行が書き換えられたとき）は `RIGHT`**

最後のものは推測ではなく**決めごと**です（GitHub の REST も既定は `RIGHT`）。
変更前の行を指したいときは `--side LEFT` を明示してください。

#### まとめて足す

20 件の指摘に 20 回プロセスを起こさなくてよい。**1 件でも駄目なら 1 件も書き込まない。**

```sh
python3 <skill>/diff_review.py comment rev-abc.dreview --batch findings.json
```

```json
[
  {"path": "src/a.py", "line": 12, "severity": "must", "body": "空文字で落ちます"},
  {"path": "src/a.py", "line": 8, "side": "LEFT", "body": "消したのは意図的ですか"},
  {"path": "src/a.py", "line": 30, "note": true, "body": "ここは意図的に残しています"},
  {"reply_to": "t1", "body": "直しました"}
]
```

キーは引数名から `--` を取って `-` を `_` にしたもの（`path` / `line` / `side` / `body` /
`severity` / `note` / `reply_to` / `author`）。**知らないキーは落とします**（綴り違いを握り潰さない）。
失敗したときは**全件ぶんまとめて**理由が出るので、1 往復で直せます。

> `--batch` の中で、同じ実行の中で作ったスレッドには返信できません
> （書く前に全件を検証するため）。返信は別の実行にしてください。

### 3. JSON を読む（AI が修正する場合）

`check` と `list` は**記録 JSON でもバンドルでも**受ける（拡張子ではなく中身で判別する）。

```sh
python3 <skill>/diff_review.py check review.json                 # 構造・参照・値域を検証
python3 <skill>/diff_review.py check rev-abc.dreview             # バンドルも同じコマンドで
python3 <skill>/diff_review.py check rev-abc.dreview --anchors   # 指摘の位置が実在するかも見る
python3 <skill>/diff_review.py list  review.json                 # 未解決の指摘だけを一覧に
python3 <skill>/diff_review.py list  review.json --severity must  # must だけ（should,nit,none も指定可）
python3 <skill>/diff_review.py list  review.json --notes          # 作者の説明コメントも出す
python3 <skill>/diff_review.py list  review.json --format tsv     # path<TAB>重大度<TAB>state<TAB>kind<TAB>本文
python3 <skill>/diff_review.py list  review.json --all            # 解決済みも出す
```

`list` の出力（`path:line` と本文）をそのまま修正の作業リストにできる。
**直したら `resolved` を立てるのではなく、人間に返す**——解決の判断はレビューした側が行う。
直した報告は `comment --reply-to <スレッド> --body "直しました"` で同じスレッドに残せる。

## 画面でできること

### 画面の形（3 ペイン）

```
┌──────────────┬──────────────────────┬──────────────┐
│ 変更ファイル │        差分          │ コメント一覧 │
│ ツリー/フラット│  unified / split     │ 絞り込み・移動 │
└──────────────┴──────────────────────┴──────────────┘
      ↑ 境界をドラッグして幅を変える・畳む（キーボードでも可）
```

- **左**: 変更ファイル一覧。**ツリー ↔ フラット**を切り替えられる（ツリーは深さに応じて字下げされ、
  ディレクトリを開閉でき、子が 1 つだけのディレクトリは `a/b/c` と 1 行にまとまる）。選ぶと差分の該当位置へ
  移動し、**フォーカスもそこへ移る**。**検索欄**でファイル一覧を絞り込める（下記）。
  一覧の各ファイルに**確認済みチェックボックス**があり、見出しに確認済み件数 / 全体件数が出る
  （「N / M 確認済み」）。

#### ファイル一覧の検索

検索欄には 3 通りの書き方ができる。

| 書き方 | 例 | 意味 |
|---|---|---|
| そのまま | `util` | パスに含まれるかの部分一致（大文字小文字を区別しない） |
| ワイルドカード（`*` / `?`） | `src/*.py` | `*` は 0 文字以上、`?` は任意の 1 文字 |
| 正規表現（`/…/フラグ`） | `/^src\/api\//` | スラッシュで囲むとそのまま正規表現として使う |

一致件数を欄の下に出す。正規表現が壊れているときはエラー内容を出し、欄に印をつける
（一覧は絞り込まれない）。ツリー表示中に検索すると、一致する枝が見えるようすべて開く
（検索を消せば元の開閉状態に戻る）。ファイルの**中身**は検索しない（パスだけ）。
- **中央**: 差分。**unified ↔ split（左右 2 列）**を切り替えられる（`s` キー）。
  split では削除行と追加行が同じ行に対応づき、片側しか無い行は反対側が空になる。
  左右それぞれの行にコメントでき、`side` が `LEFT` / `RIGHT` になる。
- **右**: コメント一覧。すべての指摘を位置・重大度・状態つきで並べ、
  **未解決のみ / 重大度 / 説明を含むか**で絞れる。選ぶとその指摘の位置へ移動する。
- **左右のペインは畳める**（トップバーのボタン・`{` / `}` キー・境界で `Enter`）。
  `[` / `]` は**そのペインへ移動**する（差分の奥から Tab だけでコメント一覧へ行くのは現実的でないため）。
  **境界をドラッグすると幅が変わる**（矢印キーでも。`Shift` 併用で大きく、`Home` / `End` で最小 / 最大）。
- **テーマ**は ライト / ダーク / OS に従う の 3 状態を巡回するボタンで切り替える。
- 表示形式・一覧の形・テーマ・ペインの開閉と幅・コメント一覧の絞り込み・**確認済みの状態**は
  **そのブラウザに記憶される**（`localStorage`。**レビュー記録の JSON には入らない**——
  「確認済み」は画面を見た記録であって指摘ではないため、書き出しても JSON には出てこない）。
  ファイル一覧の**検索語**は記憶しない（開き直すたびに空欄から始まる）。
- 幅の狭い画面（900px 以下）では 3 列が縦に積み重なる。

### 差分とコメント

- 変更ファイル一覧（追加 / 削除行数つき）、ファイル単位の折りたたみ、追加 / 削除の色分け
- ファイルの見出しは、**折りたたみ**（アイコンのみ）・パス・**パスをコピー**（`⧉`）・
  **確認済みチェックボックス**の順に並ぶ。パス自体はクリックしても何も起きない
  （折りたたみと機能が被るため、クリックでの展開はしない）
- **シンタックスハイライト**（python / javascript / typescript / json / yaml / shell / css / html / markdown / sql）
- **rich diff**（下記）と **rich ↔ source の切り替え**
- **前後の行の段階展開**（`↑ 20 行` / `↓ 20 行` を押すたびに広がる）と、ファイルの
  **「すべて展開」（`⏷`）/「折りたたむ」（`⏶`）**。展開ボタンを押しても**画面の表示位置は動かない**
  （押したボタンの場所にフォーカスが留まる）
- **行 / ファイル / 全体**の 3 階層のコメント、**コメントごとの返信**（返信への返信も可）、解決 / 未解決
- コメントの **重大度**（must / should / nit / なし）
- **説明コメント**（「説明として残す」）——レビュー提出の対象に入らず、未解決にも数えない。
  差分の作者がレビュアーに意図を残すためのもの
- **レビューを開始** → 未提出として溜める → **提出**（Approve / Request changes / Comment ＋ サマリ）
- JSON の書き出し（ダウンロード or コピー用テキストエリア）と読み込み（ファイル選択 / ドラッグ＆ドロップ）
- 書きかけのコメントの自動保存と復元（開き直すたびに**確認なしで自動的に**復元する。
  消したいときは「下書きを初期化」ボタンで明示的に消す）

### rich diff の対応範囲

| 形式 | 何が出るか | 限界 |
|---|---|---|
| `.csv` / `.tsv` | 表として並べ、**変わったセル**に印（行の追加・削除も色分け） | 列がずれる編集は行単位の対応付けに従う |
| `.md` / `.markdown` | 見出し・リスト・表・コード・引用・リンクを描画。**GitHub alert 記法**（`> [!NOTE]` 等 5 種）は専用表示 | 画像は取得せずテキストに落とす（オフライン維持） |
| Markdown 内の **mermaid** | `flowchart` / `graph` / `stateDiagram` / `sequenceDiagram` を **SVG に描いて埋め込む** | **mermaid 公式とは絵が違う**（読める図が目標）。他の図種はコードのまま＋理由 |
| `.html` / `.htm` | `<iframe sandbox="">` で描画（**スクリプトは実行されない**） | 外部リソースは読み込まれない |
| `.pdf` | ページ数・サイズ＋**テキストの差分** | ToUnicode を持たない PDF（スキャン等）ではテキストが取れず、理由が出る |

rich は**生成時に作られる**（ブラウザに解析器を積まない）。対象が 1 件も無ければ描画コードごと省かれる。

### キー操作

| キー | 動作 |
|---|---|
| `j` / `k`（`↓` / `↑`） | 差分の行を移動 |
| `c` / `Enter` | その行にコメントを書く |
| `Esc` | コメント欄を閉じる（**書きかけは残る**） |
| `Ctrl` / `⌘` + `Enter` | コメントを確定（未提出として溜まる） |
| `e` | 前後の行を展開（`Shift` + `E` でそのファイルを全部） |
| `t` | rich 表示 ↔ source 表示 |
| `f` | そのファイルの折りたたみを切り替え |
| `s` | unified 表示 ↔ split 表示 |
| `[` / `]` | 左（ファイル一覧）／右（コメント一覧）**へ移動**（畳んでいれば開く） |
| `{` / `}` | 左／右のペインを畳む・戻す（`Shift` + `[` / `]`） |
| `r` | 提出パネルを開く |
| `?` | キー操作の一覧 |

ツリー表示では `↑` `↓` で項目を辿り、`→` / `←` でディレクトリを開閉、`Enter` で移動する。
ペインの境界にフォーカスを合わせると `←` `→` で幅を変えられる（`Enter` で畳む）。
テーマ・ツリー・絞り込みの切り替え、ファイル検索欄、確認済みチェックボックス、パスコピーは
すべて**ボタンや通常の入力欄**なので `Tab` で届く（専用キーは増やしていない）。
アイコンだけのボタンにも `title`（マウスで hover）と `aria-label`（スクリーンリーダー）を必ず付けている。

## 制限（知っておくこと）

- **GitHub の PR・比較の取得（`--from github-pr` / `github-compare`）は差分の読み取りに限る**。
  PR へのコメント・レビューの投稿は行わない。
- **GitHub 取得元は全文（変更前後のファイル全体）を取得しない**。そのため、前後の段階展開
  （`↑`/`↓`/「すべて表示」）と rich diff（CSV/Markdown/HTML/PDF）は効かない
  （画面には既存の「展開データを持っていません」表示が出る）。構文ハイライトはハンク単位で
  行うため、ハンクをまたぐ構文（複数行コメント等）の検出精度がローカル取得元より低い。
- **GitHub API の未認証リクエストはレート制限が低い**（一般に 60 リクエスト/時。GitHub Docs 案内）。
  非公開リポジトリ・頻繁な利用では `--github-token`（または環境変数 `GITHUB_TOKEN`/`GH_TOKEN`）
  でのトークン指定を推奨する。
- **下書きの自動保存はブラウザ依存**。`file://` の localStorage を塞ぐブラウザ（Firefox 等）では
  保存されない。その場合は画面にその旨が出る。**提出済みの記録は JSON に書き出して保存すること**
  （書き出しだけが確実な永続化）。
- **`file://` では `fetch` / `XHR` / モジュール import が使えない**（実測）。
  隣のファイルを読む手段は `<script src>` だけで、それは**そのファイルを実行する**。
  だから**読む口を持たない**。読み込みは「ファイル選択 / ドラッグ＆ドロップ」、生成時の `--import`、
  ホストが HTML に埋め込む `#bundle-data` に限る。**どれもファイルを実行しない**。
- **開いたあとに中身を差し替えられるのはホストだけ**（`postMessage`）。
  `file://` では送り主を検査できないため、**形が合うかどうかだけ**で受け付ける。
  ブラウザで直接開いて使う分には、他のページから投げ込まれる経路は無い。
- **参照専用は容量を減らすためのものではない**。減るのは HTML の該当部分だけ（数百バイト）で、
  画面のコード自体は残る。目的は「**書き換えて再配布されない**」こと。
- **split は行単位の対応まで**。「行のどこが変わったか」の語単位ハイライトは持たない。
- **split で前後を展開した行は、片側の行番号が空になる**。展開用の全文は片側しか持たないため
  （本文は両側に同じものを出す。文脈行は定義上どちらの側でも同じ内容）。
- **画面の設定はそのブラウザに閉じる**。`file://` では全ページが 1 つの origin を共有するので、
  別のレビュー画面とテーマ・幅を共有する。`localStorage` が使えないブラウザでは既定値で動く
  （テーマは OS に従う）。
- ハイライトは正規表現ベースの近似（構文解析器ではない）。未対応の拡張子は素のまま表示する。
- 大きいファイル（2,000 行超の差分）は既定で折りたたみ、開いたときに描画する。
- `--expand-max-lines`（既定 2,000 行）を超えるファイルは、**前後を展開できない**（全文を埋めないため）。
  画面にその旨が出る。ハイライトは効いたまま（差分行にしか乗らないので容量への影響が小さい）。

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
| `<skill>/schema.md` | **レビュー記録 JSON の正典**（AI が書く前に読む。現行は `diff-review/2`） |
| `<skill>/highlight.py` | シンタックスハイライト（生成時に行う） |
| `<skill>/richdiff.py` | rich diff の生成（CSV / Markdown / mermaid / HTML / PDF） |
| `<skill>/templates/` | 画面の素材（`page.html` / `style.css` / `ui.js` / `app.js` / `rich.js`） |
| `<skill>/tests/test_diff_review.py` | `python3 -m unittest` で回るテスト |
| `<skill>/tests/fixture_repo.py` | 画面の確認に使う**固定の入力**を作る（新規 / 削除 / 置き換え / 隙間 / rich を含む git リポジトリ）。`python3 tests/fixture_repo.py <出力先>` |

## エディタ拡張から使う（土台）

この skill は拡張そのものを持たない。**拡張が守ればよいことだけ**を決めてある。

| 拡張がやること | 備考 |
|---|---|
| `.dreview` を読み、前後を剥がして `JSON.parse` する | **実行しない**。Node で検査済み |
| `view --readonly` で作ったビューア HTML を読む | 差分を持たないので**どのバンドルにも使い回せる** |
| 空の `#bundle-data` にバンドルの JSON を書き込んで `webview.html` に渡す | `<` を `\u003c` に退避すること（`</script>` でブロックが切れるため） |
| 開いたあとの差し替えは `webview.postMessage(bundle)` | 再読み込みしないので、**スクロール位置と現在行が残る**（差分が変わればフォーカスは先頭へ移る） |
| CSP を付けるなら `<script` を `<script nonce="…"` に置換する | 1 か所の置換で済む形にしてある |

> **未検証**: VSCode の webview が CSP 無しで inline script を実行するかは、
> この skill の開発環境（VSCode 無し）では確かめていない。
> 上の契約は「どちらに転んでも拡張側の 1 行で済む」ようにしてあるが、**実機で確かめること**。

## 終了コード

| コード | 意味 |
|---|---|
| 0 | 正常 |
| 1 | 使い方の誤り |
| 2 | `git` の失敗（リポジトリ外・不正なリビジョン等） |
| 3 | レビュー記録 JSON が不正 |
| 4 | GitHub API の失敗（HTTP エラー・接続不可・応答が JSON として読めない） |
