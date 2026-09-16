# 調査: 3 ペイン・split・ツリー・テーマ切り替え

> 前提: 出力は **単一 HTML・オフライン・第三者ライブラリなし**。
> 調べたのは「その制約の中でどう作るか」と「作れることの実測」。
> 実測は `headless Chromium`（Playwright 同梱・`/opt/pw-browsers`）で **`file://` のまま**行った。
> 検証スクリプトは使い捨て（scratchpad）。数値はすべてこの環境で取ったもの。

## 調査課題（requirements の「未確定事項」より）

1. ペインの分割とリサイズの確立したパターン（F1）と、`file://` で本当に動くか（F2・F3）。
2. テーマ切り替えの標準的な作り（`data-theme` と `prefers-color-scheme` の共存）（F4）。
3. 設定の記憶が `file://` で効くか（F5）。
4. 一覧・コメント一覧から該当箇所へ飛ぶときの挙動（F6・F7）。
5. split の行の対応づけを**既存の差分データだけで**作れるか（F8）。
6. ツリーの確立したパターン（F9）。
7. 狭い画面での畳み方（F10）。

## F1: ペイン分割は「window splitter」パターン（規範）

WAI-ARIA Authoring Practices の **window splitter** パターン:

- 境界そのものを `role="separator"` の**フォーカス可能なウィジェット**にする（`tabindex="0"`）。
- `aria-controls` で「どのペインを広げ縮めするか」を指す。
- 現在の幅を `aria-valuenow` / `aria-valuemin` / `aria-valuemax` で出す。`aria-orientation` は向き。
- キー操作の規範: **矢印キーで移動**、`Home` / `End` で最小・最大、`Enter` で**畳む / 戻す**。
  （`Shift` ＋ 矢印で大きく動かすのは慣例。規範に明記は無い）

> 出典は WebSearch の要約。**一次情報（w3.org / MDN）は egress 制限で取得できなかった**ため、
> 一次確認はしていない。ただし「属性名と役割」はどの要約でも一致しており、
> 実際に効くかは F2・F3 で**自分で測って**確かめた。

## F2: `file://` でのドラッグは Pointer Events で動く（実測）

`pointerdown` で `setPointerCapture`、`pointermove` で差分を幅に足し、`pointerup` で解放する形を作って測った。

| 測った項目 | 結果 |
|---|---|
| ドラッグ前の左ペイン幅 | 240px |
| ドラッグ中（マウスを +120px 動かした途中） | 360px（**押している間に反映される**） |
| 離したあと | 360px |
| `pointermove` が呼ばれた回数 | 8 |
| `aria-valuenow` | `"360"` に追従 |
| `localStorage` に保存された値 | `"360"` |

→ **AC13・AC-I2（ドラッグ中に反映され、離した時点で確定）は Pointer Events で満たせる。**
外部ライブラリは要らない。`mousedown`＋`document` へのリスナ登録という古い書き方より、
`setPointerCapture` のほうが「ペインの外へマウスが出た瞬間に追従が切れる」問題が起きない。

## F3: **畳む状態は CSS 変数では上書きできない**（実測・落とし穴）

最初の試作は次の形にした。

```css
.shell { grid-template-columns: var(--left) 6px 1fr 6px var(--right); }
.shell[data-left="collapsed"] { --left: 0px; }   /* ← 効かない */
```

幅の変更は `shell.style.setProperty("--left", px)` で**インラインに書く**ので、
`[data-left="collapsed"]` の側が**変数を再定義しても勝てない**（インライン宣言のほうが強い）。
実測でも `Enter` で畳む操作が**何も起きなかった**（幅 360px のまま）。

直した形——**畳む側は変数ではなく `grid-template-columns` そのものを宣言する**:

```css
.shell { grid-template-columns: var(--left, 240px) 6px 1fr 6px var(--right, 300px); }
.shell[data-left="collapsed"]  { grid-template-columns: 0 6px 1fr 6px var(--right, 300px); }
.shell[data-right="collapsed"] { grid-template-columns: var(--left, 240px) 6px 1fr 6px 0; }
.shell[data-left="collapsed"][data-right="collapsed"] { grid-template-columns: 0 6px 1fr 6px 0; }
```

| 状態 | 左 | 右 | 中央 |
|---|---|---|---|
| 両方開いている | 360 | 300 | 712 |
| 左を畳む | **0** | 300 | 1072 |
| 両方畳む | **0** | **0** | 1372 |
| 両方戻す | **360**（ドラッグした幅が戻る） | 300 | 712 |

→ **AC12（畳んで開き直せる）は、畳んでもインラインの幅が消えないのでそのまま戻る。**
この落とし穴は「黙って何も起きない」類なので、**回帰テストに入れる**。

## F4: テーマは `data-theme` ＋ `:not()` で 3 状態（実測）

3 状態（ライト / ダーク / OS に従う）を、既存の `@media (prefers-color-scheme: dark)` を
**捨てずに**作れる形:

```css
:root { /* ライトの値 */ }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* ダークの値 */ }   /* OS 追従。ただし明示ライトなら降りる */
}
:root[data-theme="dark"] { /* ダークの値 */ }             /* OS がライトでも暗くする */
```

`data-theme` 属性が**無い** = OS に従う。4 通りすべて測った（`--bg` の計算値）:

| OS の設定 | `data-theme` | 実測 `--bg` | 期待 |
|---|---|---|---|
| dark | （無し） | `#0d1117` | 暗い ✓ |
| dark | `light` | `#fff` | **明るい ✓** |
| dark | `dark` | `#0d1117` | 暗い ✓ |
| light | `dark` | `#0d1117` | **暗い ✓** |
| light | （無し） | `#fff` | 明るい ✓ |

→ **AC6 は満たせる。** 既存の 30 行ほどのダーク用宣言は、セレクタを
`:root:not([data-theme="light"])` に変え、同じ宣言を `:root[data-theme="dark"]` にも当てる形にする
（値の二重管理を避けるため、セレクタをカンマで並べるのではなく**共通の値を 1 か所**に置く設計は design で決める）。

## F5: `localStorage` は `file://` の Chromium で使える（実測）

`localStorage.setItem` → `getItem` が `"1"` を返した。前 work で作った下書き保存と同じ経路なので、
**新しい危険は無い**。ただし前 work で分かっているとおり **Firefox の `file://` は例外を投げる**。
既存コードは `storageOk` フラグで機能だけ落とす作りになっているので、**そこに相乗りする**。

保存するキーの設計で 1 つ違いがある——**下書きは差分ごと**（`diff_digest` を鍵に含める）だが、
**画面の設定は人ごと**（どの差分を見ても同じ幅・同じテーマが自然）。
→ 画面の設定は **digest を含めない固定キー**にする（decisions で確定）。

## F6: ペインの中では `scrollIntoView` がページを動かさない（実測）

中央ペインを `overflow: auto` にした状態で、80 行目の要素に `scrollIntoView({block:"center"})` ＋ `focus()`:

| 測った項目 | 結果 |
|---|---|
| ペインのスクロール位置 | 2901 |
| ページのスクロール位置 | **0**（動いていない） |
| `document.activeElement` | 対象の要素 |

→ 3 ペインにしても既存の「該当箇所へ飛ぶ」は壊れない。**AC-I4（フォーカスが移る）も `focus()` で満たせる。**

## F7: **リンクでの移動はフォーカスを運ばない**（実測・落とし穴）

現行のファイル一覧は `<a href="#file-3">` で、クリックするとペインは正しくスクロールする（1005px 動いた）。
しかし **`document.activeElement` は `BODY` のまま**だった。

→ 「スクロールはしたが、キーボードの現在位置は置き去り」という **AC-I4 が要求する状態そのもの**。
一覧・コメント一覧からの移動は、**移動先に `tabindex="-1"` を付けて明示的に `focus()` する**必要がある
（F6 で `focus()` なら移ることは確認済み）。

## F8: split の行の対応づけは**既存データだけ**で作れる（実測）

差分データはすでに 1 行ずつ `{kind: "add"|"del"|"ctx", old, new, text}` を持っている。
これだけを使って、**削除の連なりと追加の連なりを溜め、文脈行で吐き出す**規則を試した:

```
del を dels に、add を adds に溜める
ctx が来たら（または hunk の終わりで）:
    max(dels.length, adds.length) 行ぶん、dels[k] と adds[k] を左右に並べる（足りない側は空）
    ctx 自身は左右同じ行として並べる
```

この repo 自身の履歴（コミット 3 本ぶん・**20 ファイル / 88 ハンク / 4,036 行**）に当てて不変条件を測った:

| 不変条件 | 違反 |
|---|---|
| 左に出る行 = 元の `add` 以外の行と**同数・同順** | 0 |
| 右に出る行 = 元の `del` 以外の行と**同数・同順** | 0 |
| 左の `old` 行番号が**単調増加** | 0 |
| 右の `new` 行番号が**単調増加** | 0 |

→ **AC2・AC3 は生成側を触らずに画面だけで満たせる**（要件のスコープ「生成側の出力形式は変えない」と一致）。
副次的な性質: split の行数は `max(dels, adds) + ctx` なので、**unified より増えることはない**
（DOM が膨らむ心配が要らない）。

限界: これは **行単位の対応**であって、語単位の色分けではない（要件のスコープ外と一致）。
また「10 行消して 3 行足した」ような組では、4 行目以降の左に対応する右が空になる——
GitHub の split と同じ見え方になる。

## F9: ツリーは「tree view」パターン（規範）

- 根に `role="tree"`、各項目に `role="treeitem"`、子の入れ物に `role="group"`。
- **開閉できる項目にだけ** `aria-expanded` を付ける（葉には付けない）。
- 矢印キーは**見えている項目を深さ優先で**辿る。`→` は閉じていれば開き、開いていれば子へ。
  `←` は開いていれば閉じ、閉じていれば親へ。
- フォーカス管理は「1 つだけ `tabindex="0"`（ローミング）」か `aria-activedescendant` のどちらか。

> これも出典は WebSearch の要約で、**一次情報は取得できていない**（F1 と同じ制限）。
> 属性の構成はどの要約でも一致。実装後に headless で**実際に辿れること**を測る（test 工程）。

## F10: 狭い画面は 1 列に積む（実測）

`@media (max-width: 800px)` で `grid-template-columns: 1fr` に切り替えると、
700px 幅のビューポートで `grid-template-columns` の計算値は `"700px"`（= 1 列）になり、
各ペインが全幅を取った。境界（separator）はこのとき非表示にする。

→ **AC14 は満たせる。** 閾値は design で決める（差分が読める幅を中央に残せる下限）。

## リスク

- **R1（実測済みの落とし穴・F3）**: 畳む指定を CSS 変数で書くと**黙って効かない**。
  `grid-template-columns` の宣言で書く。回帰テストで固定する。
- **R2（実測済みの落とし穴・F7）**: リンクでの移動は**フォーカスを運ばない**。
  移動先に `tabindex="-1"` ＋ `focus()`。AC-I4 の実測点。
- **R3（設計）**: split では 1 行の中に**左右 2 つのコメント位置**がある。
  既存の `slotFor` は `[data-threads="鍵"]` を引くだけなので、**片側ずつ入れ物を用意すれば既存のまま**動く。
  ただしキーボードの現在行（`data-key`）は 1 行に 1 つでないと `j`/`k` が壊れる。→ design で決める。
- **R4（設計）**: 一覧・差分・コメント一覧が**それぞれ独立したスクロール領域**になるので、
  既存の `position: sticky` なヘッダ（`.topbar`・`.file-head`）の基準が変わる。
- **R5（互換）**: `--rich off` / 差分 0 件でも 3 ペインは壊れてはいけない（コメント一覧が空でも列は出る）。
- **R6（容量）**: 追加は CSS と JS だけで、**生成側のデータは増えない**。
  それでも app.js はすでに 1,318 行あり、ここに 4 つの機能を足すと読みにくくなる。→ design で分け方を決める。
- **R7（一次情報の不在）**: F1・F9 の ARIA 規範は要約に頼っている。
  属性名を間違えても**画面は普通に動いてしまう**ので、実装後に headless で
  「キーで辿れる」「状態が属性に出る」を**実測して**埋め合わせる。

## 結論（design への申し送り）

1. 3 ペインは **CSS Grid ＋ `role="separator"` ＋ Pointer Events**。畳むのは `grid-template-columns` の宣言で。
2. テーマは **`data-theme` 属性の 3 状態**。既存のメディアクエリは `:not([data-theme="light"])` で残す。
3. 画面の設定は **digest を含めない `localStorage` の固定キー**。レビュー記録の JSON には入れない。
4. split は **画面だけ**で作る（生成側は触らない）。対応づけは F8 の規則。
5. 一覧・コメント一覧からの移動は **`focus()` を必ず伴う**。
6. ARIA の規範は要約由来なので、**test 工程の実測で裏を取る**。
