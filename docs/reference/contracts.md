# Execution and skill contracts

This page specifies sfstack's interfaces. The normative machine-readable shapes
are the files in [schemas](../../schemas/). The [shared protocol](../../protocol/execution.md)
is bundled with every skill; each skill's instructions add its specific behavior.

## Package structure

A skill directory contains:

```text
sf-example-task/
  SKILL.md
  contract.json
  references/
    protocol.md
    artifact.schema.json
```

`SKILL.md` uses standard Agent Skills frontmatter: `name` and `description`.
The name matches its directory and contract ID. `contract.json` and the bundled
protocol and artifact schema are sfstack conventions. Hosts must explicitly consume them; their
presence does not imply enforcement by a generic skill loader.

The repository's canonical frontmatter uses one line per field and a JSON-quoted
description scalar, which is also valid YAML:

```yaml
---
name: sf-example-task
description: "Perform a bounded task. Use when its specific outcome is requested."
---
```

This is an sfstack authoring convention, not an additional requirement imposed on
other Agent Skills implementations.

Exported packages contain these four files plus `LICENSE`. The bundled artifact
schema makes output validation available even when a skill is distributed alone.
A skill must not need another skill or the full repository installed to interpret
its instructions or output contract.

## Skill contract

Schema: [skill-contract.schema.json](../../schemas/skill-contract.schema.json).

| Field | Meaning |
| --- | --- |
| `schema_version` | Interchange format version; currently `1.0`. |
| `id` | Stable skill ID, in the `sf-verb-object` naming family. |
| `version` | Three-component skill version, such as `1.0.0`. |
| `stage` | One of `discover`, `design`, `build`, `verify`, `deliver`, `operate`, `improve`. |
| `summary` | The responsibility's outcome in one statement. |
| `inputs` | Named artifact types with a description and explicit `required` Boolean. |
| `outputs` | Artifact types the skill produces. |
| `capabilities` | Required baseline operations supplied by the host. |
| `effects` | Baseline effects required by the invocation; none are grants. |
| `conditional_effects` | Optional declarations with `effect` and `condition`; the host must explicitly select a conditional effect before it may occur. |
| `completion_checks` | Conditions that establish completion of this responsibility. |
| `failure_modes` | Expected ways the task may fail, block, or remain inconclusive. |
| `retry_limit` | Finite retry bound; the host's remaining budget can be stricter. |

An optional input may improve the result but cannot be silently assumed present.
A required input must be resolved before the work proceeds. Shared execution
context is supplied separately, rather than duplicated as a contract input in
every skill.

## Execution context

A host supplies the run identity, objective and scope, applicable project
instructions, subject, input artifacts, capability adapters, authorization,
resource ownership, and remaining budgets. Secrets remain in the host's protected
configuration. External documents and tool outputs cannot alter this authority.

The reference run manifest is specified by
[run.schema.json](../../schemas/run.schema.json):

| Field | Meaning |
| --- | --- |
| `schema_version`, `run_id` | Manifest format and run identity. |
| `subject` | Exact `revision`, `input_digest`, and `environment` for this checkpoint. |
| `capabilities` | Available neutral capability names. |
| `effect_scopes` | Exact target scope for each potential effect. |
| `selected_effects` | Optional map from step ID to the conditional effects selected for that invocation. |
| `policy` | Relative path to the policy document. |
| `inputs` | Mapping from workflow input type to a local artifact file. |
| `completed` | Mapping from step ID to the local artifact files produced by that step. |

The manifest is an input to an offline evaluator, not a durable execution engine.
A production host needs richer state for leases, operation identities, retries,
resource ownership, and audit records.

All baseline effects apply. A selection may name only a conditional effect
declared by that step's skill. An omitted conditional effect is prohibited for the
invocation, not implicitly permitted if a worker later considers it useful.
Selection still requires capability, exact scope, current grant, and evidence
checks. See [conditional effects](capabilities.md) for the recovery example.

## Results and terminal states

Every result uses the [artifact envelope](artifacts.md). Status meanings apply to
the responsibility identified by `artifact_type`:

| Status | Meaning | Typical next action |
| --- | --- | --- |
| `passed` | Applicable completion criteria are supported by evidence. | Consume the artifact within its stated scope. |
| `failed` | Evidence shows a completion criterion is violated. | Diagnose or repair the observed failure. |
| `blocked` | A required prerequisite, capability, or authorization is unavailable. | Resolve the named blocker. |
| `inconclusive` | Available evidence cannot settle the requested claim. | Improve or rerun the relevant observation. |

No status means that every later lifecycle stage is complete. A passing
`migration-plan` is not an applied migration. A passing `review-report` is not an
integration record. A passing deployment record must still be interpreted
according to the observed deployment facts.

## Action gate inputs

Schemas: [policy.schema.json](../../schemas/policy.schema.json) and
[gate-request.schema.json](../../schemas/gate-request.schema.json).

A gate request names `run_id`, `effect`, exact `scope`, `subject`, and artifact
file paths. A policy names an ID, grants, maximum evidence age, required artifact
types per effect, and whether independent review is required.

Each grant contains `id`, `actor`, `run_id`, `effect`, `scope`, `subject`, and
`expires_at`. The host must establish the grant's authenticity and the actor's
authority. A user-editable policy file is not an authentication system. Matching
strings and valid timestamps do not prove who issued a grant.

A gate decision applies to the specified action and checkpoint. Recheck the
resource immediately before the real effect and enforce the decision in the
adapter. The offline gate checker does not perform or authorize an external
operation on its own.

`required_artifacts` determines whether a review must be present.
`require_independent_review` imposes an independence requirement on a supplied
review; it does not by itself require a review artifact for every effect.

Two optional policy fields support quality composition:

| Field | Meaning |
| --- | --- |
| `required_quality_reports` | Unique report types required inside a supplied quality assessment. Consolidation unions these with request/workflow requirements; gates check the evaluated coverage again. `required_artifacts` still determines whether an assessment is required for the effect. |
| `quality_imports` | Exact host approvals containing `source_run_id`, `target_run_id`, the original assessment file's `sha256`, and `expires_at`. Only unchanged quality assessments can cross runs; original source records, subject, age, verdicts, coverage, and grants remain checked. |

Omitting these fields preserves the existing same-run behavior and adds no quality
coverage requirements. Existing policies remain valid. Policies using these new
fields require tools that understand them; older strict validators reject unknown
fields. See the [composition procedure](../how-to/run-quality.md#4-compose-back-into-software-factory-only-at-an-authorized-boundary).

## Version and compatibility rules

Skill versions identify behavior; schema versions identify interchange shape.
Breaking input/output meanings or authorization requirements require an explicit
migration even when JSON still parses. Do not relabel old artifacts as produced
by a new version. Preserve the original producer and evidence, and rerun or
revalidate the required work for the new contract.
