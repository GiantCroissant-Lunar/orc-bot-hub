# ADR-0009: Seed engine caches per allocation; do not share them

- Status: Accepted
- Date: 2026-08-16
- Amends: ADR-0004
- Evidence: [surveys/S1](../surveys/S1-source-authority-and-candidates.md), [surveys/S4](../surveys/S4-godot-validation-and-export.md)

## Context

ADR-0004 said expensive engine derived state should become a `ToolAuthoritySlot`
— a persistent instance that attempts *lease* rather than own — on the reasoning
that per-attempt copies were correct but unaffordable.

The survey wave says the affordability premise is wrong for Godot, and that the
shared version is not merely slower to reason about but actively unsound.

A previous attempt tested it directly. Two workspaces were junctioned at one
`.godot` cache with different content at the same asset paths. Both imports
exited 0. The cache stayed 298.3 MB and looked healthy. But cache entries are
keyed by *path*, not content, so one entry existed for a path the two workspaces
disagreed about, and its `source_md5` flipped between their bytes on every
import. Between imports, anything reading that cache received the other
workspace's asset — with a zero exit code and no diagnostic anywhere.

That experiment's own conclusion was three words: **seed, do not share**.

The same work found the cost side is not what ADR-0004 assumed: a private Godot
cache can be hardlink-seeded from a warm master in roughly 5.8 seconds, writing
no new bytes.

## Decision

**For engine caches that can be seeded, seed one per allocation.** Godot's
`.godot` is provisioned by hardlink-seeding from a warm master into the
allocation, and belongs to that allocation for its lifetime.

**A shared mutable engine cache is not a sharing strategy and is not permitted.**
Not behind a lock, not "just for validation", not "only for reads". Failure is
silent, exit code 0, and produces the other workspace's asset.

**`ToolAuthoritySlot` narrows rather than disappears.** It remains the model for
derived state that genuinely cannot be seeded cheaply — Unity's `Library/` is the
candidate, and it has not been measured. A slot is now the *exception* requiring
evidence, not the default.

**Seeding is measured, not assumed.** A tool qualifies for seeding when someone
has timed it. Until then it gets a slot and a note saying nobody has checked.

## Consequences

- Godot validation parallelises: attempts stop queueing behind one cache, which
  was the main cost ADR-0004 accepted.
- Warm-master maintenance becomes real work — the master must be kept current,
  and a stale master seeds a stale cache into every allocation.
- Hardlink seeding needs the allocation and the master on the same volume. On a
  machine where they are not, provisioning must fall back to a copy and say so
  rather than silently degrading to a junction.
- ADR-0004's other decisions are untouched: derived state is still never tracked,
  and validation is still an authority producing receipts, not a step in the
  agent's loop.

## Alternatives considered

**Keep the shared slot and lock around it.** Rejected on the evidence. A lock
serialises access but does not fix path-keyed entries: the cache still holds one
entry for a path two workspaces disagree about, so the corruption survives the
lock and reappears the moment the second workspace imports.

**Copy the cache per allocation instead of hardlinking.** Kept as the fallback,
not the default. It is correct and roughly 300 MB per attempt; hardlinking gets
the same isolation for no new bytes when the volumes permit it.
