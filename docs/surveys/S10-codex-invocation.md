# S10 — How to invoke Codex CLI reliably, and why injection keeps landing unsubmitted

Scope: live investigation against Codex CLI 0.147.0 on Windows, run 2026-08-16
against a disposable scratch repo and disposable Orca worktree/terminals (never
against `orc-bot` itself — no git command was run in that checkout, and nothing
but this file was touched there). Prompted by three same-day incidents where
`orca orchestration dispatch --inject` left a Codex task pasted in the input
box but not submitted
(`orc-bot/.agent/adapters/runners/codex/config.yaml:34-44`, the `hazards` block).

**This survey overturns the working hypothesis it was asked to test.** The
hazard note's hypothesis — that Codex's MCP startup warnings interleave with
the injected paste and eat the Enter — was tested directly and is **not
supported**. The stuck-paste symptom reproduces identically whether MCP
servers are failing, mid-boot, fully settled, or suppressed outright. The real
trigger is payload size and timing: Codex's TUI collapses a sufficiently large
pasted block into a `[Pasted Content N chars]` placeholder, and absorbing that
placeholder into the live input buffer takes real wall-clock time (low
seconds) during which a submitted Enter is silently dropped rather than
queued. Every claim below carries the exact command run and the output
observed; nothing here is inferred from documentation alone unless marked
**(help-text only, not run live)**.

## 1. Reproduce and isolate

### Setup

A disposable repo was created under the system temp path and registered with
Orca (`orca repo add --path <scratch>/s10-codex-test`), then an Orca worktree
was created from it (`orca worktree create --repo id:<repo> --name
s10-codex-test-wt --setup skip`), giving a worktree at
`<worktrees>/s10-codex-test/s10-codex-test-wt`. All Codex
processes in this survey ran inside that worktree, launched and driven through
`orca terminal create` / `orca terminal send` / `orca terminal read` — the same
public primitives `orca orchestration dispatch --inject` is built from. Every
terminal was stopped and the worktree removed (`orca terminal stop
--worktree ...`, `orca worktree rm --worktree ... --force`) once testing
finished.

### The symptom reproduces via plain `terminal send`, with no `dispatch --inject` involved at all

- Evidence: `orca terminal send --terminal <handle> --text "<9069-byte payload>"` (no `--enter`) against a freshly launched, MCP-still-booting `codex` → `orca terminal read` tail: `...unityMCP) › Run /review on my current changes ... [Pasted Content 9069 chars]`
- Confidence: high
- Bearing: config.yaml hazards block, W5

The exact symptom text from the hazard note — a tail ending in
`[Pasted Content N chars]` with no `Working` line after it — reproduced on the
first attempt, using nothing but the public `orca terminal send` API against a
Codex TUI that had just logged its real MCP failures (see §4). A follow-up
bare Enter (`orca terminal send --text "" --enter`, sent ~3s later) recovered
it: Codex worked the turn and replied `OK`, exactly matching the documented
recovery. This much confirms the existing hazard note is accurate as far as it
goes — it does not confirm the note's *causal* claim.

### MCP state — failing, mid-boot, or fully settled — does not change the outcome

Four separate trials sent a large payload with `--enter` bundled into the same
`orca terminal send` call (i.e. the shape `dispatch --inject` would use if it
does not insert a deliberate wait), varying only the MCP state at send time:

| Trial | MCP state at send time | Result |
| --- | --- | --- |
| 9070-byte multi-line payload, sent while `Booting MCP server: codex_apps` was actively printing | mid-boot, actively producing warning text | `[Pasted Content 9070 chars]`, stuck |
| Same payload, sent after waiting 12s for MCP to reach its terminal `MCP startup interrupted` state | settled (no more spinner or new output) | `[Pasted Content 9070 chars]`, stuck |
| 9035-byte **single-line** (no embedded newlines) payload | settled | `[Pasted Content 9035 chars]`, stuck |
| Same single-line payload, with the three externally-failing MCP servers **and** the built-in `codex_apps` connector suppressed via ephemeral CLI overrides (§4) — no error/warning text printed at all, only a benign `Booting MCP server: pencil` line | healthy, no failures | `[Pasted Content 9035 chars]`, stuck |

- Evidence: four `orca terminal send --terminal <handle> --text "<payload>" --enter` calls, one per row above, each followed by `orca terminal read`
- Confidence: high
- Bearing: config.yaml hazards block

The last row is the decisive one: with every failing/noisy MCP server
suppressed, the payload still lands unsubmitted. **MCP startup state is not a
causal factor.** It is contemporaneous in real dispatches only because Codex
always starts its configured MCP servers at launch, and real dispatch briefs
tend to be large enough to cross the same size threshold described below —
two independent things happening at the same time, not one causing the other.

### The determinant is payload size and elapsed wall-clock time, not line shape or call boundary

- Evidence: five further trials, each `orca terminal send` against a freshly launched codex, comparing payload shape and Enter timing
- Confidence: high
- Bearing: config.yaml hazards block, W5

| Payload | Enter delivery | Result |
| --- | --- | --- |
| 78 bytes, 3 short lines | bundled with the text in one `--text ... --enter` call | Submitted immediately — no `[Pasted Content]` placeholder at all; the TUI showed the three lines as literal typed text |
| 9159 bytes, wrapped into 144 lines of ~70 chars each (no single long line) | bundled | `[Pasted Content 9159 chars]`, stuck |
| 9035 bytes, one long line | bundled | `[Pasted Content 9035 chars]`, stuck |
| 9035 bytes | two separate `terminal send` calls (text, then a bare `--enter`) issued back-to-back with **no deliberate delay** | still stuck |
| Same stuck session, one more `terminal send --text "" --enter` sent **~3s later** | — | Submitted; Codex replied `OK` |

Two things fall out of this table. First, **line shape doesn't matter** — a
9159-byte payload deliberately wrapped into 144 short lines got stuck exactly
like a single 9000-byte line; only a much smaller (78-byte) payload avoided
the placeholder entirely. The collapse into `[Pasted Content N chars]` is
driven by total size, somewhere between 78 bytes and roughly 9KB — this survey
did not narrow the exact threshold further. Second, **splitting the Enter into
a separate call is not sufficient by itself** — the same stuck state persisted
across a second call sent immediately; only once several seconds of real
elapsed time had passed did an Enter register. This means the true mechanism
is a debounce/render delay inside Codex's TUI paste handling: a
placeholder-sized paste is not synchronously absorbed into the live input
buffer, and an Enter arriving before that absorption finishes is dropped, not
queued.

### `orca orchestration dispatch --inject` itself did not reproduce the stall in two live trials

- Evidence: `orca orchestration dispatch --task <task> --to <handle> --inject` against a freshly launched, MCP-still-failing `codex`, run twice with two throwaway tasks and a disposable Run created only for this survey
- Confidence: medium
- Bearing: config.yaml hazards block

Both trials injected the full coordinator preamble plus a one-line task spec
immediately after launch — one while `codex_apps` was booting, one while a
Unity MCP handshake was actively failing mid-turn — and both submitted cleanly
(Codex started working and replied `OK`; the second trial's terminal even
showed live MCP failure text scrolling past while the turn was already
running). This does **not** mean `dispatch --inject` is immune to the bug it
is named in. The throwaway task specs used here were one sentence; the
injected preamble+task combination in these trials was almost certainly under
the multi-KB collapse threshold established above. Real Orc Bot/Orca dispatch
briefs are explicitly instructed to **quote the work item verbatim into the
brief** (`orc-bot/.agent/skills/orca-dispatch/SKILL.md:49`), which is exactly
the kind of payload likely to cross that threshold. Confidence is medium
rather than high because `dispatch --inject`'s internal implementation is not
inspectable from this repo (it is Orca's own closed CLI) — two clean trials
with a small payload are consistent with either "it has no special handling
and simply stayed under the threshold" or "it has some wait/verify step that
this survey's small payload never exercised." Either way, the root cause
identified above — size-triggered paste collapse plus an absorption delay —
is not addressed by anything visible in `dispatch --inject`'s observed
behavior, and a large enough brief should be expected to reproduce it.

### Two secondary artifacts, noted but not root-caused further

- **Injected keystrokes during MCP's own "esc to interrupt" boot window can flip MCP startup itself from `MCP startup incomplete (failed: ...)` to `MCP startup interrupted`.** Observed even in one trial where nothing beyond the initial `codex` launch line was sent — the interruption still occurred ~12s later with no further input from this survey. Plausible cause: some byte reaches Codex during the boot window and is consumed by whatever handles the `esc to interrupt` hint, but this was not isolated further. It does not affect completion correctness (the turn still runs, the MCP failure is still recorded), so it is a UX oddity rather than a correctness bug, but worth flagging as a second, distinct source of confusing terminal text around Codex launch.
- **`orca terminal read` smears rapidly-redrawing frames into overlapping, garbled text** (e.g. tails like `SStaStartartiStartin...`) during MCP boot and while a turn is running. This is the same class of failure S2 documents for `zellij action dump-screen` flattening a full-screen TUI onto one row (`S2-providers-channels-and-containment.md:237-251`) — a live capture of an animated terminal region, read mid-transition, is not reliable text. It never affected the *settled* reads this survey's conclusions rest on, but any future tooling that parses `terminal read` output live (rather than after `tui-idle`) should expect this.
- Two of twelve `orca terminal create --command "codex"` calls (combining creation and launch in one call) returned `runtime_error: Timed out waiting for terminal handle after creation`, even though in at least one case a bare shell was in fact created. Splitting into `terminal create` (bare shell) followed by a separate `terminal send --text codex --enter` was 100% reliable across all twelve terminals used in this survey. Not investigated further; noted as an operational trap for anything scripting `terminal create` with an inline `--command`.

### Root cause

**Codex's TUI collapses a sufficiently large pasted block (threshold somewhere
between 78 bytes and ~9KB, not pinned further here) into a
`[Pasted Content N chars]` placeholder, and that placeholder takes on the
order of a few seconds of real wall-clock time to be absorbed into the live
input buffer; a submit keystroke arriving before that absorption completes is
silently dropped rather than queued or delayed.** This reproduces 100% of the
time (5/5 trials) when Enter is sent without a multi-second gap after a
large paste, regardless of whether Codex's MCP servers are failing, booting,
settled, or entirely absent from the run. It did not reproduce in two trials
using a payload almost certainly below the threshold. The concurrent MCP
startup warnings in the original incident are real, and are worth cleaning up
for their own sake (§4), but they are not the cause of the unsubmitted paste.

## 2. The right way to call Codex non-interactively

Codex exposes four non-TUI entry points: `codex exec` (alias `e`),
`codex app-server`, `codex mcp-server`, and `codex exec-server`. All four were
read in full via `--help`; `exec` and `app-server` were additionally run live.

### `codex exec` / `codex exec --json`

- Evidence: `codex exec --json "Reply with the single word OK and do not run any tools."` run from the scratch repo, stdout and stderr captured to separate files
- Confidence: high
- Bearing: W5

Stdout, fully separated from stderr, was exactly five clean JSON lines with no
other text mixed in: `{"type":"thread.started",...}`,
`{"type":"item.completed","item":{...,"type":"error",...}}` (a benign
deprecated-config-key warning, not an MCP failure), `{"type":"turn.started"}`,
`{"type":"item.completed","item":{...,"type":"agent_message","text":"OK"}}`,
and `{"type":"turn.completed","usage":{...}}`. Stderr, captured separately,
carried the `Reading additional input from stdin...` notice and every
`rmcp::transport::worker: worker quit with fatal:` MCP transport error line.
**An earlier run of the same command with stdout and stderr merged
(`2>&1`) produced garbled, unparseable output** — the MCP error lines and the
JSON lines interleaved mid-line. The lesson: a caller must keep `exec --json`'s
stdout and stderr as genuinely separate pipes/handles, never merged, or the
"clean JSONL" property is lost. This is the same discipline S2 already
documents for stderr drainage
(`S2-providers-channels-and-containment.md:58-69`) — it applies here too, and
merging streams actively breaks the JSONL contract rather than just risking a
blocked pipe.

Process exited 0 regardless of the MCP failures; the typed `turn.completed`
event, not the exit code, is what should be trusted — consistent with the
existing project rule that exit code is transport evidence only
(`S2-providers-channels-and-containment.md:461-476`).

Characterization from `--help`, cross-checked against the run above:

- **stdin:** reads the prompt from stdin if no `PROMPT` argument is given (or `-` is passed); if stdin is piped *and* a prompt argument is also supplied, stdin is appended as a `<stdin>` block. In this run, a prompt argument was supplied and stdin was not deliberately piped, yet Codex still printed `Reading additional input from stdin...` on stderr — it appears to poll stdin opportunistically regardless. A caller should ensure the child's stdin is closed or otherwise won't block, not assume it is ignored just because a prompt argument was given.
- **stdout:** with `--json`, one JSON object per line (JSONL), verified clean above. Without `--json`, plain human-readable text (not tested live; not the mode W5 wants).
- **sessionful:** yes, in a light sense — sessions are persisted to disk by default, and `codex exec resume` (`Resume a previous session by id or pick the most recent with --last`) can continue one. `--ephemeral` opts out of persistence for a true one-shot run.
- **cancellable:** no in-band cancel method — it is an ordinary child process. The only way to stop a run mid-turn is killing the process (tree), which composes directly with the Windows Job Object containment model orc-bot already has for W4.
- **streams typed events:** yes, verified live.
- Other flags worth carrying into W5's launch recipe: `--output-last-message <FILE>` (final message only, for a caller that doesn't want to parse JSONL), `--output-schema <FILE>` (constrains the model's final JSON shape), `--skip-git-repo-check`, `--ignore-user-config` / `--ignore-rules` (see §4 — useful for a hermetic dispatch that doesn't inherit the ambient MCP config at all), `-C/--cd` for the working root, `--add-dir` for extra writable directories, and the same `--sandbox`/`--ask-for-approval` flags as the interactive CLI.

### `codex app-server`

- Evidence: `codex app-server generate-json-schema --out <dir>` produced 39 files including `ClientRequest.json` (184KB), `ServerRequest.json` (49KB), `ServerNotification.json` (176KB), `JSONRPCRequest/Response/Notification/Error.json`, and two full bundled schema files (`codex_app_server_protocol.schemas.json`, 606KB; a `.v2` variant, 513KB), plus `v1`/`v2` subdirectories
- Confidence: high
- Bearing: W5, ADR-0003

This confirms, by actually generating it, RFC-0003's existing claim that
"Codex's `app-server` protocol is generatable as JSON Schema, so generate its
DTOs rather than hand-writing them" (`0003-terminals-interfaces-and-the-dogfood-ramp.md:133-134`).
Grepping the generated `ClientRequest.json` for turn/session-shaped type names
surfaced `TurnStartParams`, `TurnInterruptParams`, `TurnSteerParams`,
`TurnEnvironmentParams`, and `ThreadResumeInitialTurnsPageParams`, alongside
session-listing/migration fields (`maxSessions`, `maxSessionAgeDays`,
`SessionMigration`).

- **stdin/stdout:** JSON-RPC 2.0 over stdio by default (`--listen stdio://`); also `unix://`, `unix://PATH`, or `ws://IP:PORT`, plus a `daemon` subcommand to run a persistent local instance and a `proxy` subcommand to multiplex a stdio client onto that daemon's control socket.
- **sessionful:** yes, explicitly — this is a turn/session-shaped protocol (see the type names above), not a one-shot call.
- **cancellable:** yes, explicitly — `TurnInterruptParams` is a first-class request type, distinct from killing the process. This is almost certainly the same path the TUI's own "esc to interrupt" hint calls internally.
- **streams typed events:** yes — this is the same machine channel the interactive TUI itself runs on.
- Marked `[experimental]` at the `--help` level; the schema-generation and protocol shape are solid, but treat stability as a live caveat, not a settled fact.

### `codex mcp-server` **(help-text only, not run live)**

"Start Codex as an MCP server (stdio)" — this is Codex exposing *itself* as a
set of MCP tools for some other MCP client to call into. The direction is
inverted from what W5 needs: this is Codex as a tool-offering endpoint (a
ToolEndpoint in S9's taxonomy, `S9-machine-controllable-endpoints.md:52-66`),
not Orc Bot driving Codex as an AgentEndpoint. `--help` alone settles the
directionality question that matters for W5's decision, so no live client was
built to probe it further. Possibly relevant much later, per RFC-0003's "MCP
client for tool endpoints — later, and only on demand"
(`0003-terminals-interfaces-and-the-dogfood-ramp.md:166-168`), if some future
worker wants to call *into* a Codex instance as a tool rather than being
driven by Orc Bot as the primary agent.

### `codex exec-server` **(help-text only, not run live)**

Marked `[EXPERIMENTAL]`. Listens on `ws://IP:PORT` by default, or stdio;
`--concurrent-requests` (default 1) bounds how many requests one connection
processes at once; `--remote`/`--environment-id`/`--use-agent-identity-auth`
register it as a Codex Cloud remote environment. Best read, from the flags
alone, as a long-lived process that accepts repeated `exec`-shaped one-shot
turns over a socket rather than spawning a fresh process per dispatch, while
keeping `exec`'s fire-and-forget shape (no session identity) rather than
`app-server`'s stateful turn model. Not smoke-tested — standing up a
`ws://`-listening server and hand-rolling a JSON-RPC-ish client was out of
scope for the time available for this survey, and Codex's own experimental
label is reason enough to treat it as a possible later optimization once
`exec` itself is proven in W5, not a first target.

### Which one for W5, and which for fire-and-forget

Target **`app-server`** as Codex's AgentEndpoint machine channel for any
attempt Orc Bot needs to hold open, steer, or interrupt mid-turn — it is the
sessionful, cancellable, typed-event channel, its DTOs are mechanically
generatable (verified above), and it is the same channel ADR-0003 already
committed to. Use **`exec --json`** for a bounded, fire-and-forget dispatch
that doesn't need mid-turn steering: it is a plain child process, which
composes cleanly with W4's Job Object containment (a piped machine channel and
suspended-job admission are structurally incompatible per S2's process-
containment finding, `S2-providers-channels-and-containment.md:403-424`),
cancellation is "kill the process" (already the containment model), and it was
verified above to emit clean typed JSONL on stdout as long as stderr is kept
on a separate handle — the same stderr-drain discipline S2 already documents.
Do not use the bare TUI as a machine channel for either case; that is §3.

## 3. Why we are using a TUI at all

We inject into an interactive TUI today because Orca's dispatch substrate —
`orca terminal create` plus `orca orchestration dispatch --inject` or
`orca terminal send` — only knows how to drive a target by typing into a PTY.
That is a property of Orca as the *current* dispatch substrate
(ADR-0010), not a property of Codex: `exec` and `app-server`, both verified
live above, are separate, non-interactive entry points into the same agent
loop, with no TUI involved at any point.

Once Orc Bot owns dispatch (W5), it should launch Codex directly as a child
process speaking `app-server` (JSON-RPC over stdio) for held-open attempts, or
`exec --json` for fire-and-forget briefs — never by typing into a rendered
terminal and hoping a paste lands. This sidesteps the entire bug class in §1
by construction: there is no paste, no bracketed-paste placeholder, and no
Enter-timing race, because the prompt goes in as a JSON-RPC parameter or an
argv/stdin string, not as simulated keystrokes racing a renderer.

The TUI still earns its place for exactly the purpose RFC-0003 already scopes
it for: "A human must be able to walk up to a running attempt and look at it,
and type into it" (`0003-terminals-interfaces-and-the-dogfood-ramp.md:35-36`).
That is a human observability/intervention surface, not something Orc Bot
itself should parse or inject into as its machine channel. A terminal
substrate (Zellij or otherwise) can still host a human-facing `codex` TUI
alongside the `app-server`/`exec` channel Orc Bot actually drives for that
same attempt — one attempt, two different consumers, the same split RFC-0003
already draws for other providers' ACP clients versus a human watching.

## 4. MCP startup

### What is actually configured, and what actually fails

- Evidence: `codex mcp list` and the user's `~/.codex/config.toml` (read, not modified)
- Confidence: high
- Bearing: config.yaml hazards block

The user's `~/.codex/config.toml` declares three externally-reachable MCP
servers pointing at Unity Editor MCP bridge endpoints —
`http://localhost:8090/mcp` (twice, under two different names) and
`http://localhost:8190/mcp` — none of which are listening in this environment
(no Unity Editor process reachable at those ports; every attempt to reach them
in every trial in this survey produced an identical
`rmcp::transport::worker: worker quit with fatal: ... HTTP request failed:
error sending request for url (...)`). Two more MCP servers are local stdio
executables tied to Desktop-app-adjacent tooling (`node_repl`, `pencil`) —
both are enabled and did not hard-fail in this survey's runs, but were slow or
stalled to boot in this headless-terminal test environment, adding
multi-second startup latency to every launch regardless of the hard MCP
failures.

**`codex_apps` is not one of the user's configured servers.** It appears in
every `Starting MCP servers (N/M): ..., codex_apps, ...` line because it is a
Codex-internal, feature-flag-gated surface — `codex features list` shows
`apps stable true` — not a `[mcp_servers]` table entry. Disabling it needs
`--disable apps` (or `-c features.apps=false`), not an `mcp_servers` override,
which is worth knowing since it looks identical to a user-configured server in
the TUI's startup line.

### A session-scoped way to suppress the failing servers exists, verified without touching the user's config file

- Evidence: `codex --disable apps -c mcp_servers.UnityMCP6.enabled=false -c mcp_servers.UnityMCP6C.enabled=false -c mcp_servers.unityMCP.enabled=false` → `orca terminal read` showed only `Booting MCP server: pencil` / `Starting MCP servers (1/2): pencil`, with no error or warning text at all
- Confidence: high
- Bearing: config.yaml, W5

This is a purely ephemeral, per-invocation CLI override (`-c` and `--disable`
never write to `config.toml`); it was verified to actually suppress startup
attempts for all three failing Unity servers and the built-in `apps`
connector, leaving only the two locally-hosted, non-failing servers to boot.

Two other approaches were tried and did **not** work, worth recording so
nobody re-tries them:

- `-c 'mcp_servers={}'`, intended as a blanket "replace the whole table"
  override, had no effect — all servers still attempted to start. Whether
  this is because a single dotted-path override cannot replace an entire
  table this way, or because of how the interactive shell handled the literal
  `{}` characters, was not isolated further; the per-server `enabled=false`
  form above is the verified-working approach.
- `--disable rmcp_client` — `rmcp_client` is the exact feature name shown
  under `[features]` in the user's own `config.toml` — was rejected outright:
  `Error: Unknown feature flag: rmcp_client`. It is apparently not a flag
  `codex features`/`--disable` will toggle via the CLI despite appearing
  settable in the config file directly; do not rely on it as a CLI switch.

### Disabling MCP does not fix the paste symptom

As shown in §1's MCP-state comparison table, the same oversized payload still
landed as `[Pasted Content 9035 chars]` with every failing/noisy server
suppressed this way. **Disabling these servers is worth doing on its own
merits** — it removes several seconds of startup latency and irrelevant
stderr noise from every dispatch — but it must not be presented as a fix for
the unsubmitted-paste problem, because it demonstrably is not one.

### What the user might want to change (not applied here)

Since the three failing servers are tied to a Unity Editor MCP bridge and this
is a Godot project, the user may want to either invoke Codex dispatches
through a `codex` profile (`-p <name>`, which layers
`$CODEX_HOME/<name>.config.toml` on top of the base config) that omits them,
or move the Unity entries out of the base `config.toml` into a profile enabled
only when actually working against a Unity project. This survey did not touch
`config.toml` and takes no position on which the user should prefer — flagging
the option, per the task's instruction, and leaving the decision with them.

## 5. Recommendation

### Concrete change to `orc-bot/.agent/adapters/runners/codex/config.yaml`

The current `hazards` block (`config.yaml:34-44`) states the MCP-race
hypothesis as settled fact and offers only reactive recovery (send one Enter
after the fact). Based on the findings above, whoever owns this file should
consider updating it along these lines:

- Correct the causal claim: the MCP warnings are contemporaneous with, not
  the cause of, the stuck-paste symptom. The real trigger is payload size —
  a task brief large enough to cross Codex's TUI paste-collapse threshold
  (bounded here between 78 bytes and ~9KB, not pinned further) — combined
  with sending Enter without a multi-second gap afterward. Real Orc Bot/Orca
  briefs, which are explicitly instructed to quote the work item verbatim
  (`.agent/skills/orca-dispatch/SKILL.md:49`), are squarely in the size range
  that reproduces this.
- Change the injection strategy from reactive detect-and-recover to
  prospective wait-then-verify: after any inject/paste, wait for `tui-idle`
  and confirm the tail no longer ends in `[Pasted Content N chars]` — not
  just that `input_accepted` was reported — before treating the dispatch as
  delivered. If the placeholder is still present, send a bare Enter and
  re-check; this keeps the existing reactive recovery as a fallback rather
  than replacing it, since the exact size threshold and minimum safe delay
  were not pinned precisely enough to hard-code a number with confidence.
- Optionally record the verified session-scoped MCP suppression flags
  (`--disable apps`, `-c mcp_servers.<name>.enabled=false` per failing
  server) as a non-interactive launch addendum for dispatches that don't need
  Unity MCP tools, purely to cut startup latency and noise — explicitly not
  framed as a fix for the paste bug.
- The file's existing `mcp: enabled: false` field does not correspond to any
  real Codex CLI switch found in this survey — there is no single "disable
  all MCP" flag, only the per-server/per-feature overrides above. Flagging
  this as possibly aspirational or stale for whoever next edits the file;
  this survey does not edit `config.yaml` itself.

### What W5 should implement

- Target `codex app-server` (JSON-RPC/stdio, generatable DTOs, explicit
  session/turn/interrupt types) as Codex's held-open AgentEndpoint machine
  channel, and `codex exec --json` as the fire-and-forget path for bounded
  one-shot dispatches — both verified live above, neither requiring a TUI.
- Never launch Codex as a bare TUI from Orc Bot's own dispatch path. Reserve
  the TUI for the human-observability surface RFC-0003 already scopes it for,
  hosted on whatever terminal substrate Orc Bot ends up with, in parallel
  with — not instead of — the machine channel Orc Bot actually drives.
- Whichever channel is used, don't let a headless dispatch inherit the user's
  ambient `~/.codex/config.toml` MCP servers unexamined: use
  `--ignore-user-config` plus an explicit, minimal MCP set, or a dedicated
  profile, so a stray Unity/Desktop-app server can't add multi-second latency
  or stderr noise to every attempt. Keep stdout and stderr on genuinely
  separate handles for `exec --json` — merging them was verified above to
  break the clean-JSONL property, not just risk a blocked pipe.
