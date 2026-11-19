---
name: sf-design-tests
description: "Design proportionate behavioral checks that can distinguish a correct change from plausible defects. Use when defining verification for a specification, improving weak coverage, or choosing test seams and environments."
---

# Design tests

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the specification and any supplied project context or candidate change. Identify existing tests and verification constraints from those artifacts. The goal is a useful verification plan, not a fixed ratio of test categories or a requirement to test every private function.

Read any supplied specialist reports declared by the contract. Carry relevant constraints and unresolved findings into this result; do not treat an absent report as a passed specialist check. If policy requires a report and it is missing or stale, block the dependent conclusion.

## Procedure

1. Map acceptance criteria and important risks to observable behavior. Include negative paths and boundary conditions that could produce a plausible but incorrect implementation. Give priority to consequential failures and recently changed assumptions.
2. Choose a verification seam for each claim: an exposed interface, an integration boundary, a user-visible flow, a persisted result, or an operational signal. Use a lower-cost seam when it preserves the claim; use the real boundary when substitution would hide the relevant defect.
3. Define independent expected results. Derive values from the specification, a simple trusted reference, or an explicit invariant. Do not calculate expected output with the same helper, algorithm, or fixture transformation being tested.
4. Design a small discriminating case set. Cover valid behavior, invalid input, state transitions, repetition, and partial failure as applicable. Add concurrency, property, load, or compatibility checks only where they test a real obligation.
5. Specify setup, inputs, required capabilities, isolation, cleanup, and environmental assumptions. Use controlled data and stable observations. Identify external services that must be real, may be substituted, or prevent the check from running in a given environment.
6. Define evidence and pass criteria for each check before execution. Record what a check proves and what it cannot prove. Plan a negative control, known failing version, or deliberate faulty variant when it is practical to demonstrate that an important check can fail for the intended reason.
7. Review for redundant checks, brittle coupling, and blind spots. Separate required checks from supplementary exploration. Document justified exclusions and the owner of unresolved verification gaps rather than silently treating them as covered.

## Output

Emit a `test-plan` envelope with `payload` fields `criteria_map`, `checks`, `environments`, `fixtures`, `isolation`, `cleanup`, `evidence_requirements`, and `coverage_gaps`. Each check includes `id`, `criterion_ids`, `purpose`, `inputs`, `expected_observation`, `method`, `environment`, `required`, and `limitations`. Describe commands only when the project has supplied or verified them; otherwise describe the adapter operation to resolve.

## Completion and failure

Pass when the plan provides a feasible and discriminating way to assess the required behavior. Passing the plan says nothing about the implementation’s correctness. Return `blocked` for undefined acceptance behavior or unavailable required prerequisites, and `inconclusive` when the selected seams cannot observe a material risk. Do not claim coverage solely because a file contains a test or a percentage meets a threshold.

## Example

For a retry limit, check the final user-visible failure, the maximum observable attempts, and successful recovery before the limit. A test that copies the configured limit into its own expected result cannot detect the wrong requirement value.

## Handoff

Offer the plan to `sf-build-change` for focused checks and `sf-verify-change` for evidence collection. Use `sf-explore-behavior` to investigate risks not well represented by predetermined cases.
