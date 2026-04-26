#!/bin/sh

set -e

echo "Waiting for database to be ready..."
max_attempts=30
attempt=0
db_host="${DB_HOST:-db}"
db_port="${DB_PORT:-5432}"

# ... existing code ...
while [ $attempt -lt $max_attempts ]; do
    # Try to connect to PostgreSQL
    if python3 -c "import psycopg2; psycopg2.connect(host='$db_host', port='$db_port', user='${POSTGRES_USER:-first_exam}', password='${POSTGRES_PASSWORD:-first_exam}', database='${POSTGRES_DB:-auto_repair_shop}', connect_timeout=5)" > /dev/null 2>&1; then
        echo "✓ Database is ready"
        break
    fi
    echo "  Waiting for database... ($((attempt + 1))/$max_attempts)"
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "⚠️ Database did not become ready, but attempting to start application anyway..."
fi

echo "Running database migrations..."
alembic upgrade head || echo "⚠️ Alembic upgrade failed, continuing..."

echo "Running seed..."
python3 -m app.seed || echo "⚠️ Seed failed, continuing..."

echo "Starting FastAPI application on port ${PORT:-8080}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --proxy-headers --forwarded-allow-ips='*'

