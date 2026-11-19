---
name: sf-audit-dependencies
description: "Assess dependencies and build inputs for provenance, exposure, maintenance, and update risk. Use for dependency changes, supply-chain reviews, or periodic dependency health checks."
---

# Audit dependencies

Read the [execution protocol](references/protocol.md) and use the [skill contract](contract.json). Apply the supplied scope, evidence identity, authorization, and budget throughout.

Validate factory JSON outputs with the bundled [artifact schema](references/artifact.schema.json) before handoff.

## Inputs

Read the project context and any supplied change set or specification. Establish the inventory boundary, supported environments, dependency policy, and evidence freshness requirement. Include code, packages, runtime images, build tools, generated artifacts, remote actions, and externally fetched configuration where they influence the delivered system.

## Procedure

1. Reconstruct the resolved dependency graph from manifests, locks, build records, artifact metadata, and deployment descriptions. Distinguish declared versions from what actually enters the runtime or build. Record unpinned, mutable, vendored, or dynamically downloaded inputs.
2. Determine provenance and integrity controls for each material class of input. Check trusted retrieval locations, immutable identifiers, signatures or attestations when available, and how maintainers review changes. A checksum confirms identity, not trustworthiness by itself.
3. Use approved, current advisory and license sources through the available tools. Record query date, database version or source revision, and scanner configuration. Treat scanner output as candidate evidence; distinguish missing database coverage from an absence of reported issues.
4. For relevant advisories, assess the actual resolved version, reachable feature, execution privileges, configuration, and attacker prerequisites. Record mitigating controls and uncertainty. Do not dismiss a match merely because an exploit has not been observed, or claim exploitability from a version match alone.
5. Assess maintenance and concentration risk: update cadence, compatibility constraints, abandoned components, duplicated dependencies, privileged install scripts, and critical single-maintainer or single-service dependencies. Use observed facts and avoid turning popularity into a security score.
6. Propose bounded actions with tradeoffs: update, remove, replace, isolate, pin, restrict capabilities, or accept for a defined period. Define the owner, expiry, affected interfaces, and verification needed. Include transitive-resolution changes and the cost of maintaining a fork or patch.
7. Validate supplied dependency changes in a controlled environment using the project's declared build and relevant behavior checks. Inspect execution hooks before running unknown tooling. Never automatically upgrade the entire graph to clear a report. Preserve the exact resolution and evidence for each recommendation.

## Output

Produce a `dependency-report` containing `payload.inventory`, `provenance`, `advisory_sources`, `findings`, `maintenance_risks`, `recommended_actions`, and `coverage_gaps`. Separate verified exposure, potential exposure, policy nonconformance, and unassessed inputs. Avoid placing credentials or private registry access details in the report.

## Completion and boundaries

Return failed for a demonstrated required-policy violation, inconclusive for insufficient evidence, and blocked when a required inventory or source cannot be accessed. A passed scoped assessment means the stated checks passed on the resolved inputs; it does not establish universal supply-chain safety. Remediation, public disclosure, and accepting a policy exception require separate authority.

## Example and handoff

For an image-processing update, identify the transitive native decoder actually shipped, verify whether the vulnerable format is enabled, and exercise representative decoding and error handling after the proposed change. Hand the smallest justified remediation to `sf-build-change` and include unresolved exposure in `sf-prepare-release`.
