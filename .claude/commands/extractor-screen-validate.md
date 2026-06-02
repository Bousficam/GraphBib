---
description: PRISMA pre-screening DOI gate — validates every DOI in screening/dedup.csv against Crossref, recovers missing DOIs via bibliographic search, cross-checks title + year, rehabilitates `anon-YYYY` slugs once a real DOI is recovered. Surfaces mismatches for user audit before /extractor-screen-tiab runs (so the title/abstract screener doesn't decide on a wrong paper). Cached + idempotent.
argument-hint: "[<vault>/]<project-name>  [--force]"
---

Run the DOI hygiene gate on `screening/dedup.csv`.

Arguments: $ARGUMENTS

# When to use

Between `/extractor-screen-init` (built `criteria.md`) and
`/extractor-screen-tiab` (title/abstract pass). The validation gate
is **strongly recommended** but not mandatory — the screener-tiab
agent will still default to `uncertain` on rows with a flagged DOI
mismatch even if you skip this command. The command makes the
mismatches **visible** so you can fix them in bulk before screening
1000+ rows.

Re-run any time:

- A new CSV export was added to `screening/identified/`
  (after re-running `screen_dedupe.py`).
- You suspect the title/abstract for a specific row is for a
  different paper than expected.
- Crossref has updated metadata for DOIs that were `unverifiable`
  on a previous run.

# What it does

Calls `tools/screen_fetch_metadata.py --validate-only` under the
hood. Three passes, each cached in `tools/.cache/crossref.json`:

1. **DOI recovery** — for every row with no DOI, search Crossref
   with `<title> <first_author> <year>`. If a hit clears the
   relevance + title-overlap gate, the DOI is written into the row
   and flagged `doi_status=recovered`.
2. **DOI validation** — for every row WITH a DOI, ping
   `api.crossref.org/works/{doi}/agency`. Hits flagged `valid`;
   404s flagged `invalid` (Crossref has never registered that DOI).
3. **Title + year cross-check** — for every valid/recovered DOI,
   fetch Crossref's canonical title + year. SequenceMatcher
   similarity ≥ 0.75 → `doi_title_match=true`; year within ±1 →
   `doi_year_match=true`. Failures are logged as ERROR-level
   warnings.

A bonus pass runs **slug rehab** for rows that came out of dedup as
`anon-YYYY` (CSV had no parseable first author): once a DOI is
recovered or validated, the slug is re-derived as `<family>-<year>`
from Crossref's first-author family name. This pass is
**automatically locked** if `tiab-decisions.csv` already exists —
renaming slugs after screening would orphan decisions.

# Outputs

| File | Purpose |
|---|---|
| `screening/dedup.csv` | Now has columns `doi_status`, `doi_title_match`, `doi_year_match`, `slug_rehabilitated` populated. |
| `screening/reports/doi-warnings.md` | Human-readable: every ERROR + WARN with the offending row. Skipped silently when no issues. |
| `screening/slug-renames.csv` | `old_slug, new_slug, doi` triples for the rehab audit trail. Skipped silently when nothing was renamed. |

# Procedure

## Step 1 — Resolve the project path

Parse `$ARGUMENTS`:
- `<vault>/<project>` or `<project>` (vault auto-detected from
  `$PROJECT_VAULT` or single sub-vault, same rules as
  `/extractor-init`).
- `--force` to re-validate every DOI even when `doi_status` is
  already populated from a previous run (Crossref may have updated
  records).

Build the project path:
```
project-review/<vault>/<project>/        # phased layout
project-review/<project>/                # legacy flat fallback
```

Refuse if `screening/dedup.csv` doesn't exist (instruct user to run
`/extractor-screen-init` then `python tools/screen_dedupe.py
<project>` first).

## Step 2 — Run the validation pass

```bash
python tools/screen_fetch_metadata.py <project-path> --validate-only [--force]
```

The tool prints a per-status summary to stdout:

```
✓ Records       : 287
  DOI healing  :
    valid: 251
    recovered: 12
    invalid: 3
    missing: 21
  Slug rehab   : ran (8 renamed)
✓ Wrote         project-review/<vault>/<name>/screening/dedup.csv
⚠ DOI warnings  project-review/<vault>/<name>/screening/reports/doi-warnings.md  (3 errors, 21 warnings — audit before /extractor-screen-tiab)
✓ Slug renames  project-review/<vault>/<name>/screening/slug-renames.csv (8 rows)
```

## Step 3 — Surface the audit results to the user

Read `screening/reports/doi-warnings.md` if it exists.

Display:
- The count of ERRORs, WARNs, INFOs.
- The list of ERRORs IN FULL (title-mismatch + invalid DOIs — these
  are the rows the user should NOT trust as-is).
- A SAMPLE (≤ 10) of WARNs (missing DOIs that Crossref search
  couldn't recover).
- The list of slug renames (if any).

Frame the gate explicitly:

```
DOI hygiene gate complete.

ERRORS (audit required, screener will mark uncertain):
  • <slug>: title mismatch (sim=0.47)
      CSV says    : <truncated CSV title>
      Crossref DOI: <truncated Crossref title>
  • <slug>: DOI 10.xxx/yyy not recognized by Crossref

WARNINGS (no DOI recoverable from metadata):
  • <slug>: too little metadata (title/author/year empty)
  ... (15 more, see screening/reports/doi-warnings.md)

SLUG RENAMES (audit-only; decisions not yet taken so safe):
  anon-2024 → khedr-2024  (DOI 10.xxx/aaa)
  anon-2021 → cervera-2021 (DOI 10.xxx/bbb)
  ...
```

## Step 4 — Offer the user three actions

Ask the user what to do BEFORE handing off to `/extractor-screen-tiab`:

1. **Accept** — keep the flags as-is and run T/A screening. The
   screener-tiab agent will auto-mark `uncertain` for every row
   with `doi_title_match=false`, surfacing them at the T/A audit
   gate for manual review.
2. **Fix one row** — open the user's editor on `dedup.csv`, jump
   to a specific row, let the user paste the correct DOI. Re-run
   `python tools/screen_fetch_metadata.py <project-path>
   --validate-only --force` to re-validate just that row.
3. **Drop the bad rows** — for ERROR-level rows the user is
   confident are unrecoverable. Backup `dedup.csv` to
   `dedup.before-doi-cleanup.csv`, then filter:
   ```bash
   python -c "
   import csv
   with open('<project>/screening/dedup.csv') as f:
       rows = list(csv.DictReader(f))
   fields = list(rows[0].keys()) if rows else []
   kept = [r for r in rows if r.get('doi_title_match') != 'false' and r.get('doi_status') != 'invalid']
   with open('<project>/screening/dedup.csv', 'w', newline='') as f:
       w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(kept)
   print(f'Kept {len(kept)} of {len(rows)}')
   "
   ```
   Log the drops in `screening/reports/doi-warnings.md` under a
   `## Manual drops` section.

Default: **Accept** (option 1) — the validation flags propagate
into the screener prompts; nothing is lost; the T/A audit gate
catches anything that needs human eyes.

## Step 5 — Update the log

Append to `<project-path>/log.md`:

```markdown
## YYYY-MM-DD — DOI validation gate
- Records         : 287
- Valid           : 251
- Recovered       : 12  (DOIs filled in via Crossref search)
- Invalid         : 3   (audit: see reports/doi-warnings.md)
- Missing         : 21  (no DOI recoverable from metadata)
- Title mismatch  : 5
- Slug rehab      : 8 anon-* slugs rewritten to <family>-<year>
- User action     : accepted | fixed N | dropped N
```

# Hand-off

After this gate:

- The user runs `/extractor-screen-tiab <vault>/<project>` for
  PRISMA pass 1 (title/abstract).
- Every row with `doi_title_match=false` will be auto-flagged
  `uncertain` by the screener-tiab agent (criterion tag
  `doi-title-mismatch`), surfaced at the T/A audit gate.
- Every row with `doi_status=invalid` AND no abstract will be
  auto-flagged `uncertain` (criterion tag `doi-invalid-no-abstract`).
- The screener-fulltext agent (pass 2) cross-checks the body's title
  against the row title and returns `wrong-pdf-fetched` if they
  diverge — the last line of defense if a bad DOI slipped through
  silently.

# Hard constraints

- Never modify `criteria.md`, `contexte.md`, or `background/notes.md`
  from this command. DOI hygiene is a metadata problem; criteria
  authorship stays with the user via `/extractor-screen-init`.
- Never delete `dedup.csv` rows without explicit user confirmation
  in Step 4. Defaults to **non-destructive** (Accept).
- Never run when `tiab-decisions.csv` already exists AND the user
  hasn't passed `--force`. Reason: slug rehab is locked once
  decisions exist (renaming would orphan them). If the user really
  wants to re-validate, instruct them to first archive the existing
  decisions (`mv tiab-decisions.csv tiab-decisions.before-revalidate.csv`).
