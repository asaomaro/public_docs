---
name: youtube-upload
description: 動画を YouTube に限定公開（unlisted）でアップロードし、URL を返す。motion-video・yukkuri-kaisetsu で作った動画の HTML を字幕・音入りの WebM に録り（画面なしの Chrome）、題・概要欄・タグ・サムネイル・字幕を付けて YouTube Data API で上げる。公開（public）にはしない。「YouTube に上げて」「限定公開でアップロードして」「動画ファイルにして」「WebM に書き出して」と言われたときに使用する。
---

# youtube-upload — YouTube に限定公開で上げる

動画の HTML → `record.py` → WebM → `upload.py` → YouTube（限定公開）→ URL。
題・概要欄・サムネイルは **yukkuri-publish**、字幕（SRT）は **video-export** が作ったものを、あれば拾う。録画は隣の **motion-video**（`shoot.py`）を使う。

| 道具 | すること |
|---|---|
| `record.py 動画.html` | 画面なしの Chrome で最初から再生して、字幕・音入りの WebM に録る（1920×1080。ショートは 1080×1920）。**動画の長さだけ時間がかかる** |
| `upload.py check`・`auth`・`logout` | 準備ができているか・ブラウザで認可する（使う人が自分でする）・認可を取り消す |
| `upload.py upload 動画.webm --script 台本.txt` | 送る中身を出す。`--yes` を付けたときだけ送り、URL を出す |

## 守ること

- **公開範囲は限定公開（`unlisted`）か非公開（`private`）だけ**。公開（public）は、この道具ではできない。公開は、使う人が YouTube Studio で自分でする。
- **送る前に、送る中身を使う人に見せて、よいと言われてから `--yes` を付ける**（アップロードは外に出す操作。前に「上げて」と言われていても、動画ごとに確かめる）。
- **OAuth クライアントのファイルとトークンを、読まない・表示しない・コマンド行に書かない・リポジトリに入れない**。置き場所は `~/.config/youtube-upload/` だけ。`cat` や `Read` で中を見ない（確かめるのは `upload.py check`）。
- **認可（`auth`）は、画面の前にいる使う人がする**。Google の同意画面で、Claude が代わりに同意することはない。
- 上げるのは動画のファイルだけ。HTML は配らない（集めた立ち絵・背景・BGM の多くは、素材としての再配布を禁じている）。
- 上げる前に、yukkuri-publish の「公開の前に確かめる」（クレジット・出典・キャラクターの規約・収益化）を済ませる。限定公開でも、URL を知っている人は誰でも見られる。

## 手順

### 0. 準備ができているか（毎回）

```bash
python3 <skill_dir>/upload.py check        # 終了コード 2 なら、準備が要る（下の「準備」を使う人に伝える）
```

### 1. 動画のファイルにする

```bash
python3 <skill_dir>/record.py 動画.html                   # 動画.webm と、確かめの 1 コマ 動画.check.png（Bash の timeout は 600000。長い動画は run_in_background）
python3 <skill_dir>/record.py 動画.html -o out.webm --size 720   # 1280×720 で
python3 <skill_dir>/record.py 動画.html --size 1440 --bitrate 20 --fps 60 --format mp4
```

- 録り方は引数で選ぶ（プレイヤーの ⚙ の「保存の設定」と同じもの。引数が勝つ）: `--size 720・1080（既定）・1440・2160`、`--bitrate`（映像の Mbps。既定は自動 = 1080 で 8）、
  `--fps 30・60`、`--audio-bitrate`（kbps。既定 192）、`--format webm（VP9。既定）・vp8・av1・mp4（H.264）`。YouTube に上げるだけなら既定のままでよい。
- 声を入れた HTML（`--voicevox`）を渡す。ブラウザの読み上げの声は録れない（warn が出る）。配布用（`--dist`）の HTML は録れない。
- 終わったら `<出力名>.check.png` を Read で開いて見る。長さ・大きさ・音のトラック・音の大きさ・録っている間のコマ数が出る。
  `warn:` が出たら直す: 長さが台本と 3 秒より違う／音のトラックが無い／測った所が無音（`--at 0.3` で別の所を測る）。
- 「コマ数が少ない」（毎秒 24 コマ未満）は、動きがかくつく。ほかの重い作業を止めて録り直すか、`--size 720` で録る。
  画面なしの Chrome はソフトウェアで描くので、**ショート（縦）の 1080×1920 は毎秒 20 コマほど**になる（横の 1920×1080 は毎秒 50 コマ前後。5 分の動画で約 200MB）。
  ショートをなめらかに録るなら `--size 720`（720×1280）か、使う人が HTML を開いて ⚙「動画ファイル（WebM）で保存」を押す（GPU で描く）。
- 前の `engine.js` で作った HTML は 1280×720 で録れる（warn が出る）。1920×1080 にするなら HTML を作り直す。
- 使う人が自分で録った WebM・編集ソフトで書き出した MP4 があれば、この手順は飛ばす。

### 2. 送る中身を出して、確かめてもらう

```bash
python3 <skill_dir>/upload.py upload 動画.webm --script 台本.txt          # まだ送らない
```

`--script` を渡すと、台本の `title:`・`tags:` と、隣のファイルを拾う（書いた引数が勝つ）。

| 送るもの | 拾う所 | 引数 |
|---|---|---|
| 題 | 台本の `title:`（motion-video は JSON の `title`） | `--title` |
| 概要欄 | `<台本名>.description.txt`（yukkuri-publish）→ `<台本名>_export/youtube_description.txt`（video-export）→ 台本の `summary:` | `--description ファイル` |
| タグ | 台本の `tags:` | `--tags "a, b"` |
| サムネイル | `<台本名>.thumbnail.png`（yukkuri-publish） | `--thumbnail`・`--no-thumbnail` |
| 字幕 | `<台本名>_export/*.ja.srt`（video-export）。**字幕の権限で認可したときだけ**送る | `--captions`・`--no-captions` |

- 出た一覧（動画・公開範囲・題・概要欄・タグ・サムネイル・字幕・子ども向けか・通知）を、そのまま使う人に見せる。
- 止まる所: 題が無い・100 字を超える／概要欄が 5000 バイトを超える／題・概要欄に `<` `>` がある（YouTube が受け付けない。出典の URL を `<…>` で囲まない）。
- そのほかの引数: `--privacy private`（非公開）・`--made-for-kids`（子ども向けと申告。既定は「子ども向けではない」）・`--synthetic`（合成コンテンツの開示。要るのは、
  実在の人や出来事を本物のように見せたときだけ）・`--notify`（登録者に通知。既定はしない）・`--category ID`・`--lang`（既定 `ja`）。

### 3. 送る

```bash
python3 <skill_dir>/upload.py upload 動画.webm --script 台本.txt --yes     # Bash の timeout は 600000
```

- 8MB ずつ送り、途切れたら届いている所から続ける（6 回続けて途切れたら止まる）。
- 終わると `OK : https://youtu.be/…（限定公開）` と YouTube Studio の URL が出て、動画の隣に `<動画名>.youtube.json`（動画の ID・URL・公開範囲・日時）が残る。
- 同じファイルを 2 回は上げない（`<動画名>.youtube.json` で見分ける。もう 1 本上げるなら `--again`）。
- サムネイル・字幕だけ失敗したとき（サムネイルは、電話番号で確認したチャンネルでないと付けられない）は、動画は上がったままで warn が出る。YouTube Studio から付ける。

### 4. 渡す

- URL と YouTube Studio の URL を伝える。
- **限定公開になっているかを、YouTube Studio で 1 回見てもらう**（下の「決まり」の 2。審査を受けていないプロジェクトから上げた動画は、非公開に固定される）。
- 高画質（HD）の処理が終わるまで数分かかる。概要欄の目次がチャプターになっているか・字幕・サムネイルも、そこで見てもらう。

## 準備（最初の 1 回。使う人がする）

Claude は、手順を伝えて待つ。Google Cloud の画面を代わりに操作しない。

1. [Google Cloud コンソール](https://console.cloud.google.com/) でプロジェクトを作り、「API とサービス」→「ライブラリ」で **YouTube Data API v3** を有効にする。
2. 「OAuth 同意画面」を作る（対象は「外部」。テストユーザーに、動画を上げる自分の Google アカウントを足す）。
3. 「認証情報」→「認証情報を作成」→「OAuth クライアント ID」→ 種類は **デスクトップ アプリ**。JSON をダウンロードして、次の名前で置く:
   `~/.config/youtube-upload/client_secret.json`（WSL なら WSL の中のホーム）
4. 認可する。使う人のブラウザが開くので、動画を上げるチャンネルのアカウントを選んで同意する:
   ```bash
   python3 <skill_dir>/upload.py auth              # 動画とサムネイルを上げる権限だけ（おすすめ）
   python3 <skill_dir>/upload.py auth --captions   # 字幕も上げる（アカウントの管理まで含む広い権限を求める）
   ```
   - Claude が Bash で実行してもよい（URL が画面に出て、同意を 300 秒まで待つ）。使う人がプロンプトに `! python3 <skill_dir>/upload.py auth` と打ってもよい。
   - 同意したのにブラウザが「接続できません」になるとき（ブラウザから `127.0.0.1` に届かない環境）は、使う人が自分の端末で `upload.py auth --paste` を実行し、
     アドレス欄の URL を貼る（この URL には認可コードが入っているので、**会話には貼らない**）。
5. やめるときは `python3 <skill_dir>/upload.py logout`（認可を取り消して、手元のトークンを消す）。

## 決まり（YouTube Data API v3・Google の OAuth の公式の説明。2026-10-04 に確かめた）

1. **1 日の上限**: `videos.insert`（動画を上げる）は、既定で 1 日 100 回まで（ほかの操作と別の枠）。サムネイルの設定は約 50 単位、字幕は 400 単位で、
   こちらは 1 日 10,000 単位の枠から引かれる。枠は太平洋時間の 0 時に戻る。
2. **審査を受けていないプロジェクトから上げた動画は、非公開（private）に固定される**（2020-07-28 より後に作ったプロジェクト）。
   外すには、プロジェクトごとに、利用規約を守っているかの監査（audit）を Google に申し込んで通す。固定されている間は、限定公開にも公開にもできない。
   上げた後に公開範囲が頼んだものと違えば warn が出るが、後から固定されることもあるので、YouTube Studio で見てもらう。
3. **同意画面が「テスト中」のプロジェクトは、認可が 7 日で切れる**（更新用のトークンの期限）。切れたら `upload.py auth` をやり直す（終了コード 2 で知らせる）。
4. 認可は「手元のアプリ」の流れ（ループバック `http://127.0.0.1:ポート` と PKCE）。テレビなどの機器用の流れ（コードを打つ方式）は、アップロードの権限を扱えない。
5. 題は 100 字まで、概要欄は 5000 バイトまで、どちらも `<` `>` は使えない。タグは全部で 500 字まで（カンマと、空白を含むタグの引用符も数える）。
6. 動画は 256GB まで。続きから送れる方式（resumable）で、8MB（256KB の倍数）ずつ送る。

## メモ

- 終了コード: 0 = できた／1 = 失敗／2 = 準備が要る（クライアントのファイルが無い・認可していない・認可が切れた）。
- 確かめた範囲: `upload.py` は、偽の Google のサーバーで回帰テストをしている（`../tests/test_youtube_upload.py`。認可・続きから送る・公開にしない・秘密を出さない）。
  **本物の YouTube へ上げて確かめるのは、使う人の認可が要る**。字幕のアップロード（`uploadType=multipart`）は、本物で確かめるまでは試しとみる。
- `record.py` が録る WebM は、ブラウザの MediaRecorder のもの（既定は VP9・Opus。ビットレートは上限で、絵の動きが少なければそれより小さくなる）。ファイルに長さの情報が入らない（再生はできる。YouTube が受け付けるかは、本物で 1 回上げて確かめる）。
- `upload.py`・`record.py`・`engine.js` の録画の所を変えたら、回帰テストを回す: `python3 -W ignore::ResourceWarning -m unittest discover -s ../tests -t ../tests`。
