# Microbiology Dashboard — Enhancement Report

**Date:** 2026-08-11  
**Scope:** Full audit of `microbiology_dashboard.html` (165 KB build script, 7.2 MB output) + 7 standalone interactives  
**Status:** Dashboard is stable and data-complete. This report identifies concrete gaps and enhancement opportunities.

---

## Current Inventory (What We Have)

### Main Dashboard — 5 Tabs, 19 Visualizations, 12 KPI Cards

| Tab | Charts | KPIs / Tables |
| :--- | :--- | :--- |
| **📊 Overview** | Riyadh bubble map, Monthly trend combo chart, Top 10 microbes bar | Official test table (HTML) |
| **📍 Location** | Sector stacked bar + line, Severity × GSO heatmap, Repeat-offender chains bar | — |
| **🍱 Products** | GSO categories stacked bar, Sample-type distribution, Top 10 subtypes bar, Top 15 chains bar | — |
| **🦠 Organisms** | Pathogen/Indicator failures bar (with 3-panel drilldown), Severity by month stacked bar | — |
| **📋 GSO & Quality** | YoY comparison bar, Day-of-week cadence bar | GSO audit grid (9 cards), GSO sortable table, Data-quality grid (10 cards) |

### Standalone Interactives (7 reports on index.html)

| # | Report | Type |
| :--- | :--- | :--- |
| 1 | Sunburst (Plotly) | Zoomable culture-plate hierarchy |
| 2 | Sunburst 2 (D3) | D3 sunburst chart |
| 3 | Sankey | Sector → Food → Organism → Severity flow |
| 4 | Treemap | Hierarchy volume & contamination |
| 5 | Heatmap Matrix | Sector × Pathogen positive rate |
| 6 | Network | Food ↔ Microbe bipartite graph |
| 7 | Streamgraph | Organism prevalence over time |

### Filters (Comprehensive)

Year chips, date range picker, compliance chips, severity chips, sector chips, GSO category chips, microbe/organism chips, 3 quick toggles (pathogen-only, repeat offender, exclude meat), 4 bookmark presets, URL state serialization with copy-link.

---

## Enhancement Opportunities

### 🔴 Priority 1 — Data Gaps That Block Features

| # | Gap | Impact | Enhancement |
| :--- | :--- | :--- | :--- |
| **P1.1** | **2025 test-level data missing** — panel completeness & GSO limit cross-checks are 2024-only | GSO & Quality tab is half-empty for 2025; compliance rate unverifiable against limits | Once the lab provides the 2025 LIMS export (one row per test), wire it into `enrich_gso.py` to unlock 2025 panel audit |
| **P1.2** | **2024 official numbers = `null`** — compliance card says "pending reconciliation" | Cannot compare our 2024 figures against the Annual Report | Confirm the 2024 official totals with the lab and populate `OFFICIAL_COMPLIANCE[2024]` |
| **P1.3** | **2025 Annual Report +160 discrepancy unresolved** — our 11,564 vs official 11,404 | Footnote uncertainty undermines trust | Confirm the exact exclusion rule (re-tests? private?) and add an `annual_report_scope` filter |
| **P1.4** | **2024 has no facility/chain data** — 5 charts are tagged `data-needs-year="2025"` | Chain rankings, repeat-offender table hidden when filtering to 2024 | If facility data exists in the 2024 source but was not extracted, add it to `clean_2024.py` |
| **P1.5** | **3,751 uncoded 2025 samples (Group B)** — 32% of 2025 still mapped to "Miscellaneous" | GSO category charts skewed; the Miscellaneous bucket is inflated | Complete the Group B disambiguation doc and run a Tier-1c heuristic pass |

### 🟡 Priority 2 — Missing Analytical Dimensions

| # | Enhancement | What it adds | Estimated complexity |
| :--- | :--- | :--- | :--- |
| **P2.1** | **Quarter-over-Quarter comparison chart** | The data payload already carries `quarter` (col index 3) but no chart uses it. A QoQ stacked bar would show seasonal patterns more clearly than the monthly trend | Low — add `renderQoQ()` using existing data |
| **P2.2** | **Facility-level drilldown table** | Currently the lowest granularity is "chain". A searchable table showing individual facility branches (name, address, sample count, NC rate, last inspection date) would be operationally actionable | Medium — data exists in `facility_name` column |
| **P2.3** | **Pathogen co-occurrence matrix** | When a sample fails multiple tests, which pathogens appear together? A symmetric heatmap of co-occurrence counts (e.g., Salmonella + E.coli O157 co-fail rate) would reveal systemic contamination patterns | Medium — compute from `failed_tests` arrays |
| **P2.4** | **Month-over-Month delta KPIs** | Add ▲/▼ trend arrows to the 12 headline KPIs showing change vs. previous month. Currently KPIs are static snapshots | Medium — requires grouping by current vs. prior month |
| **P2.5** | **Compliance trajectory sparkline** | A 12-month sparkline inside the "Compliance rate" KPI card showing the trend direction at a glance | Low — tiny inline SVG |
| **P2.6** | **"Organisms & Tests" tab is thin** | Only 2 charts (test failures bar + severity by month). Add: organism prevalence radar chart, pathogen seasonality small multiples, and a "zero-detection streak" tracker per pathogen | Medium-High |

### 🟢 Priority 3 — UX/UI Polish

| # | Enhancement | Detail |
| :--- | :--- | :--- |
| **P3.1** | **Export to PDF / Excel** | Add a "📥 Download Report" button that captures the current filtered view as a formatted PDF (KPIs + charts) or exports the filtered data rows as Excel. Critical for inspectors who need offline printouts |
| **P3.2** | **Dark mode toggle** | The CSS already has a well-structured `--var` design system. Adding a dark mode toggle would be straightforward and appreciated for night-shift analysts |
| **P3.3** | **Print stylesheet** | `@media print` rules so the dashboard prints cleanly on A4/Letter — hide filters, one chart per page, KPIs as a summary header |
| **P3.4** | **Chart annotations / callouts** | Allow the user to click on any data point and add a text annotation (stored in localStorage). Useful for marking "Ramadan period" or "new supplier onboarded" context |
| **P3.5** | **Cross-linking standalone interactives** | Clicking a node in the Sankey/Treemap/Network should deep-link back to the main dashboard with pre-applied filters (via URL hash state). Currently they are isolated |
| **P3.6** | **Responsive mobile layout** | The dashboard is desktop-first (1600px max-width). Add responsive breakpoints so it's usable on a tablet during field inspections |
| **P3.7** | **Loading skeleton / progress bar** | The 7.2 MB HTML takes time to parse. Add a CSS skeleton screen that shows immediately while JS initializes |

### 🔵 Priority 4 — Advanced / Future

| # | Enhancement | Detail |
| :--- | :--- | :--- |
| **P4.1** | **Predictive time-series forecasting** | Using the 24-month historical baseline, fit a simple seasonal decomposition (STL) to forecast next-quarter contamination rates. Surface as a "Projected NC %" KPI with confidence bands |
| **P4.2** | **DuckDB-WASM backend** | Replace the 7.2 MB inline JSON payload with a `.parquet` file loaded client-side via DuckDB-WASM. Would cut load time by ~80% and enable SQL-based ad-hoc queries |
| **P4.3** | **Geocoded facility map** | Replace sector-centroid bubbles with actual lat/lon per facility (via geocoding API). Show individual restaurant pins clustered by neighborhood |
| **P4.4** | **Automated inspection target list** | "Generate Top 50 Risk Facilities" button that exports a prioritized inspection schedule based on current filters (repeat offenders + pathogen severity + recency) |
| **P4.5** | **Chemistry × Microbiology cross-correlation** | Once the chemistry dashboard is complete, a unified view correlating chemical hazards (heavy metals, rancidity) with microbiology failures at the same facility |
| **P4.6** | **"What-if" threshold slider** | A dynamic slider that lets the user model stricter-than-GSO limits (e.g., "what if Listeria zero-tolerance applied to cakes?") and see the compliance rate change in real-time |

---

## Recommended Implementation Order

```
Phase 1 (Quick wins — 1-2 days each):
  P2.1  Quarter-over-Quarter chart         ← data already in payload
  P2.5  Compliance sparkline               ← tiny SVG addition
  P3.7  Loading skeleton                   ← CSS-only
  P3.2  Dark mode toggle                   ← CSS variable flip

Phase 2 (Medium effort — 2-5 days each):
  P2.2  Facility-level drilldown table     ← high operational value
  P2.4  MoM delta arrows on KPIs           ← high visual impact
  P3.1  Export to PDF / Excel              ← most-requested by field users
  P3.5  Cross-link standalone interactives ← connects the ecosystem

Phase 3 (Requires external input):
  P1.1  2025 test-level data (lab export)  ← unlocks panel audit
  P1.2  2024 official numbers              ← closes footnote
  P1.5  Group B disambiguation             ← user manual input

Phase 4 (Strategic / long-term):
  P4.2  DuckDB-WASM                        ← future-proofs for 100K+ rows
  P4.1  Predictive forecasting             ← shifts from reactive to proactive
  P4.3  Geocoded facility map              ← transforms field operations
```

---

## Summary

The dashboard is already **exceptionally comprehensive** — 19 visualizations, 12 dynamic KPIs, 22+ audit cards, URL-serialized state, bookmarks, and 7 standalone interactives. The foundation is production-grade.

The highest-impact enhancements are:
1. **Closing the 2025 test-level gap** (P1.1) — this alone would double the GSO audit coverage
2. **Facility-level drilldown** (P2.2) — transforms the dashboard from analytical to operational
3. **Export to PDF** (P3.1) — the #1 ask from field inspectors
4. **MoM trend arrows** (P2.4) — makes KPIs tell a story instead of just stating a number
