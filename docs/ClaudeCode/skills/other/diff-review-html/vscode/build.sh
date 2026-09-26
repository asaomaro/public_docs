#!/bin/sh
# diff-review-vscode の .vsix を作る。
# Windows 版は同ディレクトリの build.bat（引数・終了コード・メッセージを一致させること）。
#
# 使い方:
#   ./build.sh            いまある out/ と media/viewer.html から .vsix を作る（速い）
#   ./build.sh --build    画面の生成とコンパイルからやり直してから .vsix を作る
#   ./build.sh --help     この説明
#
# 前提:
#   - npm ci 済み（node_modules に @vscode/vsce が要る）
#   - --build のときは Python 3 も要る（画面を ../diff_review.py view から作るため。
#     python3 以外の名前で入っているなら環境変数 PYTHON で指定する）
#
# 終了コード: 0=成功 / 1=前提が足りない・ビルド失敗 / 2=引数が違う
set -eu

# 先頭のコメント（1 行目の #! を除く）をそのまま説明に使う。説明を二重に持たない。
usage() {
  awk 'NR > 1 { if ($0 !~ /^#/) { exit } sub(/^# ?/, ""); print }' "$0"
}

cd "$(dirname "$0")"

build=0
for arg in "$@"; do
  case "$arg" in
    --build) build=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      printf '不明な引数: %s\n\n' "$arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ ! -x node_modules/.bin/vsce ]; then
  echo "node_modules に vsce がありません。先に npm ci を実行してください。" >&2
  exit 1
fi

if [ "$build" -eq 1 ]; then
  npm run build
else
  # 作り直さないときは、中身が揃っているかだけ確かめる。欠けたままだと
  # 「入るけれど何も開けない .vsix」ができてしまい、入れてみるまで気づけない。
  missing=""
  [ -f media/viewer.html ] || missing="$missing media/viewer.html"
  [ -f out/src/extension.js ] || missing="$missing out/src/extension.js"
  if [ -n "$missing" ]; then
    printf 'ビルド成果物がありません:%s\n' "$missing" >&2
    echo "--build を付けて実行してください（例: ./build.sh --build）。" >&2
    exit 1
  fi
fi

node_modules/.bin/vsce package --skip-license
