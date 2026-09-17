# 判断の記録: 20260916-diff-review-ux-polish

> 1 決定 = 1 エントリ・追記式（`protocol.md`「8.1」）。既存エントリは書き直さない。
> この work は `mode: autonomous`。承認者が工程内にいないので、方針と成果物は
> 同じ approve ゲートで一度に受ける（`protocol-autonomous.md`「方針の事前承認」）。

## D1: 実行プロファイルは full、実行モードは autonomous

- **背景**: ユーザー指示は「新しいworkを起こして作業して」＋ 7 件の画面まわりの不備。
  「autonomous」の明示はないが、直前の 20260916-diff-review-rich / -bundle / -authoring も
  autonomous で通しており、同じ流儀を踏襲する。
- **決定**: `aidev new diff-review-ux-polish --mode autonomous --depends 20260916-diff-review-authoring`
  （profile full）。依存元は「画面（templates/）を最後に大きく触った work」。
- **理由・代替案**: 7 件のうち複数が `app.js` の同じ関数（`renderFileList`/`redrawFile` 等）に
  またがり、file 数・行数の両方で light の目安を超える。
- **影響**: 上流 4 文書の独立点検（`doccheck`）を requirements/design で実施済み（それぞれ
  1〜2 ラウンドで収束）。人間ゲートは置かない。

## D2: 「畳む」ボタンは隙間の展開だけを戻す。rich ↔ source やファイルの折りたたみ状態には触れない

- **背景**: 要件 3 は「展開ボタンの逆」としか書いていない。何を「初期状態」とみなすかが曖昧だった。
- **決定**: `collapseAllGaps` は `expandState[file.path]` だけを空にして再描画する。
  `viewModes`（rich/source）・`collapsed`（ファイル単位の折りたたみ）は触らない。
- **理由・代替案**: 「すべて展開」ボタン（既存）も隙間の展開だけを対象にしており、対称にするのが
  自然。rich/source まで戻すと、畳むボタンを押しただけで表示形式が変わるという別の驚きを生む。
- **影響**: design §F4・requirements AC16 に明記。`collapseAllGaps` は `renderThreads()` を呼ぶが
  `viewModes`/`collapsed` の書き換えは行わない。

## D3: 確認済み（viewed）はレビュー記録の JSON に入れない。ブラウザの localStorage だけに置く

- **背景**: 「確認済み」は差分を見たかどうかの**画面の状態**であって、指摘（コメント）ではない。
  過去 work（decisions.md D5・表示/UI 状態は localStorage 側という前例）と同じ整理。
- **決定**: `viewedFiles` は `persist()`/`restore()` で `state`/`drafts` と同じ localStorage
  エントリに同居させるが、**`exportText()`/`canonicalRecord()` はここを一切読まない**ので
  書き出す JSON には混ざらない。
- **理由・代替案**: レビュー記録のスキーマ（`diff-review/2`）を変えると、既存の `check`/`comment`/
  `submit` サブコマンドや JSON の往復契約全体に影響する。画面だけの状態なら影響範囲を
  `templates/` に閉じられる。
- **影響**: requirements AC9〜AC12。`applyDiffData`（バンドル差し替え時のリセット対象）にも
  `viewedFiles = {}` を含めた（別の差分を開いたら前の確認済みを引きずらない）。

## D4: アイコンの「選択中」配色は、既定で true になるボタンには付けない

- **背景**: レビュー ラウンド 1 の指摘（review.md 参照）。`.icon-btn[aria-expanded="true"]` を
  クラス単位で当てたところ、`.file-toggle`（既定で展開＝ true）と `#btn-pane-left/right`
  （既定で開いている＝ true）にも意図せず当たり、ほとんどのファイルの折りたたみアイコンが
  常時アクセントカラーになっていた（実測: `getComputedStyle` で確認）。
- **決定**: 配色は **既定が false で「いま切り替えた」ことに意味があるボタンだけ**に絞る
  （`#btn-tree[aria-pressed="true"]` ・ `#btn-help-open[aria-expanded="true"]`）。
  `.file-toggle` と `#btn-pane-left/right` には付けない。
- **理由・代替案**: 「同じ属性なら同じ見た目」で揃える設計時の直感は自然だが、その属性が
  **既定でどちらの値を取るか**まで含めて揃えないと、既定状態が常時ハイライトされるノイズになる。
  design.md の F5 表にはそもそも配色の指定は無く、実装時に独自に足したものなので、
  過不足なく絞るのが素直な直し方だった。
- **影響**: `templates/style.css` のみ。`btn-tree` は既存の `.view-toggle[aria-pressed="true"]`
  （rich/source 切り替え）と同じ「モード切り替えボタン」の扱いに揃う。
