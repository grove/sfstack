---
name: sf-maintain-review
description: "Bring an open review to a current, actionable state by resolving verified findings and check failures. Use when feedback, base changes, or continuous-integration results arrive."
---

# Maintain review

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the review package and any current verification or review reports. Resolve the live review identity, head, base, required checks, and unresolved discussions. Establish ownership of the source branch and a budget of at most three repair cycles unless a narrower limit was supplied.

## Procedure

1. Read the current remote state before acting. Collect unresolved findings across the entire review, including older comments that still apply. Distinguish formal change requests, advisory suggestions, informational messages, and automated check failures. Do not equate silence with approval.
2. Verify each actionable claim against the current candidate and specification. Record accepted, already resolved, rejected with evidence, deferred by authorized decision, or awaiting clarification. Preserve the original concern and reasoning; do not mark a thread resolved solely because code changed nearby.
3. Diagnose failing checks from their actual logs. Separate candidate defects from infrastructure failures, missing credentials, timeouts, and unavailable environments. Retry a demonstrably transient failure only within the budget and preserve the initial failure evidence.
4. Apply the smallest authorized correction in an isolated work area. Preserve authorship and unrelated changes. When the base advances, inspect semantic overlap and compatibility before rebasing or merging it; a conflict-free operation does not establish correctness.
5. Re-run affected checks and required integration checks on the new candidate. Invalidate prior review or verification whose inputs changed. If the correction changes scope or intended behavior, surface that decision instead of silently expanding the submission.
6. Publish authorized branch updates with an observed-head precondition or equivalent concurrency control. Re-read the remote head before retrying a conflict. Post only useful, authorized review responses containing the outcome and evidence; do not issue unrelated notifications or request additional reviewers without authority.
7. Assess readiness on the latest head and base. Report outstanding findings, check status, policy gates, human decisions, and evidence age. Use event-based resumption when available; otherwise perform a bounded check and hand off. Stop after the repair budget, a repeated non-improving failure, or an unresolved external dependency.

## Output

Produce a `review-status` containing `payload.review_reference`, `head`, `base`, `readiness` (`ready`, `waiting`, `failed`, or `blocked`), `findings`, `checks`, `updates`, and `next_event`. Preserve a stable identifier for each finding and its disposition. A completed assessment can report waiting; it is not permission to integrate.

## Completion and boundaries

Only label the candidate ready when the required policy checks and review decisions are satisfied for its current identity. Use blocked when access, authority, or an external decision prevents progress; never convert budget exhaustion into approval. This skill does not merge, enable automatic integration, close unrelated work items, or deploy.

## Example and handoff

If an older review comment identifies a missing authorization check, keep it open until the current implementation and regression evidence address it, even after several newer pushes. If the build failed because its runner was unavailable, report that distinction. Hand a current ready status to `sf-integrate-change`.
