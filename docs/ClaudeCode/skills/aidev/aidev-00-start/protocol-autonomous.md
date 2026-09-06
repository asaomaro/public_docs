# 実行モード（autonomous）と plan モード（`protocol.md`「10.」の詳細）

> **読む条件**: `state.yml` が `mode: autonomous` の work／`aidev-util-batch`／plan モードを使うか迷ったとき（start・spec・design）
> 核となる規約と要約は `protocol.md`「10.」。ここはその詳細（工程ごとの読み込み量を抑えるため切り出し）。

`state.yml` の `mode` で実行モードを選ぶ。新規作業時に決定する（既定 interactive）。

### interactive（既定）
- 各工程末で人間の承認ゲート（「3.」）を通す。自動遷移しない。

### autonomous（夜間自律・PRまで一気通貫）
人間ゲートを置かずに requirement→…→deliver を自律実行し、**PR を出して停止**する。
「ゲートを消す」のではなく「**ゲートを PR（最終レビュー）に集約し、自己チェックを固くする**」モード。

- **requirement**: 起動時に与えられたタスク指示を requirement とする（対話ヒアリングはしない。
  指示が不十分なら autonomous を中止し interactive を促す）。
- **任意工程（research/design/walkthrough）**: 推奨ではなく**自律的に採否を決める**。
  発火条件の正典は `protocol.md`「4.5」で、autonomous でもそこを変えない——**条件に当たったら実施、
  当たらなければ実施しない**（「autonomous だから全部やる」ではない。同じ条件から逆の判断が出ないように、
  ここに独自の既定を置かない）。walkthrough は人間の一括レビューを助ける工程なので、
  **PR を出す運用なら条件を満たしやすい**、という程度に読む。
- **承認ゲート**: 自動承認（「3.」の autonomous 分岐）。`humanGates` に指定された工程だけは人間に確認
  （**部分自律**。例: `humanGates: [spec]` で方向性の誤り＝最大の手戻り源だけ人間が止める）。
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
  (b) **方向が複数あり、選び損なうと成果物ごと無駄になる**——これは `EnterPlanMode` 自身の
  WHEN TO USE（「Multiple Valid Approaches」「Architectural Decisions」「User Preferences Matter」）と
  WHEN NOT TO USE（「the user has given very specific, detailed instructions」＝方向が決まっている）
  をそのまま当てたもの。**こちらで分類を発明しない**——3 回発明して 3 回とも外した（`DESIGN`「2.」）。
- **この基準は「既存のゲートが機械で止まる」を前提にする**（`guard` の exit code と承認記録）。
  **止まらないゲートしか無い工程・環境では、plan モードは二重化ではなくゲートの実体化になり、
  同じ基準から逆の結論が出る**。判定は 1 つ——**`aidev guard <工程>` が exit≠0 で止まるか**。
  止まるなら機械のゲートがある（`protocol.md`「2.10」が言う「手で同等に」は**人がやる**という
  意味なので、ここでは止まらない側）。**移植のときと、承認ゲートの無い工程を足すときに読み直す**
  （前提の欠落は文面の整合では捕まらない＝**lint で検査できない**）。
- **ただし「入る」に倒れても、下の「承認者がいない工程で入ると抜けられない」が優先する**。
  ゲートの実体化として入る価値があっても、**抜ける人がいなければ工程が完走できない**からで、
  この 3 つは順に見る——(1) 承認者がいるか →(2) 上流が方向を固めていないか →(3) 選び損なうと無駄か。
- **入る**: **上流4工程（requirement / spec / design / plan）で方向が複数あるとき**。
  どれも「何を／どう／どんな構造で／どう分けるか」を**選ぶ**工程で、選び損なうと文書ごと無駄になる。
  ほかに**ハーネス自体の改修**（aidev の対象作業ではない）。
  **`light` 以外で、その工程に承認者がいることが要る**——`autonomous` でも
  `humanGates` に挙がっていれば承認者はいる。**subtask の plan は除く**（切り方は親の plan が
  確定済み＝(a) が崩れる。`aidev-30-plan`「subtask の plan は split 判定を行わない」）。
- **入らない**: coding は上流の `tasks.md` が方向を固めている（(a) が崩れる。方針変更は
  **差し戻し**——metrics に残る）／**test・review・walkthrough・deliver・retro は
  観測して報告する工程**で、方向を選ばない（(b) が崩れる。**コードを読むかどうかは関係ない**——
  これらもコードを読む）／**`aidev-00-start` の三層判定**は選ぶが**選び直せる**
  （`aidev escalate` がある）ので (b) が崩れる／**research は plan モード自身が外している**
  （`EnterPlanMode` の WHEN NOT TO USE:「Pure research/exploration tasks
  (**use the Agent tool instead**)」＝「2.6」の委譲と同じ）。
- **plan モード中に工程を起動されたら、先に抜けるよう促す**（工程を中途で失敗させない）。
- 「工程内で段階的に確認したい」は **段階レビュー（「3.1」）**が対応する。plan モードとは併用しない。
- **「入れ」と明示する**——「方針を先に固める」のような言い方では丁寧に計画するだけで
  **モードは切り替わらない**（Claude Code は `EnterPlanMode` / `Shift+Tab` / `/plan`。
  持たない環境は `aidev-docs/README.md` の表）。`aidev guard` が上流4工程で該当条件のときだけ促す。
- **承認者がいない工程で入ると、抜けられない**。抜けるのは人間の承認なので、`autonomous` で
  `humanGates` に無い工程は**書き込みが塞がったまま完走できない**（`bypassPermissions` の実行だけは
  ブロック自体が効かず進むが、どちらになるかは起動側の設定次第で work からは見分けられない）。
  CLI はモードを検知できないので、**`autonomous` を回す環境では `defaultMode: plan` にしないこと**。
- **委譲で代用しない**——`permissionMode: plan` の子は `AskUserQuestion` を剥がされ会話履歴も
  見えないので、**plan モードの価値である往復が消える**（`DESIGN`「2.」）。

判断の根拠は `aidev-docs/DESIGN.md`「2.」。


> **plan モードを使った場合も aidev の承認ゲートは省かない。** plan モードは方針、aidev のゲートは
> 文書を承認するもので、対象が違う。
