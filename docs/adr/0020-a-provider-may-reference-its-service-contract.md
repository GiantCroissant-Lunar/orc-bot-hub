# ADR-0020: A provider may reference its service contract

- Status: Accepted
- Date: 2026-08-16
- **Supersedes: the "T3, T4 — not T1" clause of [ADR-0013](0013-four-tier-bundle-oriented-csharp-architecture.md)**
- Related: ADR-0016

## Context

[ADR-0013](0013-four-tier-bundle-oriented-csharp-architecture.md) adopted the
four tiers and recorded the reference graph as:

| Tier | May reference |
| --- | --- |
| T1 | T1 |
| T2 | T1 |
| T3 | T1, T3 — **not T2** |
| T4 | T3, T4 — **not T1** |

`ServiceArchi.Analyzers` enforced that graph as `SA1001`, an error. The stated
rationale for excluding T1 from T4 was that a T3 service family owns the
smaller provider port its backends implement, so a backend should never see the
public service surface.

The intent is right. The enforcement did not serve it.

## The rule did not do what it claimed

T1 is defined, in ServiceArchi's own documentation, as holding "public service
interfaces, attributes, **DTOs, enums**". A provider that returns a domain
record needs those types. It cannot avoid them.

And it already has them. A T4 references its T3, a T3 references T1, and
`ProjectReference` flows transitively — so the T1 types are on the T4's compile
surface whether or not the reference is declared. Forbidding the *declaration*
isolated nothing. It made the honest dependency a build error and the laundered
one legal, which is worse than either alternative: the graph read stricter than
the build actually was.

The reference implementation had already voted. `GameFoundation.Resource.Godot.Pck`
— the exact project ADR-0013 cites as its T4 exemplar — declares
`ServiceArchiTier="T1"` on its contracts reference, deliberately and explicitly.
The documented rule and the canonical example disagreed, and the example was
right.

## Decision

**A T4 provider may reference T1.** The enforced graph becomes:

| Tier | May reference |
| --- | --- |
| T1 | T1 |
| T2 | T1 |
| T3 | T1, T3 |
| T4 | T1, T3, T4 |

**The edge that survives is T2, and it is the point of the graph.** Nothing below
T2 may reference it. A collectible T3 or T4 taking a hard dependency on a
resident generated proxy pins that assembly into the plugin's load context —
which is the failure mode ADR-0016's replacement transaction exists to prevent,
and the one a reference graph can actually catch.

**"The provider port is smaller than the service contract" remains the intended
shape, as a design guideline rather than a gate.** Whether a given port is
appropriately narrow is a judgement about API design. An analyzer that cannot
make that judgement should not pretend to by proxying it onto a reference rule
that fires on unrelated cases.

Shipped as `GiantCroissant.ServiceArchi.Analyzers` 0.1.3.

## Consequences

- **The tier restructure gets substantially smaller.** Splitting every service
  contract into a T1 interface plus a T3 provider port is no longer forced by the
  build; it happens where it earns its place.
- **`SA1001` now fires only on real layering violations**, so it stops being a
  rule people route around and starts being one they trust.
- **The guideline needs somewhere to live.** It is recorded in ServiceArchi's
  `Tiers.md` and in this repository's rules, and it is now unenforced — so it
  degrades quietly rather than loudly. That is the cost of this decision and it
  is accepted knowingly.

## What would reverse this

- A provider is found implementing the public service interface directly rather
  than a narrower port, and the drift traces to the absence of the gate rather
  than to ordinary design pressure.
- A cheap mechanical test for "this port is narrower than that contract" turns
  out to exist, at which point the guideline can be gated on its own terms
  instead of through a reference rule.

## A note on how this was found

The stale-package hazard is worth recording, because it nearly inverted the
conclusion twice. The first repack of the analyzer produced a version whose
compiled assembly predated the change by three weeks; the package version was
new, the rule inside it was old, and the consumer kept reporting the superseded
behaviour while appearing to be up to date. It was caught by comparing assembly
timestamps, not by any build output.

Separately, the analyzer's own build targets record a consumer "where the
analyzer silently never fired". A gate that is present, restored, and inert is
indistinguishable from a gate that passes — which is the same shape as a stale
IDE analyser reporting zero problems, an incremental build reporting zero
warnings, and an unavailable provider returning an empty result. **A change to an
enforcement rule is only verified by observing both outcomes**: the case that
must now pass, and the case that must still fail.
