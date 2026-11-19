---
name: sf-verify-change
description: "Collect and assess current evidence that a specific candidate satisfies its required checks. Use before review, integration, or release, or whenever earlier verification has become stale."
---

# Verify change

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the change set and test plan. Resolve the exact candidate, relevant input digest, and execution environment before using any previous report. Use the specification to resolve expected behavior when supplied. Treat implementation claims as statements to verify.

## Procedure

1. Establish candidate identity, including uncommitted content, configuration, dependencies, and generated inputs that influence results. Confirm the workspace matches that identity. Do not combine results from different candidates into one apparently complete report.
2. Resolve the required checks through the project’s declared verification interfaces or execution adapter. Inspect unfamiliar commands and their effects before running them. Confirm isolation, test data, external access, and cleanup are within the granted scope.
3. Execute focused checks and the required broader suite in an order that gives useful early feedback. Record invocation or operation, timestamps, environment, counts, outcome, and evidence location. Keep sufficient output to explain a failure without exposing credentials or unnecessary private data.
4. Inspect whether the checks actually exercised the intended behavior. Detect empty collections, disabled checks, unexpectedly excluded cases, swallowed failures, and substitutions that remove the relevant integration. A successful process exit does not by itself establish a successful behavioral check.
5. Reproduce a failure once when needed to distinguish a deterministic defect from environmental failure. Preserve both attempts. Do not retry repeatedly until a favorable result appears, or classify an intermittent failure as a pass without an established policy and explanation.
6. Assess every required criterion against the collected evidence. Separate failures, blocked checks, supplementary observations, and gaps. If any source, configuration, or dependency changed during verification, invalidate affected results and return a fresh-run requirement.
7. Emit the report without editing source, weakening tests, publishing, or integrating. Give the next actor a precise failing observation or missing prerequisite rather than an unsupported overall quality score.

## Output

Emit a `verification-report` envelope. Include `candidate_revision`, `check_results`, `criteria_coverage`, `environment`, `executed_count`, `failed_count`, `required_count`, `skipped_required`, `excluded_checks`, `integrity_findings`, and `remaining_risks` in `payload`. Make the counts integers reflecting actual performed checks; list unperformed required check IDs in `skipped_required`. Use stable check and criterion identifiers. Each passed execution check must reference evidence from the declared candidate and environment.

## Completion and failure

Pass only when all required checks have current, substantive passing evidence and the required scope was actually exercised. Return `failed` for an observed violation, `blocked` for a required unavailable runtime or fixture, and `inconclusive` for zero meaningful checks, stale proof, or ambiguous outcomes. Record mixed conditions individually and use the most actionable blocking overall status; never hide a known failure behind a missing environment.

## Example

If a test runner exits successfully after selecting zero cases, report `inconclusive` with the selection details. If local checks pass but a required platform lane is unavailable, retain those results and report the overall verification as `blocked`.

## Handoff

Offer current proof to `sf-review-change` or the workflow’s gate. Return observed defects to `sf-build-change` or `sf-diagnose-defect`; a repaired candidate requires fresh affected evidence.
