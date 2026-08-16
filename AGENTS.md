# orc-bot-hub — agent rules

This repository is the **public** documentation hub for Orc Bot. The
implementation repository is private.

## What this repository is

**The cross-attempt record.** Orc Bot has been restarted twice; this is the third
attempt's implementation-independent documentation, and it is written to outlive
it. If a fourth attempt is needed, this repository carries forward and the
implementation tree does not.

`docs/` is written **here**, directly. It is not generated and not mirrored — the
private orc-bot repository keeps only notes specific to its Godot host.

- `docs/adr/` — decisions. Once accepted, an ADR is not edited; it is superseded
  by a later one, and both stay.
- `docs/rfc/` — proposed slices of work, amended as evidence arrives, each
  amendment citing the survey that caused it.
- `docs/surveys/` — findings recovered from earlier attempts. Evidence, never
  decisions.
- `docs/discussion/` — raw design conversations. **Never cite one as a
  decision**; if something in it matters, it graduates to an ADR or an RFC.

`docs/index.md` and each section's `index.md` are the site's navigation. Update
them when you add a document, because `mkdocs build --strict` fails on a page
that nothing links to.

## The rule that keeps this repository publishable

This repository is public and its documents cite a private one. The natural way
to cite evidence is an absolute path into somebody's D: drive — correct in
private, a leak here.

`tools/check-no-local-paths.py` runs as a pre-commit hook and again in the Pages
workflow, and **refuses any absolute local path, home directory, or full commit
sha**. Cite evidence as:

```
prior-attempt (2026-08-15) orc-bot/project/path/File.cs:123
```

The file and line are the useful part; the drive letter is not. A short sha is
fine, a 40-character one is not. Do not weaken the check to get a document out.

Install the hooks once:

```bash
pre-commit install --install-hooks
pre-commit install --hook-type commit-msg
```

## Agent resources

`.agent/` is the tracked canonical source. `.agents/`, `CLAUDE.md`, and every
other tool directory are generated from `.agent/adapters/` and gitignored:

```bash
python tools/sync-agent-resources.py --prune
```

## Publishing

`.github/workflows/docs.yml` builds the MkDocs site and deploys to GitHub Pages
on push to `main`. It re-runs the leak scan before building, so the gate exists
whether or not someone installed the hooks.
