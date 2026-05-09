# Conversion Workflow

Triggered by: *"convert pdfs from <path>"*, *"run the conversion
pipeline"*, or `/wiki-convert <SRC> [DST]`.

This workflow turns a directory of PDFs into ingestion-ready Markdown
sources. It is **separate from ingestion** — it produces the input that
the Ingest Workflow consumes.

## Phases

1. **Marker conversion** (`pdf2md/pdf2md_marker.py SRC DST`) —
   high-fidelity PDF → Markdown, mirrored arborescence, idempotent.
   Writes `marker_report.json`.

2. **Mistral OCR (opt-in)** (`pdf2md/pdf2md_mistral.py SRC DST`) —
   retries marker `errors`/`suspicious` via Mistral Document AI.
   Better on tables, equations, scans. Needs `MISTRAL_API_KEY` (free
   experimental at `console.mistral.ai`; script prompts if missing).
   Writes `mistral_report.json`. Skip if no key.

3. **Fallback** (`pdf2md/pdf2md_fallback.py SRC DST`) — last resort,
   pymupdf4llm. Writes `fallback_report.json`.

4. **Enrich frontmatter** (`pdf2md/enrich_frontmatter.py DST`) —
   Crossref lookup populates `title`, `authors`, `journal`, `year`,
   `doi`. Same pass extracts a raw `cites:` list from the References
   section by regex. Writes `enrich_report.json`.

5. **Validate + curate citations**
   (`tools/parse_references.py --curate --all DST`) — each extracted
   DOI is checked against Crossref; broken or missing DOIs are
   recovered via free-text bibliographic search when score and title
   overlap thresholds pass. Writes the validation cache to
   `tools/.cache/doi_validation.json` (gitignored).

## Agent procedure

1. Confirm SRC exists and contains PDFs; default DST to `raw/papers/`.
2. Run Phase 1 (marker), surface `marker_report.json`.
3. Phase 2 (Mistral) is **opt-in** — if marker left errors/suspicious,
   ask: *"N entries unprocessed. Run Mistral OCR (free experimental
   plan, prompts for MISTRAL_API_KEY)? Otherwise go to Phase 3."*.
4. Run Phase 3 (pymupdf4llm), Phase 4 (enrich) — surface each report.
5. Phase 5 is network-heavy (5–13 min); **ask before launching**
   Crossref curation. Otherwise stop and tell the user to run it later.
6. Print recap (converted / metadata / cites: / total) and suggest
   ingestion via `/wiki-ingest`.

If any phase errors, stop and show the error before going further. The
pipeline is idempotent — the user can re-run the same command and only
the unfinished work will be redone.
