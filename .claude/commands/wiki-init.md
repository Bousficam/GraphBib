---
description: Initialize a fresh wiki — create the raw/ and wiki/ directory structure, seed empty index.md / log.md / overview.md, ready for first ingestions.
argument-hint: ""
---

Set up a clean wiki structure in the current repository. Use this
once when starting a new wiki, or to recover after manually deleting
the `raw/` or `wiki/` directories.

# Procedure

## Step 1 — Confirm scope

Check whether `raw/` or `wiki/` already exist with content:

```bash
ls -la raw/ wiki/ 2>&1 | head
```

If non-empty, ask: *"raw/ or wiki/ already has content. Initialize
will create missing folders only — existing files are preserved.
Proceed? [Y/n]"*. Wait.

## Step 2 — Create directory structure

```bash
mkdir -p raw/papers raw/theses raw/notes
mkdir -p wiki/sources/articles wiki/sources/theses
mkdir -p wiki/entities wiki/concepts wiki/methods
mkdir -p wiki/interventions wiki/recommendations wiki/questions
mkdir -p wiki/syntheses
```

## Step 3 — Seed the three top-level wiki files

Create `wiki/index.md`:

```markdown
# Wiki Index

## Overview
- [Overview](overview.md) — living synthesis

## Sources — Papers
*(empty — populated on ingest)*

## Sources — Theses
*(empty)*

## Concepts
*(empty)*

## Methods
*(empty)*

## Interventions
*(empty)*

## Recommendations
*(empty)*

## Questions
*(empty)*

## Entities
*(empty)*

## Syntheses
*(empty)*
```

Create `wiki/log.md`:

```markdown
# Wiki Log

Append-only chronological record of every wiki operation. Format:
`## [YYYY-MM-DD] <operation> | <title>`

Operations: ingest, query, review, cite, health, lint, graph.
```

Create `wiki/overview.md` (using the format from
`docs/templates/overview.md`):

```markdown
---
title: "Wiki Overview"
type: synthesis
last_updated: <today>
sources: []
---

## Scope
Living synthesis across all ingested sources for the user's research domain.

## Key Findings (synthesized)
*(empty — populated as the wiki grows)*

## Major Concepts
*(none yet)*

## Major Methods
*(none yet)*

## Active Debates
*(none yet)*

## Recent Updates
*(none yet)*
```

## Step 4 — Verify

```bash
find raw/ wiki/ -type d | sort
```

Should show:

```
raw/
raw/notes
raw/papers
raw/theses
wiki/
wiki/concepts
wiki/entities
wiki/interventions
wiki/methods
wiki/questions
wiki/recommendations
wiki/sources
wiki/sources/articles
wiki/sources/theses
wiki/syntheses
```

## Step 5 — Suggest next steps

```
Wiki initialized. Suggested next steps:

1. Drop your PDFs into raw/papers/ or raw/theses/.
2. Run /wiki-convert <path-to-pdfs> raw/papers/  (or theses/)
3. Run /wiki-batch-ingest raw/papers/

If you have a research focus already (e.g. a domain or thesis topic),
edit CLAUDE.md to reflect it — the agent uses the domain context for
template selection and concept naming conventions.
```

# Notes

- `raw/` and `wiki/` are gitignored by default — they hold YOUR
  content, not committed to the repo. Adjust `.gitignore` if you
  want to commit your wiki to a personal fork.
- This command is safe to re-run; it never overwrites existing
  files, only creates missing folders.
