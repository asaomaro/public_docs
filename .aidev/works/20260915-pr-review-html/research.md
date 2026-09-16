# 調査: file:// 単一 HTML でのレビュー画面と、POSIX sh による決定論的生成の実現性

> **調査手段の制約（先に明示する）**: この環境の egress プロキシは `developer.mozilla.org` /
> `www.w3.org` / `docs.github.com` への直接フェッチを拒否する（実測: `EGRESS_BLOCKED`）。
> そのため **W3C / MDN / GitHub Docs は一次ページを直読できず、検索結果の要約を出典として扱った**
> （下記 F2 / F10 / F11 / F12）。一方、**ブラウザ挙動・git・sh・性能は実測で確かめた**
> （Chromium 1194 ＋ Playwright 1.56.1 をこの環境で実行）。実測とそれ以外を明確に分けてある。

## 調査の問い

- Q1: `file://` で開いた HTML から localStorage は使えるか。使えるとして、**別の HTML と記録が混ざる**か。
- Q2: `file://` で JSON を**書き出せる**か（ダウンロード）、**読み込める**か（ファイル選択・D&D・fetch）。
- Q3: 生成時に JSON を HTML へ埋め込む際の落とし穴は何か。
- Q4: POSIX sh だけで、HTML エスケープ・大量行の生成・**バイト一致の決定論性**を満たせるか。
- Q5: `git` から機械可読・決定論的に差分を取る方法は何か。差分の同一性は何で識別できるか。
- Q6: 数千〜数万行の差分を単一 HTML にしたとき、ブラウザで実用的に開けるか。
- Q7: GitHub の PR レビュー（pending → submit・解決）の**モデル**と、API のフィールド名は何か。
- Q8: 利用者が操作する部品（コメント欄の開閉・確定・フォーカス）の**確立したパターン**は何か。
- Q9: このリポジトリの skill の規約・先例（実行体の同梱・frontmatter・トリガ語の競合）は何か。
- Q10: sh で JSON を**読む**のは現実的か。先例はあるか。

## 判明した事実

### ブラウザ（`file://`）— すべて実測

- **F1: Chromium では `file://` でも localStorage が使え、リロード後も残る。ただし
  「`file://` 全体で 1 つの origin」として共有される。**
  実測: `probe.html` が書いた値を、同じディレクトリの**別ファイル** `other.html` がそのまま読めた
  （`OTHER_FILE_STORAGE: read:テスト値`）。`location.origin` は `"file://"`。
  → **別レビューの下書きが混ざる。キーに差分の識別子を含めることが必須**（設計制約）。
- **F2: Firefox は `file://` の localStorage を塞ぐ**（"SecurityError: The operation is insecure."）。
  ブラウザ間で挙動が定義されておらず、`file:` から読んだ文書のストレージ要件は未定義とされる。
  出典: 検索結果の要約（MDN "Window: localStorage property" / Same-origin policy、
  xjavascript.com の Firefox 解説）。**一次ページは egress 拒否で直読できていない。**
  → 要件 AC16（閉じても復元）は**ブラウザ依存**。少なくとも Firefox では成立しない。
- **F3: `file://` から同じディレクトリのファイルを `fetch` / `XHR` で読むことはできない。**
  実測: `TypeError: Failed to fetch` ／ `NetworkError`。コンソールに
  `URL scheme "file" is not supported` ／ `blocked by CORS policy ... origin 'null'`。
  → **JSON の読み込み経路は「ファイル選択 / ドラッグ＆ドロップ」と「生成時の埋め込み」だけ**。
  「HTML の隣に JSON を置けば読む」は**作れない**。
- **F4: Blob ＋ `<a download>` によるダウンロードは `file://` でも動く。** 実測: download イベントが発火し、
  保存内容は `{"日本語":"ok","s":"<script>"}` と**そのまま**（UTF-8 も記号も欠けない）。
  `URL.createObjectURL` は `blob:null/...` を返すが機能する。
- **F5: `file://` は `isSecureContext === true`** で、`navigator.clipboard.writeText` も**存在する**（実測）。
  ただしユーザー操作起点や権限の要否までは未検証。→ 主経路はダウンロード、クリップボードは補助。
- **F6: `<script type="application/json">` に JSON を素で埋めると、本文中の `</script>` で壊れる。**
  実測: 素のまま → `SyntaxError`（中身が途中で切れる）。`<` を `<` にエスケープ → `parsed:</script>` と復元。
  → 埋め込み時は **`<` を `<` に**（`&`・`>` は JSON 文字列として不要だが害もない）。
- **F7: 規模は問題にならない。** 実測（headless Chromium）: **20,000 行・2.1MB の HTML が load まで 517ms**、
  末尾行への `scrollIntoView` が 4ms。仮想スクロールなしで目標規模に届く。

### 生成側（POSIX sh / git）— すべて実測

- **F8: sh ＋ `sed` で HTML エスケープでき、生成は決定論的。** 実測: `&`→`&amp;`, `<`→`&lt;`,
  `>`→`&gt;`, `"`→`&quot;` の 4 置換で
  `+ &lt;script&gt;alert(&quot;0&quot;)&lt;/script&gt; 日本語 &amp; &quot;q&quot;` を得た。
  同じ入力で 2 回生成した HTML は `cmp` でバイト一致。**20,000 行の生成に 0.147s**（`while` ＋ `printf` ＋ `awk`）。
- **F9: `git` は機械可読・決定論的な差分を出せる。** 実測:
  - `git -c core.quotepath=false diff --no-color --no-ext-diff --raw -z <range>` →
    `:000000 100644 0000000 9814440 A\0path\0` の形で**旧/新の blob hash と変更種別**が取れる。
  - `git diff --numstat -z` → ファイルごとの追加/削除行数。
  - 同じコマンドを 2 回叩いた出力は**バイト一致**（`cmp` で確認）。
  - `-z` を使えば日本語・空白入りのパス名も安全（`core.quotepath=false` と併用）。
- **F10: 差分の同一性は git だけで刻める（外部依存ゼロ）。** 実測: `git rev-parse HEAD` →
  `3d6624ec…`、差分本文を `git hash-object --stdin` に流して `2d4df67c…`。
  `--raw` の blob hash と合わせれば**ファイル単位の同一性**も持てる。

### GitHub のレビューモデル（出典＝検索結果の要約。一次ページは egress 拒否）

- **F11: pending → submit のモデル**: 提出前の行コメントは **pending で本人にしか見えず**、提出まで編集できる。
  最初のコメントは "Start a review"、2 件目以降は "Add review comment"。提出時に
  **Approve / Request changes / Comment** のいずれかとサマリ本文を添える。
  提出前の取り消しは "Discard review"（pending コメントごと破棄）。
  出典: GitHub Docs "Reviewing proposed changes in a pull request" の検索要約。
  → 要件 AC5・AC-I2 はこのモデルにそのまま対応する（**独自モデルを発明する必要はない**）。
- **F12: レビューコメントの API フィールド名**: `path` / `line` / `side` / `start_line` / `start_side` /
  `commit_id` / `original_line` / `original_start_line` / `in_reply_to_id` / `diff_hunk`。
  複数行コメントは `start_line` ＋ `start_side` ＋ `line` ＋ `side`、単一行は `start_*` が null。
  **`position` は非推奨化の方向**で、`line` / `side` を使うことが推奨されている。
  出典: GitHub Docs "REST API endpoints for pull request review comments" の検索要約、
  および community discussion #202426（reviews エンドポイントの応答が position 系で返る既知の癖）。
  → JSON スキーマをこの命名に寄せると、**対象外にした「GitHub への書き戻し」への移行が安くなる**。

### UI の規範（出典＝検索結果の要約。W3C は egress 拒否で直読できず）

- **F13: 開閉は disclosure パターンで足りる。** 開閉ボタンは `role="button"`、開いていれば
  `aria-expanded="true"`、閉じていれば `false`。**Enter と Space の両方**で開閉する。
  出典: WAI-ARIA APG "Disclosure (Show/Hide)" の検索要約。
- **F14: モーダルにするなら別の規範**（`role="dialog"` ＋ `aria-modal="true"`、Esc で閉じる、
  Tab は中に閉じ込める）。出典: 同上の dialog パターン要約。
  → **コメント欄は行の直下にインライン展開する disclosure が素直**（GitHub も同じ形）。
  モーダルにすると閉じ込めとフォーカス復帰の実装義務が増え、差分を見ながら書けなくなる。
- **F15: 要件の AC-I1〜I5 は上記で全部答えが出る**: 開閉＝ボタン＋`aria-expanded`（Enter/Space）、
  取り消し＝pending の破棄、キーボード完結＝行の移動をフォーカス可能要素にする、
  フォーカス復帰＝閉じたら開いたボタンへ戻す、漏れ防止＝入力欄でのキーイベントを
  ページ側ショートカットへ伝播させない。

### このリポジトリの先例・規約（実測＝リポジトリ直読）

- **F16: skill は実行体を同梱してよい**。先例: `docs/ClaudeCode/skills/other/md-to-doc/generate.py`（1844 行）、
  `docs/ClaudeCode/skills/wiki/wiki-init/templates/*.tmpl`。
- **F17: 最も近い先例は `md-to-doc`** — Markdown を**外部依存なしの単一 HTML**にする skill。
  CSS 変数によるテーマ、localStorage への設定保存、目次・固定ヘッダーを持つ。
  **ただし生成は Python3 stdlib**（`generate.py:1-20` のドックストリング）。
  → 「単一 HTML を script で決定論的に作る」という形自体が、この repo では**既に確立した型**。
- **F18: frontmatter は `name` / `description`（日本語トリガ語を含む）/ 任意で `allowed-tools`**。
  `wiki-lint` は日本語・英語のトリガ語を併記している。
- **F19: トリガ語が競合する先住 skill がある**。`github/create-pr` は
  「PRを作って」「プルリクを作って」「レビュー依頼のPRを出して」で**必ず発火する**と書いている
  （`github/create-pr/SKILL.md:3`）。セッションには組み込みの `code-review` も居る。
  → 新 skill の description に「PR を作って」「レビューして」の**汎用句を書いてはいけない**
  （aidev 側の規約とも一致: `aidev-docs/README.md`「description の弁別性」）。
- **F20: sh で構造化データを読む先例はこの repo にある**。`aidev` CLI は YAML の**サブセット**を
  awk で読む（`awk '` ブロック 20 箇所、`yget` 呼び出し 72 箇所）。
  **「任意の YAML」ではなく「自分が書く形だけ」を読む**という割り切りで成立している。
- **F21: `jq` はこの環境には存在する**（`/usr/bin/jq`）が、要件 AC14 で依存禁止としている。
  → 「あれば使う」も**決定論性と可搬性を割る**ので、設計では原則使わない側に倒す。

## 影響範囲

- 新規ディレクトリ（`docs/ClaudeCode/skills/<カテゴリ>/<新 skill>/`）の追加のみ。**既存 skill のファイルは触らない**。
- ただし **description のトリガ語空間は共有資源**で、ここだけは既存 skill（F19）と衝突しうる。
- CI: `.github/workflows/aidev-cli.yml` の `paths` は `docs/ClaudeCode/skills/aidev/**` 限定。
  **新 skill のテストは現状どの CI にも載らない**。自動テストを書くならジョブ追加が要る（design で判断）。
- `.aidev/` 配下（work の成果物）は今回のコミット方針でリポジトリに載る。

## 実現性 / リスク

- **R1（最大）: sh で JSON を「読む」ことだけが難所。** 書き出し（HTML → JSON）と埋め込み（JSON → HTML）は
  文字列操作なので F6/F8 の範囲で成立する。難しいのは **F9（検証）・F10（未解決一覧）**で、
  **AI が手書きした任意形式の JSON** を awk で読むのは壊れやすい。
  緩和案（design で選ぶ）: ①JSON の**正規形**（1 レコード 1 行など）を skill が要求し、awk はその形だけ読む
  （F20 と同じ割り切り）／②検証と要約は**読む主体を LLM 自身にする**（SKILL.md にスキーマと読み方を書く）／
  ③script は「壊れた JSON を弾く最小限の構造検査」だけに責務を絞る。
- **R2: AC16 はブラウザ依存**（F2）。Firefox では自動復元が働かない。
  要件の書き換えか、UI 上の明示（「このブラウザでは下書きが保存できません」）が要る。
- **R3: ダウンロード先はブラウザ既定のフォルダ**（F4）。レビュー JSON をリポジトリ内に直接置けないので、
  人間が移動するか、パスを画面に表示して案内する必要がある（UX の摩擦。貼り付け用テキストエリアも併設が有効）。
- **R4: 決定論性は「時刻を埋めない」ことで守る**（F8 の実測は時刻を含まない生成）。
  生成時刻・乱数・ID の自動採番を HTML/JSON に混ぜると AC9 が即座に壊れる。
  コメント ID は**内容と位置から決まる形**（連番＋位置）にするか、JSON 側にだけ持たせる。
- **R5: 性能は目標規模で問題なし**（F7: 20k 行 0.5s）。10 万行級は未測定——ファイル単位の遅延展開を
  設計に入れておけば伸ばせる。
- **R6: 検索要約に依存した事実（F11/F12/F13/F14/F2）は一次ページで裏を取れていない。**
  design で仕様を固める際、**ネットワークが通る環境での再確認**を推奨事項として残す。

## 実装アンカー

- A1: 単一 HTML 生成 skill の先例（構成・CSS 変数・localStorage・単一ファイル化）—
  `docs/ClaudeCode/skills/other/md-to-doc/generate.py`（1844 行）、`…/md-to-doc/SKILL.md:1-6`
- A2: skill に実行体を同梱する置き方 — `docs/ClaudeCode/skills/other/md-to-doc/`（`SKILL.md` ＋ `generate.py`）、
  `docs/ClaudeCode/skills/wiki/wiki-init/templates/`
- A3: frontmatter とトリガ語の書式 — `docs/ClaudeCode/skills/wiki/wiki-lint/SKILL.md:1-4`、
  競合相手は `docs/ClaudeCode/skills/github/create-pr/SKILL.md:3`
- A4: awk で構造化データを読む house style — `docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev`（`yget`）
- A5: CI のパス限定 — `.github/workflows/aidev-cli.yml`（`paths:` が aidev 配下のみ）
- A6: **新 skill 本体の置き場は未特定** — `github/` か `other/` か新カテゴリかを design で決める
- A7: **差分パーサ・HTML テンプレート・JSON スキーマの実体は未特定**（新規作成。既存に流用元は無い）

## 実装時の注意

- **`file://` で `fetch` を書かない**（F3）。書くと開発機のローカルサーバでは動き、配布先の `file://` で壊れる。
- **localStorage のキーに差分識別子を必ず含める**（F1）。含めないと、別の差分をレビューした下書きが混ざる。
  さらに **try/catch で囲む**（F2。Firefox は例外を投げる）。
- **JSON を HTML に埋めるときは `<` を `<`**（F6）。差分にもコメントにも `</script>` は容易に混入する。
- **`git diff` はユーザー設定に影響される**。`-c core.quotepath=false` ＋ `--no-color` ＋ `--no-ext-diff` で
  明示的に上書きする（F9）。`diff.external` が刺さると出力形式ごと変わる。
- **`---` / `+++` のファイルヘッダ行を、追加/削除行と取り違えない**（行頭 1 文字で分類すると誤る）。
- **awk / sed のロケール依存**に注意。aidev CLI の CI コメント（`.github/workflows/aidev-cli.yml`）が、
  `mawk` と `gawk` の差、`-v` のエスケープ、POSIX 文字クラスのロケール依存で**実際に 57 件落ちた**と記録している。
  同じ罠が新 script にも当たる。
- 生成物に**時刻を埋めない**（R4）。

## design への申し送り

1. **実装言語を再確認する論点がある**（R1・F17）。repo の先例は Python3 stdlib（`md-to-doc`）、
   要件の選択は POSIX sh。**sh でも HTML 生成・エスケープ・決定論・性能は実測で成立**（F6〜F9）。
   割れるのは **JSON を読む部分だけ**なので、design では「sh のまま、JSON 読解の責務を最小化する」案を
   軸に、①正規形＋awk ②LLM が読む ③最小の構造検査だけ、のどれを採るかを決める。
2. **AC16 をブラウザ依存として書き直すか、UI で明示する**（R2・F2）。
3. **JSON スキーマは GitHub REST の命名に寄せる**（F12）: `path` / `line` / `side` / `start_line` /
   `start_side` / `body` / `in_reply_to` / レビューの `state`（`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED`）。
   将来の書き戻し（今回は対象外）への移行が安くなる。
4. **差分の識別子**（requirements の未確定事項）は `git rev-parse HEAD` ＋ 差分本文の `git hash-object` ＋
   `--raw` の blob hash で持てる（F10）。**不一致時は「警告して続行」を推奨**——
   拒否すると、少し進んだ作業ツリーに対して過去の指摘を読めなくなり、往復が止まる。
5. **コメント欄は disclosure（インライン展開）**とし、モーダルにしない（F13・F14）。
   フォーカスは開いたボタンへ戻す。Enter/Space で開閉、Esc で閉じる、修飾キー＋Enter で確定。
6. **未解決のまま design に渡す**: unified / side-by-side（**今回は unified のみを推奨**）、
   巨大差分の閾値（20k 行までは素で足りる。それ以上はファイル単位の遅延展開）、
   skill の配置カテゴリと名前（F19 の競合を避ける description を含む）、
   新 skill のテストを CI に載せるか（A5）。
7. **検索要約に依存した事実（R6）は、ネットワークの通る環境で一次ページに当て直すこと**を
   design のレビュー時に思い出せるよう残す。
