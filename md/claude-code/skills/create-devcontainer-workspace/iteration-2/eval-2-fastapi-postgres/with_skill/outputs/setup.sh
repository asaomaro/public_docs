#!/bin/bash
set -e

echo "Setting up development environment..."

# --- 1. Install project dependencies ---
if [ -f "pyproject.toml" ] && grep -q 'poetry' pyproject.toml 2>/dev/null; then
  pip install --user poetry
  poetry install
else
  pip install --user -r requirements.txt
fi

# --- 2. Copy .env template if .env does not already exist ---
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env created from .env.example"
    echo "   Fill in DATABASE_URL and any other secret values before running the app."
  else
    echo "ℹ️  No .env.example found. Create a .env file with your DATABASE_URL."
  fi
fi

# --- 3. Done ---
echo ""
echo "✅ Setup complete!"
echo "   Run 'uvicorn main:app --reload --host 0.0.0.0 --port 8000' to start the FastAPI server."
echo "   Make sure PostgreSQL is running and DATABASE_URL is configured in .env"
