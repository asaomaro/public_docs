---
name: aidev-65-walkthrough
description: ［aidev 任意工程］aidev の walkthrough（レビューガイド生成）工程。人間の PR レビューを補助する解説を作る。「aidev walkthrough」「walkthrough 工程」と言われたとき、または review 通過後に複雑度が高いと検知され推奨されたときに使用する。
allowed-tools: [Bash, Read, Write, AskUserQuestion, Agent]
---

AI 開発ワークフローの **walkthrough（レビューガイド生成）工程**（任意）。
**人間の PR レビューを補助する解説ドキュメント**を生成する。aidev-60-review（AIの自己レビュー）とは別物で、
こちらはレビュアーの理解と時間節約を目的とする。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 位置づけ

- 任意工程（番号末尾5、review と deliver の間）。小さな変更には不要。
- 起動経路（protocol.md「4.5」）: ユーザー指定、または review 終了時の AI検知＋推奨（複雑度が高い場合）。
- review 通過後の**確定コード**を対象にする（差し戻し解消後なので説明とコードが一致）。
- 重い解析（広い差分の読解）はサブエージェントに委譲してよい。

## 起動判定（検知ロジック）

review 終了時に **protocol.md「4.5」の walkthrough の3条件**のいずれかに該当したら発火対象とする（条件はそこが正典）。

- **interactive**: 検知時、遷移ゲートに `承認して walkthrough(任意) を挟む`（推奨）を理由付きで加える。却下されれば deliver へ直行。
- **autonomous**: **既定で実施**する（`protocol-autonomous.md`。検知の有無によらず生成する。`profile: light` では実施しない）。

## 前提

- review 工程を通過していること（must/should 解消済み・コード確定）。

## 入力

- 変更差分（`git diff`）。
- 対象フォルダの `requirement.md` / `spec.md` / `design.md`(あれば) / `decisions.md`。
- 実装コード。

## 出力

対象フォルダに `walkthrough.md` を生成する（deliver で PR に活用）。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定する。
   `aidev guard walkthrough` で前提を検査する（exit≠0＝未充足。目視確認で代替しない）。
2. 差分と成果物を読み、**レビュアーが知るべき非自明な点**を抽出する。
   - 重要ポイント（設計判断の要、トリッキーな箇所、影響範囲）
   - リスク・特に見てほしい点
   - 処理フロー（必要なら状態遷移・シーケンス）
3. `walkthrough.md` を下記テンプレートで記述する。
   - **処理フローは mermaid** で図示する（flowchart / sequenceDiagram 等）。
   - 該当コードは **`path:line`** で指す（クリックで飛べる形）。
4. protocol.md「3. 工程終了プロトコル」に従って終了する（次工程: `deliver`）。

## 品質の原則（重要）

- **コードの全再掲はしない**。レビュアーの時間を節約する「非自明点・リスク・全体像」に絞る。
- 自明な変更を逐次解説しない。図と要点で「どこを・なぜ見るか」を示す。

## walkthrough.md テンプレート

```markdown
# レビューガイド: <タイトル>

## 変更概要 / 目的
<何を・なぜ。requirement/spec の要約>

## 重要ポイント（特に見てほしい所）
- <非自明な実装・設計判断。decisions.md があればリンク>

## 処理フロー
\`\`\`mermaid
flowchart TD
  A[...] --> B[...]
\`\`\`

## 主要な変更箇所
- `path/to/file.ts:42` — <その変更の要点>

## リスク / 確認してほしい点
- <レビュアーに判断を仰ぎたい点・既知の制限>
```

## 完了の目安

- レビュアーが差分の意図・要点・リスクを短時間で把握できる内容になっている。
- 処理フローが mermaid で図示され、該当コードが `path:line` で参照されている。
