---
date: 2026-09-06
change: 他 PJ の retro（20260905-host.md）の 6 提案を検証し、採る 4 件を実装（taskcheck/doccheck の未報告検知、doccheck の「直す前に report」観測点、deliver の remote=none 刻印）
---

## 1. 文書は実態に追いついているか

`lint-docs.sh` は L1〜L8 すべて pass（18/18）。中身の追随は以下を手で直した。

- `protocol.md`「8.」: `task_checks` の定義を「**report まで届いた**タスク数。start だけは数えない」に。
  同じ節に `deliver` の `remote` を追加。
- `protocol.md`「運用方針」: **CLI の実体パス**を明記（+2 行、予算を 3410→3412 に引き上げ）。
  各 skill のコマンド例は裸の `aidev` で、PATH は誰も通していない。同じ節が明示的に許している
  「`aidev-00-start` を読まずに工程 skill を直接叩く」経路では、最初のコマンドで止まっていた（実走で実測）。
- `protocol-check.md`「(b)」: `report` のタイミング、断念時に `decisions.md` へ**タスク ID／工程名を含む
  1行**を残すこと（残せば未報告の名指しが消える）。
- `protocol-autonomous.md`「独立点検」: 「`--strict` で落ちる」を**上流4文書の欠落だけ**に限定。
  taskcheck の未報告は WARN 止まりなので、散文が両者を同列に書いていたのは誤り（実走が指摘）。
- `aidev-15-research` / `aidev-25-design` / `aidev-65-walkthrough` の手順 1 に
  `aidev event <工程> start` を追加（**行を増やさず**既存の guard 行を書き換えた）。
- `DESIGN.md`「3.5」に、この回の G を 2 件記録（対称性を半分だけ直す型／認めた出口に消し方を用意する）。

## 2. README のメンテナンス

- `bin/README.md`: `taskcheck` 行（数えるのは report まで届いたタスクだけ・`unreported` 列・
  判定式は `report < start`・`decisions.md` で消える）、`doccheck` 行（未報告検知の対称化・
  `at_max` は start の数で見る・size 比較は plan では `plan.md` と `tasks.md` の合計）、
  `approve` 行（deliver の `remote=none` 自動刻印）、`verify` の不変条件一覧（schema を問わない WARN）。
- `aidev-docs/README.md`: 「上限を数えるのは `start`、『点検した』を数えるのは `report`」の役割分担と、
  未報告の名指し・`decisions.md` での消し方。

## 3. 実走（サブエージェント）

テスト PJ `hostpj`（`envx` CLI・`--mode autonomous`・`profile full`）で
requirement → spec → plan → coding → test → review → deliver を 1 本通し、
`design` の追加プローブ 7 本を別コピーで実施。`.claude/skills/` は未変更を確認済み（`git diff` で検証）。

**検証できたこと（依頼どおり動いた）**

- 未報告の `start` は `taskcheck status` の `unreported` 列・`note:`・`verify` の WARN で名指しされ、
  `task_checks` に数えられない（`start` 3 本・`report` 2 本で `tasks=2`）。`report` を打てば静かになる。
- `doccheck report` を直したあとに打つと `note:` が出る（`4629→5139 バイト`）。正しい順では鳴らない。
- `approve deliver` が `remote: none` を自動で刻む（手で渡していない）。

**見つかった欠陥（10 件の報告のうち、実装を直したもの）**

| # | 欠陥 | 直し方 |
|---|---|---|
| ① | `doccheck` の size 比較が plan の `tasks.md` に効かない（`AC:` 行はそこにしかないのに） | `dc_size()` を足し、plan は `plan.md` と `tasks.md` の合計を刻む |
| ② | `doccheck` に未報告の検知が**一切**無い（`taskcheck` と非対称） | `dc_unreported()` を足し、`status` の `note:` と `verify` の WARN を `taskcheck` と**同じ関数・同じ文言**に |
| ③ | `taskcheck` の `unreported` に定義が 2 つ（表は `report < start`、`verify` は `report == 0`） | 判定を `report < start` に統一。ラウンド粒度の断念が網から落ちていた |
| ③' | 規約どおり断念しても WARN を消す手段が「規約が禁じている `report` を打つ」しか無い | `decisions.md` に ID／工程名を含む行があれば消える（`ck_recorded()`） |
| ④ | `doccheck status` の `at_max` を `report` 数で判定していた | `start` 数で判定（「まだ余裕がある」と出したそばから `exit 4` になる） |
| ⑤ | 任意3工程の SKILL.md に `event <工程> start` が無く、手順どおりに打つと `verify --strict` が exit 5 | 3 ファイルの手順 1 を書き換え（上記「1.」） |
| ⑥ | `taskcheck start` の使用法が `[--mode …]`（任意に読める）なのに実装は必須 | 角括弧を外した。`doccheck` 側と `help` は元から正しい |
| ⑦ | 工程 skill を直接叩くと CLI が見つからない | `protocol.md`「運用方針」に実体パス（上記「1.」） |
| ⑧ | remote 無しで作業ブランチに着地すると `doctor` が毎回 WARN（規約に従うほど鳴る） | WARN に「人を待っている状態ならこれが正常。マージ後に戻すこと」を 1 行足した |

**採らなかった報告**

- ⑨「`aidev smoke` は読み取り専用ではない（deliver 後にも刻む）」——**一度止めてテストが 3 本落ちた**。
  `verify` は smoke が失敗のままなら deliver 済でも FAIL し、**それを解く唯一の手段が
  「直して smoke を打ち直す」**。事後の追記を止めると、失敗したまま着地した work を直す経路が消える。
  追記が測定を動かす懸念は本物だが、対価が「直せない FAIL」では釣り合わない。元に戻し、理由をコードに残した。
- ⑩「size 比較は同じバイト数の書き換えを見逃す」——設計上の割り切りとして `bin/aidev` のコメントに
  既に明記済み。だから `note:` 止まりで exit code を変えていない。
- retro の提案2（`--mutations` の自己申告）——観測点の無い自己申告は、このハーネスが取り除いてきた
  失敗の型そのもの。採らない。

**テスト**: 862 pass / 0 fail / 0 skip（pwsh 7.4.6・gawk・mawk の 3 通りで一致）。
新規アサート 16 本（sh 10・ps1 パリティ 6）。ps1 パリティは**ここが唯一の検査**なので、
①②③' を 3 通りとも ps1 側に置いた。
