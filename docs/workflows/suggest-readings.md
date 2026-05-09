# Suggest-Readings Workflow

Triggered by: *"suggest readings for: <concept>"* or
`/wiki-suggest-readings`. For richer interpretation against the
wiki's gaps, delegate to the `suggest-reading` sub-agent.

Surfaces complementary readings to deepen a concept. Two modes:

## Internal mode (default)

Runs `tools/suggest_readings.py <concept>`:

- Walks `wiki/sources/`, collects every source tagged with the concept.
- Aggregates each source's `cites:` frontmatter (DOIs cited).
- Surfaces DOIs cited by **2+ wiki sources** but not yet present in any
  `wiki/sources/*.md` `doi:` field.
- Sorted by citation frequency. Each candidate shows: count, DOI, the
  wiki sources that cite it.

## Forward mode (`--forward`, OpenAlex)

- For each wiki source with a DOI, lists top-50 papers citing it.
- Aggregates co-citations across the wiki, ranks candidates by:
  `score = co_citation × 100 + velocity + log10(venue_h)`
- Filter: `co_citation ≥ 2 OR (velocity ≥ 2.5 AND venue_h ≥ 30)`.
  Velocity = `cited_by_count / max(1, age_years)` normalises bias for
  recent papers. Cached in `tools/.cache/openalex_forward.json`.

Output: a Markdown list of candidates with bibliographic metadata.
The user picks which to ingest.

## Auto-fetch open-access PDFs

Pipe to `tools/fetch_oa.py` (uses Unpaywall):

```bash
python tools/suggest_readings.py --forward --top 30 \
  | python tools/fetch_oa.py --from-stdin
```

`fetch_oa.py` queries Unpaywall for each DOI, downloads the OA PDF
when available to `raw/papers/<author-year>.pdf`, skips paywalled /
non-OA / already-downloaded entries. Status per DOI in
`raw/papers/fetch_oa_report.json`. Set `UNPAYWALL_EMAIL=you@example.org`
once (Unpaywall ToS).

For end-to-end discovery (suggest → fetch → convert → ingest), use
`/wiki-discover`.
