---
date: 2026-09-07
change: plan モードへ実際に切り替わるかを主エージェントで初めて実測し、分かった 3 件を正典に反映する
---

## 1. 文書は実態に追いついているか

### 何を測ったか

**「`aidev guard <工程>` の促し文を読んだ主エージェントが、実際に plan モードへ切り替えられるか」**。
これまで検査していたのは**促し文が出るか**だけだった——`run.sh` の 15 件は全部
`grep -c 'plan モードへ入ってから'`、つまり**文字列が出るか**。工程ごとの分岐（design/architecture/tasks で
出る、`light` で出ない、subtask の tasks で出ない、`humanGates` の部分自律で出る）は網羅していたが、
**その文字列を読んだ側が実際に `EnterPlanMode` を呼ぶか**は一度も試していなかった。

### なぜ今まで試せなかったか

- **サブエージェントには `EnterPlanMode` / `ExitPlanMode` が渡らない**。`tools` に書いても外される。
  実走 D が「このセッションには両ツールが無いので、促されても入れなかった」と報告している。
- **CLI からはモードを観測できない**。`aidev` は sh スクリプトで、エージェント側の状態を読む手段がない。

→ **主エージェント自身がテスト PJ を歩くしか経路が無い**。

### 測り方

テスト PJ（`scratchpad/planmode`）に `20260907-csv-export` を作り、requirements を承認したうえで
`aidev guard design` を打ち、出た促し文に従って歩いた。工程は `approve design` まで完走
（`coverage` の design 列 4/4）。

### 結果: 切り替わる

促し → `EnterPlanMode` → plan file → `ExitPlanMode` → 抜けてから `design.md` を清書 → `approve design`。
**散文で「入れ」と命じれば実際に切り替わる**、という前提は正しかった。

一次情報での裏取りも 1 件取れた——`ExitPlanMode` の定義が「plan の内容を引数に取らず、
**plan mode のシステムメッセージで指定された plan file から読む**」と明記している。
`protocol-autonomous.md`「書く順序」（探索 → plan file → 承認 → 抜ける → 成果物に清書）はこの通り。
plan モード中に書けるのは plan file **だけ**で、`design.md` は書けないことも実測した。

### 文書に無かったこと（3 件・すべて反映）

1. **入った先には別の手順書が待っている**。plan モードは
   「Explore サブエージェント最大3本 → Plan エージェント → レビュー → plan file → ExitPlanMode」という
   **自前の 5 段の手順**を注入し、「ターンは `AskUserQuestion` か `ExitPlanMode` でしか終われない」まで課す。
   **工程の手順と同時に 2 つ走る**。ハーネスは「plan モードへ入れ」と命じるだけで、
   入った先にこれがあることを一言も書いていなかった。
   → **工程の手順と成果物は aidev 側が正典**、注入された手順から使うのは**探索と plan file だけ**、
   plan file には**その工程の成果物の下書き**を書く、と明記した。
2. **`allowed-tools` にあっても即座に呼べないことがある**（遅延読み込みの環境ではスキーマ取得が要る）。
   → **入れないこと自体は工程の失敗ではない**（フォールバックに落ちる）と明記した。
3. **抜けた先は編集可能状態**（元のモードではない、は既知だが実測で確認）。

### 3 ゲートの射程が足りていなかった

**サブエージェント実走は第二層までしか届かない**。主エージェント専用ツールに触れる規約は
このゲートでは検証できず、実際 plan モードは**促し文の検査を 15 件持ちながら中核が未検証**だった。
`flow-runs/README.md`・`bin/README.md`・`DESIGN.md`「3.5」の 3 ゲートの説明に射程の限界を明記し、
**第三層（環境の機能）に触れる改修は自分で歩いて確かめる**を足した。

## 2. README のメンテナンス

- `aidev-docs/bin/README.md`: 3 ゲートの (3) に射程の限界。
- `aidev-docs/bin/test/flow-runs/README.md`: 同上（このゲートの定義そのものなので、より詳しく）。
- `aidev-docs/DESIGN.md`: 3 ゲートの表に射程、「2.」の plan モードの項に実測の経緯と教訓。

## 3. 実走（サブエージェント）

**このラウンドはサブエージェントでは検証できない**（上記のとおり、それが今回の発見そのもの）。
代わりに**主エージェント（このセッション）がテスト PJ を歩いた**——`aidev new` から
`approve design` まで、promptに従って `EnterPlanMode` / `ExitPlanMode` を実際に呼んでいる。

歩いた記録:

```
$ aidev guard design
OK guard design @ 20260907-csv-export
   → 忘れずに: aidev event design start
   → 有力案が複数あるなら **plan モードへ入ってから** 書く（承認を取り、解除してから成果物を書く）
      抜けた先は承認時に選んだモードで、元のモードには戻らない（protocol-autonomous.md）

（EnterPlanMode → plan file を書く → ExitPlanMode で承認 → 抜ける）

$ aidev coverage
coverage-summary: ac=4 design=4/4(100%)
$ aidev approve design
approved: design @ 20260907-csv-export
```

**残す既知の穴**: 抜けた先のモードは「承認オプションが与えるもの」なので、
**承認者が別のモードを選んだ場合の挙動**は測っていない（この実測では編集可能状態に着地した）。
`autonomous` × `humanGates` で承認者が人間のときも同様のはずだが、未検証。
