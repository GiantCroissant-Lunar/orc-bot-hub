# ADR-0018: Agents edit UI models through a semantic service, never as files

- Status: Accepted
- Date: 2026-08-16
- Related: ADR-0001, ADR-0002, ADR-0006, ADR-0017
- Informed by: [discussion/mps-ui.md](../discussion/mps-ui.md)

## Context

ADR-0017 makes MPS the semantic authority for trusted surfaces. That creates a
problem specific to this product, and it is worth stating before it is designed
around.

MPS is **projectional**: a program is an AST, and its stored form is generic
persistence rather than the concrete syntax a human edits. That is excellent for
a person using MPS, and hostile to every worker Orc Bot dispatches — Claude Code,
Codex, OpenCode, Kiro and Kilo all have text files as their native environment.

An agent asked to "add a validation rule to the candidate review surface" would be
editing serialised model XML. It would frequently produce something that parses,
occasionally produce something that loads, and have no way to know which.

## Decision

**No agent edits MPS persistence files.** Not as a convention — as a boundary the
architecture enforces, on the same footing as ADR-0002's rule that agents publish
candidates rather than mutating integrated source.

**A Model Service exposes semantic operations instead**, reached the way agents
reach everything else (ADR-0001: CLI, MCP, and the host are adapters over one
surface, and arriving through one grants no extra authority):

```
query surface        inspect references
add state            validate model
add intent           generate
modify expression    produce semantic diff
```

An agent says *modify surface `agent-sessions`, property `selectedSession`*, not
*replace bytes 4,812–4,977*. MPS has an Open API for programmatic model access
and supports custom persistence, so a structured service is compatible with its
architecture rather than working around it.

**A UI-model change is an ordinary candidate.** It gets the same lifecycle as a
source change — frozen, digested, reviewed, accepted or rejected — and the review
shows a **semantic** diff, not a persistence diff:

```
Candidate #318
  Source changes     + CandidateReview          (semantic)
  Design changes     + candidate-review.pen
  Generated          ~ candidate_review.tscn
                     ~ CandidateReviewPresenter.generated.cs
```

Generated output is build product, not candidate source (ADR-0016). A reviewer
approves the authored change and the compiler is responsible for the rest.

**Validation runs before a candidate is publishable, not after acceptance.** The
service can type-check the model, so a UI-model candidate that does not resolve
should never reach a human. This is the one place a projectional editor is a
clear advantage: an invalid model is representable in text and is not
representable here.

## Consequences

- MPS becomes a *service Orc Bot depends on being installed*, and that is a real
  cost — a heavier dependency than a text file, on a machine that must have it
  before a UI candidate can be produced at all. The service boundary at least
  makes its absence a clear unavailability rather than a corrupted edit.
- **This must be tested before MPS is committed to as the source of truth.** The
  discussion flags it as the one area to prove early, and it is the correct place
  to be sceptical: if the semantic operations an agent needs cannot be expressed
  through the Open API, MPS is the wrong authority regardless of how good its
  generator pipeline is. That test belongs before any MPS RFC, not inside one.
- Semantic diffs are a genuine gain for review. "This intent's precondition
  changed" is reviewable; a projectional-storage diff is not.

## What this ADR does not decide

It does not schedule MPS. It states the rule that applies *if and when* MPS
becomes the semantic authority, so that the boundary is decided before the
tooling makes it inconvenient.

It does not extend to `.pen`. Pencil's format is repo-native JSON that diffs and
merges (ADR-0017), so agents may edit it as an ordinary file — the constraint
here follows from projectional storage, not from design files in general.
