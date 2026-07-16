# Micro Dashboard v2 — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a report-sourced "Official Annual Figures" band (Tier 1) and fix the interactive explorer (Tier 2) so every filter drives every chart, geography is 5-sector, and rankings match the Annual Report.

**Architecture:** A new parser turns the Annual Report workbook into a per-year JSON block that the dashboard renders as a static top band. The existing interactive dashboard is refactored from a three-way scope/slice/active partition to a single `rowsFiltered` tier, and its geography drops the 16-sub-municipality layer for 5 sectors + Special.

**Tech Stack:** Python 3.12 (`microbiology/.venv`), pandas + openpyxl, a single self-contained HTML/JS dashboard string in `build_dashboard_combined.py`, Plotly (already vendored inline).

## Global Constraints

- Microbiology only — **no chemistry file may be staged** on any commit. Verify each commit: `git diff --cached --name-only | grep -c chemistry` must print `0`.
- Run all Python with `microbiology/.venv/bin/python`.
- Regenerate the dashboard with `microbiology/.venv/bin/python microbiology/scripts/build_dashboard_combined.py`; output is `microbiology/reports/microbiology_dashboard.html`.
- Report ground truth (2025 MICRO), assert verbatim: total samples **11404**, compliant **8345**, compliance **73.18%**, total tests **46309**, non-compliant tests **4211**, top per-test rate = Aerobic plate count **22.8%**, sector Central (القطاع الأوسط) **6790** (largest).
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Phase 2 (2024 Annual Report + richer 2024 raw) is OUT of scope.

---

### Task 1: `annual_report.py` — parse the report into a per-year block

**Files:**
- Create: `microbiology/scripts/annual_report.py`
- Test: `microbiology/scripts/test_annual_report.py`

**Interfaces:**
- Produces: `load_annual_report(path: str | Path, year: int) -> dict` returning
  `{year, total_samples, compliant, compliance_rate, total_tests,
  non_compliant_tests, per_test: [{name_en, name_ar, total, invalid, rate}],
  sectors: [{name_ar, samples, pct}]}`. Missing sheet/label → that key omitted
  (never raises on a missing optional sheet).
- Produces: `load_all_annual_figures(base_dir: str | Path) -> dict[int, dict]` —
  loads `2025-original/Annual Report 2025.xlsx` as year 2025; includes
  `2024-original/Annual Report 2024.xlsx` as year 2024 only if that file exists.

- [ ] **Step 1: Write the failing test**

```python
# microbiology/scripts/test_annual_report.py
from pathlib import Path
from annual_report import load_annual_report, load_all_annual_figures

BASE = Path(__file__).resolve().parent.parent
REPORT = BASE / "2025-original" / "Annual Report 2025.xlsx"

def test_2025_totals():
    b = load_annual_report(REPORT, 2025)
    assert b["total_samples"] == 11404
    assert b["compliant"] == 8345
    assert round(b["compliance_rate"], 2) == 73.18
    assert b["total_tests"] == 46309
    assert b["non_compliant_tests"] == 4211

def test_2025_per_test_ranked_by_rate():
    b = load_annual_report(REPORT, 2025)
    top = b["per_test"][0]
    assert top["name_en"] == "Aerobic plate count"
    assert top["rate"] == 22.8
    # sorted descending, and the synthetic "Total" row is excluded
    rates = [t["rate"] for t in b["per_test"]]
    assert rates == sorted(rates, reverse=True)
    assert all(t["name_en"].lower() != "total" for t in b["per_test"])

def test_2025_sectors_central_largest():
    b = load_annual_report(REPORT, 2025)
    assert b["sectors"][0]["name_ar"].strip() == "القطاع الأوسط"
    assert b["sectors"][0]["samples"] == 6790

def test_load_all_has_2025():
    figs = load_all_annual_figures(BASE)
    assert 2025 in figs and figs[2025]["total_samples"] == 11404
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd microbiology/scripts && ../.venv/bin/python -m pytest test_annual_report.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'annual_report'`.

- [ ] **Step 3: Write the parser**

```python
# microbiology/scripts/annual_report.py
"""Parse the official Annual Report workbook into per-year 'official figures'
for the Tier-1 band in build_dashboard_combined.py. MICRO stream only."""
from __future__ import annotations
from pathlib import Path
import pandas as pd

# Report's left-block English spelling (incl. its typos) -> Arabic display.
TEST_EN_TO_AR = {
    "Aerobic plate count":     "العد الكلي للبكتيريا",
    "Staphylococcus aureas":   "استافيلوكوكس اورياس",
    "Yeasts & Molds":          "الخمائر والاعفان",
    "Enterobacteriaceae":      "انتيروباكتريسي",
    "E. coli":                 "ايشيريشيا كولاي",
    "Salmonella":              "السالمونيلا",
    "Coliforms":               "كوليفورم",
    "Bacillus cereus":         "باسيلس سيريس",
    "Pseudomonas aeruginosa":  "سيدوموناس",
    "Campylobacter jejuni":    "كامبيلوباكتر",
    "Clostridium perfringens": "كلوستريديوم بيرفرنجنز",
    "Clostridium botulinum":   "كلوستريديوم بوتولينوم",
    "E. coli O157":            "ايشيريشيا كولاي O157",
    "Listeria monocytogenes":  "الليستيريا",
    "Vibrio parahaemolyticus": "فيبريو",
}

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def load_annual_report(path, year: int) -> dict:
    xl = pd.ExcelFile(path)
    out = {"year": year}
    sheets = set(xl.sheet_names)

    if "Compliance rate" in sheets:
        cr = xl.parse("Compliance rate", header=None)
        tot = cr[cr[1] == "Total"]
        if len(tot):
            r = tot.iloc[0]
            if _num(r[2]) is not None: out["total_samples"] = int(_num(r[2]))
            if _num(r[3]) is not None: out["compliant"] = int(_num(r[3]))
            rate = _num(r[4])
            if rate is not None:
                out["compliance_rate"] = round(rate * 100, 2) if rate <= 1 else round(rate, 2)

    if "Test" in sheets:
        ts = xl.parse("Test", header=None)
        per_test = []
        for i in range(len(ts)):
            name = ts.iloc[i, 1]
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            total = _num(ts.iloc[i, 2]); nc = _num(ts.iloc[i, 4])
            if total is None:
                continue
            if name.lower() == "total":
                out["total_tests"] = int(total)
                out["non_compliant_tests"] = int(nc or 0)
                continue
            per_test.append({
                "name_en": name,
                "name_ar": TEST_EN_TO_AR.get(name, name),
                "total": int(total),
                "invalid": int(nc or 0),
                "rate": round(100 * (nc or 0) / total, 1) if total else 0.0,
            })
        per_test.sort(key=lambda t: -t["rate"])
        out["per_test"] = per_test

    if "Municipalities" in sheets:
        mun = xl.parse("Municipalities", header=None)
        sectors = []
        for i in range(len(mun)):
            name = mun.iloc[i, 1]; samples = _num(mun.iloc[i, 2])
            if not isinstance(name, str) or samples is None:
                continue
            nm = name.strip()
            if nm in ("Total", "المجموع") or "Municipality" in nm:
                continue
            if nm.startswith(("قطاع", "القطاع", "العينات")):
                sectors.append({"name_ar": nm, "samples": int(samples)})
        tot_s = sum(s["samples"] for s in sectors) or 1
        for s in sectors:
            s["pct"] = round(100 * s["samples"] / tot_s, 1)
        sectors.sort(key=lambda s: -s["samples"])
        out["sectors"] = sectors

    return out

def load_all_annual_figures(base_dir) -> dict:
    base = Path(base_dir)
    figs = {}
    p25 = base / "2025-original" / "Annual Report 2025.xlsx"
    if p25.exists():
        figs[2025] = load_annual_report(p25, 2025)
    p24 = base / "2024-original" / "Annual Report 2024.xlsx"
    if p24.exists():
        figs[2024] = load_annual_report(p24, 2024)
    return figs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd microbiology/scripts && ../.venv/bin/python -m pytest test_annual_report.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/bioinfo/Documents/Data-Analysis-Muhannad
git add microbiology/scripts/annual_report.py microbiology/scripts/test_annual_report.py
git diff --cached --name-only | grep -c chemistry   # must print 0
git commit -m "Micro: annual_report.py — parse Annual Report into per-year official figures

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Inject `ANNUAL` figures into the dashboard payload

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` (imports near top; the payload/FACETS assembly, ~line 560–600 where the `<script>const FACETS = …</script>` block is written)

**Interfaces:**
- Consumes: `load_all_annual_figures` from Task 1.
- Produces: a JS global `const ANNUAL = {…}` (JSON of `{year: block}`) available to the render layer, and a Python `ANNUAL_FIGURES` dict.

- [ ] **Step 1: Add the import and load the figures**

Near the other imports at the top of `build_dashboard_combined.py`, add:

```python
from annual_report import load_all_annual_figures
```

In the build function, after `df` is assembled and before the HTML template is composed, add:

```python
    ANNUAL_FIGURES = load_all_annual_figures(ROOT)   # ROOT = microbiology/ dir
```

(Confirm `ROOT` already points at the `microbiology/` directory; it is used for
`scripts/gso_category_corrections.csv`. If the name differs, reuse that path base.)

- [ ] **Step 2: Emit the JS global**

Find where `const FACETS = {json};` is written into the template and add a sibling
line immediately after it:

```python
    annual_js = "const ANNUAL = " + json.dumps(ANNUAL_FIGURES, ensure_ascii=False) + ";"
```

Include `annual_js` in the template next to the `FACETS`/`PAYLOAD` script emission
so the page contains `const ANNUAL = {...};`.

- [ ] **Step 3: Regenerate and verify the global is present**

Run:
```bash
microbiology/.venv/bin/python microbiology/scripts/build_dashboard_combined.py
grep -c 'const ANNUAL = ' microbiology/reports/microbiology_dashboard.html   # expect 1
microbiology/.venv/bin/python - <<'PY'
import re, json
h = open("microbiology/reports/microbiology_dashboard.html", encoding="utf-8").read()
m = re.search(r'const ANNUAL = (\{.*?\});', h, re.S)
a = json.loads(m.group(1))
assert a["2025"]["total_samples"] == 11404, a["2025"].get("total_samples")
assert a["2025"]["non_compliant_tests"] == 4211
print("ANNUAL 2025 OK:", a["2025"]["total_samples"], a["2025"]["total_tests"])
PY
```
Expected: `1`, then `ANNUAL 2025 OK: 11404 46309`.

- [ ] **Step 4: Commit**

```bash
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
git diff --cached --name-only | grep -c chemistry   # 0
git commit -m "Micro dashboard: inject ANNUAL official figures into payload

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Render the Tier-1 "Official Annual Figures" band

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — add an HTML mount
  `<section id="annual-band">` directly below the page header / above the filter
  bar; add a JS `renderAnnual()` function; call it once at startup.

**Interfaces:**
- Consumes: `const ANNUAL` (Task 2).

- [ ] **Step 1: Add the HTML mount**

Insert directly after the page `<header>` block and before the sticky filter bar
mount in the HTML template:

```html
<section id="annual-band" class="card" style="margin:12px 0">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap">
    <h2 style="margin:0">Official Annual Figures <span class="section-note">source: Annual Report</span></h2>
    <div id="annual-tabs" style="display:flex; gap:6px"></div>
  </div>
  <div id="annual-body"></div>
</section>
```

- [ ] **Step 2: Add the `renderAnnual()` function**

Add near the other render functions:

```javascript
let annualYear = null;
function renderAnnual() {
  const years = Object.keys(ANNUAL).map(Number).sort((a,b)=>b-a);
  if (!years.length) { document.getElementById('annual-band').style.display='none'; return; }
  if (annualYear === null) annualYear = years[0];
  document.getElementById('annual-tabs').innerHTML = years.map(y =>
    `<div class="chip${y===annualYear?' active':''}" data-annual-year="${y}">${y}</div>`).join('');
  const b = ANNUAL[String(annualYear)] || {};
  const kpi = (label,val,sub)=>`<div class="kpi"><div class="label">${label}</div><div class="value">${val}</div><div class="sub">${sub||''}</div></div>`;
  const n = v => (v==null?'—':Number(v).toLocaleString());
  const kpis = [
    kpi('Total samples', n(b.total_samples), 'MICRO · annual report'),
    kpi('Compliance rate', b.compliance_rate!=null? b.compliance_rate.toFixed(2)+'%':'—', n(b.compliant)+' compliant'),
    kpi('Total tests', n(b.total_tests), 'test runs (incl. replicates)'),
    kpi('Non-compliant tests', n(b.non_compliant_tests), b.total_tests? (100*b.non_compliant_tests/b.total_tests).toFixed(1)+'% of tests':''),
  ].join('');
  const per = (b.per_test||[]).map(t=>`<tr>
     <td class="ar" style="text-align:start; padding:4px 10px">${t.name_ar}</td>
     <td style="text-align:right; padding:4px 10px; font-variant-numeric:tabular-nums">${t.invalid.toLocaleString()} / ${t.total.toLocaleString()}</td>
     <td style="text-align:right; padding:4px 10px; font-weight:600">${t.rate.toFixed(1)}%</td></tr>`).join('');
  const sec = (b.sectors||[]).map(s=>`<tr>
     <td class="ar" style="text-align:start; padding:4px 10px">${s.name_ar}</td>
     <td style="text-align:right; padding:4px 10px">${s.samples.toLocaleString()}</td>
     <td style="text-align:right; padding:4px 10px">${s.pct.toFixed(1)}%</td></tr>`).join('');
  document.getElementById('annual-body').innerHTML =
    `<div class="kpis" style="margin:12px 0">${kpis}</div>
     <div style="display:flex; gap:24px; flex-wrap:wrap">
       <div style="flex:1; min-width:280px"><div class="section-note" style="margin-bottom:4px">Failure rate by test (ranked)</div>
         <table style="width:100%; font-size:12px; border-collapse:collapse"><tbody>${per}</tbody></table></div>
       <div style="flex:1; min-width:240px"><div class="section-note" style="margin-bottom:4px">Samples collected by sector (report basis)</div>
         <table style="width:100%; font-size:12px; border-collapse:collapse"><tbody>${sec}</tbody></table></div>
     </div>`;
}
document.getElementById('annual-tabs').addEventListener('click', e => {
  const t = e.target.closest('[data-annual-year]'); if (!t) return;
  annualYear = Number(t.getAttribute('data-annual-year')); renderAnnual();
});
```

Call `renderAnnual();` once at startup (next to the initial `applyFilters();`).

- [ ] **Step 3: Regenerate and verify**

```bash
microbiology/.venv/bin/python microbiology/scripts/build_dashboard_combined.py
grep -c 'id="annual-band"' microbiology/reports/microbiology_dashboard.html   # 1
grep -c 'function renderAnnual' microbiology/reports/microbiology_dashboard.html # 1
```
Expected: `1` and `1`. (Open the file in a browser to eyeball the band: 4 KPIs
show 11,404 / 73.18% / 46,309 / 4,211 and the test table lists العد الكلي first.)

- [ ] **Step 4: Commit**

```bash
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
git diff --cached --name-only | grep -c chemistry   # 0
git commit -m "Micro dashboard: Tier-1 Official Annual Figures band

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Collapse scope/slice into a single `rowsFiltered` tier

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — `applyFilters()`
  (~1399–1551), `renderAll()` (~2604–2641), the slice-banner block, and
  `renderKpis` call arguments.

**Interfaces:**
- Produces: `renderAll(rowsFiltered)` — every render function receives the single
  filtered set. `rowsActive = rowsFiltered.filter(sev!=='none')` is computed
  locally inside `renderAll` only for the two intrinsically severity-event charts
  (severity-month, heatmap).

- [ ] **Step 1: Fold slice chips into scope in `applyFilters`**

In `applyFilters`, delete the `SCOPE_CHIPS` / `SLICE_CHIPS` split. Make one
predicate `isPass(r)` that applies **all** active chip filters + compliance + date
+ show-only toggles + excludes + the microbe match. Replace the three sets with:

```javascript
  const rowsFiltered = ROWS.filter(isPass);
```

Delete `rowsScope` / `rowsSliced` / `rowsActive` here. Keep the slice-banner but
rewrite its copy to: `'<b>Filter active:</b> N of M samples match.'` (no more
"only these charts respond"). Change the final call to:

```javascript
  renderAll(rowsFiltered);
```

- [ ] **Step 2: Rewrite `renderAll` to fan out the single set**

```javascript
function renderAll(rows) {
  const rowsActive = rows.filter(r => r[COLS.severity] !== 'none');
  document.getElementById('meta_rows').textContent = FACETS.row_count.toLocaleString();
  document.getElementById('meta_range').textContent = FACETS.date_min + ' → ' + FACETS.date_max;
  window.__mapRows = rows;

  refreshMicrobeChipCounts(rows);
  renderKpis(rows);
  renderMap(rows);
  renderTrend(rows);
  renderYoY(rows);
  renderSector(rows);
  renderGsoCategory(rows);
  renderMunicipality(rows);   // becomes sector-level in Task 5; kept for now
  renderChains(rows);
  renderDow(rows);
  renderRepeatTable(rows);
  renderTopSubtypes(rows, rows);   // scope==slice now; Task 6 refines numerator
  renderSeverityMonth(rowsActive);
  renderHeatmap(rowsActive);
  renderTests(rows);
  renderDrilldown(rows);
}
```

- [ ] **Step 3: Simplify `renderKpis` signature**

Change `function renderKpis(rows, rowsFull, rowsBase)` to `function renderKpis(rows)`
and set `const rowsBase = rows; const rowsActive = rows.filter(r=>r[COLS.severity]!=='none');`
at the top (rankOrganism uses `rowsActive`). Every `rowsBase`/`rowsFull` reference
now resolves to the single filtered set.

- [ ] **Step 4: Regenerate and verify every figure reacts to a slice filter**

```bash
microbiology/.venv/bin/python microbiology/scripts/build_dashboard_combined.py
microbiology/.venv/bin/python - <<'PY'
h=open("microbiology/reports/microbiology_dashboard.html",encoding="utf-8").read()
assert "renderAll(rowsFiltered)" in h
assert "SLICE_CHIPS" not in h and "rowsSliced" not in h, "scope/slice remnants remain"
assert h.count("renderKpis(rows)")>=1
print("single-tier OK")
PY
```
Expected: `single-tier OK`. (Manually: toggling a severity chip now changes the
KPIs, sector chart, and facilities — not just 5 charts.)

- [ ] **Step 5: Commit**

```bash
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
git diff --cached --name-only | grep -c chemistry   # 0
git commit -m "Micro dashboard: single filter tier — every filter drives every figure

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Geography → 5 sectors + Special (drop sub-municipality)

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — remove the
  `f_municipality` multi-select + `refreshMunicipalityOptions`; `renderMap` sub
  bubbles; the `municipality` entry in `CHIP_FILTERS`; the "Highest-risk
  sub-municipality" KPI; `renderMunicipality` → sector aggregation.

- [ ] **Step 1: Remove the sub-municipality filter UI + state**

Delete the `f_municipality` `<select>` from the HTML template and the
`refreshMunicipalityOptions()` function, its calls, and the `munSel` listener.
Remove `{ state_key:'municipality', col_key:'municipality' }` from `CHIP_FILTERS`.
Remove `state.municipality` usage from `btn_reset` and `activeCount`. Keep
`derive_sector_5` / `SECTOR_5_OF_SUBMUNI` (internal row→sector assignment).

- [ ] **Step 1b: Emit a "Special" sector for private samples (Python)**

Our data currently yields no `Special` sector value. In `build_dashboard_combined.py`
Python side: (a) add `"Special"` to `SECTORS_5` so it becomes the 6-entry sector
list surfaced as chips + chart order; (b) in `derive_sector_5`, before returning,
add: `if municipality_type is not None and str(municipality_type).strip() == "خاص": return "Special"`
(the caller already passes the row; thread `municipality_type` in, or check
`municipality == "عينة خاصة"`). (c) Add `"Special": (24.6877, 46.7219)` to the
Python `SECTOR_CENTROIDS` dict so the map has a bubble for it.

Verify after regen: `FACETS.sectors` includes `Special` and the payload has rows
with `sector == "Special"` (~67 in 2025).

- [ ] **Step 2: Map draws sector bubbles only**

In `renderMap`, remove the `subAgg` (per-`بلدية`) trace entirely. Aggregate only
into `secAgg` keyed by `r[COLS.sector]` over the 5 sectors + Special, using
`MAP_CENTROIDS.sectors` (add a `Special` centroid = Riyadh centre `[24.6877, 46.7219]`
in `SECTOR_CENTROIDS` and in the Python `SECTOR_CENTROIDS` dict). Bubbles = sector
totals; keep the failure/pathogen/volume metric toggle.

- [ ] **Step 3: Replace the "Highest-risk sub-municipality" KPI with sector**

In `renderKpis`, replace the `highestRiskMun` block:

```javascript
  const highestRiskSector = rankByRate(COLS.sector, 30);
```

and change the card to `label: 'Highest-risk sector'`,
`value: truncate(highestRiskSector.key, 30)`, sub = rate/volume as before.

- [ ] **Step 4: `renderMunicipality` → sector chart**

Rename the chart usage: aggregate `rows` by `r[COLS.sector]` (5 + Special) instead
of `r[COLS.municipality]`, feed `_renderVolumeVsRate('chart_mun', items, 'sector', …)`.
(The dedicated `renderSector` already covers this; if both mounts exist, point the
municipality mount at sector data too or hide it — keep one sector chart.)

- [ ] **Step 5: Regenerate and verify**

```bash
microbiology/.venv/bin/python microbiology/scripts/build_dashboard_combined.py
microbiology/.venv/bin/python - <<'PY'
import re,json
h=open("microbiology/reports/microbiology_dashboard.html",encoding="utf-8").read()
assert 'id="f_municipality"' not in h, "sub-municipality filter still present"
assert "Highest-risk sector" in h
# sector centroids include Special
m=re.search(r'"sectors": (\{[^}]*\})', h); print("map sectors:", list(json.loads(m.group(1)).keys()))
PY
```
Expected: no `f_municipality`; `Highest-risk sector` present; map sectors =
East/North/West/Central/South/Special. (Manually: sector ranking returns Central.)

- [ ] **Step 6: Commit**

```bash
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
git diff --cached --name-only | grep -c chemistry   # 0
git commit -m "Micro dashboard: geography to 5 sectors + Special; drop sub-municipality layer

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Top-test-by-rate + organism-chip class fix

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — `renderKpis`
  (`mostFreqPathogen` → top test by rate); `renderTopSubtypes` (organism tally).

- [ ] **Step 1: "Most frequent pathogen" → "Top failing test (by rate)"**

In `renderKpis`, replace the `mostFreqPathogen` rank with a rate ranking over **all**
tests (pathogens + indicators), min 30 test-results denominator:

```javascript
  function topTestByRate(rowSet, minDenom) {
    const tot = new Map(), fail = new Map();
    for (const r of rowSet) {
      const seen = new Set();
      for (const t of (r[COLS.failed_tests] || [])) { if (!seen.has(t)) { seen.add(t); fail.set(t,(fail.get(t)||0)+1); } }
    }
    // denominator: every test appears once per sample that ran a panel; approximate
    // with samples-in-scope as the panel base per organism present.
    let bestK=null, bestRate=-1, bestF=0;
    for (const [k,f] of fail) { const rate = 100*f/rowSet.length; if (rate>bestRate){bestRate=rate;bestK=k;bestF=f;} }
    return { key: bestK, rate: bestRate, fail: bestF };
  }
  const topTest = topTestByRate(rowsActive);
```

Card: `label:'Top failing test'`, `value: truncate(topTest.key,30)`,
`sub: topTest.key ? topTest.fail.toLocaleString()+' failing samples' : 'no data'`.
(Note in the card sub or a tooltip: exact per-test rates are in the Official band.)

- [ ] **Step 2: Organism chips reflect the active microbe/pathogen filter**

In `renderTopSubtypes`, when tallying `slot.organisms`, filter the organism list by
the active filter. Add at the top of the numerator loop:

```javascript
  const microFilter = state.microbe && state.microbe.size ? state.microbe : null;
  const pathOnly = !!state.pathogen_only;
```

and when adding organisms:

```javascript
    for (const t of (r[COLS.failed_tests] || [])) {
      if (microFilter && !microFilter.has(t) && !(microFilter.has(INDICATOR_TOKEN) && INDICATOR_SET.has(t))) continue;
      if (pathOnly && !PATHOGEN_SET.has(t)) continue;   // pathogen filter → only pathogens in chips
      if (seen.has(t)) continue; seen.add(t);
      slot.organisms.set(t, (slot.organisms.get(t)||0)+1);
    }
```

- [ ] **Step 3: Regenerate and verify**

```bash
microbiology/.venv/bin/python microbiology/scripts/build_dashboard_combined.py
microbiology/.venv/bin/python - <<'PY'
h=open("microbiology/reports/microbiology_dashboard.html",encoding="utf-8").read()
assert "Top failing test" in h
assert "pathogen filter" in h.lower() or "PATHOGEN_SET.has(t)) continue" in h
print("top-test + org-chip OK")
PY
```
Expected: `top-test + org-chip OK`. (Manually: enable Pathogen-only → the org
chips in the most-contaminated list contain no indicator organisms like العد الكلي.)

- [ ] **Step 4: Commit**

```bash
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
git diff --cached --name-only | grep -c chemistry   # 0
git commit -m "Micro dashboard: top failing test by rate; org chips honour pathogen/microbe filter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Cosmetic — subtitle, pathogen card, remove interactive test-count KPI

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — the `subtitle`
  element assignment (removed in Task 4's `renderAll`; confirm gone); the
  `subtitle` HTML node; the "Pathogen failures" KPI card; the "Total tests
  performed" KPI card block (~1690–1713).

- [ ] **Step 1: Remove the subtitle line**

Delete the `<div id="subtitle">…</div>` (or `<p id="subtitle">`) node from the HTML
template and any remaining `document.getElementById('subtitle')` assignment.

- [ ] **Step 2: Remove the interactive "Total tests performed" KPI**

Delete the whole `...(() => { … 'Total tests performed' … })(),` IIFE from the
`cards` array in `renderKpis` (exact counts now live only in the Official band).

- [ ] **Step 3: Clarify the pathogen card**

Change the "Pathogen failures" card so its value cannot be read as compliance —
value stays the count, but set the sub to:
`'pathogen-failure rate ' + pct(pathogenFails,total).toFixed(2) + '% — not a compliance figure'`
and keep `cls:'crit'`.

- [ ] **Step 4: Regenerate and verify**

```bash
microbiology/.venv/bin/python microbiology/scripts/build_dashboard_combined.py
microbiology/.venv/bin/python - <<'PY'
h=open("microbiology/reports/microbiology_dashboard.html",encoding="utf-8").read()
assert 'id="subtitle"' not in h, "subtitle still present"
assert "Total tests performed" not in h, "interactive total-tests KPI still present"
assert "not a compliance figure" in h
print("cosmetic OK")
PY
```
Expected: `cosmetic OK`.

- [ ] **Step 5: Final reconciliation check + commit**

```bash
microbiology/.venv/bin/python - <<'PY'
import re,json
h=open("microbiology/reports/microbiology_dashboard.html",encoding="utf-8").read()
a=json.loads(re.search(r'const ANNUAL = (\{.*?\});',h,re.S).group(1))["2025"]
assert (a["total_samples"],a["compliant"],a["total_tests"],a["non_compliant_tests"])==(11404,8345,46309,4211)
print("Tier-1 matches report:", a["total_samples"], a["compliance_rate"], a["total_tests"], a["non_compliant_tests"])
PY
git add microbiology/scripts/build_dashboard_combined.py microbiology/reports/microbiology_dashboard.html
git diff --cached --name-only | grep -c chemistry   # 0
git commit -m "Micro dashboard: remove subtitle + interactive test-count KPI; clarify pathogen card

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the implementer

- The dashboard is one large Python file that emits a single self-contained HTML
  string with inline JS. There is no JS test harness; "tests" for Tasks 2–7 are
  regenerate-then-assert on the emitted HTML/payload (shown in each task) plus a
  manual browser eyeball where noted.
- Line numbers are approximate — locate by the quoted identifiers (`renderAll`,
  `applyFilters`, `SLICE_CHIPS`, `f_municipality`, `mostFreqPathogen`, `subtitle`).
- Keep every commit micro-only; the `grep -c chemistry` guard is mandatory.
- Phase 2 (2024 Annual Report + richer raw) is deliberately excluded; `annual_report.py`
  already auto-includes 2024 when `2024-original/Annual Report 2024.xlsx` appears.
