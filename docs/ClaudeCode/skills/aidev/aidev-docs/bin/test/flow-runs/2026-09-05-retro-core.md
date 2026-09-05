---
date: 2026-09-05
change: 他 PJ（agents-control-center / core）の retro 7 件の検証と反映。smokeStaleAfter の基準日判定 / metrics の work_sec / new の autonomous note / doctor の 3 検査追加
---

## 1. 文書は実態に追いついているか

実走が指摘文の穴を 3 件出し、すべて直した。

| 直したもの | 何が起きていたか |
|---|---|
| `protocol.md` の smoke 節 | `smokeCommand`（**単数形だけ**）を挙げ、複数形に触れていなかった。protocol だけ読んで config を触ると単数キーを足しにいく |
| `aidev-20-spec` / `-30-plan` / `-40-coding` / `-50-test` / `-60-review` の手順1 | **`aidev event <phase> start` が書かれていない**（`-10-requirement` と `-70-deliver` にはある）。工程 skill 単独起動だと落とす。実走では `aidev guard` の「→ 忘れずに」に救われていた＝**CLI の 1 行が散文の穴を埋めていた** |
| `doccheck start` の出力 | 「`report` は**直す前に**打つ」が `protocol-check.md` にしかなかった。知らないと必ず間違える順序なので CLI の出力にも置いた |

**撤回した自分の変更が 1 件**: doccheck の WARN を schema を問わず出す、を一度入れたが戻した。
報告元が改訂版で「その時点のハーネスに機能が無かっただけで規約違反ではない」と訂正してきたため。
**承認済みの工程に後から点検は掛けられない**ので、旧 work では永久に鳴って直せない
——またがり検知を `note:` に落としたのと同じ判断（直せない事実を混ぜると直せる WARN が埋もれる）。

## 2. README のメンテナンス

- `bin/README.md`: `metrics` の `work_sec` 列（`lead_sec` との読み分けと、区間の重なりを潰していない限界）、
  `doctor` の検査順を 7 節 → 9 節へ、smoke 節の孤児行検査。
- `aidev-docs/README.md`: `doctor` が導入の自己診断も兼ねること（`.aidev/current` の追跡・孤児行・またがり検知の可否）。

## 3. 実走（サブエージェント）

テスト PJ を新規に起こし、`--mode autonomous` で requirement → deliver を 1 本
（上流3工程で `doccheck` 5 ラウンド 9 件、coding で `taskcheck` 4 タスク 6 件）。

**この改修で私が作り込んだ致命バグを捕まえた。**

| # | 何が起きたか | なぜテストで出なかったか |
|---|---|---|
| D-1 | **`aidev doctor` が exit 2 でクラッシュ**（`_sscut0: parameter not set`）。`set -u` の下でループ内初回に未初期化変数を参照していた。落ちる条件は「smoke 宣言を編集してまだコミットしていない」＝**`aidev-50-test`「3.2」が作れと指示している当の状態**で、規約に素直に従うと doctor が壊れる区間ができていた。一時ファイルも `.aidev` 内に残り、deliver の `git add -A` が拾いかけた | `smoke_stale_warn` に**テストが 1 本も無かった**（この関数は直前の retro 指摘で書き直した新しいコード。書き直しにテストが付かなかった）。ps1 は最初から両方初期化しており、**ここでも sh だけが落ちた** |
| D-2 | `smokeCommands:` ブロックの**外**に書いた `- ` 行が**警告なしで無視される**。`smoke` は pass、`doctor` は `configured=yes` と言うだけ。「足した表面を一度も起動しないまま pass」という、この機能が塞ぐために作られた事故が、設定の書き間違いという別の入口から再現する | 正しい書き方でしかテストしていなかった |
| D-3 | `.aidev/current` が git に追跡されていても誰も言わない。worktree 機能は current が worktree ローカルであることに乗っている（DESIGN「INV-1」）のに、deliver 手順の `git add -A` がそれを壊しにいく | 導入手順は散文にあるが、守られているかを見る機械が無かった |

D-1 は修正し、`smoke_stale_warn` の回帰テストを追加した（宣言を育てたら WARN が消えること・未コミット編集で落ちないこと）。
D-2 / D-3 は `doctor` の検査として追加した。

**残した指摘**: `metrics --format tsv` にヘッダが無い（列の増減で下流が静かにずれる。ただし
既存の消費者を壊すので、`status` 系と揃える形の変更は別途）。`work_sec` が区間の重なりを潰さない
（原理上 `work_sec > lead_sec` がありうる。今回は 880 ≦ 969 で発生せず。限界として README に明記）。
`task_checks` が「独立したコンテキストの数」ではなく「report したタスクの数」を数えている件は、
**メトリクスを変えずに規約側で閉じた**——`protocol-check.md`「(b)」に「1 委譲 = 1 タスク」を明記した。

調べると、定義済みの指標（`protocol.md:457` の「行ったタスク数」、`protocol-analysis.md:28` の
「1 タスクあたり何件」、`DESIGN.md:408` の分母の議論）は**すべて per-task で、実装と一致している**。
`start` も毎回「渡すもの: そのタスクの差分だけ」と出しており、**1 委譲 1 タスクが元々の前提**。
報告例のバッチ（1 体が T6+T7 を見た）はその前提を破ったもので、規約どおりなら
`task_checks` = コンテキスト数が構造的に成立する。`task_check_contexts` を足す案は、
イベントの `task:` 照合（上限判定・対ゲート・status・totals が全部依存）を壊すうえ、
結局「まとめたら 1 回の start にする」という人手の規律に戻るので採らなかった。
**バッチが常態化していると実測できたら再検討する**（母集団 1 work では足りない、という
報告元自身の保留基準に合わせた）。

> この 1 行は上の実走の**後**に足したもので、実走がカバーした範囲（taskcheck）の中の
> 規約明確化に留まるため、再実走はしていない。
