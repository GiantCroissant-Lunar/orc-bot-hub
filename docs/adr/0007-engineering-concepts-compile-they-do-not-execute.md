# ADR-0007: Engineering concepts compile work; they do not execute it

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0002, [discussion/different-engineering.md](../discussion/different-engineering.md)

## Context

There is a steady supply of "X Engineering" ideas — prompt, context, loop, graph,
verification, cost, knowledge-graph — plus planners (GOAP, HTN) and foreign
workflow dialects (n8n, ComfyUI). Each arrives with its own runtime, and adopting
each one natively would give Orc Bot five orchestrators.

Graph Engineering is the immediate case. It is a good fit, but the popular
framing conflates two unrelated graphs: an **execution graph** (fan-out, fan-in,
conditional routing, feedback) and a **knowledge graph** (`supersedes`,
`depends_on`, `caused_by`, with provenance and time). Those must not be one type.

The previous attempt also let a single `IReadOnlyList<string> DependsOn` mean at
least five different things: B cannot start until A succeeds; B's workspace should
contain A's candidate; B needs A's evidence; B needs A's artifact; B should get
A's review as context.

## Decision

**One sentence governs this:** *engineering concepts describe, analyse, and
compile work; Orc Bot's existing authorities execute and prove it.*

```
Graph Engineering ─┐
Loop Engineering  ─┤
Markdown workflow ─┼──► ExecutionPlan ──► supervision ──► agents, allocations,
GOAP / HTN        ─┤                                      candidates, validation,
imported dialects ─┘                                      decisions, evidence
```

A concept pack may not start a process, allocate a workspace, approve a
candidate, or mutate lifecycle state. It emits a plan.

**Edges become first-class and typed.** `DependsOn` is replaced by
`PlanEdge { EdgeId, From, To, Kind, Condition, PayloadBinding }` over a
deliberately small vocabulary:

```
requires_success   requires_terminal   routes_on_success   routes_on_failure
consumes_artifact  consumes_evidence   composes_candidate  requires_decision
```

This is what lets "review this candidate" differ from "build on top of this
candidate" — the distinction ADR-0002 depends on.

**Nodes reference capabilities, not a closed enum.** `WorkflowStepKind` stops
growing. A node is
`PlanNode { NodeId, Capability, Inputs, ResourceClaims, ExecutionPolicy, AgentProfile? }`,
and a security reviewer differs from an author by profile, loadout, and context —
not because the scheduler knows what "security reviewer" means.

**The durable execution graph stays acyclic.** A failure edge produces a new plan
revision with the prior candidate and review evidence as inputs (ADR-0002), not a
cycle back into a mutable world.

**The knowledge graph is a separate, rebuildable projection.** Derived from
SQLite, Git, and the ADRs; every relation carries `valid_from`, `valid_until`,
`observed_at`, `source_ref`, `source_digest`, and `confidence`. It is never
workflow authority, and Mem0 may reference its nodes but may not invent them. If
SurrealDB returns, this is where it belongs — as a query projection, not a
control plane. (Note for whoever builds it: a SurrealDB `SELECT` against a table
that has never been written is an *error*, not an empty set, so a fresh clone
fails its first read unless the schema is seeded.)

**Concepts contribute facets, not one god-interface.** A pack declares which of
topology / context / analysis it contributes to. Prompt Engineering is not an
execution graph and should not have to pretend to be one.

**Nothing here is v0 scope.** This ADR exists so that v0 does not foreclose it:
the first `ExecutionPlan` may have exactly one node kind, as long as the edge is
already a record and the node already references a capability.

## Consequences

- New engineering ideas arrive as compilers. The kernel stops growing.
- Cost and latency can be attributed per node and per plan revision, which makes
  "cost per successful completion" measurable — the metric worth optimising.
- A compilation step exists between what an author writes and what runs. Debugging
  gains a layer, and gains a compiled artifact to inspect.
- Reported speedups from other people's graph frameworks are not requirements.
  Orc Bot measures its own workloads.

## Alternatives considered

**Adopt an existing graph runtime (LangGraph, OpenClaw) as the executor.**
Rejected: none of them model source authority, fences, candidates, tool slots, or
acceptance, and those are the parts Orc Bot exists for.

**Persist cyclic execution graphs.** Rejected: it trades immutable, restartable
attempts for one mutable world edited until something says "done", which is the
model this project is trying to leave.
