---
name: aidev-30-plan
description: ［aidev 標準工程］aidev の plan（計画/作業分解）工程。進行中の aidev 作業の spec.md から plan.md と tasks.md を作る。「aidev plan」「plan 工程」と言われたとき、または前工程から案内されたときに使用する。aidev 作業の無い単発の計画作成では使わない。
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion]
---

AI 開発ワークフローの **plan（計画 / 作業分解）工程**を実行する。
spec を実装可能な作業単位に分解し、`plan.md`（方針・順序）と `tasks.md`（チェックリスト）を作る。
`tasks.md` のチェックボックスが、以降の進捗の単一の真実となる。

**開始前に共通プロトコル `../aidev-00-start/protocol.md` を読み、その規約に従うこと。**

## 前提

- `spec.md` が存在すること。無ければ実行を中止し、spec 工程を促す。
- **`profile: light` の work ではこの工程を単独で起動しない**（protocol.md「11.」）。light では
  `plan.md` / `tasks.md` は requirement の 1 ゲートで既に書かれている。起動されたら実行を中止し、
  `coding` へ進むか、`aidev escalate` で full に昇格してから plan を踏み直すかを確認する。
  なお **light の work は subtask 分割しない**（手順3の split 判定は「大規模で漸進レビューの価値がある」
  ケースを対象とし、light の前提と正反対）。
- `design.md` があれば**それも前提に含める**（protocol.md「7.」: plan の前提は「spec.md（design があればそれも）」）。
  design 工程を挟んだ場合、その構造設計を踏まえて分解する。

## 入力

- 対象フォルダの `spec.md` と、あれば `design.md`（必要に応じて `requirement.md`）。
- あれば `research.md`。特に「実装アンカー」は `tasks.md` の `対象` 欄の出所になる。

## 出力

対象フォルダに `plan.md` と `tasks.md` を生成する。

## 手順

1. protocol.md「1. 対象作業の特定」に従い対象フォルダを確定。`aidev guard plan` で前提を検査する
   （exit≠0＝未充足。目視確認で代替しない）。`spec.md` を確認
   （`design.md` / `research.md` があればそれも読み込む）。
   - **この work が subtask か親かを見分ける**（state.yml に `parent` があれば subtask）。
     **subtask の plan は split 判定（手順3）と subtask 生成（手順4）を行わない**。手順5の「scope 凍結の
     tasks.md 分解」だけを実施し、**再分割（subtask の下に subtask を作る）は禁止**（CLI も多段ネストを弾く）。
     scope は親 plan が確定済み——子 plan は自分の slice の分解と兄弟 subtask への dependsOn 順序付けに限定する。
2. `spec.md`（と `design.md` があればその構造設計）を読み、実装手順・依存関係・リスクを整理して `plan.md` を書く。
3. **（親 work のみ）split 判定（subtask 分割の要否）**: `aidev-docs/DESIGN.md`「5.」の3層決定木に従い、この work を
   subtask へ割るか判断する。判定の discriminator は単一原則 **「そのピースは単独で検証・デリバリ可能か」**。
   - **単独で検証・デリバリ可能（低結合）** → そもそも別 work/PR の候補（本 work では割らず、必要なら
     `aidev-util-propose` で別 work 化を提案）。**振る舞い不変な変更（refactor 等）はここ**＝subtask に落とさない。
   - **相互依存で共同検証のみ可（高結合）かつ大規模で漸進レビューの価値がある** → **subtask 分割**（下記4へ）。
   - **不可分** → 分割せず単一 tasks.md ＋ walkthrough のコミット構成（通常の plan。5へ）。
   - **判定の提示**: interactive は `AskUserQuestion` で分割可否・分割案をユーザーに委譲する。
     autonomous は自律判定する（明確に独立な seam がある時だけ分割。迷えば分けない）。
     小〜中規模で 1 PR に収まるなら subtask 化しない（過剰分割の禁止）。
4. **（subtask 分割する場合のみ）**: 親 plan は「メタ plan」として割れ目（subslug 境界）と producer→consumer の
   順序を `plan.md` に定義し、各 subtask を `aidev new <NN>-<subslug> --parent <親> [--depends 兄弟名]` で作る
   （protocol.md「2.8」＋ `protocol-subtask.md` を読む）。**各 subtask の詳細 tasks.md は、その subtask の plan 工程で作る**（親 plan では作らない）。
   - **子 plan の scope 凍結**: subtask の plan は **scope を再決定してはならない**（割れ目は親 plan が確定済み）。
     子 plan は自分の slice の tasks.md 分解と、兄弟 subtask への dependsOn 順序付けに限定する。
   - 子は親の `spec.md`/`design.md` を継承する（guard が親配下を自動 fallback。子に複製しない）。
5. **（分割しない場合）** spec を独立して検証可能な小さなタスクに分解し、`tasks.md` をチェックリストで作る。
   - 各タスクは coding 工程で 1 つずつ消化できる粒度にする。
   - **各タスクに `対象` を添える**。`research.md` の「実装アンカー」や `design.md` で位置が特定できている場合、
     変更・参照の起点を `file:line` またはシンボル名で書き、根拠の項目 ID（`research A1` 等）を併記する。
     coding が探索をやり直さずに済み、差し戻し・再開時の再探索も防げる。
   - **特定できていないタスクは `対象: 未特定` と明示する**（空欄にすると「調査済みで対象なし」と誤読され、
     coding が必要な探索を省いてしまう）。アンカーはあくまで**探索の省略**であり、読解の省略ではない。
   - **各タスクに `依存:` を添える**（依存が無ければ `依存: なし`）。値は**同じ tasks.md 内のタスク ID** を
     カンマ区切りで書く（例 `依存: T1, T2`）。本文中に「（依存: T1）」と混ぜて書かない——
     **1か所に構造化して書く**ことで、coding が「いま着手できるタスクの集合」を機械的に判定できる。
   - **ウェーブ（並行できる塊）は書かない**。`依存:` から導出できる（ラベルの併記は二重管理。
     `aidev-docs/DESIGN.md`「3.」）。
     依存が複雑なら mermaid で図示してよいが（protocol.md「9.」）、**図は説明であって正典ではない**——
     正典は `依存:` 行。
   - **`依存:` と `dependsOn` は別物**。`依存:` は tasks.md 内の**タスク間**、`state.yml` の `dependsOn` は
     **work / subtask 間**（protocol.md「2.7」「2.8」）。混ぜて書かない。
   - **各タスクに `AC:` を添える**（対応する受け入れ基準が無ければ `AC: なし`）。値は `requirement.md` の
     `完了条件 (受け入れ基準)`（と「相互作用の受け入れ基準」）の **ID** をカンマ区切りで書く（例 `AC: AC1, AC-I1`）。
     「無い」と書ける綴りは **`なし` / `none` / `None` / `NONE` / `-`** のいずれか（`無し` や `N/A` は値として
     扱われ、未定義参照になる）。
     **AC の本文は書き写さない**——正典は `requirement.md` の1箇所で、ここは ID で参照するだけ。
     これで「どの受け入れ基準がタスクに落ちていないか」を `aidev coverage` が機械的に出せる
     （spec の全範囲が落ちているかの確認を目視に委ねない）。**空欄にしない**——`対象: 未特定` と同じで、
     書き忘れと「対応する AC が無い」を区別できなくなる。
6. **`aidev coverage --strict` を通す**（exit≠0＝未解消の gap あり。目視確認で代替しない）。
   落ちるのは 2 種類で、どちらも**この工程で直す**。
   - **struct**（未定義の `AC` / 未定義のタスクを指す `依存` / `依存` の循環）: 書き間違いなので直す。
   - **cover**（`AC:` 行の書き忘れ / タスクに落ちていない `AC`）: 分解の漏れなので、次のどれかで閉じる。
     - **coding で消化する** → タスクを足す。
     - **coding ではなく test / deliver で消化する**（「README の例を実際に実行して確かめる」等）
       → **その旨を明記したタスクを立てる**。`tasks.md` は coding のチェックリストなので、
       coding の承認時に未チェックで残る前提で、`decisions.md` に「消化は test 工程」と1行残す
       （`aidev-40-coding` の完了の目安と形の上で食い違うため、判断の証跡が要る）。
     - **この work では扱わない** → `requirement.md` の `完了条件` から**行ごと外し**、
       `スコープ / 対象外` に理由つきで書く。**移すときはチェックボックスを外すこと**——
       `- [ ] AC3: …` の形のまま移すと、節が変わっても受け入れ基準として数え続ける。
     タスクを持たない `AC` を `完了条件` に残したまま承認しない——それは
     「完了条件を満たさずに完了できる」状態。
7. protocol.md「3. 工程終了プロトコル」に従って終了する（次工程: 分割時は最初の subtask の `plan`、
   非分割時は `coding`）。承認は
   `aidev approve plan tasks_planned=<tasks.md のタスク総数> tasks_anchored=<対象が特定済みのタスク数>`
   （protocol.md「3.」「8.」）。`tasks_anchored` は `対象: 未特定` を除いた数——
   coding の `unplanned_lookups` と対になり、アンカー的中率の分母になる。
   **被覆メトリクス（`ac_total` / `ac_covered` / `tasks_no_ac` / `tasks_ac_none`）は CLI が自動で刻む**
   ので手で渡さない（protocol.md「8.」）。ここで刻まれた値が、review 時の値と対になって
   「spec と実装の乖離（`ac_drift`）」の基準点になる。

## plan.md テンプレート

```markdown
# 計画: <タイトル>

## 実装方針
<spec をどの順序で・どう組み立てるか>

## 作業順序と依存関係
<依存では表せない順序の理由だけを書く。無ければ「tasks.md の `依存:` に従う」とだけ書く>
- <例: 不確実な箇所を先に試す。ここで見立てが外れたら分解をやり直す>
- <例（subtask 分割時）: `01-be` が `02-fe` の producer。API の形が固まるまで `02-fe` は着手しない>

## リスク / 留意点
- <想定リスクと対応>

## テスト方針
- <test 工程で何をどう確認するか>
```

`plan.md` の「作業順序と依存関係」は**方針の説明**。タスク間の依存の正典は `tasks.md` の `依存:` 行で、
coding はそちらを読む（同じ依存を2箇所に書き分けない）。

## tasks.md テンプレート

チェックボックスは**行頭の `- [ ]`** で書く（進捗の単一の真実）。
`対象` / `依存` / `AC` は次行以降にインデントして添える（チェック行の書式を壊さない）。
この3つは `aidev coverage` が読む**構造化された欄**なので、本文中に混ぜて書かない。

**ID の文法**: タスクは `T<数字>`（`T1` `T10`。以降に `-` や英数を足した `T1-1` も別 ID として扱う）。
`AC` は `AC<数字>`（`AC1`）か `AC-<英数>`（`AC-I1`）。**`AC` の直後に英字が続くものは受け入れ基準ではない**
（`ACL` `ACCESS` で始まる普通のチェックリスト行を基準と誤認しないため）。

```markdown
# タスク: <タイトル>

- [ ] T1: <タスク内容>
      対象: `path/to/file.ts:120` `symbolName` / 根拠: research A1
      依存: なし
      AC: AC1, AC2
- [ ] T2: <タスク内容>
      対象: 未特定
      依存: T1
      AC: AC2
- [ ] T3: <タスク内容>
      対象: `path/to/other.ts` （新規作成）
      依存: なし
      AC: なし
```

上の例では T1 と T3 が依存を持たないので、coding は**この2つを同時に着手できる**（同一ウェーブ）。
実際に並行させるかは `対象` が衝突しないかで決まる（`aidev-40-coding` の手順2）。

## 完了の目安

- spec の全範囲が tasks に漏れなく落ちている。
- 各タスクが「1 タスク = 1 つの検証可能な変更」になっている。
- 各タスクに `対象` がある（特定できないものは `未特定` と明示されている）。
- 各タスクに `依存:` がある（無いものは `なし` と明示されている）。**存在しないタスク ID を指していない**、
  **循環していない**（A→B→A）。ウェーブラベルを手で書いていない。
- 各タスクに `AC:` がある（対応が無いものは `なし` と明示されている）。
- **`aidev coverage --strict` が exit 0**（gap が残っていない）。
  なお **`spec` 列は gap を生まない**（`spec.md` の対応漏れは exit code を動かさない）。
  `spec` が `no` の `AC` は spec 工程の書き漏れなので、**表を目で見て拾う**。
