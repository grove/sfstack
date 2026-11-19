---
name: sf-recover-release
description: "Restore an acceptable service state using an authorized, data-compatible recovery action. Use for rollback, roll-forward repair, failover, or a rehearsed release recovery."
---

# Recover release

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the deployment record and recovery request. Resolve the current target, revision, impact, explicit recovery authority, and permitted effects. Include release, observation, incident, and migration artifacts when available. Use the host-approved recovery policy; block if none applies. Emergency scope may differ from release scope. Never weaken policy or rely on a prior deployment grant to justify recovery.

Data mutation is a conditional effect in the contract. Perform it only when the host selects `data.modify` for this invocation and supplies its separate scoped grant. When it is omitted, keep recovery to authorized deployment effects; if live data work becomes necessary, stop at that boundary.

## Procedure

1. Establish the current state from live deployment and telemetry evidence. Identify incomplete operations, mixed revisions, queued work, ongoing migrations, and writes accepted since the release. Preserve the smallest useful diagnostic snapshot without delaying an authorized urgent mitigation.
2. Compare feasible actions: pause rollout, remove traffic, restart a failed unit, roll back code, roll forward a repair, fail over, compensate data, or restore from backup. Select the action with the best expected user outcome under the stated time, data-loss, and operational limits. Do not assume rollback is always the safest choice.
3. Check compatibility of the recovery target with current data, messages, configuration, and external consumers. Identify irreversible transformations and whether older readers or writers remain valid. Confirm restoration evidence and account for data produced after a backup; a backup listing is not a recovery test.
4. Define the exact action, target, preconditions, expected state transitions, stop criteria, and operator ownership. Verify separate authority for deployment changes and any data mutation. If data restoration is not needed, explicitly exclude it from the action; declaring the capability never authorizes using it.
5. Execute one bounded recovery attempt using the approved adapter or procedure and a stable operation identity. Maintain concurrency control. If the response is ambiguous, inspect the existing operation and target state before repeating any step, especially a migration, compensation, or restore.
6. Verify recovered service behavior, not just command success. Check deployed identity, critical user outcomes, data invariants, backlog progression, and error trends through the required observation period. Record partial improvement and remaining impact separately from full recovery.
7. Preserve the incident timeline, action receipts, evidence, and follow-up needs. If the attempt fails or reaches its limit, stop the loop and hand off the current state and next decision. Do not stack unverified repairs that destroy evidence or exceed the recovery mandate.

## Output

Produce a `recovery-record` with `payload.initial_state`, `selected_action`, `authority_reference`, `compatibility_checks`, `operation_id`, `resulting_state`, `data_effects`, `verification`, and `remaining_impact`. Identify what was observed, what was inferred, and what still requires confirmation.

## Completion and boundaries

Pass only when the authorized recovery conditions are observed. Return failed for a confirmed unsuccessful action, inconclusive for uncertain results, and blocked for incompatible data, missing authority, or an unsafe unresolved precondition. A successful rollback command alone cannot establish recovery. External updates and further repairs require their own scoped actions.

## Example and handoff

If a release changed stored enum values that the old binary cannot read, do not blindly redeploy the previous image. Assess a compatible roll-forward or an explicitly authorized data recovery. After stabilization, hand evidence to `sf-handle-incident` and use `sf-improve-process` for durable corrective work.
