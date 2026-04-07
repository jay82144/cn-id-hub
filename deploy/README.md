# Identity & Employee Hub - Production Deployment

Self-contained Docker deployment package for the Identity Hub and shared PostgreSQL infrastructure.

## Prerequisites

- Docker Engine 24.0+
- Docker Compose 2.20+
- 2GB+ available RAM
- 10GB+ available disk space
- External nginx reverse proxy on `app-network`

## Quick Start

### 1. Create the shared Docker network (once per server)

```bash
docker network create app-network
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set ALL required values:

```bash
# Generate secure passwords
openssl rand -base64 24  # Use for POSTGRES_PASSWORD
openssl rand -base64 24  # Use for DB_PASSWORD
openssl rand -base64 48  # Use for JWT_SECRET

# Required values to change:
POSTGRES_PASSWORD=<generated superuser password>
DB_PASSWORD=<generated app user password>
JWT_SECRET=<generated JWT secret>
ID_APP_BASE_URL=https://id.yourdomain.com
ALLOWED_CORS_ORIGINS=https://id.yourdomain.com
```

### 3. Deploy the stack

```bash
docker compose up -d
```

### 4. Verify deployment

```bash
# Check all services are healthy
docker compose ps

# Check backend health (from within Docker network)
docker exec id-backend curl -s http://localhost:8000/api/health

# Or from another container on app-network:
docker run --rm --network app-network curlimages/curl http://id-backend:8000/api/health
```

**Note:** The services use `expose` not `ports`, so they are only accessible from within `app-network`. Direct `curl http://localhost:8000` from the host will NOT work.

### 5. Configure your reverse proxy

Your external nginx (already on `app-network`) should proxy to the containers:

```nginx
server {
    listen 443 ssl;
    server_name id.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://id-frontend:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

If your nginx is not yet on `app-network`:

```bash
docker network connect app-network your-nginx-container
```

### 6. First login

1. Navigate to `https://id.yourdomain.com`
2. Login with bootstrap credentials:
   - Email: `admin.new@local`
   - Password: `ChangeMeNow!`
3. **You will be forced to change both email AND password** on first login
4. After setup, use your new credentials

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     app-network                              │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │ id-frontend │    │ id-backend  │    │ shared-postgres │  │
│  │   (nginx)   │───▶│  (FastAPI)  │───▶│  (PostgreSQL)   │  │
│  │   :80       │    │   :8000     │    │   :5432         │  │
│  └─────────────┘    └─────────────┘    └─────────────────┘  │
│         │                                       │            │
│         │                                       │            │
│         ▼                                       │            │
│  Your nginx proxy                        Not exposed         │
│  (on app-network)                       (internal only)      │
└─────────────────────────────────────────────────────────────┘
```

### Services

| Service | Container | Internal Port | Description |
|---------|-----------|---------------|-------------|
| Frontend | id-frontend | 80 | React app served via nginx |
| Backend | id-backend | 8000 | FastAPI application |
| Database | shared-postgres | 5432 | PostgreSQL 16 (internal only) |

### Internal URLs (within app-network)

| Service | URL |
|---------|-----|
| Frontend | `http://id-frontend:80` |
| Backend API | `http://id-backend:8000/api` |
| Database | `postgresql://id_app_user:***@shared-postgres:5432/id_app` |

---

## Important: Database Initialization

The PostgreSQL init script (`scripts/init-db.sh`) **only runs once** when the database volume is first created.

### What this means:

- If you start with incorrect `.env` values, fix them, and restart - the init script will NOT rerun
- The `id_app_user` and grants are created only on first initialization

### If you need to reinitialize:

```bash
# WARNING: This deletes all data!
docker compose down
docker volume rm id-app-postgres-data
docker compose up -d
```

### To verify initialization succeeded:

```bash
docker exec shared-postgres psql -U postgres -c "\\du" | grep id_app_user
```

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | PostgreSQL superuser password | `<openssl rand -base64 24>` |
| `DB_PASSWORD` | ID app user password | `<openssl rand -base64 24>` |
| `JWT_SECRET` | JWT signing key (min 32 chars) | `<openssl rand -base64 48>` |
| `ID_APP_BASE_URL` | External URL | `https://id.yourdomain.com` |
| `ALLOWED_CORS_ORIGINS` | Allowed origins (comma-separated) | `https://id.yourdomain.com` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `shared-postgres` | Database host |
| `DB_PORT` | `5432` | Database port |
| `DB_NAME` | `id_app` | Database name |
| `DB_USER` | `id_app_user` | Database user |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_MINUTES` | `15` | Access token expiry |
| `REFRESH_TOKEN_DAYS` | `30` | Refresh token expiry |
| `COOKIE_SECURE` | `true` | Secure cookie flag |
| `AZURE_TENANT_ID` | - | Microsoft SSO tenant |
| `AZURE_CLIENT_ID` | - | Microsoft SSO client |
| `AZURE_CLIENT_SECRET` | - | Microsoft SSO secret |
| `BOOTSTRAP_ADMIN_EMAIL` | `admin.new@local` | Initial admin email |
| `BOOTSTRAP_ADMIN_PASSWORD` | `ChangeMeNow!` | Initial admin password |

---

## Adding New App Databases

When deploying additional applications that need their own database:

### Using the bootstrap script

```bash
# From the deploy directory
chmod +x scripts/create-app-database.sh
./scripts/create-app-database.sh hrms
```

This creates:
- Database: `hrms_app`
- User: `hrms_app_user`
- Prints connection string for your app's `.env`

### Manual creation

```bash
# Connect as postgres superuser
docker exec -it -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres psql -U postgres

-- Then run:
CREATE USER myapp_app_user WITH PASSWORD 'secure_password';
CREATE DATABASE myapp_app OWNER myapp_app_user;
GRANT ALL PRIVILEGES ON DATABASE myapp_app TO myapp_app_user;
\c myapp_app
GRANT ALL ON SCHEMA public TO myapp_app_user;
\q
```

---

## Operations

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f id-backend
```

### Restart services

```bash
docker compose restart id-backend
```

### Update deployment

```bash
# Pull latest changes and rebuild
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Backup database

```bash
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres \
    pg_dump -U postgres id_app > backup_$(date +%Y%m%d).sql
```

### Restore database

```bash
cat backup_20240101.sql | docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres \
    psql -U postgres id_app
```

---

## Troubleshooting

### Backend not starting

```bash
# Check logs
docker compose logs id-backend

# Common issues:
# - Database not ready: check shared-postgres health first
# - Missing JWT_SECRET: ensure .env has JWT_SECRET set
# - CORS misconfigured: check ALLOWED_CORS_ORIGINS is set (no wildcards)
```

### Database connection failed

```bash
# Check postgres is running and healthy
docker compose ps shared-postgres

# Verify app user exists
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres \
    psql -U postgres -c "\\du" | grep id_app_user

# Test connection as app user
docker exec -e PGPASSWORD="${DB_PASSWORD}" shared-postgres \
    psql -U id_app_user -d id_app -c "SELECT 1;"
```

### Init script didn't run

The init script only runs on first volume creation. If `id_app_user` doesn't exist:

```bash
# Option 1: Remove volume and restart (WARNING: data loss)
docker compose down
docker volume rm id-app-postgres-data
docker compose up -d

# Option 2: Manually create user
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" shared-postgres psql -U postgres <<EOF
CREATE USER id_app_user WITH PASSWORD '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE id_app TO id_app_user;
\c id_app
GRANT ALL ON SCHEMA public TO id_app_user;
EOF
```

### Frontend shows blank page

```bash
# Check frontend container
docker compose logs id-frontend

# Verify nginx is serving files
docker exec id-frontend ls -la /usr/share/nginx/html/
```

### CORS errors

Ensure `ALLOWED_CORS_ORIGINS` includes your frontend URL exactly (no trailing slash):
```
ALLOWED_CORS_ORIGINS=https://id.yourdomain.com
```

---

## Security Checklist

- [ ] Changed `JWT_SECRET` to a secure random string (min 32 chars)
- [ ] Changed `POSTGRES_PASSWORD` to a strong password
- [ ] Changed `DB_PASSWORD` to a strong password (different from POSTGRES_PASSWORD)
- [ ] Set `ALLOWED_CORS_ORIGINS` to specific domains (no wildcards)
- [ ] Set `COOKIE_SECURE=true` for HTTPS
- [ ] Changed bootstrap admin credentials on first login
- [ ] PostgreSQL not exposed publicly (internal network only)
- [ ] SSL/TLS configured on reverse proxy

---

## File Structure

```
deploy/
├── docker-compose.yml      # Main compose file
├── .env.example            # Environment template (copy to .env)
├── README.md               # This file
├── backend/
│   ├── Dockerfile          # Backend container
│   ├── entrypoint.sh       # Startup script (DB wait + migrations)
│   ├── requirements.txt    # Python dependencies
│   ├── server.py           # FastAPI app
│   ├── auth.py             # Authentication
│   ├── database.py         # Database config
│   ├── models.py           # SQLAlchemy models
│   └── schemas.py          # Pydantic schemas
├── frontend/
│   ├── Dockerfile          # Frontend container (multi-stage)
│   ├── nginx.conf          # Nginx config
│   ├── package.json        # Node dependencies
│   ├── yarn.lock           # Locked dependencies
│   └── src/                # React source
└── scripts/
    ├── init-db.sh          # Database init (runs once on first start)
    └── create-app-database.sh  # Bootstrap script for new app DBs
```

---

## Health Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Backend | `GET /api/health` | `{"status": "healthy"}` |
| Backend | `GET /api/` | `{"message": "Identity & Employee Hub API", "version": "3.0.0"}` |

### Testing from within Docker network:

```bash
# Backend health
docker exec id-backend wget -qO- http://localhost:8000/api/health

# Frontend health (returns HTML)
docker exec id-frontend wget -qO- http://localhost:80/ | head -5
```
