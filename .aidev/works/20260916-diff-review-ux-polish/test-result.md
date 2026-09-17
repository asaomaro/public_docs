# テスト結果: 画面まわりの不備 7 件

## ラウンド 1

### 実行したもの

- `python3 -m unittest tests.test_diff_review`（生成側の既存回帰） — **126 passed / 0 failed / 0 skipped**
- `aidev smoke` — **pass（exit 0、3 本）**
- headless Chromium（`file://`・固定入力 `tests/fixture_repo.py --staged`）での画面検証（scratch に書き捨て、T11/T12 の実体）:
  - `uitest.js`（通常モード・23 件）— **23 passed**
    - ツリーの字下げ（深さで `x` が変わること）
    - 検索 3 種（部分一致 / ワイルドカード `*.py` / 正規表現 `/^src\/api\//` / 壊れた正規表現のエラー表示）
    - アイコン化した全ボタン（`btn-pane-left/right`・`btn-theme`・`btn-help-open`・`btn-tree`）に
      `title`/`aria-label` があること
    - 確認済み: チェック → 件数表示（`N / M`）→ 再読み込みで状態が残ること → 書き出し JSON に
      `viewed` が混ざらないこと
    - パスコピー: ボタンの一時表示変化（`⧉` → `✓`）
    - すべて展開 → 畳む で行数が元に戻ること
    - **F10 の回帰**: research で再現したシナリオ（4 ギャップ中、1 クリックでは閉じ切らない隙間を選んで
      展開）を検査。**フォーカスが押した隙間自身のボタンに留まる**こと（以前は常に DOM 順で最初の
      `.expander` ボタンに飛んでいた）を確認
  - `uitest-readonly.js`（`--readonly`・7 件）— **7 passed**
    - コメント関連の導線が無いこと・検索/ツリー/確認済みは参照専用でも動くこと
  - `uitest-keys.js`（キー割り当ての不変・5 件）— **5 passed**
    - `e` で 1 段階展開・`Shift+E` でそのファイルの隙間が 0 になる
    - `f` で `data-collapsed` が反転する
    - `t` で rich ↔ source が切り替わる（rich 表示中はファイルに `.row` が無いため、
      `gotoFile` と同じやり方でセクション自体へ focus してから検査）
- **自己適用**: このリポジトリ自身の未ステージ差分（`SKILL.md`・`app.js`・`page.html`・`style.css`・
  `ui.js` の 5 ファイル）から HTML を生成し、ブラウザで開いて `pageerror` が 0 件であることを確認
  （読み込み約 0.9 秒）。`console.error` が 16 件出るが、すべて
  `Blocked script execution in 'about:srcdoc' ...`——**この work と無関係の既存仕様**
  （`.html` の rich diff を `<iframe sandbox="">` で描画し、スクリプトを意図的に実行させない。
  SKILL.md に明記済み）。

### 結果

全項目 **合格**。差し戻しなし。

## 受け入れ基準（AC）との対応

| AC | 検査 | 結果 |
|---|---|---|
| AC1（ツリーの字下げ） | `uitest.js` tree indentation | pass |
| AC2（検索の絞り込み・祖先自動展開） | `uitest.js` search × 3 | pass |
| AC3〜AC5（部分一致・ワイルドカード・正規表現） | 同上 | pass |
| AC6（畳むボタン） | `uitest.js` expand-all/collapse-all round trip | pass |
| AC7・AC8（アイコン化・文字のまま） | `uitest.js` icon title/aria-label 全数 | pass |
| AC9〜AC12（確認済み・件数・永続化・JSON 非混入） | `uitest.js` viewed count 系 4 件 | pass |
| AC13（パスコピー） | `uitest.js` copy-path | pass |
| AC14（ファイル名クリック廃止） | `uitest.js`（`.path-text` はクリックハンドラを持たない。実装レビューで確認） | pass |
| AC15（展開時にフォーカスが動かない） | `uitest.js` F10 regression | pass |
| AC16（畳むと初期状態へ戻る・rich/source は不変） | `uitest.js` collapse-all round trip | pass |
| AC-I1〜AC-I2（参照専用・保存の独立性） | `uitest-readonly.js` / export 検査 | pass |
| AC-I3・AC-I4（キー割り当ての不変・新キー無し） | `uitest-keys.js` | pass |

## 既存への影響

- `python3 -m unittest tests.test_diff_review` は**変更前と同じ 126 件が全通過**（生成側は一切
  触っていないので当然だが、テンプレート文字列を検査するテストがあるため回帰の網としても効いている）。
- 参照専用 HTML でも新機能（検索・ツリー・確認済み）がすべて動くことを個別に確認済み。
