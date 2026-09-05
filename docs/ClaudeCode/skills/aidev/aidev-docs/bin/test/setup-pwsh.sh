#!/bin/sh
# aidev.ps1 を検証するための PowerShell を用意する（Linux / macOS 用）
#
# なぜ要るか:
#   `aidev` と `aidev.ps1` は**同じ挙動でなければならない**。ところが pwsh の無い環境では
#   test/run.sh のパリティテストが skip され、その分だけ「ps1 が一度も実行されないまま緑」になる。
#   実際、この skip が続いていた間に **ps1 の実バグ2件**（値の無いオプションを素通りして work を
#   作ってしまう／switch が大文字小文字を区別しない）と**テスト自身のバグ2件**が緑の裏に隠れていた。
#   「環境が無い」で穴を放置しないために、入れる手順そのものを実行可能な形で置いてある。
#
# 使い方:
#   sh test/setup-pwsh.sh        # 入れる（既にあれば何もしない）
#   eval "$(sh test/setup-pwsh.sh --env)"   # PATH だけ出す（既に入れてある場合）
#   sh test/run.sh               # そのまま走らせるとパリティテストも動く
#
# 置き場所は AIDEV_PWSH_DIR で変えられる（既定 ~/.cache/aidev-pwsh）。root 権限は要らない。
# Windows では不要（Windows PowerShell 5.1 が標準搭載。run.sh はそちらへ自動でフォールバックする）。
set -eu

# 版は固定する。「最新」を取りに行くと、検証した版と CI で走る版が黙ってずれる
PWSH_VERSION=${PWSH_VERSION:-7.4.6}
DEST=${AIDEV_PWSH_DIR:-"${HOME:-/tmp}/.cache/aidev-pwsh"}

# 配布物の SHA-256（この版の linux-x64 / linux-arm64）。ダウンロードの改竄・破損を検出する。
# 版を上げるときは、公式リリースページのハッシュに合わせてここも更新すること
SHA_linux_x64=6f6015203c47806c5cc444c19d8ed019695e610fbd948154264bf9ca8e157561

# 先頭のコメント帯だけを出す（行番号を直書きすると、1行足すたびに使い方が壊れる）
usage() { awk 'NR>1 && /^#/ {print; next} NR>1 {exit}' "$0"; exit 0; }

case "${1:-}" in
  --help|-h) usage ;;
  --env) printf 'export PATH="%s:$PATH"\n' "$DEST"; exit 0 ;;
  '') ;;
  *) echo "不明な引数: $1（--env | --help）" >&2; exit 2 ;;
esac

if command -v pwsh >/dev/null 2>&1; then
  echo "pwsh は既にあります: $(command -v pwsh) ($(pwsh -v 2>/dev/null))"
  exit 0
fi
if [ -x "$DEST/pwsh" ]; then
  echo "pwsh は $DEST にあります。PATH に足してください:"
  printf '  export PATH="%s:$PATH"\n' "$DEST"
  exit 0
fi

# アーキテクチャの決定。合わない配布物を掴むと、実行して初めて気付くことになる
case "$(uname -s)" in
  Linux) ;;
  Darwin) echo "macOS は Homebrew が確実です: brew install --cask powershell" >&2; exit 1 ;;
  *) echo "この OS 向けの手順はありません（Windows は PowerShell 5.1 が標準搭載）" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64) ARCH=x64; WANT=$SHA_linux_x64 ;;
  # arm64 のハッシュは未確認。**知らないものを検証済みのように扱わない**ので、
  # ハッシュ照合は飛ばすと明示して進める（protocol.md「8.」の「捏造して埋めない」と同じ態度）
  aarch64|arm64) ARCH=arm64; WANT="" ;;
  *) echo "未対応のアーキテクチャ: $(uname -m)" >&2; exit 1 ;;
esac

TARBALL="powershell-$PWSH_VERSION-linux-$ARCH.tar.gz"
URL="https://github.com/PowerShell/PowerShell/releases/download/v$PWSH_VERSION/$TARBALL"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "取得中: $URL"
curl -fsSL -o "$TMP/$TARBALL" "$URL"

if [ -n "$WANT" ]; then
  GOT=$(sha256sum "$TMP/$TARBALL" 2>/dev/null | cut -d' ' -f1) \
    || GOT=$(shasum -a 256 "$TMP/$TARBALL" | cut -d' ' -f1)
  if [ "$GOT" != "$WANT" ]; then
    echo "SHA-256 が一致しません（期待 $WANT / 実際 $GOT）。中断します" >&2
    exit 1
  fi
  echo "SHA-256 照合: OK"
else
  echo "SHA-256: この配布物のハッシュは未登録のため照合していません（linux-$ARCH）"
fi

mkdir -p "$DEST"
tar -xzf "$TMP/$TARBALL" -C "$DEST"
chmod +x "$DEST/pwsh"
"$DEST/pwsh" -v

cat <<MSG

入りました: $DEST/pwsh
このシェルで使うには:

  export PATH="$DEST:\$PATH"
  sh test/run.sh        # RESULT の skip が 0 になるはず

**この置き場所は PATH に足さない限り効きません。** run.sh は pwsh が見つからなければ
パリティテストを skip し、その件数を RESULT と NOTE に出します。skip>0 のまま
「緑だから良し」としないこと——skip はそのまま**未検証の穴**です。
MSG
