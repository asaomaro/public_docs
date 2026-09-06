---
name: aidev-50-test
description: ［aidev 標準工程］aidev の test（テスト/検証）工程。進行中の aidev 作業の design の受け入れ基準を検証し、失敗時は coding へ差し戻す。「aidev test」「test 工程」と言われたとき、または前工程から案内されたときに使用する。aidev 作業の無い単発のテスト依頼では使わない。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Agent]
---

AI 開発ワークフローの **test（テスト / 検証）工程**を実行する。
実装が design の受け入れ基準を満たすか検証する。失敗が見つかれば coding 工程へ差し戻す。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 前提

- coding 工程で実装が行われていること（対象タスクが概ねチェック済み）。

## 入力

- 実装コード。
- 対象フォルダの `design.md`（受け入れ基準）/ `tasks.md`（テスト方針）/ `tasks.md`。

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

## 起動確認（smoke）
<`aidev smoke` の出力をそのまま貼る。GO / NO-GO の根拠>

```
$ python3 -m notes --version
notes 0.1.0
smoke: pass (exit 0)
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
   `aidev guard test` で前提を検査し、`aidev event test start` を記録する
   （exit≠0＝未充足。目視確認で代替しない。start が無いと所要時間も手戻りも導出できない）。
   - **対象が subtask（state.yml に `parent` あり）か親かを見分ける**（protocol.md「2.8」）。test の範囲が変わるので、subtask なら `protocol-subtask.md` を読む。
2. `tasks.md` のテスト方針と `design.md` の受け入れ基準に沿って検証する。
   - 自動テストがあれば実行する。無ければ受け入れ基準ごとに確認手順を実施する。
   - 必要なら不足テストを追加する。
   - **subtask の test** は slice 単独で検証可能な範囲に限定する（`protocol-subtask.md`）。
   - **親の統合 test**: 全 subtask 完了後、subtask 横断の**結合**を検証する（契約整合・結線・e2e）。
     subtask test で意図的に保留した結合の検証は、ここで確実に実施する。
3. 結果を要約する（合否、失敗したケースと原因）。
   - **環境不足で skip された検証を明示する**（未検証の穴）。テストランナーが skip 件数を出す場合は拾う
     （例: `run.sh` の `RESULT: … skip=N` / `NOTE: …`）。skip があれば「環境依存で未検証の surface」として
     要約に残し、**deliver に引き継ぐ**（PR 本文の既知の制約に載せる）。green でも skip>0 を「全数検証」と扱わない。
3.2. **起動確認（smoke）を通す**: `aidev smoke` を実行する。
   **「テストが全部通ったこと」は着地の根拠として足りない**——単体テストが緑でも、配線が壊れていて
   成果物が起動しないことは普通に起きる。見るのは「**ビルドした成果物が最初の使える状態まで到達するか**」。
   - **exit 0** → 生出力を `test-result.md` の「起動確認」節にそのまま貼る。
   - **この work が新しい入口（サブコマンド・オプション）を足したなら、`smokeCommands` に
     1 行足すか、足さない理由を `test-result.md` に書く**。起動確認は成果物と一緒に育てるもので、
     据え置くと「足した表面を一度も起動しないまま `smoke: pass`」になる（`doctor` が
     `smokeStaleAfter` 本の着地で催促するが、気づくのはここが最初）。
     単数の `smokeCommand:` しか無い PJ では**複数形へ移してから足す**（`smokeCommands:` の
     ブロックリストにして、元の 1 本を先頭行に置く。単数キーは残さない）。この変更は
     PJ 全体の設定なので、下の「留意点」の衝突面に加わる。
   - **exit 4（失敗）** → テストが全部緑でも**合格にしない**。手順4の「失敗あり」に合流して coding へ差し戻す。
   - **exit 2（`smokeCommand` 未設定）** → PJ の `.aidev/config.yml` に設定する。
     「最初の使える状態まで到達する」ことを確かめる**終了するコマンド**を書く
     （常駐するサーバなら health check を叩いて終わる形にする。起動しっぱなしにしない）。
     起動確認の対象が無い PJ（純粋なライブラリ等）は `smokeCommand: none` と**明示**する。
     どちらもせずに先へ進まない——**検証していないことは「合格」ではない**。
3.5. **失敗したラウンドがあれば、その生出力を `test-result.md` の「失敗の証跡」に貼る**
   （**修正する前に**。直してから書こうとすると出力は既に消えている）。
4. 判定に応じて分岐する。
   - **全て合格** → protocol.md「3. 工程終了プロトコル」に従って終了（次工程: `review`）。
   - **失敗あり** → 失敗内容を指摘としてまとめ、`aidev event test sent_back` を記録のうえ
     coding 工程への差し戻しを提案する（protocol.md「4. 番号と順序」に基づく正当な遷移）。
     coding を**再開する際は `aidev event coding start` を記録する**（さもないと手戻り回数を取りこぼす。protocol.md「3.」「8.」）。
     - **同じ工程を `maxSendBacks`（既定 3）回差し戻したら、そこで方向を変える**。`aidev event` が
       `aidev debug start` を促すので、**まっさらなコンテキスト**に原因究明だけを委譲する
       （`protocol-debug.md`）。
5. 承認は `aidev approve test passed=<合格数> failed=<失敗数>`（protocol.md「3.」「8.」）。

## light の昇格トリガ

`profile: light`（protocol.md「11.」）で**テストが落ちたら、それは「振る舞いを変えない」という
light の前提が崩れた合図**。coding へ差し戻す前に `aidev escalate` で full へ昇格する。

## 完了の目安

- design の全受け入れ基準に対する検証結果が揃っている（`aidev coverage` の `ac` 列と付き合わせる）。
- `test-result.md` がある。差し戻したラウンドがあるなら「失敗の証跡」に**生の出力**が残っている。
- **`aidev smoke` が pass（または `none` で対象外と宣言済み）**。テストが緑なだけで合格にしていない。
- **主張が証拠の範囲を超えていない**（protocol.md「7.」）。検証できなかった範囲は「未検証の穴」に残す。
- 未解決の失敗が残っていない（残る場合は coding へ戻す）。
