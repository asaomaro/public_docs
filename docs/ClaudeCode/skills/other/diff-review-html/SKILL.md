---
name: diff-review-html
description: ローカルの git 差分（未ステージ / ステージ済み / コミット間）を、GitHub の PR 画面のように読める単一HTMLにして出力する。差分と指摘を1ファイルにまとめたバンドル（.dreview）と、それを開くビューアHTMLに分けて出すこともでき、エディタ拡張の土台になる。配布用に書き込み機能を積まない参照専用HTMLも出せる。ファイル一覧（左・ツリー/フラット）・差分（中央・unified/split 切り替え）・コメント一覧（右）の3ペインで、左右はD&Dで幅を変えられ畳める。ライト/ダーク/OS追従のテーマ切り替え、シンタックスハイライト、CSV/TSV・Markdown（mermaid・alert記法）・HTML・PDF の rich diff、前後の行を押した分だけ広げる段階展開つき。画面では行・ファイル・全体の3階層にコメントし、must/should/nit の重大度、コメントごとの返信、解決、提出（Approve / Request changes / Comment）、レビュー対象外の説明コメントまで行え、その記録をJSONで書き出し／読み込みできる。AIが書いた指摘のJSONを埋め込んだHTMLを作ることも、人間が書いた指摘のJSONをAIが読んで修正することもできる。「差分をHTMLで見たい」「差分レビューの画面を作って」「レビュー用のHTMLを生成して」「レビュー結果をJSONで受け渡したい」「レビュー記録のJSONを読み込んで」「差分をファイルに切り出して」「レビュー用のビューアを作って」「読むだけのHTMLを配りたい」と言われたときに使用する。GitHubのPRそのものへの投稿や取得は行わない。
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
| **読む・検証する**（記録でもバンドルでも） | `check` / `list` |

### 差分の取得元（すべてのサブコマンド共通）

```sh
--from unstaged      # 未コミットの変更（既定）
--from staged        # ステージ済みの変更
--from range  --rev main..HEAD
--from commit --rev 3d6624e
--from github-pr     # まだ未対応（黙って別の差分を出さず、理由を出して落ちる）
```

従来のフラグ（`--unstaged` / `--staged` / `--range A..B` / `--commit C`）も**そのまま使える**。
ただし `--from` との**併用はできない**（同じことを 2 通りで書けるので、矛盾として落とす）。

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

# 画面 ＋ 焼き込み: そのバンドルを最初から読むビューア（※下の注意）
python3 <skill>/diff_review.py view --load rev-abc.dreview --out viewer.html
```

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

**ビューアがバンドルを受け取る口は 4 つ**:

| 口 | 誰が使う | バンドルを実行するか |
|---|---|---|
| `window.__DIFF_REVIEW_BUNDLE__` が定義済み | `--load` で焼き込んだビューア / ホストの注入 | **する** |
| 埋め込み（`html` の出力） | 通常の 1 枚 HTML | しない |
| `postMessage` | エディタ拡張・親フレーム | しない |
| ファイル選択 / ドラッグ＆ドロップ | 人間 | しない |

> [!WARNING]
> **`--load` で焼き込むと、そのバンドルは開いた時点で実行されます。**
> `file://` では `fetch` も `XMLHttpRequest` も使えず、隣のファイルを読む手段が
> `<script src>` しかないためです（実測）。他人から受け取った `.dreview` を
> 焼き込んだビューアで開くのは、**他人の HTML を開くのと同じ危険度**です。
> だから **既定では焼き込みません**。自分で作ったバンドルを自分で見るときだけ使ってください。
> 他人から受け取ったものは、**「ファイルを開く」から読み込んでください**（実行されません）。

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

### 3. JSON を読む（AI が修正する場合）

`check` と `list` は**記録 JSON でもバンドルでも**受ける（拡張子ではなく中身で判別する）。

```sh
python3 <skill>/diff_review.py check review.json                 # 構造・参照・値域を検証
python3 <skill>/diff_review.py check rev-abc.dreview             # バンドルも同じコマンドで
python3 <skill>/diff_review.py list  review.json                 # 未解決の指摘だけを一覧に
python3 <skill>/diff_review.py list  review.json --severity must  # must だけ（should,nit,none も指定可）
python3 <skill>/diff_review.py list  review.json --notes          # 作者の説明コメントも出す
python3 <skill>/diff_review.py list  review.json --format tsv     # path<TAB>重大度<TAB>state<TAB>kind<TAB>本文
python3 <skill>/diff_review.py list  review.json --all            # 解決済みも出す
```

`list` の出力（`path:line` と本文）をそのまま修正の作業リストにできる。
**直したら `resolved` を立てるのではなく、人間に返す**——解決の判断はレビューした側が行う。

## 画面でできること

### 画面の形（3 ペイン）

```
┌──────────────┬──────────────────────┬──────────────┐
│ 変更ファイル │        差分          │ コメント一覧 │
│ ツリー/フラット│  unified / split     │ 絞り込み・移動 │
└──────────────┴──────────────────────┴──────────────┘
      ↑ 境界をドラッグして幅を変える・畳む（キーボードでも可）
```

- **左**: 変更ファイル一覧。**ツリー ↔ フラット**を切り替えられる（ツリーではディレクトリを開閉でき、
  子が 1 つだけのディレクトリは `a/b/c` と 1 行にまとまる）。選ぶと差分の該当位置へ移動し、
  **フォーカスもそこへ移る**。
- **中央**: 差分。**unified ↔ split（左右 2 列）**を切り替えられる（`s` キー）。
  split では削除行と追加行が同じ行に対応づき、片側しか無い行は反対側が空になる。
  左右それぞれの行にコメントでき、`side` が `LEFT` / `RIGHT` になる。
- **右**: コメント一覧。すべての指摘を位置・重大度・状態つきで並べ、
  **未解決のみ / 重大度 / 説明を含むか**で絞れる。選ぶとその指摘の位置へ移動する。
- **左右のペインは畳める**（トップバーのボタン・`{` / `}` キー・境界で `Enter`）。
  `[` / `]` は**そのペインへ移動**する（差分の奥から Tab だけでコメント一覧へ行くのは現実的でないため）。
  **境界をドラッグすると幅が変わる**（矢印キーでも。`Shift` 併用で大きく、`Home` / `End` で最小 / 最大）。
- **テーマ**は ライト / ダーク / OS に従う の 3 状態を巡回するボタンで切り替える。
- 表示形式・一覧の形・テーマ・ペインの開閉と幅・コメント一覧の絞り込みは
  **そのブラウザに記憶される**（`localStorage`。**レビュー記録の JSON には入らない**）。
- 幅の狭い画面（900px 以下）では 3 列が縦に積み重なる。

### 差分とコメント

- 変更ファイル一覧（追加 / 削除行数つき）、ファイル単位の折りたたみ、追加 / 削除の色分け
- **シンタックスハイライト**（python / javascript / typescript / json / yaml / shell / css / html / markdown / sql）
- **rich diff**（下記）と **rich ↔ source の切り替え**
- **前後の行の段階展開**（`↑ 20 行` / `↓ 20 行` を押すたびに広がる）と、ファイルの **「すべて展開」**
- **行 / ファイル / 全体**の 3 階層のコメント、**コメントごとの返信**（返信への返信も可）、解決 / 未解決
- コメントの **重大度**（must / should / nit / なし）
- **説明コメント**（「説明として残す」）——レビュー提出の対象に入らず、未解決にも数えない。
  差分の作者がレビュアーに意図を残すためのもの
- **レビューを開始** → 未提出として溜める → **提出**（Approve / Request changes / Comment ＋ サマリ）
- JSON の書き出し（ダウンロード or コピー用テキストエリア）と読み込み（ファイル選択 / ドラッグ＆ドロップ）
- 書きかけのコメントの自動保存と復元

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
テーマ・ツリー・絞り込みの切り替えは**ボタン**なので `Tab` で届く（専用キーは増やしていない）。

## 制限（知っておくこと）

- **GitHub の PR には触らない**。PR からの差分・コメント取得も、PR への投稿も行わない。
- **下書きの自動保存はブラウザ依存**。`file://` の localStorage を塞ぐブラウザ（Firefox 等）では
  保存されない。その場合は画面にその旨が出る。**提出済みの記録は JSON に書き出して保存すること**
  （書き出しだけが確実な永続化）。
- **`file://` では `fetch` / `XHR` / モジュール import が使えない**（実測）。
  隣のファイルを読む手段は `<script src>` だけで、それは**そのファイルを実行する**。
  だから既定では読まない。読み込みは「ファイル選択 / ドラッグ＆ドロップ」（実行なし）、
  生成時の `--import`、または明示的な `--load`（実行あり）に限る。
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

## エディタ拡張から使う（土台）

この skill は拡張そのものを持たない。**拡張が守ればよいことだけ**を決めてある。

| 拡張がやること | 備考 |
|---|---|
| `.dreview` を読み、前後を剥がして `JSON.parse` する | **実行しない**。Node で検査済み |
| `view --readonly` で作ったビューア HTML を webview に流す | 差分を持たないので使い回せる |
| バンドルを `postMessage` で渡す（または `window.__DIFF_REVIEW_BUNDLE__` を注入） | 前者は実行を伴わない |
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
