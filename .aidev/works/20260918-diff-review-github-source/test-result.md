# テスト結果: GitHub の差分・PR 差分を取得元として追加

実施: coding 完了後の test 工程。環境は Python3 標準ライブラリ＋ headless Chromium（Playwright 同梱）。
GitHub 側の実地確認は、実在の公開リポジトリ `asaomaro/public_docs`（この skill 自身が入っている
リポジトリ）の実在 PR #25 に対して、**この環境から実際に `api.github.com` を叩いて**行った
（モックではなく本物のネットワーク呼び出し）。

## 1. 生成側（`python3 -m unittest`）

```
Ran 140 tests in 25.8s — OK
```

前 work からの 126 件に **14 件の純増**（1 件を置き換え・15 件を新設）。

| 変更した検査 | 何を固定したか |
|---|---|
| `SourceSelectionTest.test_github_pr_requires_github_pr_flag` | 旧「まだ未対応」テストの置き換え。`--github-pr` 必須の使い方エラー |
| `…test_github_compare_requires_github_repo_and_rev` | `github-compare` に `--github-repo`/`--rev` が無いと落ちる |
| `…test_github_compare_rejects_two_dot_rev` | 2 ドットは `EXIT_USAGE`（decisions D7） |
| `…test_github_sources_do_not_require_a_local_repo` | `--repo` を省いても使い方エラーにならない（AC3） |
| `GithubSourceTest`（11 件・`urllib.request.urlopen` をモック） | PR 取得＋ページネーション追従／compare 取得＋head 側 sha 解決／トークン有無での `Authorization` ヘッダ／`--github-api-base` 差し替え／404 が `EXIT_NETWORK` で落ちる／レート制限ヘッダの案内文／URL・スラグ両形式の解析／`github_digest` の順序非依存・決定論／トークンの優先順位／`expand_max_lines=0` で `expand` を作らない／ギャップがあれば既存の「展開できません」形を流用 |

## 2. 実地確認（本物のネットワーク。test 工程・手動）

| 確認 | 結果 |
|---|---|
| `--from github-pr --github-pr asaomaro/public_docs#25` で HTML 生成 | 成功（865,376 B） |
| 同じ PR をローカルで `--from range --rev <base>..<head>` で生成した HTML と、ファイル一覧（path・status・additions・deletions）を突き合わせ | **13/13 件、完全一致** |
| `--from github-compare --github-repo asaomaro/public_docs --rev <base>...<head>` | 成功。ファイル一覧は上記と**完全一致**（13/13） |
| 存在しない PR 番号（`#999999`） | `HTTP 404`・GitHub の `message`（`Not Found`）を含めて `EXIT_NETWORK`（4）で失敗。空の差分を返さない |
| GitHub 取得元の `bundle` → `comment` → `check --anchors` → `list` の一連 | すべて成功。既存のローカル取得元と**同じコマンドで**指摘の追加・位置検証・一覧化ができた（AC8） |

## 3. 画面（headless Chromium・`file://`）

`--from github-pr` で生成した HTML（13 ファイル）を開いて確認。

| 項目 | 実測 |
|---|---|
| JS エラー（`pageerror`/`console.error`） | **0 件** |
| ファイル数 | 13（GitHub API 側の件数と一致） |
| 「…行あるため、前後の展開データを持っていません」の表示件数 | 13（全ファイルに表示。GitHub 取得元はハンクを持つ全ファイルで `expand.truncated: true` になるため。design F8） |

既存の画面側テスト（前 work までの回帰一式）は、`templates/` を無改造にしている
（要件のスコープ・design 対象範囲）ため、この work では再実行のみで新規追加は無い。

## 4. 既存回帰（AC11）

- `python3 -m unittest tests.test_diff_review` の**既存 126 件**は無変更のまま、全通過を維持
  （上記 140 件の内数）。
- ローカル取得元（`unstaged`/`staged`/`range`/`commit`）を実際に生成し、この work の前後で
  出力ファイル一覧・HTML のバイト数に差が無いことを確認（`collect_diff` の非 GitHub 分岐は
  design 通り無改造）。

## 5. 未確認（正直に）

- **GitHub Enterprise Server（`--github-api-base`）は実機確認していない**。単体テストで
  リクエスト URL の差し替えは確認したが、実在の Enterprise 環境には接続していない。
- **非公開リポジトリでの認証付き取得**は、単体テストで `Authorization` ヘッダが正しく付くことは
  確認したが、実在の非公開リポジトリに対しては確認していない（この work の開発環境から
  操作できるトークンが無いため）。
- **100 件を超えるファイル数のページネーション**は、単体テストでは 2 ページ（各 1 件）の
  追従を確認したが、実在の GitHub 上で 100 件超の PR には当たっていない
  （`github_list_all` の実装はページ数に依らない一般化された形のため、外挿で足りると判断）。
- **レート制限超過の実挙動**は、単体テストでヘッダの解釈のみ確認した（実際にレート制限に
  達するまでリクエストを送っていない）。
