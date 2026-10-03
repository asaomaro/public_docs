---
name: ask-form
description: ユーザーに決めてもらうことが多いとき（質問が 5 つ以上、選択肢が 5 つ以上、前の回答で次の質問が変わる等）に、すべての質問を 1 つの単発ウィンドウにまとめて出し、回答を JSON で受け取る。選ぶ・複数選ぶ・書く・文面を直して返す・並べ替える・表で行ごとに選ぶ質問と、画像・コード・音のプレビュー、絞り込みを持つ。ウィンドウは自動で開き、決定すると自動で閉じてターミナルに戻る。AskUserQuestion の「1 問 4 択まで・1 回 4 問まで」に収まらない確認に使う。選んでもらう前に質問と選択肢をすべて書き出し、4 問・4 択に収まらなければこのスキルを使う（AskUserQuestion に収めるために選択肢を削ったりまとめたりしない）。ほかのスキルから部品として呼べる。「質問をまとめて聞いて」「フォームで聞いて」「選択肢を一覧で出して」と言われたとき、またはほかのスキルから案内されたときに使用する。
---

# ask-form — 質問をまとめて 1 つのウィンドウで聞く

`AskUserQuestion` は **1 問あたり選択肢 4 つまで・1 回 4 問まで**。それを超える確認は、
同梱の `ask.py`（Python3 / 標準ライブラリのみ）で 1 画面にまとめて聞く。

- タブではなく**単独のウィンドウ**が開く（Edge / Chrome の `--app` モード。画面の中央・中身に合う高さ）。
- すべての質問が 1 つのウィンドウに並ぶ。既定の回答は選択済みで出るので、変えたいところだけ触ればよい。
- 質問が多くてウィンドウの高さに収まらないときは、**自動でページに分かれる**（縦に長くならない。題を付けて分けることもできる）。
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
| 0 | `answered` | 回答あり。`answers` に従って進める。`note`（補足の欄）があれば必ず読んで反映する |
| 2 | `cancelled` | 回答せずに閉じた／キャンセルした。勝手に既定で進めず、どうするかをユーザーに聞く |
| 3 | `unavailable` | ウィンドウを出せない環境。**同じ質問を `AskUserQuestion` で聞き直す**（下の「出せないとき」） |
| 4 | `timeout` | 時間切れ。まだ必要かをユーザーに確かめてから、もう一度出す |
| 1 | — | 定義の誤り（標準エラーに理由）。直して再実行する |

- `answers` のキーは質問の `id`。`single` は文字列、`multi` は配列、`text` は文字列。
- `showIf` で隠れていた質問は `answers` に**入らない**（キーが無い＝聞いていない）。
- `custom` は「その他」に自由入力した質問の `id`。値が選択肢に無い文字列なので、解釈してから使う。

## 質問の定義

全体:

| キー | 既定 | 内容 |
|---|---|---|
| `title` | 「質問」 | ウィンドウの題 |
| `intro` | なし | 題の下の説明（何のための確認か） |
| `submit` | 「決定」 | 決定ボタンの文言 |
| `note` | `true` | 末尾の「補足」欄。`false` で出さない。文字列ならその欄の入力例 |
| `remember` | なし | 名前を書くと、前回の回答を次回の既定にする（下の「前回の回答を既定にする」） |
| `paging` | `"auto"` | ページの分け方。`"auto"`（高さに収まらないときだけ分ける）/ `false`（分けない）/ 数（1 ページの質問の数）。下の「ページ」 |
| `questions` | 必須 | 質問の配列（上から順に表示） |

質問:

| キー | 既定 | 内容 |
|---|---|---|
| `id` | 必須 | 回答のキー。呼び出し側の引数名と揃えると、そのまま渡せる |
| `label` | 必須 | 質問の見出し |
| `type` | `single` | `single`（1 つ選ぶ）/ `multi`（複数選ぶ）/ `text`（自由記述。`multiline` で複数行）/ `edit`（文面を直して返す）/ `rank`（並べ替える）/ `table`（表で行ごとに 1 つ選ぶ）。後ろの 3 つは下の「選ぶ以外の質問」 |
| `help` | なし | 見出しの下の補足 |
| `page` | なし | ページの題。書いた質問から新しいページが始まる（下の「ページ」） |
| `options` | — | 選択肢の配列。文字列（値＝表示名）か、下のオブジェクト。**数に上限は無い** |
| `default` | なし | 最初から選んでおく値（`multi` は配列）。**なるべく入れる**（触らずに決定できる） |
| `allowOther` | `false` | 「その他」の自由入力を足す（`otherLabel`・`otherPlaceholder` で文言） |
| `showIf` | なし | `{"他の質問の id": 値 または 値の配列}`。その回答のときだけ表示する（複数書くと「かつ」） |
| `required` | `false` | `multi`・`text` で空を許さない（`single` は常に必須） |
| `minWidth` | 自動 | 選択肢 1 枚の最小幅（px）。小さくすると 1 行に多く並ぶ |
| `preview` | 自動 | プレビューの置き方。`side`（選択肢の横の枠）/ `inline`（選択肢のカードの中）。既定はコードがあれば `side`、画像だけなら `inline` |
| `thumb` | `130` | `inline` の画像の高さ（px） |
| `filter` | 自動 | 絞り込みの欄。選択肢が 12 件以上なら自動で付く（`true` / `false` で指定もできる） |

選択肢: `value`（必須・回答に入る値）、`label`（表示名）、`desc`（説明）、`recommended`（「おすすめ」の札）、
`colors`（色の配列。配色の見本として帯で出す）、`group`（分類の見出し。同じ分類の選択肢を続けて並べる）、
`image`・`code`・`lang`（プレビュー。下）、`audio`（試聴。下）。

### ページ（質問が多いとき）

質問がウィンドウの高さ（既定 820px まで）に収まらないと、**何も書かなくても**、収まる分ずつのページに分かれる。
題の下にページの番号が並び、「次へ」「戻る」（`Alt+PageDown` `Alt+PageUp`）か番号を押して移る。ウィンドウの高さはいちばん高いページに合わせ、ページを移っても変わらない。

```json
{"title": "動画の指示", "questions": [
  {"id": "length", "label": "長さ", "page": "基本", "default": "3", "options": ["1", "3", "5"]},
  {"id": "cast", "label": "登場人物", "default": "zundamon", "options": ["zundamon", "metan"]},
  {"id": "theme", "label": "配色", "page": "見た目", "default": "daylight", "options": ["daylight", "paper"]},
  {"id": "music", "label": "曲", "page": "音", "default": "calm", "options": ["calm", "koto"]}
]}
```

- **題を付けて分ける**: 質問に `page`（ページの題）を書くと、その質問から新しいページが始まり、次に別の `page` が出るまでが 1 ページになる。
  まとまりに意味があるとき（基本 → 見た目 → 音）に使う。`page` を 1 つでも書いたら、高さでの自動の分割はしない。
- **数で分ける**: 定義に `"paging": 5` と書くと、質問 5 つごとに分ける。**分けない**（縦に長いまま出す）なら `"paging": false`。
- 「決定」（`Ctrl+Enter`）は**どのページからでも**押せる（既定のままでよければ、先のページを見ずに決定できる）。途中のページでは「次へ」が主のボタンになる。
  未回答の質問があるページは番号の色が変わり、決定を押すとそのページへ移る。
- 入力欄で `Enter` を押すと、途中のページでは次のページへ、最後のページでは決定する。
- `showIf` はページをまたいで効く。表示条件で質問が 1 つも出ていないページは、番号ごと隠れて飛ばされる。質問の番号は、ページをまたいで通しで付く。
- 補足の欄は最後のページに出る。説明（`intro`）は最初のページにだけ出る。
- 回答（`answers`）の形は、分けても分けなくても同じ。

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
- プレビューは判断の材料なので、**選択肢の違いが分かる最小限**にする（差分は要の数行、画面案は同じ大きさ・同じ倍率の画像）。

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
ページ分け（`page`・`paging`）はこの出し方には効かない（Sodashitsu 側の画面が、質問を上から順に並べる）。

- 次のときは `sodactl ask` を使わず、今までどおりこのマシンのウィンドウへ進む（出せなければ `unavailable`）:
  つながっているブラウザが無い／`edit`・`rank`・`table` の質問がある／選択肢に `image`・`audio`・`code` がある／`sodactl` が古い・サーバのエラー。
- 外からつなぐ使い方では、ウィンドウがサーバー側に開かないよう `ASK_FORM=off` も設定しておく。
- 使わないようにするには `ASK_FORM_SODA=off`。

## ほかのスキルから使う

スキルは同じ階層に並ぶので、`<呼び出し側の skill_dir>/../ask-form/ask.py` で届く。呼び出し側は
（1）質問の定義を作る（2）`ask.py` に渡す（3）終了コード 3 のときは `AskUserQuestion` に切り替える、の 3 つを書く。
md-to-doc は `generate.py --ask` がこの 3 つをまとめて行う（定義は `--ask-spec` で見られる）。

## 画面の部品（`ask-form.js`）と、Sodashitsu との同期

フォームの画面は、カスタム要素 `<ask-form>`（`ask-form.js`。依存なし・Shadow DOM）が描く。`form.html` は、それを置いて通信とウィンドウの操作だけを行う殻で、
`ask.py` が部品の JS を埋め込んで配る。同じ部品を Sodashitsu（`sodactl ask` の画面）が取り込むので、**画面の改修は `ask-form.js` に入れる**（殻には入れない）。

| ファイル | 役割 |
|---|---|
| `ask-form.js` | 部品。定義を描く・回答を集める・ページを分ける。通信しない・`window` や `document` に触らない |
| `form.html` | 単独ウィンドウの殻。配色を CSS 変数で渡す・受け口との通信・ウィンドウの大きさ合わせ・閉じる |
| `ask.py` | 定義の検査（`normalize()`）と受け口。検査を通った定義は、部品が受ける形（`fixtures/normalize.json` の「正規化後」）になっている |
| `fixtures/normalize.json`・`fixtures/collect.json` | 共通の試験データ。ここ（`../tests/test_ask_form.py`）と Sodashitsu の両方のテストが読む |

- 部品との受け渡し: プロパティ `spec`・`busy`・`resolveMedia`、イベント `ask-submit`・`ask-cancel`・`ask-unsupported`、読み取りの `value`・`pageCount`・`contentHeight`、
  配色の CSS 変数 `--ask-bg` `--ask-fg` `--ask-border` `--ask-accent` `--ask-accent-fg` `--ask-error` `--ask-warn`（詳しくは `ask-form.js` の先頭）。
- **同期の単位は 3 つ**: 部品のファイル・通す項目の一覧（`AskFormElement.supports`）・共通の試験データ。Sodashitsu のサーバは知っている項目だけを通すので、
  **定義に新しい項目や型を足したら、試験データに例を足し、Sodashitsu 側にも知らせる**（部品を写すだけでは届かない）。
- 検査の誤りには分類の名前がある（`SpecError.reason`。一覧は `fixtures/normalize.json` の `reasons`）。文言は実装ごとに違ってよく、分類で比べる。
- 部品の決まり（定義の文字は文字として出す・通信しない・ページ全体に触らない など）は `../tests/test_ask_form.py` が確かめる。
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
