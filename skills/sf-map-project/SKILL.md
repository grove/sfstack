---
name: sf-map-project
description: "Map a project into evidenced behavior, ownership boundaries, and verification paths. Use when entering an unfamiliar repository, locating a change, or refreshing stale project context."
---

# Map project

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the request and the supplied project scope. Use existing repository instructions, current source, configuration, and available design records. Treat earlier summaries as leads to verify, not as authoritative descriptions of the current revision.

## Procedure

1. Fix the investigation boundary: identify the candidate revision, requested behavior, relevant deployment or execution context, and available read capabilities. Note uncommitted changes without discarding or absorbing them into the task.
2. Inspect the project’s entry points and declarations before broad searching. Locate how it is built, started, configured, tested, and operated. Record declared commands as candidates; do not run setup scripts merely because a document recommends them.
3. Trace one representative user or system action from input to observable result. Follow actual calls, messages, state transitions, or data movement. Include asynchronous completion and failure handling when they affect the requested behavior.
4. Describe the components that own decisions and state. Distinguish a conceptual responsibility from a directory name. Identify external systems, generated artifacts, persistence boundaries, and configuration that can redirect execution.
5. Inspect verification facilities relevant to that path. Identify behavioral tests, integration environments, manual checks, fixtures, and known isolation requirements. Mark whether each is merely discovered or has current execution evidence supplied by the caller.
6. Check the highest-impact uncertainties with narrow source reads. Stop expansion when additional files no longer change the placement decision. If conflicting designs exist, explain which path is active and what evidence is missing.
7. Produce a compact map with precise source references, a suggested change location, and questions that genuinely require a maintainer decision. Do not modify source or silently convert mapping into implementation.

## Output

Emit a `project-context` envelope. Set `payload` to an object containing `scope`, `entry_paths`, `components`, `data_boundaries`, `configuration`, `verification_paths`, `constraints`, and `open_questions`. Give each significant claim a source or evidence identifier. Include `revision` and `observed_at` in the map when its contents may become stale independently of source changes.

## Completion and failure

Pass when the requested behavior can be located, its consequential boundaries are evidenced, and remaining uncertainty is explicit. A complete inventory of the repository is unnecessary. Return `blocked` when essential files cannot be accessed, or `inconclusive` when available evidence cannot establish the active path. A discovered test command is not proof that the project works.

## Example

For “Where should we add cancellation of an export?”, trace request admission, job ownership, cancellation signaling, storage cleanup, and result delivery. Identify whether cancellation is currently best-effort or guaranteed, and what test environment could establish the distinction.

## Handoff

Offer this map to `sf-clarify-outcome`, `sf-design-solution`, or `sf-diagnose-defect` according to the caller’s objective. Keep the handoff scoped to relevant evidence and unanswered questions.
