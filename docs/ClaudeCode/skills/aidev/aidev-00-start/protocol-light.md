# 実行プロファイル（light）（`protocol.md`「11.」の詳細）

> **読む条件**: `profile: light` の work（着手時の三層判定は `aidev-00-start`）／light からの昇格
> 核となる規約と要約は `protocol.md`「11.」。ここはその詳細（工程ごとの読み込み量を抑えるため切り出し）。

`state.yml` の `profile` で**どこまで工程を回すか**を選ぶ。`mode`（誰が承認するか）とは**直交する別軸**で、
`light × interactive` と `light × autonomous` の両方が成立する。省略時は `full`。

### 三層の切り分け

| 層 | 対象 | 扱い |
|---|---|---|
| **対象外** | typo・コメント・整形・生成物の再生成など、判断を伴わない変更 | **aidev を通さない**（直接コミット） |
| **light** | 振る舞いを変えない / 小規模 / 下記条件を満たす | 上流 1 ゲート ＋ coding 以降は full と同一 |
| **full** | それ以外すべて | 現行パイプライン |

**「対象外」を勝手に light に格上げしない**（中身のない成果物と機械的な承認を量産させないための下限）。

### light を選べる条件（すべて満たすこと）

- 既存の**振る舞いを変えない**、または変更が単一の閉じた挙動に収まる。
- 触るファイルが **N 個以下**（既定 3。`.aidev/config.yml` の `lightMaxFiles` で調整可。
  CLI の最小 YAML 読み取りはフロー形式のフラットキーのみ対応なので、ネストキーにしない）。
- **共有モジュール / 公開 API / スキーマに触らない**。
- 新規の外部依存を追加しない。

判定は着手時に行うが、**自己申告を信用しない**（小さい変更ほど影響範囲を読み違える）。下記の昇格で救う。

### 上流 1 ゲートの規約

成果物は **4 つとも作る**（`requirements.md` / `design.md` / `tasks.md`）。
**スタブは作らない**（`tasks.md` は test が「テスト方針」を読む先なので、空にすると test が検証対象を失う）。
薄く書くのは各文書の**節を絞る**ことで実現し、light 専用テンプレートは作らない（既存テンプレの部分集合）。

| 文書 | light の必須節 | 省略可 |
|---|---|---|
| `requirements.md` | 背景 / 課題、**目的 / ゴール**、完了条件（受け入れ基準） | ユーザーストーリー、スコープ、機能要件、非機能要件 / 制約、未確定事項 |
| `design.md` | 設計方針、対象範囲 | I/F・データ構造、振る舞いの詳細、ドメイン固有、エラー処理 |
| `tasks.md` | 作業順序と依存関係、テスト方針、タスク一覧（`対象` アンカー・`依存`・`AC` 含む） | リスク / 留意点 |

**記録は `requirements` 1 件**にする（`aidev event requirements start` → `aidev approve requirements`）。
`design` / `tasks` で記録すると guard の前提（`requirements.md` / `design.md`）を満たせず NG になるため
（`requirements` は前提を持たない唯一の上流工程）。理由の詳細は `aidev-docs/DESIGN.md`「2.」。

`approved` に `design` / `tasks` が入らないのは正常（`need_approved` を使うのは walkthrough / deliver /
retro だけなので影響しない）。metrics 上は **`design` / `tasks` の start が無いこと**が light の指紋になる。

### 任意工程

light では **research / architecture / walkthrough を使わない**。必要と判断した時点で light の条件を
外れているので、**昇格の合図**として扱う。

### 昇格（light → full）

| 昇格トリガ | 検知点 |
|---|---|
| 想定外のファイルに触った / 影響が広がった | coding |
| `test` が落ちた | test |
| `review` で `must` が出た | review |
| 変更ファイル数が N を超えた | deliver（`files_changed` で機械検知。`aidev verify` が WARN） |
| 任意工程（research / architecture）が必要になった | 任意 |

**昇格は片方向**（`full` → `light` は不可）。手順:

1. `aidev escalate`（`profile` を `full` に書き換える。state.yml の編集は CLI に集約する）。
2. `decisions.md` に 1 エントリ（「設計から逸脱した判断」として）。
3. 該当工程の approved に `escalated_from_light=1`（「8.」）。
4. 省略していた節を各文書に**足す**（書き換えではない）。

**light でも coding / test / review / deliver は full と完全に同一**（review を残すことが品質の担保）。
