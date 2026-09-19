# テスト結果: `.dreview` を VSCode で開いて読み書きする拡張機能

> **ラウンド 2・最終**（独立レビュー ラウンド1 の差し戻し——記録の target の保持・AC4 の検査の強化・画面側の同期のテスト・
> 信頼されていないワークスペース——を直したあとの検証）。ラウンド 1 の内容はその下に残す。

## 実行したもの（ラウンド 2・最終）

- `python3 -m unittest discover -s tests` — 146 passed / 0 failed / 0 skipped
- `npm run test:unit` — 29 passed / 0 failed / 0 skipped
- `npm run test:protocol`（新規。同梱の画面＋本物の `SyncSession`＋偽の文書、headless Chromium）— 9 passed / 0 failed
  （レビュー ラウンド 2 の nit で「返事の本文が送った全文と同じでも、重ねた変更は送る」を足した。以下は足す前の 8 場面）
  （見るだけ・解決と戻す（Python の `resolve` とバイト一致）・別の差分の記録（target を保つ）・すれ違い（知らせと消えること）・
  返事待ちの間の重ね書き・版だけ進む・元に戻す相当・壊れた文書）。記録の target の修正を戻した画面では「別の差分の記録」が
  落ちることを確認した。
- `npm run test:e2e` — 19 passed / 0 failed（ラウンド 1 の 17 件＋「画面での解決は Python の resolve と同じバイト列になり、
  未解決に戻すと元に戻る（記録の target も保つ）」＋「信頼されていないワークスペース（制限モード）でも開いて表示できる」。
  AC4 の場面に「元の中身（files・target・記録の target・元のスレッド）が変わらず、新しいスレッドは末尾だけ」を足した）。
  この実行のあとに変えたのは `vscode/README.md` だけ。
- 追加の検証（スクラッチ）: HTML 版の回帰とホストの模擬 16 passed / 0 failed、`.vsix` を入れた VSCode での開く・書く・保存（正規形・`check` 通過）
- `aidev smoke` — pass（3 本）

```
$ npm run test:e2e
PASS AC1/AC2/AC-I1/AC-I4: .dreview が既定で開き、バンドルと同じ差分とコメントが出て、先頭行にフォーカス
PASS AC-I3: マウス無しで行を移動できる（j / k）
PASS AC-I2: 書きかけを Esc で閉じても文書は変わらない
PASS AC3/AC-I2: コメントを確定すると未保存になる（書きかけは下書きから戻る）
PASS AC4/AC-I3: Ctrl+S で保存され、check を通り、Python の正規形とバイト一致する
PASS AC-I5: 入力欄の Ctrl+Z は入力欄の取り消しで、文書の元に戻すにならない
PASS AC6: VSCode の元に戻す・やり直しが画面に反映される
PASS AC8/AC-I4: 外部での追記に、スクロール位置と現在行を保ったまま追従する
PASS AC-I5: WebView の中から VSCode のキー（Ctrl+P）が効く
PASS AC15: VSCode の配色に合わせ、切り替えにその場で追従する
PASS AC-I1: 「エディターを開き直す」でテキストエディタを選べる
PASS AC7: 未保存のまま閉じると VSCode 標準の保存確認が出る
PASS AC5: 見るだけ・変更せずに保存・変更して元に戻してから保存、のどれでもバイト列が変わらない
PASS AC4/AC5: 画面での解決は Python の resolve と同じバイト列になり、未解決に戻すと元に戻る（記録の target も保つ）
PASS AC5/D2: CRLF の .dreview は開いただけでは書き換えず、最初の編集で正規形（LF）になる
PASS AC9: 壊れた .dreview は理由を出し、直ると表示する
PASS AC14: 2MB を超えるバンドルで、コメントの確定から画面への反映が 1 秒以内
PASS AC10: CSP 違反と WebView からの外部通信が 0 件で、nonce の無いスクリプトと eval は動かない
PASS AC10: 信頼されていないワークスペース（制限モード）でも開いて表示できる
NOTE AC14: バンドル 9106516 バイト / 確定→画面反映 581ms / 確定→文書が未保存 2624ms
NOTE AC14: 元に戻す→画面反映 1533ms（その場の差し替え）
NOTE AC10: 陽性対照の違反を検出（1 件）
RESULT: 19 passed / 0 failed
```

ラウンド 2 での受け入れ基準の判定の変化:
- AC4: pass — 整形の正規性に加え、元の中身が保たれていること・画面での解決が Python の `resolve` とバイト一致すること（別の差分に
  対する記録を持つファイルで）を e2e と `test:protocol` で確かめた。
- AC5: pass — 解決 → 未解決に戻す（打ち消し合う操作）で元のバイト列に戻ることを、実機と `test:protocol` で確かめた。
- AC10: pass — 「信頼されていないワークスペースでも開ける」を、信頼を有効にした別の VSCode（制限モード）で実際に開いて確かめた。
- AC14: pass — 確定 → 画面反映 581ms（9.1MB）。この回は文書が未保存になるまで 2.6 秒・元に戻すの反映 1.5 秒で、ラウンド 1 より遅い
  （同じ機械で e2e を続けて回した負荷の影響とみる。要件の目安は「確定から画面への反映」で、それは 1 秒以内）。
- ほかの AC はラウンド 1 と同じ（下）。

## ラウンド 1


- `python3 -m unittest discover -s tests`（`docs/ClaudeCode/skills/other/diff-review-html`）— 146 passed / 0 failed / 0 skipped
  （既存 140 件＋この work で足した 6 件。`node --check` の 1 件は node がある環境なので skip されていない）
- `npm run test:unit`（`vscode/`）— 29 passed / 0 failed / 0 skipped
  （`viewerHtml` 6・`minimalEdit` 6（長さ 3 までの全組み合わせを含む）・`sync` 17）
- `npm run test:e2e`（`vscode/`。実機の VSCode 1.138.0 linux-x64 を CDP で操作・実キー入力）— 17 passed / 0 failed
- 追加の検証（リポジトリには置かない。セッションのスクラッチで実行）:
  - HTML 版の回帰と、ホストを模した画面の往復（headless Chromium）— 16 passed / 0 failed
  - `.vsix` を使い捨てのポータブル VSCode に**インストールして**使う（開発用パスではなく実際の配布物）— 描画 6 ファイル・265 行、
    キーボードで追加したコメントを保存 → `check` を通り正規形
  - `npx vsce ls` — `.vsix` の中身は `package.json`・`README.md`・`media/viewer.html`・`out/src/*.js` の 10 ファイル（74.21 KB）
- `aidev smoke` — pass（3 本）

## 受け入れ基準ごとの判定

- AC1: pass — e2e「.dreview が既定で開き…」: クイックオープンで開くとテキストエディタではなくビューアの WebView が開く。
- AC2: pass — e2e: Python でバンドルを読んだファイル数・スレッド数・全コメントの本文と、画面の表示が一致。
- AC3: pass — e2e: キーボードでコメントを確定すると未保存になる。追加の検証 B: 解決にすると編集が送られる。
  返信・編集・削除・提出の各操作はすべて `persist()` を通り（design「依拠する既存の事実」）、送る条件は記録の変化だけ
  （`sendHostEdit`）なので同じ経路。**e2e で個別に押したのはコメントの確定と解決/未解決だけ**（下の「未検証の穴」）。
- AC4: pass — e2e: `Ctrl+S` で保存したファイルが `diff_review.py check` を通り、Python の `bundle_text` で作り直したものとバイト一致。
  `.vsix` を入れた VSCode でも同じ。
- AC5: pass — e2e: 見るだけ（確認済みの切り替え・移動）・変更せずに保存・変更して元に戻してから保存、のどれでもバイト列が変わらない。
  CRLF の `.dreview` は開いただけでは未保存にならず、最初の編集と保存で LF の正規形になる。追加の検証 B: 解決 → 未解決に戻すで
  全文が元のバイト列に戻る（Python の `comment` で書いた 4 スレッドのバンドル）。
- AC6: pass — e2e: WebView の中で `Ctrl+Z` / `Ctrl+Shift+Z` → スレッドが減る・戻る、未保存の印も追従。
- AC7: pass — e2e: 未保存のまま「エディターを閉じる」→ VSCode の保存確認が出る。「保存しない」でファイルは変わらない。
- AC8: pass — e2e: 40 行下へ移動してスクロールした状態で `diff_review.py comment` がファイルを書き換える → 再読み込みなしでスレッドが
  増え、現在行・スクロール量・現在行の画面上の位置（±2px）が変わらない。
- AC9: pass — e2e: 壊れた `.dreview` は「表示できません」と理由を出し行を出さない。外で直すと表示される。
- AC10: pass — e2e: ビューアの CSP への違反 0 件・WebView からの外部通信 0 件。陽性対照: nonce の無いインラインスクリプトは動かず、
  eval は（正しい nonce のページスクリプトから試して）blocked、その違反をコンソールで検出できることも確認。
  `capabilities.untrustedWorkspaces.supported: true`（`package.json`）。
- AC11: pass — unit「同梱のビューアは diff_review.py view の出力そのもの」。拡張のソース（`vscode/src/*.ts`）に解析・検証・描画・
  正規形の処理は無い（テキストと版を運ぶ `SyncSession`・CSP の付与・最小の書き換え範囲だけ）。
- AC12: pass — Python の unittest 146 件。追加の検証 A: HTML 版で開く・コメント・localStorage への下書き・再読み込みでの復元・
  JSON の書き出し（id を振り直す正規形）・書き出しの案内・参照専用 HTML・`view` の開く案内が今までどおりで、例外 0 件。
- AC13: pass — `npm run package` で `.vsix` を作れた。手順は `vscode/README.md`、契約は `SKILL.md`「エディタ拡張から使う」。
- AC14: pass — e2e 17 件（開く・編集・保存・外部変更への追従を含む）。9,106,516 バイトのバンドル（目安の 2MB を大きく超える）で
  コメントの確定 → 画面反映 337ms（目安 1 秒以内）。確定 → 文書が未保存 1,324ms、元に戻す → 画面反映 817ms（参考値）。
- AC15: pass — e2e: ダーク → ライト → ダークの切り替えに、ビューアの `data-theme` がその場で追従。
- AC16: pass — `npx vsce ls` に `node_modules`・`src`・`test` が無い。`git status` に `node_modules`・`out`・`media/viewer.html`・
  `.vscode-test`・`*.vsix` が出ない（`vscode/.gitignore`）。
- AC-I1: pass — e2e: 既定で開く。「エディターを開き直す」の選択肢に「テキストエディター」と「Diff Review」がある。閉じるときの確認は AC7。
- AC-I2: pass — e2e: 書きかけを `Esc` で閉じても未保存にならない。開き直すと下書きが戻り、`Ctrl+Enter` で確定して未保存になる。
- AC-I3: pass — e2e: 開いた直後の WebView で `j` / `k` が効く（クリックなし）。`c`・`Ctrl+Enter`・`Ctrl+S` もキーボードだけで通る。
- AC-I4: pass — e2e: 開いた直後のフォーカスは先頭行。外部変更のあとも現在行が同じ。
- AC-I5: pass — e2e: 文書に元に戻せる編集がある状態で、入力欄の中の `Ctrl+Z` は入力欄だけを取り消す（値が空・未保存にならない・
  スレッドが減らない）。WebView の中の行から `Ctrl+P` で VSCode のクイックオープンが開く。

## 失敗の証跡

test 工程では失敗が発生していない（上の 4 種の実行はすべて初回で合格）。

coding 工程の途中の失敗（生の出力は各タスク点検の時点のもの）は `review.md`「タスク点検ログ」に内容と対応を残した。
代表的なもの: 書き込みに使った道具が `\u2028` を生の文字に変え、`app.js` 全体が構文エラーになっていた（`node --check` の出力
`SyntaxError: Invalid regular expression: missing /`）。この時点の e2e は次のとおり落ちていた（直す前の出力）:

```
$ npm run test:e2e
FAIL AC1/AC2/AC-I1/AC-I4: .dreview が既定で開き、差分とコメントが出て、先頭行にフォーカス: 待ちきれませんでした: 描画
FAIL AC-I3: マウス無しで行を移動できる: 待ちきれませんでした: j で移動
…
PASS AC10: CSP 違反と WebView からの外部通信が 0 件
RESULT: 2 passed / 14 failed
```

## 最終の e2e の出力

```
$ npm run test:e2e
PASS AC1/AC2/AC-I1/AC-I4: .dreview が既定で開き、バンドルと同じ差分とコメントが出て、先頭行にフォーカス
PASS AC-I3: マウス無しで行を移動できる（j / k）
PASS AC-I2: 書きかけを Esc で閉じても文書は変わらない
PASS AC3/AC-I2: コメントを確定すると未保存になる（書きかけは下書きから戻る）
PASS AC4/AC-I3: Ctrl+S で保存され、check を通り、Python の正規形とバイト一致する
PASS AC-I5: 入力欄の Ctrl+Z は入力欄の取り消しで、文書の元に戻すにならない
PASS AC6: VSCode の元に戻す・やり直しが画面に反映される
PASS AC8/AC-I4: 外部での追記に、スクロール位置と現在行を保ったまま追従する
PASS AC-I5: WebView の中から VSCode のキー（Ctrl+P）が効く
PASS AC15: VSCode の配色に合わせ、切り替えにその場で追従する
PASS AC-I1: 「エディターを開き直す」でテキストエディタを選べる
PASS AC7: 未保存のまま閉じると VSCode 標準の保存確認が出る
PASS AC5: 見るだけ・変更せずに保存・変更して元に戻してから保存、のどれでもバイト列が変わらない
PASS AC5/D2: CRLF の .dreview は開いただけでは書き換えず、最初の編集で正規形（LF）になる
PASS AC9: 壊れた .dreview は理由を出し、直ると表示する
PASS AC14: 2MB を超えるバンドルで、コメントの確定から画面への反映が 1 秒以内
PASS AC10: CSP 違反と WebView からの外部通信が 0 件で、nonce の無いスクリプトと eval は動かない
NOTE AC14: バンドル 9106516 バイト / 確定→画面反映 337ms / 確定→文書が未保存 1324ms
NOTE AC14: 元に戻す→画面反映 817ms（その場の差し替え）
NOTE AC10: 陽性対照の違反を検出（1 件）
RESULT: 17 passed / 0 failed
```

## 起動確認（smoke）

```
$ aidev smoke
smoke: 20260919-diff-review-vscode
$ sh docs/ClaudeCode/skills/aidev/aidev-docs/bin/aidev help
（…aidev CLI のヘルプ出力…）
$ python3 docs/ClaudeCode/skills/other/diff-review-html/diff_review.py --help
（…diff_review.py のヘルプ出力…）
$ python3 docs/ClaudeCode/skills/other/diff-review-html/diff_review.py template --repo .
（…空のレビュー記録の JSON…）
smoke: pass (exit 0, 3 本)
```

**`smokeCommands` は増やさない**: この work が足した入口は VSCode 拡張で、その起動確認は画面（GUI）と VSCode の取得（初回は
数百 MB のダウンロード）と `npm ci` を要し、「短く終わるコマンド」として smoke に置けない。代わりに、test 工程で
`.vsix` を使い捨ての VSCode に実際にインストールして開く・書く・保存するところまで確かめた（上の追加の検証）。
CLI（`diff_review.py`）の入口は増えていない。

## 未検証の穴（skip / 環境不足）

- **Windows 版・macOS 版の VSCode では試していない**（Linux 版 1.138.0 のみ。利用者の Windows の VSCode には意図して触れていない）。
  CSP・キー入力の扱い（入力欄の `Ctrl+Z`）・配色のクラスは OS で変わらない見込みだが、確かめていない。
- **e2e で個別に押していない書き込み操作**: 返信・コメントの編集・削除・説明コメント・レビューの提出と、その編集・削除。
  いずれも既存の `persist()` を通る同じ経路で、送る条件（記録の変化）と書き方（正規形）は共通。解決/未解決と確定は実機で確かめた。
- 同じ `.dreview` を分割して 2 つの画面で開いたときの振る舞い（README の既知の制約に書いた）。
- `test:protocol` は Chromium を要する（`npx playwright-core install chromium` か `CHROMIUM_PATH`）。Python の unittest には入っていない。
- BOM 付きの `.dreview` を保存したときの扱い（README の既知の制約に書いた）。
- 未保存の変更がある間の外部変更（VSCode は読み直さない。保存時の衝突は VSCode 標準の扱い。README に書いた）。
- e2e と追加の検証の一部（HTML 版の回帰・ホストの模擬・`.vsix` のインストール）は、画面と VSCode を要するためリポジトリの
  自動テスト（Python の unittest）には入っていない。リポジトリには `vscode/test/e2e/`（`npm run test:e2e`）として置いた。
- 調査中の最初の試作（ポータブル化の前）が、ホームの `~/.vscode/argv.json`（以前からあった利用者のファイル）を書き換えていた。
  中身は VSCode の既定の 2 項目で、書き換え前の内容は分からない。以降の実行では更新時刻が変わらないことを確認した。
