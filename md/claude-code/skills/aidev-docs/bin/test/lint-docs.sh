#!/bin/sh
# ハーネス自身の**文書と CLI 表面**の整合を機械で検査する。
#
# なぜ要るか（このセッションで実際に踏んだ欠陥の分類）:
#   A. **片方だけ直して食い違う**（同じ規則が2箇所にあり、片方だけ更新）… 4回
#      walkthrough の要否 / walkthrough の条件2 / autonomous のループ上限 / 壊れた参照。
#      いずれも「本文の在処は常に1箇所」を破ったところで起き、**散文の規約では防げなかった**。
#   B. **CLI 表面の更新漏れ**… ps1 の help に coverage/smoke/debug が無い、README の表に行が無い。
#   C. **文書の冗長化**… 文脈削減の直後に protocol.md が +55 行、うち 21 行が付録/DESIGN の写し。
#   D. **予算の無い増加**… 実行時に読む量は全 work のコストなのに、誰も数えていなかった。
#
# 三層モデル（DESIGN「2.6」）の第二層に上げる、という判断。散文で「気をつける」と書くのは
# 既に何度もやって、そのたびに片側だけ更新されている。
set -u

SELF=$(cd "$(dirname "$0")" && pwd)
BIN=$SELF/..
SKILLS=$(cd "$BIN/../.." && pwd)
SH=$BIN/aidev
PS=$BIN/aidev.ps1
BREADME=$BIN/README.md

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); printf '  ok: %s\n' "$1"; }
ng()  { FAIL=$((FAIL+1)); printf '  NG: %s\n' "$1" >&2; }
# 集合 A に在って B に無い要素を報告する
missing() { # desc A_file B_file
  _m=$(comm -23 "$2" "$3" | tr '\n' ' ' | sed 's/ *$//')
  if [ -z "$_m" ]; then ok "$1"; else ng "$1（不足: $_m）"; fi
}

# 実行時に読む文書（＝全 work / 工程が払うコスト）。aidev-docs は参照専用なので含めない
runtime_docs() {
  # aidev-00-start は SKILL.md と付録をまとめて拾う。**下のループから除く**——
  # `aidev-[0-9]*-*/` は aidev-00-start にも当たるので、除かないと同じファイルを2回数え、
  # L5 が「同一行が2ファイルに在る」と誤検出し L6 の予算も倍に膨れる（実際にそうなった）
  ls "$SKILLS"/aidev-00-start/*.md 2>/dev/null
  for d in "$SKILLS"/aidev-[0-9]*-*/ "$SKILLS"/aidev-util-*/; do
    case "$d" in *aidev-00-start/) continue ;; esac
    [ -f "$d/SKILL.md" ] && printf '%s\n' "$d/SKILL.md"
  done
}

echo "== L1: CLI 表面の同期（dispatch / usage / README の4面）=="
# 片面だけ足すと、その面を見た利用者に新コマンドが存在しないことになる（ps1 の help で実際に起きた）
sed -n '/^case "$cmd" in/,/^esac/p' "$SH" | sed -n 's/^  \([a-z|-]*\)).*/\1/p' \
  | tr '|' '\n' | grep -v '^-*help$\|^-h$' | sort -u > "$SELF/.l1a"
grep -o '^#   aidev [a-z]*' "$SH" | awk '{print $3}' | sort -u > "$SELF/.l1b"
sed -n "/^switch -CaseSensitive (\$cmd)/,/^}/p" "$PS" | sed -n "s/^  '\([a-z-]*\)'.*/\1/p" \
  | grep -v '^-*help$\|^-h$' | sort -u > "$SELF/.l1c"
grep -o 'aidev\.ps1 [a-z]*' "$PS" | awk '{print $2}' | sort -u > "$SELF/.l1d"
grep -o '^| `[a-z]*' "$BREADME" | sed 's/^| `//' | sort -u > "$SELF/.l1e"
missing "L1 sh dispatch のコマンドが sh の usage にある" "$SELF/.l1a" "$SELF/.l1b"
missing "L1 sh dispatch のコマンドが ps1 dispatch にある" "$SELF/.l1a" "$SELF/.l1c"
missing "L1 sh dispatch のコマンドが ps1 の usage にある" "$SELF/.l1a" "$SELF/.l1d"
missing "L1 sh dispatch のコマンドが bin/README の表にある" "$SELF/.l1a" "$SELF/.l1e"
missing "L1 ps1 dispatch のコマンドが sh dispatch にもある" "$SELF/.l1c" "$SELF/.l1a"
rm -f "$SELF"/.l1[a-e]

echo "== L2: .aidev/config.yml のキーが bin/README の設定表にある =="
# 設定を足しても表に載せないと、PJ 側は存在を知る手段が無い
{ grep -o 'yget "\$AIDEV/config\.yml" [a-zA-Z]*' "$SH" | awk '{print $3}'
  grep -o "config\.yml') '[a-zA-Z]*'" "$PS" | sed "s/.*'\([a-zA-Z]*\)'\$/\1/"
  grep -o "^smokeCommandRaw\|smokeCommandWindows" "$PS"
  sed -n "s/.*SmokeCmdRaw '\([a-zA-Z]*\)'.*/\1/p" "$PS"
  sed -n "s/.*sed -n 's\/\^\([a-zA-Z]*\):.*/\1/p" "$SH"
} 2>/dev/null | grep -v '^$' | sort -u > "$SELF/.l2a"
grep -o '^| `[a-zA-Z]*` |' "$BREADME" | sed 's/^| `//; s/` |$//' | sort -u > "$SELF/.l2b"
missing "L2 コードが読む config キーが README の表にある" "$SELF/.l2a" "$SELF/.l2b"
rm -f "$SELF"/.l2a "$SELF"/.l2b

echo "== L3: 参照の健全性（付録・skill・節番号）=="
# 「詳細は protocol-X.md」と書いておいて中身が無い／ファイルが無い、が実際に起きた
_bad=""
for ref in $(grep -rho 'protocol-[a-z]*\.md' "$SKILLS"/aidev-*/ 2>/dev/null | sort -u); do
  [ -f "$SKILLS/aidev-00-start/$ref" ] || _bad="$_bad $ref"
done
[ -z "$_bad" ] && ok "L3 参照されている protocol-*.md が実在する" || ng "L3 実在しない付録を参照している:$_bad"
_bad=""
for f in "$SKILLS"/aidev-00-start/protocol-*.md; do
  b=$(basename "$f")
  grep -q "\`$b\`" "$SKILLS/aidev-00-start/protocol.md" || _bad="$_bad $b"
done
[ -z "$_bad" ] && ok "L3 全ての付録が protocol.md の付録表から辿れる" || ng "L3 protocol.md から辿れない付録:$_bad"
_bad=""
for ref in $(grep -rho 'aidev-[0-9][0-9]-[a-z][a-z]*\|aidev-util-[a-z][a-z]*' "$SKILLS"/aidev-*/*.md 2>/dev/null | sort -u); do
  [ -d "$SKILLS/$ref" ] || _bad="$_bad $ref"
done
[ -z "$_bad" ] && ok "L3 参照されている skill ディレクトリが実在する" || ng "L3 実在しない skill を参照:$_bad"

echo "== L4: schema 版の同期 =="
_ss=$(sed -n 's/^CURRENT_SCHEMA=\([0-9]*\).*/\1/p' "$SH" | head -n1)
_ps=$(sed -n 's/^\$script:CURRENT_SCHEMA = \([0-9]*\).*/\1/p' "$PS" | head -n1)
[ -n "$_ss" ] && [ "$_ss" = "$_ps" ] && ok "L4 CURRENT_SCHEMA が sh と ps1 で一致（$_ss）" \
  || ng "L4 CURRENT_SCHEMA が食い違う（sh=$_ss ps1=$_ps）"
grep -q "CURRENT_SCHEMA = $_ss" "$BREADME" && ok "L4 現行 schema が bin/README に載っている" \
  || ng "L4 bin/README の「現行 CURRENT_SCHEMA」が $_ss になっていない"
grep -q "schema ≥ $_ss の検査\|schema $_ss=" "$BREADME" && ok "L4 schema $_ss で足した不変条件が README の履歴にある" \
  || ng "L4 schema $_ss の検査内容が bin/README の履歴に無い（版を上げたら何を足したか書く）"

echo "== L5: 実行時文書をまたぐ重複文 =="
# 「本文の在処は常に1箇所」の機械化。**意図的な再掲は下の許可リストに理由つきで登録する**
# （skip 件数の申告と同じ考え方——見えなくするのではなく、数えて見えるようにする）
ALLOW=$SELF/lint-docs.allow
grep -v '^#\|^$' "$ALLOW" > "$SELF/.l5allow"
runtime_docs | while read -r f; do
  # frontmatter（`---` で挟まれた先頭ブロック）は除く。`allowed-tools:` の行は
  # 工程をまたいで同じで当たり前で、重複として報告しても直しようがない
  awk -v n="$f" '
    NR == 1 && $0 == "---" { fm = 1; next }
    fm && $0 == "---" { fm = 0; next }
    fm { next }
    { s = $0
      sub(/^[ \t]*[-*][ \t]*/, "", s); sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s)
      if (s ~ /^#/ || s ~ /^\|/ || s ~ /^```/) next
      if (length(s) >= 60) print n "\t" s }
  ' "$f"
done | sort -t'	' -k2 > "$SELF/.l5"
awk -F'\t' '
  { if ($2 == prev) { c++; files = files " " $1 } else { if (c > 1) print c "\t" files "\t" prev; c=1; files=$1; prev=$2 } }
  END { if (c > 1) print c "\t" files "\t" prev }
' "$SELF/.l5" > "$SELF/.l5dup"
_dupn=0; _dupout=""
while IFS='	' read -r n files line; do
  [ -n "$line" ] || continue
  # 同一ファイル内の重複は L5 の対象外（節をまたぐ意図的な再掲がある）
  _u=$(printf '%s' "$files" | tr ' ' '\n' | grep -v '^$' | sort -u | wc -l)
  [ "$_u" -lt 2 ] && continue
  grep -Fqf "$SELF/.l5allow" - <<EOF2 && continue
$line
EOF2
  _dupn=$((_dupn+1))
  _dupout="$_dupout  - $(printf '%s' "$files" | tr ' ' '\n' | grep -v '^$' | sed "s|$SKILLS/||" | sort -u | tr '\n' ' ')
    $(printf '%s' "$line" | cut -c1-80)
"
done < "$SELF/.l5dup"
if [ "$_dupn" -eq 0 ]; then ok "L5 実行時文書をまたぐ未登録の重複文が無い"
else ng "L5 実行時文書をまたぐ重複文が $_dupn 件（正典を1つに決めて参照にするか、理由つきで $(basename "$ALLOW") に登録する）"; printf '%s' "$_dupout" >&2; fi
rm -f "$SELF/.l5" "$SELF/.l5dup" "$SELF/.l5allow"

echo "== L6: 実行時に読む量の予算 =="
# 全 work が払うコスト。**増やすなら意図的に**（この数を書き換えるコミットで理由を述べる）。
# 減るぶんには落とさない（削減は歓迎）
BUDGET_PROTOCOL=589
BUDGET_TOTAL=3310
_p=$(wc -l < "$SKILLS/aidev-00-start/protocol.md")
_t=$(runtime_docs | xargs wc -l 2>/dev/null | tail -n1 | awk '{print $1}')
[ "$_p" -le "$BUDGET_PROTOCOL" ] && ok "L6 protocol.md が予算内（$_p / $BUDGET_PROTOCOL 行）" \
  || ng "L6 protocol.md が予算超過（$_p / $BUDGET_PROTOCOL 行）。要約は protocol.md・詳細は付録・理由は DESIGN"
[ "$_t" -le "$BUDGET_TOTAL" ] && ok "L6 実行時文書の合計が予算内（$_t / $BUDGET_TOTAL 行）" \
  || ng "L6 実行時文書の合計が予算超過（$_t / $BUDGET_TOTAL 行）"

echo
printf 'LINT: pass=%s fail=%s\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
