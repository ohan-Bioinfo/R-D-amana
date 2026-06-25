# Microbiology dashboard — filter linkage fix design

**Date**: 2026-06-18
**Scope**: `food_analysis/Iter-2/scripts/build_dashboard_combined.py` only.

## Problem

Filters and charts are wired ad-hoc. When a SLICE filter (Severity / Microbe chip / Pathogen-only / Repeat-offender) narrows the data, several KPI cards and rate charts collapse to 100% non-compliance, which is mathematically true (all selected rows are by definition failures) but practically uninformative — users read it as "the chart broke".

Today the dashboard has partial fixes (`rowsBase` excludes severity for some charts), but the categorisation is inconsistent: microbe filter still collapses rate charts, pathogen-only still skews the trend, etc.

## Design

### Filter categorisation (three categories)

| Category | Filters | Effect |
|---|---|---|
| **SCOPE** | year, date, sector, mun_type, municipality, gso_category, compliance, exclude_raw_meat | Narrows the whole dataset — every chart and KPI respects scope. |
| **SLICE** | severity, microbe, pathogen_only, repeat_only | Only narrows slice-focused views. Sample-level KPIs and rate charts ignore slice. |

### Three row sets

In `applyFilters()`:

```js
rowsScope   = ROWS.filter(scope filters only)        // narrowed by year/date/sector/GSO/compliance/meat-exclude
rowsSliced  = rowsScope.filter(slice filters)        // further narrowed by severity/microbe/pathogen-only/repeat
rowsActive  = rowsSliced.filter(r => r[COLS.severity] !== 'none')   // severity events only
```

`renderAll(rowsActive, rowsSliced, rowsScope)`.

### Chart → row-set assignment

| Component | Row set |
|---|---|
| All 10 KPI cards | `rowsScope` |
| Top 10 most-contaminated subtypes | `rowsScope` |
| Riyadh map | `rowsScope` |
| Non-compliance trend chart | `rowsScope` |
| Sectors / GSO categories / Sub-municipalities (volume + rate) | `rowsScope` |
| Year-over-year, Day-of-week, Chains, Repeat-offender table | `rowsScope` |
| Severity breakdown by month | `rowsActive` |
| Severity × GSO category heatmap | `rowsActive` |
| Tests panels (pathogens / indicators side-by-side) | `rowsActive` |
| Sample drilldown table | `rowsSliced` |

Only 4 components respond to SLICE filters: severity-month, heatmap, tests panels, drilldown.

### Defensive caps

Every Plotly percentage axis hard-capped at `[0, 100]` with `fixedrange: true`. This prevents auto-scaled gridlines (110, 120, 150…) from being misread as data >100%.

### UI cue when slice is active

Small amber banner above the 4 slice-focused charts:

> *"Slice active: <selected filter description>. The 4 charts below are narrowed to this organism. KPIs and rate charts above show the full scope."*

Hidden when no slice filter is active.

## Audit deliverable

`food_analysis/Iter-2/reports/microbiology_filter_audit.md` — a verification matrix of every chart × every filter scenario showing the row set consumed, sample count returned, and pass/fail check against the parquet ground truth.

## Implementation order

1. Refactor `applyFilters()` to compute three row sets explicitly.
2. Update `renderAll()` signature to `(rowsActive, rowsSliced, rowsScope)` and pass the right one to each renderer.
3. Lock every render function to its assigned row set.
4. Cap percentage axes at `[0, 100]`.
5. Add the slice-filter banner element + render logic.
6. Run audit script across 20+ filter combos; write the MD file.
7. Rebuild + open.

## Non-goals

- No changes to chemistry or joint dashboards.
- No changes to the underlying parquet pipeline.
- No changes to the GSO category derivation (already complete from prior session work).
