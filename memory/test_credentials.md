# Test Credentials for Identity & Employee Hub

## Current Admin Account
- **Email:** `admin.test@identity.hub`
- **Password:** `SecureTest123!`
- **Role:** `sysadmin`

## Test Companies
- **Acme Corp** - ID: 0643f219-27ad-4c1b-b52f-4d09bfcc1bff
- **TechStart Inc** - ID: 02b5ca32-6001-4990-9183-b6e031144f45

## Test Apps
- **CRM Pro** - Allocated to Acme Corp

## Test API Key
- **Prefix:** `idhub_*`
- **Scope:** `verify_only`
- **Note:** API keys are generated via POST /api/api-keys endpoint

## Auth Endpoints
- `POST /api/auth/login` - Email/password login
- `POST /api/auth/refresh` - Refresh access token (uses HttpOnly cookie)
- `POST /api/auth/logout` - Logout and revoke refresh token
- `POST /api/auth/change-password` - Change password only
- `POST /api/auth/change-credentials` - Change both email and password (for bootstrap admin)
- `GET /api/auth/me` - Get current user info
- `GET /api/auth/verify` - Verify JWT token (for downstream apps)
- `POST /api/auth/validate-redirect` - Validate redirect URL for SSO
- `POST /api/auth/magic-link` - Request magic link
- `POST /api/auth/magic-link/verify` - Verify magic link

## SSO Redirect Flow (External Apps)
- **Test URL:** `https://<hub-url>/login?redirect=https://pulse-app.example.com/callback`
- **Registered Test App:** Pulse App (`https://pulse-app.example.com`)
- **Flow:**
  1. External app redirects user to Identity Hub login with `?redirect=<callback_url>`
  2. User logs in to Identity Hub
  3. Hub validates redirect URL against registered apps
  4. If valid, user is redirected to `<callback_url>?token=<ACCESS_TOKEN>`
- **Security:** Only registered app URLs are allowed. HTTPS required for non-localhost.

## Email Service Endpoints
- `POST /api/email/send` - Send email (requires admin)
- `GET /api/email/templates` - List available templates
- `GET /api/email/status` - Check email service status

## Migration Endpoints
- `GET /api/admin/migrations` - Get migration status (requires sysadmin)
- `GET /api/admin/migrations/pending` - Get pending migrations
- `GET /api/admin/schema/changelog` - Get schema changelog
- `GET /api/admin/schema/upgrade-path` - Get upgrade instructions

## Company App Allocation Endpoints
- `GET /api/company-apps` - List all allocations (sysadmin only)
- `POST /api/company-apps` - Create allocation
- `PUT /api/company-apps/{id}` - Update allocation
- `DELETE /api/company-apps/{id}` - Remove allocation

## Company Branding Endpoints
- `GET /api/companies/{id}/branding` - Get company branding (public)
- `PUT /api/companies/my/branding` - Update own company branding (company_admin)

## API Key Endpoints
- `GET /api/api-keys` - List user's API keys
- `POST /api/api-keys` - Create new API key
- `DELETE /api/api-keys/{key_id}` - Revoke API key

## Identity Context Endpoints (for downstream apps)
- `GET /api/identity/context` - Get identity context from token
- `GET /api/identity/user/{user_id}` - Get user info by ID
- `GET /api/identity/company/{company_id}` - Get company info by ID

## Token Details
- **Access Token:** 15 minutes validity
- **Refresh Token:** 30 days validity, stored in HttpOnly cookie
- **JWT Payload:** Contains `sub`, `email`, `user_id`, `company_id`, `roles`, `permissions`, `token_type`, `exp`

## Email Service
- **Status:** Mock mode (RESEND_API_KEY not configured)
- **Templates:** magic_link, password_reset, welcome, notification
- **Note:** In mock mode, emails are logged but not actually sent

## BambooHR Integration
- **Status:** Configured and working
- **Subdomain:** penrosehealth
- **API Key:** Configured in settings
- **Employees Synced:** 214
- **Endpoints:**
  - `GET/PUT /api/settings/bamboohr` - Get/update BambooHR settings
  - `POST /api/settings/bamboohr/test` - Test connection
  - `POST /api/settings/bamboohr/sync` - Sync employees
