---
description: Deepen an already-ingested source page that came out shallow (gaps in Background, missing outcomes, summary instead of enumerated recommendations).
argument-hint: "<source-slug>"
---

Re-extract a previously-ingested source to chapter depth.

Arguments: $ARGUMENTS — the source slug (e.g. `cervera-2020`,
`lefaucheur-2014`).

# Procedure

Delegate to the `source-extender` sub-agent:

```
Agent(subagent_type=source-extender, prompt="Deepen $ARGUMENTS")
```

The sub-agent:
- Reads the existing source page and its Extraction Checklist.
- Re-reads the original source MD (from the page's `source_file:`).
- Diagnoses gaps (Background under 5 bullets, secondary outcomes
  missing, limitations under 3 items, recommendations summarized
  instead of enumerated, methods listed as bare wikilinks, missing
  Reporting Standard Alignment, etc.).
- Re-extracts missing content with full IMRAD discipline and the
  Indirect Citation Rule.
- Updates the source page in place via Edit (preserves manual edits).
- Propagates new claims to relevant concept / method / intervention /
  recommendation / question pages.
- Re-runs the self-critique gate.

# Notes

- Use this when `lint` flags `checklist_incomplete` or
  `page_too_short` for a specific source, OR after an ingestion that
  came out clearly superficial.
- For a fresh ingestion (the source isn't yet in the wiki), use
  `ingester` (or `/wiki-batch-ingest`) instead.
- The sub-agent NEVER overwrites manual edits; it appends and
  expands.
- Cost: typically 15–30k tokens (one source body + the existing page
  + per-claim concept-page propagation).
