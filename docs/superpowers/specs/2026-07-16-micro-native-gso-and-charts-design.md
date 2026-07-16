# Micro Dashboard — Native 2024 GSO Fix + Tables → Charts

**Date:** 2026-07-16
**Status:** Approved
**Scope:** Microbiology only. No chemistry files touched.

## 1. Two changes

### A. Union-concat fix (data correctness)
`main()` builds the combined frame from the **column intersection**
(`pd.concat([f[shared] for f in frames])`). Because 2025 has no native GSO
columns, the intersection drops `gso_category_name_en`, `gso_product_name_en`,
`gso_code_canonical`, `gso_panel_complete`, `gso_lab_vs_gso_disagree` for 2024
too — so 2024 loses its authoritative lab GSO and falls back to keyword
`classify_sample_name` (Miscellaneous 49→484, Fats&Oils 16→285, Jelly 113→92),
and `FACETS.gso_categories` omits those native-only categories (861 rows unable
to be filtered / shown in the heatmap).

**Fix:** union the columns — `combined = pd.concat(frames, ignore_index=True)`
(drop the `[f[shared]]` subset; drop the now-unused `shared`). `build_data` /
`build_facets` read columns via `getattr(..., None)`, so 2025's missing GSO
columns become NaN and correctly fall through to the `sample_type` derivation,
while 2024 regains native GSO. Expected after: 2024 Misc ≈ 49, Fats ≈ 16, Jelly
≈ 113; `FACETS.gso_categories` includes Jelly/Fats/Misc; 2024 drill-down regains
GSO product + code.

### B. Tables → charts
Convert every tabular component to a chart, in the one combined dashboard:

| Component | Now | → |
|---|---|---|
| Tier-1 per-test failure rate | table | horizontal bar (rate per test, ranked) |
| Tier-1 sector split | table | bar (samples per sector) |
| Top-10 most-contaminated subtypes | table | horizontal bar (rate, colour by severity; organisms in hover) |
| Repeat-offender chains | table | horizontal bar (max 90-day streak, colour) |
| Test drill-down (by year / facility / category) | 3 tables | 3 mini horizontal bars |
| **Sample drill-down (raw rows)** | table | **removed entirely** (record-level view, not an aggregate) |

Charts use the already-vendored Plotly via `Plotly.react`, matching the existing
chart styling (transparent bg, Segoe UI, year colours, `PLOTLY_CONFIG`).

## 2. Implementation stages (each: edit → regenerate → node --check → verify → commit)

- **A.** Union fix in `main()`; verify 2024 native GSO restored + `FACETS.gso_categories` complete.
- **B.** Remove `renderDrilldown` + its `#drilldown-table` card + the `renderAll` call.
- **C.** `renderAnnual`: per-test + sector tables → two Plotly bar charts (new mount divs in `#annual-body`).
- **D.** `renderTopSubtypes`: table → horizontal bar (`Plotly.react` on `#top-subtypes`).
- **E.** `renderRepeatTable` → `renderRepeatChart`: table → horizontal bar on the repeat card.
- **F.** `renderTestsDrilldown`: 3 tables → 3 mini bar charts.

## 3. Verification
- `node --check` on the generated dashboard `<script>` after every stage.
- Union fix: 2024 category distribution matches native (Misc ≈ 49, not 484); the
  3 categories appear in `FACETS.gso_categories`; 2025 GSO unchanged (Fish 130 /
  Egg 32 / Cereals 67 / 0 Misc); Tier-1 2025 still 11,404 / 46,309 / 4,211.
- Charts: every former table id renders a Plotly chart (no residual `<table>` in
  those mounts); the sample drill-down is gone.
- Micro-only commits (`git diff --cached --name-only | grep -c chemistry` = 0).

## 4. Out of scope
Phase 2 (2024 Annual Report + richer raw). Category *logic* is unchanged beyond
2024 now preferring its native GSO (which the pipeline already intended).
