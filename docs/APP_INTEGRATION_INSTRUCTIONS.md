# Connecting Apps to Identity Hub - GPT Instructions

## Overview

You are integrating an application with the Identity Hub - a centralized authentication and employee data service. The Hub handles all user authentication, so your app should NOT have its own auth system.

**Identity Hub URL:** `https://your-identity-hub.com`  
**Admin Credentials:** Ask the user for current admin login

---

## Quick Start Checklist

1. ❌ Do NOT create user tables, login pages, or JWT generation in your app
2. ✅ Redirect unauthenticated users to the Hub login page
3. ✅ Validate tokens by calling the Hub's `/api/auth/verify` endpoint
4. ✅ Get user info from `/api/auth/me` or `/api/identity/context`
5. ✅ Store the JWT token in localStorage under key `token`
6. ✅ Include `Authorization: Bearer {token}` in all API requests

---

## Authentication Flow

### Step 1: Redirect to Hub Login
When a user is not authenticated, redirect them to:
```
{IDENTITY_HUB_URL}/login?redirect={YOUR_APP_URL}
```

### Step 2: Receive Token After Login
After successful login, the Hub will redirect back to your app with a token. Your app should:
1. Extract the token from URL or localStorage
2. Store it in localStorage under key `token`
3. Use it for subsequent API calls

### Step 3: Validate Token on Each Request
Your backend should validate tokens by calling the Hub:

```javascript
// Backend middleware example (Node.js)
async function validateToken(req, res, next) {
  const token = req.headers.authorization?.replace('Bearer ', '');
  
  if (!token) {
    return res.status(401).json({ error: 'No token provided' });
  }
  
  try {
    const response = await fetch(`${IDENTITY_HUB_URL}/api/auth/verify`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    const data = await response.json();
    
    if (!data.valid) {
      return res.status(401).json({ error: 'Invalid token' });
    }
    
    // Attach user info to request
    req.user = {
      id: data.user_id,
      email: data.email,
      role: data.role,
      company_id: data.company_id,
      permissions: data.permissions
    };
    
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Token validation failed' });
  }
}
```

---

## API Endpoints Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/verify` | GET | Validate JWT token, returns user context |
| `/api/auth/me` | GET | Get current user's full profile |
| `/api/auth/refresh` | POST | Refresh access token (uses HttpOnly cookie) |
| `/api/auth/logout` | POST | Logout and revoke refresh token |

### Identity Context (for downstream apps)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/identity/context` | GET | Get full identity context from token |
| `/api/identity/user/{user_id}` | GET | Get user info by ID |
| `/api/identity/company/{company_id}` | GET | Get company info by ID |

### Employee Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/employees` | GET | List employees (filtered by user's company) |
| `/api/employees/{id}` | GET | Get single employee |

### Email Service

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/email/send` | POST | Send email (requires admin token) |
| `/api/email/templates` | GET | List available email templates |

---

## Token Verification Response

When you call `/api/auth/verify`, you get:

```json
{
  "valid": true,
  "user_id": "uuid-here",
  "email": "user@company.com",
  "role": "user",
  "company_id": "company-uuid",
  "roles": ["user", "manager"],
  "permissions": ["read:employees", "write:reports"],
  "exp": 1234567890
}
```

If invalid:
```json
{
  "valid": false,
  "error": "Token expired"
}
```

---

## Frontend Implementation

### React Example

```jsx
// lib/auth.js
const IDENTITY_HUB_URL = process.env.REACT_APP_IDENTITY_HUB_URL;

export const getToken = () => localStorage.getItem('token');

export const setToken = (token) => localStorage.setItem('token', token);

export const clearToken = () => localStorage.removeItem('token');

export const isAuthenticated = () => !!getToken();

export const redirectToLogin = () => {
  const returnUrl = encodeURIComponent(window.location.href);
  window.location.href = `${IDENTITY_HUB_URL}/login?redirect=${returnUrl}`;
};

export const logout = async () => {
  try {
    await fetch(`${IDENTITY_HUB_URL}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include'
    });
  } catch (e) {}
  clearToken();
  redirectToLogin();
};
```

```jsx
// lib/api.js
import axios from 'axios';
import { getToken, clearToken, redirectToLogin } from './auth';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL
});

// Add token to all requests
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      redirectToLogin();
    }
    return Promise.reject(error);
  }
);

export default api;
```

```jsx
// components/ProtectedRoute.jsx
import { Navigate } from 'react-router-dom';
import { isAuthenticated } from '../lib/auth';

export const ProtectedRoute = ({ children }) => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
};
```

---

## Backend Implementation

### Python/FastAPI Example

```python
from fastapi import Depends, HTTPException, Header
import httpx

IDENTITY_HUB_URL = "https://your-identity-hub.com"

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token provided")
    
    token = authorization.replace("Bearer ", "")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{IDENTITY_HUB_URL}/api/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        data = response.json()
        
        if not data.get("valid"):
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return {
            "id": data["user_id"],
            "email": data["email"],
            "role": data["role"],
            "company_id": data["company_id"],
            "permissions": data.get("permissions", [])
        }

# Usage in routes
@app.get("/api/my-endpoint")
async def my_endpoint(user = Depends(get_current_user)):
    return {"message": f"Hello {user['email']}"}
```

### Node.js/Express Example

```javascript
const axios = require('axios');

const IDENTITY_HUB_URL = process.env.IDENTITY_HUB_URL;

const authMiddleware = async (req, res, next) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  
  if (!token) {
    return res.status(401).json({ error: 'No token provided' });
  }
  
  try {
    const { data } = await axios.get(`${IDENTITY_HUB_URL}/api/auth/verify`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    
    if (!data.valid) {
      return res.status(401).json({ error: 'Invalid token' });
    }
    
    req.user = {
      id: data.user_id,
      email: data.email,
      role: data.role,
      companyId: data.company_id,
      permissions: data.permissions || []
    };
    
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Token validation failed' });
  }
};

// Usage
app.get('/api/my-endpoint', authMiddleware, (req, res) => {
  res.json({ message: `Hello ${req.user.email}` });
});
```

---

## Using API Keys (Service-to-Service)

For backend services that need to call the Hub without user context:

### Create API Key
1. Login to Identity Hub admin panel
2. Go to "API Keys" tab
3. Click "Create API Key"
4. Choose scope: `full_access`, `read_users`, `read_employees`, or `verify_only`
5. Save the key securely (shown only once)

### Use API Key
```bash
curl -X GET "https://identity-hub.com/api/employees" \
  -H "X-API-Key: idhub_xxxxxxxxxxxxxx"
```

```python
# Python
response = requests.get(
    f"{IDENTITY_HUB_URL}/api/employees",
    headers={"X-API-Key": "idhub_xxxxxxxxxxxxxx"}
)
```

---

## Sending Emails via Hub

Your app can send emails through the Hub's central email service:

```python
async def send_notification(to_email: str, title: str, message: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{IDENTITY_HUB_URL}/api/email/send",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "to": [to_email],
                "subject": title,
                "template": "notification",
                "template_data": {
                    "app_name": "My App",
                    "title": title,
                    "message": message,
                    "action_url": "https://myapp.com/dashboard",
                    "action_text": "Go to Dashboard"
                }
            }
        )
        return response.json()
```

Available templates: `magic_link`, `password_reset`, `welcome`, `notification`

---

## Fetching Employee Data

```python
# Get employees for the current user's company
async def get_employees(token: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{IDENTITY_HUB_URL}/api/employees",
            headers={"Authorization": f"Bearer {token}"},
            params={"search": "john", "department": "Engineering"}
        )
        return response.json()
```

---

## Company Branding

Get company branding for white-labeling your app:

```python
async def get_company_branding(company_id: str, token: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{IDENTITY_HUB_URL}/api/companies/{company_id}/branding",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()

# Response:
# {
#   "name": "Acme Corp",
#   "logo_url": "https://...",
#   "primary_color": "#0A0A0A",
#   "secondary_color": "#0047FF"
# }
```

---

## Token Lifecycle

- **Access Token:** 15 minutes validity
- **Refresh Token:** 30 days validity (HttpOnly cookie)
- On 401 response, try refreshing token first before redirecting to login

```javascript
// Auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      
      try {
        // Try to refresh
        const { data } = await axios.post(
          `${IDENTITY_HUB_URL}/api/auth/refresh`,
          {},
          { withCredentials: true }
        );
        
        setToken(data.access_token);
        error.config.headers.Authorization = `Bearer ${data.access_token}`;
        return api(error.config);
      } catch (refreshError) {
        clearToken();
        redirectToLogin();
      }
    }
    return Promise.reject(error);
  }
);
```

---

## Register Your App in the Hub

After building your app:

1. Login to Identity Hub admin
2. Go to **Apps Catalog** → **Add App**
3. Fill in:
   - Name: Your app name
   - URL: Full URL to your app
   - Description: Brief description
   - Is Global: Check if available to all companies
4. If not global, go to **App Allocations** to assign to specific companies
5. Assign app to roles in **Roles** tab

---

## Summary: Do's and Don'ts

### ✅ DO
- Redirect to Hub for login
- Validate tokens via Hub API
- Store token in localStorage as `token`
- Handle 401 by refreshing then redirecting
- Use Hub's email service for transactional emails
- Fetch employee data from Hub

### ❌ DON'T
- Create your own user/auth tables
- Generate your own JWTs
- Store passwords
- Implement your own login page
- Duplicate employee data locally
