# Assess a GitHub pull request

The GitHub Software Factory and Quality Factory are maintained in
[`grove/factory`](https://github.com/grove/factory). Their controller, Actions
workflows, operational documentation, and recovery tests have moved there.

Continue with the [factory guide](https://github.com/grove/factory/blob/main/docs/how-to/run-github.md).

sfstack's **portable package** supplies skills, schemas, recipes, and the
[versioned contract CLI](../reference/public-cli.md). That package has no
GitHub credentials, event routing, draft publisher, or check-run owner. This
repository's thin GitHub Actions workflows only forward authenticated local
events; the actual host runs from a pinned Factory revision and consumes the
installed public sfstack interface.

## Initial manual sfstack-to-factory Quality pilot (historical)

The original manual-only pilot did not copy the GitHub factory controllers
or install automatic PR event coordination. The current automatic setup is
shown below; the controller still lives only in Factory. The trusted GitHub Actions caller
at [`.github/workflows/sfstack-quality.yml`](../../.github/workflows/sfstack-quality.yml)
invokes the reusable Quality Factory from
[`grove/factory`](https://github.com/grove/factory) at the immutable
revision `4078dd9b529debf78efba998cd00b18e5b81fb53`.

After the caller is reviewed and merged to sfstack's default branch:

1. Ensure the `COPILOT_GITHUB_TOKEN` Actions secret exists in **sfstack**,
   has the entitlement required by the [factory quality guide](https://github.com/grove/factory/blob/main/docs/how-to/run-github.md),
   and does not belong to an untrusted PR.
2. In **sfstack → Actions → sfstack GitHub quality (manual via factory) →
   Run workflow**, select `main` and enter the **open** sfstack PR number.
3. Inspect the resulting GitHub Actions run, independent verification evidence,
   and the exact-head `sfstack quality` check. A failed, skipped, missing,
   stale, or inconclusive assessment is **not** a merge approval. Do not
   execute untrusted PR code without an appropriate isolated runner.

The caller has no `pull_request`, `pull_request_target` or `push` trigger.
It uses the exact workflow filename and display title that Factory authenticates.
Factory's own code, contracts and nested Copilot review are checked out at the
immutable called-workflow SHA; `GITHUB_TOKEN`, the candidate revision, and
the published quality check belong to `grove/sfstack`.

**Original pilot scope:** one manual Quality assessment, prior to automatic
PR event support. The current setup remains caller-scoped and is not a central
cross-repository service or Software Factory. A normal factory `checks.json` currently runs the
candidate's Python unittest suite; a future generalized target needs a
maintainer-reviewed project-specific verification plan. A green check alone
does not enforce GitHub branch protection, required up-to-date CI, or an
independent human approval. Those settings and a controlled live acceptance
exercise remain separate acceptance work in
[factory #1](https://github.com/grove/factory/issues/1).

Upgrades require a reviewed PR bumping the same full Factory SHA in both callers;
never switch the call to a mutable branch or `latest`.

## Failed-before-jobs diagnostic (21 November 2026)

The [first manual caller run #44916611652](https://github.com/grove/sfstack/actions/runs/44916611652)
failed in about two seconds with **zero jobs**, no verification, and no Copilot
invocation. The public Actions API exposes a generic failure conclusion but
not the UI's precise workflow-creation error. The configured token cannot be
judged from this run because no credential-consuming step started.

No-agent diagnostic push runs confirmed that the same pinned Factory
review workflow resolves, the nested Quality workflow resolves, and the
full Quality controller starts jobs when invoked from a non-default branch.
That invocation correctly **failed closed at its branch guard** before any
candidate, model, or publication step. The diagnostic run was not a
successful Quality assessment.

This follow-up moves the caller's default-branch condition to a small
unprivileged **preflight job** and makes the reusable call depend on its
success, while Factory retains its own independent branch/run provenance
checks. If server-side validation still rejects the call before jobs,
inspect the exact red error banner on the Actions run page; do not rerun
Copilot blindly or weaken checks and publishing permissions.

## Numeric workflow_dispatch input forwarding

The first two manual requests for PR #37,
[runs 44916611652](https://github.com/grove/sfstack/actions/runs/44916611652)
and [44917531606](https://github.com/grove/sfstack/actions/runs/44917531606),
failed at workflow creation; the second reached the caller's credential-free
preflight but created **no Factory jobs**. No quality or Copilot result was
produced. The Actions REST API does not expose the workflow error banner.

An independent, no-agent test invoked the same pinned Factory workflow with a
literal numeric PR input and a preflight dependency, and the Factory jobs
**were created**, then failed closed on the test branch as intended:
[run 44917753151](https://github.com/grove/sfstack/actions/runs/44917753151).
The manual caller previously forwarded the numeric `workflow_dispatch` input
directly, `pr-number: ${{ inputs.pr-number }}`. GitHub's known
[runner issue #2848](https://github.com/actions/runner/issues/2848) documents
this exact failure mode and the `fromJSON` workaround. The caller now uses
`pr-number: ${{ fromJSON(inputs.pr-number) }}` to hand the called workflow
a true number, retaining the number input's UI validation and the pinned
Factory revision.

This is a targeted, evidence-backed compatibility fix. It must still be
confirmed with a new manual Quality run on `main`; CI alone does not prove
the live handoff. If another pre-job error occurs, capture the red GitHub
workflow-level message verbatim before further changes.

## First live cross-repository reviewer activation (21 November 2026)

The [first run that reached Factory's real reviewer](https://github.com/grove/sfstack/actions/runs/44918424600)
confirmed manual launch, exact-head admission of draft PR #37, the
pinned sfstack package, substantive independent test execution, and the
caller-owned `COPILOT_GITHUB_TOKEN` secret.

It then failed **before executing an agent** because the compiled gh-aw
reviewer attempted to read `.github/workflows/sfstack-review.md` from
the caller's empty workspace. The exact-head `sfstack quality` check
was correctly published as **failure**.

The new pinned Factory revision, `4078dd9b529debf78efba998cd00b18e5b81fb53`, embeds the
author-reviewed instructions in the compiled gh-aw lock file and checks
out the Factory controller at its called workflow SHA rather than the
caller main SHA. This pin must be reviewed and merged **after**
[Factory PR #4](https://github.com/grove/factory/pull/4).

After merging both PRs, manually run
[`sfstack-quality.yml`](../../.github/workflows/sfstack-quality.yml)
from `main` against **open draft PR #37**, then inspect the newly
published check, verified exact head and full review output. Do not
merge PR #37 merely to exercise Quality, do not reuse a failed run as
positive evidence, and keep remaining recovery and merge-rule
acceptance open.

## Automatic PR Quality using reusable Factory workflows

**Current implementation:** Three small Actions workflows live in
`grove/sfstack`, but the actual coordinator, verifier, Copilot reviewer,
evidence gate and check publisher still live in [`grove/factory`](https://github.com/grove/factory).
All called workflows are pinned to the same reviewed Factory commit,
`4078dd9b529debf78efba998cd00b18e5b81fb53`. No `npx skills` install, local Factory code copy, or
central cross-repository credential is needed; the reviewed Factory wheel
already bundles the canonical sfstack skills and contracts.

- `.github/workflows/sfstack-pr-signal.yml`: responds to eligible
  same-repository `pull_request` events with **no token permissions**, no
  checkout, and no artifact. Fork PRs are intentionally excluded.
- `.github/workflows/sfstack-quality-events.yml`: default-branch
  `workflow_run`/ `push` caller for Factory's authenticated coordinator.
  Its dispatch job re-reads PR identity and checks via GitHub before a bounded
  `workflow_dispatch` of Quality. The underlying Factory code is loaded
  from the pinned **callee** SHA; the target retains its own GitHub run,
  token, check IDs, and evidence. On a push to `main`, stale successful
  assessments are invalidated **without** triggering another Copilot run;
  completion events reconcile abandoned checks as failures.
- `.github/workflows/sfstack-quality.yml`: accepts both operator
  dispatches and coordinator-generated expected head, base, and request IDs.
  It forwards the numeric PR number through `fromJSON` (required by
  GitHub's runner behavior). The repository's `COPILOT_GITHUB_TOKEN` is
  passed **only** to this Quality execution path.

The two workflows named `sfstack PR signal` and `sfstack GitHub quality`
must keep those exact names in the coordinator's `workflow_run` event
filter. The coordinator must also retain the exact filenames so its API
provenance checks cannot be bypassed by a malicious event or artifact.
Only its dispatch job has `actions: write`; the base invalidator and
run reconciler have `actions: read` and `checks: write`.

**Costs and safeguards:** a newly opened, synchronized, reopened, edited,
or ready-for-review PR can now incur Copilot usage automatically. Unchanged
already-successful head/base/intent is deduplicated, and a `main` push
does not fan out new model assessments. A base push only revokes stale
clearance; a fresh head event or manual invocation is needed for reassessment.
This path cannot merge, approve, or deploy PRs. Ordinary Actions runners
are not a hostile-code sandbox, so do not invite untrusted contributors to
create same-repository branches with executable verification code.

### After the paired PRs are merged

To accept the automatic path, keep the safe
[draft PR #37](https://github.com/grove/sfstack/pull/37) open. Push one
harmless new documentation commit to that PR branch; observe the sequence
`sfstack PR signal` → `sfstack quality events` →
`sfstack GitHub quality`, and confirm the `sfstack quality` check is
attached to the **new** PR head. A new default-branch push should revoke
prior passing clearance without starting an AI review. Retain actual
run and check links in [factory acceptance #1](https://github.com/grove/factory/issues/1).
A live end-to-end automatic result cannot be claimed from CI alone.

To **enforce** Quality as a merge gate, configure an up-to-date required
`sfstack quality` GitHub Actions check, normal CI, and independent human
approval in branch rules. Neither PR changes the repository's rulesets.
Automatic signal/dispatch is not evidence that failure or stale checks
prevent merging unless those rules are enabled.

## First manual smoke test and evidence record

Use an **open, same-repository, documentation-only draft PR** to test the
cross-repository Quality handoff without changing executable behavior.
Do not merge a PR simply to exercise the factory.

Before dispatch, record the PR number, exact head commit and current `main`
SHA. Start the workflow from **main** with the PR number, not from the PR
branch. The manual workflow is the only trigger installed in sfstack.

After dispatch, keep a link to the **caller** Actions run and inspect:

- The trusted Factory checkout used the pinned workflow revision, and the
  candidate checkout used the PR's exact head, not a mutable branch.
- The independent verification ran the declared nonempty check suite and
  retained logs and evidence; passing tests alone are not approval.
- The Quality check on that PR head belongs to the GitHub Actions app,
  matches the workflow run/attempt and assessment inputs, and has an
  appropriate nonpassing conclusion if a prerequisite was absent.
- A newer PR head, changed intent or advanced base must not reuse this
  assessment. Automatic invalidation and reconciliation are not yet
  installed in this manual-only pilot, so require a fresh manual run and
  never use a stale check as clearance.

If Copilot credentials are missing or invalid, preserve the failed run and
configure the **repository** secret without sharing its contents. Do not
rerun paid work to disguise a previous failure, and do not assume that a
visible successful check enforces human approval or branch protection.

Record the actual run link and observations in
[factory acceptance #1](https://github.com/grove/factory/issues/1). A
passing CI run for this documentation-only PR does **not** count as the
manual Quality handoff until the manual workflow is dispatched and its
result observed.

## Automatic PR-signal acceptance probe (21 November 2026)

This draft PR is deliberately a **documentation-only** acceptance subject
for the post-merge, cross-repository Quality Factory event route. This
appendix introduces no executable changes, permissions, workflow edits, or
policy changes. Its commit is the new PR head that the automated route must
authenticate; do not replace it with a branch tip inferred from prose.

After this commit's `pull_request.synchronize` event, check the actual
`sfstack PR signal` run, its authenticated `workflow_run` completion
handled by `sfstack quality events`, the automatically dispatched
`sfstack GitHub quality` run, and the `sfstack quality` check on this
exact commit. Inspect the real independent verifier, Copilot review and
retained evidence; no report or check should be marked passed merely because
the signal itself succeeded.

A future `main` change should revoke any stale success without starting
another paid review. This test PR is **not an authorization to merge**; CI,
up-to-date Quality and independent human review remain separate merge gates.
Record the observed positive and negative runs in
[Factory acceptance #1](https://github.com/grove/factory/issues/1).
