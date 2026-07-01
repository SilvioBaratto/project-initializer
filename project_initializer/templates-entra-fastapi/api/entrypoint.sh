#!/bin/bash
set -e

echo "Starting FastAPI API (Entra)..."

# Run migrations against local Docker PostgreSQL
echo "Running database migrations..."
alembic upgrade head
echo "Migrations completed!"

echo "Setup complete! Starting application..."

# Execute the main command (start uvicorn)
exec "$@"
