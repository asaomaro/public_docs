#!/bin/bash
set -e

echo "Setting up development environment..."

# --- 1. Install project dependencies ---
npm install

# --- 2. One-time initialization ---
# Copy .env template only if .env doesn't already exist
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  .env created from .env.example"
  echo "   Fill in the secret values before running the app."
fi

# --- 3. Done ---
echo ""
echo "✅ Setup complete!"
echo "   Run 'npm run dev' to start the development server on port 3000."
