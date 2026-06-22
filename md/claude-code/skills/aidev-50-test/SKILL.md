---
name: aidev-50-test
description: ［標準工程・末尾0／主トリガ:両方（直接起動 or 前工程からの遷移／autonomous 自動）］AI開発ワークフローの test（テスト/検証）工程。spec の受け入れ基準を検証し、失敗時は coding へ差し戻す。「テストしたい」「検証工程」「test工程」などと言われたとき、または前工程から案内されたときに使用する。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Agent]
---

AI 開発ワークフローの **test（テスト / 検証）工程**を実行する。
実装が spec の受け入れ基準を満たすか検証する。失敗が見つかれば coding 工程へ差し戻す。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 前提

- coding 工程で実装が行われていること（対象タスクが概ねチェック済み）。

## 入力

- 実装コード。
- 対象フォルダの `spec.md`（受け入れ基準）/ `plan.md`（テスト方針）/ `tasks.md`。

## 出力

- テスト実行結果のサマリ（合否・失敗内容）。必要に応じて追加したテストコード。
- 失敗時は coding への差し戻し指摘。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定する。
   - **対象が subtask（state.yml に `parent` あり）か親かを見分ける**（protocol.md「2.8」）。test の範囲が変わる。
2. `plan.md` のテスト方針と `spec.md` の受け入れ基準に沿って検証する。
   - 自動テストがあれば実行する。無ければ受け入れ基準ごとに確認手順を実施する。
   - 必要なら不足テストを追加する。
   - **subtask の test**: **その slice 単独で検証可能な範囲（unit・契約モック）に限定**する。高結合 work の
     subtask 境界は単独検証が効きにくい（`aidev-docs/DESIGN.md`「5.」: 検証可能性が seam の指標）。単独で
     検証できない結合は**ここで無理に検証しない**（false-green を避ける）。結合検証は親の統合 test に委ねる。
   - **親の統合 test**: 全 subtask 完了後、subtask 横断の**結合**を検証する（契約整合・結線・e2e）。
     subtask test で意図的に保留した結合の検証は、ここで確実に実施する。
3. 結果を要約する（合否、失敗したケースと原因）。
   - **環境不足で skip された検証を明示する**（未検証の穴）。テストランナーが skip 件数を出す場合は拾う
     （例: `run.sh` の `RESULT: … skip=N` / `NOTE: …`）。skip があれば「環境依存で未検証の surface」として
     要約に残し、**deliver に引き継ぐ**（PR 本文の既知の制約に載せる）。green でも skip>0 を「全数検証」と扱わない。
4. 判定に応じて分岐する。
   - **全て合格** → protocol.md「3. 工程終了プロトコル」に従って終了（次工程: `review`）。
   - **失敗あり** → 失敗内容を指摘としてまとめ、`aidev event test sent_back` を記録のうえ
     coding 工程への差し戻しを提案する（protocol.md「4. 番号と順序」に基づく正当な遷移）。
     coding を**再開する際は `aidev event coding start` を記録する**（さもないと手戻り回数を取りこぼす。protocol.md「3.」「8.」）。
5. 承認は `aidev approve test passed=<合格数> failed=<失敗数>`（protocol.md「3.」「8.」）。

## 完了の目安

- spec の全受け入れ基準に対する検証結果が揃っている。
- 未解決の失敗が残っていない（残る場合は coding へ戻す）。
