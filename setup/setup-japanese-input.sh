#!/bin/bash
set -e

echo "==> Installing fcitx5-mozc..."
sudo apt install -y fcitx5 fcitx5-mozc fcitx5-config-qt

echo "==> Configuring ~/.bashrc..."
if ! grep -q 'fcitx5-mozc' ~/.bashrc; then
    cat >> ~/.bashrc << 'EOF'

# Japanese input (fcitx5-mozc, X11 mode for WSLg compatibility)
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export GDK_BACKEND=x11
if [ -z "$(pgrep -u $USER fcitx5)" ]; then
    fcitx5 -d --disable=wayland,waylandim &>/dev/null
fi
EOF
fi

echo "==> Configuring ~/.profile..."
if ! grep -q 'GTK_IM_MODULE=fcitx' ~/.profile; then
    cat >> ~/.profile << 'EOF'

# Japanese input (fcitx5-mozc)
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export GDK_BACKEND=x11
EOF
fi

echo "==> Writing fcitx5 profile..."
mkdir -p ~/.config/fcitx5/conf

cat > ~/.config/fcitx5/profile << 'EOF'
[Groups/0]
# Group Name
Name=Default
# Layout
Default Layout=us
# Default Input Method
DefaultIM=mozc

[Groups/0/Items/0]
# Name
Name=keyboard-us
# Layout
Layout=

[Groups/0/Items/1]
# Name
Name=mozc
# Layout
Layout=

[GroupOrder]
0=Default
EOF

echo "==> Disabling fcitx5 Wayland addons (incompatible with WSLg)..."
cat > ~/.config/fcitx5/conf/wayland.conf << 'EOF'
[Addon]
Enabled=False
EOF

cat > ~/.config/fcitx5/conf/waylandim.conf << 'EOF'
[Addon]
Enabled=False
EOF

echo "==> Setting up autostart..."
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/fcitx5.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Fcitx5
Exec=fcitx5 -d --disable=wayland,waylandim
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

echo ""
echo "Done! To apply without restarting, run:"
echo "  pkill fcitx5 2>/dev/null; fcitx5 -d --disable=wayland,waylandim"
