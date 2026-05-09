# Source Organization (thematic folders)

`wiki/sources/` is **not flat**. New sources are written directly into
thematic sub-folders so the corpus stays browsable in Obsidian. Theses
are kept apart from articles. The Indirect Citation Rule and
`[[wikilinks]]` work the same way regardless of folder depth (Obsidian
resolves by file basename).

## Layout

```
wiki/sources/
├── theses/<slug>/<slug>.md             # parent + chapter sub-sources
└── articles/
    ├── bci/        [<subfamily>/]      # mi-bci, ao-bci, hybrid…
    ├── tms/        [<subfamily>/]      # rtms, itbs, ctbs…
    ├── tdcs/
    ├── mirror-therapy/
    ├── robot-therapy/
    ├── mental-practice/
    ├── physio/
    ├── imaging/    [<modality>/]       # dti, fmri, eeg (observational)
    ├── reviews/    <form>/             # systematic, scoping, narrative
    ├── theory/                          # framework / conceptual papers
    ├── methodology/                     # new methods / pipelines
    └── general/                         # fallback
```

## Routing rule (first match wins)

Apply at ingest step 5 to choose the destination path:

1. `tags` contains `thesis` → `theses/<slug>/<slug>.md`
2. `tags` contains `thesis-chapter` → `theses/<parent_thesis>/<slug>.md`
3. `study_design ∈ {systematic-review, meta-analysis}` → `articles/reviews/systematic/<slug>.md`
4. `study_design == scoping-review` → `articles/reviews/scoping/<slug>.md`
5. `study_design == narrative-review` → `articles/reviews/narrative/<slug>.md`
6. `study_design == theoretical` → `articles/theory/<slug>.md`
7. `study_design == methodological` → `articles/methodology/<slug>.md`
8. `intervention_family` set (≠ `none`) → `articles/<family>/[<intervention_subfamily>/]<slug>.md`
9. `methods` contains DTI / fMRI / EEG with no intervention → `articles/imaging/<modality>/<slug>.md`
10. Otherwise → `articles/general/<slug>.md`

## Principal vs adjuvant

When a study combines multiple interventions (e.g. MI-BCI + concurrent
rTMS), the **dossier = principal intervention**, decided in this order:

1. Title / abstract framing — *"we tested X"* → X is principal.
2. Experimental vs control arm — what distinguishes them is principal.
3. If still ambiguous, first item in `interventions:` is principal.

The agent sets `intervention_family:` to the principal. Adjuvants
remain listed in `interventions:` (full list).

Examples:

- *"MI-BCI training with concurrent rTMS conditioning"* →
  `intervention_family: BCI`, `intervention_subfamily: hybrid` →
  `articles/bci/hybrid/`.
- *"cTBS over contralesional M1, with standard physiotherapy as
  control"* → `intervention_family: TMS`, `intervention_subfamily: ctbs`
  → `articles/tms/ctbs/`.

## Tier-2 subfolders (`mi-bci/`, `rtms/`, …)

Created **only when ≥ 3 papers share the same subfamily** to avoid a
forest of nearly-empty folders. The agent fills `intervention_subfamily:`
at ingest, but writes to the tier-1 folder by default.

`tools/organize_sources.py --promote --threshold 3` periodically scans
the corpus, counts subfamily groups, and `git mv`s papers into tier-2
subfolders for groups that pass the threshold.

## Reorganization workflow

```bash
# Preview first (no file moved)
python tools/organize_sources.py --dry-run

# Apply tier-1 routing only
python tools/organize_sources.py

# Apply tier-1 + promote established subfamilies to tier-2
python tools/organize_sources.py --promote --threshold 3
```

The tool uses `git mv` so file history is preserved.
