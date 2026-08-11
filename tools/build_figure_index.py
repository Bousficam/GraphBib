#!/usr/bin/env python3
"""Build a searchable figure bank from the images extracted next to each paper.

The image files stay where the OCR put them, in `<slug>_images/`, because the
converted markdown refers to them by the id the OCR assigned (`img-3.jpeg`) and
that corpus is immutable. Renaming the files would break those references, so
the readable title lives here instead: each image gets a caption-derived slug
in the manifest and in the generated index page, which is what makes the bank
browsable without touching the raw corpus.

Pairing rule: an OCR figure is emitted as one image per panel, and the caption
follows the panel group. Each image therefore takes the first `Fig. N` caption
below it, falling back to the nearest one above.

Outputs
  raw/<vault>/papers/<dir>/figures.json   manifest, one record per image
  wiki/<vault>/figures-index.md           index page grouped by source

Usage
  python tools/build_figure_index.py raw/BCINET/papers/ERS [--vault BCINET]
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

CAPTION = re.compile(
    r"^\s*\**\s*(?:Fig(?:ure)?s?\.?)\s*(\d+)\s*([A-Za-z])?\b[.:–-]?\s*(.*)",
    re.I)
IMG_REF = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
STOP = {"the", "a", "an", "of", "and", "for", "in", "on", "to", "with", "from",
        "is", "are", "was", "were", "by", "at", "as", "shows", "showing",
        "shown", "each", "this", "that", "their", "its", "during", "between"}


def dedash(text):
    """Apply the house ban on em and en dashes to OCR'd caption text.

    Captions are copied from the sources, which print ranges with en dashes
    ("15-30 Hz"). The generated page is wiki output and the lint `em_dash`
    check applies to it, so ranges get a plain hyphen and em dashes become a
    spaced hyphen. The manifest keeps the caption as the OCR returned it.
    """
    return text.replace("–", "-").replace("—", " - ")


def slugify(text, max_words=8):
    """Turn a caption into a short, filesystem-safe title.

    Stop words are dropped so the slug carries the informative terms, which is
    what makes a list of figures scannable.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    keep = [w for w in words if w not in STOP and len(w) > 1]
    if not keep:
        keep = words
    return "-".join(keep[:max_words]) or "untitled"


# running heads, page numbers and stray panel letters sit between a panel and
# its caption; they must not stop the search
NOISE_LINE = re.compile(
    r"^\s*($"
    r"|\d{1,4}\s*$"                     # a bare page number
    r"|\(?[A-Za-z][.)]?\s*$"            # a bare panel letter, with or without punctuation
    r"|.{0,80}\b(19|20)\d{2}\b.{0,40}\d{2,4}[-–]\d{2,4}\s*$"  # journal running head
    r")")


def captions_for(md_path):
    """Map each image id in a converted paper to its caption.

    The OCR emits one image per panel, so a multi-panel figure appears as a run
    of consecutive image references followed by a single caption. Matching each
    panel independently would make the early panels of a run miss it, so runs
    are detected first and the caption below the LAST panel is attributed to
    every panel in the run, numbered p1..pN to keep their titles distinct.

    Returns {image_id: {"fig", "panel", "caption"}}.
    """
    if not md_path.is_file():
        return {}
    lines = md_path.read_text(errors="replace").split("\n")

    runs, current = [], []
    for i, line in enumerate(lines):
        m = IMG_REF.search(line)
        if m:
            current.append((i, Path(m.group(1)).name))
        elif current and not NOISE_LINE.match(line):
            runs.append(current)
            current = []
    if current:
        runs.append(current)

    out = {}
    for run in runs:
        last = run[-1][0]
        found = None
        for j in range(last + 1, min(last + 30, len(lines))):
            if IMG_REF.search(lines[j]):
                break  # the next figure starts; this caption is not ours
            c = CAPTION.match(lines[j])
            if c and len(lines[j].strip()) > 15:
                found = c
                break
        if not found:
            continue
        cap = " ".join(found.group(3).split())[:600]
        multi = len(run) > 1
        for n, (_, img_id) in enumerate(run, 1):
            out[img_id] = {
                "fig": found.group(1),
                "panel": (found.group(2) or "").lower(),
                "part": f"p{n}" if multi else "",
                "caption": cap,
            }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("papers_dir", help="Directory holding <slug>.md and <slug>_images/")
    ap.add_argument("--vault", default="BCINET")
    ap.add_argument("--out-index", default=None,
                    help="Index page path (default wiki/<vault>/figures-index.md)")
    args = ap.parse_args()

    root = Path(args.papers_dir).expanduser().resolve()
    repo = Path(__file__).resolve().parent.parent
    index_path = Path(args.out_index) if args.out_index else \
        repo / "wiki" / args.vault / "figures-index.md"

    records = []
    for img_dir in sorted(root.glob("*_images")):
        slug = img_dir.name[:-len("_images")]
        caps = captions_for(root / f"{slug}.md")
        files = [f for f in sorted(img_dir.iterdir())
                 if f.is_file() and not f.name.startswith(".")]

        # A scanned PDF makes the OCR segment page furniture as figures, which
        # can run into the hundreds. Two signals mark that noise: a source whose
        # images are overwhelmingly caption-less, and bytes repeated across the
        # document (a running logo or rule).
        by_size = {}
        for f in files:
            by_size.setdefault(f.stat().st_size, []).append(f.name)
        repeated = {n for names in by_size.values() if len(names) >= 3
                    for n in names}
        bulk_noise = len(files) >= 60 and len(caps) < len(files) * 0.2

        for img in files:
            c = caps.get(img.name, {})
            cap = c.get("caption", "")
            fig, panel, part = c.get("fig", ""), c.get("panel", ""), c.get("part", "")
            label = f"fig-{fig}{panel}" + (f"-{part}" if part else "") \
                if fig else "unlabelled"
            records.append({
                "source": slug,
                "file": str(img.relative_to(repo)),
                "image_id": img.name,
                "figure": label,
                "title_slug": f"{slug}--{label}--{slugify(cap)}" if cap
                              else f"{slug}--{label}",
                "caption": cap,
                "bytes": img.stat().st_size,
                "noise": bool(not cap and (bulk_noise or img.name in repeated)),
            })

    manifest = root / "figures.json"
    manifest.write_text(json.dumps(records, indent=1, ensure_ascii=False),
                        encoding="utf-8")

    # the index lists what is usable; the noise stays in the manifest only
    useful = [r for r in records if not r["noise"]]
    by_source = {}
    for r in useful:
        by_source.setdefault(r["source"], []).append(r)
    captioned = sum(1 for r in useful if r["caption"])
    noisy = len(records) - len(useful)

    lines = [
        "---", "title: Banque de figures", "type: index",
        f"tags:\n  - figures\n  - {args.vault.lower()}", "---", "",
        "# Banque de figures", "",
        f"{len(useful)} images retenues sur {len(by_source)} sources, dont "
        f"{captioned} appariees a une legende. {noisy} images ecartees comme "
        "mobilier de page (PDF scannes ou l'OCR segmente en-tetes et filets) ; "
        "elles restent dans le manifeste avec `noise: true`.", "",
        "Les fichiers restent a cote de leur article, dans "
        "`<slug>_images/`, parce que le markdown converti les designe par "
        "l'identifiant de l'OCR : les renommer casserait le corpus. Le titre "
        "lisible est le `title_slug`. Manifeste complet : "
        f"`{manifest.relative_to(repo)}`.", "",
    ]
    sources_dir = repo / "wiki" / args.vault / "sources"
    for slug in sorted(by_source):
        rows = by_source[slug]
        n_cap = sum(1 for r in rows if r["caption"])
        # only wikilink a slug that has a source page, so the index does not
        # manufacture broken links for raw files never ingested under that name
        has_page = any(sources_dir.rglob(f"{slug}.md")) if sources_dir.is_dir() \
            else False
        title = f"[[{slug}]]" if has_page else f"`{slug}` (pas de page source)"
        lines += [f"## {title}", "",
                  f"{len(rows)} images, {n_cap} legendees.", ""]
        for r in sorted(rows, key=lambda x: (x["figure"], x["image_id"])):
            cap = dedash(r["caption"])
            short = (cap[:170] + "...") if len(cap) > 170 else cap
            lines.append(f"- `{r['title_slug']}`")
            lines.append(f"  ![{r['figure']}]({r['file']})")
            if short:
                lines.append(f"  {r['figure']} : {short}")
        lines.append("")

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"{len(records)} images, {len(by_source)} sources, "
          f"{captioned} avec legende")
    print(f"manifeste : {manifest}")
    print(f"index     : {index_path}")


if __name__ == "__main__":
    main()
