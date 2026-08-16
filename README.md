# Orc Bot — documentation hub

Public documentation for **Orc Bot**, a development-resource orchestrator.

Orc Bot owns the parts of software work that an agent should not own: work
topology, fenced source allocations, immutable candidates, validation, and
acceptance. It delegates the thinking to real coding-agent CLIs — Codex, Claude
Code, OpenCode, Kilo, Kiro — and treats what they say as a proposal, never as a
fact about the repository.

The implementation is private. This repository is where the reasoning lives.

## Start here

- **[Decisions](docs/adr/)** — every architectural decision, with its context,
  its consequences, and the alternatives that were rejected and why.
- **[Proposed work](docs/rfc/)** — the slices being built, and what "done"
  means for each.
- **[Surveys](docs/surveys/)** — the part most projects never publish: what was
  learned from two earlier attempts at this system that were abandoned. Roughly
  75 findings, each citing the file and line it came from.

If you read one thing, read [ADR-0002 — fenced source allocations and immutable
candidates](docs/adr/0002-fenced-source-allocations-and-immutable-candidates.md).
It is the reason the project exists.

## Why the surveys are here

Orc Bot has been restarted twice. The code from those attempts is gone; the
things they *found out* are not, and they are worth more than the code was.

They include the sort of finding that only comes from running the thing: a
shared engine cache that returns another workspace's asset with exit code 0; a
candidate whose patch applies cleanly into a workspace missing the code it was
meant to inherit, because `git diff HEAD` ignores untracked files; an agent that
stalls indistinguishably from working because its client missed one inbound
request.

Published in full, on the theory that a failure someone else can avoid is worth
more than the appearance of having had none.

## Reading conventions

- An ADR is not edited once accepted. It is superseded by a later one, and both
  stay.
- An RFC is a proposal. Its work items get amended as evidence arrives, and the
  amendments cite the survey that caused them.
- A survey is evidence, never a decision. It may change an ADR, but only by
  someone writing that ADR.

Absolute local paths and internal commit identifiers are rewritten on
publication, so a citation reads `prior-attempt (2026-08-15) orc-bot/path:line`
rather than a path on somebody's D: drive. The file and line are the useful part
and they are preserved.

## Licence

Documentation: [CC BY 4.0](LICENSE).
