#!/bin/bash
# ============================================================
# PostgreSQL Initialization Script
# This runs automatically on first database creation
# ============================================================

set -e

echo "PostgreSQL initialization starting..."

# The default database (id_app) is created automatically via POSTGRES_DB
# This script can be extended to create additional databases

echo "PostgreSQL initialization complete."
echo "Database '${POSTGRES_DB}' created with user '${POSTGRES_USER}'"
