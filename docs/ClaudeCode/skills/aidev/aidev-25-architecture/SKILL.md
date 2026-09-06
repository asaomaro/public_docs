---
name: aidev-25-architecture
description: ［aidev 任意工程］aidev の architecture（詳細設計）工程。design と tasks の間で構造設計を固める。「aidev architecture」「architecture 工程」と言われたとき、または design 終了時に複雑度が高いと検知され推奨されたときに使用する。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Agent, EnterPlanMode, ExitPlanMode]
---

AI 開発ワークフローの **architecture（詳細設計）工程**（任意）。
design（何を作るか）と tasks（作業分解）の間で、**構造設計**を固める。
モジュール分割・インターフェース・データモデル・処理シーケンスなど、tasks で分解する前提となる
設計を具体化する。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 位置づけ

- 任意工程（番号末尾5、design と tasks の間に差し込む）。小〜中規模なら design＋tasks で足りるため不要。
- 起動経路は2つ（protocol.md「4.5」）: ユーザー指定、または design 終了時の AI検知＋推奨（複雑度が高い場合）。
- 設計検討が重い場合はサブエージェント委譲（protocol.md「2.6」）も可。

## 起動判定（検知ロジック）

design 終了時に **protocol.md「4.5」の architecture の4条件**のいずれかに該当したら発火対象とする（条件はそこが正典）。

- **interactive**: 検知時、遷移ゲートに `承認して architecture(任意) を挟む`（推奨）を理由付きで加える。却下されれば tasks へ直行。
- **autonomous**: 検知時、推奨ではなく自動で実施する。該当しなければスキップして tasks へ進む。

## 前提

- `design.md` が存在すること。無ければ実行を中止し、design 工程を促す。

## 入力

- 対象フォルダの `design.md`（必要に応じて `requirements.md` / `research.md`）。
- 既存コードの構造、PJ のアーキテクチャ規約。

## 出力

対象フォルダに `architecture.md` を生成する（tasks の入力になる）。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定。
   `aidev guard architecture` で前提を検査し、`aidev event architecture start` を記録する（exit≠0＝未充足。start が無いと `verify --strict` が落ち、ts は後から復元できない）。
2. design を実現する構造を設計する。典型的な観点:
   - コンポーネント / モジュール分割と責務
   - 主要インターフェース・型・データモデル
   - 処理フロー / 状態遷移 / シーケンス（必要なら）
   - 既存アーキテクチャとの整合、横断的関心事（エラー処理・ログ等）
3. 設計上の選択は理由とともに残す（採用案・退けた代替案）。重い検討は委譲してよい。
   - 構造の選択肢が複数あるなら、**`architecture.md` を書く前に plan モードへ入る**（承認を取ってから解除して書く）。
     **入る条件は `protocol-autonomous.md`**——ここに写さない（`aidev guard architecture` が該当時だけ促す）。
4. 下記テンプレートに沿って `architecture.md` を記述する。
   アーキテクチャ/コンポーネント・class・sequence・state は mermaid で図示する（protocol.md「9.」）。
   - 書き終えたら内部一貫性の点検（対象範囲を構造が満たすか・責務分割の漏れと重複・図と本文の整合）を
     別コンテキストへ点検させる（`autonomous` は必須。規約は `protocol-check.md`「(a)」）:
     `aidev doccheck start architecture --mode <delegated|same_session>` → `report architecture --findings <n>`。
5. protocol.md「3. 工程終了プロトコル」に従って終了する（次工程: `tasks`）。

## architecture.md テンプレート

```markdown
# 設計: <タイトル>

## アーキテクチャ概要
<全体構造の要約。図や箇条書きで>

## コンポーネント / モジュール
- <名称>: <責務 / 依存>

## インターフェース / データモデル
- <主要な型・API・スキーマ>

## 処理フロー / シーケンス
- <重要な経路の流れ。状態遷移があれば>

## 設計判断
- <採用したアプローチと理由。退けた代替案>

## tasks への申し送り
- <作業分解時に踏まえるべき分割単位・順序の示唆>
```

## 完了の目安

- design を実装するための構造が、tasks で作業分解できる粒度まで具体化している。
- 主要な設計判断が理由付きで残っている。
