# 実行モード（autonomous）と plan モード（`protocol.md`「10.」の詳細）

> **読む条件**: `state.yml` が `mode: autonomous` の work／`aidev-util-batch`／plan モードを使うか迷ったとき（start・spec・design）
> 核となる規約と要約は `protocol.md`「10.」。ここはその詳細（工程ごとの読み込み量を抑えるため切り出し）。

`state.yml` の `mode` で実行モードを選ぶ。新規作業時に決定する（既定 interactive）。

### interactive（既定）
- 各工程末で人間の承認ゲート（「3.」）を通す。自動遷移しない。

### autonomous（夜間自律・PRまで一気通貫）
人間ゲートを置かずに requirement→…→deliver を自律実行し、**PR を出して停止**する。
「ゲートを消す」のではなく「**ゲートを PR（最終レビュー）に集約し、自己チェックを固くする**」モード。

- **requirement**: 起動時に与えられたタスク指示を requirement とする（対話ヒアリングはしない。
  指示が不十分なら autonomous を中止し interactive を促す）。
- **任意工程（research/design/walkthrough）**: 推奨ではなく**自律的に採否を決める**（検知したら実施）。
  **walkthrough は既定で実施**する（朝の一括レビューを助けるため）。
- **承認ゲート**: 自動承認（「3.」の autonomous 分岐）。`humanGates` に指定された工程だけは人間に確認
  （**部分自律**。例: `humanGates: [spec]` で方向性の誤り＝最大の手戻り源だけ人間が止める）。
- **終端**: deliver は **PR を作成して停止**する。**auto-merge は禁止**（マージは人間が行う）。

### 安全弁（autonomous 必須）
- **テストを硬いゲートに**: test が通らないまま PR を出さない。未解決なら **draft PR** にして要点を報告。
- **ループ上限**: review/test→coding の差し戻しは **`state.yml` の `maxSendBacks`（未指定なら 3）回まで**
  （同一工程あたり）。現在値は `metrics.yml` の当該 phase の `sent_back` イベント件数で判定する。
  上限到達後にさらに手戻りが必要なら、その工程の差し戻しは行わず**停止し、未解決点を報告して人手に委ねる**
  （test が未通過のままなら deliver は draft PR とする）。
- **予算/時間上限**: 上限到達で停止・報告（無限ループ防止）。
- **記録継続**: モードに関わらず state/metrics/各成果物・walkthrough は残す（朝の一括レビューの証跡）。
- **逸脱記録**: 自律中の重要判断は decisions.md に残す。

### 実行手段（別レイヤ）
autonomous の「夜間に回す」には実行主体が要る（headless 実行 / スケジュール起動でオーケストレーターが
本 skill 群を駆動）。これは harness（プロセス定義）とは別レイヤで用意する。

### plan モードとの関係（Claude Code）

plan モードは Write / Edit を禁じるので、成果物を書くのが仕事である**工程を完走することはできない**。
成立するのは **plan モード内で探索して方針の承認を取り、解除してから書く**形だけ。

```
探索（read-only）→ 方針を提案 → 承認 → 解除 → 成果物を書く
```

- **使う**: `aidev-00-start` の三層判定（この時点で aidev のゲートが無く二重にならない。解除後
  `aidev new` へ引き渡す）／spec・design（`full` × `interactive` のみ・任意。有力案が複数あるとき、
  文書を書く前に方針の承認を取れる）／ハーネス自体の改修（aidev の対象作業ではない）。
- **使わない**: research（純粋な調査は「2.6」の委譲が正）／plan（`plan.md` と成果物が重複＝
  計画を二度書く）／coding（`tasks.md` が承認済みの計画。方針変更は**差し戻し**を使う——
  差し戻しは metrics に残る）／test・review・deliver・retro（実装計画ではない）／
  `profile: light`（往復を減らす趣旨に反する）／`autonomous`（承認者がいない）。
- **plan モード中に工程を起動されたら、先に抜けるよう促す**（工程を中途で失敗させない）。
- 「工程内で段階的に確認したい」は **段階レビュー（「3.1」）**が対応する。plan モードとは併用しない。

判断の根拠は `aidev-docs/DESIGN.md`「2.」。


> **plan モードを使った場合も aidev の承認ゲートは省かない。** plan モードは方針、aidev のゲートは
> 文書を承認するもので、対象が違う。
