---
name: aidev-60-review
description: ［aidev 標準工程］aidev の review（レビュー）工程。進行中の aidev 作業の差分を要件・仕様・規約の観点で点検し review.md に記録、指摘があれば coding へ差し戻す。「aidev review」「review 工程」と言われたとき、または前工程から案内されたときに使用する。aidev 作業の無い単発のレビュー依頼では使わない。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Agent]
---

AI 開発ワークフローの **review（レビュー）工程**を実行する。
実装全体を design・要件・コーディング規約の観点で点検する。指摘があれば coding 工程へ差し戻す。
通過後は最終工程 deliver（着地）へ進む。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` と、PJ 固有ルールを読むこと。**

## 前提

- test 工程を通過していること（実装が受け入れ基準を満たしている）。

## 入力

- 変更差分（diff）。
- 対象フォルダの `requirements.md` / `design.md` / `decisions.md`。
- PJ 固有のコーディング規約。

## 出力

- レビュー指摘の一覧（重大度付き）。
- `review.md`（指摘の**内容**をラウンドごとに追記。protocol.md「8.」のフォーマット）。
- 指摘なしの場合もその旨を `review.md` に記録。
- `walkthrough.md`（**要ると判断したときだけ**。work フォルダ直下。下記「レビュー補助」）。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定する。
   `aidev guard review` で前提を検査し、`aidev event review start` を記録する
   （exit≠0＝未充足。目視確認で代替しない。start が無いと所要時間も手戻りも導出できない）。
   - 対象が subtask（state.yml に `parent` あり）か親（統合 review）かを見分ける（`protocol-subtask.md`）。
2. 差分を以下の観点で点検する。**実作業の優先順位は protocol.md「2.5」の三段階**に従う
   （PJ 固有 skill → エージェント組み込みのレビューコマンド → 下記のジェネリック観点）。
   - **組み込みコマンドは「委譲」ではなく「併用」**。カバーできるのは下記のうち
     **正確性・保守性**までで、**要件適合 / 価値適合 / 規約適合は work の文脈（requirements.md /
     design.md / AGENTS.md）を要するため、この工程が自分で見る**。丸ごと任せると観点が3つ落ちる。
   - **レビュー対象を明示的に渡す**。組み込みコマンドは `.aidev/current` を知らないので、
     指定しないと work と無関係な差分（未コミットの別変更など）を見に行くことがある。
   - 出力は**テキストを写し取る前提**で `review.md` に落とす（構造化出力ツールの存在を前提にしない）。
   - **要件適合**: requirements の完了条件（`AC` の各 ID）・design の意図を満たしているか。
     **まず `aidev coverage` を打つ**（tasks 時と同じコマンドを、実装後の `tasks.md` に対してもう一度回す）。
     `ac` 列と `tasks` 列を突き合わせ、**この工程で見るのはコマンドが機械的に出せない側**——
     被覆されている `AC` が「タスクは在るが実装が基準を満たしていない」ものになっていないか、
     coding 中に `tasks.md` へ足したタスクが `AC:` を持たないまま増えていないか。
     **tasks の時と数字が変わっていたら、その差分が design と実装の乖離**（`git diff` で `tasks.md` を見る）。
   - **価値適合**: requirements の `目的 / ゴール`（達成したい状態）とユーザーストーリーの
     「なぜなら（価値）」に照らして、**その変更が本当にその状態をもたらすか**。
     受け入れ基準を満たしていても価値に繋がっていない実装はここで拾う。
   - **正確性**: バグ・エッジケースの取りこぼし・異常系。
   - **規約適合**: PJ のコーディング規約・レビュー観点（AGENTS.md や PJ固有 skill があれば優先）。
   - **保守性**: 重複・複雑さ・命名・周辺コードとの一貫性。
   - **（統合 review のみ）結合**: 単体 review では**原理的に見えない** subtask 横断の不整合だけを見る
     （子で見たことは繰り返さない——二重化して形骸化する）。開くものは 3 つ:
     - **親の `tasks.md`**: 割れ目と producer→consumer の契約が書いてある**唯一の場所**。
       実装がその契約どおりか（引数・戻り値・エラー・呼ぶ順序）。
     - **各子の `test-result.md` の「スキップした検証」**: 子 test は unit・契約モックに限定されるので、
       **結合の穴は必ずここに残る**（`protocol-subtask.md`）。親の統合 test で閉じたかを 1 件ずつ照合し、
       閉じていなければ **must**。
     - **家族全体の diff**: 責務の重複・抜け、横断規約の破れ。
     **`aidev coverage` の読み方も変わる**——分割 work では親の tasks 承認時に子の `tasks.md` がまだ
     無いので、**被覆の基準点を刻まない**（`ac_drift` は `-`）。見るのは「tasks 時と同じ数字か」ではなく
     **今の gap が 0 か**。
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
     - **無効になる後工程の承認を `aidev unapprove` で取り消す**（protocol.md「3.」）。
       review → coding なら **`aidev unapprove test` → `aidev unapprove coding` の順**（後ろから）。
       取り消さないと `approved` に test/coding が残ったまま coding をやり直すことになり、
       state が実態と食い違う。取り消しても記録は消えない（`by: unapprove` 付きで残り、
       差し戻し回数には数えない）。
     - そのうえで coding を**再開する際は `aidev event coding start` を記録する**（さもないと手戻り回数を取りこぼす。protocol.md「3.」「8.」）。
     - **`maxSendBacks`（既定 3）に達したら `aidev debug start`**——まっさらなコンテキストに
       原因究明だけを委譲する（`protocol-debug.md`）。同じコンテキストで回し続けない。
     - **統合 review の差し戻し先（protocol.md「2.8」＋ `protocol-subtask.md`）**: 結合起因の指摘は**原因となった subtask の coding** へ
       戻す。**まず親で `aidev event review sent_back`** を打ってから `aidev use <親>/<NN>-<subslug>`
       （親の `activeSubtask` も同期される）→ **`aidev unapprove review` → `unapprove test` →
       `unapprove coding`**（上の通常経路と同じく後ろから。`review` だけ取り消すと
       `approved` に test/coding が残ったまま coding をやり直すことになり、この節が
       禁じている状態そのものになる）→ `aidev event coding start`。これで
       再 coding→test→review 後の `approve review` が再びカーソルを前進させられる（D と整合）。
       再 split（親 tasks 戻し）は避け、最小手戻りにする。
   - **指摘なし（または nit のみ）** → protocol.md「3. 工程終了プロトコル」に従って終了する。
     - **subtask の review** なら `aidev approve review` の時点で CLI がカーソルを自動前進させる
       （出力 `cursor: …` で遷移先を確認する）。
     - 終了前に**レビュー補助の要否を判定する**（下記「レビュー補助」）。次工程は常に `deliver`。
5. 承認は `aidev approve review must=<件数> should=<件数> nit=<件数>`（protocol.md「3.」「8.」）。
   **件数は work 全体の合計**（全ラウンドの通算）——`approve review` は最後に 1 回しか打たないので、
   最終ラウンドの 0 件を刻むと「差し戻したのに指摘 0 件」という読めない記録になる。
   ラウンドごとの分布を残したいときは `review.md` 本文に書く（metrics のキーは増やさない）。
   **被覆メトリクスは CLI が自動で刻む**ので手で渡さない。tasks 時の刻印と対になり、
   `aidev metrics` の `ac_drift`（tasks 以降に増えた gap ＝ design と実装の乖離）になる。

## light の昇格トリガ

`profile: light`（protocol.md「11.」）で **`must` の指摘が出たら、上流を薄くしたことが原因である
可能性が高い**。coding へ差し戻す前に `aidev escalate` で full へ昇格する。`should` / `nit` だけなら
light のまま続けてよい。

なお **light でも入力に `requirements.md` は存在する**（薄いが必須節は埋まっている）。
節が足りずレビュー観点を確認できない場合も、昇格の合図として扱う。

## レビュー補助（`walkthrough.md`）

**人間の PR レビューを助ける解説**。**工程ではなく、この工程の任意の成果物**——差分を読むだけで
分かる変更に解説は要らないし、書くこと自体が作業段階でもない。以前は 65 番の独立した任意工程だったが、
**遷移ゲートを1つ消費して「やる/やらない」を尋ねるだけ**の工程になっていた。

**要否の3条件（ここが正典）**。いずれかに当たれば書く。当たらなければ書かない。
- 差分が大きい（変更ファイル数・行数が多く全体像を掴みにくい）
- 複数モジュールを横断する——**protocol.md「4.5」の architecture 条件1と同じ但し書き**
  （触ったファイル数では読まない。見るのは責務や依存の向きが跨いでいるか）
- 処理フローが複雑（非自明な制御フロー・状態遷移・トリッキーな実装）

**interactive** は判定結果を理由付きでユーザーに示し、不要と言われたら書かない。
**autonomous** は自分で決める（`protocol-autonomous.md`）。`profile: light` では書かない。
**書くのは must/should 解消後の確定コードに対して**（差し戻し前に書くと説明とコードがずれる）。
広い差分の読解はサブエージェントに委譲してよい。

```markdown
# レビューガイド: <タイトル>
## 変更概要 / 目的       <requirements/design の要約>
## 重要ポイント          <非自明な実装・設計判断。decisions.md があればリンク>
## 処理フロー            <mermaid（flowchart / sequenceDiagram 等）>
## 主要な変更箇所        <`path/to/file.ts:42` — その変更の要点>
## リスク / 確認したい点  <判断を仰ぎたい点・既知の制限>
```

- **コードの全再掲はしない**。自明な変更を逐次解説しない。レビュアーの時間を節約する
  「非自明点・リスク・全体像」に絞り、図と要点で「どこを・なぜ見るか」を示す。
- 該当コードは **`path:line`** で指す（クリックで飛べる形）。

## 完了の目安

- must/should の指摘が解消されている。
- 変更が requirements・design・規約に整合している。
- **`aidev coverage` が tasks 承認時と同じ被覆を示している**（gap が増えていない。増えていれば、
  coding 中に design と実装が乖離した箇所がそこにある）。
