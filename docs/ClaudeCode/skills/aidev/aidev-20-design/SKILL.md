---
name: aidev-20-design
description: ［aidev 標準工程］aidev の design（仕様策定）工程。進行中の aidev 作業の requirements.md を実装仕様 design.md に落とす。「aidev design」「design 工程」と言われたとき、または前工程から案内されたときに使用する。aidev 作業の無い単発の仕様書作成では使わない。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Agent, EnterPlanMode, ExitPlanMode]
---

AI 開発ワークフローの **design（仕様策定）工程**を実行する。
requirements を「どう作るか」の実装仕様に落とす。設計判断・インターフェース・データ構造を確定し、
`design.md` としてまとめる。コードはまだ書かない。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 前提

- `requirements.md` が存在すること。無ければ実行を中止し、requirements 工程を促す。
- **`profile: light` の work ではこの工程を単独で起動しない**（protocol.md「11.」）。light では
  `design.md` は requirements の 1 ゲートで既に書かれている。起動されたら実行を中止し、
  `coding` へ進むか、`aidev escalate` で full に昇格してから design を書き直すかを確認する。

## 入力

- 対象フォルダの `requirements.md`。
- 既存コードや PJ 固有ルール（AGENTS.md 等。存在すれば設計判断の基準として優先する）。

## 出力

対象フォルダに `design.md` を生成する。requirements の未確定事項があればここで解消する。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定。
   `aidev guard design` で前提を検査し、`aidev event design start` を記録する
   （exit≠0＝未充足。目視確認で代替しない。start が無いと所要時間も手戻りも導出できない）。
2. `requirements.md` を読み、完了条件を満たす実装方針を検討する。
   - 有力な案が複数あるなら、**`design.md` を書く前に plan モードへ入る**（承認を取ってから解除して書く）。
     **入る条件は `protocol-autonomous.md`**——ここに写さない（`aidev guard design` が該当時だけ促す）。
3. 設計判断を行う。PJ のドメイン固有の論点（PJ ルールに記載があれば、それに従う）は明示的に扱う。
   - 設計選択が多いなら深掘り質問（grilling）を opt-in で行う（PJ の質問深掘り skill があれば優先。
     小規模と autonomous ではスキップ）。
4. 下記テンプレートに沿って `design.md` を記述する。
   シーケンス・状態遷移・データモデルは、明確になるなら mermaid で図示する（protocol.md「9.」）。
   - 書き終えたら内部一貫性を別コンテキストへ点検させる（`autonomous` は必須。規約は
     `protocol-check.md`「(a)」）: `aidev doccheck start design --mode <delegated|same_session>`
     → `aidev doccheck report design --findings <n>`。
5. **複雑度の自己評価（architecture 推奨判定）**：protocol.md「4.5」の architecture の4条件に該当すれば、
   次の遷移ゲートの選択肢に `承認して architecture(任意) を挟む`（推奨）を加え、推奨理由を添える。
6. protocol.md「3. 工程終了プロトコル」に従って終了する
   （次工程: `tasks`、または推奨時は `architecture` へ進むか確認）。

## design.md テンプレート

```markdown
# 仕様: <タイトル>

## 概要
<requirements をどう実現するかの要約>

## 設計方針
<採用するアプローチと理由。代替案を退けた理由があれば添える>

## 対象範囲
- 変更/追加するモジュール・ファイル

## インターフェース / データ構造
- <API・関数シグネチャ・設定スキーマ・データ形式など>

## 振る舞いの詳細
- <入出力・状態遷移・エッジケース>

## ドメイン固有の考慮
- <PJ のドメイン固有の論点。PJ ルール(AGENTS.md 等)に該当があれば反映する>

## エラー処理 / 異常系
- <想定エラーと扱い>

## 受け入れ基準との対応
- AC1: <requirements の AC1 をどう満たすか>
- AC2: <…>
（requirements の `完了条件 (受け入れ基準)` の ID に 1:1 で対応させる。漏れがあれば ID で分かる。
書式は行頭 `- AC<id>: …`——`aidev coverage` の `design` 列がここを読む）
```

**各 AC には「その入力がどこから来るか」を書く**。`coverage` は ID の対応しか見ないので、
入力の出所の欠落は機械では拾えない（他 PJ の retro が実測——出所の無い AC が coding まで素通りした）。

## 完了の目安

- requirements の全完了条件に対し、実現方法が design 上で説明できる。
  **各 AC の入力の出所が design 内で辿れる**（辿れないなら design の穴か requirements への差し戻し）。
- tasks 工程で作業分解できる粒度まで設計が具体化している。
