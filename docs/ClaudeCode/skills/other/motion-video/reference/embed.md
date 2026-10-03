# ほかの HTML に埋め込む・動く図

md-to-doc の文書やほかのページに動画・動く図を入れるときに読む。

```bash
python3 <skill_dir>/build.py spec.json --embed -o intro.embed.html   # 断片（CSS と実行部を含む。何個並べてもよい）
```

- md-to-doc の文書には `<!--MD2DOC-VIDEO src="spec.json" player="minimal"-->` と書けば、文書を作るときに埋め込まれる。
- **動く図**（プレイヤー無し）: md-to-doc の文書では ```` ```motion ```` のブロックに場面 1 つを書くと、画面に入ったら動いて完成した図で止まる図になる
  （md-to-doc の SKILL.md の 4f）。仕組みは `figure.py`（`build_figure`・`runtime`）と `figure.js`（`window.MotionFigure`）。
  ほかの HTML でも、`figure.build_figure(場面, 明るい配色, 暗い配色, {caption, loop, width})` の断片を並べ、`figure.runtime()` を 1 度入れれば使える。
