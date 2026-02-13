#!/bin/sh
set -e

echo "Starting NestJS API (Supabase)..."

# Run Prisma migrations against hosted Supabase DB
echo "Running database migrations..."
npx prisma migrate deploy
echo "Migrations completed!"

echo "Setup complete! Starting application..."

# Execute the main command
exec "$@"
