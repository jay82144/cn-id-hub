# Identity Hub Integration Guide

Use this guide when asking AI to integrate apps with the Identity & Employee Hub.

---

## Hub Details

| Item | Value |
|------|-------|
| **Hub URL** | `https://employee-hub-283.preview.emergentagent.com` |
| **Admin Email** | steve.harding@me.com |
| **Admin Password** | ChangeMeNow! |

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
  "last_login": "2024-01-15T10:30:00Z",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 5. Frontend Token Handling
- Store JWT in `localStorage` under key `token`
- Include in all API requests: `Authorization: Bearer {token}`
- On 401 response, redirect to Hub login

---

## B) Employee Data Integration

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

### Get Single Employee
```http
GET {HUB_URL}/api/employees/{employee_id}
Authorization: Bearer {token}
```

---

## C) Register Your App in the Hub

After building your app, register it so users can access it from the launchpad:

1. Login to Hub as admin (steve.harding@me.com)
2. Go to **Admin Panel** → **Apps**
3. Click **Add App**
4. Fill in:
   - **Name**: Your app name
   - **URL**: Full URL to your app
   - **Icon**: Choose from available icons
   - **Description**: Brief description
5. Save
6. Go to **Roles** to assign the app to roles, or **Users** to assign to specific users

---

## D) Example Prompts for AI

### For Building New Apps
```
Build [APP NAME]. 

Use the Identity Hub at https://employee-hub-283.preview.emergentagent.com for authentication:
- Don't create local auth/user tables
- Validate tokens via GET /api/auth/verify
- Fetch current user from GET /api/auth/me
- For employee data, call GET /api/employees

Hub admin: steve.harding@me.com / ChangeMeNow!
```

### For Adapting Existing Apps
```
Adapt [APP NAME] to use the Identity Hub at https://employee-hub-283.preview.emergentagent.com

Changes needed:
- Remove local user table and auth system
- Remove login/registration pages
- Replace JWT validation with calls to Hub's /api/auth/verify
- Fetch user info from Hub's /api/auth/me instead of local DB
- Redirect unauthenticated users to Hub login

Hub admin: steve.harding@me.com / ChangeMeNow!
```

### For Apps Needing Employee Data
```
Build [APP NAME] that uses employee data from the Identity Hub.

- Hub URL: https://employee-hub-283.preview.emergentagent.com
- Fetch employees from GET /api/employees
- Available fields: first_name, last_name, email, department, division, team, job_title, location, manager_id, hire_date, status
- Use Hub for auth (no local auth)
```

---

## E) Technical Notes

### CORS
The Hub allows cross-origin requests. Your app can call Hub APIs directly from the frontend.

### Token Expiration
JWT tokens expire after 24 hours. Handle 401 responses by redirecting to Hub login.

### User Roles
- `admin` - Full access to Hub admin panel and all apps
- `user` - Access only to assigned apps

### App Access Control
Users see apps based on:
1. **Role defaults** - Apps assigned to their role(s)
2. **User overrides** - Apps explicitly granted/revoked for that user

Admins automatically see all active apps.

---

## F) API Quick Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/verify` | GET | Bearer | Validate JWT token |
| `/api/auth/me` | GET | Bearer | Get current user |
| `/api/employees` | GET | Bearer | List employees |
| `/api/employees/{id}` | GET | Bearer | Get single employee |
| `/api/apps` | GET | Bearer | List apps (for reference) |
| `/api/roles` | GET | Bearer | List roles (for reference) |
