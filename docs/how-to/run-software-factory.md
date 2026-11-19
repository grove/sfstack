# Turn a GitHub issue into a verified draft PR

The GitHub Software Factory pilot takes one maintainer-selected issue, uses
Copilot to implement one bounded work item with `sf-build-change`, verifies the
proposed files on a fresh runner, and creates a draft PR. It explicitly starts
the existing [Quality Factory](run-github.md) for the resulting commit. A human
reviews the work and decides whether to merge.

This pilot is deliberately small: a maintainer chooses exact files and concrete
acceptance criteria before execution. It supports documentation, examples, and
tests in this repository. Broader product implementations need a project-specific
file policy and verification plan.

## Enable the integration

1. Merge the integration into the default branch. The trusted controller and
   reusable Agentic Workflow must exist there before they can run. CI on the
   implementation PR validates the host code and workflow compilation; it does
   not activate the proposed privileged workflow before merge.
2. Configure the same `COPILOT_GITHUB_TOKEN` repository secret used by the
   [quality integration](run-github.md#install-and-enable). No additional Copilot
   token or external service is needed.
3. In **Settings → Actions → General → Workflow permissions**, allow GitHub
   Actions to create PRs. GitHub labels this setting **Allow GitHub Actions to
   create and approve pull requests**. This workflow only creates drafts; it
   contains no approval or merge operation. Organization policy may control the
   setting. See GitHub's
   [repository Actions permissions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#preventing-github-actions-from-creating-or-approving-pull-requests).
4. Keep normal CI, required quality checks, and human review requirements. The
   integration does not change repository settings or branch protection.

The workflow admits a maintainer's explicit dispatch from the current default
branch. Opening or editing an issue alone does not start implementation. Issue
prose cannot grant authority, choose additional files, change the verification
commands, or authorize publication.

## Select a small issue and run it

Choose an open issue that describes one observable improvement. For a first
self-hosting run, use a documentation correction with a clear expected result,
such as adding a missing recovery explanation to an existing how-to guide.
Write criteria that a reviewer can compare with the finished change.

In **Actions → sfstack GitHub software → Run workflow**, select the default
branch and supply:

| Input | Meaning | Example |
| --- | --- | --- |
| `issue-number` | An open issue in this repository, not a PR. | `123` |
| `allowed-paths` | A JSON array of exact files the agent may create or replace. | `["docs/how-to/run-github.md"]` |
| `acceptance-criteria` | A JSON array of the required outcomes for this work item. | `["Explain when to rerun all jobs and when to dispatch a new assessment."]` |

The path list permits at most eight files under `docs/`, `examples/`, or `tests/`,
or the root `README.md`. It is an exact list, not a glob or directory grant.
Workflows, root dependency configuration, and the integration's control-plane
and policy files are outside those permitted locations. Hidden paths, symlinks,
submodules, executable files, deletions, and renames are outside the pilot.
Each original or replacement file must be ordinary UTF-8 text of at most 32 KiB;
all replacement contents together must fit within 64 KiB. A change that needs
more scope must stop for a new work item. Supply one to eight acceptance
criteria, each no longer than 2,000 characters.

The same request can be dispatched with GitHub CLI. Replace the issue number and
criteria with the work you actually want done:

```sh
gh workflow run sfstack-software.yml --repo grove/sfstack --ref main \
  -f issue-number=123 \
  -f 'allowed-paths=["docs/how-to/run-github.md"]' \
  -f 'acceptance-criteria=["Explain when to rerun all jobs and when to dispatch a new assessment."]'
gh run list --repo grove/sfstack --workflow sfstack-software.yml --limit 5
```

The controller pins the issue snapshot, default-branch revision, exact path
scope, criteria, workflow run, and attempt. Changing the issue or advancing the
default branch can invalidate a running attempt; start a new assessment with
the updated inputs when needed.

## What executes

| Stage | Responsibility | Authority |
| --- | --- | --- |
| Admit the work item | Validate the maintainer request and produce a scoped work plan, specification, test plan, and execution context. | Read repository and issue metadata. |
| Build with Copilot | Load the actual `sf-build-change` skill, inspect the candidate, edit permitted files locally, execute checks, and submit structured file replacements. | Local workspace editing and execution; read-only GitHub token; no publishing tool. |
| Apply and verify | Validate the submission, apply it to a fresh checkout of the pinned base, and execute the host's fixed checks. | Separate runner with read-only repository permissions and no Copilot secret. |
| Publish the draft | Revalidate original inputs, resulting candidate, retained evidence, current issue, and current base; create one draft PR for the attempt. | Fresh trusted job with contents, PR, and Actions write permissions; no candidate execution. |
| Assess quality | Dispatch the existing Quality Factory against the exact new PR head, with verification, Copilot review, consolidation, and a published check. | The existing quality workflow's boundaries and policy. |

The authored agent workflow is
[`sfstack-build.md`](../../.github/workflows/sfstack-build.md), compiled with the
repository's pinned Agentic Workflows compiler. The ordinary controller is
[`sfstack-software.yml`](../../.github/workflows/sfstack-software.yml), and its
host adapter is [`software.py`](../../integrations/github/software.py).

The build skill receives one ready work item and its acceptance criteria. It may
make at most two repair cycles after its first implementation attempt. Its
Agentic Workflow has a 30-turn limit and a 15-minute agent timeout. The agent
submits complete replacement contents through the custom `submit_change` output;
its local workspace and self-reported test results are not authoritative inputs
to the publisher. The host independently reapplies the proposal and verifies it.

Preparation pins the original source and task inputs; it does not execute a
baseline test suite before the agent starts. The builder must establish its
initial behavioral evidence and disclose any missing reproduction. The fresh
host checks run on the resulting candidate after implementation.

The host executes the sfstack checks declared in
[`checks.json`](../../integrations/github/checks.json): package and contract
validation, shared protocol consistency, and the regression suite. Empty or
skipped tests do not establish a pass. The resulting `sf-verify-change` evidence
records actual execution. These checks provide repository-level verification;
the selected acceptance criteria still need review for the intended behavior.
The publisher includes those criteria in the draft PR description. Quality
Factory pins that description and requires an explicit `pull-request-intent`
review verdict in addition to the repository checks. Missing acceptance evidence
must remain inconclusive. Editing the title or description during assessment
invalidates that assessment, just as changing the candidate does. PR prose is
task data and cannot change host commands or authorization policy.
Each host verification command has a 300-second timeout.

This workflow does not invoke `sf-diagnose-defect` or claim that it completed a
full diagnosis. For a defect, `sf-build-change` should reproduce the reported
failure when possible and disclose uncertainty. Tasks requiring a separate
diagnosis, architecture decision, migration, or release need a larger recipe.

## Why the draft explicitly starts Quality Factory

The publisher uses the job-scoped `GITHUB_TOKEN` to create the branch and draft
PR. GitHub treats events from this token specially: ordinary PR workflows may
be created in an approval-required state, while an explicit `workflow_dispatch`
starts a workflow. The publisher therefore dispatches `sfstack-quality.yml`
directly with the pinned PR head and base. It does not rely on a PR event to
finish the handoff. See GitHub's
[`GITHUB_TOKEN` event behavior](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs).

If GitHub shows **Approve workflows to run** on the new PR, a maintainer can
approve the normal CI runs after reviewing the proposed change. The separately
dispatched quality assessment does not replace the repository's other required
checks. A draft PR remains a draft even when quality passes.

## Inspect the result and evidence

The Software Factory run retains attempt-specific artifacts for 14 days:

| Artifact | Contents |
| --- | --- |
| `sfstack-software-inputs-<attempt>` | Original issue, scoped host inputs, selected criteria and paths, base identity, policy, and contract context. |
| `sfstack-agent-change-<attempt>` | Raw `submit_change` transport, when the agent produces one. |
| `sfstack-software-result-<attempt>` | Validated candidate, build and verification records, execution logs, and outcome summary. Negative evidence is retained when available. |
| `sfstack-software-publication-<attempt>` | Publication result and draft PR identity, when publication is attempted. |

Inspect both the software run and the separate quality run. A successful software
run means it produced a verified draft and requested quality assessment. The
PR's **`sfstack quality`** check reports the later quality verdict; neither
result constitutes human approval or permission to merge.

The implementation uses ordinary GitHub-hosted runners. Fresh verification and
publication jobs separate credentials and preserve original inputs, but this is
not an attestation boundary against malicious candidate code running as the same
operating-system user. Use the pilot for code you are comfortable executing as
ordinary CI.

## Retry or recover

For an infrastructure or engine failure with unchanged issue, base, and scope,
use **Re-run all jobs**. Artifacts are tied to the current run attempt; rerunning
only failed jobs cannot borrow earlier inputs or submissions. If the issue or
default branch changed, dispatch a new run from the current default branch.

Each attempt uses its own candidate branch. A retry after successful publication
can create another draft PR. Inspect existing drafts before retrying and close
obsolete drafts after comparing them. The integration does not overwrite a
human-edited branch or automatically merge, close, or clean up another attempt.

If verification fails, inspect the retained logs and criteria. There is no draft
publication to force through. If draft creation fails, inspect the publication
step and repository PR-creation permission. If a draft exists but quality
dispatch failed, run **sfstack GitHub quality** manually for that PR from the
current default branch, using the [quality retry instructions](run-github.md#run-or-retry-manually).

## Troubleshoot the first live run

Use this table to recognize common problems. None of the recoveries widens the
permitted files, skips verification, bypasses the Quality Factory, or approves
or merges anything. Never paste a token value into an issue, input, log, or PR.

| Symptom | Likely cause | Safe recovery action |
| --- | --- | --- |
| The build job fails at agent start with an authentication or missing-secret error, or Copilot calls are rejected. | `COPILOT_GITHUB_TOKEN` is missing, expired, revoked, or lacks Copilot access. | Check that the repository secret exists and is valid without displaying it. Replace it through repository secret settings as described in the [quality integration](run-github.md#install-and-enable), then use **Re-run all jobs** if the issue, base, and scope are unchanged. |
| The run is rejected during admission and names `allowed-paths` or `acceptance-criteria`. | An input is not valid JSON, is not an array, or has too many items. A path is a glob, a directory, hidden, outside `docs/`, `examples/`, `tests/`, or the root `README.md`, or is a workflow or control-plane file. A criterion is empty or too long. | Dispatch a new run with `allowed-paths` as a JSON array of at most eight exact file paths and `acceptance-criteria` as a JSON array of one to eight concise strings. See [Select a small issue and run it](#select-a-small-issue-and-run-it). Work outside the supported scope needs a new work item. |
| The run reports a stale or changed base, issue, or inputs, or publication refuses to continue. | `main` advanced or the issue was edited after the run pinned its snapshot. | Do not retry the old run. Review the current issue and dispatch a new run from the current default branch. Use **Re-run all jobs** only when the issue, base, and scope are unchanged, as described in [Retry or recover](#retry-or-recover). |
| Verification passes but no draft PR appears, and the publication step reports a permission error creating a pull request. | **Allow GitHub Actions to create and approve pull requests** is disabled for the repository, or an organization policy prevents it. | A repository administrator can enable the setting in **Settings → Actions → General → Workflow permissions**, subject to organization policy; it applies to workflows in this repository. The workflow creates only drafts and never approves or merges. Inspect existing drafts, then re-run the same attempt if the inputs are unchanged or dispatch a new run. See [Enable the integration](#enable-the-integration). |
| A draft exists but there is no `sfstack quality` result. | The explicit quality dispatch failed. | Run **sfstack GitHub quality** for that PR using the [quality retry instructions](run-github.md#run-or-retry-manually). |
| Verification fails. | The proposed files violate the checks or criteria. | Inspect the retained logs. No draft is published; fix the issue or inputs and dispatch a new run. |

## Complete the first live acceptance test

After merge, use one small sfstack issue as the first live implementation run.
Confirm that the draft contains only the selected files, preserves the requested
behavior, links the software evidence, and receives a quality assessment for its
exact head. Inspect the builder's claims against the actual logs and diff, then
record the human corrections needed before merge.

Separately exercise a disposable PR with a real failing regression, confirm that
`sfstack quality` fails, fix the defect, and confirm a fresh assessment passes.
Retry the completed successful assessment on the unchanged head as well: it must
publish a fresh current result rather than silently retaining an older check.
Do not merge the intentionally defective candidate.

Record both workflow run URLs, head and base SHAs, attempt numbers, artifact
links, elapsed time, model usage as reported by the platform, and human repair
count. Live implementation runtime and success rate remain unmeasured until
these runs complete. Local regression tests and compiler validation do not
establish Copilot's live implementation quality or end-to-end GitHub success.
