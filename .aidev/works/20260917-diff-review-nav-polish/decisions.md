# 判断の記録: 20260917-diff-review-nav-polish

> 1 決定 = 1 エントリ・追記式（`protocol.md`「8.1」）。既存エントリは書き直さない。
> この work は `mode: autonomous`。承認者が工程内にいないので、方針と成果物は
> 同じ approve ゲートで一度に受ける（`protocol-autonomous.md`「方針の事前承認」）。

## D1: 実行プロファイルは full、実行モードは autonomous

- **背景**: ユーザーから 6 件の追加指摘（GitHub 風の一括展開・ツリー名の省略・パネル開閉
  ボタンの配置・一覧のスクロール追従・検索欄の固定・進捗バー）。
- **決定**: `aidev new diff-review-nav-polish --mode autonomous
  --depends 20260916-diff-review-ux-polish,20260916-diff-review-current-file`（profile full）。
- **理由・代替案**: 触るファイルが `page.html`/`style.css`/`app.js` の 3 つで light の目安
  （既定 3）に収まりそうだが、F3（パネル開閉ボタンの移設）はパネルの折りたたみという
  既存の中核的な振る舞いを変える構造変更であり、「振る舞いを変えない/小規模」という light の
  条件を素直には満たさない。full を選び、上流 4 文書の独立点検を通す。
- **影響**: `requirements`/`design`/`tasks` それぞれで `doccheck`（同一セッション内点検）を実施。

## D2: パネル開閉ボタンは新設せず、既存の 1 個を DOM 上で移設するだけにする

- **背景**: 「開閉ボタンを閉じたパネル自身の領域に置く」という要件を実現する方法として、
  (a) 開くボタンと閉じるボタンを別々に新設する、(b) 既存の 1 個のボタンをそのまま
  パネルの中へ移し、閉じたときも CSS でそのボタンだけを残す、の 2 案があった。
- **決定**: (b) を採用。`ui.js` の `setPane`/`togglePane`/`wireSeparator`/`init` は
  `document.getElementById("btn-pane-" + which)` で参照するだけで DOM 上の位置に依存しない
  （research.md F3 で確認）ので、ボタンを移設するだけで済み、**`ui.js` を無改造にできた**。
- **理由・代替案**: (a) はボタンが 2 個になり、`aria-expanded` 等の状態を 2 個のボタン間で
  同期する新しいコードが要る。(b) は既存の状態管理をそのまま使い回せ、変更量が最小になる。
- **影響**: `templates/ui.js` の diff は 0 行。`templates/page.html`/`templates/style.css` だけで
  F3 を実現できた。

## D3: 900px 以下（モバイル幅）のパネル開閉ボタンの見た目も、最小限だけ直す

- **背景**: 要件のスコープでは「モバイル幅でのパネル開閉ボタンの再配置は対象外」としていたが、
  ボタンをトップバーから各パネルへ移す（F3）ことそのものが、既存のモバイル用 CSS
  （閉じたパネルを `display:none` で丸ごと隠す）と衝突し、**モバイルで閉じたパネルを
  二度と開けなくなる**という退行を生むことに design の段階で気づいた。
- **決定**: 「モバイル向けの再設計はしない」という要件のスコープ外の宣言は守ったまま、
  この退行**だけ**を最小限直す（`display: none` を「中身は隠すがボタンは残す」規則に
  差し替える 1 行）。
- **理由・代替案**: 直さない場合、要件のスコープ外という理由でモバイル利用者に実害のある
  退行を出荷することになる。移設そのものが生む副作用の埋め合わせは、スコープの拡大ではなく
  最小限の是正として扱った。
- **影響**: `templates/style.css` の `@media (max-width: 900px)` ブロック内、1 行の変更。
  480px 幅の headless Chromium で実測し、退行が実際に防がれていることを確認した
  （test-result.md）。

## D4: 進捗バーは `#pane-center` のスクロールを見る（`document.documentElement` ではない）

- **背景**: 参考にした `md-to-doc` skill は 1 ペイン構成でページ自体がスクロールするため
  `document.documentElement` を見ているが、`diff-review-html` は 3 ペイン構成で
  ページ自体は固定高さ、`#pane-center` だけがスクロールする（research.md F6）。
- **決定**: `document.documentElement` ではなく `#pane-center` の `scrollTop`/`scrollHeight` を見る。
- **理由・代替案**: `document.documentElement` を見ても、それ自体がスクロールしないため
  常に 0% のままになり、要件（AC9: スクロール位置に応じてバーの長さが変わる）を満たせない。
- **影響**: `templates/app.js` に `updateProgressBar()` を新設。既存の `#pane-center` scroll
  リスナー（前 work 20260916-diff-review-current-file で追加済み）に相乗りさせ、
  2 本目の scroll リスナーを増やさなかった。
