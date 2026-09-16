# 判断の記録: 20260915-pr-review-html

> 1 決定 = 1 エントリ・追記式（`protocol.md`「8.1」）。既存エントリは書き直さない。

## D1: 実装プロファイルは full（三層判定）

- **背景**: `aidev-00-start` 手順 0 の三層判定。新規 skill 一式（SKILL.md ＋ 生成 script ＋
  JSON スキーマ ＋ HTML テンプレート）を作る work。
- **決定**: `full`（`aidev new pr-review-html --mode interactive`）。
- **理由・代替案**: light の 4 条件のうち「触るファイル 3 個以下」と「公開 I/F・スキーマに触らない」を
  同時に外れる——JSON スキーマは**外部 I/F**（AI と人間の往復の契約）そのもの。
  ユーザーにも確認し `full` を選択（light は後から昇格できるが逆はできない、という非対称も根拠）。
- **影響**: requirements → design → tasks → coding → test → review → deliver の全工程を通る。

## D2: 差分の入力ソースは「ローカル git 差分」に限定し、GitHub PR 取得は別 work に送る

- **背景**: 当初の要望は「ローカル差分・staged・GitHub の差分・PR」の 4 経路。
- **決定**: 今回は unstaged / staged / コミット範囲のみ。GitHub PR / API からの取得と、
  レビュー結果の GitHub への書き戻しは**スコープ外**。
- **理由・代替案**: 一番頻度の高い用途（AI がコミット前に書いた差分を人間が読む）を最短で満たすため。
  GitHub 経路は認証・レート・失敗時の扱いという別種の設計を連れてくる。ユーザーが選択。
- **影響**: requirements のスコープ外節に明記。将来の書き戻しに備え、JSON スキーマの命名だけは
  GitHub REST に寄せる（D6）。

## D3: 生成 script は POSIX sh、ただし **JSON の読解責務を script に持たせない**

- **背景**: 要件は「決定論的に生成する script」＋「依存ゼロ（Node/Python/npm/jq 不要）」。
  一方 research R1 が、**sh で任意形式の JSON を読むことだけが難所**だと示した
  （生成・埋め込み・エスケープ・決定論・性能は実測で成立: research F6〜F9）。
  repo の先例 `other/md-to-doc` は同種の仕事を Python3 stdlib で行っている（research F17）。
- **決定**: **案B を採る** — script（POSIX sh）は
  ①差分 → HTML 生成、②JSON の**埋め込み**、③JSON の**構造検査（壊れていないことの確認）**、
  ④未解決コメントの**一覧出力**までを担い、**JSON の意味的な解釈は HTML 側の JS と、
  読み手である AI エージェント自身に任せる**。③④は「この skill が書いた正規形の JSON」だけを
  対象とし、awk で行指向に読む（`aidev` CLI が YAML サブセットを awk で読むのと同じ割り切り。research F20）。
- **理由・代替案**:
  - 案A（sh で汎用 JSON パーサを書く）: 依存ゼロは満たすが、AI が手書きした任意整形の JSON で
    壊れる。壊れ方が静かなのが最悪（誤った指摘一覧を出す）。
  - 案C（Python3 stdlib に切り替える）: repo の先例には合うが、要件の「依存ゼロ・POSIX sh」を覆す。
    HTML 生成に関しては sh で足りることを実測済みなので、覆す理由が弱い。
  - 案B は、**正規形を要求する側に立つ**ことで sh の弱点を回避する。AI が JSON を書く場合も
    SKILL.md が正規形を指示するので、実運用上の制約にならない。
- **影響**: SKILL.md に「JSON は正規形で書く」ことと、その形を明記する必要がある。
  script の検査は「正規形かどうか」を含めて落とす（壊れた JSON を黙って通さない＝AC11）。

## D4: JSON は「決定論的な正規形」で書き出す（キー順固定・1 プロパティ 1 行）

- **背景**: AC9（同じ入力で 2 回生成してバイト一致）と、D3 の awk による行指向読み取り。
- **決定**: 書き出す JSON は**キー順を固定**し、**配列要素・プロパティを 1 行 1 項目**で並べる整形とする。
  インデントはスペース 2。文字列は最小限のエスケープ（`"` `\` 制御文字 ＋ 埋め込み用に `<`→`<`）。
- **理由・代替案**: 圧縮 1 行 JSON は人間にも AI にも読みにくく、diff にも乗らない。
  自由整形は awk 読みを壊す。正規形なら**人間が読める・diff に乗る・sh が読める**の 3 つを同時に満たす。
- **影響**: HTML 側の書き出し実装も同じ正規形を守る必要がある（`JSON.stringify` の既定に任せない）。

## D5: 記録の自動復元（AC16）は「使えるブラウザでだけ働く」ことを明示する

- **背景**: research F1/F2 — Chromium は `file://` で localStorage が使えるが、
  **`file://` 全体で 1 オリジンを共有**する。Firefox は `file://` の localStorage を塞ぐ（SecurityError）。
- **決定**: ①localStorage のキーに**差分識別子を必ず含める**、②アクセスは try/catch で囲み、
  使えない環境では**画面に「このブラウザでは下書きが保存されません」と明示**して機能を落とす、
  ③requirements の AC16 はこの条件付きで満たすものとする。
- **理由・代替案**: 「全ブラウザで復元」は実現不能（ブラウザ側の制限）。黙って動かないのが最悪なので、
  能力の有無を利用者に見せる。
- **影響**: AC16 の検証は「対応ブラウザでの復元」＋「非対応時の明示」の 2 点で行う（test 工程）。

## D6: JSON スキーマの語彙は GitHub REST に寄せる

- **背景**: research F12（`path` / `line` / `side` / `start_line` / `start_side` / `in_reply_to_id` /
  レビューの `state`。`position` は非推奨方向）。
- **決定**: コメントは `path` / `line` / `side` / `start_line` / `start_side` / `body` / `in_reply_to`、
  レビューは `state: APPROVED | CHANGES_REQUESTED | COMMENTED` を使う。
- **理由・代替案**: 独自命名にすると、対象外にした「GitHub への書き戻し」を後から足すときに
  変換層が要る。既存の語彙に寄せる方が、AI にとっても意味が自明（学習済みの語彙）。
- **影響**: ファイル単位・全体コメントは `line: null` などで表現する（GitHub の慣習に合わせる）。

## D7: 差分の同一性は git だけで刻み、不一致は「警告して続行」

- **背景**: requirements の未確定事項「別の差分に誤って指摘を適用する事故をどう防ぐか」。
  research F10 で `git rev-parse HEAD` ＋ `git hash-object` ＋ `--raw` の blob hash が外部依存なしで取れる。
- **決定**: JSON に base commit・差分本文のハッシュ・ファイルごとの blob hash を刻む。
  読み込み時に不一致なら**警告を出して続行**（拒否しない）。
- **理由・代替案**: 拒否すると、レビュー中に 1 文字直しただけで過去の指摘が読めなくなり往復が止まる。
  警告なら「ずれている」ことを人間が判断できる。
- **影響**: HTML に「この記録は別の差分に対するものです」の帯を出す設計が要る。

## D8: 表示は unified のみ。巨大差分はファイル単位の遅延展開

- **背景**: research F7（20,000 行・2.1MB で load 517ms）。
- **決定**: side-by-side は作らない。既定でファイルは折りたたみ、大きいファイルだけ展開時に描画する。
- **理由・代替案**: side-by-side は列の同期・折り返し・行番号対応で実装量が跳ね、
  今回の主用途（AI の差分を読む）では unified で足りる。必要になれば後から足せる。
- **影響**: AC2 の「折りたたみ」は必須機能として扱う。

## D9: 実装言語は Python3 標準ライブラリに変更する（**D3 の決定を上書き**）

- **背景**: D3 では「POSIX sh ＋ JSON 読解を script に持たせない（案B）」を推奨したが、
  design 工程の方針ゲートでユーザーが**案C（Python3 stdlib）**を選択した。
- **決定**: 生成 script は **Python3（標準ライブラリのみ）**で書く。D3 の案B は採らない。
  D3 が回避しようとしていた「sh で JSON を読む難所」は、`json` モジュールで消える。
- **理由・代替案**: repo の先例 `other/md-to-doc/generate.py`（単一 HTML 生成・1844 行・stdlib のみ）と
  同じ型になり、**JSON の検証（AC11）と未解決一覧（AC12）を script 自身が正しく行える**。
  案A（sh で汎用パーサ）は壊れ方が静かで退けた。案B は依存ゼロを守れるが、
  JSON の意味解釈を script から追い出す必要があり、AC11 / AC12 の実装が痩せる。
  代償は **Python3 への依存**——ただし aidev CLI（sh）と違い、この skill は
  「レビュー画面を作る」用途で、実行環境は開発者の手元に限られるため許容できると判断した。
- **影響**:
  - **requirements の AC14 と非機能要件「依存ゼロ」を書き換える**（POSIX sh → Python3 stdlib）。
    この上書きは requirements 承認後の変更なので、この D9 が唯一の証跡になる。
  - D4（JSON の正規形）は**維持する**。理由が変わる——sh の行指向読み取りのためではなく、
    **AC9（バイト一致）と、人間・AI が diff で読めること**のため。`json.dumps` の
    `sort_keys` / `indent` / `ensure_ascii=False` で決定論的に出せる。
  - test 工程の検証コマンドは `python3` 前提になる。

## D10: skill は `docs/ClaudeCode/skills/other/diff-review-html/` に置く

- **背景**: 配置先とトリガ語の競合（research F19: `github/create-pr` が「PRを作って」で必ず発火、
  セッションには組み込み `code-review` も居る）。
- **決定**: 名前は **`diff-review-html`**、置き場は `other/`（`md-to-doc` と同じ）。
  description のトリガ語は「差分をHTMLで見たい」「レビュー画面を作って」「差分レビューのHTML」など、
  **「PRを作って」「レビューして」の汎用句を避ける**。
- **理由・代替案**: `pr-review-html` は GitHub PR を取らない（D2）のに PR を名乗るため、
  将来 `create-pr` と混同されうる。`review/` 新カテゴリはレビュー系 skill が 1 本では早い。
- **影響**: work の slug（`20260915-pr-review-html`）と skill 名が一致しないが、
  work は「作業名」、skill は「製品名」なので揃える必要はない。

## D11: script は 1 本 ＋ サブコマンド構成

- **背景**: 3 機能（HTML 出力 / JSON 作成 / JSON 読み取り）をどう割るか。
- **決定**: `diff_review.py <subcommand>` の 1 本にまとめる（`html` / `check` / `list`）。
- **理由・代替案**: エスケープ・正規形・識別子の算出という共通処理を 1 箇所に置ける。
  3 本に割ると共通処理が重複し、片方だけ直す事故（CI コメントが警告している「片方だけ直して食い違う」）が起きる。
- **影響**: SKILL.md は 3 機能をサブコマンドとして説明する。

## D12: sh/pwsh の二重実装を避けることを、D9（Python3）の追加根拠として記録する

- **背景**: ユーザーの指摘——「sh だけでなく pwsh も必要。難しければ Python か Node を検討する」。
  この repo の先例がまさにそれで、`aidev` CLI は **POSIX sh 版と PowerShell 版の 2 実装**を持ち、
  `.github/workflows/aidev-cli.yml` は「**両方の処理系が揃う環境で走らせ、skip が出たら落とす**」
  という運用をしている（skip＝未検証の穴の裏に ps1 の実バグ 2 件が隠れていた、と同ファイルが記録）。
- **決定**: D9（Python3 標準ライブラリ 1 実装）を維持する。**sh 版・pwsh 版は作らない。**
- **理由・代替案**:
  - sh を採ると **pwsh 版が必然的に要る**（Windows で動かせないため）。そこから
    「2 実装の挙動・出力・終了コードを一致させる」義務と、それを検証する CI が発生する。
    レビュー画面 1 本にその常設コストは見合わない。
  - Node も候補だが、Python3 と違って **Windows の既定では入っていない**ことが多く、
    HTML 生成に有利な点も無い（テンプレートは外部ファイルに置くため）。
  - Python3 は macOS / Linux に既存、Windows も公式インストーラ・ストア版が一般的で、
    **1 実装で 3 OS を賄える**。
- **影響**: design に「Windows での実行」節を足し、**実行系の名前（`python3` / `py -3`）・
  改行コード・標準出力のエンコーディング**を仕様として固定する（下記 D13 の実体）。

## D13: Windows でも決定論を守るための出力規約

- **背景**: D12 で Python 1 実装に決めた以上、**Windows で出力が変わらない**ことを仕様で担保する必要がある。
  `aidev-docs/bin/README.md` は PowerShell 版について「出力は OS を問わず UTF-8 固定
  （コンソール CP のまま出すとパイプ先で化ける）」と記録しており、同じ罠が Python にもある。
- **決定**:
  - ファイル出力・標準出力とも **UTF-8 固定・改行 LF 固定**（`open(..., encoding="utf-8", newline="\n")`、
    標準出力は `reconfigure(encoding="utf-8", newline="\n")`）。Windows の text mode 既定（CRLF）に任せない。
  - 実行系は **`python3` / `py -3` / `python` のいずれか**を SKILL.md に明記する（script 側は何もしない）。
  - `git` 呼び出しはバイト列で受け取り、**自前で UTF-8 デコード**する（コンソール CP に依存させない）。
- **理由・代替案**: 改行を OS 任せにすると、**同じ入力なのに Windows だけ出力が変わり AC9（バイト一致）が
  壊れる**。`core.autocrlf` が有効な Windows では差分本文にも CR が混ざりうるので、
  差分行の末尾 CR は**そのまま保持して表示**する（勝手に削ると差分の事実が変わる）。
- **影響**: AC9 / AC15 の検証は「同一 OS で 2 回」だけでなく、**改行と符号化の固定**を
  コード上で確かめる（test 工程でバイト列を直接検査する）。

## D14: T20（画面の受け入れ確認）は coding ではなく test 工程で消化する

- **背景**: `aidev-30-tasks` の手順 6 は、`AC` を coding 以外で消化する場合は**その旨を明記したタスクを立て、
  `decisions.md` に 1 行残す**ことを求めている（coding の完了の目安と形の上で食い違うため）。
- **決定**: T20（headless Chromium による画面の受け入れ確認）は **coding 工程では未チェックのまま残し、
  test 工程で消化する**。
- **理由・代替案**: 画面の受け入れ基準（AC3 / AC4 / AC5 / AC7 / AC16 / AC-I1〜I5）は
  実際にブラウザで操作しないと確かめられない。coding 内で確かめると、実装しながら検証する形になり
  「書いた本人が書いたとおりに動かす」検証になりやすい。工程を分けて、test 工程の検証として独立させる。
- **影響**: coding の承認時に T20 が未チェックで残る。`tasks_done` はその分 1 少なくなる（記録どおりでよい）。

## D15: coding の途中から `mode: autonomous` に切り替える

- **背景**: ユーザーが「ここから先は autonomous で」と指示した。requirements / research / design / tasks は
  interactive の承認ゲートを通っており、coding の実装も終わっている段階での切り替え。
- **決定**: `state.yml` の `mode` を `autonomous` にし、以降（coding の承認 → test → review → deliver）は
  人間ゲートを置かず自動承認で進める。`protocol-autonomous.md` の安全弁（テストを硬いゲートに・
  差し戻し上限・独立点検の記録・逸脱記録）をここから適用する。
- **理由・代替案**: `mode` を変える CLI コマンドは存在しない（`aidev new --mode` のみ）ため、
  `state.yml` を直接編集した。**state の編集を CLI に集約する原則からの逸脱**なので、この記録が証跡になる。
  代替は「新しい work を autonomous で起こし直す」だが、requirements 以降の記録と metrics が分断され、
  この work の手戻り・所要時間が追えなくなるので採らない。
- **影響**:
  - 以降の approve は自動。`walkthrough.md` の要否は `aidev-60-review` の 3 条件だけで決める
    （「PR を出すから書く」とはしない）。
  - **上流 4 文書の独立点検（`aidev doccheck`）が autonomous では必須**なので、
    interactive 下で省略した分を test 工程に入る前に実施して記録する。
  - 終端は PR。ただしこのセッションの運用規約（PR は明示依頼があるときだけ作る）に従い、
    **作業ブランチへの push までを自動で行い、PR 作成の可否だけ最後に確認する**。
