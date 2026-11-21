#!/bin/bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"
DB_WAIT_TIMEOUT_SECONDS="${DB_WAIT_TIMEOUT_SECONDS:-60}"
DB_WAIT_INTERVAL_SECONDS=2
POSTGRES_DEFAULT_PORT=5432

# Waiting on the host the application will actually connect to: a hardcoded
# host would hang forever, or pass against the wrong server, as soon as the
# database is not the compose service.
database_endpoint="$(python -c '
import sys
from urllib.parse import urlsplit

url = urlsplit(sys.argv[1])
print(url.hostname or "localhost", url.port or sys.argv[2], url.username or "postgres")
' "$DATABASE_URL" "$POSTGRES_DEFAULT_PORT")"
read -r database_host database_port database_user <<< "$database_endpoint"

deadline=$((SECONDS + DB_WAIT_TIMEOUT_SECONDS))
until pg_isready --quiet --host "$database_host" --port "$database_port" \
    --username "$database_user" --timeout "$DB_WAIT_INTERVAL_SECONDS"; do
    if ((SECONDS >= deadline)); then
        echo "Database ${database_host}:${database_port} not ready after ${DB_WAIT_TIMEOUT_SECONDS}s" >&2
        exit 1
    fi
    echo "Waiting for database ${database_host}:${database_port}..."
    sleep "$DB_WAIT_INTERVAL_SECONDS"
done

# Alembic takes no lock of its own, so replicas that start together would race
# on the same migration. Run one migration job before scaling out, and keep
# this step for single-instance deployments such as the compose stack.
alembic upgrade head

exec "$@"
