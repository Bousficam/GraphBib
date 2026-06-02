---
description: Add relevant figures (from cited sources' raw PDFs) to a concept page. Runs `source-illustrator` on cited sources that lack a `## Figures` section, then `concept-illustrator` to pick and insert the figures.
argument-hint: "<concept-slug> [--max-figures N] [--no-prep]"
---

Augment a concept page with figures from its cited sources.

Arguments: $ARGUMENTS — the concept slug (e.g. `MotorImagery`,
`Neuroplasticity`) plus optional flags:
- `--max-figures N` (default 4) forwarded to `concept-illustrator`.
- `--no-prep` skip the `source-illustrator` prep pass (only useful if
  you know `## Figures` sections are already populated).

# Procedure

## Phase 1 — Prep cited sources (default)

Read the concept page at `wiki/<vault>/concepts/<Concept>.md` and
collect the cited `[[source-slug]]` wikilinks. For each cited source
whose wiki page is missing a `## Figures` section AND whose raw
images dir `raw/<vault>/papers/<slug>_images/` exists, delegate:

```
Agent(subagent_type=source-illustrator, prompt="Illustrate <slug>")
```

Run them sequentially (figures extraction is cheap but ordered output
makes the report cleaner). Skip sources whose raw isn't slug-aligned
yet — surface them in the final report so the user can run
`python tools/audit_raw.py --apply` (or `/wiki-maintain`) first.

Skip Phase 1 entirely if `--no-prep` was passed.

## Phase 2 — Select and insert

Delegate:

```
Agent(subagent_type=concept-illustrator, prompt="Illustrate <Concept> [--max-figures N]")
```

The sub-agent reads the concept page, walks the (now populated)
`## Figures` sections of cited sources, picks the most relevant
figures, and inserts them inline with full citation.

## Phase 3 — Report

Summarize:
- Concept page: `wiki/<vault>/concepts/<Concept>.md`
- Sources prepped in Phase 1: `<count>`
- Sources skipped (raw not aligned): `<list>` (run audit_raw first)
- Figures inserted in Phase 2: `<count>` (cap: `<max>`)
- Under which sub-sections

# Notes

- Images are linked **directly to `raw/<vault>/papers/<slug>_images/`**
  (no copy into the wiki). Renaming or moving raws will break the
  links — the librarian's `audit_raw` keeps raws slug-aligned to
  minimize this risk.
- Obsidian caveat: rendering images outside the Obsidian vault root
  may not work depending on the viewer config. The links are still
  valid markdown and render in VS Code, GitHub, and pandoc.
- Use `/wiki-maintain` to back-fill `## Figures` across the whole vault
  before running illustrate on multiple concepts in a row.
