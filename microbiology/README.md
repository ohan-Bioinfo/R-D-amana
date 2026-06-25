# Riyadh Food-Safety Lab Data — Iter-2

Cleans and analyses Riyadh municipality food-safety lab inspection data
(microbiological tests vs. **GSO 1016** standards). Stacks **2023 + 2024 +
2025** into a single self-contained interactive HTML dashboard.

## Status

| Year | Source format | Samples (wide) | Per-test rows (long) | GSO-decodable | Notes |
|---:|---|---:|---:|---:|---|
| 2023 | 80 monthly xlsx files (Aug–Dec only) | **2,938** | 10,310 | 33% | Aug–Oct forms have no GSO code; no facility data |
| 2024 | 183 monthly xlsx files (Jan–Dec) | **8,094** | 31,583 | 85% | Header row varies (6 in Jan, 12 Feb–Dec); no facility data |
| 2025 | Single consolidated xlsx | **11,564** | – (already wide) | 0% (no codes at source) | Has full facility + sector + sample-type metadata |
| **Combined** | — | **22,596** | — | — | Stacked on 43 shared columns |

## File layout

```
food_analysis/Iter-2/
├── README.md                              ← this file
│
├── 2023/                                  ← source xlsx files (5 monthly folders)
├── 2024-original/2024/                    ← source xlsx files (12 monthly folders)
├── 2025-original/Data 2025.xlsx           ← single source xlsx
│   2025-original/Annual Report 2025.xlsx
│
├── schemas/
│   ├── lab_data_2024_v2.yaml              ← shared by 2023 + 2024 cleaning
│   ├── lab_data_2025_v1.yaml              ← 2025-specific + pathogen/indicator + sector taxonomy
│   └── gso_1016_reference.yaml            ← parsed from Classification.html
│
├── scripts/                               ← active pipeline (see below)
│
├── cleaned/                               ← output parquets (zstd-compressed)
│   ├── data2023.parquet         (wide, per-sample)
│   ├── data2023_long.parquet    (long, per-sample-test)
│   ├── data2024.parquet
│   ├── data2024_long.parquet
│   └── data2025.parquet         (wide only; source is already per-sample)
│
├── reports/
│   ├── data_combined_dashboard.html       ← MAIN OUTPUT — open in any browser
│   ├── data<YEAR>_clean_report.md         ← per-file audit per year
│   ├── data2025_diff.md / _review.md      ← 2025-specific cleaning audit
│   └── data2025_vs_annual_report.{md,csv} ← 2025 vs published annual report comparison
│
└── archive/                               ← deprecated v1 scripts, schemas, dashboards
```

## Active pipeline

End-to-end build from sources, **in this order**:

```bash
# 1. Parse the GSO 1016 standards table (only re-run if Classification.html changes)
.venv/bin/python scripts/parse_gso_reference.py

# 2. Clean each year. The 2024 cleaner is year-parameterised and handles 2023 too.
.venv/bin/python scripts/clean_2024.py --year 2023
.venv/bin/python scripts/clean_2024.py --year 2024
.venv/bin/python scripts/clean_2025.py 2025-original/'Data 2025.xlsx' \
    cleaned/data2025.parquet reports/data2025_diff.md

# 3. Enrich each year's wide parquet (pathogen/indicator/severity/repeat-offender + sector=null for pre-2025)
.venv/bin/python scripts/enrich_2024.py --year 2023
.venv/bin/python scripts/enrich_2024.py --year 2024

# 4. Apply the GSO reference (product names, categories, limits, panel-completeness audit)
.venv/bin/python scripts/enrich_gso.py

# 5. Build the combined dashboard (auto-discovers every cleaned/data<YEAR>.parquet)
.venv/bin/python scripts/build_dashboard_combined.py
```

After step 5, open `reports/data_combined_dashboard.html` in a browser.

## Active scripts (in `scripts/`)

| Script | Purpose |
|---|---|
| `clean_2024.py` | Year-parameterised cleaner for the 2023+2024 form shape. CLI: `--year <YYYY>`. |
| `clean_2025.py` | 2025-specific cleaner (single flat xlsx, different schema). |
| `enrich_2024.py` | Adds pathogen/indicator/severity/repeat-offender columns. CLI: `--year <YYYY>`. |
| `enrich_gso.py` | Auto-iterates every `data<YEAR>.parquet`; adds GSO product info, panel-completeness flag, lab-vs-GSO-limit cross-check. |
| `parse_gso_reference.py` | Parses `Classification.html` → `schemas/gso_1016_reference.yaml`. |
| `build_dashboard_combined.py` | Builds the single self-contained dashboard from all years. |
| `audit_filters.py` | Sanity-check script: simulates every dashboard filter against the parquets and reports counts. |
| **Auxiliary tools** | |
| `compare_against_annual_report.py` | Compares 2025 cleaned data to the published Annual Report. |
| `build_summary_pack.py` | Generates summary CSVs + figures (one-off). |
| `export_by_keyword.py` | Exports samples matching free-text keywords. |
| `export_csv_2025.py` | One-off 2025 CSV export. |
| `explore.py` | Original exploratory script (kept for reference). |

## Dashboard features (`data_combined_dashboard.html`)

**Filters** (grouped into 6 sections):
- **Year** — 2023 / 2024 / 2025 chips (top bar)
- **Time & Compliance** — date range, compliance (pass/fail), severity tier
- **Location (2025 only)** — sector, municipality type, municipality multi-select
- **Sample product** — sample type (2025), GSO category (2024), GSO product multi-select (2024)
- **Microbe** — per-organism chips (Salmonella, S. aureus, E.coli, Listeria, etc.) + "Indicator" meta-chip
- **GSO 1016 audit (2024-only)** — show only panel-incomplete, show only lab-vs-GSO disagreement, pathogen-only, repeat offender
- **Quick excludes** — raw meat & poultry, total bacterial count, yeasts & moulds, animal feed, indicator-only samples

**Visualisations:**
- Riyadh map with 16 canonical sub-municipality bubbles (3 metrics × 3 view modes × 3 tile styles)
- Trend over time (non-compliance %, pathogen %, volume)
- Year-on-year severity comparison
- Sector breakdown
- GSO category breakdown
- Top chains by non-compliance (2025)
- Failed-test bar (pathogen vs indicator coloured)
- Municipality failure rate
- Day-of-week cadence
- Repeat-offender table
- Sample drill-down (200-row table)

## Schema notes

### `lab_data_2024_v2.yaml`
Used for both 2023 and 2024. Detects header row dynamically (row 6 in Jan-2024 + all of 2023; row 12 in Feb–Dec 2024) by scanning for `M.S.No`. Column mapping is **name-based** rather than position-based, so monthly format drift (extra `104` column, `الاختبارات التأكيدية` block, missing `Restaurant name` / `GSO code` etc.) is handled gracefully — required vs optional columns are explicit in the schema.

Canonical test names (Arabic-first) include 2024-introduced pathogens: Listeria, Clostridium perfringens/botulinum, Campylobacter, Vibrio, Aeromonas, E.coli O157.

### `lab_data_2025_v1.yaml`
2025-specific shape. Includes:
- Pathogen / indicator classification (used by both years' enrichment)
- Sector taxonomy (5 sectors × 16 sub-municipalities — authoritative from user)
- Sample-type bucket keywords
- Repeat-offender rules (90-day window, threshold ≥ 2)

### `gso_1016_reference.yaml`
Parsed from `Classification.html` (the user-supplied GSO 1016 standards table). **15 product categories, 130 GSO codes, 485 test-requirement rows**. Each code has English/Arabic names, sub-products, required tests, and numeric limits.

## Known caveats per year

**2023:** Only Aug–Dec covered. No facility/sector/municipality data. Aug–Oct forms have no GSO code. The Sep-2023 file `Result 05092023.xlsx` could not be parsed (sheet date unparseable).

**2024:** No facility/sector/municipality data anywhere — the source forms simply didn't capture it. 20 empty xlsx files were skipped. **30% of samples** ran the full GSO panel; **70 samples** show lab marking valid but result exceeds GSO limit (worth flagging upstream).

**2025:** No GSO code field at source — product cannot be decoded into the GSO 1016 taxonomy. Has rich facility data (chain/branch split), municipality, and the 5 canonical sectors.

## Adding a new year

1. Drop the source xlsx files under e.g. `2026/` (with monthly subfolders, similar to 2023/).
2. Add a `YEAR_CONFIG` entry in `scripts/clean_2024.py` pointing to the new source dir.
3. If filenames use a new pattern, extend `FILENAME_PATTERNS` in `clean_2024.py`.
4. Run steps 2–5 of the active pipeline above (substituting `--year 2026`).
5. The dashboard builder will auto-discover the new parquet.

If the new year follows the 2025 single-flat-xlsx shape instead, copy `clean_2025.py` as a starting point.
