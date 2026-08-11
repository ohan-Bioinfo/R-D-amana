# Chemistry Dashboard — Enhancement Report

A focused proposal for extending the chemistry decision dashboard, mirroring the
microbiology enhancement report. The chemistry dashboard already shares the
microbiology dashboard's design language (5-tab, touch-first, hash-routed shell);
this document catalogues what exists and where the highest-impact next steps are.

## Current Inventory (What We Have)

### Main Dashboard — 5 Tabs, 6 Charts, Sortable GSO Table
Tabs: 📊 Overview · 📍 Location · 🧪 Products · ⚗️ Sections & tests · 📋 GSO & Quality.

- **Monthly trend combo** — lines + bars per month across sections.
- **Validity distribution** — stacked bar: valid / invalid / other.
- **Failed-tests breakdown** — top failing analytes.
- **GSO categories bar** — stacked by year; **click-to-drill** toggles a category.
- **Riyadh sector map** — 5 amanah sectors; **click-to-drill** toggles a sector.
- **Municipality bar** — volume & NC by sub-municipality.
- **Sortable GSO 1016 table** — Category · Samples · Non-compliant · NC%.
- **Data-quality audit** — flagged-row counts and structural issues.

Every chart supports zoom / pinch / touch via a shared `PLOTLY_CONFIG`; the whole
file is self-contained offline HTML.

### Standalone Interactives (2 reports on index.html)
- **Assay-plate sunburst** — Year → Section → GSO Category → failing analyte;
  Riyadh-emblem branded, bilingual, shareable deep-link; counts **15,297 unique
  samples** (pesticides collapsed), **5.8%** non-compliant.
- **D3 sunburst (v2)** — an alternate zoomable rendering.

### Filters
Year chips (2024 / 2025), section multiselect, validity-status chips (valid,
invalid, no_limit, rejected, unknown), and sector multiselect.

## Enhancement Opportunities

### 🔴 Priority 1 — Data Gaps That Block Features
- **P1.1 No LOD/LOQ columns.** A non-detect stores `value=0.0, is_nd=True`, so
  "below detection" is indistinguishable from a true zero. Capturing LOD/LOQ in
  the schema would make trace-level judgments defensible.
- **P1.2 Pesticide "invalid, no exceedance" rows.** A cluster is lab-flagged
  `is_valid=False` yet has no row exceeding a limit — they surface as
  "unspecified" in the sunburst. The lab should clarify the failure basis.
- **P1.3 Heavy-metals & pesticides YoY spike unexplained.** +12.0 pp and +8.5 pp
  in 2025; cannot be published until the cause (methodology / detection / real)
  is confirmed.
- **P1.4 Small-n & single-year sections.** hormones/antibiotics is 2025-only
  (9 rows); jam is 2024-only (83 rows, 82 no_limit). Neither supports a
  year-over-year read.
- **P1.5 Dirty `analysis_section` free-text.** Spelling variants
  (`المعادن الثقيله` / `معادن الثقيلة`); harmless today but a latent integrity
  risk.

### 🟡 Priority 2 — Missing Analytical Dimensions
- **P2.1 Analyte seasonality & sector patterns** *(medium)* — pivot
  `failed_tests_derived` by month × sector.
- **P2.2 Facility-level drilldown table** *(medium)* — searchable facility list
  (name · district · samples · NC rate); data already in the parquets.
- **P2.3 Pesticide co-occurrence matrix** *(medium-high)* — which residues appear
  together, from per-sample `pesticide_name` arrays.
- **P2.4 "Missing limits" audit view** *(low)* — list every
  `validity_status='no_limit'` sample to prioritise GSO limit standardisation.
- **P2.5 Corrections audit trail** *(medium)* — visual diff of hand-corrected vs
  auto-classified samples (~2,400 overrides).

### 🟢 Priority 3 — UX/UI Polish
- **P3.1 Export to PDF / Excel** — "Download Report" for the filtered view;
  most-requested by field inspectors.
- **P3.2 Section-bar deep-linking** — make the section bar click-to-drill for
  parity with the GSO and sector charts.
- **P3.3 Per-section trend sparklines** — inline 12-month SVG inside KPI cards.

### 🔵 Priority 4 — Advanced / Future
- **P4.1 DuckDB-WASM backend** — serve parquets client-side instead of inlining
  ~4.5 MB of JSON.
- **P4.2 GSO limit cross-audit** — cross-check 2025 results against canonical GSO
  1016 limits and flag mismatches.
- **P4.3 Geocoded facility map** — real per-facility lat/lon for field navigation.

## Recommended Implementation Order

1. **Phase 1 — Quick wins (days):** P2.4 missing-limits view, P3.2 section-bar
   deep-linking, P3.3 KPI sparklines.
2. **Phase 2 — Analytical depth (weeks):** P2.1 seasonality, P2.2 facility
   drilldown, P2.3 co-occurrence, P2.5 corrections trail.
3. **Phase 3 — Requires lab input:** P1.1 LOD/LOQ capture, P1.2 pesticide failure
   basis, P1.3 spike cause.
4. **Phase 4 — Strategic:** P4.1 DuckDB-WASM, P4.2 GSO limit cross-audit, P4.3
   geocoded map.

## Summary

The chemistry dataset is deterministic, row-for-row verified, and already shares
the microbiology dashboard's design language. Its distinctive challenges are
chemical, not microbial: the five-way validity model, the meaning of "no limit",
the pesticide long-format explosion, and two year-over-year spikes that need the
lab's read. The highest-impact next steps are **(1)** LOD/LOQ capture, **(2)**
facility-level drilldown, **(3)** resolving the heavy-metals/pesticides spike, and
**(4)** a "missing limits" audit view.
