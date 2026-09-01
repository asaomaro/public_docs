#!/bin/sh
# aidev CLI テスト（status / metrics / worktree / 既存回帰 / sh⇔ps1 パリティ）。Node 非依存。
# 使い方: sh .claude/skills/aidev-docs/bin/test/run.sh
# 一時フィクスチャ（works/backlog/metrics）を作り、aidev の出力を期待値と照合する。
set -u

SELF=$(cd "$(dirname "$0")" && pwd)
BIN="$SELF/.."
AIDEV_SH="$BIN/aidev"
AIDEV_PS1="$BIN/aidev.ps1"

# ps1 を走らせるホストを決める。pwsh は Windows に標準搭載ではないため、素の Windows では
# Windows PowerShell 5.1（powershell.exe）へフォールバックする。ここを pwsh 決め打ちにすると
# ps1 が「対象 OS で一度も検証されないまま緑」になる(#32 と同じ穴)。
PS_HOST=""
if command -v pwsh >/dev/null 2>&1; then PS_HOST=pwsh
elif command -v powershell >/dev/null 2>&1; then PS_HOST=winps
fi
run_ps1() { # script args...
  _s=$1; shift
  case "$PS_HOST" in
    pwsh)  pwsh "$_s" "$@" ;;
    winps) MSYS2_ARG_CONV_EXCL='*' powershell -NoProfile -ExecutionPolicy Bypass \
             -File "$(cygpath -w "$_s" 2>/dev/null || printf '%s' "$_s")" "$@" ;;
    *)     return 127 ;;
  esac
}

# CLI が刻む現行スキーマ版。テストで版番号を二重管理しない（bump のたびに期待値を書き換えると
# 「テストを通すために期待値を直す」形になり、刻印そのものの回帰を守れなくなる）。
CUR_SCHEMA=$(sed -n 's/^CURRENT_SCHEMA=\([0-9][0-9]*\).*/\1/p' "$AIDEV_SH" | head -n1)

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
assert_contains "$ST_TSV" "backlog	x.md	2	1	0" "backlog x.md: todo=2/needs=1/inflight=0（刻印付き work 無し）"
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

# verify: イベント対の検査（approved があるのに start が無い＝記録漏れ）
# guard と event start が別コマンドなので実際に踏んだ事故。WARN であり exit は変えない。
mkdir -p "$TMP/.aidev/works/20260101-gap"
cat > "$TMP/.aidev/works/20260101-gap/state.yml" <<'YML'
schema: 3
slug: gap
current: spec
approved: [requirement]
YML
cat > "$TMP/.aidev/works/20260101-gap/metrics.yml" <<'YML'
events:
  - { ts: 2026-01-01T00:00:00Z, phase: requirement, event: approved }
  - { ts: 2026-01-01T01:00:00Z, phase: spec, event: start }
  - { ts: 2026-01-01T02:00:00Z, phase: spec, event: approved }
YML
V_GAP=$(run_sh verify 20260101-gap 2>&1); V_RC=$?
echo "$V_GAP" | grep -q "WARN requirement" && ok "verify: start 欠落を WARN で知らせる" || ng "verify: start 欠落の WARN が出ない"
echo "$V_GAP" | grep -q "WARN spec" && ng "verify: 対の揃った工程に WARN が出ている" || ok "verify: 対の揃った工程には WARN を出さない"
assert_eq "$V_RC" "0" "verify: WARN は exit コードを変えない"
rm -rf "$TMP/.aidev/works/20260101-gap"

# WARN の並びは PHASES 順（ハッシュ列挙順に任せると awk と PowerShell で並びが変わり
# 「出力を一致させる」契約＝パリティが破れる）。
mkdir -p "$TMP/.aidev/works/20260101-order"
cat > "$TMP/.aidev/works/20260101-order/state.yml" <<'YML'
schema: 3
slug: order
current: coding
approved: [requirement, spec, design, plan]
YML
cat > "$TMP/.aidev/works/20260101-order/metrics.yml" <<'YML'
events:
  - { ts: 2026-01-01T00:00:00Z, phase: plan, event: approved }
  - { ts: 2026-01-01T01:00:00Z, phase: spec, event: approved }
  - { ts: 2026-01-01T02:00:00Z, phase: design, event: approved }
  - { ts: 2026-01-01T03:00:00Z, phase: requirement, event: approved }
YML
V_ORD=$(run_sh verify 20260101-order 2>&1 | grep -o 'WARN [a-z]*' | tr '\n' ' ')
assert_eq "$V_ORD" "WARN requirement WARN spec WARN design WARN plan " "verify: WARN は PHASES 順（記録順やハッシュ順ではない）"
if [ -n "$PS_HOST" ]; then
  P_ORD=$( ( cd "$TMP" && run_ps1 "$AIDEV_PS1" verify 20260101-order ) | tr -d '\r' | grep -o 'WARN [a-z]*' | tr '\n' ' ')
  assert_eq "$P_ORD" "$V_ORD" "パリティ: WARN の並びが sh⇔ps1 で一致"
else
  skip "PowerShell(pwsh/powershell) 不在のため WARN 並びのパリティを省略"
fi
rm -rf "$TMP/.aidev/works/20260101-order"

# guard: start の記録が要るときだけ促す（自動記録はしない＝手戻り回数の二重計上を避ける）
mkdir -p "$TMP/.aidev/works/20260101-hint"
cat > "$TMP/.aidev/works/20260101-hint/state.yml" <<'YML'
schema: 3
slug: hint
current: requirement
approved: []
YML
: > "$TMP/.aidev/works/20260101-hint/requirement.md"
cat > "$TMP/.aidev/works/20260101-hint/metrics.yml" <<'YML'
events:
  - { ts: 2026-01-01T00:00:00Z, phase: requirement, event: start }
YML
PREV_CURRENT=$(cat "$TMP/.aidev/current")
echo "20260101-hint" > "$TMP/.aidev/current"
H1=$(run_sh guard spec 2>&1)
echo "$H1" | grep -q "aidev event spec start" && ok "guard: 未 start の工程では start を促す" || ng "guard: start の促しが出ない"
H2=$(run_sh guard requirement 2>&1)
echo "$H2" | grep -q "aidev event requirement start" && ng "guard: start 済なのに促している" || ok "guard: start 済の工程では促さない"
rm -rf "$TMP/.aidev/works/20260101-hint"
printf '%s\n' "$PREV_CURRENT" > "$TMP/.aidev/current"
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
  # 共有ファイル警告は .aidev/config.yml の sharedFiles から生成する（PJ 固有名を CLI に埋めない）。
  # このフィクスチャは config.yml を持たないので、名指しではなく汎用文言になる。
  assert_contains "$ADD_OUT" "共有するもの" "add: sharedFiles 未設定なら汎用の共有ファイル警告"
  assert_contains "$ADD_OUT" "sharedFiles" "add: 未設定時は sharedFiles で名指しできると案内する"
  WP="$TMP/repo-wt/probe"
  assert_eq "$([ -d "$WP" ] && echo yes || echo no)" "yes" "add: 既定 path に worktree 作成"
  WT_CUR=$(cat "$WP/.aidev/current" 2>/dev/null)
  assert_contains "$WT_CUR" "-probe" "add: worktree current が dated probe work を指す"
  # INV-1: main(repo) tree の current は add で作られない/変わらない（gitignore＝worktree ローカル）
  assert_eq "$([ -f "$REPO/.aidev/current" ] && echo yes || echo no)" "no" "INV-1: main の current は不変(未作成)"

  # list（判定キー=current 有無。probe worktree が出る）
  L_TSV=$(run_repo worktree list --format tsv)
  # パスは git の表記に従う（Windows では MSYS の /c/... ではなく C:/... が返る）ため末尾で照合する
  assert_contains "$L_TSV" "repo-wt/probe	feature/probe" "list: probe を current 有無で抽出(branch=feature/probe)"
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

  # rm <path>: list が出したパスをそのまま渡せること。git は Windows で C:/Users/... を返す一方
  # 解決側は MSYS の /c/Users/...（sh）／C:\Users\...（ps1）なので、素の文字列比較だと必ず外れた。
  run_repo worktree add bypath >/dev/null 2>&1
  BP=$(run_repo worktree list --format tsv | awk -F'\t' '$2 ~ /bypath$/ {print $2}')
  assert_eq "$([ -n "$BP" ] && echo yes || echo no)" "yes" "rm(path): list からパスを取得できる"
  run_repo worktree rm "$BP" --force --delete-branch >/dev/null 2>&1
  assert_eq "$?" "0" "rm: list が出したパス表記をそのまま rm できる"
  assert_eq "$([ -d "$TMP/repo-wt/bypath" ] && echo yes || echo no)" "no" "rm(path): worktree 撤去済み"

  # #33: slug が main worktree(basename=repo) に一致しても rm 対象にせず、明確なメッセージで拒否する
  RMM_OUT=$(run_repo worktree rm repo 2>&1); RMM_RC=$?
  assert_eq "$RMM_RC" "1" "rm: main worktree に一致する slug は exit 1"
  assert_contains "$RMM_OUT" "main worktree は rm できません" "rm: main worktree 一致時は明確な文言で拒否"
  assert_eq "$([ -d "$REPO" ] && echo yes || echo no)" "yes" "rm: main worktree は削除されない"

  # sharedFiles を設定すると、その名前で警告する（PJ 固有名は config 側にだけ存在する）。
  # 読むのは main tree の .aidev/config.yml（worktree 側ではない）＝ add は main tree で実行されるため。
  printf 'sharedFiles: [package.json, src/fileScope.ts]\n' > "$REPO/.aidev/config.yml"
  CFG_OUT=$(run_repo worktree add cfgprobe 2>&1)
  assert_contains "$CFG_OUT" "共有ファイル（package.json, src/fileScope.ts）" "add: sharedFiles を名指しで警告"
  case "$CFG_OUT" in *"共有するもの"*) ng "add: sharedFiles 設定時は汎用文言を出さない" ;; *) ok "add: sharedFiles 設定時は汎用文言を出さない" ;; esac
  run_repo worktree rm cfgprobe --force --delete-branch >/dev/null 2>&1
  rm -f "$REPO/.aidev/config.yml"
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
assert_contains "$(cat "$SCST")" "schema: $CUR_SCHEMA" "子 schema=CURRENT_SCHEMA"

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

echo "== backlog 出自の消し込み（new --backlog / verify） =="
# 背景: 直接入口（aidev-00-start で backlog 項目を選ぶ）は batch と違い自動で [x] にしない。
# 閉じ忘れると「完了済みの項目を次の人が選ぶ」（2026-08-01 に実際に発生）。
BLR=$(mktemp -d); mkdir -p "$BLR/.aidev/backlog"
printf '# demo\n\n- [ ] やること\n' > "$BLR/.aidev/backlog/demo.md"
run_bl() { ( cd "$BLR" && "$AIDEV_SH" "$@" ); }

run_bl new nofile --backlog missing.md >/dev/null 2>&1
assert_eq "$?" "1" "new --backlog: 存在しないファイルは着手前に弾く"

run_bl new demo-work --mode autonomous --backlog demo.md >/dev/null
BLW=$(cat "$BLR/.aidev/current")
assert_contains "$(cat "$BLR/.aidev/works/$BLW/state.yml")" "backlog: demo.md" "new --backlog: state.yml に出自を刻む"

# deliver まで通す（review.md は schema>=2 の不変条件）
: > "$BLR/.aidev/works/$BLW/review.md"
for p in requirement spec plan coding test review deliver; do run_bl approve "$p" >/dev/null; done

BLV=$(run_bl verify 2>&1); BLC=$?
assert_eq "$BLC" "4" "verify: 消し込み前は FAIL（deliver 済 + backlog 出自）"
assert_contains "$BLV" "消し込みが無い" "verify: 消し込み漏れを名指しする"

# 消し込む（規約どおり works slug を根拠として併記する）
printf '# demo\n\n- [x] やること\n    → %s で完了\n' "$BLW" > "$BLR/.aidev/backlog/demo.md"
run_bl verify >/dev/null 2>&1
assert_eq "$?" "0" "verify: 消し込み後は PASS"

# archive へ退避しても追える（全項目 [x] のファイルは archive/ へ移る運用）
mkdir -p "$BLR/.aidev/backlog/archive"
mv "$BLR/.aidev/backlog/demo.md" "$BLR/.aidev/backlog/archive/demo.md"
run_bl verify >/dev/null 2>&1
assert_eq "$?" "0" "verify: archive/ へ退避後も消し込みを追える"

# 出自を持たない work は従来どおり（後方互換）
run_bl new plain --mode autonomous >/dev/null
PLW=$(cat "$BLR/.aidev/current")
assert_absent "$(cat "$BLR/.aidev/works/$PLW/state.yml")" "backlog:" "new: --backlog 無しでは backlog 行を書かない"
: > "$BLR/.aidev/works/$PLW/review.md"
for p in requirement spec plan coding test review deliver; do run_bl approve "$p" >/dev/null; done
run_bl verify >/dev/null 2>&1
assert_eq "$?" "0" "verify: backlog 出自の無い work は従来どおり PASS"
rm -rf "$BLR"

echo "== status: backlog の inflight 列 =="
# 背景: backlog 行が [x] になるのは deliver。着手から着地までの間、backlog 側は
# 「掴まれている項目」と「素の未着手」を区別できず、新規セッションが二重に選びうる。
IFR=$(mktemp -d); mkdir -p "$IFR/.aidev/works" "$IFR/.aidev/backlog"
run_if() { ( cd "$IFR" && "$AIDEV_SH" "$@" ); }
cat > "$IFR/.aidev/backlog/q.md" <<'EOF'
---
kind: standing
---

- [ ] ひとつめ
- [ ] ふたつめ
EOF

run_if new inflight-a --mode autonomous --backlog q.md >/dev/null   # 着手中（未 deliver）
run_if new plain-b --mode autonomous >/dev/null                     # 刻印なし＝数えない
run_if new delivered-c --mode autonomous --backlog q.md >/dev/null
DC=$(cat "$IFR/.aidev/current")
: > "$IFR/.aidev/works/$DC/review.md"
for p in requirement spec plan coding test review deliver; do run_if approve "$p" >/dev/null; done

IF_TSV=$(run_if status --format tsv)
assert_contains "$IF_TSV" "backlog	q.md	2	0	1" "status: inflight=1（未 deliver の刻印付きだけ数える）"
assert_contains "$(run_if status)" "inflight" "status: 表形式に inflight 列が出る"

# deliver 済は掴んでいない＝落ちる（着地したら backlog 行は [x] 側で表現される）
assert_absent "$IF_TSV" "backlog	q.md	2	0	2" "status: deliver 済 work は inflight に数えない"
rm -rf "$IFR"

echo "== doctor: backlog ファイル横断検査 =="
# 背景: verify の消し込み検査は work にぶら下がるため、**ファイル自身の一生**（退避・frontmatter・
# 項目の書式）には持ち主がいなかった。batch は split を退避するが直接入口は退避せず、
# ts5250 では全消化 11 ファイルが未退避・frontmatter 全欠落のまま誰にも検知されていなかった。
DTR=$(mktemp -d); mkdir -p "$DTR/.aidev/works" "$DTR/.aidev/backlog/archive"
run_dt() { ( cd "$DTR" && "$AIDEV_SH" "$@" ); }

# standing の全消化は正常（継続キューなので退避しない）＝WARN を出してはいけない
cat > "$DTR/.aidev/backlog/standing-done.md" <<'EOF'
---
backlog: st
kind: standing
---

- [x] 済み → 20260101-alpha
EOF
# split の全消化は退避漏れ
cat > "$DTR/.aidev/backlog/split-done.md" <<'EOF'
---
backlog: sp
kind: split
parent: 20260101-alpha
---

- [x] 済み → 20260101-alpha
EOF
# topic の全消化も退避対象（一件で完結＝もう積まれない）
cat > "$DTR/.aidev/backlog/topic-done.md" <<'EOF'
---
backlog: tp
kind: topic
---

- [x] 済み → 20260101-alpha
EOF
# kind の誤記を黙って standing 扱いにすると退避検査がまるごと効かなくなる
cat > "$DTR/.aidev/backlog/typo-kind.md" <<'EOF'
---
kind: standig
---

- [x] 済み → 20260101-alpha
EOF
# frontmatter が無いと standing/split/topic を判定できない
cat > "$DTR/.aidev/backlog/nofront.md" <<'EOF'
# 見出しだけ

- [ ] まだ
EOF
# 見出し形式のチェックボックスは status の glob に掛からない＝未着手が見えなくなる
cat > "$DTR/.aidev/backlog/heading.md" <<'EOF'
---
kind: standing
---

## - [ ] 見出し形式の項目
EOF
# archive/ は status の *.md グロブから外れるので、未消化を退避すると誰の目にも入らない
cat > "$DTR/.aidev/backlog/archive/stale.md" <<'EOF'
---
kind: split
---

- [ ] 残ってる
- [x] 済み → 20260101-alpha
EOF

DT=$(run_dt doctor)
assert_contains "$DT" "backlog: ファイル横断検査" "doctor: backlog 検査の節を出す"
assert_contains "$DT" "全消化(split)だが未退避" "doctor: 全消化 split の退避漏れを検知"
assert_contains "$DT" "全消化(topic)だが未退避" "doctor: 全消化 topic の退避漏れを検知"
assert_contains "$DT" "未知の kind: standig" "doctor: kind の誤記を検知（黙って standing 扱いにしない）"
assert_contains "$DT" "frontmatter(kind)が無い" "doctor: frontmatter 欠落を検知"
assert_contains "$DT" "status が数えない書式の項目が 1 件" "doctor: 見出し形式の項目を検知"
assert_contains "$DT" "archive 済だが未消化が 1 件" "doctor: archive 内の未消化を検知"
assert_absent "$DT" "standing-done.md" "doctor: 全消化の standing は正常（WARN しない）"
assert_contains "$DT" "backlog-summary: files=6 archived=1 warn=6" "doctor: backlog サマリの件数"

run_dt doctor >/dev/null 2>&1
assert_eq "$?" "0" "doctor: backlog の WARN は exit code を変えない（硬ゲートは verify 側）"

if [ -n "$PS_HOST" ]; then
  O_PS=$( ( cd "$DTR" && run_ps1 "$AIDEV_PS1" doctor ) | tr -d '\r' )
  assert_eq "$DT" "$O_PS" "パリティ: doctor(backlog 検査)"
else
  skip "PowerShell(pwsh/powershell) 不在のため doctor(backlog) のパリティを省略"
fi
rm -rf "$DTR"

echo "== use / backlog new / backlog archive =="
# 背景: backlog の積む・退避する・current の切替は、検査だけあって**実行手段が無かった**
# （verify は消し込み漏れを FAIL させ doctor は退避漏れを WARN するのに、どちらも手作業だった）。
CLR=$(mktemp -d); mkdir -p "$CLR/.aidev/works"
run_cl() { ( cd "$CLR" && "$AIDEV_SH" "$@" ); }

run_cl backlog new nokind >/dev/null 2>&1
assert_eq "$?" "1" "backlog new: --kind は必須（欠落を構造的に防ぐ）"
run_cl backlog new sp --kind split >/dev/null 2>&1
assert_eq "$?" "1" "backlog new: kind=split は --parent 必須"
run_cl backlog new bad --kind standig >/dev/null 2>&1
assert_eq "$?" "1" "backlog new: 未知の kind を弾く"
run_cl backlog new demo --kind topic >/dev/null
DEMO=$(cat "$CLR/.aidev/backlog/demo.md")
assert_contains "$DEMO" "kind: topic" "backlog new: frontmatter に kind を書く"
assert_contains "$DEMO" "backlog: demo" "backlog new: frontmatter に識別名を書く"
run_cl backlog new demo --kind topic >/dev/null 2>&1
assert_eq "$?" "1" "backlog new: 既存ファイルは拒否"

A1=$(run_cl backlog archive)
assert_contains "$A1" "summary: archived=0 skipped=0" "backlog archive: 未消化は退避しない"
printf '%s\n' "- [x] 済み → 20260101-alpha" >> "$CLR/.aidev/backlog/demo.md"
A2=$(run_cl backlog archive)
assert_contains "$A2" "archived: demo.md" "backlog archive: 全消化 topic を退避"
assert_contains "$A2" "note: git 未反映" "backlog archive: git は触らないと明示（DESIGN 2.6）"
assert_eq "$(ls "$CLR/.aidev/backlog/archive/")" "demo.md" "backlog archive: archive/ へ移動している"

cat > "$CLR/.aidev/backlog/st.md" <<'EOF'
---
backlog: st
kind: standing
---

- [x] 済み → 20260101-alpha
EOF
A3=$(run_cl backlog archive st.md)
assert_contains "$A3" "退避条件を満たしません" "backlog archive: standing は明示指定でも退避しない"
A4=$(run_cl backlog archive st.md --force)
assert_contains "$A4" "archived: st.md" "backlog archive: --force なら条件を越えられる"

# doctor の WARN と archive の実行が**同じ判定**を通ること（検査と実行の一致）
cat > "$CLR/.aidev/backlog/tp.md" <<'EOF'
---
backlog: tp
kind: topic
---

- [x] 済み → 20260101-alpha
EOF
assert_contains "$(run_cl doctor)" "全消化(topic)だが未退避" "doctor: 退避漏れを WARN"
run_cl backlog archive >/dev/null
assert_absent "$(run_cl doctor)" "全消化(topic)だが未退避" "archive 実行で doctor の WARN が消える（判定が一致）"

run_cl new alpha --mode autonomous >/dev/null
CW1=$(cat "$CLR/.aidev/current")
run_cl new beta --mode autonomous >/dev/null
assert_eq "$(run_cl use)" "$(cat "$CLR/.aidev/current")" "use: 引数なしで現在値を出す"
CU=$(run_cl use "$CW1")
assert_contains "$CU" "current: $CW1" "use: 別の work へ切り替える"
assert_eq "$(cat "$CLR/.aidev/current")" "$CW1" "use: .aidev/current が実際に書き換わる"
run_cl use nosuch >/dev/null 2>&1
assert_eq "$?" "1" "use: 存在しない slug を弾く（手書きの打ち間違い対策）"

if [ -n "$PS_HOST" ]; then
  for args in "use" "backlog archive"; do
    # shellcheck disable=SC2086
    O_SH=$( ( cd "$CLR" && "$AIDEV_SH" $args ) )
    # shellcheck disable=SC2086
    O_PS=$( ( cd "$CLR" && run_ps1 "$AIDEV_PS1" $args ) | tr -d '\r' )
    assert_eq "$O_SH" "$O_PS" "パリティ: $args"
  done
else
  skip "PowerShell(pwsh/powershell) 不在のため use / backlog のパリティを省略"
fi
rm -rf "$CLR"

echo "== 実行プロファイル（profile: full / light・escalate） =="
# protocol.md「11.」。mode（誰が承認するか）と直交する軸で、既定は full。
# 別リポジトリで回す（$TMP 側の status 件数アサートを壊さないため）。
LREPO="$TMP/lrepo"
mkdir -p "$LREPO/.aidev/works" "$LREPO/.aidev/backlog"
run_lsh() { ( cd "$LREPO" && "$AIDEV_SH" "$@" ); }

L_NEW=$(run_lsh new tiny --light)
assert_contains "$L_NEW" "profile light" "new --light: profile light を報告"
assert_contains "$L_NEW" "requirement 1ゲート" "new --light: 上流1ゲートの注意を出す"
L_SLUG=$(cat "$LREPO/.aidev/current")
assert_contains "$(cat "$LREPO/.aidev/works/$L_SLUG/state.yml")" "profile: light" "new --light: state.yml に profile: light"

F_NEW=$(run_lsh new normal)
F_SLUG=$(cat "$LREPO/.aidev/current")
assert_contains "$F_NEW" "profile full" "new(既定): profile full"
assert_absent  "$F_NEW" "requirement 1ゲート" "new(既定): light の注意は出さない"

run_lsh new bad --profile medium >/dev/null 2>&1; assert_eq "$?" "1" "不正な --profile は exit 1"

# subtask は親の profile を継承する（親 light / 子 full の食い違いを構造的に防ぐ）
P_NEW=$(run_lsh new parent-light --light); P_SLUG=$(cat "$LREPO/.aidev/current")
assert_contains "$P_NEW" "profile light" "new --light(親): profile light"
S_NEW=$(run_lsh new 01-a --parent "$P_SLUG")
assert_contains "$S_NEW" "profile light" "subtask: 親の profile を継承する"

# light 逸脱の WARN: 任意工程の実施 + 変更規模の上限超過
cat >> "$LREPO/.aidev/works/$L_SLUG/metrics.yml" <<'EOF'
  - { ts: 2026-08-23T01:00:00Z, phase: research, event: start }
  - { ts: 2026-08-23T03:00:00Z, phase: deliver, event: start }
  - { ts: 2026-08-23T03:10:00Z, phase: deliver, event: approved, metrics: { files_changed: 9 } }
EOF
LV=$(run_lsh verify "$L_SLUG")
assert_contains "$LV" "任意工程 research を実施" "verify: light で任意工程を使ったら WARN"
assert_contains "$LV" "変更 9 ファイル（上限 3）" "verify: light で規模超過なら WARN"
run_lsh verify "$L_SLUG" >/dev/null 2>&1; assert_eq "$?" "0" "light の WARN は exit code を変えない（硬ゲートは既存判定）"

printf 'lightMaxFiles: 20\n' > "$LREPO/.aidev/config.yml"
LV2=$(run_lsh verify "$L_SLUG")
assert_absent "$LV2" "変更 9 ファイル" "config.yml の lightMaxFiles で上限を緩められる"
rm -f "$LREPO/.aidev/config.yml"

FV=$(run_lsh verify "$F_SLUG")
assert_absent "$FV" "profile=light" "full な work に light の WARN は出ない"

# escalate は片方向（full -> light には戻せない）
LE=$(run_lsh escalate "$L_SLUG")
assert_contains "$LE" "light -> full" "escalate: 昇格を報告"
assert_contains "$(cat "$LREPO/.aidev/works/$L_SLUG/state.yml")" "profile: full" "escalate: state.yml が full になる"
run_lsh escalate "$L_SLUG" >/dev/null 2>&1; assert_eq "$?" "1" "escalate: full からは戻せない（片方向）"
LV3=$(run_lsh verify "$L_SLUG")
assert_absent "$LV3" "profile=light" "昇格後は light の WARN が消える"

# profile 未記載（導入前の work）は full 扱い＝WARN も escalate も対象外
mkdir -p "$LREPO/.aidev/works/20260101-oldwork"
cat > "$LREPO/.aidev/works/20260101-oldwork/state.yml" <<'EOF'
schema: 2
slug: oldwork
current: coding
approved: [requirement, spec, plan]
mode: interactive
humanGates: []
maxSendBacks: 3
dependsOn: []
EOF
printf 'events:\n' > "$LREPO/.aidev/works/20260101-oldwork/metrics.yml"
OV=$(run_lsh verify 20260101-oldwork)
assert_absent "$OV" "profile=light" "profile 未記載の work は full 扱い（後方互換）"
run_lsh escalate 20260101-oldwork >/dev/null 2>&1; assert_eq "$?" "1" "profile 未記載の work は escalate 不可（full 扱い）"

echo "== verify --strict（記録漏れを致命にする機械ゲート） =="
# protocol.md「2.6」第三層（フック）から使う。既定の verify は WARN 止まり（既存 work を壊さない）
# ままにし、--strict のときだけ「今しか直せない」記録漏れを exit 5 にする。
SREPO="$TMP/srepo"
mkdir -p "$SREPO/.aidev/works" "$SREPO/.aidev/backlog"
run_ssh() { ( cd "$SREPO" && "$AIDEV_SH" "$@" ); }

run_ssh new rec-gap >/dev/null
S_SLUG=$(cat "$SREPO/.aidev/current")
# start の無い approved（＝記録漏れ）を仕込む
printf 'events:\n  - { ts: 2026-08-23T01:00:00Z, phase: coding, event: approved }\n' \
  > "$SREPO/.aidev/works/$S_SLUG/metrics.yml"

SV=$(run_ssh verify); assert_contains "$SV" "WARN coding" "既定 verify: 記録漏れを WARN で出す"
run_ssh verify >/dev/null 2>&1; assert_eq "$?" "0" "既定 verify: 記録漏れでも exit 0（既存 work を壊さない）"

SVS=$(run_ssh verify --strict)
assert_contains "$SVS" "WARN coding" "--strict: WARN も従来どおり出す"
assert_contains "$SVS" "FAIL(strict) 記録漏れ" "--strict: 記録漏れを FAIL として明示"
run_ssh verify --strict >/dev/null 2>&1; assert_eq "$?" "5" "--strict: 記録漏れは exit 5"

# 記録を補えば通る（＝直し方が伝わる形になっている）
printf '  - { ts: 2026-08-23T00:50:00Z, phase: coding, event: start }\n' \
  >> "$SREPO/.aidev/works/$S_SLUG/metrics.yml"
run_ssh verify --strict >/dev/null 2>&1; assert_eq "$?" "0" "--strict: start を補えば exit 0"

# light の逸脱は「人間の判断」なので strict でも致命にしない
run_ssh new light-dev --light >/dev/null
L2_SLUG=$(cat "$SREPO/.aidev/current")
cat >> "$SREPO/.aidev/works/$L2_SLUG/metrics.yml" <<'EOF'
  - { ts: 2026-08-23T01:00:00Z, phase: research, event: start }
  - { ts: 2026-08-23T01:10:00Z, phase: research, event: approved }
EOF
LS_OUT=$(run_ssh verify --strict "$L2_SLUG")
assert_contains "$LS_OUT" "profile=light だが任意工程 research" "--strict: light の逸脱は WARN のまま出す"
run_ssh verify --strict "$L2_SLUG" >/dev/null 2>&1
assert_eq "$?" "0" "--strict: light の逸脱は致命にしない（昇格は人間の判断）"

run_ssh verify --bogus >/dev/null 2>&1; assert_eq "$?" "1" "verify: 未知のオプションは exit 1"

# doctor は横断スキャンなので strict にならない（verify_work の STRICT が漏れない）
printf 'events:\n  - { ts: 2026-08-23T01:00:00Z, phase: coding, event: approved }\n' \
  > "$SREPO/.aidev/works/$S_SLUG/metrics.yml"
run_ssh doctor >/dev/null 2>&1; assert_eq "$?" "0" "doctor: --strict の影響を受けない（WARN 止まり）"

echo "== convention（条項の一生 / 効果検証の母集団 / 二重管理の防止） =="
# 背景: retro/insights の「PJ プロセス / 規約」の宛先が AGENTS.md（=PJ 所有）だったため、
# 「依存しないと宣言したファイルに harness が書き戻す」構造になっていた。生成物は docs/aidev/ へ移し、
# **効果が確認できたら PJ ドキュメントへ移送して本文を1箇所に保つ**（protocol.md「12.」）。
CVR=$(mktemp -d); mkdir -p "$CVR/.aidev/works" "$CVR/docs"
run_cv() { ( cd "$CVR" && "$AIDEV_SH" "$@" ); }

# --- 入口ゲート: 仮説の無い条項は作らせない（検証不能な改善を積まない） ---
run_cv convention new naming >/dev/null 2>&1
assert_eq "$?" "1" "convention new: --hypothesis は必須（検証できない条項を弾く）"
run_cv convention new naming --hypothesis "x" >/dev/null 2>&1
assert_eq "$?" "1" "convention new: --baseline は必須（起票時にしか「前」を作れない）"
assert_eq "$([ -e "$CVR/docs/aidev/naming.md" ] && echo yes || echo no)" "no" \
  "convention new: 入口ゲートで弾いたらファイルを作らない"
run_cv convention new naming --hypothesis "x" --baseline "b" --verify-after abc >/dev/null 2>&1
assert_eq "$?" "1" "convention new: --verify-after は整数"

CV_NEW=$(run_cv convention new naming-boolean --hypothesis "命名の must/should 指摘が減る" --baseline "b" \
  --source ".aidev/insights/2026-08-28-insights.md" --verify-after 2 2>&1)
assert_contains "$CV_NEW" "status pending" "convention new: pending で起こす"
assert_contains "$CV_NEW" "AGENTS.md の索引ブロック" "convention new: 索引への追記を促す（自動読込されないため）"
CVF="$CVR/docs/aidev/naming-boolean.md"
assert_eq "$([ -f "$CVF" ] && echo yes || echo no)" "yes" "convention new: 既定の conventionsDir は docs/aidev"
CVB=$(cat "$CVF")
assert_contains "$CVB" "hypothesis: 命名の must/should 指摘が減る" "convention new: 仮説を frontmatter に残す"
assert_contains "$CVB" "verify_after: 2" "convention new: 判定に要する母集団件数を残す"
assert_contains "$CVB" "source: .aidev/insights/2026-08-28-insights.md" "convention new: 出所を残す"
# 条項 id は今この瞬間に生まれるので、導入前の review.md にその id は決して現れない。
# 「前」は起票時に観点で数えて刻んだこの値だけ。落ちると効果検証が前後比較でなくなる。
assert_contains "$CVB" "baseline: b" "convention new: baseline を frontmatter に残す（判定の「前」）"
run_cv convention new naming-boolean --hypothesis "again" --baseline "b" >/dev/null 2>&1
assert_eq "$?" "1" "convention new: 同名の active は拒否"

# --- 母集団: introduced 以降に着手した work だけを数える ---
CV_S0=$(run_cv convention status --format tsv)
assert_contains "$CV_S0" "naming-boolean	pending" "convention status: pending を出す"
assert_contains "$CV_S0" "	0	2	no	" "convention status: 母集団 0 件では ready=no"

TODAY=$(date -u +%Y%m%d)
for w in one two; do
  mkdir -p "$CVR/.aidev/works/$TODAY-$w"
  printf 'schema: 4\nslug: %s\ncurrent: deliver\napproved: [deliver]\nharnessRev: aaa1111\n' "$w" \
    > "$CVR/.aidev/works/$TODAY-$w/state.yml"
  printf 'events:\n  - { ts: %s-01:00:00Z, phase: requirement, event: start }\n' \
    "$(date -u +%Y-%m-%dT)" > "$CVR/.aidev/works/$TODAY-$w/metrics.yml"
done
# 着手しただけの work は review を通っていない＝判定材料を1つも産んでいないので数えない。
# ここを数えると、レビュー記録がまだ無いのに ready=yes が立ち insights が空の材料で判定する。
mkdir -p "$CVR/.aidev/works/$TODAY-inflight"
printf 'schema: 4\nslug: inflight\ncurrent: coding\napproved: [requirement, spec]\n' \
  > "$CVR/.aidev/works/$TODAY-inflight/state.yml"
printf 'events:\n  - { ts: %s-01:00:00Z, phase: requirement, event: start }\n' \
  "$(date -u +%Y-%m-%dT)" > "$CVR/.aidev/works/$TODAY-inflight/metrics.yml"
# 導入日より前に着手した work は母集団に入れない（効果を受けていないため）
mkdir -p "$CVR/.aidev/works/20200101-old"
printf 'schema: 4\nslug: old\ncurrent: requirement\napproved: []\n' > "$CVR/.aidev/works/20200101-old/state.yml"
printf 'events:\n  - { ts: 2020-01-01T01:00:00Z, phase: requirement, event: start }\n' \
  > "$CVR/.aidev/works/20200101-old/metrics.yml"

CV_S1=$(run_cv convention status --format tsv)
assert_contains "$CV_S1" "	2	2	yes	" "convention status: 母集団は deliver 済みだけを数える（導入前・着手中は数えない）"

# --- doctor: 判定できる状態になったら催促する（人間が思い立つまで待たない） ---
CV_D1=$(run_cv doctor 2>&1)
assert_contains "$CV_D1" "母集団が揃った(2/2)のに未判定" "doctor: 判定可能なのに未判定を WARN"
assert_contains "$CV_D1" "convention-summary: files=1 archived=0 warn=1" "doctor: 条項のサマリを出す"

# --- confirmed のまま放置＝二重管理予備軍 ---
run_cv convention confirm naming-boolean --result "must 3件 -> 0件" >/dev/null
assert_contains "$(cat "$CVF")" "status: confirmed" "convention confirm: status を進める"
assert_contains "$(cat "$CVF")" "result: must 3件 -> 0件" "convention confirm: 判定の内訳を残す"
CV_D2=$(run_cv doctor 2>&1)
assert_contains "$CV_D2" "confirmed だが未移送" "doctor: 移送漏れ（PJ docs との二重管理予備軍）を WARN"

# --- promote: 移送先の実在を検査し、本文を捨てて tombstone にする ---
run_cv convention promote naming-boolean --to docs/coding-standards.md#naming >/dev/null 2>&1
assert_eq "$?" "1" "convention promote: 実在しない移送先を弾く（dangling な promoted_to を作らない）"
printf '# coding standards\n' > "$CVR/docs/coding-standards.md"
CV_P=$(run_cv convention promote naming-boolean --to docs/coding-standards.md#naming 2>&1)
assert_contains "$CV_P" "索引ブロックのリンク先" "convention promote: 索引の張り替えを促す"
assert_eq "$([ -f "$CVF" ] && echo yes || echo no)" "no" "convention promote: active から退避される"
CVT=$(cat "$CVR/docs/aidev/archive/naming-boolean.md")
assert_contains "$CVT" "promoted_to: docs/coding-standards.md#naming" "convention promote: 移送先を刻む"
assert_contains "$CVT" "本文は promoted_to へ移送済み" "convention promote: 本文を捨てて tombstone にする"
assert_absent "$CVT" "## 規約" "convention promote: 本文が2箇所に存在しない（二重管理の防止）"

# --- tombstone は重複排除のために残す（消すと同じ提案がまた上がる） ---
run_cv convention new naming-boolean --hypothesis "again" --baseline "b" >/dev/null 2>&1
assert_eq "$?" "1" "convention new: archive の tombstone と同 id は重複として弾く"

# --- retire: 効かなかった条項の行き先は「削除」ではなく「層を下げる」 ---
run_cv convention new err-gran --hypothesis "エラー粒度の指摘が減る" --baseline "b" >/dev/null
run_cv convention retire err-gran --status bogus >/dev/null 2>&1
assert_eq "$?" "1" "convention retire: 未知の status を弾く"
CV_R=$(run_cv convention retire err-gran --status ineffective --note "散文層の限界" 2>&1)
assert_contains "$CV_R" "CLI/フック層へ寄せる" "convention retire: ineffective は層を下げる検討を促す"
assert_contains "$(cat "$CVR/docs/aidev/archive/err-gran.md")" "note: 散文層の限界" "convention retire: 理由を残す"

# 全部退避されたので警告は消える（定常状態では pending だけが active に残る）
CV_D3=$(run_cv doctor 2>&1)
assert_contains "$CV_D3" "convention-summary: files=0 archived=2 warn=0" "doctor: 退避済みなら警告なし"

# --- 手編集で壊れた条項も拾う（frontmatter は人間も触る） ---
mkdir -p "$CVR/docs/aidev"
printf -- '---\nconvention: broken\n---\n\n# broken\n' > "$CVR/docs/aidev/broken.md"
printf -- '---\nconvention: weird\nstatus: kinda\n---\n\n# weird\n' > "$CVR/docs/aidev/weird.md"
CV_D4=$(run_cv doctor 2>&1)
assert_contains "$CV_D4" "frontmatter(status)が無い" "doctor: status 欠落を WARN"
assert_contains "$CV_D4" "未知の status: kinda" "doctor: 誤記を黙って通さない"

# --- conventionsDir は PJ が変えられる ---
CVR2=$(mktemp -d); mkdir -p "$CVR2/.aidev/works"
printf 'conventionsDir: docs/rules\n' > "$CVR2/.aidev/config.yml"
( cd "$CVR2" && "$AIDEV_SH" convention new x --hypothesis "y" --baseline "b" >/dev/null )
assert_eq "$([ -f "$CVR2/docs/rules/x.md" ] && echo yes || echo no)" "yes" "conventionsDir で置き場を変えられる"
rm -rf "$CVR2"



echo "== convention: 破壊的操作のガード（データ喪失の回帰） =="
# 背景: promote は本文を捨てて tombstone にする。その前に「条項ファイルか」「行き先が空か」を
# 確かめないと、無関係な md を 0 バイトにしたり、失敗した後に破壊だけが残ったりする。
# 実際に3件とも起きていた（README を消す / ../foo で外を壊す / 衝突時に本文だけ消える）。
GRD=$(mktemp -d); mkdir -p "$GRD/.aidev/works" "$GRD/docs/aidev"
run_gd() { ( cd "$GRD" && "$AIDEV_SH" "$@" ); }
printf '# tgt\n' > "$GRD/tgt.md"

# --- frontmatter が無いファイルを条項として扱わない ---
printf '# README\n\nこのディレクトリの説明。消えてはいけない。\n' > "$GRD/docs/aidev/README.md"
SZ0=$(wc -c < "$GRD/docs/aidev/README.md")
run_gd convention promote README --to 'tgt.md#x' >/dev/null 2>&1
assert_eq "$?" "1" "promote: frontmatter の無いファイルを弾く"
assert_eq "$(wc -c < "$GRD/docs/aidev/README.md")" "$SZ0" "promote: 弾いたファイルの本文が無傷（0バイト化しない）"
run_gd convention confirm README >/dev/null 2>&1
assert_eq "$?" "1" "confirm: frontmatter の無いファイルを弾く"

# --- id にパス成分を書いても条項ディレクトリの外に出ない ---
# 外のファイルを**正しい条項の見た目**にしておく。こうしないと frontmatter 検査の方が
# 先に弾いてしまい、id の sanitize が効いているかを確かめられない（両方を独立に検査する）。
printf -- '---\nconvention: important\nstatus: pending\nintroduced: 2026-01-01\nhypothesis: h\nverify_after: 1\n---\n\n# 重要\n\n消えてはいけない本文。\n' > "$GRD/docs/important.md"
SZ1=$(wc -c < "$GRD/docs/important.md")
run_gd convention promote ../important --to 'tgt.md#a' >/dev/null 2>&1
assert_eq "$?" "1" "promote: id のパス成分を潰す（../ で外に出ない）"
assert_eq "$(wc -c < "$GRD/docs/important.md")" "$SZ1" "promote: 条項ディレクトリ外のファイルが無傷"
run_gd convention retire ../important --status ineffective >/dev/null 2>&1
assert_eq "$?" "1" "retire: id のパス成分を潰す"
assert_eq "$([ -f "$GRD/docs/important.md" ] && echo yes || echo no)" "yes" "retire: 外のファイルを移動しない"

# --- 退避先が埋まっているときは、破壊する前に失敗する ---
run_gd convention new dup --hypothesis h --baseline "b" >/dev/null
run_gd convention retire dup --status ineffective >/dev/null
printf -- '---\nconvention: dup\nstatus: pending\nintroduced: 2026-01-01\nhypothesis: h\nverify_after: 1\n---\n\n# dup\n\n本文。\n' > "$GRD/docs/aidev/dup.md"
SZ2=$(wc -c < "$GRD/docs/aidev/dup.md")
run_gd convention promote dup --to 'tgt.md#a' >/dev/null 2>&1
assert_eq "$?" "1" "promote: archive が埋まっていれば失敗する"
assert_eq "$(wc -c < "$GRD/docs/aidev/dup.md")" "$SZ2" "promote: 失敗時に本文を破壊しない（非原子性の回帰）"
rm -rf "$GRD"

echo "== convention: 母集団の着手日を metrics キーと取り違えない =="
# 背景: `.*ts:` は貪欲なので行内の最後の ts: を拾う。metrics キーが ts で終わる
# （defects / commits / tests / artifacts …）と、その数値を着手日として読んでいた。
TSR=$(mktemp -d); mkdir -p "$TSR/.aidev/works"
run_ts() { ( cd "$TSR" && "$AIDEV_SH" "$@" ); }
run_ts convention new tsconv --hypothesis h --baseline "b" --verify-after 1 >/dev/null
TODAY_D=$(date -u +%Y%m%d); TODAY_T=$(date -u +%Y-%m-%d)
mkdir -p "$TSR/.aidev/works/$TODAY_D-w"
printf 'schema: 4\nslug: w\ncurrent: deliver\napproved: [deliver]\n' > "$TSR/.aidev/works/$TODAY_D-w/state.yml"
# 1行目のイベントに ts で終わる metrics キーを載せる
printf 'events:\n  - { ts: %sT01:00:00Z, phase: coding, event: start, metrics: { defects: 3 } }\n' \
  "$TODAY_T" > "$TSR/.aidev/works/$TODAY_D-w/metrics.yml"
assert_contains "$(run_ts convention status --format tsv)" "	1	1	yes	" \
  "母集団: metrics キー(defects)を着手日と取り違えない"
rm -rf "$TSR"
echo "== convention: 索引（AGENTS.md の aidev:conventions ブロック） =="
# 背景: AGENTS.md は自動読込されるが docs/aidev/ はされない。索引に載っていない条項は**読まれないまま**
# works が流れ、効果検証で「効かなかった」と誤判定される——条項の内容の問題ではなく届いていないだけなのに。
# CLI が「索引に足せ」と言うだけで誰も見ていないと、この誤判定が静かに積み上がる。
IXR=$(mktemp -d); mkdir -p "$IXR/.aidev/works" "$IXR/docs"
run_ix() { ( cd "$IXR" && "$AIDEV_SH" "$@" ); }
IX_NEW=$(run_ix convention new naming --hypothesis "命名の指摘が減る" --baseline "b" --verify-after 1 2>&1)
assert_contains "$IX_NEW" "docs/aidev/naming.md" "convention new: 索引に足す行を提示する（機械にできる部分は機械が出す）"
assert_contains "$IX_NEW" "docsRoots が未設定" "convention new: 未設定なら「確認していない」と明記させる（捏造で埋めない）"

IX_D0=$(run_ix doctor 2>&1)
assert_contains "$IX_D0" "索引ファイルが無い" "doctor: 索引ファイル自体が無いことを WARN"

printf '# AGENTS\n\n<!-- aidev:conventions -->\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
IX_D1=$(run_ix doctor 2>&1)
assert_contains "$IX_D1" "索引に無い（AGENTS.md）" "doctor: 索引に未登録の条項を WARN"
assert_contains "$IX_D1" "→ docs/aidev/naming.md" "doctor: 足すべき行をそのまま示す（検査だけあって実行が無い形にしない）"
assert_contains "$(run_ix convention status)" "no" "convention status: index 列で索引漏れが見える"
assert_contains "$(run_ix convention status)" "索引漏れ=1" "convention status: 索引漏れ件数をサマリに出す"

# 索引に登録すれば警告は消える
printf '# AGENTS\n\n<!-- aidev:conventions -->\n- 命名を判断するとき → docs/aidev/naming.md\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
IX_D2=$(run_ix doctor 2>&1)
assert_absent "$IX_D2" "索引に無い" "doctor: 索引に載っていれば警告しない"
assert_contains "$(run_ix convention status)" "索引漏れ=0" "convention status: 登録済みなら索引漏れ 0"

# マーカー外に書いても索引とは認めない（harness が見るのはブロック内だけ）
printf '# AGENTS\n\n- 命名 → docs/aidev/naming.md\n\n<!-- aidev:conventions -->\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
assert_contains "$(run_ix doctor 2>&1)" "索引に無い" "doctor: マーカー外の記述は索引と認めない（PJ の領域は見ない）"

# 移送したら索引の張り替え漏れを検知する（promote が「張り替えろ」と言うだけでは誰も見ていない）
printf '# AGENTS\n\n<!-- aidev:conventions -->\n- 命名を判断するとき → docs/aidev/naming.md\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
printf '# std\n' > "$IXR/docs/std.md"
run_ix convention confirm naming >/dev/null
run_ix convention promote naming --to docs/std.md#naming >/dev/null
IX_D3=$(run_ix doctor 2>&1)
assert_contains "$IX_D3" "索引が移送前を指したまま" "doctor: 移送後の張り替え漏れを WARN"
printf '# AGENTS\n\n<!-- aidev:conventions -->\n- 命名を判断するとき → docs/std.md#naming\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
assert_absent "$(run_ix doctor 2>&1)" "索引が移送前" "doctor: 張り替え済みなら警告しない"

# 索引ファイルは PJ が config で指定できる（PJ 固有名を CLI に埋めない）
printf 'conventionsIndex: docs/rules.md\n' > "$IXR/.aidev/config.yml"
printf 'x\n' > "$IXR/docs/rules.md"
run_ix convention new err --hypothesis h --baseline "b" >/dev/null
assert_contains "$(run_ix doctor 2>&1)" "索引に無い（rules.md）" "conventionsIndex で索引ファイルを差し替えられる"
rm -rf "$IXR"

echo "== convention: 母集団は deliver で増える（到達をその瞬間に知らせる） =="
# 背景: doctor の WARN は retro/insights を叩いた人にしか見えない＝既に見に行った人にしか届かない。
# works が母集団に加わる唯一の瞬間は approve deliver なので、そこで鳴らす。
RDR=$(mktemp -d); mkdir -p "$RDR/.aidev/works"
run_rd() { ( cd "$RDR" && "$AIDEV_SH" "$@" ); }
run_rd convention new conv1 --hypothesis h --baseline "b" --verify-after 1 >/dev/null
run_rd new rd >/dev/null
RDW=$(ls "$RDR/.aidev/works")
for p in requirement spec plan coding test review; do
  run_rd event "$p" start >/dev/null; run_rd approve "$p" >/dev/null
done
: > "$RDR/.aidev/works/$RDW/review.md"
# deliver 前は判定材料が無いので ready にならない
assert_contains "$(run_rd convention status --format tsv)" "	0	1	no	" "母集団: deliver 前の work は数えない（review 記録がまだ無い）"
run_rd event deliver start >/dev/null
RD_A=$(run_rd approve deliver files_changed=1 insertions=1 deletions=0 2>&1)
assert_contains "$RD_A" "条項 conv1 の母集団が揃いました(1/1)" "approve deliver: 母集団が揃った瞬間に知らせる"
assert_contains "$(run_rd convention status --format tsv)" "	1	1	yes	" "母集団: deliver 済みになって初めて数える"
rm -rf "$RDR"
echo "== harnessRev（効果検証の母集団の刻印） =="
# 背景: ハーネス改修が効いたかを後から判定するには「どの版で回した work か」が要る。
# 手書きに任せると忘れられ、忘れられた work は母集団から静かに漏れる（schema: と同じ理由で new に一本化）。
HVR=$(mktemp -d); mkdir -p "$HVR/.aidev/works"
run_hv() { ( cd "$HVR" && "$AIDEV_SH" "$@" ); }
run_hv new hv >/dev/null
HVW=$(ls "$HVR/.aidev/works")
HVST="$HVR/.aidev/works/$HVW/state.yml"
assert_contains "$(cat "$HVST")" "harnessRev:" "new: harnessRev を自動で刻む"
assert_contains "$(cat "$HVST")" "schema: $CUR_SCHEMA" "new: schema は CURRENT_SCHEMA"

# またがり work（着手時と着地時で版が違う）は効果を半分しか受けていないので母集団から外す
for p in requirement spec plan coding test review deliver; do
  run_hv event "$p" start >/dev/null
done
: > "$HVR/.aidev/works/$HVW/review.md"
# 着手後にハーネスが改修された状況を作る（着手時の刻印だけを別版に書き換える）
awk '{ if ($0 ~ /^harnessRev:/) print "harnessRev: deadbee"; else print }' "$HVST" > "$HVST.t" && mv "$HVST.t" "$HVST"
run_hv approve deliver files_changed=1 insertions=1 deletions=0 >/dev/null
assert_contains "$(cat "$HVST")" "harnessRevDelivered:" "approve deliver: 着地時の版も刻む"
HV_V=$(run_hv verify 2>&1)
assert_contains "$HV_V" "またがり work" "verify: またがり work を WARN（母集団から除外する合図）"

# schema<4 の旧 work は遡って違反扱いしない（version-aware）
mkdir -p "$HVR/.aidev/works/20200101-legacy"
printf 'schema: 3\nslug: legacy\ncurrent: requirement\napproved: []\n' > "$HVR/.aidev/works/20200101-legacy/state.yml"
printf 'events:\n' > "$HVR/.aidev/works/20200101-legacy/metrics.yml"
HV_L=$(run_hv verify 20200101-legacy 2>&1)
assert_absent "$HV_L" "harnessRev が無い" "verify: schema<4 の work に harnessRev を要求しない"
rm -rf "$HVR"

echo "== sh ⇔ ps1 パリティ =="
if [ -n "$PS_HOST" ]; then
  # verify --strict のパリティ（exit code と出力が sh と一致すること）
  for sargs in "verify --strict $S_SLUG" "verify --strict $L2_SLUG"; do
    # shellcheck disable=SC2086
    S_SH=$( ( cd "$SREPO" && "$AIDEV_SH" $sargs ) 2>&1 ); S_SH_RC=$?
    # shellcheck disable=SC2086
    # 注意: `$(… | tr)` の `$?` は **tr の** 終了コードになり、常に 0 を拾ってしまう。
    #       exit code を比べるなら CR 除去は代入を分ける（この取り違えを実際にやった）
    S_PS_RAW=$( ( cd "$SREPO" && run_ps1 "$AIDEV_PS1" $sargs ) 2>&1 ); S_PS_RC=$?
    S_PS=$(printf '%s' "$S_PS_RAW" | tr -d '\r')
    assert_eq "$S_SH" "$S_PS" "パリティ: $sargs（出力）"
    assert_eq "$S_SH_RC" "$S_PS_RC" "パリティ: $sargs（exit code）"
  done


  # convention のパリティ（条項の一生が OS で食い違うと、片方の環境だけ二重管理が起きる）
  PCV=$(mktemp -d); mkdir -p "$PCV/.aidev/works" "$PCV/docs"
  printf '# std\n' > "$PCV/docs/std.md"
  mkdir -p "$PCV/.aidev/works/20200101-w1"
  printf 'schema: 4\nslug: w1\ncurrent: requirement\napproved: []\n' > "$PCV/.aidev/works/20200101-w1/state.yml"
  printf 'events:\n  - { ts: 2020-01-01T01:00:00Z, phase: requirement, event: start }\n' \
    > "$PCV/.aidev/works/20200101-w1/metrics.yml"

  # sh 側で一生を進め、同じ操作を ps1 側でも行って生成物を突き合わせる
  ( cd "$PCV" && "$AIDEV_SH" convention new sh-side --hypothesis "h1" --baseline "b" --verify-after 1 >/dev/null )
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention new ps-side --hypothesis "h1" --baseline "b" --verify-after 1 >/dev/null )
  CP_SH=$(sed 's/^introduced: .*/introduced: X/' "$PCV/docs/aidev/sh-side.md")
  CP_PS=$(tr -d '\r' < "$PCV/docs/aidev/ps-side.md" | sed 's/^introduced: .*/introduced: X/; s/^convention: ps-side/convention: sh-side/; s/^# ps-side/# sh-side/')
  assert_eq "$CP_SH" "$CP_PS" "パリティ: convention new の生成ファイルが一致"

  CS_SH=$( ( cd "$PCV" && "$AIDEV_SH" convention status --format tsv ) 2>&1 )
  CS_PS=$( ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention status --format tsv ) 2>&1 | tr -d '\r' )
  assert_eq "$CS_SH" "$CS_PS" "パリティ: convention status（母集団の数え方が一致）"

  CD_SH=$( ( cd "$PCV" && "$AIDEV_SH" doctor ) 2>&1 | sed -n '/^convention:/,$p' )
  CD_PS=$( ( cd "$PCV" && run_ps1 "$AIDEV_PS1" doctor ) 2>&1 | tr -d '\r' | sed -n '/^convention:/,$p' )
  assert_eq "$CD_SH" "$CD_PS" "パリティ: doctor の条項検査（未判定の催促が一致）"

  ( cd "$PCV" && "$AIDEV_SH" convention confirm sh-side >/dev/null )
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention confirm ps-side >/dev/null )
  ( cd "$PCV" && "$AIDEV_SH" convention promote sh-side --to docs/std.md#a >/dev/null )
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention promote ps-side --to docs/std.md#a >/dev/null )
  CT_SH=$(sed 's/^introduced: .*/introduced: X/; s/^promoted_at: .*/promoted_at: X/' "$PCV/docs/aidev/archive/sh-side.md")
  CT_PS=$(tr -d '\r' < "$PCV/docs/aidev/archive/ps-side.md" | sed 's/^introduced: .*/introduced: X/; s/^promoted_at: .*/promoted_at: X/; s/^convention: ps-side/convention: sh-side/')
  assert_eq "$CT_SH" "$CT_PS" "パリティ: promote の tombstone が一致（本文の捨て方が同じ）"

  # 入口ゲート（仮説必須）と重複排除は両実装で同じ exit code
  ( cd "$PCV" && "$AIDEV_SH" convention new nohyp >/dev/null 2>&1 ); CG_SH=$?
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention new nohyp >/dev/null 2>&1 ); CG_PS=$?
  assert_eq "$CG_SH" "$CG_PS" "パリティ: --hypothesis 必須の exit code"
  ( cd "$PCV" && "$AIDEV_SH" convention new nobase --hypothesis h >/dev/null 2>&1 ); CB_SH=$?
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention new nobase --hypothesis h >/dev/null 2>&1 ); CB_PS=$?
  assert_eq "$CB_SH" "$CB_PS" "パリティ: --baseline 必須の exit code"
  ( cd "$PCV" && "$AIDEV_SH" convention new sh-side --hypothesis h --baseline "b" >/dev/null 2>&1 ); CX_SH=$?
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention new sh-side --hypothesis h --baseline "b" >/dev/null 2>&1 ); CX_PS=$?
  assert_eq "$CX_SH" "$CX_PS" "パリティ: tombstone との重複拒否の exit code"
  rm -rf "$PCV"



  # 破壊的操作のガードのパリティ（片方だけ緩いと、その OS でだけデータが消える）
  PGD=$(mktemp -d); mkdir -p "$PGD/.aidev/works" "$PGD/docs/aidev"
  printf '# tgt\n' > "$PGD/tgt.md"
  printf '# README\n\n消えてはいけない。\n' > "$PGD/docs/aidev/README.md"
  ( cd "$PGD" && "$AIDEV_SH" convention promote README --to 'tgt.md#x' >/dev/null 2>&1 ); GS=$?
  ( cd "$PGD" && run_ps1 "$AIDEV_PS1" convention promote README --to 'tgt.md#x' >/dev/null 2>&1 ); GP=$?
  assert_eq "$GS" "$GP" "パリティ: frontmatter 無しを弾く exit code"
  assert_eq "$(wc -c < "$PGD/docs/aidev/README.md")" "40" "パリティ: どちらの実装でも本文が無傷"
  ( cd "$PGD" && "$AIDEV_SH" convention promote ../tgt --to 'tgt.md#x' >/dev/null 2>&1 ); IS=$?
  ( cd "$PGD" && run_ps1 "$AIDEV_PS1" convention promote ../tgt --to 'tgt.md#x' >/dev/null 2>&1 ); IP=$?
  assert_eq "$IS" "$IP" "パリティ: id のパス成分を潰す exit code"
  rm -rf "$PGD"

  # 着手日の抽出パリティ（sh は sed・ps1 は -match。母集団の数え方が食い違うと判定時期がずれる）
  PTS=$(mktemp -d); mkdir -p "$PTS/.aidev/works"
  ( cd "$PTS" && "$AIDEV_SH" convention new tsp --hypothesis h --baseline "b" --verify-after 1 >/dev/null )
  TD=$(date -u +%Y%m%d); TT=$(date -u +%Y-%m-%d)
  mkdir -p "$PTS/.aidev/works/$TD-w"
  printf 'schema: 4\nslug: w\ncurrent: deliver\napproved: [deliver]\n' > "$PTS/.aidev/works/$TD-w/state.yml"
  printf 'events:\n  - { ts: %sT01:00:00Z, phase: coding, event: start, metrics: { defects: 3 } }\n' \
    "$TT" > "$PTS/.aidev/works/$TD-w/metrics.yml"
  TS_SH=$( ( cd "$PTS" && "$AIDEV_SH" convention status --format tsv ) 2>&1 )
  TS_PS=$( ( cd "$PTS" && run_ps1 "$AIDEV_PS1" convention status --format tsv ) 2>&1 | tr -d '\r' )
  assert_eq "$TS_SH" "$TS_PS" "パリティ: metrics キーを含む行からの着手日抽出"
  rm -rf "$PTS"
  # 索引検査のパリティ（片方だけ検査が緩いと、その OS では読まれない条項が野放しになる）
  PIX=$(mktemp -d); mkdir -p "$PIX/.aidev/works" "$PIX/docs"
  printf '# AGENTS\n\n<!-- aidev:conventions -->\n<!-- /aidev:conventions -->\n' > "$PIX/AGENTS.md"
  ( cd "$PIX" && "$AIDEV_SH" convention new ix --hypothesis h --baseline "b" --verify-after 1 >/dev/null )
  IX_SH=$( ( cd "$PIX" && "$AIDEV_SH" doctor ) 2>&1 | sed -n '/^convention:/,$p' )
  IX_PS=$( ( cd "$PIX" && run_ps1 "$AIDEV_PS1" doctor ) 2>&1 | tr -d '\r' | sed -n '/^convention:/,$p' )
  assert_eq "$IX_SH" "$IX_PS" "パリティ: doctor の索引検査"
  IS_SH=$( ( cd "$PIX" && "$AIDEV_SH" convention status --format tsv ) 2>&1 )
  IS_PS=$( ( cd "$PIX" && run_ps1 "$AIDEV_PS1" convention status --format tsv ) 2>&1 | tr -d '\r' )
  assert_eq "$IS_SH" "$IS_PS" "パリティ: convention status の index 列"
  rm -rf "$PIX"

  # deliver 到達通知のパリティ（母集団の数え方が食い違うと判定タイミングがずれる）
  PRD=$(mktemp -d); mkdir -p "$PRD/.aidev/works"
  ( cd "$PRD" && "$AIDEV_SH" convention new rc --hypothesis h --baseline "b" --verify-after 1 >/dev/null )
  ( cd "$PRD" && "$AIDEV_SH" new pa >/dev/null )
  PAW=$(ls "$PRD/.aidev/works")
  for p in requirement spec plan coding test review; do
    ( cd "$PRD" && "$AIDEV_SH" event "$p" start >/dev/null; cd "$PRD" && "$AIDEV_SH" approve "$p" >/dev/null )
  done
  : > "$PRD/.aidev/works/$PAW/review.md"
  ( cd "$PRD" && "$AIDEV_SH" event deliver start >/dev/null )
  RA_SH=$( ( cd "$PRD" && "$AIDEV_SH" approve deliver files_changed=1 ) 2>&1 )
  RA_PS=$( ( cd "$PRD" && run_ps1 "$AIDEV_PS1" approve deliver files_changed=1 ) 2>&1 | tr -d '\r' )
  assert_eq "$RA_SH" "$RA_PS" "パリティ: approve deliver の到達通知（冪等なので2回目も同じ出力）"
  rm -rf "$PRD"
  # harnessRev のパリティ（刻印が片方だけ欠けると、その OS の work が母集団から漏れる）
  PHV=$(mktemp -d); mkdir -p "$PHV/.aidev/works"
  ( cd "$PHV" && "$AIDEV_SH" new a >/dev/null ) && ( cd "$PHV" && run_ps1 "$AIDEV_PS1" new b >/dev/null )
  HA=$(sed -n 's/^harnessRev: //p' "$PHV/.aidev/works/"*-a/state.yml)
  HB=$(tr -d '\r' < "$PHV/.aidev/works/"*-b/state.yml | sed -n 's/^harnessRev: //p')
  assert_eq "$HA" "$HB" "パリティ: harnessRev の刻印が一致"
  rm -rf "$PHV"
  # profile 系のパリティ（同じフィクスチャに対して同じ出力になること）
  for pargs in "verify $L_SLUG" "verify $F_SLUG" "verify 20260101-oldwork"; do
    # shellcheck disable=SC2086
    P_SH=$( ( cd "$LREPO" && "$AIDEV_SH" $pargs ) 2>&1 )
    # shellcheck disable=SC2086
    P_PS=$( ( cd "$LREPO" && run_ps1 "$AIDEV_PS1" $pargs ) 2>&1 | tr -d '\r' )
    assert_eq "$P_SH" "$P_PS" "パリティ: $pargs（profile 判定）"
  done
  PE_SH=$( ( cd "$LREPO" && "$AIDEV_SH" escalate "$F_SLUG" ) 2>&1 )
  PE_PS=$( ( cd "$LREPO" && run_ps1 "$AIDEV_PS1" escalate "$F_SLUG" ) 2>&1 | tr -d '\r' )
  assert_eq "$PE_SH" "$PE_PS" "パリティ: escalate（full からの拒否メッセージ）"

  for args in "status --format tsv" "metrics --all --format tsv" "metrics 20260101-alpha --phases --format tsv"; do
    # shellcheck disable=SC2086
    O_SH=$( ( cd "$TMP" && "$AIDEV_SH" $args ) )
    # shellcheck disable=SC2086
    O_PS=$( ( cd "$TMP" && run_ps1 "$AIDEV_PS1" $args ) | tr -d '\r' )
    assert_eq "$O_SH" "$O_PS" "パリティ: $args"
  done

  # subtask 層のパリティ（$SUB フィクスチャ。doctor のネスト横断・status・metrics を sh⇔ps1 突合）
  for args in "doctor" "status --format tsv" "status --subtasks --format tsv" "metrics --all --format tsv"; do
    # shellcheck disable=SC2086
    O_SH=$( ( cd "$SUB" && "$AIDEV_SH" $args ) )
    # shellcheck disable=SC2086
    O_PS=$( ( cd "$SUB" && run_ps1 "$AIDEV_PS1" $args ) | tr -d '\r' )
    assert_eq "$O_SH" "$O_PS" "パリティ(subtask): $args"
  done

  # ps1 の new --parent を実機で検証（sh で作った親に ps1 が subtask を足し、親 state を正しく更新）
  ( cd "$SUB" && run_ps1 "$AIDEV_PS1" new 03-ps --parent "$SP" >/dev/null 2>&1 )
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
    WL_PS=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree list --format tsv ) | tr -d '\r' )
    assert_eq "$WL_SH" "$WL_PS" "パリティ: worktree list --format tsv"

    # (2) ps1 の add（既存work一致＝current 設定のみ）。current が full dated 名であること
    #     ＝ review 検出の must「PowerShell 単一要素配列アンラップ($mw[0]が先頭1文字)」の回帰ガード
    PW_OUT=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree add existing ) | tr -d '\r' )
    PW_CUR=$(cat "$TMP/prepo-wt/existing/.aidev/current" 2>/dev/null)
    assert_eq "$PW_CUR" "20260101-existing" "パリティ: ps1 add(既存work) current=full dated 名(\$mw アンラップ回帰)"
    assert_contains "$PW_OUT" "既存 work をリンク" "パリティ: ps1 add は既存をリンク(new 委譲せず)"

    # (3) ps1 の add（新規 slug＝add 内で new に委譲する経路）。ここは長らく未検証で、
    #     委譲先パスが `.aidev/bin/aidev.ps1`（誤）かつホストが `pwsh` 決め打ちのまま壊れていた。
    PN_OUT=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree add fresh ) 2>&1 | tr -d '\r' ); PN_RC=$?
    assert_eq "$PN_RC" "0" "パリティ: ps1 add(新規slug) exit 0"
    assert_contains "$PN_OUT" "新規 work を作成" "パリティ: ps1 add(新規slug) は new に委譲"
    PN_CUR=$(cat "$TMP/prepo-wt/fresh/.aidev/current" 2>/dev/null | tr -d '\r')
    assert_contains "$PN_CUR" "-fresh" "パリティ: ps1 add(新規slug) が worktree の current を書く"
    assert_eq "$([ -f "$TMP/prepo-wt/fresh/.aidev/works/$PN_CUR/state.yml" ] && echo yes || echo no)" "yes" \
      "パリティ: ps1 add(新規slug) が work を実際に作る（委譲失敗の空振り回帰）"

    # (4) ps1 の rm <path>: 自分の list が出したパス表記をそのまま渡せること
    #     （git は C:/... 、.NET の解決は C:\... なので素の比較だと Windows で必ず外れた）
    PB=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree list --format tsv ) | tr -d '\r' | awk -F'\t' '$2 ~ /fresh$/ {print $2}')
    ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree rm "$PB" --force --delete-branch >/dev/null 2>&1 )
    assert_eq "$?" "0" "パリティ: ps1 rm は list が出したパス表記をそのまま扱える"
    assert_eq "$([ -d "$TMP/prepo-wt/fresh" ] && echo yes || echo no)" "no" "パリティ: ps1 rm(path) で worktree 撤去済み"
  else
    skip "git 不在のため worktree パリティを省略"
  fi
else
  skip "PowerShell(pwsh/powershell) 不在のためパリティテストを省略"
fi

echo
printf 'RESULT: pass=%s fail=%s skip=%s\n' "$PASS" "$FAIL" "$SKIP"
# skip>0＝環境不足で未実行の検証（未検証の穴）。deliver/PR で「未検証 surface」として引き継ぐこと(#32)。
[ "$SKIP" -gt 0 ] && printf 'NOTE: %s 件の検証が環境不足で skip された（未検証の穴）。pwsh/git のある環境(CI)で再実行して埋めること。\n' "$SKIP" >&2
[ "$FAIL" -eq 0 ]
