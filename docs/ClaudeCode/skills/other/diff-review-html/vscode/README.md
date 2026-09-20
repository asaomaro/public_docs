# Diff Review（VSCode 拡張）

`diff-review-html` の `.dreview`（差分とレビュー指摘を 1 つにまとめたファイル）を VSCode で開き、
HTML 版と**同じ画面**のまま読み書きする拡張。Marketplace には公開していない（手元でビルドして入れる）。

- `.dreview` をエクスプローラーから開くと、この画面が既定で開く（テキストで見たいときは「エディターを開き直す」）。
- 画面でのコメント・返信・編集・削除・解決・説明コメント・レビューの提出は、**その `.dreview` への編集**になる。
  未保存の印・`Ctrl+S` での保存・元に戻す／やり直し・閉じるときの確認は VSCode の標準どおり。
- CLI（`diff_review.py comment` / `resolve`）や git でファイルが変わると、開いている画面が再読み込みなしで追従する。
  差分が同じ（指摘だけが変わった）ならスクロール位置と現在行はそのまま、差分そのものが変わったら先頭から表示し直す。
  **未保存の変更がある間は追従しない**（VSCode がディスクから読み直さないため。保存時の衝突は VSCode の標準の扱いになる）。
- 配色は VSCode のライト／ダークに合わせる（画面の「◐」で「自動」のとき）。

## しくみ（コードを二重に持たない）

画面は `../diff_review.py view` の出力**そのもの**で、ビルド時に `media/viewer.html` として生成する（コミットしない）。
解析・検証・描画・正規形の書き出しは画面の JS（`../templates/app.js`。HTML 版と共通）が行い、拡張は
「文書のテキストと版」と「画面」をメッセージでつなぐだけ。画面を直せば、次のビルドで拡張にもそのまま入る。

| ファイル | 役割 |
|---|---|
| `src/extension.ts` | 起動。`media/viewer.html` を読み、エディタを登録する |
| `src/editorProvider.ts` | `.dreview` のカスタムエディタ（WebView の設定と VSCode のイベントの結線） |
| `src/sync.ts` | 画面と文書の同期の判断（VSCode に依存しない。unit テストで順序を検査） |
| `src/viewerHtml.ts` | 画面に CSP と nonce を付ける |
| `src/minimalEdit.ts` | 文書の書き換えを最小の範囲にする |
| `scripts/build-viewer.mjs` | `media/viewer.html` を `diff_review.py view` で生成する |
| `media/icon.svg` / `icon.png` | 拡張のアイコン（原本は SVG。PNG は 256px に書き出したもの） |

画面と拡張のあいだのメッセージの契約は `../SKILL.md` の「エディタ拡張から使う」にある。

## 必要なもの

- Node.js 22 以上（unit テストの起動にグロブ指定の `node --test` を使う）と npm
- Python 3（画面の生成に `diff_review.py` を使う。`python3` 以外で呼ぶなら環境変数 `PYTHON` で指定）
- e2e を回すときだけ: 画面（Linux なら X / WSLg）、初回はネットワーク（テスト用の VSCode を取得する）
- `test:protocol` を回すときだけ: Chromium（下の「テスト」）
- e2e と `test:protocol` の両方: git（検査用の固定リポジトリ `../tests/fixture_repo.py` を作るため）

## ビルドとインストール

```sh
cd <skill>/vscode
npm ci
npm run package          # 画面の生成 → コンパイル → diff-review-vscode-<版>.vsix
code --install-extension diff-review-vscode-0.1.0.vsix
```

入れたあとは `.dreview` を開くだけ。消すときは拡張機能ビューから「アンインストール」。
`.vsix` に入るのは `package.json`・`README.md`・`out/src/`・`media/viewer.html` だけで、実行時の依存は無い
（`npx vsce ls` で確かめられる）。

## テスト

```sh
npm run test:unit        # CSP の付与・最小の書き換え・同期の順序・「同梱の画面 == view の出力」（VSCode 不要）
npm run test:protocol    # 同梱の画面と本物の同期（SyncSession）をつなぎ、すれ違い・送り直し・壊れた文書などの順序を確かめる
npm run test:e2e         # 実機の VSCode を起動し、キー入力で開く・書く・保存・元に戻す・外部変更・配色などを確かめる
```

- `test:protocol` は headless Chromium を使う。`npx playwright-core install chromium` で入れるか、手元の Chromium を
  環境変数 `CHROMIUM_PATH` で指す。VSCode は使わない。

- e2e はテスト用の VSCode（既定 1.138.0。`VSCODE_VERSION` で変更）を `.vscode-test/` に取得し、
  一時ディレクトリの中だけを使うポータブル状態で起動する（手元の VSCode の設定・拡張・`~/.vscode` には触れない）。
  一時ディレクトリは終わったら消す（`DIFF_REVIEW_E2E_KEEP=1` で残す）。
- 画面側の変更は、`../` の Python の unittest（`python3 -m unittest discover -s tests`）も回す。

## 既知の制約

- **VSCode 1.138.0（Linux 版）でしか確かめていない。** Windows 版・macOS 版は未確認。
- 正規形でない `.dreview`（改行が CRLF・手で整形したもの等）は、開いただけでは書き換えないが、**最初の編集で全体が
  正規形（LF・キー昇順）に置き換わる**。そのとき、記録のスキーマ（`../schema.md`）に無い項目（手で足したキー等）は
  落ち、書き手の無いコメントは `unknown` になる（HTML 版の「JSON を書き出す」と同じ。`diff_review.py` が書く記録には
  そうした項目は無い）。
- BOM 付きで保存された `.dreview` は、保存しても BOM が残りうる（文字コードは VSCode の設定が決める。`diff_review.py` は
  BOM を付けない）。
- HTML 版にしかない操作（別のファイルを開く・下書きを初期化・JSON のダウンロード）は出さない。ファイルは VSCode が
  扱うので、「元に戻す」「ファイルを元に戻す」「名前を付けて保存」を使う。「JSON を書き出す」はテキストのコピーだけ。
- 開いている間に外部でファイルが変わったときや元に戻したとき、**返信・編集の入力欄は閉じる**（書きかけは下書きとして
  残り、開き直すと戻る）。行やファイルへのコメントの入力欄は、差分が同じならそのまま残る（差分が変わると作り直す）。
- 画面のテーマが「自動」のとき、起動の一瞬だけ OS 側の配色が見えることがある。
- 同じ `.dreview` を分割して 2 つの画面で開いたときの振る舞い（片方の変更がもう片方に追従するか）は確かめていない。
- 画面での操作と、同じ瞬間の外部での書き換えが重なったときは、画面の操作を捨てて文書の内容で表示し直す（画面に知らせが出る）。
