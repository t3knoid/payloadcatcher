# PayloadCatcher Requirements

## 1. Scope

PayloadCatcher is a provider-agnostic webhook capture platform hosted at <https://www.payloadcat.ch>.
The canonical capture and viewer URL patterns are:

- Hook endpoint: <https://payloadcat.ch/hook/{clsid}>
- Viewer endpoint: <https://payloadcat.ch/inbox/{clsid}>

The www host is allowed for site entry, but callback and viewer URLs use the canonical payloadcat.ch host.

Default serving requirements:

- The site is served on port `8080` by default.
- The deployment structure must support running behind a reverse proxy.
- Reverse-proxy deployments must preserve canonical host behavior, forwarded scheme, forwarded host, and client IP handling.
- Development workflows must support Windows, macOS, and Linux.
- Production deployment must support Linux-based hosting and reverse-proxy operation.
- PayloadCatcher supports native cross-platform development workflows on Windows, macOS, and Linux. Docker may be used for local infrastructure, integration testing, and deployment packaging, but core development workflows must not require Docker.

## 2. Identifier and URL Rules

1. `clsid` is always lowercase.
2. `clsid` uses high-entropy UUIDv4 format.
3. A generated callback URL is valid for 24 hours from issuance.
4. After expiration, a new callback URL is issued.
5. Callback URLs use only the hook endpoint shape, for example:
   <https://payloadcat.ch/hook/550e8400-e29b-41d4-a716-446655440000>

## 3. First-Visit Provisioning

1. On first site visit, the backend creates a new inbox `clsid`.
2. The callback URL is paired to requester context anchored to source IP plus a session cookie.
3. If the active URL is still within its 24-hour TTL, the same URL is returned.
4. If the URL is expired, a new `clsid` and callback URL are returned.
5. Session continuity uses cookie-first identity; source IP is a risk and abuse signal, not the sole session key.
6. Source IP normalization honors trusted proxy configuration before using forwarded headers.
7. If source IP changes while session cookie is valid, the callback URL remains stable unless abuse policy requires rotation.

## 4. Visit Metadata Collection

The platform records the following metadata at site visit time:

- Source IP address
- Visit timestamp (UTC)
- Browser type (derived from user-agent)
- Device type (derived from user-agent)
- Referer URL
- User-Agent string
- Locality (IP-geo derived, best effort)
- Language (Accept-Language and browser locale hint)
- Timezone (browser-provided value when available)
- Browser headers (selective allowlist, sanitized)
- GPS location (only when explicit user consent is granted)

Metadata collection is best effort and must not block callback URL provisioning.

## 5. Cookie Requirements

1. Cookies are used to bind a browser session to an issued callback URL lifecycle.
2. Cookies are configured with secure defaults (`HttpOnly`, `Secure`, `SameSite=Lax` at minimum).
3. Cookie TTL does not exceed callback URL TTL unless a stricter policy is configured.

## 6. Inbound Hook Behavior

1. The hook endpoint accepts provider-agnostic payloads (JSON and non-JSON) without provider-specific assumptions.
2. The endpoint acknowledges quickly with HTTP 200.
3. Heavy processing, persistence, and viewer materialization can run asynchronously after ack.
4. Captured payloads are stored as raw canonical data.
5. The viewer presents captures as YAML for human inspection.

## 7. Viewer Behavior

1. Viewer URLs are bearer-style public links by possession of URL.
2. The viewer lists captures associated with a valid `clsid`.
3. If a `clsid` is expired or unknown, the viewer returns a safe not-found response.
4. YAML rendering escapes unsafe content and never executes payload data.

## 8. Abuse Protection

1. Enforce per-originator and per-IP rate limits for both bootstrap and hook endpoints.
2. Enforce payload size limits with explicit rejection behavior.
3. Detect and throttle burst traffic and malformed request patterns.
4. Keep hook acknowledgement path resilient under load.

## 9. Retention and Cleanup

1. Callback URLs remain active for 24 hours.
2. Captured events and expired inbox mappings are cleaned up daily.
3. Cleanup jobs are idempotent and safe under concurrency.

## 10. Configuration via .env

Default settings are configured through `.env` values, including:

- `BASE_URL`
- `CALLBACK_TTL_HOURS` (default 24)
- `CLEANUP_CRON` or `CLEANUP_INTERVAL_HOURS`
- `RATE_LIMIT_PER_MINUTE`
- `HOOK_PAYLOAD_MAX_BYTES`
- `HEADER_ALLOWLIST`
- `GEOIP_ENABLED`
- `GPS_COLLECTION_ENABLED`
- `COOKIE_SECURE`, `COOKIE_SAMESITE`, `COOKIE_MAX_AGE`
- `PORT` (default `8080` for site serving)
- trusted proxy and forwarded-header configuration values required for reverse-proxy deployments

## 10A. Serving and Reverse Proxy Requirements

1. The default site-facing application port is `8080`.
2. The architecture must support deployment behind a reverse proxy such as Nginx, Caddy, Traefik, or equivalent infrastructure.
3. Reverse-proxy support must preserve:
   - canonical host behavior for `payloadcat.ch`
   - forwarded scheme handling for HTTP to HTTPS termination
   - trusted proxy-aware client IP normalization
   - header forwarding required for request tracing and safe origin handling
4. Reverse-proxy deployment must not break callback generation, viewer URLs, rate limiting, or auth verification behavior.
5. Public URL generation must rely on configured external base URL values rather than raw socket host and port values.
6. Local development and test workflows must remain executable on Windows, macOS, and Linux without requiring OS-specific application logic.
7. Production runtime assumptions may target Linux-based hosting, but repository structure and tooling must remain cross-platform for development use.

## 11. Legal and Privacy Warning

PayloadCatcher collects connection and browser metadata and can collect location data when users opt in.
This can be personal data in multiple jurisdictions.

Minimum requirements:

1. Display a clear privacy notice before or at data collection time.
2. Request explicit consent before collecting GPS data.
3. Support lawful basis, retention limits, and deletion handling per applicable law.
4. Avoid collecting unnecessary headers or sensitive values.
5. Document operator responsibilities for regional compliance (for example GDPR, CPRA/CCPA, and similar regimes).

## 12. UI Requirements

1. Keep UI complexity minimal and task-focused.
2. Provide a top header containing:
   - A compact menu entry point.
   - A recognizable app logo.
3. Present the callback URL as a clickable control.
4. When the callback URL is clicked, copy the URL to the clipboard so users can paste it immediately.
5. Main inbox view uses a two-column layout:
   - Left column is narrower and contains request list plus search bar.
   - Right column is wider and displays the payload associated with the selected request.
6. Clicking a request in the left column updates the payload panel in the right column.
7. Payload panel renders captured data as YAML and supports large payload viewing safely.
8. Layout works on desktop and mobile:
   - Desktop uses side-by-side columns.
   - Mobile stacks list and payload panels while preserving request selection behavior.
9. Small-device support is required, with a mobile-first baseline viewport range suitable for modern phones and common portrait scrolling behavior.

## 13. Future Authentication and Account Extensibility

1. The architecture must support adding user accounts without breaking existing anonymous capture flows.
2. Authentication and authorization concerns must live behind dedicated service interfaces and middleware, not inside individual business handlers.
3. Inbox ownership must be modelled so an inbox can transition from anonymous to account-bound access.
4. Access control must support independent permissions for read, replay, and delete actions.
5. Callback authentication must be pluggable and provider-agnostic, with support for modes such as shared token and signature verification.
6. Hook ingestion must support optional authenticated callback validation while preserving a clearly isolated unsigned capture mode.
7. Data models must remain migration-friendly for future entities such as `users`, `inbox_memberships`, `api_tokens`, and callback verification secrets.
8. API contracts must remain versionable so future authenticated routes can be introduced without breaking existing clients.
9. Observability must include authentication outcomes (allowed, denied, missing credentials, invalid signature) without logging secrets.

## 14. Payload Format and Rendering Rules

1. Ingestion supports arbitrary webhook body formats, including JSON, form-encoded, plain text, and binary payloads.
2. Persistence stores byte-safe raw payload data plus content metadata (`content_type`, payload size, and encoding hints where available).
3. Viewer rendering is best effort and safe:
   - Render YAML for structured payloads when conversion is deterministic.
   - Render text preview for text payloads.
   - Render metadata-only preview for binary payloads.
4. Rendering failures must never block storage or ack behavior.

## 15. Error Envelope and Failure Semantics

1. API endpoints use a consistent error envelope for all non-2xx responses.
2. Error envelopes include at minimum: `error.code`, `error.message`, `request_id`, and safe `details` when relevant.
3. Public endpoint failures must not leak stack traces, secrets, local paths, or internal implementation details.
4. Failure semantics are documented for at least: 400, 401, 403, 404, 413, 415, 422, 429, and 5xx.
5. Retry semantics are explicit for retryable responses:
   - 429 and 503 responses include `Retry-After` header and `error.details.retry_after_seconds`.
   - Non-retryable client errors do not include retry hints.

## 15A. API Documentation Requirements

1. The backend API must expose Swagger UI generated from the OpenAPI schema.
2. Local development Swagger UI is served from the backend on port `8000`.
3. The default local documentation URL is `<http://127.0.0.1:8000/docs>`.
4. The default local OpenAPI schema URL is `<http://127.0.0.1:8000/openapi.json>`.
5. All implemented API routes, request bodies, response models, status codes, and auth requirements must be represented in the generated OpenAPI schema.
6. Swagger documentation must stay aligned with `docs/api.md` and `docs/route-contract.md`.
7. Any API implementation or API modification is incomplete unless both the generated Swagger documentation and `docs/api.md` reflect the change.
8. Site-facing serving defaults on port `8080` do not change the local backend API documentation requirement on port `8000`.

## 16. Listing Scale and Query Behavior

1. Inbox event listing supports pagination with stable sorting by receive time.
2. Search behavior is defined for request id, method, source IP, and payload preview text.
3. Pagination contracts define limit bounds and a cursor/token for next page retrieval.
4. Viewer selection behavior remains deterministic when paginated results change.
5. Default and maximum page size values are documented and enforced consistently.

## 17. Callback Authentication and Secret Lifecycle

1. Callback auth modes are explicit per inbox, at minimum: `none`, `shared_token`, and `signature`.
2. Secrets/tokens are generated with high entropy and never stored or logged in plaintext.
3. Secret material uses hashing or encryption-at-rest based on verification mode.
4. Rotation and revocation are supported without downtime.
5. Signature verification supports replay resistance with timestamp windows and nonce/idempotency checks.
6. Verification failures return safe, auditable outcomes without exposing secret values.

## 18. Idempotency and Deduplication

1. Ingestion supports retry-safe behavior through deterministic deduplication when enabled.
2. Deduplication keys and windows are explicit and documented.
3. Duplicate events are either linked to existing records or marked with dedup metadata without data corruption.
4. Idempotency controls remain provider-agnostic and do not assume vendor-specific headers.

## 19. Observability and SLO Baselines

1. Define measurable ingest-path latency targets (for example ack latency and persistence completion latency).
2. Emit metrics for receive rate, payload size distribution, rejection reasons, and storage outcomes.
3. Propagate request correlation IDs across API, service, worker, and persistence layers.
4. Structured logs include auth decisions, rate-limit decisions, and cleanup outcomes without secret leakage.

## 20. Privacy Operations and Data Subject Handling

1. Provide operator workflows for deletion, export, and retention override requests where legally required.
2. Document metadata retention durations separately from payload retention durations.
3. GPS and locality fields follow data minimization defaults and are removable via cleanup or operator request.
4. Privacy documentation includes cross-region compliance responsibility notes for operators.
5. Viewer-facing network identifiers are redacted by default in public bearer-link views.
