# ADR-0006: Memory is scoped, untrusted recall — and it ships in v0

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0002, [discussion/new-attempt-inital.md](../discussion/new-attempt-inital.md)

## Context

The previous plan put scoped memory after profiles, UI, an agent framework, and
the first provider integration. For a project whose whole point is to develop
itself, that is backwards.

Consider the first five self-development tasks. They discover things like: Godot
validation needs a particular invocation; `.godot` must not enter a source layer;
this provider signals completion this way; that source-projection approach failed
for this reason; these contracts must stay independent. Without memory, every one
of those lives only in a transcript, and the sixth worker rediscovers them.

## Decision

**Mem0 is in the bootstrap set**, behind a small `OrcBot.Memory` domain that owns
the vocabulary — `MemoryScope`, `MemoryQuery`, `MemoryRecord`, `MemoryCandidate`,
`MemoryPromotion`, `IMemoryProvider` — with `OrcBot.Memory.Mem0` as one
implementation.

**Orc Bot owns meaning; the provider owns storage and search.** Orc scope
identities (`project:orc-bot`, `agent-profile:csharp-worker`,
`work-item:source-layering`) map *into* provider metadata. Mem0's `user_id` and
`agent_id` are never treated as Orc Bot identity. This is what makes the provider
replaceable.

**Retrieved memory is untrusted context.** It can inform a worker. It cannot
settle an attempt, grant a permission, mutate source, or approve anything.

**Knowledge is symmetrical with source.** An agent saying "this fact is worth
remembering" has exactly the authority of an agent saying "this code should be
canonical": it may propose, it may not promote.

```
agent output
  ├── source claim    → SourceCandidate → review → integrated source
  └── knowledge claim → MemoryCandidate → policy → durable memory
```

**Scopes are a set, not a tree.** An invocation is authorised for several scopes
at once — installation, project, agent profile, work item, session — and
retrieval is *retrieve per scope, then rank, deduplicate, and budget*. There is
no "current memory namespace", because one agent participates across projects and
authorities.

**Retrieval is reproducible and inspectable.** Every attempt receipt records the
authorised scopes, the query digest, the retrieved memory ids and digests, the
provider identity, and the resulting context-package digest. SQLite stores
ids, digests, scope, and provenance; Mem0 stores and searches the content. Memory
is also addressable from outside — `orc memory search|inspect|candidates|approve|reject`
and the MCP equivalents — so an agent can *ask* what previous attempts learned,
rather than Orc Bot silently stuffing recall into every prompt.

**Refinement is a candidate too.** Prime Agent's `/refine` loop, which can revise
prompts, memory, skills, and subagent specs with rationale and history, is a good
idea with the wrong authority model. Adopted as `RefinementCandidate`: same
proposed → reviewed → accepted → promoted path as source, never direct mutation
of shared state.

## Consequences

- The first dogfood loop is worth running for its own sake: run 1 discovers a
  fact and proposes it, a human promotes it, run 2 retrieves it and the receipt
  proves it was in context. That demonstrates cross-run learning, not just
  orchestration.
- Attempts carry more metadata. Receipts get bigger; they are also the thing that
  makes a six-week-old failure explicable.
- Two stores to keep consistent. Mitigated by the split: SQLite holds identity and
  provenance, Mem0 holds text. Losing Mem0 costs recall, not truth.

## Alternatives considered

**Adopt Microsoft Agent Framework as the memory and context architecture.**
Rejected for v0, not rejected outright. Orc Bot assembles its own
`ContextPackage` behind `IMemoryProvider` first; if Agent Framework's context
providers, middleware, and session handling prove concretely better, they arrive
*behind* that seam. The framework must not become the architectural definition of
memory.

**Defer memory until after the first provider integration.** Rejected — see
Context. The first five self-development tasks are exactly the ones whose lessons
we cannot afford to lose.
