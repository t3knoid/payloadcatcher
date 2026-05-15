# PayloadCatcher Implementation Ticket Prompt

Use this prompt to generate a scoped implementation ticket for PayloadCatcher.

## Inputs

- Feature title: {{feature_title}}
- Problem statement: {{problem_statement}}
- User impact: {{user_impact}}
- Requested timeline: {{timeline}}
- Dependencies: {{dependencies}}

## Instructions

Draft one implementation ticket that is specific, testable, and ready for engineering.
Keep architecture boundaries strict and preserve provider-agnostic webhook behavior.

## Ticket Template to Produce

### 1. Summary
One short paragraph describing the feature and expected outcome.

### 2. Scope
- In scope items
- Out of scope items

### 3. Functional Requirements
Include explicit requirements relevant to this change, as applicable:

1. URL and identity rules
   - Hook URL: `https://payloadcat.ch/hook/{clsid}`
   - Viewer URL: `https://payloadcat.ch/inbox/{clsid}`
   - `clsid` is lowercase UUIDv4
   - Callback URL persists for 24 hours, then rotates
2. Ingestion behavior
   - Return HTTP 200 quickly from hook endpoints
   - Persist/process asynchronously when work is heavy
3. Metadata and privacy
   - Capture only approved metadata fields
   - GPS requires explicit opt-in consent
   - Include legal/privacy warning updates if data collection scope changes
4. Abuse controls
   - Rate limiting and payload size limits on public endpoints
5. Retention behavior
   - Daily cleanup of expired inboxes/events
6. Future auth/account compatibility
   - Preserve backward compatibility with anonymous inbox usage
   - Define extension points for user accounts and role-based access
   - Define optional authenticated callback modes (token/signature)

### 4. Non-Functional Requirements
- Performance expectations
- Reliability/concurrency expectations
- Security expectations
- Observability/logging/metrics expectations

### 5. API Contract Changes
- Endpoints added/changed
- Request/response shape changes
- Error envelope/status code changes

### 6. Data Model and Migration Impact
- Tables/columns/indexes affected
- Alembic migration requirements
- Reversibility notes
- Future compatibility notes for users/ownership/tokens (if not implemented in this ticket)

### 7. Configuration Changes
- New or updated `.env` keys
- Default values
- Operational notes

### 8. Acceptance Criteria
Provide a numbered list of verifiable criteria written as observable outcomes.

### 9. Test Plan
At minimum include:

- Unit tests (services and validation)
- API tests (happy path + negative cases)
- Concurrency or load-adjacent tests if endpoint behavior changes
- Migration tests if schema changes occur

### 10. Risks and Mitigations
- Top technical risks
- Mitigation plan for each

### 11. Rollout and Verification
- Rollout steps
- Post-deploy checks
- Suggested verification commands:
  - `pytest`
  - `alembic upgrade head`

## Output Constraints

- Keep the ticket concise but implementation-ready.
- Use present tense.
- Avoid provider-specific assumptions or lock-in.
- Call out unknowns explicitly under "Open Questions" when needed.
