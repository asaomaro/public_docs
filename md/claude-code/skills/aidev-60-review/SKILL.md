---
name: aidev-60-review
description: ［aidev 標準工程］aidev の review（レビュー）工程。進行中の aidev 作業の差分を要件・仕様・規約の観点で点検し review.md に記録、指摘があれば coding へ差し戻す。「aidev review」「review 工程」と言われたとき、または前工程から案内されたときに使用する。aidev 作業の無い単発のレビュー依頼では使わない。
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
   `aidev guard review` で前提を検査する（exit≠0＝未充足。目視確認で代替しない）。
   - 対象が subtask（state.yml に `parent` あり）か親（統合 review）かを見分ける（`protocol-subtask.md`）。
2. 差分を以下の観点で点検する。**実作業の優先順位は protocol.md「2.5」の三段階**に従う
   （PJ 固有 skill → エージェント組み込みのレビューコマンド → 下記のジェネリック観点）。
   - **組み込みコマンドは「委譲」ではなく「併用」**。カバーできるのは下記のうち
     **正確性・保守性**までで、**要件適合 / 価値適合 / 規約適合は work の文脈（requirement.md /
     spec.md / AGENTS.md）を要するため、この工程が自分で見る**。丸ごと任せると観点が3つ落ちる。
   - **レビュー対象を明示的に渡す**。組み込みコマンドは `.aidev/current` を知らないので、
     指定しないと work と無関係な差分（未コミットの別変更など）を見に行くことがある。
   - 出力は**テキストを写し取る前提**で `review.md` に落とす（構造化出力ツールの存在を前提にしない）。
   - **要件適合**: requirement の完了条件（`AC` の各 ID）・spec の意図を満たしているか。
     **まず `aidev coverage` を打つ**（plan 時と同じコマンドを、実装後の `tasks.md` に対してもう一度回す）。
     `ac` 列と `tasks` 列を突き合わせ、**この工程で見るのはコマンドが機械的に出せない側**——
     被覆されている `AC` が「タスクは在るが実装が基準を満たしていない」ものになっていないか、
     coding 中に `tasks.md` へ足したタスクが `AC:` を持たないまま増えていないか。
     **plan の時と数字が変わっていたら、その差分が spec と実装の乖離**（`git diff` で `tasks.md` を見る）。
   - **価値適合**: requirement の `目的 / ゴール`（達成したい状態）とユーザーストーリーの
     「なぜなら（価値）」に照らして、**その変更が本当にその状態をもたらすか**。
     受け入れ基準を満たしていても価値に繋がっていない実装はここで拾う。
   - **正確性**: バグ・エッジケースの取りこぼし・異常系。
   - **規約適合**: PJ のコーディング規約・レビュー観点（AGENTS.md や PJ固有 skill があれば優先）。
   - **保守性**: 重複・複雑さ・命名・周辺コードとの一貫性。
   - **（統合 review のみ）結合**: subtask 間の契約整合・結線・統合 test の通過。単体 review では見えない
     subtask 横断の不整合を重点的に見る。
3. 指摘を重大度（must / should / nit）と**条項参照タグ**付きで一覧化し、`review.md` に当該ラウンドとして
   追記する（フォーマットは protocol.md「8.」）。
   - **条項参照タグ `[conv:<id>]`**: その指摘の根拠となる PJ規約の条項 id を付す。候補は
     `aidev convention status` が出す一覧（＝分類の語彙を新しく発明しない）。該当が無ければ **`[conv:-]`**。
   - PJ に条項がまだ無い（`.aidev/conventions/` が空）なら全て `[conv:-]` でよい。それ自体が最初の材料になる。
   - **coding のタスク点検（`protocol-check.md`）で既に直された指摘は再掲しない**。`review.md` の
     「タスク点検ログ」節は読んでよい（同じ箇所が再発していないかの手掛かりになる）が、
     **その件数を `must` / `should` / `nit` に数えない**——点検で潰れた欠陥は工程に到達しておらず、
     ラウンド指摘とは母集団が違う（protocol.md「8.」）。
4. 判定に応じて分岐する。
   - **must/should の指摘あり** → `aidev event review sent_back` を記録のうえ coding 工程への
     差し戻しを提案する（protocol.md「4. 番号と順序」に基づく正当な遷移）。
     coding を**再開する際は `aidev event coding start` を記録する**（さもないと手戻り回数を取りこぼす。protocol.md「3.」「8.」）。
     - **統合 review の差し戻し先（protocol.md「2.8」＋ `protocol-subtask.md`）**: 結合起因の指摘は**原因となった subtask の coding** へ
       戻す。`aidev use <親>/<NN>-<subslug>`（親の `activeSubtask` も同期される）→
       **`aidev unapprove review`**（完了を取り消す。記録は `sent_back` として残る）→ `aidev event coding start`。これで
       再 coding→test→review 後の `approve review` が再びカーソルを前進させられる（D と整合）。
       再 split（親 plan 戻し）は避け、最小手戻りにする。
   - **指摘なし（または nit のみ）** → protocol.md「3. 工程終了プロトコル」に従って終了する。
     - **subtask の review** なら `aidev approve review` の時点で CLI がカーソルを自動前進させる
       （出力 `cursor: …` で遷移先を確認する）。
     - **親の統合 review** なら **複雑度の自己評価（walkthrough 推奨判定）**: protocol.md「4.5」の walkthrough の
       3条件に該当すれば、遷移ゲートに `承認して walkthrough(任意) を挟む`（推奨）を加え理由を添える
       （次工程: 推奨時 `walkthrough`、それ以外 `deliver`）。
5. 承認は `aidev approve review must=<件数> should=<件数> nit=<件数>`（protocol.md「3.」「8.」）。

## light の昇格トリガ

`profile: light`（protocol.md「11.」）で **`must` の指摘が出たら、上流を薄くしたことが原因である
可能性が高い**。coding へ差し戻す前に `aidev escalate` で full へ昇格する。`should` / `nit` だけなら
light のまま続けてよい。

なお **light でも入力に `requirement.md` は存在する**（薄いが必須節は埋まっている）。
節が足りずレビュー観点を確認できない場合も、昇格の合図として扱う。

## 完了の目安

- must/should の指摘が解消されている。
- 変更が requirement・spec・規約に整合している。
- **`aidev coverage` が plan 承認時と同じ被覆を示している**（gap が増えていない。増えていれば、
  coding 中に spec と実装が乖離した箇所がそこにある）。
