# Connect an issue tracker

Use this guide to connect any tracker, task database, or file-based work queue.
Skills exchange neutral artifacts; an adapter translates them into the tracker's
fields and operations. A tracker is optional for single-agent local work.

## 1. Choose the system of record

Decide where work-item identity, dependencies, ownership, and completion live.
Use one canonical identity for each item even when it has links in several
systems. Store external provider identifiers as opaque values; do not derive
meaning from a provider's identifier format.

A tracker item is a projection of work state. Its label or column alone is not
proof that a change was tested, integrated, or deployed.

## 2. Map concepts explicitly

| sfstack concept | Adapter responsibility |
| --- | --- |
| Work item | Read and write an item with a stable identity and current version. |
| Outcome and acceptance criteria | Preserve meaning in the provider's available fields. |
| Dependencies | Represent prerequisite relationships, or maintain them in a companion artifact. |
| Owner or lease | Identify who may work on the item and when the claim expires. |
| Status | Translate local states without conflating reviewed, integrated, and deployed. |
| Evidence and artifact links | Preserve durable references to the results underlying a transition. |
| Update precondition | Detect a changed item before overwriting another actor's work. |
| Operation identity | Make retries detectable and avoid duplicate items or comments. |

Document any unsupported concept. If the provider cannot represent dependencies
or optimistic updates, a controller can maintain those guarantees in its own
store. If neither layer can guarantee them, reduce automation accordingly.

For exported JSON, try the included read adapter before building a live connector:

```sh
python tools/tracker.py \
  --mapping examples/tracker-mapping.json \
  --item examples/tracker-item.json
```

Create an explicit mapping for your export's object fields and native states.
The [nested example](../../examples/tracker-mapping-nested.json) demonstrates dotted
paths. The tool rejects missing fields and unmapped states instead of guessing.
It returns a validated canonical record without contacting the provider. See the
[tooling reference](../reference/tooling.md) for the supported mapping syntax.

## 3. Define transitions by meaning

Write the local mapping for states such as ready, active, waiting, blocked, and
complete. Include separate delivery facts where the tracker exposes only a single
closed state. Agree which event closes an item: accepted implementation,
integration, deployment, or a business outcome.

Before transitioning an item, reread its current version, confirm the transition
is valid, and attach the relevant artifact references. On a conflict, reload and
reconcile. Do not overwrite a newer instruction merely to make the automation's
expected state appear true.

## 4. Separate preparation from publication

Creating a work plan does not itself authorize posting issues, assigning people,
sending notifications, or changing shared workflow configuration. Apply the
user's existing authorization to the specific operation. If publication is
outside scope, keep a reviewable local artifact and report the blocked action.

Use a single operation key for a retried creation. After a timeout, inspect the
provider for the operation's result before repeating it. Distinguish unknown
outcome from failed operation; this matters when an item was created but the
response was lost.

## 5. Qualify read and write paths

Use an isolated project or a fake provider to exercise:

1. Reading an item with incomplete fields.
2. Creating a work item once despite repeated delivery.
3. Updating an item with a matching version.
4. Rejecting or reconciling a stale version.
5. Preserving dependency direction and unresolved blockers.
6. Recovering after a timeout with an unknown write outcome.
7. Refusing unauthorized comments, assignments, or status changes.
8. Keeping private content out of logs and evidence intended for wider audiences.

The [capability reference](../reference/capabilities.md) defines the neutral read
and write boundaries. Keep provider-specific field names and API commands in the
adapter configuration, not in every skill.
