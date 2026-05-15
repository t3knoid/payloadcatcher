# PayloadCatcher API Reference

This document tracks the current implemented API surface for PayloadCatcher.

Any API implementation, API behavior change, request or response shape change, status code change, authentication change, pagination change, or error-envelope change must be reflected in this file as part of the same change.

This reference complements [route-contract.md](route-contract.md):

- `docs/route-contract.md` defines the normative product contract and minimal schema expectations.
- `docs/api.md` is the developer-facing reference for what the repository currently implements.

Swagger and OpenAPI documentation are also required parts of the API surface:

- Local Swagger UI: <http://127.0.0.1:8000/docs>
- Local OpenAPI schema: <http://127.0.0.1:8000/openapi.json>
- Implemented routes, request models, response models, status codes, and auth requirements must be reflected in the generated schema.

## Base URLs

- Site entry: `https://www.payloadcat.ch`
- Hook endpoint pattern: `https://payloadcat.ch/hook/{clsid}`
- Viewer endpoint pattern: `https://payloadcat.ch/inbox/{clsid}`

## Serving Defaults

- The site-facing application port defaults to `8080`.
- The local backend API development port remains `8000`.
- Deployments must support reverse-proxy operation without changing canonical external URL behavior.
- External URL generation must rely on configured base URL values and trusted forwarded-header handling.

## Identifier Rules

- `clsid` is a lowercase UUIDv4 string.
- Callback URLs remain valid for 24 hours and rotate after expiration.

## Current Implemented Endpoints

## Interactive API Documentation

Swagger UI must be enabled for the backend API during development on port `8000`.

Required behavior:

- Swagger UI is served at `/docs`.
- OpenAPI JSON is served at `/openapi.json`.
- Route summaries, descriptions, request models, response models, error responses, and auth-related inputs are declared so they render correctly in Swagger.
- API changes are documented both in generated Swagger output and in `docs/api.md`.

### GET /healthz

Return a lightweight process health signal for local development, Docker health checks, and orchestration probes.

Response shape:

```json
{
  "status": "ok"
}
```

Notes:

- This route is operational and not part of the public webhook contract.
- It appears in Swagger and OpenAPI during local development on port `8000`.

### Planned Product Endpoints

The routes below are defined by the current PayloadCatcher contract and must stay aligned with [route-contract.md](route-contract.md) and the generated Swagger schema once implemented.

### GET /

Provision or return the active inbox callback URL for the current browser session.

Expected behavior:

- Creates a new inbox on first visit.
- Returns the same callback URL while the current URL is still valid.
- Issues a new callback URL after expiration.
- Uses cookie-first session continuity.

Documentation updates required when this endpoint changes:

- request or response fields
- cookie or session behavior
- callback lifecycle behavior
- metadata collection or privacy behavior

### POST /hook/{clsid}

Accept a provider-agnostic webhook payload and acknowledge quickly with HTTP 200.

Expected behavior:

- Accepts JSON and non-JSON payloads.
- Stores raw payloads in a byte-safe form.
- Defers heavy processing asynchronously.
- Applies rate limits, payload size limits, and configured callback authentication rules when enabled.

Documentation updates required when this endpoint changes:

- request headers or auth requirements
- accepted payload formats or size limits
- ack behavior or async processing semantics
- deduplication, replay protection, or verification behavior
- status codes or error envelope behavior

### GET /inbox/{clsid}

Return the viewer-facing event list and related inbox data for a valid inbox identifier.

Expected behavior:

- Lists captured events for a valid `clsid`.
- Supports documented pagination and search behavior.
- Renders payloads safely for inspection.
- Redacts viewer-facing network identifiers by default.

Documentation updates required when this endpoint changes:

- response fields
- pagination or search parameters
- payload rendering behavior
- privacy redaction behavior
- status codes or error envelope behavior

## Error Envelope

Non-2xx responses use a safe error envelope with:

- `error.code`
- `error.message`
- `request_id`
- optional safe `details`

Current scaffold behavior:

- Unhandled backend failures return a safe `500` response body with `error.code`, `error.message`, and `request_id`.
- Error responses also include the `X-Request-ID` response header for correlation.

Retryable responses such as `429` and `503` include:

- `Retry-After` header
- `error.details.retry_after_seconds`

## Authentication Modes

Per-inbox callback authentication modes are:

- `none`
- `shared_token`
- `signature`

When authentication behavior changes, update this file and [route-contract.md](route-contract.md) together.

## Documentation Sync Rule

Any change to API implementation or API behavior must update `docs/api.md` in the same pull request.

Any change to API implementation or API behavior must also keep Swagger UI on port `8000` accurate for the affected routes.
