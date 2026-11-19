# Development and reference tools

The utilities require Python 3.11 or newer and the dependencies declared in
[requirements-dev.txt](../../requirements-dev.txt). They maintain and demonstrate
the library; they do not constrain the technology used by a target project.

Run commands from the repository root:

```sh
python -m pip install -r requirements-dev.txt
```

## Validate the library

```sh
python tools/validate.py
```

Checks package structure and naming, canonical frontmatter, contract schemas, capability and
effect consistency, workflow references and bindings, shared reference copies, local
Markdown links, and example records covered by the validator. A successful run
establishes those structural properties, not general agent effectiveness or the
correctness of arbitrary payload prose.

The command exits nonzero on a detected error. Read the reported path and problem
before changing a file; do not weaken a check solely to make the library pass.

## Synchronize shared references

Canonical sources: [protocol/execution.md](../../protocol/execution.md) and
[schemas/artifact.schema.json](../../schemas/artifact.schema.json).

```sh
python tools/sync_protocol.py
python tools/sync_protocol.py --check
```

Without `--check`, copies the protocol and artifact schema into every skill's
`references/protocol.md` and `references/artifact.schema.json`. With `--check`,
performs no writes and exits `1` if any shared reference differs or is missing.
Review changes to either canonical source as interface changes affecting all
skills. The command reports shared-reference synchronization or verification.

## Inspect workflow readiness

```sh
python tools/factory.py plan \
  --workflow workflows/feature.json \
  --run examples/feature-run.json \
  --at 2026-11-19T12:00:00Z
```

`--workflow` and `--run` are required. `--at` fixes the UTC evaluation time for a
reproducible fixture; omit it to evaluate at the current time. Do not backdate a
live decision to bypass expired grants or old evidence.

The JSON response contains `workflow`, `run_id`, `status`, `ready`, `completed`,
and `blocked`. The planner validates fixed-subject artifacts and checks the
capabilities, effect scopes, grants, and evidence required for eligible steps.
It never invokes an agent or performs an operation. An optional workflow-node
`max_work_items` bound prevents a single implementation node from consuming an
oversized or insufficiently specified plan. Expanding a larger plan and verifying
the aggregate result remain host responsibilities.

| Exit code | Meaning |
| --- | --- |
| `0` | The workflow is ready to advance or complete. Inspect `status`. |
| `2` | No eligible progress is available; inspect blocked reasons. |
| `1` | An input is malformed, inaccessible, or structurally invalid. |

Paths inside a run resolve relative to the run file's directory. Artifact evidence
paths resolve relative to the artifact's directory. Absolute paths, URI schemes,
and escapes through parent directories or symlinks are rejected by the reference
resolver.

JSON inputs and retained evidence must be regular files no larger than 16 MiB.
Pipes, device files, duplicate JSON keys, and oversized files are rejected rather
than read without bounds.

## Evaluate a proposed effect

```sh
python tools/factory.py gate \
  --request examples/gate-request.json \
  --policy examples/policy.json \
  --at 2026-11-19T12:00:00Z
```

The JSON response contains `decision` (`allowed` or `blocked`), `effect`, `scope`,
and `reasons`. Exit `0` means allowed under the supplied inputs, `2` means blocked,
and `1` means malformed or inaccessible inputs.

The policy must come from the trusted host. The evaluator checks exact scoped
grants, expiry, subject identity, evidence age and integrity, required artifact
types, and supported verification/review semantics. An effect without an explicit
policy evidence rule is blocked. A rule may explicitly require no artifacts for
a suitably bounded low-risk action; that still needs the actual scoped grant.

For verification, `required_count` must be a positive integer and
`executed_count` must be at least that count. `failed_count` must be zero,
`skipped_required` must be empty, and test or observation evidence must be cited.
Blocking review findings cannot contradict a passing claim; an accepted-risk
disposition needs an explicit, evidenced waiver. Supplied review-status proof
must identify the current head, establish readiness, and have no pending or failed
required checks. See [artifact semantics](artifacts.md) for the exact fields.

`require_independent_review` applies to a supplied review. Whether a review is
required at all is controlled by `required_artifacts`. Independent-review fields
must contain meaningful identities and an independence basis, and reviewer and
author must differ after whitespace trimming. The host authenticates them.

The command trusts the host to authenticate grants and evidence producers. It
cannot prove that a log was honestly generated or that a named reviewer is a
particular real person. It makes no external changes. The actual adapter must
recheck resource state and enforce the decision immediately before the effect.

## Export standalone packages

```sh
python tools/export_skills.py --output /tmp/sfstack-export
python tools/export_skills.py --output /tmp/sfstack-map \
  --skill sf-map-project
```

Repeat `--skill` to select multiple skills. Omitting it exports the whole catalog.
The destination must be absent or empty. The exporter checks required package
resources and shared-reference freshness, then copies five files per selected
skill: `SKILL.md`, `contract.json`, `references/protocol.md`,
`references/artifact.schema.json`, and `LICENSE`. It does not install into an agent or contact a
service. An invalid request exits nonzero.

## Render a portable agent invocation

```sh
python tools/render_invocation.py \
  --skill sf-clarify-outcome \
  --context examples/invocation-context.json
```

Both arguments are required. The tool reads the selected skill, its contract,
its bundled protocol and output artifact schema, and the supplied JSON context,
then prints a Markdown invocation. It sends nothing to an agent and performs no task execution. The
context is explicitly presented as task data; embedded instructions do not grant
authority. Unknown skills, malformed JSON, and missing files fail nonzero.

The renderer does not certify that the supplied context is complete or trusted.
The host and selected skill must check scope, required inputs, capabilities, and
authorization before acting.

## Normalize an exported tracker item

```sh
python tools/tracker.py \
  --mapping examples/tracker-mapping.json \
  --item examples/tracker-item.json
```

The tool prints a canonical work item using an explicit field and state mapping.
It reads local JSON only and never writes a tracker. The mapping follows
[tracker-mapping.schema.json](../../schemas/tracker-mapping.schema.json); the
result follows [work-item.schema.json](../../schemas/work-item.schema.json).

Field paths use dotted object keys, such as `item.state`; array indexing and
arbitrary expressions are unsupported. The mapping must provide all canonical
fields. Unknown states and missing fields fail explicitly. String or integer
native identities and versions are normalized to strings; Boolean values are
not valid identities or versions. A missing explicit version is not invented.

The normalized item preserves provider identity and original state under
`source`. This read adapter demonstrates semantic portability, not a complete
live-service connector. See [connect a tracker](../how-to/connect-tracker.md) for
write-side guarantees.

## Run regression tests

```sh
python -m unittest discover -s tests -v
```

The tests exercise the implemented validation and reference-tool boundaries.
They are not a substitute for behavioral evaluations of skill quality or
qualification of a production adapter. See [evaluate quality](../how-to/evaluate-quality.md)
and the [contribution guide](../../CONTRIBUTING.md).

## Plan dependency-aware evidence revalidation

```sh
python tools/evidence_impact.py --manifest examples/evidence-impact.json
```

This is advisory static analysis only. It identifies changed input digests and
propagates their effects through declared claim dependencies. A reuse candidate
is not valid evidence for the new subject; existing gates continue to require
matching subjects. See [revalidation](../how-to/revalidate-evidence.md).

## Compare paired agent trials

```sh
python tools/compare_trials.py --input examples/comparative-trials-synthetic.json
```

Rejects duplicate or unpaired trials, then reports descriptive averages and
paired differences for bare, instructions-only, and contracts configurations.
The example data are synthetic and must not be cited as an effectiveness result.
See [comparative evaluation](../how-to/compare-trials.md).

## Execute one effect-free skill through a local adapter

`tools/local_slice.py` checks readiness, invokes a host-provided Python script,
validates the returned artifact and evidence, and writes a new checkpoint.
It is not a sandbox or an external-effect controller. See the
[local slice tutorial](../tutorials/local-slice.md).
