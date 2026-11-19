# Initialize and resume a local quality run

Use [`tools/sfstack.py`](../../tools/sfstack.py) for a local run with ordinary
JSON manifests and retained files. Install the development dependencies first:

```sh
python -m pip install -r requirements-dev.txt
```

For an executable example needing no agent integration, run
`python evals/run_quality_regression.py --output ../sfstack-quality-demo`.
It executes real behavioral checks on disposable fixtures and preserves failed,
passing, skipped, and empty-discovery outcomes. See the
[evaluation guide](../../evals/README.md) for the exact scope and limits.

## Create a run for an existing checkout

```sh
python tools/sfstack.py init --repo ../my-project --out ../my-quality-run \
  --goal "Assess the API behavior and its regression coverage" \
  --environment my-isolated-python
python tools/sfstack.py status --run ../my-quality-run/run.json
```

The checkout must have a committed HEAD and no modified or untracked files.
The output directory must be new and outside the candidate checkout. For an
already checked-out PR, add `--base <base-commit>`; initialization resolves and
records the exact base and head without contacting a provider. Submodules need
an explicit host snapshot and are outside this initializer's scope.

Initialization records the goal, Git commit and tree, environment identifier,
and selected quality dimensions. Their retained JSON is the initial input
digest. This identifies the starting request; it does not attest to installed
dependencies, ignored/generated files, or the runtime environment. The selected
adapter must pin its actual execution inputs, including the test suite, and
reject a changed candidate. Use a new subject/checkpoint when those inputs change.

The new directory contains `run.json`, `workflow.json`, `policy.json`, and the
request with its retained target record. The first ready step is `orient`.
The policy grants no mutations and requires independent review; the offline
summarizer cannot authenticate reviewers, so that requirement can leave the
assessment inconclusive. Choose the policy to reflect the actual use case before
running, rather than changing it to make a result pass.

## Choose a small assessment scope

| Preset | Existing workflow | Policy-required reports |
| --- | --- | --- |
| `baseline` (default) | `quality` | Verification, review, impact |
| `risk` | `quality-risk` | Baseline plus security and compatibility |

Use `init --profile risk` when those additional risks apply. These are two
convenience presets over existing workflows and policies, not a new profile
format. For other risks, extend the workflow using existing skills and add the
report type to `policy.required_quality_reports`. A request can add required
dimensions but cannot remove requirements from the trusted policy. Missing
required coverage prevents clearance.

## Advance a bounded amount of work

```sh
python tools/sfstack.py run --run ../my-quality-run/run.json \
  --adapter-script /path/to/trusted_adapter.py --max-steps 3 --timeout 60
```

The adapter implements the [local invocation contract](../tutorials/local-slice.md).
It receives the skill package path, contract, exact subject, input artifact paths,
and output location. It performs the selected responsibility and writes its
artifact with retained evidence. The runner validates the result before recording
completion. The [Python unittest adapter](../../examples/adapters/README.md) is
a concrete implementation for a ready verification node; other responsibilities
need their own appropriate implementation. There is no bundled general-purpose
coding agent or automatic invention of missing specifications/reviews.

The runner advances at most the explicit step budget. It writes a new
`checkpoint-000N-STEP.json` after each completed step and prints the latest path.
Resume by passing that checkpoint to the same command. No existing manifest or
artifact is overwritten, and no failed step is retried automatically. Live
execution rechecks evidence age before each step. Use one controller per run
directory; this runner has no scheduler or concurrent worker service.

Only effect-free, single-output steps can execute here. Software workflows may
use it for eligible observational steps, but code modification and publication
still require a host with enforcement at the actual tool boundary. An adapter
process is not a sandbox: the host must isolate and trust the executable and the
candidate code it executes.

An interrupted adapter attempt leaves an `.attempt.json` reservation beside its
intended artifact directory. Resuming the same checkpoint stops before dispatching
it again. Inspect whether its process is still running and reconcile any output
before explicitly removing the reservation or choosing a new attempt. The last
completed checkpoint remains available even if a later step fails.

## Read the quality verdict

The runner consolidates automatically when the final quality step is ready;
that step needs no adapter. To consolidate an existing ready checkpoint directly:

```sh
python tools/sfstack.py assess --run ../my-quality-run/checkpoint-0008-review.json
```

Use the actual latest checkpoint path from your run; the number depends on the
selected workflow. This creates an `assessment/` bundle and `run-assessed.json`,
then prints the verdict, evaluated dimensions, findings, and limitations.
Use `--out-dir` and `--out-run` to choose new names for another report.
Add `--json` to any CLI command for machine-readable output. `--workflow` allows
existing manifests to use a workflow outside their directory.

| Exit | Meaning |
| --- | --- |
| `0` | Initialization/status succeeded, or execution/reporting completed with passing quality where a quality assessment exists. |
| `2` | Work is bounded/incomplete/blocked, or the completed quality verdict is failed, blocked, or inconclusive. Read the result. |
| `1` | Invalid inputs, adapter error, or failed output validation; inspect the error and last checkpoint. |

A valid negative quality report is a completed observation. It remains available
to review and consolidation where the workflow permits it, while action gates
continue to reject it as passing proof. `status` reports workflow readiness;
`run` and `assess` also reflect the quality verdict in their exit code.

These local tools do not supply authentication, service-side effects, or broad
agent-effectiveness evidence. They exercise and preserve the factory contracts.
See [cross-run composition](run-quality.md#4-compose-back-into-software-factory-only-at-an-authorized-boundary)
when a separately authorized software run needs the assessment.
