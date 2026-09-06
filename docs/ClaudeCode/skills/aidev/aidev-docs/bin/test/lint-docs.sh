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

echo "== L7: help ヘッダのオプションが実装の使用法と揃っている =="
# L1 は**動詞**の同期しか見ない。動詞が在るまま**オプションだけ落ちる**ドリフトは素通りし、
# 実際 `worktree add` の help から `--backlog` / `--profile|--light` が落ちていた
# （2026-09-04 の実走で発覚。`--backlog` を落とすと deliver の消し込み強制が静かに外れる）。
# 正典は実装が die で出す「使用法:」文字列——利用者が失敗したとき実際に見る文面だから。
# 突き合わせの粒度は**コマンドの第1語**（`worktree` / `harness` / `new` …）。help は
# 1行に複数の下位コマンドを畳むことがあり（`harness confirm ... / retire ...`）、
# 下位コマンド単位で対応づけると畳んだ行を取り落として誤検出する。
l7() { # file usage_prefix header_prefix
  _f=$1; _pre=$2; _hpre=$3
  # 実装の「使用法: <pre> <語...> [--x]」から、第1語ごとのフラグ集合を作る
  sed -n "s/.*使用法: $_pre \([a-z][a-z-]*\).*/\1/p" "$_f" | sort -u | while read -r _w; do
    [ -n "$_w" ] || continue
    _want=$(grep "使用法: $_pre $_w" "$_f" | grep -o -- '--[a-zA-Z][a-zA-Z-]*' | sort -u)
    [ -n "$_want" ] || continue
    # help ヘッダ側: 先頭のコメント塊のうち `<pre> <語>` を含む行と、その継続行
    # BOM を落としてから見る。ps1 は BOM 付きなので 1 行目が `^#` に当たらず、
    # 落とさないと **ヘッダ塊が空のまま素通り**する（ps1 側が 1 件も検査されない）
    _have_raw=$(awk -v pre="$_hpre" -v w="$_w" -v bom="$(printf '\357\273\277')" '
      NR == 1 { sub("^" bom, "") }
      { sub(/\r$/, "") }
      $0 !~ /^#/ { exit }
      { line = $0; sub(/^#[ \t]*/, "", line) }
      # 行が ` ...` で終わる＝「オプションは正典（sh 冒頭）を見よ」と明示的に畳んだ形。
      # ps1 の help は sh を写した要約で、正典は sh 側（ps1 冒頭 5 行目にそう書いてある）。
      # 畳んだ宣言まで不足と数えると、要約であることを許さない検査になる
      index(line, pre " " w) == 1 { on = 1; if (line ~ / \.\.\.$/) print "@@ABBREV@@"; print; next }
      index(line, pre " ") == 1 { on = 0; next }
      on { print }
    ' "$_f")
    _have=$(printf '%s\n' "$_have_raw" | grep -o -- '--[a-zA-Z][a-zA-Z-]*' | sort -u)
    case "$_have_raw" in *'@@ABBREV@@'*) continue ;; esac
    printf '%s\n' "$_want" > "$SELF/.l7w"
    printf '%s\n' "$_have" > "$SELF/.l7h"
    _m=$(grep -vxF -f "$SELF/.l7h" "$SELF/.l7w" | tr '\n' ' ' | sed 's/[ ]*$//')
    [ -n "$_m" ] && printf '%s %s: %s\n' "$_pre" "$_w" "$_m"
  done
}
# ps1 の使用法文字列は sh と同じ「使用法: aidev ...」だが、help ヘッダは
# 「pwsh .claude/skills/aidev-docs/bin/aidev.ps1 ...」と綴る。前置きを別に取る
# （揃えたつもりで ps1 側が 1 件も突き合わされていない、という無言の素通りを避ける）
_l7=$( { l7 "$SH" aidev aidev
         l7 "$PS" aidev 'pwsh .claude/skills/aidev-docs/bin/aidev.ps1'; } )
rm -f "$SELF/.l7w" "$SELF/.l7h"
if [ -z "$_l7" ]; then ok "L7 help ヘッダに実装の使用法のオプションが揃っている"
else ng "L7 help ヘッダに載っていないオプションがある（利用者は help しか見ない）"; printf '%s\n' "$_l7" | sed 's/^/    /' >&2; fi

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
BUDGET_PROTOCOL=608
# 3395 -> 3410: doccheck の追加に伴う増加。内訳と根拠（すべて実走で必要と分かったもの）:
#   protocol-autonomous「安全弁」に独立点検 +3（autonomous の必須事項一覧から到達できず、
#     一覧だけ読んだ実行者は schema 11 の必須記録に辿り着けなかった）
#   protocol-check「(a)」の起動経路・report のタイミング・対象工程の限定 +5
#     （起動経路が spec/design だけの古い記述で、requirement/plan の経路が「存在しない」ことになっていた）
#   protocol-analysis に doc_check_* の読み方 +2（刻んだメトリクスの使い道が未定義だった）
#   aidev-00-start に --backlog-item +2（打たないと status の HELD が行単位で出ない）
#   各 SKILL の doccheck 行 +3（正典は protocol-check。ここは引き金と打つコマンドだけ）
# 3410 -> 3412: 実走で「書いてあるのに機械が一度も通らない」経路が 1 本見つかったぶん。
#   protocol.md「運用方針」に CLI の実体パス +2（各 skill のコマンド例は裸の `aidev` で、
#     PATH は誰も通していない。`aidev-00-start` を読まずに工程 skill を直接叩く運用——
#     同じ節が明示的に許している経路——では最初のコマンドで止まっていた）
#   任意3工程（research / design / walkthrough）の `event <工程> start` は**行を増やさず**
#     既存の guard 行を書き換えて足した（打たないと `verify --strict` が exit 5 になる経路）
# 3412 -> 3417: plan モードの入り方・抜け方を「使ってよい」から**実行できる指示**にしたぶん。
#   protocol-autonomous「plan モードとの関係」+5（役割だけの言い方では丁寧に計画するだけで
#     モードは切り替わらない／抜けた先は元のモードではない／ハーネス側から切り替える口が無い、の 3 点。
#     どれも「書いてあるのに実行できない」を生む差で、裏取りは DESIGN「2.」）
# 3417 -> 3422: 実走が見つけた「書いてあるのに実行できない」を塞いだぶん。
#   protocol-autonomous「plan モードとの関係」+5（承認者がいない工程で入ると**抜けられない**＝
#     autonomous で工程が完走できなくなる、という一番痛い帰結が書かれていなかった。
#     併せて「使う／使わない」を「入る／入らない」の命令形に直し、humanGates の部分自律を
#     条件に含めた——実走が「承認者がいるのに促しを止めている」を実測した）
# 3422 -> 3426: **判断基準を書いていなかった**ぶん（外部レビューの読み合わせで発覚）。
#   protocol-autonomous「plan モードとの関係」+4。工程ごとの可否だけが列挙され、
#   **11 工程のうち requirement と walkthrough が どちらのリストにも無かった**。
#   さらに除外理由の一部が「実装計画ではない」で、**論点がずれていた**——plan モードで
#   禁じられるのは Write/Edit だけで対話は動くので、それは理由にならない。
#   本当の基準（「二重ゲートに見合うか」＝承認する対象がゲートと違うか）は DESIGN「2.」に
#   あったが実行時文書に無く、**各工程の可否が基準から導かれていなかった**。
#   基準を 1 行書けば全工程が導出できるので、列挙を短くしたぶんを差し引いて +4 に収まる
# 3426 -> 3429: 基準だけでは **11 工程のうち 9 しか導出できなかった**ぶん（実走が実測）。
#   protocol-autonomous「plan モードとの関係」+3。足りなかったのは 3 点:
#   (1)「aidev のゲート」が**その工程だけか上流を含むか**が未定義で、素直に読むと
#      coding が「入る」に化けた（`tasks.md` は plan のゲートが承認済み、と読ませる必要がある）
#   (2) research は**基準の外の規則**（純粋な調査は「2.6」の委譲）なのに、基準から導けるように
#      並んでいたので spec と同じ形に見えた
#   (3) walkthrough の除外理由が「成果物がその工程の判断そのもの」で、
#      **説明文書である walkthrough には当てはまっていなかった**（結論は同じだが理由が嘘）
# 3429 -> 3434: **基準が前提を 1 つ書いていなかった**ぶん（外部レビューの読み合わせで発覚）。
#   protocol-autonomous「plan モードとの関係」+5。基準（「二重ゲートに見合うか」）は
#   **既存のゲートが機械で止まること**を前提にしているが、文面はそれを見ていない。
#   止まらないゲートしか無い工程・環境では、plan モードは二重化ではなく**ゲートの実体化**で、
#   同じ基準から逆の結論が出る。「2.10」が CLI 無しの環境を「手で同等に」と認めている以上、
#   **ハーネス自身の想定範囲の内側で前提が崩れる**。
#   **前提の欠落は文面の整合では捕まらないので lint を作れない**——だから
#   「いつ読み直すか」（移植のとき・ゲートの無い工程を足すとき）を本文に書いた。
#   検査できないものを検査できるふりで置かない、という DESIGN「2.」の態度の適用でもある
# 3434 -> 3438: 前提の書き方が**曖昧で、しかも別の規約と衝突していた**ぶん（実走が実測）。
#   protocol-autonomous「plan モードとの関係」+4。
#   (1)「2.10 が『手で同等に』と認めている」だけでは、**手のゲートが「機械で止まる」に
#      当たるのか当たらないのか**が 2 通りに読めた（正典に決着が無く、DESIGN にしか無かった）
#      → 判定を 1 つに固定した（`guard <工程>` が exit≠0 で止まるか）
#   (2) 新しい前提の行だけを読むと「入る」に倒れるが、下の「承認者がいない工程で入ると
#      **抜けられない**」と衝突する。**新しい行だけを読んだ実行者は入って詰む**
#      → 見る順（承認者 → 二重ゲート）を明記した
# 3438 -> 3449: **除外理由を 2 つとも間違えていた**ぶん（対話で発覚）。
#   protocol-autonomous +7 / aidev-30-plan +2 / aidev-00-start -1。
#   requirement の除外理由「方針と成果物が分離できない」は **spec / design にもそのまま
#   当てはまり、区別になっていなかった**（結論に貼った後付けのラベル）。
#   そこで「行動計画 vs 仕様」という分類を作って plan を外したが、**これも逆だった**——
#   `ExitPlanMode` の定義が「planning the **implementation steps**」なので、
#   plan 工程と種類が同じことは**除外の理由ではなく最も適合する証拠**。
#   **手元にツール定義があるのに読まずに分類を発明した**のが両方の原因。
#   **plan モードの機能と思想を調べ直した**結果、買えるのは「コード探索中の read-only 強制」で、
#   機能も思想も「触る前にコードを読む」に収束していた（EnterPlanMode: explore the codebase）。
#   これを (b) に据えると、**requirement は主活動がユーザーへのヒアリング**（入力は
#   「要望・課題・背景」でコードは「必要に応じて参照してよい」）なので外れる。
#   一度 EnterPlanMode の "Unclear Requirements" を根拠に入れたが、その例は
#   「profile して bottleneck を見つける」＝**コード探索でスコープを掴む**話で、
#   人から要件を聞き出す話ではなかった（引用が不正確だった）。
#   副産物: research の除外に一次根拠が付いた——EnterPlanMode の WHEN NOT TO USE が
#   「Pure research/exploration tasks (use the Agent tool instead)」と言っており、
#   ハーネスの「2.6 の委譲が正」と一致する。「基準の外の規則」ではなくなった。
#   (b) は aidev-00-start の三層判定を外すためにも要る——(a) だけだと
#   「二重でないから入ってよい」が言えてしまう（読むだけで書く対象が無いのに）
# 3449 -> 3450: 基準を **`ExitPlanMode` の用途規定**に据え直したぶん（外部レビューの読み合わせ）。
#   protocol-autonomous「plan モードとの関係」+1（差し引き）。
#   `EnterPlanMode`（入口）の WHEN TO USE を基準にしていたが、**承認を出すのは `ExitPlanMode` だけ**で、
#   そこには「planning the **implementation steps** … For **research** … do NOT use」と書いてある。
#   出口の制約を見ていなかったので `requirement`（何を・なぜ＝実装計画ではない）が入っていた。
#   据え直すと **`research` も基準内で落ちる**ので、「基準の外の規則」という特例が 1 つ消える。
#   併せて **plan file と成果物の書く順序**（探索→plan file→承認→抜ける→清書）を明記した——
#   逆順だと plan file が写しになり、それが「計画を二度書く」の正体
BUDGET_TOTAL=3450
_p=$(wc -l < "$SKILLS/aidev-00-start/protocol.md")
_t=$(runtime_docs | xargs wc -l 2>/dev/null | tail -n1 | awk '{print $1}')
[ "$_p" -le "$BUDGET_PROTOCOL" ] && ok "L6 protocol.md が予算内（$_p / $BUDGET_PROTOCOL 行）" \
  || ng "L6 protocol.md が予算超過（$_p / $BUDGET_PROTOCOL 行）。要約は protocol.md・詳細は付録・理由は DESIGN"
[ "$_t" -le "$BUDGET_TOTAL" ] && ok "L6 実行時文書の合計が予算内（$_t / $BUDGET_TOTAL 行）" \
  || ng "L6 実行時文書の合計が予算超過（$_t / $BUDGET_TOTAL 行）"

echo "== L9: 判定条件の写しを工程 SKILL に作らない =="
# **条件を skill に写した時点で、次の変更での取り残しが予約される**。実際に起きた——
# `guard` の promote 条件を「mode」から「その工程に承認者がいるか」へ変えたとき、CLI と
# `protocol-autonomous.md` は直したのに、spec / design の SKILL.md に写した
# `（full × interactive のみ）` が残り、**部分自律で CLI は促すのに skill は「入るな」と読める**
# 状態になった（外部レビューが実測）。
# 規律自体は既にあった——`doccheck` では「正典は protocol-check。ここは引き金と打つコマンドだけ」
# として条件を写していない（上の L6 の内訳コメント）。**規律はあったのに守られなかった**ので、
# 分類 G と同じ扱いで観測点にする。
#
# **検査するのは「plan モードに言及する行が、判定に使う語を抱えていないか」**。
# 外部レビューは「判定キー（profile / mode / humanGates）が SKILL 本文に出たら WARN」を
# 提案したが、**それでは今回の欠陥を捕まえられない**——残っていた文言は
# `full` × `interactive` で、キー名を 1 つも含んでいなかった。値の側も見る必要がある。
# 対象を「plan モードの行」に絞るのは、`profile: light` 等の**正当な言及**が
# 工程 SKILL に多数あるため（13 ファイル。全部を弾くと誤検知だらけになる）。
# **初版は「plan モードを含むその 1 行」しか見ておらず、4 通りで素通りした**（実走が実測）。
#   H1 条件を継続行へ送る——**現行の文体そのものが 2 行構成**なので一番踏みやすい
#   H2/H5/H6 現行条件を自然語や CLI フラグ綴りで写す（「承認者がいるときだけ」「--human-gates」
#           「対話モードで、簡易プロファイルでないとき」）
#   H3/H4 表記ゆれ（`planモード` / `plan mode`）
#   H7 対象ファイル外へ写す（`aidev-util-*` / `protocol*.md` / `DESIGN.md`）——実際に
#      `DESIGN.md` と `protocol.md` に旧条件が生き残っていた
# **見出し語のゆれを吸収し、継続行まで見て、対象を実行時文書＋参照文書に広げる**。
# 正典（`protocol-autonomous.md` の当該節）だけを除外する。
# **`aidev-docs/*.md` を明示的に足すのが要点**——初版は「実行時文書ぜんぶ」に広げたと書きながら
# `runtime_docs` を使っていたので、**旧条件が実際に残っていた `DESIGN.md` に永久に届かなかった**
# （`README.md` に残った 2 件も同じ理由で機械に一度も見えていなかった。実走が実測）。
# **`runtime_docs` と SKILL のグロブは全工程 SKILL で重なる**ので、和集合を取ってから走査する。
# 重ねたまま回すと同じファイルを 2 回数え、1 件の写しが「2 ファイル」と出た
# （`runtime_docs` 自身のコメントが同じ罠を警告しているのに、その隣で再発させた）
PMHEAD='plan ?モード|planモード|plan mode'
# **改修のたびに語彙を足す**。足さないと「旧条件の写し」しか捕まえられず、**新条件の写しは
# 全部素通りする**（実走が H10-H13 で実測）。工程名の列挙（`spec / design / plan` の形）も条件の写し
PMKEY='profile|humanGates|human-gates|interactive|autonomous|full[^ ]* *×|light|承認者|対話モード|自律モード|プロファイル|機械で止ま|ゲートの実体化|exit code|read-only|主活動|ヒアリング|既存コード|コード探索|方向が複数|選び損な|上流4工程|spec *[/／] *design'
_l9=0
# `runtime_docs` は `$d/SKILL.md`（`$d` は末尾 `/`）を出すので **`//` を含む**。
# 潰さないと `sort -u` が別物として残し、二重走査がそのまま生き残る（テストで実測）
for _f in $({ runtime_docs
              printf '%s\n' "$SKILLS"/aidev-*/SKILL.md "$SKILLS"/aidev-docs/*.md \
                             "$SKILLS"/aidev-docs/bin/README.md; } \
             | sed 's://*:/:g' | LC_ALL=C sort -u); do
  [ -f "$_f" ] || continue
  case "$_f" in *protocol-autonomous.md) continue ;; esac  # 正典。ここには条件が在ってよい
  # **見出し行とその継続行**（行頭が空白で始まる後続行）をひとまとまりで見る。
  # 正典への参照そのものは条件ではない（ファイル名が `autonomous` を含む）ので落とす
  _hits=$(awk -v head="$PMHEAD" '
      # **見出しより前は切り落とす**。plan モードの可否を縛る条件は見出しの後ろに来るので、
      # 同じ行の無関係な前置き（`humanGates` で部分的に人間ゲートを残せる。plan モードは…）を拾わない
      function ltrim(x) { sub(/^[ \t]+/, "", x); return x }
      $0 ~ head { inb=1; ln=NR; buf=substr($0, match($0, head))
                  ind=length($0) - length(ltrim($0)); next }
      # **継続行は「字下げされていて、新しい箇条書きでも表の行でもない行」**。
      # 字下げだけで見ると隣の箇条書きや次の表の行まで飲み込んで誤検知した（両方とも実際に踏んだ）
      # **より深く字下げされた箇条書きは「子」なので取り込む**。打ち切っていた頃は
      # `- plan モードの扱い` の下にぶら下げた条件が原理的に見えず、`DESIGN.md` の
      # `  - **使う**:` 以下の列挙もまるごと素通りしていた（実走が H8 で実測）。
      # 打ち切るのは**同じ深さ以下**の箇条書き・表の行だけ
      inb && /^[ \t]+/ && (!/^[ \t]*([-*+|]|[0-9]+\.)/ || length($0) - length(ltrim($0)) > ind) {
        buf=buf " " $0; next }
      inb { print ln ": " buf; inb=0 }
      END { if (inb) print ln ": " buf }
    ' "$_f" | sed 's/protocol-autonomous\.md//g' | grep -E "$PMKEY") || true
  # **`DESIGN.md` は「なぜその基準にしたか」を書く場所**なので、規則に触れる行が正当に在る。
  # 全部弾くとノイズになり、全部許すと**旧条件がそこに生き残る**（実際に 3 箇所生き残った）。
  # L5 と同じ形——**理由つきで登録した行だけ免除する**（`lint-docs.allow` の `L9:` 行）
  if [ -n "$_hits" ] && [ -f "$ALLOW" ]; then
    _hits=$(printf '%s\n' "$_hits" | while IFS= read -r _hl; do
      _ok=no
      while IFS= read -r _al; do
        case "$_al" in ''|\#*) continue ;; L9:*) ;; *) continue ;; esac
        _ap=${_al#L9:}
        case "$_hl" in *"$_ap"*) _ok=yes; break ;; esac
      done < "$ALLOW"
      [ "$_ok" = yes ] || printf '%s\n' "$_hl"
    done)
  fi
  [ -n "$_hits" ] || continue
  _l9=$((_l9 + 1))
  printf '%s:\n%s\n' "${_f#"$SKILLS"/}" "$_hits" >&2
done
if [ "$_l9" -eq 0 ]; then ok "L9 plan モードの判定条件が正典の外に写されていない"
else ng "L9 plan モードの判定条件の写しが $_l9 ファイル（正典は protocol-autonomous.md「plan モードとの関係」だけ。他所には引き金と参照だけを置く）"; fi

echo "== L8: ハーネス改修の実走記録 =="
# **「改修のたびに実走を1本通す」は DESIGN「3.5」に書いてあったのに、次の改修で破られた**
# （doccheck の追加。テストと lint で止めた）。分類 G（散文にしか無い規約）そのものなので、
# 扱いも同じ——観測点を作る。L1〜L7 は表面の整合しか見ないので、
# 「書いてある規約が実際に発火するか」はここでしか担保できない。
FLOWDIR=$SELF/flow-runs
# git の pathspec は $SKILLS からの相対で渡す（絶対パス + :(exclude) は環境差が出る）
FLOWREL=aidev-docs/bin/test/flow-runs
# 「改修」に数えないもの: 記録ファイル自身（数えると永久に追いつけない）と、
# **他 PJ から受け取った retro**（入力であって改修ではない）。マージコミットも数えない
# ——どちらも実走をやり直す理由にならないのに、L8 を鳴らして本物の警告を埋もれさせる
RETRO_REL=aidev-docs/retro
if ! command -v git >/dev/null 2>&1 || ! git -C "$SKILLS" rev-parse --git-dir >/dev/null 2>&1; then
  ok "L8 実走記録の鮮度（git 不在のため検査省略）"
else
  # 記録ファイル自身のコミットは「改修」に数えない（数えると永久に追いつけない）
  # **「最新の記録」は git のコミット時刻で選ぶ**。ファイル名の辞書順で選んでいた頃は、
  # 同じ日に 2 本置くとスラグ順で決まり、**古いほうを「最新」として表示し、
  # 3 見出しの検査も古い側に対して行っていた**（実走が実測）。1 日 2 回改修すれば必ず起きる。
  # git が無い／未コミットなら辞書順に落とす（判定自体はそのとき鮮度を見ないので実害が無い）
  _fr=""
  if git -C "$SKILLS" rev-parse --git-dir >/dev/null 2>&1; then
    _fr=$(for _ff in "$FLOWDIR"/[0-9]*.md; do
            [ -f "$_ff" ] || continue
            _ft=$(git -C "$SKILLS" log -1 --format=%ct -- "$_ff" 2>/dev/null)
            # **未コミットの記録は「いちばん新しい」**。記録は改修と同じコミットに載せる運用なので、
            # 書いた直後は必ず未コミットになる。0 に落とすと**いま書いた記録が最下位になり、
            # 古い記録を相手に鮮度を見る**（コミット時刻で選ぶようにした直後にこれを踏んだ）
            printf '%s\t%s\n' "${_ft:-9999999999}" "$_ff"
          done | LC_ALL=C sort -n -k1,1 | tail -n1 | cut -f2-)
  fi
  [ -n "$_fr" ] || _fr=$(ls "$FLOWDIR"/[0-9]*.md 2>/dev/null | LC_ALL=C sort | tail -n1)
  if [ -z "$_fr" ]; then
    ng "L8 実走記録が1件も無い（$FLOWDIR/<日付>-<slug>.md。書き方は同ディレクトリの README.md）"
  else
    _frc=$(git -C "$SKILLS" log -1 --format=%H -- "$FLOWREL" 2>/dev/null) || _frc=""
    if [ -z "$_frc" ]; then
      ok "L8 実走記録あり（未コミットなので鮮度は判定しない）: $(basename "$_fr")"
    else
      # 記録より後に入った「実質的な」ハーネス改修の本数（記録ディレクトリ自身は除く）
      _stale=$(git -C "$SKILLS" rev-list --no-merges --count "$_frc..HEAD" \
                 -- . ":(exclude)$FLOWREL" ":(exclude)$RETRO_REL" 2>/dev/null) || _stale=0
      case "$_stale" in ''|*[!0-9]*) _stale=0 ;; esac
      if [ "$_stale" -eq 0 ]; then
        ok "L8 実走記録が最新の改修をカバーしている: $(basename "$_fr")"
      else
        ng "L8 実走記録より後にハーネス改修が $_stale 本ある（$(basename "$_fr") 以降）。着地前に 3 ゲートを通し、$FLOWDIR に記録すること: (1) 文書が実態に追いついているか (2) README のメンテナンス (3) サブエージェントでの実走"
      fi
    fi
    # 3 見出しが揃っているか（記録の形が崩れると、あとから何を確かめたのか読めない）
    _miss=""
    for _h in "## 1. 文書は実態に追いついているか" "## 2. README のメンテナンス" "## 3. 実走（サブエージェント）"; do
      grep -qF "$_h" "$_fr" || _miss="$_miss [$_h]"
    done
    if [ -z "$_miss" ]; then ok "L8 実走記録に 3 ゲートの見出しが揃っている"
    else ng "L8 実走記録に見出しが足りない:$_miss（$(basename "$_fr")）"; fi
    # 未コミットのハーネス変更があれば、記録はそれを見ていない
    _dirty=$(git -C "$SKILLS" status --porcelain -- . ":(exclude)$FLOWREL" ":(exclude)$RETRO_REL" 2>/dev/null | grep -c . 2>/dev/null) || _dirty=0
    case "$_dirty" in ''|*[!0-9]*) _dirty=0 ;; esac
    [ "$_dirty" -gt 0 ] && printf '  note: 未コミットのハーネス変更が %s 件あります（実走記録はこれを見ていません）\n' "$_dirty"
  fi
fi

echo
printf 'LINT: pass=%s fail=%s\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
