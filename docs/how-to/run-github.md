# Assess a GitHub pull request

Quality Factory independently assesses an eligible PR, whether human-authored or Factory-generated. The GitHub host and canonical operating guide are maintained in [grove/factory](https://github.com/grove/factory).

- [Install Factory](https://github.com/grove/factory/blob/main/docs/getting-started-new-repository.md).
- [Run and inspect Quality Factory](https://github.com/grove/factory/blob/main/docs/how-to/run-github.md).
- [Recover safely](https://github.com/grove/factory/blob/main/docs/how-to/troubleshooting.md).

## Automatic PR Quality using reusable Factory workflows

sfstack's current [PR signal](../../.github/workflows/sfstack-pr-signal.yml) and [event coordinator](../../.github/workflows/sfstack-quality-events.yml) request the independently assessed, exact-head [Quality workflow](../../.github/workflows/sfstack-quality.yml). The [native required gate](../../.github/workflows/sfstack-quality-required.yml) is a read-only witness to the completed independent result. It never launches a separate AI review.

Eligible PR events can consume Copilot usage; moving only from draft to ready does not require another assessment of an unchanged passing result. A default-branch push invalidates stale clearance without automatically reviewing all open PRs. For a selected PR that needs fresh review, a maintainer can explicitly dispatch Quality; this consumes additional model usage.

Retain ordinary required CI, the exact `sfstack quality` check from GitHub Actions, up-to-date branch protection and human review. A passing assessment is not permission to merge.

## Software Factory: explicit issue dispatch, not PR event automation

To build from an issue, use [issue labels](issue-label-software.md). Quality does not implement changes; it works independently of Software Factory.

## Historical evidence

The [original manual and automatic Quality integration record](https://github.com/grove/sfstack/blob/bf3c743dcb2b88ef1bafa39720fff0aab35ebb02/docs/how-to/run-github.md) retains the rollout, numeric input forwarding and activation diagnostics. It contains historical pins and instructions; do not treat them as current.

[Back to sfstack documentation](../README.md).

## Archived sections

These historical sections are retained at the original immutable revision, not as current operating instructions.

<a id="initial-manual-sfstack-to-factory-quality-pilot-historical"></a>
- [Initial manual sfstack-to-factory Quality pilot (historical)](https://github.com/grove/sfstack/blob/bf3c743dcb2b88ef1bafa39720fff0aab35ebb02/docs/how-to/run-github.md#initial-manual-sfstack-to-factory-quality-pilot-historical)
<a id="failed-before-jobs-diagnostic-21-november-2026"></a>
- [Failed-before-jobs diagnostic (21 November 2026)](https://github.com/grove/sfstack/blob/bf3c743dcb2b88ef1bafa39720fff0aab35ebb02/docs/how-to/run-github.md#failed-before-jobs-diagnostic-21-november-2026)
<a id="numeric-workflow_dispatch-input-forwarding"></a>
- [Numeric workflow_dispatch input forwarding](https://github.com/grove/sfstack/blob/bf3c743dcb2b88ef1bafa39720fff0aab35ebb02/docs/how-to/run-github.md#numeric-workflow_dispatch-input-forwarding)
<a id="first-live-cross-repository-reviewer-activation-21-november-2026"></a>
- [First live cross-repository reviewer activation (21 November 2026)](https://github.com/grove/sfstack/blob/bf3c743dcb2b88ef1bafa39720fff0aab35ebb02/docs/how-to/run-github.md#first-live-cross-repository-reviewer-activation-21-november-2026)
<a id="after-the-paired-prs-are-merged"></a>
- [After the paired PRs are merged](https://github.com/grove/sfstack/blob/bf3c743dcb2b88ef1bafa39720fff0aab35ebb02/docs/how-to/run-github.md#after-the-paired-prs-are-merged)
