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
- **Database**: PostgreSQL with Alembic migrations (fallback to create_all)

## User Personas
1. **Sysadmin** - Full system access, manage all companies, users, apps, settings
2. **Company Admin** - Manage users/apps within their company
3. **Regular User** - Access launchpad, view assigned apps

## Core Requirements
- ✅ Single sign-on with multiple auth methods (password, magic link, Azure AD SSO)
- ✅ Employee directory (BambooHR sync placeholder)
- ✅ App registry for internal apps
- ✅ Role-based + per-user app access control
- ✅ Smart launchpad with auto-redirect
- ✅ Multi-tenant support with company branding
- ✅ Platform-grade identity service with refresh tokens and API keys

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
- [x] Settings management (BambooHR, Azure SSO)
- [x] Multi-tenancy with companies
- [x] Strict CORS configuration

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
- [x] Automatic token refresh via interceptors

### Database Models
- User, Company, App, Role, RoleApp, UserApp, UserRoleAssignment
- Employee
- Settings, CompanySettings
- RefreshToken (NEW)
- APIKey (NEW)

### Docker Deployment
- PostgreSQL: `shared-postgres` container, `id_app` database, `id_app_user` user
- Backend: `id-backend` container
- Frontend: `id-frontend` container
- Networks: `app-network` (external), `app-network-internal` (database only)

## Current Admin Credentials
- **Email:** `admin.final@identity.hub`
- **Password:** `FinalSecure456!`
- **Role:** `sysadmin`

## Prioritized Backlog

### P0 (Critical - DONE)
- [x] Platform-grade identity with short-lived JWTs
- [x] Refresh token implementation
- [x] API key authentication
- [x] Bootstrap admin with forced credential change
- [x] Strict CORS configuration

### P1 (High Priority)
- [ ] Alembic migrations (currently using fallback create_all)
- [ ] Password reset flow via email
- [ ] User self-service profile editing
- [ ] Audit logging for admin actions

### P2 (Nice to Have)
- [ ] BambooHR actual API integration
- [ ] Magic link email delivery (currently logs to console)
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
- `POST /api/auth/magic-link` - Request magic link
- `POST /api/auth/magic-link/verify` - Verify magic link
- `GET /api/auth/azure/login` - Initiate Azure SSO
- `GET /api/auth/azure/callback` - Azure SSO callback

### API Keys
- `GET /api/api-keys` - List user's API keys
- `POST /api/api-keys` - Create new API key
- `DELETE /api/api-keys/{key_id}` - Revoke API key

### Identity Context (for downstream apps)
- `GET /api/identity/context` - Get identity context from token
- `GET /api/identity/user/{user_id}` - Get user info by ID
- `GET /api/identity/company/{company_id}` - Get company info by ID

### Other Endpoints
- Companies, Apps, Users, Roles, Employees, Settings - Full CRUD

## Files of Reference
- `/app/backend/server.py` - Main API (1481 lines)
- `/app/backend/auth.py` - Authentication logic
- `/app/backend/models.py` - Database models
- `/app/backend/schemas.py` - Pydantic schemas
- `/app/frontend/src/context/AuthContext.js` - Auth context
- `/app/frontend/src/lib/api.js` - API client with refresh
- `/app/deploy/docker-compose.yml` - Docker configuration
