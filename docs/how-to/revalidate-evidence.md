# Plan evidence revalidation after a candidate changes

The [artifact identity contract](../reference/artifacts.md) intentionally rejects
stale evidence at gates. This tool **does not** weaken that rule. It helps a host
identify which claims to recheck after an implementation, rebase, or integration.

Use a trusted host to inventory the bytes and configuration affecting each
claim. Represent their SHA-256 digests under `before.inputs` and `after.inputs`,
and identify both checkpoints through their full `subject`. For each claim,
declare `depends_on` input keys and `needs` upstream claims. Set
`complete_inventory` to `false` if the host cannot prove it captured every
relevant input.

Run:

```sh
python tools/evidence_impact.py --manifest examples/evidence-impact.json
```

The result distinguishes `revalidate` from `reuse-candidate`. In the example,
the specification is a reuse candidate, while implementation, verification,
and review require new evidence because the source dependency changed.

**A reuse candidate is not valid proof at a new checkpoint.** The host must
authenticate the inventory, check that the claim's declared dependencies are
complete, and explicitly produce a new scoped decision before advancing. Gate
checks continue requiring exact subject equality. For changed environments,
missing dependencies, empty dependency declarations, or inconsistent input
digests, the planner conservatively requests revalidation.

The reference implementation is a static dependency analysis, not an automated
attestation service. It does not inspect a repository, certify that a test ran,
infer which checks are affected by an arbitrary diff, or launch an agent.
