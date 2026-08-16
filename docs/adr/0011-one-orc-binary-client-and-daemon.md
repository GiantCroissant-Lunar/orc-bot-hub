# ADR-0011: One `orc` binary is both client and daemon; the Godot host is a third client

- Status: **Superseded by [ADR-0012](0012-the-product-is-one-exported-godot-binary.md)**
- Date: 2026-08-16
- Refines: ADR-0008
- Related: ADR-0001, ADR-0005

## Context

ADR-0008 established that the runtime is its own process and every UI is a
client. RFC-0001 turned that into two host projects, `orc-runtime` and `orc-cli`,
which prompted two fair questions: what is each of them actually for, and — since
Godot has `--headless` — could the Godot host simply *be* the CLI and remove one
of them?

### What the two projects are for

`orc-runtime` exists because of a timing mismatch. `orc task submit` returns in
milliseconds; the worker it started runs for twenty minutes. Something has to
outlive the command: hold the machine channel open, notice the typed completion
event, freeze the candidate, keep the fence, and still be there when a second
shell asks `orc task get`. If that something is the command's own process, then
closing the shell kills the attempt and `orc terminal attach` has nothing to
attach to. So the runtime owns lifecycle supervision, SQLite, work topology,
source authority, candidate authority, tool-authority slots, and the provider
gateway.

`orc-cli` exists because ADR-0001 requires a machine-first surface — stdout is
the result, stderr is diagnostics, exit codes are stable, `--json` means no
decoration and no prompts — and because that surface must be usable by any agent
that can run a shell command, on a machine that may have no GUI at all.

### Could the Godot host be the CLI?

Worth taking seriously: it would mean one binary, and the CLI and UI could not
drift because they would share a composition root. So it was measured rather than
argued about.

**Startup, five warm invocations each, this machine:**

| | per invocation |
| --- | --- |
| `complete-app --headless --quiet --quit` | **~396 ms** |
| published .NET console app | **~51 ms** |

**stdout cleanliness.** Without `--quiet`, Godot writes its banner and rendering
driver line to stdout unconditionally — `Godot Engine v4.7.1.stable.mono…` and
`D3D12 12_0 - Forward+ - Using Device #0…` — which breaks `--json` on the first
byte. With `--quiet`, stdout is completely clean, but `GD.Print` is suppressed
along with everything else. `System.Console.Out.WriteLine` still writes through,
verified: `--headless --quiet` emitted exactly `{"probe":"console-stdout"}` and
nothing else.

So the two objections that sound fatal are not. It is technically workable.

## Decision

**The Godot host is not the CLI.** Three reasons, in order of weight:

1. **It inverts ADR-0008.** If `orc` *is* the Godot host, the Godot host is on
   the critical path for every headless, scripted, and CI invocation, and the
   engine becomes a dependency of the control plane. ADR-0008 exists precisely to
   prevent a UI from becoming durable authority; making the UI the only entry
   point is a stronger version of the same mistake.
2. **It makes Godot a prerequisite for using Orc Bot at all.** A CI runner, a
   container, or a headless server would need a 109 MB engine binary and its
   export templates to run `orc task get`.
3. **~400 ms versus ~51 ms.** Eightfold, and it compounds: an agent polling task
   state during a twenty-minute attempt makes hundreds of these calls. This is
   the weakest of the three reasons and would not decide it alone.

Godot's headless mode keeps a real and different job: **running the host to check
the host** (RFC-0001 W12), and driving the export. That is the host under test,
not the control plane.

**`orc-runtime` and `orc-cli` collapse into one project, `orc`, with two roles.**

```
orc serve                 # runs the daemon in the foreground
orc task submit ...       # client; auto-starts the daemon if it is not running
orc task get ... --json
```

They remain two *processes* — ADR-0008 is unchanged — but one project, one
binary, one composition root, one version. The client auto-starts the daemon on
first use and connects, the way `docker` starts nothing and `dotnet` starts its
build server. This removes a failure mode worth removing: "did you start the
runtime?" is a question no user should ever have to answer, and a stale
runtime/CLI version pair is a class of bug that cannot occur when they ship as
one file.

The daemon's own logic stays in `libs/`, so `orc` is thin in both roles and the
Godot host composes the same libraries without going through the CLI.

## Consequences

- RFC-0001's W8 and W9 target one project. The work does not shrink — the
  process boundary, the protocol, the cursors, and the recovery are all still
  needed — but the packaging does.
- Auto-start needs care: concurrent clients must not race to spawn two daemons,
  and a client must be able to tell "starting" from "unreachable". A lock file
  plus a bounded connect-retry is the expected shape.
- `orc serve` stays explicitly available. Auto-start is a convenience, and
  anything that only works via auto-start is a bug.
- The Godot host never becomes the way to script Orc Bot, which keeps CI and
  container use open.
- If a future host needs the CLI's exact behaviour, it calls `orc`, rather than
  the CLI being reimplemented inside it.

## Alternatives considered

**Keep `orc-runtime` and `orc-cli` as separate projects.** Rejected as
packaging, not architecture. Two binaries that must be version-matched, deployed
together, and started in the right order, in exchange for a separation that the
process boundary already provides.

**Make the CLI a thin script over the Godot host's headless mode.** Rejected —
see Decision. It is technically workable and architecturally backwards.

**Have the CLI do everything in-process against shared SQLite, with no daemon.**
Already rejected in ADR-0008: nothing supervises the machine channel between
invocations, so a worker's completion event arrives with no listener.
