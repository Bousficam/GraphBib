#!/usr/bin/env python3
"""Fallback pymupdf4llm pour les PDF en échec/suspects du rapport marker.

Lit DST/marker_report.json, retraite errors + suspicious avec pymupdf4llm,
écrase les MD ciblés. Écrit fallback.log et fallback_report.json dans DST.
"""
import json
import logging
import sys
from pathlib import Path


def main():
    from tqdm import tqdm
    import pymupdf4llm

    if len(sys.argv) < 3:
        sys.exit("Usage: pdf2md_fallback.py SRC DST")

    src = Path(sys.argv[1]).expanduser().resolve()
    dst = Path(sys.argv[2]).expanduser().resolve()
    report_path = dst / "marker_report.json"
    if not report_path.exists():
        sys.exit(f"Pas de rapport marker à {report_path}. Lance d'abord pdf2md_marker.py.")

    log_path = dst / "fallback.log"
    out_report = dst / "fallback_report.json"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stderr)],
    )
    log = logging.getLogger("fallback")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    targets = (
        [{"rel": e["pdf"], "reason": "error"} for e in report.get("errors", [])]
        + [{"rel": s["pdf"], "reason": "suspicious"} for s in report.get("suspicious", [])]
    )
    log.info(
        f"{len(targets)} PDF à retraiter "
        f"({len(report.get('errors', []))} erreurs, "
        f"{len(report.get('suspicious', []))} suspects)"
    )

    stats = {"ok": [], "still_failing": []}

    for t in tqdm(targets, unit="pdf"):
        rel = Path(t["rel"])
        pdf = src / rel.with_suffix(".pdf")
        out = dst / rel
        if not pdf.exists():
            log.warning(f"PDF source introuvable : {pdf}")
            stats["still_failing"].append({"pdf": str(rel), "error": "source PDF missing"})
            continue
        try:
            text = pymupdf4llm.to_markdown(str(pdf))
            out.parent.mkdir(parents=True, exist_ok=True)
            header = (
                f"---\nsource_pdf: {pdf}\ntitle: {pdf.stem}\n"
                f"backend: pymupdf4llm\nfallback_from: {t['reason']}\n---\n\n"
            )
            out.write_text(header + text, encoding="utf-8")
            stats["ok"].append({"pdf": str(rel), "chars": len(text)})
            log.info(f"FALLBACK OK     {rel}  ({len(text)} chars)")
        except Exception as e:
            stats["still_failing"].append({"pdf": str(rel), "error": repr(e)})
            log.exception(f"FALLBACK ÉCHEC  {rel}")

    stats["summary"] = {
        "candidates": len(targets),
        "ok": len(stats["ok"]),
        "still_failing": len(stats["still_failing"]),
    }
    out_report.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"=== RÉSUMÉ === {stats['summary']}")


if __name__ == "__main__":
    main()
