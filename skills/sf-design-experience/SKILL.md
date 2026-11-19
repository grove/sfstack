---
name: sf-design-experience
description: "Design coherent user journeys, interaction states, and presentation rules. Use for a new or changed interface, a usability problem, or a product experience proposal."
---

# Design experience

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Use the outcome brief to identify users, their circumstances, and the task they need to complete. Read the specification and existing experience conventions when supplied. Separate established requirements from assumptions that still need user research.

## Procedure

1. Select the critical journeys and define observable success for each. Include the entry point, information required, decision moments, completion, and recovery. Prioritize frequency and consequence rather than the number of screens.
2. Inspect the existing interaction vocabulary and constraints. Identify what should remain familiar and where a change is justified. Consider device, input method, interruption, connection quality, language, and access needs without assuming a particular interface technology.
3. Produce two materially different interaction approaches when a consequential decision remains. Compare their cognitive effort, error likelihood, implementation cost, and ability to support the core task. Choose with explicit reasons; do not manufacture alternatives for settled details.
4. Describe the selected journey as states and transitions. Cover normal, empty, partial, loading, denied, failed, cancelled, and completed states where relevant. Specify which information survives interruptions and how users recover safely.
5. Define a small set of reusable presentation and content rules: hierarchy, emphasis, spacing relationships, naming, feedback timing, and destructive-action treatment. Reuse the project's design system when present; record deliberate exceptions. Avoid encoding arbitrary aesthetic preferences as universal quality rules.
6. Make the proposal inspectable using the available medium: annotated sketch, textual interaction model, clickable prototype, or sample conversation. Use representative content and realistic long, missing, and localized values. Mark simulated behavior explicitly.
7. Define a validation exercise for the riskiest assumptions. State participant characteristics, tasks, observations, success measures, and what would change the design. Report actual observations separately from predicted outcomes.

## Output

Produce an `experience-design` artifact with `payload.journeys`, `states`, `presentation_rules`, `content_examples`, `alternatives`, `decisions`, and `validation_plan`. Link each major decision to an outcome or observed constraint. Identify unresolved questions with an owner and the next evidence needed.

## Completion and boundaries

Pass the design activity when a reader can follow the key tasks, inspect failure recovery, and assess the remaining assumptions. A complete proposal does not establish usability or accessibility compliance. Record unavailable research or prototype execution as a limitation; do not invent feedback. Do not change product requirements, implement source changes, or publish a prototype without a separate scoped task.

## Example and handoff

For a bulk-import experience, show how a user previews invalid rows, corrects a subset, resumes an interrupted upload, and distinguishes accepted from pending items. A single successful upload screen is insufficient. Hand the approved interaction decisions to `sf-write-specification` or `sf-build-change`; use `sf-check-accessibility` for an evidence-based access assessment.
