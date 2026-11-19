# Artifact envelope and payloads

Schema: [artifact.schema.json](../../schemas/artifact.schema.json). Every skill
bundles the same schema at `references/artifact.schema.json` for standalone use.
Validate produced JSON against that local copy before accepting the result.

Artifacts carry results between skills, humans, agents, and controllers. An
artifact's type states what the result is about; its subject states which
candidate and inputs it applies to. Its status must be interpreted within those
boundaries.

## Envelope fields

| Field | Required content |
| --- | --- |
| `schema_version` | `1.0`. |
| `artifact_id` | Stable identity for this particular result. |
| `artifact_type` | A kebab-case type from the producing skill's declared outputs, or the type of an external input. |
| `producer` | Object with `skill` and three-component `version`. |
| `run_id` | The run that produced or accepted the artifact. |
| `status` | `passed`, `failed`, `blocked`, or `inconclusive`. |
| `created_at` | ISO 8601 timestamp with timezone; use UTC for interoperable records. |
| `subject` | Object with exact `revision`, 64-character lowercase SHA-256 `input_digest`, and `environment`. |
| `summary` | A concise factual account of the result. |
| `evidence` | Evidence records described below. |
| `checks` | Explicit criteria and their observed results. |
| `unresolved` | Material open questions, gaps, or findings. |
| `next_action` | The concrete next step or an explicit completion statement. |
| `payload` | Skill-specific result content defined in the skill's instructions. |

The generic schema deliberately allows a payload object rather than prescribing
one universal business model. Skill instructions define payload meaning. Structural
validation alone cannot establish that an arbitrary payload is complete or
truthful; controllers and evaluators must check the relevant semantic contract.

The offline reference checker also validates **core payload schemas** for
`verification-report` and `review-report` from
[`payload-verification-report.schema.json`](../../schemas/payload-verification-report.schema.json)
and [`payload-review-report.schema.json`](../../schemas/payload-review-report.schema.json).
They constrain claim-bearing counts, dispositions, and field types while allowing
additional skill-specific fields. A schema-valid report is still not proof that a
check ran or a reviewer is independent: the host must authenticate producers,
inspect evidence, and enforce policy at the action boundary. Missing or malformed
core payload fields block a reference gate.

A consolidated `quality-assessment` uses the same envelope, with an
additional [quality payload schema](../../schemas/payload-quality-assessment.schema.json)
for its target, report statuses, coverage, findings, limitations, independence,
and remediation boundary. The result is **not** permission to mutate. Any
passing quality report must include passing verification and review evidence,
plus passing evidence for every selected required dimension. Negative source
statuses cannot be repackaged into a passing quality result.

The checker opens each retained source report and validates the same bytes named
by its evidence digest. Its artifact ID, type, status, run, subject, age, checks,
and evidence must agree with the summary. The target revision must match the
envelope, and evaluated coverage must match the retained assessment/report types.
A summary cannot weaken a source verdict, drop or downgrade a source finding,
or replace an approval with an unevidenced risk label. Consolidation preserves
finding locations, source evidence references, and waivers; copied approval
references resolve within the new bundle. Nested quality summaries are rejected,
so inspection has one bounded level of source reports.

These are consistency checks, not producer authentication. A host must still
establish who performed the checks and who had authority to accept a risk.

## Evidence record

Each evidence record has:

- `id`: a unique local kebab-case reference.
- `kind`: `analysis`, `observation`, `test`, `review`, `log`, `metric`, `diff`, `approval`, or `input`.
- `uri`: a location from which the evidence can be inspected.
- `sha256`: the expected lowercase SHA-256 digest of its bytes.
- `description`: what the evidence establishes and any important boundary.

The offline reference tools resolve local evidence paths relative to the artifact
file. They reject paths escaping the permitted artifact directory, including
symlink escapes. They do not fetch arbitrary remote evidence. A production host
can provide a different evidence store, but must preserve integrity, authorization,
and availability guarantees.

Local JSON inputs and retained evidence must be regular files of at most 16 MiB.
The reference reader rejects pipes, device files, oversized inputs, and duplicate
JSON object keys. These limits keep an offline check bounded; large evidence
stores need a separately qualified integration.

A digest detects changed bytes; it does not authenticate the source of a log or
prove execution. Retain execution provenance in the host. Redact unnecessary
secrets and personal data before evidence is published to a wider audience.

## Check record

Each check has `id`, `status`, `evidence` (an array of evidence IDs), and `detail`.
Check IDs, like evidence IDs, use lowercase kebab-case. The detail explains the
criterion, the observation, and any limitation. References
must resolve to evidence in the same artifact.

A passing check needs evidence appropriate to its claim. A zero-test run is not
successful runtime verification. An inaccessible environment is a blocker; an
insufficiently discriminating observation is inconclusive. Keep skipped required
checks and waivers visible rather than converting them into passing checks.

## Semantics checked for verification and review

In addition to the generic envelope, the reference tools enforce these payload
rules when consuming passing proof:

| Artifact | Required semantics |
| --- | --- |
| `verification-report` | Integer `required_count` greater than zero; integer `executed_count` at least `required_count`; integer `failed_count` equal to zero; `skipped_required` equal to `[]`; cited test or observation evidence. |
| `review-report` | Explicit `findings` array. Every finding has Boolean `blocking` and a supported `disposition`; unresolved blocking findings prevent advancement. |
| `review-status` at an action gate | `payload.readiness` is `ready`; `payload.head` matches `subject.revision`; an explicit `payload.checks` array has no unsatisfied required check. |

Finding dispositions are `open`, `resolved`, `rejected`, and `accepted-risk`.
A blocking finding marked `accepted-risk` requires `waiver` with nonempty
`actor`, `decision`, and `evidence` strings. The evidence value must identify a
hashed evidence record of kind `approval` in the same artifact. The host must
authenticate that decision and verify the actor's authority; a waiver is not a
passing test or a repair.

When policy requires independent review, `reviewer`, `change_author`, and
`independence_basis` must be meaningful nonempty strings. The reviewer and author
must differ after trimming whitespace. Placeholder identities do not establish
independence. The host still authenticates identities; the offline checker cannot.

## Artifact families

| Family | Typical artifact types | What completion establishes |
| --- | --- | --- |
| Intent and design | `outcome-brief`, `opportunity-assessment`, `domain-model`, `specification`, `solution-design`, `experience-design` | A stated problem, decision, or design is sufficiently defined. |
| Planning | `work-plan`, `test-plan`, `migration-plan`, `observability-plan`, `retirement-plan` | A scoped plan with verifiable completion and recovery conditions exists. |
| Implementation | `change-set`, `documentation-report` | A bounded change or documentation update is described and evidenced. |
| Consolidated quality | `quality-assessment` | Scoped quality verdict with report provenance and limitations; does not change source. |
| Assessment | `diagnosis`, `impact-assessment`, `security-assessment`, `privacy-assessment`, `dependency-report` | The stated assessment was performed with explicit limits. |
| Verification | `verification-report`, `exploration-report`, `compatibility-report`, `accessibility-report`, `performance-report` | The named criteria have observations tied to the candidate. |
| Review | `review-report`, `review-package`, `review-status` | Review analysis, publication preparation, or the current review state is recorded. |
| Delivery | `integration-record`, `release-plan`, `deployment-record`, `release-observation`, `recovery-record` | A specific delivery responsibility is recorded; inspect its actual effects and observations. |
| Coordination and improvement | `project-context`, `coordination-record`, `incident-record`, `improvement-plan`, `evaluation-report` | Context, ownership, response, or improvement work is made explicit. |

Consult the [catalog](catalog.md) and the producing skill for exact required
payload content. Artifact names are interfaces, not interchangeable labels.

## Freshness and reuse

Reusing evidence requires the same relevant revision, inputs, environment, and
producer semantics. The reference tools use conservative exact subject matching
and policy age limits. A changed checkpoint requires deliberate revalidation or a
new run; the tools do not implement selective incremental replay.

Do not rewrite a timestamp or hash to make stale evidence appear current. Preserve
prior records and create a new result when the work is rerun. A richer controller
may record a justified reuse decision, but it must retain the original evidence
and establish that the claim still applies.
