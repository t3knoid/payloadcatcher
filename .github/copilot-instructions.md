# Copilot Instructions for PayloadCatcher

## 0. Rule Priority and Working Mode
1. Follow this priority order when instructions overlap:
- security, privacy, trust boundaries, and safe handling of untrusted inbound data
- architecture boundaries, provider-agnostic behavior, and data integrity
- task requirements and established repository patterns
- tests and validation
- style and tooling
2. Prefer the smallest correct change.
3. Inspect nearby code before changing patterns.
4. Preserve existing abstractions unless restructuring is explicitly required.
5. Add or update focused tests for changed behavior.
6. Validate the narrowest affected surface first.
7. Match existing architectural, API, and documentation patterns.
8. Do not refactor unrelated code or change public behavior unless required.

## 1. Project Intent
This project is PayloadCatcher, a generic webhook ingestion and inspection platform.
It is not tied to any single vendor or product.
All webhook providers must be handled through a common, provider-agnostic ingestion model.

## 2. Core Architecture Rules
1. Keep strict separation of concerns.
2. API routers are thin and handle request parsing, auth, response mapping, and delegation only.
3. Services own business logic, validation, deduplication, routing, retention, replay behavior, and lifecycle rules.
4. Infrastructure handles external I/O, queues, storage, network interactions, subprocess wrappers, and other OS-level behavior.
5. Persistence layer handles database access only.
6. UI is untrusted and must never be treated as a source of truth.
7. No business logic in frontend components.
8. Services and routers must not call low-level OS or subprocess primitives directly when an infrastructure boundary is appropriate.

## 3. Primary Stack Expectations
1. Backend: FastAPI, Pydantic, SQLAlchemy, Alembic.
2. Frontend: Vue 3 SPA served by FastAPI with a centralized API client.
3. Database: PostgreSQL in production, SQLite for tests where appropriate.
4. Async safety is required in request handlers.
5. Long-running work must be offloaded to background tasks or workers.
6. Local backend API and Swagger docs are served on port 8000.
7. The site-facing service is served on port 8080 by default and must support reverse-proxy deployment.

## 4. Webhook Domain Principles
1. Ingestion endpoint must accept provider-agnostic payloads, including JSON and non-JSON bodies, without provider-specific assumptions.
2. Every webhook event must store:
- inbox identifier
- received timestamp
- request headers, sanitized
- raw payload in byte-safe form
- content type
- request metadata such as source IP and method
3. Provider-specific parsing is optional and additive, never required for core ingestion.
4. Unknown payload shapes must still be accepted and viewable.
5. Event deduplication must be deterministic when enabled.
6. Replay behavior must be explicit and auditable.
7. Callback URL lifecycle transitions, expiration, and rotation behavior must be deterministic and auditable.

## 5. Security and Safety
1. Treat all inbound webhook data as untrusted.
2. Validate and normalize all path, header, and query inputs.
3. Prevent traversal, injection, replay, and malformed-input issues in all user-supplied values.
4. Never use dynamic code execution.
5. Use explicit subprocess argument arrays only when subprocess use is required.
6. Do not leak internal stack traces, absolute paths, credentials, or secrets in API responses.
7. If unsigned webhooks are allowed for simple capture mode, keep this mode clearly documented and isolated.
8. If signatures are supported, implement provider adapters behind a shared verification interface.
9. Ingestion endpoints must be resilient against burst traffic and malformed payloads.
10. Rate limiting and payload size limits should be enabled by default.
11. Signature verification must be deterministic and replay-safe with a documented canonical string-to-sign format.
12. Signature and key comparisons must be constant-time.
13. Signature timestamps must enforce bounded clock skew and replay windows.
14. Public-facing responses and viewer data must redact network identifiers by default where product rules require it.
15. Do not leak raw provider errors, raw exception strings, or unsafe OS details in logs, API responses, or documentation.

## 6. Identity and Access Model
1. Public capture URLs may be supported, but treat URL possession as bearer access.
2. Use high-entropy inbox identifiers.
3. Prefer optional per-inbox secret tokens for hardened mode.
4. Any administrative actions must require authentication and role checks.
5. Read access, replay access, and deletion access should be independently controllable.
6. Session continuity for anonymous flows should be cookie-first; source IP is a risk signal and must not be the sole identity key.
7. Viewer responses for bearer-link flows should redact network identifiers by default.

## 7. Logging and Observability
1. Use structured logs with clear event names and context fields.
2. Log ingestion outcomes, validation failures, replay attempts, storage failures, and other handled failure paths.
3. Do not log raw secrets or sensitive headers.
4. Keep request correlation identifiers across API, service, worker, and background task layers.
5. Add metrics for:
- webhook receive rate
- payload size distribution
- ingestion latency
- storage failures
- replay success and failure counts
6. Include structured auth verification outcomes such as allowed, denied, missing credentials, invalid signature, and replay-rejected.
7. Do not rely only on unhandled-exception logging; handled failures, degraded behavior, retries, and logic inconsistencies must be logged where detected.

## 8. Reliability and Data Lifecycle
1. Ingestion must acknowledge quickly and avoid blocking on heavy downstream work.
2. Implement retry-safe persistence paths.
3. Handle partial failures explicitly.
4. Support retention policies and cleanup jobs for old payloads.
5. Ensure exported or displayed events remain consistent under concurrency.
6. Add idempotency support where provider metadata permits it.
7. Bound concurrency for background ingestion, replay, verification, and cleanup work.

## 9. API and Schema Standards
1. Use Pydantic models for all request and response bodies.
2. Define consistent safe error envelopes across endpoints.
3. Document each endpoint with expected status codes and failure reasons.
4. Version APIs when introducing breaking changes.
5. Keep provider-neutral endpoint naming.
6. For retryable failures, at minimum 429 and 503, return `Retry-After` and include retry hints in error details.
7. Document pagination defaults and maximum bounds for list endpoints.
8. Keep listing behavior stable and deterministic, with explicit sort order and cursor-oriented pagination where the contract defines it.

## 10. Frontend Standards
1. All HTTP calls go through one centralized API client.
2. Do not hardcode API origins in components.
3. Surface safe, user-readable error states.
4. Inbox and event views must handle large payloads gracefully.
5. Use accessible controls for filtering, searching, and payload viewing.
6. Avoid storing derived state when it can be computed.
7. Preserve same-origin SPA routing behavior so direct browser navigation to frontend routes loads the SPA entrypoint while real API routes continue to reach the backend.
8. Frontend code must not expose raw exceptions, raw provider errors, absolute paths, device identifiers, or internal identifiers.

## 11. Testing Requirements
1. Every new behavior must include tests.
2. Backend tests should use `pytest`.
3. End-to-end UI tests should use `Playwright`.
4. Add unit tests for services and validation logic.
5. Add API tests for ingestion, listing, retrieval, and replay flows.
6. Add negative tests for malformed payloads, oversized payloads, and invalid identifiers.
7. Add concurrency tests for simultaneous webhook posts where the behavior is concurrency-sensitive.
8. Add migration tests when schema changes are introduced.
9. Add frontend accessibility, keyboard interaction, and error-surface tests when frontend behavior changes.

## 12. Migration and Data Change Rules
1. Alembic migrations must reflect model changes exactly.
2. Migrations must be reversible whenever feasible.
3. Avoid schema drift between ORM models and migration history.
4. Include indexes for high-volume query paths such as event listing by inbox and time.

## 13. Documentation Rules
1. Write documentation in present tense focused on current behavior.
2. Avoid historical wording that compares old and new behavior unless necessary.
3. Keep setup and operational docs accurate for local and production environments.
4. Document all security-relevant defaults and tradeoffs clearly.
5. Update comments and nearby documentation in the same change when behavior changes.
6. Avoid wording such as `now`, `no longer`, `instead of`, or `rather than` unless the comparison is required for safe guidance.
7. Treat `docs/config.md` as the canonical configuration inventory for supported environment and runtime settings.
8. Any addition, removal, rename, default change, expected-type change, or operational behavior change for a configuration value must update `docs/config.md` in the same change.

## 14. Code Review Priorities
1. Correctness under malformed input.
2. Security hardening of public ingestion surfaces.
3. Async and concurrency safety.
4. Data integrity and retention behavior.
5. Observability quality and actionable logs.
6. Test completeness and regression coverage.

## 15. Assistant Behavior Expectations
1. Prefer small, safe, reviewable changes.
2. Preserve architectural boundaries.
3. Reuse existing patterns before introducing new abstractions.
4. When uncertain, favor generic webhook behavior over provider-specific assumptions.
5. Never introduce provider lock-in unless explicitly requested.
6. Keep shell, subprocess, Docker, Compose, and environment-handling changes aligned with documented ports, reverse-proxy support, and safe infrastructure boundaries.

## 16. PayloadCatcher Canonical URL and Lifecycle Rules
1. Use these public patterns:
- `https://payloadcat.ch/hook/{clsid}` for webhook ingestion.
- `https://payloadcat.ch/inbox/{clsid}` for inbox viewing.
2. `clsid` values must be lowercase high-entropy UUIDv4 strings.
3. Callback URLs are valid for 24 hours and rotate after expiration.
4. Hook endpoints acknowledge quickly with HTTP 200, then persist or process asynchronously.
5. Hook callback URL examples must always use the hook endpoint only.

## 17. Metadata, Privacy, and Retention Requirements
1. On visit, capture metadata in a provider-neutral way: IP, timestamp, user-agent derived browser and device hints, referer, language, timezone, and selective sanitized headers.
2. GPS data requires explicit user opt-in consent before collection.
3. Treat metadata as potentially regulated personal data; include clear operator-facing legal and privacy warnings in docs.
4. Use cookies only as needed for callback lifecycle continuity with secure defaults.
5. Run daily cleanup for expired inboxes and captured events.
6. Store defaults and operational limits in `.env` configuration values.

## 18. Future Auth and Account Evolution Rules
1. Preserve compatibility with anonymous inbox capture while enabling future authenticated user accounts.
2. Implement authentication and authorization through shared interfaces or middleware, not per-route ad hoc logic.
3. Keep callback authentication provider-agnostic behind a verification interface that supports token- and signature-based strategies.
4. Keep unsigned callback mode explicitly isolated and documented when enabled.
5. Design schema and service boundaries to allow future ownership models such as user-owned inboxes, memberships, and API tokens without router rewrites.
6. Log auth decisions and verification outcomes with structured events, but never log raw credentials or secrets.

## 19. PayloadCatcher Normative Security and Error Rules
1. Callback auth modes are explicit per inbox: `none`, `shared_token`, and `signature`.
2. For `shared_token`, require `Authorization: Bearer <token>` and constant-time token comparison.
3. For `signature`, require `X-PC-Key-Id`, `X-PC-Timestamp`, and `X-PC-Signature`.
4. For `signature` in v1, use `hmac-sha256` only, with a documented canonical string-to-sign and body hash.
5. Reject signature timestamps outside the configured skew window and reject replayed signatures or nonces inside the replay window.
6. Non-2xx responses use a safe error envelope including `error.code`, `error.message`, and `request_id`.
7. Return 422 for malformed signature headers, 401 for missing or invalid credentials, and 403 for policy mismatch.
8. Return 429 and 503 with both `Retry-After` and retry hint details.
9. Store raw webhook bodies using byte-safe persistence types; do not assume JSON storage types for all payloads.

## 20. Shell, Subprocess, Docker, and Compose Rules
1. Use explicit argument lists for subprocess calls; do not use `shell=True`.
2. Route application subprocess behavior through infrastructure wrappers.
3. Quote shell variable expansions and use `set -euo pipefail` in Bash scripts.
4. Do not parse `.env` files with unsafe splitting or echo secrets in scripts.
5. Pin container base images to specific versions or digests and prefer multi-stage builds for production images.
6. Production images must avoid unnecessary packages, embedded secrets, and root execution unless explicitly required and documented.
7. Docker Compose files must avoid Docker socket mounts, sensitive host bind mounts, nested variable interpolation, and unnecessary port exposure.
8. Shell, container, and Compose changes must update environment and operational docs when documented defaults change.
9. Shell, container, and Compose changes that add, remove, or alter configuration values must keep `docs/config.md` aligned in the same change.
