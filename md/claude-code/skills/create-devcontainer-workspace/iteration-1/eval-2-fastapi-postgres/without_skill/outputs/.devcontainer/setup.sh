#!/bin/bash
set -e

echo "=== Setting up FastAPI + PostgreSQL development environment ==="

# Navigate to workspace
cd /workspace

# Install Python dependencies
echo "--- Installing Python dependencies ---"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
elif [ -f "pyproject.toml" ]; then
    pip install -e ".[dev]" 2>/dev/null || pip install -e . 2>/dev/null || pip install poetry && poetry install
fi

# Install dev dependencies if pyproject.toml has them
if [ -f "pyproject.toml" ] && grep -q "tool.poetry.dev-dependencies" pyproject.toml; then
    echo "--- Installing dev dependencies (pytest, ruff, httpx) ---"
    pip install pytest httpx ruff 2>/dev/null || true
fi

# Wait for PostgreSQL to be ready
echo "--- Waiting for PostgreSQL to be ready ---"
until pg_isready -h db -U postgres -d appdb 2>/dev/null; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "PostgreSQL is ready!"

# Run database migrations if alembic is configured
if [ -f "alembic.ini" ]; then
    echo "--- Running Alembic migrations ---"
    alembic upgrade head
fi

echo "=== Setup complete! ==="
echo ""
echo "To start the FastAPI server, run:"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs at:              http://localhost:8000/docs"
