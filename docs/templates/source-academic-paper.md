# Academic Paper Template

Used by default for sources in `raw/papers/*`. Also used by chapter
sub-sources (`raw/theses/<slug>/ch*.md`) per the Long Document Ingestion
workflow — chapters are journal-paper-sized units.

The body follows the **IMRAD** structure (Introduction · Methods · Results
· And Discussion). Each subsection captures a specific extractable item.
**Omit a subsection only when the paper does not provide that content** —
do not write "N/A". Empty subsections waste structure; missing
subsections record reality.

The Indirect Citation Rule and the Depth & Completeness Rules apply
throughout — see `docs/rules/citation.md` and
`docs/rules/depth-completeness.md`.

## Frontmatter

```yaml
---
title: "Paper Title"
type: source
tags: [paper]
date: YYYY-MM-DD            # ingest date
source_file: raw/papers/<slug>.md
authors: ["First Last", "First Last"]
year: 2024
journal: "Journal Name"
doi: "10.xxxx/xxxxx"
source_pdf: "/abs/path/to/original.pdf"

# Study metadata
study_design: ""            # RCT | cohort | cross-sectional | review |
                            # meta-analysis | case-series | case-report |
                            # simulation | computational | theoretical
sample_size:                # integer N (or empty)
population: ""              # e.g. "chronic stroke patients (>6 months post-onset)"
domain: []                  # e.g. [stroke, motor-rehab, MI-BCI]
methods: []                 # measurement instruments — e.g. [EEG, FuglMeyer, ARAT, MEP, DTI]
interventions: []           # treatments delivered — e.g. [MI-BCI, rTMS, mirror-therapy]
intervention_family: ""     # PRINCIPAL therapy family — BCI | TMS | tDCS | mirror | robot | mental-practice | physio | combined | none
intervention_subfamily: ""  # paradigm within the family — e.g. mi-bci | ao-bci | hybrid | rtms | itbs | ctbs (drives tier-2 folder)

# Quality signals
peer_reviewed: true
preprint: false
language: en
replication_of: ""          # DOI of the replicated paper, if applicable

# Citation (auto-generated, copyable)
citation_apa: ""
bibtex_key: ""              # e.g. cervera2020

# Citation network (auto-populated by tools/parse_references.py)
cites: []                   # DOIs cited by this paper
---
```

## Body

```markdown
## Summary
2-4 sentence neutral summary. **Every claim cites a page**.

---

## Introduction

### Background (from cited literature)
Claims this paper inherits from prior work. **This section must be
exhaustive** — see `docs/rules/citation.md` (Knowledge construction
from introductions). Aim 5–15 bullets for an empirical paper, 20+ for a
review or thesis introduction. Each bullet cites the **original** source
per the Indirect Citation Rule with explicit `reported via [[X]]`
provenance:
- Claim from prior work — [[paper-y]] (p. ?), reported via this paper (p. ?, intro).
- Framework adopted — [[paper-z]] (p. ?), reported via this paper (p. ?).
- If the original is not in the wiki: `this paper (p. ?, citing Y, 2018)` and add Y's DOI to `cites:`.

### Theoretical Framework
- Anchored in [[ConceptName]] / [[FrameworkName]].
- Reasoning chain leading to the present hypothesis.

### Gap Identified
1–2 sentences stating what the literature was missing prior to this paper.

### Research Question
Single sentence — the question the paper explicitly addresses.

### Hypotheses (if explicit)
- H1: ... (p. ?)
- H2: ... (p. ?)

## Methods

### Study Design
- `<study_design>`: RCT | cohort | cross-sectional | review | meta-analysis | …
- Trial registration ID (RCTs): NCT… or equivalent.
- Pre-registration / protocol publication if any.

### Participants
- N enrolled / randomized / analyzed / completed.
- Population profile: chronicity, severity (e.g. baseline FM range),
  lesion side and type, age, sex distribution.
- **Inclusion criteria** — bullet list.
- **Exclusion criteria** — bullet list.
- Recruitment setting (single-centre, multi-centre, clinic, registry).

### Intervention(s)
For each arm, document:
- What is delivered (e.g. MI-BCI with FES feedback) → [[interventions/...]].
- Dose: sessions count, duration per session, total hours.
- Delivery: who, where, supervision level.
- Co-interventions allowed / forbidden.

### Comparator
- Control / sham / standard care / waitlist. Describe the contrast.

### Outcome Measures
- **Primary**: <measure> → [[methods/<MethodName>]] (timepoint).
- **Secondary**: ...
- **Exploratory / mechanistic**: ...
- For neurophysiological outcomes (EEG, MEP, DTI), specify acquisition
  parameters as reported.

### Procedure / Timeline
- Schedule: baseline, intervention sessions, post-intervention, follow-up(s).

### Statistical Analysis
- Sample size justification / power calculation.
- Tests used (mixed models, ANOVA, regression…).
- Adjustment for multiple comparisons.
- Subgroup / mediator analyses pre-specified vs exploratory.
- Software (R, SPSS, MATLAB…) and version.

### Ethics
- IRB / ethics committee approval.
- Informed consent procedure.
- Funding source(s) and conflicts of interest declared.

### Data and Code Availability
- Pre-registration: link or registration ID (e.g. OSF, AsPredicted) — p. ?.
- Data: repository link / DOI / "available on request" / "not shared".
- Code / analysis scripts: repository link, version, license.
- Raw materials (stimuli, questionnaires): where deposited.

## Results

### Participant Flow
- Enrolled → screened → randomized → completed → analyzed.
- Dropouts with reasons.
- CONSORT-style numbers when available (RCTs).

### Baseline Characteristics
- Group equivalence at baseline; flag any imbalance the authors note.

### Primary Outcome
- Verbatim result with effect size (Cohen's d / g / η², or raw mean
  difference), 95 % CI, p-value (p. ?).
- Direction of effect.

### Secondary Outcomes
- Each one — verbatim with effect size and statistic (p. ?).

### Subgroup / Exploratory Analyses
- Each one — verbatim, with the warning that they're exploratory if so.

### Adverse Events / Safety
- Number of events per group, severity, attribution to the intervention.

### Compliance / Adherence
- Adherence rate; reasons for non-adherence.

### Tables and Figures
For each numbered table or figure cited in the body:
- **Table 1** (p. ?) — what it summarizes (e.g. "baseline demographics by group");
  flag any notable rows.
- **Figure 2** (p. ?) — what it depicts (e.g. "individual ΔFM trajectories
  over 12 weeks by intervention arm").
- Note any pattern visible only in the figure (outliers, dose-response
  curves, individual variability) that the prose narrative downplays.

Do not skip tables/figures. They often carry information not stated in
the body text — particularly secondary outcome details, sub-group
breakdowns, and individual-level variability.

## Discussion

### Summary of Findings (authors' framing)
- 2–3 sentences quoting the authors' own summary of what they found.

### Comparison with Prior Work
Authors situate their findings against the literature. Apply the
Indirect Citation Rule with `reported via this paper's discussion`:
- Aligns with [[paper-y]] (p. ?) on … — reported via this paper's
  discussion (p. ?).
- Differs from [[paper-z]] (p. ?) on … — reported via this paper's
  discussion (p. ?).

### Mechanism / Theoretical Implications
- Authors' interpretation in terms of [[ConceptName]] / [[FrameworkName]].

### Strengths
- As acknowledged by the authors (p. ?).

### Limitations
- **Every** limitation acknowledged by the authors (p. ?). Most honest
  papers list 4–6.

### Generalizability
- Authors' statements on external validity, applicability to other
  populations.

### Future Research Directions
- Open questions raised → routed to `wiki/questions/<slug>.md`.

## Recommendations / Implications
- Recommendation 1 (p. ?) — target: [clinician | researcher | policy] —
  routed to `wiki/recommendations/<topic>.md`.
- Implication for theory of [[ConceptName]] (p. ?).

## Reporting Standard Alignment
Identify which reporting checklist applies and flag deviations the agent
notices. Most empirical clinical / behavioural papers should align with one:

- **RCT** → CONSORT — verify: random sequence generation, allocation
  concealment, blinding, intention-to-treat analysis, CONSORT flow
  diagram present.
- **Observational (cohort, case-control, cross-sectional)** → STROBE.
- **Systematic review / meta-analysis** → PRISMA — verify: PRISMA flow
  diagram, search dates, included databases, risk-of-bias assessment.
- **Diagnostic accuracy** → STARD.
- **Quasi-experimental / non-randomized** → TREND.
- **Case report** → CARE.
- **Animal study** → ARRIVE.

Format:
- Standard: <CONSORT | STROBE | PRISMA | …>.
- Deviations / missing items: <list with page references>.
- Quality risk this introduces (e.g. unblinded outcome assessor on
  subjective measure → high risk of detection bias).

If the paper does not align with any standard or pre-dates the standard,
state so.

## Verbatim Quotes
Minimum 3 quotes from distinct sections (Introduction / Results / Discussion).
> "Quote here verbatim" — p. N (section)

## Cites (in-wiki + snowball candidates)
Auto-populated from the paper's References section by
`tools/parse_references.py`. Wikilinks for papers already in the wiki,
raw DOIs for snowball candidates.
- [[paper-y]] — referenced in Background.
- [[paper-z]] — framework citation in Discussion.
- 10.xxxx/yyy — *not yet in wiki* (snowball candidate).
- 10.xxxx/zzz — *not yet in wiki*.

## Cited By
*(Auto-populated by `tools/update_cited_by.py`: list of `[[paper-slug]]`
pages whose `cites:` frontmatter contains this paper's DOI.)*

## Connections
- [[AuthorName]] — author.
- [[ConceptName]] — central concept; how this paper uses it.
- [[methods/MethodName]] — operationalization used.
- [[interventions/<slug>]] — therapy family.

## Contradictions / Agreements
- Contradicts [[OtherPaper]] on: claim X (this p. ?, other p. ?).
- Confirms [[OtherPaper]] on: claim Y (this p. ?, other p. ?).

## Extraction Checklist
Filled by the agent at end of ingest as a self-audit. Each box must be
checked or annotated with the reason for omission. **Do not skip a box
just because the section was hard to find** — the absence of an item is
itself information (e.g., no power analysis = quality flag).

- [ ] **Background**: ≥ 5 cited claims with original references and `reported via` provenance.
- [ ] **Theoretical framework** identified and wikilinked.
- [ ] **Hypotheses** listed verbatim, or noted as not pre-stated.
- [ ] **Inclusion AND exclusion criteria** both documented.
- [ ] **Sample size justification / power analysis** documented or noted as missing.
- [ ] **All outcome measures** (primary + secondary + exploratory) listed,
      each linked to `[[methods/...]]`.
- [ ] **Each outcome has a result** with effect size + CI + p-value verbatim.
- [ ] **Tables and figures** all referenced with their content described.
- [ ] **Adverse events** documented or noted as not reported.
- [ ] **Compliance / adherence** documented.
- [ ] **All limitations** acknowledged by authors are listed.
- [ ] **Comparison with prior work** uses `reported via` provenance for cited claims.
- [ ] **Reporting standard alignment** assessed (CONSORT / STROBE / PRISMA / etc.).
- [ ] **Pre-registration / data availability** documented.
- [ ] **Trial registration ID** present (RCTs only).
- [ ] **≥ 3 verbatim quotes** from distinct IMRAD sections.
- [ ] **References parsed**: `cites:` populated; snowball candidates flagged.
- [ ] **Recommendations** routed to `wiki/recommendations/<topic>.md`.
- [ ] **Open questions** routed to `wiki/questions/<slug>.md`.
- [ ] **Concept / method / intervention pages** updated with per-source description (not bare wikilinks).

If any box remains unchecked **without a noted reason**, the ingest is
incomplete — re-read the source MD and fill the gap before declaring
the source page final.

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
