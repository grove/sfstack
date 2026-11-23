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
2. Add `factory:plan` **as a repository writer**. This authorizes one
   **paid Copilot planning call**, but no implementation. The first bot
   comment records the exact immutable scope and base; it is only a trusted
   authorization snapshot. A separate read-only Copilot job proposes
   per-file implementation steps, concrete verification for every original
   criterion, risks and open questions. A third job independently validates
   and posts a **second, AI-assisted plan comment**. The model cannot run
   commands, edit code, publish comments or approve work.
3. Read the **second, AI-assisted comment**. If it is missing, incomplete or
   not useful, do **not** apply `factory:run`. When satisfied, add
   `factory:run` once: this is a separate **paid** implementation decision. The trusted
   controller checks the live issue, unchanged plan and base SHA, original label
   event, actor permission, and unique one-shot claim. Only then does it call
   the existing Software Factory: Copilot implementation → independent host
   verification → draft PR → exact-head Quality.
4. Review the draft, approve GitHub's normal PR-triggered workflows if prompted,
   and decide whether to merge. The Factory cannot merge.

For a **defect**, start the title with `defect:`, list an existing
`examples/` implementation file and exactly one new
`tests/test_*.py` regression file; the host still requires genuine test-only
RED and repaired GREEN. The AI plan proposes genuine test-only RED and repaired GREEN for the exact
new regression file, before you authorize implementation.

No label can add workflow/controller files, grant permissions, override checks,
or authorize a passing Quality result. If the issue text or `main` changes
after planning, reapply `factory:plan` and review the new result. If a
paid attempt has already been claimed, relabeling or rerunning is **blocked**:
inspect the recorded run and reconcile any pending GitHub writes before creating
a separately authorized follow-up issue. Do not delete the bot's claim comment
to force an unexamined retry.

This is not autonomous task selection: someone with write permission must make
the deliberate final `factory:run` choice. The first comment is the deterministic **security snapshot**, not planning.
The second comment must be a bounded, actual AI-generated implementation
strategy before a human writer may authorize a paid build. The model's
proposal is advice only; it cannot change the original authorized scope. Full authority boundaries and operational details are in
[the Factory's label-based Software guide](https://github.com/grove/factory/blob/e279c0eb3ce18a529cf7941492caa07ca0c03882/docs/how-to/issue-label-software-factory.md).

## Troubleshooting a label that did not start work

Before retrying anything, open the issue and read the bot's **plan** and
**claim** comments, then open the matching run in the repository's **Actions**
tab (the run for the label event, linked from or named in those comments).
Match what you see to a row below.

| Symptom | Likely explanation | Safe response |
| --- | --- | --- |
| No AI plan comment after `factory:plan` | The authenticated scope snapshot may be present, but the paid Copilot job failed, returned malformed advice, lacked entitlement, or the issue/base changed before publication. | Inspect the `plan` and `publish_plan` jobs in the issue-label Actions run. Do **not** add `factory:run`. A duplicate request on the exact same issue/base is blocked to prevent another charge. |
| The issue or `main` changed after planning | The AI plan is bound to the exact issue text and base SHA, so `factory:run` is rejected as stale. | If you want another paid plan for the changed issue/base, reapply `factory:plan`, review the new AI proposal, and only then decide on `factory:run`. |
| `factory:run` ignored: bot or non-writer actor, or label removed | Only a repository writer who applied the label may authorize a build, and the label must still be present when the run checks it. | Have a writer review the plan and deliberately add `factory:run` themselves. Do not work around the permission check. |
| A claim comment already exists | A one-shot durable claim records that a paid attempt was authorized for this plan. | Do **not** remove and reapply `factory:run`: this never launches a second paid attempt for an existing claim. Inspect the recorded run instead. |
| The paid run is still executing or has failed | The claimed attempt is in progress, or it ended in failure. | While running, wait for it to finish. If it failed, read the run logs and any pending GitHub writes, and reconcile them. For another attempt, open a separately authorized follow-up issue and start again with `factory:plan`. Never delete the claim comment to force a retry. |

None of these responses changes the guardrails: `factory:plan` is explicitly
**paid AI planning** without code execution or direct mutation permission,
`factory:run` stays writer-only and separately paid, only the exact files listed in the issue may
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
