---
name: sf-consolidate-quality
description: "Consolidate verification, code review and risk-based assessments for an existing or externally produced candidate. Use when a quality-only workflow needs a single evidence-backed verdict without remediation."
---

# Consolidate quality

Apply the [execution protocol](references/protocol.md) and [contract](contract.json).
Validate JSON against the [bundled artifact schema](references/artifact.schema.json).
An integrated host also validates the optional sfstack quality payload extension;
the standalone skill never requires repository-root files.

## Inputs

Read the fixed change-set, verification-report, review-report, and any requested
impact or specialist reports. These may be **failed**, **blocked**, or
**inconclusive**: they are observations to consolidate, not assertions of success.
Inspect the actual report subjects, provenance, status, evidence references,
limitations, and reviewer/author identities. Do not infer independent review
from two prompts or worker role labels.

## Procedure

1. Fix the assessment scope and exact subject from the execution context.
   Reject contradictory revisions, environments, or material input digests.
2. Enumerate the required quality dimensions from the request, applicable host
   policy, and selected workflow. Required dimensions without reports remain
   blocked or inconclusive; unselected dimensions are marked `not assessed`,
   never `passed`. An absent optional report is not a clearance.
3. For each report, retain its immutable identity, status, evidence locations,
   and check IDs. Record each material finding with a stable ID, source report,
   severity, blocking decision, disposition, mechanism/impact, and evidence.
   Distinguish confirmed failure from suspected risk and accepted risk from a
   fix. Never silently discard negative findings.
4. Verify independent-review metadata against host-supplied provenance. If
   independence was required but cannot be established, disclose the gap and do
   not claim an independent pass. Do not manufacture approvals.
5. Compute the verdict conservatively for required dimensions:
   `failed` when any observed required violation or unresolved blocking finding
   exists; otherwise `blocked` when required access, check, or report is missing;
   otherwise `inconclusive` for ambiguous or insufficient proof; only then
   `passed` if all applicable required checks have substantive, current evidence.
   Explicitly mark coverage limits even for a scoped pass.
6. Emit a `quality-assessment` envelope with `payload.target`,
   `reports`, `coverage`, `findings`, `limitations`,
   `independence`, `recommendations`, and
   `remediation_authorized: false`. Link every report/finding to retained
   evidence records; use `payload` for source-specific detail.
7. Recommend the next distinct action but do **not** edit code, create comments,
   publish a review, open a ticket, waive a gate, merge, or deploy.

## Completion and failure

The assessment's status is the **quality verdict**, not the successful execution
of an aggregation step. A failed report must not become a passing assessment
merely because consolidation completed. A `passed` result means *this
assessment's specified scope* is supported by current evidence; it does not
promise overall system correctness. Report all untested dimensions and unknown
source provenance. Use a new scoped, authorized workflow for remediation.

## Handoff

The quality-assessment can be consumed by a software-factory gate after the
host verifies the same subject/run and the relevant policy. It never grants an
external effect on its own.
