# ADR-0000: Restart from scratch; previous attempts are reference-only

- Status: Accepted
- Date: 2026-08-16
- Related: [docs/surveys/](../surveys/)

## Context

This is the third Orc Bot attempt. The first was restarted on 2026-08-07 and the
second on 2026-08-12. Both reached a large architecture before Orc Bot was ever
usable by the people building it, and both accumulated behaviour that only made
sense to the agent that wrote it.

The second attempt's most telling symptom: its orchestrator could only run against
the Orc Bot repository itself, because window validation was hard-coded to the
title `"Orc Bot"`, the path `project/hosts/complete-app`, and the export preset
`"Windows Desktop"`, compiled into the executable. Adding a second project type
required editing source and rebuilding. That is the shape a system takes when it
grows features before it grows a usable interface.

Both previous lines exist on the prior-attempt snapshots snapshots. The published `main`
of the second attempt is preserved on the remote as the tag
`archive/attempt-2-main`.

## Decision

Start from an empty repository. Port **no code**.

Previous attempts are treated as an **evidence source, not a codebase**. What we
take from them is written down as findings in `docs/surveys/`, each carrying the
snapshot path and commit it was recovered from, and then re-derived here. A
finding is only allowed to influence this repository by first becoming an ADR or
an RFC work item.

The ordering rule that follows: **nothing is built before it is needed by
somebody using Orc Bot to build Orc Bot.** A component earns its place by making
the next self-development task easier, not by appearing in an architecture
diagram.

## Consequences

- Work starts slower. The first weeks produce a CLI and a database rather than a
  graph editor, and that is the point.
- Every capability carried over must survive being restated as a decision. Ideas
  that only existed as code do not survive, which is the intended filter.
- `docs/surveys/` becomes load-bearing: it is the only channel by which two
  previous attempts' hard-won knowledge reaches this one. Surveys must cite
  snapshot and commit, or they are hearsay.
- The remote's `main` was force-reset. Nothing was lost — the prior head is
  tagged, and the working trees are on D:.

## Alternatives considered

**Port the second attempt's contracts and start from there.** Rejected: the
contracts were the healthiest part, but they were shaped by a runtime that was
never driven from outside. Importing them imports that shape.

**Keep developing the second attempt and refactor toward CLI-first.** Rejected:
the hard-coded validation protocol and the compiled-in workflows meant the
refactor was larger than the rewrite, and it would have preserved the habit of
adding capability ahead of usability.
