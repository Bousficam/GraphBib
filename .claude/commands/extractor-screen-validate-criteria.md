---
description: Audit a screening/criteria.md for defects BEFORE screening starts — vague terms, missing Stage tags, duplicate tags, subjective phrasing, placeholder leftovers, missing PICO definitions. Pure deterministic checks (no LLM, no network). Surfaces findings + optional interactive fix loop. Pairs with /extractor-screen-init (which writes criteria.md) and runs before /extractor-screen-validate (DOI gate) and /extractor-screen-tiab (T/A pass).
argument-hint: "[<vault>/]<project-name>  [--fix]  [--json]"
---

Audit `screening/criteria.md` for defects that would cause biased
exclusions or screener disagreement before the actual screening
starts.

Arguments: $ARGUMENTS

# When to use

Right after `/extractor-screen-init` (which writes `criteria.md`)
and before `/extractor-screen-tiab` (which uses it to screen
hundreds of articles).

If criteria.md has vague terms, missing Stage tags, or duplicate
exclusion tags, two PRISMA screeners would disagree on the same
abstract and the κ value (inter-rater agreement) tanks. Catching
these defects at the criteria-authoring step is the cheapest
intervention — fixing one ambiguity here saves an audit gate over
1000 decisions later.

This command also runs naturally during a refinement loop:

```
/extractor-screen-init   →   criteria.md v1
/extractor-screen-validate-criteria   →   audit, surface 7 issues
[user edits criteria.md]
/extractor-screen-validate-criteria   →   re-audit, 0 issues
/extractor-screen-tiab   →   confident screening
```

# What it checks

Six deterministic rules, no LLM, no network:

1. **PICO completeness** — every PICO row has a non-placeholder
   Definition (no `<from Q1>` leftovers).
2. **Stage tag presence** — every criterion (inclusion + exclusion)
   has a Stage cell ∈ {tiab, fulltext, both}. Missing → error
   (the screener-tiab agent's testability gate can't fire).
3. **Tag uniqueness** — every criterion `Tag` appears once. Two
   rows with the same tag collide in `tiab-decisions.xlsx`.
4. **Vague terms** — language flagged by a static lexicon
   (`recent`, `severe`, `elderly`, `high`, `low`, `quality`,
   `appropriate`, `significant`, …) without a quantification.
5. **Subjective phrasing** — `high-quality`, `well-designed`,
   `adequate sample`, etc. PRISMA forbids value-laden phrasing
   at the eligibility bar — those belong in quality appraisal,
   not screening.
6. **Verifiable-from column** — exclusion table should declare
   where in the body each criterion is verified (e.g. "Methods
   §Participants"). Absence is a hygiene info, not an error.

Each finding gets a severity:
  - **error**  : will cause a wrong / inconsistent screening
                  decision. Block the user from proceeding.
  - **warn**   : will cause disagreement between screeners.
                  Recommend fixing but allow proceeding.
  - **info**   : hygiene suggestion. No action required.

# Procedure

## Step 1 — Resolve the project path

Parse `$ARGUMENTS`:
- `<vault>/<project>` or `<project>` (vault auto-detected from
  `$PROJECT_VAULT` or single sub-vault, same rules as
  `/extractor-init`).
- `--fix` (default off) — after surfacing findings, enter an
  interactive fix loop with the user.
- `--json` (default off) — print findings as JSON on stdout
  instead of the user-facing report (machine-readable mode).

Build the project path:
```
project-review/<vault>/<project>/        # phased layout
project-review/<project>/                # legacy flat fallback
```

Refuse if `screening/criteria.md` doesn't exist (instruct the user
to run `/extractor-screen-init` first).

## Step 2 — Run the audit

```bash
python tools/criteria_audit.py <project-path>
```

The tool prints a summary and writes
`screening/reports/criteria-audit.md`:

```
✓ Audited project-review/<vault>/<project>/screening/criteria.md
  PICO rows      : 4
  Inclusion rows : 5
  Exclusion rows : 9

  ERRORS : 0
  WARN   : 3
  INFO   : 1

✓ Report : project-review/<vault>/<project>/screening/reports/criteria-audit.md
```

If `--json` was passed, the tool emits findings as JSON instead
of writing the report. Stop after the JSON dump.

## Step 3 — Surface the findings

Read `screening/reports/criteria-audit.md` and present:

```
Audit complete on screening/criteria.md.

ERRORS (must fix before /extractor-screen-tiab):
  [stage-missing]    Inclusion criterion `eligible-design` has no Stage.
  [tag-duplicate]    Exclusion tag `wrong-pop` appears twice (rows 1 and 2).

WARN (recommended — reduces screener disagreement):
  [vague-term]       Inclusion `eligible-population` uses `elderly` without an age range.
  [subjective-phrase] Inclusion `eligible-design` says `high-quality` (move to quality appraisal).
  [vague-term]       Exclusion `wrong-outcome` uses `significant` without a threshold.

INFO:
  [verifiable-missing] Exclusion table has no Verifiable-from column.

Options:
  [f]   Enter fix loop — walk through each finding interactively
  [e]   Open criteria.md in your editor; re-run the audit afterwards
  [a]   Accept as-is and proceed (errors remain; screening will be biased)
  [s]   Stop — re-run later
```

## Step 4 — Fix loop (only when user picks [f] or --fix was passed)

For each finding (errors first, then warns, info skipped):

1. Read the relevant row of `criteria.md`. Show it verbatim in
   context (the table row + its current Stage and tag).
2. Propose a concrete rewrite based on the finding type:

   - `stage-missing` / `stage-invalid` → ask:
     ```
     Stage for `<tag>` ? [tiab / fulltext / both]
       tiab     — reliably checkable from title + abstract
       fulltext — needs Methods/Results detail
       both     — visible at T/A AND must be confirmed at full text
     ```
     Apply the answer to the row's Stage cell.

   - `tag-duplicate` → ask:
     ```
     Tag `<tag>` collides between row {i} and row {j}.
       [k1] Keep row {i}, rename row {j}'s tag to ____
       [k2] Keep row {j}, rename row {i}'s tag to ____
       [m]  Merge the two rows into one (combine criterion texts)
       [s]  Skip — both rows kept as-is (the screening will fail
            to distinguish them; T/A decisions for one will
            shadow the other)
     ```

   - `criterion-placeholder` → show the placeholder, ask the user
     for the verbatim text. Apply.

   - `vague-term` → show the vague word in context, ask:
     ```
     `<tag>` uses `<word>` without quantification.
     What's the explicit threshold / range?
       Example shapes (NOT a list of recommended values):
         "recent stroke"   → "stroke onset < 6 months"
         "elderly"         → "age ≥ 65 years"
         "severe"          → "Fugl-Meyer UE < 30"
     Your rewrite (or `skip` to keep the vague term):
     ```
     Apply the rewrite to the criterion text.

   - `subjective-phrase` → ask:
     ```
     `<tag>` uses `<phrase>` — value-laden, PRISMA-discouraged.
       [r]   Rewrite as an objective criterion (you provide text)
       [m]   Move to quality appraisal (not a screening criterion)
       [s]   Keep — accept the screener disagreement risk
     ```

   - `pico-placeholder` → ask the user for the verbatim
     definition (free text), apply.

   - `pico-missing` → cannot continue; tell the user to re-run
     `/extractor-screen-init` Q1–Q4 and re-write the PICO table.

3. After each fix, write the change back to `criteria.md` and
   re-run `criteria_audit.py` to confirm the finding is gone.
4. Continue with the next finding.

When all errors are resolved, present:

```
✓ All errors resolved.
  N warnings remain — review them when you have time.
  Re-run /extractor-screen-validate-criteria to see the updated audit.

Next:
  /extractor-screen-validate <project>   (DOI hygiene gate)
  /extractor-screen-tiab     <project>   (PRISMA pass 1)
```

## Step 5 — Update the log

Append to `<project-path>/log.md`:

```markdown
## YYYY-MM-DD — Criteria audit
- Errors at start  : N
- Warnings at start: N
- Errors at end    : N  (target: 0)
- Warnings at end  : N
- User action      : fixed K issues | accepted as-is | deferred
```

# Hard constraints

- Never modify `criteria.md` without explicit user confirmation
  in the fix loop. Defaults are non-destructive (Step 3 option
  `[a]` accepts as-is).
- Never invent thresholds for vague terms. The user supplies
  every quantification — the agent only asks the question.
- Never run the audit when `tiab-decisions.xlsx` already exists
  AND the user is making criteria edits — changing the bar
  after screening has started invalidates earlier decisions.
  If decisions exist, warn:
  ```
  ⚠ tiab-decisions.xlsx already has K rows. Editing criteria.md
    now means earlier decisions were taken against a different
    bar. Either:
      - Accept the inconsistency (note it in the protocol audit)
      - Discard tiab-decisions.xlsx and re-screen with the
        corrected criteria
  Proceed with edits anyway? [y/N]
  ```
- The audit is **deterministic**, not LLM-driven. The findings
  are tied to a static lexicon and table-parsing rules — no
  hallucination risk. If a vague-term flag feels overzealous,
  the user can ignore it (warnings are non-blocking).
