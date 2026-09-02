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
- **付録**（同ディレクトリ。**該当する状況のときだけ読む**。工程ごとの読み込み量を抑えるため、
  詳細をここから切り出している。**核となる規約と要約は本ファイルに残してある**ので、
  付録を読まなくても「何があるか」は分かる）:

  | 付録 | 元の節 | 読む条件 |
  |---|---|---|
  | `protocol-worktree.md` | 「1.5」 | ユーザーが並行作業（worktree）を使う / 使っている work を触る |
  | `protocol-subtask.md` | 「2.8」 | plan の split 判定 / `state.yml` に `parent` がある work の工程 |
  | `protocol-backlog.md` | 「2.9」 | backlog 項目を選ぶ / deliver で消し込む |
  | `protocol-analysis.md` | 「8.」 | retro / insights の定量分析 |
  | `protocol-conventions.md` | 「12.」 | PJ規約の条項を起こす / 効果を判定する / PJ ドキュメントへ移送する |
  | `protocol-check.md` | 「3.3」 | 上流4工程の承認ゲートで独立点検を選ぶ / spec・design の点検 / coding のタスク点検 |
  | `protocol-autonomous.md` | 「10.」 | `mode: autonomous` の work / plan モードを使う（start・spec・design） |
  | `protocol-light.md` | 「11.」 | `profile: light` の work（4文書の必須節・昇格） |
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
git worktree＋`feature/<slug>` ブランチを作って隔離着手できる。**並列の要否はユーザーが明示
`aidev worktree add` で判断する**（ハーネスは並列化を自動判断しない。既定は単一ワーキングツリーの直列）。

**worktree を使う / 使っている work を触るときは `protocol-worktree.md` を読む**
（current の worktree ローカル性・1 worktree = 1 branch = 1 work・既存 work 継続の前提・規約の適用範囲）。

> **撤去（`aidev worktree rm`）は破壊的**（唯一「作業を失いうる」操作）。打つ前に付録「撤去」を読む。

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
- **エージェント組み込みのコマンド**：PJ 固有資産が無い場合、実作業に使える組み込みコマンド
  （レビュー・整理等）があればそれを用いてよい。ただし**固有名で参照せず役割で書く**こと、
  および**併用であって委譲ではない**ことに注意する（優先順位の三段階と理由は「2.10」）。
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
  ユーザーへ対話的承認を求められないため。`tasks.md` のチェック更新も同じ（進捗の単一の真実）。
- **同一ウェーブの並行委譲（coding）**：既定は直列。並行の可否条件は `aidev-40-coding` の手順 2 が正典
  （使うのは coding だけなのでそこに置く）。**迷えば直列**。
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
    `aidev status`/`guard` は外部チケットを常に `advisory` と表示するだけで判定しない——判定はこの規約に従い工程 skill が行う。
  - 参照先が見つからない場合は「未充足（未着手）」とみなす。
- **未充足時の挙動（soft）**:
  - **interactive**: 未充足の依存とその理由を警告し、`AskUserQuestion` で「依存を待つ＝中断 / 承知のうえ続行」を
    選ばせる。続行は妨げない（硬ゲートは承認のみ、の思想）。
  - **autonomous / batch**: その作業には着手せず「依存未充足のため保留」と報告する（batch は次の項目へ進む）。
- 充足済み・依存なしなら通常どおり進む。`dependsOn` の記録は新規作業時（「aidev-00-start」手順4）か
  `aidev-util-propose` の起票時に行う。

## 2.8 サブタスク分割（subtask 層・schema 3）

**高結合で 1 PR には割れないが大規模な work** を、1 PR を保ったまま内部で漸進的に実装・レビューする仕組み。
**割るかは plan で判定する**（3層決定木は `aidev-docs/DESIGN.md`「5.」）。

- **小〜中規模 work では使わない**。spec＋plan で 1 PR に収まるなら subtask 化しない（過剰分割の禁止）。
- **subtask を扱うときは `protocol-subtask.md` を読む**——plan の split 判定時、および `state.yml` に
  `parent` がある work の plan / coding / test / review。フォルダ規約・工程レイヤリング・カーソル前進・
  兄弟依存・差し戻し先・CLI の機械的強制はそこにある。

## 2.9 台帳の同期（backlog 出自の消し込み）

backlog は**遅延キュー**で、完了した行を閉じるのは deliver の責務
（`DESIGN.md`「2.5」: 流れは backlog → works（consume）。**backlog 行は deliver で `[x]`**）。

- **記録**: `aidev new <slug> --backlog <file>` で出自を刻む（「6.」）。**どちらの入口でも省略しない**。
- **強制**: `backlog:` を持つ work は、その backlog ファイルに自分の slug が現れないと
  **`aidev verify` が FAIL する**（deliver の着地前ゲートで弾かれる）。
- **backlog を扱うときは `protocol-backlog.md` を読む**——項目を選ぶとき（`inflight` の確認）と、
  deliver で消し込むとき。消し込みの書き方は `aidev-70-deliver`「3.5」。

## 2.10 エージェント間の可搬性

**aidev は特定のエージェントに依存しない。** Claude Code 固有の機構は**任意の高速化層**であり、
無くても不変条件は保たれる。強制力は三層:

| 層 | 実体 | 効く範囲 |
|---|---|---|
| 第一層（ソフト） | 散文規約（本 protocol・各 SKILL.md） | **全環境** |
| 第二層（ハード） | `aidev` CLI（`guard` / `approve` / `verify`） | **全環境**（CLI 無しなら手で同等に） |
| 第三層（自動化・任意） | エージェント固有のフック等 | その環境のみ |

第三層は**第二層を自動で呼ぶだけ**で判定を持たない。外しても第二層が残る。

**実行時の規範**は2つ: **判定・不変条件は必ず `aidev` CLI に置く**／**固有名を規約に焼き付けず役割で書く**
（「2.5」）。理由と残りの規範は `aidev-docs/DESIGN.md`「2.6」、他環境への設置とフォールバック一覧は
`aidev-docs/README.md`。

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
     - ※**4つ目は条件付きで差し替えてよい**: 上流工程（requirement / spec / design / plan）で
       成果物が長い・判断が多いときは、段階レビューの代わりに
       `独立検証を挟んでから決める`（「3.3」(a)）を提示する。差し替えたときは理由を添える。
       **どちらも `Other` の自由入力で明示的に要求できる**ので、片方を出しても他方は失われない。
   - **autonomous**: 人間ゲートを置かず**自動承認**する。ただし `state.yml` の `humanGates` に
     当該工程が含まれる場合は、その工程だけ interactive と同じくユーザーに確認する（部分自律）。
3. **分岐**：
   - **差し戻す**：指摘を反映し、やり直す（state は変更しない）。判定した工程で
     `aidev event <工程> sent_back` で **sent_back イベント**を記録する（「8.」）。
     - **差し戻し先が前工程の場合（例: review/test→coding）**：その工程を**再開する時に**
       `aidev event <差し戻し先工程> start`（例 `aidev event coding start`）を記録する。
       これを怠ると metrics の**手戻り回数（reworks）が増えず手戻りを取りこぼす**（「8.」）。
     - **指摘への修正も、本体と同じゲートを通す。** 直したら**間の工程を飛ばさない**
       ——`coding` へ戻したなら `test` を通してから `review` へ戻る（規模と危険度は比例しない。実例は DESIGN「6.」）。
   - **承認（いずれか）**：`aidev approve <工程> [k=v …]` を実行する。これで
     `state.yml` の `approved` 追記（冪等）・`current` 更新・`metrics.yml` の **approved イベント**追記を
     一括で行う（工程別メトリクスは `k=v`。「8.」）。
     - 差し戻しで前工程に戻る場合は、無効化される後工程の承認を **`aidev unapprove <工程>`** で
       取り消す（`approved` から外し、`current` をそこへ戻す）。**手で編集しない**——
       state.yml の更新を CLI に集約するのは「2.」の原則で、ここだけ例外にすると
       state を見ても経緯が分からなくなる。**取り消しても記録は消えない**（`sent_back` として
       刻まれる。手戻りは実際に起きた事実なので、消すと「8.」の指標が過小になる）。
   - **承認して次工程へ進む**：記録後、次工程の skill を実行する。
   - **承認してここで中断**：記録後、停止する（レジューム可能な状態で待つ）。
4. **遷移**：
   - interactive: **自動で次工程を開始してはならない**。ユーザーが「進む」を選んだ場合のみ移る。
   - autonomous: 自動で次工程へ遷移する（「10.」の安全弁・終端規約に従う）。

> エージェント互換: 選択肢UXは `AskUserQuestion` に対応するエージェント（Claude Code 等）で有効。
> 非対応エージェントでは、同じ選択肢をテキストで提示し自由入力で受け付ける（挙動は同一）。

### 3.1 段階レビュー（成果物の1項目ずつ確認）

ユーザーが成果物 md を自力で通読する代わりに、**主エージェントが成果物を順に提示し、1項目ずつ確認**しながら
ゲートを進める対話モード。**既定では全工程の承認ゲートで選択肢として提示する**（interactive のみ。autonomous は
自動承認のため不要）。ただし上流工程で「独立検証」（「3.3」(a)）を提示する場合は 4 つ目の枠をそちらに譲る
（`Other` で要求できるため失われない。「3.」の条件付き差し替え）。

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

### 3.2 停止前チェック（予防層）

`guard` と `event start` が別コマンドなので記録漏れは構造的に起こりうる。**予防は Stop フック**（第三層。
設定と他環境のフォールバックは `aidev-docs/README.md`）が `aidev verify --strict` を呼ぶ。フックが無い環境は
ルールファイルに「終える前に `verify --strict`」と書く。`/goal` は**ユーザーが打つ**補助で skill が設定してはならない。

### 3.3 独立検証（別コンテキストで点検・任意）

成果物を**書いた本人とは別のコンテキスト**に見せて点検させる。(a) 文書の内部一貫性（上流4工程の
承認ゲートの 4 つ目、または spec・design の工程内）／(b) coding のタスク差分点検。
**一次資料との照合は委譲しない**（「2.6」）。`profile: light` では使わない。詳細・発火条件・ラウンド上限は
`protocol-check.md`。

## 4. 番号と順序

- 工程番号（10 刻み）は推奨されるデフォルト順を示すもので、強制ゲートではない。
- `review → coding`、`test 失敗 → coding` 等の差し戻しは正当な遷移として許可する。
- **番号末尾の規約**：
  - **末尾 0**＝標準工程（デフォルトパイプライン。例 `aidev-20-spec`, `aidev-70-deliver`）。
  - **末尾 5**＝任意・差し込み工程（必要時のみ。例 `aidev-15-research`, `aidev-95-retro`）。

### 4.1 命名カテゴリ規約

役割／レイヤで命名し、トリガでは割らない。カテゴリ表と description の統制語彙は `aidev-docs/README.md`
「命名カテゴリ」が正典。skill 間の参照は番号を含めず論理名で行う（renumber の影響を skill 名に閉じ込める）。

## 4.5 任意工程の起動（ユーザー指定 / AI検知＋推奨）

任意工程（末尾5）は次の2経路で起動する。いずれも自動遷移はせず、ゲートでユーザーが選ぶ。

- **ユーザー指定**：ユーザーが明示的に当該工程を選ぶ。
- **AI検知＋推奨**：直前工程の終了時に、AI が不足を検知して遷移ゲートで推奨する。
  - 例（research）：requirement 終了時に次のいずれかを検知したら、遷移ゲートの選択肢に
    `承認して research(任意) を挟む`（推奨）を加え、推奨理由を添える。**この5条件がこの機構の正典**で、
    `aidev-15-research` / `aidev-10-requirement` はここを参照する（3箇所に写して1箇所だけ更新され、
    **UI の条件が判定側に届かず一度も発火しない**状態が実際に起きた）。
    - 調査で解消すべき未確定事項が残る
    - 未検証の既存挙動（既存コードの現在の振る舞い・暗黙の前提）に依存する
    - 技術的実現性が未確認（使える API/ライブラリ・制約が不明）
    - 影響が横断的（複数モジュール／言語同居の副作用など）
    - **利用者が操作する部品を作る**（ポップオーバー・ピッカー・一覧・ダイアログ等）——
      確立したパターンの調査を必須とする（`aidev-15-research`「UI の規範」）
  - design：spec 終了時に次のいずれかを検知したら `承認して design(任意) を挟む`（推奨）を加える。
    **この4条件が正典**（`aidev-20-spec` / `aidev-25-design` はここを参照する）。
    - 複数コンポーネント／モジュールにまたがる
    - アーキテクチャ判断（新規の構造・パターン・責務分割の選択）が必要
    - インターフェース／データモデルが複雑（型・スキーマ・状態遷移の設計に踏み込む）
    - plan で直接分解するには設計が粗い
  - walkthrough：review 終了時に次のいずれかを検知したら `承認して walkthrough(任意) を挟む`（推奨）を加える。
    **この3条件が正典**（`aidev-60-review` / `aidev-65-walkthrough` はここを参照する）。
    - 差分が大きい（変更ファイル数・行数が多く全体像を掴みにくい）
    - 複数モジュールを横断する
    - 処理フローが複雑（非自明な制御フロー・状態遷移・トリッキーな実装）
  - 検知は推奨に留め、強制しない。ユーザーが却下すれば次の標準工程へ進める。
  - **autonomous モード**では、推奨ではなく**自律的に採否を決定**する（検知したら実施。「10.」参照）。

## 6. state.yml スキーマ

各 works フォルダ内に 1 つ置く。

```yaml
schema: 5                   # state スキーマ版（aidev new が刻む）。verify は導入版以上の不変条件のみ強制。
                            # 未記載=legacy 免除。版ごとの導入内容は bin/README.md「schema の履歴」
slug: <作業slug>            # 例: user-login
ticket: <ID または 省略>     # 任意。外部チケット/issue の ID（ツール非依存。例 "#18" / "PROJ-123"）。種類は .aidev/config.yml の tracker
                            # 後方互換: 旧 `issue: <番号>`（GitHub前提）も受理する。新規は ticket を使う。
current: <直近で作業した工程の論理名>
approved: [<承認済み工程の論理名…>]
mode: interactive           # interactive（既定）| autonomous。「10.」参照＝**誰が承認するか**
profile: full               # full（既定・省略可）| light。「11.」参照＝**どこまで回すか**
                            # mode と直交する別軸。省略＝full（既存 work は記載が無く full 扱い＝後方互換）
humanGates: []              # autonomous 時に人間ゲートを残す工程の論理名（部分自律）。例: [spec]
maxSendBacks: 3             # autonomous 時の差し戻し上限（同一工程あたり）。未指定なら 3。「10.」参照
dependsOn: []              # この作業の前提（他の works slug / 同一親内の兄弟 subtask 名 / 外部チケット #N・PROJ-123）。未充足なら着手前に警告。「2.7」参照
backlog: <file>            # 任意。backlog 項目から起こした場合の出自（`.aidev/backlog/` 内のファイル名。例 hostserver.md）
                           # `aidev new --backlog <file>` が刻む。deliver でその行を [x] にすることを verify が強制する（「2.9」）
harnessRev: <内容ハッシュ>  # この work を回したハーネスの版（aidev-* の tree hash 12 桁。`aidev new` が刻む）。「12.」
harnessRevDelivered: <同上> # deliver 承認時の版。違えば「またがり work」で母集団から除外（「12.」）
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

- **`profile: light` の場合**（「11.」）: 上流 3 工程（requirement / spec / plan）を **1 ゲートに畳む**。
  成果物は 4 つとも作る（薄く書く）が、承認は `requirement` として 1 回だけ記録する。
  以降 coding → test → review → deliver は full と**完全に同一**。任意工程は使わない。

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

### 導出できる指標（retro / insights で算出）

`metrics.yml` のイベント列から導出する（経過時間・手戻り回数・差し戻し回数・リードタイム・
任意工程の使用・アンカー的中率・規模あたりの手戻り）。**算出は `aidev metrics` が行う**ので、
工程の実行中に手計算する必要はない。

**各指標の定義と解釈上の注意（壁時計値・`mode` による層別）は `protocol-analysis.md`**。

### 工程別の付加メトリクス

該当工程の `approved` イベントに `metrics` を付与する（任意キー。値が出せる工程のみ）。

```yaml
  - { ts: ..., phase: plan,    event: approved, metrics: { tasks_planned: 4, tasks_anchored: 3 } }
  - { ts: ..., phase: coding,  event: approved, metrics: { tasks_done: 4, unplanned_lookups: 1 } }
  - { ts: ..., phase: test,    event: approved, metrics: { passed: 12, failed: 0 } }
  - { ts: ..., phase: review,  event: approved, metrics: { must: 0, should: 1, nit: 2 } }
  - { ts: ..., phase: deliver, event: approved, metrics: { files_changed: 7, insertions: 169, deletions: 31 } }
```

- **plan**: `tasks_planned`（tasks.md のタスク総数）/
  `tasks_anchored`（`対象` が特定済みのタスク数。`対象: 未特定` は数えない）
- **coding**: `tasks_done`（チェック済みタスク数）/
  `unplanned_lookups`（**アンカー付きタスクなのに**探索し直した回数。`未特定` のタスクでの探索は
  最初から想定内なので数えない——分母 `tasks_anchored` と対応させる）/
  `task_checks`（独立点検（「3.3」(b)）を行ったタスク数）/
  `task_check_findings`（点検で見つけて**その場で直した**指摘の件数）
  - **点検を1件も行わなかったときも `task_checks=0` を明示する**（省略すると「測っていない」と区別できない）。
  - 率の分母は `tasks_done` ではなく **`task_checks`**。点検しなかったタスクを分母に入れると、
    発火条件（「3.3」(b)）が適切かどうかが見えなくなる。
  - 読み方: `task_check_findings` が出ているのに review の `must` が減らないなら、**点検が効いていない**
    （観点か発火条件がずれている）。両方が減っているなら効いている。
- **test**: `passed` / `failed`（検証結果の件数）
- **review**: `must` / `should` / `nit`（重大度別の指摘件数）
- **任意工程（light からの昇格時）**: `escalated_from_light`（`1` を刻む。昇格が起きた工程の approved に付す。
  「11.」参照。昇格率＝light の入口判定が機能しているかの指標になる）
- **deliver**: `files_changed` / `insertions` / `deletions`（着地した**実装**の変更規模）。
  `git diff --stat` から機械取得し、工程成果物（`.aidev/` 配下）は除外する
  （例: `git diff --stat HEAD -- . ':!.aidev'`。事後記録モードは既着地コミットの範囲で計測）。
- **CLI 形式**: `k=v` を `aidev approve` に渡すと `metrics:` になる。例:
  `aidev approve plan tasks_planned=4 tasks_anchored=3` /
  `aidev approve coding tasks_done=4 unplanned_lookups=1 task_checks=2 task_check_findings=1` /
  `aidev approve test passed=12 failed=0` / `aidev approve review must=0 should=1 nit=2` /
  `aidev approve deliver files_changed=7 insertions=169 deletions=31`。

**キーを勝手に増やさない。** 追加の基準（実測できる / 改善に直結する / 既存から導出できない）と、
**トークン消費を記録しない理由**は `aidev-docs/DESIGN.md`「2.」。

### レビュー指摘の内容（review.md）

件数だけでなく**指摘の内容**を `review.md` に残す（再発パターン分析・改善に活用）。
review 工程はラウンドごとに追記する（差し戻し後の再レビューも履歴として残す）。

```markdown
# レビュー記録

## タスク点検ログ（coding 工程内・「3.3」(b)）
- [must][conv:-] <ファイル:行> <指摘内容> / 対応: 修正済（T3・ラウンド1）

## ラウンド <n>（<ts>）
- [must][conv:naming-boolean] <ファイル:行> <指摘内容> / 対応: <差し戻し or 修正済 or 許容>
- [should][conv:-] <…>
- [nit][conv:-] <…>
（指摘なしの場合はその旨）
```

### 条項参照タグ（`[conv:…]`）

各指摘に根拠となる**条項の id** を付ける（無ければ `[conv:-]`）。候補は `aidev convention status` の一覧
——分類の語彙を新規に発明しない。タグから「規約の穴（`conv:-`）」と「条項の効果（id 別件数 vs `baseline`）」が
機械的に読める。点検ログ節（`protocol-check.md`）にも同じ規約で付ける。詳細は `protocol-conventions.md`。

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

`state.yml` の `mode`＝**誰が承認するか**。既定 `interactive`（各ゲートで人間が選ぶ）。`autonomous` は
夜間自律で PR まで一気通貫——**PR で停止し auto-merge しない**、test を硬ゲートに、`maxSendBacks`（既定 3）を
超えたら停止、`humanGates` で部分的に人間ゲートを残せる。plan モードは start・spec・design でのみ、
解除してから書く。詳細は `protocol-autonomous.md`。

## 11. 実行プロファイル（full / light）

`state.yml` の `profile`＝**どこまで工程を回すか**（`mode` と直交）。**対象外**（typo・整形＝aidev を通さない）／
**light**（振る舞いを変えない小規模＝上流 3 工程を requirement の 1 ゲートに畳む。coding 以降は full と同一）／
**full**。light の条件・4 文書の必須節・昇格（`aidev escalate`。片方向）は `protocol-light.md`。

## 12. PJ規約の条項（docs/aidev）と効果検証

ハーネスが生成した PJ 規約は **PJ 所有の AGENTS.md には書かず** `docs/aidev/<id>.md` に置き、
AGENTS.md には**読む条件つきの索引**（`<!-- aidev:conventions -->` ブロック）だけを置く。条項は
`pending → confirmed → promoted`（PJ ドキュメントへ移送。本文の在処は常に1箇所）または
`ineffective / superseded` で出ていく。起票は `hypothesis` と `baseline` が必須。review は指摘に
`[conv:<id>]` を付ける（「8.」）。**矛盾したときは PJ の AGENTS.md 本体が上位**。
起票・判定・移送・索引・スキーマ・CLI は `protocol-conventions.md`。

### ハーネス自身の効果検証（harnessRev）

条項（PJ規約）と同じ問いを**ハーネス自身**に向けたものが `state.yml` の `harnessRev`（「6.」）。
`aidev new` が自動で刻み、`aidev approve deliver` が `harnessRevDelivered` を刻む。

- 刻印を手書きに任せると忘れられ、**忘れられた work は母集団から静かに漏れる**
  （`schema:` を `new` に一本化したのと同じ理由）。
- **またがり work**（着手時と着地時で版が違う）は、改修の効果を半分しか受けていない。
  どちらかに帰属させると効果が薄まる方向にバイアスがかかるので、**母集団から除外**する
  （`aidev verify` が `note:` で知らせる。**WARN ではない**——またがりは事後に取り消せない事実で、
  人が直せることが無い。ハーネスを1回コミットしただけで in-flight の全 work が鳴き続けるため、
  「いま直せる」WARN と同列に置くとそちらが埋もれる）。
- **`verify` は deliver 承認の「前」に走る**ので、`harnessRevDelivered` をまだ持っていない。
  着地時の刻印を待つ検査にすると**通常の順序では一度も発火しない**ので、まだ無いときは
  **現在の版**と比べる（このまま deliver すればそれが着地時の版になる）。
- 版が見る範囲は **`aidev-*` の skill だけ**。`<skills>` 全体を見ると同居する無関係な skill の
  変更でも版が上がり、その間の work が全部またがり扱いになる。またがり判定は**母集団からの除外**
  なので、誤検知はそのまま**効果検証の母集団を痩せさせる**。
- git が無い等で版が取れない環境では **`unknown` を刻む**（「8.」の「捏造して埋めない」と同じ態度）。

判定は `aidev-util-insights`（横断分析）が行う。

