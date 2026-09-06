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
#
# `AIDEV_PS_HOST` で処理系を**明示指定**できる（`pwsh` / `winps`）。これが無いと、
# pwsh 7 と Windows PowerShell 5.1 が両方入っている環境（GitHub Actions の windows-latest が
# まさにそれ）では常に pwsh が選ばれ、**ps1 の本来の対象である 5.1 が一度も走らない**。
# 自動判定に任せると「Windows で検証した」と言えないまま緑になる。
PS_HOST=""
if [ -n "${AIDEV_PS_HOST:-}" ]; then
  case "$AIDEV_PS_HOST" in
    pwsh)  command -v pwsh >/dev/null 2>&1 || { echo "AIDEV_PS_HOST=pwsh だが pwsh がありません" >&2; exit 1; } ;;
    winps) command -v powershell >/dev/null 2>&1 || { echo "AIDEV_PS_HOST=winps だが powershell がありません" >&2; exit 1; } ;;
    *) echo "AIDEV_PS_HOST は pwsh|winps（指定: $AIDEV_PS_HOST）" >&2; exit 1 ;;
  esac
  PS_HOST=$AIDEV_PS_HOST
elif command -v pwsh >/dev/null 2>&1; then PS_HOST=pwsh
elif command -v powershell >/dev/null 2>&1; then PS_HOST=winps
fi
[ -n "$PS_HOST" ] && printf 'ps1 host: %s\n' "$PS_HOST"
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
# 抽出そのものが外れると `$CUR_SCHEMA` が空になり、needle が "schema: " に退化して**何にでも当たる**。
# 二重管理を避けるための仕掛けが、黙って検査を無効化する仕掛けに変わるので、ここで止める
case "$CUR_SCHEMA" in
  ''|*[!0-9]*) printf 'CUR_SCHEMA を %s から抽出できません（テストが空振りします）\n' "$AIDEV_SH" >&2; exit 1 ;;
esac

PASS=0; FAIL=0; SKIP=0
ok()   { PASS=$((PASS+1)); printf '  ok: %s\n' "$1"; }
ng()   { FAIL=$((FAIL+1)); printf '  NG: %s\n' "$1" >&2; }
# 環境不足で検証を飛ばしたら skip() を使う。RESULT に skip 件数を出して「未検証の穴」を可視化する(#32)。
# **件数は飛ばしたアサート数**を渡す（`skip <n> "<理由>"`）。1回=1件で数えると、53 件を覆う
# パリティブロック1つが「skip 1」に見え、未検証の穴を1桁過小に申告することになる。
# 数が実態からずれると、この可視化そのものが嘘になる。
skip() { SKIP=$((SKIP+$1)); printf '  skip: %s（未実行 %s 件）\n' "$2" "$1"; }
# 宣言した skip 件数は**実測と突き合わせる**。直書きのままだとアサートを足したときに
# 申告が古くなり、「未検証の穴」の可視化そのものが静かに嘘になる。
# 使い方: ブロックの直前で block_begin、直後で block_end <宣言件数> "<名前>"
# 入れ子になる（パリティの中に worktree パリティがある）ので、控えは**スロット名ごと**に持つ。
# 単一の変数だと内側の block_begin が外側の控えを上書きし、外側の実測が壊れる
block_begin() { eval "_BP_$1=\$PASS; _BF_$1=\$FAIL; _BS_$1=\$SKIP"; }
block_end() { # スロット 宣言件数 名前
  eval "_bp=\$_BP_$1; _bf=\$_BF_$1; _bs=\$_BS_$1"
  # +1 は block_end 自身のアサート。これもブロックが飛べば走らないので、申告に含める
  _ran=$(( (PASS-_bp) + (FAIL-_bf) + (SKIP-_bs) + 1 ))
  assert_eq "$_ran" "$2" "skip 申告の件数が実測と一致する（$3）"
}
assert_contains() { # haystack needle desc
  case "$1" in *"$2"*) ok "$3" ;; *) ng "$3 (期待を含まず: [$2])"; printf '    出力:\n%s\n' "$1" >&2 ;; esac
}
assert_absent() { # haystack needle desc
  case "$1" in *"$2"*) ng "$3 (含んではいけない: [$2])" ;; *) ok "$3" ;; esac
}
assert_eq() { # got want desc
  if [ "$1" = "$2" ]; then ok "$3"; else ng "$3 (got=[$1] want=[$2])"; fi
}
assert_ne() { # got unwanted desc
  if [ "$1" != "$2" ]; then ok "$3"; else ng "$3 (同じであってはいけない: [$1])"; fi
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
approved: [requirements, research, design, tasks, coding, test, review, deliver]
mode: autonomous
humanGates: []
maxSendBacks: 3
dependsOn: []
EOF
cat > "$TMP/.aidev/works/20260101-alpha/metrics.yml" <<'EOF'
events:
  - { ts: 2026-01-01T00:00:00Z, phase: requirements, event: start }
  - { ts: 2026-01-01T00:10:00Z, phase: requirements, event: approved }
  - { ts: 2026-01-01T00:30:00Z, phase: design, event: sent_back }
  - { ts: 2026-01-01T01:00:00Z, phase: coding, event: start }
  - { ts: 2026-01-01T01:05:00Z, phase: coding, event: start }
  - { ts: 2026-01-01T02:00:00Z, phase: coding, event: approved }
  - { ts: 2026-01-01T03:00:00Z, phase: deliver, event: approved }
EOF
# review 承認済なので review.md が必要（verify schema>=2 の不変条件）
printf '# レビュー記録\n' > "$TMP/.aidev/works/20260101-alpha/review.md"

# beta: 進行中（design まで承認）。dependsOn: alpha(充足) + #99(advisory)。
mkdir -p "$TMP/.aidev/works/20260102-beta"
cat > "$TMP/.aidev/works/20260102-beta/state.yml" <<'EOF'
schema: 2
slug: beta
ticket: "#42"
current: design
approved: [requirements, research, design]
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
current: requirements
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
assert_contains "$ST_TSV" "work	20260102-beta	#42	interactive	design	tasks	no	#99(advisory)" "beta: next=tasks/done=no/deps=#99(advisory)（alpha は充足）"
assert_contains "$ST_TSV" "work	20260103-legacy	-	-	requirements	requirements	no	ok" "legacy: schema無しでも一覧化(next=requirements)"
assert_contains "$ST_TSV" "backlog	x.md	2	1	0" "backlog x.md: todo=2/needs=1/inflight=0（刻印付き work 無し）"
assert_absent  "$ST_TSV" "should-not-count" "archive/ は除外される"

ST_TBL=$(run_sh status)
assert_contains "$ST_TBL" "WORKS (3)" "table: WORKS 件数"
assert_contains "$ST_TBL" "BACKLOG (未着手 2 件)" "table: BACKLOG 未着手件数"

echo "== status 異常系 =="
run_sh status --format bogus >/dev/null 2>&1; assert_eq "$?" "1" "不正 --format は exit 1"

echo "== metrics =="
MT=$(run_sh metrics --all --format tsv)
# `lead_sec` は**暦の上の時間**（離席ぶんが乗る）、`work_sec` は工程の elapsed 合計。
# 並べて出さないと「実作業に近い時間」と読み分けられない（retro が実測: lead の 60% が待ち時間だった）
assert_contains "$MT" "20260101-alpha	2026-01-01T00:00:00Z	yes	10800	3900	1	1" "alpha: lead=10800 / work_sec=3900 / reworks=1 / sent_backs=1"
assert_contains "$MT" "20260103-legacy	-	no	-	0	0" "legacy: metrics空でも 0/-"
# ハーネス版で層別する材料（harnessRev / straddle）。無いと insights は state.yml を grep して手で JOIN していた
assert_contains "$MT" "20260101-alpha	2026-01-01T00:00:00Z	yes	10800	3900	1	1	-	-" "metrics --all: harnessRev/straddle 列（刻印なしは -/-）"
assert_contains "$(run_sh metrics --all)" "lead_sec  work_sec" "metrics --all: work_sec も表の見出しに出る"
assert_contains "$(run_sh metrics --all)" "harnessRev  straddle" "metrics --all: 表形式の見出しにも出る"

echo "== status --active / doctor --quiet（100 works で読める出力量にする） =="
ST_ACT=$(run_sh status --active --format tsv)
assert_absent "$ST_ACT" "work	20260101-alpha" "status --active: deliver 済みを隠す"
assert_contains "$ST_ACT" "work	20260102-beta" "status --active: 進行中は出す"
assert_contains "$(run_sh status --active)" "WORKS (2)" "status --active: 件数も隠した後の数"
# OK だけの work を1つ足す（alpha/beta は記録漏れ WARN 付きで OK、legacy は SKIP＝どれも「OK だけ」ではない）
run_sh new clean >/dev/null; CLEANW=$(cat "$TMP/.aidev/current")
printf '20260102-beta\n' > "$TMP/.aidev/current"
DQ=$(run_sh doctor --quiet 2>&1 || true)
assert_absent "$DQ" "- $CLEANW" "doctor --quiet: OK だけの work は行ごと出さない"
assert_contains "$(run_sh doctor 2>&1 || true)" "- $CLEANW" "doctor（既定）: OK だけの work も出す（--quiet でだけ省く）"
assert_contains "$DQ" "- 20260101-alpha" "doctor --quiet: WARN 付きの work は OK でも出す（直せる WARN を隠さない）"
assert_contains "$DQ" "20260103-legacy" "doctor --quiet: SKIP の work は出す"
assert_contains "$DQ" "summary: works=4" "doctor --quiet: 件数は全件のまま"
assert_contains "$DQ" "--quiet: OK は省略" "doctor --quiet: 省略していることを見出しで示す"
rm -rf "$TMP/.aidev/works/$CLEANW"
MTP=$(run_sh metrics 20260101-alpha --phases --format tsv)
# coding は 01:00 と 01:05 の 2 ラウンド。直近の対だけで測ると 3300 秒に見えるが、
# 実際にかかったのは 1 ラウンド目（01:00→01:05 の 300 秒。sent_back も approved も無いので
# 次の start で閉じる）＋ 2 ラウンド目（01:05→02:00 の 3300 秒）。差し戻しのあった工程が
# **最短に見える**のを塞ぐ（実走で review 654 秒が 216 秒と出た）
assert_contains "$MTP" "20260101-alpha	coding	2026-01-01T01:00:00Z	2026-01-01T02:00:00Z	3300	2" \
  "alpha --phases: start は初回・elapsed は合算・rounds でやり直し回数が見える"
assert_contains "$MTP" "20260101-alpha	requirements	2026-01-01T00:00:00Z	2026-01-01T00:10:00Z	600	1" "alpha --phases: requirements elapsed=600 / rounds=1"

echo "== 読み取り専用（status/metrics は state/metrics を書き換えない） =="
# `.aidev/current` も含める。status/metrics が「今どの work か」を書き換えるのは
# 読み取りコマンドの越権で、state.yml だけ見ていると気付けない
SUM1=$(cat "$TMP/.aidev/works"/*/state.yml "$TMP/.aidev/works"/*/metrics.yml "$TMP/.aidev/current" 2>/dev/null | cksum)
run_sh status >/dev/null; run_sh status --format tsv >/dev/null
run_sh metrics --all >/dev/null; run_sh metrics 20260101-alpha --phases >/dev/null
SUM2=$(cat "$TMP/.aidev/works"/*/state.yml "$TMP/.aidev/works"/*/metrics.yml "$TMP/.aidev/current" 2>/dev/null | cksum)
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
current: design
approved: [requirements]
YML
cat > "$TMP/.aidev/works/20260101-gap/metrics.yml" <<'YML'
events:
  - { ts: 2026-01-01T00:00:00Z, phase: requirements, event: approved }
  - { ts: 2026-01-01T01:00:00Z, phase: design, event: start }
  - { ts: 2026-01-01T02:00:00Z, phase: design, event: approved }
YML
V_GAP=$(run_sh verify 20260101-gap 2>&1); V_RC=$?
echo "$V_GAP" | grep -q "WARN requirements" && ok "verify: start 欠落を WARN で知らせる" || ng "verify: start 欠落の WARN が出ない"
echo "$V_GAP" | grep -q "WARN design" && ng "verify: 対の揃った工程に WARN が出ている" || ok "verify: 対の揃った工程には WARN を出さない"
assert_eq "$V_RC" "0" "verify: WARN は exit コードを変えない"
rm -rf "$TMP/.aidev/works/20260101-gap"

# WARN の並びは PHASES 順（ハッシュ列挙順に任せると awk と PowerShell で並びが変わり
# 「出力を一致させる」契約＝パリティが破れる）。
mkdir -p "$TMP/.aidev/works/20260101-order"
cat > "$TMP/.aidev/works/20260101-order/state.yml" <<'YML'
schema: 3
slug: order
current: coding
approved: [requirements, design, architecture, tasks]
YML
cat > "$TMP/.aidev/works/20260101-order/metrics.yml" <<'YML'
events:
  - { ts: 2026-01-01T00:00:00Z, phase: tasks, event: approved }
  - { ts: 2026-01-01T01:00:00Z, phase: design, event: approved }
  - { ts: 2026-01-01T02:00:00Z, phase: architecture, event: approved }
  - { ts: 2026-01-01T03:00:00Z, phase: requirements, event: approved }
YML
V_ORD=$(run_sh verify 20260101-order 2>&1 | grep -o 'WARN [a-z]*' | tr '\n' ' ')
assert_eq "$V_ORD" "WARN requirements WARN design WARN architecture WARN tasks " "verify: WARN は PHASES 順（記録順やハッシュ順ではない）"
if [ -n "$PS_HOST" ]; then
  block_begin warnorder
  P_ORD=$( ( cd "$TMP" && run_ps1 "$AIDEV_PS1" verify 20260101-order ) | tr -d '\r' | grep -o 'WARN [a-z]*' | tr '\n' ' ')
  assert_eq "$P_ORD" "$V_ORD" "パリティ: WARN の並びが sh⇔ps1 で一致"
  block_end warnorder "2" "warnorder"
else
  skip 2 "PowerShell(pwsh/powershell) 不在のため WARN 並びのパリティを省略"
fi
rm -rf "$TMP/.aidev/works/20260101-order"

# guard: start の記録が要るときだけ促す（自動記録はしない＝手戻り回数の二重計上を避ける）
mkdir -p "$TMP/.aidev/works/20260101-hint"
cat > "$TMP/.aidev/works/20260101-hint/state.yml" <<'YML'
schema: 3
slug: hint
current: requirements
approved: []
YML
: > "$TMP/.aidev/works/20260101-hint/requirements.md"
cat > "$TMP/.aidev/works/20260101-hint/metrics.yml" <<'YML'
events:
  - { ts: 2026-01-01T00:00:00Z, phase: requirements, event: start }
YML
PREV_CURRENT=$(cat "$TMP/.aidev/current")
echo "20260101-hint" > "$TMP/.aidev/current"
H1=$(run_sh guard design 2>&1)
echo "$H1" | grep -q "aidev event design start" && ok "guard: 未 start の工程では start を促す" || ng "guard: start の促しが出ない"
# **余分な引数を黙って捨てない**。捨てていた頃は `aidev guard design --slug X` が
# .aidev/current の別 work に対して緑を返していた（工程入口の硬ゲートが打ち間違いを通す形）。
# sh / ps1 の共有欠陥だったのでパリティテストでは捕まらなかった
assert_eq "$(run_sh guard design --slug bogus >/dev/null 2>&1; echo $?)" "1" \
  "guard: 余分なオプションを弾く（別 work に緑を返さない）"
assert_eq "$(run_sh guard design bogus >/dev/null 2>&1; echo $?)" "1" \
  "guard: 余分な位置引数も弾く"
H2=$(run_sh guard requirements 2>&1)
echo "$H2" | grep -q "aidev event requirements start" && ng "guard: start 済なのに促している" || ok "guard: start 済の工程では促さない"
# **plan モードへ入るよう、該当条件の工程でだけ名指しで促す**。散文に書いてあっても、
# 打つ側は工程に入る瞬間には思い出さない（event start の促しと同じ型）
echo "$H1" | grep -q "plan モードへ入ってから" \
  && ok "guard design: plan モードへ入るよう促す（full × interactive）" || ng "guard design: plan モードの促しが出ない"
# **全 11 工程を前提充足済みで回す**。個別に書いていた頃は
# (1) 前提が足りず exit 2 で終わる**空振り**が 3 本混ざり（`guard review` は `need_approved test` に
#     落ちて促しに一度も到達していなかった）、
# (2) `case` に test|walkthrough|deliver|retro を足しても architecture を消しても**緑のまま**だった
#     （実走が変異試験で実測）。**検査が中核を守っていなかった**。
# 前提を全部揃えてから 11 工程を一巡し、rc=0 であることも確かめる
PM_W=$TMP/.aidev/works/20260101-hint
printf 'schema: 3\nslug: hint\ncurrent: requirements\napproved: [requirements, design, architecture, tasks, coding, test, review, walkthrough, deliver]\n' > "$PM_W/state.yml"
: > "$PM_W/design.md"; : > "$PM_W/architecture.md"; : > "$PM_W/tasks.md"
printf -- '- [ ] T1: x\n' > "$PM_W/tasks.md"
# 期待値の正典は protocol-autonomous.md「plan モードとの関係」——入るのは design / architecture / tasks
for _pmc in requirements:no research:no design:yes architecture:yes tasks:yes coding:no \
            test:no review:no walkthrough:no deliver:no retro:no; do
  _pmp=${_pmc%%:*}; _pmw=${_pmc#*:}
  _pmo=$(run_sh guard "$_pmp" 2>&1); _pmr=$?
  assert_eq "$_pmr" "0" "guard $_pmp: 前提が揃っていて rc=0（空振り検査になっていない）"
  _pmg=$(printf '%s' "$_pmo" | grep -c 'plan モードへ入ってから') || _pmg=0
  if [ "$_pmw" = yes ]; then
    assert_ne "$_pmg" "0" "guard $_pmp: 促す（成果物が実装計画）"
  else
    assert_eq "$_pmg" "0" "guard $_pmp: 促さない（成果物が実装計画ではない）"
  fi
done
# **subtask の tasks は親が切り方を確定済み**——同じ工程名でも促してはいけない
printf 'schema: 3\nslug: hint\ncurrent: requirements\napproved: []\nparent: 20260101-order\n' \
  > "$PM_W/state.yml"
assert_eq "$(run_sh guard tasks 2>&1 | grep -c 'plan モードへ入ってから')" "0" \
  "guard tasks: subtask では促さない（切り方は親の tasks が確定済み）"
printf 'schema: 3\nslug: hint\ncurrent: requirements\napproved: []\n' > "$PM_W/state.yml"
rm -f "$PM_W/design.md" "$PM_W/architecture.md" "$PM_W/tasks.md" "$PM_W/tasks.md"
# **「入れ」と命じる**。「方針を先に固める」のような役割だけの言い方だと、丁寧に計画するだけで
# モードは切り替わらない（EnterPlanMode は主エージェントのツールなので、明示すれば実際に切り替わる）
echo "$H1" | grep -q "抜けた先は承認時に選んだモードで、元のモードには戻らない" \
  && ok "guard design: 戻り先が選べないことも言う（工程の間だけ入れて戻す、は作れない）" \
  || ng "guard design: 抜けた先の説明が無い"
# 条件は散文と同じ full × interactive だけ——light は往復を減らす趣旨に反し、autonomous には承認者がいない
printf 'schema: 3\nslug: hint\ncurrent: requirements\napproved: []\nprofile: light\n' \
  > "$TMP/.aidev/works/20260101-hint/state.yml"
assert_eq "$(run_sh guard design 2>&1 | grep -c 'plan モードへ入ってから')" "0" \
  "guard design: light では促さない（往復を減らす趣旨に反する）"
printf 'schema: 3\nslug: hint\ncurrent: requirements\napproved: []\nmode: autonomous\n' \
  > "$TMP/.aidev/works/20260101-hint/state.yml"
assert_eq "$(run_sh guard design 2>&1 | grep -c 'plan モードへ入ってから')" "0" \
  "guard design: autonomous では促さない（承認者がいない）"
# **見るのは mode ではなく「その工程に承認者がいるか」**。`humanGates` の部分自律には承認者がいる。
# `mode != autonomous` で判定していた頃は、他 PJ の retro が実績として報告している構成で
# 承認者がいるのに促しを止めていた（実走で実測）
printf 'schema: 3\nslug: hint\ncurrent: requirements\napproved: []\nmode: autonomous\nhumanGates: [design]\n' \
  > "$TMP/.aidev/works/20260101-hint/state.yml"
assert_eq "$(run_sh guard design 2>&1 | grep -c 'plan モードへ入ってから')" "1" \
  "guard design: humanGates に挙がっていれば autonomous でも促す（承認者がいる）"
assert_eq "$(run_sh guard architecture 2>&1 | grep -c 'plan モードへ入ってから')" "0" \
  "guard architecture: humanGates に無い工程は promote しない（工程ごとに見る）"
# **見るのは「この工程に承認者がいるか」で、mode そのものではない**。plan モードを抜けるのが
# 人間の承認だから。`autonomous` を一律で外していた頃は、`humanGates: [design]` の部分自律——
# 他 PJ の retro が実績として報告している構成——で**承認者がいるのに促しを止めていた**（実走で実測）
printf 'schema: 3\nslug: hint\ncurrent: requirements\napproved: []\nmode: autonomous\nhumanGates: [design]\n' \
  > "$TMP/.aidev/works/20260101-hint/state.yml"
assert_eq "$(run_sh guard design 2>&1 | grep -c 'plan モードへ入ってから')" "1" \
  "guard design: autonomous でも humanGates にあれば促す（部分自律）"
assert_eq "$(run_sh guard architecture 2>&1 | grep -c 'plan モードへ入ってから')" "0" \
  "guard architecture: humanGates に無い工程は autonomous のまま促さない"
# light は承認者の有無と無関係に外す（往復を減らす趣旨に反する）
printf 'schema: 3\nslug: hint\ncurrent: requirements\napproved: []\nmode: autonomous\nhumanGates: [design]\nprofile: light\n' \
  > "$TMP/.aidev/works/20260101-hint/state.yml"
assert_eq "$(run_sh guard design 2>&1 | grep -c 'plan モードへ入ってから')" "0" \
  "guard design: humanGates があっても light なら促さない"
rm -rf "$TMP/.aidev/works/20260101-hint"
printf '%s\n' "$PREV_CURRENT" > "$TMP/.aidev/current"
# beta は tasks 前提(design.md)が無いので guard tasks は exit 2
run_sh guard tasks >/dev/null 2>&1; assert_eq "$?" "2" "guard tasks(前提成果物なし) exit 2"
G_OUT=$(run_sh guard design 2>&1); echo "$G_OUT" | grep -q "advisory" && ok "guard: #99 を advisory(warn) 表示" || ng "guard advisory 表示"

echo "== worktree =="
if command -v git >/dev/null 2>&1; then
  block_begin worktree
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
  # main tree も判定キー（.aidev/current の有無）を満たしうるので、種別を列に出す。
  # 出さないと「並行 worktree の一覧」として 1 件多く読める（rm は main を拒否するのに list には出る）
  assert_contains "$L_TSV" "	worktree" "list: 並行 worktree は kind=worktree"
  L_TBL=$(run_repo worktree list)
  assert_contains "$L_TBL" "WORKTREES" "list: table ヘッダ"
  assert_contains "$L_TBL" "kind" "list: table にも kind 列"

  # backlog 出自の刻印を worktree 経路でも通す（落とすと verify の消し込み強制が静かに効かない）
  mkdir -p "$REPO/.aidev/backlog"
  printf -- '---\nkind: topic\n---\n\n- [ ] やること\n' > "$REPO/.aidev/backlog/wb.md"
  ( cd "$REPO" && git add -A >/dev/null 2>&1 && git -c user.email=t@e -c user.name=t commit -q -m "backlog" >/dev/null 2>&1 )
  run_repo worktree add wbtest --mode autonomous --backlog wb.md --light >/dev/null 2>&1
  WBW=$(ls "$TMP/repo-wt/wbtest/.aidev/works" 2>/dev/null | head -n1)
  assert_contains "$(cat "$TMP/repo-wt/wbtest/.aidev/works/$WBW/state.yml" 2>/dev/null)" "backlog: wb.md" \
    "worktree add: --backlog を内部の new に渡す（消し込み強制が並行経路でも効く）"
  assert_contains "$(cat "$TMP/repo-wt/wbtest/.aidev/works/$WBW/state.yml" 2>/dev/null)" "profile: light" \
    "worktree add: --light も内部の new に渡す"

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
  # `( cd … && git … )` だと cd 失敗でも 1 になり、何を確かめたのか曖昧になる
  git -C "$REPO" show-ref --verify --quiet refs/heads/feature/probe; assert_eq "$?" "1" "rm: ブランチも削除済み"

  # add が **worktree を作った後**に失敗したら撤去する。しないと失敗したのに worktree と
  # ブランチだけが残り、次の add が「既にある」で弾かれる（skills を持ち込んでいない
  # リポジトリで CLI 実在検査に落ちる経路で確かめる）
  RBR=$(mktemp -d)
  ( cd "$RBR" && git init -q . && mkdir -p .aidev/works && printf 'x\n' > f.txt && git add -A \
    && git -c user.email=t@t -c user.name=t commit -qm init ) >/dev/null 2>&1
  RB_OUT=$( ( cd "$RBR" && "$AIDEV_SH" worktree add rbdemo ) 2>&1 ); RB_RC=$?
  assert_eq "$RB_RC" "1" "worktree add: CLI 不在なら失敗する"
  assert_contains "$RB_OUT" "撤去した" "worktree add: 失敗したら撤去した旨を伝える"
  assert_eq "$(git -C "$RBR" worktree list | wc -l | tr -d ' ')" "1" "worktree add: 失敗時に worktree を残さない"
  git -C "$RBR" show-ref --verify --quiet refs/heads/feature/rbdemo
  assert_eq "$?" "1" "worktree add: 失敗時に自分で作ったブランチを残さない"
  assert_eq "$([ -d "$RBR-wt" ] && echo yes || echo no)" "no" "worktree add: 失敗時に空のコンテナを残さない"
  rm -rf "$RBR" "$RBR-wt"
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
  block_end worktree "37" "worktree"
else
  skip 37 "git 不在のため worktree テストを省略"
fi

echo "== subtask 層（new --parent / guard 継承 / 兄弟 dependsOn / doctor 横断） =="
# 既存フィクスチャ(status/metrics の件数アサート)を汚さないよう独立 root を使う。
SUB="$TMP/sub"
# .aidev/works で find_root が $SUB に止まる。CLI は $AIDEV_SH を直接叩き new --parent は self-invoke しないため
# subtask フィクスチャに CLI コピーは不要（worktree add のみ self-invoke する）。
mkdir -p "$SUB/.aidev/works"
run_sub() { ( cd "$SUB" && "$AIDEV_SH" "$@" ); }

# 親 work を作り、上流成果物を置いて tasks まで承認
run_sub new feat >/dev/null
SP=$(cat "$SUB/.aidev/current")
for f in requirements design architecture tasks; do : > "$SUB/.aidev/works/$SP/$f.md"; done
for ph in requirements design architecture tasks; do run_sub approve "$ph" >/dev/null; done

# subtask 01-be 作成
SO=$(run_sub new 01-be --parent "$SP")
assert_contains "$SO" "created subtask" "new --parent: subtask 作成"
assert_eq "$(cat "$SUB/.aidev/current")" "$SP/01-be" "new --parent: current が subtask パス"
SPST="$SUB/.aidev/works/$SP/state.yml"
assert_contains "$(cat "$SPST")" "subtasks: [01-be]" "親 subtasks に追記"
assert_contains "$(cat "$SPST")" "activeSubtask: 01-be" "親 activeSubtask 設定"
SCST="$SUB/.aidev/works/$SP/01-be/state.yml"
assert_contains "$(cat "$SCST")" "parent: $SP" "子 state.yml に parent 逆参照"
assert_contains "$(cat "$SCST")" "current: tasks" "子 current=tasks"
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

# guard: subtask tasks は親の design.md を継承して充足(0)
echo "$SP/01-be" > "$SUB/.aidev/current"
run_sub guard tasks >/dev/null 2>&1; assert_eq "$?" "0" "guard tasks: 親 design.md 継承で充足"
# guard: subtask coding は親 tasks.md を継承「しない」（subtask 固有）。子に tasks.md が無いので未充足(2)
run_sub guard coding >/dev/null 2>&1; assert_eq "$?" "2" "guard coding: 親 tasks.md を継承せず未充足(2)"
# 子に tasks.md を置けば充足(0)
: > "$SUB/.aidev/works/$SP/01-be/tasks.md"; : > "$SUB/.aidev/works/$SP/01-be/tasks.md"
run_sub guard coding >/dev/null 2>&1; assert_eq "$?" "0" "guard coding: 子の tasks.md で充足(0)"
# B: 親専用工程は subtask で実行不可（exit 2）。subtask の工程は tasks/coding/test/review のみ
for ph in design architecture deliver walkthrough requirements; do
  run_sub guard "$ph" >/dev/null 2>&1; assert_eq "$?" "2" "B: subtask の guard $ph は親専用で拒否(2)"
done
# B: subtask 固有工程(review)は親専用ブロックに掛からない（design.md 継承で充足 0）
# review の前提は「test 通過」（aidev-60-review「前提」）。順に打つのが実運用の形
run_sub guard review >/dev/null 2>&1; assert_eq "$?" "2" "B: subtask の guard review は test 未承認なら未充足(2)"
run_sub approve test >/dev/null 2>&1
run_sub guard review >/dev/null 2>&1; assert_eq "$?" "0" "B: subtask の guard review は許可(0)"

# 兄弟 dependsOn: 02-fe は 01-be 未review で未充足(3)、review 後に充足(0)
echo "$SP/02-fe" > "$SUB/.aidev/current"
run_sub guard tasks >/dev/null 2>&1; assert_eq "$?" "3" "guard: 兄弟 01-be 未review で dependsOn 未充足(3)"
echo "$SP/01-be" > "$SUB/.aidev/current"
for ph in tasks coding test review; do run_sub approve "$ph" >/dev/null; done
: > "$SUB/.aidev/works/$SP/01-be/review.md"
# D: 01-be の review 承認でカーソルが次の未完 subtask(02-fe)へ自動前進する
assert_contains "$(cat "$SUB/.aidev/works/$SP/state.yml")" "activeSubtask: 02-fe" "D: 01-be review 承認で親 activeSubtask が 02-fe へ前進"
assert_eq "$(cat "$SUB/.aidev/current")" "$SP/02-fe" "D: カーソル(.aidev/current)が 02-fe へ自動前進"
run_sub guard tasks >/dev/null 2>&1; assert_eq "$?" "0" "guard: 兄弟 01-be review 済で dependsOn 充足(0)"

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
for ph in tasks coding test review; do run_sub approve "$ph" >/dev/null; done
: > "$SUB/.aidev/works/$SP/02-fe/review.md"
assert_contains "$(cat "$SUB/.aidev/works/$SP/state.yml")" "activeSubtask: done" "D: 全 subtask 完了で activeSubtask=done"
assert_eq "$(cat "$SUB/.aidev/current")" "$SP" "D: 全完了でカーソルが親 work へ戻る"

# --- status subtask ロールアップ表示（案C）---
TAB=$(printf '\t')
run_sub new feat2 >/dev/null
SP2=$(cat "$SUB/.aidev/current")
for f in requirements design tasks; do : > "$SUB/.aidev/works/$SP2/$f.md"; done
for ph in requirements design tasks; do run_sub approve "$ph" >/dev/null; done
run_sub new 01-a --parent "$SP2" >/dev/null
run_sub new 02-b --parent "$SP2" >/dev/null
# 01-a を review まで承認（N=1 / M=2。D が current を 02-b へ動かす）
echo "$SP2/01-a" > "$SUB/.aidev/current"
for ph in tasks coding test review; do run_sub approve "$ph" >/dev/null; done
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
assert_contains "$RTSV" "subtask${TAB}$SP2/02-b${TAB}tasks${TAB}no"     "rollup: tsv subtask 行(02-b tasks/no)"
WNF=$(printf '%s\n' "$RTSV" | awk -F'\t' -v w="$SP2" '$1=="work" && $2==w {print NF}')
assert_eq "$WNF" "8" "rollup: tsv work 行は8フィールド維持(後方互換)"
# 回帰: subtask 無し work は next に sub を出さない
run_sub new solo >/dev/null; SSO=$(cat "$SUB/.aidev/current")
: > "$SUB/.aidev/works/$SSO/requirements.md"; run_sub approve requirements >/dev/null
SOLOLINE=$(run_sub status --subtasks | grep "$SSO")
# grep が外れて空になっても assert_absent は通る。まず行が取れたことを確かめる
assert_contains "$SOLOLINE" "$SSO" "rollup: solo work の行が取れている（この後の assert_absent の前提）"
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

# deliver まで通す（review.md は schema>=2、工程成果物は schema>=5 の不変条件）
for f in requirements design tasks tasks review test-result; do : > "$BLR/.aidev/works/$BLW/$f.md"; done
for p in requirements design tasks coding test review deliver; do run_bl approve "$p" >/dev/null; done

BLV=$(run_bl verify 2>&1); BLC=$?
assert_eq "$BLC" "4" "verify: 消し込み前は FAIL（deliver 済 + backlog 出自）"
assert_contains "$BLV" "消し込みが無い" "verify: 消し込み漏れを名指しする"

# ファイルのどこかに slug があるだけでは通さない: `- [ ] 次 (needs: <slug>)` の未着手行や、
# slug の無い [x] 行では「消し込み無しに着地」できてしまっていた
printf '# demo\n\n- [ ] 次の課題 (needs: %s)\n- [x] 別件\n    → 20200101-other で完了\n' "$BLW" > "$BLR/.aidev/backlog/demo.md"
run_bl verify >/dev/null 2>&1
assert_eq "$?" "4" "verify: 未着手行の (needs: <slug>) では消し込みと認めない（[x] 行に限定）"
# 消し込む（規約どおり works slug を根拠として**継続行**に併記する）
printf '# demo\n\n- [x] やること\n    → %s で完了\n' "$BLW" > "$BLR/.aidev/backlog/demo.md"
run_bl verify >/dev/null 2>&1
assert_eq "$?" "0" "verify: 消し込み後は PASS（[x] 行の継続行の slug を認める）"
# 消化済み（todo=0）の backlog からは着手できない（status が todo=0/inflight=1 の自己矛盾を出していた）
run_bl new again --backlog demo.md >/dev/null 2>&1
assert_eq "$?" "1" "new --backlog: todo=0 の backlog からは着手しない"
assert_eq "$(cat "$BLR/.aidev/current")" "$BLW" "new --backlog: 弾いたら current を動かさない"
# compact: [x] 行（と継続行）を archive/<name>-done.md へ。verify はそこも見るので過去 work の検査は壊れない
printf '# demo\n\n- [x] やること\n    → %s で完了\n- [ ] まだ\n' "$BLW" > "$BLR/.aidev/backlog/demo.md"
CP=$(run_bl backlog compact demo.md)
assert_contains "$CP" "compacted: demo.md -> archive/demo-done.md (1 件)" "backlog compact: 件数を報告する"
assert_absent "$(cat "$BLR/.aidev/backlog/demo.md")" "[x]" "backlog compact: active から [x] 行が消える"
assert_contains "$(cat "$BLR/.aidev/backlog/demo.md")" "- [ ] まだ" "backlog compact: [ ] 行は残る"
assert_contains "$(cat "$BLR/.aidev/backlog/archive/demo-done.md")" "→ $BLW で完了" "backlog compact: 継続行ごと done ファイルへ移す"
run_bl verify >/dev/null 2>&1
assert_eq "$?" "0" "verify: compact 後も archive/<name>-done.md の消し込みを認める"
assert_contains "$(run_bl backlog compact demo.md)" "skip demo.md: 消化済み項目がありません" "backlog compact: 二度目は何もしない"

# archive へ退避しても追える（全項目 [x] のファイルは archive/ へ移る運用）
mkdir -p "$BLR/.aidev/backlog/archive"
mv "$BLR/.aidev/backlog/demo.md" "$BLR/.aidev/backlog/archive/demo.md"
run_bl verify >/dev/null 2>&1
assert_eq "$?" "0" "verify: archive/ へ退避後も消し込みを追える"

# 出自を持たない work は従来どおり（後方互換）
run_bl new plain --mode autonomous >/dev/null
PLW=$(cat "$BLR/.aidev/current")
assert_absent "$(cat "$BLR/.aidev/works/$PLW/state.yml")" "backlog:" "new: --backlog 無しでは backlog 行を書かない"
for f in requirements design tasks tasks review test-result; do : > "$BLR/.aidev/works/$PLW/$f.md"; done
for p in requirements design tasks coding test review deliver; do run_bl approve "$p" >/dev/null; done
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
for p in requirements design tasks coding test review deliver; do run_if approve "$p" >/dev/null; done

IF_TSV=$(run_if status --format tsv)
assert_contains "$IF_TSV" "backlog	q.md	2	0	1" "status: inflight=1（未 deliver の刻印付きだけ数える）"
# needle は**列見出しの並び**で見る。単語 "inflight" だけだと WORKS 表の work 名
# （20260901-inflight-a）に当たり、BACKLOG 表の列が消えても通ってしまう
assert_contains "$(run_if status | sed -n '/^BACKLOG/,$p')" "inflight" "status: 表形式に inflight 列が出る"

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
# warn の**総数**は、別々の WARN が入れ替わっても同じなら通ってしまう（個別 WARN は上で検査済み）。
# ファイル数と退避数だけを見る
assert_contains "$DT" "backlog-summary: files=6 archived=1" "doctor: backlog サマリの件数"

run_dt doctor >/dev/null 2>&1
assert_eq "$?" "0" "doctor: backlog の WARN は exit code を変えない（硬ゲートは verify 側）"

if [ -n "$PS_HOST" ]; then
  block_begin doctorbl
  O_PS=$( ( cd "$DTR" && run_ps1 "$AIDEV_PS1" doctor ) | tr -d '\r' )
  assert_eq "$DT" "$O_PS" "パリティ: doctor(backlog 検査)"
  block_end doctorbl "2" "doctorbl"
else
  skip 2 "PowerShell(pwsh/powershell) 不在のため doctor(backlog) のパリティを省略"
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
  block_begin usebl
  # 比較の前に**退避対象を作り直す**。ここまでで backlog は全部退避済みなので、そのまま比べると
  # 両実装とも `archived=0 skipped=0` の no-op 同士になり、kind 判定も skipped の報告も検査されない
  printf -- '---\nkind: topic\n---\n\n- [x] done\n' > "$CLR/.aidev/backlog/pa-topic.md"
  printf -- '---\nkind: standing\n---\n\n- [x] done\n' > "$CLR/.aidev/backlog/pa-standing.md"
  printf -- '---\nkind: split\n---\n\n- [ ] todo\n' > "$CLR/.aidev/backlog/pa-split.md"
  PA_SH=$( ( cd "$CLR" && "$AIDEV_SH" backlog archive ) 2>&1 )
  assert_contains "$PA_SH" "archived=1" "backlog archive: 全消化した topic を退避する（no-op でないことの確認）"
  # ps1 側にも同じ状態を作って比べる（sh が退避した後だと、また no-op 同士の比較になる）
  printf -- '---\nkind: topic\n---\n\n- [x] done\n' > "$CLR/.aidev/backlog/pa-topic.md"
  rm -f "$CLR/.aidev/backlog/archive/pa-topic.md"
  PA_PS=$( ( cd "$CLR" && run_ps1 "$AIDEV_PS1" backlog archive ) 2>&1 ); PA_PS=$(printf '%s' "$PA_PS" | tr -d '\r')
  assert_eq "$PA_SH" "$PA_PS" "パリティ: backlog archive（kind 判定と skipped の報告）"
  for args in "use" "backlog archive"; do
    # shellcheck disable=SC2086
    O_SH=$( ( cd "$CLR" && "$AIDEV_SH" $args ) )
    # shellcheck disable=SC2086
    O_PS=$( ( cd "$CLR" && run_ps1 "$AIDEV_PS1" $args ) | tr -d '\r' )
    assert_eq "$O_SH" "$O_PS" "パリティ: $args"
  done
  block_end usebl "5" "usebl"
else
  skip 5 "PowerShell(pwsh/powershell) 不在のため use / backlog のパリティを省略"
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
assert_contains "$L_NEW" "requirements 1ゲート" "new --light: 上流1ゲートの注意を出す"
L_SLUG=$(cat "$LREPO/.aidev/current")
assert_contains "$(cat "$LREPO/.aidev/works/$L_SLUG/state.yml")" "profile: light" "new --light: state.yml に profile: light"

F_NEW=$(run_lsh new normal)
F_SLUG=$(cat "$LREPO/.aidev/current")
assert_contains "$F_NEW" "profile full" "new(既定): profile full"
assert_absent  "$F_NEW" "requirements 1ゲート" "new(既定): light の注意は出さない"

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
LV2=$(run_lsh verify "$L_SLUG" 2>&1)
assert_contains "$LV2" "verify: $L_SLUG" "verify が実際に走っている（この後の assert_absent の前提）"
assert_absent "$LV2" "変更 9 ファイル" "config.yml の lightMaxFiles で上限を緩められる"
rm -f "$LREPO/.aidev/config.yml"

FV=$(run_lsh verify "$F_SLUG" 2>&1)
assert_contains "$FV" "verify: $F_SLUG" "verify が実際に走っている（この後の assert_absent の前提）"
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
approved: [requirements, design, tasks]
mode: interactive
humanGates: []
maxSendBacks: 3
dependsOn: []
EOF
printf 'events:\n' > "$LREPO/.aidev/works/20260101-oldwork/metrics.yml"
OV=$(run_lsh verify 20260101-oldwork 2>&1)
# 存在しない slug を渡すと verify は die して stdout が空になり、下の2件が**両方とも**
# 「work が無くても緑」になる。まず work が見えていることを確かめる
assert_contains "$OV" "verify: 20260101-oldwork" "verify が実際に走っている（この後の2件の前提）"
assert_absent "$OV" "profile=light" "profile 未記載の work は full 扱い（後方互換）"
ESC_OUT=$(run_lsh escalate 20260101-oldwork 2>&1); assert_eq "$?" "1" "profile 未記載の work は escalate 不可（full 扱い）"
assert_contains "$ESC_OUT" "full" "escalate の拒否理由が full 扱いであること（work 不在の die と区別する）"

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
# 「依存しないと宣言したファイルに harness が書き戻す」構造になっていた。生成物は .aidev/conventions/ へ移し、
# **効果が確認できたら PJ ドキュメントへ移送して本文を1箇所に保つ**（protocol.md「12.」）。
CVR=$(mktemp -d); mkdir -p "$CVR/.aidev/works" "$CVR/docs"
run_cv() { ( cd "$CVR" && "$AIDEV_SH" "$@" ); }

# --- 入口ゲート: 仮説の無い条項は作らせない（検証不能な改善を積まない） ---
run_cv convention new naming >/dev/null 2>&1
assert_eq "$?" "1" "convention new: --hypothesis は必須（検証できない条項を弾く）"
run_cv convention new naming --hypothesis "x" >/dev/null 2>&1
assert_eq "$?" "1" "convention new: --baseline は必須（起票時にしか「前」を作れない）"
assert_eq "$([ -e "$CVR/.aidev/conventions/naming.md" ] && echo yes || echo no)" "no" \
  "convention new: 入口ゲートで弾いたらファイルを作らない"
run_cv convention new naming --hypothesis "x" --baseline "b" --verify-after abc >/dev/null 2>&1
assert_eq "$?" "1" "convention new: --verify-after は整数"

CV_NEW=$(run_cv convention new naming-boolean --hypothesis "命名の must/should 指摘が減る" --baseline "b" \
  --source ".aidev/insights/2026-08-28-insights.md" --verify-after 2 2>&1)
assert_contains "$CV_NEW" "status pending" "convention new: pending で起こす"
# 索引ファイルが決まっていない PJ に「AGENTS.md に足せ」と言うと存在しないファイルを名指しする。
# 決まっていないことは決まっていないと言い、どこで決めるか（conventionsIndex）を示す
assert_contains "$CV_NEW" "の索引ブロックに1行足すこと" "convention new: 索引への追記を促す（自動読込されないため）"
assert_contains "$CV_NEW" "conventionsIndex" "convention new: 索引ファイル未確定なら決め方を示す（無い名前を断言しない）"
CVF="$CVR/.aidev/conventions/naming-boolean.md"
assert_eq "$([ -f "$CVF" ] && echo yes || echo no)" "yes" "convention new: 既定の conventionsDir は .aidev/conventions"
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
  # 着手は条項の introduced（いま）より後に固定する（23:59:59Z）。deliver も刻む（--members が出す）
  printf 'events:\n  - { ts: %sT23:59:59Z, phase: requirements, event: start }\n  - { ts: %sT23:59:59Z, phase: deliver, event: approved }\n' \
    "$(date -u +%Y-%m-%d)" "$(date -u +%Y-%m-%d)" > "$CVR/.aidev/works/$TODAY-$w/metrics.yml"
done
# 同じ日でも条項より**前**に着手した work は母集団に入れない。日付粒度で比べていた間は混入していた——
# 条項は「その日回っていた work の retro」から起きるのが典型なので、最初の母集団はほぼ確実に汚染される
mkdir -p "$CVR/.aidev/works/$TODAY-early"
printf 'schema: 4\nslug: early\ncurrent: deliver\napproved: [deliver]\n' > "$CVR/.aidev/works/$TODAY-early/state.yml"
printf 'events:\n  - { ts: %sT00:00:00Z, phase: requirements, event: start }\n' \
  "$(date -u +%Y-%m-%d)" > "$CVR/.aidev/works/$TODAY-early/metrics.yml"
# 着手しただけの work は review を通っていない＝判定材料を1つも産んでいないので数えない。
# ここを数えると、レビュー記録がまだ無いのに ready=yes が立ち insights が空の材料で判定する。
mkdir -p "$CVR/.aidev/works/$TODAY-inflight"
printf 'schema: 4\nslug: inflight\ncurrent: coding\napproved: [requirements, design]\n' \
  > "$CVR/.aidev/works/$TODAY-inflight/state.yml"
printf 'events:\n  - { ts: %sT01:00:00Z, phase: requirements, event: start }\n' \
  "$(date -u +%Y-%m-%d)" > "$CVR/.aidev/works/$TODAY-inflight/metrics.yml"
# 導入日より前に着手した work は母集団に入れない（効果を受けていないため）
mkdir -p "$CVR/.aidev/works/20200101-old"
printf 'schema: 4\nslug: old\ncurrent: requirements\napproved: []\n' > "$CVR/.aidev/works/20200101-old/state.yml"
printf 'events:\n  - { ts: 2020-01-01T01:00:00Z, phase: requirements, event: start }\n' \
  > "$CVR/.aidev/works/20200101-old/metrics.yml"

CV_S1=$(run_cv convention status --format tsv)
assert_contains "$CV_S1" "	2	2	yes	" "convention status: 母集団は deliver 済みだけを数える（導入前・同日でも介入前・着手中は数えない）"
assert_contains "$(grep '^introduced:' "$CVF")" "T" "convention new: introduced は時刻まで刻む（日付粒度だと同日の先行 work が混入する）"

# --- --members: 母集団の work を分子（タグ）と同じ集合で出す ---
printf -- '- [must] x [conv:naming-boolean]\n- [should] y [conv:naming-boolean]\n' > "$CVR/.aidev/works/$TODAY-one/review.md"
printf -- '- [should] z [conv:naming-boolean]\n' > "$CVR/.aidev/works/$TODAY-two/review.md"
printf -- '- [must] 混入 [conv:naming-boolean]\n' > "$CVR/.aidev/works/$TODAY-early/review.md"
CV_M=$(run_cv convention status --members naming-boolean --format tsv)
assert_contains "$CV_M" "member	$TODAY-one	" "convention status --members: 母集団の work を列挙する"
assert_absent "$CV_M" "$TODAY-early" "convention status --members: 介入前に着手した work は出さない"
assert_absent "$CV_M" "$TODAY-inflight" "convention status --members: 未 deliver の work は出さない"
assert_eq "$(printf '%s\n' "$CV_M" | grep "^member	$TODAY-one	" | awk -F'\t' '{print $5}')" "2" \
  "convention status --members: work ごとの [conv:<id>] 件数を出す"
assert_contains "$CV_M" "members-summary: id=naming-boolean pop=2 conv_tags=3" \
  "convention status --members: 分母(pop)と分子(タグ)を同じ集合で合計する（early のタグを数えない）"

# --- doctor: 判定できる状態になったら催促する（人間が思い立つまで待たない） ---
# 索引に載っている条項だけ催促する（索引に無い＝読まれていない条項を判定させると ineffective に誤る）
printf '# A\n\n<!-- aidev:conventions -->\n- x → .aidev/conventions/naming-boolean.md\n<!-- /aidev:conventions -->\n' > "$CVR/AGENTS.md"
CV_D1=$(run_cv doctor 2>&1)
assert_contains "$CV_D1" "母集団が揃った(2/2)のに未判定" "doctor: 判定可能なのに未判定を WARN"
assert_contains "$CV_D1" "convention-summary: files=1 archived=0 warn=1" "doctor: 条項のサマリを出す"
rm -f "$CVR/AGENTS.md"
CV_D1b=$(run_cv doctor 2>&1)
assert_absent "$CV_D1b" "のに未判定" "doctor: 索引に無い条項には「未判定」を催促しない（insights は判定禁止）"
assert_contains "$CV_D1b" "索引に無いので判定しない" "doctor: 代わりに「索引に足して数え直す」を案内する"

# --- defer: 「pending のまま置く」判断を CLI で黙らせる（frontmatter の手編集しか無かった） ---
run_cv convention new dfr --hypothesis h --baseline b --verify-after 2 >/dev/null
assert_contains "$(run_cv convention status --format tsv)" "dfr	pending	" "defer 前提: dfr は pending"
run_cv convention defer dfr --verify-after 2 --note n >/dev/null 2>&1
assert_eq "$?" "1" "convention defer: 現在の母集団以下の件数では黙らないので弾く"
run_cv convention defer dfr --verify-after 3 >/dev/null 2>&1
assert_eq "$?" "1" "convention defer: --note 無しは弾く（理由の無い先送りは滞留と区別できない）"
CV_DF=$(run_cv convention defer dfr --verify-after 3 --note "母集団が薄い" 2>&1)
assert_contains "$CV_DF" "deferred: dfr (verify_after 3, pop 2)" "convention defer: 必要件数を積み増す"
assert_contains "$(run_cv convention status --format tsv)" "dfr	pending	" "convention defer: pending のまま"
assert_eq "$(run_cv convention status --format tsv | awk -F'\t' '$2=="dfr"{print $6"/"$7}')" "3/no" "convention defer: need=3 / ready=no になる"
assert_contains "$(cat "$CVR/.aidev/conventions/dfr.md")" "defer_note: 母集団が薄い" "convention defer: 理由を frontmatter に残す"
assert_contains "$(cat "$CVR/.aidev/conventions/dfr.md")" "deferred: " "convention defer: 先送りした時刻を残す"
run_cv convention retire dfr --status superseded --note "naming-boolean に統合" >/dev/null

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
CVT=$(cat "$CVR/.aidev/conventions/archive/naming-boolean.md")
assert_contains "$CVT" "promoted_to: docs/coding-standards.md#naming" "convention promote: 移送先を刻む"
assert_contains "$CVT" "本文は promoted_to へ移送済み" "convention promote: 本文を捨てて tombstone にする"
assert_absent "$CVT" "## 規約" "convention promote: 本文が2箇所に存在しない（二重管理の防止）"

# --- tombstone は重複排除のために残す（消すと同じ提案がまた上がる） ---
run_cv convention new naming-boolean --hypothesis "again" --baseline "b" >/dev/null 2>&1
assert_eq "$?" "1" "convention new: archive の tombstone と同 id は重複として弾く"

# --- 出口ゲート: 母集団が揃う前の confirm / retire ineffective は拒否。--force は forced: true を残す ---
# 背景: 入口（new）には仮説の関門があるのに出口には無く、pop=0 の confirm が通っていた。
# 「事後の物語作り」を防ぎたい層で、判定側では機械的に何も止まっていなかった
run_cv convention new gate --hypothesis h --baseline b --verify-after 50 >/dev/null
run_cv convention confirm gate >/dev/null 2>&1
assert_eq "$?" "1" "convention confirm: --result 無しは弾く（内訳の無い判定は残せない）"
run_cv convention confirm gate --result "pop=2 だが confirm" >/dev/null 2>&1
assert_eq "$?" "1" "convention confirm: 母集団が揃う前は弾く（pop 2 / need 50）"
assert_contains "$(cat "$CVR/.aidev/conventions/gate.md")" "status: pending" "convention confirm: 弾いたら status は動かない"
run_cv convention retire gate --status ineffective >/dev/null 2>&1
assert_eq "$?" "1" "convention retire: --note 無しは弾く（理由の無い退役は再提案を弾く根拠にならない）"
run_cv convention retire gate --status ineffective --note n >/dev/null 2>&1
assert_eq "$?" "1" "convention retire: ineffective も母集団が揃う前は弾く"
assert_eq "$([ -f "$CVR/.aidev/conventions/gate.md" ] && echo yes || echo no)" "yes" "convention retire: 弾いたら退避しない"
CV_FO=$(run_cv convention confirm gate --result "揃う前に確定（理由: 別 PJ で実証済み）" --force 2>&1)
assert_contains "$CV_FO" "forced: true を刻む" "convention confirm --force: 揃う前でも通すが警告する"
assert_contains "$(cat "$CVR/.aidev/conventions/gate.md")" "forced: true" "convention confirm --force: forced を frontmatter に残す（後から「揃う前の判定」と分かる）"
run_cv convention promote gate --to docs/coding-standards.md#gate >/dev/null
# superseded は「別の条項に置き換わった」なので母集団は要らない（置き換え先が判定を引き継ぐ）
run_cv convention new sup --hypothesis h --baseline b >/dev/null
run_cv convention retire sup --status superseded --note "gate に統合" >/dev/null 2>&1
assert_eq "$?" "0" "convention retire: superseded は母集団が揃っていなくても通す"
assert_absent "$(cat "$CVR/.aidev/conventions/archive/sup.md")" "forced" "convention retire superseded: forced を刻まない（免除であって強行ではない）"
# 日付だけの introduced（旧記法）は 00:00:00Z として数える（既存条項を書き換えずに済む）
printf -- '---\nconvention: legacy\nstatus: pending\nintroduced: 2020-06-01\nhypothesis: h\nbaseline: b\nverify_after: 1\n---\n\n# legacy\n\n本文\n' > "$CVR/.aidev/conventions/legacy.md"
assert_contains "$(run_cv convention status --format tsv)" "legacy	pending	2020-06-01	3	1	yes" \
  "convention status: 日付だけの introduced は 00:00:00Z 扱いで数える（後方互換）"
run_cv convention retire legacy --status superseded --note "gate に統合" >/dev/null

# --- retire: 効かなかった条項の行き先は「削除」ではなく「層を下げる」 ---
run_cv convention new err-gran --hypothesis "エラー粒度の指摘が減る" --baseline "b" --verify-after 2 >/dev/null
run_cv convention retire err-gran --status bogus >/dev/null 2>&1
assert_eq "$?" "1" "convention retire: 未知の status を弾く"
CV_R=$(run_cv convention retire err-gran --status ineffective --note "散文層の限界" 2>&1)
assert_contains "$CV_R" "CLI/フック層へ寄せる" "convention retire: ineffective は層を下げる検討を促す"
assert_contains "$(cat "$CVR/.aidev/conventions/archive/err-gran.md")" "note: 散文層の限界" "convention retire: 理由を残す"

# 全部退避されたので警告は消える（定常状態では pending だけが active に残る）
CV_D3=$(run_cv doctor 2>&1)
assert_contains "$CV_D3" "convention-summary: files=0 archived=6 warn=0" "doctor: 退避済みなら警告なし"
# archive 済み条項の pop は計算も表示もしない（意味が無く、条項数×works の走査コストの半分を占めていた）
assert_eq "$(run_cv convention status --format tsv | awk -F'\t' '$2=="naming-boolean"{print $5"/"$7}')" "-/-" "convention status: archive 済みは pop/ready を出さない"

# --- 手編集で壊れた条項も拾う（frontmatter は人間も触る） ---
mkdir -p "$CVR/.aidev/conventions"
printf -- '---\nconvention: broken\n---\n\n# broken\n' > "$CVR/.aidev/conventions/broken.md"
printf -- '---\nconvention: weird\nstatus: kinda\n---\n\n# weird\n' > "$CVR/.aidev/conventions/weird.md"
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
GRD=$(mktemp -d); mkdir -p "$GRD/.aidev/works" "$GRD/.aidev/conventions" "$GRD/docs"
run_gd() { ( cd "$GRD" && "$AIDEV_SH" "$@" ); }
printf '# tgt\n' > "$GRD/tgt.md"

# --- frontmatter が無いファイルを条項として扱わない ---
printf '# README\n\nこのディレクトリの説明。消えてはいけない。\n' > "$GRD/.aidev/conventions/README.md"
SZ0=$(wc -c < "$GRD/.aidev/conventions/README.md")
run_gd convention promote README --to 'tgt.md#x' >/dev/null 2>&1
assert_eq "$?" "1" "promote: frontmatter の無いファイルを弾く"
assert_eq "$(wc -c < "$GRD/.aidev/conventions/README.md")" "$SZ0" "promote: 弾いたファイルの本文が無傷（0バイト化しない）"
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
run_gd convention retire ../important --status ineffective --note n --force >/dev/null 2>&1
assert_eq "$?" "1" "retire: id のパス成分を潰す"
assert_eq "$([ -f "$GRD/docs/important.md" ] && echo yes || echo no)" "yes" "retire: 外のファイルを移動しない"

# --- 退避先が埋まっているときは、破壊する前に失敗する ---
run_gd convention new dup --hypothesis h --baseline "b" >/dev/null
run_gd convention retire dup --status superseded --note n >/dev/null
printf -- '---\nconvention: dup\nstatus: pending\nintroduced: 2026-01-01\nhypothesis: h\nverify_after: 1\n---\n\n# dup\n\n本文。\n' > "$GRD/.aidev/conventions/dup.md"
SZ2=$(wc -c < "$GRD/.aidev/conventions/dup.md")
run_gd convention promote dup --to 'tgt.md#a' >/dev/null 2>&1
assert_eq "$?" "1" "promote: archive が埋まっていれば失敗する"
assert_eq "$(wc -c < "$GRD/.aidev/conventions/dup.md")" "$SZ2" "promote: 失敗時に本文を破壊しない（非原子性の回帰）"
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
printf 'events:\n  - { ts: %sT23:59:59Z, phase: coding, event: start, metrics: { defects: 3 } }\n' \
  "$TODAY_T" > "$TSR/.aidev/works/$TODAY_D-w/metrics.yml"
assert_contains "$(run_ts convention status --format tsv)" "	1	1	yes	" \
  "母集団: metrics キー(defects)を着手日と取り違えない"
rm -rf "$TSR"
echo "== convention: 索引（AGENTS.md の aidev:conventions ブロック） =="
# 背景: AGENTS.md は自動読込されるが .aidev/conventions/ はされない。索引に載っていない条項は**読まれないまま**
# works が流れ、効果検証で「効かなかった」と誤判定される——条項の内容の問題ではなく届いていないだけなのに。
# CLI が「索引に足せ」と言うだけで誰も見ていないと、この誤判定が静かに積み上がる。
IXR=$(mktemp -d); mkdir -p "$IXR/.aidev/works" "$IXR/docs"
run_ix() { ( cd "$IXR" && "$AIDEV_SH" "$@" ); }
IX_NEW=$(run_ix convention new naming --hypothesis "命名の指摘が減る" --baseline "b" --verify-after 1 2>&1)
# `created:` 行にも同じパスが出るので、案内行だけを指す "→ " まで含める
assert_contains "$IX_NEW" "→ .aidev/conventions/naming.md" "convention new: 索引に足す行を提示する（機械にできる部分は機械が出す）"
assert_contains "$IX_NEW" "docsRoots が未設定" "convention new: 未設定なら「確認していない」と明記させる（捏造で埋めない）"

IX_D0=$(run_ix doctor 2>&1)
assert_contains "$IX_D0" "索引ファイルが無い" "doctor: 索引ファイル自体が無いことを WARN"

printf '# AGENTS\n\n<!-- aidev:conventions -->\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
IX_D1=$(run_ix doctor 2>&1)
assert_contains "$IX_D1" "索引に無い（AGENTS.md）" "doctor: 索引に未登録の条項を WARN"
assert_contains "$IX_D1" "→ .aidev/conventions/naming.md" "doctor: 足すべき行をそのまま示す（検査だけあって実行が無い形にしない）"
# needle "no" だけだと ready 列（この時点で no）に当たり、index 列が嘘をついても通る。
# tsv で**列位置ごと**に見る（ready=no, index=no, promoted_to=-）
assert_contains "$(run_ix convention status --format tsv)" "	no	no	-" \
  "convention status: index 列で索引漏れが見える"
assert_contains "$(run_ix convention status)" "索引漏れ=1" "convention status: 索引漏れ件数をサマリに出す"

# 索引に登録すれば警告は消える
printf '# AGENTS\n\n<!-- aidev:conventions -->\n- 命名を判断するとき → .aidev/conventions/naming.md\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
IX_D2=$(run_ix doctor 2>&1)
assert_absent "$IX_D2" "索引に無い" "doctor: 索引に載っていれば警告しない"
assert_contains "$(run_ix convention status)" "索引漏れ=0" "convention status: 登録済みなら索引漏れ 0"

# マーカー外に書いても索引とは認めない（harness が見るのはブロック内だけ）
printf '# AGENTS\n\n- 命名 → .aidev/conventions/naming.md\n\n<!-- aidev:conventions -->\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
assert_contains "$(run_ix doctor 2>&1)" "索引に無い" "doctor: マーカー外の記述は索引と認めない（PJ の領域は見ない）"

# 移送したら索引の張り替え漏れを検知する（promote が「張り替えろ」と言うだけでは誰も見ていない）
printf '# AGENTS\n\n<!-- aidev:conventions -->\n- 命名を判断するとき → .aidev/conventions/naming.md\n<!-- /aidev:conventions -->\n' > "$IXR/AGENTS.md"
printf '# std\n' > "$IXR/docs/std.md"
run_ix convention confirm naming --result r --force >/dev/null
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
# 案内文も追随すること。CLI が config を無視して「AGENTS.md に足せ」と言うと、
# 索引ファイルを移した PJ では**存在しない場所**へ誘導される（検査と案内が食い違う）
assert_contains "$(run_ix convention new err2 --hypothesis h --baseline b 2>&1)" \
  "rules.md の索引ブロックに1行足すこと" "convention new: 案内する索引ファイル名が conventionsIndex に従う"
run_ix convention confirm err2 --result r --force >/dev/null
IX_PR=$(run_ix convention promote err2 --to docs/std.md#err2 2>&1)
assert_contains "$IX_PR" "rules.md の索引ブロックのリンク先" "convention promote: 案内する索引ファイル名が conventionsIndex に従う"
rm -rf "$IXR"

echo "== convention: 母集団は deliver で増える（到達をその瞬間に知らせる） =="
# 背景: doctor の WARN は retro/insights を叩いた人にしか見えない＝既に見に行った人にしか届かない。
# works が母集団に加わる唯一の瞬間は approve deliver なので、そこで鳴らす。
RDR=$(mktemp -d); mkdir -p "$RDR/.aidev/works"
run_rd() { ( cd "$RDR" && "$AIDEV_SH" "$@" ); }
run_rd convention new conv1 --hypothesis h --baseline "b" --verify-after 1 >/dev/null
run_rd new rd >/dev/null
RDW=$(ls "$RDR/.aidev/works")
for p in requirements design tasks coding test review; do
  run_rd event "$p" start >/dev/null; run_rd approve "$p" >/dev/null
done
: > "$RDR/.aidev/works/$RDW/review.md"
# deliver 前は判定材料が無いので ready にならない
assert_contains "$(run_rd convention status --format tsv)" "	0	1	no	" "母集団: deliver 前の work は数えない（review 記録がまだ無い）"
run_rd event deliver start >/dev/null
RD_A=$(run_rd approve deliver files_changed=1 insertions=1 deletions=0 2>&1)
assert_contains "$RD_A" "条項 conv1 の母集団が揃っています(1/1)" "approve deliver: 母集団が揃ったら知らせる（判定するまで鳴る）"
assert_contains "$(run_rd convention status --format tsv)" "	1	1	yes	" "母集団: deliver 済みになって初めて数える"
# 跨いだ**瞬間だけ**。-ge だと以後の全 deliver で全条項ぶん鳴り続ける（100 works×30 条項で 1 回 31 行）
run_rd new rd2 >/dev/null; RDW2=$(ls "$RDR/.aidev/works" | grep -- '-rd2$')
for f in requirements design tasks tasks review test-result; do : > "$RDR/.aidev/works/$RDW2/$f.md"; done
for p in requirements design tasks coding test review; do run_rd event "$p" start >/dev/null; run_rd approve "$p" >/dev/null; done
run_rd event deliver start >/dev/null
RD_B=$(run_rd approve deliver files_changed=1 insertions=1 deletions=0 2>&1)
assert_absent "$RD_B" "母集団が揃いました" "approve deliver: 到達済みの条項は2回目以降鳴らさない（跨いだ瞬間だけ）"
rm -rf "$RDR"
echo "== オプション値の欠落（sh 単体・pwsh 不要） =="
# 背景: この検査は長らく parity ブロックの中にあり、pwsh の無い開発機では**1件も走らなかった**。
# need_arg を no-op にする mutation が pwsh 無しでは生き残る＝27箇所の修正が無防備だった。
# パリティ（sh と ps1 が一致するか）と、sh 単体の不変条件（使い方エラーとして落ちるか）は別物。
NAR=$(mktemp -d); mkdir -p "$NAR/.aidev/works" "$NAR/.aidev/backlog"
for miss in "new x --mode" "new x --profile" "new x --ticket" "new x --depends" "new x --parent" \
            "new x --backlog" "convention new c --hypothesis" "convention new c --baseline" \
            "convention new c --source" "convention new c --verify-after" "backlog new b --kind" \
            "status --format" "metrics --format"; do
  # shellcheck disable=SC2086
  NA_OUT=$( ( cd "$NAR" && "$AIDEV_SH" $miss ) 2>&1 ); NA_RC=$?
  assert_eq "$NA_RC" "1" "値の無いオプションは die(rc=1)（[$miss]）"
  assert_contains "$NA_OUT" "には値が必要です" "値の無いオプションは使い方エラーとして落とす（[$miss]）"
done
rm -rf "$NAR"

rm -rf "$CVR"

echo "== harnessRev（効果検証の母集団の刻印） =="
# 背景: ハーネス改修が効いたかを後から判定するには「どの版で回した work か」が要る。
# 手書きに任せると忘れられ、忘れられた work は母集団から静かに漏れる（schema: と同じ理由で new に一本化）。
# **自前の git リポジトリに CLI を置いて走らせる**。harness_rev は `git -C <skills> log -- aidev-*`
# を引くので、素の $AIDEV_SH を使うと**このリポジトリの履歴**を読む。すると:
#   - tarball 配布や git archive の展開先では `unknown` になり、まただがり検査が発火せず FAIL する
#   - テスト実行中に誰かが aidev-* を触るコミットを入れると、sh と ps1 の間で版が変わって偽陽性になる
# どちらも「テストが置かれた場所の都合」で結果が変わる＝密閉されていない。
HVR=$(mktemp -d); mkdir -p "$HVR/repo/skills/aidev-docs/bin" "$HVR/.aidev/works"
cp "$AIDEV_SH" "$HVR/repo/skills/aidev-docs/bin/aidev"
cp "$AIDEV_PS1" "$HVR/repo/skills/aidev-docs/bin/aidev.ps1"
printf 'x\n' > "$HVR/repo/skills/aidev-docs/note.md"
HV_BIN="$HVR/repo/skills/aidev-docs/bin/aidev"
HV_PS1="$HVR/repo/skills/aidev-docs/bin/aidev.ps1"
if command -v git >/dev/null 2>&1; then
  ( cd "$HVR/repo" && git init -q . && git add -A \
    && git -c user.email=t@t -c user.name=t commit -qm init ) >/dev/null 2>&1
fi
run_hv() { ( cd "$HVR" && "$HV_BIN" "$@" ); }
run_hv new hv >/dev/null
HVW=$(ls "$HVR/.aidev/works")
HVST="$HVR/.aidev/works/$HVW/state.yml"
assert_contains "$(cat "$HVST")" "harnessRev:" "new: harnessRev を自動で刻む"
assert_contains "$(cat "$HVST")" "schema: $CUR_SCHEMA" "new: schema は CURRENT_SCHEMA"

# またがり work（着手時と着地時で版が違う）は効果を半分しか受けていないので母集団から外す
for p in requirements design tasks coding test review deliver; do
  run_hv event "$p" start >/dev/null
done
: > "$HVR/.aidev/works/$HVW/review.md"
# 着手後にハーネスが改修された状況を作る（着手時の刻印だけを別版に書き換える）
awk '{ if ($0 ~ /^harnessRev:/) print "harnessRev: deadbee"; else print }' "$HVST" > "$HVST.t" && mv "$HVST.t" "$HVST"
# `harnessRevDelivered` を書くのは approve deliver、verify が走るのはその前。着地時の刻印を
# 待つ書き方だと、この検査は通常の順序では**一度も発火しない**。deliver 前に鳴ること自体を固定する
HV_VB=$(run_hv verify 2>&1)
assert_contains "$HV_VB" "note: またがり work" "verify: deliver 承認の前でもまたがりを検知する（着地の刻印を待たない）"
# WARN ではなく note。またがりは事後に取り消せない事実で、人が直せることが無い。
# ハーネスを1回コミットしただけで in-flight 全 work が鳴き続けるため、
# 「いま直せる」WARN（記録漏れ・light 逸脱）と同列に置くとそちらが埋もれる
assert_absent "$HV_VB" "WARN またがり" "verify: またがりは WARN ではなく note（直せる WARN を埋もれさせない）"
assert_contains "$HV_VB" "現在" "verify: deliver 前は「現在の版」と比べていると分かる"
run_hv approve deliver files_changed=1 insertions=1 deletions=0 >/dev/null
assert_contains "$(cat "$HVST")" "harnessRevDelivered:" "approve deliver: 着地時の版も刻む"
HV_V=$(run_hv verify 2>&1)
# deliver 済みのまたがりは state.yml に刻まれた事実で、doctor を回すたびに履歴 work ぶん永久に出ていた。
# 層別の材料は metrics --all の straddle 列に移す
assert_absent "$HV_V" "note: またがり work" "verify: deliver 済みのまたがりは鳴らさない（doctor で永久に出さない）"
assert_contains "$(run_hv metrics --all --format tsv)" "	deadbee	yes" "metrics --all: またがり work は straddle=yes（母集団から外す合図はここで見る）"

echo "== harness（ハーネス改修の仮説登録: 入口・出口ゲートと母集団） =="
# 背景: 条項には仮説・baseline 必須の入口と母集団の出口があるのに、ハーネス自身の改修には受け口が無く、
# DESIGN が最も警戒する「事後の物語作り」がそのまま起きていた。同じ型の記録を .aidev/harness/ に置く
run_hv harness new nohyp >/dev/null 2>&1
assert_eq "$?" "1" "harness new: --hypothesis は必須"
run_hv harness new nobase --hypothesis h >/dev/null 2>&1
assert_eq "$?" "1" "harness new: --baseline は必須"
HN=$(run_hv harness new h1 --hypothesis "reworks が減る" --baseline "直近 10 works の reworks 平均 1.4" --verify-after 1 2>&1)
assert_contains "$HN" "created:" "harness new: 登録する"
HNF=$(cat "$HVR/.aidev/harness/h1.md")
assert_contains "$HNF" "harness: h1" "harness new: frontmatter に id"
assert_contains "$HNF" "introduced_rev: " "harness new: 今のハーネス版を刻む"
assert_contains "$HNF" "hypothesis: reworks が減る" "harness new: 仮説を残す"
# 母集団: またがり work（HVW は着手時 deadbee ≠ 着地時）は数えない。着手が導入前なのでどのみち外
assert_contains "$(run_hv harness status --format tsv)" "harness	h1	pending	" "harness status: pending を出す"
assert_eq "$(run_hv harness status --format tsv | awk -F'\t' '$2=="h1"{print $6"/"$8}')" "0/no" "harness status: 導入前・またがり work は母集団に入らない"
# 導入後に着手し、またがらずに deliver した work が母集団に入り、揃った瞬間に知らせる
run_hv new h1w >/dev/null; H1W=$(cat "$HVR/.aidev/current")
for f in requirements design tasks tasks review test-result; do : > "$HVR/.aidev/works/$H1W/$f.md"; done
for p in requirements design tasks coding test review; do run_hv event "$p" start >/dev/null; run_hv approve "$p" >/dev/null; done
run_hv event deliver start >/dev/null
HA=$(run_hv approve deliver files_changed=1 2>&1)
assert_contains "$HA" "ハーネス改修 h1 の母集団が揃っています(1/1)" "approve deliver: ハーネス改修の母集団到達も知らせる"
assert_eq "$(run_hv harness status --format tsv | awk -F'\t' '$2=="h1"{print $6"/"$8}')" "1/yes" "harness status: またがらずに deliver した work を数える"
# またがった work は数えない（着手時の刻印を別版に書き換えてから deliver）
run_hv new h1s >/dev/null; H1S=$(cat "$HVR/.aidev/current")
for f in requirements design tasks tasks review test-result; do : > "$HVR/.aidev/works/$H1S/$f.md"; done
awk '{ if ($0 ~ /^harnessRev:/) print "harnessRev: deadbee"; else print }' "$HVR/.aidev/works/$H1S/state.yml" > "$HVR/.aidev/works/$H1S/state.yml.t" && mv "$HVR/.aidev/works/$H1S/state.yml.t" "$HVR/.aidev/works/$H1S/state.yml"
for p in requirements design tasks coding test review deliver; do run_hv approve "$p" >/dev/null; done
assert_eq "$(run_hv harness status --format tsv | awk -F'\t' '$2=="h1"{print $6}')" "1" "harness status: またがり work は母集団に数えない"
HD=$(run_hv doctor 2>&1 || true)
assert_contains "$HD" "harness: ハーネス改修の記録検査" "doctor: ハーネス改修の記録も検査する"
assert_contains "$HD" "母集団が揃った(1/1)のに未判定" "doctor: 判定可能なハーネス改修を催促する"
# 出口ゲートは条項と同じ
run_hv harness confirm h1 >/dev/null 2>&1
assert_eq "$?" "1" "harness confirm: --result 無しは弾く"
run_hv harness new h2 --hypothesis h --baseline b --verify-after 50 >/dev/null
run_hv harness confirm h2 --result r >/dev/null 2>&1
assert_eq "$?" "1" "harness confirm: 母集団が揃う前は弾く"
run_hv harness retire h2 --status superseded --note "h1 に統合" >/dev/null 2>&1
assert_eq "$?" "0" "harness retire: superseded は母集団が無くても通る"
HC=$(run_hv harness confirm h1 --result "reworks 平均 1.4 -> 0.0（母集団 1）" 2>&1)
assert_contains "$HC" "confirmed: h1" "harness confirm: 判定して退避する"
assert_eq "$([ -f "$HVR/.aidev/harness/archive/h1.md" ] && echo yes || echo no)" "yes" "harness confirm: archive へ移る"
assert_contains "$(cat "$HVR/.aidev/harness/archive/h1.md")" "result: reworks 平均 1.4 -> 0.0（母集団 1）" "harness confirm: 内訳を残す"
run_hv harness new h1 --hypothesis h --baseline b >/dev/null 2>&1
assert_eq "$?" "1" "harness new: 判定済み（archive）と同じ id は重複として弾く"
assert_contains "$(run_hv doctor 2>&1 || true)" "harness-summary: files=0 archived=2 warn=0" "doctor: 判定済みなら警告なし"

# schema<4 の旧 work は遡って違反扱いしない（version-aware）
mkdir -p "$HVR/.aidev/works/20200101-legacy"
printf 'schema: 3\nslug: legacy\ncurrent: requirements\napproved: []\n' > "$HVR/.aidev/works/20200101-legacy/state.yml"
printf 'events:\n' > "$HVR/.aidev/works/20200101-legacy/metrics.yml"
HV_L=$(run_hv verify 20200101-legacy 2>&1)
assert_contains "$HV_L" "verify: 20200101-legacy" "verify が実際に走っている（この後の assert_absent の前提）"
assert_absent "$HV_L" "harnessRev が無い" "verify: schema<4 の work に harnessRev を要求しない"

# --- ps1 側の刻印と検知（sh 専用の検査だと、この3つは mutation で1つも殺せなかった） ---
# ここまでの HVR は sh でしか回っておらず、ps1 の `CURRENT_SCHEMA` / `harnessRevDelivered` /
# またがり検知は**削っても緑のまま**だった。schema<4 は harnessRev 検査のゲートなので、
# ps1 の刻印がずれると Windows で作った work だけ効果検証が静かに無効化される。
if [ -n "$PS_HOST" ]; then
  block_begin hvps
  HP=$(mktemp -d); mkdir -p "$HP/.aidev/works"
  ( cd "$HP" && run_ps1 "$HV_PS1" new hp >/dev/null )
  HPW=$(ls "$HP/.aidev/works"); HPST="$HP/.aidev/works/$HPW/state.yml"
  HPBODY=$(tr -d '\r' < "$HPST")
  assert_contains "$HPBODY" "schema: $CUR_SCHEMA" "ps1: new が刻む schema が sh と同じ（<4 だと検査が無効化される）"
  assert_contains "$HPBODY" "harnessRev:" "ps1: new が harnessRev を刻む"
  for ph in requirements design tasks coding test review deliver; do
    ( cd "$HP" && run_ps1 "$HV_PS1" event "$ph" start >/dev/null )
  done
  : > "$HP/.aidev/works/$HPW/review.md"
  # 着手後にハーネスが改修された状況（着手時の刻印だけを別版にする）
  awk '{ if ($0 ~ /^harnessRev:/) print "harnessRev: deadbee"; else print }' "$HPST" > "$HPST.t" && mv "$HPST.t" "$HPST"
  HP_VB=$( ( cd "$HP" && run_ps1 "$HV_PS1" verify ) 2>&1 | tr -d '\r' )
  assert_contains "$HP_VB" "note: またがり work" "ps1: deliver 前にまたがりを検知する（削っても緑だった箇所）"
  # **ps1 が自分で初めて着地させる**。sh が着地させた work を再承認する形だと、
  # 初回着地でしか起きない副作用（harnessRevDelivered の刻印）が比較対象に入らない
  ( cd "$HP" && run_ps1 "$HV_PS1" approve deliver files_changed=1 insertions=1 deletions=0 >/dev/null )
  assert_contains "$(tr -d '\r' < "$HPST")" "harnessRevDelivered:" "ps1: approve deliver が着地時の版を刻む（削っても緑だった箇所）"
  rm -rf "$HP"
  block_end hvps "5" "hvps"
else
  skip 5 "PowerShell 不在のため ps1 側の harnessRev 刻印を省略"
fi
rm -rf "$HVR"

# --- 版の粒度: aidev-* の外を触っても版は動かない ---
# 背景: <skills> 全体を見ていると、同居する無関係な skill の変更で版が上がり、その間に走った
# work が全部「またがり」に見える。またがり判定は母集団からの**除外**なので、誤検知は
# そのまま効果検証の母集団を痩せさせる。
if command -v git >/dev/null 2>&1; then
  block_begin hrgrain
  GRR=$(mktemp -d)
  mkdir -p "$GRR/skills/aidev-docs/bin" "$GRR/skills/other-skill"
  cp "$AIDEV_SH" "$GRR/skills/aidev-docs/bin/aidev"
  printf 'x\n' > "$GRR/skills/aidev-docs/note.md"
  printf 'x\n' > "$GRR/skills/other-skill/SKILL.md"
  ( cd "$GRR" && git init -q -b master . && git add skills \
    && git -c user.email=t@t -c user.name=t commit -qm init ) >/dev/null 2>&1
  mkdir -p "$GRR/w/.aidev/works"
  GR1=$( ( cd "$GRR/w" && "$GRR/skills/aidev-docs/bin/aidev" new g1 >/dev/null 2>&1; \
           yg() { sed -n 's/^harnessRev: //p' "$1"; }; yg "$GRR/w/.aidev/works/"*g1/state.yml ) )
  # aidev-* の**外**を変更 -> 版は動かないはず
  printf 'y\n' > "$GRR/skills/other-skill/SKILL.md"
  ( cd "$GRR" && git add skills && git -c user.email=t@t -c user.name=t commit -qm other ) >/dev/null 2>&1
  GR2=$( ( cd "$GRR/w" && "$GRR/skills/aidev-docs/bin/aidev" new g2 >/dev/null 2>&1; \
           sed -n 's/^harnessRev: //p' "$GRR/w/.aidev/works/"*g2/state.yml ) )
  assert_eq "$GR2" "$GR1" "harnessRev: aidev-* の外の変更では版が動かない（またがりの誤検知を作らない）"
  # aidev-* の中を変更 -> 版が動くこと（検知そのものを殺していないか）
  printf 'z\n' > "$GRR/skills/aidev-docs/note.md"
  ( cd "$GRR" && git add skills && git -c user.email=t@t -c user.name=t commit -qm harness ) >/dev/null 2>&1
  GR3=$( ( cd "$GRR/w" && "$GRR/skills/aidev-docs/bin/aidev" new g3 >/dev/null 2>&1; \
           sed -n 's/^harnessRev: //p' "$GRR/w/.aidev/works/"*g3/state.yml ) )
  assert_ne "$GR3" "$GR1" "harnessRev: aidev-* の中の変更では版が動く（絞り込みで検知を殺していない）"
  # 版は**内容の tree hash**。コミット SHA だと squash / rebase で同一内容が別版に割れ、
  # PR ブランチで回した work と main で回した work が常に別層になる（GitHub 既定の squash 運用で必ず起きる）
  ( cd "$GRR" && git checkout -qb feat && printf 'w\n' > skills/aidev-docs/note.md \
    && git add skills && git -c user.email=t@t -c user.name=t commit -qm feat ) >/dev/null 2>&1
  GR4=$( ( cd "$GRR/w" && "$GRR/skills/aidev-docs/bin/aidev" new g4 >/dev/null 2>&1; \
           sed -n 's/^harnessRev: //p' "$GRR/w/.aidev/works/"*g4/state.yml ) )
  ( cd "$GRR" && git checkout -q master && git merge -q --squash feat \
    && git -c user.email=t@t -c user.name=t commit -qm squashed ) >/dev/null 2>&1
  # checkout / merge が黙って失敗すると HEAD が feat のままになり、下の比較が「同じ commit を
  # 2回読む」空振りになる（実際にそうなっていた）。段取りが本当に進んだことを先に固定する
  assert_eq "$(git -C "$GRR" branch --show-current)" "master" "harnessRev(squash): master へ戻れている（空振り防止）"
  assert_ne "$(git -C "$GRR" rev-parse HEAD)" "$(git -C "$GRR" rev-parse feat)" "harnessRev(squash): squash commit が作られている（空振り防止）"
  GR5=$( ( cd "$GRR/w" && "$GRR/skills/aidev-docs/bin/aidev" new g5 >/dev/null 2>&1; \
           sed -n 's/^harnessRev: //p' "$GRR/w/.aidev/works/"*g5/state.yml ) )
  assert_eq "$GR5" "$GR4" "harnessRev: squash しても内容が同じなら同じ版（SHA ではなく内容ハッシュ）"
  assert_eq "${#GR5}" "12" "harnessRev: 固定長 12 桁（%h の自動伸長で偽またがりを作らない）"
  # **ハーネスが git 管理外なら unknown**。ここは長く sh だけ落ちていた——`ls-tree` が空でも
  # `git hash-object --stdin` が**空入力に空 blob のハッシュ**を返すので `$r` が空にならず、
  # unknown フォールバックが一度も効かなかった。全環境・全 work で同じ値が刻まれ、
  # 母集団から外れるべき work が「同一版で回した仲間」に化ける（他 PJ の retro が実測）。
  # ps1 には元からガードがあったので、**両実装を突き合わせていれば気づけた**穴でもある
  UNR=$(mktemp -d)
  mkdir -p "$UNR/skills/aidev-docs/bin" "$UNR/w/.aidev/works"
  cp "$AIDEV_SH" "$UNR/skills/aidev-docs/bin/aidev"; cp "$AIDEV_PS1" "$UNR/skills/aidev-docs/bin/aidev.ps1"
  ( cd "$UNR/w" && git init -q -b master . && printf 'x\n' > f \
    && git add -A && git -c user.email=t@t -c user.name=t commit -qm i ) >/dev/null 2>&1
  ( cd "$UNR/w" && "$UNR/skills/aidev-docs/bin/aidev" new u1 ) >/dev/null 2>&1
  assert_eq "$(sed -n 's/^harnessRev: //p' "$UNR/w/.aidev/works/"*u1/state.yml)" "unknown" \
    "harnessRev: ハーネスが git 管理外なら unknown（空 blob のハッシュを刻まない）"
  # 版名が取れない環境では**またがり判定が原理的に成立しない**（両端が unknown で差が出ない）。
  # 版名を捏造して埋めない——mtime や内容ハッシュの代用は無関係な変更で誤検知し、
  # 誤検知はそのまま効果検証の母集団を痩せさせる。代わりに**効かないことを言う**
  assert_contains "$( ( cd "$UNR/w" && "$UNR/skills/aidev-docs/bin/aidev" doctor ) 2>&1 )" "またがり判定が成立しません" \
    "doctor: ハーネスが git 管理外なら、またがり検知が効かないことを言う"
  if [ -n "$PS_HOST" ]; then
    ( cd "$UNR/w" && run_ps1 "$UNR/skills/aidev-docs/bin/aidev.ps1" new u2 ) >/dev/null 2>&1
    assert_eq "$(sed -n 's/^harnessRev: //p' "$UNR/w/.aidev/works/"*u2/state.yml | tr -d '\r')" "unknown" \
      "パリティ: ps1 も git 管理外なら unknown"
  else
    skip 1 "ps1 の unknown 刻印（PowerShell 不在）"
  fi
  # 既に空 blob 値を刻んでしまった work は、読む側でも unknown に寄せる（比較で別 PJ と混ざらない）
  UNW=$(ls -d "$UNR/w/.aidev/works/"*u1)
  awk '{ if ($0 ~ /^harnessRev:/) print "harnessRev: e69de29bb2d1"; else print }' "$UNW/state.yml" > "$UNW/state.yml.t"
  mv "$UNW/state.yml.t" "$UNW/state.yml"
  assert_contains "$( ( cd "$UNR/w" && "$UNR/skills/aidev-docs/bin/aidev" metrics --all --format tsv ) )" "	unknown	" \
    "harnessRev: 既に刻まれた空 blob 値は読むときに unknown へ正規化する"
  rm -rf "$UNR"
  rm -rf "$GRR"
  block_end hrgrain "11" "hrgrain"
else
  skip 11 "harnessRev の粒度（git 不在）"
fi

echo "== coverage（AC 被覆 / tasks.md の整合）=="
# 背景: tasks の完了の目安「design の全範囲が tasks に漏れなく落ちている」と
# 「存在しないタスク ID を指していない・循環していない」は長く散文だけで、誰も検査していなかった。
# spec-kit の /analyze が出す Coverage % に相当する層をハードに上げたのがこのコマンド。
CVR=$(mktemp -d); mkdir -p "$CVR/.aidev/backlog"
run_cv() { ( cd "$CVR" && "$AIDEV_SH" "$@" ); }
run_cv new cov-demo >/dev/null
CVW=$(cat "$CVR/.aidev/current"); CVD="$CVR/.aidev/works/$CVW"

# tasks.md が無い段階は「正常な空」で 0（読み取り専用コマンドがエラー経路を作らない）
CVOUT=$(run_cv coverage 2>&1); CVRC=$?
assert_eq "$CVRC" "0" "coverage: tasks.md が無くても exit 0（正常な空）"
assert_contains "$CVOUT" "tasks.md がまだありません" "coverage: 未作成は note で知らせる"

cat > "$CVD/requirements.md" <<'EOF'
## 完了条件 (受け入れ基準)
- [ ] AC1: ひとつ
- [ ] AC2: ふたつ
- [ ] AC3: みっつ

## 相互作用の受け入れ基準
- [ ] AC-I1 開く / 閉じる: どう開くか
EOF
cat > "$CVD/design.md" <<'EOF'
## 受け入れ基準との対応
- AC1: こう満たす
- AC2: ああ満たす
EOF
cat > "$CVD/tasks.md" <<'EOF'
- [ ] T1: ひとつめ
      対象: `a.py`
      依存: なし
      AC: AC1, AC-I1
- [x] T2: ふたつめ
      依存: T1, T9
      AC: AC2
- [ ] T3: みっつめ
      依存: T4
- [ ] T4: よっつめ
      依存: T3
      AC: AC7
EOF
CVOUT=$(run_cv coverage 2>&1); CVRC=$?
assert_eq "$CVRC" "0" "coverage: 既定は読み取り専用として exit 0"
assert_contains "$CVOUT" "AC-I1" "coverage: 相互作用の AC（AC-I1）も基準として拾う"
assert_contains "$CVOUT" "tasks=3/4(75%)" "coverage: 被覆率を出す（AC3 だけタスク無し）"
assert_contains "$CVOUT" "design=2/4(50%)" "coverage: design の対応漏れも数える"
assert_contains "$CVOUT" "T2 の 依存 が未定義のタスクを指す: T9" "coverage: 未定義のタスク依存を検出"
assert_contains "$CVOUT" "依存の循環に含まれるタスク: T3,T4" "coverage: 依存の循環を検出"
assert_contains "$CVOUT" "T4 が未定義の AC を参照: AC7" "coverage: 未定義の AC 参照を検出"
assert_contains "$CVOUT" "T3 に AC 行が無い" "coverage: AC 行の書き忘れを検出"
assert_contains "$CVOUT" "AC3 に対応するタスクが無い" "coverage: 被覆されない AC を名指しする"
assert_contains "$CVOUT" "coverage-gaps: struct=3 cover=2" "coverage: gap を struct/cover に数え分ける"

# 「なし」は書き忘れと区別する（全角読点区切りも受ける）
cat > "$CVD/tasks.md" <<'EOF'
- [ ] T1: ひとつめ
      依存: なし
      AC: AC1、AC-I1
- [x] T2: ふたつめ
      依存: T1
      AC: AC2, AC3
- [ ] T3: 準備だけ
      依存: なし
      AC: なし
EOF
cat > "$CVD/design.md" <<'EOF'
- AC1: a
- AC2: b
- AC3: c
- AC-I1: d
EOF
CVOUT=$(run_cv coverage --strict 2>&1); CVRC=$?
assert_eq "$CVRC" "0" "coverage --strict: gap が無ければ 0"
assert_contains "$CVOUT" "tasks=4/4(100%)" "coverage: 全 AC が被覆されたら 100%"
assert_contains "$CVOUT" "no_ac=0" 'coverage: AC: なし は書き忘れに数えない' 
assert_absent "$CVOUT" "gap:" "coverage: 整合していれば gap を出さない"
# 全角の「なし」がバイト単位の角括弧式で割られていないこと（`[,、]` の事故の回帰）
assert_absent "$CVOUT" "依存 が未定義" "coverage: 全角『なし』を壊さない（多バイト角括弧式の回帰）"

# --strict は gap があれば exit 4（tasks の承認前ゲート）
printf -- '- [ ] T4: 余り\n      依存: なし\n      AC: AC9\n' >> "$CVD/tasks.md"
CVOUT=$(run_cv coverage --strict 2>&1); CVRC=$?
assert_eq "$CVRC" "4" "coverage --strict: gap があれば exit 4"
assert_contains "$CVOUT" "FAIL(strict)" "coverage --strict: FAIL 行を出す"

# tsv は見出し無しの行だけ
CVTSV=$(run_cv coverage --format tsv 2>&1)
assert_contains "$CVTSV" "$(printf 'AC1\tyes\tT1')" "coverage --format tsv: 行を TSV で出す"
assert_absent "$CVTSV" "$(printf 'ac\tspec\ttasks')" "coverage --format tsv: 見出し行は出さない"

# verify との連動: struct は FAIL、cover は WARN
for f in requirements design tasks tasks review test-result; do [ -f "$CVD/$f.md" ] || : > "$CVD/$f.md"; done
run_cv approve requirements >/dev/null; run_cv approve design >/dev/null; run_cv approve tasks >/dev/null
CVV=$(run_cv verify 2>&1); CVVRC=$?
assert_eq "$CVVRC" "4" "verify: tasks.md の参照が壊れていたら FAIL"
assert_contains "$CVV" "tasks.mdの参照が壊れている(1件)" "verify: 壊れた参照の件数を出す"
# 参照を直すと FAIL が消え、被覆の穴だけが WARN で残る
sed -i.bak 's/AC: AC9/AC: なし/' "$CVD/tasks.md" && rm -f "$CVD/tasks.md.bak"
printf -- '- [ ] AC4: 未着手\n' >> "$CVD/requirements.md"
CVV=$(run_cv verify 2>&1); CVVRC=$?
assert_eq "$CVVRC" "0" "verify: 参照が直れば被覆の穴だけでは FAIL しない"
assert_contains "$CVV" "WARN AC 被覆に穴があります（1 件）" "verify: 被覆の穴は WARN で知らせる"

# test-result.md の実在検査（schema 6）と失敗の生証跡
rm -f "$CVD/test-result.md"
run_cv approve coding >/dev/null; run_cv approve test >/dev/null
CVV=$(run_cv verify 2>&1)
assert_contains "$CVV" "test-result.md欠落(test承認済)" "verify: test 承認済みなら test-result.md を要求する"
printf 'ぜんぶ通った\n' > "$CVD/test-result.md"
run_cv event test sent_back >/dev/null
CVV=$(run_cv verify 2>&1)
assert_contains "$CVV" "失敗の生出力が無い" "verify: 差し戻しがあったのに失敗の生出力が無ければ WARN"
printf '```\nFAILED test_x\n```\n' >> "$CVD/test-result.md"
CVV=$(run_cv verify 2>&1)
assert_absent "$CVV" "失敗の生出力が無い" "verify: 生出力のブロックがあれば WARN は消える"
rm -rf "$CVR"


# --- 監査で見つかった経路（どれも「片方の OS でだけ通る」か「消せない gap」を作っていた）---
echo "== coverage: 入力の揺れと ID 文法（OS 差・誤検出の回帰）=="
CVX=$(mktemp -d); mkdir -p "$CVX/.aidev/backlog"
run_cx() { ( cd "$CVX" && "$AIDEV_SH" "$@" ); }
run_cx new cov-edge >/dev/null
CXW=$(cat "$CVX/.aidev/current"); CXD="$CVX/.aidev/works/$CXW"

# CRLF: Windows チェックアウトの tasks.md で判定が割れると、deliver 前ゲートが OS で反転する
printf -- '- [ ] AC1: a\r\n- [ ] AC2: b\r\n' > "$CXD/requirements.md"
printf -- '- [ ] T1: x\r\n      AC: AC1\r\n      依存: なし\r\n- [ ] T2: y\r\n      AC: AC2\r\n      依存: T1\r\n' > "$CXD/tasks.md"
CXO=$(run_cx coverage --strict 2>&1); CXR=$?
assert_eq "$CXR" "0" "coverage: CRLF の tasks.md でも gap を作らない（OS で判定が割れない）"
assert_contains "$CXO" "tasks=2/2(100%)" "coverage: CRLF でも被覆を正しく数える"

# BOM: ps1 の ReadAllLines は BOM を外すので、sh 側も外さないと先頭行だけ取りこぼす
printf '\357\273\277- [ ] AC1: a\n' > "$CXD/requirements.md"
printf '\357\273\277- [ ] T1: x\n      AC: AC1\n      依存: なし\n' > "$CXD/tasks.md"
CXO=$(run_cx coverage --strict 2>&1); CXR=$?
assert_eq "$CXR" "0" "coverage: BOM 付きでも先頭行を取りこぼさない"
assert_contains "$CXO" "ac=1" "coverage: BOM 付き requirements.md の AC を数える"

# ID 文法: `AC` で始まるだけの普通のチェックリスト行を受け入れ基準にしない
printf -- '- [ ] AC1: a\n- [ ] ACL の設定を直す\n- [ ] ACCESS ログを見る\n' > "$CXD/requirements.md"
printf -- '- [ ] T1: x\n      AC: AC1\n      依存: なし\n' > "$CXD/tasks.md"
CXO=$(run_cx coverage --strict 2>&1); CXR=$?
assert_eq "$CXR" "0" "coverage: ACL / ACCESS を AC と誤認しない（消せない gap を作らない）"
assert_absent "$CXO" "ACL" "coverage: ACL は表に出ない"

# タスク ID: `T1-1` を `T1` に潰すと、正しく書かれた依存が「壊れた参照」になる
printf -- '- [ ] AC1: a\n- [ ] AC2: b\n' > "$CXD/requirements.md"
printf -- '- [ ] T1-1: 枝1\n      AC: AC1\n      依存: なし\n- [ ] T1-2: 枝2\n      AC: AC2\n      依存: T1-1\n' > "$CXD/tasks.md"
CXO=$(run_cx coverage --strict 2>&1); CXR=$?
assert_eq "$CXR" "0" "coverage: T1-1 / T1-2 を別 ID として扱う（依存が壊れない）"
assert_contains "$CXO" "T1-1" "coverage: タスク ID を切り詰めない"

# 重複 ID・自己依存: 「整合を見る」コマンドが最も基本的な違反を見ていなかった
printf -- '- [ ] T1: a\n      AC: AC1\n      依存: T1\n- [ ] T1: dup\n      AC: AC2\n      依存: なし\n' > "$CXD/tasks.md"
CXO=$(run_cx coverage --strict 2>&1); CXR=$?
assert_eq "$CXR" "4" "coverage: 重複 ID / 自己依存は struct gap"
assert_contains "$CXO" "タスク ID が重複している: T1" "coverage: 重複 ID を名指しする"
assert_contains "$CXO" "T1 が自分自身に依存している" "coverage: 自己依存を検出（A→A は循環検出から漏れる）"

# 空の `AC:` 行は「書き忘れ」と文言を分ける
printf -- '- [ ] T1: a\n      AC: \n      依存: なし\n- [ ] T2: b\n      AC: AC1, AC1\n      依存: なし\n' > "$CXD/tasks.md"
CXO=$(run_cx coverage 2>&1)
assert_contains "$CXO" "T1 の AC 行が空" "coverage: 空の AC 行は「行が無い」と区別して報告する"
CXT=$(run_cx coverage --format tsv 2>&1)
assert_contains "$CXT" "$(printf 'AC1\tno\tT2')" "coverage: 同じ AC を2回書いても列は重複しない"

# AC が 0 件は「被覆 100%」ではなく測れていない（ゲートが最も要る場面で空振りしていた）
rm -f "$CXD/requirements.md"
printf -- '- [ ] T1: a\n      AC: なし\n      依存: なし\n' > "$CXD/tasks.md"
CXO=$(run_cx coverage --strict 2>&1); CXR=$?
assert_eq "$CXR" "4" "coverage --strict: AC が1件も無い work は素通りさせない"
assert_contains "$CXO" "受け入れ基準が1件もありません" "coverage: AC ゼロを gap として名指しする"

# `AC: *` を unquoted で展開すると gap 件数が cwd の中身に依存する
printf -- '- [ ] AC1: a\n' > "$CXD/requirements.md"
printf -- '- [ ] T1: g\n      AC: *\n      依存: なし\n' > "$CXD/tasks.md"
CXO=$(run_cx coverage 2>&1)
assert_contains "$CXO" "T1 が未定義の AC を参照: *" "coverage: グロブ文字をファイル名に展開しない"
assert_eq "$(printf '%s\n' "$CXO" | grep -c '未定義の AC を参照')" "1" "coverage: 展開で gap が増殖しない"
rm -rf "$CVX"

echo "== coverage: 分割 work は家族単位で見る（消せない gap を作らない）=="
# subtask は親の requirements.md を継承するので、自分の slice だけを見ると
# 兄弟が担当する AC が必ず「タスクが無い」になり、誰にも直せない gap が恒久的に残る。
CVS=$(mktemp -d); mkdir -p "$CVS/.aidev/backlog"
run_cs() { ( cd "$CVS" && "$AIDEV_SH" "$@" ); }
run_cs new big >/dev/null; CSP=$(cat "$CVS/.aidev/current")
printf -- '- [ ] AC1: a\n- [ ] AC2: b\n- [ ] AC3: c\n' > "$CVS/.aidev/works/$CSP/requirements.md"
printf -- '- AC1: x\n- AC2: y\n- AC3: z\n' > "$CVS/.aidev/works/$CSP/design.md"
run_cs new 01-front --parent "$CSP" >/dev/null
run_cs new 02-back  --parent "$CSP" >/dev/null
printf -- '- [ ] T1: front\n      AC: AC1\n      依存: なし\n' > "$CVS/.aidev/works/$CSP/01-front/tasks.md"

CSO=$(run_cs coverage --strict "$CSP/01-front" 2>&1); CSR=$?
assert_eq "$CSR" "0" "coverage --strict: 兄弟が未 tasks の間は cover を致命にしない（最初の子が通れなくなる）"
assert_contains "$CSO" "tasks 未実施の subtask があります" "coverage: 致命にしない理由を note で出す"
assert_contains "$CSO" "01-front/T1" "coverage: 子のタスク ID には subslug を前置する（兄弟間の T1 衝突を避ける）"
CSO2=$(run_cs coverage "$CSP" 2>&1)
assert_eq "$(printf '%s\n' "$CSO2" | sed -n '/^ac/,$p' | tail -n +2)" \
          "$(printf '%s\n' "$CSO"  | sed -n '/^ac/,$p' | tail -n +2)" \
          "coverage: 親から見ても子から見ても同じ被覆になる"

printf -- '- [ ] T1: back\n      AC: AC2, AC3\n      依存: なし\n' > "$CVS/.aidev/works/$CSP/02-back/tasks.md"
CSO=$(run_cs coverage --strict "$CSP" 2>&1); CSR=$?
assert_eq "$CSR" "0" "coverage --strict: 全 subtask が tasks 済みなら被覆が揃う"
assert_contains "$CSO" "tasks=3/3(100%)" "coverage: 家族全体で 3 AC すべてが被覆される"
assert_absent "$CSO" "tasks 未実施" "coverage: 全員 tasks 済みなら note を出さない"
# verify は家族の根でだけ報告する（子ごとに同じ WARN を重複させない）
rm -f "$CVS/.aidev/works/$CSP/02-back/tasks.md"
for f in requirements design tasks review test-result; do : > "$CVS/.aidev/works/$CSP/$f.md"; done
CSV=$(run_cs verify "$CSP" 2>&1)
assert_eq "$(printf '%s\n' "$CSV" | grep -c 'AC 被覆')" "0" "verify: 未 tasks の subtask がある間は被覆 WARN を出さない"
rm -rf "$CVS"


echo "== 被覆の刻印（approve が自動で刻む）と ac / ac_drift =="
# 背景: 分母がこれまで実装側(files_changed)と分解側(tasks_planned)しか無く、**要求の大きさ**で
# 正規化できなかった。刻印を手書きに任せない理由は harnessRev / schema と同じ（忘れられる）。
MTR=$(mktemp -d); mkdir -p "$MTR/.aidev/backlog"
run_mt() { ( cd "$MTR" && "$AIDEV_SH" "$@" ); }
run_mt new mstamp >/dev/null; MTW=$(cat "$MTR/.aidev/current"); MTD="$MTR/.aidev/works/$MTW"

# tasks.md がまだ無い工程は刻まない（full の requirements をここで潰さない）
run_mt approve requirements >/dev/null
assert_absent "$(cat "$MTD/metrics.yml")" "ac_total" "approve: tasks.md が無ければ被覆を刻まない"

printf -- '- [ ] AC1: a\n- [ ] AC2: b\n- [ ] AC3: c\n' > "$MTD/requirements.md"
printf -- '- AC1: x\n- AC2: y\n' > "$MTD/design.md"
printf -- '- [ ] T1: a\n      AC: AC1\n      依存: なし\n- [ ] T2: b\n      AC: AC2, AC3\n      依存: なし\n- [ ] T3: 下準備\n      AC: なし\n      依存: なし\n' > "$MTD/tasks.md"
assert_contains "$(run_mt coverage)" "ac_none=1" "coverage: 明示的な AC: なし を書き忘れと分けて数える"

run_mt approve design >/dev/null
run_mt approve tasks tasks_planned=3 tasks_anchored=3 >/dev/null
MTM=$(cat "$MTD/metrics.yml")
assert_contains "$MTM" "tasks_planned: 3, tasks_anchored: 3, ac_total: 3" "approve tasks: 手書きのキーの後ろに機械値を足す"
assert_contains "$MTM" "ac_covered: 3, tasks_no_ac: 0, tasks_ac_none: 1" "approve tasks: 被覆・書き忘れ・AC 無しを刻む"

# coding でタスクを足して AC を書き忘れる＝ tasks 以降に生まれた乖離
printf -- '- [ ] T4: 追加でやった作業\n      依存: なし\n' >> "$MTD/tasks.md"
run_mt approve coding tasks_done=4 >/dev/null
assert_absent "$(sed -n 's/.*phase: coding.*/&/p' "$MTD/metrics.yml")" "ac_total" "approve coding: 被覆は刻まない（刻むのは tasks/requirements/review の3工程）"
run_mt approve test passed=9 failed=0 >/dev/null
run_mt approve review must=0 should=0 nit=0 >/dev/null
assert_contains "$(cat "$MTD/metrics.yml")" "nit: 0, ac_total: 3, ac_covered: 3, tasks_no_ac: 1" "approve review: 実装後の被覆を刻む"

MTOUT=$(run_mt metrics)
assert_contains "$MTOUT" "ac  ac_drift" "metrics: ac / ac_drift 列を出す"
assert_eq "$(run_mt metrics --format tsv | awk -F'\t' '{print $8, $9}')" "3 1" "metrics: 要求の規模(3)と tasks 以降に増えた gap(1)"

# 明示指定は機械値で上書きしない
run_mt new mstamp2 >/dev/null; MTW2=$(cat "$MTR/.aidev/current"); MTD2="$MTR/.aidev/works/$MTW2"
printf -- '- [ ] AC1: a\n' > "$MTD2/requirements.md"
printf -- '- [ ] T1: a\n      AC: AC1\n      依存: なし\n' > "$MTD2/tasks.md"
run_mt approve requirements ac_total=99 >/dev/null
assert_contains "$(cat "$MTD2/metrics.yml")" "ac_total: 99" "approve: 明示指定があれば機械値で上書きしない"
assert_absent "$(cat "$MTD2/metrics.yml")" "ac_total: 1," "approve: 明示指定と機械値を二重に刻まない"

# 刻印が1点しかない work では乖離を測れない（0 と表示して「乖離なし」と誤読させない）
assert_eq "$(run_mt metrics "$MTW2" --format tsv | awk -F'\t' '{print $9}')" "-" "metrics: 刻印が1点なら ac_drift は - （測れないことを 0 と書かない）"
rm -rf "$MTR"


echo "== smoke（起動確認 GO/NO-GO）=="
# 出所: cc-sdd の kiro-verify-completion「テストが通ることだけでは FEATURE_GO の根拠にならない」。
# aidev には「成果物が起動して最初の使える状態まで行くか」を見る場所が無かった。
SMK=$(mktemp -d); mkdir -p "$SMK/.aidev/backlog"
run_sm() { ( cd "$SMK" && "$AIDEV_SH" "$@" ); }
run_sm new boot >/dev/null; SMW=$(cat "$SMK/.aidev/current"); SMD="$SMK/.aidev/works/$SMW"

# 未設定は「合格」ではない（黙って緑にしない）
SMO=$(run_sm smoke 2>&1); SMR=$?
assert_eq "$SMR" "2" "smoke: smokeCommand 未設定は exit 2（検証していないことを合格にしない）"
assert_contains "$SMO" "smokeCommand: none と**明示**する" "smoke: 対象外の宣言方法を案内する"
assert_absent "$(cat "$SMD/metrics.yml" 2>/dev/null || true)" "smoke" "smoke: 未設定では何も刻まない"

# none は「対象外と宣言済み」として skip を刻む
printf 'smokeCommand: none\n' > "$SMK/.aidev/config.yml"
SMO=$(run_sm smoke 2>&1); SMR=$?
assert_eq "$SMR" "0" "smoke: smokeCommand: none は exit 0"
assert_contains "$(cat "$SMD/metrics.yml")" "event: smoke, metrics: { result: skip }" "smoke: none は skip を刻む"

# 実行して exit code を CLI が取る（自己申告させない）
printf 'smokeCommand: echo "booted: demo v0.1"\n' > "$SMK/.aidev/config.yml"
SMO=$(run_sm smoke 2>&1); SMR=$?
assert_eq "$SMR" "0" "smoke: コマンドが成功すれば exit 0"
assert_contains "$SMO" "booted: demo v0.1" "smoke: 出力を素通しする（要約しない）"
assert_contains "$(cat "$SMD/metrics.yml")" "result: pass, exit_code: 0" "smoke: pass と exit code を刻む"
# **yget の一律クォート除去に通すと末尾だけ剥がれて壊れる**（実際に壊れた形の回帰）
assert_absent "$SMO" "Unterminated" "smoke: 値の中のクォートを壊さない"

printf 'smokeCommand: exit 3\n' > "$SMK/.aidev/config.yml"
SMO=$(run_sm smoke 2>&1); SMR=$?
assert_eq "$SMR" "4" "smoke: コマンドが失敗すれば exit 4"
assert_contains "$(cat "$SMD/metrics.yml")" "result: fail, exit_code: 3" "smoke: fail と実際の exit code を刻む"

# verify: smokeCommand を設定している PJ でだけ deliver 前に効かせる
for f in requirements design tasks tasks review test-result; do : > "$SMD/$f.md"; done
printf -- '- [ ] AC1: 起動する\n' > "$SMD/requirements.md"
printf -- '- [ ] T1: 起動経路\n      AC: AC1\n      依存: なし\n' > "$SMD/tasks.md"
for p in requirements design tasks coding test review deliver; do run_sm approve "$p" >/dev/null; done
SMV=$(run_sm verify 2>&1); SMR=$?
assert_eq "$SMR" "4" "verify: smoke が失敗のままなら deliver 済でも FAIL"
assert_contains "$SMV" "起動確認が失敗のまま" "verify: 失敗のままであることを名指しする"
printf 'smokeCommand: true\n' > "$SMK/.aidev/config.yml"; run_sm smoke >/dev/null 2>&1
SMV=$(run_sm verify 2>&1); SMR=$?
assert_eq "$SMR" "0" "verify: smoke が通れば FAIL は消える"
# 未設定の PJ には**毎 work 鳴らさない**（直せない WARN を作らない）
rm -f "$SMK/.aidev/config.yml"
SMV=$(run_sm verify 2>&1); SMR=$?
assert_eq "$SMR" "0" "verify: smokeCommand 未設定の PJ では work ごとに鳴らさない"
assert_absent "$SMV" "起動確認" "verify: 未設定は work の問題ではないので verify では触れない"
# 代わりに doctor が PJ 単位で1行だけ知らせる
SMDC=$(run_sm doctor --quiet 2>&1)
assert_contains "$SMDC" "smoke-summary: configured=no" "doctor: 未設定を PJ 単位で1行だけ知らせる"
assert_eq "$(printf '%s\n' "$SMDC" | grep -c '起動するかは誰も見ていません')" "1" "doctor: work 数によらず1行（100 works で 100 行にしない）"
printf 'smokeCommand: none\n' > "$SMK/.aidev/config.yml"
assert_contains "$(run_sm doctor --quiet 2>&1)" "configured=none" "doctor: 対象外の宣言済みなら警告しない"
rm -rf "$SMK"


echo "== debug（詰まったときの原因究明を有限化する）=="
# 出所: cc-sdd の debug subagent（fresh context・有限ラウンド）。
# aidev は上限（maxSendBacks）を state.yml に書くだけで**どこも検査していなかった**。
DBR=$(mktemp -d); mkdir -p "$DBR/.aidev/backlog"
run_db() { ( cd "$DBR" && "$AIDEV_SH" "$@" ); }
run_db new stuck >/dev/null; DBW=$(cat "$DBR/.aidev/current"); DBD="$DBR/.aidev/works/$DBW"
for f in design tasks review test-result; do : > "$DBD/$f.md"; done
printf -- '- [ ] AC1: a\n' > "$DBD/requirements.md"
printf -- '- [ ] T1: x\n      AC: AC1\n      依存: なし\n' > "$DBD/tasks.md"
for p in requirements design tasks; do run_db approve "$p" >/dev/null; done

# 上限に達するまでは黙っている。達した瞬間に知らせる（気付くのが retro では遅い）
DBO=$(run_db event coding sent_back 2>&1)
assert_absent "$DBO" "aidev debug start" "event sent_back: 上限前は促さない"
run_db event coding sent_back >/dev/null
DBO=$(run_db event coding sent_back 2>&1)
assert_contains "$DBO" "aidev debug start --phase coding" "event sent_back: 上限(3)到達をその場で促す"
assert_contains "$DBO" "同じコンテキストで回し続けない" "event sent_back: 何が問題かを言う"

DBO=$(run_db debug status --format tsv 2>&1)
assert_contains "$DBO" "$(printf 'coding\t3\t0\tyes')" "debug status: 差し戻し3・デバッグ未実施・要=yes"
assert_contains "$DBO" "maxSendBacks=3 maxDebugRounds=2 last_action=-" "debug status: 上限と直近の行動"
assert_contains "$(run_db debug 2>&1)" "phase   sent_backs  debug_rounds  due" "debug: 引数なしは status（表）"

# start は「渡さないもの」を明示する（この手順の要）
DBO=$(run_db debug start --phase coding 2>&1); DBR2=$?
assert_eq "$DBR2" "0" "debug start: 1 ラウンド目は通る"
assert_contains "$DBO" "round 1/2" "debug start: ラウンドを数える"
assert_contains "$DBO" "**渡さないもの: これまでの修正の試行履歴**" "debug start: fresh context の要を明示する"

# report は必須フィールドを CLI が強制する（convention new の入口ゲートと同じ）
run_db debug report --phase coding --root-cause x --category logic >/dev/null 2>&1
assert_eq "$?" "1" "debug report: --next-action 無しは弾く"
run_db debug report --phase coding --root-cause x --category bogus --next-action retry >/dev/null 2>&1
assert_eq "$?" "1" "debug report: 未知の --category は弾く"
run_db debug report --phase coding --root-cause x --category logic --next-action bogus >/dev/null 2>&1
assert_eq "$?" "1" "debug report: 未知の --next-action は弾く"

DBO=$(run_db debug report --phase coding --root-cause "save() が例外を握りつぶしていた" \
        --category logic --next-action retry --confidence high --fix-tasks "os.replace の前に再送出" 2>&1)
assert_contains "$DBO" "round 1 -> retry (logic)" "debug report: 記録して次の行動を出す"
assert_contains "$DBO" "同じコンテキストに戻さない" "debug report: retry の意味を言う"
# **本文は decisions.md、列挙値は metrics**（フロー形式の1行に自由文を入れると壊れる）
DBDEC=$(cat "$DBD/decisions.md")
assert_contains "$DBDEC" "## デバッグ D1: logic / retry" "debug report: decisions.md に本文を残す"
assert_contains "$DBDEC" "- 根本原因: save() が例外を握りつぶしていた" "debug report: 根本原因は文章として残す"
assert_contains "$(cat "$DBD/metrics.yml")" "stage: report, round: 1, category: logic, next_action: retry, confidence: high" \
  "debug report: metrics には列挙値だけを刻む"

# start 無しの report は弾く（順序を守らせる）
run_db debug report --phase test --root-cause x --category logic --next-action retry >/dev/null 2>&1
assert_eq "$?" "1" "debug report: start の無い工程では弾く"

# ラウンド上限で止める（無限に粘らせない）
run_db debug start --phase coding >/dev/null
run_db debug report --phase coding --root-cause "外部 API の仕様が違う" --category external --next-action stop_for_human >/dev/null
DBO=$(run_db debug start --phase coding 2>&1); DBR2=$?
assert_eq "$DBR2" "4" "debug start: 上限(2)を超えたら止める"
assert_contains "$DBO" "これ以上粘らない" "debug start: 上限の理由を言う"

# verify: 上限に達したのに何もせず着地した work を捕まえる
for p in coding test review deliver; do run_db approve "$p" >/dev/null; done
DBV=$(run_db verify 2>&1); DBR2=$?
assert_eq "$DBR2" "4" "verify: stop_for_human のまま着地したら FAIL"
assert_contains "$DBV" "人の判断を待つ出口を素通りした" "verify: 何が問題かを名指しする"

# 別 work: 差し戻し上限に達したが debug の記録が無い -> WARN（FAIL にはしない）
run_db new stuck2 >/dev/null; DBW2=$(cat "$DBR/.aidev/current"); DBD2="$DBR/.aidev/works/$DBW2"
for f in design tasks review test-result; do : > "$DBD2/$f.md"; done
printf -- '- [ ] AC1: a\n' > "$DBD2/requirements.md"
printf -- '- [ ] T1: x\n      AC: AC1\n      依存: なし\n' > "$DBD2/tasks.md"
for i in 1 2 3; do run_db event test sent_back >/dev/null; done
for p in requirements design tasks coding test review deliver; do run_db approve "$p" >/dev/null; done
DBV=$(run_db verify 2>&1); DBR2=$?
assert_eq "$DBR2" "0" "verify: 原因究明の記録漏れは WARN 止まり（人の判断が要る）"
assert_contains "$DBV" "test の差し戻しが 3 回（上限 3）だが原因究明の記録が無い" "verify: 上限到達＋未実施を知らせる"
rm -rf "$DBR"


echo "== 監査で見つかった経路（刻印の選び方・家族単位・上限値の端・version-aware）=="
AUD=$(mktemp -d); mkdir -p "$AUD/.aidev/backlog"
run_au() { ( cd "$AUD" && "$AIDEV_SH" "$@" ); }
# **command substitution で呼ばない**（サブシェルになり AU_W/AU_D が呼び側に届かない。
# cov_analyze で踏んだのと同じ形）。結果は AU_W（dated 名）と AU_D（work dir）に入る
mk_work() { # slug
  run_au new "$1" >/dev/null
  AU_W=$(cat "$AUD/.aidev/current"); AU_D="$AUD/.aidev/works/$AU_W"
  for f in design tasks review test-result; do : > "$AU_D/$f.md"; done
  printf -- '- [ ] AC1: a\n- [ ] AC2: b\n' > "$AU_D/requirements.md"
  printf -- '- [ ] T1: x\n      AC: AC1, AC2\n      依存: なし\n' > "$AU_D/tasks.md"
}

# 明示キーの判定は**引数ごとの先頭一致**（連結文字列への部分一致だと値の中の ac_total= で分岐が変わる）
mk_work m1a; AUD1=$AU_D
run_au approve tasks "note=see ac_total=5" >/dev/null
assert_contains "$(cat "$AUD1/metrics.yml")" "note: see ac_total=5, ac_total: 2" "approve: 値の中の ac_total= を明示指定と誤認しない"
mk_work m1b; AUD2=$AU_D; AU_M1B=$AU_W
run_au approve tasks ac_total=9 >/dev/null
assert_contains "$(cat "$AUD2/metrics.yml")" "metrics: { ac_total: 9 }" "approve: 先頭が ac_total= なら機械値で上書きしない"

# ac_covered を持たない刻印は乖離の計算から捨てる（0 とみなすと乖離を捏造する）
run_au approve review >/dev/null
assert_eq "$(run_au metrics "$AU_M1B" --format tsv | awk -F'\t' '{print $9}')" "-" \
  "metrics: ac_total だけ手で渡した刻印は ac_drift に使わない（乖離を捏造しない）"

# 同じ工程を2回 approve しても「2点ある」ことにしない（測れないことを 0 と書かない）
mk_work m5; AUD3=$AU_D; AU_M5=$AU_W
run_au approve tasks >/dev/null; run_au approve tasks >/dev/null
assert_eq "$(run_au metrics "$AU_M5" --format tsv 2>/dev/null | awk -F'\t' '{print $9}')" "-" \
  "metrics: 同じ工程の二重 approve を 2 点と数えない（tasks と review で選ぶ）"
run_au approve review >/dev/null
assert_eq "$(run_au metrics "$AU_M5" --format tsv | awk -F'\t' '{print $9}')" "0" "metrics: tasks と review がそろえば測れる"

# 分割 work: 子では刻まない（家族単位の値を子ごとに刻むと分母が多重計上される）
mk_work split; AUDP=$AU_D
SPP=$(cat "$AUD/.aidev/current")
run_au new 01-a --parent "$SPP" >/dev/null
printf -- '- [ ] T1: x\n      AC: AC1, AC2\n      依存: なし\n' > "$AUDP/01-a/tasks.md"
run_au approve tasks >/dev/null
assert_absent "$(cat "$AUDP/01-a/metrics.yml")" "ac_total" "approve: subtask では被覆を刻まない"

# 起動確認は家族単位。子で打っても親に刻まれ、親の verify が通る
printf 'smokeCommand: true\n' > "$AUD/.aidev/config.yml"
AUSO=$(run_au smoke 2>&1)
assert_contains "$AUSO" "記録は親" "smoke: 子で打ったら親に刻むことを告げる"
assert_contains "$(cat "$AUDP/metrics.yml")" "event: smoke" "smoke: 記録は家族の根に入る"
assert_absent "$(cat "$AUDP/01-a/metrics.yml")" "event: smoke" "smoke: 子には刻まない"
run_au use "$SPP" >/dev/null
for p in requirements design tasks coding test review deliver; do run_au approve "$p" >/dev/null; done
AUV=$(run_au verify "$SPP" 2>&1); AUR=$?
assert_eq "$AUR" "0" "verify: 子で通した smoke が親の deliver ゲートに届く"
assert_absent "$AUV" "起動確認の記録が無い" "verify: 家族の記録を見るので誤 FAIL しない"

# smoke に時間上限（常駐コマンドで自律実行が止まらないように）
if command -v timeout >/dev/null 2>&1; then
  printf 'smokeCommand: sleep 30\nsmokeTimeoutSec: 1\n' > "$AUD/.aidev/config.yml"
  AUSO=$(run_au smoke 2>&1); AUR=$?
  assert_eq "$AUR" "4" "smoke: 上限で打ち切って fail にする"
  assert_contains "$AUSO" "秒で打ち切りました" "smoke: 打ち切ったことを言う"
  assert_contains "$(cat "$AUDP/metrics.yml")" "exit_code: 124" "smoke: 打ち切りの exit code を刻む"
else
  skip 3 "timeout(coreutils) 不在のため smoke の時間上限を省略"
fi
rm -f "$AUD/.aidev/config.yml"

# 上限値の端: maxDebugRounds: 0 は 1 に切り上げる（0 だと start も report も通らず詰む）
mk_work edge; AUDD=$AU_D; AU_EDGE=$AU_W
printf 'maxDebugRounds: 0\n' > "$AUD/.aidev/config.yml"
AUSO=$(run_au debug start --phase coding 2>&1); AUR=$?
assert_eq "$AUR" "0" "debug start: maxDebugRounds: 0 でも詰まない（下限 1）"
assert_contains "$AUSO" "round 1/1" "debug start: 下限 1 として扱う"
rm -f "$AUD/.aidev/config.yml"

# maxSendBacks: 0 の PJ で verify が全工程に鳴らない（debug status の due と同じ条件で絞る）
printf 'maxSendBacks: 0\n' >> "$AUDD/state.yml"
for p in requirements design tasks coding test review deliver; do run_au approve "$p" >/dev/null; done
AUV=$(run_au verify "$AU_EDGE" 2>&1)
assert_eq "$(printf '%s\n' "$AUV" | grep -c '原因究明の記録が無い')" "0" \
  "verify: 差し戻し 0 回の工程には原因究明を求めない（maxSendBacks: 0 で全工程が鳴らない）"

# version-aware: schema 7/8 の検査を旧 work に遡らせない
printf 'smokeCommand: true\n' > "$AUD/.aidev/config.yml"
for sc in 6 7; do
  mkdir -p "$AUD/.aidev/works/2020010$sc-old"
  printf 'schema: %s\nslug: old%s\ncurrent: deliver\napproved: [requirements, design, tasks, coding, test, review, deliver]\nharnessRev: aaa1111\n' "$sc" "$sc" \
    > "$AUD/.aidev/works/2020010$sc-old/state.yml"
  printf 'events:\n  - { ts: 2020-01-0%s\T00:00:00Z, phase: deliver, event: approved }\n' "$sc" \
    > "$AUD/.aidev/works/2020010$sc-old/metrics.yml"
  for f in requirements design tasks tasks review test-result; do : > "$AUD/.aidev/works/2020010$sc-old/$f.md"; done
done
run_au verify 20200106-old >/dev/null 2>&1
assert_eq "$?" "0" "verify: schema 6 の work に起動確認を要求しない（遡って違反にしない）"
run_au verify 20200107-old >/dev/null 2>&1
assert_eq "$?" "4" "verify: schema 7 からは起動確認の記録を要求する"

# --- 2026-09-04 の並行実走で見つかった経路 ---------------------------------------
# いずれも「散文には書いてあるのに CLI が見ていなかった」もの。実走 3 本が独立に踏んだ。

# (1) unapprove の sent_back は**差し戻しの結果**であって原因ではない。
#     数に入れると、規約どおり unapprove した work だけ 3 倍になり、
#     一度も失敗していない coding/test が maxSendBacks の予算を使い切る
mk_work sbq; AU_SBQ=$AU_W
run_au approve coding >/dev/null; run_au approve test >/dev/null
run_au event review sent_back >/dev/null
run_au unapprove test >/dev/null; run_au unapprove coding >/dev/null
AU_SBM=$(cat "$AU_D/metrics.yml")
assert_contains "$AU_SBM" "phase: test, event: sent_back, metrics: { by: unapprove }" \
  "unapprove: 取り消しは by: unapprove 付きで刻む（記録は消さない）"
assert_eq "$(run_au metrics "$AU_SBQ" --format tsv | awk -F'\t' '{print $7}')" "1" \
  "metrics: sent_backs は unapprove 由来を数えない（規約を守った work だけ数が増えない）"
assert_eq "$(run_au debug status --format tsv 2>/dev/null | awk -F'\t' '$1=="coding"{print "leaked"}')" "" \
  "debug status: 一度も失敗していない coding が上流の取り消しで予算を消費しない（行ごと出ない）"

# (2) schema 9: light は design/plan を approve しないので、承認を条件にした
#     成果物実在検査が **light では一度も走らなかった**（requirements.md だけで verify OK だった）
AU_L=$AUD/.aidev
run_au new lt1 --light >/dev/null
AU_LW=$(cat "$AU_L/current"); AU_LD="$AU_L/works/$AU_LW"
printf -- '- [ ] AC1: a\n' > "$AU_LD/requirements.md"
run_au approve requirements >/dev/null
AU_LV=$(run_au verify "$AU_LW" 2>&1); AU_LVR=$?
assert_eq "$AU_LVR" "4" "verify: light で design/plan/tasks が無ければ落ちる（4=不変条件違反）"
assert_contains "$AU_LV" "design.md欠落" "verify: light の欠落を名指しする"
assert_contains "$AU_LV" "tasks.md欠落" "verify: light でも tasks.md を要求する（AC の被覆先）"
for f in design tasks; do : > "$AU_LD/$f.md"; done
printf -- '- [ ] T1: x\n      AC: AC1\n      依存: なし\n' > "$AU_LD/tasks.md"
assert_eq "$(run_au verify "$AU_LW" >/dev/null 2>&1; echo $?)" "0" "verify: 4文書そろえば light も通る"

# (3) light の「指紋」（design/plan の start が無いこと）を機械が見ていなかった
run_au event design start --slug "$AU_LW" >/dev/null 2>&1 || run_au use "$AU_LW" >/dev/null 2>&1
run_au use "$AU_LW" >/dev/null; run_au event design start >/dev/null
assert_contains "$(run_au verify "$AU_LW" 2>&1)" "profile=light だが design を個別に起動" \
  "verify: light の指紋から外れたら WARN（定義しておいて見ていない、を無くす）"

# (5) schema 10: 記録漏れの範囲。**そのとき書かなければ二度と書けない**ものを strict で落とす
# 先行テストが $AUD の config.yml に smokeCommand を残しているので消す。残っていると
# schema 7（起動確認の記録）で FAIL し、ここで見たい記録漏れの検査に届かない
rm -f "$AUD/.aidev/config.yml"
mk_work s10a
# start も刻む。刻まないと event 対の WARN が残り、--strict はそちらで落ちるので
# 「実施形態を刻めば通る」が確かめられない（見たい検査だけを残す）
run_au event coding start >/dev/null; run_au approve coding task_checks=3 >/dev/null
run_au event deliver start >/dev/null; run_au approve deliver >/dev/null
AU_V10=$(run_au verify 2>&1); AU_R10=$?
assert_eq "$AU_R10" "0" "verify: task_check_mode 欠落は既定では WARN 止まり"
assert_contains "$AU_V10" "task_check_mode が無い" \
  "verify: 点検の実施形態が残っていないことを知らせる（委譲か同一セッションかで効き方が違う）"
run_au verify --strict >/dev/null 2>&1; assert_eq "$?" "5" \
  "verify --strict: 実施形態の記録漏れは致命（後から書けない）"
# 刻んだ側は**別の work**で見る。同じ work で approve を打ち直すと start/approved の
# 数が合わなくなり（これは正しい検知）、--strict はそちらで落ちる
mk_work s10c
run_au event coding start >/dev/null
run_au approve coding task_checks=3 task_check_mode=same_session >/dev/null
run_au event deliver start >/dev/null; run_au approve deliver >/dev/null
run_au verify --strict >/dev/null 2>&1; assert_eq "$?" "0" \
  "verify --strict: 実施形態を刻めば通る"
run_au approve coding task_check_mode=deligated >/dev/null 2>&1
assert_eq "$?" "1" "approve: task_check_mode のタイポを弾く（層別が静かに壊れるのを防ぐ）"
# task_checks=0 なら実施形態は要らない（点検していないので形態が無い）
mk_work s10b
run_au event coding start >/dev/null; run_au approve coding task_checks=0 >/dev/null
run_au event deliver start >/dev/null; run_au approve deliver >/dev/null
run_au verify --strict >/dev/null 2>&1
assert_eq "$?" "0" "verify --strict: task_checks=0 なら実施形態は要らない"

# (6) 起動確認は複数行で積める（固定 1 本だと足した表面が一度も起動されない）
mk_work smk
printf 'smokeCommands:\n  - exit 0\n  - exit 0\n' > "$AUD/.aidev/config.yml"
AU_SM=$(run_au smoke 2>&1)
assert_contains "$AU_SM" "smoke: pass (exit 0, 2 本)" "smoke: smokeCommands の全部を走らせる"
assert_contains "$(cat "$AU_D/metrics.yml")" "commands: 2" \
  "smoke: 何本走ったかを刻む（pass が成果物のどこを通ったのか後から分かる）"
printf 'smokeCommands:\n  - exit 0\n  - exit 3\n  - exit 0\n' > "$AUD/.aidev/config.yml"
run_au smoke >/dev/null 2>&1; assert_eq "$?" "4" "smoke: 1 本でも落ちれば fail"
assert_contains "$(cat "$AU_D/metrics.yml")" "failed_index: 2" \
  "smoke: 何本目で落ちたかを刻む（原因を1つに絞る）"
rm -f "$AUD/.aidev/config.yml"

# ps1 が Windows PowerShell 5.1 で動くか（構文レベル）。**pwsh 7 では通るのに 5.1 で落ちる**
# 構文は CI の winps ジョブだけが赤くなり、手元では一生気づかない。安いので静的に見張る
AU_PS51=$(grep -vE '^[[:space:]]*#' aidev.ps1 \
  | grep -nE -- '-Stable|Split-Path[^|]*-LeafBase|Join-String|-AsByteStream|-AsHashtable' || :)
assert_eq "$AU_PS51" "" "aidev.ps1: PowerShell 6+ でしか無い構文を使っていない（5.1 の CI が落ちる）"

# (12) taskcheck: 散文にしか無かった上限を CLI が止める
mk_work tc
printf -- '- [ ] T1: x\n      AC: AC1\n- [ ] T2: y\n      AC: AC2\n' > "$AU_D/tasks.md"
run_au taskcheck start T9 --mode delegated >/dev/null 2>&1
assert_eq "$?" "1" "taskcheck start: tasks.md に無いタスク ID を弾く（打ち間違いが「点検した」に化ける）"
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck report T1 --findings 2 >/dev/null
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck start T1 --mode delegated >/dev/null 2>&1
assert_eq "$?" "4" "taskcheck start: maxTaskCheckRounds に達したら exit 4（散文だけだった上限を CLI へ）"
# 上限で start が止まったあとに report だけ打てると、ラウンドは止まるのに件数が積み上がる
run_au taskcheck report T1 --findings 0 >/dev/null   # 2 回目の start と対になる report
run_au taskcheck report T1 --findings 9 >/dev/null 2>&1
assert_eq "$?" "4" "taskcheck report: 対になる start が無ければ弾く（上限後に件数だけ積ませない）"
run_au taskcheck report T2 --findings 0 >/dev/null 2>&1
assert_eq "$?" "1" "taskcheck report: start の無いタスクは弾く（結果だけ記録させない）"
run_au taskcheck start T2 --mode bogus >/dev/null 2>&1
assert_eq "$?" "1" "taskcheck start: --mode の enum を検査する"
run_au taskcheck start T2 >/dev/null 2>&1
assert_eq "$?" "1" "taskcheck start: --mode は必須（実施形態が残らないと効果を測れない）"
run_au taskcheck start T2 --mode same_session >/dev/null
run_au taskcheck report T2 --findings 0 >/dev/null
assert_contains "$(run_au taskcheck status)" "taskcheck-summary: tasks=2 findings=2 mode=mixed" \
  "taskcheck status: 形態が割れていれば mixed"
# 件数は approve が自動で刻む（手書きさせない）
run_au approve coding >/dev/null
assert_contains "$(cat "$AU_D/metrics.yml")" "task_checks: 2, task_check_findings: 2, task_check_mode: mixed" \
  "approve coding: 点検メトリクスを taskcheck の記録から自動で刻む"
# 明示指定があればそちらを尊重する（従来の手渡しを壊さない）
mk_work tc2
run_au event coding start >/dev/null
run_au approve coding task_checks=0 >/dev/null
assert_contains "$(cat "$AU_D/metrics.yml")" "task_checks: 0" "approve coding: 明示指定は上書きしない"

# (12b) doccheck: 上流文書の独立点検（(a) は長く観測点の無い規約だった）
mk_work dc
: > "$AU_D/architecture.md"
run_au doccheck start bogus --mode delegated >/dev/null 2>&1
assert_eq "$?" "1" "doccheck start: 上流4工程以外は弾く（coding のタスク点検は taskcheck）"
run_au doccheck start design >/dev/null 2>&1
assert_eq "$?" "1" "doccheck start: --mode は必須（実施形態が残らないと効果を測れない）"
run_au doccheck start requirements --mode delegated >/dev/null 2>&1
assert_eq "$?" "0" "doccheck start: 文書があれば通る（requirements.md は mk_work が作る）"
rm -f "$AU_D/architecture.md"
run_au doccheck start architecture --mode delegated >/dev/null 2>&1
assert_eq "$?" "2" "doccheck start: 対象 md が無ければ exit 2（前提成果物の不足。使い方の誤り=1 と分ける）"
: > "$AU_D/architecture.md"
run_au doccheck start tasks --mode delegated >/dev/null 2>&1   # tasks.md は mk_work が作る
assert_eq "$?" "0" "doccheck start: tasks も通る"
run_au doccheck report tasks --findings 2 >/dev/null
run_au doccheck report tasks --findings 5 >/dev/null 2>&1
assert_eq "$?" "4" "doccheck report: 対になる start が無ければ弾く（taskcheck と同じ穴を塞いである）"
run_au doccheck start tasks --mode delegated >/dev/null
run_au doccheck start tasks --mode delegated >/dev/null 2>&1
assert_eq "$?" "4" "doccheck start: maxDocCheckRounds に達したら exit 4"
run_au doccheck start design --mode same_session >/dev/null
run_au doccheck report design --findings 0 >/dev/null
# **数えるのは report まで届いたラウンドだけ**（start だけのラウンドは「点検した」に数えない）
assert_contains "$(run_au doccheck status)" "doccheck-summary: rounds=2 findings=2 mode=mixed" \
  "doccheck status: report まで届いたラウンドだけ数え、形態が割れていれば mixed"
# 件数は approve が自動で刻む（工程ごと）
run_au approve tasks >/dev/null
assert_contains "$(cat "$AU_D/metrics.yml")" "doc_check_rounds: 1, doc_check_findings: 2, doc_check_mode: delegated" \
  "approve <phase>: 上流の点検メトリクスを doccheck の記録から自動で刻む（report まで届いた分）"
# schema 11: autonomous で記録が無ければ verify が WARN（--strict で致命）
mk_work dcauto
awk '{ if ($0 ~ /^mode:/) print "mode: autonomous"; else print }' "$AU_D/state.yml" > "$AU_D/state.yml.t"
mv "$AU_D/state.yml.t" "$AU_D/state.yml"
run_au approve design >/dev/null
assert_contains "$(run_au verify 2>&1)" "design を autonomous で承認したのに独立点検の記録がありません" \
  "verify: autonomous の上流文書に独立点検の記録が無ければ WARN（schema 11）"
run_au verify --strict >/dev/null 2>&1
assert_eq "$?" "5" "verify --strict: 上流の独立点検の記録漏れは致命"
run_au doccheck start design --mode delegated >/dev/null
run_au doccheck report design --findings 0 >/dev/null
run_au approve design >/dev/null
assert_eq "$(run_au verify 2>&1 | grep -c '独立点検の記録がありません')" "0" \
  "verify: 記録があれば鳴らない"
assert_contains "$(run_au limits --format tsv)" "limit	maxDocCheckRounds	2	default	pj	2" \
  "limits: maxDocCheckRounds も一覧に出る"
# **work が 1 本も無い PJ でも PJ 側の上限は見せる**。die は exit するので `if resolve_work …` では
# 受からず、無言の exit 1 になっていた（実走で発覚。導入直後に上限を確かめたい、その瞬間に効かない）
LMZ=$(mktemp -d); mkdir -p "$LMZ/.aidev/works"
LMZ_OUT=$( ( cd "$LMZ" && "$AIDEV_SH" limits ) 2>&1 ); LMZ_RC=$?
assert_eq "$LMZ_RC" "0" "limits: work が 1 本も無くても落ちない（die が exit する穴）"
assert_contains "$LMZ_OUT" "work が未選択なので scope=work は既定値" "limits: work 未選択を明示して既定値を見せる"
if [ -n "$PS_HOST" ]; then
  LMZ_PS=$( ( cd "$LMZ" && run_ps1 "$AIDEV_PS1" limits ) 2>&1 | tr -d '\r' ); LMZ_PRC=$?
  assert_eq "$LMZ_PRC" "0" "パリティ: ps1 も work 0 本で落ちない（try/catch も exit は受からない）"
  assert_eq "$LMZ_OUT" "$LMZ_PS" "パリティ: limits（work 0 本）の出力"
else
  skip 2 "ps1 の limits（work 0 本）"
fi
rm -rf "$LMZ"
# **手渡しの *_check_mode は CLI の記録と突き合わせる**。突き合わせないと、点検を一度も打たずに
# approve <phase> doc_check_mode=… と書くだけで verify --strict を通せた（実走で再現）
mk_work dcfake
: > "$AU_D/design.md"
run_au approve design doc_check_mode=delegated >/dev/null 2>&1
assert_eq "$?" "1" "approve: doccheck の記録が無いのに doc_check_mode を手で渡せない（strict のすり抜け）"
run_au approve coding task_check_mode=delegated >/dev/null 2>&1
assert_eq "$?" "1" "approve: taskcheck の記録が無いのに task_check_mode を手で渡せない"
run_au approve coding task_checks=0 >/dev/null 2>&1
assert_eq "$?" "0" "approve: 「点検していない」を表す task_checks=0 は従来どおり通る"
run_au doccheck start design --mode delegated >/dev/null
run_au doccheck report design --findings 0 >/dev/null
run_au approve design doc_check_mode=delegated >/dev/null 2>&1
assert_eq "$?" "0" "approve: 記録があれば手渡しの doc_check_mode を尊重する"
# tasks の点検には tasks.md も渡す（AC: 行は tasks.md にしかない）
assert_contains "$(run_au doccheck start tasks --mode delegated)" "渡すもの: tasks.md" \
  "doccheck start: tasks だけ渡すものが違う（AC: 行の在処に合わせる）"
# 失敗時の見出しを stdout に出さない（成功時と同じ1行に見えてしまう）
run_au doccheck report tasks --findings 0 >/dev/null
assert_eq "$( ( run_au doccheck report tasks --findings 0 ) 2>/dev/null )" "" \
  "doccheck report: 対欠落の FAIL は stdout を汚さない"
# subtask は上流3文書を親から継承する（子に md が無い）ので、対象は**子自身の tasks.md だけ**
run_au new dcp --mode autonomous >/dev/null
DCP=$(cat "$AUD/.aidev/current")
run_au new dcs --parent "$DCP" --mode autonomous >/dev/null
DCSD="$AUD/.aidev/works/$DCP/dcs"
: > "$DCSD/tasks.md"
run_au approve tasks >/dev/null
DCSV=$(run_au verify 2>&1)
assert_contains "$DCSV" "tasks を autonomous で承認したのに独立点検の記録がありません" \
  "verify(subtask): 子自身の tasks.md は独立点検の対象"
assert_eq "$(printf '%s' "$DCSV" | grep -c 'design を autonomous')" "0" \
  "verify(subtask): 親から継承する上流3文書は対象外（子に md が無い）"

# (12c) 他 PJ の retro が見つけた指摘
# **旧 schema の work には doccheck の WARN を出さない**。一度は「schema を問わず WARN」を入れたが、
# 報告元が「その時点のハーネスに機能が無かっただけ」と訂正してきたので撤回した——
# 承認済みの工程に後から点検は掛けられず、旧 work では永久に鳴って直せない
mk_work dcs10
awk '{ if ($0 ~ /^schema:/) print "schema: 10"; else if ($0 ~ /^mode:/) print "mode: autonomous"; else print }' \
  "$AU_D/state.yml" > "$AU_D/state.yml.t" && mv "$AU_D/state.yml.t" "$AU_D/state.yml"
: > "$AU_D/design.md"
run_au event design start >/dev/null
run_au approve design >/dev/null
assert_eq "$(run_au verify 2>&1 | grep -c '独立点検の記録がありません')" "0" \
  "verify: schema 10 の work には独立点検の WARN を出さない（直せない警告を永久に鳴らさない）"
# 件数を刻んだのに内容が review.md に残っていない
mk_work tclog
printf -- '- [ ] T1: x\n      AC: AC1\n' > "$AU_D/tasks.md"
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck report T1 --findings 2 >/dev/null
run_au approve coding >/dev/null
assert_contains "$(run_au verify 2>&1)" "「タスク点検ログ」節がありません" \
  "verify: findings>0 なのにログ節が無ければ WARN（件数だけ残り何を直したか辿れない）"
printf '# レビュー\n\n## タスク点検ログ\n- x\n' > "$AU_D/review.md"
assert_eq "$(run_au verify 2>&1 | grep -c 'タスク点検ログ」節がありません')" "0" \
  "verify: ログ節があれば鳴らない"
# new --mode autonomous は「選択の帰結」をその場で出す
assert_contains "$(run_au new dcnote --mode autonomous)" "上流4工程は独立点検が必須" \
  "new: autonomous を選んだ時点で必須になる点検を知らせる（付録は該当条件を知らないと読まれない）"
assert_eq "$(run_au new dclight --mode autonomous --light | grep -c '上流4工程は独立点検が必須')" "0" \
  "new: light では出さない（light は独立点検を使わない）"

# (12d) 他 PJ の retro（host）が見つけた 4 件
# **「点検して 0 件」と「start だけで終わった」を見分ける**。散文（protocol-check.md）は
# 「形式不正なら点検しなかったものとして扱う（task_checks に数えない）」と定めているのに、
# CLI は start で数えていた——**散文と CLI が食い違っていた**
mk_work tcun
printf -- '- [ ] T1: x\n      AC: AC1\n- [ ] T2: y\n      AC: AC2\n' > "$AU_D/tasks.md"
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck report T1 --findings 2 >/dev/null
run_au taskcheck start T2 --mode delegated >/dev/null   # report を打たない（委譲の出し忘れ）
TCUN=$(run_au taskcheck status)
assert_contains "$TCUN" "taskcheck-summary: tasks=1 findings=2" \
  "taskcheck: 数えるのは report まで届いたタスクだけ（断念は数えない）"
assert_contains "$TCUN" "report が無い start が 1 件あります（T2）" \
  "taskcheck status: 未報告の start を名指しする（0 件と未実施を見分ける）"
assert_contains "$(run_au verify 2>&1)" "report が追いついていないものが 1 件あります（T2）" \
  "verify: 未報告の start を WARN する"
run_au approve coding >/dev/null
assert_contains "$(cat "$AU_D/metrics.yml")" "task_checks: 1, task_check_findings: 2" \
  "approve coding: 未報告のタスクは task_checks に数えない（散文どおり）"
# **ラウンド粒度**でも見る。protocol-check「(b)」が明示的に認めている「1ラウンド目は成功・
# 2ラウンド目を断念」は、`report が 1 度も無い` だけで見ていた頃はまるごと網から落ちていた
# （表は unreported=yes と出すのに、同じコマンドの note と verify が黙る自己矛盾つき）
run_au taskcheck start T1 --mode delegated >/dev/null   # 2ラウンド目・report を打たない
TCR2=$(run_au taskcheck status)
assert_contains "$TCR2" "（T1 T2）" \
  "taskcheck: 2ラウンド目の断念も名指しする（ラウンド粒度で見る）"
assert_contains "$(run_au verify 2>&1)" "（T1 T2）" \
  "verify: 2ラウンド目の断念も WARN する"
# **断念は認められた出口**なので、decisions.md に残せば消える。消す手段が
# 「規約が禁じている report を打つ」しか無い WARN は、規約に従うほど鳴り続ける
printf -- '- T1: 形式不正が2回続いたので断念。60 review に委ねる\n' > "$AU_D/decisions.md"
assert_contains "$(run_au taskcheck status)" "（T2）" \
  "taskcheck: decisions.md に残した断念は名指ししない"
assert_eq "$(run_au verify 2>&1 | grep -c 'T1 T2')" "0" \
  "verify: decisions.md に残した断念は WARN から外れる"
rm -f "$AU_D/decisions.md"
# doccheck の report を「直したあと」に打ったら言う（規約はあったが破っても何も起きなかった）
mk_work dcsz
printf 'design\n' > "$AU_D/design.md"
run_au doccheck start design --mode delegated >/dev/null
printf 'あとから直した\n' >> "$AU_D/design.md"
assert_contains "$(run_au doccheck report design --findings 1)" "start 時点から変わっています" \
  "doccheck report: 直したあとに打つと言う（report は直す前に打つ）"
run_au doccheck start design --mode delegated >/dev/null
assert_eq "$(run_au doccheck report design --findings 0 | grep -c '変わっています')" "0" \
  "doccheck report: 直していなければ鳴らない"
# **tasks は tasks.md の 2 つ**を渡す（dc_start の出力自身がそう言っている）。
# tasks.md しか見ていなかった頃は、`AC:` 行がある tasks.md だけを直しても何も言わなかった
mk_work dcplan
printf 'tasks\n' > "$AU_D/tasks.md"
printf -- '- [ ] T1: x\n      AC: AC1\n' > "$AU_D/tasks.md"
run_au doccheck start tasks --mode delegated >/dev/null
printf -- '      対象: src/a.py\n' >> "$AU_D/tasks.md"
assert_contains "$(run_au doccheck report tasks --findings 1)" "tasks.md が start 時点から変わっています" \
  "doccheck report: tasks は tasks.md の変更も見る（AC 行はそこにしかない）"
# **doccheck にも未報告の検知**。protocol-check は (a)(b) で「規律・禁止事項は共通」と宣言しているのに、
# 数え方だけ対称化して検知は (b) にしか無く、上流文書の出し忘れは一生表に出なかった
mk_work dcun
printf 'design\n' > "$AU_D/design.md"
run_au doccheck start design --mode delegated >/dev/null   # report を打たない
DCUN=$(run_au doccheck status)
assert_contains "$DCUN" "report が無い start が 1 件あります（design）" \
  "doccheck status: 未報告の start を名指しする（taskcheck と同じ文言）"
assert_contains "$(run_au doccheck status --format tsv)" "doccheck	design	0	0	" \
  "doccheck status: 数えるのは report まで届いたラウンドだけ"
assert_contains "$(run_au verify 2>&1)" "doccheck の start に report が追いついていない" \
  "verify: doccheck の未報告も WARN する"
printf -- '- design: 形式不正が2回続いたので断念\n' > "$AU_D/decisions.md"
assert_eq "$(run_au doccheck status | grep -c 'report が無い start')" "0" \
  "doccheck: decisions.md に残した断念は名指ししない"
rm -f "$AU_D/decisions.md"
# 上限に照らすのは **start の数**。report 数で判定すると「まだ余裕がある」と出したそばから exit 4 になる
assert_contains "$(run_au doccheck status)" "yes" \
  "doccheck status: at_max は start の数で判定する（未報告でも枠は食う）"
# remote が無い＝人間由来の判定材料が 1 件も残らない work を機械が拾えるようにする
mk_work rem
run_au approve deliver >/dev/null
assert_contains "$(cat "$AU_D/metrics.yml")" "remote: none" \
  "approve deliver: remote が無い環境を刻む（PR レビュー節が生まれないことを insights が拾える）"

# (13) limits: 上限の一覧と設定口（手編集しかなかった）
assert_contains "$(run_au limits)" "maxTaskCheckRounds" "limits: 上限を一覧できる"
assert_contains "$(run_au limits --format tsv)" "limit	maxDebugRounds	2	default	pj	2" \
  "limits: どこから来た値か（config/state/既定）まで出す"
run_au limits set maxTaskCheckRounds 5 >/dev/null
assert_contains "$(run_au limits --format tsv)" "limit	maxTaskCheckRounds	5	config	pj	2" \
  "limits set: PJ スコープは config.yml に書く"
run_au limits set maxSendBacks 7 >/dev/null
assert_contains "$(run_au limits --format tsv)" "limit	maxSendBacks	7	state	work	3" \
  "limits set: work スコープは state.yml に書く"
run_au limits set maxTaskCheckRounds 0 >/dev/null 2>&1
assert_eq "$?" "1" "limits set: 下限を検査する（0 だと start が必ず止まり出口が無い）"
run_au limits set bogus 3 >/dev/null 2>&1
assert_eq "$?" "1" "limits set: 未知のキーを弾く（効かない設定を書かせない）"
assert_contains "$(run_au limits set maxDebugRounds -1 2>&1)" "値は 0 以上の整数" \
  "limits set: 負値を「未知のオプション」と言わない（値として読んでから弾く）"
assert_contains "$(run_au limits set maxTaskCheckRounds 3 --slug "$AU_W" 2>&1)" "--slug は使えません" \
  "limits set: PJ スコープのキーに --slug を渡したら弾く（黙って無視すると効いたつもりが残る）"
run_au limits unset maxSendBacks >/dev/null
assert_contains "$(run_au limits --format tsv)" "limit	maxSendBacks	3	default	work	3" \
  "limits unset: 行を消して既定へ戻す（set <既定値> だと source が config のまま残る）"
assert_contains "$(run_au limits unset maxSendBacks 2>&1)" "書かれていません" \
  "limits unset: 書かれていないキーでも落ちない（冪等）"
# config.yml が「そのキーだけ」のとき（grep -v が全行落として exit 1 になる形）
printf 'maxDebugRounds: 4\n' > "$AUD/.aidev/config.yml"
run_au limits unset maxDebugRounds >/dev/null
assert_contains "$(run_au limits --format tsv)" "limit	maxDebugRounds	2	default	pj	2" \
  "limits unset: 唯一の行でも消える（grep -v の全行落ち exit 1 で消え損ねない）"
# 設定した上限が実際に効く
mk_work tc3
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck start T1 --mode delegated >/dev/null
run_au taskcheck start T1 --mode delegated >/dev/null 2>&1
assert_eq "$?" "4" "limits set: 設定した maxTaskCheckRounds=5 が実際に効く"
run_au limits set maxTaskCheckRounds 2 >/dev/null

# (10) schema 7 のゲートは smokeCommands だけの PJ でも効く（単数キーしか見ていなかった）
printf 'smokeCommands:\n  - exit 0\n' > "$AUD/.aidev/config.yml"
mk_work sc7
run_au approve deliver >/dev/null
assert_contains "$(run_au verify 2>&1)" "起動確認の記録が無い" \
  "verify: smokeCommands だけの PJ でも deliver 前の起動確認ゲートが効く"
run_au smoke >/dev/null 2>&1
assert_eq "$(run_au verify 2>&1 | grep -c '起動確認の記録が無い')" "0" \
  "verify: smoke を通せばゲートは解ける"
rm -f "$AUD/.aidev/config.yml"

# (11) humanGates に設定口がある（state.yml の手編集しか手段が無かった）
run_au new hg1 --mode autonomous --human-gates design,review >/dev/null
assert_contains "$(cat "$AUD/.aidev/works/$(cat "$AUD/.aidev/current")/state.yml")" "humanGates: [design, review]" \
  "new --human-gates: 部分自律の宣言を CLI から刻める"
run_au new hg2 --human-gates bogus >/dev/null 2>&1
assert_eq "$?" "1" "new --human-gates: 未知の工程を弾く（タイポで黙って無効化されない）"

# (9) 刻み直しは「訂正」であって新しいラウンドではない（WARN の指示が別の FAIL を生まない）
# `task_check_mode` は CLI の記録と突き合わせるので、先に taskcheck を打っておく
# （手渡しだけで「点検した」と名乗れないのが正。approve の突き合わせ検査を参照）
mk_work amd
printf -- '- [ ] T1: x\n      AC: AC1\n' > "$AU_D/tasks.md"
run_au taskcheck start T1 --mode same_session >/dev/null
run_au taskcheck report T1 --findings 0 >/dev/null
run_au event coding start >/dev/null
run_au approve coding task_checks=3 >/dev/null
run_au approve coding task_checks=3 task_check_mode=same_session >/dev/null
AU_AM=$(cat "$AU_D/metrics.yml")
assert_contains "$AU_AM" "task_check_mode: same_session, amend: yes" \
  "approve: 同一ラウンドの刻み直しは amend として追記する（記録は消さない）"
assert_eq "$(run_au verify >/dev/null 2>&1; echo $?)" "0" \
  "verify: 訂正を「approve の重複」と誤検知しない（WARN の指示が別の WARN を生まない）"
assert_eq "$(run_au verify 2>&1 | grep -c 'approve の重複')" "0" "verify: 重複 WARN が出ない"
assert_eq "$(run_au metrics "$AU_W" --format tsv 2>/dev/null | awk -F'\t' '{print $7}')" "0" \
  "metrics: 訂正は差し戻しにも数えない"
# 差し戻しを挟んだ再承認は**新しいラウンド**（amend にしない）
run_au event coding start >/dev/null
run_au approve coding task_checks=1 task_check_mode=delegated >/dev/null
assert_eq "$(grep -c 'phase: coding, event: approved' "$AU_D/metrics.yml")" "3" \
  "approve: start を挟んだ再承認は訂正ではない（3 件目が積まれる）"
assert_eq "$(run_au verify 2>&1 | grep -c 'approve の重複')" "0" \
  "verify: start 2 / approved 2（訂正を除く）は対が揃っている"

# (7) backlog の行単位の保持（inflight はファイル単位の件数しか言えない）
BLR=$(mktemp -d); mkdir -p "$BLR/.aidev/backlog"
run_bl() { ( cd "$BLR" && "$AIDEV_SH" "$@" ); }
printf -- '- [ ] 項目A\n- [ ] 項目B\n' > "$BLR/.aidev/backlog/b.md"
run_bl new w1 --backlog b.md --backlog-item "項目A" >/dev/null
run_bl new w2 --backlog b.md --backlog-item "項目B" >/dev/null
BL_S=$(run_bl status)
assert_contains "$BL_S" "[作業中] 項目A" "status: 掴んでいる行を HELD に出す（どの行が空いているか答えられる）"
run_bl approve deliver --slug w2 >/dev/null
BL_S=$(run_bl status)
assert_contains "$BL_S" "[着地済] 項目B" \
  "status: deliver 済み・未マージの行も HELD に残す（inflight から外れ todo に戻る死角）"
assert_eq "$(printf '%s' "$BL_S" | grep -c '⚠ 同じ項目')" "0" "status: 重複が無ければ二重着手の警告は出さない"
run_bl new w3 --backlog b.md --backlog-item "項目A" >/dev/null
assert_contains "$(run_bl status)" "⚠ 同じ項目を 2 本以上が作業中です（二重着手）: 項目A" \
  "status: 同じ行を 2 本が作業中なら警告する（CLI が二重着手を言えるようにする）"
rm -rf "$BLR"

# (8) 条項の母集団通知は**判定するまで**鳴る（跨いだ瞬間だけだと、後から着地した work に届かない）
CVR=$(mktemp -d); mkdir -p "$CVR/.aidev/works" "$CVR/docs/aidev"
run_cv() { ( cd "$CVR" && "$AIDEV_SH" "$@" ); }
printf 'conventionsDir: docs/aidev\n' > "$CVR/.aidev/config.yml"
run_cv convention new c1 --hypothesis h --baseline b --verify-after 1 >/dev/null 2>&1
for w in a b; do
  run_cv new "$w" >/dev/null
  CVW=$(cat "$CVR/.aidev/current")
  for f in requirements design tasks review test-result; do : > "$CVR/.aidev/works/$CVW/$f.md"; done
  CV_OUT=$(run_cv approve deliver 2>&1)
done
assert_contains "$CV_OUT" "母集団が揃っています" \
  "approve deliver: 閾値を跨いだ**後**の着地にも催促が届く（未判定のあいだ鳴る）"
rm -rf "$CVR"

# (4) doctor: 0 件でも節見出しを出す（「検査が無い」と「検査して 0 件」は別の情報）
assert_contains "$(run_au doctor 2>&1)" "harness-summary: files=0" \
  "doctor: ハーネス改修の記録が 0 件でも節を出す（条項側と同じ）"

rm -rf "$AUD"


echo "== awk 実装の差（同じ入力で同じ判定になるか）=="
# 背景: `awk -v` の**値**にもエスケープ処理がかかり、その扱いが実装で割れる。
# mawk は `\[` をそのまま残し、gawk は `[` に潰して警告を出す。潰れると
# `- \[[ xX]\]` が `- [[ xX]]`（角括弧式）に化けてチェックボックス行に当たらず、
# **受け入れ基準が1件も取れなくなる**。開発機（mawk）では緑、CI（gawk）で 57 件 fail、
# という形で一度出した。正規表現は**プログラム中のリテラル**として書くこと。
AWKD=$(mktemp -d); mkdir -p "$AWKD/.aidev/works/w"
printf 'schema: 8\nslug: w\ncurrent: tasks\napproved: []\n' > "$AWKD/.aidev/works/w/state.yml"
printf 'w\n' > "$AWKD/.aidev/current"
printf -- '- [ ] AC1: ひとつ\n- [ ] AC-I1 開く / 閉じる: どう\n- [ ] ACL の設定\n' > "$AWKD/.aidev/works/w/requirements.md"
printf -- '- AC1: x\n' > "$AWKD/.aidev/works/w/design.md"
# 全角スペース(U+3000)の字下げを混ぜる。POSIX の空白クラスは**ロケール依存**で、
# UTF-8 ロケールの gawk はこれを空白とみなし、バイト志向の mawk はみなさない
# （`[[:space:]]` のままだと、この行が実装 × ロケールの組でだけタスクになる）。
printf -- '- [ ] T1: t\n      AC: AC1、AC-I1\n      依存: なし\n\343\200\200- [ ] T2: 全角字下げ\n      AC: AC1\n      依存: なし\n' \
  > "$AWKD/.aidev/works/w/tasks.md"

AWK_IMPLS=""
for _a in awk gawk mawk busybox; do
  command -v "$_a" >/dev/null 2>&1 || continue
  if [ "$_a" = busybox ]; then busybox awk 'BEGIN{}' >/dev/null 2>&1 || continue; fi
  AWK_IMPLS="$AWK_IMPLS $_a"
done
printf 'awk 実装: %s\n' "${AWK_IMPLS# }"

AWK_REF=""; AWK_N=0
for _a in $AWK_IMPLS; do
  _bin=$(mktemp -d)
  if [ "$_a" = busybox ]; then printf '#!/bin/sh\nexec busybox awk "$@"\n' > "$_bin/awk"; chmod +x "$_bin/awk"
  else ln -sf "$(command -v "$_a")" "$_bin/awk"; fi
  # **ロケールも振る**。POSIX の空白・文字クラスはロケール依存なので、
  # 同じ awk でも LANG が違うと判定が変わりうる（C と UTF-8 の両方で同じであること）
  _out=$( ( cd "$AWKD" && PATH="$_bin:$PATH" LC_ALL=C "$AIDEV_SH" coverage --strict ) 2>&1 ); _rc=$?
  _outu=$( ( cd "$AWKD" && PATH="$_bin:$PATH" LC_ALL=C.UTF-8 "$AIDEV_SH" coverage --strict ) 2>&1 )
  assert_eq "$_outu" "$_out" "awk($_a): ロケール（C / C.UTF-8）で判定が変わらない"
  rm -rf "$_bin"
  AWK_N=$((AWK_N+1))
  if [ -z "$AWK_REF" ]; then
    AWK_REF="$_out"; AWK_REF_RC=$_rc; AWK_REF_NAME=$_a
    assert_contains "$_out" "ac=2" "awk($_a): 受け入れ基準を 2 件拾う（ACL は AC ではない）"
    assert_absent "$_out" "warning" "awk($_a): 警告を出さない（stderr が出力に混ざる）"
    assert_contains "$_out" "task_rows=1" "awk($_a): 全角スペース字下げをタスク行と認めない（ASCII の空白だけ）"
  else
    assert_eq "$_out" "$AWK_REF" "awk($_a): $AWK_REF_NAME と同じ判定（-v のエスケープ差で割れない）"
    assert_eq "$_rc" "$AWK_REF_RC" "awk($_a): $AWK_REF_NAME と同じ exit code"
  fi
done
if [ "$AWK_N" -lt 2 ]; then
  skip 2 "awk 実装が1つしか無いため実装間の突き合わせを省略（CI の ubuntu は gawk / 開発機は mawk のことが多い）"
fi
rm -rf "$AWKD"


echo "== 文書と CLI 表面の整合（lint-docs.sh）=="
# ハーネス自身の文書を機械で検査する層。このセッションで踏んだ欠陥の分類のうち、
# 「片方だけ直して食い違う」「CLI 表面の更新漏れ」「文書の冗長化」「予算の無い増加」を受け持つ。
# 出力はそのまま流し、合否だけをここで数える（詳細は lint 側が ok:/NG: で出す）
LINTOUT=$("$SELF/lint-docs.sh" 2>&1); LINTRC=$?
printf '%s\n' "$LINTOUT" | sed 's/^/  | /'
assert_eq "$LINTRC" "0" "lint-docs: 文書と CLI 表面が整合している"
# **検査が本当にその欠陥を捕まえるか**を、欠陥を一度戻して確かめる。
# L9 は「工程 SKILL の plan モード行に判定条件を写さない」を見る検査で、
# 外部レビューが提案した形（判定キーが本文に出たら WARN）では**今回の欠陥を捕まえられなかった**
# ——残っていた文言は `full` × `interactive` でキー名を 1 つも含んでいなかったため。値の側も見る
# **ハーネス本体は書き換えない**。初版は正典ファイルを in-place で汚して cp で戻していたが、
# 中断（Ctrl-C・タイムアウト・lint の異常終了）で**欠陥文言が残ったままになる**（実走が指摘）。
# skills ごと $TMP へ写して、その複製の中で欠陥を再現する
L9SRC=$(cd "$SELF/../../.." && pwd)
rm -rf "$TMP/l9skills"; cp -r "$L9SRC" "$TMP/l9skills"
L9GIT0=$(cd "$L9SRC" && git status --porcelain -- aidev-20-design/SKILL.md 2>/dev/null)
L9F=$TMP/l9skills/aidev-20-design/SKILL.md
L9LINT=$TMP/l9skills/aidev-docs/bin/test/lint-docs.sh
assert_eq "$("$L9LINT" >/dev/null 2>&1; echo $?)" "0" "lint L9: 複製そのままでは通る（土台の確認）"
# 実走が見つけた抜け穴を 1 つずつ塞いだので、**塞いだ形が本当に捕まるか**を全部見る。
# 見出しのゆれ・継続行・自然語・CLI フラグ綴り——どれか 1 つでも素通りすると、
# 検査は「在るのに効かない」状態になる（分類 G と同じ）
l9probe() { # 名前 置換後の本文
  printf '%s' "$2" > "$TMP/l9.to"
  python3 - "$L9F" "$L9SRC/aidev-20-design/SKILL.md" "$TMP/l9.to" <<'PYEOF'
import io,sys
tgt,orig,to=sys.argv[1],sys.argv[2],sys.argv[3]
s=io.open(orig,encoding='utf-8').read()
lines=s.split('\n')
for i,l in enumerate(lines):
    if 'plan モードへ入る' in l:
        j=i+1
        while j<len(lines) and lines[j].startswith('     '): j+=1
        lines[i:j]=io.open(to,encoding='utf-8').read().split('\n')
        break
io.open(tgt,'w',encoding='utf-8').write('\n'.join(lines))
PYEOF
  _n=$("$L9LINT" 2>&1 | grep -c 'NG: L9') || _n=0
  cp "$L9SRC/aidev-20-design/SKILL.md" "$L9F"
  assert_ne "$_n" "0" "lint L9: $1 を捕まえる"
}
l9probe "条件をそのまま写す" '   - 有力な案が複数あるなら、**`design.md` を書く前に plan モードへ入る**（`full` × `interactive` のみ）。'
l9probe "条件を継続行へ送る" '   - 有力な案が複数あるなら、**`design.md` を書く前に plan モードへ入る**。
     入るのは `full` × `interactive` のときだけ。'
l9probe "現行条件を自然語で写す" '   - 有力な案が複数あるなら、**plan モードへ入る**（その工程に承認者がいるときだけ）。'
l9probe "見出しの表記ゆれ" '   - 有力な案が複数あるなら、**planモードへ入る**（`full` × `interactive` のみ）。'
l9probe "英語表記" '   - 有力な案が複数あるなら、**plan mode へ入る**（`full` × `interactive` のみ）。'
l9probe "CLI フラグの綴り" '   - 有力な案が複数あるなら、**plan モードへ入る**（`--human-gates` に挙がっているときだけ）。'
# **H7（対象ファイル外へ写す）の probe が無かった**ので、「塞いだ」と書いてあるのに
# `DESIGN.md` と `aidev-docs/README.md` に届いていないことに気付けなかった（実走が実測）。
# 走査対象の端（実行時文書でない参照文書）を 1 つずつ突く
l9out() { # 名前 ファイル
  cp "$2" "$TMP/l9out.bak"
  printf '\nplan モードへ入るのは `full` × `interactive` のときだけ。\n' >> "$2"
  _n=$("$L9LINT" 2>&1 | grep -c 'NG: L9') || _n=0
  cp "$TMP/l9out.bak" "$2"
  assert_ne "$_n" "0" "lint L9: $1 への写しを捕まえる"
}
l9out "DESIGN.md" "$TMP/l9skills/aidev-docs/DESIGN.md"
l9out "aidev-docs/README.md" "$TMP/l9skills/aidev-docs/README.md"
l9out "protocol.md" "$TMP/l9skills/aidev-00-start/protocol.md"
l9out "util skill" "$TMP/l9skills/aidev-util-batch/SKILL.md"
l9out "bin/README.md" "$TMP/l9skills/aidev-docs/bin/README.md"
# **H8: 字下げした子の箇条書きへ条件を送る**。打ち切っていた頃は原理的に見えず、
# `DESIGN.md` の `  - **使う**:` 以下の列挙がまるごと素通りしていた（実走が実測）
cp "$TMP/l9skills/aidev-20-design/SKILL.md" "$TMP/l9h8.bak"
printf '\n- plan モードの扱い\n  - 入るのは `full` × `interactive` のときだけ。\n' \
  >> "$TMP/l9skills/aidev-20-design/SKILL.md"
assert_ne "$("$L9LINT" 2>&1 | grep -c 'NG: L9')" "0" \
  "lint L9: 字下げした子の箇条書きに送った条件を捕まえる"
cp "$TMP/l9h8.bak" "$TMP/l9skills/aidev-20-design/SKILL.md"
# **新条件の語彙**。改修のたびに PMKEY を足さないと「旧条件の写し」しか捕まらない
for _l9w in '入るのは、入力に既存コードが入る工程だけ。' \
            '入るのは、コード探索中の read-only 強制が要るときだけ。' \
            '入らない——主活動がユーザーへのヒアリングだから。' \
            '入るのは上流4工程だけ。'; do
  cp "$TMP/l9skills/aidev-20-design/SKILL.md" "$TMP/l9w.bak"
  printf '\nplan モードへ%s\n' "$_l9w" >> "$TMP/l9skills/aidev-20-design/SKILL.md"
  assert_ne "$("$L9LINT" 2>&1 | grep -c 'NG: L9')" "0" "lint L9: 新条件の語彙を捕まえる（$_l9w）"
  cp "$TMP/l9w.bak" "$TMP/l9skills/aidev-20-design/SKILL.md"
done
# **1 件の写しは「1 ファイル」と数える**。`runtime_docs` と SKILL のグロブが重なっていた頃は
# 同じファイルを 2 回走査し、1 件を「2 ファイル」と出していた
cp "$TMP/l9skills/aidev-20-design/SKILL.md" "$TMP/l9cnt.bak"
printf '\nplan モードへ入るのは `full` × `interactive` のときだけ。\n' >> "$TMP/l9skills/aidev-20-design/SKILL.md"
assert_contains "$("$L9LINT" 2>&1 | grep 'NG: L9')" "写しが 1 ファイル" \
  "lint L9: 同じファイルを二重に数えない"
cp "$TMP/l9cnt.bak" "$TMP/l9skills/aidev-20-design/SKILL.md"
assert_eq "$("$L9LINT" >/dev/null 2>&1; echo $?)" "0" "lint L9: 全て戻せば通る（複製を汚したままにしない）"
# **前後の差**で見る。絶対のクリーンさで見ていた頃は、**改修中（未コミット）だと必ず落ちた**
# ——テストが「作業ツリーは常にきれい」を前提にしていた
assert_eq "$(cd "$L9SRC" && git status --porcelain -- aidev-20-design/SKILL.md 2>/dev/null)" "$L9GIT0" \
  "lint L9: ハーネス本体を書き換えていない（前後で git status が変わらない）"

echo "== sh ⇔ ps1 パリティ =="
if [ -n "$PS_HOST" ]; then
  block_begin parity
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


  # doccheck のパリティ。**ps1 側は他のどのテストからも通らない**ので、ここが唯一の検査になる
  # （taskcheck を入れたときは ps1 の enum 検証が抜けていて、緑のまま気づかなかった）
  PDC=$(mktemp -d); mkdir -p "$PDC/.aidev/works"
  ( cd "$PDC" && "$AIDEV_SH" new pdc >/dev/null )
  PDCD="$PDC/.aidev/works/$(cat "$PDC/.aidev/current")"
  : > "$PDCD/design.md"
  ( cd "$PDC" && run_ps1 "$AIDEV_PS1" doccheck start design --mode delegated ) >/dev/null 2>&1
  assert_contains "$(tr -d '\r' < "$PDCD/metrics.yml")" "event: doccheck, metrics: { stage: start, phase: design" \
    "パリティ: ps1 doccheck start が同じ形のイベントを刻む"
  PDC_S=$( ( cd "$PDC" && "$AIDEV_SH" doccheck status --format tsv ) )
  PDC_P=$( ( cd "$PDC" && run_ps1 "$AIDEV_PS1" doccheck status --format tsv ) | tr -d '\r' )
  assert_eq "$PDC_S" "$PDC_P" "パリティ: doccheck status --format tsv"
  ( cd "$PDC" && run_ps1 "$AIDEV_PS1" doccheck start design --mode delegated ) >/dev/null 2>&1
  ( cd "$PDC" && run_ps1 "$AIDEV_PS1" doccheck start design --mode delegated ) >/dev/null 2>&1
  assert_eq "$?" "4" "パリティ: ps1 も maxDocCheckRounds で exit 4"
  ( cd "$PDC" && run_ps1 "$AIDEV_PS1" approve design ) >/dev/null 2>&1
  ( cd "$PDC" && run_ps1 "$AIDEV_PS1" doccheck report design --findings 0 ) >/dev/null 2>&1
  ( cd "$PDC" && run_ps1 "$AIDEV_PS1" approve design ) >/dev/null 2>&1
  assert_contains "$(tr -d '\r' < "$PDCD/metrics.yml")" "doc_check_rounds: 1" \
    "パリティ: ps1 の approve も上流の点検メトリクスを自動で刻む（report まで届いた分）"
  rm -rf "$PDC"

  # guard の plan モード促し。**ps1 側はここが唯一の検査**（sh 側のテストは ps1 を通らない）
  PGD=$(mktemp -d); mkdir -p "$PGD/.aidev/works"
  ( cd "$PGD" && "$AIDEV_SH" new pgd >/dev/null )
  PGDD="$PGD/.aidev/works/$(cat "$PGD/.aidev/current")"
  : > "$PGDD/requirements.md"
  PGD_S=$( ( cd "$PGD" && "$AIDEV_SH" guard design ) 2>&1 )
  PGD_P=$( ( cd "$PGD" && run_ps1 "$AIDEV_PS1" guard design ) 2>&1 | tr -d '\r' )
  assert_eq "$PGD_S" "$PGD_P" "パリティ: guard design（plan モードの促し）"
  assert_contains "$PGD_P" "plan モードへ入ってから" \
    "パリティ: ps1 guard も plan モードへ入るよう促す"
  # 条件（light / autonomous では出さない）も両実装で揃っていること
  ( cd "$PGD" && "$AIDEV_SH" new pgdl --light >/dev/null )
  : > "$PGD/.aidev/works/$(cat "$PGD/.aidev/current")/requirements.md"
  PGL_S=$( ( cd "$PGD" && "$AIDEV_SH" guard design ) 2>&1 )
  PGL_P=$( ( cd "$PGD" && run_ps1 "$AIDEV_PS1" guard design ) 2>&1 | tr -d '\r' )
  assert_eq "$PGL_S" "$PGL_P" "パリティ: guard design（light では促さない）"
  assert_eq "$(printf '%s' "$PGL_P" | grep -c 'plan モードへ入ってから')" "0" \
    "パリティ: ps1 も light では促さない"
  # 承認者の有無で見る（humanGates の部分自律）。sh 側と同じ判定になっていること
  ( cd "$PGD" && "$AIDEV_SH" new pgdh --mode autonomous --human-gates design >/dev/null )
  : > "$PGD/.aidev/works/$(cat "$PGD/.aidev/current")/requirements.md"
  PGH_S=$( ( cd "$PGD" && "$AIDEV_SH" guard design ) 2>&1 )
  PGH_P=$( ( cd "$PGD" && run_ps1 "$AIDEV_PS1" guard design ) 2>&1 | tr -d '\r' )
  assert_eq "$PGH_S" "$PGH_P" "パリティ: guard design（humanGates の部分自律）"
  assert_contains "$PGH_P" "plan モードへ入ってから" \
    "パリティ: ps1 も humanGates に挙がっていれば autonomous で促す"
  PGH2_S=$( ( cd "$PGD" && "$AIDEV_SH" guard architecture ) 2>&1 )
  PGH2_P=$( ( cd "$PGD" && run_ps1 "$AIDEV_PS1" guard architecture ) 2>&1 | tr -d '\r' )
  assert_eq "$PGH2_S" "$PGH2_P" "パリティ: guard architecture（humanGates に無い工程）"
  # **今回足した工程を ps1 側でも見る**。パリティ検査が `guard design` だけだった頃は、
  # `requirements` / `tasks` / subtask の分岐が ps1 で壊れても機械が通らなかった（実走が指摘）
  ( cd "$PGD" && "$AIDEV_SH" new pgd4 >/dev/null )
  PGD4=$PGD/.aidev/works/$(cat "$PGD/.aidev/current")
  : > "$PGD4/requirements.md"; : > "$PGD4/design.md"
  for _pgp in requirements research tasks coding review; do
    PGN_S=$( ( cd "$PGD" && "$AIDEV_SH" guard "$_pgp" ) 2>&1 )
    PGN_P=$( ( cd "$PGD" && run_ps1 "$AIDEV_PS1" guard "$_pgp" ) 2>&1 | tr -d '\r' )
    assert_eq "$PGN_S" "$PGN_P" "パリティ: guard $_pgp（促しの有無）"
  done
  # subtask の tasks は親が切り方を確定済み。sh / ps1 で同じく促さないこと
  ( cd "$PGD" && "$AIDEV_SH" new pgd5 --parent "$(basename "$PGD4")" >/dev/null ) 2>/dev/null || true
  PGD5=$PGD/.aidev/works/$(cat "$PGD/.aidev/current")
  if [ -d "$PGD5" ]; then
    : > "$PGD5/design.md" 2>/dev/null || true
    PGS_S=$( ( cd "$PGD" && "$AIDEV_SH" guard tasks ) 2>&1 )
    PGS_P=$( ( cd "$PGD" && run_ps1 "$AIDEV_PS1" guard tasks ) 2>&1 | tr -d '\r' )
    assert_eq "$PGS_S" "$PGS_P" "パリティ: guard tasks（subtask では促さない）"
  else
    assert_eq "1" "1" "パリティ: guard tasks（subtask 生成できず・skip 相当）"
  fi
  rm -rf "$PGD"

  # 他 PJ の retro（host）が見つけた 3 件の ps1 側。**ここが唯一の検査**（上のブロックと同じ理由）
  PDU=$(mktemp -d); mkdir -p "$PDU/.aidev/works"
  ( cd "$PDU" && "$AIDEV_SH" new pdu >/dev/null )
  PDUD="$PDU/.aidev/works/$(cat "$PDU/.aidev/current")"
  printf 'tasks\n' > "$PDUD/tasks.md"
  printf -- '- [ ] T1: x\n      AC: AC1\n' > "$PDUD/tasks.md"
  # ① tasks は tasks.md の 2 つを見る（tasks.md だけ直しても言う）
  ( cd "$PDU" && run_ps1 "$AIDEV_PS1" doccheck start tasks --mode delegated ) >/dev/null 2>&1
  printf -- '      対象: src/a.py\n' >> "$PDUD/tasks.md"
  PDU_R=$( ( cd "$PDU" && run_ps1 "$AIDEV_PS1" doccheck report tasks --findings 1 ) | tr -d '\r' )
  assert_contains "$PDU_R" "tasks.md が start 時点から変わっています" \
    "パリティ: ps1 doccheck report も tasks の tasks.md の変更を見る"
  # ② doccheck の未報告検知（status の note と verify の WARN）
  : > "$PDUD/design.md"
  ( cd "$PDU" && run_ps1 "$AIDEV_PS1" doccheck start design --mode delegated ) >/dev/null 2>&1
  PDU_S=$( ( cd "$PDU" && "$AIDEV_SH" doccheck status ) )
  PDU_P=$( ( cd "$PDU" && run_ps1 "$AIDEV_PS1" doccheck status ) | tr -d '\r' )
  assert_eq "$PDU_S" "$PDU_P" "パリティ: doccheck status（unreported 列と note）"
  assert_contains "$PDU_P" "report が無い start が 1 件あります（design）" \
    "パリティ: ps1 も doccheck の未報告を名指しする"
  PDU_VS=$( ( cd "$PDU" && "$AIDEV_SH" verify ) 2>&1 )
  PDU_VP=$( ( cd "$PDU" && run_ps1 "$AIDEV_PS1" verify ) 2>&1 | tr -d '\r' )
  assert_eq "$PDU_VS" "$PDU_VP" "パリティ: verify（doccheck の未報告 WARN）"
  # ③ 断念を decisions.md に残せば消える（両実装で同じ消え方をする）
  printf -- '- design: 形式不正が2回続いたので断念\n' > "$PDUD/decisions.md"
  PDU_S2=$( ( cd "$PDU" && "$AIDEV_SH" doccheck status ) )
  PDU_P2=$( ( cd "$PDU" && run_ps1 "$AIDEV_PS1" doccheck status ) | tr -d '\r' )
  assert_eq "$PDU_S2" "$PDU_P2" "パリティ: doccheck status（decisions.md で断念を認めたあと）"
  assert_eq "$(printf '%s' "$PDU_P2" | grep -c 'report が無い start')" "0" \
    "パリティ: ps1 も decisions.md に残した断念は名指ししない"
  rm -rf "$PDU"

  # coverage のパリティ（被覆率と gap の判定が OS で食い違うと、片方の環境でだけ穴が通る）
  PCOV=$(mktemp -d); mkdir -p "$PCOV/.aidev/backlog"
  ( cd "$PCOV" && "$AIDEV_SH" new pcov >/dev/null )
  PCW=$(cat "$PCOV/.aidev/current"); PCD="$PCOV/.aidev/works/$PCW"
  cat > "$PCD/requirements.md" <<'EOF'
- [ ] AC1: ひとつ
- [ ] AC2: ふたつ
- [ ] AC-I1 開く / 閉じる: どう
EOF
  cat > "$PCD/design.md" <<'EOF'
- AC1: a
EOF
  cat > "$PCD/tasks.md" <<'EOF'
- [ ] T1: ひとつめ
      依存: なし
      AC: AC1、AC-I1
- [x] T2: ふたつめ
      依存: T1, T9
      AC: AC7
- [ ] T3: みっつめ
      依存: T4
- [ ] T4: よっつめ
      依存: T3
      AC: なし
EOF
  for pf in table tsv; do
    PC_SH=$( ( cd "$PCOV" && "$AIDEV_SH" coverage --format "$pf" ) 2>&1 ); PC_SH_RC=$?
    PC_PS_RAW=$( ( cd "$PCOV" && run_ps1 "$AIDEV_PS1" coverage --format "$pf" ) 2>&1 ); PC_PS_RC=$?
    PC_PS=$(printf '%s' "$PC_PS_RAW" | tr -d '\r')
    assert_eq "$PC_SH" "$PC_PS" "パリティ: coverage --format $pf（出力）"
    assert_eq "$PC_SH_RC" "$PC_PS_RC" "パリティ: coverage --format $pf（exit code）"
  done
  PC_SH=$( ( cd "$PCOV" && "$AIDEV_SH" coverage --strict ) 2>&1 ); PC_SH_RC=$?
  PC_PS_RAW=$( ( cd "$PCOV" && run_ps1 "$AIDEV_PS1" coverage --strict ) 2>&1 ); PC_PS_RC=$?
  PC_PS=$(printf '%s' "$PC_PS_RAW" | tr -d '\r')
  assert_eq "$PC_SH" "$PC_PS" "パリティ: coverage --strict（出力）"
  assert_eq "$PC_SH_RC" "$PC_PS_RC" "パリティ: coverage --strict（exit code は 4）"
  # 監査で割れていた経路のパリティ（明示キーの判定・家族単位の smoke・上限値の端・help）
  PAU=$(mktemp -d); PAU2=$(mktemp -d)
  for pimpl in sh ps1; do
    if [ "$pimpl" = sh ]; then PA=$PAU; else PA=$PAU2; fi
    mkdir -p "$PA/.aidev/backlog"
    par() { if [ "$pimpl" = sh ]; then ( cd "$PA" && "$AIDEV_SH" "$@" >/dev/null 2>&1 ); \
            else ( cd "$PA" && run_ps1 "$AIDEV_PS1" "$@" >/dev/null 2>&1 ); fi; }
    par new fam
    PAW=$(tr -d '\r' < "$PA/.aidev/current"); PAD="$PA/.aidev/works/$PAW"
    for f in design tasks review test-result; do : > "$PAD/$f.md"; done
    printf -- '- [ ] AC1: a\n- [ ] AC2: b\n' > "$PAD/requirements.md"
    printf -- '- [ ] T1: x\n      AC: AC1, AC2\n      依存: なし\n' > "$PAD/tasks.md"
    par new 01-a --parent "$PAW"
    printf -- '- [ ] T1: y\n      AC: AC1, AC2\n      依存: なし\n' > "$PAD/01-a/tasks.md"
    # `true` は cmd.exe の組み込みに無く、PATH に true.exe があるかで結果が変わる。
    # パリティで**実行される**コマンドは sh / cmd.exe のどちらでも同じ意味のものに限る
    printf 'smokeCommand: exit 0\n' > "$PA/.aidev/config.yml"
    par use "$PAW/01-a"; par approve tasks            # 子: 刻まない / smoke は親へ
    par smoke
    par use "$PAW"
    par approve tasks "note=see ac_total=5"           # 値の中の ac_total= は明示指定ではない
    par approve tasks ac_total=9                      # 先頭一致なら尊重
    par approve review
    for p in requirements design coding test deliver; do par approve "$p"; done
  done
  PAM_SH=$(sed 's/ts: [^,]*, //' "$PAU/.aidev/works"/*/metrics.yml)
  PAM_PS=$(tr -d '\r' < "$(ls -d "$PAU2/.aidev/works"/*/metrics.yml)" | sed 's/ts: [^,]*, //')
  assert_eq "$PAM_SH" "$PAM_PS" "パリティ: 明示キーの判定と家族単位の smoke（親の metrics）"
  PAS_SH=$(sed 's/ts: [^,]*, //' "$PAU/.aidev/works"/*/01-a/metrics.yml)
  PAS_PS=$(tr -d '\r' < "$(ls -d "$PAU2/.aidev/works"/*/01-a/metrics.yml)" | sed 's/ts: [^,]*, //')
  assert_eq "$PAS_SH" "$PAS_PS" "パリティ: subtask の metrics（被覆も smoke も刻まれない）"
  for pargs in "metrics --all --format tsv" "verify" "smoke"; do
    # shellcheck disable=SC2086
    PA_SH=$( ( cd "$PAU"  && "$AIDEV_SH" $pargs ) 2>&1 | sed 's/2[0-9-]*T[0-9:]*Z//g' ); PA_SH_RC=$?
    # shellcheck disable=SC2086
    PA_PS_RAW=$( ( cd "$PAU2" && run_ps1 "$AIDEV_PS1" $pargs ) 2>&1 ); PA_PS_RC=$?
    PA_PS=$(printf '%s' "$PA_PS_RAW" | tr -d '\r' | sed 's/2[0-9-]*T[0-9:]*Z//g')
    assert_eq "$PA_SH" "$PA_PS" "パリティ: $pargs（家族単位の修正後）"
    assert_eq "$PA_SH_RC" "$PA_PS_RC" "パリティ: $pargs（exit code）"
  done
  # 上限値の端（maxDebugRounds: 0 -> 1）
  printf 'maxDebugRounds: 0\n' > "$PAU/.aidev/config.yml"; printf 'maxDebugRounds: 0\n' > "$PAU2/.aidev/config.yml"
  PE_SH=$( ( cd "$PAU"  && "$AIDEV_SH" debug start --phase coding ) 2>&1 ); PE_SH_RC=$?
  PE_PS_RAW=$( ( cd "$PAU2" && run_ps1 "$AIDEV_PS1" debug start --phase coding ) 2>&1 ); PE_PS_RC=$?
  PE_PS=$(printf '%s' "$PE_PS_RAW" | tr -d '\r')
  assert_eq "$PE_SH" "$PE_PS" "パリティ: maxDebugRounds: 0 の切り上げ"
  assert_eq "$PE_SH_RC" "$PE_PS_RC" "パリティ: maxDebugRounds: 0（exit code）"
  # ps1 の help に新コマンドが載っていること（sh は冒頭コメントを流すので元から載る）
  PH_PS=$( ( cd "$PAU2" && run_ps1 "$AIDEV_PS1" help ) 2>&1 | tr -d '\r' )
  for pcmd in coverage smoke debug "worktree rm"; do
    assert_contains "$PH_PS" "$pcmd" "ps1 help: $pcmd が載っている"
  done
  rm -rf "$PAU" "$PAU2"

  # debug のパリティ（記録の中身・上限の効き方・decisions.md の生成物）
  PDB=$(mktemp -d); PDB2=$(mktemp -d)
  for pimpl in sh ps1; do
    if [ "$pimpl" = sh ]; then PD=$PDB; else PD=$PDB2; fi
    mkdir -p "$PD/.aidev/backlog"
    pdr() { if [ "$pimpl" = sh ]; then ( cd "$PD" && "$AIDEV_SH" "$@" >/dev/null ); \
            else ( cd "$PD" && run_ps1 "$AIDEV_PS1" "$@" >/dev/null ); fi; }
    pdr new stuck
    PDW=$(tr -d '\r' < "$PD/.aidev/current"); PDD="$PD/.aidev/works/$PDW"
    for f in design tasks review test-result; do : > "$PDD/$f.md"; done
    printf -- '- [ ] AC1: a\n' > "$PDD/requirements.md"
    printf -- '- [ ] T1: x\n      AC: AC1\n      依存: なし\n' > "$PDD/tasks.md"
    for p in requirements design tasks; do pdr approve "$p"; done
    for i in 1 2 3; do pdr event coding sent_back; done
    pdr debug start --phase coding
    pdr debug report --phase coding --root-cause "save() が例外を握りつぶしていた" --category logic --next-action retry --confidence high --fix-tasks "os.replace の前に再送出"
    pdr debug start --phase coding
    pdr debug report --phase coding --root-cause "外部 API の仕様が違う" --category external --next-action stop_for_human
    for p in coding test review deliver; do pdr approve "$p"; done
  done
  PDM_SH=$(sed 's/ts: [^,]*, //' "$PDB/.aidev/works"/*/metrics.yml)
  PDM_PS=$(tr -d '\r' < "$(ls -d "$PDB2/.aidev/works"/*/metrics.yml)" | sed 's/ts: [^,]*, //')
  assert_eq "$PDM_SH" "$PDM_PS" "パリティ: debug が刻む metrics（stage/round/category/next_action）"
  PDD_SH=$(sed 's/・[0-9TZ:-]*）/）/' "$PDB/.aidev/works"/*/decisions.md)
  PDD_PS=$(tr -d '\r' < "$(ls -d "$PDB2/.aidev/works"/*/decisions.md)" | sed 's/・[0-9TZ:-]*）/）/')
  assert_eq "$PDD_SH" "$PDD_PS" "パリティ: debug report が書く decisions.md"
  for pargs in "debug status --format tsv" "debug" "debug start --phase coding" "verify"; do
    # shellcheck disable=SC2086
    PDO_SH=$( ( cd "$PDB"  && "$AIDEV_SH" $pargs ) 2>&1 ); PDO_SH_RC=$?
    # shellcheck disable=SC2086
    PDO_PS_RAW=$( ( cd "$PDB2" && run_ps1 "$AIDEV_PS1" $pargs ) 2>&1 ); PDO_PS_RC=$?
    PDO_PS=$(printf '%s' "$PDO_PS_RAW" | tr -d '\r')
    assert_eq "$PDO_SH" "$PDO_PS" "パリティ: $pargs（出力）"
    assert_eq "$PDO_SH_RC" "$PDO_PS_RC" "パリティ: $pargs（exit code）"
  done
  # 入口ゲート（必須・列挙値）のパリティ
  for pbad in "--root-cause x --category logic" "--root-cause x --category bogus --next-action retry" "--root-cause x --category logic --next-action bogus"; do
    # shellcheck disable=SC2086
    PB_SH=$( ( cd "$PDB"  && "$AIDEV_SH" debug report --phase coding $pbad ) 2>&1 ); PB_SH_RC=$?
    # shellcheck disable=SC2086
    PB_PS_RAW=$( ( cd "$PDB2" && run_ps1 "$AIDEV_PS1" debug report --phase coding $pbad ) 2>&1 ); PB_PS_RC=$?
    PB_PS=$(printf '%s' "$PB_PS_RAW" | tr -d '\r')
    assert_eq "$PB_SH" "$PB_PS" "パリティ: debug report の入口ゲート（$pbad）"
    assert_eq "$PB_SH_RC" "$PB_PS_RC" "パリティ: debug report の入口ゲート exit（$pbad）"
  done
  # sent_back の上限通知
  PN_SH=$( ( cd "$PDB"  && "$AIDEV_SH" event review sent_back ) 2>&1 )
  PN_PS=$( ( cd "$PDB2" && run_ps1 "$AIDEV_PS1" event review sent_back ) 2>&1 | tr -d '\r' )
  assert_eq "$PN_SH" "$PN_PS" "パリティ: event sent_back（上限前は促さない）"
  rm -rf "$PDB" "$PDB2"

  # smoke のパリティ（未設定・none・成功・失敗・doctor の PJ 単位 1 行）
  PSM=$(mktemp -d); mkdir -p "$PSM/.aidev/backlog"
  ( cd "$PSM" && "$AIDEV_SH" new pboot >/dev/null )
  for scase in unset none pass fail; do
    case "$scase" in
      unset) rm -f "$PSM/.aidev/config.yml" ;;
      none)  printf 'smokeCommand: none\n' > "$PSM/.aidev/config.yml" ;;
      # **シェルに依存しないコマンドを使う**。smoke は実行シェルが OS で変わる設計
      # （POSIX=`sh -c` / Windows=`cmd.exe /c`）なので、両者で意味が変わるコマンドを
      # 置くと出力が一致しない——`echo "x"` は sh がクォートを外し、cmd.exe は外さない。
      # 出力一致の契約は **CLI が出す行**についてのもの（bin/README の「素通し設計の但し書き」）。
      pass)  printf 'smokeCommand: echo booted-v0.1\n' > "$PSM/.aidev/config.yml" ;;
      fail)  printf 'smokeCommand: exit 3\n' > "$PSM/.aidev/config.yml" ;;
    esac
    SM_SH=$( ( cd "$PSM" && "$AIDEV_SH" smoke ) 2>&1 ); SM_SH_RC=$?
    SM_PS_RAW=$( ( cd "$PSM" && run_ps1 "$AIDEV_PS1" smoke ) 2>&1 ); SM_PS_RC=$?
    SM_PS=$(printf '%s' "$SM_PS_RAW" | tr -d '\r')
    assert_eq "$SM_SH" "$SM_PS" "パリティ: smoke $scase（出力）"
    assert_eq "$SM_SH_RC" "$SM_PS_RC" "パリティ: smoke $scase（exit code）"
  done
  # doctor の smoke 節（未設定 / none / 設定済み）
  for scase in unset none set; do
    case "$scase" in
      unset) rm -f "$PSM/.aidev/config.yml" ;;
      none)  printf 'smokeCommand: none\n' > "$PSM/.aidev/config.yml" ;;
      set)   printf 'smokeCommand: exit 0\n' > "$PSM/.aidev/config.yml" ;;
    esac
    SD_SH=$( ( cd "$PSM" && "$AIDEV_SH" doctor ) 2>&1 | sed -n '/^smoke:/,$p' )
    SD_PS=$( ( cd "$PSM" && run_ps1 "$AIDEV_PS1" doctor ) 2>&1 | tr -d '\r' | sed -n '/^smoke:/,$p' )
    assert_eq "$SD_SH" "$SD_PS" "パリティ: doctor の smoke 節 $scase"
  done
  # verify の schema 7（smoke fail のまま deliver）
  PSMW=$(cat "$PSM/.aidev/current"); PSMD="$PSM/.aidev/works/$PSMW"
  for f in requirements design tasks tasks review test-result; do : > "$PSMD/$f.md"; done
  printf -- '- [ ] AC1: 起動する\n' > "$PSMD/requirements.md"
  printf -- '- [ ] T1: 起動経路\n      AC: AC1\n      依存: なし\n' > "$PSMD/tasks.md"
  printf 'smokeCommand: exit 1\n' > "$PSM/.aidev/config.yml"
  ( cd "$PSM" && "$AIDEV_SH" smoke >/dev/null 2>&1 ) || true
  for p in requirements design tasks coding test review deliver; do ( cd "$PSM" && "$AIDEV_SH" approve "$p" >/dev/null ); done
  SV_SH=$( ( cd "$PSM" && "$AIDEV_SH" verify ) 2>&1 ); SV_SH_RC=$?
  SV_PS_RAW=$( ( cd "$PSM" && run_ps1 "$AIDEV_PS1" verify ) 2>&1 ); SV_PS_RC=$?
  SV_PS=$(printf '%s' "$SV_PS_RAW" | tr -d '\r')
  assert_eq "$SV_SH" "$SV_PS" "パリティ: verify の schema 7（起動確認の記録）出力"
  assert_eq "$SV_SH_RC" "$SV_PS_RC" "パリティ: verify の schema 7（exit code）"
  rm -rf "$PSM"

  # 被覆の刻印のパリティ（刻む工程・キーの並び・値、および metrics の ac/ac_drift）。
  # ここが割れると、同じ work を OS 違いで回しただけで insights の分母が変わる。
  PMS=$(mktemp -d); PMS2=$(mktemp -d)
  for pimpl in sh ps1; do
    if [ "$pimpl" = sh ]; then PD=$PMS; else PD=$PMS2; fi
    mkdir -p "$PD/.aidev/backlog"
    pr() { if [ "$pimpl" = sh ]; then ( cd "$PD" && "$AIDEV_SH" "$@" >/dev/null ); \
           else ( cd "$PD" && run_ps1 "$AIDEV_PS1" "$@" >/dev/null ); fi; }
    pr new pm
    PW=$(cat "$PD/.aidev/current" | tr -d '\r'); PDD="$PD/.aidev/works/$PW"
    printf -- '- [ ] AC1: a\n- [ ] AC2: b\n- [ ] AC3: c\n' > "$PDD/requirements.md"
    printf -- '- AC1: x\n- AC2: y\n' > "$PDD/design.md"
    printf -- '- [ ] T1: a\n      AC: AC1\n      依存: なし\n- [ ] T2: b\n      AC: AC2, AC3\n      依存: なし\n- [ ] T3: 下準備\n      AC: なし\n      依存: なし\n' > "$PDD/tasks.md"
    pr approve requirements; pr approve design; pr approve tasks tasks_planned=3 tasks_anchored=3
    printf -- '- [ ] T4: 追加\n      依存: なし\n' >> "$PDD/tasks.md"
    pr approve coding tasks_done=4; pr approve test passed=9 failed=0; pr approve review must=0 should=0 nit=0
  done
  PM_SH=$(sed 's/ts: [^,]*, //' "$PMS/.aidev/works"/*/metrics.yml)
  PM_PS=$(tr -d '\r' < "$(ls -d "$PMS2/.aidev/works"/*/metrics.yml)" | sed 's/ts: [^,]*, //')
  assert_eq "$PM_SH" "$PM_PS" "パリティ: approve が刻む被覆メトリクス（キーの並びと値）"
  PMM_SH=$( ( cd "$PMS"  && "$AIDEV_SH" metrics --format tsv ) 2>&1 | cut -f2- )
  PMM_PS=$( ( cd "$PMS2" && run_ps1 "$AIDEV_PS1" metrics --format tsv ) 2>&1 | tr -d '\r' | cut -f2- )
  assert_eq "$PMM_SH" "$PMM_PS" "パリティ: metrics の ac / ac_drift 列"
  rm -rf "$PMS" "$PMS2"

  # 入力の揺れのパリティ。**ここが割れると同じ work が片方の OS でだけ deliver できる**。
  # sh は awk/sed のバイト単位の角括弧式、ps1 は .NET の Unicode 正規表現＋BOM/CRLF 自動除去、
  # という素の挙動差がそのまま判定差になるので、素の挙動に任せず両方を明示的に揃えてある。
  PCE=$(mktemp -d); mkdir -p "$PCE/.aidev/backlog"
  ( cd "$PCE" && "$AIDEV_SH" new pedge >/dev/null )
  PCED="$PCE/.aidev/works/$(cat "$PCE/.aidev/current")"
  # 1=CRLF / 2=BOM / 3=全角スペース字下げ / 4=NBSP / 5=グロブ文字 / 6=ID 文法の境界
  for pcase in 1 2 3 4 5 6; do
    case "$pcase" in
      1) printf -- '- [ ] AC1: a\r\n- [ ] AC2: b\r\n' > "$PCED/requirements.md"
         printf -- '- [ ] T1: x\r\n      AC: AC1\r\n      依存: なし\r\n- [ ] T2: y\r\n      AC: AC2\r\n      依存: T1\r\n' > "$PCED/tasks.md" ;;
      2) printf '\357\273\277- [ ] AC1: a\n' > "$PCED/requirements.md"
         printf '\357\273\277- [ ] T1: x\n      AC: AC1\n      依存: なし\n' > "$PCED/tasks.md" ;;
      3) printf -- '- [ ] AC1: a\n- [ ] AC2: b\n' > "$PCED/requirements.md"
         printf -- '- [ ] T1: ひとつめ\n\343\200\200\343\200\200AC: AC1\n      依存: なし\n\343\200\200- [ ] T2: 全角字下げ\n      AC: AC2\n      依存: T1\n' > "$PCED/tasks.md" ;;
      4) printf -- '- [ ] AC1: a\n\302\240- [ ] AC2: NBSP\n' > "$PCED/requirements.md"
         printf -- '- [ ] T1: x\n      AC: AC1\n      依存: なし\n' > "$PCED/tasks.md" ;;
      5) printf -- '- [ ] AC1: a\n' > "$PCED/requirements.md"
         printf -- '- [ ] T1: g\n      AC: *\n      依存: なし\n' > "$PCED/tasks.md" ;;
      6) printf -- '- [ ] AC1: a\n- [ ] AC-I1 開く / 閉じる: どう\n- [ ] ACL の設定\n' > "$PCED/requirements.md"
         printf -- '- AC-I1 開く / 閉じる: こう\n' > "$PCED/design.md"
         printf -- '- [ ] T1-1: 枝\n      AC: AC1、AC-I1\n      依存: T1-1\n- [ ] T1-1: dup\n      AC: \n      依存: なし\n' > "$PCED/tasks.md" ;;
    esac
    PE_SH=$( ( cd "$PCE" && "$AIDEV_SH" coverage --strict ) 2>&1 ); PE_SH_RC=$?
    PE_PS_RAW=$( ( cd "$PCE" && run_ps1 "$AIDEV_PS1" coverage --strict ) 2>&1 ); PE_PS_RC=$?
    PE_PS=$(printf '%s' "$PE_PS_RAW" | tr -d '\r')
    assert_eq "$PE_SH" "$PE_PS" "パリティ: coverage 入力の揺れ case $pcase（出力）"
    assert_eq "$PE_SH_RC" "$PE_PS_RC" "パリティ: coverage 入力の揺れ case $pcase（exit code）"
  done
  rm -rf "$PCE"

  # 分割 work（家族単位の被覆・未 tasks の subtask がある間の扱い）
  PCS=$(mktemp -d); mkdir -p "$PCS/.aidev/backlog"
  ( cd "$PCS" && "$AIDEV_SH" new big >/dev/null ); PCSP=$(cat "$PCS/.aidev/current")
  printf -- '- [ ] AC1: a\n- [ ] AC2: b\n' > "$PCS/.aidev/works/$PCSP/requirements.md"
  ( cd "$PCS" && "$AIDEV_SH" new 01-a --parent "$PCSP" >/dev/null )
  ( cd "$PCS" && "$AIDEV_SH" new 02-b --parent "$PCSP" >/dev/null )
  printf -- '- [ ] T1: a\n      AC: AC1\n      依存: なし\n' > "$PCS/.aidev/works/$PCSP/01-a/tasks.md"
  for psub in "$PCSP" "$PCSP/01-a"; do
    PS_SH=$( ( cd "$PCS" && "$AIDEV_SH" coverage --strict "$psub" ) 2>&1 ); PS_SH_RC=$?
    PS_PS_RAW=$( ( cd "$PCS" && run_ps1 "$AIDEV_PS1" coverage --strict "$psub" ) 2>&1 ); PS_PS_RC=$?
    PS_PS=$(printf '%s' "$PS_PS_RAW" | tr -d '\r')
    assert_eq "$PS_SH" "$PS_PS" "パリティ: coverage 分割 work $psub（出力）"
    assert_eq "$PS_SH_RC" "$PS_PS_RC" "パリティ: coverage 分割 work $psub（exit code）"
  done
  PSV_SH=$( ( cd "$PCS" && "$AIDEV_SH" verify "$PCSP" ) 2>&1 ); PSV_SH_RC=$?
  PSV_PS_RAW=$( ( cd "$PCS" && run_ps1 "$AIDEV_PS1" verify "$PCSP" ) 2>&1 ); PSV_PS_RC=$?
  PSV_PS=$(printf '%s' "$PSV_PS_RAW" | tr -d '\r')
  assert_eq "$PSV_SH" "$PSV_PS" "パリティ: verify の分割 work（被覆を根でだけ報告する）"
  assert_eq "$PSV_SH_RC" "$PSV_PS_RC" "パリティ: verify の分割 work（exit code）"
  rm -rf "$PCS"

  # verify 側の連動（struct=FAIL / cover=WARN / test-result.md）もそろって動くこと
  for f in tasks review; do : > "$PCD/$f.md"; done
  for ph in requirements design tasks coding test; do ( cd "$PCOV" && "$AIDEV_SH" approve "$ph" >/dev/null ); done
  ( cd "$PCOV" && "$AIDEV_SH" event test sent_back >/dev/null )
  PV_SH=$( ( cd "$PCOV" && "$AIDEV_SH" verify ) 2>&1 ); PV_SH_RC=$?
  PV_PS_RAW=$( ( cd "$PCOV" && run_ps1 "$AIDEV_PS1" verify ) 2>&1 ); PV_PS_RC=$?
  PV_PS=$(printf '%s' "$PV_PS_RAW" | tr -d '\r')
  assert_eq "$PV_SH" "$PV_PS" "パリティ: verify の schema 6 検査（出力）"
  assert_eq "$PV_SH_RC" "$PV_PS_RC" "パリティ: verify の schema 6 検査（exit code）"
  rm -rf "$PCOV"

  # convention のパリティ（条項の一生が OS で食い違うと、片方の環境だけ二重管理が起きる）
  PCV=$(mktemp -d); mkdir -p "$PCV/.aidev/works" "$PCV/docs"
  printf '# std\n' > "$PCV/docs/std.md"
  mkdir -p "$PCV/.aidev/works/20200101-w1"
  printf 'schema: 4\nslug: w1\ncurrent: requirements\napproved: []\n' > "$PCV/.aidev/works/20200101-w1/state.yml"
  printf 'events:\n  - { ts: 2020-01-01T01:00:00Z, phase: requirements, event: start }\n' \
    > "$PCV/.aidev/works/20200101-w1/metrics.yml"

  # sh 側で一生を進め、同じ操作を ps1 側でも行って生成物を突き合わせる
  ( cd "$PCV" && "$AIDEV_SH" convention new sh-side --hypothesis "h1" --baseline "b" --verify-after 1 >/dev/null )
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention new ps-side --hypothesis "h1" --baseline "b" --verify-after 1 >/dev/null )
  CP_SH=$(sed 's/^introduced: .*/introduced: X/' "$PCV/.aidev/conventions/sh-side.md")
  CP_PS=$(tr -d '\r' < "$PCV/.aidev/conventions/ps-side.md" | sed 's/^introduced: .*/introduced: X/; s/^convention: ps-side/convention: sh-side/; s/^# ps-side/# sh-side/')
  assert_eq "$CP_SH" "$CP_PS" "パリティ: convention new の生成ファイルが一致"

  CS_SH=$( ( cd "$PCV" && "$AIDEV_SH" convention status --format tsv ) 2>&1 )
  CS_PS=$( ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention status --format tsv ) 2>&1 | tr -d '\r' )
  assert_eq "$CS_SH" "$CS_PS" "パリティ: convention status（母集団の数え方が一致）"

  CD_SH=$( ( cd "$PCV" && "$AIDEV_SH" doctor ) 2>&1 | sed -n '/^convention:/,$p' )
  CD_PS=$( ( cd "$PCV" && run_ps1 "$AIDEV_PS1" doctor ) 2>&1 | tr -d '\r' | sed -n '/^convention:/,$p' )
  assert_eq "$CD_SH" "$CD_PS" "パリティ: doctor の条項検査（未判定の催促が一致）"

  # 出口ゲートのパリティ（片方だけ緩いと、その OS でだけ揃う前の判定が通る）
  ( cd "$PCV" && "$AIDEV_SH" convention confirm sh-side --result r >/dev/null 2>&1 ); GG_SH=$?
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention confirm ps-side --result r >/dev/null 2>&1 ); GG_PS=$?
  assert_eq "$GG_SH/$GG_PS" "1/1" "パリティ: 母集団が揃う前の confirm は両実装とも弾く"
  ( cd "$PCV" && "$AIDEV_SH" convention confirm sh-side --result r --force >/dev/null )
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention confirm ps-side --result r --force >/dev/null )
  ( cd "$PCV" && "$AIDEV_SH" convention promote sh-side --to docs/std.md#a >/dev/null )
  ( cd "$PCV" && run_ps1 "$AIDEV_PS1" convention promote ps-side --to docs/std.md#a >/dev/null )
  CT_SH=$(sed 's/^introduced: .*/introduced: X/; s/^promoted_at: .*/promoted_at: X/' "$PCV/.aidev/conventions/archive/sh-side.md")
  CT_PS=$(tr -d '\r' < "$PCV/.aidev/conventions/archive/ps-side.md" | sed 's/^introduced: .*/introduced: X/; s/^promoted_at: .*/promoted_at: X/; s/^convention: ps-side/convention: sh-side/')
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
  PGD=$(mktemp -d); mkdir -p "$PGD/.aidev/works" "$PGD/.aidev/conventions"
  printf '# tgt\n' > "$PGD/tgt.md"
  printf '# README\n\n消えてはいけない。\n' > "$PGD/.aidev/conventions/README.md"
  # 期待値は手で書かず**実行前のサイズ**を採る（バイト数を直書きすると、本文を1文字直しただけで
  # 「テストを通すために期待値を書き換える」形になり、0バイト化の回帰を守れなくなる）
  PGD_SZ0=$(wc -c < "$PGD/.aidev/conventions/README.md")
  ( cd "$PGD" && "$AIDEV_SH" convention promote README --to 'tgt.md#x' >/dev/null 2>&1 ); GS=$?
  ( cd "$PGD" && run_ps1 "$AIDEV_PS1" convention promote README --to 'tgt.md#x' >/dev/null 2>&1 ); GP=$?
  assert_eq "$GS" "$GP" "パリティ: frontmatter 無しを弾く exit code"
  assert_eq "$(wc -c < "$PGD/.aidev/conventions/README.md")" "$PGD_SZ0" "パリティ: どちらの実装でも本文が無傷"
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
  printf 'events:\n  - { ts: %sT23:59:59Z, phase: coding, event: start, metrics: { defects: 3 } }\n' \
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
  for p in requirements design tasks coding test review; do
    ( cd "$PRD" && "$AIDEV_SH" event "$p" start >/dev/null; cd "$PRD" && "$AIDEV_SH" approve "$p" >/dev/null )
  done
  : > "$PRD/.aidev/works/$PAW/review.md"
  ( cd "$PRD" && "$AIDEV_SH" event deliver start >/dev/null )
  RA_SH=$( ( cd "$PRD" && "$AIDEV_SH" approve deliver files_changed=1 ) 2>&1 )
  RA_PS=$( ( cd "$PRD" && run_ps1 "$AIDEV_PS1" approve deliver files_changed=1 ) 2>&1 | tr -d '\r' )
  # 注意: これは sh が着地させた work を ps1 が**再承認**する形なので、検査しているのは
  # 「冪等性」であって初回着地の副作用ではない。harnessRevDelivered の刻印など初回だけの
  # 副作用は、ps1 が自分で着地させる「ps1 側の刻印と検知」ブロックで見ている
  assert_eq "$RA_SH" "$RA_PS" "パリティ: approve deliver の再承認が冪等（初回着地は別ブロックで検査）"
  # 母集団メンバー一覧のパリティ（subtask の review.md も親に合算する）
  mkdir -p "$PRD/.aidev/works/$PAW/01-s"
  # 指摘行（`- [` 始まり）だけを数える。本文中の言及を数えると、「この条項の指摘は 0 件だった」と
  # 書いた行が 1 件として計上される（実走で実際に起きた）。`!` 付きは違反として別に数える
  { printf -- '- [must][conv:rc!] 違反1\n'
    printf -- '- [nit][conv:rc] 関係するが違反ではない指摘\n'
    printf -- '本文: 条項 [conv:rc] の指摘は 0 件だった（この行は数えない）\n'; } > "$PRD/.aidev/works/$PAW/review.md"
  printf -- '- [should][conv:rc!] 子の違反\n' > "$PRD/.aidev/works/$PAW/01-s/review.md"
  MB_SH=$( ( cd "$PRD" && "$AIDEV_SH" convention status --members rc --format tsv ) 2>&1 )
  MB_PS=$( ( cd "$PRD" && run_ps1 "$AIDEV_PS1" convention status --members rc --format tsv ) 2>&1 | tr -d '\r' )
  assert_eq "$MB_SH" "$MB_PS" "パリティ: convention status --members（母集団の work とタグ件数）"
  assert_contains "$MB_SH" "members-summary: id=rc pop=1 conv_tags=3 violations=2" \
    "members: 指摘行のタグだけ数え、違反(!)を別に出す（subtask も親に合算）"
  assert_contains "$MB_SH" "note: scope 未宣言" "members: scope が無ければ判定前に知らせる"
  rm -rf "$PRD"
  # --- 引数の解釈のパリティ ---
  # PowerShell の switch は既定で**大文字小文字を区別しない**ので、放っておくと Windows でだけ
  # `aidev NEW x` や `--MODE` が通る。同じスクリプトが OS で違う解釈をするのが一番まずい。
  PAR=$(mktemp -d); mkdir -p "$PAR/.aidev/works"
  for bad in "NEW x" "new x --MODE interactive" "New x"; do
    # shellcheck disable=SC2086
    ( cd "$PAR" && "$AIDEV_SH" $bad >/dev/null 2>&1 ); AS=$?
    # shellcheck disable=SC2086
    ( cd "$PAR" && run_ps1 "$AIDEV_PS1" $bad >/dev/null 2>&1 ); AP=$?
    assert_eq "$AS" "$AP" "パリティ: 大文字小文字を区別する（[$bad]）"
    # 「一致」だけだと、両方が大小を無視するようになっても通る。拒否そのものを要求する
    assert_eq "$AS" "1" "大文字のコマンド／オプションは拒否する（[$bad]）"
  done
  # オプションの値が欠けたとき。sh は素で書くと shift の内部エラー(rc=2)、ps1 は $null で素通り。
  # どちらも使い方エラー＝die(rc=1) に揃える
  for miss in "new x --mode" "convention new c --hypothesis" "backlog new b --kind"; do
    # shellcheck disable=SC2086
    MS=$( ( cd "$PAR" && "$AIDEV_SH" $miss ) 2>&1 ); MSC=$?
    # shellcheck disable=SC2086
    MP=$( ( cd "$PAR" && run_ps1 "$AIDEV_PS1" $miss ) 2>&1 ); MPC=$?
    MP=$(printf '%s' "$MP" | tr -d '\r')
    assert_eq "$MSC" "$MPC" "パリティ: 値の無いオプションの exit code（[$miss]）"
    assert_eq "$MS" "$MP" "パリティ: 値の無いオプションのメッセージ（[$miss]）"
  done
  rm -rf "$PAR"

  # --- 条項の一生の後始末のパリティ（改善ループ監査より） ---
  # 背景: (1) --verify-after 0 は受理されるが判定側が va>0 を要求するので永久に ready=no、
  # (2) retire は archive へ移すのに索引に触れず、doctor も見ないので dangling が残る、
  # (3) 起票テンプレのまま本文を書かなくても誰も検知せず、「タグは付くが規約は無い」母集団ができる。
  for impl in sh ps1; do
    PCL=$(mktemp -d); mkdir -p "$PCL/.aidev/works" "$PCL/docs"
    if [ "$impl" = sh ]; then rc_() { ( cd "$PCL" && "$AIDEV_SH" "$@" ); }
    else rc_() { ( cd "$PCL" && run_ps1 "$AIDEV_PS1" "$@" ); }; fi
    rc_ convention new z --hypothesis h --baseline b --verify-after 0 >/dev/null 2>&1
    assert_eq "$?" "1" "[$impl] convention new: --verify-after 0 は弾く（永久に判定できない）"
    rc_ convention new k --hypothesis h --baseline b --verify-after 1 >/dev/null
    printf '# A\n\n<!-- aidev:conventions -->\n- x → .aidev/conventions/k.md\n<!-- /aidev:conventions -->\n' > "$PCL/AGENTS.md"
    DK=$(rc_ doctor 2>&1 | tr -d '\r')
    assert_contains "$DK" "本文が未記入" "[$impl] doctor: 起票テンプレのまま本文が無い条項を WARN"
    # 本文を書けば消える
    python3 - "$PCL/.aidev/conventions/k.md" <<'PYEOF'
import io,sys
p=sys.argv[1]; t=io.open(p,encoding='utf-8').read().replace('<!-- 何を守るか。レビューで指摘するときの根拠になる粒度で書く。 -->','boolean は is/has で始める')
io.open(p,'w',encoding='utf-8').write(t)
PYEOF
    assert_absent "$(rc_ doctor 2>&1 | tr -d '\r')" "本文が未記入" "[$impl] doctor: 本文を書けば WARN は消える"
    RT=$(rc_ convention retire k --status ineffective --note n --force 2>&1 | tr -d '\r')
    assert_contains "$RT" "索引ブロックから .aidev/conventions/k.md の行を消すこと" "[$impl] retire: 索引の行を消すよう促す"
    DR=$(rc_ doctor 2>&1 | tr -d '\r')
    assert_contains "$DR" "索引が退役済み条項を指したまま" "[$impl] doctor: 退役後に索引が dangling なら WARN"
    printf '# A\n\n<!-- aidev:conventions -->\n<!-- /aidev:conventions -->\n' > "$PCL/AGENTS.md"
    assert_absent "$(rc_ doctor 2>&1 | tr -d '\r')" "索引が退役済み" "[$impl] doctor: 行を消せば WARN は消える"
    rm -rf "$PCL"
  done
  unset -f rc_ 2>/dev/null || true

  # --- unapprove / event の入口 / worktree のロールバックのパリティ ---
  # 背景: 差し戻しで `approved` から工程を外す手段が CLI に無く、protocol.md が「手で除く」と
  # 指示していた。これは escalate を作った理由（state.yml の更新を CLI に集約する）と矛盾し、
  # しかも 60-review の統合差し戻し手順は「子の approved から review を外す」を要求していて、
  # **手段が無いまま手順だけがあった**。
  for impl in sh ps1; do
    PUA=$(mktemp -d); mkdir -p "$PUA/.aidev/works"
    if [ "$impl" = sh ]; then ru() { ( cd "$PUA" && "$AIDEV_SH" "$@" ); }
    else ru() { ( cd "$PUA" && run_ps1 "$AIDEV_PS1" "$@" ); }; fi

    ru new ua >/dev/null; UAW=$(ls "$PUA/.aidev/works" | head -n1)
    for f in requirements design tasks; do : > "$PUA/.aidev/works/$UAW/$f.md"; done
    for ph in requirements design tasks; do ru approve "$ph" >/dev/null; done
    ru new 01-c --parent "$UAW" >/dev/null
    ru use "$UAW/01-c" >/dev/null
    for f in tasks tasks review; do : > "$PUA/.aidev/works/$UAW/01-c/$f.md"; done
    for ph in tasks coding test review; do ru approve "$ph" >/dev/null; done
    # 全子完了で activeSubtask=done になる
    assert_contains "$(tr -d '\r' < "$PUA/.aidev/works/$UAW/state.yml")" "activeSubtask: done" \
      "[$impl] 全 subtask 完了で activeSubtask=done"

    # unapprove で子の review を取り消す → approved から外れ、current が戻り、親のカーソルも戻る
    ru use "$UAW/01-c" >/dev/null
    ru unapprove review >/dev/null
    UA_C=$(tr -d '\r' < "$PUA/.aidev/works/$UAW/01-c/state.yml")
    assert_contains "$UA_C" "approved: [tasks, coding, test]" "[$impl] unapprove: approved から当該工程だけ外す"
    assert_contains "$UA_C" "current: review" "[$impl] unapprove: current を取り消した工程へ戻す"
    assert_contains "$(tr -d '\r' < "$PUA/.aidev/works/$UAW/state.yml")" "activeSubtask: 01-c" \
      "[$impl] unapprove(子の review): 親の activeSubtask もその子へ戻す"
    # **記録は消さない**。手戻りは実際に起きた事実なので、消すと reworks/sent_backs が過小になる
    assert_contains "$(tr -d '\r' < "$PUA/.aidev/works/$UAW/01-c/metrics.yml")" "phase: review, event: sent_back" \
      "[$impl] unapprove: 取り消しを sent_back として刻む（記録を消さない）"
    ru unapprove review >/dev/null 2>&1
    assert_eq "$?" "1" "[$impl] unapprove: 承認されていない工程は弾く"

    # use が subtask を指したら親の activeSubtask も同期する（冗長コピーの定義を保つ）
    ru use "$UAW" >/dev/null
    ru use "$UAW/01-c" >/dev/null
    assert_contains "$(tr -d '\r' < "$PUA/.aidev/works/$UAW/state.yml")" "activeSubtask: 01-c" \
      "[$impl] use: subtask に切り替えたら親の activeSubtask も同期する"

    # event <phase> approved は state を更新しないので metrics と乖離する。入口で弾く
    ru event design approved >/dev/null 2>&1
    assert_eq "$?" "1" "[$impl] event で approved は書けない（state と metrics が乖離する）"
    rm -rf "$PUA"
  done
  unset -f ru 2>/dev/null || true

  # --- harness 登録 / convention defer / backlog compact のパリティ ---
  PHV=$(mktemp -d); mkdir -p "$PHV/.aidev/works" "$PHV/.aidev/backlog"
  ( cd "$PHV" && "$AIDEV_SH" harness new ph --hypothesis h --baseline b --verify-after 1 >/dev/null )
  HS_SH=$( ( cd "$PHV" && "$AIDEV_SH" harness status --format tsv ) 2>&1 )
  HS_PS=$( ( cd "$PHV" && run_ps1 "$AIDEV_PS1" harness status --format tsv ) 2>&1 | tr -d '\r' )
  assert_eq "$HS_SH" "$HS_PS" "パリティ: harness status（母集団の数え方と列）"
  ( cd "$PHV" && "$AIDEV_SH" convention new pd --hypothesis h --baseline b --verify-after 1 >/dev/null )
  DF_SH=$( ( cd "$PHV" && "$AIDEV_SH" convention defer pd --verify-after 0 --note n ) 2>&1 )
  DF_PS=$( ( cd "$PHV" && run_ps1 "$AIDEV_PS1" convention defer pd --verify-after 0 --note n ) 2>&1 | tr -d '\r' )
  assert_eq "$DF_SH" "$DF_PS" "パリティ: convention defer の拒否メッセージ"
  printf -- '---\nkind: standing\n---\n\n- [x] done1\n    → 20260101-x で完了\n- [ ] todo1\n' > "$PHV/.aidev/backlog/s.md"
  cp "$PHV/.aidev/backlog/s.md" "$PHV/.aidev/backlog/s2.md"
  CP_SH=$( ( cd "$PHV" && "$AIDEV_SH" backlog compact s.md ) | sed 's/s\.md/X.md/; s/s-done/X-done/' )
  CP_PS=$( ( cd "$PHV" && run_ps1 "$AIDEV_PS1" backlog compact s2.md ) | tr -d '\r' | sed 's/s2\.md/X.md/; s/s2-done/X-done/' )
  assert_eq "$CP_SH" "$CP_PS" "パリティ: backlog compact の報告"
  assert_eq "$(cat "$PHV/.aidev/backlog/s.md")" "$(tr -d '\r' < "$PHV/.aidev/backlog/s2.md")" "パリティ: backlog compact 後の active ファイル"
  assert_eq "$(sed 's/^# s /# X /' "$PHV/.aidev/backlog/archive/s-done.md")" "$(tr -d '\r' < "$PHV/.aidev/backlog/archive/s2-done.md" | sed 's/^# s2 /# X /')" "パリティ: backlog compact の done ファイル"
  # CRLF のファイルでも両実装が同じ（LF）ファイルを作る（sh が \r を残すと Windows 側とだけ食い違う）
  printf -- '---\r\nkind: standing\r\n---\r\n\r\n- [x] crlf done\r\n- [ ] crlf todo\r\n' > "$PHV/.aidev/backlog/c.md"
  cp "$PHV/.aidev/backlog/c.md" "$PHV/.aidev/backlog/c2.md"
  ( cd "$PHV" && "$AIDEV_SH" backlog compact c.md >/dev/null )
  ( cd "$PHV" && run_ps1 "$AIDEV_PS1" backlog compact c2.md >/dev/null )
  assert_eq "$(od -c "$PHV/.aidev/backlog/c.md" | tr -s ' ')" "$(od -c "$PHV/.aidev/backlog/c2.md" | tr -s ' ')" "パリティ: backlog compact は CRLF 入力でも同じバイト列（LF）を書く"
  rm -rf "$PHV"

  # --- 数え方・exit code・入口ゲートのパリティ ---
  for impl in sh ps1; do
    PMX=$(mktemp -d); mkdir -p "$PMX/.aidev/works" "$PMX/.aidev/backlog"
    if [ "$impl" = sh ]; then rx() { ( cd "$PMX" && "$AIDEV_SH" "$@" ); }
    else rx() { ( cd "$PMX" && run_ps1 "$AIDEV_PS1" "$@" ); }; fi

    # reworks は「やり直した回数」。工程数で数えると上限が工程数で飽和し、
    # protocol-analysis「規模あたりの手戻り」の分子が頭打ちになる
    rx new rw >/dev/null; RWW=$(ls "$PMX/.aidev/works" | head -n1)
    for _i in 1 2 3 4; do rx event coding start >/dev/null; done
    RW_OUT=$(rx metrics "$RWW" --format tsv 2>&1 | tr -d '\r')
    assert_contains "$RW_OUT" "	3	" "[$impl] reworks はやり直した回数（4回 start なら 3）"

    # doctor の exit code は 4（不変条件違反）。1 は使用法・環境エラー用なので、
    # 機械ゲートが「ドリフト検知」を「環境が壊れている」と誤読する
    printf 'schema: 5\nslug: broken\ncurrent: review\napproved: [review]\n' \
      > "$PMX/.aidev/works/20200101-broken/state.yml" 2>/dev/null \
      || { mkdir -p "$PMX/.aidev/works/20200101-broken"; \
           printf 'schema: 5\nslug: broken\ncurrent: review\napproved: [review]\n' \
             > "$PMX/.aidev/works/20200101-broken/state.yml"; }
    printf 'events:\n' > "$PMX/.aidev/works/20200101-broken/metrics.yml"
    rx doctor >/dev/null 2>&1
    assert_eq "$?" "4" "[$impl] doctor のドリフト検知は exit 4（1=環境エラーと区別する）"

    # 子は backlog 出自を持たない設計。受理して黙って捨てない
    printf -- '---\nkind: topic\n---\n\n- [ ] a\n' > "$PMX/.aidev/backlog/b.md"
    rx new pp >/dev/null; PPW=$(ls "$PMX/.aidev/works" | grep -- '-pp$' | head -n1)
    rx new 01-x --parent "$PPW" --backlog b.md >/dev/null 2>&1
    assert_eq "$?" "1" "[$impl] --parent と --backlog の併用は弾く（刻印を黙って捨てない）"

    # protocol.md 2.7 は `PROJ-123` 型の外部チケットを dependsOn に認めるが、CLI は `#N` しか
    # advisory にせず works slug として探しに行き「work不明」で guard を exit 3 にしていた
    rx new tk --depends PROJ-123 >/dev/null
    rx guard requirements >/dev/null 2>&1; TK_RC=$?
    TK_OUT=$(rx guard requirements 2>&1 | tr -d '\r')
    assert_eq "$TK_RC" "0" "[$impl] guard: PROJ-123 型の外部チケットは advisory（未充足にしない）"
    assert_contains "$TK_OUT" "advisory" "[$impl] guard: PROJ-123 を advisory として警告表示する"
    rm -rf "$PMX"
  done
  unset -f rx 2>/dev/null || true

  # --- 成果物の実在検査 / subtask 横断 / light の next のパリティ ---
  # 背景: verify は deliver の**着地前ゲート**（70-deliver「PASS を着地の前提とする」）なのに、
  # (1) 承認済み工程の成果物を1つも見ておらず、**成果物ゼロの work が「deliver 済み・OK」**になり、
  # (2) 分割 work の親を verify しても子を見ないので、子の記録欠落が硬ゲートを素通りし、
  # (3) light の next が永久に design を指していた（20-design 自身が「light では起動しない」と書く工程）。
  for impl in sh ps1; do
    PNV=$(mktemp -d); mkdir -p "$PNV/.aidev/works"
    if [ "$impl" = sh ]; then rv() { ( cd "$PNV" && "$AIDEV_SH" "$@" ); }
    else rv() { ( cd "$PNV" && run_ps1 "$AIDEV_PS1" "$@" ); }; fi

    # (1) 成果物ゼロで全工程 approve → verify は FAIL
    rv new nf >/dev/null; NFW=$(ls "$PNV/.aidev/works" | head -n1)
    : > "$PNV/.aidev/works/$NFW/review.md"
    for ph in requirements design tasks coding test review; do rv approve "$ph" >/dev/null; done
    NF_OUT=$(rv verify "$NFW" 2>&1); NF_RC=$?
    NF_OUT=$(printf '%s' "$NF_OUT" | tr -d '\r')
    assert_eq "$NF_RC" "4" "[$impl] 成果物を作らずに承認した work は verify が FAIL（着地前ゲートが効く）"
    assert_contains "$NF_OUT" "requirements.md欠落(requirements承認済)" "[$impl] 欠けている成果物を名指しする"
    assert_contains "$NF_OUT" "tasks.md欠落(tasks承認済)" "[$impl] tasks 承認済なら tasks.md も要る"
    assert_contains "$NF_OUT" "test-result.md欠落(test承認済)" "[$impl] test 承認済なら test-result.md も要る（schema 6）"
    for f in requirements design tasks tasks test-result; do : > "$PNV/.aidev/works/$NFW/$f.md"; done
    rv verify "$NFW" >/dev/null 2>&1
    assert_eq "$?" "0" "[$impl] 成果物が揃えば PASS"

    # 導入前（schema<5）の work は遡って違反にしない（version-aware）
    mkdir -p "$PNV/.aidev/works/20200101-old"
    printf 'schema: 4\nslug: old\ncurrent: tasks\napproved: [requirements, design, tasks]\nharnessRev: aaa1111\n' \
      > "$PNV/.aidev/works/20200101-old/state.yml"
    printf 'events:\n' > "$PNV/.aidev/works/20200101-old/metrics.yml"
    rv verify 20200101-old >/dev/null 2>&1
    assert_eq "$?" "0" "[$impl] schema<5 の work に成果物実在を要求しない（遡って違反にしない）"

    # (2) 親 verify が子の欠落を拾う
    rv new pv >/dev/null; PVW=$(ls "$PNV/.aidev/works" | grep -- '-pv$' | head -n1)
    for f in requirements design tasks; do : > "$PNV/.aidev/works/$PVW/$f.md"; done
    for ph in requirements design tasks; do rv approve "$ph" >/dev/null; done
    rv new 01-c --parent "$PVW" >/dev/null
    rv use "$PVW/01-c" >/dev/null
    for f in tasks tasks; do : > "$PNV/.aidev/works/$PVW/01-c/$f.md"; done
    for ph in tasks coding test; do rv approve "$ph" >/dev/null; done
    rv approve review >/dev/null 2>&1   # review.md を作らずに承認＝子だけ壊れた状態
    PV_OUT=$(rv verify "$PVW" 2>&1); PV_RC=$?
    PV_OUT=$(printf '%s' "$PV_OUT" | tr -d '\r')
    assert_eq "$PV_RC" "4" "[$impl] 親の verify が子の記録欠落を拾う（着地は親1本の PR）"
    assert_contains "$PV_OUT" "review.md欠落" "[$impl] 子の欠落を名指しする"

    # (3) light の next が design を指さない
    rv new lt --light >/dev/null; LTW=$(ls "$PNV/.aidev/works" | grep -- '-lt$' | head -n1)
    : > "$PNV/.aidev/works/$LTW/requirements.md"
    rv use "$LTW" >/dev/null; rv approve requirements >/dev/null
    LT_OUT=$(rv status --format tsv 2>&1 | tr -d '\r' | grep -- "-lt	")
    assert_contains "$LT_OUT" "	coding	" "[$impl] light の next は design を飛ばして coding を指す"
    rm -rf "$PNV"
  done
  unset -f rv 2>/dev/null || true

  # --- 分割 work の親のカーソルと統合 test のパリティ ---
  # 背景: (1) 子を作るたび `.aidev/current` を無条件に上書きしていたため、親 tasks で子を
  # まとめて起こすと activeSubtask=先頭 / current=最後 になり、「冗長コピー」の定義
  # （protocol.md「6.」）が生成直後から破れていた。(2) 親は tasks.md を作らない
  # （aidev-30-tasks「4.」）のに guard test が need_file tasks.md を課しており、
  # **書いてあるとおりに tasks を書くと親の統合 test が必ず塞がる**状態だった。
  for impl in sh ps1; do
    PSB=$(mktemp -d); mkdir -p "$PSB/.aidev/works"
    if [ "$impl" = sh ]; then rb() { ( cd "$PSB" && "$AIDEV_SH" "$@" ); }
    else rb() { ( cd "$PSB" && run_ps1 "$AIDEV_PS1" "$@" ); }; fi
    rb new pb >/dev/null; PBW=$(ls "$PSB/.aidev/works")
    for f in requirements design tasks; do : > "$PSB/.aidev/works/$PBW/$f.md"; done
    for ph in requirements design tasks; do rb approve "$ph" >/dev/null; done
    rb new 01-a --parent "$PBW" >/dev/null
    rb new 02-b --parent "$PBW" >/dev/null
    PB_CUR=$(tr -d '\r' < "$PSB/.aidev/current")
    PB_ACT=$(tr -d '\r' < "$PSB/.aidev/works/$PBW/state.yml" | sed -n 's/^activeSubtask: //p')
    assert_eq "$PB_CUR" "$PBW/$PB_ACT" "[$impl] 子を重ねて作ってもカーソルが activeSubtask と一致する"
    rb use "$PBW" >/dev/null
    rb guard test >/dev/null 2>&1
    assert_eq "$?" "2" "[$impl] 子が未 review なら親の統合 test は塞がる"
    for c in 01-a 02-b; do
      rb use "$PBW/$c" >/dev/null
      for f in tasks tasks review; do : > "$PSB/.aidev/works/$PBW/$c/$f.md"; done
      for ph in tasks coding test review; do rb approve "$ph" >/dev/null; done
    done
    rb use "$PBW" >/dev/null
    rb guard test >/dev/null 2>&1
    assert_eq "$?" "0" "[$impl] 親は tasks.md 無しでも全子 review 済みなら統合 test に入れる"
    rm -rf "$PSB"
  done
  unset -f rb 2>/dev/null || true

  # --- 承認の積み上げのパリティ（**2回以上**打つこと自体が検査対象） ---
  # 背景: ここまでのパリティは ps1 の approve を**1回しか打っていなかった**。そのため
  # 「2回目から approved が壊れる」欠陥が 357 件のテストをすり抜けていた。
  # PowerShell は単一要素配列をスカラーに巻き戻すので、`$cur + $ph` が配列追加ではなく
  # **文字列連結**になり `approved: [requirementspec]` になる。以後 ApprovedHas が
  # 永久に false になり、**Windows で作った work は二度と deliver できない**（sh で読んでも壊れている）。
  PAP=$(mktemp -d); mkdir -p "$PAP/.aidev/works"
  ( cd "$PAP" && run_ps1 "$AIDEV_PS1" new pa >/dev/null )
  PAW=$(ls "$PAP/.aidev/works")
  for f in requirements design tasks tasks review test-result; do : > "$PAP/.aidev/works/$PAW/$f.md"; done
  for ph in requirements design tasks coding test review; do
    ( cd "$PAP" && run_ps1 "$AIDEV_PS1" approve "$ph" >/dev/null )
  done
  PAP_ST=$(tr -d '\r' < "$PAP/.aidev/works/$PAW/state.yml" | sed -n 's/^approved: //p')
  assert_eq "$PAP_ST" "[requirements, design, tasks, coding, test, review]" \
    "ps1: approve を重ねても approved が配列として積まれる（文字列連結にならない）"
  # 壊れた state は sh からも読めない。両実装が同じ判断をすることまで見る
  ( cd "$PAP" && run_ps1 "$AIDEV_PS1" guard deliver >/dev/null 2>&1 ); PA_P=$?
  ( cd "$PAP" && "$AIDEV_SH" guard deliver >/dev/null 2>&1 ); PA_S=$?
  assert_eq "$PA_P" "0" "ps1: 積み上げた approved で guard deliver が通る"
  assert_eq "$PA_S" "$PA_P" "パリティ: ps1 が書いた state を sh が同じに読む"
  rm -rf "$PAP"

  # --- verify の出力と exit code のパリティ ---
  # 背景: ps1 の VerifyWork は「状態行は [Console]::Out へ直接出す」約束で書かれている。
  # 1行でも Write-Output を混ぜると**関数の戻り値が Object[] になり `$rc = VerifyWork` が壊れる**——
  # FAIL を印字しながら rc=0、--strict の 5 も 0 になり、**Windows で機械ゲートが素通りする**。
  # これまでのパリティは harnessRev の「刻印値」しか見ておらず、verify の出力と rc を見ていなかった。
  PVR=$(mktemp -d); mkdir -p "$PVR/.aidev/works/20260101-nohr"
  printf 'schema: 4\nslug: nohr\ncurrent: requirements\napproved: [requirements]\n' \
    > "$PVR/.aidev/works/20260101-nohr/state.yml"
  printf 'events:\n  - { ts: 2026-01-01T01:00:00Z, phase: requirements, event: approved }\n' \
    > "$PVR/.aidev/works/20260101-nohr/metrics.yml"
  VO_SH=$( ( cd "$PVR" && "$AIDEV_SH" verify --strict 20260101-nohr ) 2>&1 ); VO_SHC=$?
  VO_PS_RAW=$( ( cd "$PVR" && run_ps1 "$AIDEV_PS1" verify --strict 20260101-nohr ) 2>&1 ); VO_PSC=$?
  VO_PS=$(printf '%s' "$VO_PS_RAW" | tr -d '\r')
  assert_eq "$VO_SHC" "$VO_PSC" "パリティ: verify --strict の exit code（機械ゲートが片方で素通りしない）"
  assert_eq "$VO_SH" "$VO_PS" "パリティ: verify の出力（WARN が片方だけ消えない）"
  assert_contains "$VO_PS" "harnessRev が無い" "ps1: verify の WARN が出力される（Write-Output に戻すと消える）"
  DO_SH=$( ( cd "$PVR" && "$AIDEV_SH" doctor ) 2>&1 | grep '^summary:' )
  DO_PS=$( ( cd "$PVR" && run_ps1 "$AIDEV_PS1" doctor ) 2>&1 | tr -d '\r' | grep '^summary:' )
  assert_eq "$DO_SH" "$DO_PS" "パリティ: doctor の summary（偽の fail を数えない）"
  rm -rf "$PVR"

  # --- 値の大小の扱いのパリティ ---
  # PowerShell は switch だけでなく `-eq` / `-contains` も既定で大小を無視する。switch にだけ
  # -CaseSensitive を付けても、値の検証側が素通しでは意味が無い。実害は state.yml に
  # `current: DELIVER` が書かれること——**Windows で作った work が Linux で読めなくなる**。
  PUC=$(mktemp -d); mkdir -p "$PUC/.aidev/works" "$PUC/.aidev/backlog"
  for uc in "new x --mode INTERACTIVE" "new y --profile LIGHT" "backlog new n --kind TOPIC" \
            "status --format TSV" "event REQUIREMENT start" "approve DELIVER" "guard CODING"; do
    # shellcheck disable=SC2086
    ( cd "$PUC" && "$AIDEV_SH" $uc >/dev/null 2>&1 ); US=$?
    # shellcheck disable=SC2086
    ( cd "$PUC" && run_ps1 "$AIDEV_PS1" $uc >/dev/null 2>&1 ); UP=$?
    assert_eq "$US" "$UP" "パリティ: 大文字の値を同じように扱う（[$uc]）"
  done
  rm -rf "$PUC"

  # --- 空文字のオプション値のパリティ ---
  # need_arg / ArgAt は値の「個数」しか見ないので空文字を通す。ps1 側は Split-Path が
  # 生の .NET 例外を投げ、sh は成功する＝同じ入力で片方だけ work ができる
  PEV=$(mktemp -d); mkdir -p "$PEV/.aidev/works"
  ( cd "$PEV" && "$AIDEV_SH" new e1 --backlog "" >/dev/null 2>&1 ); ES=$?
  EP_OUT=$( ( cd "$PEV" && run_ps1 "$AIDEV_PS1" new e2 --backlog "" ) 2>&1 ); EP=$?
  assert_eq "$ES" "$EP" "パリティ: 空文字のオプション値（--backlog \"\"）"
  assert_absent "$EP_OUT" "Cannot bind argument" "ps1: 生の .NET 例外を漏らさない"
  rm -rf "$PEV"

  # --- ファイルとディレクトリの取り違え / グロブ解釈のパリティ ---
  # 素の Test-Path は**ディレクトリもファイルも通し**、パスを**ワイルドカードとして解釈する**。
  # sh は [ -f ] とリテラル比較なので、揃えないと同じ入力で結果が割れる。
  # この2ケースは IsFile を素の Test-Path に戻すと両方とも sh と食い違う（＝この置換の見張り番）
  PTP=$(mktemp -d); mkdir -p "$PTP/.aidev/works" "$PTP/.aidev/backlog/dir.md"
  printf -- '---\nkind: standing\n---\n\n- [ ] a\n' > "$PTP/.aidev/backlog/q[1].md"
  ( cd "$PTP" && "$AIDEV_SH" new d1 --backlog dir.md >/dev/null 2>&1 ); TS=$?
  ( cd "$PTP" && run_ps1 "$AIDEV_PS1" new d2 --backlog dir.md >/dev/null 2>&1 ); TP=$?
  assert_eq "$TS" "$TP" "パリティ: backlog がディレクトリなら両実装とも弾く（-PathType Leaf）"
  assert_eq "$TS" "1" "backlog がディレクトリなら着手前に弾く（存在検査はファイルであること）"
  ( cd "$PTP" && "$AIDEV_SH" new g1 --backlog 'q[1].md' >/dev/null 2>&1 ); GS2=$?
  ( cd "$PTP" && run_ps1 "$AIDEV_PS1" new g2 --backlog 'q[1].md' >/dev/null 2>&1 ); GP2=$?
  assert_eq "$GS2" "$GP2" "パリティ: グロブ文字を含む backlog 名を両実装とも受理する（-LiteralPath）"
  assert_eq "$GS2" "0" "グロブ文字を含む backlog 名は実在するので受理する"
  # IsDir 側。`.aidev` が**ファイル**なら「リポジトリの中ではない」。素の Test-Path は
  # ファイルも通すので、そこをルートと誤認して WORKS を出してしまう（sh は [ -d ] で見送る）
  PTD=$(mktemp -d); printf 'not a dir\n' > "$PTD/.aidev"
  DS_OUT=$( ( cd "$PTD" && "$AIDEV_SH" status ) 2>&1 ); DS=$?
  # `$(… | tr)` の `$?` は tr のもの。exit code を見るなら CR 除去は代入を分ける
  DP_RAW=$( ( cd "$PTD" && run_ps1 "$AIDEV_PS1" status ) 2>&1 ); DP=$?
  DP_OUT=$(printf '%s' "$DP_RAW" | tr -d '\r')
  assert_eq "$DS" "$DP" "パリティ: .aidev がファイルなら両実装ともリポジトリと認めない（-PathType Container）"
  assert_contains "$DS_OUT" ".aidev が見つかりません" "sh: .aidev がファイルならルートと認めない"
  assert_contains "$DP_OUT" ".aidev が見つかりません" "ps1: .aidev がファイルならルートと認めない"
  rm -rf "$PTD"
  rm -rf "$PTP"

  # --- 名前にグロブ文字を含む work のパリティ ---
  # ps1 の Get-ChildItem -Path はパスをワイルドカードとして解釈する。Test-Path だけを
  # -LiteralPath 化しても列挙側が残っていると、doctor が subtask を黙って落とす
  PGL=$(mktemp -d); GW="$PGL/.aidev/works/20260101-a[b]c"
  mkdir -p "$GW/01-sub"
  printf 'schema: 4\nslug: a[b]c\ncurrent: tasks\napproved: []\nsubtasks: [01-sub]\n' > "$GW/state.yml"
  printf 'events:\n' > "$GW/metrics.yml"
  printf 'schema: 4\nslug: 01-sub\ncurrent: tasks\napproved: []\nparent: 20260101-a[b]c\n' > "$GW/01-sub/state.yml"
  printf 'events:\n' > "$GW/01-sub/metrics.yml"
  GS=$( ( cd "$PGL" && "$AIDEV_SH" doctor ) 2>&1 | grep '^summary:' )
  GP=$( ( cd "$PGL" && run_ps1 "$AIDEV_PS1" doctor ) 2>&1 | tr -d '\r' | grep '^summary:' )
  assert_eq "$GS" "$GP" "パリティ: グロブ文字を含む work 名でも subtask を数える"
  rm -rf "$PGL"

  # --- 破壊の前の衝突検査のパリティ（種別の取り違え） ---
  # sh は [ -e ]（種別を問わない）。ps1 を IsFile にすると archive に**ディレクトリ**が
  # あるときに素通りし、Move-Item がその中へ本文を移す＝本文の在処が想定外の場所になる
  PAD=$(mktemp -d); mkdir -p "$PAD/.aidev/works" "$PAD/.aidev/conventions/archive/k.md"
  printf -- '---\nconvention: k\nstatus: pending\nintroduced: 2026-01-01\nhypothesis: h\nbaseline: b\nverify_after: 1\n---\n\nbody\n' \
    > "$PAD/.aidev/conventions/k.md"
  ( cd "$PAD" && "$AIDEV_SH" convention retire k --status ineffective --note n --force >/dev/null 2>&1 ); AS=$?
  ( cd "$PAD" && run_ps1 "$AIDEV_PS1" convention retire k --status ineffective --note n --force >/dev/null 2>&1 ); AP=$?
  assert_eq "$AS" "$AP" "パリティ: archive に同名ディレクトリがあれば両実装とも止める"
  assert_eq "$([ -f "$PAD/.aidev/conventions/k.md" ] && echo yes || echo no)" "yes" \
    "衝突を検知したら本文を動かさない（archive/<id>.md がディレクトリでも埋没させない）"
  rm -rf "$PAD"

  # harnessRev のパリティ（刻印が片方だけ欠けると、その OS の work が母集団から漏れる）
  PHV=$(mktemp -d); mkdir -p "$PHV/.aidev/works"
  ( cd "$PHV" && "$AIDEV_SH" new a >/dev/null ) && ( cd "$PHV" && run_ps1 "$AIDEV_PS1" new b >/dev/null )
  HA=$(sed -n 's/^harnessRev: //p' "$PHV/.aidev/works/"*-a/state.yml)
  # 注意: POSIX sh は**リダイレクトの語にパス名展開をしない**。`< .../*-b/state.yml` は
  # glob のままファイル名として開かれ、常に失敗する（このテストが長く skip だったので気付けなかった）
  HB=$(cat "$PHV/.aidev/works/"*-b/state.yml | tr -d '\r' | sed -n 's/^harnessRev: //p')
  assert_eq "$HA" "$HB" "パリティ: harnessRev の刻印が一致"
  rm -rf "$PHV"
  # profile 系のパリティ（同じフィクスチャに対して同じ出力になること）
  # 注意: $L_SLUG は escalate で **full に昇格済み**（上でそれを assert している）。
  # light のままの work は $L2_SLUG なので、light 側の判定はそちらで比べる
  for pargs in "verify $L2_SLUG" "verify $L_SLUG" "verify $F_SLUG" "verify 20260101-oldwork"; do
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
  for args in "doctor" "doctor --quiet" "status --format tsv" "status --subtasks --format tsv" "status --active --format tsv" "metrics --all --format tsv"; do
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
    block_begin wtparity
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
current: design
approved: [requirements, design]
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

    # worktree files: 重なりの検知と sh⇔ps1 の一致（並びは LC_ALL=C / Ordinal で固定してある）
    printf 'x\n' > "$PREPO/README.md"; printf 'y\n' > "$PREPO/shared.txt"
    ( cd "$PREPO" && git add -A && git commit -qm f2 >/dev/null 2>&1 )
    ( cd "$PREPO" && "$AIDEV_SH" worktree add wa >/dev/null 2>&1 )
    ( cd "$PREPO" && "$AIDEV_SH" worktree add wb >/dev/null 2>&1 )
    for w in wa wb; do
      printf 'touched by %s\n' "$w" >> "$TMP/prepo-wt/$w/shared.txt"
      ( cd "$TMP/prepo-wt/$w" && git add -A && git commit -qm "$w" >/dev/null 2>&1 )
    done
    WF_SH=$( ( cd "$PREPO" && "$AIDEV_SH" worktree files --format tsv ) )
    WF_PS=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree files --format tsv ) | tr -d '\r' )
    assert_eq "$WF_SH" "$WF_PS" "パリティ: worktree files --format tsv"
    assert_contains "$WF_SH" "file	shared.txt	2	no	wa, wb" \
      "worktree files: 2 本が触っているファイルを名前と本数で出す（sharedFiles 未宣言も分かる）"
    assert_eq "$(printf '%s' "$WF_SH" | grep -c 'file	README.md')" "0" \
      "worktree files: 1 本しか触っていないファイルは既定では出さない（重なりが埋もれる）"
    assert_contains "$( ( cd "$PREPO" && "$AIDEV_SH" worktree files ) )" "sharedFiles に無いファイルが 1 件" \
      "worktree files: 未宣言の重なりを数えて知らせる"

    # deliver しただけでは重なりの相手から外れない。deliver は PR 作成で終わりで、
    # **マージは人間の仕事**——未マージのまま deliver した枝はマージ衝突の相手として現役
    ( cd "$TMP/prepo-wt/wb" && "$AIDEV_SH" approve deliver >/dev/null 2>&1 )
    assert_contains "$( ( cd "$PREPO" && "$AIDEV_SH" worktree files --format tsv ) )" "shared.txt" \
      "worktree files: deliver 済みでも未マージなら重なりの相手のまま（マージ順の判断に要る）"
    # 既定ブランチに入った時点で初めて外れる（実際その差分はもう base 側にあるので重ならない）
    ( cd "$PREPO" && git merge -q --no-edit feature/wb >/dev/null 2>&1 )
    assert_eq "$( ( cd "$PREPO" && "$AIDEV_SH" worktree files --format tsv ) | grep -c 'wb')" "0" \
      "worktree files: 既定ブランチにマージ済みの worktree は外れる"
    assert_contains "$( ( cd "$PREPO" && "$AIDEV_SH" worktree files --all --format tsv ) )" "shared.txt" \
      "worktree files: --all ならマージ済みも含めて全件出す"

    # --planned: tasks.md の 対象: アンカーから「これから触る」重なりを出す。
    # 実差分モードは 3 本が同時に上流工程にいる立ち上がり期に構造的に空になる（実走で観測）
    for w in wa wb; do
      WD="$TMP/prepo-wt/$w"; WW=$(cat "$WD/.aidev/current")
      printf -- '- [ ] T1: x\n      対象: `planned/shared.py:12` `planned/only-%s.py`\n      依存: なし\n' \
        "$w" > "$WD/.aidev/works/$WW/tasks.md"
    done
    WP=$( ( cd "$PREPO" && "$AIDEV_SH" worktree files --planned --all --format tsv ) )
    assert_contains "$WP" "file	planned/shared.py	2	no	wa, wb" \
      "worktree files --planned: tasks.md の 対象: から予定の重なりを出す（書く前に見える）"
    assert_eq "$(printf '%s' "$WP" | grep -c 'planned/only-wa.py	1')" "1" \
      "worktree files --planned: 1 本だけの宣言は重なりに数えない"

    # doctor: sharedFiles の宣言が実態から遅れていないか
    printf 'sharedFiles: [nonexistent.txt]\n' > "$PREPO/.aidev/config.yml"
    DS_SH=$( ( cd "$PREPO" && "$AIDEV_SH" doctor --quiet ) 2>&1 )
    DS_PS=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" doctor --quiet ) 2>&1 | tr -d '\r' )
    assert_eq "$DS_SH" "$DS_PS" "パリティ: doctor の sharedFiles 検査"
    assert_contains "$DS_SH" "宣言されているが実在しません: nonexistent.txt" \
      "doctor: sharedFiles の誤記・残骸を名指しする（宣言だけ古びるのを機械が言う）"
    assert_contains "$DS_SH" "sharedFiles-summary: declared=1 実在しない=1" \
      "doctor: sharedFiles の件数を要約に出す"
    # ハーネス自身（skills 配下）は PJ のコードではないので常連から外す。
    # 外さないと、ハーネスを更新するたび skills の全ファイルが上位を占め、本命を押し出す（実測）
    assert_eq "$(printf '%s' "$DS_SH" | grep -c 'sharedFiles に無い: .claude/skills/')" "0" \
      "doctor: ハーネス自身の置き場を sharedFiles の常連に数えない"
    assert_eq "$(printf '%s' "$DS_SH" | grep -c 'sharedFiles に無い: .aidev/')" "0" \
      "doctor: .aidev/（帳簿）を sharedFiles の常連に数えない"

    # (2) ps1 の add（既存work一致＝current 設定のみ）。current が full dated 名であること
    #     ＝ review 検出の must「PowerShell 単一要素配列アンラップ($mw[0]が先頭1文字)」の回帰ガード
    PW_OUT=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree add existing ) | tr -d '\r' )
    PW_CUR=$(cat "$TMP/prepo-wt/existing/.aidev/current" 2>/dev/null)
    assert_eq "$PW_CUR" "20260101-existing" "パリティ: ps1 add(既存work) current=full dated 名(\$mw アンラップ回帰)"
    assert_contains "$PW_OUT" "既存 work をリンク" "パリティ: ps1 add は既存をリンク(new 委譲せず)"

    # (3) ps1 の add（新規 slug＝add 内で new に委譲する経路）。ここは長らく未検証で、
    #     委譲先パスが `.aidev/bin/aidev.ps1`（誤）かつホストが `pwsh` 決め打ちのまま壊れていた。
    # 注意: `$(… | tr)` の `$?` は **tr の**終了コードで常に 0 になる。exit code を見るなら
    # CR 除去は代入を分ける（このファイルの別の箇所で同じ取り違えを既にやっている）
    PN_RAW=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree add fresh ) 2>&1 ); PN_RC=$?
    PN_OUT=$(printf '%s' "$PN_RAW" | tr -d '\r')
    assert_eq "$PN_RC" "0" "パリティ: ps1 add(新規slug) exit 0"
    assert_contains "$PN_OUT" "新規 work を作成" "パリティ: ps1 add(新規slug) は new に委譲"
    PN_CUR=$(cat "$TMP/prepo-wt/fresh/.aidev/current" 2>/dev/null | tr -d '\r')
    assert_contains "$PN_CUR" "-fresh" "パリティ: ps1 add(新規slug) が worktree の current を書く"
    assert_eq "$([ -f "$TMP/prepo-wt/fresh/.aidev/works/$PN_CUR/state.yml" ] && echo yes || echo no)" "yes" \
      "パリティ: ps1 add(新規slug) が work を実際に作る（委譲失敗の空振り回帰）"

    # doctor の branch 検査: linked worktree では鳴らさない（aidev の worktree は定義上 feature/<slug>
    # に載っているので、鳴らすと 100% 誤警告になる）。sh/ps1 の両方で確かめる——**片側だけ直した**
    # のを一度やっている
    DB_WT="$TMP/prepo-wt/probe"
    DB_SH=$( ( cd "$DB_WT" && "$AIDEV_SH" doctor 2>&1 ) | grep -c '^branch:' ) || DB_SH=0
    assert_eq "$DB_SH" "0" "doctor: linked worktree では branch 検査を鳴らさない（sh）"
    DB_PS=$( ( cd "$DB_WT" && run_ps1 "$AIDEV_PS1" doctor 2>&1 ) | tr -d '\r' | grep -c '^branch:' ) || DB_PS=0
    assert_eq "$DB_PS" "0" "doctor: linked worktree では branch 検査を鳴らさない（ps1）"

    # (4) ps1 の rm <path>: 自分の list が出したパス表記をそのまま渡せること
    #     （git は C:/... 、.NET の解決は C:\... なので素の比較だと Windows で必ず外れた）
    PB=$( ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree list --format tsv ) | tr -d '\r' | awk -F'\t' '$2 ~ /fresh$/ {print $2}')
    ( cd "$PREPO" && run_ps1 "$AIDEV_PS1" worktree rm "$PB" --force --delete-branch >/dev/null 2>&1 )
    assert_eq "$?" "0" "パリティ: ps1 rm は list が出したパス表記をそのまま扱える"
    assert_eq "$([ -d "$TMP/prepo-wt/fresh" ] && echo yes || echo no)" "no" "パリティ: ps1 rm(path) で worktree 撤去済み"
    block_end wtparity "26" "wtparity"
  else
    skip 10 "git 不在のため worktree パリティを省略"
  fi
  block_end parity "267" "parity"
else
  skip 253 "PowerShell(pwsh/powershell) 不在のためパリティテストを省略（sh 単体の検査も一部含む）"
fi

echo
printf 'RESULT: pass=%s fail=%s skip=%s\n' "$PASS" "$FAIL" "$SKIP"
# skip>0＝環境不足で未実行の検証（未検証の穴）。deliver/PR で「未検証 surface」として引き継ぐこと(#32)。
# pwsh を入れるだけで埋まる穴を「環境が無い」で放置しないよう、入れ方まで書く。
# 実際、パリティテストが skip のままだった間に**ps1 側の実バグ2件**（値の無いオプションを
# 素通り／switch の大文字小文字）と**テスト自身のバグ2件**が緑の裏に隠れていた。
[ "$SKIP" -gt 0 ] && printf 'NOTE: %s 件のアサートが環境不足で未実行（未検証の穴）。pwsh/git のある環境で再実行して埋めること。\n      パリティだけでなく **sh 単体の検査も一部**が pwsh ブロックの中にある。\n      Linux なら: curl -fsSL -o /tmp/pwsh.tar.gz https://github.com/PowerShell/PowerShell/releases/download/v7.4.6/powershell-7.4.6-linux-x64.tar.gz \\\n                  && mkdir -p /opt/pwsh && tar -xzf /tmp/pwsh.tar.gz -C /opt/pwsh && export PATH=/opt/pwsh:$PATH\n' "$SKIP" >&2
[ "$FAIL" -eq 0 ]
