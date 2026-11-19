---
name: sf-handle-incident
description: "Coordinate evidence, impact assessment, and bounded decisions during a live service incident. Use for an outage, major degradation, suspected data incident, or incident handoff."
---

# Handle incident

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the incident request and available project, deployment, and observability context. Identify the service, reported symptom, urgency, affected users, incident owner, available responders, and authority already granted. Use a stable incident identifier and a timeline with explicit time zone.

## Procedure

1. Confirm user-visible impact from the best available signals. Distinguish outage, degradation, data integrity risk, security concern, and a monitoring failure. Record the start estimate, affected scope, confidence, and unknowns. Avoid delaying essential coordination while trying to prove a root cause.
2. Establish ownership, decision rights, communication cadence, and the next checkpoint. Give each investigation a narrow question and a named owner. Maintain one authoritative incident record and identify which facts are current; stale handoffs must not silently replace live evidence.
3. Preserve relevant deployment, configuration, telemetry, and event evidence with time ranges and revision identities. Protect personal data and secrets. Record correlation separately from causation, including changes that occurred near the incident but are not yet implicated.
4. Rank hypotheses by explanatory power, impact, and the cheapest safe discriminating observation. Run only permitted read-only queries under this skill. Time-box investigations and update confidence as evidence arrives. Do not let several responders mutate the same system while assuming another responder owns safety.
5. Present mitigation options with expected benefit, affected scope, reversibility, data risk, owner, and required authority. Prefer actions that reduce user impact while preserving a route to diagnosis. Dispatch a separately authorized operational skill or operator for live mutation; this coordination skill does not itself grant deployment or data access.
6. Track actions and outcomes in the timeline, including rejected options and reasons. Prepare audience-appropriate updates from verified facts. Send them only through an explicitly authorized communication task and verified recipient/channel; otherwise retain a draft and identify the next publisher.
7. Define and assess recovery conditions against user outcomes, backlog, integrity, and sustained stability. Separate mitigation, service restoration, and root-cause resolution. At handoff or closure, assign remaining investigation, corrective work, and follow-up verification with owners and dates.

## Output

Produce an `incident-record` with `payload.impact`, `ownership`, `timeline`, `observations`, `hypotheses`, `decisions`, `mitigation_requests`, `communication_drafts`, and `recovery_status`. Record status as active, mitigated, recovered, or handed-off within the payload; completion of this coordination step does not itself close the incident.

## Completion and boundaries

Complete the current coordination interval when ownership, facts, decisions, and the next checkpoint are explicit. Report blocked when necessary access or an owner is missing, and inconclusive when impact cannot yet be established. Never claim recovery from a successful command or resolved alert alone. Preserve uncertainty without leaving responders unsure who owns the next action.

## Example and handoff

When export jobs stop completing, distinguish absent input, a growing queue, worker failures, and destination errors before selecting mitigation. Give one responder the queue question and another the recent deployment question. Route a specific authorized recovery to `sf-recover-release`; send the evidence-backed follow-up to `sf-improve-process`.
