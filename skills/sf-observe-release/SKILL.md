---
name: sf-observe-release
description: "Assess a deployed revision against user outcomes and operational thresholds during a bounded observation window. Use after rollout or when validating a release canary."
---

# Observe release

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the deployment record and resolve the exact target and observed revision. Use the release and observability plans when supplied. Establish the required journeys, operational indicators, baseline, thresholds, observation window, sampling cadence, and decision owner before starting.

## Procedure

1. Verify that observations can be attributed to the intended revision and environment. Detect mixed versions, incomplete rollout, configuration drift, and traffic not reaching the new release. If attribution is impossible, record the limitation before interpreting a healthy service response.
2. Obtain a meaningful baseline from a comparable pre-release period, control group, or known-good target. Record seasonality, load, data volume, dependency changes, and other confounders. A snapshot taken only after deployment is a starting observation, not a pre-release baseline.
3. Observe critical user outcomes using the allowed read-only or pre-authorized synthetic paths. Check expected results and side effects through existing telemetry. Do not create real customer activity, send messages, charge accounts, or mutate production data merely to test the release.
4. Collect required indicators over the defined window: successful outcomes, errors, delay, queue age, saturation, integrity signals, and relevant access or compatibility failures. Keep absent, delayed, and malformed telemetry distinct from a measured zero.
5. Compare observations with the plan's absolute limits, relative changes, and persistence requirements. Avoid changing thresholds after a concerning result. Investigate ambiguous signals using the smallest additional read and preserve uncertainty when a causal claim is not supported.
6. Stop at the time budget, a confirmed abort condition, loss of visibility, or the planned decision point. Use the configured notification or incident process only when authorized; otherwise create a precise handoff with the affected target, evidence, consequence, and proposed next action.
7. Produce a verdict for the observed stage: acceptable, degraded, failed, or unverified. Explain whether the evidence supports expanding rollout, holding, investigating, or recovering. Make continuing observation an explicit assignment with an owner and end condition rather than an unbounded background promise.

## Output

Produce a `release-observation` containing `payload.target`, `revision`, `observation_window`, `baseline`, `indicator_results`, `journey_results`, `verdict`, and `recommended_action`. Link raw telemetry queries or snapshots and record their time ranges. Distinguish stage acceptance from final release acceptance.

## Completion and boundaries

Pass only when the required observation window and criteria are satisfied for the intended revision. Return failed for established threshold or functional violations, blocked for required inaccessible telemetry, and inconclusive for uncertain identity or insufficient samples. A quiet interval does not prove the absence of rare failures. This skill observes and recommends; it does not expand rollout, roll back, or change thresholds.

## Example and handoff

After deploying a notification worker, confirm that new-version workers complete authorized synthetic jobs and that real queue age and error rates remain within limits. If the queue is empty, disclose that throughput behavior was not exercised. Hand a supported acceptance decision to the release owner, or route an observed regression to `sf-handle-incident` and authorized recovery.
