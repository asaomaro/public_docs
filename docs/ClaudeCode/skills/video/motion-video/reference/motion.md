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
| `craft` | めくる・畳む・滑って抜ける・ページ（破る） | 蛍光ペン（色が満ちる） | 題名と締めに額縁、題名はゆれるカメラ | 手作り・工作・絵本・あたたかい紹介 |
| `fluid` | ぼかした境目・波・水面・墨（ぼかした境目） | 動かずに浮かぶ（光が走る） | 題名と締めに霧、題名と引用でゆっくり寄る | 癒やし・自然・美容・ゆったりした語り |
| `crisp` | 上へ拭く・滑って抜ける・左へ拭く・帯（帯） | 下線から立ち上がる（足元から伸びる） | 演出なし、言い切りは 2 段で寄る | 業務の説明・決算・手順・きびきび進めたい報告 |
| `spatial` | 奥へ沈む・扉・箱・裏返す（奥へ沈む） | 奥から迫る（起き上がる） | 題名と締めに針金の箱、題名は回りながら引く・言い切りは傾く | 3D・建築・ゲーム・空間や構造の話 |
| `show` | 円が閉じる・星・落ちてくる・外れて落ちる（絞りの羽根） | 噛み合う（並び替わる） | 題名にスポットライト、締めに花火、題名は横から流れ込む | 表彰・発表会・バラエティ・お祝い |

- 性格を選んだら台本全体の `transition` は書かない（書くとそれが全場面に効く）。見せ場の場面だけ `transition`・`anim`・`fx`・`camera`・`shake` で変える。
- 切り替え（59 種）: `fade` `slide` `zoom` `cut` `wipe` `push` `slide-up` `slide-down` `iris` `blinds` `split` `whip` `spin` `flash` `glitch` `pixel` `squeeze` `zoom-through`
  `diagonal` `diamond` `spot`（場面の `origin` から）`cube` `page` `liquid` `dive`（前の場面の `focus` へ飛び込む）`tiles` `stripes` `clock`
  `doors` `shatter`（ガラスのように割れる）`fan` `spin-zoom` `bars` `cover`（色の幕。ブランド名が出る）`ink` `flip` `rings` `stack` `shrink` `flood` `focus` `dissolve` `columns` `depth` `swing`（立体）。
  向きと形: `wipe-up`（下から上へ）`wipe-left`（右から左へ）`soft-wipe`（ぼかした境目）`iris-close`（円が閉じて開く）`shutter`（絞りの羽根が閉じて開く）`star`（星形が広がる）。
  紙と物: `tear`（縦に破れて左右へ）`fold`（じゃばらに畳まれる）`peel`（右下の角からめくれる）`uncover`（前が滑って抜け、次は動かない）`tumble`（角を軸に外れて落ちる）`slices`（横の帯が互い違いに抜ける）
  `tv-off`（ブラウン管を消すように線に潰れて開く）`drop`（次が上から落ちて弾む）。`iris-close`・`shutter`・`tv-off` は、途中で一瞬だけ前も次も見えない（章の境目向き）。
- 文字の出方（`anim`。title・statement・quote・end・kinetic・impact・logo・layout・bigtype）: `rise` `reveal` `pop` `slam` `stretch` `blur` `glitch` `neon` `type` `scramble` `wave` `letters` `split`
  `mask` `marker` `drop` `zoom` `outline` `roll` `spin` `shadow` `flip` `rotate` `bounce` `box` `flicker` `words` `halves` `swing` `elastic` `tracking` `skew` `depth` `unfold` `swirl`、
  `fade`（動かずに浮かぶ。いちばん控えめ）`count`（行の中の数字が 0 から数え上がる。桁区切り・小数はそのまま）`underline`（下線が引かれ、線の上へせり上がる）`shine`（光の帯が走って濃くなる）
  `fill`（輪郭の字に下から色が満ちる）`echo`（色の残像を引いて滑り込む）`shuffle`（入れ替わった字が正しい位置へ並ぶ）`grow`（足元から伸びる）`zipper`（上と下から噛み合う）。全部で 44 種。
- 演出の層（`fx`）: `particles` `stars` `bokeh` `rays` `speedlines` `grid` `waves` `gradient` `aurora` `plexus` `contour` `shapes` `blobs`
  `embers` `halftone` `warp` `pulse` `bubbles` `matrix` `cubes` `fog`（横に流れる霧）（部品の下）・`scanlines` `confetti` `vignette` `sweep` `noise` `rain` `snow` `film` `leaks` `spotlight` `sparkles`
  `fireworks`（花火）`hud`（四隅の括弧と目盛り）`frame`（二重の線の額縁）`petals`（花びら）（上）。全部で 36 種。
- 動き方（場面か台本の `ease`・`order`）: 緩急 `smooth`（既定）・`spring`・`snappy`・`bouncy`・`elastic`・`calm`・`linear`（一定の速さ）・`hold`（中ほどでためる）・`steps`（コマ送り）、現れる順 `reverse`・`center`・`edges`・`random`・`alternate`・`zigzag`（項目を順に出す部品に効く）。
  `"fx": false` で性格の既定も止める。1 場面に 1〜2 個まで。
- カメラの型（`camera` に名前）: `push-in` `pull-out` `pan-left` `pan-right` `rise` `punch` `tilt` `drift` `dolly` `crash-zoom` `orbit` `pan-reveal` `rack-focus`（ぼけから合う）`breathe` `sink` `handheld`
  `whip-in`（横から流れ込んで止まる）`dutch`（傾いたまま寄る）`survey`（寄ったまま見て回り、全体へ引く）`step-in`（2 段で寄る）`sway`（振り子のように傾いて収まる）。全部で 21 種。
  自分で書くときも、鍵の点に `blur`（px）を書けばピントが動く。
- 画面の揺れ: `"shake": [{"at": 0.4, "amp": 18, "dur": 450}]`（`slam`・`impact`・`countdown`・判子は自動で揺れる）。
- 強い動き（`slam`・揺れ・破片・`flash`・`glitch`）は見せ場だけに使う。全場面を強くすると、どれも強調にならない。
- **章の札と進み具合**（台本の `chrome`。動画にも入る）: `label`（既定。左上に「01 / 05 章名」）・`tab`（左の端から差し色の札）・`dots`（章の数の点。今の章の点が伸びて進み具合になる）・
  `number`（番号だけ）・`bar`（既定の札＋下の端に章ごとに区切った進み具合の線）。`false` で出さない。
- **字幕の形**（台本の `caption`）: `box`（既定）・`outline`・`band`・`card`（`player.md`）。

## 重ねの層とカメラ

- どの場面にも、**重ねの層**（`overlays`: 注記・矢印・強調・スポットライト・バッジ・カーソル・OS 風の通知・
  破片・波紋・紙吹雪・判子・手書きの丸・蛍光ペン・手書きの下線 `underline`・取り消し線 `strike`・手書きの × `cross`・四隅の括弧 `bracket`・数え上がる数字の札 `counter`。全部で 18 種）と **カメラ**（`camera`: 寄る・引く・移る・傾く。型の名前でも書ける）を付けられる。部品の見た目を崩さずに演出を足す手段で、`custom` より先に使う。
