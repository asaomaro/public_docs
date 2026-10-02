---
name: ask-form
description: ユーザーに決めてもらうことが多いとき（質問が 5 つ以上、選択肢が 5 つ以上、前の回答で次の質問が変わる等）に、すべての質問を 1 つの単発ウィンドウにまとめて出し、回答を JSON で受け取る。ウィンドウは自動で開き、決定すると自動で閉じてターミナルに戻る。AskUserQuestion の「1 問 4 択まで・1 回 4 問まで」に収まらない確認に使う。選んでもらう前に質問と選択肢をすべて書き出し、4 問・4 択に収まらなければこのスキルを使う（AskUserQuestion に収めるために選択肢を削ったりまとめたりしない）。ほかのスキルから部品として呼べる。「質問をまとめて聞いて」「フォームで聞いて」「選択肢を一覧で出して」と言われたとき、またはほかのスキルから案内されたときに使用する。
---

# ask-form — 質問をまとめて 1 つのウィンドウで聞く

`AskUserQuestion` は **1 問あたり選択肢 4 つまで・1 回 4 問まで**。それを超える確認は、
同梱の `ask.py`（Python3 / 標準ライブラリのみ）で 1 画面にまとめて聞く。

- タブではなく**単独のウィンドウ**が開く（Edge / Chrome の `--app` モード。画面の中央・中身に合う高さ）。
- すべての質問が 1 画面に並ぶ。既定の回答は選択済みで出るので、変えたいところだけ触ればよい。
- 「決定」（`Ctrl+Enter`）でウィンドウが閉じ、フォーカスがターミナルに戻る。`Esc` でキャンセル。
- 前の回答で出し分ける質問（`showIf`）、自由入力（`allowOther`）、複数選択、補足の欄を持つ。

## どちらで聞くかの決め方

`AskUserQuestion` を前提に考えると、枠に合わせて選択肢を削ってしまい、削ったことはユーザーから見えない。
そこで、**道具を選ぶ前に数える**。

1. 聞きたい質問と選択肢を**すべて書き出す**（この時点では上限を考えない）。
2. **4 問以内・どの質問も 4 択以内**に収まれば `AskUserQuestion`。収まらなければ ask-form。
3. `AskUserQuestion` に収めるために、選択肢を削る・まとめる・黙って「その他」に回す、をしない。

- コードや画面案を見比べて選ぶ質問（選択肢ごとのプレビューが要るもの）は `AskUserQuestion` を使う（ask-form にプレビューは無い）。
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
| `questions` | 必須 | 質問の配列（上から順に表示） |

質問:

| キー | 既定 | 内容 |
|---|---|---|
| `id` | 必須 | 回答のキー。呼び出し側の引数名と揃えると、そのまま渡せる |
| `label` | 必須 | 質問の見出し |
| `type` | `single` | `single`（1 つ選ぶ）/ `multi`（複数選ぶ）/ `text`（自由記述。`multiline` で複数行） |
| `help` | なし | 見出しの下の補足 |
| `options` | — | 選択肢の配列。文字列（値＝表示名）か、下のオブジェクト。**数に上限は無い** |
| `default` | なし | 最初から選んでおく値（`multi` は配列）。**なるべく入れる**（触らずに決定できる） |
| `allowOther` | `false` | 「その他」の自由入力を足す（`otherLabel`・`otherPlaceholder` で文言） |
| `showIf` | なし | `{"他の質問の id": 値 または 値の配列}`。その回答のときだけ表示する（複数書くと「かつ」） |
| `required` | `false` | `multi`・`text` で空を許さない（`single` は常に必須） |
| `minWidth` | 自動 | 選択肢 1 枚の最小幅（px）。小さくすると 1 行に多く並ぶ |

選択肢: `value`（必須・回答に入る値）、`label`（表示名）、`desc`（説明）、`recommended`（「おすすめ」の札）、
`colors`（色の配列。配色の見本として帯で出す）。

### 定義を書くときの決まり

- **`showIf` で参照する質問は、参照する側より上に置く**（上から順に判定する）。
- おすすめは選択肢の先頭に置き、`recommended` と `default` の両方を付ける。
- 質問が 1 つだけ・`single`・`"note": false` のときは、**選んだ時点で決定して閉じる**（決定ボタンを押さなくてよい）。
- 定義の検査だけなら `python3 <skill_dir>/ask.py --check spec.json`。

## 出せないとき（`unavailable`）

次のときはウィンドウを出さずに終了コード 3 を返す。**エラーではない**ので、同じ質問を `AskUserQuestion` に分けて聞く
（4 択を超える質問は、先に本文へ全件の一覧を出し、選択肢に無いものは「その他」に値を入力してもらう）。

- Chromium 系ブラウザ（Edge / Chrome / Brave / Chromium）が無い
- 画面の無い環境（devcontainer・SSH 越し・クラウドのセッション）
- `ASK_FORM=off` が設定されている

> [!IMPORTANT]
> ウィンドウは **`ask.py` が動いているマシンの画面**に開く。ブラウザ版ターミナルなどで、Claude Code が動く
> マシンとユーザーが見ている画面が別のとき（外からつないでいるとき）は、ユーザーの目に触れないウィンドウが
> サーバー側に開いてしまう。そういう環境では、シェルに `ASK_FORM=off` を設定しておく。

## ほかのスキルから使う

スキルは同じ階層に並ぶので、`<呼び出し側の skill_dir>/../ask-form/ask.py` で届く。呼び出し側は
（1）質問の定義を作る（2）`ask.py` に渡す（3）終了コード 3 のときは `AskUserQuestion` に切り替える、の 3 つを書く。
md-to-doc は `generate.py --ask` がこの 3 つをまとめて行う（定義は `--ask-spec` で見られる）。

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
