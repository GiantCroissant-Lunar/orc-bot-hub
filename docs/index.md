# Orc Bot

A development-resource orchestrator. It owns work topology, fenced source
allocations, immutable candidates, validation, and acceptance, and delegates the
thinking to real coding-agent CLIs — treating what they say as a proposal, never
as a fact about the repository.

The implementation is private. This is the cross-attempt record: it is written to
outlive any single attempt, and there have been three.

- [Decisions](adr/) — 12 ADRs
- [Proposed work](rfc/) — 3 RFCs
- [Surveys](surveys/) — 10 documents recovering what two abandoned
  attempts learned
- [Discussion](discussion/) — 4 raw design conversations; input, never
  decisions

Citations name a prior attempt and a file rather than a local path. A pre-commit
hook and the publish workflow both enforce it.
