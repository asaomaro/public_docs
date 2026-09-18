# 設計: GitHub の差分・PR 差分を取得元として追加

> 対象は `diff_review.py` のみ。`templates/`（画面側）・`schema.md`（レビュー記録の形）には
> 触れない。GitHub 取得元は既存のローカル取得元と**同じ `target` / `files` の形**を作ることで、
> 画面・記録まわりのコードを無改造のまま動かす（research.md F1・F2）。

## 全体構成

```
collect_diff(repo, source, rev, context, expand_max_lines, rich, github_opts)
  ├─ source が unstaged/staged/range/commit → 既存の経路（無改造）
  └─ source が github-pr/github-compare     → collect_diff_github(...)（新設）
       ├─ github_pr_meta / github_compare_meta  … base/head の sha・PR番号等を得る
       ├─ github_list_files(...)                … files[] をページネーションしながら全件取得
       ├─ files[] の各要素 → entries 相当（path/old_path/status/old_blob/new_blob）
       │                     と stats 相当（additions/deletions）に詰め替え
       └─ 各要素の "patch" 文字列 → parse_hunks() にそのまま渡す（research.md F1）
```

`collect_diff` の返り値の形（`target` の 4 キー・`files` の各要素の 9 キー）は変えない。
呼び出し元（`cmd_html` / `cmd_bundle` / `cmd_template` / `diff_files_for` / `anchor_of` 系）は
**1 行も変更しない**（要件 F9）。

## F1・F2: GitHub API 呼び出しの共通化

PR 用（`pulls/{n}` ＋ `pulls/{n}/files`）と compare 用（`compare/{base}...{head}`）は、
「最初に何を叩いて base/head の sha を得るか」だけが違い、ファイル一覧の形
（`filename`/`status`/`additions`/`deletions`/`previous_filename`/`sha`/`patch`）は同じ
（research.md F1・F2）。共通のページネーション関数を 1 つ持つ。

```python
def github_request(opts, path, accept="application/vnd.github+json"):
    """GitHub API を 1 回呼ぶ。JSON を返す。認証・User-Agent・エラーの共通処理はここに閉じる。"""
    url = opts.api_base.rstrip("/") + path
    req = urllib.request.Request(url, headers={
        "Accept": accept,
        "User-Agent": "diff-review-html",
        **({"Authorization": "Bearer " + opts.token} if opts.token else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        message = _github_error_message(body)
        # EXIT_NETWORK の定義は「F6: エラー処理と終了コード」節を参照
        die("GitHub API に失敗しました（HTTP %d %s): %s\n  %s"
            % (exc.code, path, message, _rate_limit_hint(exc.headers)), EXIT_NETWORK)
    except (urllib.error.URLError, TimeoutError) as exc:
        die("GitHub に接続できません: %s" % exc, EXIT_NETWORK)
    except json.JSONDecodeError as exc:
        die("GitHub の応答を JSON として読めません: %s" % exc, EXIT_NETWORK)


def github_list_all(opts, path):
    """ページネーションを追従して全件を返す（research.md F5: Link ヘッダの rel="next"）。"""
    items, next_path = [], path
    while next_path:
        page, headers = github_request(opts, next_path)
        items.extend(page)
        next_path = _next_link_path(headers.get("Link"))
    return items
```

- `_github_error_message(body)`: JSON をパースできれば `message` フィールド（research.md F4）、
  できなければ本文の先頭 200 文字をそのまま使う（GitHub 側の応答形が将来変わっても落ちない）。
- `_rate_limit_hint(headers)`: `X-RateLimit-Remaining: 0` のときだけ
  `X-RateLimit-Reset`（UNIX 時刻）を人が読める形に添える。それ以外は空文字。
- `_next_link_path(link_header)`: `rel="next"` の URL を正規表現で拾い、`opts.api_base` からの
  相対パスに変換する（`github_request` が毎回フルURLを組み立て直せるように）。無ければ `None`。

## F1: `--from github-pr`

```python
def collect_diff_github_pr(opts, owner, repo, number, context, expand_max_lines, rich):
    pr, _ = github_request(opts, "/repos/%s/%s/pulls/%s" % (owner, repo, number))
    files_raw = github_list_all(opts, "/repos/%s/%s/pulls/%s/files?per_page=100" % (owner, repo, number))
    target = {
        "source": "github-pr",
        "range": "%s/%s#%s" % (owner, repo, number),
        "base_commit": pr["head"]["sha"],
        "diff_digest": github_digest(files_raw),   # 定義は「diff_digest の作り方」節を参照
        "files": [...],   # 既存 target["files"] と同じ 4 キー（path/status/old_blob/new_blob）
    }
    return target, github_files_to_entries(files_raw, expand_max_lines is not None)
```

`--github-pr` の指定は URL でもスラグでも受ける（要件 AC2）。

```python
GITHUB_PR_RE = re.compile(
    r"^(?:https?://github\.com/)?(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?[/#](?P<number>\d+)/?$")
```

`https://github.com/o/r/pull/123` と `o/r#123` のどちらも `[/#]` の 1 文字違いだけで拾える
（`pull/123` の `/`、`o/r#123` の `#`）。マッチしなければ
「`<owner>/<repo>#<番号>` または PR の URL の形にしてください」という理由で `EXIT_USAGE` で落ちる。

## F2: `--from github-compare`

```python
def collect_diff_github_compare(opts, owner, repo, rev, context, expand_max_lines, rich):
    basehead = rev  # "base...head" をそのまま URL パスへ（3 ドット必須。research.md F2）
    cmp, _ = github_request(opts, "/repos/%s/%s/compare/%s" % (owner, repo, urllib.parse.quote(basehead, safe=".")))
    files_raw = cmp.get("files") or []
    # compare は 1 回の応答に files[] を含む（250 件まで。超えるときは pulls/…/files 形式で
    # 別途ページングが要る場合があるため、Link ヘッダも同様に追従する: github_list_all を使う）
    ...
```

`--rev` に `..`（2 ドット）が渡されたら、GitHub の compare API は別解釈になる／404 になりうる
（research.md: 実測は両方 404 だったが対象コミットの状態に依存し断定できない）ため、
**3 ドットでない `--rev` は `github-compare` では使い方の誤りとして `EXIT_USAGE` で落とす**
（黙って 2 ドットのまま渡さない）。

## F1・F2 共通: ファイル一覧の詰め替え

```python
def github_files_to_entries(files_raw):
    entries, stats = [], {}
    for f in files_raw:
        status = _github_status_to_letter(f["status"])   # "added"->"A" 等
        entries.append({
            "path": f["filename"],
            "old_path": f.get("previous_filename"),
            "status": status,
            "old_blob": None,     # GitHub のファイル一覧 API は旧blobのshaを返さない（research.md F1）
            "new_blob": f.get("sha"),
        })
        stats[f["filename"]] = (f.get("additions", 0), f.get("deletions", 0))
    return entries, stats
```

`old_blob: None` は既存コードで**識別以外に使われていない**ことを確認済み
（`target["files"]` に格納されるだけで、比較・検証ロジックは `path`/`status` を見る）。

続くハンク構築は既存の `parse_hunks(lines)` をそのまま使う。**`split_body` は使わない**
（`diff --git` ヘッダで割る前提のため。GitHub 側は最初からファイルごとに分かれている）。

```python
def build_file_from_github(f, entry, expand_max_lines):
    binary = "patch" not in f
    hunks, _ = ([], False) if binary else parse_hunks(f["patch"].split("\n"))
    add, dele = f.get("additions", 0), f.get("deletions", 0)
    language = None if binary else highlight.language_for(entry["path"])
    # F8: 全文を取得しないため、ハンク以外の行は既存の「展開できない」表示を流用する。
    # count は最終ハンクの新側の最終行（無ければ旧側）を使う近似値（design決定 D-expand-approx）。
    expand = None
    if not binary and hunks:
        approx_count = _approx_line_count(hunks)
        if approx_count:
            expand = {"truncated": True, "count": approx_count}
    # 構文ハイライトはハンクの行だけを対象に行う（全文が無いため）。
    # highlight.tokenize_lines は行のリストを取る API なので、ハンクごとの行配列に対して
    # 個別に呼び、attach_tokens は使わない（attach_tokens は全文トークン配列からの逆引き前提のため）。
    if not binary and language:
        _tokenize_hunks_inplace(hunks, language)
    return {
        "path": entry["path"], "old_path": entry["old_path"], "status": entry["status"],
        "additions": add, "deletions": dele, "binary": binary, "language": language,
        "hunks": [] if binary else hunks, "expand": expand, "rich": None,   # rich はスコープ外
    }
```

- `_approx_line_count(hunks)`: 最後のハンクの `header` から `new_start` ＋ 行数を計算する
  （`parse_hunk_header` を流用）。ファイル削除（新側が存在しない）なら旧側で計算する。
  ハンクが無ければ `None`（`expand` を作らない＝ギャップ表示も出ない。差分そのものが無い
  ＝バイナリと同じ「本文なし」表示になるだけで実害はない）。
- `_tokenize_hunks_inplace(hunks, language)`: 各ハンクの `lines` を「テキストだけ」の配列に
  一時的に落として `highlight.tokenize_lines("\n".join(texts), language)` を呼び、結果を
  行に戻す。**ハンク単位（連続していない複数ハンクをまたいでは繋げない）** ——地の文の
  複数行コメント等の検出精度は落ちるが、既存の「正規表現ベースの近似」という位置づけの範囲内
  （`SKILL.md` 既記載の限界の延長）。

## F3: 認証トークン

```python
def resolve_github_token(cli_token):
    return cli_token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None
```

優先順位は要件 F3 のとおり（CLI 引数 > `GITHUB_TOKEN` > `GH_TOKEN` > 無し）。
トークンをエラーメッセージ・`die()` の出力に含めない（`github_request` のエラー整形は
HTTP ステータスと GitHub 側の `message` だけを使い、リクエストヘッダの中身を出力しない）。

## F4: API ベース URL

`--github-api-base`（既定 `https://api.github.com`）。`GithubOpts`（後述）にそのまま格納し、
`github_request` の URL 組み立てだけで使う。

```python
class GithubOpts:
    def __init__(self, api_base, token):
        self.api_base = api_base
        self.token = token
```

## F5: ページネーション

「実装アンカー」節の `github_list_all` を PR の `files` にも compare の `files` にも使う。
compare は 1 ページ目の応答に `files` を含むが、GitHub の compare API も大きい差分では
`Link` ヘッダでページングされる場合があるため、**compare も `github_list_all` 経由で統一**し、
「1 回目の応答は JSON 全体（`files` 以外のフィールドも要る）」「2 回目以降は `files` 相当の
配列」という非対称を関数の外（呼び出し側）で吸収する。

## F6: エラー処理と終了コード

新しい終了コード `EXIT_NETWORK = 4` を追加する（`EXIT_GIT` は名前が「git の失敗」に限定されており、
流用すると `SKILL.md` の説明と食い違うため。research.md 申し送り3）。

```python
EXIT_NETWORK = 4
```

`SKILL.md` の終了コード表に 1 行足す（0/1/2/3 は変更しない）。

## F7: `--repo` 不要

`add_source_options` に `--from github-pr` / `--from github-compare` が来たときは、
`--repo`（既定 `"."）が渡っていても**使わない**（`collect_diff` の分岐で GitHub 経路に入った
場合、`args.repo` を一切参照しない）。`--repo` を明示指定していても黙って無視するのではなく、
「github-pr / github-compare では使われません」という警告は出さない
（無害な指定を警告で騒がしくしない。既定値 `"."` のまま気にせず併用できるようにする——
既定値以外を明示指定したときだけ警告するかどうかは実装コストに見合わないため見送り）。

## F8: 展開できない旨の表示（画面は無改造）

上記「F1・F2 共通」節のとおり、`expand = {"truncated": True, "count": <近似値>}` を設定する
ことで、既存の `app.js`（`fillFileBody`）が**そのまま**「このファイルは N 行あるため、
前後の展開データを持っていません（生成時に `--expand-max-lines` を上げてください）」を表示する
（research.md 申し送り4 で確認済みのコード：`app.js:1188-1191`）。

**既知の割り切り**: この文言の「`--expand-max-lines` を上げてください」という案内は、
GitHub 取得元では効果が無い（全文取得をそもそもしないため）。`templates/` を今回のスコープ外に
置いた（要件のスコープ節）ため、文言の出し分けはしない。`SKILL.md` の「制限」節に
「GitHub 取得元では展開・構文ハイライトの一部・rich diff が効かない」と明記することで、
利用者が事前に知れるようにする（画面内の文言修正は将来 work で検討）。

## F9: 既存経路の無改造

`collect_diff` の冒頭で分岐する。

```python
def collect_diff(repo, source, rev, context, expand_max_lines=DEFAULT_EXPAND_MAX_LINES,
                  rich=True, github_opts=None):
    if source in ("github-pr", "github-compare"):
        return collect_diff_github(github_opts, source, rev, context, expand_max_lines, rich)
    # ↓ 以下、既存のローカル取得元の処理。1 行も変更しない。
    args = resolve_commit_args(repo, source, rev)
    ...
```

`github_opts` は `github-pr`/`github-compare` のときだけ非 `None`。ローカル取得元の呼び出し
（既存の全呼び出し箇所）は追加引数を渡さないため、既定値 `None` で従来どおり動く
（シグネチャ変更はあるが、呼び出し側の**新規追加は無く**、既存の呼び出しは無改造で動く）。

## `--from` の引数解析（`add_source_options`）

```python
SOURCES = ("unstaged", "staged", "range", "commit", "github-pr", "github-compare")
```

`SOURCES_NOT_YET` は空にする（`github-pr` はもう未実装スタブではない）。

新しいフラグ:

| フラグ | 対象 | 意味 |
|---|---|---|
| `--github-pr <spec>` | `--from github-pr` | `owner/repo#N` または PR の URL |
| `--github-repo <owner>/<repo>` | `--from github-compare` | 対象リポジトリ |
| `--rev <base>...<head>` | `--from github-compare` | 既存の `--rev` を流用（3 ドット必須） |
| `--github-token <TOKEN>` | 両方 | 省略時は `GITHUB_TOKEN` → `GH_TOKEN` |
| `--github-api-base <URL>` | 両方 | 既定 `https://api.github.com` |

`--from github-pr` なのに `--github-pr` が無い／`--from github-compare` なのに `--github-repo`
か `--rev` が無い、は `argparse` の相互チェックでは表現しづらいため、`collect_diff` 直前の
小さな検査関数で明示的に `EXIT_USAGE` にする（既存の `resolve_commit_args` 系と同じ場所）。

## `diff_digest` の作り方（GitHub 取得元）

ローカル取得元は `git hash-object` に差分本文のバイト列を通す（`git` 前提）。GitHub 取得元は
`--repo`（ローカルリポジトリ）を要求しない設計（要件 F7・AC3）のため、`git` に頼らず
`hashlib.sha256` を使う。

```python
def github_digest(files_raw):
    canon = dumps_canonical([
        {"path": f["filename"], "sha": f.get("sha"), "status": f["status"],
         "patch_len": len(f.get("patch") or "")}
        for f in sorted(files_raw, key=lambda f: f["filename"])
    ])
    return "gh1:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()
```

`"gh1:"` 接頭辞で、git の 40 桁 16 進数（`hash-object` の出力）と**見た目で区別できる**ようにする
（`identity_mismatch` は文字列比較だけなので機能上は接頭辞が無くても動くが、デバッグ時に
「これは git のハッシュではない」と分かる方が良い、という運用上の配慮）。`patch_len` を混ぜるのは、
同じ blob sha の組でも生成時にページネーションの取りこぼしがあれば digest が変わるようにするため
（取りこぼしを人間が気づける保険。厳密な内容一致検査ではない——sha が一致していれば内容も
一致するので、本来は sha の集合だけで十分だが、桁数の少ないコストで一段安全側に振った）。

## 対象範囲

**変更**: `diff_review.py` のみ（新関数の追加・`collect_diff`/`SOURCES`/`add_source_options`/
サブコマンドの引数定義への追記・終了コード追加）。
**変更なし**: `templates/`・`schema.md`・`highlight.py`（`tokenize_lines` は関数シグネチャ不変で
呼び出し方を変えるだけ）・`richdiff.py`。

## AC ごとの実現方法

- AC1: `collect_diff_github_pr` が PR のファイル一覧・patch から `target`/`files` を作り、
  既存の `render_html` にそのまま渡る。
- AC2: `GITHUB_PR_RE` が URL 形式・スラグ形式のどちらも受理する。
- AC3: `collect_diff` の GitHub 分岐が `repo` 引数を参照しない（F9 の分岐で確認）。
- AC4: `collect_diff_github_compare` が `compare/{base}...{head}` を叩き、PR と同じ詰め替え
  関数（`github_files_to_entries`/`build_file_from_github`）を通す。
- AC5: `github_list_all` が `Link` ヘッダの `rel="next"` を追従し続ける（F5）。
- AC6: `resolve_github_token` が `--github-token` を最優先で `github_request` の
  `Authorization` ヘッダに使う。
- AC7: トークン未指定時は `Authorization` ヘッダを付けずにリクエストする（`GithubOpts.token`
  が `None` なら `github_request` がヘッダを足さない）。
- AC8: `target`/`files` の形が既存取得元と同一であるため、`comment`/`check --anchors`/`list`
  は無改造で動く（`diff_files_for` は `--from github-pr`/`github-compare` のときも
  `collect_diff` を呼ぶだけで、GitHub 用の分岐に入る）。
- AC9: `github_request` の `except urllib.error.HTTPError` が HTTP ステータスと
  `_github_error_message` を含めて `die(..., EXIT_NETWORK)` する。
- AC10: `build_file_from_github` が `expand = {"truncated": True, "count": ...}` を設定し、
  既存の `fillFileBody` の表示にそのまま乗る（F8）。
- AC11: `collect_diff` の非 GitHub 分岐は既存コードをそのまま残す（新規関数を追加するだけ）。
  既存のテスト（`tests/test_diff_review.py`）を無変更のまま全通過させることで確認する。
- AC12: `GithubOpts.api_base` が `github_request` の URL 組み立てに使われる（`--github-api-base`
  を渡すテストで、実際に呼ばれる URL が差し替わることを確認する——ネットワークを使わない
  ユニットテストでは、`github_request` 相当の URL 組み立て部分だけを切り出して検証する）。

## 既存への影響と回帰

| 項目 | 影響 |
|---|---|
| `collect_diff` のシグネチャ | `github_opts=None` を追記（デフォルト引数なので既存呼び出しは無改造） |
| `SOURCES` | `github-pr` は既存の予約値のまま。`github-compare` を新規追加 |
| `SOURCES_NOT_YET` | 空にする（既存の「未実装」エラーパスは通らなくなる。要件どおりの意図した変更） |
| 終了コード | `EXIT_NETWORK = 4` を追加。既存の 0/1/2/3 の意味は変えない |
| `highlight.tokenize_lines` の呼び出し方 | 呼び出し側（`build_file_from_github`）を新設するだけ。
  関数自体は無改造 |
| `SKILL.md` | `--from` 一覧・制限節・終了コード表・description の「取得は行わない」の一文を更新 |

## テスト方針

- **ネットワークをモックする**単体テスト（`tests/test_diff_review.py` に追加）。
  `urllib.request.urlopen` を差し替え、固定の JSON 応答（PR 1 件・compare 1 件・
  ページネーション 2 ページ・404 エラー・レート制限ヘッダ付き 403）を返す偽関数に置き換えて、
  `collect_diff_github_pr`/`collect_diff_github_compare` の出力（`target`/`files` の形）を検証する。
  **実際の外部ネットワークは叩かない**（決定論・CI 非依存のテストにするため）。
- 詰め替え関数（`github_files_to_entries`/`build_file_from_github`/`_approx_line_count`/
  `_next_link_path`/`resolve_github_token`/`GITHUB_PR_RE`）は入出力が単純なので、
  ネットワーク抜きで個別にユニットテストする。
- 既存の 126 件（ローカル取得元）は無変更のまま全通過することを確認する（AC11）。
- 実機確認として、この work の開発中に確かめた実在 PR（`asaomaro/public_docs` #25 等）への
  実際のリクエストを 1 回だけ手動で行い、ローカル `--from range --rev <base>..<head>` で
  作った HTML とファイル一覧・追加/削除行数が一致することを目視確認する（自動テストではなく
  開発時の実地確認。CI では実行しない——外部ネットワーク・実在リポジトリの状態に依存するため）。

## 未解決

- `--github-token` を引数で渡す運用は、プロセス一覧（`ps`）に一時的に見える既知のリスクが
  残る（要件の非機能要件で言及済み）。`SKILL.md` に環境変数を推奨する注記を書くところまでを
  今回のスコープとし、引数自体を無くす（環境変数のみ対応にする）かは意見が割れうるため、
  ユーザーの選択肢を残す方針で両方サポートする。
