---
name: sf-model-domain
description: "Define shared domain language, rules, states, and ownership boundaries. Use when terminology conflicts, business invariants are unclear, or a change crosses conceptual boundaries."
---

# Model domain

Apply the [execution protocol](references/protocol.md) before starting. Use [the contract](contract.json) for capability discovery and machine-readable inputs and outputs.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the outcome brief, concrete scenarios, and available project context. Use existing language from practitioners and system behavior. Treat identifiers in code or storage as evidence of current implementation, not automatically as the correct domain vocabulary.

## Procedure

1. Choose a bounded domain area and collect representative scenarios. Identify actors, decisions, relevant events, and the things whose identity or lifecycle matters. Include at least one exceptional or disputed scenario.
2. Define terms using recognizable domain concepts. Separate synonyms from genuinely different meanings. Where teams or contexts use the same word differently, retain explicit scoped meanings rather than forcing a misleading universal definition.
3. Describe identity and ownership: what makes two instances the same thing, which component or actor may change state, and what information is authoritative. Keep implementation mechanisms out of the glossary unless the mechanism itself is part of the domain contract.
4. State invariants, permitted transitions, and invalid combinations. Identify what must be true immediately, what may become true later, and how a failure or reversal affects the business state. Make temporal rules and concurrent actions explicit when they matter.
5. Walk the scenarios through the model. Try boundary cases such as duplicate requests, cancellation during completion, expired authority, and delayed information. Resolve contradictions with evidence or a named decision owner, not with convenient new terminology.
6. Identify boundaries where meanings, rules, or ownership change. Record translations at those boundaries and the information that may be lost. Avoid prescribing a service, database, or class for every concept.
7. Capture only consequential decisions with alternatives and reasons. Produce a model small enough to use during specification and review; leave uncertain parts marked rather than padding them with speculation.

## Output

Emit a `domain-model` envelope with `payload` fields `scope`, `glossary`, `actors`, `concepts`, `invariants`, `state_transitions`, `boundaries`, `scenario_walkthroughs`, and `decisions`. Give important rules stable identifiers that specifications and tests can reference. A diagram may supplement the model, but include the rules in accessible text so that meaning does not depend on a renderer.

## Completion and failure

Pass when the selected scenarios can be described consistently and consequential ambiguities have explicit dispositions. Return `blocked` when a required business rule has no authorized answer, or `inconclusive` when competing interpretations remain equally supported. Do not silently change a rule to match current code or claim that a conceptual model proves the implementation conforms.

## Example

For reservation cancellation, distinguish “requested,” “accepted,” “released,” and “refunded” if those events have different owners or timing. Define what happens when confirmation and cancellation arrive concurrently before selecting storage or messaging mechanisms.

## Handoff

Offer the model to `sf-write-specification` and `sf-design-solution`. Supply unresolved business questions to their owners; keep vocabulary changes traceable through later acceptance criteria.
