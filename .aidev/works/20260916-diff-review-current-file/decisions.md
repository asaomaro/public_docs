# 判断の記録: 20260916-diff-review-current-file

> 1 決定 = 1 エントリ・追記式（`protocol.md`「8.1」）。既存エントリは書き直さない。
> この work は `mode: autonomous` / `profile: light`。

## D1: 実行プロファイルは light

- **背景**: 「現在表示中のファイルをファイル一覧でハイライトする」という単一の閉じた挙動。
  触るファイルは `templates/app.js` と `templates/style.css` の 2 つ（既定の上限 3 以下）。
  公開 I/F（レビュー記録の JSON スキーマ）には触れない。新しい外部依存も足さない。
- **決定**: `aidev new diff-review-current-file --mode autonomous --profile light
  --depends 20260916-diff-review-ux-polish`。
- **理由・代替案**: light の 4 条件（振る舞いが閉じている・ファイル数・共有 API 不可侵・新規依存なし）
  をすべて満たす。昇格が要る兆候（想定外のファイルに触れた・テスト失敗・レビューで must）は
  最後まで出なかった。
- **影響**: 上流は `requirements.md` 1 ゲートに畳み、`design.md`/`tasks.md` は薄い版のみ
  （`walkthrough.md` は作らない）。coding 以降（taskcheck・test・review・deliver）は full と同一に実施。

## D2: 判定は scroll イベント＋幾何計算。IntersectionObserver は使わない

- **背景**: 「いま表示中のファイル」をどう求めるか。候補は (a) `IntersectionObserver`、
  (b) `scroll` イベント＋`getBoundingClientRect()` の手計算。
- **決定**: (b) を採用。`#pane-center` の `scroll` に `requestAnimationFrame` で間引いた
  リスナーを張り、各 `.file` の上端とペイン上端を比較する。
- **理由・代替案**: このファイルは既に `focusInPlace`（F10 の焦点維持）で同じ
  `getBoundingClientRect()` ベースの幾何計算を持っており、書き方を揃えられる。
  `IntersectionObserver` は非同期でコールバックのタイミングが「その回のスクロール直後」と
  ずれることがあり、`gotoFile()` からの**即時反映**（AC7）を素直に書きにくい
  （observer のコールバックを待つ形になり、クリック直後に同期的にハイライトを反映する今の作り
  より複雑になる）。ファイル数が数十件程度までの想定であれば、手計算のコストは無視できる。
- **影響**: `templates/app.js` に `currentFileSection()`/`applyCurrentFileHighlight()` を追加。
  新しい purely-visual な状態なので `viewedFiles` と同じく記録には入れない。

## D3: ハイライトの背景色は `var(--bg)`（`var(--surface)` ではない）

- **背景**: レビュー ラウンド 1 の指摘（`review.md` 参照）。最初に `var(--surface)` を使ったが、
  `.pane-left` 自体の既定の背景も `var(--surface)` のため、実測すると色の変化が無かった。
- **決定**: 既存の `:hover`/`:focus-visible` と同じ `var(--bg)` に変更。
- **理由・代替案**: 新しい色を増やすより、**同じ意味（「注目している行」）に使っている既存の色を
  再利用する**方が一貫性が保てる。
- **影響**: `templates/style.css` のみ。
