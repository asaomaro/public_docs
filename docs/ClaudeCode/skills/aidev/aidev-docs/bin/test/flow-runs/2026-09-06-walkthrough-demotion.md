---
date: 2026-09-06
change: walkthrough を工程から外して review の任意成果物にし、改名ラウンドの積み残しと実走が見つけた must 3 件を潰す
---

## 1. 文書は実態に追いついているか

### 工程変更（walkthrough の降格）

`aidev-65-walkthrough/` を削除し、`PHASES` は **10 工程**になった。判定基準は
**「作業段階か、成果物の形式か」**——walkthrough がやっていたのは「差分の読み方を説明する md を
書く」だけで、前工程と後工程の間に新しい状態を作らない。工程の定義（成果物と承認者を持つ作業
単位）のうち**承認者の側が空**で、遷移ゲートは「やる/やらない」を尋ねるためだけに 1 つ消えていた。

**同じ判断が 3 箇所に散っていた**（`protocol.md`「4.5」に条件 / `aidev-60-review` に推奨判定 /
工程 skill 自身に検知ロジック）。分類 A の温床で、実際にこの型で 2 回食い違っている。正典を
`aidev-60-review`「レビュー補助」1 箇所に畳んだ。**`walkthrough.md` は成果物として残る**
（deliver が PR 本文へ要約する経路もそのまま）——消したのは工程であって成果物ではない。

### 統合レビュー工程は作らなかった

対話で「タスクを分割して各々レビューした後の統合レビュー」を x5 に足すか検討し、**足さないと
決めた**。分割 work では**親の `test` が統合テスト、親の `review` が統合レビュー**で、
`guard test` が「全 subtask が review 承認済み」を機械で要求している（`protocol-subtask.md`）。
足りないのは工程ではなく**分量**（統合固有の観点が箇条書き 1 行）だったので、工程数・guard・
dispatch・doccheck・verify・metrics の 6 面を増やす選択は採らない。**`test` だけ工程を増やさず
`review` だけ増やすと対称性が壊れる**、という点も決め手になった。代わりに実走 B の指摘を受けて
統合 review の観点を「何を開くか」まで書き下した（下記）。

### 改名ラウンドの積み残し

| 直したもの | 何が起きていたか |
|---|---|
| lint **L10** の重複検出 | `grep -E` の後方参照 `\1` は POSIX ERE の外で、**黙って何にもマッチしない**。導入時の自己確認が素通りしていた。明示的な選択肢に直した直後に本物の取りこぼしを 1 件検出 |
| `spec_conflict` | debug 分類だけ退役語が残っていた → `upstream_conflict`（戻す先は requirements と design の**両方**なので `design_conflict` にはしない） |
| 裸の `plan` 4 箇所 | `\bplan\.md\b` しか見ておらず、「plan モード」の誤検知を避けるため裸の `plan` を意図的に外していた。区切り記号と助詞の枝を足して検出 |
| 他 SDD の対応表 | 一括置換が `Spec Kit の spec.md` を `design.md` に化かしていた（Spec Kit は spec.md → plan.md → tasks.md、Kiro の design.md は aidev の design＋architecture） |
| light の「N つとも作る」 | 4→3 に減ったのに数詞だけが 6 箇所に残り、`aidev-10-requirements` は**同一ファイル内で 3 と 4 に割れて**いた → lint **L12** |

### 実走が見つけた must（3 件）

1. **`aidev-95-retro` にだけ `guard` / `event start` が無い**（実走 A）。書いてあるとおりに回すと
   `verify --strict` が exit 5、しかも ts は捏造禁止なので**戻れない**。10 工程でこの skill だけ
   → lint **L11**（全工程 SKILL に両方あるか）。
2. **`new <NN> --parent` が生成時にカーソルを子へ移す**（実走 B）。`aidev-30-tasks` の手順どおり
   打つと**親の `approve tasks` が子に落ちる**。`unapprove` しても metrics の `approved` は追記式
   なので消えず、その子は以後ずっと `verify --strict` が exit 5 → 親 tasks が承認されるまで
   カーソルは親に置き、親の `approve tasks` が活性の subtask へ進める。
3. **親の統合 test が落ちたときの差し戻し先が無い**（実走 B）。親に `coding` は無いのに一般手順
   どおり打つと**親に幽霊の記録**が残った（子で親専用工程を叩くと exit 2 になるのに逆向きは
   素通り）→ `guard` が弾き、`aidev-50-test` に分岐を書いた。

### 検査を足した（欠陥を再導入して捕まることを確認済み）

| 検査 | 見るもの | 自己検査 |
|---|---|---|
| **L10** 拡張 | 退役名（`walkthrough` は工程の形だけ）と統合後の同名の並び | 捕捉 6 / 誤検知しないこと 4 |
| **L11**（新） | 全工程 SKILL が自分の `guard` と `event <工程> start` を書いているか | 10 工程 × 2 行 = 20 |
| **L12**（新） | light の文書数が正典（`protocol-light.md` の列挙）と全所で一致するか | 割れ方 2 通り |

L12 の初版は「上流N工程…畳む」も見ようとしたが、`[^。]*` はバイト単位で効かず**何もマッチ
しない空振り**だった。**照合できない形の検査を置かない**という L9 のときと同じ判断で、正典の
数詞と同じ行の列挙を突き合わせる形に作り直した。

## 2. README のメンテナンス

- `aidev-docs/README.md`: 工程表から 65 行を削除（10 工程）／light の文書数／`walkthrough.md` を
  成果物として記述。
- `aidev-docs/bin/README.md`: `use` の slug 補完規則／`doccheck`・`taskcheck` の light 拒否／
  `escalate` の着地後拒否／`verify` の light 逸脱に `walkthrough.md` を追加／`ac_drift` が分割
  work では `-` になる理由／**「分割 work の親は `tasks.md` を持たない」が事実と逆だったのを修正**。
- `aidev-docs/DESIGN.md`: パイプライン図から walkthrough を削除。「2.」に降格の判断基準と
  統合レビュー工程を作らなかった理由を記録。

## 3. 実走（サブエージェント）

**履歴つき `git clone`** で 2 本（コピーだと L8 が構造的に空振りする）。どちらもハーネス側
`git status --porcelain` が空、テスト PJ の skills コピーも `diff -r` で原本と一致することを
実走自身が確認済み。

- **A: 単一 work**（`requirements → design → tasks → coding → test → review → deliver → retro`、
  差し戻し 0・pytest 10 passed・smoke 2 本 pass）。13 件報告。
- **B: 分割 work（親＋子 2 本）＋ light**（子 test 1 回・統合 test 1 回の差し戻しを意図的に発生）。
  10 件報告。

合格を確認した主な点: `guard/event/approve/unapprove walkthrough` はすべて弾かれ state/metrics は
無変化／review の「レビュー補助」節は読んだだけで `walkthrough.md` を書けた／deliver の
`## レビューガイド` 経路は生きている／`walkthrough.md` が無くても `verify --strict`・
`coverage --strict`・`doctor` は exit 0／工程一覧は 4 つの出所すべてで 10 工程一貫／旧工程名は
実行時に一切見えない／子 `approve review` のカーソル自動前進と `guard test` の全子 review 要求／
`coverage` の家族単位／`smoke` の親一本化／多段ネスト禁止。

### pwsh を入れて skip=0 で回し直した（追記）

上の「残す既知の穴」（`skip=270`）を実際に埋めたところ、**`aidev.ps1` が構文エラーで 1 行も
動いていなかった**——`DieUnknownPhase` の `-join` に区切り文字が渡っておらず、187 行目で
ParserError。**その状態でテストは `pass=700 fail=0` と出ていた**（pwsh 不在だと ps1 関連が
丸ごと skip されるので、構文エラーすら検査対象にならない）。3 ゲートはどれもこれを見ない。

- 直して `skip=0` で回し直し、**`pass=983 fail=0`**。
- ついでに**検査自身の欠陥**が 1 件出た: パリティの exit code 比較が `$(… | sed)` の `$?`
  （＝ sed の終了コード）を見ており、**sh 側だけ常に 0** を拾っていた。同じ取り違えの注記が
  同じファイルの上の方にあるのに再発した。
- 再発防止: `run.sh` の NOTE に**「`aidev.ps1` を触ったなら pwsh 無しの緑を信用しない」**を
  名指しで追加し、経緯を `DESIGN.md`「3.5」に記録した。

**残す既知の穴**: Windows PowerShell 5.1（pwsh 7 ではなく）の経路は CI でのみ検証される。
