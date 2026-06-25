# Chemistry dashboard rework — design

**Date**: 2026-06-18
**Scope**: `chemistry/scripts/build_dashboard.py` only (reads `chemistry/cleaned/chem_*.parquet`).
**Validation target**: Annual Report 2025.xlsx — chemistry stream: **7,287 samples / 500,535 tests**.

## Problems addressed (28 user-reported items)

Card duplication (15k top vs 12k unique below); Unknown verdict appearing in 3 places; Arabic↔English mix in failed-tests; trace pesticide concentrations (<0.01 ppm) inflating ranks; aflatoxin Total double-counting B1/B2/G1/G2; honey "2025(25)" cryptic label; water "Physicochemical params" jargon; rejected/no-limit categories cluttering monthly chart; sensory tests in drilldown; INV/Invalid terminology; triangle direction indicators; YoY heading wording. Full list in user message tagged "نقاط الكيمستري".

## Row sets (2-tier; simpler than micro)

```
rowsAll      = getCombinedRows()         // deduped by (year, sample_id) = 12,615 across 2024+2025
rowsScope    = rowsAll.filter(section + year + search)
```

All cards and charts consume `rowsScope`. Eliminates the 15,786 / 12,615 confusion.

## KPI cards (8, single row, no duplicate strip)

| # | Card | Source | Replaces |
|---|---|---|---|
| 1 | **Total samples** | `rowsScope.length` | "unique samples" wording |
| 2 | **Compliant samples** | `is_valid==1` count | "Valid samples" |
| 3 | **Non-compliant samples** | `is_valid==0` count | "Invalid samples", "INV" |
| 4 | **Compliance rate** | % of (1+2)/(1+2+3) | "% pass all panels" |
| 5 | **Total tests** | `test_counts.grand` (pre-computed) | new |
| 6 | **Compliant tests** | `test_counts.compliance_split.compliant` | new (item #2) |
| 7 | **Non-compliant tests** | `test_counts.compliance_split.non_compliant` | new (item #2) |
| 8 | **Sectors covered** | distinct `sector` count | "Unique facilities" deprioritised |

Old "Unknown verdict" card → removed. Duplicate KPI strip under section bar → removed.

## Charts / tables — actions

| Component | Action |
|---|---|
| Monthly chart | Rename to **"Monthly compliance results"**; only Compliant / Non-compliant bars (Rejected/No-limit/Unknown dropped) |
| YoY card | Rename to **"Year-over-year comparison"** (drop "(this section)"); drop triangle glyphs, use **Worse / Better / Flat** word tags; column headers "samples / Non-compliant / %"; aggregate row labelled **"Total samples"** |
| Validity donut | 2-slice: Compliant + Non-compliant (Unknown removed) |
| Sector breakdown card | Move to **below** Validity breakdown in grid order |
| Top failed tests bar | Arabic→English normaliser (الرطوبة→Moisture, الحموضة→Acidity, etc.); case-insensitive merging (`Cypermethrin` + `cypermethrin` count as one); drop sensory/texture tests; drop pesticide rows with conc < 0.01 ppm; drop placeholder Arabic "تراكيز المبيدات أقل من 0.01"; aflatoxin: keep B1/B2/G1/G2/Total distinct but label clearly as "Aflatoxin (total)" so users see why both Total and individual aflatoxins appear |
| Sample-category table | Drop Unknown column; Fail % = `invalid / (valid+invalid)` (Unknown rows excluded from denominator) |
| Drilldown table | "Issue / test" cell never blank for non-compliant rows — fall back to derived test list; pesticide trace (<0.01) filtered; "no test details on this row" message when truly empty |
| Honey section | Audit failed tests against schema's `direction:min` rule for HMF/Glucose+Fructose/Sucrose/Acidity; document in audit MD |
| Year chips | `"2025(25)"` → `"2025 · 25 samples"` |
| Water section description | Plain English: "Drinking-water tests: pH, electrical conductivity (EC), total dissolved solids (TDS), dissolved oxygen (DO), turbidity, chlorine, metals" |
| Pesticide December 2024 | Document any value anomalies in audit MD |

## Annual Report 2025 cross-check (chemistry stream)

| Metric | Annual Report | Our parquet (2025-only) | Δ |
|---|---:|---:|---:|
| Total samples | 7,287 | ~7,339 | +52 (+0.7%) |
| Total tests | 500,535 | ~498,622 | -1,913 (-0.4%) |
| Non-compliant tests | 763 | (compute) | (verify) |

Per-test breakdown (Pesticides 450,565/252, Aflatoxins 5,779/6, Water 6,833/229, Sensory 11,103/41, Heavy metals 19,295/203, etc.) ships in the audit MD with our per-section counts side-by-side.

## Deliverables

1. **This spec** — committed at `docs/superpowers/specs/2026-06-18-chemistry-dashboard-rework-design.md`
2. **Audit MD** — `chemistry/reports/chemistry_filter_audit.md` covering:
   - Per-section sample/test counts (2024 / 2025 / all)
   - AR cross-check with Δ per metric
   - Filter scenario matrix (section × year × search)
   - Label-fix verification checklist (28 items, pass/fail each)
3. **Rebuilt dashboard** at `chemistry/reports/chemistry_dashboard.html` + opened in browser

## Non-goals

- No changes to the cleaner (`scripts/clean_chemistry.py`) — only dashboard layer
- No changes to canonical mapping (`clean/scripts/apply_*.py`)
- No new charts beyond the rearrangement above
- No effect on microbio or joint dashboards
