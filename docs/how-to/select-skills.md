# Select skills and workflows

Use this guide when deciding how much process a task needs. Begin with the result
and its risks, then select the smallest set of skills that can establish it.
The catalog is coverage, not a mandatory sequence for every change.

## 1. Identify the result and the uncertainty

Write one sentence describing the intended outcome. Separate questions about
user intent from questions answerable by reading or executing the project.
Use `sf-clarify-outcome` for the former and `sf-map-project` for the latter.

Classify the work as quality assessment, discovery, feature, defect, refactor, migration, release,
incident, retirement, or improvement. Reuse an existing approved specification or
work plan only after checking that it still describes the current task.

## 2. Choose a starting recipe

| Situation | Starting point | Evidence that matters |
| --- | --- | --- |
| Existing code, external PR, or supplied change to assess without editing | `quality` | Exact candidate identity, verification, review, scoped findings and limitations. |
| Security/compatibility-sensitive quality audit | `quality-risk` | Same fixed candidate plus selected security and compatibility evidence. |
| Uncertain value or problem | `discovery` | User/problem evidence, constraints, and an explicit decision. |
| One bounded behavior increment | `feature` | Acceptance criteria, one work unit, test results, and review. |
| Known incorrect behavior | `defect` | A representative reproduction, cause, repair, and original-path replay. |
| Internal structural change | `refactor` | Preserved behavior, bounded changes, and dependency impact. |
| Persisted-data or contract transition | `migration` | Compatibility, ordered rollout, recovery limits, and rehearsal. |
| Approved change ready to ship | `release` | Exact integrated candidate, release plan, authorized deployment, and observation. |
| Active service disruption | `incident` | Current impact, containment, safe recovery, and verified service state. |
| Planned removal | `retirement` | Consumers, commitments, retention obligations, and an executable retirement plan. |
| Repeated delivery failures | `improvement` | Observed cases, hypotheses, and a measured evaluation. |

Read the [workflow reference](../reference/workflows.md) before choosing a recipe.
Some recipes deliberately produce a plan or a review package; their completion
is not a deployment or removal claim. Feature and defect recipes each implement
one work item. For a larger plan, explicitly expand into per-item work and verify
the aggregate result; do not treat the first slice as completion of the feature.

## 3. Add specialist checks for concrete risks

- User interaction changes: `sf-design-experience` and `sf-check-accessibility`.
- New trust boundaries, permissions, or untrusted input: `sf-assess-security`.
- Personal or sensitive data: `sf-protect-privacy`.
- Persisted data changes: `sf-evolve-data` and `sf-check-compatibility`.
- Shared protocols, public APIs, or mixed-version consumers: `sf-check-compatibility`.
- Performance claims or resource risks: `sf-measure-performance`.
- Operationally meaningful behavior: `sf-design-observability`.
- New or changed dependencies: `sf-audit-dependencies`.

Insert the required nodes and artifact bindings into a project-specific workflow,
then validate the graph. Do not rely on an unwritten expectation that a generic
review will cover a specialist concern.

For example, add a `security` node using `sf-assess-security` after the candidate
is settled. Bind its `project-context`, `change-set`, and optional `specification`
from their existing producers. Add `security` to the review node's `needs` and
add this entry to its `bindings`:

```json
{
  "security-assessment": "step:security:security-assessment"
}
```

This is a bindings fragment, not a complete workflow. `sf-review-change` declares
typed optional inputs for the specialist reports, and `sf-prepare-release` can
consume the relevant assessments at the release boundary. Use the consumer's
actual contract to choose a binding; do not pass a report under a different type
merely because its prose seems relevant.

The independent [Quality Factory](run-quality.md) starts from a read-only
candidate and **does not** call `sf-build-change`. Add risk specialists to
its review and consolidation steps using the same typed bindings as Software
Factory. Non-passing reports can be forwarded only to observational consumers,
not to integration or deployment gates.

## 4. Remove work only with a reason

A documentation typo may need a bounded edit and a rendering/link check. A change
to an authorization boundary may need independent review and adversarial tests.
Do not select an expensive model, a second reviewer, or an extensive test matrix
merely because it is available.

For every omitted check, record why the risk is absent or which accepted policy
allows the omission. An omitted required check remains unresolved. A waiver is an
explicit risk decision; it must not be rewritten as a passing test.

## 5. State the finish line

Name the artifact and status that finish this task, the person or system that
owns the next decision, and the external actions already authorized. Keep
preparing review, publishing review, integrating a change, publishing a release,
and deploying a release distinct.
