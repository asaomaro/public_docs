#!/usr/bin/env pwsh
# aidev ランタイムガード CLI（PowerShell 版・Windows 向け / pwsh でも動作）
#
# POSIX sh 版（同ディレクトリの `aidev`）と挙動・出力・終了コードを一致させること。
# 役割と正典は `aidev` 冒頭コメント／protocol.md「4.1」を参照。
#
# 使い方:
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 new <slug> [--mode interactive|autonomous] [--ticket ID] [--depends a,b,#N] [--parent <親work>]
#     --parent 指定時は親 work 配下に subtask（<NN>-<subslug>・date prefix なし・current=plan）を作る
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 event <phase> <start|approved|sent_back> [key=value ...]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 approve <phase> [key=value ...]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 guard <phase>
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 verify [slug]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 doctor
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 status [--format table|tsv]
#   pwsh .claude/skills/aidev-docs/bin/aidev.ps1 metrics [slug] [--all] [--phases] [--format table|tsv]
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

$script:CURRENT_SCHEMA = 3   # schema 3=subtask 層(subtasks/activeSubtask/parent)導入。schema<=2 は legacy 免除
$script:PHASES = @('requirement','research','spec','design','plan','coding','test','review','walkthrough','deliver','retro')
$script:Utf8 = New-Object System.Text.UTF8Encoding($false)  # BOM なし

function Die($m)  { [Console]::Error.WriteLine("aidev: $m"); exit 1 }
function Warn($m) { [Console]::Error.WriteLine("aidev: $m") }
function Now() {
  # 明示フォーマット（カルチャ/書式指定子の曖昧さを避け sh 版と完全一致させる）
  $d = [DateTime]::UtcNow
  return ('{0:D4}-{1:D2}-{2:D2}T{3:D2}:{4:D2}:{5:D2}Z' -f $d.Year,$d.Month,$d.Day,$d.Hour,$d.Minute,$d.Second)
}
function WriteText($p,$t)  { [System.IO.File]::WriteAllText($p,$t,$script:Utf8) }
function AppendText($p,$t) { [System.IO.File]::AppendAllText($p,$t,$script:Utf8) }

function FindRoot() {
  $d = (Get-Location).Path
  while ($true) {
    if (Test-Path (Join-Path $d '.aidev')) { return $d }
    $parent = Split-Path $d -Parent
    if ([string]::IsNullOrEmpty($parent) -or $parent -eq $d) { break }
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
    if (-not (Test-Path $cur)) { Die "対象作業が不明です（.aidev/current 無し）。new か slug 指定を。" }
    $slug = ([System.IO.File]::ReadAllLines($cur))[0].Trim()
  }
  $script:WORK = Join-Path (Join-Path $script:AIDEV 'works') $slug
  if (-not (Test-Path $script:WORK)) { Die "work が存在しません: $slug" }
  $script:SLUG = $slug
}

# state.yml の key 行を差し替え、無ければ末尾に追記（subtasks/activeSubtask の冪等更新用）。
function SetOrAppend($file,$key,$newline) {
  $content = [System.IO.File]::ReadAllText($file)
  if ($content -match ("(?m)^" + [regex]::Escape($key) + ":")) { ReplaceLine $file $key $newline }
  else { AppendText $file ($newline + "`n") }
}

function IsPhase($p) { return $script:PHASES -contains $p }

# scalar 読み取り（前後空白と囲み二重引用符を除去）。inline コメント(#)は除去しない
# （ticket/dependsOn は '#18' 等 '#' 始まりの値を持つため）。sh の yget と一致。
function YGet($file,$key) {
  if (-not (Test-Path $file)) { return '' }
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
  return @($v -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
}

function ApprovedHas($work,$phase) { return (YList (Join-Path $work 'state.yml') 'approved') -contains $phase }

function ReplaceLine($file,$key,$newline) {
  $lines = [System.IO.File]::ReadAllLines($file)
  $out = foreach ($l in $lines) { if ($l -match ("^" + [regex]::Escape($key) + ":")) { $newline } else { $l } }
  WriteText $file (($out -join "`n") + "`n")
}

function EnsureEvents($work) {
  $f = Join-Path $work 'metrics.yml'
  if (-not (Test-Path $f)) { WriteText $f "events:`n"; return }
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
function Cmd-New($rest) {
  $slug=''; $mode=''; $ticket=''; $depends=''; $parent=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch ($rest[$i]) {
      '--mode'    { $mode=$rest[++$i] }
      '--ticket'  { $ticket=$rest[++$i] }
      '--depends' { $depends=$rest[++$i] }
      '--parent'  { $parent=$rest[++$i] }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        if ($slug) { Die "slug は1つだけ" } else { $slug=$rest[$i] }
      }
    }
  }
  if (-not $slug) { Die "使用法: aidev new <slug> [--mode ..] [--ticket ..] [--depends ..] [--parent <親work>]" }

  $depsYaml='[]'
  if ($depends) {
    $parts = @($depends -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    $depsYaml = '[' + ([string]::Join(', ',$parts)) + ']'
  }
  $worksRoot = Join-Path $script:AIDEV 'works'

  if ($parent) {
    # --- subtask 生成: 親 work 配下に <slug>(=NN-subslug) で作る（date prefix なし）。current は plan 開始 ---
    $pdir = Join-Path $worksRoot $parent
    if (-not (Test-Path $pdir)) { Die "親 work が存在しません: $parent" }
    $pst = Join-Path $pdir 'state.yml'
    if (-not (Test-Path $pst)) { Die "親 state.yml がありません: $parent" }
    # C: 多段ネスト禁止（単層のみ）。親が既に subtask なら拒否（doctor 横断・依存解決・activeSubtask は1段前提）
    if (YGet $pst 'parent') { Die "親が既に subtask です。多段ネストは不可（subtask は単層のみ）: $parent" }
    if ($slug -match '/') { Die "subtask slug にスラッシュは使えません: $slug" }
    $name = "$parent/$slug"
    $work = Join-Path $pdir $slug
    if (Test-Path $work) { Die "subtask が既に存在します: $name" }
    if (-not $mode) { $mode = YGet $pst 'mode' }
    if (-not $mode) { $mode = 'interactive' }
    if ($mode -ne 'interactive' -and $mode -ne 'autonomous') { Die "mode は interactive|autonomous" }
    New-Item -ItemType Directory -Path $work -Force | Out-Null

    $sb = "schema: $($script:CURRENT_SCHEMA)`nslug: $slug`nparent: $parent`n"
    if ($ticket) { $sb += "ticket: $ticket`n" }
    $sb += "current: plan`napproved: []`nmode: $mode`nhumanGates: []`nmaxSendBacks: 3`ndependsOn: $depsYaml`n"
    WriteText (Join-Path $work 'state.yml') $sb
    WriteText (Join-Path $work 'metrics.yml') "events:`n"

    # 親 subtasks に追記（重複排除）し、activeSubtask 未設定なら本 subtask を活性に
    $cur = @(YList $pst 'subtasks')
    if ($cur -notcontains $slug) { $cur = @($cur + $slug) }
    SetOrAppend $pst 'subtasks' ("subtasks: [" + ([string]::Join(', ', $cur)) + "]")
    $act = YGet $pst 'activeSubtask'
    if (-not $act -or $act -eq 'done') { SetOrAppend $pst 'activeSubtask' "activeSubtask: $slug" }

    WriteText (Join-Path $script:AIDEV 'current') "$name`n"
    Write-Output "created subtask: $work (parent $parent, schema $($script:CURRENT_SCHEMA), mode $mode)"
    return
  }

  # --- 通常(top-level) work ---
  if (-not $mode) { $mode = 'interactive' }
  if ($mode -ne 'interactive' -and $mode -ne 'autonomous') { Die "mode は interactive|autonomous" }

  $dateP = [DateTime]::UtcNow.ToString('yyyyMMdd')
  $base = "$dateP-$slug"; $name=$base; $n=2
  while (Test-Path (Join-Path $worksRoot $name)) { $name="$base-$n"; $n++ }
  $work = Join-Path $worksRoot $name
  New-Item -ItemType Directory -Path $work -Force | Out-Null

  $sb = "schema: $($script:CURRENT_SCHEMA)`nslug: $slug`n"
  if ($ticket) { $sb += "ticket: $ticket`n" }
  $sb += "current: requirement`napproved: []`nmode: $mode`nhumanGates: []`nmaxSendBacks: 3`ndependsOn: $depsYaml`n"
  WriteText (Join-Path $work 'state.yml') $sb
  WriteText (Join-Path $work 'metrics.yml') "events:`n"
  WriteText (Join-Path $script:AIDEV 'current') "$name`n"
  Write-Output "created: $work (schema $($script:CURRENT_SCHEMA), mode $mode)"
}

# --- event -------------------------------------------------------------------
function Cmd-Event($rest) {
  if ($rest.Count -lt 2) { Die "使用法: aidev event <phase> <start|approved|sent_back> [k=v ...]" }
  $ph=$rest[0]; $ev=$rest[1]; $kvs=@(); if ($rest.Count -gt 2) { $kvs=$rest[2..($rest.Count-1)] }
  if (-not (IsPhase $ph)) { Die "未知の phase: $ph" }
  if ('start','approved','sent_back' -notcontains $ev) { Die "event は start|approved|sent_back" }
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
  if (-not (Test-Path $st)) { Die "state.yml がありません: $($script:SLUG)" }

  if (-not (ApprovedHas $script:WORK $ph)) {
    $cur = YList $st 'approved'
    if ($cur.Count -eq 0) { $newl = "[$ph]" }
    else { $newl = '[' + ([string]::Join(', ', ($cur + $ph))) + ']' }
    ReplaceLine $st 'approved' "approved: $newl"
  }
  ReplaceLine $st 'current' "current: $ph"
  AppendEvent $script:WORK $ph 'approved' $kvs
  Write-Output "approved: $ph @ $($script:SLUG)"

  # D: subtask の review 承認でカーソルを前進させる（散文の手動カーソル操作を排除）。
  # 親 subtasks を順に見て review 未承認の最初の子を次の active にする。無ければ done（→親の統合 test へ）。
  if ($ph -eq 'review') {
    $par = YGet $st 'parent'
    $worksRoot = Join-Path $script:AIDEV 'works'
    if ($par -and (Test-Path (Join-Path $worksRoot $par))) {
      $pst2 = Join-Path (Join-Path $worksRoot $par) 'state.yml'
      $nextsub = ''
      foreach ($s in (YList $pst2 'subtasks')) {
        $subSt = Join-Path (Join-Path (Join-Path $worksRoot $par) $s) 'state.yml'
        if ((YList $subSt 'approved') -notcontains 'review') { $nextsub = $s; break }
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
  foreach ($d in (YList (Join-Path $workDir 'state.yml') 'dependsOn')) {
    if (-not $d) { continue }
    if ($d.StartsWith('#')) { $script:EvalAdvisory += $d; continue }
    $depWork = Join-Path $worksRoot $d
    if (-not (Test-Path $depWork) -and $par -and (Test-Path (Join-Path (Join-Path $worksRoot $par) $d))) {
      $depWork = Join-Path (Join-Path $worksRoot $par) $d
    }
    if (Test-Path $depWork) {
      $da = YList (Join-Path $depWork 'state.yml') 'approved'
      # 完了判定: subtask(=parent あり)は review 承認、top-level work は deliver 承認
      if (YGet (Join-Path $depWork 'state.yml') 'parent') {
        if ($da -notcontains 'review') { $script:EvalUnmet += "$d(未review)" }
      } else {
        if ($da -notcontains 'deliver') { $script:EvalUnmet += "$d(未deliver)" }
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
  if ($par) { $pd = Join-Path (Join-Path $script:AIDEV 'works') $par; if (Test-Path $pd) { $script:PARENT_DIR=$pd } }
  # B: 親専用工程は subtask で実行不可（subtask の工程は plan/coding/test/review のみ）
  if ($par -and ('requirement','research','spec','design','walkthrough','deliver','retro' -contains $ph)) {
    [Console]::Error.WriteLine("NG $ph は親 work 専用です（subtask では実行不可。subtask の工程は plan/coding/test/review）: $($script:SLUG)")
    exit 2
  }
  function needFile($f) {
    if (Test-Path (Join-Path $script:WORK $f)) { return }
    # 上流成果物(requirement/spec/design)のみ親から継承。plan.md/tasks.md は subtask 固有なので継承しない。
    if ($script:PARENT_DIR -and ('requirement.md','spec.md','design.md' -contains $f) -and (Test-Path (Join-Path $script:PARENT_DIR $f))) { return }
    $script:miss += $f
  }
  function needApproved($p) { if (-not (ApprovedHas $script:WORK $p)) { $script:unapp += $p } }
  $script:miss=@(); $script:unapp=@()
  switch ($ph) {
    'requirement' { }
    'research'    { needFile 'requirement.md' }
    'spec'        { needFile 'requirement.md' }
    'design'      { needFile 'spec.md' }
    'plan'        { needFile 'spec.md' }
    'coding'      { needFile 'plan.md'; needFile 'tasks.md' }
    'test'        { needFile 'tasks.md' }
    'review'      { needFile 'spec.md' }
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
  if ($rc -eq 0) { Write-Output "OK guard $ph @ $($script:SLUG)" }
  exit $rc
}

# --- verify ------------------------------------------------------------------
function VerifyWork($work) {
  # 注意: 状態行は [Console]::Out へ直接出す（戻り値=intだけにし、$rc=VerifyWork が出力を取り込む PS の罠を回避）
  $st = Join-Path $work 'state.yml'
  if (-not (Test-Path $st)) { [Console]::Out.WriteLine("  FAIL state.yml なし"); return 4 }
  $vf=@()
  foreach ($k in 'slug','current','approved') {
    $found=$false
    foreach ($l in [System.IO.File]::ReadAllLines($st)) { if ($l -match ("^"+$k+":")) { $found=$true; break } }
    if (-not $found) { $vf += "state.yml:${k}欠落" }
  }
  $schema = YGet $st 'schema'
  if ([string]::IsNullOrEmpty($schema)) {
    [Console]::Out.WriteLine("  SKIP legacy (schema 未記載・metrics導入前の作業として免除)")
  } else {
    $sn = 0; [void][int]::TryParse($schema, [ref]$sn)
    if ($sn -ge 2) {
      if (-not (Test-Path (Join-Path $work 'metrics.yml'))) { $vf += "metrics.yml欠落" }
      if (ApprovedHas $work 'review') { if (-not (Test-Path (Join-Path $work 'review.md'))) { $vf += "review.md欠落(review承認済)" } }
      if (ApprovedHas $work 'deliver') {
        $mf = Join-Path $work 'metrics.yml'; $ok=$false
        if (Test-Path $mf) { foreach ($l in [System.IO.File]::ReadAllLines($mf)) { if ($l -match 'phase:\s*deliver' -and $l -match 'event:\s*approved') { $ok=$true; break } } }
        if (-not $ok) { $vf += "deliver承認イベントがmetricsに無い" }
      }
    }
  }
  if ($vf.Count -gt 0) { [Console]::Out.WriteLine("  FAIL " + ($vf -join ' ')); return 4 }
  [Console]::Out.WriteLine("  OK"); return 0
}

function Cmd-Verify($rest) {
  $slug=''; if ($rest.Count -ge 1) { $slug=$rest[0] }
  ResolveWork $slug
  Write-Output "verify: $($script:SLUG)"
  $rc = VerifyWork $script:WORK
  exit $rc
}

# --- doctor ------------------------------------------------------------------
function Cmd-Doctor() {
  $worksDir = Join-Path $script:AIDEV 'works'
  if (-not (Test-Path $worksDir)) { Die "works がありません" }
  $total=0; $fail=0; $legacy=0
  Write-Output "doctor: 全 work 横断検査"
  foreach ($d in (Get-ChildItem -Path $worksDir -Directory | Sort-Object Name)) {
    $total++
    Write-Output ("- " + $d.Name)
    $sc = YGet (Join-Path $d.FullName 'state.yml') 'schema'
    if ([string]::IsNullOrEmpty($sc)) { $legacy++ }
    if ((VerifyWork $d.FullName) -ne 0) { $fail++ }
    # subtask（ネスト1段）も横断検査する
    foreach ($sd in (Get-ChildItem -Path $d.FullName -Directory | Sort-Object Name)) {
      if (-not (Test-Path (Join-Path $sd.FullName 'state.yml'))) { continue }
      $total++
      Write-Output ("  - " + $d.Name + "/" + $sd.Name)
      $ssc = YGet (Join-Path $sd.FullName 'state.yml') 'schema'
      if ([string]::IsNullOrEmpty($ssc)) { $legacy++ }
      if ((VerifyWork $sd.FullName) -ne 0) { $fail++ }
    }
  }
  Write-Output "summary: works=$total fail=$fail legacy(免除)=$legacy"
  if ($fail -eq 0) { exit 0 } else { exit 1 }
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
    if ((YList (Join-Path (Join-Path $workDir $s) 'state.yml') 'approved') -contains 'review') { $n++ }
  }
  return "$n $m"
}

function Cmd-Status($rest) {
  $fmt='table'; $subflag=$false
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch ($rest[$i]) {
      '--format'   { $fmt=$rest[++$i] }
      '--subtasks' { $subflag=$true }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        else { Die "status は位置引数を取りません: $($rest[$i])" }
      }
    }
  }
  if ($fmt -ne 'table' -and $fmt -ne 'tsv') { Die "--format は table|tsv" }

  $worksDir = Join-Path $script:AIDEV 'works'
  $wrows=@(); $wn=0   # 各要素は型タグ付き: "W`t…7列…" / "S`t親`t子`tcurrent`tdone"
  if (Test-Path $worksDir) {
    foreach ($d in (Get-ChildItem -Path $worksDir -Directory | Sort-Object Name)) {
      $st = Join-Path $d.FullName 'state.yml'
      if (-not (Test-Path $st)) { continue }
      $ticket = YGet $st 'ticket';  if (-not $ticket)  { $ticket='-' }
      $mode = YGet $st 'mode';      if (-not $mode)    { $mode='-' }
      $current = YGet $st 'current';if (-not $current) { $current='-' }
      $appr = YList $st 'approved'
      $wdone = if ($appr -contains 'deliver') { 'yes' } else { 'no' }
      $next='-'
      if ($wdone -eq 'no') { foreach ($p in $script:STD_PIPELINE) { if ($appr -notcontains $p) { $next=$p; break } } }
      # subtask を持つ親は next を subtask 進捗に差し替える（未完=sub N/M、全完了=統合工程の次）
      $sp = SubtaskProgress $d.FullName
      if ($sp -and $wdone -eq 'no') {
        $spp = $sp -split ' '; $spn=[int]$spp[0]; $spm=[int]$spp[1]
        if ($spn -lt $spm) { $next = "sub $spn/$spm" }
        else { $next='-'; foreach ($p in @('test','review','deliver')) { if ($appr -notcontains $p) { $next=$p; break } } }
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
          $cdone = if ((YList $cst 'approved') -contains 'review') { 'yes' } else { 'no' }
          $wrows += ("S`t" + $d.Name + "`t" + $cs + "`t" + $ccur + "`t" + $cdone)
        }
      }
    }
  }

  $backlogDir = Join-Path $script:AIDEV 'backlog'
  $brows=@(); $bf=0; $bn=0
  if (Test-Path $backlogDir) {
    foreach ($f in (Get-ChildItem -Path $backlogDir -File -Filter *.md | Sort-Object Name)) {
      $todo=0; $needs=0
      foreach ($l in [System.IO.File]::ReadAllLines($f.FullName)) {
        if ($l -match '^\s*- \[ \]') { $todo++; if ($l -match '\(needs:') { $needs++ } }
      }
      $bf++; $bn += $todo
      $brows += ($f.Name + "`t" + $todo + "`t" + $needs)
    }
  }

  if ($fmt -eq 'tsv') {
    foreach ($r in $wrows) {
      $c = $r -split "`t"
      if ($c[0] -eq 'W') { Write-Output ("work`t" + ($c[1..7] -join "`t")) }
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
      if ($c[0] -eq 'W') { $disp += ($c[1..7] -join "`t") }
      else { $disp += ("  ↳ " + $c[2] + "`t-`t-`t" + $c[3] + "`t-`t" + $c[4] + "`t-") }
    }
    foreach ($l in (Fmt-Table $disp)) { Write-Output $l }
  }
  Write-Output ""
  Write-Output "BACKLOG (未着手 $bn 件)"
  if ($bf -gt 0) { foreach ($l in (Fmt-Table (@("file`ttodo`tneeds") + $brows))) { Write-Output $l } }
}

# --- metrics（読み取り専用・metrics.yml から派生指標を集計） ----------------------
function Mt-Epoch($ts) {
  $t = ($ts -replace 'Z$','') -replace 'UTC$',''
  if ($t.Length -lt 19 -or $t.Substring(10,1) -ne 'T') { return -1 }
  try {
    $dt = [DateTime]::ParseExact($t.Substring(0,19), 'yyyy-MM-ddTHH:mm:ss', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None)
    return [int64]([DateTimeOffset]::new($dt, [TimeSpan]::Zero).ToUnixTimeSeconds())
  } catch { return -1 }
}

function Cmd-Metrics($rest) {
  $fmt='table'; $allf=$false; $phasesf=$false; $mslug=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch ($rest[$i]) {
      '--all'     { $allf=$true }
      '--phases'  { $phasesf=$true }
      '--format'  { $fmt=$rest[++$i] }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        elseif ($mslug) { Die "slug は1つだけ" } else { $mslug=$rest[$i] }
      }
    }
  }
  if ($fmt -ne 'table' -and $fmt -ne 'tsv') { Die "--format は table|tsv" }

  $worksDir = Join-Path $script:AIDEV 'works'
  $dirs=@()
  if ($allf) {
    if (Test-Path $worksDir) { $dirs = @(Get-ChildItem -Path $worksDir -Directory | Sort-Object Name | ForEach-Object { $_.FullName }) }
  } elseif ($mslug) {
    $p = Join-Path $worksDir $mslug
    if (-not (Test-Path $p)) { Die "work が存在しません: $mslug" }
    $dirs=@($p)
  } else {
    $cur = Join-Path $script:AIDEV 'current'
    if (-not (Test-Path $cur)) { Die "対象作業が不明です（.aidev/current 無し）。slug 指定か --all を。" }
    $c = ([System.IO.File]::ReadAllLines($cur))[0].Trim()
    $p = Join-Path $worksDir $c
    if (-not (Test-Path $p)) { Die "work が存在しません: $c" }
    $dirs=@($p)
  }

  $rows=@()
  foreach ($wd in $dirs) {
    $name = Split-Path $wd -Leaf
    $mf = Join-Path $wd 'metrics.yml'
    $first=-1; $firstts='-'; $deliveredFlag=$false; $deliveredE=-1; $sback=0
    $scount=@{}; $laststart=@{}; $laststartTs=@{}; $appat=@{}; $appatTs=@{}
    if (Test-Path $mf) {
      foreach ($line in [System.IO.File]::ReadAllLines($mf)) {
        if ($line -notmatch 'event:') { continue }
        $ts=''; $ph=''; $ev=''
        if ($line -match 'ts:\s*([^,}]+)')      { $ts = $Matches[1].Trim() }
        if ($line -match 'phase:\s*([A-Za-z_]+)'){ $ph = $Matches[1] }
        if ($line -match 'event:\s*([A-Za-z_]+)'){ $ev = $Matches[1] }
        if (-not $ph -or -not $ev) { continue }
        $e = Mt-Epoch $ts
        if ($ev -eq 'start') {
          if ($scount.ContainsKey($ph)) { $scount[$ph]++ } else { $scount[$ph]=1 }
          if ($e -ge 0) {
            if ($first -lt 0 -or $e -lt $first) { $first=$e; $firstts=$ts }
            if (-not $laststart.ContainsKey($ph) -or $e -gt $laststart[$ph]) { $laststart[$ph]=$e; $laststartTs[$ph]=$ts }
          }
        } elseif ($ev -eq 'approved') {
          if ($e -ge 0) { $appat[$ph]=$e; $appatTs[$ph]=$ts }
          if ($ph -eq 'deliver') { $deliveredFlag=$true; if ($e -ge 0) { $deliveredE=$e } }
        } elseif ($ev -eq 'sent_back') { $sback++ }
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
      $rw=0; foreach ($k in $scount.Keys) { if ($scount[$k] -ge 2) { $rw++ } }
      $rows += ($name + "`t" + $fs + "`t" + $dv + "`t" + $lead + "`t" + $rw + "`t" + $sback)
    }
  }

  if ($phasesf) { $hdr = "work`tphase`tstart`tapproved`telapsed_sec" }
  else          { $hdr = "work`tfirst_start`tdelivered`tlead_sec`treworks`tsent_backs" }

  if ($fmt -eq 'tsv') { foreach ($r in $rows) { Write-Output $r } }
  else { foreach ($l in (Fmt-Table (@($hdr) + $rows))) { Write-Output $l } }
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
  if (-not (Test-Path $wd)) { return $res }
  foreach ($d in (Get-ChildItem -Path $wd -Directory | Sort-Object Name)) {
    $st = Join-Path $d.FullName 'state.yml'
    if (-not (Test-Path $st)) { continue }
    if ((YGet $st 'slug') -eq $slug) { $res += $d.Name }
  }
  return $res
}

# git worktree list --porcelain を "path<TAB>branch" 配列に整形（sh の wt_porcelain と一致）
function WtPorcelain() {
  $out=@(); $p=''; $b=''
  foreach ($line in (git worktree list --porcelain)) {
    if ($line -like 'worktree *') {
      if ($p -ne '') { $out += ($p + "`t" + ($(if ($b -eq '') { '-' } else { $b }))); $b='' }
      $p = $line.Substring(9)
    } elseif ($line -like 'branch *') {
      $b = $line.Substring(7) -replace '^refs/heads/',''
    } elseif ($line -like 'detached*') {
      $b = 'detached'
    }
  }
  if ($p -ne '') { $out += ($p + "`t" + ($(if ($b -eq '') { '-' } else { $b }))) }
  return $out
}

function Wt-Add($rest) {
  $slug=''; $branch=''; $base='HEAD'; $wpath=''; $mode='interactive'; $ticket=''; $depends=''
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch ($rest[$i]) {
      '--branch'  { $branch=$rest[++$i] }
      '--base'    { $base=$rest[++$i] }
      '--path'    { $wpath=$rest[++$i] }
      '--mode'    { $mode=$rest[++$i] }
      '--ticket'  { $ticket=$rest[++$i] }
      '--depends' { $depends=$rest[++$i] }
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
  if (Test-Path $wpath) { Die "path が既に存在します: $wpath" }

  # ブランチ存在で分岐（既存→checkout / 新規→-b で base から作成）。branch は必ず明示。実 exit code を判定。
  git show-ref --verify --quiet "refs/heads/$branch"
  if ($LASTEXITCODE -eq 0) {
    git worktree add "$wpath" "$branch"
    if ($LASTEXITCODE -ne 0) { Die "git worktree add に失敗（branch=$branch）" }
  } else {
    git worktree add -b "$branch" "$wpath" "$base"
    if ($LASTEXITCODE -ne 0) { Die "git worktree add に失敗（branch=$branch base=$base）" }
  }
  $wpath = (Resolve-Path $wpath).Path

  # worktree 内で work を確定（main tree の .aidev/current には触れない＝INV-1）
  # @() で配列強制（要素1個だと return がスカラー文字列にアンロールし $mw[0] が先頭1文字になるのを防ぐ）
  $mw = @(WorksMatchingSlug $wpath $slug)
  if ($mw.Count -gt 1) {
    Die "worktree 内に slug=$slug の work が複数あります。曖昧なため中断（手動で current 設定を）"
  } elseif ($mw.Count -eq 1) {
    WriteText (Join-Path (Join-Path $wpath '.aidev') 'current') ($mw[0] + "`n")
    $workNote = "既存 work をリンク: $($mw[0])（current 設定のみ）"
  } else {
    # add 内で new: worktree をカレントにして既存 new ロジックに委譲（単一検証経路の維持・DRY）
    $bin = Join-Path (Join-Path (Join-Path $wpath '.aidev') 'bin') 'aidev.ps1'
    $argv = @('new', $slug, '--mode', $mode)
    if ($ticket)  { $argv += @('--ticket', $ticket) }
    if ($depends) { $argv += @('--depends', $depends) }
    Push-Location $wpath
    try { & pwsh $bin @argv; if ($LASTEXITCODE -ne 0) { Die "worktree 内の new に失敗" } }
    finally { Pop-Location }
    $workNote = "新規 work を作成（add 内で new）"
  }

  Write-Output "worktree 追加: $wpath"
  Write-Output "  branch: $branch / base: $base"
  Write-Output "  work:   $workNote"
  Write-Output "⚠ この work が package.json(contributes) / src/fileScope.ts / 言語登録に触るなら、"
  Write-Output "  他 worktree と languageId 波及・マージ衝突が起きうる（AGENTS.md「languageId 下流波及」）。並行可否はユーザー判断。"
  Write-Output "⚠ CL/RPG プロンプター定義など原典照合が要る work は主エージェント実施が必須（委譲して検証を落とさない）。"
  Write-Output "次: cd $wpath して各工程 skill を実行。"
}

function Wt-List($rest) {
  $fmt='table'
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch ($rest[$i]) {
      '--format' { $fmt=$rest[++$i] }
      default {
        if ($rest[$i].StartsWith('-')) { Die "未知のオプション: $($rest[$i])" }
        else { Die "list は位置引数を取りません: $($rest[$i])" }
      }
    }
  }
  if ($fmt -ne 'table' -and $fmt -ne 'tsv') { Die "--format は table|tsv" }
  GitPresent

  $rows=@()
  foreach ($line in (WtPorcelain)) {
    $cols = $line -split "`t"; $path = $cols[0]; $branch = $cols[1]
    # 判定キー: worktree ローカル .aidev/current の有無（branch 名ではない）
    $cur = Join-Path (Join-Path $path '.aidev') 'current'
    if (-not (Test-Path $cur)) { continue }
    $lines = [System.IO.File]::ReadAllLines($cur)
    $work = if ($lines.Count -ge 1) { $lines[0].Trim() } else { '' }
    if (-not $work) { $work = '-' }
    $phase = '-'
    $st = Join-Path (Join-Path (Join-Path (Join-Path $path '.aidev') 'works') $work) 'state.yml'
    if ($work -ne '-' -and (Test-Path $st)) { $phase = YGet $st 'current'; if (-not $phase) { $phase='-' } }
    $rows += ($path + "`t" + $branch + "`t" + $work + "`t" + $phase)
  }

  if ($fmt -eq 'tsv') {
    foreach ($r in $rows) { Write-Output ("worktree`t" + $r) }
    return
  }
  Write-Output ("WORKTREES (" + $rows.Count + ")")
  if ($rows.Count -gt 0) { foreach ($l in (Fmt-Table (@("path`tbranch`twork`tphase") + $rows))) { Write-Output $l } }
}

function Wt-Rm($rest) {
  $target=''; $force=$false; $delbranch=$false
  for ($i=0; $i -lt $rest.Count; $i++) {
    switch ($rest[$i]) {
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
  if (Test-Path -PathType Container $target) { $abst = (Resolve-Path $target).Path }
  $wts = @(WtPorcelain)
  $mainWt = if ($wts.Count -ge 1) { ($wts[0] -split "`t")[0] } else { '' }  # porcelain 先頭＝main worktree（rm 対象外）
  $rpath=''; $rbranch=''; $hitMain=$false
  foreach ($line in $wts) {
    $cols = $line -split "`t"; $p = $cols[0]; $b = $cols[1]
    if ($abst) {
      if ($p -eq $abst) { $rpath=$p; $rbranch=$b; break }
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
  if ((Test-Path $container) -and -not (Get-ChildItem -Force $container)) { Remove-Item $container -Force }

  if ($delbranch -and $rbranch -ne '-' -and $rbranch -ne 'detached') {
    git branch -D "$rbranch"
    if ($LASTEXITCODE -eq 0) { Write-Output "  branch 削除: $rbranch" } else { Warn "branch 削除に失敗: $rbranch" }
  }
}

function Cmd-Worktree($rest) {
  if ($rest.Count -lt 1) { Die "使用法: aidev worktree <add|list|rm> ..." }
  $sub=$rest[0]; $sr=@(); if ($rest.Count -gt 1) { $sr=$rest[1..($rest.Count-1)] }
  switch ($sub) {
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
switch ($cmd) {
  'new'     { Cmd-New $rest }
  'event'   { Cmd-Event $rest }
  'approve' { Cmd-Approve $rest }
  'guard'   { Cmd-Guard $rest }
  'verify'  { Cmd-Verify $rest }
  'doctor'  { Cmd-Doctor }
  'status'  { Cmd-Status $rest }
  'metrics' { Cmd-Metrics $rest }
  'worktree' { Cmd-Worktree $rest }
  'help'    { Usage }
  '-h'      { Usage }
  '--help'  { Usage }
  default   { Die "未知のコマンド: $cmd（aidev help）" }
}
