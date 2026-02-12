#!/bin/sh
set -e

echo "Starting NestJS API..."

# Wait for database to be ready
echo "Waiting for database to be ready..."
until nc -z ${DATABASE_HOST:-db} ${DATABASE_PORT:-5432}; do
    echo "Database is unavailable - sleeping"
    sleep 2
done
echo "Database is ready!"

# Run TypeORM migrations
echo "Running database migrations..."
npx typeorm migration:run -d dist/config/data-source.js
echo "Migrations completed!"

echo "Setup complete! Starting application..."

# Execute the main command
exec "$@"
