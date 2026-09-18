# レビュー記録

## ラウンド 1

**指摘 1 件（nit・その場で直した）**、他は確認して**指摘なし**と判断した。

- **[nit] 使われなくなった `SOURCES_NOT_YET` が空の辞書のまま残っていた**——
  `github-pr` が未実装スタブだった頃の仕組み（design では「空にする」としていたが、
  空になった時点で参照が 0 件になり、変数自体が死んだコードになっていた）。
  `grep` で参照が無いことを確認し、変数ごと削除した。削除後も 140 件のテストが
  無変更のまま全通過することを確認した。
- **T1（通信の土台）**: `github_request` の例外処理順序（`HTTPError` を `URLError` より先に
  捕まえる。`HTTPError` は `URLError` のサブクラスのため、逆順だと `HTTPError` が
  `URLError` 側に飲まれる）をコードで確認。実測（`test_http_error_reports_status_and_message_and_dies_with_exit_network`・
  実地確認の 404 応答）でも意図通り `EXIT_NETWORK` になることを確認した。
  トークンをエラーメッセージ・`die()` の出力に含めていないこと（`_github_error_message`/
  `_rate_limit_hint` の引数にヘッダの値そのものを使わず、ステータス・メッセージ・
  リセット時刻だけを使っていること）をコードで確認した。
- **T2（詰め替え）**: `expand_max_lines <= 0` のとき `expand` を作らない分岐
  （`build_file_from_github`）を、ローカル取得元の `build_expand` の同じ規約
  （`max_lines <= 0` で `None`）と突き合わせて確認。`_tokenize_hunks_inplace` が
  `highlight.tokenize_lines` の返り値の行数（`\n` の個数 + 1）と入力行数が一致する
  実装（`highlight.py:152-162`）であることを読み、`zip(lines, tokens)` が
  ずれなく対応することを確認した。
- **T3・T4（PR・compare の入口）**: `GITHUB_PR_URL_RE`/`GITHUB_PR_SLUG_RE` が
  「マッチしなければ `EXIT_USAGE`」で必ず理由を出して落ちること（黙って別の解釈をしない）を
  コードで確認。`collect_diff_github_compare` の 3 ドット検査が、ネットワークを一切叩く前
  （`github_list_all` の呼び出しより前）に行われることを確認した
  ——誤った書式でリクエストを浪費しない。
- **T5（CLI 配線）**: `collect_diff` の非 GitHub 分岐（既存のローカル取得元のコード）を
  `git diff` で確認し、**1 行も変更されていない**こと（design F9・要件 F9）を確認した。
  5 つの呼び出し元（`cmd_html`/`cmd_bundle`/`cmd_template`/`cmd_check`/`diff_files_for`）
  すべてに `github_opts`/`github_pr`/`github_repo` の受け渡しが漏れなく入っていることを
  `grep` で確認した。
- **T6（文書）**: `SKILL.md` の終了コード表・`--from` 一覧・description・制限節の
  4 箇所すべてが更新されていることを確認。`schema.md` は対象外（要件のスコープ通り）で
  無変更であることを `git diff --stat` で確認した。
- **参照専用・書き込み導線との関係**: GitHub 取得元は `templates/` を一切変更していない
  （要件のスコープ）ため、`--readonly` の扱いは既存のまま影響を受けないことをコードで確認した。

## ラウンド 2

再確認のみ（新しい変更は無い）。`python3 -m unittest tests.test_diff_review`（140 件）・
実地確認 3 件（PR 取得・compare 取得・存在しない PR の失敗）・`aidev smoke` を再実行し、
全通過を確認した。**指摘なし**。
