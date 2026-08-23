---
name: aidev-70-deliver
description: ［標準工程・末尾0（最終）／主トリガ:両方（直接起動 or 前工程からの遷移／autonomous 自動）］AI開発ワークフローの deliver（着地）工程。レビュー済みの変更をコミット・PR作成で着地させる最終工程。「コミットして」「PRを出して」「deliver工程」などと言われたとき、または review 通過後に使用する。
allowed-tools: [Bash, Read, AskUserQuestion]
---

AI 開発ワークフローの **deliver（着地）工程**。ワークフローの最終工程。
review を通過した変更を、コミット・PR 作成によって実際に着地させ、作業を完了する。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 前提

- review 工程を通過していること（must/should の指摘が解消済み）。

## 入力

- 着地対象の変更（diff）。
- 対象フォルダの `requirement.md`（issue 番号等）/ `state.yml`。

## 出力

- コミット（必要に応じて複数）。
- プルリクエスト（PJ 運用に応じて）。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定する。
1.5. **既着地の検知（事後記録モード判定）**: 着地作業に入る前に、対象の変更が
   **aidev ゲート外で既に着地していないか**を確認する。実装が直接コミット／別 PR で main に入り、
   issue も閉じているのに deliver ゲートだけ未記録、という状態（実体と state の乖離）を防ぐため。
   - **チェック内容**:
     - 実装の主要変更が既にデフォルトブランチに入っているか
       （例: `git log --oneline <default>..HEAD` が空、かつ対象ファイルの変更がデフォルトブランチに存在）。
     - チケットが既にクローズ/完了か（github: `gh issue view <N> --json state -q .state`、
       他トラッカーは `.aidev/config.yml` の `tracker` に応じる）。
     - コミットメッセージに `Closes #<N>` 等の close 参照が既に含まれているか。
   - **既着地と判明した場合 = 事後記録モード**:
     - 新規コミット／PR は作らない（重複・空 PR を避ける）。**既に着地済みである旨をユーザーに明示**する。
     - 残作業は工程記録のみ：`state.yml` / `metrics.yml` の deliver 記録を追記し、
       **その記録だけをコミット**して締める（着地実体は既存コミットを参照）。
     - 着地先（既存コミットSHA・PR・issue 状態）を報告に含める。
   - **未着地（通常）の場合**: 手順 2 以降を通常どおり実行する。
2. **PJ資産の優先**（protocol.md「2.5」）: コミット/PR 用の PJ固有 skill・コマンドがあれば優先する。
   - 例: コミット → PJ のコミット skill、PR → PJ の PR 作成 skill。
   - 無ければ汎用手段（`git commit` / `gh pr create` 等）にフォールバックする。
3. コミット範囲をユーザーと確認する（実装コードと工程成果物を分けるか等、PJ 方針に従う）。
3.5. **台帳の同期（backlog / 残課題）**: 着手前に `protocol-backlog.md` を読む。この作業が閉じた未着手項目を、**同じコミット**に含めて反映する
   （`DESIGN.md`「2.5」: 流れは backlog → works（consume）で、**backlog 行は deliver で `[x]`**）。
   - **対象の特定**: `state.yml` に `backlog: <file>` があれば `.aidev/backlog/<file>` が主対象
     （`aidev new --backlog` が刻む）。刻印が無くても、**実装の過程で結果的に閉じた項目**があれば
     同様に反映する（backlog 以外に PJ 側の台帳があればそれも）。
   - **書き方**（3 点セット）:
     - `- [ ]` → `- [x]` にし、**根拠を併記する**——works slug ＋ PR/コミット参照 ＋
       **リポジトリ内で裏が取れるもの**（ファイル:行・実測値）。参照だけだと後から辿るのに
       トラッカーが要る。実測値がある項目は数値を書く（次に測る人が基準線を持てる）。
     - 起票当時の記述が**事実と食い違うなら取り消し線で残す**（消さない）。
       手法や経緯の記録は残す価値があるので、**誤解を招く事実主張だけ**を消す。
     - 一部だけ済んだ項目は**割る**。`- [x]`（済んだ分）と `- [ ]`（残り）を**兄弟として並べる**
       ——インデントした子は `aidev status` の件数（行頭 `- [ ]`）に入らず、残作業が集計から消える。
   - **なぜ必須か**: `aidev-util-batch` は消化した行を自動で `[x]` にするが、**直接入口
     （`aidev-00-start` で backlog 項目を選ぶ）は誰も `[x]` にしない**。閉じ忘れると
     **次に着手する人が完了済みの項目を選ぶ**（2026-08-01 に実際に発生。着手して初めて
     5 日前に完了済みと分かり、同時に 7 件の閉じ忘れが見つかった）。
   - **機械的強制**: `backlog:` を持つ work は、**その backlog ファイルに自分の slug が現れないと
     `aidev verify` が FAIL する**（手順 5 の着地前ゲートで弾かれる）。刻印の無い work は従来どおり。
   - **消し込んだ結果そのファイルが全消化になったら `aidev backlog archive` を実行する**
     （`split`/`topic` のみ退避される。`standing` は対象外なので、そのまま実行して構わない）。
     移動は `mv` だけなので、**同じコミットに含める**こと（`git add -A .aidev/backlog`）。
4. チケット連携があれば PR に紐付ける（`state.yml` の `ticket`（旧 `issue`）を参照）。
   `.aidev/config.yml` の `tracker.type` に応じる（github: `Closes #<番号>` ／ jira・redmine: チケットURL/IDを本文に記載）。
   - PR 本文は PJ の PR 作成 skill があればその体裁に従う。無ければ下記「PR 本文テンプレート」を既定とする。
   - 対象フォルダに `walkthrough.md`（レビューガイド）があれば、その**重要ポイントとリスクを3〜5行に要約**して
     PR 本文の `## レビューガイド` 節に載せ、`walkthrough.md` 自体へのリンクを添える（全文転記はしない）。
5. protocol.md「3. 工程終了プロトコル」に従って終了する。
   - 最終工程のため、遷移確認は `承認して完了` とする。完了後、着地結果（コミット/PR の URL 等）を報告する。
   - **autonomous モード時**（protocol.md「10.」）: コミット→**PR を作成して停止**し、結果を報告する。
     **auto-merge はしない**（マージは人間）。test が未通過なら **draft PR** とし要点を明記する。
   - **着地前ゲート（verify）**: コミット前に `aidev verify` を実行し、PASS（不変条件違反なし）を着地の前提とする。
     違反があれば修正してから着地する（`aidev verify && <commit>` のパターン。`.claude/skills/aidev-docs/bin/README.md`）。
   - **記録順序の注意**: deliver は工程記録（works フォルダ）自体をコミット対象に含めるため、
     deliver の記録（`aidev approve deliver`）は**コミットの直前に行い、同じコミットに含める**。
     コミット後に記録すると、その記録が未コミットで取り残される（後追いコミットが必要になる）。
   - **したがって着地直前の順序は固定**（`verify` の backlog 検査は `approved` に `deliver` が
     入って初めて効くため、この順でないと素通りする）:

     ```
     台帳の同期（手順 3.5）→ 変更規模の計測 → aidev approve deliver → aidev verify → コミット → push/PR
     ```
   - **変更規模の計測**（protocol.md「8.」）: `aidev approve deliver` の直前に、着地する**実装**の規模を
     `git diff --stat HEAD -- . ':!.aidev'` で計測する。**工程成果物（`.aidev/` 配下）は規模に含めない**
     （含めると実装の規模が水増しされ、work 間の比較が壊れる）。
     承認は `aidev approve deliver files_changed=<n> insertions=<n> deletions=<n>`。
     - 事後記録モード（手順 1.5）では、既着地コミットの範囲で計測する
       （`git diff --stat <base>..<着地コミット> -- . ':!.aidev'`）。
     - この値は insights で「規模あたりの手戻り」の分母になる（タスク数は粒度の癖でぶれるため）。
     - **`profile: light` の昇格判定**（protocol.md「11.」）: `files_changed` が上限
       （`.aidev/config.yml` の `lightMaxFiles`、既定 3）を超えていたら light の条件を外れている。
       `aidev escalate` で full に昇格し、`decisions.md` に経緯を残してから着地する
       （`aidev verify` も同じ判定で WARN を出す）。
   - **metrics.yml の必須化**（protocol.md「8.」）: 記録は `aidev`（event/approve）が行い、`metrics.yml`
     不在なら自動生成する（CLI 無し環境は `events:` で生成してから手で追記）。事後記録モードでも同様。
6. **worktree の後始末（並行作業で着手していた場合のみ）**。`protocol-worktree.md` を読む。
   **この工程は PR 作成までで終わり、撤去はマージ後**——マージは人間の仕事なので、その後の撤去も
   人間の判断を待つ（`protocol.md`「1.5」）。
   - **deliver の中で撤去しない**。PR を出した時点で「マージ後に `aidev worktree rm <slug> --delete-branch`
     で撤去できる」ことを**報告に添える**に留める。
   - **撤去の前に push 済みを自分で確かめる**。`worktree rm` は未コミット差分があれば既定で拒否するが、
     **未 push のコミットは検知しない**（`git status --porcelain` は working tree しか見ない）。
     コミットは済んでいるが push していない状態で `--force` を打つと、その作業は失われる。
   - **`--delete-branch` は `git branch -D`（強制削除）**。マージ前に打つとブランチごと消える。
     マージ前に worktree だけ外したいなら**付けない**（worktree が外れ、ブランチは残る）。
   - **autonomous モードでは撤去しない**（PR 作成で停止する以上、マージも撤去も人間の側にある）。

## PR 本文テンプレート（PJ の PR skill が無い場合の既定）

```markdown
## 概要
<何を・なぜ。requirement/spec の要約>

## 変更点
- <主な変更を箇条書き>

## レビューガイド
<walkthrough.md があれば重要ポイント・リスクを3〜5行で要約。詳細は walkthrough.md を参照（リンク）>

## テスト
<test 工程の結果（passed/failed）。draft の場合は未解決点。
 **環境不足で skip された検証があれば「未検証の穴」として明記する**（test 工程からの引き継ぎ。
 例: ローカルに pwsh が無く ps1 パリティが未実行 → CI/該当環境での確認を促す）>

<チケット連携（あれば）: github は `Closes #<番号>` / その他は チケットURL・ID>
```

## 留意点

- コミットメッセージ・PR 本文の体裁は PJ 規約（AGENTS.md・PJ skill）に従う。
  - **フォールバック既定**: PJ にコミット/PR skill が無ければ、コミットは **Conventional Commits**
    （`feat:` / `fix:` / `docs:` 等）、PR 本文は上記テンプレートを用いる。
- **ブランチ対応**: 原則 **1 works（`.aidev/works/<YYYYMMDD-slug>`） = 1 作業ブランチ = 1 PR**。
  既存の作業ブランチがあればそれを使い、無ければ手順どおり切る。
  worktree で着手した work は `aidev worktree add` が `feature/<slug>` を作って**既にその上にいる**ため、
  この規約を最初から満たしている（切り直さない）。
- 破壊的操作（push 等）や外部公開（PR 作成）は、ユーザーの承認を得てから行う。
- **ブランチ前提（PR 運用時）**：PR は作業ブランチからデフォルトブランチへ作成する。
  作業開始時（`aidev-00-start` 手順 4-3）にブランチを用意していない場合、コミット前に
  PJ 規約に沿って作業ブランチを切る（デフォルトブランチへの直接コミットを避ける）。
  worktree で着手した場合は既にブランチ上にいるので不要。
  trunk-based 等ブランチを使わない PJ ではこの限りでない。

## 完了の目安

- 変更がコミットされ、PJ 運用に沿って PR 等で着地している。
- `state.yml` の `approved` に `deliver` が記録されている。
