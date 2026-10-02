# 差分つき立ち絵の配布元と、書き出しのレシピ

口・目・表情の差分がある立ち絵の配布元と、書き出し方の対応。2026-10-02 に取得して確かめた。VOICEVOX の話者 43 人と、ゆっくり（霊夢・魔理沙）がそろっている。
素材（zip・PSD）も書き出した PNG も再配布しない。`chars/`・`chars_src/` は `.gitignore` に入れてあり、リポジトリには入らない。
規約は配布元とキャラクターごとに違う。下は確かめる観点の案内で、使う前に配布元とキャラクター（`chars/<名前>/policy.txt`）の最新の規約を読む。

## 書き出し方

```bash
pip install psd-tools pillow
python3 psd_export.py   chars_src/zundamon/…_基本版.psd --recipe recipes/zundamon.json --out chars/zundamon   # PSD（PSDTool 形式）
python3 parts_export.py chars_src/himari/…/YMM4用 --recipe recipes/himari.json --out chars/himari              # パーツのフォルダ（--recipe を省くと preset.ini から自動）
python3 parts_export.py chars_src/kitsune/れいむ --recipe recipes/kitsune_yukkuri.json --out chars/reimu --height 400     # レシピで指定
```

- `psd_export.py`: `--list` でレイヤー、`--sheet <組>` で選択肢の見本。レシピで表情ごとの目・眉・口を選ぶ。
- どちらもパーツの形（`sprite.json`）で書き出す。`--png` を付けると、組み合わせごとに 1 枚の PNG で書き出す。
- `parts_export.py`: `--list` でパーツと preset.ini の表情。preset.ini の「会話用＿喜び」などを normal・smile・angry・sad に当て、`驚き`・`困り` のパーツがあれば surprised・troubled も作る。
- 作る表情・体のラベルは `labels.json`（表情 12・ポーズ 6・持ち物・動き 10）。素材に無いものは作らない（下の表）。
- 動画には、台本で使った表情の絵だけが埋め込まれる。





## 立ち絵ごとの表情と体

`python3 kaisetsu.py --list-casts` でも見られる（`--list-casts <登場人物>` で、形ごとの説明と度合いまで）。定義は `recipes/<登場人物>.json`（ゆっくりは `kitsune_yukkuri.json`）、
書き出した結果は `chars/<登場人物>/sprite.json` と `sprite/`。ラベルの意味は `labels.json`。
「smile×3」は、smile のラベルに形が 3 つあること（`smile`・`smile#2`・`smile#3`。度合いは控えめ・ふつう・強めのどれか）。体は、ポーズ（point・raise・peace・fold・chin・stand）と持ち物（mic・phone など）。
`point+mic` は「指す」と「マイク」の両方を満たす体。無いラベルを台本で使うと、近いもので代わり、`warn:` が出る。

書き出しは、必要な絵だけを描いて、体の絵（体ごとに 1 枚）と、表情・まばたき・口のパーツ（体の絵と違う所を囲む四角）に分けて保存する。
手が顔にかからない体では、いつもの姿の顔のパーツをそのまま使う。

| 登場人物 | 話者 | 素材 | 表情 | 体 | パーツ | 備考 |
|---|---|---|---|---|---|---|
| `zundamon` | ずんだもん | 坂本アヒル | normal×2 smile×3 surprised×2 angry×2 sad×2 troubled×3 think×3 shy×2 smug×2 doubt love | point×2 raise×2 fold chin×2 | 112 |  |
| `metan` | 四国めたん | 坂本アヒル | normal smile×2 surprised×2 angry×2 sad×2 troubled×3 think×3 shy×2 smug dizzy | point mic point+mic raise raise+mic chin×2 | 115 |  |
| `tsumugi` | 春日部つむぎ | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×2 shy×2 smug love | point raise×2 chin×2 | 112 |  |
| `hau` | 雨晴はう | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×2 shy×2 smug dizzy love | point×2 chin syringe scalpel | 42 |  |
| `ritsu` | 波音リツ | moiky | normal smile×3 surprised×3 angry×3 sad×3 troubled×2 think×2 shy×2 smug doubt dizzy love | point×2 peace×3 fold | 57 |  |
| `takehiro` | 玄野武宏 | moiky | normal smile×2 surprised angry×3 sad×2 troubled×3 think×2 shy×2 smug doubt | raise fold chin×2 | 112 |  |
| `kotaro` | 白上虎太郎 | moiky | normal smile×3 surprised×2 angry×3 sad×3 troubled×3 think×2 shy×2 smug doubt | point×2 raise fold | 39 |  |
| `ryusei` | 青山龍星 | moiky | normal smile×2 surprised×3 angry×3 sad×3 troubled×3 think×2 shy×2 smug doubt | point×2 raise phone pickaxe | 40 |  |
| `himari` | 冥鳴ひまり | moiky | normal smile×3 surprised×2 angry×2 sad×3 troubled×3 think×2 shy×2 smug love | point×2 raise fold chin | 54 |  |
| `sora` | 九州そら | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×3 shy×2 smug | point raise chin×3 | 153 |  |
| `mochiko` | もち子さん | 公式 | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×3 shy×2 smug×2 doubt dizzy | point×2 raise×2 chin×2 | 101 |  |
| `mesuo` | 剣崎雌雄 | moiky | normal smile×2 surprised×2 angry sad×2 troubled×2 think smug | point×2 raise×2 saw | 36 |  |
| `whitecul` | WhiteCUL | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×2 shy×2 smug doubt | point raise×2 | 39 |  |
| `goki` | 後鬼 | moiky | normal smile×3 surprised×3 angry×3 sad×3 troubled×3 think×2 shy×2 smug doubt dizzy love | point×2 peace×2 phone pointer | 65 |  |
| `no7` | No.7 | 公式 | normal smile×2 surprised×2 angry×2 sad×2 troubled×2 think×2 smug doubt | raise | 43 |  |
| `chibijii` | ちび式じい | moiky | normal smile surprised angry×3 sad×3 troubled×3 think shy×2 doubt | raise×3 | 47 | まばたきなし |
| `miko` | 櫻歌ミコ | moiky | normal smile×3 surprised×3 angry×3 sad×3 troubled×2 think×2 shy×2 smug doubt love | point raise×2 fold | 47 |  |
| `sayo` | 小夜/SAYO | moiky | normal smile×3 surprised×2 angry×2 sad×3 troubled×2 think×2 shy×2 smug doubt love | point raise×2 fold | 46 |  |
| `nurse` | ナースロボ＿タイプＴ | moiky | normal smile×2 angry×3 sad×3 troubled×2 think shy×2 doubt dizzy love | point chin syringe knife | 60 |  |
| `benizakura` | †聖騎士 紅桜† | moiky | normal | point fold | 3 | 口は動かない、まばたきなし |
| `akashi` | 雀松朱司 | moiky | normal smile×2 surprised angry×3 sad×2 troubled×3 think×2 shy×2 smug doubt dizzy | point fold chin phone | 80 |  |
| `sourin` | 麒ヶ島宗麟 | moiky | normal surprised×2 angry×3 sad×2 troubled×3 | point×2 raise fold phone stand | 33 | まばたきなし |
| `nana` | 春歌ナナ | moiky | normal smile×3 surprised angry×2 sad×3 troubled×3 think×2 shy×2 smug doubt love | point raise×2 peace×2 phone | 55 |  |
| `aru` | 猫使アル | moiky | normal smile×2 surprised×2 angry×3 sad×3 troubled×2 think×2 shy×2 smug doubt love | raise×2 fold | 53 |  |
| `bii` | 猫使ビィ | moiky | normal smile×2 surprised×2 angry×2 sad×3 troubled×2 think×2 shy×2 smug doubt love | raise×2 fold | 55 |  |
| `usagi` | 中国うさぎ | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×2 shy×3 smug doubt dizzy | raise×2 chin×2 fold | 122 |  |
| `maron` | 栗田まろん | moiky | normal smile×2 surprised×3 angry×3 sad×3 troubled×3 think×2 shy×2 doubt dizzy | raise peace fold stand | 39 |  |
| `aieru` | あいえるたん | 公式 | normal smile×2 surprised×2 angry×2 sad×2 troubled×2 think×2 shy×2 smug doubt dizzy | point raise×2 fold×2 chin×2 keyboard | 162 |  |
| `hanamaru` | 満別花丸 | moiky | normal smile×3 surprised angry×3 sad×2 troubled×3 think×2 shy×2 smug doubt love | point raise fold | 77 |  |
| `nia` | 琴詠ニア | moiky | normal smile×2 surprised×3 angry×3 sad×3 troubled×3 think×2 shy×2 smug doubt love | point×2 raise peace phone tablet | 44 |  |
| `voidoll` | Voidoll | moiky | normal smile surprised angry sad think×2 shy×2 doubt love | raise×2 fold | 19 | 口は動かない、まばたきなし |
| `zonko` | ぞん子 | moiky | normal smile×2 surprised angry×3 sad×3 troubled×3 think×2 shy×2 smug doubt love | peace fold×2 chin×2 phone stand | 165 |  |
| `tsurugi` | 中部つるぎ | moiky | normal smile×3 surprised×2 angry×3 sad×3 troubled×2 think×2 shy×2 smug doubt love | fold | 77 |  |
| `rito` | 離途 | moiky | normal smile×2 surprised angry×3 sad×3 troubled×3 think×2 shy×2 smug doubt | point fold×2 chin×2 phone | 47 |  |
| `saehaku` | 黒沢冴白 | moiky | normal smile×2 surprised angry×2 sad×3 troubled×3 think×2 shy×2 smug doubt | point fold×2 chin×2 phone | 93 |  |
| `yurei` | ユーレイちゃん | moiky | normal smile×3 surprised angry×3 sad×3 troubled×3 think×2 shy×3 smug doubt dizzy love | peace×2 chin×2 gamepad | 168 |  |
| `zunko` | 東北ずん子 | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×2 shy×2 smug doubt | raise×2 chin×2 bow | 95 |  |
| `kiritan` | 東北きりたん | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×2 shy×2 smug dizzy | raise×3 chin fold mic controller | 115 |  |
| `itako` | 東北イタコ | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×2 shy×2 smug | point raise×2 chin | 62 |  |
| `ankomon` | あんこもん | 坂本アヒル | normal smile×3 surprised×2 angry×2 sad×2 troubled×3 think×2 shy×2 smug doubt dizzy | point raise×2 fold chin×2 mic | 107 |  |
| `tobari` | 夜語トバリ | moiky | normal smile×3 surprised angry×3 sad×2 troubled×3 think×2 shy×2 smug doubt love | point raise phone book chin peace card | 85 |  |
| `mitama` | 暁記ミタマ | moiky | normal smile×2 angry×2 sad×3 troubled×3 think shy×3 doubt dizzy love | point chin phone tray | 63 |  |
| `yuka` | 里石ユカ | moiky | normal smile×2 surprised angry×3 sad×3 troubled×3 think shy×3 smug dizzy love | point raise phone | 51 |  |
| `reimu` | 霊夢 | きつね | normal smile×3 surprised×2 angry×3 sad×2 troubled×2 think×2 shy×2 smug doubt dizzy | － | 53 |  |
| `marisa` | 魔理沙 | きつね | normal smile×3 surprised×2 angry×3 sad×2 troubled×2 think×2 shy×2 smug doubt dizzy | － | 53 |  |

- 表情の形は、PSD の 14 人とゆっくりは見本を見て目・眉・口・顔色を選んだもの。moiky さんの素材は、付属の preset.ini（普通・喜び・怒り・悲しみ など）を 1 つ目の形にし、
  ほかの形と、preset.ini に無いラベルを、パーツの名前（驚き・困り・照れ・ハート・ぐるぐる など）から組んだもの。素材にそのパーツが無いラベルは作っていない。
- 度合い（控えめ・ふつう・強め）は、形の中身から決めたもの（開いた目のほほえみは控えめ、涙や青ざめは強め、など）。`recipes/<登場人物>.json` の `levels` で変えられる。
- 体は、素材の腕・体の差分をラベルに当てたもの。衣装の差分は取り込んでいない（レシピの `poses` に足せば書き出せる）。

## 坂本アヒルさん（PSD。作品ページの条件は「公式の規約の範囲なら何に使ってもよい」）

アップローダーのパスワードは、作品ページ（ニコニコ静画）の説明文に書かれている（作者が説明を読んでもらうために置いているものなので、ここには写さない）。

| 登場人物 | 話者 | 作品ページ | ダウンロード |
|---|---|---|---|
| `zundamon` | ずんだもん | https://seiga.nicovideo.jp/seiga/im11206626 | https://ux.getuploader.com/s_ahiru/download/59 |
| `metan` | 四国めたん | https://seiga.nicovideo.jp/seiga/im10791276 | https://ux.getuploader.com/s_ahiru/download/35 |
| `tsumugi` | 春日部つむぎ | https://seiga.nicovideo.jp/seiga/im10849150 | https://ux.getuploader.com/s_ahiru/download/42 |
| `hau` | 雨晴はう | https://seiga.nicovideo.jp/seiga/im10880094 | https://ux.getuploader.com/s_ahiru/download/43 |
| `sora` | 九州そら | https://seiga.nicovideo.jp/seiga/im10924061 | https://ux.getuploader.com/s_ahiru/download/36 |
| `whitecul` | WhiteCUL | https://seiga.nicovideo.jp/seiga/im11232248 | https://ux.getuploader.com/s_ahiru/download/54 |
| `usagi` | 中国うさぎ | https://seiga.nicovideo.jp/seiga/im11232921 | https://ux.getuploader.com/s_ahiru/download/57 |
| `zunko` | 東北ずん子 | https://seiga.nicovideo.jp/seiga/im11135374 | https://ux.getuploader.com/s_ahiru/download/49 |
| `kiritan` | 東北きりたん | https://seiga.nicovideo.jp/seiga/im10686052 | https://ux.getuploader.com/s_ahiru/download/8 |
| `itako` | 東北イタコ | https://seiga.nicovideo.jp/seiga/im11385703 | https://ux.getuploader.com/s_ahiru/download/60 |
| `ankomon` | あんこもん | https://seiga.nicovideo.jp/seiga/im11729549 | https://ux.getuploader.com/s_ahiru/download/71 |

後鬼の坂本アヒルさん版（非公式の擬人化、https://seiga.nicovideo.jp/seiga/im11049317 ）は、パスワードを確かめられず取っていない。後鬼は moiky さんの素材を使っている。

## 公式の PSD（直リンク）

| 登場人物 | 話者 | レシピ | 配布元 | 規約の要点 |
|---|---|---|---|---|
| `no7` | No.7 | `no7.json` | https://voiceseven.com/ （seven_tachie.zip） | 公式の規約の範囲で自由 |
| `mochiko` | もち子さん | `mochiko.json` | https://vtubermochio.wixsite.com/mochizora/素材配布場所 （Google Drive） | 個人・同人は可、営利・企業は問い合わせ。二次配布は不可 |
| `aieru` | あいえるたん | `aieru.json` | https://www.infiniteloop.co.jp/special/aieru-tan/ （illust.zip） | 動画・配信は収益化も可、改変可。公式素材の販売は不可 |

`aieru` の PSD は 7500×10000 で、書き出しに 8GB ほどのメモリと 1 分ほどかかる。

## moiky さん（パーツのフォルダ。パスワードなし）

規約は https://seiga.nicovideo.jp/clip/3329926 （元のキャラクターとソフトの規約に従う。収益化・動画外の利用は作者からは制限しない。改変は良識の範囲で自由。作者の表記は任意）。
「パーツの場所」は zip を展開した中のフォルダ。レシピは付属の preset.ini の表情を元に、足りない表情とポーズを足したもの（レシピなしでも preset.ini から自動で書き出せる）。

| 登場人物 | 話者 | ダウンロード | パーツの場所 | レシピ |
|---|---|---|---|---|
| `ritsu` | 波音リツ | https://ux.getuploader.com/moiky00/download/60 | `RITSU/YMM4用` | `ritsu.json` |
| `takehiro` | 玄野武宏 | https://ux.getuploader.com/moiky01/download/16 | `玄野武宏/YMM4用` | `takehiro.json` |
| `kotaro` | 白上虎太郎 | https://ux.getuploader.com/moiky01/download/12 | `KOTARO/YMM4登録用` | `kotaro.json` |
| `ryusei` | 青山龍星 | https://ux.getuploader.com/moiky01/download/50 | `青山龍星/YMM4用＿青山龍星` | `ryusei.json` |
| `himari` | 冥鳴ひまり | https://ux.getuploader.com/moiky01/download/21 | `冥鳴ひまりv2/YMM4用` | `himari.json` |
| `mesuo` | 剣崎雌雄 | https://ux.getuploader.com/moiky00/download/61 | `KENZAKI/YMM4用` | `mesuo.json` |
| `goki` | 後鬼 | https://ux.getuploader.com/moiky01/download/27 | `GOKI/後鬼` | `goki.json` |
| `chibijii` | ちび式じい | https://ux.getuploader.com/moiky01/download/4 | `ちび式じい/YMM4用ちび式じい` | `chibijii.json` |
| `miko` | 櫻歌ミコ | https://ux.getuploader.com/moiky01/download/7 | `櫻歌ミコ/YMM4用` | `miko.json` |
| `sayo` | 小夜/SAYO | https://ux.getuploader.com/moiky01/download/3 | `小夜/YMM4用` | `sayo.json` |
| `nurse` | ナースロボ＿タイプＴ | https://ux.getuploader.com/moiky01/download/20 | `ナースロボTT/YMM4用` | `nurse.json` |
| `benizakura` | †聖騎士 紅桜† | https://ux.getuploader.com/moiky01/download/14 | `聖騎士紅桜/YMM4用` | `benizakura.json` |
| `akashi` | 雀松朱司 | https://ux.getuploader.com/moiky01/download/17 | `雀松朱司/YMM4用` | `akashi.json` |
| `sourin` | 麒ヶ島宗麟 | https://ux.getuploader.com/moiky01/download/15 | `麒ヶ島宗麟/YMM4用` | `sourin.json` |
| `nana` | 春歌ナナ | https://ux.getuploader.com/moiky01/download/22 | `春歌ナナ/YMM4用` | `nana.json` |
| `aru` | 猫使アル | https://ux.getuploader.com/moiky01/download/26 | `猫使アル/YMM4用` | `aru.json` |
| `bii` | 猫使ビィ | https://ux.getuploader.com/moiky01/download/24 | `猫使ビィ/YMM4用` | `bii.json` |
| `maron` | 栗田まろん | https://ux.getuploader.com/moiky01/download/39 | `栗田まろん/YMM4用` | `maron.json` |
| `hanamaru` | 満別花丸 | https://ux.getuploader.com/moiky01/download/56 | `満別花丸/YMM4用_満別花丸` | `hanamaru.json` |
| `nia` | 琴詠ニア | https://ux.getuploader.com/moiky01/download/37 | `琴詠ニア/YMM4用` | `nia.json` |
| `voidoll` | Voidoll | https://ux.getuploader.com/moiky02/download/17 | `Voidoll/voidoll_YMM4用` | `voidoll.json` |
| `zonko` | ぞん子 | https://ux.getuploader.com/moiky02/download/1 | `ぞん子/YMM４用＿ぞん子` | `zonko.json` |
| `tsurugi` | 中部つるぎ | https://ux.getuploader.com/moiky02/download/33 | `中部つるぎ/YMM4用＿中部つるぎ` | `tsurugi.json` |
| `rito` | 離途 | https://ux.getuploader.com/moiky02/download/10 | `離途/YMM4用＿離途` | `rito.json` |
| `saehaku` | 黒沢冴白 | https://ux.getuploader.com/moiky02/download/9 | `黒沢冴白/YMM4用＿黒沢冴白` | `saehaku.json` |
| `yurei` | ユーレイちゃん | https://ux.getuploader.com/moiky02/download/15 | `ユーレイちゃん/YMM4用＿ユーレイちゃん` | `yurei.json` |
| `tobari` | 夜語トバリ | https://ux.getuploader.com/moiky02/download/48 | `夜語トバリ/YMM4用＿夜語トバリ` | `tobari.json` |
| `mitama` | 暁記ミタマ | https://ux.getuploader.com/moiky02/download/46 | `暁記ミタマ/YMM4用＿暁記ミタマ` | `mitama.json` |
| `yuka` | 里石ユカ | https://ux.getuploader.com/moiky02/download/47 | `里石ユカ/YMM4用＿里石ユカ` | `yuka.json` |
| `mesuo_human` | 剣崎雌雄（人間の姿） | https://ux.getuploader.com/moiky02/download/16 | `剣崎雌雄人間/YMM4用＿剣崎雌雄人間` | `mesuo_human.json` |

- `benizakura`（†聖騎士 紅桜†）は顔のパーツが無く表情は normal だけ（ポーズは 2 つ）、`voidoll` は口のコマが無い。口パクは体の弾みだけになる。
- `chibijii`・`sourin` は目のコマが無く、まばたきしない。

## ゆっくり（霊夢・魔理沙）

頭だけの絵なので、`casts.json` の `height` で小さく表示する。

| 登場人物 | 素材 | レシピ | 配布元 |
|---|---|---|---|
| `reimu`・`marisa` | きつねさんの新きつねゆっくり（れいむ.zip・まりさ.zip） | `kitsune_yukkuri.json`（共通） | https://ci-en.net/creator/34363/article/1770577 |
| `reimu_kai`・`marisa_kai` | nicotalk＆キャラ素材配布所の「ゆっくり霊夢改」「ゆっくり魔理沙改」（素材: ころボンさん） | `reimu.json`・`marisa.json` | http://nicotalk.com/charasozai_yk.html |

- きつねさんの規約（ https://ci-en.net/creator/34363/article/1749040 ）: 非商用は無償、商用は事前の許諾と有償ライセンス。個人が公式の仕組みで得る動画の広告収益は無償の範囲。
  改変（色の変更・パーツの組換え）は利用に必要な範囲で可、改変後の素材の譲渡と、改変を他者に依頼・受注することは禁止。
  AI に学習させること・素材を基に AI で新しい画像を作ることは禁止、AI による画像生成・高画質化は事前の許諾と有償ライセンスが要る。
  Amazon ビデオダイレクト・Vimeo・Dailymotion での利用は禁止。明示されていない用途は申請フォームで事前に相談する。
  東方 Project の一次創作者のガイドラインにも従う。
- ここでの書き出しは、パーツをプログラムで重ねるだけ（AI による生成・高画質化はしていない）。AI エージェントに取得・書き出しを任せることは
  規約に明示が無く、利用者の判断で行った。気になる場合は自分の手で `parts_export.py` を実行するか、作者に確かめる。
- nicotalk の規約: 東方 Project の一次創作者のガイドラインに従う場合に限り動画で使える。商用利用は禁止、キャラ素材の二次配布は禁止、クレジットは不問。
  `reimu_kai`・`marisa_kai` はプリセットではない。使うときはフォルダの名前を変えるか、台本の隣の `chars/reimu/` に写す。

## 公式 SD 立ち絵（デフォルメ。`chars/<名前>_sd/`）

ぼいすぼっくす ばけーしょん 公式 SD 立ち絵の「<名前>差分付き.psd」（作画: MARCO(ぺしっこ)）。配布元 https://vtubermochio.wixsite.com/voicevox41/配布場所 （Google Drive）。
波音リツ・玄野武宏・白上虎太郎・青山龍星・剣崎雌雄の 5 人分を `ritsu_sd`・`takehiro_sd`・`kotaro_sd`・`ryusei_sd`・`mesuo_sd` に書き出してある（レシピは共通の `voicevox_sd.json`）。
プリセットではないので、使うときはフォルダの名前を登場人物の名前に変えるか、台本の `chars:` で別の置き場所を指す。規約: 非商用（動画の広告収益は可）、加工可、二次配布は不可。

## 収益化・商用で気を付ける話者（キャラクター側の規約）

ぞん子（商用は問い合わせ）、ユーレイちゃん（非商用）、Voidoll（個人のみ）、中部つるぎ（原則非営利）、青山龍星（企業・個人事業主は事前申請）、
小夜/SAYO（非営利か実費回収まで）、霊夢・魔理沙（商用禁止）。ここに無い話者も、公開の前に `policy.txt` の規約の URL を開いて確かめる。
