# Identity Hub - Version Upgrade Guide

## Current Version: v3.2.0

This guide covers upgrading from previous versions to v3.2.0.

---

## What's New in v3.2.0

### New Features
- **SSO Redirect for External Apps** - External applications can now redirect users to Identity Hub for authentication and receive a JWT token via callback URL
- **Resend Email Integration** - Central email service for magic links, notifications, and password resets

### API Changes
- Added `POST /api/auth/validate-redirect` - Validates redirect URLs against registered apps
- Added `POST /api/email/send` - Send emails via Resend
- Added `GET /api/email/templates` - List available email templates
- Added `GET /api/email/status` - Check email service status

### Configuration Changes
- New optional environment variables for email service:
  - `RESEND_API_KEY` - Your Resend API key (optional, mock mode if not set)
  - `SENDER_EMAIL` - Email sender address (default: onboarding@resend.dev)
  - `SENDER_NAME` - Email sender name (default: Identity Hub)

---

## Upgrade from v3.1.0 to v3.2.0

### 1. Backup your database

```bash
# From your VPS
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres \
    pg_dump -U postgres id_app > backup_v3.1.0_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Update the deployment files

```bash
cd /path/to/deploy

# Pull new files or copy from updated package
# (Replace old files with new ones)
```

### 3. Update .env (optional - for email service)

Add these lines to your `.env` if you want to enable email functionality:

```bash
# Email Service (Resend) - optional
RESEND_API_KEY=re_xxxxxxxxxxxx  # Get from https://resend.com
SENDER_EMAIL=noreply@yourdomain.com
SENDER_NAME=Identity Hub
```

### 4. Rebuild and restart containers

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 5. Verify the upgrade

```bash
# Check API version
docker exec id-backend curl -s http://localhost:8000/api/ | grep version

# Should return: "version": "3.2.0"

# Test SSO redirect validation
docker exec id-backend curl -s http://localhost:8000/api/health
```

### 6. Register apps for SSO redirect (if needed)

For external apps to use SSO redirect, they must be registered in Identity Hub:

1. Login to Identity Hub admin panel
2. Go to Apps → Add App
3. Enter the app's callback URL (e.g., `https://pulse-app.yourcompany.com`)
4. The app can now redirect users to `/login?redirect=https://pulse-app.yourcompany.com/callback`

---

## Upgrade from v3.0.0 to v3.2.0

Follow the same steps as v3.1.0 → v3.2.0. No database migrations are required.

---

## Upgrade from v2.x.x to v3.2.0

### Breaking Changes in v3.0.0+

1. **JWT Token Structure** - Tokens now include additional claims (`company_id`, `permissions`, `token_type`)
2. **Refresh Tokens** - Now stored in database with HttpOnly cookies
3. **API Key Format** - Changed to `idhub_` prefix with improved hashing
4. **Bootstrap Admin** - New `admin@bootstrap.hub` / `ChangeMeNow!` must change both email AND password

### Migration Steps

1. **Backup everything**
   ```bash
   docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres \
       pg_dump -U postgres id_app > backup_v2_$(date +%Y%m%d).sql
   ```

2. **Export user data** (if needed for manual migration)
   ```bash
   docker exec -e PGPASSWORD="${DB_PASSWORD}" shared-postgres \
       psql -U id_app_user -d id_app -c "COPY users TO STDOUT WITH CSV HEADER" > users_export.csv
   ```

3. **Full redeploy**
   ```bash
   docker compose down
   docker volume rm id-app-postgres-data  # WARNING: This deletes data
   docker compose build --no-cache
   docker compose up -d
   ```

4. **Re-import data** or reconfigure manually via admin panel

---

## SSO Redirect Flow (New in v3.2.0)

### How It Works

1. External app redirects user to Identity Hub:
   ```
   https://id.yourdomain.com/login?redirect=https://myapp.com/auth/callback
   ```

2. User logs in to Identity Hub

3. Identity Hub validates the redirect URL against registered apps

4. If valid, user is redirected back with JWT token:
   ```
   https://myapp.com/auth/callback?token=eyJhbGciOiJIUzI1NiIs...
   ```

5. External app validates the token via Identity Hub API:
   ```bash
   curl -H "Authorization: Bearer ${TOKEN}" https://id.yourdomain.com/api/auth/verify
   ```

### Security Notes

- Only HTTPS redirect URLs are allowed (except localhost for development)
- Redirect URL origin must match a registered app's URL
- Alternatively, add allowed domains to `Settings → allowed_sso_callbacks`

---

## Email Service Configuration (New in v3.2.0)

### Get a Resend API Key

1. Sign up at https://resend.com
2. Create an API key in dashboard
3. Verify your sending domain (optional but recommended)

### Configure in .env

```bash
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
SENDER_EMAIL=noreply@yourdomain.com
SENDER_NAME=Your Company Identity Hub
```

### Test Email Service

```bash
# Check email service status
curl -s -H "Authorization: Bearer ${TOKEN}" \
    https://id.yourdomain.com/api/email/status
```

### Mock Mode

If `RESEND_API_KEY` is not set, the email service runs in mock mode:
- Emails are logged but not sent
- Useful for development/testing
- Magic links and password reset still work (check logs for links)

---

## Rollback Procedure

If upgrade fails:

### 1. Stop containers
```bash
docker compose down
```

### 2. Restore database from backup
```bash
cat backup_v3.1.0_YYYYMMDD_HHMMSS.sql | \
    docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres psql -U postgres id_app
```

### 3. Revert deployment files
```bash
# Restore from your backup or git
git checkout v3.1.0 -- deploy/
```

### 4. Restart with old version
```bash
docker compose build --no-cache
docker compose up -d
```

---

## Health Checks

After any upgrade, verify these endpoints:

| Endpoint | Expected Response |
|----------|-------------------|
| `GET /api/health` | `{"status": "healthy"}` |
| `GET /api/` | `{"version": "3.2.0", ...}` |
| `POST /api/auth/login` | Returns JWT token |
| `GET /api/email/status` | Email service config |

---

## Troubleshooting

### "validate-redirect not found" error
- Ensure you've updated the backend routes files
- Rebuild the backend container: `docker compose build --no-cache id-backend`

### Email not sending
- Check `RESEND_API_KEY` is set correctly
- Verify your sending domain in Resend dashboard
- Check backend logs: `docker compose logs id-backend | grep -i email`

### SSO redirect blocked
- Register the app in Identity Hub admin panel
- Or add the domain to Settings → `allowed_sso_callbacks`
- Ensure using HTTPS for non-localhost URLs

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v3.2.0 | 2026-04-29 | SSO redirect for external apps, Resend email integration |
| v3.1.0 | 2026-04-19 | Schema migration tracking, BambooHR real API integration |
| v3.0.0 | 2026-04-15 | Platform-grade identity (refresh tokens, API keys, multi-tenant) |
| v2.0.0 | 2026-03-01 | Multi-company support, company branding |
| v1.0.0 | 2026-02-01 | Initial release |

---

## Support

For issues or questions:
1. Check the logs: `docker compose logs -f`
2. Review this upgrade guide
3. Check `/app/docs/` for additional documentation
