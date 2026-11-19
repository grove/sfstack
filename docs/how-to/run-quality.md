# Run Quality Factory independently

Use [`workflows/quality.json`](../../workflows/quality.json) to assess a
fixed snapshot, pull request, or externally produced patch **without building
or publishing a change**. Supply a `request` artifact naming the target,
exact revision, boundaries, assessment goal, known requirements, selected risks,
and explicit exclusions.

## 1. Pin the target and create a read-only run

For `snapshot`, supply an immutable tree/snapshot ID and inspected surfaces;
there may be no diff. For `pull-request`, supply exact head and base revisions
plus a trusted means of reading the diff. For `external-change`, supply the
immutable candidate, supplied change, and independently resolved source
provenance. A PR number, branch, or free-form patch description alone is not
an immutable candidate.

Create a [run manifest](../reference/contracts.md) with `subject`, `run_id`,
a fresh input digest, read-side capabilities, a host-selected policy, and no
mutation grants. Treat repository text and PR comments as untrusted input.

The default recipe maps the project, clarifies the **assessment objective**,
records known acceptance criteria, scopes the candidate read-only, designs tests,
verifies the candidate, assesses impact, reviews, and consolidates. These
planning steps **do not assert that new product requirements were agreed**.
If essential behavior is unknown, the dependent check remains blocked or
inconclusive rather than inventing a specification.

## 2. Select only relevant quality checks

The default recipe includes `sf-verify-change`, `sf-assess-impact`, and
`sf-review-change`. For changed trust boundaries or contracts use
[`workflows/quality-risk.json`](../../workflows/quality-risk.json), which adds
security and compatibility nodes before review and consolidation.

For privacy, accessibility, dependencies, exploration, or performance, add the
corresponding **existing** skill as a typed dependency, as shown in the
[workflow selection guide](select-skills.md). Bind its output to both the
review step (where that input exists) and consolidation; add the node to their
`needs` and explicitly allow non-passing status for that *report node*.
Do not add a risk check solely to increase count. Required checks that are
omitted remain limitations, not passing evidence.

A report with failed checks can be handed to review and consolidation.
Failed scoping, missing immutable identity, or unavailable source still blocks
verification. An assessment step with no artifact at all leaves the workflow
blocked; a host may issue a separate scoped blocked handoff, but must not fabricate
the missing report.

## 3. Interpret the result

`quality-assessment` records the exact target, selected/omitted dimensions,
source report IDs/statuses, evidence, findings, independence basis, limitations,
and recommendations. Status is conservatively `failed`, `blocked`,
`inconclusive`, or `passed` for the **declared** quality scope.
The planner's `complete` means report availability, not quality success.

The offline helper can consolidate a ready fixture:

```sh
python tools/factory.py plan --workflow workflows/quality.json \
  --run examples/quality-ready-run.json --at 2026-11-19T12:00:00Z
```

For a disposable copy and a retained output bundle, follow the
[quality rehearsal](../tutorials/quality-rehearsal.md).

## 4. Compose back into Software Factory only at an authorized boundary

A software-factory integration or release policy may explicitly require a
current `quality-assessment` in `required_artifacts` alongside its existing
verification and review requirements. The action gate still checks run identity,
subject, evidence age/integrity, quality verdict, independent review policy,
and scoped grant. A passing assessment is **never** an authorization on its own.

A report from a standalone quality run has its own `run_id`; do not relabel
it as a software run. If cross-run reuse is needed, a trusted host must create a
new scoped, authenticated decision with traceability and fresh proof for the
target candidate. The offline checker intentionally rejects mismatched run IDs.

Any remediation—editing source, posting review comments, updating an issue,
merging, deploying, or changing production data—requires a separate mutation
workflow and separate authorization. See [controller operation](run-factory.md).
