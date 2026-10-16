---
date: 2026-10-15
change: Sodashitsu の plugin アプリ「aidev」（aidev-docs/soda-plugin/）を足した。あわせて、bin/aidev・aidev.ps1 の harness_rev から soda-plugin を除いた。aidev の工程・規約は変えていない
---

## 1. 文書は実態に追いついているか

- 対象: `soda-plugin/README.md`（導入・使い方・操作一覧・台帳・安全・限界）と、`aidev-docs/README.md`・`bin/README.md` の案内。
- 確かめ方: 実装（`operations.mjs` の公開操作 19 本・`agents.mjs` の台帳と上限・`soda-plugin.json`）と README を突き合わせた。
  入力の上限（指示・報告 16 KiB／画面からの操作の値 8 KiB／結果 200 KiB で切る）・台帳の置き場所と上限（ログ 300 件・1 件 8 KiB・
  以前の会話 5 件）・`aidev status` の遅さ（この環境で実測 12〜13 秒）・応答待ち（30 秒）に対する約 25 秒の `pending` は、
  実装の定数と README が一致している。
- 見つかった食い違い（直した）:
  - 設計メモの `agent prompt --expect` の例（`paneId`・`name` だけ）が、実際の sodactl の検証（5 項目すべて必須）と合わなかった
    → 送る前に `agent get` で `instanceId` を取る実装にした。
  - `git ls-tree <tree-sha>` を `git -C <サブディレクトリ>` で呼ぶと prefix で絞られて空になる
    → `harness_rev` の組み直しで `--full-tree` を付けた（実装の途中で、テストが検出した）。
- aidev の既存の文書（`protocol*.md`・`DESIGN.md`）にはこのプラグインに触れる記述が無く、食い違いは無い。

## 2. README のメンテナンス

- `aidev-docs/README.md`: 「ファイル構成」に `soda-plugin/` の 1 行と、節「Sodashitsu のアプリ（任意）」を足した。
- `bin/README.md`: `harness_rev` が `aidev-docs/soda-plugin` を版に入れないことを 1 段落足した（CLI のコマンド・終了コード・
  config キーは変えていない）。

## 3. 実走（サブエージェント）

- **サブエージェントでの aidev フローの実走は行っていない。** 変えたのは aidev の工程・規約ではなく、別の層
  （Sodashitsu のアプリ）で、`.aidev/` は読むだけのため、「書いてある規約が実際に発火するか」を歩く対象が無い。
  `harness_rev` の変更だけは CLI の挙動なので、テストで検証した（下）。
- 検証（規約の実走ではない）:
  - `node --test` 100 件（偽の sodactl・偽のホスト・一時 PJ）／`sodactl plugin pack` の通過。
  - `bin/test/run.sh`: **pwsh 7.4.6 を入れて全体を実行**し `pass=1137 fail=0 skip=0`（変更前は pwsh 無しで `pass=830 skip=285`）。
  - fix-03: harness_rev の soda-plugin 除外を sh・ps1 とも git mktree でなく一時 index（write-tree）で組む。再度 `run.sh` を実行して `pass=1137 fail=0 skip=0`。
  - fix-04: winps の harness_rev 診断（AIDEV_DEBUG_HARNESS_REV）を追加。挙動は変えていない（診断の経路のみ）。
  - fix-05: ps1 の harness_rev の一時 index・hash-object 入力を .git の下に置く（無ければ GetTempPath 等へ）。`run.sh` は `pass=1137 fail=0 skip=0`。
  - fix-06: 拡張の ready の取りこぼし（display.set の応答より先に届いた ready を、応答後の消去で捨てていた）を直し、応答を止める試験を追加。`node --test` は 101 件通過（30 回の繰り返しも通過）。
    `harness_rev` の除外は、sh・ps1 のパリティを含む 8 件（足しても・中を変えても版が動かない／外の変更では動く／ps1 も同じ版／
    `git mktree`・tree の読み取りが失敗したら両実装とも unknown）を足した。
  - more-agents: 監督・担当の種類に Copilot CLI・Bob Shell を足し、Sodashitsu の設定「エージェント連携」で導入済みのものだけに制限した
    （`soda-plugin/` の `agents.mjs`・`operations.mjs`・`ui.mjs`・README。`.aidev/` の読み書きと aidev の規約は変えていない）。
    `node --test` は 110 件通過。`copilot --help` で `--model`・`--resume` を確認。Bob の実機・実サーバでの起動は未実施。
  - 生成する `sodactl` の全コマンドを実物の引数パーサに通して受理を確認／ヘッドレス Chrome で画面スクリプトを実 DOM で動かして確認／
    実際の PJ の `.aidev/`（152 作業）を `aidev status` で読んだ時間の実測／`codex --help` で `-C`・`-m`・`-s`・`-a`・`resume` を確認。
- **未実施**: 実際の Sodashitsu サーバでの導入・承認・Claude Code／Codex の起動（監督・担当・再開・グラフの線・関連エージェント・
  完了時の終了・Codex の会話 ID の取り込み）。ライブのサーバに導入してエージェントを起こす操作になるため、この作業では行っていない
  （試験用サーバでの実機確認は、別の作業者の報告 `fix-01` にある）。
