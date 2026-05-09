#!/bin/bash
set -e

echo "=== Installing w3m and w3m-img ==="
if command -v w3m &>/dev/null; then
  echo "✓ w3m already installed: $(w3m -version 2>&1 | head -1)"
else
  sudo apt-get update -qq
  sudo apt-get install -y w3m w3m-img
  echo "✓ w3m installed: $(w3m -version 2>&1 | head -1)"
fi

echo "=== Setup complete ==="
echo ""
echo "Usage:"
echo "  w3m <URL>          # テキストブラウザで開く"
echo "  w3m -o display_image=1 <URL>  # 画像表示を有効化"
