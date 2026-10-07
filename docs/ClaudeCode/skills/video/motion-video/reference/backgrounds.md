# 背景（SVG の背景・ループする動く背景）

手順 2 で、配色の地（色と模様）だけでは場面が寂しいとき・場所や雰囲気を背景で伝えたいときに読む。名前と説明の一覧は `python3 <skill_dir>/build.py --list-bg`、
全部を順に見る動画は `python3 <skill_dir>/build.py --backgrounds -o backgrounds.html`（`--theme` で配色を替えて見られる）。

## 書き方

```json
{ "bg": "soft",
  "chapters": [ { "title": "しくみ", "bg": "grid-fade",
                  "scenes": [ { "type": "title", "title": "…", "bg": "aurora" },
                              { "type": "bullets", "items": ["…"] },
                              { "type": "quote", "text": "…", "bg": {"src": "sky-night", "dim": 0.4} },
                              { "type": "code", "code": "…", "bg": false } ] } ] }
```

- **台本の `bg`** は全場面の地。**章の `bg`** はその章の場面、**場面の `bg`** はその場面だけを替える。`false` で配色の地（色と模様）に戻す。
- 値は、背景の名前・画像のファイル（PNG・JPEG・SVG）・`{"src": 名前かファイル, "dim": 0〜1, "speed": 倍率, "color": 色}` のいずれか。
  - `dim`: 配色の地の色を重ねて背景を抑える割合。絵が強くて字が読みにくいときに `0.3`〜`0.6`。
  - `speed`: 動く背景の速さ（`0.5` で半分）。`color`: 単色の動く背景の色（配色の色の名前 `accent` `accent2` `warn` `ok` か `#rrggbb`）。
- 背景は部品の下に描かれ、カメラ（`camera`）では動かない。演出の層（`fx`）とは別物で、重ねて使える（どちらも動くものを重ねると、うるさくなる）。

## 選び方

- **まず台本の `bg` に静かなものを 1 つ**（`soft` `vignette` `curves` `grid-fade` `flow` など）。見せ場の場面・章の頭だけ、強いものに替える。全場面で違う背景にしない。
- **表・グラフ・コード・画面の画像など、情報の多い場面は静かな背景か `false`**。動く背景は、題・言い切り・引用・締めのように字の少ない場面に向く。
- 動く背景と「配色に合わせる」SVG は、**色が配色（`theme`）に合う**ので、どの配色でも字が読める。
- 「景色・場所」の SVG は**色が決まっている**。暗い絵は暗い配色（紺と真鍮・真夜中など）、明るい絵は明るい配色（日中など）で使う。
  合わないときは作るときに warn が出るので、配色を替えるか `dim` で抑える。
- 掛け合い（`talk`）の場面の `bg` にも、同じ名前を書ける。

## 動く背景（78 種）

どれも継ぎ目なく繰り返す（周期は 2〜60 秒）。時刻だけで決まるので、シーク・書き出しでも同じ画になる。

| 向き | 名前 |
|---|---|
| 色と光（静か） | `flow` `aurora` `bokeh` `rays` `spotlights` `blobs` |
| 波と線 | `waves` `ribbons` `ridges` `ocean` `stripes` `sunburst` |
| 空と粒 | `stars` `meteors` `warp` `galaxy` `rise` `snow` `rain` `bubbles` `fireflies` `petals` `confetti` `sparkles` `clouds` |
| 格子と図形（技術・データ） | `grid-floor` `grid-scroll` `dots-wave` `halftone` `hex-pulse` `tiles` `pixels` `ripples` `radar` `tunnel` `prism` `orbits` `helix` `plexus` `circuit` `matrix` `equalizer` `scan` |
| AI・判断・データの流れ | `neural` `tokens` `branch` |
| 科学 | `molecules` `waveform` `microscope` |
| 医療・体 | `cells` `ecg` |
| 数学 | `plot` `geometry` `lissajous` |
| 歴史・文化 | `sumi` `treerings` `emaki` |
| 地理・旅 | `contours` `route` |
| お金・経済 | `candles` `coins` |
| 宇宙 | `constellation`（ほかに `stars` `meteors` `galaxy` `orbits` `warp`） |
| 自然 | `komorebi` `leaves` `grass`（ほかに `rain` `snow` `fireflies` `petals` `clouds`） |
| 技術 | `servers` `packets` `stack`（ほかに `circuit` `radar` `matrix`） |
| セキュリティ | `vault` `fingerprint`（ほかに `scan`） |
| ほぼ無地（落ち着いた語り） | `fibers` `sheen` `dust`（ほかに `flow` `bokeh`） |
| 和風 | `seigaiha-flow` `asanoha-pulse` `ichimatsu` |
| ポップ | `polka` `balloons`（ほかに `confetti` `stripes`） |

題材のある動く背景（科学〜セキュリティ）は、**話と関係のない静止画を敷くかわり**に使う。絵が出たり消えたりするもの（`plot` `geometry` `route` `constellation` `stack` `sumi`）は、
1 周（14〜24 秒）より短い場面では途中までしか見えない。短い場面には `speed` を上げるか、いつも動いているもの（`molecules` `contours` `packets` など）を選ぶ。
`microscope` `vault` `waveform` `lissajous` `plot` はまん中にも線が通るので、字の多い場面では `dim` で抑える。

## SVG の背景・配色に合わせる（54 枚）

| 向き | 名前 |
|---|---|
| 光とグラデーション（無難） | `soft` `mesh` `vignette` `horizon` `window` `spotlight` |
| 波・線・形 | `wave-bottom` `wave-top` `curves` `soft-shapes` `papercut` `bands` `split` `arcs` `rings` `stairs` |
| 格子・模様（技術・設計） | `grid-fade` `dots-fade` `iso` `hex` `pcb` `blueprint` `network` `topo` `lowpoly` `diagonal` `plus` `chevrons` `speckle` `bars` |
| にぎやか・催し | `burst` `dots-corner` `memphis` `lights` `frame` `gingham` `mizutama` |
| 影絵・場面 | `orbit` `ridge` `city` |
| 和の模様 | `checker` `seigaiha` `asanoha` `shippo` `uroko` `yagasuri` `kagome` `tatewaku` `kanoko` `hishi` |
| 布・木・石の地 | `linen` `woodgrain` `marble` `pinstripe` |

## SVG の背景・景色と場所（63 枚）

| 向き | 暗い絵（暗い配色で） | 明るい絵（明るい配色で） |
|---|---|---|
| 空・自然 | `sky-sunset` `sky-night` `mountains-night` `sea-sunset` `space` `forest` `underwater` `fireworks` `bamboo` `aurora-sky` `moon` `space-station` | `sky-day` `sky-dawn` `mountains` `sea` `desert` `snowfield` `field` `sakura` `autumn` `rainbow` `lake` `island` `park` `countryside` |
| 街・室内・舞台 | `city-night` `curtain` `bookshelf` `studio` `cafe` | `city-day` `room` `washitsu` `shopping-street` `station` `shrine` |
| 学ぶ・働く・暮らす場所 | `server-room` `control-room` `factory` | `classroom` `lab` `library` `meeting-room` `office` `kitchen` `hospital` `harbor` `airport` |
| 紙・板・壁・布 | `blackboard` `cork` `wood` `brick` `blueprint-blue` `stone-wall` `denim` | `whiteboard` `notebook` `graph-paper` `kraft` `washi` `tile-wall` `tatami` |

場所の絵（教室・駅・港など）は、まん中を淡くしてあるが、物の多い絵なので、字の多い場面では `dim`（`0.3`〜`0.5`）で抑える。

## 足すとき

- SVG の背景: `bg_make.py` に `@themed`（色を配色の変数で書く）か `@scenery`（色を決めて書く。`tone` を付ける）の関数を 1 つ足し、`python3 bg_make.py` を回す
  （`bg/<名前>.svg` と一覧 `bg/index.json` ができる。SVG を手で直さない）。
- 動く背景: `parts-backdrops.js` に `def(名前, 周期 ms, function (u, o) {…})` を足し、`build.py` の `BACKDROPS` に説明を足す。
  `u`（周期の中の位置 0..1）だけで描き、`u` に掛ける回数を整数にする（そうしないと継ぎ目で飛ぶ。`../tests/README.md` の回帰テストが確かめる）。
- 動く背景と SVG の背景で、同じ名前を使わない。
