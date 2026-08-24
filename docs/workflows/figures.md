# Figures Workflow

How an image extracted from a PDF becomes a figure on a wiki page.
Referenced by step 18 of `docs/workflows/ingest.md`, by the
`source-illustrator` sub-agent, and by `/wiki-illustrate`.

## Where images come from

Extraction happens at **conversion**, never at ingestion. Both backends
write a `<slug>_images/` directory beside the converted markdown, with
different naming conventions - both exist in the corpus:

| Backend | File name | Page in the name |
|---|---|---|
| marker | `_page_3_Figure_2.jpeg` | yes, 0-based page index |
| Mistral (default) | `img-7.jpeg` | no |

`pdf2md_mistral.py` requests images by default (`--no-images` to skip,
`--images-only` to re-OCR the images of an already-ingested source
without touching the markdown the wiki was built from).

So a page reference recovered from the file name only works for marker
output, which is the minority. Never infer a page number any other way -
see *Page references* below.

## The tool does the pairing

```bash
python tools/figure_pairs.py --source <slug>              # inspect
python tools/figure_pairs.py --source <slug> --markdown   # ready to paste
python tools/figure_pairs.py --source <slug> --json       # machine-readable
```

It resolves what cannot be guessed from file names:

- **caption per image**, reusing `build_figure_index.captions_for`. An
  OCR emits one image per panel, so a multi-panel figure is a *run* of
  image references followed by a single caption; the run is detected
  first and the caption attributed to every panel (`Figure 6 (panel 2)`).
- **page**, from the converted markdown's own page anchors, else from
  the marker file name corrected by the Crossref page range, else
  unknown.
- **relative path** from the wiki source page down to the image, which
  depends on how deep the page sits under `wiki/<vault>/sources/`.
- **classification**: `figure`, `table` (a screenshot whose caption
  starts with `Table`), `duplicate` (same bytes), `orphan` (file on disk
  never referenced in the markdown), `noise` (page furniture - a
  caption-less image on the title page, or one whose byte size repeats
  across the document, or a scan the OCR shredded into hundreds of
  fragments).

Only `figure` items reach the markdown; `--include-noise` overrides that
when a genuine uncaptioned figure was misfiled.

Exit code 1 means there is nothing to illustrate, so a caller can branch
without parsing the output.

## Page references - never invent one

A marker file name gives the **PDF** page, not the printed one: an
article that runs pages 111-118 of a journal has its Figure 1 on PDF
page 4 and on printed page 114. The tool closes that gap with Crossref -
it reads the article's page range from the DOI already on the page and
adds the offset, refusing when the range does not cover the pages the
images claim. So a marker source with a valid DOI gets a real `(p. N)`;
without one it degrades to `(PDF p. N - confirm the printed page)`.

`(p. N)` on a wiki page means the **printed** page. The tool prints:

- `(p. N)` when a printed page was established, either from the
  article's own page anchors or from the Crossref range plus the PDF
  page - trustworthy;
- `(PDF p. N - confirm the printed page)` when the marker file name gave
  a page but no range could be resolved (no DOI, article-number journal,
  Crossref offline). The PDF page equals the printed page only when the
  article starts at page 1, which is false for supplements (`p. S80`)
  and offprints. Confirm against the article, then rewrite it;
- `(p. ?)` when neither exists. This is allowed by the Citation Rule and
  is the correct output - a later pass can resolve it. Writing a
  plausible number instead is a fabrication.

## Writing the section

`## Figures` sits after `## Results` (or `## Findings` for reviews) and
before `## Cites`, as declared in the source templates.

```markdown
## Figures

### Figure 2 - Time-course of mu power over C3 (p. 7)
![Figure 2](../../../../raw/<vault>/papers/<slug>_images/img-4.jpeg)
*Time-course of mu-band power (8-13 Hz) over C3 during the imagery task.
Shaded area = 95 % CI across N = 24 participants.*
```

- The caption is **verbatim** from the converted markdown, never
  paraphrased. If none was recovered, write
  `*(caption not recovered in the conversion)*` rather than inventing
  one.
- No citation on the figure: the page IS the source, provenance is
  implicit. On a concept page it is the opposite - see below.
- Check the link resolves (`ls` the path) before finishing.

## Who runs it

| Context | Who | What |
|---|---|---|
| During an ingest | the **ingester itself**, step 18 | writes `## Figures` on the source page it just wrote |
| Back-fill on an old source | `source-illustrator`, launched by the parent | same, on a page that has no `## Figures` |
| Illustrating a concept | `concept-illustrator` via `/wiki-illustrate` | picks from the cited sources' `## Figures` and inserts with a full citation |
| Corpus-wide bank | `tools/build_figure_index.py` | `figures.json` + `wiki/<vault>/figures-index.md` |
| Sources ingested before this workflow | `tools/backfill_figures.py` | `--mode new` adds a missing section, `--mode pages` repairs wrong page references |

**The ingester does this itself and does not delegate.** A sub-agent's
`tools:` allowlist does not include `Agent`, so an
`Agent(subagent_type=source-illustrator, ...)` call from inside the
ingester cannot run - it fails silently and the ingest reports success
with no figures. The ingester has the same tools `source-illustrator`
has (Read / Write / Edit / Bash / Grep / Glob), so it runs
`figure_pairs.py` and writes the section itself. `source-illustrator`
stays the entry point for back-fill, where the caller IS the parent.
