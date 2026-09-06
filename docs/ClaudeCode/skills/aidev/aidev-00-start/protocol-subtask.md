# サブタスク分割（subtask 層・schema 3）（`protocol.md`「2.8」の詳細）

> **読む条件**: tasks で split 判定をするとき / `state.yml` に `parent` がある work（subtask）の tasks・coding・test・review。
> 核となる規約と要約は `protocol.md`「2.8」。ここはその詳細を切り出したもの
> （工程ごとの読み込み量を抑えるため。`protocol.md`「0.」の付録一覧を参照）。


**高結合で 1 PR には割れないが大規模な work** を、1 PR を保ったまま内部で漸進的に実装・レビューする仕組み。
split 判定の3層決定木（`aidev-docs/DESIGN.md`「5.」）の中段に当たる。**割るかは tasks で判定する**
（interactive=ユーザーに委譲 / autonomous=自律判定。`aidev-30-tasks` 参照）。

- **フォルダ**: `works/<親>/<NN>-<subslug>/`（`NN`=2桁連番、`subslug`=kebab-case。date prefix なし）。
  生成は `aidev new <NN>-<subslug> --parent <親>`。子 state.yml（`parent` 付き・`current: tasks`）を作り、
  親 state.yml の `subtasks` に追記、`activeSubtask` 未設定なら当該子を活性にする。
- **工程レイヤリング**:
  - **親**: requirements → research → design → architecture → tasks（=split 判定）→ 〔subtask 群〕→ **統合 test →
    統合 review** → deliver → retro。
  - **子（subtask）**: **tasks → coding → test → review** の独立サイクル。子は親の design/architecture を継承し
    tasks から始める（子は design/architecture を持たない）。子 tasks は **scope を再決定しない**（割れ目は親 tasks が凍結済み。
    tasks.md 分解と dependsOn 順序付けに限定）。子 test は **単独検証可能な範囲（unit・契約モック）に限定**し、
    結合検証は親統合 test に集約する。**子も自分の `test-result.md` を持つ**（`verify` が
    schema 6 で実在を検査する。親から継承しない——子 test と親統合 test は検証範囲が別なので、
    片方の結果でもう片方を代弁できない）。
- **カーソル**: `.aidev/current` が親工程中は `<親>`、subtask 実行中は `<親>/<NN>-<subslug>` を指す。
  `aidev`（event/approve/guard/verify）はこのパスが指す対象（親 or 子）に作用する。
  **subtask の `aidev approve review` でカーソルは自動前進する**（手動操作不要）: 親 `subtasks` の次の未完
  （= `review` 未承認の）子へ `activeSubtask` と `.aidev/current` を進め、全完了なら `activeSubtask=done` にして
  `.aidev/current` を親へ戻す（→ 親の統合 test へ）。CLI が `cursor: …` を出力する。
- **依存**: 子は同一親内の兄弟 subtask を **bare 名（`01-backend`）** で `dependsOn` に書ける
  （producer→consumer 順。「2.7」の充足判定で、兄弟 subtask は **review 承認**を完了とみなす）。
- **差し戻し**: 親の統合 review で結合起因の must/should が出たら、**該当 subtask の coding へ差し戻す**
  （親で `aidev event review sent_back` → `aidev use <親>/<子>` → 子で `aidev unapprove review` →
  `aidev event coding start`。親の `activeSubtask` は `unapprove` がその子へ戻す）。`maxSendBacks` は親・子それぞれの
  `sent_back` 件数で独立に判定する。
- **被覆（`aidev coverage`）は家族単位**: 子は親の `requirements.md` を継承するので、**受け入れ基準の被覆は
  親＋全 subtask をまとめて**見る（親から打っても子から打っても同じ表が出る。子のタスク ID には
  `01-front/T1` のように subslug が前置される）。子1本だけで測ると、兄弟が担当する `AC` が必ず
  「タスクが無い」になり**誰にも直せない gap** が残るため。tasks 未実施の subtask が残っている間は
  cover の穴を致命にしない（最初の子の tasks が、兄弟の担当ぶんまで背負って通らなくなる）。
  一方 `依存:` の整合（未定義参照・循環）は **各 `tasks.md` の中**で見る（依存は子の中で閉じる）。
- **小〜中規模 work では使わない**。design＋tasks で 1 PR に収まるなら subtask 化しない（過剰分割の禁止）。
- **機械的強制（CLI guard）**: 「同じ skill が親/子で走る」ことに起因する誤用は `aidev` CLI が弾く（散文に頼らない）。
  - **subtask の工程は tasks/coding/test/review のみ**。subtask に対し `requirements/research/design/architecture/
    deliver/retro` を `aidev guard` すると **exit 2** で拒否される（これらは親 work 専用）。
  - **多段ネスト禁止（単層のみ）**: `aidev new <NN>-<subslug> --parent <親>` の `<親>` が既に subtask なら拒否する
    （doctor のネスト横断・兄弟依存解決・activeSubtask は1段ネスト前提のため）。
  - **subtask の tasks は split 判定をしない**（再分割禁止）。tasks skill が `parent` の有無で分岐する（`aidev-30-tasks`）。
