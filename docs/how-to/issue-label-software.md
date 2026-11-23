# Start the Software Factory with issue labels

You no longer need the long `gh workflow run` command or the five-field
GitHub Actions form for a normal work item. The established manual workflow
remains available when you need an explicit operator recovery.

## Prerequisites for current use

- The repository has labels named exactly `factory:plan` and `factory:run`.
- The reviewed, SHA-pinned
  [`sfstack-issue-label.yml`](../../.github/workflows/sfstack-issue-label.yml)
  caller is already merged into the default branch (`main`). A caller that is
  only on a feature branch does not handle labels.
- Copilot entitlement is available and the `COPILOT_GITHUB_TOKEN` secret is
  configured for the planning and build jobs.
- Actions `GITHUB_TOKEN` may create **draft PRs**, and the default branch stays
  protected: normal review, branch-protection and Quality requirements still
  apply. Using this feature never requires broader permissions or skipping
  review.

No production workflow starts from opening or editing an issue alone.

## Choose a mode

1. Open a GitHub issue (choose the **Software Factory work item** template).
   State the problem, list the **exact files** under `## Files to change` and
   concrete outcomes under `## Acceptance criteria`. The existing restricted
   file and acceptance-criteria rules apply to both modes.
2. **Direct build (one paid decision):** If you do not need a separate AI
   implementation strategy, a repository writer adds `factory:run` once
   without first adding `factory:plan`. The trusted controller
   authenticates the human labeler, issue, scope and default-branch SHA and
   posts one durable bot-authored **direct run claim** containing the exact
   files and criteria before starting the paid Copilot implementation.
   No separate paid planning job or AI-plan comment is created.
3. **AI-assisted plan first (two paid decisions):** Instead, a repository
   writer adds `factory:plan`, authorizing one **paid read-only Copilot
   planning call**, not implementation. The first bot comment is only a
   deterministic scope snapshot. A separate model job generates useful per-file
   steps and proposed checks, and the trusted publisher validates and posts a
   second, **AI-assisted plan comment**. Review this advice; if it is missing,
   rejected or incomplete, **do not** add `factory:run`. Once satisfied,
   add `factory:run` to authorize a separate paid build bound to that
   exact plan digest.
4. In either mode, the existing Software Factory performs independently
   verified implementation and opens a **draft PR** with normal exact-head
   Quality requirements. Review the draft, approve normal PR-triggered
   workflows if prompted, and decide whether to merge. The Factory cannot
   approve or merge.

The direct path is for an issue **without a previous planning request**.
A failed or pending `factory:plan` snapshot, an orphaned authenticated
AI plan, or a still-present `factory:plan` label cannot be downgraded
to a direct build. If you chose planning, only the verified AI plan can
authorize `factory:run`. Both paths enforce a permanent one-shot claim;
removing and reapplying `factory:run` never buys another build.

For a **defect**, start the title with `defect:`, list an existing
`examples/` implementation file and exactly one new
`tests/test_*.py` regression file; the host still requires genuine test-only
RED and repaired GREEN. With optional AI planning, the plan should propose the RED/GREEN strategy.
Direct mode does not skip the actual test-only RED and repaired GREEN checks:
those are enforced independently after the human authorizes implementation.

No label can add workflow/controller files, grant permissions, override checks,
or authorize a passing Quality result. If the issue text or `main` changes
after planning, reapply `factory:plan` and review the new result. If a
paid attempt has already been claimed, relabeling or rerunning is **blocked**:
inspect the recorded run and reconcile any pending GitHub writes before creating
a separately authorized follow-up issue. Do not delete the bot's claim comment
to force an unexamined retry.

This is not autonomous task selection: a writer must deliberately apply
`factory:run` after reviewing either the bounded issue (direct mode)
or the second validated AI-plan comment (planned mode). For direct mode, the
bot-authored claim is the immutable scope record; for planned mode, the
first bot comment is only the deterministic **security snapshot**, and the
second is advisory AI advice, never execution evidence. Neither route can
expand the original scope or bypass independent verification or Quality. Full authority boundaries and operational details are in
[the Factory's current AI-assisted label-based Software guide](https://github.com/grove/factory/blob/main/docs/how-to/issue-label-software-factory.md).
Documentation links like this one may point to the current guide, but
execution and controller workflows must still use immutable, reviewed commit
SHAs.

### What a useful AI plan looks like

Suppose an issue's criterion is "empty input is rejected". A plan that only
repeats it ("make empty input rejected; add a test") adds nothing. A useful
plan is specific per file, for example: "In `examples/parser.py`, make
`parse()` raise `ValueError` when the input is empty, because it currently
returns `None`; in `tests/test_parser.py`, propose a test that calls
`parse("")` and expects `ValueError`." Proposed test methods are advice, not
executed evidence: only the independent host verification after `factory:run`
produces results.

## Troubleshooting a label that did not start work

Before retrying anything, open the issue and read the bot's **plan** and
**claim** comments, then open the matching run in the repository's **Actions**
tab (the run for the label event, linked from or named in those comments).
Match what you see to a row below.

| Symptom | Likely explanation | Safe response |
| --- | --- | --- |
| Direct `factory:run` is blocked | The issue already has a trusted planning snapshot, orphaned AI proposal or a still-present `factory:plan` label; direct mode cannot bypass pending or failed AI planning. | Review/reconcile the original planning run. Do not erase bot comments or relabel to force a downgrade. |
| No AI plan comment after `factory:plan` | The authenticated scope snapshot may be present, but the paid Copilot job failed, returned malformed advice, lacked entitlement, or the issue/base changed before publication. | Inspect the `plan` and `publish_plan` jobs in the issue-label Actions run. Do **not** add `factory:run`. A duplicate request on the exact same issue/base is blocked to prevent another charge. |
| The issue or `main` changed after planning | The AI plan is bound to the exact issue text and base SHA, so `factory:run` is rejected as stale. | If you want another paid plan for the changed issue/base, reapply `factory:plan`, review the new AI proposal, and only then decide on `factory:run`. |
| `factory:run` ignored: bot or non-writer actor, or label removed | Only a repository writer who applied the label may authorize a build, and the label must still be present when the run checks it. | Have a writer review the plan and deliberately add `factory:run` themselves. Do not work around the permission check. |
| A claim comment already exists | A one-shot durable claim records one paid build attempt, direct or AI-planned. | Do **not** remove and reapply `factory:run`: this never launches a second paid attempt for an existing claim. Inspect the recorded run instead. |
| The paid run is still executing or has failed | The claimed attempt is in progress, or it ended in failure. | While running, wait for it to finish. If it failed, read the run logs and any pending GitHub writes, and reconcile them. For another attempt, open a separately authorized follow-up issue and start again with `factory:plan`. Never delete the claim comment to force a retry. |

Neither path relaxes the guardrails: `factory:plan` is optional
**paid AI planning** without candidate mutation or GitHub write permission;
`factory:run` is writer-only **paid implementation** whether direct
or AI-planned. Exact files and acceptance criteria remain immutable, changes
are independently verified, the output is a draft PR requiring Quality, and
merging remains a human decision. A direct build requires a reviewed bounded
issue; a planned build requires the actual bot-authenticated AI proposal.
