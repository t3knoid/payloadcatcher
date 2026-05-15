---
name: Implement Ticket
description: "Implement a PayloadCatcher ticket with a root-cause fix, focused tests, verification, pattern reuse, and documentation review."
argument-hint: "Paste the ticket, acceptance criteria, issue text, or subsystem"
agent: "agent"
---
# PayloadCatcher - Unified Ticket Implementation Prompt

Implement the provided ticket in the PayloadCatcher repository.

Use the user argument as the source of truth for the requested behavior, acceptance criteria, or problem scope.

This prompt includes documentation-audit and documentation-update requirements as part of implementation. Treat documentation review as a required deliverable whenever behavior, API contracts, operations, or UI expectations change.

-------------------------------------------------------------------------------
## Mandatory instruction sources
-------------------------------------------------------------------------------

Read and apply all of the following before any analysis, planning, code edits, or test changes:

- `.github/copilot-instructions.md`
- `docs/api.md`
- `docs/requirements.md`
- `docs/route-contract.md`
- `docs/ui-mock.md`
- `docs/development.md`
- `.github/prompts/code-review.prompt.md`
- `.github/prompts/scaffold-ticket.prompt.md`

Treat these repository documents as the single source of truth.
Do not restate or loosen them.
If one of them is missing, say so explicitly.

-------------------------------------------------------------------------------
## Pattern Discovery and DRY Enforcement (Mandatory)
-------------------------------------------------------------------------------

Before writing any code, you must perform a repository-wide pattern discovery step.

### 1. Search for existing patterns
Identify and inspect the closest existing implementation that solves a similar problem, including:

- API routers, request and response models, and error envelopes
- service-layer logic for validation, routing, retention, deduplication, and replay behavior
- infrastructure wrappers for storage, queues, external I/O, and background work
- SQLAlchemy models, Alembic migration patterns, and indexed query paths
- Vue components, layouts, centralized API client usage, and mobile-responsive UI patterns
- request listing, pagination, search, selection, and payload rendering flows
- logging, metrics, correlation ID, auth verification, and rate-limit patterns
- test patterns for API, services, concurrency, malformed input, oversized payloads, and migrations

### 2. Enforce DRY
You must avoid DRY violations:

- do not duplicate logic, schemas, components, services, or error contracts
- do not introduce new abstractions if an equivalent one already exists
- do not create new provider-specific logic when a provider-agnostic path is required
- if you introduce a new pattern, justify why reuse is not possible

### 3. Reuse existing contracts and patterns
You must reuse:

- existing API contracts and error envelope patterns
- existing Pydantic schemas and validation boundaries
- existing service ownership and router thinness
- existing infrastructure wrappers and async handoff patterns
- existing Vue UI patterns, layout behavior, and API client usage
- existing test structure and fixtures

Match the closest existing implementation in:

- structure
- naming
- validation
- error handling
- observability
- async safety
- UI behavior
- testing style

If the ticket requires a new variant, explain why the existing one cannot be reused.

-------------------------------------------------------------------------------
## Scope routing
-------------------------------------------------------------------------------

Apply repository rules by file and behavior scope:

- `.github/copilot-instructions.md`: always-on rules for architecture boundaries, provider-agnostic webhook behavior, security, privacy, observability, retention, migration fidelity, and testing
- `docs/requirements.md`: product behavior, canonical URLs, metadata/privacy rules, UI expectations, error semantics, retention, and future auth constraints
- `docs/route-contract.md`: API shapes, response fields, status codes, schema expectations, signature verification rules, pagination, and byte-safe storage contracts
- `docs/ui-mock.md`: desktop and mobile layout, request selection behavior, payload display, and callback URL interaction expectations
- `docs/development.md`: local setup, verification workflow, debugging expectations, and developer-facing operational guidance
- `.github/prompts/code-review.prompt.md`: review priorities to preserve during implementation, especially defects, regressions, security, and test completeness

When a changed file falls under multiple instruction sources, apply all relevant rules together.

-------------------------------------------------------------------------------
## Implementation goals
-------------------------------------------------------------------------------

Your job is to:

- restate the ticket clearly before coding
- investigate the current implementation and identify the root cause or missing behavior
- perform pattern discovery and reuse existing patterns and contracts
- implement the smallest complete change that satisfies the request
- keep the solution aligned with PayloadCatcher architecture and safety rules
- add or update automated tests for the changed behavior
- verify the change with the relevant checks before declaring success
- inspect affected files and behavior to identify required documentation updates
- implement the necessary documentation changes in the relevant documents

If the ticket affects an API implementation or API behavior, `docs/api.md` must be updated in the same change.

If the ticket conflicts with repository instructions, do not implement the conflicting behavior.
Explain the conflict and propose a compliant alternative.

-------------------------------------------------------------------------------
## PayloadCatcher-specific invariants
-------------------------------------------------------------------------------

These rules must remain true unless the ticket explicitly changes the specification and the documentation is updated accordingly:

- canonical public patterns remain `https://payloadcat.ch/hook/{clsid}` and `https://payloadcat.ch/inbox/{clsid}`
- `clsid` values are lowercase high-entropy UUIDv4 strings
- callback URLs remain valid for 24 hours and rotate after expiration
- hook endpoints acknowledge quickly with HTTP 200 and defer heavy work asynchronously
- ingestion remains provider-agnostic and accepts JSON and non-JSON payloads
- raw payload storage remains byte-safe and must not assume JSON-only persistence
- public viewer responses redact network identifiers by default
- metadata collection remains explicit, sanitized, and GPS-gated by consent
- rate limiting and payload size limits remain enabled by default on public endpoints
- callback auth modes remain explicit and provider-agnostic: `none`, `shared_token`, and `signature`
- signature verification uses deterministic rules, constant-time comparison, bounded skew, and replay protection
- future user-account extensibility must not break anonymous capture flows

-------------------------------------------------------------------------------
## Documentation sync requirements
-------------------------------------------------------------------------------

Review the current workspace changes and identify every documentation update required for PayloadCatcher.

Primary task:

- inspect the changed code, affected files, and related API or UI behavior
- determine which documents must be updated so docs remain accurate for developers, operators, reviewers, and QA

Focus areas:

- user-facing behavior
- developer-facing setup or run behavior
- architectural behavior or trust-boundary changes
- request and response contracts
- validation rules and error messages
- privacy warnings and metadata collection behavior
- callback auth, signature verification, replay protection, and retry semantics
- retention, cleanup, and operational controls
- new or changed UI states, filters, buttons, mobile behavior, loading states, empty states, and error states

Check for required updates in places such as:

- `README.md`
- `docs/api.md`
- files under `docs/`
- route or schema reference sections
- setup and deployment guidance
- UI mockups or interaction notes
- prompt files when implementation workflow expectations change

For each required update:

1. Show the exact diff lines, changed behavior, or concrete evidence that triggered the documentation need.
2. Name the document that must be updated and explain why.
3. Propose the minimal documentation change in 1 to 3 sentences.
4. If the change introduces a new UI state or workflow, propose a QA test case.
5. Implement the change in the relevant document.

Documentation constraints:

- be evidence-based and avoid speculative documentation work
- keep edits small, targeted, and contributor-friendly
- prefer current-behavior documentation over historical wording
- if no documentation update is needed for an area, say so briefly

-------------------------------------------------------------------------------
## Required workflow
-------------------------------------------------------------------------------

1. Summarize the ticket and list assumptions.
2. Identify which instruction sources apply to the touched files.
3. Perform pattern discovery and list the existing patterns and contracts you will reuse.
4. Read the relevant code, tests, and docs.
5. If schema changes are required, inspect current SQLAlchemy models and Alembic history before editing.
6. Identify the root cause with evidence.
7. Describe instruction compliance before coding, including trust boundaries, async safety, service ownership, safe error handling, privacy handling, and migration fidelity when applicable.
8. Add or update focused tests first when practical.
9. Implement the minimal root-cause fix using the identified existing patterns.
10. Audit the changed behavior for required documentation, QA, and UI use-case updates using concrete evidence.
11. Implement the minimal required documentation updates in the relevant documents, including `docs/api.md` for any API implementation or modification.
12. Run the relevant verification steps.
13. Report what changed and whether the ticket now appears complete.
14. State whether documentation is aligned or which documents and comments needed updates and why.

If the request is unclear or under-specified, ask a small number of focused questions instead of guessing.

-------------------------------------------------------------------------------
## Output format
-------------------------------------------------------------------------------

## Ticket Understanding
Short summary of the requested behavior.

## Instruction Compliance
Explain how the planned change respects repository instructions, including trust boundaries, async safety, service ownership, safe error handling, privacy rules, and migration workflow where applicable.

## Pattern Reuse Plan
List the existing patterns, contracts, and abstractions being reused.

## Root Cause
What is broken, missing, or risky.

## Implementation
Bullet list of the changes made.

## Tests and Verification
List the tests or checks run and the outcomes. Do not claim success without fresh verification evidence.

#### Required Documentation Updates
- Group by document or feature area.

#### Suggested Additions to QA Testing Guide
- Include manual verification scenarios when relevant.

#### Suggested Additions to UI Use Cases
- Include any new operator or viewer workflows, states, or privacy-visible behavior.

#### Confidence (High / Medium / Low)
- Give a short reason for the confidence level.

## Notes
Any remaining risks, follow-ups, assumptions, instruction conflicts, or documentation updates still needed.