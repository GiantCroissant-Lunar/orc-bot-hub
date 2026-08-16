# ADR-0004: Derived state is never tracked, and expensive tools get authority slots

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0002

## Context

Orc Bot materialises fenced allocations out of a repository. Anything tracked in
that repository is reproduced into every allocation. That turns a tidiness
question into a correctness one: a committed `.godot/` directory is copied into
every worker's workspace, where it is simultaneously stale, huge, and mutable.

The second attempt hit the concrete version of this — source allocation had to
reject any repository containing tracked `.godot` state, because otherwise the
allocation was poisoned before the worker started.

Separately, some derived state is *too expensive to fence*. A Unity `Library/` or
a Godot `.godot/` can take minutes to regenerate. Giving every attempt its own
copy is correct and unaffordable.

## Decision

**Nothing derived is tracked.** `.godot/`, `Library/`, `bin/`, `obj/`,
`target/`, and `build/_artifacts/` are ignored, and
`build/scripts/Assert-NoTrackedDerivedState.ps1` fails the commit and `task
verify` if any of them are staged or tracked. The check runs against
`git ls-files`, so it catches state that was committed before the ignore rule
existed.

**Expensive derived state is modelled as a `ToolAuthoritySlot`.** A slot is a
persistent, exclusively-leased instance of a tool's derived state — one Godot
`.godot`, one Unity `Library` — that an attempt *borrows* rather than owns.
Slots are:

- **leased**, not allocated: an attempt holds one for the duration of a
  validation step and returns it;
- **rebuildable**: losing one is slow, never fatal;
- **never a source of truth**: nothing in a slot is an input to a candidate.

**Validation is an authority, not a step in the agent's loop.** A validation
receipt is produced by Orc Bot holding a slot, not by the worker claiming its
change works. The previous attempt's mistake was not having receipts — it had
them — but hard-coding *what* they validated into the executable. Validation
targets are configuration: project path, window title, export preset, and
expected artifacts are data, so a second project type needs no rebuild.

## Consequences

- A fresh clone is small and every allocation is clean.
- Godot and Unity work can be orchestrated at all, which was the original reason
  for the project.
- Slot contention becomes a real scheduling concern: with one Godot slot,
  validation serialises even when authoring parallelises. That is visible and
  measurable rather than mysterious, and it is the right place to spend money
  later (more slots) rather than complexity now.
- `task verify` will fail on a repository someone "fixed" by committing an
  import cache. That is intended.

## Alternatives considered

**Give every attempt its own engine derived state.** Rejected on cost. It is the
correct model and remains the fallback for cheap tools; for Unity it is minutes
per attempt.

**Share one checkout and serialise all engine work with a mutex.** Rejected:
that is the shared-worktree model with extra steps, and it loses the fence that
makes candidates meaningful.
