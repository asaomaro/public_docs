# タスク: GitHub の差分・PR 差分を取得元として追加

## 実装方針

**通信の土台 → 詰め替え → 入口 2 つ → CLI 配線 → 文書 → テスト**の順に積む。

1. 通信の土台（T1）——GitHub API を叩く・ページネーションを追う・エラーを理由付きで返す部分。
   ここが決まらないと PR も compare も動かせない。
2. 詰め替え（T2）——GitHub の `files[]` を既存の `entries`/`files` の形に変換する部分。
   PR と compare で共通。
3. 入口 2 つ（T3 `github-pr` / T4 `github-compare`）——T1・T2 を使って `target`/`files` を作る。
4. CLI 配線（T5）——`--from`・新フラグ・`collect_diff` の分岐・既存サブコマンドへの接続。
   ここまでで初めてコマンドラインから使える。
5. 文書（T6）とテスト（T7 単体・T8 回帰・T9 実地確認）。

**各タスクの終わりに既存の性質を確認する**（標準ライブラリのみ・決定論はローカル取得元で維持・
UTF-8/LF・既存 126 件のテストが通ったままであること）。

## 作業順序と依存関係

下の `依存:` に従う。それでは表せない順序の理由だけをここに書く。

- **T5（CLI 配線）を T3・T4 の後に**。入口の関数が無い状態で引数だけ増やすと、
  「フラグは受け付けるが何もしない」という壊れた中間状態を経由する。
- **T7（単体テスト）を T1〜T5 全部の後に**。モックの対象（`github_request`/`collect_diff_github_*`）
  が固まる前にテストを書くと、実装の都合でテストを何度も書き直すことになる。
- **T8（回帰）は T5 の直後、T6・T7 と並行できる**。既存経路を壊していないかは
  実装が終わった時点ですぐ確認でき、文書・新規テストの完成を待つ必要が無い。

## リスク / 留意点

- **R1（decisions D2）**: `.diff` 静的ファイル方式は採らない。実装中に「楽だから」で
  `github.com/…/pull/N.diff` 方式に流れないこと（T3 の検査点）。
- **R2（decisions D5）**: 全文取得をしない。`expand`/`rich` を「無いなら明示的に無い形
  （`None` または `{"truncated": true, …}`）」にする——**空の全文（`""`）で埋めない**
  （空文字だと「0 行のファイル」に見えてしまう。T2 の検査点）。
- **R3（decisions D3）**: GitHub 由来の失敗は必ず `EXIT_NETWORK`。既存の `EXIT_GIT`/
  `EXIT_USAGE`/`EXIT_INVALID` の意味を広げないこと（T1・T7 の検査点）。
- **R4（要件 非機能要件）**: トークンをエラーメッセージ・ログに含めない
  （`github_request` のエラー整形はヘッダの中身を出力しない。T1 の検査点）。
- **R5（design F9）**: `collect_diff` の非 GitHub 分岐（既存コード）を**1 行も変更しない**。
  差分に既存経路の変更が出たら設計から外れている（T5・T8 の検査点）。

## テスト方針

- **単体（T7・stdlib `unittest`）**: `urllib.request.urlopen` をモックし、実際の外部
  ネットワークは叩かない。PR 1 件・compare 1 件・ページネーション 2 ページ・404・
  レート制限（403 + `X-RateLimit-Remaining: 0`）・トークン有無での `Authorization` ヘッダ・
  `--github-api-base` 差し替え・`GITHUB_PR_RE` の URL/スラグ両形式・
  `github-compare` の 2 ドット拒否・`_approx_line_count`・`github_digest` の決定論
  （同じ入力→同じ出力）を検証する。
- **回帰（T8）**: 既存 126 件を無変更のまま実行し、全通過を確認する。
- **実地確認（T9・test 工程・手動）**: 実在の公開 PR に対して `--from github-pr` で HTML を
  作り、同じ PR をローカルで `git fetch` して `--from range` で作った HTML と
  ファイル一覧・追加/削除行数が一致することを目視確認する。自動テストには含めない
  （外部ネットワーク・実在リポジトリの状態に依存するため。design のテスト方針を参照）。

## タスク

- [x] T1: 通信の土台（`GithubOpts` / `github_request` / `github_list_all` /
      `_next_link_path` / `_github_error_message` / `_rate_limit_hint` /
      `resolve_github_token` / `EXIT_NETWORK`）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/diff_review.py` / 根拠: design F1・F2共通, F3, F6
      依存: なし
      AC: AC5, AC6, AC7, AC9, AC12
- [x] T2: 詰め替え（`github_files_to_entries` / `build_file_from_github` /
      `_approx_line_count` / `_tokenize_hunks_inplace` / `github_digest`）
      対象: 同上 / 根拠: design F1・F2共通, F8, diff_digest の作り方
      依存: T1
      AC: AC1, AC4, AC8, AC10
- [x] T3: `collect_diff_github_pr`（`GITHUB_PR_RE` による URL/スラグ解析を含む）
      対象: 同上 / 根拠: design F1
      依存: T1, T2
      AC: AC1, AC2, AC3
- [x] T4: `collect_diff_github_compare`（3 ドット検査を含む）
      対象: 同上 / 根拠: design F2, decisions D7
      依存: T1, T2
      AC: AC4
- [x] T5: CLI 配線（`SOURCES`/`SOURCES_NOT_YET` 更新・`add_source_options` への新フラグ
      追加・`collect_diff` の分岐・`cmd_html`/`cmd_bundle`/`cmd_template`/`diff_files_for` からの
      `github_opts` 受け渡し・`--from` ごとの必須フラグ検査）
      対象: 同上 / 根拠: design F9, `--from` の引数解析
      依存: T3, T4
      AC: AC3, AC5, AC8, AC11
- [x] T6: 文書更新（`SKILL.md` の `--from` 一覧・制限節・終了コード表・description の
      「取得は行わない」の一文、`schema.md` は変更なしを確認）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/SKILL.md` / 根拠: decisions D3, D5, D6, D7
      依存: T5
      AC: AC4, AC9, AC10
- [x] T7: 単体テスト（ネットワークをモック。T1〜T5 の全関数）
      対象: `docs/ClaudeCode/skills/other/diff-review-html/tests/test_diff_review.py` / 根拠: design テスト方針
      依存: T5
      AC: AC1, AC2, AC3, AC4, AC5, AC6, AC7, AC9, AC10, AC12
- [x] T8: 既存回帰（126 件が無変更のまま全通過）
      対象: 同上 / 根拠: design 対象範囲, 要件 F9
      依存: T5
      AC: AC11
- [x] T9: 実地確認（実在の公開 PR。test 工程で実施し `test-result.md` に記録）
      対象: なし（手動確認） / 根拠: design テスト方針
      依存: T7, T8
      AC: AC1, AC4, AC8
