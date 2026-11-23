# Start the Software Factory with issue labels

You no longer need the long `gh workflow run` command or the five-field
GitHub Actions form for a normal work item. The established manual workflow
remains available when you need an explicit operator recovery.

**Once after deployment:** in your repository's **Issues → Labels**, create
labels `factory:plan` and `factory:run` with these exact spellings.
This label handler runs only after the reviewed, SHA-pinned
[`sfstack-issue-label.yml`](../../.github/workflows/sfstack-issue-label.yml)
has been merged into `main`.

## Use it

1. Open a GitHub issue (choose the **Software Factory work item** template).
   Write what needs to change, list **exact files** under `## Files to
   change` and concrete outcomes under `## Acceptance criteria`.
   These two ordinary Markdown lists replace the old JSON workflow parameters.
2. Add `factory:plan`. GitHub Actions checks the actual label author has
   repository write permission and posts an **exact plan preview** as a comment.
   **This stage does not call Copilot, run candidate code, or publish a PR.**
3. Read that comment. When satisfied, add `factory:run` once. The trusted
   controller checks the live issue, unchanged plan and base SHA, original label
   event, actor permission, and unique one-shot claim. Only then does it call
   the existing Software Factory: Copilot implementation → independent host
   verification → draft PR → exact-head Quality.
4. Review the draft, approve GitHub's normal PR-triggered workflows if prompted,
   and decide whether to merge. The Factory cannot merge.

For a **defect**, start the title with `defect:`, list an existing
`examples/` implementation file and exactly one new
`tests/test_*.py` regression file; the host still requires genuine test-only
RED and repaired GREEN. The plan comment shows the selected repair mode and
regression file before you authorize work.

No label can add workflow/controller files, grant permissions, override checks,
or authorize a passing Quality result. If the issue text or `main` changes
after planning, reapply `factory:plan` and review the new result. If a
paid attempt has already been claimed, relabeling or rerunning is **blocked**:
inspect the recorded run and reconcile any pending GitHub writes before creating
a separately authorized follow-up issue. Do not delete the bot's claim comment
to force an unexamined retry.

This is not autonomous task selection: someone with write permission must make
the deliberate final `factory:run` choice. The plan is a deterministic
summary of the exact paths and criteria in the issue, not a separate paid AI
planner. Full authority boundaries and operational details are in
[the Factory's label-based Software guide](https://github.com/grove/factory/blob/e279c0eb3ce18a529cf7941492caa07ca0c03882/docs/how-to/issue-label-software-factory.md).

## Troubleshooting a label that did not start work

Before retrying anything, open the issue and read the bot's **plan** and
**claim** comments, then open the matching run in the repository's **Actions**
tab (the run for the label event, linked from or named in those comments).
Match what you see to a row below.

| Symptom | Likely explanation | Safe response |
| --- | --- | --- |
| No plan comment after `factory:plan` | The label was added by a bot or a user without write permission, the label was removed, the label spelling is wrong, or the planning run failed or has not finished. | Check the label's exact spelling and who added it, then check the planning run in Actions. A writer can remove and re-add `factory:plan`; this is no-model and spends nothing. |
| The issue or `main` changed after planning | The plan is bound to the exact issue text and base SHA, so `factory:run` is rejected as stale. | Reapply `factory:plan`, review the new plan comment, and only then decide on `factory:run`. |
| `factory:run` ignored: bot or non-writer actor, or label removed | Only a repository writer who applied the label may authorize a build, and the label must still be present when the run checks it. | Have a writer review the plan and deliberately add `factory:run` themselves. Do not work around the permission check. |
| A claim comment already exists | A one-shot durable claim records that a paid attempt was authorized for this plan. | Do **not** remove and reapply `factory:run`: this never launches a second paid attempt for an existing claim. Inspect the recorded run instead. |
| The paid run is still executing or has failed | The claimed attempt is in progress, or it ended in failure. | While running, wait for it to finish. If it failed, read the run logs and any pending GitHub writes, and reconcile them. For another attempt, open a separately authorized follow-up issue and start again with `factory:plan`. Never delete the claim comment to force a retry. |

None of these responses changes the guardrails: `factory:plan` stays no-model,
`factory:run` stays writer-only, only the exact files listed in the issue may
change, the result is published only as a draft PR after independent
verification and Quality, and merging remains a human decision. A future paid
build is authorized only when a human reviews the plan and deliberately applies
`factory:run`.

## Activation order and prerequisites

Merge the [Factory implementation PR](https://github.com/grove/factory/pull/14)
**first**, then the thin, exact-SHA-pinned sfstack caller PR. Confirm that
the repository can create **draft PRs** with Actions `GITHUB_TOKEN`,
and that `COPILOT_GITHUB_TOKEN` remains configured for the underlying
bounded builder. No production workflow starts from opening or editing an
issue alone, and `factory:plan` is no-model.

Keep `grove/factory` and `grove/sfstack` protected on main.
No branch-protection, GitHub Actions setting, or merge policy is changed by
adding this feature.
