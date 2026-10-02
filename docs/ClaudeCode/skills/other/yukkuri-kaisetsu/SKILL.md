---
name: yukkuri-kaisetsu
description: ゆっくり解説・ずんだもん解説のような、2 人のキャラクターが左右で掛け合いながら解説する動画（単一 HTML）を作る。台本は「話し手: せりふ」を並べるだけ。立ち絵（口パク・まばたき・表情・気持ちの印）、話し手の色の字幕、中央の黒板（箇条書き・数字・図・画像）、BGM、効果音を motion-video の仕組みで組み、声は VOICEVOX（ローカル）で自動で作るか、用意した WAV を使う。クレジットは締めの画面に自動で出る。「ゆっくり解説を作って」「ずんだもんに解説させて」「掛け合いの解説動画」などと言われたときに使用する。
---

# yukkuri-kaisetsu — 掛け合いの解説動画を作る

台本（テキスト）→ `kaisetsu.py` → motion-video の台本（JSON）→ 単一 HTML。
描画・プレイヤー・字幕・BGM・効果音は隣の **motion-video** スキルの仕組みを使う（同じ場所に置く）。

- 登場人物は左右に立ち、話している方が弾み、口が動く（音声ファイルがあれば音量に合わせて、無ければ文字の拍で）。まばたきする。
- せりふごとに表情（`smile` など）・気持ちの印（`!` `?` `♪` `💦` `💢`）・揺れを付けられる。
- 中央の黒板には、motion-video のどの部品でも置ける（箇条書き・数字・グラフ・流れ・画像…）。
- 立ち絵が無くても、仮のキャラクター（色つきの丸顔）で最後まで作れる。後から画像を置けば差し替わる。

## 手順

### 0. 素材を集める
- 何を解説するか、誰が見るか、元の資料を会話とリポジトリから集める。足りなければ聞く。
- 立ち絵・BGM がすでに手元にあるか確かめる（`chars/<名前>/`・`bgm/` にあるか）。無くても作れる。

### 1. 選ばせる（`AskUserQuestion` を 1 回、最大 4 問）
1. **登場人物**（「登場人物」）: ずんだもん＋四国めたん（おすすめ。VOICEVOX で声まで自動）／霊夢＋魔理沙（ゆっくり。声は WAV を用意するかブラウザの声で代用）／
   春日部つむぎ＋ずんだもん／仮のキャラクター（画像・声なし。試しに）。
2. **声**（「声」）: VOICEVOX で作る（おすすめ。VOICEVOX を起動しておく）／用意した WAV を使う／ブラウザの読み上げ（試し。声は環境による）。
3. **BGM**（「BGM」）: motion-video の曲（`calm`・`study`・`happy` など。おすすめ）／用意した音声ファイル（フリー素材）／なし。
4. **長さ**（「長さ」）: 3 分前後（おすすめ）／1 分（ショート）／5〜10 分。

引数や会話で分かっている項目は聞かない。

### 2. 台本を書く（`<名前>.txt`）

```text
---
title: ずんだもんと学ぶ「並行作業」
cast: zundamon, metan
theme: daylight
motion: playful
music: calm
pronounce: {"Sodashitsu": "ソダシツ"}
---
# 導入
@board title: 並行作業のコツ | ずんだもんと四国めたん
zundamon: ずんだもんなのだ！ [!]
metan(smile): 四国めたんよ。今日は並行作業のコツを話すわね。
zundamon(surprised, shake): えっ、そんなに大事なのだ？ [!?]
(間 0.8)

# 仕組み
@board bullets: 3 つのコツ | 並べて見る | 待ちを知らせる | 任せる
metan: コツは 3 つあるの。
@board {"type": "gauge", "value": 82, "unit": "点", "label": "満足度"}
@transition: whip
zundamon(smile): 満足度は 82 点なのだ♪ [♪]
```

| 書き方 | 意味 |
|---|---|
| 先頭の `---` の間 | 設定。`cast`（左から並ぶ。プリセットは `--list-casts`、知らない名前は仮のキャラクター）・`theme`・`motion`・`music`（曲の名前か `bgm/曲.mp3`）・`music_credit`・`pronounce`（読み方。字幕はそのまま）・`<名前>.credit`（立ち絵の作者の表記）・`voice_credit`（VOICEVOX 以外の声の表記。VOICEVOX で作ったときは自動）・`<名前>.color`・`<名前>.side`・`<名前>.name`・`bg`（全場面の背景）。` # ` 以降は注記 |
| `# 見出し` | 章（チャプター） |
| `@board …` | 黒板。ここから新しい場面になる |
| `話し手: せりふ` | せりふ。`話し手(表情, shake)` で表情と揺れ、行末の `[!]` `[?]` `[!?]` `[♪]` `[💦]` `[💢]` で気持ちの印 |
| `(間 0.8)` | 前のせりふの後に間を空ける（秒） |
| `@bg: 画像`・`@transition: 名前`・`@fx: 名前, 名前` | 次の場面の背景・切り替え・演出の層 |
| `@music: 曲` | その章の曲 |
| `// …` | 注記（読み飛ばす） |

- 黒板の短い書き方: `title: 題 | 副題`・`bullets: 見出し | 項目 | …`・`steps: 見出し | 手順 | …`・`cards: 見出し | 名前 — 説明 | …`・
  `stats: 見出し | 3倍 速さ | …`・`statement: 行 | 行`・`image: パス | 説明`。それ以外は JSON で motion-video の部品を書く（`build.py --list`）。
- 表情: `normal` `smile` `surprised` `angry` `sad` `think` など（立ち絵にその表情が無ければ normal）。仮のキャラクターは smile・surprised・angry を描き分ける。
- 1 つのせりふは字幕 2 行（40 字）まで。長い説明は 2 つのせりふに分ける。ボケとツッコミ、問いと答えを交互に。
- 構成の目安（3 分）: 導入（あいさつ・今日の話題）→ 本題 3〜4 章（黒板を 1〜3 枚ずつ）→ まとめ（要点の黒板）。締めのクレジットは自動で付く。

### 3. 確かめて作る

```bash
python3 <skill_dir>/kaisetsu.py 台本.txt --timeline            # せりふの時間割り（声が無いときは見積もり）
python3 <skill_dir>/kaisetsu.py 台本.txt --voicevox            # VOICEVOX で声を作ってから HTML（作り済みの声は使い回す）
python3 <skill_dir>/kaisetsu.py 台本.txt --voices-dir voices/  # 用意した WAV を名前順にせりふへ当てる
python3 <skill_dir>/kaisetsu.py 台本.txt                        # 声なし（ブラウザの読み上げ）で HTML
```

- VOICEVOX は既定で `http://127.0.0.1:50021`（`--voicevox-url` で変える）。起動していなければ、その旨のエラーで止まる。
- 声は `<台本名>_voices/` に WAV で保存され、動画の長さは WAV の長さで決まる。口は WAV の音量で動く。
- 途中の台本（motion-video の JSON）は `<台本名>.json` に出る。細かい調整はそれを直して `motion-video/build.py` で作ってもよい。
- 作ったら 1 回開いて、黒板の文字の大きさ・字幕の長さ・掛け合いの間を見る。

**YouTube・YMM4・AviUtl 用に書き出す**（「YouTube に上げたい」「ゆっくりMovieMaker で仕上げたい」「AviUtl で編集したい」と言われたとき）

```bash
python3 <skill_dir>/kaisetsu.py 台本.txt --voicevox --export youtube,ymm4 --win-dir "C:\Users\me\Videos\台本_export"
```

- `<台本名>_export/` に、字幕（SRT・VTT。「名前：せりふ」）・概要欄に貼るチャプターとクレジット・YMM4 の台本 CSV（A 列キャラクター名・B 列セリフ）と `.ymmp`・AviUtl の `.exo`・せりふの声（`voices/`）が出る。
  種類と置き方は motion-video の SKILL.md の「編集・投稿用に書き出す」と、書き出した `README.txt`。
- 映像（字幕・音なし WebM）と音（声・音楽・効果音・全部の WAV）は、HTML の ⚙ から書き出して同じフォルダに置く。
- YMM4 の CSV は、YMM4 側のキャラクター名（例: 「ずんだもん」「四国めたん」）と A 列の名前が一致している必要がある。違うときは台本の `<名前>.name` を YMM4 の名前に合わせる。

### 4. 渡す
- HTML の場所を伝える（`SendUserFile`）。
- **素材の規約を確かめるよう一言添える**（`assets.md` の確認表）。とくに公開・収益化するとき。締めのクレジットの表記が足りているか。

## 立ち絵の置き方（詳しくは assets.md）

```
台本.txt
chars/zundamon/normal.png  normal_open.png  normal_half.png  normal_blink.png  smile.png  smile_open.png …
chars/metan/…
```

`<表情>.png`（口を閉じた絵）・`_open`（開いた口）・`_half`（半開き）・`_blink`（目を閉じた絵）。無い組み合わせは近いもので代わる。
PSD の立ち絵は、表情と口ごとに PNG で書き出して置く（このスキルは PSD を読まない）。

## メモ
- 登場人物の色・位置・名前は台本の先頭で変えられる（`zundamon.color: #5fae45`・`metan.side: right`・`a.name: 先生`）。
- プリセットは `casts.json`。声の高さ・速さ（VOICEVOX の `speed`・`vv_pitch`、ブラウザの `pitch`・`rate`）もここで変える。
- 仕組みは motion-video の `cast`・`talk`・`lines`（`build.py --list` の talk）。JSON で直接書けば、掛け合いを部品の場面と混ぜることもできる。
