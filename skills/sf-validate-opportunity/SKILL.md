---
name: sf-validate-opportunity
description: "Assess whether a proposed outcome addresses a supported need and merits investment. Use before committing to uncertain product work, comparing opportunities, or defining a learning experiment."
---

# Validate opportunity

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the outcome brief and supplied observations about users, demand, incidents, support, adoption, or operating cost. Include project context when it changes feasibility. Do not assume that the existence of a request proves frequency, willingness to adopt, or business value.

## Procedure

1. Identify the decision to support: invest, run a limited experiment, defer, or stop. Record the decision horizon and the people who can commit resources. Avoid producing a broad market study when a narrower uncertainty governs the choice.
2. Inventory evidence by source, observation date, sample, and limitations. Separate observed behavior from interview statements, forecasts, anecdotes, and internal preferences. Note selection bias and missing populations without pretending to correct them mathematically.
3. Describe the causal claim connecting the proposed capability to the desired outcome. Identify assumptions about discoverability, adoption, workflow fit, reliability, and alternatives. Rank the assumptions by how much their failure would change the decision.
4. Compare a small set of realistic options, including improving an existing process or doing nothing where appropriate. Evaluate expected value, delivery and operating cost, opportunity cost, reversibility, and material risks using explicit confidence ranges or qualitative bounds.
5. Design the least costly ethical observation or experiment that can discriminate between the leading options. Define the audience, intervention, success and stop criteria, measurement window, and decision rule before collecting results. Record any consent, privacy, or external communication authorization needed.
6. If results are already supplied, evaluate them against the stated rule. Account for confounders, incomplete follow-up, and effects that only shift work elsewhere. Do not turn a weak signal into a definitive conclusion.
7. Recommend a next decision with its rationale and remaining uncertainty. Keep proposed experiments as plans unless the caller separately authorizes execution and the required capabilities are available.

## Output

Emit an `opportunity-assessment` envelope. Include `decision`, `evidence_inventory`, `causal_assumptions`, `options`, `tradeoffs`, `experiment`, `recommendation`, and `revisit_conditions` in `payload`. Identify which observations support each material conclusion. Distinguish the quality of the assessment from the outcome of any unperformed experiment.

## Completion and failure

Pass when the assessment enables a bounded decision and explains its evidence limits. The recommendation may be “defer” or “run an experiment”; passing does not mean the opportunity has been proven. Return `inconclusive` when the available material cannot support even a useful comparison. Return `blocked` for a required observation that cannot be obtained within the authorized scope. Do not contact users, run experiments, or publish commitments through this skill.

## Example

For a proposed bulk-edit feature, compare repeated support requests with actual task frequency. A small assisted workflow may test whether selection, preview, or execution is the dominant problem before committing to a generalized editor.

## Handoff

Offer supported constraints and learning results to `sf-write-specification`. Return uncertain priorities to the decision owner instead of converting them into implementation tasks.
