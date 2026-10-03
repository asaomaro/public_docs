# ファクトチェック: sky-blue.txt

確かめた日: 2026-10-02　確かめた人: 書いた本人とは別のエージェント（深さ: ふつう。Web 検索は使えず、出どころの一覧と、そこからたどれるページで確かめた）

同じ主張が別の場所（画面とせりふ、本文とまとめ）にもあるときは、2 つ目からは「- 同じ: C6」とだけ書けば、判定・根拠・出典は要らない（直し方は書く）。
1 つの文に主張が 2 つあるとき（年と人）は、### C6a・### C6b のように分ける。

判定は 確認できた・食い違う・言いすぎ・確かめられない・対象外 のどれか。確認できた・食い違う・言いすぎ には、根拠（出どころの原文の引用）と出典（URL）を書く。

### C1a 空が青い理由がわかると、夕焼けが赤い理由も同じ仕組みで説明できます。空が紫じゃない理由も合わせて、光の「散らばりやすさ」を
- 場所: 3 行目（設定の summary）
- 種類: 説明の文
- 同じ: C30
- 直し方: —

### C1b 3 分で。
- 場所: 3 行目（設定の summary）
- 種類: 数字
- 判定: 対象外
- 根拠: 動画の長さの案内で、出どころと照らす事実ではない。手元の sky-blue.info.json の length は 3:03（ただし info.json は台本より古い版の書き出し）
- 出典: —
- 直し方: —

### C2 空が青い   本当の理由   約5.9倍！？
- 場所: 5 行目（設定の thumb）
- 種類: 数字
- 同じ: C15b
- 直し方: 字数の都合で残すなら「約」は外さず、概要欄に、450nm と 700nm で比べた計算だと一言足す。直すなら「450と700nmで約5.9倍」

### C3 青 450nm
- 場所: 55 行目（画面の絵「青い丸」の名札）
- 種類: 数字
- 同じ: C6
- 直し方: —

### C4 約 5.9 倍 散らばる
- 場所: 55 行目（画面の言葉）
- 種類: 数字
- 同じ: C6
- 直し方: —

### C5 赤 700nm
- 場所: 55 行目（画面の絵「赤い丸」の名札）
- 種類: 数字
- 同じ: C6
- 直し方: —

### C6 青が 450、赤が 700 ナノメートルなら、約 5.9 倍よ。
- 場所: 57 行目（metan・青は散らばりやすい）
- 種類: 数字・固有名詞
- 判定: 確認できた
- 根拠: 色ごとの波長の表（単位 nm）に「blue 450–485」「red 625–750」。450 は青の短い側の端、700 は赤の範囲の中。法則は「the amount of scattering is inversely proportional to the fourth power of the wavelength」。計算 (700÷450)^4 = 5.855… ≒ 5.9。「なら」と条件つきで言っているので、原文と合う。別の出どころ（Usenet Physics FAQ）は 400nm で比べて「blue light is scattered more than red light by a factor of (700/400)」の 4 乗 ≒ 10 と書く（波長の選び方で変わる。計算 (700÷400)^4 = 9.38）
- 出典: https://en.wikipedia.org/wiki/Visible_spectrum ・ https://en.wikipedia.org/wiki/Rayleigh_scattering ・ https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html （2026-10-02 に見た）
- 直し方: —

### C7 ほぼ 6 倍なのだ！？
- 場所: 58 行目（zundamon・青は散らばりやすい）
- 種類: 数字
- 同じ: C6
- 直し方: —

### C8 ふふん。ボク、もう全部わかったのだ！
- 場所: 61 行目（zundamon・青は散らばりやすい）
- 種類: 言い切り
- 判定: 対象外
- 根拠: キャラクターの強がり（事実の主張ではない）。次の章の「なぜ紫じゃない？」でひっくり返される
- 出典: —
- 直し方: —

### C9 1869年 ティンダル（吹き出し: 青が強く散らばるぞ）
- 場所: 94 行目（画面の絵「男性科学者」の名札）
- 種類: 数字・年・日付・固有名詞
- 同じ: C11a
- 直し方: —

### C10 1871年 レイリー卿（吹き出し: 理論にしたぞ）
- 場所: 94 行目（画面の絵「男性の教師」の名札）
- 種類: 数字・年・日付・固有名詞
- 同じ: C12
- 直し方: —

### C11a （年と人）1869 年にティンダルが見つけたの。
- 場所: 95 行目（metan・昔の人も悩んだ）
- 種類: 数字・年・日付・固有名詞
- 判定: 確認できた
- 根拠: 英語版ウィキペディア「John Tyndall discovered that bright light scattering off nanoscopic particulates was faintly blue-tinted」（文の頭は In 1869）。論文の書誌も「Tyndall, John (1869)」。日本語版も「微細な粒子によって散乱された光が青みを帯びることを発見し」（1869年）。なお Usenet Physics FAQ は「Tyndall in 1859」と書くが、論文の書誌に合う 1869 を採る（台本は強いほうに合っている）。絵は男性の科学者で、人物と合う
- 出典: https://en.wikipedia.org/wiki/Rayleigh_scattering ・ https://ja.wikipedia.org/wiki/レイリー散乱 ・ https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html （2026-10-02 に見た）
- 直し方: —

### C11b （中身）青い光ほど強く散らばることは、…ティンダルが見つけた
- 場所: 95 行目（metan・昔の人も悩んだ）
- 種類: 原因・仕組み
- 判定: 確認できた
- 根拠: 「the shorter blue wavelengths are scattered more strongly than the red」（ティンダルが見つけたこととして）。英語版ウィキペディアは「bright light scattering off nanoscopic particulates was faintly blue-tinted」。どちらも、小さな粒を浮かべた気体・液体での話（台本は粒の条件を省いているが、強めてはいない）
- 出典: https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html ・ https://en.wikipedia.org/wiki/Rayleigh_scattering （2026-10-02 に見た）
- 直し方: —

### C12 1871 年にレイリー卿が理論にして、レイリー散乱と呼ばれるわ。
- 場所: 96 行目（metan・昔の人も悩んだ）
- 種類: 数字・年・日付・固有名詞
- 判定: 確認できた
- 根拠: 「In 1871, Rayleigh published the first theoretical treatment of the elastic scattering of light by particles much smaller than the light's wavelength, a phenomenon now known as Rayleigh scattering」。別のページも「In 1871, Lord Rayleigh published two papers on the color and polarization of skylight」「The phenomenon is named after the 19th-century British physicist Lord Rayleigh」。米国気象局も「This process of scattering is known as Rayleigh scattering」（1870 年代に初めて記述、と書く）。絵は男性で、人物と合う
- 出典: https://en.wikipedia.org/wiki/John_William_Strutt,_3rd_Baron_Rayleigh ・ https://en.wikipedia.org/wiki/Rayleigh_scattering ・ https://www.weather.gov/fgz/SkyBlue （2026-10-02 に見た）
- 直し方: —

### C13 1910年 アインシュタイン（吹き出し: 分子の散乱を式に）
- 場所: 100 行目（画面の絵「電球」の名札）
- 種類: 数字・年・日付・固有名詞
- 同じ: C14b
- 直し方: —

### C14a （年と人）1910 年にアインシュタインが
- 場所: 101 行目（metan・昔の人も悩んだ）
- 種類: 数字・年・日付・固有名詞
- 判定: 確認できた
- 根拠: 「In 1910 Albert Einstein showed that the link between critical opalescence and Rayleigh scattering is quantitative」。日本語版も「さらに1910年、 アインシュタイン はこの理論を定式化し」。論文の書誌は Annalen der Physik 33 巻（1910）。なお Usenet Physics FAQ は「The case was finally settled by Einstein in 1911」と書くが、論文の書誌に合う 1910 を採る（台本は強いほうに合っている）
- 出典: https://en.wikipedia.org/wiki/Critical_opalescence ・ https://ja.wikipedia.org/wiki/レイリー散乱 ・ https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html （2026-10-02 に見た）
- 直し方: —

### C14b （中身）空気の分子そのものだとわかってきて、…アインシュタインが式にまとめたの。
- 場所: 101 行目（metan・昔の人も悩んだ）
- 種類: 原因・仕組み
- 判定: 確認できた
- 根拠: 「they supposed correctly that the molecules of oxygen and nitrogen in the air are sufficient to account for the scattering」「calculated the detailed formula for the scattering of light from molecules」。日本語版は、アインシュタインが式にしたのは密度ゆらぎの理論だと書く（「密度ゆらぎと散乱強度との関係を明確にした」）。分子に当てはめた式そのものは、その前に「レイリーは1899年に散乱理論を個々の分子に適用し」とある。台本は「初めて」「決着」とは言っていないので、原文より強くはない
- 出典: https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html ・ https://ja.wikipedia.org/wiki/レイリー散乱 （2026-10-02 に見た）
- 直し方: —

### C15a 今日のまとめ | 太陽の光は、色のまぜもの
- 場所: 106 行目（画面・まとめ）
- 種類: 説明の文
- 同じ: C70
- 直し方: —

### C15b 青は赤の約 5.9 倍散らばる
- 場所: 106 行目（画面・まとめ）
- 種類: 数字
- 判定: 言いすぎ
- 根拠: 5.9 倍は、青を 450nm（表の「blue 450–485」の短い側の端）、赤を 700nm に選んだときだけの値。計算 (700÷450)^4 = 5.86、(700÷485)^4 = 4.34。出どころの法則「the amount of scattering is inversely proportional to the fourth power of the wavelength」には倍率の数字は無い。せりふ（C6）は 450 と 700 なら、と条件を付けているが、まとめの画面は条件を落として、青と赤の決まった倍率のように言い切っている
- 出典: https://en.wikipedia.org/wiki/Visible_spectrum ・ https://en.wikipedia.org/wiki/Rayleigh_scattering （2026-10-02 に見た）
- 直し方: 条件を戻す。例:「青（450nm）は赤（700nm）の約 5.9 倍散らばる」。または数字を外して「波の短い青は、赤よりずっと強く散らばる」

### C15c 夕方は青が散らばりきって、赤が残る
- 場所: 106 行目（画面・まとめ）
- 種類: 説明の文
- 同じ: C78
- 直し方: —

### C16 空はなぜ青いのか？答えは「散らばりやすさ」にあった【ずんだもん解説】
- 場所: 2 行目（設定の title）
- 種類: 画面・題の文字
- 同じ: C30
- 直し方: —

### C17 散らばった青い光が、空じゅうから目に届く。だから空は青いの。
- 場所: 60 行目（metan・青は散らばりやすい）
- 種類: 原因・仕組み
- 判定: 確認できた
- 根拠: 「Blue is scattered more than other colors because it travels as shorter, smaller waves. This is why we see a blue sky most of the time.」。別の出どころも「This results in the indirect blue and violet light coming from all regions of the sky.」
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://en.wikipedia.org/wiki/Rayleigh_scattering （2026-10-02 に見た）
- 直し方: —

### C18 ボクの目のせいでもあったのだ…
- 場所: 75 行目（zundamon・なぜ紫じゃない？）
- 種類: 原因・仕組み
- 判定: 対象外
- 根拠: キャラクターの感想。元の事実（目が紫に鈍い）は C54 で確かめた
- 出典: —
- 直し方: —

### C19 火星の大気は二酸化炭素が中心で、細かい砂ぼこりが多いからよ。
- 場所: 89 行目（metan・夕焼けが赤いわけ）
- 種類: 原因・仕組み
- 判定: 言いすぎ
- 根拠: 大気の中身は原文どおり（「Mars has a very thin atmosphere made mostly of carbon dioxide and filled with fine dust particles.」）。ただし原文が色の原因にしているのは砂ぼこりだけ: 「These fine particles scatter light differently than the gases and particles in」。別の出どころも「the red color of the sky is caused by the presence of iron(III) oxide in the airborne dust particles」「On Mars, Rayleigh scattering is usually a very weak effect」。台本は、二酸化炭素が中心であることも「から」でつなぎ、二酸化炭素も色の原因のように言っている
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://en.wikipedia.org/wiki/Extraterrestrial_sky （2026-10-02 に見た）
- 直し方: 原因を砂ぼこりに絞る。例:「火星の大気はうすくて、細かい砂ぼこりがたくさん舞っているの。その砂ぼこりが、光を地球とはちがうふうに散らすからよ」（二酸化炭素を残すなら「大気は二酸化炭素が中心。でも色を決めているのは、細かい砂ぼこりよ」）

### C20 青いペンキ
- 場所: 22 行目（画面の絵「バケツ」の名札）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: 茶番の小道具
- 出典: —
- 直し方: —

### C21 空
- 場所: 22 行目（画面の絵「雲」の名札）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: 茶番の小道具
- 出典: —
- 直し方: —

### C22 ふっふっふ。今日は空を、もっと青く塗るのだ！
- 場所: 23 行目（zundamon・茶番）
- 種類: 説明の文　※茶番の章（おふざけ。事実として言っているものだけ確かめる）
- 判定: 対象外
- 根拠: 茶番のボケ（寸劇の中のふるまい）
- 出典: —
- 直し方: —

### C23 空は誰かが塗ってるに決まってるのだ。ボクも手伝うのだ！
- 場所: 25 行目（zundamon・茶番）
- 種類: 説明の文　※茶番の章（おふざけ。事実として言っているものだけ確かめる）
- 判定: 対象外
- 根拠: ボケ。27 行目のせりふ（塗ってないわよ）で訂正される。空が青い本当の理由は C17 で確かめた
- 出典: —
- 直し方: —

### C24 青いペンキ
- 場所: 26 行目（画面の絵「バケツ」の名札）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: 茶番の小道具
- 出典: —
- 直し方: —

### C25 塗ってない！
- 場所: 26 行目（画面の言葉）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: ボケへの訂正（つっこみ）。空が青い理由そのものは C17 で確かめた
- 出典: —
- 直し方: —

### C26 じゃあ、なんで青いのだ！ ペンキ代を返してほしいのだ！
- 場所: 29 行目（zundamon・茶番）
- 種類: 説明の文　※茶番の章（おふざけ。事実として言っているものだけ確かめる）
- 判定: 対象外
- 根拠: 茶番の問いかけとボケ
- 出典: —
- 直し方: —

### C27 というわけで今回は、空が青い本当の理由よ。
- 場所: 32 行目（metan・茶番）
- 種類: 説明の文　※茶番の章（おふざけ。事実として言っているものだけ確かめる）
- 判定: 対象外
- 根拠: これから話す内容の予告
- 出典: —
- 直し方: —

### C28 空はなぜ青いのか
- 場所: 35 行目（画面の見出し）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: 問いの見出し（主張ではない）
- 出典: —
- 直し方: —

### C29 答えは 「散らばりやすさ」
- 場所: 35 行目（画面の言葉）
- 種類: 画面・題の文字
- 同じ: C30
- 直し方: —

### C30 答えは、光の「散らばりやすさ」。夕焼けが赤いわけまで、同じ理由で説明できるわ。
- 場所: 36 行目（metan・光は色のまぜもの）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「Blue light is scattered more than the other colors because it travels as shorter, smaller waves. This is why we see a blue sky most of the time.」。夕焼けも同じ散乱で説明されている:「Due to Rayleigh scattering, red and orange colors are more visible during sunset because the blue and violet light has been scattered out of the direct path.」
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://en.wikipedia.org/wiki/Rayleigh_scattering （2026-10-02 に見た）
- 直し方: —

### C31 太陽の光は白い
- 場所: 38 行目（画面の絵「太陽」の名札）
- 種類: 画面・題の文字
- 同じ: C70
- 直し方: —

### C32 虹の色がぜんぶ
- 場所: 38 行目（画面の絵「虹」の名札）
- 種類: 画面・題の文字
- 同じ: C70
- 直し方: —

### C33 プリズムに通すと、色に分かれる
- 場所: 41 行目（画面の一言）
- 種類: 固有名詞・説明の文
- 同じ: C34
- 直し方: —

### C34 ガラスのプリズムに通すと、こうして色に分かれるのよ。
- 場所: 42 行目（metan・光は色のまぜもの）
- 種類: 固有名詞・説明の文
- 判定: 確認できた
- 根拠: 「When white light shines through a prism, the light is separated into all its colors.」。ガラスであることは別の出どころ:「White light is dispersed by a glass prism into the colors of the visible spectrum.」。画面の写真（prism.png）は Wikimedia Commons の PrismDispersion で、中身と合う
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://en.wikipedia.org/wiki/Visible_spectrum （2026-10-02 に見た）
- 直し方: —

### C35 光も波で伝わる
- 場所: 44 行目（画面の絵「波」の名札）
- 種類: 画面・題の文字
- 同じ: C71
- 直し方: —

### C36 赤 — 波が長い
- 場所: 47 行目（画面の絵「赤い丸」の名札）
- 種類: 画面・題の文字
- 同じ: C72
- 直し方: —

### C37 青 — 波が短い
- 場所: 47 行目（画面の絵「青い丸」の名札）
- 種類: 画面・題の文字
- 同じ: C72
- 直し方: —

### C38 空気の分子（吹き出し: ぶつかる！）
- 場所: 51 行目（画面の絵「分子」の名札）
- 種類: 画面・題の文字
- 同じ: C40
- 直し方: —

### C39 青はあちこちへ
- 場所: 51 行目（画面の絵「青い丸」の名札）
- 種類: 画面・題の文字
- 同じ: C40
- 直し方: —

### C40 光は、空気の小さな分子にぶつかると、あちこちに散らばるわ。
- 場所: 52 行目（metan・青は散らばりやすい）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「Blue light is scattered in all directions by the tiny molecules of air in Earth's atmosphere.」。別の出どころも「As white light passes through our atmosphere, tiny air molecules cause it to」散らばる、と書く
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://www.rmg.co.uk/stories/topics/why-sky-blue （2026-10-02 に見た）
- 直し方: —

### C41 波の長さの 4 乗に反比例
- 場所: 55 行目（画面の一言）
- 種類: 画面・題の文字
- 判定: 確認できた
- 根拠: 「the amount of scattering is inversely proportional to the fourth power of the wavelength」。別の出どころも「the amount of light scattered is inversely proportional to the fourth power of wavelength for sufficiently small particles」
- 出典: https://en.wikipedia.org/wiki/Rayleigh_scattering ・ https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html （2026-10-02 に見た）
- 直し方: —

### C42 空じゅうから目に届く
- 場所: 59 行目（画面の絵「目」の名札）
- 種類: 画面・題の文字
- 同じ: C17
- 直し方: —

### C43 紫 — もっと短い
- 場所: 64 行目（画面の絵「紫の丸」の名札）
- 種類: 画面・題の文字
- 同じ: C75
- 直し方: —

### C44 青
- 場所: 64 行目（画面の絵「青い丸」の名札）
- 種類: 画面・題の文字
- 同じ: C75
- 直し方: —

### C45 なのに、空は紫じゃない
- 場所: 64 行目（画面の一言）
- 種類: 画面・題の文字
- 同じ: C75
- 直し方: —

### C46 ……教えてほしいのだ。
- 場所: 66 行目（zundamon・なぜ紫じゃない？）
- 種類: 説明の文
- 判定: 対象外
- 根拠: 頼みごと（主張ではない）
- 出典: —
- 直し方: —

### C47 ① 紫はもともと少ない
- 場所: 68 行目（画面の絵「太陽」の名札）
- 種類: 画面・題の文字
- 同じ: C76
- 直し方: —

### C48 ① 紫はもともと少ない
- 場所: 70 行目（画面の絵「太陽」の名札）
- 種類: 画面・題の文字
- 同じ: C76
- 直し方: —

### C49 ② 上空で吸収される
- 場所: 70 行目（画面の絵「雲」の名札）
- 種類: 画面・題の文字
- 同じ: C50
- 直し方: —

### C50 次に、上空の大気で吸収されるわ。
- 場所: 71 行目（metan・なぜ紫じゃない？）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「additionally is absorbed by the high atmosphere, giving less violet in the light」。別の出どころでは未確認: 米国気象局は理由を、目の感度と太陽の出す光の 2 つだけ挙げ、英語版ウィキペディア（Rayleigh scattering）も太陽の光・散乱・目の 3 要因で、上空での吸収には触れない。支えは Usenet Physics FAQ（専門家個人の解説。年の記載に誤りがあった出どころ）だけ
- 出典: https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html ・ https://www.weather.gov/fgz/SkyBlue （2026-10-02 に見た）
- 直し方: —

### C51 ① 紫はもともと少ない
- 場所: 73 行目（画面の絵「太陽」の名札）
- 種類: 画面・題の文字
- 同じ: C76
- 直し方: —

### C52 ② 上空で吸収される
- 場所: 73 行目（画面の絵「雲」の名札）
- 種類: 画面・題の文字
- 同じ: C50
- 直し方: —

### C53 ③ 目が紫に鈍い
- 場所: 73 行目（画面の絵「目」の名札）
- 種類: 画面・題の文字
- 同じ: C54
- 直し方: —

### C54 そのうえ、人の目は紫に鈍いのよ。
- 場所: 74 行目（metan・なぜ紫じゃない？）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「For one thing, our eyes are less sensitive to violet.」。別の出どころも「The sky looks blue, not violet, because our eyes are more sensitive to blue light」
- 出典: https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html ・ https://www.weather.gov/fgz/SkyBlue （2026-10-02 に見た）
- 直し方: —

### C55 太陽が低い
- 場所: 79 行目（画面の絵「夕日」の名札）
- 種類: 画面・題の文字
- 同じ: C77
- 直し方: —

### C56 光が空気の中を 長く通る
- 場所: 79 行目（画面の言葉）
- 種類: 画面・題の文字
- 同じ: C77
- 直し方: —

### C57 青は散らばりきる
- 場所: 82 行目（画面の絵「青い丸」の名札）
- 種類: 画面・題の文字
- 同じ: C78
- 直し方: —

### C58 赤が残る
- 場所: 82 行目（画面の絵「赤い丸」の名札）
- 種類: 画面・題の文字
- 同じ: C78
- 直し方: —

### C59 同じ仕組みで、青にも赤にもなるのだ！
- 場所: 84 行目（zundamon・夕焼けが赤いわけ）
- 種類: 説明の文
- 同じ: C30
- 直し方: —

### C60 火星では、夕日のまわりが青い
- 場所: 85 行目（画面の一言）
- 種類: 画面・題の文字
- 同じ: C79
- 直し方: —

### C61 細かい砂ぼこりが多い
- 場所: 88 行目（画面の絵「竜巻」の名札）
- 種類: 画面・題の文字
- 判定: 確認できた
- 根拠: 「Mars has a very thin atmosphere made mostly of carbon dioxide and filled with fine dust particles.」。別の出どころも「Mars has only a thin atmosphere; however, it is extremely dusty」。名札そのものは合っている（原因の言い方は C19）
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://en.wikipedia.org/wiki/Extraterrestrial_sky （2026-10-02 に見た）
- 直し方: —

### C62 原因は ちりや水滴？
- 場所: 98 行目（画面の言葉）
- 種類: 画面・題の文字
- 同じ: C80
- 直し方: —

### C63 青は散らばりやすい。夕方は赤が残る。ばっちりなのだ！
- 場所: 108 行目（zundamon・まとめ）
- 種類: 説明の文
- 同じ: C78
- 直し方: —

### C64 青いペンキ
- 場所: 109 行目（画面の絵「バケツ」の名札）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: 茶番のオチの小道具
- 出典: —
- 直し方: —

### C65 もういらない！
- 場所: 109 行目（画面の言葉）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: 茶番のオチ
- 出典: —
- 直し方: —

### C66 うっ…屋上に置きっぱなしなのだ。
- 場所: 111 行目（zundamon・まとめ）
- 種類: 説明の文
- 判定: 対象外
- 根拠: 茶番のオチ（作り話）
- 出典: —
- 直し方: —

### C67 あしたの空
- 場所: 112 行目（画面の絵「太陽」の名札）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: 呼びかけの小道具
- 出典: —
- 直し方: —

### C68 あしたは空を見上げてみるのだ！
- 場所: 113 行目（zundamon・まとめ）
- 種類: 説明の文
- 判定: 対象外
- 根拠: 呼びかけ・これからの予定
- 出典: —
- 直し方: —

### C69 あしたは雨
- 場所: 114 行目（画面の絵「傘と雨」の名札）
- 種類: 画面・題の文字
- 判定: 対象外
- 根拠: オチの作り話（実際の天気予報を言っているのではない）。115 行目のせりふも同じ
- 出典: —
- 直し方: —

## 拾い切れていない主張（読んで足す）

数字の無い事実（〜は〜である、〜が〜した）は、上の一覧に出ないことがある。文章を頭から読んで、ここに C の続きの番号で足す。

### C70 まず、太陽の光。白く見えるけれど、虹の色がぜんぶまざっているの。
- 場所: 39 行目（metan・光は色のまぜもの）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「The light from the Sun looks white. But it is really made up of all the colors of the rainbow.」。別の出どころも「White light consists of all the colors we can see, and each of these colors has a different wavelength.」
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://www.weather.gov/fgz/SkyBlue （2026-10-02 に見た）
- 直し方: —

### C71 そして光は、海の波みたいに、波で伝わるの。
- 場所: 45 行目（metan・光は色のまぜもの）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「Like energy passing through the ocean, light energy travels in waves, too.」。別の出どころも「it travels in the form of waves possessing electric and magnetic properties」
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://www.weather.gov/fgz/SkyBlue （2026-10-02 に見た）
- 直し方: —

### C72 そう。色のちがいは、波の長さのちがい。青は短くて、赤は長いの。
- 場所: 48 行目（metan・光は色のまぜもの）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「Blue light waves are shorter than red light waves.」。別の出どころも「each of these colors has a different wavelength」「Red has the longest wavelength, and lowest frequency and energy.」
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://www.weather.gov/fgz/SkyBlue （2026-10-02 に見た）
- 直し方: —

### C73 そして、波の短い光ほど、強く散らばるの。
- 場所: 53 行目（metan・青は散らばりやすい）
- 種類: 原因・仕組み
- 判定: 確認できた
- 根拠: 「increases as the wavelength of light decreases」（空気の分子による散乱について）。別の出どころも「shorter ( blue ) wavelengths are scattered more strongly than longer ( red ) wavelengths」
- 出典: https://www.rmg.co.uk/stories/topics/why-sky-blue ・ https://en.wikipedia.org/wiki/Rayleigh_scattering （2026-10-02 に見た）
- 直し方: —

### C74 波が少し短いだけで、散らばり方はぐんと強くなるの。
- 場所: 56 行目（metan・青は散らばりやすい）
- 種類: 原因・仕組み
- 同じ: C41
- 直し方: —

### C75 あら。じゃあ紫は、青よりもっと波が短いわ。なぜ空は紫じゃないの？
- 場所: 65 行目（metan・なぜ紫じゃない？）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「Violet has the shortest wavelength in the visible spectrum.」。色ごとの波長の表も「violet 380–450」「blue 450–485」。空が紫に見えないことも「The sky looks blue, not violet」
- 出典: https://www.weather.gov/fgz/SkyBlue ・ https://en.wikipedia.org/wiki/Visible_spectrum （2026-10-02 に見た）
- 直し方: —

### C76 理由は 3 つ。まず、太陽の光に、紫はもともと少ないの。
- 場所: 69 行目（metan・なぜ紫じゃない？）
- 種類: 数字・説明の文
- 判定: 確認できた
- 根拠: 「the sun also emits more energy as blue light than as violet」。別の出どころも「the spectrum of light emission from the Sun is not constant at」all wavelengths、と書く。「3 つ」は台本の数え方で、3 つとも挙げるのは Usenet Physics FAQ だけ（2 つ目は C50）
- 出典: https://www.weather.gov/fgz/SkyBlue ・ https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html （2026-10-02 に見た）
- 直し方: —

### C77 夕方は太陽が低いから、光が空気の中を長く通るでしょう。
- 場所: 81 行目（metan・夕焼けが赤いわけ）
- 種類: 原因・仕組み
- 判定: 確認できた
- 根拠: 「As the Sun gets lower in the sky, its light is passing through more of the atmosphere to reach you.」。別の出どころも「At sunrise and sunset, the sunlight passes through more atmosphere than during the day」
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://www.weather.gov/fgz/SkyBlue （2026-10-02 に見た）
- 直し方: —

### C78 青は途中で散らばりきって、残った赤や黄がまっすぐ届くの。
- 場所: 83 行目（metan・夕焼けが赤いわけ）
- 種類: 原因・仕組み
- 判定: 確認できた
- 根拠: 「Even more of the blue light is scattered, allowing the reds and yellows to pass straight through to your eyes.」。「散らばりきる」は別の出どころが支える:「If the path is long enough, all the blue and violet light gets redirected out of your line of sight」
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://www.weather.gov/fgz/SkyBlue （2026-10-02 に見た）
- 直し方: —

### C79 ちなみに火星は逆。昼の空がオレンジっぽくて、夕日のまわりが青いの。
- 場所: 86 行目（metan・夕焼けが赤いわけ）
- 種類: 比べる・説明の文
- 判定: 確認できた
- 根拠: 「During the daytime, the Martian sky takes on an orange or reddish color. But as the Sun sets, the sky around the Sun begins to take on a blue-gray tone.」（原文は青灰色。その前の文で、地球の逆だと言っている）。別の出どころも「in the vicinity of the setting Sun it is blue. This is the opposite of the situation on Earth.」。画面の写真（mars_sunset）は Curiosity が撮った火星の夕日で、中身と合う
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://en.wikipedia.org/wiki/Extraterrestrial_sky （2026-10-02 に見た）
- 直し方: —

### C80 それが、二人とも、はじめは原因を、ちりや水滴だと考えていたの。
- 場所: 99 行目（metan・昔の人も悩んだ）
- 種類: 説明の文
- 判定: 確認できた
- 根拠: 「Tyndall and Rayleigh thought that the blue colour of the sky must be due to small」particles of dust and droplets of water vapour、と続く。別の出どころも「レイリーは当初、散乱体を 大気 中に浮遊する 塵 や 水滴 などの微粒子と考えていた」
- 出典: https://math.ucr.edu/home/baez/physics/General/BlueSky/blue_sky.html ・ https://ja.wikipedia.org/wiki/レイリー散乱 （2026-10-02 に見た）
- 直し方: —

### C81 まとめるわ。空の色は、光の散らばりやすさで決まるの。
- 場所: 107 行目（metan・まとめ）
- 種類: 説明の文
- 同じ: C30
- 直し方: —

### C82 空気の中身がちがうと、空の色まで変わるのだ…
- 場所: 90 行目（zundamon・夕焼けが赤いわけ）
- 種類: 原因・仕組み
- 判定: 確認できた
- 根拠: ほかの惑星の空の色について「in the atmosphere! For example, Mars has a very thin atmosphere made mostly of carbon dioxide」と、大気の中身しだいだと書く。別の出どころも「Other planets don’t have an atmosphere exactly like ours, and so their skies would look different.」
- 出典: https://spaceplace.nasa.gov/blue-sky/en/ ・ https://www.rmg.co.uk/stories/topics/why-sky-blue （2026-10-02 に見た）
- 直し方: —

### C83 metan.credit: 坂本アヒル ／ zundamon.credit: 坂本アヒル
- 場所: 8〜9 行目（設定のクレジット）
- 種類: 固有名詞
- 判定: 確認できた
- 根拠: 投稿者のページの題に「ずんだもん立ち絵素材」「四国めたん立ち絵素材」、どちらも「坂本アヒル さんのイラスト」。（この動画がその素材を使っているかは、台本からは確かめていない）
- 出典: https://seiga.nicovideo.jp/seiga/im10788496 ・ https://seiga.nicovideo.jp/seiga/im10791276 （2026-10-02 に見た）
- 直し方: —
