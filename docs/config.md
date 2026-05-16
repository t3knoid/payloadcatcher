# PayloadCatcher Configuration Reference

This document tracks the environment-based configuration surface for PayloadCatcher.

Use the values in this reference together with [install.md](install.md) and [development.md](development.md) when creating local or deployment-specific `.env` files.

## Backend Configuration

| Config Name | Default Value | Expected Value Type | Description |
| --- | --- | --- | --- |
| `ENV` | `development` | `string` | Application environment label used for local or deployed backend configuration. |
| `BASE_URL` | `https://payloadcat.ch` | `URL string` | Public base URL used when generating callback and viewer links. |
| `PORT` | `8080` | `integer` | Site-facing service port for deployment-oriented configuration. |
| `API_BIND_HOST` | `127.0.0.1` | `host string` | Backend bind host used by the local API server process. |
| `API_BIND_PORT` | `8000` | `integer` | Backend bind port used by the local API server process. |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/payloadcatcher` | `SQLAlchemy database URL string` | Database connection string for the backend persistence layer. |
| `CALLBACK_TTL_HOURS` | `24` | `integer` | Lifetime in hours for provisioned inbox callback URLs. |
| `RATE_LIMIT_PER_MINUTE` | `60` | `integer` | Per-minute request budget used by the API rate limiting logic. |
| `HOOK_PAYLOAD_MAX_BYTES` | `1048576` | `integer` | Maximum accepted webhook request body size in bytes. |
| `VIEWER_PAYLOAD_PREVIEW_CHARS` | `4096` | `integer` | Maximum preview length used for inbox listing payload snippets. |
| `GPS_COLLECTION_ENABLED` | `true` | `boolean` | Controls whether explicit browser GPS opt-in requests are persisted in visit metadata. |
| `LOCALITY_HEADER_NAME` | `x-geo-city` | `header name string or empty` | Trusted-proxy header used for best-effort locality capture. Set it to an empty value to disable locality header ingestion. |
| `HEADER_ALLOWLIST` | `content-type,user-agent,referer,accept-language` | `comma-delimited string list` | Request headers that are retained for viewer-safe metadata display. |
| `CORS_ALLOW_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | `comma-delimited origin list` | Explicit browser origins allowed to call the backend API through CORS. |
| `CORS_ALLOW_ORIGIN_REGEX` | `^https?://(?:localhost\|127\.0\.0\.1):(5173\|4173)$` | `regex string` | Regex-based CORS origin rule used for loopback development hosts. |
| `CORS_ALLOW_ORIGIN_NETWORK` | `(empty)` | `CIDR string or comma-delimited CIDR list` | Network-scoped CORS allowlist for frontend origins opened from private-network machine IPs. Keep it empty unless needed, then prefer the smallest practical CIDR such as `192.168.0.22/32` or `192.168.0.0/24`. |
| `TRUSTED_PROXIES` | `127.0.0.1,::1` | `comma-delimited IP/CIDR list` | Proxy addresses trusted for forwarded client metadata handling. |
| `SESSION_COOKIE_NAME` | `payloadcatcher_session` | `string` | Cookie name used for inbox session continuity. |
| `COOKIE_SECURE` | `true` | `boolean` | Controls whether the session cookie requires HTTPS transport. |
| `COOKIE_SAMESITE` | `lax` | `enum string` (`lax`, `strict`, `none`) | SameSite policy applied to the session cookie. |
| `COOKIE_MAX_AGE` | `86400` | `integer` | Session cookie lifetime in seconds. |

## Frontend Configuration

| Config Name | Default Value | Expected Value Type | Description |
| --- | --- | --- | --- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | `URL string` | API origin used by the frontend client for bootstrap, inbox listing, and event detail requests. |

## Notes

| Topic | Detail |
| --- | --- |
| Local loopback access | `http://127.0.0.1:5173` and `http://localhost:5173` are covered by the explicit origin list and loopback regex. |
| Local machine-IP access | When the frontend is opened on the same machine by IP, keep `VITE_API_BASE_URL` aligned with the reachable backend origin and allow the frontend origin with `CORS_ALLOW_ORIGIN_NETWORK`. |
| Cross-device development | When another device loads the frontend over the network, bind the backend to `0.0.0.0`, use a reachable machine-IP API base URL, and allow the frontend origin network explicitly. |
| Visit locality capture | `LOCALITY_HEADER_NAME` is read only from clients listed in `TRUSTED_PROXIES`; use it with a reverse proxy that injects sanitized IP-geo locality data. |
| Example files | The tables above are seeded from [backend/.env.example](../backend/.env.example) and [frontend/.env.example](../frontend/.env.example). |
