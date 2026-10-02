---
name: yukkuri-kaisetsu
description: ゆっくり解説・ずんだもん解説のような、2 人のキャラクターが左右で掛け合いながら解説する動画（単一 HTML）を作る。台本は「話し手: せりふ」と、画面に出す絵（@show）を並べるだけ。挿絵・写真・矢印・吹き出しで見せる画面、パーツを重ねて動く立ち絵（表情・体・26 種の動き・聞き手の反応・気持ちの印）、話し手の色の字幕、BGM、効果音を motion-video の仕組みで組み、声は VOICEVOX（ローカル）で自動で作るか、用意した WAV を使う。クレジットは締めの画面に自動で出る。「ゆっくり解説を作って」「ずんだもんに解説させて」「掛け合いの解説動画」などと言われたときに使用する。
---

# yukkuri-kaisetsu — 掛け合いの解説動画を作る

台本（テキスト）→ `kaisetsu.py` → motion-video の台本（JSON）→ 単一 HTML。
描画・プレイヤー・字幕・BGM・効果音は隣の **motion-video** スキルの仕組みを使う（同じ場所に置く）。

動画づくりは 3 つのスキルに分けてある。**テーマだけ渡されたら、台本は yukkuri-script の手順で作る**（調べる → 事実の一覧 → 構成 → 台本 → 検査）。

| 工程 | スキル | 作るもの |
|---|---|---|
| 1. 調査と台本 | **yukkuri-script** | `<名前>.facts.md`（事実と出典）・`<名前>.outline.md`（構成）・`<名前>.txt`（台本） |
| 2. 動画 | **yukkuri-kaisetsu**（これ） | `<名前>.html`（動画）・`<名前>.info.json`（章の時刻・クレジット） |
| 3. 公開まわり | **yukkuri-publish** | 題の案・`<名前>.description.txt`（概要欄）・`<名前>.thumbnail.png`（サムネイル） |

## 画面の作り（手本の動画に合わせてある）

視聴回数の多い解説動画は、**ほぼ全部の画面に絵がある**（写真・挿絵・地図・絵と矢印の図）。箇条書きはほとんど無く、文字は短い名札と一言だけ。
絵はせりふ 1〜3 個ごとに替わる（`research.md` の 11）。このスキルの画面も同じ作りにしてある。

- **絵で見せる場面**（`@show`）: 背景の上に、絵・写真・矢印・短い言葉、動くアイコン・グラフなどの部品・描き下ろしの図解を並べる。絵は順にぽんと現れ、ゆっくり浮く。せりふごとに替えられる。
- **立ち絵**: 左右に大きく立ち（足元は画面の下に切れる）、絵に少し重なる。パーツ（体・表情・まばたき・口）を重ねて描くので、表情・体・動きを自由に組み合わせられる。
  口は声の大きさで動き、話している間は声に合わせて弾む。聞いている側は反応し、しばらくすると素の顔に戻る。
- **字幕**: 画面の下に 2 行まで。白い字に、話し手の色の太い縁。山場は大きく出せる。
- **左上の札**: 章の題が出る（`@tag:` で変える）。
- 立ち絵が無くても、仮のキャラクター（色つきの丸顔）で最後まで作れる。

## 手順

### 0. 素材を集める
- 何を解説するか、誰が見るか、元の資料を会話とリポジトリから集める。テーマだけなら yukkuri-script へ。
- 立ち絵・BGM がすでに手元にあるか確かめる（`chars/<名前>/`・`bgm/`）。無くても作れる。

### 1. 選ばせる（聞くのは、会話から分からないときだけ。`AskUserQuestion` を 1 回）
1. **登場人物**: ずんだもん＋四国めたん（おすすめ。VOICEVOX で声まで自動）／霊夢＋魔理沙（ゆっくり。声は WAV を用意するかブラウザの声で代用）／
   春日部つむぎ＋ずんだもん／仮のキャラクター。VOICEVOX の話者は 43 人ともプリセットにいる（`--list-casts`）。
2. **声**: VOICEVOX で作る（おすすめ）／用意した WAV／ブラウザの読み上げ（試し）。
3. **BGM**: 集めたフリー BGM（18 曲。HTML が 3〜9MB 大きくなる）／motion-video の曲（合成なので軽い）／用意した音声ファイル／なし。
4. **長さ**: 3 分前後（おすすめ）／1 分／5〜10 分。

### 2. 台本を書く（`<名前>.txt`）

```text
---
title: 空はなぜ青いのか
cast: metan, zundamon
roles: metan=解説, zundamon=聞き手
bg: sky
music: espresso
speed: 1.15
pronounce: {"nm": "ナノメートル"}
---
# つかみ
@show: 波 "海" | → | "空が青いのは/海の色が映るから？"
zundamon(smug, fold, bounce): 空が青いのは、海の色が映ってるからなのだ！ [♪]
metan(angry-, chin, big): それ、よくある勘違いよ。 [💢]
> zundamon(surprised, squash) [ガーン]

# 青は散らばりやすい
@show: 太陽 | → | 分子 "空気の分子" > "ぶつかる！" | → | 青い丸 "青はあちこちへ"
metan(point): 光は、空気の小さな分子にぶつかると、あちこちに散らばるわ。
metan(think, chin | smug, point): そして、|波の短い光ほど、強く散らばるの。
@show: 青い丸 "青" | "**5.9 倍**/散らばる" | 赤い丸 "赤" | note: 波の長さの 4 乗に反比例
zundamon(surprised+, jump, big): 5.9 倍！？ そんなに！？ [!?]
@show: mars_sunset | note: 火星の夕日は、青い
```

| 書き方 | 意味 |
|---|---|
| 先頭の `---` の間 | 設定（下の「設定」）。` # ` 以降は注記 |
| `# 見出し` | 章（チャプター）。左上の札にも出る |
| `@show: …` | **絵で見せる画面**。次のせりふから、この絵に替わる（場面は切り替えない）。`|` で区切って並べる（4 つまでが見やすい） |
| `話し手(表情, 体, 動き): せりふ [印]` | せりふ。`( )` と `[ ]` は省ける |
| `> 相手(表情, 動き) [印] @0.6` | 直前のせりふの間の、**相手の反応**。`@0.6` は、せりふの 6 割の所で（省くと半分の所） |
| `(間 0.8)` | 前のせりふの後に間を空ける（秒） |
| `@tag: 言葉`・`@corner: 言葉` | 左上の札（既定は章の題。空にすると出さない）・右上の札（「3. 北センチネル島」のような項目名） |
| `@bg: 名前か画像`・`@transition: 名前`・`@fx: 名前, 名前` | 次の場面の背景・切り替え・演出の層（ここで場面が切り替わる） |
| `@board …` | 白い黒板の場面（数字のカード・グラフ・まとめの箇条書きなど。下の「黒板」） |
| `@music: 曲` | その章の曲 |
| `// …` | 注記（読み飛ばす） |

#### 絵で見せる画面（`@show`）

`|` で区切った 1 つずつが、左から並ぶ。

| 書くもの | 例 | 出るもの |
|---|---|---|
| 絵の名前 | `太陽`・`images/prism.png`・`mars_sunset` | `images/` の絵（拡張子は省ける）。写真（JPEG）は白い縁つき。ほかの絵にも縁を付けるなら後ろに `frame` |
| 絵 ＋ 名札 | `分子 "空気の分子"` | 絵の上に、色つきの名札 |
| 絵 ＋ 吹き出し | `男性科学者 "ティンダル" > "青が散らばるぞ"` | 絵の上に吹き出し（絵の中の人や物にしゃべらせる） |
| 短い言葉 | `"原因は/ちりや水滴？"`・`"もう卒業！" red` | 太い縁の大きな字。`/` で改行、`**…**` は黄色。色は `red` `yellow` `blue` `green` |
| 記号 | `→` `←` `＋` `×` `＝` `vs` `？` | 絵と絵の間の矢印・記号 |
| `title: …` | `title: 空はなぜ青いのか` | 上の見出し |
| `note: …` | `note: 火星の夕日は、青い` | 下の一言（黄色） |

- **絵を先に集める**。挿絵は `python3 <skill_dir>/illust.py get 太陽 波 目`（日本語の言葉で約 1,500 点から。`search` で候補）、
  写真は `python3 <skill_dir>/fetch_images.py search "検索語"` → `get 3 --as 名前`。どちらも `images/` に入り、クレジットは自動で出る。
  **人物・しぐさ・場面の絵**（困っている会社員・実験する人・買い物の場面 など）は、irasutoya スキルがあれば
  `python3 ../irasutoya/irasutoya.py search "困っている|悩んでいる" 会社員 --sheet` → 見本を Read で見て → `get 3 --dir images --as 困る人`（探し方のこつは irasutoya の SKILL.md）。
  いらすとやの絵は、**素材としての再配布が不可**（HTML は手元だけで使い、配るのは WebM の動画）、**収益化した動画は 1 本 20 点まで**（サムネイルを含む。作るときに点数が出る）。
  自分で用意した絵（いらすとや など）は `images/` に置けば名前で使える（規約は `assets.md`）。
- 写真は 1 回開いて、話に合っているかを見る（`Read`）。見つからない絵は、名前が文字で出て `warn:` が出る。
- **ほとんどの画面を絵にする**。1 つの絵でせりふ 1〜3 個。同じ絵のまま 15 秒（本編は 25 秒）を超えない。
  数字は `"**5.9 倍**"` のように言葉で大きく出す。箇条書きの黒板は、まとめだけ。
- 物ごとの関係は、絵と記号で書く: `原因 | → | 結果`・`A | vs | B`・`A | ＋ | B | ＝ | C`。人や物に吹き出しでしゃべらせると、小さな寸劇になる。

##### 動く図で見せる（アイコン・部品・描き下ろし）

絵の代わりに、プログラムが描いて動かす図を、絵と同じ場所に置ける。素材の絵に無い「仕組み・量・流れ」に使う。

| 書き方 | 出るもの | 向くもの |
|---|---|---|
| `icon:名前 "名札" > "吹き出し"` | 線で描かれて、動き続けるアイコン（白い丸の上。105 種。`python3 ../motion-video/build.py --list-icons`） | 記号で足りる物・概念（太陽・地球・時計・お金・人・歯車） |
| `part:{部品の JSON} "名札"` | motion-video の部品（棒・円・メーター・年表・流れ図・ベン図 など 85 種。`build.py --list`）を、白い板の上に | 数の比べ・割合・順番・関係 |
| `@draw: 名前`（`@show: draw:名前 \| note: …` と同じ） | **描き下ろしの図解**。`scenes/名前.js`（台本の隣でもよい）を、濃い板の上に描く。後ろに `light`（白い板）・`none`（板なし） | 話題に固有の仕組み（光が散らばる・水が回る・力がつり合う） |

```text
@show: icon:sun "太陽" | → | icon:globe "地球" > "8 分で届く"
@show: part:{"type":"bars","heading":"散らばりやすさ","unit":"倍","items":[{"label":"青","value":5.9},{"label":"赤","value":1}]} | "青は/約 6 倍" blue
@draw: scatter | note: 青い光ほど散らばる
```

- 部品は、ほかの絵より広く取る（1 つなら幅いっぱい）。それでも字は黒板（`@board`）より小さいので、項目は 2〜4 個まで。細かい表・長い文の部品は `@board` に出す。
- **描き下ろし**（`scenes/名前.js`）は、motion-video の `custom` と同じ `(ctx, lt, d, H, s)` の本体を書く。手本は `examples/scenes/scatter.js`（光の散らばり・3 段）と `examples/scenes/sunset.js`（夕焼け・2 段）。
  - `s.box`（`{x, y, w, h}`）が描く範囲（立ち絵と字幕に隠れない所。板もここに敷かれる）。位置は `s.box` からの割合で決める。
  - `lt` はこの図が出てからの ms。`s.cue(1)` は次のせりふ、`s.cue(2)` はその次のせりふが始まる ms（せりふに合わせて段を進める）。
  - **時刻 `lt` だけで姿が決まる**書き方にする（`Math.random`・`Date` は使わない。乱数は `H.rand(種)`）。道具は `H.txt`・`H.clamp`・`H.eo`・`H.arrow`・`H.icon`・`H.sub` など（motion-video の SKILL.md の「custom」）。
  - 描く途中でエラーになると、そこから先が描かれず、板の下に赤い字で「draw のエラー: …」と出る（色を混ぜる道具は無い。`H.mix` は数の補間なので、色は自分で `rgb(…)` を作る）。
  - 1 つの図で言うことは 1 つ。字は 44px 以上、線は 10px 以上。色は 3 色まで。名前は図の余白に置き、線と重ねない。
  - 作ったら、その時刻の画面を撮って見る（`kaisetsu.py 台本.txt --shots 6.5,10`。時刻は `--timeline` で分かる）。段が進む前・後の 2 枚は必ず見る。
- 描き下ろしは山場の 1〜2 か所に絞る（手間がかかり、出来がばらつく）。ほかは素材の絵・アイコン・部品で回す。

#### せりふと演技

`( )` には、**表情・体・動き**のラベルを順不同で並べる。ラベルと説明は `labels.json`、その立ち絵にあるものは `python3 <skill_dir>/kaisetsu.py --list-casts <名前>`。

- **表情**（12）: `normal` `smile` `surprised` `angry` `sad` `troubled` `think` `shy` `smug` `doubt` `dizzy` `love`。
  度合いは `smile-`（控えめ）・`smile+`（強め）。同じラベルに形がいくつもある立ち絵では、使うたびに違う形が順に出る。名指しは `smile#2`。
- **体**: ポーズ `point` `raise` `peace` `fold` `chin` と、持ち物 `mic` `phone` `book` など（立ち絵による）。`point, mic` で両方を満たす体。
- **動き**（26）:
  - 弾む: `bounce`（弾み続ける）`jump`（跳ねる）`hop`（小さくはずむ）`dance`（るんるん）`spin`（くるっと回る）
  - うなずく・首: `nod`（うなずく）`tilt`（かしげる）`shakehead`（いやいや）`bow`（おじぎ）
  - 寄る・引く: `lean`（前のめり）`peek`（ずいっと寄る）`back`（のけぞる）`away`（後ずさり）`turn`（そっぽを向く）
  - 沈む・震える: `sink`（沈む）`shrink`（しゅんと小さく）`squash`（ぺしゃっ）`tremble`（震える）`stomp`（じたばた）`zukkoke`（ずっこける）
  - 大きく・ゆれる: `zoom`（どーんと大きく）`stretch`（のびる）`pulse`（どきどき）`sway`（ゆらゆら）`float`（ふわふわ）、`still`（止まる）
  - `jump+`・`sway-` で大きさ。書かなければ、表情に合った動きになる。
- **せりふの途中で変える**: `metan(think, chin | smug, point): うーん…|わかったわ！` — `( )` の中と文の中を `|` で区切ると、その位置で演技が替わる。
- **相手の反応**: せりふの次の行に `> zundamon(surprised, back) [!?]`。書かなければ、控えめな反応（うなずく・驚く・考える・あきれる）が自動で付く（`react: off` で止める）。
- **そのほか**: `big`（字幕を大きく出す。ツッコミ・山場）・`shake`（画面ごと揺らす）・`se:tada`（効果音を名指し。一覧は `python3 ../motion-video/build.py --list-sounds`）・
  `voice:ささやき`（声のスタイルを名指し）。
- **印**（行末の `[ ]`）: `!` `?` `!?` `♪` `…` `💦`（汗）`💢`（怒り）`💡`（ひらめき）`✨`（きらきら）`♥` `ガーン` `ショック` `zzz`。
  絵文字の書体に頼らず線で描くので、どの環境でも同じに出る。印に合った効果音が鳴る（続けては鳴らさない。`se: off` で止める）。
- ラベルを書かなかったせりふには、中身から演技が自動で付く（控えめ。`acting: off` で止める）。話の山は自分で付ける。
- 声は表情に合うスタイルに自動で切り替わる（その話者にあるときだけ。ずんだもんの `sad` → なみだめ、`angry` → ツンツン、`shy` → あまあま。`voice_style: off` で止める）。
- 無いラベルは近いもので代わり、`warn:` で知らせる。warn が出たら台本を直すか、そのままでよいかを判断する。
- 1 つのせりふは字幕 2 行（40 字）まで。使い分けの表は yukkuri-script の `patterns.md`。

#### 設定（先頭の `---` の間）

| 項目 | 中身 |
|---|---|
| `title`・`cast`・`roles` | 題・登場人物（左から。プリセットは `--list-casts`）・役（`metan=解説, zundamon=聞き手`。自動の演技と反応に使う） |
| `bg`・`music`・`theme`・`motion` | 全場面の背景・曲（名前は `--list-assets`）・配色・動きの性格 |
| `speed`・`<名前>.speed` | 話速の倍率（既定 1.1。解説動画の定番は 1.15〜1.25） |
| `pronounce` | 読み方（`{"nm": "ナノメートル"}`。字幕はそのまま） |
| `subtitle`・`subtitle_size`・`subtitle_name` | 字幕の形（`outline` 既定・`box` 白い箱）・大きさ（既定 56）・名札を出すか |
| `font`・`text_font` | 字幕の書体（`fonts.json` の名前。既定 `rounded`。使う字だけ埋め込む。`off` で OS の書体）・`same` で画面の文字ぜんぶを同じ書体に |
| `cast_height`・`cast_offset` | 立ち絵の高さ（既定 700）・下にずらす量（既定 110） |
| `art`・`<名前>.art` | `png` で、SVG の立ち絵（`chars/<名前>/svg/`）があっても PNG のパーツを使う |
| `<名前>.name`・`.color`・`.side`・`.credit` | 表示名・色・左右・立ち絵の作者の表記 |
| `acting`・`react`・`voice_style`・`se`・`relax`・`tags`・`cast_motion` | `off` で、自動の演技・自動の反応・声のスタイルの切り替え・印の効果音・素の顔に戻る動き・左上の札・立ち絵の動き を止める |
| `music_credit`・`voice_credit`・`credit` | クレジットに足す表記 |
| `length`・`facts`・`summary`・`tags`・`thumb` など | yukkuri-script・yukkuri-publish が読む |

#### 黒板（`@board`）

白い板に motion-video の部品を置く場面。絵で見せられないものに使う（グラフ・表・コード・まとめ）。
`title: 題 | 副題`・`bullets: 見出し | 項目 | …`・`steps: 見出し | 手順 — 補足 | …`・`cards: 見出し | 名前 — 説明 | …`・`stats: 見出し | 3倍 速さ | …`・
`statement: 行 | 行`・`image: パス | 説明`。それ以外は JSON（`@board {"type": "gauge", "value": 82}`。部品の一覧は `python3 ../motion-video/build.py --list`）。

#### 背景と BGM

`python3 <skill_dir>/kaisetsu.py --list-assets` に、名前と説明が出る（`backgrounds.json` 59 枚・`bgm.json` 18 曲）。
背景は話の中身で変える（`@bg: library`。時間帯は `_evening`・`_night`）。最初から最後まで同じ背景にしない。クレジットは自動で出る。

### 3. 確かめて作る

```bash
python3 <skill_dir>/kaisetsu.py 台本.txt --readings            # VOICEVOX がどう読むか（かな）を出す。読み間違いを先に直す
python3 <skill_dir>/kaisetsu.py 台本.txt --timeline            # せりふの時間割り
python3 <skill_dir>/kaisetsu.py 台本.txt --voicevox            # VOICEVOX で声を作ってから HTML（作り済みの声は使い回す）
python3 <skill_dir>/kaisetsu.py 台本.txt --voicevox --shots 6.5,0:42   # その時刻の画面を PNG に撮る（<台本名>_shots/。Read で開いて、絵・図・立ち絵の見え方を見る）
python3 <skill_dir>/kaisetsu.py 台本.txt --voicevox --compact  # HTML を小さく（声を 16kHz に、背景と写真を幅 1280 に。さらに小さくするなら --voice-rate 12000。こもった声になる）
python3 <skill_dir>/kaisetsu.py 台本.txt --voices-dir voices/  # 用意した WAV を名前順にせりふへ当てる
python3 <skill_dir>/kaisetsu.py 台本.txt --yukkuri-bat          # 霊夢・魔理沙のせりふを、Windows の AquesTalkPlayer で WAV にするバッチファイルを書く
python3 <skill_dir>/kaisetsu.py 台本.txt                        # 声なし（ブラウザの読み上げ）で HTML
python3 <skill_dir>/kaisetsu.py 台本.txt --voicevox --dist     # 配布用（⚙ の書き出しを省いて小さくする。motion-video の --dist）
```

- **声を作る前に `--readings` を見る**。固有名詞・英字・数字・むずかしい漢字の読みを確かめ、違っていたら `pronounce` に足す。
- 霊夢・魔理沙の声は、ゆっくりボイス（AquesTalk1）。`--voicevox` を付けると作る。`aquestalk/` に置いてあるものから自動で選ぶ:
  鍵つきのライブラリ → AquesTalkPlayer を Wine で動かす（無償の道）→ 評価版のライブラリ（「ヌ」になる）。どれも無ければブラウザの読み上げ。
  今どれが使われるかは `python3 <skill_dir>/aquestalk.py --check`。入手と準備は `assets.md` の「声」。Wine が使えない環境では `--yukkuri-bat`。
- VOICEVOX は既定で `http://127.0.0.1:50021`。声は `<台本名>_voices/` に WAV で保存され、動画の長さは WAV の長さで決まる。
- 大きさの目安: 声は 1 分で約 4MB（`--compact` で約 2.5MB）、BGM のファイルは曲ごとに 3〜9MB。アーティファクトに載せる（16MB まで）なら、3 分までで `--compact`。
- 字幕の書体を埋め込むには fontTools が要る（`pip install fonttools`。無ければ OS の書体で描く）。
- 章の時刻・クレジット・画像の出どころは `<台本名>.info.json` に出る。途中の台本（motion-video の JSON）は `<台本名>.json`。
- **作ったら画面を見る**。絵が立ち絵や字幕に隠れていないか、名札が読めるか、同じ絵が長く続いていないか。

**YouTube・YMM4・AviUtl 用に書き出す**（「YouTube に上げたい」「ゆっくりMovieMaker で仕上げたい」「AviUtl で編集したい」と言われたとき）は、
**video-export スキル**に台本（.txt）をそのまま渡す。YMM4 の台本 CSV の名前は、台本の `<名前>.name` を YMM4 のキャラクター名に合わせる。

### 4. 渡す
- HTML の場所を伝える（`SendUserFile`）。公開するなら、yukkuri-publish で題・概要欄・サムネイルを作る。
- **素材の規約を確かめるよう一言添える**（`assets.md` の確認表）。集めた立ち絵・背景・BGM を入れた HTML は配らず、WebM に書き出した動画を配る。

## 立ち絵の置き方（詳しくは assets.md）

```
台本.txt
chars/zundamon/normal.png  normal_open.png  normal_half.png  normal_blink.png  smile.png  smile_open.png …
images/太陽.svg  prism.png  credits.json
```

`<表情>.png`（口を閉じた絵）・`_open`（開いた口）・`_half`（半開き）・`_blink`（目を閉じた絵）。ポーズつきは `<表情>@<ポーズ>.png`。
集めた立ち絵は**パーツの形**（`chars/<名前>/sprite.json` と `sprite/`）で持つ: ポーズごとの体の絵 1 枚と、表情・まばたき・口の小さなパーツを、再生のときに重ねる。
PNG のフォルダは `python3 <skill_dir>/sprite.py <PNG のフォルダ> --out chars/<名前>` でこの形にできる。
台本の隣の `chars/<名前>/` に無ければ、スキルの `chars/<名前>/`（集めた立ち絵。リポジトリには入れない）を使う。動画には台本で使った表情だけが埋め込まれる。
素材からの書き出しは、PSD（PSDTool 形式）なら `psd_export.py`、パーツ画像のフォルダなら `parts_export.py`。配布元・レシピ・規約の要点は `recipes/README.md`。

### 立ち絵を SVG（ベクトル）にする

パーツを 1 つずつ、色の塊ごとに輪郭をなぞって SVG にできる（`chars/<名前>/svg/`。vtracer が要る: `python3 -m pip install --user vtracer`）。
`svg/` があれば動画はそちらを使う。エンジンは SVG を Canvas に描くので、**「WebM で保存」の録画にも、シークバーのプレビューにも映る**。

```bash
python3 <skill_dir>/psd_export.py   素材.psd       --recipe recipes/<名前>.json --out chars/<名前> --svg     # PNG のパーツと、svg/ の両方を作る
python3 <skill_dir>/parts_export.py パーツのフォルダ --recipe recipes/<名前>.json --out chars/<名前> --svg
python3 <skill_dir>/sprite.py chars/<名前> --compare     # svg/compare.png（上が PNG、下が SVG。全身と、顔を大きくしたもの 4 つ）
```

| | SVG | PNG |
|---|---|---|
| 大きく映す・寄る・全画面 | 輪郭が荒れない（映す高さの 2 倍で作る） | 高さ 720 の絵を引き伸ばすので、ぼやける |
| 大きさ | **PNG の 1.2〜3 倍**（動画 1 本で 1〜3MB 増える。16MB までのアーティファクトに載せるなら `art: png`） | — |
| 質感 | ぼかし・グラデーションは色の段になる（頬の赤みが少し薄くなる）。半透明は不透明か透明かになる | 元のまま |

- **作ったら `--compare` の絵を Read で開いて見比べる**。見る所は 4 つ: 顔の印象、パーツの継ぎ目（目のまわりの四角い色の差・縦横の線）、縁（輪郭の線が太っていないか・黒い塊が出ていないか）、半透明の物（羽衣・ベール）が消えていないか。
  1 つでも崩れていれば、`chars/<名前>/svg/` を消して PNG のままにする。大きさが PNG の 3 倍を超えるものも PNG のままにする。
- **集めた 53 人で試した結果**（2026-10-03）: SVG にしたのは 14 人 — `zundamon` `metan` `ankomon` `zunko` `kiritan` `sora` `whitecul`（坂本アヒルさん）、`voidoll` `benizakura`、公式 SD の 5 人。
  PNG のままにしたのは 39 人 — 大きさが 3 倍を超える（moiky さんの素材の多く・`mochiko`・`aieru`・`no7`。`reimu`・`marisa` は 10 倍以上）、
  継ぎ目が出る（`usagi`・`tsumugi`・`hau`）、半透明の羽衣が消える（`itako`）、縁に黒い塊が出る（`mesuo`）。
- 小さい絵をなぞると目もとが崩れるので、書き出しは `--height` の 2 倍の大きさで絵を描いてからなぞる（`--svg-scale` で変える）。`--detail soft` は色の段を細かく、`mid` は粗く小さくする。
- 仕組み: なぞる前に色を段に分け（ぼかしが色の段として残る）、表情・口・目のパーツは、体の絵に重ねた絵をまわりごとなぞって四角の中だけを使う（境目の形が体の絵と揃う）。
- 台本ごとに選ぶなら `art: png`（全員）・`<名前>.art: png`（その人だけ）。サムネイル（yukkuri-publish）は、いつも PNG のパーツから描く。
- なぞるのは加工に当たる。立ち絵の規約が加工を認めているかを確かめ、作った SVG も素材として配らない（`chars/` はリポジトリに入らない）。

## メモ
- プリセットは `casts.json`。声の高さ・速さ（VOICEVOX の `speed`・`vv_pitch`・`intonation`、ブラウザの `pitch`・`rate`）もここで変える。
- VOICEVOX の話者（43 人）とスタイルの一覧は `speakers.md`。手本の動画から拾った画面の作りと、基準の出どころは `research.md`。
- 仕組みは motion-video の `cast`・`talk`・`lines`。台本の JSON では、せりふに `acts`（途中の演技）・`react`（相手の反応）・`big`・`se`、
  場面に `board: {type: "stage", shots: […]}`・`tag`・`corner`、全体に `talk`（字幕の形など）・`images`・`fonts` を書ける。
