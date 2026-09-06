# 並行作業（worktree）（`protocol.md`「1.5」の詳細）

> **読む条件**: ユーザーが `aidev worktree` で並行作業を始める / 並行作業中の work を触るとき。使わないなら読まなくてよい。
> 核となる規約と要約は `protocol.md`「1.5」。ここはその詳細を切り出したもの
> （工程ごとの読み込み量を抑えるため。`protocol.md`「0.」の付録一覧を参照）。


- **current は worktree ローカル**: `.aidev/current` は `.gitignore` 対象＝未追跡のため、各 worktree が独立した
  current を持ち、worktree 間で共有されない。よって **worktree 操作は main tree の `.aidev/current` を書き換えない（INV-1）**。
- **1 worktree = 1 branch = 1 work** を単位とする。`worktree add` は worktree 内に該当 slug の work が無ければ `new` を
  委譲し（add 内で new）、有れば current 設定のみ行う。
- **既存 work の継続は要コミット**: work 成果物（`works/*`）は追跡対象なので、別ブランチの worktree で継続するには
  その work がコミット済みでブランチに乗っている必要がある（未コミットの work フォルダは worktree に伝播しない）。
- **PJ 規約は並行作業でも変わらず適用される**: 共有ファイルへの波及や、検証を委譲せず主エージェントが行う
  義務といった PJ 固有の規約は AGENTS.md が正で、worktree 上でも同じに効く。
  - **backlog の消し込みも成果物と同じくブランチに乗る**。`.aidev/backlog/*.md` は追跡対象なので、
  worktree で `[x]` にしてもマージするまで main tree の `aidev status` は未着手のままに見える。
  `inflight` 列は worktree を横断して数えるので、着手中であることはそちらで分かる。
  **ただし deliver した時点で `inflight` から外れ、未マージなら `todo` に戻る**。
  選ぶ前の確認は `protocol-backlog.md` の `HELD`（行単位で答えられる）。
- **共有ファイルは `.aidev/config.yml` の `sharedFiles` に挙げておく**と、`worktree add` の完了時に
    CLI がその名前を挙げて警告する（未設定なら汎用文言）。例: `sharedFiles: [package.json, src/registry.ts]`。
  - CLI が名指しできるのは**そこに書かれた事実だけ**。「この work は委譲せず主エージェントが検証すべきか」
    のような判断は散文（AGENTS.md）の担当で、CLI には持たせない（`DESIGN.md`「2.6」の線引き）。
  - **宣言が実態から遅れていないかは `aidev doctor` が見る**（実在しない名前／多くのコミットが
    触っているのに未宣言、を WARN）。直すのは人間だが、古びていることは機械が言える。
- **いま重なっているファイルは `aidev worktree files` で見る**。`sharedFiles` は静的な宣言なので、
  「触らないファイルが警告され、触るファイルは警告されない」という反転が起きうる。
  `worktree files` は**未マージの worktree**の変更を突き合わせて、**2 本以上が触っているファイル**を出す。
  - **coding に入る前は `--planned`**（`tasks.md` の `対象:` を突き合わせる）。実差分は
    「もう書いた後」しか見えず、上流工程にいる間は**構造的に空になる**。衝突を避ける余地が
    あるのはその時間帯なので、そこでは**宣言**を見る（`対象:` は tasks の時点で揃っている）。
  - **deliver の前は実差分**（オプション無し）。「マージ順で相手を壊さないか」の判断に要る。
    重なっていること自体は禁止ではない（並行可否はユーザー判断）——見ずに進むことだけが問題。
  - **`doctor` と食い違ったら `worktree files` を採る**。`doctor` が見るのは履歴の頻度（過去の傾向）、
    `worktree files` は**いま未マージの差分**（目の前の事実）。いま重なっているものが履歴の閾値に
    届かないことは普通に起きる。
- **`.aidev/backlog/*.md` は並行 N 本なら必ず衝突する**。`verify` が deliver での消し込みを強制する以上、
  N 本すべてが同じファイルの近い行を書き換えるため（実マージで確認済み）。避けられないので
  **マージ時に手で解決する前提**で進める（消し込み行どうしは独立なので、両方を残せば正しい）。
  `.aidev/config.yml` も同じ性質を持つ（`smokeCommands` を足す等、PJ 全体の設定を機能追加 work の
  差分に同梱することになる）。こちらは行が独立とは限らないので、**触ったら deliver の PR 本文に書く**。

## ライフサイクルの終わり（撤去）

`add`（着手）→ 各工程 → deliver（コミット・PR）→ **マージ後に `rm`**。
**deliver は PR 作成で終わり、撤去はしない**——マージが人間の仕事である以上、その後の撤去も人間の判断を待つ
（`aidev-70-deliver`「6.」）。

```sh
aidev worktree rm <slug|path> [--force] [--delete-branch]
```

- **未コミット差分があれば既定で拒否**する（`--force` で強制）。ただし **未 push のコミットは検知しない**
  ——判定は `git status --porcelain`＝working tree だけを見るため。コミット済み・未 push で `--force` を
  打つと、その作業は失われる。**push 済みかは自分で確かめる**。
- **`--delete-branch` は `git branch -D`（強制削除）**。マージ前に打つとブランチごと消える。
  worktree だけ外してブランチを残すなら付けない。
- **main worktree は対象外**。slug が main worktree の basename に一致しても、明確な文言で拒否される。
- **撤去し忘れても壊れない**。残った worktree は `aidev worktree list` に出続けるだけで、
  main tree の状態には影響しない（INV-1）。急いで消す理由はない。
