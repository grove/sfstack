---
name: sf-prepare-release
description: "Assemble a reproducible release candidate and a bounded rollout plan. Use when integrated changes need versioning, release notes, artifact identification, rollout, and recovery preparation."
---

# Prepare release

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the integration record and resolve the exact integrated revision. Include verification, migration, observability, and request artifacts when available. Establish the release audience, target environments, release policy, responsible operator, and whether the candidate includes data or compatibility changes.

Read any supplied specialist reports declared by the contract. Carry relevant constraints and unresolved findings into this result; do not treat an absent report as a passed specialist check. If policy requires a report and it is missing or stale, block the dependent conclusion.

## Procedure

1. Enumerate the changes entering the release from observed integration history. Reconcile work items, user-visible behavior, compatibility changes, and known issues. Do not describe an unmerged or excluded feature as shipped merely because it appears in a tracker or branch.
2. Apply the project's version and release-note conventions. If versioning or packaging requires source modifications, return those as a separate change requiring verification and integration. Do not silently alter the already verified revision while continuing to cite its old evidence.
3. Build or identify the candidate through the declared reproducible build path. Record source revision, resolved inputs, build configuration, toolchain identity, and artifact digest. Check that artifacts contain the intended contents and no unintended secrets. Distinguish repeatable build procedure from byte-for-byte reproducibility actually demonstrated.
4. Collect applicable verification, review, compatibility, security, accessibility, and performance evidence. Confirm their scope and freshness. Treat missing required evidence as a blocker; record optional assessments as unperformed rather than implying a full review occurred.
5. Define rollout stages, target identity, ordering, capacity needs, maintenance constraints, and migration sequencing. Give each stage an entry condition, action, observation window, success condition, abort threshold, owner, and time budget. Specify how an operator confirms the deployed revision independently of a generic health response.
6. Design recovery against the candidate's actual data and dependency compatibility. Identify the known-good target, retained artifacts, restoration evidence, and consequences for writes accepted during rollout. Separate code rollback, data restoration, failover, and roll-forward repair.
7. Assemble a reviewable release manifest and operator instructions. State required authorization for artifact publication, deployment, data mutation, and external communication separately. Resolve unknown deployment behavior before execution, and define how partial or ambiguous outcomes will be reconciled.

## Output

Produce a `release-plan` with `payload.release_id`, `source_revision`, `artifacts`, `change_summary`, `evidence_manifest`, `targets`, `rollout_stages`, `abort_conditions`, `recovery_plan`, and `required_authorizations`. Include draft release communication as an artifact only when needed; do not send it.

## Completion and boundaries

Pass preparation when the immutable candidate and required controls can be inspected and the release decision has sufficient evidence. This does not publish, deploy, or establish production health. Use blocked for missing mandatory evidence or unresolved deployment and recovery requirements. Never call a restoration path proven unless it was actually exercised and its evidence remains applicable.

## Example and handoff

For a release adding a new event field, identify the exact build, supported consumer versions, staged rollout, queue-lag threshold, and recovery behavior for events already emitted. Hand the plan to `sf-deploy-release`; use `sf-observe-release` to assess outcomes after deployment.
