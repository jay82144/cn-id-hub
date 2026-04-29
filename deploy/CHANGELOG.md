# Identity Hub Changelog

## v3.2.0 (2026-04-29)

### New Features
- **SSO Redirect for External Apps** - External applications can redirect users to `/login?redirect=<callback_url>` and receive a JWT token via callback
- **Resend Email Integration** - Central email service with templates for magic links, password resets, and notifications

### New API Endpoints
- `POST /api/auth/validate-redirect` - Validates redirect URLs against registered apps
- `POST /api/email/send` - Send emails via Resend API
- `GET /api/email/templates` - List available email templates
- `GET /api/email/status` - Check email service configuration

### Configuration
- Added optional environment variables: `RESEND_API_KEY`, `SENDER_EMAIL`, `SENDER_NAME`

### Security
- SSO redirects require HTTPS for non-localhost URLs
- Only registered app URLs are allowed for SSO callbacks

---

## v3.1.0 (2026-04-19)

### New Features
- Schema migration tracking for production upgrades
- BambooHR real API integration with employee sync
- Audit logs UI in admin panel

### Improvements
- Modular backend routes architecture
- Version number displayed on login page

---

## v3.0.0 (2026-04-15)

### Major Changes
- Platform-grade identity service
- Short-lived JWTs (15 minutes) with refresh tokens (30 days)
- API key authentication for service-to-service calls
- Multi-tenant app allocations
- Company branding

### Breaking Changes
- Bootstrap admin now requires changing BOTH email AND password on first login
- JWT payload structure changed (added `company_id`, `permissions`, `token_type`)
- Refresh tokens stored in database with HttpOnly cookies

---

## v2.0.0 (2026-03-01)

- Multi-company support
- Company branding (logo, colors)
- Role-based access control

---

## v1.0.0 (2026-02-01)

- Initial release
- Basic authentication (email/password, magic links)
- Employee directory
- App registry
- Admin panel
