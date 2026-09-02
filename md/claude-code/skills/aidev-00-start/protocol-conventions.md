# PJ規約の条項と効果検証（`protocol.md`「12.」の詳細）

> **読む条件**: 条項を起こすとき（retro / insights / propose）／効果を判定するとき（insights）／
> PJ ドキュメントへ移送するとき（batch / 人間）／doctor の convention 検査を読むとき。
> 核となる規約と要約は `protocol.md`「12.」。ここはその詳細を切り出したもの
> （工程ごとの読み込み量を抑えるため。`protocol.md`「0.」の付録一覧を参照）。


## 条項の一生

| status | 意味 | 次にすること |
|---|---|---|
| `pending` | 導入済み・母集団が未達 | 待つ（`aidev convention status` の `ready` を見る） |
| `confirmed` | 効果が確認できた | **PJ ドキュメントへ本文を移送**し `promote` |
| `promoted` | 移送済み | 何もしない（tombstone として `archive/` に残る） |
| `ineffective` | 効果が無かった | 撤去、または CLI / フック層へ寄せる（下記） |
| `superseded` | 別条項に置き換わった | 撤去 |

**本文の在処は常に1箇所**。移送したら `docs/aidev/` 側は本文を捨てて tombstone にする。

### 条項ファイルのスキーマ

`docs/aidev/<id>.md`（場所は `.aidev/config.yml` の `conventionsDir` で変更可。既定 `docs/aidev`）。

```yaml
---
convention: naming-boolean      # id（ファイル名と一致）
status: pending                 # pending | confirmed | promoted | ineffective | superseded
introduced: 2026-08-30T09:12:00Z # 導入時刻（UTC）。母集団の起点。日付だけの旧記法は 00:00:00Z 扱い
source: .aidev/insights/2026-08-28-insights.md   # この条項を生んだ信号（任意）
hypothesis: 命名に関する must/should 指摘が減る    # 必須。書けない条項は作らせない
baseline: 直近10 works で boolean 命名の指摘 7件（must 2 / should 5）  # 必須。「前」の記録
verify_after: 5                 # 判定に要する母集団の最低件数（既定 5）。defer で積み増せる
deferred: 2026-09-10T00:00:00Z  # defer 時（任意）
defer_note: <先送りの理由>        # defer 時（必須）
result: <判定の内訳>             # confirm 時
promoted_to: docs/coding-standards.md#boolean-naming  # promote 時
promoted_at: 2026-09-15         # promote 時
note: <退役理由>                 # retire 時（必須）
forced: true                    # 母集団が揃う前に --force で confirm/retire したとき（後から「揃う前の判定」と分かる）
---
```


## 条項を起こす（`pending` にする）

```sh
.claude/skills/aidev-docs/bin/aidev convention new <id> \
  --hypothesis "<何がどう動けば効果ありと判定するか>" \
  --baseline "<導入前にこの観点の指摘が何件あったか>" \
  --source .aidev/insights/<日付>-insights.md \
  --verify-after 5
```

- **`--hypothesis` は必須**。CLI が拒否する。書けない条項は後から検証できず、事後の物語作りに
  しかならない。**この関門自体に価値がある**——検証不能な改修は「効果を主張してはいけない改修」。
- **`--baseline` も必須**。**「前」を作れるのは起票のこの瞬間だけ**だから。
  条項 id はいま生まれるので、導入前の review.md にその id は決して現れない
  （id 別の件数は必ず `0 → N` と増えるだけで、前後比較にならない）。

  ```sh
  # 数え方の例: 過去の review.md を読み、その観点の指摘を拾う
  # -r で works 配下を再帰する。subtask は works/<親>/<NN>-<子>/ にあり、
  # `works/*/review.md` の1段グロブからは落ちるため（分割 work の指摘は大半がそこに入る）
  grep -rho --include=review.md 'boolean\|真偽' .aidev/works | wc -l
  ```

  - **数えるのは id ではなく観点**。「何をその観点とみなしたか」を値に文章で残す
    （後から同じ基準で数え直せるように）。
  - **数えられないならその事実を書く**：`0件（review.md がまだ無く、前を作れない）`。
    捏造も空欄も不可。この条項は**前後比較が成立しない**ので、判定時は根拠を明示する。
  - 数え方が前後で違う（前＝読んで数える／後＝タグを数える）ことは避けられない。
    だからこそ境目の判断を `baseline` に書き残す。
- **`--source` を付ける**。どの信号から起こしたかが残らないと、insights が「未対応の改善」を
  追うときに突合できない。
- **`--verify-after`** は判定に要する母集団の最低件数（既定 5）。条項が関係する work は一部だけなので、
  ハーネス改修より判定に必要な件数は**増える**方向で見積もる。
  母集団に数えるのは **`introduced` 以降に着手し、かつ deliver 済み**の work だけ
  （着手しただけの work は review を通っておらず判定材料が無い）。
  なお数えるのは **top-level work のみ**で、subtask は親と二重に数えない。
- 起こしたら **`## 規約` の本文を書く**（起票テンプレのコメントを残さない）。`convention new` は
  枠しか作らない。本文が無いまま索引に載ると「読まれるが中身が無い」＝タグは付くのに規約は無い
  母集団ができる。`doctor` が未記入を WARN する。
- 続けて **索引ファイルの索引ブロックに1行足す**（既定 `AGENTS.md`。`conventionsIndex` で変更可。
  `protocol.md`「12.」）。
  これを飛ばすと条項は自動読込されず、**読まれていないだけなのに「効かなかった」と判定される**。
  `convention new` が**足すべき行をそのまま出力する**ので、`<いつ参照するか>` を埋めて貼る:

  ```markdown
  <!-- aidev:conventions -->
  - <いつ参照するか> → docs/aidev/<id>.md
  <!-- /aidev:conventions -->
  ```

  飛ばしても `aidev doctor` が「索引に無い」と WARN し、`aidev convention status` の `index` 列が
  `no` になる。索引に無い間は母集団が揃っても **doctor は「未判定」を催促しない**（読まれていない条項を
  判定させない）。索引に足したら `aidev convention defer` で必要件数を積み増し、読まれた work で数え直す。

### 索引ブロックの規則

- **harness が触るのはマーカーの内側だけ**。導入時に人間が1回置き、以後は索引行の増減と
  リンク先の張り替え（移送時）のみ。マーカー外は完全に PJ のもの（**マーカー外の記述は索引と認めない**）。
- **索引漏れは `aidev doctor` が検知する**。載っていない条項は読まれないので、
  **効果検証で「効かなかった」と誤判定される**——条項の内容の問題ではなく届いていないだけなのに。
  検査だけ置くと直す手がないので、WARN は**足すべき行をそのまま示す**。
  `aidev convention status` の `index` 列でも一覧できる。
- **移送したら索引の張り替えも検査される**（`docs/aidev/<id>.md` を指したままなら WARN）。
- 索引ファイルは `.aidev/config.yml` の `conventionsIndex` で指定できる
  （未設定なら AGENTS.md → CLAUDE.md の順で探す。PJ 固有ファイル名を CLI に埋めないため）。
- aidev を使わない PJ は**索引ブロックごと削除すれば無害に切り離せる**。
- **矛盾したときは PJ の AGENTS.md 本体が上位**。`docs/aidev/` は追補であって上書きではない
  （ハーネスの提案が PJ の明示的な意思を覆すのは越権）。


### 起こす前に既存 PJ ドキュメントを確認する（入口の重複排除）

PJ の既存ドキュメントに**既に書いてある**規約を条項として起こすと、最初から二重管理になる。
ハーネスは PJ のドキュメント構成を知らない（`protocol.md`「0.」の自己完結原則）ので、
**PJ から教えてもらう**:

```yaml
# .aidev/config.yml
conventionsDir: docs/aidev     # 条項の置き場（既定。変更可）
conventionsIndex: AGENTS.md    # 索引ブロックを置くファイル（未設定なら AGENTS.md → CLAUDE.md を探す）
docsRoots: [docs/, AGENTS.md]  # 条項を起こす前に既存規約を探す場所（PJ が申告）
```

`aidev convention new` は起票時に **`docsRoots` の内容をそのまま出力**して確認を促し、
**未設定なら「機械的に絞れないので、確認していない旨を明記せよ」と告げる**
（`protocol.md`「8.」の「欠落を捏造で埋めない」と同じ態度）。

> 注: CLI がするのは**申告された探索先を提示するところまで**。実際に「同じ規約が既にあるか」の
> 判定は散文（＝読んで判断する）に残す。どのファイルのどの記述が同じ規約かは判断であって、
> grep で決まる話ではないから。CLI が**パス解決に**使うのは `conventionsDir` と `conventionsIndex` だけで、
> `docsRoots` は読み上げて提示するだけ（判定には使わない）。

## 効果を判定する（`confirmed` / `ineffective`）

判定案を出すのは `aidev-util-insights`（横断分析）の仕事（実行は propose→batch→PR。下の「batch に許す範囲」）。起動の合図は2つ:

1. **`aidev approve deliver` の到達通知**（`note: 条項 <id> の母集団が揃いました(N/M)`）。
   母集団が増える瞬間は deliver の1点なので、**到達の一報はここで鳴る**。
2. `aidev doctor` の **「母集団が揃った(N/M)のに未判定」** WARN（retro / insights の冒頭で回る）。
   doctor は**既に見に行った人にしか届かない**ので、1 の一報と併せて機能する。
3. `aidev convention status` の **`ready=yes`**

判定は **`baseline` と、導入後のタグ件数の比較**で行う（`protocol.md`「12.」）。材料の中では
`review.md` の**「PR レビュー（人間）」節**（`aidev-70-deliver`）を優先する（唯一の人間由来の信号）。
`baseline` に「前を作れない」と書かれている条項は**比較が成立しない**ので、
件数ではなく個別の根拠を示して判定する（示せないなら `pending` のまま置く——
`aidev convention defer <id> --verify-after <n> --note <理由>` で必要件数を積み増し、次に揃うまで催促を止める）。

「前」＝`baseline` は条項ファイルの frontmatter にある（`<conventionsDir>/<id>.md`。
`convention status` はこの値を出さないので、判定するときはファイルを開く）。
「後」＝導入後の件数は `review.md` のタグから数える:

```sh
# 導入後の件数を数える（「前」は frontmatter の baseline。id では前後比較できない）
# -r で再帰するのは、subtask が works/<親>/<NN>-<子>/ にあり、
# `works/*/review.md` の1段グロブからは落ちるため（分子だけ落ちると「効いた」側に倒れる）
grep -rho --include=review.md '\[conv:[^]]*\]' .aidev/works | sort | uniq -c | sort -rn
```

- **母集団は `introduced` 以降に着手し、かつ deliver 済みの work だけ**
  （`aidev convention status` の `pop` が数える）。
  導入前から走っていた work は条項の効果を半分しか受けていない。
- **上の grep は全 works を舐める**ので、分母と同じ集合で数えるには
  `aidev convention status --members <id>` を使う（母集団の work ごとに着手・deliver・`[conv:<id>]` 件数。
  subtask の `review.md` は親に合算）。絞らずに数えると、分子（タグ）と分母（母集団）が別のものを指す。
  **subtask は親に属する**——親が `introduced` より前に着手していれば、その子のタグも数えない。
- **出口も CLI が守る**: `confirm` は `--result`、`retire` は `--note` が必須。母集団が `verify_after` に
  達していない条項の `confirm` / `retire --status ineffective` は拒否される（`superseded` は置き換えなので免除）。
  それでも進めるなら `--force`——`forced: true` が frontmatter に残り、後から「揃う前の判定」と分かる。
- **陰性は結論にならない**。遵守が LLM 依存で非決定的なので、指摘が減らなくても
  「条項の内容が間違っていた」とは言えない。言えるのは「**散文では効かなかった**」まで。
  その場合の打ち手は削除ではなく **CLI（ハード層）かフック（自動化層）へ寄せる**こと。
- **タスク点検（`protocol-check.md`）は判定を保守側にずらす**。点検で潰れた欠陥は review のラウンド指摘に現れないため、
`must` 件数だけを見ると条項の効果は**過小に**見える。判定材料の主役は `review.md` の `[conv:…]` タグで、
タグは点検ログ節にも同じ規約で付く（「8.」）ので**節をまたいで grep すれば漏れない**。
件数指標を使うときは `task_check_findings` を併せて見る。

| review 指摘が条項に | 意味 | 打ち手 |
|---|---|---|
| 対応しない（`conv:-`） | 規約に穴がある | 条項を起こす |
| 対応する（なのに指摘された） | 規約はあるが守られていない | **追記しても効かない**。層を下げる |


```sh
aidev convention confirm <id> --result "baseline 7件(must 2/should 5) -> 導入後 6works で [conv:<id>] 1件"
aidev convention retire  <id> --status ineffective --note "散文層の限界。CLI の verify へ寄せる"
```

## PJ ドキュメントへ移送する（`promoted`）

**`confirmed` のまま放置すると PJ ドキュメントと二重管理になる**（doctor が WARN する）。

1. 条項の本文を PJ の該当ドキュメントへ**移す**（文体・配置・既存章との統合はここで判断する。
   CLI にはさせない）。
2. `aidev convention promote <id> --to docs/coding-standards.md#anchor`
   - 移送先の**ファイルの実在を CLI が検査**する（アンカーまでは見ない）。
     dangling な `promoted_to` は「本文がどこにも無い」という、二重管理より悪い状態を作る。
   - 条項ファイルは**本文を捨てて tombstone 化**され `archive/` へ退避される。
3. **索引ブロックのリンク先を張り替える**（`docs/aidev/<id>.md` → 移送先）。
   どのファイルかは `promote` の出力が名指しする（`conventionsIndex` に従う）。
   忘れると `aidev doctor` が「索引が移送前を指したまま」と WARN する。

### 移送を自己給餌ループに乗せる

移送は PJ ドキュメントの編集＝**通常のリポジトリ変更**なので、既存のループに流せる:

```
doctor が「confirmed だが未移送」を WARN
  → aidev-util-propose が信号として拾い backlog に積む
  → aidev-util-batch が autonomous で消化（本文を移し、promote する）
  → PR で人間がレビュー（auto-merge しない）
```

**batch に許すのは条項の追加・移送・判定（insights の判定案どおりの `confirm` / `retire`）まで**。
判定は PR に載って**人間が見てから着地する**——insights が直接 status を進めない理由（AI 単独の判定に
人間ゲートを通す）。既存条項の**削除・緩和は人間**が行う。
追加は次のレビューで効かなければ消せる（可逆）が、緩和は「守らなくてよくなった」状態を作り、
それが正しかったかを事後に検証できない（ガードを外す方向は検証不能）。

## CLI（`aidev convention`）

起こす・状態を進める・退避するは CLI にある。**本文を PJ ドキュメントへ実際に移す作業だけは CLI にしない**
（文体・配置・既存章との統合が判断だから）。

| コマンド | 役割 |
|---|---|
| `aidev convention new <id> --hypothesis <text> --baseline <text> [--source <p>] [--verify-after <n>]` | 起こす（`--hypothesis` と `--baseline` は必須） |
| `aidev convention confirm <id> --result <text> [--force]` | 効果ありと判定（`--result` 必須。母集団が `verify_after` 未満なら拒否。`--force` は `forced: true` を刻む） |
| `aidev convention defer <id> --verify-after <n> --note <t>` | 判定を先送り（必要件数を積み増す。`n` は現在の母集団より大きいこと。理由必須） |
| `aidev convention promote <id> --to <path#anchor>` | tombstone 化して退避（移送先の実在を検査） |
| `aidev convention retire <id> --status ineffective\|superseded --note <t> [--force]` | 退役して退避（`--note` 必須。`ineffective` は母集団が要る。`superseded` は置き換えなので免除） |
| `aidev convention status [--format table\|tsv] [--members <id>]` | 状態・母集団・判定可否の一覧。`--members` は母集団の work ごとに着手・deliver・`[conv:<id>]` 件数（分母と分子を同じ集合で見る） |

**ファイル自身の一生は `aidev doctor` が見る**（条項ファイルには持ち主の work がいないので `verify` の
硬ゲートにできない）。検知するのは `status` の欠落・誤記／判定可能なのに未判定／confirmed の移送漏れ／
終状態の退避漏れ／索引漏れ・張り替え漏れ／退役後の索引 dangling／本文未記入。**WARN 止まり**。

## tombstone を消さない

`archive/` の tombstone は**重複排除のため**に残す。跡形なく消すと同じ提案が retro から再び上がる。
`aidev convention new` は archive に同じ id があれば**重複として弾く**。

## `docs/aidev/` の肥大化は異常の信号

移送パスがあるので、定常状態では **`pending` の条項しか残らない**。確定したものも否定されたものも
出ていく。膨らんできたら「検証が回っていない」か「移送が滞っている」ということなので、
`aidev convention status` の `pending` 件数を**ループの健全性メトリクス**として見る
（insights の「light 比率が9割超なら light が新しい full になっているサイン」と同じ使い方）。
