# aidev プラグイン（Sodashitsu のアプリ）

PJ の `.aidev/` を読み、aidev（SDD ハーネス）による開発を、Sodashitsu の**アプリ画面**で見て・動かす plugin アプリ。

- **見る**: 作業（`.aidev/works/*`）の一覧・進捗・詳細（工程・tasks・文書・events）と、backlog。
- **動かす**: アプリにつき 1 つの**監督エージェント**（Claude Code）を起動し、アプリから指示を出す。各作業は別の**担当エージェント**（Claude Code）が受け持ち、監督と連携する。
- **続ける**: 監督・担当の**セッション ID を記憶**し、止まっても同じ会話で**再開**できる。
- **呼べる**: アプリの操作は `sodactl plugin call aidev <操作>` でも呼べる（監督・担当のエージェントもこれを使う）。

`.aidev/` は**読むだけ**で書き換えない（aidev の state は aidev CLI と工程スキルだけが書く）。依存は Node 標準ライブラリだけ。

## 導入

前提: Sodashitsu（`soda serve`）が動いていること、設定「スクリプトが動く表示」が有効なこと（無効のときは読むだけの画面になる）、
`sodactl` が**サーバと同じ OS 利用者で `sodactl login` 済み**であること（プラグインは `sodactl` を呼んでエージェントを起こす）。

```sh
# このフォルダを配布物にする
sodactl plugin pack docs/ClaudeCode/skills/aidev/aidev-docs/soda-plugin --out aidev.sodaplugin
# 利用者全体へ導入（PJ だけなら --state-dir の代わりに --project-dir <PJ>）
sodactl plugin install aidev.sodaplugin --state-dir <状態ディレクトリ>
# コード・作者・許可（script-html）を確かめてから有効にする
sodactl plugin enable aidev --state-dir <状態ディレクトリ>
sodactl ext reload
```

PJ に導入したときは、設定の「拡張」で**プロジェクトの拡張の承認**が別に要る。配置したパッケージを画面から入れるなら、設定「拡張」の「パッケージを探す」
（端末版はメニューの「プラグインパッケージ…」）を使う。

## 使い方

1. タブの［＋］の **［タブの種類］で「aidev」** を選ぶ（PJ フォルダを設定した workspace で使う）。
   既存のタブには **［ビューを追加］→「aidev の進捗」** で、帯・パネル・浮いた窓の要約を足せる（端末版は Markdown）。
2. **監督**: タブを開くと、監督が動いていなければ自動で 1 回だけ起動する（記録があれば再開。設定で切れる）。失敗したら自動では繰り返さない。
   ［監督を起動］［監督を再開］で手動でも起動できる。承認待ち（信頼の確認など）のときは、［監督の端末を表示］か作業画面で答える。
3. **指示**: 「監督への指示」の欄（Ctrl+Enter で送る）と定型ボタン。監督の報告・担当の報告・アプリの出来事は「ログ」に出る（`question` は目立つ）。
4. **作業**: 一覧（進行中／すべて）から作業を選ぶと、工程の並び・state・tasks（読み取り専用）・文書（Markdown を簡易表示）・events が見られる。
   詳細の「担当」で、［担当を起動］（指示つき）・［再開］・［指示を送る］・［端末を表示］・［監督に任せる］が使える。
5. **担当**: 監督（または利用者）が起動すると、新しい端末タブで Claude Code が動き、担当 → 監督へ**グラフの線**（監督・承認の代理・完了のトリガ）が結ばれる。
   担当が一区切りつくと、トリガの線が監督へ知らせる。担当は `worker-report` で進捗・質問・失敗を報告する。
6. **再開**: エージェントが止まって（pane が無い・エージェントが居ない）も、台帳のセッション ID で `--resume` して同じ会話に戻れる。
   Sodashitsu のサーバの再起動で会話が自動で復元された場合は、同じ pane にエージェントが居れば「生きている」扱い（名前は付け直す）。

## 操作一覧

`sodactl plugin operations aidev --tab <アプリのタブ>` で入力スキーマが見られる。値は検証され（型・長さ・書式・enum）、指示・報告は 16 KiB まで。

| 名前 | 入力 | 内容 |
|---|---|---|
| `works-list` | `{all?}` | 作業の一覧（slug・current・next・mode・profile・state・tasks の進み・担当の状態）。`all` を省くと進行中だけ |
| `work-get` | `{slug}` | 詳細（state・工程・tasks・文書の一覧・events・担当） |
| `work-doc` | `{slug,name}` | 文書の本文（作業フォルダ直下の `*.md`。512 KiB で切る） |
| `backlog-list` | `{}` | backlog の要約（ファイルごとの未着手の数と先頭 50 件） |
| `agents-list` | `{}` | 監督・担当（セッション ID・状態・pane）と設定 |
| `supervisor-start` / `supervisor-resume` | `{model?}` / `{}` | 監督の起動（動いていれば何もしない）／同じ会話での再開 |
| `supervisor-prompt` | `{text}` | 監督へ指示 |
| `worker-start` | `{slug,instruction?,model?}` | 担当の起動（新しい端末タブ。監督が動いていること） |
| `worker-resume` | `{slug}` | 担当の再開 |
| `worker-prompt` | `{slug,text}` | 担当へ指示 |
| `worker-report` | `{slug,status,message}` | 担当からの報告（`progress`・`done`・`question`・`blocked`・`failed`）。`question`・`failed`・`blocked` は監督へも中継 |
| `report` | `{message,level?}` | 監督から利用者への知らせ（`info`・`warn`・`question`）。アプリのログに出る |
| `log-list` | `{limit?}` | ログ（新しい順。既定 50・最大 300） |
| `refresh` | `{}` | 読み直し |

```sh
sodactl plugin call aidev works-list --tab <タブ>
sodactl plugin call aidev worker-start --tab <タブ> --params '{"slug":"20261015-my-work","instruction":"要件定義から始めて"}'
sodactl plugin call aidev report --tab <タブ> --params '{"message":"design の承認をください","level":"question"}'
```

起動・再開は時間がかかる（エージェントの起動を待つ）。`sodactl plugin call` の応答待ち（30 秒）を超えそうなときは、約 25 秒で
`{"status":"pending"}` を返して処理を続ける。結果は `agents-list`・`log-list` で確かめる（**自動では再試行しない**）。

## 台帳（セッション ID の記憶）

`<PJ>/.soda/aidev/`（初回に `.gitignore`（`*`）を作るので、リポジトリには入らない）。

| ファイル | 内容 |
|---|---|
| `agents.json` | 監督と担当のセッション ID・名前・pane・状態・最後の報告、ログ（300 件・1 件 8 KiB まで）。原子的に書く |
| `settings.json` | 監督・担当のモデル（空なら指定しない）、権限のモード（`default`・`acceptEdits`・`auto`・`plan`）、自動起動 |
| `prompts/` | 監督・担当に渡した役割の文面（長い文面は端末へ貼らず、ここを読ませる） |

セッション ID は**プラグインが先に決める**（UUID）。`--session-id <UUID>` で起動し、再開は `--resume <UUID>`。
エージェントの名前は `aidev-sup-<PJ の短いハッシュ>`（監督）・`aidev-w-<ハッシュ>-<slug>-<ハッシュ>`（担当）。

## 安全

- ファイルから読んだ文字・エージェントの報告は信用しない（画面は `textContent` で描き、静的な HTML は全部エスケープ。長さを切る）。
- `sodactl` は `execFile`（シェルを通さない）。引数は検証済みの値だけ。`SODA_PANE_ID`・`SODA_PANE_SOCKET` は外して呼ぶ。
- 読む・書くパスは PJ の `.aidev/` と `.soda/aidev/` の中だけ（シンボリックリンクで外へ出ない）。
- 外部への公開（push・PR・merge）は、利用者が求めた範囲でだけ担当に指示するよう、監督の役割に書いてある。
- 拡張は隔離されない（利用者の権限で動く）。`aidev status` を呼ぶため、PJ の `.claude/skills/aidev-docs/bin/aidev` を `sh` で実行する。信頼できる PJ だけで使う。

## 限界

- エージェントは **Claude Code だけ**（セッション ID を先に決められる種類）。Codex 等は対象外。
- **`sodactl` のログインが要る**。サーバと同じ OS 利用者で `sodactl login` していないと、起動・指示は失敗し、画面のログに理由が出る。
- `.aidev/` は書き換えない。aidev の状態は工程スキルと CLI だけが更新する。
- **自動の再試行はしない**（作成・起動の操作の重複を避ける）。同じ起動が走っている間の 2 回目は「実行中」で断る。
- `next`・`deps` は aidev CLI（`status --all --format tsv`）の結果。作業が多いと CLI が遅い（150 件で十数秒）ため、結果は背景で取って前回の値を使う。
  CLI が無い・時間切れのときは、自前の読み取りだけで表示する（`next` は空）。
- 画面からの操作の値は 8 KiB まで（画面の指示は約 6000 バイト）。長い指示は `sodactl plugin call` を使う。
- 作業は新しい 1000 件まで。`display.send` の頻度制限のため、大きな文書は数秒かけて届く。

## 開発

```sh
cd docs/ClaudeCode/skills/aidev/aidev-docs/soda-plugin
node --test          # 単体テスト（偽の sodactl・偽のホスト）。sodactl が PATH にあれば pack の確認も走る
```
