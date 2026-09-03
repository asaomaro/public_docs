# 並行作業（worktree）（`protocol.md`「1.5」の詳細）

> **読む条件**: ユーザーが `aidev worktree` で並行作業を始める / 並行作業中の work を触るとき。使わないなら読まなくてよい。
> 核となる規約と要約は `protocol.md`「1.5」。ここはその詳細を切り出したもの
> （工程ごとの読み込み量を抑えるため。`protocol.md`「0.」の付録一覧を参照）。


複数の作業を**並行**で進めたいとき、ユーザーは `aidev worktree`（CLI。`bin/README.md` 参照）で work 専用の
git worktree＋`feature/<slug>` ブランチを作って隔離着手できる。ハーネスは並列化を自動判断せず、
**並列の要否はユーザーが明示 `aidev worktree add` で判断する**（人間オプトインの逸脱。既定は単一ワーキングツリーの直列）。

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
- **共有ファイルは `.aidev/config.yml` の `sharedFiles` に挙げておく**と、`worktree add` の完了時に
    CLI がその名前を挙げて警告する（未設定なら汎用文言）。例: `sharedFiles: [package.json, src/registry.ts]`。
  - CLI が名指しできるのは**そこに書かれた事実だけ**。「この work は委譲せず主エージェントが検証すべきか」
    のような判断は散文（AGENTS.md）の担当で、CLI には持たせない（`DESIGN.md`「2.6」の線引き）。

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
