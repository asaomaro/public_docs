#!/bin/bash
set -e

echo "Setting up development environment..."

# --- 1. Install root project dependencies ---
echo "Installing root dependencies..."
npm install

# --- 2. Install Firebase Functions dependencies ---
echo "Installing functions dependencies..."
(cd functions && npm install)

# --- 3. Copy .env template if .env doesn't already exist ---
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "  .env created from .env.example"
  echo "   Fill in the VITE_FIREBASE_* values before running the app."
  echo "   (Or set them as environment variables on your host so remoteEnv picks them up.)"
fi

# --- 4. Done ---
echo ""
echo "Setup complete!"
echo ""
echo "Available commands:"
echo "  npm run dev        - Start Vite dev server (port 5173)"
echo "  npm run emulators  - Start Firebase Emulators (UI on port 4100)"
echo "  npm run build      - TypeScript check + production build"
echo "  npm run lint       - Run ESLint"
echo "  npm run deploy     - Build and deploy to Firebase"
