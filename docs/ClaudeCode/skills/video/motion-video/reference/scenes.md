# 場面の部品（内容 → type）

手順 2 で台本を書くときに読む。各部品の項目と例は `python3 <skill_dir>/build.py --list`。

| 伝える内容 | type |
|---|---|
| 題名・導入 | `title` |
| 一言で言い切る主張・問い | `statement` |
| できること・特徴（3〜5 個） | `bullets` |
| 処理・データ・依頼の流れ、差し戻し | `flow`（受け渡しは `travel`） |
| 手順・工程 | `steps` |
| コマンドの実行例 | `terminal` |
| 実績・効果の数字 | `stats` |
| 量の比較・推移 | `bars` |
| 順位の移り変わり（年ごとの順位が入れ替わる） | `race`（バーチャートレース。`periods` と各項目の `values`） |
| 複数の値の推移を競わせる・伸びていく様子 | `linerace`（線の先に名前と値） |
| 2 つの指標と大きさが時間とともに動く | `bubble`（`periods`・`x`・`y`・`r`） |
| 地域ごとの値 | `regions`（`preset: "japan"` の 8 地方か `tiles`） |
| 人・お金・件数の流れと分かれ道 | `sankey`（`flows: [{from, to, value}]`） |
| 実績の大きな数字（桁が回って止まる） | `odometer` |
| 割合を升目で（100 のうちいくつ） | `waffle` |
| 2 時点の変化を項目ごとに | `slope`（上がり・下がりを色で） |
| アプリの操作手順をスクリーンショットで | `tour`（`steps: [{rect, note, click}]`。手順はナレーションの文に合わせて進む） |
| 長いページを上から下へ | `scrollshot`（`stops: [{y, note}]`） |
| 前と後の画面を見比べる | `swipe`（`before`・`after`） |
| 前後・案の対比 | `compare`（`tone: good/bad`） |
| コードの解説 | `code`（`highlight` で行を順に強調し `note`） |
| アプリの画面・状態の変化・通知 | `window`（pane の `states`・`toasts`） |
| スクリーンショット・写真 | `image`（台本からの相対パス。埋め込まれる） |
| 締め・始め方・連絡先 | `end` |
| 機能・特徴を並べて（2〜6 枚） | `cards` |
| 年表・マイルストーン | `timeline` |
| AI とのやりとり・会話 | `chat` |
| 数値の推移 | `line` |
| 割合・内訳 | `donut` |
| 表での比較（行を順に強調） | `table` |
| 利用者の声・引用 | `quote` |
| 短い主張を語ごとに組み上げる | `kinetic`（`statement` より動きが強い） |
| 説明と数字・図を左右に | `split`（右に部品を縮小して置く） |
| 導入の前と後 | `beforeafter`（境目が動いて後の姿が現れる） |
| 推移（面）・内訳の推移 | `area`（`stacked` で積み上げ）・`stack`（積み上げ棒） |
| 2 つの量の関係・位置づけ | `scatter`（`trend` で傾向の線） |
| 曜日×時間などの濃淡 | `heatmap` |
| 1 つの指標の水準（満足度・稼働率） | `gauge` |
| 複数の進み具合・達成率 | `rings` |
| 構成比（面積で） | `treemap` |
| 多面的な比較（性能の軸） | `radar` |
| スマホアプリの画面・通知 | `phone`（`screens` で画面を送る・`notify`・`points` で横に説明） |
| 管理画面・数字の集まり | `dashboard` |
| 入力・申し込みの手順 | `form`（カーソルが順に入力して送信） |
| 通知・連絡が次々に来る | `notifs` |
| 文書・サイトの中を見せる | `scroll` |
| タスクを移す・並べ替える | `drag`（カンバン） |
| 関係のつながり（多対多） | `network` |
| 階層・分類 | `tree` |
| 状態の移り変わり | `states`（`path` の順に印が移る） |
| 拠点・場所・経路 | `map` |
| 構成の層（アーキテクチャ） | `layers` |
| 次々に処理が流れる | `pipeline` |
| できること・特徴をアイコンで | `icons`（アイコンは `--list-icons`。`bullets`・`cards`・`orbit` 等の `icon` にも名前で書ける） |
| 複数の部品を 1 画面に（3 つ並び・大見出し＋小窓・写真の重なり・全面の写真・1 つを大きく・左右の比較） | `layout`（`template` と `slots`） |
| キーワードの広がり | `wordcloud` |
| 大きな言葉を背景に（標語・ブランド） | `bigtype` |
| 2 人の掛け合いで解説（ゆっくり解説・ずんだもん解説など） | `talk`（`lines` と中央の黒板 `board`。登場人物は台本の `cast`。台本づくりは **yukkuri-kaisetsu** スキル） |
| 強い一語・結論（集中線・揺れ） | `impact` |
| 公開日・開始までの数え下ろし | `countdown` |
| 中心と周りの関係（生態系・連携先） | `orbit`（項目が中心の周りを回る） |
| ロゴ・製品名の登場（頭・締め） | `logo`（破片が集まり、題名に光が走る） |
| キーワードの多さ・勢い | `marquee`（大きな文字の帯が流れる。`caption` で中央に札） |
| 集客・選考などの絞り込み（段ごとの歩留まり） | `funnel` |
| 候補と、その確率・割合（数字を後から見せる。次の言葉の候補・予想） | `probbars` |
| 文・データを、細かい単位に分ける | `tokensplit` |
| どの言葉・要素どうしが関わるか（強い 1 本を見せる） | `attention` |
| くり返して、1 つずつ出来ていく | `loopgrow` |
| 大きい物から小さい物へ、少しずつ移す・教える・写す | `flowfill`（`from`・`to` に `label` と、後から出す名札 `name`） |
| かたよった物を、ならす（つまみを上げると、高い 1 本が下がり、ほかがのびる） | `softenbars`（`items` に `from`・`to`。`knob` でつまみの名前） |
| 話す順に、数字を 1 本ずつ見せて比べる | `stepbars`（字幕の文か、`at` の秒ごとに 1 本） |
| 小さくしても、力は残る（「〇%減」と、ほぼ満ちたメーター） | `shrinkkeep`（`shrink` と `meter`） |
| 細かい値を、粗い段へ丸める（量子化・段階に分ける） | `snapruler`（`fine`・`coarse`・`points`。`result` で「A → B」） |
| つながりを減らす・間引く | `prunenet`（`layers` と、刈る本数 `cut`） |
| 大ぜいから集めて、1 つを通り、1 つへ渡す | `funnelflow`（`many`・`mid`・`to`。後から出す一言 `mark`） |
| 出来事の順と、間の長さ（「◯日後」） | `dottimeline`（`items` に `date`・`label`。`gap` で 2 点の間の印） |
| 「100 回のうち 79 回」のような割合を、点の数で | `dotgrid`（`total`・`count`。`label`・`unit`） |
| 話しながら 1 行ずつ埋める比較表 | `revealtable`（`columns`・`rows`。`hot` の字のます目に色） |
| 入力を増やすと、結果が変わる（つまみを右へ動かすと、となりの図の線がのびる） | `knobcurve`（`knobs` 2〜4 個。`dir` で右上がり・右下がり。`steps` で線の下の段） |
| 穴うめ・伏せ字・クイズ（札の 1 枚にふたをして、当てさせてから開く） | `maskreveal`（`tokens` と、かくす札 `mask`。`who`・`guess`・`answer`） |
| 大きさの差を、面積で（2 つの丸の面積が、数の比） | `areacompare`（`items` に `label`・`value`・見せる字 `text`。`pick` で片方に札） |
| 得意と苦手・むらのある成績（でこぼこの線の山と谷に名前） | `jaggedline`（`points` と `marks`。目盛りは無い） |
| 直列と並列・1 つずつと同時の比べ | `seqparallel`（`labels`・`count`。`time` で下に時間の帯） |
| 同じ数がそろう形（多角形の角に順に印が出て、右で数える） | `polymarks`（`sides` と `rows`。`center` でまん中の形） |
| 近いのに遠い・回り道（直線と、らせんの道） | `spiralpath`（`from`・`to`・`straight`・`path`。`captions` で段ごとの一言） |
| 2〜3 個の数字を、太い棒と大きな字で（立ち絵のある狭い画面でも読める） | `bigbars`（`items` に `label`・`value`。棒ごとの `at` か、字幕の文ごとに 1 本） |
| 力のつり合い・板ばさみ（まん中の物が左右から引かれて、のびちぢみ） | `tugofwar`（`center`・`left`・`right`。`mark` で一言） |
| 噴き出した物のゆくえ・循環（一部は外へ、残りは降ってもどる） | `fountain`（`source`・`top`・`out`・`back`） |
| 軸の傾き・角度の比べ（球の軸が傾き、弧と数字） | `axistilt`（`items` に `label`・`angle`） |
| 土台から積み上がる構成・優先度 | `pyramid` |
| 2〜3 の性質の重なり | `venn`（`center` で重なりの言葉） |
| 繰り返す工程（PDCA など） | `cycle` |
| 2 軸での位置づけ（優先度の判断） | `matrix`（四象限） |
| 日程・予定 | `calendar` |
| 確認項目・完了の数 | `checklist` |
| 2 つの対決・乗り換え | `versus`（`winner` で勝者が光る） |
| 順位・人気 | `ranking` |
| キーボードの操作・ショートカット | `keys` |
| 3〜4 の面・顔を順に見せる（立体） | `cube`（箱が回る） |
| 道具・製品を並べて 1 つずつ前へ（立体） | `carousel`（カードの輪） |
| 構成の層を分けて見せる（立体） | `explode`（斜め上から見た板が分かれる） |
| 手順・章を奥へ進むように（立体） | `tunnel` |
| 場所・世界観の導入（奥行きのある風景） | `parallax`（`scene: hills|city|space`） |
| 2〜4 語のキーワードを印象的に | `swarm`（粒が集まって言葉になる） |
| 変化・成長の段階 | `morph`（形が次の形へ変わる） |
| 短い言葉をテンポよく連打（標語・締め） | `barrage` |
| 「〇〇で [速く／安全に…] 作る」 | `rotator`（間の語だけ入れ替わる） |
| ロゴ・標語を円や波に沿わせる | `textpath` |
| 文章の中の大事な語を、説明の順に | `emphasis`（`**強調**` の語だけが光る） |
| 上のどれにも当たらない絵 | `custom`（最後の手段。`custom.md`） |
