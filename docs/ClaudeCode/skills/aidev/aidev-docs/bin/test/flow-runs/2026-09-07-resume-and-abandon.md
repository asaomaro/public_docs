---
date: 2026-09-07
change: 差し戻し理由の機械検査と work の廃止状態を足し、実走2本が見つけた must 5 件・should 16 件を潰す
---

## 1. 文書は実態に追いついているか

### 何を作ったか（対話で確認した仕様の穴 2 件）

| | 穴 | 対応 |
|---|---|---|
| **差し戻しの理由** | `verify` が `review.md` / `test-result.md` を見るのは**承認時**なので、「差し戻しを記録 → 書く前にセッションが切れる」と理由が永久に失われる（metrics に残るのは工程と時刻だけ）。順序は `aidev-60-review` 手順3→4 の**散文**だけで、破っても何も起きなかった | `aidev event <工程> sent_back` が記録の直前に「**このラウンドで**印が増えたか」を検査し、無ければ exit 2 |
| **work の廃止** | 完了は `deliver ∈ approved` の**導出**で表せるが、**やめた判断**を書く場所が無く、中止した work は `done: no` のまま一覧に残り `doctor` も評価を続けていた（畳む手段は backlog 側の `archive` にしかなかった） | `state.yml` に `status: abandoned` ＋ `abandonedReason`、`aidev abandon --reason` / `--undo`、`status` / `doctor` の既定表示から除外 |

**新セッションからの再開**（同じ対話で確認した 3 点目）は**対応不要**だった——`aidev status` の WORKS 表に
`current` 列が既にあり、`aidev-00-start`「2.」も読み方を書いている。ただし実走が
「差し戻し直後は親行の `current` が実際に手を動かす位置を指さない」と実測したので、
**表の下に `cursor:` 行**（`.aidev/current` が指す work とその工程）を足した。

### 実走が見つけた must（5 件）

両実走が**独立に同じものを 3 件**挙げた。偶然ではなく構造的な穴だったことの傍証になる。

1. **`event` / `approve` が未知の引数を黙って metrics キーに変えていた**（既存）。
   `aidev approve review --slug foo` が exit 0 で通り、`.aidev/current` の**別 work** が承認され、
   `metrics: { --slug: --slug, foo: foo }` という行が残った。`guard` は余分な引数を弾くのに、
   **実際に state と metrics を書く側だけ素通し**。自由文の `, { }` でフロー形式が壊れることも実測された
   （`debug report` と `abandon --reason` は既に同じ理由で弾いていた＝危険は認識済みだった）。
2. **廃止した work が引き続き完全に操作できた**（新機能）。`abandon` が `.aidev/current` を動かさず、
   `guard` / `event` / `approve` も `status` を見ていなかったので、**「一覧に出ないのに作業は進む」**。
   廃止機能が一番避けたい組み合わせを、その機能自身が作っていた。
3. **`--undo` が `abandonedReason` を残し、metrics に何も刻まなかった**（新機能）。`active` が理由を持つのは
   スキーマ外で、`event: abandoned` だけが残るとイベントログが「やめたまま」と嘘をつく。
4. **`verify` の生出力 WARN が `by: unapprove` を除外していなかった**（既存）。統合 review から子へ
   差し戻すと**子では一度も test が落ちていない**のに WARN が出て、書いてある解消法に従うと親の出力を
   子へ写すことになり「捏造しない」と衝突する——**消せない WARN**。
5. **エラーが存在しないコマンドを案内していた**（このラウンドで入れた）。`一覧は aidev list` の `list` は
   無い。`resolve_work` 経由なので全経路に出て、**まさに `--undo` したい場面で刺さる**
   （廃止 work は既定 status に出ないので探せない）。

### 検査そのものが空振りしていた（should のうち最も重い）

追加した理由検査は「中身の有無」しか見ておらず、**2 ラウンド目以降は素通り**した——前ラウンドの
指摘行が残っているから。さらに test 側は `aidev-50-test` のテンプレが smoke の生出力に ``` を要求するので、
**「失敗が発生していない」と書いた文書でも常に通る実質 no-op** だった（手順どおり歩いた人ほど素通りする）。

バイト数ではなく**「印」の数**（review＝`must`/`should` 行数 / test＝フェンス行数）を
`event <工程> start` 時点と比べる形に変えて両方塞いだ。`nit` を数えないのは、`aidev-60-review` が
「指摘なし（または nit のみ）→ 終了」と定めているため——ゲートの語彙に `nit` が入っていたのが誤り。

### そのほかの should（実走の指摘・全件対応）

- light で `guard design` が通り、しかも `event design start` を**打つよう促していた**（散文だけの規約）
- 統合 review の差し戻し手順が 2 つの箇条書きに割れ、**正典側に親の `unapprove test` が無かった**
- `metrics --all` に廃止が出ず `insights` が「進行中」と数える → `delivered` 列を `state` 3 値に
- 廃止の理由を機械で読む口が無い（`aidev-00-start` は「status で機械抽出する」と定めているのに、
  廃止だけがその原則の外だった）→ `status --all` に `ABANDONED` 節
- review はインデントを許すのに test は桁 0 必須という非対称（`cv_count_tags` はインデント可）
- 非表示件数の内訳が出ない（`doctor` は `廃止(検査対象外)=N` と分けている）
- README 3 箇所の `--active` 説明と WORKS 表の凡例が旧仕様のまま

### 検査を書いた場所こそ、その検査の対象

**L13（二重引用符の中の生の逆引用符）を足した数コミット後に、追加したテストのアサート
メッセージで同じ間違いをした**。`sh -n` が「Unterminated quoted string」で落ちて初めて分かった
——L13 は `bin/aidev` しか見ておらず、`run.sh` を見ていなかったから。

走査対象を `run.sh` と `lint-docs.sh` 自身にも広げ、併せてヒアドキュメントと行をまたぐ単一引用符を
正しく扱うようにした（どちらも誤検知として出ていた）。両ファイルに欠陥を戻して捕捉を確認済み。

**一般則として残す**: 検査を足したら、**その検査を書いたファイル自身**を対象に含める。
書いた直後の自分が最初の違反者になる。

## 2. README のメンテナンス

- `aidev-docs/README.md`（概観）: 「中断と再開」に `cursor:` 行・`--all`・差し戻しは理由を先に書く・
  **やめる（`abandon`）**を追加。
- `aidev-docs/bin/README.md`: `status` 行を新仕様に（既定が隠す / `--all` / `state` 3 値 / `cursor:` 行 /
  `ABANDONED` 節）、`abandon` 行を新設、`guard` の light 拒否、`verify` の `by: unapprove` 除外、
  `taskcheck` の `task_check_mode`、lint の表に **L10〜L13** を追加。
- `aidev-00-start/SKILL.md`: WORKS 表の凡例を `state` 列に、コマンド例を `--all` に、
  **やめた work を探す導線**（`status --all` の `ABANDONED` 節と `--undo`）を追加。

## 3. 実走（サブエージェント）

**履歴つき `git clone`** で 2 本。どちらもハーネス側 `git status --porcelain` が空、
テスト PJ の skills コピーも `diff -r` で原本と一致することを実走自身が確認済み。

- **E: 単一 work**（`full` / `interactive`、test 1 回・review 2 回を**実際に失敗させて**差し戻し）。
  17 件報告。**書いてあるとおりの順序で歩いたとき、新しい exit 2 は一度も邪魔にならなかった**
  ——問題は逆で、その順序で歩くと検査が空振りすることだった（上記）。
  順序を破ったときのメッセージは「書式・打ち直す順序・出典がそろっていて次の一手が読める」と評価。
- **F: 分割 work（親＋子 2 本）/ light / 途中でやめる work** の 3 本。15 件報告。
  統合 review から子への差し戻しで**子に消せない WARN が出ないこと**を、子の `test-result.md` から
  フェンスを全部落として確認（`verify --strict` exit 0）。light の 4 つの硬ゲートも期待どおり。

`abandon` の拒否メッセージ 5 種（理由必須 / deliver 済み / 二重廃止 / 廃止していない work への `--undo` /
カンマ）は「**メッセージだけで次の一手が読める**」、特に二重廃止の文言が `--undo` を名指ししているのが
`--undo` への最短導線になっている、との評価。

**残す既知の穴**: Windows PowerShell 5.1 の経路は CI でのみ検証される（ここでは pwsh 7.4.6 で skip=0）。
