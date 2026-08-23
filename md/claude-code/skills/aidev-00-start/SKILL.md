---
name: aidev-00-start
description: ［入口/ルーター／主トリガ:ユーザー起動］AI開発ワークフローの入口。作業状況を確認し、どの工程から始めるかをユーザーに確認して案内する。「AI開発を始めたい」「開発ワークフローを開始」「続きから再開」「aidev」などと言われたときに使用する。
allowed-tools: [Bash, Read, AskUserQuestion]
---

AI 開発ワークフローの入口（ルーター）。
ワークフロー全体を説明し、現在の作業状況を確認したうえで、どの工程から開始するかをユーザーに確認して案内する。

共通規約は同梱の `protocol.md`（このディレクトリ内）に従う。実行前に必ず読むこと。
この harness は `.claude/skills/aidev-*` だけで自己完結し、PJ 固有ファイルには依存しない。

## 1. ワークフローの説明

以下を簡潔に提示する。

- 工程は `requirement → spec → plan → coding → test → review` の順（推奨デフォルト）。
- 各工程は **承認ゲート付き**で、自動では次に進まない（承認後に「次へ進むか」を確認する）。
- 番号順は強制ではなく、差し戻し（例: review → coding）も可能。
- 作業は `.aidev/works/<YYYYMMDD-slug>/` 単位で管理され、いつでも中断・再開できる。

## 2. 作業状況の確認

**`aidev status` で機械抽出する**（各 `state.yml` を個別に手読みしない。works が増えても一定コスト）。

```sh
.claude/skills/aidev-docs/bin/aidev status                 # 進行中(works)＋未着手(backlog) を人間可読表で
# 機械処理が必要なら: .claude/skills/aidev-docs/bin/aidev status --format tsv
# Windows: pwsh .claude/skills/aidev-docs/bin/aidev.ps1 status
#          （pwsh 無しなら powershell -NoProfile -File ... / Git Bash なら POSIX 版の aidev がそのまま動く）
```

出力の読み方:

- **WORKS 表**: `work` / `ticket` / `mode` / `current` / `next`（次工程。`done` なら `-`）/ `done`
  （`deliver` 承認済か）/ `deps`。`deps` が `ok` 以外（`<slug>(未deliver)` や `#N(advisory)`）の作業は
  依存未充足・要確認＝ `⛔依存待ち（<deps の内容>）` として扱う（`protocol.md`「2.7」）。
- **BACKLOG 表**: backlog ファイルごとの未着手件数 `todo` と、依存待ち（`(needs:…)`）件数 `needs`。
  これで「進行中（works）＋未着手（backlog）」を1画面で把握できる（ビュー統合。`DESIGN.md`「2.5」）。
  各項目の本文（先頭数件）が必要なら、対象ファイルを `grep '- \[ \]' .aidev/backlog/<file>` で参照する。
- **外部トラッカー（任意）**: `.aidev/config.yml` の `tracker.type` が `github` 等なら、必要に応じ
  `gh issue list`（または各ツール）で open を「未着手（トラッカー）」として併記してよい（status の対象外）。

CLI が使えない環境のフォールバック: `cat .aidev/current` / `ls .aidev/works` と各 `state.yml`
（`current`/`approved`/`dependsOn`）＋ `.aidev/backlog/*.md`（`archive/` 除く）を読んで同等に要約する。

`.aidev/` 自体が無い場合は「新規作業の開始」のみ提示する。

## 3. ユーザーへの確認

`AskUserQuestion` ツールで次の選択肢を提示する（`Other` による自由入力も可）。
非対応エージェントでは同じ選択肢をテキストで提示する。

- **続きから**：既存の作業を選択 → `aidev use <slug>`（`.aidev/current` を更新。存在しない slug は弾かれる）
  → その工程の skill を案内。CLI 無し環境では `.aidev/current` を手で書く。
- **別工程をやり直す（差し戻し）**：作業と工程を選択 → 当該工程の skill を案内。
- **未着手から着手する**：backlog／トラッカーの未着手項目を選び、その内容を requirement として手順 4 へ
  （依存 `(needs:…)` が未充足なら警告。`protocol.md`「2.7」）。
  - **選ぶ前に、その項目が本当に未着手か確かめる**。backlog は**遅れる**——別の作業が結果的に
    閉じていても、行は `[ ]` のまま残りうる。**works の記述ではなくリポジトリの現物**
    （ファイル・シンボル・テスト・ビルド出力）で裏を取ってから着手する。
    2026-08-01 に、5 日前に完了済みの項目を選んで requirement を書きかけた実例がある。
  - **backlog 由来なら手順 4 で `--backlog <file>` を渡す**（deliver での消し込みを verify が強制する）。
- **新規 requirement を起こす**：手順 4 へ。

作業が複数ある場合は、まず対象の works フォルダを選ばせてから上記を提示してよい。

## 4. 新規作業の開始

0. **三層のどれかを判定する**（`protocol.md`「11.」）。ここを飛ばすと、typo 修正に全工程を回すか、
   逆に影響の大きい変更を軽い経路に流すことになる。

   | 層 | 対象 | 案内 |
   |---|---|---|
   | **対象外** | typo・コメント・整形・生成物の再生成など、判断を伴わない変更 | **aidev を通さない**。直接修正・コミットを案内してここで終了する |
   | **light** | 振る舞いを変えない / 小規模（触るファイルが 3 個以下・共有モジュールや公開 API に触らない・新規依存なし） | `aidev new <slug> --light`。上流 3 工程を 1 ゲートに畳む |
   | **full** | それ以外すべて | `aidev new <slug>`（既定） |

   - **判定はユーザーに確認する**（`AskUserQuestion`）。「小さい変更」の見立ては外れやすく、
     特に共有モジュールの 1 行変更は影響範囲を読み違えやすい。
   - **影響範囲が読めないときは plan モードを使う**（`protocol.md`「10.」）。`EnterPlanMode` で
     read-only のまま影響範囲を調べ、三層の判定と着手方針を提案して `ExitPlanMode` で承認を取り、
     **解除してから手順 2 の `aidev new` に引き渡す**。この時点では aidev のゲートがまだ無いので
     二重ゲートにならず、plan モードが最も素直に効く場所になる。
     - 判定が自明なとき（typo・明らかに大きい機能追加）は使わない。
     - `aidev new` は書き込みなので、**必ず plan モードを解除してから**実行する。
   - 迷ったら **full を選ぶ**。light は後から full へ昇格できる（`aidev escalate`）が、逆はできない。
   - **light を選んでも review / test / deliver は full と同一**に通る。省くのは上流の文書の深さと
     承認の往復だけで、品質ゲートは残る。

1. requirement の概要をユーザーに確認し、簡潔な slug を決める（kebab-case、英小文字）。
2. **`aidev new <slug>` を実行**して作業を作成する（フォルダ作成・日付プレフィックス採番・
   `state.yml`/`metrics.yml` 初期化・`.aidev/current` 設定・`schema` 刻印を一括で行う）。
   - 実行モード（`protocol.md`「10.」）: 既定 `--mode interactive`。夜間自律で PR まで回すなら
     `--mode autonomous`（必要なら作成後に `state.yml` の `humanGates` を設定＝部分自律。例 `[spec]`）。
   - 実行プロファイル（`protocol.md`「11.」）: 手順 0 が light なら `--light`。**mode とは直交**するので
     `--mode autonomous --light` のような組み合わせも成立する。
   - 外部チケット連携時は `--ticket <ID>`（種類は `.aidev/config.yml` の `tracker`）。
   - 前提となる作業/issue があれば `--depends <works slug,#N,…>`（`protocol.md`「2.7」「6.」）。
   - **backlog 項目から起こしたなら `--backlog <file>`**（例 `--backlog hostserver.md`）。
     出自を `state.yml` に刻み、**deliver で消し込まないと `aidev verify` が FAIL する**
     （閉じ忘れを機械的に塞ぐ。`aidev-70-deliver`「3.5」）。
   - 例: `aidev new user-login --mode interactive --ticket "#42" --depends 20260620-base`
   - 例: `aidev new ifs-preview-race --mode autonomous --backlog hostserver.md`
   - **CLI を持たない環境**では手で同等に行う（`date -u +%Y%m%d` で `<YYYYMMDD>-<slug>` 採番 → `mkdir` →
     `protocol.md`「6.」に従い `state.yml`（`schema`/`current: requirement`/`approved: []`）と
     `metrics.yml`（`events:`）を作成 → `.aidev/current` 設定）。
3. **作業ブランチの準備（PJ委譲・任意）**：PJ がブランチ運用の場合に行う（`protocol.md`「2.5」に従う）。
   - PJ にブランチ作成を伴う skill（例: issue＋ブランチ作成 skill）があれば、それを優先して使う。
   - 無ければ PJ 規約に沿って作成する（例: `feature/<slug>`）。
   - trunk-based 等ブランチを使わない PJ ではスキップする。
   - 既に作業ブランチ上にいる場合は新規作成しない（重複防止）。
   - 成果物（`.aidev/works/...`）も同じブランチに乗せると、後段の PR がきれいになる。
4. `aidev-10-requirement` 工程の開始を案内する（`profile: light` の場合も同じ——上流 3 工程は
   requirement 1 ゲートに畳まれ、`aidev-10-requirement` がそのゲートを担う。`protocol.md`「11.」）。

## 5. 注意

- この skill は工程を直接実行しない。あくまで現在地の把握と次工程の案内に徹する。
- 工程の実行可否・終了処理は各工程 skill と `protocol.md` に委譲する。
- **plan モード中に呼ばれたら、先に plan モードを抜けるよう促す**（`protocol.md`「10.」）。
  aidev の工程は成果物を書くのが仕事なので、plan モードのままでは工程が途中で止まる。
- **記録漏れの予防は Stop フックに任せる**（`protocol.md`「3.2」「2.10」）。この skill が
  `/goal` を設定することはできない（組み込みスラッシュコマンドで**ユーザーが打つもの**）。
  記録以外の完了条件を置きたい場合に限り、ユーザーへ `/goal` の設定を提案してよい。
