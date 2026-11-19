---
name: sf-improve-process
description: "Turn observed delivery problems into testable process improvements. Use for a retrospective, recurring defect, handoff failure, slow workflow, or corrective action review."
---

# Improve process

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the improvement request and available incident, evaluation, or review artifacts. Establish the affected workflow, observation period, intended outcomes, and scope for proposed changes. Use raw examples and records where possible; distinguish observations from participants' interpretations.

## Procedure

1. Define the problem in observable terms: escaped defects, repeated rework, delayed decisions, unreliable handoffs, excessive execution cost, or a missed user outcome. Identify who is affected and how often. Avoid substituting activity counts or agent verbosity for delivered value.
2. Reconstruct several representative examples, including a successful comparison when available. Record the triggering conditions, available information, decisions, actions, and results. Separate an individual mistake from a recurring mechanism and state uncertainty when the sample is small.
3. Identify the weakest control or feedback loop that allowed the outcome. Examine unclear contracts, missing evidence, wrong abstraction, delayed verification, hidden permissions, stale context, and impractical incentives. Do not default to adding another instruction when the system can enforce a clearer invariant.
4. Propose a small set of interventions and compare expected benefit, cost, adoption effort, failure modes, and reversibility. Consider simplifying the workflow, improving interfaces, adding executable checks, strengthening types or schema constraints, changing ownership, or removing a step that provides no demonstrated value.
5. Choose the smallest trial that can discriminate whether the intervention works. Define baseline, success and guardrail measures, trial scope, duration, owner, and the evidence that would justify keeping, revising, or reverting it. Record these criteria before inspecting trial results.
6. Translate the trial into actionable work with acceptance criteria and a follow-up date. Keep skill edits, policy changes, tracker publication, and external communication as separately authorized implementation actions. Do not silently rewrite the operating rules of an active run.
7. Review supplied trial evidence against the original criteria. Attribute results cautiously when workload, staffing, or tools changed. Retain useful improvements, revise uncertain ones, and remove changes that increased overhead without improving the intended outcome. Preserve rejected alternatives and why they were rejected.

## Output

Produce an `improvement-plan` with `payload.problem`, `examples`, `causal_hypotheses`, `options`, `selected_trial`, `measures`, `owner`, `follow_up`, and `decision_rules`. If trial results are already available, add `trial_results` and `recommendation`. Tie each proposed action to a specific failure mechanism and expected effect.

## Completion and boundaries

Pass the planning or review activity when another owner can run or assess the trial without inventing missing criteria. Use inconclusive for unsupported causal claims and blocked for missing decision ownership or essential evidence. Do not promise improvement before testing, create a skill for every anecdote, or conflate agreement among reviewers with measured effectiveness.

## Example and handoff

If verification repeatedly targets an outdated revision, trial automatic evidence invalidation when the candidate changes, then measure stale-evidence escapes and added delay. A reminder alone may not address the mechanism. Hand the bounded change to `sf-plan-work`; use `sf-evaluate-skills` when the intervention changes agent instructions or workflow composition.
