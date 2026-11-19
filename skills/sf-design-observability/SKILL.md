---
name: sf-design-observability
description: "Define how operators will detect, explain, and respond to service behavior. Use for new services, changed failure modes, service objectives, alert gaps, or incident follow-up."
---

# Design observability

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the project context and specification. Include a solution design or incident record when supplied. Establish service ownership, user-visible outcomes, existing service objectives, and the operational constraints on telemetry volume, cost, retention, and access.

## Procedure

1. Map critical user outcomes to the system paths that deliver them. Identify failure, delay, corruption, partial success, and silent omission. Include asynchronous work and external dependencies so that a healthy entry point cannot hide a failing downstream outcome.
2. Define service indicators with precise numerator, denominator, measurement point, units, dimensions, and exclusions. Identify where absence of data is itself a fault. Choose objectives and evaluation windows from the supplied policy or record them as proposals awaiting an owner.
3. Design the minimum instrumentation needed to distinguish causes. Specify meaningful events, counters, distributions, correlation identifiers, and traces at ownership or trust boundaries. Control cardinality, sampling, and overhead. Avoid personal data and secrets in telemetry unless a specific approved purpose requires them.
4. Define alert conditions around actionable impact and time to respond. Include persistence windows, severity, routing, deduplication, maintenance handling, and what distinguishes a symptom from a noisy proxy. Pair every alert with an owner and a concrete first action.
5. Describe investigation views that let an operator move from a user symptom to affected versions, regions, tenants or other permitted cohorts, queues, and dependencies. Make the deployed revision and configuration observable without exposing credentials or sensitive values.
6. Plan validation by inducing representative failures in an authorized test environment. Specify the expected signal, alert timing, evidence, recovery indication, and missing-data behavior. Include a way to verify that monitoring itself still works and that an alert reaches its intended destination through an approved test.
7. Define deployment observation and incident handoff. State release baselines, abort thresholds, monitoring duration, and the evidence needed to declare recovery. Assign runbook maintenance and review dates rather than leaving dashboards without operational ownership.

## Output

Produce an `observability-plan` with `payload.outcomes`, `indicators`, `instrumentation`, `alerts`, `investigation_views`, `validation_plan`, and `ownership`. Give each indicator and alert a stable identifier. Record proposed thresholds separately from approved objectives and measured baselines.

## Completion and boundaries

Pass the planning activity when the important failure modes have a detection and response path and the design has a practical validation plan. A complete plan does not prove that instrumentation, alerts, or delivery channels work. Return blocked when critical ownership or measurement points cannot be established. Do not create alerts, send test notifications, or change production sampling without a separate authorized implementation or operational step.

## Example and handoff

For a scheduled export service, observe successful delivery by its due time, not merely the scheduler's heartbeat. Include queued age, terminal failures, destination errors, and evidence that a particular release completed the export. Hand instrumentation to `sf-build-change`, validation to `sf-verify-change`, and release thresholds to `sf-observe-release`.
