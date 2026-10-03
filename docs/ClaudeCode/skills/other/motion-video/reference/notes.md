# メモ（書き方の細部・見本・足し方）

細かい仕様を確かめるとき・見本を探すとき・テーマや部品を足すときに読む。

- コマンドは `python3` で書いている。Windows で `python3` が無ければ `py -3`（または `python`）で同じように動く。
- **締め（`end`）**: 上に大きな題と一文（`tagline`）、下に行（`lines`。コマンド・連絡先）。行は画面に収まる高さに縮み、8 行以上は小さな字の 2 段になる。長さは 6 秒（ナレーションが長ければその長さ）。
  紋章は、`mark` か `markText` を書いたときだけ題の上に小さく出る（書かなければ出さない）。締めへ替わるときは切り替えの音を鳴らさず、動画の最後の 2 秒で映像と音が一緒に消える（台本の `endFade`（ms）。`0` で切る）。
- `title`・`logo` の紋章（と、紋章を出す `end`）の中の 1 文字は、既定で題名の頭の字。`markText` で変えられる（例: `"markText": "G"`）。
- 画面の比率は 16:9（1920×1080 の座標で描き、表示の大きさに合わせて拡大縮小する）。
- `image` の画像は data URI で埋め込むので、画像が多い・大きいと HTML が大きくなる。
- 読み上げの声が無い環境（例: 声の入っていない Linux）では、効果音と音楽だけになり、その旨がプレイヤーの下に出る。
- 絵文字のアイコン（`bullets` の `icon`）は OS の絵文字の書体で描く。絵文字の書体が無い環境では四角になる。
- 見本: `examples/data-tour.json`（時間とともに動くデータと画面の解説。画像は `examples/assets/`）・`examples/depth-type.json`（立体・奥行きの部品と文字の演出・切り替え depth/swing・演出の層 cubes）・`examples/dynamic.json`（動きの性格 dynamic・動きの強い部品・切り替え・文字の出方・演出の層・新しい重ねの層）・`examples/showcase.json`（追加した部品・切り替え・`dom` の場面をすべて使う。`theater`）・`examples/sodashitsu.json`（部品だけ）・`examples/sodashitsu-mixed.json`（混在。pane が割れて増える・ブラウザと端末版の並び・
  SSH の線・OS 風の通知・カメラ・注記を `custom` と `overlays` で）。
- テーマを足すときは `build.py` の `THEMES` に 1 つ足す（canvas の配色・書体・背景の模様・操作部の配色）。
- 部品を足すときは `engine.js` の `R.<type>` と、`build.py` の `SCENE_TYPES`（必須の項目・説明・例）と `MIN_SEC` に足す。
