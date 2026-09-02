# aidev 開発ワークフローハーネス — 利用ガイド

PJ非依存の開発ワークフローを、skill 群で制御・進捗管理するハーネス。
要件定義からデリバリまでを、人間の承認ゲート付きで一貫して進め、いつでも中断・再開できる。

> このファイルは参照専用（`SKILL.md` ではないため skill 実行時には読まれない）。
> 設計思想・意思決定の記録は [DESIGN.md](./DESIGN.md) を参照。

## これは何か

- **基盤＝開発フローの制御と進捗管理の器**（工程順・承認・遷移・状態・再開）。
- **実作業の中身は PJ 資産に委ねる**：PJ の AGENTS.md（規約・観点）と PJ固有 skill（review/commit 等）が
  あれば自動的に優先され、無ければ各工程のジェネリック手順で進む。

## クイックスタート

1. 開発を始める／再開する：

   ```
   /aidev-00-start
   ```

   現在の作業状況を確認し、「続きから / 別工程をやり直す / 新規作業」を選べる。
2. 新規作業を選ぶと `.aidev/works/<YYYYMMDD>-<slug>/` が作られ、requirement 工程へ進む。
3. 以降、各工程の最後で承認ゲート（選択肢UX）が出る。選ぶだけで次へ進む／中断できる。

慣れていれば各工程を直接呼んでもよい（例 `/aidev-40-coding`）。各工程は前提を自己チェックする。

## 工程一覧

| 番号 | 工程 | 種別 | 役割 |
|------|------|------|------|
| 00 | start | 入口 | ルーター。状況確認と工程案内 |
| 10 | requirement | 標準 | 何を・なぜ作るか。ゴール（達成したい状態）・ユーザーストーリー・受け入れ基準（requirement.md） |
| 15 | research | 任意 | spec 前の事実調査（research.md） |
| 20 | spec | 標準 | どう作るか・仕様（spec.md） |
| 25 | design | 任意 | 構造設計（design.md） |
| 30 | plan | 標準 | 作業分解（plan.md / tasks.md） |
| 40 | coding | 標準 | 実装、tasks 更新 |
| 50 | test | 標準 | 受け入れ基準の検証 |
| 60 | review | 標準 | 差分点検（指摘あれば coding へ差し戻し） |
| 65 | walkthrough | 任意 | 人間レビュー補助の解説（walkthrough.md・mermaid） |
| 70 | deliver | 標準（最終） | コミット / PR で着地 |
| 95 | retro | 任意 | 振り返りと改善提案（retro.md） |

標準フロー：`requirement → spec → plan → coding → test → review → deliver`。
番号末尾 **0=標準 / 5=任意**。番号は推奨順であり強制ではない（差し戻し可）。

### 命名カテゴリ（役割で割る）

skill は **役割／レイヤ**で命名し、トリガ（人間/AI）では割らない（標準工程は両方から呼ばれ得るため）。
**ここが正典**（`protocol.md`「4.1」はここを指す）。カテゴリは各 skill の description 冒頭の定型タグで示す:
統制語彙は `［aidev 入口｜aidev 標準工程｜aidev 任意工程｜aidev ユーティリティ］`。主トリガは下表が正で、
description には書かない（15 本で同じ 50 字を繰り返しても弁別に寄与しない）。
`aidev` CLI は skill ではなく Bash コマンドなので「skill」と呼ばない。

**description の弁別性**: 発火語は `aidev <工程名>` / `<工程名> 工程` と「前工程から案内されたとき」に限る。
「レビューして」「コミットして」「PR を出して」「実装を始めたい」のような**汎用句を書かない**——同居する他 skill
（`create-pr` / `code-review` 等）と競合し、aidev の作業が無い文脈で発火すると protocol.md を丸ごと無駄読みする
（誤発火 1 回のコストが description 全体より大きい）。工程 skill には「aidev 作業の無い単発依頼では使わない」を明記する。

| カテゴリ | 命名 | 主トリガ |
|---|---|---|
| 入口/ルーター | `aidev-00-start` | ユーザー起動 |
| 標準工程 | `aidev-N0-<名>`（末尾0） | 両方（直接 / 前工程遷移 / autonomous 自動） |
| 任意工程 | `aidev-N5-<名>`（末尾5） | AI検知推奨 or ユーザー指定 |
| ユーティリティ | `aidev-util-<名>`（番号なし） | ユーザー起動（一部 /loop） |
| ランタイムガード（skill外） | `aidev` CLI（`.claude/skills/aidev-docs/bin/`） | 工程内で AI が自動 |

### ユーティリティ（番号なし・パイプライン外）

| skill | 役割 |
|---|---|
| `aidev-util-insights` | 複数作業を横断して傾向・再発パターンを分析し、改善提案を出す（`/aidev-util-insights`） |
| `aidev-util-batch` | バックログの未処理項目を autonomous モードで順次処理（L1 バッチ駆動）。`/loop`・`/schedule` から起動可 |
| `aidev-util-propose` | charter と信号(insights/retro/負債)から次の課題を提案・分割し、承認のうえ issue/バックログ化（L_planner / 最上流） |

### 自己給餌ループ（実用形）

```
insights/retro（信号） → aidev-util-propose（課題化・人間承認） → aidev-util-batch（autonomous実装） → PR（人間レビュー）
```
両端（どの課題・どの PR）に人間ゲートを残し、間を自律化する。完全自動（発案→マージ）は高リスクのため採らない。
planner の方針は `.aidev/charter.md` で縛る。

## 承認ゲート（各工程の終わり）

工程ごとに成果物を提示し、単一の選択肢から選ぶ：

- `承認して次工程へ進む`
- `承認してここで中断`（再開可能な状態で停止）
- `差し戻す`（指摘を反映して同工程をやり直す）
- `成果物を1項目ずつ確認しながら進む`（段階レビュー。`protocol.md`「3.1」）

自動では次へ進まない。最終工程 deliver では「承認して完了」になる。
（AskUserQuestion 非対応エージェントでは同じ選択肢をテキストで提示）

## 実行モード（interactive / autonomous）

`state.yml` の `mode` で切替（既定 interactive）。

- **interactive**: 各工程末で人間が承認（上記ゲート）。
- **autonomous**: 人間ゲートを置かず requirement→…→deliver を自律実行し、**PR を出して停止**（auto-merge しない）。
  夜間に回して朝に PR を一括レビューする使い方。`humanGates`（例 `[spec]`）で特定工程だけ人間ゲートを残す**部分自律**も可。
  安全弁: test は硬いゲート（未通過なら draft PR）／差し戻し回数・予算に上限／成果物・walkthrough を証跡として残す。
  ※夜間に回す実行手段（headless/スケジュール）は harness とは別レイヤで用意する。

## 実行プロファイル（full / light）

`state.yml` の `profile` で「どこまで工程を回すか」を選ぶ。`mode`（誰が承認するか）とは**直交**する軸で、
`light × autonomous` のような組み合わせも成立する。省略時は `full`。

| 層 | 対象 | 使い方 |
|---|---|---|
| **対象外** | typo・コメント・整形など判断を伴わない変更 | **aidev を通さない**（直接コミット） |
| **light** | 振る舞い不変・小規模（3 ファイル以下・共有モジュールや公開 API に触らない） | `aidev new <slug> --light` |
| **full** | それ以外 | `aidev new <slug>`（既定） |

light は**上流3工程（requirement / spec / plan）を1ゲートに畳む**。成果物は4つとも作るが、
各文書は必須節だけに絞る（`protocol.md`「11.」）。**coding / test / review / deliver は full と完全に同一**で、
品質ゲートは省かない。任意工程（research / design / walkthrough）は light では使わない。

条件を外れたら `aidev escalate` で **full へ片方向に昇格**する（省略していた節を足すだけ）。
昇格の合図は「想定外のファイルに触った」「test が落ちた」「review で must が出た」
「`files_changed` が上限超過」。昇格漏れは `aidev verify` が WARN で知らせる。

## 任意工程の起動

- **ユーザー指定**：明示的に `/aidev-15-research` 等を選ぶ。
- **AI検知＋推奨**：requirement 終了時に調査不足を、spec 終了時に複雑度を検知すると、
  遷移ゲートで research / design を理由付きで推奨する（却下すれば標準工程へ直行）。
- retro はユーザー指定で起動（作業完了後）。

## 中断と再開

- 状態は `.aidev/works/<YYYYMMDD-slug>/state.yml`（`current` / `approved` / `dependsOn`）＋成果物ファイルで管理。
- どこで止めても、`/aidev-00-start` で現在地が復元され、続きから再開できる。
- 複数作業を並行可能。`.aidev/current` が「今どれを触っているか」を指す。

## ファイル構成

```
.claude/skills/
  aidev-00-start/      入口 + protocol.md（共通規約のホーム）
  aidev-10-requirement/ … aidev-95-retro/   各工程（番号付きパイプライン）
  aidev-util-propose/ aidev-util-batch/ aidev-util-insights/   ユーティリティ（番号なし・パイプライン外）
  aidev-docs/          このREADMEとDESIGN（参照専用・skillではない）＋ bin/
    bin/               ランタイムガード CLI（aidev=POSIX sh / aidev.ps1=PowerShell・README.md / test/ 同梱）
.aidev/                PJ固有の実行時状態（skill ではない）
  config.yml           PJ単位の設定（tracker 種類など。コミット対象）
  current              現在の作業フォルダ名（.gitignore 対象）
  works/<YYYYMMDD-slug>/  作業単位ごとの成果物（命名: 日付(UTC)-slug）
    state.yml          進捗（schema / current / approved / dependsOn / ticket / mode / profile）
    metrics.yml        工程の実施日時・時間・件数などのイベントログ
    requirement.md / spec.md / plan.md / tasks.md / decisions.md / review.md など
  backlog/             遅延キュー（任意）。<domain>.md（standing）/ split-<親>.md（split）/ archive/
  insights/            横断分析レポート（<日付>-insights.md）
```

## 別PJへの導入

1. `.claude/skills/aidev-*`（`aidev-docs/bin/` のランタイムガード CLI を含む）をコピー。CLI は skills 同梱なので
   別途コピーは不要。`aidev-docs/bin/aidev` に実行権限を付ける（`chmod +x`）。
2. リポジトリ直下に `.aidev/` を用意する（CLI は `.aidev/` を上方探索して状態を読み書きする。最初の作業前に
   存在させる。`config.yml` を置くか空ディレクトリでよい）。
3. `.gitignore` に `.aidev/current` を追加（`.aidev/works/` 配下の成果物はコミット推奨）。
4. PJ の AGENTS.md に規約・レビュー観点を書く。PJ固有 skill があればそのまま活かされる。

基盤はドメイン非依存。PJ固有の知識・実作業は AGENTS.md と PJ skill 側が担う。

## 任意セットアップ: Stop フック（Claude Code のみ）

**記録漏れの予防**を機械化する。`aidev` の `guard` と `event start` は別コマンドなので、
guard だけ実行して工程に入り start を記録し忘れる事故が構造的に起こりうる。`verify` は
これを deliver 前に WARN で**事後検知**できるが、`Stop` フックなら**停止の手前で防げる**。

**任意である**（`protocol.md`「2.10」の第三層）。設定しなくても第一層（散文規約）と
第二層（`aidev verify`）は効く。判定はフックではなく CLI（`verify --strict`）が持つ。

`~/.claude/settings.json`（または `.claude/settings.json`）の `hooks` に追加する:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "shell": "bash",
            "statusMessage": "aidev: 記録漏れを検査中",
            "timeout": 20,
            "command": "[ -d .aidev ] || exit 0; A=\"$HOME/.claude/skills/aidev-docs/bin/aidev\"; [ -f \"$A\" ] || exit 0; [ -f .aidev/current ] || exit 0; sh \"$A\" verify --strict >/dev/null 2>&1; if [ $? -eq 5 ]; then printf \"%s\" \"{\\\"decision\\\":\\\"block\\\",\\\"reason\\\":\\\"aidev: 工程の記録漏れがあります。aidev verify --strict で該当工程を確認し、aidev event <工程> start 等で記録を補ってから終えてください（metrics.yml は追記のみで、当時の timestamp は後から復元できません）。\\\"}\"; fi; exit 0"
          }
        ]
      }
    ]
  }
}
```

- **`.aidev` の無いディレクトリでは即 `exit 0`**——aidev を使っていないリポジトリには一切影響しない。
- 記録漏れ以外（`profile: light` の逸脱など）では**止めない**。止めるのは「今しか直せないもの」だけ。
- 設定後は `/hooks` で確認できる（設定ファイルの監視は、セッション開始時に存在したディレクトリのみ
  対象なので、初回は `/hooks` を開くか再起動が必要な場合がある）。
- `aidev` を別パスに置いた場合は `A=` を書き換える。

## 他エージェントについて

Claude Code 固有の機構は**すべて任意の高速化層**で、無くても不変条件は保たれる（`protocol.md`「2.10」）。
採用基準は「**同じことを指示で書けるものに限る**」で、ハードな層（判定・不変条件）は必ず `aidev` CLI 側にある。

| Claude Code 固有 | 他エージェントでのフォールバック |
|---|---|
| `Stop` フック | 指示に「終える前に `aidev verify --strict`」を書く |
| `/goal`（停止前チェック・**ユーザーが打つもの**） | 同じ内容を指示で書く |
| 組み込みレビューコマンド | ジェネリック手順で自分で見る |
| plan モード | 「先に方針を提示して承認を得てから書く」を指示で行う |
| `AskUserQuestion`（選択肢UX） | 同じ選択肢をテキストで提示 |
| サブエージェント委譲（`Agent`） | 各機構、または同一セッションでインライン実行 |

Copilot / Codex 等では、各エージェントのルールファイル（`AGENTS.md` /
`.github/copilot-instructions.md`）に次を書けば第三層の代替になる。

```markdown
## aidev（AI開発ワークフロー）
- 工程を開始したら `aidev event <工程> start` を記録する。
- **工程を終える前に必ず `.claude/skills/aidev-docs/bin/aidev verify --strict` を実行する。**
  非ゼロで終われば（5＝記録漏れ）記録を補ってから終える。
  `metrics.yml` は追記のみで、**当時の timestamp は後から復元できない**。
- 各工程の完了条件は対応する SKILL.md の「完了の目安」に従う。
```
