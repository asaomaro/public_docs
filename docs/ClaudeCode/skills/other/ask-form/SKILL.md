---
name: ask-form
description: ユーザーに決めてもらうことが多いとき（質問が 5 つ以上、選択肢が 5 つ以上、前の回答で次の質問が変わる等）に、すべての質問を 1 つの単発ウィンドウにまとめて出し、回答を JSON で受け取る。選ぶ・複数選ぶ・書く・文面を直して返す・並べ替える・表で行ごとに選ぶ質問と、画像・コード・音のプレビュー、絞り込みを持つ。ウィンドウは自動で開き、決定すると自動で閉じてターミナルに戻る。スキルが作った成果物（HTML・Markdown・mermaid の図・画像・テキスト）を横に見せて、承認か修正の依頼かを聞くこともできる。AskUserQuestion の「1 問 4 択まで・1 回 4 問まで」に収まらない確認に使う。選んでもらう前に質問と選択肢をすべて書き出し、4 問・4 択に収まらなければこのスキルを使う（AskUserQuestion に収めるために選択肢を削ったりまとめたりしない）。ほかのスキルから部品として呼べる。「質問をまとめて聞いて」「フォームで聞いて」「選択肢を一覧で出して」「成果物を見せて確認して」と言われたとき、またはほかのスキルから案内されたときに使用する。
---

# ask-form — 質問をまとめて 1 つのウィンドウで聞く

`AskUserQuestion` は **1 問あたり選択肢 4 つまで・1 回 4 問まで**。それを超える確認は、
同梱の `ask.py`（Python3 / 標準ライブラリのみ）で 1 画面にまとめて聞く。

- タブではなく**単独のウィンドウ**が開く（Edge / Chrome の `--app` モード。画面の中央・中身に合う高さ）。
- すべての質問が 1 つのウィンドウに並ぶ。既定の回答は選択済みで出るので、変えたいところだけ触ればよい。
- 質問が多くてウィンドウの高さに収まらないときは、**左に質問の題の目次が出る**（スクロールに合わせて今の質問に印が付き、押すとその質問へ移る）。
- 「決定」（`Ctrl+Enter`）でウィンドウが閉じ、フォーカスがターミナルに戻る。`Esc` でキャンセル。
- 前の回答で出し分ける質問（`showIf`）、自由入力（`allowOther`）、複数選択、補足の欄を持つ。
- 選択肢に**画像とコードのプレビュー**を付けられる（画面案の見比べ・実装方針の比較・差分の確認）。音は試聴できる。
- 選ぶ以外に、**文面を直して返す**（`edit`）・**並べ替える**（`rank`）・**表で行ごとに選ぶ**（`table`）質問を出せる。
- 選択肢が多いときは**絞り込み**と**分類の見出し**が付く。前回の回答を既定にできる（`remember`）。
- **画面の前に人がいないとき**（スマホなど別の端末から指示しているとき）は、ウィンドウを出さずに `AskUserQuestion` へ切り替わる。

## どちらで聞くかの決め方

`AskUserQuestion` を前提に考えると、枠に合わせて選択肢を削ってしまい、削ったことはユーザーから見えない。
そこで、**道具を選ぶ前に数える**。

1. 聞きたい質問と選択肢を**すべて書き出す**（この時点では上限を考えない）。
2. **4 問以内・どの質問も 4 択以内**に収まれば `AskUserQuestion`。収まらなければ ask-form。
3. `AskUserQuestion` に収めるために、選択肢を削る・まとめる・黙って「その他」に回す、をしない。

- コードや画面案を見比べて選ぶ質問は、選択肢の `code`・`image` でプレビューを付ける（下の「プレビュー」）。
  画像を見せたいときは `AskUserQuestion` では出せないので、問数に関わらず ask-form を使う。
- ask-form を出せない環境では `AskUserQuestion` に分けて聞く（下の「出せないとき」）。

## 使い方

質問の定義（JSON）を標準入力で渡し、**Bash の `timeout` を `600000` にして**実行する（回答を待つ間ブロックする。既定で 540 秒待つ）。

```bash
python3 <skill_dir>/ask.py - <<'JSON'
{
  "title": "リリースの設定",
  "intro": "v1.4.0 を出す前の確認です。",
  "submit": "この内容で進める",
  "questions": [
    {"id": "channel", "label": "配布先", "default": "beta",
     "options": [
       {"value": "beta", "label": "ベータ", "desc": "社内と登録者のみ。", "recommended": true},
       {"value": "stable", "label": "安定版", "desc": "全ユーザーに配る。"}
     ]},
    {"id": "notes", "label": "告知", "type": "multi", "default": ["changelog"],
     "options": ["changelog", "blog", "mail"]},
    {"id": "rollout", "label": "段階的に配るか", "showIf": {"channel": "stable"}, "default": "10",
     "options": [{"value": "10", "label": "10% から"}, {"value": "100", "label": "一度に全員"}],
     "allowOther": true, "otherPlaceholder": "割合を入力（例: 25）"}
  ]
}
JSON
```

標準出力に 1 行の JSON が出る。

```json
{"status": "answered", "answers": {"channel": "stable", "notes": ["changelog", "mail"], "rollout": "25"}, "custom": ["rollout"], "note": "金曜は避けたい"}
```

| 終了コード | `status` | 意味と、次にすること |
|---|---|---|
| 0 | `answered` | 回答あり。`answers` に従って進める。`comments`（質問ごとの自由記述）と `note`（補足の欄）があれば必ず読んで反映する |
| 2 | `cancelled` | 回答せずに閉じた／キャンセルした。勝手に既定で進めず、どうするかをユーザーに聞く |
| 3 | `unavailable` | ウィンドウを出せない環境。**同じ質問を `AskUserQuestion` で聞き直す**（下の「出せないとき」） |
| 4 | `timeout` | 時間切れ。まだ必要かをユーザーに確かめてから、もう一度出す |
| 1 | — | 定義の誤り（標準エラーに理由）。直して再実行する |

- `answers` のキーは質問の `id`。`single` は文字列、`multi` は配列、`text` は文字列。
- `showIf` で隠れていた質問は `answers` に**入らない**（キーが無い＝聞いていない）。
- `custom` は「その他」に自由入力した質問の `id`。値が選択肢に無い文字列なので、解釈してから使う。
- `comments` は、質問ごとの自由記述（`{質問の id: 書いた文}`。書いた質問だけ入る）。**その質問の答えへの条件・希望として必ず読み、答えと合わせて解釈する**
  （例: `"palette": "daylight"` に「もう少し暗めで」）。各質問（書く質問 `text` を除く）の下の「＋ 自由記述」を押すと欄が開く。
  質問が 1 つだけで選んだ時点で決定するフォームには付かない。

## 質問の定義

全体:

| キー | 既定 | 内容 |
|---|---|---|
| `title` | 「質問」 | ウィンドウの題 |
| `intro` | なし | 題の下の説明（何のための確認か） |
| `submit` | 「決定」 | 決定ボタンの文言 |
| `note` | `true` | 末尾の「補足」欄。`false` で出さない。文字列ならその欄の入力例 |
| `comments` | `true` | 質問ごとの自由記述（「＋ 自由記述」のボタンで開く欄）。`false` で、どの質問にも付けない |
| `remember` | なし | 名前を書くと、前回の回答を次回の既定にする（下の「前回の回答を既定にする」） |
| `view` | なし | 質問の横に見せる成果物（HTML・画像・テキスト）。下の「成果物を見せて確認してもらう」 |
| `paging` | `"auto"` | 目次（質問の題の一覧）の出し方。`"auto"`（高さに収まらないときだけ出す）/ `true`（必ず出す）/ `false`（出さない）。下の「目次」 |
| `questions` | 必須 | 質問の配列（上から順に表示） |

質問:

| キー | 既定 | 内容 |
|---|---|---|
| `id` | 必須 | 回答のキー。呼び出し側の引数名と揃えると、そのまま渡せる |
| `label` | 必須 | 質問の見出し |
| `type` | `single` | `single`（1 つ選ぶ）/ `multi`（複数選ぶ）/ `text`（自由記述。`multiline` で複数行）/ `edit`（文面を直して返す）/ `rank`（並べ替える）/ `table`（表で行ごとに 1 つ選ぶ）。後ろの 3 つは下の「選ぶ以外の質問」 |
| `help` | なし | 見出しの下の補足 |
| `page` | なし | まとまりの題。書いた質問から新しいまとまりが始まり、目次の見出しになる（下の「目次」） |
| `options` | — | 選択肢の配列。文字列（値＝表示名）か、下のオブジェクト。**数に上限は無い** |
| `default` | なし | 最初から選んでおく値（`multi` は配列）。**なるべく入れる**（触らずに決定できる） |
| `allowOther` | `false` | 「その他」の自由入力を足す（`otherLabel`・`otherPlaceholder` で文言） |
| `showIf` | なし | `{"他の質問の id": 値 または 値の配列}`。その回答のときだけ表示する（複数書くと「かつ」） |
| `comment` | `true` | `false` で、この質問には自由記述を付けない |
| `required` | `false` | `multi`・`text` で空を許さない（`single` は常に必須） |
| `minWidth` | 自動 | 選択肢 1 枚の最小幅（px）。小さくすると 1 行に多く並ぶ |
| `preview` | 自動 | プレビューの置き方。`side`（選択肢の横の枠）/ `inline`（選択肢のカードの中）。既定はコードがあれば `side`、画像だけなら `inline` |
| `thumb` | `130` | `inline` の画像の高さ（px） |
| `filter` | 自動 | 絞り込みの欄。選択肢が 12 件以上なら自動で付く（`true` / `false` で指定もできる） |

選択肢: `value`（必須・回答に入る値）、`label`（表示名）、`desc`（説明）、`recommended`（「おすすめ」の札）、
`colors`（色の配列。配色の見本として帯で出す）、`group`（分類の見出し。同じ分類の選択肢を続けて並べる）、
`image`・`code`・`lang`（プレビュー。下）、`audio`（試聴。下）。

### 目次（質問が多いとき）

質問がウィンドウの高さ（既定 820px まで）に収まらないと、**何も書かなくても**、左に**質問の題の一覧（目次）**が出る。質問は 1 枚に並んだままで、ページには分かれない。
スクロールに合わせて、目次の「今見ている質問」に印が付く（いちばん下まで下げると最後の項目に付く。最後の画面に並ぶ短い質問にも、下げる途中で順に付く）。
質問が多くて目次が高さに収まらないときは、目次にも縦のスクロールバーが出て、印に合わせて目次も動く。目次の項目を押すか、`Alt+PageDown` `Alt+PageUp` で、次・前の質問へ移る。目次が出ると、ウィンドウの幅はその分だけ広がる。

```json
{ "title": "動画の指示", "questions": [
  {"id": "length", "label": "長さ", "page": "基本", "default": "3", "options": ["1", "3", "5"]},
  {"id": "voice", "label": "声", "default": "a", "options": ["a", "b"]},
  {"id": "theme", "label": "配色", "page": "見た目", "default": "daylight", "options": ["daylight", "paper"]},
  {"id": "music", "label": "曲", "page": "音", "default": "calm", "options": ["calm", "koto"]}
] }
```

- **まとまりの見出しを付ける**: 質問に `page`（まとまりの題）を書くと、その質問から次に別の `page` が出るまでが 1 つのまとまりになり、目次に見出しが入る。
  まとまりに意味があるとき（基本 → 見た目 → 音）に使う。`page` を 1 つでも書いたら、高さに収まっていても目次を出す（`"paging": false` のときは、`page` を書いていても出さない）。
- **必ず出す・出さない**: 定義に `"paging": true` と書くと、高さに収まっていても目次を出す。`"paging": false` なら出さない（質問が縦に並ぶだけ）。
  数（前の版の「1 ページの質問の数」）は `true` と同じに扱う。
- 「決定」（`Ctrl+Enter`）は**どこからでも**押せる（既定のままでよければ、下まで見ずに決定できる）。
  未回答の質問は目次の色が変わり、決定を押すとその質問へ移る。
- 入力欄で `Enter` を押すと、目次が出ているときは次の質問へ、最後の質問では決定する（目次が出ていない短いフォームでは決定する）。
- 表示条件（`showIf`）で出ていない質問は、目次にも出ない。質問の番号は、出ている質問に通しで付く。
- 幅の狭い画面（768px 未満）では、目次は出ない。

### プレビュー（画像・コード）

選択肢に `image` か `code` を書くと、その選択肢のプレビューが出る。

```json
{"id": "layout", "label": "画面の案", "default": "a", "options": [
  {"value": "a", "label": "案A サイドバー", "image": "mock/a.png", "recommended": true},
  {"value": "b", "label": "案B ヘッダーのみ", "image": "mock/b.png"}]},
{"id": "impl", "label": "実装の方針", "default": "stash", "options": [
  {"value": "regex", "label": "正規表現で置換", "lang": "python", "code": "s = re.sub(r\"…\", …)\n"},
  {"value": "stash", "label": "コードを退避してから処理", "lang": "diff", "code": "@@ -1,2 +1,3 @@\n-old\n+new\n"}]}
```

| 項目 | 内容 |
|---|---|
| `image` | 画像のファイル（png / jpg / gif / webp / avif / svg）。相対パスは定義のファイルの場所から、標準入力で渡したときは今の場所から解く。`https://…`・`data:image/…` も可。無いファイルは定義の誤り（終了コード 1） |
| `code` | 等幅でそのまま出す文字列（コード・設定・文字で描いた画面の案）。改行は `\n` |
| `lang` | プレビューの枠に出す種類の名前。`diff` のときは `+`・`-`・`@@` の行を色分けする（ほかは色を付けない） |

- **`side`**（コードがあるときの既定）: 選択肢を左に縦に並べ、右の枠に、触れている選択肢（無ければ選択中の選択肢）のプレビューを出す。
  ウィンドウの幅は自動で広くなる（1080）。
- **`inline`**（画像だけのときの既定）: カードの中にサムネイル（コードは高さを抑えた枠）を出す。見比べる画像が 3〜8 枚のときに向く。
- 画像は「拡大」かプレビューの画像を押すと大きく出る。`←` `→` で同じ質問の画像を移り、`Enter` でその選択肢を選ぶ。
- 画像は定義に書かれたファイルだけを受け口から配る（ほかのファイルは読めない）。
- **外部 URL（`https://…`）の画像は、窓でも `ask.py` が取りに行く**（ブラウザは取りに行かない。Sodashitsu の画面内と同じ）。取った画像は一時ファイルに保存し、ローカルのファイルと同じ受け口（`file/N`）から窓へ渡す。
  利用者のマシン（IP）は画像の取得先に見えない（見えるのは `ask.py` を動かしているマシン）。規則は Sodashitsu の `RemoteImageFetcher` と同じ: https の 443 だけ・解決した全アドレスが公開アドレスであること
  （ループバック・プライベート・リンクローカル・メタデータ宛・IPv4 射影の IPv6・`2130706433`／`0x7f000001`／`0177.0.0.1` のような数の表記は拒否）・接続は検査したアドレスに固定・リダイレクトは 3 回まで毎回検査し直す・
  10 秒・1 ファイル 8 MiB（合計 24 MiB・32 件）・Cookie などは付けない・プロキシの環境変数は使わない・Content-Type が画像で、先頭のバイトがそれと一致すること。標準ライブラリだけで動く（`remote_image.py`）。
  **取得できなかった画像は、画像なしで出す**（窓の上に「画像 N 件を取得できませんでした」の固定の行が出て、理由〔宛先は書かない〕は標準エラーに出る）。社内プロキシ越しにしか外へ出られない環境では取れない。
  外部 URL の `audio` は出さない（Sodashitsu と同じ。絶対パスか `data:` で渡す）。`data:` は今までどおりで、1 ファイル 8 MiB を超えると定義の誤り（`too_large`）。
- プレビューは判断の材料なので、**選択肢の違いが分かる最小限**にする（差分は要の数行、画面案は同じ大きさ・同じ倍率の画像）。

### 成果物を見せて確認してもらう（`view`・`--review`）

スキルが作った成果物（HTML の文書・差分の画面・設計のメモ）を**ウィンドウの左に見せ、右で判断を聞く**。確認して次へ進む流れ（工程の承認など）に使う。

```bash
python3 <skill_dir>/ask.py --review out/requirements.html notes.md --title "requirements の確認"
```

```json
{"status": "answered", "answers": {"decision": "revise", "comment": "2 章の表に、対象外の項目を足す"}}
```

- **`--review ファイル…`**: 定義を書かずに、成果物を見せて「承認 / 修正を依頼 / 中止」を聞く。答えは `decision`（`approve`・`revise`・`stop`）と、
  修正の依頼なら `comment`（直してほしい所。必須）、承認・中止なら `remark`（一言。任意。空なら空の文字列）。ファイルをいくつか渡すと、タブで切り替えられる。
- **自分の質問と一緒に見せる**: 定義に `"view"` を書く。1 つなら辞書かパス、いくつかなら配列。項目は `file`（ファイル）か `text`（その場の文字）と、任意の `title`（タブの名前）。

```json
{"title": "設計の確認", "view": [{"file": "out/design.html", "title": "設計"}, {"file": "tasks.md"}],
 "questions": [{"id": "ok", "label": "この設計で進めますか", "default": "yes", "options": [{"value": "yes", "label": "進める"}, {"value": "no", "label": "見直す"}]},
               {"id": "sections", "label": "節ごとの判断", "type": "table", "default": "ok", "options": ["ok", "要修正"], "rows": ["データの形", "画面", "テスト"]}]}
```

| 見せるもの | 出し方 |
|---|---|
| HTML（`.html`） | 隔離した枠（`sandbox="allow-scripts"` のみ）に、そのまま表示する。中のスクリプトも動く（md-to-doc の文書・diff-review-html の画面など、1 つのファイルで完結した HTML） |
| 画像（png・jpg・gif・webp・avif・svg） | そのまま表示する |
| Markdown（`.md`・`.markdown`。2 MB まで） | **整形して**表示する（見出し・表・コード・チェックリスト）。` ```mermaid ` のコードは図になる（描けない図は、コードのまま理由を添える）。本文の http(s) のリンクは新しいタブで開ける（図の中のリンクは開けない）。右上の「ソースを見る」で元の文字に切り替えられる。`{"file": …, "raw": true}` なら文字のまま |
| そのほか（テキスト・コード。UTF-8・2 MB まで） | **文字のまま**表示する |

- **待ち方**: 読んでもらう時間が要るので、**Bash を `run_in_background: true` で実行する**（前面の実行は 10 分で打ち切られる）。答えが返ると通知が来るので、そこで結果を読む。
  待つ時間の既定は 59 分（`--timeout` で変えられる）。ウィンドウは幅 1400・高さ 1000 までで開く。
- **出せないとき**（終了コード 3）: 成果物を見せる手段が `AskUserQuestion` には無い。成果物のファイルを利用者に渡してから（場所を伝える・送る）、判断を `AskUserQuestion` で聞く。
- Sodashitsu の pane の中では、成果物も `sodactl ask --features` で確かめて画面内に出す（使えないときだけこのマシンのウィンドウ。下の「Sodashitsu（soda）の pane の中で動いているとき」）。
- HTML が読む別のファイル（画像・CSS・スクリプトを相対パスで読むもの）は配らない。**1 つのファイルで完結した HTML** を渡す。
  Markdown の中の相対パスの画像も出ない（`https://…` の画像は出る）。
- Markdown と mermaid は、同梱のライブラリ（`vendor/` の marked・mermaid。どちらも MIT License）で描く。外へは取りに行かない。
  凝った体裁（テーマ・目次・図の動き）で見せたいときは、md-to-doc で HTML にしてから渡す。
- 成果物は、回答の受け口とは別の合言葉のアドレスから配り、枠は同じ origin として扱わない（枠の中のスクリプトから、回答・取り消しは送れない）。
  ただし、見せるのは自分のスキルが作ったものにする（外から取ってきた HTML をそのまま見せない）。
- **窓の枠の sandbox は、HTML・text・image の成果物では `sandbox="allow-scripts"` だけ**（iframe の属性・成果物の応答の `Content-Security-Policy: sandbox allow-scripts`）。`allow-popups`（スクリプトが動く枠で許すと、popup の URL に本文を載せて外へ出せる）と
  `allow-downloads` は付けない。このため、成果物の HTML の中のリンクを押して新しいウィンドウで開く・ファイルをダウンロードする、はできない。
  **Markdown の整形ページの枠だけ、リンクを新しいタブで開ける**: sandbox は `allow-scripts allow-popups allow-popups-to-escape-sandbox`（iframe の属性と、整形ページの応答の `Content-Security-Policy: sandbox …` の両方。`allow-same-origin`・`allow-top-navigation` 系は付けない）。
  考え方: Markdown の枠は、整形の結果から script・iframe・svg などを取り除くのでスクリプトが動かず、popup の URL に本文を載せて外へ出す害が成り立たない。ただし、これは取り除きの網羅に頼っており、過大には保証しない。
  開けるリンクは、**本文の `a` で `href` が小文字の `http://`・`https://` で始まり、空白・制御文字を含まないものだけ**。`target="_blank"`・`rel="noopener noreferrer"` を付ける。
  `javascript:`・`data:`・`vbscript:`・`file:`・相対・`//host`・大文字の `HTTP://`・前後の空白・制御文字・改行を含むもの・`xlink:href` が混ざるものは、リンクを外して文字のまま残す（行き先は `title`）。`#` で始まる同じ文書の中は今まで通り。
  **mermaid の図の中のリンク（`click … href`・ラベルの HTML）は開けない**（外したまま）。整形した結果と図の中から、meta・link・base・form・iframe・object・embed・svg・math・map・area・script・SMIL（`set`・`animate*`）を、
  文書に入れる前に（動かない入れ物の中で）取り除く（`<meta http-equiv=refresh>` 対策）。mermaid は `htmlLabels: false`・`securityLevel: 'strict'`。
  それでも、**枠自身が外のページへ移ること（HTML の成果物のスクリプトによる遷移）は止められない**。成果物は信頼できるもの（自分のスキルが作ったもの）だけにする。
  Sodashitsu の画面内のダイアログの Markdown の枠も、同じ仕様に揃えている（別の変更）。
- 確かめたこと・手動で確かめること: sandbox の文字列・ヘッダ（Markdown だけ popup 許可・HTML は `allow-scripts` のまま）・Markdown のリンクの扱い（https が開ける形で残る・`javascript:` 等が外れる）・危険な入力（meta refresh・SMIL・mermaid の `click`・ラベルの HTML）が除かれることは、画面なしの Chrome のテストで確かめる（`tests/`）。
  実際の窓（Edge）で、外部の `https://` の画像が出ること・取れない URL で固定の行が出ること・HTML の成果物のリンクが開かないこと・Markdown のリンクをクリックして新しいタブで開くこと（ポップアップブロッカーに止められないか）は、手元の Edge で目で確かめる（画面なしの Chrome では、クリックと実際のポップアップは未確認）。
- 質問の欄は幅が狭いので、目次は出さない（`paging` を書けば、それに従う）。質問は、判断に要るものだけにする（3〜4 問まで）。

### 選択肢が多いとき（絞り込み・分類・試聴）

```json
{"id": "song", "label": "曲", "default": "calm", "options": [
  {"value": "calm", "label": "calm", "desc": "静かなピアノ", "group": "落ち着いた", "audio": "preview/calm.wav"},
  {"value": "koto", "label": "koto", "desc": "琴と尺八", "group": "和風", "audio": "preview/koto.wav"}]}
```

- `group` を書くと分類の見出しが入る。**同じ分類の選択肢は続けて並べる**（並べた順に見出しを出す）。
- 選択肢が 12 件以上になると、絞り込みの欄が付く。名前・値・説明・分類のどれかに当たるものだけが残る（空白で区切ると「かつ」）。選択中の選択肢は隠れない。
- `audio` に音のファイル（wav / mp3 / ogg / m4a / aac / flac。URL も可）を書くと「▶ 試聴」が付く。鳴るのは 1 つだけで、別のものを押すと切り替わる。
  ファイルは `image` と同じく、定義に書かれたものだけを配る。数秒の短い音にする。

### 選ぶ以外の質問（`edit`・`rank`・`table`）

```json
{"id": "plan", "label": "進め方の案", "type": "edit", "text": "1. 定義を書く\n2. ask.py に渡す\n3. 結果を読む\n"},
{"id": "prio", "label": "優先順位", "type": "rank",
 "options": [{"value": "speed", "label": "速さ"}, {"value": "quality", "label": "品質"}, {"value": "cost", "label": "費用"}]},
{"id": "layouts", "label": "節ごとのレイアウト", "type": "table", "rowLabel": "節", "pickLabel": "レイアウト",
 "default": "plain", "options": ["plain", "cards", "timeline", "accordion", "tabs", "checklist"],
 "rows": [{"value": "導入手順", "desc": "番号付きの 5 工程", "default": "timeline"}, "補足"]}
```

| 型 | 画面 | 回答の値 | 項目 |
|---|---|---|---|
| `edit` | 文面が入った編集欄。「この案でよいか」を、選ぶ代わりに直して答えてもらう | 直した後の文字列。直されたら結果の `edited` に id が入る | `text`（最初の文面）・`rows`（行数）・`mono`（`false` で等幅にしない）・`required`（既定で空は不可。`false` で許す） |
| `rank` | ドラッグか `↑` `↓` で並べ替える一覧 | 並べた順の `value` の配列 | `options`・`default`（最初の順の配列。無ければ `options` の順） |
| `table` | 行ごとに 1 つ選ぶ表。選択肢が 5 つまでは並んだボタン、それより多ければ選択欄（`group` で分類） | `{行の value: 選んだ value}` | `rows`（行。文字列か `value`・`label`・`desc`・`default`）・`options`・`default`（行に `default` が無いときの値）・`rowLabel`・`pickLabel`（見出し） |

- `table` は、同じ選択肢から選ぶ質問が何行も続くとき（節ごとの割り当て・項目ごとの設定）に使う。質問を行の数だけ並べない。
  既定から変えた行には印が付く。
- `edit` は長い文面を読ませる所ではない。**直してほしい所だけ**（計画の手順・文案・割り当ての一覧）を入れる。
- `showIf` の条件にできるのは `single`・`multi` の質問だけ。

### 前回の回答を既定にする（`remember`）

定義に `"remember": "名前"` を書くと、回答を `~/.local/state/ask-form/remember/<名前>.json` に保存し、次に同じ名前で聞くとき、
**今回の定義でもそのまま選べる値だけ**を既定にする（質問には「前回の回答」の札が付き、「今回の既定に戻す」で定義の既定へ戻せる）。

- 持ち越すのは `single`・`multi`・`rank`・`table`。自由記述（`text`・`edit`）・補足・選択肢に無い自由入力は持ち越さない。
- 質問に `"remember": false` を書くと、その質問は持ち越さない（**毎回おすすめが変わる質問**はこうする）。
- 名前はスキルごと・用途ごとに分ける（例: `md-to-doc`）。同じ名前を別の質問の組で使い回さない。

### 定義を書くときの決まり

- **`showIf` で参照する質問は、参照する側より上に置く**（上から順に判定する）。
- おすすめは選択肢の先頭に置き、`recommended` と `default` の両方を付ける。
- 質問が 1 つだけ・`single`・`"note": false` のときは、**選んだ時点で決定して閉じる**（決定ボタンを押さなくてよい）。
  決定するのはクリック・タップ・`Space`・`Enter` で選んだときだけで、矢印キーで選択肢を移っただけでは決定しない。
- 定義の検査だけなら `python3 <skill_dir>/ask.py --check spec.json`。

## 出せないとき（`unavailable`）

次のときは終了コード 3 を返す（`reason` に理由）。**エラーではない**ので、同じ質問を `AskUserQuestion` に分けて聞く
（4 択を超える質問は、先に本文へ全件の一覧を出し、選択肢に無いものは「その他」に値を入力してもらう）。

- Chromium 系ブラウザ（Edge / Chrome / Brave / Chromium）が無い
- 画面の無い環境（devcontainer・SSH 越し・クラウドのセッション）
- `ASK_FORM=off` が設定されている
- **このマシンの操作（キーボード・マウス）が 300 秒以上無い** — 画面の前に人がいないとみて、ウィンドウを出さない
- **開いたウィンドウに 90 秒のあいだ操作が無い** — ウィンドウを閉じて戻る

後ろの 2 つは、スマホのアプリなど**別の端末から指示しているとき**のための仕組み。そのまま待つと、誰も見ていない画面に
ウィンドウが出て、時間切れまで進まなくなる。`AskUserQuestion` はどの端末にも出るので、そちらへ切り替える。

- 秒数は `--away-after`・`--react-within`（環境変数 `ASK_FORM_AWAY_SECONDS`・`ASK_FORM_REACT_SECONDS`）で変えられる。`0` で判定しない。
- 画面の前にいても、長い作業を触らずに見ていた後は 300 秒を超えることがある。そのときも `AskUserQuestion` に切り替わるだけで、質問は届く。
- 操作の無い時間は Windows（WSL を含む）・macOS・`xprintidle` のある Linux で分かる。分からない環境では、開いた後の 90 秒だけで判定する。

> [!IMPORTANT]
> ウィンドウは **`ask.py` が動いているマシンの画面**に開く。ブラウザ版ターミナルなどで、Claude Code が動く
> マシンとユーザーが見ている画面が別のとき（外からつないでいるとき）は、ユーザーの目に触れないウィンドウが
> サーバー側に開いてしまう。そういう環境では、シェルに `ASK_FORM=off` を設定しておく。

### Sodashitsu（soda）の pane の中で動いているとき

`SODA_PANE_ID` があり `sodactl` が PATH にあるときは、ウィンドウを開く前に `sodactl ask` へ渡し、**その pane を見ているブラウザの画面**に
フォームを出す（ブラウザが別のマシンでも届く。新しいウィンドウは開かない。`ASK_FORM=off` でも行う）。結果と終了コードは同じ。
目次（`page`・`paging`）は、Sodashitsu が部品（`ask-form.js`）の新しい版を取り込んでから効く。それより前の版では、ページに分かれるか、質問が上から順に 1 枚に並ぶ。

- 画像・音・コード・成果物（`view`。`--review` を含む）・`edit`・`rank`・`table` を使う定義は、先に `sodactl ask --features` を 1 回呼んで（5 秒で打ち切る）、
  `sodactl` とサーバがその機能（`types:*`・`media`・`remote-image`・`view`）を持つと確かめてから渡す。`single`・`multi`・`text` だけの定義は、確かめずに今までどおり渡す。
- **使えないときだけ**、今までどおりこのマシンのウィンドウへ進む（出せなければ `unavailable`）: 古い `sodactl`（`--features` を知らない）・`soda` が古い・サーバにつながらない・機能が足りない・
  つながっているブラウザが無い。画面内に出せるのに窓へ落ちることは無い。
- **ローカル起動では、大きさの上限は無い**: Sodashitsu の `soda serve` が loopback だけで待ち受け（`--origin`・TLS なし）、別のマシンの中継越しの画面が無いとき、`sodactl ask --features` の `limits.unlimited` が真になる。
  このとき `ask.py` は、ファイルの大きさ・合計の事前確認を `limits.safety`（安全弁。1 ファイル 256 MiB・合計 512 MiB）まで緩め、**8 MiB を超える HTML・2 MiB を超える Markdown も、窓へ落とさず画面内のダイアログに出す**
  （個数 32・`view` 8 件は変わらない。実測: 200 MiB の HTML も出る〔重いのでメモリの少ない端末では遅い〕）。外向きに公開した `soda`（`--origin`・TLS・LAN）・別のマシンの pane・古い `soda`／`sodactl`（`unlimited` を知らない）は従来の上限
  （1 ファイル 8 MiB・Markdown とテキストは 2 MiB・1 つの質問の合計 24 MiB）で、超えると下のとおり終了コード 1。窓（Edge）へ出す経路の上限は、どの場合も従来のまま（窓へ落ちるときは Markdown・テキストを 2 MiB まで）。
- **窓へ落とさず、終了コード 1 で理由を出す**もの: ファイルの大きさ・個数・合計が上限（1 ファイル 8 MiB・Markdown とテキストは 2 MiB・1 つの質問の合計 24 MiB・32 ファイル・`view` は 8 件。ローカル起動では大きさは安全弁）を超えるとき
  （`--features` の `limits` で事前に確かめる）と、`sodactl ask` が定義の誤り（`invalid ask spec: …`）としたとき。窓に落としても同じ定義なので、定義を直す。
- 画像・音・`view.file` の相対パス・`~/` は、`ask.py` が定義ファイルの場所（標準入力で渡したときは今の場所）から絶対パスにして渡す（`sodactl` は自分の cwd から解くため）。
- 画像の参照: pane が動くマシンのファイル（絶対パス・相対パス）・`data:`・外部の `https://`。**外部の `https://` の画像は、ブラウザではなく `soda` のサーバが取りに行く**
  （公開アドレスの 443 だけ・10 秒・8 MiB まで。社内プロキシ越しにしか外へ出られない環境では取れず、画像なしで出る。窓でも、`ask.py` が同じ規則で取りに行って窓へ渡す〔上の「プレビュー（画像・コード）」〕）。音は絶対パスか `data:` だけ（外部 URL は不可）。
- **成果物の HTML は、スクリプトは動くが外へは通信しない**（CDN・Google Fonts を読む HTML は崩れる）。ただし隔離の枠にも限界がある。枠自身が外のページへ移ることは止められず、
  枠の中のスクリプトは、質問側の入力欄（自由記述・`text`・`edit`）からフォーカスを奪って、その後に打った文字を読めてしまう（Sodashitsu の docs/sodactl.md「安全の境界」「枠の中のキー」）。
  **出す成果物は、信頼できるもの（自分のスキルが作ったもの）だけにする。外から取ってきた HTML は、自由記述・`text`・`edit` を含む質問と一緒に出さない。**
  Markdown の枠はスクリプトが動かず、リンクは新しいタブで開ける（http(s) のみ）。枠の中で Ctrl/Cmd+Enter を押しても確定せず、質問側の固定の行へフォーカスが移るだけ（もう一度押すと確定）。
- 外からつなぐ使い方では、ウィンドウがサーバー側に開かないよう `ASK_FORM=off` も設定しておく。
- 使わないようにするには `ASK_FORM_SODA=off`。

## ほかのスキルから使う

同じまとまり（`other/`）のスキルからは `<呼び出し側の skill_dir>/../ask-form/ask.py` で届く。別のまとまり（`video/` の motion-video・yukkuri-kaisetsu）は、
隣 → 1 つ上の階層の別のまとまり → `~/.claude/skills` の順に探す（各スキルの `find_skill`）。見つからなければ、ウィンドウを出せないときと同じ `unavailable`・終了コード 3 を返す。呼び出し側は
（1）質問の定義を作る（2）`ask.py` に渡す（3）終了コード 3 のときは `AskUserQuestion` に切り替える、の 3 つを書く。
md-to-doc は `generate.py --ask` がこの 3 つをまとめて行う（定義は `--ask-spec` で見られる）。

## 画面の部品（`ask-form.js`）と、Sodashitsu との同期

フォームの画面は、カスタム要素 `<ask-form>`（`ask-form.js`。依存なし・Shadow DOM）が描く。`form.html` は、それを置いて通信とウィンドウの操作だけを行う殻で、
`ask.py` が部品の JS を埋め込んで配る。同じ部品を Sodashitsu（`sodactl ask` の画面）が取り込むので、**画面の改修は `ask-form.js` に入れる**（殻には入れない）。

| ファイル | 役割 |
|---|---|
| `ask-form.js` | 部品。定義を描く・回答を集める・質問の目次を出す。通信しない・`window` や `document` に触らない |
| `form.html` | 単独ウィンドウの殻。配色を CSS 変数で渡す・受け口との通信・ウィンドウの大きさ合わせ・閉じる・質問の横に成果物を見せる（`view`） |
| `ask.py` | 定義の検査（`normalize()`）と受け口。検査を通った定義は、部品が受ける形（`fixtures/normalize.json` の「正規化後」）になっている |
| `viewer.html`・`vendor/` | Markdown を整形して見せるページと、それが読む同梱のライブラリ（marked・mermaid。配布元のファイルそのまま。版・出どころ・sha256 は `vendor/SOURCE.json`） |
| `fixtures/normalize.json`・`fixtures/collect.json` | 共通の試験データ。ここ（`tests/test_ask_form.py`）と Sodashitsu の両方のテストが読む |

- 部品との受け渡し: プロパティ `spec`・`busy`・`resolveMedia`、イベント `ask-submit`・`ask-cancel`・`ask-unsupported`、読み取りの `value`・`pageCount`・`contentHeight`、
  配色の CSS 変数 `--ask-bg` `--ask-fg` `--ask-border` `--ask-accent` `--ask-accent-fg` `--ask-error` `--ask-warn`（詳しくは `ask-form.js` の先頭）。
- **同期の単位は 3 つ**: 部品のファイル・通す項目の一覧（`AskFormElement.supports`）・共通の試験データ。Sodashitsu のサーバは知っている項目だけを通すので、
  **定義に新しい項目や型を足したら、試験データに例を足し、Sodashitsu 側にも知らせる**（部品を写すだけでは届かない）。
- 検査の誤りには分類の名前がある（`SpecError.reason`。一覧は `fixtures/normalize.json` の `reasons`）。文言は実装ごとに違ってよく、分類で比べる。
- 部品の決まり（定義の文字は文字として出す・通信しない・ページ全体に触らない など）は `tests/test_ask_form.py` が確かめる（`python3 -m unittest discover -s tests -t tests`。このスキルの場所から）。
  変えたら `cd .. && python3 -W ignore::ResourceWarning -m unittest discover -s tests -t tests -k ask_form`。

## 対応する環境と確認

| 環境 | 開き方 |
|---|---|
| Windows / WSL | Edge・Chrome・Brave（WSL からは Windows 側のブラウザを起動する） |
| macOS | Chrome・Edge・Brave・Chromium |
| Linux（画面あり） | google-chrome・microsoft-edge・chromium・brave-browser |

- 使うブラウザを固定するには `ASK_FORM_BROWSER=<実行ファイルのパス>`。
- `python3 <skill_dir>/ask.py --selftest` で、人の操作なしに「開く → 既定で回答 → 閉じる」を確かめられる
  （定義を渡せばその定義で試す）。
- 受け口は `127.0.0.1` の空きポートで、URL に毎回変わる合言葉を含む。回答を受け取るかウィンドウが閉じると終わる。
