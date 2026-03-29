# Identity & Employee Hub - Docker Deployment Guide

Production-ready deployment for Ubuntu VPS with Docker Compose behind Nginx Proxy Manager.

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │       Nginx Proxy Manager           │
                    │         (SSL Termination)           │
                    └───────────┬─────────────┬───────────┘
                                │             │
                    ┌───────────▼───────────┐ │
                    │   id.example.com      │ │
                    │   (Frontend:80)       │ │
                    └───────────────────────┘ │
                                              │
                    ┌─────────────────────────▼───────────┐
                    │      api-id.example.com             │
                    │      (Backend:8000)                 │
                    └─────────────────────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │      PostgreSQL (internal only)     │
                    │      (Not exposed)                  │
                    └─────────────────────────────────────┘
```

## Prerequisites

- Ubuntu VPS (20.04+)
- Docker & Docker Compose installed
- Nginx Proxy Manager running (or similar reverse proxy)
- Domain names configured:
  - `id.example.com` → Frontend
  - `api-id.example.com` → Backend API

## Quick Start

### 1. Clone/Copy deployment files

```bash
mkdir -p /opt/identity-hub
cd /opt/identity-hub

# Copy all files from deploy/ directory
# - docker-compose.yml
# - .env.example
# - backend/
# - frontend/
```

### 2. Configure environment

```bash
# Copy example env file
cp .env.example .env

# Edit with your values
nano .env
```

**Required changes in `.env`:**

```bash
# Your domains
FRONTEND_URL=https://id.yourdomain.com
BACKEND_URL=https://api-id.yourdomain.com
CORS_ORIGINS=https://id.yourdomain.com

# Secure database password
POSTGRES_PASSWORD=your-secure-password-here

# Generate JWT secret: openssl rand -hex 32
JWT_SECRET=your-generated-secret-here

# Admin credentials
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=YourSecurePassword123!
```

### 3. Copy application code

```bash
# Copy backend code (from your working app)
cp -r /path/to/app/backend/* ./backend/

# Copy frontend code
cp -r /path/to/app/frontend/* ./frontend/
```

### 4. Build and start

```bash
# Build images
docker compose build

# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 5. Configure Nginx Proxy Manager

#### Frontend Proxy Host
- **Domain**: `id.yourdomain.com`
- **Scheme**: `http`
- **Forward Hostname/IP**: `identity-hub-frontend`
- **Forward Port**: `80`
- **SSL**: Request new certificate or use existing

#### Backend Proxy Host
- **Domain**: `api-id.yourdomain.com`
- **Scheme**: `http`
- **Forward Hostname/IP**: `identity-hub-api`
- **Forward Port**: `8000`
- **SSL**: Request new certificate or use existing
- **Custom Nginx Configuration** (Advanced tab):
```nginx
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
```

### 6. Verify deployment

```bash
# Test API health
curl https://api-id.yourdomain.com/api/health

# Test frontend
curl -I https://id.yourdomain.com
```

### 7. First login

1. Go to `https://id.yourdomain.com`
2. Login with credentials from `.env` (ADMIN_EMAIL/ADMIN_PASSWORD)
3. **You will be required to change your password on first login**

---

## Database Migrations

The database schema is auto-created on first startup. For subsequent changes:

```bash
# Access backend container
docker compose exec backend bash

# Run migrations (if using alembic)
alembic upgrade head
```

---

## Maintenance

### View logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

### Restart services
```bash
# All
docker compose restart

# Specific service
docker compose restart backend
```

### Update deployment
```bash
# Pull latest code changes
git pull

# Rebuild and restart
docker compose build
docker compose up -d
```

### Backup database
```bash
# Create backup
docker compose exec postgres pg_dump -U identity_hub identity_hub > backup_$(date +%Y%m%d).sql

# Or with compression
docker compose exec postgres pg_dump -U identity_hub identity_hub | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restore database
```bash
# Stop backend first
docker compose stop backend

# Restore
cat backup.sql | docker compose exec -T postgres psql -U identity_hub identity_hub

# Start backend
docker compose start backend
```

---

## Security Checklist

- [ ] Changed default POSTGRES_PASSWORD
- [ ] Generated strong JWT_SECRET (`openssl rand -hex 32`)
- [ ] Changed ADMIN_PASSWORD from default
- [ ] SSL certificates configured in Nginx Proxy Manager
- [ ] Firewall rules: only 80/443 exposed publicly
- [ ] PostgreSQL not exposed (internal network only)

---

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker compose logs backend

# Common issues:
# - Database not ready: wait for postgres healthcheck
# - Missing env vars: check .env file
# - Port conflict: check if 8000 is in use
```

### Database connection failed
```bash
# Check postgres is running
docker compose ps postgres

# Check postgres logs
docker compose logs postgres

# Verify DATABASE_URL in backend environment
docker compose exec backend env | grep DATABASE
```

### Frontend shows blank page
```bash
# Rebuild frontend with correct BACKEND_URL
docker compose build --no-cache frontend
docker compose up -d frontend
```

### CORS errors
- Ensure CORS_ORIGINS includes your frontend URL exactly
- Check for trailing slashes (should not have trailing slash)

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FRONTEND_URL` | Yes | - | Public URL for frontend |
| `BACKEND_URL` | Yes | - | Public URL for API |
| `CORS_ORIGINS` | Yes | - | Allowed CORS origins (comma-separated) |
| `POSTGRES_USER` | Yes | - | Database username |
| `POSTGRES_PASSWORD` | Yes | - | Database password |
| `POSTGRES_DB` | Yes | - | Database name |
| `JWT_SECRET` | Yes | - | Secret for JWT signing |
| `JWT_ALGORITHM` | No | HS256 | JWT algorithm |
| `JWT_EXPIRATION_HOURS` | No | 24 | Token expiration |
| `ADMIN_EMAIL` | Yes | - | Initial admin email |
| `ADMIN_PASSWORD` | Yes | - | Initial admin password |
| `TRUSTED_HOSTS` | No | * | Allowed hosts |

---

## Network Architecture

```yaml
Networks:
  identity-hub-internal:  # Database communication (isolated)
    - postgres
    - backend
    
  identity-hub-external:  # Exposed to reverse proxy
    - backend
    - frontend
```

The `identity-hub-internal` network is marked as `internal: true`, meaning PostgreSQL cannot be accessed from outside the Docker network.
