---
date: 2026-10-15
change: Sodashitsu の plugin アプリ「aidev」（aidev-docs/soda-plugin/）を足した。aidev の工程・CLI・規約は変えていない
---

## 1. 文書は実態に追いついているか

- 対象: `soda-plugin/README.md`（導入・操作一覧・台帳・限界）と、`aidev-docs/README.md` の案内。
- 確かめ方: 実装（`operations.mjs` の公開操作 15 本・`agents.mjs` の台帳と上限・`soda-plugin.json`）と README を突き合わせた。
  入力の上限（指示・報告 16 KiB／画面からの操作の値 8 KiB）・台帳の置き場所と上限（ログ 300 件・1 件 8 KiB）・
  `aidev status` の遅さ（この環境で実測 12〜13 秒）・応答待ち（30 秒）に対する約 25 秒の `pending` は、実装の定数と README が一致している。
- 見つかった食い違い: 設計メモの `agent prompt --expect` の例（`paneId`・`name` だけ）が、実際の sodactl の検証
  （`paneId`・`instanceId`・`tabId`・`projectDir`・`name` の 5 項目がすべて必須）と合わなかった。実装を実物に合わせた
  （送る前に `agent get` で `instanceId` を取る）。aidev の既存の文書（`protocol*.md`・`bin/README.md`・`DESIGN.md`）には
  このプラグインに触れる記述が無く、食い違いは無い。

## 2. README のメンテナンス

- `aidev-docs/README.md`: 「ファイル構成」に `soda-plugin/` の 1 行と、節「Sodashitsu のアプリ（任意）」を足した。
- `bin/README.md`: 不要。aidev CLI のコマンド・終了コード・config キーは変えていない
  （プラグインは `aidev status --all --format tsv` を読むだけで、`.aidev/` には書かない）。

## 3. 実走（サブエージェント）

- **サブエージェントでの aidev フローの実走は行っていない。** 変えたのは aidev の工程・CLI・規約ではなく、別の層
  （Sodashitsu のアプリ）で、`.aidev/` は読むだけのため、「書いてある規約が実際に発火するか」を歩く対象が無い。
- 代わりの検証（規約の実走ではない）: `node --test` 65 件（偽の sodactl・偽のホスト・一時 PJ）／`sodactl plugin pack` の通過／
  生成する `sodactl` の全コマンドを実物の引数パーサに通して受理を確認／ヘッドレス Chrome で画面スクリプトを実 DOM で動かして確認／
  実際の PJ の `.aidev/`（152 作業）を `aidev status` で読んだ時間の実測／`codex --help` で `-C`・`-m`・`-s`・`-a`・`resume` の引数を確認。
- **未実施**: 実際の Sodashitsu サーバでの導入・承認・Claude Code／Codex の起動（監督・担当・再開・グラフの線・Codex の会話 ID の取り込み）。
  ライブのサーバに導入してエージェントを起こす操作になるため、この作業では行っていない。
