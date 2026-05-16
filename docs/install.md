# PayloadCatcher Installation Guide

This guide documents the current installation requirements and installation procedures for PayloadCatcher.

Use this guide for:

- first-time local installation
- Linux host installation from source
- Docker Compose-based installation
- post-install verification and monitoring

For day-to-day contributor workflows, see [development.md](development.md).

Command examples in this guide use Linux shell syntax. Source installation is still supported on Windows, macOS, and Linux. On Windows or macOS, adapt shell-specific steps such as virtual-environment activation and file-copy commands to your local shell.

## 1. Installation Requirements

### Supported installation modes

PayloadCatcher currently supports these practical installation paths:

- source installation for local or self-managed environments
- Docker Compose installation for local integration and operator validation

Docker is optional for Windows and macOS. Those platforms can also use the source installation flow in this guide when Python, Node.js, and PostgreSQL are installed locally.

The repository currently includes a Vite frontend scaffold and a FastAPI backend API. Treat the source and Compose procedures below as the supported installation paths for the current repository state.

### Platform requirements

- Windows, macOS, or Linux for local source installation
- Linux with `systemd` if you want `journalctl`-based service monitoring examples

### Required software

Backend:

- Python 3.12
- `pip`
- PostgreSQL 15 or newer

Frontend:

- Node.js 20 LTS
- npm

Optional infrastructure:

- Docker Engine / Docker Desktop
- Docker Compose v2

### Network and port requirements

- backend API default local port: `8000`
- frontend Vite dev port: `5173`
- PostgreSQL default local port: `5432`
- site-facing deployment default port: `8080`

### Configuration requirements

At minimum, review and set these environment values before first run:

- `BASE_URL`
- `DATABASE_URL`
- `CALLBACK_TTL_HOURS`
- `RATE_LIMIT_PER_MINUTE`
- `HOOK_PAYLOAD_MAX_BYTES`
- `VIEWER_PAYLOAD_PREVIEW_CHARS`
- `HEADER_ALLOWLIST`
- `TRUSTED_PROXIES`
- `COOKIE_SECURE`
- `COOKIE_SAMESITE`
- `COOKIE_MAX_AGE`

The current example values live in [backend/.env.example](../backend/.env.example).

## 2. Source Installation

### 2.1 Clone the repository

```bash
git clone https://github.com/t3knoid/payloadcatcher.git
cd payloadcatcher
```

### 2.2 Configure the backend environment

Create a local backend environment file from the example.

```bash
cd backend
cp .env.example .env
```

Windows and macOS note:

- PowerShell example: `Copy-Item .env.example .env`
- Windows Command Prompt example: `copy .env.example .env`

Review `.env` and update at least:

- `DATABASE_URL` for your PostgreSQL instance
- `BASE_URL` for your target environment
- `COOKIE_SECURE=false` only if you are intentionally testing over plain local HTTP

### 2.3 Install backend dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Windows note:

- PowerShell activation example: `.\.venv\Scripts\Activate.ps1`
- Command Prompt activation example: `.venv\Scripts\activate.bat`

macOS note:

- The Linux activation command shown above also applies to macOS shells such as `zsh` and `bash`.

### 2.4 Prepare the database

Create the PostgreSQL database referenced by `DATABASE_URL` and ensure the configured user can connect.

Example using the default local settings from `backend/.env.example`:

```bash
createdb -h localhost -p 5432 -U postgres payloadcatcher
```

If `createdb` is not available, use `psql`:

```bash
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE payloadcatcher"
```

PowerShell example:

```powershell
createdb -h localhost -p 5432 -U postgres payloadcatcher
```

When you run `createdb` or `psql` from PowerShell, ensure the PostgreSQL `bin` directory is on `PATH` so those commands resolve.

If you changed `DATABASE_URL`, create the database named in that connection string instead. The Docker Compose `db` service creates `payloadcatcher` automatically, so no manual database creation step is needed for the Compose path.

Then apply migrations:

```bash
cd backend
alembic upgrade head
```

### 2.5 Install frontend dependencies

```bash
cd frontend
npm install
npx playwright install chromium
```

### 2.6 Run the application from source

Backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows PowerShell, activate the virtual environment with `.\.venv\Scripts\Activate.ps1` before running `uvicorn`.

Frontend:

```bash
cd frontend
npm run dev
```

### 2.7 Verify installation

Open and verify:

- frontend UI: <http://127.0.0.1:5173>
- backend health: <http://127.0.0.1:8000/healthz>
- Swagger UI: <http://127.0.0.1:8000/docs>

Confirm all of the following:

- the home page provisions a callback URL
- the callback URL copies successfully
- the inbox route loads
- request search and pagination work
- the payload panel updates when a request is selected

## 3. Docker Compose Installation

Use this path when you want a quick local installation with containerized dependencies.

### 3.1 Start the stack

From repository root:

```bash
docker compose up --build api frontend db
```

This starts:

- PostgreSQL on `5432`
- backend API on `8000`
- frontend dev server on `5173`

### 3.2 Verify the Compose installation

Open and verify:

- frontend UI: <http://127.0.0.1:5173>
- backend health: <http://127.0.0.1:8000/healthz>
- Swagger UI: <http://127.0.0.1:8000/docs>

### 3.3 Stop the stack

```bash
docker compose down
```

If you also want to remove the PostgreSQL data volume:

```bash
docker compose down -v
```

## 4. Linux Service Installation Notes

If you install PayloadCatcher from source on Linux and want persistent process supervision, run the backend under `systemd`.

The current repository state supports this cleanly for the FastAPI backend. The frontend scaffold remains Vite-based, so if you choose to run it persistently on Linux, treat that as an operator-managed source process and keep the reverse-proxy behavior explicit.

### 4.1 Example backend systemd unit

Create `/etc/systemd/system/payloadcatcher-api.service`:

```ini
[Unit]
Description=PayloadCatcher API
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
WorkingDirectory=/opt/payloadcatcher/backend
EnvironmentFile=/opt/payloadcatcher/backend/.env
ExecStart=/opt/payloadcatcher/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
User=payloadcatcher
Group=payloadcatcher

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable payloadcatcher-api
sudo systemctl start payloadcatcher-api
```

### 4.2 Example status checks

```bash
sudo systemctl status payloadcatcher-api
sudo systemctl is-active payloadcatcher-api
```

### 4.3 Example nginx reverse proxy

Use nginx when you want TLS termination and a stable public origin in front of the backend service.

The current repository state runs the FastAPI backend as one process and keeps the Vite frontend as a separate operator-managed process. The example below focuses on proxying the backend routes that generate callback and viewer URLs.

Before you enable the proxy, confirm the backend environment matches the public origin served by nginx:

- set `BASE_URL` to the external HTTPS origin, for example `https://payloadcat.ch`
- keep the backend bound to `127.0.0.1:8000`
- set `TRUSTED_PROXIES` to the nginx source address or network, for example `127.0.0.1` or your internal proxy subnet
- keep `COOKIE_SECURE=true` for HTTPS deployments

Create `/etc/nginx/sites-available/payloadcatcher.conf`:

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 80;
    listen [::]:80;
    server_name payloadcat.ch;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name payloadcat.ch;

    ssl_certificate /etc/letsencrypt/live/payloadcat.ch/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/payloadcat.ch/privkey.pem;

    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_redirect off;
        proxy_read_timeout 60s;
    }
}
```

Enable the site and reload nginx:

```bash
sudo ln -s /etc/nginx/sites-available/payloadcatcher.conf /etc/nginx/sites-enabled/payloadcatcher.conf
sudo nginx -t
sudo systemctl reload nginx
```

Verification checks:

- `curl -I https://payloadcat.ch/healthz` returns `200 OK`
- `curl -I https://payloadcat.ch/docs` returns `200 OK`
- `curl -X POST https://payloadcat.ch/hook/<clsid>` reaches the backend and returns `200 OK`

If you also run the Vite frontend behind nginx, expose it on a separate origin and set `VITE_API_BASE_URL` to the backend public origin. Do not proxy the frontend and backend to the same `/` path in the current repository state because the frontend home route and the backend bootstrap route both use `/`.

## 5. Post-Installation Monitoring

### Source installation logs

If you run the backend and frontend in terminals, monitor the terminal output directly.

Useful checks:

- backend request logs while opening `/`, `/healthz`, `/docs`, and `/inbox/{clsid}`
- frontend dev-server output for build or routing errors
- migration output during `alembic upgrade head`

### Docker Compose logs

Follow all container logs:

```bash
docker compose logs -f
```

Follow one service only:

```bash
docker compose logs -f api
docker compose logs -f frontend
docker compose logs -f db
```

Recent logs without following:

```bash
docker compose logs --tail=100 api
```

### systemd and journalctl monitoring

For a Linux backend service installed under `systemd`:

Show recent backend logs:

```bash
sudo journalctl -u payloadcatcher-api -n 100
```

Follow backend logs live:

```bash
sudo journalctl -u payloadcatcher-api -f
```

Show logs since the last boot:

```bash
sudo journalctl -u payloadcatcher-api -b
```

Show logs for a time window:

```bash
sudo journalctl -u payloadcatcher-api --since "2026-05-16 09:00:00"
```

### Health and runtime checks

Use these checks after installation and after restarts:

Backend health:

```bash
curl http://127.0.0.1:8000/healthz
```

Swagger availability:

```bash
curl http://127.0.0.1:8000/docs
```

Database container health in Compose:

```bash
docker compose ps
```

Backend service state in Linux:

```bash
sudo systemctl status payloadcatcher-api
```

## 6. Recommended Post-Install Validation

From the repository root, run the checks that match your installation mode.

Backend tests:

```bash
cd backend
pytest
```

Frontend tests:

```bash
cd frontend
npm run lint
npm run test
npm run build
npm run test:e2e
```

## 7. Common Installation Issues

### Backend cannot connect to PostgreSQL

Check:

- PostgreSQL is running
- `DATABASE_URL` matches the real host, port, database, user, and password
- migrations were applied with `alembic upgrade head`

### Frontend cannot reach the backend API

Check:

- backend is reachable on `8000`
- `VITE_API_BASE_URL` points to the correct backend origin
- the frontend dev server was restarted after env changes

### Cookie behavior looks broken over plain local HTTP

Check:

- `COOKIE_SECURE=true` prevents secure cookies on plain HTTP
- for intentional local HTTP browser testing only, set `COOKIE_SECURE=false` in your uncommitted local override

### Compose starts but the UI is unavailable

Check:

- `docker compose ps`
- `docker compose logs -f frontend`
- `docker compose logs -f api`

## 8. Related Documentation

- [development.md](development.md)
- [api.md](api.md)
- [requirements.md](requirements.md)
- [route-contract.md](route-contract.md)
