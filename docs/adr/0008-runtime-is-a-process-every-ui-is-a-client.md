# ADR-0008: The runtime is its own process; every UI is a client

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0001, ADR-0003, [discussion/prime-agent-vs-orc-bot.md](../discussion/prime-agent-vs-orc-bot.md)

## Context

ADR-0001 says the CLI comes first. That immediately forces a question: when
`orc task submit` returns in 200ms and the worker runs for twenty minutes, what
is watching the machine channel?

If the answer is "the CLI process", then closing the shell kills the attempt,
`orc task get` from a second shell sees nothing live, and terminal attachment has
nothing to attach to. If the answer is "the Godot host", then the UI becomes
durable authority and everything ADR-0001 says is undone the moment someone wants
a headless run.

Prime Agent has already worked through this and split
client → connection → daemon supervisor → session worker. Its daemon carries
reconnect and reattach, worker adoption after the supervisor is replaced,
snapshot-based recovery, an idempotent mutation journal, explicitly *uncertain*
outcomes rather than blind replay, and per-attachment backpressure. Its best
single idea is the cursor: `{ generation, sequence }` rather than a naked
sequence, so a client that reconnects to a new worker generation cannot compare
its old position against the new stream — it either catches up or is handed a
coherent replacement snapshot.

## Decision

**`orc-runtime` is a long-lived local process.** It owns lifecycle supervision,
SQLite, work topology, source authority, candidate authority, tool-authority
slots, and the provider gateway.

**Every UI is a client over a versioned local protocol.** The `orc` CLI is a thin
client. The Godot host is another client. Neither holds durable state, and the
runtime does not know which one is attached.

**Event cursors are `{ generation, sequence }`.** A generation change invalidates
sequence comparison by construction.

**Recovery is snapshot-plus-journal.** Snapshots are the baseline; mutations are
journaled and idempotent; an outcome that cannot be determined is recorded as
*uncertain* and surfaced, never replayed on the assumption it did not happen.

**A supervision framework stays inside the runtime.** If Akka.NET is adopted, it
supervises the domain *within* the process. The daemon is the process and client
boundary around it, not a replacement for it.

**Cognitive delegation and resource-owning work are different.** A provider's own
subagents (Prime's `rlm()`, Claude's Task tool) stay internal and invisible to Orc
Bot. They cross the boundary only when delegation needs an independently governed
resource — another repository, its own candidate, a tool slot, a different
loadout, different permissions. At that point the provider raises a
`work.spawn.request` and Orc Bot decides whether it becomes a work item. An agent
never owns work topology; Prime's own move toward a supervisor-owned spawn ledger
is the same lesson arriving from the other direction.

**Provider-specific metadata is namespaced, never smuggled into the protocol.**
Following Prime's use of a reverse-domain `_meta` namespace, Orc Bot context on
an ACP message goes under `_meta["dev.orc-bot"]` so standard ACP clients ignore
it and ACP stays ACP.

## Consequences

- Closing a terminal does not kill work; that is the entire point.
- Two processes to start, and an IPC boundary to version. The protocol is local
  and internal for now, so it may change freely as long as both sides ship
  together — the version field exists so that it can stop changing later.
- Godot never becomes durable authority, which is what keeps headless runs and
  CI-style automation possible.
- A client crash is uneventful: reconnect, present the cursor, catch up or take a
  snapshot.

## Alternatives considered

**In-process CLI over shared SQLite, no daemon.** Rejected: nothing supervises
the machine channel between CLI invocations, so a worker's completion event
arrives with no listener. It also makes `orc terminal attach` meaningless.

**Defer the daemon until the Godot UI exists.** Rejected: deferring it means the
first execution path is written to run inside whatever process happens to call it,
and moving it afterwards is the expensive kind of refactor. Prime Agent is the
evidence that this boundary is worth having early.
