# Run a bounded local execution slice

[`local_slice.py`](../../tools/local_slice.py) is a **single-step reference
harness** that connects a validated workflow plan to an executable Python agent
adapter, validates the returned artifact and hashed evidence, and writes a
new checkpoint. It demonstrates dispatch and handoff, not a production controller.

For initialization and bounded multi-step execution over the same protocol, use
the [local CLI](../how-to/run-local.md). For real test execution on a pinned
candidate, see the [unittest adapter](../../examples/adapters/README.md).

A host must sandbox and authorize the adapter separately. This harness does
not prevent a malicious or buggy adapter from writing to disk or accessing
credentials. It refuses baseline or selected conditional external effects,
never merges, publishes, or deploys, and never overwrites the original manifest.

To inspect the adapter protocol, copy the example run, policy, and records
into a disposable directory (preserving their relative paths). Then run:

```sh
python tools/local_slice.py \
  --workflow workflows/feature.json \
  --run /tmp/sfstack-slice/feature-run.json \
  --step orient \
  --adapter-script tools/fixtures/synthetic_map_agent.py \
  --artifact-dir generated/orient \
  --out-run step-1.json \
  --at 2026-11-19T12:00:00Z
```

The synthetic adapter **does not perform project mapping** or invoke a model.
Its artifact establishes only a successful demonstration of file binding and
the result protocol. A real adapter must load the specified full skill package,
perform the requested work with host-supplied capabilities, and output a JSON
artifact plus evidence files relative to the result.

A step is eligible only if `factory.plan` marks it ready. After execution the
harness checks the claimed producer, skill version, subject identity, evidence
digests, required check statuses, and any recognized typed payload schema.
It emits a new run manifest referencing the result, then prints the next
ready frontier. Invalid results do not advance the checkpoint.

In quality mode, a valid `failed`, `blocked`, or `inconclusive` output is retained.
The workflow's explicit acceptance rules determine whether downstream reporting
may consume it. Software mode keeps the passing-only rule. An exclusive attempt
reservation prevents another dispatch of the same interrupted output; inspect
and reconcile an interrupted attempt before retrying it. Completed manifests
publish atomically and never replace an existing checkpoint.

This is intentionally **not** a feature-to-PR or deployment controller:
effectful execution, artifact storage transactions, locks, idempotency,
authentication, retries, branch management, provenance verification, and
post-integration revalidation require a trusted host.
