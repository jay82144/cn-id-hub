# Identity Hub Integration Guide

Use this guide when asking AI to integrate apps with the Identity & Employee Hub.

---

## Hub Details

| Item | Value |
|------|-------|
| **Hub URL** | `https://employee-hub-283.preview.emergentagent.com` |
| **Version** | 3.0.0 |
| **Admin Email** | admin.test@identity.hub |
| **Admin Password** | SecureTest123! |

---

## A) Authentication Integration

**For new apps or adapting existing apps to use the Hub for auth:**

### 1. Remove Local Auth
- Delete any local user tables, login pages, and JWT generation
- Remove password hashing, session management, etc.

### 2. Redirect to Hub for Login
Send unauthenticated users to the Hub login page:
```
{HUB_URL}/login
```

After login, users will have a JWT token stored in their browser.

### 3. Validate JWT Tokens
Your app's backend should validate tokens by calling:
```http
GET {HUB_URL}/api/auth/verify
Authorization: Bearer {token}
```

**Response (valid token):**
```json
{
  "valid": true,
  "user_id": "uuid-here",
  "email": "user@company.com",
  "role": "user|admin",
  "company_id": "company-uuid",
  "roles": ["user"],
  "permissions": ["read:profile"],
  "exp": 1234567890
}
```

**Response (invalid token):**
```json
{
  "valid": false,
  "error": "Invalid or expired token"
}
```

### 4. Get Current User Info
To get full user details:
```http
GET {HUB_URL}/api/auth/me
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@company.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "user",
  "status": "active",
  "company_id": "company-uuid",
  "company_name": "Acme Corp",
  "last_login": "2024-01-15T10:30:00Z",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 5. Frontend Token Handling
- Store JWT in `localStorage` under key `token`
- Include in all API requests: `Authorization: Bearer {token}`
- On 401 response, try refresh token first, then redirect to Hub login
- Access tokens expire in 15 minutes, refresh tokens in 30 days

### 6. Token Refresh
```http
POST {HUB_URL}/api/auth/refresh
Cookie: refresh_token=<token>
```

Returns a new access token if the refresh token is valid.

---

## B) Central Email Service

**Use the Hub's email service for sending transactional emails from your app:**

### Send Custom Email
```http
POST {HUB_URL}/api/email/send
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "to": ["user@example.com"],
  "subject": "Email Subject",
  "html": "<h1>Email content</h1>"
}
```

### Send Using Templates
```http
POST {HUB_URL}/api/email/send
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "to": ["user@example.com"],
  "subject": "Welcome!",
  "template": "notification",
  "template_data": {
    "app_name": "Your App",
    "title": "Welcome!",
    "message": "Thanks for signing up.",
    "action_url": "https://yourapp.com/dashboard",
    "action_text": "Go to Dashboard"
  }
}
```

### Available Templates
| Template | Data Fields |
|----------|-------------|
| `magic_link` | app_name, magic_link, expires_in |
| `password_reset` | app_name, reset_link, expires_in |
| `welcome` | app_name, first_name, login_url |
| `notification` | app_name, title, message, action_url (opt), action_text (opt) |

### Check Email Service Status
```http
GET {HUB_URL}/api/email/status
Authorization: Bearer {admin_token}
```

---

## C) API Keys for Service-to-Service

**For backend apps that need to call Hub APIs without user context:**

### Create API Key (Admin)
```http
POST {HUB_URL}/api/api-keys
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "name": "My App Backend",
  "scope": "read_users"
}
```

**Scopes:** `full_access`, `read_users`, `read_employees`, `verify_only`

### Use API Key
```http
GET {HUB_URL}/api/auth/me
X-API-Key: idhub_xxxxxxxxxxxxxxxx
```

---

## D) Employee Data Integration

**To fetch employee/user data from the Hub:**

### List Employees
```http
GET {HUB_URL}/api/employees
Authorization: Bearer {token}
```

### Query Parameters
| Param | Description | Example |
|-------|-------------|---------|
| `search` | Search by name or email | `?search=john` |
| `department` | Filter by department | `?department=Engineering` |
| `status` | Filter by status | `?status=active` |

### Employee Fields
```json
{
  "id": "uuid",
  "user_id": "uuid (if linked to user account)",
  "company_id": "uuid of employee's company",
  "company_name": "Acme Corp",
  "bamboo_id": "external ID from BambooHR",
  "email": "employee@company.com",
  "first_name": "John",
  "last_name": "Doe",
  "department": "Engineering",
  "division": "Product",
  "team": "Frontend",
  "job_title": "Senior Developer",
  "location": "New York",
  "manager_id": "uuid of manager",
  "hire_date": "2023-06-15T00:00:00Z",
  "status": "active|archived",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## E) Multi-Tenant Support

The Hub supports multi-tenant deployments where apps can be allocated to specific companies.

### Get Company Info
```http
GET {HUB_URL}/api/identity/company/{company_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "logo_url": "https://example.com/logo.png",
  "primary_color": "#0A0A0A",
  "secondary_color": "#0047FF",
  "is_active": true
}
```

### Company Branding
Apps can use company branding colors for white-labeling:
- `primary_color` - Main brand color (buttons, headers)
- `secondary_color` - Accent color (highlights, links)
- `logo_url` - Company logo for headers

---

## F) Schema Migrations (For Production)

**Track and manage database schema changes:**

### Check Migration Status
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
  "applied_migrations": [...],
  "pending_migrations": []
}
```

### Get Upgrade Path
```http
GET {HUB_URL}/api/admin/schema/upgrade-path?from_version=1.0.0&to_version=3.0.0
Authorization: Bearer {sysadmin_token}
```

**Response:**
```json
{
  "from_version": "1.0.0",
  "to_version": "3.0.0",
  "changes": [
    "Added refresh_tokens table",
    "Added api_keys table",
    ...
  ],
  "migrations_needed": ["002", "003"],
  "alembic_command": "alembic upgrade 003"
}
```

### Schema Changelog
```http
GET {HUB_URL}/api/admin/schema/changelog
Authorization: Bearer {sysadmin_token}
```

---

## G) Register Your App in the Hub

After building your app, register it so users can access it from the launchpad:

1. Login to Hub as admin
2. Go to **Admin Panel** → **Apps Catalog**
3. Click **Add App**
4. Fill in:
   - **Name**: Your app name
   - **URL**: Full URL to your app
   - **Icon**: Choose from available icons
   - **Description**: Brief description
   - **Is Global**: If true, available to all companies
5. Save
6. If not global, go to **App Allocations** to assign the app to specific companies
7. Go to **Roles** to assign the app to roles, or **Users** to assign to specific users

---

## H) Example Prompts for AI

### For Building New Apps
```
Build [APP NAME]. 

Use the Identity Hub at https://employee-hub-283.preview.emergentagent.com for authentication:
- Don't create local auth/user tables
- Validate tokens via GET /api/auth/verify
- Fetch current user from GET /api/auth/me
- For employee data, call GET /api/employees
- Use Hub's email service for transactional emails

Hub admin: admin.test@identity.hub / SecureTest123!
```

### For Apps Needing Email
```
Build [APP NAME] that sends email notifications via the Identity Hub.

- Hub URL: https://employee-hub-283.preview.emergentagent.com
- Send emails via POST /api/email/send
- Use templates: notification, welcome, or custom HTML
- Hub admin: admin.test@identity.hub / SecureTest123!
```

---

## I) Technical Notes

### CORS
The Hub allows cross-origin requests. Your app can call Hub APIs directly from the frontend.

### Token Expiration
- Access tokens: 15 minutes
- Refresh tokens: 30 days
Handle 401 responses by trying refresh first, then redirecting to Hub login.

### User Roles
- `sysadmin` - Full system access, manage all companies
- `company_admin` - Manage users/apps within their company
- `user` - Access only to assigned apps

### App Access Control
Users see apps based on:
1. **Company allocation** - App must be allocated to user's company
2. **Role defaults** - Apps assigned to their role(s)
3. **User overrides** - Apps explicitly granted/revoked for that user

Sysadmins automatically see all active apps.

---

## J) API Quick Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/verify` | GET | Bearer | Validate JWT token |
| `/api/auth/me` | GET | Bearer/API-Key | Get current user |
| `/api/auth/refresh` | POST | Cookie | Refresh access token |
| `/api/auth/logout` | POST | Bearer | Logout and revoke tokens |
| `/api/employees` | GET | Bearer | List employees |
| `/api/employees/{id}` | GET | Bearer | Get single employee |
| `/api/email/send` | POST | Bearer (admin) | Send email |
| `/api/email/status` | GET | Bearer (admin) | Email service status |
| `/api/admin/migrations` | GET | Bearer (sysadmin) | Migration status |
| `/api/admin/schema/changelog` | GET | Bearer (sysadmin) | Schema changelog |
| `/api/api-keys` | POST | Bearer (admin) | Create API key |
| `/api/identity/context` | GET | Bearer | Get identity context |
| `/api/identity/company/{id}` | GET | Bearer | Get company info |
| `/api/admin/audit-logs` | GET | Bearer (sysadmin) | View audit logs |
