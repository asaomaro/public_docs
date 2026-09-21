# タスク: retro で出たハーネス改善提案 5 件を aidev に適用する

## 実装方針

文書だけの変更（T1・T2・T3）を先に済ませ、CLI の変更（T4〜T7）を後に置く。CLI は sh → ps1 → README → テストの順で、
**表面をそろえながら**進める（`lint-docs.sh` が食い違いを検査する）。

## 作業順序と依存関係

- 下の `依存:` に従う。T4（sh の実装）が決まらないと ps1・README・テストの中身が決まらないので、そこだけ直列。

## リスク / 留意点

- **既存の記録を壊さない**。`metrics.yml` は追記のみ。skip が無い work の出力は変えない。
- **sh と ps1 の食い違い**が最も起きやすい（`lint-docs.sh` の検査対象）。同じ関数名・同じ出力文字列にそろえる。
- 文書の増加は最小限（`lint-docs.sh` が読み込み量を見る）。

## テスト方針

- `sh docs/ClaudeCode/skills/aidev/aidev-docs/bin/test/run.sh`（既存の回帰 ＋ 足した skip の回帰）。
- `sh docs/ClaudeCode/skills/aidev/aidev-docs/bin/test/lint-docs.sh`（CLI 表面と文書の整合）。
- 実際の work（この work 自身）で `aidev debug skip` を打ち、`verify` の WARN が消えることを確かめる。

## タスク

- [x] T1: review のラウンド 2 以降の範囲を書く。
      対象: `docs/ClaudeCode/skills/aidev/aidev-60-review/SKILL.md` の手順 2
      依存: なし
      AC: AC1
- [x] T2: 「沈黙する失敗」と `sent_backs` の読み方を protocol に書く。
      対象: `docs/ClaudeCode/skills/aidev/aidev-00-start/protocol.md`「7.」「8.」
      依存: なし
      AC: AC4, AC5
- [x] T3: タスク点検の推奨を強める。
      対象: `docs/ClaudeCode/skills/aidev/aidev-40-coding/SKILL.md` の手順 5
      依存: なし
      AC: AC6
- [x] T4: `aidev debug skip` を sh に実装する（`dbg_skip` / `dbg_skips` / `cmd_debug` / `dbg_status` / `verify` の WARN /
      `event sent_back` の促し）。
      対象: `docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev`
      依存: なし
      AC: AC2, AC3
- [x] T5: ps1 に同じ表面を実装する。
      対象: `docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev.ps1`
      依存: T4
      AC: AC8
- [x] T6: CLI の表面の文書を更新する（`debug` の行に `skip`・使用法の行・`protocol-debug.md` の位置づけ）。
      対象: `docs/ClaudeCode/skills/aidev/aidev-docs/bin/README.md`・`docs/ClaudeCode/skills/aidev/aidev-00-start/protocol-debug.md`
      依存: T4
      AC: AC2, AC8
- [x] T7: 回帰テストを足し、テスト一式を通す。
      対象: `docs/ClaudeCode/skills/aidev/aidev-docs/bin/test/run.sh`
      依存: T4, T5
      AC: AC7

## 完了メモ
- T1〜T3（文書）：`lint-docs.sh` の L6（読み込み量の予算）に当たったので、追記を詰めたうえで
  `BUDGET_TOTAL` を 3485 → 3511 に更新した（内訳と根拠を同ファイルのコメントに残した。予算は
  「増やすなら意図的に、その数を書き換えるコミットで理由を述べる」設計）。
- T4（sh）：`dbg_skip` / `dbg_skips` を足し、`cmd_debug`・`dbg_status`・`verify` の WARN・
  `event sent_back` の促しを更新。記録の分け方（散文は decisions.md・列挙値は metrics.yml）は
  既存の `debug report` にそろえた。
- T5（ps1）：同じ表面を実装（`DbgSkips` / `Dbg-Skip`・dispatch・status の列・verify の WARN・促し）。
- T6（文書）：`bin/README.md` の `debug` の行に `skip` を足し、`protocol-debug.md` に「省く」節を新設。
- T7（テスト）：`test/run.sh` に skip の回帰 8 件を追加（`--reason` 必須・差し戻し 0 回では拒否・
  decisions.md と metrics.yml への記録・WARN が消える・status の skip 列）。`debug status` の列が
  増えたので既存の期待値 2 件も更新した。
- 検証：`sh test/run.sh` は 820 passed / 0 failed（pwsh 不在時）。`lint-docs.sh` は 23 passed / 0 failed。
  pwsh が無いとパリティテスト 260 件が skip されるため、`test/setup-pwsh.sh` で 7.4.6 を入れて流し直した。

- [x] T8: review ラウンド1 の 10 件を直す。(a) skip の受理範囲（上限未到達は拒否・skip 後に増えたら鳴らし直す）。
      (b) ps1 のパリティテストに skip を足す。(c) ハーネス改修の 3 ゲートを通し `flow-runs/` に実走記録を残す。
      (d) 概観 README・`protocol-debug.md`「記録と検査」・sh の help に skip を反映。(e) AC6 の重複を 1 箇所に寄せる。
      (f) AC5 の追記を `protocol-analysis.md` へ移す。(g) 予算の内訳コメント・`--reason` の改行・工程ごとの抑止のテスト。
      対象: `docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev`・`aidev.ps1`・`test/run.sh`・`test/lint-docs.sh`・
      `aidev-docs/README.md`・`aidev-docs/retro/flow-runs/`・`aidev-00-start/protocol.md`・`protocol-debug.md`・
      `protocol-analysis.md`・`aidev-40-coding/SKILL.md`
      依存: T7
      AC: AC1, AC2, AC3, AC5, AC6, AC7, AC8
      完了メモ（T8）: review の 10 件を反映し、3 ゲートの (3) 実走を使い捨ての PJ で行った。**実走が重い欠陥を 1 件見つけた**——
      `--phase` を省くと `current`（＝最後に承認した工程。多くは coding）に記録され、差し戻された工程の WARN は消えないまま
      黙って通る。しかも `verify` の WARN と概観 README がその裸の形を勧めていた。既定を「上限に達している工程」に変え、
      1 つに決まらなければ `--phase` を要求するようにした（sh / ps1 とも。回帰テスト 4 件）。あわせて bin/README の条件の
      誤り（「差し戻しが 1 回も無い工程では拒否」）と、省ける回数に上限が無い旨の記載漏れも直した。実走記録は
      `aidev-docs/bin/test/flow-runs/2026-09-20-debug-skip-and-review-scope.md`。範囲外の既存差（sh と ps1 の slug 解決）は
      `.aidev/backlog/harness.md` へ。`sh test/run.sh` は 1123 passed / 0 failed / 0 skipped、`lint-docs.sh` は 23 passed。
