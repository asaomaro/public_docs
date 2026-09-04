# aidev ランタイムガード CLI

aidev ハーネスの **state.yml / metrics.yml 更新を「単一の検証済み経路」に集約**し、工程の前提と
不変条件を**決定的に**検査するためのコマンド群。散文規約（=ソフト強制）に対する**ハード強制の土台**。

- **Node 非依存**。`aidev` は POSIX sh（`sed`/`awk`/`grep`/`find` 等の POSIX ツールのみ）、`aidev.ps1` は Windows PowerShell。
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
| `new <slug> [--mode interactive\|autonomous] [--profile full\|light] [--light] [--ticket ID] [--depends a,b,#N] [--parent <親work>] [--backlog <file>] [--backlog-item <text>]` | work 作成。`state.yml`/`metrics.yml` を**スキーマ付きで原子的に初期化**し `.aidev/current` を設定。`schema` を刻む。`--backlog` は backlog 項目から起こした出自（`.aidev/backlog/` 内のファイル名）を刻み、**deliver での消し込みを `verify` が強制**する（存在しないファイルは着手前に弾く）。`--backlog-item` は**掴んだ行の文言**を刻む——`backlog:` はファイル名までしか持たないので、並行 N 本が同じファイルの別項目を掴んでいると `inflight` は件数しか言えず、**どの行が空いているか**を機械が答えられない。刻むと `status` の `HELD` に行単位で出て、同じ項目を 2 本が作業中なら警告する。`--profile`/`--light` は「どこまで工程を回すか」（`protocol.md`「11.」）で **`--mode` と直交**。既定 `full`。subtask は親の `profile` を継承する。**`harnessRev`（ハーネスの版＝aidev-* の内容の tree hash。コミット SHA ではないので squash で割れない）も自動で刻む**——ハーネス改修の効果検証で母集団を特定するための刻印で、手書きに任せると忘れられ、忘れられた work は母集団から静かに漏れる（`schema:` を `new` 一本化したのと同じ理由）。取れない環境は `unknown`。`protocol.md`「12.」 |
| `event <phase> <start\|sent_back> [k=v ...]` | `metrics.yml` に **UTC 時刻を自分で打って**イベント追記。`metrics.yml` 不在なら自動生成。`events: []` も block 形式へ変換。 |
| `approve <phase> [k=v ...]` | `state.yml` の `approved` 追記（冪等）＋ `current` 更新 ＋ approved イベント追記を一括・検証付きで。**`plan` / `requirement` / `review` のときは被覆メトリクス（`ac_total` / `ac_covered` / `tasks_no_ac` / `tasks_ac_none`）を `requirement.md` と `tasks.md` から算出して自動で刻む**（手書きの `key=value` に任せない。`harnessRev` や `schema` を `new` に一本化したのと同じ理由で、手書きの値は忘れられる。`ac_total=` を明示指定したときだけその値を尊重する。tasks.md がまだ無い工程では刻まない）。`deliver` のときは **`harnessRevDelivered`** も刻み（`harnessRev` と違えば**またがり work**＝効果検証の母集団から除外）、**母集団が揃った条項をその場で通知**する——条項の母集団が増える瞬間は deliver の1点で、`doctor` の WARN は既に見に行った人にしか届かないため。`protocol.md`「12.」<br>**`task_check_mode=` は enum 検証**する（`delegated`\|`same_session` 以外は弾く——タイポを通すと層別が静かに壊れる）。**同じラウンドの打ち直しには `amend=yes` を自動で付ける**（直近の approved のあとに start が無ければ訂正とみなす）。`verify` のイベント対検査はこの印をラウンド数から除く——付けないと「approve を打ち直せ」という WARN の指示が別の WARN を生む。 |
| `unapprove <phase> [--slug <work>]` | 差し戻しで無効化される後工程の**承認を取り消す**。`approved` から当該工程を外し、`current` をそこへ戻す。**記録は消さない**——取り消し自体を `sent_back` イベントとして刻む（手戻りは実際に起きた事実なので、消すと `reworks` が過小になる）。**ただし `by: unapprove` を併記し、差し戻し回数（`metrics` の `sent_backs` と `debug status`／`maxSendBacks` の判定）からは除外する**——差し戻しの原因は指摘のあった 1 工程で、後工程の取り消しはその結果だから。除外しないと、規約どおり `unapprove` した work だけ数が 3 倍になり work 間で比較できない。子の `review` を取り消したときは**親の `activeSubtask` もその子へ戻す**（`aidev-60-review` の統合差し戻し手順）。元は「`approved` から手で除く（CLI に削除は設けていない）」だったが、それは `state.yml` の更新を CLI に集約する原則と矛盾し、しかも手順だけあって手段が無かった。 |
| `guard <phase>` | 工程開始時の**前提チェック**（前提成果物の有無・前提工程の承認・`dependsOn` 充足）。未充足なら非ゼロ終了。**subtask では `plan`/`coding`/`test`/`review` 以外を拒否**する（それ以外は親 work 専用。exit 2）。OK のときは `aidev event <phase> start` を忘れないよう促す。 |
| `verify [slug] [--strict]` | 現在(または指定)work の**不変条件**を version-aware に検査。違反で非ゼロ終了。**deliver の commit 前ゲート**に使う。deliver 承認済で `backlog:` 刻印がある work は、**その backlog ファイルの `- [x]` 行かその継続行に自分の slug が現れること**も検査する（消し込み忘れの検知。下の「backlog の消し込み検査」。`protocol.md`「2.9」）。`profile: light` の work では**条件逸脱**も見る——任意工程の実施／**`spec`・`plan` を個別に起動した**（light の「上流 1 ゲートに畳む」指紋から外れた）／`files_changed` の上限超過（`.aidev/config.yml` の `lightMaxFiles`、既定 3）。**WARN 止まりで exit code は変えない**（昇格漏れは事後検知。硬ゲートは既存判定に任せる）。<br>**`--strict`**: **記録漏れ（`event` の start 欠落）だけ**を致命（exit 5）にする。機械ゲート（Claude Code の `Stop` フック等）専用の入口。既定を FAIL に変えると start が欠けた過去の work が deliver できなくなるため、入口を分けた。**light の逸脱は strict でも致命にしない**——記録漏れは「今しか直せない」（metrics は追記のみで当時の timestamp は復元不能）が、light の昇格は人間の判断だから。 |
| `escalate [slug]` | `profile` を **`light` → `full` に片方向で昇格**（`protocol.md`「11.」）。`full` からは戻せない。`state.yml` の手編集を避け、昇格を単一の検証済み経路に集約するためのコマンド。`decisions.md` への経緯記録と `escalated_from_light=1` の付与は skill 側の仕事。 |
| `coverage [slug] [--format table\|tsv] [--strict]` | **読み取り専用**。受け入れ基準（`AC`）の**被覆率**と `tasks.md` の**整合**を検査する。出所は spec-kit の `/analyze` が出す `Coverage % (requirements with >=1 task)`。対応付けの正典は **`tasks.md` の `AC:` 継続行**（`対象:` `依存:` と同じ形）で、AC の本文は `requirement.md` にしか置かない（ID で参照するだけなので二重管理にならない）。出す gap は 2 種類——**struct**（タスク ID の重複／未定義の `AC` を参照／自己依存／`依存` が未定義のタスクを指す／`依存` が循環）と **cover**（`AC:` 行の書き忘れ／`AC:` 行が空／タスクに落ちていない `AC`／**`requirement.md` に受け入れ基準が 1 件も無い**＝被覆 100% ではなく**測れていない**）。表の列は `ac / spec / tasks` で、**`spec` は `spec.md` に当該 AC の箇条書きがあるかの参考列**（gap は立てない。`coverage-summary` に `spec=N/M(P%)` として出る）。`--strict` は gap があれば **exit 4** で、**plan の承認前ゲート**に使う（`aidev-30-plan` の手順6）。**被覆メトリクスを刻むのは家族の根の work だけ**（subtask では刻まない）——家族単位の値を子ごとに刻むと `metrics --all` の足し上げで分母が subtask 数だけ多重計上される。<br>**ID の文法**: `AC<数字>` / `AC-<英数>`（`AC` の直後に英字が続く `ACL` `ACCESS` は基準ではない）、タスクは `T<数字>`（`T1-1` も別 ID）。**`no_ac` 列は「`AC:` 行を書き忘れた／空にしたタスクの数」**（明示的な `AC: なし` は数えない）。**入力は BOM と行末 CR を落としてから読む**（落とさないと Windows チェックアウトの `tasks.md` で判定が OS ごとに割れる）。空白は **ASCII のみ**を空白として扱う（sh の `[[:space:]]` と ps1 の `[ \t]` を揃えてある）。<br>**被覆は work 全体（親＋全 subtask）で見る**——subtask は親の `requirement.md` を継承するので、自分の slice だけを見ると兄弟が担当する `AC` が必ず「タスクが無い」になり、**誰にも直せない gap** が恒久的に残る。親から打っても子から打っても同じ表が出る。plan 未実施の subtask が残っている間は cover の gap を致命にしない（最初の subtask の plan が、兄弟の担当ぶんまで背負って通らなくなる）。`verify` も**家族の根でだけ**報告する（子ごとに同じ WARN を重複させない）。`tasks.md` がまだ無い段階は**正常な空**として exit 0（`convention status` と同じ扱い。読み取り専用コマンドがエラー経路を作らない）。review では**再実行して spec と実装の乖離を見る**（spec-kit の `/converge` に相当。追記でなく毎回同じ入力から同じ表を出す）。 |
| `debug <start\|report\|status> ...` | **詰まったときの原因究明を有限化する**。出所は cc-sdd の `kiro-impl` の debug subagent——発火は「レビュアーが2ラウンド連続で REJECTED」等で、要点は *"runs in a **fresh context** — it receives only the error information, not the failed implementation history. This avoids the context pollution that causes infinite retry loops."* aidev は上限（`maxSendBacks`）を `state.yml` に書くだけで**どこも検査していなかった**（散文の第一層のまま）。<br>`start [slug] [--phase p]` は**委譲の前**に打つ。ラウンド上限（`.aidev/config.yml` の `maxDebugRounds`、既定 2）を検査し、超えていれば exit 4 で止める。渡すもの／**渡さないもの（試行履歴）**を出力する。<br>`report [slug] --root-cause <t> --category <c> --next-action <retry\|block\|stop_for_human> [--phase p] [--confidence high\|medium\|low] [--fix-plan <t>] [--verification <t>]` は結果を受ける（`--fix-plan` / `--verification` が下記「修正方針・確認方法」になる）。**必須フィールドを CLI が強制する**（`convention new` の `--hypothesis`/`--baseline` と同じ入口ゲート——散文の講評だけ返して終わると、何が原因だったのか後から誰にも読めない）。**本文（根本原因・修正方針・確認方法）は `decisions.md`、列挙値は `metrics.yml`** に分ける（metrics はフロー形式の1行なので自由文を入れると壊れる）。<br>`status [--format table\|tsv]` は工程ごとの差し戻し数・デバッグ回数・要否。<br>`aidev event <工程> sent_back` が上限到達をその場で知らせる（気付くのが retro では遅い）。手順・分類・渡すもの/渡さないものは `protocol-debug.md`。 |
| `taskcheck <start\|report\|status> ...` | **タスク単位の独立点検を有限化する**（`protocol-check.md`「(b)」）。`maxTaskCheckRounds` は長らく**散文にしか無い上限**だった——`config.yml` のキーだと書いてあるのに CLI は読まず、`0` を書いても `999` を書いても挙動が変わらなかった（`DESIGN`「3.5」の分類 G）。読めなかったのは「観測できない」からではなく**観測する口が無かった**から——`maxSendBacks` は `event <工程> sent_back`、`maxDebugRounds` は `debug start` という「1ラウンド = 1 コマンド」の形があるから数えられる。タスク点検は `approve coding` 時の**合計**しか届かず、「タスク T の点検が何回目か」が残らなかった。<br>`start <task-id> --mode <delegated\|same_session> [--slug s]` がラウンド上限を検査し、超えていれば **exit 4**（`debug start` と同じ形）。**`--mode` は必須**——点検が効く理由はコンテキスト分離なので、どちらで行ったかを残さないと効果を測れない。出力は「渡すもの／観点2つ／固定の返却形式」を毎回示す。<br>`report <task-id> --findings <n>` が結果を受ける。`--findings` は必須で、**崩れた返答から数字を拾わせない**（件数が読めないなら report を打たず、点検しなかったものとして扱う）。`start` の無いタスクへの `report` は弾く。<br>`status [--format table\|tsv]` はタスクごとの rounds / findings / 上限到達。<br>**副産物**: `approve coding` が `task_checks` / `task_check_findings` / `task_check_mode` を**この記録から自動で刻む**（被覆・`harnessRev` と同じ理由——手書きの値は忘れられる）。明示指定があればそちらを尊重し、`taskcheck` を1回も打っていない work では刻まない（`0` を書くと「点検していない」と「点検して 0 件」が区別できなくなる）。形態が割れていれば `mixed`。 |
| `limits [show\|set <key> <n>] [--format table\|tsv] [--slug <work>]` | **回数の上限を一覧・設定する**。上限は `state.yml`（work ごと）と `config.yml`（PJ ごと）に散っていて、**どれも設定口が無く手編集しかなかった**（`escalate` / `unapprove` / `--human-gates` を作ったのと同じ矛盾で、「state の更新は単一の検証済み経路に集約する」に反する）。しかも「いまいくつが効いているか」を一望する手段が無く、既定値は各所のコードにしか無かった。<br>一覧は **どこから来た値か**（`config` / `state` / `default`）と scope、既定値まで出す。`set` は**キーと下限を検査**する（`maxDebugRounds` / `maxTaskCheckRounds` は下限 1、`smokeStaleAfter` / `sharedFilesWindow` は 0 で停止可）。scope が `work` のキーは `state.yml`、`pj` は `.aidev/config.yml` に書く。<br>条項の `verify_after` はここに含めない——上限ではなく母集団の**下限**で、項目ごとに違うので `convention new --verify-after` / `convention defer` が正しい口。 |
| `smoke [slug]` | **起動確認 GO/NO-GO**。`.aidev/config.yml` の `smokeCommand`（または `smokeCommands`）を実行し、結果を `metrics.yml` に `event: smoke` として刻む。刻むキーは `result` / `exit_code` / **`commands`（走らせた本数）**、失敗時はさらに **`failed_index`（何本目で落ちたか）**。`smokeCommands` は**上から順に全部**走らせ、**最初に落ちた時点で打ち切る**（原因を1つに絞る）。実行ディレクトリは**リポジトリルート**。出所は cc-sdd の `kiro-verify-completion`——`FEATURE_GO` の条件に「**ビルドした成果物が最初の使える状態に到達した実行結果**」を置き、*"A passing test suite alone is not enough for FEATURE_GO."* と明記している。**CLI が実行して exit code を取る**のは、`--result pass` のような自己申告にすると「手書きの値は都合よく書かれる」形になるから（`harnessRev` を `new` に、被覆を `approve` に一本化したのと同じ理由）。出力は**捕まえずに素通し**する（test 工程が `test-result.md` に貼るのは生の出力）。<br>**exit 0**=pass / **exit 4**=fail / **exit 2**=`smokeCommand` 未設定（**検証していないことを合格にしない**。設定するか `smokeCommand: none` と明示する）。`none` は `result: skip` を刻んで exit 0。<br>実行するシェルは POSIX 側が `sh -c`、Windows 側が `cmd.exe /c`（ps1 が Windows 以外で走るときは `sh -c` で sh 版と一致する）。Windows だけ別のコマンドが要るなら `smokeCommandWindows` を設定する——**単独で設定しない**（POSIX 側では未設定扱いになり、同じ PJ が OS で `configured=yes`/`no` に割れる）。<br>**時間上限**: `smokeTimeoutSec`（既定 300）。常駐コマンドを書かれると自律実行がそこで永久に止まるので、`timeout`(coreutils) がある環境では打ち切って `exit_code: 124` を刻む。**`timeout` が無い環境（Windows を含む）では掛けられない**ので、その事実を出力に残す（黙って無制限にしない）。<br>**記録先は家族の根**（親＋全 subtask で1つ）。子で打っても親の `metrics.yml` に刻む——起動確認は work 全体の性質で、着地するのは親1本の PR だから（被覆を `cov_root()` で家族単位にしたのと同じ理由。片方だけ work 単位だと、子で通した smoke が親の deliver ゲートから見えず誤 FAIL する）。刻む `phase` は工程を問わず `test` 固定。<br>**素通し設計の但し書き**: 子シェル自身が出すエラー文（`sh: 1: …` と `/usr/bin/sh: 1: …`）は起動の仕方の違いで文言が変わりうる。出力一致の契約は**この CLI が出す行**についてのもの。**値は行をそのまま読む**（YAML のエスケープは解釈しない）。全体を `"` で囲んだときだけ1組外すので、**基本はクォートで囲まない**。 |
| `doctor [--quiet]` | 全 work を横断検査しドリフトを報告（legacy は**その版で導入された不変条件（FAIL）だけ**免除。イベント対・light 逸脱・`decisions.md` の WARN と `--strict` の exit 5 は legacy でも走る）。`--quiet` は「OK だけ」の work を行ごと省く（100 works で 9 割が OK 行になり、直すべき WARN が埋もれる）。検査の順は works → backlog → 条項 → ハーネス改修の記録（`.aidev/harness/`。未判定・退避漏れ）→ 起動確認の設定（`smokeCommand`/`smokeCommands` の有無を **PJ 単位で1行**＋宣言が古びていないか）→ **共有ファイル**（`sharedFiles` が実在するか／履歴の常連なのに未宣言／いま複数 worktree が触るのに未宣言）→ **main worktree の位置**（既定ブランチに載っていなければ WARN。`worktree add` は新しい枝を切るときにしか警告しないため）。**`.aidev/works` がまだ無い導入直後でも、works 以外の 6 節は走る**（導入の自己診断に使うため）。条項の検査は下記に加えて本文未記入・退役済み条項の索引 dangling も WARN する。retro/insights の冒頭で事後検知に使う。続けて **backlog ファイル自体**も横断検査する（全消化した `split`・`topic` の退避漏れ／`kind` frontmatter の欠落と誤記／`status` が数えない書式の項目／`archive/` に残った未消化）。**WARN 止まりで exit code は works の fail だけで決める**（ファイルの一生には持ち主の work がおらず `verify` で硬ゲートにできないため。`protocol.md`「2.9」）。続けて **条項ファイル**（`.aidev/conventions/`）も検査する（`status` の欠落・誤記／**母集団が揃ったのに未判定**／**`confirmed` の移送漏れ**＝二重管理予備軍／終状態の退避漏れ／**索引漏れ**＝索引ファイル（既定 `AGENTS.md`。`conventionsIndex` で変更可）の `aidev:conventions` ブロックに無い＝自動読込されず読まれないまま「効かなかった」と誤判定される／移送後の**張り替え漏れ**）。索引の WARN は**足すべき行をそのまま示す**（検査だけあって直す手が無い形にしない）。こちらも同じ理由で WARN 止まり。 |
| `status [--subtasks] [--active] [--format table\|tsv]` | **読み取り専用**。`--active` は deliver 済み work を隠す。`inflight` は **worktree を横断**して数える（現在の tree だけ見ると、並行作業という当の場面で二重選択の防止が効かない）。全 work を横断（work/ticket/mode/current/next/done/deps）＋ backlog（`*.md`・`archive/` 除く）の未着手件数（todo/needs）と **`inflight`（そのファイルの項目を掴んだまま未 deliver の work 数）**を機械抽出。backlog 行が `[x]` になるのは deliver なので、着手中の項目は `todo` からは区別できない——`inflight` はそこを埋め、**別セッションが同じ項目を二重に選ぶのを防ぐ**（`protocol.md`「2.9」）。`aidev-00-start` の状況把握に使う。既定は人間可読表、`--format tsv` は機械パース向け（先頭列 `work`/`backlog`/**`subtask`** でレコード種別を判別）。**`--subtasks`** を付けると分割 work の子（`subtask / <親>/<子> / current / done` の4列。work 行の8列とは列数が違う）も出す——`.aidev/current` は未追跡でセッションをまたぐと消えるので、**復帰時にどの子へ戻るかはこれで確認する**。 |
| `metrics [slug] [--all] [--phases] [--format table\|tsv]` | **読み取り専用**。`metrics.yml` のイベントログから protocol §8 の派生指標を集計。`--phases` は工程ごとに `start`（初回）/`approved`（最後）/`elapsed_sec`（**全ラウンドの合計**）/`rounds`（start の回数）。既定 per-work（first_start/delivered/lead_sec/reworks/sent_backs/**ac/ac_drift**——`ac` は受け入れ基準の総数＝**要求側の規模の分母**（実装側 `files_changed`・分解側 `tasks_planned` に無かった軸）、`ac_drift` は **plan 以降に増えた gap** ＝ spec と実装の乖離。**2点は工程で選ぶ**——基準点は `plan`（light では `requirement`）の**最初**、終点は `review` の**最後**。件数で選ぶと、同じ工程を2回 approve しただけの work が「2点ある＝測れる」に化ける。どちらかが欠ければ `-`＝**測れない**（`0` と読み替えない）。手で `ac_total=` だけ渡した刻印は `ac_covered` が無いので**計算から捨てる**（0 とみなすと乖離を捏造する。明示するなら4キーまとめて渡すこと）。被覆率そのものは plan の承認前ゲートで 100% に張り付くので **KPI にしない**——読むのは差分の方／**harnessRev/straddle**——版で層別し、またがり work を外すための列。deliver 済みのまたがりは verify では鳴らさず、ここで見る）、`--phases` で工程別（phase/start/approved/elapsed_sec）。`--all` で全 work。`aidev-util-insights` の集計に使う。ts は `Z`/`UTC`/無しを許容。 |
| `use [<slug>]` | 継続する作業を切り替える（`.aidev/current` を書く）。引数なしなら現在値を表示。存在しない slug は弾く。**`new` と `approve` 以外に current を書く手段が無かった**ため、「続きから」は手書きに頼っていた。 |
| `backlog new <name> --kind standing\|split\|topic [--parent <p>] [--priority <n>]` | frontmatter 付きで backlog ファイルを起こす。**`--kind` を必須**にして欠落を構造的に防ぐ（`split` は `--parent` 必須）。 |
| `convention new <id> --hypothesis <text> --baseline <text> [--scope <t>] [--source <p>] [--verify-after <n>]` | PJ規約の条項を `.aidev/conventions/` に起こす（`--verify-after` 既定 5）（場所は `.aidev/config.yml` の `conventionsDir`。既定 `.aidev/conventions`）。**`--hypothesis` と `--baseline` を必須**にして「検証できない条項」を構造的に防ぐ。`--baseline` は**導入前にその観点の指摘が何件あったか**——**条項 id は起票のその瞬間に生まれる**ので、導入前の review.md にその id は現れず、**id 別の前後比較は原理的にできない**（必ず `0 → N` と増える）。「前」を作れるのは起票時に観点で数えて刻む道だけ。数えられないならその事実を値に書く（捏造も空欄も不可）。`--hypothesis` は——「どの指標がどう動けば成功か」を先に書かないと、後から見た指標は常に何かしら動いているので都合のいい説明がつき、検証ではなく事後の物語作りになる。archive に同 id があれば**重複として弾く**（移送済み規約の再提案）。起票時に**索引へ足すべき行**と、`.aidev/config.yml` の `docsRoots`（既存 docs との重複を確認する場所。未設定なら「確認していない旨を明記せよ」）を出力する。`protocol.md`「12.」 |
| `convention confirm <id> --result <text> [--force]` | 効果ありと判定（`status: confirmed`）。`--result` 必須。**母集団が `verify_after` 未満なら拒否**（入口の仮説と対になる出口ゲート）。`--force` は `forced: true` を刻む。次は PJ ドキュメントへの移送。 |
| `convention defer <id> --verify-after <n> --note <t>` | 判定を先送り（`pending` のまま必要件数を積み増す。`n` は現在の母集団より大きいこと。理由必須。`deferred`/`defer_note` を刻む）。「示せないなら pending のまま置く」を CLI で表す手段。 |
| `harness new <id> --hypothesis <t> --baseline <t> [--source <p>] [--verify-after <n>]` | **ハーネス改修の仮説登録**（`.aidev/harness/<id>.md`。`--verify-after` 既定 5）。`introduced`（時刻）と `introduced_rev`（今の版）を刻む。条項と同じ入口ゲート。母集団＝導入後に着手し、**またがらずに** deliver した top-level work。 |
| `harness confirm <id> --result <t> [--force]` / `harness retire <id> --status ineffective\|superseded --note <t> [--force]` | 判定して `archive/` へ退避。条項と同じ出口ゲート（母集団未達は拒否。`--force` は `forced: true`）。 |
| `harness status [--format table\|tsv]` | **読み取り専用**（記録がゼロでも exit 0）。改修ごとの `status` / `introduced` / `introduced_rev` / `pop` / `need` / `ready`。`doctor` が未判定を WARN し、`approve deliver` が到達を知らせる。 |
| `convention promote <id> --to <path#anchor>` | 本文を PJ docs へ移した**後**に打つ。**破壊の前に**「条項ファイルか（frontmatter がある）」「id にパス成分が無いか」「退避先が空か」を検査する——この3つを後回しにしていたため、無関係な md を 0 バイトにする／`../foo` で条項ディレクトリ外を壊す／衝突時に本文だけ消える、の3件が実際に起きた。`promoted_to`/`promoted_at` を刻み、**本文を捨てて tombstone 化**して `archive/` へ退避する（本文の在処を常に1箇所に保ち二重管理を防ぐ）。**移送先ファイルの実在を検査**する（dangling な `promoted_to` は「本文がどこにも無い」状態を作るため）。tombstone を消さないのは**重複排除**のため。 |
| `convention retire <id> --status ineffective\|superseded --note <t> [--force]` | 退役して退避（`--note` 必須。`ineffective` は母集団が要る。`superseded` は免除）。`ineffective` は「条項が誤り」ではなく「**散文層の限界に当たった**」可能性がある（DESIGN「2.6」）ので、CLI/フック層へ寄せる検討を促す。 |
| `convention status [--format table\|tsv] [--members <id>]` | **読み取り専用**。条項がゼロでも exit 0（空表＋note）。`--members <id>` は母集団の work 一覧（着手・deliver・`conv_tags`・`violations`。数えるのは行頭 `- [` の指摘行だけで、`[conv:<id>!]` を違反として別に数える。subtask の review.md は親に合算）。条項の `status` / `introduced` / **`pop`（母集団＝導入時刻（`introduced`）以降に着手し **deliver 済み**の work 件数）** / `need` / **`ready`（判定可能か）** / **`index`（索引に載っているか）** / `promoted_to` を一覧。`aidev-util-insights` の縦断分析の入口。 |
| `backlog compact [<file>...]` | `[x]` 行（と継続行）を `archive/<name>-done.md` へ移し、active を薄く保つ。無指定なら `standing` 全部。`verify` の消し込み検査は `-done.md` も見るので過去 work の検査は壊れない。 |
| `backlog archive [<file>...] [--force]` | 消化しきった backlog（`split`/`topic` で全項目 `[x]`）を `archive/` へ退避。無指定なら条件を満たすものだけ。**判定は `doctor` の WARN と同じ関数**を通る。`mv` のみで **git は触らない**（`verify && commit` 方針）。 |
| `worktree add <slug> [--branch n] [--base ref] [--path dir] [--mode m] [--profile p\|--light] [--ticket id] [--depends list] [--backlog file] [--backlog-item text]` | **ユーザー責任の並行作業 on-ramp**。work 専用の git worktree（既定 `<repo>-wt/<slug>`）と `feature/<slug>` ブランチ（既定 base=HEAD）を作る。worktree 内に該当 slug の work が無ければ `new` を委譲し（add 内で new）、有れば current 設定のみ。**main tree の `.aidev/current` は書き換えない（INV-1）**。完了時に共有ファイル警告を出す——名指しする対象は `.aidev/config.yml` の `sharedFiles`（例 `sharedFiles: [package.json, src/registry.ts]`）から取り、未設定なら汎用文言にフォールバックする（PJ 固有名を CLI に埋めない）。 |
| `worktree list [--format table\|tsv]` | **読み取り専用**。aidev 管理 worktree（判定キー = worktree ローカル `.aidev/current` の有無）を path/branch/work/phase/**kind** で一覧（`kind=main` は main tree。`rm` の対象外なので区別できるようにしてある）。`--format tsv` の先頭列は `worktree`。 |
| `worktree files [--planned] [--all] [--format table\|tsv]` | **どのファイルを何本の worktree が触っているか**を実態から出す。`sharedFiles` は人間が書く静的な宣言なので実態から遅れる——実走で「触らない `storage.py` が名指しされ、全 work が触る `cli.py` は名指しされない」という反転が起きた。既定は**未マージの worktree の、2 本以上が重なっているものだけ**（全件は `--all`）。外すのは**既定ブランチにマージ済み**の worktree だけ——deliver 済みで外すのは誤りで、deliver は PR 作成で終わり**マージは人間の仕事**なので、未マージのまま deliver した枝は衝突の相手として現役（実走で 3 本が deliver した瞬間に表が空になり、「マージ順で相手を壊さないか」を見るという当の用途で先に deliver した本ほど何も見えなくなった）。`--planned` は実差分ではなく **`tasks.md` の `対象:` アンカー**を突き合わせる——実差分は「もう書いた後」しか見えず、並行 3 本が同時に上流工程にいる立ち上がり期は構造的に空になる（実測 0 件 → deliver 前 5 件）。宣言は plan 時点で揃うので、**書く前**の重なりはこちらで見る。比較の基点は **main tree の HEAD との merge-base**——既定ブランチにすると、未マージ枝から切った worktree では共有ぶんまで全員の変更に見える（実測で 23 行中 17 行がそれだった）。`--format tsv` の先頭列は `file`。 |
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
| 2 | 前提成果物／前提工程の不足（guard）／未設定（`smoke` の `smokeCommand` 未設定） |
| 3 | 依存（`dependsOn`）未充足（guard） |
| 4 | 不変条件違反（verify）／**ドリフト検知（doctor）**／gap（`coverage --strict`）／失敗（`smoke`）／上限超過（`debug start`） |
| 5 | 記録漏れ（`verify --strict` のときのみ。既定の `verify` は WARN 止まりで 0） |

## schema の履歴（version-aware verify。「PJと一緒に育てる」ための要）

`new` が `state.yml` に `schema: <N>` を刻む。`verify`/`doctor` は **その work の `schema` 以上で導入された
不変条件だけ**を強制する。`schema` 未記載の旧 work は **legacy として免除**（「過去分は捏造しない」方針。
`protocol.md`「8.」）。これにより新ガードを足しても**過去 work を遡及的に違反扱いしない**。

- 現行 `CURRENT_SCHEMA = 10`。
- schema 3: subtask 層（`subtasks`/`activeSubtask`/`parent`）を導入。schema ≤ 2 の work は subtask 不変条件を免除。
- schema ≥ 2 の不変条件: `metrics.yml` の存在 ／ review 承認済なら `review.md` 存在 ／ deliver 承認済なら
  metrics に deliver の approved イベントが存在 ／ deliver 承認済で `backlog:` 刻印があれば消し込み（下記）。
- schema ≥ 4 の検査: `harnessRev` の存在（**WARN**）／ **またがり work**（deliver 前に `harnessRev` ≠ 現在の版なら **`note:`**。deliver 済みは鳴らさず `metrics --all` の `straddle` 列で見る）。
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
- schema ≥ 6 の検査: **`test-result.md` の実在**（test 承認済なら **FAIL**）／**`tasks.md` の参照の壊れ**
  （未定義の `AC` 参照・未定義のタスクを指す `依存`・`依存` の循環。**FAIL**）／**AC 被覆の穴**
  （タスクに落ちていない `AC`・`AC:` 行の書き忘れ。**WARN**。詳細は `aidev coverage`）／
  **失敗の生証跡**（test で `sent_back` があるのに `test-result.md` に ``` のブロックが無ければ **WARN**）。
  被覆の穴が WARN なのは**人の判断が要る**から（意図して落とした AC もありうる）で、参照の壊れは
  機械的に誤りだから FAIL。硬いゲートは plan の承認前に打つ `aidev coverage --strict`（exit 4）が担う。
  被覆は**家族単位**（親＋全 subtask）で見るので、`verify` も**家族の根でだけ**報告する。
- schema ≥ 7 の検査（**FAIL**）: **起動確認（smoke）の記録**——deliver 承認済で、`smokeCommand` を
  **設定している PJ** なら、`metrics.yml` に `result: pass`（または `skip`）の smoke イベントが要る。
  記録が無い／`fail` のままなら FAIL。**未設定の PJ では鳴らさない**——それは work の問題ではなく
  PJ の設定漏れで、100 works ある PJ に 100 行出すと直せる WARN がノイズに埋もれる
  （straddle で学んだ形）。未設定は `doctor` が **PJ 単位で1行**知らせる。
- schema ≥ 8 の検査: **詰まりの扱い**。(a) 同一工程の差し戻しが `maxSendBacks` に達しているのに
  原因究明（`aidev debug`）の記録が無い → **WARN**（挟むかは人の判断なので致命にしない）。
  (b) デバッグが `next_action: stop_for_human` で終わっているのに deliver 承認済 → **FAIL**
  （人の判断を待つ出口を素通りしている。`autonomous` でもここは待つ）。
- schema ≥ 9 の検査: **light の上流 4 文書の実在**。`profile: light` は `spec` / `plan` を
  approve しない（`protocol-light.md`）ため、schema 5 の「承認済み工程の成果物実在検査」が
  **light では構造的に一度も走らなかった**——`requirement.md` だけ書いた light work が
  `verify OK` で着地できていた（2026-09-04 の実走で実測）。light の「4つとも作る・
  スタブは作らない」は散文にしか無く、二層（散文＝ソフト / CLI＝ハード）の CLI 側が
  丸ごと欠けていた。`requirement` の承認をもって 4 文書を要求する。
- schema ≥ 10 の検査: **記録漏れの範囲を広げる**。`--strict` が致命扱いするのは
  「そのとき書かなければ二度と書けないもの」——`event` の start に加えて、(a) `autonomous`
  なのに `decisions.md` が無い（人間が承認していない判断の唯一の証跡）、(b) `task_checks > 0`
  なのに `task_check_mode` が無い（委譲したのか同一セッションで読み直したのか）。どちらも既定の `verify` では **WARN 止まり**で、致命になるのは `--strict` のときだけ。
  (a) の WARN 自体は **schema を問わず出る**（致命化だけが `--strict` かつ schema ≥ 10）。
  (b) は実走で問題になった——委譲機構の無い環境ではフォールバックが認められている
  （`protocol-check.md`）のに、metrics 上で区別が付かず、「別コンテキストが見て 0 件」と
  「本人が読み直して 0 件」が同じ数字として足し上がっていた。
- 新しい不変条件を足すときは `CURRENT_SCHEMA` を上げ、検査をそのバージョン以上に限定する。

## `test/lint-docs.sh`（文書と CLI 表面の整合）

`run.sh` から呼ばれ、CI でも走る（ワークフローのトリガは `md/claude-code/skills/aidev-**`
＝**文書だけの変更でも走る**）。散文で「気をつける」と書いても片側だけ更新される、という事故を
繰り返したので、機械で見られるものを第二層に上げたもの。

| 検査 | 何を防ぐか |
|---|---|
| **L1 CLI 表面の同期** | sh dispatch のコマンドが sh usage / ps1 dispatch / ps1 usage / この README の表の**4面すべて**にあるか。片面だけ足すと、その面を見た利用者に新コマンドが存在しないことになる（ps1 の help で実際に起きた） |
| **L2 config キー** | コードが読む `.aidev/config.yml` のキーが下の設定表にあるか。載せないと PJ 側は存在を知る手段が無い |
| **L3 参照の健全性** | 参照されている `protocol-*.md` と skill ディレクトリが実在するか。全付録が `protocol.md` の付録表から辿れるか |
| **L4 schema の同期** | `CURRENT_SCHEMA` が sh と ps1 で一致し、この README の履歴に「その版で何を足したか」が載っているか |
| **L5 実行時文書をまたぐ重複文** | 「本文の在処は常に1箇所」の機械化。60 文字以上の同一行が 2 ファイル以上に在れば報告する。**意図的な再掲は `test/lint-docs.allow` に理由つきで登録する**（skip 件数の申告と同じ——見えなくするのではなく、数えて見えるようにする） |
| **L7 help のオプション** | 実装が `die` で出す「使用法:」のオプションが help ヘッダにも載っているか。L1 は**動詞**しか見ないので、動詞が在るまま**オプションだけ落ちる**ドリフトを素通りしていた（`worktree add` の `--backlog`、`convention new` の `--scope`）。ps1 の help は sh を写した要約なので、` ...` で終わる行は「正典（sh 冒頭）を見よ」の宣言として免除する |
| **L6 読み込み量の予算** | `protocol.md` と実行時文書の合計行数。全 work が払うコストなので、**増やすならこの数を書き換えるコミットで理由を述べる**（減るぶんには落とさない） |

**L5 に引っかかったら、まず正典を1つに決めて他を参照にする**。許可リストに足すのは
「正典を1つに決める」を諦める判断なので、理由を必ず添える。実際、この lint の初回実行で
`protocol.md` と付録の逐語重複が 4 件出た——**そこはこのセッションで実際にバグが出た場所**
（walkthrough の要否・walkthrough の条件・autonomous のループ上限が、片方だけ更新されていた）。

## 移植性の落とし穴（実際に踏んだもの）

- **`awk -v` の値にもエスケープ処理がかかり、その扱いが実装で割れる**。mawk は `\[` をそのまま
  残し、gawk は `[` に潰して警告を出す。潰れると `- \[[ xX]\]` が `- [[ xX]]`（角括弧式）に化けて
  チェックボックス行に当たらなくなり、**受け入れ基準が1件も取れなくなる**。
  開発機（mawk）では緑、CI（gawk）で 57 件 fail、という形で一度出した。
  **正規表現は `-v` で渡さず、プログラム中のリテラルとして書く**。
  `test/run.sh` は使える awk 実装を全部列挙し、**ロケール（C / C.UTF-8）も振って**、
  同じ入力で同じ判定になるかを突き合わせる。
- **POSIX の文字クラスはロケール依存**。UTF-8 ロケールの gawk は `[[:space:]]` に
  全角スペース(U+3000)を含め、バイト志向の mawk は含めない。.NET の `\s` も含める。
  全角スペースで字下げした `tasks.md` が「実装 × ロケール」の組でだけタスク行になる、という形で出た。
  **範囲の狭い側（ASCII の `[ \t]`）に全実装を揃える**。
- **`grep -c` は一致 0 件でも `0` を出して exit 1 する**。`|| printf '0'` を足すと "0" が2回出て
  値が2行になる。フォールバックは代入側で受ける（`_n=$(grep -c …) || _n=0`）。
- **多バイト文字を角括弧式に入れない**。awk/sed の角括弧式はバイト単位なので、`[,、]` は
  「、」の構成バイトを1つずつ候補にし、同じ先頭バイトを持つ「なし」を空白に割る。
- **BOM と行末 CR は自分で落とす**。PowerShell の `ReadAllLines` は両方自動で外すので、
  落とさないと Windows チェックアウトの同じファイルで判定が OS ごとに割れる。
- **`smoke` の実行シェルは OS で変わる**（POSIX=`sh -c` / Windows=`cmd.exe /c`）ので、
  **同じ1行が両者で同じ意味になるとは限らない**。`echo "x"` は sh がクォートを外し、
  cmd.exe は外さない。`true` は cmd.exe の組み込みに無い。
  出力一致の契約は **CLI が出す行**についてのもので、素通しする子プロセスの出力は含まない
  （パリティテストではシェル非依存のコマンドだけを使う）。
- **`set -e` は AND-OR リストが関数やループ本体の最後の文のときだけ効く**。
  `[ … ] && cmd` を関数の末尾に置くと、その関数の呼び出しがそのまま失敗として扱われる。

## deliver ゲートの使い方（`land` を別コマンドにしない理由）

破壊的な git 操作を CLI に持たせない（移植性・安全性）。deliver の commit 前に **`verify` を通し、
成功時のみコミット**する：

```sh
.claude/skills/aidev-docs/bin/aidev verify && git commit ...   # verify 失敗なら commit しない
```

## 依存（dependsOn）の判定

- `works slug`（例 `20260620-ruler-display`）→ その work の `approved` に `deliver` が含まれれば充足。

## backlog の消し込み検査

`backlog:` 刻印を持つ work が deliver 承認済みのとき、その backlog ファイル（`active` → `archive/<file>` → `archive/<name>-done.md` の順）の **`- [x]` 行とその継続行**（次の項目・見出し・空行まで）に work の slug が現れなければ FAIL。ファイルのどこかに slug があるだけでは通さない（`- [ ] 次の課題 (needs: <slug>)` の未着手行で着地できていた）。`new --backlog` は未着手 0 件（todo=0）のファイルを拒否する。
- 外部チケット（`#N`、または `PROJ-123` のような英字始まり・数字終わりの ID）→ 自動判定はせず **advisory**（警告のみ。CLI/API 連携は PJ 側 tracker に委ねる）。

## 設定（`.aidev/config.yml`）

CLI が読むキー。どれも任意で、無ければ既定で動く（PJ 固有のファイル名を CLI に埋めないための口）。

| キー | 読む場所 | 意味 |
|---|---|---|
| `lightMaxFiles` | `verify` / `doctor`（light の逸脱 WARN） | light で触ってよいファイル数の上限（既定 3） |
| `conventionsDir` | `convention *` / `doctor` / `approve deliver`（到達通知） | 条項の置き場（既定 `.aidev/conventions`） |
| `conventionsIndex` | `convention *` / `doctor` | 索引ブロックを置くファイル（未設定なら AGENTS.md → CLAUDE.md の順で探す） |
| `docsRoots` | `convention new` | 既存 docs との重複確認先（未設定なら「確認していない」と案内する） |
| `maxDebugRounds` | `debug start` | 1工程あたりのデバッグ回数の上限（既定 2・**下限 1**。`0` を書いても 1 に切り上げる——0 を許すと `debug start` が必ず止め、`debug report` は「start が無い」と弾くので、どちらにも進めなくなる）。超えたら `block` か `stop_for_human` で締める |
| `maxTaskCheckRounds` | `taskcheck start` / `limits` | 同一タスクの「点検 → 修正」の上限（既定 2・**下限 1**）。超えたら深追いせず `decisions.md` に経緯を残して次のタスクへ進み、判断は 60 review に委ねる |
| `smokeCommand` | `smoke` / `verify`（schema 7） / `doctor` | 起動確認のコマンド（**終了するもの**を書く。常駐させない）。対象が無い PJ は `none` と明示する。未設定は `smoke` が exit 2 |
| `smokeCommandWindows` | `smoke`（ps1・Windows のみ） | Windows で別のコマンドが要るときの上書き（未設定なら `smokeCommand`）。**単独で設定しない**——POSIX 側からは未設定に見える |
| `smokeCommands` | `smoke` / `doctor` | 起動確認を**複数行で積む**形（`smokeCommand` の代わり。両方あればこちらが優先）。値は 1 行 1 コマンドで、`smokeCommand` と同じく**行をそのまま**読む（配列リテラル `[a, b]` にしないのは、コマンドに含まれるカンマで壊れるため）。**起動確認は成果物と一緒に育てる**ためのもの——固定 1 本だと work が足した表面を一度も起動しないまま `smoke: pass` になる（実走で 3 本ともそうなった） |
| `smokeStaleAfter` | `doctor` | 起動確認の宣言を最後に変えてから何本着地したら WARN を出すか（既定 5・`0` で停止）。判定は git の pickaxe で「`smokeCommand` を含む行が最後に変わったコミット」を基準にする。`sharedFiles` と同じ「静的な宣言が実態から遅れる」型として扱う |
| `smokeTimeoutSec` | `smoke` | 起動確認に許す最長秒数（既定 300）。`timeout`(coreutils) がある環境でのみ効く |
| `sharedFiles` | `worktree add` / `worktree files` / `doctor` | 並行作業で衝突しやすい共有ファイル名（完了時に名前を挙げて警告） |
| `sharedFilesWindow` | `doctor` / `worktree add` | `sharedFiles` の宣言漏れを見るときに遡るコミット数（既定 20・HEAD の履歴）。その 1/4 以上のコミットが触っているファイルが未宣言なら WARN。`doctor` は上位 5 件、`worktree add` の警告は上位 3 件を名指しする（**同じ関数**で判定する——同じハーネスが片方で「この 3 つは共有だ」と言い、もう片方で「共有は storage.py です」と言う状態を作らないため）。`0` で検査を止める |
| `tracker` | （CLI は読まない） | 外部チケットの種類。判定は工程 skill が行う（`protocol.md`「2.7」） |

## 設計メモ

- YAML は**フロー形式前提**の最小読み取り（`key: value` / `key: [a, b]`）。複雑な YAML は扱わない。
- 行の差し替えは `awk`（sh）／配列再構築（ps1）で行い、`sed` エスケープ事故を避ける。
- 出力は UTF-8（BOM なし）・LF で書き出し、git 差分を OS 間で安定させる。
