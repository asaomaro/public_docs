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
- **同一ウェーブの並行委譲（coding）**：`tasks.md` の未チェックタスクのうち **`依存:` を満たした集合＝ウェーブ**は、
  原理的には同時に着手できる。ただし**既定は直列**で、並行してよいのは次を全て満たすときだけ。
  - 同一ウェーブである（`依存:` から導出する。ウェーブのラベルは書かれていない。tasks.md の書式は `aidev-30-plan`）
  - **`対象` のファイルが重ならない**——アンカーが**衝突判定の材料**になる（アンカーの副次的な効能）
  - 両方とも `対象` が特定済み（**`対象: 未特定` は触る範囲が読めないので必ず直列**）

  実装中にウェーブ外のファイルへ触ることになったら**並行をやめて直列に戻す**（アンカーが外れた合図）。
  **迷えば直列**——並行は最適化であって、不変条件ではない（「2.8」の「迷えば分けない」と同じ態度）。
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

**実行時の規範**（設計上の理由は `aidev-docs/DESIGN.md`「2.」）:

- **判定・不変条件は必ず `aidev` CLI に置く。**固有機構は CLI を呼ぶだけの層に留める。
- **固有名を規約に焼き付けない。役割で書く**（「2.5」と同じ流儀）。
  ❌「`/xxx` を使う」／✅「その用途に使える組み込みコマンドがあれば使う。無ければジェネリック手順」
- **「使えること」を不変条件にしない。** 組み込みコマンドやツールは環境によって存在しないので、
  **その出力形式や存在を前提にした成果物スキーマを作らない**（受け渡しはテキスト前提）。
- **組み込みコマンドは代替ではなく併用。** カバーするのは工程の観点の一部で、
  **その work の文脈を要する観点（要件適合・規約適合）は工程 skill 自身が見る**。
- **避けるべき依存**: 成果物の形式・不変条件そのものを固有機構に依存させること
  （state を CLI 以外で保持する、フックでしか生成できないファイルを前提にする等）。
- 各機構のフォールバックは**その機構を使う節に併記**する（「2.6」委譲 /「3.2」停止前チェック /
  「3.3」独立検証 /「10.」plan モード / `aidev-00-start`「3.」選択肢 UX）。
- 他環境への設置手順とフォールバック一覧は `aidev-docs/README.md`「他エージェントについて」。

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
       ——`coding` へ戻したなら `test` を通してから `review` へ戻る。
       **修正は本体より小さいので省きたくなるが、規模と危険度は比例しない。**
       実例（`20260826-datetime-picker` の decisions D14）: review 指摘への修正が
       **元より重い回帰**（部品が自分の書き込みで閉じる）を生み、単体テストは通ったまま
       実機の検証でしか出なかった。**修正の検証を省いた分だけ、後段で高くつく。**
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

`guard` と `event start` が別コマンドなので、**記録漏れは構造的に起こりうる**（過去に実際に発生）。
`verify` は deliver 前に WARN で事後検知するが、**予防には停止の手前で止める層が要る**。

- **機械的な予防は Stop フックが担う**（「2.10」第三層 / 設定は `aidev-docs/README.md`）。
  `aidev verify --strict` を呼び、記録漏れなら停止をブロックして理由を返す。
- **フックが無い環境**では、ルールファイルに「終える前に `verify --strict` を実行する」と書く。
- **`/goal`（Claude Code）は補助**。**エージェントからは設定できない**（組み込みスラッシュコマンドで
  ユーザーが打つもの）ので、**工程 skill が自分で設定してはならない**——必要ならユーザーに促すに留める。
  置く内容は「その工程の完了の目安＋終了プロトコルの記録まで完了すること」。工程を移るたび更新が
  要るため常用には向かない。**`requirement.md` の「目的 / ゴール」とは別物**（あちらは永続する成果物、
  `/goal` はセッション内の揮発的ガード）。

### 3.3 独立検証（別コンテキストで点検・任意）

成果物を**書いた本人とは別のコンテキスト**に見せて点検させる（自分の成果物の穴は同じコンテキストからは
見えにくい）。対象は2つあり、**規律・禁止事項・フォールバックは共通**。

| | (a) 文書の内部一貫性 | (b) 実装タスクの差分点検 |
|---|---|---|
| 対象 | requirement / spec / design / plan の md | coding のタスク1件分の差分 |
| 効く理由 | 手戻りの最大の源は方向 / spec 誤り＝**上流で最も効く** | 欠陥を review 工程へ持ち越さず、**タスク境界の記憶があるうちに**潰す |
| 起動 | 工程内の任意ステップ / 承認ゲートの4つ目 | coding の手順（発火条件つき） |

**共通の規律**

- **根拠の明示**: **根拠（`file:line` / 節名）の無い指摘は出さない**。推測と事実を区別する
  （さもないと的外れな指摘でゲートが詰まる）。
- **点検しない範囲（禁止）**: **外部ソース／一次資料との照合**（「2.6」。幻覚的な指摘を量産するため）。
  一次資料を要する検証は**主エージェントが直読**する。
- **委譲できないもの**は「2.6」と同じ。承認・遷移・state 記録に加え、`tasks.md` のチェック更新も
  主エージェントが行う（点検を委譲しても、進捗の単一の真実を書くのは主エージェント）。
- **フォールバック**: 委譲機構が無い環境では**同一セッションで観点を切り替えて読み直す**
  （コンテキスト分離は失うが点検項目は同じ）。
- **`profile: light` では使わない**（往復を減らす趣旨に反する）。(a) では昇格の合図でもある。

#### (a) 文書の内部一貫性

- **起動経路**: 工程内の任意ステップ（`aidev-20-spec` / `aidev-25-design` の手順）、または
  承認ゲートの 4 つ目（「3.」の条件付き差し替え。`Other` でも要求できる）。
- **点検してよい範囲（内部一貫性のみ）**: `AC` の ID 対応漏れ／`目的 / ゴール` が状態で書けているか／
  `対象範囲` と設計方針・図と本文の食い違い／節の欠落・前後の矛盾。
- **結果の扱い**: 指摘あり → その場で直して再提示、または `差し戻す`（「3.」の分岐に合流）。
  指摘なし → 承認へ。**記録は通常ゲートと同一**（新しいメトリクスキーは設けない）。
- **使わない場面**: 自明な成果物／`autonomous` のゲート経路（工程内ステップとしては使ってよい）。

#### (b) 実装タスクの差分点検

coding 工程で、**タスク1件を終えるたびにその差分だけを**別コンテキストに点検させる（`aidev-40-coding` の手順）。

- **60 review の代替ではなく前段フィルタ**。点検が見るのは **正確性・規約適合の2観点だけ**。
  **要件適合・価値適合は work 全体の文脈**（`requirement.md` の `AC` と `目的 / ゴール`）を要するので
  **60 review が見る**——`aidev-60-review` が組み込みレビューコマンドに対して引いているのと同じ線で、
  丸ごと前倒しすると観点が2つ落ちる。
- **発火条件（全タスクにはやらない）**: 点検にもコストがかかる。次のいずれかに当たるタスクだけを点検する。
  - `mode: autonomous`（人間の目が入らないので**全タスク**）
  - `対象: 未特定` だったタスク（探索から始めた＝設計の当たりが弱い）
  - アンカーが外れて探索し直したタスク（`unplanned_lookups` に数えたもの）
  - 共有モジュール／公開 API に触れたタスク（`.aidev/config.yml` の `sharedFiles` があればそれを使う）
- **ラウンド上限**: 同一タスクの「点検 → 修正」は **`maxTaskCheckRounds`**（`.aidev/config.yml`。既定 2）まで。
  超えたら深追いせず `decisions.md` に経緯を残して次のタスクへ進み、判断は 60 review に委ねる
  （`maxSendBacks`（「10.」）と同じ思想で、**ループの上限は必ず有限にする**）。
- **記録**: 件数は coding の付加メトリクス（`task_checks` / `task_check_findings`。「8.」）、
  内容は `review.md` の「タスク点検ログ」節（「8.」）。**60 review のラウンド件数には混ぜない**
  ——点検で潰れた欠陥は「工程に到達しなかった欠陥」で、ラウンド指摘とは母集団が違う。

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
schema: 4                   # state スキーマ版（aidev new が刻む）。verify は導入版以上の不変条件のみ強制。未記載=legacy として免除
                            # schema 3=subtask 層（subtasks/activeSubtask/parent）導入。schema<=2 work は subtask 不変条件を免除（後方互換）
                            # schema 4=harnessRev 刻印（効果検証の母集団特定）導入。schema<=3 work は harnessRev 検査を免除
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
harnessRev: <短縮SHA>      # この work を回したハーネスの版。`aidev new` が自動で刻む（schema 4〜）
                           # ハーネス改修の効果検証で母集団を特定するための刻印。取れない環境は unknown。「12.」参照
harnessRevDelivered: <SHA> # deliver 承認時の版。`aidev approve deliver` が刻む
                           # harnessRev と違う work＝またがり work で、効果検証の母集団からは除外される
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

### タスク点検ログ節（coding 工程内）

coding の独立点検（「3.3」(b)）で見つけて**その場で直した**指摘を、1件1行で追記する
（`review.md` が無ければ coding が生成する。ファイルの持ち主は review 工程のままでよい）。

- **review 工程の `must` / `should` / `nit` の件数には数えない**。点検で潰れた欠陥は
  「工程に到達しなかった欠陥」で、ラウンド指摘とは母集団が違う。混ぜると再発パターンの分母が壊れる。
- **`[conv:…]` タグはラウンド指摘と同じ規約で付ける**。条項の効果判定（「12.」）は `review.md` 全体を
  grep するので、節を分けても**タグの集計からは漏れない**（漏れるのは `must` 件数の側だけ）。
- 何件を何タスクに対して行ったかは metrics（`task_checks` / `task_check_findings`）が持つので、
  この節では**内容だけ**を残す（件数の二重管理を作らない）。

### 条項参照タグ（`[conv:…]`）

各指摘に、その根拠となる**条項の id** を付ける（「12.」の `docs/aidev/<id>.md` または
移送済み条項の id）。対応する条項が無ければ **`[conv:-]`**。

**分類の語彙を新規に発明しない**のが要点。「この指摘は何類型か」を毎回考えさせると判断がぶれて
書かれなくなる（`kind` frontmatter が全ファイルで欠落した失敗と同じ形）。選択肢は
`aidev convention status` が出す id の一覧なので、判断軸は「どの条項の話か」の一本になる。

タグから2つのことが機械的に読める（どちらも `review.md` の grep で足りるので、**metrics のキーは
増やさない**——「8.」の追加基準「既存から導出できない」を満たさないため）。

| 読めること | 使い道 |
|---|---|
| `[conv:-]` の頻度と内容 | **規約の穴**。条項を起こす候補（retro / insights） |
| 条項 id 別の指摘件数の推移 | **条項の効果**。`introduced` の前後で減ったか（insights の判定材料） |

id を持つ指摘が繰り返し出るなら、それは「規約が無い」ではなく「**規約はあるのに守られていない**」。
条項に追記しても効かないので、「12.」の表に従って層を下げる判断に回す。

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

### plan モードとの関係（Claude Code）

plan モードは Write / Edit を禁じるので、成果物を書くのが仕事である**工程を完走することはできない**。
成立するのは **plan モード内で探索して方針の承認を取り、解除してから書く**形だけ。

```
探索（read-only）→ 方針を提案 → 承認 → 解除 → 成果物を書く
```

- **使う**: `aidev-00-start` の三層判定（この時点で aidev のゲートが無く二重にならない。解除後
  `aidev new` へ引き渡す）／spec・design（`full` × `interactive` のみ・任意。有力案が複数あるとき、
  文書を書く前に方針の承認を取れる）／ハーネス自体の改修（aidev の対象作業ではない）。
- **使わない**: research（純粋な調査は「2.6」の委譲が正）／plan（`plan.md` と成果物が重複＝
  計画を二度書く）／coding（`tasks.md` が承認済みの計画。方針変更は**差し戻し**を使う——
  差し戻しは metrics に残る）／test・review・deliver・retro（実装計画ではない）／
  `profile: light`（往復を減らす趣旨に反する）／`autonomous`（承認者がいない）。
- **plan モード中に工程を起動されたら、先に抜けるよう促す**（工程を中途で失敗させない）。
- 「工程内で段階的に確認したい」は **段階レビュー（「3.1」）**が対応する。plan モードとは併用しない。

判断の根拠は `aidev-docs/DESIGN.md`「2.」。

## 11. 実行プロファイル（full / light）

`state.yml` の `profile` で**どこまで工程を回すか**を選ぶ。`mode`（誰が承認するか）とは**直交する別軸**で、
`light × interactive` と `light × autonomous` の両方が成立する。省略時は `full`。

### 三層の切り分け

| 層 | 対象 | 扱い |
|---|---|---|
| **対象外** | typo・コメント・整形・生成物の再生成など、判断を伴わない変更 | **aidev を通さない**（直接コミット） |
| **light** | 振る舞いを変えない / 小規模 / 下記条件を満たす | 上流 1 ゲート ＋ coding 以降は full と同一 |
| **full** | それ以外すべて | 現行パイプライン |

**「対象外」を勝手に light に格上げしない**（中身のない成果物と機械的な承認を量産させないための下限）。

### light を選べる条件（すべて満たすこと）

- 既存の**振る舞いを変えない**、または変更が単一の閉じた挙動に収まる。
- 触るファイルが **N 個以下**（既定 3。`.aidev/config.yml` の `lightMaxFiles` で調整可。
  CLI の最小 YAML 読み取りはフロー形式のフラットキーのみ対応なので、ネストキーにしない）。
- **共有モジュール / 公開 API / スキーマに触らない**。
- 新規の外部依存を追加しない。

判定は着手時に行うが、**自己申告を信用しない**（小さい変更ほど影響範囲を読み違える）。下記の昇格で救う。

### 上流 1 ゲートの規約

成果物は **4 つとも作る**（`requirement.md` / `spec.md` / `plan.md` / `tasks.md`）。
**スタブは作らない**（`plan.md` は test が「テスト方針」を読む先なので、空にすると test が検証対象を失う）。
薄く書くのは各文書の**節を絞る**ことで実現し、light 専用テンプレートは作らない（既存テンプレの部分集合）。

| 文書 | light の必須節 | 省略可 |
|---|---|---|
| `requirement.md` | 背景 / 課題、完了条件（受け入れ基準） | スコープ、機能要件、非機能要件 / 制約 |
| `spec.md` | 設計方針、対象範囲 | I/F・データ構造、振る舞いの詳細、ドメイン固有、エラー処理 |
| `plan.md` | 作業順序と依存関係、テスト方針 | リスク / 留意点 |
| `tasks.md` | すべて（`対象` アンカー・`依存` 含む） | — |

**記録は `requirement` 1 件**にする（`aidev event requirement start` → `aidev approve requirement`）。
`spec` / `plan` で記録すると guard の前提（`requirement.md` / `spec.md`）を満たせず NG になるため
（`requirement` は前提を持たない唯一の上流工程）。理由の詳細は `aidev-docs/DESIGN.md`「2.」。

`approved` に `spec` / `plan` が入らないのは正常（`need_approved` を使うのは walkthrough / deliver /
retro だけなので影響しない）。metrics 上は **`spec` / `plan` の start が無いこと**が light の指紋になる。

### 任意工程

light では **research / design / walkthrough を使わない**。必要と判断した時点で light の条件を
外れているので、**昇格の合図**として扱う。

### 昇格（light → full）

| 昇格トリガ | 検知点 |
|---|---|
| 想定外のファイルに触った / 影響が広がった | coding |
| `test` が落ちた | test |
| `review` で `must` が出た | review |
| 変更ファイル数が N を超えた | deliver（`files_changed` で機械検知。`aidev verify` が WARN） |
| 任意工程（research / design）が必要になった | 任意 |

**昇格は片方向**（`full` → `light` は不可）。手順:

1. `aidev escalate`（`profile` を `full` に書き換える。state.yml の編集は CLI に集約する）。
2. `decisions.md` に 1 エントリ（「設計から逸脱した判断」として）。
3. 該当工程の approved に `escalated_from_light=1`（「8.」）。
4. 省略していた節を各文書に**足す**（書き換えではない）。

**light でも coding / test / review / deliver は full と完全に同一**（review を残すことが品質の担保）。
## 12. PJ規約の条項（docs/aidev）と効果検証

ハーネスが生成した規約を **PJ 所有の AGENTS.md / CLAUDE.md に書き込まない**ための層。
retro / insights の「PJ プロセス / 規約」カテゴリの出力先はここになる。

### なぜ AGENTS.md に直接書かないか

このファイルの冒頭が宣言しているとおり、harness は **PJ 固有ファイル（AGENTS.md / CLAUDE.md / docs 等）
には依存しない**。にもかかわらず改善提案の宛先が AGENTS.md だと、**依存しないと宣言したファイルに
harness が書き戻す**ことになる。AGENTS.md は PJ が所有し、aidev を使わない人も編集する。
所有権の衝突を構造に埋め込まないため、生成物は `docs/aidev/` に置く。

### docs/aidev は終着点ではない（二重管理の防止）

`docs/aidev/` は保管庫ではなく**検証中の待避所（インキュベーター）**。条項は必ずここから出ていく。

| status | 意味 | 次にすること |
|---|---|---|
| `pending` | 導入済み・母集団が未達 | 待つ（`aidev convention status` の `ready` を見る） |
| `confirmed` | 効果が確認できた | **PJ ドキュメントへ本文を移送**し `promote` |
| `promoted` | 移送済み | 何もしない（tombstone として `archive/` に残る） |
| `ineffective` | 効果が無かった | 撤去、または CLI / フック層へ寄せる（下記） |
| `superseded` | 別条項に置き換わった | 撤去 |

**本文の在処は常に1箇所**。移送したら `docs/aidev/` 側は本文を捨てて tombstone（frontmatter と
`promoted_to` リンクだけ）にする。本文が2箇所に存在する瞬間を作らないことで二重管理を構造的に防ぐ。

**tombstone を消さない理由は重複排除**。跡形なく消すと、同じ提案が retro から再び上がってくる
（`aidev-util-propose` の柱の一つが重複排除であるのと同じ理由）。`aidev convention new` は
archive に同じ id があれば**重複として弾く**。

**定常状態では `pending` の条項しか残らない**。確定したものも否定されたものも出ていくので、
`docs/aidev/` が膨らんできたら**それ自体が異常の信号**（検証が回っていない / 移送が滞っている）。

### AGENTS.md に置くのは「読む条件つきの索引」だけ

AGENTS.md / CLAUDE.md は**自動読込**される。`docs/aidev/` 配下はされない。移設は
「確実に読まれる」を「リンクを辿れば読まれるかもしれない」に落とすので、そこを索引で埋める。

裸のリンクは辿られない。**いつ辿るかが書かれたリンク**は辿られる——これは「0.」の付録テーブルが
このファイル自身に対してやっていることと同じ形で、要約も併記して**辿らなくても「何があるか」は
分かる**状態を保つ。

```markdown
<!-- aidev:conventions -->
- 命名を判断するとき → docs/coding-standards.md#boolean-naming（移送済み）
- エラー処理の粒度を決めるとき → docs/aidev/error-granularity.md（検証中）
<!-- /aidev:conventions -->
```

- **harness が触るのはマーカーの内側だけ**。導入時に人間が1回置き、以後は索引行の増減と
  リンク先の張り替え（移送時）のみ。マーカー外は完全に PJ のもの。
- aidev を使わない PJ は**索引ブロックごと削除すれば無害に切り離せる**。
- **矛盾したときは PJ の AGENTS.md 本体が上位**。`docs/aidev/` は追補であって上書きではない
  （ハーネスの提案が PJ の明示的な意思を覆すのは越権）。

### 条項ファイルのスキーマ

`docs/aidev/<id>.md`（場所は `.aidev/config.yml` の `conventionsDir` で変更可。既定 `docs/aidev`）。

```yaml
---
convention: naming-boolean      # id（ファイル名と一致）
status: pending                 # pending | confirmed | promoted | ineffective | superseded
introduced: 2026-08-30          # 導入日（UTC）。母集団の起点になる
source: .aidev/insights/2026-08-28-insights.md   # この条項を生んだ信号（任意）
hypothesis: 命名に関する must/should 指摘が減る    # 必須。書けない条項は作らせない
verify_after: 5                 # 判定に要する母集団の最低件数（既定 5）
result: <判定の内訳>             # confirm 時
promoted_to: docs/coding-standards.md#boolean-naming  # promote 時
promoted_at: 2026-09-15         # promote 時
note: <退役理由>                 # retire 時
---
```

**`hypothesis` を必須にするのがこの層の入口ゲート**。「どの指標がどう動けば成功か」を先に書かないと、
後から見た指標は常に何かしら動いているので都合のいい説明がついてしまう。それは検証ではなく
事後の物語作り。書けないなら条項にすべきでない、と CLI が拒否する。

**母集団**＝`introduced` 以降に**着手した** work の件数（`aidev convention status` の `pop`）。
導入前から走っていた work は条項の効果を半分しか受けていないので数えない。

**タスク点検（「3.3」(b)）は判定を保守側にずらす**。点検で潰れた欠陥は review のラウンド指摘に現れないため、
`must` 件数だけを見ると条項の効果は**過小に**見える。判定材料の主役は `review.md` の `[conv:…]` タグで、
タグは点検ログ節にも同じ規約で付く（「8.」）ので**節をまたいで grep すれば漏れない**。
件数指標を使うときは `task_check_findings` を併せて見る。

### 効果が無かった条項の行き先（重要）

`ineffective` は「条項の内容が間違っていた」とは限らない。「2.6」の三層モデルどおり、
**散文規約は LLM が守る前提で実効が非決定的**なので、**散文層の限界に当たった**可能性がある。
その場合の打ち手は削除ではなく **CLI（ハード層）かフック（自動化層）へ寄せる**こと。

この診断を立てられるようにするのが、review.md の**条項参照タグ**（「8.」）。

| review 指摘が条項に | 意味 | 打ち手 |
|---|---|---|
| 対応しない（`conv:-`） | 規約に穴がある | 条項を起こす |
| 対応する（なのに指摘された） | 規約はあるが守られていない | **追記しても効かない**。層を下げる |

### CLI（`aidev convention`）

起こす・状態を進める・退避するは CLI にある（「検査だけあって実行が無い」を作らない）。
**本文を PJ ドキュメントへ実際に移す作業だけは CLI にしない**——文体・配置・既存章との統合が
判断だから（backlog の消し込み本体と同じ線引き）。

| コマンド | 役割 |
|---|---|
| `aidev convention new <id> --hypothesis <text> [--source <p>] [--verify-after <n>]` | 起こす |
| `aidev convention confirm <id> [--result <text>]` | 効果ありと判定 |
| `aidev convention promote <id> --to <path#anchor>` | tombstone 化して退避（移送先の実在を検査） |
| `aidev convention retire <id> --status ineffective\|superseded [--note <t>]` | 退役して退避 |
| `aidev convention status [--format table\|tsv]` | 状態・母集団・判定可否の一覧 |

**ファイル自身の一生は `aidev doctor` が見る**（backlog と同じく、条項ファイルには持ち主の work が
いないので `verify` の硬ゲートにできない）。検知するのは `status` の欠落・誤記／**判定可能なのに
未判定**／**confirmed の移送漏れ**／終状態の退避漏れ。**WARN 止まり**。

### ハーネス自身の効果検証（harnessRev）

条項（PJ規約）と同じ問いを**ハーネス自身**に向けたものが `state.yml` の `harnessRev`（「6.」）。
`aidev new` が自動で刻み、`aidev approve deliver` が `harnessRevDelivered` を刻む。

- 刻印を手書きに任せると忘れられ、**忘れられた work は母集団から静かに漏れる**
  （`schema:` を `new` に一本化したのと同じ理由）。
- **またがり work**（着手時と着地時で版が違う）は、改修の効果を半分しか受けていない。
  どちらかに帰属させると効果が薄まる方向にバイアスがかかるので、**母集団から除外**する
  （`aidev verify` が WARN で知らせる）。
- git が無い等で版が取れない環境では **`unknown` を刻む**（「8.」の「捏造して埋めない」と同じ態度）。

判定は `aidev-util-insights`（横断分析）が行う。

