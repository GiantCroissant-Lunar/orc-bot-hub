# RFC-0001: The bootstrap slice

- Status: Proposed
- Date: 2026-08-16
- Depends on: ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0006, ADR-0008
- Informed by: RFC-0002 (survey findings)

## Goal

Reach the point where **an external coding agent can use Orc Bot to develop Orc
Bot**, and prove it by doing so.

Concretely, this must work end to end:

```bash
orc task submit --repo <workspace>/agent-projects/orc-bot \
                --agent codex \
                --goal "Add the MCP resource for candidate inspection" --json
orc task get <id> --json          # from a different shell, while it runs
orc terminal attach <attempt>      # a human can see what the worker is doing
orc candidate diff <id>
orc candidate accept <id>
```

and the attempt's receipt names the memory it was given, so the *next* task can
retrieve what this one learned.

Anything that does not make that loop work is out of scope for this RFC.

## Not in scope

Godot operator UI beyond the host shell, GraphEdit, timelines, ECS projections,
Akka.NET, DAG/GOAP/HTN planners, engineering concept packs (ADR-0007), the
knowledge graph, Rust/gdext, and web export. Each returns when a dogfood task
demands it.

## Layout

ADR-0002 and ADR-0008 imply four kinds of C# project, so the tree grows one
directory beyond what exists today:

```
project/contracts/   vocabulary and ports. No policy, no infrastructure.
project/libs/        policy. Core and Application. Not swappable, not plugins.
project/plugins/     adapters. Swappable, discovered, hold capability not authority.
project/hosts/       processes. orc-runtime, orc-cli, complete-app.
```

Adapters live in `plugins/` deliberately: SQLite, Mem0, ACP, and Zellij are
exactly the things that should be replaceable without touching policy, and making
them plugins forces the port boundary to be real rather than aspirational.

| Project | Where | Role |
| --- | --- | --- |
| `OrcBot.Contracts` | contracts | ids, task/attempt/candidate, events, ports |
| `OrcBot.Extensibility` | contracts | the plugin contract |
| `OrcBot.Core` | libs | domain: allocations, candidates, attempts, receipts |
| `OrcBot.Application` | libs | the command/query surface of ADR-0001 |
| `OrcBot.Plugins.Sqlite` | plugins | operational truth |
| `OrcBot.Plugins.SourceLocal` | plugins | first source materialiser |
| `OrcBot.Plugins.Acp` | plugins | ACP machine channel + provider registry |
| `OrcBot.Plugins.Zellij` | plugins | terminal presentation |
| `OrcBot.Plugins.Mem0` | plugins | long-term recall |
| `OrcBot.Plugins.Echo` | plugins | reference plugin; proves the host |
| `orc` | hosts | one binary, two roles — `orc serve` is the daemon, everything else is the client (ADR-0011) |
| `complete-app` | hosts | Godot host shell; a client, never the CLI |
| `OrcBot.Mcp` | hosts | MCP adapter (may start inside `orc serve`) |

## Work items

Each is sized for one dispatched worker with a bounded, non-overlapping scope.
Dependencies are stated so the wave can be planned; `→` means "cannot start
until".

**W1 — Contracts and domain vocabulary.**
Flesh out `OrcBot.Contracts` and add `OrcBot.Core`: attempt, receipt, source
generation, allocation, candidate, evidence, event with a
`{ generation, sequence }` cursor. Records only, plus invariants. No I/O.
*Done when:* the vocabulary expresses everything in ADR-0002 and ADR-0003, and
`task ci` is green.

**W2 — Persistence.** → W1
`OrcBot.Plugins.Sqlite`: schema and repositories for tasks, attempts,
correlations, candidates, decisions, receipts, events. Migrations from the start.
*Done when:* a task submitted, attempted, and disposed round-trips through a
fresh database, and a second process sees the same state.

**W3 — Source authority.** → W1
`OrcBot.Plugins.SourceLocal`: allocate a fenced workspace for an attempt from a
named source generation, freeze a delta into a digest-addressed candidate,
compose a candidate as a read-only dependency layer, release.
*Done when:* two concurrent attempts on the same repository cannot see each
other's edits, and a frozen candidate's digest is stable across re-freezing.

Four things the previous attempts paid to learn (S1) that this must get right
from the first commit:

- **`git diff HEAD` ignores untracked files.** A candidate could list a new
  file's content hash while the generated patch carried nothing, and the patch
  then applied cleanly into a workspace missing the code it was meant to
  inherit. Publication must `git add --intent-to-add` the candidate paths before
  diffing — which touches the index but not the worker's working tree.
- **A live path list is not a frozen candidate.** Rereading the working tree on
  demand means two captures of "the same candidate" can name different content
  while the agent is still writing, and deleting the workspace destroys the only
  evidence. Freeze the entries, and treat a selected file that vanished between
  inspection and capture as a deletion rather than dropping it.
- **Hashes alone make a candidate comparable but unusable.** Pair the frozen
  description with a stored artifact, or a dependent attempt has nothing to
  build on once the workspace is gone.
- **Composition needs a synthetic base commit.** After applying ancestor layers
  into the dependent workspace, commit them — otherwise the dependent item's
  delta against the root generation republishes its ancestors' work as its own.

Overlap between *independent* sibling candidates must be refused before an agent
is launched, not discovered as a merge failure afterwards.

**W4 — Process containment.** → W1
Windows Job Object containment for a launched worker and its children, with
`orc` able to prove a tree is dead.
*Done when:* killing an attempt leaves no surviving descendant, verified against
an agent CLI that spawns children.

**W5 — Machine channel and provider registry.** → W1
`OrcBot.Plugins.Acp`: launch a provider, speak its channel, surface typed events.
Codex uses `app-server`; generate its DTOs from the JSON Schema rather than hand-
writing them. Claude Code is NDJSON with no joinable runtime. Capabilities are
declared per provider (ADR-0003) — no lowest-common-denominator interface.
Adapters resolve to a real binary path; never `npx -y`.
*Done when:* one provider reaches typed semantic completion, and a second
provider with a different shape works without changing the first.

From S2, three failure modes that all present as "the agent is thinking":

- **An ACP client must answer every inbound request.** Miss one and the agent
  stalls in a way indistinguishable from working.
- **Drain the child's stderr.** Once the pipe buffer fills, the child blocks
  silently.
- **A launch/profile mismatch produces a receipt-less success.** Two operations
  exited cleanly with a captured source delta and were still correctly recorded
  `Failed` — because Claude Code had been started in plain-text mode while the
  profile demanded a typed receipt only a structured transport can produce. The
  provider registry must refuse a launch whose transport cannot satisfy the
  profile, rather than discovering it at completion.

**W6 — Terminal presentation.** → W1, W4
`OrcBot.Plugins.Zellij`: bind an attempt to a session/pane, attach, send input,
observe, clean up. Each agent gets its own session with real pane geometry.
*Done when:* `orc terminal attach <attempt>` drops a human into a live worker,
and nothing in this plugin can move an attempt's state.

**W7 — Application surface.** → W1, W2, W3
`OrcBot.Application`: the commands and queries of ADR-0001, with authorisation at
the surface and profiles that can withhold accept/integrate.
*Done when:* every operation is callable with no interactive prompt and returns a
stable, documented result.

**W8 — Runtime daemon.** → W7
`orc serve`: process boundary, versioned local protocol, `{generation,
sequence}` cursors, snapshot + idempotent journal recovery, uncertain outcomes
recorded rather than replayed.
*Done when:* a client can disconnect mid-attempt, reconnect, and either catch up
or receive a coherent snapshot; and killing the client does not kill the work.

**W9 — CLI.** → W8
The same `orc` binary in client mode (ADR-0011). `stdout` machine-readable,
`stderr` diagnostic, stable exit codes, `--json` meaning no decoration and no
prompts. Auto-starts the daemon on first use, without racing a concurrent client
into spawning a second one, and able to distinguish "starting" from
"unreachable".
*Done when:* the full loop at the top of this RFC runs from a shell, on a machine
with no Godot installed.

**W10 — Memory.** → W7
`OrcBot.Plugins.Mem0` behind the `OrcBot.Memory` vocabulary: scope set, retrieve
per scope then rank/dedupe/budget, memory candidates that cannot self-promote,
receipts recording scopes and digests. `orc memory search|inspect|candidates|approve|reject`.
*Done when:* run 1 proposes a fact, a human promotes it, run 2's receipt proves it
was in context.

S3 is blunt about why that bar is set there. The previous Mem0 work proved
persistence and scope filtering and **never** proved a later-run gain, because
context receipts verified the constructed prompt but did not preserve a
replayable retrieval — so no attempt could show recall had helped. A receipt must
record enough to re-run the retrieval, not just enough to show a prompt existed.

Two more from S3: provider-side filters could not be trusted to preserve Orc
scope, so scope enforcement belongs on our side of the boundary and the filter
is an optimisation; and the previous line shipped exactly one live scope
(agent-profile) while modelling five, so a scope that is not exercised should not
be claimed.

**W11 — MCP adapter.** → W7
Tools for actions, resources for state, the external-agent profile of ADR-0001.
*Done when:* an external agent can submit and inspect but cannot accept.

**W12 — Godot host validation.** → W9
Windowed validation as *configuration*: project path, window title, export
preset, and expected artifacts are data (ADR-0004). Screenshots and receipts land
under `build/_artifacts/<version>/`.
*Done when:* a second project type validates with no code change, and the
exported windowed app is verified by looking at it — green build, green export,
and green headless checks have hidden clipped-off-screen controls before.

S4 supplies the precise shapes to avoid:

- The previous protocol matched a window title the app set in **`_Ready`**, so
  validation was matching a runtime string. Set it in `project.godot`.
- One export failed on an invalid preset name and a screenshot was still claimed
  — from a binary that was never produced. A receipt must name the artifact it
  observed and verify it exists.
- Synthetic input drove the UI by `PostMessage` at hard-coded design
  coordinates. It reports success while doing nothing. Drive the UI over a
  control endpoint; only the nonce-bound window observation distinguished "the
  UI displayed something" from "the UI did the right thing".
- The headless smoke test matched tab names and button labels — a string
  comparison that passes against dummy data.
- Godot has no PCK unmount. Repeated bundle reloads grow the mounted VFS
  monotonically for the process lifetime, so hot reload replaces the scene and
  the managed context but leaks resources. Do not design around unmounting.

Engine caches are seeded per allocation, never shared (ADR-0009).

## The milestone that ends this RFC

Not "W12 is done". The milestone is:

> A task that improves Orc Bot was submitted through `orc`, executed by a real
> provider in a fenced allocation, watched live through `orc terminal attach`,
> settled by a typed completion event, frozen into a candidate, accepted by a
> human, and its lesson retrieved by the following task.

Until that has happened once, nothing here is proven.

## What S5 says about ordering

The survey that mattered most was the one that asked when each previous attempt
stopped being usable by the people building it.

Attempt 2 accepted its foundation decisions and reversed most of them the same
day. Its only automated gate never ran a test. Its "verify" step was the
window-presence check its own product rules disallow as acceptance. It passed its
entire first-slice acceptance exactly once, manually, then spent its last twenty
hours on interruption hardening and died inside that hardening's acceptance loop.
A machine-usable surface was bolted on only at the end — after two days of
driving the product exclusively through a window.

Attempt 1 was at least five fresh `git init`s in fifteen days, each abandoning
the previous tree unmerged, ending in three parallel repositories plus an
unmerged survey worktree. Its own progress records were found to be false at
least twice.

Three rules for this attempt follow directly:

1. **The CLI is not allowed to be last.** W9 is the point at which Orc Bot
   becomes usable, and every week it slips is a week of building blind. If
   something has to be cut, cut it from W10–W12, not from W7–W9.
2. **A decision reversed the same week it was accepted is a decision that was
   never made.** Write the ADR when the evidence exists, not to unblock a task.
3. **`task ci` must earn the name.** Right now it proves hygiene, format, and
   compile; W1 owes it real tests. A gate that never ran a test is what let
   attempt 2 stay green while its foundations moved underneath it.

## Risks

- **The daemon is the biggest single piece.** If W8 slips, W1–W7 are still useful
  and the CLI can run in-process for single-shot commands as a stopgap — but that
  stopgap must not be allowed to become the design.
- **Provider drift.** Agent CLIs change their machine channels without notice.
  Mitigated by generating DTOs where a schema exists and by declaring capability
  per provider.
- **Scope creep from ADR-0007.** Typed plan edges are cheap to leave room for and
  expensive to build now. v0 may have exactly one node kind.
