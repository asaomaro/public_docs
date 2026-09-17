---
date: 2026-09-16
change: 他 PJ の retro 13 件（5250プロジェクト由来）を検証し、guard の前提工程承認検査の欠落（Theme A）を適用。残りは優先順位付けのうえ DESIGN.md に記録して見送り
---

## 1. 文書は実態に追いついているか

**受け取った提案をそのまま入れない**——13 件の retro から「ハーネス自体」の改善提案を抽出し（約40件）、
実物で確かめてから採否を決めた。

| 提案（要約） | 出所 | 判定 | 根拠（実測） |
|---|---|---|---|
| `event <phase> start` は前提工程の承認を検査すべき | acs-data-transfer / hostserver-sql（2件が独立に指摘） | **症状は事実。直す層は違う** | `protocol.md`「2.」は `guard` が入口ゲートだと明記。実測すると `guard design` は requirements 未承認でも OK を返していた——6/9工程（`research`/`design`/`architecture`/`tasks`/`coding`/`test`）が前提成果物の**実在**しか見ておらず、**承認**を見ていなかった（`review`/`deliver`/`retro` の3工程だけ承認を見ていた） |
| verify は「approved はあるが start が無い」を検知すべき | screen-macro #3 | **既に実装済み** | `event_pair_warnings()` で既存動作を確認 |
| deliver の SKILL.md 手順は `event deliver start` を最初に置くべき | screen-macro #4 | **既に実装済み** | `aidev-70-deliver/SKILL.md` の step 1 で確認済み（datetime-picker H4 の適用） |
| review に review→backlog の配線が無い | sql-insert-upload | **既に解消済み** | 前ラウンドで `aidev backlog add` を追加済み（この retro はそれ以前の記録） |
| datetime-picker H1〜H6 | datetime-picker | **適用済み（本ラウンドでは無変更）** | 5件（H1〜H5）が既存ファイルに実在することを再確認、H6 は撤回のまま |

上記以外の残り約35件の提案は、下記「優先度」節のとおり分類し、今回は Theme A（guard の前提承認検査）
1件だけを適用した。**1ラウンドで多数を同時に変えると検証が粗くなる**——過去ラウンドの学びのとおり、
1つを深く検証するほうを優先した。

## 2. README のメンテナンス

- `aidev-docs/DESIGN.md`「2.6」— `guard` の前提承認検査の欠落と修正内容、subtask/light の分岐が
  必要だった理由を追記。「退けた案」に `event start` 側で検査する原提案を退けた理由を追記。
- `aidev-docs/DESIGN.md`「5.」— 13件の retro から拾った未着手の改善提案を優先度つきで記録
  （最優先: 「主張の前提を疑う」観点の追加。3件の retro が独立に指摘した最多corroboration）。
- `aidev-docs/DESIGN.md`「6.」— acs-data-transfer / hostserver-sql の corroboration と、
  「提案の症状は正しいが直す層の指定が一段浅かった」という学びを記録。
- `protocol.md`「2.」・`bin/README.md` の `guard` 説明・各工程 SKILL.md の `guard` 言及は
  **いずれも変更不要**——散文は元々「前提工程の承認」を正しく検査対象と明記しており、
  今回の修正は実装を散文の約束に追いつかせただけ（散文側の記述ミスではなかった）。

## 3. 実走（サブエージェント）

テスト PJ（`/tmp/aidev-flowrun-guardfix`、ハーネスを `.claude/skills/aidev/` にコピーし fresh git init）
で以下を確認：

- **前提未承認での block**: `requirements.md` を書いて未承認のまま `aidev guard design` →
  `NG 前提工程が未承認: requirements`（exit 2）。`aidev approve requirements` 後は `OK guard design`（exit 0）。
- **通常経路の無回帰**: design→tasks→coding を承認を挟みながら通し、各段で block→approve→pass の
  パターンを確認（回帰なし）。
- **light プロファイル**: `guard design`/`guard tasks` は従来どおり単独起動を拒否（この修正の対象外・無変更）。
  `requirements` のみ承認した状態で `guard coding` は最初 `NG 前提成果物が不足: tasks.md`
  （light でも `design.md`/`tasks.md` を**書く**必要はある。承認は不要なだけ）。ファイルを書けば通過。
- **subtask 継承**: 親の `01-sub-one` 作成後、subtask 自身は `requirements`/`design` を一度も承認せず、
  `guard tasks` が親の承認を継承して OK。`guard requirements`/`guard design` は subtask では拒否
  （親専用工程のガードは無回帰）。
- `aidev verify --strict` は全 work（`feature-alpha`・`feature-alpha/01-sub-one`・light の `feature-beta`）で exit 0。
- 終了後 `git status --porcelain`（ソースリポジトリ）は実行前後で不変（テスト対象ファイル4件の
  変更のみ、新規変更なし）。

**実走が見つけた小さな粗**: light プロファイルで `tasks.md` が欠けているときの `NG 前提成果物が不足:
tasks.md` というメッセージは、承認は不要でも**書く**ことは必要という light の性質を初見のユーザーには
伝えない（`protocol-light.md` を読まないと分からない）。実害は無い（メッセージ自体は正確）ため、
今回は見送り——次にこの種の混乱が実際に報告されたら `bin/README.md` のメッセージ説明を厚くする。

## 4. テスト

`sh aidev-docs/bin/test/run.sh`（pwsh 込み）: **pass=1101 fail=0 skip=0**
（本ラウンドで新設・修正したケース: subtask の `guard coding` が tasks 未承認では通らないことを追加検証、
light の `guard coding` に `approve requirements` を追加、`20260101-hint` フィクスチャ群に
`approved:` を追加、ps1 パリティの `guard design`/`guard architecture` フィクスチャに承認手順を追加）。

`sh aidev-docs/bin/test/lint-docs.sh .`: **pass=23 fail=0**（L1〜L13 すべて）。

## この改修の教訓

**retro の「原因」は正しいことがあっても「直す場所」が正しいとは限らない**——acs-data-transfer /
hostserver-sql はどちらも「requirements を承認しなくても次工程に進めた」という同じ実測を独立に
報告し、片方は前回提案が「未適用」であることまで確認していた。だが両方とも修正先を
`event <phase> start` としていた。`protocol.md`「2.」を読み直すと `guard` こそが入口ゲートだと
明記されており、実装を読むと `guard` 側の6工程で承認検査が丸ごと抜けていた——**症状の報告は
信頼し、直す層は自分で一次資料（protocol.md と実装）に当たって決め直す**、という扱いの実例。

**13件のうち適用したのは1件**。約40件の提案を全部同時に変えると検証が粗くなるため、
最も corroboration が強く（2件の独立した retro）・最も一次資料（`protocol.md`）と実装のギャップが
明確だった1件に絞り、残りは優先度をつけて `DESIGN.md`「5.」に記録した。次にこの種の retro が
来たときの入口はそこにある。
