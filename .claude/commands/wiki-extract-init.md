---
description: Bootstrap a literature-review extraction project folder (contexte.md, instructions.md, template, articles/, output/). Pairs with /wiki-extract-table which extracts into the created folder.
argument-hint: "<project-name>  [--from-source <SR-slug>]  [--columns col1,col2,...]"
---

Create a fresh extraction project folder with the structure expected
by `/wiki-extract-table`.

Arguments: $ARGUMENTS

# What this command creates

```
<project-name>/
├── contexte.md           # narrative scope — agent seeds, user fills
├── instructions.md       # per-column spec — empty preamble, filled by Phase 1
├── template.xlsx         # 2-row template (slug + instruction)
├── articles/             # source MD files (linked or copied later)
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
  `articles/` is useful if the user wants a portable project folder
  (e.g. to share with a collaborator who doesn't have the full wiki
  cloned).

- `output/` is created empty. The slash command `/wiki-extract-table`
  writes there.

- This command does NOT touch the wiki. It only creates files under
  `<project>/`. Removing the project folder removes all artifacts.

- For multi-project users: each review lives in its own folder
  alongside the repo root (don't nest inside `wiki/`).

# Hard constraints

- **NEVER overwrite an existing `contexte.md`, `instructions.md`, or
  `template.{xlsx,csv}`.** Ask the user to remove it manually if they
  want a fresh project.
- **NEVER use a project name that conflicts with a repo top-level
  directory** (`raw`, `wiki`, `pdf2md`, `tools`, `docs`, `.claude`,
  `graph`). Refuse and ask for a different name.
- **NEVER call `extract_data.py --from-source` with a slug not present
  in `wiki/sources/`.** Verify first; if missing, suggest
  `/wiki-batch-ingest` first to ingest the SR.
