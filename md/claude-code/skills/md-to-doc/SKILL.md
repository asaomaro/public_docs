---
name: md-to-doc
description: Markdown を、視覚的に分かりやすく図表を活用した単一HTMLドキュメントに変換する。固定ヘッダー・見出しメニュー・目次・コールアウト・コードコピー・印刷/PDF対応を備え、5つのデザインテーマから選べる。mermaid 図はテーマ配色でSVG化（環境が無い場合は内容を解釈して手描きSVGでフォールバック）。「mdをHTMLにして」「資料用のHTMLを作って」「このメモを綺麗なドキュメントに」「htmlドキュメント生成」などと言われたときに使用する。
---

# md-to-doc — Markdown → 視覚的HTMLドキュメント生成

Markdown を、配布しやすい**単一HTML**（外部依存なし）に変換する。
変換は同梱の `generate.py`（Python3 / stdlib のみ）が行う。

## 重要: 実行時は必ず「順番に選択」させる

ユーザーに **テーマ → 出力モード** の順で `AskUserQuestion` を使って選ばせてから生成する。
引数で明示指定がある場合のみ確認を省略してよい。

---

## 手順

### 0. 入力 Markdown を特定
- 会話やコマンド引数に対象 `.md` があればそれを使う。
- 不明なら、どのファイル（複数可）を変換するかユーザーに確認する。

### 1. テーマを選ばせる（1問目）
`AskUserQuestion` で以下を提示（header 例: 「テーマ」）。値はカッコ内のキー。

- **モダンコーポレート**（`corporate`）— 青基調・カード・万人向け。資料/報告書に無難。
- **ダークテック**（`darktech`）— 暗背景＋シアン/パープル。エンジニア向け。
- **インフォグラフィック**（`infographic`）— カラフル・丸ゴシック。インパクト重視。
- **エディトリアル**（`editorial`）— 明朝・余白・落ち着いた読み物風。
- **やわらかパステル**（`pastel`）— 丸み・淡色。社内共有で親しみやすく。

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
- **ヘッダーメニュー**（`menu`）— 上部固定メニューのみ。本文は全幅。
- **両方**（`both`）— ヘッダーメニュー＋左サイド目次（情報量重視）。
- **目次なし**（`none`）— どちらも出さない。

### 3c. リストの見せ方（レイアウト）を選ばせる
`AskUserQuestion`（header 例: 「レイアウト」）。各セクション直下のトップレベル箇条書きの描画方法。

- **箇条書き**（`plain`）— 通常のリスト（既定）。
- **カード**（`cards`）— トップレベル項目をカードグリッドに。各項目＋その小項目が1枚のカード。一覧性・見栄え重視。
- **タイムライン**（`timeline`）— 番号付きの縦タイムライン。手順・工程・時系列向き。
- **アコーディオン**（`accordion`）— 折りたたみ。項目が多く詳細を隠したいとき向き（先頭だけ開く）。
- **完全フリーフォーム**（`freeform`）— 形式に縛られず、**あなた（Claude）が内容ごとに自由にデザイン**する。

### 3d. 構築方法（design）を選ばせる
`AskUserQuestion`（header 例: 「構築」）。3c で `plain`/`cards`/`timeline`/`accordion` を選んだ場合に聞く。

- **決定論的**（`deterministic`）— スクリプトが選んだ形式に型変換。**同じ入力→同じ出力**（既定）。
- **AIがこのテイストで構築**（`ai`）— 選んだ形式を**基調テイスト**に、Claude が内容ごとに作り込む（アイコン/タグ/色/数値強調などで手作りサンプル相当の質に）。再現性より表現力。

> `freeform` を選んだ場合は常に AI 構築（`design=ai` 相当）。`plain/cards/timeline/accordion` × `deterministic/ai` の組合せで、「同じ形式でも決定論的かAI作り込みか」を選べる。
> 1〜3d の質問は、`AskUserQuestion` の複数質問機能で**まとめて**聞いてよい。
> 補足: `cards`/`timeline` は「番号付き手順」セクションと相性が良い。auto-figure と併用する場合、
> 同じセクションで「リストのカード化」と「図の差し込み」が重複しないよう、必要なら一方に寄せる。

### 4. 生成スクリプトを実行
スキルディレクトリの `generate.py` を、選択値で実行する（パスは実際の配置に合わせる）。

```bash
python3 <skill_dir>/generate.py "<input.md>" [さらに.md...] \
  --theme <key> --mode <mode> [--auto-figure off|light|rich] \
  [--toc sidebar|menu|both|none] [--layout plain|cards|timeline|accordion|freeform] \
  [--design deterministic|ai]
```

- 出力は既定で入力と同じ場所に `<元ファイル名>.html`。別の場所にしたい場合は `--outdir <dir>`。
- ヘッダー上部に小見出しを出したい場合は `--eyebrow "AI情報共有会"` のように渡す。

### 4b. 図解の自動補完（auto-figure が off 以外のとき）
スクリプトは各セクション末尾に空の差し込みスロットを置き、次のマーカーを出力する:

```
===== AUTO_FIGURE_ENABLED (level=...) =====
... 配色パレット と 各ファイルのセクションslug一覧 ...
===== /AUTO_FIGURE_ENABLED =====
```

このとき **元の Markdown を読み、図解すべき内容のあるセクションだけ**、対応スロット
`<div class="auto-fig-slot" data-section="SLUG"></div>` の**中身**を、テーマ配色の自己完結 `<svg>` に `Edit` で置き換える：

- 図にすべき典型: **番号付き手順→フロー図**、**比較→対比図/簡易棒グラフ**、**階層→ツリー**、
  **循環→サイクル図**、**時系列→タイムライン**、**全体像→構成図**。
- 描画ルールは「4の mermaid フォールバック」と同じ（`viewBox`＋`max-width:…;width:100%;height:auto`、配色パレット使用、外部依存なし、`aria-label` 付与、marker の id はユニークに）。
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
- **配色**: パレットの `accent`/`accent-2`/`accent-soft`/`ink`/`muted`/`line`/`card` と `accents`（循環色）を使う。要素に `style="--ca:色"` を付けると部品ごとに色を変えられる。`dark:true` は暗背景前提。
- **部品**: `.lead` / `.card-grid>.doc-card` / `.feature-grid` / `.stat-row>.stat(.big,.cap)` / `.chips>.chip` / `.badge` / `.timeline` / `.accordion` / `.callout` / `.tablewrap>table` / `.split`。これらを内容に応じて自由に組み合わせる（カードとタイムラインの混在等）。
- **図**: 必要なら自己完結 `<figure class="mermaid-fig"><svg viewBox=...>…</svg></figure>`（外部依存なし）。
- **自己完結を厳守**: 画像/外部CSS/JS/フォントを足さない。既存の部品クラスとインライン `style` のみで仕上げる。むやみに新しい `<style>` を足さない（必要時は最小限）。
- 内容の意味づけ（手順→タイムライン、比較→.split や表、要点→カード、数値→.stat）に合わせ、**メリハリのある誌面**にする。

### 5. mermaid のフォールバック対応（環境にmmdcが無い場合）
スクリプトは mermaid 図を、`@mermaid-js/mermaid-cli`（`mmdc`）があれば**選択テーマの配色でSVG化**して埋め込む。

`mmdc` が無い環境では、出力に次のマーカーが出る:

```
===== MERMAID_MANUAL_RENDER_REQUIRED =====
... 配色パレット(JSON) と 各図の id・mermaidソース ...
===== /MERMAID_MANUAL_RENDER_REQUIRED =====
```

このとき **あなた（Claude）が各 mermaid 定義を解釈し、テーマ配色の `<svg>` を手描きして差し替える**：

1. 出力された **配色パレット**（`accent` / `accent-2` / `accent-soft` / `ink` / `muted` / `line` / `card` / `font` / `dark`）を使う。
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
   - **配色**: ノード塗り=`accent-soft`、枠線=`accent`、矢印/線=`accent-2` か `muted`、文字=`ink`、`font` を `font-family` に。`dark:true` のテーマは背景が暗い前提で文字を明るく。
   - **レスポンシブ**: 必ず `viewBox` を付け、`style="max-width:…;width:100%;height:auto"`。座標は左上原点で手計算（ノード幅~140, 高さ~48, 間隔~50 が目安）。
   - **自己完結**: 画像/外部フォント/スクリプトを使わず、SVG要素だけで描く。矢印は `<marker>` を `defs` に定義（id は図ごとにユニークに）。
   - `aria-label` に図の意味を日本語で入れる。
   - 置き換え後、`manual-render` クラスとマーカーコメント・フォールバックの code 要素は残さない。
4. すべて差し替えたら、スクリプトが作った `.md2doc-mermaid-todo.json` は削除してよい。

### 6. 完了報告
- 生成した HTML の場所を伝える。`SendUserFile` で渡すと確認しやすい。
- mermaid を手描きフォールバックした場合は「mmdc が無いため図はClaudeが描画した」旨を一言添える。
- 必要なら「`mmdc` を入れると今後は自動でテーマ配色SVGになる」ことも案内。

---

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
- テーマを増やすときは `generate.py` の `THEMES` に1エントリ（CSS変数＋mermaid配色）を足すだけ。
