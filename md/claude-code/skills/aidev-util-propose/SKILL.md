---
name: aidev-util-propose
description: ［ユーティリティ・パイプライン外／主トリガ:ユーザー起動］AI開発ワークフローの planner（課題提案）ユーティリティ。charter と信号（insights/retro/lint/テスト等）から次に着手すべき課題を提案し、適切な粒度に分割して、承認のうえ issue/バックログ化する。「次の課題を提案して」「バックログを作って」「propose」などのときに使用する。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Agent]
---

AI 開発ワークフローの **planner（課題提案 / L_planner・A 層）**。
**charter（ゴール・制約）と実信号**から次に着手すべき課題を**提案**し、split 判定で右サイズ化して、
**承認のうえ issue / バックログ化**する。出力は `aidev-util-batch` や per-issue の aidev が消化する。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読むこと。**

## 位置づけ（重要）

- **パイプライン工程ではない**（番号なし。insights/batch と同列のユーティリティ・最上流 L_planner）。
- **AIが自由に発案するのではなく、信号に根ざして提案**する（恣意的発案は暴走の元）。
- **採否は人間が決める**のが既定（interactive）。autonomous でもガード内に限定。
- **作るのは提案＋issue/バックログまで**。実装は aidev（autonomous）/aidev-util-batch が担う。

## 前提

- `.aidev/charter.md`（ゴール・スコープ・やらないこと・品質基準）があること（無ければ作成を促す）。
  charter が planner を縛る錨。これが無いと提案が発散する。

## 入力（信号・grounded 優先）

1. **charter**: ゴール/スコープ/制約/優先度。
2. **実信号**（あれば優先）:
   - `.aidev/insights/*`（横断分析の改善提案）
   - `.aidev/works/*/retro.md`（per-work 改善提案）
   - lint / テスト失敗 / カバレッジ欠落 / TODO・FIXME / 既知の技術的負債
3. **既存の open issue ＋ バックログ**（重複排除のため）。

## 出力

- 提案課題の一覧（根拠・優先度・split 案つき）。
- 承認分 → `create-issue`（PJの issue 作成 skill）で issue 化、かつ/または バックログ（`.aidev/backlog/*.md`）へ追記。

## 手順

1. charter と信号を読む（信号が薄い場合はユーザーの高レベル要望を入力にする）。
2. 候補課題を抽出する。**信号由来を優先**（insights/retro/負債）。各候補に根拠（出典）を付ける。
3. **split 判定**（DESIGN「split 判定基準」に従う）:
   - 規模は引き金。**結合度**で可否を決める。低結合で単独検証可なら**複数課題に分割提案**。
   - 高結合は1課題のまま（大規模＋高結合は依存順分割/リファクタ先行を提案）。
4. **重複排除**: 既存 open issue / バックログと突き合わせ、重複・包含を除く。
5. **優先度付け**: charter のゴール・価値・リスク・依存で並べる。
6. **採否**（protocol「10.」のモードに従う）:
   - interactive: `AskUserQuestion` で「どの課題を作るか」を選ばせる（複数選択可）。
   - autonomous: ガード内で自動採用（**grounded・独立・1回の件数上限内**のみ。曖昧/高結合/根拠薄は採用しない）。
7. 採用分を起票: `create-issue` で issue 化（ブランチ運用は委譲）かつ/または バックログへ `[ ]` 追記。
   - **backlog へ追記する場合**: 定常ドメインキュー（`.aidev/backlog/<domain>.md`、`kind: standing`）か、
     1タスクを分割した産物なら `split-<親>.md`（`kind: split` / `parent`）に分ける（`aidev-util-batch`「backlog ファイル規約」）。
     着手前から既知の前提は項目行末に `(needs: <slug/#N>)` を付す。
   - **依存関係があれば記録する**: issue 本文に前提（例 `#18 に依存`）を明記し、backlog 項目には `(needs: …)` を付す。
     その課題が works 化される際に `aidev new --depends <works slug/#N>` で `dependsOn` へ設定される
     （batch・start いずれの入口でも。`protocol.md`「2.7」）。これで全入口で依存順が尊重される。
8. レポート（採用/見送り/分割の理由、作成した issue/バックログ）。

## 安全弁（必須）

- **人間承認が既定**（interactive）。autonomous は grounded・独立・件数上限内に限定。
- **charter で縛る**（スコープ外・non-goals は提案しない）。
- **重複排除**（既存 issue/バックログと衝突させない）。
- **提案止まり**（実装はしない。誤提案は起票段階で人間が弾ける）。

## 自己給餌ループとしての位置（参考）

`insights/retro（信号）→ aidev-util-propose（課題化・承認）→ aidev-util-batch（autonomous 実装）→ PR（人間レビュー）`。
両端（どの課題・どの PR）に人間ゲートを残し、間を自律化するのが実用形。完全自動（発案→マージ）は高リスク。
