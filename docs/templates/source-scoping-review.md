# Scoping Review Template

Use for sources where the study design is `scoping-review`. Detection
cues: "scoping review", "PRISMA-ScR", "we mapped the literature",
"identify gaps", "clarify concepts", explicitly NO pooling of effects.

A scoping review **maps** the literature on a topic - it identifies
the volume, scope, range of evidence, and gaps without pooling
effects or evaluating quality at a study level. The output is often a
typology, a gap analysis, or a concept map.

This template is structured around the JBI / Arksey & O'Malley
framework, with PRISMA-ScR reporting alignment.

## Frontmatter

```yaml
---
title: "Scoping Review Title"
type: source
tags: [scoping-review]
date: YYYY-MM-DD
source_file: raw/<vault>/papers/<slug>.md
authors: [...]
year: 2024
journal: "..."
doi: "..."
source_pdf: "..."

# Review metadata
study_design: "scoping-review"
review_protocol: ""                  # PROSPERO / OSF / Figshare ID
prisma_scr_compliant: true
n_studies_included: 0
n_works_cited:                       # rough count from References (often
                                     # larger than n_studies_included)
date_range: "1990-2023"
domain: []
methods: []
interventions: []
intervention_family: ""

# Quality signals
peer_reviewed: true
preprint: false
language: en
citation_apa: ""
bibtex_key: ""
cites: []
---
```

## Body

```markdown
## Summary
2-4 sentence neutral summary: scope of the map, key categories
identified, headline gap(s).

## Introduction

### Background (from cited literature)
Exhaustive - see `docs/rules/citation.md`. Aim 10-25 bullets for a
substantive scoping review. Each bullet cites the original Y per the
Indirect Citation Rule.

### Rationale
Why a scoping review is the right method here (concept emerging,
literature too heterogeneous for SR, mapping needed for funder /
practitioner / researcher).

### Research Question (broad)
Scoping reviews ask broader questions than SRs:
- "What is known about …?"
- "How is concept X operationalized across studies?"
- "What types of evidence exist on intervention Y?"
- "What gaps exist in the literature on Z?"

Use a **PCC framework** (Population, Concept, Context) rather than PICO.

## Methods

### Protocol Registration
- PROSPERO ID / OSF link / "not registered".

### Search Strategy
- **Databases**: PubMed, Embase, CINAHL, PsycINFO, Web of Science,
  Cochrane CENTRAL, grey literature (OpenGrey, Google Scholar
  first 100), conference proceedings.
- **Date range**: from-to.
- **Search terms**: full block if reproducible.
- **Hand-searching**: reference lists, citation chasing.
- **Date last searched**: YYYY-MM-DD.

### Eligibility Criteria
- **Inclusion** (PCC framework):
  - Population
  - Concept (the focal idea being mapped)
  - Context (clinical / research / geographic / methodological)
- **Exclusion**:
  - Study designs excluded (often none - scoping reviews are
    inclusive).
  - Languages, time period, etc.

### Source Selection
- Screening process (titles/abstracts, full texts).
- Number of reviewers, conflict resolution.
- Software used (Covidence, Rayyan).

### Data Charting (Charting the Data)
Scoping reviews don't "extract" - they **chart**. The charting form
typically captures:
- Study characteristics (year, country, design).
- Concept operationalization.
- Population characteristics.
- Outcomes reported.
- Theoretical framework, if any.

Reproduce the charting categories used.

### Synthesis Approach
- Tabular summary by category (most common).
- Concept maps / typology.
- Narrative synthesis grouped by theme.
- Quantitative descriptive (counts by category).

**No risk-of-bias assessment**: scoping reviews do not appraise study
quality. Note this explicitly.

**No effect pooling**: scoping reviews do not run meta-analyses.

## Results

### PRISMA-ScR Flow
- Records identified.
- Duplicates removed.
- Screened.
- Assessed for eligibility.
- Included sources of evidence.

### Characteristics of Sources of Evidence
- Total N sources.
- Distribution by year.
- Distribution by country / region.
- Distribution by study design (descriptive / RCT / qualitative / …).
- Distribution by population (subacute / chronic / specific subgroup).

### Mapping by Theme / Category
For each major category identified by the review, summarize:
- N sources in the category.
- Key features (methods, populations, outcomes).
- Notable sub-themes.

### Concept Maps / Typologies
If the review proposes a typology or concept map, reproduce its
structure:
- Category A: definition, examples ([[paper-x]], [[paper-y]]).
- Category B: definition, examples.
- Relationships between categories.

### Identified Gaps
The headline output of a scoping review. List **each** identified
gap explicitly:
- Gap 1: e.g. "no studies on subacute stroke with MI-BCI" (this
  review p. ?).
- Gap 2: e.g. "no comparative studies of MI-BCI vs AO-BCI" (p. ?).
- …

Each gap → routed to `wiki/questions/<slug>.md`.

## Discussion

### Summary of Mapping
Authors' framing of what the literature covers and where it doesn't.

### Comparison with Prior Reviews
Apply the Indirect Citation Rule.

### Implications
- For research: gaps to fill, registries needed.
- For practice: extent of evidence base.
- For methodology: standardization opportunities.

### Limitations of the Review
- Search limitations.
- Charting subjectivity.
- No quality appraisal (by design).
- Coverage of grey literature.

## Recommendations / Implications
Routed to `wiki/recommendations/<topic>.md`. Scoping reviews often
recommend specific future SR/MA topics, registries, methodological
work - capture each.

## Reporting Standard Alignment
- **Standard**: PRISMA-ScR (PRISMA extension for Scoping Reviews).
- **Deviations / missing items** with page references.
- The 22 PRISMA-ScR items: title, abstract, rationale, objectives,
  eligibility, information sources, search, selection, data charting,
  data items, critical appraisal (NA), synthesis, results, etc.

## Verbatim Quotes
Minimum 3 quotes from distinct sections.

## Cites (in-wiki + snowball candidates)
Like SRs, scoping reviews have large `cites:` lists. Each gap
identified is a high-priority snowball direction.

## Cited By
*(Auto-populated.)*

## Connections
- [[ConceptName]] - central concept being mapped (often gives the
  review its raison d'être).
- [[methods/...]] / [[interventions/...]] - methods / treatments
  charted.

## Contradictions / Agreements
- Contradicts [[OtherReview]] on …
- Aligns with [[OtherReview]] on …

## Extraction Checklist
- [ ] **PCC framework** documented (Population, Concept, Context).
- [ ] **Protocol registration** (PROSPERO / OSF) documented or noted.
- [ ] **Full search strategy** captured.
- [ ] **Eligibility criteria** (inclusion + exclusion) documented.
- [ ] **Charting categories** documented.
- [ ] **PRISMA-ScR flow** numbers captured.
- [ ] **Distribution descriptions** (year, country, design, population)
      captured.
- [ ] **Themes / categories / typology** identified and listed.
- [ ] **Concept map / typology** reproduced if present.
- [ ] **Each identified gap** captured and routed to
      `wiki/questions/<slug>.md`.
- [ ] **No quality appraisal** noted explicitly (it's a scoping review
      design feature, not an omission).
- [ ] **PRISMA-ScR compliance** assessed, deviations noted.
- [ ] **High-frequency cited works** flagged as snowball priorities.
- [ ] **Recommendations** routed.
- [ ] **Concept / method / intervention pages** updated.

## How to Cite
**APA**: <citation_apa>

**BibTeX**:
```bibtex
@article{<bibtex_key>,
  author  = {...},
  title   = {...},
  journal = {...},
  year    = {...},
  doi     = {...}
}
```
```
