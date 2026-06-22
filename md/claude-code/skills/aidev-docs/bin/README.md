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
# Windows PowerShell 5.1 の場合: powershell -File .claude\skills\aidev-docs\bin\aidev.ps1 <command> ...
```

## コマンド

| コマンド | 役割 |
|---|---|
| `new <slug> [--mode interactive\|autonomous] [--ticket ID] [--depends a,b,#N]` | work 作成。`state.yml`/`metrics.yml` を**スキーマ付きで原子的に初期化**し `.aidev/current` を設定。`schema` を刻む。 |
| `event <phase> <start\|approved\|sent_back> [k=v ...]` | `metrics.yml` に **UTC 時刻を自分で打って**イベント追記。`metrics.yml` 不在なら自動生成。`events: []` も block 形式へ変換。 |
| `approve <phase> [k=v ...]` | `state.yml` の `approved` 追記（冪等）＋ `current` 更新 ＋ approved イベント追記を一括・検証付きで。 |
| `guard <phase>` | 工程開始時の**前提チェック**（前提成果物の有無・前提工程の承認・`dependsOn` 充足）。未充足なら非ゼロ終了。 |
| `verify [slug]` | 現在(または指定)work の**不変条件**を version-aware に検査。違反で非ゼロ終了。**deliver の commit 前ゲート**に使う。 |
| `doctor` | 全 work を横断検査しドリフトを報告（legacy は免除）。retro/insights の冒頭で事後検知に使う。 |
| `status [--format table\|tsv]` | **読み取り専用**。全 work を横断（work/ticket/mode/current/next/done/deps）＋ backlog（`*.md`・`archive/` 除く）の未着手件数（todo/needs）を機械抽出。`aidev-00-start` の状況把握に使う。既定は人間可読表、`--format tsv` は機械パース向け（先頭列 `work`/`backlog` でレコード種別を判別）。 |
| `metrics [slug] [--all] [--phases] [--format table\|tsv]` | **読み取り専用**。`metrics.yml` のイベントログから protocol §8 の派生指標を集計。既定 per-work（first_start/delivered/lead_sec/reworks/sent_backs）、`--phases` で工程別（phase/start/approved/elapsed_sec）。`--all` で全 work。`aidev-util-insights` の集計に使う。ts は `Z`/`UTC`/無しを許容。 |
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
