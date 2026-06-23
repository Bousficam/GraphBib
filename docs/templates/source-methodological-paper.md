# Methodological Paper Template

Use for sources where the study design is `methodological`. Detection
cues: paper introduces a new method / protocol / pipeline / instrument
(e.g. a new TMS protocol, a new BCI paradigm, a new DTI processing
pipeline, a new clinical scale), and the empirical content is mostly
**validation** of the method rather than answering a clinical question.

The output of ingesting a methodological paper feeds **directly** the
relevant `wiki/methods/<MethodName>.md` (for measurement instruments)
or `wiki/interventions/<intervention-slug>.md` (for therapy protocols)
page - beyond the source page itself.

## Frontmatter

```yaml
---
title: "Method Paper Title"
type: source
tags: [methodological]
date: YYYY-MM-DD
source_file: raw/<vault>/papers/<slug>.md
authors: [...]
year: 2024
journal: "..."
doi: "..."
source_pdf: "..."

# Method paper metadata
study_design: "methodological"
method_introduced: ""                # e.g. "MI-BCI with FES feedback"
method_category: ""                  # imaging | neurophysiology |
                                     # behavioral | subjective-scale |
                                     # stimulation | analysis | software
target_outcome: []                   # what the method measures or modifies
domain: []
methods: []                          # other methods used FOR validation
interventions: []
intervention_family: ""

# Quality signals
peer_reviewed: true
preprint: false
language: en
open_source: false                   # is the method publicly available?
data_availability: ""                # repository / DOI for validation data
code_availability: ""                # repository for source code
citation_apa: ""
bibtex_key: ""
cites: []
---
```

## Body

```markdown
## Summary
2-4 sentence summary: what method, what gap it fills, headline
validation result.

## Introduction

### Background (from cited literature)
Existing methods, their limitations, the gap this paper addresses.
Apply Indirect Citation Rule.

### Theoretical Basis
- Underlying principle (e.g. "Hebbian learning predicts that
  contingent feedback will reinforce …").
- Link to relevant [[concepts/...]] pages.

### Limitations of Existing Methods
- Method A - [[paper-x]] (p. ?) - limitation: …
- Method B - [[paper-y]] (p. ?) - limitation: …
- Gap this paper fills: 1-2 sentences.

### Aim of the New Method
Single sentence - what the method does that prior ones don't.

## Method Description

### Core Idea
1-2 paragraphs of prose explaining the method conceptually.

### Procedure / Algorithm
Step-by-step description, faithful to the paper. If the paper provides
pseudo-code or block diagrams, reproduce the structure.

### Hardware / Equipment
- Devices, sensors, stimulators.
- Specifications (sampling rate, electrode count, coil type, etc.).

### Software / Implementation
- Programming language, libraries, dependencies.
- Repository link if open source.
- License.

### Parameters
- All tunable parameters with their defaults and acceptable ranges.

### Configuration / Calibration
- Setup procedure, calibration steps.

## Validation

### Validation Design
- What was tested (accuracy, reliability, sensitivity, comparison vs
  gold standard, agreement with established method).
- Test datasets (synthetic / real, sample size, public availability).

### Comparison Methods
- Reference method(s) the new method is compared against.
- Each linked to its `[[methods/<RefMethod>]]` page if applicable.

### Performance Metrics
- Each metric reported, verbatim with effect size and statistical
  test (p. ?).

### Results
- Primary validation finding.
- Sub-tests (different parameter ranges, populations, conditions).
- Where the method outperforms reference.
- Where it doesn't (failure modes).

## Discussion

### Strengths of the Method
- As acknowledged by authors.

### Limitations of the Method
- Authors' acknowledged limitations.
- Failure modes encountered.

### Use Cases
- Recommended applications.
- Patient profiles / data conditions where the method shines.
- Patient profiles / data conditions to avoid.

### Comparison with Prior Methods
- vs Method A: differs / aligns / improves on …
- vs Method B: …

### Future Method Refinements
- Open questions about the method itself → routed to
  `wiki/questions/<slug>.md`.

## Reproducibility

### Code Availability
- Repository, version, license, dependencies.
- Containerization (Docker / Singularity)?

### Data Availability
- Validation datasets: public / on-request / private.

### Documentation Quality
- Tutorials, API docs, examples provided.

## Recommendations / Implications
- For users (clinicians / researchers): when and how to use this method.
- Routed to `wiki/recommendations/<topic>.md` if a recommendation page
  exists for the method's context.

## Reporting Standard Alignment
- For new clinical scales: COSMIN reporting checklist.
- For new neuroimaging pipelines: BIDS compliance, COBIDAS guidelines.
- For new clinical trial methodology: SPIRIT.
- For software / algorithms: typically no formal standard; check FAIR
  principles (Findable, Accessible, Interoperable, Reusable).

## Verbatim Quotes
Minimum 3 quotes from distinct sections.

## Cites (in-wiki + snowball candidates)
Methodological papers often cite a small number of foundational works
densely. These are high-priority snowball candidates.

## Cited By
*(Auto-populated.)*

## Connections
- [[methods/<MethodName>]] - the method introduced. **Updated heavily**:
  this paper is THE primary source for the method page; populate
  Definition, When to Use, Best Practices, Common Pitfalls verbatim
  from this paper.
- [[interventions/<slug>]] - if the method is a therapy.
- [[ConceptName]] - concepts the method operationalizes.

## Contradictions / Agreements
- Improves on [[OtherMethod-paper]] on …
- Aligns with [[OtherMethod-paper]] on …

## Extraction Checklist
- [ ] **Existing methods limitations** documented (≥ 2 prior methods
      cited as comparators).
- [ ] **Theoretical basis** linked to concept pages.
- [ ] **Procedure / algorithm** captured at sufficient detail to
      reproduce (or noted as proprietary).
- [ ] **Hardware / software** specifications listed.
- [ ] **All tunable parameters** listed with defaults and ranges.
- [ ] **Validation design** captured.
- [ ] **Comparison method(s)** identified and linked.
- [ ] **All performance metrics** quoted verbatim.
- [ ] **Failure modes** acknowledged by authors are listed.
- [ ] **Code availability** documented.
- [ ] **Data availability** documented.
- [ ] **`wiki/methods/<MethodName>.md` populated** with this paper as
      the primary source (Definition, When to Use, Best Practices,
      Common Pitfalls, Variants).
- [ ] **Open questions** about the method routed to
      `wiki/questions/`.
- [ ] **Concept pages** updated where the method operationalizes a
      concept.

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
