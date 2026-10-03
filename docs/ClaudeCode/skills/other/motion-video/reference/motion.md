# 動きの性格・切り替え・文字の出方・演出・カメラ

手順 2 で、動きの性格（`motion`）を決めるときと、見せ場の場面だけ動きを変えるときに読む。

**動きの性格（台本の `motion`）** — 1 つ選ぶと、切り替え・文字の出方・演出の層・カメラの既定がまとまって決まる（場面の指定が優先）。
内容と見る人から Claude が決める（質問はしない。ユーザーが「ダイナミックに」「落ち着いて」等と言ったときはそれに従う）:

| `motion` | 切り替え（章の境目） | 文字（題名） | 演出・カメラ | 向く内容 |
|---|---|---|---|---|
| `gentle`（既定） | fade | 浮かぶ（カーソルで現れる） | なし | 研修・社内説明・手順 |
| `dynamic` | whip・push・突っ込む・上へ（円が開く） | 弾む（叩きつける・揺れる） | 題名に集中線と粒、言い切りで寄る | 製品の発表・告知・勢いのある紹介 |
| `playful` | 回る・箱・円・上へ（回る） | 波打つ（落ちてくる） | 題名と締めに紙吹雪 | 子ども・イベント・親しみやすい案内 |
| `cinematic` | fade・突っ込む（白く光る） | ぼけから（伸びから縮む） | 光の玉・光の筋・周りを暗く、ゆっくり漂う | ビジョン・物語・ブランド |
| `tech` | 乱れ・拭き取り・モザイク・帯（乱れ） | でたらめな文字から | 走査線・格子の床 | 技術・データ・開発者向け |
| `retro` | モザイク・ばらばら・縞・縦の帯（タイル） | 瞬いて点く（落ちて跳ねる） | 古いフィルム・網点、題名は手持ちのカメラ | 懐かしさ・ゲーム・昭和風・遊び心 |
| `elegant` | ぼけ・fade・色の幕（色の幕） | 字間が詰まる（同じ） | 光漏れ・きらめき、呼吸するカメラ・ピントが合う題名 | 高級感・ブランド・式典・招待 |
| `news` | 色の帯・押し出し・重なる・扉（色の帯） | 箱が走る（斜めに滑り込む） | レーダーの輪、言い切りで一瞬で引く | 速報・発表・社内報・数字の報告 |

- 性格を選んだら台本全体の `transition` は書かない（書くとそれが全場面に効く）。見せ場の場面だけ `transition`・`anim`・`fx`・`camera`・`shake` で変える。
- 切り替え（43 種）: `fade` `slide` `zoom` `cut` `wipe` `push` `slide-up` `slide-down` `iris` `blinds` `split` `whip` `spin` `flash` `glitch` `pixel` `squeeze` `zoom-through`
  `diagonal` `diamond` `spot`（場面の `origin` から）`cube` `page` `liquid` `dive`（前の場面の `focus` へ飛び込む）`tiles` `stripes` `clock`
  `doors` `shatter`（ガラスのように割れる）`fan` `spin-zoom` `bars` `cover`（色の幕。ブランド名が出る）`ink` `flip` `rings` `stack` `shrink` `flood` `focus` `dissolve` `columns`。
- 文字の出方（`anim`。title・statement・quote・end・kinetic・impact・logo・layout・bigtype）: `rise` `reveal` `pop` `slam` `stretch` `blur` `glitch` `neon` `type` `scramble` `wave` `letters` `split`
  `mask` `marker` `drop` `zoom` `outline` `roll` `spin` `shadow` `flip` `rotate` `bounce` `box` `flicker` `words` `halves` `swing` `elastic` `tracking` `skew`。
- 演出の層（`fx`）: `particles` `stars` `bokeh` `rays` `speedlines` `grid` `waves` `gradient` `aurora` `plexus` `contour` `shapes` `blobs`
  `embers` `halftone` `warp` `pulse` `bubbles` `matrix`（部品の下）・`scanlines` `confetti` `vignette` `sweep` `noise` `rain` `snow` `film` `leaks` `spotlight` `sparkles`（上）。
- 動き方（場面か台本の `ease`・`order`）: 緩急 `smooth`（既定）・`spring`・`snappy`・`bouncy`・`elastic`・`calm`、現れる順 `reverse`・`center`・`edges`・`random`・`alternate`・`zigzag`（項目を順に出す部品に効く）。
  `"fx": false` で性格の既定も止める。1 場面に 1〜2 個まで。
- カメラの型（`camera` に名前）: `push-in` `pull-out` `pan-left` `pan-right` `rise` `punch` `tilt` `drift` `dolly` `crash-zoom` `orbit` `pan-reveal` `rack-focus`（ぼけから合う）`breathe` `sink` `handheld`。
  自分で書くときも、鍵の点に `blur`（px）を書けばピントが動く。
- 画面の揺れ: `"shake": [{"at": 0.4, "amp": 18, "dur": 450}]`（`slam`・`impact`・`countdown`・判子は自動で揺れる）。
- 強い動き（`slam`・揺れ・破片・`flash`・`glitch`）は見せ場だけに使う。全場面を強くすると、どれも強調にならない。

## 重ねの層とカメラ

- どの場面にも、**重ねの層**（`overlays`: 注記・矢印・強調・スポットライト・バッジ・カーソル・OS 風の通知・
  破片・波紋・紙吹雪・判子・手書きの丸・蛍光ペン）と **カメラ**（`camera`: 寄る・引く・移る・傾く。型の名前でも書ける）を付けられる。部品の見た目を崩さずに演出を足す手段で、`custom` より先に使う。
