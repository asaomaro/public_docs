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
  `cast.<名前>.motion: "yukkuri"` は話す間に縦に伸び縮みする（頭だけの立ち絵向け）。`cast.<名前>.motion: false` か `castMotion: false` で止まる。OS の「動きを減らす」でも止まる。
- **気持ちの印**（`emote`）は線と形で描く（絵文字の書体が無い環境でも出る）: `!` `?` `!?` `♪` `…` `💦` `💢` `💡` `✨` `♥` `gloom`（ガーン）`shock` `zzz`。
- **絵で見せる場面**: `board: {"type": "stage", "shots": [{"line": 0, "items": […], "title": …, "note": …}]}`。白い黒板を置かず、背景の上に絵・写真・矢印・短い言葉を並べる。
  `line` 番目のせりふからその並びに替わる。`items` は `{"img": 名前, "label": 名札, "say": 吹き出し, "frame": 白い縁, "credit": 出どころ}`・`{"text": "1 行目/2 行目", "color"}`・`{"op": "→"}`。
  絵の代わりに `{"icon": アイコンの名前}`（白い丸の上に線で描かれて動く）・`{"part": 部品の台本}`（白い板の上に縮めて置く。ほかの絵より広く取る）も置ける（`label`・`say` は同じ）。
  `{"draw": "…JS…", "plate": "dark"・"light"・"board"（黒板。木の枠と粉受け。明るい色の字と線で描く）・"none"}` は描き下ろし: `custom` と同じ `(ctx, lt, d, H, s)` の本体を、並びの外に（板を敷いて）描く。`s.box` が描く範囲、`lt` はその並びが出てからの ms、`s.cue(n)` は n 個あとのせりふが始まる ms。
  絵は台本の `images: {名前: 画像}` から名前で引く（同じ絵を何度使っても 1 回だけ埋め込む）。場面の `tag`・`corner` は左上・右上の札。
- **掛け合いの設定**（台本の `talk`）: `caption`（`"box"` 白い箱とキャラ色の縁・`"outline"` 箱なしの太い縁・`"bar"` 下に暗い箱を置きっぱなし・`"band"` 白く透ける帯・`"strip"` 黒い帯に黄色い字・
  `"bubble"` 話し手のそばの白い箱。立ち絵の無い語り手は下の中央）・`capWidth`（置きっぱなしの字幕の折り返し幅）・`nameTag`（立ち絵の頭の上に名札）・
  `stage: {plate: "white"・"paper"・"dark", photo: "full", align: "ground"}`（絵で見せる場面の板・写真 1 枚の並びを画面いっぱいに・絵を地面に立たせる）・`tags: {tag, tagInk, corner}`（札の色）。
  登場人物の `hidden: true` は、声だけの語り手・`name`（名札）・`size`・`font`（`fonts: [{family, src, weight}]` で埋め込んだ書体）・
  `relax`（素の顔に戻るまでの ms。false で戻らない）・`dim`（話していない人を薄く）・`sfx`（印と大きい字幕に付ける効果音。false で付けない）。
  せりふの `big` は字幕を大きく出し、`se` は効果音を名指しする。章の表示は `chrome: false` で消せる。
- 画像が無い登場人物は、仮のキャラクター（`color` の丸顔。smile・surprised・angry を描き分け）で描く。
- `castAlways: true` なら、掛け合いでない場面にも登場人物を出したままにする（締めの `end` を除く）。
- 声が無いせりふはブラウザの読み上げで、`cast.<名前>.voice` の `pitch`・`rate` で話し手ごとに変える。
