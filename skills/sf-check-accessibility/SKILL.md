---
name: sf-check-accessibility
description: "Assess whether people with differing access needs can complete the changed journeys. Use before releasing an interface or when investigating an accessibility defect."
---

# Check accessibility

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Use the specification to identify tasks and applicable accessibility requirements. Use the change set to pin the candidate and affected interfaces. Read any experience design and project context. Resolve the required standard, version, platform, and assessment scope from project policy; do not infer a legal compliance obligation.

## Procedure

1. Map changed journeys to access needs: perceiving content, navigating, entering information, understanding feedback, and recovering from errors. Include users relying on keyboard input, assistive technology, magnification, reduced motion, or alternate interaction methods where relevant.
2. Establish a reproducible test environment and representative data. Record platform, rendering environment, assistive tools, configuration, and candidate revision. Use isolated accounts and safe actions. Distinguish a runnable interface from a static design assessment.
3. Run available automated checks and inspect their coverage. Preserve rule identifiers and evidence, then verify each material finding in context. A clean scanner result is one observation, not proof that all users can complete the journey.
4. Exercise full tasks manually with applicable alternate input and output modes. Check focus order and restoration, programmatic names and relationships, announcements, status updates, error association, nonvisual completion, and escape from modal or time-limited states.
5. Assess presentation under relevant variations: zoom, reflow, text spacing, high contrast, reduced motion, long text, orientation, and translation. Check that essential meaning does not depend solely on color, sound, position, or a transient visual change.
6. For each finding, record the affected task and user need, expected behavior, actual behavior, reproduction steps, supporting evidence, and severity based on blocked or degraded use. Distinguish an observed failure from a suspected risk requiring a particular device or assistive tool.
7. Recheck repaired behavior on the new candidate only when a repair has been supplied. Repeat the original path and one adjacent state. Limit this assessment to one recheck cycle unless the execution budget explicitly allows more.

## Output

Produce an `accessibility-report` with `payload.scope`, `requirements`, `environment`, `journey_results`, `findings`, `coverage_gaps`, and `recheck_results`. Include the assessment date and the exact candidate. Give practical acceptance conditions for each repair; keep automated and manual evidence distinct.

## Completion and boundaries

Return failed for demonstrated violations of required criteria. Return blocked when a required environment cannot be accessed, or inconclusive when evidence cannot support the requested claim. A scoped passed result applies only to the declared journeys, modes, and criteria. Do not label an entire product compliant from a sampled review. This skill assesses and rechecks; source repairs belong to a separately authorized implementation task.

## Example and handoff

For a new date picker, test opening it, selecting a date, correcting an invalid value, and returning focus without a pointer. If an assistive mode is unavailable, preserve that gap even when automated checks pass. Send reproducible findings to `sf-build-change` and include the report in `sf-review-change`.
