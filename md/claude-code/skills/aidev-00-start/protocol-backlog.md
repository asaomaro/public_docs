# 台帳の同期（backlog 出自の消し込み）（`protocol.md`「2.9」の詳細）

> **読む条件**: `aidev-00-start` で backlog 項目を選ぶとき / deliver で消し込むとき / doctor の backlog 検査を読むとき。
> 核となる規約と要約は `protocol.md`「2.9」。ここはその詳細を切り出したもの
> （工程ごとの読み込み量を抑えるため。`protocol.md`「0.」の付録一覧を参照）。


backlog は**遅延キュー**で、作業が完了したらその行を閉じるのは deliver の責務
（`DESIGN.md`「2.5」: 流れは backlog → works（consume）。**backlog 行は deliver で `[x]`**）。

- **記録は両入口で刻む**: `aidev new <slug> --backlog <file>` で `state.yml` に出自を残す（「6.」）。
  直接入口（`aidev-00-start` で選ぶ）はもちろん、**batch 経由でも省略しない**——batch は自分で `[x]` に
  するので一見不要だが、**途中で切れると刻印が無く、後続セッションは backlog 由来だと知る手段が無い**。
- **着手中は backlog から見えない**: 行が `[x]` になるのは deliver なので、着手から着地までの間、
  掴まれた項目と素の未着手を区別できない。`aidev status` の **`inflight` 列**がそこを埋める。
  **選ぶ前に必ず見る**（閉じ忘れると次の人が完了済みの項目を選ぶ。過去に実際に発生）。
- **強制**: `backlog:` を持つ work は、**その backlog ファイルに自分の slug が現れないと
  `aidev verify` が FAIL する**（deliver の着地前ゲートで弾かれる）。
- **消し込みの書き方**は `aidev-70-deliver`「3.5」（根拠 3 点セット／取り消し線／部分完了は兄弟で割る）。
- **ファイル自身の一生は `aidev doctor` が見る**（`verify` は work にぶら下がる検査なので、退避・
  `kind` frontmatter・項目の書式というファイル側の話は持ち主の work がいない）。検知するのは
  退避漏れ／`kind` の欠落・誤記／`status` が数えない書式／`archive/` に残った未消化。**WARN 止まり**。
- **積む・退避するも CLI にある**（`aidev backlog new --kind …` / `archive`。判定は doctor と同一関数）。
  **検査だけあって実行が無い**状態を作らないため。消し込み本体だけは判断が要るので散文に残す。
- 刻印の無い work は検査しないが、**結果的に閉じた項目があれば deliver で反映する**のは同じ。
