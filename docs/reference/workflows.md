# Workflow recipes

Schema: [workflow.schema.json](../../schemas/workflow.schema.json).

A recipe is a directed acyclic graph of skill responsibilities. Its bindings
identify exactly where each input comes from. Recipes describe composition; they
do not grant authorization or dispatch tools.

## Included recipes

| Recipe | External inputs | Completion boundary |
| --- | --- | --- |
| [discovery](../../workflows/discovery.json) | `request` | A specification informed by project context, opportunity assessment, and domain modeling. |
| [feature](../../workflows/feature.json) | `request` | One bounded behavior increment, documented, verified, reviewed, and prepared for review. |
| [defect](../../workflows/defect.json) | `request`, `specification`, `work-plan` | One diagnosed and scoped repair work unit with verification and review package. |
| [refactor](../../workflows/refactor.json) | `request`, `specification` | A structural change checked against preserved behavior and prepared for review. |
| [migration](../../workflows/migration.json) | `request`, `specification` | A data-evolution plan, solution design, and test plan; no live data mutation. |
| [release](../../workflows/release.json) | `review-package`, `verification-report`, `review-report` | An integrated, prepared, deployed, and observed release, subject to separate gates at each effect. |
| [incident](../../workflows/incident.json) | `request`, `deployment-record` | An incident record and scoped recovery of the identified deployment. |
| [retirement](../../workflows/retirement.json) | `request` | An executable retirement plan; no live deletion. |
| [improvement](../../workflows/improvement.json) | `request` | An improvement plan informed by an explicit skill evaluation. |

The feature and defect recipes each have one implementation node. That node sets
`max_work_items` to `1`, so a larger plan cannot be declared complete after only
its first slice. If planning yields several work items, the host must expand the
work into per-item runs or an explicitly expanded graph, preserve parent
traceability, and verify the integrated result against the whole specification.
The included planner does not perform that expansion.

The defect recipe assumes the supplied specification and work plan already bound
the intended repair. Run discovery and planning first when those are absent.
The incident recipe assumes a deployment-related incident with a known deployment
record; use `sf-handle-incident` directly for initial response or other incident
types. Its recovery node requires recovery-specific authority and preconditions.

The feature, defect, and refactor recipes place documentation changes before the
final impact and verification work, so a late documentation edit does not silently
invalidate the candidate under review.

## Graph fields

| Field | Meaning |
| --- | --- |
| `schema_version` | `1.0`. |
| `id` | Stable kebab-case workflow name. |
| `summary` | The recipe's intended outcome and boundary. |
| `inputs` | Artifact types supplied from outside this workflow. |
| `steps` | Nodes with `id`, `skill`, `needs`, `bindings`, and optional `max_work_items`. |
| `completion` | Step IDs whose successful completion establishes the recipe outcome. |

Every node's `id` is unique. `skill` names an installed contract in this checkout.
`needs` names predecessor nodes. A node may depend on a predecessor's completion
without consuming its artifact, for example to ensure documentation changes
finish before verification starts. Optional `max_work_items` is a positive bound
on a consumed work plan's item count. The reference planner blocks a bounded
implementation node when the plan exceeds the bound, omits the required item
information, or does not identify ready work. For these nodes, `work-plan.payload.items`
must contain one or more item objects within the bound, each with an `id` included
in `work-plan.payload.ready_frontier`.

## Binding syntax

A binding key must be a declared input of the selected skill. Its value is one of:

- `input:<artifact-type>` for a declared external workflow input.
- `step:<step-id>:<artifact-type>` for a declared output of an ancestor step.

The source's artifact type must match the input name. All required inputs must be
bound. Optional inputs may be omitted. An output cannot be borrowed from an
unrelated or future node merely because a file exists on disk.

A minimal valid recipe is:

```json
{
  "schema_version": "1.0",
  "id": "project-map",
  "summary": "Map a project without changing source or shared state.",
  "inputs": ["request"],
  "steps": [
    {
      "id": "orient",
      "skill": "sf-map-project",
      "needs": [],
      "bindings": {"request": "input:request"}
    }
  ],
  "completion": ["orient"]
}
```

## Validation and readiness

Validation checks contract names, input/output types, graph closure, unique node
IDs, cycles, and completion coverage. A valid graph can still be blocked at run
time by missing capabilities, unavailable inputs, stale evidence, or absent
permission.

The reference planner reports:

- `ready`: nodes eligible at this checkpoint.
- `completed`: nodes whose supplied output artifacts are acceptable for this checkpoint.
- `blocked`: reasons for nodes that cannot currently advance, including unmet dependencies.
- `status`: `ready`, `complete`, or `blocked` for the recipe.

A `ready` node is not a command already executed. The planner is read-only. A
controller must still acquire ownership and enforce permissions at the actual
tool boundary.

## Checkpoints and candidate changes

The reference planner compares all consumed artifacts with one fixed subject and
run identity. It does not automatically follow a candidate through source edits,
rebases, integrations, or deployments. After a change, deliberately establish the
next checkpoint and revalidate the affected artifacts and grants. Preserve the
original evidence; do not rewrite its subject to make it appear current.

This is especially relevant to the release recipe. If integration produces a new
revision, verify that resulting candidate before deployment. A verification report
for a pre-integration branch is insufficient. A production controller must perform
that checkpoint transition; the recipe alone cannot make old proof apply to a new
candidate.

## Composition limits in version 1

Recipes have no conditional nodes, dynamic fan-out, loops, or executable command
strings. Select a variant or construct a validated project-specific graph to add
specialist checks. Retry limits belong to skills and controller budgets; a repair
starts a deliberate new attempt rather than a graph cycle.

Do not expand every recipe to include every skill. Add security, privacy,
accessibility, compatibility, performance, dependency, and operational checks
when the task's risks require them. Record omitted applicable checks as unresolved
rather than silently weakening completion.
