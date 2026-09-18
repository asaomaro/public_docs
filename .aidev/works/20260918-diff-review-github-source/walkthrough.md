# レビューガイド: GitHub の差分・PR 差分を取得元として追加

> `diff_review.py` のみの変更（＋ `SKILL.md`・テスト）。`templates/`（画面側）・`schema.md`
> には触れていない。**処理フローが複雑**（ネットワーク・ページネーション・エラー系統が
> 新規）ため、`aidev-60-review`「レビュー補助」の要否 3 条件のうち 1 つに該当すると判断した。

## 変更概要 / 目的

「github差分、pr差分へ対応して」という指摘に応え、`--from github-pr` / `--from github-compare`
を実装した。**ローカルに clone していないリポジトリでも**、PR 番号や 2 リビジョンの比較を
指定するだけで、既存の `html`/`bundle`/`template`/`comment`/`check`/`list` がそのまま使える。

- 先行 work（`20260915-pr-review-html` D2）が明記した「GitHub PR には触らない」という非目標を、
  **取得（読み取り）の側だけ**覆す。投稿（コメント・レビューの書き戻し）は引き続き対象外。

## 読む順番（推奨）

1. **`GithubOpts`・`github_request`・`github_list_all`**（`diff_review.py` の新設ブロック冒頭）
   ——ここがすべての土台。エラー処理・ページネーション・認証ヘッダの組み立てが1箇所に閉じている。
2. **`github_files_to_entries` / `build_file_from_github`**——GitHub の `files[]` を、
   既存のローカル取得元の `entries`/`files[]` と**同じ形**に詰め替える部分。ここが一致していれば、
   下流（`render_html`・`comment`・`check --anchors` 等）は無改造で動く。
3. **`collect_diff_github_pr` / `collect_diff_github_compare`**——1・2 を組み合わせて
   `target`/`files` を作る入口。
4. **`collect_diff` の分岐**（既存関数の冒頭 3 行）——ここだけが既存コードへの接点。
   それ以外のローカル取得元の処理は変更していない。
5. **`normalize_source`**（CLI 引数の検査）——`--from github-pr`/`github-compare` に
   必要な組の指定漏れを、ネットワークを叩く前に検査する。

## 重要ポイント（非自明な判断）

1. **`.diff` 静的ファイル方式ではなく REST API 方式を選んだ**（decisions.md D2）。
   この開発環境では `.diff` のリダイレクト先ドメインが egress で塞がれることを実測で確認し、
   `api.github.com` 1 ドメインで完結する方式に倒した。
2. **GitHub の `patch`（ハンク単位のテキスト）は既存の `parse_hunks` にそのまま渡せる**
   （research.md F1）。新しいパーサを書いていない——GitHub 側がすでに構造化して返す情報
   （`status`/`additions`/`deletions`/`previous_filename`）をそのまま使い、
   本文だけ既存のパーサに通す設計。
3. **全文を取得しない**（decisions.md D5）。前後の段階展開・rich diff は GitHub 取得元では
   動かない。`expand = {"truncated": true, "count": <近似値>}` を設定することで、
   **既存の**「展開データを持っていません」表示（`app.js`、変更なし）にそのまま乗せている
   ——新しい文言・UI を足さずに「展開できない」という事実を伝える。
4. **`diff_digest` は `git hash-object` ではなく `hashlib.sha256`**（decisions.md D4）。
   GitHub 取得元は `--repo`（ローカルリポジトリ）を要求しない設計のため、`git` に一切頼れない。
5. **エラーは新しい終了コード `EXIT_NETWORK`（4）**（decisions.md D3）。
   既存の `EXIT_GIT`（2・「git の失敗」）とは意味を分けている。

## 動作確認

- `python3 -m unittest tests.test_diff_review` — **140 件**（既存 126 件は無変更のまま全通過。
  1 件を新しい振る舞いに合わせて置き換え、14 件を新設）。ネットワークはすべてモック。
- **実地確認**（本物の `api.github.com`）: 実在の公開 PR（この skill 自身が入っている
  リポジトリの PR #25）を `--from github-pr` で取得し、同じ PR をローカル `--from range` で
  取得した結果とファイル一覧（path・status・追加/削除行数）が**完全一致**することを確認。
  `--from github-compare` でも同様に一致を確認。存在しない PR 番号は `EXIT_NETWORK` で
  理由付きで失敗することを確認。
- GitHub 取得元のバンドルに対する `comment`/`check --anchors`/`list` が、ローカル取得元と
  同じコマンドでそのまま動くことを確認（詳細は `test-result.md`）。
- headless Chromium で生成 HTML を開き、JS エラー 0 件・「展開データを持っていません」表示が
  想定通り出ることを確認。

## 見なくてよいところ

- `SOURCES_NOT_YET` の削除（空の辞書のまま参照が 0 件になっていた死んだコードを、
  レビュー中に気づいて削除しただけ。振る舞いへの影響なし）。
- `SKILL.md` の文言の細部（`--from` 一覧・制限節・終了コード表・description の 1 文の言い換え）。
