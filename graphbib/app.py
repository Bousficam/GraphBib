"""
GraphBib — Interface de curation interactive (Streamlit).

Usage:
    streamlit run graphbib/app.py
    graphbib curate --input ./graphbib_output
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

# Allow running as a script even without `pip install -e .`
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st
import yaml

from graphbib.cleaner import KeywordCleaner
from graphbib.models import Document
from graphbib.synthesizer import AutoSynthesizer

# ── Constants ──────────────────────────────────────────────────────────────
_COLORS = [
    "#6366f1", "#f59e0b", "#10b981", "#ef4444", "#3b82f6",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#84cc16",
]

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GraphBib — Curation",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
section[data-testid="stSidebar"] { background: #0f172a; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px 6px 0 0; padding: 6px 16px; }
div[data-testid="metric-container"] { background: #1e293b; border-radius: 8px; padding: 8px 12px; border: 1px solid #334155; }
code { background: #1e293b !important; border-radius: 4px; padding: 1px 6px; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────
def render_sidebar() -> Optional[str]:
    """Returns clusters_path or None if not loaded."""
    with st.sidebar:
        st.title("📚 GraphBib")
        st.caption("Interface de curation — Étape 2")
        st.divider()

        scan_path = st.text_input(
            "scan_results.json",
            value="./graphbib_output/scan_results.json",
            key="scan_path_input",
        )
        clusters_path = st.text_input(
            "clusters_template.yaml",
            value="./graphbib_output/clusters_template.yaml",
            key="clusters_path_input",
        )

        load_btn = st.button("🔄 Charger / Recharger", type="primary", use_container_width=True)

        if load_btn or "docs" not in st.session_state:
            try:
                docs = _load_docs(scan_path)
                raw_yaml = _load_yaml(clusters_path)
                _init_state(docs, raw_yaml)
                st.success(f"✓ {len(docs)} documents chargés")
            except FileNotFoundError as exc:
                st.error(f"Fichier introuvable : {exc}")
                return None
            except Exception as exc:
                st.error(f"Erreur : {exc}")
                return None

        if "docs" not in st.session_state:
            return None

        st.divider()
        docs = st.session_state.docs
        n_active = len(st.session_state.all_kw) - len(st.session_state.rejected)
        col1, col2 = st.columns(2)
        col1.metric("Documents", len(docs))
        col2.metric("Keywords actifs", n_active)
        col1.metric("Clusters", len(st.session_state.clusters))
        col2.metric("Familles", len(st.session_state.families))

        st.divider()
        st.markdown("**Pipeline :**")
        st.code("graphbib scan ./biblio\n# curation ici ← vous êtes ici\ngraphbib build --clusters ...", language="bash")

        return clusters_path


# ── Data loading (cached) ──────────────────────────────────────────────────
@st.cache_data
def _load_docs(path: str) -> List[Document]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Document.from_dict(d) for d in data]


@st.cache_data
def _load_yaml(path: str) -> dict:
    p = Path(path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


# ── State initialisation ───────────────────────────────────────────────────
def _init_state(docs: List[Document], raw: dict) -> None:
    st.session_state.docs = docs

    # Keyword frequencies
    all_kw: Dict[str, int] = {}
    for doc in docs:
        for kw in doc.keywords:
            all_kw[kw] = all_kw.get(kw, 0) + 1
    st.session_state.all_kw = all_kw

    # Rejected keywords
    rejected: Set[str] = set()
    for item in (raw.get("reject_keywords") or []):
        if isinstance(item, list):
            rejected.update(str(x) for x in item if x and str(x) != "[]")
        elif item and str(item) not in ("[]", ""):
            rejected.add(str(item))
    st.session_state.rejected = rejected

    # Synonyms
    st.session_state.synonyms = dict(raw.get("synonyms") or {})

    # Keyword families
    raw_fam = raw.get("keyword_families") or {}
    families = []
    for name, val in raw_fam.items():
        val = val or {}
        families.append({
            "name": str(name),
            "description": str(val.get("description", "")),
            "color": str(val.get("color", _COLORS[len(families) % len(_COLORS)])),
            "includes": list(val.get("includes", [])),
        })
    st.session_state.families = families

    # Predefined clusters
    st.session_state.clusters = list(raw.get("predefined_clusters") or [])

    # Per-cluster synthesis (user descriptions)
    st.session_state.synthesis = {
        c["name"]: c.get("description", "")
        for c in st.session_state.clusters
    }

    # Artifact detection
    cleaner = KeywordCleaner()
    st.session_state.artifacts = cleaner.detect(all_kw, len(docs))


def _active_kw() -> Dict[str, int]:
    return {
        k: v
        for k, v in st.session_state.all_kw.items()
        if k not in st.session_state.rejected
    }


# ── Tab 1 — Keywords & Nettoyage ──────────────────────────────────────────
def tab_keywords() -> None:
    col_art, col_chart = st.columns([1, 2], gap="large")

    with col_art:
        st.subheader("🧹 Artefacts détectés automatiquement")
        confirmed: Dict[str, str] = st.session_state.artifacts.get("confirmed", {})
        suspected: Dict[str, str] = st.session_state.artifacts.get("suspected", {})

        new_confirmed = {k: r for k, r in confirmed.items() if k not in st.session_state.rejected}
        if new_confirmed:
            st.error(f"**{len(new_confirmed)} artefacts confirmés** à supprimer")
            with st.expander("Réviser avant suppression", expanded=True):
                keep = []
                for kw, reason in sorted(new_confirmed.items()):
                    freq = st.session_state.all_kw.get(kw, 0)
                    if not st.checkbox(f"`{kw}` ({freq}×) — {reason}", value=True, key=f"c_{kw}"):
                        keep.append(kw)
            if st.button("🗑 Supprimer artefacts confirmés", type="primary"):
                st.session_state.rejected |= set(new_confirmed.keys()) - set(keep)
                st.rerun()
        else:
            st.success("Aucun artefact confirmé restant")

        st.divider()

        new_suspected = {k: r for k, r in suspected.items() if k not in st.session_state.rejected}
        if new_suspected:
            st.warning(f"**{len(new_suspected)} suspects** — vérification manuelle")
            with st.expander(f"Examiner ({min(len(new_suspected), 40)} affichés)"):
                to_reject = []
                rows = sorted(new_suspected.items(), key=lambda x: st.session_state.all_kw.get(x[0], 0))
                for kw, reason in rows[:40]:
                    freq = st.session_state.all_kw.get(kw, 0)
                    if st.checkbox(f"`{kw}` ({freq}×) — {reason}", value=False, key=f"s_{kw}"):
                        to_reject.append(kw)
                if to_reject and st.button("🗑 Rejeter la sélection"):
                    st.session_state.rejected |= set(to_reject)
                    st.rerun()

        st.divider()
        st.subheader("✏️ Rejet manuel")
        manual = st.text_input("Keywords à rejeter (séparés par virgule)", key="manual_reject")
        if st.button("Rejeter") and manual:
            added = {k.strip().lower() for k in manual.split(",") if k.strip()}
            st.session_state.rejected |= added
            st.rerun()

        if st.session_state.rejected:
            with st.expander(f"Liste rejetés ({len(st.session_state.rejected)})", expanded=False):
                restore = st.multiselect("Restaurer :", sorted(st.session_state.rejected))
                if restore and st.button("↩ Restaurer"):
                    st.session_state.rejected -= set(restore)
                    st.rerun()

    with col_chart:
        st.subheader("📊 Fréquences")
        kws = _active_kw()
        search = st.text_input("Filtrer", placeholder="Rechercher…", key="kw_search")
        if search:
            kws = {k: v for k, v in kws.items() if search.lower() in k}
        top = sorted(kws.items(), key=lambda x: x[1], reverse=True)[:50]
        if top:
            df = pd.DataFrame(top, columns=["Keyword", "Documents"])
            st.bar_chart(df.set_index("Keyword"), height=460)
        else:
            st.info("Aucun keyword correspondant")

    st.divider()
    st.subheader("🔀 Fusionner / Agréger")
    kw_list = sorted(_active_kw().keys())
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        to_merge = st.multiselect("Keywords à fusionner", kw_list, key="merge_sel")
    with c2:
        canonical = st.text_input("Forme canonique", key="merge_canon")
    with c3:
        st.write(""); st.write("")
        if st.button("Fusionner", disabled=not (to_merge and canonical)):
            canon = canonical.lower().strip()
            aliases = [k for k in to_merge if k != canon]
            existing = st.session_state.synonyms.get(canon, [])
            st.session_state.synonyms[canon] = list(set(existing + aliases))
            st.session_state.rejected |= set(aliases)
            st.success(f"`{canon}` ← {aliases}")
            st.rerun()

    if st.session_state.synonyms:
        with st.expander(f"Synonymes ({len(st.session_state.synonyms)})", expanded=False):
            for canon, aliases in list(st.session_state.synonyms.items()):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**`{canon}`** ← {', '.join(f'`{a}`' for a in aliases)}")
                if c2.button("✕", key=f"delsyn_{canon}"):
                    del st.session_state.synonyms[canon]
                    st.rerun()


# ── Tab 2 — Familles / Modules ────────────────────────────────────────────
def tab_families() -> None:
    st.caption(
        "Les **Familles** sont des super-noeuds regroupant des keywords. "
        "Un keyword peut appartenir à plusieurs familles — l'overlap est intentionnel."
    )
    kw_list = sorted(_active_kw().keys())

    if st.button("➕ Nouvelle famille", type="primary"):
        st.session_state.families.append({
            "name": f"Famille_{len(st.session_state.families) + 1}",
            "description": "",
            "color": _COLORS[len(st.session_state.families) % len(_COLORS)],
            "includes": [],
        })
        st.rerun()

    if not st.session_state.families:
        st.info("Aucune famille définie. Les familles forment la hiérarchie supérieure du graphe (modules thématiques).")
        return

    for i, fam in enumerate(st.session_state.families):
        overlap_info = _compute_overlaps(i)
        label = f"**{fam['name']}** — {len(fam['includes'])} keyword(s){' · ↗ overlap' if overlap_info else ''}"
        with st.expander(label, expanded=False):
            c1, c2, c3 = st.columns([2, 1, 0.4])
            with c1:
                new_name = st.text_input("Nom", value=fam["name"], key=f"fn_{i}")
                st.session_state.families[i]["name"] = new_name
            with c2:
                new_color = st.color_picker("Couleur", value=fam["color"], key=f"fc_{i}")
                st.session_state.families[i]["color"] = new_color
            with c3:
                st.write(""); st.write("")
                if st.button("🗑", key=f"delfam_{i}", help="Supprimer"):
                    st.session_state.families.pop(i)
                    st.rerun()

            new_desc = st.text_area("Description", value=fam["description"], key=f"fd_{i}", height=60)
            st.session_state.families[i]["description"] = new_desc

            current = [k for k in fam["includes"] if k in kw_list]
            new_includes = st.multiselect(
                "Keywords membres (overlap inter-familles autorisé)",
                options=kw_list,
                default=current,
                key=f"fi_{i}",
            )
            st.session_state.families[i]["includes"] = new_includes

            if overlap_info:
                st.info("↗ Overlap : " + " | ".join(overlap_info))


def _compute_overlaps(fam_idx: int) -> list[str]:
    fam = st.session_state.families[fam_idx]
    mine = set(fam["includes"])
    result = []
    for j, other in enumerate(st.session_state.families):
        if j == fam_idx:
            continue
        shared = mine & set(other["includes"])
        if shared:
            result.append(f"**{other['name']}** : {', '.join(f'`{k}`' for k in sorted(shared)[:3])}")
    return result


# ── Tab 3 — Clusters ──────────────────────────────────────────────────────
def tab_clusters() -> None:
    docs = st.session_state.docs
    clusters = st.session_state.clusters

    if not clusters:
        st.info("Aucun cluster prédéfini dans le YAML. Lancez d'abord `graphbib scan`.")
        return

    # Overview metrics
    cluster_names = [c["name"] for c in clusters]
    doc_per_cluster: Dict[str, int] = {n: 0 for n in cluster_names}
    unclustered = 0
    for doc in docs:
        assigned = {c["name"] for c in (doc.clusters or [])} & set(cluster_names)
        if assigned:
            for n in assigned:
                doc_per_cluster[n] += 1
        else:
            unclustered += 1

    cols = st.columns(min(len(clusters) + 1, 5))
    for i, name in enumerate(cluster_names):
        cols[i % len(cols)].metric(name, doc_per_cluster[name])
    cols[len(clusters) % len(cols)].metric(
        "Non assignés", unclustered,
        delta=f"{round(100 * unclustered / max(len(docs), 1))}%",
        delta_color="inverse",
    )

    st.divider()

    # Per-cluster expandable document list
    show_n = st.slider("Documents affichés par cluster", 5, 100, 20, step=5)

    for cluster in clusters:
        cname = cluster["name"]
        cdocs = [d for d in docs if any(c["name"] == cname for c in (d.clusters or []))]
        seeds = cluster.get("seed_keywords", [])

        with st.expander(f"**{cname}** — {len(cdocs)} document(s)", expanded=False):
            st.caption("Seeds : " + " · ".join(f"`{k}`" for k in seeds[:8]))

            if not cdocs:
                st.info("Aucun document assigné.")
                continue

            shown = cdocs[:show_n]
            rows = []
            for d in shown:
                matched = next(
                    (c.get("matched_keywords", []) for c in (d.clusters or []) if c["name"] == cname),
                    [],
                )
                score = next(
                    (c.get("score", 0) for c in (d.clusters or []) if c["name"] == cname),
                    0,
                )
                rows.append({
                    "Titre": (d.title or "")[:80],
                    "Format": d.format,
                    "Année": d.year or "—",
                    "Score": round(score, 2),
                    "Mots-clés communs": ", ".join(matched[:5]),
                })
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=1)},
            )
            if len(cdocs) > show_n:
                st.caption(f"… et {len(cdocs) - show_n} autre(s) — augmentez le slider")


# ── Tab 4 — Synthèse ──────────────────────────────────────────────────────
def tab_synthesis() -> None:
    docs = st.session_state.docs
    clusters = st.session_state.clusters
    synthesizer = AutoSynthesizer()

    if not clusters:
        st.info("Aucun cluster défini.")
        return

    st.caption(
        "Synthèse automatique par extraction TF-IDF des phrases les plus représentatives des abstracts. "
        "Modifiez la description personnalisée — elle sera exportée dans le YAML et dans le vault Obsidian."
    )

    for cluster in clusters:
        cname = cluster["name"]
        cdocs = [d for d in docs if any(c["name"] == cname for c in (d.clusters or []))]
        seeds = cluster.get("seed_keywords", [])

        with st.expander(f"**{cname}** ({len(cdocs)} docs)", expanded=True):
            c1, c2 = st.columns(2, gap="large")

            with c1:
                st.markdown("**🤖 Synthèse automatique**")
                auto = synthesizer.synthesize(cdocs, seeds)
                st.info(auto)
                if st.button("↺ Régénérer", key=f"regen_{cname}"):
                    _load_docs.clear()  # force cache clear → re-run
                    st.rerun()

            with c2:
                st.markdown("**✏️ Description personnalisée**")
                val = st.session_state.synthesis.get(cname, "")
                desc = st.text_area(
                    "desc",
                    value=val,
                    height=130,
                    key=f"synth_{cname}",
                    label_visibility="collapsed",
                    placeholder="Décrivez ce cluster en quelques phrases…",
                )
                st.session_state.synthesis[cname] = desc

            st.caption("Keywords seeds : " + " · ".join(f"`{k}`" for k in seeds[:6]))


# ── Tab 5 — Export ────────────────────────────────────────────────────────
def tab_export() -> None:
    yaml_str = _build_yaml()
    col1, col2 = st.columns([3, 1], gap="large")

    with col1:
        st.subheader("Aperçu — clusters_template.yaml")
        st.code(yaml_str, language="yaml", line_numbers=True)

    with col2:
        st.subheader("Actions")
        st.download_button(
            "⬇ Télécharger",
            data=yaml_str,
            file_name="clusters_template.yaml",
            mime="text/yaml",
            use_container_width=True,
        )
        save_path = st.text_input(
            "Sauvegarder vers",
            value=st.session_state.get("clusters_path_input", "./graphbib_output/clusters_template.yaml"),
        )
        if st.button("💾 Sauvegarder", type="primary", use_container_width=True):
            try:
                Path(save_path).write_text(yaml_str, encoding="utf-8")
                st.success(f"✓ {save_path}")
            except Exception as exc:
                st.error(str(exc))

        st.divider()
        st.markdown("**Prochaine étape :**")
        st.code(f"graphbib build \\\n  --clusters {save_path} \\\n  --out ./vault", language="bash")

        st.divider()
        st.subheader("Statistiques")
        kws = _active_kw()
        st.metric("Keywords actifs", len(kws))
        st.metric("Rejetés", len(st.session_state.rejected))
        st.metric("Synonymes", len(st.session_state.synonyms))
        st.metric("Familles", len(st.session_state.families))


def _build_yaml() -> str:
    lines = [
        "# GraphBib — clusters_template.yaml",
        "# Généré par l'interface de curation GraphBib",
        "",
        "reject_keywords:",
    ]
    rejected = sorted(st.session_state.rejected)
    lines += ([f'  - "{k}"' for k in rejected] if rejected else ["  []"])
    lines += ["", "synonyms:"]
    if st.session_state.synonyms:
        for canon, aliases in st.session_state.synonyms.items():
            aliases_str = ", ".join(f'"{a}"' for a in aliases)
            lines.append(f'  "{canon}": [{aliases_str}]')
    else:
        lines += ["  {}"]

    lines += ["", "keyword_families:"]
    if st.session_state.families:
        for fam in st.session_state.families:
            lines.append(f'  "{fam["name"]}":')
            if fam.get("description"):
                lines.append(f'    description: "{fam["description"].replace(chr(34), chr(39))}"')
            lines.append(f'    color: "{fam["color"]}"')
            includes_str = ", ".join(f'"{k}"' for k in fam["includes"])
            lines.append(f"    includes: [{includes_str}]")
    else:
        lines += ["  {}"]

    lines += ["", "predefined_clusters:"]
    for i, cluster in enumerate(st.session_state.clusters):
        cname = cluster["name"]
        seeds_str = ", ".join(f'"{k}"' for k in cluster.get("seed_keywords", []))
        color = cluster.get("color", _COLORS[i % len(_COLORS)])
        lines.append(f'  - name: "{cname}"')
        lines.append(f"    seed_keywords: [{seeds_str}]")
        lines.append(f'    color: "{color}"')
        desc = st.session_state.synthesis.get(cname, "")
        if desc:
            lines.append(f'    description: "{desc.replace(chr(34), chr(39))}"')

    lines += [
        "",
        "discovery:",
        "  enabled: true",
        "  algorithm: hdbscan",
        "  min_cluster_size: 3",
        "  embedding: tfidf",
    ]
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    clusters_path = render_sidebar()

    if clusters_path is None or "docs" not in st.session_state:
        st.title("📚 GraphBib — Interface de Curation")
        st.info("Renseignez les chemins dans la sidebar puis cliquez sur **Charger**.")
        st.code(
            "# Générer d'abord les données :\ngraphbib scan ./ma_biblio --output ./graphbib_output\n\n"
            "# Puis lancer cette interface :\nstreamlit run graphbib/app.py",
            language="bash",
        )
        return

    docs = st.session_state.docs
    st.title(f"📚 GraphBib — Curation · {len(docs)} documents")

    t1, t2, t3, t4, t5 = st.tabs([
        "① Keywords & Nettoyage",
        "② Familles / Modules",
        "③ Clusters",
        "④ Synthèse",
        "⑤ Export",
    ])
    with t1:
        tab_keywords()
    with t2:
        tab_families()
    with t3:
        tab_clusters()
    with t4:
        tab_synthesis()
    with t5:
        tab_export()


main()
