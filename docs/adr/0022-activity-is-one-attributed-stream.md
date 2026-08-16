# ADR-0022: Activity is one attributed stream, and its UI splits by feature then by load tier

- Status: Accepted
- Date: 2026-08-17
- Related: ADR-0003, ADR-0013, ADR-0016, ADR-0017, ADR-0021
- Informed by: `prior-attempt (2026-08-06) orc-bot/docs/handovers/2026-08-06-activity-timeline-control.md`,
  `prior-attempt (2026-06-07) fantasim-app-godot/vault/architecture/activity-log-ui.md`,
  and `docs/discussion/mps-ui.md` (raw input, not a decision)

## Context

Orc Bot needs to show what is happening — by the system, by an agent, and by a
human — as a visual surface rather than a log tail. Three implementations of this
already exist across previous attempts, and they disagree about almost nothing
important, so this records what they converged on rather than choosing between
them.

The open question was where A2UI and AG-UI sit. They are not alternatives to each
other and neither is a UI toolkit.

## Decision

**Activity is one attributed stream.** Every event carries an actor — **system**,
**agent**, or **user** — a sequence number, a kind, and a timestamp.

**An agent operating Orc Bot is recorded as a `user` activity, with its source.**
Acting-as-the-user is still an act. Attributing it to the system would make the
stream unable to answer "who did this", which is the only question it exists to
answer.

**Sequence order is delivery order.** Publication is serialised and subscribers
are exception-isolated, so one bad subscriber cannot reorder or truncate the
stream for the others. Attribution is scoped by an explicit attach/detach, so
concurrent runs never cross-attribute.

**The timeline is a pure function of an event prefix.** Rebuilding it as it stood
after event *n* is a deterministic projection, not a replay side effect. Scrubbing
is therefore not a separate mechanism with its own bugs.

**One pipeline.** Activity is a view over the streams that already exist — the
machine channel (ADR-0021) and the control endpoint — never a second log.

**The UI splits by feature first, then by load tier** (ADR-0013):

| Assembly | Tier | Owns |
| --- | --- | --- |
| `*.Activity.Contracts` | T1, shared | event and row vocabulary, the view-model interface |
| `*.Activity.Godot` | resident | the `Control` view and panel host. No filtering, no domain logic |
| `*.Activity.Ui` | **collectible bundle** | presenter and view-model logic, hot-reloadable |

**A2UI is the allowlisted renderer for agent-authored activity fragments.**
Rendering something an agent generated is the one place UI is not authored by us,
so it is allowlisted rather than trusted.

**AG-UI is transport and belongs beside ACP and A2A, not beside a UI language.**
It translates external run, message, tool, and state streams into Orc Bot's T1
contracts and **never becomes authoritative state** — the same standing as terminal
output (ADR-0003) and retrieved memory (ADR-0006): it informs, it settles nothing.

Everything else — graph, timeline, terminal, inspector, ordinary panels — stays a
native Godot surface. Generative UI is a lane, not a replacement.

## Two traps, both already paid for

- **A bundle scene must never attach a bundle-owned C# script.** Godot loads that
  script type through the resident app assembly path rather than the collectible
  context, so the bundle appears to work while its isolation is silently gone.
  Bundle scenes are scriptless structure, or they bind *resident* scripts.
- **Generated Godot views derive from `Control`, so they are resident.** That is
  what forces the three-way split above: keeping view classes lightweight and
  logic in the collectible assembly is what makes any of it hot-reloadable.

## Consequences

- **The activity feature is the first real exercise of the bundle mechanism.** Up
  to now bundles were proven with a provider that had no UI. A presenter in a
  collectible context, behind a resident view, is the shape ADR-0013 was adopted
  for.
- **Attribution has to be established at the source.** A stream that infers the
  actor after the fact will get agent-as-user wrong, because by then the only
  evidence is which code path published.
- **The A2UI allowlist is now load-bearing** and needs its own decision before
  agent-authored fragments render. This ADR places the lane; it does not settle
  what is admissible inside it.

## What would reverse this

- Attribution proves unanswerable at the source for some real event class, making
  the three-actor model a fiction maintained by guesswork.
- AG-UI acquires state semantics Orc Bot actually needs to trust, at which point
  "never authoritative" is the wrong rule and the boundary moves rather than bends.

## Alternatives considered

**Render activity from the terminal viewport.** Rejected for the same reason
ADR-0021 rejects it for protocol bytes: it makes rendering behaviour part of the
contract, and it cannot attribute anything.

**One monolithic UI assembly.** Rejected. It forces every UI change to be a
resident change, which is precisely the hot-reload the tier split exists to
provide.

**Treat AG-UI as the UI description language.** Rejected on its own
documentation, which states it is a runtime connection that can *carry* a
generative-UI specification such as A2UI, not one itself.
