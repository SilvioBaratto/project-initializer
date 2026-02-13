#!/bin/bash
set -e

echo "Starting FastAPI API (Supabase)..."

# Run migrations against hosted Supabase DB
echo "Running database migrations..."
alembic upgrade head
echo "Migrations completed!"

echo "Setup complete! Starting application..."

# Execute the main command (start uvicorn)
exec "$@"
