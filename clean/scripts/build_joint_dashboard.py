"""Joint chemistry + microbiology dashboard.

Reads:
  clean/chemistry/chem_<section>_<year>.parquet × 12
  clean/microbiology/data<year>.parquet × 3 (wide)

Produces:
  clean/reports/joint_dashboard.html

The dashboard's main unit is the **unique physical sample** (year + lowercase
sample_id). Each sample carries:
  - which domain(s) tested it (Chemistry, Microbiology, Both)
  - which chemistry sections (aflatoxins, heavy_metals, …) tested it
  - the aggregated verdict from each domain (invalid > valid > unknown)
  - failed test / pesticide / pathogen list from each domain

Filters: year, domain (chem-only / micro-only / both), search.
KPIs: total samples, per-domain counts, the 2×2 cross-validity matrix.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risk import compute_per_sample_risk

ROOT       = Path(__file__).resolve().parent.parent
CHEM_DIR   = ROOT / "chemistry"
MICRO_DIR  = ROOT / "microbiology"
OUT_HTML   = ROOT / "reports" / "joint_dashboard.html"


def agg_validity(s: pd.Series):
    """invalid > valid > unknown."""
    if (s == False).any():
        return 0
    if (s == True).any():
        return 1
    return None


def collect_chemistry() -> dict[tuple[int, str], dict]:
    """Map (year, lowercase sample_id) → dict of fields aggregated across sections."""
    by_sample: dict[tuple[int, str], dict] = {}
    for p in sorted(CHEM_DIR.glob("chem_*_*.parquet")):
        m = re.match(r"chem_(.+)_(\d{4})\.parquet$", p.name)
        if not m:
            continue
        section, year = m.group(1), int(m.group(2))
        df = pd.read_parquet(p)
        if "sample_id" not in df.columns:
            continue
        df = df[df["sample_id"].notna()].copy()
        df["_sid"] = df["sample_id"].astype(str).str.lower()
        for _, r in df.iterrows():
            key = (year, r["_sid"])
            slot = by_sample.setdefault(key, {
                "year": year,
                "sid": r["_sid"],
                "sample_name": None,
                "sample_category": None,
                "facility": None,
                "municipality": None,
                "district": None,
                "sector": None,
                "ym": None,
                "chem_sections": set(),
                "chem_valid_votes": [],
                "chem_issues": [],
                "micro_valid_votes": [],
                "micro_issues": [],
            })
            slot["chem_sections"].add(section)
            slot["chem_valid_votes"].append(r.get("is_valid"))
            # Backfill metadata if not yet set
            if not slot["sample_name"] and pd.notna(r.get("sample_name")):
                slot["sample_name"] = r["sample_name"]
            # Prefer canonical category over the raw (lab-typo) category text
            canon = r.get("sample_category_canonical") if "sample_category_canonical" in r.index else None
            if (canon is None or (isinstance(canon, float) and pd.isna(canon))) and pd.notna(r.get("sample_category")):
                canon = r["sample_category"]
            if not slot["sample_category"] and canon is not None and not (isinstance(canon, float) and pd.isna(canon)):
                slot["sample_category"] = canon
            if not slot["facility"] and pd.notna(r.get("facility_name")):
                slot["facility"] = r["facility_name"]
            # Per user direction (2026-06-11): the "municipality" slot in the
            # dashboard payload now holds the SECTOR name (East / Central /
            # North / South / West), not the sub-municipality. Sub-municipality
            # is no longer surfaced in the UI — the parquet still has
            # municipality_canonical for forensics.
            sec_val = r.get("sector") if "sector" in r.index else None
            try:
                if pd.isna(sec_val): sec_val = None
            except Exception:
                pass
            if not slot["municipality"] and sec_val is not None:
                slot["municipality"] = sec_val
            if not slot.get("sector") and sec_val is not None:
                slot["sector"] = sec_val
            if not slot["district"] and pd.notna(r.get("district_name")):
                slot["district"] = r["district_name"]
            if not slot["ym"] and pd.notna(r.get("sheet_year_month")):
                slot["ym"] = r["sheet_year_month"]
            # Issue strings: failed_tests_derived for non-pesticide; pesticide_name + invalid_test for pesticides
            issue = None
            if section == "pesticides":
                if r.get("is_valid") == False and pd.notna(r.get("pesticide_name")):
                    issue = r["pesticide_name"]
            else:
                if pd.notna(r.get("failed_tests_derived")):
                    issue = r["failed_tests_derived"]
                elif r.get("is_valid") == False and pd.notna(r.get("invalid_test")):
                    issue = r["invalid_test"]
            if issue:
                for tok in str(issue).split("|"):
                    tok = tok.strip()
                    if tok:
                        slot["chem_issues"].append(f"[{section}] {tok}")
    return by_sample


def add_microbiology(by_sample: dict):
    """Add microbiology rows. Year 2023 is micro-only."""
    for year in (2023, 2024, 2025):
        p = MICRO_DIR / f"data{year}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "sample_id" not in df.columns:
            continue
        df = df[df["sample_id"].notna()].copy()
        df["_sid"] = df["sample_id"].astype(str).str.lower()
        def _is_false(v):
            try:
                return v is False or (hasattr(v, "__bool__") and not bool(v) and v is not None and not pd.isna(v))
            except Exception:
                return False
        for _, r in df.iterrows():
            key = (year, r["_sid"])
            slot = by_sample.setdefault(key, {
                "year": year,
                "sid": r["_sid"],
                "sample_name": None,
                "sample_category": None,
                "facility": None,
                "municipality": None,
                "district": None,
                "sector": None,
                "ym": None,
                "chem_sections": set(),
                "chem_valid_votes": [],
                "chem_issues": [],
                "micro_valid_votes": [],
                "micro_issues": [],
            })
            iv = r.get("is_valid")
            # Convert pandas NA / pd.BooleanArray scalars to python types
            try:
                if pd.isna(iv): iv = None
                else: iv = bool(iv)
            except Exception:
                pass
            slot["micro_valid_votes"].append(iv)
            if not slot["sample_name"] and pd.notna(r.get("sample_name")):
                slot["sample_name"] = r["sample_name"]
            if not slot["sample_category"] and pd.notna(r.get("category_canonical")):
                slot["sample_category"] = r["category_canonical"]
            # Use facility_chain (or facility_name) when available
            fac = r.get("facility_chain") if "facility_chain" in r.index else None
            try:
                if pd.isna(fac): fac = None
            except Exception: pass
            if fac is None and "facility_name" in r.index:
                fac = r["facility_name"]
                try:
                    if pd.isna(fac): fac = None
                except Exception: pass
            if not slot["facility"] and fac is not None:
                slot["facility"] = fac
            # Sectors-only mode: "municipality" holds the sector name.
            sec_val = r.get("sector") if "sector" in r.index else None
            try:
                if pd.isna(sec_val): sec_val = None
            except Exception:
                pass
            if not slot["municipality"] and sec_val is not None:
                slot["municipality"] = sec_val
            if not slot.get("sector") and sec_val is not None:
                slot["sector"] = sec_val
            if not slot["ym"] and pd.notna(r.get("year_month")):
                slot["ym"] = r["year_month"]
            if iv is False:
                issue = r.get("invalid_tests")
                # invalid_tests in microbio parquet is sometimes a list/array
                if isinstance(issue, (list, tuple)):
                    tokens = [str(x).strip() for x in issue if x is not None]
                elif issue is None:
                    tokens = []
                else:
                    try:
                        if pd.isna(issue): tokens = []
                        else: tokens = [t.strip() for t in str(issue).split("|") if t.strip()]
                    except Exception:
                        tokens = [str(issue).strip()]
                for tok in tokens:
                    if tok:
                        slot["micro_issues"].append(tok)


def aggregate_validity(votes):
    """Apply invalid > valid > unknown across all votes."""
    votes = [v for v in votes if v is not None and not (isinstance(v, float) and pd.isna(v))]
    if any(v == False for v in votes):
        return 0
    if any(v == True for v in votes):
        return 1
    return None


def build_payload(by_sample: dict) -> dict:
    # Compute risk per sample (separate pass over raw parquets)
    risks = compute_per_sample_risk()
    cols = ["year", "sample_id", "sample_name", "category", "facility",
            "municipality", "sector", "district", "year_month",
            "domain",            # 'chem' | 'micro' | 'both'
            "chem_sections",     # comma-separated
            "chem_valid",        # 1 / 0 / null
            "micro_valid",       # 1 / 0 / null
            "chem_issues",       # pipe-joined
            "micro_issues",      # pipe-joined
            "matrix",            # V/V, V/X, X/V, X/X, V/?, ?/V, etc.
            "risk_score",        # 0-100
            "risk_tier",         # None/Low/Medium/High/Critical
            "risk_drivers"]      # pipe-joined top drivers
    rows = []
    for (year, sid), s in by_sample.items():
        cv = aggregate_validity(s["chem_valid_votes"])
        mv = aggregate_validity(s["micro_valid_votes"])
        has_chem = bool(s["chem_sections"])
        has_micro = bool(s["micro_valid_votes"])
        domain = "both" if (has_chem and has_micro) else ("chem" if has_chem else "micro")
        def lbl(v):
            return "V" if v == 1 else ("X" if v == 0 else "?")
        # Matrix: only meaningful for "both"
        matrix = f"{lbl(cv)}/{lbl(mv)}" if domain == "both" else None
        risk = risks.get((year, sid), {"composite": 0.0, "tier": "None", "drivers": []})
        rows.append([
            year,
            sid,
            s["sample_name"],
            s["sample_category"],
            s["facility"],
            s["municipality"],
            s.get("sector"),
            s["district"],
            s["ym"],
            domain,
            "|".join(sorted(s["chem_sections"])) if s["chem_sections"] else None,
            cv, mv,
            "|".join(s["chem_issues"]) if s["chem_issues"] else None,
            "|".join(s["micro_issues"]) if s["micro_issues"] else None,
            matrix,
            risk["composite"],
            risk["tier"],
            "|".join(risk["drivers"]) if risk["drivers"] else None,
        ])
    return {"cols": cols, "rows": rows}


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Riyadh Municipality Lab — R&amp;D · Joint Chemistry × Microbiology</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root { --bg:#f7f8fb; --bg-2:#ffffff; --bg-3:#eef2f7; --fg:#1c2742; --muted:#6b7894;
        --line:#d8dee9; --accent:#3b82f6; --good:#059669; --warn:#d97706;
        --bad:#ea580c; --crit:#dc2626;
        --chem:#7c3aed; --micro:#059669; --both:#d97706;
        --shadow:0 1px 3px rgba(28,39,66,0.06), 0 1px 2px rgba(28,39,66,0.04); }
*{box-sizing:border-box}html,body{background:var(--bg);color:var(--fg);margin:0;
  font-family:'Segoe UI','Tahoma',system-ui,sans-serif;font-size:14px}
body{padding:18px 22px 60px}
h1{font-size:22px;margin:0 0 6px;font-weight:600}
h2{font-size:13px;margin:0 0 10px;font-weight:500;color:var(--muted);
   text-transform:uppercase;letter-spacing:1px}
.subtitle{color:var(--muted);font-size:13px;margin-bottom:18px}
.control-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
  padding:12px 16px;background:var(--bg-2);border:1px solid var(--line);
  border-radius:12px;margin-bottom:14px;box-shadow:var(--shadow)}
.control-label{font-size:11px;color:var(--muted);text-transform:uppercase;
  letter-spacing:1.5px;font-weight:600;margin-right:4px}
.chip{padding:6px 12px;background:var(--bg-3);border:1px solid var(--line);
  border-radius:999px;font-size:12px;cursor:pointer;user-select:none;white-space:nowrap;
  color:var(--fg)}
.chip:hover{border-color:var(--accent);background:#fff}
.chip.active{background:var(--accent);border-color:var(--accent);color:#ffffff;font-weight:600}
.search{flex:1;min-width:200px;padding:6px 12px;background:#fff;
  border:1px solid var(--line);border-radius:8px;color:var(--fg);font-size:13px;
  font-family:inherit}
.search:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(59,130,246,0.1)}
.btn{padding:6px 14px;background:#fff;border:1px solid var(--line);
  border-radius:8px;color:var(--fg);font-size:12px;cursor:pointer;font-family:inherit}
.btn:hover{border-color:var(--accent);background:var(--bg-3)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#ffffff;font-weight:600}
.btn.primary:hover{background:#2563eb;border-color:#2563eb}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:12px;margin-bottom:16px}
.kpi{padding:14px 18px;background:var(--bg-2);border:1px solid var(--line);
  border-radius:12px;position:relative;overflow:hidden;box-shadow:var(--shadow)}
.kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--accent)}
.kpi.good::before{background:var(--good)}.kpi.warn::before{background:var(--warn)}
.kpi.bad::before{background:var(--bad)}.kpi.crit::before{background:var(--crit)}
.kpi.chem::before{background:var(--chem)}.kpi.micro::before{background:var(--micro)}
.kpi.both::before{background:var(--both)}
.kpi .label{color:var(--muted);font-size:11px;text-transform:uppercase;
  letter-spacing:1px;margin-bottom:6px}
.kpi .value{font-size:24px;font-weight:600;line-height:1}
.kpi .sub{color:var(--muted);font-size:11px;margin-top:4px}
.grid{display:grid;gap:14px;grid-template-columns:1fr 1fr}
.grid>.full{grid-column:1/-1}
.card{background:var(--bg-2);border:1px solid var(--line);border-radius:12px;padding:16px;
  box-shadow:var(--shadow)}
.card .chart{width:100%;min-height:280px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:600;
  background:var(--bg-3)}
tbody tr:hover{background:var(--bg-3)}
.muted{color:var(--muted)}
.ar{font-family:'Tahoma','Segoe UI',sans-serif;direction:rtl;unicode-bidi:embed}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600}
.badge.valid{background:#d1fae5;color:#065f46}
.badge.invalid{background:#fee2e2;color:#991b1b}
.badge.unknown{background:#e5e7eb;color:#4b5563}
.badge.chem{background:#ede9fe;color:#6d28d9}
.badge.micro{background:#d1fae5;color:#047857}
.badge.both{background:#fef3c7;color:#92400e}
.badge.risk-none{background:#e5e7eb;color:#4b5563}
.badge.risk-low{background:#dbeafe;color:#1d4ed8}
.badge.risk-medium{background:#fef3c7;color:#92400e}
.badge.risk-high{background:#ffedd5;color:#9a3412}
.badge.risk-critical{background:#fee2e2;color:#991b1b;font-weight:700}
.matrix{display:grid;grid-template-columns:auto repeat(3, 1fr);gap:0;
  border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}
.matrix .mc{padding:14px;text-align:center;border-bottom:1px solid var(--line);
  border-right:1px solid var(--line);background:#fff;cursor:pointer;color:var(--fg)}
.matrix .mc:hover{background:var(--bg-3)}
.matrix .mc.head{background:var(--bg-3);color:var(--muted);font-size:11px;
  text-transform:uppercase;letter-spacing:1px;cursor:default;font-weight:600}
.matrix .mc.head:hover{background:var(--bg-3)}
.matrix .mc-val{font-size:22px;font-weight:600;line-height:1.2}
.matrix .mc-sub{color:var(--muted);font-size:10px;margin-top:4px}
.matrix .mc.both-valid{color:var(--good);background:#ecfdf5}
.matrix .mc.both-invalid{color:var(--crit);background:#fef2f2}
.matrix .mc.disagree{color:var(--warn);background:#fffbeb}
.matrix .mc.both-valid:hover{background:#d1fae5}
.matrix .mc.both-invalid:hover{background:#fee2e2}
.matrix .mc.disagree:hover{background:#fef3c7}
footer{margin-top:30px;color:var(--muted);font-size:11px;text-align:center}
</style>
</head>
<body>

<h1>Riyadh Municipality Lab</h1>
<div class="brand-line" style="margin-top:-4px;margin-bottom:8px;color:#475569;font-size:14px;letter-spacing:0.04em;">Under R&amp;D · Joint Chemistry × Microbiology Dashboard</div>
<div class="subtitle" id="subtitle">Loading…</div>

<div class="kpis" id="kpis"></div>

<!-- Year + domain + search controls -->
<div class="control-row">
  <span class="control-label">Year</span>
  <div id="year-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
  <span class="control-label" style="margin-left:18px">Domain</span>
  <div id="domain-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
</div>

<div class="control-row">
  <span class="control-label">Verdict</span>
  <div id="verdict-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
  <span class="control-label" style="margin-left:18px">Risk</span>
  <div id="risk-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
</div>

<div class="control-row">
  <span class="control-label">Sector</span>
  <div id="sector-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
</div>

<div class="control-row">
  <span class="control-label">Search</span>
  <input type="text" class="search" id="search" placeholder="Sample ID, name, facility, failed test, risk driver…" autocomplete="off">
  <span class="muted" id="filter-status" style="font-size:11px"></span>
  <button class="btn" id="btn-reset">Reset</button>
  <button class="btn primary" id="btn-csv">Download CSV</button>
</div>

<div class="grid">
  <div class="card">
    <h2>Cross-tested samples · validity matrix</h2>
    <div class="muted" style="margin-bottom:10px;font-size:12px">Click any cell to filter the drilldown</div>
    <div class="matrix" id="matrix"></div>
  </div>
  <div class="card">
    <h2>Domain breakdown</h2>
    <div class="chart" id="chart-domain"></div>
  </div>

  <div class="card"><h2>Risk-tier distribution</h2><div class="chart" id="chart-risk"></div></div>
  <div class="card full"><h2>Top 30 highest-risk samples</h2><div id="tbl-top-risk" style="overflow:auto;max-height:480px"></div></div>

  <div class="card"><h2>Monthly volume (filtered)</h2><div class="chart" id="chart-monthly"></div></div>
  <div class="card"><h2>Year-on-year fail rate by domain</h2><div class="chart" id="chart-yoy"></div></div>

  <div class="card full"><h2>Top failed tests · pesticides · pathogens</h2><div class="chart" id="chart-fail"></div></div>

  <div class="card"><h2>Top repeat-offender facilities</h2><div id="tbl-facilities" style="overflow:auto;max-height:400px"></div></div>
  <div class="card"><h2>Sample-category breakdown</h2><div id="tbl-categories" style="overflow:auto;max-height:400px"></div></div>

  <div class="card full">
    <h2>Drilldown · matching samples (invalid first, max 300)</h2>
    <div id="drilldown" style="overflow:auto;max-height:600px"></div>
  </div>
</div>

<footer>Joint dashboard · Chemistry × Microbiology · Riyadh municipality lab data</footer>

<script>
"use strict";

const DATA = __DATA_JSON__;
const COLS = {};
DATA.cols.forEach((c, i) => COLS[c] = i);

let currentYear = "all";
let currentDomain = "all";  // all | chem | micro | both
let currentVerdict = "all";  // all | valid | invalid | unknown
let currentMatrix = null;    // V/V, V/X, X/V, X/X, etc — null if no matrix filter
let currentRisk = "all";     // all | None | Low | Medium | High | Critical
let currentSector = "all";   // all | East | West | North | Central | South
let searchTerm = "";

const RISK_TIERS = ["None","Low","Medium","High","Critical"];
const RISK_COLORS = {"None":"#9ca3af","Low":"#3b82f6","Medium":"#d97706","High":"#ea580c","Critical":"#dc2626"};

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function pct(n, d) { return d > 0 ? (n*100/d).toFixed(1) : '0.0'; }
function lc(x) { return x == null ? '' : String(x).toLowerCase(); }
function overallVerdict(r) {
  // invalid wins (chem invalid OR micro invalid) > valid > unknown
  const cv = r[COLS.chem_valid];
  const mv = r[COLS.micro_valid];
  if (cv === 0 || mv === 0) return 'invalid';
  if (cv === 1 || mv === 1) return 'valid';
  return 'unknown';
}

function filteredRows() {
  let rows = DATA.rows;
  if (currentYear !== 'all') {
    const y = parseInt(currentYear, 10);
    rows = rows.filter(r => r[COLS.year] === y);
  }
  if (currentDomain !== 'all') {
    rows = rows.filter(r => r[COLS.domain] === currentDomain);
  }
  if (currentMatrix) {
    rows = rows.filter(r => r[COLS.matrix] === currentMatrix);
  }
  if (currentVerdict !== 'all') {
    rows = rows.filter(r => overallVerdict(r) === currentVerdict);
  }
  if (currentRisk !== 'all') {
    rows = rows.filter(r => r[COLS.risk_tier] === currentRisk);
  }
  if (currentSector !== 'all') {
    rows = rows.filter(r => r[COLS.sector] === currentSector);
  }
  if (searchTerm) {
    const q = searchTerm;
    rows = rows.filter(r =>
      lc(r[COLS.sample_id]).includes(q)
      || lc(r[COLS.sample_name]).includes(q)
      || lc(r[COLS.facility]).includes(q)
      || lc(r[COLS.municipality]).includes(q)
      || lc(r[COLS.category]).includes(q)
      || lc(r[COLS.chem_issues]).includes(q)
      || lc(r[COLS.micro_issues]).includes(q)
      || lc(r[COLS.risk_drivers]).includes(q)
    );
  }
  return rows;
}

function renderYearBar() {
  const wrap = document.getElementById('year-chips');
  wrap.innerHTML = '';
  const yearCounts = {};
  DATA.rows.forEach(r => { yearCounts[r[COLS.year]] = (yearCounts[r[COLS.year]]||0)+1; });
  const yrs = Object.keys(yearCounts).sort();
  const opts = [['all', `All (${DATA.rows.length.toLocaleString()})`]];
  yrs.forEach(y => opts.push([y, `${y} (${yearCounts[y].toLocaleString()})`]));
  opts.forEach(([key, label]) => {
    const c = document.createElement('div');
    c.className = 'chip' + (key === currentYear ? ' active' : '');
    c.textContent = label;
    c.onclick = () => { currentYear = key; currentMatrix = null; renderAll(); };
    wrap.appendChild(c);
  });
}

function renderDomainBar() {
  const wrap = document.getElementById('domain-chips');
  wrap.innerHTML = '';
  const counts = {chem:0, micro:0, both:0};
  DATA.rows.forEach(r => { counts[r[COLS.domain]]++; });
  const opts = [
    ['all',   `All (${(counts.chem+counts.micro+counts.both).toLocaleString()})`],
    ['chem',  `Chemistry only (${counts.chem.toLocaleString()})`],
    ['micro', `Microbiology only (${counts.micro.toLocaleString()})`],
    ['both',  `Tested in BOTH (${counts.both.toLocaleString()})`],
  ];
  opts.forEach(([key, label]) => {
    const c = document.createElement('div');
    c.className = 'chip' + (key === currentDomain ? ' active' : '');
    c.textContent = label;
    c.onclick = () => { currentDomain = key; currentMatrix = null; renderAll(); };
    wrap.appendChild(c);
  });
}

function renderVerdictBar() {
  const wrap = document.getElementById('verdict-chips');
  wrap.innerHTML = '';
  ['all','valid','invalid','unknown'].forEach(key => {
    const c = document.createElement('div');
    c.className = 'chip' + (key === currentVerdict ? ' active' : '');
    c.textContent = key.charAt(0).toUpperCase() + key.slice(1);
    c.onclick = () => { currentVerdict = key; renderAll(); };
    wrap.appendChild(c);
  });
}

function renderSectorBar() {
  const wrap = document.getElementById('sector-chips');
  wrap.innerHTML = '';
  const counts = {all:0, East:0, Central:0, South:0, West:0, North:0};
  DATA.rows.forEach(r => {
    counts.all++;
    if (r[COLS.sector]) counts[r[COLS.sector]] = (counts[r[COLS.sector]]||0) + 1;
  });
  const opts = [
    ['all',     `All (${counts.all.toLocaleString()})`],
    ['East',    `East (${counts.East.toLocaleString()})`],
    ['Central', `Central (${counts.Central.toLocaleString()})`],
    ['South',   `South (${counts.South.toLocaleString()})`],
    ['West',    `West (${counts.West.toLocaleString()})`],
    ['North',   `North (${counts.North.toLocaleString()})`],
  ];
  opts.forEach(([key, label]) => {
    const c = document.createElement('div');
    c.className = 'chip' + (key === currentSector ? ' active' : '');
    c.textContent = label;
    c.onclick = () => { currentSector = key; renderAll(); };
    wrap.appendChild(c);
  });
}

function renderRiskBar() {
  const wrap = document.getElementById('risk-chips');
  wrap.innerHTML = '';
  // Count per tier
  const counts = {all:0};
  RISK_TIERS.forEach(t => counts[t] = 0);
  DATA.rows.forEach(r => {
    counts.all++;
    counts[r[COLS.risk_tier]] = (counts[r[COLS.risk_tier]]||0) + 1;
  });
  const opts = [['all', `All (${counts.all.toLocaleString()})`]];
  RISK_TIERS.forEach(t => opts.push([t, `${t} (${(counts[t]||0).toLocaleString()})`]));
  opts.forEach(([key, label]) => {
    const c = document.createElement('div');
    c.className = 'chip' + (key === currentRisk ? ' active' : '');
    c.textContent = label;
    c.onclick = () => { currentRisk = key; renderAll(); };
    if (key !== 'all' && key === currentRisk) {
      c.style.background = RISK_COLORS[key];
      c.style.borderColor = RISK_COLORS[key];
      c.style.color = '#fff';
    }
    wrap.appendChild(c);
  });
}

function renderKpis() {
  const rows = filteredRows();
  const total = rows.length;
  const chem = rows.filter(r => r[COLS.domain] === 'chem').length;
  const micro = rows.filter(r => r[COLS.domain] === 'micro').length;
  const both = rows.filter(r => r[COLS.domain] === 'both').length;
  const invalid = rows.filter(r => overallVerdict(r) === 'invalid').length;
  const valid = rows.filter(r => overallVerdict(r) === 'valid').length;
  const critical = rows.filter(r => r[COLS.risk_tier] === 'Critical').length;
  const highOrCrit = rows.filter(r => r[COLS.risk_tier] === 'High' || r[COLS.risk_tier] === 'Critical').length;
  const failPct = pct(invalid, total);
  const cls = failPct >= 15 ? 'crit' : failPct >= 7 ? 'bad' : failPct >= 3 ? 'warn' : 'good';
  const critCls = critical > 0 ? 'crit' : (highOrCrit > 0 ? 'bad' : 'good');
  document.getElementById('kpis').innerHTML = `
    <div class="kpi"><div class="label">Unique samples (filtered)</div><div class="value">${total.toLocaleString()}</div><div class="sub">of ${DATA.rows.length.toLocaleString()} total</div></div>
    <div class="kpi chem"><div class="label">Chemistry only</div><div class="value">${chem.toLocaleString()}</div><div class="sub">${pct(chem,total)}%</div></div>
    <div class="kpi micro"><div class="label">Microbiology only</div><div class="value">${micro.toLocaleString()}</div><div class="sub">${pct(micro,total)}%</div></div>
    <div class="kpi both"><div class="label">Tested in BOTH</div><div class="value">${both.toLocaleString()}</div><div class="sub">${pct(both,total)}%</div></div>
    <div class="kpi ${cls}"><div class="label">Non-compliant (any panel)</div><div class="value">${invalid.toLocaleString()}</div><div class="sub">${failPct}%</div></div>
    <div class="kpi ${critCls}"><div class="label">High / Critical risk</div><div class="value">${highOrCrit.toLocaleString()}</div><div class="sub">${critical.toLocaleString()} critical · ${pct(highOrCrit,total)}%</div></div>
  `;
}

function renderMatrix() {
  // 2×2 of chem outcome × micro outcome for the "both" subset, ignoring year/domain filters for the matrix display
  // BUT honor the year filter so it stays consistent
  let baseRows = DATA.rows.filter(r => r[COLS.domain] === 'both');
  if (currentYear !== 'all') {
    const y = parseInt(currentYear, 10);
    baseRows = baseRows.filter(r => r[COLS.year] === y);
  }
  const counts = {};
  baseRows.forEach(r => {
    const k = r[COLS.matrix];
    if (k) counts[k] = (counts[k]||0) + 1;
  });
  function cell(label, key, cls, sub) {
    const n = counts[key] || 0;
    const active = currentMatrix === key ? ' style="outline:2px solid var(--accent);outline-offset:-2px"' : '';
    return `<div class="mc ${cls}" onclick="filterMatrix(${JSON.stringify(key)})"${active}>
      <div class="mc-val">${n.toLocaleString()}</div>
      <div class="mc-sub">${sub}</div>
    </div>`;
  }
  const m = document.getElementById('matrix');
  m.innerHTML = `
    <div class="mc head"></div>
    <div class="mc head">Micro Compliant</div>
    <div class="mc head">Micro Non-compliant</div>
    <div class="mc head">Micro Unknown</div>
    <div class="mc head">Chem Compliant</div>
    ${cell('V/V','V/V','both-valid','both pass')}
    ${cell('V/X','V/X','disagree','chem ✓ · micro ✗')}
    ${cell('V/?','V/?','','chem ✓ · micro ?')}
    <div class="mc head">Chem Non-compliant</div>
    ${cell('X/V','X/V','disagree','chem ✗ · micro ✓')}
    ${cell('X/X','X/X','both-invalid','both fail')}
    ${cell('X/?','X/?','','chem ✗ · micro ?')}
    <div class="mc head">Chem Unknown</div>
    ${cell('?/V','?/V','','chem ? · micro ✓')}
    ${cell('?/X','?/X','','chem ? · micro ✗')}
    ${cell('?/?','?/?','','both ?')}
  `;
}

function filterMatrix(key) {
  if (currentMatrix === key) { currentMatrix = null; }
  else {
    currentMatrix = key;
    currentDomain = 'both';
  }
  renderAll();
}

function renderRisk() {
  const rows = filteredRows();
  const counts = {None:0, Low:0, Medium:0, High:0, Critical:0};
  rows.forEach(r => { counts[r[COLS.risk_tier]] = (counts[r[COLS.risk_tier]]||0) + 1; });
  if (!rows.length) {
    Plotly.purge('chart-risk');
    document.getElementById('chart-risk').innerHTML = '<p class="muted">No data.</p>'; return;
  }
  const tiers = RISK_TIERS;
  Plotly.newPlot('chart-risk', [{
    x: tiers, y: tiers.map(t => counts[t]||0),
    type:'bar',
    marker:{color: tiers.map(t => RISK_COLORS[t])},
    text: tiers.map(t => (counts[t]||0).toLocaleString()),
    textposition:'auto',
  }], {paper_bgcolor:'transparent', plot_bgcolor:'transparent',
       font:{color:'#1c2742'}, margin:{t:10,r:10,b:40,l:50}, height:280,
       xaxis:{gridcolor:'#e5e7eb'},
       yaxis:{title:'Samples', gridcolor:'#e5e7eb'}}, {responsive:true, displayModeBar:false});
}

function renderTopRisk() {
  const rows = filteredRows().filter(r => (r[COLS.risk_score]||0) > 0);
  const ordered = rows.slice().sort((a,b) => (b[COLS.risk_score]||0) - (a[COLS.risk_score]||0)).slice(0, 30);
  if (!ordered.length) {
    document.getElementById('tbl-top-risk').innerHTML = '<p class="muted">No risk-bearing samples in current filter.</p>'; return;
  }
  const tr = ordered.map(r => {
    const tier = r[COLS.risk_tier];
    const tierBadge = `<span class="badge risk-${tier.toLowerCase()}">${tier}</span>`;
    return `<tr>
      <td><strong>${(r[COLS.risk_score]||0).toFixed(0)}</strong></td>
      <td>${tierBadge}</td>
      <td>${r[COLS.year]}</td>
      <td>${escapeHtml(r[COLS.sample_id])}</td>
      <td class="ar">${escapeHtml(r[COLS.sample_name])}</td>
      <td>${escapeHtml(r[COLS.category])}</td>
      <td class="ar">${escapeHtml(r[COLS.facility])}</td>
      <td style="max-width:380px;word-break:break-word">${escapeHtml(r[COLS.risk_drivers])}</td>
    </tr>`;
  }).join('');
  document.getElementById('tbl-top-risk').innerHTML = `<table>
    <thead><tr><th>Score</th><th>Tier</th><th>Yr</th><th>Sample ID</th><th>Name</th><th>Category</th><th>Facility</th><th>Top risk drivers</th></tr></thead>
    <tbody>${tr}</tbody></table>`;
}

function renderDomain() {
  const rows = filteredRows();
  const c = {Chemistry:0, Microbiology:0, Both:0};
  rows.forEach(r => {
    const d = r[COLS.domain];
    c[d === 'chem' ? 'Chemistry' : (d === 'micro' ? 'Microbiology' : 'Both')]++;
  });
  if (!rows.length) {
    document.getElementById('chart-domain').innerHTML = '<p class="muted">No data.</p>'; return;
  }
  Plotly.newPlot('chart-domain', [{
    labels: Object.keys(c), values: Object.values(c),
    type: 'pie', hole: 0.55,
    marker: {colors: ['#7c3aed','#059669','#d97706']},
    textinfo:'label+percent', textposition:'outside',
  }], {paper_bgcolor:'transparent', font:{color:'#1c2742'},
       margin:{t:10,r:10,b:10,l:10}, height:280, showlegend:false}, {responsive:true, displayModeBar:false});
}

function renderMonthly() {
  const rows = filteredRows();
  const m = {};
  const yearsSeen = new Set();
  rows.forEach(r => {
    const ym = r[COLS.year_month];
    if (!ym) return;
    if (!m[ym]) m[ym] = {v:0, i:0, u:0};
    const v = overallVerdict(r);
    if (v === 'valid') m[ym].v++;
    else if (v === 'invalid') m[ym].i++;
    else m[ym].u++;
    const yr = r[COLS.year];
    if (yr) yearsSeen.add(yr);
  });
  if (!Object.keys(m).length) {
    Plotly.purge('chart-monthly');
    document.getElementById('chart-monthly').innerHTML = '<p class="muted">No data.</p>'; return;
  }
  // Expand x-axis to all 12 months of each year present so sparse sections
  // (hormones, honey) show empty months as zero instead of collapsing to a
  // few narrow bars.
  const months = [];
  Array.from(yearsSeen).sort().forEach(yr => {
    for (let i = 1; i <= 12; i++) {
      const ym = `${yr}-${String(i).padStart(2, '0')}`;
      months.push(ym);
      if (!m[ym]) m[ym] = {v:0, i:0, u:0};
    }
  });
  Plotly.newPlot('chart-monthly', [
    {x:months, y:months.map(x=>m[x].v), name:'Compliant',     type:'bar', marker:{color:'#059669'}},
    {x:months, y:months.map(x=>m[x].i), name:'Non-compliant', type:'bar', marker:{color:'#dc2626'}},
    {x:months, y:months.map(x=>m[x].u), name:'Unknown', type:'bar', marker:{color:'#9ca3af'}},
  ], {barmode:'stack', paper_bgcolor:'transparent', plot_bgcolor:'transparent',
      font:{color:'#1c2742'}, margin:{t:10,r:10,b:60,l:50}, height:280,
      xaxis:{tickangle:-45, gridcolor:'#e5e7eb'},
      yaxis:{gridcolor:'#e5e7eb'},
      legend:{orientation:'h', y:-0.25}}, {responsive:true, displayModeBar:false});
}

function renderYoY() {
  // Year × domain fail rate
  const acc = {};  // {year: {chem: {t,i}, micro:{t,i}}}
  filteredRows().forEach(r => {
    const y = r[COLS.year];
    if (!acc[y]) acc[y] = {chem:{t:0,i:0}, micro:{t:0,i:0}};
    if (r[COLS.chem_valid] != null) {
      acc[y].chem.t++;
      if (r[COLS.chem_valid] === 0) acc[y].chem.i++;
    }
    if (r[COLS.micro_valid] != null) {
      acc[y].micro.t++;
      if (r[COLS.micro_valid] === 0) acc[y].micro.i++;
    }
  });
  const years = Object.keys(acc).sort();
  const chemPct = years.map(y => acc[y].chem.t ? acc[y].chem.i*100/acc[y].chem.t : 0);
  const microPct = years.map(y => acc[y].micro.t ? acc[y].micro.i*100/acc[y].micro.t : 0);
  if (!years.length) {
    Plotly.purge('chart-yoy');
    document.getElementById('chart-yoy').innerHTML = '<p class="muted">No data.</p>'; return;
  }
  Plotly.newPlot('chart-yoy', [
    {x:years, y:chemPct, name:'Chemistry', type:'bar', marker:{color:'#7c3aed'}, text:chemPct.map(v=>v.toFixed(1)+'%'), textposition:'auto'},
    {x:years, y:microPct, name:'Microbiology', type:'bar', marker:{color:'#059669'}, text:microPct.map(v=>v.toFixed(1)+'%'), textposition:'auto'},
  ], {barmode:'group', paper_bgcolor:'transparent', plot_bgcolor:'transparent',
      font:{color:'#1c2742'}, margin:{t:10,r:10,b:40,l:50}, height:280,
      yaxis:{title:'% invalid samples', rangemode:'tozero', gridcolor:'#e5e7eb'},
      xaxis:{gridcolor:'#e5e7eb'},
      legend:{orientation:'h', y:-0.15}}, {responsive:true, displayModeBar:false});
}

function renderFail() {
  const rows = filteredRows();
  const counts = {};
  rows.forEach(r => {
    if (r[COLS.chem_issues]) {
      String(r[COLS.chem_issues]).split('|').map(s=>s.trim()).filter(Boolean).forEach(t=>{
        counts[t] = (counts[t]||0)+1;
      });
    }
    if (r[COLS.micro_issues]) {
      String(r[COLS.micro_issues]).split('|').map(s=>s.trim()).filter(Boolean).forEach(t=>{
        const k = `[microbio] ${t}`;
        counts[k] = (counts[k]||0)+1;
      });
    }
  });
  const entries = Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,30);
  if (!entries.length) {
    Plotly.purge('chart-fail');
    document.getElementById('chart-fail').innerHTML = '<p class="muted">No failed-test data.</p>'; return;
  }
  Plotly.newPlot('chart-fail', [{
    x: entries.map(e=>e[1]), y: entries.map(e=>e[0]),
    type:'bar', orientation:'h',
    marker:{color: entries.map(e=>e[0].startsWith('[microbio]') ? '#059669' : '#7c3aed')},
    text: entries.map(e=>e[1]), textposition:'auto',
  }], {paper_bgcolor:'transparent', plot_bgcolor:'transparent',
       font:{color:'#1c2742'}, margin:{t:10,r:10,b:30,l:300},
       height: Math.max(280, entries.length*22+50),
       xaxis:{gridcolor:'#e5e7eb'},
       yaxis:{automargin:true, autorange:'reversed'}}, {responsive:true, displayModeBar:false});
}

function renderFacilities() {
  const rows = filteredRows();
  const fac = {};
  rows.forEach(r => {
    const f = r[COLS.facility];
    if (!f) return;
    if (!fac[f]) fac[f] = {t:0, i:0};
    fac[f].t++;
    if (overallVerdict(r) === 'invalid') fac[f].i++;
  });
  const arr = Object.entries(fac).filter(([_,v])=>v.i>=1)
    .sort((a,b)=>b[1].i-a[1].i || (b[1].i/b[1].t)-(a[1].i/a[1].t)).slice(0,20);
  if (!arr.length) {
    document.getElementById('tbl-facilities').innerHTML = '<p class="muted">No facility-level invalid samples.</p>'; return;
  }
  const tr = arr.map(([f,v])=>{
    const p = (v.i*100/v.t).toFixed(1);
    const cls = p >= 50 ? 'invalid' : p >= 25 ? 'unknown' : '';
    return `<tr><td class="ar">${escapeHtml(f)}</td><td>${v.t}</td>
      <td><span class="badge ${cls}">${v.i}</span></td><td>${p}%</td></tr>`;
  }).join('');
  document.getElementById('tbl-facilities').innerHTML = `<table>
    <thead><tr><th>Facility</th><th>Total</th><th>Non-compliant</th><th>Fail %</th></tr></thead>
    <tbody>${tr}</tbody></table>`;
}

function renderCategories() {
  const rows = filteredRows();
  const cat = {};
  rows.forEach(r => {
    const c = r[COLS.category];
    if (!c) return;
    if (!cat[c]) cat[c] = {t:0,v:0,i:0,u:0};
    cat[c].t++;
    const ov = overallVerdict(r);
    if (ov === 'valid') cat[c].v++;
    else if (ov === 'invalid') cat[c].i++;
    else cat[c].u++;
  });
  const arr = Object.entries(cat).sort((a,b)=>b[1].i-a[1].i || b[1].t-a[1].t).slice(0,20);
  if (!arr.length) {
    document.getElementById('tbl-categories').innerHTML = '<p class="muted">No category data.</p>'; return;
  }
  const tr = arr.map(([c,v])=>{
    const p = (v.i*100/v.t).toFixed(1);
    const cls = p >= 50 ? 'invalid' : p >= 25 ? 'unknown' : '';
    return `<tr><td>${escapeHtml(c)}</td><td>${v.t}</td>
      <td><span class="badge valid">${v.v}</span></td>
      <td><span class="badge ${cls}">${v.i}</span></td>
      <td><span class="badge unknown">${v.u}</span></td>
      <td>${p}%</td></tr>`;
  }).join('');
  document.getElementById('tbl-categories').innerHTML = `<table>
    <thead><tr><th>Category</th><th>Total</th><th>Compliant</th><th>Non-compliant</th><th>Unknown</th><th>Fail %</th></tr></thead>
    <tbody>${tr}</tbody></table>`;
}

function renderDrilldown() {
  const rows = filteredRows();
  // Sort: higher risk first, then invalid, then by date desc
  const ordered = rows.slice().sort((a,b)=>{
    const ra = a[COLS.risk_score]||0, rb = b[COLS.risk_score]||0;
    if (ra !== rb) return rb - ra;
    const av = overallVerdict(a), bv = overallVerdict(b);
    const sa = av === 'invalid' ? 0 : (av === 'unknown' ? 1 : 2);
    const sb = bv === 'invalid' ? 0 : (bv === 'unknown' ? 1 : 2);
    if (sa !== sb) return sa - sb;
    return (b[COLS.year_month]||'').localeCompare(a[COLS.year_month]||'');
  }).slice(0, 300);
  if (!ordered.length) {
    document.getElementById('drilldown').innerHTML = '<p class="muted">No matching rows.</p>'; return;
  }
  const tr = ordered.map(r => {
    const dom = r[COLS.domain];
    const domBadge = `<span class="badge ${dom}">${dom === 'chem' ? 'Chemistry' : (dom === 'micro' ? 'Microbio' : 'Both')}</span>`;
    function vBadge(v) {
      return v === 1 ? '<span class="badge valid">V</span>'
           : v === 0 ? '<span class="badge invalid">X</span>'
           : '<span class="badge unknown">?</span>';
    }
    const overall = overallVerdict(r);
    const overallBadge = overall === 'valid' ? '<span class="badge valid">Compliant</span>'
                       : overall === 'invalid' ? '<span class="badge invalid">Non-compliant</span>'
                       : '<span class="badge unknown">Unknown</span>';
    const issues = [r[COLS.chem_issues], r[COLS.micro_issues]].filter(Boolean).join(' | ');
    const tier = r[COLS.risk_tier]||'None';
    const riskBadge = `<span class="badge risk-${tier.toLowerCase()}">${tier} (${(r[COLS.risk_score]||0).toFixed(0)})</span>`;
    return `<tr>
      <td>${r[COLS.year]}</td>
      <td>${domBadge}</td>
      <td>${escapeHtml(r[COLS.sample_id])}</td>
      <td class="ar">${escapeHtml(r[COLS.sample_name])}</td>
      <td>${escapeHtml(r[COLS.category])}</td>
      <td class="ar">${escapeHtml(r[COLS.facility])}</td>
      <td class="ar">${escapeHtml(r[COLS.municipality])}</td>
      <td>${vBadge(r[COLS.chem_valid])}</td>
      <td>${vBadge(r[COLS.micro_valid])}</td>
      <td>${overallBadge}</td>
      <td>${riskBadge}</td>
      <td>${escapeHtml(issues)}</td>
    </tr>`;
  }).join('');
  document.getElementById('drilldown').innerHTML = `<table>
    <thead><tr><th>Yr</th><th>Domain</th><th>Sample ID</th><th>Name</th><th>Category</th>
      <th>Facility</th><th>Municipality</th><th>Chem</th><th>Micro</th><th>Overall</th><th>Risk</th><th>Issues</th></tr></thead>
    <tbody>${tr}</tbody></table>`;
}

function renderAll() {
  try {
    const total = DATA.rows.length;
    const both = DATA.rows.filter(r => r[COLS.domain] === 'both').length;
    document.getElementById('subtitle').textContent =
      `${total.toLocaleString()} unique physical samples · ${both.toLocaleString()} tested in BOTH labs · years 2023–2025`;
    const fRows = filteredRows();
    document.getElementById('filter-status').textContent =
      `→ ${fRows.length.toLocaleString()} match`;
    renderKpis();
    renderYearBar();
    renderDomainBar();
    renderVerdictBar();
    renderRiskBar();
    renderSectorBar();
    renderMatrix();
    renderDomain();
    renderRisk();
    renderTopRisk();
    renderMonthly();
    renderYoY();
    renderFail();
    renderFacilities();
    renderCategories();
    renderDrilldown();
  } catch (err) {
    console.error('render failed', err);
    document.getElementById('subtitle').textContent = 'Render error: ' + err.message;
  }
}

let st = null;
document.getElementById('search').addEventListener('input', (e) => {
  clearTimeout(st);
  st = setTimeout(() => { searchTerm = e.target.value.trim().toLowerCase(); renderAll(); }, 150);
});
document.getElementById('btn-reset').onclick = () => {
  document.getElementById('search').value = '';
  searchTerm = '';
  currentYear = 'all'; currentDomain = 'all'; currentVerdict = 'all'; currentMatrix = null; currentRisk = 'all'; currentSector = 'all';
  renderAll();
};
document.getElementById('btn-csv').onclick = () => {
  const rows = filteredRows();
  const headers = ['year','sample_id','sample_name','category','facility','municipality','sector',
                   'domain','chem_sections','chem_valid','micro_valid',
                   'chem_issues','micro_issues','year_month',
                   'risk_score','risk_tier','risk_drivers'];
  const esc = v => {
    if (v == null) return '';
    const s = String(v);
    return s.match(/[,"\n]/) ? '"' + s.replace(/"/g,'""') + '"' : s;
  };
  const lines = [headers.join(',')];
  rows.forEach(r => {
    lines.push(headers.map(h => esc(r[COLS[h]])).join(','));
  });
  const blob = new Blob(['﻿' + lines.join('\n')], {type:'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `joint_samples_${currentYear}_${currentDomain}.csv`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

renderAll();
</script>
</body></html>
"""


def main():
    by_sample = collect_chemistry()
    add_microbiology(by_sample)
    payload = build_payload(by_sample)
    print(f"Total unique samples: {len(payload['rows']):,}")

    # Stats for sanity
    domains = defaultdict(int)
    for r in payload["rows"]:
        # Look up by column name to avoid index drift when cols change
        dom_idx = payload["cols"].index("domain")
        domains[r[dom_idx]] += 1
    print(f"  chem-only:  {domains['chem']:,}")
    print(f"  micro-only: {domains['micro']:,}")
    print(f"  BOTH:       {domains['both']:,}")

    html = TEMPLATE.replace("__DATA_JSON__", json.dumps(payload, ensure_ascii=False))
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size // 1024
    print(f"\nwrote {OUT_HTML}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
