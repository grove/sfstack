# Assess a GitHub pull request

The GitHub Software Factory and Quality Factory are maintained in
[`grove/factory`](https://github.com/grove/factory). Their controller, Actions
workflows, operational documentation, and recovery tests have moved there.

Continue with the [factory guide](https://github.com/grove/factory/blob/main/docs/how-to/run-github.md).

sfstack supplies the portable skills, schemas, recipes, and
[versioned contract CLI](../reference/public-cli.md). It has no GitHub credentials,
event routing, draft publisher, or check-run owner. The host installs a pinned
distribution and invokes that public interface.

## Manual sfstack-to-factory Quality pilot

This repository intentionally does **not** copy the GitHub factory controllers
or install automatic PR event coordination. The trusted GitHub Actions caller
at [`.github/workflows/sfstack-quality.yml`](../../.github/workflows/sfstack-quality.yml)
invokes the reusable Quality Factory from
[`grove/factory`](https://github.com/grove/factory) at the immutable
revision `550832359160e49e0824010cbd9c7e8f84b32589`.

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

**Scope:** one manual Quality assessment, not automatic PR events, base-push
invalidation, interrupted-run reconciliation, Software Factory, or a central
cross-repository service. A normal factory `checks.json` currently runs the
candidate's Python unittest suite; a future generalized target needs a
maintainer-reviewed project-specific verification plan. A green check alone
does not enforce GitHub branch protection, required up-to-date CI, or an
independent human approval. Those settings and a controlled live acceptance
exercise remain separate acceptance work in
[factory #1](https://github.com/grove/factory/issues/1).

Upgrades require a reviewed PR bumping the full Factory SHA in this caller;
never switch the call to a mutable branch or `latest`.

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
