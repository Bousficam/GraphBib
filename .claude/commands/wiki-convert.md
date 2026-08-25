---
description: Run the PDF → Markdown conversion pipeline (Mistral first → marker/fallback only on failures → enrich → curate)
argument-hint: "<SRC> [DST]"
---

Run the PDF → Markdown conversion pipeline on the given source directory.

Arguments: $ARGUMENTS

- The first argument is `SRC` - an absolute path to a directory containing PDFs (recurses into subdirectories).
- The second argument, if provided, is `DST` - the output directory. If omitted, default to `raw/<vault>/papers/` relative to the repo root.

Read **`docs/workflows/conversion.md`** before starting; it is the spec,
this file is the sequence.

# Backend

**Mistral first, always**, unless `$WIKI_CONVERT_BACKEND` says `ask`
(the session-start hook asks the user once and persists the answer).
Mistral is ~5 s per paper against ~40 min for marker, so a
marker-first run means the user waits hours before ingestion can start.

**A missing API key does not change the backend.** `pdf2md_mistral.py`
exits with **code 3** when it finds no key in the environment, in `.env`
or in the macOS keychain. That code means *ask the user for a key*, not
*this PDF cannot be converted*:

1. Ask the user for a Mistral key (free experimental at `console.mistral.ai`).
2. Offer to append it to the gitignored `.env` as `MISTRAL_API_KEY=...`
   so the next session finds it. Never commit it, never echo it back.
3. Re-run Phase 1.

Falling back to marker or pymupdf4llm on a missing key is a defect: it
converts the whole corpus with the slow backend and nobody decided it.

# Phases

1. **Phase 1 - Mistral OCR (default)**
   ```
   python pdf2md/pdf2md_mistral.py "<SRC>" "<DST>"
   ```
   Read `<DST>/mistral_report.json` and show its summary (ok /
   skipped / errors / missing). On exit code 3, apply the key procedure
   above and re-run - do NOT advance to Phase 2.

2. **Phase 2 - marker, on the PDFs Mistral failed on, or on request**
   ```
   python pdf2md/pdf2md_marker.py "<SRC>" "<DST>"
   ```
   Reached for two reasons only: the entries Mistral errored on, or a
   deliberate high-fidelity pass (math-heavy corpus, or figures wanted -
   marker names images `_page_N_Figure_M`, which carries the page).
   Slow: offer it, do not assume it, and launch it detached rather than
   blocking the session. If marker is not installed, say
   `pip install marker-pdf`.

3. **Phase 3 - pymupdf4llm fallback**
   ```
   python pdf2md/pdf2md_fallback.py "<SRC>" "<DST>"
   ```
   Only for PDFs both backends failed on. Show the summary from
   `<DST>/fallback_report.json`. If pymupdf4llm is not installed, say
   `pip install pymupdf4llm`.

4. **Phase 4 - Enrich frontmatter (Crossref metadata)**
   ```
   python pdf2md/enrich_frontmatter.py "<DST>"
   ```
   Show the summary from `<DST>/enrich_report.json` (crossref_ok /
   doi_only / no_doi / errors). Warn that this step can mis-tag a paper
   from a cited reference's DOI - `tools/verify_doi.py` catches it at
   ingest step 20.

5. **Phase 5 - Validate + curate citations** (network-heavy, optional)

   **Before launching, ask the user**: *"Phase 5 calls Crossref for every
   reference (~13 min on first run, ~5 min after, thanks to the cache).
   Proceed?"*

   ```
   python tools/parse_references.py --curate --all "<DST>"
   ```
   This is snowball work, not conversion work - it is fine to skip it
   here and run `/wiki-snowball --all` later.

# Recap

After the phases, print:
- PDFs converted, by backend (Mistral / marker / pymupdf4llm)
- Which backend produced what, and its known failure mode: Mistral
  corrupts superscripts and subscripts (`2^36` seen as `2^90`), marker
  shreds tables with vertically-set headers. The user needs this to
  judge the ingest that follows.
- Files with bibliographic metadata (Crossref hits)
- Sources with an extracted `<slug>_images/` directory
- Next step: *"Ready to ingest? Try `ingest <DST>/<file>.md`"*

If a phase fails, stop and show the error before continuing - except
exit code 3 on Phase 1, which is a key request, not a failure.
