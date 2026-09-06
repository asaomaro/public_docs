<!-- 出典: work の retro ではなく、外部レビュー（別セッションからの読み合わせ）による指摘。
     対象は plan モードの適用範囲を決める判断基準（改修中・未コミットの案を口頭で受け取って検証）。
     この 3 行のみ公開時に付与 -->

# 振り返り: plan モードの適用範囲 — 基準の据え方と、`spec` という名前

## サマリ

改修中の判断基準「**コードベース探索が主活動で、readonly の強制が有効か**」を、
`EnterPlanMode` / `ExitPlanMode` のツール定義を一次情報として検証した。

**結論（spec / design / plan を対象にする）は妥当。** ただし**その基準は採らないほうがよい**——
片方はツール定義と正面から衝突し、もう片方は絞り込まない。
**ツール自身の用途規定を基準にすると、同じ答えが出たうえで特例が 1 つ減る。**

あわせて、この議論が長引いた原因が **`spec` という名前**にあることが分かった。
aidev の `spec` は「どう作るか」だが、**業界の `spec` は「何を作るか」**で、意味が逆である。

## うまくいった点

- **結論そのものは正しい。** spec / design / plan はいずれも成果物が実装計画側にあり、
  `ExitPlanMode` の用途規定（後述）を満たす。要件側の `requirement` を外した判断も正しい。
- **`plan` を対象に戻した判断は、ツール適合の観点ではむしろ最も素直**。
  `ExitPlanMode` は "planning the **implementation steps**" と書いており、
  作業分解はこれに文字どおり合致する。
- **readonly の強制に着目した点は、価値の説明として正確**。plan モードで
  Write / Edit が塞がること自体が、承認前に実装へ走るのを止める。

## 課題 / 手戻り

### 1. 「探索が主活動」はツール定義と反対を向いている

`EnterPlanMode` は**使わない場面**として明記している:

> **Pure research/exploration tasks (use the Agent tool instead)**

悪い例も「What files handle routing?」＝「**Research task, not implementation planning**」。
**探索は手段であって資格条件ではない。** 「探索が主活動」を基準にすると、
道具が「Agent へ回せ」と言っている仕事ほど高得点になる。

**具体的な誤判定**: コードを読んで事実を集める `research` は、
「探索が主活動」も「readonly の強制が有効」も**両方満たして通る**。
ところが aidev は `research` を「基準の外の規則」で外している。
**新しい基準は、自分の既存ルールと矛盾する。**

### 2. 「readonly の強制が有効か」は絞り込まない

verify も review も research も deliver も、「書くべきでない」という意味では有効である。
**ほぼ全工程で真になるので、基準として働かない。**
資格を満たした工程で「なぜ入る価値があるか」を説明する文としては正しい。

### 3. `spec` という名前が業界と逆で、実際に事故を起こした

SDD ツールを横断すると、**要件フェーズの呼び名は揃っている**——
Kiro の `requirements.md`、Spec Kit の `spec.md`、OpenSpec の proposal-and-spec は
**同じフェーズの別名**（「Almost every SDD tool converges on the same four-phase loop:
Specify—write the "what" and "why"…」）。

| | 何を・なぜ | 方針 | 構造 | 分解 |
|---|---|---|---|---|
| Kiro | requirements | — | design | tasks |
| Spec Kit | spec | plan | — | tasks |
| **aidev** | requirement | **spec** | design | **plan** |

**aidev の `spec` だけが「どう作るか」側にある。** 実装は正しいが、
**他ツールから来た人は逆に読む**。

**実測された害**: 外部レビュー側（このセッション）が、aidev の「spec は plan モード対象」を
別ハーネス（教材用 SDD キット。`spec.md` は業界標準の意味）へそのまま持ち込み、
**要件工程を plan モード対象にする誤りを犯した**。指摘を受けて 3 回作り直している。
語彙が業界と逆であることのコストが、そのまま観測された形。

## 改善提案

### ハーネス自体（→ `aidev-*` への提案・適用は人間）

- **提案 1（本命）: 基準を `ExitPlanMode` の用途規定に置き換える。**

  > **Only use this tool when the task requires planning the implementation steps of
  > a task that requires writing code.** For research tasks where you're gathering
  > information, searching files, reading files or in general trying to understand
  > the codebase — do NOT use this tool.

  基準は「**その工程の成果物が、これから書くコードの実装計画か**」。
  活動ではなく**何を承認してもらうか**で切るので、探索量に関係なく要件工程が落ちる。

  | 工程 | 判定 |
  |---|---|
  | spec / design / plan | ○ |
  | requirement | ×（何をしたいか） |
  | **research** | **×（基準内で落ちる）** |
  | coding | ×（計画ではなく実行） |
  | test / review / deliver / retro | ×（判定・指摘・着地・振り返り） |

  **欲しい答えがそのまま出たうえで、`research` の特例（「基準の外の規則」）が要らなくなる。**
  「探索が主活動」は基準から外し、`readonly` の強制は**入る価値の説明**として基準の下に置く。

- **提案 2: 「二重ゲートに見合うか」は残す。** ツール適合は必要条件であって十分ではない。
  spec → design → plan は承認するものが方針 / 構造 / 手順と別々なので二重にならないが、
  この確認を外すと、承認済みのものを二度承認する工程が混ざる。

- **提案 3: plan file と成果物の書く順序を明記する。** `ExitPlanMode` は
  「**あらかじめ plan file に計画を書いておくこと。ツールは内容を引数に取らず、
  書いたファイルから読む**」と定義しており、**plan モードは自前の成果物ファイルを持つ**。
  したがって `plan` 工程の除外理由だった「計画を二度書く」は**文字どおり正しい**。
  順序が

  ```
  探索 → plan file に計画を書く → 承認 → 抜ける → plan.md / tasks.md に清書
  ```

  なら重複しないが、**成果物を先に書いてから入ると plan file が写しになる**。
  どちらの順かを書かないと、工程ごとに割れる。

- **提案 4: `spec` の名前を扱う。** 選択肢は 2 つ。
  - **(a) 改名する**（`spec`→`plan`、`plan`→`tasks`）。4 つの名前が業界の位置に揃う。
    ただし**`plan.md` の意味が反転する**（同名別義は最も危険な改名）／
    **工程名だけ変えると成果物名がねじれる**（`tasks` 工程が `plan.md` を作ることになる）／
    工程名は `metrics.yml`・`guard`・`dependsOn`・subtask の許可リストに**データとして**入っている。
    `CURRENT_SCHEMA` があるので移行は作れるが、**進行中 work の扱いを先に決める**必要がある。
    **plan モード改修と同時にやらない**——不具合が出たとき切り分けられなくなる。
  - **(b) 一行の但し書きを置く**。「aidev の `spec` は実装仕様であり、
    他ツールの `spec`（要件）とは別物」。大手術を避けつつ、今回の事故は防げる。

- **提案 5（参考・提案ではない）: `plan` が `plan.md` と `tasks.md` を 1 工程で作る点。**
  Spec Kit（`/plan` → `/tasks`）も Kiro（design.md → tasks.md）も**工程を分けている**ので
  aidev は少数派だが、**問題とは言えない**——aidev には `taskcheck` という補償機構があり、
  他ツールには無い。分けたゲートで捕まえるか別の点検で捕まえるかの違いで、どちらも空白ではない。
  ただし plan モードを当てると、**`ExitPlanMode` の承認が方針と手順を一括で受ける**ので
  承認の粒度は粗くなる。判断材料が要るなら、**過去 work に「plan 承認後に tasks 起因の
  手戻りが出た」記録があるか**を insights で見るのが実測になる。

## 補足

- **基準は口頭で受け取ったものを検証した。** 改修中・未コミットとのことで、
  リポジトリと作業ツリーは見ていない。**現物の文面が上記と違えば、指摘はその分ずれる。**
- **動作は確認していない**（ツール定義と公開情報の読み合わせのみ）。
- 一次情報は `EnterPlanMode` / `ExitPlanMode` のツール定義そのもの。
  業界の呼び名は SDD ツール横断比較（MarkTechPost 2026-05-08）、
  Kiro / GitHub Spec Kit の公式ドキュメントで裏を取った。
