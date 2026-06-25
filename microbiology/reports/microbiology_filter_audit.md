# Microbiology dashboard — full filter linkage audit

**Date**: 2026-06-18 · **Spec**: `docs/superpowers/specs/2026-06-18-micro-filter-linkage-fix-design.md`

Every chart × every filter scenario, ground-truth verified.

## Row-set per chart (post-fix)

| Chart / KPI | Row set | Notes |
|---|---|---|
| All 10 KPI cards | `rowsScope` | Total/Comp/NC stay meaningful regardless of slice filter |
| Top 10 most-contaminated subtypes | `rowsScope` | Rate denominators honest |
| Riyadh map | `rowsScope` | Per-location samples & rates |
| Non-compliance trend chart | `rowsScope` | Y-axis hard-capped [0,100] |
| Sectors / GSO / Sub-municipalities (volume + rate) | `rowsScope` | Stacked-by-year + rate line (y2 also capped [0,100]) |
| Year-over-year | `rowsScope` | |
| Top 15 chains | `rowsScope` | |
| Day-of-week | `rowsScope` | |
| Repeat-offender chains | `rowsScope` | |
| **Severity breakdown by month** | `rowsActive` | **SLICE-AWARE** |
| **Severity tier × GSO heatmap** | `rowsActive` | **SLICE-AWARE** |
| **Tests panels (pathogens / indicators)** | `rowsActive` | **SLICE-AWARE** |
| **Sample drill-down table** | `rowsSliced` | **SLICE-AWARE** |

## Filter scenarios — counts verified against ground truth

| Scenario | rowsScope | rowsSliced | rowsActive | KPI Total | KPI Non-comp | Compliance % |
|---|---:|---:|---:|---:|---:|---:|
| No filter | 22,596 | 22,596 | 6,257 | 22,596 | 6,258 | 72.3% |
| Year 2025 | 11,564 | 11,564 | 3,038 | 11,564 | 3,039 | 73.7% |
| Sector East | 4,265 | 4,265 | 1,210 | 4,265 | 1,210 | 71.6% |
| GSO=Dairy Products | 2,355 | 2,355 | 818 | 2,355 | 818 | 65.3% |
| Sub-muni الروضة | 4,118 | 4,118 | 1,174 | 4,118 | 1,174 | 71.5% |
| Compliance=Non-compliant | 6,258 | 6,258 | 6,257 | 6,258 | 6,258 | 0.0% |
| Exclude raw/cooked meat | 20,840 | 20,840 | 5,805 | 20,840 | 5,806 | 72.1% |
| SCOPE multi: 2025+East+Dairy | 281 | 281 | 106 | 281 | 106 | 62.3% |
| SLICE: Severity=pathogen | 22,596 | 1,776 | 1,776 | 22,596 | 6,258 | 72.3% |
| SLICE: Severity=multi_pathogen | 22,596 | 315 | 315 | 22,596 | 6,258 | 72.3% |
| SLICE: Microbe=Salmonella | 22,596 | 190 | 190 | 22,596 | 6,258 | 72.3% |
| SLICE: Microbe=Listeria (zero-fail) | 22,596 | 0 | 0 | 22,596 | 6,258 | 72.3% |
| SLICE: Pathogen-only | 22,596 | 2,091 | 2,091 | 22,596 | 6,258 | 72.3% |
| SLICE: Repeat-offender | 22,596 | 8,832 | 3,034 | 22,596 | 6,258 | 72.3% |
| SCOPE+SLICE: 2025+Salmonella | 11,564 | 122 | 122 | 11,564 | 3,039 | 73.7% |
| SCOPE+SLICE: 2025+Severity=pathogen | 11,564 | 851 | 851 | 11,564 | 3,039 | 73.7% |

## Key behaviour assertions (pass/fail)

| Check | Result |
|---|---|
| Baseline scope = 22,596 | ✓ |
| Year 2025 scope = 11,564 | ✓ |
| SLICE: Salmonella scope unchanged (= baseline) | ✓ |
| SLICE: Salmonella sliced count = 190 | ✓ |
| SLICE: pathogen scope unchanged | ✓ |
| SLICE: pathogen sliced count = 1,776 | ✓ |
| KPI Total card stays meaningful when slice filter active | ✓ |

**Overall**: ✓ ALL ASSERTIONS PASSED

## Defensive axis caps

| Axis | Cap | Why |
|---|---|---|
| Trend chart left y (`% of samples`) | `range: [0,100], fixedrange: true` | Prevents Plotly auto-scale gridlines at 110/120/150 being misread as data > 100% |
| Volume/rate charts right y2 (`% non-compliance`) | `range: [0,100]` | Same reason for sector/GSO/sub-muni rate line |
