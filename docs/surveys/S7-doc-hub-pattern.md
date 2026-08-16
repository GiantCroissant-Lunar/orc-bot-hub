# S7 — How a "*-hub" repository actually works, and what orc-bot-hub should be

Survey for the question: `orc-bot` stays private, `orc-bot-hub` will be public,
and the plan is to move `orc-bot/docs` into it. This reads every `*-hub`
repository recoverable from the the prior-attempt snapshots snapshots to find the real
mechanism, then checks it against the live `orc-bot-hub` skeleton.

Path shorthand (all snapshots read-only; no git command was run):

- **FH-0625** = `prior-attempt (2026-06-25) fantasim-hub`
- **FH-0718** = `prior-attempt (2026-07-18) fantasim-hub`
- **FH-0726** = `prior-attempt (2026-07-26) fantasim-hub`
- **FH-0727** = `prior-attempt (2026-07-27) fantasim-hub`
- **FH-0730** = `prior-attempt (2026-07-30) fantasim-hub`
- **FH-0731** = `prior-attempt (2026-07-31) fantasim-hub`
- **FH-0803** = `prior-attempt (2026-08-03) fantasim-hub`
- **UB** = `prior-attempt (2026-08-03) unify-build/unify-nuke9-upgrade` (not a `*-hub` repo — included because it is the only repository found anywhere in the snapshots that actually publishes a docs site)
- **Hub-skeleton** = `<workspace>/agent-projects/orc-bot-hub` (live, current, has a real `origin` remote: `git@github.com:GiantCroissant-Lunar/orc-bot-hub.git`)

`fantasim-hub` is the only `*-hub` repository that exists anywhere under
the prior-attempt snapshots (searched all 13 snapshot roots, depth 4, for `*hub*`
directories). It has seven snapshots across six weeks. This is a single
lineage, not a genre — treat everything below as one repo's evolution, not a
convention independently validated by multiple teams.

## Finding 1: no snapshot of `fantasim-hub` is a mirror of a private repo's docs

This is the load-bearing finding and it inverts the task's working
assumption. In every snapshot, `fantasim-hub` is the **primary, canonical**
location for design content, and the code repos (`fantasim-world`,
`fantasim-app-godot`) are the satellites — the opposite direction from
`orc-bot` → `orc-bot-hub`, where the docs already live in the private code
repo and need to move *out*.

- FH-0726 `README.md`: *"Design documents for FantaSim, the 9th attempt. Code
  lives in the sibling repos — `fantasim-world` ... and `fantasim-app-godot`
  ... Nothing here is code, and nothing here generates code."*
- FH-0625 `README.md` calls it the *"documentation and workflow control
  plane"* — again the hub is upstream of the code repos, driving sandbox
  provisioning for them, not downstream of one.
- FH-0803 `AGENTS.md`: *"This repository is the design and decision hub for
  Fantasim. Its primary working memory is the project-local SurrealDB
  database..."* — canonical source is a local SurrealDB instance, not a
  private repo it mirrors.

No `.gitmodules` referencing `fantasim-hub` exists in `fantasim-world` or
`fantasim-app-godot` (checked at FH-0803's snapshot date). No script or CI job
in any of the three repos pulls content *into* `fantasim-hub` from a sibling.
There is nothing in this codebase's history that does what the task describes
— it has to be designed new, informed by adjacent evidence below, not copied.

## Finding 2: the hub concept itself was rebuilt at least three times, and shrank each time

| Snapshot | Shape | Top-level scaffolding |
|---|---|---|
| FH-0625 | Retrieval/indexing control plane: `qmd`+Qdrant, CocoIndex, sandbox provisioning for `fantasim-inone-*` repos, Repomix packing | `LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `.secrets.baseline`, `.pre-commit-config.yaml`, full `.agent/adapters/` per-CLI tree, `.agent/logs/` (70+ numbered dispatch logs) |
| FH-0718 | Thinner; same top-level doc files, no `.agent/` | `AGENTS.md`, `CLAUDE.md`, `Taskfile.yml`, `repomix.config.json` |
| FH-0726/0727 | `vault/` of hand-written design docs (`world-design.md`, `attempt-ledger.md`) | Only `README.md` |
| FH-0730 | `vault/discussion/*.md` — raw design-conversation writeups | `.github` present but empty of files |
| FH-0731 | Reset to almost nothing (`.git`, `.github` only) — mid-restart | — |
| FH-0803 | SurrealDB-backed `design_memory` MCP server; `docs/` holds one materialized doc | `.codegraph`, `.omo/`, `.surrealdb/`, `history.txt` (raw SurrealQL transaction log), `.codex/config.toml` |

None of these five distinct shapes is a "public docs site fed by a private
repo." Each is a working-memory or knowledge-capture tool for Fantasim's own
agents, redesigned as the team's idea of "what a hub is for" changed. Weigh
the whole lineage as evidence that this repo family reinvents "hub" readily —
do not treat FH-0803 (merely the most recent) as more authoritative than
FH-0726 just because it is newer.

## Finding 3: `.github/` never carried a publish workflow, in any snapshot

Full `.github/` contents by snapshot:

- FH-0625: `ISSUE_TEMPLATE/bug_report.md`, `ISSUE_TEMPLATE/feature_request.md`,
  `PULL_REQUEST_TEMPLATE.md`, `SECURITY.md`. No `workflows/` directory at all.
- FH-0718, FH-0726, FH-0727, FH-0730, FH-0731, FH-0803: `.github/` exists as a
  directory and is **completely empty** — zero files, in every one of the six
  later snapshots.

No `mkdocs.yml`, `docusaurus.config.*`, or `_config.yml` was ever committed to
`fantasim-hub` at any snapshot (checked all seven). **No site was ever
published for any hub.** The one working counter-example anywhere in the
the prior-attempt snapshots tree is **UB** (`unify-build`, not a hub — a public
build-tool repo), which publishes its *own* `docs/` in the *same* repo via
`.github/workflows/docs.yml`:

```yaml
name: Deploy Documentation
on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml']
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install mkdocs-material
      - run: mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with: { path: site }
  deploy:
    needs: build
    steps:
      - uses: actions/deploy-pages@v4
```

`mkdocs.yml` (UB) confirms `docs_dir: docs`, `theme: material`, and a `nav:`
that mirrors `adrs/`, `rfcs/`, `specs/`, `archive/` — i.e. the same
adr/rfc-shaped layout `orc-bot/docs` already has. This is real, proven
plumbing for "publish a docs folder as a static site," but it publishes a
folder that already lives in the repo being published — it says nothing about
moving content *from* a second, private repo. Treat UB's `docs.yml` +
`mkdocs.yml` as the reusable publish mechanism, and the "how do private docs
get here" problem as unsolved in this codebase and requiring new work.

## Finding 4: no scrubbing or allowlist step exists anywhere, and the hub's own artifacts show why one is needed

No file matching a scrub/allowlist/redaction pattern (script name, CI step,
or `AGENTS.md` instruction) was found in any `fantasim-hub` snapshot. The
`.secrets.baseline` + `.pre-commit-config.yaml` in FH-0625 are generic
secret-scanning (gitleaks-style credential detection), not path/machine-name
scrubbing, and they did not survive past FH-0625.

FH-0803's own tracked `history.txt` (a raw SurrealQL transaction log,
committed to the repo) demonstrates exactly the leakage class the task asks
about, inside a repo that already exists in this family:

```
export_path: "<workspace>/fantasim-projects/fantasim-app-godot/project/hosts/complete-app/build/windows/release/fantasim-geodynamics.exe",
export_sha256: "ccfc23d9e37e570529748136299f153582ad86e2efdc7cc9b6c1e27f66b98543",
...
implementation_commits: ["c652c9b", "e5af0e6", "13f3791", "bc59711", "5e9f087"],
orchestration_run: "run_73ec72446303",
worker_runtime: "Claude Code Opus 5 high"
```

Absolute local build paths, export digests, and internal commit SHAs sit in a
tracked file with no gate over them. This is the strongest available evidence
that raw internal-repo content leaks exactly the details the task named
(local paths, provenance hashes, internal commits) unless something stops it
— and that this hub lineage never built that something.

Cross-checking `orc-bot/docs` itself against the same class of leakage
(`grep -rc "lunar-horse-202"`, i.e. any `<workspace>/-<date>` or
`<workspace>/-<date>` citation):

| Path | Hits |
|---|---|
| `docs/adr/*.md` (all 11 ADRs) | 0 |
| `docs/rfc/0001-bootstrap-slice.md` | 0 |
| `docs/rfc/0002-recover-prior-attempt-knowledge.md` | 4 |
| `docs/surveys/S1-source-authority-and-candidates.md` | 14 |
| `docs/surveys/S2-providers-channels-and-containment.md` | 39 |
| `docs/surveys/S3-memory-context-and-loadouts.md` | 16 |
| `docs/surveys/S4-godot-validation-and-export.md` | 30 |
| `docs/surveys/S5-decisions-and-shape-of-failure.md` | 3 |
| `docs/discussion/*.md` (all 3 files) | 0 |

ADRs are clean by construction — they record decisions, not investigation
trails. `discussion/` is clean of D: paths too (though see Finding 5 for why
it should still stay private). `rfc/0002` and every `surveys/` file cite
snapshot paths pervasively, because citing the evidence path is exactly what
a survey is for (see this file's own path shorthand table above — S7 does the
same thing). That is correct methodology for a private research doc and
exactly the content a scrub step must catch before anything public ships.

## Finding 5: the hub's own `AGENTS.md` and `.agent/` — and orc-bot already runs the same adapter pattern

FH-0803 `AGENTS.md` (the fullest, most recent version) states the hub's
artifact policy directly: *"SurrealDB is canonical for evolving discussion
memory... Materialize accepted artifacts into `docs/` when a reviewable
repository document is needed, and retain the artifact identifier in both
places."* — i.e. even inside this private/internal hub, raw discussion stayed
in the database and only accepted, reviewed material became a `docs/` file.
That accept-before-materialize discipline is the same shape as `orc-bot`'s own
ADR-0002/ADR-0006 ("an agent proposes; it does not promote" — a source or
memory candidate is never self-promoted).

FH-0803's `.agent/` differs from a code repo's in *what* it generates, not
*how*:

- `.agent/adapters/targets/claude/config.yaml` — generates a thin `CLAUDE.md`
  pointer to `AGENTS.md` (`strategy: import`, `target: CLAUDE.md`).
- `.agent/adapters/targets/agents/config.yaml` — mirrors skills into
  `.agents/skills/` and declares the Codex MCP server (`fantasim_design_memory`).
- `.agent/skills/design-memory/` — the hub's *own* skill, and it is
  hub-specific: it teaches the SurrealDB recall/store workflow. A code repo
  has no equivalent; its skills are about building and dispatching, not
  curating cross-project memory.
- `tools/sync-agent-resources.py` regenerates the above from `.agent/` and
  supports `--check` for drift.

This is not hypothetical prior art — `orc-bot` itself has already adopted
this exact mechanism (live, current state, not a snapshot): `orc-bot/.agent/`
now has `adapters/targets/{agents,claude,kiro}/`, `adapters/runners/`, and
`skills/orca-dispatch/`, generated by `orc-bot/tools/sync-agent-resources.py`
— the identical script name and identical `.agent/ → generated surface`
direction as FH-0803. `orc-bot-hub`'s `.agent/` should reuse this same
mechanism (same `tools/sync-agent-resources.py`, same
`adapters/targets/{claude,agents}/` shape) rather than invent a second one,
but its *skills* should be hub-specific — e.g. a promotion/scrub skill — the
same way `design-memory` is specific to being a hub and `orca-dispatch` is
specific to being a dispatcher.

## The `orc-bot-hub` skeleton, checked directly

`<workspace>/agent-projects/orc-bot-hub` is a real, currently-empty clone
with a live `origin` remote (`git@github.com:GiantCroissant-Lunar/orc-bot-hub.git`).
`.agent/`, `.github/`, `docs/` are empty directories; `AGENTS.md`, `README.md`,
`.gitignore` are zero-byte files. There is nothing here to reverse-engineer —
it needs to be built, and the evidence above is what to build it from.

## Answering the five-way split for `orc-bot/docs`

| Directory | Verdict | Why |
|---|---|---|
| `adr/` | **Public** | 0 leaked paths across all 11 files; ADRs record accepted decisions, not investigation trails, matching FH-0803's own "materialize accepted artifacts into docs" rule. |
| `rfc/` | **Needs scrubbing** (per-file, not blanket) | `0001` is clean (0 hits); `0002` cites the prior-attempt snapshots 4 times because its whole subject is recovering prior-attempt knowledge — scrub those 4 citations to a described reference before publishing, ship `0001` as-is. |
| `discussion/` | **Private** | Contains no leaked absolute paths, but `orc-bot/docs/README.md` itself instructs *"Never cite a discussion document as a decision"* — it is unedited, first-draft reasoning including dropped arguments, exactly the class FH-0803's AGENTS.md keeps out of `docs/` until "materialized." Publishing it exposes reasoning-in-progress with no curation pass, which is a judgment risk even where no literal secret is present. |
| `surveys/` | **Needs scrubbing** | 14–39 `<workspace>/-<date>` citations per file plus internal commit SHAs throughout (this file included) — high public value (this is literally "how we learned this"), but every snapshot path and commit SHA needs to become a described reference ("a prior internal attempt", not a literal `prior-attempt (2026-08-03) file:line`) before it ships, per Finding 4's leakage evidence. |
| `docs/README.md` | **Public, needs a rewrite** | It is only a navigation index, but it currently links directly into `discussion/` (staying private) and cites `surveys/` as if unscrubbed — the public version must drop the `discussion/` table and point only at the scrubbed `adr/`/`rfc/`/`surveys/` trees. |

## Proposed `orc-bot-hub` layout

```
orc-bot-hub/
  README.md                    public overview; points into docs/
  AGENTS.md                    hub-specific agent rules (own artifact policy,
                                like FH-0803's — not a copy of orc-bot's AGENTS.md)
  LICENSE
  mkdocs.yml                   adapted from UB: docs_dir: docs, material theme
  .github/
    workflows/docs.yml         adapted verbatim from UB (build+deploy to Pages)
    ISSUE_TEMPLATE/, PULL_REQUEST_TEMPLATE.md   (adapted from FH-0625, the one
                                snapshot that had them)
  .agent/
    adapters/targets/{claude,agents}/config.yaml   same shape as orc-bot's own
    skills/hub-promote/         hub-specific skill: owns the promotion+scrub
                                 workflow (the FH-0803 "design-memory" role,
                                 filled in for this hub's actual job)
  tools/
    sync-agent-resources.py    intra-repo generated-surface sync, same script
    promote-docs.py            NEW — does not exist anywhere in this codebase's
                                history; see mechanism below
  docs/
    adr/                       mirrored from orc-bot/docs/adr verbatim
    rfc/                       mirrored, with D:\ citations rewritten per-file
    surveys/                   mirrored, with D:\ paths + commit SHAs rewritten
                                (v0: ship none until promote-docs.py's scrub
                                gate exists; adr/ alone is enough to launch)
    (no discussion/ tree — stays in orc-bot only)
```

## Proposed sync mechanism

Nothing in this codebase's history solves "move docs from a private repo into
a public one," so this is new, not borrowed — but it should follow the two
conventions that *are* established and proven:

1. **One-way, not two-way, and orc-bot-hub never wins a conflict.** Same rule
   `orc-bot/AGENTS.md` already states for the intra-repo case: *"editing a
   generated file loses the edit on the next sync"* — `orc-bot-hub/docs/`
   should be treated as fully generated from `orc-bot/docs/`. A human edit
   made directly in `orc-bot-hub` is a fork that the next promotion silently
   overwrites; if that is a problem, the fix belongs upstream in `orc-bot`.
2. **A gate, not an autopublish.** ADR-0002/ADR-0006's "an agent proposes; it
   does not promote" applies directly: `promote-docs.py` should produce a
   branch/PR in `orc-bot-hub` for review, not push straight to `main`. Only
   `main` triggers `docs.yml`'s Pages deploy (per UB's `on: push: branches:
   [main]`), so the review gate is exactly where nothing has published yet.

Concretely: `promote-docs.py` (run from `orc-bot`, given both repo paths)
copies the allow-listed subtrees (`adr/` verbatim, `rfc/` and `surveys/`
after rewrite rules strip the prior-attempt snapshots/the prior-attempt snapshots paths and bare
commit SHAs to descriptive text), refuses to proceed if any of those patterns
survive the rewrite (fail closed, matching ADR-0004's "gate enforces, does
not warn" spirit already used for derived-state hygiene), and leaves the
result staged in `orc-bot-hub` for a human or reviewing agent to open as a PR.
`discussion/` is never in the allow-list — it is not copied, ever, by this
tool; if something in it needs to be public, it graduates to an ADR or RFC in
`orc-bot` first, the same "materialize when reviewable" rule FH-0803 already
follows.
