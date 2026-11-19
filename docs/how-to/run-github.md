# Run quality assessment with GitHub Actions and Agentic Workflows

Use the opt-in **sfstack GitHub quality** workflow to assess an open PR in this
repository. Ordinary Actions jobs execute deterministic checks and apply the
quality gate. A reusable [GitHub Agentic Workflow](https://github.github.com/gh-aw/)
uses Copilot to perform `sf-review-change` between those jobs.

This first integration demonstrates the complete contract and evidence handoff:
host inputs → verification → agent review → quality assessment → gate. It uses
the existing sfstack skills and core validators. It does not require a Software
Factory run or generate an implementation before assessing a PR.

## Prerequisites

1. Merge the integration into the repository's default branch. The workflow
   deliberately requires dispatch from that branch so a PR cannot select its own
   controller, policy, or verification plan.
2. Enable GitHub Actions and configure `COPILOT_GITHUB_TOKEN` as a repository
   Actions secret using GitHub's [Copilot engine setup](https://github.github.com/gh-aw/engines/copilot/).
   Use an account entitled to Copilot and the credential type supported by that
   guide. Model execution consumes that account's allowance. The standard
   `GITHUB_TOKEN` alone does not replace this engine credential in this workflow.
3. Choose an open PR whose code you are comfortable executing as ordinary CI.
   The workflow checks Python sfstack changes; it is not a general build system
   for arbitrary languages or an isolation boundary for hostile test programs.

For example, GitHub CLI can prompt for the secret without putting its value into
shell history:

```sh
gh secret set COPILOT_GITHUB_TOKEN --repo grove/sfstack
```

No GitHub App, merge permission, issue writer, or external controller service is
required. The engine credential is passed only to the reusable agent workflow;
candidate verification and final validation run in separate jobs.

## Assess a PR

In **Actions → sfstack GitHub quality → Run workflow**, select the default
branch and enter the PR number. Or use the CLI, replacing `123` with your PR:

```sh
gh workflow run sfstack-quality.yml --repo grove/sfstack --ref main -f pr-number=123
gh run list --repo grove/sfstack --workflow sfstack-quality.yml --limit 5
```

Open the run and its **sfstack quality gate** job. The final step summary reports
the exact head and base, the verification and review verdicts, and any handoff
problem. Download the `sfstack-quality-<attempt>` artifact for the full record.

Only a `passed` assessment makes that gate job succeed. `failed`, `blocked`, and
`inconclusive` fail it; missing artifacts and a failed or skipped agent workflow
cannot become an implicit pass. Producing a valid negative verification report
does not stop the review or consolidation steps, so the failure remains useful
evidence.

**This gate belongs to the dispatched workflow run.** It does not publish a
Check Run on the PR head, automatically reassess later pushes, or configure a
required branch-protection check. Do not select this dispatch job as a required
PR check. Automatic PR triggers and an authoritative PR-head publisher are a
later integration step.

If the PR head or target base advances before finalization, the gate blocks.
Dispatch a new assessment of the new candidate. To retry an infrastructure or
engine failure, select **Re-run all jobs** or dispatch again. Evidence names
include `github.run_attempt`; rerunning only failed jobs cannot borrow earlier
attempts' inputs or reviews and will fail closed when the new inputs are absent.

## What runs

| Job | Work | Boundary |
| --- | --- | --- |
| Pin candidate and contracts | Resolve the PR through GitHub's API, check out its exact head, record its current base and merge base, and prepare the request, change set, specification, test plan, policy, and run. | Controller files come from the dispatched default-branch commit. The diff is merge-base to head; the test candidate is the head. |
| Execute pinned verification | Execute the host-selected checks and create an `sf-verify-change` verification report with retained logs. | No Copilot credential; negative observations are retained. |
| Review through Agentic Workflows | Load the standalone review skill and rendered contract, inspect source and evidence, and submit a bounded JSON response. | Read-only GitHub permissions, no edit tool, no source execution requested, and one custom safe output. |
| sfstack quality gate | Re-read the PR, validate both handoffs, normalize the review, run the core planner and consolidator, then evaluate the effect gate. | Fresh job, original host inputs, deterministic validation; agent output cannot replace policy or authorize a mutation. |

The portable three-node recipe is
[`integrations/github/workflow.json`](../../integrations/github/workflow.json).
Host-created inputs replace the earlier discovery and planning stages: their
scope is explicit, rather than claiming that an agent performed those stages.

The selected criteria in
[`integrations/github/checks.json`](../../integrations/github/checks.json) are:

- `contracts`: `python tools/validate.py` checks packages, schemas, bindings,
  examples, and documentation links.
- `protocol`: `python tools/sync_protocol.py --check` checks bundled resources.
- `regressions`: `python -m unittest discover -s tests -v` runs the regression
  suite. Empty discovery, skipped tests, expected failures, an unavailable
  runner, or an ambiguous test summary cannot pass.

These are required commands, not a claim that arbitrary product requirements
were discovered or that every specialist quality dimension was evaluated.
The agent separately describes engineering quality and criterion conformance.

## Inspect the evidence and authorization decision

The result artifact includes:

| File | Meaning |
| --- | --- |
| `target.json` | Repository, PR, head, base, merge base, run and attempt, selected checks, and diff hash. Its digest is part of the sfstack subject. |
| `run.json`, `run-assessed.json` | Contract-bound checkpoint before and after consolidation. |
| `verification/verification-report.json` and `verification/logs/` | Actual command outcomes, test counts, required check identities, and SHA-256 references to logs. |
| `review/review-report.json` | Host-owned artifact envelope around the validated agent response. |
| `review/submission.json` | The retained safe-output submission when available. |
| `assessment/quality-assessment.json` and `assessment/support/` | Consolidated verdict and original source records with their evidence bytes. |
| `quality-gate.json` | Machine-readable automated verdict. Only `status: passed` has `success: true`. |
| `authorization-gate.json` | Core sfstack effect decision. The pilot has no grants, so even successful quality does not authorize integration. |

The adapter validates the existing artifact schemas, skill producer/version,
typed DAG bindings, evidence hashes, freshness, run/subject identity, and exact
required criterion coverage. The response schema accepts only known evidence
IDs and open findings. It rejects agent-supplied approval claims, waivers,
identity overrides, extra criteria, and altered subjects. Blocking findings and
failed test results survive consolidation even if the agent's overall response
says `passed`.

The policy explicitly sets `require_independent_review: false` for this
**automated assessment pilot**. The result still records
`independence.established: false` and `remediation_authorized: false`. Maintain
your existing human PR review requirements. If you set that policy field to
`true`, the core consolidator correctly returns `inconclusive` until an
authenticated independent-review mechanism is implemented. An account name or
a second model session is not that mechanism.

## Maintain the Agentic Workflow

Edit [sfstack-review.md](../../.github/workflows/sfstack-review.md), then compile
and commit its generated
[sfstack-review.lock.yml](../../.github/workflows/sfstack-review.lock.yml).
The lock file is generated output; do not hand-edit it.

The checked-in compiler identity is
[`.github/aw/compiler.json`](../../.github/aw/compiler.json): `gh-aw v1.2.2`, with
the official Linux binary URL and SHA-256. CI verifies those bytes, compiles in
strict mode, and fails on lock-file or Actions pin-cache drift.

With that version installed as the `gh aw` extension:

```sh
gh aw compile sfstack-review --strict --no-check-update --no-logo
git diff -- .github/workflows/sfstack-review.lock.yml .github/aw/actions-lock.json
```

The standalone binary accepts the same arguments without `gh aw`. Use the
[official installation guide](https://github.github.com/gh-aw/setup/quick-start/)
and keep the compiler version aligned with the pin file. Compilation is not a
live Copilot test; it validates and generates the Actions configuration.

The integration regressions run without GitHub or model credentials:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p test_github_quality.py -v
```

They create small clean Git candidates and execute real passing and failing
tests. The agent replies in these tests are explicitly constructed fixtures;
they validate the handoff and rejection rules, not Copilot's review quality.

## Scope and limits

This is a bounded reference integration. The verifier uses an ordinary fresh
Actions runner, and candidate test code shares its filesystem. Removing job
tokens from the subprocess environment and separating jobs reduces exposure;
it does not turn that runner into a sandbox against deliberately malicious
tests. Log hashes establish that retained bytes have not changed; they do not
authenticate a dishonest test program or prove the semantic truth of its output.
Use stronger execution isolation and protected test oracles before treating
hostile fork code as authoritative verification.

The environment label records the selected Python major/minor; it is not a
hermetic image or dependency attestation. Ubuntu and transitive Python packages
can vary between runs. The head is tested, not a synthesized merge or merge-queue
candidate. No specialist security, accessibility, privacy, performance, or
deployment clearance is implied. The assessment lists omitted dimensions.

Each command has a five-minute timeout. The agent has a ten-minute execution
budget and twenty turns. The controller caps the diff at 8 MiB, requires a clean
checkout without submodules, and accepts a bounded review response. Evidence is
retained as Actions artifacts for fourteen days; download it if a longer audit
history is needed. There are no automatic source edits, PR comments, issues,
merges, or deployments.
