#!/bin/bash
# ============================================================
# Backend Entrypoint Script
# Handles database readiness and migrations
# ============================================================

set -e

echo "============================================================"
echo "Identity Hub Backend - Starting..."
echo "============================================================"

# Wait for database to be ready
echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" > /dev/null 2>&1; then
        echo "Database is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for database... (${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: Database not ready after ${MAX_RETRIES} retries"
    exit 1
fi

# Run database migrations
echo "Running database migrations..."

if [ -f "alembic.ini" ]; then
    alembic upgrade head || {
        echo "Alembic migration failed, using fallback table creation..."
        python -c "
from database import engine, Base
import asyncio
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created via fallback')
asyncio.run(create_tables())
"
    }
else
    echo "No alembic.ini found, using direct table creation..."
    python -c "
from database import engine, Base
import asyncio
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created')
asyncio.run(create_tables())
"
fi

echo "Migrations complete!"

# Start the application
echo "Starting uvicorn server..."
exec uvicorn server:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
