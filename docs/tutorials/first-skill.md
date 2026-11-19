# Run your first skill

In this exercise you will use one portable skill to turn a small request into a
reviewable outcome brief. You will inspect its contract, prepare an invocation,
and check the result. No source changes, tracker writes, or live services are
needed.

You need a checkout of sfstack and a coding agent that accepts text or local
files. The optional invocation-rendering command also needs the repository's
Python development dependencies.

## 1. Read the skill boundary

Open [sf-clarify-outcome](../../skills/sf-clarify-outcome/SKILL.md) and its
[contract](../../skills/sf-clarify-outcome/contract.json). Its required input is a
`request`; its output is an `outcome-brief`. Its job is to make the outcome and
acceptance conditions explicit, not to implement or publish the change.

Read the bundled [protocol](../../skills/sf-clarify-outcome/references/protocol.md)
and [output schema](../../skills/sf-clarify-outcome/references/artifact.schema.json).
Notice that output status applies to the work actually performed. A completed
brief does not establish that software has been changed or tested.

## 2. Inspect the example request

Open [invocation-context.json](../../examples/invocation-context.json). The example
asks to persist an account display name and reject empty input without changing
saved data. It permits producing an artifact and grants no external effects.
It includes an embedded `inputs.request` artifact and a synthetic subject identity
so the result can retain the same revision, input digest, and environment. The
context also supplies the retained synthetic request text and its integrity
metadata for text-only use. Treat it as supplied input evidence, not evidence
that tests or any other operation ran.

This is a synthetic exercise. It does not contain credentials or a real customer
record. Keep the declared planning scope when giving it to the agent.

## 3. Prepare the invocation

From the repository root, run:

```sh
python -m pip install -r requirements-dev.txt
python tools/render_invocation.py \
  --skill sf-clarify-outcome \
  --context examples/invocation-context.json
```

The command prints one text package containing the skill, execution protocol,
machine-readable contract, output artifact schema, and supplied context. It does not send anything to a
model or execute the task. If your agent has native skill discovery, you can
instead provide the complete skill directory and the same context.

Give that package to your coding agent with this instruction:

```text
Perform this planning-only task using the supplied sf-clarify-outcome skill.
Return an outcome-brief with the declared artifact envelope.
Use only the supplied request and context. Ask only for decisions that materially
change the outcome, and keep unresolved decisions explicit.
Do not modify source files or contact any service.
```

## 4. Inspect what the agent produces

The brief should preserve the known behavior: a nonempty display name can be
saved, and empty input must leave the existing saved value unchanged. It should
separate those facts from decisions that were not supplied, such as length limits,
whitespace handling, visibility to other users, or the intended persistence scope.

Do not expect a particular architecture or data store. Those choices belong to
later design work. A useful brief defines the outcome without prematurely
committing the implementation.

Check the result against the skill's output section:

- Does it identify the intended user and observable outcome?
- Does it preserve the supplied acceptance condition?
- Does it distinguish assumptions from confirmed requirements?
- Are unresolved decisions and the next action visible?
- Does its status claim only the work actually completed?
- Does the envelope identify the run, subject, producer, and evidence?
- Does the output JSON validate against the bundled schema, including lowercase kebab-case evidence and check IDs?

If a material decision is missing, answer the agent's focused question or accept a
clearly stated assumption within the exercise. Do not fabricate runtime evidence
to make the brief look more complete.

## 5. Follow the handoff

The brief can now be consumed by `sf-write-specification`, by another agent, or by
a human reviewer. No special conversational memory is required: the next worker
receives the artifact and its scope.

You have exercised the central boundary in sfstack: one named responsibility,
explicit inputs, an inspectable result, and a clear next step. Continue with the
[factory rehearsal](factory-rehearsal.md) to see how the reference tools evaluate
workflow readiness and stale evidence.
