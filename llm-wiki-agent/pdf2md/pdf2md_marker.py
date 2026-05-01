#!/usr/bin/env python3
"""Conversion récursive SRC → DST en Markdown via marker-pdf, en miroir d'arborescence.

Idempotent : skippe les .md déjà produits.
Écrit marker.log (texte) et marker_report.json (structuré) à la racine de DST.
"""
import json
import logging
import multiprocessing as mp
import sys
import time
from pathlib import Path

MIN_CHARS = 200


def main():
    from tqdm import tqdm
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    if len(sys.argv) < 3:
        sys.exit("Usage: pdf2md_marker.py SRC DST")

    src = Path(sys.argv[1]).expanduser().resolve()
    dst = Path(sys.argv[2]).expanduser().resolve()
    dst.mkdir(parents=True, exist_ok=True)

    log_path = dst / "marker.log"
    report_path = dst / "marker_report.json"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stderr)],
    )
    log = logging.getLogger("marker")

    log.info("Chargement des modèles marker…")
    converter = PdfConverter(artifact_dict=create_model_dict())

    pdfs = sorted(src.rglob("*.pdf"))
    log.info(f"{len(pdfs)} PDF trouvés sous {src}")

    stats = {"ok": [], "skipped": [], "suspicious": [], "errors": []}

    for pdf in tqdm(pdfs, unit="pdf"):
        rel = pdf.relative_to(src).with_suffix(".md")
        out = dst / rel
        if out.exists():
            stats["skipped"].append(str(rel))
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        img_dir = out.parent / f"{out.stem}_images"
        t0 = time.time()
        try:
            rendered = converter(str(pdf))
            text, _, images = text_from_rendered(rendered)
            if images:
                img_dir.mkdir(exist_ok=True)
                for name, img in images.items():
                    img.save(img_dir / name)
            header = f"---\nsource_pdf: {pdf}\ntitle: {pdf.stem}\nbackend: marker\n---\n\n"
            out.write_text(header + text, encoding="utf-8")
            elapsed = time.time() - t0
            entry = {"pdf": str(rel), "chars": len(text), "sec": round(elapsed, 1)}
            if len(text) < MIN_CHARS:
                stats["suspicious"].append(entry)
                log.warning(f"SUSPECT  {rel}  ({len(text)} chars, {elapsed:.1f}s)")
            else:
                stats["ok"].append(entry)
                log.info(f"OK       {rel}  ({len(text)} chars, {elapsed:.1f}s)")
        except Exception as e:
            stats["errors"].append({"pdf": str(rel), "error": repr(e)})
            log.exception(f"ERREUR   {rel}")

    stats["summary"] = {k: len(v) for k, v in stats.items() if isinstance(v, list)}
    stats["summary"]["total"] = len(pdfs)
    report_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"=== RÉSUMÉ === {stats['summary']}")


if __name__ == "__main__":
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    main()
