---
name: aidev-util-insights
description: ［aidev ユーティリティ］aidev の横断分析。.aidev/works/* を横断して review.md / metrics.yml / decisions.md を集計し、条項・ハーネス改修の効果判定案と systemic な改善提案をまとめる。「aidev insights」「aidev の横断分析をして」と言われたときに使用する。
allowed-tools: [Bash, Read, Write, AskUserQuestion, Agent]
---

AI 開発ワークフローの **横断分析（cross-work insights）ユーティリティ**。
複数の完了作業を横断して記録を集計し、**再発パターン**と **systemic な改善提案**を出す。

per-work の `retro` が「その作業1件」を振り返るのに対し、これは **meta レベル**（作業をまたいだ傾向）を見る。

**分析の軸は2つある**。どちらも1件では成立しないのでここに置く。

| 軸 | 見るもの | 出力 |
|---|---|---|
| **横断（空間）** | 複数 works に共通する再発パターン・ボトルネック | 新しい改善提案 |
| **縦断（時間）** | **過去に入れた改善が効いたか**（ハーネス改修 / PJ規約の条項） | `confirmed` / `ineffective` の判定 |

縦断が無いと、改善提案は入れっぱなしになり「効いた気がする」で終わる。
**縦断を先に回す**（手順2）——未判定の改善を抱えたまま新しい提案を積むと、何が効いているか永久に分からない。

## 位置づけ（重要）

- **パイプライン工程ではない**（番号なし）。`protocol.md` の「対象作業の特定」「工程終了プロトコル」
  「メトリクス記録」には**乗らない**（特定の works を進める skill ではないため）。
- 読み取り中心の分析。出力はレポートで、**改善は提案のみ**（適用は人間。retro と同じ思想）。
- metrics.yml / review.md のスキーマ理解のため `aidev-00-start/protocol.md`「8.」を参照してよい。
  **各指標の定義と解釈上の注意は `aidev-00-start/protocol-analysis.md`**（本ユーティリティ向けの付録）。
- 読み込みが重い場合はサブエージェントに委譲してよい（works ごとに読ませてサマリを集約）。

## 前提

- `.aidev/works/` に複数の作業がある（1件以下では傾向が出ないため、その旨を明示して続行）。

## 入力（全 works 横断）

- **定量指標は `aidev metrics --all` で機械集計する**（`metrics.yml` を手読みしない）。
  - `.claude/skills/aidev-docs/bin/aidev metrics --all`：work 別の first_start / delivered / **lead_sec（リードタイム）** /
    **reworks（手戻り）** / **sent_backs（差し戻し）**。
  - `.claude/skills/aidev-docs/bin/aidev metrics --all --phases`：work×工程の start / approved / **elapsed_sec（工程時間）**。
  - `--format tsv` で機械パース可（列の集計・平均算出に使う）。Windows は `pwsh .claude/skills/aidev-docs/bin/aidev.ps1 metrics ...`（pwsh 無しなら `powershell -NoProfile -File ...`）。
  - **例外: 工程別の付加メトリクスは CLI の派生テーブルに出ない**（`aidev metrics` はイベント列からの
    導出値だけを出力する）。`tasks_anchored` / `unplanned_lookups` / `files_changed` 等が必要な場合に限り、
    `.aidev/works/**/metrics.yml` の `approved` 行から抽出する（1 イベント 1 行なので grep で足りる）。
    **`*/` の1段グロブでは subtask（`works/<親>/<NN>-<子>/`）が落ちる**ので `grep -r` を使う。
    protocol.md「8.」の「工程別の付加メトリクス」がキーの正典。
- `.aidev/works/**/review.md`：レビュー指摘の内容（再発パターン分析の主材料。**テキストは読む**）。
  - **「タスク点検ログ」節（coding 工程内の独立点検。protocol.md「3.3」(b)「8.」）はラウンド指摘と分けて数える**。
    点検で潰れた欠陥は工程に到達しなかったもので、母集団が違う。`[conv:…]` タグの集計は節をまたいでよい
    （タグの規約は同じ）が、`must` 件数の推移を見るときは混ぜない。
  - 点検の効き具合は `task_checks` / `task_check_findings`（coding の付加メトリクス）と `must` の推移を
    突き合わせて読む——**findings が出ているのに `must` が減らないなら、点検の観点か発火条件がずれている**。
- `.aidev/works/**/decisions.md`：繰り返される設計逸脱（テキスト）。
- `.aidev/works/**/retro.md`：過去の per-work 改善提案（再発・未対応の把握。テキスト）。
- **`aidev convention status`**：PJ規約の条項の状態・母集団件数(`pop`)・判定可否(`ready`)。
  `--members <id>` で母集団の work 一覧と `[conv:<id>]` 件数（分母と分子を同じ集合で見る）。
  縦断分析の入口（`protocol.md`「12.」＋ `protocol-conventions.md`）。
- **`aidev harness status`** と **`aidev metrics --all` の `harnessRev`/`straddle` 列**：ハーネス改修の
  仮説・母集団と、work を回した版。改修の前後を分ける鍵（`protocol.md`「12.」）。
- **`.aidev/works/**/review.md` の条項参照タグ `[conv:…]`**：条項の効果判定の主材料（`protocol.md`「8.」）。

## 出力

- `.aidev/insights/<YYYY-MM-DD>-insights.md`（日付は `date -u +%F` で取得）。履歴として残す。
- **判定案**：条項／ハーネス改修ごとに、**そのまま実行できる CLI 行**を書く
  （`aidev convention confirm <id> --result "<内訳>"` ／ `aidev convention retire <id> --status ineffective|superseded --note "<理由>"` ／
  `aidev harness confirm|retire …`）。**insights は CLI を打たない**。判定の実行は
  propose → backlog（判定タスク）→ batch → PR の経路に乗せ、**人間が PR で判定を見てから着地する**
  （`protocol-conventions.md`「batch に許す範囲」）。ユーザーが同席していてその場で承認したときだけ
  interactive で打ってよい（打った変更はその PR に含める）。
  レポートの散文に埋めると propose が拾えず doctor が WARN を出し続けるので、判定案はテンプレの「判定案」節に
  CLI 行の形で残す。母集団が揃う前の `confirm` / `retire --status ineffective` は CLI が拒否する（`--force` は `forced: true` が残る）。
- **却下記録は読むだけ**：`.aidev/insights/rejected.md`（propose が人間の却下を記録する）にある提案は
  「未対応の改善」として再掲しない。再掲するなら**新しい信号**（新たな work・件数の変化）を添える。

## 手順

1. 対象範囲を決める（既定は全 works）。必要なら期間や対象を `AskUserQuestion` で絞ってよい。
2. **定量指標は `aidev metrics --all`（必要に応じ `--phases`/`--format tsv`）で機械集計**し、テキスト材料
   （review.md / decisions.md / retro.md）は読んで突き合わせる。重い場合は works 単位の読み取りを委譲する。
   （記録ドリフト＝metrics/review 欠落は `aidev doctor --quiet` で機械検出できる。legacy work は免除される。）
3. **縦断分析＝過去に入れた改善の効果検証**（新しい提案より先に回す）。

   **(a) PJ規約の条項**（`protocol.md`「12.」／詳細は `protocol-conventions.md`）:
   - `aidev convention status` で `ready=yes`（母集団が揃って未判定）の条項を洗い出す。
     `aidev doctor` の「母集団が揃った(N/M)のに未判定」WARN、および `approve deliver` の到達通知も
     同じものを指す。母集団は **`introduced` 以降に着手し deliver 済み**の work だけ。
   - **`index` 列が `no` の条項は判定しない**。索引に載っていない＝自動読込されず**読まれていない**ので、
     指摘が減っていなくてもそれは条項の効果ではない。先に索引へ足し、母集団を取り直す
     （ここで `ineffective` を打つと、届いていないだけの条項を誤って退役させる）。
   - **数え方と判定手順は `protocol-conventions.md`「効果を判定する」に従う**（`baseline` と導入後の
     タグ件数の比較／数える範囲／`baseline` に「前を作れない」とある条項の扱い）。
   - **陰性は「条項が誤り」を意味しない**（protocol.md「12.」）。理由は `retire --status ineffective --note` に残す。
   - **人間の信号を優先する**: `review.md` の「PR レビュー（人間）」節（`aidev-70-deliver`）の指摘は、AI が書いた
     ラウンド指摘より判定の根拠として重い（他の材料は全段 AI 出力なので、これが唯一の外部信号）。
   - 判定は **CLI 行の形の判定案**として残す（実行は propose→batch→PR 経路。上の「出力」）。
   - **`confirmed` のまま未移送の条項**（doctor が WARN する）は、`docs/aidev/` と PJ ドキュメントの
     二重管理予備軍。改善提案の「PJ プロセス / 規約」に**移送タスク**として挙げる。

   **(b) ハーネス自身の改修**（`state.yml` の `harnessRev`。`protocol.md`「12.」）:
   - `aidev harness status` で `ready=yes`（母集団が揃って未判定）の改修を洗い出す（`aidev doctor` の
     WARN と `approve deliver` の到達通知も同じものを指す）。登録の無い改修は判定できない——見つけたら
     「`aidev harness new` で登録する」を改善提案に挙げる（過去分の仮説を捏造しない）。
   - `aidev metrics --all --format tsv` の **`harnessRev` / `straddle` 列**で works を版ごとに層別し、
     改修の前後で指標を比べる（state.yml を grep して JOIN する必要は無い）。
   - **またがり work（`straddle=yes`）は母集団から外す**。改修の効果を半分しか受けておらず、
     どちらに帰属させても効果が薄まる。
   - 判定は条項と同じく **CLI 行の形の判定案**（`aidev harness confirm <id> --result …` / `retire …`）で残す。
   - 比較に使う指標は**手戻り回数(reworks)を第一に**選ぶ。`elapsed_sec` / `lead_sec` は
     `mode` の層別（autonomous 同士）が成立する件数がないと意味を持たない（`protocol-analysis.md`）。
   - `harnessRev: unknown` の work は層別できないので数から外し、**その旨をレポートに書く**（捏造しない）。

4. 次の観点で**横断**の傾向を抽出する（数値は手順2の `aidev metrics` 出力から算出する）。
   - **レビュー指摘の再発**：同種・同観点の指摘が複数作業で繰り返されていないか。
   - **ボトルネック工程**：手戻り回数(reworks)・差し戻し(sent_backs)・経過時間(elapsed_sec)が突出する工程はどれか。
   - **上流の効き**：research/design を挟んだ作業は手戻りが少ないか（任意工程の効果）。
   - **アンカー的中率**：`1 − unplanned_lookups / tasks_anchored`。低ければ research の問いの立て方が
     的外れ（実装の起点を特定できていない）、常に 100% なら research が過剰。
     → **任意工程 research の発火条件そのものを調整する材料**にする。
   - **規模あたりの手戻り**：reworks ÷（`insertions` + `deletions`）。tasks 数は粒度の癖でぶれるため、
     work 間の比較はこの正規化で行う。
   - **経過時間の層別**：`elapsed_sec` を比べるときは `state.yml` の `mode` で分ける
     （interactive は人間の承認待ちが支配的で工程の重さを反映しない。比較が成立するのは autonomous 同士）。
   - **light プロファイルの健全性**（`state.yml` の `profile`。protocol.md「11.」）。次の3点を見る。
     - **light の手戻り率が full と同等か**。有意に高ければ light の適用条件が緩い。
     - **昇格率**（`escalated_from_light` の件数 ÷ light の件数）。高ければ入口判定が機能していない。
     - **light の比率**。9割を超えたら light が新しい full になっているサイン（＝full の存在意義が消えている）。
     `aidev verify` / `doctor` の「profile=light だが…」WARN が残っている work は**昇格漏れ**として扱う
     （light のまま着地した work は、上の手戻り率を実態より良く見せる）。
   - **未対応の改善**：過去 retro の提案で、繰り返し挙がるが未反映のもの。
     **`.aidev/insights/rejected.md` にある提案は除く**（人間が却下したものを毎周「未対応」として再掲しない）。
   - **未着手キューの滞留（任意）**：`.aidev/backlog/*.md`（archive 除く）の未処理件数・滞留や
     `(needs:…)` で止まっている項目を、残作業のコンテキストとして添えてよい（完了作業の分析が主旨）。
5. 観察を **systemic な改善提案**に変換し、3カテゴリに仕分ける。
   - **製品 / コード**：横断する技術的負債 → 新 issue 候補。
   - **PJ プロセス / 規約**：反復するレビュー指摘・観点抜け → **`docs/aidev/` の条項**として起こす
     （`aidev convention new` → **`## 規約` の本文を書く**。**AGENTS.md 本体には書かない**。protocol.md「12.」）。
     `confirmed` 済み条項の**移送タスク**もここに入れる（未移送は二重管理予備軍）。
   - **ハーネス自体**：工程・ゲート・protocol の構造的不備 → `aidev-*` への変更提案（提案のみ）。
6. 下記テンプレートで `.aidev/insights/<日付>-insights.md` を生成し、サマリを提示する。
   - これは提案レポート。採用された提案は、ユーザー指示で別途（issue / AGENTS.md / 基盤改修）対応する。

## insights.md テンプレート

```markdown
# 横断分析 (<日付>)

## 対象
- works: <件数・対象範囲>

## 効果検証（縦断）
### PJ規約の条項
| id | introduced | 母集団 | 判定 | 根拠 |
|---|---|---|---|---|
| <id> | <時刻> | <pop>件 | confirmed / ineffective | <conv タグの増減> |

### ハーネス改修
- <harnessRev X 以前 / 以後 の reworks 比較。またがり work・unknown は除外した件数を明記>

### 判定案（そのまま backlog の判定タスクになる CLI 行。propose が拾う）
- [ ] 条項 <id> を判定: `aidev convention confirm <id> --result "<baseline> -> <導入後>（母集団 <pop>）"`
- [ ] 条項 <id> を判定: `aidev convention retire <id> --status ineffective --note "<理由>"`
- [ ] ハーネス改修 <id> を判定: `aidev harness confirm <id> --result "<…>"`

### 未判定・未移送
- <母集団が揃っていない条項（あと何件か）>
- <confirmed だが未移送の条項（＝二重管理予備軍）>

## 主要メトリクス（横断）
- 平均リードタイム / 手戻り回数の分布 / ボトルネック工程
- research・design 使用有無と手戻りの相関（わかる範囲で）
- アンカー的中率（`1 − unplanned_lookups / tasks_anchored`）と、規模あたりの手戻り

## 再発パターン
### レビュー指摘
- <繰り返し現れる指摘の類型と頻度>
### 設計逸脱・その他
- <decisions/retro から繰り返すもの>

## 改善提案
### 製品 / コード（→ issue 候補）
- <横断する負債>
### PJ プロセス / 規約（→ `docs/aidev/` の条項。AGENTS.md 本体には書かない）
- <新しい条項案（id / 仮説 / 根拠にした `[conv:-]` 指摘）>
- <`confirmed` 条項の PJ ドキュメントへの移送タスク>
- <「規約はあるが守られていない」＝散文層の限界。CLI / フック層へ寄せる提案>
### ハーネス自体（→ aidev-* への提案・適用は人間）
- <構造的改善案と理由>

## データの限界
- <件数不足・記録欠落など、解釈上の注意>
- <`harnessRev: unknown` / またがり work で母集団から外した件数>
- <条項の陰性は「散文では効かなかった」までしか言えない旨>
```

## 完了の目安

- **未判定だった改善（条項 / ハーネス改修）の判定案が CLI 行の形で「判定案」節に残っている**
  （散文で「効いたと思う」と書くだけでは propose が拾えず、doctor の WARN が止まらない）。
- 単一作業では見えない**横断の再発パターン**が抽出されている。
- 改善提案が3カテゴリに仕分けられ、次アクションが明確（提案止まりでよい）。
