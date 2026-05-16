# PayloadCatcher Development Guide

## 1. Purpose

This guide defines the local software stack and setup flow for developing, running, and debugging PayloadCatcher from source.

PayloadCatcher development workflows are expected to support Windows, macOS, and Linux.

PayloadCatcher supports native cross-platform development workflows on Windows, macOS, and Linux. Docker may be used for local infrastructure, integration testing, and deployment packaging, but core development workflows must not require Docker.

## 2. Target Development Stack

Backend:

- Python 3.12
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

Frontend:

- Node.js 20 LTS
- Vue 3
- Vite
- Centralized API client pattern

Data and infrastructure:

- PostgreSQL 15 or newer (local development)
- SQLite may be used for selected tests

Tooling:

- Git
- VS Code
- Docker Desktop (optional, recommended for local Postgres)

Operating system support:

- Development is expected to work on Windows, macOS, and Linux.
- Production deployment may target Linux-based hosting.
- Commands in this guide use Linux shell examples. If you are developing on Windows or macOS, adapt activation and file-copy syntax for your local shell.

## 3. Recommended VS Code Extensions

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Vue - Official (Vue.volar)
- ESLint (dbaeumer.vscode-eslint)
- Prettier (esbenp.prettier-vscode)
- PostgreSQL client extension of your choice (optional)

## 4. Source Layout Expectations

Use this layout for local development:

```text
payloadcatcher/
  backend/
    app/
      api/
      core/
      middleware/
      services/
      infrastructure/
      persistence/
    alembic/
    requirements files
    Dockerfile
    .env.example
  frontend/
    src/
    package.json
  docs/
```

If your local structure differs, adjust path-based commands accordingly.

If you are not using a Linux-compatible shell locally, adapt activation and path syntax for your environment.

## 5. Environment Configuration

Create environment files for local development.

Backend local env example:

```env
ENV=development
BASE_URL=https://payloadcat.ch
PORT=8080
CALLBACK_TTL_HOURS=24
CLEANUP_INTERVAL_HOURS=24
RATE_LIMIT_PER_MINUTE=60
HOOK_PAYLOAD_MAX_BYTES=1048576
VIEWER_PAYLOAD_PREVIEW_CHARS=4096
HEADER_ALLOWLIST=content-type,user-agent,accept-language,referer
GEOIP_ENABLED=true
GPS_COLLECTION_ENABLED=true
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
COOKIE_MAX_AGE=86400
SESSION_COOKIE_NAME=payloadcatcher_session
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/payloadcatcher
```

Cookie note:

- Session cookies use secure defaults in the application configuration.
- If you intentionally run the backend over plain local HTTP for browser testing, set `COOKIE_SECURE=false` in your uncommitted local `.env` override.
- Keep `COOKIE_SECURE=true` for shared, preview, and production-like environments.

The default site-facing serving port is `8080`. Local backend API development and Swagger access continue to use port `8000` unless your local stack intentionally consolidates them.
The example `DATABASE_URL` uses `localhost` for native local development. When running through Docker Compose, the API container uses the `db` service hostname instead.

Frontend local env example:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The frontend accepts the API base URL from `frontend/.env`, `frontend/.env.local`, or a runtime-injected `window.__PAYLOADCATCHER_CONFIG__` object. If no frontend env file is present, copy `frontend/.env.example` and adjust it for your local backend origin.

Never commit secrets in local env files.

`VIEWER_PAYLOAD_PREVIEW_CHARS` controls the public inbox preview length and must be an integer greater than or equal to `4`.

## 6. Backend Setup and Run

From repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install dependencies using the backend project definition:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Create the PostgreSQL database referenced by `DATABASE_URL` before running Alembic for the first time.

Example using the default local settings from Section 5:

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

If you use a different database name or PostgreSQL role in `DATABASE_URL`, create that database instead. When running through Docker Compose, the `db` service creates the `payloadcatcher` database automatically.

Apply database migrations:

```bash
alembic upgrade head
```

Migration workflow:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic downgrade -1
```

Migration strategy notes:

- Keep ORM models under `backend/app/persistence/` and keep Alembic revisions aligned to the shared SQLAlchemy metadata.
- Review autogenerated revisions before applying them, especially constraints, index definitions, and byte-safe payload column types.
- Prefer additive, reversible migrations and keep rollback steps valid for local and deployment use.
- The initial schema provisions `inboxes`, `visit_metadata`, and `webhook_events` with the indexed query paths defined in `docs/route-contract.md`.

Rollback procedure:

- Use `alembic downgrade -1` to roll back the most recent revision.
- Use `alembic downgrade base` only when intentionally removing all managed schema from the target database.
- After downgrade, rerun `alembic upgrade head` to confirm the migration chain remains reversible.

Run backend in reload mode:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation endpoints during local development:

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

Swagger is the required interactive API documentation surface for local development. Keep FastAPI route metadata, request models, response models, and status code declarations accurate so the generated docs stay aligned with `docs/api.md`.

The initial backend scaffold exposes the operational health route at `<http://127.0.0.1:8000/healthz>` in addition to Swagger and OpenAPI endpoints.
The backend also exposes `GET /` for cookie-backed inbox provisioning and callback URL reuse.
The hook ingress path `POST /hook/{clsid}` accepts provider-agnostic payloads, acknowledges quickly, and persists in a background task.
The viewer path `GET /inbox/{clsid}` exposes bearer-style inbox browsing with safe previews, search, pagination, and masked network identifiers.

Reverse proxy note:

- Default site-facing deployments should expose port `8080` to the proxy tier.
- Proxy configuration must forward host, scheme, and client IP information correctly.
- Public URL generation must use configured external base URL settings rather than backend bind address values.

## 7. Frontend Setup and Run

From repository root:

```bash
cd frontend
npm install
npx playwright install chromium
npm run dev
```

Frontend quality checks:

```bash
cd frontend
npm run lint
npm run test
npm run build
npm run test:e2e
```

Default local dev URL is typically:

- <http://127.0.0.1:5173>

The scaffold uses Vue Router history mode for `/` and `/inbox/{clsid}` and uses a centralized API client under `frontend/src/api/api-client.ts` for all backend requests.

Optional Docker Compose workflow:

```bash
docker compose up --build frontend api db
```

The Compose frontend service binds Vite to `0.0.0.0:5173` and targets the backend API at `http://127.0.0.1:8000` for browser traffic on the host machine.

## 8. Run the Site from Source

1. Start PostgreSQL, create the database referenced by `DATABASE_URL` if it does not exist yet, and ensure the connection is reachable.
2. Start backend (Section 6).
3. Start frontend (Section 7).
4. Open the frontend URL.
5. Open <http://127.0.0.1:8000/docs> and confirm Swagger UI loads.
6. Verify callback generation, request list rendering, payload panel selection, and inbox route loading.
7. Confirm `<http://127.0.0.1:8000/healthz>` returns `{"status": "ok"}`.

## 9. Debugging in VS Code

Create .vscode/launch.json with backend and frontend profiles.

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend: Uvicorn",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8000"
      ],
      "cwd": "${workspaceFolder}/backend",
      "justMyCode": true,
      "envFile": "${workspaceFolder}/backend/.env"
    },
    {
      "name": "Frontend: Chrome",
      "type": "pwa-chrome",
      "request": "launch",
      "url": "http://127.0.0.1:5173",
      "webRoot": "${workspaceFolder}/frontend"
    }
  ]
}
```

Debugging tips:

1. Put breakpoints in API routers and service layers to confirm boundary separation.
2. Break on exception in backend while testing malformed webhooks.
3. Verify quick 200 hook responses while async persistence continues.
4. Use browser network tools to confirm callback copy behavior and inbox list/payload updates.
5. Use Swagger UI on port `8000` to verify documented request and response models match the implementation.

## 10. Test and Quality Workflow

Use [qa-test-guide.md](qa-test-guide.md) as the source of truth for QA suite definitions, case inventory, and regression pack selection.

Backend tests:

```bash
cd backend
pytest
```

Bootstrap endpoint regression:

```bash
cd backend
pytest tests/test_inbox_service.py tests/test_bootstrap_api.py
```

Hook ingestion regression:

```bash
cd backend
pytest tests/test_webhook_service.py tests/test_hook_api.py
```

Inbox viewer regression:

```bash
cd backend
pytest tests/test_inbox_viewer_service.py tests/test_inbox_viewer_api.py
```

Migration verification:

```bash
cd backend
pytest tests/test_persistence_models.py tests/test_migrations.py
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run test
```

End-to-end tests (when configured):

```bash
npx playwright install chromium
npm run test:e2e
```

Docker Compose development stack:

```bash
docker compose up --build
```

Compose note:

- The Compose API service overrides `DATABASE_URL` to use the container-network database host `db`.

## 11. Common Local Issues

1. Migration errors:
   - Confirm DATABASE_URL and that Postgres is running.
2. CORS/API errors in frontend:
   - Confirm VITE_API_BASE_URL points to backend URL.
3. Missing callback data in viewer:
   - Confirm backend worker/background path is active and no payload-size rejection occurred.
4. Signature auth test failures:
   - Confirm timestamp skew window, header names, and signing algorithm.

## 12. Security Notes for Development

1. Treat all webhook payloads as untrusted input.
2. Do not log raw credentials, tokens, or signature secrets.
3. Keep unsigned callback mode isolated and clearly marked in development configs.
4. Use sample data for manual testing whenever possible.
