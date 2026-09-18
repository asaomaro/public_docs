# 判断の記録: 20260918-diff-review-github-source

> 1 決定 = 1 エントリ・追記式。この work は `mode: autonomous`（`protocol-autonomous.md`
> 「方針の事前承認」）。

## D1: 実行プロファイルは full、実行モードは autonomous

- **背景**: 「GitHub の PR には触らない（取得も投稿もしない）」という、先行 work
  （`20260915-pr-review-html` D2）が明記した非目標を**取得の側だけ**覆す変更。
  ネットワーク呼び出し・認証トークンの扱いという新しい種類のリスクを持ち込む。
- **決定**: `aidev new diff-review-github-source --mode autonomous --profile full
  --depends 20260915-pr-review-html`。
- **理由・代替案**: light は「振る舞いを変えない/小規模」が条件。今回は非目標だった機能を
  丸ごと足すので該当しない。既存の先行 work（`pr-review-html`・`diff-review-nav-polish`）も
  同様の判断基準で full を選んでおり、一貫性がある。
- **影響**: `requirements`/`design`/`tasks` それぞれで `doccheck`（同一セッション内点検）を実施。

## D2: 差分の取得は GitHub REST API（`api.github.com`）経由。`.diff` 静的ファイル方式は採らない

- **背景**: GitHub は PR/compare に `.diff`/`.patch` を付けた URL（`github.com/…/pull/N.diff`）
  でも生の unified diff を返す。試したところ `github.com` はこれを
  `patch-diff.githubusercontent.com` へ 302 リダイレクトするが、**この開発環境の egress
  プロキシはそのリダイレクト先への接続を拒否した**（`CONNECT tunnel failed, response 403`。
  research.md 冒頭の実測）。一方 `api.github.com` は疎通した。
- **決定**: `GET /repos/{owner}/{repo}/pulls/{number}` ＋
  `GET /repos/{owner}/{repo}/pulls/{number}/files`（PR）、
  `GET /repos/{owner}/{repo}/compare/{base}...{head}`（compare）という
  **REST API・JSON 応答**の方式を採用する。
- **理由・代替案**: `.diff` 方式は実装が単純（1 リクエストで済む）だが、
  (1) リダイレクト先ドメインが環境によって塞がれうる、(2) ファイルの状態
  （リネーム・追加/削除行数）を得るには結局テキストを自前でパースし直す必要があり、
  GitHub 側が既に構造化して返してくれる情報を再発明することになる。REST API 方式は
  1 ドメイン（`api.github.com`）だけで完結し、`filename`/`status`/`additions`/`deletions`/
  `previous_filename` を構造化データとしてそのまま使える（research.md F1・F2）。
- **影響**: 変更ファイル数に応じてリクエスト数が増える（ページネーション）。
  1 ドメインへの疎通確認だけで済むため、利用者側の障害切り分けも単純になる。

## D3: 新しい終了コード `EXIT_NETWORK = 4` を設ける（既存 `EXIT_GIT` は流用しない）

- **背景**: 既存の `EXIT_GIT`（2）は `SKILL.md` の終了コード表で「`git` の失敗
  （リポジトリ外・不正なリビジョン等）」と明記されている。GitHub API の失敗
  （HTTP エラー・接続不可・JSON 不正）をここに含めると、表の説明と実態が食い違う。
- **決定**: `EXIT_NETWORK = 4` を新設し、GitHub 取得元の失敗はすべてこのコードで落ちる。
  既存の `EXIT_OK`/`EXIT_USAGE`/`EXIT_GIT`/`EXIT_INVALID`（0/1/2/3）の意味は変えない。
- **理由・代替案**: `EXIT_GIT` を「差分取得全般の失敗」に意味を広げる案もあったが、
  `git` という名前のコードにネットワーク由来の失敗を含めるのは名が体を表さない。
  終了コードを見ただけで「ローカルの git の問題か、GitHub 側の問題か」を区別できる方が、
  呼び出し側（CI・スクリプト）にとって有用。
- **影響**: `SKILL.md` の終了コード表に 1 行追加。既存の呼び出し元・テストで
  `EXIT_GIT`/`EXIT_INVALID` を判定している箇所には影響しない。

## D4: `diff_digest`（GitHub 取得元）は `git hash-object` ではなく `hashlib.sha256` を使う

- **背景**: `--repo`（ローカルリポジトリ）を要求しない設計にする（要件 F7・AC3）ため、
  `git` コマンドに一切依存できない。既存の `digest()` は `git hash-object` を使っている。
- **決定**: 変更ファイルのパス・sha・status・patch 長を正規形 JSON にして
  `hashlib.sha256` を通し、`"gh1:"` を前置する。
- **理由・代替案**: 標準ライブラリのみで完結し（既存方針の継続）、git の有無に依存しない。
  `"gh1:"` の接頭辞は、git の 40 桁 16 進数と見た目で区別できるようにする運用上の配慮
  （`identity_mismatch` は文字列比較のみで動作するため機能上は必須ではない）。
- **影響**: `diff_review.py` に `import hashlib` を追加。

## D5: 全文（旧/新ファイル全体）は取得しない。展開・rich diff は今回スコープ外

- **背景**: PR/compare の files API はハンク単位の `patch` しか返さない（research.md F3）。
  全文が要る機能（前後の段階展開・rich diff・展開データ経由のハイライト）を提供するには、
  変更ファイルごとに追加の API 呼び出し（Contents API 等）が要り、
  ファイル数に比例してリクエスト数が増える別種のコスト。
- **決定**: 今回は全文取得をしない。`expand`（段階展開データ）・`rich`（rich diff）は
  GitHub 取得元では常に「展開データなし」の状態にする。`expand` は
  `{"truncated": true, "count": <近似値>}` を設定し、**既存の**「展開できません」表示
  （`app.js` の `fillFileBody`、`--expand-max-lines` 超過時と同じコードパス）を流用する。
- **理由・代替案**: `templates/`（画面側）を今回のスコープ外に置いた（要件のスコープ節）ため、
  GitHub 取得元専用の新しい文言・UI は作れない／作らない方針とした。既存の表示を流用すれば
  「全文が無くて展開できない」という**同じ意味の事実**を、追加コードなしで伝えられる。
  文言中の「`--expand-max-lines` を上げてください」という案内が GitHub 取得元には効かない
  という不正確さは残るが、`SKILL.md` の制限節に明記することで補う。
- **影響**: `build_file_from_github` は `expand`/`rich` を作らない（`rich` は常に `None`）。
  将来、全文取得（Contents API）を足す別 work では、この決定を上書きして
  `expand`/`rich` を実データで埋める形に拡張できる（既存の `target`/`files` の形を
  崩していないため、拡張時に呼び出し元の再改修は不要）。

## D6: 構文ハイライトはハンク単位で行う（全文単位ではない）

- **背景**: 既存の `attach_tokens` は全文トークン配列から行番号で逆引きする作りで、
  全文が無い GitHub 取得元では使えない。
- **決定**: 各ハンクの行テキストだけを取り出し、ハンク単位で `highlight.tokenize_lines` を
  個別に呼ぶ。ハンクをまたいだ地の文（複数行コメント・複数行文字列の途中がハンクの外にある場合）
  の検出精度は落ちる。
- **理由・代替案**: 全文取得（D5 で見送り）をしない以上、ハンク単位が唯一の現実的な選択肢。
  `SKILL.md` は元々「ハイライトは正規表現ベースの近似（構文解析器ではない）」と明記しており
  （既存の限界の記述）、この精度低下はその延長として扱える——新しい種類の限界ではなく、
  既存の限界が GitHub 取得元でやや強く出る、という説明で足りる。
- **影響**: `SKILL.md` の制限節に「GitHub 取得元ではハンク単位でハイライトするため、
  ハンクをまたぐ構文の検出精度がローカル取得元より低い」を追記する。

## D7: `github-compare` の `--rev` は 3 ドット（`base...head`）のみを受理する

- **背景**: GitHub の compare API は `base...head`（3 ドット）が正規の書式。
  実測では 2 ドット（`base..head`）は対象コミットによっては 404 になったが、
  常に 404 になるとは断定できなかった（research.md）。
- **決定**: `github-compare` では、`--rev` の値に `...` が含まれない場合は
  「`--rev` は `<base>...<head>`（3 ドット）の形にしてください」という理由で
  `EXIT_USAGE` で落とす（黙ってそのまま渡さない）。ローカル取得元の `--from range`
  （2 ドット）とは書式が異なることを `SKILL.md` に明記する。
- **理由・代替案**: 断定できない挙動差をそのまま利用者に押し付けると、
  「2 ドットで指定したら意味の分からない 404 が返った」という分かりにくい失敗になる。
  书式を早期に検査して理由を出す方が親切（既存方針「存在しない位置には書けない」と同じ
  「黙って別の結果を返さない」思想の延長）。
- **影響**: `diff_review.py` に軽量な検査を 1 箇所追加。

## D8: `--repo` は GitHub 取得元では参照するが使わない。警告も出さない

- **背景**: `--repo` は既定値 `"."` を持つため、GitHub 取得元のコマンドでも
  （明示していなくても）常に値が入っている。
- **決定**: GitHub 分岐では `args.repo` を一切参照しない。値が既定のままでも
  明示指定でも、警告は出さない。
- **理由・代替案**: 明示指定と既定値を区別して警告するには「利用者が明示したか」を
  argparse から拾う追加コードが要り、得られる価値（無害な指定に気づかせる）に対して
  実装コストが見合わない。既定値のまま気にせず併用できる方が利用者にとって単純。
- **影響**: なし（実装しない、という決定）。
