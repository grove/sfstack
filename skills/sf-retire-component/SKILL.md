---
name: sf-retire-component
description: "Plan the controlled retirement of a component, interface, environment, or data set. Use for deprecation, service shutdown, feature removal, or end-of-life migration."
---

# Retire component

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the project context and retirement request. Include an impact assessment or specification when supplied. Establish what is being retired, why, the owner, desired date, supported consumers, retention obligations, and the authority responsible for accepting residual risk.

## Procedure

1. Inventory the component's public and internal contracts, dependencies, data, credentials, scheduled work, infrastructure, documentation, and operational responsibilities. Trace indirect consumers such as reports, exports, integrations, disaster-recovery paths, and rarely used administrative functions.
2. Gather evidence of use from source references, maintained inventories, supplied telemetry, owner confirmation, and support history. State the observation window and blind spots. No recent traffic or no text-search match is not sufficient proof that nobody depends on the component.
3. Define the replacement or intentional removal outcome. Map each consumer to a migration path, supported alternative, explicit acceptance of loss, or unresolved owner. Include compatibility windows, contractual commitments, offline users, and delayed events.
4. Plan deprecation notices and migration guidance with dates, affected audiences, responsibilities, and escalation paths. Keep communications as drafts until publication and recipients are authorized. Define measurable adoption or readiness evidence rather than relying only on elapsed time.
5. Separate reversible disablement from irreversible deletion. Specify a staged sequence such as preventing new adoption, migrating consumers, disabling the interface, observing, removing code and infrastructure, and disposing of retained data. Give each step entry checks, exit evidence, an owner, and a recovery option.
6. Define data disposition for primary storage, replicas, backups, logs, archives, and external processors. Resolve required retention and holds before deletion. Address credentials, domains, routing, and resource names that could create takeover or accidental-reuse risks after shutdown.
7. Design verification after each step: expected failures are intentional and understandable, replacements work, no residual jobs or costs remain, sensitive access is revoked, and required records survive. Make the irreversible decision a separately authorized checkpoint after evidence review.

## Output

Produce a `retirement-plan` with `payload.inventory`, `consumer_matrix`, `usage_evidence`, `replacement_paths`, `communication_plan`, `phases`, `data_disposition`, `recovery_options`, and `exit_criteria`. Identify unknown owners and unverified consumers as explicit blockers or accepted risks, with the decision authority recorded.

## Completion and boundaries

Pass the planning task when the retirement path and its evidence requirements can be reviewed. Do not claim that retirement or deletion occurred. Return blocked when an essential consumer, retention obligation, or recovery decision remains unresolved. Implementation, infrastructure shutdown, account removal, and data destruction require separate authorization and execution records.

## Example and handoff

For an old export format, identify external consumers and archived-file readers, offer a conversion path, observe migration, then disable new exports before deleting compatibility code. Preserve required historical access. Hand source removal to `sf-build-change`, operational stages to the deployment process, and outcome checks to `sf-verify-change`.
