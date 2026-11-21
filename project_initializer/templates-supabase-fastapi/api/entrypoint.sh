#!/bin/bash
set -e

echo "Starting FastAPI API (Supabase)..."

# No db container to wait for: the database is the hosted Supabase project, so
# migrations run straight away.
echo "Running database migrations..."
alembic upgrade head
echo "Migrations completed!"

echo "Setup complete! Starting application..."

# exec replaces the shell so uvicorn is PID 1 and receives the SIGTERM that
# docker stop sends, instead of the shell swallowing it.
exec "$@"
