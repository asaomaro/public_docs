# aidev ランタイムガード CLI

aidev ハーネスの **state.yml / metrics.yml 更新を「単一の検証済み経路」に集約**し、工程の前提と
不変条件を**決定的に**検査するためのコマンド群。散文規約（=ソフト強制）に対する**ハード強制の土台**。

- **Node 非依存**。`aidev` は POSIX sh（`sed`/`awk`/`grep`/`date` のみ）、`aidev.ps1` は Windows PowerShell。
- 両者は**挙動・出力・終了コードを一致**させてある（OS 差をここで吸収）。
- 強制力の主体は**各 skill がこの CLI を呼ぶ**こと（「正しいやり方＝ガードされたやり方」にする）。
  hooks（Stop フック等）は任意の自動化層で、無くても成立する（`DESIGN.md`「2.6」）。最後の砦は deliver の `verify` ゲートと `doctor` の事後検知。

## 使い方

POSIX（Linux/macOS）:

```sh
.claude/skills/aidev-docs/bin/aidev <command> ...
```

Windows:

```powershell
pwsh .claude/skills/aidev-docs/bin/aidev.ps1 <command> ...
# pwsh は Windows の標準搭載ではない。Windows PowerShell 5.1 だけの環境ではこちら:
powershell -NoProfile -File .claude\skills\aidev-docs\bin\aidev.ps1 <command> ...
```

Git Bash（Git for Windows 同梱）があるなら POSIX 版の `aidev` がそのまま動く（実測で全機能・
生成ファイルとも一致）。どちらを使ってもよい。

> **`aidev.ps1` は UTF-8 BOM 付きで保存すること**（`.gitattributes` で改行も固定してある）。
> Windows PowerShell 5.1 は BOM 無し `.ps1` を ANSI（日本語環境なら cp932）として読むため、
> BOM を落とすと日本語リテラルが壊れて ParserError になり**起動すらできない**。
> 出力は OS を問わず UTF-8 固定（コンソール CP のまま出すとパイプ先で化けるため明示設定している）。

## コマンド

| コマンド | 役割 |
|---|---|
| `new <slug> [--mode interactive\|autonomous] [--profile full\|light] [--light] [--ticket ID] [--depends a,b,#N] [--parent <親work>] [--backlog <file>]` | work 作成。`state.yml`/`metrics.yml` を**スキーマ付きで原子的に初期化**し `.aidev/current` を設定。`schema` を刻む。`--backlog` は backlog 項目から起こした出自（`.aidev/backlog/` 内のファイル名）を刻み、**deliver での消し込みを `verify` が強制**する（存在しないファイルは着手前に弾く）。`--profile`/`--light` は「どこまで工程を回すか」（`protocol.md`「11.」）で **`--mode` と直交**。既定 `full`。subtask は親の `profile` を継承する。**`harnessRev`（ハーネスの版＝aidev-* の内容の tree hash。コミット SHA ではないので squash で割れない）も自動で刻む**——ハーネス改修の効果検証で母集団を特定するための刻印で、手書きに任せると忘れられ、忘れられた work は母集団から静かに漏れる（`schema:` を `new` 一本化したのと同じ理由）。取れない環境は `unknown`。`protocol.md`「12.」 |
| `event <phase> <start\|sent_back> [k=v ...]` | `metrics.yml` に **UTC 時刻を自分で打って**イベント追記。`metrics.yml` 不在なら自動生成。`events: []` も block 形式へ変換。 |
| `approve <phase> [k=v ...]` | `state.yml` の `approved` 追記（冪等）＋ `current` 更新 ＋ approved イベント追記を一括・検証付きで。`deliver` のときは **`harnessRevDelivered`** も刻み（`harnessRev` と違えば**またがり work**＝効果検証の母集団から除外）、**母集団が揃った条項をその場で通知**する——条項の母集団が増える瞬間は deliver の1点で、`doctor` の WARN は既に見に行った人にしか届かないため。`protocol.md`「12.」 |
| `unapprove <phase> [--slug <work>]` | 差し戻しで無効化される後工程の**承認を取り消す**。`approved` から当該工程を外し、`current` をそこへ戻す。**記録は消さない**——取り消し自体を `sent_back` イベントとして刻む（手戻りは実際に起きた事実なので、消すと `reworks`/`sent_backs` が過小になる）。子の `review` を取り消したときは**親の `activeSubtask` もその子へ戻す**（`aidev-60-review` の統合差し戻し手順）。元は「`approved` から手で除く（CLI に削除は設けていない）」だったが、それは `state.yml` の更新を CLI に集約する原則と矛盾し、しかも手順だけあって手段が無かった。 |
| `guard <phase>` | 工程開始時の**前提チェック**（前提成果物の有無・前提工程の承認・`dependsOn` 充足）。未充足なら非ゼロ終了。 |
| `verify [slug] [--strict]` | 現在(または指定)work の**不変条件**を version-aware に検査。違反で非ゼロ終了。**deliver の commit 前ゲート**に使う。deliver 承認済で `backlog:` 刻印がある work は、**その backlog ファイルに自分の slug が現れること**も検査する（消し込み忘れの検知。`protocol.md`「2.9」）。`profile: light` の work では**条件逸脱**も見る——任意工程の実施と `files_changed` の上限超過（`.aidev/config.yml` の `lightMaxFiles`、既定 3）。**WARN 止まりで exit code は変えない**（昇格漏れは事後検知。硬ゲートは既存判定に任せる）。<br>**`--strict`**: **記録漏れ（`event` の start 欠落）だけ**を致命（exit 5）にする。機械ゲート（Claude Code の `Stop` フック等）専用の入口。既定を FAIL に変えると start が欠けた過去の work が deliver できなくなるため、入口を分けた。**light の逸脱は strict でも致命にしない**——記録漏れは「今しか直せない」（metrics は追記のみで当時の timestamp は復元不能）が、light の昇格は人間の判断だから。 |
| `escalate [slug]` | `profile` を **`light` → `full` に片方向で昇格**（`protocol.md`「11.」）。`full` からは戻せない。`state.yml` の手編集を避け、昇格を単一の検証済み経路に集約するためのコマンド。`decisions.md` への経緯記録と `escalated_from_light=1` の付与は skill 側の仕事。 |
| `doctor` | 全 work を横断検査しドリフトを報告（legacy は免除）。retro/insights の冒頭で事後検知に使う。続けて **backlog ファイル自体**も横断検査する（全消化した `split`・`topic` の退避漏れ／`kind` frontmatter の欠落と誤記／`status` が数えない書式の項目／`archive/` に残った未消化）。**WARN 止まりで exit code は works の fail だけで決める**（ファイルの一生には持ち主の work がおらず `verify` で硬ゲートにできないため。`protocol.md`「2.9」）。続けて **条項ファイル**（`docs/aidev/`）も検査する（`status` の欠落・誤記／**母集団が揃ったのに未判定**／**`confirmed` の移送漏れ**＝二重管理予備軍／終状態の退避漏れ／**索引漏れ**＝索引ファイル（既定 `AGENTS.md`。`conventionsIndex` で変更可）の `aidev:conventions` ブロックに無い＝自動読込されず読まれないまま「効かなかった」と誤判定される／移送後の**張り替え漏れ**）。索引の WARN は**足すべき行をそのまま示す**（検査だけあって直す手が無い形にしない）。こちらも同じ理由で WARN 止まり。 |
| `status [--subtasks] [--format table\|tsv]` | **読み取り専用**。全 work を横断（work/ticket/mode/current/next/done/deps）＋ backlog（`*.md`・`archive/` 除く）の未着手件数（todo/needs）と **`inflight`（そのファイルの項目を掴んだまま未 deliver の work 数）**を機械抽出。backlog 行が `[x]` になるのは deliver なので、着手中の項目は `todo` からは区別できない——`inflight` はそこを埋め、**別セッションが同じ項目を二重に選ぶのを防ぐ**（`protocol.md`「2.9」）。`aidev-00-start` の状況把握に使う。既定は人間可読表、`--format tsv` は機械パース向け（先頭列 `work`/`backlog`/**`subtask`** でレコード種別を判別）。**`--subtasks`** を付けると分割 work の子（`subtask / <親>/<子> / current / done` の4列。work 行の8列とは列数が違う）も出す——`.aidev/current` は未追跡でセッションをまたぐと消えるので、**復帰時にどの子へ戻るかはこれで確認する**。 |
| `metrics [slug] [--all] [--phases] [--format table\|tsv]` | **読み取り専用**。`metrics.yml` のイベントログから protocol §8 の派生指標を集計。既定 per-work（first_start/delivered/lead_sec/reworks/sent_backs）、`--phases` で工程別（phase/start/approved/elapsed_sec）。`--all` で全 work。`aidev-util-insights` の集計に使う。ts は `Z`/`UTC`/無しを許容。 |
| `use [<slug>]` | 継続する作業を切り替える（`.aidev/current` を書く）。引数なしなら現在値を表示。存在しない slug は弾く。**`new` と `approve` 以外に current を書く手段が無かった**ため、「続きから」は手書きに頼っていた。 |
| `backlog new <name> --kind standing\|split\|topic [--parent <p>] [--priority <n>]` | frontmatter 付きで backlog ファイルを起こす。**`--kind` を必須**にして欠落を構造的に防ぐ（`split` は `--parent` 必須）。 |
| `convention new <id> --hypothesis <text> --baseline <text> [--source <p>] [--verify-after <n>]` | PJ規約の条項を `docs/aidev/` に起こす（場所は `.aidev/config.yml` の `conventionsDir`。既定 `docs/aidev`）。**`--hypothesis` と `--baseline` を必須**にして「検証できない条項」を構造的に防ぐ。`--baseline` は**導入前にその観点の指摘が何件あったか**——**条項 id は起票のその瞬間に生まれる**ので、導入前の review.md にその id は現れず、**id 別の前後比較は原理的にできない**（必ず `0 → N` と増える）。「前」を作れるのは起票時に観点で数えて刻む道だけ。数えられないならその事実を値に書く（捏造も空欄も不可）。`--hypothesis` は——「どの指標がどう動けば成功か」を先に書かないと、後から見た指標は常に何かしら動いているので都合のいい説明がつき、検証ではなく事後の物語作りになる。archive に同 id があれば**重複として弾く**（移送済み規約の再提案）。起票時に**索引へ足すべき行**と、`.aidev/config.yml` の `docsRoots`（既存 docs との重複を確認する場所。未設定なら「確認していない旨を明記せよ」）を出力する。`protocol.md`「12.」 |
| `convention confirm <id> [--result <text>]` | 効果ありと判定（`status: confirmed`）。次は PJ ドキュメントへの移送。 |
| `convention promote <id> --to <path#anchor>` | 本文を PJ docs へ移した**後**に打つ。**破壊の前に**「条項ファイルか（frontmatter がある）」「id にパス成分が無いか」「退避先が空か」を検査する——この3つを後回しにしていたため、無関係な md を 0 バイトにする／`../foo` で条項ディレクトリ外を壊す／衝突時に本文だけ消える、の3件が実際に起きた。`promoted_to`/`promoted_at` を刻み、**本文を捨てて tombstone 化**して `archive/` へ退避する（本文の在処を常に1箇所に保ち二重管理を防ぐ）。**移送先ファイルの実在を検査**する（dangling な `promoted_to` は「本文がどこにも無い」状態を作るため）。tombstone を消さないのは**重複排除**のため。 |
| `convention retire <id> --status ineffective\|superseded [--note <t>]` | 退役して退避。`ineffective` は「条項が誤り」ではなく「**散文層の限界に当たった**」可能性がある（DESIGN「2.6」）ので、CLI/フック層へ寄せる検討を促す。 |
| `convention status [--format table\|tsv]` | **読み取り専用**。条項の `status` / `introduced` / **`pop`（母集団＝導入日以降に着手し **deliver 済み**の work 件数）** / `need` / **`ready`（判定可能か）** / **`index`（索引に載っているか）** / `promoted_to` を一覧。`aidev-util-insights` の縦断分析の入口。 |
| `backlog archive [<file>...] [--force]` | 消化しきった backlog（`split`/`topic` で全項目 `[x]`）を `archive/` へ退避。無指定なら条件を満たすものだけ。**判定は `doctor` の WARN と同じ関数**を通る。`mv` のみで **git は触らない**（`verify && commit` 方針）。 |
| `worktree add <slug> [--branch n] [--base ref] [--path dir] [--mode m] [--ticket id] [--depends list]` | **ユーザー責任の並行作業 on-ramp**。work 専用の git worktree（既定 `<repo>-wt/<slug>`）と `feature/<slug>` ブランチ（既定 base=HEAD）を作る。worktree 内に該当 slug の work が無ければ `new` を委譲し（add 内で new）、有れば current 設定のみ。**main tree の `.aidev/current` は書き換えない（INV-1）**。完了時に共有ファイル警告を出す——名指しする対象は `.aidev/config.yml` の `sharedFiles`（例 `sharedFiles: [package.json, src/registry.ts]`）から取り、未設定なら汎用文言にフォールバックする（PJ 固有名を CLI に埋めない）。 |
| `worktree list [--format table\|tsv]` | **読み取り専用**。aidev 管理 worktree（判定キー = worktree ローカル `.aidev/current` の有無）を path/branch/work/phase で一覧。`--format tsv` の先頭列は `worktree`。 |
| `worktree rm <slug\|path> [--force] [--delete-branch]` | worktree を撤去。未コミット差分があれば**既定で拒否**（`--force` で強制）。ブランチ削除は `--delete-branch` 指定時のみ。main の current は不変。 |

> worktree は **`.aidev/current` が gitignore 対象＝worktree ローカル**である性質に乗る（worktree 間で current は非共有）。
> 並列の要否判断はハーネスではなく**ユーザー**が行う（明示 `worktree add` のみがトリガ）。既存 work を継続する場合は、
> その work の成果物が**コミット済み**でブランチに乗っている必要がある（未コミットの work フォルダは worktree に伝播しない）。

`k=v` は `metrics.yml` の `metrics:` マップになる（例: `approve plan tasks_planned=4` /
`approve test passed=12 failed=0` / `approve review must=0 should=1 nit=2`）。
> **`approved` は `event` では書けない**——`event` は `metrics.yml` にしか書かないので、
> `state.yml` の `approved` と乖離した work ができてしまう（`verify` はイベント対が壊れないので検知できない）。

## テストの走らせ方

```sh
sh test/run.sh                      # 処理系は自動判定（pwsh → powershell の順）
AIDEV_PS_HOST=winps sh test/run.sh  # Windows PowerShell 5.1 を明示指定
sh test/setup-pwsh.sh               # pwsh が無ければ入れる（版固定・SHA-256 照合つき）
```

**`AIDEV_PS_HOST` で処理系を明示できる**（`pwsh` / `winps`）。pwsh 7 と Windows PowerShell 5.1 が
両方入っている環境（GitHub Actions の `windows-latest` がまさにそれ）では、自動判定は pwsh を選ぶので、
**ps1 の本来の対象である 5.1 が一度も走らないまま緑になる**。CI は3通り（ubuntu/pwsh・windows/pwsh・
windows/winps）を回す。

`RESULT` の `skip` は**未実行のアサート数**で、`skip>0` はそのまま未検証の穴。
CI ではこれを失敗として扱う（`.github/workflows/aidev-cli.yml`）。

## 終了コード

| code | 意味 |
|---|---|
| 0 | OK |
| 1 | 使用法・環境エラー（`.aidev` 不在、未知コマンド等） |
| 2 | 前提成果物／前提工程の不足（guard） |
| 3 | 依存（`dependsOn`）未充足（guard） |
| 4 | 不変条件違反（verify）／**ドリフト検知（doctor）** |
| 5 | 記録漏れ（`verify --strict` のときのみ。既定の `verify` は WARN 止まりで 0） |

## schema の履歴（version-aware verify。「PJと一緒に育てる」ための要）

`new` が `state.yml` に `schema: <N>` を刻む。`verify`/`doctor` は **その work の `schema` 以上で導入された
不変条件だけ**を強制する。`schema` 未記載の旧 work は **legacy として免除**（「過去分は捏造しない」方針。
`protocol.md`「8.」）。これにより新ガードを足しても**過去 work を遡及的に違反扱いしない**。

- 現行 `CURRENT_SCHEMA = 5`。
- schema 3: subtask 層（`subtasks`/`activeSubtask`/`parent`）を導入。schema ≤ 2 の work は subtask 不変条件を免除。
- schema ≥ 2 の不変条件: `metrics.yml` の存在 ／ review 承認済なら `review.md` 存在 ／ deliver 承認済なら
  metrics に deliver の approved イベントが存在。
- schema ≥ 4 の検査: `harnessRev` の存在（**WARN**）／ **またがり work**（`harnessRev` ≠ `harnessRevDelivered`。**`note:`**）。
- schema ≥ 5 の検査（**FAIL**）: **承認済み工程の成果物が実在するか**（`requirement.md` / `spec.md` /
  `plan.md` / `tasks.md`）。これが無いと**成果物を1つも作らずに全工程 approve した work が
  「deliver 済み・verify OK」になる**。subtask は親の `requirement/spec/design` を継承し、
  分割 work の親は `tasks.md` を持たない（各 subtask の plan が作る）。
- **分割 work の親を verify すると子も検査する**（着地するのは親1本の PR なので、
  子だけ記録が欠けていても素通りしてしまう）。数え方は `doctor` と揃えてある。
  またがりが WARN でないのは、**事後に取り消せない事実**で人が直せることが無いから。ハーネスを
  1回コミットしただけで in-flight の全 work が鳴き続けるので、「いま直せる」WARN（記録漏れ・light 逸脱）
  と同列に置くとそちらが埋もれる。
  `verify` は deliver 承認の**前**に走るので `harnessRevDelivered` をまだ持っていない。着地時の刻印を
  待つと**この検査は通常の順序では一度も発火しない**ため、まだ無いときは**現在の版**と比べる。
  効果検証の母集団を正しく切るための刻印なので、旧 work は遡って違反扱いしない（`protocol.md`「12.」）。
- 新しい不変条件を足すときは `CURRENT_SCHEMA` を上げ、検査をそのバージョン以上に限定する。

## deliver ゲートの使い方（`land` を別コマンドにしない理由）

破壊的な git 操作を CLI に持たせない（移植性・安全性）。deliver の commit 前に **`verify` を通し、
成功時のみコミット**する：

```sh
.claude/skills/aidev-docs/bin/aidev verify && git commit ...   # verify 失敗なら commit しない
```

## 依存（dependsOn）の判定

- `works slug`（例 `20260620-ruler-display`）→ その work の `approved` に `deliver` が含まれれば充足。
- 外部チケット（`#N`、または `PROJ-123` のような英字始まり・数字終わりの ID）→ 自動判定はせず **advisory**（警告のみ。CLI/API 連携は PJ 側 tracker に委ねる）。

## 設計メモ

- YAML は**フロー形式前提**の最小読み取り（`key: value` / `key: [a, b]`）。複雑な YAML は扱わない。
- 行の差し替えは `awk`（sh）／配列再構築（ps1）で行い、`sed` エスケープ事故を避ける。
- 出力は UTF-8（BOM なし）・LF で書き出し、git 差分を OS 間で安定させる。
