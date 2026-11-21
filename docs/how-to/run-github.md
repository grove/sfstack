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
