---
date: 2026-09-06
change: plan モードの判断基準を EnterPlanMode 自身の WHEN TO USE から導出し直し、対象を上流4工程にする
---

## 1. 文書は実態に追いついているか

**判断基準を 3 回発明して 3 回とも外した**。実走がそれを実測で潰した。

| 回 | 発明した物差し | なぜ外れたか |
|---|---|---|
| 1 | 「方針と成果物が分離できない」 | **spec / design にもそのまま当てはまる**。区別になっていない後付けのラベル |
| 2 | 「行動計画 vs 仕様」 | **`ExitPlanMode` の定義が逆を言う**（「planning the implementation steps」＝`plan` 工程こそ最適合） |
| 3 | 「入力に既存コードが入る工程」 | 実走が各 SKILL の「## 入力」を突き合わせ、**`plan` にコードは無く `test`/`review`/`walkthrough`/`research` には有る**と実測。**集合が反転する** |

**正解は発明する必要が無く、`EnterPlanMode` 自身の WHEN TO USE に書いてあった**——
「Multiple Valid Approaches」「Architectural Decisions」「User Preferences Matter」、
裏返しの WHEN NOT TO USE が「the user has given very specific, detailed instructions」。
つまり **方向が複数あって、選び損なうと無駄になるか**。

これで 11 工程が導出できる:

| 分類 | 工程 | 導出 |
|---|---|---|
| **入る** | requirement / spec / design / plan | 「何を／どう／どんな構造で／どう分けるか」を**選ぶ**。選び損なうと文書ごと無駄 |
| 入らない | test / review / walkthrough / deliver / retro | **観測して報告する**。方向を選ばない（**コードを読むかどうかは関係ない**——これらも読む） |
| 入らない | coding | 上流の `tasks.md` が方向を固めている |
| 入らない | `aidev-00-start` の三層判定 | 選ぶが**選び直せる**（`aidev escalate`） |
| 入らない | research | plan モード自身が外す（WHEN NOT TO USE: use the Agent tool instead） |
| 入らない | subtask の plan | 切り方は親の plan が確定済み |

**教訓**: **道具の可否を決める前に、その道具の定義を読む**。3 回とも、手元にツール定義があるのに
読まずに分類を作った。`DESIGN`「2.」に記録した。

## 2. README のメンテナンス

- `bin/README.md`: `guard` 行から**工程集合と条件の写しを削り**、正典への参照に落とした
  （実走が「2 コミット前に掃除したセルに、より大きな写しを置き直した」と指摘）。L9 の行も更新。
- `aidev-docs/README.md`: 同じく参照に落とした。

## 3. 実走（サブエージェント）

履歴付き clone で lint / テストを実行。`.claude/skills/` とハーネス本体の未変更を
sha256 と `git diff | md5sum` の両方で確認済み（実走が自分で二重に検証した）。

### 実走が見つけた欠陥と対応

| # | 欠陥 | 対応 |
|---|---|---|
| **B** | **基準から 11 工程中 4〜5 しか導出できない**（`plan` が落ち、`test`/`review`/`walkthrough`/`research` が入る側に倒れる） | 基準を `EnterPlanMode` の WHEN TO USE から導出し直した（上記「1.」） |
| **F-1** | **`aidev-30-plan/SKILL.md` が `EnterPlanMode` を `allowed-tools` に持たない**のに「入れ」と命じていた | 追加。`requirement` にも追加 |
| **F-9** | 逆に `aidev-00-start` は外したのに `EnterPlanMode` が残っていた | 削除 |
| **F-2** | **subtask の `guard plan` が促していた**（切り方は親が確定済み＝基準 (a) に反する） | `parent` を見て除外。sh / ps1 両方＋テスト |
| **C-8/F-5** | **L9 に新規の抜け穴 6 通り**——字下げした子の箇条書きへ送る／新条件の語彙（`read-only`・`主活動`・`ヒアリング`・`既存コード`・工程名の列挙）／`bin/README.md` が走査対象外 | 窓を「より深い子は取り込む」に、`PMKEY` に新語彙、走査対象に `bin/README.md`。**6 通り全部を probe するテスト**を追加 |
| **C-7/F-6** | **`guard plan` の回帰検査が空振り**していた（直前に `spec.md` を消していたので exit 2 で促しに到達せず、`case` から `plan` を外しても入れても緑） | 前提を揃えて実効化。ラベルも旧理由から書き換え |
| **F-10** | ps1 パリティ検査が `guard spec` だけで、**今回足した工程を見ていなかった** | `requirement` / `plan` / `coding` / `review` / subtask を追加 |
| **C-2** | 「順に見る」手順が (a) だけで (b) が適用されない | 3 段（承認者 → (a) → (b)）に |
| **C-3** | `DESIGN.md:464-474` に旧基準・旧集合が正文として生存（`plan` について新旧が正反対） | 撤回の記述を上の列挙に統合 |
| **C-6** | `bin/aidev` のコメントに旧集合と、廃した「使ってよい」 | 書き換え |
| **F-11** | plan の引き金だけ「ここに写さない」の一句が落ちていた | 揃えた |
| **F-12** | 「research は基準の外の規則ではなくなった」は成立しない（一次根拠が付くことと導出できることは別） | 「plan モード自身が外している」＝基準の外の規則、と書き直した |

### 見送り

- `aidev use <slug>` が日付付きディレクトリ名でないと通らない（`new` が受ける綴りと非対称）——本改修と無関係。

## テスト

**913 pass / 0 fail / 0 skip**（pwsh 7.4.6・gawk・mawk の 3 通りで一致）。
L9 の自己テストは**塞いだ抜け穴を 1 つずつ再現して捕捉を確認**し（対象ファイル外 5 種・
字下げした子・新語彙 4 種）、最後にハーネス本体が未変更であることまで assert する。
