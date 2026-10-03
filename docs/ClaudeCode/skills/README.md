# スキルの置き場所と、スキル同士の関係

`other/` と `video/` のスキルの関係をまとめる（`aidev/`・`github/`・`wiki/` は、それぞれの中で閉じているので、ここでは扱わない）。

## 置き場所の決まり

- **必ず要る相手は、同じフォルダに置く**。隣のフォルダ（`../motion-video` など）として読み込む。
- **フォルダをまたぐのは「あれば使う」関係だけ**。相手が無くても動き、その機能だけが別の形に落ちる。
  相手は、隣 → 1 つ上の階層の別のまとまり → `~/.claude/skills` の順に探す（各スキルの `find_skill`）。

```
skills/
  video/   motion-video  yukkuri-kaisetsu  yukkuri-publish  yukkuri-qa  video-export  youtube-upload  tests
  other/   ask-form  md-to-doc  irasutoya  fact-check  create-devcontainer  diff-review-html  grill-me  grilling
```

## 関係の図

```mermaid
flowchart LR
  subgraph video
    MV[motion-video]
    YK[yukkuri-kaisetsu]
    YP[yukkuri-publish]
    YQ[yukkuri-qa]
    VE[video-export]
    YU[youtube-upload]
  end
  subgraph other
    AF[ask-form]
    MD[md-to-doc]
    IR[irasutoya]
    FC[fact-check]
  end
  YK ==> MV
  YP ==> YK
  YQ ==> YK
  VE ==> MV
  VE ==> YK
  YU -.-> MV
  YU -.-> YP
  YU -.-> VE
  MV -.-> AF
  YK -.-> AF
  MD -.-> AF
  MD -.-> MV
  MV -.-> IR
  YK -.-> IR
  YK -.-> FC
```

太い矢印は「必ず要る」（同じフォルダ）、点線は「あれば使う」。

## video/ — 動画を作る

| スキル | 役目 | 必ず要る相手 |
|---|---|---|
| motion-video | 動画のように再生できる単一 HTML を作る。プレイヤー・時間割・字幕・音楽・効果音・背景を持つ | なし（独立） |
| yukkuri-kaisetsu | 2 人の掛け合いの解説動画を作る。調査と台本づくりの道具（`script.md`・`script_order.py`・`script_check.py`）もこの中にある（別のスキルにはしていない） | motion-video（描画・プレイヤー・音。`engine.js` を共有する） |
| yukkuri-publish | 題の案・概要欄・サムネイルを作る | yukkuri-kaisetsu |
| yukkuri-qa | 出来上がった動画を測って確かめる | yukkuri-kaisetsu |
| video-export | YouTube・YMM4・AviUtl 向けに書き出す | motion-video。yukkuri-kaisetsu の台本を渡すときは yukkuri-kaisetsu も |
| youtube-upload | 動画の HTML を WebM に録り、YouTube に限定公開で上げる | 録るときは motion-video（`shoot.py`）。上げるだけなら独立。題・概要欄・サムネイル（yukkuri-publish）と字幕（video-export）は、あれば拾う |

- yukkuri-kaisetsu の台本からは、motion-video の曲（`music:`・`@music:`）・効果音（`se:`・`kit:`）・背景（`bg:`・`@bg:`）を名前で使える。
- `video/tests/` は、このまとまりの回帰テスト。motion-video の変更が yukkuri-kaisetsu を壊していないかを確かめる（`video/tests/README.md`）。

## other/ — 汎用・独立のもの

| スキル | 役目 | 必ず要る相手 |
|---|---|---|
| ask-form | 質問を 1 つのウィンドウにまとめて聞く | なし（独立） |
| md-to-doc | Markdown から単一 HTML の文書を作る | なし（独立） |
| irasutoya | いらすとやの絵を探して取り、SVG や動く絵にする | なし（独立） |
| fact-check | 文書の事実を、出典に当てて確かめる | なし（独立） |

create-devcontainer・diff-review-html・grill-me・grilling は、ほかのスキルと関係を持たない。

## フォルダをまたぐ関係（あれば使う）

| 使う側 | 相手 | 何に使うか | 相手が無いとき |
|---|---|---|---|
| md-to-doc・motion-video・yukkuri-kaisetsu | ask-form | 作る前の指示を、1 つのウィンドウで聞く | `unavailable`・終了コード 3 が返る。端末の質問（`AskUserQuestion`）で聞く |
| md-to-doc | motion-video | 文書への動画の埋め込み・動く図 | その場所が注意の枠に置き換わる。文書は作れる |
| motion-video・yukkuri-kaisetsu | irasutoya | 人物・しぐさ・場面の絵を取る | 手元の絵・ほかの素材で作る |
| yukkuri-kaisetsu | fact-check | 台本の事実を出典と照らす | その工程を飛ばす（台本の検査が「まだ」と知らせる） |

## 写しを持つもの

- **アイコン集（`icons.py`）**: 元は `video/motion-video/icons.py`。`other/md-to-doc/icons.py` は写し（motion-video が無くても、文書のアイコンが出るように）。
  足す・直すのは motion-video の側で行い、`cp video/motion-video/icons.py other/md-to-doc/icons.py` で写す。写し忘れは `video/tests/test_motion_build.py` が見つける。
- **Chrome を動かすテストの道具**: `video/tests/test_engine.py` の `Chrome` と、`other/ask-form/tests/chrome.py`（ask-form のテストを単独で回せるように）。

## スキルを足す・移すとき

- 必ず要る相手があれば、その相手と同じフォルダに置く。
- 別のフォルダのスキルを使うなら、無いときの動きを決め、`find_skill` で探す（`../名前` と決め打ちしない）。
- フォルダを動かしたら、`.github/workflows/video-skills.yml` の対象パスと、`~/.claude/skills` のリンクを直す。
