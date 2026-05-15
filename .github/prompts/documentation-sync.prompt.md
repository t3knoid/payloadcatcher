---
name: Documentation Sync
description: Audit code changes and identify the exact documentation, QA, and UI use-case updates required for PayloadCatcher.
argument-hint: Describe the feature, branch, PR, or diff to audit for documentation updates
agent: agent
---

# PayloadCatcher Documentation Sync Prompt

Review the current workspace changes and identify every documentation update required for PayloadCatcher.

Mandatory instruction sources:
- `.github/copilot-instructions.md`
- `docs/api.md`
- `docs/requirements.md`
- `docs/route-contract.md`
- `docs/ui-mock.md`
- `docs/development.md`
- `.github/prompts/code-review.prompt.md`
- `.github/prompts/implement-ticket.prompt.md`

If any required source is missing, say so explicitly.
Treat the existing repository documents as the source of truth.

Primary task:
- Inspect the current code changes, affected files, and any related UI or API behavior.
- Determine which documentation must be updated so the docs stay accurate for developers, operators, reviewers, and QA.

Focus areas:
- User-facing behavior
- Developer-facing behavior
- Architectural behavior
- Validation rules and error messages
- Canonical callback and viewer URL behavior
- Callback lifecycle, expiration, and rotation behavior
- Webhook ingestion semantics, async acknowledgement, and byte-safe payload handling
- Metadata collection, privacy warnings, consent gating, and redaction behavior
- Callback authentication, signature verification, replay protection, and retry semantics
- Pagination, search, filtering, and payload rendering behavior
- New or changed buttons, menus, search controls, navigation paths, loading states, empty states, mobile states, and error states
- Setup, configuration, deployment, or operational guidance

Check for required updates in places such as:
- [README.md](../../README.md)
- relevant files under the `docs` tree
- [docs/api.md](../../docs/api.md)
- API contract sections
- schema or migration notes
- setup and deployment instructions
- development and debugging guidance
- PayloadCatcher UI mockups or interaction notes
- prompt files when implementation workflow expectations change

For each required update:
1. Show the exact diff lines, changed behavior, or concrete evidence that triggered the documentation need.
2. Name the document that must be updated and explain why.
3. Propose the minimal documentation change in 1 to 3 sentences.
4. If the change introduces a new UI state or workflow, propose a QA test case.
5. Implement the change in the relevant document.
6. When updating UI-facing documentation, QA guides, or use-case text for frontend behavior, describe the current interface directly.
7. Prefer present-tense expectations for controls, dialogs, navigation, loading states, mobile layout, and accessibility behavior.
8. Avoid framing docs as migrations from an older interface with wording such as `now`, `no longer`, `instead of`, or `rather than` unless the comparison is required for operator safety or release notes.

PayloadCatcher-specific constraints:
- Be evidence-based. Do not suggest speculative documentation work.
- Preserve provider-agnostic webhook terminology and avoid vendor-specific assumptions.
- Any API implementation or API modification must update `docs/api.md` in the same change.
- Keep canonical URL references aligned with `https://payloadcat.ch/hook/{clsid}` and `https://payloadcat.ch/inbox/{clsid}` unless the audited change explicitly updates the specification.
- Keep privacy and security wording aligned with the documented redaction, consent, retry, and auth rules.
- Prefer small targeted edits over broad rewrites.
- Keep recommendations modular, concise, contributor-friendly, and onboarding-first.
- Keep formatting print-ready and easy to scan.
- If no update is needed for an area, say so briefly.

Return findings in exactly this structure:

#### Required Documentation Updates
- Group by document or feature area.

#### Suggested Additions to QA Testing Guide
- Include manual verification scenarios when relevant.

#### Suggested Additions to UI Use Cases
- Include any new viewer, operator, privacy-visible, or mobile-specific workflows and states.

#### Confidence (High / Medium / Low)
- Give a short reason for the confidence level.