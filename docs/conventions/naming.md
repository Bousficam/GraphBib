# Naming Conventions

## Slugs and filenames

Format is domain-agnostic; only the **structure** below matters. For
the concrete vocabulary (which concepts / methods / interventions
to expect), see `context.md` at the repo root.

- **Source slugs (papers)**: `kebab-case`
  — `firstauthor-year-shorttitle.md`
- **Thesis slugs**: `lastname-year-shorttitle.md`
- **Book slugs**: `firstauthor-year-shorttitle.md`
- **Entity pages** (authors, labs, institutions): `TitleCase.md`
- **Concept pages**: `TitleCase.md` (single-word ideal, multi-word
  joined CamelCase)
- **Method pages**: `TitleCase.md` (abbreviations preserved as
  written: `EEG.md`, `fMRI.md`)
- **Intervention pages**: `kebab-case.md` matching the family or
  subfamily name from your `context.md` taxonomy
- **Recommendation pages**: `kebab-case.md`
- **Question pages**: `kebab-case.md`
- **Synthesis pages**: `kebab-case.md` (often `<topic>-review.md`)

## Domain vocabulary

Domain-specific page-name expectations (concept lists, method
abbreviations, recommendation slugs) live in **`context.md`** at
the repo root — not here. That file is the single source of truth
for "what entries are likely in this wiki, given the field it covers".

When ingesting, the agent reads `context.md`'s vocabulary sections
to decide whether a mention should land on an existing page (with
the canonical name from the context) or spawn a new one. This file
just declares the *format* (CamelCase for concepts/methods/entities,
kebab-case for interventions/recommendations/questions/syntheses).

If you're starting a wiki without a `context.md`, the agent runs in
neutral mode and grows vocabulary organically — see
`docs/context/README.md` for the full mechanism and example
contexts.
