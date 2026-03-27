# Identity & Employee Hub PRD

## Original Problem Statement
Build an Identity & Employee Hub — a shared authentication and employee data service that acts as a gateway for multiple internal apps.

## Architecture
- **Backend**: FastAPI (Python) + SQLAlchemy async + PostgreSQL
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Auth**: JWT tokens, password login, magic links, Azure AD SSO (placeholder)
- **Database**: PostgreSQL (local instance)

## User Personas
1. **Admin** - steve.harding@me.com - Can manage apps, users, roles, employees, settings
2. **Regular User** - Access launchpad, view assigned apps

## Core Requirements (Static)
- Single sign-on with multiple auth methods
- Employee directory (BambooHR sync ready)
- App registry for internal apps
- Role-based + per-user app access control
- Smart launchpad with auto-redirect

## What's Been Implemented (2026-03-27)
### Backend
- [x] User authentication (email/password, magic links)
- [x] JWT token issuance and verification
- [x] Azure AD SSO settings storage (placeholder)
- [x] Apps CRUD + role/user assignments
- [x] Roles CRUD with default app assignments
- [x] Users CRUD with role/app overrides
- [x] Employees CRUD with search
- [x] Settings management (BambooHR, Azure SSO)
- [x] Token verification endpoint for downstream apps
- [x] Launchpad API with smart redirect logic

### Frontend
- [x] Login page (password + magic link + SSO button)
- [x] Launchpad with app cards grid
- [x] Admin panel with navigation tabs
- [x] Apps management page
- [x] Users management with role/app assignment
- [x] Roles management with app assignment
- [x] Employees directory with search
- [x] Settings page (BambooHR + Azure SSO config)

### Admin Seeded
- Email: steve.harding@me.com
- Password: ChangeMeNow!

## Prioritized Backlog

### P0 (Critical for Production)
- [ ] Azure AD SSO actual implementation (once tenant configured)
- [ ] BambooHR API integration (once credentials available)
- [ ] Email service for magic links

### P1 (High Priority)
- [ ] Password reset flow
- [ ] User self-service profile editing
- [ ] Audit logging for admin actions
- [ ] Session management (force logout)

### P2 (Nice to Have)
- [ ] Bulk user import
- [ ] Employee org chart visualization
- [ ] App usage analytics
- [ ] Custom branding per tenant

## Next Tasks
1. Configure Azure AD in Entra portal using setup instructions in Settings page
2. Add WorkAssess as first registered app
3. Test JWT validation from WorkAssess
4. Set up BambooHR integration when credentials available
