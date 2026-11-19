# sfstack

**Reusable skills for building software and checking the results with evidence.**

If you work with a coding agent, sfstack helps you give it smaller, clearer jobs:
understand a project, clarify a request, implement a scoped change, or check
whether a change works. Each skill explains what it needs, what it should
produce, and what evidence supports the result.

There are 39 skills in the library. You can use just one of them; you don't need
to set up an entire "factory" to get started.

For larger work, sfstack offers two independent paths:

- **Software Factory** helps plan, build, verify, and deliver scoped changes.
- **Quality Factory** assesses existing code or pull requests *without*
  changing them. It can run on its own, even if you never use Software Factory.

Both paths follow the same rules for recording evidence and respecting
permissions. Learn more about the [operating modes](docs/explanation/operating-modes.md)
and [independent quality assessment](docs/how-to/run-quality.md).

sfstack is not a coding agent or a deployment service. It provides portable
instructions and contracts; your agent, adapter, or integration supplies the
tools needed to do the work. If a check cannot run or evidence is missing, that
should be visible rather than reported as a success.

## Start here

No need to read the whole library first. Pick the path that matches your goal:

- **I want to try one skill with my agent.** Follow
  [Run your first skill](docs/tutorials/first-skill.md) to turn a sample request
  into a reviewable outcome brief, without editing code.
- **I want to see the checks in action, without an agent.** Run the
  [local demo](#try-the-local-demo) below. It uses real tests on small examples.
- **I want to assess code I already have.** Use the
  [local quality guide](docs/how-to/run-local.md) to initialize an assessment
  for a clean Git checkout and connect a trusted adapter for execution.
- **I want to assess a GitHub pull request.** Follow the
  [GitHub integration guide](docs/how-to/run-github.md) for Actions,
  Agentic Workflows, and quality gates.
- **I want to build a change from a GitHub issue.** Follow the
  [Software Factory guide](docs/how-to/run-software-factory.md) to implement
  one scoped work item, verify it, and open a draft PR for review.

### Try the local demo

You'll need Git and Python 3.11 or newer. From a terminal, clone the project
and run the regression demo:

```sh
git clone https://github.com/grove/sfstack.git
cd sfstack
python -m pip install -r requirements-dev.txt
python evals/run_quality_regression.py --output ../sfstack-quality-demo
```

The demo runs actual tests against a deliberately defective example, a
separately corrected example, and cases with skipped or missing tests. **Failures
and inconclusive assessments are expected**: the point is to see how the
reports tell them apart. The reports go into `../sfstack-quality-demo`, which
must not exist before you run the command. No live agent or authenticated
reviewer is involved; planning and review inputs are example fixtures.

### Assess your own checkout

If you have a separate, **clean Git checkout** of a project you want to assess,
you can initialize a local quality run from the sfstack directory:

```sh
python tools/sfstack.py init --repo ../my-project --out ../my-quality-run \
  --goal "Assess the public behavior and regression coverage" \
  --environment my-isolated-python
python tools/sfstack.py status --run ../my-quality-run/run.json
```

Replace the example paths and environment label with your own. The output
directory must be new and outside the project being assessed. This step
**prepares the assessment; it does not run the checks**. A trusted adapter
does the actual work. See the [local guide](docs/how-to/run-local.md) for
execution, checkpoints, and resuming a run. Use `--profile risk` at
initialization if you also need security and compatibility assessments.

### Where to go next

- **Learn the workflows:** try the [factory rehearsal](docs/tutorials/factory-rehearsal.md),
  [Quality Factory rehearsal](docs/tutorials/quality-rehearsal.md), or
  [local adapter slice](docs/tutorials/local-slice.md).
- **Build from an issue:** see the [Software Factory integration](docs/how-to/run-software-factory.md)
  for a maintainer-scoped GitHub workflow.
- **Choose and connect tools:** read [skill and workflow selection](docs/how-to/select-skills.md),
  [agent integration](docs/how-to/connect-agent.md), and
  [tracker integration](docs/how-to/connect-tracker.md).
- **Understand the evidence:** see [revalidation](docs/how-to/revalidate-evidence.md),
  [paired trial comparisons](docs/how-to/compare-trials.md), and
  the [evaluation guide](evals/README.md).
- **Browse everything:** visit the [documentation](docs/README.md),
  [skill catalog](docs/reference/catalog.md), and
  [workflow reference](docs/reference/workflows.md).

The documentation is organized into tutorials, how-to guides, reference, and
explanation using [Diátaxis](https://diataxis.fr/).

## What is included

| Layer | Contents | Purpose |
| --- | --- | --- |
| Skills | `skills/sf-*/SKILL.md` | Concise, independently usable instructions with consistent names. |
| Contracts | One `contract.json` per skill | Explicit inputs, outputs, capabilities, effects, and completion conditions. |
| Shared references | Execution protocol and artifact schema bundled in every skill | Consistent statuses, evidence, authorization, handoffs, and independently verifiable output structure. |
| Workflows | JSON recipes in `workflows/` | Named dependency graphs with explicit artifact bindings. |
| Schemas and examples | `schemas/`, `examples/` | Validate interchange records and demonstrate integration boundaries. |
| Adapter contracts | `adapters/` | Separate neutral skill behavior from environment-specific tool calls. |
| GitHub integration | [Quality Factory](docs/how-to/run-github.md) and [Software Factory](docs/how-to/run-software-factory.md) | Build a scoped issue into a draft PR, then assess the pinned candidate through real verification, review, and deterministic quality/effect gates. |
| Reference tools | `tools/` and `tests/` | Validate the library, inspect readiness, assess gates, and export skills. |
| Behavioral evaluation | [Seed case and rubric](evals/README.md) | Exercise skills on an isolated coding task and report evidence and limits. |

The reference tools validate local records. A [bounded local runner](docs/how-to/run-local.md)
can dispatch **trusted Python adapters** for effect-free skills, validate their
results, and save a checkpoint after each step. A
[reference unittest adapter](examples/adapters/README.md) executes real checks
on pinned candidates. These tools supply no sandbox or production tool boundary.
The optional GitHub integration connects Copilot through Agentic Workflows for
automatic review of same-repository PRs and publishes an evidence-backed quality
check on the reviewed commit. Manual dispatch remains available. The integration
grants no merge authority; independent human approval remains separate. The library does not
supply a tracker, merge queue, or deployment service. A production controller must provide persistence,
authentication, isolation, scheduling, and enforcement at the actual tool
boundary. See [factory architecture](docs/explanation/factory-design.md).

## Use a skill

A skill is an instruction package for an agent, not a command that runs by
itself. Choose a directory from the [catalog](docs/reference/catalog.md). Give the agent
its `SKILL.md`, `contract.json`, bundled `references/protocol.md`, and
`references/artifact.schema.json`, together with the task and execution context. For hosts supporting the
[Agent Skills format](https://agentskills.io/specification), register or install
the complete directory using that host's documented mechanism. For other agents,
load those files explicitly into the task context.

For example:

```text
Use sf-map-project from skills/sf-map-project/.
Map this repository's entry points, behavior boundaries, and verification paths.
Scope: read repository files and produce a project-context artifact.
Do not change source files or publish anything.
Record unknowns and the evidence for each conclusion.
```

`contract.json` is a **sfstack extension**, not a standard Agent Skills metadata
file. A host may ignore it unless its integration explicitly reads and enforces
it. Declaring a capability never grants permission to use it.

## Validate this repository

The optional development utilities require Python 3.11 or newer and the declared
validation dependencies. These are requirements for maintaining this library,
not requirements for the software your agents build.

```sh
python -m pip install -r requirements-dev.txt
python tools/validate.py
python tools/sync_protocol.py --check
python -m unittest discover -s tests -v
```

Export complete skill directories, including license material, into an empty
staging directory:

```sh
python tools/export_skills.py --output /tmp/sfstack-export
```

See [tooling reference](docs/reference/tooling.md) for commands, exit behavior,
and what each check does and does not establish.

## Design commitments

1. **Consistent interfaces.** Stable artifact names and status meanings make handoffs inspectable.
2. **Verifiable claims.** Results identify the candidate, inputs, environment, checks, and evidence.
3. **Bounded autonomy.** Scope, capability availability, authorization, and budgets remain separate.
4. **Small units.** Use the smallest workflow that resolves the task's actual risks.
5. **Portable behavior.** Adapters map capabilities to local tools; skills do not embed provider assumptions.
6. **Measured quality.** Evaluate behavior on representative tasks before adopting broader automation.

Compatibility is an integration contract, not a claim that every agent or tracker
has been exercised. Record the hosts and adapters you actually qualify. The
[contribution guide](CONTRIBUTING.md) explains how to change the library without
weakening these commitments.

## License

[Apache License 2.0](LICENSE).
