---
name: sf-write-specification
description: "Describe externally observable behavior, constraints, and acceptance criteria for a bounded change. Use when an agreed outcome needs an implementation-ready specification or an existing specification needs reconciliation."
---

# Write specification

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the outcome brief and all relevant supplied decisions. Use project context, domain language, opportunity evidence, and experience designs when available. Reconcile existing material before introducing new questions; a specification records the agreement rather than restarting discovery.

Read any supplied specialist reports declared by the contract. Carry relevant constraints and unresolved findings into this result; do not treat an absent report as a passed specialist check. If policy requires a report and it is missing or stale, block the dependent conclusion.

## Procedure

1. Establish the authoritative scope and artifact versions. Resolve contradictions by identifying the decision owner and recording the chosen interpretation. Never silently overwrite an accepted constraint because another document is newer or more convenient.
2. Describe the current problem and intended behavior in terms of actors, inputs, outcomes, and observable state. Define terminology locally or reference the supplied domain model. Separate requirements from possible implementation approaches.
3. Give each requirement and acceptance criterion a stable identifier. Cover representative success, boundaries, invalid input, partial completion, cancellation, and recovery as applicable. State what observers can measure without requiring private implementation details.
4. Specify material quality constraints: security, privacy, accessibility, compatibility, performance, reliability, and operational support. Use supplied targets or explicitly unresolved decisions. Do not invent numerical service levels or apply irrelevant categories merely to fill a template.
5. Define integration and data expectations, including old and new participants during rollout. Record who owns authority, retries, ordering, idempotency, retention, and irreversible effects when these affect correctness.
6. Describe how each criterion can be verified and what environment or evidence is required. Identify prerequisites and hard-to-observe behavior early. A proposed test method is a plan, not proof that the criterion has passed.
7. Record exclusions, rollout constraints, reversal requirements, open decisions, and acceptance ownership. Check that the specification can be understood without reading the conversation. Keep code paths as supporting evidence where useful, not as the sole definition of the requirement.

## Output

Emit a `specification` envelope with `payload` fields `problem`, `scope`, `actors`, `requirements`, `acceptance_criteria`, `quality_constraints`, `integration_contracts`, `verification_approach`, `rollout_constraints`, `non_goals`, and `open_decisions`. Link criteria to their source outcome or domain rule. Include a concise change record when reconciling an existing specification so that downstream plans can detect changed assumptions.

## Completion and failure

Pass when a builder and a verifier can independently interpret the same behavior and all material unresolved choices have explicit treatment. Return `blocked` for a decision that prevents safe implementation. Return `inconclusive` for unresolved contradictions. Do not claim approval unless it exists in the supplied authorization or decision record. Do not publish the specification to an external tracker through this skill.

## Example

For resumable imports, specify how progress is identified, how a repeated segment is handled, what remains visible after failure, and which compatibility guarantees apply to older clients. Avoid defining success merely as “add a resume endpoint.”

## Handoff

Offer the specification to `sf-design-solution`, `sf-design-tests`, or `sf-plan-work` when a sufficient design already exists. Preserve criterion identifiers through all later artifacts.
