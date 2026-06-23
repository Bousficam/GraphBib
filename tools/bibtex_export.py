#!/usr/bin/env python3
"""Export wiki/sources/ as BibTeX, organized in three modes.

Mode 1 - master file with %-section comments by primary type (default):

    python tools/bibtex_export.py > wiki.bib

Mode 2 - one file per concept / intervention / method:

    python tools/bibtex_export.py --per-concept --output-dir bib/
    python tools/bibtex_export.py --per-intervention --output-dir bib/
    python tools/bibtex_export.py --per-method --output-dir bib/

Mode 3 - explicit chapter mapping (manuscript / thesis):

    python tools/bibtex_export.py --chapters chapters.yaml --output-dir bib/

    # chapters.yaml example:
    # chapters:
    #   - name: "Introduction"
    #     pages: [wiki/concepts/MotorRecovery.md, wiki/concepts/Neuroplasticity.md]
    #   - name: "Methods"
    #     pages: [wiki/methods/MI-BCI.md, wiki/methods/TMS.md]

Each chapter file contains the BibTeX entries for the source pages
linked from the listed wiki pages.

The script reads each source page's `bibtex_key`, `authors`, `title`,
`journal` / `university`, `year`, `doi` from frontmatter and emits a
@article (or @phdthesis when degree: PhD/MSc/HDR is set).
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from _lib import REPO_ROOT, SRC_DIR, WIKI_DIR  # noqa: E402

WIKILINK_RE = re.compile(r"\[\[([A-Za-z0-9\-_/.]+)\]\]")


def parse_fm(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]
            except Exception:
                pass
    return {}, text


def slugify_for_key(s):
    return re.sub(r"[^A-Za-z0-9]+", "", (s or "").lower())[:30]


def make_bibtex(slug, fm):
    """Render a single BibTeX entry from a source page's frontmatter."""
    key = fm.get("bibtex_key") or slug
    is_thesis = "thesis" in (fm.get("tags") or []) or fm.get("degree")
    entry_type = "@phdthesis" if is_thesis else "@article"

    authors = fm.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]
    author_str = " and ".join(authors) if authors else ""

    fields = []
    if author_str:
        fields.append(("author", author_str))
    if fm.get("title"):
        fields.append(("title", str(fm["title"]).replace("{", "").replace("}", "")))
    if is_thesis:
        if fm.get("university"):
            fields.append(("school", fm["university"]))
        if fm.get("degree"):
            fields.append(("type", f"{fm['degree']} thesis"))
    elif fm.get("journal"):
        fields.append(("journal", fm["journal"]))
    if fm.get("year"):
        fields.append(("year", str(fm["year"])))
    if fm.get("doi"):
        fields.append(("doi", fm["doi"]))
    if fm.get("source_pdf"):
        fields.append(("note", f"PDF: {fm['source_pdf']}"))

    body = ",\n  ".join(f"{k:8s} = {{{v}}}" for k, v in fields)
    return f"{entry_type}{{{key},\n  {body}\n}}"


def load_sources():
    out = []
    if not SRC_DIR.is_dir():
        return out
    for p in sorted(SRC_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm, body = parse_fm(text)
        out.append({"slug": p.stem, "fm": fm, "body": body, "path": p})
    return out


def primary_type(fm, body):
    """Best-effort primary chapter for a source: concept / intervention / method / recommendation / question."""
    family = fm.get("intervention_family")
    if family and family != "none":
        return ("intervention", family)
    methods = fm.get("methods") or []
    if methods:
        return ("method", methods[0])
    domain = fm.get("domain") or []
    if domain:
        return ("concept", domain[0])
    return ("source", "uncategorized")


def write_master(sources, out):
    """Write a single .bib with %-section comments by primary type."""
    grouped = {}
    for s in sources:
        cat, label = primary_type(s["fm"], s["body"])
        grouped.setdefault((cat, label), []).append(s)

    chunks = []
    for (cat, label), items in sorted(grouped.items()):
        header = f"% {'=' * 60}\n% {cat.upper()}: {label}\n% {'=' * 60}"
        items.sort(key=lambda x: (x["fm"].get("year") or 9999, x["slug"]))
        body = "\n\n".join(make_bibtex(s["slug"], s["fm"]) for s in items)
        chunks.append(f"{header}\n\n{body}")
    out.write("\n\n".join(chunks) + "\n")


def collect_per_target(sources, target_kind):
    """target_kind: 'concept' / 'intervention' / 'method'.
    Return dict[target_name -> list of sources cited under that target.]
    """
    target_dir = WIKI_DIR / {"concept": "concepts", "intervention": "interventions", "method": "methods"}[target_kind]
    if not target_dir.is_dir():
        return {}
    by_target = {}
    for tp in target_dir.glob("*.md"):
        text = tp.read_text(encoding="utf-8")
        slugs = set(WIKILINK_RE.findall(text))
        cited = [s for s in sources if s["slug"] in slugs]
        if cited:
            by_target[tp.stem] = cited
    return by_target


def chapter_sources(chapter_pages, sources):
    """For a list of wiki page paths, return source pages they wikilink to."""
    slug_to_source = {s["slug"]: s for s in sources}
    cited = []
    seen = set()
    for page_path in chapter_pages:
        p = Path(page_path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if not p.is_file():
            print(f"  ! page not found: {p}", file=sys.stderr)
            continue
        text = p.read_text(encoding="utf-8")
        for slug in WIKILINK_RE.findall(text):
            if slug in slug_to_source and slug not in seen:
                cited.append(slug_to_source[slug])
                seen.add(slug)
    return cited


def write_grouped(label_to_sources, output_dir, prefix=""):
    output_dir.mkdir(parents=True, exist_ok=True)
    for label, items in label_to_sources.items():
        items_sorted = sorted(items, key=lambda x: (x["fm"].get("year") or 9999, x["slug"]))
        path = output_dir / f"{prefix}{label}.bib"
        with path.open("w", encoding="utf-8") as fh:
            fh.write(f"% {label} ({len(items_sorted)} entries)\n\n")
            fh.write("\n\n".join(make_bibtex(s["slug"], s["fm"]) for s in items_sorted))
            fh.write("\n")
        print(f"  ✓ {path.relative_to(REPO_ROOT)} ({len(items_sorted)} entries)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-concept", action="store_true")
    ap.add_argument("--per-intervention", action="store_true")
    ap.add_argument("--per-method", action="store_true")
    ap.add_argument("--chapters", help="YAML file with explicit chapter mapping")
    ap.add_argument("--output-dir", default="bib", help="Output directory for grouped modes")
    ap.add_argument("--output", "-o", help="Output file for master mode (default stdout)")
    args = ap.parse_args()

    sources = load_sources()
    if not sources:
        sys.exit(f"No sources under {SRC_DIR}")

    output_dir = REPO_ROOT / args.output_dir

    if args.per_concept:
        groups = collect_per_target(sources, "concept")
        write_grouped(groups, output_dir)
    elif args.per_intervention:
        groups = collect_per_target(sources, "intervention")
        write_grouped(groups, output_dir)
    elif args.per_method:
        groups = collect_per_target(sources, "method")
        write_grouped(groups, output_dir)
    elif args.chapters:
        cfg = yaml.safe_load(Path(args.chapters).read_text(encoding="utf-8"))
        groups = {}
        for ch in cfg.get("chapters", []):
            slug = re.sub(r"[^A-Za-z0-9]+", "-", ch["name"]).strip("-").lower()
            groups[slug] = chapter_sources(ch.get("pages", []), sources)
        write_grouped(groups, output_dir)
    else:
        if args.output:
            out = open(args.output, "w", encoding="utf-8")
        else:
            out = sys.stdout
        try:
            write_master(sources, out)
        finally:
            if args.output:
                out.close()
                print(f"  ✓ {Path(args.output).resolve()}", file=sys.stderr)


if __name__ == "__main__":
    main()
