# Schema Migrations Guide

This document describes how to manage database schema changes in production deployments of the Identity & Employee Hub.

## Overview

The Identity Hub uses **Alembic** for database migrations. Each schema change is versioned and tracked, allowing you to:
- See what changes are pending before upgrading
- Safely apply migrations in production
- Roll back if needed

---

## Checking Migration Status

### Via API
```http
GET {HUB_URL}/api/admin/migrations
Authorization: Bearer {sysadmin_token}
```

**Response:**
```json
{
  "current_revision": "812b22b68a1c",
  "is_up_to_date": true,
  "pending_count": 0,
  "applied_migrations": [
    {
      "revision": "812b22b68a1c",
      "description": "Initial schema with all tables",
      "is_applied": true
    }
  ],
  "pending_migrations": []
}
```

### Via CLI
```bash
cd /app/backend
alembic current   # Shows current revision
alembic history   # Shows all migrations
```

---

## Schema Version History

### Version 1.0.0 (Migration 001)
**Date:** 2026-04-01

**Changes:**
- Initial schema: users, companies, apps, roles, employees, settings tables
- Added UserApp, RoleApp, UserRoleAssignment junction tables

**Tables Created:**
- `users` - User accounts with auth info
- `companies` - Multi-tenant company records
- `apps` - Registered applications
- `roles` - Permission roles
- `employees` - Employee directory records
- `settings` - System settings
- `company_settings` - Per-company settings
- `role_apps` - Role-to-app assignments
- `user_apps` - User-to-app overrides
- `user_role_assignments` - User role memberships

---

### Version 2.0.0 (Migration 002)
**Date:** 2026-04-15

**Changes:**
- Added refresh_tokens table for JWT refresh token storage
- Added api_keys table for service-to-service authentication
- Added must_change_email field to users table

**New Tables:**
- `refresh_tokens` - Stores refresh tokens for JWT auth
  ```sql
  - id: UUID PRIMARY KEY
  - user_id: UUID REFERENCES users(id)
  - token: VARCHAR (hashed)
  - expires_at: TIMESTAMP
  - created_at: TIMESTAMP
  ```

- `api_keys` - API keys for service-to-service auth
  ```sql
  - id: UUID PRIMARY KEY
  - name: VARCHAR
  - prefix: VARCHAR (for display)
  - hashed_key: VARCHAR
  - scope: ENUM (full_access, read_users, read_employees, verify_only)
  - user_id: UUID REFERENCES users(id)
  - company_id: UUID REFERENCES companies(id)
  - last_used_at: TIMESTAMP
  - created_at: TIMESTAMP
  ```

**Schema Changes:**
- `users` table: Added `must_change_email` column (BOOLEAN, default false)

---

### Version 3.0.0 (Migration 003)
**Date:** 2026-04-19

**Changes:**
- Added company_apps table for multi-tenant app allocation
- Added branding fields to companies (logo_url, primary_color, secondary_color)
- Added email service support

**New Tables:**
- `company_apps` - Maps apps to companies
  ```sql
  - id: UUID PRIMARY KEY
  - company_id: UUID REFERENCES companies(id)
  - app_id: UUID REFERENCES apps(id)
  - is_active: BOOLEAN
  - purchased_at: TIMESTAMP
  - expires_at: TIMESTAMP (nullable)
  ```

**Schema Changes:**
- `companies` table: Added branding fields
  - `logo_url`: VARCHAR (nullable)
  - `primary_color`: VARCHAR (default '#0A0A0A')
  - `secondary_color`: VARCHAR (default '#0047FF')

---

## Upgrading Production

### Step 1: Check Current Version
```bash
# Via CLI
alembic current

# Or via API
curl -X GET "{HUB_URL}/api/admin/migrations" \
  -H "Authorization: Bearer {token}"
```

### Step 2: Get Upgrade Path
```http
GET {HUB_URL}/api/admin/schema/upgrade-path?from_version=1.0.0&to_version=3.0.0
```

This returns all changes and migrations needed.

### Step 3: Backup Database
**ALWAYS backup before migrations!**

```bash
pg_dump -h localhost -U postgres identity_hub > backup_before_upgrade.sql
```

### Step 4: Apply Migrations

**Option A: Via Alembic CLI (Recommended for Production)**
```bash
cd /app/backend
alembic upgrade head  # Apply all pending migrations
# or
alembic upgrade +1    # Apply one migration at a time
```

**Option B: Via API (Development/Staging)**
```http
POST {HUB_URL}/api/admin/migrations/apply
Authorization: Bearer {sysadmin_token}
```

### Step 5: Verify
```bash
alembic current
# Should show latest revision
```

---

## Rolling Back

If something goes wrong:

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 812b22b68a1c

# Restore from backup if needed
psql -h localhost -U postgres identity_hub < backup_before_upgrade.sql
```

---

## Creating New Migrations

When making schema changes:

```bash
cd /app/backend

# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new_field to users"

# Or create empty migration for custom SQL
alembic revision -m "Custom migration"

# Edit the generated migration in /app/backend/alembic/versions/

# Apply the migration
alembic upgrade head
```

---

## Best Practices

1. **Always backup** before applying migrations in production
2. **Test migrations** in staging first
3. **Use transactions** - Alembic wraps migrations in transactions by default
4. **One change per migration** - Easier to roll back
5. **Document changes** - Update the SCHEMA_CHANGELOG in migration_service.py
6. **Monitor during upgrades** - Watch for errors, check application health

---

## Troubleshooting

### Migration Fails
```bash
# Check alembic error output
alembic upgrade head 2>&1

# Common issues:
# - Missing column: Check model matches database
# - Constraint violation: May need data migration first
# - Permission denied: Check database user permissions
```

### Out of Sync
If alembic and database are out of sync:
```bash
# Stamp current state without running migrations
alembic stamp head

# Or stamp specific revision
alembic stamp 812b22b68a1c
```

### Check Database State
```sql
-- See alembic version table
SELECT * FROM alembic_version;

-- Check if table exists
SELECT EXISTS (
  SELECT FROM information_schema.tables 
  WHERE table_name = 'refresh_tokens'
);
```
