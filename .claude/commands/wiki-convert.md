---
description: Run the PDF → Markdown conversion pipeline (marker → fallback → enrich → curate)
argument-hint: "<SRC> [DST]"
---

Run the PDF → Markdown conversion pipeline on the given source directory.

Arguments: $ARGUMENTS

- The first argument is `SRC` — an absolute path to a directory containing PDFs (recurses into subdirectories).
- The second argument, if provided, is `DST` — the output directory. If omitted, default to `raw/<vault>/papers/` relative to the repo root.

Follow the **Conversion Workflow** defined in CLAUDE.md exactly. The four phases:

1. **Phase 1 — Marker conversion**
   ```
   python pdf2md/pdf2md_marker.py "<SRC>" "<DST>"
   ```
   When done, read `<DST>/marker_report.json` and show its `summary` field (ok / suspicious / errors / skipped). If marker hasn't been installed, instruct the user to run `pip install marker-pdf`.

2. **Phase 2 — Fallback for failures**
   ```
   python pdf2md/pdf2md_fallback.py "<SRC>" "<DST>"
   ```
   Reads the marker report and reprocesses errors + suspicious entries with pymupdf4llm. Show the summary from `<DST>/fallback_report.json`. If pymupdf4llm isn't installed, instruct the user to run `pip install pymupdf4llm`.

3. **Phase 3 — Enrich frontmatter (Crossref metadata + raw cites:)**
   ```
   python pdf2md/enrich_frontmatter.py "<DST>"
   ```
   Show the summary from `<DST>/enrich_report.json` (crossref_ok / doi_only / no_doi / with_cites / errors).

4. **Phase 4 — Validate + curate citations** (network-heavy)

   **Before launching, ask the user**: *"Phase 4 calls Crossref for every reference (typically ~13 min on first run, ~5 min on subsequent runs thanks to the cache). Proceed?"*

   If approved:
   ```
   python tools/parse_references.py --curate --all "<DST>"
   ```
   Show the per-file progress as it runs and the final summary (valid / curated / unresolved).

After all four phases, print a concise recap:
- Number of PDFs converted (marker + fallback)
- Number of files with bibliographic metadata (Crossref hits)
- Number of files with `cites:` populated and total citation count
- Suggested next step: "Ready to ingest? Try `ingest <DST>/<file>.md`"

If any phase fails, stop the pipeline and show the error before continuing.
