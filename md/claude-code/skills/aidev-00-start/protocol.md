# 開発ワークフロー共通プロトコル

すべての `aidev-*` 工程 skill が従う共通規約。この harness は `.claude/skills/aidev-*` だけで
自己完結し、PJ 固有ファイル（AGENTS.md / CLAUDE.md / docs 等）には依存しない。

各工程 skill は開始時にこのファイル（`../aidev-00-start/protocol.md`）を読み、ここの規約に従う。

## 0. 構成と運用方針

- harness 本体（番号付きパイプライン）: `.claude/skills/aidev-00-start/` 〜 `aidev-95-retro/`（任意工程 research/design/walkthrough/retro を含む）
  - パイプライン外ユーティリティ: `aidev-util-propose` / `aidev-util-batch` / `aidev-util-insights`（番号なし・`aidev-util-*` で名前空間を分離）
  - ランタイムガード（skill ではない）: `aidev` CLI（`.claude/skills/aidev-docs/bin/aidev`＝POSIX sh / `.claude/skills/aidev-docs/bin/aidev.ps1`＝Windows PowerShell）。
    state/metrics 更新と前提・不変条件検査の単一経路。詳細は `.claude/skills/aidev-docs/bin/README.md`
  - `aidev-00-start/protocol.md`: この共通プロトコル（定義のホーム）
  - 各工程の手順は、その工程の `SKILL.md` 内にインラインで定義する
- 実行時状態: `.aidev/`（リポジトリ内に生成）
  - `.aidev/current`: 現在作業中の works フォルダ名（ポインタ）
  - `.aidev/works/<YYYYMMDD-slug>/`: 作業単位ごとのフォルダ。成果物と `state.yml` を格納
    - 命名規約: **`<YYYYMMDD>-<slug>`**。日付プレフィックスは `date -u +%Y%m%d`（UTC）。
      slug は kebab-case・英小文字。同日・同 slug が既存なら末尾に `-2`,`-3`… を付けて一意化する。
      （日付プレフィックスは時系列ソート・可読性・並行作成時の衝突回避を両立する）

### 運用方針（推奨）

- 迷ったとき・再開時は `aidev-00-start` から始めるのを推奨する。
- ただし各工程 skill は単独でも実行できる（このプロトコルを自身で参照し、前提を自己チェックする）。
  慣れた利用者は `/aidev-40-coding` のように直接工程を叩いてもよい。

## 1. 対象作業の特定

- 各工程は開始時に `.aidev/current` を読み、対象の works フォルダを確定する。
- `.aidev/current` が無い、または指す先が存在しない場合は工程を実行せず、`aidev-00-start` を案内する。
- 対象確定後、`aidev event <工程> start` で **start イベント**を記録する（CLI が `metrics.yml` を自動生成・追記。「8.」）。

## 1.5 並行作業（worktree・ユーザー責任の任意機能）

複数の作業を**並行**で進めたいとき、ユーザーは `aidev worktree`（CLI。`bin/README.md` 参照）で work 専用の
git worktree＋`feature/<slug>` ブランチを作って隔離着手できる。ハーネスは並列化を自動判断せず、
**並列の要否はユーザーが明示 `aidev worktree add` で判断する**（人間オプトインの逸脱。既定は単一ワーキングツリーの直列）。

- **current は worktree ローカル**: `.aidev/current` は `.gitignore` 対象＝未追跡のため、各 worktree が独立した
  current を持ち、worktree 間で共有されない。よって **worktree 操作は main tree の `.aidev/current` を書き換えない（INV-1）**。
- **1 worktree = 1 branch = 1 work** を単位とする。`worktree add` は worktree 内に該当 slug の work が無ければ `new` を
  委譲し（add 内で new）、有れば current 設定のみ行う。
- **既存 work の継続は要コミット**: work 成果物（`works/*`）は追跡対象なので、別ブランチの worktree で継続するには
  その work がコミット済みでブランチに乗っている必要がある（未コミットの work フォルダは worktree に伝播しない）。
- **規約**: worktree 上の作業が共有ファイル（`package.json` contributes・`fileScope.ts`・言語登録）に及ぶ場合の
  languageId 波及（AGENTS.md）と、原典照合の主エージェント実施義務は、並行作業でも変わらず適用される
  （`worktree add` 完了時に CLI が注意を出力する）。

## 2. 前提チェック

- 工程番号の順序ではなく、必要な成果物ファイルの有無で開始可否を判断する。
- 前提成果物が無ければ実行を中止し、不足している前工程を提示する。
- 各工程の前提成果物は、その工程 skill に記載する。
- **`aidev guard <工程>`** を実行し、前提成果物・前提工程の承認・`dependsOn`（「2.7」）の充足を
  機械的に検査する（exit≠0＝未充足。code 2=成果物/工程不足・3=依存未充足）。未充足時の扱いは「2.7」の soft 方針に従う。

## 2.5 PJ資産の優先（実作業の委譲）

この harness は開発フローの制御と進捗管理に責任を持ち、実作業の「やり方」は
可能な限りプロジェクト(PJ)固有の資産に委ねる。各工程は実作業に入る前に次を確認する。

- **規約・観点（知識）**：PJ のルール（AGENTS.md 等、エージェントが自動読込する指示）が
  あれば、それを当該工程の判断基準として優先する。
- **実行可能な skill / コマンド**：その工程に関連する PJ固有 skill やコマンドが存在すれば、
  それを優先して実作業に用いる（例: review→PJのレビュー skill、test→PJのテストコマンド、
  完了時のコミット/PR→PJの該当 skill）。
- いずれも無ければ、各工程 skill のジェネリック手順にフォールバックする。
- 採用の有無にかかわらず、ゲート・state 記録・遷移の制御は常に基盤(protocol)が担う。
- PJ 側の事前宣言・設定は不要。存在すれば自動的に優先する。

## 2.6 重い工程の委譲（任意・指示ベース）

重く対話の少ない工程は、サブエージェントに委譲してよい。委譲は特定ツールに依存させず、
「サブエージェントに委譲する」という意図として扱い、各エージェントが自身の機構で実現する。

- **委譲してよい工程**：coding / test / review など、重く対話の少ない工程。
  委譲先は対象 works フォルダ（`.aidev/works/<YYYYMMDD-slug>/`）を読み書きし、結果サマリを返す。
  これにより主エージェントの context を圧迫しない。
- **委譲しない工程**：requirement はユーザーとの対話が必要なため委譲しない。
- **委譲しない検証（重要）**：**外部ソース／一次資料との照合を伴う検証（原典準拠のレビュー等）は
  サブエージェントに委譲しない**。委譲先のツール権限（ネットワーク取得・Bash 等）が落ちると照合不能となり、
  知識ベースの幻覚的な指摘を量産して判断を誤らせる。この種の検証は**主エージェントが一次ソースを直読**して
  行う（要約や grep の取りこぼしにも注意し、確定は生テキストの直読で行う）。
  ※ 一次資料を要しない範囲（スキーマ整合・内部一貫性）の点検は委譲してよい。
- **委譲できないもの（不変条件）**：承認ゲート・遷移・state 記録は、委譲の有無にかかわらず
  必ず主エージェントが担う。サブエージェントは自律実行して結果を返すだけで、実行中に
  ユーザーへ対話的承認を求められないため。
- **フォールバック**：委譲機構を持たないエージェントでは、同一セッションでインライン実行する
  （挙動は同一）。委譲は最適化手段であり、必須ではない。

> Claude Code での実現: 各工程 skill の `allowed-tools` に `Agent` を含めることで委譲を可能にしている。
> 他エージェントでは各自の委譲機構を用いる（無ければインライン実行）。

## 2.7 作業間依存（dependsOn）の前提チェック

作業（works）が他の作業/issue に依存する場合、`state.yml` の `dependsOn`（「6.」）に記録する。
依存を**1か所（state.yml）に集約**することで、batch・手動・`/aidev-40-coding` 直叩きのいずれの入口でも
一律に効く（backlog 等への個別注記は不要）。各工程は開始時（「1. 対象作業の特定」の後）に評価する。

- **充足判定**:
  - works slug（例 `20260620-rpg-dialect-split`）→ 当該 works の `state.yml` の `approved` に `deliver` が含まれる
    （ツール非依存で最も推奨。依存解決を外部トラッカーに縛らない）。
  - 外部チケット（例 `#18` / `PROJ-123`）→ そのチケットがクローズ／完了。判定は `.aidev/config.yml` の
    `tracker.type` に応じたアダプタで行う（github: `gh issue view <N> --json state -q .state` ／ jira・redmine:
    各CLI/API ／ `none` や CLI不在: **advisory＝参照のみで自動判定しない**）。
  - 参照先が見つからない場合は「未充足（未着手）」とみなす。
- **未充足時の挙動（soft）**:
  - **interactive**: 未充足の依存とその理由を警告し、`AskUserQuestion` で「依存を待つ＝中断 / 承知のうえ続行」を
    選ばせる。続行は妨げない（硬ゲートは承認のみ、の思想）。
  - **autonomous / batch**: その作業には着手せず「依存未充足のため保留」と報告する（batch は次の項目へ進む）。
- 充足済み・依存なしなら通常どおり進む。`dependsOn` の記録は新規作業時（「aidev-00-start」手順4）か
  `aidev-util-propose` の起票時に行う。

## 2.8 サブタスク分割（subtask 層・schema 3）

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

## 3. 工程終了プロトコル

工程の成果物を生成・更新したら、必ず以下の順で終える。

1. **提示**：生成・更新した成果物を要約して提示する。
2. **承認ゲート**：実行モード（「10. 実行モード」）に従う。
   - **interactive（既定）**: `AskUserQuestion` で承認と遷移を 1 問にまとめた単一4択を提示
     （`Other` 自由入力も可）:
     - `承認して次工程 <論理名> へ進む`
     - `承認してここで中断`
     - `差し戻す（指摘を入力）`
     - `成果物を1項目ずつ確認しながら進む（段階レビュー）`（「3.1」）
     - ※最終工程 deliver では「次工程へ進む」の代わりに `承認して完了` とする。
     - ※選択肢は最大4つのため、上記4つを既定とする（deliver では1つ目を `承認して完了` に置換）。
   - **autonomous**: 人間ゲートを置かず**自動承認**する。ただし `state.yml` の `humanGates` に
     当該工程が含まれる場合は、その工程だけ interactive と同じくユーザーに確認する（部分自律）。
3. **分岐**：
   - **差し戻す**：指摘を反映し、やり直す（state は変更しない）。判定した工程で
     `aidev event <工程> sent_back` で **sent_back イベント**を記録する（「8.」）。
     - **差し戻し先が前工程の場合（例: review/test→coding）**：その工程を**再開する時に**
       `aidev event <差し戻し先工程> start`（例 `aidev event coding start`）を記録する。
       これを怠ると metrics の**手戻り回数（reworks）が増えず手戻りを取りこぼす**（「8.」）。
   - **承認（いずれか）**：`aidev approve <工程> [k=v …]` を実行する。これで
     `state.yml` の `approved` 追記（冪等）・`current` 更新・`metrics.yml` の **approved イベント**追記を
     一括で行う（工程別メトリクスは `k=v`。「8.」）。
     - 差し戻しで前工程に戻る場合は、無効化される後工程を `state.yml` の `approved` から手で除く
       （CLI に削除は設けていない）。
   - **承認して次工程へ進む**：記録後、次工程の skill を実行する。
   - **承認してここで中断**：記録後、停止する（レジューム可能な状態で待つ）。
4. **遷移**：
   - interactive: **自動で次工程を開始してはならない**。ユーザーが「進む」を選んだ場合のみ移る。
   - autonomous: 自動で次工程へ遷移する（「10.」の安全弁・終端規約に従う）。

> エージェント互換: 選択肢UXは `AskUserQuestion` に対応するエージェント（Claude Code 等）で有効。
> 非対応エージェントでは、同じ選択肢をテキストで提示し自由入力で受け付ける（挙動は同一）。

### 3.1 段階レビュー（成果物の1項目ずつ確認）

ユーザーが成果物 md を自力で通読する代わりに、**主エージェントが成果物を順に提示し、1項目ずつ確認**しながら
ゲートを進める対話モード。**全工程の承認ゲートで常に選択肢として提示する**（interactive のみ。autonomous は
自動承認のため不要）。

- **walkthrough 工程（`aidev-65-walkthrough`）とは別物**。あちらは deliver 前のコードレビュー補助 md を生成する
  任意工程。こちらは**任意の工程の承認ゲートで選べる「提示モード」**で、成果物 md を生成・変更しない。
- **進め方**: 成果物を意味のある単位で順に提示し、各単位ごとに要点を述べてユーザーの確認/指摘を受ける。
  粒度は成果物に合わせる:
  - `requirement.md` / `spec.md` / `design.md` / `plan.md` → **見出し節ごと**
  - `tasks.md` → **タスクごと**
  - `review.md` → **指摘ごと**
  - コード差分（review 等）→ **ファイル/ハンク単位**
- **終了**: 全単位を提示し終えたら、
  - 指摘なし → そのまま承認（`aidev approve <工程>`）して遷移先を確認する。
  - 指摘あり → 差し戻し（`aidev event <工程> sent_back`）として反映する（「3.」分岐に合流）。
- 記録（approve / sent_back・state・metrics）は通常ゲートと同一で、主エージェントが担う。段階レビューは
  **提示の仕方が違うだけ**で、ゲートの判定ロジック・記録は変えない。

## 4. 番号と順序

- 工程番号（10 刻み）は推奨されるデフォルト順を示すもので、強制ゲートではない。
- `review → coding`、`test 失敗 → coding` 等の差し戻しは正当な遷移として許可する。
- **番号末尾の規約**：
  - **末尾 0**＝標準工程（デフォルトパイプライン。例 `aidev-20-spec`, `aidev-70-deliver`）。
  - **末尾 5**＝任意・差し込み工程（必要時のみ。例 `aidev-15-research`, `aidev-95-retro`）。

### 4.1 命名カテゴリ規約（役割で割る・トリガでは割らない）

skill の命名軸は **「役割／レイヤ」**とする。**「人間が呼ぶ／AIが呼ぶ」では割らない**
（標準工程は interactive で人間直叩きも前工程からの遷移も、autonomous で AI 自動も起こり得る＝
トリガは状況依存の二次属性。`§0 運用方針`・`DESIGN §3` の「各工程は単独実行可能」と整合）。

| カテゴリ | 命名規則 | 例 |
|---|---|---|
| 入口/ルーター | `aidev-00-start` | start |
| 標準工程 | `aidev-N0-<論理名>`（末尾0） | requirement…deliver |
| 任意工程 | `aidev-N5-<論理名>`（末尾5） | research, design, walkthrough, retro |
| ユーティリティ（パイプライン外） | `aidev-util-<名>`（番号なし） | util-propose, util-batch, util-insights |
| ランタイムガード（skill ではない） | `aidev` CLI（`.claude/skills/aidev-docs/bin/aidev`・`aidev.ps1`） | new, event, approve, guard, verify, doctor |

- **トリガは命名でなく description の定型タグで示す**（picker UI と AI ルーティングが見る場所）。
  統制語彙: 各 description 冒頭に `［入口/ルーター｜標準工程・末尾0｜任意工程・末尾5｜ユーティリティ・パイプライン外］`
  のいずれか＋`／主トリガ:…`（例 `両方（直接起動 or 前工程からの遷移／autonomous 自動）` / `AI検知推奨 or ユーザー指定` / `ユーザー起動`）を付す。
- ユーティリティは `aidev-util-*` で名前空間を分離し、工程（番号付き）と一目で区別できるようにする。
- `aidev` CLI は **skill ではない**（Bash コマンド）。文書では常に「`aidev` コマンド／CLI」と呼び「skill」と呼ばない。

## 4.5 任意工程の起動（ユーザー指定 / AI検知＋推奨）

任意工程（末尾5）は次の2経路で起動する。いずれも自動遷移はせず、ゲートでユーザーが選ぶ。

- **ユーザー指定**：ユーザーが明示的に当該工程を選ぶ。
- **AI検知＋推奨**：直前工程の終了時に、AI が不足を検知して遷移ゲートで推奨する。
  - 例（research）：requirement 終了時に「調査で解消すべき未確定事項が残る」「未検証の既存挙動に
    依存する」「実現性が未確認」「影響が横断的」のいずれかを検知したら、遷移ゲートの選択肢に
    `承認して research(任意) を挟む`（推奨）を加え、推奨理由を添える。
  - 例（design）：spec 終了時に「複数コンポーネントにまたがる」「アーキ判断が必要」「インターフェース/
    データモデルが複雑」「plan で分解するには設計が粗い」のいずれかを検知したら、遷移ゲートの選択肢に
    `承認して design(任意) を挟む`（推奨）を加え、推奨理由を添える。
  - 例（walkthrough）：review 終了時に「差分が大きい」「複数モジュール横断」「処理フローが複雑」の
    いずれかを検知したら、遷移ゲートの選択肢に `承認して walkthrough(任意) を挟む`（推奨）を加え、
    推奨理由を添える。
  - 検知は推奨に留め、強制しない。ユーザーが却下すれば次の標準工程へ進める。
  - **autonomous モード**では、推奨ではなく**自律的に採否を決定**する（検知したら実施。「10.」参照）。

## 5. 参照規約

- skill 間・文書間の参照は番号を含めず論理名（`requirement` / `research` / `spec` / `design` / `plan` / `coding` / `test` / `review` / `walkthrough` / `deliver` / `retro`）で行う。
- これにより将来 renumber しても参照側を変更せずに済む（番号変更の影響を skill 名だけに閉じ込める）。

## 6. state.yml スキーマ

各 works フォルダ内に 1 つ置く。

```yaml
schema: 3                   # state スキーマ版（aidev new が刻む）。verify は導入版以上の不変条件のみ強制。未記載=legacy として免除
                            # schema 3=subtask 層（subtasks/activeSubtask/parent）導入。schema<=2 work は subtask 不変条件を免除（後方互換）
slug: <作業slug>            # 例: user-login
ticket: <ID または 省略>     # 任意。外部チケット/issue の ID（ツール非依存。例 "#18" / "PROJ-123"）。種類は .aidev/config.yml の tracker
                            # 後方互換: 旧 `issue: <番号>`（GitHub前提）も受理する。新規は ticket を使う。
current: <直近で作業した工程の論理名>
approved: [<承認済み工程の論理名…>]
mode: interactive           # interactive（既定）| autonomous。「10.」参照
humanGates: []              # autonomous 時に人間ゲートを残す工程の論理名（部分自律）。例: [spec]
maxSendBacks: 3             # autonomous 時の差し戻し上限（同一工程あたり）。未指定なら 3。「10.」参照
dependsOn: []              # この作業の前提（他の works slug / 同一親内の兄弟 subtask 名 / 外部チケット #N・PROJ-123）。未充足なら着手前に警告。「2.7」参照
# --- subtask 層（schema 3・親 work のみが持つ。「2.8」参照）---
subtasks: []               # 親が持つ子 subtask 名の一覧（フローリスト。例 [01-backend, 02-frontend]）
activeSubtask: <名 or done> # 実行中の子（.aidev/current の冗長コピー。propose/metrics 用。全完了で done）
# --- subtask 層（schema 3・子 subtask のみが持つ）---
parent: <親 work の dated 名> # 子が親 work を逆参照（例 20260622-feat）。これがある work=subtask
```

> `maxSendBacks` の現在のカウントは `state.yml` に別途持たず、`metrics.yml` の当該 phase の
> `sent_back` イベント件数から導出する（イベントログを単一の真実とし、中断・再開に強くするため）。

> **subtask の state.yml は親と別ファイル**（`works/<親>/<NN>-<subslug>/state.yml`）で、上の通常 schema を
> そのまま再帰適用する（独立した状態機械）。子は `parent` を、親は `subtasks`/`activeSubtask` を追加で持つだけで、
> ネストした YAML は導入しない（`aidev` CLI のフロー形式専用パーサで読めるよう保つため）。詳細は「2.8」。

## 7. 工程一覧（論理名と推奨順）

| 番号 | 論理名 | skill | 種別 | 成果物 | 前提 |
|------|--------|-------|------|--------|------|
| 10 | requirement | aidev-10-requirement | 標準 | `requirement.md` | （新規） |
| 15 | research | aidev-15-research | 任意 | `research.md` | requirement.md |
| 20 | spec | aidev-20-spec | 標準 | `spec.md` | requirement.md |
| 25 | design | aidev-25-design | 任意 | `design.md` | spec.md |
| 30 | plan | aidev-30-plan | 標準 | `plan.md`, `tasks.md` | spec.md（design があればそれも） |
| 40 | coding | aidev-40-coding | 標準 | コード, tasks 更新 | plan.md, tasks.md |
| 50 | test | aidev-50-test | 標準 | テスト結果 | コード |
| 60 | review | aidev-60-review | 標準 | レビュー指摘（→ coding へ差し戻し可） | diff |
| 65 | walkthrough | aidev-65-walkthrough | 任意 | `walkthrough.md`（人間レビュー補助） | review 通過 |
| 70 | deliver | aidev-70-deliver | 標準（最終） | コミット / PR | review 通過 |
| 95 | retro | aidev-95-retro | 任意 | `retro.md`（改善提案） | 作業完了（deliver 済み） |

## 8. メトリクス記録

各 works フォルダに `metrics.yml` を置き、工程の遷移を**追記式のイベントログ**で記録する。
ループ（差し戻し）・中断/再開に耐えるよう、状態ではなくイベントを積む。各指標はここから導出する。

### 必須化（ファイル不在時は生成して追記）

`metrics.yml`（全工程）と `review.md`（review 工程）は**任意ではなく必須の工程出力**とする。
retro / insights の定量分析（手戻り回数・差し戻し回数・リードタイム・再発パターン）は
これらを単一の真実として成立するため、欠落させない。

- **各工程**: start / approved / sent_back の各タイミングで記録する（「記録のタイミング」）。記録は
  `aidev`（`event` / `approve`）が行い、**`metrics.yml` 不在時は自動生成**する（不在をスキップ理由にしない）。
  CLI を持たない環境では同等の編集を手で行う（`events: []` で生成してから追記。挙動は同一・移植性のため）。
- **review 工程**: 指摘の有無にかかわらず `review.md` をラウンドごとに追記する（「レビュー指摘の内容」）。
  **不在なら生成してから追記する**。
- **retro / insights**: `metrics.yml` または `review.md` が欠落している works を見つけたら、
  欠落自体を改善対象として明示的にフラグする（過去分の timestamp を**捏造して埋めない**。
  欠落は「記録漏れ」という事実として retro.md / 集計に残す）。

### 記録のタイミング

- **start**：工程開始時（「1. 対象作業の特定」で対象確定後）→ `aidev event <工程> start`。
- **approved**：承認時（「3. 工程終了プロトコル」の記録ステップ）→ `aidev approve <工程> [k=v…]`。
- **sent_back**：差し戻し時（「3.」の差し戻し分岐）→ `aidev event <工程> sent_back`。

### タイムスタンプ（＝実施日時）

- 時刻は実行時に取得する：`date -u +%FT%T%Z`（例 `2026-06-20T10:30:00Z`、UTC・ISO 8601）。
- この `ts` が各工程の**実施日時**を兼ねる（日付・時刻の両方を含む）。
- **複数工程を続けて実行する場合**も、各工程の start/approved は**実際にその工程を行った時刻**で記録する。
  まとめて同一 ts にすると工程別の所要時間が失われるため、工程ごとに `date` を取り直す。

### metrics.yml スキーマ

```yaml
events:
  - { ts: 2026-06-20T10:00:00Z, phase: requirement, event: start }
  - { ts: 2026-06-20T10:30:00Z, phase: requirement, event: approved }
  - { ts: 2026-06-20T10:31:00Z, phase: spec,        event: start }
  - { ts: 2026-06-20T11:10:00Z, phase: spec,        event: sent_back }  # 差し戻し
  - { ts: 2026-06-20T11:11:00Z, phase: spec,        event: start }      # やり直し
  - { ts: 2026-06-20T11:40:00Z, phase: spec,        event: approved }
```

### 導出できる指標（retro 等で算出）

- **各工程の経過時間**：approved − 直近の start（待ち時間・中断を含む壁時計値）。
- **手戻り回数**：同一 phase の start が2回以上（review/test→coding ループ等）。
  ※差し戻しで coding を再開する際に `aidev event coding start` を記録しないと、この指標は手戻りを取りこぼす（「3.」差し戻し分岐）。
- **差し戻し回数**：sent_back の件数（工程別）。
- **リードタイム**：最初の start 〜 deliver の approved。
- **任意工程の使用**：research / design の start 有無。

> 注意: 経過時間は承認待ち・セッション中断を含む壁時計値であり、純粋な作業時間ではない。
> 品質傾向としては**手戻り回数**の方が示唆に富む（上流工程の弱さを示すため）。

### 工程別の付加メトリクス

該当工程の `approved` イベントに `metrics` を付与する（任意キー。値が出せる工程のみ）。

```yaml
  - { ts: ..., phase: plan,   event: approved, metrics: { tasks_planned: 4 } }
  - { ts: ..., phase: coding, event: approved, metrics: { tasks_done: 4 } }
  - { ts: ..., phase: test,   event: approved, metrics: { passed: 12, failed: 0 } }
  - { ts: ..., phase: review, event: approved, metrics: { must: 0, should: 1, nit: 2 } }
```

- **plan**: `tasks_planned`（tasks.md のタスク総数）
- **coding**: `tasks_done`（チェック済みタスク数）
- **test**: `passed` / `failed`（検証結果の件数）
- **review**: `must` / `should` / `nit`（重大度別の指摘件数）
- **CLI 形式**: `k=v` を `aidev approve` に渡すと `metrics:` になる。例:
  `aidev approve plan tasks_planned=4` / `aidev approve coding tasks_done=4` /
  `aidev approve test passed=12 failed=0` / `aidev approve review must=0 should=1 nit=2`。

### レビュー指摘の内容（review.md）

件数だけでなく**指摘の内容**を `review.md` に残す（再発パターン分析・改善に活用）。
review 工程はラウンドごとに追記する（差し戻し後の再レビューも履歴として残す）。

```markdown
# レビュー記録

## ラウンド <n>（<ts>）
- [must] <ファイル:行> <指摘内容> / 対応: <差し戻し or 修正済 or 許容>
- [should] <…>
- [nit] <…>
（指摘なしの場合はその旨）
```

## 9. 図示（mermaid）規約

成果物では、**テキストより図のほうが明確な場合に `mermaid` で図示する**（任意・全工程共通）。

- 対象: 構造 / フロー / 関係 / 状態遷移 / 依存 など。
- 図種は内容に合わせる: `flowchart` / `sequenceDiagram` / `stateDiagram` / `erDiagram` / `classDiagram` / `gantt` 等。
- **装飾目的では使わない**。図が理解・レビューを助ける時だけ使う（walkthrough の品質原則と同じ）。
- 工程別の目安（該当すれば）:
  - research: 既存構造・呼び出し関係・影響範囲
  - spec: シーケンス・状態遷移・データモデル
  - design: アーキテクチャ/コンポーネント・class・sequence・state
  - plan: タスク依存（順序が複雑な場合）
  - walkthrough: 処理フロー（review 補助）

## 10. 実行モード（interactive / autonomous）

`state.yml` の `mode` で実行モードを選ぶ。新規作業時に決定する（既定 interactive）。

### interactive（既定）
- 各工程末で人間の承認ゲート（「3.」）を通す。自動遷移しない。

### autonomous（夜間自律・PRまで一気通貫）
人間ゲートを置かずに requirement→…→deliver を自律実行し、**PR を出して停止**する。
「ゲートを消す」のではなく「**ゲートを PR（最終レビュー）に集約し、自己チェックを固くする**」モード。

- **requirement**: 起動時に与えられたタスク指示を requirement とする（対話ヒアリングはしない。
  指示が不十分なら autonomous を中止し interactive を促す）。
- **任意工程（research/design/walkthrough）**: 推奨ではなく**自律的に採否を決める**（検知したら実施）。
  **walkthrough は既定で実施**する（朝の一括レビューを助けるため）。
- **承認ゲート**: 自動承認（「3.」の autonomous 分岐）。`humanGates` に指定された工程だけは人間に確認
  （**部分自律**。例: `humanGates: [spec]` で方向性の誤り＝最大の手戻り源だけ人間が止める）。
- **終端**: deliver は **PR を作成して停止**する。**auto-merge は禁止**（マージは人間が行う）。

### 安全弁（autonomous 必須）
- **テストを硬いゲートに**: test が通らないまま PR を出さない。未解決なら **draft PR** にして要点を報告。
- **ループ上限**: review/test→coding の差し戻しは **`state.yml` の `maxSendBacks`（未指定なら 3）回まで**
  （同一工程あたり）。現在値は `metrics.yml` の当該 phase の `sent_back` イベント件数で判定する。
  上限到達後にさらに手戻りが必要なら、その工程の差し戻しは行わず**停止し、未解決点を報告して人手に委ねる**
  （test が未通過のままなら deliver は draft PR とする）。
- **予算/時間上限**: 上限到達で停止・報告（無限ループ防止）。
- **記録継続**: モードに関わらず state/metrics/各成果物・walkthrough は残す（朝の一括レビューの証跡）。
- **逸脱記録**: 自律中の重要判断は decisions.md に残す。

### 実行手段（別レイヤ）
autonomous の「夜間に回す」には実行主体が要る（headless 実行 / スケジュール起動でオーケストレーターが
本 skill 群を駆動）。これは harness（プロセス定義）とは別レイヤで用意する。
