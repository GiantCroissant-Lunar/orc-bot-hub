# RFC-0004: Memory in the exported host

- Status: Proposed
- Date: 2026-08-16
- Depends on: ADR-0006, ADR-0012, ADR-0013, ADR-0014
- Deliberately does not depend on: ADR-0015, ADR-0016, ADR-0017, ADR-0018

## What this is

The exported Godot binary shows what previous attempts learned, read-only.

`orc memory search` already works from a shell. This makes the same retrieval
visible in the product, which ADR-0012 says *is* the product: one exported Godot
binary, with headless as the daemon.

## Why this one first

It is the smallest thing that makes the Godot host show real domain data, and it
needs none of the machinery just filed. Specifically:

- **No dynamic loading.** The surface is resident. ADR-0016's revision
  transaction is not exercised, and RFC-0005 is not a prerequisite.
- **No MPS, no design IR.** `visualAuthority = godot` (ADR-0017). Plain TSCN
  authored in the editor.
- **No composition plane.** One provider, one store, resolved at startup.

That makes it a genuine test of the *boundaries* rather than of new frameworks:
does the T1/T2/T3/T4 split from ADR-0013 survive contact with a real surface, and
does a Godot host consume the memory vocabulary without any engine type crossing
T1?

It also gives RFC-0005 something real to hot-swap later, instead of a synthetic
fixture built to be swappable.

## Scope

**In:**

- A resident memory surface in `complete-app`: query box, scope selector, results
  list, and the retrieval receipt for the query just run.
- Retrieval through the existing `OrcBot.Memory.Core` retriever and
  `OrcBot.Memory.Mem0` provider. No new retrieval logic.
- Read-only. No propose, approve, or reject from the UI.
- Provider-unavailable rendered **as unavailable**, with the reason, never as an
  empty result. This is the same rule the CLI already enforces and it matters more
  here, because an empty list in a UI reads as "nothing was learned".

**Out:**

- Writing memory from the UI. Promotion is a human decision that already has a
  path (`orc memory approve`), and adding a second one before the first is
  exercised would create two authorities for the same act.
- A2UI, AG-UI, agent-composed views.
- Any dynamic surface loading.

## Acceptance

*Done when a person launches the exported binary on a machine with the sidecar
running, types a query, and sees a fact a previous run promoted — with the
receipt digest visible — and sees an explicit unavailability when the sidecar is
stopped.*

The proof is the **exported** binary, not the editor. Prior attempts recorded
green build, green export, and green headless checks while the shipped window had
controls clipped off-screen; and a Godot C# export with no `.sln` beside
`project.godot` exits 0 and ships an app with no managed assemblies at all. So
acceptance is: run the export and look at it.

## Open questions

- **Does the daemon or the UI own the retrieval?** ADR-0012 makes headless the
  daemon and every UI a client. Doing this properly implies the surface calls an
  application command rather than constructing a provider itself — but W7's
  application surface does not exist yet. The stopgap is the same one RFC-0001
  sanctions for the CLI, and it must be fenced the same way: the surface calls the
  same handler the daemon will later serve, and owns no policy.
- **Where does the store live for an exported app?** The CLI defaults to an
  embedded SurrealKV path under `LOCALAPPDATA`. An exported host on the same
  machine should read the same store, which means the path is configuration, not
  a constant compiled into two places.
- **Does the embedded SurrealKV engine work inside the exported Godot host?** It
  works from `dotnet run`. The exported player's assembly-loading path differs
  (ADR-0016), and a native-dependency engine is exactly the kind of thing that
  differs. This is the first risk to retire.
