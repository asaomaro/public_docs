#!/usr/bin/env bash
set -euo pipefail

echo "=== Team Task Manager: Dev Container Setup ==="

# ── 1. Install Java (required for Firebase Emulators) ──────────────────────────
echo "[1/6] Checking Java..."
if ! java -version &>/dev/null; then
  echo "  Installing OpenJDK 21..."
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends openjdk-21-jre-headless
fi
java -version

# ── 2. Install Firebase CLI globally ──────────────────────────────────────────
echo "[2/6] Installing Firebase CLI..."
npm install -g firebase-tools@latest
firebase --version

# ── 3. Install root dependencies ──────────────────────────────────────────────
echo "[3/6] Installing root npm dependencies..."
cd /workspaces/team-task-manager
npm install

# ── 4. Install Cloud Functions dependencies ───────────────────────────────────
echo "[4/6] Installing Cloud Functions npm dependencies..."
cd /workspaces/team-task-manager/functions
npm install

# ── 5. Build Cloud Functions (TypeScript → JavaScript) ───────────────────────
echo "[5/6] Building Cloud Functions..."
npm run build

cd /workspaces/team-task-manager

# ── 6. Set up .env if it doesn't exist ────────────────────────────────────────
echo "[6/6] Checking .env file..."
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "  Copied .env.example → .env"
    echo "  NOTE: Edit .env and fill in your Firebase project credentials."
    echo "        For emulator-only development, the placeholder values are sufficient."
  fi
else
  echo "  .env already exists, skipping."
fi

# ── Emulator data directory ────────────────────────────────────────────────────
if [ ! -d emulator-data ]; then
  mkdir -p emulator-data
  echo "  Created emulator-data/ directory for Firebase Emulator persistence."
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Available commands:"
echo "  npm run dev        – Start Vite dev server (port 5173)"
echo "  npm run emulators  – Start Firebase Emulators (ports: auth=9199, firestore=8180, storage=9299, ui=4100)"
echo "  npm run build      – Type-check and build for production"
echo "  npm run lint       – Run ESLint"
echo "  npm run seed       – Seed Firestore emulator with sample data"
echo ""
echo "Tip: Run 'npm run emulators' in one terminal and 'npm run dev' in another."
