# Build a verified draft pull request from an issue

The GitHub Software Factory and Quality Factory are maintained in
[`grove/factory`](https://github.com/grove/factory). Their controller, Actions
workflows, operational documentation, and recovery tests have moved there.

Continue with the [factory guide](https://github.com/grove/factory/blob/main/docs/how-to/run-software-factory.md).

sfstack supplies the portable skills, schemas, recipes, and
[versioned contract CLI](../reference/public-cli.md). It has no GitHub credentials,
event routing, draft publisher, or check-run owner. The host installs a pinned
distribution and invokes that public interface.

## Reusable issue-to-draft Software Factory (manual caller)

The trusted Software Factory implementation now lives in
[`grove/factory`](https://github.com/grove/factory). This repository's
thin [`.github/workflows/sfstack-software.yml`](../../.github/workflows/sfstack-software.yml)
calls it at the immutable, reviewed Factory commit
`cb4b0b07b1d273af03e9fe860b7cf9113b6064d9`. It is a **manual-only** `workflow_dispatch`
entrypoint: opening, editing, or labeling an issue cannot autonomously
start a build, and candidates cannot choose their own controller source.

The maintainer selects an **open issue**, 1–8 exact permitted files, a JSON
array of acceptance criteria, and `change` or `defect` mode. The caller
verifies `main` before invoking the pinned workflow and forwards the
`COPILOT_GITHUB_TOKEN` repository secret only to the trusted Factory
workflow. The called workflow checks out Factory at `job.workflow_sha`
and sfstack at the authorized caller base, uses the self-contained compiled
Copilot builder, independently verifies a bounded proposal, and exposes
repository write privileges **only** to the final publisher. Any successful
publication creates a **draft PR** and invokes the already-installed Quality
Factory for its exact head. No agent can approve or merge a PR.

### Prerequisites and live pilot boundaries

- Configure **Settings → Actions → General → Workflow permissions →
  Allow GitHub Actions to create and approve pull requests** for
  `grove/sfstack`. The workflow itself *only creates drafts* and
  requests Quality; it does not call the approval/merge APIs.
- Keep the existing protected `main`, required current CI and the GitHub Actions
  `sfstack quality` check. The repository's solo-maintainer policy requires
  **zero external approvals**; the maintainer still inspects evidence before merging.
- Begin only with a **maintainer-approved, harmless, bounded issue** and
  explicitly selected files. The package's Python test suite and independent
  verifier are the initial default checks; no hostile same-repo candidate
  code should be run on ordinary Actions workers.
- The compiler-only Factory CI proves the reviewed gh-aw build prompt is
  self-contained and controller-SHA-bound. It does **not** prove that
  this target has completed a real issue→draft→Quality run. That
  requires a separately inspected live pilot with retained negative
  evidence in [factory #1](https://github.com/grove/factory/issues/1).

### Troubleshooting the first live run

| Symptom | Likely cause | Safe recovery action |
| --- | --- | --- |
| The build step fails at authentication, or the Copilot step reports a missing or unauthorized token. | The `COPILOT_GITHUB_TOKEN` repository secret is missing, empty, expired, or lacks Copilot access. It is forwarded only to the trusted Factory workflow. | Have a maintainer re-create the secret in **Settings → Secrets and variables → Actions** for `grove/sfstack`, then start a new run. Never paste the token into an issue, input, log, or comment, and do not echo it to debug. |
| The caller rejects the inputs before any build starts. | `allowed-paths` is not a JSON array of 1–8 exact file paths, or `acceptance-criteria` is not a JSON array of strings. Globs, directories, and files outside the supported scope are not accepted. | Re-dispatch with, for example, `["docs/how-to/run-software-factory.md"]` for `allowed-paths` and `["First criterion","Second criterion"]` for `acceptance-criteria`. Do not widen the file list beyond what the issue needs. |
| The run stops because `main` or the issue no longer matches the pinned inputs. | The run is pinned to a base commit and issue content. Advancing `main` or editing the issue (title, body, or state) invalidates that pin. | Do not retry the old run. Review the new `main` and issue text, then start a new run so it pins fresh inputs. Retry only for transient infrastructure failures where `main` and the issue are unchanged. |
| Verification passed, but no draft PR appears and the publish step reports it cannot create a pull request. | **Allow GitHub Actions to create and approve pull requests** is disabled. It is a repository setting under **Settings → Actions → General → Workflow permissions**, and an organization policy can override it. | A maintainer enables the setting for `grove/sfstack` only, then starts a new run. This grants no approval or merge authority: the publisher only creates drafts, and quality gates and human review still apply. |

Recovery never involves bypassing a quality gate, granting broader write
authority, or merging or approving automatically. See
[Prerequisites and live pilot boundaries](#prerequisites-and-live-pilot-boundaries)
for the supported setup.

Do not silently broaden the file policy, start paid model work merely to
test whether the workflow is visible in Actions, or merge an AI-produced
draft without human review.
