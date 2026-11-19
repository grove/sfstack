---
name: sf-plan-work
description: "Decompose a specification and design into bounded, dependency-aware work units. Use when planning delivery, coordinating parallel implementation, or splitting a change into independently verifiable increments."
---

# Plan work

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the specification and design, including their open decisions and rollout constraints. Use project context to assess verification cost and ownership. Treat existing tickets as candidate work descriptions; do not inherit obsolete dependencies or assume that their status proves completion.

## Procedure

1. Identify the deliverable outcome and its acceptance criteria. Separate unresolved decisions from implementation work. Create a research or decision task when uncertainty must be reduced before a build task can be meaningfully scoped.
2. Find small increments that demonstrate useful behavior across the required layers. Prefer a narrow end-to-end path over a stack of unrelated implementation layers. For mechanical migrations, use explicit preparation, bounded conversion batches, and cleanup when a vertical slice would be misleading.
3. Define each work unit with purpose, inputs, output artifacts, criteria, verification method, affected ownership boundaries, and exclusions. Make it small enough for one accountable worker to complete and explain without relying on the full project conversation.
4. Add only real prerequisites. Distinguish a dependency on a decision or contract from a preference for a particular ordering. Check the graph for cycles and identify the first ready frontier.
5. Plan parallel work around stable interfaces and isolated write ownership. Name the integrator and how conflicting changes, shared generated artifacts, and cross-cutting tests will be reconciled. Parallel execution must not depend on workers editing the same uncoordinated state.
6. Define integration checkpoints and evidence requirements. State when earlier proof becomes stale, which combined result must be reverified, and what prevents a work item from being closed. Include rollout, documentation, and operational work where required by the scope.
7. Set bounded effort and recovery rules for each uncertain item. Record assumptions, escalation conditions, and deferred ideas. Produce a tracker-neutral plan; publishing or changing external work items requires an adapter and separate authorized action.

## Output

Emit a `work-plan` envelope with `payload` fields `goal`, `items`, `dependencies`, `ready_frontier`, `integration_strategy`, `verification_checkpoints`, and `deferred_work`. Each item contains a stable `id`, `purpose`, `inputs`, `deliverables`, `acceptance_criteria`, `verification`, `owner_role`, `write_scope`, `dependencies`, and `stop_conditions`. Reference criteria by identifier instead of duplicating contradictory versions.

## Completion and failure

Pass when every in-scope criterion has an accountable path to delivery, at least one item is ready or its blocker is explicit, and the graph is acyclic. Return `blocked` when unresolved design decisions prevent a usable plan. Return `inconclusive` when proposed tasks cannot be independently understood or verified. Do not label planned work as implemented or create artificial precision through unsupported time estimates.

## Example

For replacing an identifier format, plan compatibility support first, convert producers and consumers in bounded groups, verify mixed-version operation, then remove the old format only after usage evidence satisfies the exit condition.

## Handoff

Offer one ready item and its relevant references to `sf-build-change`. Offer the graph to `sf-coordinate-work` when multiple workers or resumable execution are needed.
