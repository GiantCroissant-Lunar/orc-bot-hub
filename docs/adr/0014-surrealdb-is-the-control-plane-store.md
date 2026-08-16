# ADR-0014: SurrealDB is the control-plane store

- Status: Accepted
- Date: 2026-08-16
- Supersedes: the storage clause of [ADR-0006](0006-memory-is-scoped-untrusted-recall.md)
- Related: ADR-0011, ADR-0013

## Context

[ADR-0006](0006-memory-is-scoped-untrusted-recall.md) settled memory as scoped,
untrusted recall and split the stores: *"SQLite stores ids, digests, scope, and
provenance; Mem0 stores and searches the content."* That clause inherited a
decision from the first attempt rather than making one. That attempt had run its
journal and memory on SurrealKV, hit operational trouble, and moved to SQLite +
append-only segment files + the filesystem — three stores, each for what it is
(prior-attempt (2026-08-06)
orc-bot/docs/adr/0003-sqlite-segments-filesystem-not-surrealdb.md:10-32).

That record is unusually good: it wrote down what would reverse it. *Revisit only
when **≥2** hold: real graph-traversal needs across runs/agents/artifacts;
production-scale vector retrieval; multi-node runtime; a matured embedded SDK
(1.x with operational track record); demonstrated SQLite pain.*

Measured against 2026-08-16, **none of the five hold**. `SurrealDb.Net` is still
`1.0.0`, unchanged since 2026-07-28. There is no multi-node runtime and ADR-0011
says there will not be one. There are no runs yet, so no graph traversal has been
needed. Vector retrieval belongs to Mem0 and Qdrant under ADR-0006, so it is not
an argument for SurrealDB at all. And no SQLite exists in this attempt, so no
SQLite pain has been demonstrated.

This ADR therefore records a decision taken **against** those criteria, and the
honest thing to record is what is being bought and what is being accepted.

## Decision

**SurrealDB is the control-plane store.** It holds task, attempt, allocation, and
candidate identity; the event journal; and — for memory — the record ids,
digests, authorised scopes, and provenance that make retrieval replayable. SQLite
is not adopted.

**Mem0 keeps content and search.** The two-store split of ADR-0006 survives; only
the identity half changes hands. Losing Mem0 still costs recall, not truth.

**Persistence stays behind a port.** `OrcBot.Persistence.Surreal` is a T4
provider, and the domain depends on the port, never on SurrealDB types. The
contracts continue to model `IEventStore` / `IStoreTransaction` so that changing
this decision again is a T4 substitution rather than a rewrite. This is the
cheapest available insurance against the criteria above eventually mattering.

**The schema is defined at store-open, not on first write.** See below — this is
not a stylistic preference, it is the mitigation for a live defect.

## The defect that drove the original move is not fixed

Retested directly on **SurrealDB 3.2.3** (`3.2.3+20260721.40522d1`), 2026-08-16,
on a server started **without** `--strict`:

| Query | Result |
| --- | --- |
| `CREATE table_a SET name = "first"` | OK |
| `SELECT * FROM table_a` (written) | OK |
| `SELECT * FROM table_b` (never written) | **ERR — "The table 'table_b' does not exist"** |
| `SELECT count() FROM table_c GROUP ALL` | **ERR** |

This is the same behaviour the first attempt hit, three weeks later, on the
current engine: a read against a never-written table errors instead of returning
an empty set, so a fresh store fails its first read.

The mitigation is bounded and was verified in the same session. After
`DEFINE TABLE IF NOT EXISTS memory_record SCHEMALESS`, the same reads return `[]`
and `[{"count": 0}]`. So the defect converts into a **schema-bootstrap step at
store-open**: every table the control plane reads must be defined when the store
is opened, not created implicitly by the first write.

That step is mandatory. A table added later in code but not added to the
bootstrap is a read that fails only on a fresh clone — green on every developer
machine that has written to it once, and broken for the next person. It belongs
in one place, exercised by a test that opens a brand-new store and reads every
table.

## Consequences

- **One store instead of two.** No SQLite/Mem0 identity split to keep consistent;
  no third store for append-only bytes unless terminal capture later proves it
  needs one.
- **A startup schema step is now load-bearing**, with the fresh-store test above
  as its guard.
- **The SDK is young and the versions are skewed.** The server here is 3.2.3
  while `SurrealDb.Net` is 1.0.0; that pairing is unverified and must be proven
  before the persistence provider is relied on.
- **Graph traversal is bought before it is needed.** RFC-0001's task DAGs and
  ADR-0007's typed plan edges are the plausible future use; none exists yet, so
  this is an option purchased, not a requirement met.
- **ADR-0003's criteria are not discarded.** They were good criteria and remain
  the honest test. This decision simply does not clear them.

## What would reverse this

Symmetry with the record it supersedes — revisit when **any** hold:

- The 3.2.3 read-before-write defect reaches the domain despite the bootstrap
  step, or an equivalent defect appears in another operation.
- `SurrealDb.Net` cannot drive the running server version and the gap is not
  closed by pinning one side.
- A year passes with no graph traversal in the control plane, at which point the
  option bought here was not worth its premium.

## Alternatives considered

**Keep SQLite as ADR-0006 specified.** Rejected here, though it satisfies every
criterion in the record it would have followed. Its cost is the two-store
identity split plus, eventually, a third store for append-only terminal bytes.

**Defer and build store-agnostic.** Rejected as a false economy: the port exists
either way, and a port with no implementation is not evidence that the port is
right. One real implementation is what tests the seam.
