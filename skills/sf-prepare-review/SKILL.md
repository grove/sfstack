---
name: sf-prepare-review
description: "Prepare and publish a focused change for review through the available review adapter. Use when an implementation is verified and needs a review request or equivalent reviewable submission."
---

# Prepare review

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the change set, verification report, and review report. Include specification and impact assessment when supplied. Identify the target repository or review surface, intended base, contributor history, publication authority, and current candidate. Use the available adapter rather than assuming a hosting service or command-line client.

## Procedure

1. Reconcile the intended change with the complete candidate, including new files and relevant configuration. Check for an existing submission for the same work. Preserve unrelated workspace changes and contributor attribution. Do not create a duplicate review merely because a previous publication response was lost.
2. Verify that implementation, verification, and review refer to the same candidate and input state. Resolve differences before publication. Ensure required checks actually ran, findings have explicit dispositions, and unsupported environments are disclosed. A summary that says tests passed cannot replace execution evidence.
3. Inspect the material to be published for unintended files, credentials, personal data, generated noise, and internal-only evidence. Use safe references for restricted logs. Exclude unrelated local artifacts without discarding their owner's work.
4. Prepare a concise review narrative: the problem, why it matters, resulting behavior, significant design decisions, verification evidence, compatibility or rollout implications, and unresolved limits. Connect the change to work-item identifiers without relying on one tracker's closing syntax.
5. Establish the publication boundary: source branch or patch, target base, review title, visibility, and allowed metadata changes. Publishing a review does not imply permission to merge, request named reviewers, notify people, or deploy. If publication is not authorized, retain the prepared package and return blocked for publication with the exact next action.
6. Publish through the adapter with a stable correlation or idempotency key when supported. Recheck remote state before retrying an ambiguous response. If a source push is needed, write only the authorized branch and never overwrite another contributor's new work.
7. Read the resulting submission back. Confirm its identity, head, base, title, body, and linked evidence. Record observed checks as pending, passed, failed, or unknown; do not report the submission ready solely because creation succeeded.

## Output

Produce a `review-package` with `payload.publication_state` (`prepared` or `published`), `candidate`, `base`, `review_reference`, `narrative`, `evidence_links`, and `remaining_work`. A prepared package has no fabricated remote identifier. Include the exact publication receipt when a review exists.

## Completion and boundaries

Pass a publication task only after reading back the intended submission. Return blocked for missing authority or adapter capability, inconclusive for an unresolved publication outcome, and failed for a confirmed mismatch. Do not modify the candidate after its final checks without invalidating affected evidence. Keep source corrections in an implementation task.

## Example and handoff

For a retry fix, explain the duplicate-processing failure, the new idempotency behavior, and the regression that demonstrated it. Link the exact verification result and disclose any untested deployment mode. Hand the published reference to `sf-maintain-review`; leave integration to `sf-integrate-change`.
