# ADR-0012: The product is one exported Godot binary; headless is the daemon

- Status: Accepted
- Date: 2026-08-16
- **Supersedes: ADR-0011**
- Related: ADR-0001, ADR-0008, RFC-0003

## Context

ADR-0011 concluded that the Godot host should not be the CLI, and gave three
reasons. Two of them were wrong, and the owner was right to push back.

**Reason 3 (startup cost, ~396 ms against ~51 ms) was already downweighted.**
Disk and startup budgets are not scarce; a few hundred megabytes of CLI is
unremarkable in 2026.

**Reason 2 was simply incorrect.** It claimed that making the Godot host the
entry point "makes Godot a prerequisite for using Orc Bot at all" and that a CI
runner "would need a 109 MB engine binary and its export templates". That
conflates the Godot *editor* with an *exported binary*. Export templates are
needed to build the app, not to run it. The exported app is self-contained: one
executable plus its data directory, no engine install, no SDK. It is a **simpler**
deployment than a .NET console app that has to find a runtime.

**Reason 1 survives, but it is satisfiable rather than fatal.** The objection was
that a UI must not sit on the critical path for headless and scripted use. That
is true. It is also avoidable: if the *same binary* runs headless as a service
and windowed as a service-with-a-view, then the binary is on the critical path
and the UI is not.

Three things were measured on the exported host to check this is real, not
hopeful:

| Check | Result |
| --- | --- |
| stdout under `--headless --quiet` | completely clean; `Console.Out.WriteLine` writes through, `GD.Print` is suppressed |
| user arguments after `--` | `OS.GetCmdlineUserArgs()` returns `["--serve","--port","7777"]` exactly |
| exit code | 0, controllable via `GetTree().Quit(code)` |

So a Godot binary can satisfy ADR-0001's CLI contract — stdout is the result,
stderr is diagnostics, the exit code is stable, `--json` means no decoration.

The owner's framing, which this ADR adopts: the product is an app that agents
reach through MCP and a CLI, windowed or headless, driving agent CLIs through
Zellij, with memory and context. That is one deliverable, not a family of them.

## Decision

**The exported Godot binary is the product, and it is the runtime.**

```
complete-app.exe                          daemon + operator UI
complete-app.exe --headless -- --serve    daemon only; CI, servers, containers
complete-app.exe --headless --quiet -- task get <id> --json
                                          one-shot command, clean stdout
```

Headless and windowed are the **same process in two modes**, not two programs.
The UI attaches to a runtime that would have existed anyway, which is what keeps
it off the critical path and satisfies ADR-0008. ADR-0008's substance is
unchanged: the runtime outlives any single command, and every view is a view of
it.

**`orc` remains as a thin client, and is optional.** A small .NET console app
that speaks the local protocol to a running instance, and starts one headlessly
if none is running. It exists for two reasons only: a poll loop that costs ~51 ms
per call instead of ~396 ms, and the ergonomics of a short command name. It
contains no policy and no orchestration. If it were deleted tomorrow, everything
would still work through the app.

**Policy still does not live in the Godot project.** ADR-0001 is untouched:
`libs/` owns the application surface, `plugins/` owns adapters, and the Godot
project is composition plus presentation. What changed is which process hosts
them, not who owns them. A `.tscn` must never become the place a decision lives.

**MCP and the CLI are surfaces of that binary**, not separate deliverables. An
external agent points its MCP client at the running instance; a shell calls `orc`
or the binary directly. Both land on the same application commands with the same
authorisation, per ADR-0001.

## Consequences

- One thing to build, sign, version, and ship. `build/_artifacts/<version>/godot/`
  already produces it.
- The Godot main loop becomes the daemon's host loop. That is a real coupling:
  a hang in the engine is a hang in the orchestrator. Headless Godot has been
  stable here, but it is now load-bearing and worth a watchdog.
- RFC-0003's Zellij constraint now applies to this process: **it must not capture
  stdout when spawning Zellij**, or every pane it creates breaks silently.
- Running the operator UI no longer means "start a second thing" — it means
  running the same binary without `--headless`.
- A CI job runs the exported binary. No Godot install, no export templates, no
  .NET SDK.
- Web export stays impossible for this host (the engine excludes C# from Web
  entirely), so a browser UI would need a separate client speaking the protocol.

## Alternatives considered

**Keep ADR-0011: a .NET `orc` binary is the runtime, Godot is a client.**
Rejected. It is defensible on its own terms and it costs an extra deployable, an
extra protocol hop, and a second composition root to keep in step — for a
separation the two-mode binary already provides.

**Make the CLI a script that shells into the app for every command.** Rejected as
the *only* path: ~396 ms per call is fine for `task submit` and wrong for a poll
loop. Hence the thin client, as an optimisation rather than an architecture.

**Put the runtime in the Godot project itself rather than in `libs/`.** Rejected
firmly. That is the mistake both previous attempts made — workflows compiled into
the host, validation hard-coded to one window title — and it is what ADR-0001
exists to prevent. The host composes; it does not decide.
