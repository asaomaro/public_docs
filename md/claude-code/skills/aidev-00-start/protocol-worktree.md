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
- **規約**: worktree 上の作業が共有ファイル（`package.json` contributes・`fileScope.ts`・言語登録）に及ぶ場合の
  languageId 波及（AGENTS.md）と、原典照合の主エージェント実施義務は、並行作業でも変わらず適用される
  （`worktree add` 完了時に CLI が注意を出力する）。
