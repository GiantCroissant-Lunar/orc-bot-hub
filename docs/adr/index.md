# ADR

Architectural decisions. Once accepted, an ADR is not edited — it is superseded by a later one, and both stay.

- [ADR-0000: Restart from scratch; previous attempts are reference-only](0000-restart-from-scratch.md)
- [ADR-0001: One application surface behind every adapter](0001-one-application-surface-behind-every-adapter.md)
- [ADR-0002: Fenced source allocations and immutable candidates](0002-fenced-source-allocations-and-immutable-candidates.md)
- [ADR-0003: Containment, semantics, and presentation are three independent planes](0003-three-independent-planes-per-attempt.md)
- [ADR-0004: Derived state is never tracked, and expensive tools get authority slots](0004-derived-state-and-tool-authority-slots.md)
- [ADR-0005: UnifyBuild, GitVersion, and one artifact root per commit](0005-build-versioning-and-artifact-layout.md)
- [ADR-0006: Memory is scoped, untrusted recall — and it ships in v0](0006-memory-is-scoped-untrusted-recall.md) — storage clause superseded by 0014
- [ADR-0007: Engineering concepts compile work; they do not execute it](0007-engineering-concepts-compile-they-do-not-execute.md)
- [ADR-0008: The runtime is its own process; every UI is a client](0008-runtime-is-a-process-every-ui-is-a-client.md)
- [ADR-0009: Seed engine caches per allocation; do not share them](0009-seed-engine-caches-do-not-share-them.md)
- [ADR-0010: Orca is scaffolding, and is retired plane by plane](0010-orca-is-scaffolding-not-a-dependency.md)
- [ADR-0011: One `orc` binary is both client and daemon; the Godot host is a third client](0011-one-orc-binary-client-and-daemon.md) — superseded by 0012
- [ADR-0012: The product is one exported Godot binary; headless is the daemon](0012-the-product-is-one-exported-godot-binary.md)
- [ADR-0013: Four-tier, bundle-oriented C# architecture](0013-four-tier-bundle-oriented-csharp-architecture.md)
- [ADR-0014: SurrealDB is the control-plane store](0014-surrealdb-is-the-control-plane-store.md)
- [ADR-0015: Runtime contributions declare requirements, offer capabilities, and own their effects](0015-runtime-composition-requirements-offers-and-owned-effects.md)
- [ADR-0016: A component revision is a presentation unit and a managed unit](0016-a-revision-is-a-presentation-unit-and-a-managed-unit.md) — extends 0013
- [ADR-0017: Meaning and look are two orthogonal IRs that meet at binding ids](0017-two-orthogonal-ui-irs-meeting-at-binding-ids.md)
- [ADR-0018: Agents edit UI models through a semantic service, never as files](0018-agents-edit-ui-models-through-a-service-not-as-files.md)
