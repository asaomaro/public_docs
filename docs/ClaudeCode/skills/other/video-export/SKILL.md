---
name: video-export
description: motion-video（モーショングラフィックスの動画 HTML）・yukkuri-kaisetsu（掛け合いの解説動画）の台本から、YouTube への投稿と動画編集ソフト向けのファイルを書き出す。字幕（SRT・WebVTT。訳した多言語の字幕も）、概要欄に貼るチャプターとクレジット、ゆっくりMovieMaker4（YMM4）の台本 CSV とプロジェクト（.ymmp）、AviUtl 拡張編集のオブジェクトファイル（.exo）。映像（字幕・音なし WebM）と音（声・音楽・効果音・全部を別々の WAV）は、同じ時間割で作る HTML のプレイヤーの ⚙ から書き出す。「YouTube に上げたい」「字幕ファイルがほしい」「YMM4 で仕上げたい」「AviUtl で編集したい」「音声を別々に」「英語の字幕も」などと言われたときに使用する。
---

# video-export — 動画を YouTube・編集ソフト向けに書き出す

台本（motion-video の `.json` か yukkuri-kaisetsu の `.txt`）→ `export.py` → `<台本名>_export/` に一式。
台本の読み込みと時間割は、隣の **motion-video**（`.txt` は **yukkuri-kaisetsu** も）を使う（同じ場所に置く）。

| 種類（`--to`） | 書き出すもの |
|---|---|
| `youtube` | 字幕 `<題>.ja.srt`・`.vtt`（掛け合いは「名前：せりふ」）／概要欄に貼る `youtube_description.txt`（チャプターの時刻・クレジット）／訳す元 `subs.ja.txt` |
| `ymm4` | ゆっくりMovieMaker4 の台本 `<題>_ymm4_script.csv`（A 列キャラクター名・B 列セリフ）／映像・音楽・効果音・声・字幕を層に並べた `<題>.ymmp`（実験的） |
| `exo` | AviUtl（拡張編集）の `<題>.exo`（映像・音楽・効果音・声（話し手ごとの層）・縁取りの字幕。Shift_JIS） |

どの種類でも、同じ時間割の `<題>.html` と、何をどこに置くかの `README.txt` も出る。

## 手順

### 0. 確かめる
- 台本がどれか（motion-video の `.json`・yukkuri-kaisetsu の `.txt`）。まだ無ければ、先にそのスキルで作る。
- どこに出すか（YouTube だけ／YMM4／AviUtl）。分からなければ `AskUserQuestion` で聞く（複数選択。おすすめは YouTube）。
- **声を前もって作るか**。公開する動画は VOICEVOX（`--voicevox`）か用意した WAV（`--voices-dir`）で作る。
  ブラウザの読み上げの声は書き出せない（字幕・プロジェクトに声が入らず、時間は見積もりになる）。
- YMM4・AviUtl に出すなら、書き出したフォルダを置く **Windows の場所**（`--win-dir`）。Windows 以外で作るときは必ず聞く。

### 1. 書き出す

```bash
python3 <skill_dir>/export.py 台本.json --to youtube --voicevox
python3 <skill_dir>/export.py 台本.txt --to all --voicevox --win-dir "C:\Users\me\Videos\台本_export"
```

| 引数 | 意味 |
|---|---|
| `--to` | `youtube`・`ymm4`・`exo` をカンマで。既定 `all` |
| `--voicevox`・`--voicevox-url`・`--voices-dir` | 声を前もって作る・用意した WAV を当てる（motion-video と同じ） |
| `--win-dir` | YMM4・AviUtl のプロジェクトに書く素材の場所（Windows の絶対パス）。既定は書き出す場所 |
| `--fps` | プロジェクトのフレームレート（既定 30） |
| `--out-dir` | 書き出す場所（既定 `<台本名>_export/`） |
| `--player`・`--theme` | 一緒に作る HTML のプレイヤー・配色 |

- 警告を読む: YouTube のチャプターは **3 章以上・どれも 10 秒以上・最初が 0:00** で表示される（外れると警告）。
- 声の WAV は `voices/` に集め、プロジェクトはそこを指す。

### 2. 映像と音をプレイヤーから書き出す（ユーザーがする）
音楽・効果音はブラウザで合成するため、映像と音はプレイヤーで作る。`<題>.html` を開き、⚙（設定）から:

- **編集用の映像（字幕・音なし WebM）** → `<題>_video.webm`（1920×1080。最初から 1 倍速で録るので、動画の長さだけかかる）
- **音のトラックを書き出す（WAV）** → `<題>_voice.wav`・`_music.wav`・`_sfx.wav`・`_mix.wav`（48kHz。録らずにすぐできる）

ダウンロードされたファイルを書き出したフォルダへ移す。どちらも台本どおりの時間割なので、字幕・プロジェクトと時刻がそろう。

### 3. ほかの言語の字幕（頼まれたとき）
`subs.ja.txt`（1 行に字幕 1 つ）を Claude が訳し、**同じ行数**で同じフォルダに `subs.en.txt` などを書いて、もう一度 `--to youtube` で書き出す。
`<題>.en.srt`・`.vtt` ができる（行数が違うと警告して作らない）。1 行に収まる長さに訳す。
YouTube の多言語の音声トラックにするには、その言語の声（WAV）で動画を作り直す（字幕を訳すだけではできない）。

### 4. 渡す
- 書き出したフォルダと `README.txt` を伝え、⚙ から映像と音を書き出して置く手順を一言で添える。
- YouTube: 字幕は YouTube Studio の「字幕」→「ファイルをアップロード」→「タイミングあり」。概要欄に `youtube_description.txt` を貼る。
  動画の本体は ⚙ の「動画ファイル（WebM）で保存」（字幕・音入り）か、編集ソフトで書き出したもの。
- YMM4: CSV は「ファイル → 台本ファイルを開く」で読む。**A 列の名前は YMM4 のキャラクター名と一致していないと読めない**
  （yukkuri-kaisetsu なら台本の `<名前>.name` を合わせる）。YMM4 のキャラクターの声・立ち絵で作り直すときに使う。
  `.ymmp` は YMM4 の公開されていない形式に合わせた実験的なもの。開けない・崩れるときは CSV を読み、映像と音を手で置く。
- AviUtl: `.exo` をタイムラインへドラッグ。WebM を読むには L-SMASH Works などの入力プラグインが要る。
- 素材（立ち絵・声・曲）の利用規約とクレジットの表記を確かめるよう添える（`youtube_description.txt` のクレジット）。

## 層の並び（YMM4・AviUtl 共通。下から）
映像 → 音楽 → 効果音 → 声（話し手ごとに 1 層。ナレーションは 1 層）→ 字幕（話し手の色で縁取り）。

## メモ
- 書き出し用の印（声の WAV のローカルのパスなど）は HTML に入れない（motion-video の build.py が外す）。
- 書き出した字幕・プロジェクトの時刻は台本どおり。プレイヤーで再生したときの時刻は、ブラウザの読み上げの速さで少し変わることがある
  （前もって作った声なら変わらない）。
