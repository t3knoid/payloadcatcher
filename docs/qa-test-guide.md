# PayloadCatcher QA Test Guide

This guide scaffolds the QA test suites and test cases for PayloadCatcher.

Use it to plan manual QA, automate regression coverage, and confirm that implemented behavior stays aligned with:

- `docs/requirements.md`
- `docs/route-contract.md`
- `docs/api.md`
- `docs/ui-mock.md`
- `docs/development.md`

## 1. Purpose

This guide defines:

1. the core QA test suites for PayloadCatcher
2. the related test cases each suite should contain
3. which checks are currently executable versus planned for upcoming implementation work
4. the minimum regression coverage expected before merging behavior changes

## 2. QA Strategy

Use a layered test approach:

| Layer | Primary tools | Purpose |
| --- | --- | --- |
| Unit | `pytest` | Validate service logic, validation, parsing, and persistence behavior in isolation. |
| API | `pytest` + FastAPI test client | Verify request/response contracts, error envelopes, auth handling, and negative cases. |
| Migration | `pytest` + Alembic | Verify schema creation, indexes, and reversible migrations. |
| End-to-end UI | `Playwright` | Verify callback provisioning, inbox viewing, payload rendering, responsive layout, and copy flows. |
| Manual exploratory QA | Browser, Swagger UI, local environment | Verify product workflows, edge cases, privacy-visible behavior, and operator experience. |

## 3. Execution Status Model

Use these statuses while building out the test program:

| Status | Meaning |
| --- | --- |
| `implemented` | A runnable automated test exists in the repository. |
| `ready` | The test case is fully specified and can be implemented as soon as the feature exists. |
| `blocked` | The test case depends on product behavior that is not implemented yet. |

## 4. Entry Criteria For QA

Run or update the relevant suites when a change affects any of the following:

- API routes, request or response models, or error semantics
- SQLAlchemy models, Alembic revisions, or indexed query paths
- callback lifecycle, auth behavior, deduplication, or retention logic
- frontend inbox flows, payload rendering, search, pagination, or responsive layout
- privacy-visible behavior such as metadata collection, consent prompts, or redaction
- deployment or configuration behavior documented in `.env`, Swagger, or reverse-proxy setup

## 5. Test Suites And Cases

## Suite QA-001 Backend Scaffold And Operational Health

Purpose: verify the basic backend process contract and developer-facing operational surface.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-001-01 | `GET /healthz` returns `200` and `{ "status": "ok" }` | API | implemented | Health endpoint responds with the documented shape. |
| QA-001-02 | Every backend response includes `X-Request-ID` | API | implemented | Response includes a non-empty correlation header. |
| QA-001-03 | Unhandled backend exceptions return the safe `500` error envelope | API | implemented | Response omits internal details and includes `request_id`. |
| QA-001-04 | Swagger UI loads at `/docs` on port `8000` | Manual/API | ready | Swagger UI renders without server errors. |
| QA-001-05 | OpenAPI JSON loads at `/openapi.json` | API | implemented | Schema is returned and includes implemented routes. |

## Suite QA-002 Configuration And Environment Parsing

Purpose: verify environment configuration defaults and cross-environment parsing behavior.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-002-01 | Comma-delimited `CORS_ALLOW_ORIGINS` parses correctly | Unit | implemented | Settings convert the env string into the expected list. |
| QA-002-02 | Comma-delimited `TRUSTED_PROXIES` parses correctly | Unit | implemented | Settings convert the env string into the expected list. |
| QA-002-03 | JSON-array list env values parse correctly | Unit | ready | Settings accept equivalent JSON list input. |
| QA-002-04 | Default local API docs bind to port `8000` while site-facing port remains `8080` | Manual | ready | Local docs and serving defaults remain distinct and documented. |

## Suite QA-003 Database Schema And Migration Safety

Purpose: verify that the persistence layer matches the documented schema and remains reversible.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-003-01 | Metadata contains `inboxes`, `visit_metadata`, and `webhook_events` | Unit | implemented | Shared ORM metadata exposes the required tables. |
| QA-003-02 | `webhook_events.payload_raw` uses byte-safe binary storage | Unit | implemented | ORM type remains binary-safe. |
| QA-003-03 | Required indexes exist on inbox expiry and event listing paths | Unit | implemented | ORM index definitions match documented query paths. |
| QA-003-04 | `alembic upgrade head` creates the initial schema | Migration | implemented | The database contains the required tables and indexes. |
| QA-003-05 | `alembic downgrade base` rolls the schema back cleanly | Migration | implemented | Managed tables are removed without leaving partial state. |
| QA-003-06 | Applying downgrade then re-upgrade works cleanly | Migration | ready | Migration chain remains reversible across repeated runs. |

## Suite QA-004 Callback Provisioning And URL Lifecycle

Purpose: verify first-visit inbox provisioning and 24-hour callback rotation behavior.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-004-01 | First visit provisions a lowercase UUIDv4 `clsid` | API/E2E | implemented | Response returns valid `clsid`, `callback_url`, `viewer_url`, `expires_at`, and `new_session=true`. |
| QA-004-02 | Repeat visit within TTL returns the same callback URL | API/E2E | implemented | Existing unexpired callback remains stable and `new_session=false`. |
| QA-004-03 | Expired callback rotates to a new `clsid` | API/E2E | implemented | A new callback is issued after expiration. |
| QA-004-04 | Cookie-first session continuity works when source IP changes | API/E2E | blocked | Valid session cookie preserves the same callback unless abuse policy rotates it. |
| QA-004-05 | Session cookie is issued with `HttpOnly` and `SameSite=Lax` semantics | Unit/API | implemented | Response issues the configured session cookie with safe defaults. |

## Suite QA-005 Hook Ingestion And Payload Acceptance

Purpose: verify provider-agnostic capture behavior and fast acknowledgement semantics.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-005-01 | Valid JSON webhook is accepted with fast `200` response | API | blocked | Endpoint acknowledges quickly and returns the accepted shape. |
| QA-005-02 | Plain text payload is accepted | API | blocked | Non-JSON text payload is stored without schema assumptions. |
| QA-005-03 | Form-encoded payload is accepted | API | blocked | Request is accepted and stored in byte-safe form. |
| QA-005-04 | Binary payload is accepted and stored safely | API | blocked | Binary payload does not break parsing or storage. |
| QA-005-05 | Unknown or expired `clsid` returns a safe `404` error envelope | API | blocked | Response contains safe error details and request correlation. |
| QA-005-06 | Oversized payload returns `413` with safe error response | API | blocked | Payload size limits are enforced with documented failure semantics. |
| QA-005-07 | Burst traffic keeps the ack path responsive | API/Load | blocked | Ack latency remains within the configured target under concurrent posts. |

## Suite QA-006 Inbox Viewer, Search, And Pagination

Purpose: verify viewer data contracts and operator-facing browsing behavior.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-006-01 | `GET /inbox/{clsid}` returns request summaries and selected event | API | blocked | Response matches the documented viewer contract. |
| QA-006-02 | Newest event is selected by default when `selected_event_id` is omitted | API/E2E | blocked | Viewer uses deterministic default selection. |
| QA-006-03 | Search filters by request id, method, source IP, and payload preview | API/E2E | blocked | Results honor the documented query behavior. |
| QA-006-04 | Pagination enforces default and maximum page sizes | API | blocked | Out-of-range limits return safe client errors. |
| QA-006-05 | Stable sort order is preserved across pages | API | blocked | Results remain ordered by `received_at DESC, event_id DESC`. |
| QA-006-06 | Viewer-facing network identifiers are redacted by default | API/E2E | blocked | Public bearer-link view does not expose raw network identifiers. |

## Suite QA-007 Payload Rendering And Safe Inspection

Purpose: verify safe rendering behavior for structured, text, and binary payloads.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-007-01 | Structured payload renders as YAML | API/E2E | blocked | Viewer shows deterministic YAML output. |
| QA-007-02 | Text payload renders as text preview | API/E2E | blocked | Viewer shows readable text when YAML conversion is not appropriate. |
| QA-007-03 | Binary payload shows metadata-only preview | API/E2E | blocked | Viewer avoids unsafe binary rendering. |
| QA-007-04 | Unsafe HTML or script content is escaped | E2E | blocked | Viewer never executes payload content. |
| QA-007-05 | Large payload remains viewable without UI breakage | E2E/Manual | blocked | UI stays responsive and readable for large payloads. |

## Suite QA-008 Callback Authentication And Replay Safety

Purpose: verify provider-agnostic callback authentication strategies and failure handling.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-008-01 | `shared_token` mode accepts valid bearer token | API | blocked | Valid token allows normal ingest flow. |
| QA-008-02 | Missing bearer token returns `401` | API | blocked | Safe error envelope is returned without leaking secret material. |
| QA-008-03 | Policy mismatch returns `403` | API | blocked | Response matches the documented forbidden behavior. |
| QA-008-04 | Valid signature headers pass verification | API | blocked | Signed request is accepted using the canonical signing format. |
| QA-008-05 | Malformed signature headers return `422` | API | blocked | Safe validation failure response is returned. |
| QA-008-06 | Timestamp outside skew window is rejected | API | blocked | Replay-safety clock window is enforced. |
| QA-008-07 | Replayed signature is rejected within the replay window | API | blocked | Replay protection prevents duplicate signed acceptance. |

## Suite QA-009 Privacy, Metadata, And Consent

Purpose: verify metadata collection boundaries and privacy-visible behavior.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-009-01 | Visit metadata captures only approved fields | API/Manual | blocked | Stored metadata matches the documented allowlist and categories. |
| QA-009-02 | Sensitive headers are not stored or exposed | API/Manual | blocked | Raw secrets do not appear in persistence, logs, or public responses. |
| QA-009-03 | GPS data is collected only after explicit consent | E2E/Manual | blocked | No GPS values are stored without opt-in. |
| QA-009-04 | Privacy notice is visible before or at collection time | E2E/Manual | blocked | Operator-visible privacy notice appears as required. |
| QA-009-05 | Public viewer redacts source IP details by default | API/E2E | blocked | Network identifiers remain masked in bearer-link views. |

## Suite QA-010 Abuse Controls, Deduplication, And Retention

Purpose: verify resilience controls, retry-safe ingest, and cleanup behavior.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-010-01 | Public endpoints enforce documented rate limits | API/Load | blocked | Excess traffic returns a safe `429` with retry hints. |
| QA-010-02 | Retryable failures include `Retry-After` and retry details | API | blocked | `429` and `503` responses include documented retry data. |
| QA-010-03 | Deterministic deduplication marks duplicate deliveries safely | API/Unit | blocked | Duplicate events do not overwrite canonical first-capture data. |
| QA-010-04 | Daily cleanup removes expired inboxes and stale events idempotently | Integration | blocked | Cleanup can be rerun without corrupting data. |
| QA-010-05 | Concurrent hook delivery does not corrupt event records | API/Concurrency | blocked | Persistence remains consistent under simultaneous posts. |

## Suite QA-011 Frontend Inbox Experience And Responsive Layout

Purpose: verify the operator-facing UI matches the documented layout and interactions.

| Case ID | Test case | Type | Status | Expected result |
| --- | --- | --- | --- | --- |
| QA-011-01 | Header shows menu entry point and recognizable branding | E2E/Manual | blocked | Header matches the UI mock structure. |
| QA-011-02 | Callback URL control copies the URL to clipboard | E2E | blocked | Primary click action copies the current hook URL. |
| QA-011-03 | Desktop layout uses narrow list and wide payload panel | E2E/Visual | blocked | Layout approximates the documented 30/70 split at desktop widths. |
| QA-011-04 | Mobile layout stacks list before payload panel | E2E/Visual | blocked | Small-device flow preserves request selection behavior. |
| QA-011-05 | Clicking a request updates the selected payload panel | E2E | blocked | Selected payload changes without unsafe rendering. |
| QA-011-06 | Empty, loading, and error states remain user-readable | E2E/Manual | ready | UI surfaces safe operator-friendly states when data is absent or failing. |

## 6. Minimum Regression Packs

Use these packs to scope verification work:

| Pack | When to run | Minimum suites |
| --- | --- | --- |
| `smoke` | Every backend or docs-affecting change | QA-001, QA-002, QA-003 |
| `api-contract` | Any API route, schema, auth, or error-envelope change | QA-001, QA-005, QA-006, QA-008, QA-010 |
| `viewer-ui` | Any inbox, payload rendering, search, or layout change | QA-006, QA-007, QA-009, QA-011 |
| `release` | Pre-release or milestone verification | All suites |

## 7. Current Automation Mapping

Current automated coverage in the repository maps to these suites:

| Existing test file | Covered suites |
| --- | --- |
| `backend/tests/test_app.py` | QA-001 |
| `backend/tests/test_config.py` | QA-002 |
| `backend/tests/test_inbox_service.py` | QA-004 |
| `backend/tests/test_bootstrap_api.py` | QA-004 |
| `backend/tests/test_persistence_models.py` | QA-003 |
| `backend/tests/test_migrations.py` | QA-003 |

## 8. Verification Commands

Backend regression:

```powershell
cd backend
pytest
```

Focused migration regression:

```powershell
cd backend
pytest tests/test_persistence_models.py tests/test_migrations.py
```

Frontend checks:

```powershell
cd frontend
npm run lint
npm run test
```

End-to-end checks:

```powershell
npx playwright test
```

## 9. Maintenance Rules

When a change introduces or modifies behavior:

1. update the affected suite entries in this guide
2. add or update automated coverage where the behavior is implemented
3. keep `docs/api.md` aligned for API changes
4. keep `docs/ui-mock.md` aligned for user-visible workflow or layout changes
5. add missing negative cases for malformed input, oversized payloads, auth failures, and concurrency when applicable

## 10. Recommended Next Additions

1. Add Playwright specs for callback provisioning and inbox browsing once the frontend exists.
2. Add API tests for `GET /`, `POST /hook/{clsid}`, and `GET /inbox/{clsid}` as those routes are implemented.
3. Add dedicated load and concurrency checks for burst webhook ingestion before production release.
