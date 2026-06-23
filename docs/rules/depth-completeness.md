# Depth & Completeness Rules (full spec)

CLAUDE.md carries the short summary; this file is the authoritative
reference for the agent during ingest.

A source page is the agent's **only chance** to mine that paper for the
wiki. Subsequent passes won't re-read the PDF. Therefore:

## Extraction must be exhaustive, not representative

The default failure mode is the agent extracting the 2-3 most salient
items from each section and skipping the rest. This produces a
superficial wiki. Counter it.

For empirical papers (RCTs, cohort, cross-sectional), follow the
**IMRAD** structure of `docs/templates/source-academic-paper.md` and
complete each subsection that the source paper provides. Detailed
expectations:

**Introduction (### Background / ### Theoretical Framework / ### Gap / ### Research Question / ### Hypotheses)**
- Every claim the paper inherits from prior work → bullet in
  `### Background`, citing the **original** source per the Indirect
  Citation Rule with explicit `reported via [[X]]` provenance. Aim
  5-15 bullets for an empirical paper, 20+ for a review or thesis
  introduction.
- The theoretical framework names every concept / model the paper
  builds on, with wikilinks.
- The gap is stated in 1-2 sentences (not paraphrased away).
- Hypotheses, when explicit, are listed verbatim with page numbers.

**Methods (### Study Design / ### Participants / ### Intervention(s) /
### Comparator / ### Outcome Measures / ### Procedure /
### Statistical Analysis / ### Ethics / ### Data and Code Availability)**
- Trial registration ID, IRB number, conflict-of-interest disclosure
  belong in `### Ethics`. Pre-registration / data / code repositories
  belong in `### Data and Code Availability`.
- `### Participants`: enrolled vs randomized vs analyzed counts;
  inclusion AND exclusion criteria as bullet lists; population profile
  detailed enough that `tools/cohort_tracker.py` can extract chronicity
  / severity / lesion side.
- `### Intervention(s)`: dose (sessions × duration × frequency),
  delivery (who, where, supervision), co-interventions allowed/
  forbidden - for every arm separately. Link to
  `[[interventions/<slug>]]`.
- `### Outcome Measures`: distinguish **primary**, **secondary**,
  **exploratory**. Each measure → `[[methods/<MethodName>]]` with the
  timepoint(s) at which it's assessed.
- `### Statistical Analysis`: tests, multiple-comparison correction,
  pre-specified vs exploratory analyses, software + version.

**Results (### Participant Flow / ### Baseline Characteristics /
### Primary Outcome / ### Secondary Outcomes / ### Subgroup analyses /
### Adverse Events / ### Compliance / ### Tables and Figures)**
- `### Primary Outcome`: verbatim with effect size, 95 % CI, p-value,
  direction (p. ?). Single bullet - this is the paper's flagship
  result.
- `### Secondary Outcomes`: every one with effect size and statistic,
  not collapsed to "improved". A typical RCT reports 3-10 secondary
  outcomes; if you have 1, you missed them.
- `### Subgroup / Exploratory`: each one with the explicit warning
  "exploratory" if the paper labels it so.
- `### Adverse Events`: all reported, with severity and attribution.
- `### Compliance`: adherence rate and dropout reasons.
- `### Tables and Figures`: each numbered table/figure described with
  its content and any pattern visible only there.

**Discussion (### Summary of findings / ### Comparison with Prior Work /
### Mechanism / ### Strengths / ### Limitations /
### Generalizability / ### Future Research)**
- `### Comparison with Prior Work` is where the Indirect Citation Rule
  fires hardest. Every "aligns with"/"differs from" claim cites the
  original Y, not the transmitter X (this paper) - use
  `[[Y]] (p. ?), reported via this paper's discussion (p. ?)`.
- `### Limitations`: every limitation acknowledged by the authors. Most
  honest papers list 4-6.
- `### Future Research`: each open question routed to
  `wiki/questions/<slug>.md`.

**Recommendations / Implications**
- Every actionable item, including secondary, conditional, and
  cautionary ones - not just the headline. Each routed to
  `wiki/recommendations/<topic>.md`. See "Guidelines &
  meta-analyses" below for the strict rule on guideline papers.

**Reporting Standard Alignment** - identify CONSORT / STROBE / PRISMA /
STARD / TREND / CARE / ARRIVE and flag deviations.

**Verbatim Quotes** - minimum 3 quotes covering Introduction, Results,
Discussion (one per section).

**Cites** - populated from the References section automatically by
`tools/parse_references.py`; review the snowball candidates before
moving on.

## Guidelines, meta-analyses, consensus statements (special case)

Such papers contain dense **recommendation tables** (e.g. Lefaucheur
guidelines for TMS list dozens of recommendations across depression,
pain, stroke, Parkinson, OCD…, each with A/B/C evidence level).

Strict rule for these papers:

1. **Enumerate every recommendation** in the source page's
   `## Recommendations / Implications`. If the paper has a Table
   titled "Recommendations" or "Levels of Evidence", **the source page
   must reference at least the row count of that table**. Don't
   paraphrase "the paper recommends rTMS for several conditions" - 
   list each one.
2. **Route each recommendation** to the appropriate
   `wiki/recommendations/<topic-slug>.md` page (create per-topic pages
   if needed). For Lefaucheur-type guidelines, expect 5-15
   recommendation pages to be touched, one per condition / protocol
   family.
3. **Preserve evidence level** (A / B / C) verbatim with each item.
4. **Quote the recommendation text verbatim** when feasible - these
   papers are reused as authoritative references.

A guideline paper that produces a 200-word source page is incomplete
by definition. Expect 1500-3000 words for a major guideline.

## Anti-patterns (do NOT)

- ❌ Don't write *"the paper shows X"* without quoting the supporting
  result.
- ❌ Don't paraphrase numerical results - quote verbatim.
- ❌ Don't list a method with just `[[methods/X]]`. Describe **how this
  specific paper used it** (parameters, sample, deviations from
  standard).
- ❌ Don't summarize the abstract; extract from the body.
- ❌ Don't compress 8 findings into 2 bullets to save space.
- ❌ Don't drop secondary or cautionary recommendations because they're
  less prominent.
- ❌ Don't summarize a guideline paper's recommendation table - 
  enumerate.

## Length expectations (rough heuristic, not hard rule)

| Paper type | Source page length |
|---|---|
| Conference abstract | 300-600 words |
| Theoretical / opinion | 600-1200 words |
| Empirical (RCT, cohort, cross-sectional) | 800-2000 words |
| Review / meta-analysis | 1200-2500 words |
| Guidelines / consensus statement | 1500-3000 words |
| Thesis | 2000-5000 words (across chapters) |

A source page below the lower bound for its type is almost certainly
incomplete unless the paper itself is unusually short.

## Method, intervention, recommendation pages - depth

Same rule applies to the auxiliary pages updated at ingest:

- When the **method update** step runs, don't just append
  `- [[<source-slug>]]` to `## Used In This Wiki`. Add a 2-sentence
  description of *how this paper used the method* - parameters,
  sample, deviation from standard protocol. Example:
  > Used 1 Hz rTMS over contralesional M1, 1200 pulses, 10 sessions
  > over 2 weeks ([[lefaucheur-2014]] p. 22). Differs from
  > [[khedr-2005]] protocol by lower intensity (90 vs 110 % RMT).
- Same for intervention pages: document each study's protocol variant
  in `## Variants` and `## Identified Studies`.
- Recommendation pages: enumerate each new item under the right
  evidence-strength heading; never collapse multiple recs into one
  bullet.

## Self-critique gate (mandatory)

**Before declaring the ingest complete, re-read the source page and
ask, in this order:**

1. Did I capture every numerical result reported in the paper? If the
   paper has a Results table with N rows, does the source page
   reference N findings?
2. Did I list every measure used and link to its method page?
3. Does `## Background` cite at least 3 prior works (Indirect Citation
   Rule)?
4. Are there 3+ verbatim quotes covering different sections?
5. Are all author-acknowledged limitations listed?
6. **For guidelines/reviews/meta-analyses**: does the source page
   enumerate every recommendation in the original recommendation
   table? Were they routed to per-topic recommendation pages?
7. For each method touched, did I add a per-source description (not
   just a wikilink)?

If any answer is "no", expand the missing section by re-reading the
relevant part of the source MD before finishing. Do not declare ingest
complete with these gates open.
