---
name: sf-refactor-structure
description: "Improve internal structure while preserving an explicitly defined behavioral contract. Use for bounded refactoring, reducing duplicated decisions, or preparing a safe structural migration."
---

# Refactor structure

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the request and project context. Identify the structural problem using concrete examples: repeated policy decisions, tangled ownership, costly changes, or confusing interfaces. Use any supplied impact assessment and test plan. Do not treat a preferred style as sufficient justification for broad changes.

## Procedure

1. Define the improvement and the behavior that must remain stable. Include public interfaces, errors, ordering, persistence, timing guarantees, resource ownership, and operational behavior where relevant. Separate an intended behavior change into a distinct requirement.
2. Inspect consumers and existing verification. Establish a baseline on the current candidate. If important behavior lacks protection, add a narrow characterization check or reproducible comparison before changing its structure; distinguish accidental behavior from an agreed compatibility obligation.
3. Choose the smallest structural move that addresses the problem. Evaluate how it simplifies callers and future changes, rather than counting extracted helpers or deleted lines. Avoid abstraction for variants that do not yet exist unless a real boundary requires it.
4. Plan bounded increments with an intelligible intermediate state. For a broad mechanical migration, introduce compatibility support, migrate consumers in groups, and remove the old path only after usage and verification evidence allow it.
5. Apply one increment and run the relevant behavioral checks. Compare externally observable results against the baseline. Inspect generated or persisted forms where a superficially internal change can affect compatibility.
6. Review the diff for hidden behavior changes, altered test expectations, and unrelated cleanup. Repair within two bounded cycles, or stop with a clear remaining risk. Never make a preservation test pass by changing its expectation without identifying an authorized behavior change.
7. Recheck the combined candidate and explain the structural improvement with a representative caller or change scenario. Preserve rollback information where transitional code or data is involved. Leave publication and integration to their dedicated workflows.

## Output

Emit a `change-set` envelope with `payload` fields `structural_problem`, `improvement`, `preserved_contract`, `base_revision`, `candidate_revision`, `changed_paths`, `increments`, `behavior_comparison`, `compatibility_notes`, and `remaining_work`. Include evidence for both the baseline and the final candidate. Mark any behavior whose preservation remains unverified.

## Completion and failure

Pass when the stated structural problem is materially improved and the required preservation checks have current evidence. Return `failed` for a known regression, `blocked` for missing prerequisites, or `inconclusive` when the important behavior cannot be observed. A smaller file or a clean build alone does not establish a successful refactor.

## Example

For duplicated pricing decisions in several entry points, move the policy behind one clear boundary and compare representative prices, rounding, errors, and historical compatibility. Do not combine this with a new pricing rule under the same refactoring claim.

## Handoff

Offer the stable candidate to `sf-verify-change` and `sf-review-change`. Provide transition constraints to `sf-prepare-release` if old and new forms must coexist.
