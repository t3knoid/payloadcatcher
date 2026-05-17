# PayloadCatcher Native Installation Guide

This guide documents a native production installation of PayloadCatcher on a Linux host.

Use this guide for:

- first-time native production deployment
- deploying the application into `/opt/payloadcatcher`
- configuring the required system service and reverse proxy
- updating an existing native installation
- post-install verification and monitoring

For day-to-day development workflows, see [development.md](development.md).

Command examples in this guide use Linux shell syntax.

## 1. Deployment Model

PayloadCatcher runs as a native FastAPI application behind a reverse proxy.

This guide uses nginx for the reverse-proxy examples, but nginx is not a hard requirement. You can use another reverse proxy if it provides equivalent TLS termination and forwards the required host and proxy headers to FastAPI.

Production serving model:

- the application code is installed under `/opt/payloadcatcher`
- the Python application runs locally on `127.0.0.1:8000`
- compiled frontend assets are built during installation and served by FastAPI
- a reverse proxy provides the site-facing origin, TLS termination, and request forwarding
- PostgreSQL provides the production database

The site-facing service port defaults to `8080`, but most public deployments terminate on `443` through the selected reverse proxy.

## 2. Host Requirements

Install these packages or their platform-equivalent names on the target Linux host:

- `git`
- Python `3.12`
- Python `venv` support
- `pip`
- Node.js `20` LTS
- `npm`
- PostgreSQL `15` or newer
- nginx or another reverse proxy with equivalent forwarding behavior

Operational assumptions:

- the host can create `/opt/payloadcatcher`
- the host can reach the PostgreSQL server named in `DATABASE_URL`
- the reverse proxy and application run on the same host unless you intentionally split them

## 3. Prepare the Host

Create a dedicated service account and installation directory.

```bash
sudo useradd --system --home /opt/payloadcatcher --shell /usr/sbin/nologin payloadcatcher
sudo mkdir -p /opt/payloadcatcher
sudo chown payloadcatcher:payloadcatcher /opt/payloadcatcher
```

If the account or directory already exists, keep the existing objects and confirm ownership is still correct.

## 4. Deploy the Application Files

Clone the repository directly into the production installation directory.

```bash
sudo -u payloadcatcher git clone https://github.com/t3knoid/payloadcatcher.git /opt/payloadcatcher
cd /opt/payloadcatcher
```

If `/opt/payloadcatcher` already contains a checkout, stop here and use the update procedure in Section 10 instead of cloning again.

Expected installed layout:

```text
/opt/payloadcatcher/
  app/
  alembic/
  frontend/
  docs/
  requirements.txt
  alembic.ini
  .env.example
```

## 5. Create the Python Environment

Build the application virtual environment and install backend dependencies.

```bash
cd /opt/payloadcatcher
sudo -u payloadcatcher python3.12 -m venv .venv
sudo -u payloadcatcher ./.venv/bin/python -m pip install --upgrade pip
sudo -u payloadcatcher ./.venv/bin/pip install -r requirements.txt
```

`requirements-dev.txt` is not required for a production install.

## 6. Build the Frontend Assets

Install the frontend build dependencies and compile the production assets.

```bash
cd /opt/payloadcatcher/frontend
sudo -u payloadcatcher npm ci
sudo -u payloadcatcher npm run build
```

This produces the compiled frontend output under `/opt/payloadcatcher/frontend/dist`, which FastAPI serves directly in production.

## 7. Configure the Application

Create the production environment file from the example.

```bash
cd /opt/payloadcatcher
sudo -u payloadcatcher cp .env.example .env
```

Review `/opt/payloadcatcher/.env` and update at minimum:

- `BASE_URL` to the public HTTPS origin, for example `https://payloadcat.ch`
- `DATABASE_URL` to the production PostgreSQL connection string
- `TRUSTED_PROXIES` to the nginx source address or network, for example `127.0.0.1`
- `COOKIE_SECURE=true`
- `CALLBACK_TTL_HOURS` if you want a non-default inbox lifetime
- `RATE_LIMIT_PER_MINUTE` for your production traffic expectations
- `HOOK_PAYLOAD_MAX_BYTES` for your accepted payload ceiling

For a same-origin production deployment, you generally do not need to add browser development origins to `CORS_ALLOW_ORIGINS`.

## 8. Prepare the Database

Create the database named by `DATABASE_URL` and then apply migrations.

Example using the default PostgreSQL naming pattern:

```bash
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE payloadcatcher"
```

Then apply migrations with the production virtual environment:

```bash
cd /opt/payloadcatcher
sudo -u payloadcatcher ./.venv/bin/alembic upgrade head
```

If your database already exists, do not recreate it. Apply the migration step only.

## 9. Install the System Service and Reverse Proxy

The example in this section uses nginx. If you prefer another reverse proxy, adapt the same public-origin and forwarded-header behavior to your chosen software.

### 9.1 systemd service

Create `/etc/systemd/system/payloadcatcher.service`:

```ini
[Unit]
Description=PayloadCatcher API
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
WorkingDirectory=/opt/payloadcatcher
EnvironmentFile=/opt/payloadcatcher/.env
ExecStart=/opt/payloadcatcher/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
User=payloadcatcher
Group=payloadcatcher

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable payloadcatcher
sudo systemctl start payloadcatcher
```

Confirm the service is running:

```bash
sudo systemctl status payloadcatcher
sudo systemctl is-active payloadcatcher
```

### 9.2 Example nginx reverse proxy

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

## 10. Update an Existing Installation

Use this procedure when `/opt/payloadcatcher` already contains a working deployment.

### 10.1 Pull the new release

```bash
cd /opt/payloadcatcher
sudo systemctl stop payloadcatcher
sudo -u payloadcatcher git fetch --tags origin
sudo -u payloadcatcher git pull --ff-only origin main
```

If you deploy from a tagged release or a non-`main` branch, replace the final checkout target accordingly.

### 10.2 Refresh dependencies

```bash
cd /opt/payloadcatcher
sudo -u payloadcatcher ./.venv/bin/pip install -r requirements.txt
cd /opt/payloadcatcher/frontend
sudo -u payloadcatcher npm ci
```

### 10.3 Rebuild assets and apply migrations

```bash
cd /opt/payloadcatcher/frontend
sudo -u payloadcatcher npm run build
cd /opt/payloadcatcher
sudo -u payloadcatcher ./.venv/bin/alembic upgrade head
```

### 10.4 Review configuration changes

Compare your existing `.env` file against the current `.env.example` and merge any new or changed settings before restarting the service.

### 10.5 Restart and verify

```bash
sudo systemctl start payloadcatcher
sudo systemctl status payloadcatcher
sudo nginx -t
sudo systemctl reload nginx
```

## 11. Verify the Installation

Run these checks after the first install and after every update.

Application checks:

```bash
curl -I https://payloadcat.ch/
curl -I https://payloadcat.ch/healthz
curl -I https://payloadcat.ch/docs
```

Functional checks:

- open the public site entry and confirm a callback URL is provisioned
- open the generated inbox viewer URL and confirm the page loads
- send a webhook to `/hook/{clsid}` and confirm the event appears in the inbox
- confirm callback and viewer URLs use the configured `BASE_URL`

## 12. Monitoring and Operations

Show recent application logs:

```bash
sudo journalctl -u payloadcatcher -n 100
```

Follow application logs live:

```bash
sudo journalctl -u payloadcatcher -f
```

Show service state:

```bash
sudo systemctl status payloadcatcher
```

Useful operational checks:

- verify `/opt/payloadcatcher/frontend/dist` exists after every install or update
- verify `alembic upgrade head` completed successfully before restarting the service
- verify nginx continues to forward the public host and HTTPS scheme correctly

## 13. Common Native Installation Issues

### The service does not start

Check:

- `sudo systemctl status payloadcatcher`
- `sudo journalctl -u payloadcatcher -n 100`
- `/opt/payloadcatcher/.env` for missing or invalid settings

### The site loads but callback URLs are wrong

Check:

- `BASE_URL` matches the public HTTPS origin
- nginx is forwarding `Host` and `X-Forwarded-Proto`
- `TRUSTED_PROXIES` trusts the nginx source address

### The UI does not load correctly

Check:

- `/opt/payloadcatcher/frontend/dist/index.html` exists
- `/opt/payloadcatcher/frontend/dist/assets/` contains the built asset files
- you ran `npm run build` after the latest code update

### Migrations fail during install or update

Check:

- `DATABASE_URL` points to the intended PostgreSQL database
- the database exists and accepts connections from the configured user
- the service is stopped while you are applying schema changes during an update

## 14. Related Documentation

- [config.md](config.md)
- [api.md](api.md)
- [requirements.md](requirements.md)
- [route-contract.md](route-contract.md)
- [development.md](development.md)
```
