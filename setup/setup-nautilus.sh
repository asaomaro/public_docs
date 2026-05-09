#!/bin/bash
set -e

echo "=== Installing Nautilus ==="
if command -v nautilus &>/dev/null; then
  echo "✓ Nautilus already installed: $(nautilus --version 2>&1 | head -1)"
else
  sudo apt-get update -qq
  sudo apt-get install -y nautilus
  echo "✓ Nautilus installed: $(nautilus --version 2>&1 | head -1)"
fi

echo "=== Setup complete ==="
echo ""
echo "Usage:"
echo "  nautilus                  # ホームディレクトリを開く"
echo "  nautilus <path>           # 指定ディレクトリを開く"
echo "  nautilus --no-desktop     # デスクトップ統合なしで起動"
