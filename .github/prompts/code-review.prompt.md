---
name: Code Review
description: "Perform a code review of local outgoing changes not yet synced to origin using PayloadCatcher repository instructions and repository prompt rules, including required documentation and test follow-up."
argument-hint: "Describe the feature, local outgoing change set, ticket, or risk areas to review"
agent: agent
---

# PayloadCatcher Code Review Prompt

Use this prompt to run a focused review of the local outgoing PayloadCatcher change set that has not yet been synced to `origin`.

Default review scope:

- local commits ahead of the tracked upstream branch, or `origin/main` when the upstream branch is `origin/main`
- local uncommitted tracked changes when they are part of the user-requested outgoing work

Do not default to reviewing historical merged work, `HEAD` in isolation, or generic repository state when there is no outgoing delta.
If there are no local outgoing changes, say so explicitly and stop after reporting that there is no change set to review.

## Context

- Feature summary: {{feature_summary}}
- Changed files: {{changed_files}}
- Related issue/ticket: {{ticket_reference}}
- Risk notes from author: {{author_risks}}

## Review Objectives

Perform a rigorous code review with findings ordered by severity.
Prioritize correctness, security, async safety, data integrity, and test completeness.
Treat documentation gaps and missing test follow-up as real findings when the outgoing change requires them.

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
   - Configuration additions, removals, renames, default changes, and expected-type changes update `docs/config.md`.
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
10. Documentation and follow-through
   - API, route-contract, setup, QA, UI mock, and config docs stay aligned with the outgoing implementation.
   - Review findings must call out any required documentation updates needed to keep repository docs accurate.
   - Review findings must call out any missing or inadequate tests needed to support the recommended fix.

## Output Format

1. Findings
   - Severity: Critical | High | Medium | Low
   - File and line reference
   - Why this is a risk
   - Minimal fix recommendation
   - Required documentation updates, if any
   - Required test updates, if any
2. Open questions or assumptions
3. Test gaps
4. Brief change summary (only after findings)

## Hard Rules for Reviewer Output

- If no issues are found, state: "No findings identified."
- If there are no local outgoing changes not yet synced to `origin`, state that explicitly and do not invent a review scope.
- Do not rewrite large sections unless required for a fix suggestion.
- Keep focus on defects, regressions, and missing tests over style-only comments.
- When a finding implies documentation or test follow-up, name the affected document or test surface directly instead of leaving the recommendation implicit.
