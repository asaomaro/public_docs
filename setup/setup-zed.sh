#!/bin/bash
set -e

echo "==> Installing Zed..."
curl -f https://zed.dev/install.sh | sh

ZED_BIN="$HOME/.local/zed.app/bin/zed"

echo "==> Creating zed-jp wrapper..."
mkdir -p ~/.local/bin
cat > ~/.local/bin/zed-jp << EOF
#!/bin/bash
if [ -z "\$(pgrep -u \$USER fcitx5)" ]; then
    fcitx5 -d --disable=wayland,waylandim
fi
exec env -u WAYLAND_DISPLAY XMODIFIERS=@im=fcitx "$ZED_BIN" "\$@"
EOF
chmod +x ~/.local/bin/zed-jp

echo "==> Updating .desktop file..."
DESKTOP="$HOME/.local/share/applications/dev.zed.Zed.desktop"
if [ -f "$DESKTOP" ]; then
    sed -i "s|Exec=$ZED_BIN|Exec=$HOME/.local/bin/zed-jp|g" "$DESKTOP"
fi

echo ""
echo "Done! Launch Zed with Japanese input support:"
echo "  zed-jp"
