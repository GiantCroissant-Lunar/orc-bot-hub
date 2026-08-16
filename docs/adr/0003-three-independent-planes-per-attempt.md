# ADR-0003: Containment, semantics, and presentation are three independent planes

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0002, ADR-0008, [discussion/new-attempt-inital.md](../discussion/new-attempt-inital.md)

## Context

When Orc Bot launches a coding agent, three different questions have three
different answers, and the previous attempts repeatedly let one answer stand in
for another:

- *Is the process contained?* — a live experiment found child processes surviving
  the closure of their terminal pane. Windows Job Objects were added afterwards.
- *Did the work succeed?* — a pane printing "Build succeeded!" is a rendering of
  bytes, not a claim Orc Bot can act on.
- *Can a human see it?* — an orchestrator without an attachable terminal is
  missing an operating surface, no matter how good its event stream is.

Zellij was verified on Windows for persistent sessions, panes, targeted input,
viewport observation, reconnect, exit observation, and cleanup. It works. The
mistake would be promoting it to supervisor.

## Decision

One attempt is **three correlated channels**, each with a single responsibility:

```
                        Orc Attempt
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   containment           semantics            presentation
   Job Object /          ACP / app-server /   zellij
   process group         NDJSON
        │                    │                    │
        └──────────── correlation only ───────────┘
```

**Terminal output never settles anything.** Not completion, not failure, not
permission, not termination. Semantic truth comes from the typed machine channel
only. Process exit is evidence about a process, not about an attempt.

**Zellij is mandatory in v0 anyway** — not because a process cannot be launched
without it, but because being able to attach to a live worker is what makes
developing Orc Bot through Orc Bot bearable. It ships in the bootstrap set and is
still never trusted.

**Orc Bot owns identity; providers supply handles.** Zellij session names are not
task identities. The mapping is explicit:

```
TaskId → AttemptId → TerminalBinding { provider, externalSessionId, externalPaneId }
```

and the CLI resolves it, so nobody memorises session names:

```
orc terminal list
orc terminal inspect <attempt>
orc terminal attach  <attempt>
orc terminal input   <attempt> "..."
```

**Machine channels differ by shape and are normalised by declared capability,
never by a lowest common denominator.** OpenCode and Kilo ship stdio JSON-RPC ACP
servers. Codex uses `app-server` — same runtime and channel shape, JSON-RPC, and
its whole protocol is generatable as JSON Schema, so its DTOs are generated
rather than hand-written. Claude Code is NDJSON, not JSON-RPC, and has no
joinable runtime at all. `IAgentProvider` therefore exposes
`AgentProviderCapabilities`, and callers branch on capability rather than
assuming a shared subset. Published ACP adapters (`claude-agent-acp`,
`codex-acp`) mean the provider registry is mostly data, not per-agent protocol
code — but adapters are launched from a resolved binary, never `npx -y`.

## Consequences

- A worker that hangs is diagnosable: containment says the process lives,
  semantics says no event has arrived, presentation shows what it is stuck on —
  very often an approval prompt, which looks exactly like being busy.
- Orc Bot survives a provider that has no structured channel: it degrades to
  "presentation only, completion must be asserted by a human", explicitly, rather
  than silently guessing from text.
- Three subsystems instead of one. Worth it; the previous attempts paid for the
  alternative.
- The ACP client-side filesystem capabilities are **not** a sandbox. All four
  live agents completed a file-editing task without issuing a single `fs/read` or
  `fs/write` call. Containment is the fence (ADR-0002) plus the OS; the protocol's
  path checks constrain nobody who matters.

## Alternatives considered

**Treat the multiplexer as the supervisor.** Rejected: it is the design the
2026-08-11 archaeology explicitly warned against, and it produces an orchestrator
whose model of reality is a screen buffer.

**Skip Zellij in v0 and add it once the event stream works.** Rejected: the first
thing anyone does when a worker misbehaves is try to look at it. Removing that
makes every early debugging session worse, which is exactly the period when
debugging matters most.
