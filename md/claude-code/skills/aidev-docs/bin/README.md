# aidev ランタイムガード CLI

aidev ハーネスの **state.yml / metrics.yml 更新を「単一の検証済み経路」に集約**し、工程の前提と
不変条件を**決定的に**検査するためのコマンド群。散文規約（=ソフト強制）に対する**ハード強制の土台**。

- **Node 非依存**。`aidev` は POSIX sh（`sed`/`awk`/`grep`/`date` のみ）、`aidev.ps1` は Windows PowerShell。
- 両者は**挙動・出力・終了コードを一致**させてある（OS 差をここで吸収）。
- hooks は使わない方針のため自動割り込みはしない。**各 skill がこの CLI を呼ぶ**ことで強制力を得る
  （「正しいやり方＝ガードされたやり方」にする）。最後の砦は deliver の `verify` ゲートと `doctor` の事後検知。

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
| `new <slug> [--mode interactive\|autonomous] [--profile full\|light] [--light] [--ticket ID] [--depends a,b,#N] [--backlog <file>]` | work 作成。`state.yml`/`metrics.yml` を**スキーマ付きで原子的に初期化**し `.aidev/current` を設定。`schema` を刻む。`--backlog` は backlog 項目から起こした出自（`.aidev/backlog/` 内のファイル名）を刻み、**deliver での消し込みを `verify` が強制**する（存在しないファイルは着手前に弾く）。`--profile`/`--light` は「どこまで工程を回すか」（`protocol.md`「11.」）で **`--mode` と直交**。既定 `full`。subtask は親の `profile` を継承する。 |
| `event <phase> <start\|approved\|sent_back> [k=v ...]` | `metrics.yml` に **UTC 時刻を自分で打って**イベント追記。`metrics.yml` 不在なら自動生成。`events: []` も block 形式へ変換。 |
| `approve <phase> [k=v ...]` | `state.yml` の `approved` 追記（冪等）＋ `current` 更新 ＋ approved イベント追記を一括・検証付きで。 |
| `guard <phase>` | 工程開始時の**前提チェック**（前提成果物の有無・前提工程の承認・`dependsOn` 充足）。未充足なら非ゼロ終了。 |
| `verify [slug]` | 現在(または指定)work の**不変条件**を version-aware に検査。違反で非ゼロ終了。**deliver の commit 前ゲート**に使う。deliver 承認済で `backlog:` 刻印がある work は、**その backlog ファイルに自分の slug が現れること**も検査する（消し込み忘れの検知。`protocol.md`「2.9」）。`profile: light` の work では**条件逸脱**も見る——任意工程の実施と `files_changed` の上限超過（`.aidev/config.yml` の `lightMaxFiles`、既定 3）。**WARN 止まりで exit code は変えない**（昇格漏れは事後検知。硬ゲートは既存判定に任せる）。 |
| `escalate [slug]` | `profile` を **`light` → `full` に片方向で昇格**（`protocol.md`「11.」）。`full` からは戻せない。`state.yml` の手編集を避け、昇格を単一の検証済み経路に集約するためのコマンド。`decisions.md` への経緯記録と `escalated_from_light=1` の付与は skill 側の仕事。 |
| `doctor` | 全 work を横断検査しドリフトを報告（legacy は免除）。retro/insights の冒頭で事後検知に使う。続けて **backlog ファイル自体**も横断検査する（全消化した `split`・`topic` の退避漏れ／`kind` frontmatter の欠落と誤記／`status` が数えない書式の項目／`archive/` に残った未消化）。**WARN 止まりで exit code は works の fail だけで決める**（ファイルの一生には持ち主の work がおらず `verify` で硬ゲートにできないため。`protocol.md`「2.9」）。 |
| `status [--format table\|tsv]` | **読み取り専用**。全 work を横断（work/ticket/mode/current/next/done/deps）＋ backlog（`*.md`・`archive/` 除く）の未着手件数（todo/needs）と **`inflight`（そのファイルの項目を掴んだまま未 deliver の work 数）**を機械抽出。backlog 行が `[x]` になるのは deliver なので、着手中の項目は `todo` からは区別できない——`inflight` はそこを埋め、**別セッションが同じ項目を二重に選ぶのを防ぐ**（`protocol.md`「2.9」）。`aidev-00-start` の状況把握に使う。既定は人間可読表、`--format tsv` は機械パース向け（先頭列 `work`/`backlog` でレコード種別を判別）。 |
| `metrics [slug] [--all] [--phases] [--format table\|tsv]` | **読み取り専用**。`metrics.yml` のイベントログから protocol §8 の派生指標を集計。既定 per-work（first_start/delivered/lead_sec/reworks/sent_backs）、`--phases` で工程別（phase/start/approved/elapsed_sec）。`--all` で全 work。`aidev-util-insights` の集計に使う。ts は `Z`/`UTC`/無しを許容。 |
| `use [<slug>]` | 継続する作業を切り替える（`.aidev/current` を書く）。引数なしなら現在値を表示。存在しない slug は弾く。**`new` と `approve` 以外に current を書く手段が無かった**ため、「続きから」は手書きに頼っていた。 |
| `backlog new <name> --kind standing\|split\|topic [--parent <p>] [--priority <n>]` | frontmatter 付きで backlog ファイルを起こす。**`--kind` を必須**にして欠落を構造的に防ぐ（`split` は `--parent` 必須）。 |
| `backlog archive [<file>...] [--force]` | 消化しきった backlog（`split`/`topic` で全項目 `[x]`）を `archive/` へ退避。無指定なら条件を満たすものだけ。**判定は `doctor` の WARN と同じ関数**を通る。`mv` のみで **git は触らない**（`verify && commit` 方針）。 |
| `worktree add <slug> [--branch n] [--base ref] [--path dir] [--mode m] [--ticket id] [--depends list]` | **ユーザー責任の並行作業 on-ramp**。work 専用の git worktree（既定 `<repo>-wt/<slug>`）と `feature/<slug>` ブランチ（既定 base=HEAD）を作る。worktree 内に該当 slug の work が無ければ `new` を委譲し（add 内で new）、有れば current 設定のみ。**main tree の `.aidev/current` は書き換えない（INV-1）**。完了時に languageId 波及・原典照合の注意を出力。 |
| `worktree list [--format table\|tsv]` | **読み取り専用**。aidev 管理 worktree（判定キー = worktree ローカル `.aidev/current` の有無）を path/branch/work/phase で一覧。`--format tsv` の先頭列は `worktree`。 |
| `worktree rm <slug\|path> [--force] [--delete-branch]` | worktree を撤去。未コミット差分があれば**既定で拒否**（`--force` で強制）。ブランチ削除は `--delete-branch` 指定時のみ。main の current は不変。 |

> worktree は **`.aidev/current` が gitignore 対象＝worktree ローカル**である性質に乗る（worktree 間で current は非共有）。
> 並列の要否判断はハーネスではなく**ユーザー**が行う（明示 `worktree add` のみがトリガ）。既存 work を継続する場合は、
> その work の成果物が**コミット済み**でブランチに乗っている必要がある（未コミットの work フォルダは worktree に伝播しない）。

`k=v` は `metrics.yml` の `metrics:` マップになる（例: `approve plan tasks_planned=4` /
`event test approved passed=12 failed=0` / `approve review must=0 should=1 nit=2`）。

## 終了コード

| code | 意味 |
|---|---|
| 0 | OK |
| 1 | 使用法・環境エラー（`.aidev` 不在、未知コマンド等） |
| 2 | 前提成果物／前提工程の不足（guard） |
| 3 | 依存（`dependsOn`）未充足（guard） |
| 4 | 不変条件違反（verify/doctor） |

## version-aware verify（「PJと一緒に育てる」ための要）

`new` が `state.yml` に `schema: <N>` を刻む。`verify`/`doctor` は **その work の `schema` 以上で導入された
不変条件だけ**を強制する。`schema` 未記載の旧 work は **legacy として免除**（「過去分は捏造しない」方針。
`protocol.md`「8.」）。これにより新ガードを足しても**過去 work を遡及的に違反扱いしない**。

- 現行 `CURRENT_SCHEMA = 2`。
- schema ≥ 2 の不変条件: `metrics.yml` の存在 ／ review 承認済なら `review.md` 存在 ／ deliver 承認済なら
  metrics に deliver の approved イベントが存在。
- 新しい不変条件を足すときは `CURRENT_SCHEMA` を上げ、検査をそのバージョン以上に限定する。

## deliver ゲートの使い方（`land` を別コマンドにしない理由）

破壊的な git 操作を CLI に持たせない（移植性・安全性）。deliver の commit 前に **`verify` を通し、
成功時のみコミット**する：

```sh
.claude/skills/aidev-docs/bin/aidev verify && git commit ...   # verify 失敗なら commit しない
```

## 依存（dependsOn）の判定

- `works slug`（例 `20260620-ruler-display`）→ その work の `approved` に `deliver` が含まれれば充足。
- 外部チケット（`#N`）→ 自動判定はせず **advisory**（警告のみ。CLI/API 連携は PJ 側 tracker に委ねる）。

## 設計メモ

- YAML は**フロー形式前提**の最小読み取り（`key: value` / `key: [a, b]`）。複雑な YAML は扱わない。
- 行の差し替えは `awk`（sh）／配列再構築（ps1）で行い、`sed` エスケープ事故を避ける。
- 出力は UTF-8（BOM なし）・LF で書き出し、git 差分を OS 間で安定させる。
