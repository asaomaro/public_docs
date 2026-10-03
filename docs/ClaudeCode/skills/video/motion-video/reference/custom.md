# custom（Canvas）と dom（HTML・SVG・CSS）で描く

手順 2 で、部品では伝わらない見せ場を描くとき（表現が mixed の見せ場・free の全場面）に読む。手本は `recipes.md`、実物は `examples/scenes/*.js`、道具の一覧は `python3 <skill_dir>/build.py --api`。

## dom（HTML・SVG・CSS で自由に描く）

- `src`（HTML）・`cssSrc`（CSS）・`updateSrc`（毎コマ呼ぶ JS。本体 `(el, lt, d, H, s)`）を台本からの相対パスで書く（`html`・`css`・`update` に直接でもよい）。
- 1920×1080 の箱に描き、舞台の大きさに合わせて縮む。時刻は CSS 変数 `--lt`（場面の経過 ms）と `--p`（0..1）で受け取る。
- **CSS のアニメーションは一時停止にして、遅れを `--lt` で与える**（`animation-play-state: paused; animation-delay: calc(var(--lt) * -1ms)`）。
  こうすればシーク・倍速でも同じ画になる。JS で動かすなら `update` で `lt` から決める。
- `dom` の場面は、シークバーのプレビューと「WebM で保存」には映らない（Canvas だけが対象）。見せ場に使い、全場面を `dom` にしない。

## custom（Canvas に自由に描く）

- 本体 `(ctx, lt, d, H, s)`。`lt` は場面の中の経過 ms、`d` は場面の長さ ms、`s` は台本の場面、`H` は描画の道具
  （一覧は `python3 <skill_dir>/build.py --api`、手本は `recipes.md`、実物は `examples/scenes/*.js`）。
- JS は **`src` に .js のパス**（台本からの相対）で書くのが基本。短いものは `code` に文字列か行の配列。
- 場面の共通の項目の名前（`type` `narration` `duration` `transition` `anim` `ease` `order` `sync` `camera` `overlays` `fx` `bg` `mark` `markText`）は、
  部品でも `custom` でも設定として読まれる。`custom` の独自のデータには別の名前（`data`・`items` など）を使う（`order` に配列を書くとエラーになる）。
- 緩急は `H.P(lt, a, b, H.eio)` のように渡す。`H.lin(lt, a, b)` は進みそのもの（形が違う）で、等速の緩急は `H.linear`。
- **時刻だけで決まる描き方にする**（`Math.random` → `H.rand(種)`、`Date.now`・前のコマの状態・DOM の操作は使わない）。
- 座標は 1920×1080。大事な文字は縦 120〜880 に収める（下は字幕）。色は `H.C` の配色だけ。
- 長いデータ（行・名前の配列・部品の spec）は台本の場面 `s` に置き、JS は描き方だけにする。

## 表現が free のとき

- `free`: 各場面を `custom` で描く。部品は `H.sub(type, spec, lt, d, {x, y, scale})` で縮小して並べる道具として使ってよい。
  ただし `title`・`end` は部品のままでもよい。
