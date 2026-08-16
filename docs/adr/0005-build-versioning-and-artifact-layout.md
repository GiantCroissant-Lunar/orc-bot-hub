# ADR-0005: UnifyBuild, GitVersion, and one artifact root per commit

- Status: Accepted
- Date: 2026-08-16

## Context

Orc Bot produces more kinds of output than a normal .NET repository: NuGet
packages, published hosts, a Godot export, screenshots taken during windowed
validation, `.pck` bundles for hot-reloaded content, and evidence files attached
to attempts. In the previous attempts these landed wherever the tool that
produced them defaulted to, and correlating "which screenshot belongs to which
build" was guesswork.

Two prior failures are worth naming, because they both looked like success:

- A Godot export without a `.sln` exits 0 and ships an application containing no
  managed assemblies.
- A Godot C# project referencing `GodotSharp` without the source generators
  compiles and runs, but never receives `_Ready`, `_Process`, or `_Notification`.

Both produce green builds and a broken product.

## Decision

**Build is [UnifyBuild](https://github.com/GiantCroissant-Lunar/unify-build),
consumed as a dotnet tool**, configured by `build/build.config.json`. Task is the
entrypoint; nobody calls `dotnet build` directly in a script.

**GitVersion is the only version authority.** `build/scripts/Get-BuildVersion.ps1`
resolves it once and exports it as `ORCBOT_BUILD_VERSION`, which is also
UnifyBuild's `versionEnv`, so the tool and the scripts cannot disagree about the
folder name.

**Every artifact for a commit lives under `build/_artifacts/<version>/`**, with a
fixed set of subfolders created up front:

```
nuget/  hosts/  godot/  rust/  bundles/  screenshots/  logs/  evidence/
```

**`build/_artifacts/latest` is a relative directory symlink to the current
version folder.** Everything outside the build — docs, tooling, agent briefs,
Godot export presets — refers to `latest`. It is a symlink and not a copy, so
anything written into the version folder afterwards is immediately reachable
through the stable path.

**net8.0 is the floor.** GodotSharp 4.7.1 ships `lib/net8.0`, and the Godot host
references the contracts directly, so contracts cannot target something the host
cannot consume. Raising the floor means checking Godot first.

**Rust via gdext is a documented seam, not v0 scope.** `IUnifyRust` is not
composed into the UnifyBuild CLI, so a Rust target needs a custom NUKE build. C#
plus a Rust GDExtension has been verified end to end in the mono build, with two
constraints recorded for whenever it lands: a new `.gdextension` is silently
inert until `--import` writes `extension_list.cfg` (`task godot:import`), and
C#→gdext calls are dynamic only.

## Consequences

- "Which build is this screenshot from" is answerable by path.
- A stale artifact cannot masquerade as a fresh one, because the version folder
  changes with the commit.
- `build/_artifacts/latest` requires symlink capability. Present here; on a
  machine without it, the sync script fails loudly rather than silently copying.
- Godot web export is permanently out of scope for this host: the engine gates
  C# out of Web entirely, and the mono editor refuses the Web preset even for
  pure GDScript. Web would need a second, separate binary.

## Alternatives considered

**A hand-written NUKE build in-repo.** Rejected: UnifyBuild already implements
the versioned-artifact layout, the `latest` sync, and Godot export orchestration,
and it is maintained across the sibling repositories. Divergence here would be
pure cost.

**Flat `build/output/` with timestamped filenames.** Rejected: it makes the
correlation implicit and it makes `latest` impossible to express as one path.
