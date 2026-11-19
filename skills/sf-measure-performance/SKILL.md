---
name: sf-measure-performance
description: "Measure whether a change satisfies an explicit performance or capacity claim. Use for latency, throughput, resource, scalability, or regression investigations."
---

# Measure performance

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Use the project context and change set to identify the candidate and relevant execution path. Read performance requirements from the specification when supplied. Agree on the user-visible question, workload, acceptable resource cost, and decision threshold before measuring.

## Procedure

1. State a falsifiable claim such as improving a particular latency percentile under a defined workload without increasing error rate. Identify primary metrics, guardrail metrics, baseline, candidate, and the smallest difference that would change the engineering decision.
2. Inspect the measurement harness. Verify that it times the intended work, consumes meaningful outputs, counts failures, and does not optimize away or cache away the operation being studied. Distinguish client queueing, service time, network delay, and downstream work where they matter.
3. Define representative input sizes, data distributions, concurrency, arrival pattern, warm or cold state, and resource limits. Explain which production characteristics are absent. Use safe isolated capacity; a load test against a shared or live environment requires specific authority.
4. Establish comparable baseline and candidate conditions. Record hardware or resource allocation, runtime and dependency versions, configuration, background load, and tuning. Change only the variable under investigation unless the comparison explicitly includes a broader system change.
5. Run repeated measurements with a fixed budget and a justified sample plan. Alternate or randomize baseline and candidate order when drift is plausible. Preserve raw observations, warm-up treatment, correctness checks, errors, and any discarded runs with reasons fixed before inspecting winners.
6. Analyze distributions and variability appropriate to the workload. Report the measured effect alongside uncertainty, saturation, resource consumption, and failure rate. Avoid presenting unstable tail percentiles from tiny samples or extrapolating capacity past an unmeasured bottleneck.
7. Test the interpretation against the original question. Separate microbenchmark improvement from end-user benefit, and consider whether the gain justifies complexity or operating cost. If the evidence is noisy or contradictory, propose the smallest additional experiment rather than extending the run indefinitely.

## Output

Produce a `performance-report` with `payload.claim`, `workload`, `environment`, `method`, `raw_results`, `analysis`, `correctness_checks`, and `decision`. Include commands or harness references, baseline and candidate identities, units, sample counts, and limitations. Make the result reproducible by another operator.

## Completion and boundaries

Pass only when the agreed performance decision is supported and all required guardrails hold. Return failed for an established regression or threshold violation, blocked for unavailable required infrastructure, and inconclusive for insufficient or confounded measurements. Do not select only favorable runs, claim performance from source inspection, or change the acceptance threshold after seeing results.

## Example and handoff

For a queue worker, compare completed correct jobs per unit time and end-to-end delay at the same arrival rate, including retries and resource use. A faster inner loop with growing backlog does not satisfy the claim. Send a supported optimization decision to `sf-review-change`; route unresolved bottlenecks to `sf-diagnose-defect`.
