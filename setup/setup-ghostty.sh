#!/bin/bash
set -e

DOWNLOAD_DIR="${1:-$HOME/Downloads}"
ARCH=$(dpkg --print-architecture)
UBUNTU_VERSION=$(lsb_release -rs)

echo "==> Fetching latest ghostty-ubuntu release for Ubuntu ${UBUNTU_VERSION} (${ARCH})..."
RELEASE_JSON=$(curl -fsSL https://api.github.com/repos/mkasberg/ghostty-ubuntu/releases/latest)

ASSET_URL=$(echo "$RELEASE_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
arch = '$ARCH'
ver = '$UBUNTU_VERSION'
for asset in data['assets']:
    if f'_{arch}_{ver}.deb' in asset['name']:
        print(asset['browser_download_url'])
        break
else:
    sys.exit(1)
") || { echo "ERROR: No .deb found for Ubuntu ${UBUNTU_VERSION} (${ARCH})"; exit 1; }

DEB_NAME=$(basename "$ASSET_URL")
DEB_PATH="$DOWNLOAD_DIR/$DEB_NAME"

echo "==> Downloading $DEB_NAME..."
mkdir -p "$DOWNLOAD_DIR"
curl -fL -o "$DEB_PATH" "$ASSET_URL"
echo "    Saved to $DEB_PATH"

echo "==> Installing Ghostty..."
sudo apt install -y "$DEB_PATH"

echo "==> Creating ghostty-jp wrapper..."
mkdir -p ~/.local/bin
cat > ~/.local/bin/ghostty-jp << 'EOF'
#!/bin/bash
if [ -z "$(pgrep -u $USER fcitx5)" ]; then
    fcitx5 -d --disable=wayland,waylandim
fi
exec env GDK_BACKEND=x11 GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx /usr/bin/ghostty "$@"
EOF
chmod +x ~/.local/bin/ghostty-jp

echo "==> Updating .desktop file..."
mkdir -p ~/.local/share/applications
cp /usr/share/applications/com.mitchellh.ghostty.desktop ~/.local/share/applications/
sed -i "s|Exec=/usr/bin/ghostty|Exec=$HOME/.local/bin/ghostty-jp|g" \
    ~/.local/share/applications/com.mitchellh.ghostty.desktop

echo ""
echo "Done! Launch Ghostty with Japanese input support:"
echo "  ghostty-jp"
