#!/bin/bash
set -e

DOWNLOAD_DIR="${1:-$HOME/Downloads}"
ARCH=$(dpkg --print-architecture)

echo "==> Fetching latest Obsidian release..."
RELEASE_JSON=$(curl -fsSL https://api.github.com/repos/obsidianmd/obsidian-releases/releases/latest)

ASSET_URL=$(echo "$RELEASE_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
arch = '$ARCH'
for asset in data['assets']:
    if asset['name'].endswith(f'_{arch}.deb'):
        print(asset['browser_download_url'])
        break
else:
    sys.exit(1)
") || { echo "ERROR: No .deb found for ${ARCH}"; exit 1; }

DEB_NAME=$(basename "$ASSET_URL")
DEB_PATH="$DOWNLOAD_DIR/$DEB_NAME"

echo "==> Downloading $DEB_NAME..."
mkdir -p "$DOWNLOAD_DIR"
curl -fL -o "$DEB_PATH" "$ASSET_URL"
echo "    Saved to $DEB_PATH"

echo "==> Installing Obsidian..."
sudo apt install -y "$DEB_PATH"

echo "==> Creating obsidian-jp wrapper..."
mkdir -p ~/.local/bin
cat > ~/.local/bin/obsidian-jp << 'EOF'
#!/bin/bash
if [ -z "$(pgrep -u $USER fcitx5)" ]; then
    fcitx5 -d --disable=wayland,waylandim
fi
exec env XMODIFIERS=@im=fcitx /opt/Obsidian/obsidian --disable-gpu "$@"
EOF
chmod +x ~/.local/bin/obsidian-jp

echo "==> Updating .desktop file..."
mkdir -p ~/.local/share/applications
cp /usr/share/applications/obsidian.desktop ~/.local/share/applications/obsidian.desktop
sed -i "s|Exec=/opt/Obsidian/obsidian|Exec=$HOME/.local/bin/obsidian-jp|g" \
    ~/.local/share/applications/obsidian.desktop

echo ""
echo "Done! Launch Obsidian with Japanese input support:"
echo "  obsidian-jp"
