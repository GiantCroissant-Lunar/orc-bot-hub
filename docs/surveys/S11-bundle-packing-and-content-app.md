# S11 — bundle packing with a headless Godot editor, and what `content-app` is for

- Date: 2026-08-16
- Scope: how a `.pck` bundle is actually produced and consumed, across the six
  `fantasim-app-godot` snapshots, the **first Orc Bot attempt** (which shipped the same
  machinery and improved on it), the Archi/Foundation libraries, and a live
  Godot 4.7.1 experiment run for this survey.
- Frame: [ADR-0004](../adr/0004-derived-state-and-tool-authority-slots.md),
  [ADR-0005](../adr/0005-build-versioning-and-artifact-layout.md),
  [ADR-0009](../adr/0009-seed-engine-caches-do-not-share-them.md),
  [RFC-0001](../rfc/0001-bootstrap-slice.md).
- Supersedes the recommendation half of
  [S8](S8-fantasim-bundles-and-tiers.md). S8's *evidence* stands; its conclusion
  ("do not take the four-tier architecture", "do not add PCK hot reload") was
  answering a question the owner was not asking.

## Why this survey exists

S8 evaluated the four-tier + bundle design as a **game-services pattern** and correctly
found it oversized for a headless daemon. The owner's actual requirement is different and
broader: the four tiers plus bundle orientation are intended as the **uniform architecture
for all their C# development** — Godot, Unity, and plain C# alike — and bundle orientation
is the thing that makes that development hot-reloadable. Under that framing the question
is not *whether* but *how*.

So this survey takes the requirement as given and asks what the prior work actually did
about the two hard constraints S8 named — Godot cannot unmount a PCK, and a Godot `Node`
reference pins a collectible ALC. Both were confronted, and both have concrete answers in
the code.

## Result

The machinery is real, complete, and was **built twice**: once in `fantasim-app-godot` and
once, better, in the **first Orc Bot attempt**, which S8 did not look at. Orc Bot's own
prior tree already had `project/hosts/content-app`, `project/bundles/{orc-ui,
orc-devtools, orc-history-ui}`, a Taskfile that creates the junction and drives
`--export-pack`, an ABI-fingerprint compatibility guard, and reload rollback. The Godot
host present in orc-bot today has a `content-app` that is **byte-identical to the
vestigial empty skeleton** left in the 2026-07-18 fantasim snapshot — it is the shell, not
the working version.

The two constraints resolve like this:

- **PCK cannot be unmounted.** Nobody unmounts it. The load path copies each PCK to a
  fresh per-load temp path and mounts it with `replace_files: true`, so the newer mount
  shadows the older at the same `res://` path. The cost is a bounded VFS growth of one
  entry set per reload; the prior Orc Bot turned that cost into a feature by keeping the
  previous copy as a **reload rollback**.
- **A Godot `Node` pins the ALC.** Nothing Godot-derived is ever put in a collectible ALC.
  That is the whole content of Tier 1/2 being *resident*: the resident layer is the Godot
  surface, the collectible layer is plain C#, and they talk over a message bus. This is
  enforced by a Roslyn analyzer (PLUG007), not by convention.

Three findings are new and were measured for this survey on Godot 4.7.1 mono:

1. **Godot's exporter silently drops a raw `.dll` from a bundle unless `include_filter`
   names it, while it always carries `.json`.** This is the previously-unrecorded reason
   the prior Orc Bot base64-wrapped every plugin assembly into a `.dll.payload.json`.
2. **`include_filter` still does not scope a bundle PCK in 4.7.1** — the documented
   4.6 gotcha reproduces exactly. `exclude_filter` does.
3. **Every bundle PCK contains `res://project.binary`, `res://icon.svg` and the
   `.godot` caches**, and mounting it with `replace_files: true` shadows the host's.
   That hazard is not addressed anywhere in the prior work.

---

## 0. Which snapshot is mature, and what changed

| Snapshot | `project/bundles/` | `hosts/content-app` | `--export-pack` in Taskfile |
|---|---|---|---|
| **2026-06-25** `fantasim-app-godot` | 22 bundles | full: presets + junction | 22 targets |
| **2026-06-25** `orc-bot` (attempt 1) | 3 bundles | full: presets + junction | 3 targets |
| 2026-07-18 | absent | **empty skeleton, no presets** | none |
| 2026-07-26 … 2026-07-31 | absent | deleted | none |
| 2026-08-03 | absent | deleted | none |

**2026-06-25 is the mature version and the only one that has the mechanism at all.** The
2026-07-18 snapshot is the fantasim rewrite: the bundle system was dropped and `content-app`
left behind as an empty Godot project with `project.godot`, `icon.svg`, `icon.svg.import`
and nothing else. By 2026-07-26 even that was gone.

**Orc Bot's current `project/hosts/content-app/project.godot` is byte-identical to the
2026-07-18 vestigial one** (verified by diff; the only additions since are the generated
`.godot/` cache and a `config/features` bump to 4.7). So the starting point is the shell,
and everything in §1 is what has to be added back.

By 2026-08-03 the word "bundle" had been reassigned in fantasim to a **content-addressed
immutable world package** — `manifest.rwp` plus `payloads/sha256/<xx>/<64-hex>.bin`, read
through a three-method `IRuntimeBundle` interface, never mounted and never loaded into an
ALC. (prior-attempt (2026-08-03) fantasim-app-godot/project/runtime/README.md:136-173) That
is a *different artifact* solving a different problem, and §2 explains why both concepts
are worth having.

---

## 1. The packing mechanism, exactly

### 1.1 The invocation

One Godot call per bundle. From the mature Taskfile, the simplest target in full:

```yaml
  "build:bundle:hud-control":
    desc: Build hud-control bundle
    deps: ["ensure:artifacts-dir"]
    cmds:
      - python tools/build.py ensure-dir "{{.BUNDLES_DIR}}"
      - '"{{.GODOT}}" --headless --path "{{.CONTENT_PROJECT}}" --export-pack "hud-control PCK" "{{.BUNDLES_DIR}}/hud-control.pck"'
```

(prior-attempt (2026-06-25) fantasim-app-godot/Taskfile.yml:244-249)

`{{.GODOT}}` is the **mono** editor binary; `CONTENT_PROJECT` is
`project/hosts/content-app`; `BUNDLES_DIR` is
`build/_artifacts/<version>/godot/win-x64/bundles`.
(prior-attempt (2026-06-25) fantasim-app-godot/Taskfile.yml:6-38)

Three things about that command line are load-bearing, and all three are confirmed by
running it:

- **`--headless` is enough.** No virtual display, no `--script`, no `-s`, no editor
  automation. `--export-pack` is a first-class editor CLI verb. There is no `--script`-
  driven packer anywhere in either 2026-06-25 tree.
- **`ensure-dir` is not defensive tidiness.** Godot's exporter does **not** create the
  output directory. Measured 2026-08-16 on Godot 4.7.1 mono, exporting into a
  non-existent folder:

  ```
  [   0% ] savepack | Started Packing (102 steps)
  ERROR: Save PCK: Can't open file for writing at path ".../out/probe-bundle.pck".
     at: add_message (./editor/export/editor_export_platform.h:270)
  ERROR: Project export for preset "probe-bundle PCK" failed.
  ```
  Exit code 2, no `.pck`. Creating the directory first makes the identical command succeed.
- **Bundle builds must be serialised.** The aggregate target uses `cmds:` rather than
  `deps:` with this reason: *"Sequenced via cmds (not deps) because parallel Godot
  --headless calls on the same project contend on the .godot/ project lock."*
  (prior-attempt (2026-06-25) fantasim-app-godot/Taskfile.yml:442-449) This is the same
  path-keyed-cache hazard [ADR-0009](../adr/0009-seed-engine-caches-do-not-share-them.md)
  records, arriving through a different door: one `content-app`, one `.godot`, so one
  packer at a time.

The 4.7 CLI also gained `--export-patch <preset> <path>` plus `--patches`, which exports a
pack containing **changed files only**. Nothing in the prior work uses it; it is the
obvious future answer to per-reload PCK size and is noted here so it is not rediscovered.

### 1.2 The `content-app` project itself

The mature `content-app` is **not a C# project**. It has no `.csproj` and no `.sln`; it is
a bare Godot project whose entire job is to own export presets and a view of the bundle
sources. Its complete contents, 2026-06-25:

```
.editorconfig  .gitattributes  .gitignore
export_presets.cfg      37 KB, one preset per bundle
icon.svg  icon.svg.import
project.godot          533 bytes
bundles/               → directory junction to ../../bundles/
```

`project.godot` still declares `[dotnet] project/assembly_name="content-app"` even with no
`.csproj` present. (prior-attempt (2026-06-25) fantasim-app-godot/project/hosts/content-app/project.godot:17-19)

The junction is the point, and the preset header says so:

> This project's sole purpose is `--export-pack` calls. The `bundles/` subdirectory is a
> junction back to `../../bundles/`; each bundle preset below scopes `export_filter` to
> that bundle's subtree so only its own scenes/scripts/assets land in the resulting
> `.pck`. The "Windows Desktop PCK" full-content preset excludes the `bundles/` tree
> (each bundle ships via its own PCK at runtime).

(prior-attempt (2026-06-25) fantasim-app-godot/project/hosts/content-app/export_presets.cfg:1-8)

The junction is ignored in the packing project so the same files are not tracked twice:

```
# Directory junction to ../../bundles/. The real files live under
# project/bundles/ (sibling to plugins/contracts) and are tracked there;
# ignoring the junction here prevents duplicate tracking and keeps the
# content-app project free of accidental PCK-source commits.
/bundles
```

(prior-attempt (2026-06-25) fantasim-app-godot/project/hosts/content-app/.gitignore:5-9)

The first Orc Bot attempt made the junction a Taskfile precondition rather than a manual
setup step, and validated it:

```yaml
  "ensure:content-bundles-link":
    desc: Ensure content-app can see project/bundles for Godot PCK export
    cmds:
      - powershell -NoProfile -Command "... if (!(Test-Path '<root>\project\hosts\content-app\bundles')) { New-Item -ItemType Junction -Path '...\content-app\bundles' -Target '...\project\bundles' } elseif ((... -band [IO.FileAttributes]::ReparsePoint) -eq 0) { throw 'project/hosts/content-app/bundles exists but is not a junction' }"
```

(prior-attempt (2026-06-25) orc-bot/Taskfile.yml:123-127; the target is a `deps:` of every
bundle build)

**Minimum a packing project must contain**, from the above and confirmed by building one
from scratch: `project.godot`; an `export_presets.cfg` with one preset per bundle; a
`bundles/` view of the sources. `icon.svg` is only needed because `project.godot` points
`config/icon` at it. No `.csproj`, no scene, no autoload, no main scene, no C#.

### 1.3 Preset scoping — the gotcha, still true in 4.7.1

The presets use `export_filter="customized"` with `include_filter="bundles/<id>/*"` and a
long `exclude_filter` naming **every other bundle**:

```
[preset.1]
name="hud-control PCK"
export_filter="customized"
include_filter="bundles/hud-control/*"
exclude_filter="*.gd.uid,bundles/panel-inspector/*,bundles/panel-scene-tree/*,…"
```

(prior-attempt (2026-06-25) fantasim-app-godot/project/hosts/content-app/export_presets.cfg:38-53)

That exclude list is generated, not hand-written, and the generator states the failure it
prevents:

> In Godot, `include_filter` only adds *non-resource* files; it does NOT restrict which
> resources (scripts/scenes) get exported. With an empty customized-file set,
> `customized` exports the ENTIRE resource tree → every bundle PCK becomes a full dump of
> every bundle's scripts (~323 KB each, all near-identical).
>
> The practical damage: a script … ends up duplicated in every bundle PCK. Fixing it and
> rebuilding only its "home" bundle leaves stale copies in the others; whichever bundle
> loads last wins via `load_resource_pack(replace_files=true)`, silently shadowing the fix.

(prior-attempt (2026-06-25) fantasim-app-godot/tools/scope_bundle_presets.py:1-30; the
script is idempotent and has a `--check` mode for CI)

**Reproduced on Godot 4.7.1 mono, 2026-08-16.** A scratch `content-app` with two bundles
and a `probe-bundle` preset carrying `include_filter="bundles/probe-bundle/*"` and no
cross-bundle excludes produced a "probe-bundle" pack containing:

```
res://bundles/other-bundle/manifest.json          ← wrong bundle
res://bundles/other-bundle/scenes/other.tscn.remap ← wrong bundle
res://bundles/probe-bundle/manifest.json
res://bundles/probe-bundle/Probe.Plugin.dll
res://bundles/probe-bundle/scenes/probe.tscn.remap
res://icon.svg   res://icon.svg.import   res://project.binary
res://.godot/global_script_class_cache.cfg  res://.godot/uid_cache.bin
```

Adding `bundles/other-bundle/*` to `exclude_filter` removed both foreign entries and
nothing else. The 4.6-era workaround is still exactly correct in 4.7.1.

### 1.4 The `.dll` carriage problem — why `.payload.json` exists

The two 2026-06-25 trees stage managed assemblies into a bundle differently, and the
difference has never been explained in either tree. It matters, so it was measured.

**fantasim** copies raw DLLs into the bundle directory before packing, including
plugin-private dependencies:

```yaml
  "build:bundle:plugin-fantasim":
    desc: … Stages the reconstruct node's plugin-private deps … into the bundle ALC;
          UnifyGeometry/FantaSim stay host-shared (SharedAssemblyPolicy).
    deps: ["ensure:artifacts-dir", "compile"]
    vars:
      PF_BIN: project/plugins/Plugin.Fantasim/.godot/mono/temp/bin/Debug
    cmds:
      - cp "{{.PF_BIN}}/Plugin.Fantasim.dll" "project/bundles/plugin-fantasim/"
      - cp "{{.PF_BIN}}/App.Datasets.Import.Gplates.Reconstruction.World.dll" "project/bundles/plugin-fantasim/"
      …
      - cp "<nuget-cache>/unifycell.core/0.0.5/lib/netstandard2.1/UnifyCell.Core.dll" "project/bundles/plugin-fantasim/"
      - '"{{.GODOT}}" --headless --path "{{.CONTENT_PROJECT}}" --export-pack "plugin-fantasim PCK" "{{.BUNDLES_DIR}}/plugin-fantasim.pck"'
```

(prior-attempt (2026-06-25) fantasim-app-godot/Taskfile.yml:335-352)

Two incidental facts worth keeping: a `Godot.NET.Sdk` plugin builds to
`.godot/mono/temp/bin/<Config>`, **not** `bin/<Config>/net8.0`, and it must be built that
way so the Godot source generators run — otherwise `_Ready`/`_Process` never dispatch
(prior-attempt (2026-06-25) fantasim-app-godot/Taskfile.yml:284-286); and NuGet-sourced
dependencies must be copied from the package cache, because a library project does not
copy package DLLs locally.

**The first Orc Bot attempt does the opposite** — it deletes any raw `.dll` from the bundle
directory and writes a base64 JSON envelope instead:

```powershell
$rawDllBundlePath = Join-Path $BundleDir ($projectName + ".dll")
if (Test-Path -LiteralPath $rawDllBundlePath) { Remove-Item -LiteralPath $rawDllBundlePath -Force }

if (Test-Path -LiteralPath $dllSource) {
    $dllPayload = [ordered]@{
        format   = "orc-managed-binary-v1"
        fileName = [IO.Path]::GetFileName($dllSource)
        base64   = [Convert]::ToBase64String([IO.File]::ReadAllBytes($dllSource))
    }
    $dllPayloadPath = Join-Path $BundleDir ($projectName + ".dll.payload.json")
    …
}
```

(prior-attempt (2026-06-25) orc-bot/tools/stage-managed-bundle.ps1:34-50; it also cleans up
an even earlier `.dll.bundle` / `.deps.json.bundle` scheme at :26-32, so this is the third
generation of the same decision)

**Measured 2026-08-16, Godot 4.7.1 mono.** A scratch bundle containing
`Probe.Plugin.dll`, `Probe.Plugin.dll.payload.json`, `manifest.json`, `probe.deps.json`,
`probe.txt`, `probe.bin`, `probe.dat`, `probe.so`, `probe.dylib` was packed twice from the
same `export_filter="customized"` preset.

With `include_filter=""`, the pack contained **only**:

```
res://bundles/probe-bundle/manifest.json
res://bundles/probe-bundle/probe.deps.json
res://bundles/probe-bundle/Probe.Plugin.dll.payload.json
res://bundles/probe-bundle/scenes/probe.tscn.remap
```

With `include_filter="bundles/probe-bundle/*"`, every one of `.dll`, `.txt`, `.bin`,
`.dat`, `.so`, `.dylib` came back.

So: **Godot's exporter carries `.json` unconditionally and drops `.dll` unless
`include_filter` names it.** A bundle whose preset lost its `include_filter` still packs,
still mounts, still reads its manifest, and simply has no assembly — the exact "loads but
does nothing" signature. Wrapping the assembly in JSON makes carriage independent of
whether one generated preset among twenty is correct. That is a real reason, and it is why
the JSON envelope should be preferred over raw DLLs even though raw DLLs demonstrably work
(the 4096 random bytes staged as `Probe.Plugin.dll` were verified byte-identical inside the
resulting `.pck`).

The cost is ~4/3 size and a base64 decode on load, both trivial next to a PCK mount.

### 1.5 A hazard nobody addressed

Every bundle PCK produced by this mechanism also contains `res://project.binary`,
`res://icon.svg`, `res://icon.svg.import`, `res://.godot/uid_cache.bin` and
`res://.godot/global_script_class_cache.cfg` (observed above; `exclude_filter` does not
remove them — `project.binary` is synthesised by the exporter, not read from the tree).
Every mount in both prior trees is `ProjectSettings.LoadResourcePack(pckPath)` with
Godot's default `replace_files: true`
(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleVfs.cs:8-11;
prior-attempt (2026-06-25) orc-bot/project/plugins/Plugin.Orc.Bundles/OrcBundleVfs.cs:15-16),
so a bundle shadows the host's `project.binary` and script-class cache at those paths for
the rest of the process. Nothing in either tree notices this. It has not been observed to
break anything, and it should be decided deliberately rather than inherited.

---

## 2. The manifest and addressing

### 2.1 What travels with a bundle

`manifest.json` sits at the root of the bundle directory and therefore at
`res://bundles/<id>/manifest.json` inside the pack. The mature fantasim shape:

```json
{"bundleId":"plugin-world-globe","displayName":"World Globe Sink","version":"0.1.0",
 "pluginAssembly":"Plugin.WorldGlobe.dll"}
```

```json
{"bundleId":"hud-control","displayName":"HUD Control","version":"0.1.0",
 "entryScene":"scenes/hud_root.tscn",
 "residentScripts":[{"nodePath":"VBox/DockContainer","residentType":"CompleteApp.HudDockContainer"}]}
```

(prior-attempt (2026-06-25) fantasim-app-godot/project/bundles/plugin-world-globe/manifest.json:1;
prior-attempt (2026-06-25) fantasim-app-godot/project/bundles/hud-control/manifest.json:1)

A bundle is **content, code, or both** — `view-runtime-topology` declares an `entryScene`
*and* a `pluginAssembly`. The model also has a second-generation shape with
`content.pcks[]` and `managed.assemblies[]` arrays, where a managed assembly declares a
`kind` of `dll`, `nupkg`, or `zip`; the legacy scalar fields are compatibility accessors
over the first array element.
(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleManifest.cs:41-99, 107-176)
That `ManagedAssemblyKind` enum matters for §5: the manifest already anticipated carriers
that are not PCKs.

**S8's finding that the manifest carries no dependency declaration is correct for
fantasim and wrong for Orc Bot's own prior attempt.** Orc Bot's manifests carry a
per-shared-assembly ABI fingerprint:

```json
{
  "bundleId": "orc-devtools",
  "displayName": "Orc DevTools Commands",
  "version": "0.1.0",
  "metadata": {
    "kind": "managed-plugin",
    "surface": "bridge-commands",
    "commands": "bridge.describe,bundle.status,bundle.build,bundle.reload,repo.status,…",
    "requires.sharedAssembly.Orc.Bot.Contracts.publicApiFingerprint": "sha256:79ecebca…",
    "requires.sharedAssembly.Orc.Bot.Bundles.Contracts.publicApiFingerprint": "sha256:2d2320c9…"
  },
  "managed": { "assemblies": [ { "id": "Plugin.Orc.DevTools", "uri": "Plugin.Orc.DevTools.dll" } ] }
}
```

(prior-attempt (2026-06-25) orc-bot/project/bundles/orc-devtools/manifest.json:1-20;
fingerprints truncated here, full 64-hex in the source)

There is still no `dependsOn` between bundles and no topological load validation. Ordering
is a filename heuristic: anything named `plugin-*` loads in phase 0, everything else in
phase 1, alphabetical within a phase.
(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleRuntimeService.cs:58-62, 240-244)
That is the weakest part of the design and the one place a successor should not copy.

### 2.2 Who writes the fingerprint

Nobody by hand. Each shared contract assembly declares a generated constant:

```csharp
public static class OrcContractAbi
{
    public const string PublicApiFingerprint = "sha256:79ecebca…";
}
```

(prior-attempt (2026-06-25) orc-bot/project/contracts/Orc.Bot.Contracts/OrcContractAbi.cs:3-5)

The staging script walks the plugin's `ProjectReference` list, keeps only references under
a `contracts/` path, reads each one's `PublicApiFingerprint`, and stamps
`requires.sharedAssembly.<AssemblyName>.publicApiFingerprint` into the manifest — throwing
if a contract reference does not declare one.
(prior-attempt (2026-06-25) orc-bot/tools/stage-managed-bundle.ps1:170-219)

The fingerprint itself is a sha256 over a canonicalised rendering of the assembly's
exported surface — every public type with its base/interface/abstract/sealed flags, then
its constructors, fields (with const values), properties, methods and parameters, each on
a sorted line — with the `*ContractAbi` type itself excluded so the constant does not hash
itself.
(prior-attempt (2026-06-25) orc-bot/project/tests/Orc.Bot.DevTools.Tests/Program.cs:5695-5740)
A test asserts the committed constant equals the recomputed value, so a contract change
that is not re-stamped fails the build rather than the runtime.
(prior-attempt (2026-06-25) orc-bot/project/tests/Orc.Bot.DevTools.Tests/Program.cs:1769-1777)

This is the same discipline the current tree already uses for
[profile manifest digests and the bridge digest](S8-fantasim-bundles-and-tiers.md) — mint
by hashing a canonical form, commit the constant, gate on drift.

### 2.3 How the runtime finds bundles

By convention, from one resolver:

```csharp
public string ResolveAutoLoadBundlesDirectory()
{
    if (OS.HasFeature("editor"))
        return ProjectSettings.GlobalizePath("res://system_bundles");

    var exeDir = OS.GetExecutablePath().GetBaseDir();
    return Path.Combine(exeDir, "bundles");
}
```

(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/GodotBundleDirectoryResolver.cs:8-15)

Auto-load enumerates `*.pck` in that directory, drops any id in a configured exclude list,
orders by phase then name, and loads each — logging and continuing on a per-bundle failure
rather than aborting the boot.
(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleRuntimeService.cs:46-81)

**This is where the mechanism collides with ADR-0005 and the collision must be resolved
before any of it is adopted.** ADR-0005 puts bundles at
`build/_artifacts/<version>/bundles/`. The resolver hard-codes `<exe-dir>/bundles`, and the
exported host lives at `build/_artifacts/<version>/godot/win-x64/`, which is why fantasim's
`BUNDLES_DIR` is `…/godot/win-x64/bundles` rather than the ADR's location. See §6.

Bundles are also loadable from an arbitrary path and over HTTP
(`LoadRemoteAsync` fetches a URL to a temp file and calls the same load path)
(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleHost.cs:122-137),
which is where the "downloadable panel" ambition lived. Nothing in either tree verifies a
digest on that path.

### 2.4 The other bundle — content-addressed payloads

The newest fantasim uses "bundle" for something else, and the shape is worth keeping
separate rather than merged:

```csharp
public interface IRuntimeBundle
{
    string Description { get; }
    string ReadManifest();
    byte[]? ReadPayload(string contentHash);
    IReadOnlyCollection<string> PayloadContentHashes();
}
```

```
world_package_v1/
  manifest.rwp                              canonical text, sealed by its own hash
  payloads/sha256/<xx>/<64-hex>.bin         one array per field, addressed by content
```

> The path under `payloads/` is derived from the hash of the bytes and never declared, so
> a payload somebody replaced is one that no longer hashes to the name it is stored under.

(prior-attempt (2026-08-03) fantasim-app-godot/project/runtime/README.md:136-173)

Two carriers implement it: `DirectoryBundle` over `System.IO` for a plain C# consumer, and
`DelegateBundle` — three lambdas — for the Godot host, "an engine path resolves inside a
shipped archive where `System.IO` sees nothing".
(prior-attempt (2026-08-03) fantasim-app-godot/project/runtime/README.md:144-149)

**The two bundle concepts are complementary, not competing.** A PCK bundle is an
*executable/renderable unit* that gets mounted and whose code is loaded. A digest-addressed
payload bundle is an *immutable data unit* that is read and never executed. Orc Bot needs
both, for different things: the first for hot-reloadable development surfaces, the second
for candidate evidence under [ADR-0002](../adr/0002-fenced-source-allocations-and-immutable-candidates.md).
And the three-method `IRuntimeBundle` + two-carrier split is precisely the engine-neutral
seam §5 needs.

---

## 3. Loading, and the hot-reload loop

### 3.1 The load path

The mature Orc Bot version, in order:

```csharp
var pckName       = Path.GetFileNameWithoutExtension(pckPath);
var bundleResPath = $"res://bundles/{pckName}";
var loadPckPath   = CopyPckToSessionTemp(pckPath, pckName);      // fresh path per load

if (!_vfs.LoadPck(loadPckPath))                                   // LoadResourcePack
    throw new InvalidOperationException($"Failed to load bundle PCK: {pckPath}");

var manifest = _vfs.ReadManifest(bundleResPath);
bundleId = manifest?.BundleId ?? pckName;

OrcBundleCompatibilityGuard.Validate(bundleId, manifest, _logger);   // ABI gate, before anything runs

if (!string.IsNullOrWhiteSpace(manifest?.EntryScene))
{
    var scene = _sceneHost.InstantiateScene(bundleResPath.PathJoin(manifest.EntryScene));
    if (scene is not null) _sceneHost.RegisterScene(bundleId, scene);
}

if (!string.IsNullOrWhiteSpace(manifest?.PluginAssembly))
{
    var tempPath = _extractor.ExtractToTemp(bundleResPath, manifest.PluginAssembly);
    …
    await _pluginHost.AddGroupAsync(bundleId, manifest.DisplayName, tempDir, ct: cancellationToken);
}
```

(prior-attempt (2026-06-25) orc-bot/project/plugins/Plugin.Orc.Bundles/OrcBundleHost.cs:74-141)

The fantasim version is the same minus the guard and the PCK copy, and extracts **every**
`.dll` in the bundle rather than just the declared one, because a collectible ALC resolves
a plugin's private dependencies from the directory beside the plugin DLL.
(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleHost.cs:65-120;
DllExtractor.cs:43-86, which also handles PCK entries surfacing as `<name>.remap`)

Scene instantiation must bust Godot's resource cache or a reload silently serves the old
scene:

```csharp
// CacheMode.ReplaceDeep: re-read the PackedScene AND its dependencies … from the PCK
// instead of serving the cached copy. This is what makes bundle hot-reload work …
// a plain cached Load would still return the OLD scene/script.
var packed = ResourceLoader.Load<PackedScene>(scenePath, null, ResourceLoader.CacheMode.ReplaceDeep);
```

(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleSceneHost.cs:20-51)

### 3.2 What is done about "Godot cannot unmount a PCK"

Nothing pretends otherwise. The unmount is an empty method with an honest comment:

```csharp
public void UnloadPck(string pckPath)
{
    // Godot does not support unloading individual PCKs at runtime.
    // Tracked as a known limitation — scenes instantiated from the PCK
    // can still be freed, but the VFS entries persist until restart.
}
```

(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleVfs.cs:13-18)

The strategy is **shadow, not unmount**, and it works because `LoadResourcePack` defaults to
`replace_files: true`: a newer mount wins at the same `res://` path. Orc Bot's version adds
the piece that makes this safe on disk — every load copies the PCK to a monotonically
numbered session-temp path first:

```csharp
private string CopyPckToSessionTemp(string pckPath, string pckName)
{
    var loadId  = Interlocked.Increment(ref _pckLoadSeq);
    var tempDir = Path.Combine(_pckTempRoot, SafeFileName(pckName), loadId.ToString(…));
    Directory.CreateDirectory(tempDir);
    var tempPath = Path.Combine(tempDir, Path.GetFileName(pckPath));
    File.Copy(pckPath, tempPath, overwrite: true);
    return tempPath;
}
```

(prior-attempt (2026-06-25) orc-bot/project/plugins/Plugin.Orc.Bundles/OrcBundleHost.cs:286-295)

Two consequences. First, the mounted file is never the build output, so the packer can
overwrite `bundles/<id>.pck` while the app holds a mount. Second — and this is the design
turning a leak into a feature — the *previous* copy is still on disk and still mountable,
so a failed reload rolls back:

```csharp
var rollbackPckPath = bundle.LoadedPckPath;
await UnloadAsync(bundleId, detachScene: true, cancellationToken);
try
{
    await LoadCoreAsync(pckPath, pckPath, cancellationToken);
    if (!_loaded.ContainsKey(bundleId))
        throw new InvalidOperationException($"Reloaded PCK did not register bundle '{bundleId}'.");
}
catch (Exception ex) when (ex is not OperationCanceledException)
{
    var restored = await TryRestorePreviousBundleAsync(bundle, rollbackPckPath);
    …
}
```

(prior-attempt (2026-06-25) orc-bot/project/plugins/Plugin.Orc.Bundles/OrcBundleHost.cs:186-226, 303-341)

So the answer to "version the paths, relaunch, or accept the leak" is: **accept a bounded
leak, deliberately, and spend it on rollback.** The residue per reload is one temp PCK copy
plus one temp DLL directory, both queued for deletion by a sweep, plus one non-reclaimable
set of Godot VFS entries. Only the last is permanent, and it is metadata, not payload.

### 3.3 The real developer loop

The measured behaviour table, from the authoritative note:

| Change type | Live hot-reload in exported build? | What you do |
|---|---|---|
| **GDScript *logic*** (a `.gd` script body) | ❌ **No** — verified 2026-05-30 | Rebuild that one bundle → **restart** the app |
| **`.tscn` scene *structure*** | ⚠️ Reported yes (prior session, NOT re-verified) | Rebuild that bundle; re-verify before relying on it |
| **C# Tier-3 collectible-ALC service** | ✅ **Yes — verified 2026-05-30**, old ALC truly unloads | Rebuild that plugin bundle; new behaviour runs live |

(prior-attempt (2026-06-25) fantasim-app-godot/vault/bundle-hot-reload-behavior.md:9-23)

The GDScript negative was established with an `ALPHA`/`BETA` probe: the watcher fired for
the changed bundle only, `_ready` ran a second time, and still printed `ALPHA`; restarting
printed `BETA`. The mechanism is that bundle scripts export as compiled binary tokens
(`script_export_mode=2` → `.gdc` + `.gd.remap`) and Godot keeps the GDScript *class object*
resident even when `ReplaceDeep` re-reads the scene resource.
(prior-attempt (2026-06-25) fantasim-app-godot/vault/bundle-hot-reload-behavior.md:24-54)

The C# positive was established the same way and additionally proved the ALC collected:
two consecutive reloads each logged *"old ALC collected — released and deleted"* and the
temp-dir count stayed at 1 instead of growing by one per reload.
(prior-attempt (2026-06-25) fantasim-app-godot/vault/bundle-hot-reload-behavior.md:80-96)

**The loop, in seconds.** The watcher polls every **0.5 s** with a **250 ms** debounce, a
seeded mtime baseline so boot does not reload everything, and a `SemaphoreSlim` so reloads
serialise:

```csharp
_timer = new Godot.Timer { WaitTime = 0.5, OneShot = false, Autostart = true };
```

(prior-attempt (2026-06-25) orc-bot/project/plugins/Plugin.Orc.Bundles/OrcBundleHotReloadService.cs:52, 92-160)

The pack step itself was measured for this survey: **3.4 s wall clock** for a trivial
two-bundle `content-app` on Godot 4.7.1 mono, including project scan (`real 0m3.430s`).
That is the floor and it is dominated by editor startup, not by packing, so it will not
grow much with bundle size.

Adding the `dotnet build` of the plugin that precedes it, the honest loop for a C# service
change is roughly: **build (seconds, project-dependent) → pack ~3.5 s → detect ≤0.75 s →
unload/reload (sub-second)**. Against the alternative — full `task build:app` plus relaunch
plus re-reaching the app state you were testing — that is the difference the owner is
buying. It is also why the prior Orc Bot's own rule was blunt:

> The app stays **running ~95%** of the time. Bundle changes hot-reload into the **live
> app** and you verify via the assist bridge — **not** kill/relaunch … Only `task
> build:app` turns it off (and it **wipes bundles + seed** — re-run … after).

(prior-attempt (2026-06-25) orc-bot/docs/concepts/bundle-tiers.md:24-31)

Note the trap in that quote: a full app build wipes the bundles directory, so bundles must
be rebuilt after it. And: *"never commit between `build:app` and a hot-reload proof"* —
GitVersion moves the artifact directory out from under the running app
(prior-attempt (2026-06-25) orc-bot/docs/concepts/bundle-tiers.md:20-22). Both are direct
consequences of ADR-0005's one-artifact-root-per-commit and neither is a reason to change
it.

---

## 4. The C# half

### 4.1 PCK and assembly are one artifact, not two

A managed bundle's `.pck` **contains** its assembly (raw, or base64 in
`<name>.dll.payload.json`, §1.4) plus a `.deps.json` sidecar. There is no separate
assembly artifact and no NuGet feed in the loop. On load, the assembly is extracted out of
the PCK's `res://` tree onto real disk, because `AssemblyLoadContext` needs a filesystem
path:

```csharp
var bytes    = ReadPayloadBytes(payloadResPath);            // base64-decoded if wrapped
var loadId   = Interlocked.Increment(ref s_loadSeq);
var tempDir  = Path.Combine(SessionTempRoot, BundleTempName(bundleResPath), loadId…);
var tempPath = Path.Combine(tempDir, Path.GetFileName(StripPayloadSuffix(dllName)));
File.WriteAllBytes(tempPath, bytes);
CopySidecarIfPresent(logicalResPath, tempPath, ".deps.json");
```

(prior-attempt (2026-06-25) orc-bot/project/plugins/Plugin.Orc.Bundles/OrcDllExtractor.cs:28-47, 58-81)

`SessionTempRoot` is `<temp>/orc_bot_bundles/<pid>-<guid>`, because a PID alone gets reused
by Windows and a stale DLL from a prior run can be loaded before the current bundle is
extracted. `loadId` is monotonic per extraction, so a reload never writes over a file the
not-yet-collected old ALC still holds — which was the original `IOException` bug.
(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/DllExtractor.cs:9-31)

### 4.2 How the ALC is unloaded, and how collection is proven

`RemoveGroupAsync` only *initiates*. The library is explicit that a successful
`Directory.Delete` is **not** proof:

> a sound "bundle unloaded" signal for hot-reload is a `WeakReference` to the ALC plus a
> forced GC — not a successful `Directory.Delete` (on macOS/Linux, unlinking a
> still-mapped DLL succeeds regardless of ALC liveness, a false positive).

(scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Abstractions/IPluginHostDiagnostics.cs:15-20)

The proof is an opt-in diagnostics interface — `IPluginHostDiagnostics.RemoveGroupWithDiagnosticsAsync`
returns a `PluginUnloadResult` exposing `IsCollected`, and the host polls it on its own
cadence; the library never loops
(same file, :21-34). Underneath:

```csharp
public bool IsContextCollected(bool forceGC = false)
{
    if (_contextWeakRef is null) return true;
    if (forceGC)
        for (var i = 0; i < 10 && _contextWeakRef.IsAlive; i++)
        { GC.Collect(); GC.WaitForPendingFinalizers(); }
    return !_contextWeakRef.IsAlive;
}
```

(scarlet-projects/plugin-archi/dotnet/src/PluginArchi.Extensibility.Hosting/IsolatedLoader.cs:191-208)

Neither prior tree calls it. Both instead drive the GC themselves and use *deletability of
the temp directory* as the proxy — up to 16 rounds of 250 ms with a
`GC.Collect()`/`WaitForPendingFinalizers()`/`GC.Collect()` between, logging any directory
still pinned at the end and leaving it for the next reload or process exit.
(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleHost.cs:209-270)
Per the quote above, that proxy is sound on Windows and a false positive on Unix. **A
successor should call the diagnostics interface, not delete a directory.**

The reason cleanup cannot be synchronous is recorded precisely and is the most transferable
sentence in the whole body of work:

> the resident UI holder (`UiPanelService`) does NOT drop its reference to the old
> view-model here — `OnRegistryChanged` merely flags a rebuild, and the actual dispose runs
> on the next `_Process` frame, which cannot execute until this method returns control to
> the engine. So at THIS instant the old ALC is still pinned and a synchronous delete would
> always lose the race…

(prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleHost.cs:192-200)

### 4.3 What pins an ALC, and what was done about it

The three-layer rule is the answer to S8's second objection, and it predates the objection:

> 1. **PCK layer** — Godot resources … Scene structure is hot-swappable; exported-build
>    GDScript logic is not.
> 2. **Resident managed layer** — loaded once … **Never unloaded.** *Anything deriving from
>    a Godot type (`Node`, `Control`, `Resource`, `RefCounted`, `GodotObject`) MUST live
>    here.*
> 3. **Collectible ALC layer** — plain-C# plugin assemblies … **Unloadable.** *Only plain
>    C# with no Godot base type may live here.*

(prior-attempt (2026-06-25) fantasim-app-godot/vault/architecture/load-unload-by-tier.md:14-28)

with the mechanism spelled out:

> A `Node`-derived C# object lives in the Godot SceneTree and is referenced by Godot's
> native side, which is in the parent/default context. So a Godot-derived type loaded into
> a collectible ALC pins that ALC **forever** — `Unload()` is initiated but the context is
> never collected, the DLL handle is never released, and "unload" becomes a lie.

(same file, :80-90)

The tier mapping onto those layers, and the linchpin:

| Tier | Role | Attribute | Layer | Unloads? |
|---|---|---|---|---|
| 1 | Service interface | `[ServiceContract]` | Resident, in a `*.Contracts` assembly, shared with the parent ALC | No |
| 2 | Service proxy (source-generated) | `[RealizeService(typeof(IFoo))]` | Resident | No |
| 3 | Real service | `[ServiceImplementation]`/`[AutoRegister]` | Collectible ALC, plain C# only | **Yes** |
| 4 | Provider | `[ServiceProvider]` | Collectible ALC | **Yes** |

> **The linchpin:** the generated Tier-2 proxy calls `_registry.Get<IFoo>(…)` on **every
> method invocation** — it does not cache the resolved implementation. So to hot-swap a
> Tier-3 implementation you `Unregister` the old + `Register` the new … and the next call
> through the resident proxy picks up the new impl. **No caller is recompiled, re-wired, or
> even aware.**

(same file, :124-141)

So the four tiers are not an optional extra beside the bundle mechanism — **the T2 proxy is
what makes a bundle swap invisible to callers.** Remove it and every resident caller has to
be told about the swap by hand. S8 evaluated the tiers as a services pattern and missed
that they are the reload mechanism's calling convention.

Where a plain-C# service must touch the scene, it publishes rather than holds:
`WorldGlobeBackendPlugin` does `_bus.Publish(new ApplyPlateColorsCommand(...))` and a
resident `WorldGlobeScene` subscribes and mutates the mesh
(same file, :143-148). The note explaining *why that particular plugin collects cleanly* is
the reusable checklist: it only **publishes** to the bus (never subscribes → no host→ALC
delegate), holds no Godot `Node`/`Resource` across calls, and `PluginGroup.UnloadAsync`
clears its instances. A plugin that leaves a `Node` in the tree, holds a bus
*subscription*, or is cached as a `Func`/`Type` in the host logs "old ALC NOT collected"
— *"that's the signal to add the matching teardown"*.
(prior-attempt (2026-06-25) fantasim-app-godot/vault/bundle-hot-reload-behavior.md:97-102)

Three of those five pinning patterns are caught at compile time:

| ID | Package | Flags |
|---|---|---|
| PLUG001 | `PluginArchi.Analyzers` (core) | A **static** field/property whose type is (or contains) a plugin type |
| PLUG002 | core | Registering a plugin implementation type as a **DI singleton** |
| PLUG007 | `PluginArchi.Analyzers.Godot` (**engine satellite**) | A plugin type retaining a **`Godot.GodotObject`** in a field/property |
| PLUG008 | core | A `[PluginSharedContract]` assembly that also declares a plugin implementation (over-sharing) |
| PLUG009 | core | A `[PluginSharedContract]` assembly whose public API exposes a type from an unshared assembly (under-sharing) |

(scarlet-projects/plugin-archi/docs/unload-safety-analyzers.md:40-49)

### 4.4 Type identity across the boundary

The second hard constraint. `typeof(IFoo)` in the host ALC is a different `Type` from
`typeof(IFoo)` in a collectible ALC, and every reference-equality check then fails
silently: discovery drops every plugin, MessagePipe's per-`T` dispatch never matches,
`IRegistry.Get<IFoo>()` returns null.
(prior-attempt (2026-06-25) fantasim-app-godot/vault/architecture/load-unload-by-tier.md:98-105)

The fix is two-part, and part one is easy to get wrong: Godot loads the game's managed
assemblies into an `IsolatedComponentLoadContext`, **not** `Default`, so plugin ALCs must be
parented to *that*:

```csharp
var hostContext = AssemblyLoadContext.GetLoadContext(typeof(Bootstrap).Assembly)
    ?? AssemblyLoadContext.Default;

PluginHost = new PluginHostBuilder()
    .ConfigureServices(services => { services.AddSingleton(Registry); })
    .WithParentContext(hostContext)
    .WithSharedPolicy(new SharedAssemblyPolicy(
        exactMatches: new[] { "Orc.Bot.Contracts", "Orc.Bot.Bundles.Contracts" },
        prefixes: new[] { "System.", "Microsoft.", "Godot", "GodotSharp", "netstandard",
                          "PluginArchi.", "ServiceArchi.", "Crosscut.", … }))
    …
```

(prior-attempt (2026-06-25) orc-bot/project/plugins/App.Composition/Bootstrap.cs:67-103)

The policy matches by `AssemblyName.Name` — the DLL name, not the NuGet package id. Note
`Godot`/`GodotSharp` are shared, which is what lets a value type like `Godot.Vector3` cross
the boundary in a DTO without pinning anything.

A hand-maintained allowlist was found to be a recurring bug source, with a list of specific
outages, so plugin-archi ≥ 0.1.3 replaced it: a contract assembly declares
`[assembly: PluginSharedContract]` once, and a source generator scans the host
compilation's referenced assemblies for that attribute and emits the policy at compile
time — AOT-safe, no startup reflection, and transitive because the compiler's reference set
is the transitive closure.
(scarlet-projects/plugin-archi/docs/rfcs/RFC-0014-self-describing-shared-contract-assemblies.md:8-77)
PLUG008/PLUG009 then police over- and under-sharing.

**Sharing solves identity; it does not solve versioning** — a bundle built against an older
contract still resolves the *same* `Type`, just one whose members have moved. That is what
the §2.2 ABI fingerprint is for, checked before a single line of bundle code runs:

```csharp
if (!string.Equals(requirement.Fingerprint, actualFingerprint, StringComparison.Ordinal))
    throw new InvalidOperationException(
        $"Bundle '{bundleId}' requires shared assembly '{requirement.AssemblyName}' public API fingerprint "
        + $"'{requirement.Fingerprint}', but the running host has '{actualFingerprint}'. "
        + "Rebuild and restart the exported app before reloading this bundle.");
```

(prior-attempt (2026-06-25) orc-bot/project/plugins/Plugin.Orc.Bundles/OrcBundleCompatibilityGuard.cs:16-45)

Together with the §3.2 rollback, that is the pair that makes hot reload safe rather than
merely fast: a stale bundle is rejected with an actionable message and the previous bundle
stays live.

---

## 5. Generalising beyond Godot

The uniform-architecture claim is not aspirational — a cross-engine implementation of
exactly this shape already exists in the family, in `game-foundation`, and its dependency
graph is the answer to this question:

| Artifact | Tier | Depends on |
|---|---:|---|
| `GameFoundation.Resource.Contracts` | T1 | none |
| `GameFoundation.Resource.Proxy` | T2 | Resource T1 |
| `com.giantcroissant.game-foundation.resource` | **Unity T3** | Resource T1 |
| `com.giantcroissant.game-foundation.resource.addressables` | **Unity T4** | Resource Unity T3 |
| `GiantCroissant.GameFoundation.Resource.Godot` | **Godot T3** | Resource T1 |
| `GiantCroissant.GameFoundation.Resource.Godot.Pck` | **Godot T4** | Resource Godot T3 |

> Addressables code exists only in Resource Unity T4; PCK mounting and `ResourceLoader`
> calls exist only in Resource Godot T4.

(scarlet-projects/game-foundation/README.md:62-90)

and the T1 rule that makes it hold:

> No engine object, address, path, operation handle, PCK, Addressables, or `UniTask` type
> crosses T1. Composition maps logical IDs to backend locations.

(scarlet-projects/game-foundation/README.md:24-27)

### 5.1 The split

**Engine-neutral** — these move to Unity and plain C# unchanged:

- The **tier attributes and the T2 proxy**. `[ServiceContract]`, `[RealizeService]`,
  `[ServiceImplementation]`, `[ServiceProvider]`, the analyzer that enforces the reference
  rules, and the per-call `ResolveService()` generated forwarder. Nothing about them is
  Godot.
- **Registry ownership.** Owner-scoped registration/removal is what makes a swap atomic
  from the caller's point of view; it is a dictionary, not an engine feature.
- **Manifest, ABI fingerprint, digest addressing.** JSON, sha256 over a canonical
  rendering, `payloads/sha256/<xx>/<64-hex>.bin`. The fingerprint computation is pure
  reflection over `GetExportedTypes()`.
- **`PluginArchi.Analyzers` core (PLUG001/002/008/009)**, which "must never reference or
  name a game engine".
- **The three-method bundle reader.** `IRuntimeBundle` with `DirectoryBundle` for plain C#
  and `DelegateBundle` for an engine VFS is the carrier seam in its final form.

**Godot-specific** — one file each, ideally:

- `.pck` as the container, `ProjectSettings.LoadResourcePack`, `ResourceLoader.CacheMode.ReplaceDeep`,
  `res://` path arithmetic, `--export-pack` and `export_presets.cfg`.
- The **resident Node layer** and `residentScripts` binding.
- **PLUG007**, which lives in `PluginArchi.Analyzers.Godot` precisely so the string
  `"Godot.GodotObject"` appears in exactly one place. The satellite pattern is documented
  with a five-step recipe for adding a Unity one whose only difference is
  `type.DerivesFrom("UnityEngine.Object")`.
  (scarlet-projects/plugin-archi/docs/unload-safety-analyzers.md:51-82)

### 5.2 The Unity equivalent

- **Content** → an **AssetBundle** or an Addressables group. The T4 already exists
  (`AddressablesResourceProvider`, `IUnityResourceAddressResolver`). Unity is *better* here
  than Godot, not worse: `AssetBundle.Unload` genuinely unmounts, so the §3.2 shadow trick
  is unnecessary on Unity — but the shape (mount, read manifest, instantiate entry, release
  by lease) is identical.
- **Code** → **not a collectible ALC.** Unity's runtime does not offer one; plugin-archi's
  own guidance is `DefaultContextLoader` + source-generated registration for a Unity game
  build, and `DirectoryLoader` for hot-reload **in the editor** only.
  (scarlet-projects/plugin-archi/docs/rfcs/RFC-0005-plugin-loading-hosting.md:625-634)
  So the Unity T3 hot-swap is editor-domain-reload, and a shipped Unity build gets
  *replaceable content* plus *statically-registered code*. The tier architecture is the
  same; the reload guarantee is weaker and must be stated as such rather than assumed.
- **Manifest** → identical JSON, `managed.assemblies[].kind = "dll"`, plus the same ABI
  fingerprint, which is *more* valuable on Unity because a mismatched assembly cannot be
  hot-corrected.

### 5.3 The plain-C# equivalent

The easiest of the three, and the one that should be built **first** because it needs no
engine at all:

- **Content** → a **directory or a `.zip`/`.nupkg`**. `ManagedAssemblyKind` already spells
  `Dll | Nupkg | Zip`
  (prior-attempt (2026-06-25) fantasim-app-godot/project/plugins/App.Bundles.Core/BundleManifest.cs:161-167),
  and `DirectoryBundle` is the reader.
- **Code** → a **collectible ALC**, natively, with no extraction step, no PCK, and no
  `res://` — this is the case .NET actually supports. `IPluginHostDiagnostics` proves
  collection.
- **Manifest** → unchanged.

Which is the real argument for taking this design: **the plain-C# case is the simple one,
and Godot is the one paying a tax** (no unmount, a mandatory extraction to disk, a resident
Node layer, a packing project). Building the neutral core first and treating `.pck` as one
carrier among three is both cheaper and a better test of the abstraction than starting from
Godot.

---

## 6. What Orc Bot should do

### 6.1 `content-app` — what it must contain

Today it is the 2026-07-18 empty skeleton. It needs, in order:

1. **`export_presets.cfg`**, currently absent. One `[preset.N]` per bundle, plus a
   `runnable=false`, `export_path=""` base preset with `exclude_filter="bundles/*"` if a
   whole-content pack is ever wanted. Each bundle preset:
   `export_filter="customized"`, `include_filter="bundles/<id>/*"` (**required** — §1.4:
   without it a raw `.dll` is dropped), `exclude_filter` naming every *other* bundle
   (**required** — §1.3), `script_export_mode=2`.
2. **A generator + CI check for those exclude lists.** Port
   `tools/scope_bundle_presets.py` and wire its `--check` into `task verify`. A hand-edited
   exclude list is one forgotten line away from a silently-shadowed bundle.
3. **`bundles/` as a junction** to `project/bundles/`, created and validated by a Taskfile
   precondition, plus `/bundles` in `project/hosts/content-app/.gitignore`.
4. **Nothing else.** No `.csproj`, no `.sln`, no scenes. `content-app` is a packer, and
   both prior attempts kept it that way.

It also needs one thing neither prior attempt had: a **decision about the root-level files
every bundle PCK carries** (`project.binary`, `icon.svg`, the `.godot` caches — §1.5).
Simplest defensible answer: keep them, mount with `replace_files: true` as today, and
record in `docs/host/` that a bundle PCK shadows those five host paths by design. If that
turns out to matter, the fallback is a bundle-specific mount with `replace_files: false`
plus a fresh `res://` prefix per version — which costs the shadow-based reload and should
not be chosen without a reason.

### 6.2 New `project/bundles/`

A sibling of `contracts/`, `libs/`, `plugins/`, `hosts/` — not inside a Godot project.
One directory per bundle, each holding `manifest.json` and its sources. Staged build
products (`*.dll`, `*.payload.json`, `*.deps.json`, `*.pdb`) are **gitignored**, exactly as
the prior attempt did
(prior-attempt (2026-06-25) orc-bot/.gitignore:20-26) — this is
[ADR-0004](../adr/0004-derived-state-and-tool-authority-slots.md) applied one level down,
and `Assert-NoTrackedDerivedState.ps1` should learn these patterns.

### 6.3 Taskfile targets

```
task bundles:link          ensure project/hosts/content-app/bundles is a junction; fail if it exists and isn't
task bundle:stage:<id>     dotnet build the plugin, base64-stage its assembly + deps.json into project/bundles/<id>/,
                           stamp requires.sharedAssembly.*.publicApiFingerprint into the manifest
task bundle:<id>           deps: bundles:link, artifacts, bundle:stage:<id>
                           "$GODOT4_BIN" --headless --path project/hosts/content-app \
                               --export-pack "<id> PCK" build/_artifacts/<version>/bundles/<id>.pck
task bundles               every bundle, SEQUENTIALLY via cmds: (one .godot project lock)
task bundles:presets:check tools/scope_bundle_presets.py --check   → wire into task verify
```

`task artifacts` already creates `build/_artifacts/<version>/bundles/`, so the output
directory precondition (§1.1) is satisfied by an existing dependency rather than a new
`ensure-dir` helper. `task bundles` must **not** be a `deps:` of `godot:export` — a host
export wipes the artifact tree, so bundles are rebuilt after it, and that ordering should be
explicit rather than emergent.

### 6.4 Where bundles land, and the one conflict to resolve

**Bundles land at `build/_artifacts/<version>/bundles/`.** That is already ADR-0005's
layout and it is the right one; fantasim's `godot/win-x64/bundles` was a workaround for a
hard-coded resolver.

The conflict: `GodotBundleDirectoryResolver` computes `<exe-dir>/bundles`, and the exported
host lives in `godot/win-x64/`. **Do not move the artifacts to match the resolver.** Make
the bundles directory *configuration* — which is what
[ADR-0004](../adr/0004-derived-state-and-tool-authority-slots.md) already says validation
targets are — resolved in this order:

1. an explicit setting/CLI argument, used by `orc` when it launches the host;
2. `build/_artifacts/latest/bundles`, resolved through the stable symlink;
3. `<exe-dir>/bundles` as the shipped-app fallback.

Option 2 is why ADR-0005 insists `latest` is a symlink and not a copy: a running host
pointed at `latest/bundles` sees a freshly packed bundle the moment it is written.

### 6.5 Changes to RFC-0001

S8 recommended no changes. This survey recommends four, all additive:

1. **W5 gains the acceptance criteria S8 already identified, plus two.** Owner-scoped
   registry cleanup; an explicit shared-contract policy (via `[assembly: PluginSharedContract]`,
   not a hand-typed list); a retained-reference *negative* unload test beside a positive
   one; **collection proven through `IPluginHostDiagnostics.RemoveGroupWithDiagnosticsAsync`,
   not by deleting a directory** (§4.2 — the delete proxy is a false positive on Unix); and
   **an ABI-fingerprint constant on every shared contract, with a test asserting it matches
   the recomputed surface** (§2.2).
2. **A new work item — the engine-neutral bundle core, before any Godot work.**
   `OrcBot.Contracts` gains the manifest model, `ManagedAssemblyKind`, the three-method
   bundle reader, and a `DirectoryBundle`; `libs/` gains load/unload/reload over a
   collectible ALC with the compatibility guard and rollback. This is testable with
   `dotnet test` and no engine, and it is the piece Unity and plain C# reuse verbatim (§5.3).
3. **W12 gains PCK packing, and is honest about what it buys.** `content-app` per §6.1,
   the Godot carrier as a `DelegateBundle` over `res://`, the resident-Node/collectible-ALC
   split, and the watcher. The claim to make is the measured one: **C# service behaviour
   hot-reloads live; scene structure re-instantiates; GDScript logic does not reload in an
   exported build and needs a restart** (§3.3). W12 keeps its fresh-Godot-process reload as
   the answer for a changed *host*; hot reload is the answer for a changed *bundle*.
   Godot's cache stays seeded per allocation under
   [ADR-0009](../adr/0009-seed-engine-caches-do-not-share-them.md) — unchanged, and now
   with a second reason: two packers on one `content-app` contend on the same `.godot`.
4. **A note that the four tiers are in scope after all**, with the reason S8 lacked: the
   T2 per-call proxy is not a services convenience, it is the calling convention that makes
   a T3 swap invisible (§4.3). Adopt `[ServiceContract]`/`[RealizeService]` where a
   contract has a hot-swappable implementation. This does not reopen S6's rejection of
   DependencyArchi, CrosscutFoundation Hosting/Messaging, or GameFoundation as dependencies
   — `game-foundation` is cited here as the **proof that the shape generalises**, not as a
   package to take.

### 6.6 What not to copy

- **Filename-prefix load ordering.** `plugin-*` before everything else is a heuristic
  standing in for a dependency graph. Put `dependsOn` in the manifest and validate the
  closure at load; it is the weakest part of both prior attempts.
- **Directory-deletion as collection proof** (§4.2).
- **`LoadRemoteAsync` without a digest check.** If a bundle can arrive over HTTP, its bytes
  must hash to a value the manifest declares, per the 2026-08-03 payload model (§2.4).
- **A hand-maintained `SharedAssemblyPolicy` list.** RFC-0014 exists because that list is a
  documented, repeated outage source.

---

## Appendix: sources

| Source | What it holds |
|---|---|
| prior-attempt (2026-06-25) `fantasim-app-godot` | 22 bundles, `content-app` with 37 KB of presets, `App.Bundles.Core`, the canonical tier doc, the hot-reload behaviour note, `scope_bundle_presets.py` |
| prior-attempt (2026-06-25) `orc-bot` (attempt 1) | 3 bundles, `content-app`, `Plugin.Orc.Bundles`, the ABI guard, `stage-managed-bundle.ps1`, reload rollback, per-load PCK copy |
| prior-attempt (2026-07-18) `fantasim-app-godot` | the vestigial empty `content-app` that orc-bot's current one is a byte-identical copy of |
| prior-attempt (2026-08-03) `fantasim-app-godot` | `IRuntimeBundle`, `manifest.rwp` + `payloads/sha256/…`, `DirectoryBundle`/`DelegateBundle` |
| `scarlet-projects/plugin-archi` | `SharedAssemblyPolicy`, `IsolatedLoader.IsContextCollected`, `IPluginHostDiagnostics`, PLUG001–009, RFC-0005, RFC-0014 |
| `scarlet-projects/game-foundation` | the cross-engine T1/T2/T3/T4 resource family: PCK on Godot, Addressables on Unity |
| `scarlet-projects/service-archi` | tier attributes, the tier-reference analyzer, the non-caching proxy generator |
| measured 2026-08-16 | Godot 4.7.1 mono, scratch two-bundle `content-app`: `--export-pack` timing, missing-output-directory failure, `include_filter` scoping, the `.json`-vs-`.dll` carriage asymmetry, root-level PCK contents |
