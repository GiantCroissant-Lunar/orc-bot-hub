# ADR-0021: An agent session has two correlated channels, and a durable runner owns its stdio

- Status: Accepted
- Date: 2026-08-17
- Related: ADR-0003, ADR-0010, ADR-0012, RFC-0006
- Carries forward: `prior-attempt (2026-08-09) orc-bot/docs/adrs/0016-pair-zellij-with-acp-machine-channel.md`
  and `prior-attempt (2026-08-12) orc-bot/docs/adr/0003-zellij-terminal-substrate-and-machine-channel.md`

## Context

ADR-0003 separates containment, semantics, and presentation as three planes with
different authority. RFC-0006 requires the semantics plane to be the agent's own
machine channel, so that retiring the orchestrator (ADR-0010) retires nothing
about Orc Bot's view of the work.

The obvious implementation — spawn the agent as a detached server on a port and
connect to it — was assumed workable and is not. Measured 2026-08-16 on the
installed toolchain:

| Channel | Version | Machine transport | Drivable without parent-held stdio |
| --- | --- | --- | --- |
| OpenCode ACP | 1.18.18 | newline-delimited JSON-RPC on stdin/stdout | **No** — exits 0 at stdin EOF; `--port` listener closes |
| Kilo ACP | 7.4.22 | newline-delimited JSON-RPC on stdin/stdout | **No** |
| `claude-agent-acp` | 0.66.0 | newline-delimited JSON-RPC on stdin/stdout | **No** |
| `codex-acp` | 1.1.14 | newline-delimited JSON-RPC on stdin/stdout | **No** |
| Codex **app-server** | 0.147.0 | JSON-RPC over WebSocket (`--listen ws://…`) | **Yes** — listener stayed reachable after the launching process exited |

OpenCode's `--port` is its internal HTTP server, not a socket ACP transport. The
port listener exists only while stdio stays open.

So for every ACP channel available here, **something must hold the child's stdio
for as long as the session must remain reachable, and closing that holder is
session termination — not merely loss of a terminal view.**

Both previous attempts reached the same structural conclusion. This ADR carries
it forward rather than rediscovering it a fourth time.

## Decision

**An owned agent session has two correlated channels, and they never share a
byte stream.**

- **Presentation** — the terminal provider owns the operator-facing view,
  attach/detach, input, restart discovery, and bounded viewport diagnostics.
- **Semantics** — a typed machine channel owns session lifecycle, prompts,
  updates, usage, permissions, cancellation, and completion.

**Machine protocol bytes never traverse the PTY.** Terminal text, pane state, and
process exit cannot grant a permission, declare completion, publish a candidate,
or settle an attempt. This is ADR-0003's authority rule made concrete, and it is
also why scraping a rendered pane is not an implementation option: the question of
whether a viewport stream preserves long-line framing does not arise, because no
protocol byte is ever read from one.

**A durable runner owns the stdio.** For a stdio-bound channel, a runner process
lives in a terminal session that survives the orchestrator, spawns the agent child
with private redirected pipes, and renders typed activity into the pane for the
human. Orc Bot drives the runner. The terminal provider supervises the runner and
never becomes the transport.

**Where a genuine socket transport exists, no runner is required.** Codex
app-server over `--listen ws://` is driven directly. This is a per-provider fact,
declared through capabilities and branched on — never assumed shared.

**The durable owner of a turn is the Orc Bot operation**, not the pane and not the
agent process. Both channels bind to one attempt identity, and correlation is
verified rather than presumed.

Three admission rules, each paid for by the previous attempt:

- **A capability that was not advertised is not called.** The channel refuses,
  rather than attempting the method and interpreting the error.
- **An unrecognised protocol version fails admission.** Reject rather than
  degrade.
- **Agent-originated permission requests default to deny.** The prior attempt
  records that a structured ACP client worked correctly and that *"its permissive
  default was unsafe"* — the defect was the default, not the protocol.

## Consequences

- **Survival becomes a property of the runner's host, not of the agent.** Closing
  the Godot host does not end a session whose runner lives in a surviving terminal
  session — which is the requirement that motivated this.
- **Providers are not interchangeable, and the model must say so.**
  `AgentProviderCapabilities.SupportsJoinableSession` stops being ceremony: the
  transports differ in kind, and a lowest-common-denominator interface would
  silently encode whichever provider was implemented first.
- **The runner is a new component, and it is load-bearing.** It holds stdio for
  every stdio-bound agent, so its own crash ends those sessions. It is the thing
  to make boring and well-tested.
- **A session that dies with its runner must be reported as such**, never as a
  completed or failed attempt. Losing the holder is a distinct fact from the work
  ending, and collapsing them is the same error as reading completion off a pane.

## What is deliberately not decided here

Reconnection after an orchestrator restart, whether an app-server session can be
safely reattached, process-ownership attestation, and completion semantics beyond
"the channel said the turn ended". The 2026-08-12 predecessor required a
process-containment attestation before an attempt could settle or release its
allocation; that is the right shape and it needs its own probes before it is
restated as a decision here.

## Alternatives considered

**Read the machine channel from the terminal viewport.** Rejected by both prior
attempts and again here. It reintroduces exactly the coupling ADR-0003 exists to
prevent, and it makes rendering behaviour — wrapping, styling, scrollback
eviction — part of the protocol.

**Require a socket transport and support only agents that offer one.** Rejected:
on the measured toolchain that is one provider out of five, and it would make the
orchestrator's coverage a function of an upstream implementation detail.

**Hold the stdio in the orchestrator itself.** Rejected because it makes closing
the orchestrator equivalent to killing every agent, which is the requirement this
ADR exists to satisfy.
