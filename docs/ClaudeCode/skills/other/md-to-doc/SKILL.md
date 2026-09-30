---
name: md-to-doc
description: Markdown を、視覚的に分かりやすく図表を活用した単一HTMLドキュメントに変換する。固定ヘッダー・見出しメニュー・目次（開閉トグル/検索/章アコーディオン付き）・コールアウト・コードコピー・印刷/PDF対応を備え、11 のデザインテーマから選べる。ヘッダーの切替ボタンで ライト/ダーク/システム設定 に追従。mermaid 図はテーマ配色でSVG化（環境が無い場合は内容を解釈して手描きSVGでフォールバック）。説明図の要所をモーショングラフィックスで動かすこともできる（スクロールで再生・再生し直し・動きを減らす設定と印刷では静止）。「mdをHTMLにして」「資料用のHTMLを作って」「このメモを綺麗なドキュメントに」「htmlドキュメント生成」などと言われたときに使用する。
---

# md-to-doc — Markdown → 視覚的HTMLドキュメント生成

Markdown を、配布しやすい**単一HTML**（外部依存なし）に変換する。
変換は同梱の `generate.py`（Python3 / stdlib のみ）が行う。

## 表示モード（ライト / ダーク / システム設定）

全テーマがライト・ダーク両方のパレットを持ち、ヘッダー右端の切替ボタン（`☀ / ☾ / ◐`）で
**ライト / ダーク / システム設定に追従** を選べる。選択は `localStorage` に保存され、次回も維持される。
初回表示の既定は `darktech` のみ `dark`、他テーマは `system`（OS設定に追従）。`--default-mode` で変更できる。

> [!IMPORTANT]
> このため、**あなた（Claude）が書き足すHTML/SVGの色は必ず CSS 変数で指定する**。
> `var(--accent)` `var(--ink)` `var(--card)` `var(--a0)`〜`var(--aN)`（循環配色）、
> アクセント色の上に載る文字は `var(--on-accent)`。
> hex を直書きすると切替に追従せず、ダークモードで判読できなくなる。

## 重要: 実行時は必ず「順番に選択」させる

ユーザーに **テーマ → 出力モード** の順で `AskUserQuestion` を使って選ばせてから生成する。
引数で明示指定がある場合のみ確認を省略してよい。

### `AskUserQuestion` の上限と、それに対する運用ルール（必守）

`AskUserQuestion` には **1問あたり選択肢 4つまで / 1回の呼び出しで 4問まで** という上限がある
（「その他」は自動で付くので、明示する選択肢は最大 4つ）。
本スキルには選択肢が 4 つを超える項目（**テーマ 11 種**・**レイアウト 5 種**）があり、そのまま並べると入り切らない。
そこで以下を必ず守る。

1. **4 つを超える項目は、`AskUserQuestion` を呼ぶ直前に本文テキストへ全件の一覧表を必ず出す。**
   質問の選択肢に載らないものも、ユーザーの目には必ず触れさせる。落として黙るのは禁止。
2. **選択肢の並べ方は項目ごとに次のとおり**。

| 項目 | 選択肢に並べるもの | 「その他」側（一覧表に明記して誘導） |
|---|---|---|
| テーマ | **md の内容に合う 3 件（Claude が選ぶ。1 件目に「（おすすめ）」）＋ `corporate`**。`corporate` が 3 件に入っていれば 4 件目は次点 | 残りすべて（キーを入力してもらう） |
| レイアウト | `plain` / `cards` / `timeline` / `accordion`（固定） | `freeform`（完全フリーフォーム） |

3. **質問は 2 回の呼び出しに分ける**（1回 4問の上限、および 3d が 3c の回答に依存するため）。

   - **1回目（4問）**: 1. テーマ / 2. 出力モード / 3b. 目次 / 3c. レイアウト
   - **2回目（2〜4問）**: 3. 図解 / 3d. 構築（3c が `plain|cards|timeline|accordion` のときだけ）/
     3e. 画像（対象 md にローカル画像リンクがあるときだけ）/ 3g. 動き（出力モードが `print` のときは聞かない）

---

## 手順

### 0. 入力 Markdown を特定
- 会話やコマンド引数に対象 `.md` があればそれを使う。
- 不明なら、どのファイル（複数可）を変換するかユーザーに確認する。

### 1. テーマを選ばせる（1問目）
テーマは **11 種**、`AskUserQuestion` の選択肢上限は 4 つ。md の内容に合う候補を出し、全件の表も必ず見せる。

**(a) 呼び出し直前に、本文テキストへ全件の表を出す**（省略禁止）。表は次で出せる:

```bash
python3 <skill_dir>/generate.py --list-themes
```

| キー | 名前 | 性格 | 向く文書 |
|---|---|---|---|
| `corporate` | モダンコーポレート | 青基調・カード・万人向け | 資料・報告・社内共有の既定 |
| `darktech` | ダークテック | 暗背景＋シアン/パープル | エンジニア向けの技術資料 |
| `infographic` | インフォグラフィック | カラフル・丸ゴシック | インパクト重視の紹介・広報 |
| `editorial` | エディトリアル | 明朝・余白・読み物風 | コラム・解説・読み物 |
| `pastel` | やわらかパステル | 丸み・淡色 | 社内の親しみやすい共有 |
| `formal` | フォーマル | 白と墨＋紺・罫線・見出しに 1. / 1.1 の番号 | 報告書・稟議・規程・提案書（印刷が最も整う） |
| `manual` | マニュアル | 灰色の地＋オレンジ・詰めた組み・見出しに番号の札 | 手順書・運用手順・トラブル対応 |
| `contrast` | 高コントラスト | 大きな文字・高コントラスト・太い下線のリンク | 社外公開・全社向け・読みやすさ最優先 |
| `blueprint` | ブループリント | 方眼の地に紺・等幅の見出し・製図風の図枠 | 設計書・仕様書・アーキテクチャ説明 |
| `minimal` | ミニマル | 黒い文字と余白・細い罫線・影なし | 社内メモ・議事録・ナレッジ |
| `paper` | 紙（セピア） | 生成りの紙色・焦げ茶・広い行間 | 長文の読み物・解説・研修資料 |

表の直後に「**選択肢に無いテーマは「その他」にキー（例: `blueprint`）を入力してください**」と添える。

**(b) 質問の選択肢（header 例: 「テーマ」）は、md の内容に合う 3 件＋`corporate`**。
- md を軽く読み、表の「向く文書」に照らして 3 件選ぶ（例: 手順書→`manual`、設計書→`blueprint`、稟議→`formal`、
  議事録→`minimal`、長い解説→`paper`、社外公開→`contrast`）。1 件目の label に「（おすすめ）」を付ける。
- 4 件目は迷ったときの既定として `corporate` を置く（3 件に入っていれば次点を置く）。
- 全テーマがライト/ダーク両パレットを持つので、「暗くしたい」だけの要望に `darktech` を勧める必要はない
  （`--default-mode dark` で足りる）。
- 読み手はヘッダーの「Aa」から書体と文字の大きさを変えられる（テーマの選択とは別）。

### 2. 出力モードを選ばせる（2問目）
`AskUserQuestion`（header 例: 「出力モード」）。

- **単一HTML**（`single`）— 1ファイル完結。メール添付/USB配布に最適（既定・推奨）。
- **印刷/PDF重視**（`print`）— 画面より紙・PDF配布を主目的に、改ページ・余白を最適化。
- **複数md→サイト化**（`site`）— 複数ファイルを束ね、一覧 `index.html` を生成して相互リンク。
  ※入力が1ファイルなら `single` を勧める。

### 3. 図解の自動補完を選ばせる（3問目）
`AskUserQuestion`（header 例: 「図解」）。mermaid で書かれていない内容でも、
**あなた（Claude）が図解した方が分かりやすい箇所を判断して図にするか**を選ばせる。

- **しない**（`off`）— 本文そのまま。図は mermaid ブロックのみ（既定）。
- **控えめに補う**（`light`）— 各ドキュメントで最も効果的な1〜2個だけ図解。
- **積極的に図解**（`rich`）— 図にできる箇所は積極的に図解。

### 3b. 目次の出し方を選ばせる
`AskUserQuestion`（header 例: 「目次」）。ヘッダーメニューと左サイド目次が重複しないよう選ばせる。

- **左サイドに目次**（`sidebar`）— 本文左に目次。ヘッダーはブランド名のみ（既定・推奨）。狭い画面ではハンバーガーで目次を表示。
  ヘッダー左端のトグルで**サイドメニューの展開/非表示を切替**でき、目次上部の検索欄で見出しを絞り込める。章（`##`）ごとにアコーディオンで開閉可（いずれも初期状態は展開）。
- **ヘッダーメニュー**（`menu`）— 上部固定メニューのみ。本文は全幅。
- **両方**（`both`）— ヘッダーメニュー＋左サイド目次（情報量重視）。
- **目次なし**（`none`）— どちらも出さない。

### 3c. リストの見せ方（レイアウト）の【既定値】を選ばせる
`AskUserQuestion`（header 例: 「レイアウト」）。各セクション直下のトップレベル箇条書きの描画方法。

> [!IMPORTANT]
> **レイアウトは文書全体で画一に決まるものではない。**
> 「導入手順はタイムライン、機能一覧はカード、補足は素の箇条書き」のように、
> 同じドキュメント内でセクションごとに変えるのが自然。
> ここで聞くのは **`--layout`＝どのセクション別指定も無い節に適用される既定値**であって、
> 全節をこれで塗るという意味ではない。セクション別の割り当ては **3f** で仕分ける。
> `design=ai` を選ぶ場合はスクリプト側が節ごとに選ばせる指示を出すので、ここの回答は
> 「迷ったときの寄せ先（基調テイスト）」にすぎない。
> 3f で使う追加のレイアウト（`tabs`・`checklist`・`defs`・`stats`・`chips`・`tree`・`proscons`・
> 節の見せ方の `walkthrough`・`summary`）は既定値としては聞かない。節の中身で決まるので 3f で割り当てる。

レイアウトは **5 つあるので選択肢には 4 つしか載らない**。テーマの表と同じ本文テキスト内に、
5 件すべてを列挙してから聞く（`freeform` を落として黙るのは禁止）。

**質問の選択肢はこの 4 件で固定。**

- **箇条書き**（`plain`）— 通常のリスト（既定）。
- **カード**（`cards`）— トップレベル項目をカードグリッドに。各項目＋その小項目が1枚のカード。一覧性・見栄え重視。
- **タイムライン**（`timeline`）— 番号付きの縦タイムライン。手順・工程・時系列向き。
- **アコーディオン**（`accordion`）— 折りたたみ。項目が多く詳細を隠したいとき向き（先頭だけ開く）。

**「その他」側**（一覧に明記して誘導する 1 件）:

- **完全フリーフォーム**（`freeform`）— 形式に縛られず、**あなた（Claude）が内容ごとに自由にデザイン**する。
  選ぶ場合は「その他」に `freeform` と入力してもらう。`freeform` は**文書全体のモード**なので、
  セクション単位には指定できない（3f の仕分けも不要になる）。

### 3d. 構築方法（design）を選ばせる
`AskUserQuestion`（header 例: 「構築」）。3c で `plain`/`cards`/`timeline`/`accordion` を選んだ場合に聞く。

- **決定論的**（`deterministic`）— スクリプトが選んだ形式に型変換。**同じ入力→同じ出力**（既定）。
- **AIがこのテイストで構築**（`ai`）— Claude が**セクションごとに内容を読んで部品を選び**、作り込む（アイコン/タグ/色/数値強調などで手作りサンプル相当の質に）。3c の回答は「迷ったときの寄せ先」として使われるだけで、全節に適用する指定ではない。再現性より表現力。

> `freeform` を選んだ場合は常に AI 構築（`design=ai` 相当）。`plain/cards/timeline/accordion` × `deterministic/ai` の組合せで、「同じ形式でも決定論的かAI作り込みか」を選べる。
> 質問のまとめ方は「`AskUserQuestion` の上限と、それに対する運用ルール」の 3. に従う。
> 3d は 3c の回答に依存するので、**1回目の呼び出しに混ぜてはならない**（1回目: 1・2・3b・3c／2回目: 3・3d・3e）。
> 補足: `cards`/`timeline` は「番号付き手順」セクションと相性が良い。auto-figure と併用する場合、
> 同じセクションで「リストのカード化」と「図の差し込み」が重複しないよう、必要なら一方に寄せる。

### 3e. 画像の扱い（image-mode）を選ばせる ※対象mdにローカル画像リンクがあるときだけ聞く
入力 Markdown に **ローカル画像リンク**（`![alt](相対パス.png)` 等。`http(s)://` や `data:` は対象外）が
含まれる場合のみ、`AskUserQuestion`（header 例: 「画像」）で以下を聞く。**画像リンクが無ければ質問しない**
（`--image-mode` は省略＝既定 `embed` でよい）。判定は対象 md を軽く読み、`![...](...)` のうち URL/データURI
でないものがあるかで行う。

- **埋め込み**（`embed`）— 画像を data URI として HTML に埋め込み、**単一ファイルで自己完結**（既定・推奨）。
  メール添付/USB配布に最適。画像が多い/大きいと HTML が肥大化する点に注意。
- **外部フォルダ参照**（`link`）— 画像は埋め込まず、**出力HTMLからの相対パス**で外部ファイルを参照。
  HTML は軽量だが、配布時は画像フォルダも一緒に運ぶ必要がある。`--outdir` を指定した場合、参照パスは
  出力先を起点に自動で再計算される（例: 一段深い出力先なら `../assets/x.png`）。

> `--image-mode` は**ローカル画像にのみ**作用する。外部URL画像は常にそのまま参照。`site` モードで複数mdを
> 束ねる場合も各HTMLごとに相対参照を再計算する。`freeform`/`design=ai` のときはスクリプトが選択モードを
> Claude 向け指示（AI_DESIGN_REQUIRED）に添えるので、著述時に埋め込み/参照を合わせること。

### 3g. 説明図の動き（motion）を選ばせる ※出力モードが `print` 以外のとき
`AskUserQuestion`（header 例: 「動き」）。動画ではなく読み物なので、**説明図の要所に動きを付けるか**を聞く。
動くのは図（mermaid・3 の図解・AI 構築で書く図）。`rich` ではカード・数字（数え上げ）・年表・チェックリスト・表の行と棒も、見えたときに現れる（`--motion-blocks`）。本文の段落は動かさない。

- **動かさない**（`off`）— 静止した図のみ（既定）。
- **要所だけ動かす**（`key`）— 流れ・手順・状態遷移など、動きで理解が進む図を Claude が各文書 1〜2 個選んで動かす。
- **図をすべて動かす**（`rich`）— すべての図が、図の流れの向きに沿って順に現れる。要の図は Claude が順序を注釈してよい。

動きの仕様（全モード共通・スクリプトが決める。決定論的）:
- 図が画面に入ったとき 1 回再生。図の右上の「↻ 再生」でもう一度。
- 線だけの要素は「描かれ」、図形・文字は「浮かび上がる」。注釈で順序・現れ方・流れる破線・明滅を指定できる（4d）。
- OS の「視差効果を減らす（prefers-reduced-motion）」・印刷・JS 無しでは、静止した完成図のまま表示する。
- 図が 1 つも無い文書では効果が無い（mermaid が無く、図解 `off`、`design=deterministic` のとき）。その場合は聞かなくてよい。
- **質問はこの 1 問だけ**。速さ（`--motion-tempo`）・動きの性格（`--motion-style`）・図ごとの見せ方・再生のきっかけは聞かず、
  4d の選び方の表に従って Claude が決める。ユーザーが言葉で指定した場合（「ゆっくり」「ダイナミックに」「クリックで再生」等）だけそれに従う。

### 3f. セクション別レイアウトの仕分け案を提示して合意を取る ※`design=deterministic` のときだけ

3c で選ばせた `--layout` は**既定値**にすぎない。生成前に、**対象 md の見出し構成を実際に読んで**
セクションごとの割り当て案を作り、表で提示して合意を取る（`AskUserQuestion` は使わず、
本文テキストで案を出して「これで生成してよいか」を確認する）。

**まず `--suggest-layouts` で案の叩き台を作る**（HTML は作らない。Markdown の形から機械的に判定する）:

```bash
python3 <skill_dir>/generate.py "<input.md>" --theme <key> --suggest-layouts
# | セクション | 割り当て | 理由 |  の表と、そのまま使える --layout-map "…" が出る
```

叩き台を元 md の内容と照らして直し（誤判定を外す・判定できない節を足す）、表で提示する。

**仕分けの目安**（内容から判断する。見出し名の語感だけで決めない）

| 節の中身 | 割り当て | Markdown の形（判定の手がかり） |
|---|---|---|
| 番号付きの手順・工程・時系列 | `timeline` | 番号付きリスト |
| 並列に比較できる機能・選択肢・種別 | `cards` | 並列な項目に小項目 |
| 項目が多い / 詳細を畳みたい / Q&A | `accordion` | 8 件以上、または `？` で終わる項目 |
| OS 別・言語別・環境別など、並列で中身が長い | `tabs` | 2〜6 項目それぞれにコードや 3 行以上の中身 |
| 確認項目・やることリスト | `checklist` | `- [ ]` / `- [x]`（チェックはブラウザに保存・進み具合のバー） |
| 用語集・設定項目・仕様 | `defs` | `- **用語**: 説明` / `- 項目: 値`（10 件以上で絞り込み欄） |
| 実績・効果・KPI | `stats` | 先頭が数値の項目（`- 98.5% 稼働率`）が 3〜6 件 |
| 技術スタック・対象範囲・キーワード | `chips` | 短い語（全角 14 文字程度まで）が 5 件以上、小項目なし |
| ディレクトリ構成・階層 | `tree` | 入れ子の項目がパスの形（`src/`・`a.ts`）。`— 説明` で注記 |
| メリット／デメリット、A 案／B 案 | `proscons` | 2〜3 項目に小項目。良い点・懸念は見出しの語で色と印が付く |
| 説明とコードが交互に続く（コードの解説） | `walkthrough` | 段落→コードが 2 組以上（左に説明・右にコード） |
| 冒頭の概要・まとめ | `summary` | 最初の節が「概要」「まとめ」「要点」等（節全体を要点の箱で包む） |
| 散文的な補足・注意・前提、項目が2つ以下 | `plain` | — |

- `walkthrough`・`summary` は節の見せ方で、節の中の箇条書きは素の箇条書きになる。
- **文章として読ませるならレイアウト、全体像を一目で見せるなら図（figkit）**。同じ内容を両方で出さない
  （例: 数値は本文で読ませるなら `stats`、比較や推移を見せるなら figkit の `bars`・`line`）。

- **既定値と同じになる節は表に載せなくてよい**（差分だけ出すと読みやすい）。
- 同じ部品が3節以上続く場合は、内容を見直して振り分けを変えるか `plain` に落とす。
- トップレベル箇条書きが無い節（段落だけ、表だけ、mermaid だけ）は割り当て不要。

**提示のしかた（例）**

> 既定は `plain` として、次のように割り当てます:
>
> | セクション | 割り当て | 理由 |
> |---|---|---|
> | 導入手順 | `timeline` | 番号付きの5工程 |
> | 主な機能 | `cards` | 並列な機能が6件、アイコン付き |
> | よくある質問 | `accordion` | Q&Aが9件あり畳みたい |
> | (その他の節) | `plain`（既定） | 散文的な補足 |

**合意後の渡し方は 2 通り。既定は `--layout-map`**（元 md を書き換えないので安全）。

1. **`--layout-map`（既定）** — CLI で渡す。元 md は無修正。
   `--layout-map "導入手順=timeline,主な機能=cards,よくある質問=accordion"`
2. **md 内ディレクティブ** — 割り当てを md 自身に残したい・今後も同じ形で再生成したい、と
   ユーザーが希望した場合のみ。見出しの直後に `<!-- layout: timeline -->` を挿入する。
   **元 md の書き換えになるので、必ず明示的な合意を取ってから**行う。

優先順は **ディレクティブ > `--layout-map` > `--layout`**。節名は見出しテキストか slug で
突き合わせる（空白・記号・大小は無視）。一致しなかった節名は警告が出るので、出たら見出しを確認する。

### 4. 生成スクリプトを実行
スキルディレクトリの `generate.py` を、選択値で実行する（パスは実際の配置に合わせる）。

```bash
python3 <skill_dir>/generate.py "<input.md>" [さらに.md...] \
  --theme <key> --mode <mode> [--auto-figure off|light|rich] \
  [--toc sidebar|menu|both|none] [--layout plain|cards|timeline|accordion|freeform] \
  [--layout-map "節名=cards,節名2=timeline"] \
  [--design deterministic|ai] [--image-mode embed|link] [--default-mode system|light|dark] \
  [--motion off|key|rich] [--motion-tempo slow|normal|fast] \
  [--motion-style gentle|dynamic|playful|cinematic|tech] [--motion-blocks auto|on|off]
```

- 出力は既定で入力と同じ場所に `<元ファイル名>.html`。別の場所にしたい場合は `--outdir <dir>`。
- ヘッダー上部に小見出しを出したい場合は `--eyebrow "AI情報共有会"` のように渡す。
- `--layout` は**セクション別指定が無い節の既定値**。`--layout-map` は 3f で合意したセクション別の
  割り当て（`plain|cards|timeline|accordion`。`freeform` は節単位には指定できない）。
- `--image-mode` はローカル画像リンクの扱い（`embed`=data URI で埋め込み／`link`=外部フォルダ参照）。
  省略時は `embed`。3e で `link` を選んだ場合のみ明示する。
- `--motion` は 3g の選択。`--mode print` と組み合わせた場合は警告を出して `off` として扱う。
- `--motion-tempo` は動きの速さ（既定 `normal`）。聞かずに決める: 落ち着いた資料・経営向け・読み込む文書は `slow`、
  説明会の投影・短い紹介は `fast`、迷えば `normal`。図ごとには `data-tempo` で上書きできる。
- `--motion-style` は動きの性格（既定 `gentle`）。聞かずに決める: 製品紹介・発表・勢いを出したい資料は `dynamic`、
  子ども・イベント・親しみやすい案内は `playful`、ビジョン・物語・経営向けの語りは `cinematic`、技術・データ・開発者向けは `tech`、
  手順書・規程・読み込む文書は `gentle`。図ごとには `data-motion-style` で上書きできる。
- `--motion-blocks` はカード・数字・年表・チェックリスト・表などの部品の登場（既定 `auto` = `--motion rich` のときだけ）。
  `key` でも部品を動かしたいときは `on`、`rich` でも図だけにしたいときは `off`。
- `--default-mode` は初回表示（localStorage 未設定時）の既定モード。省略時はテーマの既定に従う。
  ユーザーから指定がなければ省略してよい。

### 4b. 図解の自動補完（auto-figure が off 以外のとき）
スクリプトは各セクション末尾に空の差し込みスロットを置き、次のマーカーを出力する:

```
===== AUTO_FIGURE_ENABLED (level=...) =====
... 配色パレット と 各ファイルのセクションslug一覧 ...
===== /AUTO_FIGURE_ENABLED =====
```

**図はまず figkit で作る**（下の「figkit」節）。SVG を手で描くより生成コストが低く、同じ仕様から同じ図になる。
figkit に無い形の図だけ、以下の手描きのルールで描く。

このとき **元の Markdown を読み、図解すべき内容のあるセクションだけ**、対応スロット
`<div class="auto-fig-slot" data-section="SLUG"></div>` の**中身**を、テーマ配色の自己完結 `<svg>` に `Edit` で置き換える：

- 図にすべき典型: **番号付き手順→フロー図**、**比較→対比図/簡易棒グラフ**、**階層→ツリー**、
  **循環→サイクル図**、**時系列→タイムライン**、**全体像→構成図**。
- 描画ルールは「4の mermaid フォールバック」と同じ（`viewBox`＋`max-width:…;width:100%;height:auto`、
  色は **CSS変数**（`fill="var(--accent-soft)"` 等）、外部依存なし、`aria-label` 付与、marker の id はユニークに）。
- `light` は1〜2個に厳選、`rich` は積極的に。**無理に図にしない**（箇条書きで十分なものはスロットを空のまま＝自動で非表示）。
- 1つのスロットに複数 `<figure>` を入れてもよい。

### 4c. AI構築（layout が freeform、または design=ai のとき）
スクリプトはガワ（固定ヘッダー・メニュー・目次・テーマCSS・部品クラス・スクロールスパイ・印刷）だけを生成し、
本文を `<main class="content"><!--MD2DOC_CONTENT--></main>` のプレースホルダにする。出力に次が出る（`[基調テイスト=...]` に選んだ形式が入る）:

```
===== AI_DESIGN_REQUIRED =====
[配色] ... / [使える部品クラス] ... / 必須見出し(slug) ... / 元Markdown
===== /AI_DESIGN_REQUIRED =====
```

このとき **あなた（Claude）が元Markdownを解釈し、内容に最適化した自由なデザインのHTML**を著述して、
`<!--MD2DOC_CONTENT-->` を `Edit` で置き換える：

- **基調テイスト**: 出力の `[基調テイスト=...]` に従う。`cards/timeline/accordion/plain` のときはその形式を主モチーフにしつつ作り込む（決定論版より凝ってよいが、テイストは外さない）。`freeform` は完全自由。
- **必須見出し**: 出力された各 h2/h3 は、指定の `slug` を `id` に、`class="hl"` を付けて含める（nav・目次・スクロールスパイと一致させるため）。順序も合わせる。
- **配色**: `var(--accent)`/`var(--accent-2)`/`var(--accent-soft)`/`var(--ink)`/`var(--muted)`/`var(--line)`/`var(--card)` と循環色 `var(--a0)`〜`var(--aN)` を使う。要素に `style="--ca:var(--a1)"` を付けると部品ごとに色を変えられる。アクセント色の上の文字は `var(--on-accent)`。**hex 直書きは不可**（ライト/ダーク切替に追従しないため）。
- **部品**: `.lead` / `.card-grid>.doc-card` / `.feature-grid` / `.stat-row>.stat(.big,.cap)` / `.chips>.chip` / `.badge` / `.timeline` / `.accordion` / `.callout` / `.tablewrap>table` / `.split`。これらを内容に応じて自由に組み合わせる（カードとタイムラインの混在等）。
- **図**: 必要なら自己完結 `<figure class="mermaid-fig"><svg viewBox=...>…</svg></figure>`（外部依存なし）。
- **自己完結を厳守**: 画像/外部CSS/JS/フォントを足さない。既存の部品クラスとインライン `style` のみで仕上げる。むやみに新しい `<style>` を足さない（必要時は最小限）。
- 内容の意味づけ（手順→タイムライン、比較→.split や表、要点→カード、数値→.stat）に合わせ、**メリハリのある誌面**にする。
- **定型の部品はスクリプトに任せる（MD2DOC-PART と --finalize）**。タブ・チェックリスト・用語・数値タイル・タグ・
  ツリー・対比・説明とコード・表・mermaid のような定型の形は、HTML を手で書かず、本文の中に Markdown の断片を置く:

  ```html
  <h2 id="インストール" class="hl">インストール</h2>
  <p class="lead">（Claude が書く導入）</p>
  <!--MD2DOC-PART layout=tabs-->
  - macOS
    ```bash
    brew install node
    ```
  - Windows
    ```powershell
    winget install OpenJS.NodeJS
    ```
  <!--/MD2DOC-PART-->
  ```

  本文を書き終えたら 1 回だけ仕上げる（断片が決定論的な部品に置き換わり、mermaid も描かれる）:

  ```bash
  python3 <skill_dir>/generate.py --finalize "<out.html>" --theme <key> [--src "<input.md>"]
  ```

  - `layout` は 3f の表と同じ値（省略時 `plain`）。見出し（h2/h3）は断片に入れず Claude が書く（slug を合わせるため）。
  - `--src` は断片の中のローカル画像の相対パスの基準（省略時は出力 HTML の場所）。
  - mmdc が無い環境では `MERMAID_MANUAL_RENDER_REQUIRED` が出るので、5 の手順（figkit の `replace` が最短）で差し替える。
  - 手作りするのは、文書全体の構成・導入や強調・定型に当たらない独自の部品だけにする（生成コストと書き漏れを減らす）。
- **手で書いた表もページ側で整う**: 8 行以上の `<table>` には並べ替え・絞り込み・数値の列の右寄せと棒が自動で付く
  （1 列目は行の見出しとして扱う）。止めるなら `<table data-table="plain">`、8 行未満でも付けるなら `data-table="tools"`。
- **割り当て案が渡る**: `AI_DESIGN_REQUIRED` に `--suggest-layouts` と同じ判定の結果が載る。参考にしつつ崩してよいが、
  定型に当たる節は MD2DOC-PART を使う。

### 4d. 図の動き（motion が off 以外のとき）
スクリプトは動きの実行部を埋め込み、`MOTION_ENABLED` マーカー（図の一覧・注釈の語彙・figkit の使い方）を出す。
**動かし方は実行部が決める**。Claude が決めるのは「どの図を動かすか」と「(任意の)注釈」だけで、
図の色・座標・style は変えない（再現性のため）。4b・5 で図を描き終えてから行う。

- **`key`**: 各文書で動きが理解を足す図を **1〜2 個**選び、`data-motion` を付ける（figkit なら仕様に `"motion": true`）。
  0 個でもよい。静的な一覧・単純な階層は選ばない。
- **`rich`**: 全図が動く。注釈の無い図は位置の順に自動で現れる。邪魔な図は `data-motion="none"`。
- **mermaid（mmdc 出力）の svg は内部を書き換えない**。figure に `data-motion` 等を足すだけにする。

#### 選び方の表（ユーザーに聞かず、ここから決める）

| 図の中身 | figkit の type | 動き（figkit は組み込み済み。手描き・mermaid は注釈で） |
|---|---|---|
| 処理・データ・依頼の流れ、分岐、差し戻し | `flow` | 段ごとに現れ、矢印が描かれる。受け渡しは `travel`、要のノードは `pulse` |
| 番号付きの手順・工程 | `steps` | 左から順に。手順を 1 つずつ解説するなら `walkthrough`（`data-focus`） |
| 循環する工程（PDCA、往復） | `cycle` | 順に現れ、中央の輪が回る（`data-spin`） |
| 数量の比較・推移 | `bars` | 棒が伸び（`grow`）、値が数え上がる（`data-count`）。強調は `highlight` |
| 指標の強調（件数・割合・時間） | `metrics` | タイルが弾んで現れ（`pop`）、値が数え上がる |
| 2〜3 案の対比、Before/After | `compare` | 列ごとに現れ、要点が 1 つずつ（`data-stagger`） |
| 中核と周り（関係者・連携先） | `hub` | 中心→線→周り。やりとりは `travel` / `flow`、繰り返し見せるなら `"trigger":"loop"` |
| 層の構成（アーキテクチャ） | `layers` | 下の層から積み上がる |
| 登場者の間のやりとりの順序 | `sequence` | メッセージが順に、線の上を印が移動 |
| 数値の推移 | `line` | 線が描かれ、点が弾み、最後の値が数え上がる（`area` で面も） |
| 割合・内訳 | `donut` | 時計回りに埋まり、合計が数え上がる |
| 予定・工程表・マイルストーン | `gantt` | バーが伸び、今日の線が引かれる |
| コマンドの実行例・セットアップ | `terminal` | コマンドが 1 文字ずつ打たれ、出力が続く。長い手順は `"trigger":"click"` |
| 会話・問い合わせ・AI とのやりとりの例 | `chat` | 吹き出しが順に現れる。`side` 省略時は `user` が右、他は左。長い文は折り返す |
| 段ごとに減る件数（訪問→登録→購入） | `funnel` | 段が上から順に現れ、値が数え上がる。右に前段からの割合。要の段は `highlight` |
| 2〜3 の集合の重なり・共通点 | `venn` | 円が順に弾んで現れ、重なりのラベル（`overlap`）が最後に出る |
| 2 軸での位置づけ（効果×工数など） | `matrix` | 軸が描かれ、象限の名前、点が順に弾む。`quadrants` は左上・右上・左下・右下の順 |
| 年表・マイルストーン（日付の点） | `timeline` | 軸が伸び、点と文字が上下交互に順に現れる。節目は `highlight`（明滅） |
| 組織図・階層（親子の木） | `org` | 上の段から順に現れ、親子の線が描かれる。葉が多いと間隔を詰め、縦に積む |
| 移行・改善・設計変更 | `toggle` | 変更前／変更後をボタンで切り替え、変わった所（`changed`）が光る。印刷は並べて表示 |
| 1 枚の流れで複数の経路（正常系・異常系） | `flow` ＋ `edges[].paths` | 経路のボタンで、その経路だけが光り印が流れる |
| 大きな構成図の要所を順に説明 | `flow`・`hub` ＋ `zoom` | 全体→部分へ寄り、次へ移って全体へ戻る（小さな図には使わない） |
| 図の各部に一言ずつ説明を添える | 各 type の `note` | 引き出し線付きの吹き出しが、その部分と一緒に現れる |
| 線が多いつながりの図 | `flow`・`hub`（既定で `hover`） | ノードに触れると、つながる線と相手だけが残る |
| 本文を読み進めながら図を追ってほしい | 任意 ＋ `"trigger":"scroll"` | 図が画面を通る位置に合わせて段が進む（1 文書に 1〜2 個） |
| 上のどれにも当たらない | 手描き svg | `data-motion="auto"`、必要なら `data-step` で順序 |

- **再生のきっかけ**（`data-trigger`）: 既定は `view`（見えたら 1 回）。常に動いていてほしい全体像（hub 等）だけ `loop`、
  読み手が自分のペースで見たい長いシーケンス・ターミナルは `click`、本文と歩調を合わせたい図は `scroll`。
  1 文書で `loop` は 1 つまで。`data-trigger` を付けた図は、`key` で `data-motion` が無くても動く。
- **操作と注記は動きの設定と無関係に働く**: 経路の切り替え・変更前／変更後・関連の強調・注記の吹き出しは、
  `--motion off` や「視差効果を減らす」でも使える（動きだけが止まり、切り替えは即座になる）。
  ただし注記と経路は JS が要るので、**本文の理解に欠かせない情報は本文か caption にも書く**。
- **強さの目安**: `data-flow`・`data-pulse`・`data-spin` などのループは 1 図に 1〜2 個まで。全図にループを付けない。
  `data-attn`（現れた後の強調）と `data-burst`（弾ける粒）は、結論・結果など 1 図に 1 か所だけ。
- **動きの性格**（`--motion-style` / figure の `data-motion-style`）: 注釈の無い要素の現れ方・図全体の入り方・段の間隔を決める。
  注釈（`data-effect` 等）を付けた要素は注釈が優先。

| 性格 | 図形 | 文字 | 大きな面 | 図全体の入り方 | 段の間隔 |
|---|---|---|---|---|---|
| `gentle`（既定） | 浮かぶ | 浮かぶ | 浮かぶ | なし | 標準 |
| `dynamic` | 弾む（pop） | 下から滑る | 寄る（zoom） | punch（縮んだ所から弾む） | 詰める |
| `playful` | 伸び縮み（elastic） | 跳ねる（bounce） | 落ちる（drop） | drop | やや詰める |
| `cinematic` | ぼけから（blur） | ぼけから | ぼけから | zoom-out（大きくぼけた所から） | ゆったり |
| `tech` | 拭き取り（wipe） | でたらめな文字から（scramble） | 拭き取り | glitch（乱れて定まる） | やや詰める |

#### 注釈の語彙（手描き svg・mermaid の figure に付ける。figkit は組み込み済み）

| 付ける場所 | 属性 | 意味 |
|---|---|---|
| figure | `data-motion="auto\|steps\|none"` | 動かし方（auto=位置順、steps=`data-step` 順、none=動かさない） |
| figure | `data-tempo="slow\|normal\|fast"` | この図の速さ |
| figure | `data-trigger="view\|click\|loop"` | 再生のきっかけ（見えたら／ボタン／繰り返し） |
| figure | `data-motion-dir="auto\|x\|y\|reverse-x\|reverse-y\|radial\|in\|diagonal\|spiral\|random"` | auto の順番の向き（radial=中心から外へ、in=外から中心へ、spiral=中心の周りを回る順） |
| figure | `data-motion-style="gentle\|dynamic\|playful\|cinematic\|tech"` | この図の動きの性格（上の表） |
| figure | `data-intro="punch\|zoom-out\|drop\|tilt\|glitch\|iris\|fade\|rise\|none"` | 図全体の入り方（中の要素はその途中から現れる） |
| 要素・g | `data-step="N"` | 現れる順番（同じ N は同時）。付けた要素だけが動く |
| 要素・g | `data-effect="draw\|rise\|fade\|slide\|pop\|grow\|wipe\|none"` | 現れ方（描く／浮かぶ／その場で／左から／弾む／伸びる／拭う） |
| 要素・g | `data-effect="zoom\|flip\|flip-y\|spin\|roll\|swing\|drop\|bounce\|elastic\|jelly"` | 動きの強い現れ方（大きい所から／裏返る／回る／転がる／振り子／落ちる／跳ねる／伸び縮み／ぷるん） |
| 要素・g | `data-effect="slide-left\|slide-right\|slide-up\|slide-down\|blur\|iris\|blinds\|glitch\|flicker\|outline"` | 向きのある滑り／ぼけから／円が開く／帯が開く／乱れる／明滅して点く／輪郭を描いてから塗る |
| text・g | `data-effect="letters\|scramble"` | 1 文字ずつ現れる／でたらめな文字から定まる |
| 要素・g | `data-attn="shake\|wiggle\|jump\|pop\|tada\|heartbeat\|flash\|glow\|ring\|pulse"` | 登場がすべて終わった後、段の順に 1 回強調する（ring は波紋） |
| 要素 | `data-burst="粒の数"` | 現れるときに粒が弾ける（結果・達成に） |
| 要素・g | `data-float="px"`・`data-sway="度"`・`data-blink`・`data-heartbeat`・`data-glow` | 現れた後の繰り返し（漂う／揺れる／瞬く／鼓動／光る） |
| 図形・g | `data-march` | 輪郭の点線が回り続ける（処理中・選択中） |
| g | `data-wave` | 子が順に波打ち続ける（点・並んだ項目） |
| 要素 | `data-orbit="半径"`・`data-ripple` | 小さく回り続ける／波紋が広がり続ける |
| 線・g | `data-stream="数"` | 線の上を印が流れ続ける（`travel` の繰り返し版） |
| 要素 | `data-depth="-2〜2"` | スクロールに合わせてずれる（背景の飾りに奥行き） |
| 要素 | `data-grow="up\|down\|left\|right"` | `grow` の向き |
| g | `data-stagger="ms"` | 子を 1 つずつ（既定 130ms 間隔） |
| 線・g | `data-travel="ラベル"` | 線の上を印が移動（受け渡し。空文字なら点だけ） |
| text | `data-count="0"` | 数値を 0（や指定値）から数え上げる。書式（カンマ・小数・単位）は元の文字を保つ |
| 線・g | `data-flow` | 現れた後、線に沿って破線が流れ続ける |
| 要素 | `data-pulse` | 現れた後、ゆっくり明滅 |
| 要素 | `data-spin="cw\|ccw"` | 回り続ける（飾りの輪に。文字には付けない） |
| 要素・g | `data-focus="N"` | 現れた後、N の順に 1 つずつ強調し、他の `data-focus` を薄くする |
| text・g | `data-effect="type"` | 文字を 1 文字ずつ打つ（コマンドの入力に） |
| 要素・g | `data-note="説明"`（`data-note-pos="top\|bottom\|left\|right"`） | 引き出し線付きの吹き出し。位置は空いている側を自動で選ぶ |
| 要素・g | `data-zoom-step="N"` | 現れた後、N の順にその部分へ寄って戻る |
| figure | `data-paths="正常系\|異常系"` ＋ 要素の `data-path="正常系\|…"` | 経路のボタンを出し、選んだ経路の要素だけを残して印を流す |
| figure | `data-hover` ＋ `data-node="id"`・`data-link="id1 id2"` | ノードに触れる・フォーカスすると、つながる線と相手だけを残す |
| figure | `data-toggle`（`data-toggle-auto`）＋ `.mo-states > .mo-state[data-state="名前"]` | 状態を切り替える。`data-changed` の要素が切り替え時に光る |

ノードとその文字は同じ `<g>` にまとめ、1 つの step にすると自然に見える。
`pop`・`grow`・`spin` は要素の中心・端を基準に拡大・回転するので、`transform` 属性で回転・拡大している要素には付けず、`<g>` で包んで付ける。

### figkit — 図の部品（JSON の仕様から図を作る）

同梱の `figkit.py` は、図の種類と中身だけを JSON で受け取り、テーマ配色（CSS 変数）と動きの注釈入りの
`<figure>` を作って出力 HTML に差し込む。auto-figure（4b）・mermaid の手描きフォールバック（5）・AI 構築（4c）の
どれでも使える。**手描きより先にこれを使う**。

```bash
python3 <skill_dir>/figkit.py --list                      # 図の種類と仕様の書き方
python3 <skill_dir>/figkit.py spec.json --insert out.html # 各図の slot / replace / placeholder に差し込む
```

- 共通の項目: `type`（必須）/ `id` / `caption` / `aria` / `motion`（`true`=段の順に動く）/ `tempo` / `trigger`、
  差し込み先は `slot`（auto-figure の `data-section`）・`replace`（置き換える figure の id。mermaid の手描き
  フォールバック `md2doc-mm-N` に使う）・`placeholder`（AI 構築の本文に置いた `<!--FIGKIT:名前-->`）のどれか。
- 種類: `flow` / `steps` / `cycle` / `bars` / `metrics` / `compare` / `hub` / `layers` / `sequence` /
  `line` / `donut` / `gantt` / `terminal` / `toggle` / `chat` / `funnel` / `venn` / `matrix` / `timeline` / `org`
  （仕様は `--list`）。
- 項目の共通の注釈: `note`（吹き出し）・`note_pos`・`changed`（toggle で変わった所）。
  `flow` は `edges[].paths`（経路）・`zoom`（寄るノード id の順）・`hover`、`hub` は `zoom`（label の順）・`hover`。
- `toggle` は `states` に他の type の仕様を 2 つ以上並べる（`labels` で状態の名前）。
- 1 つの JSON に複数の図を `{"figures":[...]}` で入れ、1 回で差し込める。
- mermaid の flowchart・sequenceDiagram は、mmdc が無いとき `flow`・`sequence` の仕様に写して `replace` で差し込める。
- 動きが `off` の文書でも使える（注釈は data-* 属性だけなので、静止した図として表示される）。

```json
{"figures": [
  {"type": "flow", "slot": "処理の流れ", "motion": true, "caption": "実装からレビューへの受け渡し",
   "nodes": [{"id": "i", "label": "実装", "sub": "impl"}, {"id": "r", "label": "レビュー", "pulse": true}],
   "edges": [{"from": "i", "to": "r", "travel": "{output}"}]},
  {"type": "bars", "slot": "月ごとの件数", "unit": "件", "highlight": 2,
   "items": [{"label": "4月", "value": 320}, {"label": "5月", "value": 480}, {"label": "6月", "value": 1240}]}
]}
```

### 4e. 動画を埋め込む（任意）

文書の中に、動画のように再生できる説明（motion-video のプレイヤー）を置ける。
**プレイヤー・時間割・字幕・音声は motion-video が受け持ち、中身は Claude が作る**（部品でも、`custom`・`dom` で自由にでも）。

```markdown
<!--MD2DOC-VIDEO src="intro.json" player="minimal" caption="概要（1 分）"-->
```

- `src` は motion-video の台本（md からの相対パス）。書き方は motion-video スキルの SKILL.md と `build.py --list`。
- `player` の既定は `minimal`（文書に馴染む）。`theme` を省くと文書のテーマに近い配色になる
  （corporate→daylight、darktech→midnight、editorial・paper→paper、contrast→mono、blueprint→navy-brass など）。
- 決定論的な構築（md に書く）でも、AI 構築（本文に書いて `--finalize`）でも同じ書き方で効く。
- 音楽（86 曲）・効果音（125 種・組 10 種）は台本の `audio` で選ぶ（motion-video の `build.py --list-sounds`）。
  文書の中の動画は音を出さずに見られることも多いので、曲は `calm`・`study`・`minimal` など控えめなものにし、
  効果音は `"sfx": {"kit": "soft", "density": "low"}` 程度に抑える。
- 向くのは、手順の実演・画面の変化・全体像を順に見せる説明。文章と図で足りる節には使わない（1 文書に 1〜2 本まで）。
- motion-video スキルが無い環境では、注意の枠に置き換わる。

### 5. mermaid のフォールバック対応（環境にmmdcが無い場合）
スクリプトは mermaid 図を、`@mermaid-js/mermaid-cli`（`mmdc`）があれば**選択テーマの配色でSVG化**して埋め込む。
このとき **ライト用・ダーク用の2枚**を描き、`.mm-light` / `.mm-dark` として両方埋め込んで表示モードで出し分ける
（ダーク側は id 衝突を避けるため接尾辞を付与）。

`mmdc` が無い環境では、出力に次のマーカーが出る:

```
===== MERMAID_MANUAL_RENDER_REQUIRED =====
... 配色パレット(JSON) と 各図の id・mermaidソース ...
===== /MERMAID_MANUAL_RENDER_REQUIRED =====
```

このとき **あなた（Claude）が各 mermaid 定義を解釈し、テーマ配色の図に差し替える**。
flowchart は figkit の `flow`、sequenceDiagram は `sequence` の仕様に写し、`"replace": "md2doc-mm-N"` で差し込むのが
最も安く確実（figure 全体が置き換わる）。figkit に当たらない図だけ、次の手順で `<svg>` を手描きする：

1. 出力された **配色パレット** の `use`（`var(--accent)` などの CSS 変数参照）をそのまま使う。
   `ref_light` / `ref_dark` は「どんな色か」を把握するための参考値であって、**HTML には書かない**。
   CSS 変数で描けば、1枚の SVG がライト/ダーク両モードに自動追従する。
2. 各図について、対象HTML内の `<figure class="mermaid-fig manual-render" id="md2doc-mm-N">…</figure>` を、
   `Read` で確認のうえ `Edit` で **figure 全体**を次のように置き換える：
   ```html
   <figure class="mermaid-fig" id="md2doc-mm-N">
     <svg viewBox="0 0 W H" role="img" aria-label="図の説明"
          xmlns="http://www.w3.org/2000/svg" style="max-width:WIDTHpx;width:100%;height:auto">
       …ノード(rect/円)・ラベル(text)・矢印(line+marker)…
     </svg>
   </figure>
   ```
3. 描画の指針:
   - **対応図種**: flowchart（LR/TD）、sequenceDiagram、状態遷移、簡単な gantt/円グラフ程度。複雑すぎる場合は要点を簡略化して図示する。
   - **配色**: ノード塗り=`var(--accent-soft)`、枠線=`var(--accent)`、矢印/線=`var(--accent-2)` か `var(--muted)`、文字=`var(--ink)`、`font-family="var(--font)"`。塗りつぶしたアクセント図形の上に文字を置くなら `var(--on-accent)`。
   - **レスポンシブ**: 必ず `viewBox` を付け、`style="max-width:…;width:100%;height:auto"`。座標は左上原点で手計算（ノード幅~140, 高さ~48, 間隔~50 が目安）。
   - **自己完結**: 画像/外部フォント/スクリプトを使わず、SVG要素だけで描く。矢印は `<marker>` を `defs` に定義（id は図ごとにユニークに）。
   - `aria-label` に図の意味を日本語で入れる。
   - 置き換え後、`manual-render` クラスとマーカーコメント・フォールバックの code 要素は残さない。
4. すべて差し替えたら、スクリプトが作った `.md2doc-mermaid-todo.json` は削除してよい。

### 6. 完了報告
- 生成した HTML の場所を伝える。`SendUserFile` で渡すと確認しやすい。
- mermaid を手描きフォールバックした場合は「mmdc が無いため図はClaudeが描画した」旨を一言添える。
- motion が `key` のときは、動かした図（見出し名）を一言添える。
- figkit を使った場合は、使った図の種類を一言添える（手描きとの区別）。
- 必要なら「`mmdc` を入れると今後は自動でテーマ配色SVGになる」ことも案内。

---

## セクション別レイアウトの指定記法

`--layout` は既定値、セクション単位の指定は次の優先順で解決される。

| 優先 | 方法 | 書式 | 使いどき |
|---|---|---|---|
| 1 | md 内ディレクティブ | `<!-- layout: cards -->` | 割り当てを md 自身に残したいとき（要ユーザー合意） |
| 2 | CLI 引数 | `--layout-map "導入手順=timeline,主な機能=cards"` | 元 md を書き換えたくないとき（**既定**） |
| 3 | CLI 引数 | `--layout plain` | 上のどちらにも指定が無い節 |

```markdown
## 導入手順
<!-- layout: timeline -->
1. リポジトリを clone
2. 依存を入れる

## 主な機能
<!-- layout: cards -->
- 🔍 全文検索 {fast}
- 📊 集計 {chart}

## 補足
- 指定が無いので --layout の既定値で描画される
```

- 表は 8 行以上で自動的に「見出しの固定・列の並べ替え・絞り込み欄・数値の列の右寄せと棒」が付く。
  表の直前に `<!-- table: plain -->`（付けない）/ `<!-- table: tools -->`（8 行未満でも付ける）で個別に変えられる。
  1 列目は行の見出しとして扱い、数値の列にしない。
- ディレクティブは**その節の中でだけ有効**。次の見出しでリセットされ、前節の指定を引きずらない。
- 置く場所は節内のどこでもよいが、**見出しの直後**が読みやすい。出力HTMLには残らない。
- 値は `plain` / `cards` / `timeline` / `accordion` / `tabs` / `checklist` / `defs` / `stats` / `chips` /
  `tree` / `proscons` / `walkthrough` / `summary`。`freeform` は文書全体のモードなので節単位には
  指定できず、警告を出して既定値のまま描画される。
- `--layout-map` の節名が どの見出しとも一致しなかった場合は警告が出る（黙って無視しない）。
- `design=ai` / `layout=freeform` のときは本文を Claude が著述するので、ディレクティブは
  描画には使われず、`AI_DESIGN_REQUIRED` に「節指定あり」として渡される（その指定を優先して著述する）。

## カード等を“リッチ化”する記法（任意）
`--layout cards|timeline|accordion` のとき、トップレベル項目に次の装飾が効く（決定論的・再現可能）。
内容に応じて、元 Markdown にこれらを足すと表現が一気に豊かになる（ユーザー合意のうえで追記する）。

- **先頭の絵文字** → カードのアイコン: `- 🔍 AIコードレビューツール`
- **末尾の `{タグ}`** → タグpill（複数可・`{a}{b}` や `{a, b}`）: `- AS400開発をVSCodeで {AS400}{lint}`
- **配色は自動で循環**: 各テーマの調和色（`THEMES[..]["accents"]`）をカード/タイムライン/アコーディオンで順に適用。一律の単調さを避ける。

> 元の箇条書きに装飾が無くても動作する（その場合は配色循環のみ効く）。アイコン/タグは項目の意味づけが明確なときだけ付ける。

## メモ
- 対応する Markdown 記法: 見出し / ネスト箇条書き / 番号リスト / チェックボックス / 表 / コードフェンス / 引用 / コールアウト(`> [!NOTE|TIP|IMPORTANT|WARNING|CAUTION]`) / mermaid / 太字・斜体・コード・リンク / 先頭絵文字アイコン・末尾`{タグ}` / frontmatter(`title`/`date`/`tags`/`eyebrow`/`brand`)。
- 見出し `##` がトップメニュー、`##`/`###` が左の目次になる（ID自動付与）。
- 左サイドメニュー（`--toc sidebar|both`）の操作:
  - **展開/非表示トグル** — ヘッダー左端のボタン。初期状態は展開。選択は
    `localStorage['md2doc-toc-open']`（`1|0`）に保存され、次回も維持される（`<head>` で先に適用するため再訪時のちらつきなし）。
  - **メニュー検索** — 目次上部の検索欄。見出しテキストの部分一致（大小・空白は無視）で絞り込む。
    章名がヒットした章は配下の小見出しも全件残る。検索中は畳んだ章も一時的に開き、`Esc` でクリア。
  - **章アコーディオン** — `##` 単位で `###` を開閉。初期状態は全章展開。`###` を持たない章は開閉ボタンを出さない。
- 表示モードの選択は `localStorage['md2doc-color-mode']`（`system|light|dark`）に保存。
- ヘッダーの「Aa」で、読み手が書体（既定／ゴシック／明朝／UD）と文字の大きさ（小／標準／大／特大）を選べる。
  `localStorage['md2doc-font']`・`['md2doc-size']` に保存し、`<head>` で先に反映する（ちらつきなし）。
  大きさは本文（`.content`）の拡大縮小で、印刷では標準に戻る。テーマの選択とは独立。
  印刷/PDF はモードに関わらず常にライト配色になる。
- テーマを増やすときは `generate.py` の `THEMES` に1エントリを足す。必要なのは
  `vars`（ライト・全キー）/ `vars_dark`（ダーク上書き）/ `accents`＋`accents_dark`（要素数を揃える）/
  `mermaid`＋`mermaid_dark` / `default_mode`。
