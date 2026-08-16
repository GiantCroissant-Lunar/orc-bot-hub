# ADR-0001: One application surface behind every adapter

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0008, [discussion/new-attempt-inital.md](../discussion/new-attempt-inital.md)

## Context

Orc Bot will eventually be driven from at least four directions: a shell, an
external agent over MCP, the Godot operator UI, and scheduled automation. The
previous attempts grew the UI first, which meant workflows lived where the UI
could reach them and every new entry point re-implemented a slightly different
version of the same operation.

There are two distinct protocol directions here and they must not be conflated:

| Direction | Interface |
| --- | --- |
| human / script / agent → Orc Bot | CLI, MCP |
| Orc Bot → coding agent | ACP, provider-native machine channel |
| editor → Orc Bot as an agent | ACP server, later, if it earns its place |

MCP exists to expose resources and model-invokable tools. ACP exists to
standardise the relationship between an agent and its client. They sit on
opposite sides of Orc Bot. Choosing "MCP or ACP" globally is a category error.

## Decision

Define one application command/query surface and make **every** ingress an
adapter over it. The surface is roughly:

```
SubmitTask   GetTask     ListTasks    CancelTask
GetCandidate GetCandidateDelta        AcceptCandidate  RejectCandidate
GetEvidence  SubscribeEvents
MemorySearch MemoryPropose            MemoryApprove    MemoryReject
```

Rules:

1. **CLI, MCP, and the Godot host contain zero orchestration policy.** They
   translate a request into an application command and render the result.
2. **No adapter reaches past the surface.** Not to a workspace, not to SQLite,
   not to a process. An MCP tool that edits the repository directly is a bug even
   if it produces the right diff.
3. **Authority is a property of the caller, not the transport.** Arriving through
   MCP grants nothing extra. The default external-agent profile may
   `task.submit`, `task.inspect`, `candidate.inspect`, `candidate.comment`; it may
   not `candidate.accept`, `candidate.integrate`, `slot.force-reset`, or
   `authority.release`.
4. **The CLI comes first and stays machine-first.** `stdout` is the machine-readable
   result, `stderr` is diagnostics, the exit code is stable and documented, and
   `--json` means no decoration, no ANSI, no prompts. Any agent that can run a
   shell command can drive Orc Bot on day one.

MCP then becomes a thin mapping — tools for actions, resources for state:

```
orc://tasks/<id>   orc://operations/<id>   orc://candidates/<id>
orc://candidates/<id>/delta   orc://evidence/<id>   orc://memory/<id>
```

## Consequences

- The Godot UI cannot be the place a feature lands. Anything the UI can do, the
  CLI can already do, which is also what makes the UI testable.
- Adding MCP is cheap once the commands exist, and the security story is uniform
  because authorisation happens once, at the surface.
- Every operation must be expressible without an interactive prompt. This is a
  constraint on design, and a good one.
- Screen-scraping is structurally excluded: an agent that needs orchestration
  state calls `orc_task_get`, not "type into a pane and read the output".

## Alternatives considered

**Let MCP be the primary surface and generate the CLI from it.** Rejected: MCP
requires a client runtime, so the bootstrap would depend on the thing it is meant
to help build. A shell exists everywhere.

**One universal protocol for both directions.** Rejected: ACP is for controlling
an agent session, MCP is for exposing tools, and the Orc-native surface is for
work items, candidates, leases, validation, and decisions. Collapsing them makes
all three worse — which is visible in Prime Agent, where keeping them separate is
what lets its daemon, its ACP mode, and its MCP skills coexist.
