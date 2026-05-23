#!/bin/bash
set -euo pipefail

INSTALL_ROOT="$HOME/.local"
INSTALL_DIR="$INSTALL_ROOT/bin"
NVIM_BIN="$INSTALL_DIR/nvim"
RUNTIME_MARKER="$INSTALL_ROOT/share/nvim/runtime/lua/vim/uri.lua"
CONFIG_DIR="$HOME/.config/nvim"

# --- Determine release asset for this architecture ---
case "$(uname -m)" in
  x86_64)          NVIM_ARCH="x86_64" ; RG_ARCH="x86_64-unknown-linux-musl" ;;
  aarch64 | arm64) NVIM_ARCH="arm64"  ; RG_ARCH="aarch64-unknown-linux-musl" ;;
  *) echo "✗ Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac
ASSET="nvim-linux-${NVIM_ARCH}.tar.gz"

# --- Resolve the latest version tag ---
NVIM_VERSION=$(curl -fsSL https://api.github.com/repos/neovim/neovim/releases/latest \
  | grep '"tag_name"' | cut -d'"' -f4 || true)
if [ -z "$NVIM_VERSION" ]; then
  echo "✗ Could not resolve the latest nvim version (GitHub API rate limit or network error)." >&2
  exit 1
fi

# --- Decide whether a (re)install is needed ---
need_install=true
if [ -x "$NVIM_BIN" ] && [ -f "$RUNTIME_MARKER" ]; then
  installed=$("$NVIM_BIN" --version 2>/dev/null | head -1 | awk '{print $2}')
  if [ "$installed" = "$NVIM_VERSION" ]; then
    need_install=false
    echo "✓ nvim already up to date: $installed"
  else
    echo "→ nvim $installed installed; upgrading to $NVIM_VERSION"
  fi
elif [ -x "$NVIM_BIN" ]; then
  # binary present but runtime missing → previous install was incomplete
  echo "→ nvim binary found but runtime is missing; reinstalling"
fi

echo "=== Installing ripgrep ==="
if command -v rg &>/dev/null; then
  echo "✓ ripgrep already installed: $(rg --version | head -1)"
else
  RG_VERSION=$(curl -fsSL https://api.github.com/repos/BurntSushi/ripgrep/releases/latest \
    | grep '"tag_name"' | cut -d'"' -f4 || true)
  if [ -z "$RG_VERSION" ]; then
    echo "✗ Could not resolve the latest ripgrep version." >&2; exit 1
  fi
  rg_url="https://github.com/BurntSushi/ripgrep/releases/download/${RG_VERSION}/ripgrep-${RG_VERSION}-${RG_ARCH}.tar.gz"
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  curl -fSL "$rg_url" -o "$tmp/rg.tar.gz"
  tar -xzf "$tmp/rg.tar.gz" -C "$tmp"
  cp "$tmp/ripgrep-${RG_VERSION}-${RG_ARCH}/rg" "$INSTALL_DIR/rg"
  export PATH="$INSTALL_DIR:$PATH"
  echo "✓ ripgrep $(rg --version | head -1) installed"
fi

echo "=== Installing nvim ==="
if [ "$need_install" = true ]; then
  url="https://github.com/neovim/neovim/releases/download/${NVIM_VERSION}/${ASSET}"
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT

  # -f: fail (non-zero) on HTTP errors instead of saving the error page
  curl -fSL "$url" -o "$tmp/nvim.tar.gz"

  # Verify the download is a real gzip archive before touching the install dir
  if ! gzip -t "$tmp/nvim.tar.gz" 2>/dev/null; then
    echo "✗ Downloaded file is not a valid archive: $url" >&2
    exit 1
  fi

  mkdir -p "$INSTALL_ROOT"
  tar -xzf "$tmp/nvim.tar.gz" -C "$INSTALL_ROOT" --strip-components=1

  # Confirm the runtime actually landed (the part that broke before)
  if [ ! -f "$RUNTIME_MARKER" ]; then
    echo "✗ Extraction incomplete: nvim runtime not found at $RUNTIME_MARKER" >&2
    exit 1
  fi

  if ! grep -q "$INSTALL_DIR" "$HOME/.bashrc" 2>/dev/null; then
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$HOME/.bashrc"
  fi
  export PATH="$INSTALL_DIR:$PATH"
  echo "✓ nvim $("$NVIM_BIN" --version | head -1) installed"
fi

echo "=== Configuring nvim ==="
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/init.lua" << 'EOF'
-- Bootstrap lazy.nvim
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
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

  -- Colorscheme
  {
    "folke/tokyonight.nvim",
    lazy = false,
    priority = 1000,
    opts = { style = "night" },
    config = function(_, opts)
      require("tokyonight").setup(opts)
      vim.cmd("colorscheme tokyonight")
    end,
  },

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
      require("lualine").setup({ options = { theme = "tokyonight" } })
    end,
  },

  -- Syntax highlighting
  {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    config = function()
      require("nvim-treesitter.configs").setup({
        ensure_installed = { "lua", "vim", "python", "javascript", "typescript", "bash" },
        highlight = { enable = true },
        indent = { enable = true },
      })
    end,
  },

  -- Markdown rendering
  {
    "MeanderingProgrammer/render-markdown.nvim",
    dependencies = {
      "nvim-treesitter/nvim-treesitter",
      "nvim-tree/nvim-web-devicons",
    },
    opts = {},
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
"$NVIM_BIN" --headless "+Lazy! sync" +qa 2>&1
echo "✓ plugins installed"

echo "=== Installing Treesitter parsers ==="
"$NVIM_BIN" --headless "+TSInstall markdown markdown_inline" +qa 2>&1
echo "✓ Treesitter parsers installed"

echo "=== Setup complete ==="
