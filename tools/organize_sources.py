#!/usr/bin/env python3
"""Reorganize wiki/sources/ into thematic folders based on each page's frontmatter.

Layout (theses kept apart, articles classified by intervention/study type):

    wiki/sources/
    ├── theses/
    │   └── <thesis-slug>/        # parent + chapters
    └── articles/
        ├── bci/[<subfamily>/]    # principal: BCI; subfamily: mi-bci, ao-bci, hybrid…
        ├── tms/[<subfamily>/]    # principal: TMS; subfamily: rtms, itbs, ctbs…
        ├── tdcs/
        ├── mirror-therapy/
        ├── robot-therapy/
        ├── mental-practice/
        ├── physio/
        ├── imaging/[<modality>/] # observational imaging without intervention
        ├── reviews/<form>/       # systematic | scoping | narrative
        ├── theory/
        ├── methodology/
        └── general/

Routing rule (first match wins):
    1. tags contains "thesis" → theses/<slug>/<slug>.md
    2. tags contains "thesis-chapter" → theses/<parent_thesis>/<slug>.md
    3. study_design ∈ {systematic-review, meta-analysis} → articles/reviews/systematic/
       study_design == scoping-review                   → articles/reviews/scoping/
       study_design == narrative-review                 → articles/reviews/narrative/
    4. study_design == theoretical    → articles/theory/
    5. study_design == methodological → articles/methodology/
    6. intervention_family is set and != "none" → articles/<family>/[<subfamily>/]
    7. methods contains DTI/fMRI/EEG (no intervention) → articles/imaging/[<modality>/]
    8. otherwise → articles/general/

Tier 2 sub-folders (--promote): only created when ≥ N papers share the
same (family, subfamily) pair. Threshold N defaults to 3.

Usage:
    python tools/organize_sources.py --dry-run     # preview moves
    python tools/organize_sources.py                # tier 1 move only
    python tools/organize_sources.py --promote      # also create tier-2 subfolders
    python tools/organize_sources.py --promote --threshold 5
"""
import argparse
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, SRC_DIR, load_sources  # noqa: E402

ARTICLES_DIR = SRC_DIR / "articles"
THESES_DIR = SRC_DIR / "theses"

# Slug-form intervention_family → folder name
#
# DOMAIN-SPECIFIC: this dict mirrors the interventions taxonomy declared
# in context.md. The default values below configure GraphBib for the
# stroke / MI-BCI / TMS de-facto specialization. To retarget GraphBib
# for another field, edit BOTH context.md (declarative) AND this dict
# (the Python source of truth used by source routing).
#
# Any intervention_family value not in this dict routes the source to
# articles/general/ by default — safe fallback for partial adaptations.
FAMILY_FOLDER = {
    "bci": "bci",
    "tms": "tms",
    "tdcs": "tdcs",
    "mirror": "mirror-therapy",
    "robot": "robot-therapy",
    "mental-practice": "mental-practice",
    "physio": "physio",
    "combined": "general",  # combined → general; subfamily explicit if hybrid
}
REVIEW_DESIGNS = {
    "systematic-review": "systematic",
    "meta-analysis": "systematic",
    "scoping-review": "scoping",
    "narrative-review": "narrative",
}
IMAGING_METHODS = {"DTI", "Tractography", "fMRI", "MRI", "EEG", "MEG", "PET"}
IMAGING_MODALITY = {
    "DTI": "dti",
    "Tractography": "dti",
    "fMRI": "fmri",
    "MRI": "fmri",
    "EEG": "eeg",
    "MEG": "meg",
    "PET": "pet",
}


def normalize(s):
    return (s or "").strip().lower().replace("_", "-")


def primary_imaging_modality(methods):
    for m in methods or []:
        if m in IMAGING_MODALITY:
            return IMAGING_MODALITY[m]
    return None


def has_imaging_method(methods):
    return any(m in IMAGING_METHODS for m in (methods or []))


def target_path(src):
    """Return the target Path for a source dict, before tier-2 promotion."""
    fm, slug = src["fm"], src["slug"]
    tags = [normalize(t) for t in (fm.get("tags") or [])]

    # 1. Theses
    if "thesis" in tags:
        return THESES_DIR / slug / f"{slug}.md", ("theses", slug)
    if "thesis-chapter" in tags:
        parent = fm.get("parent_thesis") or "unknown-thesis"
        return THESES_DIR / parent / f"{slug}.md", ("theses", parent)

    # 2-5. Reviews / theory / methodology
    sd = normalize(fm.get("study_design"))
    if sd in REVIEW_DESIGNS:
        sub = REVIEW_DESIGNS[sd]
        return ARTICLES_DIR / "reviews" / sub / f"{slug}.md", ("reviews", sub)
    if sd == "theoretical":
        return ARTICLES_DIR / "theory" / f"{slug}.md", ("theory", None)
    if sd == "methodological":
        return ARTICLES_DIR / "methodology" / f"{slug}.md", ("methodology", None)

    # 6. Intervention principal
    family = normalize(fm.get("intervention_family"))
    subfamily = normalize(fm.get("intervention_subfamily"))
    if family and family != "none":
        folder = FAMILY_FOLDER.get(family, family)
        if subfamily:
            return ARTICLES_DIR / folder / subfamily / f"{slug}.md", (folder, subfamily)
        return ARTICLES_DIR / folder / f"{slug}.md", (folder, None)

    # 7. Observational imaging
    if has_imaging_method(fm.get("methods")):
        modality = primary_imaging_modality(fm.get("methods")) or "general"
        return ARTICLES_DIR / "imaging" / modality / f"{slug}.md", ("imaging", modality)

    # 8. Fallback
    return ARTICLES_DIR / "general" / f"{slug}.md", ("general", None)


def git_mv(old, new, dry_run):
    if old == new:
        return "keep"
    new.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return "would-move"
    # git mv — preserves history
    rel_old = old.relative_to(REPO_ROOT)
    rel_new = new.relative_to(REPO_ROOT)
    try:
        subprocess.run(
            ["git", "mv", str(rel_old), str(rel_new)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return "moved"
    except subprocess.CalledProcessError as e:
        # Fallback to plain mv if git rejects (e.g. file untracked)
        shutil.move(str(old), str(new))
        return "moved-untracked"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview moves without touching the filesystem.")
    ap.add_argument("--promote", action="store_true",
                    help="Promote subfamily groups to tier-2 subfolders when count >= threshold.")
    ap.add_argument("--threshold", type=int, default=3,
                    help="Minimum group size to create a tier-2 subfolder (default 3).")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit("No sources to organize.")

    plans = []
    for s in sources:
        target, group = target_path(s)
        plans.append((s, target, group))

    # Tier-2 promotion: count subfamily groups, demote if below threshold (unless --promote)
    group_counts = Counter()
    for _, _, group in plans:
        if group[1] is not None:
            group_counts[group] += 1

    final_plans = []
    for s, target, group in plans:
        if group[1] is not None and not args.promote:
            # Without --promote, drop subfamily folder unless it already exists
            if not target.parent.is_dir():
                target = target.parent.parent / target.name
                group = (group[0], None)
        elif args.promote and group[1] is not None:
            if group_counts[group] < args.threshold:
                # Below threshold → keep at tier 1
                target = target.parent.parent / target.name
                group = (group[0], None)
        final_plans.append((s, target, group))

    # Stats
    stats = Counter()
    for s, target, _ in final_plans:
        action = git_mv(s["path"], target, args.dry_run)
        stats[action] += 1
        if action == "would-move":
            print(f"[dry] {s['path'].relative_to(REPO_ROOT)}")
            print(f"      → {target.relative_to(REPO_ROOT)}")
        elif action == "moved":
            print(f"  ✓ {target.relative_to(REPO_ROOT)}")
        elif action == "moved-untracked":
            print(f"  ✓ {target.relative_to(REPO_ROOT)}  (untracked, mv not git-tracked)")

    print(f"\n=== {len(final_plans)} sources processed ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if args.dry_run:
        print("\n(dry-run: no file moved. Re-run without --dry-run to apply.)")


if __name__ == "__main__":
    main()
