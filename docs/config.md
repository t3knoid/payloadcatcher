# PayloadCatcher Configuration Reference

This document tracks the environment-based configuration surface for PayloadCatcher.

Use the values in this reference together with [install.md](install.md) and [development.md](development.md) when creating local or deployment-specific `.env` files.

## Backend Configuration

| Config Name | Default Value | Expected Value Type | Description |
| --- | --- | --- | --- |
| <code>ENV</code> | <code>development</code> | <code>string</code> | Application environment label used for local or deployed backend configuration. |
| <code>BASE_URL</code> | <code>https://<wbr>payloadcat.ch</code> | <code>URL string</code> | Public base URL used when generating callback and viewer links. |
| <code>PORT</code> | <code>8080</code> | <code>integer</code> | Site-facing service port for deployment-oriented configuration. |
| <code>API_BIND_HOST</code> | <code>127.0.0.1</code> | <code>host string</code> | Backend bind host used by the local API server process. |
| <code>API_BIND_PORT</code> | <code>8000</code> | <code>integer</code> | Backend bind port used by the local API server process. |
| <code>DATABASE_URL</code> | <code>postgresql+psycopg://<wbr>postgres:<wbr>postgres@<wbr>localhost:<wbr>5432/<wbr>payloadcatcher</code> | <code>SQLAlchemy database URL string</code> | Database connection string for the backend persistence layer. |
| <code>CALLBACK_TTL_HOURS</code> | <code>24</code> | <code>integer</code> | Lifetime in hours for provisioned inbox callback URLs. |
| <code>RATE_LIMIT_PER_MINUTE</code> | <code>60</code> | <code>integer</code> | Per-minute request budget used by the API rate limiting logic. |
| <code>HOOK_PAYLOAD_MAX_BYTES</code> | <code>1048576</code> | <code>integer</code> | Maximum accepted webhook request body size in bytes. |
| <code>VIEWER_PAYLOAD_PREVIEW_CHARS</code> | <code>4096</code> | <code>integer</code> | Maximum preview length used for inbox listing payload snippets. |
| <code>HEADER_ALLOWLIST</code> | <code>content-type,<wbr>user-agent,<wbr>referer,<wbr>accept-language</code> | <code>comma-delimited string list</code> | Request headers that are retained for viewer-safe metadata display. |
| <code>CORS_ALLOW_ORIGINS</code> | <code>http://<wbr>127.0.0.1:<wbr>5173,<wbr>http://<wbr>localhost:<wbr>5173</code> | <code>comma-delimited origin list</code> | Explicit browser origins allowed to call the backend API through CORS. |
| <code>CORS_ALLOW_ORIGIN_REGEX</code> | <code>^https?://<wbr>(?:localhost|<wbr>127\.0\.0\.1):<wbr>(5173|4173)$</code> | <code>regex string</code> | Regex-based CORS origin rule used for loopback development hosts. |
| <code>CORS_ALLOW_ORIGIN_NETWORK</code> | <code>192.168.10.0/24</code> | <code>CIDR string or comma-delimited CIDR list</code> | Network-scoped CORS allowlist for frontend origins opened from private-network machine IPs such as <code>192.168.0.0/24</code> or <code>192.168.0.22/32</code>. |
| <code>TRUSTED_PROXIES</code> | <code>127.0.0.1,<wbr>::1</code> | <code>comma-delimited IP/CIDR list</code> | Proxy addresses trusted for forwarded client metadata handling. |
| <code>SESSION_COOKIE_NAME</code> | <code>payloadcatcher_session</code> | <code>string</code> | Cookie name used for inbox session continuity. |
| <code>COOKIE_SECURE</code> | <code>true</code> | <code>boolean</code> | Controls whether the session cookie requires HTTPS transport. |
| <code>COOKIE_SAMESITE</code> | <code>lax</code> | <code>enum string</code> (<code>lax</code>, <code>strict</code>, <code>none</code>) | SameSite policy applied to the session cookie. |
| <code>COOKIE_MAX_AGE</code> | <code>86400</code> | <code>integer</code> | Session cookie lifetime in seconds. |

## Frontend Configuration

| Config Name | Default Value | Expected Value Type | Description |
| --- | --- | --- | --- |
| <code>VITE_API_BASE_URL</code> | <code>http://<wbr>127.0.0.1:<wbr>8000</code> | <code>URL string</code> | API origin used by the frontend client for bootstrap, inbox listing, and event detail requests. |

## Notes

| Topic | Detail |
| --- | --- |
| Local loopback access | <code>http://<wbr>127.0.0.1:<wbr>5173</code> and <code>http://<wbr>localhost:<wbr>5173</code> are covered by the explicit origin list and loopback regex. |
| Local machine-IP access | When the frontend is opened on the same machine by IP, keep <code>VITE_API_BASE_URL</code> aligned with the reachable backend origin and allow the frontend origin with <code>CORS_ALLOW_ORIGIN_NETWORK</code>. |
| Cross-device development | When another device loads the frontend over the network, bind the backend to <code>0.0.0.0</code>, use a reachable machine-IP API base URL, and allow the frontend origin network explicitly. |
| Example files | The tables above are seeded from [backend/.env.example](../backend/.env.example) and [frontend/.env.example](../frontend/.env.example). |