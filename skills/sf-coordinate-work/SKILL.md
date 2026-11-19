---
name: sf-coordinate-work
description: "Coordinate a bounded graph of work across available agents without losing ownership or evidence. Use to run a software-factory workflow, schedule parallel work, resume execution, or manage handoffs."
---

# Coordinate work

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the work plan and supplied execution context, including existing run records, artifact references, actor identities, policies, and budgets. Use project context and the request when available. Treat the plan as a dependency graph with explicit outcomes rather than a list of commands to execute blindly.

## Procedure

1. Validate the graph, required inputs, acceptance criteria, output types, and integration boundaries. Detect cycles, missing dependencies, conflicting ownership, and work that exceeds the agreed scope. Separate discovery decisions from implementation tasks when a prerequisite is not yet settled.
2. Identify the ready frontier from current accepted artifacts. Check revision, input, and environment identity before reusing evidence. A worker's completed message is not sufficient proof; inspect the referenced result and unresolved conditions.
3. Create a bounded work packet for each ready item: objective, input references, owned resources, allowed capabilities and effects, completion evidence, time or cost budget, retry limit, and escalation conditions. Supply only task-relevant context; do not leak expected answers into an independent evaluation or review.
4. Assign one owner and a claim identifier for each work item. Parallelize independent investigation or changes with isolated work areas. Serialize conflicting writes and integration. Require the host to persist claims with an observed-state precondition; without atomic claims, keep dispatch serial rather than pretending races are prevented.
5. Return dispatch decisions to the host's authorized execution mechanism. If no agent-dispatch adapter is available, provide the same packets for sequential or human execution. This skill's baseline produces coordination artifacts; it does not assume an agent API, write tracker records, or grant workers additional permissions.
6. Reconcile returned artifacts with the packet and current state. Preserve failed, blocked, and inconclusive outcomes. Route a bounded repair or a specific external decision; stop repeated non-improving loops. Integration can invalidate prior evidence, so schedule appropriate verification on the combined candidate.
7. Checkpoint the run after meaningful transitions: accepted outputs, outstanding claims, remaining budgets, next events, and cancellation state. On resume, reconcile live external operations before dispatching duplicates. Cancel or expire abandoned claims explicitly and preserve the history needed for another owner to continue.

## Output

Produce a `coordination-record` with `payload.run_state`, `ready_items`, `work_packets`, `claims`, `accepted_artifacts`, `blocked_items`, `budget_state`, and `next_checkpoint`. Record planned dispatch separately from confirmed execution. Include a clear completion decision tied to the workflow's required outcomes.

## Completion and boundaries

Pass a coordination interval when scheduling decisions are consistent and the next action is explicit; declare the overall workflow complete only when all required outcome artifacts are accepted and current. Missing capability or authority blocks the affected task, not an invented substitute operation. Keep permission enforcement, external side effects, durable locking, and credential isolation in the host runtime.

## Example and handoff

Two independent adapters may be implemented in isolated work areas, then integrated by one owner. Verify the combined result even if both individual tasks passed. Hand a blocked policy decision to its responsible owner; use `sf-improve-process` when recurring coordination failures reveal a structural problem.
