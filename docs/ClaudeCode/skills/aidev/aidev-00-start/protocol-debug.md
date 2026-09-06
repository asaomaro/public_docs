# 詰まりの原因究明（デバッグ委譲）（`protocol.md`「10.」の詳細）

> **読む条件**: 同一工程の差し戻しが `maxSendBacks` に達したとき／`aidev event <工程> sent_back` が
> `aidev debug start` を促したとき／タスク点検が `maxTaskCheckRounds` を超えても直らないとき
> 核となる規約と要約は `protocol.md`「10.」。ここはその詳細（工程ごとの読み込み量を抑えるため切り出し）。

同じ失敗を繰り返しているときに、**まっさらなコンテキストへ原因究明だけを委譲する**手順。
`protocol.md`「3.3」の独立点検が「**ゲートでの**別コンテキスト」なのに対し、こちらは
「**詰まったときの**別コンテキスト」。観点も出力も違うので、同じものとして扱わない。

## なぜ履歴を渡さないのか（この手順の要）

**失敗した試行の履歴を渡さない**。エラーの情報だけを渡す。
履歴を渡すと、新しいコンテキストは「これまでに試したこと」の延長線上で考え、
**同じ穴を掘り続ける**（試した手を避けるだけで、前提そのものを疑わなくなる）。
上限を設けてもこれは解決しない——上限は回数を止めるだけで、**方向は変えない**。

## 発火条件

次のいずれか。**全部の差し戻しでやるものではない**（点検と同じでコストがかかる）。

- 同一工程の差し戻しが **`maxSendBacks`**（`state.yml`。既定 3）に達した
  → `aidev event <工程> sent_back` がその場で促す。
- タスク点検の「点検 → 修正」が **`maxTaskCheckRounds`**（既定 2）を超えても直らない（`protocol-check.md`）。
- 原因が分からないまま実装を変えている自覚があるとき（自己申告でよい。上限を待たなくてよい）。

## 手順

1. **`aidev debug start [--phase <工程>]`** を打つ。ラウンド上限（`maxDebugRounds`。既定 2）を検査し、
   渡すもの／渡さないものを出力する。上限を超えていれば exit 4 で止まる。
2. **新しいコンテキスト**（サブエージェント。無ければ新しいセッション）へ、次だけを渡す。
   - 失敗の**生出力**（`test-result.md` の「失敗の証跡」）
   - いまの差分（`git diff`。コミット前の変更）
   - 対象タスクの行（`tasks.md`）と、その `AC` の本文（`requirements.md`）
   - review の直近ラウンドの指摘（`review.md`）
   - **渡さない: これまでの修正の試行履歴**
3. 委譲先は**原因究明だけを行う**（修正はしない）。守ること:
   - **根拠の明示**（`file:line` / エラーメッセージの該当行）。推測は推測と書く。
   - **一次資料との照合は行わない**（「2.6」。外部ドキュメントの参照が要ると判断したら、
     それ自体を報告に書いて主エージェントに戻す）。
   - **分類まで落とす**（下記 `--category`）。「よく分からないが直してみる」で終えない。
4. **`aidev debug report`** で結果を記録する。`--root-cause` / `--category` / `--next-action` は必須。
   本文（根本原因・修正方針・確認方法）は `decisions.md` に、列挙値は `metrics.yml` に入る。

   ```
   aidev debug report --phase coding \
     --root-cause "save() が temp 書き込み中の例外を握りつぶしていた" \
     --category logic --next-action retry --confidence high \
     --fix-tasks "os.replace の前に例外を再送出する" \
     --verification "python3 -m unittest tests.test_storage"
   ```

5. `--next-action` に従う。

| 値 | 意味 | 次にすること |
|---|---|---|
| `retry` | リポジトリ内の修正で直る | **新しい実装コンテキスト**に `--fix-tasks` を渡してやり直す（**同じコンテキストに戻さない**）。再開時は `aidev event <工程> start` を記録する |
| `block` | このタスクは止める | `decisions.md` の記録を残して次のタスクへ。判断は review 工程に委ねる |
| `stop_for_human` | リポジトリの外の判断・アクセスが要る | **ここで停止して人に返す**。`autonomous` でも待つ |

## 分類（`--category`）

**「リポジトリ内の編集で直るか」を判定するための語彙**。迷ったら `logic` ではなく実際に近い方を選ぶ。

| 値 | 例 |
|---|---|
| `dependency` | 必要なパッケージが入っていない／版が合っていない |
| `environment` | 実行環境・ランタイムの不一致（別のランタイムでは動く） |
| `config` | エントリポイント・ビルド設定・実行フラグの不足 |
| `logic` | 実装そのもののバグ |
| `upstream_conflict` | 要件・仕様が技術的に成立しない（上流へ戻す必要がある） |
| `test_defect` | テスト側の誤り（実装は正しい） |
| `external` | リポジトリ外の判断・アクセス・ハードウェアが要る |

`upstream_conflict` と `external` は **`retry` にしない**——前者は上流の差し戻し、後者は人の判断が要る。

## 上限（ループは必ず有限にする）

- **`maxDebugRounds`**（`.aidev/config.yml`。既定 2）。超えたら `aidev debug start` が止める。
- 2 ラウンド粘っても直らないなら、それは**この場で解けない問題**。`block` か `stop_for_human` で締める。
  `maxSendBacks` / `maxTaskCheckRounds` と同じ思想で、**上限を延ばして粘らない**。

## 記録と検査

- `metrics.yml`: `{ phase: <工程>, event: debug, metrics: { stage: start|report, round: N,
  category: …, next_action: …, confidence: … } }`
- `decisions.md`: 「デバッグ D&lt;n&gt;」の節（根本原因・修正方針・確認方法・確度・次の行動）。
- `aidev debug status`: 工程ごとの差し戻し数・デバッグ回数・要否（`due`）。
- `aidev verify`（schema 8）:
  - 差し戻しが上限に達しているのに原因究明の記録が無い → **WARN**（挟むかは人の判断）。
  - `stop_for_human` のまま deliver 承認済 → **FAIL**（人の判断を待つ出口を素通りしている）。
