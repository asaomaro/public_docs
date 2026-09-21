# 仕様: retro で出たハーネス改善提案 5 件を aidev に適用する

## 概要

文書 4 点の追記と、CLI の新しいサブコマンド `aidev debug skip` を 1 つ足す。CLI の変更は
**既存の `debug report` と同じ作り**（散文は `decisions.md`・列挙値は `metrics.yml`・必須フィールドは CLI が強制）に
そろえ、`verify` の WARN と `debug status` の見え方だけを変える。

## 設計方針

- **「黙って無視」と「理由を書いて省く」を区別する**。`maxSendBacks` を超えた差し戻しは、原因究明の委譲が効く場面と、
  原因が特定済みで委譲の価値が無い場面の両方がある。後者を**記録の無い放置**と同じ扱いにすると、WARN が常態化して
  他の WARN を埋める（`taskcheck` の `unreported` で同じ判断をしている）。**出口を作るが、理由の記録を対価にする**。
- **新しい記録の形を作らない**。`stage=skip` は `stage=start` / `stage=report` と同じ `event: debug` の中に置く。
  既存の `dbg_rounds`（`stage:start` を数える）は変えず、`dbg_skips` を足して読む側だけを増やす。
- **文書は増やさず、既にある節に 1〜数行を足す**。`lint-docs.sh` が読み込み量を検査するため。

## 対象範囲

- `docs/ClaudeCode/skills/aidev/aidev-60-review/SKILL.md`（手順 2 の冒頭に、ラウンド 2 以降の範囲）
- `docs/ClaudeCode/skills/aidev/aidev-40-coding/SKILL.md`（手順 5 の条件に 1 行）
- `docs/ClaudeCode/skills/aidev/aidev-00-start/protocol.md`（「7.」に沈黙する失敗・「8.」に `sent_backs` の読み方）
- `docs/ClaudeCode/skills/aidev/aidev-00-start/protocol-debug.md`（`skip` の位置づけと打ち方）
- `docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev`（`dbg_skip` / `dbg_skips` / `cmd_debug` / `verify` / `dbg_status`）
- `docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev.ps1`（同じ表面）
- `docs/ClaudeCode/skills/aidev/aidev-docs/bin/README.md`（`debug` の行に `skip` を足す）
- `docs/ClaudeCode/skills/aidev/aidev-docs/bin/test/run.sh`（回帰テスト）

## 依拠する既存の事実

- `debug` の実装は `aidev` の `dbg_start` / `dbg_report` / `dbg_status` / `cmd_debug`（`aidev:1641-1845` 付近）。
  ラウンド数は `dbg_rounds`（`stage:start` を数える。`aidev:1688-1695`）。
- `debug report` は**散文を `decisions.md` に、列挙値を `metrics.yml` に**分けている（`aidev:1771-1795` 付近。
  metrics はフロー形式の 1 行なので自由文を入れると壊れる）。
- `verify` の WARN は schema 8 の節で、`dbg_sent_backs >= maxSendBacks` かつ `dbg_rounds == 0` のときに出る
  （`aidev:2841-2853`）。`by: unapprove` の `sent_back` は `dbg_sent_backs` が既に除外している（`aidev:2801-2808`）。
- `debug status` は工程ごとに `sent_backs` / `debug_rounds` / `due` を出す（`aidev:1808-1836`）。
- ps1 は sh と同じ表面を持つ（`aidev.ps1:1464-1540` 付近が `debug`）。表面の食い違いは `test/lint-docs.sh` が検査する。
- 差し戻し時の促しは `event ... sent_back` の中にある（`aidev:778-800`・`aidev.ps1:815`）。

## インターフェース / データ構造

```
aidev debug skip [slug] [--phase <phase>] --reason "<理由>"
```

- `--reason` は**必須**（無ければ exit 1 で「理由を書けないなら省かない」と案内する）。
- 対象工程は `--phase`、無ければ `state.yml` の `current`。
- **差し戻しが 1 回も無い工程では拒否する**（exit 1）。省く対象が無いのに記録だけ残るのを防ぐ。
- 記録：
  - `metrics.yml`：`{ ts: …, phase: <p>, event: debug, metrics: { stage: skip, sent_backs: <n> } }`
    （`sent_backs` はその時点の差し戻し回数。後から「何回目で省いたか」が読める）
  - `decisions.md`：`## デバッグ D<n>: <工程> の原因究明を省いた` … 背景（差し戻し回数）・決定（理由）を追記。
    既存の `debug report` の追記と同じ体裁。
- 出力：`debug: <slug>/<phase> skip（差し戻し <n> 回）` と、`next:` に「同じコンテキストで回し続けない」注意。

## 振る舞いの詳細

- `verify`：schema 8 の WARN の条件に `dbg_skips == 0` を足す（skip があれば出さない）。
- `debug status`：`due` 列の判定に skip を含め（skip があれば `no`）、`debug-summary` に `skips=<n>` を足す。
- `event <工程> sent_back` の上限到達の促し：`aidev debug start` に加えて
  「原因が特定済みなら `aidev debug skip --reason …`」を 1 行添える。
- skip の後に `debug start` を打つことは妨げない（省いた後に必要になったら委譲してよい）。

## ドメイン固有の考慮

- **記録は追記のみ**（`metrics.yml` の既存行は書き換えない）。skip が無い work の出力は 1 文字も変わらない。
- **sh と ps1 の表面をそろえる**。`lint-docs.sh` の CLI 表面の検査（help・README の表）に掛かる。

## エラー処理 / 異常系

- `--reason` 無し → exit 1・「`--reason` は必須（理由を書けないなら省かない）」。
- 差し戻しが 0 回の工程 → exit 1・「この工程は差し戻されていない」。
- 未知の工程名 → 既存の `die_unknown_phase` に合わせる。

## 受け入れ基準との対応

- AC1: `aidev-60-review/SKILL.md` の手順 2 に、ラウンド 2 以降の範囲（前ラウンドの解消＋当該差分の must/should、
  範囲外は backlog）を書く。入力は wtm の retro の「統合 review のラウンドが収束しなかった」。
- AC2: `dbg_skip` を足し、`--reason` を必須にして `decisions.md` と `metrics.yml` に分けて記録する。
- AC3: `verify` の WARN の条件に `dbg_skips == 0` を足す。
- AC4: `protocol.md`「7.」に、出力の有無で成否を判断しない旨を足す。入力は wtm の D96 の訂正。
- AC5: `protocol.md`「8.」に、per-phase の `sent_back` が `by: unapprove` を含む旨を足す
  （`metrics` の表と `dbg_sent_backs` は除外している、という既存の事実との対で書く）。
- AC6: `aidev-40-coding/SKILL.md` の手順 5 の条件に、interactive でも共有モジュール・外部に見える振る舞いは既定で点検、を足す。
- AC7: `test/run.sh` に skip の回帰（記録・WARN の消滅・理由必須）を足し、`lint-docs.sh` を通す。
- AC8: `aidev.ps1` に同じ `skip` を実装し、help と README の表を更新する。
