#!/bin/bash
set -e

echo "Setting up development environment..."

# --- 1. Install Poetry ---
if ! command -v poetry &> /dev/null; then
  curl -sSL https://install.python-poetry.org | python3 -
  export PATH="$HOME/.local/bin:$PATH"
fi

# --- 2. Install project dependencies ---
poetry install

# --- 3. Copy .env template if not already present ---
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env created from .env.example"
    echo "   Fill in the secret values (especially DATABASE_URL) before running the app."
  else
    echo ""
    echo "⚠️  No .env.example found. Create a .env file with at least:"
    echo "   DATABASE_URL=postgresql://user:password@localhost:5432/mydb"
  fi
fi

# --- 4. Done ---
echo ""
echo "✅ Setup complete!"
echo "   Run 'poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000' to start the API."
echo "   Or use 'poetry run alembic upgrade head' to run database migrations."
