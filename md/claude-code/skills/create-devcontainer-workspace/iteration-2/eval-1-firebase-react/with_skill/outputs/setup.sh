#!/bin/bash
set -e

echo "=== Setting up team-task-manager development environment ==="

# --- 1. Install root dependencies ---
echo "[1/4] Installing root npm dependencies..."
cd /workspaces/team-task-manager
npm install

# --- 2. Install and build Cloud Functions sub-package ---
echo "[2/4] Installing Cloud Functions dependencies..."
(cd functions && npm install)

echo "[3/4] Building Cloud Functions (TypeScript -> JavaScript)..."
(cd functions && npm run build)

# --- 3. Copy .env template if not present ---
echo "[4/4] Checking .env file..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "  .env created from .env.example"
  echo "  Fill in your Firebase project credentials before running against production."
  echo "  For emulator-only development, placeholder values are sufficient."
else
  echo "  .env already exists, skipping."
fi

# --- Ensure emulator-data directory exists for emulator persistence ---
if [ ! -d emulator-data ]; then
  mkdir -p emulator-data
  echo "  Created emulator-data/ for Firebase Emulator data persistence."
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Available commands:"
echo "  npm run dev        - Start Vite dev server        (http://localhost:5173)"
echo "  npm run emulators  - Start Firebase Emulators"
echo "                         Auth:      http://localhost:9199"
echo "                         Firestore: http://localhost:8180"
echo "                         Storage:   http://localhost:9299"
echo "                         UI:        http://localhost:4100"
echo "  npm run build      - Type-check and build for production"
echo "  npm run lint       - Run ESLint"
echo "  npm run seed       - Seed Firestore emulator with sample data"
echo ""
echo "Tip: Open two terminals — run 'npm run emulators' in one and 'npm run dev' in the other."
