# Archived validation tools — 2026-07 rounds (retired 2026-08-07)

One-off scripts that generated review/audit workbooks for specific data-validation
and taxonomy sign-off rounds during 2026-06 → 2026-07. Those rounds are **done** —
their rulings are baked into the cleaners, `enrich_gso.py`, the correction CSVs,
and `build_classification_table.py`. Kept for provenance; not part of the build.

| Script | Produced (now in `archive/reports-validation-2026-07/`) |
|---|---|
| `build_full_review_workbook.py` | `full_classification_review_to_fill.xlsx` |
| `build_correction_workbook.py` | `classification_corrections_to_fill.xlsx` |
| `build_audit_2025.py` | `audit_2025_to_fill.xlsx` |
| `build_fruit_swab_review.py` | `fruit_swab_review_to_fill.xlsx` |
| `build_reconciliation_workbook.py` | `annual_reconciliation_to_fill.xlsx` |
| `build_verification_workbook.py` | `annual_verification_check.xlsx` |
| `compare_against_annual_report.py` | `data2025_vs_annual_report.{md,csv}` |
| `build_summary_pack.py` | summary CSVs + matplotlib figures |
| `audit_filters.py` | QA: simulates dashboard filters vs parquets — **stale**: expects the old `data_combined_dashboard.html` and a `sample_types` facet key the current dashboard no longer emits. Would need a rewrite against the current facets schema to run. |
| `explore.py` | original exploratory dumps |
| `export_csv_2025.py` | one-off 2025 CSV export |
| `export_by_keyword.py` | ad-hoc keyword sample export |

**To run one again:** they import `build_classification_table` / `build_dashboard_combined`
from the active `scripts/`, so run from `microbiology/` with `scripts/` importable, e.g.
`PYTHONPATH=scripts .venv/bin/python archive/validation-tools-2026-07/<script>.py`.

The build itself is verified reproducible without any of these — `./scripts/refresh.sh`
regenerates byte-identical parquets (20,880 rows).
