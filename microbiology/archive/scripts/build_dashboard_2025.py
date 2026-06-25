"""Build a self-contained interactive HTML dashboard from the enriched 2025 parquet.

Reads:  cleaned/data2025.parquet      (the 32-column enriched table)
Writes: reports/data2025_dashboard.html

The dashboard:
  - Embeds the data as JSON (no external file dependency).
  - Loads Plotly via CDN.
  - Supports filtering by date range, municipality, municipality type,
    sample type, severity tier, pathogen-only, repeat-offender-only.
  - Re-renders all KPIs, charts and tables on every filter change.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "cleaned" / "data2025.parquet"
OUT_HTML = ROOT / "reports" / "data2025_dashboard.html"


# ---------------------------------------------------------------------------
# Data → compact JSON
# ---------------------------------------------------------------------------
DATA_COLS = [
    "date",          # 0  ISO date string
    "year_month",    # 1
    "quarter",       # 2  int 1..4
    "dow",           # 3  Mon=0..Sun=6
    "sample_type",   # 4
    "chain",         # 5  facility_chain
    "facility",      # 6  facility_name (full)
    "municipality",  # 7
    "mun_type",      # 8
    "valid",         # 9  0 / 1 / null  (raw source signal)
    "failure",       # 10 0 / 1  (composite: is_valid==false OR n_failed_tests>0)
    "pathogen",      # 11 0 / 1
    "severity",      # 12
    "n_failed",      # 13 int
    "ro_count",      # 14 chain_invalid_count_90d
    "failed_tests",  # 15 list[str]
]


def _val(x):
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return x


def build_data(df: pd.DataFrame) -> dict:
    rows: list[list] = []
    for r in df.itertuples(index=False):
        sd = r.sampling_date
        date_str = sd.strftime("%Y-%m-%d") if pd.notna(sd) else None
        valid = None
        if pd.notna(r.is_valid):
            valid = 1 if bool(r.is_valid) else 0
        failure_b = 0
        if pd.notna(r.is_failure):
            failure_b = 1 if bool(r.is_failure) else 0
        pathogen_b = 0
        if pd.notna(r.has_pathogen_failure):
            pathogen_b = 1 if bool(r.has_pathogen_failure) else 0
        failed = list(r.invalid_tests) if r.invalid_tests is not None else []
        rows.append([
            date_str,
            _val(r.year_month),
            int(r.quarter) if pd.notna(r.quarter) else None,
            int(r.day_of_week) if pd.notna(r.day_of_week) else None,
            _val(r.sample_type) or "other",
            _val(r.facility_chain),
            _val(r.facility_name),
            _val(r.municipality),
            _val(r.municipality_type),
            valid,
            failure_b,
            pathogen_b,
            _val(r.severity_tier) or "none",
            int(r.n_failed_tests),
            int(r.chain_invalid_count_90d),
            failed,
        ])
    return {"cols": DATA_COLS, "rows": rows}


def build_facets(df: pd.DataFrame) -> dict:
    months = sorted([m for m in df["year_month"].dropna().unique().tolist()])
    sample_types_order = ["swab", "water", "raw_meat", "cooked_meat_poultry", "dairy",
                          "produce", "sauce_condiment", "sweets_bakery", "beverage",
                          "prepared_meal", "animal_feed", "other"]
    present = set(df["sample_type"])
    sample_types = [s for s in sample_types_order if s in present]
    severity = ["none", "indicator_only", "pathogen", "multi_pathogen"]
    mun_types = [t for t in ["بلدية", "قطاع", "خاص"] if t in set(df["municipality_type"].dropna())]
    municipalities = sorted([m for m in df["municipality"].dropna().unique().tolist()])
    return {
        "months": months,
        "sample_types": sample_types,
        "severity": severity,
        "mun_types": mun_types,
        "municipalities": municipalities,
        "date_min": df["sampling_date"].min().strftime("%Y-%m-%d"),
        "date_max": df["sampling_date"].max().strftime("%Y-%m-%d"),
        "row_count": len(df),
    }


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Riyadh Food-Safety 2025 — Decision Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root {
  --bg: #0b1220;
  --bg-2: #131c30;
  --bg-3: #1c2742;
  --fg: #e8edf6;
  --muted: #95a3bd;
  --line: #29345b;
  --accent: #6aa9ff;
  --good: #34d399;
  --warn: #fbbf24;
  --bad: #f97316;
  --crit: #ef4444;
  --pathogen: #ef4444;
}
* { box-sizing: border-box; }
html, body { background: var(--bg); color: var(--fg); margin: 0;
  font-family: 'Segoe UI', 'Tahoma', system-ui, -apple-system, sans-serif;
  font-size: 14px; }
body { padding: 18px 22px 60px; }
h1 { font-size: 22px; margin: 0 0 6px; font-weight: 600; letter-spacing: 0.2px; }
h2 { font-size: 13px; margin: 0 0 10px; font-weight: 500; color: var(--muted);
  text-transform: uppercase; letter-spacing: 1px; }
.subtitle { color: var(--muted); font-size: 13px; margin-bottom: 18px; }

.filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px; padding: 16px; background: var(--bg-2); border: 1px solid var(--line);
  border-radius: 12px; margin-bottom: 22px; }
.filter-group label { display: block; font-size: 11px; color: var(--muted);
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; font-weight: 500; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 4px 11px; background: var(--bg-3); border: 1px solid var(--line);
  border-radius: 999px; font-size: 12px; cursor: pointer; user-select: none;
  transition: all 0.15s; }
.chip:hover { border-color: var(--accent); }
.chip.active { background: var(--accent); border-color: var(--accent); color: #051121;
  font-weight: 600; }
.toggle-row { display: flex; gap: 12px; flex-wrap: wrap; }
.toggle { padding: 6px 12px; background: var(--bg-3); border: 1px solid var(--line);
  border-radius: 8px; font-size: 12px; cursor: pointer; user-select: none; }
.toggle.active { background: var(--pathogen); border-color: var(--pathogen); color: #fff; }
select { width: 100%; padding: 7px 10px; background: var(--bg-3); color: var(--fg);
  border: 1px solid var(--line); border-radius: 8px; font-size: 13px;
  font-family: inherit; }
select[multiple] { height: 90px; }
input[type=date] { width: 100%; padding: 7px 10px; background: var(--bg-3);
  color: var(--fg); border: 1px solid var(--line); border-radius: 8px;
  font-size: 13px; font-family: inherit; }
.date-range { display: flex; gap: 8px; }
.date-range input { flex: 1; }
.btn { padding: 6px 12px; background: var(--bg-3); border: 1px solid var(--line);
  border-radius: 8px; color: var(--fg); cursor: pointer; font-size: 12px; }
.btn:hover { border-color: var(--accent); }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px; margin-bottom: 22px; }
.kpi { padding: 16px 18px; background: var(--bg-2); border: 1px solid var(--line);
  border-radius: 12px; position: relative; overflow: hidden; }
.kpi::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: var(--accent); }
.kpi.good::before { background: var(--good); }
.kpi.warn::before { background: var(--warn); }
.kpi.bad::before { background: var(--bad); }
.kpi.crit::before { background: var(--crit); }
.kpi .label { color: var(--muted); font-size: 11px; text-transform: uppercase;
  letter-spacing: 1px; margin-bottom: 6px; }
.kpi .value { font-size: 28px; font-weight: 600; line-height: 1; }
.kpi .sub { color: var(--muted); font-size: 11px; margin-top: 4px; }

.grid { display: grid; gap: 16px; grid-template-columns: 1fr 1fr; }
.grid > .full { grid-column: 1 / -1; }
.card { background: var(--bg-2); border: 1px solid var(--line); border-radius: 12px;
  padding: 16px; }
.card .chart { width: 100%; min-height: 280px; }
.card.tall .chart { min-height: 420px; }

@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
}

table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
  cursor: pointer; user-select: none; }
th:hover { color: var(--fg); }
tr.row-bad { background: rgba(239, 68, 68, 0.06); }
tr.row-warn { background: rgba(251, 191, 36, 0.05); }
.bar-inline { display: inline-block; height: 6px; background: var(--accent); border-radius: 3px;
  vertical-align: middle; margin-right: 6px; }
td.r, th.r { text-align: right; }

.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px;
  font-weight: 600; }
.badge.none { background: rgba(52, 211, 153, 0.15); color: var(--good); }
.badge.indicator_only { background: rgba(251, 191, 36, 0.15); color: var(--warn); }
.badge.pathogen { background: rgba(249, 115, 22, 0.15); color: var(--bad); }
.badge.multi_pathogen { background: rgba(239, 68, 68, 0.18); color: var(--crit); }

.muted { color: var(--muted); }
.ar { font-family: 'Tahoma', 'Segoe UI', sans-serif; direction: rtl; unicode-bidi: embed; }

footer { margin-top: 30px; color: var(--muted); font-size: 11px; text-align: center; }
</style>
</head>
<body>

<h1>Riyadh Food-Safety 2025 · Decision Dashboard</h1>
<div class="subtitle" id="subtitle">Loading…</div>

<div class="filters" id="filters">
  <div class="filter-group">
    <label>Date range</label>
    <div class="date-range">
      <input type="date" id="f_date_from">
      <input type="date" id="f_date_to">
    </div>
  </div>
  <div class="filter-group">
    <label>Compliance</label>
    <div class="chips" id="f_compliance"></div>
  </div>
  <div class="filter-group">
    <label>Municipality type</label>
    <div class="chips" id="f_mun_type"></div>
  </div>
  <div class="filter-group">
    <label>Severity</label>
    <div class="chips" id="f_severity"></div>
  </div>
  <div class="filter-group">
    <label>Sample type</label>
    <div class="chips" id="f_sample_type"></div>
  </div>
  <div class="filter-group">
    <label>Municipality</label>
    <select id="f_municipality" multiple></select>
  </div>
  <div class="filter-group">
    <label>Quick toggles</label>
    <div class="toggle-row">
      <div class="toggle" id="t_pathogen">Pathogen only</div>
      <div class="toggle" id="t_repeat">Repeat offender (≥2 non-compliant in 90d)</div>
    </div>
    <div style="margin-top:8px"><button class="btn" id="btn_reset">Reset all filters</button></div>
  </div>
</div>

<div class="kpis" id="kpis"></div>

<div class="grid">
  <div class="card full">
    <h2>Non-compliance rate &amp; pathogen rate over time</h2>
    <div id="chart_trend" class="chart"></div>
  </div>

  <div class="card">
    <h2>Severity tier × sample type</h2>
    <div id="chart_heatmap" class="chart"></div>
  </div>

  <div class="card">
    <h2>Severity breakdown by month</h2>
    <div id="chart_severity_month" class="chart"></div>
  </div>

  <div class="card tall">
    <h2>Top 15 chains by non-compliant samples</h2>
    <div id="chart_chains" class="chart tall"></div>
  </div>

  <div class="card">
    <h2>Non-compliant tests · pathogens vs indicators</h2>
    <div id="chart_tests" class="chart"></div>
  </div>

  <div class="card">
    <h2>Municipality — failure rate &amp; volume</h2>
    <div id="chart_mun" class="chart"></div>
  </div>

  <div class="card">
    <h2>Sampling cadence by day-of-week</h2>
    <div id="chart_dow" class="chart"></div>
  </div>

  <div class="card full">
    <h2>Repeat-offender chains (rolling 90-day non-compliance count, peak)</h2>
    <div id="repeat_table"></div>
  </div>

  <div class="card full">
    <h2>Sample drill-down (filtered rows)</h2>
    <div class="muted" style="margin-bottom:10px">Showing first 200 rows after filters.</div>
    <div id="drilldown_table"></div>
  </div>
</div>

<footer>Generated from cleaned/data2025.parquet — <span id="meta_rows">…</span> rows · last data point <span id="meta_last_date">…</span></footer>

<script>
const PAYLOAD = __PAYLOAD__;
const COLS = {};
PAYLOAD.data.cols.forEach((c, i) => { COLS[c] = i; });
const ROWS = PAYLOAD.data.rows;
const FACETS = PAYLOAD.facets;

const SEVERITY_COLOR = {
  none: '#34d399', indicator_only: '#fbbf24',
  pathogen: '#f97316', multi_pathogen: '#ef4444'
};
const SEVERITY_ORDER = ['none', 'indicator_only', 'pathogen', 'multi_pathogen'];
const PATHOGEN_TESTS = new Set(['السالمونيلا','ايشيريشيا كولاي','استافيلوكوكس اورياس','باصلص سيرز','باسيلس سيريس']);
const DOW_LABELS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: { color: '#e8edf6', family: 'Segoe UI, Tahoma, sans-serif', size: 12 },
  margin: { l: 60, r: 18, t: 20, b: 50 },
  xaxis: { gridcolor: '#29345b', zerolinecolor: '#29345b' },
  yaxis: { gridcolor: '#29345b', zerolinecolor: '#29345b' },
};
const PLOTLY_CONFIG = { displayModeBar: false, responsive: true };

const state = {
  date_from: FACETS.date_min,
  date_to: FACETS.date_max,
  compliance: new Set(),     // {'Compliant','Non-compliant'} — empty = both
  mun_type: new Set(),
  severity: new Set(),
  sample_type: new Set(),
  municipality: new Set(),
  pathogen_only: false,
  repeat_only: false,
};

const COMPLIANCE_OPTIONS = ['Compliant (مطابقة)', 'Non-compliant (غير مطابقة)'];

function buildChips(parentId, items, stateKey) {
  const parent = document.getElementById(parentId);
  parent.innerHTML = '';
  items.forEach(it => {
    const el = document.createElement('div');
    el.className = 'chip';
    el.textContent = it;
    el.dataset.value = it;
    el.addEventListener('click', () => {
      el.classList.toggle('active');
      if (state[stateKey].has(it)) state[stateKey].delete(it);
      else state[stateKey].add(it);
      applyFilters();
    });
    parent.appendChild(el);
  });
}

document.getElementById('f_date_from').value = FACETS.date_min;
document.getElementById('f_date_to').value = FACETS.date_max;
document.getElementById('f_date_from').addEventListener('change', e => {
  state.date_from = e.target.value; applyFilters();
});
document.getElementById('f_date_to').addEventListener('change', e => {
  state.date_to = e.target.value; applyFilters();
});

buildChips('f_compliance',  COMPLIANCE_OPTIONS,  'compliance');
buildChips('f_mun_type',    FACETS.mun_types,    'mun_type');
buildChips('f_severity',    FACETS.severity,     'severity');
buildChips('f_sample_type', FACETS.sample_types, 'sample_type');

const munSel = document.getElementById('f_municipality');
FACETS.municipalities.forEach(m => {
  const o = document.createElement('option'); o.value = m; o.textContent = m;
  munSel.appendChild(o);
});
munSel.addEventListener('change', () => {
  state.municipality = new Set(Array.from(munSel.selectedOptions).map(o => o.value));
  applyFilters();
});

document.getElementById('t_pathogen').addEventListener('click', e => {
  e.target.classList.toggle('active');
  state.pathogen_only = e.target.classList.contains('active');
  applyFilters();
});
document.getElementById('t_repeat').addEventListener('click', e => {
  e.target.classList.toggle('active');
  state.repeat_only = e.target.classList.contains('active');
  applyFilters();
});

document.getElementById('btn_reset').addEventListener('click', () => {
  state.date_from = FACETS.date_min;
  state.date_to = FACETS.date_max;
  state.compliance.clear();
  state.mun_type.clear(); state.severity.clear(); state.sample_type.clear();
  state.municipality.clear();
  state.pathogen_only = false; state.repeat_only = false;
  document.getElementById('f_date_from').value = FACETS.date_min;
  document.getElementById('f_date_to').value = FACETS.date_max;
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  document.querySelectorAll('.toggle').forEach(t => t.classList.remove('active'));
  Array.from(munSel.options).forEach(o => o.selected = false);
  applyFilters();
});

function applyFilters() {
  const cD = COLS.date, cMt = COLS.mun_type, cSv = COLS.severity,
        cSt = COLS.sample_type, cMu = COLS.municipality, cP = COLS.pathogen,
        cRo = COLS.ro_count, cF = COLS.failure;
  const dFrom = state.date_from, dTo = state.date_to;
  const fCo = state.compliance;
  const fMt = state.mun_type, fSv = state.severity, fSt = state.sample_type,
        fMu = state.municipality;
  const pOnly = state.pathogen_only, rOnly = state.repeat_only;

  // Pre-resolve compliance filter — checks against is_failure (the composite).
  const wantCompliant = fCo.has('Compliant (مطابقة)');
  const wantNoncompliant = fCo.has('Non-compliant (غير مطابقة)');
  const complianceActive = fCo.size > 0 && !(wantCompliant && wantNoncompliant);

  const filtered = ROWS.filter(r => {
    if (r[cD] && (r[cD] < dFrom || r[cD] > dTo)) return false;
    if (complianceActive) {
      const isNonCompliant = r[cF] === 1;
      if (wantCompliant && isNonCompliant) return false;
      if (wantNoncompliant && !isNonCompliant) return false;
    }
    if (fMt.size && !fMt.has(r[cMt])) return false;
    if (fSv.size && !fSv.has(r[cSv])) return false;
    if (fSt.size && !fSt.has(r[cSt])) return false;
    if (fMu.size && !fMu.has(r[cMu])) return false;
    if (pOnly && r[cP] !== 1) return false;
    if (rOnly && (r[cRo] || 0) < 2) return false;
    return true;
  });
  renderAll(filtered);
}

function groupBy(rows, keyFn) {
  const m = new Map();
  for (const r of rows) {
    const k = keyFn(r);
    if (k === null || k === undefined) continue;
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(r);
  }
  return m;
}
function pct(num, den) { return den ? 100 * num / den : 0; }

function renderKpis(rows) {
  const total = rows.length;
  const invalid = rows.filter(r => r[COLS.failure] === 1).length;
  const failureRate = pct(invalid, total);
  const pathogen = rows.filter(r => r[COLS.pathogen] === 1).length;
  const pathogenRate = pct(pathogen, total);
  const multiPath = rows.filter(r => r[COLS.severity] === 'multi_pathogen').length;
  const repeatChains = new Set(rows.filter(r => (r[COLS.ro_count] || 0) >= 2).map(r => r[COLS.chain])).size;
  const totalChains = new Set(rows.map(r => r[COLS.chain]).filter(Boolean)).size;
  const avgN = invalid ? rows.filter(r => r[COLS.failure] === 1).reduce((s, r) => s + r[COLS.n_failed], 0) / invalid : 0;

  const cards = [
    { label: 'Samples', value: total.toLocaleString(), sub: totalChains.toLocaleString() + ' unique chains', cls: '' },
    { label: 'Non-compliance rate', value: failureRate.toFixed(1) + '%', sub: invalid.toLocaleString() + ' non-compliant', cls: failureRate > 30 ? 'bad' : (failureRate > 15 ? 'warn' : 'good') },
    { label: 'Pathogen rate', value: pathogenRate.toFixed(1) + '%', sub: pathogen.toLocaleString() + ' samples', cls: pathogenRate > 10 ? 'crit' : (pathogenRate > 5 ? 'bad' : 'warn') },
    { label: 'Multi-pathogen', value: multiPath.toLocaleString(), sub: '≥2 pathogens in same sample', cls: multiPath > 0 ? 'crit' : 'good' },
    { label: 'Repeat-offender chains', value: repeatChains.toLocaleString(), sub: '≥2 non-compliant in any 90d window', cls: 'warn' },
    { label: 'Avg failed tests', value: invalid ? avgN.toFixed(2) : '—', sub: 'per non-compliant sample', cls: '' },
  ];
  document.getElementById('kpis').innerHTML = cards.map(c =>
    '<div class="kpi ' + c.cls + '"><div class="label">' + c.label + '</div><div class="value">' + c.value + '</div><div class="sub">' + c.sub + '</div></div>'
  ).join('');
}

function renderTrend(rows) {
  const byMonth = groupBy(rows, r => r[COLS.year_month]);
  const months = Array.from(byMonth.keys()).sort();
  const failureRate = months.map(m => {
    const list = byMonth.get(m);
    return pct(list.filter(r => r[COLS.failure] === 1).length, list.length);
  });
  const pathogenRate = months.map(m => {
    const list = byMonth.get(m);
    return pct(list.filter(r => r[COLS.pathogen] === 1).length, list.length);
  });
  const volume = months.map(m => byMonth.get(m).length);

  Plotly.react('chart_trend', [
    { type: 'bar', x: months, y: volume, name: 'Sample volume', yaxis: 'y2',
      marker: { color: '#1f2a4a' }, opacity: 0.9, hovertemplate: '%{x} · %{y} samples<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x: months, y: failureRate, name: 'Non-compliance rate %',
      line: { color: '#fbbf24', width: 3 }, marker: { size: 8 }, hovertemplate: '%{x} · %{y:.1f}% non-compliance<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x: months, y: pathogenRate, name: 'Pathogen rate %',
      line: { color: '#ef4444', width: 3, dash: 'dot' }, marker: { size: 8 }, hovertemplate: '%{x} · %{y:.1f}% pathogen<extra></extra>' },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e8edf6', family: 'Segoe UI, Tahoma, sans-serif', size: 12 },
    margin: { l: 50, r: 60, t: 10, b: 50 },
    xaxis: { gridcolor: '#29345b' },
    yaxis: { gridcolor: '#29345b', title: '% of samples', rangemode: 'tozero' },
    yaxis2: { overlaying: 'y', side: 'right', title: 'volume', showgrid: false, rangemode: 'tozero', gridcolor: 'rgba(0,0,0,0)' },
    legend: { orientation: 'h', y: 1.15 },
    hovermode: 'x unified',
  }, PLOTLY_CONFIG);
}

function renderHeatmap(rows) {
  const types = FACETS.sample_types;
  const z = SEVERITY_ORDER.map(sev =>
    types.map(t => rows.filter(r => r[COLS.severity] === sev && r[COLS.sample_type] === t).length)
  );
  Plotly.react('chart_heatmap', [{
    type: 'heatmap', x: types, y: SEVERITY_ORDER, z: z,
    colorscale: [[0, '#101931'], [0.3, '#1f2a4a'], [0.6, '#f59e0b'], [1, '#ef4444']],
    showscale: true, hovertemplate: '%{x} · %{y}: %{z} samples<extra></extra>',
  }], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e8edf6', size: 12 },
    margin: { l: 130, r: 18, t: 10, b: 90 },
    xaxis: { tickangle: -30 },
  }, PLOTLY_CONFIG);
}

function renderSeverityMonth(rows) {
  const byMonth = groupBy(rows, r => r[COLS.year_month]);
  const months = Array.from(byMonth.keys()).sort();
  const traces = SEVERITY_ORDER.map(sev => ({
    type: 'bar', name: sev,
    x: months,
    y: months.map(m => byMonth.get(m).filter(r => r[COLS.severity] === sev).length),
    marker: { color: SEVERITY_COLOR[sev] },
    hovertemplate: '%{x} · ' + sev + ': %{y}<extra></extra>',
  }));
  Plotly.react('chart_severity_month', traces, {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e8edf6', size: 12 },
    barmode: 'stack',
    legend: { orientation: 'h', y: 1.15 },
    margin: { l: 50, r: 18, t: 10, b: 50 },
    xaxis: { gridcolor: '#29345b' }, yaxis: { gridcolor: '#29345b' },
  }, PLOTLY_CONFIG);
}

function renderChains(rows) {
  const byChain = groupBy(rows.filter(r => r[COLS.chain]), r => r[COLS.chain]);
  const stats = [];
  for (const [chain, list] of byChain) {
    const total = list.length;
    const inv = list.filter(r => r[COLS.failure] === 1).length;
    if (inv === 0) continue;
    const path = list.filter(r => r[COLS.pathogen] === 1).length;
    const indicatorOnly = Math.max(0, inv - path);
    stats.push({ chain, total, inv, path, indicatorOnly, rate: pct(inv, total) });
  }
  stats.sort((a, b) => b.inv - a.inv);
  const top = stats.slice(0, 15).reverse();

  Plotly.react('chart_chains', [
    { type: 'bar', orientation: 'h',
      y: top.map(s => s.chain.length > 35 ? s.chain.slice(0, 33) + '…' : s.chain),
      x: top.map(s => s.indicatorOnly), name: 'Indicator-only non-compliance',
      marker: { color: '#fbbf24' },
      customdata: top.map(s => [s.total, s.rate.toFixed(1)]),
      hovertemplate: '<b>%{y}</b><br>%{x} indicator-only non-compliance (of %{customdata[0]} samples · %{customdata[1]}% non-compliance)<extra></extra>',
    },
    { type: 'bar', orientation: 'h',
      y: top.map(s => s.chain.length > 35 ? s.chain.slice(0, 33) + '…' : s.chain),
      x: top.map(s => s.path), name: 'Pathogen non-compliance',
      marker: { color: '#ef4444' },
      hovertemplate: '<b>%{y}</b><br>%{x} pathogen non-compliance<extra></extra>',
    },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e8edf6', size: 12 },
    barmode: 'stack',
    margin: { l: 240, r: 18, t: 10, b: 40 },
    xaxis: { gridcolor: '#29345b' }, yaxis: { automargin: true, gridcolor: '#29345b' },
    legend: { orientation: 'h', y: 1.08 },
  }, PLOTLY_CONFIG);
}

function renderTests(rows) {
  const counts = new Map();
  for (const r of rows) {
    for (const t of r[COLS.failed_tests]) {
      counts.set(t, (counts.get(t) || 0) + 1);
    }
  }
  const items = Array.from(counts.entries()).map(([t, n]) => ({
    test: t, count: n, kind: PATHOGEN_TESTS.has(t) ? 'pathogen' : 'indicator',
  }));
  items.sort((a, b) => a.count - b.count);
  Plotly.react('chart_tests', [{
    type: 'bar', orientation: 'h',
    y: items.map(i => i.test), x: items.map(i => i.count),
    marker: { color: items.map(i => i.kind === 'pathogen' ? '#ef4444' : '#fbbf24') },
    hovertemplate: '<b>%{y}</b>: %{x}<extra></extra>',
  }], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e8edf6', size: 12 },
    margin: { l: 170, r: 18, t: 10, b: 40 },
    xaxis: { gridcolor: '#29345b' }, yaxis: { automargin: true, gridcolor: '#29345b' },
  }, PLOTLY_CONFIG);
}

function renderMunicipality(rows) {
  const byMun = groupBy(rows.filter(r => r[COLS.municipality]), r => r[COLS.municipality]);
  const stats = Array.from(byMun.entries()).map(([m, list]) => {
    const inv = list.filter(r => r[COLS.failure] === 1).length;
    return { mun: m, total: list.length, inv, rate: pct(inv, list.length) };
  });
  stats.sort((a, b) => b.total - a.total);

  Plotly.react('chart_mun', [
    { type: 'bar', x: stats.map(s => s.mun), y: stats.map(s => s.total),
      name: 'Sample volume', marker: { color: '#1f2a4a' },
      hovertemplate: '<b>%{x}</b>: %{y} samples<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x: stats.map(s => s.mun),
      y: stats.map(s => s.rate), name: 'Non-compliance rate %', yaxis: 'y2',
      line: { color: '#f97316', width: 3 }, marker: { size: 9 },
      hovertemplate: '<b>%{x}</b>: %{y:.1f}% non-compliance<extra></extra>' },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e8edf6', size: 12 },
    xaxis: { tickangle: -25, gridcolor: '#29345b' },
    yaxis: { gridcolor: '#29345b', title: 'volume' },
    yaxis2: { overlaying: 'y', side: 'right', title: '% non-compliance', showgrid: false, rangemode: 'tozero', gridcolor: 'rgba(0,0,0,0)' },
    margin: { l: 50, r: 60, t: 10, b: 90 },
    legend: { orientation: 'h', y: 1.15 },
  }, PLOTLY_CONFIG);
}

function renderDow(rows) {
  const counts = [0, 0, 0, 0, 0, 0, 0];
  const inv = [0, 0, 0, 0, 0, 0, 0];
  for (const r of rows) {
    if (r[COLS.dow] === null) continue;
    counts[r[COLS.dow]]++;
    if (r[COLS.failure] === 1) inv[r[COLS.dow]]++;
  }
  Plotly.react('chart_dow', [
    { type: 'bar', x: DOW_LABELS, y: counts, name: 'Total', marker: { color: '#1f2a4a' },
      hovertemplate: '<b>%{x}</b>: %{y} samples<extra></extra>' },
    { type: 'bar', x: DOW_LABELS, y: inv, name: 'Non-compliant', marker: { color: '#f97316' },
      hovertemplate: '<b>%{x}</b>: %{y} non-compliant<extra></extra>' },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e8edf6', size: 12 },
    barmode: 'group',
    margin: { l: 50, r: 18, t: 10, b: 40 },
    xaxis: { gridcolor: '#29345b' }, yaxis: { gridcolor: '#29345b' },
    legend: { orientation: 'h', y: 1.12 },
  }, PLOTLY_CONFIG);
}

function renderRepeatTable(rows) {
  const byChain = groupBy(rows.filter(r => r[COLS.chain]), r => r[COLS.chain]);
  const stats = [];
  for (const [chain, list] of byChain) {
    const total = list.length;
    const inv = list.filter(r => r[COLS.failure] === 1).length;
    const path = list.filter(r => r[COLS.pathogen] === 1).length;
    let peak = 0;
    for (const r of list) peak = Math.max(peak, r[COLS.ro_count] || 0);
    if (peak < 2) continue;
    stats.push({ chain, total, inv, path, peak, rate: pct(inv, total) });
  }
  stats.sort((a, b) => b.peak - a.peak);
  const maxPeak = stats[0]?.peak || 1;

  let html = '<table id="repeat_tbl"><thead><tr>'
    + '<th>Chain</th>'
    + '<th class="r">Samples</th>'
    + '<th class="r">Non-compliant</th>'
    + '<th class="r">Non-compliance %</th>'
    + '<th class="r">Pathogen</th>'
    + '<th class="r">Peak 90d non-compliance</th>'
    + '</tr></thead><tbody>';
  for (const s of stats.slice(0, 50)) {
    const cls = s.peak >= 10 ? 'row-bad' : (s.peak >= 5 ? 'row-warn' : '');
    const barW = Math.max(20, 120 * s.peak / maxPeak);
    html += '<tr class="' + cls + '"><td class="ar">' + escapeHtml(s.chain) + '</td>'
      + '<td class="r">' + s.total + '</td>'
      + '<td class="r">' + s.inv + '</td>'
      + '<td class="r">' + s.rate.toFixed(1) + '%</td>'
      + '<td class="r">' + s.path + '</td>'
      + '<td class="r"><span class="bar-inline" style="width:' + barW + 'px"></span>' + s.peak + '</td>'
      + '</tr>';
  }
  html += '</tbody></table>';
  if (stats.length > 50) html += '<div class="muted" style="margin-top:8px">…+' + (stats.length - 50) + ' more chains</div>';
  if (stats.length === 0) html = '<div class="muted">No repeat-offender chains in current view.</div>';
  document.getElementById('repeat_table').innerHTML = html;
}

function renderDrilldown(rows) {
  const slice = rows.slice(0, 200);
  let html = '<table><thead><tr>'
    + '<th>Date</th><th>Sample type</th><th>Severity</th>'
    + '<th>Chain</th><th>Municipality</th>'
    + '<th>Non-compliant tests</th>'
    + '</tr></thead><tbody>';
  for (const r of slice) {
    const sev = r[COLS.severity];
    html += '<tr><td>' + (r[COLS.date] || '—') + '</td>'
      + '<td>' + r[COLS.sample_type] + '</td>'
      + '<td><span class="badge ' + sev + '">' + sev + '</span></td>'
      + '<td class="ar">' + escapeHtml(r[COLS.chain] || '—') + '</td>'
      + '<td class="ar">' + escapeHtml(r[COLS.municipality] || '—') + '</td>'
      + '<td class="ar">' + escapeHtml((r[COLS.failed_tests] || []).join(' · ') || '—') + '</td>'
      + '</tr>';
  }
  html += '</tbody></table>';
  if (rows.length > 200) html += '<div class="muted" style="margin-top:8px">…+' + (rows.length - 200) + ' more rows</div>';
  document.getElementById('drilldown_table').innerHTML = html;
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function renderAll(rows) {
  document.getElementById('subtitle').textContent =
    rows.length.toLocaleString() + ' samples in view · ' + state.date_from + ' → ' + state.date_to;
  document.getElementById('meta_rows').textContent = FACETS.row_count.toLocaleString();
  document.getElementById('meta_last_date').textContent = FACETS.date_max;

  renderKpis(rows);
  renderTrend(rows);
  renderHeatmap(rows);
  renderSeverityMonth(rows);
  renderChains(rows);
  renderTests(rows);
  renderMunicipality(rows);
  renderDow(rows);
  renderRepeatTable(rows);
  renderDrilldown(rows);
}

applyFilters();
</script>
</body>
</html>
"""


def main() -> None:
    df = pd.read_parquet(PARQUET)
    payload = {
        "data": build_data(df),
        "facets": build_facets(df),
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    html = TEMPLATE.replace("__PAYLOAD__", payload_json)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size / 1024
    print(f"wrote {OUT_HTML}  ({size_kb:.0f} KB, {len(df)} rows)")


if __name__ == "__main__":
    main()
