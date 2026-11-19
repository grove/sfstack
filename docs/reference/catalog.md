# Skill catalog

The library contains 37 independent skills. Names follow `sf-verb-object`; each
entry links to the complete instruction package. The required inputs listed here
are artifact types. Every skill also receives the shared execution context.
Optional inputs, effects, retry limits, and detailed completion conditions are
specified in its adjacent `contract.json`.

Select the smallest set that settles the task's risks. A category is a navigation
aid, not a requirement to execute every entry. See [select skills](../how-to/select-skills.md)
and the [workflow recipes](workflows.md) for composition.

## Discovery and design

| Skill | Responsibility | Required inputs | Output |
| --- | --- | --- | --- |
| [sf-map-project](../../skills/sf-map-project/SKILL.md) | Map a project into evidenced behavior, ownership boundaries, and verification paths. | `request` | `project-context` |
| [sf-clarify-outcome](../../skills/sf-clarify-outcome/SKILL.md) | Turn an ambiguous request into a bounded, testable outcome. | `request` | `outcome-brief` |
| [sf-validate-opportunity](../../skills/sf-validate-opportunity/SKILL.md) | Assess whether a proposed outcome addresses a supported need and merits investment. | `outcome-brief` | `opportunity-assessment` |
| [sf-model-domain](../../skills/sf-model-domain/SKILL.md) | Define shared domain language, rules, states, and ownership boundaries. | `outcome-brief` | `domain-model` |
| [sf-write-specification](../../skills/sf-write-specification/SKILL.md) | Describe externally observable behavior, constraints, and acceptance criteria for a bounded change. | `outcome-brief` | `specification` |
| [sf-design-solution](../../skills/sf-design-solution/SKILL.md) | Choose a maintainable implementation structure that satisfies a specification and existing system constraints. | `specification`, `project-context` | `solution-design` |
| [sf-plan-work](../../skills/sf-plan-work/SKILL.md) | Decompose a specification and design into bounded, dependency-aware work units. | `specification`, `solution-design` | `work-plan` |

## Implementation and verification

| Skill | Responsibility | Required inputs | Output |
| --- | --- | --- | --- |
| [sf-build-change](../../skills/sf-build-change/SKILL.md) | Implement one bounded work unit with requirement-linked evidence and a reviewable change set. | `work-plan`, `specification` | `change-set` |
| [sf-diagnose-defect](../../skills/sf-diagnose-defect/SKILL.md) | Establish a defect mechanism through a faithful reproduction and discriminating experiments. | `request`, `project-context` | `diagnosis` |
| [sf-refactor-structure](../../skills/sf-refactor-structure/SKILL.md) | Improve internal structure while preserving an explicitly defined behavioral contract. | `request`, `project-context` | `change-set` |
| [sf-design-tests](../../skills/sf-design-tests/SKILL.md) | Design proportionate behavioral checks that can distinguish a correct change from plausible defects. | `specification` | `test-plan` |
| [sf-verify-change](../../skills/sf-verify-change/SKILL.md) | Collect and assess current evidence that a specific candidate satisfies its required checks. | `change-set`, `test-plan` | `verification-report` |
| [sf-explore-behavior](../../skills/sf-explore-behavior/SKILL.md) | Explore a running candidate through realistic paths to discover unanticipated defects. | `change-set`, `specification` | `exploration-report` |
| [sf-assess-impact](../../skills/sf-assess-impact/SKILL.md) | Identify downstream obligations and evidence needed to change a system safely. | `change-set`, `project-context` | `impact-assessment` |
| [sf-review-change](../../skills/sf-review-change/SKILL.md) | Review a fixed candidate for requirement conformance, correctness, and maintainability using supported findings. | `change-set`, `specification`, `verification-report` | `review-report` |
| [sf-maintain-documentation](../../skills/sf-maintain-documentation/SKILL.md) | Update documentation to match verified behavior and the reader’s task. | `change-set`, `specification` | `documentation-report` |

## Specialist assurance

| Skill | Responsibility | Required inputs | Output |
| --- | --- | --- | --- |
| [sf-design-experience](../../skills/sf-design-experience/SKILL.md) | Design coherent user journeys, interaction states, and presentation rules. | `outcome-brief` | `experience-design` |
| [sf-check-accessibility](../../skills/sf-check-accessibility/SKILL.md) | Assess whether people with differing access needs can complete the changed journeys. | `specification`, `change-set` | `accessibility-report` |
| [sf-assess-security](../../skills/sf-assess-security/SKILL.md) | Assess changed trust boundaries and verify plausible abuse paths. | `project-context`, `change-set` | `security-assessment` |
| [sf-protect-privacy](../../skills/sf-protect-privacy/SKILL.md) | Minimize and govern personal or sensitive data across a feature lifecycle. | `project-context`, `specification` | `privacy-assessment` |
| [sf-evolve-data](../../skills/sf-evolve-data/SKILL.md) | Plan a compatible, recoverable data or schema evolution. | `project-context`, `specification` | `migration-plan` |
| [sf-check-compatibility](../../skills/sf-check-compatibility/SKILL.md) | Verify compatibility across producers, consumers, versions, and persisted formats. | `specification`, `change-set` | `compatibility-report` |
| [sf-measure-performance](../../skills/sf-measure-performance/SKILL.md) | Measure whether a change satisfies an explicit performance or capacity claim. | `project-context`, `change-set` | `performance-report` |
| [sf-design-observability](../../skills/sf-design-observability/SKILL.md) | Define how operators will detect, explain, and respond to service behavior. | `project-context`, `specification` | `observability-plan` |
| [sf-audit-dependencies](../../skills/sf-audit-dependencies/SKILL.md) | Assess dependencies and build inputs for provenance, exposure, maintenance, and update risk. | `project-context` | `dependency-report` |

## Delivery and operations

| Skill | Responsibility | Required inputs | Output |
| --- | --- | --- | --- |
| [sf-prepare-review](../../skills/sf-prepare-review/SKILL.md) | Prepare and publish a focused change for review through the available review adapter. | `change-set`, `verification-report`, `review-report` | `review-package` |
| [sf-maintain-review](../../skills/sf-maintain-review/SKILL.md) | Bring an open review to a current, actionable state by resolving verified findings and check failures. | `review-package` | `review-status` |
| [sf-integrate-change](../../skills/sf-integrate-change/SKILL.md) | Integrate an authorized reviewed change into its target using current revision evidence. | `review-status`, `verification-report`, `review-report` | `integration-record` |
| [sf-prepare-release](../../skills/sf-prepare-release/SKILL.md) | Assemble a reproducible release candidate and a bounded rollout plan. | `integration-record` | `release-plan` |
| [sf-deploy-release](../../skills/sf-deploy-release/SKILL.md) | Execute an authorized release plan and establish the identity of the deployed revision. | `release-plan`, `verification-report` | `deployment-record` |
| [sf-observe-release](../../skills/sf-observe-release/SKILL.md) | Assess a deployed revision against user outcomes and operational thresholds during a bounded observation window. | `deployment-record` | `release-observation` |
| [sf-recover-release](../../skills/sf-recover-release/SKILL.md) | Restore an acceptable service state using an authorized, data-compatible recovery action. | `deployment-record`, `request` | `recovery-record` |
| [sf-handle-incident](../../skills/sf-handle-incident/SKILL.md) | Coordinate evidence, impact assessment, and bounded decisions during a live service incident. | `request` | `incident-record` |
| [sf-retire-component](../../skills/sf-retire-component/SKILL.md) | Plan the controlled retirement of a component, interface, environment, or data set. | `project-context`, `request` | `retirement-plan` |

## Coordination and improvement

| Skill | Responsibility | Required inputs | Output |
| --- | --- | --- | --- |
| [sf-coordinate-work](../../skills/sf-coordinate-work/SKILL.md) | Coordinate a bounded graph of work across available agents without losing ownership or evidence. | `work-plan` | `coordination-record` |
| [sf-improve-process](../../skills/sf-improve-process/SKILL.md) | Turn observed delivery problems into testable process improvements. | `request` | `improvement-plan` |
| [sf-evaluate-skills](../../skills/sf-evaluate-skills/SKILL.md) | Evaluate whether a versioned skill or workflow improves realistic outcomes. | `request` | `evaluation-report` |

## Boundaries worth preserving

- `sf-design-tests` defines a verification approach; `sf-verify-change` executes and evaluates it.
- `sf-diagnose-defect` establishes a cause; `sf-build-change` applies an agreed implementation scope.
- `sf-review-change` assesses a candidate; `sf-prepare-review` prepares or publishes its review package under the granted scope.
- `sf-maintain-review` reconciles review state; `sf-integrate-change` performs an authorized integration against current evidence.
- `sf-prepare-release` defines the release; `sf-deploy-release` changes the target deployment; `sf-observe-release` checks the deployed result.
- `sf-evolve-data` and `sf-retire-component` produce executable plans. Their passing status does not claim live migration or deletion.
- `sf-coordinate-work` manages dependencies and ownership within its granted scope; it does not create broader permissions for workers.

The catalog is intentionally independent of any tracker, programming language,
framework, model, or host. An integration must supply and qualify the required
capabilities. Missing capabilities remain visible in the result.
