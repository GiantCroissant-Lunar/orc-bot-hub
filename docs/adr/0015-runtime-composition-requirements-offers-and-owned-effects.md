# ADR-0015: Runtime contributions declare requirements, offer capabilities, and own their effects

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0002, ADR-0003, ADR-0013
- Informed by: [discussion/cordis-osgi.md](../discussion/cordis-osgi.md)

## Context

Orc Bot has two control mechanisms and is missing a third.

**Durable orchestration** answers *what should happen* — tasks, attempts,
candidates, decisions, receipts. **Resource transactions** answer *who owns
what* — fenced allocations, immutable candidates, validation slots (ADR-0002).

Neither answers *given the environment right now, which runtime contributions
may legitimately be active?* Without that, availability is expressed as a
growing pile of ad-hoc checks — is Mem0 up, is the provider binary present, did
this surface load, is Zellij installed — each written at its call site and none
of them observable together.

Two prior bodies of work address this directly. **OSGi Declarative Services** has
done reactive dependency satisfaction for two decades: a component declares
references, is activated only when its mandatory references are satisfied, is
deactivated when one disappears, and is reactivated when it returns. **Cordis**
(4.0.0-rc.8, MIT, API explicitly unstable) reaches the same operational place
from effect/coeffect theory, and adds the part OSGi does not emphasise: an
explicit effect tree that is unwound in reverse on teardown.

The useful conclusion is not to adopt either.

## Decision

**Introduce a composition plane** below durable authority and above dynamically
composed adapters, context providers, and surfaces. It reconciles a *desired*
composition against an *observed* one. It is not a workflow engine and it does
not own lifecycle; it is told what should be active and reports what is.

**Every dynamic contribution declares four things**: what it requires, what it
offers, what it changes, and how those changes are released. A contribution that
cannot state all four does not get to be dynamic.

**Requirements are not permissions.** A component declaring `workspace.write`
must never thereby obtain `workspace.write`. A requirement may *select* an
existing grant; it may never manufacture one. Orc Bot is deliberately stricter
than Cordis here and stays so:

```
requirement ≠ permission
dependency  ≠ authority
service     ≠ capability grant
```

**Reversibility has four classes, not two.** Cordis's temporal composability
assumes removal fully reverts a component's effects. That holds for an in-process
plugin runtime and does not hold here — an agent orchestrator launches
processes, mutates engine state, and publishes durable facts.

| Class | Meaning | Example |
| --- | --- | --- |
| `EphemeralReversible` | Exact inverse exists and is provable | subscription, timer, UI binding |
| `OwnedCleanup` | Cleanup expected, needs external evidence | process tree, terminal session |
| `Compensatable` | No inverse; a compensating operation exists | some slot mutations |
| `DurableIrreversible` | Historical fact, never composition-managed | candidate publication, a human decision |

**Deactivation returns a typed disposition**, not a completed `DisposeAsync`:
`Reverted`, `Released`, `ResidualState`, `RestartRequired`, `Quarantined`. "The
dispose call returned" is not evidence that anything was released — which is the
same rule ADR-0003 already applies to terminal output.

**Every transition carries a monotonic generation, checked after every
asynchronous boundary.** Activation computes against generation *N*; before
publishing, it compares *N* against the current generation and discards itself if
they differ. Never conclude "nothing changed" by comparing computed dependency
state for equality — Cordis has an open issue where configuration goes A→B→A
during an async load and the stale activation sees A again and commits. Orc Bot
already thinks in fences; this is where that pays.

**Neither Cordis nor OSGi becomes a dependency.** Cordis is an RC solving a
Node/TypeScript problem — its HMR manipulates Node's ESM/CJS caches with
version-specific code for Node 22–24. Copy the state machine, not the source.

**The composition graph is a third graph**, and must not be merged with the other
two:

| Graph | Question |
| --- | --- |
| Work | What must be done, in what causal order? |
| Resource | What owns what? |
| Composition | What may be active right now? |

## Consequences

- Availability becomes an observable fact rather than scattered conditionals. A
  provider whose binary disappears withdraws its offers, and everything depending
  on them is re-evaluated deterministically.
- **A live attempt is not torn down because a composition dependency vanished.**
  The composition plane withdraws offers; it does not kill running work. Whatever
  owns attempt lifecycle reconciles the real external resource and records the
  honest durable state. This is the single most important boundary in this ADR,
  and getting it backwards would let a Mem0 restart kill an agent mid-run.
- An operator surface falls out: for each active component, its requirements with
  satisfaction state, its offers, its effects, and its blocked reason. That is far
  more useful than "plugin loaded".
- Cordis's open lifecycle bugs become our adversarial fixtures rather than a
  reason to avoid the model: A→B→A during async activation, child-scope teardown
  over-cleaning parent registrations, provider removal during dependent startup,
  partial activation failure, double disposal, cancellation mid-load, and
  incomplete external cleanup that must yield `Quarantined` rather than success.

## What this ADR does not decide

The discussion this came from assumes an architecture with Akka.NET supervision
and Arch ECS projections. **Neither exists in this attempt**, and ADR-0000 makes
the prior attempts reference-only. This ADR therefore names "durable authority"
and "lifecycle owner" as roles without binding them to those technologies. When
something fills those roles, it inherits the boundary above.

Dynamic module loading itself remains out of the accepted slice (RFC-0001). This
ADR describes the model a later slice implements; it does not schedule it.

## Alternatives considered

**Adopt Cordis as the runtime.** Rejected. API explicitly unstable, no releases,
open lifecycle issues, and it solves a Node module-cache problem while Orc Bot's
concerns are durable facts, external processes, containment, and Godot object
lifetime. More architectural mismatch than benefit.

**Adopt an OSGi-style container wholesale.** Rejected for v0 scope, not on
merit — its requirements/capabilities and cardinality model is more mature than
what is proposed here, and is the obvious place to look when this one proves
insufficient.

**Do nothing until dynamic loading is scheduled.** Rejected because the
vocabulary is needed before the mechanism: the four declarations and the four
reversibility classes are what a later ALC implementation is tested *against*.
