---
name: sf-clarify-outcome
description: "Turn an ambiguous request into a bounded, testable outcome. Use when scope, user needs, success criteria, or decision ownership are unclear before work begins."
---

# Clarify outcome

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the request, existing discussion, and any supplied project context. Carry forward decisions already made. Separate facts about present behavior from assumptions, preferences, and proposed solutions.

## Procedure

1. Restate the outcome in terms of the person or system affected, the situation they face, and the observable change they need. If the request names an implementation, determine what outcome that implementation is intended to achieve.
2. Extract constraints already supplied: compatibility, timing, cost, access, data handling, reliability, and excluded work. Mark a constraint as mandatory only when the requester or an applicable policy establishes it.
3. Build a small decision list ordered by consequence. Resolve factual questions from supplied evidence. Ask only for decisions whose answers would materially change scope, acceptance, or irreversible choices; do not ask the requester to rediscover facts accessible to the agent.
4. Define representative success, boundary, and failure scenarios. State observable results rather than internal implementation steps. Include recovery or cancellation behavior when partial completion is possible.
5. Establish non-goals and an acceptable first increment. Identify adjacent ideas separately so that useful suggestions do not silently enlarge the commitment. For a small correction, the brief may be only a few clear criteria.
6. Assign ownership to unresolved decisions and name the point at which they must be resolved. Reversible assumptions may proceed when consistent with the caller’s authorization; record their consequences and the evidence that would overturn them.
7. Check the brief against the original request. Highlight any substantive interpretation before downstream implementation. Return the usable brief without starting code, publishing work items, or repeating already settled questions.

## Output

Emit an `outcome-brief` envelope with `payload` fields `problem`, `affected_actors`, `desired_outcome`, `success_signals`, `acceptance_criteria`, `constraints`, `non_goals`, `assumptions`, and `decisions`. Give acceptance criteria stable identifiers. Each unresolved decision records an owner, consequence, and latest safe decision point.

## Completion and failure

Pass when a downstream planner can distinguish an acceptable result from an unacceptable one and the remaining assumptions are explicitly bounded. Return `blocked` when a missing decision changes authorization or makes the work impossible to scope. Return `inconclusive` when stated objectives conflict and no priority is established. Do not invent user agreement, numerical targets, or business justification to make the brief look complete.

## Example

For “Make exports faster,” clarify whether success means shorter queue time, quicker generation, or earlier access to partial results. Preserve the actual workload and correctness constraints. Record an unagreed latency target as a decision, not as a measured baseline or an accepted requirement.

## Handoff

Offer the brief to `sf-validate-opportunity` when value is uncertain, `sf-model-domain` when terminology is unstable, or `sf-write-specification` when the outcome is ready to describe precisely.
