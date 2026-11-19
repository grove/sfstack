# Trusted Python unittest adapter

[`python_unittest.py`](python_unittest.py) is a small executable example for
`sf-verify-change`. It uses the [local adapter invocation contract](../../docs/tutorials/local-slice.md),
runs real Python `unittest` checks in a subprocess, and retains stdout, stderr,
structured test counts, and failing test IDs. It does not install dependencies,
invoke an agent, or authenticate evidence producers.

Run it only on code and tests the host has placed in an appropriately isolated
environment. A subprocess is not a sandbox. The host supplies permissions,
resource limits, and any network restrictions; the adapter supplies a timeout.

## Supply a test plan

The bound `test-plan` artifact needs this adapter-specific payload:

```json
{
  "python_unittest": {
    "candidate_dir": "candidate",
    "tests_dir": "tests",
    "candidate_sha256": "<directory digest>",
    "tests_sha256": "<directory digest>",
    "required_tests": ["test_inventory.InventoryContract.test_exact"],
    "timeout_seconds": 30
  }
}
```

Both directories are relative to the test-plan file and must stay below its
directory. Copy the selected repository or PR candidate into `candidate/` and
the independently selected checks into `tests/`. The adapter's `snapshot_digest`
helper computes each digest over sorted relative filenames and file SHA-256
values, excluding only top-level `.git` metadata; links and non-regular source
files are rejected. The run's subject revision can identify either:

- A copied snapshot: `sha256:` followed by the candidate digest. Record the
  original commit or PR head/base separately in the scope artifact's provenance.
- A Git checkout: the exact full commit ID. The candidate must be the Git root,
  `HEAD` must match, and the checkout must be clean both before and after testing.
  Git reads disable filesystem-monitor hooks and optional index writes.

Both forms still require the source and test-directory digests. The Git form
works with a run initialized from that same clean commit; place the checkout
below the test-plan directory to keep its paths contained. This adapter does
not fetch GitHub or establish the source's authenticity.

Required IDs are Python unittest IDs, including module, class, and method. A
missing required ID, a skip, empty discovery, a runner failure, or changed inputs
cannot produce a passing result. An observed test failure remains `failed`.
The adapter checks both directory digests before and after execution. It does
not rewrite the candidate or retry failed tests.

Candidate modules take precedence over equally named test helper modules.
Discovery and suite setup/teardown errors are retained separately from executed
test failures; they produce an inconclusive report with their logs, including
when no test method could run.

Then dispatch the verification node with the existing local harness:

```sh
python tools/local_slice.py --workflow workflows/quality.json \
  --run /path/to/run/run.json --step verify \
  --adapter-script examples/adapters/python_unittest.py \
  --out-run after-verify.json --artifact-dir verification
```

The prerequisite scope, specification, and test-plan records must already be
valid and the `verify` step ready. The new checkpoint retains a valid negative
verification result for review and consolidation. Later steps require their own
appropriate adapters or supplied reports; this adapter handles verification only.

For a complete reproducible exercise, run:

```sh
python evals/run_quality_regression.py --output /tmp/sfstack-quality-regression
```

Use a new output directory. See the [evaluation guide](../../evals/README.md)
for expected results and the distinction between real test execution and fixture
planning/review records.
