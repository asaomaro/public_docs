# テスト結果: diff-review-html

## 実行したもの

- `python3 -m unittest discover -s tests`（script のテスト） — **28 passed / 0 failed / 0 skipped**
- `node accept.mjs`（headless Chromium による画面の受け入れ確認・T20） — **20 passed / 0 failed**
  （ラウンド 1 は 19 passed / 1 failed。下記「失敗の証跡」）
- `aidev smoke` — **pass（exit 0、3 本）**
- `python3 diff_review.py html --repo . > a.html` を 2 回 → `cmp` でバイト一致
- `python3 diff_review.py list exported.json [--format tsv]`

環境: Linux / Python 3.11.15 / git 2.43.0 / Chromium 1194（Playwright 1.56.1）。

## 受け入れ基準ごとの判定

| AC | 判定 | どう確かめたか |
|---|---|---|
| AC1 | pass | `html` が unstaged / staged / range から生成でき、`file://` で開いた画面の**外部リクエストが 0 件**（Playwright の request イベントで計測） |
| AC2 | pass | 変更ファイル 2 件＝一覧 2 行、行種別に `ctx` / `add` / `del` が揃い、`file-toggle` で `data-collapsed=true` |
| AC3 | pass | 行 / ファイル / 全体の 3 階層で確定し、記録に `line` / `file` / `overall` が揃った |
| AC4 | pass | 返信が `in_reply_to` に起点コメントの id を持ち、`resolved` が切り替わる |
| AC5 | pass | `CHANGES_REQUESTED` ＋ サマリで提出 → `reviews` 1 件、未提出表示が 0 件に |
| AC6 | pass | 書き出した JSON が `schema` / `target`（`diff_digest` 含む）/ `reviews` / `threads` を持つ |
| AC7 | pass | 書き出し → 読み込み → 再書き出しが**文字列として完全一致**。Python の `dumps_canonical` で読み直しても同一バイト（JS と Python の正規形が一致） |
| AC8 | pass | AI が `template` から書いた JSON を `--import` した HTML が、指摘 1 件を最初から表示 |
| AC9 | pass | `html` / `template` をそれぞれ 2 回実行して `cmp` が一致。出力に時刻・乱数を持たない |
| AC10 | pass | 差分の `<script>alert(1)</script>` が**文字列として表示**され、dialog も pageerror も発生しない。埋め込み JSON では `<` に退避 |
| AC11 | pass | CLI: 不正な `state` / 壊れた参照を exit 3 と理由付きで拒否、`html --import` も生成せず停止。画面: 同じ記録を「読み込めませんでした」と拒否 |
| AC12 | pass | `list` が未解決だけを `path:line` ＋ 本文で出し、`--format tsv` は 1 行 1 件 |
| AC13 | pass | SKILL.md に `html` / `template`＋`check` / `list` の使用例が 13 箇所、`schema.md` への導線あり |
| AC14 | pass | `import` は `argparse` / `json` / `subprocess` / `sys` / `pathlib` のみ。テストも `unittest` のみ |
| AC15 | pass | `ドキュメント メモ.md`（空白＋日本語）と日本語本文が、表示・書き出し・読み込みで化けない |
| AC16 | pass | リロードで下書きが復元され、「下書きを破棄」で消える。保存キーは `diff-review-html/v1/<diff_digest>` |
| AC-I1 | pass | `aria-expanded` が開閉で `true`/`false`。`Esc` で閉じても本文が残り、次に開くと続きから書ける |
| AC-I2 | pass | 修飾キー＋`Enter` で pending 確定、「取り消し」で記録から消える |
| AC-I3 | pass | `j` → `c` → 入力 → `Ctrl+Enter` → `Esc`、提出（`r`）までマウス無しで到達 |
| AC-I4 | pass | 開いたら `TEXTAREA` にフォーカス、閉じたら開いたボタン（`comment-open`）へ復帰 |
| AC-I5 | pass | 入力欄で `jjjfffrrr???` と打っても行移動・折りたたみ・ヘルプが動かず、本文にそのまま入る |

## 失敗の証跡

**ラウンド 1（受け入れスクリプトの選択ミス。製品側の欠陥ではない）**

```
$ node accept.mjs
pass	AC-I2	確定した未提出コメントを取り消すと記録から消える
FAIL	AC3	記録された階層: overall,file,overall
pass	AC4	返信が in_reply_to を持ち、解決状態が切り替わる
RESULT: 19 passed / 1 failed
```

原因: AC-I2 の「取り消し」を `.comment .row-actions button ... .last()` で選んでいた。
DOM 上は `#overall` が `#files` より前に来るため、**最後の取り消しボタンは行コメント側**で、
意図した全体コメントではなく行コメントを消していた。その結果 AC3 の階層が
`line` ではなく `overall` 2 件になった。**製品は指示どおりのコメントを消しており、正しい**。
セレクタを `#overall .comment .row-actions button ... .first()` に直してラウンド 2 で 20/20。

`aidev event test sent_back` は記録していない——coding へ差し戻していない（実装に修正は無い）。

## 起動確認（smoke）

```
$ aidev smoke
（1/3）sh docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev help
（2/3）python3 docs/ClaudeCode/skills/other/diff-review-html/diff_review.py --help
（3/3）python3 docs/ClaudeCode/skills/other/diff-review-html/diff_review.py template --repo .
smoke: pass (exit 0, 3 本)
```

この work が足した入口（`diff_review.py` とそのサブコマンド）を `smokeCommands` に 2 行足した
（単数キー `smokeCommand:` は複数形へ移して残していない）。`--help` は入口が起動することを、
`template --repo .` は git を実際に読んで JSON を出せることを見ている。

## 未検証の穴（skip / 環境不足）

- **Firefox / Safari での `file://` の挙動は未検証**。この環境には Chromium しか無い。
  `research.md` F2（Firefox は `file://` の localStorage を塞ぐ）は検索結果の要約に基づく推定で、
  実機では確かめていない。**AC16 の「復元」は Chromium 系でのみ実測済み**、
  非対応ブラウザでの「明示して機能を落とす」経路はコード上の `try/catch` のみで、実機未確認。
- **Windows での実行は未検証**（`decisions.md` D13 の改行・符号化の固定はコード上の指定とバイト検査まで。
  実際の Windows / PowerShell 環境では走らせていない）。
- **10 万行級の巨大差分は未計測**（`research.md` F7 の実測は 20,000 行で load 517ms）。
- GitHub REST の語彙（`research.md` F12）と APG のパターン（F13）は**一次ページ未確認**
  （egress 制限のため検索要約が出典）。挙動ではなく命名の根拠なので、テストの対象外。

以上は deliver の「既知の制約」へ引き継ぐ。


---

# ラウンド 2（review からの差し戻し後・2026-09-16T02:16:52Z）

## 実行したもの

- `python3 -m unittest discover -s tests` — **28 passed / 0 failed / 0 skipped**
- `node accept.mjs`（画面の受け入れ確認） — **21 passed / 0 failed**
  （review ラウンド 1 の must を検知する `AC-I5b` を 1 件追加したので 20 → 21 件）
- `node enter.mjs`（must の再現確認専用） — 修正前後で挙動が反転することを確認
- `aidev smoke` — **pass（exit 0、3 本）**

## 直したもの（review ラウンド 1 の指摘）

| 指摘 | 修正 | 確認 |
|---|---|---|
| [must] Enter をページ全体で横取りしてボタンが押せない | `onKeyDown` の Enter を**差分の行にフォーカスがあるときだけ**扱うようにした | `resolved_after_enter: 1` / `composer_opened_instead: 0` / 提出パネルも Enter で開く |
| [nit] `git_text()` が未使用 | 削除 | 28 テスト緑 |
| [nit] 採番が読み込んだ id と衝突しうる | 実在する id の**最大の連番から**採番するようにした | 往復（AC7）が一致したまま |
| [nit] 壊れた `@@` 行で黙って行番号 0 | `die()` で原因を見せて exit 2 で止める | 28 テスト緑 |

## 失敗の証跡

**修正前（must の再現）**

```
$ node enter.mjs
threads: 1
focused: 解決にする
resolved_after_enter: 0
composer_opened_instead: 1
submit_panel_hidden_after_enter: true
```

**過剰修正で自分が壊した分（同じラウンド内で検知・修正）**

`c` キーまでボタン上で無効化したところ、コメント確定後にフォーカスがボタンへ戻った状態から
`c` で次のコメントを開けなくなり、受け入れ確認が止まった:

```
$ node accept.mjs
locator.inputValue: Timeout 30000ms exceeded.
Call log:
  - waiting for locator('.composer textarea').first()
    at accept.mjs:52
```

`c` はボタン・リンクの標準操作ではない（奪っているものが無い）ので、ガードは **Enter だけ**に絞った。

**修正後**

```
$ node enter.mjs
resolved_after_enter: 1
composer_opened_instead: 0
submit_panel_hidden_after_enter: false

$ node accept.mjs
RESULT: 21 passed / 0 failed

$ python3 -m unittest discover -s tests
Ran 28 tests in 2.743s
OK
```

## 起動確認（smoke）

```
$ aidev smoke
smoke: pass (exit 0, 3 本)
```

## 未検証の穴（skip / 環境不足）

ラウンド 1 と同じ（Firefox / Safari・Windows・10 万行級・一次資料の再確認）。
ラウンド 2 で新たに増えた穴は無い。


---

# ラウンド 3（review ラウンド 2 の should 修正後・2026-09-16T02:18:39Z）

## 実行したもの

- `python3 -m unittest discover -s tests` — **28 passed / 0 failed / 0 skipped**
- `node accept.mjs` — **22 passed / 0 failed**（空差分の案内を見る `AC2b` を追加して 21 → 22 件）
- `aidev smoke` — **pass（exit 0、3 本）**

## 直したもの（review ラウンド 2 の指摘）

| 指摘 | 修正 | 確認 |
|---|---|---|
| [should] 差分 0 件のとき画面が無言 | `#files` に「差分がありません…」、`#filelist` に「変更ファイルなし」を出すようにした | `AC2b` が pass（空差分の `--staged` 生成物で実測） |

## 失敗の証跡

このラウンドでは失敗が発生していない（修正 → 再実行で 22/22・28/28 とも一度で緑）。
差し戻しの根拠となったラウンド 2 の実測は review.md（`#files` / `#filelist` が空文字）に記録済み。

## 起動確認（smoke）

```
$ aidev smoke
smoke: pass (exit 0, 3 本)
```

## 未検証の穴（skip / 環境不足）

ラウンド 1 と同じ（Firefox / Safari・Windows・10 万行級・一次資料の再確認）。新たな穴は無い。
