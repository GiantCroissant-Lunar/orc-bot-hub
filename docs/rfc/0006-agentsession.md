# RFC-0006: AgentSession

- Status: Proposed
- Date: 2026-08-16
- Depends on: ADR-0001, ADR-0003, ADR-0008, ADR-0010, ADR-0011
- Informed by: RFC-0003 (its 2026-08-16 amendments), the JetBrains MCP
  solution-model pinning observed the same day, the three-worker cost wave
  measured the same day

## The problem

Orc Bot must know about the agent CLIs developing *Orc Bot itself*, no matter
who spawned them — Orca, Orc Bot, another orchestration tool, or a human who
typed `codex` into a terminal. The launcher is an attribute of a session, not
its identity. Today three agent CLIs are building Orc Bot and Orc Bot can see
none of them.

That is not a dogfood accounting gap. It is a control-plane gap: the thing
Orc Bot is meant to orchestrate is happening on this machine, right now, and the
orchestrator is blind to it. Stage 6 of RFC-0003's ramp is "Orca is deleted",
and the same day the ADR-0010 question was closed in favour of "retired
scaffold", it became clear that deleting Orca only produces a clean handoff if
Orc Bot can already observe the sessions Orca was launching — plus the ones
Orca was not.

## The model

`AgentSession` is the domain concept. An **Attempt is a subset of it**: an
AgentSession for which Orc Bot owns all three of ADR-0003's planes —
containment, semantics, presentation. Every attempt is a session; not every
session is an attempt.

The dogfood fraction then needs no special machinery. It is `attempts /
sessions` over one list. Modelling "my attempts" and "foreign sessions" as two
disjoint things would force the fraction to reconcile across them, which is
how a derived number goes quietly wrong — two sources of truth, one rounding
direction each, and the gap is where the gaming RFC-0003 already warns against
lives. One list, one denominator, no reconciliation.

## Five sources, mapping onto the planes

| Plane | Source | What it contributes |
| --- | --- | --- |
| containment | the process table | catches everything, including hand-launched sessions. The honest denominator. |
| semantics | ACP / app-server attach | first-hand typed events, where capability allows |
| provenance | orchestrator adapter | metadata only, never truth about progress |
| presentation | terminal | a human can look and type |
| consumption | a usage reader | tokens and, where knowable, money |

The process table is the denominator because it is the one source that cannot
lie about whether a session is running. ACP can miss a session that was
launched without it; an orchestrator adapter can only report what it
dispatched; a terminal can be closed without the session ending; a usage
reader only sees sessions that wrote logs. The process table is what makes
"unattributed" a first-class value rather than a hole in the model.

## ACP is what makes orchestrator-agnostic actually work

This is the load-bearing insight. OpenCode and Kilo ship stdio JSON-RPC ACP
servers, and `acp --port N` plus `attach --session <id>` yields one runtime
with two views of one conversation. Attaching to the *agent's own* machine
channel means Orc Bot needs nothing from the orchestrator about progress —
which is exactly what the closed ADR-0010 question requires, because there is
then no reporting dependency to unwind when Orca is deleted.

This is also why the provenance plane is metadata-only and never truth about
progress. If the orchestrator adapter were Orc Bot's source of "how far along
is this session", retiring the orchestrator would retire the answer. Built
with ACP as the semantic source, retiring the orchestrator retires nothing
about Orc Bot's view of the work — only about who launched it.

## Two limits, stated plainly

- **Capability-declared, never assumed.** Claude Code is NDJSON with no
  joinable runtime. `AgentProviderCapabilities.SupportsJoinableSession` already
  models this (ADR-0003) and callers must branch on it. A session whose
  provider has no joinable runtime is still a session — it just has no
  semantic plane beyond process exit, and that is recorded, not papered over.
- **The spawn has to opt in.** An ACP port cannot be retrofitted onto an
  already-running TUI. The three workers running right now were launched as
  TUIs and therefore cannot be joined. This is an argument for Orc Bot's own
  launcher exposing the endpoint by default: a session that starts without
  `acp --port` is a session whose semantics plane is missing by construction,
  and that is the shape that produces "the agent is thinking" when it has
  actually stalled (S2).

## Provenance metadata

A session records who launched it and how that was learned — a launcher id,
an external task or dispatch reference when the launcher exposes one, and how
Orc Bot discovered the session (process table, ACP attach, orchestrator
adapter, terminal). `Unknown` is a **first-class value, not an error**: not
every tool provides metadata, and a hand-launched agent is a legitimate row.

Unattributed sessions belong in the dogfood **denominator**. Excluding what
cannot be attributed inflates the fraction, which is exactly the gaming
RFC-0003 warns against when it says "dogfooding needs a number, or it becomes
a feeling". A session whose launcher is `Unknown` still consumed a process
table row, still held a terminal, and still produced a diff or did not —
counting only the ones Orc Bot can attribute to itself would report a fraction
that can only go up, which is the shape of the number that is not measuring
anything.

## The limit that survives ACP

Completion is not acceptance. The machine channel settles that a turn ended;
it cannot settle that a diff is correct. Acceptance remains Orc Bot running
validation on a candidate, plus a human promoting it — so an observed
AgentSession can reach *completion* but never *acceptance*.

This is the same boundary RFC-0003 drew for code intelligence: a retrieval
source informs, never settles. ACP is a retrieval source for session state,
not a settlement source for the work the session did. The JetBrains MCP
server that reported `{"problems":[],"totalCount":0}` against a stale
solution model is the same failure shape as an ACP event stream that reports
`turn_complete` against a diff that does not compile — both are the tool
speaking its own truth, neither is Orc Bot's.

## Consumption, the fifth source

The reader in question is `ccusage`, which auto-detects many agent CLIs
(Claude, Codex, OpenCode, Kilo, Gemini, Copilot and others) and groups usage
by day, week, month, and **session**. Session is the important one: it is the
join key onto an `AgentSession`, which is what makes the rest of this
possible.

The payoff is not a cost dashboard. It is **cost attributed to outcomes**.
A usage reader gives cost per session; `AgentSession` gives session to task
to candidate. Joined, Orc Bot can say what a *candidate* cost. Without the
provenance link the number is untethered, which is precisely why this is the
same RFC and not a separate one — the join is the point, and the join lives
on the session id that this RFC already needs.

Measured on 2026-08-16, one wave of three workers on this project:

- one delivered a verified provider with passing tests, for $8.85
- one delivered two accepted deliverables, for $16.20
- one produced nothing at all, and displayed $0.00

### The invariant: measured zero and unmeasurable are not the same value

The third worker was billed through a flat-rate plan, so it has no per-token
price. It still consumed 3.4 million tokens and nine minutes. Rendered
naively, the most wasteful worker of the wave ranks as the cheapest.

**Measured zero and unmeasurable must never be the same value.** This is a
requirement on the source, not a preference in the renderer. It is the same
shape the project hit four times in one day: a stale IDE analyser reporting
zero problems (RFC-0003), an incremental build reporting zero warnings, an
unavailable memory provider returning an empty result (RFC-0004), and now a
flat-rate agent reporting zero cost. In every case an absent measurement was
indistinguishable from a good one. The vocabulary separates the cases in the
type — `Zero` against a measured scale, `Unmeasured` against a missing one —
rather than leaving it to whoever renders the number, because the renderer is
exactly where the pressure to show a clean figure lands.

### Two limits, recorded honestly

- **A usage reader reads local log files.** A worker running on a remote
  host produces no data locally, which is another `Unmeasured`, not a zero.
  The same shape as a session whose provider has no joinable runtime: a
  session that is real, that consumed tokens somewhere, and that this source
  cannot see.
- **It is a third-party tool with its own output format.** It belongs behind
  a typed port exactly as the memory provider and the code-intelligence
  provider do, and its version belongs in the record because it parses
  someone else's format. A silent format change is the same failure as the
  JetBrains solution model pinned at launch: the tool keeps speaking, the
  meaning drifts, and nobody above the adapter is told.

### The rule that keeps it honest

Consumption informs; it settles nothing. A cheap attempt is not a good one
and an expensive attempt is not a failed one. Nothing here may gate
acceptance — same status as retrieved memory and observed code intelligence.
Cost joined to a candidate tells you what it took to get there; it does not
tell you whether "there" is where the work should have gone.

## A consequence for the sibling repository

Worth recording as a known edit, not resolved here: the sibling repository's
terminal contract currently binds a terminal to an `AttemptId`. Under this
model that is too narrow, since an observed session has no attempt — the
attempt is the owned case, the session is the general one. The field likely
widens to a session id, with `AttemptId` becoming the owned case (Orc Bot
launched it, owns its three planes, and the session id *is* the attempt id).
The change is mechanical when it happens, but it has to happen, or a
terminal attached to a hand-launched session has nowhere to record its
binding.

## Open questions

- **Does the process table source run inside `orc serve`, or as a separate
  poller?** Inside is simpler and matches the daemon's existing role as the
  one process that holds operational truth (ADR-0008). The risk is a poll
  rate that either misses short-lived sessions or burns CPU watching
  long-lived ones — the answer is probably `WTSRegisterSessionNotification`
  on Windows rather than polling, but that is implementation, not design.
- **How does a hand-launched session become an attempt?** A human runs
  `codex` in a terminal, then decides to bring it under Orc Bot. The session
  already exists; the question is whether adoption is a single command that
  attaches the missing planes, or whether a session must be launched by Orc
  Bot to ever be an attempt. The model permits the former; the bootstrap may
  only need the latter.
- **Does provenance metadata need its own adapter port, or is it a field on
  the session record?** ADR-0010's "no shim, no adapter layer" rule argues
  for a field; the fact that more than one orchestrator could launch sessions
  on the same machine argues for a port. Decide when a second orchestrator
  actually exists.
