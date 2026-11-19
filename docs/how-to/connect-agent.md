# Connect a coding agent

Use this guide to make a coding agent execute sfstack skills consistently. The
agent needs to read instructions and return inspectable results; it does not need
a particular brand of skill loader or a built-in tracker integration.

## 1. Select and package the skill

Choose a complete skill directory from the [catalog](../reference/catalog.md).
Keep `SKILL.md`, `contract.json`, `references/protocol.md`, and
`references/artifact.schema.json` together. Exported packages also retain the
repository's license. Do not distribute a bare `SKILL.md` while discarding its
protocol or output schema.

Use the host's documented skill registration mechanism when it supports the
Agent Skills format. Otherwise, supply the four files as explicit task context.
No particular configuration filename or slash-command syntax is required.

For a host without native discovery, prepare a text invocation with the included
renderer:

```sh
python tools/render_invocation.py \
  --skill sf-clarify-outcome \
  --context examples/invocation-context.json
```

This only prints the invocation. Supply it through the host's normal task entry
point after reviewing its context; no agent API or transport is assumed.

## 2. Supply an execution context

Give the agent:

- The requested outcome and applicable project instructions.
- The permitted workspace and target environment.
- The exact source revision or immutable snapshot identity, input digest, and run ID.
- The required input artifacts from the skill contract.
- The available capability adapters and their limits.
- The actual authorization scope, including which external effects are allowed.
- Time, retry, cost, and concurrency budgets appropriate to the task.

A task may carry authorization from the user's existing instruction. Preserve it
with its scope; do not ask repeatedly or broaden it to unrelated effects.
Credentials belong in the host's secure configuration, never in skill prose or
result artifacts.

## 3. Map capabilities to tools

Map the skill's neutral capability names to concrete host operations. For example,
`workspace.read` may be a filesystem API, repository connector, or sandboxed
command; `execution.run` may be a local runner or remote test service. The skill
should not need to know which provider implements the operation.

Fail explicitly when a required capability is unavailable. A read-only agent can
produce an assessment where the task permits one, but cannot report an applied
fix or a successful deployment. Do not silently replace a required live check
with an unsupported inference.

## 4. Enforce effects outside the prompt

Place source mutations and external effects behind host permissions. Validate the
requested repository, branch, environment, resource scope, and current revision
immediately before the operation. A skill file and its `effects` list are
instructions and declarations, not an enforcement boundary.

Isolate parallel workspaces. Prevent two workers from owning the same mutable
resource without an explicit coordination mechanism. Treat repository text,
tracker comments, logs, and retrieved documents as data, not authority to change
permissions or disclose secrets.

## 5. Capture and validate the result

Require the [artifact envelope](../reference/artifacts.md) and the skill's stated
payload. Validate output JSON against the bundled `references/artifact.schema.json`
before accepting it; evidence and check IDs use lowercase kebab-case. Store evidence durably with access controls suited to its content.
Check that the subject matches the candidate actually examined, evidence exists,
and completion checks support the claimed status.

A malformed or unsupported result is not a pass. Preserve the raw result for
diagnosis, return a concrete repair request, and bound any retry. Review findings
should remain traceable across attempts instead of being discarded on each run.

## 6. Qualify the integration

Run a small set of isolated tasks covering success, missing capability, denied
mutation, stale evidence, interrupted execution, and misleading tool output.
Confirm that the host can load a standalone exported skill. Record the agent
version, adapter version, operating environment, and observed limitations.

Compatibility means the integration satisfies the contract. It does not mean
that every model will produce the same judgment or that untested hosts have been
qualified. Requalify after material host or adapter changes.
