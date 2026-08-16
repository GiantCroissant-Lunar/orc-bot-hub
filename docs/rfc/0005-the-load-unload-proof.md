# RFC-0005: The load/unload proof

- Status: Proposed
- Date: 2026-08-16
- Depends on: ADR-0013, ADR-0015, ADR-0016

## What this is

A small experiment that proves a managed component can be loaded, replaced, and
**collected** inside the exported Godot binary — and that each way of leaking
fails the test for its own reason.

Not a module framework. The point is to learn which boundary can be mechanically
enforced in the Godot 4.7.x C# host before designing anything on top of it.

## Why before the framework

ADR-0016 describes a replacement transaction ending in proof of collection. That
proof is the only part that cannot be reasoned about from documentation:
`Unload()` returning is not evidence of anything, and the exported player's
assembly-loading path is exactly where behaviour differs from the editor and from
`dotnet test`.

The prior attempt built `PluginArchi`/`ServiceArchi` and a bundle framework, and
the rules that survived are a handful of invariants (ADR-0016) rather than the
framework around them. Proving the invariants first and building the smallest
layer that satisfies them is the opposite order, deliberately.

## The spike

One exported Godot C# process, one shared contract, two revisions of one plain
managed component.

1. The exported app stays running. A resident `Control` displays a string obtained
   through a shared `IOrcComponent` contract.
2. Load revision A into a collectible ALC using `AssemblyDependencyResolver`. The
   ALC **explicitly delegates the contract assembly** to
   `AssemblyLoadContext.GetLoadContext(typeof(IOrcComponent).Assembly)` rather
   than assuming `Default`.
3. The component may carry its own dependency versions. It has **no GodotSharp
   reference** and exposes only shared DTOs.
4. Activate A through an `EffectScope`, render its result through the resident
   node, then load B without touching A.
5. Atomically swap the owner/generation registration A→B, dispose A's effects,
   call `Unload()`, and prove collection via `WeakReference`.
6. Repeat A→B→C about 100 times, watching managed memory, loaded assemblies, open
   files, event handlers, and Godot behaviour.

## The adversarial matrix

A spike that only tests the happy path proves that nothing was leaked *this
time*. Each of these is introduced deliberately and **must fail the test for its
expected reason** — a leak that does not fail is the finding.

| Injected fault | Expected failure |
| --- | --- |
| Resident code retains a delegate into the component | Not collected |
| Static host cache holds a component object | Not collected |
| Component leaves a `Task` running | Not collected |
| Serializer reflects over a component-defined type | Not collected |
| Contract DLL duplicated into the component's own folder | Type identity mismatch, not a silent second contract |
| Effect registered outside the `EffectScope` | Survives disposal |

And the lifecycle races ADR-0015 names, which Cordis's own open issues show are
real: A→B→A during asynchronous activation, child-scope teardown reaching parent
registrations, provider removal during dependent startup, partial activation
failure, double disposal, and cancellation mid-load.

## Acceptance

*Done when 100 A→B→C cycles run inside the exported binary with every revision
collected, and every fault above fails for its own reason rather than passing
quietly.*

Plus one honest negative result: **whichever of these cannot be made to work is
the more valuable output.** If a Godot-hosted collectible ALC cannot be made to
collect reliably in the exported player, that is the finding, and it moves the
extension story to out-of-process — which ADR-0016 already lists as the third
deployment policy.

## Open questions

- **What exactly pins an ALC in the exported player?** The next research step is
  Godot's `PluginLoadContext`, `ScriptManagerBridge`/`GCHandle` lifetime, and the
  exported C# assembly-loading path. That would turn "nothing Godot-derived enters
  a collectible ALC" from a rule into a mechanically checkable one.
- **Does attribute-based discovery drag attribute assemblies into the shared
  identity contract?** The prior attempt found that reflecting custom attributes
  makes the CLR resolve their defining assemblies. If so, discovery metadata is
  part of the contract surface and must be designed as such.
- **Is `EffectScope` sufficient on its own**, or does unloadability also need the
  registry to hand out resident proxies rather than component objects? ADR-0016
  leans toward proxies; this spike can settle it with evidence.
