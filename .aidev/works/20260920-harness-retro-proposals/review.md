# レビュー記録: retro で出たハーネス改善提案 5 件を aidev に適用する

## ラウンド 1（2026-09-20・独立レビューに委譲）

- [must][conv:-] `aidev debug skip` が差し戻し 1 回（`maxSendBacks` 未到達）でも通り、一度記録すると以後その工程の WARN が永久に鳴らない（実測：skip の後に 4 回差し戻して計 5 回でも WARN 無し）。README と `protocol-debug.md` は「上限に達した差し戻しでも」と書いており、実装の受理範囲が文書より広い — 根拠: aidev-docs/bin/aidev:1839 / 対応: 修正済（上限未到達は拒否し、skip 時に刻んだ `sent_backs` を超えて増えたら鳴らし直す）
- [must][conv:-] ps1 の `Dbg-Skip` がどのテストからも一度も実行されない（新テストの `run_db` は sh 固定。パリティの debug ブロックに skip が無い）。`lint-docs.sh` の L1 は動詞（`debug`）しか突き合わせないので AC8 の根拠にならない（DESIGN「3.5」の偽の緑） — 根拠: aidev-docs/bin/test/run.sh:1983 / 対応: 修正済（パリティ列に skip を追加）
- [must][conv:-] ハーネス改修の 3 ゲートのうち (3) 実走記録が `flow-runs/` に無い。このままコミットすると L8 が NG になり AC7 が着地時に崩れる。tasks.md にもこのゲートのタスクが無い — 根拠: aidev-docs/bin/test/lint-docs.sh:778 / 対応: 修正済（T8 を足して 3 ゲートを通し、記録を同じコミットに載せる）
- [should][conv:-] 3 ゲートの (2) が `bin/README.md` だけで、概観 `aidev-docs/README.md` の「ループの上限」表が `aidev debug start` のままで新しい出口に触れていない — 根拠: aidev-docs/README.md:181 / 対応: 修正済
- [should][conv:-] `protocol-debug.md`「記録と検査」が `stage: start|report`・`debug status` の説明が「差し戻し数・デバッグ回数・要否」のままで、同じファイルの新設節と食い違う。sh の help ヘッダにも `skip` の使用法行が無く `--reason` 必須が読めない — 根拠: aidev-00-start/protocol-debug.md:98 / 対応: 修正済
- [should][conv:-] AC6 の追記が直下の既存条件（「共有モジュール・公開 API に触れたタスク」。モード非依存）と重複し、条件を 2 回定義して読み替える形になっている — 根拠: aidev-40-coding/SKILL.md:59 / 対応: 修正済（既存行に語を足す 1 箇所へ寄せた）
- [should][conv:-] AC5 の追記を protocol.md 本体に置いたが、除外規則は protocol.md:211 と付録 `protocol-analysis.md`:17 に既にあり、本文の在処が 3 箇所になった。新しいのは「素で grep すると混ざる」という読み方だけ — 根拠: aidev-00-start/protocol.md:379 / 対応: 修正済（retro / insights が読む `protocol-analysis.md` へ移した）
- [nit][conv:-] `BUDGET_TOTAL` の内訳コメントが実際の追加行数と 2 箇所ずれている（protocol.md は +7・protocol-debug.md は +13。合計 26 は一致） — 根拠: aidev-docs/bin/test/lint-docs.sh:425 / 対応: 修正済
- [nit][conv:-] `--reason` に改行を含めると `decisions.md` に偽の `## デバッグ D<n>` 見出しを書けて採番が飛ぶ（`debug report --root-cause` と同じ既存の穴。metrics.yml は壊れない） — 根拠: aidev-docs/bin/aidev:1850 / 対応: 修正済（改行を潰す。`report` 側も同じ扱いにする）
- [nit][conv:-] 抑止が工程ごとであることを固定するテストが無い（`dbg_skips` から phase 条件が落ちても緑のまま通る） — 根拠: aidev-docs/bin/test/run.sh:2069 / 対応: 修正済

## ラウンド 2（2026-09-20・独立レビューに委譲。範囲はラウンド1 の解消＋当該差分）

ラウンド1 の 10 件のうち 9 件は解消。must(2)（ps1 の `Dbg-Skip` がテストから一度も実行されない）は**部分的**で、
下の 1 件目として再指摘された。

- [must][conv:-] 追加した skip のパリティ検査が**偽の緑**。フィクスチャの `test-result.md` が空で `event test sent_back` が exit 2 になり、`debug skip` は sh/ps1 とも「上限に達していません」で die。両系とも `stage: skip` が 0 件のまま一致していた（ps1 の記録経路は依然テストで未実行＝AC8 の根拠が無い） — 根拠: aidev-docs/bin/test/run.sh:3552,3562 / 対応: 修正済（フィクスチャに生出力を入れ、`--phase` 省略の経路もパリティに追加）
- [must][conv:-] `--phase` 既定の**曖昧時メッセージが sh と ps1 で一致しない**（候補 0 件で sh は「なし 計 0 件」・候補 2 件以上で sh は最後の 1 工程しか出さない）。しかもパリティ検査は `--phase` を明示した 2 例だけで、省略経路は ps1 で未実行 — 根拠: aidev-docs/bin/aidev:1847-1852 / aidev.ps1:1657-1660 / 対応: 修正済（候補を全部並べる形にそろえ、省略経路をパリティに追加）
- [should][conv:-] 既定の候補集合が `verify` の WARN 条件と一致せず、**意図しない工程を選べる**（委譲済み・有効な skip 済みの工程も候補に入り、解決済みの工程に矛盾する記録を残せる／本当に省きたい工程が「複数」で弾かれる）。概観 README も裸の形を勧めたまま — 根拠: aidev-docs/bin/aidev:1848-1850 / aidev-docs/README.md:181 / 対応: 修正済（候補は「WARN が実際に鳴る工程」に限定。README も `--phase` 付きに）
- [nit][conv:-] 予算コメントの見出しが `3485 -> 3510` のままで `BUDGET_TOTAL=3513` と合わない — 根拠: test/lint-docs.sh:425 / 対応: 修正済
- [nit][conv:-] 改行の潰し方が sh（1 文字ずつ）と ps1（連続をまとめる）で違う — 根拠: aidev:1792-1793 / aidev.ps1:1601 / 対応: 修正済（sh も連続をまとめる形に）
- [nit][conv:-] 実走記録の 2 箇所が差分と合わない（「すべて一致」／`protocol.md` の増減の基準） — 根拠: test/flow-runs/2026-09-20-debug-skip-and-review-scope.md:28,39 / 対応: 修正済
- [範囲外・backlog] 作業ツリーが別ブランチで、無関係な `diff-review-html` の変更と同居している（着地時に分離が要る） / 対応: 利用者の判断で**別の worktree**に私の変更だけを載せる

## ラウンド 3（2026-09-20・修正の確認）

ラウンド2 の 6 件を反映し、テストで固定した。修正の途中でパリティが 1 件落ち、**テスト側の日時の正規化漏れ**と判明
（`・<日時>）` だけを落としていたので、skip の見出しの `（<日時>）` が sh/ps1 の実行時刻の差で必ず落ちる）。正規化を直した。

指摘なし。`sh test/run.sh` は **1129 passed / 0 failed / 0 skipped**、`lint-docs.sh` は 23 passed。

件数（ラウンド1〜3 の通算）：must 5・should 5・nit 6。
