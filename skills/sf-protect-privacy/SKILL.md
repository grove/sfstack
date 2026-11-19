---
name: sf-protect-privacy
description: "Minimize and govern personal or sensitive data across a feature lifecycle. Use for new data collection, analytics, retention, identity, export, deletion, or data-sharing changes."
---

# Protect privacy

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the project context and specification, plus any supplied design or change set. Identify the applicable organizational policies and responsible decision makers. Treat jurisdictional or contractual requirements as inputs requiring authoritative confirmation when unclear; this assessment does not substitute for a qualified determination.

## Procedure

1. Inventory the data introduced or affected by the feature. Include direct identifiers, sensitive attributes, inferred traits, device or usage identifiers, free text, metadata, and combinations that can identify someone. Track data beyond the primary database into logs, caches, search indexes, exports, analytics, and support tools.
2. Map the data lifecycle: collection, derivation, transfer, use, access, retention, correction, deletion, and recovery from backups. Record the purpose, owner, recipient, and location for each material step. Identify unknown flows rather than assuming they do not exist.
3. Challenge collection and precision against the stated purpose. Consider removing fields, processing locally, shortening retention, aggregating, separating identifiers, or using synthetic data for development. Explain the functional tradeoff of each recommendation.
4. Specify access and separation controls. Cover administrative access, support workflows, cross-tenant visibility, service credentials, exports, and third-party transfer. Distinguish pseudonymization from anonymity and identify linkage paths that remain possible.
5. Describe how users or operators can inspect, correct, export, restrict, or delete data when those obligations apply. Include propagation, derived records, queued work, legal holds, backup treatment, and verification of completion. Do not promise immediate physical erasure where the storage design cannot provide it.
6. Define notice, choice, and consent behavior where required by the supplied policy. Separate a product preference from a legal requirement. Escalate unresolved policy decisions to a named responsible role with precise questions and decision deadlines.
7. Create acceptance checks for the risky lifecycle paths, including log redaction, access denial, retention expiry, deletion propagation, and restored-data handling. Identify the evidence needed to show each control works without collecting further unnecessary personal data.

## Output

Produce a `privacy-assessment` containing `payload.data_inventory`, `data_flows`, `purposes`, `minimization_decisions`, `access_controls`, `retention_and_deletion`, `open_policy_questions`, and `acceptance_checks`. Use categories and synthetic examples in the report; avoid copying raw personal data into evidence.

## Completion and boundaries

Pass the design assessment when the lifecycle and decisions are explicit and unresolved obligations have owners. A passed plan does not prove implemented controls or legal compliance. Return blocked when a required policy decision prevents a defensible design. Do not alter retention, disclose data, or delete records under this skill; route those changes through implementation and operational authorization.

## Example and handoff

For product analytics, document why an event needs an account identifier, whether aggregate counts suffice, how long linkage is retained, and how account deletion reaches the event store. Hand concrete requirements to `sf-write-specification`; use `sf-verify-change` to establish implemented behavior.
