# Conversion Workflow

Triggered by: *"convert pdfs from <path>"*, *"convert epubs from
<path>"*, *"run the conversion pipeline"*, or `/wiki-convert <SRC>
[DST]`.

This workflow turns a directory of source documents (PDFs, EPUBs)
into ingestion-ready Markdown. It is **separate from ingestion** - 
it produces the input that the Ingest Workflow consumes.

## Phases (PDFs)

1. **Marker conversion** (`pdf2md/pdf2md_marker.py SRC DST`) - 
   high-fidelity PDF → Markdown, mirrored arborescence, idempotent.
   Writes `marker_report.json`.

2. **Mistral OCR (opt-in)** (`pdf2md/pdf2md_mistral.py SRC DST`) - 
   retries marker `errors`/`suspicious` via Mistral Document AI.
   Better on tables, equations, scans. Needs `MISTRAL_API_KEY` (free
   experimental at `console.mistral.ai`; script prompts if missing).
   Writes `mistral_report.json`. Skip if no key.

3. **Fallback** (`pdf2md/pdf2md_fallback.py SRC DST`) - last resort,
   pymupdf4llm. Writes `fallback_report.json`.

4. **Enrich frontmatter** (`pdf2md/enrich_frontmatter.py DST`) - 
   Crossref lookup populates `title`, `authors`, `journal`, `year`,
   `doi`. Same pass extracts a raw `cites:` list from the References
   section by regex. Writes `enrich_report.json`.

5. **Validate + curate citations**
   (`tools/parse_references.py --curate --all DST`) - each extracted
   DOI is checked against Crossref; broken or missing DOIs are
   recovered via free-text bibliographic search when score and title
   overlap thresholds pass. Writes the validation cache to
   `tools/.cache/doi_validation.json` (gitignored).

## Phase E (EPUBs - academic books)

EPUB is the native distribution format for most contemporary
academic books, edited volumes, and handbooks. Unlike PDFs, EPUBs
expose chapter structure and bibliographic metadata directly through
the OPF manifest, so conversion is cleaner.

**EPUB conversion** (`pdf2md/epub2md.py SRC [DST]`) - walks SRC
recursively for `*.epub`, mirrors arborescence to DST (default
`raw/<vault>/books/`), and converts each book to Markdown via **pandoc**
(primary) or **markitdown** (fallback). Metadata is extracted from
the OPF (`dc:title`, `dc:creator` with `aut`/`edt` roles, ISBN,
publisher, year, language) and written to frontmatter. The backend
used (`pandoc-epub` or `markitdown-epub`) is recorded for audit.
Writes `epub.log` and `epub_report.json`. Idempotent.

For long books / edited volumes (≥ 150 pages or any handbook with
distinct per-chapter authors), follow with `pdf2md/split_thesis.py`
on each produced `raw/<vault>/books/<slug>.md` - the script splits by
chapter heading and is type-agnostic. The chapters then ingest via
`source-academic-paper.md` with the `parent_book` / `book_editors`
extra fields documented in `docs/templates/source-book.md`.

After Phase E, the Crossref enrichment + reference curation phases
(Phases 4-5 above) apply identically to book chapters that contain
DOI-bearing references.

## Agent procedure

1. Confirm SRC exists. **Sniff content**:
   - PDFs present → default DST `raw/<vault>/papers/`, run Phases 1-5.
   - EPUBs present → default DST `raw/<vault>/books/`, run Phase E + Phases
     4-5 on the produced markdown.
   - Both → ask which to process (or run both in sequence with
     distinct DSTs).
2. Run Phase 1 (marker) for PDFs, surface `marker_report.json`.
3. Phase 2 (Mistral) is **opt-in** - if marker left errors/suspicious,
   ask: *"N entries unprocessed. Run Mistral OCR (free experimental
   plan, prompts for MISTRAL_API_KEY)? Otherwise go to Phase 3."*.
4. Run Phase 3 (pymupdf4llm), Phase 4 (enrich) - surface each report.
5. For Phase E (EPUBs), check pandoc availability first
   (`which pandoc`). If absent, suggest install (`apt install pandoc`
   / `brew install pandoc`) or fall back to `--engine markitdown`.
6. After EPUB conversion, ask whether to split long books:
   *"K books ≥ 150 pages produced. Split each into per-chapter pages
   via `split_thesis.py`?"*.
7. Phase 5 is network-heavy (5-13 min); **ask before launching**
   Crossref curation. Otherwise stop and tell the user to run it later.
8. Print recap (converted / metadata / cites: / total per format) and
   suggest ingestion via `/wiki-batch-ingest`.

If any phase errors, stop and show the error before going further. The
pipeline is idempotent - the user can re-run the same command and only
the unfinished work will be redone.
