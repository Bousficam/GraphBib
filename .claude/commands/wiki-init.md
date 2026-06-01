---
description: Initialize a fresh vault — create wiki/<vault-name>/ with the standard sub-folders + seed index.md / log.md / overview.md. Also creates raw/ at the repo root on first run. Multi-vault aware — each invocation adds a new vault sub-folder.
argument-hint: "<vault-name>"
---

Set up a clean vault inside the wiki/ directory. Use this:
- Once per research domain you want to track (e.g. `stroke-rehab`,
  `cardiology`, `nlp-research`)
- After manually deleting `wiki/<vault>/` to recover

# Multi-vault layout

```
wiki/                           ← parent (not opened directly in Obsidian)
├── <vault-1>/                  ← one Obsidian vault per research domain
│   ├── index.md, log.md, overview.md
│   ├── sources/, concepts/, methods/, recommendations/, questions/, syntheses/, entities/
├── <vault-2>/
│   └── ...
```

Each `wiki/<vault>/` is independent: its own sources, concepts,
citation graph. The agent operates on one vault at a time, resolved
via this priority (handled by `tools/_lib.py:_detect_active_vault`):

1. `$WIKI_VAULT` env var → `wiki/$WIKI_VAULT/`
2. Single vault present  → that one, automatically
3. Legacy flat layout    → `wiki/` itself (backward-compat for
   pre-multi-vault wikis where `wiki/sources/` exists at the root)
4. Multiple vaults, no env → ambiguous; tools warn and ask user

`raw/` (shared pool of source documents) stays flat at the repo
root — its content is reusable across vaults. Each ingest pulls
from `raw/` into the active vault's `sources/`.

# Procedure

## Step 1 — Confirm scope

Parse `$ARGUMENTS`:
- Required: `<vault-name>` (kebab-case, no slashes, no spaces).
  Examples: `stroke-rehab`, `cardiology`, `nlp-llm-evaluation`.

If `$ARGUMENTS` is empty, ASK the user:

> *"What's the name of this vault? (kebab-case, e.g. `stroke-rehab`,
> `cardiology`, `materials-science`). Each vault is a self-contained
> knowledge graph for one research domain."*

Refuse names that:
- Contain `/`, ` `, or start with `.`
- Match reserved sub-artifact names: `sources`, `concepts`, `methods`,
  `recommendations`, `questions`, `syntheses`, `entities`,
  `interventions`, `index`, `log`, `overview`
- Are repo top-level dirs: `raw`, `pdf2md`, `tools`, `docs`,
  `.claude`, `graph`, `project-review`, `wiki`

## Step 2 — Detect existing layout

```bash
ls -la wiki/ 2>&1 | head
```

Three cases:

**A. `wiki/` doesn't exist or is empty** → proceed cleanly.

**B. `wiki/<name>/` already exists** → REFUSE. Ask user to `rm -rf
wiki/<name>` first if they want to reset that vault.

**C. `wiki/sources/` exists directly (legacy flat layout)** →
Ask the user:

> *"Existing wiki uses the legacy flat layout (`wiki/sources/`,
> `wiki/concepts/`, …). Multi-vault expects `wiki/<vault>/sources/`.
>
> Options:
>   [1] Migrate the existing content into a vault first
>       (rename to `wiki/<existing-vault-name>/`), then create
>       `wiki/<new-name>/` alongside.
>   [2] Skip — keep using the flat layout (legacy mode stays
>       supported, but you can only have one vault).
>   [3] Cancel.*

If [1], propose a default migration name (slug from `context.md`'s
declared domain) and confirm:

```bash
mkdir -p wiki/<migration-target>
mv wiki/sources wiki/<migration-target>/
mv wiki/concepts wiki/<migration-target>/   # etc. for every existing subfolder
mv wiki/index.md wiki/<migration-target>/
mv wiki/log.md wiki/<migration-target>/
mv wiki/overview.md wiki/<migration-target>/
```

Then proceed to Step 3 for the new vault.

## Step 3 — Create the vault directory structure

```bash
mkdir -p raw/papers raw/theses raw/books raw/notes
mkdir -p wiki/<vault>/sources/articles wiki/<vault>/sources/theses wiki/<vault>/sources/books
mkdir -p wiki/<vault>/entities wiki/<vault>/concepts wiki/<vault>/methods
mkdir -p wiki/<vault>/interventions wiki/<vault>/recommendations wiki/<vault>/questions
mkdir -p wiki/<vault>/syntheses
```

The `raw/` tree is shared across vaults — created once if missing,
left alone otherwise.

## Step 4 — Seed the three top-level vault files

Create `wiki/<vault>/index.md`:

```markdown
# <vault> — Wiki Index

## Overview
- [Overview](overview.md) — living synthesis

## Sources — Papers
*(empty — populated on ingest)*

## Sources — Theses
*(empty)*

## Sources — Books
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

Create `wiki/<vault>/log.md`:

```markdown
# <vault> — Wiki Log

Append-only chronological record of every wiki operation. Format:
`## [YYYY-MM-DD] <operation> | <title>`

Operations: ingest, query, review, cite, health, lint, graph.
```

Create `wiki/<vault>/overview.md`:

```markdown
---
title: "<vault> — Wiki Overview"
type: synthesis
last_updated: <today>
sources: []
---

## Scope
Living synthesis across all sources ingested into the `<vault>` vault.

## Key Findings (synthesized)
*(empty — populated as the vault grows)*

## Major Concepts
*(none yet)*

## Major Methods
*(none yet)*

## Active Debates
*(none yet)*

## Recent Updates
*(none yet)*
```

## Step 5 — Verify

```bash
find raw/ wiki/<vault>/ -type d | sort
```

## Step 6 — Suggest next steps + activation guidance

If this is the **only vault** (`wiki/` had no other vaults), no
further config needed — tools auto-detect it.

If this is the **second+ vault**, tell the user:

```
Multiple vaults now exist in wiki/. Set the active one explicitly
when running tools (otherwise they'll error with "ambiguous"):

  export WIKI_VAULT=<vault>            # current shell
  WIKI_VAULT=<vault> python tools/...  # one-off command

Or run /wiki-status to see which vaults exist and switch.
```

Then the usual onboarding:

```
Vault `<vault>` initialized. Suggested next steps:

1. Drop your PDFs into raw/papers/ or raw/theses/ (shared across vaults).
2. Run /wiki-convert <path-to-pdfs> raw/papers/  (or theses/)
3. Run /wiki-batch-ingest raw/papers/
   (ingest goes into wiki/<vault>/sources/)

If you have a research focus already, edit context.md (at the repo
root) to reflect it — the agent uses the domain context for template
selection and concept naming conventions. Per-vault context lives at
wiki/<vault>/context.md (overrides the root context.md when present).
```

# Hard constraints

- **NEVER overwrite an existing `wiki/<vault>/index.md`,
  `log.md`, or `overview.md`** — refuse and ask the user to remove
  the vault folder first.
- **NEVER create the vault structure outside `wiki/`** (refuse paths
  with `/`, including `wiki/sub/sub2`).
- **The vault name MUST be kebab-case** (lowercase letters, digits,
  hyphens). Reject `STROKE_REHAB`, `Stroke Rehab`, `stroke.rehab`.
- **Refuse** names matching reserved repo-level or sub-artifact
  names listed in Step 1.

# Notes

- `raw/` and `wiki/` are gitignored by default — they hold YOUR
  content, not committed to the repo. Adjust `.gitignore` if you
  want to commit your vault(s) to a personal fork.
- This command is safe to re-run on a vault that already has files;
  it never overwrites existing files, only creates missing folders.
- For pre-multi-vault wikis (legacy `wiki/sources/` at the root), no
  immediate action required — `tools/_lib.py` keeps treating
  `wiki/` itself as a single implicit vault. Migrate when you're
  ready to have a second domain.
