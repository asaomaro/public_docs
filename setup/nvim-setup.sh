#!/bin/bash

NVIM_VERSION="v0.12.2"
INSTALL_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/nvim"

echo "=== Installing nvim ==="
if command -v nvim &>/dev/null; then
  echo "✓ nvim already installed: $(nvim --version | head -1)"
else
  url="https://github.com/neovim/neovim/releases/download/${NVIM_VERSION}/nvim-linux-x86_64.tar.gz"
  tmp=$(mktemp -d)
  curl -L "$url" -o "$tmp/nvim.tar.gz"
  tar -xzf "$tmp/nvim.tar.gz" -C "$tmp"
  mkdir -p "$INSTALL_DIR"
  cp "$tmp/nvim-linux-x86_64/bin/nvim" "$INSTALL_DIR/nvim"
  chmod +x "$INSTALL_DIR/nvim"
  rm -rf "$tmp"
  if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$HOME/.bashrc"
    export PATH="$INSTALL_DIR:$PATH"
  fi
  echo "✓ nvim $(nvim --version | head -1) installed"
fi

echo "=== Configuring nvim ==="
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/init.lua" << 'EOF'
-- Bootstrap lazy.nvim
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({
    "git", "clone", "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

-- Basic options
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.expandtab = true
vim.opt.tabstop = 2
vim.opt.shiftwidth = 2
vim.opt.termguicolors = true
vim.opt.signcolumn = "yes"
vim.g.mapleader = " "

-- Plugins
require("lazy").setup({

  -- File explorer
  {
    "nvim-tree/nvim-tree.lua",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("nvim-tree").setup({
        view = { width = 30 },
        renderer = { group_empty = true },
        filters = { dotfiles = false },
      })
      vim.keymap.set("n", "<leader>e", ":NvimTreeToggle<CR>", { desc = "Toggle file tree" })
    end,
  },

  -- Fuzzy finder
  {
    "nvim-telescope/telescope.nvim",
    dependencies = { "nvim-lua/plenary.nvim" },
    config = function()
      local builtin = require("telescope.builtin")
      vim.keymap.set("n", "<leader>ff", builtin.find_files, { desc = "Find files" })
      vim.keymap.set("n", "<leader>fg", builtin.live_grep,  { desc = "Live grep" })
      vim.keymap.set("n", "<leader>fb", builtin.buffers,    { desc = "Buffers" })
    end,
  },

  -- Statusline
  {
    "nvim-lualine/lualine.nvim",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("lualine").setup({ options = { theme = "auto" } })
    end,
  },

  -- Syntax highlighting
  {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    config = function()
      require("nvim-treesitter").setup({
        ensure_installed = { "lua", "vim", "python", "javascript", "typescript", "bash" },
        highlight = { enable = true },
        indent = { enable = true },
      })
    end,
  },

  -- Git signs
  {
    "lewis6991/gitsigns.nvim",
    config = function()
      require("gitsigns").setup({
        signs = {
          add    = { text = "+" },
          change = { text = "~" },
          delete = { text = "-" },
        },
      })
      vim.keymap.set("n", "<leader>gb", ":Gitsigns blame_line<CR>", { desc = "Git blame line" })
      vim.keymap.set("n", "]h", ":Gitsigns next_hunk<CR>",          { desc = "Next hunk" })
      vim.keymap.set("n", "[h", ":Gitsigns prev_hunk<CR>",          { desc = "Prev hunk" })
    end,
  },

})
EOF
echo "✓ nvim configured"

echo "=== Installing plugins ==="
nvim --headless "+Lazy! sync" +qa 2>&1
echo "✓ plugins installed"

echo "=== Setup complete ==="
