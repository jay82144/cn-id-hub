#!/bin/bash
# ============================================================
# Bootstrap Script: Create New App Database and User
# ============================================================
# Usage: ./create-app-database.sh <appname>
# 
# This script creates:
# - A new database named <appname>_app
# - A new database user named <appname>_app_user
# - Grants full permissions on the database to the new user
# ============================================================

set -e

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <appname>"
    echo "Example: $0 hrms"
    echo ""
    echo "This will create:"
    echo "  - Database: hrms_app"
    echo "  - User: hrms_app_user"
    exit 1
fi

APP_NAME="$1"
NEW_DB_NAME="${APP_NAME}_app"
NEW_DB_USER="${APP_NAME}_app_user"

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo "ERROR: .env file not found. Please run this from the deploy directory."
    exit 1
fi

# Check required variables
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "ERROR: POSTGRES_PASSWORD not set in .env"
    exit 1
fi

# Generate a random password for the new user
NEW_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)

echo "============================================================"
echo "Creating database and user for app: ${APP_NAME}"
echo "============================================================"
echo ""
echo "Database: ${NEW_DB_NAME}"
echo "User: ${NEW_DB_USER}"
echo ""

# Check if database already exists
if docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres psql -U postgres -lqt | cut -d \| -f 1 | grep -qw "${NEW_DB_NAME}"; then
    echo "ERROR: Database '${NEW_DB_NAME}' already exists!"
    exit 1
fi

echo "Creating database and user..."

docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres psql -U postgres <<EOF
-- Create the new user
CREATE USER ${NEW_DB_USER} WITH PASSWORD '${NEW_PASSWORD}';

-- Create the new database owned by the new user
CREATE DATABASE ${NEW_DB_NAME} OWNER ${NEW_DB_USER};

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE ${NEW_DB_NAME} TO ${NEW_DB_USER};

-- Connect to the new database and grant schema permissions
\c ${NEW_DB_NAME}
GRANT ALL ON SCHEMA public TO ${NEW_DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${NEW_DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${NEW_DB_USER};
EOF

echo ""
echo "============================================================"
echo "SUCCESS! Database and user created."
echo "============================================================"
echo ""
echo "Add these to your app's .env file:"
echo ""
echo "  DB_HOST=shared-postgres"
echo "  DB_PORT=5432"
echo "  DB_NAME=${NEW_DB_NAME}"
echo "  DB_USER=${NEW_DB_USER}"
echo "  DB_PASSWORD=${NEW_PASSWORD}"
echo ""
echo "Connection string for your app:"
echo "  postgresql://${NEW_DB_USER}:${NEW_PASSWORD}@shared-postgres:5432/${NEW_DB_NAME}"
echo ""
echo "IMPORTANT: Save this password securely - it cannot be recovered!"
echo "============================================================"
