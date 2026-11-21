# sfstack

**Portable skills for verifiable software and quality factories.**

sfstack is a library of 39 focused skills covering discovery, design, implementation,
verification, delivery, operations, and continuous improvement. Each skill defines
one useful responsibility, its inputs, its output, and the evidence needed to
finish. Use a single skill for a small task or compose skills into a controlled
workflow.

Two independent entry points share one evidence and policy system:
**Software Factory** builds and delivers scoped changes;
**Quality Factory** assesses existing code, external pull requests, and changes
without implementing them. Software delivery may consume quality assessments,
but quality assessment never requires a software-factory run.
See [operating modes](docs/explanation/operating-modes.md) and the
[quality guide](docs/how-to/run-quality.md).

The instructions do not depend on a programming language, framework, coding agent,
issue tracker, or deployment provider. An integration supplies the capabilities
available in its environment. Missing capabilities and incomplete evidence remain
visible; a successful-looking response is not a substitute for a verified result.


The [versioned public contract CLI](docs/reference/public-cli.md) provides the
pinned distribution boundary used by independent hosts. The GitHub Software
Factory and Quality Factory are maintained in
[`grove/factory`](https://github.com/grove/factory).

## Start here

- **Start a local quality run:** [Initialize, inspect, and resume](docs/how-to/run-local.md) with one CLI.
- **Assess a GitHub PR:** [Use the manual, SHA-pinned Factory Quality caller](docs/how-to/run-github.md) with deterministic verification, Copilot review, retained evidence, and a quality gate.
- **Build from a GitHub issue:** [Run Software Factory](docs/how-to/run-software-factory.md) to implement one scoped work item, verify it, and open a draft PR for Quality Factory and human review.
- **See real test evidence:** [Execute the quality regression](evals/README.md#execute-the-quality-handoff-with-real-tests).
- **Try one skill:** [Create an outcome brief with your agent](docs/tutorials/first-skill.md).
- **Try a factory workflow:** [Rehearse an offline factory run](docs/tutorials/factory-rehearsal.md).
- **Assess existing code independently:** [Quality Factory rehearsal](docs/tutorials/quality-rehearsal.md).
- **Exercise one execution boundary:** [Run a local adapter slice](docs/tutorials/local-slice.md).
- **Plan evidence freshness:** [Revalidate a changed candidate](docs/how-to/revalidate-evidence.md).
- **Measure relative value:** [Compare paired agent trials](docs/how-to/compare-trials.md).
- **Choose the right scope:** [Select skills and workflows](docs/how-to/select-skills.md).
- **Connect your tools:** [Agent integration](docs/how-to/connect-agent.md) and [tracker integration](docs/how-to/connect-tracker.md).
- **Explore the library:** [Skill catalog](docs/reference/catalog.md) and [workflow reference](docs/reference/workflows.md).

The [documentation](docs/README.md) separates tutorials, how-to guides, reference,
and explanation using [Diátaxis](https://diataxis.fr/).

### A first working example

Run actual tests against a small defective candidate, a corrected candidate,
and skipped/empty test suites, retaining their quality reports:

```sh
python -m pip install -r requirements-dev.txt
python evals/run_quality_regression.py --output ../sfstack-quality-demo
```

The directory must be new. The defect remains a failed assessment; passing tests
alone remain inconclusive on independent review. Planning and review inputs in
this example are declared fixtures. No live agent or authenticated reviewer is
implied.

For your own clean local Git checkout:

```sh
python tools/sfstack.py init --repo ../my-project --out ../my-quality-run \
  --goal "Assess the public behavior and regression coverage" \
  --environment my-isolated-python
python tools/sfstack.py status --run ../my-quality-run/run.json
```

Initialization pins the candidate, creates the policy and request, and selects
the existing quality workflow. `--profile risk` also selects security and
compatibility. A trusted adapter supplies the actual work; the
[local guide](docs/how-to/run-local.md) explains bounded execution and resume.

## What is included

| Layer | Contents | Purpose |
| --- | --- | --- |
| Skills | `skills/sf-*/SKILL.md` | Concise, independently usable instructions with consistent names. |
| Contracts | One `contract.json` per skill | Explicit inputs, outputs, capabilities, effects, and completion conditions. |
| Shared references | Execution protocol and artifact schema bundled in every skill | Consistent statuses, evidence, authorization, handoffs, and independently verifiable output structure. |
| Workflows | JSON recipes in `workflows/` | Named dependency graphs with explicit artifact bindings. |
| Schemas and examples | `schemas/`, `examples/` | Validate interchange records and demonstrate integration boundaries. |
| Adapter contracts | `adapters/` | Separate neutral skill behavior from environment-specific tool calls. |
| External GitHub host | [`grove/factory`](https://github.com/grove/factory) | Owns GitHub events, credentials, candidate execution, draft publication, and quality checks; consumes sfstack through the pinned public CLI. |
| Reference tools | `tools/` and `tests/` | Validate the library, inspect readiness, assess gates, and export skills. |
| Behavioral evaluation | [Seed case and rubric](evals/README.md) | Exercise skills on an isolated coding task and report evidence and limits. |

The reference tools validate local records. A [bounded local runner](docs/how-to/run-local.md)
can dispatch **trusted Python adapters** for effect-free skills, validate their
results, and save a checkpoint after each step. A
[reference unittest adapter](examples/adapters/README.md) executes real checks
on pinned candidates. These tools supply no sandbox or production tool boundary.
The separate [factory host](https://github.com/grove/factory) connects Copilot
through Agentic Workflows, publishes evidence-backed checks, and builds bounded
changes into draft pull requests. Its GitHub workflows and operational tests
are maintained there. Independent human approval remains separate. The library does not
supply a tracker, merge queue, or deployment service. A production controller must provide persistence,
authentication, isolation, scheduling, and enforcement at the actual tool
boundary. See [factory architecture](docs/explanation/factory-design.md).

## Use a skill

Choose a directory from the [catalog](docs/reference/catalog.md). Give the agent
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
