#!/bin/sh
# aidev CLI テスト（status / metrics / worktree / 既存回帰 / sh⇔ps1 パリティ）。Node 非依存。
# 使い方: sh .claude/skills/aidev-docs/bin/test/run.sh
# 一時フィクスチャ（works/backlog/metrics）を作り、aidev の出力を期待値と照合する。
set -u

SELF=$(cd "$(dirname "$0")" && pwd)
BIN="$SELF/.."
AIDEV_SH="$BIN/aidev"
AIDEV_PS1="$BIN/aidev.ps1"

PASS=0; FAIL=0; SKIP=0
ok()   { PASS=$((PASS+1)); printf '  ok: %s\n' "$1"; }
ng()   { FAIL=$((FAIL+1)); printf '  NG: %s\n' "$1" >&2; }
# 環境不足で検証を飛ばしたら skip() を使う。RESULT に skip 件数を出して「未検証の穴」を可視化する(#32)。
skip() { SKIP=$((SKIP+1)); printf '  skip: %s\n' "$1"; }
assert_contains() { # haystack needle desc
  case "$1" in *"$2"*) ok "$3" ;; *) ng "$3 (期待を含まず: [$2])"; printf '    出力:\n%s\n' "$1" >&2 ;; esac
}
assert_absent() { # haystack needle desc
  case "$1" in *"$2"*) ng "$3 (含んではいけない: [$2])" ;; *) ok "$3" ;; esac
}
assert_eq() { # got want desc
  if [ "$1" = "$2" ]; then ok "$3"; else ng "$3 (got=[$1] want=[$2])"; fi
}

# ---- フィクスチャ作成 -------------------------------------------------------
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.aidev/works" "$TMP/.aidev/backlog/archive"

# alpha: 完了（deliver 済・schema 2）。metrics に手戻り(coding 2回)/sent_back/リードタイム。
mkdir -p "$TMP/.aidev/works/20260101-alpha"
cat > "$TMP/.aidev/works/20260101-alpha/state.yml" <<'EOF'
schema: 2
slug: alpha
current: deliver
approved: [requirement, research, spec, plan, coding, test, review, deliver]
mode: autonomous
humanGates: []
maxSendBacks: 3
dependsOn: []
EOF
cat > "$TMP/.aidev/works/20260101-alpha/metrics.yml" <<'EOF'
events:
  - { ts: 2026-01-01T00:00:00Z, phase: requirement, event: start }
  - { ts: 2026-01-01T00:10:00Z, phase: requirement, event: approved }
  - { ts: 2026-01-01T00:30:00Z, phase: spec, event: sent_back }
  - { ts: 2026-01-01T01:00:00Z, phase: coding, event: start }
  - { ts: 2026-01-01T01:05:00Z, phase: coding, event: start }
  - { ts: 2026-01-01T02:00:00Z, phase: coding, event: approved }
  - { ts: 2026-01-01T03:00:00Z, phase: deliver, event: approved }
EOF
# review 承認済なので review.md が必要（verify schema>=2 の不変条件）
printf '# レビュー記録\n' > "$TMP/.aidev/works/20260101-alpha/review.md"

# beta: 進行中（spec まで承認）。dependsOn: alpha(充足) + #99(advisory)。
mkdir -p "$TMP/.aidev/works/20260102-beta"
cat > "$TMP/.aidev/works/20260102-beta/state.yml" <<'EOF'
schema: 2
slug: beta
ticket: "#42"
current: spec
approved: [requirement, research, spec]
mode: interactive
humanGates: []
maxSendBacks: 3
dependsOn: [20260101-alpha, #99]
EOF
printf 'events:\n' > "$TMP/.aidev/works/20260102-beta/metrics.yml"

# legacy: schema 無し・approved 空。
mkdir -p "$TMP/.aidev/works/20260103-legacy"
cat > "$TMP/.aidev/works/20260103-legacy/state.yml" <<'EOF'
slug: legacy
current: requirement
approved: []
EOF

# backlog（archive 配下は除外されること）
cat > "$TMP/.aidev/backlog/x.md" <<'EOF'
- [ ] a
- [ ] b (needs: #1)
- [x] done
EOF
cat > "$TMP/.aidev/backlog/archive/old.md" <<'EOF'
- [ ] should-not-count
EOF

printf '20260102-beta\n' > "$TMP/.aidev/current"

run_sh() { ( cd "$TMP" && "$AIDEV_SH" "$@" ); }

echo "== status =="
ST_TSV=$(run_sh status --format tsv)
assert_contains "$ST_TSV" "work	20260101-alpha	-	autonomous	deliver	-	yes	ok" "alpha: 完了行(next=-/done=yes/deps=ok)"
assert_contains "$ST_TSV" "work	20260102-beta	#42	interactive	spec	plan	no	#99(advisory)" "beta: next=plan/done=no/deps=#99(advisory)（alpha は充足）"
assert_contains "$ST_TSV" "work	20260103-legacy	-	-	requirement	requirement	no	ok" "legacy: schema無しでも一覧化(next=requirement)"
assert_contains "$ST_TSV" "backlog	x.md	2	1" "backlog x.md: todo=2/needs=1"
assert_absent  "$ST_TSV" "should-not-count" "archive/ は除外される"

ST_TBL=$(run_sh status)
assert_contains "$ST_TBL" "WORKS (3)" "table: WORKS 件数"
assert_contains "$ST_TBL" "BACKLOG (未着手 2 件)" "table: BACKLOG 未着手件数"

echo "== status 異常系 =="
run_sh status --format bogus >/dev/null 2>&1; assert_eq "$?" "1" "不正 --format は exit 1"

echo "== metrics =="
MT=$(run_sh metrics --all --format tsv)
assert_contains "$MT" "20260101-alpha	2026-01-01T00:00:00Z	yes	10800	1	1" "alpha: lead=10800/reworks=1/sent_backs=1"
assert_contains "$MT" "20260103-legacy	-	no	-	0	0" "legacy: metrics空でも 0/-"
MTP=$(run_sh metrics 20260101-alpha --phases --format tsv)
assert_contains "$MTP" "20260101-alpha	coding	2026-01-01T01:05:00Z	2026-01-01T02:00:00Z	3300" "alpha --phases: coding は直近start基準で elapsed=3300"
assert_contains "$MTP" "20260101-alpha	requirement	2026-01-01T00:00:00Z	2026-01-01T00:10:00Z	600" "alpha --phases: requirement elapsed=600"

echo "== 読み取り専用（status/metrics は state/metrics を書き換えない） =="
SUM1=$(cat "$TMP/.aidev/works"/*/state.yml "$TMP/.aidev/works"/*/metrics.yml | cksum)
run_sh status >/dev/null; run_sh status --format tsv >/dev/null
run_sh metrics --all >/dev/null; run_sh metrics 20260101-alpha --phases >/dev/null
SUM2=$(cat "$TMP/.aidev/works"/*/state.yml "$TMP/.aidev/works"/*/metrics.yml | cksum)
assert_eq "$SUM1" "$SUM2" "status/metrics 実行後も state/metrics 不変"

echo "== 既存コマンド回帰 =="
run_sh verify 20260101-alpha >/dev/null 2>&1; assert_eq "$?" "0" "verify(alpha) exit 0"
run_sh doctor >/dev/null 2>&1; assert_eq "$?" "0" "doctor exit 0"
# beta は plan 前提(spec.md)が無いので guard plan は exit 2
run_sh guard plan >/dev/null 2>&1; assert_eq "$?" "2" "guard plan(前提成果物なし) exit 2"
G_OUT=$(run_sh guard spec 2>&1); echo "$G_OUT" | grep -q "advisory" && ok "guard: #99 を advisory(warn) 表示" || ng "guard advisory 表示"

echo "== worktree =="
if command -v git >/dev/null 2>&1; then
  # フィクスチャ git リポジトリを $TMP/repo に作る（既定 worktree パスは $TMP/repo-wt/* ＝ $TMP 配下なので
  # 既存 trap の rm -rf "$TMP" で worktree ごと自動掃除される）。
  REPO="$TMP/repo"
  # CLI は skills 配下に置く（worktree add は worktree 内の .claude/skills/aidev-docs/bin/aidev を self-invoke するため、
  # 追跡＝コミットして worktree に伝播させる）。.aidev/ は追跡マーカ(.gitkeep)で worktree に存在させ、
  # find_root が worktree 内 .aidev で止まる（さもないと $TMP/.aidev へ脱出して汚染する）。実 repo は charter/config/works
  # が追跡されているのと同じ前提。
  mkdir -p "$REPO/.claude/skills/aidev-docs/bin" "$REPO/.aidev"
  cp "$AIDEV_SH" "$REPO/.claude/skills/aidev-docs/bin/aidev"; chmod +x "$REPO/.claude/skills/aidev-docs/bin/aidev"
  : > "$REPO/.aidev/.gitkeep"
  printf '.aidev/current\n' > "$REPO/.gitignore"
  (
    cd "$REPO"
    git init -q
    git config user.email t@example.com; git config user.name tester
    git add -A; git commit -qm init >/dev/null 2>&1
  )
  run_repo() { ( cd "$REPO" && "$AIDEV_SH" "$@" ); }

  # add（add 内で new）
  ADD_OUT=$(run_repo worktree add probe 2>&1); ADD_RC=$?
  assert_eq "$ADD_RC" "0" "worktree add exit 0"
  assert_contains "$ADD_OUT" "worktree 追加" "add: 追加メッセージ"
  assert_contains "$ADD_OUT" "languageId" "add: 規約警告(languageId)を出力"
  WP="$TMP/repo-wt/probe"
  assert_eq "$([ -d "$WP" ] && echo yes || echo no)" "yes" "add: 既定 path に worktree 作成"
  WT_CUR=$(cat "$WP/.aidev/current" 2>/dev/null)
  assert_contains "$WT_CUR" "-probe" "add: worktree current が dated probe work を指す"
  # INV-1: main(repo) tree の current は add で作られない/変わらない（gitignore＝worktree ローカル）
  assert_eq "$([ -f "$REPO/.aidev/current" ] && echo yes || echo no)" "no" "INV-1: main の current は不変(未作成)"

  # list（判定キー=current 有無。probe worktree が出る）
  L_TSV=$(run_repo worktree list --format tsv)
  assert_contains "$L_TSV" "worktree	$WP	feature/probe" "list: probe を current 有無で抽出(branch=feature/probe)"
  L_TBL=$(run_repo worktree list)
  assert_contains "$L_TBL" "WORKTREES" "list: table ヘッダ"

  # 異常系
  run_repo worktree bogus >/dev/null 2>&1; assert_eq "$?" "1" "未知 sub は exit 1"
  run_repo worktree add >/dev/null 2>&1; assert_eq "$?" "1" "slug 無し add は exit 1"
  run_repo worktree list --format bogus >/dev/null 2>&1; assert_eq "$?" "1" "list 不正 --format は exit 1"

  # rm（未コミット work フォルダがあるので --force 無しは拒否）
  run_repo worktree rm probe >/dev/null 2>&1; assert_eq "$?" "1" "rm: 未コミット差分で既定拒否(exit 1)"
  assert_eq "$([ -d "$WP" ] && echo yes || echo no)" "yes" "rm: 拒否時は worktree 残存"
  RM_OUT=$(run_repo worktree rm probe --force --delete-branch 2>&1); assert_eq "$?" "0" "rm --force --delete-branch exit 0"
  assert_contains "$RM_OUT" "branch 削除: feature/probe" "rm: --delete-branch でブランチ削除"
  assert_eq "$([ -d "$WP" ] && echo yes || echo no)" "no" "rm: worktree 撤去済み"
  ( cd "$REPO" && git show-ref --verify --quiet refs/heads/feature/probe ); assert_eq "$?" "1" "rm: ブランチも削除済み"
  # INV-1（rm 後も main current 不変＝未作成のまま）
  assert_eq "$([ -f "$REPO/.aidev/current" ] && echo yes || echo no)" "no" "INV-1: rm 後も main current 不変"

  # #33: slug が main worktree(basename=repo) に一致しても rm 対象にせず、明確なメッセージで拒否する
  RMM_OUT=$(run_repo worktree rm repo 2>&1); RMM_RC=$?
  assert_eq "$RMM_RC" "1" "rm: main worktree に一致する slug は exit 1"
  assert_contains "$RMM_OUT" "main worktree は rm できません" "rm: main worktree 一致時は明確な文言で拒否"
  assert_eq "$([ -d "$REPO" ] && echo yes || echo no)" "yes" "rm: main worktree は削除されない"
else
  skip "git 不在のため worktree テストを省略"
fi

echo "== subtask 層（new --parent / guard 継承 / 兄弟 dependsOn / doctor 横断） =="
# 既存フィクスチャ(status/metrics の件数アサート)を汚さないよう独立 root を使う。
SUB="$TMP/sub"
# .aidev/works で find_root が $SUB に止まる。CLI は $AIDEV_SH を直接叩き new --parent は self-invoke しないため
# subtask フィクスチャに CLI コピーは不要（worktree add のみ self-invoke する）。
mkdir -p "$SUB/.aidev/works"
run_sub() { ( cd "$SUB" && "$AIDEV_SH" "$@" ); }

# 親 work を作り、上流成果物を置いて plan まで承認
run_sub new feat >/dev/null
SP=$(cat "$SUB/.aidev/current")
for f in requirement spec design plan; do : > "$SUB/.aidev/works/$SP/$f.md"; done
for ph in requirement spec design plan; do run_sub approve "$ph" >/dev/null; done

# subtask 01-be 作成
SO=$(run_sub new 01-be --parent "$SP")
assert_contains "$SO" "created subtask" "new --parent: subtask 作成"
assert_eq "$(cat "$SUB/.aidev/current")" "$SP/01-be" "new --parent: current が subtask パス"
SPST="$SUB/.aidev/works/$SP/state.yml"
assert_contains "$(cat "$SPST")" "subtasks: [01-be]" "親 subtasks に追記"
assert_contains "$(cat "$SPST")" "activeSubtask: 01-be" "親 activeSubtask 設定"
SCST="$SUB/.aidev/works/$SP/01-be/state.yml"
assert_contains "$(cat "$SCST")" "parent: $SP" "子 state.yml に parent 逆参照"
assert_contains "$(cat "$SCST")" "current: plan" "子 current=plan"
assert_contains "$(cat "$SCST")" "schema: 3" "子 schema=3"

# 2つ目: activeSubtask は先頭(01-be)のまま・subtasks に追記
run_sub new 02-fe --parent "$SP" --depends 01-be >/dev/null
assert_contains "$(cat "$SPST")" "subtasks: [01-be, 02-fe]" "親 subtasks に2件目を追記"
assert_contains "$(cat "$SPST")" "activeSubtask: 01-be" "activeSubtask は先頭のまま"

# subtask slug にスラッシュ禁止
run_sub new a/b --parent "$SP" >/dev/null 2>&1; assert_eq "$?" "1" "subtask slug にスラッシュは exit 1"
# 親不在は exit 1
run_sub new x --parent nope >/dev/null 2>&1; assert_eq "$?" "1" "親不在の --parent は exit 1"
# C: 多段ネスト禁止（親が既に subtask なら exit 1）
run_sub new deep --parent "$SP/01-be" >/dev/null 2>&1; assert_eq "$?" "1" "C: 親が subtask の --parent は exit 1（多段ネスト不可）"

# guard: subtask plan は親の spec.md を継承して充足(0)
echo "$SP/01-be" > "$SUB/.aidev/current"
run_sub guard plan >/dev/null 2>&1; assert_eq "$?" "0" "guard plan: 親 spec.md 継承で充足"
# guard: subtask coding は親 plan.md を継承「しない」（subtask 固有）。子に plan.md/tasks.md が無いので未充足(2)
run_sub guard coding >/dev/null 2>&1; assert_eq "$?" "2" "guard coding: 親 plan.md を継承せず未充足(2)"
# 子に plan.md/tasks.md を置けば充足(0)
: > "$SUB/.aidev/works/$SP/01-be/plan.md"; : > "$SUB/.aidev/works/$SP/01-be/tasks.md"
run_sub guard coding >/dev/null 2>&1; assert_eq "$?" "0" "guard coding: 子の plan.md/tasks.md で充足(0)"
# B: 親専用工程は subtask で実行不可（exit 2）。subtask の工程は plan/coding/test/review のみ
for ph in spec design deliver walkthrough requirement; do
  run_sub guard "$ph" >/dev/null 2>&1; assert_eq "$?" "2" "B: subtask の guard $ph は親専用で拒否(2)"
done
# B: subtask 固有工程(review)は親専用ブロックに掛からない（spec.md 継承で充足 0）
run_sub guard review >/dev/null 2>&1; assert_eq "$?" "0" "B: subtask の guard review は許可(0)"

# 兄弟 dependsOn: 02-fe は 01-be 未review で未充足(3)、review 後に充足(0)
echo "$SP/02-fe" > "$SUB/.aidev/current"
run_sub guard plan >/dev/null 2>&1; assert_eq "$?" "3" "guard: 兄弟 01-be 未review で dependsOn 未充足(3)"
echo "$SP/01-be" > "$SUB/.aidev/current"
for ph in plan coding test review; do run_sub approve "$ph" >/dev/null; done
: > "$SUB/.aidev/works/$SP/01-be/review.md"
# D: 01-be の review 承認でカーソルが次の未完 subtask(02-fe)へ自動前進する
assert_contains "$(cat "$SUB/.aidev/works/$SP/state.yml")" "activeSubtask: 02-fe" "D: 01-be review 承認で親 activeSubtask が 02-fe へ前進"
assert_eq "$(cat "$SUB/.aidev/current")" "$SP/02-fe" "D: カーソル(.aidev/current)が 02-fe へ自動前進"
run_sub guard plan >/dev/null 2>&1; assert_eq "$?" "0" "guard: 兄弟 01-be review 済で dependsOn 充足(0)"

# event/approve が subtask に記録される
echo "$SP/01-be" > "$SUB/.aidev/current"
run_sub event coding start >/dev/null
assert_contains "$(cat "$SUB/.aidev/works/$SP/01-be/metrics.yml")" "phase: coding, event: start" "event は subtask の metrics に記録"

# doctor が subtask も横断検査する
SD=$(run_sub doctor)
assert_contains "$SD" "$SP/01-be" "doctor: subtask 01-be を横断検査"
assert_contains "$SD" "$SP/02-fe" "doctor: subtask 02-fe を横断検査"
# verify が subtask を解決
SV=$(run_sub verify "$SP/01-be"); assert_contains "$SV" "verify: $SP/01-be" "verify: subtask パスを解決"

# D: 最後の subtask(02-fe)の review 承認で activeSubtask=done、カーソルが親へ戻る
echo "$SP/02-fe" > "$SUB/.aidev/current"
for ph in plan coding test review; do run_sub approve "$ph" >/dev/null; done
: > "$SUB/.aidev/works/$SP/02-fe/review.md"
assert_contains "$(cat "$SUB/.aidev/works/$SP/state.yml")" "activeSubtask: done" "D: 全 subtask 完了で activeSubtask=done"
assert_eq "$(cat "$SUB/.aidev/current")" "$SP" "D: 全完了でカーソルが親 work へ戻る"

# --- status subtask ロールアップ表示（案C）---
TAB=$(printf '\t')
run_sub new feat2 >/dev/null
SP2=$(cat "$SUB/.aidev/current")
for f in requirement spec plan; do : > "$SUB/.aidev/works/$SP2/$f.md"; done
for ph in requirement spec plan; do run_sub approve "$ph" >/dev/null; done
run_sub new 01-a --parent "$SP2" >/dev/null
run_sub new 02-b --parent "$SP2" >/dev/null
# 01-a を review まで承認（N=1 / M=2。D が current を 02-b へ動かす）
echo "$SP2/01-a" > "$SUB/.aidev/current"
for ph in plan coding test review; do run_sub approve "$ph" >/dev/null; done
: > "$SUB/.aidev/works/$SP2/01-a/review.md"

# 既定: 親 next=sub 1/2、子行は出さない
RST=$(run_sub status)
assert_contains "$RST" "sub 1/2" "rollup: 既定 status の next=sub 1/2"
assert_absent  "$RST" "↳ 01-a"  "rollup: 既定では子行を出さない"
# --subtasks: 子をインデント展開
RSTS=$(run_sub status --subtasks)
assert_contains "$RSTS" "↳ 01-a" "rollup: --subtasks で子 01-a を展開"
assert_contains "$RSTS" "↳ 02-b" "rollup: --subtasks で子 02-b を展開"
# tsv: subtask 行型／work 行は8フィールド維持
RTSV=$(run_sub status --subtasks --format tsv)
assert_contains "$RTSV" "subtask${TAB}$SP2/01-a${TAB}review${TAB}yes" "rollup: tsv subtask 行(01-a review/yes)"
assert_contains "$RTSV" "subtask${TAB}$SP2/02-b${TAB}plan${TAB}no"     "rollup: tsv subtask 行(02-b plan/no)"
WNF=$(printf '%s\n' "$RTSV" | awk -F'\t' -v w="$SP2" '$1=="work" && $2==w {print NF}')
assert_eq "$WNF" "8" "rollup: tsv work 行は8フィールド維持(後方互換)"
# 回帰: subtask 無し work は next に sub を出さない
run_sub new solo >/dev/null; SSO=$(cat "$SUB/.aidev/current")
: > "$SUB/.aidev/works/$SSO/requirement.md"; run_sub approve requirement >/dev/null
SOLOLINE=$(run_sub status --subtasks | grep "$SSO")
assert_absent "$SOLOLINE" "sub " "rollup: subtask 無し work(solo) は next に sub を出さない"

echo "== sh ⇔ ps1 パリティ =="
if command -v pwsh >/dev/null 2>&1; then
  for args in "status --format tsv" "metrics --all --format tsv" "metrics 20260101-alpha --phases --format tsv"; do
    # shellcheck disable=SC2086
    O_SH=$( ( cd "$TMP" && "$AIDEV_SH" $args ) )
    # shellcheck disable=SC2086
    O_PS=$( ( cd "$TMP" && pwsh "$AIDEV_PS1" $args ) | tr -d '\r' )
    assert_eq "$O_SH" "$O_PS" "パリティ: $args"
  done

  # subtask 層のパリティ（$SUB フィクスチャ。doctor のネスト横断・status・metrics を sh⇔ps1 突合）
  for args in "doctor" "status --format tsv" "status --subtasks --format tsv" "metrics --all --format tsv"; do
    # shellcheck disable=SC2086
    O_SH=$( ( cd "$SUB" && "$AIDEV_SH" $args ) )
    # shellcheck disable=SC2086
    O_PS=$( ( cd "$SUB" && pwsh "$AIDEV_PS1" $args ) | tr -d '\r' )
    assert_eq "$O_SH" "$O_PS" "パリティ(subtask): $args"
  done

  # ps1 の new --parent を実機で検証（sh で作った親に ps1 が subtask を足し、親 state を正しく更新）
  ( cd "$SUB" && pwsh "$AIDEV_PS1" new 03-ps --parent "$SP" >/dev/null 2>&1 )
  assert_contains "$(cat "$SUB/.aidev/works/$SP/state.yml")" "03-ps" "パリティ: ps1 new --parent が親 subtasks に追記"
  assert_contains "$(cat "$SUB/.aidev/works/$SP/03-ps/state.yml" 2>/dev/null)" "parent: $SP" "パリティ: ps1 new --parent が子 parent 逆参照を刻む"

  # worktree パリティ（git 必須）: ps1 の worktree 実装を実機で検証する（#28）。
  # pwsh 不在の開発機では skip されるため、ps1 の worktree は本節（pwsh 環境/CI）で初めて実行検証される。
  if command -v git >/dev/null 2>&1; then
    PREPO="$TMP/prepo"
    # CLI は skills 配下（worktree add の self-invoke 先）。.aidev/ は追跡 work(20260101-existing)で worktree に存在。
    mkdir -p "$PREPO/.claude/skills/aidev-docs/bin" "$PREPO/.aidev/works/20260101-existing"
    cp "$AIDEV_SH"  "$PREPO/.claude/skills/aidev-docs/bin/aidev";     chmod +x "$PREPO/.claude/skills/aidev-docs/bin/aidev"
    cp "$AIDEV_PS1" "$PREPO/.claude/skills/aidev-docs/bin/aidev.ps1"
    printf '.aidev/current\n' > "$PREPO/.gitignore"
    # 既存work一致 add の回帰用に slug:existing の work をコミットしておく
    cat > "$PREPO/.aidev/works/20260101-existing/state.yml" <<'YML'
schema: 2
slug: existing
current: spec
approved: [requirement, spec]
mode: interactive
humanGates: []
maxSendBacks: 3
dependsOn: []
YML
    printf 'events:\n' > "$PREPO/.aidev/works/20260101-existing/metrics.yml"
    ( cd "$PREPO" && git init -q && git config user.email t@example.com && git config user.name tester \
        && git add -A && git commit -qm init >/dev/null 2>&1 )

    # (1) sh で worktree を1つ作り、list の出力を sh⇔ps1 で突合（同一 git 状態・同一 current を読むので一致するはず）
    ( cd "$PREPO" && "$AIDEV_SH" worktree add probe >/dev/null 2>&1 )
    WL_SH=$( ( cd "$PREPO" && "$AIDEV_SH"      worktree list --format tsv ) )
    WL_PS=$( ( cd "$PREPO" && pwsh "$AIDEV_PS1" worktree list --format tsv ) | tr -d '\r' )
    assert_eq "$WL_SH" "$WL_PS" "パリティ: worktree list --format tsv"

    # (2) ps1 の add（既存work一致＝current 設定のみ）。current が full dated 名であること
    #     ＝ review 検出の must「PowerShell 単一要素配列アンラップ($mw[0]が先頭1文字)」の回帰ガード
    PW_OUT=$( ( cd "$PREPO" && pwsh "$AIDEV_PS1" worktree add existing ) | tr -d '\r' )
    PW_CUR=$(cat "$TMP/prepo-wt/existing/.aidev/current" 2>/dev/null)
    assert_eq "$PW_CUR" "20260101-existing" "パリティ: ps1 add(既存work) current=full dated 名(\$mw アンラップ回帰)"
    assert_contains "$PW_OUT" "既存 work をリンク" "パリティ: ps1 add は既存をリンク(new 委譲せず)"
  else
    skip "git 不在のため worktree パリティを省略"
  fi
else
  skip "pwsh 不在のためパリティテストを省略"
fi

echo
printf 'RESULT: pass=%s fail=%s skip=%s\n' "$PASS" "$FAIL" "$SKIP"
# skip>0＝環境不足で未実行の検証（未検証の穴）。deliver/PR で「未検証 surface」として引き継ぐこと(#32)。
[ "$SKIP" -gt 0 ] && printf 'NOTE: %s 件の検証が環境不足で skip された（未検証の穴）。pwsh/git のある環境(CI)で再実行して埋めること。\n' "$SKIP" >&2
[ "$FAIL" -eq 0 ]
