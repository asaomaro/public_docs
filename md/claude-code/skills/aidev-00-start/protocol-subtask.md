# サブタスク分割（subtask 層・schema 3）（`protocol.md`「2.8」の詳細）

> **読む条件**: plan で split 判定をするとき / `state.yml` に `parent` がある work（subtask）の plan・coding・test・review。
> 核となる規約と要約は `protocol.md`「2.8」。ここはその詳細を切り出したもの
> （工程ごとの読み込み量を抑えるため。`protocol.md`「0.」の付録一覧を参照）。


**高結合で 1 PR には割れないが大規模な work** を、1 PR を保ったまま内部で漸進的に実装・レビューする仕組み。
split 判定の3層決定木（`aidev-docs/DESIGN.md`「5.」）の中段に当たる。**割るかは plan で判定する**
（interactive=ユーザーに委譲 / autonomous=自律判定。`aidev-30-plan` 参照）。

- **フォルダ**: `works/<親>/<NN>-<subslug>/`（`NN`=2桁連番、`subslug`=kebab-case。date prefix なし）。
  生成は `aidev new <NN>-<subslug> --parent <親>`。子 state.yml（`parent` 付き・`current: plan`）を作り、
  親 state.yml の `subtasks` に追記、`activeSubtask` 未設定なら当該子を活性にする。
- **工程レイヤリング**:
  - **親**: requirement → research → spec → design → plan（=split 判定）→ 〔subtask 群〕→ **統合 test →
    統合 review** → walkthrough → deliver → retro。
  - **子（subtask）**: **plan → coding → test → review** の独立サイクル。子は親の spec/design を継承し
    plan から始める（子は spec/design を持たない）。子 plan は **scope を再決定しない**（割れ目は親 plan が凍結済み。
    tasks.md 分解と dependsOn 順序付けに限定）。子 test は **単独検証可能な範囲（unit・契約モック）に限定**し、
    結合検証は親統合 test に集約する。
- **カーソル**: `.aidev/current` が親工程中は `<親>`、subtask 実行中は `<親>/<NN>-<subslug>` を指す。
  `aidev`（event/approve/guard/verify）はこのパスが指す対象（親 or 子）に作用する。
  **subtask の `aidev approve review` でカーソルは自動前進する**（手動操作不要）: 親 `subtasks` の次の未完
  （= `review` 未承認の）子へ `activeSubtask` と `.aidev/current` を進め、全完了なら `activeSubtask=done` にして
  `.aidev/current` を親へ戻す（→ 親の統合 test へ）。CLI が `cursor: …` を出力する。
- **依存**: 子は同一親内の兄弟 subtask を **bare 名（`01-backend`）** で `dependsOn` に書ける
  （producer→consumer 順。「2.7」の充足判定で、兄弟 subtask は **review 承認**を完了とみなす）。
- **差し戻し**: 親の統合 review で結合起因の must/should が出たら、**該当 subtask の coding へ差し戻す**
  （`aidev event review sent_back` → 該当子で `aidev event coding start`）。`maxSendBacks` は親・子それぞれの
  `sent_back` 件数で独立に判定する。
- **小〜中規模 work では使わない**。spec＋plan で 1 PR に収まるなら subtask 化しない（過剰分割の禁止）。
- **機械的強制（CLI guard）**: 「同じ skill が親/子で走る」ことに起因する誤用は `aidev` CLI が弾く（散文に頼らない）。
  - **subtask の工程は plan/coding/test/review のみ**。subtask に対し `requirement/research/spec/design/walkthrough/
    deliver/retro` を `aidev guard` すると **exit 2** で拒否される（これらは親 work 専用）。
  - **多段ネスト禁止（単層のみ）**: `aidev new <NN>-<subslug> --parent <親>` の `<親>` が既に subtask なら拒否する
    （doctor のネスト横断・兄弟依存解決・activeSubtask は1段ネスト前提のため）。
  - **subtask の plan は split 判定をしない**（再分割禁止）。plan skill が `parent` の有無で分岐する（`aidev-30-plan`）。
