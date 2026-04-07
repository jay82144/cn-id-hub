# Identity & Employee Hub - Production Deployment

Self-contained Docker deployment package for the Identity Hub and shared PostgreSQL infrastructure.

## Prerequisites

- Docker Engine 24.0+
- Docker Compose 2.20+
- 2GB+ available RAM
- 10GB+ available disk space

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
# Required - generate secure random strings
JWT_SECRET=<generate with: openssl rand -base64 48>
DB_PASSWORD=<strong password for database>

# Required - your domain
ID_APP_BASE_URL=https://id.yourdomain.com
ALLOWED_CORS_ORIGINS=https://id.yourdomain.com

# Optional - Microsoft SSO (leave empty to disable)
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
```

### 3. Deploy the stack

```bash
docker compose up -d
```

### 4. Verify deployment

```bash
# Check all services are healthy
docker compose ps

# Check backend health
curl http://localhost:8000/api/health

# Check frontend (via nginx)
curl http://localhost:80/
```

### 5. Configure your reverse proxy (nginx on host)

Add to your nginx site configuration:

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

Or use the external nginx with `app-network`:

```nginx
# Ensure nginx container is on app-network
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
│  External nginx                          Not exposed         │
│  (your server)                          (internal only)      │
└─────────────────────────────────────────────────────────────┘
```

### Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| Frontend | id-frontend | 80 | React app served via nginx |
| Backend | id-backend | 8000 | FastAPI application |
| Database | shared-postgres | 5432 | PostgreSQL 16 (internal only) |

### URLs

| Type | URL |
|------|-----|
| External Frontend | `https://id.yourdomain.com` |
| External API | `https://id.yourdomain.com/api` |
| Internal Backend | `http://id-backend:8000` |
| Internal Database | `shared-postgres:5432` |

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_PASSWORD` | PostgreSQL password | `SecureP@ssw0rd!` |
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
docker exec -it -e PGPASSWORD=your_postgres_password shared-postgres psql -U postgres

CREATE USER myapp_app_user WITH PASSWORD 'secure_password';
CREATE DATABASE myapp_app OWNER myapp_app_user;
GRANT ALL PRIVILEGES ON DATABASE myapp_app TO myapp_app_user;
\c myapp_app
GRANT ALL ON SCHEMA public TO myapp_app_user;
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
docker exec shared-postgres pg_dump -U id_app_user id_app > backup_$(date +%Y%m%d).sql
```

### Restore database

```bash
cat backup_20240101.sql | docker exec -i shared-postgres psql -U id_app_user id_app
```

---

## Security Checklist

- [ ] Changed `JWT_SECRET` to a secure random string
- [ ] Changed `DB_PASSWORD` to a strong password
- [ ] Set `ALLOWED_CORS_ORIGINS` to specific domains (no wildcards)
- [ ] Set `COOKIE_SECURE=true` for HTTPS
- [ ] Changed bootstrap admin credentials on first login
- [ ] PostgreSQL not exposed publicly (internal network only)
- [ ] SSL/TLS configured on reverse proxy

---

## Troubleshooting

### Backend not starting

```bash
# Check logs
docker compose logs id-backend

# Common issues:
# - Database not ready: wait a few seconds, check shared-postgres health
# - Missing JWT_SECRET: ensure .env has JWT_SECRET set
# - CORS misconfigured: check ALLOWED_CORS_ORIGINS
```

### Database connection failed

```bash
# Check postgres is running
docker compose ps shared-postgres

# Test connection
docker exec -it shared-postgres psql -U id_app_user -d id_app -c "SELECT 1;"
```

### Frontend shows blank page

```bash
# Check frontend container
docker compose logs id-frontend

# Verify nginx config
docker exec id-frontend cat /etc/nginx/conf.d/default.conf
```

### CORS errors

Ensure `ALLOWED_CORS_ORIGINS` includes your frontend URL exactly:
```
ALLOWED_CORS_ORIGINS=https://id.yourdomain.com
```

---

## File Structure

```
deploy/
├── docker-compose.yml      # Main compose file
├── .env.example            # Environment template
├── README.md               # This file
├── backend/
│   ├── Dockerfile          # Backend container
│   ├── entrypoint.sh       # Startup script
│   ├── requirements.txt    # Python dependencies
│   ├── server.py           # FastAPI app
│   ├── auth.py             # Authentication
│   ├── database.py         # Database config
│   ├── models.py           # SQLAlchemy models
│   └── schemas.py          # Pydantic schemas
├── frontend/
│   ├── Dockerfile          # Frontend container
│   ├── nginx.conf          # Nginx config
│   ├── package.json        # Node dependencies
│   └── src/                # React source
└── scripts/
    ├── init-db.sh          # Database init
    └── create-app-database.sh  # New app DB bootstrap
```

---

## Support

### Health Endpoints

- Backend: `GET /api/health` → `{"status": "healthy"}`
- Frontend: `GET /` → HTML page

### API Documentation

Once deployed, visit:
- Swagger UI: `https://id.yourdomain.com/api/docs`
- ReDoc: `https://id.yourdomain.com/api/redoc`
