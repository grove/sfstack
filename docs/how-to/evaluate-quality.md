# Evaluate skill quality

Use the [included behavioral seed and rubric](../../evals/README.md) to rehearse
the process below. It records a narrow observed exercise and its limitations;
build a broader corpus before making comparative effectiveness claims.

Use this guide before adopting a new skill version or granting a workflow more
autonomy. Evaluate whether it improves the task outcome, not whether its answers
sound more thorough.

## 1. State a falsifiable claim

Write the expected improvement and its cost boundary before running the
comparison. For example: fewer incorrect resolutions of concurrency defects,
without more than an agreed increase in execution time. Choose an observable
failure the evaluation can distinguish from a successful result.

Separate correctness, usefulness, and operational safety. An accurate review with
many irrelevant findings may slow delivery; a fast implementation that silently
skips verification has not met the same task.

## 2. Build representative cases

Include normal tasks, boundary cases, and realistic failures. Cover different
project structures, target technologies, and adapters relevant to the intended
use. Keep held-out cases that were not used to tune the instructions.

For a factory integration, include missing runtime access, zero executed tests,
stale evidence, conflicting item versions, wrong deployment identity, duplicate
requests, interrupted writes, and untrusted text asking for additional authority.
Use synthetic data and isolated resources for destructive scenarios.

## 3. Compare under controlled conditions

Compare the candidate against the current skill and, where useful, the same agent
without the skill. Fix task inputs, tool access, budgets, and scoring criteria.
Record agent version and configuration. Use repeated trials when variability can
change the conclusion, and report uncertainty rather than overinterpreting one
favorable run.

Keep the evaluator independent of the expected implementation. Use acceptance
tests, external observations, or blinded review suited to the task. A second
model agreeing with the first is evidence about agreement, not proof of truth.

## 4. Record a useful result

For each trial, retain:

- Task identity, candidate skill/version, and exact input/environment identity.
- The artifact and raw evidence necessary to inspect the outcome.
- Correctness against the agreed criteria and any unsupported claims.
- For review tasks, verified findings, missed defects, and false alarms.
- Time, resource use, repair rounds, and operator intervention.
- Permission, recovery, and idempotency failures, even if the eventual task succeeded.

Distinguish blocked trials from failed behavior. A tool outage should not be
quietly counted as a correct solution or silently dropped from the report.

## 5. Decide and follow through

Promote the change only if the evidence supports the stated claim and its
tradeoffs are acceptable. Keep it experimental, revise it, or remove it when it
adds cost without demonstrated benefit. Report which populations and environments
the conclusion applies to.

Use `sf-evaluate-skills` to structure an evaluation and `sf-improve-process` to
turn repeated observed failures into bounded improvements. Structural checks in
this repository do not replace these behavioral evaluations, and sample fixtures
are demonstrations rather than proof of broad effectiveness.
