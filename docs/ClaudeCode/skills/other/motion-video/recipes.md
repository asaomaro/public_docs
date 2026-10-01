# custom の手本集

`custom` の場面は、JS の本体 `(ctx, lt, d, H, s)` で 1 コマを描く。道具の一覧は `python3 build.py --api`。
実物の見本は `examples/scenes/*.js`（`examples/sodashitsu-mixed.json` から使っている）。

## 守ること

- **時刻だけで描く**。同じ `lt` なら同じ絵になるようにする（シーク・倍速・巻き戻しで崩れないため）。
  - 使わない: `Math.random`（→ `H.rand(種)`）・`Date.now`・`performance.now`・前のコマで覚えた値・`setTimeout`。
  - 使わない: DOM の操作・外部の読み込み（fetch・画像の URL）。画像は `image` の部品か data URI。
- **座標は 1920×1080**。字幕と重ならないよう、大事な文字は **縦 120〜880** に収める（左上は章の名前、下は字幕）。
- **色は `H.C` の配色だけ**。hex を直書きしない（配色テーマを変えても合うように）。
- **長いデータは台本の `s` に置く**（JS は描き方だけ）。`src` の .js は台本からの相対パス。
- 場面の見出しを出すなら `H.heading(s, lt)`（台本の `heading` を部品と同じ見た目で出す）。

## 時間の割り付け

```js
// 場面の長さ d に合わせて、3 つの出来事を均等に割り付ける（先頭 600ms・末尾 900ms は空ける）
var at = H.slots(3, d, 600, 900);
var k0 = H.P(lt, at[0], at[0] + 700);           // 0..1 の進み（既定は減速の緩急）
var k1 = H.P(lt, at[1], at[1] + 700, H.back);   // 少し行き過ぎて戻る緩急
var cur = -1; at.forEach(function (a, i) { if (lt >= a) cur = i; });   // 今どの段か
```

## 部品を並べる・縮小して置く（`H.sub`）

```js
// 左に window の部品、右に terminal の部品を半分の大きさで並べる（spec は台本の s に置く）
H.sub("window", s.win, lt, d, { x: -40, y: 200, scale: .5 });
H.sub("terminal", s.term, lt - 600, d - 600, { x: 900, y: 150, scale: .5, alpha: H.P(lt, 400, 1200) });
```

部品の中の時刻を遅らせるときは `lt - 遅らせる ms` を渡す。部品の重ねの層（`overlays`）も一緒に描かれる。

## 分割されながら増える（矩形の補間）

```js
var f2 = H.P(lt, d * .2, d * .2 + 700, H.eio);          // 0 → 1 で左右に割れる
var lw = gw * (1 - .5 * f2);                             // 左の幅が全体から半分へ
H.rr(gx, gy, lw, gh, 10);  ctx.fillStyle = H.C.code; ctx.fill();
if (f2 > 0) { ctx.globalAlpha *= f2; H.rr(gx + lw + 8, gy, gw - lw - 8, gh, 10); ctx.fill(); }
```

実物は `examples/scenes/panes.js`（1 → 4 に割れる）。

## 線をつなぐ・印を流す

```js
var p0 = { x: 400, y: 600 }, p1 = { x: 1300, y: 600 }, c = { x: 850, y: 420 };   // c は曲げる制御点（null で直線）
H.arrow(p0, c, p1, H.P(lt, 800, 1600, H.eio), { color: H.C.accent2 });             // 線が伸びて矢印が付く
H.packet(p0, c, p1, H.lin(lt, 2000, 3400), "{output}");                            // ラベル付きの印が移動
```

## 入力中の文字・数え上げ

```js
H.txt(H.typed("sodactl graph show", H.P(lt, 500, 2000, function (x) { return x; })), 200, 400, { size: 30, font: H.F.mono });
H.txt(H.count("1,240件", H.P(lt, 300, 1800)), 960, 540, { size: 120, weight: 800, align: "center", color: H.C.accent });
```

## カメラ

場面の `camera` に書けば、部品にも custom にも効く（重ねの層も一緒に動く）:

```json
"camera": [{ "at": 0, "zoom": 1 }, { "at": 0.5, "zoom": 1 }, { "at": 0.7, "x": 1150, "y": 560, "zoom": 1.4 }, { "at": 1, "zoom": 1 }]
```

custom の中で一部だけに掛けるとき:

```js
ctx.save(); H.applyCam(H.camAt([{ at: 0, zoom: 1 }, { at: 1, x: 1200, y: 500, zoom: 1.8 }], H.clamp(lt / d)));
/* ここで描いたものだけが寄る */
ctx.restore();
```

## 背景の粒子・紋章

```js
H.particles({ seed: 3, n: 80, color: H.C.accent2, size: 3, alpha: .35 }, lt);   // 種が同じなら毎回同じ動き
H.emblem("ring", 960, 420, 150 * H.P(lt, 0, 1200, H.back), lt * .0002, 1, "S");
```

## 重ねの層（どの場面にも）

部品の上に注記・矢印・強調・カーソル・通知を重ねるだけなら、custom を書かずに `overlays` を使う:

```json
"overlays": [
  { "kind": "note", "text": "出力は **{output}** で受け渡す", "x": 1250, "y": 260, "target": [1000, 600], "at": 0.5 },
  { "kind": "highlight", "rect": [1266, 344, 480, 96], "spotlight": true, "label": "承認待ち", "at": 0.45, "until": 0.85 },
  { "kind": "cursor", "path": [[500, 820], [900, 420]], "click": [1], "at": 0.2, "until": 0.6 },
  { "kind": "notify", "app": "Sodashitsu", "text": "impl が完了しました", "at": 0.2, "until": 0.55 }
]
```

## HTML・SVG・CSS で描く（dom）

`dom` の場面は、HTML の箱（1920×1080）を舞台に重ねる。時刻は CSS 変数 `--lt`（ms）と `--p`（0..1）で届く。
実物は `examples/scenes/orbit.html`・`orbit.css`・`orbit.js`（`examples/showcase.json` から使っている）。

```css
/* CSS のアニメーションを一時停止にし、遅れを --lt で与える → シークしても同じ画 */
.ring { animation: draw 1.4s ease-out both paused; animation-delay: calc(var(--lt) * -1ms); }
.ring.late { animation-delay: calc(var(--lt) * -1ms + 400ms); }   /* 400ms 遅れて始まる */
.title { opacity: calc(min(1, var(--lt) / 800)); }                  /* 0.8 秒で浮かぶ */
@keyframes draw { to { stroke-dashoffset: 0; } }
```

```js
// updateSrc の本体 (el, lt, d, H, s): 毎コマ呼ばれる。JS で動かすときは lt から決める
el.querySelector(".core").setAttribute("r", String(110 + 8 * Math.sin(lt / 400)));
```

- `setTimeout`・`requestAnimationFrame`・CSS の `transition` は使わない（時刻と無関係に進み、シークで崩れる）。
- 文字の大きさは px で決めてよい（箱ごと縮むので、画面の大きさに合わせて揃う）。

## 音（作曲・効果音を自作する）

一覧は `python3 build.py --list-sounds`、聞き比べは `python3 build.py --sounds -o sounds.html`。
まず用意された曲・効果音の組を選び、足りないときだけ自作する（自作するのは表現が `free` のときが基本）。

```json
"audio": {
  "music": {"preset": "corporate", "bpm": 92, "key": "E"},
  "sfx": {"kit": "soft", "density": "low", "map": {"appear": "bubble"}},
  "energy": [1, 2, 3, 1]
}
```

楽器 × 型で一から組む（層の `e` はその盛り上がりから鳴る。和音の記号は音階の度数。`b7` は借りてくる和音、`m`・`7`・`s4` も付けられる）:

```json
"music": {"bpm": 96, "key": "D", "scale": "dorian", "prog": [["1", "4", "b7", "1"], ["6", "4", "5", "1"]],
          "layers": [{"inst": "epiano", "pat": "hold", "oct": 4},
                     {"inst": "bass", "pat": "walk", "oct": 2, "v": .8},
                     {"inst": "flute", "pat": "melody", "oct": 5, "dens": .4, "e": 2}],
          "drum": "brush", "swing": .4}
```

ジャンルの型を組み合わせる例（タンゴ: バンドネオンの鋭い刻み・ハバネラの低音・後半の駆け上がり。トラップ: 808・3 音ずつの分散・連打のハイハット）:

```json
"music": {"bpm": 118, "key": "D", "scale": "harmonic", "prog": [["1", "4", "5", "1"]],
          "layers": [{"inst": "bandoneon", "pat": "tango", "oct": 4, "v": .5},
                     {"inst": "upright", "pat": "habanera", "oct": 2, "v": .7},
                     {"inst": "pizz", "pat": "run", "oct": 4, "v": .35, "e": 3}], "drum": "tango"}
"music": {"bpm": 140, "key": "C#", "scale": "harmonic", "prog": [["1", "6", "4", "5"]],
          "layers": [{"inst": "sub808", "pat": "root2", "oct": 1, "v": .8}, {"inst": "pluck", "pat": "arp3", "oct": 5, "v": .25}],
          "drum": {"kick808": "X......x..x.....", "clap": "........X.......", "hat": "x.x.xrx.x.x.rttr"}}
```

JS で作曲する（小節ごとに呼ばれ、音符の配列を返す。時刻だけで決まるように `M.rand` を使う）:

```js
// music.js — 本体 (bar, M)。M: bar chapter energy beats bpm key scale prog chord(記号, oct) root(記号, oct) degree(i, oct) rand() hz(midi)
var out = [], ch = M.chord(M.prog, 4);
ch.forEach(function (n) { out.push({ at: 0, len: M.beats, n: n, inst: "strings", v: .6 }); });
for (var i = 0; i < 8; i++) out.push({ at: i * .5, len: .4, n: ch[i % ch.length] + 12, inst: "kalimba", v: .5 + .3 * M.rand() });
if (M.energy >= 2) out.push({ at: 0, drum: "kick" }, { at: 2, drum: "snare", v: .8 });
return out;
```

効果音を層で作る（`audio.sfxDefs`。楽器の `audio.instruments` も同じ書き方で、`f` を書かなければ音符の高さで鳴る）:

```json
"sfxDefs": {
  "rise-hit": {"l": [{"w": "noise", "a": .5, "d": .05, "v": .3, "flt": ["highpass", [600, 6000], .7, .5]},
                     {"w": "sine", "at": .5, "f": [120, 45], "ft": .3, "d": .6, "v": .8}]}
}
```

custom の場面から鳴らす（場面の最初に一度だけ集めるので、`if (lt > …)` の中ではなく外で呼ぶ）:

```js
var at = H.slots(3, d, 600, 900);
at.forEach(function (a, i) { H.sfx(a, "appear", { i: i }); });   // 出来事（組の音が鳴る。i で少しずつ高く）
H.sfx(d * .7, "rise-hit");                                        // 効果音の名前をじかに
```

## 動きを強くする（custom の中で）

```js
// 叩きつける題名・揺れ・破片・集中線（揺れと効果音は、場面の最初に一度集めるので条件の外で呼ぶ）
var hit = 600;
H.shake(hit, 20, 500); H.sfx(hit, "hit");
if (lt < hit + 1200) { ctx.save(); ctx.globalAlpha *= H.clamp(1 - (lt - hit) / 1200); H.fx(["speedlines"], lt * 2, d, "under"); ctx.restore(); }
H.burst(960, 480, lt - hit, { n: 40, seed: 3 });
H.text("**3 倍**速い", 960, 540, { size: 140, weight: 900, align: "center", font: H.F.display }, "slam", lt, hit - 250, 500);
H.text("同じ作業が 3 分で", 960, 660, { size: 40, align: "center", color: H.C.accent }, "scramble", lt, hit + 500, 900);
```

- 文字の出方は `--list` の一覧（`rise` `pop` `slam` `stretch` `blur` `glitch` `neon` `type` `scramble` `wave` `letters` `split` `reveal`）。
- 場面の外側（台本）で足りるなら、`anim`・`fx`・`camera`・`shake`・重ねの層（`burst` `stamp` `confetti` `ripple` `circle` `marker`）を先に使う。
