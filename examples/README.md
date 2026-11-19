# Synthetic integration examples

These files demonstrate sfstack's contracts and offline tools. They describe a
fictional display-name change. They are not records of real tests, reviews,
authorization, integration, or deployment.

Use the fixed time `2026-11-19T12:00:00Z` when reproducing the fixtures. Their grant
expiry and evidence age are deliberate. Never backdate a live decision to reuse
these example grants.

| Example | Purpose |
| --- | --- |
| [invocation-context.json](invocation-context.json) | Planning-only task context for the invocation renderer. |
| [quality-run.json](quality-run.json) | Initial read-only Quality Factory checkpoint. |
| [quality-ready-run.json](quality-ready-run.json) | Synthetic reports ready for consolidation. |
| [quality-failed-run.json](quality-failed-run.json) | Negative verification and blocking review finding retained. |
| [quality-risk-ready-run.json](quality-risk-ready-run.json) | Explicit security and compatibility assessments. |
| [quality-pr-ready-run.json](quality-pr-ready-run.json) | Externally produced PR head/base for read-only evaluation. |
| [feature-run.json](feature-run.json) | Initial feature checkpoint with only `orient` ready. |
| [policy.json](policy.json) | Illustrative exact-scope grants and evidence requirements. |
| [gate-request.json](gate-request.json) | An integration request consistent with its synthetic proof. |
| [gate-stale-request.json](gate-stale-request.json) | The same gate with a changed candidate, intentionally blocked. |
| [tracker-mapping.json](tracker-mapping.json) and [tracker-item.json](tracker-item.json) | Flat native tracker shape. |
| [tracker-mapping-nested.json](tracker-mapping-nested.json) and [tracker-item-nested.json](tracker-item-nested.json) | Nested native tracker shape with equivalent canonical meaning. |
| [adapter.json](adapter.json) | Generic agent-interface declaration, not a live integration. |

Quality fixtures use the same artifact envelopes, evidence files and
`policy.json` as Software Factory. They are **not genuine test results**.
The [quality rehearsal](../docs/tutorials/quality-rehearsal.md) shows how
to generate a consolidated output without mutating candidate code.

Follow the [first-skill tutorial](../docs/tutorials/first-skill.md) or the
[factory rehearsal](../docs/tutorials/factory-rehearsal.md) for the commands and
expected results. The retained records and evidence support those demonstrations
only. A production integration must capture its own trusted records and evidence.
