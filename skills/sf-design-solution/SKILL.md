---
name: sf-design-solution
description: "Choose a maintainable implementation structure that satisfies a specification and existing system constraints. Use for consequential boundaries, competing approaches, or changes with difficult-to-reverse decisions."
---

# Design solution

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the specification and project context at their identified revisions. Inspect the relevant current source to confirm the context remains accurate. Use domain rules and impact evidence when supplied. Scale the design effort to the consequence of the decision, not to the size of a template.

Read any supplied specialist reports declared by the contract. Carry relevant constraints and unresolved findings into this result; do not treat an absent report as a passed specialist check. If policy requires a report and it is missing or stale, block the dependent conclusion.

## Procedure

1. Identify the decisions that actually need design: responsibility placement, information ownership, public contracts, failure handling, and rollout. Preserve existing conventions unless evidence shows that they obstruct the required outcome.
2. Sketch the caller or operator experience first. Show the inputs, outputs, errors, timing, and ownership a consumer must understand. Prefer an interface that hides avoidable decisions while leaving consequential policy explicit.
3. Compare at least two materially different approaches for difficult-to-reverse choices. Include a small extension of the existing design when viable. Evaluate complexity paid by callers, change locality, verification cost, operational burden, and reversibility; do not score options with unsupported precision.
4. Trace normal and failure paths through the preferred approach. Account for concurrency, partial success, retries, stale information, cleanup, and transitions between versions where relevant. State which guarantees are local and which depend on other systems.
5. Identify verification seams and evidence needed to challenge the design. Propose a bounded experiment when an uncertain performance or integration assumption controls the decision. Keep an unperformed experiment explicitly pending instead of treating plausibility as proof.
6. Describe the migration or rollout order, compatibility window, and recovery strategy. Highlight any state that cannot be restored by reverting source. Assign decisions that require product, operational, or security authority to their owners.
7. Record the chosen approach, rejected alternatives, reasons, and revisit triggers. Give implementers enough structure to proceed while leaving routine details adaptable. Do not start code changes or expand the specification without an authorized change to scope.

## Output

Emit a `solution-design` envelope with `payload` fields `decisions`, `responsibilities`, `interfaces`, `data_ownership`, `behavior_paths`, `alternatives`, `verification_seams`, `rollout`, `recovery`, and `open_questions`. Link each consequential decision to relevant requirement identifiers and evidence. Include a compact diagram only when it clarifies ownership or ordering better than prose.

## Completion and failure

Pass when the design addresses the required behavior, makes the important tradeoffs inspectable, and identifies a credible verification and rollout path. Return `blocked` for missing authority or a required unresolved constraint; return `inconclusive` when a critical assumption cannot yet be tested or justified. A design pass does not establish runtime correctness.

## Example

For deduplicating asynchronous requests, compare ownership at admission with ownership at execution. Examine races, retention, replay, and user-visible responses before choosing a shared store or a queue-specific mechanism.

## Handoff

Offer the design to `sf-plan-work` and `sf-design-tests`. Route consequential unresolved questions to their decision owners, with the smallest experiment needed to resolve them.
