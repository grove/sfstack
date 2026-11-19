---
name: sf-diagnose-defect
description: "Establish a defect mechanism through a faithful reproduction and discriminating experiments. Use for unexpected behavior, regressions, intermittent failures, or unclear operational symptoms before choosing a fix."
---

# Diagnose defect

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the reported symptom and project context. Gather expected behavior, timing, affected population, relevant configuration, and recent changes from supplied evidence. A proposed cause is a hypothesis until an observation distinguishes it from alternatives.

## Procedure

1. Define the observable discrepancy and its impact. Preserve original evidence before changing the environment. Separate immediate incident containment from diagnosis; consequential production actions belong to an authorized incident workflow.
2. Establish the smallest faithful reproduction available within the allowed environment. Capture the exact invocation, inputs, candidate, configuration, and observed result. For intermittent failures, record the attempt count and occurrence rate; a single successful retry does not disprove the report.
3. Verify that the reproduction exercises the affected path. Reduce irrelevant setup without removing timing, state, concurrency, or external behavior that may cause the symptom. If no faithful reproduction is possible, describe the missing observation rather than substituting an easier unrelated failure.
4. Form a small set of plausible mechanisms and state what observation would support or contradict each. Include at least one alternative explanation for the leading hypothesis. Prioritize experiments by information gained and risk, not by convenience of the likely fix.
5. Run one discriminating experiment at a time in isolated, authorized conditions. Use temporary evidence artifacts for probes; do not alter production source or shared data as a diagnostic shortcut. Record the changed variable, result, and effect on each hypothesis.
6. Stop after the supplied budget or two unsuccessful hypothesis rounds. When a mechanism is established, trace why the existing safeguards missed it and identify the narrowest responsible boundary. Avoid turning one defect into an unsupported redesign.
7. Propose a repair direction and a regression check that would fail for the observed mechanism. Preserve reproduction instructions, rejected explanations, and uncertainty so a builder can continue without repeating the investigation.

## Output

Emit a `diagnosis` envelope with `payload` fields `symptom`, `expected_behavior`, `reproduction`, `observations`, `hypotheses`, `experiments`, `causal_mechanism`, `repair_direction`, and `regression_check`. Identify which claims are observed, inferred, or unresolved. Include the environment and revision for each experiment, especially when comparing versions.

## Completion and failure

Pass when evidence supports a mechanism that explains the reported symptom and suggests a testable repair. Return `inconclusive` when reproduction or discrimination remains insufficient; list the next observation that would change the conclusion. Return `blocked` for inaccessible required environments or unsafe experiments. Do not report a guessed cause as established because a speculative patch appears to help.

## Example

For records occasionally disappearing after an update, distinguish stale reads, overwritten writes, and incomplete persistence with controlled versions and observations. Repeating the request until it succeeds does not identify which mechanism occurred.

## Handoff

Offer the diagnosis to `sf-build-change` with the relevant specification and work item. Escalate active service impact to `sf-handle-incident` through the caller’s authorized workflow.
