---
name: sf-build-change
description: "Implement one bounded work unit with requirement-linked evidence and a reviewable change set. Use when a specification and work plan are ready for source changes."
---

# Build change

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the selected ready work item, specification, and available design, test, or diagnosis artifacts. Confirm the item’s dependencies and write scope. Use the project’s actual build and verification mechanisms; no particular language, framework, editor, or agent interface is assumed.

For a fixed recipe bounded to one increment, require a work plan containing one explicitly ready item and a specification scoped to that increment. If a larger plan is supplied, request a scoped item packet or an expanded host workflow; do not silently select one item and report the whole feature complete.

## Procedure

1. Inspect the current workspace and candidate revision. Preserve unrelated changes and establish an isolated work area when the host supports one. Confirm that prerequisites still apply and that the authorized write scope covers the intended files and generated outputs.
2. Trace the behavior to be changed and choose the smallest coherent implementation. Follow existing ownership and interfaces. If the design cannot satisfy a requirement, record the conflict and resolve the necessary decision before expanding the task.
3. Establish a discriminating verification case. For a defect, replay the supplied reproduction and capture its failure where feasible. For new behavior, define expected results independently of the implementation. Prefer a focused behavioral test or executable experiment over a brittle assertion about internal structure.
4. Implement an increment and run the most relevant checks. Keep test inputs, expected values, and production logic sufficiently independent to catch incorrect behavior. Do not weaken checks, bypass policy, or replace required proof with a successful build.
5. Inspect the resulting diff for accidental scope, unfinished behavior, compatibility effects, secrets, generated churn, and documentation consequences. Run the appropriate broader checks after the focused path works. Record exactly which environment and candidate produced each result.
6. Repair defects within the item’s scope and budget. Use at most two repair cycles after the first implementation attempt, unless the caller supplies a different bound. Stop and explain when the fix requires a new requirement, a risky migration, or a larger architectural decision.
7. Produce a clean handoff describing behavior, changed surfaces, checks, and remaining risks. Do not publish, merge, deploy, or mark external work complete merely because implementation is finished.

## Output

Emit a `change-set` envelope with `payload` fields `work_item`, `criteria_addressed`, `base_revision`, `candidate_revision`, `changed_paths`, `behavior_changes`, `checks_run`, `compatibility_notes`, `documentation_needs`, and `remaining_work`. Include a reproducible diff or immutable source reference. Record the effective tree identity if uncommitted content is part of the candidate.

## Completion and failure

Pass when the selected item is implemented and the required item-level checks have current evidence. This does not replace independent verification or review required by policy. Return `failed` for a known criterion violation, `blocked` for unavailable prerequisites or required runtime, and `inconclusive` when the attempt cannot establish correctness. Any later source, configuration, or dependency change invalidates affected proof.

## Example

For preventing duplicate notifications, first demonstrate the duplicate with a controlled retry, implement the ownership rule, then check both retry suppression and delivery of distinct events. A test that only counts calls to a new helper is insufficient.

## Handoff

Offer the candidate to `sf-verify-change`, `sf-assess-impact`, and `sf-review-change` as required by the selected workflow. Keep the candidate stable while its evidence is gathered.
