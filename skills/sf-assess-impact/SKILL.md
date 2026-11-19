---
name: sf-assess-impact
description: "Identify downstream obligations and evidence needed to change a system safely. Use when a candidate affects shared contracts, lifecycle behavior, dependencies, persisted data, or consumers beyond the edited files."
---

# Assess impact

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the change set, current project context, and relevant specification. Begin with what the candidate changes semantically, including configuration and dependency changes. A small source diff may affect a broad contract, while a large mechanical diff may preserve it.

## Procedure

1. Identify changed assumptions: values, types, protocols, ownership, timing, defaults, ordering, resource lifetime, and persisted representations. Separate intended changes from accidental effects suggested by the diff.
2. Trace direct consumers and indirect dependencies. Inspect call sites, data readers and writers, generated clients, background jobs, operators, and external contract descriptions. Search across relevant language and repository boundaries when authorized; record inaccessible consumers rather than assuming they do not exist.
3. Examine mixed-version and lifecycle behavior. Consider startup, shutdown, retries, partial rollout, old data, queued work, cache invalidation, and delayed messages where applicable. Determine whether a source rollback also restores safe data and protocol behavior.
4. Identify the few safety claims that carry the largest consequence. For each, state what observation would establish it and which environment can provide that observation. Distinguish source inspection, logical inference, and actual execution evidence.
5. Inspect supplied evidence and challenge overbroad claims. A caller search does not prove wire compatibility; a local test does not establish production configuration; an unchanged type does not prove unchanged timing. Request a specific check when the available evidence does not support the claim.
6. Record mitigations, required sequencing, compatibility windows, and recovery limitations. Distinguish confirmed defects, credible risks, cleared concerns, and unknowns. Do not turn speculative possibilities into mandatory redesign without a plausible path to impact.
7. Produce an actionable assessment scoped to the candidate. Do not edit consumers or execute migrations. Identify the owners and checks needed to close the remaining consequential uncertainty.

## Output

Emit an `impact-assessment` envelope with `payload` fields `changed_assumptions`, `affected_consumers`, `boundaries`, `lifecycle_cases`, `safety_claims`, `risks`, `mitigations`, `required_checks`, and `recovery_limits`. Each safety claim includes its supporting evidence, strength, uncertainty, and affected requirement or consumer. Keep the candidate and relevant dependency versions explicit.

## Completion and failure

Pass when the consequential impact is understood and all required safety claims have sufficient evidence for the stated assessment. Return `failed` for a demonstrated obligation violation, `blocked` for a necessary inaccessible boundary, or `inconclusive` for consequential unresolved assumptions. A useful assessment may still be inconclusive; retain its findings rather than manufacturing a safe verdict.

## Example

For changing timestamp precision, inspect serializers, stored values, comparisons, cache keys, and consumers that round or parse the value. A compilation success in the producer cannot establish compatibility for delayed messages or older clients.

## Handoff

Offer required checks to `sf-design-tests` or `sf-check-compatibility`, and rollout obligations to `sf-prepare-release`. Supply established risks to `sf-review-change` with evidence and scope.
