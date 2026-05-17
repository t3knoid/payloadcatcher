---
name: Scaffold Ticket
description: "Generate a scoped, implementation-ready PayloadCatcher GitHub issue from a feature request, issue summary, or subsystem change."
argument-hint: "Paste the feature request, acceptance criteria, issue text, or subsystem to turn into a build-ready ticket"
agent: agent
---

# PayloadCatcher Ticket Scaffolding Prompt

Use this prompt to generate one scoped implementation ticket for PayloadCatcher.

Use the user argument as the source of truth for the requested behavior, acceptance criteria, subsystem, or engineering need.

Treat the following repository documents as the source of truth when shaping the ticket:

- `.github/copilot-instructions.md`
- `docs/config.md`
- `docs/api.md`
- `docs/requirements.md`
- `docs/route-contract.md`
- `docs/ui-mock.md`
- `docs/development.md`
- `.github/prompts/code-review.prompt.md`
- `.github/prompts/documentation-sync.prompt.md`
- `.github/prompts/implement-ticket.prompt.md`

If one of these sources is missing, say so explicitly.

## Goal

Draft one implementation issue that is specific, testable, documentation-aware, and ready for engineering work.

Create the GitHub issue in the current repository by using the `gh` CLI tool after drafting the issue content.

The issue must preserve strict architecture boundaries and provider-agnostic webhook behavior.

## GitHub Issue Creation Requirements

- Before creating a new issue, search for an existing open GitHub issue with the same or materially similar title using the `gh` CLI.
- Prefer a non-interactive duplicate check such as `gh issue list --search <title>` or an equivalent `gh` search command scoped to the current repository.
- If a matching open issue already exists, report that issue to the user and do not create a duplicate unless the user explicitly asks for a separate issue.
- After drafting the issue title and body, create the issue in the current repository with a non-interactive `gh issue create` command.
- Use the `gh` CLI through the terminal tool; do not stop after only drafting the issue text when issue creation is possible.
- Prefer a non-interactive form such as `gh issue create --title <title> --body-file <file>` or an equivalent safe non-interactive variant.
- If `gh` is unavailable, the user is not authenticated, or issue creation fails for an environment reason you cannot resolve safely, say so explicitly and return the ready-to-submit issue title and body.
- After successful creation, include the created issue number and URL in the final response.

## Issue shaping rules

- Keep routers thin and business logic in services.
- Preserve provider-agnostic ingestion for JSON and non-JSON payloads.
- Preserve byte-safe raw payload storage requirements.
- Keep canonical public patterns aligned to `https://payloadcat.ch/hook/{clsid}` and `https://payloadcat.ch/inbox/{clsid}` unless the request explicitly changes the spec.
- Preserve 24-hour callback lifecycle expectations unless the request explicitly changes them.
- Keep privacy, consent, and redaction requirements explicit when the change affects metadata or viewer behavior.
- Keep future user-account and authenticated-callback extensibility intact.
- Require documentation updates whenever behavior, API shape, configuration, operations, or UI expectations change.
- Require `docs/api.md` updates whenever API implementation or API behavior changes.
- Require `docs/config.md` updates whenever configuration keys, default values, expected value types, or operational configuration behavior change.
- Avoid vendor-specific assumptions, names, or lock-in.

## Required sections to produce

### 1. Summary
One short paragraph describing the feature, problem, and expected outcome.

### 2. Scope
- In scope
- Out of scope

### 3. Functional Requirements
Include the relevant requirements from the repository docs, tailored to the request. Cover the applicable areas below.

1. Canonical URL and identity rules
   - Hook URL pattern: `https://payloadcat.ch/hook/{clsid}`
   - Viewer URL pattern: `https://payloadcat.ch/inbox/{clsid}`
   - `clsid` is lowercase UUIDv4
   - Callback URL lifetime is 24 hours with rotation after expiration
2. Ingestion behavior
   - Hook acknowledges quickly with HTTP 200
   - Heavy work is deferred asynchronously
   - Unknown payload shapes remain accepted and viewable
   - Raw payload persistence remains byte-safe
3. Viewer behavior
   - Public viewer remains bearer-link by possession of URL
   - Request listing, selection, pagination, search, and payload rendering stay deterministic
   - Viewer-facing network identifiers stay redacted by default
4. Metadata and privacy
   - Capture only approved metadata fields
   - Sanitize headers and avoid sensitive values
   - GPS requires explicit opt-in consent
   - Privacy/legal wording is updated when collection or exposure changes
5. Security and abuse controls
   - Rate limiting and payload size limits apply to public endpoints
   - Error envelopes remain safe and consistent
   - Signature or token validation stays provider-agnostic when relevant
6. Retention and lifecycle
   - Daily cleanup of expired inboxes and events
   - Retry-safe and concurrency-safe retention behavior
7. Future auth and account compatibility
   - Preserve backward compatibility with anonymous inbox usage
   - Keep extension points for users, memberships, and API tokens
   - Keep optional authenticated callback modes (`none`, `shared_token`, `signature`) pluggable

### 4. Non-Functional Requirements
- Performance expectations
- Reliability and concurrency expectations
- Security expectations
- Observability, logging, and metrics expectations
- Accessibility or mobile behavior expectations when UI is affected

### 5. API Contract Changes
- Endpoints added or changed
- Request or response shape changes
- Error envelope or status code changes
- Pagination, retry, or auth behavior changes

### 6. Data Model and Migration Impact
- Tables, columns, or indexes affected
- Alembic migration requirements
- Reversibility notes
- Byte-safe storage implications
- Future compatibility notes for users, ownership, memberships, or tokens if relevant

### 7. Configuration Changes
- New or updated `.env` keys
- Default values
- Expected value types
- Operational notes and rollout considerations

### 8. Acceptance Criteria
Provide a numbered list of verifiable criteria written as observable outcomes.

### 9. Test Plan
At minimum include the applicable items below:

- Unit tests for services and validation
- API tests for happy path and negative cases
- Concurrency or load-adjacent tests when endpoint behavior changes
- Migration tests when schema changes occur
- Frontend or Playwright coverage when UI behavior changes
- Privacy, auth, rate-limit, malformed payload, or oversized payload tests when relevant

### 10. Documentation Impact
- Documents that must be updated
- Why each document needs an update
- Minimal doc changes required
- QA test additions if UI or workflow behavior changes

If the ticket changes API implementation or API behavior, this section must explicitly include `docs/api.md`.
If the ticket changes configuration shape or behavior, this section must explicitly include `docs/config.md`.

### 11. Risks and Mitigations
- Top technical risks
- Mitigation plan for each

### 12. Rollout and Verification
- Rollout steps
- Post-deploy checks
- Suggested verification commands, as applicable:
  - `pytest`
  - `alembic upgrade head`
  - frontend lint or test commands

### 13. Open Questions
Call out unknowns explicitly when the request is underspecified.

## Output constraints

- Keep the ticket concise but implementation-ready.
- Use present tense.
- Prefer small, reviewable slices over multi-system rewrites.
- Be explicit about documentation work when behavior changes.
- Do not invent provider-specific behavior unless the request explicitly requires it.
- When issue creation succeeds, report the final GitHub issue number and URL after the issue content summary.
