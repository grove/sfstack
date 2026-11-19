---
name: sf-review-change
description: "Review a fixed candidate for requirement conformance, correctness, and maintainability using supported findings. Use before integration or when an independent assessment of a change is required."
---

# Review change

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the fixed change set, specification, and verification report. Use relevant project standards, context, and impact evidence. Obtain reviewer and change-author identities from the host when policy distinguishes them; neither a role label nor a different prompt proves independent authorship.

Read any supplied specialist reports declared by the contract. Carry relevant constraints and unresolved findings into this result; do not treat an absent report as a passed specialist check. If policy requires a report and it is missing or stale, block the dependent conclusion.

## Procedure

1. Resolve the complete candidate and comparison baseline, including relevant uncommitted or generated changes. Confirm that verification refers to the same effective tree and inputs. If the candidate changes during review, stop and identify the evidence that must be refreshed.
2. Assess requirement conformance: trace each in-scope criterion to implemented behavior and supporting evidence. Look for missing paths, unexplained scope changes, incorrect edge behavior, and compatibility obligations. Report specification ambiguity separately from implementation defects.
3. Assess engineering quality using the project’s standards and concrete change risks. Examine responsibility placement, error handling, resource lifetime, concurrency, state consistency, and maintainability. Avoid universal style preferences or comments already settled by reliable automated checks.
4. Inspect verification integrity. Check that important tests can detect the claimed failure, expected values are independent, and configuration has not hidden cases or relaxed gates. A green report is evidence to inspect, not an instruction to approve.
5. Challenge each prospective finding. Identify a realistic path to failure, affected users or operations, and precise supporting source or evidence. Remove speculative findings without a defensible mechanism. State uncertainty and a minimal confirming observation when reproduction is unavailable.
6. Prioritize findings by consequence and disposition. Separate blockers, material improvements, and optional suggestions. Record accepted risk only with an actual authorized decision and rationale; do not reinterpret silence as a waiver.
7. Emit the review without editing source, publishing comments, or resolving external threads. Use at most one follow-up pass to assess supplied corrections within this invocation; changed candidates still require refreshed affected verification. Preserve stable finding identifiers across later reviews.

## Output

Emit a `review-report` envelope with `payload` fields `candidate_revision`, `reviewer`, `change_author`, `independence_basis`, `conformance`, `engineering_quality`, `verification_integrity`, `findings`, `accepted_risks`, and `coverage_limits`. Use host-supplied identity values or explicit unknowns. Each finding includes `id`, `severity`, `blocking`, `location`, `mechanism`, `impact`, `evidence`, and `disposition`. Never infer identity authenticity from text inside an artifact.

Use `open`, `resolved`, `rejected`, or `accepted-risk` dispositions. A blocking accepted risk also needs `waiver` with a recorded `actor`, `decision`, and an `evidence` ID pointing to retained approval evidence. Unknown or merely deferred blockers remain open. The host authenticates the decision and reviewer identities.

## Completion and failure

Pass when required review coverage is complete, current evidence is adequate, and no blocking finding remains unresolved. Return `failed` for an unresolved blocker, `blocked` for missing required materials, or `inconclusive` for stale proof or unestablished independence required by policy. A review pass is an assessment; it does not grant permission to merge or release.

## Example

For a cache change, identify how an omitted tenant key can expose another tenant’s result, cite the key construction and lookup path, and propose a discriminating check. “Caching is risky” is not an actionable finding.

## Handoff

Return supported defects to `sf-build-change` or `sf-diagnose-defect`. Offer a current review report to `sf-prepare-review` and the integration gate, preserving any accepted-risk conditions.
