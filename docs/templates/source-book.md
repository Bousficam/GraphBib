# Academic Book Template

Used by default for sources in `raw/books/*` — academic monographs,
edited volumes, handbooks, textbooks, scholarly conference
proceedings published as books.

**For long books (≥ 150 pages or any edited volume with distinct
per-chapter authors)**, use the **Long Document Ingestion** workflow
defined in `docs/workflows/long-document-ingestion.md`: split with
`pdf2md/split_thesis.py` first (works for any chaptered document),
ingest the parent book MD as a lightweight parent page (this template),
and each chapter as its own source page using
`docs/templates/source-academic-paper.md` with the extra fields
documented under "Chapter sub-sources" below. The parent's
`## Methods`, `## Results`, `## Background` are deliberately empty on
the parent and live on the chapter pages instead.

For short books or single-author monographs (< 150 pages, unified
narrative), ingest as a single source — fill the full template below.

The Indirect Citation Rule and the Depth & Completeness Rules apply
throughout — see `docs/rules/citation.md` and
`docs/rules/depth-completeness.md`.

## Frontmatter

```yaml
---
title: "Book Title"
subtitle: ""                 # optional, often informative for academic books
type: source
tags: [book]                 # add [edited-volume], [handbook], [textbook], [monograph] as appropriate
date: YYYY-MM-DD             # ingest date
source_file: raw/books/<slug>.md

# Authorship — mutually exclusive in usage
authors: ["First Last"]      # for authored monographs / textbooks
editors: []                  # for edited volumes / handbooks (leave authors: [] then)
year: 2024
edition: ""                  # e.g. "2nd", "3rd revised", empty if first edition

# Publication
publisher: "Publisher Name"
publisher_place: ""          # city — e.g. "Cambridge, MA" or "Berlin"
series: ""                   # e.g. "Springer Handbooks of Neuroscience"
series_editors: []
series_volume: ""            # if part of a numbered series

# Identifiers
isbn: ""                     # ISBN-13 preferred, ISBN-10 acceptable
doi: ""                      # increasingly common for scholarly books (e.g. Springer, Routledge)
oclc: ""                     # WorldCat OCLC number, optional
source_pdf: "/abs/path/to/original.pdf"

# Study metadata (often multi-method across chapters)
study_design: "book"         # or "edited-volume", "textbook", "handbook"
sample_size:                 # rarely applies, leave empty
population: ""               # e.g. "stroke survivors" if clinically focused
domain: []                   # union of domains across chapters
methods: []                  # union of methods discussed
interventions: []
intervention_family: ""

# Quality signals
peer_reviewed: false         # most academic books are publisher-reviewed,
                             # not peer-reviewed in the journal sense — set
                             # true only for series with explicit peer review
                             # (e.g. Cambridge University Press monograph series)
publisher_reviewed: true     # editorial / publisher review (default for academic books)
language: en
chapters: 0                  # integer
pages_total: 0               # integer

# Citation
citation_apa: ""
bibtex_key: ""

# Citation network (auto-populated)
cites: []                    # DOIs cited across all chapters
---
```

## Body

```markdown
## Abstract / Preface
Verbatim preface, foreword, or back-cover summary. For edited
volumes, the editors' introduction often serves this role.

## Scope and Audience
- **Aimed at**: ... (p. ?)
- **Prerequisite knowledge**: ... (p. ?)
- **Position in the field**: how this book situates itself relative
  to existing literature (p. ?)

## Theoretical Framework
- Anchored in [[ConceptName]] — how the book builds on it (p. ?)
- Contributes to [[FrameworkName]]
- For textbooks: the canonical model the book teaches (p. ?)

## Table of Contents

### Part I — <part title>

#### Chapter X — <title> (p. NN-NN)
- **Author(s)** (for edited volumes): First Last, First Last
- **Topic**: ...
- **Key concepts introduced**: → [[ConceptName]]
- **Key methods discussed**: → [[methods/...]]
- **Key findings / claims**: ... (p. ?)

*(Repeat for every chapter — exhaustive enumeration per the Depth
& Completeness Rule, not "Chapters 3–7 cover ...")*

## Cross-Chapter Synthesis
The book's overall argument, integrating chapters. For edited volumes,
the editorial through-line (p. ?).

## Canonical Definitions / Equations
Books often serve as the primary citable source for foundational
definitions. Capture verbatim:

> "Definition or equation verbatim" — p. N (Chapter X, §Y)

These become the citable definition for [[ConceptName]] pages.

## Recommendations / Implications
- For clinical practice: ... (p. ?)
- For future research: ... (p. ?)
- For pedagogy (if textbook): ... (p. ?)

## Limitations / Critiques
- Acknowledged by author(s): ... (p. ?)
- Known critiques in the literature (if applicable): ... — see
  [[critique-source-slug]]

## Notable References (citation snowball)
High-value references this book builds on. For edited volumes,
collect the most-cited references across chapters. Format:
- *Author, A. (Year).* Title. *Journal*, V(I), pp. — relevance
- ☐ not yet in wiki
- ✓ [[already-ingested-slug]]

After ingest, surface the ☐ items and ask the user about snowball
ingestion.

## Cites (in-wiki + snowball candidates)
Auto-populated by `tools/parse_references.py` from the book's
bibliography (or unionized across chapter bibliographies for edited
volumes). Wikilinks for sources already in the wiki, raw DOIs
otherwise.

## Cited By
*(Auto-populated: sources in the wiki whose `cites:` includes this
book's DOI or ISBN.)*

## Verbatim Quotes
> "..." — p. N (Chapter X)

## Connections
- [[EditorName]] — editor (for edited volumes)
- [[AuthorName]] — author (for monographs)
- [[ConceptName]] — central concept the book establishes
- [[methods/MethodName]] — method canonically described here
- [[series/SeriesName]] — sibling volumes in the series

## Contradictions / Agreements
- ...

## How to Cite

**APA** (authored monograph): <citation_apa>
> Last, F. M. (Year). *Book title: Subtitle* (Edition ed.). Publisher.

**APA** (edited volume): 
> Last, F. M., & Last, F. M. (Eds.). (Year). *Book title* (Edition ed.). Publisher.

**APA** (chapter in edited volume): 
> Last, F. M. (Year). Chapter title. In F. M. Editor & F. M. Editor (Eds.), *Book title* (pp. NN–NN). Publisher.

**BibTeX** (authored monograph):
```bibtex
@book{<bibtex_key>,
  author    = {Last, First and Last, First},
  title     = {Book Title},
  edition   = {2},
  publisher = {Publisher},
  address   = {City},
  year      = {2024},
  isbn      = {978-...},
  doi       = {10.xxxx/...}
}
```

**BibTeX** (edited volume):
```bibtex
@book{<bibtex_key>,
  editor    = {Last, First and Last, First},
  title     = {Book Title},
  publisher = {Publisher},
  year      = {2024},
  isbn      = {978-...}
}
```

**BibTeX** (single chapter from edited volume — used on chapter sub-source pages):
```bibtex
@incollection{<bibtex_key>,
  author    = {Last, First},
  title     = {Chapter Title},
  editor    = {Last, First and Last, First},
  booktitle = {Book Title},
  publisher = {Publisher},
  year      = {2024},
  pages     = {NN--NN},
  isbn      = {978-...}
}
```
```

## Chapter sub-sources

When a book is split into per-chapter pages via the long-document
workflow, each chapter is ingested using
`docs/templates/source-academic-paper.md` with these **extra
frontmatter fields** to keep the chapter linked to its parent book:

```yaml
parent_book: "[[ParentBookSlug]]"   # wikilink to the parent book page
book_title: "Book Title"            # full book title (for citation_apa)
book_editors: ["First Last"]        # editors of the parent volume
book_publisher: "Publisher Name"
book_year: 2024
book_isbn: ""
chapter_number: 7
pages_in_book: "NN-NN"              # range string, e.g. "143-176"
bibtex_type: "incollection"         # overrides the default @article
```

The chapter's `citation_apa` and BibTeX entry should follow the
"chapter in edited volume" formats above. The chapter's `authors:`
remain the chapter authors — `book_editors` is separate metadata so
the citation generator can format both correctly.

## When to use this template vs. another

- **Single-author research monograph** → this template (whole book)
- **Edited handbook with distinct chapter authors** → this template
  for the parent + `source-academic-paper.md` for each chapter
- **Textbook used as canonical reference** → this template; ingest
  selectively only the chapters you actually cite
- **Conference proceedings published as a book** → this template for
  the parent + `source-academic-paper.md` for each paper
- **Practice guideline issued as a book** → consider
  `source-systematic-review.md` if the guideline is PRISMA-derived,
  otherwise this template with `tags: [book, guideline]`
- **Thesis (PhD / MSc)** → use `source-thesis.md` instead, even if
  the thesis was later published as a book
