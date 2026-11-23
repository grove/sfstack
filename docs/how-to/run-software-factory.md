# Build a verified draft pull request from an issue

The GitHub Software Factory is maintained in [grove/factory](https://github.com/grove/factory), not in the portable sfstack package.

- **Install into a repository:** [Factory onboarding](https://github.com/grove/factory/blob/main/docs/getting-started-new-repository.md).
- **Everyday work:** [direct and planned issue-label builds](issue-label-software.md). Use `factory:run` directly for a well-scoped issue with no previous planning request, or optionally apply paid `factory:plan`, review the validated proposal, then apply `factory:run`.
- **Explicit manual entrypoint:** [Factory manual Software guide](https://github.com/grove/factory/blob/main/docs/how-to/run-software-factory.md). Do not use it to bypass a permanent label claim.

## Reusable issue-to-draft Software Factory (manual caller)

This repository retains its [thin manual caller](../../.github/workflows/sfstack-software.yml) and [issue-label caller](../../.github/workflows/sfstack-issue-label.yml). The reviewed workflow files, not copied documentation, determine their immutable execution pins. Both operate on this repository's scoped work and independently verified draft PRs; the label route is the normal user path.

## Prerequisites and live pilot boundaries

The current pilot supports only the [reviewed verification and file-scope profile](https://github.com/grove/factory/blob/main/docs/reference/configuration.md). Separate paid planning (optional), implementation and independent Quality are distinct. Keep required CI, protected branch and human review. Opening or editing an issue alone never starts implementation.

## Troubleshooting the first live run

Use the [Factory recovery guide](https://github.com/grove/factory/blob/main/docs/how-to/troubleshooting.md) and [read-only run diagnostics](https://github.com/grove/factory/blob/main/docs/how-to/inspect-factory-run.md). Never erase a claim or relabel to force another paid build.

The [original integration pilot and incident record](https://github.com/grove/sfstack/blob/bf3c743dcb2b88ef1bafa39720fff0aab35ebb02/docs/how-to/run-software-factory.md) is preserved as historical evidence, not current instructions.

[Back to sfstack documentation](../README.md).
