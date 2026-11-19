# Evidence and consistent quality

Consistency does not require every agent to write identical code. It requires
stable meanings for inputs, outputs, completion, and uncertainty. Two agents may
choose different valid implementations while producing evidence that lets a
reviewer assess both against the same acceptance criteria.

## A result is a claim with a subject

A verification result describes one candidate under particular inputs and an
environment. If any relevant part changes, the old result no longer proves the
new candidate. sfstack makes that subject explicit through `revision`,
`input_digest`, and `environment`.

The reference planner deliberately uses a fixed-subject checkpoint. This is
conservative: it may require revalidation even when a skilled operator can see
that only some evidence changed. It avoids silently carrying obsolete results
across revisions. A production controller can implement more precise dependency
tracking, provided it records why each reused result still applies.

Artifact identity and content hashes help detect missing or altered evidence.
They do not prove that a log is truthful, that an agent followed its instructions,
or that an approval came from an authorized person. The host must establish
those trust properties at the execution boundary.

## Four terminal states preserve useful distinctions

`passed` means the responsibility's criteria were satisfied. `failed` means
observed behavior or results violated a criterion. `blocked` identifies a missing
prerequisite, capability, or authority. `inconclusive` means available evidence
cannot settle the claim.

These distinctions matter operationally. A failed check calls for investigation
or a repair. A blocked runtime requires access or a different agreed scope.
An inconclusive performance measurement may require a better experiment. Calling
all three failures obscures the next action; calling any of them success hides
work that remains.

A completed plan can pass as a plan while its implementation remains untouched.
The artifact type and payload bound the claim. Downstream consumers must not
interpret the word `passed` without reading what was actually assessed.

## Evidence should match the question

A source inspection may establish that a branch exists; it cannot establish that
a deployed service is running that branch. A unit test may establish behavior at
one seam; it cannot automatically establish the full user journey. A deployment
command may finish while the wrong revision serves traffic.

For each acceptance criterion, choose a check that would fail if the relevant
behavior were wrong. Record what it covers and what it leaves unresolved. Prefer
the smallest reliable evidence that settles the risk, then widen the check only
when a concrete uncertainty remains.

## Review and verification support each other

Tests exercise selected behavior. Review can detect missing assumptions,
maintainability problems, unsafe boundaries, and flaws in the tests themselves.
Neither is a universal substitute for the other. Independent review is valuable
when risk or policy warrants it, but adding reviewers without a clear question
can add disagreement and cost without better decisions.

Review findings should identify the candidate, relevant evidence, consequence,
and disposition. A finding does not become valid because several models repeat
it. A dismissed finding should retain a reason; a fixed finding needs fresh proof.

## Quality evolves through observation

Measure the real failure modes of the work. Repeated errors may call for a type
constraint, an executable invariant, a better adapter, clearer acceptance
criteria, or a skill change. More prose is not always the best repair.

The goal is a system in which unsupported claims are hard to advance and useful
corrections are easy to preserve. Behavioral evaluation, not the size of the
catalog or the length of a checklist, determines whether that system improves
outcomes.
