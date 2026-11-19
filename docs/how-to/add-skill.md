# Add or change a skill

Use this guide when an observed task exposes a gap in the library. First decide
whether the gap belongs in a skill, a workflow, an adapter, or project policy.
A provider-specific command belongs in an adapter; a new order of existing
capabilities belongs in a workflow.

## 1. Define the responsibility

Describe the task, the inputs available at entry, the result at exit, and the
failure that current skills do not handle. Find the nearest entries in the
[catalog](../reference/catalog.md). Extend one when the responsibility remains
coherent; add a skill when it needs a distinct contract and can be used alone.

Choose a name of the form `sf-verb-object`, using lowercase letters, digits, and
single hyphens. Keep it under 64 characters. The directory, frontmatter name, and
contract ID must match.

## 2. Write the standard entry point

Create `skills/<name>/SKILL.md` with `name` and `description` YAML frontmatter.
Describe what the skill does and the circumstances that should select it.
Use a single line for each field and a JSON-quoted description string, matching
the repository's canonical frontmatter convention.

In the body, include the responsibility, required inputs, a bounded procedure,
expected output content, completion checks, failure handling, and a concrete
example. Link the local `contract.json`, `references/protocol.md`, and
`references/artifact.schema.json`. Require output JSON to validate against the
bundled schema. Make optional handoffs explicit, without requiring another skill
to be installed.

Keep task-specific reasoning in the skill and shared rules in the protocol. Avoid
universal demands for a language, tool, model, tracker field, test framework, or
number of agents. State which observable property matters and let the adapter
supply the environment-specific operation.

## 3. Declare the machine interface

Write `contract.json` using the [skill contract schema](../../schemas/skill-contract.schema.json).
Declare required and optional inputs separately. Use established artifact types
where their meaning fits; do not reuse a type for a different meaning merely to
make a workflow validate.

Declare every baseline capability and possible side effect. Add specific
completion checks and failure modes. Set a finite retry limit appropriate to the
work. The contract describes requirements; it does not create authorization.

Separate baseline `effects` from genuinely conditional operations. Declare each
conditional with its triggering condition, and require the host to select it for
the invocation. An omitted conditional effect must remain prohibited. Do not use
a conditional to hide an effect the normal task always requires.

Generate the shared protocol and output-schema copies:

```sh
python tools/sync_protocol.py
```

## 4. Connect the documentation and workflows

Add a catalog entry and describe the output in the relevant reference. Update a
recipe only if the new responsibility is required for that recipe's goal; optional
risk checks belong in a selected project variant. Bind each required input to a
workflow input or an ancestor's declared output.

Add a tutorial only if the new skill needs a distinct learning exercise. Add a
how-to when it enables a new practical task. Keep implementation rationale in
explanation, not in every execution instruction.

## 5. Validate and evaluate

```sh
python tools/validate.py
python tools/sync_protocol.py --check
python -m unittest discover -s tests -v
```

Then run representative tasks with the candidate skill, including a case where
success is impossible because a capability or evidence is missing. Confirm that
the skill reports the limitation accurately. Use a fresh agent context when
checking generalization; do not include the expected answer in the task prompt.

Record versioned results using [the evaluation guide](evaluate-quality.md).
Structural validation is necessary for interoperability but does not prove task
quality.

## 6. Review the public interface

Check the change against current consumers. Renaming an input, tightening a
required field, changing the meaning of a status, or adding a required effect
can break an integration. Version the skill accordingly and explain how existing
workflows and evidence must migrate.
