#!/bin/bash

echo "=== Installing packages ==="
sudo apt-get update -q
sudo apt-get install -y --no-install-recommends tmux xclip
sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*
echo "✓ tmux, xclip installed"

echo "=== Configuring tmux ==="
cat > ~/.tmux.conf << 'TMUX_CONF'
# インデックスを1始まりに
set -g base-index 1
setw -g pane-base-index 1

# 256色 + True Color対応
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"

# マウス操作を有効化
set -g mouse on

# ウィンドウ番号の自動リナンバリング
set -g renumber-windows on

# ステータスバー設定
set -g status-position bottom
set -g status-bg colour234
set -g status-fg colour137
set -g status-left '#[fg=colour233,bg=colour241,bold] #S '
set -g status-right '#[fg=colour233,bg=colour241,bold] %Y-%m-%d %H:%M '
set -g status-right-length 50
set -g status-left-length 20

# ウィンドウステータス
setw -g window-status-current-format '#[fg=colour81,bg=colour238,bold] #I:#W '
setw -g window-status-format '#[fg=colour138,bg=colour235] #I:#W '

# コピーモードの設定 (Vimキーバインド)
setw -g mode-keys vi
bind-key -T copy-mode-vi v send-keys -X begin-selection
bind-key -T copy-mode-vi y send-keys -X copy-selection-and-cancel

# エスケープタイムを短縮 (Vimとの干渉防止)
set -sg escape-time 10

# ヒストリーの行数
set -g history-limit 50000

# アクティビティ通知
setw -g monitor-activity on
set -g visual-activity off
TMUX_CONF
echo "✓ tmux configured"

echo "=== Setup complete ==="
