# 実行モード（autonomous）と plan モード（`protocol.md`「10.」の詳細）

> **読む条件**: `state.yml` が `mode: autonomous` の work／`aidev-util-batch`／plan モードに入るか迷ったとき
> 核となる規約と要約は `protocol.md`「10.」。ここはその詳細（工程ごとの読み込み量を抑えるため切り出し）。

`state.yml` の `mode` で実行モードを選ぶ。新規作業時に決定する（既定 interactive）。

### interactive（既定）
- 各工程末で人間の承認ゲート（「3.」）を通す。自動遷移しない。

### autonomous（夜間自律・PRまで一気通貫）
人間ゲートを置かずに requirements→…→deliver を自律実行し、**PR を出して停止**する。
「ゲートを消す」のではなく「**ゲートを PR（最終レビュー）に集約し、自己チェックを固くする**」モード。

- **requirements**: 起動時に与えられたタスク指示を requirements とする（対話ヒアリングはしない。
  指示が不十分なら autonomous を中止し interactive を促す）。
- **任意工程（research/architecture/walkthrough）**: 推奨ではなく**自律的に採否を決める**。
  発火条件の正典は `protocol.md`「4.5」で、autonomous でもそこを変えない——**条件に当たったら実施、
  当たらなければ実施しない**（「autonomous だから全部やる」ではない。同じ条件から逆の判断が出ないように、
  ここに独自の既定を置かない）。walkthrough は人間の一括レビューを助ける工程なので、
  **PR を出す運用なら条件を満たしやすい**、という程度に読む。
- **承認ゲート**: 自動承認（「3.」の autonomous 分岐）。`humanGates` に指定された工程だけは人間に確認
  （**部分自律**。例: `humanGates: [design]` で方向性の誤り＝最大の手戻り源だけ人間が止める）。
- **終端**: deliver は **PR を作成して停止**する。**auto-merge は禁止**（マージは人間が行う）。
  - **PR を作れない環境**（remote が無い／PJ が PR 運用でない／ユーザーが PR を禁じた）では、
    **作業ブランチへのコミットで停止**し、「どこに何を着地させたか（ブランチ名・コミット）」と
    「人間のレビューが未実施であること」を報告に明記する。ここを書かないと、着地点が無いまま
    手順を埋めようとして**存在しない規約を引用する**（実際に起きた）。
  - この場合 **`review.md` の「PR レビュー（人間）」節は生まれない**。条項・ハーネス改修の効果検証は
    AI の出力だけを材料に回ることになるので、insights はその旨をレポートに明記する
    （`protocol-conventions.md`「効果を判定する」の人間信号の優先はここで効かなくなる）。

### 安全弁（autonomous 必須）
- **テストを硬いゲートに**: test が通らないまま PR を出さない。未解決なら **draft PR** にして要点を報告。
- **ループ上限**: review/test→coding の差し戻しは **`state.yml` の `maxSendBacks`（未指定なら 3）回まで**
  （同一工程あたり）。現在値は `metrics.yml` の当該 phase の `sent_back` イベント件数
  （`by: unapprove` を除く）で判定する。除かないと、一度も失敗していない coding / test が
  上流の取り消しだけで予算を使い切る。
  上限到達後は**差し戻しを続けない**。まず `aidev debug start` で**まっさらなコンテキストへ原因究明を
  委譲する**（「10.」／`protocol-debug.md`）——上限は回数を止めるだけで方向を変えないため。
  デバッグも尽きた（`stop_for_human`）なら**停止し、未解決点を報告して人手に委ねる**
  （test が未通過のままなら deliver は draft PR とする）。
- **予算/時間上限**: 上限到達で停止・報告（無限ループ防止）。
- **記録継続**: モードに関わらず state/metrics/各成果物・walkthrough は残す（朝の一括レビューの証跡）。
- **逸脱記録**: 自律中の重要判断は decisions.md に残す。
- **独立点検**: 人間の目が入らないので、上流4文書は `aidev doccheck`、coding の各タスクは
  `aidev taskcheck` で点検を記録する（`protocol-check.md`「3.3」）。記録が無いまま承認すると
  `verify` が WARN（**致命になるのは上流4文書の欠落だけ**——`--strict` で exit 5）。

### 実行手段（別レイヤ）
autonomous の「夜間に回す」には実行主体が要る（headless 実行 / スケジュール起動でオーケストレーターが
本 skill 群を駆動）。これは harness（プロセス定義）とは別レイヤで用意する。

### plan モードとの関係

plan モードは Write / Edit を禁じるので、成果物を書くのが仕事である**工程を完走することはできない**。
成立するのは **plan モード内で探索して方針の承認を取り、解除してから書く**形だけ。

```
探索（read-only）→ 方針を提案 → 承認 → 解除 → 成果物を書く
```

- **判断基準は 2 つとも満たすとき**。(a) **同じ判断を二度承認しない**——その工程のゲートが
  承認する判断を、**上流のゲートが既に承認済み**なら二重になる（coding は `tasks.md` がそれ）。
  (b) **その工程の成果物が「これから書くコードの実装計画」か**——`ExitPlanMode` の用途規定
  （「Only use this tool when the task requires **planning the implementation steps** of a task that
  requires writing code. For **research** tasks where you're **gathering information** … do NOT use」）。
  **承認を出すのはこのツールだけ**なので、ここが実質の資格条件。`EnterPlanMode`（入口）は
  もっと広いが、**出口の制約で決まる**。**こちらで分類を発明しない**（`DESIGN`「2.」）。
- **この基準は「既存のゲートが機械で止まる」を前提にする**（`guard` の exit code と承認記録）。
  **止まらないゲートしか無い工程・環境では、plan モードは二重化ではなくゲートの実体化になり、
  同じ基準から逆の結論が出る**。判定は 1 つ——**`aidev guard <工程>` が exit≠0 で止まるか**。
  止まるなら機械のゲートがある（`protocol.md`「2.10」が言う「手で同等に」は**人がやる**という
  意味なので、ここでは止まらない側）。**移植のときと、承認ゲートの無い工程を足すときに読み直す**
  （前提の欠落は文面の整合では捕まらない＝**lint で検査できない**）。
- **ただし「入る」に倒れても、下の「承認者がいない工程で入ると抜けられない」が優先する**。
  ゲートの実体化として入る価値があっても、**抜ける人がいなければ工程が完走できない**からで、
  この 3 つは順に見る——(1) 承認者がいるか →(2) 成果物が実装計画か (b) →(3) 二重でないか (a)。
- **入る**: **design・architecture・tasks で方向が複数あるとき**。3 つとも成果物が
  「どう作るか／どんな構造で／どう分けるか」＝**実装計画側**にあり (b) を満たし、
  承認するものが方針／構造／手順と別々なので (a) も満たす。
  ほかに**ハーネス自体の改修**（aidev の対象作業ではない）。
  **`light` 以外で、その工程に承認者がいることが要る**——`autonomous` でも
  `humanGates` に挙がっていれば承認者はいる。**subtask の tasks は除く**（切り方は親の tasks が
  確定済み＝(a) が崩れる。`aidev-30-tasks`「subtask の tasks は split 判定を行わない」）。
- **入らない**: **requirements は「何を・なぜ」で実装計画ではない**（**aidev の `design` は
  「どう作るか」で、他ツールの `design`（要件）とは別物**——この名前のずれで「requirements も
  design と同じ側」と読み違えた事故が実際に起きた。「11.」の表）／**research も (b) で落ちる**
  （`ExitPlanMode` が「gathering information … do NOT use」と名指ししている。**特例は要らない**）／
  coding は実装計画の**実行**で上流の `tasks.md` が承認済み（方針変更は**差し戻し**——metrics に残る）／
  test・review・walkthrough・deliver・retro は判定・指摘・解説・着地・振り返りで実装計画ではない／
  **`aidev-00-start` の三層判定**も実装計画ではない（選ぶが `aidev escalate` で選び直せる）。
- **書く順序**: **plan モードは自前の plan file を持つ**（`ExitPlanMode` は内容を引数に取らず、
  先に書いたファイルから読む）。**探索 → plan file → 承認 → 抜ける → 成果物に清書**の順にする。
  **成果物を先に書いてから入ると plan file が写しになる**（それが「計画を二度書く」）。
- **plan モード中に工程を起動されたら、先に抜けるよう促す**（工程を中途で失敗させない）。
- 「工程内で段階的に確認したい」は **段階レビュー（「3.1」）**が対応する。plan モードとは併用しない。
- **「入れ」と明示する**——「方針を先に固める」のような言い方では丁寧に計画するだけで
  **モードは切り替わらない**（Claude Code は `EnterPlanMode` / `Shift+Tab` / `/plan`。
  持たない環境は `aidev-docs/README.md` の表）。`aidev guard design|architecture|tasks` が該当条件のときだけ促す。
- **承認者がいない工程で入ると、抜けられない**。抜けるのは人間の承認なので、`autonomous` で
  `humanGates` に無い工程は**書き込みが塞がったまま完走できない**（`bypassPermissions` の実行だけは
  ブロック自体が効かず進むが、どちらになるかは起動側の設定次第で work からは見分けられない）。
  CLI はモードを検知できないので、**`autonomous` を回す環境では `defaultMode: plan` にしないこと**。
- **委譲で代用しない**——`permissionMode: plan` の子は `AskUserQuestion` を剥がされ会話履歴も
  見えないので、**plan モードの価値である往復が消える**（`DESIGN`「2.」）。

判断の根拠は `aidev-docs/DESIGN.md`「2.」。


> **plan モードを使った場合も aidev の承認ゲートは省かない。** plan モードは方針、aidev のゲートは
> 文書を承認するもので、対象が違う。
