# Identity Hub - Redeployment Guide

## Overview
This guide explains how to redeploy the Identity Hub on top of an existing deployment that was previously pushed to GitHub.

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

### Step 2: Check for Schema Changes
```bash
# Connect to your backend container or server
cd backend
alembic current  # Shows current DB revision

# Check if migrations are needed
alembic history  # Shows all migrations
```

### Step 3: Apply Database Migrations
```bash
# Backup database first!
pg_dump -h localhost -U postgres identity_hub > backup_$(date +%Y%m%d).sql

# Apply migrations
alembic upgrade head
```

### Step 4: Update Environment Variables
Check `/deploy/.env.example` for any new required variables:

```bash
# New in v3.1.0:
RESEND_API_KEY=           # Optional: For email service
SENDER_EMAIL=             # Email sender address
SENDER_NAME=Identity Hub  # Email sender name
```

### Step 5: Rebuild and Restart Containers
```bash
cd deploy

# Rebuild images with new code
docker-compose build --no-cache

# Restart services
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f backend
```

### Step 6: Verify Deployment
```bash
# Check API health
curl https://your-domain.com/api/health

# Check version
curl https://your-domain.com/api/
# Should return: {"message": "Identity & Employee Hub API", "version": "3.1.0"}

# Check migrations applied
curl -X GET https://your-domain.com/api/admin/migrations \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
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

# Copy and edit environment files
cp .env.example .env.backend
cp .env.example .env.frontend

# Edit .env.backend with your values:
# - DATABASE_URL
# - JWT_SECRET (generate a secure random string)
# - CORS_ORIGINS (your frontend URL)
# - BACKEND_URL (your backend URL)
```

### Step 3: Start Services
```bash
docker-compose up -d
```

### Step 4: Initialize Database
The database will auto-initialize on first start with:
- Alembic migrations applied
- Bootstrap admin created: `admin@bootstrap.hub` / `ChangeMeNow!`

### Step 5: First Login
1. Navigate to `https://your-domain.com/login`
2. Login with `admin@bootstrap.hub` / `ChangeMeNow!`
3. **You will be forced to change both email AND password**
4. Set your production admin credentials

---

## Schema Changes Since v2.0

### v3.0.0 Changes
- Added `company_apps` table (app-to-company allocations)
- Added branding fields to `companies` table:
  - `logo_url`
  - `primary_color`
  - `secondary_color`

### v3.1.0 Changes
- No schema changes (code refactoring only)
- New features: Audit logging (in-memory), BambooHR sync

### Migration Commands Reference
```bash
# Check current state
alembic current

# See pending migrations
alembic history --verbose

# Upgrade to latest
alembic upgrade head

# Upgrade one step at a time
alembic upgrade +1

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade abc123
```

---

## Post-Deployment Checklist

- [ ] API health check returns `{"status": "healthy"}`
- [ ] Admin can login
- [ ] Companies page loads
- [ ] Users page loads
- [ ] BambooHR sync works (if configured)
- [ ] Azure SSO works (if configured)
- [ ] Audit logs are capturing events

---

## Troubleshooting

### Database Connection Failed
```bash
# Check if PostgreSQL is running
docker-compose ps

# Check database logs
docker-compose logs postgres

# Verify connection string in .env.backend
```

### Migrations Failed
```bash
# Check alembic error
alembic upgrade head 2>&1

# If out of sync, stamp current state
alembic stamp head  # Only if you know DB matches code

# Check alembic_version table
psql -d identity_hub -c "SELECT * FROM alembic_version;"
```

### Frontend Can't Connect to Backend
```bash
# Check CORS_ORIGINS in backend .env
# Should include your frontend URL

# Check REACT_APP_BACKEND_URL in frontend .env
# Should be the public backend URL with /api prefix
```

---

## Rollback Procedure

If deployment fails:

```bash
# 1. Stop services
docker-compose down

# 2. Restore database
psql -h localhost -U postgres identity_hub < backup_YYYYMMDD.sql

# 3. Checkout previous version
git checkout <previous-commit-hash>

# 4. Rebuild and restart
docker-compose build --no-cache
docker-compose up -d
```
