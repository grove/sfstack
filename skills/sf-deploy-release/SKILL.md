---
name: sf-deploy-release
description: "Execute an authorized release plan and establish the identity of the deployed revision. Use for a deployment to a named environment with an approved artifact and rollout controls."
---

# Deploy release

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the release plan and required verification report. Resolve the immutable artifact, source revision, exact environment, rollout stage, deployment adapter, authorization, and operating window. Confirm that the requested action is supported by the adapter without requiring hidden provider-specific assumptions.

Read any supplied specialist reports declared by the contract. Carry relevant constraints and unresolved findings into this result; do not treat an absent report as a passed specialist check. If policy requires a report and it is missing or stale, block the dependent conclusion.

## Procedure

1. Recheck plan preconditions against the current target: deployed revision, environment identity, capacity, active incidents, required approvals, and migration state. Confirm artifact digest and evidence freshness. An environment label alone is insufficient when it can resolve to several accounts or regions.
2. Enumerate the effects of the deployment, including automatic migrations, restarts, traffic changes, and externally triggered jobs. Verify authority for each relevant effect. If the plan requires artifact publication or data mutation beyond the declared deployment action, obtain a separately scoped action before proceeding.
3. Establish a single deployment owner or equivalent concurrency control. Capture the current state and known-good recovery reference. Confirm that the approved stop and recovery procedures remain compatible with current data; the existence of an older binary is not enough.
4. Execute only the authorized stage using the exact artifact and target. Supply a correlation or idempotency key where available. Record the operation identifier immediately. Do not reconstruct deployment commands from memory when project-approved procedures exist.
5. Observe the operation with the plan's cadence and finite timeout. Distinguish accepted, running, completed, rejected, failed, and unknown outcomes. Before retrying an ambiguous response, query the existing operation and actual target to avoid duplicate deployment or repeated migration effects.
6. Verify the deployed identity through an independent target observation: revision endpoint, artifact metadata, control-plane record, or equivalent project-defined mechanism. Match it to the intended artifact and environment. A successful submission response or HTTP success from an old instance does not prove the new revision is live.
7. Check stage-level technical conditions and stop at the next approval or observation gate. Report partial rollout, mixed revisions, drift, or unresolved operations accurately. If an abort threshold is met, stop further rollout and hand off the approved recovery decision; do not invent an unapproved rollback.

## Output

Produce a `deployment-record` with `payload.release_id`, `artifact_digest`, `target`, `operation_id`, `requested_revision`, `observed_revision`, `rollout_phase`, `operation_state`, and `next_gate`. Preserve deployment receipts and identity evidence. Separate deployment completion from the service-health verdict that follows.

## Completion and boundaries

Pass the deployment stage only after its defined action and identity checks are observed. Use blocked for absent authority or preconditions, failed for a confirmed deployment failure, and inconclusive for an unresolved outcome. Do not proceed through additional stages solely because a prior stage passed. Never equate a deployment record with production acceptance.

## Example and handoff

For a staged worker rollout, verify the artifact actually running in the initial worker pool and record mixed-version state before expanding. If the controller times out, inspect the existing operation instead of resubmitting it. Send the record to `sf-observe-release`; use `sf-recover-release` only under recovery authority.
