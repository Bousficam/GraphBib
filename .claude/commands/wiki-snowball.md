---
description: Citation snowball on a source - harvest what it cites (backward) and what cites it (forward). Standalone; never runs as part of an ingest.
argument-hint: "<source-slug> [--backward-only|--forward-only] | --all"
---

Grow the wiki along its citation edges: what did this paper build on,
and what has been built on it since?

Arguments: `$ARGUMENTS`

- `<source-slug>` - the source to snowball (e.g. `lefaucheur-2014`,
  `cervera-2020`). Default: backward **then** forward.
- `--backward-only` / `--forward-only` - one direction.
- `--all` - vault-wide backward harvest, no forward pass.

Read `docs/workflows/snowball.md` before starting.

# Why this is a command and not an ingest step

Ingestion never reads a bibliography (`docs/workflows/ingest.md` step 1)
and never surfaces snowball candidates. So a freshly-ingested source has
an empty `## Cites` until this command is run on it. That is the
intended state, not a gap to fix during the ingest.

# Procedure

## 1 - Resolve the source

Find `wiki/sources/**/<slug>.md`. Read its frontmatter: `doi`,
`source_file` (the converted article under `raw/`), and whether `cites:`
is already populated.

If `source_file` is missing or stale, run
`python tools/audit_raw.py --source <slug> --apply` first - the backward
pass reads the reference list from that file.

## 2 - Backward pass (unless `--forward-only`)

The reference list lives in the converted article, not on the wiki page.
Read it from there, write only to the wiki page:

```bash
python tools/parse_references.py --curate \
  --refs-from raw/<vault>/papers/<slug>.md \
  wiki/sources/<path>/<slug>.md
```

For `--all`:

```bash
python tools/parse_references.py --curate --refs-from-raw --all wiki/sources/
```

Never point `parse_references.py` at a file under `raw/` as its target -
it writes frontmatter, and `raw/` is immutable. `--refs-from` reads it.

Then write, on the source page:

- `## Cites` - `[[wikilink]]` for each DOI already in the wiki, raw DOI
  for the rest (those are the backward candidates).
- `## Notable References` (theses and books only) - the 10-30 references
  the document leans on most, judged by how often the body cites them.

## 3 - Forward pass (unless `--backward-only` or `--all`)

Delegate to the `suggest-reading` sub-agent in focused-source mode:

```
Agent(subagent_type=suggest-reading,
      prompt="Forward-citation snowball from <slug>. Use OpenAlex,
              return tier-1 candidates ranked by velocity x venue h-index,
              with rationale per candidate.")
```

The sub-agent resolves the DOI, calls OpenAlex
`/works/<id>/cited_by_api_url`, filters on velocity >= 2.5 AND venue
h-index >= 30, and returns a tiered list.

## 4 - Report

```
Snowball: <slug>
Backward: <N> DOIs harvested, <M> already in the wiki, <K> candidates
Forward : Tier 1 <n> / Tier 2 <n> / Tier 3 <n>
Top candidates:
  - <DOI> - <title> (<year>, <venue>) - <one-line rationale>
```

Ask the user which candidates to pursue. **Never auto-ingest.** On
approval, hand the DOIs to `fetch-reading`, then `/wiki-convert`, then
`/wiki-batch-ingest`.

# Notes

- Differs from `/wiki-discover`, which scans the whole wiki and
  aggregates co-citations across all sources. Use this when you want ONE
  paper's neighbourhood.
- The aggregate view (`tools/suggest_readings.py <concept>`, DOIs cited
  by 2+ wiki sources) only works on sources whose `cites:` has been
  harvested - so run `--all` once after a batch ingest.
- Common use case: after ingesting a major guideline or meta-analysis,
  `/wiki-snowball <slug>` to find both its foundations and its
  descendants.
