# Behavioral evaluation seeds

The regression suite in `tests/` checks sfstack's reference tooling. These cases
instead exercise an agent using the skills. Keep the candidate workspace and
grader separate so the worker receives the task and initial files, not a supplied
repair or grading implementation. Run candidate code only in an isolated
environment with the permissions and resource limits appropriate to that code.

## Inventory boundary case

Copy `cases/inventory-boundary/task.md` and the contents of its `seed/` directory
into an isolated temporary workspace. Give a fresh agent that task and the complete
packages for `sf-diagnose-defect`, `sf-build-change`, and `sf-verify-change`. Let it
derive the small specification, single-item plan, and test plan. Grant local edits
and Python execution in that workspace only. Do not provide the hidden grader or
an expected patch to the worker.

After the worker returns, run the independent public-behavior grader:

```sh
SFSTACK_CANDIDATE_DIR=/absolute/path/to/candidate \
  python -m unittest discover -s evals/cases/inventory-boundary/grading -v
```

Inspect the worker's own evidence as well. A correct final function does not prove
that the agent reproduced the defect, preserved scope, obeyed the budget, or
returned conforming artifacts. Use the [rubric](cases/inventory-boundary/rubric.json)
for those checks. Validate each emitted JSON envelope against
[artifact.schema.json](../schemas/artifact.schema.json) and inspect actual retained
evidence hashes. Record a failed or inconclusive dimension separately.

This seed is small and deterministic. It is suitable for checking basic behavior
and packaging, not for estimating broad engineering effectiveness. Expand the
corpus across project types, languages, failure modes, tools, and missing-capability
conditions before making comparative quality or autonomy claims. Keep held-out
cases separate from authoring examples and record the agent, model, tools, skill
versions, cost, and evaluation conditions for every comparative run.

## Initial observed exercise

On 2026-11-19, one isolated agent exercise used the diagnosis, implementation, and
verification skills on this case with CPython 3.12.14. The original three tests
passed. The agent found the rejected equality boundary, added a regression that
failed against the original implementation, made the one-character comparison
correction, and finished with six passing tests. It stayed within three diagnosis
probes and one repair attempt. No external system was contacted by that exercise.

The initial output envelopes failed the repository schema because their check
and evidence identifiers used uppercase letters and their environment identity
used an object where a string was required. This exposed a distribution
gap: the result schema was not included in standalone packages. The packages now
carry the exact schema and explicit output validation instructions. Corrected
reports then passed all three schema validations and all three retained-evidence
inspections without changing the behavioral evidence. The
[observed report](reports/2026-11-19-inventory/summary.json) retains the repair diff
and red/green runner output with documented path normalization. This is an
observed failure and correction, not a claim that the initial exercise passed
every dimension. The exercise establishes neither an advantage over an unskilled
baseline nor compatibility with other agents, trackers, or production systems.

## Comparative results format

Use [the paired-trial comparison guide](../docs/how-to/compare-trials.md)
to record bare-agent, instructions-only, and contracts-and-gates outcomes on
the same cases, agent, tools, and environment. The included comparison JSON is
explicitly synthetic; no comparative experiment has been run by this addition.
