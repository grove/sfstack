# Rehearse Quality Factory without a live agent

All fixtures are **synthetic** and use a fictional display-name component.
They demonstrate the workflow's reporting behavior, not real test execution,
PR inspection, or independent review.

From the repository root, inspect the initial ready frontier:

```sh
python tools/factory.py plan --workflow workflows/quality.json \
  --run examples/quality-run.json --at 2026-11-19T12:00:00Z
```

Only `orient` is initially ready. There is **no** build step and no mutation
grant. The supplied `quality-ready-run.json` fixture contains recorded
outputs of the upstream steps, so `consolidate` is next.

Copy fixtures to a disposable working directory before invoking the reporting
utility (it writes a new output bundle and manifest):

```sh
cp -R examples /tmp/sfstack-quality-rehearsal
python tools/quality_report.py --workflow workflows/quality.json \
  --run /tmp/sfstack-quality-rehearsal/quality-ready-run.json \
  --out-dir output/normal --out-run quality-after.json \
  --at 2026-11-19T12:00:00Z
python tools/factory.py plan --workflow workflows/quality.json \
  --run /tmp/sfstack-quality-rehearsal/quality-after.json \
  --at 2026-11-19T12:00:00Z
```

The workflow now reports `complete`, while the quality assessment is
`inconclusive`: the policy requires independently authenticated review,
which this offline fixture cannot supply. Inspect
`output/normal/quality-assessment.json` and the retained
`output/normal/support/` evidence.

For a **known failure**, use `quality-failed-run.json` and a distinct output
directory and manifest. The assessment is `failed`, with a blocking finding
and the original failing verification evidence preserved.

For a **read-only pull request**, use `quality-pr-ready-run.json` with
`workflows/quality.json`; the target kind is `pull-request` and base/head
are preserved. For explicitly selected security and compatibility reports,
use `quality-risk-ready-run.json` with `workflows/quality-risk.json`.
An external-change request uses the same workflow with
`target_kind: external-change` and an immutable supplied source.

Do not backdate real evidence, use synthetic fixtures to authorize actual
integration, or interpret this exercise as a running production controller.
