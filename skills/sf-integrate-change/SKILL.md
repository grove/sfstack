---
name: sf-integrate-change
description: "Integrate an authorized reviewed change into its target using current revision evidence. Use when a review is ready to merge, land, or otherwise enter the shared integration line."
---

# Integrate change

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the current review status, verification report, and review report. Use an impact assessment when supplied. Resolve the intended target, integration strategy, exact head and base, and authorization. Determine whether integration triggers a deployment or other external effect; include such effects in the required scope before acting.

## Procedure

1. Confirm that the request authorizes integrating this specific change into this target. Require the review-status payload's `readiness` to equal `ready`, with no unresolved blocking findings. Check approvals, branch or stream rules, and separation-of-duty requirements. A passed assessment that reports waiting is not readiness; neither readiness nor a capability declaration grants authority.
2. Refresh remote state and compare head, base, checks, and review decisions with the supplied evidence. Stop on a mismatch. Obtain fresh verification after changes that invalidate the candidate or its integration assumptions; do not transplant a green result from another revision.
3. Inspect the integration result available from the source-control adapter, such as a merge candidate, staged integration commit, or equivalent preview. Check semantic interaction with concurrent work and any ordering constraints. Use the project's required integration checks rather than inventing a universal test command.
4. Establish a precondition on the observed head and target base where the adapter supports it. Serialize integration ownership for the target or use a queue that enforces equivalent freshness. If the adapter cannot prevent an unsafe race, block and identify the missing control.
5. Perform the authorized integration using the configured strategy. Preserve contributor attribution and required history. Never bypass protected checks, use administrative override, or force a shared target merely because the workflow is otherwise complete.
6. Read back the operation outcome before retrying. If the response is ambiguous, resolve whether the change already integrated. Record the actual resulting revision, which may differ from the reviewed head because of merge, squash, or replay behavior.
7. Observe required checks on the integrated result and any known automatic downstream trigger. Separate successful source integration from a healthy deployment. If a post-integration check fails, retain the integrated identity, report failure, and propose the smallest authorized recovery path rather than silently rewriting shared history.

## Output

Produce an `integration-record` with `payload.review_reference`, `requested_head`, `observed_base`, `strategy`, `integrated_revision`, `integration_receipt`, `post_integration_checks`, and `downstream_effects`. Include authorization reference and timestamps without copying confidential credentials or policy internals.

## Completion and boundaries

Pass only when the intended change is observed in the target and required integration checks are satisfied. Use blocked for missing authority, stale evidence, unmet policy, or unsafe concurrency; use inconclusive for an unresolved remote outcome. Never label integration as release or production success. A new failure requires a new evidence-based action, not an unbounded integration retry loop.

## Example and handoff

If another change lands after review, recompute and verify the integration candidate against the new base before proceeding. After a squash operation, record the new target revision rather than the old branch head. Hand that revision to `sf-prepare-release`, or report the observed automatic deployment for separate verification.
