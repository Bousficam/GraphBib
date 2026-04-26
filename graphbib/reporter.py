import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml

from .models import Document

# Palette for suggested clusters
_COLORS = [
    "#6366f1", "#f59e0b", "#10b981", "#ef4444", "#3b82f6",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#84cc16",
]

# ---------------------------------------------------------------------------
# HTML template — __REPORT_DATA__ is replaced at generation time
# ---------------------------------------------------------------------------
_HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GraphBib — Rapport Keywords</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#0f172a;--surf:#1e293b;--surf2:#334155;
  --acc:#6366f1;--acc2:#8b5cf6;
  --txt:#e2e8f0;--muted:#94a3b8;--border:#334155;
  --ok:#10b981;--warn:#f59e0b;--err:#ef4444;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--txt);font-size:14px;line-height:1.6}
a{color:var(--acc);text-decoration:none}
h1{font-size:1.6rem;font-weight:700}
h2{font-size:1.1rem;font-weight:600;margin-bottom:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.wrap{max-width:1280px;margin:0 auto;padding:24px}
/* header */
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;padding-bottom:16px;border-bottom:1px solid var(--border)}
header small{color:var(--muted);font-size:.8rem}
/* stat cards */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:28px}
.card{background:var(--surf);border-radius:10px;padding:16px 20px;border:1px solid var(--border)}
.card .val{font-size:2rem;font-weight:700;color:var(--acc)}
.card .lbl{font-size:.78rem;color:var(--muted);margin-top:2px}
.card .fmt-list{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px}
.badge{font-size:.7rem;padding:2px 7px;border-radius:20px;background:var(--surf2);color:var(--txt)}
/* sections */
section{background:var(--surf);border-radius:12px;padding:20px 24px;margin-bottom:20px;border:1px solid var(--border)}
/* search */
.toolbar{display:flex;gap:10px;margin-bottom:14px;align-items:center}
.toolbar input{flex:1;background:var(--surf2);border:1px solid var(--border);color:var(--txt);border-radius:6px;padding:7px 12px;font-size:.88rem;outline:none}
.toolbar input:focus{border-color:var(--acc)}
.toolbar button,.btn{background:var(--surf2);color:var(--txt);border:1px solid var(--border);border-radius:6px;padding:6px 14px;cursor:pointer;font-size:.82rem;transition:.15s}
.toolbar button:hover,.btn:hover{background:var(--acc);border-color:var(--acc)}
/* chart */
.chart-wrap{position:relative;height:420px;margin-top:8px}
/* table */
table{width:100%;border-collapse:collapse;font-size:.83rem}
th{text-align:left;padding:8px 10px;border-bottom:2px solid var(--border);color:var(--muted);font-weight:600;cursor:pointer;user-select:none;white-space:nowrap}
th:hover{color:var(--txt)}
th .sort-arrow{margin-left:4px;opacity:.4}
th.active .sort-arrow{opacity:1;color:var(--acc)}
td{padding:7px 10px;border-bottom:1px solid var(--border);vertical-align:top}
tr:hover td{background:var(--surf2)}
.kw-tags{display:flex;flex-wrap:wrap;gap:3px;max-width:360px}
.kw-tag{font-size:.68rem;padding:2px 7px;border-radius:20px;background:var(--surf2);color:var(--muted);cursor:pointer;border:1px solid transparent;transition:.1s}
.kw-tag:hover,.kw-tag.active-filter{background:var(--acc);color:#fff;border-color:var(--acc)}
.fmt-pdf{color:#ef4444}.fmt-bib{color:#f59e0b}.fmt-md{color:#10b981}.fmt-txt{color:#94a3b8}
.filter-info{font-size:.8rem;color:var(--warn);margin-bottom:8px;min-height:18px}
/* clusters */
.cluster-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.cluster-card{border-radius:10px;padding:14px 16px;border-left:4px solid var(--acc)}
.cluster-card .seed{font-weight:700;font-size:.95rem;margin-bottom:6px}
.cluster-card .count{font-size:.72rem;color:var(--muted);margin-bottom:8px}
.cluster-card .co-kws{display:flex;flex-wrap:wrap;gap:4px}
/* yaml */
.yaml-toolbar{display:flex;gap:8px;margin-bottom:10px}
.yaml-code{background:#0d1117;border:1px solid var(--border);border-radius:8px;padding:16px;font-family:'Cascadia Code','Fira Code',monospace;font-size:.78rem;line-height:1.7;overflow-x:auto;white-space:pre;color:#cdd9e5;max-height:520px;overflow-y:auto}
.y-comment{color:#6e7681}.y-key{color:#79c0ff}.y-val{color:#a5d6ff}.y-str{color:#a8d7a8}.y-section{color:#d2a8ff;font-weight:700}
/* toggle docs */
.toggle-docs-btn{margin-top:8px;background:none;border:1px solid var(--border);color:var(--muted);border-radius:6px;padding:3px 10px;font-size:.72rem;cursor:pointer;width:100%;text-align:left;transition:.15s}
.toggle-docs-btn:hover{border-color:var(--acc);color:var(--acc)}
.toggle-docs-btn.open{color:var(--acc)}
.doc-list{display:none;margin-top:6px;padding-left:14px;list-style:disc;color:var(--muted);font-size:.72rem;line-height:1.7;max-height:200px;overflow-y:auto}
.doc-list.open{display:block}
/* toast */
#toast{position:fixed;bottom:24px;right:24px;background:var(--ok);color:#fff;padding:8px 18px;border-radius:8px;font-size:.82rem;opacity:0;transition:opacity .3s;pointer-events:none}
#toast.show{opacity:1}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>GraphBib &mdash; Rapport Keywords</h1>
      <small>Scanné le <span id="scan-date"></span></small>
    </div>
    <div style="text-align:right">
      <small style="color:var(--muted)">Étape 1/3 — Éditer <code>clusters_template.yaml</code><br>puis lancer <code>graphbib build</code></small>
    </div>
  </header>

  <div class="cards" id="cards"></div>

  <section>
    <h2>Top Keywords — fréquence corpus</h2>
    <div class="toolbar">
      <input id="kw-search" type="text" placeholder="Rechercher un keyword…" oninput="filterChart(this.value)">
      <button onclick="clearKwFilter()">Tout afficher</button>
    </div>
    <div class="chart-wrap"><canvas id="kw-chart"></canvas></div>
  </section>

  <section>
    <h2>Documents</h2>
    <div class="filter-info" id="filter-info"></div>
    <div class="toolbar">
      <input id="doc-search" type="text" placeholder="Rechercher titre / auteur…" oninput="renderTable()">
    </div>
    <table>
      <thead>
        <tr>
          <th onclick="sortBy('title')">Titre <span class="sort-arrow" id="arr-title"></span></th>
          <th onclick="sortBy('format')">Format <span class="sort-arrow" id="arr-format"></span></th>
          <th onclick="sortBy('year')">Année <span class="sort-arrow" id="arr-year"></span></th>
          <th>Auteurs</th>
          <th>Keywords</th>
        </tr>
      </thead>
      <tbody id="doc-tbody"></tbody>
    </table>
  </section>

  <section>
    <h2>Clusters suggérés (pré-analyse)</h2>
    <p style="color:var(--muted);font-size:.8rem;margin-bottom:14px">Basé sur la co-occurrence des top keywords — à valider dans <code>clusters_template.yaml</code></p>
    <div class="cluster-grid" id="cluster-grid"></div>
  </section>

  <section>
    <h2>clusters_template.yaml</h2>
    <p style="color:var(--muted);font-size:.8rem;margin-bottom:12px">
      Éditez ce fichier : renommez les clusters, ajoutez des seeds, rejetez le bruit, puis lancez <code>graphbib build --clusters clusters_template.yaml</code>
    </p>
    <div class="yaml-toolbar">
      <button class="btn" onclick="copyYaml()">📋 Copier</button>
      <a class="btn" id="yaml-dl">⬇ Télécharger</a>
    </div>
    <pre class="yaml-code" id="yaml-code"></pre>
  </section>
</div>
<div id="toast">✓ Copié !</div>

<script>
const D = __REPORT_DATA__;

// ---- cards ----
function renderCards() {
  const s = D.stats;
  const fmtHtml = Object.entries(s.by_format).map(([k,v]) =>
    `<span class="badge">${k} <strong>${v}</strong></span>`).join('');
  document.getElementById('cards').innerHTML = `
    <div class="card"><div class="val">${s.n_docs}</div><div class="lbl">Documents</div>
      <div class="fmt-list">${fmtHtml}</div></div>
    <div class="card"><div class="val">${s.n_keywords}</div><div class="lbl">Keywords uniques</div></div>
    <div class="card"><div class="val">${s.avg_keywords}</div><div class="lbl">Keywords / document</div></div>
    <div class="card"><div class="val">${D.suggested_clusters.length}</div><div class="lbl">Clusters suggérés</div></div>
  `;
}

// ---- chart ----
let chart, activeKw = null;
function renderChart(pairs) {
  const labels = pairs.map(p => p[0]);
  const values = pairs.map(p => p[1]);
  const colors = labels.map(l => l === activeKw ? '#f59e0b' : '#6366f1');
  const ctx = document.getElementById('kw-chart').getContext('2d');
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderRadius: 4, borderSkipped: false }]
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => ` ${ctx.raw} document${ctx.raw > 1 ? 's' : ''}` }
      }},
      scales: {
        x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
        y: { grid: { display: false }, ticks: { color: '#e2e8f0', font: { size: 11 } } }
      },
      onClick: (e, els) => {
        if (!els.length) return;
        const kw = labels[els[0].index];
        activeKw = activeKw === kw ? null : kw;
        filterByKw(activeKw);
        renderChart(pairs);
      }
    }
  });
}
function filterChart(q) {
  const filtered = D.top_keywords.filter(p => p[0].includes(q.toLowerCase())).slice(0, 40);
  renderChart(filtered.length ? filtered : D.top_keywords.slice(0, 40));
}

// ---- table ----
let sortField = 'title', sortAsc = true;
function sortBy(f) {
  sortAsc = sortField === f ? !sortAsc : true;
  sortField = f;
  ['title','format','year'].forEach(k => {
    document.getElementById('arr-'+k).textContent = '';
    document.getElementById('th-'+k)?.classList.remove('active');
  });
  document.getElementById('arr-'+f).textContent = sortAsc ? ' ▲' : ' ▼';
  renderTable();
}
function filterByKw(kw) {
  activeKw = kw;
  document.getElementById('filter-info').textContent =
    kw ? `Filtre actif : "${kw}" — cliquer sur le graphe ou le tag pour désactiver` : '';
  renderTable();
}
function clearKwFilter() { activeKw = null; filterByKw(null); renderChart(D.top_keywords.slice(0,40)); }

function renderTable() {
  const q = (document.getElementById('doc-search').value || '').toLowerCase();
  let docs = D.documents.filter(d => {
    const matchSearch = !q ||
      (d.title||'').toLowerCase().includes(q) ||
      (d.authors||[]).join(' ').toLowerCase().includes(q);
    const matchKw = !activeKw || (d.keywords||[]).includes(activeKw);
    return matchSearch && matchKw;
  });
  docs = [...docs].sort((a, b) => {
    let va = a[sortField]??'', vb = b[sortField]??'';
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    return sortAsc ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0);
  });
  document.getElementById('filter-info').textContent =
    activeKw ? `Filtre : "${activeKw}" — ${docs.length} document(s). Cliquer sur le tag pour désactiver.` : '';
  const rows = docs.map(d => {
    const kws = (d.keywords||[]).slice(0, 8).map(k =>
      `<span class="kw-tag ${k===activeKw?'active-filter':''}" onclick="toggleKwFilter('${k.replace(/'/g,"\\'")}')">
        ${escHtml(k)}</span>`
    ).join('');
    const authors = (d.authors||[]).slice(0,2).join(', ') + (d.authors?.length > 2 ? ' …' : '');
    const yr = d.year || '—';
    const title = escHtml((d.title||'').slice(0, 90)) + (d.title?.length > 90 ? '…' : '');
    return `<tr>
      <td title="${escHtml(d.path)}">${title}</td>
      <td><span class="fmt-${d.format}">${d.format}</span></td>
      <td>${yr}</td>
      <td style="color:var(--muted);font-size:.78rem">${escHtml(authors)}</td>
      <td><div class="kw-tags">${kws}</div></td>
    </tr>`;
  }).join('');
  document.getElementById('doc-tbody').innerHTML = rows || '<tr><td colspan="5" style="color:var(--muted);text-align:center;padding:20px">Aucun document</td></tr>';
}
function toggleKwFilter(kw) {
  activeKw = activeKw === kw ? null : kw;
  filterByKw(activeKw);
  renderChart(D.top_keywords.slice(0,40));
}

// ---- clusters ----
function renderClusters() {
  const html = D.suggested_clusters.map((c, i) => {
    const color = D.colors[i % D.colors.length];
    const coHtml = c.co_keywords.map(k =>
      `<span class="kw-tag" onclick="toggleKwFilter('${k.replace(/'/g,"\\'")}')">
        ${escHtml(k)}</span>`
    ).join('');
    const titles = (c.doc_titles || []);
    const titlesHtml = titles.map(t => `<li>${escHtml(t)}</li>`).join('');
    const moreLabel = titles.length ? `▶ ${c.doc_count} document${c.doc_count>1?'s':''}` : '';
    const uid = 'cl_' + i;
    return `<div class="cluster-card" style="border-color:${color};background:${color}18">
      <div class="seed" style="color:${color}">${escHtml(c.seed)}</div>
      <div class="co-kws">${coHtml}</div>
      ${titles.length ? `
        <button class="toggle-docs-btn" onclick="toggleDocList('${uid}',this)">
          ▶ ${c.doc_count} document${c.doc_count>1?'s':''}
        </button>
        <ul class="doc-list" id="${uid}">${titlesHtml}</ul>` : ''}
    </div>`;
  }).join('');
  document.getElementById('cluster-grid').innerHTML = html || '<p style="color:var(--muted)">Aucun cluster détecté (corpus trop petit)</p>';
}

// ---- yaml ----
function setupYaml() {
  const raw = D.yaml_template;
  document.getElementById('yaml-code').innerHTML = syntaxHighlight(raw);
  const blob = new Blob([raw], {type:'text/yaml'});
  const url = URL.createObjectURL(blob);
  document.getElementById('yaml-dl').href = url;
  document.getElementById('yaml-dl').download = 'clusters_template.yaml';
}
function copyYaml() {
  navigator.clipboard.writeText(D.yaml_template).then(() => {
    const t = document.getElementById('toast');
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2000);
  });
}
function syntaxHighlight(yaml) {
  return escHtml(yaml)
    .replace(/^(#.*)$/gm, '<span class="y-comment">$1</span>')
    .replace(/^(\s*)([\w_]+)(:)/gm, '$1<span class="y-key">$2</span>$3')
    .replace(/"([^"]+)"/g, '<span class="y-str">"$1"</span>');
}
function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function toggleDocList(uid, btn) {
  const list = document.getElementById(uid);
  const open = list.classList.toggle('open');
  btn.classList.toggle('open', open);
  const n = list.querySelectorAll('li').length;
  btn.textContent = (open ? '▼ ' : '▶ ') + n + ' document' + (n>1?'s':'');
}

// ---- init (after all function definitions) ----
document.getElementById('scan-date').textContent = D.scan_date;
renderCards();
renderChart(D.top_keywords.slice(0, 40));
renderTable();
renderClusters();
setupYaml();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------

class HTMLReporter:
    def __init__(self, output_dir: str):
        self.out = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        documents: List[Document],
        global_freq: Dict[str, int],
        suggested_clusters: List[dict],
    ):
        """Write keyword_report.html and clusters_template.yaml. Returns (html_path, yaml_path)."""
        yaml_str = _build_yaml(suggested_clusters, global_freq)

        # Build stats
        by_format: Dict[str, int] = {}
        for d in documents:
            by_format[d.format] = by_format.get(d.format, 0) + 1

        data = {
            "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "stats": {
                "n_docs": len(documents),
                "n_keywords": len(global_freq),
                "avg_keywords": round(
                    sum(len(d.keywords) for d in documents) / max(len(documents), 1), 1
                ),
                "by_format": {f".{k}": v for k, v in by_format.items()},
            },
            "top_keywords": list(global_freq.items())[:60],
            "documents": [d.to_dict() for d in documents],
            "suggested_clusters": suggested_clusters,
            "yaml_template": yaml_str,
            "colors": _COLORS,
        }

        html_path = self.out / "keyword_report.html"
        # Escape </ so PDF text containing </script> can't break the inline script block.
        json_str = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        html_path.write_text(
            _HTML.replace("__REPORT_DATA__", json_str),
            encoding="utf-8",
        )

        yaml_path = self.out / "clusters_template.yaml"
        yaml_path.write_text(yaml_str, encoding="utf-8")

        return html_path, yaml_path


# ---------------------------------------------------------------------------

def _build_yaml(clusters: List[dict], global_freq: Dict[str, int]) -> str:
    lines = [
        "# GraphBib — clusters_template.yaml",
        "# ─────────────────────────────────────────────────────────────",
        "# ÉTAPE 2 : éditez ce fichier, puis lancez :",
        "#   graphbib build --clusters clusters_template.yaml --out ./vault",
        "# ─────────────────────────────────────────────────────────────",
        "",
        "# ── Clusters pré-définis (top-down) ──────────────────────────",
        "# Renommez 'Cluster_N', ajoutez/supprimez des seed_keywords.",
        "predefined_clusters:",
    ]

    for i, c in enumerate(clusters[:8]):
        seeds = [c["seed"]] + c["co_keywords"][:3]
        seeds_yaml = ", ".join(f'"{k}"' for k in seeds)
        color = _COLORS[i % len(_COLORS)]
        lines += [
            f'  - name: "Cluster_{i + 1}"  # ← renommez',
            f"    seed_keywords: [{seeds_yaml}]",
            f'    color: "{color}"',
            f"    # {c['doc_count']} doc(s) contiennent le keyword \"{c['seed']}\"",
            "",
        ]

    # Suggest noise keywords (very high frequency often = noise)
    high_freq = [k for k, v in global_freq.items() if v >= max(3, len(global_freq) // 5)]
    noise_candidates = high_freq[:10] if len(high_freq) > 8 else []

    lines += [
        "",
        "# ── Keywords à rejeter (bruit, artefacts PDF) ────────────────",
        "# Ajoutez ici les tokens non pertinents détectés dans le rapport.",
        "reject_keywords:",
    ]
    if noise_candidates:
        lines.append("  # Candidats fréquents à vérifier :")
        lines.append("  # " + ", ".join(f'"{k}"' for k in noise_candidates[:6]))
    lines += ["  - []  # remplacez par vos tokens bruit", ""]

    lines += [
        "",
        "# ── Synonymes à fusionner ────────────────────────────────────",
        "synonyms:",
        '  # "terme_canonique": ["alias1", "alias2"]',
        '  # "neural network": ["neural net", "deep learning"]',
        "",
        "",
        "# ── Découverte automatique de nouveaux clusters ───────────────",
        "# Activez pour laisser l'algo trouver des groupes non anticipés.",
        "discovery:",
        "  enabled: true",
        "  algorithm: hdbscan   # hdbscan | kmeans",
        "  min_cluster_size: 3  # nb minimum de documents par cluster",
        "  embedding: tfidf     # tfidf | keybert (nécessite sentence-transformers)",
    ]

    return "\n".join(lines) + "\n"
