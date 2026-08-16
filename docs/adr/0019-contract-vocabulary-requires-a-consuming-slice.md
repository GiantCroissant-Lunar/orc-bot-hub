# ADR-0019: Contract vocabulary requires a consuming slice

- Status: Proposed
- Date: 2026-08-16
- Related: ADR-0001, ADR-0002, ADR-0006, ADR-0013

## Context

The implementation repository's rules carry an invariant against speculative
code: *"No stubs, demos, fallbacks, or placeholder projects. If a thing is not
needed yet, it is not created."* Its worked example is a reference plugin that
exists to prove the plugin host works — the kind of thing that never gets
deleted and quietly becomes load-bearing.

That example is about **demos**, and a contracts assembly does not read like
one. Declaring an interface before anything implements it is not a placeholder;
it is arguably the entire purpose of a contract. ADR-0001 already lists the
application surface as operations (`SubmitTask`, `GetCandidate`,
`AcceptCandidate`, …) and ADR-0002 defines candidates and their dispositions.
Transcribing those into C# ahead of an implementation looks like diligence.

So the invariant, read reasonably, exempts contracts. That reading was taken,
and it produced a defect that sat in the tree looking authoritative until
2026-08-16.

## The evidence

The orchestration contracts assembly was found carrying a **second**
`ITerminalProvider`, `TerminalBinding`, `IMemoryProvider`, `MemoryQuery` and
`MemoryRecord`, in a namespace nothing outside the file itself referenced. Both
sets compiled. Both looked canonical.

The dangerous one is the memory port. The unexercised declaration was:

```csharp
public interface IMemoryProvider
{
    string ProviderId { get; }
    Task<IReadOnlyList<MemoryRecord>> SearchAsync(MemoryQuery query, ...);
}
```

A bare list. **It cannot express "the provider could not be asked."** An
unreachable Mem0 sidecar and a project that has learned nothing return the same
value.

That is precisely the collapse ADR-0006 exists to prevent, and the survey record
of the previous attempt names it as S3: the earlier Mem0 adapter *"reported
absent credentials, unreachable service, and timeouts as unavailable rather than
fabricating an empty successful capability."* The port that was written later,
against a real sidecar, carries `ProbeAsync` returning a
`MemoryProviderAvailability` and `SearchScopeAsync` returning a
`MemoryScopeResult` — because writing it against something real forced the
question.

The declaration survived **because** it was unused. Nothing exercised it, so
nothing ever revealed that it could not express the distinction its own design
turns on. Had a second implementer reached for it — the obvious thing to do,
since it sat in the orchestration contracts under an authoritative name — they
would have built the exact bug the memory ADR was written to prevent.

The same file's `IOrcControlPlane` shows a milder version. It is not merely
unimplemented; its own doc comment states that no adapter "may reach past it to
a workspace, a database, or a process", while the only adapter that exists —
the CLI — constructs a store, a memory provider, and a terminal provider
directly. The interface does not describe the system. It describes an intention.

**This is the fifth instance of one shape in a single day.** A stale IDE
analyser reporting zero problems, an incremental build reporting zero warnings,
a flat-rate agent reporting zero cost, an unavailable memory provider returning
an empty result, and now unexercised vocabulary reading as settled design. In
every case an absent check was indistinguishable from a passed one.

## Decision

**Contract vocabulary requires a consuming slice.** A type may exist in a
contracts assembly when either an implementation exists in the tree, or a named
and accepted RFC consumes it in the next slice of work. Vocabulary with neither
is deleted, and re-derived from its ADR when a slice needs it.

Three clarifications, each load-bearing:

- **The ADR is the durable record; the C# is not.** ADR-0001 lists the surface
  operations, ADR-0002 defines candidate dispositions. A C# transcription adds
  no design and is regenerated in minutes. The hub is public and outlives the
  implementation tree by construction — which means deleting a transcription
  loses nothing, and keeping a drifting one costs the thing the hub is for.
- **"It is only a record" is not an exemption.** A `TaskState` with six states
  and a `CandidateDisposition` with three are *guesses* until a lifecycle
  enforces them. They carry the same false authority as an interface, and they
  are cheaper to get wrong quietly.
- **A type named in an accepted RFC is needed, not speculative.** RFC-0006 cites
  `AgentProviderCapabilities.SupportsJoinableSession` by name and builds its
  semantics plane on it. That is a consuming slice, and the type stays.

## Consequences

- **Contracts lag design by one slice, deliberately.** The contracts assembly
  stops being a map of the intended system and becomes a record of what is built
  plus exactly one step ahead.
- **Reading the tree no longer tells you the plan.** This is a real loss and it
  is accepted, because the plan was never reliably there — the drifted memory
  port is what reading the tree actually told you. The ADRs and RFCs carry the
  plan, they are reviewed as documents, and they survive a fourth attempt.
- **The check is mechanical.** "Does anything outside this namespace reference
  it" is one search, and it is the check that was never run.
- **An RFC that names a type creates an obligation.** Naming a contract type in
  an accepted RFC is what licenses its existence, so an RFC that is abandoned
  leaves vocabulary to collect.

## What would reverse this

- A slice is blocked because vocabulary was deleted and re-deriving it from the
  ADR proved lossy — which would mean the C# carried design the ADR did not, and
  the ADR should be fixed rather than the rule.
- Contracts churn becomes the dominant cost of adding a slice, indicating the
  one-slice lookahead is too short.

## Alternatives considered

**Keep the vocabulary, add a test that every contract type has an
implementation.** Rejected: it fails from the moment it is written and stays red
for months, which makes it a disabled test, which is another absent check that
looks like a passed one.

**Keep it and rely on review.** Rejected on evidence. The duplicate ports
survived every review between the first slice and 2026-08-16, because a
duplicate in a namespace nobody imports is invisible in a diff.

**Delete everything currently unimplemented, including the agent-provider
pair.** Rejected. Those are cited by name in an accepted RFC and are consumed by
the next slice, so deleting them manufactures exactly the churn this rule exists
to avoid.
