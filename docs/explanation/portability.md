# Portability and independence

A portable skill specifies the work and the evidence for its result. It does not
need to specify which vendor provides the editor, which syntax identifies an
issue, or which command starts the test environment. Those choices belong at the
boundary between the skill and its host.

## Three interfaces with different purposes

The `SKILL.md` entry point is the human- and agent-readable instruction interface.
Its directory shape follows the [Agent Skills specification](https://agentskills.io/specification).
An agent that does not implement that discovery format can still use the
instructions when they are supplied directly.

The sfstack `contract.json` is the composition interface. It states which inputs,
outputs, capabilities, effects, and completion criteria a controller should
expect. It is an additional sfstack convention; generic skill loaders are not
assumed to understand it.

An adapter is the execution interface. It maps a neutral capability to a concrete
operation and reconciles local details such as identifiers, authentication,
version conflicts, retry behavior, and result capture. This is where provider
knowledge belongs.

## Independence is about meaningful boundaries

Each skill packages its own protocol and output artifact schema so it can be
distributed alone, including the structure needed to validate its result. The
reference copies are generated from canonical sources and checked for drift.
That deliberate duplication trades a small amount of storage for reliable
standalone use. It does not require loading the whole library into every task.

A skill can mention an optional next capability without assuming that another
skill exists or invoking it automatically. Its result must be usable by a human,
a different agent, or a controller. Stable artifacts make those handoffs possible.

Some responsibilities contain several steps. Independent does not mean one
command per skill; it means one coherent result with a clear boundary. A defect
diagnosis may need experiments, but it should not silently take ownership of
publishing and deploying a repair.

## Neutrality does not mean lowest common denominator

A capable adapter can expose rich diagnostics, native dependency relationships,
strong concurrency primitives, and detailed test results. The skill can use
those capabilities without depending on their provider. A weaker integration
must expose its limits rather than inventing equivalent guarantees.

For example, a tracker with no conditional updates may still support local
manual work. An unattended controller needs an alternative place to enforce
ownership and conflict detection. Portability preserves this distinction instead
of claiming all integrations provide identical safety or performance.

The same principle applies to coding agents. An agent may be able to read a
skill but unable to launch a runtime, store durable evidence, or enforce a
restricted effect. The integration must qualify the capabilities it actually
provides.

## What stays project-specific

Business decisions, acceptable risks, architecture conventions, compliance
requirements, deployment policy, and the definition of done remain local.
Skills make those decisions explicit; they do not replace them with universal
preferences. Project-specific commands and services can change without rewriting
the underlying work discipline.

The optional Python reference tools maintain and exercise the library. They are
not a requirement to use the skills, and they do not constrain the target
project's language or runtime.
