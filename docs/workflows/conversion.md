# Conversion Workflow

Triggered by: *"convert pdfs from <path>"*, *"convert epubs from
<path>"*, *"run the conversion pipeline"*, or `/wiki-convert <SRC>
[DST]`.

This workflow turns a directory of source documents (PDFs, EPUBs)
into ingestion-ready Markdown. It is **separate from ingestion** - 
it produces the input that the Ingest Workflow consumes.

## Phases (PDFs)

1. **Mistral OCR - the default converter**
   (`pdf2md/pdf2md_mistral.py SRC DST [--files a.pdf b.pdf]`) - Mistral
   Document AI. Needs `MISTRAL_API_KEY` (free experimental at
   `console.mistral.ai`; script prompts if missing). Writes
   `mistral_report.json`. **Run this first** unless the user asks
   otherwise.

   *Why it is the default:* on a laptop CPU, marker runs roughly 40 min
   per paper (measured: 5 h 26 for two 17-page articles), Mistral about
   5 s. For a batch of any size, marker-first means the user waits
   hours before ingestion can even start.

   *What it costs:* Mistral is the better of the two on tables (it
   recovers tables with vertically-set headers that marker shreds
   character by character) and the worse on math - it corrupts
   superscripts and subscripts (observed: `2^36` rendered `2^90`,
   `(3!)^5` rendered `(3)^15`). Marker is the reverse.

2. **Marker conversion - opt-in, high-fidelity math pass**
   (`pdf2md/pdf2md_marker.py SRC DST`) - mirrored arborescence,
   idempotent, and the only backend that extracts figures into
   `<slug>_images/`. Writes `marker_report.json`. Run it when:
   - the source is math-heavy and exact exponents/matrix notation matter;
   - the ingest flagged unreadable formulas (see below);
   - figures are wanted on the source page (`source-illustrator` needs
     `<slug>_images/`).

   Because it is slow, launch it **in the background** (overnight for a
   batch) against a scratch DST, then reconcile: keep whichever
   conversion is better per artefact, or re-run `source-extender` on the
   affected source pages once the faithful math is available.

3. **Fallback** (`pdf2md/pdf2md_fallback.py SRC DST`) - last resort,
   pymupdf4llm. Writes `fallback_report.json`.

**Tell the ingester what it is reading.** Whichever backend produced the
markdown, the ingest MUST flag rather than guess: any exponent, index or
table cell that is not legible with certainty is reported as unverifiable
(with the paper's own prose quoted instead), never transcribed on a hunch.
This is a standing rule in `.claude/agents/ingester.md` > Citation
discipline; restate the backend used in the ingest prompt so the agent
knows which failure mode to watch for.

4. **Enrich frontmatter** (`pdf2md/enrich_frontmatter.py DST`) - 
   Crossref lookup populates `title`, `authors`, `journal`, `year`,
   `doi`. Same pass extracts a raw `cites:` list from the References
   section by regex. Writes `enrich_report.json`.

   **The script is not incremental**: it walks DST recursively and
   re-enriches *every* `.md` it finds, already-enriched ones included.
   Pointing it at a populated `raw/<vault>/papers/` therefore rewrites
   hundreds of files and hammers Crossref. For an incremental batch,
   copy just the new `.md` into a scratch directory, enrich there,
   **check the resulting `doi:` against the PDF's own first page**, then
   copy back - `enrich_frontmatter` is known to mis-tag a source with a
   DOI harvested from one of its cited references.

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
2. Run Phase 1 (Mistral) for PDFs, surface `mistral_report.json`. Say
   in the recap which backend was used and what its known failure mode
   is, so the user can judge the ingest that follows.
3. Phase 2 (marker) is **opt-in**. Offer it, do not assume it:
   *"Mistral converted N PDFs in Ms. Marker is the faithful backend for
   formulas and the only one that extracts figures, but costs about
   40 min per paper - launch it in the background on these N?"*. If the
   corpus is math-heavy or figures are wanted, recommend yes and run it
   detached rather than blocking the session.
4. Run Phase 3 (pymupdf4llm) only for PDFs both backends failed on, then
   Phase 4 (enrich) - surface each report.
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
