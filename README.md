# sfstack

**Portable skills and contracts for verifiable software and quality work.**

sfstack is a library of focused skills, explicit interfaces and evidence-based workflows. Use one skill for a small task, or compose skills into a controlled factory workflow. An integration supplies the execution tools and enforces permissions; declaring a capability never grants access to it.

**Looking for the GitHub issue-to-PR product?** Install [Factory](https://github.com/grove/factory). It is the GitHub Actions host for bounded Copilot builds and independent Quality assessments. This repository is its portable foundation.

## Start here

| I want to… | Go to |
| --- | --- |
| Install Factory in a GitHub repository | [Factory onboarding](https://github.com/grove/factory/blob/main/docs/getting-started-new-repository.md) |
| Build a change from a GitHub issue | [Use issue labels](docs/how-to/issue-label-software.md) |
| Assess a GitHub PR | [GitHub Quality](docs/how-to/run-github.md) |
| Try a portable skill | [First skill tutorial](docs/tutorials/first-skill.md) |
| Try local Quality Factory | [Local execution](docs/how-to/run-local.md) |
| Find skills or workflows | [Skill catalog](docs/reference/catalog.md) · [Workflow reference](docs/reference/workflows.md) |
| Integrate or maintain sfstack | [Documentation index](docs/README.md) |

## Two independent entry points

**Software Factory** implements and verifies a scoped change. **Quality Factory** independently assesses an existing candidate, including human-authored changes. Software may consume Quality evidence; Quality never needs Software to run first. Both use a shared evidence and policy system.

See [operating modes](docs/explanation/operating-modes.md) and [architecture](docs/explanation/factory-design.md).

<a id="a-first-working-example"></a>

## Try a local example

Run a deterministic regression with real tests against a defective candidate, corrected candidate and negative test-suite cases:

```sh
python -m pip install -r requirements-dev.txt
python evals/run_quality_regression.py --output ../sfstack-quality-demo
```

Choose a fresh output directory. The demo uses declared fixture review inputs, not a live agent. A passing test alone is not an independent Quality verdict. See [regression documentation](evals/README.md).

To initialize a quality run for a clean local Git checkout:

```sh
python tools/sfstack.py init --repo ../my-project --out ../my-quality-run \
  --goal "Assess public behavior and regression coverage" \
  --environment my-isolated-python
python tools/sfstack.py status --run ../my-quality-run/run.json
```

This initializes pinned inputs and policy; a trusted adapter supplies execution. See [local execution and resume](docs/how-to/run-local.md).

## Use a skill

Choose a skill from the [catalog](docs/reference/catalog.md). Provide its `SKILL.md`, `contract.json`, and bundled `references/protocol.md` and `references/artifact.schema.json`, with the task and execution context. For [Agent Skills](https://agentskills.io/specification) hosts, install the complete skill directory according to the host's instructions. The contract is an sfstack extension; the host must explicitly enforce it.

```text
Use sf-map-project from skills/sf-map-project/.
Map this repository's entry points, behavior and verification paths.
Scope: read repository files and produce a project-context artifact.
Do not change source files or publish anything.
Record unknowns and the evidence for each conclusion.
```

<a id="what-is-included"></a>

## What belongs here?

| Layer | Responsibility |
| --- | --- |
| Skills and contracts | Reusable instructions, inputs, outputs, capabilities, effects and completion |
| Schemas, protocols and workflows | Consistent evidence, authorization and artifact handoffs |
| Adapters and reference tools | Environment-specific capability interfaces, local inspection and deterministic evaluation |
| [Versioned public CLI](docs/reference/public-cli.md) | Stable installed distribution boundary for independent hosts |
| [Factory](https://github.com/grove/factory) | Separate GitHub host: events, credentials, candidate execution, publication and checks |

The portable contracts are language- and provider-neutral, but individual execution profiles have specific limits. The GitHub Factory pilot currently requires Python unittest and restricted exact files; see its [configuration](https://github.com/grove/factory/blob/main/docs/reference/configuration.md). The local adapter examples supply no hardened sandbox or production authorization system.

<a id="validate-this-repository"></a>

## Maintain sfstack

Use Python 3.11+ and development dependencies:

```sh
python -m pip install -r requirements-dev.txt
python tools/validate.py
python tools/sync_protocol.py --check
python -m unittest discover -s tests -v
```

To export complete skill directories, including license material, into a fresh staging directory:

```sh
python tools/export_skills.py --output /tmp/sfstack-export
```

See [tooling reference](docs/reference/tooling.md), [contributing](CONTRIBUTING.md) and the [documentation index](docs/README.md). The library does not supply a tracker, merge queue or deployment service; a host must enforce permissions, isolation and persistence.

<a id="design-commitments"></a>

For the original design commitments, see [architecture](docs/explanation/factory-design.md) and [the original README](https://github.com/grove/sfstack/blob/bf3c743dcb2b88ef1bafa39720fff0aab35ebb02/README.md#design-commitments).

<a id="license"></a>

[Apache License 2.0](LICENSE).

