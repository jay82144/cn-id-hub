# Identity & Employee Hub PRD

## Original Problem Statement
Build an Identity & Employee Hub — a shared authentication and employee data service that acts as a gateway for multiple internal apps.

## Platform Identity Requirements (Latest - Completed)
- **Short-lived JWTs:** Access tokens expire in 15 minutes
- **Refresh Tokens:** 30-day validity, stored in database, set as HttpOnly cookies
- **API Keys:** Support for global and scoped API keys for service-to-service authentication
- **Bootstrap Admin:** `admin@bootstrap.hub` / `ChangeMeNow!` must change both email and password on first login
- **Strict CORS:** Environment-variable driven allowed origins (no wildcard in production)
- **JWT Payload:** Contains `sub`, `email`, `user_id`, `company_id`, `roles`, `permissions`, `token_type`, `exp`

## Architecture
- **Backend**: FastAPI (Python) + SQLAlchemy async + PostgreSQL
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Auth**: JWT (15m access + 30d refresh), API keys, Azure AD SSO, Magic links
- **Database**: PostgreSQL with Alembic migrations
- **Email**: Resend (configurable, mock mode if no API key)
- **Code Structure**: Modular routes in `/backend/routes/` (auth, azure_sso, api_keys, identity, email, admin)

## User Personas
1. **Sysadmin** - Full system access, manage all companies, users, apps, settings
2. **Company Admin** - Manage users/apps within their company, edit company branding
3. **Regular User** - Access launchpad, view assigned apps

## Core Requirements
- ✅ Single sign-on with multiple auth methods (password, magic link, Azure AD SSO)
- ✅ Employee directory (BambooHR sync placeholder)
- ✅ App registry for internal apps
- ✅ Role-based + per-user app access control
- ✅ Smart launchpad with auto-redirect
- ✅ Multi-tenant support with company branding
- ✅ Platform-grade identity service with refresh tokens and API keys
- ✅ Central email service for all apps
- ✅ Schema migration tracking for production upgrades

## What's Been Implemented

### Backend (v3.0.0)
- [x] JWT authentication with 15-minute access tokens
- [x] Refresh tokens (30 days, HttpOnly cookies, database storage)
- [x] API key authentication for service-to-service calls
- [x] Bootstrap admin with forced email+password change
- [x] Token verification endpoint for downstream apps
- [x] Identity context endpoints (`/api/identity/context`, `/api/identity/user/{id}`, `/api/identity/company/{id}`)
- [x] User authentication (email/password, magic links)
- [x] Azure AD SSO integration (MSAL)
- [x] Apps CRUD + role/user assignments
- [x] Roles CRUD with default app assignments
- [x] Users CRUD with role/app overrides
- [x] Employees CRUD with search
- [x] BambooHR API integration with real sync (NEW)
- [x] Settings management (BambooHR, Azure SSO)
- [x] Multi-tenancy with companies
- [x] Company-App allocations (NEW)
- [x] Company branding (logo, colors) (NEW)
- [x] Central email service (NEW)
- [x] Schema migration tracking (NEW)

### Frontend
- [x] Login page (password + magic link + SSO button)
- [x] Change Credentials page (for bootstrap admin)
- [x] Change Password page
- [x] Launchpad with app cards grid
- [x] Admin panel with navigation tabs
- [x] Apps management page
- [x] Users management with role/app assignment
- [x] Roles management with app assignment
- [x] Employees directory with search
- [x] Settings page (BambooHR + Azure SSO config)
- [x] Companies management (sysadmin only)
- [x] API Keys management page
- [x] Company App Allocations page (NEW)
- [x] Company Branding page (NEW)
- [x] Sysadmin company switcher dropdown (NEW)
- [x] Automatic token refresh via interceptors

### Database Models
- User, Company, App, Role, RoleApp, UserApp, UserRoleAssignment
- Employee
- Settings, CompanySettings
- RefreshToken
- APIKey
- CompanyApp (NEW)

## Current Admin Credentials
- **Email:** `admin.test@identity.hub`
- **Password:** `SecureTest123!`
- **Role:** `sysadmin`

## Production Bootstrap Credentials
For fresh deployments:
- **Email:** `admin@bootstrap.hub`
- **Password:** `ChangeMeNow!`
- **Note:** Must change BOTH email AND password on first login

## Prioritized Backlog

### P0 (Critical - DONE)
- [x] Platform-grade identity with short-lived JWTs
- [x] Refresh token implementation
- [x] API key authentication
- [x] Bootstrap admin with forced credential change
- [x] Multi-tenant app allocations
- [x] Company branding
- [x] Central email service
- [x] Schema migration tracking

### P1 (High Priority)
- [x] Alembic migrations (configured and working)
- [x] API Key management UI in admin panel
- [x] Production Docker deployment package
- [x] Redirect-based SSO for external apps (NEW)
- [ ] Password reset flow via email (email service ready)
- [ ] User self-service profile editing
- [ ] Audit logging for admin actions

### P2 (Nice to Have)
- [x] BambooHR actual API integration (DONE)
- [ ] Magic link email delivery (hidden, email service ready)
- [ ] Bulk user import
- [ ] Employee org chart visualization
- [ ] App usage analytics

## API Endpoints

### Authentication
- `POST /api/auth/login` - Email/password login
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/logout` - Logout and revoke refresh token
- `POST /api/auth/change-password` - Change password only
- `POST /api/auth/change-credentials` - Change both email and password
- `GET /api/auth/me` - Get current user info
- `GET /api/auth/verify` - Verify JWT token
- `POST /api/auth/validate-redirect` - Validate SSO redirect URL (NEW)
- `POST /api/auth/magic-link` - Request magic link
- `POST /api/auth/magic-link/verify` - Verify magic link
- `GET /api/auth/azure/login` - Initiate Azure SSO
- `GET /api/auth/azure/callback` - Azure SSO callback

### Email Service (NEW)
- `POST /api/email/send` - Send email (custom or template)
- `GET /api/email/templates` - List available templates
- `GET /api/email/status` - Check email service configuration

### Schema Migrations (NEW)
- `GET /api/admin/migrations` - Get migration status
- `GET /api/admin/migrations/pending` - Get pending migrations
- `GET /api/admin/schema/changelog` - Get schema version history
- `GET /api/admin/schema/upgrade-path` - Get upgrade instructions
- `POST /api/admin/migrations/apply` - Apply pending migrations

### API Keys
- `GET /api/api-keys` - List user's API keys
- `POST /api/api-keys` - Create new API key
- `DELETE /api/api-keys/{key_id}` - Revoke API key

### Identity Context (for downstream apps)
- `GET /api/identity/context` - Get identity context from token
- `GET /api/identity/user/{user_id}` - Get user info by ID
- `GET /api/identity/company/{company_id}` - Get company info by ID

### Company Apps (NEW)
- `GET /api/company-apps` - List app allocations
- `POST /api/company-apps` - Allocate app to company
- `PUT /api/company-apps/{id}` - Update allocation
- `DELETE /api/company-apps/{id}` - Remove allocation

### Company Branding (NEW)
- `GET /api/companies/{id}/branding` - Get company branding
- `PUT /api/companies/my/branding` - Update own company branding

### Other Endpoints
- Companies, Apps, Users, Roles, Employees, Settings - Full CRUD

## Files of Reference
- `/app/backend/server.py` - Main API (refactored, ~1067 lines)
- `/app/backend/routes/auth.py` - Authentication routes
- `/app/backend/routes/azure_sso.py` - Azure SSO integration
- `/app/backend/routes/api_keys.py` - API key management
- `/app/backend/routes/identity.py` - Identity context for downstream apps
- `/app/backend/routes/email.py` - Email service endpoints
- `/app/backend/routes/admin.py` - Migrations, audit logs, admin functions
- `/app/backend/auth.py` - Authentication logic
- `/app/backend/models.py` - Database models
- `/app/backend/schemas.py` - Pydantic schemas
- `/app/backend/email_service.py` - Central email service
- `/app/backend/migration_service.py` - Schema migration tracking
- `/app/frontend/src/context/AuthContext.js` - Auth context
- `/app/frontend/src/context/AdminContext.js` - Admin company switcher
- `/app/frontend/src/pages/admin/AuditLogsPage.js` - Audit logs UI
- `/app/frontend/src/lib/api.js` - API client with refresh
- `/app/deploy/docker-compose.yml` - Docker configuration
- `/app/docs/INTEGRATION_GUIDE.md` - Integration documentation
- `/app/docs/SCHEMA_MIGRATIONS.md` - Migration documentation

## Docker Deployment
- PostgreSQL: `shared-postgres` container, `id_app` database, `id_app_user` user
- Backend: `id-backend` container
- Frontend: `id-frontend` container
- Networks: `app-network` (external), `app-network-internal` (database only)

## Environment Variables

### Backend (.env)
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret for JWT signing
- `JWT_ALGORITHM` - Algorithm (HS256)
- `MAGIC_LINK_EXPIRATION_MINUTES` - Magic link expiry
- `BACKEND_URL` - Public backend URL
- `CORS_ORIGINS` - Allowed CORS origins
- `COOKIE_SECURE` - Secure cookie flag
- `RESEND_API_KEY` - Resend API key for emails (optional)
- `SENDER_EMAIL` - Email sender address
- `SENDER_NAME` - Email sender name

### Frontend (.env)
- `REACT_APP_BACKEND_URL` - Backend API URL
