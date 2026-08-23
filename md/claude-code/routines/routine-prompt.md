# ルーチン登録用プロンプト

claude.ai/code/routines の **Instructions** 欄に貼るテキスト。
`{{宛先}}` を自分のメールアドレスに置き換えること。

> **注意**: このリポジトリは public。**メールアドレスをここに書かないこと。**
> 宛先はルーチンのプロンプト側（claude.ai アカウントに保存され、非公開）に書く。

## 設定値

| 項目 | 値 |
| :-- | :-- |
| Repositories | `asaomaro/public_docs` |
| Environment | `AI Digest` (`env_015TuMfJLi69QMZx2LUkaD4L`) — Custom / `allowed-domains.txt` を許可 |
| Connectors | **Gmail のみ**。他は全部外す |
| Trigger | Schedule / Daily / 07:00（ローカル時刻で指定。数分の stagger あり） |
| Model | 好みで。Sonnet で十分 |

## Instructions（以下をコピー）

```text
リポジトリの md/claude-code/routines/CLAUDE.md を最初に読み、そこに書かれた
収集ルール・採否基準・items.json スキーマに厳密に従うこと。

手順:

1. Gmail コネクタの search_threads で subject:"AI Daily Digest" in:sent を検索し、
   最新の 1 通を読む。そこに載っている URL と見出しは今回の対象から除外する。
   該当メールが無ければ除外なしで進む。

2. CLAUDE.md の「収集クエリ」を全部 WebSearch で実行する。採用候補の日付と事実は
   WebFetch で一次情報にあたって裏取りする。許可ドメインは allowed-domains.txt を
   参照。許可外は EGRESS_BLOCKED になるので深追いしない。

3. CLAUDE.md の採否基準で選別し、日本語で要約して /tmp/items.json を書く。
   スキーマは CLAUDE.md の定義に厳密に従うこと。

4. node md/claude-code/routines/build.mjs /tmp/items.json --out /tmp/digest
   を実行する。スキーマ違反で失敗したら /tmp/items.json を直して再実行する。
   HTML を自分で書いてはいけない。必ずこのスクリプトの出力を使う。

5. Gmail コネクタの send_message で送信する。パラメータの対応を厳守すること。
   to:       ["{{宛先}}"]
   subject:  build.mjs が出力した「件名:」の行の値をそのまま（接尾辞を付けない）
   htmlBody: /tmp/digest/out.html の中身をそのまま
   body:     /tmp/digest/out.txt の中身をそのまま

   HTML を body に入れてはいけない。エスケープされた生ソースが届いてしまう。
   HTML は必ず htmlBody、プレーンテキストは必ず body。

制約:
- リポジトリには何もコミットしない。push もしない。git 操作は一切不要。
- 送信は 1 通のみ。send_message は 1 回しか呼ばない。送信後に不備に気づいても
  再送しないで、何が問題だったかを報告して終了する。
- 採用できる記事が 1 件も無かった場合は、メールを送らずに
  「本日は配信対象なし」とだけ報告して終了する。
- build.mjs が成功していない状態でメールを送らない。
```

## 既知の落とし穴

- **`htmlBody` と `body` を取り違えない。** 初回実行では HTML を `body` に入れてしまい、
  エスケープされた生ソースが届いた。`body` は `htmlBody` 併用時のプレーンテキスト
  代替として扱われる。
- **WebFetch は許可ドメインでのみ使える。** 専用環境 `AI Digest`
  (`env_015TuMfJLi69QMZx2LUkaD4L`) の Network access を `Custom` にし、
  `allowed-domains.txt` のドメインを許可してある。許可外は `EGRESS_BLOCKED` で失敗する。
  WebSearch はサーバ側ツールなので許可リストの影響を受けない。
  ドメインを足すときは `allowed-domains.txt` と環境設定の両方を更新すること。
- **ルーチン ID**: `trig_01N4xVWJ1novQerHbTG1ZGDP`
  （https://claude.ai/code/routines/trig_01N4xVWJ1novQerHbTG1ZGDP）
