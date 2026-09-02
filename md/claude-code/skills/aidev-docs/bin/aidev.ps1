#!/usr/bin/env pwsh
# aidev ランタイムガード CLI（PowerShell 版・Windows 向け / pwsh でも動作）
#
# POSIX sh 版（同ディレクトリの `aidev`）と挙動・出力・終了コードを一致させること。
# 役割と正典は `aidev` 冒頭コメント／protocol.md「4.1」を参照。
#
# 使い方:
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 new <slug> [--mode interactive|autonomous] [--profile full|light] [--light] [--ticket ID] [--depends a,b,#N] [--parent <親work>] [--backlog <file>]
#     --parent 指定時は親 work 配下に subtask（<NN>-<subslug>・date prefix なし・current=plan）を作る
#     --profile/--light は「どこまで工程を回すか」（protocol.md「11.」）。mode（誰が承認するか）と直交
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 escalate [slug]   # profile を light -> full に昇格（片方向）
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 event <phase> <start|sent_back> [key=value ...]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 approve <phase> [key=value ...]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 unapprove <phase> [--slug <work>]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 guard <phase>
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 verify [slug] [--strict]
#     --strict は記録漏れ(event の start 欠落)だけを致命(exit 5)にする（機械ゲート用）
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 doctor [--quiet]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 status [--format table|tsv] [--active]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 metrics [slug] [--all] [--phases] [--format table|tsv]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 convention <new|confirm|retire|defer|promote|status> ...
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 harness <new|confirm|retire|status> ...
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 backlog <new|archive|compact> ...
#     PJ規約の条項を docs/aidev/ で起こし・判定し・PJ ドキュメントへ移送する（protocol.md「12.」）
#     new は --hypothesis と --baseline が必須（検証できない条項を作らせない入口ゲート）
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 worktree add <slug> [--branch n] [--base ref] [--path dir] [--mode m] [--ticket id] [--depends list]

#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 worktree list [--format table|tsv]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 worktree rm <slug|path> [--force] [--delete-branch]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 help
#
# 終了コード: 0=OK / 1=使用法・環境エラー / 2=前提成果物の不足 / 3=依存未充足 / 4=不変条件違反

$ErrorActionPreference = 'Stop'
# git をネイティブ呼び出しする（worktree）。PS7.4+ の既定 throw-on-nonzero を無効化し、$LASTEXITCODE で判定する
# （git show-ref 等は ref 不在で 1 を返すのが正常系のため）。古い pwsh では通常変数になるだけで無害。
$PSNativeCommandUseErrorActionPreference = $false

$script:CURRENT_SCHEMA = 5   # schema 3=subtask 層(subtasks/activeSubtask/parent)導入。schema 4=harnessRev 刻印（効果検証の母集団特定）導入。schema 5=承認済み工程の成果物実在検査を導入。schema<=2 は legacy 免除
$script:STRICT = $false      # verify --strict（記録漏れを致命にする）。doctor 経由では常に false
$script:PHASES = @('requirement','research','spec','design','plan','coding','test','review','walkthrough','deliver','retro')
$script:Utf8 = New-Object System.Text.UTF8Encoding($false)  # BOM なし

# 標準出力/標準エラーを UTF-8 固定にする。既定ではコンソールの CP（日本語 Windows なら cp932）で
# エンコードされ、UTF-8 前提のパイプ先（grep 等）や sh 版との出力照合が壊れるため。
try { [Console]::OutputEncoding = $script:Utf8 } catch {}

function Die($m)  { [Console]::Error.WriteLine("aidev: $m"); exit 1 }
function Warn($m) { [Console]::Error.WriteLine("aidev: $m") }
function Now() {
  # 明示フォーマット（カルチャ/書式指定子の曖昧さを避け sh 版と完全一致させる）
  $d = [DateTime]::UtcNow
  return ('{0:D4}-{1:D2}-{2:D2}T{3:D2}:{4:D2}:{5:D2}Z' -f $d.Year,$d.Month,$d.Day,$d.Hour,$d.Minute,$d.Second)
}
function IsWindowsHost() {
  # $IsWindows は PowerShell Core のみ。Windows PowerShell 5.1 では未定義＝Windows。
  return (($null -eq $IsWindows) -or $IsWindows)
}
function PsHost() {
  # 自己呼び出しは「今動いているホスト」を使う。`pwsh` 決め打ちだと Windows PowerShell 5.1 しか
  # 入っていない素の Windows（pwsh は標準搭載ではない）で CommandNotFound になる。
  try {
    $exe = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    if ($exe) { return $exe }
  } catch {}
  if ($PSVersionTable.PSEdition -ceq 'Core') { return 'pwsh' } else { return 'powershell' }
}
function PsHostArgs($script) {
  # -ExecutionPolicy は Windows のみ有効（Linux/macOS の pwsh では不正オプション）
  $a = @('-NoProfile')
  if (IsWindowsHost) { $a += @('-ExecutionPolicy','Bypass') }
  return $a + @('-File', $script)
}

function PathKey($p) {
  # パス比較用の正規化キー。git worktree list は `C:/Users/...`（スラッシュ）を返すのに対し
  # .NET の解決結果は `C:\Users\...` なので、そのまま比較すると Windows で必ず不一致になる。
  if (-not $p) { return '' }
  try { $full = [System.IO.Path]::GetFullPath($p) } catch { $full = $p }
  return ($full -replace '\\','/').TrimEnd('/')
}

function WriteText($p,$t)  { [System.IO.File]::WriteAllText($p,$t,$script:Utf8) }
function AppendText($p,$t) { [System.IO.File]::AppendAllText($p,$t,$script:Utf8) }

# sh の [ -f ] / [ -d ] / [ -e ] に対応する述語。素の Test-Path はファイルもディレクトリも通し、
# しかもパスを**ワイルドカードとして解釈する**（`[` を含む slug で誤判定する）。sh 側は常に
# リテラルかつ種別つきなので、-LiteralPath と -PathType で揃える。
function IsFile($p)     { if (-not $p) { return $false }; return (Test-Path -LiteralPath $p -PathType Leaf) }
function IsDir($p)      { if (-not $p) { return $false }; return (Test-Path -LiteralPath $p -PathType Container) }
function PathExists($p) { if (-not $p) { return $false }; return (Test-Path -LiteralPath $p) }

# オプション値の取り出し口。`$rest[++$i]` を裸で書くと、値が欠けたとき $null を拾って
# 素通りし、sh 側（値必須で die）と違う結果になる。使い方エラーは sh と同じ die(rc=1) に揃える。
function ArgAt($arr, $i, $opt) {
  if ($i -ge $arr.Count) { Die "$opt には値が必要です" }
  return $arr[$i]
}

function FindRoot() {
  $d = (Get-Location).Path
  while ($true) {
    if (IsDir (Join-Path $d '.aidev')) { return $d }
    $parent = Split-Path $d -Parent
    if ([string]::IsNullOrEmpty($parent) -or $parent -eq $d) { break }   # パス比較は OS の流儀に従う
    $d = $parent
  }
  return $null
}

$script:ROOT = FindRoot
if (-not $script:ROOT) { Die ".aidev が見つかりません（リポジトリ内で実行してください）" }
$script:AIDEV = Join-Path $script:ROOT '.aidev'

function ResolveWork($slug) {
  # slug は top-level work（dated 名）か subtask のネストパス（<dated>/<NN>-<subslug>）。works/<slug> へ素直に連結する。
  if (-not $slug) { $slug = $env:AIDEV_WORK }
  if (-not $slug) {
    $cur = Join-Path $script:AIDEV 'current'
    if (-not (IsFile $cur)) { Die "対象作業が不明です（.aidev/current 無し）。new か slug 指定を。" }
    $slug = ([System.IO.File]::ReadAllLines($cur))[0].Trim()
  }
  $script:WORK = Join-Path (Join-Path $script:AIDEV 'works') $slug
  if (-not (IsDir $script:WORK)) { Die "work が存在しません: $slug" }
  $script:SLUG = $slug
}

# state.yml の key 行を差し替え、無ければ末尾に追記（subtasks/activeSubtask の冪等更新用）。
function SetOrAppend($file,$key,$newline) {
  $content = [System.IO.File]::ReadAllText($file)
  if ($content -match ("(?m)^" + [regex]::Escape($key) + ":")) { ReplaceLine $file $key $newline }
  else { AppendText $file ($newline + "`n") }
}

function IsPhase($p) { return $script:PHASES -ccontains $p }

# scalar 読み取り（前後空白と囲み二重引用符を除去）。inline コメント(#)は除去しない
# （ticket/dependsOn は '#18' 等 '#' 始まりの値を持つため）。sh の yget と一致。
function YGet($file,$key) {
  if (-not (IsFile $file)) { return '' }
  foreach ($line in [System.IO.File]::ReadAllLines($file)) {
    if ($line -match ("^" + [regex]::Escape($key) + ":\s*(.*)$")) {
      return (($Matches[1].Trim()) -replace '^"','' -replace '"$','')
    }
  }
  return ''
}

function YList($file,$key) {
  $v = (YGet $file $key).Trim()
  if ($v.StartsWith('[')) { $v = $v.Substring(1) }
  if ($v.EndsWith(']'))   { $v = $v.Substring(0, $v.Length - 1) }
  $v = $v -replace '"',''
  if ([string]::IsNullOrWhiteSpace($v)) { return @() }
  return @($v -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -cne '' })
}

function ApprovedHas($work,$phase) { return (YList (Join-Path $work 'state.yml') 'approved') -ccontains $phase }

function ReplaceLine($file,$key,$newline) {
  $lines = [System.IO.File]::ReadAllLines($file)
  $out = foreach ($l in $lines) { if ($l -match ("^" + [regex]::Escape($key) + ":")) { $newline } else { $l } }
  WriteText $file (($out -join "`n") + "`n")
}

function EnsureEvents($work) {
  $f = Join-Path $work 'metrics.yml'
  if (-not (IsFile $f)) { WriteText $f "events:`n"; return }
  $lines = [System.IO.File]::ReadAllLines($f)
  $changed = $false
  $out = foreach ($l in $lines) { if ($l -match '^events:\s*\[\]\s*$') { $changed = $true; 'events:' } else { $l } }
  if ($changed) { WriteText $f (($out -join "`n") + "`n") }
  $content = [System.IO.File]::ReadAllText($f)
  if ($content -notmatch '(?m)^events:') { AppendText $f "events:`n" }
}

function BuildEntry($phase,$event,$kvs) {
  $m = @()
  foreach ($kv in $kvs) {
    $i = $kv.IndexOf('=')
    if ($i -ge 0) { $k = $kv.Substring(0,$i); $val = $kv.Substring($i+1); $m += "${k}: $val" }
  }
  $base = "{ ts: $(Now), phase: $phase, event: $event"
  if ($m.Count -gt 0) { return "$base, metrics: { $([string]::Join(', ',$m)) } }" }
  return "$base }"
}

function AppendEvent($work,$phase,$event,$kvs) {
  EnsureEvents $work
  AppendText (Join-Path $work 'metrics.yml') ("  - " + (BuildEntry $phase $event $kvs) + "`n")
}

# --- new ---------------------------------------------------------------------
# --- ハーネス版（効果検証の母集団特定） -------------------------------------------
# その work が**どの版のハーネスで回されたか**が無いと、改修が効いたかを後から判定できない。
# 刻印を手書きに任せると忘れられ、忘れられた work は母集団から静かに漏れる（schema: と同じ理由で new に一本化）。
# 版の実体は「ハーネス・ディレクトリを最後に触ったコミット」。取れない環境では捏造せず 'unknown'。
# 浅いパスに置くと内側の Split-Path が空を返し、外側が例外でスクリプトごと落ちる（=全コマンドが死ぬ）。
# sh の dirname は '/' を返し続けるので落ちない。取れなければ空にして HarnessRev を unknown に倒す
$script:HARNESS = try { Split-Path -Parent (Split-Path -Parent $PSScriptRoot) } catch { '' }   # <skills>/aidev-docs/bin -> <skills>

function HarnessRev() {
  if (-not $script:HARNESS) { return 'unknown' }
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return 'unknown' }
  # 見る範囲は aidev-* の skill だけ。<skills> 全体を見ると、同居する無関係な skill の変更でも
  # 版が上がり、その間に走った work が全部「またがり」に見える。またがり判定は母集団からの
  # 除外なので、誤検知はそのまま効果検証の母集団を痩せさせる。
  try {
    $paths = @(Get-ChildItem -LiteralPath $script:HARNESS -Directory -Filter 'aidev-*' -ErrorAction SilentlyContinue |
               ForEach-Object { $_.FullName })
    if ($paths.Count -eq 0) { return 'unknown' }
    # 版の実体は内容の tree hash（コミット SHA だと squash / rebase で同一内容が別版に割れる。sh 版と同じ）
    $trees = @(& git -C $script:HARNESS ls-tree -d HEAD -- @paths 2>$null | ForEach-Object { ($_ -split '\s+')[2] })
    if ($trees.Count -eq 0) { return 'unknown' }
    # stdin パイプは使わない: PowerShell は native コマンドへ渡すとき自分で改行を足し、しかも
    # Windows では CRLF になるので sh 版（LF）と別のハッシュになる。LF 固定の一時ファイルで渡す
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
      [System.IO.File]::WriteAllText($tmp, (($trees -join "`n") + "`n"), $script:Utf8)
      $r = (& git hash-object -- $tmp 2>$null | Select-Object -First 1)
    } finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    if ([string]::IsNullOrWhiteSpace($r)) { return 'unknown' }
    return $r.Trim().Substring(0, 12)
  } catch { return 'unknown' }
}

# --- 条項（docs/aidev の PJ規約）---------------------------------------------------
# ハーネスが生成した規約は PJ 所有の AGENTS.md / CLAUDE.md に書き込まない（protocol.md「12.」）。
# docs/aidev/ は終着点ではなく**検証中の待避所**で、条項は必ずここから出ていく
#（効果あり -> PJ ドキュメントへ移送 / 効果なし・置換 -> 退役）。本文の在処を常に1箇所に保つ。
function CvDir() {
  $d = YGet (Join-Path $script:AIDEV 'config.yml') 'conventionsDir'
  if (-not $d) { $d = 'docs/aidev' }
  if ([System.IO.Path]::IsPathRooted($d)) { return $d }
  return (Join-Path $script:ROOT $d)
}

# 条項ファイル先頭 frontmatter から key を読む（sh の cv_get と一致）。
function CvGet($path,$key) {
  if (-not (IsFile $path)) { return '' }
  $lines = [System.IO.File]::ReadAllLines($path)
  if ($lines.Count -eq 0 -or $lines[0] -notmatch '^---\s*$') { return '' }
  for ($i=1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^---\s*$') { return '' }
    if ($lines[$i] -match ("^" + [regex]::Escape($key) + ":\s*(.*?)\s*$")) { return $Matches[1] }
  }
  return ''
}

# frontmatter 内の key を差し替え、無ければ frontmatter 末尾に足す（冪等）。
function CvSet($path,$key,$value) {
  $lines = [System.IO.File]::ReadAllLines($path)
  $out=@(); $fm=0; $done=$false
  for ($i=0; $i -lt $lines.Count; $i++) {
    $l = $lines[$i]
    if ($i -eq 0 -and $l -match '^---\s*$') { $out += $l; $fm=1; continue }
    if ($fm -eq 1 -and $l -match '^---\s*$') {
      if (-not $done) { $out += "${key}: $value" }
      $out += $l; $fm=2; continue
    }
    if ($fm -eq 1 -and $l.StartsWith("${key}:")) { $out += "${key}: $value"; $done=$true; continue }
    $out += $l
  }
  WriteText $path (($out -join "`n") + "`n")
}

# 本文を捨てて tombstone にする（本文が2箇所に存在する瞬間を作らない）。
function CvTombstone($path,$msg) {
  $lines = [System.IO.File]::ReadAllLines($path)
  $out=@(); $fm=0
  for ($i=0; $i -lt $lines.Count; $i++) {
    $l = $lines[$i]
    if ($i -eq 0 -and $l -match '^---\s*$') { $out += $l; $fm=1; continue }
    if ($fm -eq 1 -and $l -match '^---\s*$') { $out += $l; $out += ''; $out += $msg; $fm=2; break }
    if ($fm -eq 1) { $out += $l }
  }
  WriteText $path (($out -join "`n") + "`n")
}

# id は必ずここで潰す——`../foo` のような値をそのまま連結すると、条項ディレクトリの外の
# ファイルを confirm/retire/promote が破壊・移動できてしまう（Cv-New だけが潰していた）。
function CvId($id) {
  $i = Split-Path -Leaf $id
  if ($i.EndsWith('.md')) { $i = $i.Substring(0, $i.Length-3) }
  if (-not $i -or $i -ceq '.' -or $i -ceq '..') { Die "id が不正です: $id" }
  return $i
}

function CvFind($id) {  # active 優先、無ければ archive。見つからなければ ''
  $d = CvDir
  $i = CvId $id
  $a = Join-Path $d "$i.md"
  if (IsFile $a) { return $a }
  $b = Join-Path (Join-Path $d 'archive') "$i.md"
  if (IsFile $b) { return $b }
  return ''
}

# 条項ファイルであることを確かめる。frontmatter が無いものに CvTombstone をかけると
# 本文が丸ごと消えるため、破壊的な操作の前に必ず通す。
function CvRequire($path) {
  $lines = [System.IO.File]::ReadAllLines($path)
  if ($lines.Count -eq 0 -or $lines[0].TrimEnd() -cne '---') {
    Die "条項ファイルではありません（frontmatter が無い）: $path"
  }
  if (-not (CvGet $path 'convention') -and -not (CvGet $path 'status')) {
    Die "条項ファイルではありません（convention / status がどちらも無い）: $path"
  }
}

# 退避先が空いているか。破壊的な操作の前に呼べるよう、移動本体と分けてある。
function CvArchiveFree($path) {
  $d = CvDir
  $b = Split-Path -Leaf $path
  # sh は [ -e ]。種別を問わず「そこに何かある」なら止める——ここは**破壊の前の衝突検査**なので、
  # ディレクトリを見逃すと Move-Item がその中へ移し、本文の在処が想定外の場所になる
  if (PathExists (Join-Path (Join-Path $d 'archive') $b)) {
    Die "archive に同名があります: $(Join-Path (Join-Path $d 'archive') $b)"
  }
}

# 母集団＝その条項の導入日以降に着手し、**かつ deliver 済み**の work の件数。
#  - 導入前から走っていた work は条項の効果を半分しか受けていない。
#  - 着手しただけの work は review を通っていない＝判定材料を1つも産んでいない。数えると
#    レビュー記録が無いのに ready=yes が立ち、insights が空の材料で判定してしまう。
# ts（YYYY-MM-DD / YYYY-MM-DDTHH:MM:SSZ）→ 比較用の 14 桁 YYYYMMDDHHMMSS。
# 日付だけの値は 00:00:00 扱い（introduced が日付粒度だった旧条項の後方互換）。8 桁未満なら ''
function CvTsKey($ts) {
  $k = ("$ts" -replace '[^0-9]','')
  if ($k.Length -lt 8) { return '' }
  return ($k + '00000000000000').Substring(0,14)
}
# 先頭イベントの ts。行内に metrics キー（defects / commits / tests …）があっても最初の ts: を拾うよう、
# イベント行の形 `- { ts: … }` の `{` の直後にアンカーする（sh の sed と揃える）。
function CvFirstTs($lines) {
  foreach ($l in $lines) {
    if ($l -match '^[^{]*\{\s*ts:\s*([0-9][0-9:TZ.-]*)') { return $Matches[1] }
  }
  return ''
}
# 母集団の材料（deliver 済み top-level work の着手時刻）を 1 回だけ走査して積む（sh の cv_pop_prime と同じ）。
# 条項ごとに全 works を舐め直すと O(条項×works) になる
function CvPopPrime() {
  if ($script:CvTsReady) { return }
  $script:CvTsReady = $true; $script:CvTs = @()
  $worksRoot = Join-Path $script:AIDEV 'works'
  if (-not (IsDir $worksRoot)) { return }
  foreach ($d in (Get-ChildItem -LiteralPath $worksRoot -Directory | Sort-Object Name)) {
    $f = Join-Path $d.FullName 'metrics.yml'
    if (-not (IsFile $f)) { continue }
    if (@(YList (Join-Path $d.FullName 'state.yml') 'approved') -cnotcontains 'deliver') { continue }
    $ts = CvFirstTs ([System.IO.File]::ReadAllLines($f))
    if (-not $ts) { continue }
    $a = CvTsKey $ts
    if (-not $a) { continue }
    $script:CvTs += $a
  }
}
function CvPop($introduced) {
  $b = CvTsKey $introduced
  if (-not $b) { return 0 }
  CvPopPrime
  $n = 0
  foreach ($a in @($script:CvTs)) { if ([int64]$a -ge [int64]$b) { $n++ } }
  return $n
}

# 判定可能になった条項の通知。works が母集団に加わる唯一の瞬間＝`approve deliver` に鳴らす。
# doctor にも同じ検査があるが、doctor の WARN は retro/insights を叩いた人にしか見えない。
function CvReadyNotice() {
  $d = CvDir
  if (-not (IsDir $d)) { return }
  foreach ($fi in (Get-ChildItem -LiteralPath $d -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)) {
    if ((CvGet $fi.FullName 'status') -cne 'pending') { continue }
    $intro = CvGet $fi.FullName 'introduced'
    if (-not $intro) { continue }
    $va = CvGet $fi.FullName 'verify_after'
    if ($va -notmatch '^\d+$') { continue }
    if ([int]$va -le 0) { continue }
    $pop = CvPop $intro
    # 跨いだ瞬間だけ鳴らす（-ge だと以後の全 deliver で全条項ぶん鳴り続ける。sh 版と同じ）
    if ([int]$pop -eq [int]$va) {
      $id = [System.IO.Path]::GetFileNameWithoutExtension($fi.Name)
      Write-Output "note: 条項 $id の母集団が揃いました($pop/$va)。insights で効果を判定してください"
    }
  }
}

# --- 索引（AGENTS.md の aidev:conventions ブロック）------------------------------
# AGENTS.md / CLAUDE.md は自動読込されるが docs/aidev/ はされない。索引に載っていない条項は
# 読まれないまま works が流れ、効果検証で「効かなかった」と誤判定される（条項の内容の問題ではなく
# 単に届いていないだけなのに）。doctor が索引を突き合わせる。
$script:CV_IDX_OPEN = '<!-- aidev:conventions -->'
$script:CV_IDX_CLOSE = '<!-- /aidev:conventions -->'

# PJ 固有ファイル名を CLI に埋めないため config を優先し、未設定時のみ慣行にフォールバック。
function CvIndexFile() {
  $f = YGet (Join-Path $script:AIDEV 'config.yml') 'conventionsIndex'
  if ($f) {
    if ([System.IO.Path]::IsPathRooted($f)) { return $f }
    return (Join-Path $script:ROOT $f)
  }
  foreach ($c in @('AGENTS.md','CLAUDE.md')) {
    $p = Join-Path $script:ROOT $c
    if (IsFile $p) { return $p }
  }
  return ''
}

# 索引ファイルの表示名。config も慣行も外れている PJ に「AGENTS.md に足せ」と言うと、
# 存在しないファイルを名指しすることになる。決まっていないなら決まっていないと言い、
# どこで決めるか（conventionsIndex）を示す。
function CvIndexLabel() {
  $f = CvIndexFile
  if ($f) { return (Split-Path -Leaf $f) }
  return '索引ファイル（.aidev/config.yml の conventionsIndex。未設定なら AGENTS.md → CLAUDE.md を探す）'
}

# 索引ブロックの中身だけを取り出す（マーカー外は PJ のもので harness は見ない）。
function CvIndexBlock($path) {
  if (-not $path -or -not (IsFile $path)) { return '' }
  $out = @(); $inb = $false
  foreach ($l in [System.IO.File]::ReadAllLines($path)) {
    if ($l.Contains($script:CV_IDX_OPEN))  { $inb = $true;  continue }
    if ($l.Contains($script:CV_IDX_CLOSE)) { $inb = $false; continue }
    if ($inb) { $out += $l }
  }
  return ($out -join "`n")
}

# 条項ディレクトリの ROOT 相対表記（索引に書かれるリンクの形）。
function CvDirRel() {
  $d = CvDir
  $r = $script:ROOT
  if ($d.StartsWith($r)) {
    return ($d.Substring($r.Length).TrimStart('\','/') -replace '\\','/')
  }
  return $d
}

function Cmd-New($rest) {
  $slug=''; $mode=''; $profile=''; $ticket=''; $depends=''; $parent=''; $backlog=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--mode'    { $i++; $mode=(ArgAt $rest $i '--mode') }
      '--profile' { $i++; $profile=(ArgAt $rest $i '--profile') }
      '--light'   { $profile='light' }
      '--ticket'  { $i++; $ticket=(ArgAt $rest $i '--ticket') }
      '--depends' { $i++; $depends=(ArgAt $rest $i '--depends') }
      '--parent'  { $i++; $parent=(ArgAt $rest $i '--parent') }
      # 空文字は sh 側（basename "" が空を返し、未指定として扱われる）に合わせる。
      # 素で Split-Path に渡すと 'Cannot bind argument...' の生の .NET 例外が出て、
      # 同じ入力で片方は work を作り片方は落ちる
      '--backlog' { $i++; $_bv=(ArgAt $rest $i '--backlog'); if ($_bv) { $backlog=Split-Path -Leaf $_bv } }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($slug) { Die "slug は1つだけ" } else { $slug=$rest[$i] }
      }
    }
  }
  if (-not $slug) { Die "使用法: aidev new <slug> [--mode ..] [--profile ..|--light] [--ticket ..] [--depends ..] [--parent <親work>] [--backlog <file>]" }
  # backlog 出自は「消し込み忘れ」を verify で捕まえるための刻印。存在しないファイルを
  # 指したまま進むと deliver 直前まで気づけないので、この場で弾く（sh 版と同一）
  if ($backlog -and -not (IsFile (Join-Path (Join-Path $script:AIDEV 'backlog') $backlog))) {
    Die "backlog ファイルが無い: .aidev/backlog/$backlog"
  }
  # 消化済み（todo=0）の backlog から着手できると status が todo=0 / inflight=1 という自己矛盾を出す（sh 版と同一）
  if ($backlog -and -not $parent) {
    $bt = 0
    foreach ($l in [System.IO.File]::ReadAllLines((Join-Path (Join-Path $script:AIDEV 'backlog') $backlog))) { if ($l -match '^\s*- \[ \]') { $bt++ } }
    if ($bt -le 0) { Die "backlog に未着手項目がありません（todo=0）: .aidev/backlog/$backlog。項目を足してから着手する" }
  }

  $depsYaml='[]'
  if ($depends) {
    $parts = @($depends -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -cne '' })
    $depsYaml = '[' + ([string]::Join(', ',$parts)) + ']'
  }
  $worksRoot = Join-Path $script:AIDEV 'works'

  # 子は backlog 出自を持たない設計（出自は親が持つ）。受理して黙って捨てない
  if ($parent -and $backlog) { Die "--parent と --backlog は併用できません（backlog 出自は親 work に刻む）" }
  if ($parent) {
    # --- subtask 生成: 親 work 配下に <slug>(=NN-subslug) で作る（date prefix なし）。current は plan 開始 ---
    $pdir = Join-Path $worksRoot $parent
    if (-not (IsDir $pdir)) { Die "親 work が存在しません: $parent" }
    $pst = Join-Path $pdir 'state.yml'
    if (-not (IsFile $pst)) { Die "親 state.yml がありません: $parent" }
    # C: 多段ネスト禁止（単層のみ）。親が既に subtask なら拒否（doctor 横断・依存解決・activeSubtask は1段前提）
    if (YGet $pst 'parent') { Die "親が既に subtask です。多段ネストは不可（subtask は単層のみ）: $parent" }
    if ($slug -match '/') { Die "subtask slug にスラッシュは使えません: $slug" }
    $name = "$parent/$slug"
    $work = Join-Path $pdir $slug
    if (IsDir $work) { Die "subtask が既に存在します: $name" }
    if (-not $mode) { $mode = YGet $pst 'mode' }
    if (-not $mode) { $mode = 'interactive' }
    if ($mode -cne 'interactive' -and $mode -cne 'autonomous') { Die "mode は interactive|autonomous" }
    # profile も mode と同様に親から継承（省略時）。sh 版と同一
    if (-not $profile) { $profile = YGet $pst 'profile' }
    if (-not $profile) { $profile = 'full' }
    if ($profile -cne 'full' -and $profile -cne 'light') { Die "profile は full|light" }
    New-Item -ItemType Directory -Path $work -Force | Out-Null

    $sb = "schema: $($script:CURRENT_SCHEMA)`nslug: $slug`nparent: $parent`n"
    if ($ticket) { $sb += "ticket: $ticket`n" }
    $sb += "current: plan`napproved: []`nmode: $mode`nprofile: $profile`nhumanGates: []`nmaxSendBacks: 3`ndependsOn: $depsYaml`n"
    $sb += "harnessRev: $(HarnessRev)`n"
    WriteText (Join-Path $work 'state.yml') $sb
    WriteText (Join-Path $work 'metrics.yml') "events:`n"

    # 親 subtasks に追記（重複排除）し、activeSubtask 未設定なら本 subtask を活性に
    $cur = @(YList $pst 'subtasks')
    if ($cur -cnotcontains $slug) { $cur = @($cur + $slug) }
    SetOrAppend $pst 'subtasks' ("subtasks: [" + ([string]::Join(', ', $cur)) + "]")
    $act = YGet $pst 'activeSubtask'
    if (-not $act -or $act -ceq 'done') {
      SetOrAppend $pst 'activeSubtask' "activeSubtask: $slug"
      $act = $slug
    }

    # カーソルは活性の子に合わせる（無条件に「今作った子」へ動かすと冗長コピーの定義が破れる）
    WriteText (Join-Path $script:AIDEV 'current') "$parent/$act`n"
    Write-Output "created subtask: $work (parent $parent, schema $($script:CURRENT_SCHEMA), mode $mode, profile $profile)"
    return
  }

  # --- 通常(top-level) work ---
  if (-not $mode) { $mode = 'interactive' }
  if ($mode -cne 'interactive' -and $mode -cne 'autonomous') { Die "mode は interactive|autonomous" }
  if (-not $profile) { $profile = 'full' }
  if ($profile -cne 'full' -and $profile -cne 'light') { Die "profile は full|light" }

  $dateP = [DateTime]::UtcNow.ToString('yyyyMMdd')
  $base = "$dateP-$slug"; $name=$base; $n=2
  while (IsDir (Join-Path $worksRoot $name)) { $name="$base-$n"; $n++ }
  $work = Join-Path $worksRoot $name
  New-Item -ItemType Directory -Path $work -Force | Out-Null

  $sb = "schema: $($script:CURRENT_SCHEMA)`nslug: $slug`n"
  if ($ticket) { $sb += "ticket: $ticket`n" }
  $sb += "current: requirement`napproved: []`nmode: $mode`nprofile: $profile`nhumanGates: []`nmaxSendBacks: 3`ndependsOn: $depsYaml`n"
  $sb += "harnessRev: $(HarnessRev)`n"
  if ($backlog) { $sb += "backlog: $backlog`n" }
  WriteText (Join-Path $work 'state.yml') $sb
  WriteText (Join-Path $work 'metrics.yml') "events:`n"
  WriteText (Join-Path $script:AIDEV 'current') "$name`n"
  Write-Output "created: $work (schema $($script:CURRENT_SCHEMA), mode $mode, profile $profile)"
  if ($profile -ceq 'light') { Write-Output "note: profile=light。上流3工程は requirement 1ゲートに畳む（protocol.md「11.」）" }
  if ($backlog) { Write-Output "backlog: $backlog（deliver で該当行を [x] にすること。verify が検査する）" }
}

# --- event -------------------------------------------------------------------
function Cmd-Event($rest) {
  if ($rest.Count -lt 2) { Die "使用法: aidev event <phase> <start|sent_back> [k=v ...]" }
  $ph=$rest[0]; $ev=$rest[1]; $kvs=@(); if ($rest.Count -gt 2) { $kvs=$rest[2..($rest.Count-1)] }
  if (-not (IsPhase $ph)) { Die "未知の phase: $ph" }
  # approved は approve の役割。event で書くと state.yml が更新されず metrics と乖離する
  if ($ev -ceq 'approved') { Die "approved は aidev approve <phase> で記録すること（event では state.yml が更新されず、metrics と乖離する）" }
  if ('start','sent_back' -cnotcontains $ev) { Die "event は start|sent_back（approved は approve コマンド）" }
  ResolveWork ''
  AppendEvent $script:WORK $ph $ev $kvs
  Write-Output "recorded: $($script:SLUG)/$ph/$ev"
}

# --- approve -----------------------------------------------------------------
function Cmd-Approve($rest) {
  if ($rest.Count -lt 1) { Die "使用法: aidev approve <phase> [k=v ...]" }
  $ph=$rest[0]; $kvs=@(); if ($rest.Count -gt 1) { $kvs=$rest[1..($rest.Count-1)] }
  if (-not (IsPhase $ph)) { Die "未知の phase: $ph" }
  ResolveWork ''
  $st = Join-Path $script:WORK 'state.yml'
  if (-not (IsFile $st)) { Die "state.yml がありません: $($script:SLUG)" }

  if (-not (ApprovedHas $script:WORK $ph)) {
    # @() は必須。PowerShell は単一要素配列をスカラーに巻き戻すので、これが無いと
    # 2回目の approve で `$cur + $ph` が**文字列連結**になり approved が壊れる
    $cur = @(YList $st 'approved')
    if ($cur.Count -eq 0) { $newl = "[$ph]" }
    else { $newl = '[' + ([string]::Join(', ', ($cur + $ph))) + ']' }
    ReplaceLine $st 'approved' "approved: $newl"
  }
  ReplaceLine $st 'current' "current: $ph"
  AppendEvent $script:WORK $ph 'approved' $kvs
  Write-Output "approved: $ph @ $($script:SLUG)"

  # deliver 時のハーネス版も刻む。new 時と食い違う work は改修をまたいで走った＝前半を旧版・
  # 後半を新版で回している。どちらかに帰属させると効果が薄まるので母集団から除外する。
  if ($ph -ceq 'deliver') {
    $hr = HarnessRev
    SetOrAppend $st 'harnessRevDelivered' "harnessRevDelivered: $hr"
    $hr0 = YGet $st 'harnessRev'
    if ($hr0 -and $hr0 -cne $hr -and $hr0 -cne 'unknown' -and $hr -cne 'unknown') {
      Write-Output "note: ハーネス版が着手時($hr0)と着地時($hr)で異なる＝またがり work。効果検証の母集団からは除外される"
    }
    # この deliver で母集団が揃った条項があれば、その場で知らせる
    CvReadyNotice
    HvReadyNotice
  }


  # D: subtask の review 承認でカーソルを前進させる（散文の手動カーソル操作を排除）。
  # 親 subtasks を順に見て review 未承認の最初の子を次の active にする。無ければ done（→親の統合 test へ）。
  if ($ph -ceq 'review') {
    $par = YGet $st 'parent'
    $worksRoot = Join-Path $script:AIDEV 'works'
    if ($par -and (IsDir (Join-Path $worksRoot $par))) {
      $pst2 = Join-Path (Join-Path $worksRoot $par) 'state.yml'
      $nextsub = ''
      foreach ($s in @(YList $pst2 'subtasks')) {
        $subSt = Join-Path (Join-Path (Join-Path $worksRoot $par) $s) 'state.yml'
        if ((YList $subSt 'approved') -cnotcontains 'review') { $nextsub = $s; break }
      }
      if ($nextsub) {
        SetOrAppend $pst2 'activeSubtask' "activeSubtask: $nextsub"
        WriteText (Join-Path $script:AIDEV 'current') "$par/$nextsub`n"
        Write-Output "cursor: activeSubtask=$nextsub（次の subtask へ自動前進）"
      } else {
        SetOrAppend $pst2 'activeSubtask' "activeSubtask: done"
        WriteText (Join-Path $script:AIDEV 'current') "$par`n"
        Write-Output "cursor: 全 subtask 完了 → activeSubtask=done。親 $par の統合 test へ"
      }
    }
  }
}

# 依存(dependsOn)の充足を読み取り専用で評価（state は変更しない）。
# 結果を $script:EvalUnmet（works 由来の未充足・exit に影響）/ $script:EvalAdvisory（外部チケット #N）に格納。
function Eval-Depends($workDir) {
  $script:EvalUnmet = @(); $script:EvalAdvisory = @()
  $worksRoot = Join-Path $script:AIDEV 'works'
  # subtask は同一親配下の兄弟 subtask を bare 名（NN-subslug）で依存指定できる。
  $par = YGet (Join-Path $workDir 'state.yml') 'parent'
  foreach ($d in @(YList (Join-Path $workDir 'state.yml') 'dependsOn')) {
    if (-not $d) { continue }
    if ($d.StartsWith('#')) { $script:EvalAdvisory += $d; continue }
    # works slug は日付/連番で始まる。英字始まり+数字終わり（PROJ-123 型）は外部チケット＝advisory
    if ($d -cmatch '^[A-Za-z][A-Za-z0-9_]*-[0-9]+$') { $script:EvalAdvisory += $d; continue }
    $depWork = Join-Path $worksRoot $d
    if (-not (IsDir $depWork) -and $par -and (IsDir (Join-Path (Join-Path $worksRoot $par) $d))) {
      $depWork = Join-Path (Join-Path $worksRoot $par) $d
    }
    if (IsDir $depWork) {
      $da = @(YList (Join-Path $depWork 'state.yml') 'approved')
      # 完了判定: subtask(=parent あり)は review 承認、top-level work は deliver 承認
      if (YGet (Join-Path $depWork 'state.yml') 'parent') {
        if ($da -cnotcontains 'review') { $script:EvalUnmet += "$d(未review)" }
      } else {
        if ($da -cnotcontains 'deliver') { $script:EvalUnmet += "$d(未deliver)" }
      }
    } else { $script:EvalUnmet += "$d(work不明)" }
  }
}

# --- guard -------------------------------------------------------------------
function Cmd-Guard($rest) {
  if ($rest.Count -lt 1) { Die "使用法: aidev guard <phase>" }
  $ph=$rest[0]
  if (-not (IsPhase $ph)) { Die "未知の phase: $ph" }
  ResolveWork ''
  $miss=@(); $unapp=@()
  # subtask なら上流成果物(requirement/spec/design)の継承元として親 work dir を立てる
  $script:PARENT_DIR=''
  $par = YGet (Join-Path $script:WORK 'state.yml') 'parent'
  if ($par) { $pd = Join-Path (Join-Path $script:AIDEV 'works') $par; if (IsDir $pd) { $script:PARENT_DIR=$pd } }
  # B: 親専用工程は subtask で実行不可（subtask の工程は plan/coding/test/review のみ）
  if ($par -and ('requirement','research','spec','design','walkthrough','deliver','retro' -ccontains $ph)) {
    [Console]::Error.WriteLine("NG $ph は親 work 専用です（subtask では実行不可。subtask の工程は plan/coding/test/review）: $($script:SLUG)")
    exit 2
  }
  function needFile($f) {
    if (IsFile (Join-Path $script:WORK $f)) { return }
    # 上流成果物(requirement/spec/design)のみ親から継承。plan.md/tasks.md は subtask 固有なので継承しない。
    if ($script:PARENT_DIR -and ('requirement.md','spec.md','design.md' -ccontains $f) -and (IsFile (Join-Path $script:PARENT_DIR $f))) { return }
    $script:miss += $f
  }
  function needApproved($p) { if (-not (ApprovedHas $script:WORK $p)) { $script:unapp += $p } }
  $script:miss=@(); $script:unapp=@()
  switch -CaseSensitive ($ph) {
    'requirement' { }
    'research'    { needFile 'requirement.md' }
    'spec'        { needFile 'requirement.md' }
    'design'      { needFile 'spec.md' }
    'plan'        { needFile 'spec.md' }
    'coding'      { needFile 'plan.md'; needFile 'tasks.md' }
    'test'        {
      # 分割 work の親は tasks.md を持たない（各 subtask の plan が作る）。一律に要求すると
      # 書いてあるとおりに plan を書いた親の統合 test が必ず塞がる
      $subs = @(YList (Join-Path $script:WORK 'state.yml') 'subtasks')
      if ($subs.Count -gt 0) {
        needFile 'plan.md'
        foreach ($sub in $subs) {
          $subAp = @(YList (Join-Path (Join-Path $script:WORK $sub) 'state.yml') 'approved')
          if ($subAp -cnotcontains 'review') { $script:miss += "$sub(未review)" }
        }
      } else {
        needFile 'tasks.md'
      }
    }
    'review'      { needFile 'spec.md'; needApproved 'test' }
    'walkthrough' { needApproved 'review' }
    'deliver'     { needApproved 'review' }
    'retro'       { needApproved 'deliver' }
  }
  # dependsOn（共有 Eval-Depends を使用。挙動は従来と一致）
  Eval-Depends $script:WORK
  $dep = $script:EvalUnmet
  foreach ($a in $script:EvalAdvisory) { Warn "依存(外部チケット $a): 自動判定不可＝advisory（手動確認）" }

  $rc=0
  if ($script:miss.Count -gt 0)  { [Console]::Error.WriteLine("NG 前提成果物が不足: " + ($script:miss -join ' ')); $rc=2 }
  if ($script:unapp.Count -gt 0) { [Console]::Error.WriteLine("NG 前提工程が未承認: " + ($script:unapp -join ' ')); $rc=2 }
  if ($dep.Count -gt 0)          { [Console]::Error.WriteLine("NG 依存(dependsOn)が未充足: " + ($dep -join ' ')); if ($rc -eq 0) { $rc=3 } }
  if ($rc -eq 0) {
    Write-Output "OK guard $ph @ $($script:SLUG)"
    # guard は「入ってよいか」の判定で、start の記録は別コマンド。
    # 分かれているため記録を忘れる事故が実際に起きた（review の start が両ラウンドとも欠落）。
    # start を自動記録はしない（skill 側の event start と二重になり、手戻り回数を
    # 誤って数えるため）。代わりに、まだ必要な場合だけ促す。
    if (NeedsStart $script:WORK $ph) { Write-Output "   → 忘れずに: aidev event $ph start" }
  }
  exit $rc
}

# その工程に新しい start の記録が要るか（start 回数 <= approved 回数なら要る）。
function NeedsStart($work, $phase) {
  $mf = Join-Path $work 'metrics.yml'
  if (-not (IsFile $mf)) { return $true }
  $s = 0; $a = 0
  foreach ($l in [System.IO.File]::ReadAllLines($mf)) {
    $m = [regex]::Match($l, 'phase:\s*([a-z]+)')
    if (-not $m.Success -or $m.Groups[1].Value -cne $phase) { continue }
    if ($l -match 'event:\s*start')    { $s++ }
    if ($l -match 'event:\s*approved') { $a++ }
  }
  return ($s -le $a)
}

# --- verify ------------------------------------------------------------------
# verify の状態行の出口。通常は [Console]::Out へ直接（戻り値=int だけにし、$rc=VerifyWork が出力を
# 取り込む PS の罠を回避）。doctor --quiet のときだけ $script:VBuf に溜めて呼び出し側が出す
$script:VCapture = $false; $script:VBuf = @()
function VLine($s) { if ($script:VCapture) { $script:VBuf += $s } else { [Console]::Out.WriteLine($s) } }

# [x] 行とその継続行（次の項目・見出し・空行まで）に slug があるか（sh の bl_done_has と同一）
function BlDoneHas($path, $slug) {
  $inx = $false
  foreach ($l in [System.IO.File]::ReadAllLines($path)) {
    if ($l -match '^\s*- \[[xX]\]') { $inx = $true }
    elseif ($l -match '^\s*- \[[^xX]\]' -or $l -match '^#' -or $l -match '^\s*$') { $inx = $false }
    if ($inx -and $l.Contains($slug)) { return $true }
  }
  return $false
}

function VerifyWork($work) {
  # 注意: 状態行は VLine 経由（通常は [Console]::Out へ直接。Write-Output は戻り値を汚すので使わない）
  $st = Join-Path $work 'state.yml'
  if (-not (IsFile $st)) { VLine("  FAIL state.yml なし"); return 4 }
  $vf=@()
  foreach ($k in 'slug','current','approved') {
    $found=$false
    foreach ($l in [System.IO.File]::ReadAllLines($st)) { if ($l -match ("^"+$k+":")) { $found=$true; break } }
    if (-not $found) { $vf += "state.yml:${k}欠落" }
  }
  $schema = YGet $st 'schema'
  if ([string]::IsNullOrEmpty($schema)) {
    VLine("  SKIP legacy (schema 未記載・metrics導入前の作業として免除)")
  } else {
    $sn = 0; [void][int]::TryParse($schema, [ref]$sn)
    if ($sn -ge 2) {
      if (-not (IsFile (Join-Path $work 'metrics.yml'))) { $vf += "metrics.yml欠落" }
      if (ApprovedHas $work 'review') { if (-not (IsFile (Join-Path $work 'review.md'))) { $vf += "review.md欠落(review承認済)" } }
      # 承認済み工程の成果物が実在するか（protocol.md「7.」）。これが無いと、成果物を1つも
      # 作らずに全工程 approve した work が「deliver 済み・verify OK」になる。
      # schema 5 以降だけ（version-aware。導入前の work を遡って違反扱いしない）
      if ($sn -ge 5) {
        $issub = YGet $st 'parent'
        $hassub = @(YList $st 'subtasks')
        foreach ($pf in @(@('requirement','requirement.md'), @('spec','spec.md'), @('plan','plan.md'))) {
          if (-not (ApprovedHas $work $pf[0])) { continue }
          if (IsFile (Join-Path $work $pf[1])) { continue }
          # subtask は親の requirement/spec/design を継承する
          if ($issub -and (IsFile (Join-Path (Join-Path (Join-Path $script:AIDEV 'works') $issub) $pf[1]))) { continue }
          $vf += "$($pf[1])欠落($($pf[0])承認済)"
        }
        # 親（subtasks を持つ）は tasks.md を持たない（各 subtask の plan が作る）
        if ((ApprovedHas $work 'plan') -and $hassub.Count -eq 0 -and -not (IsFile (Join-Path $work 'tasks.md'))) {
          $vf += "tasks.md欠落(plan承認済)"
        }
      }
      if (ApprovedHas $work 'deliver') {
        $mf = Join-Path $work 'metrics.yml'; $ok=$false
        if (IsFile $mf) { foreach ($l in [System.IO.File]::ReadAllLines($mf)) { if ($l -match 'phase:\s*deliver' -and $l -match 'event:\s*approved') { $ok=$true; break } } }
        if (-not $ok) { $vf += "deliver承認イベントがmetricsに無い" }
        # backlog 出自の消し込み（DESIGN「2.5」: backlog 行は deliver で [x]）。sh 版と同一。
        # 見るのは [x] 行とその継続行に自分の slug が現れるか（どこかにあるだけだと (needs: <slug>) の
        # 未着手行で通ってしまう）。backlog compact が退避した archive/<name>-done.md も見る
        $bl = YGet $st 'backlog'
        if (-not [string]::IsNullOrEmpty($bl)) {
          $blRoot = Join-Path $script:AIDEV 'backlog'
          $blf = Join-Path $blRoot $bl
          if (-not (IsFile $blf)) { $blf = Join-Path (Join-Path $blRoot 'archive') $bl }
          $bld = Join-Path (Join-Path $blRoot 'archive') (($bl -replace '\.md$','') + '-done.md')
          $wslug = Split-Path -Leaf $work
          if (-not (IsFile $blf) -and -not (IsFile $bld)) {
            $vf += "backlog:${bl}が見つからない"
          } else {
            $blok = $false
            if ((IsFile $blf) -and (BlDoneHas $blf $wslug)) { $blok = $true }
            if ((-not $blok) -and (IsFile $bld) -and (BlDoneHas $bld $wslug)) { $blok = $true }
            if (-not $blok) { $vf += "backlog:${bl}に${wslug}の消し込みが無い（[x] 行かその継続行に slug が要る）" }
          }
        }
      }
    }
  }
  # イベント対の検査（WARN。既存 work を壊さないよう終了コードは変えない）
  #
  # guard と event start が別コマンドなので、guard だけ実行して工程に入り
  # start を記録し忘れる事故が起きる（実際に review の start が両ラウンドとも
  # 欠落し、所要時間が導出できなくなった）。記録漏れは後から気付けないので、
  # deliver 前に verify が知らせる。
  $mf2 = Join-Path $work 'metrics.yml'
  $epw = @()
  if (IsFile $mf2) { $epw = @(EventPairWarnings $mf2) }
  foreach ($l in $epw) { VLine($l) }

  # profile: light の逸脱検査（WARN）
  LightWarnings $work

  # またがり work の検知（WARN）。schema 4 以降のみ＝旧 work を遡って違反扱いしない。
  $vsc = YGet (Join-Path $work 'state.yml') 'schema'
  if ($vsc -notmatch '^\d+$') { $vsc = '0' }
  if ([int]$vsc -ge 4) {
    $hr0 = YGet (Join-Path $work 'state.yml') 'harnessRev'
    $hr1 = YGet (Join-Path $work 'state.yml') 'harnessRevDelivered'
    # harnessRevDelivered を書くのは approve deliver、verify が走るのはその前。着地時の刻印を
    # 待つ書き方だと、この検査は通常の順序では一度も発火しない。まだ無いときは今の版と比べる。
    $hrw = '着地時'
    if (-not $hr1) { $hr1 = HarnessRev; $hrw = '現在' }
    # ここで Write-Output を使うと、この関数の戻り値が Object[] になり `$rc = VerifyWork` が
    # 壊れる（FAIL を出しながら rc=0、--strict の 5 も 0 になり、Windows で機械ゲートが素通りする）。
    # 状態行は必ず [Console]::Out へ直接出すこと（この関数の先頭コメントの通り）
    if (-not $hr0) {
      VLine("  WARN harnessRev が無い: 効果検証の母集団から漏れる（aidev new で刻まれる）")
    } elseif ($hrw -ceq '現在' -and $hr0 -cne $hr1 -and $hr0 -cne 'unknown' -and $hr1 -cne 'unknown') {
      # deliver 前だけ鳴らす。deliver 済みのまたがりは metrics --all の straddle 列で見る（sh 版と同一）
      VLine("  note: またがり work: ハーネス版が着手時($hr0)と$hrw($hr1)で異なる。効果検証の母集団からは除外される")
    }
  }


  if ($vf.Count -gt 0) { VLine("  FAIL " + ($vf -join ' ')); return 4 }
  # --strict: 記録漏れだけを致命扱い（sh 版と同一。理由は sh 側のコメント参照）
  if ($script:STRICT -and $epw.Count -gt 0) {
    VLine("  FAIL(strict) 記録漏れ: 上記 WARN を解消してから終えること（timestamp は後から復元できません）")
    return 5
  }
  VLine("  OK"); return 0
}

# profile=light の条件逸脱を WARN で知らせる（終了コードには影響しない）。sh 版 light_warnings と同一。
#
# light は「振る舞い不変・小規模」を前提にした軽量プロファイル（protocol.md「11.」）。
# 条件を外れたら full へ昇格するのが正だが、昇格漏れは後から気付けない
# （light のまま着地すると insights の「light の手戻り率」が実態より良く見える）。
function LightWarnings($work) {
  $st = Join-Path $work 'state.yml'
  if (-not (IsFile $st)) { return }
  if ((YGet $st 'profile') -cne 'light') { return }
  $mf = Join-Path $work 'metrics.yml'
  if (-not (IsFile $mf)) { return }
  $lines = [System.IO.File]::ReadAllLines($mf)

  # 任意工程を使った＝「小規模」の前提を外れている（出力順は sh 版のループと同一）
  foreach ($p in @('research','design','walkthrough')) {
    foreach ($l in $lines) {
      if ($l -match ("phase:\s*" + $p + ",")) {
        VLine("  WARN profile=light だが任意工程 $p を実施（aidev escalate で full へ）")
        break
      }
    }
  }

  # 変更規模が上限超過（deliver の files_changed。上限は .aidev/config.yml の lightMaxFiles、既定 3）
  $max = 3
  $cfg = Join-Path $script:AIDEV 'config.yml'
  if (IsFile $cfg) {
    $v = YGet $cfg 'lightMaxFiles'
    if ($v -match '^\d+$') { $max = [int]$v }
  }
  $fc = $null
  foreach ($l in $lines) {
    if ($l -match 'phase:\s*deliver,' -and $l -match 'event:\s*approved') {
      $m = [regex]::Match($l, 'files_changed:\s*(\d+)')
      if ($m.Success) { $fc = [int]$m.Groups[1].Value }   # sh 版の tail -n1 と同じく最後の一致を採る
    }
  }
  if ($null -ne $fc -and $fc -gt $max) {
    VLine("  WARN profile=light だが変更 $fc ファイル（上限 $max）。aidev escalate で full へ")
  }
}

# metrics.yml のイベント対を検査し、WARN 行を出す（終了コードには影響しない）。
function EventPairWarnings($metricsFile) {
  $starts = @{}; $approved = @{}; $seen = New-Object System.Collections.Generic.List[string]
  foreach ($l in [System.IO.File]::ReadAllLines($metricsFile)) {
    $m = [regex]::Match($l, 'phase:\s*([a-z]+)')
    if (-not $m.Success) { continue }
    $p = $m.Groups[1].Value
    if (-not $seen.Contains($p)) { [void]$seen.Add($p) }
    if ($l -match 'event:\s*start')    { $starts[$p]    = [int]$starts[$p] + 1 }
    if ($l -match 'event:\s*approved') { $approved[$p]  = [int]$approved[$p] + 1 }
  }
  # 出力順は PHASES 順（未知の phase は初出順で後ろに）。ハッシュの列挙順に任せると
  # awk と PowerShell で並びが変わり「出力を一致させる」契約が破れる。
  $order = @($script:PHASES | Where-Object { $approved.ContainsKey($_) })
  $order += @($seen | Where-Object { $approved.ContainsKey($_) -and ($script:PHASES -cnotcontains $_) })
  # 行は**返す**（呼び出し側が出力する）。--strict で件数を数える必要があるため。sh 版の
  # `EPW=$(event_pair_warnings …)` と同じ形にして、出力内容・順序は従来どおりに保つ。
  foreach ($p in $order) {
    $s = [int]$starts[$p]; $a = [int]$approved[$p]
    if ($s -eq 0) {
      "  WARN ${p}: approved があるのに start が無い（所要時間が導出できません）"
    } elseif ($s -lt $a) {
      "  WARN ${p}: start $s 回に対し approved $a 回（start の記録漏れ、または approve の重複）"
    }
  }
}

function Cmd-Verify($rest) {
  $slug=''; $script:STRICT = $false
  for ($i=0; $i -lt $rest.Count; $i++) {
    if ($rest[$i] -ceq '--strict') { $script:STRICT = $true }
    elseif ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
    elseif ($slug) { Die "slug は1つだけ" }
    else { $slug = $rest[$i] }
  }
  ResolveWork $slug
  $vroot = $script:WORK; $vrslug = $script:SLUG
  Write-Output "verify: $vrslug"
  $rc = VerifyWork $vroot
  # 分割 work の親を verify するときは子も見る（着地するのは親1本の PR）
  foreach ($sd in @(Get-ChildItem -LiteralPath $vroot -Directory -ErrorAction SilentlyContinue | Sort-Object Name)) {
    if (-not (IsFile (Join-Path $sd.FullName 'state.yml'))) { continue }
    Write-Output "verify: $vrslug/$($sd.Name)"
    $src = VerifyWork $sd.FullName
    if ($rc -eq 0) { $rc = $src }
  }
  $script:STRICT = $false
  exit $rc
}

# --- escalate（profile: light -> full。片方向） --------------------------------
# state.yml の更新を CLI に集約するための経路（sh 版 cmd_escalate と同一）。
function Cmd-Escalate($rest) {
  $slug=''; if ($rest.Count -ge 1) { $slug=$rest[0] }
  ResolveWork $slug
  $st = Join-Path $script:WORK 'state.yml'
  $cur = YGet $st 'profile'
  if (-not $cur) { $cur = 'full' }   # 未記載 = full（profile 導入前の work）
  if ($cur -ceq 'full')  { Die "既に profile=full です（昇格は片方向。full -> light は不可）: $($script:SLUG)" }
  if ($cur -cne 'light') { Die "未知の profile: $cur" }
  SetOrAppend $st 'profile' 'profile: full'
  Write-Output "escalated: $($script:SLUG) (light -> full)"
  Write-Output "next: 省略していた節を各文書に足す / decisions.md に経緯を残す /"
  Write-Output "      該当工程の承認に escalated_from_light=1 を付ける（protocol.md「11.」）"
}

# --- doctor ------------------------------------------------------------------
# --- backlog ファイル横断検査（doctor の一部）。sh 版と同一の判定・同一の出力 ------------
# verify の消し込み検査は work にぶら下がるが、退避・frontmatter・書式は
# ファイル自身の一生の話で持ち主の work がいない（sh 版の注記参照）。WARN 止まりで exit code は変えない。
function BlKind($path) {  # 先頭 frontmatter の kind（frontmatter 自体が無ければ空）
  $lines = [System.IO.File]::ReadAllLines($path)
  if ($lines.Count -eq 0 -or $lines[0] -notmatch '^---\s*$') { return '' }
  for ($i=1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^---\s*$') { return '' }
    if ($lines[$i] -match '^kind:\s*(.*?)\s*$') { return $Matches[1] }
  }
  return ''
}

# backlog ファイル1件の数え上げ（sh の bl_stat と同一。status と同じパターンで数える）。
function BlStat($path) {
  $todo=0; $dn=0; $hid=0
  foreach ($l in [System.IO.File]::ReadAllLines($path)) {
    if ($l -match '^\s*- \[ \]') { $todo++ }
    elseif ($l -match '^\s*- \[[xX]\]') { $dn++ }
    if ($l -match '^(#+\s*- |\s*[*+]\s*)\[[ xX]\]') { $hid++ }
  }
  $script:BL_TODO=$todo; $script:BL_DN=$dn; $script:BL_HID=$hid; $script:BL_KIND=(BlKind $path)
}

# 退避してよいか＝消化しきったら終わるキュー（split/topic）で全項目 [x]。doctor と archive が同じ判定を通る。
function BlArchivable($path) {
  BlStat $path
  if ($script:BL_KIND -cne 'split' -and $script:BL_KIND -cne 'topic') { return $false }
  return ($script:BL_TODO -eq 0 -and $script:BL_DN -gt 0)
}

function Doctor-Backlog() {
  $blRoot = Join-Path $script:AIDEV 'backlog'
  if (-not (IsDir $blRoot)) { return }
  $items = @()
  foreach ($f in (Get-ChildItem -LiteralPath $blRoot -File -Filter *.md | Sort-Object Name)) {
    $items += ,@($f.FullName, $f.Name, $false)
  }
  $arcRoot = Join-Path $blRoot 'archive'
  if (IsDir $arcRoot) {
    foreach ($f in (Get-ChildItem -LiteralPath $arcRoot -File -Filter *.md | Sort-Object Name)) {
      $items += ,@($f.FullName, ("archive/" + $f.Name), $true)
    }
  }

  $bfiles=0; $barch=0; $bwarn=0; $bout=''
  foreach ($it in $items) {
    $path=$it[0]; $label=$it[1]; $arch=$it[2]
    if ($arch) { $barch++ } else { $bfiles++ }
    # 集計は status と同じパターンで行う（status に見えている姿そのものを検査対象にする）
    BlStat $path
    $todo=$script:BL_TODO; $dn=$script:BL_DN; $hid=$script:BL_HID; $kind=$script:BL_KIND
    $w=''
    if (-not $arch) {
      # kind はファイルの一生の宣言（sh 版と同一）。standing=退避しない / split・topic=退避する。
      if ([string]::IsNullOrEmpty($kind)) {
        $w += "    WARN frontmatter(kind)が無い: standing/split/topic を判定できず退避の要否が決まらない`n"
      } elseif ($kind -ceq 'split' -or $kind -ceq 'topic') {
        if ($todo -eq 0 -and $dn -gt 0) {
          $w += "    WARN 全消化($kind)だが未退避: .aidev/backlog/archive/ へ移す`n"
        }
      } elseif ($kind -cne 'standing') {
        # 誤記を黙って standing 扱いにしない（退避検査がまるごと効かなくなるため）
        $w += "    WARN 未知の kind: $kind（standing/split/topic のいずれか）`n"
      }
    } elseif ($todo -gt 0) {
      $w += "    WARN archive 済だが未消化が ${todo} 件: status から外れて見えない未着手になっている`n"
    }
    if ($hid -gt 0) {
      $w += "    WARN status が数えない書式の項目が ${hid} 件（見出し '## - [ ]' や '*' 箇条書き）: 未着手が status から漏れる`n"
    }
    if ($w) {
      $bwarn++
      $k = if ([string]::IsNullOrEmpty($kind)) { '-' } else { $kind }
      $bout += "- $label (todo=$todo done=$dn kind=$k)`n" + $w
    }
  }
  Write-Output "backlog: ファイル横断検査"
  if ($bout) { Write-Output ($bout.TrimEnd("`n")) }   # 末尾の改行は Write-Output が足す（sh の printf %s と一致）
  Write-Output "backlog-summary: files=$bfiles archived=$barch warn=$bwarn"
}

# 1 work ぶんの検査と出力。--quiet では「  OK」だけの work を行ごと出さない（sh の doctor_one と同一）
function Doctor-One($label, $path) {
  $script:VCapture = $true; $script:VBuf = @()
  $r = VerifyWork $path
  $script:VCapture = $false
  if ($r -ne 0) { $script:DFail++ }
  if ($script:DQuiet -and $script:VBuf.Count -eq 1 -and $script:VBuf[0] -ceq '  OK') { return }
  Write-Output $label
  foreach ($l in $script:VBuf) { Write-Output $l }
}

function Cmd-Doctor($rest) {
  $script:DQuiet = $false
  foreach ($a in @($rest)) {
    if ($a -ceq '--quiet') { $script:DQuiet = $true }
    elseif ($a.StartsWith('-')) { Die "未知のオプション: $a" }
    else { Die "doctor は位置引数を取りません: $a" }
  }
  $worksDir = Join-Path $script:AIDEV 'works'
  if (-not (IsDir $worksDir)) { Die "works がありません" }
  $total=0; $script:DFail=0; $legacy=0
  $qn = if ($script:DQuiet) { '（--quiet: OK は省略）' } else { '' }
  Write-Output "doctor: 全 work 横断検査$qn"
  foreach ($d in (Get-ChildItem -LiteralPath $worksDir -Directory | Sort-Object Name)) {
    $total++
    $sc = YGet (Join-Path $d.FullName 'state.yml') 'schema'
    if ([string]::IsNullOrEmpty($sc)) { $legacy++ }
    Doctor-One ("- " + $d.Name) $d.FullName
    # subtask（ネスト1段）も横断検査する
    foreach ($sd in (Get-ChildItem -LiteralPath $d.FullName -Directory | Sort-Object Name)) {
      if (-not (IsFile (Join-Path $sd.FullName 'state.yml'))) { continue }
      $total++
      $ssc = YGet (Join-Path $sd.FullName 'state.yml') 'schema'
      if ([string]::IsNullOrEmpty($ssc)) { $legacy++ }
      Doctor-One ("  - " + $d.Name + "/" + $sd.Name) $sd.FullName
    }
  }
  $fail = $script:DFail
  Write-Output "summary: works=$total fail=$fail legacy(免除)=$legacy"
  Doctor-Backlog
  Doctor-Conventions
  Doctor-Harness
  # 4（不変条件違反）に揃える。1 は使用法・環境エラー用（sh 版と同一）
  if ($fail -eq 0) { exit 0 } else { exit 4 }
}

# --- status（読み取り専用・works横断＋backlog未着手） ----------------------------
$script:STD_PIPELINE = @('requirement','spec','plan','coding','test','review','deliver')

# タブ区切り行（先頭にヘッダ含む）を列幅で揃えた行配列に整形（sh の fmt_table と一致）
function Fmt-Table($rows) {
  $w=@{}; $maxnf=0; $cells=@()
  foreach ($r in $rows) {
    $cols = $r -split "`t"
    $cells += ,$cols
    if ($cols.Count -gt $maxnf) { $maxnf = $cols.Count }
    for ($i=0; $i -lt $cols.Count; $i++) {
      if (-not $w.ContainsKey($i) -or $cols[$i].Length -gt $w[$i]) { $w[$i] = $cols[$i].Length }
    }
  }
  $out=@()
  foreach ($cols in $cells) {
    $line=''
    for ($i=0; $i -lt $maxnf; $i++) {
      $c = if ($i -lt $cols.Count) { $cols[$i] } else { '' }
      if ($i -lt $maxnf-1) { $line += $c + (' ' * ($w[$i]-$c.Length)) + '  ' } else { $line += $c }
    }
    $out += $line
  }
  return $out
}

# 親 work dir の subtask 進捗 "N M"（N=review承認済の子数/M=総数）。subtasks 無しは ''。
function SubtaskProgress($workDir) {
  $subs = @(YList (Join-Path $workDir 'state.yml') 'subtasks')
  if ($subs.Count -eq 0) { return '' }
  $m = $subs.Count; $n = 0
  foreach ($s in $subs) {
    if ((YList (Join-Path (Join-Path $workDir $s) 'state.yml') 'approved') -ccontains 'review') { $n++ }
  }
  return "$n $m"
}

function Cmd-Status($rest) {
  $fmt='table'; $subflag=$false; $activef=$false
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--format'   { $i++; $fmt=(ArgAt $rest $i '--format') }
      '--subtasks' { $subflag=$true }
      '--active'   { $activef=$true }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        else { Die "status は位置引数を取りません: $($rest[$i])" }
      }
    }
  }
  if ($fmt -cne 'table' -and $fmt -cne 'tsv') { Die "--format は table|tsv" }

  $worksDir = Join-Path $script:AIDEV 'works'
  $wrows=@(); $wn=0   # 各要素は型タグ付き: "W`t…7列…" / "S`t親`t子`tcurrent`tdone"
  if (IsDir $worksDir) {
    foreach ($d in (Get-ChildItem -LiteralPath $worksDir -Directory | Sort-Object Name)) {
      $st = Join-Path $d.FullName 'state.yml'
      if (-not (IsFile $st)) { continue }
      $ticket = YGet $st 'ticket';  if (-not $ticket)  { $ticket='-' }
      $mode = YGet $st 'mode';      if (-not $mode)    { $mode='-' }
      $current = YGet $st 'current';if (-not $current) { $current='-' }
      $appr = @(YList $st 'approved')
      $wdone = if ($appr -ccontains 'deliver') { 'yes' } else { 'no' }
      # --active: deliver 済みは出さない（sh 版と同一）
      if ($activef -and $wdone -ceq 'yes') { continue }
      $next='-'
      if ($wdone -ceq 'no') {
        # profile: light は spec/plan を畳む（承認されないのが正常）。素通しすると next が
        # 永久に spec を指し、light では起動しない工程を案内し続けることになる
        $pipe = $script:STD_PIPELINE
        if ((YGet $st 'profile') -ceq 'light') { $pipe = @('requirement','coding','test','review','deliver') }
        foreach ($p in $pipe) { if ($appr -cnotcontains $p) { $next=$p; break } }
      }
      # subtask を持つ親は next を subtask 進捗に差し替える（未完=sub N/M、全完了=統合工程の次）
      $sp = SubtaskProgress $d.FullName
      if ($sp -and $wdone -ceq 'no') {
        $spp = $sp -split ' '; $spn=[int]$spp[0]; $spm=[int]$spp[1]
        if ($spn -lt $spm) { $next = "sub $spn/$spm" }
        else { $next='-'; foreach ($p in @('test','review','deliver')) { if ($appr -cnotcontains $p) { $next=$p; break } } }
      }
      Eval-Depends $d.FullName
      $tok=@()
      foreach ($u in $script:EvalUnmet) { $tok += $u }
      foreach ($a in $script:EvalAdvisory) { $tok += "$a(advisory)" }
      $deps = if ($tok.Count -gt 0) { [string]::Join(',', $tok) } else { 'ok' }
      $wn++
      $wrows += ("W`t" + $d.Name + "`t" + $ticket + "`t" + $mode + "`t" + $current + "`t" + $next + "`t" + $wdone + "`t" + $deps)
      # --subtasks: 親直下に子を列挙（S 行）
      if ($subflag -and $sp) {
        foreach ($cs in @(YList $st 'subtasks')) {
          $cst = Join-Path (Join-Path $d.FullName $cs) 'state.yml'
          $ccur = YGet $cst 'current'; if (-not $ccur) { $ccur='-' }
          $cdone = if ((YList $cst 'approved') -ccontains 'review') { 'yes' } else { 'no' }
          $wrows += ("S`t" + $d.Name + "`t" + $cs + "`t" + $ccur + "`t" + $cdone)
        }
      }
    }
  }

  # in-flight 収集（sh 版と同一）: backlog 刻印を持ち、まだ deliver していない work。
  # backlog 行が [x] になるのは deliver なので、その間 backlog 側は掴まれた項目を区別できない。
  $inflight = @{}
  $iworks = Join-Path $script:AIDEV 'works'
  if (IsDir $iworks) {
    foreach ($d in (Get-ChildItem -LiteralPath $iworks -Directory | Sort-Object Name)) {
      $ist = Join-Path $d.FullName 'state.yml'
      if (-not (IsFile $ist)) { continue }
      $ibl = YGet $ist 'backlog'
      if ([string]::IsNullOrEmpty($ibl)) { continue }
      if ((YList $ist 'approved') -ccontains 'deliver') { continue }
      if ($inflight.ContainsKey($ibl)) { $inflight[$ibl]++ } else { $inflight[$ibl] = 1 }
    }
  }

  $backlogDir = Join-Path $script:AIDEV 'backlog'
  $brows=@(); $bf=0; $bn=0
  if (IsDir $backlogDir) {
    foreach ($f in (Get-ChildItem -LiteralPath $backlogDir -File -Filter *.md | Sort-Object Name)) {
      $todo=0; $needs=0
      foreach ($l in [System.IO.File]::ReadAllLines($f.FullName)) {
        if ($l -match '^\s*- \[ \]') { $todo++; if ($l -match '\(needs:') { $needs++ } }
      }
      $inf = 0
      if ($inflight.ContainsKey($f.Name)) { $inf = $inflight[$f.Name] }
      $bf++; $bn += $todo
      $brows += ($f.Name + "`t" + $todo + "`t" + $needs + "`t" + $inf)
    }
  }

  if ($fmt -ceq 'tsv') {
    foreach ($r in $wrows) {
      $c = $r -split "`t"
      if ($c[0] -ceq 'W') { Write-Output ("work`t" + ($c[1..7] -join "`t")) }
      else { Write-Output ("subtask`t" + $c[1] + "/" + $c[2] + "`t" + $c[3] + "`t" + $c[4]) }
    }
    foreach ($r in $brows) { Write-Output ("backlog`t" + $r) }
    return
  }

  Write-Output "WORKS ($wn)"
  if ($wn -gt 0) {
    $disp = @("work`tticket`tmode`tcurrent`tnext`tdone`tdeps")
    foreach ($r in $wrows) {
      $c = $r -split "`t"
      if ($c[0] -ceq 'W') { $disp += ($c[1..7] -join "`t") }
      else { $disp += ("  ↳ " + $c[2] + "`t-`t-`t" + $c[3] + "`t-`t" + $c[4] + "`t-") }
    }
    foreach ($l in (Fmt-Table $disp)) { Write-Output $l }
  }
  Write-Output ""
  Write-Output "BACKLOG (未着手 $bn 件)"
  if ($bf -gt 0) { foreach ($l in (Fmt-Table (@("file`ttodo`tneeds`tinflight") + $brows))) { Write-Output $l } }
}

# --- metrics（読み取り専用・metrics.yml から派生指標を集計） ----------------------
function Mt-Epoch($ts) {
  $t = ($ts -replace 'Z$','') -replace 'UTC$',''
  if ($t.Length -lt 19 -or $t.Substring(10,1) -cne 'T') { return -1 }
  try {
    $dt = [DateTime]::ParseExact($t.Substring(0,19), 'yyyy-MM-ddTHH:mm:ss', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None)
    return [int64]([DateTimeOffset]::new($dt, [TimeSpan]::Zero).ToUnixTimeSeconds())
  } catch { return -1 }
}

function Cmd-Metrics($rest) {
  $fmt='table'; $allf=$false; $phasesf=$false; $mslug=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--all'     { $allf=$true }
      '--phases'  { $phasesf=$true }
      '--format'  { $i++; $fmt=(ArgAt $rest $i '--format') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        elseif ($mslug) { Die "slug は1つだけ" } else { $mslug=$rest[$i] }
      }
    }
  }
  if ($fmt -cne 'table' -and $fmt -cne 'tsv') { Die "--format は table|tsv" }

  $worksDir = Join-Path $script:AIDEV 'works'
  $dirs=@()
  if ($allf) {
    # ネスト1段（subtask）まで拾う。top-level だけだと子の手戻り・差し戻しが集計から消える
    if (IsDir $worksDir) {
      foreach ($d in @(Get-ChildItem -LiteralPath $worksDir -Directory | Sort-Object Name)) {
        $dirs += $d.FullName
        foreach ($sd in @(Get-ChildItem -LiteralPath $d.FullName -Directory -ErrorAction SilentlyContinue | Sort-Object Name)) {
          if (IsFile (Join-Path $sd.FullName 'state.yml')) { $dirs += $sd.FullName }
        }
      }
    }
  } elseif ($mslug) {
    $p = Join-Path $worksDir $mslug
    if (-not (IsDir $p)) { Die "work が存在しません: $mslug" }
    $dirs=@($p)
  } else {
    $cur = Join-Path $script:AIDEV 'current'
    if (-not (IsFile $cur)) { Die "対象作業が不明です（.aidev/current 無し）。slug 指定か --all を。" }
    $c = ([System.IO.File]::ReadAllLines($cur))[0].Trim()
    $p = Join-Path $worksDir $c
    if (-not (IsDir $p)) { Die "work が存在しません: $c" }
    $dirs=@($p)
  }

  $rows=@()
  foreach ($wd in $dirs) {
    # subtask は <親>/<子>（basename だけだと親の違う同名 subtask が同一に見える）
    $name = Split-Path $wd -Leaf
    $wdParent = Split-Path $wd -Parent
    if ((Split-Path $wdParent -Leaf) -cne 'works') { $name = "$(Split-Path $wdParent -Leaf)/$name" }
    $mf = Join-Path $wd 'metrics.yml'
    $first=-1; $firstts='-'; $deliveredFlag=$false; $deliveredE=-1; $sback=0
    $scount=@{}; $laststart=@{}; $laststartTs=@{}; $appat=@{}; $appatTs=@{}
    if (IsFile $mf) {
      foreach ($line in [System.IO.File]::ReadAllLines($mf)) {
        if ($line -notmatch 'event:') { continue }
        $ts=''; $ph=''; $ev=''
        if ($line -match 'ts:\s*([^,}]+)')      { $ts = $Matches[1].Trim() }
        if ($line -match 'phase:\s*([A-Za-z_]+)'){ $ph = $Matches[1] }
        if ($line -match 'event:\s*([A-Za-z_]+)'){ $ev = $Matches[1] }
        if (-not $ph -or -not $ev) { continue }
        $e = Mt-Epoch $ts
        if ($ev -ceq 'start') {
          if ($scount.ContainsKey($ph)) { $scount[$ph]++ } else { $scount[$ph]=1 }
          if ($e -ge 0) {
            if ($first -lt 0 -or $e -lt $first) { $first=$e; $firstts=$ts }
            if (-not $laststart.ContainsKey($ph) -or $e -gt $laststart[$ph]) { $laststart[$ph]=$e; $laststartTs[$ph]=$ts }
          }
        } elseif ($ev -ceq 'approved') {
          if ($e -ge 0) { $appat[$ph]=$e; $appatTs[$ph]=$ts }
          if ($ph -ceq 'deliver') { $deliveredFlag=$true; if ($e -ge 0) { $deliveredE=$e } }
        } elseif ($ev -ceq 'sent_back') { $sback++ }
      }
    }
    if ($phasesf) {
      foreach ($p in $script:PHASES) {
        if ($laststart.ContainsKey($p) -or $appat.ContainsKey($p)) {
          $st = if ($laststartTs.ContainsKey($p)) { $laststartTs[$p] } else { '-' }
          $ap = if ($appatTs.ContainsKey($p))     { $appatTs[$p] }     else { '-' }
          $el = '-'
          if ($laststart.ContainsKey($p) -and $appat.ContainsKey($p)) { $el = $appat[$p]-$laststart[$p] }
          $rows += ($name + "`t" + $p + "`t" + $st + "`t" + $ap + "`t" + $el)
        }
      }
    } else {
      $fs = if ($first -ge 0) { $firstts } else { '-' }
      $dv = if ($deliveredFlag) { 'yes' } else { 'no' }
      $lead = '-'
      if ($deliveredFlag -and $first -ge 0 -and $deliveredE -ge 0) { $lead = $deliveredE-$first }
      # 「手戻り回数」= やり直した回数（工程数で数えると分子が飽和する。sh 版と同一）
      $rw=0; foreach ($k in $scount.Keys) { if ($scount[$k] -ge 2) { $rw += $scount[$k] - 1 } }
      # ハーネス版で層別できるよう harnessRev / straddle を添える（sh 版と同一）
      $sty = Join-Path $wd 'state.yml'
      $hr = YGet $sty 'harnessRev'; if (-not $hr) { $hr = '-' }
      $hd = YGet $sty 'harnessRevDelivered'
      $sd = '-'
      if ($hd -and $hr -cne '-' -and $hr -cne 'unknown' -and $hd -cne 'unknown') { $sd = if ($hr -ceq $hd) { 'no' } else { 'yes' } }
      $rows += ($name + "`t" + $fs + "`t" + $dv + "`t" + $lead + "`t" + $rw + "`t" + $sback + "`t" + $hr + "`t" + $sd)
    }
  }

  if ($phasesf) { $hdr = "work`tphase`tstart`tapproved`telapsed_sec" }
  else          { $hdr = "work`tfirst_start`tdelivered`tlead_sec`treworks`tsent_backs`tharnessRev`tstraddle" }

  if ($fmt -ceq 'tsv') { foreach ($r in $rows) { Write-Output $r } }
  else { foreach ($l in (Fmt-Table (@($hdr) + $rows))) { Write-Output $l } }
}

# --- ハーネス改修の仮説登録（.aidev/harness/<id>.md。sh の hv_* と同一） --------------------
# 母集団 = introduced 以降に着手し、deliver 済みで、またがっていない（harnessRev == harnessRevDelivered）top-level work
function HvDir() { return (Join-Path $script:AIDEV 'harness') }
function HvFind($id) {
  $i = CvId $id
  $f = Join-Path (HvDir) "$i.md"; if (IsFile $f) { return $f }
  $f = Join-Path (Join-Path (HvDir) 'archive') "$i.md"; if (IsFile $f) { return $f }
  return ''
}
function HvRequire($path) {
  if (-not (CvGet $path 'harness') -and -not (CvGet $path 'status')) {
    Die "ハーネス改修の記録ではありません（harness / status がどちらも無い）: $path"
  }
}
function HvPopPrime() {
  if ($script:HvTsReady) { return }
  $script:HvTsReady = $true; $script:HvTs = @()
  $worksRoot = Join-Path $script:AIDEV 'works'
  if (-not (IsDir $worksRoot)) { return }
  foreach ($d in (Get-ChildItem -LiteralPath $worksRoot -Directory | Sort-Object Name)) {
    $pf = Join-Path $d.FullName 'metrics.yml'; $ps = Join-Path $d.FullName 'state.yml'
    if (-not (IsFile $pf) -or -not (IsFile $ps)) { continue }
    if (@(YList $ps 'approved') -cnotcontains 'deliver') { continue }
    $hr = YGet $ps 'harnessRev'; $hd = YGet $ps 'harnessRevDelivered'
    if (-not $hr -or $hr -ceq 'unknown') { continue }
    if ($hd -and $hd -cne $hr) { continue }
    $ts = CvFirstTs ([System.IO.File]::ReadAllLines($pf))
    if (-not $ts) { continue }
    $a = CvTsKey $ts
    if (-not $a) { continue }
    $script:HvTs += $a
  }
}
function HvPop($introduced) {
  $b = CvTsKey $introduced
  if (-not $b) { return 0 }
  HvPopPrime
  $n = 0
  foreach ($a in @($script:HvTs)) { if ([int64]$a -ge [int64]$b) { $n++ } }
  return $n
}
$script:HvForced = $false
function Hv-ExitGate($path, $force, $verb) {
  $script:HvForced = $false
  $va = CvGet $path 'verify_after'; if ($va -notmatch '^\d+$') { $va = '0' }
  if ([int]$va -le 0) { return }
  $in = CvGet $path 'introduced'
  $pop = 0; if ($in) { $pop = HvPop $in }
  if ([int]$pop -ge [int]$va) { return }
  if ($force) {
    Write-Output "warn: 母集団が揃っていません(pop $pop / need $va)。--force により $verb します（forced: true を刻む）"
    $script:HvForced = $true
    return
  }
  Die "母集団が揃っていません(pop $pop / need $va)。判定は揃ってから（aidev harness status）。それでも $verb するなら --force（理由を --result/--note に書く）"
}
function HvReadyNotice() {
  $d = HvDir
  if (-not (IsDir $d)) { return }
  foreach ($fi in (Get-ChildItem -LiteralPath $d -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)) {
    if ((CvGet $fi.FullName 'status') -cne 'pending') { continue }
    $intro = CvGet $fi.FullName 'introduced'
    if (-not $intro) { continue }
    $va = CvGet $fi.FullName 'verify_after'
    if ($va -notmatch '^\d+$') { continue }
    if ([int]$va -le 0) { continue }
    $pop = HvPop $intro
    if ([int]$pop -eq [int]$va) {
      $id = [System.IO.Path]::GetFileNameWithoutExtension($fi.Name)
      Write-Output "note: ハーネス改修 $id の母集団が揃いました($pop/$va)。insights で効果を判定してください"
    }
  }
}
function Hv-Archive($path) {
  $arc = Join-Path (HvDir) 'archive'
  if (-not (IsDir $arc)) { New-Item -ItemType Directory -Path $arc -Force | Out-Null }
  $dst = Join-Path $arc (Split-Path -Leaf $path)
  if (PathExists $dst) { Die "退避先が埋まっています: $dst" }
  Move-Item -LiteralPath $path -Destination $dst
}
function Hv-New($rest) {
  $id=''; $hyp=''; $src=''; $va=''; $base=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--hypothesis'   { $i++; $hyp=(ArgAt $rest $i '--hypothesis') }
      '--baseline'     { $i++; $base=(ArgAt $rest $i '--baseline') }
      '--source'       { $i++; $src=(ArgAt $rest $i '--source') }
      '--verify-after' { $i++; $va=(ArgAt $rest $i '--verify-after') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($id) { Die "id は1つだけ" } else { $id=$rest[$i] }
      }
    }
  }
  if (-not $id) { Die "使用法: aidev harness new <id> --hypothesis <text> --baseline <text> [--source <path>] [--verify-after <n>]" }
  $id = CvId $id
  if (-not $hyp) { Die "--hypothesis は必須です（どの指標がどう動けば効果ありと判定するか。書けない改修は効果を主張できない）" }
  if (-not $base) { Die "--baseline は必須です（改修前の値。例: '直近 10 works の reworks 平均 1.4' / '0件（前を作れない）'）" }
  if (-not $va) { $va = '5' }
  if ($va -notmatch '^\d+$') { Die "--verify-after は整数（母集団の最低件数）" }
  if ([int]$va -le 0) { Die "--verify-after は 1 以上" }
  $d = HvDir
  if (-not (IsDir $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
  $f = Join-Path $d "$id.md"
  if (PathExists $f) { Die "すでにあります: $f" }
  $arcf = Join-Path (Join-Path $d 'archive') "$id.md"
  if (IsFile $arcf) { Die "同じ id が archive にあります（$arcf）。判定済み改修の再登録は重複です" }
  $rev = HarnessRev
  $sb = "---`nharness: $id`nstatus: pending`nintroduced: $(Now)`nintroduced_rev: $rev`n"
  if ($src) { $sb += "source: $src`n" }
  $sb += "hypothesis: $hyp`nbaseline: $base`nverify_after: $va`n---`n`n"
  $sb += "# $id`n`n## 改修内容`n`n<!-- aidev-* のどこをどう変えたか。改修 PR/コミットへの参照 -->`n`n"
  $sb += "## 判定メモ`n`n<!-- confirm/retire 時の内訳の補足（frontmatter の result/note が正） -->`n"
  WriteText $f $sb
  Write-Output "created: $f (status pending, verify_after $va, introduced_rev $rev)"
  if ($rev -ceq 'unknown') { Write-Output "warn: harness_rev が取れない環境です（git 不在）。母集団は時刻だけで数えます" }
  Write-Output "next: ## 改修内容 を書く。母集団は導入後に着手し、またがらずに deliver した work（aidev harness status）"
}
function Hv-Confirm($rest) {
  $id=''; $result=''; $force=$false
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--result' { $i++; $result=(ArgAt $rest $i '--result') }
      '--force'  { $force=$true }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($id) { Die "id は1つだけ" } else { $id=$rest[$i] }
      }
    }
  }
  if (-not $id) { Die "使用法: aidev harness confirm <id> --result <text> [--force]" }
  if (-not $result) { Die "--result は必須です（判定の内訳: baseline と導入後の値、母集団の work 数）" }
  $f = HvFind $id
  if (-not $f) { Die "ハーネス改修の記録がありません: $id" }
  if ($f -match '[\\/]archive[\\/]') { Die "判定済みです: $id" }
  HvRequire $f
  Hv-ExitGate $f $force 'confirm'
  CvSet $f 'status' 'confirmed'
  CvSet $f 'result' $result
  if ($script:HvForced) { CvSet $f 'forced' 'true' }
  Hv-Archive $f
  Write-Output "confirmed: $id（archive へ退避）"
}
function Hv-Retire($rest) {
  $id=''; $st=''; $note=''; $force=$false
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--status' { $i++; $st=(ArgAt $rest $i '--status') }
      '--note'   { $i++; $note=(ArgAt $rest $i '--note') }
      '--force'  { $force=$true }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($id) { Die "id は1つだけ" } else { $id=$rest[$i] }
      }
    }
  }
  if (-not $id) { Die "使用法: aidev harness retire <id> --status ineffective|superseded --note <text> [--force]" }
  if ($st -ceq '') { Die "--status は必須です（ineffective|superseded）" }
  if ($st -cne 'ineffective' -and $st -cne 'superseded') { Die "未知の status: $st（ineffective|superseded）" }
  if (-not $note) { Die "--note は必須です（退役理由）" }
  $f = HvFind $id
  if (-not $f) { Die "ハーネス改修の記録がありません: $id" }
  if ($f -match '[\\/]archive[\\/]') { Die "判定済みです: $id" }
  HvRequire $f
  if ($st -ceq 'ineffective') { Hv-ExitGate $f $force 'retire' }
  CvSet $f 'status' $st
  CvSet $f 'note' $note
  if ($script:HvForced) { CvSet $f 'forced' 'true' }
  Hv-Archive $f
  Write-Output "retired: $id ($st)"
}
function Hv-Status($rest) {
  $fmt='table'
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--format' { $i++; $fmt=(ArgAt $rest $i '--format') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        Die "余分な引数: $($rest[$i])"
      }
    }
  }
  if ($fmt -cne 'table' -and $fmt -cne 'tsv') { Die "--format は table|tsv" }
  $d = HvDir
  if (-not (IsDir $d)) { Die "ハーネス改修の記録がありません: $d（aidev harness new で登録する）" }
  HvPopPrime
  $files = @()
  $files += (Get-ChildItem -LiteralPath $d -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)
  $arcPath = Join-Path $d 'archive'
  if (IsDir $arcPath) { $files += (Get-ChildItem -LiteralPath $arcPath -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name) }
  $rows=@(); $npend=0; $nready=0
  foreach ($fi in $files) {
    $id = [System.IO.Path]::GetFileNameWithoutExtension($fi.Name)
    $st = CvGet $fi.FullName 'status'; if (-not $st) { $st='-' }
    $intro = CvGet $fi.FullName 'introduced'; if (-not $intro) { $intro='-' }
    $rev = CvGet $fi.FullName 'introduced_rev'; if (-not $rev) { $rev='-' }
    $va = CvGet $fi.FullName 'verify_after'; if ($va -notmatch '^\d+$') { $va='0' }
    $isArc = $fi.DirectoryName -eq $arcPath
    $pop = if ($isArc) { '-' } elseif ($intro -ceq '-') { 0 } else { HvPop $intro }
    $ready='-'
    if ($st -ceq 'pending') {
      $npend++
      if ($pop -cne '-' -and [int]$va -gt 0 -and [int]$pop -ge [int]$va) { $ready='yes'; $nready++ } else { $ready='no' }
    }
    $rows += "$id`t$st`t$intro`t$rev`t$pop`t$va`t$ready"
  }
  if ($fmt -ceq 'tsv') { foreach ($r in $rows) { Write-Output "harness`t$r" } }
  else {
    $all = @("id`tstatus`tintroduced`tintroduced_rev`tpop`tneed`tready") + $rows
    foreach ($l in (Fmt-Table $all)) { Write-Output $l }
  }
  Write-Output "harness-summary: pending=$npend ready=$nready"
}
function Doctor-Harness() {
  $d = HvDir
  if (-not (IsDir $d)) { return }
  HvPopPrime
  $items=@()
  foreach ($f in (Get-ChildItem -LiteralPath $d -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)) { $items += ,@($f.FullName, $f.Name, $false) }
  $arc = Join-Path $d 'archive'
  if (IsDir $arc) { foreach ($f in (Get-ChildItem -LiteralPath $arc -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)) { $items += ,@($f.FullName, "archive/$($f.Name)", $true) } }
  $hfiles=0; $harch=0; $hwarn=0; $out=@()
  foreach ($it in $items) {
    $path=$it[0]; $label=$it[1]; $isArc=$it[2]
    if ($isArc) { $harch++ } else { $hfiles++ }
    $st = CvGet $path 'status'; $intro = CvGet $path 'introduced'; $va = CvGet $path 'verify_after'
    $w=@()
    if (-not $st) {
      $w += "    WARN frontmatter(status)が無い: pending/confirmed/ineffective/superseded"
    } elseif ($st -ceq 'pending') {
      if ($isArc) { $w += "    WARN 退避済みだが status=pending: 判定前に退避されている" }
      else {
        if ($va -notmatch '^\d+$') { $va='0' }
        if ($intro -and [int]$va -gt 0) {
          $pop = HvPop $intro
          if ([int]$pop -ge [int]$va) { $w += "    WARN 母集団が揃った($pop/$va)のに未判定: insights で効果を判定すること（aidev harness confirm|retire）" }
        }
      }
    } elseif ($st -ceq 'confirmed' -or $st -ceq 'ineffective' -or $st -ceq 'superseded') {
      if (-not $isArc) { $w += "    WARN $st だが未退避: archive/ へ移すこと（confirm/retire は CLI で打てば退避される）" }
    } else {
      $w += "    WARN 未知の status: $st（pending/confirmed/ineffective/superseded）"
    }
    if ($w.Count -gt 0) {
      $hwarn++
      $stl = if ($st) { $st } else { '-' }
      $out += "- $label (status=$stl)"
      $out += $w
    }
  }
  Write-Output "harness: ハーネス改修の記録検査"
  foreach ($l in $out) { Write-Output $l }
  Write-Output "harness-summary: files=$hfiles archived=$harch warn=$hwarn"
}
function Cmd-Harness($rest) {
  if ($rest.Count -lt 1) { Die "使用法: aidev harness <new|confirm|retire|status> ..." }
  $sub = $rest[0]
  $sr = @(); if ($rest.Count -gt 1) { $sr = $rest[1..($rest.Count-1)] }
  switch -CaseSensitive ($sub) {
    'new'     { Hv-New $sr }
    'confirm' { Hv-Confirm $sr }
    'retire'  { Hv-Retire $sr }
    'status'  { Hv-Status $sr }
    default   { Die "未知の harness サブコマンド: $sub（new|confirm|retire|status）" }
  }
}

# --- worktree（ユーザー責任の並行作業 on-ramp） --------------------------------
# .aidev/current は gitignore 対象＝worktree ローカルで main と非干渉。worktree 操作は main の current を書き換えない(INV-1)。
function GitPresent() { if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "git が見つかりません" } }

function DefaultWtPath($slug) {
  $parent = Split-Path $script:ROOT -Parent
  $repo = Split-Path $script:ROOT -Leaf
  return (Join-Path (Join-Path $parent "$repo-wt") $slug)
}

# worktree 内で state.yml の slug が一致する work dir 名（dated）の配列を返す
function WorksMatchingSlug($path, $slug) {
  $res = @()
  $wd = Join-Path (Join-Path $path '.aidev') 'works'
  if (-not (IsDir $wd)) { return $res }
  foreach ($d in (Get-ChildItem -LiteralPath $wd -Directory | Sort-Object Name)) {
    $st = Join-Path $d.FullName 'state.yml'
    if (-not (IsFile $st)) { continue }
    if ((YGet $st 'slug') -ceq $slug) { $res += $d.Name }
  }
  return $res
}

# git worktree list --porcelain を "path<TAB>branch" 配列に整形（sh の wt_porcelain と一致）
function WtPorcelain() {
  $out=@(); $p=''; $b=''
  foreach ($line in (git worktree list --porcelain)) {
    if ($line -like 'worktree *') {
      if ($p -cne '') { $out += ($p + "`t" + ($(if ($b -ceq '') { '-' } else { $b }))); $b='' }
      $p = $line.Substring(9)
    } elseif ($line -like 'branch *') {
      $b = $line.Substring(7) -replace '^refs/heads/',''
    } elseif ($line -like 'detached*') {
      $b = 'detached'
    }
  }
  if ($p -cne '') { $out += ($p + "`t" + ($(if ($b -ceq '') { '-' } else { $b }))) }
  return $out
}

# 共有ファイル警告。PJ 固有のファイル名は CLI に埋めず .aidev/config.yml の sharedFiles から生成する
# （基盤は PJ 非依存＝DESIGN「1.」「2.」。機械が言えるのは config にある事実だけで、検証義務のような
#  PJ 規約は散文＝AGENTS.md / protocol-worktree.md の担当。DESIGN「2.6」の線引きと同じ）。
function Wt-SharedWarn {
  $sh = @(YList (Join-Path $script:AIDEV 'config.yml') 'sharedFiles')
  if ($sh.Count -gt 0) {
    Write-Output "⚠ この work が共有ファイル（$($sh -join ', ')）に触るなら、他 worktree と"
    Write-Output "  波及・マージ衝突が起きうる（PJ 規約は AGENTS.md）。並行可否はユーザー判断。"
  } else {
    Write-Output "⚠ この work が他 worktree と共有するもの（ビルド設定・登録テーブル・共有モジュール等）に触るなら、"
    Write-Output "  波及・マージ衝突が起きうる（PJ 規約は AGENTS.md。config.yml の sharedFiles で名指しできる）。並行可否はユーザー判断。"
  }
}

function Wt-Add($rest) {
  $slug=''; $branch=''; $base='HEAD'; $wpath=''; $mode='interactive'; $ticket=''; $depends=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--branch'  { $i++; $branch=(ArgAt $rest $i '--branch') }
      '--base'    { $i++; $base=(ArgAt $rest $i '--base') }
      '--path'    { $i++; $wpath=(ArgAt $rest $i '--path') }
      '--mode'    { $i++; $mode=(ArgAt $rest $i '--mode') }
      '--ticket'  { $i++; $ticket=(ArgAt $rest $i '--ticket') }
      '--depends' { $i++; $depends=(ArgAt $rest $i '--depends') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($slug) { Die "slug は1つだけ" } else { $slug=$rest[$i] }
      }
    }
  }
  if (-not $slug) { Die "使用法: aidev worktree add <slug> [--branch ..] [--base ..] [--path ..] [--mode ..] [--ticket ..] [--depends ..]" }
  GitPresent
  if (-not $branch) { $branch = "feature/$slug" }
  if (-not $wpath)  { $wpath = DefaultWtPath $slug }
  if (PathExists $wpath) { Die "path が既に存在します: $wpath" }

  # ブランチ存在で分岐（既存→checkout / 新規→-b で base から作成）。branch は必ず明示。実 exit code を判定。
  git show-ref --verify --quiet "refs/heads/$branch"
  if ($LASTEXITCODE -eq 0) {
    $wtNewBranch = $false
    git worktree add "$wpath" "$branch"
    if ($LASTEXITCODE -ne 0) { Die "git worktree add に失敗（branch=$branch）" }
  } else {
    $wtNewBranch = $true
    git worktree add -b "$branch" "$wpath" "$base"
    if ($LASTEXITCODE -ne 0) { Die "git worktree add に失敗（branch=$branch base=$base）" }
  }
  $wpath = (Resolve-Path -LiteralPath $wpath).Path

  # ここから先の Die は worktree を作った後に起きる。ロールバックしないと、失敗したのに
  # worktree とブランチだけが残り、次の add が「既にある」で弾かれる（sh 版と同一）
  $wtRollback = {
    param($msg)
    git worktree remove --force $wpath 2>$null | Out-Null
    if ($wtNewBranch) { git branch -D $branch 2>$null | Out-Null }
    git worktree prune 2>$null | Out-Null
    # 既定のコンテナも空なら掃除する（rm と同じ後始末）
    $cont = Split-Path $wpath -Parent
    if ((IsDir $cont) -and -not (Get-ChildItem -LiteralPath $cont -Force)) { Remove-Item -LiteralPath $cont -Force }
    Die "$msg（作りかけの worktree とブランチは撤去した）"
  }

  # worktree 内で work を確定（main tree の .aidev/current には触れない＝INV-1）
  # @() で配列強制（要素1個だと return がスカラー文字列にアンロールし $mw[0] が先頭1文字になるのを防ぐ）
  $mw = @(WorksMatchingSlug $wpath $slug)
  if ($mw.Count -gt 1) {
    & $wtRollback "worktree 内に slug=$slug の work が複数あります。曖昧なため中断（手動で current 設定を）"
  } elseif ($mw.Count -eq 1) {
    WriteText (Join-Path (Join-Path $wpath '.aidev') 'current') ($mw[0] + "`n")
    $workNote = "既存 work をリンク: $($mw[0])（current 設定のみ）"
  } else {
    # add 内で new: worktree をカレントにして既存 new ロジックに委譲（単一検証経路の維持・DRY）
    # CLI は skills 同梱＝`.claude/skills/aidev-docs/bin/`（sh 版と同じ正典パス。protocol.md「4.1」）。
    $bin = [System.IO.Path]::Combine($wpath, '.claude', 'skills', 'aidev-docs', 'bin', 'aidev.ps1')
    if (-not (IsFile $bin)) { & $wtRollback "worktree 内に CLI がありません: $bin（skills が追跡・コミット済みか確認）" }
    $argv = @('new', $slug, '--mode', $mode)
    if ($ticket)  { $argv += @('--ticket', $ticket) }
    if ($depends) { $argv += @('--depends', $depends) }
    # ロールバックは **Pop-Location の後**に回す。try の中で呼ぶと finally の Pop-Location と
    # 二重になり、しかも worktree の中に居るまま `git worktree remove` を打つことになる
    Push-Location $wpath
    $newFailed = $false
    try { & (PsHost) @(PsHostArgs $bin) @argv; if ($LASTEXITCODE -ne 0) { $newFailed = $true } }
    finally { Pop-Location }
    if ($newFailed) { & $wtRollback "worktree 内の new に失敗" }
    $workNote = "新規 work を作成（add 内で new）"
  }

  Write-Output "worktree 追加: $wpath"
  Write-Output "  branch: $branch / base: $base"
  Write-Output "  work:   $workNote"
  Wt-SharedWarn
  Write-Output "次: cd $wpath して各工程 skill を実行。"
}

function Wt-List($rest) {
  $fmt='table'
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--format' { $i++; $fmt=(ArgAt $rest $i '--format') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        else { Die "list は位置引数を取りません: $($rest[$i])" }
      }
    }
  }
  if ($fmt -cne 'table' -and $fmt -cne 'tsv') { Die "--format は table|tsv" }
  GitPresent

  $rows=@()
  foreach ($line in (WtPorcelain)) {
    $cols = $line -split "`t"; $path = $cols[0]; $branch = $cols[1]
    # 判定キー: worktree ローカル .aidev/current の有無（branch 名ではない）
    $cur = Join-Path (Join-Path $path '.aidev') 'current'
    if (-not (IsFile $cur)) { continue }
    $lines = [System.IO.File]::ReadAllLines($cur)
    $work = if ($lines.Count -ge 1) { $lines[0].Trim() } else { '' }
    if (-not $work) { $work = '-' }
    $phase = '-'
    $st = Join-Path (Join-Path (Join-Path (Join-Path $path '.aidev') 'works') $work) 'state.yml'
    if ($work -cne '-' -and (IsFile $st)) { $phase = YGet $st 'current'; if (-not $phase) { $phase='-' } }
    $rows += ($path + "`t" + $branch + "`t" + $work + "`t" + $phase)
  }

  if ($fmt -ceq 'tsv') {
    foreach ($r in $rows) { Write-Output ("worktree`t" + $r) }
    return
  }
  Write-Output ("WORKTREES (" + $rows.Count + ")")
  if ($rows.Count -gt 0) { foreach ($l in (Fmt-Table (@("path`tbranch`twork`tphase") + $rows))) { Write-Output $l } }
}

function Wt-Rm($rest) {
  $target=''; $force=$false; $delbranch=$false
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--force' { $force=$true }
      '--delete-branch' { $delbranch=$true }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($target) { Die "対象は1つだけ" } else { $target=$rest[$i] }
      }
    }
  }
  if (-not $target) { Die "使用法: aidev worktree rm <slug|path> [--force] [--delete-branch]" }
  GitPresent

  $abst=''
  if (IsDir $target) { $abst = PathKey (Resolve-Path -LiteralPath $target).Path }
  $wts = @(WtPorcelain)
  $mainWt = if ($wts.Count -ge 1) { ($wts[0] -split "`t")[0] } else { '' }  # porcelain 先頭＝main worktree（rm 対象外）
  $rpath=''; $rbranch=''; $hitMain=$false
  foreach ($line in $wts) {
    $cols = $line -split "`t"; $p = $cols[0]; $b = $cols[1]
    if ($abst) {
      if ((PathKey $p) -eq $abst) { $rpath=$p; $rbranch=$b; break }   # パス比較は OS の流儀に従う
    } else {
      if ((Split-Path $p -Leaf) -eq $target -or $b -eq "feature/$target" -or $b -eq $target) {
        if ($p -eq $mainWt) { $hitMain=$true; continue }  # slug が main worktree に一致しても対象にしない
        if ($rpath) { Die "対象が複数該当します（path を明示してください）: $target" }
        $rpath=$p; $rbranch=$b
      }
    }
  }
  if (-not $rpath) {
    if ($hitMain) { Die "'$target' は main worktree（$mainWt）に該当します。main worktree は rm できません（worktree のみ対象）。" }
    Die "対象 worktree が見つかりません: $target"
  }

  if (-not $force) {
    $dirty = (git -C "$rpath" status --porcelain)
    if ($dirty) { Die "未コミットの変更があります（--force で強制削除）: $rpath" }
  }
  if ($force) { git worktree remove --force "$rpath" } else { git worktree remove "$rpath" }
  if ($LASTEXITCODE -ne 0) { Die "git worktree remove に失敗: $rpath" }
  Write-Output "worktree 撤去: $rpath"
  $container = Split-Path $rpath -Parent
  # -Force を落とすと隠しファイルだけのディレクトリを「空」とみなして消す。
  # sh 側は rmdir で、非空なら失敗して何もしない（隠しファイルも中身と数える）
  if ((IsDir $container) -and -not (Get-ChildItem -LiteralPath $container -Force)) { Remove-Item -LiteralPath $container -Force }

  if ($delbranch -and $rbranch -cne '-' -and $rbranch -cne 'detached') {
    git branch -D "$rbranch"
    if ($LASTEXITCODE -eq 0) { Write-Output "  branch 削除: $rbranch" } else { Warn "branch 削除に失敗: $rbranch" }
  }
}

# --- use（継続する作業の切り替え）。sh 版と同一 --------------------------------
function Cmd-Use($rest) {
  if ($rest.Count -eq 0) {
    $cur = Join-Path $script:AIDEV 'current'
    if (-not (IsFile $cur)) { Die "対象作業が不明です（.aidev/current 無し）" }
    Write-Output (([System.IO.File]::ReadAllLines($cur))[0].Trim())
    return
  }
  if ($rest.Count -ne 1) { Die "使用法: aidev use [<slug>]" }
  ResolveWork $rest[0]
  WriteText (Join-Path $script:AIDEV 'current') "$($script:SLUG)`n"
  $ph = YGet (Join-Path $script:WORK 'state.yml') 'current'
  Write-Output "current: $($script:SLUG) ($ph)"
  # subtask に切り替えたら親の activeSubtask も合わせる（activeSubtask は current の冗長コピー）
  $upar = YGet (Join-Path $script:WORK 'state.yml') 'parent'
  if ($upar) {
    $ppath = Join-Path (Join-Path $script:AIDEV 'works') $upar
    if (IsDir $ppath) {
      $leaf = Split-Path $script:WORK -Leaf
      SetOrAppend (Join-Path $ppath 'state.yml') 'activeSubtask' "activeSubtask: $leaf"
      Write-Output "cursor: 親 $upar の activeSubtask を $leaf に同期"
    }
  }
}

# --- unapprove ---------------------------------------------------------------
# 差し戻しで無効化される後工程の承認を取り消す。元は「approved から手で除く」だったが、
# それは state.yml の更新を CLI に集約するという原則と矛盾する（sh 版のコメント参照）。
# 記録は消さない——取り消し自体を sent_back イベントとして刻む（手戻りは実際に起きた事実）。
function Cmd-Unapprove($rest) {
  $uslug=''; $uph=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--slug' { $i++; $uslug=(ArgAt $rest $i '--slug') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        elseif ($uph) { Die "工程は1つだけ" } else { $uph = $rest[$i] }
      }
    }
  }
  if (-not $uph) { Die "使用法: aidev unapprove <phase> [--slug <work>]" }
  if (-not (IsPhase $uph)) { Die "未知の工程: $uph" }
  ResolveWork $uslug
  $st = Join-Path $script:WORK 'state.yml'
  if (-not (ApprovedHas $script:WORK $uph)) { Die "承認されていません: $uph @ $($script:SLUG)" }

  $keep = @(@(YList $st 'approved') | Where-Object { $_ -cne $uph })
  ReplaceLine $st 'approved' ('approved: [' + ([string]::Join(', ', $keep)) + ']')
  ReplaceLine $st 'current' "current: $uph"
  AppendEvent $script:WORK $uph 'sent_back' @()
  Write-Output "unapproved: $uph @ $($script:SLUG)"
  Write-Output "next: やり直す工程で aidev event <phase> start を記録すること（統合 review からの差し戻しは coding）"

  $par = YGet $st 'parent'
  if ($par -and $uph -ceq 'review') {
    $ppath = Join-Path (Join-Path $script:AIDEV 'works') $par
    if (IsDir $ppath) {
      $leaf = Split-Path $script:WORK -Leaf
      SetOrAppend (Join-Path $ppath 'state.yml') 'activeSubtask' "activeSubtask: $leaf"
      Write-Output "cursor: 親 $par の activeSubtask を $leaf に戻した"
    }
  }
}

# --- backlog（積む/退避する。消し込みは判断の仕事なので CLI に持たせない） -----------
function Cmd-Backlog($rest) {
  if ($rest.Count -lt 1) { Die "使用法: aidev backlog <new|archive|compact> ..." }
  $sub = $rest[0]
  $sr = @(); if ($rest.Count -gt 1) { $sr = $rest[1..($rest.Count-1)] }
  switch -CaseSensitive ($sub) {
    'new'     { Bl-New $sr }
    'archive' { Bl-DoArchive $sr }
    'compact' { Bl-Compact $sr }
    default   { Die "未知の backlog サブコマンド: $sub（new|archive|compact）" }
  }
}

# standing backlog の [x] 行（と継続行）を archive/<name>-done.md へ移して active を薄く保つ（sh の bl_compact と同一）
function Bl-Compact($rest) {
  $targets=@(); $explicit=$true
  foreach ($a in @($rest)) {
    if ($a.StartsWith('-')) { Die "未知のオプション: $a" }
    $targets += (Split-Path -Leaf $a)
  }
  $blRoot = Join-Path $script:AIDEV 'backlog'
  if (-not (IsDir $blRoot)) { Die "backlog がありません" }
  if ($targets.Count -eq 0) {
    $explicit=$false
    foreach ($f in (Get-ChildItem -LiteralPath $blRoot -File -Filter *.md | Sort-Object Name)) {
      BlStat $f.FullName
      if ($script:BL_KIND -ceq 'standing' -and $script:BL_DN -gt 0) { $targets += $f.Name }
    }
  }
  $moved = 0
  foreach ($t in $targets) {
    $f = Join-Path $blRoot $t
    if (-not (IsFile $f)) { Write-Output "skip ${t}: active にありません"; continue }
    BlStat $f
    $bdn = $script:BL_DN
    if ($bdn -eq 0) {
      if ($explicit) { Write-Output "skip ${t}: 消化済み項目がありません" }
      continue
    }
    $arc = Join-Path $blRoot 'archive'
    if (-not (IsDir $arc)) { New-Item -ItemType Directory -Path $arc -Force | Out-Null }
    $base = $t -replace '\.md$',''
    $dn = Join-Path $arc ($base + '-done.md')
    if (-not (IsFile $dn)) {
      WriteText $dn ("# $base (done)`n`n<!-- aidev backlog compact が退避した消化済み項目。verify の消し込み検査はここも見る -->`n")
    }
    $keep=@(); $mv=@(); $inx=$false
    foreach ($l in [System.IO.File]::ReadAllLines($f)) {
      if ($l -match '^\s*- \[[xX]\]') { $inx = $true }
      elseif ($l -match '^\s*- \[[^xX]\]' -or $l -match '^#' -or $l -match '^\s*$') { $inx = $false }
      if ($inx) { $mv += $l } else { $keep += $l }
    }
    AppendText $dn (($mv -join "`n") + "`n")
    WriteText $f (($keep -join "`n") + "`n")
    Write-Output "compacted: $t -> archive/$base-done.md ($bdn 件)"
    $moved += $bdn
  }
  Write-Output "compact-summary: moved=$moved"
}

function Bl-New($rest) {
  $name=''; $kind=''; $parent=''; $priority=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--kind'     { $i++; $kind=(ArgAt $rest $i '--kind') }
      '--parent'   { $i++; $parent=(ArgAt $rest $i '--parent') }
      '--priority' { $i++; $priority=(ArgAt $rest $i '--priority') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($name) { Die "名前は1つだけ" } else { $name=$rest[$i] }
      }
    }
  }
  if (-not $name) { Die "使用法: aidev backlog new <name> --kind standing|split|topic [--parent <slug>] [--priority <n>]" }
  if ($name.EndsWith('.md')) { $name = $name.Substring(0, $name.Length-3) }
  $name = Split-Path -Leaf $name
  if ($kind -ceq 'split') {
    if (-not $parent) { Die "kind: split には --parent が要ります（親 work slug / チケット）" }
  } elseif ($kind -ceq '') {
    Die "--kind は必須です（standing|split|topic）"
  } elseif ($kind -cne 'standing' -and $kind -cne 'topic') {
    Die "未知の kind: $kind（standing|split|topic）"
  }
  $blRoot = Join-Path $script:AIDEV 'backlog'
  if (-not (IsDir $blRoot)) { New-Item -ItemType Directory -Path $blRoot -Force | Out-Null }
  $f = Join-Path $blRoot "$name.md"
  if (PathExists $f) { Die "すでにあります: .aidev/backlog/$name.md" }
  $sb = "---`nbacklog: $name`nkind: $kind`n"
  if ($parent)   { $sb += "parent: $parent`n" }
  if ($priority) { $sb += "priority: $priority`n" }
  $sb += "---`n`n# $name`n`n"
  $sb += "<!-- 項目は行頭の ``- [ ]`` で書く（見出しに書くと aidev status の未着手件数から漏れる） -->`n"
  WriteText $f $sb
  Write-Output "created: .aidev/backlog/$name.md (kind $kind)"
}

function Bl-DoArchive($rest) {
  $force=$false; $targets=@(); $explicit=$true
  foreach ($a in $rest) {
    if ($a -ceq '--force') { $force=$true }
    elseif ($a.StartsWith('-')) { Die "未知のオプション: $a" }
    else { $targets += (Split-Path -Leaf $a) }
  }
  $blRoot = Join-Path $script:AIDEV 'backlog'
  if (-not (IsDir $blRoot)) { Die "backlog がありません" }
  if ($targets.Count -eq 0) {
    $explicit=$false
    foreach ($f in (Get-ChildItem -LiteralPath $blRoot -File -Filter *.md | Sort-Object Name)) {
      if (BlArchivable $f.FullName) { $targets += $f.Name }
    }
  }

  $moved=0; $skipped=0
  $arcRoot = Join-Path $blRoot 'archive'
  foreach ($t in $targets) {
    $f = Join-Path $blRoot $t
    if (-not (IsFile $f)) {
      Write-Output "skip ${t}: active にありません"; $skipped++; continue
    }
    if ((-not $force) -and (-not (BlArchivable $f))) {
      if ($explicit) {
        $k = if ([string]::IsNullOrEmpty($script:BL_KIND)) { '-' } else { $script:BL_KIND }
        Write-Output "skip ${t}: 退避条件を満たしません (kind=$k todo=$($script:BL_TODO) done=$($script:BL_DN))"
      }
      $skipped++; continue
    }
    if (-not (IsDir $arcRoot)) { New-Item -ItemType Directory -Path $arcRoot -Force | Out-Null }
    if (PathExists (Join-Path $arcRoot $t)) {
      Write-Output "skip ${t}: archive/ に同名があります"; $skipped++; continue
    }
    Move-Item -LiteralPath $f -Destination (Join-Path $arcRoot $t)
    Write-Output "archived: $t"; $moved++
  }
  Write-Output "summary: archived=$moved skipped=$skipped"
  if ($moved -gt 0) {
    Write-Output "note: git 未反映（``git add -A .aidev/backlog`` でリネームとして拾われる）"
  }
}

# --- コマンド: convention -----------------------------------------------------
# 起こす／状態を進める／退避するだけを持たせる。本文を PJ ドキュメントへ実際に移す作業は
# 文体・配置・既存章との統合という判断なので CLI にしない（backlog の消し込み本体と同じ線引き）。
function Cmd-Convention($rest) {
  if ($rest.Count -lt 1) { Die "使用法: aidev convention <new|confirm|retire|defer|promote|status> ..." }
  $sub = $rest[0]
  $sr = @(); if ($rest.Count -gt 1) { $sr = $rest[1..($rest.Count-1)] }
  switch -CaseSensitive ($sub) {
    'new'     { Cv-New $sr }
    'defer'   { Cv-Defer $sr }
    'confirm' { Cv-Confirm $sr }
    'retire'  { Cv-Retire $sr }
    'promote' { Cv-Promote $sr }
    'status'  { Cv-Status $sr }
    default   { Die "未知の convention サブコマンド: $sub（new|confirm|retire|promote|status）" }
  }
}

function Cv-ArchiveFile($path) {
  CvArchiveFree $path
  $d = CvDir
  $arc = Join-Path $d 'archive'
  if (-not (IsDir $arc)) { New-Item -ItemType Directory -Path $arc -Force | Out-Null }
  $b = Split-Path -Leaf $path
  $dest = Join-Path $arc $b
  Move-Item -LiteralPath $path -Destination $dest
  Write-Output "archived: $dest"
}

function Cv-New($rest) {
  $id=''; $hyp=''; $src=''; $va=''; $base=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--hypothesis'   { $i++; $hyp=(ArgAt $rest $i '--hypothesis') }
      '--baseline'     { $i++; $base=(ArgAt $rest $i '--baseline') }
      '--source'       { $i++; $src=(ArgAt $rest $i '--source') }
      '--verify-after' { $i++; $va=(ArgAt $rest $i '--verify-after') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($id) { Die "id は1つだけ" } else { $id=$rest[$i] }
      }
    }
  }
  if (-not $id) { Die "使用法: aidev convention new <id> --hypothesis <text> --baseline <text> [--source <path>] [--verify-after <n>]" }
  if ($id.EndsWith('.md')) { $id = $id.Substring(0, $id.Length-3) }
  $id = Split-Path -Leaf $id
  # 仮説を必須にするのがこの層の入口ゲート。「どの指標がどう動けば成功か」を書けない条項は
  # 後から検証できず、事後の物語作りにしかならない
  if (-not $hyp) { Die "--hypothesis は必須です（何がどう動けば効果ありと判定するか。書けない条項は検証できない）" }
  # 条項 id は今この瞬間に生まれるので、導入前の review.md にその id は現れない。
  # 「前」を作れるのは起票時に観点で数えて刻む道だけ（sh 版と同じ理由）。
  if (-not $base) { Die "--baseline は必須です（導入前にこの観点の指摘が何件あったか。数えられないならその事実を書く。例: '直近10 works で must 2 / should 5' / '0件（review.md が無く前を作れない）'）" }
  if (-not $va) { $va = '5' }
  if ($va -notmatch '^\d+$') { Die "--verify-after は整数（母集団の最低件数）" }
  # 0 は受理すると永久に ready=no（判定側が va>0 を要求する）。入口で弾く
  if ([int]$va -le 0) { Die "--verify-after は 1 以上（0 だと母集団が揃わず永久に判定できない）" }
  $d = CvDir
  if (-not (IsDir $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
  $f = Join-Path $d "$id.md"
  if (PathExists $f) { Die "すでにあります: $f" }
  $arcf = Join-Path (Join-Path $d 'archive') "$id.md"
  if (IsFile $arcf) { Die "同じ id が archive にあります（$arcf）。移送済み条項の再提案は重複です" }
  $now = Now
  $sb = "---`nconvention: $id`nstatus: pending`nintroduced: $now`n"
  if ($src) { $sb += "source: $src`n" }
  $sb += "hypothesis: $hyp`nbaseline: $base`nverify_after: $va`n---`n`n"
  $sb += "# $id`n`n"
  $sb += "<!-- 条項の本文。PJ ドキュメントへ移送(promote)するまではここが唯一の在処。 -->`n`n"
  $sb += "## 規約`n`n"
  $sb += "<!-- 何を守るか。レビューで指摘するときの根拠になる粒度で書く。 -->`n`n"
  $sb += "## 背景`n`n"
  $sb += "<!-- どのレビュー指摘/分析から起こしたか（source を人間向けに補足）。 -->`n"
  WriteText $f $sb
  Write-Output "created: $f (status pending, verify_after $va)"
  # 索引に載せないと自動読込されない＝読まれない。doctor も見るが、まずここで促す
  $rel = "$(CvDirRel)/$id.md"
  $idxl = CvIndexLabel
  Write-Output "next: $idxl の索引ブロックに1行足すこと（読む条件つき。無いと読まれない。protocol.md「12.」）"
  Write-Output "      - <いつ参照するか> → $rel"
  # 入口の重複排除。どこを見るかは PJ が config で申告する（探索範囲の決定は判断なので CLI はしない）
  $dr = @(YList (Join-Path $script:AIDEV 'config.yml') 'docsRoots')
  if ($dr.Count -gt 0) {
    Write-Output "check: 同じ規約が既存 docs に無いか確認すること（docsRoots: $($dr -join ', ')）"
  } else {
    Write-Output "check: .aidev/config.yml に docsRoots が未設定です。既存 docs との重複を機械的に絞れないので、"
    Write-Output "       確認していない旨を retro/insights に明記すること（捏造で埋めない。protocol.md「8.」）"
  }
}

# 出口ゲート: 母集団が verify_after に達していない条項は判定させない（sh の cv_exit_gate と同じ）。
# --force は理由必須の非常口で、呼び出し側が frontmatter に forced: true を刻む
$script:CvForced = $false
function Cv-ExitGate($path, $force, $verb) {
  $script:CvForced = $false
  $va = CvGet $path 'verify_after'; if ($va -notmatch '^\d+$') { $va = '0' }
  if ([int]$va -le 0) { return }
  $in = CvGet $path 'introduced'
  $pop = 0; if ($in) { $pop = CvPop $in }
  if ([int]$pop -ge [int]$va) { return }
  if ($force) {
    Write-Output "warn: 母集団が揃っていません(pop $pop / need $va)。--force により $verb します（forced: true を刻む）"
    $script:CvForced = $true
    return
  }
  Die "母集団が揃っていません(pop $pop / need $va)。判定は揃ってから（aidev convention status）。それでも $verb するなら --force（理由を --result/--note に書く）"
}

# 判定を先送りする（sh の cv_defer と同一）。必要件数を積み増して次に揃うまで黙らせる。理由必須
function Cv-Defer($rest) {
  $id=''; $va=''; $note=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--verify-after' { $i++; $va=(ArgAt $rest $i '--verify-after') }
      '--note'         { $i++; $note=(ArgAt $rest $i '--note') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($id) { Die "id は1つだけ" } else { $id=$rest[$i] }
      }
    }
  }
  if (-not $id) { Die "使用法: aidev convention defer <id> --verify-after <n> --note <text>" }
  if ($va -notmatch '^\d+$') { Die "--verify-after は整数（先送り後に必要な母集団件数）" }
  if (-not $note) { Die "--note は必須です（なぜ先送りするか。理由の無い先送りは pending の滞留と区別できない）" }
  $f = CvFind $id
  if (-not $f) { Die "条項がありません: $id" }
  if ($f -match '[\\/]archive[\\/]') { Die "退避済みの条項は変更できません: $id" }
  CvRequire $f
  if ((CvGet $f 'status') -cne 'pending') { Die "pending の条項だけ先送りできます: $id" }
  $in = CvGet $f 'introduced'
  $pop = 0; if ($in) { $pop = CvPop $in }
  if ([int]$va -le [int]$pop) { Die "--verify-after $va は現在の母集団 $pop 以下なので黙りません（$([int]$pop+1) 以上を指定）" }
  CvSet $f 'verify_after' $va
  CvSet $f 'deferred' (Now)
  CvSet $f 'defer_note' $note
  Write-Output "deferred: $id (verify_after $va, pop $pop)"
}

function Cv-Confirm($rest) {
  $id=''; $result=''; $force=$false
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--result' { $i++; $result=(ArgAt $rest $i '--result') }
      '--force'  { $force=$true }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($id) { Die "id は1つだけ" } else { $id=$rest[$i] }
      }
    }
  }
  if (-not $id) { Die "使用法: aidev convention confirm <id> --result <text> [--force]" }
  # 内訳の無い confirm は後から検証できない
  if (-not $result) { Die "--result は必須です（判定の内訳: baseline と導入後の件数、母集団の work 数。書けない判定は残せない）" }
  $f = CvFind $id
  if (-not $f) { Die "条項がありません: $id" }
  if ($f -match '[\\/]archive[\\/]') { Die "退避済みの条項は変更できません: $id" }
  CvRequire $f
  Cv-ExitGate $f $force 'confirm'
  CvSet $f 'status' 'confirmed'
  CvSet $f 'result' $result
  if ($script:CvForced) { CvSet $f 'forced' 'true' }
  Write-Output "confirmed: $id"
  Write-Output "next: 本文を PJ ドキュメントへ移し、``aidev convention promote $id --to <path#anchor>`` で tombstone 化する"
}

function Cv-Retire($rest) {
  $id=''; $st=''; $note=''; $force=$false
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--status' { $i++; $st=(ArgAt $rest $i '--status') }
      '--note'   { $i++; $note=(ArgAt $rest $i '--note') }
      '--force'  { $force=$true }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($id) { Die "id は1つだけ" } else { $id=$rest[$i] }
      }
    }
  }
  if (-not $id) { Die "使用法: aidev convention retire <id> --status ineffective|superseded --note <text> [--force]" }
  if ($st -ceq '') { Die "--status は必須です（ineffective|superseded）" }
  if ($st -cne 'ineffective' -and $st -cne 'superseded') { Die "未知の status: $st（ineffective|superseded）" }
  # 理由の無い退役は tombstone に何も残さず、同じ観点の再提案を弾く根拠にならない
  if (-not $note) { Die "--note は必須です（退役理由。ineffective なら何が効かなかったか、superseded なら何に置き換わったか）" }
  $f = CvFind $id
  if (-not $f) { Die "条項がありません: $id" }
  if ($f -match '[\\/]archive[\\/]') { Die "すでに退避済みです: $id" }
  CvRequire $f
  # superseded は置き換えなので母集団は要らない。ineffective は効果判定なので要る
  if ($st -ceq 'ineffective') { Cv-ExitGate $f $force 'retire' }
  CvSet $f 'status' $st
  CvSet $f 'note' $note
  if ($script:CvForced) { CvSet $f 'forced' 'true' }
  Cv-ArchiveFile $f
  Write-Output "retired: $id ($st)"
  # 退役しても索引ブロックの行は残る（promote の張り替えと同じ後始末）。doctor も検査するが、まずここで促す
  Write-Output "next: $(CvIndexLabel) の索引ブロックから $(CvDirRel)/$id.md の行を消すこと"
  if ($st -ceq 'ineffective') {
    Write-Output "note: 「効かなかった」は「条項が誤り」とは限らない。散文層の限界なら CLI/フック層へ寄せることを検討（DESIGN「2.6」）"
  }
}

function Cv-Promote($rest) {
  $id=''; $to=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--to' { $i++; $to=(ArgAt $rest $i '--to') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($id) { Die "id は1つだけ" } else { $id=$rest[$i] }
      }
    }
  }
  if (-not $id) { Die "使用法: aidev convention promote <id> --to <path#anchor>" }
  if (-not $to) { Die "--to は必須です（移送先の PJ ドキュメント。例 docs/coding-standards.md#naming）" }
  $f = CvFind $id
  if (-not $f) { Die "条項がありません: $id" }
  if ($f -match '[\\/]archive[\\/]') { Die "すでに退避済みです: $id" }
  CvRequire $f
  # 移送先の実在を確かめる。dangling な promoted_to は「本文がどこにも無い」状態を作る
  $tgt = ($to -split '#')[0]
  $tpath = if ([System.IO.Path]::IsPathRooted($tgt)) { $tgt } else { Join-Path $script:ROOT $tgt }
  if (-not (IsFile $tpath)) { Die "移送先が見つかりません: $tgt（先に本文を移してから promote する）" }
  # 破壊の前に退避先の衝突を見る。後ろで見ると、本文を捨てた後に失敗して
  # 「tombstone だけが active に残る」という直せない状態になる
  CvArchiveFree $f
  $today = ('{0:D4}-{1:D2}-{2:D2}' -f [DateTime]::UtcNow.Year, [DateTime]::UtcNow.Month, [DateTime]::UtcNow.Day)
  CvSet $f 'status' 'promoted'
  CvSet $f 'promoted_to' $to
  CvSet $f 'promoted_at' $today
  CvTombstone $f "本文は promoted_to へ移送済み。ここには置かない（本文の在処は常に1箇所）。"
  Cv-ArchiveFile $f
  Write-Output "promoted: $id -> $to"
  Write-Output "next: $(CvIndexLabel) の索引ブロックのリンク先を $to に張り替えること"
}

# 母集団のメンバー一覧（sh の cv_members と同じ）。pop の件数だけでは分子（タグ）を分母と同じ集合に絞れない。
# タグは subtask の review.md も含めて数える（subtask は親に属する。母集団は top-level だけ）
function Cv-Members($id, $fmt) {
  $f = CvFind $id
  if (-not $f) { Die "条項がありません: $id" }
  $sid = CvId $id
  $in = CvGet $f 'introduced'
  if (-not $in) { Die "introduced が無い条項です: $sid" }
  $b = CvTsKey $in
  if (-not $b) { Die "introduced が不正です: $in" }
  $worksRoot = Join-Path $script:AIDEV 'works'
  $rows=@(); $n=0; $tsum=0
  if (IsDir $worksRoot) {
    foreach ($d in (Get-ChildItem -LiteralPath $worksRoot -Directory | Sort-Object Name)) {
      $pf = Join-Path $d.FullName 'metrics.yml'
      if (-not (IsFile $pf)) { continue }
      if (@(YList (Join-Path $d.FullName 'state.yml') 'approved') -cnotcontains 'deliver') { continue }
      $lines = [System.IO.File]::ReadAllLines($pf)
      $pts = CvFirstTs $lines
      if (-not $pts) { continue }
      $a = CvTsKey $pts
      if (-not $a) { continue }
      if ([int64]$a -lt [int64]$b) { continue }
      $dts = '-'
      foreach ($l in $lines) {
        if ($l.Contains('phase: deliver, event: approved') -and $l -match '^[^{]*\{\s*ts:\s*([0-9][0-9:TZ.-]*)') { $dts = $Matches[1] }
      }
      $tg = 0
      $needle = "[conv:$sid]"
      foreach ($rv in @(Get-ChildItem -LiteralPath $d.FullName -Recurse -File -Filter review.md -ErrorAction SilentlyContinue)) {
        $txt = [System.IO.File]::ReadAllText($rv.FullName)
        $ix = 0
        while (($ix = $txt.IndexOf($needle, $ix, [StringComparison]::Ordinal)) -ge 0) { $tg++; $ix += $needle.Length }
      }
      $n++; $tsum += $tg
      $rows += "$($d.Name)`t$pts`t$dts`t$tg"
    }
  }
  if ($fmt -ceq 'tsv') {
    foreach ($r in $rows) { Write-Output "member`t$r" }
  } else {
    $all = @("work`tstarted`tdelivered`tconv_tags") + $rows
    foreach ($l in (Fmt-Table $all)) { Write-Output $l }
  }
  Write-Output "members-summary: id=$sid pop=$n conv_tags=$tsum"
}

function Cv-Status($rest) {
  $fmt='table'; $members=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch -CaseSensitive ($rest[$i]) {
      '--format'  { $i++; $fmt=(ArgAt $rest $i '--format') }
      '--members' { $i++; $members=(ArgAt $rest $i '--members') }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        Die "余分な引数: $($rest[$i])"
      }
    }
  }
  if ($fmt -cne 'table' -and $fmt -cne 'tsv') { Die "--format は table|tsv" }
  $d = CvDir
  if (-not (IsDir $d)) { Die "条項ディレクトリがありません: $d（aidev convention new で起こす）" }
  if ($members) { Cv-Members $members $fmt; return }
  $files = @()
  $files += (Get-ChildItem -LiteralPath $d -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)
  $arc = Join-Path $d 'archive'
  if (IsDir $arc) { $files += (Get-ChildItem -LiteralPath $arc -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name) }
  $idxf = CvIndexFile
  $idxb = if ($idxf) { CvIndexBlock $idxf } else { '' }
  $rel = CvDirRel
  $arcPath = Join-Path $d 'archive'
  $rows=@(); $npend=0; $nready=0; $nconf=0; $nidx=0
  foreach ($fi in $files) {
    $id = [System.IO.Path]::GetFileNameWithoutExtension($fi.Name)
    $st = CvGet $fi.FullName 'status'; if (-not $st) { $st='-' }
    $intro = CvGet $fi.FullName 'introduced'; if (-not $intro) { $intro='-' }
    $va = CvGet $fi.FullName 'verify_after'; if ($va -notmatch '^\d+$') { $va='0' }
    $pt = CvGet $fi.FullName 'promoted_to'; if (-not $pt) { $pt='-' }
    # archive 済みの pop は意味を持たない（判定は済んでいる）ので計算も表示もしない（sh 版と同一）
    $isArcRow = $fi.DirectoryName -eq $arcPath
    $pop = if ($isArcRow) { '-' } elseif ($intro -ceq '-') { 0 } else { CvPop $intro }
    $ready='-'
    if ($st -ceq 'pending') {
      $npend++
      if ($pop -cne '-' -and [int]$va -gt 0 -and [int]$pop -ge [int]$va) { $ready='yes'; $nready++ } else { $ready='no' }
    }
    if ($st -ceq 'confirmed') { $nconf++ }
    # index 列: active な条項が索引に載っているか。載っていない＝自動読込されない＝読まれない。
    # 読まれていないだけの条項を「効かなかった」と判定しないための可視化。
    $idx = '-'
    $isArc = $fi.DirectoryName -eq $arcPath   # パス比較は OS の流儀に従う
    if ((-not $isArc) -and ($st -ceq 'pending' -or $st -ceq 'confirmed')) {
      if ($idxf -and $idxb.Contains("$rel/$($fi.Name)")) { $idx = 'yes' } else { $idx = 'no'; $nidx++ }
    }
    $rows += "$id`t$st`t$intro`t$pop`t$va`t$ready`t$idx`t$pt"
  }
  if ($fmt -ceq 'tsv') {
    foreach ($r in $rows) { Write-Output "convention`t$r" }
  } else {
    $all = @("id`tstatus`tintroduced`tpop`tneed`tready`tindex`tpromoted_to") + $rows
    foreach ($l in (Fmt-Table $all)) { Write-Output $l }
  }
  Write-Output "convention-summary: pending=$npend ready=$nready confirmed(未移送)=$nconf 索引漏れ=$nidx"
}

# 条項ファイルの一生を見る（backlog と同じく持ち主の work がいないので verify では硬ゲートにできない）。
function Doctor-Conventions() {
  $d = CvDir
  if (-not (IsDir $d)) { return }
  $items=@()
  foreach ($f in (Get-ChildItem -LiteralPath $d -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)) {
    $items += ,@($f.FullName, $f.Name, $false)
  }
  $arc = Join-Path $d 'archive'
  if (IsDir $arc) {
    foreach ($f in (Get-ChildItem -LiteralPath $arc -File -Filter *.md -ErrorAction SilentlyContinue | Sort-Object Name)) {
      $items += ,@($f.FullName, "archive/$($f.Name)", $true)
    }
  }
  # 索引はファイル単位で1回だけ読む（条項ごとに読み直さない）
  $idxf = CvIndexFile
  $idxb = if ($idxf) { CvIndexBlock $idxf } else { '' }
  $idxl = if ($idxf) { Split-Path -Leaf $idxf } else { '-' }
  $rel = CvDirRel
  $cfiles=0; $carch=0; $cwarn=0; $out=@()
  foreach ($it in $items) {
    $path=$it[0]; $label=$it[1]; $isArc=$it[2]
    if ($isArc) { $carch++ } else { $cfiles++ }
    $st = CvGet $path 'status'
    $intro = CvGet $path 'introduced'
    $va = CvGet $path 'verify_after'
    $inidx = $false
    if ($idxf -and $idxb.Contains("$rel/$(Split-Path -Leaf $path)")) { $inidx = $true }
    $w=@()
    # switch は条件が $null のとき default ごと素通りする。status 欠落を**必ず**拾いたい検査なので
    # if/elseif で書く（sh 版の case と分岐を一致させる）。
    if (-not $st) {
      $w += "    WARN frontmatter(status)が無い: 検証の進み方が決まらない（pending/confirmed/promoted/ineffective/superseded）"
    } elseif ($st -ceq 'pending') {
      if ($isArc) {
        $w += "    WARN 退避済みだが status=pending: 判定前に退避されている"
      } else {
        if ($va -notmatch '^\d+$') { $va='0' }
        if ($intro -and [int]$va -gt 0) {
          $pop = CvPop $intro
          # 索引に無い条項は読まれていないので判定させない（sh 版と同一。索引漏れ自体は下で WARN）
          if ([int]$pop -ge [int]$va -and $inidx) {
            $w += "    WARN 母集団が揃った($pop/$va)のに未判定: insights で効果を判定すること"
          } elseif ([int]$pop -ge [int]$va) {
            $w += "    note 母集団は揃った($pop/$va)が索引に無いので判定しない: 索引に足してから aidev convention defer で必要件数を積み増し、読まれた work で数え直す"
          }
        }
      }
    } elseif ($st -ceq 'confirmed') {
      # 効果が確認された条項が docs/aidev に居座ると PJ ドキュメントと二重管理になる
      if (-not $isArc) { $w += "    WARN confirmed だが未移送: PJ ドキュメントへ移して promote すること" }
    } elseif ($st -ceq 'promoted') {
      if (-not (CvGet $path 'promoted_to')) { $w += "    WARN promoted だが promoted_to が無い: 本文の行き先が辿れない" }
      if (-not $isArc) { $w += "    WARN promoted だが未退避: active に残ると重複提案の検査対象からずれる" }
    } elseif ($st -ceq 'ineffective' -or $st -ceq 'superseded') {
      if (-not $isArc) { $w += "    WARN $st だが未退避: archive/ へ移すこと" }
    } else {
      $w += "    WARN 未知の status: $st（pending/confirmed/promoted/ineffective/superseded）"
    }
    # 本文が未記入（起票テンプレのコメントが残ったまま）の active な条項。索引に載っても中身が無ければ効かない
    if ((-not $isArc) -and ($st -ceq 'pending' -or $st -ceq 'confirmed')) {
      if (([System.IO.File]::ReadAllText($path)).Contains('<!-- 何を守るか。')) {
        $w += "    WARN 本文が未記入（起票テンプレのまま）: ## 規約 を書くこと。索引に載っても中身が無ければ効かない"
      }
    }
    # 索引の突き合わせ（active な条項＝読まれる必要があるもの、と移送済みの張り替え漏れ）
    $link = "$rel/$(Split-Path -Leaf $path)"
    if ((-not $isArc) -and ($st -ceq 'pending' -or $st -ceq 'confirmed')) {
      if (-not $idxf) {
        $w += "    WARN 索引ファイルが無い: 条項が自動読込されず、読まれないまま「効かなかった」と誤判定される"
      } elseif (-not $idxb.Contains($link)) {
        $w += "    WARN 索引に無い（$idxl）: 自動読込されないので読まれない。ブロック内に足すこと"
        $w += "         例: - <いつ参照するか> → $link"
      }
    } elseif ($st -ceq 'promoted') {
      $pt = CvGet $path 'promoted_to'
      if ($idxf -and $pt -and $idxb.Contains($link)) {
        $w += "    WARN 索引が移送前を指したまま（$idxl）: $link → $pt に張り替えること"
      }
    } elseif ($st -ceq 'ineffective' -or $st -ceq 'superseded') {
      # 退役した条項の行が索引に残ると、存在しないファイルを指し続ける（promote の張り替え漏れと同型）
      if ($isArc -and $idxf -and $idxb.Contains($link)) {
        $w += "    WARN 索引が退役済み条項を指したまま（$idxl）: $link の行を消すこと"
      }
    }
    if ($w.Count -gt 0) {
      $cwarn++
      $shown = if ($st) { $st } else { '-' }
      $out += "- $label (status=$shown)"
      $out += $w
    }
  }
  Write-Output "convention: 条項ファイル横断検査"
  foreach ($l in $out) { Write-Output $l }
  Write-Output "convention-summary: files=$cfiles archived=$carch warn=$cwarn"
}

function Cmd-Worktree($rest) {
  if ($rest.Count -lt 1) { Die "使用法: aidev worktree <add|list|rm> ..." }
  $sub=$rest[0]; $sr=@(); if ($rest.Count -gt 1) { $sr=$rest[1..($rest.Count-1)] }
  switch -CaseSensitive ($sub) {
    'add'  { Wt-Add $sr }
    'list' { Wt-List $sr }
    'rm'   { Wt-Rm $sr }
    default { Die "未知の worktree サブコマンド: $sub（add|list|rm）" }
  }
}

function Usage() {
  # 先頭(2行目以降)の連続するコメント行のみを出力（コメント末尾で停止。範囲ズレに強い）
  foreach ($l in (Get-Content $PSCommandPath | Select-Object -Skip 1)) {
    if ($l -match '^#') { $l -replace '^#\s?','' } else { break }
  }
}

if ($args.Count -lt 1) { Usage; exit 1 }
$cmd = $args[0]
$rest = @(); if ($args.Count -gt 1) { $rest = $args[1..($args.Count-1)] }
switch -CaseSensitive ($cmd) {
  'new'     { Cmd-New $rest }
  'event'   { Cmd-Event $rest }
  'approve' { Cmd-Approve $rest }
  'unapprove' { Cmd-Unapprove $rest }
  'guard'   { Cmd-Guard $rest }
  'verify'  { Cmd-Verify $rest }
  'escalate' { Cmd-Escalate $rest }
  'doctor'  { Cmd-Doctor $rest }
  'harness' { Cmd-Harness $rest }
  'status'  { Cmd-Status $rest }
  'metrics' { Cmd-Metrics $rest }
  'use'     { Cmd-Use $rest }
  'backlog' { Cmd-Backlog $rest }
  'convention' { Cmd-Convention $rest }
  'worktree' { Cmd-Worktree $rest }
  'help'    { Usage }
  '-h'      { Usage }
  '--help'  { Usage }
  default   { Die "未知のコマンド: $cmd（aidev help）" }
}
