---
name: sf-maintain-documentation
description: "Update documentation to match verified behavior and the reader\u2019s task. Use when a change affects usage, configuration, contracts, operations, or contributor guidance."
---

# Maintain documentation

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the change set, specification, and current documentation. Identify who needs to learn, accomplish a task, look up a fact, or understand a design decision. Use the project’s documentation conventions while preserving those distinct reader needs.

## Procedure

1. Map changed behavior to affected documentation surfaces: getting started, task guidance, interface and configuration reference, explanations, migration notes, and operational procedures. Include generated documentation and externally owned pages in the impact list without editing outside the authorized scope.
2. Check each existing claim against the specification and current candidate. Distinguish intended behavior from behavior actually verified. Resolve conflicting sources or record uncertainty; do not make a confident documentation claim merely because the implementation author stated it.
3. Place material according to its purpose. Write tutorials as a guided learning experience with visible results. Write how-to guides around a concrete task and prerequisites. Keep reference precise and complete within scope. Use explanation for reasons, alternatives, and tradeoffs.
4. Update the smallest coherent set of pages. Preserve established terminology and stable links. Remove or redirect superseded instructions when authorized, and explain compatibility or migration steps where users may follow an older path.
5. Verify commands, examples, configuration names, paths, and links using the actual project mechanisms. Execute relevant examples in isolated conditions when feasible. Never run destructive operational examples against a live environment simply to check that the text is correct.
6. Inspect the rendered or structured result when formatting affects use. Check heading hierarchy, navigability, accessible descriptions, and consistency between generated and maintained sources. Do not duplicate an authoritative reference in multiple places that will drift independently.
7. Record changed pages, validation results, and remaining external updates. Keep documentation changes reviewable. Publishing to a hosted service, notifying users, or changing external records requires the caller’s separate authorized workflow.

## Output

Emit a `documentation-report` envelope with `payload` fields `audiences`, `affected_surfaces`, `changed_paths`, `documentation_types`, `behavior_claims`, `checks_run`, `external_updates`, and `remaining_gaps`. Tie executable example results to the candidate and environment. If documentation changes alter a candidate under review, provide the new identity so that affected gates can be reassessed.

## Completion and failure

Pass when the relevant material matches the established behavior and required documentation checks have evidence. Return `failed` for a known contradiction, `blocked` for a required unavailable execution environment or publishing capability, and `inconclusive` for material unsupported claims. A successful spell check alone does not establish that instructions are usable or accurate.

## Example

For a new retry policy, update the configuration reference with exact defaults, a how-to guide for choosing a policy, and an explanation of duplicate-effect risks. Keep a beginner tutorial focused on a safe working path rather than embedding every configuration option.

## Handoff

Offer the documentation diff and report to `sf-review-change` or `sf-prepare-release`. List external publication work as pending instead of reporting it as completed.
