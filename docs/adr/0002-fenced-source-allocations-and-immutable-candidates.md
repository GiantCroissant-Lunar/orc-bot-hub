# ADR-0002: Fenced source allocations and immutable candidates

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0004, ADR-0007, [discussion/prime-agent-vs-orc-bot.md](../discussion/prime-agent-vs-orc-bot.md)

## Context

This is the reason Orc Bot exists. Most agent runtimes tell you to run them in
the directory you want changed, and to use a clean worktree if you care. Prime
Agent's own repository rules describe several agents working in one worktree,
kept apart by conventions like "only stage files you changed". That works until
two agents touch the same file, or until one of them is a game engine that
regenerates a hundred megabytes of derived state on import.

Game development makes this acute: Unity's `Library/`, Godot's `.godot/`, and
Unreal's derived data are expensive, per-checkout, and hostile to concurrency.

## Decision

**A worker never operates on a shared checkout.** Every attempt receives a
`SourceWorkspaceAllocation`: a fenced, privately-owned materialisation of a
specific source generation, allocated by Orc Bot and released by Orc Bot.

**A worker's output is a candidate, not a commit.** When an attempt reaches
semantic completion, its delta is frozen into a digest-addressed
`ComponentCandidate`. A candidate is immutable. It can be inspected, diffed,
composed into another attempt's workspace as a dependency layer, accepted, or
rejected — never edited.

Four facts are kept separate and must never be collapsed into one another:

```
agent completion  ≠  candidate publication  ≠  validation  ≠  acceptance/integration
```

An agent finishing its turn produces the first. Only Orc Bot produces the rest,
and only a human or an explicit policy produces the last.

**Failure does not mutate; it supersedes.** When a review or gate rejects a
candidate, the old candidate is not reopened. A new attempt is created with the
previous candidate and the review evidence as explicit inputs. This is why the
durable execution graph stays acyclic (ADR-0007): a feedback edge produces a new
plan revision, not a loop back into a mutable world.

**Reviewing a candidate is not composing it.** A reviewer needs to read a
candidate; it does not need that candidate materialised into its own writable
workspace. Conflating the two is what makes `DependsOn` mean five things at once.

## Consequences

- Parallel agents become safe by construction rather than by etiquette.
- The whole history of a task is inspectable: every attempt has a receipt naming
  its source generation, its allocation, its candidate, and its evidence.
- Restart recovery is tractable, because the durable objects are immutable and
  content-addressed.
- Allocation costs disk and time. Materialisation strategy (copy, worktree,
  overlay, layered) is an implementation choice behind `ISourceAuthority`, and the
  first implementation may be the dumb one.
- Every capability that wants to "just edit the repo" has to be redesigned. That
  friction is the feature.

## Alternatives considered

**Git worktrees as the model.** Rejected as the *model*, kept as one possible
*implementation*. A worktree is environmental Git context; it carries no
ownership, no fence, no generation identity, and no release semantics. Orc Bot
needs those regardless of how the bytes get on disk. It also fails immediately
for engine derived state, which is not in Git at all.

**Let agents commit directly to branches.** Rejected: a commit is mutable
history with an author's authority attached, and it drags integration policy into
the worker. A candidate is a proposal with no authority whatsoever.
