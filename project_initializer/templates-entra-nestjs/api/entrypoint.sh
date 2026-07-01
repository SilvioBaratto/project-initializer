#!/bin/sh
set -e

echo "Starting NestJS API (Entra)..."

# Generate Prisma client (needed when source is volume-mounted in dev)
echo "Generating Prisma client..."
npx prisma generate

# Run Prisma migrations against local Docker PostgreSQL
echo "Running database migrations..."
npx prisma migrate deploy
echo "Migrations completed!"

echo "Setup complete! Starting application..."

# Execute the main command
exec "$@"
