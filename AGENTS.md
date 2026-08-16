# orc-bot-hub — agent rules

This repository is the **public** documentation hub for Orc Bot. The
implementation repository is private.

## The one rule that matters

**`docs/` is generated. Do not edit it here.**

Every file under `docs/adr/`, `docs/rfc/`, and `docs/surveys/` is projected from
the private orc-bot repository by its `tools/promote-docs.py`, which rewrites
absolute local paths and internal commit identifiers on the way through. The
projection is one-way and rebuilds those trees from scratch, so an edit made
here is a fork that the next promotion silently overwrites.

If something in `docs/` is wrong, fix it in orc-bot and re-promote. If you
cannot reach orc-bot, open an issue here rather than editing the file.

What *is* editable here: `README.md`, this file, `mkdocs.yml`, `.github/`, and
`.agent/`.

## What is not published

`docs/discussion/` exists in orc-bot and is never promoted, by any flag. It is
unedited first-draft reasoning including arguments that were considered and
dropped. If something in it should be public, it graduates into an ADR or an RFC
first.

The promotion tool fails closed: if any absolute local path, home directory, or
bare commit sha survives its rewrite rules, nothing is written at all. Do not
weaken that gate to get a document out — add a rewrite rule, or fix the source.

## Agent resources

`.agent/` is the tracked canonical source. `.agents/`, `CLAUDE.md`, and every
other tool directory are generated from `.agent/adapters/` and gitignored:

```bash
python tools/sync-agent-resources.py --prune
```

## Publishing

`.github/workflows/docs.yml` builds the MkDocs site and deploys to GitHub Pages
on push to `main`. Promotion produces a branch for review; only `main` publishes,
so review is the gate and nothing reaches the public site unreviewed.
