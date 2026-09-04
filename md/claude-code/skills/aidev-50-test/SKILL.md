---
name: aidev-50-test
description: ［aidev 標準工程］aidev の test（テスト/検証）工程。進行中の aidev 作業の spec の受け入れ基準を検証し、失敗時は coding へ差し戻す。「aidev test」「test 工程」と言われたとき、または前工程から案内されたときに使用する。aidev 作業の無い単発のテスト依頼では使わない。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Agent]
---

AI 開発ワークフローの **test（テスト / 検証）工程**を実行する。
実装が spec の受け入れ基準を満たすか検証する。失敗が見つかれば coding 工程へ差し戻す。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 前提

- coding 工程で実装が行われていること（対象タスクが概ねチェック済み）。

## 入力

- 実装コード。
- 対象フォルダの `spec.md`（受け入れ基準）/ `plan.md`（テスト方針）/ `tasks.md`。

## 出力

- **`test-result.md`**（work フォルダ直下）にテスト実行結果のサマリを書く（合否・件数・失敗内容・
  スキップした検証とその理由）。名前を決めておかないと work ごとに置き場が変わり、後から突き合わせられない。
  **`aidev verify` が実在を検査する**（test 承認済で無ければ FAIL）。
  必要に応じて追加したテストコード。
- 失敗時は coding への差し戻し指摘。

### test-result.md テンプレート

````markdown
# テスト結果: <タイトル>

## 実行したもの
- <コマンド> — <合格数> passed / <失敗数> failed / <skip数> skipped

## 受け入れ基準ごとの判定
- AC1: pass — <どう確かめたか>
- AC2: fail — <何が違ったか>

## 失敗の証跡
<失敗を観測したラウンドごとに、**実際に打ったコマンドとその出力をそのまま**貼る>

```
$ pytest -q tests/test_x.py
FAILED tests/test_x.py::test_roundtrip - AssertionError: ...
1 failed, 12 passed
```

## 未検証の穴（skip / 環境不足）
- <skip された検証と理由。deliver の PR 本文「既知の制約」へ引き継ぐ>
````

**失敗が1度も起きなかったラウンドでは、節を残したまま「このラウンドでは失敗が発生していない」と
1行書く**（節ごと消さない——後から見て「失敗が無かった」のか「証跡を書き忘れた」のかが区別できなくなる）。

**「失敗の証跡」は要約に置き換えない**（生の出力をそのまま貼る）。差し戻したという事実だけが残って
出力が残っていないと、**何が落ちていたのかを後から誰も再現できない**——review は「直った」ことを
確認できず、insights は再発パターンの分母を作れない。`aidev verify` は、test に `sent_back` があるのに
`test-result.md` に ``` のブロックが無ければ WARN を出す。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定する。
   `aidev guard test` で前提を検査する（exit≠0＝未充足。目視確認で代替しない）。
   - **対象が subtask（state.yml に `parent` あり）か親かを見分ける**（protocol.md「2.8」）。test の範囲が変わるので、subtask なら `protocol-subtask.md` を読む。
2. `plan.md` のテスト方針と `spec.md` の受け入れ基準に沿って検証する。
   - 自動テストがあれば実行する。無ければ受け入れ基準ごとに確認手順を実施する。
   - 必要なら不足テストを追加する。
   - **subtask の test** は slice 単独で検証可能な範囲に限定する（`protocol-subtask.md`）。
   - **親の統合 test**: 全 subtask 完了後、subtask 横断の**結合**を検証する（契約整合・結線・e2e）。
     subtask test で意図的に保留した結合の検証は、ここで確実に実施する。
3. 結果を要約する（合否、失敗したケースと原因）。
   - **環境不足で skip された検証を明示する**（未検証の穴）。テストランナーが skip 件数を出す場合は拾う
     （例: `run.sh` の `RESULT: … skip=N` / `NOTE: …`）。skip があれば「環境依存で未検証の surface」として
     要約に残し、**deliver に引き継ぐ**（PR 本文の既知の制約に載せる）。green でも skip>0 を「全数検証」と扱わない。
3.5. **失敗したラウンドがあれば、その生出力を `test-result.md` の「失敗の証跡」に貼る**
   （打ったコマンドと出力をそのまま。要約に置き換えない）。**貼るのは修正する前**——直してから
   書こうとすると出力は既に消えている。
4. 判定に応じて分岐する。
   - **全て合格** → protocol.md「3. 工程終了プロトコル」に従って終了（次工程: `review`）。
   - **失敗あり** → 失敗内容を指摘としてまとめ、`aidev event test sent_back` を記録のうえ
     coding 工程への差し戻しを提案する（protocol.md「4. 番号と順序」に基づく正当な遷移）。
     coding を**再開する際は `aidev event coding start` を記録する**（さもないと手戻り回数を取りこぼす。protocol.md「3.」「8.」）。
5. 承認は `aidev approve test passed=<合格数> failed=<失敗数>`（protocol.md「3.」「8.」）。

## light の昇格トリガ

`profile: light`（protocol.md「11.」）で**テストが落ちたら、それは「振る舞いを変えない」という
light の前提が崩れた合図**。coding へ差し戻す前に `aidev escalate` で full へ昇格する。

## 完了の目安

- spec の全受け入れ基準に対する検証結果が揃っている（`aidev coverage` の `ac` 列と付き合わせる）。
- `test-result.md` がある。差し戻したラウンドがあるなら「失敗の証跡」に**生の出力**が残っている。
- 未解決の失敗が残っていない（残る場合は coding へ戻す）。
