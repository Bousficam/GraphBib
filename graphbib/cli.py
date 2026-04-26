import json
import sys
from pathlib import Path

import click
from tqdm import tqdm

from .extractor import TextExtractor
from .keywords import KeywordExtractor
from .reporter import HTMLReporter
from .scanner import SUPPORTED_FORMATS, FileScanner


def _echo_ok(msg: str) -> None:
    click.echo(click.style("  ✓ ", fg="green") + msg)


def _echo_warn(msg: str) -> None:
    click.echo(click.style("  ⚠ ", fg="yellow") + msg)


def _echo_step(msg: str) -> None:
    click.echo(click.style("\n" + msg, bold=True))


@click.group()
@click.version_option(package_name="graphbib")
def cli() -> None:
    """GraphBib — organise ta bibliographie en graphe de connaissances Obsidian."""


@cli.command()
@click.argument("biblio_path", type=click.Path(exists=True, file_okay=False))
@click.option("--output", "-o", default="./graphbib_output", show_default=True,
              help="Dossier de sortie pour le rapport et le YAML.")
@click.option("--formats", "-f", default=",".join(sorted(SUPPORTED_FORMATS)),
              show_default=True, help="Extensions à scanner (séparées par virgule).")
@click.option("--max-keywords", "-k", default=15, show_default=True,
              help="Nombre maximum de keywords par document.")
@click.option("--top-clusters", default=8, show_default=True,
              help="Nombre de clusters suggérés dans le rapport.")
def scan(biblio_path: str, output: str, formats: str, max_keywords: int, top_clusters: int) -> None:
    """Scanne BIBLIO_PATH, extrait les keywords et génère un rapport HTML interactif."""
    click.echo(click.style("\n══ GraphBib — Scan ══", bold=True, fg="cyan"))

    # ── 1. Scan ──────────────────────────────────────────────────────────────
    fmt_set = {f.strip() if f.strip().startswith(".") else f".{f.strip()}"
               for f in formats.split(",")}
    scanner = FileScanner(biblio_path, fmt_set)

    _echo_step("1/3  Scan des fichiers…")
    paths = scanner.scan()
    stats = scanner.stats(paths)

    if not paths:
        click.echo(click.style("  Aucun fichier trouvé. Vérifiez le dossier et les formats.", fg="red"))
        sys.exit(1)

    for ext, count in sorted(stats["by_format"].items()):
        _echo_ok(f"{count:>3} fichier(s) {ext}")
    _echo_ok(f"{stats['total']} fichier(s) au total")

    # ── 2. Extraction de texte ────────────────────────────────────────────────
    _echo_step("2/3  Extraction de texte…")
    extractor = TextExtractor()
    documents = []
    errors = 0

    for path in tqdm(paths, desc="  Extraction", unit="fichier", leave=False):
        docs = extractor.extract(path)
        for d in docs:
            if d.raw_metadata.get("error"):
                errors += 1
                _echo_warn(f"{d.filename} — {d.raw_metadata['error']}")
            else:
                documents.append(d)

    _echo_ok(f"{len(documents)} document(s) extrait(s)" +
             (f" ({errors} erreur(s) ignorée(s))" if errors else ""))

    if not documents:
        click.echo(click.style("  Aucun document extractible. Abandon.", fg="red"))
        sys.exit(1)

    # ── 3. Keywords TF-IDF ───────────────────────────────────────────────────
    _echo_step("3/3  Extraction des keywords (TF-IDF)…")
    extractor_kw = KeywordExtractor(max_keywords=max_keywords)
    documents, global_freq = extractor_kw.fit_transform(documents)
    suggested = extractor_kw.suggest_clusters(documents, global_freq, top_n=top_clusters)

    _echo_ok(f"Vocabulaire : {len(global_freq)} keywords uniques")
    avg = round(sum(len(d.keywords) for d in documents) / len(documents), 1)
    _echo_ok(f"Moyenne : {avg} keywords / document")

    # ── 4. Sauvegarde JSON + rapport HTML ────────────────────────────────────
    reporter = HTMLReporter(output)
    html_path, yaml_path = reporter.generate(documents, global_freq, suggested)

    json_path = Path(output) / "scan_results.json"
    json_path.write_text(
        json.dumps([d.to_dict() for d in documents], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    click.echo(click.style("\n══ Résultats ══", bold=True, fg="cyan"))
    _echo_ok(f"{html_path}")
    _echo_ok(f"{yaml_path}")
    _echo_ok(f"{json_path}")

    click.echo(click.style("\nProchaine étape :", bold=True))
    click.echo("  1. Ouvrez  " + click.style(str(html_path), fg="cyan") + " dans un navigateur")
    click.echo("  2. Curate  " + click.style("graphbib curate --input " + output, fg="magenta"))
    click.echo("  3. Build   " + click.style("graphbib build --clusters " + str(yaml_path), fg="green"))
    click.echo()


@cli.command()
@click.option("--input", "-i", "input_dir", default="./graphbib_output", show_default=True,
              help="Dossier contenant scan_results.json et clusters_template.yaml.")
def curate(input_dir: str) -> None:
    """Lancer l'interface de curation Streamlit interactive."""
    import subprocess

    app_path = Path(__file__).parent / "app.py"
    scan_json = Path(input_dir) / "scan_results.json"
    clusters_yaml = Path(input_dir) / "clusters_template.yaml"

    if not scan_json.exists():
        click.echo(click.style(f"  ✗ Introuvable : {scan_json}", fg="red"))
        click.echo("  → Lancez d'abord : graphbib scan ./ma_biblio --output " + input_dir)
        raise SystemExit(1)

    click.echo(click.style("\n══ GraphBib — Interface de Curation ══", bold=True, fg="magenta"))
    click.echo(f"  scan_results.json      : {scan_json}")
    click.echo(f"  clusters_template.yaml : {clusters_yaml}")
    click.echo(click.style("\n  Ouverture Streamlit… (Ctrl+C pour quitter)\n", fg="cyan"))

    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
