#!/bin/bash
# Identity Hub - Deployment Script

set -e

echo "========================================"
echo "  Identity Hub - Docker Deployment"
echo "========================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Load environment variables
source .env

# Validate required variables
required_vars=(
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "POSTGRES_DB"
    "JWT_SECRET"
    "FRONTEND_URL"
    "BACKEND_URL"
    "CORS_ORIGINS"
    "ADMIN_EMAIL"
    "ADMIN_PASSWORD"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "ERROR: Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

# Check for weak passwords
if [ "$POSTGRES_PASSWORD" == "CHANGE_THIS_SECURE_PASSWORD" ]; then
    echo "ERROR: Please change POSTGRES_PASSWORD from the default value!"
    exit 1
fi

if [ "$JWT_SECRET" == "CHANGE_THIS_TO_A_SECURE_RANDOM_STRING" ]; then
    echo "ERROR: Please generate a secure JWT_SECRET!"
    echo "  Run: openssl rand -hex 32"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  Frontend URL: $FRONTEND_URL"
echo "  Backend URL:  $BACKEND_URL"
echo "  Admin Email:  $ADMIN_EMAIL"
echo ""

# Build and start
echo "Building containers..."
docker compose build

echo ""
echo "Starting services..."
docker compose up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "Checking service status..."
docker compose ps

echo ""
echo "========================================"
echo "  Deployment Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Configure Nginx Proxy Manager:"
echo "   - Frontend: $FRONTEND_URL → identity-hub-frontend:80"
echo "   - Backend:  $BACKEND_URL → identity-hub-api:8000"
echo ""
echo "2. Access the application:"
echo "   - URL: $FRONTEND_URL"
echo "   - Login: $ADMIN_EMAIL"
echo "   - Password change required on first login"
echo ""
echo "View logs: docker compose logs -f"
echo ""
