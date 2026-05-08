"""
Route flat wiki/sources/*.md files into articles/ subfolders
based on frontmatter (intervention_family, study_design, tags).
Routing rule mirrors CLAUDE.md:
  1. tags contains thesis* → skip (already handled)
  2. systematic-review / meta-analysis → reviews/systematic/
  3. scoping-review → reviews/scoping/
  4. narrative-review → reviews/narrative/
  5. theoretical → theory/
  6. methodological → methodology/
  7. intervention_family set → <family>/[<subfamily>/]
     known families: BCI→bci, TMS/rTMS→tms, FES/NMES→fes,
     Mental Practice/mental-practice→mental-practice,
     Physio/rehabilitation→physio, tDCS→tdcs
  8. tags/slug hint: imagery/mi-assessment → imagery/
  9. imaging modality hint → imaging/<modality>
 10. fallback → general/
"""
import os, re, shutil, sys, yaml

SOURCES = "wiki/sources"
ARTICLES = os.path.join(SOURCES, "articles")

FAMILY_MAP = {
    "bci": "bci", "mi-bci": "bci", "BCI": "bci",
    "tms": "tms", "rtms": "tms", "rTMS": "tms", "TMS": "tms",
    "itbs": "tms", "ctbs": "tms", "tbs": "tms", "nibs": "tms",
    "fes": "fes", "nmes": "fes", "FES": "fes", "NMES": "fes",
    "mental-practice": "mental-practice", "mental practice": "mental-practice",
    "physio": "physio", "rehabilitation": "physio",
    "tdcs": "tdcs", "tDCS": "tdcs",
    "mirror-therapy": "physio", "robot-therapy": "physio",
    "combined": "bci",  # BCI+TMS combined → principal = BCI folder
    "neurofeedback": "bci",
}

DESIGN_MAP = {
    "systematic-review": "reviews/systematic",
    "meta-analysis": "reviews/systematic",
    "scoping-review": "reviews/scoping",
    "narrative-review": "reviews/narrative",
    "theoretical": "theory",
    "methodological": "methodology",
}

IMAGERY_SLUGS = re.compile(
    r"(mi-ability|mi-assessment|mi-impair|mi-inability|mi-strategy|"
    r"kviq|miq|mental-chron|ki-vi|imagery|imagerie|imagin|"
    r"guillot|jeannerod|malouin|munzert|hetu|kraeutner|santoro|"
    r"neuper|chholak|ouin|sirigu|ruffino|sharma|kantak|"
    r"braun.*mi|mi.*stroke|motor-imag)"
)

IMAGING_SLUGS = re.compile(
    r"(dti|tractography|fa-cst|fa-hf|disconnectome|schlemm|"
    r"dulyan|jang.*cst|moura.*dti|zolkefley|williams.*cst|"
    r"lam.*struct|trunk.*cst|hordacre|alawieh|"
    r"grefkes|rehme|dijkhuizen|guggisberg|cassidy|cheng.*network|"
    r"hensel.*fc|hallett.*fc|olafson|fc-stroke|"
    r"aoni|bazanova|jeon|tangwiriyasakul|fu-2006|mierau|"
    r"gray.*iaf|devicofallani|hamedi|feng.*fc|corcoran.*iaf)"
)


def read_frontmatter(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def classify(slug, fm):
    tags = [str(t).lower() for t in (fm.get("tags") or [])]
    if any(t in ("thesis", "thesis-chapter") for t in tags):
        return None  # skip

    design = str(fm.get("study_design") or "").lower().replace("_", "-")
    if design in DESIGN_MAP:
        return DESIGN_MAP[design]

    family_raw = str(fm.get("intervention_family") or "").lower().strip()
    if family_raw and family_raw not in ("none", ""):
        folder = FAMILY_MAP.get(family_raw, family_raw.lower())
        # CLAUDE.md: tier-2 subfolders only when ≥3 papers share a subfamily.
        # Flatten all to tier-1 here; tools/organize_sources.py --promote handles promotion.
        return folder

    # heuristic slug / tag hints
    if IMAGERY_SLUGS.search(slug):
        return "imagery"
    if IMAGING_SLUGS.search(slug):
        return _imaging_modality(slug, fm)

    # physio / general fallback tags
    for t in tags:
        if t in ("physio", "rehabilitation"):
            return "physio"

    return "general"


def _imaging_modality(slug, fm):
    methods = [str(m).lower() for m in (fm.get("methods") or [])]
    if any("dti" in m or "tractography" in m for m in methods):
        return "imaging/dti"
    if any("fmri" in m for m in methods):
        return "imaging/fmri"
    if any("eeg" in m for m in methods):
        return "imaging/eeg"
    # slug hints — DTI/structural
    if re.search(r"(dti|tractography|disconnectome|schlemm|dulyan|moura-2019|zolkefley|"
                 r"lam-2018|jang-2014|trunk-2022|hordacre|alawieh|williams-2012-cst)", slug):
        return "imaging/dti"
    # fMRI / BOLD
    if re.search(r"(grefkes|rehme|dijkhuizen|cassidy|cheng|olafson|guggisberg)", slug):
        return "imaging/fmri"
    # EEG-based FC / oscillations
    return "imaging/eeg"


def main():
    dry_run = "--dry-run" in sys.argv
    moved, skipped, errors = [], [], []

    flat_files = sorted(
        f for f in os.listdir(SOURCES)
        if f.endswith(".md") and os.path.isfile(os.path.join(SOURCES, f))
    )

    for fname in flat_files:
        src = os.path.join(SOURCES, fname)
        slug = fname[:-3]
        fm = read_frontmatter(src)
        dest_folder = classify(slug, fm)
        if dest_folder is None:
            skipped.append(fname)
            continue
        dest_dir = os.path.join(ARTICLES, dest_folder)
        dest = os.path.join(dest_dir, fname)
        if dry_run:
            print(f"  {fname} → articles/{dest_folder}/")
        else:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(src, dest)
            moved.append(f"{fname} → articles/{dest_folder}/")

    if dry_run:
        print(f"\nTotal: {len(flat_files)} files, {len(skipped)} skipped (theses)")
    else:
        print(f"Moved {len(moved)} files, skipped {len(skipped)}, errors {len(errors)}")
        for m in moved:
            print(f"  {m}")


if __name__ == "__main__":
    main()
