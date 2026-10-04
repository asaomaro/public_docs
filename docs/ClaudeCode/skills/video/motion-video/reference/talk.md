# 掛け合い（登場人物・せりふ）

`talk` の場面（2 人の掛け合い）を motion-video の台本で直に書くときに読む。掛け合いの解説動画を作るなら、yukkuri-kaisetsu スキルが台本からこの形を作る。

```json
"cast": {"zunda": {"name": "ずんだもん", "color": "#5fae45", "side": "right", "height": 520,
                   "images": {"normal": {"closed": "chars/z/normal.png", "open": "chars/z/normal_open.png", "blink": "chars/z/normal_blink.png"}, "smile": "chars/z/smile.png"},
                   "voice": {"pitch": 1.35, "rate": 1.15}}},
"castAlways": true,
"chapters": [{"title": "導入", "scenes": [{"type": "talk", "board": {"type": "bullets", "items": ["…"]}, "bg": "bg/room.png",
  "lines": [{"who": "zunda", "text": "解説するのだ！", "face": "smile", "emote": "!", "voice": "voices/001.wav", "shake": true, "pause": 0.5}]}]}]
```

- `lines` のある場面では、登場人物が左右に立ち、話している方が声に合わせて弾んで口が動く。まばたきする。字幕は話し手の色で映像に描く。
- 口は、`voice`（WAV）があれば音量に合わせて、無ければ文字の拍で動く（どちらも時刻だけで決まる）。`voice` のある場面は WAV の長さで時間を割り付ける。
- 再生の速さ（0.5 倍〜2 倍）を変えても、声（WAV）の高さは変わらない（波形を短い区間に切って重ね直す。速さごとに 1 度だけ作る）。
  高さも一緒に変えたいなら、台本の `audio.keepPitch: false`。
- 立ち絵は `images`（表情ごとに 1 枚の絵を差し替える）か `sprite`（体の絵の上に、表情・まばたき・口のパーツを重ねる）で渡す。`sprite` は
  `{"w", "h", "images": {名前: 画像}, "poses": {"": {"base": 名前, "faces": {"smile": {"e": [名前, x, y], "open": […], "half": […], "blink": […]}}}, "raise": {…}}}`。
  パーツは体の絵の (x, y) にその四角を置き換えて描く（描く順は 体 → e → blink → open か half）。ポーズはせりふの `pose`（無ければ `""`）で選ぶ。
  yukkuri-kaisetsu の `sprite.py` がこの形を作る。画像は PNG でも SVG でもよい（SVG は width・height を画素の大きさで書く。Canvas に描くので録画にも映る）。
  SVG の画像は、base64 にせず文字のまま埋め込む（`'` を含まないもの。2 割ほど小さい）。
- **演技**（時刻だけで決まり、録画にも入る）: せりふの `face`・`pose`・`motion`。せりふの途中で変えるなら `acts: [{"at": 0.5, "face": …, "pose": …, "motion": …}]`（`at` はせりふの中の位置 0〜1）、
  相手の反応は `react: [{"who": 名前, "at": 0.6, "face": …, "motion": …, "emote": "!?"}]`。反応した瞬間は口だけが開く。
  せりふの後 1.5 秒で、いつもの顔（`cast.<名前>.rest`、既定 normal）と姿に戻る。絵が替わるときは、前の絵を重ねて消していく。
- **動き**: いつもの呼吸と小さな揺れ、表情・体が変わったときの弾み、身ぶり。身ぶりは `motion` で選ぶ（26 種。`bounce` `jump` `hop` `dance` `spin` `nod` `tilt` `shakehead` `bow`
  `lean` `peek` `back` `away` `turn` `sink` `shrink` `squash` `tremble` `stomp` `zukkoke` `zoom` `stretch` `pulse` `sway` `float` `still`）。無ければ表情から決まる。
  大きさは `mlv`（無ければ表情の度合い `lv`。1 控えめ・2 ふつう・3 強め）。`face`・`pose` の `smile#2`・`point+mic` などは、`#`・`+` の前のラベルで動きを決める。
  `cast.<名前>.motion: "yukkuri"` は話す間に縦に伸び縮みする（頭だけの立ち絵向け）。`cast.<名前>.motion: false` か `castMotion: false` で止まる。OS の「動きを減らす」で止めるのは、`talk.reducedMotion: true` と書いたときだけ（いつも止めると、その設定の機械では HTML で見る動きと書き出した動画の動きが違ってしまう）。
  パーツの立ち絵（`sprite`）は、口と目のパーツの位置から首の高さを決め、頭だけを首から傾ける（`nod`・`tilt`・`shakehead`・`bow` と、話している間の小さな揺れ）。首の高さを決められない立ち絵は、今までどおり全身で動く。
  絵で見せる画面（`stage`）の並びは、立ち絵が左右に 1 人ずつでないとき（1 人・3 人・4 人）、立ち絵の間の空いている所のまん中に寄せて、その幅に収める。
  `sprite.poses.<ポーズ>.rig`（層の一覧。yukkuri-kaisetsu の `sprite.py` が作る）があれば、腕・髪を軸のまわりに回し、黒目（`iris`）を白目の中でずらして、毎コマ重ね直す（表情のパーツは顔の層だけに当てる）。`talk.rig: false` で動かさない。髪（`k: "hair"`）は細い帯に切って、先ほど大きくずらしてしならせる（`talk.hairBend: false` で丸ごと回す）。腕（`k: "arm"`）は、肩から 3 割は動かさず、ひじのあたりから先だけを同じやり方で動かす（`talk.armBend: false` で肩から丸ごと回す。丸ごと回すと、袖が服の輪郭とつながっている腕が体から離れて見える）。動かし方は `talk.rigMotion`（全員）・`cast.<名前>.rigMotion`（その人）で変える: `{arm: {rest, breath, voice, jump, speed, limit}, hair: {sway, voice, jump, follow, bend, lag, speed, limit}, iris: {listen, wander, wanderListen, every, up}}`（角度はラジアン、時間は ms。書いた項目だけ上書き。yukkuri-kaisetsu は `rig.json` の名前の付いた設定から入れる）。
- **気持ちの印**（`emote`）は線と形で描く（絵文字の書体が無い環境でも出る）: `!` `?` `!?` `♪` `…` `💦` `💢` `💡` `✨` `♥` `gloom`（ガーン）`shock` `zzz`。
- **絵で見せる場面**: `board: {"type": "stage", "shots": [{"line": 0, "items": […], "title": …, "note": …}]}`。白い黒板を置かず、背景の上に絵・写真・矢印・短い言葉を並べる。
  `line` 番目のせりふからその並びに替わる。`items` は `{"img": 名前, "label": 名札, "say": 吹き出し（`/` で改行）, "sayAt": "left"・"right"・"bottom"（画面いっぱいの写真の吹き出しの位置。既定は上の中央）, "frame": 白い縁, "credit": 出どころ}`・`{"text": "1 行目/2 行目", "color"}`・`{"op": "→"}`。
  絵の代わりに `{"icon": アイコンの名前}`（白い丸の上に線で描かれて動く）・`{"part": 部品の台本}`（白い板の上に縮めて置く。ほかの絵より広く取る）も置ける（`label`・`say` は同じ）。
  `{"draw": "…JS…", "plate": "dark"・"light"・"board"（黒板。木の枠と粉受け。明るい色の字と線で描く）・"none"}` は描き下ろし: `custom` と同じ `(ctx, lt, d, H, s)` の本体を、並びの外に（板を敷いて）描く。`s.box` が描く範囲（同じ側に 2 人立つときは、立ち絵にかからない幅に狭くなる）、`lt` はその並びが出てからの ms、`s.cue(n)` は n 個あとのせりふが始まる ms。
  黒板（`board` に部品を置く形）は部品を 0.66 倍に縮めて置くので、字が小さくなる。箇条書き（`bullets`）は `"zoom": "fit"`（板に収まる範囲で 1.6 倍まで）か数字で、字を大きくできる（yukkuri-kaisetsu の `@board bullets:` は `fit` を付ける）。
  絵は台本の `images: {名前: 画像}` から名前で引く（同じ絵を何度使っても 1 回だけ埋め込む）。場面の `tag`・`corner` は左上・右上の札。
- **掛け合いの設定**（台本の `talk`）: `caption`（`"box"` 白い箱とキャラ色の縁・`"outline"` 箱なしの太い縁・`"bar"` 下に暗い箱を置きっぱなし・`"band"` 白く透ける帯・`"strip"` 黒い帯に黄色い字・
  `"bubble"` 話し手のそばの白い箱。立ち絵の無い語り手は下の中央）・`capWidth`（置きっぱなしの字幕の折り返し幅）・`nameTag`（立ち絵の頭の上に名札）・
  `stage: {plate: "white"・"paper"・"dark", photo: "full", align: "ground"}`（絵で見せる場面の板・写真 1 枚の並びを画面いっぱいに・絵を地面に立たせる）・`tags: {tag, tagInk, corner, cornerInk}`（札の地の色と、字・縁の色）・
  `capFill`（字幕の箱・帯の色。`rgba(…)` で濃さも）・`capEdge`（`bar` の箱の縁の色）・`capColor`（置きっぱなしの字幕の字の色。色か `"speaker"`）。
  登場人物の `hidden: true` は、声だけの語り手・`name`（名札）・`size`・`font`（`fonts: [{family, src, weight}]` で埋め込んだ書体）・
  `relax`（素の顔に戻るまでの ms。false で戻らない）・`dim`（話していない人を薄く）・`sfx`（印と大きい字幕に付ける効果音。false で付けない）。
  せりふの `big` は字幕を大きく出し、`se` は効果音を名指しする。章の表示は `chrome: false` で消せる。
- 画像が無い登場人物は、仮のキャラクター（`color` の丸顔。smile・surprised・angry を描き分け）で描く。
- `castAlways: true` なら、掛け合いでない場面にも登場人物を出したままにする（締めの `end` を除く）。
- 声が無いせりふはブラウザの読み上げで、`cast.<名前>.voice` の `pitch`・`rate` で話し手ごとに変える。

## 縦の画面（ショート。`talk.format: "short"`）

`talk.format` を `"short"` にすると、舞台が 9:16（1080×1920）になる。場面・立ち絵・字幕を横の画面（1920×1080）のまま 3 枚の層に描き、縦の枠に組み直す（`engine.js` の `drawVert`）:
上から 題（`title`）→ 絵（横の画面の中央 1080×900）→ 字幕（縁取りの字・3 行まで）→ 立ち絵（左右の端の幅 720 ずつを 0.75 倍で）。掛け合いでない場面（題・クレジット）は、全体を幅に合わせて出す。
録画は 720×1280（編集用は 1080×1920）。絵を並べる幅は `talk.stageWidth`（yukkuri-kaisetsu は 980 にする）。台本からは yukkuri-kaisetsu の `format: short`。
