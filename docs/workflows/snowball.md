# Snowball Workflow

Triggered by: *"snowball <slug>"*, `/wiki-snowball`, or a reading-discovery
pass. **Never triggered by an ingest.**

Snowball is the citation-network work: harvesting what a paper cites
(backward) and what cites it (forward), so the wiki can grow along its
own edges. It used to run inside the ingest workflow, which coupled two
unrelated jobs - extracting a paper's content, and shopping for the next
paper - and forced the ingesting agent to read a bibliography it had no
use for. It is now a standalone workflow with its own trigger.

## Why it is detached

- An ingest reads the body of one article and writes claims. The
  reference list carries no claim; step 1 of `docs/workflows/ingest.md`
  forbids reading it. Snowball reads the reference list and nothing else.
- Snowball is a *decision* about what to read next. It belongs to a
  reading session, at the user's pace, not to every ingest.
- Backward snowball is deterministic (regex + Crossref) and forward
  snowball is an API pass. Neither needs the ingesting agent's context.

## Backward - what this paper cites

Runs on a source already in the wiki. The reference list is read from
the **converted article in `raw/`** (the wiki page has none), and only
`cites:` on the wiki page is written. `raw/` is never modified.

```bash
# One source
python tools/parse_references.py --curate \
  --refs-from raw/<vault>/papers/<slug>.md \
  wiki/sources/<path>/<slug>.md

# Whole vault, resolving each page's source_file: pointer
python tools/parse_references.py --curate --refs-from-raw --all wiki/sources/
```

Three phases, each opt-in:

- default - regex DOI extraction (offline, fast).
- `--validate` - checks each DOI against Crossref; DOIs broken at a line
  break by the converter are dropped.
- `--curate` - for entries with no valid DOI, a Crossref bibliographic
  free-text search recovers the canonical DOI, accepted only above a
  relevance-score and title-overlap threshold. Recovered DOIs are tracked
  in `cites_curated:` for audit.

A local cache (`tools/.cache/doi_validation.json`) makes re-runs nearly
free.

Then write the page sections the harvest feeds:

- `## Cites` - wikilinks for DOIs already in the wiki, raw DOIs for the
  rest (the snowball candidates).
- `## Notable References` (theses and books) - the 10-30 references the
  document builds on most heavily.

## Forward - what cites this paper

`tools/suggest_readings.py --forward`, or the `suggest-reading` sub-agent
for interpretation against the wiki's gaps. Ranks candidates by
co-citation, velocity and venue h-index. Full description in
`docs/workflows/suggest-readings.md`.

## Aggregate - what the wiki is converging on

`tools/suggest_readings.py <concept>` surfaces DOIs cited by 2+ wiki
sources but absent from it. This is the payoff of the backward pass:
it only works on sources whose `cites:` has been harvested.

## Output

A prioritized candidate list. **Never auto-ingest.** The user picks;
`fetch-reading` downloads the open-access ones; `/wiki-batch-ingest`
ingests what was fetched.

## Where it is invoked from

| Entry point | Scope |
|---|---|
| `/wiki-snowball <slug>` | one source, backward + forward |
| `/wiki-snowball --all` | vault-wide backward harvest |
| `/wiki-discover` | wiki-wide discovery pipeline (suggest → fetch → convert → ingest) |
| `librarian` | maintenance re-harvest of `cites:` across the vault |

The ingest workflow appears nowhere in that table, by design.
