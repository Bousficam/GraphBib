---
description: Bootstrap a literature-review extraction project folder (contexte.md, instructions.md, template, articles/, output/). Pairs with /wiki-extract-table which extracts into the created folder.
argument-hint: "<project-name>  [--from-source <SR-slug>]  [--columns col1,col2,...]"
---

Create a fresh extraction project folder with the structure expected
by `/wiki-extract-table`.

Arguments: $ARGUMENTS

# Project folder vs. the wiki — IMPORTANT

GraphBib has **two distinct types of folders**:

| Folder | Purpose | Obsidian? |
|---|---|---|
| `wiki/` (at repo root) | The agent's knowledge graph: sources, concepts, methods, recommendations, questions, syntheses, entities. Read by Obsidian as a vault. | **YES** — opened as an Obsidian vault |
| `<project>-review/` (sibling of wiki/) | Self-contained literature-review extraction project: contexte, instructions, template, articles, output. **NOT part of any Obsidian vault.** | **NO** — pure file system, opened in Excel / a code editor |

This command creates the **project folder**, which is **separate from
the wiki and outside any Obsidian vault**. The wiki keeps its job
(domain knowledge graph). The project folder is a focused
analytical artifact for ONE specific systematic review / literature
review.

# Location

The project folder is created **at the repo root**, as a sibling of
`wiki/`:

```
GraphBib/                        ← repo root
├── wiki/                        ← Obsidian vault (knowledge graph)
├── raw/                         ← source MDs / PDFs
├── docs/, tools/, pdf2md/       ← agent infrastructure
└── <project>-review/            ← THIS COMMAND creates folders here
```

The command **refuses** to create a project inside `wiki/`,
`raw/`, `docs/`, `tools/`, or any other repo top-level directory —
projects are first-class artifacts at the same level as those, not
nested under them.

# What this command creates

```
<project>-review/
├── contexte.md           # narrative scope — agent seeds, user fills
├── instructions.md       # per-column spec — empty preamble, filled by Phase 1
├── template.xlsx         # 2-row template (slug + instruction)
├── articles/             # source MD files (linked or copied from wiki/sources/ later)
└── output/               # extraction outputs land here (empty for now)
```

Naming: if `$ARGUMENTS` does not end in `-review`, append `-review` for
clarity (e.g. `mibci → mibci-review`). Override by passing the exact
folder name.

# Procedure

## Step 1 — Confirm scope

Parse `$ARGUMENTS`:
- First positional argument = project name (e.g. `mibci-stroke`)
- `--from-source <SR-slug>` (optional) — seed the template's data
  rows from the SR's `cites:` list
- `--columns col1,col2,...` (optional) — column set for the template;
  default is the 27-column SR set in `tools/extract_data.py`

Show the plan and ask before creating:

```
Will create: ./<project-name>-review/
  ├── contexte.md   (seeded with research-question prompts)
  ├── instructions.md   (empty preamble)
  ├── template.xlsx   (M columns × N rows)
  │     M = 27 (default SR set) | <count from --columns>
  │     N = 0 (manual) | <count from --from-source cites>
  ├── articles/   (empty)
  └── output/   (empty)
Proceed? [Y/n]
```

If the folder already exists and is non-empty:
- If any of `contexte.md`, `instructions.md`, `template.{xlsx,csv}` exist
  → REFUSE. Ask user to pick a different name or `rm -rf` themselves
  before re-running (don't overwrite their work).
- If folder exists but empty → proceed.

## Step 2 — Create the folder structure

```bash
mkdir -p <project>/articles <project>/output
```

## Step 3 — Seed contexte.md

Write `<project>/contexte.md` with a guided template the user fills:

```markdown
# Project context — <project-name>

> Fill me before running /wiki-extract-table. The extraction agent
> reads this to ground inclusion / exclusion decisions and to
> calibrate its style.

## Research question

(One sentence — the PICO question if clinical, the cause-effect
hypothesis if experimental, the construct under review if theoretical.)

## Inclusion criteria

- Population: ...
- Intervention / Exposure: ...
- Comparator (if applicable): ...
- Outcomes of interest: ...
- Study designs: RCT, cohort, ...
- Date range: YYYY-MM-DD to YYYY-MM-DD
- Languages: en, fr, ...

## Exclusion criteria

- ...

## Notes for the extraction agent

- Domain priors (e.g. *prefer ITT over PP analyses*)
- Style preferences (e.g. *quote dose parameters verbatim*)
- Known caveats (e.g. *MEP amplitude is reported in mV or µV — convert
  to mV*)

## Source list

(Filled by the agent after `--from-source` or manually. One slug per
line, matching `wiki/sources/<slug>.md`.)

- cervera-2020
- khedr-2005
...
```

## Step 4 — Seed instructions.md (empty preamble)

Write `<project>/instructions.md`:

```markdown
# Extraction instructions — <project-name>

> Auto-populated by the `/wiki-extract-table` Phase 1 debrief.
> Each column gets a section with the row-2 terse instruction
> plus narrative detail and edge cases.

(Empty — run `/wiki-extract-table <project>/` to populate.)
```

## Step 5 — Create the template

### Path A — `--from-source <SR-slug>` provided

```bash
python tools/extract_data.py \
    --from-source <SR-slug> \
    -o <project>/template.xlsx \
    --no-spec
```

`--no-spec` skips the legacy INSTRUCTIONS/TYPE/SCALE rows so you get
a clean 2-row format the user fills via Phase 1 debrief.

Pass `--columns` if provided.

### Path B — no --from-source

Create an empty template with just headers + empty row 2:

```python
python tools/extract_data.py --from-source __empty__ -o <project>/template.xlsx --no-spec --columns "<cols>"
```

If that doesn't work (since `__empty__` isn't a real slug), write the
template directly with openpyxl:

```python
python - <<'PY'
from openpyxl import Workbook
cols = ["slug", "year", "design", "n_intervention", "n_control",
        "baseline_outcome", "post_outcome", "p_value", "effect_size",
        "risk_of_bias", "notes"]  # or args.columns split
wb = Workbook()
ws = wb.active
ws.append(cols)        # row 1: variable names
ws.append([""] * len(cols))  # row 2: empty instructions (Phase 1 will fill)
wb.save("<project>/template.xlsx")
PY
```

Default column set (if no `--columns`): the 27-field SR set used by
`extract_data.py --from-source`. Keep it broad — users delete what
they don't need.

## Step 6 — Final guidance

Print the next-steps message:

```
✓ Project created at ./<project>/

Next steps:
  1. Edit contexte.md  → fill research question + inclusion criteria
  2. Add sources to articles/  (copy / symlink from raw/papers/)
       cp wiki/sources/articles/bci/cervera-2020.md <project>/articles/
       (or just list slugs in contexte.md — extract_data.py will find them
        in the wiki regardless of articles/ contents)
  3. Run /wiki-extract-table <project>/
       → Phase 1 will debrief on empty template row 2,
         then write instructions.md and produce output/extraction-{detailed,coded}.xlsx
```

# Notes

- The `articles/` folder is a **convenience** — the actual source MD
  files live in `wiki/sources/<...>/<slug>.md` and `extract_data.py`
  finds them there via `load_sources()`. Copying / linking to
  `articles/` is useful only if the user wants a portable project
  folder (e.g. to share with a collaborator who doesn't have the full
  wiki cloned). For solo workflows, leave `articles/` empty —
  extraction reads straight from `wiki/sources/`.

- `output/` is created empty. The slash command `/wiki-extract-table`
  writes there.

- **This command does NOT touch the wiki.** It only creates files
  under `<project>-review/` at the repo root. Removing the project
  folder removes all artifacts; the wiki is unaffected.

- Each review lives in its OWN sibling folder. You can have many
  active reviews (`mibci-review/`, `tms-dose-response-review/`,
  `dti-biomarkers-review/`) — they don't interact, share no state,
  and each has its own `contexte.md` / `instructions.md` /
  `template.xlsx`.

- The project folder is intentionally NOT part of any Obsidian vault.
  Open `template.xlsx` in Excel / LibreOffice / Numbers; open
  `contexte.md` / `instructions.md` in any text editor. Obsidian
  stays focused on the wiki.

# Hard constraints

- **NEVER create the project folder inside `wiki/`** (or any repo
  top-level directory). Projects are siblings of `wiki/`, at the repo
  root. If the user passes a path containing `wiki/`, `raw/`,
  `docs/`, `tools/`, `pdf2md/`, `.claude/`, or `graph/`, REFUSE and
  explain the project / wiki separation.
- **NEVER overwrite an existing `contexte.md`, `instructions.md`, or
  `template.{xlsx,csv}`.** Ask the user to remove the folder manually
  if they want a fresh project.
- **NEVER use a project name that conflicts with a repo top-level
  directory** (`raw`, `wiki`, `pdf2md`, `tools`, `docs`, `.claude`,
  `graph`). Refuse and ask for a different name.
- **NEVER call `extract_data.py --from-source` with a slug not present
  in `wiki/sources/`.** Verify first; if missing, suggest
  `/wiki-batch-ingest` first to ingest the SR.
