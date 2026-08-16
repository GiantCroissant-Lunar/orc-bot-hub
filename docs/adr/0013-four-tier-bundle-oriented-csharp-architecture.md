# ADR-0013: Four-tier, bundle-oriented C# architecture

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0004, ADR-0009, ADR-0012
- Evidence: [S8](../surveys/S8-fantasim-bundles-and-tiers.md), [S11](../surveys/S11-bundle-packing-and-content-app.md)
- Reverses: S8's recommendation "do not take the four-tier architecture"

## Context

S8 surveyed `fantasim-app-godot`, described the four tiers accurately, and then
recommended against adopting them — on the grounds that the T2 per-call proxy
solves live replacement of *game services*, which an orchestrator does not need.

That recommendation was made without the requirement. The four-tier,
bundle-oriented design is not a game pattern here: it is intended as the
**uniform architecture for all C# development in this workspace** — Godot, Unity,
and plain C# alike — and bundle orientation is what makes that development
hot-reloadable. Judged against *that*, "an orchestrator does not need live
service swap" is answering a question nobody asked.

S11 then established that this is not aspirational. `game-foundation` already
ships the cross-engine version, and its dependency graph is the proof:

| Artifact | Tier | Depends on |
| --- | --- | --- |
| `GameFoundation.Resource.Contracts` | T1 | nothing |
| `GameFoundation.Resource.Proxy` | T2 | Resource T1 |
| `…game-foundation.resource` (Unity) | T3 | Resource T1 |
| `…resource.addressables` (Unity) | T4 | Unity T3 |
| `…Resource.Godot` | T3 | Resource T1 |
| `…Resource.Godot.Pck` | T4 | Godot T3 |

Addressables code exists only in the Unity T4; PCK mounting only in the Godot T4.
The same T1 and T2 serve both.

S11 also found that **the first Orc Bot attempt already built all of this** —
`content-app`, `project/bundles/*`, a Taskfile driving `--export-pack`, an
ABI-fingerprint compatibility guard, and reload rollback. S8 missed it by looking
only at fantasim. The `content-app` currently in this repository is byte-identical
to a vestigial empty skeleton from a 2026-07-18 snapshot: the shell, not the
working version.

## Decision

**Adopt the four tiers as the C# architecture, across engines.**

| Tier | What it is | Lifetime | May reference |
| --- | --- | --- | --- |
| **T1** | service *interface*, `[ServiceContract]` | resident, never unloads | T1 |
| **T2** | generated *proxy*, `[RealizeService]` | resident, never unloads | T1 |
| **T3** | *implementation*, `[ServiceImplementation]` | collectible, unloadable | T1, T3 — **not T2** |
| **T4** | *provider*, `[ServiceProvider]` | collectible, unloadable | T3, T4 — **not T1** |

The reference rules are enforced by a Roslyn analyzer, not by convention. T2's
generated members forward through a per-call `ResolveService()`, which is what
makes replacing a T3 implementation visible to resident callers on the next call
without rebuilding them.

**No engine type crosses T1.** No engine object, address, path, operation handle,
PCK, Addressables type, or `UniTask` — composition maps logical ids to backend
locations. This one rule is what makes the same T1/T2 serve Godot, Unity, and a
console app.

**Adopt bundle orientation, with `content-app` as a packer.** Godot can only
produce a `.pck` through its editor, so `project/hosts/content-app` exists to be
driven headless:

```bash
"$GODOT4_BIN" --headless --path project/hosts/content-app \
    --export-pack "<id> PCK" build/_artifacts/<version>/bundles/<id>.pck
```

It contains `export_presets.cfg`, a junction to `project/bundles/`, and **nothing
else** — no `.csproj`, no `.sln`, no scenes. Both prior attempts kept it that way.
Bundles are authored in `project/bundles/<id>/` as a sibling of `contracts/`,
`libs/`, `plugins/`, and `hosts/`, and their staged build products are gitignored
(ADR-0004, one level down; `Assert-NoTrackedDerivedState.ps1` learns the patterns).

### The two constraints, and how they are actually resolved

S8 raised both as reasons not to proceed. They are real, and both were already
solved:

**Godot cannot unmount a PCK — so nothing unmounts one.** Each load copies the
PCK to a fresh per-load temp path and mounts it with `replace_files: true`, so
the newer mount shadows the older at the same `res://` path. The cost is bounded
VFS growth of one entry set per reload. The prior Orc Bot turned that cost into a
feature: the previous copy is the **reload rollback**.

**A Godot `Node` pins a collectible ALC — so nothing Godot-derived ever enters
one.** That is precisely what "T1 and T2 are resident" means: the resident layer
is the engine surface, the collectible layer is plain C#, and they communicate
over a message bus. Enforced by analyzer `PLUG007`, which lives in a Godot
satellite package so that the string `Godot.GodotObject` appears in exactly one
place — the documented recipe for a Unity equivalent differs only in deriving
from `UnityEngine.Object`.

### Three hazards measured on Godot 4.7.1 for this decision

1. **The exporter silently drops a raw `.dll` from a bundle unless
   `include_filter` names it**, while always carrying `.json`. This is why the
   prior attempt base64-wrapped every plugin assembly into a `.dll.payload.json`
   — a workaround whose reason was never written down until now.
2. **`include_filter` does not scope a bundle PCK in 4.7.1.** The documented 4.6
   gotcha reproduces exactly; `exclude_filter` does work. Every bundle preset must
   therefore exclude every *other* bundle, which is one forgotten line away from a
   silently-shadowed bundle — so the exclude lists are **generated and
   `--check`ed in `task verify`**, never hand-maintained.
3. **Every bundle PCK carries `res://project.binary`, `res://icon.svg`, and the
   `.godot` caches**, and mounting with `replace_files: true` shadows the host's.
   Nothing in the prior work addresses this. Accepted deliberately: keep them,
   and record in `docs/host/` that a bundle shadows those host paths by design.
   The fallback — `replace_files: false` plus a fresh `res://` prefix per version
   — costs the shadow-based reload and needs a reason.

### Non-Godot targets

- **Unity**: a bundle is an AssetBundle or Addressables group, and the T4 already
  exists. Unity is *better* here — `AssetBundle.Unload` genuinely unmounts, so the
  shadow trick is unnecessary. Code, however, is **not** collectible: Unity's
  runtime offers no collectible ALC, so a player build uses source-generated
  registration and hot reload is editor-only.
- **Plain C#**: a bundle is a directory. `IRuntimeBundle` with `DirectoryBundle`
  for the filesystem and `DelegateBundle` for an engine VFS is the carrier seam.

## Consequences

- `task verify` grows a preset-scope check, and the derived-state gate grows
  bundle staging patterns.
- Bundle builds must run **sequentially** — one `.godot` project lock — and must
  not be a dependency of `godot:export`, because a host export wipes the artifact
  tree. That ordering is explicit, not emergent.
- The bundles directory becomes **configuration**, resolved from an explicit
  setting first. The prior resolver computed `<exe-dir>/bundles`, which does not
  match ADR-0005's `build/_artifacts/<version>/bundles/`; the layout is right and
  the resolver moves, not the artifacts.
- S6's "do-not-adopt GameFoundation" was judged against the wrong question too.
  It is the reference implementation of the cross-engine tier split, and is
  revisited when the second engine appears.
- Hot reload becomes a property of the development loop rather than a feature to
  build later, which is the point.

## Alternatives considered

**Keep S8's recommendation and build Orc Bot as a plain layered app.** Rejected.
It optimises for this one program and gives up the reason the architecture exists
— that every C# project in the workspace has the same shape.

**Adopt the tiers but skip bundles, shipping everything in the host.** Rejected:
bundles are the delivery mechanism that makes T3/T4 replaceable at runtime.
Without them the tier split is bookkeeping.

**Wait until a second engine actually appears.** Rejected: the T1 rule ("no engine
type crosses") is nearly free to hold from the start and expensive to retrofit,
because by then engine types are in the contracts.
