# ADR-0010: Orca is scaffolding, and is retired plane by plane

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0001, ADR-0002, ADR-0003, ADR-0008, RFC-0001

## Context

Orc Bot cannot yet orchestrate anything, so every piece of parallel work on Orc
Bot is currently dispatched through Orca. That is the right call — the survey
wave that produced `docs/surveys/` was five providers running concurrently, and
none of it would have happened otherwise.

But it creates an awkward shape: **Orca already implements, in production, most
of what Orc Bot is being built to do.**

| Orca | Orc Bot equivalent |
| --- | --- |
| worktree | source workspace allocation (ADR-0002) |
| terminal handle, `terminal read/send/wait` | terminal binding, presentation plane (ADR-0003) |
| Run / Task / Dispatch | task / attempt / operation (ADR-0001) |
| `worker_done`, `escalation`, `question` | typed semantic completion (ADR-0003) |
| coordinator mailbox, `check --wait` | event stream with `{generation, sequence}` (ADR-0008) |
| `worker-start` launch preferences | agent profile and loadout |
| capability revocation on completion | attempt fence release |

That is not a dependency to wrap. It is a working reference implementation of
the same control plane, running on the same machine, against the same providers.

The risk if we ignore this: Orc Bot grows a permanent Orca adapter, "dogfooding"
quietly means "Orca does the hard part", and the day Orca changes its CLI we
discover how much of our orchestration was never ours. The previous attempts
already show the failure mode — a system that looks complete while the load is
carried somewhere else.

## Decision

**Orca is scaffolding with an explicit demolition order.** It is not abstracted
behind a port, not wrapped in an `IOrchestrator`, and not planned for
indefinitely. Each Orc Bot plane replaces the corresponding Orca function, and
the replacement is only accepted when Orc Bot has done that job for real work.

**Retirement order, following RFC-0001:**

| Phase | Orc Bot capability | What stops using Orca |
| --- | --- | --- |
| 1 | W3 source authority | allocation. Workers get an Orc Bot allocation; Orca worktrees are no longer created for Orc Bot's own work. |
| 2 | W4 + W5 containment and machine channel | launch and completion. `worker_done` stops being the completion signal; the typed channel is. |
| 3 | W6 terminal binding | attach. `orc terminal attach` replaces `orca terminal read/send`. |
| 4 | W7 + W8 + W9 application, daemon, CLI | dispatch. `orc task submit` replaces `orca orchestration worker-start`. |
| 5 | — | Orca is removed from `AGENTS.md` and the `orca-dispatch` skill is deleted. |

**A phase is done when Orc Bot has run a real dispatch without Orca doing that
job — not when the code exists.** The proof is a task in this repository, done by
a worker, through the new path.

**Until its phase lands, Orca is used directly and idiomatically.** No shim, no
adapter layer, no "just in case" abstraction. Wrapping it now would cost design
effort on an interface we intend to delete, and would hide exactly the
comparison that makes the phase-out verifiable.

**While both exist, they are a differential test.** The same dispatch can be run
through Orca and through Orc Bot and the results compared. That is a better
correctness signal than any test we could write for the new path alone, and it is
only available during the transition — so use it while it lasts.

**Orca's operational knowledge outlives Orca.** Everything learned from driving
it — approval flags per CLI, the worktree-escape hazard, "a blocked agent looks
like a busy one", capability revocation on completion — belongs in
`.agent/adapters/runners/` as data, not in the Orca skill as prose. Those facts
are about the provider CLIs, not about Orca, and Orc Bot will need every one of
them.

## Consequences

- "Dogfooding" gets a precise definition: the fraction of Orc Bot's own
  development that runs through Orc Bot rather than Orca. It starts near zero
  and is expected to be reported honestly.
- Phase 4 is the real milestone. Phases 1–3 are individually useful but do not
  change who is orchestrating.
- There will be a period where both systems are live and it is not obvious which
  ran a given task. Attempt receipts must record which path was used, or the
  dogfood fraction is unmeasurable.
- If a phase stalls, Orca keeps working. The fallback is always "keep using
  Orca for that plane", which is why no shim is needed.

## Alternatives considered

**Abstract Orca behind an `IOrchestrator` port and swap implementations.**
Rejected. The interface would be shaped by Orca's model — Runs, Dispatches,
mailboxes — and Orc Bot would inherit that shape into a design that has
deliberately different concepts (candidates, generations, fences). It also makes
the transition invisible: with a port in place, nobody can tell how much is still
Orca.

**Keep Orca permanently as the terminal and worktree layer, and build only the
candidate/validation parts on top.** Genuinely tempting — Orca's terminal work on
Windows is good and was expensive. Rejected because it leaves Orc Bot unable to
run anywhere Orca is not installed, and because ADR-0002's fenced allocation and
ADR-0003's containment plane have requirements an editor's worktree feature does
not owe us.

**Retire Orca all at once when Orc Bot is ready.** Rejected: that day never
arrives, because nothing forces any individual plane to become good enough.
