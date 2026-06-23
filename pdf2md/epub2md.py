#!/usr/bin/env python3
"""Conversion récursive SRC → DST en Markdown via pandoc (ou markitdown), en miroir d'arborescence.

Cible les livres académiques au format EPUB (monographies, volumes
édités, handbooks, textbooks). EPUB est un format zip XHTML+CSS+OPF
qui préserve la structure de chapitres mieux qu'un PDF - pandoc en
extrait du Markdown propre avec footnotes, équations, et headings de
chapitre que `pdf2md/split_thesis.py` peut ensuite splitter.

Backend par défaut : pandoc (`apt install pandoc` ou `brew install
pandoc`). Fallback : markitdown (`pip install markitdown`) si pandoc
absent. Le backend retenu est inscrit dans le frontmatter
(`backend: pandoc-epub` ou `markitdown-epub`).

Métadonnées extraites du fichier OPF interne à l'EPUB :
  - dc:title              → title
  - dc:creator (role aut) → authors
  - dc:creator (role edt) → editors
  - dc:identifier ISBN    → isbn
  - dc:publisher          → publisher
  - dc:date publication   → year
  - dc:language           → language

Idempotent : skippe les .md déjà produits. Écrit epub.log (texte) et
epub_report.json (structuré) à la racine de DST.

Usage
=====

    # Conversion simple (default DST = raw/books/)
    python pdf2md/epub2md.py "/path/to/EPUBs"

    # DST explicite
    python pdf2md/epub2md.py "/path/to/EPUBs" raw/books

    # Forcer markitdown même si pandoc est dispo
    python pdf2md/epub2md.py "/path/to/EPUBs" raw/books --engine markitdown

    # Re-convertir les fichiers déjà produits (perd les éditions manuelles)
    python pdf2md/epub2md.py "/path/to/EPUBs" raw/books --force

Aval : pour découper un livre/handbook long en pages-chapitre
ingérables séparément, utiliser :

    python pdf2md/split_thesis.py raw/books/<slug>.md

(le script split_thesis.py est agnostique au type - il découpe par
headings de chapitre et fonctionne tel quel sur les livres).
"""
import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MIN_CHARS = 500  # plus permissif que pdf2md_marker - un chapitre court reste valide

OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
}


def find_opf_path(epub_zip: zipfile.ZipFile) -> str | None:
    """Locate the OPF file by reading META-INF/container.xml."""
    try:
        with epub_zip.open("META-INF/container.xml") as f:
            tree = ET.parse(f)
        rootfile = tree.find(".//container:rootfile", OPF_NS)
        if rootfile is not None:
            return rootfile.get("full-path")
    except (KeyError, ET.ParseError):
        return None
    return None


def parse_opf_metadata(epub_path: Path) -> dict:
    """Extract bibliographic metadata from an EPUB's OPF file.

    Returns a dict suitable for inclusion in the source frontmatter.
    Missing fields are left empty rather than guessed.
    """
    meta: dict = {
        "title": "",
        "authors": [],
        "editors": [],
        "year": "",
        "publisher": "",
        "isbn": "",
        "language": "",
    }
    try:
        with zipfile.ZipFile(epub_path) as z:
            opf_path = find_opf_path(z)
            if not opf_path:
                return meta
            with z.open(opf_path) as f:
                tree = ET.parse(f)
    except (zipfile.BadZipFile, ET.ParseError, KeyError):
        return meta

    root = tree.getroot()

    title_el = root.find(".//dc:title", OPF_NS)
    if title_el is not None and title_el.text:
        meta["title"] = title_el.text.strip()

    for creator in root.findall(".//dc:creator", OPF_NS):
        if not creator.text:
            continue
        name = creator.text.strip()
        role = creator.get("{http://www.idpf.org/2007/opf}role", "aut")
        if role == "edt":
            meta["editors"].append(name)
        else:
            meta["authors"].append(name)

    publisher_el = root.find(".//dc:publisher", OPF_NS)
    if publisher_el is not None and publisher_el.text:
        meta["publisher"] = publisher_el.text.strip()

    lang_el = root.find(".//dc:language", OPF_NS)
    if lang_el is not None and lang_el.text:
        meta["language"] = lang_el.text.strip().lower()[:2]

    for date_el in root.findall(".//dc:date", OPF_NS):
        if not date_el.text:
            continue
        m = re.search(r"\d{4}", date_el.text)
        if m:
            meta["year"] = m.group(0)
            break

    for ident in root.findall(".//dc:identifier", OPF_NS):
        if not ident.text:
            continue
        scheme = ident.get("{http://www.idpf.org/2007/opf}scheme", "").lower()
        text = ident.text.strip()
        if scheme == "isbn" or "isbn" in text.lower():
            digits = re.sub(r"[^0-9X]", "", text.upper())
            if len(digits) in (10, 13):
                meta["isbn"] = digits
                break

    return meta


def yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    parts = []
    for x in items:
        safe = x.replace('"', "'")
        parts.append('"' + safe + '"')
    return "[" + ", ".join(parts) + "]"


def yaml_str(value: str) -> str:
    if not value:
        return '""'
    escaped = value.replace('"', "'")
    return '"' + escaped + '"'


def build_frontmatter(epub_path: Path, meta: dict, backend: str) -> str:
    title = meta["title"] or epub_path.stem
    year = meta["year"] or ""
    authors = yaml_list(meta["authors"])
    editors = yaml_list(meta["editors"])
    publisher = yaml_str(meta["publisher"])
    isbn = yaml_str(meta["isbn"])
    language = meta["language"] or "en"
    year_field = year if year else '""'
    return (
        "---\n"
        f"source_epub: {epub_path}\n"
        f"title: {yaml_str(title)}\n"
        f"authors: {authors}\n"
        f"editors: {editors}\n"
        f"year: {year_field}\n"
        f"publisher: {publisher}\n"
        f"isbn: {isbn}\n"
        f"language: {language}\n"
        f"backend: {backend}\n"
        "tags: [book]\n"
        "type: source\n"
        "---\n\n"
    )


def convert_pandoc(epub_path: Path) -> str:
    """Run pandoc EPUB → GFM markdown. Returns body text (no frontmatter)."""
    result = subprocess.run(
        [
            "pandoc",
            "-f", "epub",
            "-t", "gfm",
            "--wrap=preserve",
            "--markdown-headings=atx",
            str(epub_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def convert_markitdown(epub_path: Path) -> str:
    """Run markitdown EPUB → markdown. Returns body text (no frontmatter)."""
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(str(epub_path))
    return result.text_content


def pick_engine(requested: str | None) -> tuple[str, callable]:
    """Resolve which engine to use. Returns (backend_label, convert_fn)."""
    if requested == "pandoc":
        if not shutil.which("pandoc"):
            sys.exit("pandoc not found in PATH - install with `apt install pandoc` or `brew install pandoc`")
        return ("pandoc-epub", convert_pandoc)
    if requested == "markitdown":
        try:
            import markitdown  # noqa: F401
        except ImportError:
            sys.exit("markitdown not installed - `pip install markitdown`")
        return ("markitdown-epub", convert_markitdown)

    if shutil.which("pandoc"):
        return ("pandoc-epub", convert_pandoc)
    try:
        import markitdown  # noqa: F401
        return ("markitdown-epub", convert_markitdown)
    except ImportError:
        sys.exit(
            "No EPUB converter available. Install one:\n"
            "  - pandoc:    apt install pandoc  /  brew install pandoc\n"
            "  - markitdown: pip install markitdown"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("src", help="Source directory containing .epub files")
    parser.add_argument("dst", nargs="?", default="raw/books", help="Destination directory (default: raw/books)")
    parser.add_argument("--engine", choices=["pandoc", "markitdown"], default=None)
    parser.add_argument("--force", action="store_true", help="Re-convert files even if .md already exists")
    args = parser.parse_args()

    src = Path(args.src).expanduser().resolve()
    dst = Path(args.dst).expanduser().resolve()
    dst.mkdir(parents=True, exist_ok=True)

    log_path = dst / "epub.log"
    report_path = dst / "epub_report.json"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stderr)],
    )
    log = logging.getLogger("epub")

    backend_label, convert_fn = pick_engine(args.engine)
    log.info(f"Engine retained: {backend_label}")

    try:
        from tqdm import tqdm
    except ImportError:
        def tqdm(x, **kw):
            return x

    epubs = sorted(src.rglob("*.epub"))
    log.info(f"{len(epubs)} EPUB trouvés sous {src}")

    stats: dict = {"ok": [], "skipped": [], "suspicious": [], "errors": []}

    for epub in tqdm(epubs, unit="epub"):
        rel = epub.relative_to(src).with_suffix(".md")
        out = dst / rel
        if out.exists() and not args.force:
            stats["skipped"].append(str(rel))
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        try:
            meta = parse_opf_metadata(epub)
            body = convert_fn(epub)
            frontmatter = build_frontmatter(epub, meta, backend_label)
            out.write_text(frontmatter + body, encoding="utf-8")
            elapsed = time.time() - t0
            entry = {
                "epub": str(rel),
                "chars": len(body),
                "sec": round(elapsed, 1),
                "title": meta["title"],
                "isbn": meta["isbn"],
            }
            if len(body) < MIN_CHARS:
                stats["suspicious"].append(entry)
                log.warning(f"SUSPECT  {rel}  ({len(body)} chars, {elapsed:.1f}s)")
            else:
                stats["ok"].append(entry)
                log.info(f"OK       {rel}  ({len(body)} chars, {elapsed:.1f}s)")
        except subprocess.CalledProcessError as e:
            stats["errors"].append({"epub": str(rel), "error": f"pandoc exit {e.returncode}: {e.stderr[:300]}"})
            log.exception(f"ERREUR   {rel}")
        except Exception as e:
            stats["errors"].append({"epub": str(rel), "error": repr(e)})
            log.exception(f"ERREUR   {rel}")

    stats["summary"] = {k: len(v) for k, v in stats.items() if isinstance(v, list)}
    stats["summary"]["total"] = len(epubs)
    stats["summary"]["backend"] = backend_label
    report_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Report → {report_path}")


if __name__ == "__main__":
    main()
