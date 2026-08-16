# S4 — Godot host, validation, export pipeline, and operator UI

Survey of two abandoned Orc Bot attempts for evidence about the engine side
that produced a green result and a broken product. Bears on RFC-0001 work item
W12, ADR-0004, ADR-0005.

Snapshots inspected (read-only):

- Attempt 1: `prior-attempt (2026-08-11) orc-bot` (commit `b88054c`)
- Attempt 2: `prior-attempt (2026-08-12) orc-bot` (commit `00dea65`)
  and `prior-attempt (2026-08-15) orc-bot` (final state, no git)

## Findings

### The windowed validation protocol was hard-coded to one window title, one project path, and one export preset

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/validation/godot/OrcBot.Validation.Godot.Windows/WindowsGodotValidationProvider.cs:11-16, 83, 231`
- Evidence: `prior-attempt (2026-08-15) orc-bot/project/validation/godot/OrcBot.Validation.Godot.Windows/GodotValidationOptions.cs:3-14`
- Confidence: high
- Bearing: W12, ADR-0004

The validation provider accepted a `GodotValidationOptions` record carrying
`GodotExecutable`, `GodotProjectRelativePath`, `ExportPreset`,
`ExportedExecutableName`, and `ExpectedWindowTitle` as required strings. The
provider's `ObserveWindowAsync` matched the process window title against
`_options.ExpectedWindowTitle` using `StringComparison.Ordinal` (line 231), and
the export step invoked `--export-release` with `_options.ExportPreset` (line
83). The host's `HostComposition.CreateOperatorApplication()` (line 55-56) passed
`Path.Combine("project", "hosts", "complete-app")` as the project relative path,
`"Windows Desktop"` as the preset, and `"Orc Bot"` as the title. The design
constants `DesignWidth = 2560` and `DesignHeight = 1600` (lines 11-12) were used
to scale synthetic click coordinates. Adding a second project type would require
a second `GodotValidationOptions` instance and a second preset in
`export_presets.cfg`; there is no registry, no discovery, and no fallback. The
`ExpectedWindowTitle` match is exact and case-sensitive, so a window titled
"Orc Bot — Debug" would fail validation silently.

### The exported application set its window title in `_Ready`, not in `project.godot`, so validation matched a runtime string

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/hosts/complete-app/scripts/Main.cs:94`
- Evidence: `prior-attempt (2026-08-15) orc-bot/project/hosts/complete-app/project.godot:13`
- Confidence: high
- Bearing: W12

`Main.cs` line 94 sets `GetWindow().Title = "Orc Bot"` inside `_Ready()`, while
`project.godot` line 13 declares `config/name="Orc Bot"`. The validation
provider's `ObserveWindowAsync` reads `process.MainWindowTitle` (line 231),
which is the OS-level window title set by the engine after `_Ready` runs. If
`_Ready` never executes (e.g., the managed assembly is missing — see below),
the window title defaults to the `config/name` from `project.godot` or the
engine default, and the validation provider would time out waiting for the
expected title. This means the title check indirectly proves that managed code
ran, but only by accident — a different `config/name` would break validation
without a diagnostic.

### A missing `.sln` next to `project.godot` ships an app with no managed assemblies, and the export succeeds

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/hosts/complete-app/complete-app.sln` (exists, 19 lines)
- Evidence: `prior-attempt (2026-08-11) orc-bot/project/hosts/complete-app/complete-app.sln` (exists, different GUID)
- Evidence: `prior-attempt (2026-08-15) orc-bot/AGENTS.md:66-69`
- Confidence: high
- Bearing: W12, ADR-0005

The current repository's `AGENTS.md` lines 66-69 state: "Two solutions exist on
purpose: `project/OrcBot.sln` is the developer/CI solution, and
`project/hosts/complete-app/complete-app.sln` is the one Godot itself requires
next to `project.godot` — without it the export succeeds and ships an app with
no managed assemblies." This is a corrective finding from the prior attempts:
Godot's `--headless --export-release` does not fail when the `.sln` is absent or
when the C# build produces no assemblies. The export exits 0 and produces an
executable that runs but never calls `_Ready` on any C# script, because the
managed assembly was never compiled or embedded. The 20260815 attempt carried
both `complete-app.csproj` and `complete-app.sln` next to `project.godot`; the
20260812 attempt had no `.sln` at all (only a `.csproj`), and its export output
(`build/export.out`) shows only Godot initialization with no MSBuild invocation.

### The 20260812 export failed with an invalid preset name, and the screenshot was claimed from a binary that was never produced

- Evidence: `prior-attempt (2026-08-12) orc-bot/build/export.err:1`
- Evidence: `prior-attempt (2026-08-12) orc-bot/docs/screenshots/stage9-work-graph.png` (86,580 bytes, exists)
- Evidence: `prior-attempt (2026-08-15) orc-bot/docs/research/2026-08-12/experiment-20260812-lineage.md:101`
- Confidence: high
- Bearing: W12, ADR-0005

`build/export.err` line 1 reads: `ERROR: Invalid export preset name: Windows.`
The only preset in `export_presets.cfg` is `"Windows Desktop"`. The
`export.out` file contains only Godot's initialization and class registration
steps — no export step ran. The lineage report (line 101) states: "Main's
`build/export.err` says `Windows` is not a valid preset and names
`Windows Desktop`; `build/export.out` contains Godot initialization only. The
roadmap claims `docs/screenshots/stage9-work-graph.png` came from an exported
binary." The screenshot exists but the export that produced it either used a
different command or was from an editor run, not a headless export. This is the
specific failure mode where a green-looking artifact (a screenshot) coexists
with a failed export log.

### Synthetic input drove the UI by PostMessage WM_MOUSEMOVE/DOWN/UP at hard-coded design coordinates, not by a control endpoint

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/validation/godot/OrcBot.Validation.Godot.Windows/WindowsGodotValidationProvider.cs:306-325`
- Confidence: high
- Bearing: W12, ADR-0004

`ClickWindow` (line 306) takes a window handle and design-space `(x, y)`,
scales them by the actual client rect divided by `DesignWidth`/`DesignHeight`
(lines 314-316), and posts `WM_MOUSEMOVE`, `WM_LBUTTONDOWN`, `WM_LBUTTONUP`
via `PostMessage` (lines 319-321). The validation provider calls
`ClickWindow(application.MainWindowHandle, 460, 640)` (line 128) — a single
hard-coded coordinate intended to hit the "Refresh" button. There is no
control-level endpoint, no accessibility tree traversal, and no verification
that the click landed on the intended control. If the UI layout changes, the
click hits a different control and the test reports success for the wrong
action. The live smoke test (`RunExportedUiAsync`, Program.cs line 1437-1438)
uses the same approach with different coordinates: `EnterText(handle, 220, 335, ...)`
and `Click(handle, 260, 505)`. These coordinates are relative to the 2560x1600
design surface and break if the window is smaller or the layout shifts.

### The nonce-bound window observation protocol was the only thing that distinguished "the UI displayed something" from "the UI did the right thing"

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/hosts/complete-app/scripts/WindowValidationProtocol.cs:15-16, 40-50`
- Evidence: `prior-attempt (2026-08-15) orc-bot/project/tests/README.md:150-154`
- Confidence: high
- Bearing: W12, ADR-0003

`WindowValidationProtocol.WriteAsync` reads two environment variables:
`ORCBOT_WINDOW_VALIDATION_PATH` and `ORCBOT_WINDOW_VALIDATION_NONCE` (lines 15-16).
When both are set, it writes a JSON observation file with a schema version,
nonce, stage (`"ready"` or `"refreshed"`), and ~30 fields covering workflow
count, run count, capabilities, roster, loadout, native sessions, usage, and
Orca observation (lines 54-94). The validation provider generates a random
nonce, sets both env vars on the exported process (lines 109-110), and then
polls the observation file until the nonce and stage match (lines 271-304). The
test README (lines 150-154) states: "A matching title, window size, or process
survival interval alone cannot produce a successful validation receipt." This
is the direct counter to the "green result, broken product" pattern: without
the nonce-bound observation, a window that opens and stays responsive would
pass validation even if `_Ready` never ran or the Refresh button did nothing.

### The live smoke test reported success while driving the UI entirely through synthetic coordinates and polling SQLite

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/tests/live/OrcBot.AgentExecution.LiveSmoke/Program.cs:1437-1438, 1449-1450, 1564-1569`
- Confidence: high
- Bearing: W12

`RunExportedUiAsync` (line 1437) enters text at `(220, 335)` and clicks at
`(260, 505)` to start a run, then enters text at `(220, 690)` and clicks at
`(375, 640)` to cancel. `RunExportedUiFullAsync` (line 1564-1569) enters a
prompt at `(220, 335)` and clicks at `(260, 505)`, then clicks at `(190, 638)`
three times to advance workflow steps. The test verifies outcomes by polling
the SQLite control plane (`WaitForExportedUiRecordAsync`, line 1439-1442), not
by inspecting the UI. This means the test proves the UI buttons are wired to
real operations, but only if the coordinates hit the right controls. If a
layout change moves the "Start" button, the click hits a different control or
empty space, and the test times out rather than reporting which control it
hit. The full-path smoke (line 1577) clicks `(190, 638)` to execute work — a
coordinate that must hit the "Execute ready work" button, but nothing checks.

### The 20260811 attempt's verify.ps1 checked for `complete-app.dll` because the export could succeed without managed assemblies

- Evidence: `prior-attempt (2026-08-11) orc-bot/build/verify.ps1:81-92`
- Confidence: high
- Bearing: W12, ADR-0005

`verify.ps1` lines 81-92 explicitly check: if the build manifest records
`completeApp` as produced, then `complete-app.exe` must exist AND
`complete-app.dll` must be found in the output. Line 90 states: "The
complete-app output is marked produced but contains no complete-app.dll; the
exported Godot app cannot run managed code." This check exists because the
prior attempt learned that Godot's export can produce an executable without
the managed assembly, and without this check, the build would verify green
while shipping a broken app. The 20260815 `build.ps1` does not repeat this
check — it relies on `verify-windowed.ps1` to launch the exported app and
observe its window, which indirectly proves managed code ran (via the title
and nonce observation), but only if the windowed verification is actually
executed.

### `.godot/` derived state was gitignored in both attempts but physically present in the 20260812 working tree with 239 files

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/.gitignore:2`
- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/.godot/` (239 files, including `imported/`, `editor/`, `exported/`, `mono/`)
- Confidence: high
- Bearing: ADR-0004

Both attempts' `.gitignore` files contain `.godot/` (line 2). The 20260811
working tree had no `.godot/` directory (0 files). The 20260812 working tree
had 239 files under `.godot/`, including `imported/icon.svg-*.ctex`,
`editor/filesystem_cache10`, `exported/*/Main.scn`, and `mono/metadata/`. The
20260815 final state had 90 files under `complete-app/.godot/` and 10 under
`project/.godot/`. The gitignore prevents these from entering git, but they
are physically present in the working tree because Godot's editor and headless
import create them. The validation provider (`WindowsGodotValidationProvider`
line 57-59) explicitly checks: `if (Directory.Exists(Path.Combine(sourceRoot,
".godot")))` then throw — a candidate materialization containing `.godot`
state is rejected. The candidate materializer
(`GitCandidateMaterializationProvider.cs` lines 220-224) refuses any
candidate path starting with `.godot/`.

### The Godot cache is portable but sharing one cache between workspaces silently thrashes — exit 0, wrong asset

- Evidence: `prior-attempt (2026-08-12) orc-bot/docs/surveys/godot-cache-provisioning.md:46-71`
- Confidence: high
- Bearing: ADR-0004

The Godot cache provisioning survey (section 3) tested two workspaces
junctioned at one `.godot` cache with different content at `art/tex_5.png`
and `art/tex_9.png`. Both processes exited 0. The cache stayed 298.3 MB. But
cache entries are keyed by path, not content — `tex_5.png-76094b1f….ctex` — so
there is exactly one entry for a path two workspaces disagree about. The
`source_md5` in the cache flipped between the two workspaces' bytes on each
import. Between imports, anything reading the cache gets the other workspace's
asset. The survey's conclusion (line 71): "A shared mutable engine cache is
not a sharing strategy. Seed, do not share." This is why the validation
protocol refuses `.godot` in candidate materializations and why ADR-0004
exists.

### PCK unmount is not real; repeated bundle reloads monotonically grow the mounted VFS

- Evidence: `prior-attempt (2026-08-11) orc-bot/project/hosts/complete-app/scripts/BundleHost.cs:310-335`
- Evidence: `prior-attempt (2026-08-15) orc-bot/docs/research/2026-08-12/experiment-20260811.md:108`
- Confidence: high
- Bearing: ADR-0004

`BundleHost.Unload` (line 315) frees the scene and unloads the managed context
but does not unmount the PCK. The method's doc-comment (line 310-314) states:
"Does not unmount the pack — Godot has no such operation — so the returned
state is `MountedUntilRestart` and the log says so out loud." The
experiment-20260811 report (line 108) confirms: "PCK unmount is not real;
repeated reloads monotonically grow the mounted VFS. Bundle GDScript was
rejected because exported logic did not provide the intended reload
semantics." This means hot-reload of Godot bundles is a leaky abstraction:
the scene and managed code are replaced, but the resource VFS accumulates
dead entries for the process lifetime.

### The operator UI proved the real operator application was wired; it displayed projections that could not advance lifecycle state

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/hosts/complete-app/scripts/Main.cs:92-99, 438-473`
- Evidence: `prior-attempt (2026-08-15) orc-bot/docs/adr/0001-product-root-and-runtime-boundary.md:26-30`
- Confidence: high
- Bearing: W12, ADR-0004

`Main._Ready` (line 92-99) calls `HostComposition.CreateOperatorApplication()`
and then `InitializeAsync()`, which calls `GetCapabilitiesAsync()`,
`ListWorkflowsAsync()`, `GetAgentRosterAsync()`, and three independent source
reads (runs, usage, Orca). The UI renders all of these as tabs and controls
with real data. But ADR-0001 (line 26) states: "The UI can be restarted and
rebuilt from durable facts without treating nodes or controls as truth." The
UI polls every 1 second (`_poll`, line 432-434) and re-queries the operator
application; it does not cache or own state. Every visible action (Start,
Execute, Cancel, Accept, Reject, Retry cleanup) issues a real command through
`_application` and then re-reads the durable state. The Arch ECS projection
(ADR-0004) is rebuilt from SQLite facts after restart. The UI proves the
operator application is wired but cannot prove anything the durable facts do
not already prove.

### The headless smoke test checked tab names and button labels, not behavior — a string match that passes with dummy data

- Evidence: `prior-attempt (2026-08-15) orc-bot/project/tests/host_smoke.gd:3-32, 61-72`
- Confidence: high
- Bearing: W12

`host_smoke.gd` defines `EXPECTED_TABS` (lines 3-13) and `EXPECTED_ACTIONS`
(lines 14-24) as string arrays, then checks (lines 61-72) that each expected
tab name and button text is found by `find_child`. This proves the scene tree
contains nodes with those names, not that the buttons are wired to real
handlers or that the tabs display real data. A stub scene with correctly named
labels and buttons would pass this smoke. The smoke also checks (lines 81-92)
that the native session scope selector defaults to the all-runs catalog —
again a string match on the picker's first item text. The test README (line
150-154) acknowledges this: "A matching title, window size, or process
survival interval alone cannot produce a successful validation receipt." The
headless smoke is a structure check; the exported-window smoke is the
behavioral check.

### The 20260811 build.ps1 retention deleted stale artifact directories but swallowed failures from locked directories

- Evidence: `prior-attempt (2026-08-11) orc-bot/build/build.ps1:261-284`
- Confidence: high
- Bearing: ADR-0005

`build.ps1` lines 261-284 prune stale artifact directories, keeping only the
newest `$Retain` (default 3). Line 277-279 catches `Remove-Item` failures:
"A resident exported app intentionally keeps its version directory open.
Retention is best-effort housekeeping and must not turn a successfully
published replacement into a failed build." This means a locked artifact
directory (e.g., from a running exported app that wasn't killed) survives
pruning silently. The `latest` symlink (lines 216-247) is repointed before
retention runs, so `latest` always points to the current version, but stale
locked directories accumulate. The 20260815 `build.ps1` (line 59-62) checks
that `latest` is a `SymbolicLink` and throws if not, but does not repeat the
retention logic — it relies on UnifyBuild's `SyncLatestArtifacts`.

### The 20260812 Main.cs hard-coded absolute paths to tool executables and the repository root

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/Main.cs:35-46`
- Confidence: high
- Bearing: ADR-0004

`Main.cs` lines 35-46 define:
```csharp
private const string ZellijExe = @"<tools>/zellij\0.44.3\zellij.exe";
private const string OrcaExe = @"<home>\AppData\Local\Programs\orca\resources\bin\orca.exe";
private const string Repo = @"<workspace>/agent-projects/orc-bot";
```
These are hard-coded absolute paths to specific machine locations. The
20260815 attempt replaced these with `HostComposition.CreateOperatorApplication()`
(lines 27-61) which resolves paths from environment variables
(`ORCBOT_ZELLIJ`, `ORCBOT_CODEX`, `ORCBOT_GODOT`, `ORCBOT_ORCA`) with
fallbacks to known `<tools>/` locations. The 20260812 hard-coding means the
exported app only works on one developer's machine.

### The 20260812 `binary_format/embed_pck=false` shipped the app as a bare executable with a sidecar `.pck`, while 20260815 set `embed_pck=true`

- Evidence: `prior-attempt (2026-08-12) orc-bot/project/hosts/complete-app/export_presets.cfg:25`
- Evidence: `prior-attempt (2026-08-15) orc-bot/project/hosts/complete-app/export_presets.cfg:24`
- Confidence: high
- Bearing: W12, ADR-0005

The 20260812 `export_presets.cfg` line 25 sets
`binary_format/embed_pck=false`, and the export produced a bare `complete-app.exe`
plus a sidecar `.pck` file. The 20260815 `export_presets.cfg` line 24 sets
`binary_format/embed_pck=true`, embedding the pack into the executable. The
20260811 attempt also used `embed_pck=false` (line 28). The embed-pck change in
20260815 means the exported executable is self-contained, but it also means
the export must succeed completely in one pass — there is no sidecar to
partially ship. The `dotnet/embed_build_outputs=false` setting (present in
both 20260811 line 49 and 20260815 line 31) means the managed assemblies are
copied alongside the executable, not embedded in the `.pck`. This is the
Godot.NET.Sdk default and is what makes the missing `.sln` so dangerous: the
export succeeds, the `.pck` is embedded, but the managed `.dll` files are
never compiled and thus never copied.

## Unverified recollections

### MSBuild node-reuse hangs after every artifact was written

I could not find direct evidence of MSBuild node-reuse hangs in any snapshot.
The 20260811 `build\build.ps1` does not disable node reuse (`-nodeReuse:false`
is absent from the `dotnet build` invocation in
`WindowsGodotValidationProvider.cs` line 64, which runs `dotnet build ...
--nologo --ignore-failed-sources`). The `ExternalProcess.RunAsync` (line 9-50)
has a timeout that kills the process tree on cancellation. If MSBuild
node-reuse caused a hang, it would manifest as a timeout in the validation
provider, but no snapshot contains a log or note documenting this. The task
brief mentions this failure mode, but I found no evidence for it in the
surveyed trees.

### Crash dialogs from the export binary that read as the app crashing

I could not find evidence of crash dialogs from the exported Godot binary. The
`WindowsGodotValidationProvider.ObserveWindowAsync` (line 217-269) checks
`IsHungAppWindow` and `process.HasExited`, and throws if the process exits
before presenting a window (line 226). A crash dialog would appear as a window
with a different title than expected, causing a timeout at line 239-242. No
snapshot contains a log or note documenting a crash dialog from the export
binary specifically.

### A bare GodotSharp reference compiling but never receiving _Ready

I found no direct evidence of a "bare GodotSharp reference" failure. The
20260812 `complete-app.csproj` (not read in detail) and the 20260815
`complete-app.csproj` (line 1) both use `<Project Sdk="Godot.NET.Sdk/4.7.1">`,
which injects the GodotSharp reference. The missing `.sln` finding above is
the closest evidence: without the `.sln`, Godot's export does not build the
C# project, so `GodotSharp.dll` is present (it ships with the engine) but the
application's own `complete-app.dll` is absent, and `_Ready` never runs because
the script class is never instantiated. This is inferred from the
`verify.ps1` check for `complete-app.dll` (lines 81-92) and the `AGENTS.md`
note (lines 66-69), not from a captured log of the failure.