# 音楽と効果音

手順 2 で曲と効果音を選ぶときに読む。一覧は `python3 <skill_dir>/build.py --list-sounds`、聞き比べるページは `--sounds -o sounds.html`。

- **音楽と効果音も決定論的**。曲は「時刻 → 音符」で決まり（シークしても同じ所が鳴る）、章ごとに和音の進行が変わり、
  章の盛り上がり（1〜3）で楽器が増える。効果音は部品・重ねの層の出来事（項目が出る・線がつながる・通知・クリック…）に合わせて自動で鳴る。

- 曲（`audio.music`）は内容と雰囲気から 1 つ選ぶ。毎回同じ曲にしない。目安:

| 内容・雰囲気 | 曲の例 |
|---|---|
| 会社・サービスの紹介（定番） | `corporate` `bright` `trust` `pitch` `clean` |
| 新製品・発表・告知 | `launch` `innovate` `keynote` `hype` `startup` |
| 技術・開発者・データ | `tech` `data` `circuit` `ai` `robot` `synthwave` `hacker` `cyber` `neural` |
| 科学・実験・宇宙 | `lab` `quantum` `orbit` `space` `aurora` |
| 落ち着いた解説・研修 | `calm` `study` `lofi` `lofipiano` `rain` `documentary` `minimal` `ripple` |
| ピアノだけ・静かな語り | `piano` `nocturne`（6/8） |
| 課題の提示・危機 → 解決 | 章ごとに `tension` / `mystery` → `hope`（章の `music` で切り替える） |
| 調査・ミステリー・こわい話 | `detective` `heist`（5 拍子） `mystery` `suspense` `kaidan` `horror` `creepy` |
| 物語・ビジョン・壮大 | `epic` `hero` `wonder` `trailer` `adventure` `space` `overture`（3 拍子） `cathedral` |
| 明るい・楽しい・子ども | `happy` `pop` `kids` `summer` `island` `musicbox` |
| 掛け合いの解説・日常・おとぼけ | `daily` `oompah` `comedy` `sneaky` `chase` `picnic` |
| 和・アジア・民族 | `wa` `kyoto` `miyabi`（3 拍子） `matsuri` `tsugaru` `ninja` `zen` `ryukyu` `orient` `chuka` `celtic` `jig`（6/8） `andes` `polka` `savanna`（6/8） |
| レトロ・ゲーム | `chiptune` `chiprun` `chiplull`（3 拍子） `arcade` `puzzle` `rpg` |
| 大人・店舗・夜 | `jazz` `jazzwaltz`（3 拍子） `bossa` `lounge` `cafe` `night` `soul` `house` |
| 力強い・スピード | `rock` `drive` `sport` `funk` `countdown` |
| 番組・ニュース・クイズ・料理 | `opening` `news` `breaking`（速報） `morning` `weather` `quiz` `thinking`（3 拍子） `timeup` `cooking` |
| 締め・余韻 | `credits` `afterglow` `sunset` `memory` |

- 効果音の組（`audio.sfx.kit`）: `standard`（既定）・`soft`（研修・医療・子ども）・`digital`（技術・SaaS）・`retro`・`organic`（手作り・生活）・
  `cinematic`（予告・ビジョン）・`playful`・`wa`（和）・`news`（報道・レポート）・`minimal`（章・通知・クリックだけ）・
  `variety`（掛け合いの解説。ハリセン・ぴょこ・チャンチャン）・`quiz`（出題・まるとばつ・ロールと一撃）・`cute`（ゆるい日常。ぷに・ぽよん・ぽわん）。
  ほかに `scifi` `horror` `kids` `game` `luxury`（全部は `--list-sounds`）。曲の雰囲気と揃える。
- 量（`audio.sfx.density`）: `low`（章・通知・クリック・数え上げの終わり等だけ）・`normal`（既定。項目が出る・線がつながる等も）・`high`（表の行まで）。
  読み上げのある 2 分以上の動画で、うるさく感じそうなら `low`。
- 盛り上がり: 章ごとに 1〜3（既定は最初と最後が 1、最後の手前が 3、ほかは 2）。山場の章に `"energy": 3`。
- 場面ごとに足す・止める: 場面の `"sfx": [{"at": 0.5, "name": "ding"}]`・`"sfx": false`・`{"map": {"appear": "bubble"}}`。
  重ねの層は `"sfx": false` か `"sfx": "効果音の名前"`。読み上げ中は音楽が自動で下がる（`audio.duck`）。
- 掛け合い・気持ちに合わせて場面に足す効果音（分類「気持ち・擬音」ほか。場面の `sfx` に名前で書く）:
  - ツッコミ・オチ・笑い: `harisen`（パシーン）・`bishi`（ビシッ）・`zukkoke`（ずっこけ）・`dote`（ドテッ）・`chanchan`（オチ）・`shock`（ガーン）・`horn`（パフパフ）・`fail`（残念）・`rimshot`
  - 正解・不正解・出題: `maru`・`pinpon`・`correct`／`batsu`・`buzzer`／`quiz-in`（デデン）・`drumroll-hit`（ロールと一撃）・`time-signal`（秒読み）・`idea`（ひらめき）
  - 擬音: `poyon`（ぽよん）・`puni`（ぷに）・`pyoko`（ぴょこ）・`nyu`（にゅっ）・`slide-up`（ひゅいっ）・`shakin`（シャキーン）・`tekuteku`（てくてく）・`kira`（キラッ）
  - 気持ちの印: 稲妻 `lightning`・炎 `ignite`・涙のしずく `tear`・汗 `sweat`・もやもや `moyamoya`・まる `maru`・ばつ `batsu`・ぐるぐる `guruguru`（目を回すなら `piyo`）・花 `bloom`・
    魂が抜ける `soul-out`・鼻息 `snort`・星 `kira`・じーっ `stare`・紙ふぶき `confetti`・どんより雨 `drizzle`（落ち込みは `zuun`）・太陽 `shine`・雪 `snowfall`・湯気 `steam`・
    割れたハート `heart-break`・チェック `check`・虫めがね `search`・びっくり `exclaim`・怒り `muka`・ため息 `sigh`・いびき `snore`・ドキドキ `dokidoki`
- 表現が `free` で、音も作り込むと決めたとき（質問で「作曲・自作」を選んだとき）:
  - 曲は `{"preset": "…", 上書き}` で既存の曲の一部（`bpm`・`key`・`scale`・`prog`・`layers`・`drum`）を変えるか、
    `layers`（楽器 × 型）を一から組む。さらに自由にするなら `{"bpm": 96, "src": "music.js"}`（小節ごとに音符を返す JS）。
  - 楽器（`audio.instruments`）・効果音（`audio.sfxDefs`）は層（発振器・雑音・包絡・フィルタ）の並びで作る（書き方は `--list-sounds` と `audio.js` の冒頭）。
  - `custom` の場面の中で `H.sfx(ms, "名前か出来事")` を呼べば、その時刻に鳴る（条件の外で呼ぶ）。
  - 自作しても、時刻だけで決まる作りは同じ（`Math.random` は使わず `M.rand`）。

## 曲のファイル・楽器の音・音の定義

- 音楽の音声ファイルを使うなら `"music": {"file": "bgm.mp3"}`（埋め込むので HTML が大きくなる。権利に注意。同じファイルは何度使っても 1 回だけ入る）。
  曲は章ごと（章の `music`）と、場面ごと（場面の `music`。その場面からその章の終わりまで）に替えられる。替わるときは `audio.musicFade`（既定 900ms）かけて前の曲と重ねて入れ替える。
  ファイルの曲は、`"loop": true` ならそのまま回し、書かなければ、曲の終わりのフェードアウトと無音を除いた所で次の頭に重ねてくり返す。
- **楽器の音**: 曲の旋律・和音・リズムは `audio.js` で作り、ピアノ・電気ピアノ・弦・合唱・ハープ・マリンバ・ギター・ベース・管楽器・
  琴・尺八・三味線など 35 の楽器は、録音した楽器の音（`samples.py`。FluidR3_GM、Frank Wen、CC BY 3.0）で鳴らす。合成の音のままの楽器
  （シンセ・8bit・パッド・打楽器のほとんど）はそのまま。作るときに、曲が使う楽器の使う音域だけ（4 半音おき）を埋め込む
  （1 楽器 300 KB 前後。1 曲で 0.5〜1.5 MB 増える）。録音の音は初回に取りに行き `~/.cache/motion-video/samples/` に置いて使い回す
  （オフラインで作るなら先に `python3 <skill_dir>/samples.py` で全部取っておく。取れなければその楽器は合成の音で鳴る）。
  クレジット（「楽器の音: FluidR3_GM（Frank Wen、CC BY 3.0）」）はプレイヤーの下に自動で出る。合成の音だけにするなら `audio.samples: false`。
  `--sounds` の聞き比べのページも録音した楽器の音で鳴り、「楽器の音」で合成の音と切り替えて比べられる（10 MB 前後。`--no-samples` で合成の音だけ）。
- 音の定義は `sound.py`（曲・効果音・効果音の組・出来事）、合成は `audio.js`（楽器・打楽器の型・和音と旋律の作り方）。
  曲や効果音を足すときは `sound.py` に 1 つ足す（楽器・型・打楽器の型を足すときは両方）。`--sounds` のページで聞いて確かめる。
  足したら音量の倍率も付ける: 効果音は波形の山が 0.5 になる倍率（`SFX_GAIN`。上限 3）、曲は盛り上がり 3 の実効値が既存の曲のまん中（-23 dB 前後）になる倍率（`MUSIC_GAIN`）。
  3 拍子・6/8 の曲は `beats: 3`（1 小節 12 刻み）、5 拍子は `beats: 5`（20 刻み）で、打楽器の型も同じ刻みの数のもの（`waltz` `sixeight` `jig` `afro` `jazzwaltz`／`five`）を使う。

- `audio.sfx.transitionVolume`（数）: 章・場面の切り替えの音（`chapter`・`tr.*`）だけ、音量に掛ける倍率。書かなければ 1。締めの `end` の場面が `variant: "credits"` のときは、切り替えの音を鳴らさない。
- **効果音の大きさはそろえてある**。音色ごとの実効値（いちばん大きい 0.3 秒）を `sfx_levels.py` が測って `sfx_levels.json` に書き、`sound.py` がまん中の大きさへ寄せる倍率（`lv`。0.45〜2 倍）を音ごとに付ける。
  効果音を足した・作り直したら `python3 sfx_levels.py`（Chrome が要る）。倍率を見るだけなら `--show`。`audio.sfx.level: false` で止める。出来事ごとの音量（効果音の組の数字）は、そろえた上での強弱。
