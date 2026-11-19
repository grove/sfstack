# Contributing

Contribute changes that improve a demonstrable task outcome, remove an ambiguity,
or strengthen interoperability. Start with a concrete failure, missing capability,
or repeated source of rework. A new skill needs a responsibility that existing
skills cannot express cleanly through composition.

## Development loop

1. Read the relevant skill, its contract, and the [execution contract](docs/reference/contracts.md).
2. Define the observable improvement and a representative task that would expose a regression.
3. Change the smallest coherent unit. Keep target-language and tool-provider details in adapters or examples.
4. Update the corresponding documentation quadrant: a tutorial teaches, a how-to solves a task, reference specifies, and explanation develops the reasoning.
5. Validate structure and run the relevant behavioral checks.
6. Review the resulting diff for unsupported claims, changed authorization scope, stale evidence rules, and broken handoffs.
7. Submit a review describing the problem, resulting behavior, validation, and remaining limits.

```sh
python -m pip install -r requirements-dev.txt
python tools/validate.py
python tools/sync_protocol.py --check
python -m unittest discover -s tests -v
```

If the shared protocol or artifact schema changes, regenerate its bundled copies
with `python tools/sync_protocol.py`, then review the canonical sources and the
exported copies. Edit [protocol/execution.md](protocol/execution.md) or
[schemas/artifact.schema.json](schemas/artifact.schema.json), not one isolated
skill's generated reference.

## Authoring requirements

- Keep names in the `sf-verb-object` form and match the skill directory, frontmatter, and contract ID.
- Describe triggering situations in the frontmatter. Keep the body focused on execution.
- Use canonical one-line frontmatter fields with a JSON-quoted description scalar.
- Define required inputs, specific output content, executable checks where applicable, and honest stop conditions.
- Keep every skill usable without another skill installed. Optional handoffs name a capability; they do not silently invoke it.
- Declare all required capabilities and effects. Do not use a declaration, a workflow edge, or a previous successful run as authorization.
- Declare conditional effects explicitly and require a host selection; an omitted conditional is prohibited for that invocation.
- Preserve the distinction between producing a plan, carrying out an operation, and verifying its outcome.
- Never interpret unavailable checks, zero executed tests, missing review, or uncertain deployment identity as success.
- Keep loops finite and resumable. State what an operator needs to do after a blocked or inconclusive result.
- Add only resources the skill actually needs. Keep shared background out of every instruction body.

See [add or change a skill](docs/how-to/add-skill.md) for the detailed procedure.

## Contract changes

Treat input/output names, required fields, status meanings, capability semantics,
and workflow bindings as public interfaces. A change that makes an existing valid
consumer fail is breaking, even if it only changes prose. Increment the skill
version and document migration requirements. Change `schema_version` only when
the interchange schema changes; skill and schema versions serve different roles.

Keep old evidence attached to the version that produced it. Do not relabel old
runs as results from the new skill. New evaluation must use the exact candidate
being proposed.

## Evaluation

Structural checks detect invalid files and broken composition; they cannot prove
that a skill improves an agent's judgment. For material behavior changes, compare
the candidate with the current version and an appropriate baseline on held-out
tasks. Record environment, tool access, task outcomes, verification evidence,
error classes, cost, and time. Evaluate high-impact actions through isolated
fixtures before connecting live services.

See [evaluate skill quality](docs/how-to/evaluate-quality.md). Tests must protect
an observable contract or failure mode, rather than restating implementation.

## Review boundaries

A contribution does not authorize merging, publishing a release, changing a
production deployment, or contacting people. Use the repository's configured
review and release process. Keep secrets and personal records out of examples,
logs, and evaluation fixtures.
