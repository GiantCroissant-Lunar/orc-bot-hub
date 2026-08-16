# RFC-0002: Recover what the previous attempts learned

- Status: Done (2026-08-16)
- Date: 2026-08-16
- Depends on: ADR-0000
- Feeds: RFC-0001

## Outcome

Five surveys, roughly 75 evidenced findings, one provider each — S1 Codex, S2
Claude Code, S3 Kiro, S4 OpenCode, S5 Kilo. They produced one new decision
(ADR-0009, amending ADR-0004 on engine caches) and amendments to RFC-0001's W3,
W5, W10, and W12, plus the ordering rules in that RFC's "What S5 says about
ordering".

## Goal

Two previous Orc Bot lines were built and abandoned. Their code is not coming
back (ADR-0000), but the things they *found out* are the most expensive asset
this project has, and they currently exist only as file trees on `D:`.

This RFC dispatches a survey wave to convert those trees into citable findings
under `docs/surveys/`, so that RFC-0001's work items start from evidence rather
than from memory.

## Sources

Eight snapshots contain an `agent-projects/orc-bot`:

```
prior-attempt snapshot (2026-07-27)    prior-attempt snapshot (2026-08-03)    prior-attempt snapshot (2026-08-05)
prior-attempt snapshot (2026-08-06)    prior-attempt snapshot (2026-08-08)    prior-attempt snapshot (2026-08-11)
prior-attempt snapshot (2026-08-12)    prior-attempt snapshot (2026-08-15)
```

`20260727`–`20260811` are the first line. `20260812` and `20260815` are the
second, which restarted on 2026-08-12; `20260815` is its final state and has
`docs/adr/0001`–`0006`, `docs/rfc/0001`, `docs/decision-register.md`,
`docs/architecture.md`, and `docs/source-ledger.md`.

Two related repositories are also reference material and are named where a
survey needs them: `prior-attempt snapshot (2026-06-25)` holds the canonical
load-unload-by-tier document in `fantasim-app-godot`, and the `*-archi`
repositories now live on `C:`.

## Method

Five workers, one topic each, non-overlapping. Every worker writes exactly one
file into `docs/surveys/` and touches nothing else in the repository.

**Every finding must be citable.** The format is fixed:

```markdown
### <short claim, stated as a fact>

- Evidence: <snapshot path>:<file>[:line] (+ commit sha where the tree has git)
- Confidence: high | medium | low
- Bearing: <which RFC-0001 work item or ADR this changes, or "none">

<two to six sentences. What was tried, what happened, why it matters here.>
```

A claim with no evidence line is deleted, not softened. A worker that cannot find
evidence for something it believes writes it under a clearly-marked
`## Unverified recollections` section at the end.

Workers must prefer **failures and surprises** over inventories. "The repository
had a WorkflowApplication class" is worthless. "Workflow definitions compiled
into the executable, so adding a project type required a rebuild" changes what we
build.

## Survey assignments

**S1 — Source authority, allocations, and candidates.**
How were fenced workspaces actually materialised? What did `CandidateStackComposer`
do, and what did composing a dependency candidate cost? Where did `DependsOn`
ambiguity bite? What made allocation refuse a repository?
*Bears on:* W3, ADR-0002, ADR-0007.

**S2 — Providers, machine channels, terminals, and containment.**
Which providers were driven, over which channels, and what broke? Zellij on
Windows: what worked and what needed a workaround. Process containment: what
survived a pane closing, and what Job Objects fixed. ACP versus `app-server`
versus NDJSON in practice.
*Bears on:* W4, W5, W6, ADR-0003.

**S3 — Memory, context, profiles, and loadouts.**
The Mem0 integration: scope model, what was frozen into an attempt, what the
receipts recorded. Agent profiles and immutable loadouts — what the split bought.
Where Microsoft Agent Framework helped and where it took over.
*Bears on:* W10, ADR-0006.

**S4 — Godot host, validation, and the operator UI.**
The windowed validation protocol and precisely how it was hard-coded. Export
pipeline failures — the missing `.sln`, the missing source generators, MSBuild
node-reuse hangs, crash dialogs from the export binary. What the UI actually
proved versus what it displayed. Synthetic input reliability.
*Bears on:* W12, ADR-0004, ADR-0005.

**S5 — Decisions, build tooling, and the shape of the failure.**
Read `20260815`'s `docs/adr/`, `decision-register.md`, `architecture.md`, and
`source-ledger.md` against what the code actually did. Which decisions held?
Which were quietly violated? What did the build/CI gate really cover? Then answer
the question that matters most: **at what point did each attempt stop being
usable by the people building it, and what was being built at that moment?**
*Bears on:* ADR-0000, RFC-0001 ordering.

## Constraints for every worker

- The snapshots are **read-only**. Do not write to `D:` for any reason.
- Write one file: `docs/surveys/<Sn>-<topic>.md`. Do not edit `AGENTS.md`, any
  ADR, any RFC, or any code.
- Do not propose architecture. If a finding implies a change, say so on the
  `Bearing:` line and stop there.
- Paths in this repository are absolute:
  `<workspace>/agent-projects/orc-bot`. A relative path resolves against
  whichever process is calling.
- **Do not run any git command.** All five workers share the main checkout, so a
  worker touching the index races the other four. Write your one file and stop;
  the coordinator reviews and commits. This also sidesteps two known traps: an
  agent sandbox cannot commit inside a worktree because `.git` points outside it,
  and OpenCode and Kilo resolve the project root through the gitdir pointer and
  would edit the main checkout from a worktree anyway.

## Done when

Five survey files exist, every claim carries evidence, and each RFC-0001 work
item has been checked against the findings — with W3, W5, and W12 in particular
either confirmed or amended before implementation starts.
