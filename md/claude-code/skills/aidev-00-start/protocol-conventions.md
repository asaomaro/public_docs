# PJ規約の条項と効果検証（`protocol.md`「12.」の詳細）

> **読む条件**: 条項を起こすとき（retro / insights / propose）／効果を判定するとき（insights）／
> PJ ドキュメントへ移送するとき（batch / 人間）／doctor の convention 検査を読むとき。
> 核となる規約と要約は `protocol.md`「12.」。ここはその詳細を切り出したもの
> （工程ごとの読み込み量を抑えるため。`protocol.md`「0.」の付録一覧を参照）。


## 条項を起こす（`pending` にする）

```sh
.claude/skills/aidev-docs/bin/aidev convention new <id> \
  --hypothesis "<何がどう動けば効果ありと判定するか>" \
  --source .aidev/insights/<日付>-insights.md \
  --verify-after 5
```

- **`--hypothesis` は必須**。CLI が拒否する。書けない条項は後から検証できず、事後の物語作りに
  しかならない。**この関門自体に価値がある**——検証不能な改修は「効果を主張してはいけない改修」。
- **`--source` を付ける**。どの信号から起こしたかが残らないと、insights が「未対応の改善」を
  追うときに突合できない。
- **`--verify-after`** は判定に要する母集団の最低件数（既定 5）。条項が関係する work は一部だけなので、
  ハーネス改修より判定に必要な件数は**増える**方向で見積もる。
- 起こしたら **AGENTS.md の索引ブロックに1行足す**（`protocol.md`「12.」）。
  これを飛ばすと条項は自動読込されず、**読まれていないだけなのに「効かなかった」と判定される**。

### 起こす前に既存 PJ ドキュメントを確認する（入口の重複排除）

PJ の既存ドキュメントに**既に書いてある**規約を条項として起こすと、最初から二重管理になる。
ハーネスは PJ のドキュメント構成を知らない（`protocol.md`「0.」の自己完結原則）ので、
**PJ から教えてもらう**:

```yaml
# .aidev/config.yml
conventionsDir: docs/aidev     # 条項の置き場（既定。変更可）
docsRoots:                     # 条項を起こす前に既存規約を探す場所（PJ が申告）
  - docs/
  - AGENTS.md
```

`docsRoots` が未設定なら検査を飛ばし、**「既存 docs を確認していない」と retro / insights に明記する**
（`protocol.md`「8.」の「欠落を捏造で埋めない」と同じ態度）。

> 注: `docsRoots` は**散文の規約**で、CLI は読まない。探索範囲の決定は判断（どのファイルが規約か）で、
> 機械にできるのは「どこを見ればよいか」の申告までだから。CLI が読むのは `conventionsDir` だけ。

## 効果を判定する（`confirmed` / `ineffective`）

判定は `aidev-util-insights`（横断分析）の仕事。起動の合図は2つ:

1. `aidev doctor` の **「母集団が揃った(N/M)のに未判定」** WARN（retro / insights の冒頭で回る）
2. `aidev convention status` の **`ready=yes`**

判定材料は `review.md` の**条項参照タグ**（`protocol.md`「8.」）:

```sh
# 条項 id 別の指摘件数を introduced の前後で比べる
grep -ho '\[conv:[^]]*\]' .aidev/works/*/review.md | sort | uniq -c | sort -rn
```

- **母集団は `introduced` 以降に着手した work だけ**（`aidev convention status` の `pop` が数える）。
  導入前から走っていた work は条項の効果を半分しか受けていない。
- **陰性は結論にならない**。遵守が LLM 依存で非決定的なので、指摘が減らなくても
  「条項の内容が間違っていた」とは言えない。言えるのは「**散文では効かなかった**」まで。

```sh
aidev convention confirm <id> --result "must 3件/5works -> 0件/6works"
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
3. **AGENTS.md 索引ブロックのリンク先を張り替える**（`docs/aidev/<id>.md` → 移送先）。

### 移送を自己給餌ループに乗せる

移送は PJ ドキュメントの編集＝**通常のリポジトリ変更**なので、既存のループに流せる:

```
doctor が「confirmed だが未移送」を WARN
  → aidev-util-propose が信号として拾い backlog に積む
  → aidev-util-batch が autonomous で消化（本文を移し、promote する）
  → PR で人間がレビュー（auto-merge しない）
```

**batch に許すのは条項の追加と移送まで**。既存条項の**削除・緩和は人間**が行う。
追加は次のレビューで効かなければ消せる（可逆）が、緩和は「守らなくてよくなった」状態を作り、
それが正しかったかを事後に検証できない（ガードを外す方向は検証不能）。

## tombstone を消さない

`archive/` の tombstone は**重複排除のため**に残す。跡形なく消すと同じ提案が retro から再び上がる。
`aidev convention new` は archive に同じ id があれば**重複として弾く**。

## `docs/aidev/` の肥大化は異常の信号

移送パスがあるので、定常状態では **`pending` の条項しか残らない**。確定したものも否定されたものも
出ていく。膨らんできたら「検証が回っていない」か「移送が滞っている」ということなので、
`aidev convention status` の `pending` 件数を**ループの健全性メトリクス**として見る
（insights の「light 比率が9割超なら light が新しい full になっているサイン」と同じ使い方）。
