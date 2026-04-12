# Ubuntu Base DevContainer Image

Ubuntu 24.04ベースイメージをtarで配布し、devcontainerとして使用するための手順です。

---

## ファイル構成

```
.
├── Dockerfile
├── devcontainer.json（参考）
└── README.md
```

---

## Dockerfile

```dockerfile
FROM ubuntu:24.04

CMD ["/bin/bash"]
```

```dockerfile
FROM ubuntu:24.04

RUN apt-get update -q && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
```

> tmuxなどの開発ツールは`devcontainer.json`側でインストールします。

---

## イメージのビルド

Dockerfileがあるディレクトリで以下を実行します。

```bash
docker build -t dev_ubuntu:latest .
```

---

## イメージの書き出し

配布用にtarファイルへ書き出します。

```bash
docker save -o dev_ubuntu.tar dev_ubuntu:latest
```

---

## tarファイルの分割（GitHubの50MB制限対策）

GitHubにプッシュする場合、50MB制限のためtarファイルを分割します。

```bash
split -b 10m dev_ubuntu.tar dev_ubuntu.tar.part_
```

分割されたファイルを確認します。

```bash
ls dev_ubuntu.tar.part_*
# dev_ubuntu.tar.part_aa
# dev_ubuntu.tar.part_ab
# dev_ubuntu.tar.part_ac
# ...
```

分割ファイルをGitにコミットします。

```bash
git add dev_ubuntu.tar.part_*
git commit -m "Add docker image"
git push
```

> `dev_ubuntu.tar`本体は`.gitignore`に追加しておくことを推奨します。
> ```
> dev_ubuntu.tar
> ```

---

## イメージのロード（配布先での手順）

分割ファイルをクローン後、まずtarファイルに復元します。

```bash
cat dev_ubuntu.tar.part_* > dev_ubuntu.tar
```

復元したtarファイルからイメージを読み込みます。

```bash
docker load -i dev_ubuntu.tar
```

ロード後にイメージが存在することを確認します。

```bash
docker images dev_ubuntu
```

---

## devcontainerとして使用する

### 1. リポジトリのクローン

WSL2のターミナルでクローンします（Windows側の`/mnt/`配下は避けてください）。

```bash
cd ~/projects
git clone https://github.com/yourorg/yourrepo.git
cd yourrepo
```

### 2. devcontainer.jsonの作成

リポジトリ直下に`.devcontainer/devcontainer.json`を作成します。

```json
{
  "name": "dev_ubuntu",
  "image": "dev_ubuntu:latest",
  "postStartCommand": "apt-get update -q && apt-get install -y --no-install-recommends tmux xclip && apt-get clean"
}
```

### 3. VSCodeで開く

```bash
code .
```

VSCodeが「コンテナで再度開く」を提案するので、それをクリックします。
または、コマンドパレット（`Ctrl+Shift+P`）から`Dev Containers: Reopen in Container`を実行します。

---

## tmuxの起動

devcontainer内のターミナルで以下を実行します。

```bash
tmux new -s main
```

### 主なキー操作（デフォルトキーバインド）

| 操作 | キー |
|------|------|
| ペインを左右分割 | `Ctrl+b` → `%` |
| ペインを上下分割 | `Ctrl+b` → `"` |
| ペイン移動 | `Ctrl+b` → 矢印キー |
| 新しいウィンドウ | `Ctrl+b` → `c` |
| セッションをデタッチ | `Ctrl+b` → `d` |
| セッションに再接続 | `tmux attach -t main` |
