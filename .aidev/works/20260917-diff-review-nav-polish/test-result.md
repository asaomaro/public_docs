# テスト結果: ナビゲーションまわりの改善 6 件

## ラウンド 1

### 実行したもの

- `python3 -m unittest tests.test_diff_review`（生成側の既存回帰） — **126 passed / 0 failed / 0 skipped**
- `aidev smoke` — **pass（exit 0、3 本）**
- headless Chromium（`file://`・固定入力 `tests/fixture_repo.py --staged`）:
  - `uitest-nav.js`（この work の新規検査・16 件）— 通常モード **16 passed**、
    `--readonly` **16 passed**（AC1〜AC10 を両モードで検査）
    - AC1: 隙間の「すべて表示」ボタンが `↑`/`↓` と並んで出ること・押すと行数が増えその隙間の
      展開表示が消えること
    - AC2・AC3: ツリー名が `overflow:hidden`/`text-overflow:ellipsis`/`white-space:nowrap` で
      1 行に収まること・`title` が元の文字列と一致すること
    - AC4・AC5: `#btn-pane-left`/`#btn-pane-right` が `.topbar` の外・`.pane-head` の中にあること・
      パネルを畳んだ直後もそのボタンが幅・高さを持つ（= 見えている）こと・もう一度押すと開くこと
    - AC6: 中央をスクロールしてハイライトが一覧の表示範囲外のファイルへ移ったとき、一覧が
      自動でスクロールして表示範囲内に収めること・すでに見えているときは一覧を動かさないこと
    - AC7・AC8: 一覧をスクロールしても検索欄・絞り込み欄の `getBoundingClientRect().top` が
      変わらないこと
    - AC9・AC10: `#pane-center` のスクロールで進捗バーの幅が変わること・進捗バーのクリックで
      `#pane-center` がスクロールすること
  - `uitest-pane-keys.js`（`[`/`]`/`{`/`}` キーの不変・5 件）— **5 passed**
    - パネル開閉ボタンを移設した後も、キー操作の対象・挙動が変わらないこと
    - 移設後のボタンをクリックしても `aria-expanded` が正しく反転すること
  - `uitest-mobile.js`（モバイル幅・480px・3 件）— **3 passed**
    - 開閉ボタンをパネルへ移したことで生まれかけた退行（900px 以下で閉じたパネルを
      `display:none` にすると二度と開けない）が、design で見込んだ CSS の修正で
      実際に防がれていることを確認
  - 前 work の回帰一式を再実行し、影響が無いことを確認 — `uitest.js`（23 件）・
    `uitest-readonly.js`（7 件）・`uitest-keys.js`（5 件）・`uitest-current.js`
    （通常・`--readonly` 各 11 件）すべて **pass**
- **自己適用**: このリポジトリ自身の未ステージ差分から HTML を生成し、ブラウザで開いて
  `pageerror` が 0 件であることを確認（`console.error` は既存仕様のサンドボックス iframe
  由来のみ。前 work までと同じ）。

### 結果

全項目 **合格**。差し戻しなし。

## 受け入れ基準（AC）との対応

| AC | 検査 | 結果 |
|---|---|---|
| AC1（隙間の一括展開） | `uitest-nav.js` | pass |
| AC2・AC3（ツリー名の省略・title） | `uitest-nav.js` | pass |
| AC4・AC5（開閉ボタンの移設・閉じたパネルでの表示） | `uitest-nav.js` | pass |
| AC6（一覧のスクロール追従） | `uitest-nav.js` | pass |
| AC7・AC8（検索欄・絞り込み欄の固定） | `uitest-nav.js` | pass |
| AC9・AC10（進捗バー） | `uitest-nav.js` | pass |
| AC11（参照専用でも同じに動く） | `uitest-nav.js` を `--readonly` の生成物で再実行 | pass |
| AC12（既存キー操作の不変） | `uitest-pane-keys.js`・前 work の `uitest-keys.js` | pass |

## 既存への影響

- `python3 -m unittest tests.test_diff_review` は変更前と同じ 126 件が全通過（生成側は無変更）。
- 前 work（20260916-diff-review-ux-polish・20260916-diff-review-current-file）の回帰スクリプト
  一式を再実行し、影響が無いことを確認済み。
- モバイル幅（900px 以下）での退行（開閉ボタンの移設が生みかけた「閉じたら二度と開けない」）を
  design の段階で見込み、実装後に `uitest-mobile.js` で実際に防がれていることを確認した。
