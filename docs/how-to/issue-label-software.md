# Build a change in sfstack with issue labels

sfstack already has a reviewed [issue-label caller](../../.github/workflows/sfstack-issue-label.yml) on its default branch. The canonical [Factory label guide](https://github.com/grove/factory/blob/main/docs/how-to/issue-label-software-factory.md) explains authorization, exact file scope, the issue format and both operating modes. To install in another repository, follow [Factory onboarding](https://github.com/grove/factory/blob/main/docs/getting-started-new-repository.md).

## Prerequisites for current use

A human writer must choose a real open issue. The configured labels, entitled Copilot secret, immutable caller pins, protected branch, required CI/Quality and draft-PR setting must remain intact.

## Choose a mode

1. Open a **Software Factory work item** issue with exact backticked files under **Files to change** and observable **Acceptance criteria**.
2. **Direct:** for a clear issue with no previous planning request, apply `factory:run` once. It authorizes paid implementation; separate paid AI planning is skipped.
3. **Planned:** optionally apply `factory:plan` for paid read-only advice. Review the second validated AI-plan comment before separately authorizing `factory:run`. The first scope snapshot is not an AI plan.
4. Follow the bot's permanent claim to its run. Inspect actual verification and the draft PR. Independent Quality uses Copilot separately; ordinary CI and human review remain mandatory before merge.

### Verify a direct run

Check the bot's exact direct-mode claim. The plan and publish-plan jobs are intentionally skipped; judge the build by actual implementation and independent host verification. Inspect the draft PR, retained evidence and separate required Quality checks. [Read-only run diagnostics](https://github.com/grove/factory/blob/main/docs/how-to/inspect-factory-run.md) can inspect the historical attempt.

### What a useful AI plan looks like

Use the [Factory example and mode comparison](https://github.com/grove/factory/blob/main/docs/how-to/issue-label-software-factory.md#choose-one-of-two-human-authorized-paths). A proposed test method is advice, not executed evidence.

## Troubleshooting a label that did not start work

A failed or pending planning request cannot be downgraded to direct mode. Once a build is claimed, never remove/reapply the label, delete the claim or rerun the paid label event. Inspect existing writes and evidence; another build requires a separately authorized follow-up issue.

See [Factory troubleshooting](https://github.com/grove/factory/blob/main/docs/how-to/troubleshooting.md) for safe handling of stale plans, missing drafts, CI approvals and Quality recovery. For historical examples, see [Factory #17](https://github.com/grove/factory/issues/17), [sfstack #54](https://github.com/grove/sfstack/issues/54) and [sfstack #58](https://github.com/grove/sfstack/issues/58).
