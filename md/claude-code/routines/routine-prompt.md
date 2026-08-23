# ルーチン登録用プロンプト

claude.ai/code/routines の **Instructions** 欄に貼るテキスト。
`{{宛先}}` を自分のメールアドレスに置き換えること。

> **注意**: このリポジトリは public。**メールアドレスをここに書かないこと。**
> 宛先はルーチンのプロンプト側（claude.ai アカウントに保存され、非公開）に書く。

## 設定値

| 項目 | 値 |
| :-- | :-- |
| Repositories | `asaomaro/public_docs` |
| Environment | `Default`（Trusted のままでよい。WebSearch はサンドボックスのネットワークを通らない） |
| Connectors | **Gmail のみ**。他は全部外す |
| Trigger | Schedule / Daily / 07:00（ローカル時刻で指定。数分の stagger あり） |
| Model | 好みで。Sonnet で十分 |

## Instructions（以下をコピー）

```text
リポジトリの md/claude-code/routines/CLAUDE.md を最初に読み、そこに書かれた
収集ルール・採否基準・items.json スキーマに厳密に従うこと。

手順:

1. Gmail コネクタで、自分が過去に送った件名 "AI Daily Digest" のメールのうち
   最新の 1 通を検索して読む。そこに載っている URL と見出しは今回の対象から除外する。
   該当メールが無ければ除外なしで進む。

2. CLAUDE.md の「収集クエリ」を全部 WebSearch で実行する。

3. CLAUDE.md の採否基準で選別し、日本語で要約して /tmp/items.json を書く。
   スキーマは CLAUDE.md の定義に厳密に従うこと。

4. node md/claude-code/routines/build.mjs /tmp/items.json --out /tmp/digest
   を実行する。スキーマ違反で失敗したら /tmp/items.json を直して再実行する。
   HTML を自分で書いてはいけない。必ずこのスクリプトの出力を使う。

5. Gmail コネクタで送信する。
   宛先: {{宛先}}
   件名: build.mjs が出力した「件名:」の行をそのまま使う
   HTML 本文: /tmp/digest/out.html の中身をそのまま
   プレーンテキスト: /tmp/digest/out.txt の中身をそのまま

制約:
- リポジトリには何もコミットしない。push もしない。git 操作は一切不要。
- 採用できる記事が 1 件も無かった場合は、メールを送らずに
  「本日は配信対象なし」とだけ報告して終了する。
- build.mjs が成功していない状態でメールを送らない。
```
