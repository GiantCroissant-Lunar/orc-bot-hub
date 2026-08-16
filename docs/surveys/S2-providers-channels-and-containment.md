# S2 — Providers, machine channels, terminals, and process containment

Survey of what the two abandoned Orc Bot attempts found out about driving real
coding-agent CLIs: which channels worked, what Zellij needed on Windows, what
process containment actually required, and every place terminal text got
(or almost got) mistaken for semantic truth. Scope per
[RFC-0002](../rfc/0002-recover-prior-attempt-knowledge.md): attempt 1
(`prior-attempt snapshot (2026-07-27)` … `prior-attempt snapshot (2026-08-11)`) and attempt 2
(`prior-attempt snapshot (2026-08-12)`, `prior-attempt snapshot (2026-08-15)`).

## Machine channels and providers

### Zellij's own subscribe/dump-screen surface was rejected as an agent protocol before any code was written

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/adrs/0003-zellij-is-a-terminal-substrate.md:53-58`
- Confidence: high
- Bearing: ADR-0003, W6

The decision explicitly names and rejects "Treat `zellij subscribe` as the agent
protocol" as "fragile in the presence of redraws, ANSI sequences, viewport
truncation, and prompt changes," and separately rejects "Manage raw PTYs
directly" and "Write a Zellij WASM plugin now." Attempt 1 designed the
terminal/machine-channel split as policy from the start rather than
discovering it after a failed unified attempt — the split in this repo's own
ADR-0003 restates a conclusion attempt 1 had already reached and documented
its alternatives for.

### A capability-gating rule was shipped, found to overstate itself, and was corrected in place rather than silently

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/adrs/0016-pair-zellij-with-acp-machine-channel.md:7-10,52-58`
- Confidence: high
- Bearing: W5

ADR-0016 carries a dated amendment: "The capability-gating paragraph
previously read 'Every optional method is capability-gated,' which described
the intended sweep as though it were the landed channel's surface. It now
states the rule and then says which methods exist and which one is gated."
The corrected text lists exactly five implemented methods and states only
`close` actually carries a gate today, with `resume`/`fork`/`list` "recorded
from the agent's advertisement and **not yet exposed**." A capability
statement that is true in aspiration but not in the shipped surface is worse
than an absent one — it reads as safety that is not there.

### An ACP client must answer every inbound request or the agent stalls in a way indistinguishable from working

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/Acp/AcpClient.cs:25-33`
- Confidence: high
- Bearing: ADR-0003, W5

The class doc states plainly: "requests coming *in* — permission, file reads
and writes — are the half that makes an agent able to do work, and every one
of them must be answered. An unanswered inbound request is not a dropped
message, it is a stalled agent that looks exactly like a busy one." The
default branch of `HandleRequest` (same file, method-not-found case) answers
with a JSON-RPC error rather than staying silent, specifically so an
unimplemented method still unblocks the agent instead of hanging it.

### An agent's stderr must be drained or the child blocks silently once its pipe buffer fills

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/Acp/AcpClient.cs:178-183`
- Confidence: high
- Bearing: W5

Comment on the code that spawns the dedicated `ErrorLoop` task: "stderr is
redirected, so it MUST also be drained. Agents log there freely, and an
undrained pipe blocks the writer once its buffer fills — the agent stops
mid-turn with no error anywhere, which is indistinguishable from one that is
simply thinking." This is a second, independent way an agent process can look
alive while being wedged, distinct from the approval-prompt hang.

### A provider's own protocol richness forced a "declared but not admitted" state rather than trusting discovery

- Evidence: `prior-attempt (2026-08-15) orc-bot/docs/architecture.md:96`
- Confidence: high
- Bearing: ADR-0003, W5

By the end of attempt 2: "Claude Code, OpenCode, and Kilo ACP descriptors are
deliberately unavailable — even when their executables are discovered — until
each exact provider identity and advertised-mode map is independently
verified and composed." Finding a binary on `PATH` was explicitly decided to
be insufficient grounds to trust its protocol surface; only Codex's JSONL
bridge and the one live-verified `codex-acp` build were admitted. This is a
stronger position than attempt 1 ever reached and directly informs what W5's
provider registry needs to refuse by default.

### Registering a second provider meant a second transport, not a second implementation of the same interface

- Evidence: `prior-attempt (2026-08-15) orc-bot/docs/adr/0005-work-item-dags-provider-registry-and-observation.md:38`
- Confidence: high
- Bearing: W5

"The initial registry admits the already installed Codex JSONL bridge and ACP
providers only when their real executable/protocol probes succeed." Codex
was never made to speak ACP; it kept its own JSONL bridge as a first-class
citizen of the registry rather than being forced through an ACP adapter,
confirming a uniform wire format could not be assumed even for two providers
running in the same build.

### An unattended auto-approve permission policy from the other implementation line was named as something that must not be copied

- Evidence: `prior-attempt (2026-08-15) orc-bot/docs/adr/0005-work-item-dags-provider-registry-and-observation.md:12,40`
- Confidence: high
- Bearing: ADR-0003, W5

ADR-0005's context section states the sibling line's "permission policy
auto-approves" as one of the things "that must not be copied," and the
decision text repeats it as a rule: "No provider may inherit the other
implementation's unattended auto-approve policy." One implementation line
built a working multi-provider registry by defaulting to unattended approval;
the successor line evaluated it directly and rejected it as a design choice,
not merely as an unfinished feature.

## Zellij on Windows

### A zellij session spawned from a process with redirected stdout silently breaks every pane it creates

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-08-zellij-windows-smoke.md:104-113`
- Confidence: high
- Bearing: W6

"The first client spawns the zellij server, and the server spawns pane
processes through a pseudo-console. Launched from a process whose stdout is a
pipe — a test host, a CI step, an agent harness — the pane processes end up on
the launcher's console instead: they read EOF and exit immediately, panes
report `exited: true, exit_status: 0` with a blank viewport... Every symptom
points at the pane command rather than at the launcher." The fix was to
create the session with `UseShellExecute` and a hidden window rather than
redirected pipes, confirmed live in `ZellijCli.RunUncaptured`
(`prior-attempt (2026-08-12) Substrate/ZellijCli.cs:144-186`, comment: "Redirecting the
first client's output silently defeats the ConPTY attach... a capturing
caller blocks until timeout and healthy code looks broken").

### Git Bash's exported `$SHELL` cannot be used as zellij's default pane shell on native Windows

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-08-zellij-windows-smoke.md:115-119`
- Confidence: high
- Bearing: W6

"Git Bash exports `/bin/bash.exe`, which native Windows cannot resolve. The
session's default pane dies, the last pane closing ends the session, and
`list-sessions` reports success a moment before the session disappears." The
adapter always passes `options --default-shell` explicitly rather than
trusting the ambient shell environment variable.

### zellij's own "no sessions" state is a non-zero exit that must be pattern-matched, not treated as a generic failure

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-08-zellij-windows-smoke.md:121-125`
- Confidence: high
- Bearing: W6

"`list-sessions` exits 1 with `No active zellij sessions found.` on stderr.
That is the normal state before the first session, so it is recognised by
message; any other failure still throws. Collapsing all non-zero exits into
'no sessions' would make reconciliation read a broken CLI as 'the session is
gone' and drop live bindings." Confirmed live in attempt 2's rewrite
(`prior-attempt (2026-08-12) Substrate/ZellijTerminalSubstrate.cs:66-78`), which reads
`Exists` off `list-sessions --short` and treats a non-zero exit as "not
found" only there.

### zellij `run --cwd` was accepted by the CLI but the pane still started in the server's inherited directory, not the requested one

- Evidence: `prior-attempt (2026-08-11) orc-bot/project/bundles/execution/OrcBot.Execution.Zellij/ZellijWorkingDirectoryGuard.cs:11-23`
- Confidence: high
- Bearing: W6

"zellij 0.44.3 on Windows accepts `run --cwd` and then starts the pane's
process in the zellij *server's* inherited working directory (observed
2026-08-10: a dispatch declaring another checkout ran its agent here,
produced an empty delta, and failed)... zellij offers no query for a pane's
actual directory, so the launch cannot verify it after the fact." The fix
does not trust `--cwd` at all: it rewrites the pane's command line into a
shell step (`cd` then `exec`/`ProcessStartInfo`) so the directory is
established *inside* the pane process itself, and still passes `--cwd`
alongside "for zellij's own bookkeeping wherever it is honored." This is a
live contradiction of a later, unverified claim recorded elsewhere that
`--cwd` works on 0.44.3 — see Unverified recollections.

### Windows PowerShell strips embedded quotes when it serializes a native command's own argv, corrupting a JSON argument mid-flight

- Evidence: `prior-attempt (2026-08-11) orc-bot/project/bundles/execution/OrcBot.Execution.Zellij/ZellijWorkingDirectoryGuard.cs:34-43` (root-caused in `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-11-pane-argv-fidelity.md:1-7`)
- Confidence: high
- Bearing: W6

"Windows PowerShell serializes the arguments of a native command itself and
drops every embedded double quote while doing so (observed 2026-08-11: a JSON
argument arrived at the completion bridge with all its quotes gone, so the
bridge refused it as malformed and the pane exited 64 before the agent ran)."
The note is blunt about why the obvious fix does not work: "Decoding an
argument safely is therefore not enough — it must also reach the child
unchanged." The eventual fix builds the Windows argv-quoted command line by
hand and starts the child via `ProcessStartInfo` instead of PowerShell's call
operator — reimplemented identically in attempt 2's `ZellijCli.BuildCommandLine`
(`prior-attempt (2026-08-12) Substrate/ZellijCli.cs:188-236`).

### A killed zellij session lingers in an "EXITED" state that silently resurrects and inherits stale panes/cwd/size if not explicitly deleted

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/Substrate/ZellijTerminalSubstrate.cs:29-58`
- Confidence: high
- Bearing: W6

"A killed session lingers in an EXITED state and blocks reuse of the name
until it is explicitly deleted — and the delete is refused while the kill is
still settling. That failure is invisible if the results are ignored: `attach
-b` succeeds against a session that already exists by simply joining it, so
the run silently inherits the previous run's panes, its viewport size, and a
shell still sitting in whatever directory that run used." `EnsureSession`
polls `kill-session` + `delete-session` up to 10 times with a 200ms sleep and
returns failure rather than silently reusing a name it could not clear.

### A detached zellij session has no client and defaults to roughly 46 columns, which is destructive to full-screen TUIs — the only fix is to briefly attach a sized console and drop it

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/Substrate/ZellijTerminalSubstrate.cs:80-99`
- Confidence: high
- Bearing: W6

"A session created with `attach -b` has no client, so its viewport defaults
to roughly 46 columns — and each pane split halves that again. Children then
see a ~23-column terminal, which mangles every TUI and is small enough to
crash some of them outright. The viewport is client-driven and there is no
CLI to set it." `SizeSession` works around this by shelling out to
`cmd /c "mode con: cols=... lines=... & zellij.exe attach <session>"` and
killing that client after a short linger — the size persists on the session
after the client that set it is gone.

### Cramped pane geometry crashes an agent TUI outright rather than degrading, so each agent gets its own tab/session, never a shared split

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/Substrate/ZellijTerminalSubstrate.cs:101-108`
- Confidence: high
- Bearing: W6

Comment directly on `OpenPane`: "Agent TUIs are given their own tab rather
than a split: a pane squeezed into an already-crowded tab can hand the child
a TTY small enough to crash it outright instead of degrading." This is a
design rule baked into the terminal substrate itself, not just an
observation in a note — every agent pane call goes through this method.

### `zellij action dump-screen` silently collapses a full-screen TUI's entire viewport onto one row; `subscribe --format json` is the only reliable read

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/Substrate/ZellijTerminalSubstrate.cs:158-193`
- Confidence: high
- Bearing: W6, ADR-0003

`CaptureViewport`'s comment: "`action dump-screen` is NOT usable here: for a
full-screen TUI it collapses the whole screen onto a single row, destroying
the grid. (It is fine for line-oriented output, which is what makes the bug
easy to miss.) `subscribe` emits an NDJSON frame carrying the viewport as a
row array." The method starts a `subscribe` process, reads exactly one line
via `ZellijCli.ReadFirstLine` (`prior-attempt (2026-08-12) Substrate/ZellijCli.cs:101-105`,
"`subscribe` never exits on its own; one NDJSON frame is a complete viewport
snapshot, which is all a poll needs"), then kills the process — because the
command has no other way to terminate.

### Attempt 2's later Zellij rewrite stopped re-deriving its process handle from parsed PowerShell output

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/execution/zellij/ZellijTerminalSessionProvider.cs:161-165` (commit `621fec1` "fix: stabilize background zellij sessions", confirmed present in this snapshot's `git log` for the file)
- Confidence: medium
- Bearing: W6

By this snapshot, session creation launches `zellij.exe` directly through
`ProcessStartInfo`/`Process.Start` and keeps the resulting `Process` object,
rather than shelling through `powershell.exe Start-Process -PassThru` and
parsing a PID back out of captured stdout to re-acquire the process later.
Re-deriving a process handle from parsed text is exactly the kind of
terminal-output-as-truth pattern ADR-0003 warns against — this is a second,
distinct instance of the same lesson, applied to the launcher's own control
path rather than to the agent it launches. Confidence is medium: only the
resulting code was read directly, not a diff against the pre-fix revision.

### A zero exit code from `zellij action list-panes` does not prove the session's own bootstrap pane exists yet

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/execution/zellij/ZellijTerminalSessionProvider.cs:153-158,194-221` (commit `17f1c83` "fix: verify concurrent zellij session hosts")
- Confidence: high
- Bearing: W6, ADR-0003

`WaitForSessionReadyAsync`'s readiness loop does not stop at `ExitCode == 0`
from `list-panes --json`; it additionally parses the JSON pane array via
`HasRunningSessionHostPane` and requires a pane specifically titled
`"orc-bot-session-host"` (the name baked into the KDL layout at session
creation) to be present and not `exited`. A command exiting cleanly is
process-success, not the semantic fact — "the pane I need is actually there
and alive" — the caller needs. This is the same distinction ADR-0003 draws
for agent completion, independently re-discovered and reapplied here to
zellij's own CLI.

### A helper binary packaged next to Godot's published managed assemblies silently binds the host's JSON library version unless deliberately isolated

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/execution/zellij-probe/Program.cs:98-101`
- Confidence: high
- Bearing: W6

Comment directly on the probe's hand-written serializer: "The probe is
copied next to Godot's published managed assemblies. It must not bind to the
host application's System.Text.Json version because it also runs as an
independent .NET 8 process. This fixed-schema encoder keeps the bootstrap
receipt BCL-only and immune to that published load-context collision." A
standalone helper process shipped alongside a Godot-exported host is not
isolated from the host's publish output just because it runs as its own
process — colocation in the same output directory was enough to cause a
version collision. Worth remembering for any future helper binary shipped
inside `build/_artifacts/<version>/`.

## Process containment

### An operation dispatched one commit before Job Object containment landed can never be proven cancelled, because the containment proof is written at process start and there is no retroactive path to it

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/adrs/0024-indeterminate-retirement-of-uncontainable-operations.md:9-22`
- Confidence: high
- Bearing: W4, ADR-0003

"The proof is a durable attestation the bridge writes as it starts its child,
so an operation accepted by a build that predates the containment provider
has no attestation and never will — the process that would have written one
is gone." The two escape hatches considered were both rejected as unsound:
"Editing the control-plane database destroys the audit the operation is
evidence for... Recording `Cancelled` claims a containment proof nobody
obtained." The resolution added a third terminal outcome, `Abandoned`
(lines 36-46), that releases the held resource lease without ever claiming
the stronger fact of proven termination. This is a durable design
consequence of building containment retroactively rather than from day one —
directly relevant to sequencing W4 before anything that can hold a lease.

### Closing a zellij pane killed the completion bridge but left its OpenCode child process alive, requiring manual out-of-band termination

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-11-rfc0007-c5a-rust-lifecycle.md:24-28`
- Confidence: high
- Bearing: W4, ADR-0003

"Closing the pane terminated the completion bridge but left its OpenCode
child (PID `45564`) alive. The parent terminated that exact orphan and
stopped the resident lane. This is an Orc Bot ownership defect: pane/bridge
termination must terminate the admitted child process tree." This is the
concrete, dated incident (not a hypothetical) that ADR-0003's stated context
line — "a live experiment found child processes surviving the closure of
their terminal pane" — is citing.

### The Windows Job Object repair assigns the bridge process to a private, non-inheritable, kill-on-close job before it starts its child, so kernel handle closure — not cooperative cleanup — is what kills the whole tree

- Evidence: `prior-attempt (2026-08-11) orc-bot/project/bundles/development/OrcBot.Development.Process/WindowsJobObjectProcessTree.cs:46-111`
- Confidence: high
- Bearing: W4

`EstablishForCurrentProcess` creates an unnamed job (`CreateJobObjectW`),
sets `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, and calls
`AssignProcessToJobObject` on the bridge's own current process *before* it
launches the admitted child, so the child inherits job membership at spawn.
The doc comment states the invariant plainly: "The handle is intentionally
rooted until process exit: disposing the last handle is the kill boundary
and would also terminate the bridge, which is itself assigned to this
private unnamed job." No cooperative signal (SIGTERM-equivalent, cancellation
token, etc.) is part of the kill path at all — the mechanism is a kernel
guarantee, which is exactly what made it survive an external pane close in
the first place (see the incident finding above).

### Recovery proof uses exact PID + process-start-time identity, specifically to defeat PID reuse, and polls for termination rather than trusting one check

- Evidence: `prior-attempt (2026-08-11) orc-bot/project/bundles/development/OrcBot.Development.Process/WindowsJobObjectProcessTree.cs:213-214,296-409`
- Confidence: high
- Bearing: W4

`ProcessIdentity` is `(ProcessId, StartedAtUtc)`, and `ExactProcessState`
(lines 411-437) treats a PID whose live `StartTime` doesn't match the
recorded one as already-gone rather than as a false negative — the reused-PID
case is handled by treating it as absence, not as a match. The recovery
probe (`ProbeAsync`, lines 296-409) refuses to call the tree dead on a single
observation: it polls the admitted child on a 25ms interval for up to 2
seconds after confirming the bridge itself is gone, and returns "Unproven"
rather than "Terminated" if the deadline elapses with the child still live —
an explicit refusal to guess under ambiguity.

### A quarantined operation's leases could not be released through the operator surface at all, because the Cancel selector filtered out exactly the state the stuck operation was in

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-11-rfc0007-c5a-rust-lifecycle.md:71-76`
- Confidence: high
- Bearing: W4

"After restart, operation `op-3b558fe151cc59b6abfc80acd3c2c940` was
`Quarantined`... The control-center Cancel selector filtered out
`Quarantined`, leaving no operator path to terminalize the invocation or
reopen the repository lane." A UI filter meant to hide operations that
weren't actionable had accidentally hidden the one operation an operator most
needed to act on — the exclusive lease it held then blocked every later
dispatch on the same profile/capability until the ADR-0024 repair shipped.

### Attempt 2's containment goes further than attempt 1's: processes are created suspended and admitted to a nested Job Object before being resumed, closing the race window between spawn and admission

- Evidence: `prior-attempt (2026-08-15) orc-bot/docs/architecture.md:104`; confirmed at the code level in `prior-attempt (2026-08-15) orc-bot/project/execution/windows-process/WindowsJobObjectProcessTree.cs:84-115,129` (`CreateProcessW` with `CREATE_SUSPENDED` → `AssignProcessToJobObject` → `ResumeThread`, with `AdmittedBeforeFirstInstruction: true` recorded as an explicit, checked field on the attestation itself)
- Confidence: high
- Bearing: W4

"Zellij session roots are created suspended, admitted to allocation-private
nested jobs, and only then resumed. Each agent bridge establishes its own
nested job before starting Codex or an ACP provider... Closing a pane,
disposing a session, or abruptly terminating the operator therefore invokes a
kernel process-tree boundary rather than relying on cooperative cleanup." This
is a direct refinement over attempt 1's mechanism (which assigned the job to
the *bridge* process before it spawned its child, closing the same race for
one hop but not composing it across nested session→bridge→provider trees).
The same paragraph also states plainly: "No non-Windows containment provider
is currently composed, so agent execution is unavailable there instead of
making a cross-platform claim" — containment gaps fail closed rather than
silently degrading on other platforms.

### Job Object admission requires a direct, unredirected process launch — structurally incompatible with a piped machine channel on the same process

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/execution/windows-process/WindowsJobObjectProcessTree.cs:66,348-358`; the same constraint's other side is `project\agents\OrcBot.AgentExecution.Adapters\CodexJsonlMachineChannel.cs:44,311-334`
- Confidence: medium
- Bearing: W4, W5

`WindowsJobObjectProcessTree.Start` calls `ValidateUnredirectedStart` before
doing anything else, and it throws if `UseShellExecute` or any of
`RedirectStandardInput/Output/Error` is set: "Suspended Job Object admission
requires a direct, unredirected process launch." That is exactly the shape
`CodexJsonlMachineChannel` needs for its piped stdin/stdout/stderr JSONL
channel, so the two mechanisms cannot compose on the same process — one hop
can be Job-Object-contained or machine-channel-piped, not both at once. The
same channel file separately hard-denylists provider arguments that could
alter "the adapter's sandbox, channel, or workspace authority" (`--sandbox`,
`--cd`, `--dangerously-bypass-approvals-and-sandbox`, `--json`, and others,
`ValidateProviderArguments`), showing the same boundary was also enforced by
convention wherever the OS mechanism could not reach it directly. Confidence
is medium because the causal link between the redirection constraint and the
final file-bridge architecture (evidence written to `process-tree.json` on
disk rather than passed over a pipe) is inferred from these two constraints,
not stated outright in a comment.

### Process-containment evidence crossing a filesystem reparse point is explicitly rejected, not silently followed

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/agents/OrcBot.AgentExecution.Adapters/BridgeProcessContainment.cs:28,130-152`
- Confidence: high
- Bearing: W4, ADR-0003

Before trusting a written `process-tree.json` attestation, `EnsureNoReparsePoint`
walks every ancestor directory from the evidence file up to the configured
state root and throws `InvalidDataException` ("...crosses reparse point...")
if any segment has `FileAttributes.ReparsePoint` set. This guards against the
evidence file, or its directory chain, being swapped out via a symlink or
junction between the moment the bridge writes it and the moment the verifier
reads it — a narrow but concrete failure mode that only becomes visible once
completion evidence is trusted from a file on disk instead of an in-process
channel.

## Terminal text (and transport signals) mistaken for truth

### Attempt 2's own ADR-0003 is explicitly a correction, and names exactly the failure mode this repo's ADR-0003 restates

- Evidence: `prior-attempt (2026-08-15) orc-bot/docs/adr/0003-zellij-terminal-substrate-and-machine-channel.md:1-6,39-46`
- Confidence: high
- Bearing: ADR-0003

Its status line reads "Accepted (corrected 2026-08-12)" with "Supersedes:
acceptance based on fake channels, pane exit, viewport text, or status-only
UI." The decision body states outright that "Pane state, viewport text,
terminal prose, and process exit cannot grant permission, declare semantic
completion, publish an artifact, or settle an operation," and its acceptance
checks require proving as a test criterion that "pane exit or
completion-looking viewport text cannot settle success." This is dated the
same day attempt 2 restarted, meaning the lesson was learned (or re-learned)
essentially immediately — this document is the closest thing to a
primary-source precedent for the current repo's own ADR-0003.

### Codex's own process exit code is demoted to diagnostic text inside a typed failure event, never trusted as the verdict by itself

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/agents/OrcBot.AgentExecution.Adapters/CodexJsonlMachineChannel.cs:207-223`
- Confidence: high
- Bearing: ADR-0003, W5

After the codex process exits, `ReadEventsAsync` checks whether a terminal
JSONL event (`turn.completed`, `turn.failed`, `error`) was ever seen. If not,
it does not report the raw exit code as the result — it emits
`AgentFailed("codex-exit-without-completion", $"Codex exited with code
{process.ExitCode}: {stderr}")`, folding the exit code into the *message* of
a typed failure rather than letting it stand as the verdict on its own. This
is the same "process exit is evidence about a process, not about an attempt"
principle ADR-0003 states, applied at the machine-channel code level rather
than in a design document.

### An exit-status-equals-success reading of a dispatch was shipped, then explicitly retracted as insufficient once source writes were in scope

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-09-configured-agent-cli-dispatch.md:159-167`
- Confidence: high
- Bearing: ADR-0003, W4, W5

The note's own "What this does not prove" section carries a dated
retraction: "**Superseded 2026-08-10.** An exit status is now transport
evidence only. A run declaring `SourceWrite`, or a binding declaring a typed
completion source, requires a provider-neutral typed receipt plus a source
delta... and fails closed otherwise... The artifacts above were produced
under the earlier rule and are kept as a record of that run; **they do not
describe current behaviour**." This is a first-party admission that the
project itself initially treated a clean process exit as sufficient, caught
it, and left the earlier proof artifact in place labeled as obsolete rather
than deleting it — a useful pattern for how this repo's own docs/surveys
should age.

### Two operations with a clean transport exit and a captured (even empty) source delta were still correctly recorded `Failed`, because no typed completion receipt existed

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-11-bridge-digest-readmission.md:162-176`
- Confidence: high
- Bearing: ADR-0003, W5

Operation `op-18225aa4b3d62bbc066576bdd6840c7a` "durably captured the
uncommitted P0 source delta... Orc Bot nevertheless recorded the operation as
`Failed` because the profile's declared `standard.completion.receipt-document`
source emitted no typed completion receipt... the clean transport exit and
captured delta are not a typed statement that the requested work completed."
A second operation (`op-9cb5fa9ed3e58e7fa72eaeefea4fa2bb`) reproduced the
identical failure with Claude Code exiting 0 and an honest empty delta. Both
rows were left as `Failed` rather than reinterpreted after the underlying bug
was fixed — the historical record was treated as immutable evidence, not as
something to retcon once the cause was understood.

### The root cause of both receipt-less failures was a launch/profile mismatch: Claude Code was started in plain-text output mode while the profile demanded a typed receipt only a structured transport could produce

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-11-bridge-digest-readmission.md:186-192`
- Confidence: high
- Bearing: W5

"The architectural cause was the profile/launch mismatch: the Claude binding
selected a typed receipt source but launched `--output-format text`, declared
no completion bridge, and used one shared workspace-relative receipt path. No
trusted host component therefore had either the structured Claude transport
evidence or the authority to produce the document; satisfying the profile
would have required the model to author its own success receipt." This is a
config-time defect that guaranteed every Claude-driven attempt would fail
regardless of what the model actually did — worth flagging because it looks,
from the outside, like a provider capability gap rather than a launch-flag
bug.

### An agent wrote its own prose "proof of completion" directly into the docs tree, which is exactly the shape of evidence the project's own ADRs elsewhere reject as untrustworthy

- Evidence: `prior-attempt (2026-08-11) orc-bot/docs/notes/2026-08-10-orcbot-opencode-live-proof.md:1-19`
- Confidence: medium
- Bearing: ADR-0003, none for RFC-0001 directly

The file is titled "Live Proof Note," authored and committed by OpenCode
itself ("**Author:** OpenCode (autonomous agent run)"), and its own listed
"Evidence" is `git status --porcelain` / `git diff --stat` run by the same
agent that is the subject of the claim. Nothing here is a forged claim — the
change really did land — but the artifact is model-authored prose asserting
its own success, filed next to the same repository's ADR-0003 language that
"a pane printing 'Build succeeded!' is a rendering of bytes, not a claim Orc
Bot can act on." Confidence is medium because this is one file, not a
pattern observed repeatedly, and no downstream system in either attempt is
shown treating this specific note as authoritative.

## Unverified recollections

- A retest of `zellij run --cwd` on 0.44.3 (session dated 2026-08-11, in this
  agent's own memory, not located in any D: snapshot file) concluded `--cwd`
  *is* honored on Windows and that `ZellijWorkingDirectoryGuard`-style
  workarounds might be redundant. This directly contradicts the dated,
  in-tree note above (`docs/notes/2026-08-11-pane-argv-fidelity.md` and
  `ZellijWorkingDirectoryGuard.cs`'s own remarks, both observed 2026-08-10/11)
  and no snapshot file recording the later retest could be found. Do not
  drop the pane-internal `cd` workaround on the strength of the retest alone;
  re-verify against a pinned zellij build before relying on `--cwd` directly.
- opencode and kilo were separately observed (again only in this agent's own
  memory, not evidenced in any D: snapshot — the observation concerns a
  dispatch into `git worktree` checkouts, which live outside the
  `agent-projects\orc-bot` folders the snapshots capture) to resolve project
  root through a linked worktree's `.git` gitdir pointer and edit the main
  checkout instead of the worktree they were given, while codex and kiro-cli
  stayed put. If true, this is a containment-relevant gap no `IAgentMachineChannel`
  capability flag currently models, but it could not be sourced to a citable
  file and is omitted from the findings above.
