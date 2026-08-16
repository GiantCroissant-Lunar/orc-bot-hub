# ADR-0017: Meaning and look are two orthogonal IRs that meet at binding ids

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0003, ADR-0012, ADR-0013
- Informed by: [discussion/mps-ui.md](../discussion/mps-ui.md)

## Context

Orc Bot's UI has to absorb several tools that all claim to describe interfaces —
JetBrains MPS, Figma, Pencil `.pen`, and the agent-facing protocols AG-UI and
A2UI — plus Godot's own scene and theme system. Treating them as competitors
produces a matrix of importers: Figma→TSCN, Pen→TSCN, Figma→C#, MPS→TSCN, and so
on, each pair needing to understand the other's concerns.

They are not competitors. They describe different axes.

## Decision

**Two orthogonal intermediate representations, and neither consumes the other.**

```
      Orc.UI.IR                      Orc.DesignIR
   semantic behaviour              visual presentation
         ▲                            ▲        ▲
        MPS                        Figma     .pen
```

`Orc.UI.IR` answers what state a surface exposes, what selection means, which
intents exist, what is derived, what validation applies. `Orc.DesignIR` answers
what it looks like, how it is laid out, which reusable component this is, which
tokens and themes apply.

**They meet through stable binding ids**, and that junction is where UI becomes
compile-time checkable:

```
Orc.UI.IR                          Orc.DesignIR
  Binding  id = "candidate.accept"   Button  id = "candidate.accept"
           command = AcceptCandidate          component = OrcButton, tone = Positive
```

The compiler can then ask: does the design reference a binding that exists, does
the semantic model expose every binding the design requires, and does this button
invoke an intent it is allowed to invoke. Without a shared id space those are
review questions; with one they are build errors.

**Godot keeps visual authority.** TSCN, theme, `GraphEdit`, `AnimationPlayer`,
anchors and containers are what the Godot editor is good at, and `Orc.DesignIR`
compiles *into* them. Nothing generates imperative code that news up
`VBoxContainer` and `Label`.

**Exactly one visual authority per surface**, declared:

| `surface.visualAuthority` | Source | Generated |
| --- | --- | --- |
| `godot` | `.tscn` | design files are reference only |
| `pen` | `.pen` | `.tscn` |
| `figma` | versioned Figma node | DesignIR snapshot, then `.tscn` |

Two editable authorities for one layout is how a developer's TSCN edit silently
disappears the next time a designer exports. This is the same one-writer rule
ADR-0002 applies to source.

**Target details never appear in the semantic model.** `Surface`, `State`,
`Derived`, `Intent`, `Binding`, `Collection`, `Selection`, `Validation` belong to
Orc Bot. `INotifyPropertyChanged`, `AssemblyLoadContext`, `Callable`, `Signal`,
`RefCounted`, `Variant` belong to backends. C# stops being architecture and
becomes the desktop execution backend.

**External design formats are version-pinned adapters, never contracts.** Pencil
states plainly that `.pen` may take breaking changes. So `.pen vX` → pinned
adapter → `Orc.DesignIR v1`, and `.pen` types never surface as Orc Bot types —
the same rule already applied to agent providers.

**Figma and Pencil are a tooling choice, not an architectural one.** Both import
into `Orc.DesignIR`. Pencil is favoured for Orc Bot's own dogfooding for one
specific reason: `.pen` is repo-native JSON that branches, diffs, and merges, so
a design edit becomes an ordinary candidate alongside a source edit.

**AG-UI and A2UI are a different lane entirely, and neither is a UI language for
trusted surfaces.**

| | Role |
| --- | --- |
| AG-UI | *What happened* — agent↔frontend run/message/tool/state events. Transport. Belongs beside ACP, not beside MPS |
| A2UI | *How an agent may compose a view* from an allowlisted component catalog |
| MPS | Meaning and behaviour of trusted product surfaces |
| Figma/Pencil | Look |

Control Center, Candidate Review, Graph, Timeline, Terminal and Settings are
trusted surfaces and are **not** A2UI. Conversely **A2UI does not go through
`Orc.DesignIR`** — generating a `.tscn` every time an agent shows a confirmation
card defeats the point of a dynamic lane. A2UI resolves component ids against a
pre-built catalog of scenes, and *that resolution is the security boundary*: the
agent says "show an `orc.approval` with this data", and Orc Bot decides what
`orc.approval` means. Designers and trusted code decide what danger looks like;
agents compose from what exists.

## Consequences

- Each external design tool needs exactly one importer, and Godot needs exactly
  one visual compiler. The importer matrix collapses.
- UI gains real validation: a binding referenced by a design but absent from the
  model fails the build instead of failing at runtime in front of a user.
- Two IRs is more machinery than one. It is justified by the id junction; without
  compile-time cross-checking, a single IR would be simpler and this ADR would be
  over-engineering.

## The GDScript argument is withdrawn

The discussion's headline case for `Orc.UI.IR` was avoiding direct generation of
both C# and GDScript from the surface model, with GDScript serving Godot Web.
**Godot's Web export excludes C# entirely**, but Orc Bot is not shipping a Web
target, so that reason is void and is not recorded here as if it held.

Three reasons survive, and the decision rests only on them: much UI behaviour is
declarative enough for a resident binder to *interpret* rather than compile,
which removes generated source instead of adding it; conformance vectors can be
generated from the same model, making backend equivalence mechanically testable
rather than hoped for; and keeping backend types out of the model is what makes
the backend replaceable at all.

If those three do not hold up in practice, the honest response is to collapse to
one IR, not to reinstate a Web backend to justify two.

## What this ADR does not decide

The discussion assumes an existing A2UI/AG-UI activity ADR. **There is none in
this attempt** — the AG-UI/A2UI rows above record a boundary, not a scheduled
lane. Nothing here commits to building A2UI rendering, a Figma importer, a Pencil
importer, or an MPS pipeline. RFC-0004's memory surface is deliberately plain
TSCN with `visualAuthority = godot`, needing none of this.
