# Systematic Review / Meta-Analysis Template

Use for sources where the study design is `systematic-review` or
`meta-analysis`. Detection cues: "systematic review", "PRISMA", "Cochrane
review", "we searched databases", "study selection", "risk of bias
assessment", "pooled effect size", "I² heterogeneity".

This template extends `source-academic-paper.md` with PRISMA-aware
sections and stricter expectations on review-specific content (search
strategy, risk of bias, pooled effects). The Indirect Citation Rule
(`docs/rules/citation.md`) and Depth & Completeness Rules
(`docs/rules/depth-completeness.md`) apply throughout - every cited
study is a primary source whose claim must be attributed to that study,
not to the review.

## Frontmatter

```yaml
---
title: "Review Title"
type: source
tags: [systematic-review]   # or [meta-analysis] if pooling effects
date: YYYY-MM-DD
source_file: raw/<vault>/papers/<slug>.md
authors: [...]
year: 2024
journal: "..."
doi: "..."
source_pdf: "..."

# Review metadata
study_design: "systematic-review"   # or "meta-analysis"
review_protocol: ""                  # PROSPERO / OSF registration ID
prisma_compliant: true
n_studies_included: 0
n_participants_total:
date_range: "1990-2023"              # span of included studies
domain: []
methods: []                          # measurement methods reviewed
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
2-4 sentence neutral summary including the review's question, methods,
and headline finding (with effect size if a meta-analysis).

## Introduction

### Background (from cited literature)
Exhaustive - see `docs/rules/citation.md` (Knowledge construction from
introductions). Reviews typically have a denser intro than empirical
papers (20+ bullets common). Each bullet cites the original Y per the
Indirect Citation Rule.

### Rationale
Why this review is needed (gap, divergent findings, new evidence since
last review).

### Research Question (PICO/PECO)
- **P** Population
- **I** Intervention (or Exposure for PECO)
- **C** Comparator
- **O** Outcome
- **S** Study designs eligible

## Methods

### Protocol Registration
- PROSPERO ID / OSF link / "not registered".

### Search Strategy
- **Databases**: PubMed, Embase, Cochrane CENTRAL, Web of Science, etc.
- **Date range**: from-to.
- **Search terms / MeSH headings**: full block if reproducible.
- **Filters**: language, study type.
- **Date last searched**: YYYY-MM-DD.
- **Hand-searching**: reference lists, conference proceedings.

### Eligibility Criteria
- **Inclusion** (study-level):
  - Population
  - Intervention
  - Comparator
  - Outcome
  - Study design
  - Other (e.g. peer-reviewed, full-text available)
- **Exclusion**:
  - Reasons (e.g. animal studies, non-English, abstract only, …)

### Study Selection Process
- Number of reviewers.
- Title/abstract screening method.
- Full-text review method.
- Conflict resolution procedure.
- Software used (Covidence, Rayyan, …).

### Data Extraction
- Independent extractors? Single? Duplicate?
- Items extracted (study characteristics, outcomes, RoB).
- Disagreement resolution.

### Risk of Bias Assessment
- Tool used: Cochrane RoB 1 / RoB 2 / ROBINS-I / Newcastle-Ottawa /
  GRADE / AMSTAR-2 / etc.
- Domains assessed.
- Reviewer count / consensus.

### Data Synthesis
- **Qualitative synthesis**: narrative grouping by ...
- **Quantitative synthesis (meta-analysis)** - only if pooling:
  - Effect measure (RR, OR, SMD, MD, Hedges' g).
  - Pooling model (fixed effect / random effects, DerSimonian-Laird,
    REML, …).
  - Software (RevMan, R metafor, Stata).

### Heterogeneity Assessment (meta-analysis only)
- I², τ², Q-test.
- Subgroup analyses planned.
- Meta-regression covariates.

### Sensitivity & Bias Analyses
- Sensitivity (leave-one-out, RoB-based).
- Publication bias: funnel plot, Egger test, trim-and-fill.

## Results

### PRISMA Flow
- Records identified (per database).
- Duplicates removed.
- Records screened.
- Records excluded with reasons.
- Full-text articles assessed for eligibility.
- Studies included in qualitative synthesis (N).
- Studies included in quantitative synthesis (N) - meta-analysis only.

### Characteristics of Included Studies
Either prose summary OR a representative table:

| Study | Design | N | Population | Intervention | Comparator | Outcome | RoB |
|---|---|---|---|---|---|---|---|
| [[paper-a]] | RCT | 32 | … | … | … | ΔFM | low |
| [[paper-b]] | … | … | … | … | … | … | … |

Each row links to the source page if the included study is in the wiki
(otherwise raw author/year + DOI; add to `cites:`).

### Risk of Bias Summary
- Per-study RoB judgments (table or prose).
- Overall: how many studies low / some-concerns / high RoB per domain.

### Primary Outcome - Pooled Effect (meta-analysis only)
- Effect estimate, 95 % CI, p-value.
- Number of studies, total N.
- I² heterogeneity.
- Verbatim with page reference.

### Secondary Outcomes - Pooled Effects
- Each one: effect estimate, CI, n_studies, I².

### Subgroup / Sensitivity Analyses
- Each pre-specified subgroup result.
- Each sensitivity check with finding.

### Publication Bias (meta-analysis only)
- Funnel plot interpretation.
- Egger test p-value.
- Adjusted estimate if trim-and-fill applied.

### Certainty of Evidence (GRADE, if applied)
- Per-outcome GRADE rating: high / moderate / low / very low.
- Domains downgraded.

## Discussion

### Summary of Evidence
- 2-3 sentences quoting authors' framing of what the review found.

### Comparison with Prior Reviews
Apply the Indirect Citation Rule:
- Aligns with [[review-a]] (p. ?) on … - reported via this review's
  discussion (p. ?).
- Differs from [[review-b]] (p. ?) on … - reported via this review's
  discussion (p. ?).

### Interpretation
Authors' interpretation in terms of [[ConceptName]] / [[FrameworkName]].

### Strengths of the Review
- As acknowledged by the authors.

### Limitations of the Review
- Search limitations (databases missed, language).
- Risk of bias of included studies → quality of pooled estimates.
- Heterogeneity unexplained.
- Other (publication bias, small-study effects).

### Implications for Practice and Research
- For clinicians: actionable conclusions.
- For researchers: future review questions, registries needed.

### Future Research Directions
- Open questions raised → routed to `wiki/questions/<slug>.md`.

## Recommendations / Implications
Routed to `wiki/recommendations/<topic>.md`. Often a SR/MA produces 1-5
direct recommendations.

## Reporting Standard Alignment
- **Standard**: PRISMA 2020 (or older PRISMA versions, MOOSE for
  observational, PRISMA-NMA for network meta-analysis).
- **Deviations / missing items** with page references.

## Verbatim Quotes
Minimum 3 quotes covering Methods, Results, Discussion (one per section).

## Cites (in-wiki + snowball candidates)
**Left empty by the ingest**; filled by `/wiki-snowball <slug>`. For SRs, the
`cites:` list is large (every included study is a
candidate). Each included study NOT in the wiki is a high-priority
snowball candidate.

## Cited By
*(Auto-populated.)*

## Connections
- [[ConceptName]] - central concept.
- [[methods/MethodName]] - methods aggregated.
- [[interventions/<slug>]] - therapy family.

## Contradictions / Agreements
- Contradicts [[OtherReview]] on …
- Aligns with [[OtherReview]] on …

## Extraction Checklist
- [ ] **Background**: ≥ 5 cited claims with `reported via` provenance.
- [ ] **PICO / PECO** documented.
- [ ] **Protocol registration** (PROSPERO ID) documented or noted as missing.
- [ ] **Full search strategy** captured (databases + dates + terms).
- [ ] **Eligibility criteria**: inclusion AND exclusion both documented.
- [ ] **Selection process** documented (reviewer count, conflict resolution).
- [ ] **Risk of bias tool** identified and per-domain summary documented.
- [ ] **PRISMA flow** numbers captured (identified / screened /
      assessed / included).
- [ ] **All outcomes** (primary + secondary + safety) listed with pooled
      effect, CI, n_studies, I² (meta-analysis) or narrative synthesis
      (qualitative).
- [ ] **Subgroup / sensitivity analyses** each listed with finding.
- [ ] **Publication bias** assessed (or noted as not assessed).
- [ ] **GRADE certainty** per outcome (or noted as not applied).
- [ ] **Limitations of the review** listed.
- [ ] **PRISMA compliance** verified, deviations noted.
- [ ] **Each included study** added to `cites:`; high-impact ones flagged
      as snowball candidates.
- [ ] **Recommendations** routed to `wiki/recommendations/<topic>.md`.
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
