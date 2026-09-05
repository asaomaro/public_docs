# AI 日次ダイジェスト — 収集・生成ルール

このディレクトリは、Claude Code の**ルーチン**（クラウド定期実行）が毎日 1 回、
AI 関連情報を WebSearch で収集し、HTML メールとして配信するための資材置き場。

ルーチンから使われるときは、リポジトリのルートが作業ディレクトリになる。
以下のパスはすべてリポジトリルートからの相対パス。

## 実行手順（ルーチンはこの順で動く）

1. **収集** — WebSearch で下記のクエリ群を実行し、記事を集める
2. **選別・要約** — 採否基準に従って絞り、日本語で要約する
3. **`/tmp/items.json` を書く** — 下記スキーマに厳密に従う
4. **ビルド** — `node docs/ClaudeCode/routines/ai-news-delivery/build.mjs /tmp/items.json --out /tmp/digest`
   （`/tmp/digest/htmlBody.html` と `/tmp/digest/body.txt` が出る）
5. **送信** — Gmail コネクタの `send_message` で送る。パラメータ対応は下記「送信」節を厳守
6. **検証** — 送ったメールを読み直し、HTML が生ソースで届いていないか確かめる

リポジトリには**何もコミットしない・push しない**。成果物は `/tmp` に置くだけ。

## 収集クエリ

毎回すべて実行する。英語クエリを主軸にし、日本語は補助。

- `Anthropic Claude announcement this week`
- `OpenAI announcement this week`
- `Google DeepMind Gemini announcement this week`
- `open source LLM release this week`
- `AI research paper breakthrough this week`
- `AI regulation policy news this week`
- `AI funding round startup this week`
- `AI 最新ニュース 今週`

### 一次情報の裏取り

このルーチンは専用環境 `AI Digest`（Network access: Custom）で動く。ラボ公式・論文・
規制当局・主要ニュースのドメインが許可済みなので、**採用候補の日付と事実は WebFetch で
一次情報にあたって裏取りする**。許可ドメインの一覧は `allowed-domains.txt` を参照。

許可外のドメインは `EGRESS_BLOCKED` で失敗する。その場合は深追いせず、WebSearch の
結果だけで判断できる範囲に留めるか、その記事を落とす。WebSearch 自体はサンドボックスの
ネットワークを通らないので、許可リストの影響を受けない。

## 採否基準

**採用する**
- 公開から 48 時間以内（`published` が不明なら本文中の日付で判断）
- 一次情報に近いもの（公式ブログ、論文、リリースノート、規制当局の発表）
- 実務に影響しうるもの（モデルの能力・価格・提供条件の変化、ライセンス変更、規制）

**落とす**
- 一次情報のない伝聞・転載記事、まとめサイト、アフィリエイト
- 「AI が世界を変える」式の論評だけで新事実がないもの
- 同一ニュースの重複（最も一次情報に近い 1 本だけ残す）
- 前回配信で既に取り上げたもの（次節）

## 重複排除

状態ファイルは持たない。代わりに **Gmail コネクタで自分が直近に送った
ダイジェストメールを 1 通読み**、そこに載っている URL / 見出しは除外する。
初回実行時は該当メールがないので、除外なしで進める。

## items.json スキーマ

```jsonc
{
  "date": "2026-08-23",              // 必須 YYYY-MM-DD（配信日、JST）
  "summary": "…",                    // 必須 今日の総括 1〜2 文
  "sections": [                       // 必須 空セクションは書かない
    {
      "title": "モデル・リリース",    // 必須
      "items": [
        {
          "title": "…",              // 必須 日本語の見出し（全角 40 字以内）
          "url": "https://…",        // 必須 http/https のみ
          "source": "Anthropic",     // 必須 発信元の名前
          "published": "2026-08-22",  // 任意 YYYY-MM-DD
          "summary": "…",            // 必須 日本語 2〜3 文
          "why": "…"                 // 任意 なぜ重要か 1 文
        }
      ]
    }
  ]
}
```

セクションの `title` は原則この 5 つから選ぶ（該当なしなら省く）。

1. モデル・リリース
2. 研究・論文
3. プロダクト・ツール
4. 業界・資金調達
5. 規制・ポリシー

1 セクションあたり最大 5 件、全体で最大 15 件。多すぎる場合は重要度で切る。

## 送信

Gmail コネクタの `send_message` のパラメータ対応を厳守する。
**`build.mjs` の出力ファイル名が、そのまま渡すべきパラメータ名になっている。**

| パラメータ | 渡すもの |
| :-- | :-- |
| `to` | `["<宛先>"]`（宛先はルーチンのプロンプト側に書く。このファイルに書かない） |
| `subject` | `build.mjs` が出力した「件名:」の行の値をそのまま。接尾辞を付けない |
| `htmlBody` | `/tmp/digest/htmlBody.html` の中身をそのまま |
| `body` | `/tmp/digest/body.txt` の中身をそのまま |

**HTML を `body` に入れてはいけない。** `body` は `htmlBody` 併用時のプレーンテキスト
代替として扱われるため、HTML を入れるとエスケープされた生ソースがそのまま届く。
`htmlBody` を省いて `body` だけで送った場合も同じ結果になる。
どちらも実際に起きた事故なので、ファイル名とパラメータ名を突き合わせて確認すること。

`htmlBody` はテンプレート込みで 12〜20KB になる（md-to-doc 風の部品を持つため）。要約したり省略したりせず、
`htmlBody.html` の中身を 1 バイトも変えずに渡す。

送信は 1 通のみ。`send_message` は 1 回しか呼ばない。送信後に不備に気づいても
再送せず、何が問題だったかを報告して終了する。

### 送信後の自己検証（必須）

`send_message` が返した `id` を `get_message`（`messageFormat: PLAIN_TEXT`）で読み直す。

- 本文が `AI Daily Digest — ` で始まっていれば成功
- 本文が `<!doctype` や `<html` で始まっていたら **HTML を `body` に入れた失敗**

失敗していても再送はしない。何をどのパラメータに渡したかを添えて報告し、終了する。

## 体裁について

**HTML を自分で書かないこと。** `build.mjs` がテンプレートに流し込む。
体裁を変えたいときは `template.html` を直す。
`build.mjs` はスキーマ違反を検出したら異常終了するので、
エラーが出たら `items.json` を直して再実行する。
