---
name: aidev-60-review
description: ［標準工程・末尾0／主トリガ:両方（直接起動 or 前工程からの遷移／autonomous 自動）］AI開発ワークフローの review（レビュー）工程。差分を要件・仕様・規約の観点で点検し、指摘があれば coding へ差し戻す。「レビューして」「review工程」などと言われたとき、または前工程から案内されたときに使用する。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Agent]
---

AI 開発ワークフローの **review（レビュー）工程**を実行する。
実装全体を spec・要件・コーディング規約の観点で点検する。指摘があれば coding 工程へ差し戻す。
通過後は最終工程 deliver（着地）へ進む。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` と、PJ 固有ルールを読むこと。**

## 前提

- test 工程を通過していること（実装が受け入れ基準を満たしている）。

## 入力

- 変更差分（diff）。
- 対象フォルダの `requirement.md` / `spec.md` / `decisions.md`。
- PJ 固有のコーディング規約。

## 出力

- レビュー指摘の一覧（重大度付き）。
- `review.md`（指摘の**内容**をラウンドごとに追記。protocol.md「8.」のフォーマット）。
- 指摘なしの場合もその旨を `review.md` に記録。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定する。
   - **対象が subtask（state.yml に `parent` あり）か親かを見分ける**。subtask の review は**その slice 単独**の
     レビュー（局所欠陥を漸進的に潰す）。親の review は全 subtask 完了後の**統合 review**（結合起因の欠陥を見る）。
2. 差分を以下の観点で点検する。
   - **要件適合**: requirement の完了条件・spec の意図を満たしているか。
   - **正確性**: バグ・エッジケースの取りこぼし・異常系。
   - **規約適合**: PJ のコーディング規約・レビュー観点（AGENTS.md や PJ固有 skill があれば優先）。
   - **保守性**: 重複・複雑さ・命名・周辺コードとの一貫性。
   - **（統合 review のみ）結合**: subtask 間の契約整合・結線・統合 test の通過。単体 review では見えない
     subtask 横断の不整合を重点的に見る。
3. 指摘を重大度（must / should / nit）付きで一覧化し、`review.md` に当該ラウンドとして追記する。
4. 判定に応じて分岐する。
   - **must/should の指摘あり** → `aidev event review sent_back` を記録のうえ coding 工程への
     差し戻しを提案する（protocol.md「4. 番号と順序」に基づく正当な遷移）。
     coding を**再開する際は `aidev event coding start` を記録する**（さもないと手戻り回数を取りこぼす。protocol.md「3.」「8.」）。
     - **統合 review の差し戻し先（protocol.md「2.8」）**: 結合起因の指摘は**原因となった subtask の coding** へ
       戻す。`.aidev/current` を該当 subtask（`<親>/<NN>-<subslug>`）に切り替え、親 `activeSubtask` をその子に戻し、
       **その子の `approved` から `review` を外して**（完了を取り消す）から `aidev event coding start`。これで
       再 coding→test→review 後の `approve review` が再びカーソルを前進させられる（D と整合）。
       再 split（親 plan 戻し）は避け、最小手戻りにする。
   - **指摘なし（または nit のみ）** → protocol.md「3. 工程終了プロトコル」に従って終了する。
     - **subtask の review** なら、`aidev approve review` の時点で **CLI がカーソルを自動前進**させる
       （手動の `activeSubtask` 操作は不要）: 親 `subtasks` の次の未完 subtask があれば `activeSubtask` と
       `.aidev/current` をそこへ進め（次工程: その子の `plan`）、全 subtask 完了なら `activeSubtask=done` にして
       `.aidev/current` を親へ戻す（次工程: 親の統合 `test`）。CLI の出力 `cursor: …` で遷移先を確認する。
     - **親の統合 review** なら **複雑度の自己評価（walkthrough 推奨判定）**: protocol.md「4.5」に従い「差分が
       大きい/複数モジュール横断/処理フローが複雑」のいずれかなら、遷移ゲートに `承認して walkthrough(任意) を挟む`
       （推奨）を加え理由を添える（次工程: 推奨時 `walkthrough`、それ以外 `deliver`）。
5. 承認は `aidev approve review must=<件数> should=<件数> nit=<件数>`（protocol.md「3.」「8.」）。

## 完了の目安

- must/should の指摘が解消されている。
- 変更が requirement・spec・規約に整合している。
