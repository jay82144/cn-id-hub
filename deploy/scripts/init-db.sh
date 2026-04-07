#!/bin/bash
# ============================================================
# PostgreSQL Initialization Script for Identity Hub
# This runs automatically on first database creation
# ============================================================

set -e

echo "Initializing Identity Hub database..."

# Create the ID app user and grant permissions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create the ID app user if not exists
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER:-id_app_user}') THEN
            CREATE USER ${DB_USER:-id_app_user} WITH PASSWORD '${DB_PASSWORD}';
        END IF;
    END
    \$\$;

    -- Grant privileges on the database
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${DB_USER:-id_app_user};
    
    -- Grant schema permissions
    GRANT ALL ON SCHEMA public TO ${DB_USER:-id_app_user};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER:-id_app_user};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER:-id_app_user};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO ${DB_USER:-id_app_user};
EOSQL

echo "Identity Hub database initialized successfully"
echo "  Database: ${POSTGRES_DB}"
echo "  User: ${DB_USER:-id_app_user}"
