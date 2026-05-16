---
name: Fix Review Findings
description: "Resolve issues identified in a recent PayloadCatcher review with root-cause fixes, focused validation, and required documentation sync."
argument-hint: "Paste the review findings, PR comments, issue list, or review summary to address"
agent: agent
---

# PayloadCatcher Review Findings Resolution Prompt

Use this prompt to fix issues identified during a recent review of PayloadCatcher.

Use the user argument as the source of truth for the findings to address. Treat each finding as a concrete defect, regression risk, or test/documentation gap unless the user explicitly marks it as non-actionable.

-------------------------------------------------------------------------------
## Mandatory instruction sources
-------------------------------------------------------------------------------

Read and apply all of the following before any analysis, planning, code edits, or test changes:

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

Treat these repository documents as the single source of truth.
Do not restate or loosen them.
If one of them is missing, say so explicitly.

-------------------------------------------------------------------------------
## Review-fix goals
-------------------------------------------------------------------------------

Your job is to:

- restate the review findings you are going to fix
- confirm which findings are reproducible, already fixed, or blocked
- identify the root cause for each actionable finding
- implement the smallest complete fix that resolves the actual defect
- preserve PayloadCatcher architecture boundaries and provider-agnostic behavior
- add or update focused tests for each fixed issue when practical
- re-run the narrowest checks that prove the finding is resolved
- update documentation when the fix changes API behavior, setup, operations, or UI expectations
- update `docs/config.md` when the fix changes configuration keys, defaults, expected types, or runtime/deployment config behavior
- update `docs/qa-test-guide.md` when the fix changes user-facing behavior or UI states
- update the e2e tests when the fix changes user-facing behavior or UI states
- provide a concise summary of the change suitable for use as a commit message

If a reported finding is incorrect, outdated, or no longer reproducible, say so with concrete evidence rather than silently skipping it.

-------------------------------------------------------------------------------
## Pattern Discovery and DRY Enforcement (Mandatory)
-------------------------------------------------------------------------------

Before writing code, perform targeted pattern discovery around each finding.

Inspect the nearest existing implementation for:

- routers, response models, and error envelopes
- service-layer validation and business logic
- infrastructure wrappers and async handoff patterns
- SQLAlchemy and Alembic conventions
- logging, request correlation, and auth verification patterns
- Vue UI behavior and centralized API client usage
- existing tests that cover adjacent behavior

You must:

- reuse existing contracts and patterns where possible
- avoid duplicate fixes or one-off abstractions
- justify any new pattern introduced to fix a finding

-------------------------------------------------------------------------------
## PayloadCatcher-specific invariants
-------------------------------------------------------------------------------

Unless the reviewed change explicitly alters the specification and the docs are updated accordingly, these rules remain true:

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
- any API implementation or API modification must update `docs/api.md`
- any configuration addition, removal, rename, default change, expected-type change, or runtime config behavior change must update `docs/config.md`

-------------------------------------------------------------------------------
## Required workflow
-------------------------------------------------------------------------------

1. Summarize the findings and list any assumptions.
2. Identify which findings are actionable, already fixed, blocked, or invalid.
3. Identify which instruction sources apply to the touched files.
4. Perform pattern discovery near each finding and list the patterns you will reuse.
5. Read the relevant code, tests, and docs.
6. Reproduce or otherwise validate each finding with evidence when feasible.
7. Identify the root cause for each finding you will fix.
8. Describe instruction compliance before coding, including architecture boundaries, async safety, safe error handling, privacy rules, and migration fidelity when relevant.
9. Add or update focused tests first when practical.
10. Implement the minimal root-cause fixes.
11. Audit the changed behavior for required documentation updates, including `docs/api.md` for API-related fixes.
12. Run the relevant verification steps.
13. Report which findings are fixed, which remain open, and why.
14. End with a concise change summary that can be reused as a commit message. Present the commit message in imperative or past-tense style inside a code block.

If the user supplied multiple findings, address them in severity order unless there is a clear dependency that requires a different order.

If a finding cannot be fixed safely without more context, ask a small number of focused questions instead of guessing.

-------------------------------------------------------------------------------
## Documentation sync requirements
-------------------------------------------------------------------------------

Review the fixes for any required documentation updates.

Check for updates in places such as:

- `README.md`
- `docs/config.md`
- `docs/api.md`
- files under `docs/`
- setup and deployment guidance
- UI mocks or interaction notes
- prompt files if workflow expectations changed

For each required update:

1. Show the concrete evidence that triggered the documentation need.
2. Name the document that must change and explain why.
3. Make the minimal documentation edit needed to keep docs accurate.

Keep documentation edits present-tense, evidence-based, and narrowly scoped.

-------------------------------------------------------------------------------
## Output format
-------------------------------------------------------------------------------

## Findings Addressed
List the review findings you handled in this pass.

## Instruction Compliance
Explain how the fixes respect repository rules, including architecture boundaries, async safety, error handling, privacy, and documentation obligations.

## Pattern Reuse Plan
List the existing patterns, contracts, and abstractions reused for the fixes.

## Root Cause
Describe the actual cause of each actionable finding.

## Implementation
Bullet list of the fixes made.

## Tests and Verification
List the checks run and their outcomes. Do not claim a finding is fixed without fresh evidence.

#### Required Documentation Updates
- Group by document or feature area.

#### Remaining Findings or Blockers
- List any review findings not fixed in this pass and explain why.

#### Confidence (High / Medium / Low)
- Give a short reason for the confidence level.

## Notes
Include follow-ups, assumptions, invalidated findings, or residual risks.

## Commit Message Summary
Provide 1 concise sentence in imperative or past-tense style that summarizes the change set and can be used directly or adapted for a git commit message.