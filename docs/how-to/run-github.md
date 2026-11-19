# Run quality assessment with GitHub Actions and Agentic Workflows

The GitHub integration automatically assesses open, same-repository PRs targeting
the default branch and publishes **`sfstack quality`** on the exact PR head.
Ordinary Actions jobs execute deterministic checks and apply the quality policy.
A reusable [GitHub Agentic Workflow](https://github.github.com/gh-aw/) uses
Copilot to perform `sf-review-change` between those jobs.

The complete handoff uses existing sfstack contracts and validators: host inputs,
verification, agent review, consolidated assessment, and a published quality
check. Quality assessment can start directly from a PR; it does not require a
Software Factory run or an agent-generated implementation.

## Install and enable

1. Merge the integration into the repository's default branch. Automatic event
   routing and the trusted controller must exist there before they can run.
   A PR changing these files can validate their code and compilation, but cannot
   activate its own privileged controller before merge.
2. Enable GitHub Actions and configure `COPILOT_GITHUB_TOKEN` as a repository
   Actions secret using GitHub's
   [Copilot engine setup](https://github.github.com/gh-aw/engines/copilot/).
   Use an account entitled to Copilot and the credential type supported by that
   guide. Model execution consumes that account's allowance. The standard
   `GITHUB_TOKEN` supplies repository API access; the Copilot engine needs its
   separate credential.
3. Keep the repository's normal CI and human review requirements. This pilot
   executes sfstack's Python checks on an ordinary Actions runner. Use it for
   candidate code you are comfortable running as ordinary CI.

GitHub CLI can prompt for the secret without putting its value into shell history:

```sh
gh secret set COPILOT_GITHUB_TOKEN --repo grove/sfstack
```

No additional GitHub App installation or external controller service is required.
Only the reusable review workflow receives the Copilot credential. Candidate
verification has a read-only repository token and no Copilot secret. Check
publication and event routing use separate jobs with narrowly declared write
permissions.

The default branch is currently `main`. If it is renamed, update the `push`
branch filter in
[sfstack-quality-events.yml](../../.github/workflows/sfstack-quality-events.yml)
as well as any other repository workflows using that branch name. Runtime
eligibility checks resolve the actual default branch through GitHub's API.

## Normal PR flow

Opening, reopening, updating, editing, or marking an eligible PR ready for review
starts a small **sfstack PR signal** workflow. The trusted **sfstack quality
events** coordinator resolves the current PR through GitHub's API, queues its
check, and dispatches **sfstack GitHub quality** from the default branch.
Editing a PR's title or description can therefore cause another review even when
its head SHA has not changed.

The PR's **`sfstack quality`** check shows queued or running while assessment is
in progress. Its final details identify the candidate and base commits, the
workflow attempt, and the workflow summary. Passing results also link directly
to the retained evidence bundle; negative results include the same link when an
artifact is available. The linked workflow and its **sfstack quality gate**
summary explain failures, and the run's artifacts retain whatever evidence could
be produced.

Only a `passed` assessment from a successful trusted gate can publish a
successful check. `failed`, `blocked`, and `inconclusive` results publish failure.
Missing artifacts, stale identities, and unsuccessful or absent agent review
cannot become an implicit pass. A valid negative verification report is retained
and passed through review and consolidation, so failed tests remain evidence.

When `main` advances, the coordinator queues fresh assessments for open
same-repository PRs targeting it. GitHub may continue to report an older
`pull_request.base.sha` even after that branch advances: sfstack resolves the
current default-branch ref separately, preserves the API-reported base SHA as
`base.reported_sha` in its normalized PR snapshot, and pins the live ref as
the actual assessment base. The final quality gate refreshes that same ref and
rejects genuine head or branch-tip changes.

GitHub may also omit the PR association from an authenticated `workflow_run`
event. The coordinator then finds an unambiguous same-repository open PR by
matching both the signal's exact head SHA and branch name against GitHub's
current pull request data; ambiguous matches cannot dispatch.

 Queuing replaces any previous result on the
same PR head with a pending check. The controller pins the PR head, current base,
and current default-branch policy revision. It rechecks these identities before
publishing success. Superseded runs may finish, but cannot overwrite a check
owned by a newer request or attempt. Separate run concurrency groups also keep
a delayed old dispatch from cancelling newer work before its ownership is checked.

Fork PRs and PRs targeting another branch are outside this integration, including
manual dispatch. The signal and coordinator do not assess them. Existing
unprivileged repository CI may still run on those PRs. Do not weaken the trusted
controller checks to add fork support; that needs a separate execution and
credential design.

## Run or retry manually

In **Actions → sfstack GitHub quality → Run workflow**, select the default
branch and enter the PR number. Leave the optional expected head, expected base,
and request identity empty; the coordinator uses those fields for automatic
dispatch. The controller resolves a fresh snapshot for a manual run.

Or use the CLI, replacing `123` with the PR number:

```sh
gh workflow run sfstack-quality.yml --repo grove/sfstack --ref main -f pr-number=123
gh run list --repo grove/sfstack --workflow sfstack-quality.yml --limit 5
```

Use **Re-run all jobs** to retry an infrastructure or engine failure while the
head, base, and controller policy are unchanged. If they have advanced, dispatch
a new run from the current default branch. An old workflow revision is not
allowed to assess a newer policy revision.

Artifacts include `github.run_attempt` in their names. Rerunning only failed jobs
cannot borrow an earlier attempt's inputs, review, or publication record and
will fail closed when fresh inputs are absent. The event coordinator observes
controller starts and completions, invalidates previous-attempt ownership, and
closes incomplete owned checks on the current eligible PR head as failures after
cancellation or interruption. Checks on an obsolete head or a closed PR may
remain pending as historical records; they cannot approve the current candidate.
Recovery never turns incomplete evidence into success. If event delivery or
publication itself fails, the check may remain pending; inspect the coordinator
run and dispatch a fresh assessment.

The custom check's details link leads to the controller run. Use that run's
**Re-run all jobs** control or the manual command above when retrying; this
integration does not implement a separate `check_run.rerequested` handler.

## Make the check required

After the post-merge smoke test below, configure the default branch's ruleset or
branch protection to require the check named exactly **`sfstack quality`**.
Where GitHub offers an expected source, select **GitHub Actions**. Also enable
**Require branches to be up to date before merging** and retain existing test
and human approval requirements.

The published check is separate from the controller job named **sfstack quality
gate**. Select the published `sfstack quality` check for the PR requirement. The
controller's ordinary jobs are associated with its default-branch dispatch.

Strict up-to-date protection matters because GitHub event delivery and check
updates are asynchronous. A base push can occur just after a passing assessment;
the repository rule closes that interval until the branch is updated and fresh
checks pass. The integration does not configure repository settings itself.
See GitHub's
[required status check guidance](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging).

This integration tests the PR head. It has no `merge_group` trigger and does not
assess a synthesized merge-queue candidate. Add that distinct subject and its
verification before enabling a merge queue for this check.

## What runs and where authority lives

Three entry-point workflows separate event handling from candidate execution:

| Workflow | Purpose | Boundary |
| --- | --- | --- |
| [sfstack-pr-signal.yml](../../.github/workflows/sfstack-pr-signal.yml) | Signal eligible PR activity. | No checkout, artifacts, secrets, or repository permissions. Its GitHub run metadata is only a hint to the coordinator. |
| [sfstack-quality-events.yml](../../.github/workflows/sfstack-quality-events.yml) | Resolve current PRs, dispatch assessments, refresh after base pushes, and reconcile interrupted checks. | Runs trusted default-branch code, verifies source workflow identity through the API, and handles metadata only. Dispatch can write Actions and checks; reconciliation can write checks. |
| [sfstack-quality.yml](../../.github/workflows/sfstack-quality.yml) | Pin inputs, verify, call the review workflow, consolidate, and publish. | All controller files come from its immutable default-branch revision. Only the start and publication jobs can write checks. |

The controller's jobs have distinct responsibilities:

| Job | Work | Boundary |
| --- | --- | --- |
| Start the PR quality check | Resolve and retain PR metadata, validate eligibility and controller freshness, and acquire the PR-head check. | Metadata only; no candidate checkout. |
| Pin candidate and contracts | Check out the exact head and prepare the request, change set, specification, test plan, policy, and run. | Host-selected controller and checks; the diff is merge-base to head. |
| Execute pinned verification | Execute the selected checks and retain an `sf-verify-change` report and logs. | Separate fresh runner; read-only repository permissions and no Copilot credential. |
| Review through Agentic Workflows | Render the review skill and contract, inspect source and evidence, and submit bounded JSON. | Read-only GitHub permissions, no edit tool, no candidate execution requested, and one custom safe output. |
| sfstack quality gate | Re-read the PR, validate handoffs, consolidate the quality assessment, and evaluate the core effect gate. | Fresh job and original host inputs; agent output cannot replace policy. |
| Publish the PR quality check | Validate the successful gate, retained result identity, artifact provenance, current PR, and check ownership. | Fresh metadata job; never executes candidate code or agent output. |

Every metadata writer uses the same
[queued concurrency group](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
with `queue: max`. This serializes check ownership changes without the usual
single-pending-job replacement. GitHub currently caps such a queue at 100 jobs;
queue exhaustion requires operational recovery, not bypassing the quality gate.

The coordinator uses
[`workflow_run`](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)
for privilege separation and
[`GITHUB_TOKEN`-initiated workflow dispatch](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs)
to start the trusted controller. It does not use `pull_request_target`; GitHub's
[security guidance](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)
explains that event's privileged context and current public-repository policy.

The portable quality recipe remains
[`integrations/github/workflow.json`](../../integrations/github/workflow.json).
Host-created inputs have an explicit scope; they do not claim that an agent
performed earlier discovery or planning stages. The selected criteria in
[`checks.json`](../../integrations/github/checks.json) are:

- `contracts`: `python tools/validate.py` checks packages, schemas, bindings,
  examples, and documentation links.
- `protocol`: `python tools/sync_protocol.py --check` checks bundled resources.
- `regressions`: `python -m unittest discover -s tests -v` runs the regression
  suite. Empty discovery, skipped tests, expected failures, an unavailable
  runner, or an ambiguous test summary cannot pass.

These commands cover the declared sfstack criteria. They do not discover every
product requirement or establish specialist quality clearance. The agent's
response separately describes engineering quality and criterion conformance.

## Inspect evidence and authorization

Download `sfstack-quality-<attempt>` from the controller run for the complete
assessment. Other attempt-specific artifacts retain the original host inputs,
verification, raw review submission, publication request, and publication result.

| File in the quality bundle | Meaning |
| --- | --- |
| `target.json` | Repository, PR, head, base, merge base, run and attempt, selected checks, and diff hash. Its digest is part of the sfstack subject. |
| `run.json`, `run-assessed.json` | Contract-bound checkpoint before and after consolidation. |
| `verification/verification-report.json` and `verification/logs/` | Actual command outcomes, test counts, required check identities, and SHA-256 log references. |
| `review/review-report.json` | Host-owned artifact envelope around the validated response. |
| `review/submission.json` | Retained agent safe-output submission when available. |
| `assessment/quality-assessment.json` and `assessment/support/` | Consolidated verdict and original source records with retained evidence bytes. |
| `quality-gate.json` | Automated verdict. Only `status: passed` has `success: true`. |
| `authorization-gate.json` | Core sfstack effect decision. The policy has no mutation grants even when quality passes. |

The adapter validates artifact schemas, producer/version, typed DAG bindings,
evidence hashes, freshness, run/subject identity, and exact criterion coverage.
The review schema allows only known evidence IDs and open findings. It rejects
agent-supplied approvals, waivers, identity overrides, extra criteria, and altered
subjects. Blocking findings and failed tests survive consolidation even when
the response's overall status says `passed`.

The publisher also rechecks the age of original inputs and required source
reports against the policy's evidence lifetime. Once published, a passing GitHub
check is a snapshot: it does not automatically expire when that lifetime elapses
without a new event. A requirement to reassess solely because time has passed
needs a separate scheduled or merge-time enforcement mechanism.

The pilot policy explicitly sets `require_independent_review: false`. Assessment
still records `independence.established: false` and
`remediation_authorized: false`. If that policy field is set to `true`, the core
consolidator returns `inconclusive` until an authenticated independent-review
mechanism exists. An account name or another model session does not establish
that independence. Publishing a GitHub check is a narrow host operation; it does
not grant the assessed change permission to merge, modify source, or deploy.

## Validate after merging

The new automatic path becomes active only after these workflows reach the
default branch. Use an open same-repository PR or create a disposable pilot PR:

1. Push a small acceptable change and observe **sfstack PR signal**, the
   coordinator, and the dispatched controller. Verify that `sfstack quality`
   appears on the PR's exact head and links to its assessment evidence.
2. Add a deliberately failing unittest on the disposable branch. Confirm the
   verification report and consolidated assessment fail, and the published
   check blocks the PR. Inspect the retained failing assertion.
3. Remove the deliberate failure in a new commit. Confirm a fresh assessment
   uses that new head and can pass after both required reports pass. Keep the
   failed and repaired run links as evidence; do not merge the deliberate defect.
4. Push another commit while a run is active, or cancel a pilot controller run.
   Confirm obsolete work cannot publish success for the new head and incomplete
   owned checks close as failures. Retry through **Re-run all jobs** or a fresh
   manual dispatch.
5. Enable the required check and strict up-to-date rule after reviewing those
   results. A normal later `main` push exercises base-change reassessment.

This proves the live event, credential, evidence, and publication path. A failing
test proves deterministic failure propagation; it does not prove that Copilot
independently discovered the defect. To measure review effectiveness separately,
use held-out changes with known defects that the existing tests do not reveal,
and inspect the agent's finding and supporting evidence before the repair.

## Maintain and test the integration

Edit [sfstack-review.md](../../.github/workflows/sfstack-review.md), then compile
and commit its generated
[sfstack-review.lock.yml](../../.github/workflows/sfstack-review.lock.yml).
The lock file is generated output. The compiler identity in
[`.github/aw/compiler.json`](../../.github/aw/compiler.json) pins `gh-aw v1.2.2`,
the official Linux binary URL, and its SHA-256. CI checks the binary, compiles in
strict mode, and rejects lock-file or Actions pin-cache drift.

With that version installed as the `gh aw` extension:

```sh
gh aw compile sfstack-review --strict --no-check-update --no-logo
git diff -- .github/workflows/sfstack-review.lock.yml .github/aw/actions-lock.json
```

The standalone binary accepts the same arguments without `gh aw`. Follow the
[official installation guide](https://github.github.com/gh-aw/setup/quick-start/)
and keep its version aligned with the pin. Compilation validates configuration;
it does not invoke Copilot.

Run the integration regressions without GitHub or model credentials:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_github*.py' -v
python evals/run_github_regression.py --output dist/github-regression
```

Use a new output directory. The
[GitHub bridge regression](../../evals/README.md#execute-the-github-bridge-failure-and-repair-path)
commits a known inventory defect, executes six real checks, commits its repair,
and reruns the same checks. Its deliberately positive review fixture cannot
override failed verification. CI retains the failed and fixed reports, log hashes,
and assessments in the `github-regression` artifact. This exercises actual Git
candidates and the evidence pipeline; the PR metadata and review are labelled
fixtures. It calls neither GitHub nor Copilot and does not establish live
publication or model defect-detection effectiveness.

## Scope and limits

Candidate tests run on an ordinary fresh Actions runner and share its filesystem.
Separating jobs and removing credentials from subprocess environments reduces
exposure; it does not make the verifier a sandbox against deliberately malicious
tests. Log hashes preserve retained bytes but do not authenticate a dishonest
test program or establish the semantic truth of its output. Stronger execution
isolation and protected test oracles are needed before hostile code can provide
authoritative verification.

The environment label records Python major/minor. It is not a hermetic image or
dependency attestation: Ubuntu images and transitive packages can change. The
assessment covers the PR head and declared criteria, without specialist
security, accessibility, privacy, performance, deployment, or merge-queue
clearance. Keep those requirements explicit in repository policy and review.

Each verification command has a five-minute timeout. The agent has a ten-minute
execution budget and twenty turns. The controller caps the diff at 8 MiB,
requires a clean checkout without submodules, and accepts a bounded response.
Actions artifacts are retained for fourteen days; download them when longer
audit retention is needed. The integration publishes checks and dispatches
assessments. It does not edit source, post PR comments, open issues, merge, or
deploy.
