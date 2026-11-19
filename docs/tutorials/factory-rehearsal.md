# Rehearse a factory workflow

This exercise uses only synthetic local files. You will inspect a workflow's first
ready step, evaluate an example integration gate, observe a stale-candidate
rejection, and normalize two tracker exports. No agent is launched and no tracker,
repository, or deployment service is changed.

You need Python 3.11 or newer and a checkout of sfstack. Run the commands from the
repository root. The fixed evaluation time makes this fixture reproducible even
after its example grants have expired in real time.

## 1. Validate the library

```sh
python -m pip install -r requirements-dev.txt
python tools/validate.py
python tools/sync_protocol.py --check
```

Both checks should succeed. They establish structural consistency: the packages,
contracts, shared protocol and artifact schema, recipes, and covered examples agree. They do not prove
that a live agent has successfully delivered software.

Open [feature.json](../../workflows/feature.json). Its first node is `orient`,
which consumes the external `request` through `sf-map-project`. Later steps refer
to declared outputs from their ancestors.

## 2. Inspect the initial checkpoint

```sh
python tools/factory.py plan \
  --workflow workflows/feature.json \
  --run examples/feature-run.json \
  --at 2026-11-19T12:00:00Z
```

The result includes:

```json
{
  "workflow": "feature",
  "run_id": "tutorial-run",
  "status": "ready",
  "ready": ["orient"],
  "completed": []
}
```

The full response also lists blocked reasons for later steps. They are waiting
for prerequisite outputs. Nothing has executed: `ready` describes what a
controller could schedule after enforcing the relevant runtime boundaries.

Open [feature-run.json](../../examples/feature-run.json). Observe its fixed subject,
available capabilities, exact effect scopes, policy path, input artifact paths,
and empty completed-step map. This is one checkpoint, not an automatic record of
future source revisions.

## 3. Evaluate an example integration gate

```sh
python tools/factory.py gate \
  --request examples/gate-request.json \
  --policy examples/policy.json \
  --at 2026-11-19T12:00:00Z
```

The response is:

```json
{
  "decision": "allowed",
  "effect": "integration.modify",
  "scope": "repository:demo/change:42",
  "reasons": []
}
```

The fixture has matching grant, subject, verification, review, and review-status
records. Its evidence files are explicitly synthetic. The checker verifies the
supplied record relationships and hashes; it does not establish that a real test
ran or a real authority granted permission. An actual host must establish those
facts and enforce the decision against the live target.

## 4. Observe a stale-candidate rejection

```sh
python tools/factory.py gate \
  --request examples/gate-stale-request.json \
  --policy examples/policy.json \
  --at 2026-11-19T12:00:00Z
```

This command intentionally exits with code `2`. Its response has
`"decision": "blocked"` and reasons identifying the unmatched subject and stale
evidence. The request names a different candidate while retaining proof for the
old one.

Do not repair this by editing evidence timestamps or candidate IDs. A real change
requires revalidation and a correctly scoped grant. For this exercise, simply
compare the two request files and see which field caused the rejection.

## 5. Normalize two tracker shapes

```sh
python tools/tracker.py \
  --mapping examples/tracker-mapping.json \
  --item examples/tracker-item.json

python tools/tracker.py \
  --mapping examples/tracker-mapping-nested.json \
  --item examples/tracker-item-nested.json
```

Both results identify item `DEMO-7`, canonical state `ready`, and version `"3"`.
The `source` fields preserve their different native shapes and state names.
Neither command contacts a tracker.

This is the adapter boundary: skills can consume a stable work-item meaning even
when providers arrange fields differently. A writable live adapter needs further
contracts for permissions, conditional updates, idempotency, and recovery.

## 6. Inspect what remains to build

The exercises evaluated data; they did not run a software factory. A production
controller would dispatch the ready skill, preserve results durably, acquire
leases, enforce action gates, reconcile unknown outcomes, and advance to a new
checkpoint when the candidate changes.

Read [operate a factory controller](../how-to/run-factory.md) to implement that
loop, or [connect a coding agent](../how-to/connect-agent.md) to qualify one
execution host first. The [tooling reference](../reference/tooling.md) documents
the command interfaces and exit codes used here.
