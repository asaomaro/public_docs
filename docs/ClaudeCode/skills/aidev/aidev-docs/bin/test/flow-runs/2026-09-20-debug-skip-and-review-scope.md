---
date: 2026-09-20
change: 別 PJ（web-tn-multiplexer の新規プロジェクト 1 本）の retro が出した「ハーネス自体」の提案 5 件を適用。`aidev debug skip` の新設と、review のラウンド範囲・沈黙する失敗・`sent_back` の数え方・タスク点検の推奨の追記
---

## 1. 文書は実態に追いついているか

**提案をそのまま入れず、実物で確かめてから採否を決めた**。出所は
`/workspaces/web-tn-multiplexer/.aidev/works/20260918-web-terminal-multiplexer/retro.md`「ハーネス自体」の 5 件。

| 提案（要約） | 判定 | 根拠（実測） |
|---|---|---|
| review のラウンド 2 以降は範囲を絞る規定を入れる | **採用** | その work の 01-server-core の review が **7 ラウンド**まで伸びた。毎ラウンド別コンテキストのレビュアーが範囲を広げ、周辺の既存欠陥（`token reset` が動かない・不正 URL でログが氾濫・M6/M7）を拾い続けた。ラウンド 7 で「前ラウンドの解消＋当該差分」に手で絞って初めて閉じた |
| `aidev debug` に「原因が特定済み」の逃げ道を作る | **採用**（`debug skip`） | 親の統合 test の差し戻し 5 回に対し、原因はすべてその場で特定・再現できていた（D96・D98・D104・D105・T16）。`decisions.md` に理由を書いて回避したが、**記録と WARN が噛み合わず**「黙って無視」と区別できなかった |
| 「沈黙する失敗」への注意を protocol に入れる | **採用** | `pnpm -s` の再帰実行は失敗しても無出力で、終了コードだけが変わる。これで誤った結論（「typecheck は通る」）を decisions.md に書き、後から訂正した |
| `metrics` の `sent_backs` の読み方を明記する | **採用・置き場所を変更** | 除外規則は `protocol.md` と付録 `protocol-analysis.md` に既にあり、本文を 3 箇所に増やすところだった。新しいのは「素で grep すると混ざる（表 6 対 素の合計 8）」だけなので、**retro が実際に読む付録**へ置いた |
| タスク点検の推奨を強める | **採用・重複を回避** | 点検はタスク 20 件に対し **100 件**を review の前に潰した（同期間の review のラウンド指摘は 78 件）。ただし既存の発火条件が既に「共有モジュール・公開 API」をモード非依存で挙げていたので、条件を 2 回定義せず**既存行に語を足した** |

**本文の在処は 1 箇所に保った**——`debug skip` の説明は `protocol-debug.md` にだけ置き、`protocol.md` と各 SKILL には
1 行も写していない。`bin/README.md` は CLI 表面の表（`lint-docs.sh` の L1 が検査する面）なので、そこだけ更新した。

## 2. README のメンテナンス

- `aidev-docs/bin/README.md` — `debug` の行に `skip` の説明（打てる条件・`--phase` の既定・記録の分け方・WARN の抑止）。
- `aidev-docs/README.md`「ループの上限」表 — `maxSendBacks` の「到達したら」に `debug skip` を追記。
  概観を更新しないと**新しい出口が概観に一度も出てこない**（レビュー指摘）。
- `test/lint-docs.sh` の `BUDGET_TOTAL` を 3485 → 3513 に更新し、内訳と根拠をコメントに残した（予算は
  「増やすなら意図的に、その数を書き換えるコミットで理由を述べる」設計）。protocol.md 本体は 611 → 603 行に**減った**
  （`sent_back` の記述を付録へ移し、追記を詰めたため）。

## 3. 実走（サブエージェント）

使い捨ての PJ（`/tmp/aidev-flowrun-skip`。ハーネスを `.claude/skills/` にコピーし fresh git init）で、
**文書だけを頼りに** requirements → coding まで通し、test を上限まで差し戻して `debug skip` を使わせた。

確認できたこと：上限到達時の促し・`--reason` 無しの拒否（exit 1）・理由つきの記録（`decisions.md` の
「デバッグ D1」と `metrics.yml` の `stage: skip, sent_backs: 3`）・`verify` の WARN の消滅・`debug status` の
`skips 1 / due no`・**4 回目の差し戻しで WARN と due が鳴り直すこと**・上限未到達の拒否。ps1 とは
メッセージ・exit code・`decisions.md`・`metrics.yml`・`debug status`・`verify` が一致（tsv は `diff` で完全一致）。
ただし**実走の時点では `--phase` を省いた経路が ps1 で一度も実行されていなかった**——この記録の後のレビューが
指摘し、曖昧なときの文面が sh と ps1 で割れていたことも分かった（どちらも修正し、パリティ検査を足した）。

**実走が見つけた欠陥（この記録の一番の収穫。いずれも修正済み）**

1. **`--phase` を省くと別の工程に記録されていた**（最も重い）。既定が `state.yml` の `current`（＝最後に承認した
   工程。多くは coding）で、上限に達するのは差し戻された工程（test / review）。しかも **`verify` の WARN 自身と
   `aidev-docs/README.md` が裸の形（`debug skip --reason`）を勧めていた**ため、**狙った WARN は消えないまま
   別の工程に記録が残り、黙って通る**。
   → 既定を「上限に達している工程」に変え、1 つに決まらなければ `--phase` を要求する。WARN の文面も
   `--phase <工程>` を含む形に直した（sh / ps1 とも。回帰テストを 4 件追加）。
2. **`bin/README.md` の条件が実装より緩かった**（「差し戻しが 1 回も無い工程では拒否」→ 実際は上限未到達なら拒否）。
   → 実装に合わせて書き直した。
3. **省ける回数に上限が無いことが未記載**だった（差し戻し → skip を繰り返せる）。
   → `protocol-debug.md` に明記（歯止めは「毎回、理由が `decisions.md` に積まれる」ことだけ、と書いた）。

**skip と無関係の既存差を 1 件検出**：短い slug の解決が sh は通るのに ps1 は完全名を要求する
（`debug status demo2` / `verify demo2`）。この改修の範囲外なので backlog に積んだ。

**実走で確認できなかったこと**：`aidev insights` / `metrics` が `stage: skip` をどう集計するか（未実行）。
tracker / remote を要する deliver 以降の経路（テスト PJ には remote が無い）。
