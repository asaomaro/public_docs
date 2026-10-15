# aidev プラグイン（Sodashitsu のアプリ）

PJ の `.aidev/` を読み、aidev（SDD ハーネス）による開発を、Sodashitsu の**アプリ画面**で見て・動かす plugin アプリ。

- **見る**: 作業（`.aidev/works/*`）の一覧・進捗・詳細（工程・tasks・文書・events）と、backlog。
- **動かす**: アプリにつき 1 つの**監督エージェント**（Claude Code または Codex）を起動し、アプリから指示を出す。各作業は別の**担当エージェント**が受け持ち、監督と連携する。種類は監督と担当で別々に選べる。
- **続ける**: 監督・担当の**セッション ID を記憶**し、止まっても同じ会話で**再開**できる。
- **呼べる**: アプリの操作は `sodactl plugin call aidev <操作>` でも呼べる（監督・担当のエージェントもこれを使う）。

`.aidev/` は**読むだけ**で書き換えない（aidev の state は aidev CLI と工程スキルだけが書く）。依存は Node 標準ライブラリだけ。

## 導入

前提: Sodashitsu（`soda serve`）が動いていること、設定「スクリプトが動く表示」が有効なこと（無効のときは読むだけの画面になる）、
`sodactl` が**サーバと同じ OS 利用者で `sodactl login` 済み**であること（プラグインは `sodactl` を呼んでエージェントを起こす）。
aidev の skill は、Claude Code は `.claude/skills/`、Codex は `.agents/skills/` に置く（aidev CLI も両方を探す）。

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
2. **監督**: アプリのタブがあり、監督が動いていなければ、**1 回だけ**自動で起動する（再開できる会話があれば再開。設定で切れる）。
   - 条件: アプリのタブ（サーバのセッションにある表示用の pane）が `ext.panes` に見えていること。**ブラウザで画面を開いている必要はない**。
     拡張が起動してから約 8 秒後に判定し、記録した pane がまだ残っているのにエージェントが検出されない間は、サーバが会話を復元する時間として
     約 35 秒まで待つ。拡張の 1 回の実行につき PJ ごとに 1 回だけ（失敗しても自動では繰り返さない）。`sodactl` にログインしていないと失敗し、ログに理由が出る。
   - ［監督を起動］［監督を再開］［新しい会話で始める］で手動でも起動できる。再開できる会話がある間、［起動］は断る（会話の ID を黙って上書きしない）。
     ［新しい会話で始める］を選ぶと、前の会話の ID は台帳の `previousSessions`（最新 5 件）に残す。
   - 承認待ち（信頼の確認など）のときは、画面の端末で答える。答えて待機になると、**役割（と担当なら線）が自動で届く**（［起動］を押し直しても届く）。
   - 監督の端末は画面に常設される（直接操作できる。同時に開ける端末は 4 つまで）。
3. **指示**: 「監督への指示」の欄（Ctrl+Enter で送る）と定型ボタン。監督の報告・担当の報告・アプリの出来事は「ログ」に出る（`question` は目立つ）。
4. **作業**: 一覧（進行中／すべて）から作業を選ぶと、工程の並び・state・tasks（読み取り専用）・文書（Markdown を簡易表示）・events が見られる。
   詳細の「担当」で、［担当を起動］（指示つき）・［再開］・［指示を送る］・［端末を表示］・［監督に任せる］が使える。
5. **担当**: 監督（または利用者）が起動すると、**アプリのタブの作業 pane を分けて**（最新の pane を右・下の交互に）担当が動き、
   担当 → 監督へ**グラフの線**（監督・承認の代理・完了のトリガ）が結ばれる。利用者が見ているタブは移らない。
   **アプリのタブの作業 pane が 6 個に達したときだけ**、新しい端末タブを作る（このとき画面がそのタブへ移る）。
   以後は、その担当用のタブの空き pane を使い、無ければそのタブを分けるので、タブは増えない（移るのは最初の 1 回だけ）。
   担当が一区切りつくと、トリガの線が監督へ知らせる。担当は `worker-report` で進捗・質問・失敗を報告する。
   担当の端末は、作業の詳細に常設される（直接操作できる）。
   - **種類（claude / codex）とモデル**は、監督・担当の起動ごとに画面から指定できる（空なら設定の既定）。
   - **関連するエージェント**: 担当が自分の pane から `sodactl` で起こした別のエージェントは、グラフの線（監督・承認の代理）で担当に連なるので、
     作業の詳細に並び、端末の表示・指示ができる（孫まで）。深い所など自動で出ないものは、担当が `work-agent-register` で登録する
     （登録できるのは、担当の pane から線で連なる pane だけ。利用者自身の pane は登録できない）。
   - **完了したら終了**: 担当が `done` を報告し、次の条件がそろったら、担当と**自動の線で連なる**関連するエージェントの pane を閉じる。
     (1) 担当が待機（20 秒の猶予のあと） (2) 完了の知らせ（担当 → 監督のトリガの線）が、`done` の後に監督へ**送られた**
     （閉じるとノードと線が消え、監督が作業中で待っていた知らせが黙って取り消されるため。`sodactl graph history` で確かめる）
     (3) 関連するエージェントが全部待機。条件が 30 分たってもそろわなければ、理由をログに残して閉じず、以後その担当は自動では閉じない。
     登録分の関連するエージェントは閉じない。完了の後に担当へ追加の指示を送ると、終了は取り消す。
     会話の ID は台帳にあるので、あとから再開できる（設定で切れる。Codex で会話 ID が未取得なら、再開できなくなるので終了を見送る）。
6. **再開**: エージェントが止まって（pane が無い・エージェントが居ない）も、台帳のセッション ID で `--resume` して同じ会話に戻れる。
   止まった担当の pane が残っていてエージェントが居なければ、その pane を再利用する（無ければ新しく置く）。
   再開の知らせには、いまのアプリのタブ ID を入れる（古い `--tab` を使い続けないため）。再開しただけでは動き出さず、
   「状況を確かめて報告し、指示を待つ」。役割を送る前に止まった会話は、再開できる会話が無いので、新しい会話で起動する。
   `--resume` が会話を見つけられず落ちた（`agent_start_failed`）ときは `failed` にして、［新しい会話で始める］を案内する。
   起動・再開が `timeout` で返っても、名前が付いて動いていれば失敗にせず、待機になってから役割（または再開の知らせ）を届ける。
   起動に失敗しても、新しい pane・会話 ID は台帳に残す（名前を握った孤児を作らない。前の会話の ID は `previousSessions`）。
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
| `supervisor-start` / `supervisor-resume` | `{kind?,model?,fresh?}` / `{}` | 監督の起動（動いていれば仕上げが残っていれば仕上げだけ）／同じ会話での再開。`fresh:true` は再開できる会話があっても新しい会話で始める |
| `supervisor-prompt` | `{text}` | 監督へ指示 |
| `worker-start` | `{slug,instruction?,kind?,model?,fresh?}` | 担当の起動（アプリのタブの pane。監督が動いていること）。`kind` は `claude`・`codex` |
| `worker-resume` | `{slug}` | 担当の再開 |
| `worker-prompt` | `{slug,text}` | 担当へ指示 |
| `worker-report` | `{slug,status,message}` | 担当からの報告（`progress`・`done`・`question`・`blocked`・`failed`）。`question`・`failed`・`blocked` は監督へも中継 |
| `report` | `{message,level?}` | 監督から利用者への知らせ（`info`・`warn`・`question`）。アプリのログに出る |
| `work-agents` | `{slug}` | 作業の担当と、関連するエージェント（担当が起こしたもの） |
| `work-agent-register` | `{slug,paneId}` | 担当が、自分で起こしたエージェントの pane を関連として登録する |
| `work-agent-prompt` | `{slug,paneId,text}` | 担当または関連するエージェントへ指示 |
| `work-agent-read` | `{slug,paneId,lines?}` | 担当または関連するエージェントの画面の末尾を読む |
| `log-list` | `{limit?}` | ログ（新しい順。既定 50・最大 300） |
| `refresh` | `{}` | 読み直し |

```sh
sodactl plugin call aidev works-list --tab <タブ>
sodactl plugin call aidev worker-start --tab <タブ> --params '{"slug":"20261015-my-work","instruction":"要件定義から始めて"}'
sodactl plugin call aidev report --tab <タブ> --params '{"message":"design の承認をください","level":"question"}'
```

結果は 200 KiB 程度で切る（`app.result` は 256 KiB を超えると、サーバが受理せず 30 秒の時間切れになるため）。
`work-doc`・`log-list`・`works-list`・`backlog-list` は、収まらないとき `truncated: true` で返す。それ以外は「結果が大きすぎます」で明示的に断る。

起動・再開は時間がかかる（エージェントの起動を待つ）。`sodactl plugin call` の応答待ち（30 秒）を超えそうなときは、約 25 秒で
`{"status":"pending"}` を返して処理を続ける。結果は `agents-list`・`log-list` で確かめる（**自動では再試行しない**）。

## 台帳（セッション ID の記憶）

`<PJ>/.soda/aidev/`（初回に `.gitignore`（`*`）を作るので、リポジトリには入らない）。

| ファイル | 内容 |
|---|---|
| `agents.json` | 監督と担当のセッション ID・名前・pane・状態・最後の報告・仕上げの印（`pending`: 役割／再開の知らせ／線のうち未送信のもの）・以前の会話（`previousSessions`）、ログ（300 件・1 件 8 KiB まで）。原子的に書く |
| `settings.json` | 監督・担当の種類（`claude`・`codex`）、モデル（空なら指定しない）、Claude の権限のモード（`default`・`acceptEdits`・`auto`・`plan`）、Codex の権限（`read-only`・`workspace-write`・`workspace-write-never`）、自動起動 |
| `prompts/` | 監督・担当に渡した役割の文面（長い文面は端末へ貼らず、ここを読ませる） |

セッション ID は、Claude Code では**プラグインが先に決める**（UUID）。`--session-id <UUID>` で起動し、再開は `--resume <UUID>`。
Codex は ID を先に決められないので、**初回はそのまま起動し、起動後に Sodashitsu が pane に記録した会話 ID（`agentSession`）を台帳へ取り込む**
（種類・名前が一致するものだけ。約 8 秒ごと）。取り込めるまでは「会話 ID 未取得」と表示し、再開はできない。再開は `codex resume <ID> -C <PJ>`。
再開は、設定が後で変わっても、台帳に記録した種類で行う。
エージェントの名前は `aidev-sup-<PJ の短いハッシュ>`（監督）・`aidev-w-<ハッシュ>-<slug>-<ハッシュ>`（担当）。

## 安全

- ファイルから読んだ文字・エージェントの報告は信用しない（画面は `textContent` で描き、静的な HTML は全部エスケープ。長さを切る）。
- `sodactl` は `execFile`（シェルを通さない）。引数は検証済みの値だけ。`SODA_PANE_ID`・`SODA_PANE_SOCKET` は外して呼ぶ。
- 読む・書くパスは PJ の `.aidev/` と `.soda/aidev/` の中だけ（`works`・`backlog`・`prompts/`・`agents.json`・`settings.json` は、シンボリックリンクなら使わない）。
- 担当・監督には「PJ フォルダの外のファイルは変更しない。外のコマンド（テスト等）も、指示がなければ流さない」と役割に書く。
- 担当の slug は読み取りと同じ書式（英数字と `. _ -`）。エージェント名は slug から安全な形に作る。
- aidev の版（`harnessRev`）には、このフォルダ（`aidev-docs/soda-plugin`）を入れない（`bin/aidev`・`bin/aidev.ps1` の `harness_rev` が除く）。
- 外部への公開（push・PR・merge）は、利用者が求めた範囲でだけ担当に指示するよう、監督の役割に書いてある。
- 拡張は隔離されない（利用者の権限で動く）。`aidev status` を呼ぶため、PJ の `.claude/skills/aidev-docs/bin/aidev` を `sh` で実行する。信頼できる PJ だけで使う。

## 限界

- エージェントは **Claude Code と Codex**。Codex は会話 ID の取り込み前（起動直後〜最初の入力まで）に止まると再開できず、起動し直しになる。権限は固定の組だけ（任意の引数は渡せない）。
- **`sodactl` のログインが要る**。サーバと同じ OS 利用者で `sodactl login` していないと、起動・指示は失敗し、画面のログに理由が出る。
- `.aidev/` は書き換えない。aidev の状態は工程スキルと CLI だけが更新する。
- **自動の再試行はしない**（作成・起動の操作の重複を避ける）。同じ起動が走っている間の 2 回目は「実行中」で断る。
- `next`・`deps` は aidev CLI（`status --all --format tsv`）の結果。作業が多いと CLI が遅い（150 件で十数秒）ため、結果は背景で取って前回の値を使う。
  CLI が無い・時間切れのときは、自前の読み取りだけで表示する（`next` は空）。
- `work-agent-read` は、画面の末尾（最大 40,000 文字）を ANSI を除いてそのまま返す。担当・監督（LLM）が呼べる口なので、
  画面に出た秘密（トークンなど）も戻りに載る。秘密を扱う PJ では、エージェントの出力に出さない運用にする。
- 画面からの操作の値は 8 KiB まで（画面の指示は約 6000 バイト）。長い指示は `sodactl plugin call` を使う。
- 作業は新しい 1000 件まで。subtask（`works/<親>/<NN>-<子>/`）は一覧に出ない（親の作業として扱う）。`display.send` の頻度制限のため、大きな文書は数秒かけて届く。

## 開発

```sh
cd docs/ClaudeCode/skills/aidev/aidev-docs/soda-plugin
node --test          # 単体テスト（偽の sodactl・偽のホスト）。sodactl が PATH にあれば pack の確認も走る
```
