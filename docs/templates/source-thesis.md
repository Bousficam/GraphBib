# Thesis Template

Used by default for sources in `raw/<vault>/theses/*`. Theses have richer
metadata, multiple chapters, and serve as citation snowball sources.

**For long theses (≥ 100 pages or > 8 chapters)**, use the **Long Document
Ingestion** workflow defined in `CLAUDE.md`: split with
`pdf2md/split_thesis.py` first, then ingest the parent thesis MD as a
lightweight parent page (this template) and each chapter as its own
source page using `docs/templates/source-academic-paper.md`. The parent's
`## Methods`, `## Results`, `## Background` are deliberately empty on
the parent and live on the chapter pages instead.

For short theses (< 60 pages), or when chapters can't be cleanly
detected, ingest the thesis as a single source - fill the full template
below.

## Frontmatter

```yaml
---
title: "Thesis Title"
type: source
tags: [thesis, paper]
date: YYYY-MM-DD            # ingest date
source_file: raw/<vault>/theses/<slug>.md
authors: ["First Last"]
year: 2024
degree: "PhD"               # PhD | MSc | MD | HDR | habilitation
university: "University Name"
department: ""
advisors: ["First Last"]
defense_date: YYYY-MM-DD
journal: ""                 # empty for theses
doi: ""                     # if archived (HAL, ProQuest, theses.fr)
source_pdf: "/abs/path/to/original.pdf"

# Study metadata (often multi-method across chapters)
study_design: "thesis"
sample_size:                # total N across studies, or empty
population: ""
domain: []
methods: []                 # union of methods across chapters

# Quality signals
peer_reviewed: false        # committee-reviewed, not peer-reviewed
preprint: false
language: en
chapters: 0                 # integer

# Citation
citation_apa: ""
bibtex_key: ""

# Citation network (auto-populated)
cites: []                   # DOIs cited across all chapters
---
```

## Body

```markdown
## Abstract
Verbatim abstract from the thesis frontmatter.

## Research Questions
- RQ1: ... (p. ?)
- RQ2: ... (p. ?)

## Hypotheses
- H1: ... (p. ?)

## Theoretical Framework
- Anchored in [[ConceptName]] - how the thesis builds on it (p. ?)
- Contributes to [[FrameworkName]]

## Chapters Summary

### Chapter X - <title> (p. NN-NN)
- **Design**: ...
- **Methods**: → [[methods/...]]
- **Key findings**: ... (p. ?)

## Cross-Chapter Synthesis
The thesis's overall argument, integrating chapters (p. ?).

## Recommendations / Implications
- For clinical practice: ... (p. ?)
- For future research: ... (p. ?)

## Limitations
- ... (p. ?)

## Notable References (citation snowball)
Filled by `/wiki-snowball <slug>`, not by the ingest.
High-value references this thesis builds on. Format:
- *Author, A. (Year).* Title. *Journal*, V(I), pp. - relevance
- ☐ not yet in wiki
- ✓ [[already-ingested-slug]]

After ingest, surface the ☐ items and ask the user about snowball
ingestion.

## Figures

Written at step 18 of the ingest by `tools/figure_pairs.py --markdown`,
which pairs each extracted image with its caption and recovers the page
across both converter conventions. Left out entirely when the source
ships no `<slug>_images/` directory. Full rule:
`docs/workflows/figures.md`.

### Figure N - <first clause of the caption> (p. N)
![Figure N](<relative path emitted by the tool, never counted by hand>)
*Verbatim caption, copied from the converted markdown, never
paraphrased. `*(caption not recovered in the conversion)*` when the OCR
lost it.*

Page reference: `(p. N)` only when it was recovered from the article
itself; `(PDF p. N - confirm the printed page)` when it came from a
marker file name; `(p. ?)` when neither. Never a plausible number.
No citation on a figure here - this page IS the source.

## Cites (in-wiki + snowball candidates)
**Left empty by the ingest** - the reference list is never read during
ingestion (`docs/workflows/ingest.md` step 1). Populated later by
`/wiki-snowball <slug>`, which reads the bibliography from the converted
article under `raw/`. Wikilinks for sources already in the wiki, raw DOIs
for the snowball candidates.

## Cited By
*(Auto-populated: theses/papers in the wiki whose `cites:` includes this
thesis's DOI.)*

## Verbatim Quotes
> "..." - p. N

## Connections
- [[AdvisorName]] - advisor
- [[ConceptName]] - central concept
- [[methods/MethodName]] - used technique

## Contradictions / Agreements
- ...

## How to Cite
**APA**: <citation_apa>

**BibTeX**:
```bibtex
@phdthesis{<bibtex_key>,
  author       = {...},
  title        = {...},
  school       = {...},
  year         = {...},
  type         = {PhD thesis},
  doi          = {...}
}
```
```
