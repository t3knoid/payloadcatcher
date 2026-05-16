# PayloadCatcher Code Review Prompt

Use this prompt to run a focused review of a change set for PayloadCatcher.

description: "Perform a code review of changes in the current branch using PayloadCatcher repository instructions and Cursor .mdc rules, including required documentation updates."

## Context

- Feature summary: {{feature_summary}}
- Changed files: {{changed_files}}
- Related issue/ticket: {{ticket_reference}}
- Risk notes from author: {{author_risks}}

## Review Objectives

Perform a rigorous code review with findings ordered by severity.
Prioritize correctness, security, async safety, data integrity, and test completeness.

## Required Checks

1. Architecture boundaries
   - Routers are thin and only handle request parsing/auth/response mapping.
   - Business logic is in services, not API route handlers or frontend components.
2. Webhook ingestion behavior
   - Hook route remains provider-agnostic.
   - Hook returns HTTP 200 quickly and defers heavy work asynchronously.
   - Unknown JSON payload shapes are accepted and viewable.
3. Canonical URL and CLSID rules
   - Hook pattern is `https://payloadcat.ch/hook/{clsid}`.
   - Viewer pattern is `https://payloadcat.ch/inbox/{clsid}`.
   - `clsid` is lowercase UUIDv4 and high entropy.
   - Callback URL lifetime is 24 hours with rotation after expiration.
4. Metadata and privacy
   - Metadata capture is explicit and limited to intended fields.
   - Header capture is selective/sanitized, not a raw blanket dump.
   - GPS collection is gated behind explicit consent.
   - Privacy/legal warning coverage is present where user-facing behavior changes.
5. Security and abuse resistance
   - Input validation/sanitization for path/query/body/header-derived values.
   - Rate limiting and payload size limits are enforced on public endpoints.
   - No sensitive leaks in logs or error responses.
6. Persistence and lifecycle
   - Retention logic matches daily cleanup and 24-hour URL validity.
   - Storage and cleanup behavior is idempotent and concurrency-safe.
   - Schema/index choices support listing by inbox and time.
7. Configuration and operational controls
   - Defaults are configurable via `.env` and documented.
   - No hardcoded environment-specific constants.
8. Testing quality
   - Unit tests cover service logic and validation.
   - API tests cover ingestion, listing, retrieval, and negative cases.
   - Concurrency and malformed/oversized payload scenarios are addressed.
9. Future auth/account extensibility
   - Changes preserve a clean path to user accounts and authenticated access.
   - Auth logic is centralized in middleware/services, not duplicated in routes.
   - Callback authentication strategy remains pluggable (token/signature adapters).
   - No secrets are leaked through logs, errors, or serialized models.

## Output Format

1. Findings
   - Severity: Critical | High | Medium | Low
   - File and line reference
   - Why this is a risk
   - Minimal fix recommendation
2. Open questions or assumptions
3. Test gaps
4. Brief change summary (only after findings)

## Hard Rules for Reviewer Output

- If no issues are found, state: "No findings identified."
- Do not rewrite large sections unless required for a fix suggestion.
- Keep focus on defects, regressions, and missing tests over style-only comments.
