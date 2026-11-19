---
name: sf-explore-behavior
description: "Explore a running candidate through realistic paths to discover unanticipated defects. Use for exploratory quality assurance, integration uncertainty, or behavior that predetermined checks do not cover adequately."
---

# Explore behavior

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the change set, specification, and any existing test plan. Identify the real interaction surface: interface, command, service boundary, event stream, background process, or combination. Exploration is not limited to browser-based products.

## Procedure

1. Fix the candidate, environment, allowed data, and mutation boundaries. Confirm how to start, access, observe, and clean up the surface. Use isolated synthetic identities and data when possible; do not explore destructive paths against shared systems without explicit authorization.
2. Select a few risk-based charters. Each charter states a user or system goal, relevant constraints, likely failure modes, and a time or action budget. Prioritize changed behavior, handoffs between components, and gaps left by predetermined tests.
3. Exercise a normal path through the actual supported interface. Observe both the immediate response and meaningful downstream effects. Record enough context to distinguish a failure in the candidate from a broken fixture, missing dependency, or misunderstood requirement.
4. Vary state, order, timing, repetition, invalid input, interruptions, and recovery where they challenge the charter. Include realistic combinations rather than only isolated field checks. Preserve the chronology of important observations instead of relying on a final screenshot or a remembered description.
5. Reproduce suspected defects once with minimized, faithful steps. Compare expected and actual results against the specification. Record severity through user impact, not visual drama or certainty of cause. Keep uncertain observations separate from established defects.
6. Stop at the declared budget, a consequential safety boundary, or a blocker that prevents further useful exploration. Clean up authorized test artifacts and verify cleanup. If a defect suggests a new charter, identify it explicitly instead of allowing unbounded scope growth.
7. Summarize exercised and untouched behavior, reproducible findings, and candidates for durable regression checks. Do not modify the source during this skill; changing the candidate would make prior observations refer to a different subject.

## Output

Emit an `exploration-report` envelope with `payload` fields `candidate_revision`, `environment`, `charters`, `sessions`, `coverage`, `findings`, `regression_candidates`, `cleanup`, and `unexplored_risks`. Each finding includes a stable identifier, expected and actual behavior, impact, reproduction steps, evidence, and confidence. Redact personal data and secrets from recordings while preserving diagnostic value.

## Completion and failure

Pass when the agreed charters were meaningfully exercised without unresolved behavior violations, within the stated scope. This is not proof that no defects exist. Return `failed` for an observed violation, `blocked` when the relevant surface cannot be exercised, and `inconclusive` when evidence is too ambiguous. Report skipped charters explicitly and do not describe a launch-only check as completed exploration.

## Example

For an export feature, begin an export, reconnect during processing, cancel near completion, retry after a timeout, and inspect the resulting file and job state. A successful download alone does not establish all lifecycle behavior.

## Handoff

Offer reproducible defects to `sf-diagnose-defect` or `sf-build-change`. Offer stable behavioral discoveries to `sf-design-tests`, preserving the distinction between exploration evidence and automated coverage.
