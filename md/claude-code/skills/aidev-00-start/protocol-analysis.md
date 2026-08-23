# 導出できる指標と解釈（`protocol.md`「8」の詳細）

> **読む条件**: retro / insights で定量分析するとき。工程の実行中は読まなくてよい。
> 核となる規約と要約は `protocol.md`「8」。ここはその詳細を切り出したもの
> （工程ごとの読み込み量を抑えるため。`protocol.md`「0.」の付録一覧を参照）。


- **各工程の経過時間**：approved − 直近の start（待ち時間・中断を含む壁時計値）。
- **手戻り回数**：同一 phase の start が2回以上（review/test→coding ループ等）。
  ※差し戻しで coding を再開する際に `aidev event coding start` を記録しないと、この指標は手戻りを取りこぼす（「3.」差し戻し分岐）。
- **差し戻し回数**：sent_back の件数（工程別）。
- **リードタイム**：最初の start 〜 deliver の approved。
- **任意工程の使用**：research / design の start 有無。
- **アンカー的中率**：`1 − unplanned_lookups / tasks_anchored`（research/plan の位置特定がどれだけ当たったか）。
  低ければ research の問いが的外れ、常に 100% なら research が過剰——**任意工程の発火条件を調整する材料**になる。
- **規模あたりの手戻り**：手戻り回数 ÷（`insertions` + `deletions`）。tasks 数は粒度の癖でぶれるため、
  work 間を比較するときはこちらで正規化する。

> 注意: 経過時間は承認待ち・セッション中断を含む壁時計値であり、純粋な作業時間ではない。
> 品質傾向としては**手戻り回数**の方が示唆に富む（上流工程の弱さを示すため）。
> 経過時間を比較するときは `state.yml` の `mode` で**層別する**（interactive は人間の承認待ちが支配的で、
> 工程の重さをほとんど反映しない。比較が成立するのは autonomous 同士）。
