---
name: sf-evolve-data
description: "Plan a compatible, recoverable data or schema evolution. Use for persisted-data changes, backfills, storage moves, rolling migrations, and irreversible transformations."
---

# Evolve data

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the project context and specification. Inspect the current data model, writers, readers, retention, and deployment topology. Use a supplied design or change set as evidence, not as proof that a migration is safe. Identify the migration owner and the environments in which rehearsal may later occur.

## Procedure

1. State the invariants that must remain true: identity, uniqueness, ordering, referential integrity, totals, authorization boundaries, and permitted loss or delay. Estimate data volume, growth, hot partitions, write rate, and the operational budget for locks, lag, and extra capacity.
2. Map all readers and writers, including older deployed versions, background jobs, reporting, imports, exports, and external consumers. Build a compatibility matrix for old and new code against each intermediate data shape.
3. Divide the change into observable phases. Prefer introducing compatible structures, migrating readers and writers, backfilling, verifying, switching authority, and removing obsolete structures only when their prerequisites are satisfied. Do not force this pattern where an atomic offline change is demonstrably simpler and authorized.
4. Design the transformation with stable progress markers, bounded batches, idempotent retries, conflict handling, and resumability. Define how concurrent writes are captured and reconciled. Explain whether repeated execution can duplicate, lose, or overwrite data.
5. Specify rehearsal and validation. Use representative volume and edge cases, compare independent counts or invariants, and sample meaning as well as row totals. Include interrupted execution, partial failure, repeated batches, lagging consumers, and restoring a checkpoint. State what cannot be reproduced outside production.
6. Define phase entry and exit gates, responsible operators, monitoring, pause criteria, and time limits. Make destructive cleanup a separate authorized step after the compatibility window and evidence of consumer migration.
7. Design recovery for each phase. Distinguish reverting code, compensating data, restoring a backup, and rolling forward. Account for writes accepted after the migration began, recovery point objectives, restoration time, and whether old binaries can read the resulting data. Mark irreversible boundaries explicitly.

## Output

Produce a `migration-plan` with `payload.invariants`, `compatibility_matrix`, `phases`, `transformation`, `rehearsal_plan`, `verification_queries`, `operating_limits`, and `recovery_matrix`. Include expected evidence for every phase exit and an explicit list of irreversible actions. Commands, when provided, must be derived from the actual project and reviewed before execution.

## Completion and boundaries

This skill completes a plan, not a live migration. A passed plan requires a plausible compatibility and recovery path; it must identify missing rehearsal results. Return blocked if essential invariants or ownership cannot be established. Never represent a backup's existence as proof of successful restoration, and never authorize data mutation by describing it.

## Example and handoff

For splitting a customer's address into structured fields, preserve old readers while new writers populate both forms, reconcile updates during backfill, and defer dropping the original field until consumers are confirmed. Hand implementation to `sf-build-change`, compatibility checks to `sf-check-compatibility`, and execution controls to `sf-prepare-release`.
