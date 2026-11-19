# Behavioral evaluation and executable regressions

The regression suite in `tests/` checks sfstack's reference tooling. The inventory
seed below can also exercise an agent using the skills. Keep the candidate workspace and
grader separate so the worker receives the task and initial files, not a supplied
repair or grading implementation. Run candidate code only in an isolated
environment with the permissions and resource limits appropriate to that code.

## Inventory boundary case

Copy `cases/inventory-boundary/task.md` and the contents of its `seed/` directory
into an isolated temporary workspace. Give a fresh agent that task and the complete
packages for `sf-diagnose-defect`, `sf-build-change`, and `sf-verify-change`. Let it
derive the small specification, single-item plan, and test plan. Grant local edits
and Python execution in that workspace only. Do not provide the hidden grader or
an expected patch to the worker.

After the worker returns, run the independent public-behavior grader:

```sh
SFSTACK_CANDIDATE_DIR=/absolute/path/to/candidate \
  python -m unittest discover -s evals/cases/inventory-boundary/grading -v
```

Inspect the worker's own evidence as well. A correct final function does not prove
that the agent reproduced the defect, preserved scope, obeyed the budget, or
returned conforming artifacts. Use the [rubric](cases/inventory-boundary/rubric.json)
for those checks. Validate each emitted JSON envelope against
[artifact.schema.json](../schemas/artifact.schema.json) and inspect actual retained
evidence hashes. Record a failed or inconclusive dimension separately.

This seed is small and deterministic. It is suitable for checking basic behavior
and packaging, not for estimating broad engineering effectiveness. Expand the
corpus across project types, languages, failure modes, tools, and missing-capability
conditions before making comparative quality or autonomy claims. Keep held-out
cases separate from authoring examples and record the agent, model, tools, skill
versions, cost, and evaluation conditions for every comparative run.

## Execute the quality handoff with real tests

```sh
python evals/run_quality_regression.py --output /tmp/sfstack-quality-regression
```

Use a new destination. The command creates disposable copies of this known tiny
fixture and uses the [trusted unittest adapter](../examples/adapters/README.md)
through the local execution boundary. It pins candidate and check-directory
digests, executes the six behavior checks in a subprocess, retains raw stdout,
stderr and actual counts, and consolidates the resulting quality evidence.
The candidate under assessment is never repaired during a run: the corrected
candidate is a separate, explicitly prepared input with its own identity.

| Case | Verification | Consolidated quality | Evidence |
| --- | --- | --- | --- |
| Original equality-boundary defect | Failed | Failed | Six checks run; the failing equality assertion survives as a blocking finding. |
| Separate corrected candidate | Passed | Inconclusive | Six passing checks; independent review is not authenticated. |
| Required equality check skipped | Inconclusive | Inconclusive | The omitted check is retained in `skipped_required`. |
| Empty test discovery | Inconclusive | Inconclusive | Zero checks run; missing required IDs remain explicit. |

The exercise also verifies that changing the expected revision or modifying
retained runner output causes evidence rejection. `summary.json` identifies the
case reports and records limitations; the command exits nonzero if any expected
behavior changes. These assertions also run in `tests/test_quality_regression.py`.

Only verification is a real execution result. Planning, scope, and review records
are explicitly labelled regression scaffolding; no live agent or provider is
invoked. The independent-review requirement remains enabled, so a green test run
does not turn the fixture review into quality clearance. This is an executable
integration regression, not a bare-agent versus skills experiment, a held-out
effectiveness result, or evidence of production isolation. Execute unfamiliar
candidate code only in a host-provided sandbox.

## Execute the GitHub bridge failure and repair path

```sh
python evals/run_github_regression.py --output /tmp/sfstack-github-regression
```

This companion regression exercises the same `prepare`, `verify`, `render`, and
`finalize` functions used by the [GitHub integration](../docs/how-to/run-github.md).
It creates a disposable Git repository, commits the known inventory defect, and
runs the six retained behavior checks. It then commits the repair and runs the
same checks under a fresh run identity. Both candidates keep the same PR base;
each assessment records its own exact head, inputs, log hashes, and source reports.

| Candidate | Actual verification | Quality gate | Mutation authorization |
| --- | --- | --- | --- |
| Defective equality boundary | Six tests run; `test_exact` fails. | Failed; the failed verification report survives a positive fixture review. | Denied. |
| Repaired commit | The same six tests pass. | Passed under the automated pilot policy. | Denied. |

`summary.json` links the retained logs and assessments. The command exits nonzero
if the expected failure or recovery disappears. The same exercise runs in
`tests/test_github_regression.py`, and validation CI retains its output as the
`github-regression` artifact.

The PR metadata and positive review are explicitly synthetic inputs. No GitHub
API or Copilot model is invoked, so this checks deterministic evidence handling
and failure propagation, not live PR publication or the agent's ability to find
a defect. The passing case uses the GitHub pilot's automated-review policy;
neither case establishes independent human approval or grants mutation rights.
The separate local quality regression above keeps independent review required
and therefore remains inconclusive for its corrected candidate.

## Execute the bounded Software Factory handoff

```sh
python evals/run_software_regression.py --output /tmp/sfstack-software-regression
```

This regression exercises the actual issue-input preparation, build-contract
rendering, scoped file reconstruction, immutable Git identity, and host
verification used by the [Software Factory](../docs/how-to/run-software-factory.md).
An unfixed inventory proposal fails the six behavioral checks. A separate fixed
proposal passes the same checks with a different candidate commit. Both retain
the original issue and criteria, submission, source bytes, logs, and gate result.
Validation CI publishes these records as `software-regression`.

The selected issue and builder responses are explicitly synthetic. The Git
commits, subprocess checks, and host decisions are real. This demonstrates that
an optimistic builder response cannot override a behavioral failure; it does
not measure live Copilot implementation, GitHub publication, or human approval.

## Initial observed exercise

On 2026-11-19, one isolated agent exercise used the diagnosis, implementation, and
verification skills on this case with CPython 3.12.14. The original three tests
passed. The agent found the rejected equality boundary, added a regression that
failed against the original implementation, made the one-character comparison
correction, and finished with six passing tests. It stayed within three diagnosis
probes and one repair attempt. No external system was contacted by that exercise.

The initial output envelopes failed the repository schema because their check
and evidence identifiers used uppercase letters and their environment identity
used an object where a string was required. This exposed a distribution
gap: the result schema was not included in standalone packages. The packages now
carry the exact schema and explicit output validation instructions. Corrected
reports then passed all three schema validations and all three retained-evidence
inspections without changing the behavioral evidence. The
[observed report](reports/2026-11-19-inventory/summary.json) retains the repair diff
and red/green runner output with documented path normalization. This is an
observed failure and correction, not a claim that the initial exercise passed
every dimension. The exercise establishes neither an advantage over an unskilled
baseline nor compatibility with other agents, trackers, or production systems.

## Comparative results format

Use [the paired-trial comparison guide](../docs/how-to/compare-trials.md)
to record bare-agent, instructions-only, and contracts-and-gates outcomes on
the same cases, agent, tools, and environment. The included comparison JSON is
explicitly synthetic; no comparative experiment has been run by this addition.
