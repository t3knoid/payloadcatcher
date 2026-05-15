---
name: Commit Message
description: "Summarize the current PayloadCatcher change set as a concise commit message."
argument-hint: "Optionally describe the intended emphasis, subsystem, or commit style"
agent: agent
---

# PayloadCatcher Commit Message Prompt

Use this prompt to summarize the current workspace changes as a concise commit message for PayloadCatcher.

Use the current workspace diff as the primary source of truth.
Use the user argument only to refine emphasis, scope, or style when provided.

## Required workflow

1. Inspect the current workspace changes before writing anything.
2. Identify the main change theme, affected subsystem, and most important user- or developer-visible outcome.
3. Prefer the smallest accurate summary over a broad changelog.
4. Mention documentation or configuration changes only if they are core to the change.
5. Do not include unrelated details, implementation trivia, or speculative scope.

## Output rules

- Return one concise commit message line.
- Prefer imperative mood.
- Keep it short enough to use directly as a commit subject.
- Do not include bullets, labels, quotes, or explanation.
- Do not include a body unless the user explicitly asks for one.
- If the workspace has no meaningful changes, return: `No commit message: no meaningful changes detected`

## Style guidance

- Good: `Scaffold FastAPI backend and local dev stack`
- Good: `Fix config parsing and safe backend error handling`
- Good: `Add API docs sync and Swagger requirements`
- Avoid: overly long summaries, file lists, or mixed unrelated changes in one message.