#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is not set}"

DB_WAIT_TIMEOUT_SECONDS="${DB_WAIT_TIMEOUT_SECONDS:-60}"
DB_POLL_INTERVAL_SECONDS=2
DB_CONNECT_TIMEOUT_SECONDS=2

# The host and port come from DATABASE_URL, not from separate variables that could disagree with
# it. URL parsing in shell breaks on IPv6 literals and credentials with reserved characters.
db_endpoint=$(node -e '
  const url = new URL(process.env.DATABASE_URL);
  process.stdout.write(url.hostname.replace(/^\[|\]$/g, "") + " " + (url.port || "5432"));
')
db_host=${db_endpoint% *}
db_port=${db_endpoint#* }

deadline=$(($(date +%s) + DB_WAIT_TIMEOUT_SECONDS))
echo "Waiting for the database at ${db_host}:${db_port} (up to ${DB_WAIT_TIMEOUT_SECONDS}s)..."
until nc -z -w "$DB_CONNECT_TIMEOUT_SECONDS" "$db_host" "$db_port" >/dev/null 2>&1; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "Database ${db_host}:${db_port} did not accept connections within ${DB_WAIT_TIMEOUT_SECONDS}s" >&2
        exit 1
    fi
    sleep "$DB_POLL_INTERVAL_SECONDS"
done

if [ "${PRISMA_GENERATE_ON_START:-false}" = "true" ]; then
    npx prisma generate
fi

npx prisma migrate deploy

exec "$@"
