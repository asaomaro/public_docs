---
name: aidev-util-batch
description: ［aidev ユーティリティ］aidev のバッチ駆動。.aidev/backlog の未処理項目を順に autonomous モードの aidev で処理し、1 つの PR にまとめる。「aidev batch」「aidev の backlog を消化して」と言われたとき、または /loop・/schedule から起動されたときに使用する。
allowed-tools: [Bash, Read, Edit, AskUserQuestion, Agent]
---

AI 開発ワークフローの **バッチ駆動（L1 オーケストレーター）**。
バックログの**未処理項目を1件ずつ autonomous モードの aidev で処理**し、反復する。
1反復＝「次の1件を選ぶ → autonomous で処理 → 完了マーク」。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` と `protocol-autonomous.md` を読むこと。**

## 位置づけ（重要）

- **パイプライン工程ではない**（番号なし。insights と同列のユーティリティ）。
- 各項目の実処理は **autonomous aidev（L0.5）に委譲**する。バッチ自身はドメインを知らない
  （「1件＝何か・どう作るか」は項目テキストと PJ資産＝PJ skill に委ねる）。
- 繰り返し起動は L2（`/loop` または `/schedule`）が担う。バッチ本体は「1回分」を確実に進める。

## 前提

- バックログ・ファイル（チェックリスト形式）が存在すること。パスは引数で受け取り、
  無指定なら PJ 既定（例 `.aidev/backlog/*.md`）を探す。

## 入力

- バックログ（markdown チェックリスト）。各 **未チェック行 = 1件のタスク**（autonomous aidev の requirement になる）。

```markdown
# <タイトル> バックログ
- [ ] <タスク1の指示（autonomous aidev に渡す内容）>
- [ ] <タスク2の指示>
- [x] <処理済み（PR: <url>）>
```

## backlog ファイル規約（複数前提）

backlog は1ファイルとは限らない（ドメイン別・タスク分割由来で複数になる）。各ファイル先頭に
自己記述ヘッダ（frontmatter）を置く:

```yaml
---
backlog: <識別名>              # 例 cl / rpg-spec / split-rpg-dialect
kind: standing | split | topic # ファイルの一生の宣言。「消化しきったら終わるか」で選ぶ
parent: <slug/ticket>          # split のときだけ: 親（work slug / チケット）
priority: <整数>               # 複数ファイルの選択順（小さいほど先）。未指定は最後
---
```

- **選択順**: 明示指定（`batch <file>`）が最優先。無指定は active な `.aidev/backlog/*.md` を
  `priority` → ファイル名 の順に走査する。
- **kind の選び方**（`aidev doctor` がこの3値で退避漏れを見る。未記載・誤記も WARN）:
  - **`standing`** = 定常ドメインキュー。そのドメインが続く限り**また積まれる**（例 `cl.md`）。
    **全消化でも退避しない**。
  - **`split`** = タスク分割由来の短命キュー（`split-<親>.md`）。`parent` を持つ。**消化後に退避**。
  - **`topic`** = 一件で完結するトピック（特定の調査・特定の設計変更）。`parent` を持たないが、
    **消化しきったら終わる**ので split と同じく**消化後に退避**。
    standing との違いは「またここに積むか」——積まないなら topic。
- **archive**: 消化しきったら終わるキュー（`split` / `topic`）で全項目が `[x]` になったファイルは
  `.aidev/backlog/archive/` に退避し、active の glob（`archive/` を除く）を小さく保つ。
  `standing` は全消化でも退避せず継続。`[x]` 行が溜まったら `aidev backlog compact` で
  `archive/<name>-done.md` へ移す（`verify` の消し込み検査はそこも見る）。
  - **退避は `aidev backlog archive` で行う**（引数なしで条件を満たすものだけ退避。判定は `doctor` の
    WARN と同じ関数を通る）。`mv` のみなので、**コミットは呼び出し側の仕事**
    （`git add -A .aidev/backlog` でリネームとして拾われる）。
- **新しい backlog ファイルは `aidev backlog new <name> --kind <k>` で起こす**。
  frontmatter を CLI が書くので `kind` の付け忘れが起きない。
- **依存**: 順序の正は生成する work の `state.yml` `dependsOn`（`protocol.md`「2.7」）。
  ただし**着手前から既知の前提**（ファイル跨ぎ・split 親・未整備の前提skill 等）は、項目行末の任意注記
  `(needs: <slug/#N>)` で表してよい。batch は `aidev new --depends` で作成時に `dependsOn` へ転記し、未充足なら保留＝次項目へ。

## 出力

- 各項目の autonomous 実行による成果物・コミット。
- バックログの該当行を `[x]` に更新し、PR/コミット参照を追記。
- バッチ実行サマリ（処理件数・スキップ・失敗）。

## 手順

1. バックログ・ファイルを解決して読む。未チェック `[ ]` 項目を列挙する。
2. **無ければ「完了（未処理なし）」と報告して終了**（停止条件）。
3. **1回の処理件数上限**を決める（既定 3、必要なら確認）。上限まで、未チェックの**先頭から**処理：
   - `aidev new <slug> --mode autonomous --backlog <いま消化しているバックログのファイル名> [--depends <(needs:…)の前提>]`
     で work を作成し、その項目テキストを **task** として autonomous で実行する
     （protocol「10.」。重い実処理はサブエージェントに委譲してよい）。
   - **`--backlog` は省略しない**。batch は手順 4 で自分が `[x]` にするので一見不要だが、
     **バッチが途中で切れると誰も刻んでおらず、後続セッションはその work が backlog 由来だと知る手段が無い**
     （`state.yml` に出自が無ければ deliver の `aidev verify` も素通りする）。刻印しておけば、
     別セッションで再開しても着地前に消し込みが強制される（`protocol.md`「2.9」）。
     刻印は `aidev status` の `inflight` 列にも出るので、**着手中の項目を別の入口が二重に選ばなくなる**。
   - 実処理は PJ資産（関連 skill）に委譲される（例: CL定義なら `cl-command-def`）。
   - **test を硬いゲートに**: 通らなければその項目は失敗として記録し、`[ ]` のまま残す。
     - **定義・データ生成系（原典のある成果物）では、test硬ゲートに「原典との機械diff」を含める**:
       生成物のキー集合・必須/型・定義済み値を**一次資料の生テキストと機械的に突き合わせ**、過不足・
       required 誤りを着地前に弾く（要約や知識ではなく原典直読で確定。主エージェントが実施＝protocol §2.6）。
4. 成功項目はバックログを `[x]` に更新し、コミット/PR 参照を追記。
5. **着地**: バッチ実行分を **1ブランチ・1PR にまとめる**（項目ごとに1コミット）。
   全件失敗なら PR を作らない／一部失敗は **draft PR** にして要点を報告。**auto-merge はしない**。
6. 残件・上限・失敗の状況を報告して終了。次回起動（/loop 等）で続きから消化される。

## 安全弁（必須）

- **1回の件数上限**（暴走防止）。**予算/時間上限**で停止・報告。
- **test 硬ゲート**・**PRで停止（auto-merge禁止）**・**人間が PR レビュー**。
- **独立な項目を選ぶ**（同一ファイルを争う項目は同時に処理しない）。
- **PJ規約（条項）とハーネス改修の記録に対してできるのは、追加・移送・判定案どおりの判定まで**
  （`protocol-conventions.md`）。既存条項の**削除・緩和は人間**の判断に残す。
  - **判定タスク**（項目に insights の判定案＝`--result`/`--note` 付きの `aidev convention confirm|retire` /
    `aidev harness confirm|retire` の行がそのままある）は autonomous で実行してよい。**項目に CLI 行が無ければ
    実行せず `[ ]` のまま残す**（batch が判定を発明しない）。結果は PR に載るので、人間が判定を見てから着地する。
  - 移送タスク（`confirmed` 条項の本文を PJ ドキュメントへ移す）は**通常のリポジトリ変更**なので
    autonomous で消化してよい。着地は `aidev convention promote <id> --to <path#anchor>`
    （移送先の実在を CLI が検査する）。詳細は `protocol-conventions.md`。
- **依存順を尊重する**: 項目に前提があれば、`aidev new --depends` で work の `dependsOn` に設定する。
  各 work の前提チェック（`protocol.md`「2.7」）が未充足依存を**保留**にするため、依存先が未完了の項目は
  自動的に飛ばされ、次回（依存先の完了後）に消化される。
- 重要判断・失敗理由は各作業の decisions に残す。

## 冪等性・再開

- 「未チェック行」を毎回**ファイルから導出**するため、中断しても次回は続きから（pop カーソルを別管理しない）。
- 出力が既に存在する項目はスキップ扱いにできる（PJ 側の判定に従う）。
