# Capabilities, effects, and authorization

A **capability** describes an operation the host can perform. An **effect** describes
a class of state change the skill may need. **Authorization** is the actual grant
to perform a particular effect on a particular resource. None implies the others.

## Capabilities

| Name | Meaning |
| --- | --- |
| `workspace.read` | Inspect project files and local task context. |
| `workspace.write` | Modify files in the permitted workspace. |
| `execution.run` | Run approved verification, experiments, or project commands in the permitted environment. |
| `tracker.read` | Read work items, dependencies, and tracker state. |
| `tracker.write` | Create or update tracker records within scope. |
| `review.read` | Inspect review requests, findings, and review state. |
| `review.write` | Create or modify shared review records. |
| `vcs.read` | Inspect version history, references, and changes. |
| `vcs.write` | Modify version-control state within the permitted scope. |
| `release.publish` | Publish release material to the selected distribution surface. |
| `deployment.read` | Inspect deployment identity and status. |
| `deployment.write` | Change the selected deployment. |
| `telemetry.read` | Inspect operational logs, metrics, traces, or observations. |
| `communication.send` | Send an authorized message to an explicitly resolved destination. |
| `artifact.write` | Record task output and evidence without implying source or external mutation. |

A tool may expose several capabilities; a capability may be implemented through
several tools. Required baseline capabilities appear in each skill's contract.
Additional operations need their own capability and authorization checks even if
a host happens to expose a convenient broad tool.

## Effects

| Name | Boundary |
| --- | --- |
| `workspace.modify` | Source, configuration, test, or documentation changes in the workspace. |
| `tracker.modify` | Shared work-item creation or updates. |
| `review.publish` | Shared review request, comment, or review-state publication. |
| `integration.modify` | Integration of a candidate into a shared target line of development. |
| `release.publish` | Publication of a release or distributable artifact. |
| `deployment.modify` | Rollout, rollback, or other deployment-state changes. |
| `data.modify` | Live or persistent data operations beyond ordinary isolated test fixtures. |
| `external.communicate` | Person- or audience-directed communication outside the task's local artifacts. |

The same operation can cross several boundaries. A merge that triggers deployment
has deployment consequences even if the source-control API exposes only one
button. The controller must understand those configured effects before acting.

## Conditional effects

`effects` contains the skill's baseline effects. Optional `conditional_effects`
entries declare an `effect` and the `condition` that makes it necessary. The host
selects applicable conditional effects per step through the run's
`selected_effects` map. Selection describes the requested operation; it never
grants permission.

For example, `sf-recover-release` always declares `deployment.modify`. It declares
`data.modify` conditionally for recovery that changes persistent data. An ordinary
deployment rollback that leaves data untouched does not select that effect. For
a data-restoring recovery, the incident run includes:

```json
{
  "selected_effects": {
    "recover": ["data.modify"]
  }
}
```

This fragment is part of a complete run manifest, not a standalone manifest. The
run also needs an exact `data.modify` scope, the required capability, a trusted
grant, and the recovery policy's evidence. Baseline effects remain mandatory.
Undeclared selections are invalid; omitted conditional effects are prohibited for
that invocation. If recovery unexpectedly requires a data write, stop and revise
the scoped invocation before making it.

Emergency recovery may use a separately owned policy with recovery-specific
preconditions and targets. A worker must not weaken the normal policy or invent a
waiver to make a blocked recovery proceed.

## Scope and grants

The reference policy matches exact `run_id`, `effect`, `scope`, and `subject`
values, with an expiry. Scope strings identify concrete targets; there is no
implicit wildcard or inheritance from a similar target. See the
[policy schema](../../schemas/policy.schema.json).

A host should derive trusted grants from the user's instruction or configured
policy. Do not ask again when the existing grant already covers the operation.
Do not broaden it to a different environment, another person's resources, or a
new class of effect. Read a skill's declaration as a requirement to check, not as
permission created by the file.

## Adapter declarations

Schema: [adapter.schema.json](../../schemas/adapter.schema.json).

An adapter declaration identifies `id`, `kind`, advertised `capabilities`,
`implementation`, and `operations`. Kinds are `agent`, `tracker`, `vcs`,
`verification`, `deployment`, `observability`, and `communication`.

`implementation` distinguishes `reference` from `declaration`. A declaration
specifies a boundary; it does not mean an external integration has been built or
qualified.

Each operation records its name, capability, description, input/output names,
idempotency requirement, and concurrency mode. Concurrency is `read-only`,
`isolated`, or `compare-and-set`. An operation marked as requiring idempotency
needs an implementation that detects repeated requests and reconciles unknown
outcomes.

A production adapter must also enforce authentication, target scope, input
validation, evidence capture, and error semantics. Documentation and valid JSON
cannot enforce those properties by themselves.

## Included adapter boundaries

| Artifact | Status | Boundary |
| --- | --- | --- |
| [Agent interface](../../adapters/agent-interface.json) | Declaration | Prepare an invocation and collect its declared artifacts. |
| [Tracker interface](../../adapters/tracker-interface.json) | Declaration | Read and conditionally update canonical work items. |
| [Verification interface](../../adapters/verification-interface.json) | Declaration | Run a named check against an identified subject. |
| [Deployment interface](../../adapters/deployment-interface.json) | Declaration | Inspect and change a scoped deployment. |
| [Local export reader](../../adapters/local-export-reader.json) | Reference implementation | Normalize a supplied tracker JSON export without service calls. |

The text invocation renderer is also implemented, but it does not constitute a
live agent connection. Qualify a real execution host separately.

## Canonical work item

Schema: [work-item.schema.json](../../schemas/work-item.schema.json).

A work item has `schema_version`, `id`, `title`, `description`, `state`, `version`,
`dependencies`, `acceptance`, `source`, and `links`. Canonical states are `queued`,
`ready`, `active`, `blocked`, `review`, `done`, and `cancelled`. `source` preserves
the adapter ID, native item ID, and native state. A project's mapping determines
what `done` means; it must not silently equate it with deployment.

The work-item schema describes data, not transition enforcement. Version checking,
ownership, valid transitions, and deduplication remain adapter/controller duties.
