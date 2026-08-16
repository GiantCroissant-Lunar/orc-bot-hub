# RFC-0003: Zellij, the MCP/CLI/ACP surfaces, and the dogfood ramp

- Status: Proposed
- Date: 2026-08-16
- Depends on: ADR-0001, ADR-0003, ADR-0008, ADR-0010, ADR-0011
- Informed by: surveys S2, S9; discussion/jetbrains-mcp.md

Three questions this answers: what Zellij is actually for and how it gets driven,
how the MCP, CLI, and ACP surfaces get built and in what order, and how Orc Bot's
own development moves off Orca onto Orc Bot without a big-bang cutover.

## A correction first

ADR-0011 gave three reasons the Godot host should not be the CLI. The third —
that Godot headless costs ~396 ms against ~51 ms for a console app — is
**downweighted**: disk and startup budgets are not scarce, and a few hundred
megabytes of CLI is unremarkable. The decision does not change, because reasons
one and two stand on their own: making the Godot host the CLI puts a UI on the
critical path for every headless and CI invocation (inverting ADR-0008), and it
makes a game engine a prerequisite for `orc task get`.

The practical consequence of relaxing the size constraint is that `orc` should be
**fat and self-contained**: daemon, CLI, MCP server, and ACP client in one
binary, publishable self-contained, with no "install these three things first".

---

## Part 1 — Zellij

### What it is for

ADR-0003 says terminal output is never truth. That is what Zellij is *not*. What
it *is* for is narrower and worth stating positively:

**A human must be able to walk up to a running attempt and look at it, and type
into it.** An orchestrator without that is only debuggable after the fact, and
the period when it matters most is exactly now, while Orc Bot is being built.

Zellij is also the answer to a question ADR-0010 creates. Orca currently supplies
terminals. When Orca is retired, the terminal plane has to become Orc Bot's, and
Zellij is the substrate already validated on Windows for persistent sessions,
targeted input, viewport observation, reconnect, exit observation, and cleanup.

### The binding

Zellij never holds identity. Orc Bot does:

```
TaskId → AttemptId → TerminalBinding { provider: "zellij", externalSessionId, externalPaneId }
```

The CLI resolves it, so nobody memorises a session name:

```bash
orc terminal list
orc terminal inspect <attempt>
orc terminal attach  <attempt>
orc terminal input   <attempt> "..."
```

### The rules, all of which were paid for

From S2, in the order they will bite:

- **One session per agent, never a shared split.** A cramped pane does not
  degrade an agent TUI, it crashes it outright — OpenCode's Bun runtime segfaults.
- **`orc serve` must not capture stdout when it spawns Zellij.** A Zellij session
  spawned from a process with redirected stdout silently breaks *every pane it
  creates*. This is a hard constraint on the daemon's process-launch code, not a
  preference, and it is invisible until a pane misbehaves.
- **A detached session has no client and defaults to ~46 columns**, which is
  destructive to a full-screen TUI. The only known fix is to briefly attach a
  correctly-sized console and drop it.
- **Read with `subscribe --format json`.** `zellij action dump-screen` silently
  collapses a full-screen TUI's entire viewport onto one row. It is correct only
  for line-oriented output.
- **A killed session lingers `EXITED` and resurrects**, inheriting stale panes,
  cwd, and size. `delete-session` before reuse.
- **`zellij --cwd` works** on 0.44.3 — an earlier note that it was ignored was
  retested and is wrong. Whether `ZellijWorkingDirectoryGuard` is still needed is
  an open question for W6.
- **Git Bash's exported `$SHELL` cannot be Zellij's default pane shell** on native
  Windows.
- **`zellij` reports "no sessions" as a non-zero exit.** Pattern-match it; do not
  treat it as a generic failure.
- **Build the command line yourself.** PowerShell strips embedded quotes when it
  serialises a native command's argv, so a JSON argument arrives malformed and
  re-split. Assign `ProcessStartInfo.Arguments` directly.

### What Zellij is still not

Not the completion signal (that is the machine channel), and not the containment
boundary (that is the Job Object). Closing a pane killed the completion bridge
and left its OpenCode child alive, which is the whole reason those are three
separate planes.

---

## Part 2 — the MCP, CLI, and ACP surfaces

### They are four things, not three

The discussion in `jetbrains-mcp.md` makes a distinction worth adopting: what
matters is not the product, but whether an endpoint *performs an attempt*,
*manages a fleet*, or *offers capabilities*. Crossed with direction, Orc Bot has
four surfaces and they are not variants of each other:

| Surface | Direction | Role | Protocol |
| --- | --- | --- | --- |
| **CLI** | in | a shell drives Orc Bot | local, client of the daemon |
| **MCP server** | in | an external agent drives Orc Bot | MCP tools + resources |
| **ACP client** | out | Orc Bot drives a worker agent | ACP / app-server / NDJSON |
| **MCP client** | out | a worker gains tool capability | MCP, admitted into a loadout |

The last one is the one that is easy to miss and easy to get wrong, and the
2026-08-16 design session drew a line through it that the original wording did
not: a JetBrains IDE exposing an MCP server is **two different things depending on
which side of the IDE you stand on**, and the rule that held for tool use does
not hold for retrieval.

**Mutating IDE operations stay worker-only.** Rename, extract method, safe
delete, reorganise namespaces. Orc Bot never calls them. The worker admits the
MCP server into its loadout and consumes it; Orc Bot gains no capability, the
agent does, under Orc Bot's grant. This is the original reading and it stands
unchanged — anything else turns the orchestrator into a tool user, which is a
different product. The boundary is the port, not a grant list: nothing above the
plugin can even ask for a rename, so no policy has to refuse one.

**Read-only code intelligence is a retrieval source.** `lint_files`,
`get_symbol_info`, `get_class_hierarchy`, `search_symbol` arrive behind a typed
port in the plugin, so the application surface never sees "MCP tools" — it sees a
provider. MCP is the plugin's implementation detail exactly as HTTP is the
implementation detail of the existing Mem0 memory provider. ADR-0001 already
requires this shape of an adapter: one application surface, every ingress an
adapter over it. Code intelligence becomes one more adapter behind that surface,
not a special case.

The guard that must be stated plainly: **code intelligence informs, never
settles.** Validation stays with a build the orchestrator runs itself. The
evidence for this arrived the same day the line was drawn — a JetBrains MCP
server pins its solution model at launch, so after new projects were added it
reported `{"problems":[],"totalCount":0}`, byte-identical to a genuinely clean
repository. That is ADR-0003's "terminal output is never truth" applied to a tool
that speaks JSON instead of ANSI, and it is why a retrieval source may never
reach acceptance. A JSON body is not a build.

### Build order, and why

**1. CLI first (W9).** Everything else is a rendering of the same application
commands, so building it first forces those commands to exist and to be
promptless. It is also the only surface that works before anything else does. Any
agent that can run a shell command can drive Orc Bot on day one — which is the
whole bootstrap.

**2. ACP client second (W5).** This is where the actual work happens, and it is
the largest source of unknowns. Build it against exactly two providers with
*different shapes* — one ACP-native and one that is not — because the second one
is what stops the interface from silently encoding the first one's assumptions.
Codex's `app-server` protocol is generatable as JSON Schema, so generate its DTOs
rather than hand-writing them. Claude Code is NDJSON with no joinable runtime, so
it is the honest second.

Capabilities are **declared per provider**, never assumed shared:

```
session.create   session.resume   session.cancel
events.typed     events.streamed
permission.request
fs.read / fs.write        <- declared, and not a sandbox
```

The ACP filesystem capabilities are worth a warning in the code: all four live
agents completed a file-editing task without issuing a single `fs/read` or
`fs/write`. The client-side path check constrains nobody who matters. Containment
is the fence plus the OS.

**3. MCP server third (W11).** Thin by construction — tools for actions,
resources for state, over the same handlers the CLI calls:

```
tools:     orc_task_submit  orc_task_cancel  orc_candidate_accept  orc_candidate_reject
           memory_search  memory_propose  memory_approve  memory_reject
resources: orc://tasks/<id>          orc://operations/<id>
           orc://candidates/<id>     orc://candidates/<id>/delta
           orc://evidence/<id>       orc://memory/<id>
```

The default external-agent profile may submit, inspect, and comment. It may not
accept, integrate, force-reset a slot, or release authority. Authorisation is at
the application surface, so arriving over MCP grants nothing extra.

**4. MCP client for tool endpoints — pulled forward, and split.** It is the
mechanism by which a worker gets IDE indexing, navigation, and refactoring. The
original schedule put it "later, and only on demand". The 2026-08-16 line through
Part 2 retires that ordering: retrieval-side code intelligence
(`lint_files`, `get_symbol_info`, `get_class_hierarchy`, `search_symbol`) now
schedules with the adapters that feed the application surface, because it is one
of them, and a worker needs it the moment a real task asks "where is this
symbol". Mutating IDE operations (rename, extract, safe delete) keep the
"admitted into a worker's loadout" rule above and stay worker-only by
construction — the plugin port does not surface them.

**5. ACP server — not scheduled.** Orc Bot presenting *itself* as an agent to Zed
or JetBrains Air is a genuine future, not a bootstrap need.

### Where this resolves ADR-0010

ADR-0010 treats Orca as scaffolding to retire. The endpoint taxonomy originally
suggested a second reading: Orca as a legitimate **OrchestratorEndpoint** — a
system that controls agents and worktrees, to which Orc Bot could permanently
delegate a bounded sub-plan and reconcile the results.

**Resolved 2026-08-16: retired scaffold, which is ADR-0010's original reading.**
Orca is in use only because Orc Bot cannot yet spawn agent CLIs itself. The
reason is what makes the answer falsifiable rather than a preference: the day Orc
Bot can launch, contain, and settle a worker on its own machine channel, the
question stops being "do we keep Orca" and starts being "what would Orca do that
Orc Bot cannot do itself", and the answer so far is nothing.

The architectural consequence is the part that matters, and it constrains the
AgentSession work in RFC-0006: **Orca must never shape the domain — only supply
observations of it through an adapter.** Stage 6 below is "Orca is deleted". If
the observation model were built around Orca's handles and dispatch ids, that
stage would be a rewrite. Built adapter-first, it is removing a plugin with
nothing above it changing.

---

## Part 3 — the dogfood ramp

"Dogfooding" needs a number, or it becomes a feeling. The number is the
**dogfood fraction**: of the work items completed on Orc Bot this week, what
share ran through Orc Bot rather than Orca. It starts at zero and is reported
honestly, including when it goes down.

For it to be measurable at all, every attempt receipt must record which path
executed it. That is a W1 contract field, not an afterthought.

### The stages

Each stage names what changes, and the proof that it happened — a real task in
this repository, not a passing test.

**Stage 0 — now.** Everything runs through Orca. Orc Bot orchestrates nothing.
Fraction: 0.

**Stage 1 — Orc Bot allocates (needs W1, W2, W3).** A worker still launched by
Orca, but working inside an Orc Bot allocation, and its result frozen as an Orc
Bot candidate that a human accepts through `orc`.
*Proof:* one work item where the diff that landed came out of `orc candidate accept`.

**Stage 2 — Orc Bot launches and settles (needs W4, W5).** Orc Bot starts the
worker, owns containment, and settles the attempt on a typed completion event.
Orca is no longer in the execution path for that work item.
*Proof:* an attempt that completes with no Orca dispatch, and a killed attempt
that leaves no surviving descendant process.

**Stage 3 — Orc Bot is watchable (needs W6, W8, W9).** `orc task submit` from a
shell, `orc terminal attach` into the live worker, `orc task get` from a second
shell while it runs.
*Proof:* the loop at the top of RFC-0001, run by a person, on a work item that
was going to be done anyway.

**Stage 4 — Orc Bot is addressable by agents (needs W11).** The lead agent
developing Orc Bot submits through MCP rather than a shell, and cannot accept its
own candidate.
*Proof:* a work item submitted by an agent, executed by Orc Bot, accepted by a
human.

**Stage 5 — Orc Bot learns (needs W10).** Run 1 proposes a fact, a human promotes
it, run 2's receipt proves it was in context and the retrieval is replayable.
*Proof:* the two receipts, side by side.

**Stage 6 — Orca is deleted.** `AGENTS.md` stops mentioning it and the
`orca-dispatch` skill is removed. Whether this happens at all depends on the
OrchestratorEndpoint question above; what does not depend on it is stages 1–5.

### The rule that keeps this honest

**Do not run a work item through Orc Bot to raise the fraction.** Route work
through whichever system can actually do it, and let the fraction measure
capability rather than enthusiasm. A stage counts when the *natural* choice for a
real task became Orc Bot — not when it was forced once for a demo.

Attempt 2 passed its entire first-slice acceptance exactly once, manually, and
then spent its remaining twenty hours hardening something else. A demo is not a
stage.

## Open questions

- ~~Is Orca a retired scaffold or a permanent OrchestratorEndpoint?~~ Resolved
  2026-08-16: retired scaffold. See "Where this resolves ADR-0010" above.
- Does `ZellijWorkingDirectoryGuard` still earn its place now that `--cwd` is
  confirmed working on 0.44.3? (W6)
- Does the MCP server live inside `orc serve`, or as its own process? Inside is
  simpler and is the default assumption until something argues otherwise.
