# S9 — Organizing the JetBrains MCP discussion into a decision-ready endpoint taxonomy

Scope: [`docs/discussion/jetbrains-mcp.md`](../discussion/jetbrains-mcp.md) (872
lines, two branched conversations concatenated at line 128), read against
ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0008, ADR-0010, ADR-0011,
[RFC-0001](../rfc/0001-bootstrap-slice.md), and
[S2](S2-providers-channels-and-containment.md).

**This file organizes a design conversation. It is not evidence, and the
discussion it organizes is not evidence either.** Per the surveys README, a
survey's claims normally carry `Evidence: <path>:<line>` for something that
*happened* — a run, a shipped line of code, a dated incident. Almost nothing
here meets that bar. The discussion is a single AI-generated conversation
reasoning from public product documentation, most of it unprobed against a
running instance of anything named. Every product-specific claim below is
therefore marked **ASSERTED** (stated in the discussion, unverified) unless a
second, independent, in-repo source corroborates it, in which case it is
marked **VERIFIED** and that source is cited alongside. Treat this file as
raw material an ADR could be drafted from, not as the ADR's evidence base.

## 1. The taxonomy

The discussion proposes replacing "agent CLI provider" with three endpoint
kinds (`docs/discussion/jetbrains-mcp.md:4,20-36`):

### AgentEndpoint (`docs/discussion/jetbrains-mcp.md:39`)

**Owns:** nothing on its own — it performs one attempt. Orc Bot owns "the work
item, source allocation, cancellation, permissions, completion, candidate
publication, and durable identity" for that attempt.
**Must never own:** the candidate's promotion. This is already this repo's
rule, independent of the discussion: "an agent proposes; it does not promote"
(AGENTS.md invariant 4; ADR-0002 line 37, "Only Orc Bot produces the rest").
**The test:** does Orc Bot launch it directly, hold its machine channel for
the duration of one attempt, and can Orc Bot unilaterally cancel it mid-turn?
If yes, it's an AgentEndpoint. Codex, Claude Code, OpenCode, Junie, and Kilo
are placed here (`:39`).

### OrchestratorEndpoint (`docs/discussion/jetbrains-mcp.md:41`)

**Owns:** its own agents, worktrees, and sessions for a sub-plan Orc Bot
delegated to it as one bounded unit.
**Must never own:** being mistaken for Orc Bot's own work topology. Orc Bot
"record[s] that delegation as a child orchestration authority and
reconcile[s] its results rather than pretending each child terminal is
directly Orc Bot-owned" (`:41`).
**The test:** does the product manage worktrees/sessions/agents as a
first-class capability of its own, such that Orc Bot must delegate a bounded
sub-plan and later reconcile the result, rather than holding one machine
channel itself? Orca and Scape are placed here (`:41`).

### ToolEndpoint (`docs/discussion/jetbrains-mcp.md:43`)

**Owns:** capabilities offered to an agent that Orc Bot already owns — symbol
search, build, refactor, and similar.
**Must never own:** any signal that settles an attempt. The discussion states
this twice, once abstractly ("MCP calls must not become agent completion
events", `:208`) and once concretely: `Rider: lint_files -> 0 problems` does
not mean `Agent attempt = Completed`, and `Rider: build_project -> success`
does not mean `Candidate = accepted` (`:210-224`). A ToolEndpoint's output is
"evidence belonging to one development operation or validation phase" (`:226`),
never a verdict.
**The test:** is the product something an agent calls *into* for capability,
while something else (Orc Bot, or the agent under Orc Bot's authority) still
decides when the unit of work is done? JetBrains' IDE MCP server is the
worked example (`:43,136`).

### Where the discussion is ambiguous

**Naming is not stable across the file.** The same concept is spelled four
different ways in four different places: `OrchestratorEndpoint` in the
taxonomy diagram (`:28`), `ExternalOrchestrator endpoint` in the per-product
table (`:18,19`), and `ExternalOrchestratorProvider` in the build-order list
(`:122`). The tool side fares no better: `ToolEndpoint` (`:28`),
`Tool/IDE endpoint` (`:16`), `DevelopmentToolEndpoint` (`:197`), and
`JetBrainsMcpToolEndpoint` (`:827`) all name overlapping-but-not-identical
things. The `AgentProvider.endpointKind` enum itself only offers three
lowercase values — `agent | orchestrator | tool-host` (`:63-65`) — which is a
fifth spelling again. An ADR drafted from this discussion needs to pick one
name per kind before anything else; the discussion doesn't do this for you.

**JetBrains Air does not cleanly fit any of the three kinds.** The per-product
table says Air is "Not really an AgentEndpoint itself... Orc Bot should
normally talk to the agent Air launches, rather than automate Air" (`:14`) —
but Air's actual function as described ("Air is primarily an ACP client/host:
its acp.json starts ACP-compatible agents", `:14`) is structurally the same
thing that defines an OrchestratorEndpoint: a system that itself launches and
controls agents. The discussion never assigns Air that kind, though. Its
closing summary instead buckets Air with the *tool* side — "Air/JetBrains IDE
are agent hosts/tool hosts" as distinct from "Orca/Scape are orchestrators"
(`:126`) — even though nothing about Air matches the ToolEndpoint definition
(it doesn't give an agent capabilities; it launches the agent in the first
place). Operationally the discussion resolves this by recommending Orc Bot
bypass Air entirely and talk to whatever agent Air started (`:549-563`, the
"JetBrains-hosted mode" vs "Orc Bot-owned mode" split), which sidesteps the
classification question rather than answering it. An ADR should treat Air as
a fourth, currently out-of-scope case — not silently fold it into either
OrchestratorEndpoint or ToolEndpoint.

**The discussion cites decision numbers ("D-NN") that do not exist in this
repo.** Three places assert continuity with "your current" decisions using a
`D-##` shorthand: "Your current D-22 already defines a validation slot as a
stable authority... claims are transactional and fence-checked, concurrent
claims return busy, quarantined slots stay non-claimable" (`:283`); "This is
much more consistent with D-23/D-24/D-28 than relying on whatever MCP tools
happen to be visible" (`:493`); and "Keep MCP SDK/types outside contracts,
consistent with D-06" (`:827`). This repo has no `D-NN` register — its
decisions are `docs/adr/0000` through `0011`, and none of them use that
numbering. `D-01` through `D-29` is the abandoned second attempt's
`decision-register.md`, documented in
[S5](S5-decisions-and-shape-of-failure.md:72-74) as having "decayed into an
implementation specification" between 2026-08-12 and 2026-08-14 — a dead
artifact on a `D:` snapshot, not part of this repo. The closest living
equivalent to "D-22"'s validation-slot fencing is ADR-0004's
`ToolAuthoritySlot` (leased, rebuildable, never a source of truth — see
§5), but ADR-0004 does not use the words "busy" or "quarantined," and the
quarantine/busy vocabulary the discussion attributes to "D-22" traces instead
to the *abandoned* attempt's own operational incident record
([S2](S2-providers-channels-and-containment.md:370-382), about a stuck
operation, not a tool slot). An ADR written from this discussion must not
assume "D-22", "D-06", or "D-23/24/28" name anything real here — it should
re-derive the fencing semantics for a future validation slot from ADR-0002
and ADR-0004 directly.

## 2. Transport vs. kind

The discussion argues capability discovery should replace product-name
branching, and proposes a schema (`docs/discussion/jetbrains-mcp.md:53-76`):

```
transport:
  acp-stdio        native-jsonl      native-jsonrpc
  http-api         mcp               structured-cli
  terminal-only
```

This isn't a new idea in this repo — ADR-0001 already separates the two
protocol *directions* transport belongs to ("human/script/agent → Orc Bot:
CLI, MCP" vs. "Orc Bot → coding agent: ACP, provider-native machine channel",
`docs/adr/0001-one-application-surface-behind-every-adapter.md:15-21`) and
ADR-0003 already states that machine channels "differ by shape and are
normalised by declared capability, never by a lowest common denominator"
(`docs/adr/0003-three-independent-planes-per-attempt.md:65-66`), both
accepted the same day as this discussion. What the discussion adds is the
*capability list itself* — something neither ADR enumerates:

```
session.create   session.resume   session.prompt   session.cancel
session.stream   permission.request   tool.event   file.diff
plan.update      usage.observe    artifact.observe   workspace.bind
process.identity
```
(`:79-91`)

**One granularity mismatch worth flagging:** the transport enum treats `mcp`
as a single value, but the discussion's own JetBrains section later describes
MCP as having at least three distinct wire transports of its own — "SSE,
stdio and HTTP Stream configuration" (`:142`). If the transport enum stays
flat, a ToolEndpoint's actual reachability (can Orc Bot reach this JetBrains
MCP server over stdio from a launched subprocess, or does it require an
HTTP/SSE connection to an already-running IDE?) is invisible at the schema
level that is supposed to make capability discovery meaningful.

**A second, differently-named capability vocabulary appears later in the same
file**, this time for what a ToolEndpoint offers rather than what an
AgentEndpoint's machine channel offers:

```
code.symbol.search   code.symbol.describe   code.calls.analyze
code.inspect.file    code.inspect.batch
project.modules.read project.dependencies.read
project.build        project.run.configuration
source.refactor.rename  source.format   source.patch
debug.session.control   debug.breakpoints   debug.stack.read   debug.variables.read
database.schema.read    database.query.read
```
(`:587-616`)

and a *third*, JetBrains-specific namespace for the same underlying
capabilities, proposed for the MCP tool gateway specifically:

```
ide.symbol.search   ide.symbol.describe   ide.calls.analyze
ide.inspection.read ide.project.describe
ide.refactor.rename ide.source.patch
ide.build   ide.run.configuration   ide.terminal.execute
```
(`:463-476`)

The discussion never reconciles `code.*`/`project.*`/`source.*`/`debug.*`
(the cross-IDE, generalized vocabulary) with `ide.*` (the JetBrains-typed
gateway vocabulary covering an overlapping but not identical set — `ide.*`
has no `code.inspect.batch` equivalent, `code.*` has no equivalent to
`ide.terminal.execute`). An ADR needs to decide whether these are one
vocabulary or two before W11 (the MCP adapter) or any later JetBrains work
touches either.

### Load-bearing for W5 vs. merely nice

RFC-0001's W5 is scoped to AgentEndpoints only — "launch a provider, speak
its channel, surface typed events... Capabilities are declared per provider
(ADR-0003) — no lowest-common-denominator interface"
(`docs/rfc/0001-bootstrap-slice.md:174-178`), done when "one provider reaches
typed semantic completion, and a second provider with a different shape
works without changing the first" (`:180-181`). Judged against that bar and
against S2's own three W5-relevant failure modes
(`docs/rfc/0001-bootstrap-slice.md:183-194`):

| Capability | Load-bearing for W5? | Why |
| --- | --- | --- |
| `session.create` | Yes | there is no attempt without it |
| `session.prompt` | Yes | the goal has to reach the agent |
| `session.stream` | Yes | this *is* ADR-0003's typed machine channel — the whole reason W5 exists instead of scraping terminal text |
| `session.cancel` | Yes | ADR-0001's `CancelTask` and W4's containment both need a way to ask the agent to stop before falling back to the kernel-level kill |
| `permission.request` | Yes | "An ACP client must answer every inbound request or the agent stalls in a way indistinguishable from working" (RFC-0001:186-187, sourced from S2) |
| `process.identity` | Yes | W4's containment proof needs exact PID + start-time identity to hand off to; a channel that can't correlate to a process can't be contained |
| `session.resume` | Nice | the one prior-attempt capability-gating correction on record was for exactly this method — advertised, "not yet exposed" (S2:37-39) — a durable warning against declaring it before it's actually wired |
| `tool.event`, `file.diff`, `plan.update` | Nice | observability/presentation, not completion; ADR-0002 already freezes candidates from the actual workspace state, not from an agent's self-reported diff, so `file.diff` specifically is not the source of truth for anything |
| `usage.observe`, `artifact.observe` | Nice | telemetry, not correctness |
| `workspace.bind` | Ambiguous | plausibly load-bearing (an attempt must run against its fenced allocation, ADR-0002) but this may be a launch-argument concern rather than a machine-channel capability; worth resolving explicitly rather than defaulting either way |

## 3. Per-product verdict table

Every product named in the discussion, its assigned endpoint kind, its
transport(s), and — the important separation — what is corroborated by
something other than the discussion versus what rests on the discussion
alone.

| Product | Endpoint kind | Transport(s) | VERIFIED (independent source) | ASSERTED only | Experiment to settle |
| --- | --- | --- | --- | --- | --- |
| **Codex** | AgentEndpoint (`:11,39`) | `native-jsonrpc` (app-server), `native-jsonl`/`structured-cli` (`exec --json`), `mcp` (server mode) | ADR-0003 independently confirms the app-server/JSON-RPC shape and that its DTOs are schema-generated (`docs/adr/0003:67-69`) | that app-server is preferable to `exec --json` for "richer persistent-session integration" (`:11,119`) — a design preference, not measured | Probe both `codex app-server` and `codex exec --json` through W5's registry and record which capabilities in §2's table are actually observed |
| **Claude Code** | AgentEndpoint (`:12,39`) | `structured-cli` (`-p`, JSON/streaming), consumes `mcp` as a client | ADR-0003 independently states "Claude Code is NDJSON, not JSON-RPC, and has no joinable runtime at all" (`docs/adr/0003:69-70`) — compatible with, not derived from, the discussion's framing | that native structured CLI is "preferable" to the ACP adapter route (`:12`) | Launch the structured/streaming CLI mode through W5's registry and confirm the S2-documented launch/profile-mismatch failure (`docs/surveys/S2-providers-channels-and-containment.md:512-527`, a receipt-less `Failed` from a plain-text launch against a profile expecting a typed receipt) cannot recur |
| **OpenCode** | AgentEndpoint (`:13,39`), called "the cleanest reference provider" | `acp-stdio` (`opencode acp`), `http-api` (`opencode serve`) | ADR-0003 corroborates the ACP-stdio shape (`docs/adr/0003:66-67`); the worktree-escape hazard is independently documented from actual dispatch experience, not from this discussion (`.agent/skills/orca-dispatch/SKILL.md:61-64`) | that it's the "cleanest" fit and integrates "almost directly" (`:13`) — not measured against Junie or Codex | Probe `opencode acp` vs. `opencode serve` side by side; separately verify the worktree-escape hazard before trusting it inside a fenced allocation (ADR-0002) |
| **Kilo** | AgentEndpoint (implied — grouped with OpenCode at `:6`, ADR-0003:66-67; the discussion's own product table has no dedicated row for it) | `acp-stdio` (grouped with OpenCode) | ADR-0003 groups Kilo with OpenCode as stdio JSON-RPC ACP servers (`docs/adr/0003:66-67`, same date as the discussion — not fully independent); `.agent/skills/orca-dispatch/SKILL.md:114-117` documents Kilo-specific quota/credit rejection behaviour from real dispatch use | nothing — the discussion never analyzes Kilo on its own; it is the least-examined product in the whole file | Run the same registry probe as OpenCode and record whether Kilo's actual capability set matches or diverges — the discussion gives no basis to assume either |
| **JetBrains Air** | Unclassified — see §1 | `acp` (as client/host, not as something Orc Bot calls) | none | everything about Air's role | Not needed for W5; the discussion's own conclusion is to bypass Air, so no experiment is proposed unless a later RFC decides to delegate to it directly |
| **Junie** | AgentEndpoint (`:15,39`), recommended first in the build order (`:118`) | `acp-stdio` (`junie --acp true`) | none — Junie is absent from the currently-discovered provider list the discussion itself cites (`:6`) | "Excellent AgentEndpoint... a very natural next Orc Bot provider" and "should be easy to add because its ACP server is explicit and officially documented" (`:15,118`) — both confidence claims, never run | The single most directly settle-able unknown in the file: actually run `junie --acp true` once and check it against §2's load-bearing capability list |
| **JetBrains IDEs (Rider/IntelliJ)** | ToolEndpoint (`:16,43,136`); a candidate future `ToolAuthoritySlot` host under ADR-0004 (see §5) | `mcp` (SSE, stdio, HTTP Stream — `:142`) | none — the entire tool-surface table (`:146-159`) is read from JetBrains' public docs, not probed against a running Rider | the whole capability table; the debugger-toolset caveat is one the discussion flags as uncertain about itself ("The Rider MCP reference I inspected does not currently document the equivalent debugger toolset", `:815-818`) | The discussion's own step 1 (`:826`): dogfood Rider MCP manually with read-only tools only (`search_symbol`, `get_symbol_info`, `analyze_calls`, `get_file_problems`) against this solution and record what actually responds |
| **ZCode** | Unclassified / pending (`:17,124`) | none confirmed | none | the absence itself — "its current official integration page does not document a ZCode ACP/server/structured automation interface" (`:17`) is a claim about docs read at an unstated date, exactly the kind of claim that ages fastest | Re-check Z.AI's current docs before treating the absence as durable; meanwhile route GLM through an existing AgentEndpoint's compatible mode rather than building a ZCode adapter |
| **Scape** | OrchestratorEndpoint (`:18,41`) | `mcp` (100+ tools, PID-lineage-gated) | none | the entire capability description and the ownership-gating behaviour — the discussion is explicit that this is unverified: "Orc Bot needs an experiment to verify whether a non-Scape parent process can be admitted" (`:18`) | Exactly the one the discussion names (`:123`): attempt an MCP call (e.g. `create_session`) from a process that is not a Scape-launched descendant and record admit/reject, before any OrchestratorEndpoint design assumes Scape is reachable at all |
| **Orca** | OrchestratorEndpoint (`:19,41`) — "should not be disguised as one agent" (`:19`) | `structured-cli` (JSON CLI: `worktree create`, `terminal create/read/send/wait/stop`) | Strongly — this is the one product this repo verifies continuously through direct use, not through the discussion. AGENTS.md's dispatch section, `.agent/skills/orca-dispatch/SKILL.md`, and ADR-0010's own function-mapping table (`docs/adr/0010-orca-is-scaffolding-not-a-dependency.md:17-25`) all describe the same live CLI surface this task itself was dispatched through | only the framing of Orca's role as *permanent* — see §4 | None needed for the transport/capability facts; the open question is organizational, not technical (§4) |

## 4. Where it conflicts with existing ADRs

**ADR-0010** ("Orca is scaffolding, and is retired plane by plane") gives
Orca an explicit demolition order across five phases, ending with "Orca is
removed from `AGENTS.md` and the `orca-dispatch` skill is deleted"
(`docs/adr/0010-orca-is-scaffolding-not-a-dependency.md:43-51`). Its
Alternatives-considered section explicitly rejects keeping Orca "permanently
as the terminal and worktree layer" (`docs/adr/0010:96-101`) and rejects
wrapping it behind a port precisely because "it makes the transition
invisible: with a port in place, nobody can tell how much is still Orca"
(`docs/adr/0010:89-94`).

**The discussion** places Orca (and Scape) inside a permanent taxonomy
category with no retirement horizon: "OrchestratorEndpoint means 'delegate a
bounded sub-plan to another system that itself controls agents/worktrees/
sessions.' Orca and Scape belong here" (`:41`), and lists "Orca as the first
ExternalOrchestratorProvider" in its forward build order (`:122`) on the same
footing as adding Junie or a JetBrains tool adapter — permanent additions to
the architecture, not scaffolding scheduled for removal.

**Two different futures, laid out without picking one:**

- **Reading A (ADR-0010's).** Orca is present today only because Orc Bot
  cannot yet do the job itself. Every plane it covers is duplicated,
  deliberately, in RFC-0001's own work items (W3 source authority, W4+W5
  containment and machine channel, W6 terminal binding, W7+W8+W9 application/
  daemon/CLI) specifically so it can be switched off phase by phase. Under
  this reading, "OrchestratorEndpoint" as a durable *kind* in Orc Bot's
  taxonomy would still exist — but its only durable member would be Scape (a
  genuinely external system nobody plans to reimplement), not Orca.
- **Reading B (the discussion's).** Orca earns a permanent place as one of
  two example OrchestratorEndpoints because "delegate a bounded sub-plan to a
  system that itself controls agents and worktrees" is a useful capability on
  its own merits, independent of whether Orc Bot could technically
  reimplement it. Under this reading, an OrchestratorEndpoint adapter for
  Orca would persist even after W9 lands — for cases where delegating a
  sub-plan externally (spreading a wave of workers across providers at once,
  exactly the pattern that produced the `docs/surveys/` files this repo
  already relies on) is cheaper than doing the same fan-out through Orc Bot's
  own, presumably more serial, W7 application surface.

**What would decide between them:** ADR-0010 already supplies the test —
"A phase is done when Orc Bot has run a real dispatch without Orca doing that
job — not when the code exists" (`docs/adr/0010:53-54`). The same test
resolves the Orca question specifically: if, once Phase 4 lands, nobody has a
real workload that needs OrchestratorEndpoint-shaped delegation *to Orca in
particular* — as opposed to Scape, which is external by construction and
never had a retirement plan — Reading A wins and OrchestratorEndpoint remains
a real kind with zero durable Orca instance. If such a workload does appear
(a genuinely nested, self-scheduling fan-out that Orc Bot's own task/attempt/
candidate model doesn't cover, and which ADR-0007 keeps out of scope for
engineering-concept planners), Reading B wins, and ADR-0010's phase 5 would
need to be revisited rather than executed as written.

**A second, more structural tension worth naming:** the discussion's own
`AgentProvider { endpointKind, transports[], capabilities }` schema
(`:53-76`) is, functionally, a port that would cover Orca as one instance of
its `orchestrator` `endpointKind`. If a future work item builds a generic
OrchestratorEndpoint abstraction that happens to admit Orca first, that is
the same "abstract Orca behind a port" move ADR-0010's Alternatives section
rejects (`docs/adr/0010:89-94`) — just arrived at from the tool-taxonomy
direction instead of the orchestrator-porting direction. An ADR resolving §4
should say explicitly whether a generic `OrchestratorEndpoint` type is
allowed to exist before Orca is retired, or whether it must wait until Scape
is the only candidate implementer.

## 5. What W5 should actually build first

RFC-0001 scopes W5 to AgentEndpoints only — machine channel and provider
registry (`docs/rfc/0001-bootstrap-slice.md:174-181`). OrchestratorEndpoint
and ToolEndpoint work are both, independently of this discussion, already
placed later: the discussion's own sequencing puts JetBrains MCP integration
at step 2, after a code-free manual dogfood at step 1 (`:826-827`), and
ADR-0010 keeps Orca deliberately un-abstracted until its own phases land. So
"the smallest provider registry that's honest about capability differences"
means, concretely, for W5 and W5 alone:

- **Carry `endpointKind` in the registry record from the start, even though
  only `agent` is admitted today.** Not because W5 needs to resolve
  orchestrator or tool-host records, but because a registry schema with no
  such field at all is exactly the "if provider == 'codex' ... else if
  provider == 'claude'" hardcoding the discussion argues against (`:110-113`)
  — just moved one field up. Adding it after the fact is a breaking
  migration for a cost that is free now.
- **Only implement the transports W5 can actually test today** —
  `acp-stdio` (OpenCode, Kilo, and Junie once added), `native-jsonrpc`/
  `native-jsonl` (Codex), and `structured-cli`/`terminal-only` as the honest
  fallback for Claude Code's NDJSON shape (ADR-0003) — but keep `mcp` and
  `http-api` as unused enum values so ToolEndpoint work later doesn't force a
  schema migration either.
- **Implement exactly the load-bearing capability subset from §2** —
  `session.create`, `session.prompt`, `session.stream`, `session.cancel`,
  `permission.request`, `process.identity` — and represent the rest as
  optional, provider-may-report-absent fields. This is the corrected version
  of a mistake the abandoned line already made once: shipping "every optional
  method is capability-gated" as a blanket claim before the surface actually
  matched it, then having to amend the text in place to say only one method
  was really gated (S2's `docs/surveys/S2-providers-channels-and-containment.md:28-42`).
  Don't repeat that shape here — don't declare a capability flag for anything
  W5 hasn't actually probed.
- **Admit a provider to the live registry only after a real probe, not after
  a name appears in a document.** The abandoned second attempt reached this
  standard only at the very end: "Claude Code, OpenCode, and Kilo ACP
  descriptors are deliberately unavailable — even when their executables are
  discovered — until each exact provider identity and advertised-mode map is
  independently verified" (S2:`docs/surveys/S2-providers-channels-and-containment.md:77-84`).
  W5 should start there rather than re-discover it.
- **Test W5's "second provider with a different shape" criterion against
  three genuinely different providers, not two similar ones.** §3 shows
  OpenCode and Kilo are already-known, same-shaped `acp-stdio` providers
  (`:6`); Junie is unprobed but recommended first (`:118`); Claude Code is
  the one provider ADR-0003 says has "no joinable runtime at all"
  (`docs/adr/0003:69-70`). Running Codex (`native-jsonrpc`), Junie
  (`acp-stdio`, new to this repo), and Claude Code (`terminal-only`/NDJSON)
  as the first three forces the registry to prove it doesn't assume a shared
  subset, rather than proving it against three providers that already look
  alike.
- **Explicitly not W5:** JetBrains MCP (the discussion's own step 2, gated on
  step 1's manual dogfood, `:826-827`) and any Orca/Scape
  OrchestratorEndpoint adapter (ADR-0010 keeps Orca un-abstracted on purpose;
  Scape needs its PID-lineage experiment run first, `:123`, before any
  adapter design starts). Both are real future work; neither belongs inside
  W5's scope.

One alignment worth carrying forward rather than treating as new design
work: the discussion's "Rider Semantic Slot" — "stable project root, stable
Rider solution/project, warm IDE index..." through "claim RiderSemanticSlot"
(`:291-298,352`) — is, structurally, exactly ADR-0004's `ToolAuthoritySlot` ("a
persistent, exclusively-leased instance of a tool's derived state... that an
attempt *borrows* rather than owns", `docs/adr/0004-derived-state-and-tool-authority-slots.md:31-33`)
applied to an IDE instead of an engine. That primitive already exists in
this repo's accepted architecture. A future ADR for JetBrains-as-ToolEndpoint
doesn't need to invent slot semantics — it needs to instantiate ADR-0004's
existing one, which is a smaller and more honest claim than the discussion's
own "D-22" self-citation (§1) suggests.

## Open questions for an ADR

In descending order of how much they'd change the architecture:

1. **Is Orca a temporary scaffold or a permanent OrchestratorEndpoint?**
   (§4) — this is a live fork between ADR-0010 and the discussion, not a
   naming detail, and it determines whether Orc Bot ever builds a generic
   OrchestratorEndpoint abstraction at all.
2. **What is the one canonical name and shape for each of the three kinds**,
   given the discussion itself uses four spellings for two of them (§1)?
3. **Do the `code.*`/`project.*`/`source.*`/`debug.*` and `ide.*` capability
   vocabularies merge into one, or stay two** (§2), before W11's MCP adapter
   or any JetBrains work needs either?

The biggest of the three is (1): it is the only one where picking wrong
means building (or deleting) real infrastructure, rather than renaming a
field.
