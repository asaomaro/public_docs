# 要件: retro で出たハーネス改善提案 5 件を aidev に適用する

## 背景 / 課題

別リポジトリ（`asaomaro/web-tn-multiplexer`）で、新規プロジェクトを 1 work として最後まで回した
（要件 → 着地。341 ファイル・52,418 行・リードタイム約 47 時間・再開 77 回）。その retro
（`/workspaces/web-tn-multiplexer/.aidev/works/20260918-web-terminal-multiplexer/retro.md`）で、
ハーネス（aidev）自体の不備が 5 件挙がった。いずれも**実際にその work で時間を失った**箇所で、
提案のまま置くと次の work でも同じ形で踏む。

1. **統合 review のラウンドが収束しない**。`aidev-60-review` は「差分を点検する」としか書いておらず、
   ラウンドを重ねるたびに（別コンテキストの）レビュアーが範囲を広げ、周辺の**以前からある**欠陥を拾い続けた。
   実測：01-server-core の review が 7 ラウンド。ラウンド 7 で「前ラウンドの解消 ＋ 当該差分の must/should」に
   手で絞って初めて収束した。
2. **`aidev debug` の発火条件に逃げ道が無い**。差し戻しが `maxSendBacks` を超えると `verify` が WARN を出し続けるが、
   差し戻しの原因が毎回違い、その場で特定・再現できている場合は委譲の価値が無い。実測：親の統合 test の
   差し戻し 5 回に対し、原因はすべて特定済み（D96・D98・D104・D105・T16）。`decisions.md` に理由を書いて
   回避したが、**記録と WARN が噛み合っていない**（「黙って無視」と「理由を書いて省く」が区別できない）。
3. **「沈黙する失敗」への注意が protocol に無い**。`pnpm -s` の再帰実行は失敗しても何も出力せず、終了コードだけが
   変わる。これで誤った結論を decisions.md に書き、後で訂正した（wtm の D96）。
4. **`metrics` の `sent_backs` の読み方が書かれていない**。`unapprove` が各工程に `by: unapprove` の記録を残すため、
   per-phase の `sent_back` は「差し戻しの回数」より大きく出る（実測：親の表 6 に対し per-phase の合計 8）。
   retro で誤読しやすい。
5. **タスク点検（`taskcheck`）の推奨が弱い**。実測：点検が review に届く前に 100 件を潰した（点検したタスク 20 件）。
   同じ期間の review のラウンド指摘は 78 件。`aidev-40-coding` の手順 5 は `mode: autonomous` を全タスク必須とする一方、
   `interactive` では条件付きで、**効果の大きさが推奨に反映されていない**。

## 目的 / ゴール

- 次の work で、**統合 review が有限のラウンドで収束する**（範囲の絞り方がハーネスに書かれている）。
- **原因が特定済みの差し戻しを、理由を記録したうえで WARN 無しに閉じられる**（記録の無い放置とは区別される）。
- 「沈黙する失敗」「`sent_backs` の読み方」を**次に読む人が protocol で知れる**。
- タスク点検の推奨が、**実測の効果に見合う強さ**になっている。

## ユーザーストーリー

- US1: **aidev を回す AI** として、review のラウンド 2 以降で見る範囲を知りたい。なぜなら、範囲が書かれていないと
  毎ラウンド全体を見直して周辺の既存欠陥を拾い、いつまでも収束しないから。（受け入れ: AC1）
- US2: **aidev を回す AI** として、原因が特定済みの差し戻しを理由つきで閉じたい。なぜなら、委譲の価値が無い場面でも
  WARN が残り続け、記録を読む人が「手順を飛ばした」のか「理由があって省いた」のか区別できないから。（受け入れ: AC2, AC3）
- US3: **ハーネスの利用者（人間・AI）** として、検査コマンドの結果を取り違えずに読みたい。なぜなら、出力が無いことを
  成功と読む・`sent_backs` を差し戻し回数と読むと、誤った結論が記録に残るから。（受け入れ: AC4, AC5）
- US4: **work を回す AI** として、タスク点検をいつ行うかの推奨を知りたい。なぜなら、効果が大きいのに条件が弱く、
  interactive では行われないまま review に流れるから。（受け入れ: AC6）

## スコープ

### 対象
- `aidev-60-review/SKILL.md`（ラウンド 2 以降の範囲）
- `aidev-40-coding/SKILL.md`（タスク点検の推奨）
- `aidev-00-start/protocol.md`（沈黙する失敗・`sent_backs` の読み方）
- `aidev-00-start/protocol-debug.md`（`debug skip` の位置づけ）
- `aidev-docs/bin/aidev`（`debug skip` の実装）・`aidev-docs/bin/aidev.ps1`（同じ表面）・`aidev-docs/bin/README.md`（表）
- `aidev-docs/bin/test/`（回帰テスト）

### 対象外
- retro の「製品 / コード」「PJ プロセス / 規約」カテゴリ（wtm 側の backlog・条項として既に起票済み）。
- `maxSendBacks` / `maxDebugRounds` の既定値の変更。
- 既存の work の記録の書き換え。

## 機能要件

- `aidev debug skip --reason "<理由>"`：その工程の差し戻しについて、**原因究明の委譲を省いた事実と理由を記録する**。
  - 理由は必須（`debug report` の `--root-cause` と同じく、書けないなら記録させない）。
  - 散文（理由）は `decisions.md` へ、列挙値は `metrics.yml` へ（`debug report` と同じ分け方）。
  - `aidev verify` の「原因究明の記録が無い」WARN は、その工程に skip の記録があれば出さない。
  - `aidev debug status` で skip が見える。
- 文書 4 点の追記（上記スコープ）。

## 非機能要件 / 制約

- **sh と ps1 の表面をそろえる**（`test/lint-docs.sh` が CLI 表面の食い違いを検査する）。
- 既存の記録（`metrics.yml`）の形式を壊さない。skip が無い work の挙動は変わらない。
- 文書の増加は最小限にする（`lint-docs.sh` が読み込み量を検査する）。

## 完了条件 (受け入れ基準)

- [ ] AC1: `aidev-60-review/SKILL.md` に、review のラウンド 2 以降で見る範囲（前ラウンドの指摘の解消 ＋ 当該差分の
      must/should。範囲外の発見は backlog へ）が書かれている。
- [ ] AC2: `aidev debug skip --reason "<理由>"` が、理由を `decisions.md` に、記録を `metrics.yml` に残す。理由が無ければ
      非 0 で終わる。
- [ ] AC3: skip を記録した工程について `aidev verify` が「原因究明の記録が無い」WARN を出さない（skip が無ければ従来どおり出す）。
- [ ] AC4: `protocol.md` に「出力の有無で成否を判断しない・終了コードを別に確認する」が書かれている。
- [ ] AC5: `protocol.md`（または metrics の説明）に、per-phase の `sent_back` が `unapprove` を含むことが書かれている。
- [ ] AC6: `aidev-40-coding/SKILL.md` のタスク点検の条件に、`interactive` でも「共有モジュール・外部に見える振る舞い」に
      触るタスクは既定で点検する旨が入っている。
- [ ] AC7: `sh test/run.sh` と `sh test/lint-docs.sh` が通る（sh / ps1 の表面の食い違い・文書の整合を含む）。
- [ ] AC8: `aidev debug skip` が ps1 でも同じ表面で使える（`--help` / README の表を含む）。

## 未確定事項 / 確認したいこと
- 無し（retro の提案が具体的で、変更箇所も特定済み）。
