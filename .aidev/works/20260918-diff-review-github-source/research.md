# 調査: GitHub PR / compare API を差分取得元にする実現性

> **実測の範囲**: この環境の egress プロキシは `github.com` からのリダイレクト先
> `patch-diff.githubusercontent.com`（`.diff` URL が実際に返す先）への接続を**拒否する**
> （`CONNECT tunnel failed, response 403`。実測）。一方 `api.github.com` は疎通する
> （実測: 200 応答・レート制限ヘッダあり）。そのため、この work は**REST API
> （`api.github.com`）を経由する方式**を前提に調査した。`github.com/…/pull/N.diff` の
> ような「リダイレクトされる静的ファイル」方式は、少なくともこの実行環境では使えない
> ——利用者の環境でも同様にプロキシで塞がれる可能性があるため、**採用しない**（decisions.md）。

## 調査の問い

- Q1: PR の差分・ファイル一覧を、認証なし/ありで `api.github.com` から取得できるか。
  取得できる情報の形は何か（既存の `parse_hunks` にそのまま食わせられるか）。
- Q2: PR に紐付かない任意の 2 リビジョン間の比較を同じ形で取得できるか。
- Q3: ページネーション・レート制限・認証エラーの実際の応答形はどうなっているか。
- Q4: 標準ライブラリ（`urllib.request`）だけで実装できるか（pip 依存を増やさない方針）。

## 判明した事実（すべて実測。対象: `asaomaro/public_docs` の実在 PR #25）

- **F1: PR のファイル一覧 API がハンク単位の patch を返す**。
  `GET /repos/{owner}/{repo}/pulls/{number}/files?per_page=100`（未認証で 200）は、
  各要素に `filename` / `status`（`added`/`removed`/`renamed`/`modified` 等） /
  `additions` / `deletions` / `previous_filename`（リネーム元） / `sha`（新blob） /
  **`patch`**（`@@ …` から始まるハンクのテキスト。ファイルヘッダ行 `diff --git`
  `--- `/`+++ ` は含まない）を持つ。`patch` は既存の `parse_hunks()` にそのまま渡せる
  （`parse_hunks` は `@@` 行でハンクを開始し、`--- `/`+++ ` 行はもともと読み飛ばす作りのため、
  無改造で食える）。バイナリ・大きすぎるファイルは `patch` キー自体が無い
  （既存コードの「バイナリなら hunks が無い」扱いとそのまま整合する）。
- **F2: compare API も同じ `files[]` の形**。`GET /repos/{owner}/{repo}/compare/{base}...{head}`
  （3 ドット。実測: 2 ドットは 404）は、`base_commit` / `merge_base_commit` / `files[]` を
  返し、`files[]` の各要素は F1 と同じ形（`filename`/`status`/`additions`/`deletions`/
  `previous_filename`/`sha`/`patch`）。**PR 用と compare 用で、ファイル一覧の変換ロジックを
  共通化できる**（design への申し送り）。
- **F3: 全文（旧/新のファイル全体）は API から直接は得られない**。`pulls/…/files` も
  `compare` も、返るのは**変更箇所のハンク（`patch`）だけ**。全文が要る機能
  （前後の段階展開・展開データを使う構文ハイライト・rich diff）を GitHub 取得元で
  提供するには、変更ファイルごとに別リクエスト（Contents API 等）が要る
  ——要件でスコープ外にした判断の裏付け。
- **F4: エラー応答は JSON で `message` を持つ**。存在しない PR（`GET .../pulls/999999`）は
  `404` ＋ `{"message": "Not Found", "documentation_url": "…"}`。認証エラー・レート制限も
  同じ形（`message` フィールド）と GitHub Docs に記載（一次ページは egress 拒否のため
  検索要約が出典。ステータスコードは 401/403 系との記載）。
- **F5: ページネーションは `Link` ヘッダ（RFC 5988）**。`per_page=1` で叩くと
  `Link: <…&page=2>; rel="next", <…&page=13>; rel="last"` が返る。**レスポンス本体には
  次ページの有無を示す情報が無い**——`Link` ヘッダをパースする必要がある
  （`rel="next"` が無くなるまで `page` を進める、という素朴な実装で足りる）。
- **F6: レート制限ヘッダは毎回付く**。`X-RateLimit-Limit` / `X-RateLimit-Remaining` /
  `X-RateLimit-Reset`。この実行環境では未認証でも 15000/時 と出た（環境のプロキシが
  何らかの資格情報を仲介している可能性があり、**一般的な値ではない**——GitHub Docs 上の
  既定値は未認証 60/時・個人アクセストークン 5000/時と案内されている。実機の値を過信せず、
  `403`/`429` ＋ `X-RateLimit-Remaining: 0` を検知したら理由をそのまま出す設計にする）。
- **F7: `urllib.request` だけで完結する**。認証ヘッダ（`Authorization: Bearer <token>`）・
  `Accept` ヘッダ・JSON 応答の読み取りまで標準ライブラリで足りる（実測。追加パッケージ不要）。
  `User-Agent` 未指定でも今回は 200 が返ったが、GitHub Docs は指定を推奨しているため、
  実装では明示的に付ける（コストがほぼ無いため）。

## 影響範囲

- `diff_review.py` の `collect_diff` とその呼び出し元（`cmd_html` / `cmd_bundle` /
  `cmd_template` / `diff_files_for`）。**`target` / `files` の形を変えずに**分岐を足せば、
  これらの呼び出し元・下流（`render_html`・`anchor_of` 系・`comment` 系）は無改造で動く
  （F1・F2 で確認した通り、GitHub 側のハンクは既存パーサにそのまま渡せるため）。
- `SOURCES` / `SOURCES_NOT_YET`（`diff_review.py:1461-1462`）・`add_source_options`
  （同 1465 行以降）・各サブコマンドの引数定義。
- `SKILL.md` の「GitHub の PR には触らない」節（`SKILL.md:375`）・`--from` の説明表
  （`SKILL.md:36-47`）・終了コード表（`SKILL.md:435-442`、新しいコードを 1 つ足す前提）。
- 新規: ネットワーク呼び出し・JSON 応答の解釈・ページネーション・認証ヘッダをまとめる
  小さなモジュール（`diff_review.py` 内の新関数群、または `githubapi.py` として分離するかは
  design で判断）。

## 実現性 / リスク

- **実現性は高い**: F1・F2 の通り、GitHub 側のデータ形が既存パーサ（`parse_hunks`）と
  ほぼそのまま噛み合う。新規実装の中心は「HTTP で取りに行って、既存の `files[]` 要素の形
  （`entries`/`stats` 相当）に詰め替える」部分に閉じられる。
- **リスク1: 全文非対応による見た目の差**。ローカル取得元では当たり前にできる
  「前後の展開」「rich diff」「展開データ経由の構文ハイライト」が GitHub 取得元では働かない。
  要件で明示スコープ外にしたが、**同じ画面の別のファイルでは動いてこのファイルでは動かない**、
  という体験の差は残る。既存の「展開できません」表示（`--expand-max-lines` 超過時）を
  流用することで、少なくとも**表示の形式自体は初見でも意味が分かる**ようにする。
- **リスク2: レート制限**。未認証はレート制限が低い（一般に 60/時）。変更ファイル数が多い
  PR で `files` API のページネーションを回すと、1 回の生成で複数リクエストを使う
  （13 ファイルの PR で `per_page=100` なら 1 リクエストだが、`per_page=1` なら 13 回、
  という違いが出る——**`per_page=100` 固定で叩けば、通常規模の PR は 1〜数リクエストで済む**）。
  トークン運用を案内すること（要件 F3）で軽減する。
- **リスク3: この実行環境固有のプロキシ挙動を一般化しない**。F6 のレート制限値・egress の
  可否は、この開発環境固有の可能性がある。実装は「その場で返ってきたヘッダ・ステータスを
  そのまま見せる」に徹し、**特定の数値をハードコードしない**。

## 実装アンカー

- 既存の差分パーサ: `parse_hunks`（`diff_review.py:310`）・`split_body`（`diff_review.py:290`）
  ——`split_body` は `diff --git` 行でファイル単位に割る前提なので、GitHub の `patch`
  （ファイルごとに既に分かれている）には使わない。`parse_hunks` だけを個別の `patch` に対して
  直接呼ぶ形にする。
- 取得元の分岐点: `collect_diff`（`diff_review.py:461`）、`diff_args`/`resolve_commit_args`
  （同 200/211）と同じ役割を GitHub 版として新設する。
- 入口の選択肢: `SOURCES`（`diff_review.py:1461`）・`SOURCES_NOT_YET`（1462）・
  `add_source_options`（1465 付近）。
- 終了コード: `EXIT_OK`/`EXIT_USAGE`/`EXIT_GIT`/`EXIT_INVALID`（`diff_review.py:48-51`）。
  ネットワーク由来の失敗をどれに割り当てるか（既存流用か新設か）は design で決める。
- `SKILL.md` の要修正箇所: L3（description の「GitHubのPRそのものへの投稿や取得は行わない」）・
  L36-47（`--from` 一覧）・L375（制限の節）・L435-442（終了コード表）。

## 実装時の注意

- `patch` を `parse_hunks` に渡すときの改行分割は、ローカル側と同じ `lines.split("\n")` の形に
  揃える（GitHub API の JSON 文字列内で `\n` はデコード後の実改行になるので、素朴な `split`
  で足りることを実測で確認済み）。
- リネームの新旧パス: ローカル取得元は `entry["old_path"]`（raw の R/C ステータス由来）。
  GitHub 側は `previous_filename`（`status == "renamed"` のときだけ入る）が対応する。
- `additions`/`deletions` は API が既に計算済みの値をそのまま使えばよい
  （ローカット取得元のように `--numstat` を別途叩く必要がない）。
- ページネーションの継続条件は `Link` ヘッダに `rel="next"` があるかどうかで判定する
  （正規表現 1 つで十分。`email.message` 等の重い解析器は不要）。
- `--rev` は `range`/`commit`（ローカル）と `github-compare`（リモート）の両方で使う共有フラグに
  なる。既存のヘルプ文言（`--rev <SPEC>` の説明）に `github-compare` 時の書式（3 ドット）を
  追記する必要がある。

## design への申し送り

1. **PR 用・compare 用の GitHub API 呼び出しを 1 つの内部関数に共通化**できる（F1・F2 で
   `files[]` の形が同一と確認済み）。差異は「どの URL を最初に叩いて base/head の SHA と
   ファイル一覧を得るか」だけ。
2. **`diff_digest` の作り方を GitHub 取得元専用に決める**必要がある。ローカット取得元は
   `git hash-object` に本文バイト列を通しているが、GitHub 取得元はそもそも `git` にも
   ローカルリポジトリにも依存しない設計にする（要件 F7・AC3）ので、`hashlib` 等の
   標準ライブラリで代替する。
3. **新しい終了コードを 1 つ設けるか、既存 `EXIT_GIT`（2）を「差分取得の失敗」全般に
   意味を広げるか**を決める（現在の `SKILL.md` の記述は「git の失敗」に限定しているため、
   広げるなら文言修正、新設するなら終了コード表に 1 行追加）。
4. **F8（展開できない旨の表示）をどこで作るか**——`build_expand` を GitHub 取得元では
   呼ばずに `expand: None` のままにする、という最小差分で足りるか、あるいは
   「全文が無いので展開できない」という理由を持たせるフィールドが要るかを、
   既存の画面側 JS（`app.js` の expand 描画）の分岐条件を読んで確認する。
