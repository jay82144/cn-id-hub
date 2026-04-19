# Identity Hub - Redeployment Guide

## Overview
This guide explains how to redeploy the Identity Hub on top of an existing deployment.

---

## Prerequisites
- Docker and Docker Compose installed
- Access to the GitHub repository
- PostgreSQL database (existing or new)

---

## Option 1: Update Existing Deployment (Recommended)

### Step 1: Pull Latest Code
```bash
cd /path/to/identity-hub
git pull origin main
```

### Step 2: Rebuild and Restart Containers
```bash
cd deploy

# Rebuild images with new code (includes updated Alembic migrations)
docker-compose build --no-cache

# Restart services
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f id-backend
```

The backend entrypoint automatically:
1. Waits for database to be ready
2. Runs `alembic upgrade head` if `alembic.ini` is present
3. Falls back to `create_all()` if Alembic fails
4. Starts the uvicorn server

### Step 3: Verify Deployment
```bash
# Check API health
curl https://your-domain.com/api/health

# Check version
curl https://your-domain.com/api/
# Should return: {"message": "Identity & Employee Hub API", "version": "3.1.0"}
```

---

## Option 2: Fresh Deployment

### Step 1: Clone Repository
```bash
git clone https://github.com/your-org/identity-hub.git
cd identity-hub
```

### Step 2: Configure Environment
```bash
cd deploy

# Copy environment example
cp .env.example .env

# Edit .env with your values:
# - POSTGRES_PASSWORD (superuser password)
# - DB_USER, DB_PASSWORD (app user)
# - JWT_SECRET (generate secure random: openssl rand -hex 32)
# - ID_APP_BASE_URL (your public URL)
# - CORS_ORIGINS (frontend URL)
```

### Step 3: Start Services
```bash
docker-compose up -d
```

### Step 4: First Login
1. Navigate to `https://your-domain.com/login`
2. Login with `admin@bootstrap.hub` / `ChangeMeNow!`
3. **You will be forced to change both email AND password**
4. Set your production admin credentials

---

## Database Migration Details

### How Migrations Work in Docker

The deploy package (`/deploy/backend/`) includes:
- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Migration environment setup
- `alembic/versions/` - Migration files

The `entrypoint.sh` script handles migrations:
```bash
if [ -f "alembic.ini" ]; then
    alembic upgrade head || {
        # Fallback to create_all() if Alembic fails
    }
fi
```

### Manual Migration Commands (inside container)

```bash
# Enter the backend container
docker exec -it id-backend bash

# Check current revision
alembic current

# See migration history
alembic history --verbose

# Apply all pending migrations
alembic upgrade head

# Apply one migration at a time
alembic upgrade +1
```

### Schema Version History

| Version | Migration | Changes |
|---------|-----------|---------|
| 1.0.0 | 812b22b68a1c | Initial schema: all 13 tables + 5 enum types |

### Current Tables
- `companies` - Multi-tenant companies
- `users` - User accounts
- `roles` - Permission roles
- `apps` - Registered applications
- `role_apps` - Role-to-app assignments
- `user_apps` - User-to-app overrides
- `user_role_assignments` - User role memberships
- `company_apps` - App allocations to companies
- `employees` - Employee directory
- `settings` - Global settings
- `company_settings` - Per-company settings
- `refresh_tokens` - JWT refresh tokens
- `api_keys` - API keys for service-to-service auth

---

## Environment Variables

### Required
```env
# Database
POSTGRES_PASSWORD=your_superuser_password
DB_HOST=shared-postgres
DB_PORT=5432
DB_NAME=id_app
DB_USER=id_app_user
DB_PASSWORD=your_app_password

# JWT
JWT_SECRET=your_32_char_secret_here

# URLs
ID_APP_BASE_URL=https://your-domain.com
CORS_ORIGINS=https://your-domain.com
```

### Optional
```env
# Email (Resend)
RESEND_API_KEY=re_xxxxx
SENDER_EMAIL=noreply@yourdomain.com
SENDER_NAME=Identity Hub

# Token expiry
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=30
```

---

## Post-Deployment Checklist

- [ ] API health check returns `{"status": "healthy"}`
- [ ] Admin can login
- [ ] Companies page loads
- [ ] Users page loads
- [ ] Employees page loads (BambooHR sync if configured)
- [ ] Azure SSO works (if configured)

---

## Troubleshooting

### Backend Won't Start
```bash
# Check logs
docker-compose logs id-backend

# Common issues:
# - Database not ready: Wait longer or check postgres health
# - Missing environment variable: Check .env file
# - Port conflict: Check if 8000 is in use
```

### Alembic Migration Errors
```bash
# Enter container
docker exec -it id-backend bash

# Check current state
alembic current

# If database exists but alembic_version is empty/wrong:
alembic stamp head  # Mark as up-to-date

# If need to recreate tables (WARNING: loses data)
alembic downgrade base
alembic upgrade head
```

### Database Connection Failed
```bash
# Check postgres is running
docker-compose ps shared-postgres

# Test connection
docker exec -it id-backend pg_isready -h shared-postgres -p 5432 -U id_app_user -d id_app
```

---

## Rollback Procedure

If deployment fails:

```bash
# 1. Stop services
docker-compose down

# 2. If you have a database backup, restore it
docker exec -i shared-postgres psql -U postgres -d id_app < backup.sql

# 3. Checkout previous version
git checkout <previous-commit-hash>

# 4. Rebuild and restart
docker-compose build --no-cache
docker-compose up -d
```

---

## Updating Deploy Package from Source

If you modify backend code in `/app/backend/`, sync to deploy:

```bash
# Sync all backend files
cp backend/server.py deploy/backend/
cp backend/models.py deploy/backend/
cp backend/schemas.py deploy/backend/
cp backend/auth.py deploy/backend/
cp backend/database.py deploy/backend/
cp backend/requirements.txt deploy/backend/
cp backend/email_service.py deploy/backend/
cp backend/bamboohr_service.py deploy/backend/
cp backend/migration_service.py deploy/backend/

# Sync routes
cp -r backend/routes/* deploy/backend/routes/

# Sync Alembic
cp backend/alembic.ini deploy/backend/
cp backend/alembic/env.py deploy/backend/alembic/
cp backend/alembic/versions/*.py deploy/backend/alembic/versions/
```
