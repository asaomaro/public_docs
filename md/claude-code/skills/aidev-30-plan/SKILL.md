---
name: aidev-30-plan
description: ［標準工程・末尾0／主トリガ:両方（直接起動 or 前工程からの遷移／autonomous 自動）］AI開発ワークフローの plan（計画/作業分解）工程。spec.md から plan.md と tasks.md を作る。「計画を立てたい」「作業分解」「plan工程」などと言われたとき、または前工程から案内されたときに使用する。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion]
---

AI 開発ワークフローの **plan（計画 / 作業分解）工程**を実行する。
spec を実装可能な作業単位に分解し、`plan.md`（方針・順序）と `tasks.md`（チェックリスト）を作る。
`tasks.md` のチェックボックスが、以降の進捗の単一の真実となる。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 前提

- `spec.md` が存在すること。無ければ実行を中止し、spec 工程を促す。
- `design.md` があれば**それも前提に含める**（protocol.md「7.」: plan の前提は「spec.md（design があればそれも）」）。
  design 工程を挟んだ場合、その構造設計を踏まえて分解する。

## 入力

- 対象フォルダの `spec.md` と、あれば `design.md`（必要に応じて `requirement.md`）。

## 出力

対象フォルダに `plan.md` と `tasks.md` を生成する。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定。「2. 前提チェック」に従い `spec.md` を確認
   （`design.md` があればそれも読み込む）。
   - **この work が subtask か親かを見分ける**（state.yml に `parent` があれば subtask）。
     **subtask の plan は split 判定（手順3）と subtask 生成（手順4）を行わない**。手順5の「scope 凍結の
     tasks.md 分解」だけを実施し、**再分割（subtask の下に subtask を作る）は禁止**（CLI も多段ネストを弾く）。
     scope は親 plan が確定済み——子 plan は自分の slice の分解と兄弟 subtask への dependsOn 順序付けに限定する。
2. `spec.md`（と `design.md` があればその構造設計）を読み、実装手順・依存関係・リスクを整理して `plan.md` を書く。
3. **（親 work のみ）split 判定（subtask 分割の要否）**: `aidev-docs/DESIGN.md`「5.」の3層決定木に従い、この work を
   subtask へ割るか判断する。判定の discriminator は単一原則 **「そのピースは単独で検証・デリバリ可能か」**。
   - **単独で検証・デリバリ可能（低結合）** → そもそも別 work/PR の候補（本 work では割らず、必要なら
     `aidev-util-propose` で別 work 化を提案）。**振る舞い不変な変更（refactor 等）はここ**＝subtask に落とさない。
   - **相互依存で共同検証のみ可（高結合）かつ大規模で漸進レビューの価値がある** → **subtask 分割**（下記4へ）。
   - **不可分** → 分割せず単一 tasks.md ＋ walkthrough のコミット構成（通常の plan。5へ）。
   - **判定の提示**: interactive は `AskUserQuestion` で分割可否・分割案をユーザーに委譲する。
     autonomous は自律判定する（明確に独立な seam がある時だけ分割。迷えば分けない）。
     小〜中規模で 1 PR に収まるなら subtask 化しない（過剰分割の禁止）。
4. **（subtask 分割する場合のみ）**: 親 plan は「メタ plan」として割れ目（subslug 境界）と producer→consumer の
   順序を `plan.md` に定義し、各 subtask を `aidev new <NN>-<subslug> --parent <親> [--depends 兄弟名]` で作る
   （protocol.md「2.8」）。**各 subtask の詳細 tasks.md は、その subtask の plan 工程で作る**（親 plan では作らない）。
   - **子 plan の scope 凍結**: subtask の plan は **scope を再決定してはならない**（割れ目は親 plan が確定済み）。
     子 plan は自分の slice の tasks.md 分解と、兄弟 subtask への dependsOn 順序付けに限定する。
   - 子は親の `spec.md`/`design.md` を継承する（guard が親配下を自動 fallback。子に複製しない）。
5. **（分割しない場合）** spec を独立して検証可能な小さなタスクに分解し、`tasks.md` をチェックリストで作る。
   - 各タスクは coding 工程で 1 つずつ消化できる粒度にする。
   - 依存があるタスクは順序が分かるように並べる。依存が複雑なら mermaid で図示する（protocol.md「9.」）。
6. protocol.md「3. 工程終了プロトコル」に従って終了する（次工程: 分割時は最初の subtask の `plan`、
   非分割時は `coding`）。承認は `aidev approve plan tasks_planned=<tasks.md のタスク総数>`（protocol.md「3.」「8.」）。

## plan.md テンプレート

```markdown
# 計画: <タイトル>

## 実装方針
<spec をどの順序で・どう組み立てるか>

## 作業順序と依存関係
1. <ステップ>（依存: なし）
2. <ステップ>（依存: 1）

## リスク / 留意点
- <想定リスクと対応>

## テスト方針
- <test 工程で何をどう確認するか>
```

## tasks.md テンプレート

```markdown
# タスク: <タイトル>

- [ ] T1: <タスク内容>
- [ ] T2: <タスク内容>（依存: T1）
- [ ] T3: <タスク内容>
```

## 完了の目安

- spec の全範囲が tasks に漏れなく落ちている。
- 各タスクが「1 タスク = 1 つの検証可能な変更」になっている。
