# テスト結果: retro で出たハーネス改善提案 5 件を aidev に適用する

## 実行したもの
- `sh docs/ClaudeCode/skills/aidev/aidev-docs/bin/test/run.sh`（pwsh 7.4.6 を入れた後）— **1111 passed / 0 failed / 0 skipped**
- 同（pwsh 不在時）— 820 passed / 0 failed / 277 skipped（skip はすべて sh⇔ps1 のパリティ。`test/setup-pwsh.sh` で
  PowerShell 7.4.6 を入れて 0 にした）
- `sh .../test/lint-docs.sh` — **23 passed / 0 failed**（CLI 表面の 4 面の同期・文書の整合・読み込み量の予算）
- `aidev smoke` — pass（3 本）
- 実物の CLI で一巡（`/tmp` のフィクスチャ）：差し戻し 3 回 → `debug skip --reason` → `verify` の WARN が消える →
  `debug status` に skips 列が出る

## 受け入れ基準ごとの判定
- AC1: pass——`aidev-60-review/SKILL.md` の手順 2 に「ラウンド 2 以降は (a) 前ラウンドの解消 と (b) 当該差分の
  must/should に絞る・周辺の既存欠陥は backlog へ」が入った。
- AC2: pass——`aidev debug skip --reason "<理由>"` が理由を `decisions.md` に、`stage: skip, sent_backs: <n>` を
  `metrics.yml` に残す。`--reason` 無しは exit 1、差し戻し 0 回の工程も exit 1。
- AC3: pass——skip のある工程では `verify` の「原因究明の記録が無い」WARN が出ない（回帰テストで確認）。
- AC4: pass——`protocol.md`「7.」に「出力の有無で成否を判断しない・パイプに通すと終了コードも消える」。
- AC5: pass——`protocol.md`「8.」に `sent_back` の数え方が 2 通りある旨（`by: unapprove` の扱い）。
- AC6: pass——`aidev-40-coding/SKILL.md` の手順 5 に「interactive でも共有モジュール・公開 API・外部に見える
  振る舞いは既定で点検」（実測値つき）。
- AC7: pass——`run.sh`（1111）・`lint-docs.sh`（23）とも通過。
- AC8: pass——`aidev.ps1` に同じ `skip`（`Dbg-Skip` / `DbgSkips`・dispatch・status の列・verify の WARN・促し）。
  `lint-docs.sh` の L1（sh dispatch / sh usage / ps1 dispatch / ps1 usage / README の表の 5 面）が通っている。

## 失敗の証跡
実装の途中で 2 回落ちた。どちらも**意図した表面の変更に既存の期待値が追いつかなかったもの**で、期待値を更新した。

```
  NG: L6 protocol.md が予算超過（611 / 608 行）
  NG: L6 実行時文書の合計が予算超過（3502 / 3485 行）
  LINT: pass=21 fail=2
```
→ 追記を詰めて protocol.md を 607 行に収め、残りは `BUDGET_TOTAL` を 3485 → 3511 に更新（内訳と根拠を
   `lint-docs.sh` のコメントに残した。予算は「増やすなら意図的に、その数を書き換えるコミットで理由を述べる」設計）。

```
  NG: debug status: 差し戻し3・デバッグ未実施・要=yes (期待を含まず: [coding	3	0	yes])
  NG: debug: 引数なしは status（表） (期待を含まず: [phase   sent_backs  debug_rounds  due])
  RESULT: pass=818 fail=2 skip=277
```
→ `debug status` に `skips` 列を足したため。既存の期待値 2 件を新しい列に更新した。

## 起動確認（smoke）
```
smoke: pass (exit 0, 3 本)
```

## 未検証の穴
- **Windows PowerShell 5.1（`powershell.exe`）での実行**。この環境には無く、pwsh 7.4.6 でのみ検証した
  （`run.sh` は Windows では 5.1 へフォールバックする作り）。
- 実際の work で `debug skip` を使った後に `retro` / `insights` がどう読むか（今回は CLI とフィクスチャまで）。

## ラウンド 2（2026-09-20・review ラウンド1 の 10 件と、実走で見つかった 3 件の修正後）

### 実行したもの
- `sh .../test/run.sh`（pwsh 7.4.6 あり）— **1123 passed / 0 failed / 0 skipped**
- `sh .../test/lint-docs.sh` — **23 passed / 0 failed**（L6 の予算は 3513 に更新。内訳はコメントに記録）
- 3 ゲートの (3) 実走（使い捨ての PJ で、文書だけを頼りに一巡）

### 失敗の証跡
実走が**仕様どおりでない挙動を 1 件**見つけた（修正済み）：

```
$ aidev debug skip --reason "R1〜R3 は毎回別の AC の取りこぼしで、いずれも失敗行を再現できている"
debug: 20260920-demo/coding skip（差し戻し 4 回）      ← test ではなく coding に記録された
verify → WARN test の差し戻しが 3 回…（残ったまま）   ← 黙って別工程の WARN だけが消えた
```

テストの修正の過程で 4 件落ちた（いずれも**意図した表面の変更に既存の期待値が追いつかなかったもの**）：

```
  NG: verify: 省く出口も示す (期待を含まず: [省くなら aidev debug skip --reason])
  NG: verify: 理由つきで省いた工程では WARN を出さない (含んではいけない: [だが原因究明の記録が無い])
  NG: debug status: skip 列を出し、due を満たす (期待を含まず: [test	3	0	1	no])
  NG: debug status: skip の後に増えたら due=yes に戻る (期待を含まず: [test	4	0	1	yes])
  RESULT: pass=1119 fail=4 skip=0
```
→ 1 件目は WARN の文面を `--phase` 付きにしたため期待値を更新。残り 3 件は、足した「`--phase` 省略」の検査を既存の
   塊の**前**に入れてフィクスチャの状態（skip と差し戻しの回数）を変えていたため。専用のフィクスチャ（`stuck3`）へ移した。

### 受け入れ基準ごとの判定
- AC1〜AC8: すべて pass（ラウンド 1 と同じ。加えて `--phase` の既定・上限未到達の拒否・工程ごとの抑止・省いた後の
  再発・ps1 との一致に回帰テストが付いた）。

### 起動確認（smoke）
```
smoke: pass (exit 0, 3 本)
```

### 未検証の穴
- Windows PowerShell 5.1（`powershell.exe`）での実行（この環境に無く、pwsh 7.4.6 でのみ検証）。
- `aidev insights` / `metrics` が `stage: skip` をどう集計するか（実走でも未実行）。

## ラウンド 3（2026-09-20・review ラウンド2 の 6 件の修正後）

### 実行したもの
- `sh .../test/run.sh`（pwsh 7.4.6 あり）— **1129 passed / 0 failed / 0 skipped**
- `sh .../test/lint-docs.sh` — 23 passed / 0 failed
- 実物の CLI で候補の選び方を確認（省ける工程が 1 つ→通る・2 つ→全部並べて拒否・0 件→「省ける工程: なし」）

### 失敗の証跡
```
  NG: パリティ: debug report / skip が書く decisions.md (got=[… ## デバッグ D3: test の原因究明を省いた（2026-09-20T03:30:40Z）…] want=[…D2 まで…])
  RESULT: pass=1128 fail=1 skip=0
```
→ テスト側の日時の正規化が `・<日時>）`（report の見出し）しか落としておらず、skip の見出しの `（<日時>）` が
   sh と ps1 の実行時刻の差でそのまま比較されていた。正規化を直して 1129 passed。

### 受け入れ基準ごとの判定
- AC1〜AC8: すべて pass。AC8（ps1 の同一表面）は、**記録経路そのもの**（decisions.md・metrics.yml・出力）と
  `--phase` 省略の経路がパリティ検査を通るようになった。

### 未検証の穴
- Windows PowerShell 5.1 での実行（この環境に無い）。`aidev insights` / `metrics` の `stage: skip` の集計。
