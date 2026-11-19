---
name: sf-check-compatibility
description: "Verify compatibility across producers, consumers, versions, and persisted formats. Use for interface, protocol, event, configuration, command, or storage-contract changes."
---

# Check compatibility

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the specification and exact change set. Use project context and a migration plan when available. Establish which consumers, versions, platforms, persisted formats, and deployment orders are supported. Record who has authority to end support; do not silently shrink the matrix to make a change pass.

## Procedure

1. Enumerate the externally observable contracts affected by the change. Include request and response shapes, errors, ordering, defaults, serialization, configuration, command behavior, event semantics, timing, and storage interpretation where relevant.
2. Map producers and consumers across current, previous, and candidate versions. Include rolling deployments, delayed jobs, cached objects, offline clients, generated clients, and archived data. Identify combinations that can occur during rollout and recovery.
3. Translate the support policy into a compatibility matrix with expected outcomes. Distinguish backward compatibility, forward compatibility, interoperability, and deliberately breaking changes. An additive field may still break strict parsers or change semantics.
4. Select representative fixtures or contract tests from independently established expectations. Keep literal examples for stable public boundaries where useful. Do not generate both the input and the expected output with the same candidate code and treat agreement as proof.
5. Execute the relevant matrix in a controlled environment. Exercise valid and invalid input, unknown fields or values, omitted fields, retry and replay behavior, encoding, and boundary limits. Verify meaningful end-to-end interactions rather than only schema parsing.
6. For every mismatch, identify the affected combination, observable change, supported expectation, and migration or negotiation path. Assess whether detection occurs before harm and whether consumers can recover. Record untested combinations and why their risk remains acceptable or blocking.
7. Recheck a supplied repair against the failing combination and nearby supported cases. Preserve both baseline and candidate identities, fixtures, execution records, and results. Stop after one bounded recheck cycle unless directed otherwise.

## Output

Produce a `compatibility-report` with `payload.contracts`, `support_policy`, `matrix`, `test_results`, `breaking_changes`, `migration_requirements`, and `coverage_gaps`. Attach evidence to matrix cells and explicitly distinguish sampled evidence from complete coverage.

## Completion and boundaries

Return failed when a supported combination violates its contract. Return blocked for an unavailable required environment and inconclusive for unsupported claims or inadequate evidence. A passed result applies to the declared matrix, not all historical or future versions. Do not approve a support-policy change, publish a breaking interface, or alter stored data as part of assessment.

## Example and handoff

For an event rename, test a candidate producer with both old and new consumers and replay an old event into the candidate consumer. Verify semantics and idempotency, not just decoding. Send defects to `sf-build-change`; carry required sequencing and deprecation dates into `sf-evolve-data` or `sf-prepare-release`.
