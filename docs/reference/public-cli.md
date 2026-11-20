# Public contract and gate CLI (v1.0)

This is the **portable, read-only sfstack interface** for a future independent
factory host. It is not a controller, GitHub adapter, runner, credential broker,
or a new authorization model. The only supported machine entrypoint is
**sfstack-contract** from the **sfstack-contracts** distribution. Python modules
under tools/ and integrations/ are implementation details, not import APIs.

## Install a pinned distribution

The repository builds version **1.0.0** of the distributable wheel. This
documentation does **not** assert that a PyPI package or GitHub Release has
been published. A host must acquire the versioned wheel from an independently
controlled release/artifact channel and verify its independently pinned SHA-256
before installation. For a local, reproducible build from a trusted sfstack
release checkout:

    python -m pip wheel --wheel-dir wheelhouse .
    sha256sum wheelhouse/sfstack_contracts-1.0.0-py3-none-any.whl
    python -m venv consumer-venv
    consumer-venv/bin/python -m pip install --no-index --find-links wheelhouse \
      'sfstack-contracts==1.0.0'
    consumer-venv/bin/sfstack-contract version

For production, **pin and verify the exact wheel digest** when promoting the
artifact (not merely its version string), retain its dependency lock/attestation,
and install that verified wheel in an isolated environment. Do not install a
mutable main branch or import Python files from an sfstack checkout. The
wheel includes the canonical schemas, skills, protocol references, and recipes
as a build-time snapshot. It does not read the build checkout at runtime.
The supplied **tests/external_consumer/run.sh** makes a version-pinned wheel,
installs it and its dependencies into a fresh virtual environment, copies only
untrusted fixture data to an unrelated directory, and exercises the executable
without any source imports, sys.path edits, or assumed working directory.

## Commands

All paths are host-selected filesystem inputs. Relative paths are relative to
the caller's working directory, **not** to the sfstack source tree.

| Operation | Arguments | Result |
| --- | --- | --- |
| version | none | Interface and distribution versions. |
| resolve | --skill ID | Canonical versioned contract, skill instructions and execution protocol. |
| schema | --name NAME | Existing canonical JSON Schema by name, e.g. artifact, policy, gate-request, run. |
| recipe | --name NAME | Existing canonical workflow recipe by name, e.g. quality, feature. |
| artifact | --path FILE --request FILE --policy FILE [--type TYPE] [--at UTC] | Inspect one artifact, its subject/run, freshness, checks and retained evidence bytes. |
| plan | (--workflow FILE or --recipe NAME) --run FILE [--at UTC] | Bind an existing recipe to a fixed checkpoint and evaluate eligible steps. |
| gate | --request FILE --policy FILE [--at UTC] | Evaluate exact-scoped grants and proof requirements for one effect. |

The artifact command takes the same existing gate-request schema for the
immutable **subject** and **run_id**, and the existing policy for its maximum
evidence age. The host prepares and retains input/output envelopes conforming
to the schema returned by schema, provides verified subjects and physical
evidence, and calls artifact/gate to validate them. The CLI cannot invent
authenticated evidence or attest that a worker's claims were observed.

An **offline fixture** can be invoked from any directory containing a copy of
examples/ (never use this backdated clock for a live decision):

    sfstack-contract gate --request examples/gate-request.json \
      --policy examples/policy.json --at 2026-11-19T12:00:00Z

Live hosts omit --at to use the current UTC clock. Reject path traversal,
symlink escapes, missing/changed retained bytes, stale observations, changed
subjects and unsatisfied required checks using the canonical validators.

## Response contract and exit codes

Every non-help invocation emits **exactly one JSON object on stdout**; neither
warnings nor error prose are intermixed. The stable top-level keys are:

    {
      "interface_version": "1.0",
      "distribution_version": "1.0.0",
      "operation": "gate",
      "status": "blocked",
      "result": {
        "decision": "blocked",
        "effect": "integration.modify",
        "scope": "the-exact-host-scope",
        "reasons": ["No current exact-scope authorization for ..."]
      },
      "errors": []
    }

The example is schematic, not a result from a live evaluation.
Exit **0** means status passed, exit **2** means status blocked, and exit
**64** means status invalid. Invalid invocations (missing/unknown flags, unknown
resource, malformed request or policy JSON/schema, invalid UTC time, unavailable
control files) return result null and nonempty errors. Valid controls referring
to malformed/missing evidence return blocked, **not passed**, with reasons in
result. Callers MUST check **both** exit code and status, and for a gate also
require result.decision == allowed. Never infer effect authorization from a
planner's successful execution: plan result.status distinguishes ready, blocked
and complete, and complete does not mean the candidate's quality passed.

A denied gate is an **expected negative result**, not an invalid call. Error
message text is diagnostic and may evolve; do not parse prose. Host-policy
files, authorization grants, subjects, artifact paths, evidence SHA-256 digests,
and selection of effects/recipes are supplied by trusted code, never by an
agent's free-form response. No command performs a GitHub mutation or invokes a
candidate agent.

## Compatibility policy

- **interface_version** uses MAJOR.MINOR. A new minor may add commands,
  optional fields or new bundled resources without changing the meaning of
  existing fields, statuses, exits, or required flags. Removing/renaming
  commands or response fields, changing exit-code/status meanings, or
  weakening the fail-closed contract requires a new major interface version.
- **distribution_version** uses SemVer and pins an immutable implementation
  plus bundled policy/contract resources. Existing sfstack JSON schemas and
  per-skill contract versions remain authoritative; the CLI neither
  auto-upgrades their data nor silently accepts unknown schema versions.
- A factory host should check version and refuse unsupported interface or
  schema major versions; pin its distribution and dependencies, run its own
  regression suite and re-verify artifact checksums on upgrades.
- Versions and exit codes are not credentials or grants. Source verifiers
  remain responsible for cryptographic digests, independent host
  observations, and exact immutable subject identity.

## Current GitHub self-host boundary and conversion plan

The existing **integrations/github/quality.py finalize** path now shells out
to the public gate command, checks both the JSON response and process exit,
records the versioned envelope in authorization-interface.json, and preserves
the earlier authorization-gate.json result for existing consumers. The
adapter still resolves the CLI through its trusted controller checkout; it is
**not** yet an independently versioned GitHub host. Agent and verification
jobs receive no new GitHub permissions.

Remaining internal dependencies are explicit:

- **integrations/github/quality.py:** common artifact/path/schema helpers,
  factory plan, quality_report consolidation, render_invocation, plus local
  workflow and policy file reads.
- **integrations/github/software.py:** common helpers, factory plan,
  quality_report status, render_invocation, quality/defect helpers, and local
  workflow/schemas. **integrations/github/defect.py** also imports common.
- **integrations/github/automation.py:** owns authenticated GitHub
  publication/check-run operations; it should remain on the host side, not
  move into the portable CLI.

Follow-up conversion should replace planner, artifact validation, skill
rendering and consolidation calls with carefully selected CLI operations
where they cross the host boundary, then install a digest-pinned release in
trusted controller jobs and remove source-tree imports/layout assumptions.
Controller-owned PR admissions, GitHub events/API credentials, isolated
candidate execution, independent checks, draft publishing and check-run
ownership remain host responsibilities. Do not relax existing at-most-once
recovery or treat Copilot's success label as verification evidence.

Extraction to a separate factory repository is explicitly **out of scope**
until the acceptance suites for issues #29 and #30, including any required
live recovery exercise and human review, are separately satisfied.
