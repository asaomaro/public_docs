# -*- coding: utf-8 -*-
"""ブラウザ受け入れ確認のための**固定の**入力を作る。

作業ツリーの差分を入力にすると、リポジトリの状態で検査が通ったり落ちたりする
（実際に 2 度踏んだ: スレッド 150 件が作れない / 展開ボタンが無い / ツリーの
ディレクトリが無い）。**検査の前提は入力側で作る。**

含めるもの:
  - 2 階層以上のディレクトリ（ツリー表示の検査用）
  - 隙間のある変更ファイル（段階展開・すべて展開の検査用。展開の上限を超えない大きさ）
  - **先頭行から始まるハンク ＋ 後ろにも隙間**（すべて展開の回帰。ここが壊れていた）
  - 新規ファイル・削除ファイル（片側しか無い差分）
  - 置き換えの多い変更（split の対応づけの検査用）
  - rich の対象（Markdown＋mermaid＋alert / CSV）
"""
import io, os, shutil, subprocess, sys


def run(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write(repo, path, text):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with io.open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def numbered(prefix, n):
    return "\n".join("%s %d" % (prefix, i) for i in range(1, n + 1)) + "\n"


def build(repo):
    if os.path.exists(repo):
        shutil.rmtree(repo)
    os.makedirs(repo)
    run(repo, "init", "-q", ".")
    run(repo, "config", "user.email", "fixture@example.invalid")
    run(repo, "config", "user.name", "fixture")

    # --- 1 つめのコミット（変更前）
    write(repo, "src/core/engine.py", numbered("engine", 120))
    write(repo, "src/core/util.py", numbered("util", 40))
    write(repo, "src/api/handler.py", numbered("handler", 80))
    write(repo, "src/api/legacy.py", numbered("legacy", 25))          # あとで削除する
    write(repo, "docs/guide.md", "# 手引き\n\n最初の段落。\n")
    write(repo, "data/rows.csv", "id,name,qty\n1,alpha,10\n2,beta,20\n3,gamma,30\n")
    run(repo, "add", "-A")
    run(repo, "-c", "commit.gpgsign=false", "commit", "-qm", "before")

    # --- 2 つめ（変更後）
    # (a) 先頭行から始まるハンク ＋ 後ろにも隙間（すべて展開の回帰）
    lines = ["engine %d" % i for i in range(1, 121)]
    lines[0] = "engine 1 — 先頭を変更"
    lines[99] = "engine 100 — 後ろも変更"
    write(repo, "src/core/engine.py", "\n".join(lines) + "\n")

    # (b) 置き換えの多い変更（split の対応づけ）＋ 片側だけの行
    lines = ["util %d" % i for i in range(1, 41)]
    for i in (9, 10, 11):
        lines[i] = "util %d — 置き換え" % (i + 1)
    del lines[20]                                   # 削除だけの行
    lines.insert(30, "util — 追加だけの行")          # 追加だけの行
    write(repo, "src/core/util.py", "\n".join(lines) + "\n")

    # (c) 真ん中だけの変更（前後に隙間がある＝段階展開）
    lines = ["handler %d" % i for i in range(1, 81)]
    lines[39] = "handler 40 — 変更"
    write(repo, "src/api/handler.py", "\n".join(lines) + "\n")

    # (d) 削除ファイル
    os.remove(os.path.join(repo, "src/api/legacy.py"))

    # (e) 新規ファイル
    write(repo, "src/api/router.py", numbered("router", 12))

    # (f) rich の対象（Markdown＋mermaid＋alert）
    write(repo, "docs/guide.md", """# 手引き

最初の段落を**書き換えた**。

> [!NOTE]
> これは alert 記法。

```mermaid
flowchart LR
  A["読む"] --> B["指摘する"] --> C["直す"]
```

| 列 | 説明 |
|---|---|
| a | あ |
| b | い |
""")

    # (g) rich の対象（CSV。セルの変更と行の増減）
    write(repo, "data/rows.csv", "id,name,qty\n1,alpha,11\n2,beta,20\n4,delta,40\n")
    run(repo, "add", "-A")
    return repo


if __name__ == "__main__":
    # 使い方: python3 tests/fixture_repo.py <出力先>
    #   → その場に git リポジトリを作り、変更を staged にした状態で終わる。
    #     あとは `diff_review.py html --repo <出力先> --from staged` で画面が作れる。
    repo = sys.argv[1] if len(sys.argv) > 1 else "fixture-repo"
    build(repo)
    print(os.path.abspath(repo))
