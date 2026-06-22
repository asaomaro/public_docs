---
name: aidev-util-insights
description: ［ユーティリティ・パイプライン外／主トリガ:ユーザー起動］AI開発ワークフローの横断分析ユーティリティ。複数の作業（.aidev/works/*）を横断して review.md / metrics.yml / decisions.md を集計し、再発パターンと systemic な改善提案をまとめる。「横断分析して」「これまでの作業の傾向を見たい」「insights」などと言われたときに使用する。
allowed-tools: [Bash, Read, Write, AskUserQuestion, Agent]
---

AI 開発ワークフローの **横断分析（cross-work insights）ユーティリティ**。
複数の完了作業を横断して記録を集計し、**再発パターン**と **systemic な改善提案**を出す。

per-work の `retro` が「その作業1件」を振り返るのに対し、これは **meta レベル**（作業をまたいだ傾向）を見る。

## 位置づけ（重要）

- **パイプライン工程ではない**（番号なし）。`protocol.md` の「対象作業の特定」「工程終了プロトコル」
  「メトリクス記録」には**乗らない**（特定の works を進める skill ではないため）。
- 読み取り中心の分析。出力はレポートで、**改善は提案のみ**（適用は人間。retro と同じ思想）。
- metrics.yml / review.md のスキーマ理解のため `aidev-00-start/protocol.md`「8.」を参照してよい。
- 読み込みが重い場合はサブエージェントに委譲してよい（works ごとに読ませてサマリを集約）。

## 前提

- `.aidev/works/` に複数の作業がある（1件以下では傾向が出ないため、その旨を明示して続行）。

## 入力（全 works 横断）

- **定量指標は `aidev metrics --all` で機械集計する**（`metrics.yml` を手読みしない）。
  - `.claude/skills/aidev-docs/bin/aidev metrics --all`：work 別の first_start / delivered / **lead_sec（リードタイム）** /
    **reworks（手戻り）** / **sent_backs（差し戻し）**。
  - `.claude/skills/aidev-docs/bin/aidev metrics --all --phases`：work×工程の start / approved / **elapsed_sec（工程時間）**。
  - `--format tsv` で機械パース可（列の集計・平均算出に使う）。Windows は `pwsh .claude/skills/aidev-docs/bin/aidev.ps1 metrics ...`。
- `.aidev/works/*/review.md`：レビュー指摘の内容（再発パターン分析の主材料。**テキストは読む**）。
- `.aidev/works/*/decisions.md`：繰り返される設計逸脱（テキスト）。
- `.aidev/works/*/retro.md`：過去の per-work 改善提案（再発・未対応の把握。テキスト）。

## 出力

- `.aidev/insights/<YYYY-MM-DD>-insights.md`（日付は `date -u +%F` で取得）。履歴として残す。

## 手順

1. 対象範囲を決める（既定は全 works）。必要なら期間や対象を `AskUserQuestion` で絞ってよい。
2. **定量指標は `aidev metrics --all`（必要に応じ `--phases`/`--format tsv`）で機械集計**し、テキスト材料
   （review.md / decisions.md / retro.md）は読んで突き合わせる。重い場合は works 単位の読み取りを委譲する。
   （記録ドリフト＝metrics/review 欠落は `aidev doctor` で機械検出できる。legacy work は免除される。）
3. 次の観点で傾向を抽出する（数値は手順2の `aidev metrics` 出力から算出する）。
   - **レビュー指摘の再発**：同種・同観点の指摘が複数作業で繰り返されていないか。
   - **ボトルネック工程**：手戻り回数(reworks)・差し戻し(sent_backs)・経過時間(elapsed_sec)が突出する工程はどれか。
   - **上流の効き**：research/design を挟んだ作業は手戻りが少ないか（任意工程の効果）。
   - **未対応の改善**：過去 retro の提案で、繰り返し挙がるが未反映のもの。
   - **未着手キューの滞留（任意）**：`.aidev/backlog/*.md`（archive 除く）の未処理件数・滞留や
     `(needs:…)` で止まっている項目を、残作業のコンテキストとして添えてよい（完了作業の分析が主旨）。
4. 観察を **systemic な改善提案**に変換し、3カテゴリに仕分ける。
   - **製品 / コード**：横断する技術的負債 → 新 issue 候補。
   - **PJ プロセス / 規約**：反復するレビュー指摘・観点抜け → AGENTS.md への反映案。
   - **ハーネス自体**：工程・ゲート・protocol の構造的不備 → `aidev-*` への変更提案（提案のみ）。
5. 下記テンプレートで `.aidev/insights/<日付>-insights.md` を生成し、サマリを提示する。
   - これは提案レポート。採用された提案は、ユーザー指示で別途（issue / AGENTS.md / 基盤改修）対応する。

## insights.md テンプレート

```markdown
# 横断分析 (<日付>)

## 対象
- works: <件数・対象範囲>

## 主要メトリクス（横断）
- 平均リードタイム / 手戻り回数の分布 / ボトルネック工程
- research・design 使用有無と手戻りの相関（わかる範囲で）

## 再発パターン
### レビュー指摘
- <繰り返し現れる指摘の類型と頻度>
### 設計逸脱・その他
- <decisions/retro から繰り返すもの>

## 改善提案
### 製品 / コード（→ issue 候補）
- <横断する負債>
### PJ プロセス / 規約（→ AGENTS.md）
- <反復指摘・観点抜けへの対応案>
### ハーネス自体（→ aidev-* への提案・適用は人間）
- <構造的改善案と理由>

## データの限界
- <件数不足・記録欠落など、解釈上の注意>
```

## 完了の目安

- 単一作業では見えない**横断の再発パターン**が抽出されている。
- 改善提案が3カテゴリに仕分けられ、次アクションが明確（提案止まりでよい）。
